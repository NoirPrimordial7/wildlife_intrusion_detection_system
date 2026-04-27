from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.utils.paths import DETECTION_CONFIG_PATH, load_json


def estimate_detection_region(frame: np.ndarray, prediction_result: dict[str, Any]) -> dict[str, int | str]:
    height, width = frame.shape[:2]
    bbox = prediction_result.get("bbox")
    if not bbox and prediction_result.get("detections"):
        first = prediction_result["detections"][0]
        bbox = first.get("bbox") if isinstance(first, dict) else None
    if isinstance(bbox, dict):
        x1 = max(0, min(width - 1, int(bbox.get("x1", 0))))
        y1 = max(0, min(height - 1, int(bbox.get("y1", 0))))
        x2 = max(x1 + 1, min(width, int(bbox.get("x2", width))))
        y2 = max(y1 + 1, min(height, int(bbox.get("y2", height))))
        return {
            "x": x1,
            "y": y1,
            "width": int(x2 - x1),
            "height": int(y2 - y1),
            "note": "Location: YOLO bounding box around detected animal.",
        }
    return {
        "x": 0,
        "y": 0,
        "width": int(width),
        "height": int(height),
        "note": "Location: detected in current frame. Bounding box requires detection model.",
    }


def draw_detection_overlay(frame: np.ndarray, prediction_result: dict[str, Any], level: str) -> np.ndarray:
    output = frame.copy()
    config = load_json(DETECTION_CONFIG_PATH, {})
    if isinstance(config, dict) and not bool(config.get("draw_bounding_boxes", True)):
        return output
    thickness = max(3, int(config.get("box_thickness", 3) if isinstance(config, dict) else 3))
    draw_yolo = bool(config.get("draw_yolo_debug_label", True)) if isinstance(config, dict) else True
    detections = prediction_result.get("detections") if isinstance(prediction_result.get("detections"), list) else []
    if detections:
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            bbox = detection.get("bbox", {})
            x1 = int(bbox.get("x1", 0))
            y1 = int(bbox.get("y1", 0))
            x2 = int(bbox.get("x2", output.shape[1]))
            y2 = int(bbox.get("y2", output.shape[0]))
            label = str(detection.get("display_label", detection.get("final_label", detection.get("yolo_label", "animal"))))
            confidence = float(detection.get("final_confidence", detection.get("yolo_confidence", 0.0)))
            yolo_label = str(detection.get("yolo_label", "--"))
            yolo_conf = float(detection.get("yolo_confidence", 0.0))
            box_color = _box_color(detection, level)
            text = f"{label} {confidence:.0%}"
            if draw_yolo and yolo_label and yolo_label != "--":
                text = f"{text} | YOLO: {yolo_label} {yolo_conf:.0%}"
            _draw_box(output, x1, y1, x2, y2, text, box_color, thickness)
    else:
        region = estimate_detection_region(output, prediction_result)
        _draw_box(
            output,
            int(region["x"]),
            int(region["y"]),
            int(region["width"]) - 1,
            int(region["height"]) - 1,
            str(prediction_result.get("display_label", prediction_result.get("label", "Animal detected"))),
            (0, 165, 255),
            thickness,
        )
    return output


def _box_color(detection: dict[str, Any], level: str) -> tuple[int, int, int]:
    normalized_level = str(level).upper()
    if detection.get("is_dangerous") or normalized_level in {"DANGER", "HIGH", "CRITICAL"}:
        return (0, 0, 255)
    if normalized_level == "WARNING":
        return (0, 190, 255)
    return (255, 180, 0)


def _draw_box(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, label: str, color: tuple[int, int, int], thickness: int) -> None:
    height, width = frame.shape[:2]
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width - 1, x2))
    y2 = max(y1 + 1, min(height - 1, y2))
    shadow = (0, 0, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), shadow, thickness + 3)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
    text_w, text_h = text_size
    label_y1 = max(0, y1 - text_h - 10)
    label_x2 = min(width - 1, x1 + text_w + 12)
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, label_y1), (label_x2, y1), color, -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
    cv2.putText(frame, label, (x1 + 6, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
