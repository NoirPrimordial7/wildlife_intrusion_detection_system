from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

import cv2

from app.core.prediction_service import PredictionService


FrameCallback = Callable[[Any, dict[str, Any]], None]
PredictionCallback = Callable[[dict[str, Any], Any, dict[str, Any]], None]
ProgressCallback = Callable[[dict[str, Any]], None]
ErrorCallback = Callable[[str], None]


DETECTION_INTERVALS: dict[str, tuple[str, float]] = {
    "Every 8 frames": ("frames", 8),
    "Every 16 frames": ("frames", 16),
    "Every 24 frames": ("frames", 24),
    "Every 30 frames": ("frames", 30),
    "Every 60 frames": ("frames", 60),
    "Every 1 sec": ("seconds", 1),
    "Every 2 sec": ("seconds", 2),
    "Every 5 sec": ("seconds", 5),
}


def format_video_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    remainder = seconds - (minutes * 60)
    return f"{minutes:02d}:{remainder:05.2f}"


class VideoService:
    def __init__(
        self,
        prediction_service: PredictionService,
        frame_callback: FrameCallback,
        prediction_callback: PredictionCallback,
        progress_callback: ProgressCallback,
        error_callback: ErrorCallback,
    ) -> None:
        self.prediction_service = prediction_service
        self.frame_callback = frame_callback
        self.prediction_callback = prediction_callback
        self.progress_callback = progress_callback
        self.error_callback = error_callback

        self.video_path: str | None = None
        self.fps = 30.0
        self.frame_count = 0
        self.current_frame_index = 0
        self.speed = 1.0
        self.interval_label = "Every 16 frames"

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._seek_frame: int | None = None
        self._last_prediction_second = -9999.0
        self._last_frame_at: float | None = None
        self._playback_fps = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def open_video(self, video_path: str) -> None:
        self.stop(wait=True, reset=False)
        path = str(Path(video_path).resolve())
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.error_callback(f"Could not open video: {video_path}")
            return
        self.video_path = path
        self.fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.current_frame_index = 0
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            self.error_callback("Video loaded but first frame could not be read")
            return
        self._last_prediction_second = -9999.0
        self.frame_callback(frame.copy(), self._metadata())
        self._emit_progress()

    def start(self) -> None:
        if not self.video_path:
            self.error_callback("No video selected")
            return
        if self._running:
            self.resume()
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        if self._running:
            self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def stop(self, wait: bool = False, reset: bool = True) -> None:
        self._stop_event.set()
        self._pause_event.clear()
        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if reset:
            self.current_frame_index = 0
            self._last_prediction_second = -9999.0
            self._emit_frame_at(0)

    def restart(self) -> None:
        self.stop(wait=True, reset=True)
        self.start()

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = max(0.25, float(speed))

    def set_detection_interval(self, label: str) -> None:
        if label in DETECTION_INTERVALS:
            with self._lock:
                self.interval_label = label
                self._last_prediction_second = -9999.0

    def seek_seconds(self, seconds: float) -> None:
        if not self.video_path:
            return
        delta_frames = int(seconds * self.fps)
        self.seek_frame(self.current_frame_index + delta_frames)

    def seek_percent(self, percent: float) -> None:
        if not self.video_path or self.frame_count <= 0:
            return
        target = int((max(0.0, min(100.0, float(percent))) / 100.0) * max(0, self.frame_count - 1))
        self.seek_frame(target)

    def seek_frame(self, frame_index: int) -> None:
        if not self.video_path:
            return
        target = max(0, min(int(frame_index), max(0, self.frame_count - 1)))
        with self._lock:
            self.current_frame_index = target
            self._seek_frame = target
            self._last_prediction_second = -9999.0
        if not self._running:
            self._emit_frame_at(target)

    def _run(self) -> None:
        if not self.video_path:
            return
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.error_callback(f"Could not open video: {self.video_path}")
            return

        self._running = True
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_index)
        try:
            while not self._stop_event.is_set():
                if self._pause_event.is_set():
                    time.sleep(0.05)
                    continue

                with self._lock:
                    seek_frame = self._seek_frame
                    self._seek_frame = None
                if seek_frame is not None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)

                ok, frame = cap.read()
                if not ok or frame is None:
                    break

                frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                self.current_frame_index = max(0, frame_index)
                now = time.perf_counter()
                if self._last_frame_at is not None:
                    elapsed = max(0.0001, now - self._last_frame_at)
                    self._playback_fps = 1.0 / elapsed
                self._last_frame_at = now
                metadata = self._metadata()
                self.frame_callback(frame.copy(), metadata)
                self._emit_progress()

                if self._should_predict(self.current_frame_index):
                    try:
                        prediction_started_at = time.perf_counter()
                        prediction = self.prediction_service.predict_frame(frame.copy())
                        prediction_finished_at = time.perf_counter()
                        prediction_metadata = dict(metadata)
                        prediction_metadata.update(
                            {
                                "processing_time_ms": round((prediction_finished_at - prediction_started_at) * 1000, 2),
                                "detection_video_timestamp": format_video_timestamp(metadata.get("current_second", 0.0)),
                                "detection_frame_number": self.current_frame_index,
                                "playback_fps": round(self._playback_fps, 2),
                            }
                        )
                        self.prediction_callback(prediction, frame.copy(), prediction_metadata)
                    except Exception as exc:
                        self.error_callback(f"Prediction failed: {exc}")

                with self._lock:
                    speed = self.speed
                delay = (1.0 / max(self.fps, 1.0)) / max(speed, 0.25)
                time.sleep(min(max(delay, 0.001), 0.2))
        finally:
            cap.release()
            self._running = False
            self._stop_event.clear()
            self._last_frame_at = None

    def _should_predict(self, frame_index: int) -> bool:
        with self._lock:
            label = self.interval_label
        mode, value = DETECTION_INTERVALS.get(label, ("frames", 16))
        if mode == "frames":
            return frame_index % int(value) == 0
        current_second = frame_index / max(self.fps, 1.0)
        if current_second - self._last_prediction_second >= float(value):
            self._last_prediction_second = current_second
            return True
        return False

    def _metadata(self) -> dict[str, Any]:
        current_second = self.current_frame_index / max(self.fps, 1.0)
        return {
            "source_type": "video",
            "source_path": self.video_path or "",
            "frame_index": self.current_frame_index,
            "current_second": current_second,
            "detection_video_timestamp": format_video_timestamp(current_second),
            "detection_frame_number": self.current_frame_index,
            "ai_interval": self.interval_label,
            "playback_fps": round(self._playback_fps, 2),
        }

    def _emit_progress(self) -> None:
        duration = self.frame_count / max(self.fps, 1.0) if self.frame_count else 0.0
        current_second = self.current_frame_index / max(self.fps, 1.0)
        percent = (self.current_frame_index / max(1, self.frame_count - 1)) * 100 if self.frame_count else 0.0
        self.progress_callback(
            {
                "frame_index": self.current_frame_index,
                "frame_count": self.frame_count,
                "current_second": current_second,
                "duration_seconds": duration,
                "percent": percent,
                "fps": self.fps,
                "playback_fps": round(self._playback_fps, 2),
                "speed": self.speed,
            }
        )

    def _emit_frame_at(self, frame_index: int) -> None:
        if not self.video_path:
            return
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index))
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            self.current_frame_index = max(0, frame_index)
            self.frame_callback(frame.copy(), self._metadata())
            self._emit_progress()
