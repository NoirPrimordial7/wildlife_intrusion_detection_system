from __future__ import annotations

import customtkinter as ctk


COLORS = {
    "app_bg": "#0C1514",
    "surface": "#15221F",
    "surface_alt": "#21332D",
    "border": "#344940",
    "text": "#EFF4E8",
    "muted": "#A8B9AF",
    "accent": "#B9DA83",
    "accent_hover": "#91B85B",
    "accent_text": "#132017",
    "safe": "#18a058",
    "low": "#18a058",
    "warning": "#d99a20",
    "high": "#e66f2a",
    "danger": "#d64545",
    "critical": "#e02f44",
    "preview_bg": "#09110F",
}


def apply_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    for name in ("CTkButton", "CTkOptionMenu", "CTkSlider", "CTkProgressBar"):
        widget = ctk.ThemeManager.theme[name]
        widget["fg_color"] = COLORS["surface_alt"]
        for key in ("button_color", "progress_color", "selected_color"):
            if key in widget:
                widget[key] = COLORS["accent"]
        for key in ("hover_color", "button_hover_color"):
            if key in widget:
                widget[key] = COLORS["accent_hover"]
    ctk.ThemeManager.theme["CTkOptionMenu"]["button_color"] = COLORS["border"]
    ctk.ThemeManager.theme["CTkEntry"]["fg_color"] = COLORS["preview_bg"]
    ctk.ThemeManager.theme["CTkEntry"]["border_color"] = COLORS["border"]


def threat_color(level: str) -> str:
    level = (level or "SAFE").upper()
    if level in {"CRITICAL", "DANGER"}:
        return COLORS["critical"]
    if level == "HIGH":
        return COLORS["high"]
    if level == "WARNING":
        return COLORS["warning"]
    if level == "LOW":
        return COLORS["low"]
    return COLORS["safe"]
