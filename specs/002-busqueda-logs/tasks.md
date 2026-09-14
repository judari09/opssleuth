---

description: "Task list template for feature implementation"
---

# Tasks: Búsqueda en Archivos de Logs

**Input**: Design documents from `/specs/002-busqueda-logs/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Se incluyen tareas de pruebas unitarias, siguiendo el mismo criterio que 001: `plan.md`
(Technical Context → Testing) designa explícitamente `pytest` con archivos `tests/unit/*.py` como
parte del diseño de esta funcionalidad.

**Organization**: Las tareas están agrupadas por historia de usuario para permitir implementación y
prueba independientes de cada una. **Alcance ampliado** (decisión del usuario, 2026-09-03): la fase
Foundational incluye además la migración del motor de aclaración de 001 (`ClarificationEngine`) a la
arquitectura basada en LangChain adoptada por esta spec — ver `research.md`, Decisiones 1, 3 y 9, y
`contracts/chat_model_provider.md` / `contracts/clarification_migration.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias entre sí)
- **[Story]**: A qué historia de usuario pertenece la tarea (US1, US2, US3, US4)
- Cada tarea incluye la ruta de archivo exacta

## Path Conventions

- Proyecto único: `src/opssleuth/`, `tests/unit/` en la raíz del repositorio (ver `plan.md` → Project Structure)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Añadir las dependencias nuevas del ecosistema LangChain/LangGraph y el esqueleto de
paquetes que sustituye/extiende la estructura de 001.

- [X] T001 Añadir las dependencias `langchain`, `langchain-core`, `langchain-anthropic`,
  `langchain-ollama` y `langgraph` en `pyproject.toml` (ver `research.md`, "Nuevas dependencias";
  `langchain` se añadió además de lo planificado porque `langchain.agents.create_agent` — verificado
  contra la documentación instalada como la construcción recomendada para salida estructurada y
  agentes con herramientas — vive en ese paquete, no en `langchain-core`); `anthropic` y `ollama`
  permanecen como dependencias transitivas
- [X] T002 [P] Crear el esqueleto de paquetes Python nuevos: `src/opssleuth/llm/__init__.py`,
  `src/opssleuth/evidence/__init__.py`

**Checkpoint**: Dependencias instaladas; paquetes `llm/` y `evidence/` listos para recibir código.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: (a) La función de fábrica compartida de modelo de chat, de la que dependen ambos flujos
del proyecto; (b) la migración del motor de aclaración de 001 a esa fábrica compartida (alcance
ampliado de esta spec — ver `research.md`, Decisión 9); (c) las entidades de dominio nuevas y la
extensión de `Caso` que las cuatro historias de usuario de esta spec necesitan.

**⚠️ CRITICAL**: Ninguna historia de usuario puede implementarse antes de completar esta fase

- [X] T003 Implementar `crear_modelo_chat() -> BaseChatModel` en `src/opssleuth/llm/factory.py`,
  según `contracts/chat_model_provider.md`: lee `OPSSLEUTH_LLM_PROVIDER` (por defecto `claude`) y
  devuelve `ChatAnthropic(model="claude-sonnet-5", ...)` u `ChatOllama(model=<OPSSLEUTH_OLLAMA_MODEL>,
  ...)`; lanza `ProveedorDesconocidoError` ante un valor no reconocido y
  `ModeloOllamaNoConfiguradoError` si falta `OPSSLEUTH_OLLAMA_MODEL` con el proveedor `ollama`
  (mismos nombres de excepción que la implementación original de 001, preservados), con docstring
  numpydoc. Esta es la ÚNICA función del proyecto que puede importar `langchain_anthropic`/
  `langchain_ollama` (Principio II, excepción de estándar de terceros — ver
  `.specify/memory/constitution.md`)
- [X] T004 [P] Migrar el motor de aclaración en `src/opssleuth/clarification/engine.py`, según
  `contracts/clarification_migration.md`: reemplazar el `Protocol` `ClarificationEngine` y la clase
  base compartida por dos funciones de módulo — `evaluar_descripcion(chat_model: BaseChatModel,
  texto: str, contexto: list[dict]) -> EvaluacionDescripcion` (usando el mecanismo estándar de
  `BaseChatModel` para salida estructurada contra `EvaluacionDescripcion`, preservando la Regla 1:
  sin efectos secundarios sobre `Caso`) y `generar_preguntas(evaluacion, contexto) -> list[Aclaracion]`
  (sin cambios de comportamiento respecto a 001 — transformación determinista, sin llamada adicional
  al modelo, Regla 5 preservada); capturar las excepciones que el proveedor subyacente propague y
  relanzarlas como `ClarificationEngineError` (conservando la excepción original como `__cause__`,
  Regla 4); **eliminar** `src/opssleuth/clarification/claude_engine.py`,
  `src/opssleuth/clarification/ollama_engine.py` y `src/opssleuth/clarification/factory.py`
  (sustituidos por T003); mantener `EvaluacionDescripcion` y demás tipos Pydantic sin cambios; todo
  con docstring numpydoc
- [X] T005 [P] Migrar `tests/unit/test_claude_engine.py` y `tests/unit/test_ollama_engine.py` a
  `tests/unit/test_evaluar_descripcion.py`, preservando cada caso de prueba existente (detección de
  campos presentes/ausentes, detección de `contradiccion`, detección de `multiples_problemas`,
  transformación determinista de `generar_preguntas`, propagación de `ClarificationEngineError`),
  pero mockeando `BaseChatModel` (o `ChatAnthropic`/`ChatOllama` según corresponda) en vez del
  cliente `anthropic`/`ollama` crudo — ver `contracts/clarification_migration.md`, "Estrategia de
  migración de pruebas"
- [X] T006 Actualizar `src/opssleuth/cli.py` para obtener un único `BaseChatModel` vía
  `crear_modelo_chat()` en `main()` y pasarlo a `evaluar_descripcion()`/`generar_preguntas()` en el
  flujo de intake existente, en vez de instanciar `ClarificationEngine` — sin cambios en el
  comportamiento observable del flujo de aclaración de 001
- [X] T007 Implementar las entidades de dominio `FuenteDeLogs`, `EntradaLogRelevante` y
  `ApreciacionInicialLogs` en `src/opssleuth/domain/log_evidence.py`, según `data-model.md` (campos,
  reglas de validación: `FuenteDeLogs.ruta` no vacía, `EntradaLogRelevante.numero_linea >= 1`), con
  docstrings numpydoc en cada clase
- [X] T008 [P] Extender `Caso` en `src/opssleuth/domain/case.py` con los campos `creado_en: datetime`
  (poblado automáticamente al crear el caso — ancla temporal, `research.md` Decisión 5),
  `fuentes_logs: list[FuenteDeLogs]` (lista vacía por defecto) y `apreciacion_logs:
  ApreciacionInicialLogs | None` (ver `data-model.md`, "Extensión de `Caso`"); actualizar el
  docstring numpydoc de `Caso`
- [X] T009 [P] Pruebas unitarias de las entidades nuevas de dominio (`FuenteDeLogs`,
  `EntradaLogRelevante`, `ApreciacionInicialLogs`, incluyendo sus reglas de validación) en
  `tests/unit/test_log_evidence.py`, y de la extensión de `Caso` (`creado_en` poblado automáticamente,
  `fuentes_logs`/`apreciacion_logs` con sus valores por defecto) añadidas a `tests/unit/test_case.py`

**Checkpoint**: Fábrica de modelo compartida lista; motor de aclaración de 001 migrado y con
comportamiento preservado (verificable ya en este punto contra `001-recepcion-incidencia/quickstart.md`);
entidades de dominio de esta spec listas — la implementación de las historias de usuario puede
comenzar.

---

## Phase 3: User Story 1 - Aportar la evidencia de logs a analizar (Priority: P1) 🎯 MVP

**Goal**: En cuanto la recepción de la incidencia queda completa, el sistema invita proactivamente a
aportar logs y acepta tanto una ruta de archivo como contenido pegado en el chat, generando un
archivo temporal cuando ese contenido supera 4 líneas.

**Independent Test**: Aportar una ruta a un archivo de logs existente y verificar que el sistema la
acepta y la usa como fuente; y, por separado, pegar contenido de logs directamente en la conversación
(por encima y por debajo del umbral de 4 líneas) y verificar el comportamiento correspondiente en
cada caso.

### Implementation for User Story 1

- [X] T010 [US1] Implementar la invitación proactiva a aportar logs en `src/opssleuth/cli.py`: en
  cuanto `Caso.estado_informacion` queda `"completa"` (recepción de 001) y no hay fuentes de logs
  aportadas todavía, invitar explícitamente al usuario a aportarlas, sin que este tenga que
  solicitarlo (FR-014)
- [X] T011 [US1] Implementar el aporte de logs por ruta de archivo en `src/opssleuth/cli.py`: registra
  una `FuenteDeLogs(origen="ruta_usuario")` en `Caso.fuentes_logs` cuando la ruta es accesible
  (FR-001); si la ruta no existe o no es accesible, informa al usuario y permite indicar otra ruta o
  pegar los logs directamente, sin fallar silenciosamente (FR-002)
- [X] T012 [US1] Implementar el aporte de logs por contenido pegado en `src/opssleuth/cli.py`:
  acumula el total de líneas pegadas por el usuario (incluso si llegan fragmentadas en varios
  mensajes sucesivos); si el total supera 4 líneas, escribe el contenido a un archivo temporal vía
  `tempfile` (sufijo `.log`, ver `research.md` Decisión 8), informa al usuario la ruta/nombre del
  archivo generado antes de continuar (FR-015) y registra una `FuenteDeLogs(origen="contenido_pegado")`
  con esa ruta (FR-003); si el total es 4 líneas o menos, usa el contenido directamente sin generar
  archivo (FR-004)
- [X] T013 [P] [US1] Pruebas unitarias de la lógica de acumulación de líneas pegadas/umbral de 4
  líneas, generación de archivo temporal, y validación de ruta de archivo (accesible/inaccesible) en
  `tests/unit/test_cli.py`, siguiendo el mismo patrón de `monkeypatch` sobre E/S ya usado en 001

**Checkpoint**: En este punto, la Historia de Usuario 1 debe ser completamente funcional y probable
de forma independiente (escenarios 1 y 2 de `quickstart.md`).

---

## Phase 4: User Story 2 - Localizar entradas de log relacionadas con el incidente (Priority: P2)

**Goal**: Con la evidencia ya aportada, el sistema localiza — sin cargar el archivo completo — las
entradas relacionadas con el incidente, aislando por horario cuando se conoce, o por contenido del
problema descrito cuando no.

**Independent Test**: Aportar un archivo de logs de gran tamaño junto con la hora aproximada del
incidente y verificar que el sistema aísla las entradas de ese horario sin intervención manual del
usuario; y, por separado, sin hora conocida, verificar que localiza entradas por contenido.

### Implementation for User Story 2

- [X] T014 [US2] Implementar las herramientas `buscar_texto`, `leer_contexto` y `contar_lineas` en
  `src/opssleuth/evidence/tools.py`, decoradas con `@tool` de `langchain_core.tools` (esquema
  auto-derivado de anotaciones de tipo + docstring — usar el texto de `contracts/tools_schema.json`
  como contenido de cada docstring), operando por iteración de líneas sobre un archivo en disco (sin
  cargarlo completo en memoria) según `contracts/log_search_engine.md`
- [X] T015 [P] [US2] Pruebas unitarias de `buscar_texto`/`leer_contexto`/`contar_lineas` contra
  archivos de logs de prueba (sin mock de modelo) en `tests/unit/test_tools.py`, cubriendo: patrón
  con y sin coincidencias, límite `maximo_resultados`, lectura de contexto en los bordes del archivo
- [X] T016 [US2] Construir el agente LangGraph en `src/opssleuth/evidence/agent.py` (p. ej.
  `langgraph.prebuilt.create_react_agent`, o un `StateGraph` a medida si el bookkeeping determinista
  de T017 lo requiere — ver `research.md` Decisión 3), parametrizado por el `chat_model` recibido y
  enlazado a las 3 herramientas de T014; el prompt del sistema DEBE guiar al modelo a: (a) construir
  patrones regex de fecha/hora sobre el ancla `Caso.creado_en`/`momento` cuando se conoce el horario
  del incidente (FR-006, `research.md` Decisión 4), y (b) buscar por sistema afectado/síntoma cuando
  no se conoce (FR-007); límite de iteraciones razonable (Regla 7 del contrato)
- [X] T017 [US2] Implementar `buscar_evidencia(chat_model, caso, fuentes, preguntar_callback)` en
  `src/opssleuth/evidence/engine.py`: invoca el agente de T016 sobre una fuente activa a la vez;
  registra de forma determinista cada `EntradaLogRelevante` a partir de los `ToolMessage` reales
  devueltos por las herramientas (`research.md` Decisión 6 — nunca por enumeración libre del modelo);
  cuando ninguna herramienta produce resultados, refleja explícitamente la ausencia de coincidencias
  en vez de omitirlo (FR-008); define y lanza `LogSearchEngineError` (mismo criterio que
  `ClarificationEngineError`) ante fallos del proveedor subyacente (Regla 3 del contrato); con
  docstring numpydoc
- [X] T018 [P] [US2] Pruebas unitarias de `buscar_evidencia` con `BaseChatModel`/agente mockeado en
  `tests/unit/test_buscar_evidencia.py`, cubriendo: aislamiento por horario conocido, localización
  por contenido sin horario conocido, mensaje explícito de "sin coincidencias", y propagación de
  `LogSearchEngineError`

**Checkpoint**: En este punto, las Historias de Usuario 1 y 2 deben funcionar juntas de forma
independiente (escenarios 3, 4 y 5 de `quickstart.md`).

---

## Phase 5: User Story 3 - Obtener una apreciación inicial de lo encontrado en los logs (Priority: P3)

**Goal**: El sistema elabora una apreciación inicial consolidada (entre todas las fuentes aportadas)
a partir de las entradas localizadas, acotada ante volúmenes grandes, y la incorpora al contexto del
caso para referencia posterior.

**Independent Test**: Completar una búsqueda de logs y verificar que el sistema presenta una
apreciación inicial coherente, que sigue disponible más adelante en la misma conversación, y que se
consolida correctamente cuando hay varias fuentes de logs.

### Implementation for User Story 3

- [X] T019 [US3] Implementar el cómputo determinista de `entradas_destacadas` en
  `src/opssleuth/evidence/engine.py` (extiende T017): acota y deduplica la lista de entradas
  registradas a un conjunto representativo cuando el volumen de coincidencias es muy grande, y
  establece `ApreciacionInicialLogs.hay_mas_coincidencias = true` en ese caso, indicando que existen
  más resultados disponibles (FR-009a)
- [X] T020 [US3] Implementar la consolidación entre varias fuentes en `src/opssleuth/evidence/engine.py`
  (extiende T017/T019): `buscar_evidencia` itera todas las `fuentes` recibidas, acumula sus
  `EntradaLogRelevante` antes de aplicar el límite/deduplicación de T019, y produce una única
  `ApreciacionInicialLogs.resumen` de síntesis (pedido al modelo a partir de la lista ya acotada, no
  al revés) — nunca una apreciación independiente por fuente (FR-010a, FR-009)
- [X] T021 [US3] Integrar `buscar_evidencia()` en el flujo de la CLI en `src/opssleuth/cli.py`:
  invocarlo una vez aportadas las fuentes de logs de US1, guardar el resultado en
  `Caso.apreciacion_logs` (FR-010), y exponerlo cuando el usuario pida al sistema que recuerde o
  resuma lo encontrado en los logs (consistente con `Caso.resumen()` de 001)
- [X] T022 [P] [US3] Pruebas unitarias del cómputo de `entradas_destacadas`/`hay_mas_coincidencias`
  ante volúmenes grandes, de la consolidación multi-fuente, y del texto de apreciación cuando no se
  encontró evidencia (nunca una conclusión fabricada — SC-003) en `tests/unit/test_buscar_evidencia.py`

**Checkpoint**: En este punto, las Historias de Usuario 1, 2 y 3 deben funcionar juntas de forma
independiente (escenarios 6, 7 y 8 de `quickstart.md`).

---

## Phase 6: User Story 4 - Solicitar contexto del proyecto cuando sea necesario (Priority: P4)

**Goal**: Cuando el contenido de los logs o del problema no es interpretable sin conocer más sobre el
proyecto, el sistema pregunta al usuario por contexto general — sin preguntar innecesariamente
cuando el contenido ya es claro.

**Independent Test**: Aportar logs con terminología o estructura propia de un proyecto no descrita
previamente y verificar que el sistema pregunta por contexto antes de continuar; y, por separado,
aportar logs con contenido claro y verificar que esa pregunta no se formula innecesariamente.

### Implementation for User Story 4

- [X] T023 [US4] Implementar la herramienta `preguntar_al_usuario` en `src/opssleuth/evidence/tools.py`,
  decorada con `@tool`, cuyo cuerpo invoca el `preguntar_callback` recibido (mediante cierre/closure
  o el mecanismo de LangGraph para argumentos de herramienta inyectados en tiempo de ejecución —
  `research.md` Decisión 4) — NUNCA accede directamente a `stdin`/`stdout` (Regla 4 del contrato);
  añadirla al conjunto de herramientas enlazadas al agente en `src/opssleuth/evidence/agent.py`
  (extiende T016)
- [X] T024 [US4] Implementar `preguntar_callback` en `src/opssleuth/cli.py`: imprime la pregunta al
  usuario por la línea de comandos, lee su respuesta, y la pasa como argumento a `buscar_evidencia()`
  en la integración de T021
- [X] T025 [US4] Refinar el prompt del sistema del agente en `src/opssleuth/evidence/agent.py`
  (extiende T016) con guía explícita sobre cuándo usar `preguntar_al_usuario`: únicamente cuando el
  contenido de los logs o del problema no puede interpretarse sin contexto adicional del proyecto
  (terminología propia, nombres de componentes, convenciones de formato desconocidas — FR-011); NO
  usarla cuando el contenido ya es interpretable por sí mismo (FR-012)
- [X] T026 [P] [US4] Pruebas unitarias verificando que `preguntar_al_usuario` invoca el callback
  inyectado (con un callback falso, sin acceso real a stdin/stdout) ante contenido no interpretable, y
  que NO se invoca ante contenido ya claro, en `tests/unit/test_tools.py` y/o
  `tests/unit/test_buscar_evidencia.py`

**Checkpoint**: Las cuatro historias de usuario deben ser funcionales de forma independiente
(escenario 9 de `quickstart.md`, más el escenario 10 de regresión del motor de aclaración migrado).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final que abarca la migración y las cuatro historias de usuario.

- [X] T027 [P] Revisar que todas las clases y funciones nuevas o migradas en `src/opssleuth/` cuenten
  con docstrings numpydoc completos (Parameters, Returns, Raises), conforme al Principio III de la
  constitución — incluyendo las funciones `@tool` (cuyo docstring alimenta además el esquema que ve
  el modelo)
- [X] T028 Revisar `pyproject.toml`: confirmar si `anthropic`/`ollama` siguen siendo necesarios como
  dependencias directas o si pueden quedar únicamente como transitivas de `langchain-anthropic`/
  `langchain-ollama` (ver `research.md`, "Nuevas dependencias")
- [X] T029 Verificar por inspección (o búsqueda de importaciones) que ningún módulo de negocio fuera
  de `src/opssleuth/llm/factory.py` importa `langchain_anthropic`, `langchain_ollama`, `anthropic` u
  `ollama` directamente — confinamiento exigido por la excepción del Principio II (constitución
  v1.1.0)
- [ ] T030 Ejecutar manualmente los escenarios de validación de `quickstart.md` (escenarios 1 a 9, más
  el escenario 10 de regresión del motor de aclaración migrado) con ambos proveedores
  (`OPSSLEUTH_LLM_PROVIDER=claude` y `OPSSLEUTH_LLM_PROVIDER=ollama`, este último con un modelo local
  que soporte tool calling), confirmando comportamiento observable idéntico entre proveedores
  — **pendiente**: requiere ejecución interactiva contra un proveedor real (API key de Claude o
  instancia local de Ollama en ejecución), no ejecutable de forma autónoma en la sesión de
  `/speckit-implement` (ver `/speckit-implement` del 2026-09-07); T001-T029 verificados por
  inspección de código y suite automatizada (72/72 tests, `uv run pytest tests/`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciarse de inmediato
- **Foundational (Phase 2)**: Depende de que Setup esté completo — BLOQUEA todas las historias de
  usuario. Internamente: T003 (fábrica compartida) precede a T004 (migración, que la usa); T004
  precede a T005 (pruebas migradas) y a T006 (integración en la CLI); T007 precede a T008 (extensión
  de `Caso` referencia `FuenteDeLogs`/`ApreciacionInicialLogs`); T007/T008 preceden a T009 (pruebas)
- **User Story 1 (Phase 3)**: Depende de Foundational
- **User Story 2 (Phase 4)**: Depende de User Story 1 — necesita fuentes de logs ya aportadas para
  poder buscar sobre ellas (el spec documenta esta dependencia explícitamente: "Depende de que exista
  evidencia aportada (US1)")
- **User Story 3 (Phase 5)**: Depende de User Story 2 — la apreciación se elabora a partir de las
  entradas que US2 localiza ("Depende de que existan entradas localizadas (US2)")
- **User Story 4 (Phase 6)**: Depende de que el agente de búsqueda (US2/US3) ya exista, sobre el cual
  añade la herramienta de contexto de proyecto — el spec lo documenta como capacidad de apoyo,
  priorizada después de las capacidades centrales
- **Polish (Phase 7)**: Depende de que las cuatro historias de usuario y la migración estén completas

> Igual que en 001, esta funcionalidad tiene una dependencia secuencial genuina y documentada en
> `spec.md` entre sus historias de usuario (cada prioridad se apoya explícitamente en la anterior),
> por lo que se implementan en orden P1 → P2 → P3 → P4, no en paralelo entre sí.

### Within Each User Story

- Las herramientas (`tools.py`) preceden a la construcción del agente (`agent.py`), que precede a la
  orquestación (`evidence/engine.py`), que precede a su integración en `cli.py`
- Las pruebas unitarias de un módulo se ejecutan después de implementar ese módulo (no hay TDD
  estricto solicitado en el spec)

### Parallel Opportunities

- T001 y T002 (Setup) no tienen dependencia entre sí pero T002 no requiere T001 completo — pueden
  solaparse
- T004 y T005 (Foundational: migración y sus pruebas) pueden ejecutarse en paralelo una vez completo
  T003; T007 y T008 (entidades nuevas y extensión de `Caso`) pueden ejecutarse en paralelo
- T013, T015, T018, T022 y T026 (pruebas unitarias de cada historia) pueden ejecutarse en paralelo
  respecto a otras tareas de prueba de historias distintas, una vez completada la implementación que
  cubren
- T027 (Polish) puede ejecutarse en paralelo con T028/T029; T030 depende de que toda la
  implementación esté completa

---

## Parallel Example: Foundational

```bash
# Una vez completado T003 (crear_modelo_chat), lanzar en paralelo:
Task: "Migrar el motor de aclaración en src/opssleuth/clarification/engine.py"
Task: "Migrar las pruebas a tests/unit/test_evaluar_descripcion.py"

# En paralelo con lo anterior, también sin dependencia entre sí:
Task: "Implementar FuenteDeLogs/EntradaLogRelevante/ApreciacionInicialLogs en src/opssleuth/domain/log_evidence.py"
Task: "Extender Caso con creado_en/fuentes_logs/apreciacion_logs en src/opssleuth/domain/case.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — incluye la migración del motor de 001 y bloquea todas
   las historias de esta spec)
3. Completar Phase 3: User Story 1
4. **DETENER Y VALIDAR**: Probar la User Story 1 de forma independiente contra `quickstart.md`
   (escenarios 1 y 2), y validar la regresión de 001 (escenario 10) ya en este punto, dado que la
   migración ocurrió en Foundational
5. Desplegar/demostrar si está listo

### Incremental Delivery

1. Setup + Foundational completos (incluye migración) → base lista
2. Añadir User Story 1 → probar de forma independiente → demo (MVP)
3. Añadir User Story 2 → probar de forma independiente → demo
4. Añadir User Story 3 → probar de forma independiente → demo
5. Añadir User Story 4 → probar de forma independiente → demo
6. Cada historia añade valor sin romper las anteriores

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí
- [Story] mapea cada tarea a su historia de usuario para trazabilidad
- Dada la dependencia secuencial documentada en el spec, no se recomienda desarrollo en paralelo por
  historia con múltiples desarrolladores en esta funcionalidad
- Confirmar que las pruebas fallan antes de implementar solo aplica si se decide seguir TDD
  estrictamente; no fue solicitado explícitamente en el spec
- Hacer commit tras cada tarea o grupo lógico de tareas
- Detenerse en cada checkpoint para validar la historia de forma independiente
- La migración del motor de aclaración (T004-T006) es un refactor de comportamiento preservado, no
  una reescritura de reglas de negocio — cualquier diferencia de comportamiento observable respecto
  a 001 detectada en T030 es una regresión, no un cambio de alcance aceptable
- Evitar: tareas vagas, conflictos de archivo simultáneos, dependencias cruzadas entre historias que
  rompan su independencia de prueba
