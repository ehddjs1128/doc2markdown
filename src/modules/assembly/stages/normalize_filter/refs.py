from __future__ import annotations

"""Normalize/filter 결과를 document refs에 동기화한다."""

from dataclasses import replace
from typing import Dict, List

from modules.assembly.ir import AssemblyElement, FigureRef, NoteRef, TableRef


def sync_table_refs(
    table_refs: List[TableRef],
    element_map: Dict[str, AssemblyElement],
) -> List[TableRef]:
    """layout table element와 연결된 ref의 좌표/페이지를 다시 맞춘다."""
    synced_refs: List[TableRef] = []
    for table_ref in table_refs:
        source_element = element_map.get(table_ref.table_id)
        if source_element is None:
            synced_refs.append(table_ref)
            continue

        synced_refs.append(
            replace(
                table_ref,
                page=source_element.page,
                bbox=source_element.bbox or table_ref.bbox,
                metadata={
                    **dict(table_ref.metadata),
                    "normalized_from_element": True,
                },
            )
        )
    return synced_refs


def sync_figure_refs(
    figure_refs: List[FigureRef],
    element_map: Dict[str, AssemblyElement],
) -> List[FigureRef]:
    """figure ref도 element 정규화 결과와 좌표를 맞춘다."""
    synced_refs: List[FigureRef] = []
    for figure_ref in figure_refs:
        source_element = element_map.get(figure_ref.figure_id)
        if source_element is None:
            synced_refs.append(figure_ref)
            continue

        synced_refs.append(
            replace(
                figure_ref,
                page=source_element.page,
                bbox=source_element.bbox or figure_ref.bbox,
                metadata={
                    **dict(figure_ref.metadata),
                    "normalized_from_element": True,
                },
            )
        )
    return synced_refs


def sync_note_refs(
    note_refs: List[NoteRef],
    element_map: Dict[str, AssemblyElement],
) -> List[NoteRef]:
    """note ref는 정규화된 text를 반영해 뒤 단계가 바로 쓰게 한다."""
    synced_refs: List[NoteRef] = []
    for note_ref in note_refs:
        source_element = element_map.get(note_ref.note_id)
        if source_element is None:
            synced_refs.append(note_ref)
            continue

        synced_refs.append(
            replace(
                note_ref,
                page=source_element.page,
                bbox=source_element.bbox or note_ref.bbox,
                text=source_element.text or note_ref.text,
                metadata={
                    **dict(note_ref.metadata),
                    "normalized_from_element": True,
                },
            )
        )
    return synced_refs

