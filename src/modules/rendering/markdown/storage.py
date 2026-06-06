from __future__ import annotations

"""Markdown 렌더링 결과 저장 도우미."""

import json
from pathlib import Path

from modules.rendering.ir import MarkdownRenderResult
from modules.rendering.markdown.assets import rewrite_image_paths_for_output


def save_render_result(
    render_result: MarkdownRenderResult,
    output_dir: str | Path,
    markdown_file_name: str = "output.md",
    report_file_name: str = "render_report.json",
) -> dict[str, str]:
    """Markdown 본문과 렌더링 report를 output directory에 저장한다."""
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = resolved_output_dir / markdown_file_name
    report_path = resolved_output_dir / report_file_name

    markdown_text = rewrite_image_paths_for_output(
        markdown=render_result.markdown,
        markdown_path=markdown_path,
    )

    markdown_path.write_text(markdown_text, encoding="utf-8")
    report_path.write_text(
        json.dumps(render_result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "output_dir": str(resolved_output_dir),
        "markdown_path": str(markdown_path),
        "report_path": str(report_path),
    }
