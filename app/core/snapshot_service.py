from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core.detection_localizer import draw_detection_overlay
from app.utils.image_utils import safe_filename_part
from app.utils.paths import SNAPSHOTS_DIR, relative_to_project
from app.utils.time_utils import file_timestamp


class SnapshotService:
    def __init__(self, output_dir: Path = SNAPSHOTS_DIR) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        frame: np.ndarray,
        animal: str,
        confidence: float,
        source_type: str,
        prediction: dict | None = None,
    ) -> str:
        if frame is None:
            return ""
        if prediction:
            frame = draw_detection_overlay(frame, prediction, "DANGER")
        self._draw_snapshot_header(frame, animal, confidence, source_type)
        animal_part = safe_filename_part(animal)
        source_part = safe_filename_part(source_type or "source")
        filename = f"{file_timestamp()}_{source_part}_{animal_part}_{confidence:.2f}.jpg"
        path = self.output_dir / filename
        ok = cv2.imwrite(str(path), frame)
        if not ok:
            raise IOError(f"Failed to save alert snapshot: {path}")
        return relative_to_project(path)

    def _draw_snapshot_header(self, frame: np.ndarray, animal: str, confidence: float, source_type: str) -> None:
        text = f"DANGER | {animal} {confidence:.0%} | {source_type} | AI Wildlife Monitoring System"
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 52), (0, 0, 180), -1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
        cv2.putText(frame, text, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (255, 255, 255), 2, cv2.LINE_AA)
