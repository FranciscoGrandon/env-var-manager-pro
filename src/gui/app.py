"""Ventana principal de EnvVar Manager Pro."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

import customtkinter as ctk

from . import theme
from .dialogs import (
    DialogoConfirmacion,
    DialogoCrearRespaldo,
    DialogoEditarSecreto,
    DialogoNuevoSecreto,
    DialogoPrevisualizarRestauracion,
    DialogoRestaurarRespaldo,
    DialogoVariable,
    DialogoVerSecreto,
)
from .widgets import BarraEstado, mostrar_notificacion
from .. import __version__
from ..core.backup_service import BackupService
from ..core.crypto import CryptoService
from ..core.env_service import EnvironmentVariableService
from ..core.exceptions import EnvManagerError, InvalidPasswordError
from ..core.models import EnvironmentVariable, EnvScope
from ..core.secrets_service import SecretsService
from ..utils.logger_config import get_logger

logger = get_logger(__name__)


class VentanaPrincipal(ctk.CTk):
    def __init__(self):
        super().__init__()
        theme.aplicar_tema()

        self.title(f"EnvVar Manager Pro  ·  v{__version__}")
        self.geometry("1180x720")
        self.minsize(920, 560)
        self.configure(fg_color=theme.BG_BASE)

        # Configurar icono de la aplicación
        icon_path = Path(__file__).resolve().parent / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(icon_path)
            except Exception as e:
                logger.warning("No se pudo cargar el icono del sistema: %s", e)

        self._env_service = EnvironmentVariableService()
        self._crypto = CryptoService()
        self._backup_service = BackupService(self._env_service, self._crypto)
        self._secrets_service = SecretsService()

        self._scope_actual: EnvScope = EnvScope.USER
        self._variables_cache: Dict[str, str] = {}
        self._vista_actual = "variables"  # "variables" | "secretos"

        self._construir_layout()
        self._cargar_variables()

    # ------------------------------------------------------------ layout

    def _construir_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_sidebar()

        self._contenedor_contenido = ctk.CTkFrame(self, fg_color=theme.BG_BASE, corner_radius=0)
        self._contenedor_contenido.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self._contenedor_contenido.grid_rowconfigure(1, weight=1)
        self._contenedor_contenido.grid_columnconfigure(0, weight=1)

        self._construir_vista_variables()
        self._construir_vista_secretos()
        self._mostrar_vista("variables")

        self.barra_estado = BarraEstado(self)
        self.barra_estado.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.barra_estado.set_admin(self._env_service.es_admin())

    def _construir_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, fg_color=theme.BG_SURFACE, width=210, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar, text="EnvVar Manager", font=theme.font_titulo(), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(
            sidebar, text="Pro", font=theme.font_subtitulo(), text_color=theme.ACCENT
        ).pack(anchor="w", padx=20, pady=(0, 24))

        ctk.CTkLabel(
            sidebar, text="VARIABLES DE ENTORNO", font=theme.font_ui(10, "bold"), text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self._botones_scope: Dict[EnvScope, ctk.CTkButton] = {}
        for scope in EnvScope:
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {scope.etiqueta}",
                anchor="w",
                font=theme.font_ui(13),
                fg_color="transparent",
                hover_color=theme.BG_SURFACE_ALT,
                text_color=theme.TEXT_SECONDARY,
                corner_radius=6,
                height=38,
                command=lambda s=scope: self._cambiar_scope(s),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._botones_scope[scope] = btn

        ctk.CTkFrame(sidebar, fg_color=theme.BORDER, height=1).pack(fill="x", padx=16, pady=18)

        ctk.CTkLabel(
            sidebar, text="RESPALDO CIFRADO", font=theme.font_ui(10, "bold"), text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        ctk.CTkButton(
            sidebar, text="⤓  Crear respaldo", anchor="w", font=theme.font_ui(13),
            fg_color="transparent", hover_color=theme.BG_SURFACE_ALT, text_color=theme.TEXT_PRIMARY,
            corner_radius=6, height=38, command=self._abrir_dialogo_crear_respaldo,
        ).pack(fill="x", padx=12, pady=2)

        ctk.CTkButton(
            sidebar, text="⤒  Restaurar respaldo", anchor="w", font=theme.font_ui(13),
            fg_color="transparent", hover_color=theme.BG_SURFACE_ALT, text_color=theme.TEXT_PRIMARY,
            corner_radius=6, height=38, command=self._abrir_dialogo_restaurar,
        ).pack(fill="x", padx=12, pady=2)

        ctk.CTkFrame(sidebar, fg_color=theme.BORDER, height=1).pack(fill="x", padx=16, pady=18)

        ctk.CTkLabel(
            sidebar, text="SECRETOS (KEYRING)", font=theme.font_ui(10, "bold"), text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self._boton_secretos = ctk.CTkButton(
            sidebar, text="🔐  Tokens y credenciales", anchor="w", font=theme.font_ui(13),
            fg_color="transparent", hover_color=theme.BG_SURFACE_ALT, text_color=theme.TEXT_SECONDARY,
            corner_radius=6, height=38, command=self._mostrar_secretos,
        )
        self._boton_secretos.pack(fill="x", padx=12, pady=2)

        self._actualizar_resaltado_sidebar()

    def _actualizar_resaltado_sidebar(self) -> None:
        for scope, btn in self._botones_scope.items():
            activo = self._vista_actual == "variables" and scope is self._scope_actual
            btn.configure(
                fg_color=theme.ACCENT_SOFT if activo else "transparent",
                text_color=theme.TEXT_PRIMARY if activo else theme.TEXT_SECONDARY,
            )
        activo_secretos = self._vista_actual == "secretos"
        self._boton_secretos.configure(
            fg_color=theme.ACCENT_SOFT if activo_secretos else "transparent",
            text_color=theme.TEXT_PRIMARY if activo_secretos else theme.TEXT_SECONDARY,
        )

    def _mostrar_vista(self, vista: str) -> None:
        self._vista_actual = vista
        if vista == "variables":
            self._frame_secretos.grid_remove()
            self._frame_variables.grid(row=0, column=0, rowspan=2, sticky="nsew")
        else:
            self._frame_variables.grid_remove()
            self._frame_secretos.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._actualizar_resaltado_sidebar()

    # ------------------------------------------------------------ vista: variables

    def _construir_vista_variables(self) -> None:
        self._frame_variables = ctk.CTkFrame(self._contenedor_contenido, fg_color=theme.BG_BASE, corner_radius=0)
        self._frame_variables.grid_rowconfigure(1, weight=1)
        self._frame_variables.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self._frame_variables, fg_color=theme.BG_BASE, height=64, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        self.titulo_scope = ctk.CTkLabel(
            top, text=self._scope_actual.etiqueta, font=theme.font_titulo(), text_color=theme.TEXT_PRIMARY
        )
        self.titulo_scope.pack(side="left", padx=24, pady=14)

        contenedor_derecha = ctk.CTkFrame(top, fg_color="transparent")
        contenedor_derecha.pack(side="right", padx=20)

        ctk.CTkButton(
            contenedor_derecha, text="＋ Nueva variable", font=theme.font_ui(13, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, width=150,
            command=self._abrir_dialogo_nueva_variable,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            contenedor_derecha, text="↻", width=36, font=theme.font_ui(15),
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self._cargar_variables,
        ).pack(side="right", padx=(8, 0))

        self.entry_busqueda = ctk.CTkEntry(
            contenedor_derecha, placeholder_text="Buscar variable...", width=220, font=theme.font_ui(13)
        )
        self.entry_busqueda.pack(side="right", padx=(8, 0))
        self.entry_busqueda.bind("<KeyRelease>", lambda _e: self._filtrar_tabla())

        contenedor_tabla = ctk.CTkFrame(self._frame_variables, fg_color=theme.BG_BASE, corner_radius=0)
        contenedor_tabla.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        contenedor_tabla.grid_columnconfigure(0, weight=1)
        contenedor_tabla.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        theme.estilo_treeview(style)

        columnas = ("nombre", "valor")
        self.tabla = ttk.Treeview(
            contenedor_tabla, columns=columnas, show="headings", style="Custom.Treeview", selectmode="browse"
        )
        self.tabla.heading("nombre", text="NOMBRE")
        self.tabla.heading("valor", text="VALOR")
        self.tabla.column("nombre", width=300, anchor="w")
        self.tabla.column("valor", width=640, anchor="w")
        self.tabla.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(contenedor_tabla, orient="vertical", command=self.tabla.yview, style="Custom.Vertical.TScrollbar")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scrollbar.set)

        self.tabla.bind("<Double-1>", lambda _e: self._editar_seleccion())

        menu = tk.Menu(self, tearoff=0, bg=theme.BG_SURFACE, fg=theme.TEXT_PRIMARY, activebackground=theme.ACCENT)
        menu.add_command(label="Editar", command=self._editar_seleccion)
        menu.add_command(label="Copiar valor", command=self._copiar_valor_seleccion)
        menu.add_command(label="Copiar nombre", command=self._copiar_nombre_seleccion)
        menu.add_separator()
        menu.add_command(label="Eliminar", command=self._eliminar_seleccion)
        self._menu_contextual = menu

        def abrir_menu(event):
            item = self.tabla.identify_row(event.y)
            if item:
                self.tabla.selection_set(item)
                menu.tk_popup(event.x_root, event.y_root)

        self.tabla.bind("<Button-3>", abrir_menu)

    # ------------------------------------------------------------ vista: secretos

    def _construir_vista_secretos(self) -> None:
        self._frame_secretos = ctk.CTkFrame(self._contenedor_contenido, fg_color=theme.BG_BASE, corner_radius=0)
        self._frame_secretos.grid_rowconfigure(1, weight=1)
        self._frame_secretos.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self._frame_secretos, fg_color=theme.BG_BASE, height=64, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        ctk.CTkLabel(
            top, text="Secretos (Keyring del sistema)", font=theme.font_titulo(), text_color=theme.TEXT_PRIMARY
        ).pack(side="left", padx=24, pady=14)

        frame_acciones = ctk.CTkFrame(top, fg_color="transparent")
        frame_acciones.pack(side="right", padx=20)

        ctk.CTkButton(
            frame_acciones, text="＋ Nuevo secreto", font=theme.font_ui(13, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, width=150,
            command=self._abrir_dialogo_nuevo_secreto,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            frame_acciones, text="✏️ Editar", font=theme.font_ui(13),
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER, width=100,
            command=self._editar_secreto_seleccionado,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            frame_acciones, text="↻", width=36, font=theme.font_ui(15),
            fg_color=theme.BG_SURFACE_ALT, hover_color=theme.BORDER,
            command=self._cargar_secretos,
        ).pack(side="right", padx=(8, 0))

        aviso = ctk.CTkFrame(self._frame_secretos, fg_color=theme.ACCENT_SOFT, corner_radius=8, border_color=theme.ACCENT, border_width=1)
        aviso.grid(row=1, column=0, sticky="new", padx=20, pady=(0, 10))
        self._etiqueta_backend = ctk.CTkLabel(
            aviso, text="", font=theme.font_ui(11), text_color=theme.TEXT_SECONDARY, justify="left", wraplength=900,
        )
        self._etiqueta_backend.pack(anchor="w", padx=14, pady=8)

        contenedor_tabla = ctk.CTkFrame(self._frame_secretos, fg_color=theme.BG_BASE, corner_radius=0)
        contenedor_tabla.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 12))
        contenedor_tabla.grid_columnconfigure(0, weight=1)
        contenedor_tabla.grid_rowconfigure(0, weight=1)
        self._frame_secretos.grid_rowconfigure(2, weight=1)

        style = ttk.Style()
        theme.estilo_treeview(style)

        self.tabla_secretos = ttk.Treeview(
            contenedor_tabla, columns=("nombre", "estado"), show="headings", style="Custom.Treeview", selectmode="browse"
        )
        self.tabla_secretos.heading("nombre", text="NOMBRE")
        self.tabla_secretos.heading("estado", text="ESTADO")
        self.tabla_secretos.column("nombre", width=400, anchor="w")
        self.tabla_secretos.column("estado", width=200, anchor="w")
        self.tabla_secretos.grid(row=0, column=0, sticky="nsew")

        scrollbar2 = ttk.Scrollbar(contenedor_tabla, orient="vertical", command=self.tabla_secretos.yview, style="Custom.Vertical.TScrollbar")
        scrollbar2.grid(row=0, column=1, sticky="ns")
        self.tabla_secretos.configure(yscrollcommand=scrollbar2.set)

        self.tabla_secretos.bind("<Double-1>", lambda _e: self._ver_secreto_seleccionado())

        menu_secretos = tk.Menu(self, tearoff=0, bg=theme.BG_SURFACE, fg=theme.TEXT_PRIMARY, activebackground=theme.ACCENT)
        menu_secretos.add_command(label="Ver / copiar valor", command=self._ver_secreto_seleccionado)
        menu_secretos.add_command(label="✏️ Editar valor", command=self._editar_secreto_seleccionado)
        menu_secretos.add_separator()
        menu_secretos.add_command(label="Eliminar", command=self._eliminar_secreto_seleccionado)
        self._menu_secretos = menu_secretos

        def abrir_menu_secretos(event):
            item = self.tabla_secretos.identify_row(event.y)
            if item:
                self.tabla_secretos.selection_set(item)
                menu_secretos.tk_popup(event.x_root, event.y_root)

        self.tabla_secretos.bind("<Button-3>", abrir_menu_secretos)

    def _mostrar_secretos(self) -> None:
        self._mostrar_vista("secretos")
        self._cargar_secretos()

    def _cargar_secretos(self) -> None:
        backend = self._secrets_service.backend_activo()
        self._etiqueta_backend.configure(
            text=f"Almacén activo: {backend}\n"
            "Los valores se cifran y controlan por el sistema operativo, no por esta aplicación."
        )
        self.tabla_secretos.delete(*self.tabla_secretos.get_children())
        nombres = self._secrets_service.listar_nombres()
        for nombre in nombres:
            self.tabla_secretos.insert("", "end", iid=nombre, values=(nombre, "●  Guardado en el SO"))
        self.barra_estado.set_mensaje(f"{len(nombres)} secretos registrados")

    def _abrir_dialogo_nuevo_secreto(self) -> None:
        def guardar(nombre: str, valor: str):
            try:
                self._secrets_service.guardar(nombre, valor)
                mostrar_notificacion(self, f"Secreto '{nombre}' guardado en el SO", tipo="exito")
                self._cargar_secretos()
            except EnvManagerError as exc:
                messagebox.showerror("No se pudo guardar el secreto", str(exc))
                raise

        DialogoNuevoSecreto(self, on_guardar=guardar)

    def _secreto_seleccionado(self) -> Optional[str]:
        seleccion = self.tabla_secretos.selection()
        return seleccion[0] if seleccion else None

    def _ver_secreto_seleccionado(self) -> None:
        nombre = self._secreto_seleccionado()
        if not nombre:
            return
        try:
            valor = self._secrets_service.obtener(nombre)
        except EnvManagerError as exc:
            messagebox.showerror("No se pudo leer el secreto", str(exc))
            return
        if valor is None:
            messagebox.showwarning("Secreto no encontrado", "El valor ya no existe en el almacén del sistema.")
            self._cargar_secretos()
            return
        DialogoVerSecreto(self, nombre, valor, on_editar=self._editar_secreto_seleccionado)

    def _editar_secreto_seleccionado(self) -> None:
        nombre = self._secreto_seleccionado()
        if not nombre:
            mostrar_notificacion(self, "Selecciona un secreto para editar", tipo="advertencia")
            return
        try:
            valor_actual = self._secrets_service.obtener(nombre) or ""
        except EnvManagerError as exc:
            messagebox.showerror("No se pudo leer el secreto", str(exc))
            return

        def on_guardar(nuevo_valor: str) -> None:
            self._secrets_service.actualizar(nombre, nuevo_valor)
            mostrar_notificacion(self, f"Secreto '{nombre}' actualizado", tipo="exito")
            self._cargar_secretos()

        DialogoEditarSecreto(self, nombre=nombre, valor_inicial=valor_actual, on_guardar=on_guardar)

    def _eliminar_secreto_seleccionado(self) -> None:
        nombre = self._secreto_seleccionado()
        if not nombre:
            return

        def confirmar():
            try:
                self._secrets_service.eliminar(nombre)
                mostrar_notificacion(self, f"Secreto '{nombre}' eliminado", tipo="advertencia")
                self._cargar_secretos()
            except EnvManagerError as exc:
                messagebox.showerror("No se pudo eliminar", str(exc))

        DialogoConfirmacion(
            self, "Eliminar secreto",
            f"¿Eliminar el secreto '{nombre}' del almacén del sistema operativo?\nEsta acción no se puede deshacer.",
            confirmar, peligroso=True,
        )

    # ------------------------------------------------------------ datos: variables

    def _cambiar_scope(self, scope: EnvScope) -> None:
        self._scope_actual = scope
        self._mostrar_vista("variables")
        self.titulo_scope.configure(text=scope.etiqueta)
        self._cargar_variables()

    def _cargar_variables(self) -> None:
        try:
            self._variables_cache = self._env_service.listar(self._scope_actual)
            self._filtrar_tabla()
            self.barra_estado.set_mensaje(f"{len(self._variables_cache)} variables cargadas · {self._scope_actual.etiqueta}")
        except EnvManagerError as exc:
            self.barra_estado.set_mensaje(str(exc), es_error=True)
            messagebox.showerror("Error al cargar variables", str(exc))

    def _filtrar_tabla(self) -> None:
        filtro = self.entry_busqueda.get().strip().lower() if hasattr(self, "entry_busqueda") else ""
        self.tabla.delete(*self.tabla.get_children())
        for nombre, valor in sorted(self._variables_cache.items()):
            if filtro and filtro not in nombre.lower() and filtro not in valor.lower():
                continue
            self.tabla.insert("", "end", iid=nombre, values=(nombre, valor))

    def _variable_seleccionada(self) -> Optional[EnvironmentVariable]:
        seleccion = self.tabla.selection()
        if not seleccion:
            return None
        nombre = seleccion[0]
        valor = self._variables_cache.get(nombre, "")
        return EnvironmentVariable(name=nombre, value=valor, scope=self._scope_actual)

    # ------------------------------------------------------------ acciones CRUD: variables

    def _abrir_dialogo_nueva_variable(self) -> None:
        DialogoVariable(self, on_guardar=self._guardar_variable, scope_inicial=self._scope_actual)

    def _editar_seleccion(self) -> None:
        var = self._variable_seleccionada()
        if not var:
            return
        DialogoVariable(self, on_guardar=self._guardar_variable, variable=var)

    def _guardar_variable(self, variable: EnvironmentVariable) -> None:
        try:
            self._env_service.establecer(variable.name, variable.value, variable.scope)
            mostrar_notificacion(self, f"Variable '{variable.name}' guardada", tipo="exito")
            if variable.scope is self._scope_actual:
                self._cargar_variables()
        except EnvManagerError as exc:
            messagebox.showerror("No se pudo guardar", str(exc))
            raise

    def _eliminar_seleccion(self) -> None:
        var = self._variable_seleccionada()
        if not var:
            return

        def confirmar():
            try:
                self._env_service.eliminar(var.name, var.scope)
                mostrar_notificacion(self, f"Variable '{var.name}' eliminada", tipo="advertencia")
                self._cargar_variables()
            except EnvManagerError as exc:
                messagebox.showerror("No se pudo eliminar", str(exc))

        DialogoConfirmacion(
            self,
            "Eliminar variable",
            f"¿Eliminar la variable '{var.name}' del alcance {var.scope.etiqueta}?\nEsta acción no se puede deshacer.",
            confirmar,
            peligroso=True,
        )

    def _copiar_valor_seleccion(self) -> None:
        var = self._variable_seleccionada()
        if var:
            self.clipboard_clear()
            self.clipboard_append(var.value)
            mostrar_notificacion(self, "Valor copiado al portapapeles", tipo="info")

    def _copiar_nombre_seleccion(self) -> None:
        var = self._variable_seleccionada()
        if var:
            self.clipboard_clear()
            self.clipboard_append(var.name)
            mostrar_notificacion(self, "Nombre copiado al portapapeles", tipo="info")

    # ------------------------------------------------------------ respaldo / restauración

    def _abrir_dialogo_crear_respaldo(self) -> None:
        DialogoCrearRespaldo(self, on_confirmar=self._crear_respaldo)

    def _crear_respaldo(self, ruta, password: str, scopes: List[EnvScope]) -> None:
        try:
            cantidad = self._backup_service.crear_respaldo(ruta, password, scopes)
            mostrar_notificacion(self, f"Respaldo creado: {cantidad} variables", tipo="exito")
            self.barra_estado.set_mensaje(f"Respaldo guardado en {ruta}")
        except Exception as exc:
            logger.exception("Error al crear respaldo")
            messagebox.showerror("Error al crear respaldo", str(exc))

    def _abrir_dialogo_restaurar(self) -> None:
        DialogoRestaurarRespaldo(self, on_confirmar=self._previsualizar_restauracion)

    def _previsualizar_restauracion(self, ruta, password: str) -> None:
        try:
            payload = self._backup_service.previsualizar_respaldo(ruta, password)
        except InvalidPasswordError as exc:
            messagebox.showerror("Clave incorrecta", str(exc))
            return
        except Exception as exc:
            logger.exception("Error al leer respaldo")
            messagebox.showerror("Error al leer respaldo", str(exc))
            return

        metadata = (
            f"Creado: {payload.created_at}   ·   Equipo: {payload.hostname}   ·   "
            f"Versión app: {payload.app_version}   ·   {len(payload.variables)} variables"
        )
        DialogoPrevisualizarRestauracion(self, payload.variables, metadata, self._aplicar_restauracion)

    def _aplicar_restauracion(self, variables: List[EnvironmentVariable]) -> None:
        if not variables:
            mostrar_notificacion(self, "No se seleccionó ninguna variable", tipo="advertencia")
            return

        aplicadas, errores = self._backup_service.restaurar_respaldo(None, variables)  # type: ignore[arg-type]
        if errores:
            messagebox.showwarning(
                "Restauración parcial",
                f"Se aplicaron {aplicadas} de {len(variables)} variables.\n\nErrores:\n" + "\n".join(errores),
            )
        else:
            mostrar_notificacion(self, f"{aplicadas} variables restauradas correctamente", tipo="exito")
        self._cargar_variables()


def ejecutar_aplicacion() -> None:
    app = VentanaPrincipal()
    app.mainloop()
