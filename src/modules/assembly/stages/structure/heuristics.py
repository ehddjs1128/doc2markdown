from __future__ import annotations

"""Structure 단계의 geometry/text heuristic."""

import re
from typing import Any, Optional, Tuple

from modules.assembly.common.values import normalize_text
from modules.assembly.ir import AssemblyElement, PageStats, SectionNode


PARA_MERGE_RATIO = 0.80
NEW_PARA_RATIO = 1.50
HEADING_FONT_RATIO = 1.20
CAPTION_DIST_RATIO = 1.00
NOTE_DIST_RATIO = 2.50

DEFAULT_LINE_HEIGHT = 12.0
DEFAULT_BODY_FONT_SIZE = 12.0
MIN_INDENT_TOLERANCE = 18.0

PARAGRAPH_LIKE_KINDS = frozenset({"text", "quote", "code_block", "formula", "caption"})
TERMINAL_PUNCTUATION = tuple(".!?;:)]}\"'”’")

ORDERED_LIST_PATTERN = re.compile(
    r"^\s*(?:\d+[.)]|[A-Za-z][.)]|[가-힣][.)]|\(\d+\)|\([A-Za-z]\)|\([가-힣]\))\s+"
)
UNORDERED_LIST_PATTERN = re.compile(r"^\s*(?:[-*•◦▪‣·])\s+")
NUMERIC_HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+")
PAREN_HEADING_PATTERN = re.compile(r"^\s*\((\d+|[A-Za-z]|[가-힣])\)\s+")
KOREAN_HEADING_PATTERN = re.compile(r"^\s*([가-힣]|[A-Za-z])[.)]\s+")
TABLE_CAPTION_PATTERN = re.compile(r"^\s*(?:table|tbl\.?|표)\s*\d*", re.IGNORECASE)
FIGURE_CAPTION_PATTERN = re.compile(r"^\s*(?:figure|fig\.?|그림)\s*\d*", re.IGNORECASE)
NOTE_PATTERN = re.compile(r"^\s*(?:note\b|note:|주\)|주:|※|단위:|source:)", re.IGNORECASE)


def infer_heading(element: AssemblyElement, page_stat: Optional[PageStats]) -> tuple[int, str]:
    """문자 패턴과 block 높이를 같이 보고 heading level과 근거를 추정한다."""
    llm_heading_level = normalize_heading_level_hint(element.metadata.get("llm_heading_level"))
    if llm_heading_level is not None:
        return llm_heading_level, "llm_hint"

    text = normalize_text(element.text) or ""

    numeric_match = NUMERIC_HEADING_PATTERN.match(text)
    if numeric_match:
        return max(1, numeric_match.group(1).count(".") + 1), "numeric_pattern"

    if PAREN_HEADING_PATTERN.match(text):
        return 2, "paren_pattern"

    if KOREAN_HEADING_PATTERN.match(text):
        return 2, "korean_pattern"

    body_font_size = page_stat.body_font_size if page_stat else None
    heading_height = bbox_height(element)
    if heading_height is not None:
        baseline = body_font_size or DEFAULT_BODY_FONT_SIZE
        if heading_height >= baseline * 1.8:
            return 1, "height_ratio"
        if heading_height >= baseline * HEADING_FONT_RATIO:
            return 2, "height_ratio"

    return 3, "default"


def normalize_heading_level_hint(value: Any) -> Optional[int]:
    """LLM heading level hint의 Markdown 안전 범위 정규화."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(6, normalized))


def effective_section_level(section: SectionNode) -> int:
    """level이 비어 있어도 stack 계산이 가능하게 만든다."""
    return section.level if section.level is not None else 99


def shares_column_flow(
    previous: AssemblyElement,
    current: AssemblyElement,
    page_stat: Optional[PageStats],
) -> bool:
    """column_id가 없더라도 bbox 단서로 같은 흐름인지 판단한다."""
    if previous.column_id is not None and current.column_id is not None:
        return previous.column_id == current.column_id

    if previous.bbox is None or current.bbox is None:
        return previous.column_id == current.column_id

    indent_tolerance = max(MIN_INDENT_TOLERANCE, line_height(page_stat))
    if abs(previous.bbox[0] - current.bbox[0]) <= indent_tolerance:
        return True

    return horizontal_overlap_ratio(previous.bbox, current.bbox) >= 0.5


def should_merge_paragraph(
    previous: AssemblyElement,
    current: AssemblyElement,
    page_stat: Optional[PageStats],
) -> bool:
    """같은 문단으로 묶을 수 있는지 보수적으로 판단한다."""
    if previous.kind not in PARAGRAPH_LIKE_KINDS or current.kind not in PARAGRAPH_LIKE_KINDS:
        return False
    if previous.page != current.page:
        return False
    if not shares_column_flow(previous, current, page_stat):
        return False
    if previous.bbox is None or current.bbox is None:
        return False
    if current.kind == "caption":
        return False

    current_line_height = line_height(page_stat)
    gap = current.bbox[1] - previous.bbox[3]
    if gap > max(current_line_height * PARA_MERGE_RATIO, 0.0):
        return False

    indent_tolerance = max(MIN_INDENT_TOLERANCE, current_line_height)
    if abs(previous.bbox[0] - current.bbox[0]) > indent_tolerance:
        return False

    previous_text = normalize_text(previous.text) or ""
    if previous_text.endswith(TERMINAL_PUNCTUATION):
        return False

    if current.text and is_list_like_text(current.text):
        return False

    return True


def should_continue_list(
    previous: AssemblyElement,
    current: AssemblyElement,
    page_stat: Optional[PageStats],
) -> bool:
    """연속 list_item을 같은 list_group으로 묶을 수 있는지 본다."""
    if previous.page != current.page:
        return False
    if not shares_column_flow(previous, current, page_stat):
        return False
    if previous.bbox is None or current.bbox is None:
        return False

    current_line_height = line_height(page_stat)
    gap = current.bbox[1] - previous.bbox[3]
    if gap > max(current_line_height * NEW_PARA_RATIO, MIN_INDENT_TOLERANCE):
        return False

    previous_ordered = is_ordered_list_item(previous.text)
    current_ordered = is_ordered_list_item(current.text)
    return previous_ordered == current_ordered


def caption_threshold(page_stat: Optional[PageStats]) -> float:
    """caption 연결에 사용할 최대 거리다."""
    return max(24.0, line_height(page_stat) * CAPTION_DIST_RATIO * 1.5)


def note_threshold(page_stat: Optional[PageStats]) -> float:
    """note 연결에 사용할 최대 거리다."""
    return max(32.0, line_height(page_stat) * NOTE_DIST_RATIO)


def line_height(page_stat: Optional[PageStats]) -> float:
    """없을 때도 안전하게 line height를 돌려준다."""
    if page_stat is None or page_stat.median_line_height is None:
        return DEFAULT_LINE_HEIGHT
    return max(1.0, float(page_stat.median_line_height))


def looks_like_caption_text(text: Optional[str], object_kind: str) -> bool:
    """caption 패턴을 object 종류별로 느슨하게 확인한다."""
    normalized = normalize_text(text)
    if normalized is None:
        return False

    if object_kind == "table":
        return bool(TABLE_CAPTION_PATTERN.match(normalized))
    return bool(FIGURE_CAPTION_PATTERN.match(normalized))


def looks_like_note_text(text: Optional[str]) -> bool:
    """note 패턴을 보수적으로 확인한다."""
    normalized = normalize_text(text)
    if normalized is None:
        return False
    return bool(NOTE_PATTERN.match(normalized))


def caption_distance(
    candidate_bbox: Tuple[float, float, float, float],
    object_bbox: Tuple[float, float, float, float],
) -> tuple[int, float]:
    """아래쪽 caption을 우선하고, 같으면 가까운 쪽을 선택한다."""
    if candidate_bbox[1] >= object_bbox[3]:
        return 0, candidate_bbox[1] - object_bbox[3]
    return 1, max(0.0, object_bbox[1] - candidate_bbox[3])


def horizontal_overlap_ratio(
    left_bbox: Tuple[float, float, float, float],
    right_bbox: Tuple[float, float, float, float],
) -> float:
    """두 bbox의 가로 겹침 비율을 구한다."""
    left_width = max(0.0, left_bbox[2] - left_bbox[0])
    right_width = max(0.0, right_bbox[2] - right_bbox[0])
    if left_width <= 0 or right_width <= 0:
        return 0.0
    overlap = max(0.0, min(left_bbox[2], right_bbox[2]) - max(left_bbox[0], right_bbox[0]))
    return overlap / min(left_width, right_width)


def bbox_left(element: AssemblyElement) -> float:
    """bbox가 없으면 0을 돌려준다."""
    if element.bbox is None:
        return 0.0
    return float(element.bbox[0])


def bbox_top(element: AssemblyElement) -> float:
    """bbox가 없으면 0을 돌려준다."""
    if element.bbox is None:
        return 0.0
    return float(element.bbox[1])


def bbox_height(element: AssemblyElement) -> Optional[float]:
    """bbox 높이를 반환한다."""
    if element.bbox is None:
        return None
    return max(0.0, float(element.bbox[3] - element.bbox[1]))


def is_ordered_list_item(text: Optional[str]) -> bool:
    """ordered list marker를 간단히 판별한다."""
    normalized = normalize_text(text)
    if normalized is None:
        return False
    return bool(ORDERED_LIST_PATTERN.match(normalized))


def split_list_marker(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """list marker와 실제 item 본문을 분리한다."""
    normalized = normalize_text(text)
    if normalized is None:
        return None, None

    ordered_match = ORDERED_LIST_PATTERN.match(normalized)
    if ordered_match:
        marker = ordered_match.group(0).strip()
        stripped_text = normalized[ordered_match.end():].strip()
        return marker, stripped_text or normalized

    unordered_match = UNORDERED_LIST_PATTERN.match(normalized)
    if unordered_match:
        marker = unordered_match.group(0).strip()
        stripped_text = normalized[unordered_match.end():].strip()
        return marker, stripped_text or normalized

    return None, normalized


def is_list_like_text(text: str) -> bool:
    """문단 병합 중 list 시작 후보를 잘못 합치지 않게 막는다."""
    return bool(ORDERED_LIST_PATTERN.match(text) or UNORDERED_LIST_PATTERN.match(text))
