"""Ventanas de diálogo modales usadas por la ventana principal."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme
from .widgets import CampoContrasena, MedidorFortaleza
from ..core.crypto import evaluar_fortaleza
from ..core.exceptions import ValidationError
from ..core.models import EnvironmentVariable, EnvScope


class DialogoBase(ctk.CTkToplevel):
    """Clase base con centrado, modalidad y estilo común para todos los diálogos."""

    def __init__(self, master, titulo: str, ancho: int = 460, alto: int = 320):
        super().__init__(master)
        self.title(titulo)
        self.geometry(f"{ancho}x{alto}")
        self.configure(fg_color=theme.BG_BASE)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self._centrar(master, ancho, alto)

    def _centrar(self, master, ancho: int, alto: int) -> None:
        master.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() - ancho) // 2
        y = master.winfo_y() + (master.winfo_height() - alto) // 2
        self.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")


class DialogoVariable(DialogoBase):
    """Formulario para crear o editar una variable de entorno."""

    def __init__(
        self,
        master,
        on_guardar: Callable[[EnvironmentVariable], None],
        variable: Optional[EnvironmentVariable] = None,
        scope_inicial: EnvScope = EnvScope.USER,
    ):
        editando = variable is not None
        super().__init__(master, "Editar variable" if editando else "Nueva variable", 480, 380)
        self._on_guardar = on_guardar
        self._editando = editando
        self._nombre_original = variable.name if variable else None

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(contenedor, text="Nombre", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.entry_nombre = ctk.CTkEntry(contenedor, font=theme.font_mono(13), placeholder_text="Ej: JAVA_HOME")
        self.entry_nombre.pack(fill="x", pady=(2, 14))
        if variable:
            self.entry_nombre.insert(0, variable.name)
            self.entry_nombre.configure(state="disabled")  # el nombre no se edita, se recrea

        ctk.CTkLabel(contenedor, text="Valor", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.texto_valor = ctk.CTkTextbox(contenedor, font=theme.font_mono(13), height=90)
        self.texto_valor.pack(fill="x", pady=(2, 14))
        if variable:
            self.texto_valor.insert("1.0", variable.value)

        ctk.CTkLabel(contenedor, text="Alcance", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.combo_scope = ctk.CTkOptionMenu(
            contenedor,
            values=[s.etiqueta for s in EnvScope],
            fg_color=theme.BG_SURFACE_ALT,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
        )
        self.combo_scope.set((variable.scope if variable else scope_inicial).etiqueta)
        self.combo_scope.pack(fill="x", pady=(2, 4))
        if editando:
            self.combo_scope.configure(state="disabled")

        self.etiqueta_error = ctk.CTkLabel(contenedor, text="", font=theme.font_ui(11), text_color=theme.DANGER)
        self.etiqueta_error.pack(anchor="w", pady=(6, 0))

        botones = ctk.CTkFrame(contenedor, fg_color="transparent")
        botones.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(
            botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones, text="Guardar", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._guardar,
        ).pack(side="right")

        self.entry_nombre.focus_set()

    def _mapa_scope(self) -> dict:
        return {s.etiqueta: s for s in EnvScope}

    def _guardar(self) -> None:
        nombre = self._nombre_original or self.entry_nombre.get().strip()
        valor = self.texto_valor.get("1.0", "end").rstrip("\n")
        scope = self._mapa_scope()[self.combo_scope.get()]

        try:
            if not self._nombre_original:
                from ..core.env_service import validar_nombre_variable

                validar_nombre_variable(nombre)
            variable = EnvironmentVariable(name=nombre, value=valor, scope=scope)
            self._on_guardar(variable)
            self.destroy()
        except ValidationError as exc:
            self.etiqueta_error.configure(text=str(exc))
        except Exception as exc:  # errores de permisos, etc.
            self.etiqueta_error.configure(text=str(exc))


class DialogoConfirmacion(DialogoBase):
    """Diálogo genérico de confirmación Sí/No."""

    def __init__(self, master, titulo: str, mensaje: str, on_confirmar: Callable[[], None], peligroso: bool = False):
        super().__init__(master, titulo, 420, 200)
        self.on_confirmar = on_confirmar

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            contenedor, text=mensaje, font=theme.font_ui(13), text_color=theme.TEXT_PRIMARY,
            wraplength=370, justify="left",
        ).pack(anchor="w", pady=(0, 20))

        botones = ctk.CTkFrame(contenedor, fg_color="transparent")
        botones.pack(fill="x", side="bottom")
        ctk.CTkButton(
            botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones, text="Eliminar" if peligroso else "Confirmar",
            fg_color=theme.DANGER if peligroso else theme.ACCENT,
            hover_color="#C94747" if peligroso else theme.ACCENT_HOVER,
            command=self._confirmar,
        ).pack(side="right")

    def _confirmar(self) -> None:
        self.destroy()
        self.on_confirmar()


class DialogoCrearRespaldo(DialogoBase):
    """Selecciona alcances, ruta de archivo y contraseña para crear un respaldo cifrado."""

    def __init__(self, master, on_confirmar: Callable[[Path, str, List[EnvScope]], None]):
        super().__init__(master, "Crear respaldo cifrado", 480, 480)
        self._on_confirmar = on_confirmar
        self._ruta: Optional[Path] = None

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(c, text="Alcances a incluir", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.checks = {}
        for scope in EnvScope:
            var = ctk.BooleanVar(value=(scope != EnvScope.SESSION))
            ctk.CTkCheckBox(
                c, text=scope.etiqueta, variable=var, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                font=theme.font_ui(13),
            ).pack(anchor="w", pady=3)
            self.checks[scope] = var

        ctk.CTkLabel(c, text="Archivo de destino", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w", pady=(14, 0))
        fila_ruta = ctk.CTkFrame(c, fg_color="transparent")
        fila_ruta.pack(fill="x", pady=(2, 14))
        self.entry_ruta = ctk.CTkEntry(fila_ruta, font=theme.font_ui(12), placeholder_text="Selecciona una ubicación...")
        self.entry_ruta.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            fila_ruta, text="Explorar", width=90, fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self._elegir_ruta,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(c, text="Clave secreta (recuérdala, no se almacena)", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.campo_pass = CampoContrasena(c)
        self.campo_pass.pack(fill="x", pady=(2, 4))
        self.campo_pass.entry.bind("<KeyRelease>", self._on_pass_cambia)

        self.medidor = MedidorFortaleza(c)
        self.medidor.pack(fill="x")

        ctk.CTkLabel(c, text="Confirmar clave", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w", pady=(10, 0))
        self.campo_pass2 = CampoContrasena(c)
        self.campo_pass2.pack(fill="x", pady=(2, 4))

        self.etiqueta_error = ctk.CTkLabel(c, text="", font=theme.font_ui(11), text_color=theme.DANGER)
        self.etiqueta_error.pack(anchor="w")

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", side="bottom", pady=(10, 0))
        ctk.CTkButton(botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(botones, text="Crear respaldo", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._confirmar).pack(side="right")

    def _on_pass_cambia(self, _event=None) -> None:
        fuerza = evaluar_fortaleza(self.campo_pass.get())
        self.medidor.actualizar(fuerza.score, fuerza.label)

    def _elegir_ruta(self) -> None:
        ruta = filedialog.asksaveasfilename(
            title="Guardar respaldo cifrado",
            defaultextension=".evb",
            filetypes=[("Respaldo cifrado EnvVar", "*.evb"), ("Todos los archivos", "*.*")],
        )
        if ruta:
            self.entry_ruta.delete(0, "end")
            self.entry_ruta.insert(0, ruta)

    def _confirmar(self) -> None:
        scopes = [s for s, v in self.checks.items() if v.get()]
        ruta_txt = self.entry_ruta.get().strip()
        pass1 = self.campo_pass.get()
        pass2 = self.campo_pass2.get()

        if not scopes:
            self.etiqueta_error.configure(text="Selecciona al menos un alcance.")
            return
        if not ruta_txt:
            self.etiqueta_error.configure(text="Selecciona un archivo de destino.")
            return
        if len(pass1) < 8:
            self.etiqueta_error.configure(text="La clave debe tener al menos 8 caracteres.")
            return
        if pass1 != pass2:
            self.etiqueta_error.configure(text="Las claves no coinciden.")
            return

        self.destroy()
        self._on_confirmar(Path(ruta_txt), pass1, scopes)


class DialogoRestaurarRespaldo(DialogoBase):
    """Selecciona archivo cifrado y contraseña, y delega la restauración."""

    def __init__(self, master, on_confirmar: Callable[[Path, str], None]):
        super().__init__(master, "Restaurar respaldo cifrado", 460, 260)
        self._on_confirmar = on_confirmar

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(c, text="Archivo de respaldo", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        fila_ruta = ctk.CTkFrame(c, fg_color="transparent")
        fila_ruta.pack(fill="x", pady=(2, 14))
        self.entry_ruta = ctk.CTkEntry(fila_ruta, font=theme.font_ui(12), placeholder_text="Selecciona un archivo .evb...")
        self.entry_ruta.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            fila_ruta, text="Explorar", width=90, fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self._elegir_archivo,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(c, text="Clave secreta", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.campo_pass = CampoContrasena(c)
        self.campo_pass.pack(fill="x", pady=(2, 4))

        self.etiqueta_error = ctk.CTkLabel(c, text="", font=theme.font_ui(11), text_color=theme.DANGER)
        self.etiqueta_error.pack(anchor="w", pady=(6, 0))

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", side="bottom", pady=(10, 0))
        ctk.CTkButton(botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(botones, text="Ver contenido", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._confirmar).pack(side="right")

        self.campo_pass.entry.bind("<Return>", lambda _e: self._confirmar())

    def _elegir_archivo(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar respaldo cifrado",
            filetypes=[("Respaldo cifrado EnvVar", "*.evb"), ("Todos los archivos", "*.*")],
        )
        if ruta:
            self.entry_ruta.delete(0, "end")
            self.entry_ruta.insert(0, ruta)

    def _confirmar(self) -> None:
        ruta_txt = self.entry_ruta.get().strip()
        password = self.campo_pass.get()
        if not ruta_txt:
            self.etiqueta_error.configure(text="Selecciona un archivo.")
            return
        if not password:
            self.etiqueta_error.configure(text="Ingresa la clave secreta.")
            return
        self.destroy()
        self._on_confirmar(Path(ruta_txt), password)


class DialogoNuevoSecreto(DialogoBase):
    """Formulario para guardar un secreto (token/credencial) en el almacén del SO."""

    def __init__(self, master, on_guardar: Callable[[str, str], None]):
        super().__init__(master, "Nuevo secreto", 460, 300)
        self._on_guardar = on_guardar

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(c, text="Nombre identificador", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.entry_nombre = ctk.CTkEntry(c, font=theme.font_mono(13), placeholder_text="Ej: GITHUB_TOKEN")
        self.entry_nombre.pack(fill="x", pady=(2, 14))

        ctk.CTkLabel(c, text="Valor secreto", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.campo_valor = CampoContrasena(c, placeholder="Token, contraseña o clave...")
        self.campo_valor.pack(fill="x", pady=(2, 4))

        ctk.CTkLabel(
            c, text="Se guardará cifrado en el almacén de credenciales del sistema\n"
            "(Credential Manager / Keychain / Secret Service), no en un archivo de la app.",
            font=theme.font_ui(11), text_color=theme.TEXT_MUTED, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.etiqueta_error = ctk.CTkLabel(c, text="", font=theme.font_ui(11), text_color=theme.DANGER)
        self.etiqueta_error.pack(anchor="w", pady=(6, 0))

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", side="bottom", pady=(10, 0))
        ctk.CTkButton(botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(botones, text="Guardar", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._guardar).pack(side="right")

        self.entry_nombre.focus_set()

    def _guardar(self) -> None:
        nombre = self.entry_nombre.get().strip()
        valor = self.campo_valor.get()
        if not nombre:
            self.etiqueta_error.configure(text="Ingresa un nombre identificador.")
            return
        if not valor:
            self.etiqueta_error.configure(text="Ingresa el valor secreto.")
            return
        try:
            self._on_guardar(nombre, valor)
            self.destroy()
        except Exception as exc:
            self.etiqueta_error.configure(text=str(exc))


class DialogoVerSecreto(DialogoBase):
    """Muestra el valor de un secreto bajo demanda, con copia rápida al portapapeles."""

    def __init__(self, master, nombre: str, valor: str, on_editar: Optional[Callable[[], None]] = None):
        super().__init__(master, f"Secreto: {nombre}", 480, 220)

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(c, text=nombre, font=theme.font_ui(13, "bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")

        campo = ctk.CTkTextbox(c, font=theme.font_mono(13), height=70)
        campo.insert("1.0", valor)
        campo.configure(state="disabled")
        campo.pack(fill="x", pady=(8, 14))

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", side="bottom")
        ctk.CTkButton(botones, text="Cerrar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy).pack(side="right", padx=(8, 0))
        if on_editar:
            def _editar_accion():
                self.destroy()
                on_editar()

            ctk.CTkButton(
                botones, text="✏️ Editar...", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
                command=_editar_accion,
            ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones, text="Copiar valor", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=lambda: (self.clipboard_clear(), self.clipboard_append(valor)),
        ).pack(side="right")


class DialogoEditarSecreto(DialogoBase):
    """Formulario para actualizar el valor de un secreto existente en el almacén del SO."""

    def __init__(
        self,
        master,
        nombre: str,
        valor_inicial: str,
        on_guardar: Callable[[str], None],
    ):
        super().__init__(master, "Editar secreto — EnvVarManager Pro", 480, 280)
        self._nombre = nombre
        self._on_guardar = on_guardar

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            c,
            text="Actualizar credencial en el almacén seguro del SO",
            font=theme.font_ui(11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(c, text="Nombre del secreto", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.entry_nombre = ctk.CTkEntry(c, font=theme.font_mono(13))
        self.entry_nombre.insert(0, nombre)
        self.entry_nombre.configure(state="disabled")
        self.entry_nombre.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(c, text="Nuevo valor secreto", font=theme.font_ui(12), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        self.campo_valor = CampoContrasena(c, placeholder="Nuevo token o contraseña...")
        if valor_inicial:
            self.campo_valor.entry.insert(0, valor_inicial)
        self.campo_valor.pack(fill="x", pady=(2, 4))

        self.etiqueta_error = ctk.CTkLabel(c, text="", font=theme.font_ui(11), text_color=theme.DANGER)
        self.etiqueta_error.pack(anchor="w", pady=(4, 0))

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", side="bottom", pady=(6, 0))
        ctk.CTkButton(
            botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones, text="Guardar cambios", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._guardar
        ).pack(side="right")

        self.campo_valor.focus()

    def _guardar(self) -> None:
        nuevo_valor = self.campo_valor.get()
        try:
            self._on_guardar(nuevo_valor)
            self.destroy()
        except Exception as exc:
            self.etiqueta_error.configure(text=str(exc))


class DialogoPrevisualizarRestauracion(DialogoBase):
    """Muestra el contenido descifrado del respaldo con checkboxes antes de aplicarlo."""

    def __init__(self, master, variables: List[EnvironmentVariable], metadata: str, on_aplicar: Callable[[List[EnvironmentVariable]], None]):
        super().__init__(master, "Previsualizar restauración", 560, 560)
        self._on_aplicar = on_aplicar
        self._variables = variables
        self._checks: List[ctk.BooleanVar] = []

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(c, text=metadata, font=theme.font_ui(11), text_color=theme.TEXT_SECONDARY).pack(anchor="w", pady=(0, 10))

        marco_lista = ctk.CTkScrollableFrame(c, fg_color=theme.BG_SURFACE, height=380)
        marco_lista.pack(fill="both", expand=True)

        for var in variables:
            fila = ctk.CTkFrame(marco_lista, fg_color="transparent")
            fila.pack(fill="x", pady=3)
            chk_var = ctk.BooleanVar(value=True)
            self._checks.append(chk_var)
            ctk.CTkCheckBox(fila, text="", variable=chk_var, width=20, fg_color=theme.ACCENT).pack(side="left")
            texto = f"[{var.scope.etiqueta}]  {var.name} = {var.value}"
            if len(texto) > 78:
                texto = texto[:75] + "..."
            ctk.CTkLabel(fila, text=texto, font=theme.font_mono(11), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True)

        botones = ctk.CTkFrame(c, fg_color="transparent")
        botones.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(botones, text="Cancelar", fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones, text="Aplicar seleccionadas", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._aplicar,
        ).pack(side="right")

    def _aplicar(self) -> None:
        seleccionadas = [v for v, chk in zip(self._variables, self._checks) if chk.get()]
        self.destroy()
        self._on_aplicar(seleccionadas)
