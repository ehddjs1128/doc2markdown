from __future__ import annotations

"""Validation 단계의 caption/note/object link 검증."""

from collections import defaultdict
from typing import DefaultDict, Dict, List, Sequence, Set

from modules.assembly.ir import AssemblyElement, AssemblyWarning, BlockRelation, FigureRef, NoteRef, TableRef
from modules.assembly.stages.validation import relations
from modules.assembly.stages.validation import warnings as warning_helpers


def validate_caption_links(
    ordered_elements: Sequence[AssemblyElement],
    table_refs: Sequence[TableRef],
    figure_refs: Sequence[FigureRef],
    caption_relations: Sequence[BlockRelation],
    object_ids: Set[str],
) -> List[AssemblyWarning]:
    """caption 연결과 caption_of 관계가 일관적인지 점검한다."""
    collected_warnings: List[AssemblyWarning] = []
    caption_targets = relations.build_relation_targets(caption_relations)

    for table_ref in table_refs:
        if table_ref.caption_id is not None:
            caption_targets[table_ref.caption_id].add(table_ref.table_id)
    for figure_ref in figure_refs:
        if figure_ref.caption_id is not None:
            caption_targets[figure_ref.caption_id].add(figure_ref.figure_id)

    conflicting_ids = [
        caption_id
        for caption_id, targets in caption_targets.items()
        if len(targets) > 1
    ]
    if conflicting_ids:
        collected_warnings.append(
            AssemblyWarning(
                code="relation_conflict",
                message="하나의 caption이 여러 object를 동시에 가리키고 있습니다.",
                level="warning",
                page=warning_helpers.first_known_page(ordered_elements, conflicting_ids),
                element_ids=conflicting_ids,
                metadata={
                    "relation_type": "caption_of",
                    "targets": {
                        caption_id: sorted(caption_targets[caption_id])
                        for caption_id in conflicting_ids
                    },
                },
            )
        )

    orphan_by_page: DefaultDict[int, List[str]] = defaultdict(list)
    for element in ordered_elements:
        if element.kind != "caption":
            continue

        targets = caption_targets.get(element.id, set())
        if not targets:
            orphan_by_page[element.page].append(element.id)
            continue

        if element.parent_id is not None and element.parent_id not in targets:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="caption block의 parent_id와 caption_of 대상이 다릅니다.",
                    level="warning",
                    page=element.page,
                    element_ids=[element.id],
                    metadata={
                        "relation_type": "caption_of",
                        "parent_id": element.parent_id,
                        "relation_targets": sorted(targets),
                    },
                )
            )

        missing_targets = sorted(target for target in targets if target not in object_ids)
        if missing_targets:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="caption이 가리키는 object id가 현재 문서 ref 목록에 없습니다.",
                    level="warning",
                    page=element.page,
                    element_ids=[element.id],
                    metadata={
                        "relation_type": "caption_of",
                        "missing_targets": missing_targets,
                    },
                )
            )

    for page, element_ids in sorted(orphan_by_page.items()):
        collected_warnings.append(
            AssemblyWarning(
                code="orphan_caption",
                message="어떤 table/figure에도 연결되지 않은 caption이 있습니다.",
                level="warning",
                page=page,
                element_ids=element_ids,
            )
        )

    return collected_warnings


def validate_note_links(
    ordered_elements: Sequence[AssemblyElement],
    table_refs: Sequence[TableRef],
    note_refs: Sequence[NoteRef],
    note_relations: Sequence[BlockRelation],
    object_ids: Set[str],
    elements_by_id: Dict[str, AssemblyElement],
) -> List[AssemblyWarning]:
    """note 연결과 note_of 관계가 일관적인지 점검한다."""
    collected_warnings: List[AssemblyWarning] = []
    note_targets = relations.build_relation_targets(note_relations)

    for table_ref in table_refs:
        for note_id in table_ref.note_ids:
            note_targets[note_id].add(table_ref.table_id)
    for note_ref in note_refs:
        if note_ref.target_id is not None:
            note_targets[note_ref.note_id].add(note_ref.target_id)

    conflicting_ids = [
        note_id
        for note_id, targets in note_targets.items()
        if len(targets) > 1
    ]
    if conflicting_ids:
        collected_warnings.append(
            AssemblyWarning(
                code="relation_conflict",
                message="하나의 note가 여러 object를 동시에 가리키고 있습니다.",
                level="warning",
                page=warning_helpers.first_known_page(ordered_elements, conflicting_ids),
                element_ids=conflicting_ids,
                metadata={
                    "relation_type": "note_of",
                    "targets": {
                        note_id: sorted(note_targets[note_id])
                        for note_id in conflicting_ids
                    },
                },
            )
        )

    orphan_by_page: DefaultDict[int, List[str]] = defaultdict(list)
    for note_ref in note_refs:
        targets = note_targets.get(note_ref.note_id, set())
        note_element = elements_by_id.get(note_ref.note_id)
        page = note_element.page if note_element is not None else note_ref.page

        if not targets:
            orphan_by_page[page].append(note_ref.note_id)
            continue

        if note_element is not None and note_element.parent_id is not None and note_element.parent_id not in targets:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="note block의 parent_id와 note_of 대상이 다릅니다.",
                    level="warning",
                    page=page,
                    element_ids=[note_ref.note_id],
                    metadata={
                        "relation_type": "note_of",
                        "parent_id": note_element.parent_id,
                        "relation_targets": sorted(targets),
                    },
                )
            )

        missing_targets = sorted(target for target in targets if target not in object_ids)
        if missing_targets:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="note가 가리키는 object id가 현재 문서 ref 목록에 없습니다.",
                    level="warning",
                    page=page,
                    element_ids=[note_ref.note_id],
                    metadata={
                        "relation_type": "note_of",
                        "missing_targets": missing_targets,
                    },
                )
            )

    for page, element_ids in sorted(orphan_by_page.items()):
        collected_warnings.append(
            AssemblyWarning(
                code="orphan_note",
                message="어떤 object에도 연결되지 않은 note가 있습니다.",
                level="warning",
                page=page,
                element_ids=element_ids,
            )
        )

    return collected_warnings


def validate_object_refs(
    table_refs: Sequence[TableRef],
    figure_refs: Sequence[FigureRef],
    elements_by_id: Dict[str, AssemblyElement],
    caption_relations: Sequence[BlockRelation],
    note_relations: Sequence[BlockRelation],
) -> List[AssemblyWarning]:
    """table/figure ref가 필요한 attachment를 갖고 있는지 점검한다."""
    collected_warnings: List[AssemblyWarning] = []
    caption_targets = relations.build_relation_targets(caption_relations)
    note_targets = relations.build_relation_targets(note_relations)

    for table_ref in table_refs:
        if table_ref.caption_id is None:
            collected_warnings.append(
                AssemblyWarning(
                    code="orphan_table",
                    message="caption이 연결되지 않은 table이 있습니다.",
                    level="warning",
                    page=table_ref.page,
                    element_ids=[table_ref.table_id],
                )
            )
        elif table_ref.caption_id not in elements_by_id:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="table이 참조한 caption block id를 ordered_elements에서 찾지 못했습니다.",
                    level="warning",
                    page=table_ref.page,
                    element_ids=[table_ref.table_id, table_ref.caption_id],
                    metadata={"relation_type": "caption_of"},
                )
            )
        elif table_ref.table_id not in caption_targets.get(table_ref.caption_id, set()):
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="table_ref.caption_id와 caption_of 관계가 서로 맞지 않습니다.",
                    level="warning",
                    page=table_ref.page,
                    element_ids=[table_ref.table_id, table_ref.caption_id],
                    metadata={"relation_type": "caption_of"},
                )
            )

        for note_id in table_ref.note_ids:
            if note_id not in elements_by_id:
                collected_warnings.append(
                    AssemblyWarning(
                        code="relation_conflict",
                        message="table이 참조한 note block id를 ordered_elements에서 찾지 못했습니다.",
                        level="warning",
                        page=table_ref.page,
                        element_ids=[table_ref.table_id, note_id],
                        metadata={"relation_type": "note_of"},
                    )
                )
                continue

            if table_ref.table_id not in note_targets.get(note_id, set()):
                collected_warnings.append(
                    AssemblyWarning(
                        code="relation_conflict",
                        message="table_ref.note_ids와 note_of 관계가 서로 맞지 않습니다.",
                        level="warning",
                        page=table_ref.page,
                        element_ids=[table_ref.table_id, note_id],
                        metadata={"relation_type": "note_of"},
                    )
                )

    for figure_ref in figure_refs:
        if figure_ref.caption_id is None:
            collected_warnings.append(
                AssemblyWarning(
                    code="orphan_figure",
                    message="caption이 연결되지 않은 figure가 있습니다.",
                    level="warning",
                    page=figure_ref.page,
                    element_ids=[figure_ref.figure_id],
                )
            )
        elif figure_ref.caption_id not in elements_by_id:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="figure가 참조한 caption block id를 ordered_elements에서 찾지 못했습니다.",
                    level="warning",
                    page=figure_ref.page,
                    element_ids=[figure_ref.figure_id, figure_ref.caption_id],
                    metadata={"relation_type": "caption_of"},
                )
            )
        elif figure_ref.figure_id not in caption_targets.get(figure_ref.caption_id, set()):
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="figure_ref.caption_id와 caption_of 관계가 서로 맞지 않습니다.",
                    level="warning",
                    page=figure_ref.page,
                    element_ids=[figure_ref.figure_id, figure_ref.caption_id],
                    metadata={"relation_type": "caption_of"},
                )
            )

    return collected_warnings

