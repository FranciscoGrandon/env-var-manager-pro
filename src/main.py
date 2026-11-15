"""Punto de entrada de EnvVar Manager Pro."""

from __future__ import annotations

import sys
from tkinter import messagebox

from .gui.app import ejecutar_aplicacion
from .utils.logger_config import get_logger

logger = get_logger(__name__)


def main() -> int:
    try:
        ejecutar_aplicacion()
        return 0
    except Exception as exc:  # última barrera: nunca cerrar sin avisar al usuario
        logger.exception("Error fatal no controlado")
        try:
            messagebox.showerror("EnvVar Manager Pro - Error fatal", str(exc))
        except Exception:
            print(f"Error fatal: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
