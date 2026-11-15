"""
EJEMPLO 3: Patrón de configuración profesional que mezcla secretos
(tokens, claves API) con variables de entorno (rutas, flags).

Uso:
    python examples/03_config_app.py
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envvar_manager_client import get_secret_safe


@dataclass
class Configuracion:
    """Configuración centralizada de la aplicación."""

    # Secretos (desde keyring de EnvVar Manager Pro)
    github_token: str | None
    openai_api_key: str | None
    database_password: str | None

    # Variables de entorno (no sensibles)
    debug: bool
    log_level: str
    data_dir: str

    @staticmethod
    def cargar() -> "Configuracion":
        """Carga la configuración desde secretos y variables de entorno."""
        print("🔧 Cargando configuración...")
        print()

        # Secretos: desde EnvVar Manager Pro (keyring)
        print("Secretos:")
        github_token = get_secret_safe("GITHUB_TOKEN")
        print(f"  • GITHUB_TOKEN: {'✅ encontrado' if github_token else '⚠️  no encontrado'}")

        openai_api_key = get_secret_safe("OPENAI_API_KEY")
        print(f"  • OPENAI_API_KEY: {'✅ encontrado' if openai_api_key else '⚠️  no encontrado'}")

        database_password = get_secret_safe("DB_PASSWORD")
        print(f"  • DB_PASSWORD: {'✅ encontrado' if database_password else '⚠️  no encontrado'}")
        print()

        # Variables de entorno: no sensibles
        print("Variables de entorno:")
        debug = os.getenv("DEBUG", "false").lower() == "true"
        print(f"  • DEBUG: {debug}")

        log_level = os.getenv("LOG_LEVEL", "INFO")
        print(f"  • LOG_LEVEL: {log_level}")

        data_dir = os.getenv("DATA_DIR", str(Path.home() / "myapp_data"))
        print(f"  • DATA_DIR: {data_dir}")
        print()

        return Configuracion(
            github_token=github_token,
            openai_api_key=openai_api_key,
            database_password=database_password,
            debug=debug,
            log_level=log_level,
            data_dir=data_dir,
        )

    def validar(self) -> bool:
        """Valida que los secretos críticos estén disponibles."""
        criticos = [self.database_password]  # DB password es crítico para la app
        faltantes = [s for s in criticos if not s]
        if faltantes:
            print("❌ Secretos críticos faltantes:")
            print("   La aplicación no puede funcionar sin:")
            print("   • DB_PASSWORD (abre EnvVar Manager Pro → Secretos → Nuevo secreto)")
            return False
        return True

    def resumen(self):
        """Imprime un resumen de la configuración cargada."""
        print("=" * 70)
        print("CONFIGURACIÓN CARGADA")
        print("=" * 70)
        print()
        print("🔐 Secretos:")
        print(f"   GITHUB_TOKEN:    {self.github_token[:15] + '...' if self.github_token else '(no configurado)'}")
        print(f"   OPENAI_API_KEY:  {self.openai_api_key[:15] + '...' if self.openai_api_key else '(no configurado)'}")
        print(f"   DB_PASSWORD:     {self.database_password[:15] + '...' if self.database_password else '(NO CONFIGURADO - CRÍTICO)'}")
        print()
        print("⚙️  Variables de entorno:")
        print(f"   DEBUG:           {self.debug}")
        print(f"   LOG_LEVEL:       {self.log_level}")
        print(f"   DATA_DIR:        {self.data_dir}")
        print()
        print("=" * 70)


if __name__ == "__main__":
    # Cargar configuración
    config = Configuracion.cargar()

    # Validar
    if not config.validar():
        print()
        print("⚠️  Faltan secretos críticos. La app no puede iniciar.")
        sys.exit(1)

    # Mostrar resumen
    config.resumen()

    print()
    print("✅ Aplicación lista para ejecutarse con configuración segura")
    print()
    print("Patrón aplicable a:")
    print("  • Tu FG Agente Telegram")
    print("  • Scripts de procesamiento de datos")
    print("  • Bots y servicios backend")
    print("  • Herramientas de escritorio")
