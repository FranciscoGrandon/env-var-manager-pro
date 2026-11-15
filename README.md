# EnvVar Manager Pro

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-1.2.0-informational.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Crypto: PBKDF2 + Fernet](https://img.shields.io/badge/Crypto-PBKDF2%20%2B%20Fernet-green.svg)](src/core/crypto.py)
[![Keyring: Native OS](https://img.shields.io/badge/Keyring-Native%20OS-brightgreen.svg)](https://github.com/jaraco/keyring)

> **Creado por Francisco Grandón Vergara**  
> Repositorio oficial: [https://github.com/FranciscoGrandon/env-var-manager-pro](https://github.com/FranciscoGrandon/env-var-manager-pro)

**EnvVar Manager Pro** es una suite de escritorio, CLI y SDK en Python para separar de forma estricta la **configuración del sistema** (variables de entorno) de las **credenciales sensibles** (tokens, API keys, contraseñas), delegando estas últimas al almacén cifrado nativo del sistema operativo (`keyring`) y ofreciendo respaldos portables cifrados con `PBKDF2-HMAC-SHA256` + `Fernet`.

---

## 🎯 Propuesta de Valor: Separar Configuración de Secretos

En el desarrollo diario, es habitual mezclar parámetros inocuos (`PORT`, `LOG_LEVEL`, `PATH`) con credenciales críticas (`OPENAI_API_KEY`, `DB_PASSWORD`, `GITHUB_TOKEN`) dentro del mismo archivo `.env` o en las variables de entorno del usuario.

**EnvVar Manager Pro** parte de un principio arquitectónico simple:
1. **Variables de entorno** → Solo para configuración no sensible (rutas, flags, modos de ejecución). Administrables por ámbito (**Usuario**, **Sistema** o **Sesión**).
2. **Secretos y credenciales** → Almacenados exclusivamente en la bóveda nativa del sistema operativo (Windows Credential Manager / macOS Keychain / Linux Secret Service) bajo el servicio `EnvVarManagerPro`, accesibles bajo demanda desde Python o CLI sin pasar por el entorno del proceso.

| Criterio | Variables de Entorno / `.env` | Bóveda Nativa (`keyring`) en EnvVar Manager Pro |
| :--- | :--- | :--- |
| **Almacenamiento** | Texto plano (Registro de Windows, `~/.profile`, archivo `.env`) | Cifrado por el sistema operativo (DPAPI, Keychain, Secret Service) |
| **Exposición a subprocesos** | Heredada automáticamente a todo proceso hijo | Ninguna: los procesos hijos no ven los secretos en `os.environ` |
| **Riesgo de volcado accidental** | Alto (logs de error, crash dumps, `/proc/<pid>/environ`) | Aislado bajo demanda mediante lectura explícita por nombre |
| **Uso recomendado** | `PATH`, `JAVA_HOME`, `APP_ENV`, `PORT` | API keys, tokens PAT, contraseñas de BD, secretos OAuth |

---

## ⚠️ Análisis Técnico de Riesgos: El Problema del Texto Plano

Guardar secretos en archivos `.env` o en variables de entorno persistentes (`HKCU\Environment`, `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment`, `~/.bashrc`, `~/.zshrc`) introduce cuatro vectores de exposición reales bajo el capó:

1. **Herencia indiscriminada en `os.environ`:**  
   Cuando un proceso arranca, recibe una copia completa del bloque de entorno de su proceso padre. A su vez, cualquier subproceso que ese programa lance (intérpretes, linters, herramientas CLI de terceros, compiladores o telemetría) hereda exactamente las mismas variables. Un paquete de terceros comprometido o un plugin con acceso a `os.environ` obtiene todas tus API keys sin necesidad de privilegios elevados.
2. **Exposición en volcados, diagnósticos y `/proc`:**  
   Numerosos frameworks web, agentes de monitoreo y manejadores de excepciones capturan el entorno completo en crash reports o logs de CI/CD. En Linux, `/proc/<pid>/environ` expone el bloque de entorno inicial del proceso; en Windows, herramientas de inspección de procesos (como Process Explorer o volcados de memoria minidump) leen el *Process Environment Block (PEB)* en texto plano.
3. **Filtración en el historial del shell:**  
   Ejecutar comandos como `export API_KEY="sk-..."` o `cli.py set API_KEY sk-...` deja la credencial persistida en texto plano dentro de `~/.bash_history`, `~/.zsh_history` o el archivo `ConsoleHost_history.txt` de `PSReadLine` en PowerShell.
4. **Commits accidentales y ausencia de aislamiento en disco:**  
   Un archivo `.env` sin cifrar es legible por cualquier proceso ejecutado bajo la misma sesión de usuario (o respaldos en la nube sincronizados como OneDrive/Dropbox), y un descuido en `.gitignore` basta para filtrar credenciales al historial de Git.

---

## 🛡️ Cómo Mitiga Esta Aplicación Cada Riesgo

### 1. Aislamiento en Bóveda Nativa del SO (`SecretsService`)
- Deja de escribir credenciales en el Registro o en `.env`. Los secretos se almacenan mediante `keyring` bajo el identificador de servicio `EnvVarManagerPro`:
  - **Windows:** Windows Credential Manager / Locker (respaldado por DPAPI vinculado a la cuenta del usuario).
  - **macOS:** Keychain.
  - **Linux:** Secret Service (GNOME Keyring / KWallet vía D-Bus).
- **Índice local ciego (`secrets_index.json`):** Dado que `keyring` no provee una API estándar para enumerar claves en todos los backends, la aplicación mantiene un archivo JSON local que registra **únicamente los nombres** de los secretos (nunca sus valores ni metadatos sensibles).

### 2. CLI *Agent-Safe* (`keyring_secrets_cli.py`)
Diseñada específicamente para automatización, scripts y agentes de IA:
- **Ingesta por tubería (`--stdin`):** Permite pasar secretos por entrada estándar sin exponerlos en la línea de comandos ni en el historial del shell (`PSReadLine` / `bash_history`).
- **Salida determinista (`--json`):** Respuestas estructuradas `{ "success": bool, "data": ..., "error": ... }` ideales para parseo programático.
- **Inspección sin exposición (`--no-reveal`):** En `inspect` y en `get` (que por defecto oculta el valor salvo que se pase `--reveal`), permite verificar existencia, metadatos o longitud del secreto sin imprimir su contenido en consola o logs.

### 3. Respaldos Cifrados Portables (`.evb` y `.ksb`)
Cuando necesitas migrar tu entorno de trabajo o respaldar tus secretos fuera de la máquina local, **EnvVar Manager Pro** genera contenedores binarios cifrados con un esquema transparente y verificable (`src/core/crypto.py` y `src/core/keyring_backup_service.py`):

```text
+----------------+----------------+------------------+------------------------+
| MAGIC (4 bytes)| VERSION (1 b)  | SALT (16 bytes)  | Token Fernet (resto)   |
| "EVMB" / "KSMB"|     0x01       | os.urandom(16)   | AES-128-CBC + HMAC-256 |
+----------------+----------------+------------------+------------------------+
```

- **Derivación de clave:** `PBKDF2-HMAC-SHA256` con **480.000 iteraciones** (alineado con recomendaciones OWASP) y **sal aleatoria de 16 bytes** por cada respaldo. La contraseña maestra nunca se almacena en disco.
- **Cifrado e integridad autenticada:** `Fernet` (`AES-128-CBC` con padding PKCS7 + `HMAC-SHA256` de 32 bytes), garantizando confidencialidad y detección inmediata de manipulación o contraseña incorrecta (`InvalidPasswordError` / `CorruptedBackupError`).
- **Previsualización previa:** Tanto la CLI (`inspect`) como las interfaces gráficas permiten descifrar en memoria e inspeccionar el contenido del respaldo antes de sobrescribir variables o secretos locales.

### 4. Propagación de Variables de Entorno en Windows (`WM_SETTINGCHANGE`)
Al crear, editar o eliminar variables persistentes en el Registro de Windows (`HKCU\Environment` o `HKLM\...\Environment`), `EnvService` invoca `ctypes.windll.user32.SendMessageTimeoutW` con `HWND_BROADCAST` (`0xFFFF`) y `WM_SETTINGCHANGE` (`0x1A`, timeout de 5 segundos).  
> **Nota técnica honesta:** Esta señal actualiza el bloque de entorno de Windows Explorer y de las **nuevas** aplicaciones o terminales que abras después del cambio; las consolas que ya estaban abiertas antes de la edición conservan su bloque heredado hasta que se reinicien.

### 5. SDK Desacoplado (`envvar_manager_client.py`)
Tus scripts y aplicaciones Python pueden consumir secretos sin depender de la GUI ni de archivos `.env`:
- `get_secret(nombre, fallback_env=False)`: Obtiene el secreto desde `EnvVarManagerPro` o lanza `SecretoNoEncontradoError` / `KeyringNoDisponibleError`.
- `get_secret_safe(nombre, default=None, fallback_env=True)`: Lectura tolerante a fallos con retorno controlado (`default` o `os.getenv`).
- `listar_secretos()`: Consulta el índice local de nombres disponibles.

### 6. Dos Interfaces Gráficas Complementarias
- **Suite Completa (`run.py` / `src/gui/app.py`):** Construida con `customtkinter` para gestionar variables de entorno (Usuario, Sistema, Sesión), secretos y respaldos `.evb`.
- **Gestor Dedicado de Secretos (`keyring_secrets_gui.py`):** Construida en `tkinter`/`ttk` bajo el estilo **Corporate Light UI** (paleta clara de alto contraste, tipografía entera y estilos `Secrets.Treeview`), enfocada en operaciones CRUD rápidas sobre `keyring` y respaldos `.ksb`.

---

## 🏗️ Arquitectura del Proyecto

```text
env_var_manager_public/
├── src/
│   ├── __init__.py                   # Versión del paquete (1.2.0)
│   ├── main.py                       # Punto de entrada de la suite completa
│   ├── core/
│   │   ├── env_service.py            # CRUD de variables de entorno + WM_SETTINGCHANGE
│   │   ├── secrets_service.py        # CRUD de secretos sobre keyring + índice ciego
│   │   ├── crypto.py                 # PBKDF2-HMAC-SHA256 (480k) + Fernet
│   │   ├── backup_service.py         # Respaldos cifrados de variables (.evb)
│   │   ├── keyring_backup_service.py # Respaldos cifrados de secretos (.ksb)
│   │   ├── models.py                 # Modelos de dominio (Scope, EnvVar, etc.)
│   │   └── exceptions.py             # Jerarquía de excepciones del dominio
│   ├── gui/                          # Interfaz principal en CustomTkinter
│   └── utils/                        # Validadores y configuración de logging
├── examples/                         # Ejemplos de consumo del SDK
├── tests/                            # Suite de pruebas unitarias e integración (pytest)
├── envvar_manager_client.py          # SDK cliente desacoplado
├── keyring_secrets_cli.py            # CLI determinista (--json, --stdin)
├── keyring_secrets_gui.py            # GUI dedicada en Tkinter/ttk (Corporate Light UI)
├── run.py                            # Lanzador directo de la suite GUI
├── pyproject.toml                    # Empaquetado PEP 517/621 y entry points
├── requirements.txt                  # Dependencias de ejecución
└── CHANGELOG.md                      # Historial de cambios
```

---

## 📦 Instalación

### Requisitos
- **Python 3.9 o superior** (verificado en Python 3.12).
- **Sistema operativo:** Windows 10/11, macOS o Linux (con backend de Secret Service activo).

### Instalación desde el repositorio

```bash
git clone https://github.com/FranciscoGrandon/env-var-manager-pro.git
cd env-var-manager-pro
```

**Opción A — Instalación editable con entry points (recomendada):**
```bash
pip install -e .
```
Esto registra automáticamente los comandos globales:
- `envvar-manager` (Suite completa GUI)
- `keyring-secrets` (CLI de secretos)
- `keyring-secrets-gui` (GUI dedicada de secretos)

**Opción B — Instalación de dependencias directa:**
```bash
pip install -r requirements.txt
```

---

## 🚀 Guía Rápida de Uso

### 1. CLI de Secretos (`keyring_secrets_cli.py`)

```bash
# Verificar backend activo del sistema operativo
python keyring_secrets_cli.py backend --json

# Guardar un secreto usando tubería (--stdin) para no dejar rastro en el historial del shell
# PowerShell:
"mi_token_super_secreto" | python keyring_secrets_cli.py set GITHUB_TOKEN --stdin --force --json
# Bash / Zsh:
printf '%s' "mi_token_super_secreto" | python keyring_secrets_cli.py set GITHUB_TOKEN --stdin --force --json

# Verificar existencia sin revelar el valor
python keyring_secrets_cli.py exists GITHUB_TOKEN --json
python keyring_secrets_cli.py get GITHUB_TOKEN --json

# Obtener el valor explícitamente cuando un script lo necesite
python keyring_secrets_cli.py get GITHUB_TOKEN --reveal --json

# Respaldar secretos en archivo cifrado .ksb e inspeccionar sin revelar valores
python keyring_secrets_cli.py backup ./respaldo.ksb -p "ClaveMaestraFuerte!2026" --json
python keyring_secrets_cli.py inspect ./respaldo.ksb -p "ClaveMaestraFuerte!2026" --no-reveal --json
```

### 2. SDK en Python (`envvar_manager_client.py`)

```python
from envvar_manager_client import get_secret, get_secret_safe, listar_secretos

# Lectura estricta (lanza SecretoNoEncontradoError si no existe)
github_token = get_secret("GITHUB_TOKEN")

# Lectura tolerante con fallback a os.getenv() o valor por defecto
api_key = get_secret_safe("OPENAI_API_KEY", default="", fallback_env=True)

# Listar nombres registrados en el índice local
nombres = listar_secretos()
```

Más ejemplos prácticos disponibles en [`examples/`](examples/README.md).

### 3. Interfaces Gráficas (GUI)

```bash
# Suite completa (Variables de Entorno + Secretos + Respaldos .evb)
python run.py

# Gestor dedicado de Secretos Keyring (Tkinter/ttk Corporate Light UI)
python keyring_secrets_gui.py
```

---

## 🤖 Integración Automática en Flujos de IA y Equipos (Directiva Global y Agent Skill)

Para que tus asistentes de IA (Antigravity, Claude Code, Cursor, Gemini CLI, Codex, etc.) utilicen **EnvVar Manager Pro** de forma automática y nunca escriban credenciales en texto plano, puedes configurar una regla global o una Agent Skill reutilizable.

### Opción A — Directiva Global / Regla de Proyecto

Copia y pega este bloque en tu archivo de instrucciones (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md` o `.cursorrules`):

```markdown
## Gestión Obligatoria de Secretos y Credenciales (Keyring)

- **Prohibición de texto plano:** Queda estrictamente prohibido almacenar tokens, API keys, contraseñas o secretos en archivos `.env`, JSON/YAML, scripts o código fuente.
- **CLI obligatorio (`keyring-secrets` / `python keyring_secrets_cli.py`):**
  - Usa siempre `--json` para obtener salidas estructuradas y deterministas.
  - Usa `--stdin` en `set` y `update` para inyectar secretos por tubería sin dejar rastro en el historial ni en los argumentos del proceso.
  - Usa `--no-reveal` en `get` (o el comando `exists`) cuando solo necesites verificar disponibilidad o metadatos sin exponer el valor en logs.
- **SDK en Python:** En aplicaciones y scripts Python, lee credenciales exclusivamente mediante `envvar_manager_client.get_secret("<NOMBRE>")` (o `get_secret_safe("<NOMBRE>")`), nunca desde literales ni archivos `.env`.
```

### Opción B — Plantilla de Agent Skill (`SKILL.md`)

Guarda esta plantilla en `~/.gemini/skills/keyring-secrets/SKILL.md` (o en `.agent/skills/keyring-secrets/SKILL.md` / `.claude/skills/keyring-secrets/SKILL.md` según tu herramienta):

````markdown
---
name: keyring-secrets
description: Gestiona y consume credenciales, tokens de API y contraseñas de forma segura mediante el almacén nativo del sistema operativo (Keyring) con EnvVar Manager Pro. Activar siempre que se requiera leer, guardar, actualizar, verificar o respaldar secretos sin escribir archivos .env ni exponer valores en texto plano.
---

# Gestión Segura de Secretos con EnvVar Manager Pro

## Reglas Críticas
1. Nunca almacenes secretos en `.env`, JSON, YAML o código fuente.
2. Nunca muestres ni registres valores de secretos en logs o respuestas.
3. Usa `--json` en todas las llamadas al CLI y `--stdin` al guardar o actualizar valores.

## Comandos CLI (`keyring-secrets` o `python keyring_secrets_cli.py`)

```bash
# Verificar si existe un secreto o inspeccionar metadatos sin exponer el valor
keyring-secrets exists NOMBRE_SECRETO --json
keyring-secrets get NOMBRE_SECRETO --no-reveal --json

# Guardar o actualizar un secreto de forma segura vía stdin
printf '%s' "$VALOR" | keyring-secrets set NOMBRE_SECRETO --stdin --force --json
printf '%s' "$NUEVO_VALOR" | keyring-secrets update NOMBRE_SECRETO --stdin --json

# Listar nombres registrados y verificar backend activo
keyring-secrets list --json
keyring-secrets backend --json
```

## Uso en Scripts Python (`envvar_manager_client.py`)

```python
from envvar_manager_client import get_secret, get_secret_safe

token = get_secret("GITHUB_TOKEN")
api_key = get_secret_safe("OPENAI_API_KEY", default="", fallback_env=False)
```
````

---

## 🧪 Ejecución de Tests

Instala `pytest` (o `pip install -e ".[test]"`) y ejecuta la suite completa:

```bash
pytest -v
```

Los tests en `tests/` validan de forma aislada el servicio de entorno, el cifrado `PBKDF2` + `Fernet`, la integridad de respaldos `.evb` / `.ksb` (incluyendo detección de contraseña incorrecta y corrupción de bytes) y todos los comandos de `keyring_secrets_cli.py`.

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulta [LICENSE](LICENSE) para más detalles.

Reporta errores o sugerencias en: [https://github.com/FranciscoGrandon/env-var-manager-pro/issues](https://github.com/FranciscoGrandon/env-var-manager-pro/issues)
