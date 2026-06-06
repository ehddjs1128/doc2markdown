from __future__ import annotations

"""조립된 문서 노드별 Markdown 렌더링."""

from typing import Any

from modules.assembly.ir import (
    FigureRef,
    ListGroup,
    NoteRef,
    ParagraphGroup,
    SectionNode,
    TableRef,
)
from modules.rendering.ir import RenderWarning
from modules.rendering.markdown.assets import normalize_asset_path
from modules.rendering.markdown.context import RenderContext
from modules.rendering.markdown.text import (
    extract_indent_level,
    normalize_body_text,
    normalize_heading_level,
    normalize_single_line_text,
    render_list_item_lines,
)


def render_document_nodes(
    nodes: list[Any],
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> list[str]:
    """document.children 순서를 유지하며 Markdown block 목록을 만든다."""
    rendered_blocks: list[str] = []

    for node in nodes:
        rendered = render_document_node(
            node=node,
            warnings=warnings,
            render_context=render_context,
        )
        if rendered:
            rendered_blocks.append(rendered)

    return rendered_blocks


def render_document_node(
    node: Any,
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> str:
    """조립 노드 타입에 맞는 Markdown 렌더러를 호출한다."""
    if isinstance(node, SectionNode):
        return render_section(node, warnings, render_context)

    if isinstance(node, ParagraphGroup):
        return render_paragraph(node, warnings)

    if isinstance(node, ListGroup):
        return render_list(node, warnings)

    if isinstance(node, TableRef):
        return render_table(node, warnings, render_context)

    if isinstance(node, FigureRef):
        return render_figure(node, warnings, render_context)

    if isinstance(node, NoteRef):
        return render_note(node, warnings, render_context)

    node_type = getattr(node, "type", type(node).__name__)
    node_id = (
        getattr(node, "id", None)
        or getattr(node, "table_id", None)
        or getattr(node, "figure_id", None)
        or getattr(node, "note_id", None)
    )
    warnings.append(
        RenderWarning(
            code="unsupported_node_type",
            message=f"현재 단계에서는 {node_type!r} 노드 렌더링을 지원하지 않습니다.",
            node_id=node_id,
            metadata={"node_type": node_type},
        )
    )
    return ""


def render_section(
    section: SectionNode,
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> str:
    """section 노드를 heading과 child block 묶음으로 렌더링한다."""
    title = normalize_single_line_text(section.title)
    blocks: list[str] = []

    if title:
        level = normalize_heading_level(section.level)
        blocks.append(f"{'#' * level} {title}")
    else:
        warnings.append(
            RenderWarning(
                code="empty_heading",
                message="section title이 비어 있어 heading 출력은 생략합니다.",
                node_id=section.id,
                metadata={"level": section.level},
            )
        )

    child_blocks = render_document_nodes(
        nodes=section.children,
        warnings=warnings,
        render_context=render_context,
    )
    blocks.extend(child_blocks)
    return "\n\n".join(blocks).strip()


def render_paragraph(
    paragraph: ParagraphGroup,
    warnings: list[RenderWarning],
) -> str:
    """paragraph_group을 일반 Markdown 문단으로 렌더링한다."""
    text = normalize_body_text(paragraph.text)
    if text:
        return text

    warnings.append(
        RenderWarning(
            code="empty_paragraph",
            message="paragraph_group text가 비어 있어 출력하지 않습니다.",
            node_id=paragraph.id,
            metadata={"block_ids": list(paragraph.block_ids)},
        )
    )
    return ""


def render_list(
    list_group: ListGroup,
    warnings: list[RenderWarning],
) -> str:
    """list_group을 ordered/unordered Markdown list로 렌더링한다."""
    ordered = bool(list_group.ordered)
    counters_by_level: dict[int, int] = {}
    lines: list[str] = []

    for item in list_group.items:
        item_text = normalize_body_text(item.text)
        if not item_text:
            warnings.append(
                RenderWarning(
                    code="empty_list_item",
                    message="list item text가 비어 있어 출력하지 않습니다.",
                    node_id=(item.block_ids[0] if item.block_ids else list_group.id),
                    metadata={"list_group_id": list_group.id},
                )
            )
            continue

        indent_level = extract_indent_level(item)
        counters_by_level = {
            level: count
            for level, count in counters_by_level.items()
            if level <= indent_level
        }
        counters_by_level[indent_level] = counters_by_level.get(indent_level, 0) + 1

        marker = f"{counters_by_level[indent_level]}." if ordered else "-"
        lines.extend(
            render_list_item_lines(
                text=item_text,
                marker=marker,
                indent_level=indent_level,
            )
        )

    return "\n".join(lines).strip()


def render_table(
    table_ref: TableRef,
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> str:
    """table_ref를 Markdown 표, 대체 이미지, 자리표시자 중 하나로 렌더링한다."""
    metadata = table_ref.metadata if isinstance(table_ref.metadata, dict) else {}
    markdown = metadata.get("markdown")
    crop_path = metadata.get("crop_path")
    caption_text = render_context.lookup_caption_text(table_ref.caption_id)
    caption_block = render_caption(caption_text)
    note_blocks = render_attached_notes(
        target_id=table_ref.table_id,
        preferred_note_ids=table_ref.note_ids,
        warnings=warnings,
        render_context=render_context,
    )

    if isinstance(markdown, str) and markdown.strip():
        blocks = [markdown.strip()]
        if caption_block:
            blocks.append(caption_block)
        blocks.extend(note_blocks)
        return "\n\n".join(blocks).strip()

    if isinstance(crop_path, str) and crop_path.strip():
        warnings.append(
            RenderWarning(
                code="table_crop_fallback",
                message="table markdown이 없어 crop_path 이미지를 대체 출력했습니다.",
                node_id=table_ref.table_id,
                metadata={
                    "table_id": table_ref.table_id,
                    "crop_path": crop_path,
                },
            )
        )
        blocks = [f"![Table {table_ref.table_id}]({normalize_asset_path(crop_path)})"]
        if caption_block:
            blocks.append(caption_block)
        blocks.extend(note_blocks)
        return "\n\n".join(blocks).strip()

    warnings.append(
        RenderWarning(
            code="table_placeholder",
            message="table markdown과 crop_path가 모두 없어 자리표시자를 출력했습니다.",
            node_id=table_ref.table_id,
            metadata={"table_id": table_ref.table_id},
        )
    )
    blocks = [f"[TABLE PLACEHOLDER: {table_ref.table_id}]"]
    if caption_block:
        blocks.append(caption_block)
    blocks.extend(note_blocks)
    return "\n\n".join(blocks).strip()


def render_figure(
    figure_ref: FigureRef,
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> str:
    """figure_ref를 이미지, caption, attached note 묶음으로 렌더링한다."""
    metadata = figure_ref.metadata if isinstance(figure_ref.metadata, dict) else {}
    asset_path = figure_ref.asset_path or metadata.get("crop_path")
    caption_text = render_context.lookup_caption_text(figure_ref.caption_id)
    caption_block = render_caption(caption_text)
    note_blocks = render_attached_notes(
        target_id=figure_ref.figure_id,
        preferred_note_ids=[],
        warnings=warnings,
        render_context=render_context,
    )

    if isinstance(asset_path, str) and asset_path.strip():
        blocks = [f"![Figure {figure_ref.figure_id}]({normalize_asset_path(asset_path)})"]
        if caption_block:
            blocks.append(caption_block)
        blocks.extend(note_blocks)
        return "\n\n".join(blocks).strip()

    warnings.append(
        RenderWarning(
            code="figure_placeholder",
            message="figure asset_path와 crop_path가 모두 없어 자리표시자를 출력했습니다.",
            node_id=figure_ref.figure_id,
            metadata={"figure_id": figure_ref.figure_id},
        )
    )
    blocks = [f"[FIGURE PLACEHOLDER: {figure_ref.figure_id}]"]
    if caption_block:
        blocks.append(caption_block)
    blocks.extend(note_blocks)
    return "\n\n".join(blocks).strip()


def render_note(
    note_ref: NoteRef,
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> str:
    """standalone note 또는 아직 출력되지 않은 attached note를 렌더링한다."""
    if render_context.has_rendered_note(note_ref.note_id):
        return ""

    text = normalize_body_text(note_ref.text)
    if not text:
        warnings.append(
            RenderWarning(
                code="empty_note",
                message="note text가 비어 있어 출력하지 않습니다.",
                node_id=note_ref.note_id,
                metadata={"target_id": note_ref.target_id},
            )
        )
        return ""

    render_context.mark_note_rendered(note_ref.note_id)
    if note_ref.target_id:
        return text.strip()
    return render_blockquote_note(text)


def render_caption(caption_text: str) -> str:
    """table과 figure caption을 공통 보조 텍스트 스타일로 렌더링한다."""
    if not caption_text:
        return ""
    return f"*{caption_text}*"


def render_attached_notes(
    target_id: str,
    preferred_note_ids: list[str],
    warnings: list[RenderWarning],
    render_context: RenderContext,
) -> list[str]:
    """object에 연결된 note들을 Markdown block 목록으로 렌더링한다."""
    attached_notes = render_context.resolve_attached_notes(
        target_id=target_id,
        preferred_note_ids=preferred_note_ids,
    )
    rendered_blocks: list[str] = []

    for note_ref in attached_notes:
        text = normalize_body_text(note_ref.text)
        if not text:
            warnings.append(
                RenderWarning(
                    code="empty_note",
                    message="attached note text가 비어 있어 출력하지 않습니다.",
                    node_id=note_ref.note_id,
                    metadata={"target_id": target_id},
                )
            )
            continue

        render_context.mark_note_rendered(note_ref.note_id)
        rendered_blocks.append(text.strip())

    return rendered_blocks


def render_blockquote_note(text: str) -> str:
    """standalone note를 Markdown blockquote 형식으로 렌더링한다."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(f"> {line}" for line in lines)
