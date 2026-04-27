from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.utils.logging_utils import get_logger
from app.utils.paths import DETECTION_CONFIG_PATH, load_json


DEFAULT_DETECTION_CONFIG = {
    "yolo_model": "yolov8n.pt",
    "yolo_confidence": 0.25,
    "max_detections_per_frame": 5,
    "animal_like_classes": ["bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"],
}


@dataclass(frozen=True)
class YoloDetection:
    bbox: dict[str, int]
    label: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {"bbox": self.bbox, "label": self.label, "confidence": self.confidence}


class YoloDetector:
    def __init__(self, model_name: str | None = None) -> None:
        config = self.load_config()
        self.model_name = model_name or str(config.get("yolo_model", "yolov8n.pt"))
        self.confidence = float(config.get("yolo_confidence", 0.25))
        self.max_detections = int(config.get("max_detections_per_frame", 5))
        self.animal_like_classes = {str(name).casefold() for name in config.get("animal_like_classes", [])}
        self._model: Any | None = None
        self.logger = get_logger("wildlife.yolo", "detection.log")

    @staticmethod
    def load_config() -> dict[str, Any]:
        loaded = load_json(DETECTION_CONFIG_PATH, {})
        config = DEFAULT_DETECTION_CONFIG.copy()
        if isinstance(loaded, dict):
            config.update(loaded)
        return config

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError("Ultralytics is required for YOLO detection. Run: pip install ultralytics") from exc
        self._model = YOLO(self.model_name)
        self.logger.info("YOLO model loaded: %s", self.model_name)

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        self.load()
        results = self._model.predict(frame, conf=self.confidence, verbose=False)
        detections: list[dict[str, Any]] = []
        if not results:
            return detections

        result = results[0]
        names = getattr(result, "names", {}) or getattr(self._model, "names", {})
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections

        for box in boxes:
            class_id = int(box.cls[0])
            label = self._class_name(names, class_id)
            if label.casefold() not in self.animal_like_classes:
                continue
            xyxy = box.xyxy[0].detach().cpu().numpy().astype(int).tolist()
            x1, y1, x2, y2 = xyxy
            confidence = float(box.conf[0])
            detections.append(
                YoloDetection(
                    bbox={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    label=label,
                    confidence=confidence,
                ).as_dict()
            )
            if len(detections) >= self.max_detections:
                break

        self.logger.info("YOLO detections: %s", [{"label": d["label"], "confidence": round(d["confidence"], 3)} for d in detections])
        return detections

    def _class_name(self, names: Any, class_id: int) -> str:
        if isinstance(names, dict):
            return str(names.get(class_id, class_id))
        if isinstance(names, list) and 0 <= class_id < len(names):
            return str(names[class_id])
        return str(class_id)
