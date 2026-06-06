from __future__ import annotations

"""Step 3. Structural Relation Assembly의 공개 실행 단계."""

from dataclasses import replace
from typing import Any, Dict, List, Set

from modules.assembly.ir import AssemblyElement, AssemblyResult, BlockRelation, SectionNode
from modules.assembly.stages.contracts import require_assembly_result, require_stage
from modules.assembly.stages.structure import (
    caption_linker,
    heuristics,
    reading_order,
    section_assembly,
)


class StructureAssembler:
    """읽기 순서가 확정된 block을 문서 구조 IR로 조립한다."""

    PARA_MERGE_RATIO = heuristics.PARA_MERGE_RATIO
    NEW_PARA_RATIO = heuristics.NEW_PARA_RATIO
    HEADING_FONT_RATIO = heuristics.HEADING_FONT_RATIO
    CAPTION_DIST_RATIO = heuristics.CAPTION_DIST_RATIO
    NOTE_DIST_RATIO = heuristics.NOTE_DIST_RATIO

    DEFAULT_LINE_HEIGHT = heuristics.DEFAULT_LINE_HEIGHT
    DEFAULT_BODY_FONT_SIZE = heuristics.DEFAULT_BODY_FONT_SIZE
    MIN_INDENT_TOLERANCE = heuristics.MIN_INDENT_TOLERANCE

    PARAGRAPH_LIKE_KINDS = heuristics.PARAGRAPH_LIKE_KINDS
    TERMINAL_PUNCTUATION = heuristics.TERMINAL_PUNCTUATION
    ORDERED_LIST_PATTERN = heuristics.ORDERED_LIST_PATTERN
    UNORDERED_LIST_PATTERN = heuristics.UNORDERED_LIST_PATTERN
    NUMERIC_HEADING_PATTERN = heuristics.NUMERIC_HEADING_PATTERN
    PAREN_HEADING_PATTERN = heuristics.PAREN_HEADING_PATTERN
    KOREAN_HEADING_PATTERN = heuristics.KOREAN_HEADING_PATTERN
    TABLE_CAPTION_PATTERN = heuristics.TABLE_CAPTION_PATTERN
    FIGURE_CAPTION_PATTERN = heuristics.FIGURE_CAPTION_PATTERN
    NOTE_PATTERN = heuristics.NOTE_PATTERN

    @classmethod
    def apply(cls, result: AssemblyResult) -> AssemblyResult:
        """reading order 결과를 section/list/paragraph/object 구조로 조립한다."""
        result = require_assembly_result(result, cls.__name__)
        require_stage(result, "normalized", cls.__name__)

        ordered_elements = reading_order.ensure_reading_order(result.ordered_elements)
        next_relations = reading_order.build_next_relations(ordered_elements)
        page_stats_by_page = {page_stat.page: page_stat for page_stat in result.page_stats}
        element_map = {element.id: element for element in ordered_elements}

        (
            table_refs,
            figure_refs,
            note_refs,
            caption_target_map,
            note_target_map,
            attachment_summary,
        ) = caption_linker.resolve_object_attachments(
            ordered_elements=ordered_elements,
            element_map=element_map,
            table_refs=result.document.table_refs,
            figure_refs=result.document.figure_refs,
            note_refs=result.document.note_refs,
            page_stats_by_page=page_stats_by_page,
        )

        section_stack: List[SectionNode] = []
        root_children: List[Any] = []
        top_sections: List[SectionNode] = []
        structure_relations: List[BlockRelation] = caption_linker.build_attachment_relations(
            table_refs=table_refs,
            figure_refs=figure_refs,
            note_target_map=note_target_map,
        )
        parent_assignments: Dict[str, str] = {}

        paragraph_index = 1
        list_index = 1
        paragraph_buffer: List[AssemblyElement] = []
        list_buffer: List[AssemblyElement] = []
        anchored_table_ids: Set[str] = set()
        anchored_figure_ids: Set[str] = set()
        anchored_note_ids: Set[str] = set()

        def flush_paragraph_buffer() -> None:
            nonlocal paragraph_index
            if not paragraph_buffer:
                return

            paragraph_node = section_assembly.build_paragraph_group(
                block_ids=list(paragraph_buffer),
                group_index=paragraph_index,
            )
            paragraph_index += 1
            section_assembly.append_node_to_tree(
                node=paragraph_node,
                section_stack=section_stack,
                root_children=root_children,
                relations=structure_relations,
                source_block_ids=paragraph_node.source_block_ids,
            )
            paragraph_buffer.clear()

        def flush_list_buffer() -> None:
            nonlocal list_index
            if not list_buffer:
                return

            list_node = section_assembly.build_list_group(
                block_ids=list(list_buffer),
                group_index=list_index,
                page_stats_by_page=page_stats_by_page,
            )
            list_index += 1
            section_assembly.append_node_to_tree(
                node=list_node,
                section_stack=section_stack,
                root_children=root_children,
                relations=structure_relations,
                source_block_ids=list_node.source_block_ids,
            )
            list_buffer.clear()

        for element in ordered_elements:
            if element.kind == "heading" and element.text:
                flush_paragraph_buffer()
                flush_list_buffer()

                section_node = section_assembly.build_section_node(
                    heading=element,
                    page_stat=page_stats_by_page.get(element.page),
                )
                while section_stack and heuristics.effective_section_level(
                    section_stack[-1]
                ) >= heuristics.effective_section_level(section_node):
                    section_stack.pop()

                if section_stack:
                    parent_section = section_stack[-1]
                    parent_section.children.append(section_node)
                    structure_relations.append(
                        BlockRelation(
                            type="child_of",
                            src=section_node.id,
                            dst=parent_section.id,
                            score=1.0,
                            metadata={"source": "structure_section_tree"},
                        )
                    )
                else:
                    root_children.append(section_node)
                    top_sections.append(section_node)

                section_stack.append(section_node)
                parent_assignments[element.id] = section_node.id
                structure_relations.append(
                    BlockRelation(
                        type="child_of",
                        src=element.id,
                        dst=section_node.id,
                        score=1.0,
                        metadata={"source": "structure_heading", "role": "heading"},
                    )
                )
                continue

            if element.id in caption_target_map:
                flush_paragraph_buffer()
                flush_list_buffer()
                parent_assignments[element.id] = caption_target_map[element.id]
                continue

            if element.id in note_target_map:
                flush_paragraph_buffer()
                flush_list_buffer()
                parent_assignments[element.id] = note_target_map[element.id]
                continue

            if element.kind == "list_item":
                flush_paragraph_buffer()
                if not list_buffer:
                    list_buffer.append(element)
                    continue

                if heuristics.should_continue_list(
                    previous=list_buffer[-1],
                    current=element,
                    page_stat=page_stats_by_page.get(element.page),
                ):
                    list_buffer.append(element)
                    continue

                flush_list_buffer()
                list_buffer.append(element)
                continue

            flush_list_buffer()

            if element.kind == "table":
                flush_paragraph_buffer()
                table_node = section_assembly.resolve_table_node(table_refs, element)
                section_assembly.append_node_to_tree(
                    node=table_node,
                    section_stack=section_stack,
                    root_children=root_children,
                    relations=structure_relations,
                    source_block_ids=table_node.source_block_ids or [table_node.table_id],
                )
                if section_stack:
                    parent_assignments[element.id] = section_stack[-1].id
                anchored_table_ids.add(table_node.table_id)
                continue

            if element.kind == "figure":
                flush_paragraph_buffer()
                figure_node = section_assembly.resolve_figure_node(figure_refs, element)
                section_assembly.append_node_to_tree(
                    node=figure_node,
                    section_stack=section_stack,
                    root_children=root_children,
                    relations=structure_relations,
                    source_block_ids=figure_node.source_block_ids or [figure_node.figure_id],
                )
                if section_stack:
                    parent_assignments[element.id] = section_stack[-1].id
                anchored_figure_ids.add(figure_node.figure_id)
                continue

            if element.kind == "note":
                flush_paragraph_buffer()
                note_node = section_assembly.resolve_note_node(note_refs, element)
                section_assembly.append_node_to_tree(
                    node=note_node,
                    section_stack=section_stack,
                    root_children=root_children,
                    relations=structure_relations,
                    source_block_ids=note_node.source_block_ids or [note_node.note_id],
                )
                if section_stack:
                    parent_assignments[element.id] = section_stack[-1].id
                anchored_note_ids.add(note_node.note_id)
                continue

            if not paragraph_buffer:
                paragraph_buffer.append(element)
                continue

            if heuristics.should_merge_paragraph(
                previous=paragraph_buffer[-1],
                current=element,
                page_stat=page_stats_by_page.get(element.page),
            ):
                paragraph_buffer.append(element)
                continue

            flush_paragraph_buffer()
            paragraph_buffer.append(element)

        flush_paragraph_buffer()
        flush_list_buffer()

        for table_ref in table_refs:
            if table_ref.table_id not in anchored_table_ids:
                root_children.append(table_ref)

        for figure_ref in figure_refs:
            if figure_ref.figure_id not in anchored_figure_ids:
                root_children.append(figure_ref)

        for note_ref in note_refs:
            if note_ref.note_id in anchored_note_ids or note_ref.target_id is not None:
                continue
            root_children.append(note_ref)

        section_assembly.finalize_sections(top_sections)

        updated_elements = section_assembly.apply_parent_assignments(
            ordered_elements=ordered_elements,
            parent_assignments=parent_assignments,
            caption_target_map=caption_target_map,
            note_target_map=note_target_map,
        )
        structure_summary = section_assembly.build_structure_summary(
            root_children=root_children,
            top_sections=top_sections,
            table_refs=table_refs,
            figure_refs=figure_refs,
            note_refs=note_refs,
            attachment_summary=attachment_summary,
        )

        document_metadata = dict(result.document.metadata)
        document_metadata["structure_assembly"] = structure_summary

        return AssemblyResult(
            ordered_elements=updated_elements,
            block_relations=reading_order.merge_next_relations(
                result.block_relations,
                next_relations,
            ) + structure_relations,
            document=replace(
                result.document,
                children=root_children,
                sections=top_sections,
                table_refs=table_refs,
                figure_refs=figure_refs,
                note_refs=note_refs,
                metadata=document_metadata,
            ),
            page_stats=list(result.page_stats),
            warnings=list(result.warnings),
            metadata=section_assembly.build_structure_metadata(result.metadata, structure_summary),
            raw=result.raw,
        )
