from __future__ import annotations

"""Markdown 렌더링 통계 도우미."""

from typing import Any

from modules.assembly.ir import AssemblyResult
from modules.rendering.ir import RenderStats, RenderWarning


SUPPORTED_NODE_TYPES = [
    "section",
    "paragraph_group",
    "list_group",
    "table_ref",
    "figure_ref",
    "note_ref",
]


def build_markdown_render_stats(
    result: AssemblyResult,
    warnings: list[RenderWarning],
    rendered_block_count: int,
    cleanup_report: dict[str, Any],
) -> RenderStats:
    """Markdown 렌더링 결과에 포함할 통계 payload를 만든다."""
    placeholder_count = sum(
        1
        for warning in warnings
        if warning.code in {"table_placeholder", "figure_placeholder"}
    )
    table_fallback_count = sum(
        1
        for warning in warnings
        if warning.code == "table_crop_fallback"
    )

    return RenderStats(
        input_stage=result.metadata.stage,
        ordered_element_count=len(result.ordered_elements),
        root_child_count=len(result.document.children),
        section_count=len(result.document.sections),
        table_ref_count=len(result.document.table_refs),
        figure_ref_count=len(result.document.figure_refs),
        note_ref_count=len(result.document.note_refs),
        warning_count=len(warnings),
        placeholder_count=placeholder_count,
        table_fallback_count=table_fallback_count,
        rendered_block_count=rendered_block_count,
        metadata={
            "renderer_contract_fixed": True,
            "used_document_children": True,
            "supported_node_types": list(SUPPORTED_NODE_TYPES),
            "document_title_candidate": result.document.title_candidate,
            "render_report": {
                "cleanup": cleanup_report,
                "placeholder_count": placeholder_count,
                "table_fallback_count": table_fallback_count,
                "warning_code_counts": summarize_warning_codes(warnings),
            },
        },
    )


def summarize_warning_codes(warnings: list[RenderWarning]) -> dict[str, int]:
    """warning code별 개수를 요약한다."""
    summary: dict[str, int] = {}
    for warning in warnings:
        summary[warning.code] = summary.get(warning.code, 0) + 1
    return summary
