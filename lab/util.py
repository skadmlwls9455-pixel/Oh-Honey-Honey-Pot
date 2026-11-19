from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def rel(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_yaml(path: str | Path):
    return yaml.safe_load(rel(path).read_text(encoding="utf-8"))


def load_json(path: str | Path):
    return json.loads(rel(path).read_text(encoding="utf-8"))


def dump_json(obj, path: str | Path) -> None:
    p = rel(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(path: str | Path) -> str:
    return rel(path).read_text(encoding="utf-8")


def short_hash(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:10]


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "x"


def fill(template: str, values: dict) -> str:
    """{{KEY}} 자리를 values로 채운다. 없는 키는 그대로 둔다."""
    def sub(m):
        key = m.group(1)
        return str(values[key]) if key in values else m.group(0)
    return re.sub(r"\{\{([A-Z_]+)\}\}", sub, template)
