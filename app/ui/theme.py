from __future__ import annotations

import customtkinter as ctk


COLORS = {
    "app_bg": "#101820",
    "surface": "#17212b",
    "surface_alt": "#1f2c38",
    "border": "#2f3f4e",
    "text": "#f4f7fb",
    "muted": "#9fb0c0",
    "accent": "#24a19c",
    "accent_hover": "#1c807c",
    "safe": "#18a058",
    "warning": "#d99a20",
    "danger": "#d64545",
    "preview_bg": "#071017",
}


def apply_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def threat_color(level: str) -> str:
    level = (level or "SAFE").upper()
    if level == "DANGER":
        return COLORS["danger"]
    if level == "WARNING":
        return COLORS["warning"]
    return COLORS["safe"]

