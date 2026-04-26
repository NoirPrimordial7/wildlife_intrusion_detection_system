from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from app.ui.theme import COLORS


class Sidebar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, callbacks: dict[str, Callable[[], None]]) -> None:
        super().__init__(master, width=240, corner_radius=0, fg_color=COLORS["surface"])
        self.grid_propagate(False)
        self.callbacks = callbacks
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Video Intrusion\nDetection",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text"],
            justify="left",
        )
        title.grid(row=0, column=0, sticky="ew", padx=22, pady=(28, 6))

        subtitle = ctk.CTkLabel(
            self,
            text="PC wildlife safety demo",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["muted"],
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 24))

        buttons = [
            ("Upload Video", "upload_video"),
            ("Start Webcam Monitoring", "start_webcam"),
            ("Upload Image", "upload_image"),
            ("Stop Monitoring", "stop_monitoring"),
            ("Export Report", "export_report"),
            ("Open Alerts Folder", "open_alerts"),
            ("Settings", "settings"),
        ]

        for index, (label, key) in enumerate(buttons, start=2):
            button = ctk.CTkButton(
                self,
                text=label,
                height=42,
                anchor="w",
                command=self.callbacks.get(key),
                fg_color=COLORS["accent"] if index == 2 else COLORS["surface_alt"],
                hover_color=COLORS["accent_hover"],
                text_color=COLORS["text"],
                corner_radius=6,
                font=ctk.CTkFont(size=14, weight="bold" if index == 2 else "normal"),
            )
            button.grid(row=index, column=0, sticky="ew", padx=18, pady=6)

        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.grid(row=20, column=0, sticky="nsew")
        self.grid_rowconfigure(20, weight=1)

        footer = ctk.CTkLabel(
            self,
            text="Upload a video, then use\nStart Detection below preview.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            justify="left",
        )
        footer.grid(row=21, column=0, sticky="ew", padx=22, pady=(12, 24))
