from __future__ import annotations

"""Assembly 전체에서 쓰는 bbox/geometry helper."""

from typing import Any, Optional

from modules.assembly.common.values import normalize_float
from modules.assembly.types import BBox


def normalize_bbox(value: Any) -> Optional[BBox]:
    if value is None:
        return None
    if isinstance(value, dict):
        if {"x1", "y1", "x2", "y2"}.issubset(value.keys()):
            coords = [value["x1"], value["y1"], value["x2"], value["y2"]]
        elif {"left", "top", "right", "bottom"}.issubset(value.keys()):
            coords = [value["left"], value["top"], value["right"], value["bottom"]]
        elif {"x", "y", "width", "height"}.issubset(value.keys()):
            x = normalize_float(value["x"])
            y = normalize_float(value["y"])
            width = normalize_float(value["width"])
            height = normalize_float(value["height"])
            if None in (x, y, width, height):
                return None
            coords = [x, y, x + width, y + height]
        else:
            return None
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        coords = list(value)
    else:
        return None
    normalized = [normalize_float(item) for item in coords]
    if any(item is None for item in normalized):
        return None
    return normalized[0], normalized[1], normalized[2], normalized[3]


def bbox_iou(left: Optional[BBox], right: Optional[BBox]) -> Optional[float]:
    if left is None or right is None:
        return None
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    inter_x1 = max(left_x1, right_x1)
    inter_y1 = max(left_y1, right_y1)
    inter_x2 = min(left_x2, right_x2)
    inter_y2 = min(left_y2, right_y2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    left_area = max(0.0, (left_x2 - left_x1) * (left_y2 - left_y1))
    right_area = max(0.0, (right_x2 - right_x1) * (right_y2 - right_y1))
    union = left_area + right_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union
