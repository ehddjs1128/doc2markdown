from __future__ import annotations

"""Shared adapter helpers for converting external layout/table output into assembly IR."""

import re
from typing import Any, Dict, List, Optional, Tuple

from modules.assembly.ir import AssemblyElement, AssemblyMeta, PageStats, TableRef
from modules.assembly.types import (
    AssemblyAdapterType,
    AssemblyElementKind,
    AssemblySourceType,
    AssemblyStage,
    AssemblyWarningCode,
    BBox,
)

REF_ID_KEYS: Tuple[str, ...] = ('id', 'note_id', 'caption_id', 'uuid')


KIND_ALIASES: Dict[str, AssemblyElementKind] = {'text': 'text', 'paragraph': 'text', 'body': 'text', 'heading': 'heading', 'title': 'heading', 'section_header': 'heading', 'list_item': 'list_item', 'list': 'list_item', 'bullet': 'list_item', 'table': 'table', 'figure': 'figure', 'picture': 'figure', 'image': 'figure', 'caption': 'caption', 'note': 'note', 'footnote': 'note', 'formula': 'formula', 'equation': 'formula', 'quote': 'quote', 'blockquote': 'quote', 'code': 'code_block', 'code_block': 'code_block', 'header': 'header', 'page_header': 'header', 'footer': 'footer', 'page_footer': 'footer', 'page_number': 'page_number', 'noise': 'noise', 'artifact': 'noise'}


def _pick_first(payload: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub('\\s+', ' ', text)


def _normalize_kind(value: str) -> AssemblyElementKind:
    normalized = value.strip().lower().replace('-', '_').replace(' ', '_')
    return KIND_ALIASES.get(normalized, 'text')


def _normalize_bbox(value: Any) -> Optional[BBox]:
    if value is None:
        return None
    if isinstance(value, dict):
        if {'x1', 'y1', 'x2', 'y2'}.issubset(value.keys()):
            coords = [value['x1'], value['y1'], value['x2'], value['y2']]
        elif {'left', 'top', 'right', 'bottom'}.issubset(value.keys()):
            coords = [value['left'], value['top'], value['right'], value['bottom']]
        elif {'x', 'y', 'width', 'height'}.issubset(value.keys()):
            x = _normalize_float(value['x'])
            y = _normalize_float(value['y'])
            width = _normalize_float(value['width'])
            height = _normalize_float(value['height'])
            if None in (x, y, width, height):
                return None
            coords = [x, y, x + width, y + height]
        else:
            return None
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        coords = list(value)
    else:
        return None
    normalized = [_normalize_float(item) for item in coords]
    if any(item is None for item in normalized):
        return None
    return normalized[0], normalized[1], normalized[2], normalized[3]


def _normalize_float(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_int(value: Any, default: Optional[int]=None) -> Optional[int]:
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_id_list(value: Any) -> List[str]:
    items = _coerce_list(value)
    normalized: List[str] = []
    for item in items:
        candidate = _normalize_ref_id(item)
        if candidate is not None:
            normalized.append(candidate)
    return normalized


def _normalize_ref_id(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return _normalize_str(_pick_first(value, REF_ID_KEYS))
    return _normalize_str(value)


def _looks_like_markdown_table(value: Any) -> bool:
    text = _normalize_str(value)
    if text is None:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    header_line = lines[0]
    divider_line = lines[1]
    if '|' not in header_line or '|' not in divider_line:
        return False
    divider_chars = divider_line.replace('|', '').replace(':', '').replace('-', '').replace(' ', '')
    return divider_chars == ''


def _normalize_markdown_table(value: Any) -> Optional[str]:
    text = _normalize_str(value)
    if text is None or not _looks_like_markdown_table(text):
        return None
    return text


def _extract_metadata(payload: Dict[str, Any], known_keys: set[str]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in known_keys and value is not None}


def _merge_unique_ids(*values: Any) -> List[str]:
    merged: Dict[str, None] = {}
    for value in values:
        for item in _coerce_list(value):
            candidate = _normalize_ref_id(item)
            if candidate is not None:
                merged[candidate] = None
    return list(merged.keys())


def _bbox_iou(left: Optional[BBox], right: Optional[BBox]) -> Optional[float]:
    if left is None or right is None:
        return None
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    inter_x1 = max(left_x1, right_x1)
    inter_y1 = max(left_y1, right_y1)
    inter_x2 = min(left_x2, right_x2)
    inter_y2 = min(left_y2, right_y2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    left_area = max(0.0, (left_x2 - left_x1) * (left_y2 - left_y1))
    right_area = max(0.0, (right_x2 - right_x1) * (right_y2 - right_y1))
    union = left_area + right_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


LAYOUT_CONTAINER_KEYS: Tuple[str, ...] = ('layout_output', 'layout_result', 'layout', 'vision_output', 'vision_result', 'ordered_layout')


TABLE_CONTAINER_KEYS: Tuple[str, ...] = ('table_output', 'table_result', 'table_results', 'tables_output', 'tables_result')


ELEMENT_LIST_KEYS: Tuple[str, ...] = ('ordered_elements', 'elements', 'blocks', 'items', 'layout_elements', 'regions')


PAGE_LIST_KEYS: Tuple[str, ...] = ('pages', 'page_results', 'document_pages')


PAGE_STATS_KEYS: Tuple[str, ...] = ('page_stats', 'page_statistics', 'statistics')


PAGE_NUMBER_KEYS: Tuple[str, ...] = ('page', 'page_num', 'page_number')


TABLE_LIST_KEYS: Tuple[str, ...] = ('table_refs', 'tables', 'results', 'table_results', 'table_ir', 'items')


ELEMENT_ID_KEYS: Tuple[str, ...] = ('id', 'element_id', 'block_id', 'uuid')


TABLE_ID_KEYS: Tuple[str, ...] = ('table_id', 'id', 'uuid', 'table_key')


ELEMENT_LABEL_KEYS: Tuple[str, ...] = ('label', 'type', 'kind', 'class', 'category', 'role')


BBOX_KEYS: Tuple[str, ...] = ('bbox', 'box', 'bounds', 'rect')


TEXT_KEYS: Tuple[str, ...] = ('text', 'content', 'ocr_text', 'raw_text', 'value')


CONFIDENCE_KEYS: Tuple[str, ...] = ('confidence', 'score', 'probability')


COLUMN_KEYS: Tuple[str, ...] = ('column_id', 'column')


READING_ORDER_KEYS: Tuple[str, ...] = ('reading_order', 'order', 'index')


PARENT_KEYS: Tuple[str, ...] = ('parent_id', 'parent', 'section_id')


SOURCE_BLOCK_IDS_KEYS: Tuple[str, ...] = ('source_block_ids', 'block_ids', 'source_blocks')


PAGE_WIDTH_KEYS: Tuple[str, ...] = ('width', 'page_width')


PAGE_HEIGHT_KEYS: Tuple[str, ...] = ('height', 'page_height')


LINE_HEIGHT_KEYS: Tuple[str, ...] = ('median_line_height', 'line_height', 'avg_line_height')


BODY_FONT_SIZE_KEYS: Tuple[str, ...] = ('body_font_size', 'font_size', 'avg_font_size')


COLUMN_COUNT_KEYS: Tuple[str, ...] = ('column_count', 'columns', 'num_columns')


CAPTION_KEYS: Tuple[str, ...] = ('caption_id', 'caption', 'caption_ref')


NOTE_KEYS: Tuple[str, ...] = ('note_ids', 'notes', 'note_refs')


TABLE_STRUCTURE_KEYS: Tuple[str, ...] = ('cells', 'rows', 'columns')


TABLE_MARKDOWN_KEYS: Tuple[str, ...] = ('markdown', 'table_markdown', 'md', 'table_md')


TABLE_IMAGE_KEYS: Tuple[str, ...] = ('crop_path', 'image_path', 'table_image_path')


FIGURE_ASSET_KEYS: Tuple[str, ...] = ('figure_assets_metadata', 'figure_assets', 'figure_asset_map')


DOCUMENT_METADATA_KEYS: Tuple[str, ...] = ('file_name', 'file_type', 'total_pages')


ELEMENT_FALLBACK_PREFIX: str = 'element'


TABLE_FALLBACK_PREFIX: str = 'table'


WARNING_LAYOUT_MISSING_ID: AssemblyWarningCode = 'layout_missing_id'


WARNING_LAYOUT_MISSING_PAGE: AssemblyWarningCode = 'layout_missing_page'


WARNING_TABLE_MISSING_ID: AssemblyWarningCode = 'table_missing_id'


WARNING_TABLE_MISSING_PAGE: AssemblyWarningCode = 'table_missing_page'


def _build_adapter_metadata(stage: AssemblyStage, adapter: AssemblyAdapterType, source: AssemblySourceType, **extra: Any) -> AssemblyMeta:
    return AssemblyMeta(stage=stage, adapter=adapter, source=source, details=extra)


def _merge_ref_list(primary: List[Any], secondary: List[Any], id_attr: str) -> List[Any]:
    merged: Dict[str, Any] = {}
    for item in list(primary) + list(secondary):
        ref_id = getattr(item, id_attr, None)
        if ref_id is None:
            continue
        merged[str(ref_id)] = item
    return list(merged.values())


def _merge_page_stats(current: PageStats, incoming: PageStats) -> PageStats:
    return PageStats(page=current.page, width=current.width if current.width is not None else incoming.width, height=current.height if current.height is not None else incoming.height, median_line_height=current.median_line_height if current.median_line_height is not None else incoming.median_line_height, body_font_size=current.body_font_size if current.body_font_size is not None else incoming.body_font_size, column_count=current.column_count if current.column_count is not None else incoming.column_count, metadata={**incoming.metadata, **current.metadata}, raw=current.raw if current.raw is not None else incoming.raw)


def _make_element_fallback_id(index: int) -> str:
    return f'{ELEMENT_FALLBACK_PREFIX}_{index}'


def _make_page_element_fallback_id(page: int, index: int) -> str:
    return f'p{page}_e{index}'


def _make_table_fallback_id(index: int) -> str:
    return f'{TABLE_FALLBACK_PREFIX}_{index}'


def _extract_source_block_ids(payload: Dict[str, Any]) -> List[str]:
    value = _pick_first(payload, SOURCE_BLOCK_IDS_KEYS)
    return _normalize_id_list(value)


def _has_layout_shape(raw: Any) -> bool:
    if isinstance(raw, dict):
        return _pick_first(raw, PAGE_LIST_KEYS) is not None or _pick_first(raw, ELEMENT_LIST_KEYS) is not None or _looks_like_element_entry(raw)
    return _is_layout_sequence(raw)


def _has_table_shape(raw: Any) -> bool:
    if _looks_like_markdown_table(raw):
        return True
    if isinstance(raw, dict):
        return _pick_first(raw, TABLE_LIST_KEYS) is not None or _pick_first(raw, TABLE_MARKDOWN_KEYS) is not None or _looks_like_table_entry(raw)
    return _is_table_sequence(raw)


def _is_layout_sequence(raw: Any) -> bool:
    if not isinstance(raw, (list, tuple)) or not raw:
        return False
    return any(_looks_like_element_entry(item) for item in raw)


def _is_table_sequence(raw: Any) -> bool:
    if not isinstance(raw, (list, tuple)) or not raw:
        return False
    return any(_looks_like_table_entry(item) or _looks_like_markdown_table(item) for item in raw)


def _looks_like_element_entry(raw: Any) -> bool:
    if isinstance(raw, AssemblyElement):
        return True
    if not isinstance(raw, dict):
        return False
    return any(key in raw for key in (*TEXT_KEYS, *BBOX_KEYS, *ELEMENT_LABEL_KEYS))


def _looks_like_table_entry(raw: Any) -> bool:
    if isinstance(raw, TableRef):
        return True
    if _looks_like_markdown_table(raw):
        return True
    if not isinstance(raw, dict):
        return False
    markdown_candidate = _pick_first(raw, TABLE_MARKDOWN_KEYS)
    if _looks_like_markdown_table(markdown_candidate):
        return True
    return any(key in raw for key in (*TABLE_ID_KEYS, *CAPTION_KEYS, *NOTE_KEYS, *TABLE_STRUCTURE_KEYS))
