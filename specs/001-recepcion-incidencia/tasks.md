---

description: "Task list template for feature implementation"
---

# Tasks: Recepción de Incidencia

**Input**: Design documents from `/specs/001-recepcion-incidencia/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Se incluyen tareas de pruebas unitarias, ya que `plan.md` (Technical Context → Testing) y la estructura de proyecto definida allí ya designan explícitamente archivos `tests/unit/*.py` con `pytest` como parte del diseño de esta funcionalidad.

**Organization**: Las tareas están agrupadas por historia de usuario para permitir implementación y prueba independientes de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias entre sí)
- **[Story]**: A qué historia de usuario pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta de archivo exacta

## Path Conventions

- Proyecto único: `src/opssleuth/`, `tests/unit/` en la raíz del repositorio (ver `plan.md` → Project Structure)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto y dependencias

- [X] T001 Añadir dependencias del proyecto (`anthropic`, `ollama`, `pydantic`, y `pytest` como dependencia de desarrollo) en `pyproject.toml`
- [X] T002 [P] Crear el esqueleto de paquetes Python: `src/opssleuth/__init__.py`, `src/opssleuth/domain/__init__.py`, `src/opssleuth/clarification/__init__.py`
- [X] T003 [P] Configurar `pytest` en `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) y crear `tests/unit/__init__.py`

**Checkpoint**: Estructura de paquetes lista; `pytest` ejecutable desde la raíz del repositorio.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entidades de dominio compartidas por las tres historias de usuario

**⚠️ CRITICAL**: Ninguna historia de usuario puede implementarse antes de completar esta fase

- [X] T004 Implementar las entidades de dominio `Caso`, `DescripcionProblema`, `CampoExtraido` y `Aclaracion` en `src/opssleuth/domain/case.py`, según `data-model.md` (campos, reglas de validación, transiciones de `estado_informacion`/`estado_caso`, y en `Aclaracion` los campos `campo_objetivo` con valor `"problema_principal"` y `contradice_descripcion_original`), con docstrings numpydoc en cada clase y método público (Principio III de la constitución)
- [X] T005 [P] Pruebas unitarias de las reglas de dominio de `Caso` (transiciones de estado, validación de descripción no vacía) en `tests/unit/test_case.py`

**Checkpoint**: Entidades de dominio listas y probadas — la implementación de las historias de usuario puede comenzar.

---

## Phase 3: User Story 1 - Registrar la descripción inicial del problema (Priority: P1) 🎯 MVP

**Goal**: Al iniciar un caso, el sistema solicita la descripción del problema, la registra y confirma su recepción, gestionando el ciclo de vida básico del caso (un caso activo a la vez, casos secuenciales).

**Independent Test**: Iniciar un caso nuevo y verificar que el sistema solicita explícitamente la descripción del problema antes de continuar, que dicha descripción queda registrada asociada al caso una vez el usuario la envía, y que una descripción vacía es rechazada.

### Implementation for User Story 1

- [X] T006 [US1] Implementar el bucle principal de la CLI (`main()`, ejecutable vía `python -m opssleuth.cli`) en `src/opssleuth/cli.py`, con docstring numpydoc
- [X] T007 [US1] Implementar la solicitud y validación de la descripción inicial en `src/opssleuth/cli.py`: solicita la descripción al iniciar el caso (FR-001) y rechaza contenido vacío o sin contenido interpretable, volviendo a solicitarla (FR-011)
- [X] T008 [US1] Implementar el registro y la confirmación de la descripción inicial en `src/opssleuth/cli.py`: guarda el texto recibido en `Caso.descripcion_inicial` (FR-002) y confirma al usuario que fue recibida (FR-003)
- [X] T009 [US1] Implementar el reconocimiento de un caso ya iniciado en `src/opssleuth/cli.py`: si el flujo de intake se reinvoca con un caso activo que ya tiene descripción registrada, no la vuelve a solicitar desde cero (Acceptance Scenario 3 de US1)
- [X] T010 [US1] Implementar la finalización de un caso y el inicio de un caso nuevo secuencial en `src/opssleuth/cli.py`: tras finalizar un caso, permite abrir uno nuevo en la misma conversación solicitando de nuevo la descripción, con contexto separado del caso anterior (FR-013)
- [X] T011 [US1] Implementar el bloqueo de casos en paralelo en `src/opssleuth/cli.py`: si el usuario intenta iniciar un caso adicional mientras uno sigue activo, informa que hay un caso en curso y solicita confirmación antes de finalizarlo y abrir uno nuevo (FR-014)

**Checkpoint**: En este punto, la Historia de Usuario 1 debe ser completamente funcional y probable de forma independiente (escenarios 1, 4, 5 y edge case de descripción vacía en `quickstart.md`).

---

## Phase 4: User Story 2 - Mantener el contexto del caso disponible durante toda la conversación (Priority: P2)

**Goal**: El sistema conserva la descripción original y todo lo aportado sobre el caso a lo largo de la conversación, y puede referenciarlo consistentemente en cualquier momento.

**Independent Test**: Iniciar un caso, registrar una descripción, sostener varios intercambios adicionales sin repetir la descripción original, y verificar que el sistema sigue pudiendo referirse correctamente al problema original en cualquier punto de la conversación.

### Implementation for User Story 2

- [X] T012 [US2] Implementar la acumulación de contexto conversacional en `Caso.mensajes` (y, cuando aplique, `Caso.aclaraciones`) en `src/opssleuth/cli.py` y `src/opssleuth/domain/case.py`, sin perder la descripción original al incorporar información adicional (FR-004)
- [X] T013 [US2] Implementar un resumen determinista del caso (p. ej. método `Caso.resumen()`) en `src/opssleuth/domain/case.py`, que compila la descripción original y las aclaraciones registradas en una respuesta consistente, y exponerlo en `src/opssleuth/cli.py` cuando el usuario solicita que el sistema recuerde o resuma el problema (FR-005)
- [X] T014 [P] [US2] Pruebas unitarias del resumen determinista y de la acumulación de contexto en `tests/unit/test_case.py`

**Checkpoint**: En este punto, las Historias de Usuario 1 y 2 deben funcionar juntas de forma independiente (escenario 2 de `quickstart.md`).

---

## Phase 5: User Story 3 - Solicitar aclaraciones ante descripciones ambiguas (Priority: P3)

**Goal**: Cuando la descripción (o una aclaración previa) no cubre los 3 campos mínimos de diagnóstico, el sistema formula preguntas puntuales en lugar de continuar con información insuficiente.

**Independent Test**: Enviar una descripción deliberadamente vaga o incompleta (p. ej. "no funciona") y verificar que el sistema responde con preguntas específicas orientadas a completar los datos faltantes; al responderlas, el caso queda con una descripción suficientemente clara.

### Implementation for User Story 3

- [X] T015 [US3] Implementar el contrato `ClarificationEngine` (Protocol) y los tipos `EvaluacionDescripcion` / `ClarificationEngineError` en `src/opssleuth/clarification/engine.py`, según `contracts/clarification_engine.md` (incluyendo los campos `contradiccion` y `multiples_problemas` de `EvaluacionDescripcion`, y dejando `generar_preguntas` como transformación determinista sin llamada adicional al modelo — Regla 5 del contrato) y `contracts/evaluacion_schema.json`, con docstrings numpydoc
- [X] T016 [P] [US3] Implementar `ClaudeClarificationEngine` en `src/opssleuth/clarification/claude_engine.py`: adaptador sobre `anthropic.Anthropic().messages.parse(...)` con `output_config.format` según `evaluacion_schema.json`, modelo `claude-sonnet-5`, reenviando el historial de conversación como `messages` (ver `research.md`, Decisiones 1 y 3); DEBE capturar `anthropic.APIError` y `anthropic.APIConnectionError` y relanzarlas como `ClarificationEngineError` conservando la excepción original como `__cause__` (Regla 4 del contrato)
- [X] T017 [P] [US3] Implementar `OllamaClarificationEngine` en `src/opssleuth/clarification/ollama_engine.py`: adaptador sobre el cliente `ollama` (`ollama.chat(model=..., messages=..., format=...)`) contra una instancia local, modelo configurable vía `OPSSLEUTH_OLLAMA_MODEL` (ver `research.md`, Decisión 4); DEBE capturar `ollama.ResponseError` y errores de conexión (p. ej. `ConnectionError` al no encontrar una instancia de Ollama accesible) y relanzarlos como `ClarificationEngineError` conservando la excepción original como `__cause__` (Regla 4 del contrato)
- [X] T018 [US3] Implementar `crear_motor_aclaracion()` en `src/opssleuth/clarification/factory.py`: selecciona `ClaudeClarificationEngine` u `OllamaClarificationEngine` según la variable de entorno `OPSSLEUTH_LLM_PROVIDER` (por defecto `claude`)
- [X] T019 [US3] Integrar la evaluación de la descripción inicial en el flujo de intake en `src/opssleuth/cli.py`: invocar `ClarificationEngine.evaluar` para poblar los 3 `CampoExtraido` de `DescripcionProblema` (FR-006) y capturar `evaluacion.multiples_problemas`
- [X] T020 [US3] Implementar la confirmación de "problema principal" en `src/opssleuth/cli.py`: si `evaluacion.multiples_problemas.detectado = true` sobre la descripción inicial, formular al usuario la pregunta correspondiente (`Aclaracion` con `campo_objetivo="problema_principal"`, listando `problemas_identificados`) y usar la respuesta para acotar cuál es el problema a investigar antes de continuar con la evaluación de los 3 campos (Edge Case "descripción extremadamente extensa con múltiples problemas mezclados", spec.md)
- [X] T021 [US3] Implementar la formulación de preguntas de aclaración estándar en `src/opssleuth/cli.py`: si algún campo evaluado tiene `presente=false`, invocar `generar_preguntas` (transformación determinista de `evaluacion.preguntas_sugeridas`, sin llamada adicional al modelo) y formularlas al usuario en lugar de continuar sin ellas (FR-007); si los 3 campos ya están presentes y no hay múltiples problemas pendientes de confirmar, no formular preguntas (FR-009)
- [X] T022 [US3] Implementar la incorporación de respuestas de aclaración en `src/opssleuth/cli.py` y `src/opssleuth/domain/case.py`: al recibir cada respuesta, invocar `ClarificationEngine.evaluar` sobre ella (con el contexto acumulado) para detectar contradicciones con la descripción original o aclaraciones previas; registrar la respuesta en `Caso.aclaraciones` (campo objetivo + respuesta), marcando `contradice_descripcion_original=true` cuando `evaluacion.contradiccion.detectada=true` y señalando la inconsistencia al usuario **sin descartar ninguno de los dos valores** (FR-008 + Edge Case "el usuario aporta información que contradice lo dicho en la descripción original", spec.md); marcar `estado_informacion = "completa"` cuando ya no falten campos
- [X] T023 [US3] Implementar el manejo de "no puedo aportar más información" en `src/opssleuth/cli.py`: si el usuario lo indica explícitamente durante una ronda de aclaraciones, marcar la(s) `Aclaracion` pendientes con `sin_confirmar = true`, dejar de insistir y continuar el caso con la información disponible (FR-010)
- [X] T024 [P] [US3] Pruebas unitarias de `ClaudeClarificationEngine` con el cliente `anthropic` mockeado en `tests/unit/test_claude_engine.py`: evaluación de campos presentes/ausentes, detección de `contradiccion`, detección de `multiples_problemas`, transformación determinista de `generar_preguntas` (sin llamada adicional al cliente mockeado), y propagación de `ClarificationEngineError` ante fallos de `anthropic.APIError`/`anthropic.APIConnectionError`
- [X] T025 [P] [US3] Pruebas unitarias de `OllamaClarificationEngine` con el cliente `ollama` mockeado en `tests/unit/test_ollama_engine.py`: mismas coberturas que T024, incluyendo explícitamente la propagación de `ClarificationEngineError` ante fallos de `ollama.ResponseError`/errores de conexión

**Checkpoint**: Todas las historias de usuario deben ser funcionales de forma independiente (escenarios 3 y 3b de `quickstart.md`, más los edge cases de contradicción y múltiples problemas).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final que abarca todas las historias de usuario

- [X] T026 [P] Revisar que todas las clases y funciones nuevas en `src/opssleuth/` cuenten con docstrings numpydoc completos (Parameters, Returns, Raises), conforme al Principio III de la constitución
- [X] T027 Ejecutar manualmente los escenarios de validación de `quickstart.md` con ambos proveedores (`OPSSLEUTH_LLM_PROVIDER=claude` y `OPSSLEUTH_LLM_PROVIDER=ollama`), confirmando comportamiento observable idéntico, incluyendo los edge cases de contradicción y múltiples problemas — **Nota**: validado en vivo end-to-end contra Ollama (servidor local disponible en este entorno, modelo `qwen2.5:7b-instruct`): descripción vacía rechazada, descripción completa sin preguntas innecesarias, aclaraciones ante descripción ambigua, detección de contradicción, detección de múltiples problemas, resumen del caso, y ciclo de vida de casos secuenciales/bloqueo de casos en paralelo. El proveedor Claude no se pudo validar en vivo en este entorno (no hay `ANTHROPIC_API_KEY` ni perfil `ant auth login` configurados); queda cubierto por las 8 pruebas unitarias de T024 contra el mismo contrato.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciarse de inmediato
- **Foundational (Phase 2)**: Depende de que Setup esté completo — BLOQUEA todas las historias de usuario
- **User Story 1 (Phase 3)**: Depende de Foundational
- **User Story 2 (Phase 4)**: Depende de User Story 1 — reutiliza el flujo de intake y el `Caso` que US1 crea y confirma; el spec documenta esta dependencia explícitamente ("Depende de que exista una descripción inicial (US1)")
- **User Story 3 (Phase 5)**: Depende de User Story 2 — las aclaraciones se incorporan al mismo mecanismo de contexto (`Caso.mensajes`/`aclaraciones`) que US2 construye, tal como documenta el spec ("las aclaraciones se incorporan al mismo contexto que US2 mantiene")
- **Polish (Phase 6)**: Depende de que las tres historias de usuario estén completas

> A diferencia del patrón por defecto de historias independientes, en esta funcionalidad las
> tres historias tienen una dependencia secuencial genuina y documentada en `spec.md` (cada
> prioridad se apoya explícitamente en la anterior), por lo que se implementan en orden
> P1 → P2 → P3, no en paralelo.

### Within Each User Story

- Los métodos/entidades de dominio necesarios preceden a la lógica de la CLI que los usa
- El contrato `ClarificationEngine` (T015) precede a sus dos implementaciones (T016, T017), que a su vez preceden a `factory.py` (T018) y a su integración en la CLI (T019-T023)
- Dentro de la integración en la CLI: la evaluación de la descripción inicial (T019) precede a la confirmación de problema principal (T020), que precede a la formulación de preguntas estándar (T021)
- Las pruebas unitarias de un módulo se ejecutan después de implementar ese módulo (no hay TDD estricto solicitado en el spec)

### Parallel Opportunities

- T002 y T003 (Setup) pueden ejecutarse en paralelo
- T016 y T017 (US3: implementaciones Claude y Ollama) pueden ejecutarse en paralelo entre sí una vez completado T015 — son adaptadores independientes del mismo contrato
- T024 y T025 (US3: pruebas de cada adaptador) pueden ejecutarse en paralelo una vez existan T016/T017 respectivamente
- T026 (Polish) puede ejecutarse en paralelo con T027

---

## Parallel Example: User Story 3

```bash
# Una vez completado T015 (contrato ClarificationEngine), lanzar en paralelo:
Task: "Implementar ClaudeClarificationEngine en src/opssleuth/clarification/claude_engine.py"
Task: "Implementar OllamaClarificationEngine en src/opssleuth/clarification/ollama_engine.py"

# Una vez completados T016 y T017 respectivamente, lanzar en paralelo:
Task: "Pruebas unitarias de ClaudeClarificationEngine en tests/unit/test_claude_engine.py"
Task: "Pruebas unitarias de OllamaClarificationEngine en tests/unit/test_ollama_engine.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloquea todas las historias)
3. Completar Phase 3: User Story 1
4. **DETENER Y VALIDAR**: Probar la User Story 1 de forma independiente contra `quickstart.md` (escenarios 1, 4, 5 y edge case de descripción vacía)
5. Desplegar/demostrar si está listo

### Incremental Delivery

1. Setup + Foundational completos → base lista
2. Añadir User Story 1 → probar de forma independiente → demo (MVP)
3. Añadir User Story 2 → probar de forma independiente → demo
4. Añadir User Story 3 → probar de forma independiente → demo
5. Cada historia añade valor sin romper las anteriores

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí
- [Story] mapea cada tarea a su historia de usuario para trazabilidad
- Dada la dependencia secuencial documentada en el spec, no se recomienda desarrollo en
  paralelo por historia con múltiples desarrolladores en esta funcionalidad (a diferencia
  del patrón por defecto del template)
- Confirmar que las pruebas fallan antes de implementar solo aplica si se decide seguir TDD
  estrictamente; no fue solicitado explícitamente en el spec
- Hacer commit tras cada tarea o grupo lógico de tareas
- Detenerse en cada checkpoint para validar la historia de forma independiente
- Evitar: tareas vagas, conflictos de archivo simultáneos, dependencias cruzadas entre
  historias que rompan su independencia de prueba
