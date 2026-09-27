# Configuración (variables de entorno)

Todas las variables se pueden definir exportándolas manualmente, o copiando
`.env.example` a `.env` en el directorio de trabajo — `opssleuth.cli.main()`
lo carga automáticamente vía `python-dotenv` (sin sobrescribir variables ya
definidas en el entorno) antes de arrancar la conversación.

## Proveedor de modelo de chat

Leídas por [`crear_modelo_chat()`](reference/llm.md).

| Variable | Requerida cuándo | Descripción |
| --- | --- | --- |
| `OPSSLEUTH_LLM_PROVIDER` | siempre (opcional, por defecto `claude`) | `"claude"`, `"ollama"` o `"gemini"`. Cualquier otro valor lanza `ProveedorDesconocidoError`. |
| `ANTHROPIC_API_KEY` | `OPSSLEUTH_LLM_PROVIDER=claude` | Estándar del SDK de Anthropic (usada internamente por `langchain-anthropic`). También puede autenticarse con `ant auth login`. |
| `OPSSLEUTH_OLLAMA_MODEL` | `OPSSLEUTH_LLM_PROVIDER=ollama` | Nombre de un modelo ya descargado localmente (`ollama pull <modelo>`) **con soporte de tool calling** — requerido por el flujo de búsqueda de evidencia. Sin valor por defecto: su ausencia lanza `ModeloOllamaNoConfiguradoError`. |
| `GOOGLE_API_KEY` | `OPSSLEUTH_LLM_PROVIDER=gemini` | Estándar del SDK de Google (usada internamente por `langchain-google-genai`). API key de Google AI Studio, capa gratuita. |

!!! warning "Límite de cuota de la capa gratuita de Gemini"
    La API key gratuita de Google AI Studio está limitada (históricamente,
    del orden de 20 solicitudes/día para el modelo usado por defecto). Es
    fácil agotarla durante pruebas manuales prolongadas — si el proveedor
    empieza a fallar sin motivo aparente, verifica primero si la respuesta
    trae un código `429` antes de asumir un error de código.

El modelo concreto de Claude/Gemini está fijado en código
(`MODELO_CLAUDE_POR_DEFECTO = "claude-sonnet-5"`,
`MODELO_GEMINI_POR_DEFECTO = "gemini-3.6-flash"`) — no configurable por
variable de entorno, para no introducir una superficie de configuración sin
una necesidad concreta (Principio IV).

## Base de datos (opcional)

Leídas por [`crear_motor_bd()`](reference/database.md). Si `OPSSLEUTH_DB_URL`
no está definida, esta fuente de evidencia simplemente no está disponible —
**no es un error**; la conversación continúa solo con recepción de
incidencias y (si se aporta) evidencia de logs.

| Variable | Requerida cuándo | Descripción |
| --- | --- | --- |
| `OPSSLEUTH_DB_URL` | para habilitar esta fuente | Cadena de conexión de SQLAlchemy (p. ej. `postgresql://usuario:password@host/bd`, `sqlite:///ruta/archivo.db`). |
| `OPSSLEUTH_DB_TABLAS_PERMITIDAS` | si `OPSSLEUTH_DB_URL` está definida | Lista de tablas separadas por comas a las que el agente puede acceder. **Sin valor por defecto equivalente a "todas las tablas"** — su ausencia (o que ninguna de las tablas listadas exista realmente) lanza `TablasPermitidasNoConfiguradasError`, un error de configuración que se deja propagar deliberadamente (fallo seguro). |
| `OPSSLEUTH_DB_TIMEOUT_SEGUNDOS` | opcional | Tiempo de espera por consulta, en segundos (por defecto `10`). Mejor esfuerzo — depende de si el DBAPI del dialecto lo soporta. |

Si la base de datos está configurada pero no es accesible en el momento de
construir la conexión (credenciales inválidas, host inaccesible), la CLI
captura `ConexionBaseDeDatosError`, informa al usuario y continúa el resto de
la conversación sin esa fuente — nunca interrumpe el arranque.

### La barandilla de seguridad de las consultas

Toda consulta que el agente propone pasa por
[`validar_consulta()`](reference/database.md) (`opssleuth.database.validacion`)
**antes** de tocar la base de datos real. Dos condiciones, ambas
obligatorias:

1. Debe parsear como una **única sentencia `SELECT`** (se rechaza cualquier
   texto con más de una sentencia, o cuya raíz no sea `SELECT` —
   `INSERT`/`UPDATE`/`DELETE`/`DROP`/etc., o texto que no es SQL válido).
2. Toda tabla referenciada (excluidos los alias de CTE) debe estar dentro de
   `OPSSLEUTH_DB_TABLAS_PERMITIDAS`.

El motivo de rechazo que se le muestra al agente es siempre genérico — nunca
revela qué tabla concreta causó el rechazo ni detalles del esquema. Además,
`ejecutar_consulta_sql` abre una conexión de solo lectura cuando el dialecto
lo soporta (`SET TRANSACTION READ ONLY`, mejor esfuerzo) y nunca hace
`commit()`.

## Resumen de todas las variables

```sh
# --- Proveedor de modelo (elegir uno) ---
OPSSLEUTH_LLM_PROVIDER=claude            # claude | ollama | gemini
ANTHROPIC_API_KEY=
OPSSLEUTH_OLLAMA_MODEL=
GOOGLE_API_KEY=

# --- Base de datos (opcional) ---
OPSSLEUTH_DB_URL=
OPSSLEUTH_DB_TABLAS_PERMITIDAS=
OPSSLEUTH_DB_TIMEOUT_SEGUNDOS=10
```
