from __future__ import annotations

"""문서 assembly의 공개 orchestration 진입점을 제공한다."""

import time
from dataclasses import dataclass
from typing import Any, Callable

from modules.assembly.adapters import from_outputs as adapter_from_outputs
from modules.assembly.adapters import from_raw as adapter_from_raw
from modules.assembly.ir import AssemblyResult
from modules.assembly.normalize_filter import NormalizeFilter
from modules.assembly.stage_contracts import require_assembly_result, require_stage
from modules.assembly.structure import StructureAssembler
from modules.assembly.validator import AssemblyValidator


@dataclass(frozen=True)
class AssemblyBuildTrace:
    result: AssemblyResult
    stages: dict[str, AssemblyResult]


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

    def build_from_outputs_with_trace(
        self,
        layout_output: Any,
        table_output: Any = None,
        *,
        semantic_enricher: Any = None,
        content_enricher: Any = None,
    ) -> AssemblyBuildTrace:
        """Build validated Assembly IR while retaining intermediate stage results."""
        semantic_enricher, content_enricher = self._resolve_enrichers(
            semantic_enricher=semantic_enricher,
            content_enricher=content_enricher,
        )

        stages: dict[str, AssemblyResult] = {}

        seed_result = self._run_stage(
            "adapter_seed",
            lambda: self.build_seed_from_outputs(layout_output, table_output),
        )
        stages["adapter_seed"] = seed_result

        normalized_result = self._run_stage(
            "NormalizeFilter",
            lambda: self.normalize(seed_result),
        )
        stages["normalized"] = normalized_result

        semantic_result = self._run_enrichment_stage(
            stage_key="semantic_enriched",
            label="SemanticEnricher",
            result=normalized_result,
            enricher=semantic_enricher,
            enabled_method_name="runs_semantic",
            stages=stages,
        )

        structure_result = self._run_stage(
            "StructureAssembler",
            lambda: self.assemble_structure(semantic_result),
        )
        stages["structure_assembled"] = structure_result

        content_result = self._run_enrichment_stage(
            stage_key="content_enriched",
            label="ContentEnricher",
            result=structure_result,
            enricher=content_enricher,
            enabled_method_name="runs_content",
            stages=stages,
        )

        validated_result = self._run_stage(
            "AssemblyValidator",
            lambda: self.validate(content_result),
        )
        stages["validated"] = validated_result

        return AssemblyBuildTrace(result=validated_result, stages=stages)

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

    @staticmethod
    def _resolve_enrichers(
        *,
        semantic_enricher: Any = None,
        content_enricher: Any = None,
    ) -> tuple[Any, Any]:
        if semantic_enricher is not None and content_enricher is not None:
            return semantic_enricher, content_enricher

        from modules.llm_core import LLMConfig
        from modules.llm_enrichment import ContentEnricher, SemanticEnricher

        config = LLMConfig.from_env()
        if semantic_enricher is None:
            semantic_enricher = SemanticEnricher(config=config)
        if content_enricher is None:
            content_enricher = ContentEnricher(config=config)
        return semantic_enricher, content_enricher

    def _run_enrichment_stage(
        self,
        *,
        stage_key: str,
        label: str,
        result: AssemblyResult,
        enricher: Any,
        enabled_method_name: str,
        stages: dict[str, AssemblyResult],
    ) -> AssemblyResult:
        if not self._is_enricher_enabled(enricher, enabled_method_name):
            mode = self._enricher_mode(enricher)
            print(f"[Assembly] {label} skipped: mode={mode}")
            return enricher.apply(result)

        enriched_result = self._run_stage(label, lambda: enricher.apply(result))
        stages[stage_key] = enriched_result
        return enriched_result

    @staticmethod
    def _is_enricher_enabled(enricher: Any, enabled_method_name: str) -> bool:
        config = getattr(enricher, "config", None)
        enabled_method = getattr(config, enabled_method_name, None)
        if callable(enabled_method):
            return bool(enabled_method())
        return True

    @staticmethod
    def _enricher_mode(enricher: Any) -> str:
        config = getattr(enricher, "config", None)
        return str(getattr(config, "mode", "unknown"))

    def _run_stage(self, label: str, action: Callable[[], AssemblyResult]) -> AssemblyResult:
        print(f"[Assembly] {label} start")
        started_at = time.perf_counter()
        result = action()
        self._print_stage_summary(label, result, started_at)
        return result

    @staticmethod
    def _print_stage_summary(label: str, result: AssemblyResult, started_at: float) -> None:
        elapsed = time.perf_counter() - started_at
        metadata = getattr(result, "metadata", None)
        stage = getattr(metadata, "stage", None) or "-"
        elements = getattr(result, "ordered_elements", []) or []
        warnings = getattr(result, "warnings", []) or []
        document = getattr(result, "document", None)

        print(
            f"[Assembly] {label} done: "
            f"stage={stage}, elements={len(elements)}, warnings={len(warnings)}, elapsed={elapsed:.2f}s"
        )
        if document is None:
            return

        children = getattr(document, "children", []) or []
        sections = getattr(document, "sections", []) or []
        table_refs = getattr(document, "table_refs", []) or []
        figure_refs = getattr(document, "figure_refs", []) or []
        print(
            f"[Assembly] {label} document: "
            f"children={len(children)}, sections={len(sections)}, "
            f"tables={len(table_refs)}, figures={len(figure_refs)}"
        )
