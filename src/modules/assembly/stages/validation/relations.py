from __future__ import annotations

"""Validation 단계의 relation 무결성 검증."""

from collections import defaultdict
from typing import DefaultDict, List, Sequence, Set, Tuple

from modules.assembly.common.values import merge_unique_ids
from modules.assembly.ir import AssemblyElement, AssemblyWarning, BlockRelation, FigureRef, NoteRef, TableRef
from modules.assembly.stages.validation import warnings as warning_helpers


def validate_next_relations(
    ordered_elements: Sequence[AssemblyElement],
    next_relations: Sequence[BlockRelation],
) -> List[AssemblyWarning]:
    """reading order와 next relation이 같은 순서를 가리키는지 점검한다."""
    if len(ordered_elements) <= 1 and not next_relations:
        return []

    expected_pairs = [
        (current.id, following.id)
        for current, following in zip(ordered_elements, ordered_elements[1:])
    ]
    actual_pairs = [(relation.src, relation.dst) for relation in next_relations]

    missing_pairs = [pair for pair in expected_pairs if pair not in actual_pairs]
    extra_pairs = [pair for pair in actual_pairs if pair not in expected_pairs]

    pair_counts: DefaultDict[Tuple[str, str], int] = defaultdict(int)
    for pair in actual_pairs:
        pair_counts[pair] += 1
    duplicate_pairs = [pair for pair, count in pair_counts.items() if count > 1]

    if not missing_pairs and not extra_pairs and not duplicate_pairs:
        return []

    element_ids = merge_unique_ids(
        [src for src, _ in missing_pairs],
        [dst for _, dst in missing_pairs],
        [src for src, _ in extra_pairs],
        [dst for _, dst in extra_pairs],
        [src for src, _ in duplicate_pairs],
        [dst for _, dst in duplicate_pairs],
    )
    page = warning_helpers.first_known_page(
        ordered_elements,
        [pair[0] for pair in missing_pairs + extra_pairs + duplicate_pairs],
    )

    return [
        AssemblyWarning(
            code="relation_conflict",
            message="reading order와 next 관계가 서로 일치하지 않습니다.",
            level="warning",
            page=page,
            element_ids=element_ids,
            metadata={
                "relation_type": "next",
                "expected_count": len(expected_pairs),
                "actual_count": len(actual_pairs),
                "missing_pairs": [list(pair) for pair in missing_pairs],
                "extra_pairs": [list(pair) for pair in extra_pairs],
                "duplicate_pairs": [list(pair) for pair in duplicate_pairs],
            },
        )
    ]


def validate_child_relations(
    ordered_elements: Sequence[AssemblyElement],
    child_relations: Sequence[BlockRelation],
    root_source_ids: Set[str],
) -> List[AssemblyWarning]:
    """본문 block가 section/tree에 일관되게 귀속되었는지 점검한다."""
    collected_warnings: List[AssemblyWarning] = []
    child_targets = build_relation_targets(child_relations)

    conflicting_ids = [src for src, targets in child_targets.items() if len(targets) > 1]
    if conflicting_ids:
        collected_warnings.append(
            AssemblyWarning(
                code="relation_conflict",
                message="하나의 block이 여러 section 부모를 가리키고 있습니다.",
                level="warning",
                page=warning_helpers.first_known_page(ordered_elements, conflicting_ids),
                element_ids=conflicting_ids,
                metadata={
                    "relation_type": "child_of",
                    "targets": {
                        src: sorted(targets)
                        for src, targets in child_targets.items()
                        if src in conflicting_ids
                    },
                },
            )
        )

    orphan_by_page: DefaultDict[int, List[str]] = defaultdict(list)
    for element in ordered_elements:
        if element.kind in {"caption", "note"}:
            continue

        relation_targets = child_targets.get(element.id, set())
        if element.parent_id is not None and relation_targets and element.parent_id not in relation_targets:
            collected_warnings.append(
                AssemblyWarning(
                    code="relation_conflict",
                    message="element.parent_id와 child_of 관계의 부모가 서로 다릅니다.",
                    level="warning",
                    page=element.page,
                    element_ids=[element.id],
                    metadata={
                        "relation_type": "child_of",
                        "parent_id": element.parent_id,
                        "relation_targets": sorted(relation_targets),
                    },
                )
            )

        if element.id in root_source_ids or relation_targets:
            continue
        orphan_by_page[element.page].append(element.id)

    for page, element_ids in sorted(orphan_by_page.items()):
        collected_warnings.append(
            AssemblyWarning(
                code="structure_orphan_block",
                message="구조 트리 어디에도 귀속되지 못한 block이 있습니다.",
                level="warning",
                page=page,
                element_ids=element_ids,
                metadata={"relation_type": "child_of"},
            )
        )

    return collected_warnings


def group_relations(
    block_relations: Sequence[BlockRelation],
) -> DefaultDict[str, List[BlockRelation]]:
    """관계 타입별로 relation을 묶는다."""
    grouped: DefaultDict[str, List[BlockRelation]] = defaultdict(list)
    for relation in block_relations:
        grouped[relation.type].append(relation)
    return grouped


def build_relation_targets(
    block_relations: Sequence[BlockRelation],
) -> DefaultDict[str, Set[str]]:
    """src 기준으로 도착 대상 집합을 만든다."""
    targets: DefaultDict[str, Set[str]] = defaultdict(set)
    for relation in block_relations:
        targets[relation.src].add(relation.dst)
    return targets


def collect_object_ids(
    table_refs: Sequence[TableRef],
    figure_refs: Sequence[FigureRef],
    note_refs: Sequence[NoteRef],
) -> Set[str]:
    """object ref id 집합을 만든다."""
    object_ids: Set[str] = set()
    object_ids.update(table_ref.table_id for table_ref in table_refs)
    object_ids.update(figure_ref.figure_id for figure_ref in figure_refs)
    object_ids.update(note_ref.note_id for note_ref in note_refs)
    return object_ids
