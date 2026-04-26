from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.utils.image_utils import safe_filename_part
from app.utils.paths import CLIPS_DIR, relative_to_project
from app.utils.time_utils import file_timestamp


@dataclass
class BufferedFrame:
    captured_at: float
    frame: np.ndarray


@dataclass
class PendingClip:
    camera_id: str
    path: Path
    frames: list[np.ndarray]
    collect_until: float
    fps: float
    created_at: float = field(default_factory=time.monotonic)


class ClipService:
    def __init__(
        self,
        output_dir: Path = CLIPS_DIR,
        pre_event_seconds: float = 5.0,
        post_event_seconds: float = 5.0,
        target_fps: float = 10.0,
        max_frames_per_camera: int = 160,
    ) -> None:
        self.output_dir = output_dir
        self.pre_event_seconds = max(1.0, float(pre_event_seconds))
        self.post_event_seconds = max(0.0, float(post_event_seconds))
        self.target_fps = max(1.0, float(target_fps))
        self.max_frames_per_camera = max(20, int(max_frames_per_camera))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._buffers: dict[str, deque[BufferedFrame]] = {}
        self._pending: list[PendingClip] = []
        self._lock = threading.Lock()

    def add_frame(self, camera_id: str, frame: np.ndarray, metadata: dict[str, Any] | None = None) -> None:
        if frame is None:
            return
        camera_id = str(camera_id or "CAM_01")
        now = time.monotonic()
        frame_copy = frame.copy()
        clips_to_write: list[PendingClip] = []
        with self._lock:
            buffer = self._buffers.setdefault(camera_id, deque())
            buffer.append(BufferedFrame(now, frame_copy))
            self._trim_buffer(buffer, now)

            remaining: list[PendingClip] = []
            for clip in self._pending:
                if clip.camera_id == camera_id:
                    clip.frames.append(frame_copy.copy())
                    if now >= clip.collect_until:
                        clips_to_write.append(clip)
                    else:
                        remaining.append(clip)
                else:
                    remaining.append(clip)
            self._pending = remaining

        for clip in clips_to_write:
            self._write_async(clip)

    def start_alert_clip(self, camera_id: str, animal: str, confidence: float, source_type: str) -> str:
        camera_id = str(camera_id or "CAM_01")
        if source_type == "image":
            return ""

        timestamp = file_timestamp()
        camera_part = safe_filename_part(camera_id)
        animal_part = safe_filename_part(animal)
        filename = f"{timestamp}_{camera_part}_{animal_part}_{confidence:.2f}.mp4"
        path = self.output_dir / filename
        now = time.monotonic()

        with self._lock:
            buffer = self._buffers.get(camera_id, deque())
            pre_frames = [
                item.frame.copy()
                for item in buffer
                if now - item.captured_at <= self.pre_event_seconds
            ]
            if not pre_frames:
                return ""
            clip = PendingClip(
                camera_id=camera_id,
                path=path,
                frames=pre_frames,
                collect_until=now + self.post_event_seconds,
                fps=self.target_fps,
            )
            if self.post_event_seconds <= 0:
                self._write_async(clip)
            else:
                self._pending.append(clip)
        return relative_to_project(path)

    def finalize_camera(self, camera_id: str) -> None:
        camera_id = str(camera_id or "CAM_01")
        self._finalize(lambda clip: clip.camera_id == camera_id)

    def finalize_all(self) -> None:
        self._finalize(lambda _clip: True)

    def _finalize(self, predicate) -> None:
        with self._lock:
            selected = [clip for clip in self._pending if predicate(clip)]
            self._pending = [clip for clip in self._pending if not predicate(clip)]
        for clip in selected:
            self._write_async(clip)

    def _trim_buffer(self, buffer: deque[BufferedFrame], now: float) -> None:
        while buffer and now - buffer[0].captured_at > self.pre_event_seconds:
            buffer.popleft()
        while len(buffer) > self.max_frames_per_camera:
            buffer.popleft()

    def _write_async(self, clip: PendingClip) -> None:
        thread = threading.Thread(target=self._write_clip, args=(clip,), daemon=True)
        thread.start()

    def _write_clip(self, clip: PendingClip) -> None:
        if not clip.frames:
            return
        clip.path.parent.mkdir(parents=True, exist_ok=True)
        first = clip.frames[0]
        height, width = first.shape[:2]
        writer = cv2.VideoWriter(
            str(clip.path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            clip.fps,
            (width, height),
        )
        if not writer.isOpened():
            fallback_path = clip.path.with_suffix(".avi")
            writer = cv2.VideoWriter(
                str(fallback_path),
                cv2.VideoWriter_fourcc(*"XVID"),
                clip.fps,
                (width, height),
            )
        if not writer.isOpened():
            return
        try:
            for frame in clip.frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                writer.write(frame)
        finally:
            writer.release()
