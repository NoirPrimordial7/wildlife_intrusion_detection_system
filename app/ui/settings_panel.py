from __future__ import annotations

from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

from app.core.notification_service import is_valid_phone, mask_phone
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
        sms_config: dict[str, Any] | None = None,
        on_save_sms_config: Callable[[dict[str, Any]], None] | None = None,
        on_refresh_status: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.config = config
        self.on_save = on_save
        self.on_stop_siren = on_stop_siren
        self.registered_users = list(registered_users or [])
        self.on_save_users = on_save_users
        self.on_test_sms = on_test_sms
        self.sms_config = dict(sms_config or {})
        self.on_save_sms_config = on_save_sms_config
        self.on_refresh_status = on_refresh_status
        self.user_rows: list[dict[str, Any]] = []
        self._tooltip: ctk.CTkToplevel | None = None
        self.threshold_var = ctk.DoubleVar(value=float(config.get("confidence_threshold", 0.70)))
        self.siren_enabled_var = ctk.BooleanVar(value=bool(config.get("siren_enabled", True)))
        self.cooldown_var = ctk.StringVar(value=str(config.get("alert_cooldown_seconds", 120)))
        self.new_user_enabled_var = ctk.BooleanVar(value=True)
        self.sms_enabled_var = ctk.BooleanVar(value=bool(self.sms_config.get("enabled", False)))
        self.sms_provider_var = ctk.StringVar(value=self._provider_display(str(self.sms_config.get("provider", "twilio"))))
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
        self.cooldown_entry = self._cooldown_row(4)
        self.location_entry = self._entry_row(5, "Camera location", str(self.config.get("camera_location", "Village Border Camera")))

        siren_toggle = ctk.CTkCheckBox(
            self,
            text="Enable Alarm Sound",
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

        self._build_sms_settings(8)
        self._build_registered_users(15)

    def _entry_row(self, row: int, label_text: str, value: str) -> ctk.CTkEntry:
        label = ctk.CTkLabel(self, text=label_text, text_color=COLORS["muted"], anchor="w")
        label.grid(row=row, column=0, sticky="ew", padx=(16, 8), pady=5)
        entry = ctk.CTkEntry(self, height=32)
        entry.insert(0, value)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 16), pady=5)
        return entry

    def _cooldown_row(self, row: int) -> ctk.CTkOptionMenu:
        label = ctk.CTkLabel(self, text="SMS cooldown", text_color=COLORS["muted"], anchor="w")
        label.grid(row=row, column=0, sticky="ew", padx=(16, 8), pady=5)
        menu = ctk.CTkOptionMenu(self, variable=self.cooldown_var, values=["30", "60", "120", "300"], width=110)
        menu.grid(row=row, column=1, sticky="ew", padx=(8, 16), pady=5)
        return menu

    def _on_threshold_change(self, value: float) -> None:
        self.threshold_value.configure(text=f"Threshold: {float(value):.0%}")

    def _save(self) -> None:
        updates = {
            "confidence_threshold": round(float(self.threshold_var.get()), 2),
            "required_repeated_detections": max(1, int(self.repeat_entry.get())),
            "alert_cooldown_seconds": max(0, int(self.cooldown_var.get())),
            "camera_location": self.location_entry.get().strip() or "Village Border Camera",
            "siren_enabled": bool(self.siren_enabled_var.get()),
        }
        self.on_save(updates)

    def _build_sms_settings(self, start_row: int) -> None:
        divider = ctk.CTkFrame(self, fg_color=COLORS["border"], height=1)
        divider.grid(row=start_row, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))
        title = ctk.CTkLabel(self, text="Notification Settings", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["text"], anchor="w")
        title.grid(row=start_row + 1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        sms_toggle = ctk.CTkSwitch(
            self,
            text="Enable Real SMS",
            variable=self.sms_enabled_var,
            command=self._save_sms_config,
            text_color=COLORS["text"],
            progress_color=COLORS["danger"],
        )
        sms_toggle.grid(row=start_row + 2, column=0, sticky="w", padx=16, pady=(4, 6))
        provider_menu = ctk.CTkOptionMenu(
            self,
            variable=self.sms_provider_var,
            values=["Twilio", "Fast2SMS", "Generic HTTP"],
            command=lambda _value: self._save_sms_config(),
            width=150,
        )
        provider_menu.grid(row=start_row + 2, column=1, sticky="ew", padx=(8, 16), pady=(4, 6))
        summary = self._masked_sms_summary()
        self.sms_secret_label = ctk.CTkLabel(self, text=summary, text_color=COLORS["muted"], anchor="w", justify="left", wraplength=310)
        self.sms_secret_label.grid(row=start_row + 3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        self.sms_ready_label = ctk.CTkLabel(
            self,
            text=self._sms_ready_text(),
            text_color=COLORS["safe"] if self._sms_provider_ready() else COLORS["critical"],
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.sms_ready_label.grid(row=start_row + 4, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        refresh_button = ctk.CTkButton(self, text="Refresh Status", height=30, corner_radius=6, fg_color=COLORS["surface_alt"], hover_color=COLORS["accent_hover"], command=self._refresh_status)
        refresh_button.grid(row=start_row + 5, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))

    def _masked_sms_summary(self) -> str:
        twilio = self.sms_config.get("twilio", {}) if isinstance(self.sms_config.get("twilio"), dict) else {}
        return (
            f"Account SID: {mask_phone(twilio.get('account_sid', ''))}\n"
            "Auth token: hidden\n"
            f"From number: {mask_phone(twilio.get('from_number', ''))}"
        )

    def _sms_provider_ready(self) -> bool:
        provider = self.sms_provider_var.get().strip().casefold().replace(" ", "_")
        if provider == "twilio":
            twilio = self.sms_config.get("twilio", {}) if isinstance(self.sms_config.get("twilio"), dict) else {}
            return all(str(twilio.get(key, "")).strip() for key in ("account_sid", "auth_token", "from_number"))
        if provider == "fast2sms":
            fast2sms = self.sms_config.get("fast2sms", {}) if isinstance(self.sms_config.get("fast2sms"), dict) else {}
            return bool(str(fast2sms.get("api_key", "")).strip())
        generic = self.sms_config.get("generic_http", {}) if isinstance(self.sms_config.get("generic_http"), dict) else {}
        return bool(str(generic.get("api_url", "")).strip())

    def _sms_test_ready(self) -> bool:
        return bool(self.sms_enabled_var.get()) and self._sms_provider_ready()

    def _sms_ready_text(self) -> str:
        provider = self.sms_provider_var.get().strip() or "Twilio"
        if self._sms_provider_ready():
            return f"{provider} ready"
        return f"{provider} not configured"

    def _provider_display(self, provider: str) -> str:
        key = provider.strip().casefold().replace(" ", "_")
        return {"twilio": "Twilio", "fast2sms": "Fast2SMS", "generic_http": "Generic HTTP"}.get(key, "Twilio")

    def _save_sms_config(self) -> None:
        if self.sms_enabled_var.get():
            ok = messagebox.askyesno("Enable real SMS?", "Real SMS may use trial credits. Enable only for final testing.")
            if not ok:
                self.sms_enabled_var.set(False)
        provider = self.sms_provider_var.get().strip().casefold().replace(" ", "_")
        updates = {"enabled": bool(self.sms_enabled_var.get()), "provider": provider}
        if self.on_save_sms_config:
            self.on_save_sms_config(updates)
        if hasattr(self, "sms_ready_label"):
            self.sms_ready_label.configure(
                text=self._sms_ready_text(),
                text_color=COLORS["safe"] if self._sms_provider_ready() else COLORS["critical"],
            )
        self._render_user_rows()

    def _refresh_status(self) -> None:
        if self.on_refresh_status:
            self.on_refresh_status()

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
            last_status = str(user.get("last_status", "--"))
            label = ctk.CTkLabel(
                row,
                text=f"Name: {user.get('name', '')}\nPhone: {mask_phone(user.get('phone', ''))}\nLast Status: {last_status}",
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
                fg_color=COLORS["accent"] if self._sms_test_ready() else COLORS["border"],
                hover_color=COLORS["accent_hover"],
                command=lambda idx=index: self._test_user_sms(idx),
                state="normal" if self._sms_test_ready() else "disabled",
            )
            self._attach_tooltip(test_button, "Requires Twilio configuration")
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
            text="" if self._sms_test_ready() else "Test SMS requires Twilio configuration.",
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

    def _attach_tooltip(self, widget: ctk.CTkBaseClass, text: str) -> None:
        def show(_event: object) -> None:
            self._hide_tooltip()
            tooltip = ctk.CTkToplevel(self)
            tooltip.overrideredirect(True)
            tooltip.configure(fg_color=COLORS["surface_alt"])
            x = self.winfo_pointerx() + 12
            y = self.winfo_pointery() + 12
            tooltip.geometry(f"+{x}+{y}")
            label = ctk.CTkLabel(tooltip, text=text, text_color=COLORS["text"], font=ctk.CTkFont(size=12))
            label.pack(padx=8, pady=5)
            self._tooltip = tooltip

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", lambda _event: self._hide_tooltip())

    def _hide_tooltip(self) -> None:
        if self._tooltip is not None and self._tooltip.winfo_exists():
            self._tooltip.destroy()
        self._tooltip = None
