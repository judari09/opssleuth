# OpsSleuth

<p align="center">
  <img src="docs/assets/banner.svg" alt="OpsSleuth — diagnóstico asistido por IA para sistemas críticos" width="100%">
</p>

<p align="center">
  <a href="#instalación"><img alt="Python 3.13+" src="https://img.shields.io/badge/python-3.13%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="#instalación"><img alt="uv" src="https://img.shields.io/badge/gestionado%20con-uv-de5fe9"></a>
  <a href="#pruebas"><img alt="pytest" src="https://img.shields.io/badge/tests-167%20passed-4ade80?logo=pytest&logoColor=white"></a>
  <a href="#el-agente-de-investigación-langgraph"><img alt="LangGraph" src="https://img.shields.io/badge/agente-LangGraph-c084fc"></a>
  <a href="#documentación-completa"><img alt="MkDocs" src="https://img.shields.io/badge/docs-MkDocs%20Material-22d3ee"></a>
</p>

**OpsSleuth** es una herramienta de diagnóstico para sistemas críticos: reduce
el tiempo de investigación de errores conversando con quien reporta la
incidencia, formulando solo las preguntas que realmente faltan para
completar el contexto, y luego saliendo a **buscar evidencia real por su
cuenta** — en archivos de logs y en bases de datos — en vez de quedarse con
lo que la persona recuerda de memoria.

No es un chatbot que "adivina" causas: cada apreciación que produce está
anclada a evidencia que un agente de [LangGraph](https://langchain-ai.github.io/langgraph/)
efectivamente leyó con sus herramientas. Si no encuentra nada relacionado con
el incidente, lo dice explícitamente en vez de fabricar una conclusión.

📖 **[Documentación completa](#documentación-completa)** con la arquitectura a
fondo, el diagrama del grafo del agente y la referencia de código generada
desde los docstrings.

---

## Qué hace

Cada caso (una incidencia en investigación) pasa por hasta tres fases, la
primera obligatoria y las otras dos activadas automáticamente cuando hay una
fuente disponible:

1. **Recepción de la incidencia** — captura la descripción libre del
   problema, identifica si falta el *sistema afectado*, el *síntoma* o el
   *momento* en que ocurrió, y pregunta solo lo que falta (una por una, o
   todo junto en un solo mensaje si prefieres). Detecta contradicciones con
   lo ya dicho sin descartar ningún dato, y confirma contigo si parece que
   describes más de un problema a la vez.
2. **Búsqueda de evidencia en logs** — en cuanto la descripción queda
   completa, te invita a aportar una ruta de archivo o a pegar contenido
   directamente en el chat. Un agente localiza las entradas relacionadas con
   el incidente (aislando por horario cuando lo conoces) **sin cargar el
   archivo completo** en el contexto del modelo, y consolida lo encontrado en
   una única apreciación — acotada si hay muchas coincidencias.
3. **Consulta a bases de datos** — si hay una base de datos configurada, un
   segundo agente inspecciona el esquema (sin adivinar nombres de columna) y
   construye consultas `SELECT` de solo lectura — incluso con cruces entre
   más de dos tablas — para correlacionar el incidente con el estado real de
   los datos. Toda consulta pasa antes por una barandilla de seguridad que la
   rechaza si no es una única sentencia `SELECT` sobre tablas explícitamente
   permitidas.

```text
OpsSleuth:
Antes de continuar, cuéntame: ¿qué problema o error encontraste, o qué te reportaron?
Tú: El servicio de facturación empezó a fallar hace una hora con errores 500
OpsSleuth:
Gracias, recibí tu descripción del problema.
OpsSleuth:
Ya tengo clara la descripción, ¿puedes aportar los logs relacionados?
Tú: /var/log/facturacion.log
OpsSleuth:
Fuente de logs registrada: /var/log/facturacion.log
OpsSleuth:
Encontré 2 entradas ERROR alrededor de las 14:15: un timeout al conectar con
la base de datos y un fallo con código 500 en la creación de una factura,
consistentes con el síntoma reportado.
```

## El agente de investigación (LangGraph)

Los dos motores de búsqueda de evidencia (logs y base de datos) no
implementan cada uno su propio bucle de decisión: ambos construyen **el mismo
grafo** vía `langchain.agents.create_agent` (el patrón ReAct: razonar → actuar
→ observar), parametrizado con un `BaseChatModel` inyectado, un conjunto de
herramientas propio, y un prompt de sistema con el contexto del incidente.

<p align="center">
  <img src="docs/assets/agent-graph.svg" alt="Grafo del agente: START, agent, tools, END, con las herramientas de logs y de base de datos" width="100%">
</p>

El agente decide en cada paso si necesita invocar una herramienta (buscar un
patrón, leer contexto alrededor de una línea, ejecutar una consulta SQL) o si
ya tiene evidencia suficiente para concluir — acotado a un máximo de
iteraciones para nunca quedarse dando vueltas indefinidamente sobre una
fuente sin evidencia útil. Las entradas que finalmente se muestran al usuario
se extraen **siempre** de los resultados reales de esas herramientas, nunca
del texto libre que el modelo redacta — ver el detalle completo en
[`docs/agent-workflow.md`](docs/agent-workflow.md).

## Arquitectura en breve

```text
src/opssleuth/
├── domain/            entidades puras (Caso, FuenteDeLogs, FuenteDeBaseDeDatos...)
├── clarification/      motor de aclaración de la recepción de incidencias
├── evidence/           búsqueda de evidencia en logs (tools + agent + engine)
├── database/           consulta a bases de datos (factory + validación + tools + agent + engine)
├── llm/                 crear_modelo_chat(): único punto que importa un SDK de proveedor
├── presentation/         único módulo que importa `rich` (etiquetas de rol, Markdown, banner)
└── cli.py               bucle conversacional que orquesta todo lo anterior
```

El proyecto se rige por cuatro principios no negociables (ver
`.specify/memory/constitution.md`): **cumplimiento SOLID**, **arquitectura
modular y reemplazable** detrás de contratos explícitos (el mecanismo de
intercambiabilidad de proveedor de modelo es `BaseChatModel` de LangChain —
nunca se importa `langchain_anthropic`/`langchain_ollama`/`langchain_google_genai`
fuera de `llm/factory.py`), **docstrings numpydoc obligatorios** en todo el
código (la fuente de esta misma documentación), y **simplicidad ante todo**
(sin abstracciones ni configuración que no resuelvan una necesidad concreta y
presente). Ver [`docs/architecture.md`](docs/architecture.md) para el
detalle.

## Instalación

Requiere Python 3.13+ y [`uv`](https://docs.astral.sh/uv/):

```sh
uv sync
```

## Configuración

Copia `.env.example` a `.env` y elige un proveedor de modelo:

```sh
# Claude (por defecto)
OPSSLEUTH_LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

# — o Gemini (capa gratuita de Google AI Studio) —
OPSSLEUTH_LLM_PROVIDER=gemini
GOOGLE_API_KEY=...

# — o un modelo local con Ollama (debe soportar tool calling) —
OPSSLEUTH_LLM_PROVIDER=ollama
OPSSLEUTH_OLLAMA_MODEL=qwen2.5:7b-instruct
```

Opcionalmente, habilita la consulta a base de datos:

```sh
OPSSLEUTH_DB_URL=postgresql://usuario:password@host/basededatos
OPSSLEUTH_DB_TABLAS_PERMITIDAS=facturas,pagos,usuarios
```

`OPSSLEUTH_DB_TABLAS_PERMITIDAS` no tiene un valor por defecto equivalente a
"todas las tablas" — es un fallo seguro deliberado. Ver
[`docs/configuration.md`](docs/configuration.md) para el resto de variables y
el detalle de la barandilla de seguridad de las consultas.

## Uso

```sh
uv run python -m opssleuth.cli
```

## Pruebas

```sh
uv run pytest tests/
```

167 pruebas, sin depender de credenciales de ningún proveedor real: los
`BaseChatModel`/`Engine` se sustituyen por dobles de prueba inyectados
directamente. Ver [`docs/testing.md`](docs/testing.md).

## Documentación completa

Este README es el punto de entrada rápido. La documentación completa del
proyecto —arquitectura a fondo, el flujo del agente explicado paso a paso,
todas las variables de configuración, y la referencia de código generada
automáticamente a partir de los docstrings numpydoc— vive en `docs/` y se
sirve con [MkDocs](https://www.mkdocs.org/) +
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) +
[mkdocstrings](https://mkdocstrings.github.io/):

```sh
uv sync --group docs
uv run mkdocs serve   # http://127.0.0.1:8000/
```

| Página | Contenido |
| --- | --- |
| [`docs/index.md`](docs/index.md) | Punto de entrada de la documentación completa. |
| [`docs/getting-started.md`](docs/getting-started.md) | Instalación, configuración de proveedor, ejecución paso a paso. |
| [`docs/architecture.md`](docs/architecture.md) | Módulos, entidades de dominio, y cómo se aplica cada principio de la constitución. |
| [`docs/agent-workflow.md`](docs/agent-workflow.md) | El grafo de LangGraph explicado nodo por nodo, con las herramientas de cada agente. |
| [`docs/configuration.md`](docs/configuration.md) | Todas las variables de entorno y la barandilla de seguridad de las consultas SQL. |
| [`docs/testing.md`](docs/testing.md) | Qué cubre cada archivo de pruebas y cómo se prueban los flujos con LLM sin un proveedor real. |
| [`docs/reference/`](docs/reference/index.md) | Referencia de código por paquete (`domain`, `clarification`, `evidence`, `database`, `llm`, `presentation`, `cli`). |
| [`docs/roadmap.md`](docs/roadmap.md) | Registro de specs implementadas y qué queda deliberadamente fuera de alcance. |

## Desarrollo guiado por specs

Este repositorio usa [Spec Kit](https://github.com/github/spec-kit)
(`.specify/`, integrado como skills de Claude Code) para toda funcionalidad
nueva: `spec.md` → `plan.md` → `tasks.md` → implementación, bajo
`specs/[###-nombre-feature]/`. `specs/ESTADO_SPECS.md` es el registro central
de decisiones arquitectónicas y contratos compartidos — se consulta antes de
plantear cualquier spec nueva, para no contradecir algo que una spec anterior
ya estableció. Ver [`docs/roadmap.md`](docs/roadmap.md) para el resumen de
qué se ha implementado hasta ahora.
