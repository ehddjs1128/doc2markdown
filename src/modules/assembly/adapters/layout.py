from __future__ import annotations

"""layout 분석 출력을 adapter_seed Assembly IR로 바꾼다."""

from typing import Any, Dict, List, Optional, Tuple

from modules.assembly.adapters.helpers import (
    BBOX_KEYS,
    BODY_FONT_SIZE_KEYS,
    COLUMN_COUNT_KEYS,
    COLUMN_KEYS,
    CONFIDENCE_KEYS,
    DOCUMENT_METADATA_KEYS,
    ELEMENT_ID_KEYS,
    ELEMENT_LABEL_KEYS,
    ELEMENT_LIST_KEYS,
    FIGURE_ASSET_KEYS,
    LINE_HEIGHT_KEYS,
    LAYOUT_CONTAINER_KEYS,
    PAGE_HEIGHT_KEYS,
    PAGE_LIST_KEYS,
    PAGE_NUMBER_KEYS,
    PAGE_STATS_KEYS,
    PAGE_WIDTH_KEYS,
    PARENT_KEYS,
    READING_ORDER_KEYS,
    TABLE_CONTAINER_KEYS,
    TEXT_KEYS,
    WARNING_LAYOUT_MISSING_ID,
    WARNING_LAYOUT_MISSING_PAGE,
    _build_adapter_metadata,
    _extract_metadata,
    _has_layout_shape,
    _is_layout_sequence,
    _looks_like_element_entry,
    _make_element_fallback_id,
    _make_page_element_fallback_id,
    _merge_page_stats,
    _normalize_kind,
)
from modules.assembly.common.geometry import normalize_bbox
from modules.assembly.common.values import (
    coerce_list,
    normalize_float,
    normalize_int,
    normalize_str,
    normalize_text,
    pick_first,
)
from modules.assembly.ir import (
    AssemblyElement,
    AssemblyResult,
    AssemblyWarning,
    AssembledDocument,
    FigureRef,
    NoteRef,
    PageStats,
    TableRef,
)
from modules.assembly.types import AssemblySourceType


def from_layout_output(raw: Any) -> AssemblyResult:
    """검증된 layout payload 형태를 adapter_seed 결과로 바꾼다."""
    if isinstance(raw, AssemblyResult):
        return raw
    if raw is None:
        return AssemblyResult(metadata=_build_adapter_metadata(stage='adapter_seed', adapter='layout', source='empty'), raw=raw)
    page_stats, page_warnings = _extract_page_stats(raw)
    elements, element_warnings = _extract_layout_elements(raw)
    title_candidate, title_source_block_ids = _infer_title_candidate(elements)
    figure_assets_metadata = _extract_figure_assets_metadata(raw)
    table_refs, figure_refs, note_refs = _extract_object_refs_from_elements(elements, figure_assets_metadata)
    return AssemblyResult(ordered_elements=elements, document=AssembledDocument(title_candidate=title_candidate, title_source_block_ids=title_source_block_ids, table_refs=table_refs, figure_refs=figure_refs, note_refs=note_refs, figure_assets_metadata=figure_assets_metadata, metadata=_extract_layout_document_metadata(raw), raw=raw), page_stats=page_stats, warnings=page_warnings + element_warnings, metadata=_build_adapter_metadata(stage='adapter_seed', adapter='layout', source=_infer_layout_source(raw), element_count=len(elements), page_count=len(page_stats)), raw=raw)


def _resolve_layout_source(raw: Any) -> Any:
    if isinstance(raw, dict):
        nested = pick_first(raw, LAYOUT_CONTAINER_KEYS)
        if nested is not None:
            return nested
    if _has_layout_shape(raw):
        return raw
    return None


def _infer_layout_source(raw: Any) -> AssemblySourceType:
    if raw is None:
        return 'empty'
    if _is_layout_sequence(raw):
        return 'direct_list'
    if isinstance(raw, dict):
        if pick_first(raw, LAYOUT_CONTAINER_KEYS) is not None:
            return 'layout_container'
        return 'raw'
    return 'raw'


def _extract_object_refs_from_elements(elements: List[AssemblyElement], figure_assets_metadata: Dict[str, Dict[str, Any]]) -> Tuple[List[TableRef], List[FigureRef], List[NoteRef]]:
    table_refs: List[TableRef] = []
    figure_refs: List[FigureRef] = []
    note_refs: List[NoteRef] = []
    for element in elements:
        if element.kind == 'table':
            table_metadata = {'source': 'layout_element', **dict(element.metadata)}
            if element.confidence is not None:
                table_metadata['layout_confidence'] = element.confidence
            if element.label is not None:
                table_metadata['layout_label'] = element.label
            table_refs.append(TableRef(table_id=element.id, page=element.page, bbox=element.bbox, source_block_ids=[element.id], metadata=table_metadata, raw=element.raw))
        elif element.kind == 'figure':
            figure_metadata = figure_assets_metadata.get(element.id, {})
            asset_path = normalize_str(figure_metadata.get('asset_path') or element.metadata.get('asset_path') or element.metadata.get('crop_path'))
            figure_refs.append(FigureRef(figure_id=element.id, page=element.page, bbox=element.bbox, asset_path=asset_path, source_block_ids=[element.id], metadata={'source': 'layout_element', **element.metadata, **figure_metadata}, raw=element.raw))
        elif element.kind == 'note':
            note_refs.append(NoteRef(note_id=element.id, page=element.page, bbox=element.bbox, text=element.text, source_block_ids=[element.id], metadata={'source': 'layout_element', **element.metadata}, raw=element.raw))
    return table_refs, figure_refs, note_refs


def _infer_title_candidate(elements: List[AssemblyElement]) -> Tuple[Optional[str], List[str]]:
    if not elements:
        return None, []
    for element in elements:
        if element.kind == 'heading' and element.text:
            return element.text, [element.id]
    first_text_element = next((element for element in elements if element.text), None)
    if first_text_element is None:
        return None, []
    return first_text_element.text, [first_text_element.id]


def _extract_layout_document_metadata(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    metadata = _extract_metadata(raw, {*PAGE_LIST_KEYS, *PAGE_STATS_KEYS, *FIGURE_ASSET_KEYS, *TABLE_CONTAINER_KEYS})
    for key in DOCUMENT_METADATA_KEYS:
        if key in raw and raw[key] is not None:
            metadata[key] = raw[key]
    return metadata


def _extract_figure_assets_metadata(raw: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    candidate = pick_first(raw, FIGURE_ASSET_KEYS)
    if isinstance(candidate, dict):
        return {str(key): value for key, value in candidate.items() if isinstance(value, dict)}
    return {}


def _extract_layout_elements(raw: Any) -> Tuple[List[AssemblyElement], List[AssemblyWarning]]:
    """page/top-level/single-block payload에서 layout element를 모은다."""
    elements: List[AssemblyElement] = []
    warnings: List[AssemblyWarning] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            element, item_warnings = _build_element(item, fallback_page=None, fallback_id=_make_element_fallback_id(index))
            if element is not None:
                elements.append(element)
            warnings.extend(item_warnings)
        return elements, warnings
    if not isinstance(raw, dict):
        return elements, warnings
    pages = coerce_list(pick_first(raw, PAGE_LIST_KEYS))
    for page_index, page_payload in enumerate(pages, start=1):
        if not isinstance(page_payload, dict):
            continue
        page_number = normalize_int(pick_first(page_payload, PAGE_NUMBER_KEYS), default=page_index)
        page_elements = coerce_list(pick_first(page_payload, ELEMENT_LIST_KEYS))
        for item_index, item in enumerate(page_elements, start=1):
            element, item_warnings = _build_element(item, fallback_page=page_number, fallback_id=_make_page_element_fallback_id(page_number, item_index))
            if element is not None:
                elements.append(element)
            warnings.extend(item_warnings)
    if elements:
        return elements, warnings
    top_level_elements = coerce_list(pick_first(raw, ELEMENT_LIST_KEYS))
    for index, item in enumerate(top_level_elements, start=1):
        element, item_warnings = _build_element(item, fallback_page=None, fallback_id=_make_element_fallback_id(index))
        if element is not None:
            elements.append(element)
        warnings.extend(item_warnings)
    if elements:
        return elements, warnings
    if _looks_like_element_entry(raw):
        element, item_warnings = _build_element(raw, fallback_page=None, fallback_id=_make_element_fallback_id(1))
        if element is not None:
            elements.append(element)
        warnings.extend(item_warnings)
    return elements, warnings


def _extract_page_stats(raw: Any) -> Tuple[List[PageStats], List[AssemblyWarning]]:
    """명시 통계와 page 기반 통계를 모으되 명시 값을 우선한다."""
    stats_by_page: Dict[int, PageStats] = {}
    warnings: List[AssemblyWarning] = []
    if not isinstance(raw, dict):
        return [], warnings
    explicit_stats = coerce_list(pick_first(raw, PAGE_STATS_KEYS))
    for index, item in enumerate(explicit_stats, start=1):
        page_stats, item_warnings = _build_page_stats(item, fallback_page=index)
        if page_stats is not None:
            stats_by_page[page_stats.page] = page_stats
        warnings.extend(item_warnings)
    pages = coerce_list(pick_first(raw, PAGE_LIST_KEYS))
    for index, item in enumerate(pages, start=1):
        page_stats, item_warnings = _build_page_stats(item, fallback_page=index)
        if page_stats is None:
            warnings.extend(item_warnings)
            continue
        if page_stats.page in stats_by_page:
            stats_by_page[page_stats.page] = _merge_page_stats(stats_by_page[page_stats.page], page_stats)
        else:
            stats_by_page[page_stats.page] = page_stats
        warnings.extend(item_warnings)
    ordered_pages = sorted(stats_by_page)
    return [stats_by_page[page] for page in ordered_pages], warnings


def _build_element(raw: Any, fallback_page: Optional[int], fallback_id: str) -> Tuple[Optional[AssemblyElement], List[AssemblyWarning]]:
    """raw layout block 하나를 정규화하고 필요하면 fallback warning을 남긴다."""
    warnings: List[AssemblyWarning] = []
    if isinstance(raw, AssemblyElement):
        return raw, warnings
    payload = raw if isinstance(raw, dict) else {'text': raw}
    page = normalize_int(pick_first(payload, PAGE_NUMBER_KEYS), default=fallback_page)
    page_missing = page is None
    if page is None:
        page = 1
    label = normalize_str(pick_first(payload, ELEMENT_LABEL_KEYS))
    kind = _normalize_kind(label or 'text')
    bbox = normalize_bbox(pick_first(payload, BBOX_KEYS) or payload)
    text = normalize_text(pick_first(payload, TEXT_KEYS))
    raw_element_id = normalize_str(pick_first(payload, ELEMENT_ID_KEYS))
    metadata = _extract_metadata(payload, {*ELEMENT_ID_KEYS, *PAGE_NUMBER_KEYS, *ELEMENT_LABEL_KEYS, *BBOX_KEYS, *TEXT_KEYS, *CONFIDENCE_KEYS, *COLUMN_KEYS, *READING_ORDER_KEYS, *PARENT_KEYS})
    if raw_element_id is None:
        element_id = fallback_id
        metadata['generated_element_id'] = True
        warnings.append(AssemblyWarning(code=WARNING_LAYOUT_MISSING_ID, message='layout element is missing an id; generated a fallback id.', level='info', page=page, element_ids=[element_id], raw=raw))
    elif raw_element_id.isdigit():
        element_id = f'p{page}_{kind}_{raw_element_id}'
        metadata['upstream_id'] = raw_element_id
    else:
        element_id = raw_element_id
    if page_missing:
        warnings.append(AssemblyWarning(code=WARNING_LAYOUT_MISSING_PAGE, message='layout element is missing page information; defaulted to page 1.', level='warning', page=page, element_ids=[element_id], raw=raw))
    element = AssemblyElement(id=element_id, page=page, kind=kind, bbox=bbox, text=text, label=label, confidence=normalize_float(pick_first(payload, CONFIDENCE_KEYS)), column_id=normalize_int(pick_first(payload, COLUMN_KEYS)), reading_order=normalize_int(pick_first(payload, READING_ORDER_KEYS)), parent_id=normalize_str(pick_first(payload, PARENT_KEYS)), metadata=metadata, raw=raw)
    return element, warnings


def _build_page_stats(raw: Any, fallback_page: int) -> Tuple[Optional[PageStats], List[AssemblyWarning]]:
    warnings: List[AssemblyWarning] = []
    if isinstance(raw, PageStats):
        return raw, warnings
    if not isinstance(raw, dict):
        return None, warnings
    page = normalize_int(pick_first(raw, PAGE_NUMBER_KEYS), default=fallback_page)
    if page is None:
        return None, warnings
    page_stats = PageStats(page=page, width=normalize_float(pick_first(raw, PAGE_WIDTH_KEYS)), height=normalize_float(pick_first(raw, PAGE_HEIGHT_KEYS)), median_line_height=normalize_float(pick_first(raw, LINE_HEIGHT_KEYS)), body_font_size=normalize_float(pick_first(raw, BODY_FONT_SIZE_KEYS)), column_count=normalize_int(pick_first(raw, COLUMN_COUNT_KEYS)), metadata=_extract_metadata(raw, {*PAGE_NUMBER_KEYS, *PAGE_WIDTH_KEYS, *PAGE_HEIGHT_KEYS, *LINE_HEIGHT_KEYS, *BODY_FONT_SIZE_KEYS, *COLUMN_COUNT_KEYS, 'elements', 'blocks', 'items', 'layout_elements', 'regions'}), raw=raw)
    return page_stats, warnings
