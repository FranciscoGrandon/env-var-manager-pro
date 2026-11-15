#!/usr/bin/env python3
"""
keyring_secrets_cli.py — CLI especializado para Agentes y Scripts de Automatización.

Gestiona secretos (tokens, passwords, API keys) en el almacén de credenciales nativo
del Sistema Operativo (Windows Credential Locker / macOS Keychain / Secret Service)
utilizando `keyring` y el índice unificado de EnvVar Manager Pro.

Diseñado con salida JSON determinista para agentes de IA y flujos CI/CD.

Uso:
    python keyring_secrets_cli.py list [--json]
    python keyring_secrets_cli.py get <NOMBRE> [--json] [--reveal]
    python keyring_secrets_cli.py set <NOMBRE> <VALOR> [--json] [--force]
    python keyring_secrets_cli.py set <NOMBRE> --stdin [--json] [--force]
    python keyring_secrets_cli.py update <NOMBRE> <VALOR> [--json]
    python keyring_secrets_cli.py delete <NOMBRE> [--json]
    python keyring_secrets_cli.py exists <NOMBRE> [--json]
    python keyring_secrets_cli.py backend [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar importación de src dentro de env_var_manager
DIRECTORIO_RAIZ = Path(__file__).resolve().parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from src.core.exceptions import EnvManagerError, InvalidPasswordError, CorruptedBackupError
from src.core.secrets_service import SecretsService, KEYRING_DISPONIBLE, SecretBackendNoDisponibleError
from src.core.keyring_backup_service import KeyringBackupService


def _responder(ok: bool, data: Any = None, error: Optional[str] = None, json_mode: bool = False, exit_code: int = 0) -> None:
    """Emite la respuesta formateada en JSON o texto plano estándar y termina el proceso."""
    if json_mode:
        payload = {
            "success": ok,
            "data": data,
            "error": error
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if ok:
            if data is not None:
                if isinstance(data, list):
                    for item in data:
                        print(item)
                elif isinstance(data, dict):
                    for k, v in data.items():
                        print(f"{k}: {v}")
                else:
                    print(str(data))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(exit_code)


def comando_backend(service: SecretsService, json_mode: bool) -> None:
    backend_nombre = service.backend_activo()
    info = {
        "service": service.SERVICIO,
        "backend": backend_nombre,
        "keyring_available": KEYRING_DISPONIBLE,
        "index_path": str(service._ruta_indice)
    }
    _responder(ok=True, data=info, json_mode=json_mode)


def comando_list(service: SecretsService, json_mode: bool, with_status: bool = False) -> None:
    nombres = service.listar_nombres()
    if json_mode:
        if with_status:
            detalles = []
            for n in nombres:
                # Comprobar si existe valor real sin revelar el secreto
                val = service.obtener(n)
                detalles.append({
                    "name": n,
                    "present_in_os": val is not None,
                    "length": len(val) if val is not None else 0
                })
            _responder(ok=True, data=detalles, json_mode=True)
        else:
            _responder(ok=True, data=nombres, json_mode=True)
    else:
        if not nombres:
            print("No hay secretos registrados en el almacén.")
        else:
            for n in nombres:
                print(n)


def comando_exists(service: SecretsService, nombre: str, json_mode: bool) -> None:
    nombre_limpio = nombre.strip()
    existe_indice = service.existe(nombre_limpio)
    # Comprobar presencia real en keyring
    val = service.obtener(nombre_limpio) if existe_indice else None
    presente = val is not None

    data = {
        "name": nombre_limpio,
        "exists_in_index": existe_indice,
        "present_in_keyring": presente
    }
    
    if json_mode:
        _responder(ok=True, data=data, json_mode=True)
    else:
        if presente:
            print(f"El secreto '{nombre_limpio}' existe y está disponible en el almacén.")
            sys.exit(0)
        elif existe_indice:
            print(f"El secreto '{nombre_limpio}' está indexado pero sin valor en el almacén del SO.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"El secreto '{nombre_limpio}' NO existe.", file=sys.stderr)
            sys.exit(1)


def comando_get(service: SecretsService, nombre: str, json_mode: bool, reveal: bool = True) -> None:
    nombre_limpio = nombre.strip()
    try:
        valor = service.obtener(nombre_limpio)
        if valor is None:
            _responder(
                ok=False,
                error=f"El secreto '{nombre_limpio}' no se encuentra en el almacén seguro.",
                json_mode=json_mode,
                exit_code=1
            )
        
        if json_mode:
            data = {
                "name": nombre_limpio,
                "length": len(valor),
                "value": valor if reveal else f"{valor[:3]}*** (oculto)"
            }
            _responder(ok=True, data=data, json_mode=True)
        else:
            if reveal:
                print(valor)
            else:
                print(f"[Oculto: {len(valor)} caracteres]")
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_set(service: SecretsService, nombre: str, valor: str, force: bool, json_mode: bool) -> None:
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        _responder(ok=False, error="El nombre del secreto no puede estar vacío.", json_mode=json_mode, exit_code=1)

    if service.existe(nombre_limpio) and not force:
        _responder(
            ok=False,
            error=f"El secreto '{nombre_limpio}' ya existe. Usa 'update' o el flag '--force' para sobrescribirlo.",
            json_mode=json_mode,
            exit_code=1
        )

    try:
        service.guardar(nombre_limpio, valor)
        data = {
            "name": nombre_limpio,
            "saved": True,
            "length": len(valor),
            "service": service.SERVICIO
        }
        _responder(ok=True, data=data, json_mode=json_mode)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_update(service: SecretsService, nombre: str, valor: str, json_mode: bool) -> None:
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        _responder(ok=False, error="El nombre del secreto no puede estar vacío.", json_mode=json_mode, exit_code=1)

    try:
        service.actualizar(nombre_limpio, valor)
        data = {
            "name": nombre_limpio,
            "updated": True,
            "length": len(valor),
            "service": service.SERVICIO
        }
        _responder(ok=True, data=data, json_mode=json_mode)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_delete(service: SecretsService, nombre: str, json_mode: bool) -> None:
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        _responder(ok=False, error="El nombre del secreto no puede estar vacío.", json_mode=json_mode, exit_code=1)

    try:
        service.eliminar(nombre_limpio)
        data = {
            "name": nombre_limpio,
            "deleted": True
        }
        _responder(ok=True, data=data, json_mode=json_mode)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_backup(service: SecretsService, ruta: str, password: str, nombres: Optional[List[str]], json_mode: bool) -> None:
    backup_mgr = KeyringBackupService(service)
    try:
        count, path_out = backup_mgr.exportar_respaldo(Path(ruta), password, nombres_seleccionados=nombres)
        data = {
            "backup_file": str(path_out),
            "secrets_count": count,
            "status": "encrypted"
        }
        _responder(ok=True, data=data, json_mode=json_mode)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_inspect(ruta: str, password: str, reveal: bool, json_mode: bool) -> None:
    backup_mgr = KeyringBackupService()
    try:
        data = backup_mgr.inspeccionar_respaldo(Path(ruta), password)
        secretos = data.get("secrets", {})
        
        info = {
            "type": data.get("type"),
            "created_at": data.get("created_at"),
            "hostname": data.get("hostname"),
            "count": len(secretos),
            "secrets": [
                {
                    "name": k,
                    "length": len(v),
                    "value": v if reveal else f"{v[:3]}*** (oculto)"
                }
                for k, v in secretos.items()
            ]
        }
        _responder(ok=True, data=info, json_mode=json_mode)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def comando_restore(service: SecretsService, ruta: str, password: str, overwrite: bool, nombres: Optional[List[str]], json_mode: bool) -> None:
    backup_mgr = KeyringBackupService(service)
    try:
        restaurados, omitidos, errores = backup_mgr.restaurar_respaldo(
            Path(ruta), password, sobrescribir=overwrite, nombres_a_restaurar=nombres
        )
        data = {
            "restored_count": restaurados,
            "skipped_count": omitidos,
            "errors": errores
        }
        ok = len(errores) == 0
        _responder(ok=ok, data=data, error="Errores durante la restauración" if not ok else None, json_mode=json_mode, exit_code=0 if ok else 1)
    except Exception as exc:
        _responder(ok=False, error=str(exc), json_mode=json_mode, exit_code=1)


def parse_args() -> argparse.Namespace:
    # Parser padre para compartir argumentos como --json entre todos los subcomandos
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--json", action="store_true", help="Salida en formato JSON estructurado")

    parser = argparse.ArgumentParser(
        description="CLI para Agentes: Gestión segura y Respaldo Cifrado de credenciales en Keyring (SO)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[base_parser],
        epilog="""
Ejemplos para agentes y scripts:
  python keyring_secrets_cli.py list --json
  python keyring_secrets_cli.py get GITHUB_TOKEN --json
  python keyring_secrets_cli.py set MI_NUEVA_KEY "secreto123" --json
  echo "secreto123" | python keyring_secrets_cli.py set MI_NUEVA_KEY --stdin --json
  python keyring_secrets_cli.py backup "C:\\respaldos\\secretos.ksb" --password "ClaveSegura2026!" --json
  python keyring_secrets_cli.py inspect "C:\\respaldos\\secretos.ksb" --password "ClaveSegura2026!" --json
  python keyring_secrets_cli.py restore "C:\\respaldos\\secretos.ksb" --password "ClaveSegura2026!" --json
        """
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponibles")

    # backend
    subparsers.add_parser("backend", parents=[base_parser], help="Información del almacén activo y estado de keyring")

    # list
    p_list = subparsers.add_parser("list", parents=[base_parser], help="Listar nombres de secretos registrados")
    p_list.add_argument("--details", action="store_true", help="Incluir longitud y estado en keyring")

    # exists
    p_exists = subparsers.add_parser("exists", parents=[base_parser], help="Verifica si un secreto existe")
    p_exists.add_argument("name", help="Nombre del secreto")

    # get
    p_get = subparsers.add_parser("get", parents=[base_parser], help="Obtener el valor de un secreto")
    p_get.add_argument("name", help="Nombre del secreto")
    p_get.add_argument("--no-reveal", dest="reveal", action="store_false", default=True, help="Ocultar el valor en la salida (solo metadatos)")

    # set
    p_set = subparsers.add_parser("set", parents=[base_parser], help="Crear o guardar un nuevo secreto")
    p_set.add_argument("name", help="Nombre del secreto")
    p_set.add_argument("value", nargs="?", default=None, help="Valor del secreto (omitir si se usa --stdin)")
    p_set.add_argument("--stdin", action="store_true", help="Leer el valor secreto desde la entrada estándar")
    p_set.add_argument("--force", "-f", action="store_true", help="Sobrescribir si el secreto ya existe")

    # update
    p_upd = subparsers.add_parser("update", parents=[base_parser], help="Actualizar un secreto existente")
    p_upd.add_argument("name", help="Nombre del secreto")
    p_upd.add_argument("value", nargs="?", default=None, help="Nuevo valor (omitir si se usa --stdin)")
    p_upd.add_argument("--stdin", action="store_true", help="Leer el valor secreto desde la entrada estándar")

    # delete
    p_del = subparsers.add_parser("delete", parents=[base_parser], help="Eliminar un secreto del almacén")
    p_del.add_argument("name", help="Nombre del secreto")

    # backup (export)
    p_bkp = subparsers.add_parser("backup", parents=[base_parser], help="Exportar secretos a un archivo cifrado (.ksb)")
    p_bkp.add_argument("file", help="Ruta de destino del archivo cifrado (.ksb)")
    p_bkp.add_argument("--password", "-p", required=True, help="Contraseña para cifrar el respaldo con PBKDF2+Fernet")
    p_bkp.add_argument("--include", nargs="*", help="Nombres específicos de secretos a incluir (por defecto todos)")

    # inspect (view backup)
    p_ins = subparsers.add_parser("inspect", parents=[base_parser], help="Descifrar y ver contenido de un respaldo (.ksb)")
    p_ins.add_argument("file", help="Ruta del archivo cifrado (.ksb)")
    p_ins.add_argument("--password", "-p", required=True, help="Contraseña de descifrado")
    p_ins.add_argument("--no-reveal", dest="reveal", action="store_false", default=True, help="Ocultar los valores descifrados")

    # restore
    p_rst = subparsers.add_parser("restore", parents=[base_parser], help="Restaurar secretos desde un archivo cifrado (.ksb) al Keyring local")
    p_rst.add_argument("file", help="Ruta del archivo cifrado (.ksb)")
    p_rst.add_argument("--password", "-p", required=True, help="Contraseña de descifrado")
    p_rst.add_argument("--no-overwrite", dest="overwrite", action="store_false", default=True, help="No sobrescribir si el secreto ya existe en el SO")
    p_rst.add_argument("--include", nargs="*", help="Restaurar solo estos nombres específicos")

    return parser, parser.parse_args()


def main() -> int:
    parser, args = parse_args()

    if not args.subcommand:
        parser.print_help()
        # Si fue ejecutado mediante doble clic desde el Explorador de Windows (sin terminal interactiva)
        # o sys.stdin no es interactivo pero queremos evitar que la ventana se cierre de golpe:
        try:
            if sys.stdin and sys.stdin.isatty():
                # En un shell normal, solo mostrar la ayuda y salir limpiamente con 0
                return 0
            else:
                input("\nPresiona Enter para cerrar...")
        except Exception:
            pass
        return 0

    try:
        service = SecretsService()
    except Exception as exc:
        _responder(ok=False, error=f"No se pudo inicializar SecretsService: {exc}", json_mode=args.json, exit_code=1)
        return 1

    cmd = args.subcommand
    json_mode = args.json

    if cmd == "backend":
        comando_backend(service, json_mode)
    elif cmd == "list":
        comando_list(service, json_mode, with_status=args.details)
    elif cmd == "exists":
        comando_exists(service, args.name, json_mode)
    elif cmd == "get":
        comando_get(service, args.name, json_mode, reveal=args.reveal)
    elif cmd == "set":
        valor = args.value
        if args.stdin:
            valor = sys.stdin.read().rstrip("\r\n")
        if valor is None:
            _responder(ok=False, error="Debes proveer un valor o especificar --stdin", json_mode=json_mode, exit_code=1)
        comando_set(service, args.name, valor, force=args.force, json_mode=json_mode)
    elif cmd == "update":
        valor = args.value
        if args.stdin:
            valor = sys.stdin.read().rstrip("\r\n")
        if valor is None:
            _responder(ok=False, error="Debes proveer un valor o especificar --stdin", json_mode=json_mode, exit_code=1)
        comando_update(service, args.name, valor, json_mode=json_mode)
    elif cmd == "delete":
        comando_delete(service, args.name, json_mode)
    elif cmd == "backup":
        comando_backup(service, args.file, args.password, args.include, json_mode)
    elif cmd == "inspect":
        comando_inspect(args.file, args.password, reveal=args.reveal, json_mode=json_mode)
    elif cmd == "restore":
        comando_restore(service, args.file, args.password, overwrite=args.overwrite, nombres=args.include, json_mode=json_mode)

    return 0


if __name__ == "__main__":
    sys.exit(main())
