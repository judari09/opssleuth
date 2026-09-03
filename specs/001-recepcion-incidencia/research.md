# Research: Recepción de Incidencia

## Decisión 0: Mecanismo de comprensión de lenguaje natural (NLU)

**Decision**: Basado en LLM, usando la API de Claude (Anthropic) a través del SDK oficial
de Python (`anthropic`).

**Rationale**: RF3 requiere evaluar si una descripción libre en lenguaje natural contiene
información suficiente y generar preguntas de aclaración contextuales y naturales. Aunque
FR-006 enumera exactamente 3 campos objetivo (sistema/aplicación afectada, síntoma,
momento/frecuencia), decidir si un texto libre los cubre —y en qué grado— es un problema de
comprensión de lenguaje natural poco fiable con heurísticas de palabras clave. Confirmado
con el solicitante (ver sesión de `/speckit-specify` → pregunta sobre "Motor de NLU").
Además, el resto del agente OpsSleuth (fases futuras de búsqueda de evidencia y
diagnóstico) previsiblemente requerirá razonamiento con LLM, por lo que introducir esta
dependencia ahora, detrás de una interfaz reemplazable, es coherente con el resto del
proyecto.

**Alternatives considered**:
- *Heurísticas locales (reglas/palabras clave)*: cero dependencias externas, pero frágil
  ante texto libre variado y con preguntas de aclaración poco naturales. Rechazado por el
  solicitante.
- *Híbrido*: mantiene dos caminos de lógica desde el día uno sin necesidad demostrada.
  Rechazado por sobreingeniería (Principio IV de la constitución) dado que aún no hay
  evidencia de que las heurísticas puras fallen en producción.

## Decisión 1: Modelo de Claude a utilizar

**Decision**: `claude-sonnet-5` como modelo por defecto para esta funcionalidad.

**Rationale**: La tarea de esta fase es acotada — clasificar la presencia de 3 campos en un
texto corto y, si faltan, generar 1-3 preguntas de aclaración en lenguaje natural. Es un
caso de uso de "Classification, summarization, extraction, Q&A" (una sola llamada a la API,
sin herramientas ni agentes), donde Claude Sonnet 5 ofrece calidad cercana a Opus a un costo
significativamente menor, coherente con el Principio IV (simplicidad, evitar
sobreingeniería y costos no justificados). El motor de aclaración queda detrás de una
interfaz (ver Decisión 3), por lo que cambiar de modelo o de proveedor en el futuro no
requiere tocar el resto del sistema.

**Alternatives considered**:
- *`claude-opus-5`*: mayor calidad de razonamiento, pero costo ~1.7x-2.5x superior sin que
  la tarea (clasificación + generación breve) lo requiera en esta fase.
- *`claude-haiku-4-5`*: más económico y rápido, pero con menor fiabilidad en tareas de
  comprensión de texto libre ambiguo; se prefiere Sonnet 5 para no comprometer la calidad de
  las aclaraciones generadas en la primera fase del producto.

## Decisión 2: Persistencia del contexto de la conversación (multi-turn)

**Decision**: La API de Mensajes de Claude es sin estado (stateless): el contexto se
mantiene reenviando el historial completo de mensajes (`messages`) en cada llamada. El
`Caso` mantiene en memoria de proceso una lista de mensajes (`role`/`content`) que se
actualiza con cada turno (descripción inicial, preguntas del sistema, respuestas del
usuario). No se usa almacenamiento persistente (archivo/BD) en esta fase, consistente con
la Aclaración de la sesión de `/speckit-clarify`: un caso vive dentro de una conversación,
en memoria, sin persistencia entre sesiones del proceso.

**Rationale**: Es el patrón estándar documentado para conversaciones multi-turno con la
API de Claude (`ConversationManager` — ver referencia del SDK). Cumple RF2 sin introducir
una capa de persistencia no solicitada (Principio IV).

**Alternatives considered**:
- *Persistencia en archivo/BD por caso*: permitiría reanudar un caso entre ejecuciones del
  proceso, pero no fue solicitado y añade complejidad (esquema de almacenamiento, migración,
  concurrencia) sin una necesidad presente. Rechazado por ahora; puede añadirse en una fase
  posterior detrás de la misma abstracción de `Caso` si se solicita.
- *Managed Agents (sesiones administradas por Anthropic)*: pensado para agentes con
  herramientas, sandbox y ejecución de larga duración; sobredimensionado para una única
  llamada de clasificación/generación por turno. Rechazado por sobreingeniería.

## Decisión 3: Extracción fiable de la presencia de los 3 campos requeridos

**Decision**: Usar **structured outputs** de la API de Mensajes (`output_config.format` con
un JSON Schema, a través de `client.messages.parse()`) para obtener una respuesta validada
del modelo con la evaluación de los 3 campos requeridos (sistema/aplicación, síntoma,
momento/frecuencia): por cada uno, si está presente y, de ser así, el valor extraído; y, si
falta información, hasta 3 preguntas de aclaración dirigidas específicamente a los datos
faltantes.

**Rationale**: `messages.parse()` con `output_config.format` garantiza una respuesta JSON
válida conforme al esquema, evitando parsers frágiles de texto libre y reintentos manuales.
Es el mecanismo recomendado por la documentación de la API de Claude para extracción
estructurada fiable (frente a prefill de mensajes, deprecado/rechazado en los modelos
usados aquí). Soportado por `claude-sonnet-5`.

**Alternatives considered**:
- *Parseo de texto libre con expresiones regulares*: frágil e inconsistente con
  descripciones variadas; rechazado.
- *Tool use forzado (`tool_choice`)*: alternativa viable equivalente en fiabilidad, pero
  `output_config.format` es más simple para este caso de uso de "clasificación + extracción"
  sin necesidad de un ciclo de ejecución de herramientas; se prefiere por simplicidad
  (Principio IV).

## Decisión 4: Modularidad sobre el proveedor de modelo (soporte de modelos locales vía Ollama)

**Decision**: Además de `ClaudeClarificationEngine` (Decisión 1), incluir una segunda
implementación de referencia del contrato `ClarificationEngine` —`OllamaClarificationEngine`—
basada en el cliente oficial de Python (`ollama`), que permite ejecutar el motor de
aclaración contra modelos servidos localmente por [Ollama](https://ollama.com). La
implementación a usar en tiempo de ejecución se selecciona mediante configuración (variable
de entorno `OPSSLEUTH_LLM_PROVIDER=claude|ollama`, por defecto `claude`), resuelta por una
única función de fábrica (`clarification/factory.py`) que es el único punto del sistema que
conoce ambas implementaciones concretas.

**Rationale**: El Principio II de la constitución exige que los módulos con dependencias
externas (aquí, el proveedor de modelo) sean reemplazables sin cambios en los módulos
consumidores. Tener una única implementación concreta (Claude) deja esa modularidad sin
demostrar: el contrato podría, en la práctica, tener fugas de detalles específicos de
Anthropic sin que nada lo detecte. Añadir una segunda implementación real, con un proveedor
de naturaleza distinta (local, sin red externa, sin costo por token), obliga a que el
contrato (`contracts/clarification_engine.md`) sea genuinamente independiente del proveedor
y verifica en código que `Caso`/CLI nunca dependen de `anthropic` u `ollama` directamente.

**Consideraciones de fiabilidad (documentadas por el contrato, regla 3)**: los modelos
locales servidos por Ollama varían en su soporte y fiabilidad de salida estructurada
(`format` con JSON Schema) según el modelo específico que el usuario tenga descargado. Esto
no rompe el contrato —`OllamaClarificationEngine` sigue devolviendo un `EvaluacionDescripcion`
válido o lanza `ClarificationEngineError`—, pero la calidad de la evaluación/preguntas
generadas puede ser menor que con Claude según el modelo local elegido. Esto se documenta
como una característica conocida del proveedor local, no como un defecto del contrato.

**Alternatives considered**:
- *No incluir un segundo proveedor en esta fase*: cumple la letra del contrato (interfaz
  definida) pero no demuestra la intercambiabilidad en la práctica; se prefiere incluirlo
  ahora, a solicitud explícita, dado que es una necesidad presente y no hipotética.
- *Soporte genérico "cualquier proveedor OpenAI-compatible"*: más flexible en abstracto, pero
  añade una capa de indirección (adaptador genérico + configuración de endpoints arbitrarios)
  no solicitada; rechazado por sobreingeniería (Principio IV). Ollama cubre concretamente la
  necesidad pedida (modelos locales).
- *Modelo local por defecto fijo en el código*: rechazado — qué modelos tiene disponibles el
  usuario en su instancia de Ollama es específico de cada entorno; se deja como configuración
  explícita (`OPSSLEUTH_OLLAMA_MODEL`), sin un valor por defecto asumido en el código.

## Resumen de Technical Context resuelto

| Aspecto | Valor |
|---|---|
| Language/Version | Python 3.13 (`.python-version`, `pyproject.toml`) |
| Primary Dependencies | `anthropic` (SDK oficial de Claude, proveedor remoto por defecto), `ollama` (cliente oficial de Ollama, proveedor local alternativo — Decisión 4), `pydantic` (esquema para structured outputs, compartido) |
| Storage | N/A — contexto del caso en memoria de proceso durante la conversación |
| Testing | `pytest`, con el cliente de Anthropic mockeado en pruebas unitarias |
| Target Platform | Aplicación de línea de comandos (CLI), multiplataforma (Windows/Linux/macOS) |
| Project Type | Proyecto único (single project): `src/`, `tests/` |
| Performance Goals | Interacción conversacional; una llamada a la API de Claude por turno (latencia típica de segundos, sin objetivo numérico estricto en esta fase) |
| Constraints | Requiere `ANTHROPIC_API_KEY` (o perfil `ant auth login`) y acceso de red saliente a la API de Claude; sin modo offline en esta fase |
| Scale/Scope | Un usuario por conversación; un caso activo a la vez por conversación (varios casos secuenciales permitidos, según aclaración) |
