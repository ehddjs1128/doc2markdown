from __future__ import annotations

"""Header/footer/page number 후보를 margin 단서로 판정한다."""

import re
from math import ceil
from typing import Any, Dict, List, Optional

from modules.assembly.common.values import normalize_text
from modules.assembly.ir import AssemblyElement
from modules.assembly.stages.normalize_filter import policy


def detect_explicit_margin_role(
    element: AssemblyElement,
    text: Optional[str],
    page_dimensions: Dict[int, Dict[str, float]],
) -> Optional[str]:
    """upstream label과 page number 패턴을 우선 적용한다."""
    if element.kind in {"header", "footer", "page_number"}:
        return element.kind

    if text is None or element.bbox is None:
        return None

    if policy.looks_like_page_number(text) and is_bottom_zone(
        element.page,
        element.bbox[3],
        page_dimensions,
    ):
        return "page_number"

    return None


def detect_repeated_margin_roles(
    elements: List[AssemblyElement],
    page_dimensions: Dict[int, Dict[str, float]],
) -> Dict[str, str]:
    """여러 페이지에서 반복되는 상하단 텍스트를 header/footer로 태깅한다."""
    total_pages = max(
        len(page_dimensions),
        len({element.page for element in elements}),
    )
    if total_pages <= 1:
        return {}

    min_pages = max(
        policy.REPEATED_MARGIN_MIN_PAGES,
        ceil(total_pages * policy.REPEATED_MARGIN_PAGE_RATIO),
    )

    candidates: List[Dict[str, Any]] = []
    zone_pages: Dict[str, Dict[str, set[int]]] = {"top": {}, "bottom": {}}

    for element in elements:
        if element.kind in policy.OBJECT_LIKE_KINDS or element.bbox is None:
            continue

        text = normalize_text(element.text)
        if text is None:
            continue

        zone = detect_margin_zone(
            page=element.page,
            y1=element.bbox[1],
            y2=element.bbox[3],
            page_dimensions=page_dimensions,
        )
        if zone is None:
            continue

        fingerprint = fingerprint_margin_text(text)
        if fingerprint is None:
            continue

        zone_pages[zone].setdefault(fingerprint, set()).add(element.page)
        candidates.append(
            {
                "id": element.id,
                "zone": zone,
                "text": text,
                "fingerprint": fingerprint,
            }
        )

    detected_roles: Dict[str, str] = {}
    for candidate in candidates:
        pages = zone_pages[candidate["zone"]][candidate["fingerprint"]]
        if len(pages) < min_pages:
            continue

        if candidate["zone"] == "top":
            detected_roles[candidate["id"]] = "header"
            continue

        if policy.looks_like_page_number(candidate["text"]):
            detected_roles[candidate["id"]] = "page_number"
        else:
            detected_roles[candidate["id"]] = "footer"

    return detected_roles


def detect_margin_zone(
    page: int,
    y1: float,
    y2: float,
    page_dimensions: Dict[int, Dict[str, float]],
) -> Optional[str]:
    """상단/하단 margin 영역 후보인지 판정한다."""
    page_height = page_dimensions.get(page, {}).get("height")
    if page_height is None or page_height <= 0:
        return None

    if y1 <= page_height * policy.TOP_ZONE_RATIO:
        return "top"
    if y2 >= page_height * (1 - policy.BOTTOM_ZONE_RATIO):
        return "bottom"
    return None


def fingerprint_margin_text(text: str) -> Optional[str]:
    """페이지 번호 차이만 무시하고 반복 텍스트를 비교한다."""
    normalized = normalize_text(text)
    if normalized is None:
        return None

    lowered = normalized.lower()
    lowered = re.sub(r"\d+", "#", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered or None


def is_bottom_zone(
    page: int,
    y2: float,
    page_dimensions: Dict[int, Dict[str, float]],
) -> bool:
    """footer 판정용 하단 영역 여부를 계산한다."""
    page_height = page_dimensions.get(page, {}).get("height")
    if page_height is None or page_height <= 0:
        return False
    return y2 >= page_height * (1 - policy.BOTTOM_ZONE_RATIO)
