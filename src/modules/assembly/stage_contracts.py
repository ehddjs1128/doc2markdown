from __future__ import annotations

from typing import Any

from modules.assembly.ir import AssemblyResult
from modules.assembly.types import AssemblyStage


def require_assembly_result(value: Any, owner: str) -> AssemblyResult:
    if isinstance(value, AssemblyResult):
        return value
    raise TypeError(f"{owner} expects an AssemblyResult input.")


def require_stage(result: AssemblyResult, expected_stage: AssemblyStage, owner: str) -> None:
    actual_stage = result.metadata.stage
    if actual_stage != expected_stage:
        raise ValueError(
            f"{owner} expects AssemblyResult(stage={expected_stage!r}), "
            f"got stage={actual_stage!r}."
        )
