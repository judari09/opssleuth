# Estado de las Specs — OpsSleuth

Registro central de todas las especificaciones (specs) del proyecto, generadas vía
el flujo Spec Kit (`/speckit-specify`, `/speckit-plan`, `/speckit-tasks`,
`/speckit-implement`).

**Este archivo DEBE revisarse antes de crear o planear una nueva spec.** Su
propósito es evitar *spec drift*: decisiones arquitectónicas contradictorias
entre specs, entidades o contratos duplicados, o cambios que rompan sin darse
cuenta una funcionalidad ya implementada por otra spec.

## Cómo usar este archivo

- **Antes de `/speckit-specify` de una nueva feature**: leer la tabla de specs
  existentes y la sección "Decisiones y contratos compartidos" para saber qué ya
  existe, qué se puede reutilizar, y qué restricciones ya establecidas aplican.
- **Antes de `/speckit-plan`**: verificar que las decisiones técnicas nuevas no
  contradigan las ya registradas aquí sin justificación explícita (si contradicen
  algo, documentarlo en "Notas de spec drift a vigilar" y resolverlo antes de
  continuar).
- **Al completar cada fase** (specify/clarify/plan/tasks/implement) de una spec:
  actualizar su fila en la tabla de registro.
- **Al introducir un contrato, entidad de dominio, variable de entorno o decisión
  arquitectónica que otras specs futuras deban conocer**: añadirla a "Decisiones y
  contratos compartidos" en el mismo turno en que se implementa, no después.

## Registro de Specs

| # | Nombre | Carpeta | Estado | Rama | Última actualización | Resumen |
|---|---|---|---|---|---|---|
| 001 | Recepción de Incidencia | [`specs/001-recepcion-incidencia/`](001-recepcion-incidencia/) | ✅ Implementada (27/27 tareas, 46/46 pruebas) | `001-recepcion-incidencia` | 2026-08-31 | Primera fase del agente: al iniciar un caso, captura la descripción del problema, mantiene el contexto de la conversación, y formula preguntas de aclaración cuando falta información (sistema afectado, síntoma, momento) o se detectan contradicciones/múltiples problemas. |
| 002 | Búsqueda en Archivos de Logs | [`specs/002-busqueda-logs/`](002-busqueda-logs/) | ✅ Implementada (29/30 tareas, 72/72 pruebas — T030 pendiente: validación manual con proveedor real, ver nota en `tasks.md`) | `002-busqueda-logs` | 2026-09-07 | Segunda herramienta de investigación: una vez completada la recepción de la incidencia (001), el sistema invita a aportar evidencia de logs (ruta o texto pegado), localiza entradas relacionadas con el incidente sin cargar el archivo completo, aísla por horario si se conoce, y carga una apreciación inicial **consolidada** (acotada si hay muchas coincidencias) en el contexto del caso. **Alcance ampliado**: además del motor nuevo, migra el motor de aclaración de 001 a la arquitectura basada en LangChain/LangGraph adoptada en esta spec. |

**Estados posibles**: 📝 Draft (spec.md sin clarificar) · ❓ Clarificada · 📐
Planificada (plan.md listo) · 📋 Tareas generadas (tasks.md listo) · 🚧 En
implementación · ✅ Implementada · ⏸️ Pausada · 🗑️ Descartada

## Decisiones y contratos compartidos

Decisiones establecidas por una spec que aplican, o deben tenerse en cuenta, en
specs futuras. Toda nueva spec que toque estas áreas DEBE respetarlas o
justificar explícitamente por qué se aparta de ellas (y registrar la excepción
aquí).

### Arquitectura general

- **Stack**: Python 3.13, proyecto único (`src/opssleuth/`, `tests/unit/`),
  gestionado con `uv`. *(001, `plan.md`)*
- **Constitución**: `.specify/memory/constitution.md` (v1.1.0, enmendada por 002
  el 2026-09-03 — ver Sync Impact Report en el propio archivo) — SOLID,
  arquitectura modular y reemplazable (con la excepción de "estándar de
  abstracción de terceros maduro" añadida en v1.1.0, ver más abajo), docstrings
  numpydoc (backend) / JSDoc (frontend) obligatorios, simplicidad ante todo.
  Toda spec debe pasar el "Constitution Check" de `/speckit-plan`.

### Motor de modelo de lenguaje (LLM)

**⚠️ Arquitectura reemplazada por 002 (2026-09-03)** — el patrón original de 001
(contrato `Protocol` propio `ClarificationEngine` + adaptadores por proveedor +
`factory.py`) fue sustituido, por decisión explícita del usuario, por una
arquitectura basada en LangChain/LangGraph. La descripción siguiente es la
vigente; el patrón original queda documentado como registro histórico en
[`specs/001-recepcion-incidencia/contracts/clarification_engine.md`](001-recepcion-incidencia/contracts/clarification_engine.md)
(con nota de "superseded" en el propio archivo).

- **`BaseChatModel` (LangChain) como mecanismo de intercambiabilidad**: en vez de
  un `Protocol` propio, `langchain_core.language_models.BaseChatModel` es ahora el
  "contrato explícito y estable" que satisface el Principio II — amparado por la
  excepción de "estándar de abstracción de terceros maduro" añadida a la
  constitución en la v1.1.0 (ver `.specify/memory/constitution.md`, Principio II).
  El acoplamiento a los paquetes concretos de LangChain (`langchain-anthropic`,
  `langchain-ollama`) queda confinado a una única función de fábrica compartida:
  `crear_modelo_chat() -> BaseChatModel` en `src/opssleuth/llm/factory.py`,
  documentada en
  [`specs/002-busqueda-logs/contracts/chat_model_provider.md`](002-busqueda-logs/contracts/chat_model_provider.md).
  **Ningún módulo de negocio debe importar `langchain_anthropic`/`langchain_ollama`
  ni los SDKs `anthropic`/`ollama` directamente** — solo recibir un `BaseChatModel`
  ya construido como parámetro. **Cualquier spec futura que necesite razonamiento
  con LLM debe usar `crear_modelo_chat()` en vez de crear un mecanismo de
  selección de proveedor paralelo.**
- **Flujo de aclaración (001, migrado)**: `evaluar_descripcion(chat_model, texto,
  contexto)` + `generar_preguntas(evaluacion, contexto)` en
  `src/opssleuth/clarification/engine.py` — funciones simples parametrizadas por
  `BaseChatModel`, sin clases por proveedor. Comportamiento y entidades de dominio
  (`EvaluacionDescripcion`, etc.) sin cambios respecto a 001 — ver
  [`specs/002-busqueda-logs/contracts/clarification_migration.md`](002-busqueda-logs/contracts/clarification_migration.md).
- **Flujo de búsqueda de logs (002, nuevo)**: `buscar_evidencia(chat_model, caso,
  fuentes, preguntar_callback)` en `src/opssleuth/evidence/engine.py`, con el
  bucle agéntico conducido por un agente LangGraph (`evidence/agent.py`) — una
  única implementación para ambos proveedores (ya no hay Tool Runner vs. bucle
  manual: `BaseChatModel.bind_tools()` es uniforme). Expone 4 herramientas fijas
  (`@tool` de LangChain): `buscar_texto`, `leer_contexto`, `contar_lineas`,
  `preguntar_al_usuario` — ver
  [`specs/002-busqueda-logs/contracts/log_search_engine.md`](002-busqueda-logs/contracts/log_search_engine.md)
  y `contracts/tools_schema.json` (referencia de contenido, no JSON Schema
  consumido en tiempo de ejecución).
- **Modelo de Claude por defecto**: `claude-sonnet-5` *(001, `research.md`,
  Decisión 1; preservado tras la migración a `ChatAnthropic`)*. No cambiar a Opus
  u otro modelo sin justificar una necesidad concreta de mayor capacidad.
- **Variables de entorno establecidas**: `OPSSLEUTH_LLM_PROVIDER`
  (`claude`|`ollama`|`gemini`), `OPSSLEUTH_OLLAMA_MODEL`, `ANTHROPIC_API_KEY`
  (estándar del SDK, usado internamente por `langchain-anthropic`),
  `GOOGLE_API_KEY`/`GEMINI_API_KEY` (estándar del SDK, usado internamente por
  `langchain-google-genai`; ver más abajo). Reutilizar estos nombres para
  necesidades de configuración de proveedor equivalentes; no introducir
  variables nuevas con el mismo propósito. El flujo de búsqueda de logs añade
  el requisito de que el modelo Ollama configurado soporte tool calling — no
  una variable nueva, sino una restricción adicional sobre el mismo
  `OPSSLEUTH_OLLAMA_MODEL`.
- **Tercer proveedor `gemini` (2026-09-14)**: añadido a `crear_modelo_chat()`
  (`src/opssleuth/llm/factory.py`) como alternativa a Ollama para máquinas con
  VRAM/RAM limitada (ver `chat_model_provider.md`, sección "Adición del
  proveedor `gemini`" para el detalle completo y la justificación de la
  excepción constitucional invocada). `ChatGoogleGenerativeAI`
  (`langchain-google-genai`) se acoge a la misma excepción de "estándar de
  abstracción de terceros maduro" (v1.1.0) que ya cubría a Claude/Ollama — no
  se requirió una nueva enmienda a la constitución. Modelo fijo
  `gemini-3.6-flash` (`MODELO_GEMINI_POR_DEFECTO`, disponible en la capa
  gratuita de Google AI Studio, con soporte de tool calling/salida
  estructurada — verificado end-to-end el 2026-09-14; ver nota histórica sobre
  el reemplazo de `gemini-2.5-flash` en `chat_model_provider.md`).
  **Cualquier spec futura que evalúe añadir un cuarto proveedor
  debe seguir el mismo patrón**: confinar la importación del SDK/paquete
  LangChain del proveedor a `llm/factory.py` y documentar la invocación de la
  excepción constitucional en `chat_model_provider.md`, no crear un mecanismo
  de selección paralelo.
- **Excepciones de dominio**: errores de comunicación con el proveedor deben
  propagarse como `ClarificationEngineError`/`LogSearchEngineError` según el
  flujo (nunca la excepción nativa de LangChain o del SDK) — ver Regla 4 de
  `clarification_migration.md` y Regla 3 de `log_search_engine.md`.
- **Nuevas dependencias**: `langchain-core`, `langchain-anthropic`,
  `langchain-ollama`, `langgraph` (ver
  [`specs/002-busqueda-logs/research.md`](002-busqueda-logs/research.md),
  "Nuevas dependencias"); `langchain-google-genai` añadida el 2026-09-14 junto
  con el proveedor `gemini`. `anthropic`/`ollama`/`google-genai` permanecen
  como dependencias transitivas, ya no importadas directamente en código de
  negocio.
- **Cómputo determinista sobre auto-enumeración del LLM**: patrón establecido en
  001 (`generar_preguntas`) y reforzado en 002 (`entradas_destacadas` de
  `ApreciacionInicialLogs`, calculada a partir de los `ToolMessage` reales del
  grafo de LangGraph) — cuando una lista de resultados debe acotarse o
  deduplicarse, hacerlo en código de aplicación a partir de datos ya obtenidos,
  nunca pidiendo al modelo que la enumere libremente en su respuesta.

### Entidades de dominio existentes

- `Caso`, `DescripcionProblema`, `CampoExtraido`, `Aclaracion` en
  `src/opssleuth/domain/case.py` (ver
  [`specs/001-recepcion-incidencia/data-model.md`](001-recepcion-incidencia/data-model.md)).
  Extendido por 002 con `Caso.creado_en` (ancla temporal), `Caso.fuentes_logs` y
  `Caso.apreciacion_logs` (ver
  [`specs/002-busqueda-logs/data-model.md`](002-busqueda-logs/data-model.md)) —
  extensión in-place, no una entidad de caso paralela.
  Un `Caso` vive en memoria de proceso durante la conversación — **sin
  persistencia duradera todavía** (decisión explícita de 001 por simplicidad,
  no una limitación técnica). Si una spec futura necesita persistir casos entre
  sesiones, extender `Caso`/añadir una capa de persistencia detrás de una
  abstracción propia, no crear una entidad de caso paralela — y actualizar esta
  sección para reflejar el cambio de decisión.
- `FuenteDeLogs`, `EntradaLogRelevante`, `ApreciacionInicialLogs` en
  `src/opssleuth/domain/log_evidence.py` (nuevas en 002, ver
  [`specs/002-busqueda-logs/data-model.md`](002-busqueda-logs/data-model.md)).
- Un caso a la vez por conversación; varios casos secuenciales permitidos
  (FR-013/FR-014 de 001). Sin colaboración multiusuario sobre un mismo caso
  (FR-015 de 001).
- Archivos generados a partir de contenido de logs pegado en el chat (FR-003 de
  002) se materializan con `tempfile` (librería estándar), sin persistencia
  duradera más allá de la sesión — mismo criterio de "sin persistencia todavía"
  que el resto del proyecto. Reutilizar este mecanismo para necesidades futuras
  equivalentes de "generar archivo temporal a partir de contenido pegado" en vez
  de introducir uno nuevo.

### Fuera de alcance (reservado para specs futuras)

- Generación de diagnóstico o respuesta final a partir de la evidencia recopilada
  (incluida la apreciación inicial de logs que produce 002) — spec futura.
- Persistencia duradera de casos, evidencia de logs y detección/redacción de datos
  sensibles en las descripciones o en los logs (explícitamente diferido en 001, FR-012, y
  reafirmado por 002 por consistencia).
- ~~Búsqueda/recopilación de evidencia en fuentes de observabilidad~~ — la búsqueda en
  archivos de logs ya está cubierta por 002; otras fuentes de observabilidad (métricas,
  trazas, APM, etc.) siguen fuera de alcance para specs futuras.

## Notas de spec drift a vigilar

_(Vacío por ahora. Cuando `/speckit-analyze` u otra revisión detecte una
inconsistencia entre specs, documentarla aquí hasta resolverla — no dejarla solo
en el reporte de análisis de una sesión que se pierde después.)_
