from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def estimate_detection_region(frame: np.ndarray, prediction_result: dict[str, Any]) -> dict[str, int | str]:
    height, width = frame.shape[:2]
    return {
        "x": 0,
        "y": 0,
        "width": int(width),
        "height": int(height),
        "note": "Location: detected in current frame. Bounding box requires detection model.",
    }


def draw_detection_overlay(frame: np.ndarray, prediction_result: dict[str, Any], level: str) -> np.ndarray:
    output = frame.copy()
    region = estimate_detection_region(output, prediction_result)
    color = (0, 0, 255)
    thickness = 4 if str(level).upper() in {"DANGER", "HIGH", "CRITICAL"} else 2
    cv2.rectangle(
        output,
        (int(region["x"]), int(region["y"])),
        (int(region["width"]) - 1, int(region["height"]) - 1),
        color,
        thickness,
    )
    label = "Dangerous animal detected in frame"
    cv2.rectangle(output, (0, 0), (min(output.shape[1], 430), 42), color, -1)
    cv2.putText(
        output,
        label,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return output
