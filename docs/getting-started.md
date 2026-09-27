# Primeros pasos

## Requisitos

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) para gestionar dependencias y entornos.
- Un proveedor de modelo de chat configurado (elige uno): Claude (Anthropic),
  Gemini (Google AI Studio, capa gratuita) u Ollama corriendo localmente.

## Instalación

```sh
uv sync
```

Esto instala las dependencias del proyecto (`langchain`, `langgraph`,
`sqlalchemy`, `sqlglot`, `rich`, etc. — ver [Arquitectura](architecture.md)
para qué hace cada una) en un entorno virtual gestionado por `uv`.

## Configurar un proveedor de modelo

OpsSleuth nunca acopla la lógica de negocio a un SDK de proveedor concreto:
todo pasa por [`crear_modelo_chat()`](reference/llm.md), que lee la variable
de entorno `OPSSLEUTH_LLM_PROVIDER` y construye un `BaseChatModel` de
LangChain. Copia `.env.example` a `.env` y completa uno de estos tres bloques
(se carga automáticamente al arrancar la CLI, vía `python-dotenv`):

=== "Claude (por defecto)"

    ```sh
    OPSSLEUTH_LLM_PROVIDER=claude
    ANTHROPIC_API_KEY=sk-ant-...
    ```

    Modelo fijo: `claude-sonnet-5`. También funciona con `ant auth login` en
    vez de una API key explícita.

=== "Gemini (capa gratuita)"

    ```sh
    OPSSLEUTH_LLM_PROVIDER=gemini
    GOOGLE_API_KEY=...
    ```

    Modelo fijo: `gemini-3.6-flash` (Google AI Studio, capa gratuita — con
    soporte de tool calling y salida estructurada, requerido por ambos
    flujos). Ver la nota sobre límites de cuota diarios en
    [Configuración](configuration.md).

=== "Ollama (modelo local)"

    ```sh
    OPSSLEUTH_LLM_PROVIDER=ollama
    OPSSLEUTH_OLLAMA_MODEL=qwen2.5:7b-instruct
    ```

    El modelo debe estar ya descargado (`ollama pull <modelo>`) **y** soportar
    tool calling — no todo modelo local sirve para el flujo de búsqueda de
    evidencia (que enlaza herramientas), aunque sí sirva para la recepción de
    incidencias (que no las usa).

## Ejecutar la CLI

```sh
uv run python -m opssleuth.cli
```

Verás el banner de bienvenida y podrás describir el problema en lenguaje
natural. A partir de ahí, la conversación sigue el flujo descrito en
[Inicio](index.md#que-hace-hoy):

```text
OpsSleuth:
Antes de continuar, cuéntame: ¿qué problema o error encontraste, o qué te reportaron?
Tú: El servicio de facturación empezó a fallar hace una hora con errores 500
OpsSleuth:
Gracias, recibí tu descripción del problema.
...
```

## (Opcional) Consulta a base de datos

Si además quieres que el agente correlacione el incidente con el estado real
de los datos, configura una conexión de solo lectura:

```sh
OPSSLEUTH_DB_URL=postgresql://usuario:password@host/basededatos
OPSSLEUTH_DB_TABLAS_PERMITIDAS=facturas,pagos,usuarios
```

Ver [Configuración](configuration.md) para el detalle de esta barandilla de
seguridad (nunca hay un valor por defecto equivalente a "todas las tablas").

## Ejecutar las pruebas

```sh
uv run pytest tests/
```

Ver [Pruebas y calidad](testing.md).

## Servir esta documentación en local

Este sitio se genera con [MkDocs](https://www.mkdocs.org/) +
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) +
[mkdocstrings](https://mkdocstrings.github.io/) (que extrae la referencia de
código directamente de los docstrings numpydoc del proyecto — ver
`.specify/memory/constitution.md`, Principio III).

```sh
uv sync --group docs
uv run mkdocs serve
```

Y abre `http://127.0.0.1:8000/`. Para generar el sitio estático:

```sh
uv run mkdocs build
```
