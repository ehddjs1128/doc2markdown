from __future__ import annotations

"""Markdown 본문 렌더링 흐름."""

from dataclasses import dataclass, field
from typing import Any

from modules.assembly.ir import (
    AssemblyResult,
    FigureRef,
    ListGroup,
    NoteRef,
    ParagraphGroup,
    SectionNode,
    TableRef,
)
from modules.rendering.ir import RenderWarning
from modules.rendering.markdown.cleanup import finalize_markdown
from modules.rendering.markdown.context import build_render_context
from modules.rendering.markdown.nodes import render_document_nodes
from modules.rendering.markdown.text import normalize_body_text, normalize_single_line_text


@dataclass
class MarkdownBodyRenderResult:
    markdown: str = ""
    warnings: list[RenderWarning] = field(default_factory=list)
    cleanup_report: dict[str, Any] = field(default_factory=dict)
    rendered_block_count: int = 0


def render_markdown_body(result: AssemblyResult) -> MarkdownBodyRenderResult:
    """validated AssemblyResult의 document.children를 Markdown 본문으로 렌더링한다."""
    warnings: list[RenderWarning] = []
    render_context = build_render_context(result)
    blocks = render_document_nodes(
        nodes=result.document.children,
        warnings=warnings,
        render_context=render_context,
    )
    markdown, cleanup_report = finalize_markdown("\n\n".join(blocks))

    return MarkdownBodyRenderResult(
        markdown=markdown,
        warnings=warnings,
        cleanup_report=cleanup_report,
        rendered_block_count=count_renderable_blocks(result.document.children),
    )


def count_renderable_blocks(nodes: list[Any]) -> int:
    """현재 Markdown 렌더러가 실제 출력할 수 있는 block 개수를 센다."""
    count = 0

    for node in nodes:
        if isinstance(node, SectionNode):
            title = normalize_single_line_text(node.title)
            count += 1 if title else 0
            count += count_renderable_blocks(node.children)
            continue

        if isinstance(node, ParagraphGroup):
            count += 1 if normalize_body_text(node.text) else 0
            continue

        if isinstance(node, ListGroup):
            if any(normalize_body_text(item.text) for item in node.items):
                count += 1
            continue

        if isinstance(node, TableRef):
            count += 1
            continue

        if isinstance(node, FigureRef):
            count += 1
            continue

        if isinstance(node, NoteRef):
            text = normalize_body_text(node.text)
            count += 1 if text else 0

    return count
