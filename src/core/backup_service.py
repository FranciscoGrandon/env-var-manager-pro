"""
Orquesta la creación y restauración de respaldos cifrados, combinando
EnvironmentVariableService (lectura/escritura real) con CryptoService (cifrado).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .. import __version__
from .crypto import CryptoService
from .env_service import EnvironmentVariableService
from .exceptions import EnvManagerError
from .models import BackupPayload, EnvironmentVariable, EnvScope
from ..utils.logger_config import get_logger

logger = get_logger(__name__)


class BackupService:
    def __init__(self, env_service: EnvironmentVariableService, crypto: CryptoService):
        self._env = env_service
        self._crypto = crypto

    def crear_respaldo(
        self, filepath: Path, password: str, scopes: Iterable[EnvScope]
    ) -> int:
        """Crea un archivo de respaldo cifrado. Retorna la cantidad de variables incluidas."""
        variables: List[EnvironmentVariable] = []
        for scope in scopes:
            for name, value in self._env.listar(scope).items():
                variables.append(EnvironmentVariable(name=name, value=value, scope=scope))

        payload = BackupPayload.now(variables, app_version=__version__)
        blob = self._crypto.encrypt_payload(payload.to_dict(), password)

        filepath = Path(filepath)
        filepath.write_bytes(blob)
        logger.info(
            "Respaldo creado en %s con %d variables (%s)",
            filepath,
            len(variables),
            ", ".join(s.value for s in scopes),
        )
        return len(variables)

    def previsualizar_respaldo(self, filepath: Path, password: str) -> BackupPayload:
        """Descifra y retorna el contenido sin aplicar cambios al sistema."""
        blob = Path(filepath).read_bytes()
        data = self._crypto.decrypt_payload(blob, password)
        return BackupPayload.from_dict(data)

    def restaurar_respaldo(
        self,
        payload: BackupPayload | None,
        variables_seleccionadas: Iterable[EnvironmentVariable] | None = None,
    ) -> tuple[int, list[str]]:
        """
        Aplica al sistema las variables del payload (o un subconjunto seleccionado).
        Retorna (cantidad_aplicadas, lista_de_errores).
        """
        objetivo = list(variables_seleccionadas) if variables_seleccionadas is not None else payload.variables
        aplicadas = 0
        errores: list[str] = []

        for var in objetivo:
            try:
                self._env.establecer(var.name, var.value, var.scope)
                aplicadas += 1
            except EnvManagerError as exc:
                errores.append(f"{var.name} ({var.scope.value}): {exc}")
                logger.warning("No se pudo restaurar '%s': %s", var.name, exc)

        return aplicadas, errores
