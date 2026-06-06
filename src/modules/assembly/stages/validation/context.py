from __future__ import annotations

"""Validation 단계에서 반복 조회하는 문맥."""

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, List, Set

from modules.assembly.ir import AssemblyElement, AssemblyResult, BlockRelation, FigureRef, NoteRef, TableRef
from modules.assembly.stages.validation import document, relations


@dataclass(frozen=True)
class ValidationContext:
    elements_by_id: Dict[str, AssemblyElement]
    table_refs: List[TableRef]
    figure_refs: List[FigureRef]
    note_refs: List[NoteRef]
    object_ids: Set[str]
    root_source_ids: Set[str]
    relations_by_type: DefaultDict[str, List[BlockRelation]]


def build_context(result: AssemblyResult) -> ValidationContext:
    """검증 함수들이 공유할 lookup 문맥을 만든다."""
    table_refs = list(result.document.table_refs)
    figure_refs = list(result.document.figure_refs)
    note_refs = list(result.document.note_refs)
    return ValidationContext(
        elements_by_id={element.id: element for element in result.ordered_elements},
        table_refs=table_refs,
        figure_refs=figure_refs,
        note_refs=note_refs,
        object_ids=relations.collect_object_ids(table_refs, figure_refs, note_refs),
        root_source_ids=document.collect_source_ids_from_nodes(result.document.children),
        relations_by_type=relations.group_relations(result.block_relations),
    )

