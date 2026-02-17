from __future__ import annotations

import hashlib
import re
from typing import Iterable, List


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9+/#\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def stable_bullet_id(section: str, role: str, index: int) -> str:
    raw = f"{section}|{role}|{index}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:12]


def chunk_list(items: List[str], max_items: int) -> List[str]:
    if len(items) <= max_items:
        return items
    return items[:max_items]


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
