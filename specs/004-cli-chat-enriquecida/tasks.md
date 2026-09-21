---

description: "Task list template for feature implementation"
---

# Tasks: CLI Chat Enriquecida

**Input**: Design documents from `/specs/004-cli-chat-enriquecida/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Se incluyen tareas de pruebas unitarias, siguiendo el mismo criterio que 001/002/003:
`plan.md` (Technical Context → Testing) designa explícitamente `pytest` con
`tests/unit/test_console.py` como parte del diseño de esta funcionalidad.

**Organization**: Las tareas están agrupadas por historia de usuario. **Sin fase Foundational**:
`spec.md` documenta explícitamente que la Historia 2 depende de la Historia 1 ("depende de que ya
exista la diferenciación básica de la Historia 1") y la Historia 3 reutiliza la misma función que
crea la Historia 1 para distinguir errores — es una construcción incremental de un único módulo
(`presentation/console.py`) en orden de prioridad P1 → P2 → P3, no infraestructura compartida
construida antes para consumidores independientes (mismo patrón ya seguido por 002/003).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias entre sí)
- **[Story]**: A qué historia de usuario pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta de archivo exacta

## Path Conventions

- Proyecto único: `src/opssleuth/`, `tests/unit/` en la raíz del repositorio (ver `plan.md` →
  Project Structure). La mayoría de las tareas de implementación editan uno de dos archivos
  (`src/opssleuth/presentation/console.py`, nuevo; `src/opssleuth/cli.py`, existente) — de ahí las
  oportunidades de paralelismo limitadas (ver "Parallel Opportunities" más abajo).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Añadir la única dependencia nueva de esta spec (`rich`) y el esqueleto del paquete
que la confina.

- [X] T001 Añadir la dependencia `rich` en `pyproject.toml` (`uv add rich`) — única dependencia
  nueva de esta spec (`research.md`, "Nuevas dependencias").
- [X] T002 [P] Crear `src/opssleuth/presentation/__init__.py` (paquete nuevo, vacío salvo
  docstring de módulo indicando que es el único punto de integración con `rich` del proyecto,
  Principio II).

**Checkpoint**: Dependencia instalada; paquete `presentation/` listo para recibir código.

---

## Phase 2: User Story 1 - Diferenciar de un vistazo quién dijo qué (Priority: P1) 🎯 MVP

**Goal**: Toda entrada del usuario y toda respuesta del sistema lleva una etiqueta textual de rol
obligatoria (reforzada con color/estilo), delegada desde las dos funciones ya existentes que
concentran el 100% de la entrada/salida de la conversación (`_imprimir`/`_leer_entrada`), sin tocar
ningún otro punto de llamada de `cli.py`.

**Independent Test**: Iniciar un caso, completar 2-3 intercambios, y verificar que cada entrada del
usuario y cada respuesta del sistema lleva una etiqueta textual de rol distinta y consistente que
permite identificar su origen sin leer el contenido (Escenario 1 de `quickstart.md`).

### Implementation for User Story 1

- [X] T003 [US1] Implementar `mostrar_mensaje_sistema(texto: str, *, console: Console | None =
  None) -> None` en `src/opssleuth/presentation/console.py` (nuevo archivo): imprime `texto`
  precedido de una etiqueta textual de rol constante ("OpsSleuth"), reforzada con color/estilo vía
  `rich.console.Console` (usa una instancia de `Console` de módulo por defecto si `console` no se
  inyecta — permite inyectar un `Console(file=io.StringIO(), force_terminal=False)` en pruebas,
  `research.md` Decisión 7); en esta tarea el contenido se imprime como texto plano (el renderizado
  Markdown se añade en la Historia 2, T007); con docstring numpydoc completo (`Parameters`).
- [X] T004 [US1] Implementar `leer_entrada_usuario(prompt: str = "", *, console: Console | None =
  None) -> str` en `src/opssleuth/presentation/console.py` (extiende T003): si `prompt` no está
  vacío, lo muestra vía `mostrar_mensaje_sistema(prompt, console=console)` — unifica el patrón ya
  existente en `cli.py` donde la pregunta se pasa como argumento de `_leer_entrada`; a continuación
  muestra una etiqueta textual de rol constante ("Tú"), reforzada con color/estilo distinto al del
  sistema, y lee la línea con `input()` estándar (no `Console.input`, para preservar exactamente el
  valor devuelto por el mecanismo ya probado — `research.md`, Decisión 2); con docstring numpydoc
  completo (`Parameters`, `Returns`).
- [X] T005 [US1] Modificar `src/opssleuth/cli.py`: importar `leer_entrada_usuario` y
  `mostrar_mensaje_sistema` de `opssleuth.presentation.console`; `_imprimir(mensaje: str) -> None`
  delega en `mostrar_mensaje_sistema(mensaje)`; `_leer_entrada(prompt: str) -> str` delega en
  `leer_entrada_usuario(prompt)` — ninguna de las dos cambia de firma en esta tarea; actualizar el
  docstring del módulo (línea 1 de `cli.py`) para reflejar que la presentación ahora se delega en
  `presentation/console.py`.
- [X] T006 [P] [US1] Pruebas unitarias en `tests/unit/test_console.py` (nuevo): inyectar
  `Console(file=io.StringIO(), force_terminal=False)` a `mostrar_mensaje_sistema` y verificar que
  la salida capturada contiene la etiqueta "OpsSleuth"; inyectar el mismo mecanismo a
  `leer_entrada_usuario` (monkeypatcheando `builtins.input` para la lectura) y verificar que la
  salida capturada contiene la etiqueta "Tú", que ambas etiquetas son distintas entre sí, y que el
  valor devuelto coincide con lo que `input()` devolvió.

**Checkpoint**: En este punto, la Historia de Usuario 1 debe ser completamente funcional y probable
de forma independiente (Escenario 1 de `quickstart.md`). Ejecutar `uv run pytest
tests/unit/test_cli.py` y confirmar que las 87 pruebas existentes siguen pasando sin modificación
(`research.md`, Decisión 2).

---

## Phase 3: User Story 2 - Leer las respuestas del sistema con formato legible (Priority: P2)

**Goal**: El contenido de toda respuesta del sistema se renderiza con `rich.markdown.Markdown` en
vez de texto plano, mostrando listas y énfasis de forma legible sin símbolos de marcado crudos.

**Independent Test**: Completar una búsqueda de evidencia en logs que produzca una apreciación con
varios hallazgos, y verificar que el resultado se presenta con estructura legible (listas, énfasis)
en vez de mostrar el texto de marcado sin procesar (Escenario 2 de `quickstart.md`).

### Implementation for User Story 2

- [X] T007 [US2] Modificar `mostrar_mensaje_sistema` en `src/opssleuth/presentation/console.py`
  (extiende T003): en vez de imprimir `texto` como cadena plana, renderizarlo con
  `rich.markdown.Markdown(texto)` dentro del mismo bloque con la etiqueta de rol — aplicado
  uniformemente a cualquier texto, sin detectar de antemano si contiene marcado (`research.md`,
  Decisión 4); actualizar el docstring.
- [X] T008 [US2] Pruebas unitarias en `tests/unit/test_console.py` (extiende T006): verificar que
  un texto con marcado Markdown (p. ej. `"- item uno\n- item dos"` y `"texto con **dato clave**
  resaltado"`) se renderiza sin los símbolos `-`/`**` visibles como texto plano en la salida
  capturada; verificar que un texto de una sola línea sin marcado se sigue mostrando legible y sin
  alteraciones inesperadas (Acceptance Scenario 3 de la Historia 2).

**Checkpoint**: En este punto, las Historias de Usuario 1 y 2 deben funcionar juntas de forma
independiente (Escenario 2 de `quickstart.md`).

---

## Phase 4: User Story 3 - Reconocer cuándo el sistema está trabajando o hay un problema (Priority: P3)

**Goal**: Se muestra un indicador de actividad durante las llamadas al proveedor de modelo que ya
toman varios segundos en uso real, y los 2 mensajes de fallo de comunicación con el proveedor se
distinguen visualmente de una respuesta normal.

**Independent Test**: Iniciar una búsqueda de evidencia en logs y verificar que aparece una
indicación de actividad mientras se procesa; forzar un error de comunicación con el proveedor y
verificar que el mensaje de error se distingue visualmente de una respuesta normal (Escenarios 3 y
4 de `quickstart.md`).

### Implementation for User Story 3

- [X] T009 [US3] Implementar `mostrar_actividad(mensaje: str, *, console: Console | None = None)`
  (context manager) en `src/opssleuth/presentation/console.py`, basado en
  `rich.console.Console.status` — muestra `mensaje` con un indicador transitorio mientras el bloque
  `with` se ejecuta, se limpia automáticamente al salir; con docstring numpydoc completo.
- [X] T010 [US3] Añadir el parámetro `es_error: bool = False` a `mostrar_mensaje_sistema` en
  `src/opssleuth/presentation/console.py` (extiende T003/T007): cuando es `True`, aplica un
  color/estilo de advertencia además de la etiqueta de rol ya existente, distinto del estilo normal
  usado por defecto; actualizar el docstring (`Parameters`).
- [X] T011 [US3] Modificar `_imprimir` en `src/opssleuth/cli.py` para aceptar `es_error: bool =
  False` y propagarlo a `mostrar_mensaje_sistema(mensaje, es_error=es_error)`; cablear
  `es_error=True` en los 2 mensajes de fallo de proveedor ya existentes: en `_procesar_intake`
  ("No pude evaluar la descripción...") y en `_buscar_y_presentar_apreciacion_logs` ("No pude
  completar la búsqueda en los logs..."); el resto de los mensajes existentes mantienen el valor
  por defecto `es_error=False` (`research.md`, Decisión 6); actualizar los docstrings.
- [X] T012 [US3] Envolver con `mostrar_actividad(...)` (importado de
  `opssleuth.presentation.console`) las 4 llamadas de latencia perceptible en
  `src/opssleuth/cli.py` (`research.md`, Decisión 5): la llamada a `evaluar_descripcion` en
  `_procesar_intake`, en `_formular_y_registrar_aclaracion`, y en
  `_formular_y_registrar_aclaraciones_combinadas`; y la llamada a `buscar_evidencia` en
  `_buscar_y_presentar_apreciacion_logs`; actualizar los docstrings de las 4 funciones modificadas.
- [X] T013 [P] [US3] Pruebas unitarias en `tests/unit/test_console.py` (extiende T006/T008):
  verificar que `mostrar_actividad("mensaje")` se puede usar como context manager sin lanzar
  excepciones y que ejecuta su bloque `with`; verificar que
  `mostrar_mensaje_sistema(texto, es_error=True)` produce una salida capturada visualmente distinta
  (estilo/color distinto) de `mostrar_mensaje_sistema(texto, es_error=False)` para el mismo
  `texto`.
- [X] T014 [US3] Ejecutar la suite de pruebas existente completa (`uv run pytest tests/`) tras
  completar T009-T013, confirmando que las 87 pruebas de 001/002/003 siguen pasando **sin
  modificarlas** — cualquier fallo indica una regresión introducida por esta spec, no un cambio de
  alcance aceptable (FR-007).

**Checkpoint**: Las tres historias de usuario deben ser funcionales de forma independiente y en
conjunto (Escenarios 3 y 4 de `quickstart.md`).

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final que abarca las tres historias de usuario, incluidos los 2 escenarios
de `quickstart.md` que no pertenecen a ninguna historia individual (degradación sin color, no
regresión de 001/002/003).

- [X] T015 [P] Revisar que todas las funciones nuevas o modificadas en
  `src/opssleuth/presentation/console.py` y `src/opssleuth/cli.py` cuenten con docstrings numpydoc
  completos (`Parameters`, `Returns`), conforme al Principio III de la constitución.
- [X] T016 Ejecutar manualmente el Escenario 5 de `quickstart.md` (degradación sin soporte de
  color: `NO_COLOR=1` o salida redirigida a un archivo) contra un proveedor real, confirmando que
  la CLI no falla y que la etiqueta textual de rol sigue apareciendo sin depender de color
  (FR-006/SC-003).
- [X] T017 Ejecutar manualmente el Escenario 6 de `quickstart.md` (no regresión): repetir los
  escenarios de `specs/001-recepcion-incidencia/quickstart.md`,
  `specs/002-busqueda-logs/quickstart.md` y `specs/003-conversacion-adaptativa/quickstart.md`,
  confirmando comportamiento conversacional idéntico (SC-004).
- [X] T018 Actualizar `specs/ESTADO_SPECS.md` (fila 004 → ✅ Implementada, con el conteo final de
  tareas/pruebas) una vez completada la implementación — mismo criterio ya seguido por 001/002/003.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciarse de inmediato.
- **User Story 1 (Phase 2)**: Depende de Setup (necesita `rich` instalado y el paquete
  `presentation/` creado).
- **User Story 2 (Phase 3)**: Depende de User Story 1 — extiende directamente
  `mostrar_mensaje_sistema`, creada en T003. Documentado explícitamente como dependencia en
  `spec.md` (Historia 2, "Why this priority").
- **User Story 3 (Phase 4)**: Depende de User Story 1 (extiende `mostrar_mensaje_sistema` y usa la
  misma infraestructura de `Console`); no depende funcionalmente de User Story 2 (el indicador de
  actividad y la distinción de error son ortogonales al renderizado Markdown), pero se implementa
  después de ella por prioridad (P1 → P2 → P3) y porque ambas modifican el mismo archivo
  (`presentation/console.py`) — implementarlas en paralelo arriesgaría conflictos de edición
  simultánea, no una dependencia real de datos o comportamiento (mismo criterio ya aplicado en
  `003-conversacion-adaptativa/tasks.md`).
- **Polish (Phase 5)**: Depende de que las tres historias de usuario estén completas.

### Within Each User Story

- US1: T003 (mensaje del sistema) precede a T004 (la usa para mostrar el `prompt`); T003 y T004
  preceden a T005 (los delega desde `cli.py`); T006 depende de T003 y T004, pero no de T005 (puede
  ejecutarse en paralelo con ella).
- US2: T007 (extiende T003) precede a T008 (la prueba).
- US3: T009 y T010 son independientes entre sí (funciones/parámetros distintos del mismo archivo);
  T011 depende de T010 (usa el parámetro `es_error`); T012 depende de T009 (usa
  `mostrar_actividad`); T013 depende de T009 y T010, pero no de T011/T012 (puede ejecutarse en
  paralelo con ellas); T014 depende de que T009-T013 estén completas.

### Parallel Opportunities

- T001 y T002 (Setup) no tienen dependencia entre sí — pueden ejecutarse en paralelo.
- T005 y T006 (US1) pueden ejecutarse en paralelo una vez completos T003 y T004 (archivos
  distintos: `cli.py` vs. `tests/unit/test_console.py`).
- T013 (US3, pruebas) puede ejecutarse en paralelo con T011/T012 (US3, cableado en `cli.py`) una
  vez completos T009 y T010 — archivos distintos.
- **Fuera de estos casos, casi ninguna otra oportunidad de paralelismo real**: la mayoría de las
  tareas de implementación editan uno de dos archivos compartidos
  (`presentation/console.py`, `cli.py`) de forma incremental a través de las 3 historias — mismo
  patrón y misma limitación ya documentados en `003-conversacion-adaptativa/tasks.md`.
- T015 (Polish, revisión de docstrings) puede ejecutarse en paralelo con la preparación de T016;
  T018 depende de que T014, T016 y T017 ya hayan confirmado que todo funciona.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup (T001-T002).
2. Completar Phase 2: User Story 1 (T003-T006).
3. **DETENER Y VALIDAR**: Probar la Historia 1 de forma independiente contra `quickstart.md`
   (Escenario 1), y confirmar que `uv run pytest tests/unit/test_cli.py` sigue en 87/87 sin
   modificar ningún test existente.
4. Desplegar/demostrar si está listo — ya resuelve el problema concreto planteado en `spec.md`
   ("hoy la conversación se imprime como texto corrido, sin ninguna señal visual").

### Incremental Delivery

1. Setup completo → base lista.
2. Añadir User Story 1 (Phase 2) → probar de forma independiente → demo (MVP).
3. Añadir User Story 2 (Phase 3) → probar de forma independiente → demo.
4. Añadir User Story 3 (Phase 4) → probar de forma independiente → demo.
5. Phase 5 (Polish) cierra la spec, incluida la verificación de no regresión sobre 001/002/003.

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí — ver "Parallel Opportunities" arriba sobre
  por qué esta spec tiene oportunidades de paralelismo limitadas.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Confirmar que las pruebas fallan antes de implementar solo aplica si se decide seguir TDD
  estrictamente; no fue solicitado explícitamente en el spec (mismo criterio que 001/002/003).
- Hacer commit tras cada tarea o grupo lógico de tareas.
- Detenerse en cada checkpoint para validar la historia de forma independiente.
- Dada la dependencia secuencial documentada en `spec.md` entre las historias (Historia 2 depende
  explícitamente de la Historia 1) y el riesgo de conflictos de edición sobre los mismos 2
  archivos, no se recomienda desarrollo en paralelo por historia con múltiples desarrolladores en
  esta funcionalidad.
- Evitar: tareas vagas, conflictos de archivo simultáneos (particularmente relevante en esta spec,
  ver "Parallel Opportunities"), dependencias cruzadas entre historias que rompan su independencia
  de prueba.
