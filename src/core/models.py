"""
Modelos de datos inmutables/estructurados usados en toda la aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class EnvScope(str, Enum):
    """Alcance de una variable de entorno."""

    USER = "USER"        # Persistente, solo para el usuario actual
    SYSTEM = "SYSTEM"     # Persistente, para todos los usuarios (requiere admin)
    SESSION = "SESSION"   # Solo en memoria del proceso actual (os.environ)

    @property
    def etiqueta(self) -> str:
        return {
            EnvScope.USER: "Usuario",
            EnvScope.SYSTEM: "Sistema",
            EnvScope.SESSION: "Sesión actual",
        }[self]


@dataclass(frozen=True)
class EnvironmentVariable:
    """Representa una variable de entorno con su alcance."""

    name: str
    value: str
    scope: EnvScope

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "scope": self.scope.value}

    @staticmethod
    def from_dict(data: dict) -> "EnvironmentVariable":
        return EnvironmentVariable(
            name=data["name"], value=data["value"], scope=EnvScope(data["scope"])
        )


@dataclass
class BackupPayload:
    """Contenido completo de un respaldo, antes/después de cifrar."""

    created_at: str
    app_version: str
    hostname: str
    variables: List[EnvironmentVariable] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "app_version": self.app_version,
            "hostname": self.hostname,
            "variables": [v.to_dict() for v in self.variables],
        }

    @staticmethod
    def from_dict(data: dict) -> "BackupPayload":
        return BackupPayload(
            created_at=data.get("created_at", ""),
            app_version=data.get("app_version", "desconocida"),
            hostname=data.get("hostname", ""),
            variables=[EnvironmentVariable.from_dict(v) for v in data.get("variables", [])],
        )

    @staticmethod
    def now(variables: List[EnvironmentVariable], app_version: str) -> "BackupPayload":
        import socket

        return BackupPayload(
            created_at=datetime.now().isoformat(timespec="seconds"),
            app_version=app_version,
            hostname=socket.gethostname(),
            variables=variables,
        )
