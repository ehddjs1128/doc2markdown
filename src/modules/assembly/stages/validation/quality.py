from __future__ import annotations

"""Validation 단계의 품질 신호 검증."""

from collections import defaultdict
from typing import DefaultDict, List, Sequence

from modules.assembly.ir import AssemblyElement, AssemblyWarning
from modules.assembly.stages.normalize_filter.policy import LOW_CONF_THRESHOLD


def validate_low_confidence_chunks(
    ordered_elements: Sequence[AssemblyElement],
) -> List[AssemblyWarning]:
    """필터링 후에도 남은 저신뢰 block를 info 수준으로 남긴다."""
    low_confidence_by_page: DefaultDict[int, List[str]] = defaultdict(list)

    for element in ordered_elements:
        if element.confidence is None or element.confidence >= LOW_CONF_THRESHOLD:
            continue
        low_confidence_by_page[element.page].append(element.id)

    collected_warnings: List[AssemblyWarning] = []
    for page, element_ids in sorted(low_confidence_by_page.items()):
        collected_warnings.append(
            AssemblyWarning(
                code="low_confidence_chunk",
                message="후속 검토가 필요한 저신뢰 block이 남아 있습니다.",
                level="info",
                page=page,
                element_ids=element_ids,
                metadata={"threshold": LOW_CONF_THRESHOLD},
            )
        )

    return collected_warnings

