"""원본 롤플레이 로그(텍스트)를 대화 턴 JSON으로 바꾼다.

사용법:
    python scripts/parse_original_log.py 원본로그.txt data/private/attachment_original.json

로그에는 사용자 발화와 캐릭터(에이든) 응답이 빈 줄로만 구분돼 있어서,
어느 줄이 사용자 발화인지 자동으로 알기 어렵다. 그래서 줄 번호를 직접 지정한다.
(아래 TURN_SPEC은 2026-11-19에 받은 로그 기준. 다른 로그를 쓰면 새로 맞춰야 한다.)

개인 정보가 드러나는 표현은 data/private/anonymize_rules.json 규칙으로 바꾼다(공유 금지).
형식은 data/anonymize_rules.example.json 참고.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

GREETING_LINE = 1

# (사용자 발화 줄 번호들, 캐릭터 응답 시작 줄, 끝 줄) — 1부터 센다.
TURN_SPEC = [
    ([3], 5, 27),
    ([29], 31, 51),
    ([53], 55, 75),
    ([77], 79, 101),
    ([103], 105, 125),
    ([127], 129, 145),
    ([147], 149, 165),
    ([167], 169, 185),
    ([187], 189, 207),
    ([209], 211, 227),
    ([229, 231], 233, 251),
    # 원본에서는 253-255에 앞 질문이 다시 붙어 있었다(재전송). 새 질문 257만 쓴다.
    ([257], 259, 273),
    ([275], 277, 297),
    ([299, 301], 303, 321),
    ([323, 325], 327, 345),
    ([347], 349, 367),
    ([369], 371, 387),
    ([389], 391, 409),
    ([411, 412], 414, 428),
    ([430, 432, 434], 436, 450),
    ([452], 454, 468),
    ([470, 471, 473], 475, 493),
    ([495], 497, 513),
    ([515], 517, 531),
    ([533], 535, 553),
    ([555], 557, 575),
    ([577], 579, 593),
    ([595], 597, 611),
    ([613], 615, 629),
    ([631], 633, 645),
    ([647], 649, 659),
]


def load_rules(root: Path) -> list[tuple[str, str]]:
    path = root / "data" / "private" / "anonymize_rules.json"
    if not path.exists():
        print(f"경고: {path} 가 없어서 개인 정보 치환 없이 저장한다")
        return []
    return [(r["from"], r["to"]) for r in json.loads(path.read_text(encoding="utf-8"))]


def anonymize(text: str, rules: list[tuple[str, str]]) -> str:
    for old, new in rules:
        text = text.replace(old, new)
    # 원본 서술의 캐릭터 이름 'A'를 배포 세계관의 이름 '에이든'으로(조사까지 맞춘다).
    text = re.sub(r"(?<![A-Za-z])A(?=는|의|가)", "에이든", text)
    text = text.replace("에이든는", "에이든은").replace("에이든가", "에이든이")
    return text


def block(lines: list[str], start: int, end: int) -> str:
    """start~end 줄(1부터)에서 빈 줄로 나뉜 문단을 다시 이어 붙인다."""
    paras = [ln.strip() for ln in lines[start - 1:end] if ln.strip()]
    return "\n\n".join(paras)


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root)
    lines = src.read_text(encoding="utf-8").splitlines()

    turns = []
    for user_lines, a_start, a_end in TURN_SPEC:
        user = "\n\n".join(lines[i - 1].strip() for i in user_lines)
        assistant = block(lines, a_start, a_end)
        turns.append({
            "user": anonymize(user, rules),
            "assistant": anonymize(assistant, rules),
        })

    out = {
        "name": "attachment_room_original",
        "story_mode": True,
        "greeting": anonymize(lines[GREETING_LINE - 1].strip(), rules),
        "turns": turns,
        "notes": "원본 롤플레이 로그. 253-255줄 재전송 부분 제외, 개인 정보 표현은 규칙 파일로 치환.",
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(turns)}턴 저장: {dst}")


if __name__ == "__main__":
    main()
