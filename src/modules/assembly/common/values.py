from __future__ import annotations

"""Assembly 전체에서 쓰는 값 변환과 id helper."""

import re
from typing import Any, Dict, List, Optional, Tuple


REF_ID_KEYS: Tuple[str, ...] = ("id", "note_id", "caption_id", "uuid")


def pick_first(payload: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub(r"\s+", " ", text)


def normalize_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_ref_id(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return normalize_str(pick_first(value, REF_ID_KEYS))
    return normalize_str(value)


def normalize_id_list(value: Any) -> List[str]:
    normalized: List[str] = []
    for item in coerce_list(value):
        candidate = normalize_ref_id(item)
        if candidate is not None:
            normalized.append(candidate)
    return normalized


def merge_unique_ids(*values: Any) -> List[str]:
    merged: Dict[str, None] = {}
    for value in values:
        for item in coerce_list(value):
            candidate = normalize_ref_id(item)
            if candidate is not None:
                merged[candidate] = None
    return list(merged.keys())
