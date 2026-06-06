from __future__ import annotations

"""Structure 단계의 CaptionLinker 역할.

table / figure와 caption / note를 연결하고, caption_of / note_of relation을 만든다.
"""

from dataclasses import replace
from typing import Any, Dict, List, Optional, Set

from modules.assembly.ir import (
    AssemblyElement,
    BlockRelation,
    FigureRef,
    NoteRef,
    PageStats,
    TableRef,
)
from modules.assembly.stages.structure import heuristics


def resolve_object_attachments(
    ordered_elements: List[AssemblyElement],
    element_map: Dict[str, AssemblyElement],
    table_refs: List[TableRef],
    figure_refs: List[FigureRef],
    note_refs: List[NoteRef],
    page_stats_by_page: Dict[int, PageStats],
) -> tuple[
    List[TableRef],
    List[FigureRef],
    List[NoteRef],
    Dict[str, str],
    Dict[str, str],
    Dict[str, Any],
]:
    """caption/note 연결을 기존 ref 우선으로 보정한다."""
    caption_elements = [element for element in ordered_elements if element.kind == "caption"]
    note_elements = [element for element in ordered_elements if element.kind == "note"]

    used_caption_ids: Set[str] = set()
    note_target_map: Dict[str, str] = {}
    caption_target_map: Dict[str, str] = {}

    updated_table_refs: List[TableRef] = []
    for table_ref in table_refs:
        page_stat = page_stats_by_page.get(table_ref.page)
        caption_id = table_ref.caption_id or find_caption_candidate(
            object_ref=table_ref,
            object_kind="table",
            candidates=caption_elements,
            used_caption_ids=used_caption_ids,
            page_stat=page_stat,
            element_map=element_map,
        )
        if caption_id is not None:
            used_caption_ids.add(caption_id)
            caption_target_map[caption_id] = table_ref.table_id

        merged_note_ids = list(table_ref.note_ids)
        for note_id in merged_note_ids:
            note_target_map[note_id] = table_ref.table_id

        if not merged_note_ids:
            merged_note_ids = find_note_candidates(
                object_ref=table_ref,
                candidates=note_elements,
                assigned_targets=note_target_map,
                page_stat=page_stat,
                element_map=element_map,
                anchor_element=element_map.get(caption_id) if caption_id else None,
            )
            for note_id in merged_note_ids:
                note_target_map[note_id] = table_ref.table_id

        updated_table_refs.append(
            replace(
                table_ref,
                caption_id=caption_id,
                note_ids=merged_note_ids,
                metadata={
                    **dict(table_ref.metadata),
                    "structure_attachment_checked": True,
                },
            )
        )

    updated_figure_refs: List[FigureRef] = []
    for figure_ref in figure_refs:
        page_stat = page_stats_by_page.get(figure_ref.page)
        caption_id = figure_ref.caption_id or find_caption_candidate(
            object_ref=figure_ref,
            object_kind="figure",
            candidates=caption_elements,
            used_caption_ids=used_caption_ids,
            page_stat=page_stat,
            element_map=element_map,
        )
        if caption_id is not None:
            used_caption_ids.add(caption_id)
            caption_target_map[caption_id] = figure_ref.figure_id

        updated_figure_refs.append(
            replace(
                figure_ref,
                caption_id=caption_id,
                metadata={
                    **dict(figure_ref.metadata),
                    "structure_attachment_checked": True,
                },
            )
        )

    updated_note_refs: List[NoteRef] = []
    for note_ref in note_refs:
        target_id = note_target_map.get(note_ref.note_id, note_ref.target_id)
        updated_note_refs.append(
            replace(
                note_ref,
                target_id=target_id,
                metadata={
                    **dict(note_ref.metadata),
                    "structure_attachment_checked": True,
                },
            )
        )

    attachment_summary = {
        "table_count": len(updated_table_refs),
        "figure_count": len(updated_figure_refs),
        "attached_caption_count": len(caption_target_map),
        "attached_note_count": len(note_target_map),
        "caption_target_map": dict(caption_target_map),
        "note_target_map": dict(note_target_map),
    }

    return (
        updated_table_refs,
        updated_figure_refs,
        updated_note_refs,
        caption_target_map,
        note_target_map,
        attachment_summary,
    )


def find_caption_candidate(
    object_ref: TableRef | FigureRef,
    object_kind: str,
    candidates: List[AssemblyElement],
    used_caption_ids: Set[str],
    page_stat: Optional[PageStats],
    element_map: Dict[str, AssemblyElement],
) -> Optional[str]:
    """object와 가장 가까운 caption block 하나를 보수적으로 연결한다."""
    threshold = heuristics.caption_threshold(page_stat)
    best_id: Optional[str] = None
    best_score: Optional[tuple[int, float]] = None

    for candidate in candidates:
        if candidate.id in used_caption_ids:
            continue
        if candidate.page != object_ref.page:
            continue
        if candidate.bbox is None or object_ref.bbox is None:
            continue
        if not heuristics.looks_like_caption_text(candidate.text, object_kind):
            continue
        if heuristics.horizontal_overlap_ratio(candidate.bbox, object_ref.bbox) < 0.30:
            continue

        position_rank, distance = heuristics.caption_distance(candidate.bbox, object_ref.bbox)
        if distance > threshold:
            continue

        score = (position_rank, distance)
        if best_score is None or score < best_score:
            best_score = score
            best_id = candidate.id

    if best_id is not None:
        return best_id

    explicit_id = getattr(object_ref, "caption_id", None)
    if explicit_id and explicit_id in element_map:
        return explicit_id
    return explicit_id


def find_note_candidates(
    object_ref: TableRef,
    candidates: List[AssemblyElement],
    assigned_targets: Dict[str, str],
    page_stat: Optional[PageStats],
    element_map: Dict[str, AssemblyElement],
    anchor_element: Optional[AssemblyElement],
) -> List[str]:
    """table 하단 note block을 짧은 거리 기준으로 연결한다."""
    if object_ref.bbox is None:
        return list(object_ref.note_ids)

    threshold = heuristics.note_threshold(page_stat)
    anchor_bbox = anchor_element.bbox if anchor_element and anchor_element.bbox is not None else object_ref.bbox
    best_candidates: List[tuple[float, str]] = []

    for candidate in candidates:
        if candidate.id in assigned_targets:
            continue
        if candidate.page != object_ref.page:
            continue
        if candidate.bbox is None:
            continue
        if not heuristics.looks_like_note_text(candidate.text):
            continue
        if heuristics.horizontal_overlap_ratio(candidate.bbox, object_ref.bbox) < 0.30:
            continue

        distance = candidate.bbox[1] - anchor_bbox[3]
        if distance < 0 or distance > threshold:
            continue
        best_candidates.append((distance, candidate.id))

    best_candidates.sort(key=lambda item: item[0])
    return [note_id for _, note_id in best_candidates]


def build_attachment_relations(
    table_refs: List[TableRef],
    figure_refs: List[FigureRef],
    note_target_map: Dict[str, str],
) -> List[BlockRelation]:
    """caption_of / note_of 관계를 edge로 만든다."""
    relations: List[BlockRelation] = []

    for table_ref in table_refs:
        if table_ref.caption_id:
            relations.append(
                BlockRelation(
                    type="caption_of",
                    src=table_ref.caption_id,
                    dst=table_ref.table_id,
                    score=1.0,
                    metadata={"source": "structure_attachment", "object_kind": "table"},
                )
            )
        for note_id in table_ref.note_ids:
            relations.append(
                BlockRelation(
                    type="note_of",
                    src=note_id,
                    dst=table_ref.table_id,
                    score=1.0,
                    metadata={"source": "structure_attachment", "object_kind": "table"},
                )
            )

    table_target_ids = {table_ref.table_id for table_ref in table_refs}
    for figure_ref in figure_refs:
        if figure_ref.caption_id:
            relations.append(
                BlockRelation(
                    type="caption_of",
                    src=figure_ref.caption_id,
                    dst=figure_ref.figure_id,
                    score=1.0,
                    metadata={"source": "structure_attachment", "object_kind": "figure"},
                )
            )

    for note_id, target_id in note_target_map.items():
        if target_id in table_target_ids:
            continue
        relations.append(
            BlockRelation(
                type="note_of",
                src=note_id,
                dst=target_id,
                score=1.0,
                metadata={"source": "structure_attachment", "object_kind": "figure"},
            )
        )

    return relations
