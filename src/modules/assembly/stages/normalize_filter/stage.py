from __future__ import annotations

"""Assembly Normalize / Filter 단계."""

from collections import defaultdict
from dataclasses import replace
from typing import Any, DefaultDict, Dict, List, Optional

from modules.assembly.common.values import normalize_text
from modules.assembly.ir import (
    AssemblyElement,
    AssemblyMeta,
    AssemblyResult,
    AssembledDocument,
)
from modules.assembly.stages.contracts import require_assembly_result, require_stage
from modules.assembly.stages.normalize_filter import margin, page_stats, policy, refs


class NormalizeFilter:
    """adapter seed 결과를 reading order 직전 상태로 정리한다."""

    TOP_ZONE_RATIO = policy.TOP_ZONE_RATIO
    BOTTOM_ZONE_RATIO = policy.BOTTOM_ZONE_RATIO
    LOW_CONF_THRESHOLD = policy.LOW_CONF_THRESHOLD
    LOW_CONF_SHORT_TEXT_MAX = policy.LOW_CONF_SHORT_TEXT_MAX
    REPEATED_MARGIN_MIN_PAGES = policy.REPEATED_MARGIN_MIN_PAGES
    REPEATED_MARGIN_PAGE_RATIO = policy.REPEATED_MARGIN_PAGE_RATIO

    TEXT_REQUIRED_KINDS = policy.TEXT_REQUIRED_KINDS
    OBJECT_LIKE_KINDS = policy.OBJECT_LIKE_KINDS
    LINE_HEIGHT_KINDS = policy.LINE_HEIGHT_KINDS
    BODY_TEXT_KINDS = policy.BODY_TEXT_KINDS
    PAGE_NUMBER_PATTERN = policy.PAGE_NUMBER_PATTERN
    NON_CONTENT_PATTERN = policy.NON_CONTENT_PATTERN

    @classmethod
    def apply(cls, result: AssemblyResult) -> AssemblyResult:
        """adapter seed 결과를 정규화하고 필터링한다."""
        result = require_assembly_result(result, cls.__name__)
        require_stage(result, "adapter_seed", cls.__name__)

        page_dimensions = page_stats.build_page_dimensions(
            result.page_stats,
            result.ordered_elements,
        )
        repeated_margin_roles = margin.detect_repeated_margin_roles(
            result.ordered_elements,
            page_dimensions,
        )

        normalized_elements: List[AssemblyElement] = []
        filtered_by_reason: DefaultDict[str, List[str]] = defaultdict(list)

        for element in result.ordered_elements:
            normalized_element, filter_reason = cls._normalize_element(
                element,
                repeated_margin_roles,
                page_dimensions,
            )
            if normalized_element is None:
                filtered_by_reason[filter_reason or "unknown"].append(element.id)
                continue
            normalized_elements.append(normalized_element)

        element_map = {element.id: element for element in normalized_elements}
        normalized_page_stats = page_stats.normalize_page_stats(
            result.page_stats,
            normalized_elements,
            page_dimensions,
        )

        title_candidate, title_source_block_ids = page_stats.infer_title_candidate(normalized_elements)
        if title_candidate is None:
            title_candidate = result.document.title_candidate
            title_source_block_ids = list(result.document.title_source_block_ids)

        normalization_summary = cls._build_normalization_summary(
            input_count=len(result.ordered_elements),
            output_count=len(normalized_elements),
            filtered_by_reason=dict(filtered_by_reason),
        )

        normalized_document = AssembledDocument(
            title_candidate=title_candidate,
            title_source_block_ids=title_source_block_ids,
            children=list(result.document.children),
            sections=list(result.document.sections),
            table_refs=refs.sync_table_refs(result.document.table_refs, element_map),
            figure_refs=refs.sync_figure_refs(result.document.figure_refs, element_map),
            note_refs=refs.sync_note_refs(result.document.note_refs, element_map),
            figure_assets_metadata=dict(result.document.figure_assets_metadata),
            metadata={
                **dict(result.document.metadata),
                "normalize_filter": normalization_summary,
            },
            raw=result.document.raw,
        )

        return AssemblyResult(
            ordered_elements=normalized_elements,
            block_relations=list(result.block_relations),
            document=normalized_document,
            page_stats=normalized_page_stats,
            warnings=list(result.warnings),
            metadata=cls._build_normalized_metadata(result.metadata, normalization_summary),
            raw=result.raw,
        )

    @classmethod
    def _normalize_element(
        cls,
        element: AssemblyElement,
        repeated_margin_roles: Dict[str, str],
        page_dimensions: Dict[int, Dict[str, float]],
    ) -> tuple[Optional[AssemblyElement], Optional[str]]:
        """개별 element를 정규화하고 제외 여부를 판정한다."""
        metadata = dict(element.metadata)
        normalized_text = normalize_text(element.text)
        if normalized_text != element.text:
            metadata["text_normalized"] = True

        explicit_role = margin.detect_explicit_margin_role(
            element,
            normalized_text,
            page_dimensions,
        )
        repeated_role = repeated_margin_roles.get(element.id)
        filter_role = explicit_role or repeated_role
        if filter_role is not None:
            metadata["normalized_role"] = filter_role
            metadata["excluded_from_reading_order"] = True
            return None, filter_role

        if element.kind == "noise":
            metadata["excluded_from_reading_order"] = True
            return None, "upstream_noise"

        if element.kind in cls.TEXT_REQUIRED_KINDS and normalized_text is None:
            metadata["excluded_from_reading_order"] = True
            return None, "empty_text"

        if policy.should_filter_low_confidence_noise(
            kind=element.kind,
            text=normalized_text,
            confidence=element.confidence,
        ):
            metadata["excluded_from_reading_order"] = True
            metadata["normalized_role"] = "noise"
            return None, "low_confidence_noise"

        return replace(
            element,
            text=normalized_text,
            metadata=metadata,
        ), None

    @classmethod
    def _build_normalization_summary(
        cls,
        input_count: int,
        output_count: int,
        filtered_by_reason: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """문서 metadata와 result metadata에 함께 남길 요약을 만든다."""
        filtered_counts = {
            reason: len(element_ids)
            for reason, element_ids in filtered_by_reason.items()
            if element_ids
        }
        filtered_ids = {
            reason: element_ids
            for reason, element_ids in filtered_by_reason.items()
            if element_ids
        }

        return {
            "input_element_count": input_count,
            "output_element_count": output_count,
            "filtered_count": input_count - output_count,
            "filtered_counts": filtered_counts,
            "filtered_element_ids": filtered_ids,
        }

    @classmethod
    def _build_normalized_metadata(
        cls,
        previous_metadata: AssemblyMeta,
        normalization_summary: Dict[str, Any],
    ) -> AssemblyMeta:
        """이전 메타데이터를 보존하면서 stage만 normalized로 갱신한다."""
        details = dict(previous_metadata.details)
        details["upstream_stage"] = previous_metadata.stage
        details["normalize_filter"] = normalization_summary

        return AssemblyMeta(
            stage="normalized",
            adapter=previous_metadata.adapter,
            source=previous_metadata.source,
            details=details,
        )
