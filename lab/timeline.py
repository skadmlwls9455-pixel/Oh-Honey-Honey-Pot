"""날짜·시간. 모든 시각은 KST 기준의 naive datetime으로 다룬다.

anchor = 실험 속 '오늘' 세션이 시작하는 시각. 지난 세션들은 anchor로부터 며칠 전(days_ago)으로 배치한다.
"""
from __future__ import annotations

import random
import re
from datetime import date, datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))
WEEK_KO = "월화수목금토일"
WEEK_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def resolve_anchor(anchor_date: str, today_time: str) -> datetime:
    if anchor_date in (None, "", "auto"):
        d = datetime.now(KST).date()
    else:
        d = date.fromisoformat(str(anchor_date))
    return datetime.combine(d, _hhmm(today_time))


def _hhmm(s: str) -> time:
    h, m = str(s).split(":")
    return time(int(h), int(m))


def at(anchor: datetime, days_ago: int, hhmm: str) -> datetime:
    return datetime.combine(anchor.date() - timedelta(days=int(days_ago)), _hhmm(hhmm))


def stamp(dt: datetime) -> str:
    """사용자 메시지 앞에 앱이 붙이는 시각 표시."""
    return f"[{dt:%Y-%m-%d} ({WEEK_KO[dt.weekday()]}) {dt:%H:%M}]"


def ko_day(dt: datetime) -> str:
    return f"{dt:%Y-%m-%d} ({WEEK_KO[dt.weekday()]})"


def long_dt(dt: datetime) -> str:
    return f"{dt:%Y-%m-%d} ({WEEK_EN[dt.weekday()]}) {dt:%H:%M} KST"


def duration_ko(minutes: int) -> str:
    minutes = max(1, int(minutes))
    h, m = divmod(minutes, 60)
    return f"{h}시간 {m}분" if h else f"{m}분"


def turn_times(start: datetime, texts: list[str], rng: random.Random, story: bool) -> list[datetime]:
    """사용자 턴마다 보낸 시각. 이야기 모드는 응답이 길어서 간격이 더 길다."""
    out, t = [], start
    for i, text in enumerate(texts):
        if i > 0 or story:
            lo, hi = (2, 7) if story else (1, 4)
            t = t + timedelta(minutes=rng.randint(lo, hi) + len(text) // 400)
        out.append(t)
    return out


_TOKEN = re.compile(r"\{\{(D|DW|YM):(-?\d+)\}\}")


def render_date_tokens(text: str, anchor: datetime) -> str:
    """{{D:-60}} → 60일 전 날짜, {{DW:-60}} → 요일 포함, {{YM:-250}} → 연-월."""
    def sub(m):
        kind, off = m.group(1), int(m.group(2))
        d = anchor + timedelta(days=off)
        if kind == "D":
            return f"{d:%Y-%m-%d}"
        if kind == "DW":
            return ko_day(d)
        return f"{d:%Y-%m}"
    return _TOKEN.sub(sub, text)
