from __future__ import annotations

"""Step 4. Section Assembly와 document tree node 생성."""

from dataclasses import replace
from typing import Any, Dict, List

from modules.assembly.common.values import merge_unique_ids
from modules.assembly.ir import (
    AssemblyElement,
    AssemblyMeta,
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
from modules.assembly.stages.structure import heuristics


def resolve_table_node(table_refs: List[TableRef], element: AssemblyElement) -> TableRef:
    """table element에 대응하는 ref를 우선 재사용한다."""
    for table_ref in table_refs:
        if table_ref.table_id == element.id:
            return table_ref

    return TableRef(
        table_id=element.id,
        page=element.page,
        bbox=element.bbox,
        source_block_ids=[element.id],
        metadata={"source": "structure_fallback"},
        raw=element.raw,
    )


def resolve_figure_node(figure_refs: List[FigureRef], element: AssemblyElement) -> FigureRef:
    """figure element에 대응하는 ref를 우선 재사용한다."""
    for figure_ref in figure_refs:
        if figure_ref.figure_id == element.id:
            return figure_ref

    return FigureRef(
        figure_id=element.id,
        page=element.page,
        bbox=element.bbox,
        source_block_ids=[element.id],
        metadata={"source": "structure_fallback"},
        raw=element.raw,
    )


def resolve_note_node(note_refs: List[NoteRef], element: AssemblyElement) -> NoteRef:
    """standalone note는 document.note_refs를 재사용한다."""
    for note_ref in note_refs:
        if note_ref.note_id == element.id:
            return note_ref

    return NoteRef(
        note_id=element.id,
        page=element.page,
        bbox=element.bbox,
        text=element.text,
        source_block_ids=[element.id],
        metadata={"source": "structure_fallback"},
        raw=element.raw,
    )


def append_node_to_tree(
    node: Any,
    section_stack: List[SectionNode],
    root_children: List[Any],
    relations: List[BlockRelation],
    source_block_ids: List[str],
) -> None:
    """현재 section 문맥에 맞게 node를 배치한다."""
    if section_stack:
        current_section = section_stack[-1]
        current_section.children.append(node)
        for source_block_id in source_block_ids:
            relations.append(
                BlockRelation(
                    type="child_of",
                    src=source_block_id,
                    dst=current_section.id,
                    score=1.0,
                    metadata={"source": "structure_child_assignment"},
                )
            )
        return

    root_children.append(node)


def build_paragraph_group(
    block_ids: List[AssemblyElement],
    group_index: int,
) -> ParagraphGroup:
    """연속 block을 하나의 paragraph_group으로 묶는다."""
    source_block_ids = [block.id for block in block_ids]
    texts = [block.text for block in block_ids if block.text]
    joined_text = " ".join(texts) if texts else None
    kinds = list(dict.fromkeys(block.kind for block in block_ids))

    return ParagraphGroup(
        id=f"paragraph_{group_index}",
        block_ids=source_block_ids,
        text=joined_text,
        source_block_ids=source_block_ids,
        metadata={
            "kinds": kinds,
            "page_range": sorted({block.page for block in block_ids}),
            "column_ids": [block.column_id for block in block_ids],
            "line_count": len(block_ids),
        },
        raw=[block.raw for block in block_ids],
    )


def build_list_group(
    block_ids: List[AssemblyElement],
    group_index: int,
    page_stats_by_page: Dict[int, PageStats],
) -> ListGroup:
    """연속 list_item block을 하나의 list_group으로 묶는다."""
    source_block_ids = [block.id for block in block_ids]
    ordered_flags = [heuristics.is_ordered_list_item(block.text) for block in block_ids if block.text]
    ordered = all(ordered_flags) if ordered_flags else None

    base_indent = min(heuristics.bbox_left(block) for block in block_ids)
    first_page_stat = page_stats_by_page.get(block_ids[0].page)
    indent_unit = max(
        heuristics.MIN_INDENT_TOLERANCE,
        heuristics.line_height(first_page_stat),
    )

    items: List[ListGroupItem] = []
    for block in block_ids:
        item_indent = heuristics.bbox_left(block)
        indent_level = max(0, round((item_indent - base_indent) / indent_unit))
        list_marker, stripped_text = heuristics.split_list_marker(block.text)
        items.append(
            ListGroupItem(
                block_ids=[block.id],
                text=stripped_text,
                source_block_ids=[block.id],
                metadata={
                    "indent": item_indent,
                    "indent_level": indent_level,
                    "ordered": heuristics.is_ordered_list_item(block.text),
                    "list_marker": list_marker,
                    "source_text": block.text,
                },
                raw=block.raw,
            )
        )

    return ListGroup(
        id=f"list_{group_index}",
        ordered=ordered,
        items=items,
        source_block_ids=source_block_ids,
        metadata={
            "item_count": len(items),
            "base_indent": base_indent,
        },
        raw=[block.raw for block in block_ids],
    )


def build_section_node(
    heading: AssemblyElement,
    page_stat: PageStats | None,
) -> SectionNode:
    """heading block 하나로 section node를 시작한다."""
    level, level_source = heuristics.infer_heading(heading, page_stat)
    return SectionNode(
        id=f"section_{heading.id}",
        level=level,
        title=heading.text,
        heading_block_id=heading.id,
        source_block_ids=[heading.id],
        metadata={
            "page": heading.page,
            "column_id": heading.column_id,
            "reading_order": heading.reading_order,
            "heading_level_source": level_source,
        },
        raw=heading.raw,
    )


def apply_parent_assignments(
    ordered_elements: List[AssemblyElement],
    parent_assignments: Dict[str, str],
    caption_target_map: Dict[str, str],
    note_target_map: Dict[str, str],
) -> List[AssemblyElement]:
    """구조 조립 결과를 element.parent_id와 metadata에 반영한다."""
    updated_elements: List[AssemblyElement] = []
    for element in ordered_elements:
        metadata = dict(element.metadata)
        metadata["structure_assembled"] = True

        parent_id = parent_assignments.get(element.id)
        if element.id in caption_target_map:
            parent_id = caption_target_map[element.id]
            metadata["attached_as"] = "caption"
            metadata["target_id"] = caption_target_map[element.id]
        elif element.id in note_target_map:
            parent_id = note_target_map[element.id]
            metadata["attached_as"] = "note"
            metadata["target_id"] = note_target_map[element.id]
        elif parent_id is not None:
            metadata["section_id"] = parent_id

        updated_elements.append(
            replace(
                element,
                parent_id=parent_id or element.parent_id,
                metadata=metadata,
            )
        )

    return updated_elements


def finalize_sections(sections: List[SectionNode]) -> None:
    """section subtree가 완성된 뒤 provenance를 재계산한다."""
    for section in sections:
        section.children = finalize_section_children(section.children)
        aggregated_ids = [section.heading_block_id] if section.heading_block_id else []

        for child in section.children:
            aggregated_ids.extend(extract_node_source_block_ids(child))

        section.source_block_ids = merge_unique_ids(aggregated_ids)


def finalize_section_children(children: List[Any]) -> List[Any]:
    """중첩 section도 같은 규칙으로 마무리한다."""
    finalized_children: List[Any] = []
    for child in children:
        if isinstance(child, SectionNode):
            finalize_sections([child])
        finalized_children.append(child)
    return finalized_children


def extract_node_source_block_ids(node: Any) -> List[str]:
    """조립 노드에서 provenance id를 일관되게 꺼낸다."""
    if isinstance(node, SectionNode):
        return list(node.source_block_ids)
    if hasattr(node, "source_block_ids"):
        return list(getattr(node, "source_block_ids"))
    if hasattr(node, "table_id"):
        return [getattr(node, "table_id")]
    if hasattr(node, "figure_id"):
        return [getattr(node, "figure_id")]
    if hasattr(node, "note_id"):
        return [getattr(node, "note_id")]
    return []


def build_structure_summary(
    root_children: List[Any],
    top_sections: List[SectionNode],
    table_refs: List[TableRef],
    figure_refs: List[FigureRef],
    note_refs: List[NoteRef],
    attachment_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """metadata에 남길 구조 조립 요약을 만든다."""
    paragraph_count = 0
    list_count = 0
    section_count = 0

    def walk(node: Any) -> None:
        nonlocal paragraph_count, list_count, section_count
        if isinstance(node, SectionNode):
            section_count += 1
            for child in node.children:
                walk(child)
            return
        if isinstance(node, ParagraphGroup):
            paragraph_count += 1
            return
        if isinstance(node, ListGroup):
            list_count += 1

    for child in root_children:
        walk(child)

    return {
        "root_child_count": len(root_children),
        "top_section_count": len(top_sections),
        "section_count": section_count,
        "paragraph_group_count": paragraph_count,
        "list_group_count": list_count,
        "table_ref_count": len(table_refs),
        "figure_ref_count": len(figure_refs),
        "note_ref_count": len(note_refs),
        "standalone_note_count": len([note_ref for note_ref in note_refs if note_ref.target_id is None]),
        "attached_note_count": len([note_ref for note_ref in note_refs if note_ref.target_id is not None]),
        "attachment": attachment_summary,
    }


def build_structure_metadata(
    previous_metadata: AssemblyMeta,
    structure_summary: Dict[str, Any],
) -> AssemblyMeta:
    """이전 메타데이터를 보존하면서 stage만 structure_assembled로 바꾼다."""
    details = dict(previous_metadata.details)
    details["upstream_stage"] = previous_metadata.stage
    details["structure_assembly"] = structure_summary

    return AssemblyMeta(
        stage="structure_assembled",
        adapter=previous_metadata.adapter,
        source=previous_metadata.source,
        details=details,
    )
