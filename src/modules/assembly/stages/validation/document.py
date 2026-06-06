from __future__ import annotations

"""Validation 단계의 document/geometry 검증."""

from collections import defaultdict
from typing import Any, DefaultDict, Iterable, List, Sequence, Set

from modules.assembly.common.values import merge_unique_ids, normalize_int
from modules.assembly.ir import (
    AssemblyElement,
    AssemblyWarning,
    FigureRef,
    ListGroup,
    NoteRef,
    ParagraphGroup,
    SectionNode,
    TableRef,
)


GEOMETRY_REQUIRED_KINDS = frozenset(
    {
        "heading",
        "text",
        "list_item",
        "table",
        "figure",
        "caption",
        "note",
        "formula",
        "quote",
        "code_block",
    }
)


def validate_sections(sections: Sequence[SectionNode]) -> List[AssemblyWarning]:
    """body 없이 heading만 남은 section을 찾는다."""
    collected_warnings: List[AssemblyWarning] = []
    for section in iter_sections(sections):
        body_child_count = len(
            [child for child in section.children if not isinstance(child, SectionNode)]
        )
        if body_child_count > 0:
            continue

        collected_warnings.append(
            AssemblyWarning(
                code="empty_section",
                message="body 없이 heading만 남은 section이 있습니다.",
                level="warning",
                page=normalize_int(section.metadata.get("page")),
                element_ids=merge_unique_ids(section.heading_block_id, section.source_block_ids),
                metadata={
                    "section_id": section.id,
                    "title": section.title,
                    "child_section_count": len(section.children),
                },
            )
        )

    return collected_warnings


def validate_geometry(
    ordered_elements: Sequence[AssemblyElement],
    table_refs: Sequence[TableRef],
    figure_refs: Sequence[FigureRef],
    note_refs: Sequence[NoteRef],
) -> List[AssemblyWarning]:
    """후속 단계가 쓰는 bbox가 비어 있는 block/ref를 모아 경고한다."""
    missing_by_page: DefaultDict[int, List[str]] = defaultdict(list)

    for element in ordered_elements:
        if element.kind not in GEOMETRY_REQUIRED_KINDS or element.bbox is not None:
            continue
        missing_by_page[element.page].append(element.id)

    for ref in list(table_refs) + list(figure_refs) + list(note_refs):
        if ref.bbox is not None:
            continue
        missing_by_page[ref.page].append(
            getattr(ref, "table_id", None)
            or getattr(ref, "figure_id", None)
            or getattr(ref, "note_id", None)
        )

    collected_warnings: List[AssemblyWarning] = []
    for page, element_ids in sorted(missing_by_page.items()):
        normalized_ids = [element_id for element_id in element_ids if element_id]
        collected_warnings.append(
            AssemblyWarning(
                code="missing_geometry",
                message="bbox가 비어 있는 block 또는 ref가 있습니다.",
                level="warning",
                page=page,
                element_ids=normalized_ids,
            )
        )

    return collected_warnings


def collect_source_ids_from_nodes(nodes: Sequence[Any]) -> Set[str]:
    """문서 구조 트리에서 소비된 source block id를 재귀적으로 모은다."""
    source_ids: Set[str] = set()

    for node in nodes:
        if isinstance(node, SectionNode):
            source_ids.update(merge_unique_ids(node.heading_block_id, node.source_block_ids))
            source_ids.update(collect_source_ids_from_nodes(node.children))
            continue

        if isinstance(node, ParagraphGroup):
            source_ids.update(merge_unique_ids(node.block_ids, node.source_block_ids))
            continue

        if isinstance(node, ListGroup):
            source_ids.update(merge_unique_ids(node.source_block_ids))
            for item in node.items:
                source_ids.update(merge_unique_ids(item.block_ids, item.source_block_ids))
            continue

        if isinstance(node, TableRef):
            source_ids.update(merge_unique_ids(node.table_id, node.source_block_ids))
            continue

        if isinstance(node, FigureRef):
            source_ids.update(merge_unique_ids(node.figure_id, node.source_block_ids))
            continue

        if isinstance(node, NoteRef):
            source_ids.update(merge_unique_ids(node.note_id, node.source_block_ids))
            continue

    return source_ids


def iter_sections(sections: Sequence[SectionNode]) -> Iterable[SectionNode]:
    """section subtree를 평탄하게 순회한다."""
    for section in sections:
        yield section
        for child in section.children:
            if isinstance(child, SectionNode):
                yield from iter_sections([child])
