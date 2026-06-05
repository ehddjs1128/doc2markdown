from __future__ import annotations

"""저장된 Assembly IR payload를 복원하는 helper를 제공한다."""

from collections.abc import Mapping
from typing import Any

from modules.assembly.ir import (
    AssemblyElement,
    AssemblyMeta,
    AssemblyResult,
    AssemblyWarning,
    AssembledDocument,
    BlockRelation,
    FigureRef,
    ListGroup,
    ListGroupItem,
    NoteRef,
    PageStats,
    ParagraphGroup,
    SectionNode,
    TableRef,
)


def assembly_result_from_dict(data: Mapping[str, Any]) -> AssemblyResult:
    """저장된 AssemblyResult dict를 렌더링 가능한 IR로 복원한다."""
    payload = dict(data)
    return AssemblyResult(
        ordered_elements=[
            assembly_element_from_dict(item)
            for item in _coerce_mapping_list(payload.get("ordered_elements"))
        ],
        block_relations=[
            block_relation_from_dict(item)
            for item in _coerce_mapping_list(payload.get("block_relations"))
        ],
        document=document_from_dict(_coerce_mapping(payload.get("document"))),
        page_stats=[
            page_stats_from_dict(item)
            for item in _coerce_mapping_list(payload.get("page_stats"))
        ],
        warnings=[
            assembly_warning_from_dict(item)
            for item in _coerce_mapping_list(payload.get("warnings"))
        ],
        metadata=meta_from_dict(_coerce_mapping(payload.get("metadata"))),
        raw=payload.get("raw"),
    )


def document_from_dict(data: Mapping[str, Any]) -> AssembledDocument:
    """AssembledDocument와 typed child/reference node를 복원한다."""
    payload = dict(data)
    return AssembledDocument(
        title_candidate=payload.get("title_candidate"),
        title_source_block_ids=list(payload.get("title_source_block_ids") or []),
        children=[
            assembled_node_from_dict(item)
            for item in _coerce_mapping_list(payload.get("children"))
        ],
        sections=[
            section_node_from_dict(item)
            for item in _coerce_mapping_list(payload.get("sections"))
        ],
        table_refs=[
            table_ref_from_dict(item)
            for item in _coerce_mapping_list(payload.get("table_refs"))
        ],
        figure_refs=[
            figure_ref_from_dict(item)
            for item in _coerce_mapping_list(payload.get("figure_refs"))
        ],
        note_refs=[
            note_ref_from_dict(item)
            for item in _coerce_mapping_list(payload.get("note_refs"))
        ],
        figure_assets_metadata=dict(payload.get("figure_assets_metadata") or {}),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def assembled_node_from_dict(data: Mapping[str, Any]) -> Any:
    """직렬화된 document child를 node type 기준으로 복원한다."""
    payload = dict(data)
    node_type = payload.get("type")
    if node_type == "section":
        return section_node_from_dict(payload)
    if node_type == "paragraph_group":
        return paragraph_group_from_dict(payload)
    if node_type == "list_group":
        return list_group_from_dict(payload)
    if node_type == "table_ref":
        return table_ref_from_dict(payload)
    if node_type == "figure_ref":
        return figure_ref_from_dict(payload)
    if node_type == "note_ref":
        return note_ref_from_dict(payload)
    raise ValueError(f"Unknown assembled node type: {node_type!r}")


def section_node_from_dict(data: Mapping[str, Any]) -> SectionNode:
    payload = dict(data)
    return SectionNode(
        type="section",
        id=str(payload.get("id", "")),
        level=payload.get("level"),
        title=payload.get("title"),
        heading_block_id=payload.get("heading_block_id"),
        source_block_ids=list(payload.get("source_block_ids") or []),
        children=[
            assembled_node_from_dict(item)
            for item in _coerce_mapping_list(payload.get("children"))
        ],
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def paragraph_group_from_dict(data: Mapping[str, Any]) -> ParagraphGroup:
    payload = dict(data)
    return ParagraphGroup(
        type="paragraph_group",
        id=str(payload.get("id", "")),
        block_ids=list(payload.get("block_ids") or []),
        text=payload.get("text"),
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def list_group_from_dict(data: Mapping[str, Any]) -> ListGroup:
    payload = dict(data)
    return ListGroup(
        type="list_group",
        id=str(payload.get("id", "")),
        ordered=payload.get("ordered"),
        items=[
            list_group_item_from_dict(item)
            for item in _coerce_mapping_list(payload.get("items"))
        ],
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def list_group_item_from_dict(data: Mapping[str, Any]) -> ListGroupItem:
    payload = dict(data)
    return ListGroupItem(
        block_ids=list(payload.get("block_ids") or []),
        text=payload.get("text"),
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def table_ref_from_dict(data: Mapping[str, Any]) -> TableRef:
    payload = dict(data)
    return TableRef(
        table_id=str(payload.get("table_id", "")),
        page=int(payload.get("page", 1)),
        type="table_ref",
        bbox=bbox_from_value(payload.get("bbox")),
        caption_id=payload.get("caption_id"),
        note_ids=list(payload.get("note_ids") or []),
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def figure_ref_from_dict(data: Mapping[str, Any]) -> FigureRef:
    payload = dict(data)
    return FigureRef(
        figure_id=str(payload.get("figure_id", "")),
        page=int(payload.get("page", 1)),
        type="figure_ref",
        bbox=bbox_from_value(payload.get("bbox")),
        caption_id=payload.get("caption_id"),
        asset_path=payload.get("asset_path"),
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def note_ref_from_dict(data: Mapping[str, Any]) -> NoteRef:
    payload = dict(data)
    return NoteRef(
        note_id=str(payload.get("note_id", "")),
        page=int(payload.get("page", 1)),
        type="note_ref",
        bbox=bbox_from_value(payload.get("bbox")),
        text=payload.get("text"),
        target_id=payload.get("target_id"),
        source_block_ids=list(payload.get("source_block_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def assembly_element_from_dict(data: Mapping[str, Any]) -> AssemblyElement:
    payload = dict(data)
    return AssemblyElement(
        id=str(payload.get("id", "")),
        page=int(payload.get("page", 1)),
        kind=payload.get("kind", "text"),
        bbox=bbox_from_value(payload.get("bbox")),
        text=payload.get("text"),
        label=payload.get("label"),
        confidence=payload.get("confidence"),
        column_id=payload.get("column_id"),
        reading_order=payload.get("reading_order"),
        parent_id=payload.get("parent_id"),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def block_relation_from_dict(data: Mapping[str, Any]) -> BlockRelation:
    payload = dict(data)
    return BlockRelation(
        type=payload.get("type", "next"),
        src=str(payload.get("src", "")),
        dst=str(payload.get("dst", "")),
        score=payload.get("score"),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def page_stats_from_dict(data: Mapping[str, Any]) -> PageStats:
    payload = dict(data)
    return PageStats(
        page=int(payload.get("page", 1)),
        width=payload.get("width"),
        height=payload.get("height"),
        median_line_height=payload.get("median_line_height"),
        body_font_size=payload.get("body_font_size"),
        column_count=payload.get("column_count"),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def assembly_warning_from_dict(data: Mapping[str, Any]) -> AssemblyWarning:
    payload = dict(data)
    return AssemblyWarning(
        code=payload.get("code", "missing_geometry"),
        message=payload.get("message", ""),
        level=payload.get("level", "warning"),
        page=payload.get("page"),
        element_ids=list(payload.get("element_ids") or []),
        metadata=dict(payload.get("metadata") or {}),
        raw=payload.get("raw"),
    )


def meta_from_dict(data: Mapping[str, Any]) -> AssemblyMeta:
    payload = dict(data)
    return AssemblyMeta(
        stage=payload.get("stage"),
        adapter=payload.get("adapter"),
        source=payload.get("source"),
        details=dict(payload.get("details") or {}),
    )


def bbox_from_value(value: Any) -> tuple[float, float, float, float] | None:
    """직렬화 값이 네 좌표를 가지면 float bbox tuple로 돌려준다."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    return float(value[0]), float(value[1]), float(value[2]), float(value[3])


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _coerce_mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
