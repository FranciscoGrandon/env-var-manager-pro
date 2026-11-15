"""
Cliente Python para acceder a secretos guardados en EnvVar Manager Pro.

Uso en tus aplicaciones:

    from envvar_manager_client import get_secret, get_secret_safe
    
    # Opción 1: fallar si el secreto no existe
    github_token = get_secret("GITHUB_TOKEN")
    
    # Opción 2: retornar un valor por defecto
    api_key = get_secret_safe("OPENAI_API_KEY", default="")
    
    # Opción 3: encadenamiento — keyring primero, luego variables de entorno
    token = get_secret_safe("API_TOKEN") or os.getenv("API_TOKEN")

Requisito: `pip install keyring`
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_DISPONIBLE = True
except ImportError:
    KEYRING_DISPONIBLE = False


class SecretoNoEncontradoError(Exception):
    """Se lanza cuando el secreto no existe en el keyring."""

    pass


class KeyringNoDisponibleError(Exception):
    """Se lanza cuando keyring no está instalado o no hay backend disponible."""

    pass


def get_secret(nombre: str, fallback_env: bool = False) -> str:
    """
    Obtiene un secreto guardado en EnvVar Manager Pro.

    Args:
        nombre: Nombre del secreto (ej. "GITHUB_TOKEN")
        fallback_env: Si True, intenta os.getenv(nombre) si no encuentra en keyring

    Returns:
        El valor del secreto

    Raises:
        SecretoNoEncontradoError: Si el secreto no existe
        KeyringNoDisponibleError: Si keyring no está disponible
    """
    if not KEYRING_DISPONIBLE:
        raise KeyringNoDisponibleError(
            "La librería 'keyring' no está instalada. Ejecuta: pip install keyring"
        )

    try:
        valor = keyring.get_password("EnvVarManagerPro", nombre)
    except KeyringError as exc:
        raise KeyringNoDisponibleError(
            f"No se pudo acceder al almacén de credenciales del SO: {exc}"
        ) from exc

    if valor is not None:
        return valor

    # Fallback a variable de entorno si se especifica
    if fallback_env:
        valor = os.getenv(nombre)
        if valor is not None:
            return valor

    raise SecretoNoEncontradoError(
        f"Secreto '{nombre}' no encontrado en EnvVar Manager Pro. "
        "Abre la app → pestaña 'Secretos' → 'Nuevo secreto' para agregarlo."
    )


def get_secret_safe(
    nombre: str, default: Optional[str] = None, fallback_env: bool = True
) -> Optional[str]:
    """
    Obtiene un secreto de forma segura (nunca falla).

    Args:
        nombre: Nombre del secreto
        default: Valor por defecto si no se encuentra
        fallback_env: Si True, intenta os.getenv(nombre) antes de retornar default

    Returns:
        El valor del secreto, el fallback de env, o default
    """
    if not KEYRING_DISPONIBLE:
        if fallback_env:
            return os.getenv(nombre, default)
        return default

    try:
        valor = keyring.get_password("EnvVarManagerPro", nombre)
        if valor is not None:
            return valor
    except KeyringError:
        pass

    # Fallback a variable de entorno
    if fallback_env:
        return os.getenv(nombre, default)

    return default


def listar_secretos() -> list[str]:
    """
    Lista todos los nombres de secretos guardados en EnvVar Manager Pro.

    Requiere: keyring disponible.

    Returns:
        Lista de nombres de secretos
    """
    if not KEYRING_DISPONIBLE:
        raise KeyringNoDisponibleError("keyring no está instalado")

    # Nota: keyring no expone una función estándar de "listar todos".
    # Para hacerlo de forma robusta, deberías leer el archivo de índice que
    # mantiene EnvVar Manager Pro en su directorio de datos.
    # Por ahora, retornamos una lista vacía con un aviso.
    try:
        from pathlib import Path

        if os.name == "nt":  # Windows
            datos = Path.home() / "AppData" / "Local" / "EnvVarManagerPro"
        elif os.name == "posix" and os.uname().sysname == "Darwin":  # macOS
            datos = Path.home() / "Library" / "Application Support" / "EnvVarManagerPro"
        else:  # Linux
            datos = Path.home() / ".local" / "share" / "envvarmanagerpro"

        indice_file = datos / "secrets_index.json"
        if indice_file.exists():
            import json

            return json.loads(indice_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    return []


if __name__ == "__main__":
    # Script de prueba
    import sys

    if not KEYRING_DISPONIBLE:
        print("❌ keyring no está instalado. Ejecuta: pip install keyring")
        sys.exit(1)

    print("🔐 Cliente de EnvVar Manager Pro")
    print()

    # Listar secretos disponibles
    secretos = listar_secretos()
    if secretos:
        print(f"Secretos disponibles ({len(secretos)}):")
        for nombre in secretos:
            print(f"  • {nombre}")
        print()

        # Intentar leer uno como ejemplo (el primero)
        ejemplo = secretos[0]
        try:
            valor = get_secret(ejemplo)
            print(f"✅ Ejemplo de lectura: {ejemplo}")
            print(f"   Valor (primeros 20 caracteres): {valor[:20]}..." if len(valor) > 20 else f"   Valor: {valor}")
        except SecretoNoEncontradoError as e:
            print(f"❌ {e}")
    else:
        print("ℹ️  No hay secretos guardados aún.")
        print("   Abre EnvVar Manager Pro → pestaña 'Secretos' → 'Nuevo secreto'")

    print()
    print("📝 Para usar en tu código:")
    print("   from envvar_manager_client import get_secret, get_secret_safe")
    print("   token = get_secret('GITHUB_TOKEN')")
    print("   api_key = get_secret_safe('OPENAI_API_KEY', default='')")
