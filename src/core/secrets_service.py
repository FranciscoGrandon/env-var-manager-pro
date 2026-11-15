"""
Servicio de secretos (tokens, API keys, credenciales) respaldado por el
almacén nativo del sistema operativo a través de la librería `keyring`:

- Windows -> Windows Credential Locker (Administrador de credenciales)
- macOS   -> Keychain
- Linux   -> Secret Service (GNOME Keyring / KWallet vía D-Bus)

A diferencia de las variables de entorno o del respaldo `.evb`, aquí el
cifrado en reposo y el control de acceso los gestiona el propio sistema
operativo, ligado a la cuenta del usuario que inició sesión. La aplicación
nunca ve ni almacena una clave maestra: solo pide al SO "guarda esto" o
"dame el valor de esto".

`keyring` no expone una forma nativa de listar todos los nombres guardados
para un backend arbitrario, así que mantenemos un índice local (SOLO con
los NOMBRES, nunca los valores) en un archivo JSON de configuración, para
poder mostrar la lista en la interfaz.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

try:
    import keyring
    from keyring.errors import KeyringError, NoKeyringError

    KEYRING_DISPONIBLE = True
except ImportError:  # keyring no instalado
    KEYRING_DISPONIBLE = False

    class KeyringError(Exception):
        pass

    class NoKeyringError(KeyringError):
        pass

from .exceptions import EnvManagerError
from ..utils.logger_config import get_logger

logger = get_logger(__name__)

SERVICIO = "EnvVarManagerPro"


class SecretBackendNoDisponibleError(EnvManagerError):
    """No hay un backend de almacén de credenciales disponible en este sistema."""


class SecretsService:
    """CRUD de secretos individuales respaldado por el keyring del sistema operativo."""

    SERVICIO: str = SERVICIO

    def __init__(self, ruta_indice: Optional[Path] = None):
        from ..utils.logger_config import _directorio_datos  # reutiliza la misma carpeta de datos

        self._ruta_indice = ruta_indice or (_directorio_datos() / "secrets_index.json")
        if not self._ruta_indice.exists():
            self._ruta_indice.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------ índice de nombres

    def _leer_indice(self) -> List[str]:
        try:
            return json.loads(self._ruta_indice.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _escribir_indice(self, nombres: List[str]) -> None:
        self._ruta_indice.write_text(
            json.dumps(sorted(set(nombres)), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def listar_nombres(self) -> List[str]:
        return sorted(self._leer_indice())

    def existe(self, nombre: str) -> bool:
        """Verifica si el secreto se encuentra registrado en el índice local."""
        if not nombre or not nombre.strip():
            return False
        return nombre.strip() in self._leer_indice()

    # ------------------------------------------------------------ operaciones

    def _verificar_backend(self) -> None:
        if not KEYRING_DISPONIBLE:
            raise SecretBackendNoDisponibleError(
                "La librería 'keyring' no está instalada. Ejecuta: pip install keyring"
            )

    def guardar(self, nombre: str, valor: str) -> None:
        self._verificar_backend()
        if not nombre or not nombre.strip():
            raise EnvManagerError("El nombre del secreto no puede estar vacío.")
        nombre_limpio = nombre.strip()
        try:
            keyring.set_password(self.SERVICIO, nombre_limpio, valor)
        except NoKeyringError as exc:
            raise SecretBackendNoDisponibleError(
                "No se encontró un almacén de credenciales del sistema operativo "
                "(Credential Manager / Keychain / Secret Service). En Linux headless, "
                "instala 'gnome-keyring' o 'kwallet' y asegúrate de tener una sesión de escritorio activa."
            ) from exc
        except KeyringError as exc:
            raise EnvManagerError(f"No se pudo guardar el secreto: {exc}") from exc

        nombres = self._leer_indice()
        if nombre_limpio not in nombres:
            nombres.append(nombre_limpio)
            self._escribir_indice(nombres)
        logger.info("Secreto '%s' guardado en el almacén del sistema operativo", nombre_limpio)

    def actualizar(self, nombre: str, nuevo_valor: str) -> None:
        """Actualiza el valor de un secreto existente en el almacén seguro."""
        self._verificar_backend()
        if not nombre or not nombre.strip():
            raise EnvManagerError("El nombre del secreto no puede estar vacío.")
        nombre_limpio = nombre.strip()
        if not self.existe(nombre_limpio):
            raise EnvManagerError(f"El secreto '{nombre_limpio}' no existe en el almacén.")

        try:
            keyring.set_password(self.SERVICIO, nombre_limpio, nuevo_valor)
        except NoKeyringError as exc:
            raise SecretBackendNoDisponibleError(
                "No se encontró un almacén de credenciales del sistema operativo "
                "(Credential Manager / Keychain / Secret Service). En Linux headless, "
                "instala 'gnome-keyring' o 'kwallet' y asegúrate de tener una sesión de escritorio activa."
            ) from exc
        except KeyringError as exc:
            raise EnvManagerError(f"No se pudo actualizar el secreto: {exc}") from exc

        logger.info("Secreto '%s' actualizado en el almacén del sistema operativo", nombre_limpio)

    def obtener(self, nombre: str) -> Optional[str]:
        self._verificar_backend()
        nombre_limpio = nombre.strip() if nombre else ""
        try:
            return keyring.get_password(self.SERVICIO, nombre_limpio)
        except KeyringError as exc:
            raise EnvManagerError(f"No se pudo leer el secreto: {exc}") from exc

    def eliminar(self, nombre: str) -> None:
        self._verificar_backend()
        nombre_limpio = nombre.strip() if nombre else ""
        try:
            keyring.delete_password(self.SERVICIO, nombre_limpio)
        except KeyringError:
            pass  # ya no existía en el backend; igual limpiamos el índice
        nombres = self._leer_indice()
        if nombre_limpio in nombres:
            nombres.remove(nombre_limpio)
            self._escribir_indice(nombres)
        logger.info("Secreto '%s' eliminado del almacén del sistema operativo", nombre_limpio)

    def backend_activo(self) -> str:
        if not KEYRING_DISPONIBLE:
            return "no disponible (falta instalar 'keyring')"
        try:
            return str(keyring.get_keyring())
        except Exception:
            return "desconocido"

