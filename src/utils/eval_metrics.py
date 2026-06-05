from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence


def heading_precision_recall_f1(predicted_ids: Iterable[str], expected_ids: Iterable[str]) -> dict[str, float]:
    predicted = set(predicted_ids)
    expected = set(expected_ids)
    true_positive = len(predicted & expected)

    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def heading_level_accuracy(
    predicted_levels: Mapping[str, int | None],
    expected_levels: Mapping[str, int | None],
) -> float:
    comparable_ids = [
        block_id
        for block_id, predicted_level in predicted_levels.items()
        if predicted_level is not None and block_id in expected_levels
    ]
    if not comparable_ids:
        return 0.0

    correct = sum(
        1
        for block_id in comparable_ids
        if predicted_levels[block_id] == expected_levels[block_id]
    )
    return correct / len(comparable_ids)


def non_space_preservation_rate(original: str, repaired: str) -> float:
    original_signature = _non_space_signature(original)
    repaired_signature = _non_space_signature(repaired)
    if not original_signature and not repaired_signature:
        return 1.0
    if not original_signature or not repaired_signature:
        return 0.0
    return _lcs_length(original_signature, repaired_signature) / len(original_signature)


def spacing_edit_distance(original: str, repaired: str) -> int:
    return _levenshtein_distance(original, repaired)


def warning_count_delta(
    baseline_warnings: Sequence[Mapping[str, object]],
    candidate_warnings: Sequence[Mapping[str, object]],
    *,
    codes: Iterable[str] | None = None,
) -> dict[str, int]:
    baseline_counts = _warning_code_counts(baseline_warnings)
    candidate_counts = _warning_code_counts(candidate_warnings)
    selected_codes = set(codes or baseline_counts.keys() | candidate_counts.keys())
    return {
        code: candidate_counts.get(code, 0) - baseline_counts.get(code, 0)
        for code in sorted(selected_codes)
    }


def _warning_code_counts(warnings: Sequence[Mapping[str, object]]) -> Counter[str]:
    return Counter(
        str(warning["code"])
        for warning in warnings
        if warning.get("code") is not None
    )


def _non_space_signature(text: str) -> str:
    return "".join(str(text).split())


def _lcs_length(left: str, right: str) -> int:
    previous = [0] * (len(right) + 1)
    for left_char in left:
        current = [0]
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _levenshtein_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]
