"""A deterministic, clearly labelled UI walkthrough; never invokes real alert services."""
from __future__ import annotations

import math
import threading
import time
import cv2
import numpy as np

from app.core.video_service import DETECTION_INTERVALS, format_video_timestamp


class DemoService:
    fps = 20.0
    frame_count = 240
    interval_label = "Every 16 frames"

    def __init__(self, frame_callback, prediction_callback, progress_callback):
        self.frame_callback = frame_callback
        self.prediction_callback = prediction_callback
        self.progress_callback = progress_callback
        self.current_frame_index = 0
        self.speed = 1.0
        self.session = 0
        self._thread = None
        self._stop = threading.Event()
        self._paused = False
        self._running = False
        self._state = "loaded"
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            self.resume()
            return
        if self.current_frame_index >= self.frame_count - 1:
            self.current_frame_index = 0
        self._stop = threading.Event()
        self._paused = False
        self._running = True
        self._state = "playing"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            while not self._stop.is_set():
                if self._paused:
                    self._stop.wait(0.05)
                    continue
                with self._lock:
                    self._emit()
                    if self.current_frame_index >= self.frame_count - 1:
                        self._state = "finished"
                        break
                    self.current_frame_index += 1
                self._stop.wait(1 / (self.fps * self.speed))
        finally:
            self._running = False
            self._progress()

    def pause(self):
        self._paused = True
        self._state = "paused"
        self._progress()

    def resume(self):
        if self._running:
            self._paused = False
            self._state = "playing"
            self._progress()

    def stop(self, wait=False, reset=True):
        self._stop.set()
        if wait and self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
        self._state = "stopped"
        if reset:
            self.seek_frame(0)
        self._progress()

    def restart(self):
        self.stop(wait=True, reset=False)
        self.current_frame_index = 0
        self.start()

    def set_speed(self, speed):
        self.speed = max(0.25, min(2.0, float(speed)))

    def set_detection_interval(self, label):
        if label in DETECTION_INTERVALS:
            self.interval_label = label

    def seek_frame(self, value):
        with self._lock:
            self.current_frame_index = max(0, min(self.frame_count - 1, int(value)))
            self._emit()

    def seek_seconds(self, value):
        self.seek_frame(self.current_frame_index + int(value * self.fps))

    def seek_percent(self, value):
        self.seek_frame((self.frame_count - 1) * max(0, min(100, value)) / 100)

    def _metadata(self):
        second = self.current_frame_index / self.fps
        return {"session": self.session, "source_type": "demo", "source_path": "built-in simulation",
                "frame_index": self.current_frame_index, "detection_frame_number": self.current_frame_index,
                "detection_video_timestamp": format_video_timestamp(second), "current_second": second,
                "ai_interval": self.interval_label, "simulation": True}

    def _progress(self):
        self.progress_callback({**self._metadata(), "frame_count": self.frame_count, "state": self._state,
                                "duration_seconds": self.frame_count / self.fps,
                                "percent": self.current_frame_index / (self.frame_count - 1) * 100,
                                "playback_fps": self.fps * self.speed, "next_check_in": "simulation",
                                "last_checked_frame": self.current_frame_index,
                                "last_checked_time": format_video_timestamp(self.current_frame_index / self.fps)})

    def _emit(self):
        metadata = self._metadata()
        second = metadata["current_second"]
        frame, bbox = render_demo_frame(second)
        self.frame_callback(frame, metadata)
        mode, value = DETECTION_INTERVALS[self.interval_label]
        interval = int(value if mode == "frames" else value * self.fps)
        if self.current_frame_index % interval == 0 or self._paused or not self._running:
            present = 3 <= second < 10
            label = "Elephant" if present else "No animal detected"
            detection = {"bbox": bbox, "display_label": label, "final_label": label, "final_confidence": 0.94,
                         "yolo_label": "Simulated", "yolo_confidence": 0.94,
                         "normalized_classifier_label": "Simulated elephant", "classifier_confidence": 0.94, "is_dangerous": True}
            prediction = {"label": label, "display_label": label, "confidence": 0.94 if present else 0,
                          "detections": [detection] if present else [], "bbox": bbox if present else None,
                          "processing_time_ms": 0, "detector_mode": "simulation"}
            self.prediction_callback(prediction, frame.copy(), metadata)
        self._progress()


def render_demo_frame(second: float):
    """Draw a local field illustration without downloading media or model weights."""
    frame = np.zeros((480, 800, 3), dtype=np.uint8)
    frame[:] = (31, 48, 40)
    for x in range(0, 800, 40):
        cv2.line(frame, (x, 0), (x, 480), (38, 58, 47), 1)
    for y in range(0, 480, 40):
        cv2.line(frame, (0, y), (800, y), (38, 58, 47), 1)
    cv2.rectangle(frame, (480, 50), (748, 405), (39, 62, 57), -1)
    for y in range(80, 380, 32):
        cv2.line(frame, (480, y), (480, y + 18), (131, 218, 185), 2)
    for x, y in ((120, 170), (200, 335), (330, 110), (90, 360)):
        cv2.circle(frame, (x, y), 42, (35, 80, 53), -1)
        cv2.circle(frame, (x - 9, y - 10), 27, (45, 98, 66), -1)
    for x, y in ((570, 150), (650, 250), (560, 325)):
        cv2.rectangle(frame, (x, y), (x + 55, y + 38), (96, 126, 121), -1)
        cv2.fillPoly(frame, [np.array([[x - 5, y], [x + 27, y - 27], [x + 60, y]])], (113, 147, 139))
    cv2.putText(frame, "FOREST", (75, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (165, 192, 177), 1, cv2.LINE_AA)
    cv2.putText(frame, "VILLAGE / BOUNDARY", (515, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (185, 218, 196), 1, cv2.LINE_AA)
    x = int(280 + max(0, min(1, (second - 3) / 4)) * 270)
    bbox = {"x1": x - 52, "y1": 190, "x2": x + 80, "y2": 300}
    if 3 <= second < 10:
        cv2.ellipse(frame, (x, 240), (46, 28), 0, 0, 360, (150, 160, 148), -1)
        cv2.circle(frame, (x + 42, 235), 24, (169, 178, 163), -1)
        cv2.ellipse(frame, (x + 21, 233), (17, 24), 0, 0, 360, (128, 143, 129), -1)
        cv2.ellipse(frame, (x + 63, 255), (10, 28), -15, 0, 220, (169, 178, 163), 12)
        for offset in (-28, -4, 21):
            swing = int(math.sin(second * 7 + offset) * 3)
            cv2.line(frame, (x + offset, 259), (x + offset + swing, 290), (148, 161, 146), 11)
        cv2.circle(frame, (x + 50, 230), 3, (30, 44, 35), -1)
    color = (100, 126, 241) if 5 <= second < 10 else (131, 218, 185)
    cv2.circle(frame, (480, 428), 5, color, -1)
    stage = "01  PERIMETER CLEAR" if second < 3 else "02  WILDLIFE APPROACHING" if second < 5 else "03  INTRUSION CONFIRMED" if second < 10 else "04  PERIMETER CLEAR"
    cv2.putText(frame, stage, (40, 445), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
    cv2.rectangle(frame, (0, 0), (800, 28), (20, 31, 26), -1)
    cv2.putText(frame, "GUIDED SIMULATION / SCRIPTED EVENTS / NO REAL SMS", (16, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (185, 218, 196), 1, cv2.LINE_AA)
    return frame, bbox
