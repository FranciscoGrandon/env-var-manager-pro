"""
Pruebas para keyring_secrets_cli.py
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

DIR_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = DIR_ROOT / "keyring_secrets_cli.py"


def ejecutar_cli(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CLI_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=encoding_safe(), cwd=str(DIR_ROOT))


def encoding_safe() -> str:
    return "utf-8"


def test_cli_help():
    res = ejecutar_cli("--help")
    assert res.returncode == 0
    assert "CLI para Agentes" in res.stdout


def test_cli_backend_json():
    res = ejecutar_cli("backend", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["success"] is True
    assert "backend" in data["data"]
    assert "service" in data["data"]


def test_cli_list_json():
    res = ejecutar_cli("list", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_cli_exists_json():
    res = ejecutar_cli("exists", "SECRET_FANTASMA_INEXISTENTE_12345", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["success"] is True
    assert data["data"]["exists_in_index"] is False
    assert data["data"]["present_in_keyring"] is False


def test_cli_get_no_existente_json():
    res = ejecutar_cli("get", "SECRET_FANTASMA_INEXISTENTE_12345", "--json")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["success"] is False
    assert "no se encuentra" in data["error"]


def test_cli_backup_e_inspect_cifrado(tmp_path):
    archivo_respaldo = tmp_path / "test_backup.ksb"
    clave = "PasswordPrueba2026!"

    # 1. Crear respaldo cifrado
    res_bkp = ejecutar_cli("backup", str(archivo_respaldo), "--password", clave, "--json")
    assert res_bkp.returncode == 0
    data_bkp = json.loads(res_bkp.stdout)
    assert data_bkp["success"] is True
    assert archivo_respaldo.exists()

    # 2. Inspeccionar con clave correcta
    res_ins = ejecutar_cli("inspect", str(archivo_respaldo), "--password", clave, "--json")
    assert res_ins.returncode == 0
    data_ins = json.loads(res_ins.stdout)
    assert data_ins["success"] is True
    assert data_ins["data"]["type"] == "keyring_secrets_backup"

    # 3. Inspeccionar con clave incorrecta
    res_err = ejecutar_cli("inspect", str(archivo_respaldo), "--password", "ClaveErronea123!", "--json")
    assert res_err.returncode == 1
    data_err = json.loads(res_err.stdout)
    assert data_err["success"] is False
    assert "incorrecta" in data_err["error"].lower()
