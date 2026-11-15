#!/usr/bin/env python3
"""
keyring_secrets_gui.py — Interfaz Gráfica Dedicada para Gestión de Secretos Keyring.

Creado por Francisco Grandón Vergara

Diseñada con estricta adherencia a:
1. Paleta clara de alto contraste (Corporate Light UI, sin modo oscuro).
2. Reglas de Tkinter/ttk:
   - Tamaños de fuente exclusivamente enteros.
   - Sin 'background=' directo en widgets temáticos ttk (uso de ttk.Style y tk.Frame).
3. Operaciones CRUD completas sobre el almacén de credenciales nativo del SO (Windows Credential Locker).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Optional, List, Dict

# Asegurar importación de src dentro de env_var_manager
DIRECTORIO_RAIZ = Path(__file__).resolve().parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from src.core.exceptions import EnvManagerError, InvalidPasswordError, CorruptedBackupError
from src.core.secrets_service import SecretsService, KEYRING_DISPONIBLE
from src.core.keyring_backup_service import KeyringBackupService

# ==============================================================================
# Paleta Clara Corporate Light UI
# ==============================================================================
COLOR_NAVY   = "#0E2E63"  # Header, títulos y textos principales
COLOR_BLUE   = "#1652A8"  # Botones primarios
COLOR_SKY    = "#00AEEF"  # Acentos, foco, selecciones
COLOR_ORANGE = "#F26522"  # Alertas, destacados
COLOR_BG     = "#F0F4F9"  # Fondo de la ventana principal
COLOR_CARD   = "#FFFFFF"  # Paneles y tarjetas
COLOR_BORDER = "#DCE7F5"  # Bordes suaves
COLOR_TEXT   = "#0E2E63"  # Texto principal
COLOR_MUTED  = "#5A6E85"  # Texto secundario / metadatos
COLOR_GREEN  = "#2FA36B"  # Éxito / estado guardado
COLOR_RED    = "#E2453C"  # Error / acción de eliminar
COLOR_HOVER  = "#124085"  # Hover primario
COLOR_LIGHT_HOVER = "#E3EDFA" # Hover en filas o botones secundarios


class DialogoModalBase(tk.Toplevel):
    """Ventana modal centrada con estilo Corporate Light UI."""

    def __init__(self, parent, titulo: str, ancho: int, alto: int):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=COLOR_CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Centrar sobre el parent
        parent.update_idletasks()
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + max(0, (pw - ancho) // 2)
        y = py + max(0, (ph - alto) // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")


class DialogoNuevoEditarSecreto(DialogoModalBase):
    """Modal para crear o actualizar un secreto con control de visibilidad."""

    def __init__(self, parent, service: SecretsService, nombre_inicial: str = "", es_edicion: bool = False, on_guardado=None):
        super().__init__(parent, "Editar Secreto en Keyring" if es_edicion else "Nuevo Secreto en Keyring", 480, 360)
        self.service = service
        self.es_edicion = es_edicion
        self.on_guardado = on_guardado
        self.mostrar_clave = False

        # Header modal
        header = tk.Frame(self, bg=COLOR_NAVY, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_tit = tk.Label(
            header,
            text="✏️  Editar Secreto" if es_edicion else "➕  Registrar Nuevo Secreto",
            font=("Segoe UI", 12, "bold"),
            bg=COLOR_NAVY,
            fg="#FFFFFF"
        )
        lbl_tit.pack(side="left", padx=16, pady=14)

        cuerpo = tk.Frame(self, bg=COLOR_CARD, padx=24, pady=18)
        cuerpo.pack(fill="both", expand=True)

        # Nombre
        lbl_nom = tk.Label(cuerpo, text="Nombre identificador (Clave):", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_nom.pack(anchor="w")

        self.txt_nombre = tk.Entry(
            cuerpo,
            font=("Consolas", 11),
            bg="#F7FAFD" if not es_edicion else "#EDF2F7",
            fg=COLOR_NAVY,
            relief="solid",
            bd=1,
            highlightthickness=0
        )
        self.txt_nombre.pack(fill="x", pady=(4, 12), ipady=4)
        if nombre_inicial:
            self.txt_nombre.insert(0, nombre_inicial)
            if es_edicion:
                self.txt_nombre.configure(state="readonly")

        # Valor
        lbl_val = tk.Label(cuerpo, text="Valor secreto (Token, Contraseña o API Key):", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_val.pack(anchor="w")

        frame_val = tk.Frame(cuerpo, bg=COLOR_CARD)
        frame_val.pack(fill="x", pady=(4, 8))

        self.txt_valor = tk.Entry(
            frame_val,
            font=("Consolas", 11),
            show="●",
            bg="#F7FAFD",
            fg=COLOR_NAVY,
            relief="solid",
            bd=1,
            highlightthickness=0
        )
        self.txt_valor.pack(side="left", fill="x", expand=True, ipady=4)

        self.btn_ojo = tk.Button(
            frame_val,
            text="👁️",
            font=("Segoe UI", 10),
            bg=COLOR_BORDER,
            fg=COLOR_NAVY,
            relief="flat",
            activebackground=COLOR_SKY,
            cursor="hand2",
            width=3,
            command=self._toggle_ver
        )
        self.btn_ojo.pack(side="left", padx=(6, 0), ipady=2)

        if es_edicion and nombre_inicial:
            try:
                v_actual = self.service.obtener(nombre_inicial)
                if v_actual:
                    self.txt_valor.insert(0, v_actual)
            except EnvManagerError as exc:
                print(f"Advertencia: no se pudo precargar el secreto '{nombre_inicial}': {exc}", file=sys.stderr)

        # Explicación de seguridad
        lbl_seg = tk.Label(
            cuerpo,
            text="🔒 Se almacena cifrado por Windows Credential Locker en su cuenta de usuario.\nNunca se guarda en texto plano en archivos de configuración.",
            font=("Segoe UI", 8),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            justify="left"
        )
        lbl_seg.pack(anchor="w", pady=(2, 14))

        # Botonera
        footer = tk.Frame(cuerpo, bg=COLOR_CARD)
        footer.pack(fill="x", side="bottom")

        btn_cancelar = tk.Button(
            footer,
            text="Cancelar",
            font=("Segoe UI", 10),
            bg="#E2E8F0",
            fg=COLOR_NAVY,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=4,
            command=self.destroy
        )
        btn_cancelar.pack(side="right", padx=(8, 0))

        btn_guardar = tk.Button(
            footer,
            text="Guardar en Keyring",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BLUE,
            fg="#FFFFFF",
            activebackground=COLOR_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=4,
            command=self._guardar
        )
        btn_guardar.pack(side="right")

        if not es_edicion:
            self.txt_nombre.focus_set()
        else:
            self.txt_valor.focus_set()

    def _toggle_ver(self):
        self.mostrar_clave = not self.mostrar_clave
        self.txt_valor.configure(show="" if self.mostrar_clave else "●")
        self.btn_ojo.configure(text="🔒" if self.mostrar_clave else "👁️")

    def _guardar(self):
        nombre = self.txt_nombre.get().strip()
        valor = self.txt_valor.get()

        if not nombre:
            messagebox.showwarning("Dato requerido", "Debe ingresar el nombre del secreto.", parent=self)
            self.txt_nombre.focus_set()
            return
        if not valor:
            messagebox.showwarning("Dato requerido", "Debe ingresar un valor para el secreto.", parent=self)
            self.txt_valor.focus_set()
            return

        try:
            if self.es_edicion:
                self.service.actualizar(nombre, valor)
            else:
                if self.service.existe(nombre):
                    r = messagebox.askyesno(
                        "Secreto existente",
                        f"El secreto '{nombre}' ya existe en el almacén.\n¿Desea sobrescribirlo con el nuevo valor?",
                        parent=self
                    )
                    if not r:
                        return
                    self.service.actualizar(nombre, valor)
                else:
                    self.service.guardar(nombre, valor)

            if self.on_guardado:
                self.on_guardado(nombre)
            self.destroy()
        except EnvManagerError as exc:
            messagebox.showerror("Error al guardar", str(exc), parent=self)


class DialogoVerSecreto(DialogoModalBase):
    """Muestra el valor descifrado con opción de copiar al portapapeles y editar."""

    def __init__(self, parent, service: SecretsService, nombre: str, on_editar=None):
        super().__init__(parent, f"Secreto: {nombre}", 480, 260)
        self.service = service
        self.nombre = nombre
        self.on_editar = on_editar

        valor = self.service.obtener(nombre) or ""

        header = tk.Frame(self, bg=COLOR_NAVY, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_tit = tk.Label(
            header,
            text=f"🔐  {nombre}",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_NAVY,
            fg="#FFFFFF"
        )
        lbl_tit.pack(side="left", padx=16, pady=12)

        cuerpo = tk.Frame(self, bg=COLOR_CARD, padx=20, pady=16)
        cuerpo.pack(fill="both", expand=True)

        lbl_info = tk.Label(
            cuerpo,
            text=f"Longitud: {len(valor)} caracteres · Almacén: Windows Credential Locker",
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_MUTED
        )
        lbl_info.pack(anchor="w", pady=(0, 6))

        txt_box = tk.Text(
            cuerpo,
            font=("Consolas", 11),
            height=4,
            bg="#F7FAFD",
            fg=COLOR_NAVY,
            relief="solid",
            bd=1,
            wrap="char"
        )
        txt_box.pack(fill="both", expand=True, pady=(0, 14))
        txt_box.insert("1.0", valor)
        txt_box.configure(state="disabled")

        footer = tk.Frame(cuerpo, bg=COLOR_CARD)
        footer.pack(fill="x", side="bottom")

        btn_cerrar = tk.Button(
            footer,
            text="Cerrar",
            font=("Segoe UI", 10),
            bg="#E2E8F0",
            fg=COLOR_NAVY,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=4,
            command=self.destroy
        )
        btn_cerrar.pack(side="right", padx=(8, 0))

        if self.on_editar:
            btn_edit = tk.Button(
                footer,
                text="✏️  Editar...",
                font=("Segoe UI", 10),
                bg=COLOR_BORDER,
                fg=COLOR_NAVY,
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=4,
                command=self._ir_a_editar
            )
            btn_edit.pack(side="right", padx=(8, 0))

        btn_copiar = tk.Button(
            footer,
            text="📋  Copiar Valor",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BLUE,
            fg="#FFFFFF",
            activebackground=COLOR_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=4,
            command=lambda: self._copiar(valor)
        )
        btn_copiar.pack(side="right")

    def _copiar(self, valor: str):
        self.clipboard_clear()
        self.clipboard_append(valor)
        messagebox.showinfo("Copiado", f"El valor de '{self.nombre}' ha sido copiado al portapapeles.", parent=self)

    def _ir_a_editar(self):
        self.destroy()
        if self.on_editar:
            self.on_editar(self.nombre)


class DialogoExportarRespaldo(DialogoModalBase):
    """Modal para exportar y cifrar los secretos locales a un archivo .ksb."""

    def __init__(self, parent, service: SecretsService, on_completado=None):
        super().__init__(parent, "Exportar Respaldo Cifrado de Secretos", 500, 360)
        self.service = service
        self.backup_mgr = KeyringBackupService(service)
        self.on_completado = on_completado

        header = tk.Frame(self, bg=COLOR_NAVY, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_tit = tk.Label(
            header,
            text="⤓  Exportar Respaldo Cifrado (.ksb)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_NAVY,
            fg="#FFFFFF"
        )
        lbl_tit.pack(side="left", padx=16, pady=12)

        cuerpo = tk.Frame(self, bg=COLOR_CARD, padx=24, pady=16)
        cuerpo.pack(fill="both", expand=True)

        lbl_dest = tk.Label(cuerpo, text="Archivo de destino (.ksb):", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_dest.pack(anchor="w")

        f_dest = tk.Frame(cuerpo, bg=COLOR_CARD)
        f_dest.pack(fill="x", pady=(4, 12))

        self.txt_ruta = tk.Entry(f_dest, font=("Segoe UI", 9), bg="#F7FAFD", fg=COLOR_NAVY, relief="solid", bd=1)
        self.txt_ruta.pack(side="left", fill="x", expand=True, ipady=3)

        btn_explorar = tk.Button(
            f_dest, text="Explorar...", font=("Segoe UI", 9), bg=COLOR_BORDER, fg=COLOR_NAVY,
            relief="flat", cursor="hand2", command=self._elegir_destino
        )
        btn_explorar.pack(side="left", padx=(6, 0))

        lbl_pass1 = tk.Label(cuerpo, text="Nueva contraseña de cifrado (mínimo 8 caracteres):", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_pass1.pack(anchor="w")

        self.txt_pass1 = tk.Entry(cuerpo, font=("Consolas", 11), show="●", bg="#F7FAFD", fg=COLOR_NAVY, relief="solid", bd=1)
        self.txt_pass1.pack(fill="x", pady=(4, 8), ipady=3)

        lbl_pass2 = tk.Label(cuerpo, text="Confirmar contraseña:", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_pass2.pack(anchor="w")

        self.txt_pass2 = tk.Entry(cuerpo, font=("Consolas", 11), show="●", bg="#F7FAFD", fg=COLOR_NAVY, relief="solid", bd=1)
        self.txt_pass2.pack(fill="x", pady=(4, 10), ipady=3)

        lbl_nota = tk.Label(
            cuerpo,
            text="⚠️ Recuerda esta contraseña. No se almacena en ninguna parte.\nSe usa PBKDF2 (480.000 iteraciones) + AES-128 Fernet para máxima seguridad.",
            font=("Segoe UI", 8), bg=COLOR_CARD, fg=COLOR_MUTED, justify="left"
        )
        lbl_nota.pack(anchor="w", pady=(0, 14))

        footer = tk.Frame(cuerpo, bg=COLOR_CARD)
        footer.pack(fill="x", side="bottom")

        btn_cancelar = tk.Button(footer, text="Cancelar", font=("Segoe UI", 10), bg="#E2E8F0", fg=COLOR_NAVY, relief="flat", cursor="hand2", padx=14, pady=4, command=self.destroy)
        btn_cancelar.pack(side="right", padx=(8, 0))

        btn_exp = tk.Button(
            footer, text="Cifrar y Exportar", font=("Segoe UI", 10, "bold"), bg=COLOR_BLUE, fg="#FFFFFF",
            activebackground=COLOR_HOVER, activeforeground="#FFFFFF", relief="flat", cursor="hand2", padx=16, pady=4, command=self._exportar
        )
        btn_exp.pack(side="right")

    def _elegir_destino(self):
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar Respaldo Cifrado de Secretos",
            defaultextension=".ksb",
            filetypes=[("Respaldo Cifrado Keyring (*.ksb)", "*.ksb"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.txt_ruta.delete(0, "end")
            self.txt_ruta.insert(0, ruta)

    def _exportar(self):
        ruta = self.txt_ruta.get().strip()
        p1 = self.txt_pass1.get()
        p2 = self.txt_pass2.get()

        if not ruta:
            messagebox.showwarning("Falta destino", "Seleccione la ruta del archivo de destino.", parent=self)
            return
        if len(p1) < 8:
            messagebox.showwarning("Contraseña corta", "La contraseña debe tener al menos 8 caracteres.", parent=self)
            return
        if p1 != p2:
            messagebox.showerror("No coinciden", "Las contraseñas ingresadas no coinciden.", parent=self)
            return

        try:
            count, dest = self.backup_mgr.exportar_respaldo(Path(ruta), p1)
            messagebox.showinfo("Exportación Exitosa", f"Se exportaron y cifraron {count} secretos exitosamente en:\n{dest}", parent=self)
            if self.on_completado:
                self.on_completado()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc), parent=self)


class DialogoRestaurarInspeccionarRespaldo(DialogoModalBase):
    """Modal para descifrar, previsualizar o restaurar secretos desde un archivo .ksb."""

    def __init__(self, parent, service: SecretsService, on_restaurado=None):
        super().__init__(parent, "Restaurar / Ver Respaldo Cifrado (.ksb)", 580, 480)
        self.service = service
        self.backup_mgr = KeyringBackupService(service)
        self.on_restaurado = on_restaurado
        self.datos_descifrados = None

        header = tk.Frame(self, bg=COLOR_NAVY, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_tit = tk.Label(
            header,
            text="⤒  Restaurar / Inspeccionar Respaldo Cifrado",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_NAVY,
            fg="#FFFFFF"
        )
        lbl_tit.pack(side="left", padx=16, pady=12)

        cuerpo = tk.Frame(self, bg=COLOR_CARD, padx=20, pady=14)
        cuerpo.pack(fill="both", expand=True)

        # Selección de archivo y password
        f_top = tk.Frame(cuerpo, bg=COLOR_CARD)
        f_top.pack(fill="x", pady=(0, 10))

        lbl_arch = tk.Label(f_top, text="Archivo (.ksb):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_arch.grid(row=0, column=0, sticky="w", pady=2)

        self.txt_arch = tk.Entry(f_top, font=("Segoe UI", 9), bg="#F7FAFD", fg=COLOR_NAVY, relief="solid", bd=1, width=38)
        self.txt_arch.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=2)

        btn_expl = tk.Button(f_top, text="Explorar...", font=("Segoe UI", 8), bg=COLOR_BORDER, fg=COLOR_NAVY, relief="flat", cursor="hand2", command=self._elegir_archivo)
        btn_expl.grid(row=0, column=2, pady=2)

        lbl_pw = tk.Label(f_top, text="Contraseña:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_pw.grid(row=1, column=0, sticky="w", pady=4)

        self.txt_pw = tk.Entry(f_top, font=("Consolas", 10), show="●", bg="#F7FAFD", fg=COLOR_NAVY, relief="solid", bd=1)
        self.txt_pw.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=4)

        btn_des = tk.Button(
            f_top, text="🔓 Descifrar y Ver", font=("Segoe UI", 9, "bold"), bg=COLOR_BLUE, fg="#FFFFFF",
            activebackground=COLOR_HOVER, relief="flat", cursor="hand2", command=self._descifrar_y_mostrar
        )
        btn_des.grid(row=1, column=2, pady=4)

        f_top.columnconfigure(1, weight=1)

        # Previsualización
        lbl_prev = tk.Label(cuerpo, text="Secretos contenidos en el respaldo:", font=("Segoe UI", 10, "bold"), bg=COLOR_CARD, fg=COLOR_NAVY)
        lbl_prev.pack(anchor="w", pady=(6, 4))

        frame_tabla = tk.Frame(cuerpo, bg=COLOR_CARD, bd=1, relief="solid")
        frame_tabla.pack(fill="both", expand=True, pady=(0, 10))

        self.tabla_prev = ttk.Treeview(
            frame_tabla,
            columns=("nombre", "longitud", "valor"),
            show="headings",
            style="Secrets.Treeview",
            selectmode="extended"
        )
        self.tabla_prev.heading("nombre", text="NOMBRE")
        self.tabla_prev.heading("longitud", text="LONGITUD")
        self.tabla_prev.heading("valor", text="VALOR DESCIFRADO")

        self.tabla_prev.column("nombre", width=180, anchor="w")
        self.tabla_prev.column("longitud", width=80, anchor="center")
        self.tabla_prev.column("valor", width=240, anchor="w")

        sc = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla_prev.yview)
        self.tabla_prev.configure(yscrollcommand=sc.set)

        self.tabla_prev.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        # Botones inferiores
        footer = tk.Frame(cuerpo, bg=COLOR_CARD)
        footer.pack(fill="x", side="bottom")

        btn_cerrar = tk.Button(footer, text="Cerrar", font=("Segoe UI", 10), bg="#E2E8F0", fg=COLOR_NAVY, relief="flat", cursor="hand2", padx=14, pady=4, command=self.destroy)
        btn_cerrar.pack(side="right", padx=(8, 0))

        self.btn_restaurar = tk.Button(
            footer, text="📥 Inyectar al Keyring de este equipo", font=("Segoe UI", 10, "bold"), bg=COLOR_GREEN, fg="#FFFFFF",
            activebackground="#258656", relief="flat", cursor="hand2", padx=16, pady=4, state="disabled", command=self._restaurar_al_so
        )
        self.btn_restaurar.pack(side="right")

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar Respaldo Cifrado de Secretos",
            filetypes=[("Respaldo Cifrado Keyring (*.ksb)", "*.ksb"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.txt_arch.delete(0, "end")
            self.txt_arch.insert(0, ruta)

    def _descifrar_y_mostrar(self):
        ruta = self.txt_arch.get().strip()
        pw = self.txt_pw.get()

        if not ruta:
            messagebox.showwarning("Falta archivo", "Seleccione el archivo .ksb a descifrar.", parent=self)
            return
        if not pw:
            messagebox.showwarning("Falta contraseña", "Ingrese la contraseña de descifrado.", parent=self)
            return

        try:
            self.datos_descifrados = self.backup_mgr.inspeccionar_respaldo(Path(ruta), pw)
            secretos = self.datos_descifrados.get("secrets", {})

            self.tabla_prev.delete(*self.tabla_prev.get_children())
            for nom, val in secretos.items():
                self.tabla_prev.insert("", "end", iid=nom, values=(nom, f"{len(val)} chars", val))

            self.btn_restaurar.configure(state="normal")
            messagebox.showinfo("Respaldo Descifrado", f"Respaldo válido descifrado exitosamente.\nContiene {len(secretos)} secretos.", parent=self)
        except InvalidPasswordError:
            messagebox.showerror("Contraseña incorrecta", "La contraseña ingresada no es válida para descifrar este archivo.", parent=self)
        except Exception as exc:
            messagebox.showerror("Error al descifrar", str(exc), parent=self)

    def _restaurar_al_so(self):
        if not self.datos_descifrados:
            return

        ruta = self.txt_arch.get().strip()
        pw = self.txt_pw.get()

        # Si hay elementos seleccionados en la tabla, restaurar solo esos. De lo contrario, todos.
        seleccionados = list(self.tabla_prev.selection())
        nombres_a_restaurar = seleccionados if seleccionados else None

        cant_str = len(nombres_a_restaurar) if nombres_a_restaurar else len(self.datos_descifrados.get("secrets", {}))
        r = messagebox.askyesno(
            "Confirmar Restauración",
            f"¿Desea inyectar los {cant_str} secretos al almacén nativo del sistema operativo (Keyring) de este equipo?\n\nLos secretos existentes con el mismo nombre se actualizarán.",
            parent=self
        )
        if not r:
            return

        try:
            rest, om, errs = self.backup_mgr.restaurar_respaldo(
                Path(ruta), pw, sobrescribir=True, nombres_a_restaurar=nombres_a_restaurar
            )
            msg = f"Se inyectaron {rest} secretos al Keyring local exitosamente."
            if errs:
                msg += f"\n\nErrores encontrados ({len(errs)}):\n" + "\n".join(errs[:5])
            messagebox.showinfo("Restauración Completada", msg, parent=self)

            if self.on_restaurado:
                self.on_restaurado()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Error al restaurar", str(exc), parent=self)


class KeyringSecretsApp(tk.Tk):
    """Ventana Principal para la Gestión Integral de Secretos Keyring."""

    def __init__(self):
        super().__init__()
        self.title("Keyring Secrets Manager — EnvVar Manager Pro")
        self.geometry("860x580")
        self.minsize(740, 480)
        self.configure(bg=COLOR_BG)

        self.service = SecretsService()

        # Icono si existe en env_var_manager
        ruta_icono = DIRECTORIO_RAIZ / "src" / "gui" / "icon.ico"
        if ruta_icono.exists():
            try:
                self.iconbitmap(str(ruta_icono))
            except (tk.TclError, OSError) as exc:
                print(f"Advertencia: no se pudo cargar el icono de ventana: {exc}", file=sys.stderr)

        self._configurar_estilos_ttk()
        self._construir_ui()
        self._cargar_secretos()

    def _configurar_estilos_ttk(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Treeview estilo Corporate Light UI
        self.style.configure(
            "Secrets.Treeview",
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_CARD,
            borderwidth=1,
            rowheight=34,
            font=("Consolas", 11)
        )
        self.style.map(
            "Secrets.Treeview",
            background=[("selected", COLOR_BORDER)],
            foreground=[("selected", COLOR_NAVY)]
        )

        self.style.configure(
            "Secrets.Treeview.Heading",
            background=COLOR_CARD,
            foreground=COLOR_NAVY,
            borderwidth=1,
            relief="flat",
            font=("Segoe UI", 10, "bold")
        )
        self.style.map(
            "Secrets.Treeview.Heading",
            background=[("active", COLOR_BORDER)]
        )

    def _construir_ui(self):
        # 1. Header Principal
        header = tk.Frame(self, bg=COLOR_NAVY, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        frame_header_textos = tk.Frame(header, bg=COLOR_NAVY)
        frame_header_textos.pack(side="left", padx=20, pady=8)

        lbl_tit = tk.Label(
            frame_header_textos,
            text="🔐 Gestor de Secretos Keyring",
            font=("Segoe UI", 14, "bold"),
            bg=COLOR_NAVY,
            fg="#FFFFFF"
        )
        lbl_tit.pack(anchor="w")

        backend_desc = self.service.backend_activo()
        self.lbl_sub = tk.Label(
            frame_header_textos,
            text=f"Almacén activo: {backend_desc} · Cifrado nativo por SO",
            font=("Segoe UI", 9),
            bg=COLOR_NAVY,
            fg="#B9D5F5"
        )
        self.lbl_sub.pack(anchor="w")

        # Botones de Respaldo Cifrado en el Header
        frame_header_acciones = tk.Frame(header, bg=COLOR_NAVY)
        frame_header_acciones.pack(side="right", padx=20, pady=14)

        btn_exp_resp = tk.Button(
            frame_header_acciones,
            text="⤓  Exportar (.ksb)",
            font=("Segoe UI", 9, "bold"),
            bg="#1652A8",
            fg="#FFFFFF",
            activebackground="#2064C7",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=4,
            command=self._accion_exportar_respaldo
        )
        btn_exp_resp.pack(side="left", padx=(0, 8))

        btn_imp_resp = tk.Button(
            frame_header_acciones,
            text="⤒  Restaurar / Ver (.ksb)",
            font=("Segoe UI", 9, "bold"),
            bg="#243354",
            fg="#FFFFFF",
            activebackground="#33466E",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=4,
            command=self._accion_restaurar_respaldo
        )
        btn_imp_resp.pack(side="left")

        # 2. Barra de Herramientas y Búsqueda
        toolbar = tk.Frame(self, bg=COLOR_BG, padx=20, pady=12)
        toolbar.pack(fill="x")

        # Búsqueda
        lbl_buscar = tk.Label(toolbar, text="🔍 Buscar:", font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_NAVY)
        lbl_buscar.pack(side="left", padx=(0, 6))

        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", lambda *_: self._filtrar_secretos())

        self.txt_buscar = tk.Entry(
            toolbar,
            textvariable=self.var_busqueda,
            font=("Segoe UI", 10),
            bg=COLOR_CARD,
            fg=COLOR_NAVY,
            relief="solid",
            bd=1,
            width=28
        )
        self.txt_buscar.pack(side="left", ipady=3)

        # Botones de Acción (Derecha)
        btn_eliminar = tk.Button(
            toolbar,
            text="🗑️  Eliminar",
            font=("Segoe UI", 10),
            bg=COLOR_CARD,
            fg=COLOR_RED,
            activebackground="#FDE8E8",
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=12,
            pady=3,
            command=self._accion_eliminar
        )
        btn_eliminar.pack(side="right", padx=(6, 0))

        btn_editar = tk.Button(
            toolbar,
            text="✏️  Editar",
            font=("Segoe UI", 10),
            bg=COLOR_CARD,
            fg=COLOR_NAVY,
            activebackground=COLOR_LIGHT_HOVER,
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=12,
            pady=3,
            command=self._accion_editar
        )
        btn_editar.pack(side="right", padx=(6, 0))

        btn_ver = tk.Button(
            toolbar,
            text="👁️  Ver / Copiar",
            font=("Segoe UI", 10),
            bg=COLOR_CARD,
            fg=COLOR_NAVY,
            activebackground=COLOR_LIGHT_HOVER,
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=12,
            pady=3,
            command=self._accion_ver
        )
        btn_ver.pack(side="right", padx=(6, 0))

        btn_nuevo = tk.Button(
            toolbar,
            text="➕  Nuevo Secreto",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_BLUE,
            fg="#FFFFFF",
            activebackground=COLOR_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=4,
            command=self._accion_nuevo
        )
        btn_nuevo.pack(side="right", padx=(6, 0))

        # 3. Contenedor de la Tabla Principal
        frame_tabla = tk.Frame(self, bg=COLOR_BG)
        frame_tabla.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        card_tabla = tk.Frame(frame_tabla, bg=COLOR_CARD, bd=1, relief="solid")
        card_tabla.pack(fill="both", expand=True)

        columnas = ("nombre", "estado", "longitud")
        self.tabla = ttk.Treeview(
            card_tabla,
            columns=columnas,
            show="headings",
            style="Secrets.Treeview",
            selectmode="browse"
        )
        self.tabla.heading("nombre", text="NOMBRE DEL SECRETO")
        self.tabla.heading("estado", text="ESTADO EN KEYRING")
        self.tabla.heading("longitud", text="CARACTERES")

        self.tabla.column("nombre", width=380, anchor="w")
        self.tabla.column("estado", width=220, anchor="w")
        self.tabla.column("longitud", width=120, anchor="center")

        scroll_y = ttk.Scrollbar(card_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll_y.set)

        self.tabla.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        # Eventos tabla
        self.tabla.bind("<Double-1>", lambda _: self._accion_ver())

        # Menú contextual
        self.menu_ctx = tk.Menu(self, tearoff=0, bg=COLOR_CARD, fg=COLOR_NAVY, activebackground=COLOR_BORDER, font=("Segoe UI", 10))
        self.menu_ctx.add_command(label="👁️  Ver / Copiar valor", command=self._accion_ver)
        self.menu_ctx.add_command(label="✏️  Editar valor", command=self._accion_editar)
        self.menu_ctx.add_separator()
        self.menu_ctx.add_command(label="🗑️  Eliminar secreto", command=self._accion_eliminar)

        def _abrir_menu_ctx(event):
            item = self.tabla.identify_row(event.y)
            if item:
                self.tabla.selection_set(item)
                self.menu_ctx.tk_popup(event.x_root, event.y_root)

        self.tabla.bind("<Button-3>", _abrir_menu_ctx)

        # 4. Barra de Estado Inferior
        statusbar = tk.Frame(self, bg=COLOR_CARD, height=32, bd=1, relief="solid")
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)

        self.lbl_status = tk.Label(
            statusbar,
            text="Listo",
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_MUTED
        )
        self.lbl_status.pack(side="left", padx=16, pady=6)

        btn_refrescar = tk.Button(
            statusbar,
            text="🔄  Recargar",
            font=("Segoe UI", 8),
            bg=COLOR_CARD,
            fg=COLOR_BLUE,
            relief="flat",
            cursor="hand2",
            command=self._cargar_secretos
        )
        btn_refrescar.pack(side="right", padx=16, pady=4)

    def _cargar_secretos(self):
        self.secretos_cache = []
        nombres = self.service.listar_nombres()
        for nom in nombres:
            val = self.service.obtener(nom)
            presente = val is not None
            longitud = len(val) if val is not None else 0
            self.secretos_cache.append({
                "nombre": nom,
                "estado": "● Protegido en SO" if presente else "⚠️ No encontrado",
                "longitud": f"{longitud} chars" if presente else "—"
            })
        self._filtrar_secretos()

    def _filtrar_secretos(self):
        self.tabla.delete(*self.tabla.get_children())
        filtro = self.var_busqueda.get().strip().lower()

        count = 0
        for item in self.secretos_cache:
            if filtro and filtro not in item["nombre"].lower():
                continue
            self.tabla.insert(
                "",
                "end",
                iid=item["nombre"],
                values=(item["nombre"], item["estado"], item["longitud"])
            )
            count += 1

        total = len(self.secretos_cache)
        if filtro:
            self.lbl_status.configure(text=f"Mostrando {count} de {total} secretos (Filtro: '{filtro}')")
        else:
            self.lbl_status.configure(text=f"Total de secretos registrados: {total}")

    def _item_seleccionado(self) -> Optional[str]:
        sel = self.tabla.selection()
        return sel[0] if sel else None

    def _accion_nuevo(self):
        DialogoNuevoEditarSecreto(self, self.service, es_edicion=False, on_guardado=lambda _: self._cargar_secretos())

    def _accion_ver(self):
        nom = self._item_seleccionado()
        if not nom:
            messagebox.showinfo("Selección requerida", "Por favor seleccione un secreto de la lista.", parent=self)
            return
        DialogoVerSecreto(self, self.service, nom, on_editar=lambda n: self._abrir_edicion_directa(n))

    def _abrir_edicion_directa(self, nom: str):
        DialogoNuevoEditarSecreto(self, self.service, nombre_inicial=nom, es_edicion=True, on_guardado=lambda _: self._cargar_secretos())

    def _accion_editar(self):
        nom = self._item_seleccionado()
        if not nom:
            messagebox.showinfo("Selección requerida", "Por favor seleccione un secreto para editar.", parent=self)
            return
        self._abrir_edicion_directa(nom)

    def _accion_eliminar(self):
        nom = self._item_seleccionado()
        if not nom:
            messagebox.showinfo("Selección requerida", "Por favor seleccione un secreto para eliminar.", parent=self)
            return

        r = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Está seguro de eliminar el secreto '{nom}' del almacén nativo del sistema operativo?\n\nEsta operación no se puede deshacer.",
            icon="warning",
            parent=self
        )
        if r:
            try:
                self.service.eliminar(nom)
                self._cargar_secretos()
                messagebox.showinfo("Eliminado", f"El secreto '{nom}' ha sido eliminado exitosamente.", parent=self)
            except Exception as exc:
                messagebox.showerror("Error al eliminar", str(exc), parent=self)

    def _accion_exportar_respaldo(self):
        DialogoExportarRespaldo(self, self.service)

    def _accion_restaurar_respaldo(self):
        DialogoRestaurarInspeccionarRespaldo(self, self.service, on_restaurado=lambda: self._cargar_secretos())


def main():
    if not KEYRING_DISPONIBLE:
        print("Error: la librería 'keyring' no está instalada.", file=sys.stderr)
        sys.exit(1)
    app = KeyringSecretsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
