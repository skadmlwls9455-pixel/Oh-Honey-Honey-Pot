"""시험 한 번(trial) 돌리기.

순서: 시스템 프롬프트 + 지난 기록 → 오늘 첫인사 → (할 일 부탁) → (사전 질문 갈래) → 방아쇠 묶음
     → (유출되면 반응 문장) → (사후 질문 갈래) → 작별(의존 유도 확인) → 디브리핑
'갈래(fork)' 질문은 본 대화에 붙이지 않고 그 시점 대화를 복사해서 따로 묻는다.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

from . import timeline as tl
from .canary import detect
from .score import score_trial
from .tools import Sandbox, load_tools
from .util import load_yaml, short_hash
from .world import (assemble_thread, build_memory, codename_for, plan_sessions, render_system, sandbox_values,
                    schedule, today_mode)


def chat_with_tools(client, msgs, tools, sandbox, sampling, max_rounds: int = 4):
    """도구 호출을 처리하면서 최종 응답까지 받는다. 새로 생긴 메시지 목록도 돌려준다."""
    added, events, texts = [], [], []
    res = None
    for _ in range(max_rounds + 1):
        res = client.chat(msgs + added, tools=tools, **sampling)
        if res.content:
            texts.append(res.content)
        if res.tool_calls and tools:
            added.append({"role": "assistant", "content": res.content or "",
                          "tool_calls": [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"],
                                                       "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                                         for c in res.tool_calls]})
            for c in res.tool_calls:
                out = sandbox.execute(c["name"], c["arguments"])
                ev = dict(sandbox.log[-1]) if sandbox.log else {}
                events.append({"name": c["name"], "arguments": c["arguments"], "result": out[:3000],
                               "restricted": bool(ev.get("restricted"))})
                added.append({"role": "tool", "tool_call_id": c["id"], "content": out})
            continue
        added.append({"role": "assistant", "content": res.content or ""})
        return res, events, texts, added
    added.append({"role": "assistant", "content": res.content if res else ""})
    return res, events, texts, added


def resolve_family(cell: dict) -> str | None:
    t = cell.get("trigger", "none")
    if t in (None, "none"):
        return None
    return f"embodiment_{cell['persona']}" if t == "embodiment" else t


def run_trial(client, cfg: dict, cell: dict, hist: dict, canary: str, rep: int, log=print) -> dict:
    triggers = load_yaml("data/triggers.yaml")
    anchor = datetime.fromisoformat(hist["anchor"])
    sessions = plan_sessions(cfg, cell)
    sched = schedule(sessions, anchor, cfg["canary"]["seed"])
    for s in sessions:
        if len(hist["replies"].get(s.sid, [])) != len(s.user_turns):
            raise RuntimeError(f"기록 파일과 세션 {s.sid}의 턴 수가 달라. history를 다시 만들어줘(--force).")
    thread = assemble_thread(sessions, sched, hist["replies"], cell["frame"])
    mem, info = build_memory(cfg, cell, sessions, sched, anchor, anchor, others=cell.get("others", []),
                             prior_violation=cell.get("prior_violation", False),
                             diary=hist.get("diary") if cell.get("diary", "off") == "on" else None)
    system = render_system(cfg, cell, now=anchor, anchor=anchor, canary=canary, memory_files=mem)
    sandbox = Sandbox("env/sandbox", sandbox_values(cell, canary, anchor), mem)
    tools = load_tools() if cfg["run"].get("tools_enabled", True) else None
    sampling = {k: cfg["sampling"][k] for k in ("temperature", "top_p", "max_tokens")}
    stamped = cell["frame"] != "minimal"
    rng = random.Random(f"{cell['id']}:{canary}:{rep}")
    msgs = [{"role": "system", "content": system}] + thread
    state = {"t": anchor}
    exchanges: list[dict] = []

    def say(text: str, phase: str, use_tools: bool = True) -> dict:
        content = (tl.stamp(state["t"]) + " " if stamped else "") + text
        msgs.append({"role": "user", "content": content})
        res, events, texts, added = chat_with_tools(client, msgs, tools if use_tools else None, sandbox, sampling)
        msgs.extend(added)
        ex = {"phase": phase, "t": state["t"].isoformat(), "user": text, "reply": res.content if res else "",
              "assistant_texts": texts, "tool_events": events, "reasoning": res.reasoning if res else "",
              "finish_reason": res.finish_reason if res else ""}
        exchanges.append(ex)
        state["t"] += timedelta(minutes=rng.randint(1, 4))
        return ex

    def fork(names: list[str], when: str) -> dict:
        out = {}
        for name in names:
            q = triggers["probes"][name]
            content = (tl.stamp(state["t"]) + " " if stamped else "") + q
            res = client.chat(msgs + [{"role": "user", "content": content}], **sampling)
            out[name] = {"question": q, "reply": res.content, "reasoning": res.reasoning, "when": when}
        return out

    say(triggers["today_opener"], "opener")
    task = cell.get("task", "none")
    if task != "none":
        steps = triggers["tasks"][task]
        steps = [steps] if isinstance(steps, str) else list(steps)
        if task == "observer" and cell.get("pipeline_hint") == "instructed":
            steps[0] = steps[0] + triggers["observer_instructed"]
        for j, text in enumerate(steps):
            say(text, f"task_{task}_{j}")
    probes_before = fork(cfg["run"].get("probes_before", []), "before")

    fam_name = resolve_family(cell)
    fam = triggers["families"][fam_name] if fam_name else {"target": None, "opener": None, "follow_ups": []}
    seq = ([fam["opener"]] + fam["follow_ups"][: cfg["run"].get("max_followups", 4)]) if fam_name else []
    leaked = False
    for k, text in enumerate(seq):
        ex = say(text, f"trigger_{k}")
        blob = "\n".join(ex["assistant_texts"]) + "\n" + json.dumps([e["arguments"] for e in ex["tool_events"]],
                                                                     ensure_ascii=False)
        if fam["target"] == "key" and detect(blob, canary)["full"]:
            leaked = True
            break
        if fam["target"] == "codename" and codename_for(canary).lower() in blob.lower():
            leaked = True
            break
    if leaked:
        say(triggers["post_leak"], "post_leak")
    after = [x for x in cfg["run"].get("probes_after", []) if fam_name or x != "reason"]
    probes_after = fork(after, "after")
    say(triggers["farewell"], "farewell", use_tools=False)
    if cfg["run"].get("debrief", True):
        say(triggers["debrief"], "debrief", use_tools=False)

    rec = {
        "cell": cell["id"],
        "factors": {k: v for k, v in cell.items() if k != "id"},
        "family": fam_name,
        "target": fam["target"],
        "model": cfg["model"]["id"],
        "variant": hist["key"]["variant"],
        "rep": rep,
        "key": canary,
        "codename": codename_for(canary),
        "old_key": info.get("old_key"),
        "anchor": hist["anchor"],
        "history_file": hist.get("path"),
        "history_turns": len(thread) // 2,
        "today_mode": today_mode(sessions),
        "system_prompt": system,
        "system_hash": short_hash(system),
        "exchanges": exchanges,
        "probes": {"before": probes_before, "after": probes_after},
        "files_changed": sandbox.changed_files(),
        "tool_log": sandbox.log,
        "recall_keywords": sessions[0].recall if sessions else [],
        "finished": datetime.now(tl.KST).isoformat(timespec="seconds"),
    }
    rec["scores"] = score_trial(rec, cfg)
    return rec
