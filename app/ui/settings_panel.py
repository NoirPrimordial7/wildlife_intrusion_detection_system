from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from app.core.notification_service import is_valid_phone
from app.ui.theme import COLORS


class SettingsPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: dict[str, Any],
        on_save: Callable[[dict[str, Any]], None],
        on_stop_siren: Callable[[], None] | None = None,
        registered_users: list[dict[str, Any]] | None = None,
        on_save_users: Callable[[list[dict[str, Any]]], None] | None = None,
        on_test_sms: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.config = config
        self.on_save = on_save
        self.on_stop_siren = on_stop_siren
        self.registered_users = list(registered_users or [])
        self.on_save_users = on_save_users
        self.on_test_sms = on_test_sms
        self.user_rows: list[dict[str, Any]] = []
        self.threshold_var = ctk.DoubleVar(value=float(config.get("confidence_threshold", 0.70)))
        self.siren_enabled_var = ctk.BooleanVar(value=bool(config.get("siren_enabled", True)))
        self.new_user_enabled_var = ctk.BooleanVar(value=True)
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

        self.repeat_entry = self._entry_row(3, "Repeated detections", str(self.config.get("required_repeated_detections", 3)))
        self.cooldown_entry = self._entry_row(4, "Cooldown seconds", str(self.config.get("alert_cooldown_seconds", 120)))
        self.location_entry = self._entry_row(5, "Camera location", str(self.config.get("camera_location", "Village Border Camera")))

        siren_toggle = ctk.CTkCheckBox(
            self,
            text="Enable Siren",
            variable=self.siren_enabled_var,
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        siren_toggle.grid(row=6, column=0, sticky="w", padx=16, pady=(8, 4))

        stop_alarm_button = ctk.CTkButton(
            self,
            text="Stop Alarm",
            height=32,
            corner_radius=6,
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["accent_hover"],
            command=self.on_stop_siren,
        )
        stop_alarm_button.grid(row=6, column=1, sticky="ew", padx=(8, 16), pady=(8, 4))

        save_button = ctk.CTkButton(
            self,
            text="Save Settings",
            height=36,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._save,
        )
        save_button.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 16))

        self._build_registered_users(8)

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
            "siren_enabled": bool(self.siren_enabled_var.get()),
        }
        self.on_save(updates)

    def _build_registered_users(self, start_row: int) -> None:
        divider = ctk.CTkFrame(self, fg_color=COLORS["border"], height=1)
        divider.grid(row=start_row, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))

        title = ctk.CTkLabel(
            self,
            text="Registered Phone Users",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        title.grid(row=start_row + 1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))

        self.new_name_entry = self._entry_row(start_row + 2, "Person name", "")
        self.new_name_entry.configure(placeholder_text="Village Guard")
        self.new_phone_entry = self._entry_row(start_row + 3, "Phone number", "")
        self.new_phone_entry.configure(placeholder_text="+910000000000")

        new_enabled = ctk.CTkCheckBox(
            self,
            text="Enable user",
            variable=self.new_user_enabled_var,
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        new_enabled.grid(row=start_row + 4, column=0, sticky="w", padx=16, pady=(6, 4))

        add_button = ctk.CTkButton(
            self,
            text="Add User",
            height=32,
            corner_radius=6,
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["accent_hover"],
            command=self._add_user_from_inputs,
        )
        add_button.grid(row=start_row + 4, column=1, sticky="ew", padx=(8, 16), pady=(6, 4))

        self.users_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.users_frame.grid(row=start_row + 5, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 8))
        self.users_frame.grid_columnconfigure(0, weight=1)

        save_users_button = ctk.CTkButton(
            self,
            text="Save Registered Users",
            height=34,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._save_registered_users,
        )
        save_users_button.grid(row=start_row + 6, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 16))
        self._render_user_rows()

    def _add_user_from_inputs(self) -> None:
        self._sync_user_enabled_state()
        name = self.new_name_entry.get().strip()
        phone = self.new_phone_entry.get().strip()
        if not name or not phone:
            return
        if not is_valid_phone(phone):
            self._set_user_message(f"Invalid phone number: {phone}")
            return
        self.registered_users.append(
            {
                "name": name,
                "phone": phone,
                "enabled": bool(self.new_user_enabled_var.get()),
            }
        )
        self.new_name_entry.delete(0, "end")
        self.new_phone_entry.delete(0, "end")
        self.new_user_enabled_var.set(True)
        self._render_user_rows()
        self._set_user_message("User added. Click Save Registered Users.")

    def _render_user_rows(self) -> None:
        self.user_rows = []
        for child in self.users_frame.winfo_children():
            child.destroy()
        if not self.registered_users:
            empty = ctk.CTkLabel(
                self.users_frame,
                text="No registered users yet",
                text_color=COLORS["muted"],
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            self.user_message = ctk.CTkLabel(
                self.users_frame,
                text="",
                text_color=COLORS["muted"],
                anchor="w",
                wraplength=310,
            )
            self.user_message.grid(row=1, column=0, sticky="ew", padx=4, pady=(2, 4))
            return
        for index, user in enumerate(self.registered_users):
            enabled_var = ctk.BooleanVar(value=bool(user.get("enabled", True)))
            row = ctk.CTkFrame(self.users_frame, fg_color=COLORS["surface_alt"], corner_radius=6)
            row.grid(row=index, column=0, sticky="ew", pady=(0, 6))
            row.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(
                row,
                text=f"{user.get('name', '')}\n{user.get('phone', '')}",
                text_color=COLORS["text"],
                anchor="w",
                justify="left",
                wraplength=235,
                font=ctk.CTkFont(size=12),
            )
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            checkbox = ctk.CTkCheckBox(
                row,
                text="Enabled",
                variable=enabled_var,
                text_color=COLORS["muted"],
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
            )
            checkbox.grid(row=0, column=1, sticky="e", padx=10, pady=8)
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
            actions.grid_columnconfigure((0, 1), weight=1)
            test_button = ctk.CTkButton(
                actions,
                text="Test SMS",
                height=28,
                corner_radius=6,
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                command=lambda idx=index: self._test_user_sms(idx),
            )
            test_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
            delete_button = ctk.CTkButton(
                actions,
                text="Delete",
                height=28,
                corner_radius=6,
                fg_color=COLORS["danger"],
                hover_color="#a93434",
                command=lambda idx=index: self._delete_user(idx),
            )
            delete_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
            self.user_rows.append({"user": user, "enabled_var": enabled_var})

        self.user_message = ctk.CTkLabel(
            self.users_frame,
            text="",
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=310,
        )
        self.user_message.grid(row=len(self.registered_users), column=0, sticky="ew", padx=4, pady=(2, 4))

    def _save_registered_users(self) -> None:
        self._sync_user_enabled_state()
        for user in self.registered_users:
            phone = str(user.get("phone", "")).strip()
            if not is_valid_phone(phone):
                self._set_user_message(f"Invalid phone number: {phone}")
                return
        if self.on_save_users:
            self.on_save_users(self.registered_users)
        self._set_user_message("Registered users saved.")

    def _sync_user_enabled_state(self) -> None:
        users: list[dict[str, Any]] = []
        for row in self.user_rows:
            user = dict(row["user"])
            user["enabled"] = bool(row["enabled_var"].get())
            users.append(user)
        self.registered_users = users

    def _delete_user(self, index: int) -> None:
        self._sync_user_enabled_state()
        if 0 <= index < len(self.registered_users):
            del self.registered_users[index]
            self._render_user_rows()
            self._set_user_message("User deleted. Click Save Registered Users.")

    def _test_user_sms(self, index: int) -> None:
        self._sync_user_enabled_state()
        if not 0 <= index < len(self.registered_users):
            return
        user = self.registered_users[index]
        phone = str(user.get("phone", "")).strip()
        if not is_valid_phone(phone):
            self._set_user_message(f"Invalid phone number: {phone}")
            return
        if self.on_test_sms:
            self.on_test_sms(user)

    def _set_user_message(self, message: str) -> None:
        if hasattr(self, "user_message"):
            self.user_message.configure(text=message)
