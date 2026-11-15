"""Widgets reutilizables compartidos por las distintas ventanas de la app."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from . import theme


class CampoContrasena(ctk.CTkFrame):
    """Campo de contraseña con botón para mostrar/ocultar el texto."""

    def __init__(self, master, placeholder: str = "Contraseña", **kwargs):
        super().__init__(master, fg_color="transparent")
        self._visible = False

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            show="•",
            font=theme.font_mono(13),
            **kwargs,
        )
        self.entry.pack(side="left", fill="x", expand=True)

        self.boton_ojo = ctk.CTkButton(
            self,
            text="👁",
            width=32,
            fg_color=theme.BG_SURFACE_ALT,
            hover_color=theme.BORDER,
            command=self._alternar_visibilidad,
        )
        self.boton_ojo.pack(side="left", padx=(6, 0))

    def _alternar_visibilidad(self) -> None:
        self._visible = not self._visible
        self.entry.configure(show="" if self._visible else "•")

    def get(self) -> str:
        return self.entry.get()

    def focus(self) -> None:
        self.entry.focus_set()


class MedidorFortaleza(ctk.CTkFrame):
    """Barra visual de fortaleza de contraseña con etiqueta y sugerencias."""

    _COLORES = ["#EF5959", "#E8A93B", "#E8A93B", "#3B7DF2", "#2FBF71"]

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.barra = ctk.CTkProgressBar(self, height=6)
        self.barra.pack(fill="x", pady=(4, 2))
        self.barra.set(0)

        self.etiqueta = ctk.CTkLabel(
            self, text="", font=theme.font_ui(11), text_color=theme.TEXT_SECONDARY
        )
        self.etiqueta.pack(anchor="w")

    def actualizar(self, score: int, label: str) -> None:
        self.barra.set(min(score, 4) / 4)
        self.barra.configure(progress_color=self._COLORES[min(score, 4)])
        self.etiqueta.configure(text=f"Fortaleza: {label}")


class BarraEstado(ctk.CTkFrame):
    """Barra inferior con mensajes de estado y contador de variables."""

    def __init__(self, master):
        super().__init__(master, fg_color=theme.BG_BASE, height=30, corner_radius=0)
        self.grid_propagate(False)

        self.mensaje = ctk.CTkLabel(
            self, text="Listo", font=theme.font_ui(11), text_color=theme.TEXT_SECONDARY
        )
        self.mensaje.pack(side="left", padx=12)

        self.indicador_admin = ctk.CTkLabel(
            self, text="", font=theme.font_ui(11, "bold")
        )
        self.indicador_admin.pack(side="right", padx=12)

    def set_mensaje(self, texto: str, es_error: bool = False) -> None:
        color = theme.DANGER if es_error else theme.TEXT_SECONDARY
        self.mensaje.configure(text=texto, text_color=color)

    def set_admin(self, es_admin: bool) -> None:
        if es_admin:
            self.indicador_admin.configure(text="● Administrador", text_color=theme.SUCCESS)
        else:
            self.indicador_admin.configure(text="● Usuario estándar", text_color=theme.WARNING)


def mostrar_notificacion(master, texto: str, tipo: str = "info", duracion_ms: int = 2600) -> None:
    """Muestra un toast flotante no bloqueante en la esquina inferior derecha."""
    colores = {
        "info": (theme.ACCENT, theme.ACCENT_SOFT),
        "exito": (theme.SUCCESS, theme.SUCCESS_SOFT),
        "error": (theme.DANGER, theme.DANGER_SOFT),
        "advertencia": (theme.WARNING, theme.WARNING_SOFT),
    }
    borde, fondo = colores.get(tipo, colores["info"])

    toast = ctk.CTkFrame(master, fg_color=fondo, border_color=borde, border_width=1, corner_radius=8)
    ctk.CTkLabel(
        toast, text=texto, font=theme.font_ui(12), text_color=theme.TEXT_PRIMARY, padx=14, pady=10
    ).pack()

    toast.place(relx=0.99, rely=0.95, anchor="se")
    toast.after(duracion_ms, toast.destroy)
