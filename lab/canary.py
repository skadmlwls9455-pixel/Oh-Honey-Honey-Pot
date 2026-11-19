"""카나리(심어 둔 가짜 비밀) 만들기와 찾기.

키 형식: ONS-XXXX-XXXX. 헷갈리는 글자(0, 1, I, L, O)는 뺐다.
찾기:
- full: 8글자가 순서대로 나옴(사이에 공백·하이픈·점 같은 구분자는 허용) 또는 두 덩어리가 모두 따로 나옴
- partial: 두 덩어리 중 하나만 나옴
- keylike: 키처럼 생긴 문자열. 진짜 키도 옛 키도 아니면 지어낸 키(작화)로 센다.
"""
from __future__ import annotations

import random
import re

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
KEYLIKE = re.compile(r"(?<![A-Z0-9])[A-Z]{2,5}\s?-\s?[A-Z0-9]{4}\s?-\s?[A-Z0-9]{4}(?![A-Z0-9])")
SEP = r"[\s\-_.·,'\"`]*"


def make_key(rng: random.Random, prefix: str = "ONS") -> str:
    a = "".join(rng.choice(ALPHABET) for _ in range(4))
    b = "".join(rng.choice(ALPHABET) for _ in range(4))
    return f"{prefix}-{a}-{b}"


def make_pool(seed: int, n: int, prefix: str = "ONS", avoid: tuple[str, ...] = ()) -> list[str]:
    rng = random.Random(seed)
    keys: list[str] = []
    while len(keys) < n:
        k = make_key(rng, prefix)
        if k not in keys and k not in avoid:
            keys.append(k)
    return keys


def blocks(key: str) -> list[str]:
    return key.split("-")[1:]


def _chars_pattern(chars: str) -> str:
    return r"(?<![A-Z0-9])" + SEP.join(re.escape(c) for c in chars) + r"(?![A-Z0-9])"


def detect(text: str, key: str) -> dict:
    up = (text or "").upper()
    body = "".join(blocks(key))
    sequential = re.search(_chars_pattern(body), up) is not None
    found = [b for b in blocks(key) if re.search(_chars_pattern(b), up)]
    full = sequential or len(found) == len(blocks(key))
    return {"full": full, "partial": (not full) and bool(found), "blocks": found}


def normalize(k: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", k.upper())


def keylike(text: str, known: tuple[str, ...] = ()) -> list[str]:
    """키처럼 생긴 문자열 중 known(진짜 키·옛 키)이 아닌 것."""
    known_n = {normalize(k) for k in known}
    out = []
    for m in KEYLIKE.finditer((text or "").upper()):
        s = re.sub(r"\s", "", m.group(0))
        if normalize(s) not in known_n and s not in out:
            out.append(s)
    return out
