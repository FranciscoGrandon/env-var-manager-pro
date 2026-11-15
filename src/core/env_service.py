"""
Servicio de gestión de variables de entorno.

Abstrae las diferencias entre sistemas operativos:

- Windows: variables USER y SYSTEM se leen/escriben en el Registro
  (HKCU\\Environment y HKLM\\...\\Environment respectivamente) usando `winreg`,
  y se notifica el cambio a las ventanas abiertas vía WM_SETTINGCHANGE.
  SYSTEM requiere privilegios de administrador.
- Linux/macOS: no existe un "registro" central. USER se persiste agregando
  líneas `export NAME="VALUE"` (delimitadas por marcadores propios) al perfil
  de shell del usuario (~/.profile). SYSTEM requiere editar /etc/environment
  y por seguridad se deja como operación explícita que requiere sudo externo.
- SESSION (todas las plataformas): solo afecta os.environ del proceso actual
  de la aplicación; útil para pruebas rápidas, no persiste.

Todas las operaciones quedan registradas mediante el logger de la aplicación.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path
from typing import Dict, List

from .exceptions import PermissionDeniedError, UnsupportedPlatformError, ValidationError
from .models import EnvScope
from ..utils.logger_config import get_logger

logger = get_logger(__name__)

MARKER_INICIO = "# >>> EnvVar Manager Pro >>>"
MARKER_FIN = "# <<< EnvVar Manager Pro <<<"

_ES_WINDOWS = platform.system() == "Windows"

if _ES_WINDOWS:
    import winreg  # type: ignore
    import ctypes


def validar_nombre_variable(name: str) -> None:
    if not name or not name.strip():
        raise ValidationError("El nombre de la variable no puede estar vacío.")
    if "=" in name:
        raise ValidationError("El nombre de la variable no puede contener '='.")
    if any(c.isspace() for c in name):
        raise ValidationError("El nombre de la variable no puede contener espacios.")


_RE_NOMBRE_UNIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _escapar_valor_shell(value: str) -> str:
    """Escapa un valor para uso seguro dentro de comillas dobles en sh/bash."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )


def _desescapar_valor_shell(value: str) -> str:
    """Inverso exacto de `_escapar_valor_shell`."""
    return re.sub(r'\\([\\"$`])', r"\1", value)


def _validar_para_unix(name: str, value: str) -> None:
    """Validaciones adicionales para persistir en el perfil de shell (previene inyección)."""
    if not _RE_NOMBRE_UNIX.match(name):
        raise ValidationError(
            "En Linux/macOS el nombre debe cumplir [A-Za-z_][A-Za-z0-9_]*."
        )
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValidationError(
            "El valor no puede contener saltos de línea ni caracteres nulos en Linux/macOS."
        )


class EnvironmentVariableService:
    """API unificada para leer, crear, modificar y eliminar variables de entorno."""

    # ---------------------------------------------------------------- utilidades

    @staticmethod
    def es_admin() -> bool:
        try:
            if _ES_WINDOWS:
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            return os.geteuid() == 0  # type: ignore[attr-defined]
        except Exception:
            return False

    @staticmethod
    def plataforma() -> str:
        return platform.system()

    # ---------------------------------------------------------------- lectura

    def listar(self, scope: EnvScope) -> Dict[str, str]:
        if scope is EnvScope.SESSION:
            return dict(os.environ)

        if _ES_WINDOWS:
            return self._listar_windows(scope)

        return self._listar_unix(scope)

    def _listar_windows(self, scope: EnvScope) -> Dict[str, str]:
        hive, subkey = self._clave_windows(scope)
        resultado: Dict[str, str] = {}
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    resultado[name] = value
                    i += 1
                except OSError:
                    break
        return resultado

    def _listar_unix(self, scope: EnvScope) -> Dict[str, str]:
        if scope is EnvScope.SYSTEM:
            return self._parsear_bloque(Path("/etc/environment"))
        return self._parsear_bloque(self._perfil_shell())

    # ---------------------------------------------------------------- escritura

    def establecer(self, name: str, value: str, scope: EnvScope) -> None:
        validar_nombre_variable(name)
        logger.info("Estableciendo variable '%s' en alcance %s", name, scope.value)

        if scope is EnvScope.SESSION:
            os.environ[name] = value
            return

        if scope is EnvScope.SYSTEM and not self.es_admin():
            raise PermissionDeniedError(
                "Se requieren privilegios de administrador para modificar variables de SISTEMA."
            )

        if _ES_WINDOWS:
            self._establecer_windows(name, value, scope)
        else:
            self._establecer_unix(name, value, scope)

        # Reflejar también en el proceso actual para feedback inmediato en la GUI
        os.environ[name] = value

    def eliminar(self, name: str, scope: EnvScope) -> None:
        logger.info("Eliminando variable '%s' del alcance %s", name, scope.value)

        if scope is EnvScope.SESSION:
            os.environ.pop(name, None)
            return

        if scope is EnvScope.SYSTEM and not self.es_admin():
            raise PermissionDeniedError(
                "Se requieren privilegios de administrador para eliminar variables de SISTEMA."
            )

        if _ES_WINDOWS:
            self._eliminar_windows(name, scope)
        else:
            self._eliminar_unix(name, scope)

        os.environ.pop(name, None)

    # ---------------------------------------------------------------- Windows

    @staticmethod
    def _clave_windows(scope: EnvScope):
        if scope is EnvScope.USER:
            return winreg.HKEY_CURRENT_USER, "Environment"
        return (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )

    def _establecer_windows(self, name: str, value: str, scope: EnvScope) -> None:
        hive, subkey = self._clave_windows(scope)
        tipo = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, tipo, value)
        self._notificar_cambio_windows()

    def _eliminar_windows(self, name: str, scope: EnvScope) -> None:
        hive, subkey = self._clave_windows(scope)
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        self._notificar_cambio_windows()

    @staticmethod
    def _notificar_cambio_windows() -> None:
        """Notifica a las ventanas del sistema que el entorno cambió (WM_SETTINGCHANGE)."""
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x1A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )

    # ---------------------------------------------------------------- Unix

    @staticmethod
    def _perfil_shell() -> Path:
        return Path.home() / ".profile"

    def _parsear_bloque(self, archivo: Path) -> Dict[str, str]:
        """Extrae variables desde export NAME="VALUE" dentro del bloque marcado, y del entorno vivo."""
        resultado: Dict[str, str] = {}
        if archivo.exists():
            dentro_bloque = archivo == self._perfil_shell()
            en_bloque = not dentro_bloque  # /etc/environment no usa marcadores
            for linea in archivo.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = linea.strip()
                if stripped == MARKER_INICIO:
                    en_bloque = True
                    continue
                if stripped == MARKER_FIN:
                    en_bloque = False
                    continue
                if not en_bloque or not stripped or stripped.startswith("#"):
                    continue
                contenido = stripped[len("export ") :] if stripped.startswith("export ") else stripped
                if "=" in contenido:
                    name, _, value = contenido.partition("=")
                    valor = value.strip()
                    if len(valor) >= 2 and valor.startswith('"') and valor.endswith('"'):
                        valor = _desescapar_valor_shell(valor[1:-1])
                    else:
                        valor = valor.strip('"').strip("'")
                    resultado[name.strip()] = valor
        return resultado

    def _establecer_unix(self, name: str, value: str, scope: EnvScope) -> None:
        if scope is EnvScope.SYSTEM:
            raise UnsupportedPlatformError(
                "La edición de variables de SISTEMA en Linux/macOS debe hacerse manualmente "
                "en /etc/environment con permisos de administrador, por seguridad."
            )
        _validar_para_unix(name, value)
        self._actualizar_bloque_shell({name: value}, eliminar=[])

    def _eliminar_unix(self, name: str, scope: EnvScope) -> None:
        if scope is EnvScope.SYSTEM:
            raise UnsupportedPlatformError(
                "La edición de variables de SISTEMA en Linux/macOS debe hacerse manualmente "
                "en /etc/environment con permisos de administrador, por seguridad."
            )
        self._actualizar_bloque_shell({}, eliminar=[name])

    def _actualizar_bloque_shell(self, establecer: Dict[str, str], eliminar: List[str]) -> None:
        archivo = self._perfil_shell()
        actuales = self._parsear_bloque(archivo)
        actuales.update(establecer)
        for name in eliminar:
            actuales.pop(name, None)

        lineas_previas = []
        if archivo.exists():
            contenido = archivo.read_text(encoding="utf-8", errors="ignore").splitlines()
            en_bloque = False
            for linea in contenido:
                if linea.strip() == MARKER_INICIO:
                    en_bloque = True
                    continue
                if linea.strip() == MARKER_FIN:
                    en_bloque = False
                    continue
                if not en_bloque:
                    lineas_previas.append(linea)

        bloque_nuevo = [MARKER_INICIO]
        for name, value in actuales.items():
            bloque_nuevo.append(f'export {name}="{_escapar_valor_shell(value)}"')
        bloque_nuevo.append(MARKER_FIN)

        archivo.write_text("\n".join(lineas_previas + bloque_nuevo) + "\n", encoding="utf-8")
        logger.info("Perfil de shell actualizado en %s", archivo)
