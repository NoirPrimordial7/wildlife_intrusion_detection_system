from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

import cv2

FrameCallback = Callable[[Any, dict[str, Any]], None]
PredictionCallback = Callable[[dict[str, Any], Any, dict[str, Any]], None]
ErrorCallback = Callable[[str], None]
StatusCallback = Callable[[dict[str, Any]], None]

RECONNECT_DELAY_SECONDS = 5.0
VALID_SOURCE_TYPES = {"webcam", "rtsp", "video"}


def _normalize_source_type(source_type: str) -> str:
    normalized = str(source_type or "webcam").strip().casefold()
    if normalized not in VALID_SOURCE_TYPES:
        raise ValueError(f"Unsupported camera source type: {source_type}")
    return normalized


def _webcam_index(source_path: Any) -> int:
    if source_path is None or source_path == "":
        return 0
    if isinstance(source_path, int):
        return source_path
    value = str(source_path).strip()
    if value.casefold().startswith("camera:"):
        value = value.split(":", 1)[1]
    return int(value)


class CameraService:
    def __init__(
        self,
        prediction_service: Any,
        frame_callback: FrameCallback,
        prediction_callback: PredictionCallback,
        error_callback: ErrorCallback,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.prediction_service = prediction_service
        self.frame_callback = frame_callback
        self.prediction_callback = prediction_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.prediction_interval_seconds = 1.0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._source_type = "webcam"
        self._source_path: Any = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, camera_index: int = 0, prediction_interval_seconds: float | None = None) -> None:
        self.start_camera_stream("webcam", camera_index, prediction_interval_seconds)

    def start_camera_stream(
        self,
        source_type: str,
        source_path: Any,
        prediction_interval_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._running:
            return
        source_type = _normalize_source_type(source_type)
        if prediction_interval_seconds is not None:
            self.prediction_interval_seconds = max(0.25, float(prediction_interval_seconds))
        self._source_type = source_type
        self._source_path = source_path
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(source_type, source_path, metadata or {}),
            daemon=True,
        )
        self._thread.start()

    def stop(self, wait: bool = False) -> None:
        self._stop_event.set()
        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self, source_type: str, source_path: Any, base_metadata: dict[str, Any]) -> None:
        self._running = True
        cap: cv2.VideoCapture | None = None
        last_prediction_at = 0.0
        self._emit_status("connecting", "Connecting...", source_type, source_path, base_metadata)
        try:
            while not self._stop_event.is_set():
                if cap is None or not cap.isOpened():
                    cap = self._open_capture(source_type, source_path)
                    if cap is None or not cap.isOpened():
                        if source_type == "video":
                            self._emit_status("error", "Video file could not be opened", source_type, source_path, base_metadata)
                            self.error_callback(f"Could not open video source: {source_path}")
                            break
                        self._emit_status("reconnecting", "Reconnecting...", source_type, source_path, base_metadata)
                        self._sleep_until_retry()
                        continue
                    self._emit_status("connected", "Connected", source_type, source_path, base_metadata)

                ok, frame = cap.read()
                if not ok or frame is None:
                    cap.release()
                    cap = None
                    if source_type == "video":
                        self._emit_status("ended", "Video ended", source_type, source_path, base_metadata)
                        break
                    self._emit_status("reconnecting", "Reconnecting...", source_type, source_path, base_metadata)
                    self._sleep_until_retry()
                    continue

                metadata = self._metadata(source_type, source_path, base_metadata, "connected")
                self.frame_callback(frame.copy(), metadata)

                now = time.monotonic()
                if now - last_prediction_at >= self.prediction_interval_seconds:
                    last_prediction_at = now
                    try:
                        prediction_started_at = time.perf_counter()
                        prediction = self.prediction_service.predict_frame(frame.copy())
                        prediction_finished_at = time.perf_counter()
                        prediction_metadata = dict(metadata)
                        prediction_metadata.update(
                            {
                                "processing_time_ms": round((prediction_finished_at - prediction_started_at) * 1000, 2),
                                "detection_frame_number": int(metadata.get("frame_index", 0) or 0),
                                "playback_fps": 0.0,
                            }
                        )
                        self.prediction_callback(prediction, frame.copy(), prediction_metadata)
                    except Exception as exc:
                        self.error_callback(f"Prediction failed: {exc}")

                time.sleep(0.01)
        finally:
            if cap is not None:
                cap.release()
            self._running = False
            self._emit_status("stopped", "Stopped", source_type, source_path, base_metadata)

    def _open_capture(self, source_type: str, source_path: Any) -> cv2.VideoCapture:
        if source_type == "webcam":
            return cv2.VideoCapture(_webcam_index(source_path))
        if source_type == "rtsp":
            return cv2.VideoCapture(str(source_path))
        path = str(Path(str(source_path)).expanduser())
        return cv2.VideoCapture(path)

    def _sleep_until_retry(self) -> None:
        deadline = time.monotonic() + RECONNECT_DELAY_SECONDS
        while not self._stop_event.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)

    def _metadata(
        self,
        source_type: str,
        source_path: Any,
        base_metadata: dict[str, Any],
        stream_status: str,
    ) -> dict[str, Any]:
        metadata = dict(base_metadata)
        metadata.update(
            {
                "source_type": source_type,
                "source_path": str(source_path),
                "stream_status": stream_status,
                "ai_interval": f"Every {self.prediction_interval_seconds:g} sec",
            }
        )
        if source_type == "webcam":
            metadata["source_path"] = f"camera:{_webcam_index(source_path)}"
        return metadata

    def _emit_status(
        self,
        status: str,
        message: str,
        source_type: str,
        source_path: Any,
        base_metadata: dict[str, Any],
    ) -> None:
        if not self.status_callback:
            return
        metadata = self._metadata(source_type, source_path, base_metadata, status)
        metadata.update({"status": status, "message": message})
        self.status_callback(metadata)
