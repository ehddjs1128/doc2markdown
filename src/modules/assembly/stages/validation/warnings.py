from __future__ import annotations

"""Validation warning 병합과 요약."""

import json
from typing import Any, Dict, Optional, Sequence, Set, Tuple

from modules.assembly.ir import AssemblyElement, AssemblyMeta, AssemblyResult, AssemblyWarning


def first_known_page(
    ordered_elements: Sequence[AssemblyElement],
    element_ids: Sequence[str],
) -> Optional[int]:
    """주어진 element id 목록에서 가장 먼저 찾는 page를 반환한다."""
    pages_by_id = {element.id: element.page for element in ordered_elements}
    for element_id in element_ids:
        page = pages_by_id.get(element_id)
        if page is not None:
            return page
    return None


def merge_warnings(
    existing_warnings: Sequence[AssemblyWarning],
    added_warnings: Sequence[AssemblyWarning],
) -> list[AssemblyWarning]:
    """기존 warning에 새 warning을 붙이되 중복은 한 번만 남긴다."""
    merged: list[AssemblyWarning] = []
    seen_keys: Set[Tuple[Any, ...]] = set()

    for warning in list(existing_warnings) + list(added_warnings):
        warning_key = (
            warning.level,
            warning.code,
            warning.page,
            tuple(warning.element_ids),
            warning.message,
            json.dumps(warning.metadata, ensure_ascii=False, sort_keys=True),
        )
        if warning_key in seen_keys:
            continue
        seen_keys.add(warning_key)
        merged.append(warning)

    return merged


def build_validation_summary(
    result: AssemblyResult,
    input_warning_count: int,
    added_warnings: Sequence[AssemblyWarning],
    output_warnings: Sequence[AssemblyWarning],
    section_count: int,
) -> Dict[str, Any]:
    """검증 단계 요약을 metadata에 남긴다."""
    return {
        "input_warning_count": input_warning_count,
        "added_warning_count": len(added_warnings),
        "output_warning_count": len(output_warnings),
        "added_warning_counts": count_warnings_by_code(added_warnings),
        "warning_counts": count_warnings_by_code(output_warnings),
        "warning_level_counts": count_warnings_by_level(output_warnings),
        "element_count": len(result.ordered_elements),
        "section_count": section_count,
        "root_child_count": len(result.document.children),
        "table_ref_count": len(result.document.table_refs),
        "figure_ref_count": len(result.document.figure_refs),
        "note_ref_count": len(result.document.note_refs),
    }


def count_warnings_by_code(warnings: Sequence[AssemblyWarning]) -> Dict[str, int]:
    """warning code별 개수를 센다."""
    counts: Dict[str, int] = {}
    for warning in warnings:
        counts[warning.code] = counts.get(warning.code, 0) + 1
    return counts


def count_warnings_by_level(warnings: Sequence[AssemblyWarning]) -> Dict[str, int]:
    """warning level별 개수를 센다."""
    counts: Dict[str, int] = {}
    for warning in warnings:
        counts[warning.level] = counts.get(warning.level, 0) + 1
    return counts


def build_validated_metadata(
    previous_metadata: AssemblyMeta,
    validation_summary: Dict[str, Any],
) -> AssemblyMeta:
    """이전 메타데이터를 보존하면서 validated stage를 기록한다."""
    details = dict(previous_metadata.details)
    details["upstream_stage"] = previous_metadata.stage
    details["validation"] = validation_summary

    return AssemblyMeta(
        stage="validated",
        adapter=previous_metadata.adapter,
        source=previous_metadata.source,
        details=details,
    )

