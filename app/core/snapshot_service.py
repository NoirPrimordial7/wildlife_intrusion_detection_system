from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.utils.image_utils import safe_filename_part
from app.utils.paths import ALERTS_DIR, relative_to_project
from app.utils.time_utils import file_timestamp


class SnapshotService:
    def __init__(self, output_dir: Path = ALERTS_DIR) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, frame: np.ndarray, animal: str, confidence: float, source_type: str) -> str:
        if frame is None:
            return ""
        animal_part = safe_filename_part(animal)
        source_part = safe_filename_part(source_type or "source")
        filename = f"{file_timestamp()}_{source_part}_{animal_part}_{confidence:.2f}.jpg"
        path = self.output_dir / filename
        ok = cv2.imwrite(str(path), frame)
        if not ok:
            raise IOError(f"Failed to save alert snapshot: {path}")
        return relative_to_project(path)

