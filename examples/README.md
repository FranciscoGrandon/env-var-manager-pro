# Ejemplos: Cómo usar secretos de EnvVar Manager Pro en tus aplicaciones

Estos ejemplos muestran patrones prácticos y seguros para leer secretos (tokens, claves API, contraseñas) desde EnvVar Manager Pro en tus aplicaciones Python.

## 0️⃣ Antes de ejecutar los ejemplos

```bash
pip install keyring
```

Luego, abre **EnvVar Manager Pro → Secretos → Nuevo secreto** y guarda algunos tokens de prueba:
- `GITHUB_TOKEN` = tu token de GitHub (o uno falso para probar)
- `OPENAI_API_KEY` = tu API key de OpenAI (o uno falso)

Cada script detectará automáticamente qué secretos existen y adaptará el comportamiento.

---

## 📖 Ejemplos

### 1️⃣ `01_basico.py` — Lo más simple

**Objetivo:** Aprender las tres formas de leer secretos.

```bash
python examples/01_basico.py
```

**Patrón 1 — `get_secret()` — Fallar si no existe:**
```python
from envvar_manager_client import get_secret, SecretoNoEncontradoError

try:
    token = get_secret("GITHUB_TOKEN")
except SecretoNoEncontradoError:
    print("Token no encontrado")
```

**Patrón 2 — `get_secret_safe()` — Valor por defecto:**
```python
from envvar_manager_client import get_secret_safe

api_key = get_secret_safe("OPENAI_API_KEY", default="sk-dev-local")
```

**Patrón 3 — Cascada: keyring → env → default:**
```python
import os
from envvar_manager_client import get_secret_safe

token = get_secret_safe("API_TOKEN") or os.getenv("API_TOKEN") or "default"
```

**Cuándo usar cada uno:**
- `get_secret()` — Token es **crítico**, la app no funciona sin él.
- `get_secret_safe()` — Token es **opcional**, hay fallback sensato.
- Cascada — **Flexibilidad**: keyring para prod, variables de entorno para dev local.

---

### 2️⃣ `02_cliente_http.py` — Clientes HTTP reales

**Objetivo:** Ver cómo inicializar clientes HTTP (GitHub, OpenAI) con secretos de forma segura.

```bash
python examples/02_cliente_http.py
```

Muestra:
- Clase `GitHubClient` que lee `GITHUB_TOKEN` al inicializarse
- Clase `OpenAIClient` que lee `OPENAI_API_KEY` al inicializarse
- Cómo inyectar tokens en headers sin exponerlos

**Aplicable a:**
- Scripts que consultan APIs externas
- Bots que necesitan múltiples tokens
- Herramientas que integran varios servicios

---

### 3️⃣ `03_config_app.py` — Configuración centralizada

**Objetivo:** Patrón profesional que distingue **secretos** (tokens) de **configuración** (flags, rutas).

```bash
python examples/03_config_app.py
```

```python
@dataclass
class Configuracion:
    # Secretos (desde keyring)
    github_token: str | None
    openai_api_key: str | None
    database_password: str | None
    
    # Variables de entorno (no sensibles)
    debug: bool
    log_level: str
    data_dir: str
    
    @staticmethod
    def cargar() -> "Configuracion":
        # Secretos de keyring, variables de env normales
        ...
    
    def validar(self) -> bool:
        # Verificar que secretos críticos existan
        ...
```

**Ventajas:**
- Separación clara de responsabilidades
- Fácil de testear (inyectable)
- Validación automática al iniciar
- Escalable a cientos de parámetros

**Aplicable a:**
- Toda aplicación seria
- FG Agente Telegram (refactorizar INDUCCION_PRO)
- Servicios backend
- Herramientas con múltiples modos de operación

---

### 4️⃣ `04_decoradores.py` — Validación automática

**Objetivo:** Decorator `@requiere_secretos()` que valida dependencias antes de ejecutar.

```bash
python examples/04_decoradores.py
```

```python
@requiere_secretos("GITHUB_TOKEN", "OPENAI_API_KEY")
def generar_documentacion_con_ai():
    """Solo se ejecuta si ambos tokens existen."""
    ...
```

**Ventajas:**
- Declarativo: la función dice qué secretos necesita
- Validación automática (no hay que escribir `if not token:`)
- Mensajes de error claros
- Reutilizable

**Aplicable a:**
- Funciones de tu FG Agente
- Tareas Celery o rq
- Scripts de cron
- Tests que requieren autenticación

---

## 🎯 Recomendación por caso de uso

| Caso | Ejemplo recomendado | Por qué |
|---|---|---|
| Script rápido, un secreto | `01_basico.py` Patrón 1 | Simple, directo |
| Desarrollo local vs. producción | `01_basico.py` Patrón 3 | Cascada flexible |
| Tu FG Agente Telegram | `03_config_app.py` + `04_decoradores.py` | Profesional, escalable |
| Cliente HTTP multi-servicio | `02_cliente_http.py` | Patrón de inicialización claro |
| Función/tarea crítica | `04_decoradores.py` | Validación automática |

---

## ✅ Checklist de seguridad

Antes de deployar tu aplicación:

- [ ] No hay secretos hardcodeados en el código (`grep -r "sk-" src/`, `grep -r "token=" src/`)
- [ ] El `.env` (si lo usas) está en `.gitignore`
- [ ] La app no falla silenciosamente si falta un secreto crítico (usa `get_secret()` o decorator)
- [ ] Los secretos se leen en tiempo de ejecución, no en time de módulo
- [ ] En producción, usas el secret manager del proveedor (AWS Secrets Manager, etc.)

---

## 🔗 Importar el cliente en tu código

Opción A — Copiar el archivo:
```bash
cp envvar_manager_client.py /path/to/tu/proyecto/
```

```python
from envvar_manager_client import get_secret, get_secret_safe
```

Opción B — Clonar el repo o agregar como submodule:
```bash
git submodule add https://github.com/tuuser/env_var_manager my_external_env
```

```python
from my_external_env.envvar_manager_client import get_secret
```

Opción C — Instalar como paquete (si publicas a PyPI):
```bash
pip install envvar-manager-client
```

```python
from envvar_manager_client import get_secret
```

---

## 🚨 Troubleshooting

**Error: `KeyringNoDisponibleError: No se pudo acceder al almacén...`**

En Linux sin sesión gráfica:
```bash
# Instala Secret Service (GNOME Keyring)
sudo apt-get install gnome-keyring

# O instala KWallet (KDE)
sudo apt-get install kwalletmanager
```

**El secreto que guardé en EnvVar Manager Pro no aparece en `get_secret()`**

Verifica:
1. Abre EnvVar Manager Pro → Secretos → lista que aparezcan los secretos
2. Ejecuta `python envvar_manager_client.py` para testear la conexión
3. En Windows, revisa Credential Manager (búsqueda: "credential manager" en Inicio)

---

## 📚 Referencias

- [keyring documentation](https://keyring.readthedocs.io/)
- [OWASP: Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [12 Factor App: Config](https://12factor.net/config)
