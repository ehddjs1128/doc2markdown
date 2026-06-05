from __future__ import annotations

"""문서 assembly의 공개 orchestration 진입점을 제공한다."""

from typing import Any

from modules.assembly.adapters import from_outputs as adapter_from_outputs
from modules.assembly.adapters import from_raw as adapter_from_raw
from modules.assembly.ir import AssemblyResult
from modules.assembly.normalize_filter import NormalizeFilter
from modules.assembly.stage_contracts import require_assembly_result, require_stage
from modules.assembly.structure import StructureAssembler
from modules.assembly.validator import AssemblyValidator


class DocumentAssembler:
    """공개 raw 입력을 assembly 단계 흐름으로 연결한다."""

    def build(self, raw: Any) -> AssemblyResult:
        """raw 또는 이미 조립된 입력에서 validated AssemblyResult를 만든다."""
        if isinstance(raw, AssemblyResult) and raw.metadata.stage == "validated":
            return raw
        return self.validate(self.build_structure(raw))

    @staticmethod
    def build_seed(raw: Any) -> AssemblyResult:
        """공개 raw payload를 adapter_seed AssemblyResult로 바꾼다."""
        if isinstance(raw, AssemblyResult):
            return raw
        return adapter_from_raw(raw)

    @staticmethod
    def build_seed_from_outputs(layout_output: Any, table_output: Any = None) -> AssemblyResult:
        """명시적인 layout/table 출력을 adapter_seed AssemblyResult로 바꾼다."""
        return adapter_from_outputs(layout_output, table_output)

    def build_normalized(self, raw: Any) -> AssemblyResult:
        """공개 raw payload에서 normalized AssemblyResult를 만들거나 그대로 돌려준다."""
        seed_result = self.build_seed(raw)
        if seed_result.metadata.stage == "normalized":
            return seed_result
        return self.normalize(seed_result)

    def build_structure(self, raw: Any) -> AssemblyResult:
        """공개 raw payload에서 structure_assembled AssemblyResult를 만들거나 그대로 돌려준다."""
        if isinstance(raw, AssemblyResult) and raw.metadata.stage == "structure_assembled":
            return raw
        normalized_result = self.build_normalized(raw)
        return self.assemble_structure(normalized_result)

    def build_from_outputs(self, layout_output: Any, table_output: Any = None) -> AssemblyResult:
        """명시적인 layout/table 출력에서 validated AssemblyResult를 만든다."""
        return self.build(self.build_seed_from_outputs(layout_output, table_output))

    @staticmethod
    def normalize(seed_result: AssemblyResult) -> AssemblyResult:
        """엄격한 adapter_seed 입력에서 normalized 단계를 실행한다."""
        seed_result = require_assembly_result(seed_result, "DocumentAssembler.normalize")
        require_stage(seed_result, "adapter_seed", "DocumentAssembler.normalize")
        return NormalizeFilter.apply(seed_result)

    @staticmethod
    def assemble_structure(normalized_result: AssemblyResult) -> AssemblyResult:
        """엄격한 normalized 입력에서 structure assembly를 실행한다."""
        normalized_result = require_assembly_result(
            normalized_result,
            "DocumentAssembler.assemble_structure",
        )
        require_stage(normalized_result, "normalized", "DocumentAssembler.assemble_structure")
        return StructureAssembler.apply(normalized_result)

    @staticmethod
    def validate(structure_result: AssemblyResult) -> AssemblyResult:
        """엄격한 structure_assembled 결과를 최종 assembly 단계로 검증한다."""
        structure_result = require_assembly_result(structure_result, "DocumentAssembler.validate")
        require_stage(structure_result, "structure_assembled", "DocumentAssembler.validate")
        return AssemblyValidator.apply(structure_result)
