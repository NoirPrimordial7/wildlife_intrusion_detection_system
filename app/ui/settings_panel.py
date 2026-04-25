from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from app.ui.theme import COLORS


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, config: dict[str, Any], on_save: Callable[[dict[str, Any]], None]) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.config = config
        self.on_save = on_save
        self.threshold_var = ctk.DoubleVar(value=float(config.get("confidence_threshold", 0.70)))
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            self,
            text="Settings",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 8))

        self.threshold_value = ctk.CTkLabel(
            self,
            text=f"Threshold: {self.threshold_var.get():.0%}",
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.threshold_value.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(2, 4))

        threshold_slider = ctk.CTkSlider(
            self,
            from_=0.10,
            to=0.99,
            variable=self.threshold_var,
            command=self._on_threshold_change,
        )
        threshold_slider.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        self.repeat_entry = self._entry_row(3, "Repeated detections", str(config.get("required_repeated_detections", 3)))
        self.cooldown_entry = self._entry_row(4, "Cooldown seconds", str(config.get("alert_cooldown_seconds", 120)))
        self.location_entry = self._entry_row(5, "Camera location", str(config.get("camera_location", "Village Border Camera")))

        save_button = ctk.CTkButton(
            self,
            text="Save Settings",
            height=36,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._save,
        )
        save_button.grid(row=6, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 16))

    def _entry_row(self, row: int, label_text: str, value: str) -> ctk.CTkEntry:
        label = ctk.CTkLabel(self, text=label_text, text_color=COLORS["muted"], anchor="w")
        label.grid(row=row, column=0, sticky="ew", padx=(16, 8), pady=5)
        entry = ctk.CTkEntry(self, height=32)
        entry.insert(0, value)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 16), pady=5)
        return entry

    def _on_threshold_change(self, value: float) -> None:
        self.threshold_value.configure(text=f"Threshold: {float(value):.0%}")

    def _save(self) -> None:
        updates = {
            "confidence_threshold": round(float(self.threshold_var.get()), 2),
            "required_repeated_detections": max(1, int(self.repeat_entry.get())),
            "alert_cooldown_seconds": max(0, int(self.cooldown_entry.get())),
            "camera_location": self.location_entry.get().strip() or "Village Border Camera",
        }
        self.on_save(updates)

