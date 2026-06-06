from __future__ import annotations

"""Markdown 최종 공백 정리 도우미."""

from typing import Any


def finalize_markdown(markdown: str) -> tuple[str, dict[str, Any]]:
    """개행, 줄 끝 공백, 중복 빈 줄을 정리하고 cleanup 통계를 만든다."""
    if not markdown:
        return "", {
            "trimmed_trailing_whitespace_lines": 0,
            "collapsed_blank_lines": 0,
            "removed_edge_blank_lines": 0,
            "input_line_count": 0,
            "output_line_count": 0,
        }

    normalized_markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = normalized_markdown.split("\n")
    trimmed_trailing_whitespace_lines = sum(
        1 for line in raw_lines if line != line.rstrip()
    )
    stripped_lines = [line.rstrip() for line in raw_lines]

    collapsed_lines: list[str] = []
    collapsed_blank_lines = 0
    previous_blank = False
    for line in stripped_lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            collapsed_blank_lines += 1
            continue
        collapsed_lines.append(line)
        previous_blank = is_blank

    leading_blank_lines = 0
    while leading_blank_lines < len(collapsed_lines) and collapsed_lines[leading_blank_lines] == "":
        leading_blank_lines += 1

    trailing_blank_lines = 0
    while (
        trailing_blank_lines < len(collapsed_lines)
        and collapsed_lines[-(trailing_blank_lines + 1)] == ""
    ):
        trailing_blank_lines += 1

    if trailing_blank_lines > 0:
        cleaned_lines = collapsed_lines[leading_blank_lines:-trailing_blank_lines]
    else:
        cleaned_lines = collapsed_lines[leading_blank_lines:]

    cleaned = "\n".join(cleaned_lines)
    cleanup_report = {
        "trimmed_trailing_whitespace_lines": trimmed_trailing_whitespace_lines,
        "collapsed_blank_lines": collapsed_blank_lines,
        "removed_edge_blank_lines": leading_blank_lines + trailing_blank_lines,
        "input_line_count": len(raw_lines),
        "output_line_count": len(cleaned_lines),
    }
    return cleaned, cleanup_report
