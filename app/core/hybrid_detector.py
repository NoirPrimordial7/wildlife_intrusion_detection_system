from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.core.label_normalizer import display_label, normalize_key, normalize_label
from app.core.prediction_service import PredictionService
from app.core.yolo_detector import YoloDetector
from app.utils.logging_utils import get_logger
from app.utils.paths import DETECTION_CONFIG_PATH, load_json


DEFAULT_HYBRID_CONFIG = {
    "mode": "hybrid",
    "classifier_confidence": 0.60,
    "crop_padding": 0.15,
    "hide_low_confidence_classifier_labels": True,
    "minimum_display_confidence": 0.50,
    "prefer_yolo_label_for_non_dangerous_low_confidence": True,
    "dangerous_classifier_override_confidence": 0.65,
}


class HybridDetector:
    def __init__(
        self,
        classifier: PredictionService,
        yolo_detector: YoloDetector | None = None,
    ) -> None:
        self.classifier = classifier
        self.yolo_detector = yolo_detector or YoloDetector()
        self.config = self.load_config()
        self.classifier_confidence = float(self.config.get("classifier_confidence", 0.60))
        self.crop_padding = float(self.config.get("crop_padding", 0.15))
        self.hide_low_confidence_classifier_labels = bool(self.config.get("hide_low_confidence_classifier_labels", True))
        self.minimum_display_confidence = float(self.config.get("minimum_display_confidence", 0.50))
        self.prefer_yolo_for_low_confidence = bool(self.config.get("prefer_yolo_label_for_non_dangerous_low_confidence", True))
        self.dangerous_classifier_override_confidence = float(self.config.get("dangerous_classifier_override_confidence", 0.65))
        self.yolo_display_labels = {
            normalize_key(label)
            for label in self.config.get("animal_like_classes", [])
            if isinstance(label, str)
        }
        self.logger = get_logger("wildlife.hybrid", "detection.log")
        self.dangerous_animals = {
            "tiger",
            "leopard",
            "lion",
            "bear",
            "brown bear",
            "polar bear",
            "elephant",
            "wolf",
            "hyena",
            "crocodile",
            "snake",
            "boar",
            "rhinoceros",
            "hippopotamus",
        }

    @staticmethod
    def load_config() -> dict[str, Any]:
        loaded = load_json(DETECTION_CONFIG_PATH, {})
        config = DEFAULT_HYBRID_CONFIG.copy()
        if isinstance(loaded, dict):
            config.update(loaded)
        return config

    def predict_frame(self, frame: np.ndarray) -> dict[str, Any]:
        started_at = time.perf_counter()
        detections: list[dict[str, Any]] = []
        yolo_error = ""

        try:
            yolo_detections = self.yolo_detector.detect(frame)
        except Exception as exc:
            yolo_detections = []
            yolo_error = str(exc)
            self.logger.error("YOLO detection failed: %s", yolo_error)

        for yolo_detection in yolo_detections:
            crop = self._crop_with_padding(frame, yolo_detection["bbox"])
            classifier_prediction = self.classifier.predict_frame(crop)
            raw_classifier_label = str(classifier_prediction.get("label", "Unknown"))
            normalized_classifier_label = normalize_label(raw_classifier_label)
            classifier_confidence = float(classifier_prediction.get("confidence", 0.0))
            yolo_label = display_label(str(yolo_detection.get("label", "Unknown")))
            yolo_confidence = float(yolo_detection.get("confidence", 0.0))
            dangerous_classifier_override = (
                self.is_dangerous(normalized_classifier_label)
                and classifier_confidence >= self.dangerous_classifier_override_confidence
            )

            prefer_yolo_for_demo = (
                self.prefer_yolo_for_low_confidence
                and not dangerous_classifier_override
                and not self.is_dangerous(normalized_classifier_label)
                and normalize_key(normalized_classifier_label) not in self.yolo_display_labels
                and yolo_confidence >= self.minimum_display_confidence
            )

            if (classifier_confidence >= self.classifier_confidence or dangerous_classifier_override) and not prefer_yolo_for_demo:
                final_label = normalized_classifier_label
                final_confidence = classifier_confidence
                label_source = "classifier_danger_override" if dangerous_classifier_override else "classifier"
            else:
                final_label = yolo_label
                final_confidence = yolo_confidence
                label_source = "yolo_demo_filter" if prefer_yolo_for_demo else "yolo"

            normalized_final_label = normalize_label(final_label)
            display = self._display_label_for_detection(
                yolo_label=yolo_label,
                normalized_classifier_label=normalized_classifier_label,
                classifier_confidence=classifier_confidence,
                final_label=normalized_final_label,
                final_confidence=final_confidence,
                label_source=label_source,
            )
            detections.append(
                {
                    "bbox": yolo_detection["bbox"],
                    "yolo_label": yolo_label,
                    "yolo_confidence": yolo_confidence,
                    "raw_classifier_label": raw_classifier_label,
                    "classifier_label": normalized_classifier_label,
                    "normalized_classifier_label": normalized_classifier_label,
                    "classifier_confidence": classifier_confidence,
                    "final_label": normalized_final_label,
                    "display_label": display,
                    "final_confidence": final_confidence,
                    "label_source": label_source,
                    "is_dangerous": self.is_dangerous(normalized_final_label),
                }
            )

        processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if detections:
            for detection in detections:
                detection["processing_time_ms"] = processing_time_ms
            primary = self._primary_detection(detections)
            result = {
                "label": primary["display_label"],
                "display_label": primary["display_label"],
                "final_label": primary["final_label"],
                "confidence": primary["final_confidence"],
                "top_predictions": self._top_predictions(detections),
                "animal_info": {},
                "bbox": primary.get("bbox"),
                "detections": detections,
                "processing_time_ms": processing_time_ms,
                "detector_mode": "hybrid_yolo_classifier",
            }
        else:
            fallback = self.classifier.predict_frame(frame)
            raw_label = str(fallback.get("label", "Unknown"))
            normalized = normalize_label(raw_label)
            fallback["raw_classifier_label"] = raw_label
            fallback["normalized_classifier_label"] = normalized
            if yolo_error:
                fallback["label"] = normalized
                fallback["display_label"] = normalized
                fallback["final_label"] = normalized
            else:
                fallback["label"] = "No animal detected"
                fallback["display_label"] = "No animal detected"
                fallback["final_label"] = "No animal detected"
                fallback["confidence"] = 0.0
            fallback["detections"] = []
            fallback["bbox"] = None
            fallback["processing_time_ms"] = processing_time_ms
            fallback["detector_mode"] = "classifier_fallback"
            if yolo_error:
                fallback["yolo_error"] = yolo_error
            result = fallback

        self.logger.info(
            "Hybrid result: label=%s confidence=%.3f detections=%s mode=%s",
            result.get("label"),
            float(result.get("confidence", 0.0)),
            len(result.get("detections", [])),
            result.get("detector_mode"),
        )
        return result

    def is_dangerous(self, label: str) -> bool:
        return normalize_key(label) in self.dangerous_animals

    def _display_label_for_detection(
        self,
        yolo_label: str,
        normalized_classifier_label: str,
        classifier_confidence: float,
        final_label: str,
        final_confidence: float,
        label_source: str,
    ) -> str:
        if (
            self.hide_low_confidence_classifier_labels
            and label_source == "classifier"
            and classifier_confidence < self.minimum_display_confidence
        ):
            return yolo_label
        if (
            self.prefer_yolo_for_low_confidence
            and not self.is_dangerous(normalized_classifier_label)
            and classifier_confidence < self.classifier_confidence
        ):
            return yolo_label
        if final_confidence < self.minimum_display_confidence:
            return yolo_label
        return display_label(final_label)

    def _crop_with_padding(self, frame: np.ndarray, bbox: dict[str, int]) -> np.ndarray:
        height, width = frame.shape[:2]
        x1 = int(bbox.get("x1", 0))
        y1 = int(bbox.get("y1", 0))
        x2 = int(bbox.get("x2", width))
        y2 = int(bbox.get("y2", height))
        pad_x = int(max(0, x2 - x1) * self.crop_padding)
        pad_y = int(max(0, y2 - y1) * self.crop_padding)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(width, x2 + pad_x)
        y2 = min(height, y2 + pad_y)
        if x2 <= x1 or y2 <= y1:
            return frame
        return frame[y1:y2, x1:x2]

    def _primary_detection(self, detections: list[dict[str, Any]]) -> dict[str, Any]:
        dangerous = [d for d in detections if d.get("is_dangerous")]
        candidates = dangerous or detections
        return max(candidates, key=lambda item: float(item.get("final_confidence", 0.0)))

    def _top_predictions(self, detections: list[dict[str, Any]]) -> list[dict[str, float | str]]:
        ordered = sorted(detections, key=lambda item: float(item.get("final_confidence", 0.0)), reverse=True)
        return [
            {"label": str(item.get("display_label", item.get("final_label", "Unknown"))), "confidence": float(item.get("final_confidence", 0.0))}
            for item in ordered[:5]
        ]
