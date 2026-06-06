from __future__ import annotations

"""Markdown 렌더링 공개 service."""

from pathlib import Path
from typing import Any

from modules.assembly.ir import AssemblyResult
from modules.rendering.ir import MarkdownRenderResult, RenderWarning
from modules.rendering.markdown.contracts import (
    normalize_render_input,
    require_validated_assembly,
)
from modules.rendering.markdown.renderer import render_markdown_body
from modules.rendering.markdown.stats import build_markdown_render_stats
from modules.rendering.markdown.storage import save_render_result


class MarkdownRenderer:
    """
    Rendering 단계의 공개 service.

    입력 계약 확인, Markdown 본문 렌더링, 통계 조립, 저장 흐름만 담당한다.
    """

    @staticmethod
    def render(assembly_result: AssemblyResult | dict[str, Any]) -> MarkdownRenderResult:
        """입력 계약을 검증하고 document.children 기반 Markdown 결과를 만든다."""
        normalized_result = normalize_render_input(assembly_result)
        require_validated_assembly(normalized_result)

        body_result = render_markdown_body(normalized_result)
        stats = build_markdown_render_stats(
            result=normalized_result,
            warnings=body_result.warnings,
            rendered_block_count=body_result.rendered_block_count,
            cleanup_report=body_result.cleanup_report,
        )
        return MarkdownRenderResult(
            markdown=body_result.markdown,
            warnings=body_result.warnings,
            stats=stats,
        )

    @staticmethod
    def save(
        render_result: MarkdownRenderResult,
        output_dir: str | Path,
        markdown_file_name: str = "output.md",
        report_file_name: str = "render_report.json",
    ) -> dict[str, str]:
        """렌더링 결과를 문서 output 폴더에 저장한다."""
        saved_paths = save_render_result(
            render_result=render_result,
            output_dir=output_dir,
            markdown_file_name=markdown_file_name,
            report_file_name=report_file_name,
        )
        _print_render_summary(render_result, saved_paths)
        return saved_paths


def _print_render_summary(
    render_result: MarkdownRenderResult,
    saved_paths: dict[str, str],
) -> None:
    stats = render_result.stats
    print(
        "[Rendering] Markdown rendering completed: "
        f"rendered_blocks={stats.rendered_block_count}, "
        f"markdown_chars={len(render_result.markdown)}, "
        f"warnings={stats.warning_count}, "
        f"placeholders={stats.placeholder_count}, "
        f"table_fallbacks={stats.table_fallback_count}"
    )
    print(f"[Rendering] └─ markdown_path={saved_paths.get('markdown_path')}")
    print(f"[Rendering] └─ report_path={saved_paths.get('report_path')}")

    warning_code_counts = _summarize_warning_codes(render_result.warnings)
    if warning_code_counts:
        print(f"[Rendering][Warning] warning_code_counts={warning_code_counts}")


def _summarize_warning_codes(warnings: list[RenderWarning]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for warning in warnings:
        summary[warning.code] = summary.get(warning.code, 0) + 1
    return summary
