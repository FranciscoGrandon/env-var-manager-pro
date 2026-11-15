"""
Configuración centralizada de logging para toda la aplicación.

Los logs se guardan en un directorio de datos de usuario (multiplataforma)
con rotación automática para no crecer indefinidamente, y también se
muestran en consola durante el desarrollo.
"""

from __future__ import annotations

import logging
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURADO = False


def _directorio_datos() -> Path:
    if platform.system() == "Windows":
        base = Path.home() / "AppData" / "Local" / "EnvVarManagerPro"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "EnvVarManagerPro"
    else:
        base = Path.home() / ".local" / "share" / "envvarmanagerpro"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _configurar_una_vez() -> None:
    global _CONFIGURADO
    if _CONFIGURADO:
        return

    log_dir = _directorio_datos() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root = logging.getLogger("envvarmanager")
    root.setLevel(logging.DEBUG)

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formato)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)
    console_handler.setLevel(logging.INFO)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _CONFIGURADO = True


def get_logger(name: str) -> logging.Logger:
    _configurar_una_vez()
    return logging.getLogger(f"envvarmanager.{name.split('.')[-1]}")


def ruta_log_actual() -> Path:
    return _directorio_datos() / "logs" / "app.log"
