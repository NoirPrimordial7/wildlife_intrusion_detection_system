from __future__ import annotations

import os
import threading
import time


class SirenService:
    def __init__(self, enabled: bool = True, cooldown_seconds: int = 15) -> None:
        self.enabled = enabled
        self.cooldown_seconds = max(1, int(cooldown_seconds))
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_started_at = 0.0

    @property
    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop()

    def trigger(self, severity: str) -> str:
        level = (severity or "").upper()
        if level not in {"HIGH", "CRITICAL", "DANGER"}:
            return "Siren skipped for non-danger severity."
        if not self.enabled:
            return "Siren disabled."

        with self._lock:
            now = time.monotonic()
            if self.is_active or now - self._last_started_at < self.cooldown_seconds:
                return "Siren cooldown active."
            self._last_started_at = now
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_alarm, daemon=True)
            self._thread.start()
        return "Siren started."

    def stop(self) -> None:
        self._stop_event.set()

    def _run_alarm(self) -> None:
        deadline = time.monotonic() + self.cooldown_seconds
        while not self._stop_event.is_set() and time.monotonic() < deadline:
            self._beep_once()
            time.sleep(0.35)
        self._stop_event.set()

    def _beep_once(self) -> None:
        if os.name == "nt":
            try:
                import winsound

                winsound.Beep(1200, 250)
                return
            except Exception:
                pass
        print("\a", end="", flush=True)
