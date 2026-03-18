from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


WHITESPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")


def normalize_text(value: str) -> str:
    lowered = value.lower()
    lowered = lowered.replace("&", " and ")
    lowered = WHITESPACE_RE.sub(" ", lowered).strip()
    lowered = NON_ALNUM_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", lowered).strip()


def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    normalized = normalize_text(value)
    return normalized.replace(" ", "-")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
