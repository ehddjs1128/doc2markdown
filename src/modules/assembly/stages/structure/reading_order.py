from __future__ import annotations

"""Step 2. Reading Order Resolution과 next relation 생성."""

from dataclasses import replace
from typing import List

from modules.assembly.ir import AssemblyElement, BlockRelation
from modules.assembly.stages.structure import heuristics


def ensure_reading_order(elements: List[AssemblyElement]) -> List[AssemblyElement]:
    """upstream이 정한 순서를 유지하면서 reading_order 필드를 채운다."""
    if not elements:
        return []

    if all(element.reading_order is not None for element in elements):
        ordered_elements = sorted(
            elements,
            key=lambda element: (
                element.reading_order,
                element.page,
                heuristics.bbox_top(element),
                heuristics.bbox_left(element),
                element.id,
            ),
        )
    else:
        ordered_elements = list(elements)

    materialized_elements: List[AssemblyElement] = []
    for index, element in enumerate(ordered_elements, start=1):
        if element.reading_order is not None:
            materialized_elements.append(element)
            continue

        metadata = dict(element.metadata)
        metadata["reading_order_source"] = "upstream_sequence"
        materialized_elements.append(
            replace(
                element,
                reading_order=index,
                metadata=metadata,
            )
        )

    return materialized_elements


def build_next_relations(ordered_elements: List[AssemblyElement]) -> List[BlockRelation]:
    """인접 ordered element를 next relation으로 연결한다."""
    next_relations: List[BlockRelation] = []
    for current, following in zip(ordered_elements, ordered_elements[1:]):
        next_relations.append(
            BlockRelation(
                type="next",
                src=current.id,
                dst=following.id,
                score=1.0,
                metadata={
                    "page": current.page,
                    "same_page": current.page == following.page,
                    "reading_order": (current.reading_order, following.reading_order),
                },
            )
        )
    return next_relations


def merge_next_relations(
    existing_relations: List[BlockRelation],
    next_relations: List[BlockRelation],
) -> List[BlockRelation]:
    """기존 next relation을 새 reading order 기준 relation으로 대체한다."""
    merged_relations = [
        relation
        for relation in existing_relations
        if relation.type != "next"
    ]
    merged_relations.extend(next_relations)
    return merged_relations
