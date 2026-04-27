from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from app.core.notification_service import mask_phone
from app.ui.theme import COLORS


class NotificationLogPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_clear: Callable[[], None],
        on_export: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.on_clear = on_clear
        self.on_export = on_export
        self.rows_frame: ctk.CTkFrame | None = None
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(self, text="Notification Log", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["text"], anchor="w")
        title.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="Clear Notification Log", height=28, corner_radius=6, fg_color=COLORS["danger"], hover_color="#a93434", command=self.on_clear).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(actions, text="Export Notification Log", height=28, corner_radius=6, fg_color=COLORS["surface_alt"], hover_color=COLORS["accent_hover"], command=self.on_export).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.rows_frame.grid_columnconfigure(0, weight=1)

    def update_logs(self, logs: list[dict[str, Any]]) -> None:
        if self.rows_frame is None:
            return
        for child in self.rows_frame.winfo_children():
            child.destroy()
        if not logs:
            ctk.CTkLabel(self.rows_frame, text="No notification attempts yet", text_color=COLORS["muted"], anchor="w").grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            return
        for index, row in enumerate(reversed(logs[-5:])):
            preview = str(row.get("message", ""))[:80]
            text = (
                f"{row.get('timestamp', '--')} | {row.get('user_name', '--')}\n"
                f"{mask_phone(row.get('phone', ''))} | {row.get('provider', '--')} | {row.get('status', '--')}\n"
                f"{preview}"
            )
            label = ctk.CTkLabel(
                self.rows_frame,
                text=text,
                text_color=COLORS["text"],
                fg_color=COLORS["surface_alt"],
                corner_radius=6,
                anchor="w",
                justify="left",
                wraplength=310,
                font=ctk.CTkFont(size=12),
            )
            label.grid(row=index, column=0, sticky="ew", padx=4, pady=(0, 6))
