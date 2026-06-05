from __future__ import annotations

"""Assembly 입력 경계의 공개 adapter 진입점을 제공한다."""

from typing import Any

from modules.assembly.adapter_helpers import (
    _bbox_iou,
    _build_adapter_metadata,
    _merge_ref_list,
    _merge_unique_ids,
    _normalize_str,
)
from modules.assembly.ir import AssemblyResult, AssembledDocument, TableRef
from modules.assembly.layout_adapter import _resolve_layout_source, from_layout_output
from modules.assembly.table_adapter import _resolve_table_source, from_table_output
from modules.assembly.types import (
    FIGURE_REF_ID_ATTR,
    MERGED_METADATA_LAYOUT_KEY,
    MERGED_METADATA_TABLE_KEY,
    NOTE_REF_ID_ATTR,
    TABLE_REF_ID_ATTR,
)


def from_raw(raw: Any) -> AssemblyResult:
    """공개 raw payload를 병합된 adapter_seed 결과로 바꾼다."""
    if isinstance(raw, AssemblyResult):
        return raw
    if isinstance(raw, AssembledDocument):
        return AssemblyResult(document=raw, raw=raw)

    layout_source = _resolve_layout_source(raw)
    table_source = _resolve_table_source(raw)
    if layout_source is None and table_source is None and raw is not None:
        layout_source = raw

    layout_result = from_layout_output(layout_source)
    table_result = from_table_output(table_source)
    return _merge_results(layout_result, table_result, raw)


def from_outputs(layout_output: Any, table_output: Any = None) -> AssemblyResult:
    """명시적인 layout/table 출력으로 adapter_seed 결과를 만든다."""
    return from_raw(
        {
            "layout_output": layout_output,
            "table_output": table_output,
        }
    )


def _merge_results(
    layout_result: AssemblyResult,
    table_result: AssemblyResult,
    raw: Any,
) -> AssemblyResult:
    """구조를 재판단하지 않고 layout block과 table 추출 결과를 병합한다."""
    linked_table_refs = _link_table_refs(
        layout_result.document.table_refs,
        table_result.document.table_refs,
    )
    merged_document = AssembledDocument(
        title_candidate=layout_result.document.title_candidate
        or table_result.document.title_candidate,
        title_source_block_ids=(
            list(layout_result.document.title_source_block_ids)
            or list(table_result.document.title_source_block_ids)
        ),
        children=list(layout_result.document.children),
        sections=list(layout_result.document.sections),
        table_refs=_merge_ref_list(
            layout_result.document.table_refs,
            linked_table_refs,
            id_attr=TABLE_REF_ID_ATTR,
        ),
        figure_refs=_merge_ref_list(
            layout_result.document.figure_refs,
            table_result.document.figure_refs,
            id_attr=FIGURE_REF_ID_ATTR,
        ),
        note_refs=_merge_ref_list(
            layout_result.document.note_refs,
            table_result.document.note_refs,
            id_attr=NOTE_REF_ID_ATTR,
        ),
        figure_assets_metadata={
            **dict(layout_result.document.figure_assets_metadata),
            **dict(table_result.document.figure_assets_metadata),
        },
        metadata={
            **dict(layout_result.document.metadata),
            **dict(table_result.document.metadata),
            MERGED_METADATA_LAYOUT_KEY: dict(layout_result.document.metadata),
            MERGED_METADATA_TABLE_KEY: dict(table_result.document.metadata),
        },
        raw=raw,
    )

    return AssemblyResult(
        ordered_elements=list(layout_result.ordered_elements),
        block_relations=list(layout_result.block_relations)
        + list(table_result.block_relations),
        document=merged_document,
        page_stats=list(layout_result.page_stats),
        warnings=list(layout_result.warnings) + list(table_result.warnings),
        metadata=_build_adapter_metadata(
            stage="adapter_seed",
            adapter="merged",
            source="raw",
            layout=layout_result.metadata,
            table=table_result.metadata,
        ),
        raw=raw,
    )


def _link_table_refs(
    layout_table_refs: list[TableRef],
    table_table_refs: list[TableRef],
) -> list[TableRef]:
    """추출된 table 내용을 대응하는 layout table ref에 붙인다."""
    if not layout_table_refs or not table_table_refs:
        return list(table_table_refs)

    remaining_layout = list(layout_table_refs)
    linked_refs: list[TableRef] = []
    for index, table_ref in enumerate(table_table_refs):
        layout_ref, strategy = _match_layout_table_ref(
            table_ref,
            remaining_layout,
            index,
        )
        if layout_ref is None or strategy is None:
            linked_refs.append(table_ref)
            continue

        linked_refs.append(_merge_linked_table_ref(layout_ref, table_ref, strategy))
        remaining_layout = [
            candidate
            for candidate in remaining_layout
            if candidate.table_id != layout_ref.table_id
        ]

    return linked_refs


def _match_layout_table_ref(
    table_ref: TableRef,
    layout_candidates: list[TableRef],
    index: int,
) -> tuple[TableRef | None, str | None]:
    """table 추출 결과와 가장 잘 맞는 layout table ref를 찾는다."""
    if not layout_candidates:
        return None, None

    for candidate in layout_candidates:
        if candidate.table_id == table_ref.table_id:
            return candidate, "table_id"

    table_source_ids = set(table_ref.source_block_ids)
    if table_source_ids:
        for candidate in layout_candidates:
            if table_source_ids.intersection(candidate.source_block_ids):
                return candidate, "source_block_id"

    table_image_path = _normalize_str(
        table_ref.metadata.get("crop_path")
        or table_ref.metadata.get("image_path")
        or table_ref.metadata.get("table_image_path")
    )
    if table_image_path is not None:
        for candidate in layout_candidates:
            candidate_image_path = _normalize_str(
                candidate.metadata.get("crop_path")
                or candidate.metadata.get("image_path")
                or candidate.metadata.get("table_image_path")
            )
            if candidate_image_path == table_image_path:
                return candidate, "crop_path"

    if not table_ref.metadata.get("generated_page") and table_ref.bbox is not None:
        best_candidate: TableRef | None = None
        best_score = 0.0
        for candidate in layout_candidates:
            if candidate.page != table_ref.page:
                continue
            iou = _bbox_iou(candidate.bbox, table_ref.bbox) or 0.0
            if iou > best_score:
                best_candidate = candidate
                best_score = iou

        if best_candidate is not None and best_score >= 0.5:
            return best_candidate, "page_bbox"

    if not table_ref.metadata.get("generated_page"):
        same_page_candidates = [
            candidate
            for candidate in layout_candidates
            if candidate.page == table_ref.page
        ]
        if len(same_page_candidates) == 1:
            return same_page_candidates[0], "page_only"

    if index < len(layout_candidates):
        return layout_candidates[index], "document_order"
    return None, None


def _merge_linked_table_ref(
    layout_ref: TableRef,
    table_ref: TableRef,
    strategy: str,
) -> TableRef:
    """layout geometry를 유지하면서 table 추출 metadata와 내용을 더한다."""
    metadata = {
        **dict(layout_ref.metadata),
        **dict(table_ref.metadata),
        "layout_table_id": layout_ref.table_id,
        "link_strategy": strategy,
    }
    if table_ref.table_id != layout_ref.table_id:
        metadata["table_output_id"] = table_ref.table_id

    return TableRef(
        table_id=layout_ref.table_id,
        page=layout_ref.page,
        bbox=layout_ref.bbox or table_ref.bbox,
        caption_id=table_ref.caption_id or layout_ref.caption_id,
        note_ids=_merge_unique_ids(layout_ref.note_ids, table_ref.note_ids),
        source_block_ids=_merge_unique_ids(
            layout_ref.source_block_ids or [layout_ref.table_id],
            table_ref.source_block_ids,
        ),
        metadata=metadata,
        raw={
            "layout": layout_ref.raw,
            "table": table_ref.raw,
        },
    )
