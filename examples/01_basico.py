"""
EJEMPLO 1: Script básico que lee secretos de EnvVar Manager Pro.

Uso:
    python examples/01_basico.py
"""

import sys
from pathlib import Path

# Agregar la carpeta raíz al path para importar envvar_manager_client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envvar_manager_client import get_secret, get_secret_safe, SecretoNoEncontradoError

print("=" * 60)
print("EJEMPLO 1: Lectura básica de secretos")
print("=" * 60)
print()

# Forma 1: get_secret() — fallar si no existe
print("1️⃣  Lectura con error si no existe:")
try:
    github_token = get_secret("GITHUB_TOKEN")
    print(f"   ✅ GITHUB_TOKEN encontrado (primeros 10 chars): {github_token[:10]}...")
except SecretoNoEncontradoError as e:
    print(f"   ⚠️  {e}")
print()

# Forma 2: get_secret_safe() — retornar default
print("2️⃣  Lectura segura con valor por defecto:")
openai_key = get_secret_safe("OPENAI_API_KEY", default="sk-dev-local")
print(f"   OPENAI_API_KEY = {openai_key[:15]}..." if len(openai_key) > 15 else f"   OPENAI_API_KEY = {openai_key}")
print()

# Forma 3: Cascada — keyring primero, luego env
print("3️⃣  Cascada keyring → variable de entorno:")
import os

api_token = get_secret_safe("API_TOKEN") or os.getenv("API_TOKEN") or "default-token"
print(f"   API_TOKEN (keyring o env o default) = {api_token}")
print()

print("=" * 60)
print("✅ Usa estas técnicas en tus aplicaciones reales")
print("=" * 60)
