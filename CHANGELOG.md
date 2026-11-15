# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Creado por Francisco Grandón Vergara

## [1.2.0] - 2026-11-15

### Añadido
- Neutralización de interfaz `keyring_secrets_gui.py` bajo estilo **Corporate Light UI** (`Secrets.Treeview`) para distribución pública open-source.
- Documentación técnica exhaustiva en `README.md` sobre riesgos de texto plano en variables de entorno/archivos `.env` y mitigaciones arquitectónicas implementadas.
- Soporte documentado y unificado para respaldos cifrados portables `.evb` (variables de entorno, magic `EVMB`) y `.ksb` (secretos keyring, magic `KSMB`).

### Cambiado
- Alineación de versión del paquete (`pyproject.toml`) a `1.2.0` en concordancia con `src/__init__.py`.
- Actualización de URLs del proyecto a `https://github.com/FranciscoGrandon/env-var-manager-pro`.

### Corregido
- Corrección de la especificación criptográfica documentada para reflejar fielmente la implementación real: derivación `PBKDF2-HMAC-SHA256` con `480.000` iteraciones (sal aleatoria de 16 bytes) y cifrado autenticado `Fernet` (`AES-128-CBC` con padding PKCS7 + `HMAC-SHA256` de 32 bytes).

## [1.0.0] - 2026-11-10

### Añadido
- Versión inicial pública de **EnvVar Manager Pro**.
- Gestión visual y por CLI de variables de entorno (Usuario, Sistema y Sesión) en Windows, macOS y Linux.
- Integración nativa con almacenes de credenciales del sistema operativo mediante `keyring` (Windows Credential Locker, macOS Keychain, Secret Service de Linux).
- Herramienta CLI especializada (`keyring_secrets_cli.py`) con soporte `--json` determinista y entrada por tubería `--stdin` para integración fluida en subagentes de IA y pipelines de CI/CD.
- Interfaz gráfica moderna y accesible (`keyring_secrets_gui.py`) construida en Tkinter/ttk con paleta clara de alto contraste y estricto cumplimiento tipográfico.
- Módulo cliente desacoplado (`envvar_manager_client.py`) para consumo seguro de secretos en aplicaciones de terceros sin exponer credenciales en código ni archivos `.env` planos.
- Sistema criptográfico de respaldos (`.evb` y `.ksb`) utilizando derivación `PBKDF2-HMAC-SHA256` (`480.000` iteraciones, sal de 16 bytes) y cifrado autenticado `Fernet` (`AES-128-CBC + HMAC-SHA256`), con previsualización selectiva antes de restaurar.
- Notificación reactiva a nivel de sistema operativo (`WM_SETTINGCHANGE` vía `SendMessageTimeoutW` en Windows) para propagación de cambios sin cerrar sesión.
- Cobertura completa de pruebas unitarias y de integración (`tests/`) para validación de servicios de entorno, cifrado, respaldos y CLI.
- Configuración estándar de empaquetado y distribución compatible con PEP 517/621 (`pyproject.toml`).
