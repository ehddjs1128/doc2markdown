from __future__ import annotations

"""Markdown 이미지 경로 처리 도우미."""

import os
from pathlib import Path
import re


def normalize_asset_path(path: str) -> str:
    """Markdown 이미지 경로에 맞게 경로 구분자를 정리한다."""
    return path.replace("\\", "/").strip()


def rewrite_image_paths_for_output(markdown: str, markdown_path: Path) -> str:
    """저장될 Markdown 파일 위치를 기준으로 이미지 경로를 다시 쓴다."""
    if not markdown:
        return ""

    def replace_image_path(match: re.Match[str]) -> str:
        alt_text = match.group("alt")
        original_path = match.group("path")
        rewritten_path = to_markdown_relative_path(
            asset_path=original_path,
            markdown_path=markdown_path,
        )
        return f"![{alt_text}]({rewritten_path})"

    return re.sub(
        r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)",
        replace_image_path,
        markdown,
    )


def to_markdown_relative_path(asset_path: str, markdown_path: Path) -> str:
    """asset 경로를 저장될 Markdown 파일 기준 상대 경로로 바꾼다."""
    normalized_asset_path = asset_path.strip().replace("\\", "/")
    if not normalized_asset_path:
        return normalized_asset_path

    if re.match(r"^(?:[a-z]+:)?//", normalized_asset_path, re.IGNORECASE):
        return normalized_asset_path

    asset_path_obj = Path(normalized_asset_path)
    if asset_path_obj.is_absolute():
        target_path = asset_path_obj
    else:
        target_path = Path.cwd() / asset_path_obj
        if not target_path.exists():
            src_relative_target_path = Path.cwd() / "src" / asset_path_obj
            if src_relative_target_path.exists():
                target_path = src_relative_target_path

    markdown_parent = markdown_path.parent.resolve()
    final_relative_path = Path(
        os.path.relpath(
            Path(target_path).resolve(),
            markdown_parent,
        )
    )
    return final_relative_path.as_posix()
