"""
Excepciones personalizadas para EnvVar Manager Pro.

Definir excepciones específicas del dominio permite manejar errores de forma
granular en la capa de GUI, mostrando mensajes claros al usuario en lugar de
tracebacks genéricos.
"""


class EnvManagerError(Exception):
    """Excepción base para todos los errores de la aplicación."""


class PermissionDeniedError(EnvManagerError):
    """Se lanza cuando la operación requiere privilegios de administrador."""


class InvalidPasswordError(EnvManagerError):
    """Se lanza cuando la clave de descifrado es incorrecta o el archivo está dañado."""


class CorruptedBackupError(EnvManagerError):
    """Se lanza cuando el archivo de respaldo no tiene el formato esperado."""


class UnsupportedPlatformError(EnvManagerError):
    """Se lanza cuando la operación no está soportada en el sistema operativo actual."""


class ValidationError(EnvManagerError):
    """Se lanza cuando el nombre o valor de una variable no es válido."""
