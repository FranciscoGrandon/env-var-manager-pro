"""
Pruebas unitarias para la capa `core`, independiente de la GUI.

Ejecutar con:  pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.core.crypto import CryptoService, evaluar_fortaleza
from src.core.exceptions import CorruptedBackupError, EnvManagerError, InvalidPasswordError, ValidationError
from src.core.models import BackupPayload, EnvironmentVariable, EnvScope
from src.core.env_service import (
    EnvironmentVariableService,
    validar_nombre_variable,
    _escapar_valor_shell,
    _desescapar_valor_shell,
    _validar_para_unix,
)
from src.core.secrets_service import SecretsService


# ---------------------------------------------------------------- crypto

def test_cifrar_y_descifrar_devuelve_los_mismos_datos():
    crypto = CryptoService()
    data = {"hola": "mundo", "numero": 42}
    blob = crypto.encrypt_payload(data, "clave-super-secreta")
    resultado = crypto.decrypt_payload(blob, "clave-super-secreta")
    assert resultado == data


def test_clave_incorrecta_lanza_invalid_password_error():
    crypto = CryptoService()
    blob = crypto.encrypt_payload({"a": 1}, "clave-correcta")
    with pytest.raises(InvalidPasswordError):
        crypto.decrypt_payload(blob, "clave-incorrecta")


def test_archivo_corrupto_lanza_corrupted_backup_error():
    crypto = CryptoService()
    with pytest.raises(CorruptedBackupError):
        crypto.decrypt_payload(b"esto-no-es-un-respaldo-valido", "cualquier-clave")


def test_dos_respaldos_con_misma_clave_generan_salts_distintos():
    crypto = CryptoService()
    blob1 = crypto.encrypt_payload({"a": 1}, "misma-clave")
    blob2 = crypto.encrypt_payload({"a": 1}, "misma-clave")
    assert blob1 != blob2  # el salt aleatorio garantiza esto


def test_evaluar_fortaleza_contrasena_debil():
    resultado = evaluar_fortaleza("abc")
    assert resultado.score <= 1


def test_evaluar_fortaleza_contrasena_fuerte():
    resultado = evaluar_fortaleza("Cl4ve#Segura2026!")
    assert resultado.score == 4


# ---------------------------------------------------------------- modelos

def test_environment_variable_serializa_y_deserializa():
    var = EnvironmentVariable(name="JAVA_HOME", value="/opt/java", scope=EnvScope.USER)
    data = var.to_dict()
    reconstruida = EnvironmentVariable.from_dict(data)
    assert reconstruida == var


def test_backup_payload_roundtrip():
    variables = [
        EnvironmentVariable(name="A", value="1", scope=EnvScope.USER),
        EnvironmentVariable(name="B", value="2", scope=EnvScope.SESSION),
    ]
    payload = BackupPayload.now(variables, app_version="1.0.0")
    data = payload.to_dict()
    reconstruido = BackupPayload.from_dict(data)
    assert len(reconstruido.variables) == 2
    assert reconstruido.variables[0].name == "A"


# ---------------------------------------------------------------- validación

def test_validar_nombre_variable_vacio():
    with pytest.raises(ValidationError):
        validar_nombre_variable("")


def test_validar_nombre_variable_con_espacios():
    with pytest.raises(ValidationError):
        validar_nombre_variable("MI VARIABLE")


def test_validar_nombre_variable_con_igual():
    with pytest.raises(ValidationError):
        validar_nombre_variable("NOMBRE=X")


def test_validar_nombre_variable_valido_no_lanza():
    validar_nombre_variable("JAVA_HOME")  # no debe lanzar excepción


# ---------------------------------------------------------------- secrets service

@pytest.fixture
def fake_keyring(monkeypatch):
    storage = {}

    def _set_password(service, username, password):
        storage[(service, username)] = password

    def _get_password(service, username):
        return storage.get((service, username))

    def _delete_password(service, username):
        storage.pop((service, username), None)

    import keyring
    monkeypatch.setattr(keyring, "set_password", _set_password)
    monkeypatch.setattr(keyring, "get_password", _get_password)
    monkeypatch.setattr(keyring, "delete_password", _delete_password)
    return storage


def test_secrets_service_guardar_y_obtener(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    assert service.listar_nombres() == []

    service.guardar("API_KEY", "valor_secreto_123")
    assert service.existe("API_KEY") is True
    assert service.obtener("API_KEY") == "valor_secreto_123"
    assert service.listar_nombres() == ["API_KEY"]


def test_secrets_service_existe(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    assert service.existe("NO_EXISTE") is False
    assert service.existe("") is False
    assert service.existe(None) is False

    service.guardar("TOKEN", "abc")
    assert service.existe("TOKEN") is True
    assert service.existe("  TOKEN  ") is True


def test_secrets_service_actualizar_exitoso(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    service.guardar("DB_PASSWORD", "clave_antigua")
    assert service.obtener("DB_PASSWORD") == "clave_antigua"

    service.actualizar("DB_PASSWORD", "clave_nueva_2026")
    assert service.obtener("DB_PASSWORD") == "clave_nueva_2026"
    assert service.existe("DB_PASSWORD") is True
    assert service.listar_nombres() == ["DB_PASSWORD"]


def test_secrets_service_actualizar_inexistente_lanza_error(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    with pytest.raises(EnvManagerError, match="no existe en el almacén"):
        service.actualizar("SECRETO_FANTASMA", "nuevo_valor")


def test_secrets_service_actualizar_nombre_vacio_lanza_error(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    with pytest.raises(EnvManagerError, match="no puede estar vacío"):
        service.actualizar("", "nuevo_valor")
    with pytest.raises(EnvManagerError, match="no puede estar vacío"):
        service.actualizar("   ", "nuevo_valor")


def test_secrets_service_guardar_nombre_vacio_lanza_error(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    with pytest.raises(EnvManagerError, match="no puede estar vacío"):
        service.guardar("", "valor")


def test_secrets_service_eliminar(tmp_path, fake_keyring):
    ruta_indice = tmp_path / "secrets.json"
    service = SecretsService(ruta_indice=ruta_indice)
    service.guardar("SECRETO_A_BORRAR", "123")
    assert service.existe("SECRETO_A_BORRAR") is True

    service.eliminar("SECRETO_A_BORRAR")
    assert service.existe("SECRETO_A_BORRAR") is False
    assert service.obtener("SECRETO_A_BORRAR") is None
    assert service.listar_nombres() == []


# ---------------------------------------------------------------- unix shell escaping & validation

def test_unix_escapar_y_desescapar_roundtrip():
    peligroso = 'test"$(whoami)`id`\\foo$BAR'
    escapado = _escapar_valor_shell(peligroso)
    assert escapado == 'test\\"\\$(whoami)\\`id\\`\\\\foo\\$BAR'
    desescapado = _desescapar_valor_shell(escapado)
    assert desescapado == peligroso


def test_unix_validar_para_unix_rechaza_nombres_peligrosos():
    with pytest.raises(ValidationError, match="En Linux/macOS el nombre debe cumplir"):
        _validar_para_unix("VAR;rm -rf /", "valor")
    with pytest.raises(ValidationError, match="En Linux/macOS el nombre debe cumplir"):
        _validar_para_unix("123VAR", "valor")
    with pytest.raises(ValidationError, match="En Linux/macOS el nombre debe cumplir"):
        _validar_para_unix("VAR$FOO", "valor")


def test_unix_validar_para_unix_rechaza_saltos_de_linea_o_nulos():
    with pytest.raises(ValidationError, match="saltos de línea ni caracteres nulos"):
        _validar_para_unix("VAR_OK", "linea1\nlinea2")
    with pytest.raises(ValidationError, match="saltos de línea ni caracteres nulos"):
        _validar_para_unix("VAR_OK", "linea1\rlinea2")
    with pytest.raises(ValidationError, match="saltos de línea ni caracteres nulos"):
        _validar_para_unix("VAR_OK", "valor\x00malicioso")


def test_unix_validar_para_unix_acepta_validos():
    _validar_para_unix("PATH_LOCAL", "/usr/bin:/bin")
    _validar_para_unix("_MY_APP_KEY", 'clave="123"')


def test_unix_bloque_shell_roundtrip(tmp_path, monkeypatch):
    perfil = tmp_path / ".profile"
    monkeypatch.setattr(EnvironmentVariableService, "_perfil_shell", staticmethod(lambda: perfil))

    svc = EnvironmentVariableService()
    svc._actualizar_bloque_shell({"SEGURO": 'valor"con"comillas y $dolar`backtick`'}, eliminar=[])

    contenido = perfil.read_text(encoding="utf-8")
    assert 'export SEGURO="valor\\"con\\"comillas y \\$dolar\\`backtick\\`"' in contenido

    parsed = svc._parsear_bloque(perfil)
    assert parsed.get("SEGURO") == 'valor"con"comillas y $dolar`backtick`'


def test_unix_bloque_shell_compatibilidad_legacy(tmp_path, monkeypatch):
    perfil = tmp_path / ".profile"
    perfil.write_text(
        '# >>> EnvVar Manager Pro >>>\nexport LEGACY="simple_val"\nexport LEGACY_SIN_COMILLAS=valor123\n# <<< EnvVar Manager Pro <<<\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(EnvironmentVariableService, "_perfil_shell", staticmethod(lambda: perfil))

    svc = EnvironmentVariableService()
    parsed = svc._parsear_bloque(perfil)
    assert parsed.get("LEGACY") == "simple_val"
    assert parsed.get("LEGACY_SIN_COMILLAS") == "valor123"

