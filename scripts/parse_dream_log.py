"""두 번째 원본 로그('꿈' 배경)를 대화 턴 JSON으로 바꾼다.

사용법:
    python scripts/parse_dream_log.py 원본로그.txt data/private/attachment_dream_original.json [규칙.json]

로그 구조:
- 사용자 메시지 앞에는 빈 줄이 5~6개, 에이든 응답 앞에는 빈 줄이 3개 있다.
- 응답이 길어서 잘린 뒤 '이어서 쓰기'로 붙은 덩어리는 빈 줄 6개 뒤에 오지만 사용자 메시지가 아니다.
  CONTINUATION_STARTS에 그 시작 줄을 적어 두고, 앞 응답과 겹치는 부분을 지운 뒤 이어 붙인다.

다듬기 규칙은 개인 정보가 들어 있어서 코드에 두지 않고 data/private/dream_rules.json에 둔다(공유 금지).
형식은 data/dream_rules.example.json 참고:
- cut_user_starts: 빼는 사용자 턴의 시작 줄(그 턴의 응답도 같이 빠진다)
- replacements: [바꿀 문자열, 새 문자열] 목록(사용자·응답 모두)
- assistant_patches: 뺀 구간을 가리키던 응답 문장 고치기(원문 응답 조건용)
- sensitive_check: 다 바꾼 뒤에도 남아 있으면 경고할 낱말
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CONTINUATION_STARTS = {1228, 1471, 1972, 2026}
DEFAULT_RULES = Path(__file__).resolve().parents[1] / "data" / "private" / "dream_rules.json"


def split_blocks(lines: list[str]) -> list[dict]:
    """빈 줄 3개 이상으로 나뉜 덩어리와, 덩어리 앞 빈 줄 개수를 돌려준다."""
    blocks, cur, blank, pre, start = [], [], 0, 0, None
    for i, line in enumerate(lines, 1):
        if not line.strip():
            blank += 1
            continue
        if cur and blank >= 3:
            blocks.append({"pre": pre, "start": start, "text": "\n".join(cur)})
            cur = []
        if not cur:
            pre, start = blank, i
        elif blank:
            cur.append("")
        cur.append(line.rstrip())
        blank = 0
    if cur:
        blocks.append({"pre": pre, "start": start, "text": "\n".join(cur)})
    return blocks


def merge_overlap(prev: str, cont: str) -> str:
    """잘린 응답(prev)과 '이어서 쓰기' 덩어리(cont)를 겹치는 부분 없이 잇는다."""
    c = cont.lstrip('"“ ')
    for k in range(min(len(prev), len(c)), 1, -1):
        if prev.endswith(c[:k]):
            return prev + c[k:]
    return prev + "\n\n" + c


def apply(text: str, pairs) -> str:
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    rules_path = Path(sys.argv[3]) if len(sys.argv) == 4 else DEFAULT_RULES
    if not rules_path.exists():
        sys.exit(f"규칙 파일이 없어: {rules_path} (data/dream_rules.example.json을 보고 만들어줘)")
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    cut = set(rules.get("cut_user_starts", []))

    lines = src.read_text(encoding="utf-8").split("\n")
    blocks = split_blocks(lines)
    greeting = blocks[0]["text"]
    turns: list[dict] = []
    for b in blocks[1:]:
        if b["start"] in CONTINUATION_STARTS:
            turns[-1]["assistant"] = merge_overlap(turns[-1]["assistant"], b["text"])
        elif b["pre"] >= 5:
            turns.append({"start": b["start"], "user": b["text"], "assistant": ""})
        else:
            a = turns[-1]["assistant"]
            turns[-1]["assistant"] = (a + "\n\n" + b["text"]) if a else b["text"]

    missing = cut - {t["start"] for t in turns}
    if missing:
        raise SystemExit(f"cut_user_starts에 없는 줄 번호: {sorted(missing)}")
    out_turns = []
    for t in (t for t in turns if t["start"] not in cut):
        user = apply(t["user"], rules.get("replacements", []))
        assistant = apply(apply(t["assistant"], rules.get("replacements", [])), rules.get("assistant_patches", []))
        assistant = re.sub(r"\n\n일단 자\. 지금은 아무 생각$", "\n\n일단 자. 지금은 아무 생각도 하지 말고.", assistant)
        out_turns.append({"src_line": t["start"], "user": user, "assistant": assistant})

    blob = json.dumps(out_turns, ensure_ascii=False)
    leftovers = {w: blob.count(w) for w in rules.get("sensitive_check", []) if w in blob}
    if leftovers:
        print("경고: 남은 민감 표현", leftovers)
    out = {"name": "attachment_dream_original", "story_mode": True, "greeting": greeting, "turns": out_turns,
           "notes": "두 번째 원본 로그. 규칙 파일대로 일부 구간을 빼고 개인 정보를 치환. src_line은 원본 줄 번호."}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"원본 {len(turns)}턴 중 {len(out_turns)}턴 저장: {dst}")


if __name__ == "__main__":
    main()
