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
| 002 | Búsqueda en Archivos de Logs | [`specs/002-busqueda-logs/`](002-busqueda-logs/) | ❓ Clarificada (checklist 100%, lista para `/speckit-plan`) | `002-busqueda-logs` | 2026-09-03 | Segunda herramienta de investigación: una vez completada la recepción de la incidencia (001), el sistema invita a aportar evidencia de logs (ruta o texto pegado), localiza entradas relacionadas con el incidente sin cargar el archivo completo, aísla por horario si se conoce, y carga una apreciación inicial **consolidada** (acotada si hay muchas coincidencias) en el contexto del caso. |

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
- **Constitución**: `.specify/memory/constitution.md` (v1.0.0) — SOLID,
  arquitectura modular y reemplazable, docstrings numpydoc (backend) / JSDoc
  (frontend) obligatorios, simplicidad ante todo. Toda spec debe pasar el
  "Constitution Check" de `/speckit-plan`.

### Motor de modelo de lenguaje (LLM)

- **Contrato `ClarificationEngine`** (`src/opssleuth/clarification/engine.py`,
  documentado en
  [`specs/001-recepcion-incidencia/contracts/clarification_engine.md`](001-recepcion-incidencia/contracts/clarification_engine.md)):
  patrón de motor de IA intercambiable — `ClaudeClarificationEngine` (remoto,
  por defecto) y `OllamaClarificationEngine` (local), seleccionados vía
  `crear_motor_aclaracion()` en `factory.py`. **Cualquier spec futura que
  necesite razonamiento con LLM debe evaluar primero si puede extender este
  contrato** (o seguir el mismo patrón: contrato + adaptadores + factory) en vez
  de crear un mecanismo paralelo de selección de proveedor.
- **Modelo de Claude por defecto**: `claude-sonnet-5` *(001, `research.md`,
  Decisión 1)*. No cambiar a Opus u otro modelo sin justificar una necesidad
  concreta de mayor capacidad.
- **Variables de entorno establecidas**: `OPSSLEUTH_LLM_PROVIDER`
  (`claude`|`ollama`), `OPSSLEUTH_OLLAMA_MODEL`, `ANTHROPIC_API_KEY` (estándar
  del SDK). Reutilizar estos nombres para necesidades de configuración de
  proveedor equivalentes; no introducir variables nuevas con el mismo propósito.
- **Excepciones de dominio**: errores de comunicación con el proveedor deben
  propagarse como `ClarificationEngineError` (nunca la excepción nativa del SDK)
  — ver Regla 4 del contrato.

### Entidades de dominio existentes

- `Caso`, `DescripcionProblema`, `CampoExtraido`, `Aclaracion` en
  `src/opssleuth/domain/case.py` (ver
  [`specs/001-recepcion-incidencia/data-model.md`](001-recepcion-incidencia/data-model.md)).
  Un `Caso` vive en memoria de proceso durante la conversación — **sin
  persistencia duradera todavía** (decisión explícita de 001 por simplicidad,
  no una limitación técnica). Si una spec futura necesita persistir casos entre
  sesiones, extender `Caso`/añadir una capa de persistencia detrás de una
  abstracción propia, no crear una entidad de caso paralela — y actualizar esta
  sección para reflejar el cambio de decisión.
- Un caso a la vez por conversación; varios casos secuenciales permitidos
  (FR-013/FR-014 de 001). Sin colaboración multiusuario sobre un mismo caso
  (FR-015 de 001).

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
