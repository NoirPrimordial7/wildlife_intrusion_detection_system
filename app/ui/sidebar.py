from __future__ import annotations
from typing import Callable
import customtkinter as ctk
from app.ui.theme import COLORS


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, callbacks: dict[str, Callable[[], None]]) -> None:
        super().__init__(master, width=208, corner_radius=0, fg_color=COLORS["surface"])
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.callbacks = callbacks
        self.buttons = {}
        ctk.CTkLabel(self, text="V / R", width=52, height=42, corner_radius=12,
                     fg_color=COLORS["accent"], text_color=COLORS["accent_text"],
                     font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(24, 12))
        ctk.CTkLabel(self, text="VanRakshak\nWILDLIFE WATCH", justify="left", anchor="w",
                     text_color=COLORS["text"], font=ctk.CTkFont(size=19, weight="bold")).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 20))
        actions = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        actions.grid(row=2, column=0, sticky="nsew", padx=8)
        actions.grid_columnconfigure(0, weight=1)
        groups = [
            ("01 / MONITOR", [("Upload video", "upload_video"), ("Use webcam", "start_webcam"), ("Analyze image", "upload_image"), ("Stop monitoring", "stop_monitoring")]),
            ("02 / WORKSPACE", [("Overview", "overview"), ("Evidence & history", "evidence"), ("Notifications", "notifications"), ("Settings", "settings"), ("Export report", "export_report"), ("Open evidence folder", "open_alerts")]),
            ("03 / TRY IT", [("Guided demo", "quick_demo")]),
        ]
        row = 0
        for heading, items in groups:
            ctk.CTkLabel(actions, text=heading, anchor="w", text_color=COLORS["muted"],
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=row, column=0, sticky="ew", padx=10, pady=(16, 6))
            row += 1
            for label, key in items:
                primary = key == "upload_video"
                button = ctk.CTkButton(actions, text=label, anchor="w", height=36, corner_radius=8,
                                      fg_color=COLORS["accent"] if primary else "transparent",
                                      text_color=COLORS["accent_text"] if primary else COLORS["text"],
                                      hover_color=COLORS["accent_hover"] if primary else COLORS["surface_alt"],
                                      font=ctk.CTkFont(size=13), command=callbacks.get(key))
                button.grid(row=row, column=0, sticky="ew", padx=4, pady=3)
                self.buttons[key] = button
                row += 1
        ctk.CTkLabel(self, text="FIELD DESK / v2\nLocal processing. Clear evidence.", anchor="w", justify="left",
                     font=ctk.CTkFont(size=11), text_color=COLORS["muted"]).grid(row=3, column=0, sticky="ew", padx=22, pady=20)
