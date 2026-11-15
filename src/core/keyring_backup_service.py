"""
Servicio de respaldo y restauración cifrado para secretos Keyring (.ksb = Keyring Secrets Backup).

Diseño del contenedor:
- Encabezado binario:
  MAGIC: b"KSMB" (Keyring Secrets Manager Backup)
  VERSION: b"\x01"
  SALT: 16 bytes aleatorios
  TOKEN Fernet (AES-128-CBC + HMAC-SHA256 con derivación PBKDF2-HMAC-SHA256 de 480.000 iteraciones)
- Payload interno en JSON con metadatos:
  {
    "type": "keyring_secrets_backup",
    "version": "1.0",
    "created_at": "ISO-8601",
    "hostname": "NOMBRE_EQUIPO",
    "service": "EnvVarManagerPro",
    "count": 5,
    "secrets": {
      "NOMBRE_SECRETO_1": "VALOR_DESCIFRADO_1",
      ...
    }
  }
"""

from __future__ import annotations

import base64
import json
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import CorruptedBackupError, EnvManagerError, InvalidPasswordError
from .secrets_service import SecretsService

MAGIC_SECRETS = b"KSMB"  # Keyring Secrets Manager Backup
FORMAT_VERSION_SECRETS = b"\x01"
SALT_SIZE = 16
PBKDF2_ITERATIONS = 480_000


def _derivar_clave_secrets(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


class KeyringBackupService:
    """Cifra, descifra, exporta e importa secretos locales respaldados por Keyring."""

    def __init__(self, secrets_service: Optional[SecretsService] = None):
        self.service = secrets_service or SecretsService()

    def exportar_respaldo(
        self,
        filepath: Path,
        password: str,
        nombres_seleccionados: Optional[List[str]] = None
    ) -> Tuple[int, Path]:
        """
        Extrae los secretos del almacén nativo del SO, cifra el paquete con PBKDF2+Fernet
        y lo guarda en un archivo binario `.ksb`.
        """
        if not password or len(password) < 8:
            raise EnvManagerError("La contraseña de respaldo debe tener al menos 8 caracteres.")

        todos = self.service.listar_nombres()
        if nombres_seleccionados is not None:
            objetivo = [n for n in todos if n in nombres_seleccionados]
        else:
            objetivo = todos

        if not objetivo:
            raise EnvManagerError("No hay secretos disponibles para exportar.")

        secretos_dict: Dict[str, str] = {}
        for nombre in objetivo:
            val = self.service.obtener(nombre)
            if val is not None:
                secretos_dict[nombre] = val

        payload = {
            "type": "keyring_secrets_backup",
            "version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "hostname": socket.gethostname(),
            "service": self.service.SERVICIO,
            "count": len(secretos_dict),
            "secrets": secretos_dict
        }

        salt = os.urandom(SALT_SIZE)
        key = _derivar_clave_secrets(password, salt)
        fernet = Fernet(key)
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        token = fernet.encrypt(raw_bytes)

        blob = MAGIC_SECRETS + FORMAT_VERSION_SECRETS + salt + token
        destino = Path(filepath)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(blob)

        return len(secretos_dict), destino

    def inspeccionar_respaldo(self, filepath: Path, password: str) -> dict:
        """
        Descifra e inspecciona el archivo de respaldo sin aplicar cambios al SO.
        Retorna el diccionario con la estructura y los secretos.
        """
        archivo = Path(filepath)
        if not archivo.exists():
            raise EnvManagerError(f"El archivo '{archivo}' no existe.")

        blob = archivo.read_bytes()
        min_size = len(MAGIC_SECRETS) + len(FORMAT_VERSION_SECRETS) + SALT_SIZE
        if len(blob) < min_size:
            raise CorruptedBackupError("El archivo es demasiado pequeño o está corrupto.")

        magic = blob[: len(MAGIC_SECRETS)]
        version = blob[len(MAGIC_SECRETS) : len(MAGIC_SECRETS) + 1]

        if magic != MAGIC_SECRETS:
            raise CorruptedBackupError("El archivo no corresponde a un respaldo válido de secretos (.ksb).")
        if version != FORMAT_VERSION_SECRETS:
            raise CorruptedBackupError(f"Versión de formato no soportada: {version!r}")

        offset = len(MAGIC_SECRETS) + len(FORMAT_VERSION_SECRETS)
        salt = blob[offset : offset + SALT_SIZE]
        token = blob[offset + SALT_SIZE :]

        key = _derivar_clave_secrets(password, salt)
        fernet = Fernet(key)

        try:
            raw_bytes = fernet.decrypt(token)
        except InvalidToken as exc:
            raise InvalidPasswordError("Contraseña incorrecta o archivo de respaldo dañado.") from exc

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(data, dict) or "secrets" not in data:
                raise CorruptedBackupError("Estructura de respaldo inválida.")
            return data
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CorruptedBackupError("No se pudo interpretar el contenido descifrado.") from exc

    def restaurar_respaldo(
        self,
        filepath: Path,
        password: str,
        sobrescribir: bool = True,
        nombres_a_restaurar: Optional[List[str]] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Descifra el archivo e inyecta los secretos en el Keyring de la máquina actual.
        Retorna (restaurados, omitidos, errores).
        """
        data = self.inspeccionar_respaldo(filepath, password)
        secretos = data.get("secrets", {})

        restaurados = 0
        omitidos = 0
        errores: List[str] = []

        for nombre, valor in secretos.items():
            if nombres_a_restaurar is not None and nombre not in nombres_a_restaurar:
                continue

            try:
                ya_existe = self.service.existe(nombre)
                if ya_existe and not sobrescribir:
                    omitidos += 1
                    continue

                if ya_existe:
                    self.service.actualizar(nombre, valor)
                else:
                    self.service.guardar(nombre, valor)

                restaurados += 1
            except Exception as exc:
                errores.append(f"{nombre}: {exc}")

        return restaurados, omitidos, errores
