"""
Sistema de diseño de EnvVar Manager Pro.

Dirección visual: "panel de control técnico" — fondo casi negro tipo terminal,
acento cobalto para acciones primarias, y tipografía monoespaciada para
nombres/valores de variables (el elemento distintivo: las variables se leen
como código, no como texto de formulario genérico). El resto de la interfaz
se mantiene sobria y disciplinada alrededor de ese único acento.
"""

from __future__ import annotations

import customtkinter as ctk

# ---------------------------------------------------------------- Paleta

BG_BASE = "#12141A"        # fondo principal (casi negro, tono azulado)
BG_SURFACE = "#1B1E27"     # tarjetas, paneles
BG_SURFACE_ALT = "#232734" # filas alternadas / hover
BORDER = "#2E3340"
TEXT_PRIMARY = "#E7E9EE"
TEXT_SECONDARY = "#8B92A5"
TEXT_MUTED = "#5D6373"

ACCENT = "#3B7DF2"          # cobalto — acción primaria
ACCENT_HOVER = "#2F68CE"
ACCENT_SOFT = "#1E2A44"     # fondo de badges/estado con acento

SUCCESS = "#2FBF71"
SUCCESS_SOFT = "#173425"
DANGER = "#EF5959"
DANGER_SOFT = "#3A1F22"
WARNING = "#E8A93B"
WARNING_SOFT = "#3A2E14"

# Colores por alcance (scope) — se usan en badges de la tabla
SCOPE_COLORS = {
    "USER": ("#3B7DF2", "#1E2A44"),      # (texto/borde, fondo)
    "SYSTEM": ("#E8A93B", "#3A2E14"),
    "SESSION": ("#8B92A5", "#1E2229"),
}

# ---------------------------------------------------------------- Tipografía

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"


def font_titulo() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=20, weight="bold")


def font_subtitulo() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=13, weight="normal")


def font_ui(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=size, weight=weight)


def font_mono(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_MONO, size=size, weight=weight)


def aplicar_tema() -> None:
    """Configura el modo de apariencia y color base de customtkinter."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def estilo_treeview(style, alto_fila: int = 34) -> None:
    """
    Estiliza el ttk.Treeview (tabla de variables) para que combine con el
    resto de la interfaz oscura de customtkinter, ya que CTk no incluye
    un widget de tabla nativo.
    """
    style.theme_use("default")

    style.configure(
        "Custom.Treeview",
        background=BG_SURFACE,
        foreground=TEXT_PRIMARY,
        fieldbackground=BG_SURFACE,
        borderwidth=0,
        rowheight=alto_fila,
        font=(FONT_MONO, 12),
    )
    style.map(
        "Custom.Treeview",
        background=[("selected", ACCENT_SOFT)],
        foreground=[("selected", TEXT_PRIMARY)],
    )

    style.configure(
        "Custom.Treeview.Heading",
        background=BG_BASE,
        foreground=TEXT_SECONDARY,
        borderwidth=0,
        font=(FONT_UI, 11, "bold"),
        relief="flat",
    )
    style.map("Custom.Treeview.Heading", background=[("active", BG_BASE)])

    style.configure("Custom.Vertical.TScrollbar", background=BG_SURFACE, troughcolor=BG_BASE, borderwidth=0)
