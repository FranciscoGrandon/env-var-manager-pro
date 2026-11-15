"""
EJEMPLO 4: Decorator profesional que requiere secretos específicos
antes de ejecutar una función.

Uso:
    python examples/04_decoradores.py
"""

import sys
from pathlib import Path
from functools import wraps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envvar_manager_client import get_secret, SecretoNoEncontradoError


def requiere_secretos(*secretos_necesarios):
    """
    Decorator que valida que los secretos necesarios existan antes de ejecutar la función.

    Uso:
        @requiere_secretos("GITHUB_TOKEN", "OPENAI_API_KEY")
        def mi_funcion():
            token = get_secret("GITHUB_TOKEN")
            ...
    """

    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            faltantes = []
            for secreto in secretos_necesarios:
                try:
                    get_secret(secreto)
                except SecretoNoEncontradoError:
                    faltantes.append(secreto)

            if faltantes:
                print(f"❌ La función '{func.__name__}' requiere secretos que faltan:")
                for s in faltantes:
                    print(f"   • {s}")
                print()
                print("   Abre EnvVar Manager Pro → Secretos → Nuevo secreto")
                raise SecretoNoEncontradoError(f"Secretos faltantes: {', '.join(faltantes)}")

            print(f"✅ Secretos requeridos validados para '{func.__name__}'")
            return func(*args, **kwargs)

        return wrapper

    return decorador


# Ejemplo de uso

@requiere_secretos("GITHUB_TOKEN")
def sincronizar_con_github():
    """Solo se ejecuta si GITHUB_TOKEN existe en EnvVar Manager Pro."""
    print("   🔄 Sincronizando con GitHub...")
    return "sincronización completada"


@requiere_secretos("OPENAI_API_KEY", "GITHUB_TOKEN")
def generar_documentacion_con_ai():
    """Requiere dos secretos."""
    print("   📝 Generando documentación con IA...")
    return "documentación generada"


@requiere_secretos("DATABASE_URL", "DATABASE_PASSWORD")
def hacer_backup_base_datos():
    """Requiere credenciales de base de datos."""
    print("   💾 Haciendo backup de base de datos...")
    return "backup completado"


if __name__ == "__main__":
    print("=" * 70)
    print("EJEMPLO 4: Decorators que requieren secretos")
    print("=" * 70)
    print()

    # Intentar ejecutar funciones que requieren secretos
    funciones = [
        ("sincronizar_con_github", sincronizar_con_github),
        ("generar_documentacion_con_ai", generar_documentacion_con_ai),
        ("hacer_backup_base_datos", hacer_backup_base_datos),
    ]

    for nombre, func in funciones:
        print(f"Intentando ejecutar '{nombre}':")
        try:
            resultado = func()
            print(f"   ✅ Resultado: {resultado}")
        except SecretoNoEncontradoError as e:
            print(f"   ⚠️  No se ejecutó (secretos faltantes)")
        print()

    print("=" * 70)
    print("Ventajas del patrón:")
    print("=" * 70)
    print("✅ Validación automática de secretos requeridos")
    print("✅ Mensajes de error claros")
    print("✅ Fácil de mantener (requiere_secretos define las dependencias)")
    print("✅ Aplicable a tests, scripts, tareas cron, etc.")
    print()
