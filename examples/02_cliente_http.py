"""
EJEMPLO 2: Cliente HTTP que usa tokens de forma segura desde EnvVar Manager Pro.

Simula una aplicación real que hace requests a APIs externas.

Uso:
    python examples/02_cliente_http.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envvar_manager_client import get_secret_safe

print("=" * 70)
print("EJEMPLO 2: Cliente HTTP con tokens seguros")
print("=" * 70)
print()


class GitHubClient:
    """Cliente simple para la API de GitHub, usando secreto de EnvVar Manager."""

    def __init__(self):
        self.token = get_secret_safe("GITHUB_TOKEN")
        if not self.token:
            print("⚠️  GITHUB_TOKEN no encontrado en EnvVar Manager Pro")
            print("   Abre la app → Secretos → Nuevo secreto → GITHUB_TOKEN")
            return

        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        print(f"✅ Cliente GitHub inicializado")
        print(f"   Token configurado: {self.token[:15]}...")

    def get_user(self, username: str) -> dict | None:
        """Simula una búsqueda de usuario en GitHub."""
        if not self.token:
            return None
        # En código real:
        # response = requests.get(f"https://api.github.com/users/{username}", headers=self.headers)
        # return response.json()

        # Por ahora, simulamos:
        print(f"   [SIMULADO] GET https://api.github.com/users/{username}")
        print(f"   Headers: Authorization: token {self.token[:10]}***")
        return {"login": username, "public_repos": 42}


class OpenAIClient:
    """Cliente simple para OpenAI, usando secreto de EnvVar Manager."""

    def __init__(self):
        self.api_key = get_secret_safe("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️  OPENAI_API_KEY no encontrado en EnvVar Manager Pro")
            return

        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        print(f"✅ Cliente OpenAI inicializado")
        print(f"   API Key configurada: {self.api_key[:15]}...")

    def chat_completion(self, prompt: str) -> str | None:
        """Simula una llamada a chat completions."""
        if not self.api_key:
            return None
        # En código real:
        # response = requests.post(
        #     "https://api.openai.com/v1/chat/completions",
        #     headers=self.headers,
        #     json={"model": "gpt-4", "messages": [{"role": "user", "content": prompt}]}
        # )

        print(f"   [SIMULADO] POST https://api.openai.com/v1/chat/completions")
        print(f"   Headers: Authorization: Bearer {self.api_key[:10]}***")
        return "[respuesta simulada de GPT-4]"


print("Inicializando clientes...")
print()

github = GitHubClient()
print()

openai = OpenAIClient()
print()

print("=" * 70)
print("Ventajas de este enfoque:")
print("=" * 70)
print("✅ Los tokens NO están hardcodeados en el código")
print("✅ Los tokens NO están en archivos .env en el repo")
print("✅ Los tokens están cifrados por el SO")
print("✅ Múltiples aplicaciones pueden compartir los mismos secretos")
print("✅ Fácil de rotar: cambias el secreto en EnvVar Manager Pro")
print()
print("=" * 70)
