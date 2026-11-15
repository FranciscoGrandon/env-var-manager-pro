"""
Servicio criptográfico responsable de cifrar y descifrar los respaldos.

Diseño del archivo de respaldo (.evb  =  Environment Variable Backup):

    +----------------+----------------+------------------+---------------------+
    | MAGIC (4 bytes)| VERSION (1 b)  | SALT (16 bytes)  | Fernet token (resto)|
    +----------------+----------------+------------------+---------------------+

- MAGIC identifica el tipo de archivo y permite detectar archivos corruptos
  o de otro origen antes de intentar descifrar.
- SALT es aleatorio por respaldo y se usa para derivar la clave con PBKDF2.
- El token de Fernet ya incluye IV, HMAC y timestamp, garantizando
  confidencialidad e integridad del contenido (AES-128-CBC + HMAC-SHA256).

La clave jamás se almacena: se deriva en memoria a partir de la contraseña
que el usuario debe recordar, tal como pidió el requerimiento.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import CorruptedBackupError, InvalidPasswordError

MAGIC = b"EVMB"          # EnvVar Manager Backup
FORMAT_VERSION = b"\x01"
SALT_SIZE = 16
PBKDF2_ITERATIONS = 480_000  # Recomendación OWASP 2023+ para PBKDF2-HMAC-SHA256


@dataclass(frozen=True)
class PasswordStrength:
    score: int          # 0 (muy débil) a 4 (muy fuerte)
    label: str
    suggestions: list


def evaluar_fortaleza(password: str) -> PasswordStrength:
    """Heurística simple y transparente de fortaleza de contraseña (sin dependencias externas)."""
    sugerencias = []
    score = 0

    if len(password) >= 12:
        score += 1
    else:
        sugerencias.append("Usa al menos 12 caracteres")

    if any(c.islower() for c in password) and any(c.isupper() for c in password):
        score += 1
    else:
        sugerencias.append("Combina mayúsculas y minúsculas")

    if any(c.isdigit() for c in password):
        score += 1
    else:
        sugerencias.append("Incluye al menos un número")

    if any(not c.isalnum() for c in password):
        score += 1
    else:
        sugerencias.append("Incluye algún símbolo (!@#$...)")

    etiquetas = ["Muy débil", "Débil", "Aceptable", "Fuerte", "Muy fuerte"]
    return PasswordStrength(score=score, label=etiquetas[score], suggestions=sugerencias)


def _derivar_clave(password: str, salt: bytes) -> bytes:
    """Deriva una clave Fernet (32 bytes url-safe base64) a partir de la contraseña y el salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


class CryptoService:
    """Cifra y descifra diccionarios (payloads JSON-serializables) para los respaldos."""

    def encrypt_payload(self, data: dict, password: str) -> bytes:
        salt = os.urandom(SALT_SIZE)
        key = _derivar_clave(password, salt)
        fernet = Fernet(key)
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        token = fernet.encrypt(raw)
        return MAGIC + FORMAT_VERSION + salt + token

    def decrypt_payload(self, blob: bytes, password: str) -> dict:
        if len(blob) < len(MAGIC) + len(FORMAT_VERSION) + SALT_SIZE:
            raise CorruptedBackupError("El archivo es demasiado pequeño para ser un respaldo válido.")

        magic = blob[: len(MAGIC)]
        version = blob[len(MAGIC) : len(MAGIC) + 1]
        if magic != MAGIC:
            raise CorruptedBackupError(
                "El archivo no corresponde a un respaldo de EnvVar Manager Pro."
            )
        if version != FORMAT_VERSION:
            raise CorruptedBackupError(f"Versión de formato no soportada: {version!r}")

        offset = len(MAGIC) + len(FORMAT_VERSION)
        salt = blob[offset : offset + SALT_SIZE]
        token = blob[offset + SALT_SIZE :]

        key = _derivar_clave(password, salt)
        fernet = Fernet(key)
        try:
            raw = fernet.decrypt(token)
        except InvalidToken as exc:
            raise InvalidPasswordError(
                "Clave incorrecta o archivo de respaldo corrupto."
            ) from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CorruptedBackupError("El contenido descifrado no es JSON válido.") from exc
