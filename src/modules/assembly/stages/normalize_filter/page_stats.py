from __future__ import annotations

"""Normalize/filter 단계의 page 통계 보강."""

from statistics import median
from typing import Dict, List, Optional

from modules.assembly.common.values import normalize_float
from modules.assembly.ir import AssemblyElement, PageStats
from modules.assembly.stages.normalize_filter import policy


def build_page_dimensions(
    page_stats: List[PageStats],
    elements: List[AssemblyElement],
) -> Dict[int, Dict[str, float]]:
    """page 높이/너비가 비어 있어도 bbox 기반 추정치를 보완한다."""
    dimensions: Dict[int, Dict[str, float]] = {}

    for stat in page_stats:
        dimensions[stat.page] = {
            "width": stat.width or 0.0,
            "height": stat.height or 0.0,
        }

    for element in elements:
        if element.bbox is None:
            dimensions.setdefault(element.page, {"width": 0.0, "height": 0.0})
            continue

        x2 = float(element.bbox[2])
        y2 = float(element.bbox[3])
        page_dimension = dimensions.setdefault(
            element.page,
            {"width": 0.0, "height": 0.0},
        )
        page_dimension["width"] = max(page_dimension["width"], x2)
        page_dimension["height"] = max(page_dimension["height"], y2)

    return dimensions


def normalize_page_stats(
    page_stats: List[PageStats],
    elements: List[AssemblyElement],
    page_dimensions: Dict[int, Dict[str, float]],
) -> List[PageStats]:
    """후속 threshold 계산에 필요한 page 통계를 보수적으로 보강한다."""
    stats_by_page = {stat.page: stat for stat in page_stats}
    elements_by_page: Dict[int, List[AssemblyElement]] = {}

    for element in elements:
        elements_by_page.setdefault(element.page, []).append(element)

    normalized_stats: List[PageStats] = []
    page_numbers = sorted(set(stats_by_page) | set(elements_by_page) | set(page_dimensions))

    for page in page_numbers:
        current = stats_by_page.get(page, PageStats(page=page))
        metadata = dict(current.metadata)
        dimension = page_dimensions.get(page, {})
        page_elements = elements_by_page.get(page, [])

        width = current.width if current.width is not None else normalize_float(dimension.get("width"))
        height = current.height if current.height is not None else normalize_float(dimension.get("height"))

        median_line_height = current.median_line_height
        if median_line_height is None:
            inferred_line_height = infer_median_height(page_elements, policy.LINE_HEIGHT_KINDS)
            median_line_height = inferred_line_height
            if inferred_line_height is not None:
                metadata["inferred_median_line_height"] = True

        body_font_size = current.body_font_size
        if body_font_size is None:
            inferred_body_font = infer_median_height(page_elements, policy.BODY_TEXT_KINDS)
            if inferred_body_font is None:
                inferred_body_font = median_line_height
            elif median_line_height is not None and inferred_body_font > median_line_height * 1.25:
                inferred_body_font = median_line_height
            body_font_size = inferred_body_font
            if inferred_body_font is not None:
                metadata["inferred_body_font_size"] = True

        metadata["active_element_count"] = len(page_elements)

        normalized_stats.append(
            PageStats(
                page=page,
                width=width,
                height=height,
                median_line_height=median_line_height,
                body_font_size=body_font_size,
                column_count=current.column_count,
                metadata=metadata,
                raw=current.raw,
            )
        )

    return normalized_stats


def infer_median_height(
    elements: List[AssemblyElement],
    allowed_kinds: frozenset[str],
) -> Optional[float]:
    """짧은 블록 높이 대역만 사용해 line/body 기준값을 보수적으로 추정한다."""
    heights = sorted(
        [
            float(element.bbox[3] - element.bbox[1])
            for element in elements
            if element.kind in allowed_kinds and element.bbox is not None and element.text
        ]
    )
    if not heights:
        return None

    base_height = heights[0]
    clustered_heights = [height for height in heights if height <= base_height * 1.5]
    if not clustered_heights:
        clustered_heights = [base_height]

    return float(median(clustered_heights))


def infer_title_candidate(
    elements: List[AssemblyElement],
) -> tuple[Optional[str], List[str]]:
    """필터링 이후의 유효 element 기준으로 제목 후보를 다시 잡는다."""
    if not elements:
        return None, []

    for element in elements:
        if element.kind == "heading" and element.text:
            return element.text, [element.id]

    first_text_element = next((element for element in elements if element.text), None)
    if first_text_element is None:
        return None, []

    return first_text_element.text, [first_text_element.id]
