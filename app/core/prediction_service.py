from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.utils.paths import ANIMAL_INFO_PATH, CLASS_NAMES_PATH, MODEL_PATH, load_json


def _normalize_name(name: str) -> str:
    return " ".join(str(name).replace("_", " ").split()).casefold()


@dataclass(frozen=True)
class PredictionResult:
    label: str
    confidence: float
    top_predictions: list[dict[str, float | str]]
    animal_info: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "top_predictions": self.top_predictions,
            "animal_info": self.animal_info,
        }


class PredictionService:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        class_names_path: Path = CLASS_NAMES_PATH,
        animal_info_path: Path = ANIMAL_INFO_PATH,
    ) -> None:
        self.model_path = model_path
        self.class_names_path = class_names_path
        self.animal_info_path = animal_info_path
        self._model: Any | None = None
        self._class_names: list[str] | None = None
        self._animal_info_index: dict[str, dict[str, Any]] | None = None

    @property
    def class_names(self) -> list[str]:
        if self._class_names is None:
            self._class_names = self._load_class_names()
        return self._class_names

    def load(self) -> None:
        if self._model is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model not found: {self.model_path}")
            from tensorflow.keras.models import load_model

            self._model = load_model(str(self.model_path))
        _ = self.class_names
        if self._animal_info_index is None:
            self._animal_info_index = self._load_animal_info()

    def _load_class_names(self) -> list[str]:
        payload = load_json(self.class_names_path, {})
        if isinstance(payload, dict) and isinstance(payload.get("class_names"), list):
            return [str(name) for name in payload["class_names"]]
        if isinstance(payload, list):
            return [str(name) for name in payload]
        if isinstance(payload, dict):
            ordered = sorted(payload.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]))
            return [str(name) for _, name in ordered]
        raise ValueError(f"Unsupported class names format: {self.class_names_path}")

    def _load_animal_info(self) -> dict[str, dict[str, Any]]:
        payload = load_json(self.animal_info_path, {})
        rows = payload.get("animals", []) if isinstance(payload, dict) else payload
        index: dict[str, dict[str, Any]] = {}
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name", "")).strip()
                if name:
                    index[_normalize_name(name)] = row.get("details", row)
        return index

    def input_size(self) -> tuple[int, int]:
        self.load()
        shape = getattr(self._model, "input_shape", None)
        if isinstance(shape, list):
            shape = shape[0]
        if isinstance(shape, tuple) and len(shape) >= 4:
            height = int(shape[1] or 224)
            width = int(shape[2] or 224)
            return width, height
        return 224, 224

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        width, height = self.input_size()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_AREA)
        normalized = resized.astype("float32") / 255.0
        return np.expand_dims(normalized, axis=0)

    def predict_frame(self, frame: np.ndarray) -> dict[str, Any]:
        self.load()
        tensor = self.preprocess_frame(frame)
        raw_output = self._model.predict(tensor, verbose=0)
        if isinstance(raw_output, list):
            raw_output = raw_output[0]
        scores = np.asarray(raw_output).reshape(-1)
        if scores.size == 0:
            raise ValueError("Model returned an empty prediction vector")

        class_names = self.class_names
        usable_count = min(len(class_names), scores.size)
        usable_scores = scores[:usable_count]
        top_indices = np.argsort(usable_scores)[::-1][:5]

        top_predictions = [
            {"label": class_names[index], "confidence": float(usable_scores[index])}
            for index in top_indices
        ]
        best_index = int(top_indices[0])
        label = class_names[best_index]
        confidence = float(usable_scores[best_index])
        animal_info = (self._animal_info_index or {}).get(_normalize_name(label), {})

        return PredictionResult(label, confidence, top_predictions, animal_info).as_dict()

