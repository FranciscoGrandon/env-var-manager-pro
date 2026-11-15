"""Validaciones reutilizables para la capa de GUI."""

from __future__ import annotations

from pathlib import Path


def contrasenas_coinciden(p1: str, p2: str) -> bool:
    return len(p1) > 0 and p1 == p2


def ruta_valida_para_escritura(ruta: str) -> bool:
    try:
        p = Path(ruta)
        return p.parent.exists()
    except Exception:
        return False
