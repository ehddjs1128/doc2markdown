from __future__ import annotations

"""Markdown 렌더링용 텍스트 정규화 도우미."""

import re
from typing import Any

from modules.assembly.ir import ListGroupItem


def normalize_heading_level(level: Any) -> int:
    """heading level을 Markdown에서 안전한 범위로 정규화한다."""
    if not isinstance(level, int):
        return 1
    return max(1, min(level, 4))


def extract_indent_level(item: ListGroupItem) -> int:
    """list item metadata에서 안전한 indent level을 읽어 온다."""
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    indent_level = metadata.get("indent_level", 0)
    if not isinstance(indent_level, int):
        return 0
    return max(0, indent_level)


def normalize_single_line_text(value: Any) -> str:
    """heading과 caption처럼 한 줄로 출력할 텍스트를 정리한다."""
    if not isinstance(value, str):
        return ""

    lines = [
        line.strip()
        for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    compact = " ".join(line for line in lines if line)
    return compact.strip()


def normalize_body_text(value: Any) -> str:
    """본문 텍스트를 정리하고 Markdown block syntax 오인을 막는다."""
    normalized = normalize_single_line_text(value)
    return escape_leading_markdown_syntax(normalized)


def escape_leading_markdown_syntax(text: str) -> str:
    """본문 text가 Markdown block syntax로 해석되지 않도록 최소 escaping을 적용한다."""
    if not text:
        return ""

    if text.startswith("\\"):
        return text

    if text.startswith(("#", ">")):
        return f"\\{text}"

    if re.fullmatch(r"(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}", text):
        return f"\\{text}"

    return text


def render_list_item_lines(text: str, marker: str, indent_level: int) -> list[str]:
    """list item 하나를 Markdown line 목록으로 렌더링한다."""
    indent = "  " * max(0, indent_level)
    continuation_indent = f"{indent}  "
    text_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not text_lines:
        return []

    rendered_lines = [f"{indent}{marker} {text_lines[0]}"]
    rendered_lines.extend(f"{continuation_indent}{line}" for line in text_lines[1:])
    return rendered_lines
