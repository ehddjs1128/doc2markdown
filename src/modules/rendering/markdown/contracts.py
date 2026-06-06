from __future__ import annotations

"""Markdown 렌더링 입력 계약 도우미."""

from collections.abc import Mapping
from typing import Any

from modules.assembly.ir import AssemblyResult
from modules.assembly.serialization import assembly_result_from_dict


def normalize_render_input(value: AssemblyResult | dict[str, Any]) -> AssemblyResult:
    """Renderer 입력을 AssemblyResult로 정규화한다."""
    if isinstance(value, AssemblyResult):
        return value

    if isinstance(value, Mapping):
        return assembly_result_from_dict(value)

    raise TypeError(
        "MarkdownRenderer는 AssemblyResult(stage='validated') 또는 직렬화 dict만 받습니다."
    )


def require_validated_assembly(result: AssemblyResult) -> None:
    """Markdown 렌더링 입력이 validated AssemblyResult인지 확인한다."""
    stage = result.metadata.stage if result.metadata is not None else None
    if stage != "validated":
        raise ValueError(
            "MarkdownRenderer는 AssemblyResult(stage='validated') 또는 직렬화 dict만 받습니다. "
            f"현재 stage={stage!r}"
        )
