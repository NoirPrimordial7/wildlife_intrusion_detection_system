from __future__ import annotations

import threading
import time
from typing import Any, Callable

import cv2

from app.core.prediction_service import PredictionService


FrameCallback = Callable[[Any, dict[str, Any]], None]
PredictionCallback = Callable[[dict[str, Any], Any, dict[str, Any]], None]
ErrorCallback = Callable[[str], None]


class CameraService:
    def __init__(
        self,
        prediction_service: PredictionService,
        frame_callback: FrameCallback,
        prediction_callback: PredictionCallback,
        error_callback: ErrorCallback,
    ) -> None:
        self.prediction_service = prediction_service
        self.frame_callback = frame_callback
        self.prediction_callback = prediction_callback
        self.error_callback = error_callback
        self.prediction_interval_seconds = 1.0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, camera_index: int = 0, prediction_interval_seconds: float | None = None) -> None:
        if self._running:
            return
        if prediction_interval_seconds is not None:
            self.prediction_interval_seconds = max(0.25, float(prediction_interval_seconds))
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(camera_index,), daemon=True)
        self._thread.start()

    def stop(self, wait: bool = False) -> None:
        self._stop_event.set()
        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self, camera_index: int) -> None:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.error_callback(f"Could not open webcam index {camera_index}")
            self._running = False
            return

        self._running = True
        last_prediction_at = 0.0
        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.error_callback("Webcam frame could not be read")
                    break

                metadata = {"source_type": "webcam", "source_path": f"camera:{camera_index}"}
                self.frame_callback(frame.copy(), metadata)

                now = time.monotonic()
                if now - last_prediction_at >= self.prediction_interval_seconds:
                    last_prediction_at = now
                    try:
                        prediction = self.prediction_service.predict_frame(frame.copy())
                        self.prediction_callback(prediction, frame.copy(), metadata)
                    except Exception as exc:
                        self.error_callback(f"Prediction failed: {exc}")

                time.sleep(0.01)
        finally:
            cap.release()
            self._running = False

