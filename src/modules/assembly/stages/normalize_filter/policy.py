from __future__ import annotations

"""Normalize/filter 단계의 판정 정책."""

import re
from typing import Optional


TOP_ZONE_RATIO = 0.10
BOTTOM_ZONE_RATIO = 0.10
LOW_CONF_THRESHOLD = 0.50
LOW_CONF_SHORT_TEXT_MAX = 3
REPEATED_MARGIN_MIN_PAGES = 2
REPEATED_MARGIN_PAGE_RATIO = 0.30

TEXT_REQUIRED_KINDS = frozenset(
    {
        "text",
        "heading",
        "list_item",
        "caption",
        "note",
        "quote",
        "code_block",
        "header",
        "footer",
        "page_number",
    }
)
OBJECT_LIKE_KINDS = frozenset({"table", "figure", "formula"})
LINE_HEIGHT_KINDS = frozenset({"text", "heading", "list_item", "caption", "note", "quote"})
BODY_TEXT_KINDS = frozenset({"text", "list_item", "caption", "note", "quote"})

PAGE_NUMBER_PATTERN = re.compile(
    r"^(?:페이지|page)\s*\d+(?:\s*/\s*\d+)?$",
    re.IGNORECASE,
)
NON_CONTENT_PATTERN = re.compile(r"^[\W_]+$", re.UNICODE)


def looks_like_page_number(text: str) -> bool:
    """페이지 번호 전용 텍스트를 느슨하게 감지한다."""
    compact = text.strip()
    if PAGE_NUMBER_PATTERN.fullmatch(compact):
        return True

    lowered = compact.lower()
    return bool(
        re.fullmatch(r"(?:페이지|page)\s+\d+\s*/\s*\d+", lowered)
        or re.fullmatch(r"\d+\s*/\s*\d+", lowered)
    )


def should_filter_low_confidence_noise(
    kind: str,
    text: Optional[str],
    confidence: Optional[float],
) -> bool:
    """짧고 신뢰도 낮은 조각만 보수적으로 noise로 제거한다."""
    if confidence is None or confidence >= LOW_CONF_THRESHOLD:
        return False

    if kind in OBJECT_LIKE_KINDS:
        return False

    compact_text = re.sub(r"\s+", "", text or "")
    if not compact_text:
        return True

    if len(compact_text) <= LOW_CONF_SHORT_TEXT_MAX:
        return True

    return bool(NON_CONTENT_PATTERN.fullmatch(compact_text))

