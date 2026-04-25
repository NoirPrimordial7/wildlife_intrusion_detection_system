from __future__ import annotations

from typing import Any

import customtkinter as ctk

from app.ui.theme import COLORS


class AlertHistoryPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.title = ctk.CTkLabel(
            self,
            text="Alert History",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.title.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        self.rows: list[ctk.CTkLabel] = []
        for row in range(1, 8):
            label = ctk.CTkLabel(
                self,
                text="--",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=12),
                anchor="w",
                justify="left",
                wraplength=310,
            )
            label.grid(row=row, column=0, sticky="ew", padx=16, pady=(2, 10 if row == 7 else 2))
            self.rows.append(label)

    def update_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            self.rows[0].configure(text="No alert events yet")
            for label in self.rows[1:]:
                label.configure(text="")
            return
        for index, label in enumerate(self.rows):
            if index < len(events):
                event = events[index]
                text = (
                    f"{event.get('timestamp', '')}\n"
                    f"{event.get('animal', 'Unknown')} - {float(event.get('confidence', 0.0)):.1%}"
                )
                label.configure(text=text)
            else:
                label.configure(text="")

