from __future__ import annotations

"""Assembly Validator 단계."""

from dataclasses import replace
from typing import List

from modules.assembly.ir import AssemblyResult, AssemblyWarning
from modules.assembly.stages.contracts import require_assembly_result, require_stage
from modules.assembly.stages.validation import context, document, links, quality, relations
from modules.assembly.stages.validation import warnings as warning_helpers


class AssemblyValidator:
    """structure 결과를 최종 점검하고 warning을 남긴다."""

    GEOMETRY_REQUIRED_KINDS = document.GEOMETRY_REQUIRED_KINDS

    @classmethod
    def apply(cls, result: AssemblyResult) -> AssemblyResult:
        """구조 조립 결과를 검증하고 `validated` stage로 마감한다."""
        result = require_assembly_result(result, cls.__name__)
        require_stage(result, "structure_assembled", cls.__name__)

        added_warnings = cls._collect_validation_warnings(result)
        merged_warnings = warning_helpers.merge_warnings(result.warnings, added_warnings)
        validation_summary = warning_helpers.build_validation_summary(
            result=result,
            input_warning_count=len(result.warnings),
            added_warnings=added_warnings,
            output_warnings=merged_warnings,
            section_count=len(list(document.iter_sections(result.document.sections))),
        )

        document_metadata = dict(result.document.metadata)
        document_metadata["validation"] = validation_summary

        return AssemblyResult(
            ordered_elements=list(result.ordered_elements),
            block_relations=list(result.block_relations),
            document=replace(
                result.document,
                metadata=document_metadata,
            ),
            page_stats=list(result.page_stats),
            warnings=merged_warnings,
            metadata=warning_helpers.build_validated_metadata(result.metadata, validation_summary),
            raw=result.raw,
        )

    @classmethod
    def _collect_validation_warnings(cls, result: AssemblyResult) -> List[AssemblyWarning]:
        """현재 구조 IR에서 파생되는 warning을 수집한다."""
        validation_context = context.build_context(result)

        collected_warnings: List[AssemblyWarning] = []
        collected_warnings.extend(
            relations.validate_next_relations(
                ordered_elements=result.ordered_elements,
                next_relations=validation_context.relations_by_type["next"],
            )
        )
        collected_warnings.extend(
            relations.validate_child_relations(
                ordered_elements=result.ordered_elements,
                child_relations=validation_context.relations_by_type["child_of"],
                root_source_ids=validation_context.root_source_ids,
            )
        )
        collected_warnings.extend(
            links.validate_caption_links(
                ordered_elements=result.ordered_elements,
                table_refs=validation_context.table_refs,
                figure_refs=validation_context.figure_refs,
                caption_relations=validation_context.relations_by_type["caption_of"],
                object_ids=validation_context.object_ids,
            )
        )
        collected_warnings.extend(
            links.validate_note_links(
                ordered_elements=result.ordered_elements,
                table_refs=validation_context.table_refs,
                note_refs=validation_context.note_refs,
                note_relations=validation_context.relations_by_type["note_of"],
                object_ids=validation_context.object_ids,
                elements_by_id=validation_context.elements_by_id,
            )
        )
        collected_warnings.extend(
            links.validate_object_refs(
                table_refs=validation_context.table_refs,
                figure_refs=validation_context.figure_refs,
                elements_by_id=validation_context.elements_by_id,
                caption_relations=validation_context.relations_by_type["caption_of"],
                note_relations=validation_context.relations_by_type["note_of"],
            )
        )
        collected_warnings.extend(document.validate_sections(result.document.sections))
        collected_warnings.extend(
            document.validate_geometry(
                ordered_elements=result.ordered_elements,
                table_refs=validation_context.table_refs,
                figure_refs=validation_context.figure_refs,
                note_refs=validation_context.note_refs,
            )
        )
        collected_warnings.extend(quality.validate_low_confidence_chunks(result.ordered_elements))
        return collected_warnings
