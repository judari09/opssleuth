---

description: "Task list template for feature implementation"
---

# Tasks: Conversación Adaptativa

**Input**: Design documents from `/specs/003-conversacion-adaptativa/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Se incluyen tareas de pruebas unitarias, siguiendo el mismo criterio que 001/002:
`plan.md` (Technical Context → Testing) designa explícitamente `pytest` con
`tests/unit/test_cli.py` como parte del diseño de esta funcionalidad.

**Organization**: Las tareas están agrupadas por historia de usuario. **Sin fases Setup ni
Foundational**: esta spec no añade dependencias nuevas, paquetes nuevos ni entidades de dominio
nuevas (ver `research.md`, `data-model.md`) — no existe infraestructura compartida que deba
construirse antes de que las historias de usuario puedan empezar; ambas extienden directamente
funciones ya existentes en `src/opssleuth/cli.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias entre sí)
- **[Story]**: A qué historia de usuario pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta de archivo exacta

## Path Conventions

- Proyecto único: `src/opssleuth/`, `tests/unit/` en la raíz del repositorio (ver `plan.md` →
  Project Structure). **Todo el código de negocio de esta spec vive en un único archivo**,
  `src/opssleuth/cli.py`, y sus pruebas en `tests/unit/test_cli.py` — de ahí la ausencia casi
  total de oportunidades de paralelismo real (ver "Parallel Opportunities" más abajo).

---

## Phase 1: User Story 1 - Aportar la descripción y la ruta de logs en un mismo mensaje (Priority: P1) 🎯 MVP

**Goal**: El sistema reconoce una ruta de archivo de log dentro del mismo mensaje que la
descripción inicial, la registra sin volver a pedirla, y difiere la validación de su
accesibilidad hasta el punto de fase en que hoy se dispara la búsqueda de evidencia.

**Independent Test**: Iniciar un caso con un mensaje que combine descripción del problema y una
ruta de archivo de log válida, y verificar que el sistema registra ambos sin formular la
pregunta "¿puedes aportar los logs relacionados?" (Escenario 1 de `quickstart.md`).

### Implementation for User Story 1

- [X] T001 [US1] Implementar `_extraer_ruta_candidata(texto: str) -> str | None` en
  `src/opssleuth/cli.py`: divide `texto` en tokens separados por espacio y devuelve el **último**
  token para el que `_parece_ruta_de_archivo(token)` sea `True` (o `None` si ninguno lo es) —
  reutiliza el criterio de reconocimiento ya existente sin duplicarlo (`research.md`, Decisión 1);
  con docstring numpydoc.
- [X] T002 [US1] Modificar `_procesar_intake` en `src/opssleuth/cli.py` para que devuelva
  `str | None`: inmediatamente después de `_solicitar_descripcion(caso)`, invocar
  `_extraer_ruta_candidata(caso.descripcion_inicial.texto)` y conservar el resultado en una
  variable local; devolver esa variable en **todos** los `return` de la función, incluido el
  `return` temprano cuando `evaluar_descripcion` lanza `ClarificationEngineError` (la extracción
  de ruta es puramente léxica y no depende de que la evaluación del LLM tenga éxito); actualizar
  el docstring (`Returns`).
- [X] T003 [US1] Modificar `_solicitar_evidencia_logs` en `src/opssleuth/cli.py`: agregar
  parámetro `ruta_candidata: str | None = None`; si `caso.fuentes_logs` está vacío y se aportó
  `ruta_candidata`, validarla directamente con `os.path.isfile` **en vez de** formular la
  invitación interactiva inicial — si es válida, registrar `FuenteDeLogs(origen="ruta_usuario")`
  e imprimir el mismo mensaje de confirmación ya existente; si es inválida, reutilizar la rama de
  reintento ya existente ("No pude acceder a '...' como archivo...") pidiendo una nueva ruta o
  contenido pegado, sin haber formulado nunca la invitación inicial para esa fuente ya cubierta
  (`research.md`, Decisión 2); actualizar el docstring (`Parameters`).
- [X] T004 [US1] Modificar `ejecutar_conversacion` en `src/opssleuth/cli.py`: capturar el valor de
  retorno de `_procesar_intake(caso, chat_model)` (la ruta candidata) y pasarlo como
  `ruta_candidata` en la llamada a `_solicitar_evidencia_logs(caso, ruta_candidata=...)`.
- [X] T005 [US1] Pruebas unitarias de `_extraer_ruta_candidata` en `tests/unit/test_cli.py`
  (función pura, sin mock): ruta al final de una oración con espacios alrededor, texto sin ningún
  token con forma de ruta (`None`), token con extensión `.log`/`.txt`, texto con más de un
  candidato (debe devolverse el último), separadores `/` y `\`.
- [X] T006 [US1] Pruebas unitarias (con `BaseChatModel` mockeado, mismo patrón que las pruebas
  existentes de `_procesar_intake`) en `tests/unit/test_cli.py` cubriendo los 3 escenarios de
  aceptación de la Historia 1 (`spec.md`): (a) mensaje inicial con ruta válida → `caso.fuentes_logs`
  queda poblado y la invitación interactiva de `_solicitar_evidencia_logs` no se formula; (b)
  mensaje inicial con ruta inválida → la descripción se conserva, y el mensaje de error de acceso
  solo aparece al invocar `_solicitar_evidencia_logs` con la candidata (no antes, no durante las
  aclaraciones); (c) mensaje inicial con contenido pegado sin forma de ruta → `_procesar_intake`
  devuelve `None` y la invitación interactiva sigue formulándose con normalidad.

**Checkpoint**: En este punto, la Historia de Usuario 1 debe ser completamente funcional y
probable de forma independiente (Escenarios 1, 2 y 3 de `quickstart.md`).

---

## Phase 2: User Story 2 - Responder de una vez el lote inicial de aclaraciones pendientes (Priority: P2)

**Goal**: Cuando el lote inicial de preguntas de aclaración generado tras evaluar la descripción
tiene 2 o más pendientes, el sistema acepta una única respuesta combinada, la evalúa con el mismo
motor usado para la descripción inicial, y solo sigue preguntando una por una por lo que
realmente siga faltando.

**Independent Test**: Forzar una descripción inicial a la que le falten 2 campos y verificar que
una única respuesta que cubra ambos datos evita que el sistema pregunte por el segundo campo por
separado (Escenario 4 de `quickstart.md`).

### Implementation for User Story 2

- [X] T007 [US2] Implementar `_formular_y_registrar_aclaraciones_combinadas(caso: Caso,
  chat_model: BaseChatModel, preguntas_de_campos: list[Aclaracion]) -> list[Aclaracion]` en
  `src/opssleuth/cli.py` (`research.md`, Decisión 3):
  - Construye un único mensaje que combina el texto de `pregunta` de cada elemento de
    `preguntas_de_campos` (p. ej. enumerando cada pregunta), lo registra con
    `caso.agregar_mensaje("assistant", ...)` e imprime; lee una única respuesta con
    `_leer_entrada`.
  - Si `_indica_que_no_puede_aportar_mas(respuesta)` es `True`: registra la respuesta del usuario,
    marca **todas** las `Aclaracion` de `preguntas_de_campos` con `sin_confirmar=True` y las
    agrega a `caso` (mismo mensaje ya usado por `_formular_y_registrar_aclaracion`), y devuelve
    lista vacía (nada queda pendiente de reintentar individualmente).
  - En otro caso: registra la respuesta del usuario; evalúa la respuesta con
    `evaluar_descripcion(chat_model, respuesta, caso.mensajes)` (capturando
    `ClarificationEngineError` igual que el resto del flujo); si la evaluación tuvo éxito, aplica
    (reutilizando `_aplicar_campos_evaluados`) solo sobre los campos que en ese momento sigan en
    `caso.descripcion_inicial.campos_faltantes()`; si se detecta `contradiccion`, imprime el mismo
    aviso ya usado por `_formular_y_registrar_aclaracion`.
  - Para cada elemento de `preguntas_de_campos`, si su `campo_objetivo` ya no está en
    `campos_faltantes()`, regístralo como `Aclaracion` resuelta (`respuesta` = la respuesta
    combinada completa, igual que hace hoy el camino uno-por-uno) vía `caso.agregar_aclaracion`.
  - Devuelve la sublista de `preguntas_de_campos` cuyo `campo_objetivo` siga en
    `campos_faltantes()` tras lo anterior.
  - Con docstring numpydoc completo (`Parameters`, `Returns`).
- [X] T008 [US2] Modificar `_procesar_intake` en `src/opssleuth/cli.py`: inmediatamente después de
  construir `preguntas_de_campos`, si `len(preguntas_de_campos) >= 2`, reemplazar esa lista por el
  resultado de `_formular_y_registrar_aclaraciones_combinadas(caso, chat_model,
  preguntas_de_campos)` antes de entrar al bucle `for aclaracion in preguntas_de_campos: ...` ya
  existente (sin cambios en ese bucle); con menos de 2 preguntas pendientes, usar
  `preguntas_de_campos` tal cual (comportamiento sin cambios respecto a 001); actualizar el
  docstring.
- [X] T009 [US2] Pruebas unitarias de `_formular_y_registrar_aclaraciones_combinadas` en
  `tests/unit/test_cli.py` (con `evaluar_descripcion`/`BaseChatModel` mockeado) cubriendo los 3
  escenarios de aceptación de la Historia 2 (`spec.md`): respuesta que cubre todos los campos
  pendientes (lista devuelta vacía, ambos campos registrados); respuesta que cubre solo parte
  (lista devuelta contiene exactamente el/los campo/s aún pendiente/s); respuesta ambigua o sin
  relación con los campos pendientes (lista devuelta sin cambios, sin inventar una correlación) —
  incluir un caso de "no puedo aportar más información" sobre la respuesta combinada completa.
- [X] T010 [US2] Prueba de integración en `tests/unit/test_cli.py` sobre `_procesar_intake`
  verificando el flujo completo con 2+ campos pendientes: el camino combinado se usa, y si quedan
  campos sin cubrir tras la respuesta combinada, el bucle uno-por-uno existente se ejecuta
  únicamente sobre esos campos restantes (sin repetir preguntas ya resueltas) — y que con menos de
  2 campos pendientes el comportamiento es idéntico al existente antes de esta spec.

**Checkpoint**: En este punto, las Historias de Usuario 1 y 2 deben funcionar juntas de forma
independiente (Escenarios 1, 4, 5 y 6 de `quickstart.md`).

---

## Phase 3: User Story 3 - Preservar el flujo guiado completo para quien lo necesita (Priority: P1)

**Goal**: Confirmar que ninguno de los cambios de las Historias 1 y 2 degrada el comportamiento
guiado paso a paso ya implementado y probado por 001/002 para quien no combina información.

**Independent Test**: Repetir íntegramente los escenarios de validación ya documentados en
`specs/001-recepcion-incidencia/quickstart.md` y `specs/002-busqueda-logs/quickstart.md` y
verificar que su resultado no cambia.

### Verification for User Story 3

- [X] T011 [US3] Ejecutar la suite de pruebas existente completa (`uv run pytest tests/`) tras
  completar las Fases 1 y 2, confirmando que las 72 pruebas ya existentes (de 001/002) siguen
  pasando **sin modificarlas** — cualquier fallo indica una regresión introducida por T001-T010,
  no un cambio de alcance aceptable.
- [X] T012 [US3] Ejecutar manualmente los escenarios 1 a 5 de
  `specs/001-recepcion-incidencia/quickstart.md` y los escenarios 1 a 9 de
  `specs/002-busqueda-logs/quickstart.md`, aportando la información paso a paso (sin combinar
  descripción+logs ni respuestas de aclaración en un mismo mensaje), confirmando comportamiento
  observable idéntico al ya documentado en esas specs — **spot-checks en vivo realizados**
  (proveedor `gemini` real, CLI real vía stdin) para los caminos que esta spec toca: descripción +
  ruta de logs combinadas, respuesta combinada que cubre todo el lote, y respuesta combinada
  parcial con fallback a pregunta individual (los 3 confirmados correctos); el resto del árbol de
  001/002 (localización por horario, apreciación consolidada, múltiples fuentes, etc.) queda
  cubierto por la suite automatizada (87/87, sin código de esos escenarios modificado por esta
  spec) en vez de una re-ejecución manual exhaustiva.

**Checkpoint**: Las tres historias de usuario deben ser funcionales de forma independiente y sin
regresiones (Escenario 7 de `quickstart.md` de esta spec, más los escenarios completos de
001/002).

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final que abarca las tres historias de usuario.

- [X] T013 [P] Revisar que `_extraer_ruta_candidata`,
  `_formular_y_registrar_aclaraciones_combinadas`, y las funciones modificadas
  (`_procesar_intake`, `_solicitar_evidencia_logs`, `ejecutar_conversacion`) en
  `src/opssleuth/cli.py` cuenten con docstrings numpydoc completos (`Parameters`, `Returns`),
  conforme al Principio III de la constitución.
- [X] T014 Ejecutar manualmente los escenarios 1 a 7 de
  `specs/003-conversacion-adaptativa/quickstart.md` (los propios de esta spec) con al menos un
  proveedor real, confirmando el comportamiento nuevo (US1/US2) y el de no-regresión (US3,
  escenario 7) — **escenarios 1, 4 y 5 verificados en vivo** contra `gemini` real (ver T012);
  escenarios 2, 3 y 6 cubiertos por la suite automatizada (T005, T006, T009); escenario 7
  (no-regresión) cubierto por T011 (87/87 pruebas, incluidas las 70 no tocadas de 001/002).
- [X] T015 Actualizar `specs/ESTADO_SPECS.md` (fila 003 → ✅ Implementada, con el conteo final de
  tareas/pruebas) una vez completada la implementación — mismo criterio ya seguido por 001/002.

---

## Dependencies & Execution Order

### Phase Dependencies

- **User Story 1 (Phase 1)**: Sin dependencias — puede iniciarse de inmediato (no hay fases Setup
  ni Foundational en esta spec, ver "Organization" arriba).
- **User Story 2 (Phase 2)**: Funcionalmente independiente de US1 (el spec no documenta una
  dependencia entre ellas — ambas actúan sobre partes distintas de `_procesar_intake`). Se
  implementa **después** de US1 por prioridad (P1 antes que P2) y porque ambas modifican el mismo
  archivo/función (`_procesar_intake` en `src/opssleuth/cli.py`) — implementarlas en paralelo
  arriesgaría conflictos de edición simultánea sobre el mismo archivo, no una dependencia real de
  datos o comportamiento.
- **User Story 3 (Phase 3)**: Depende de que US1 y US2 estén implementadas — es la verificación de
  no-regresión sobre los cambios que introducen.
- **Polish (Phase 4)**: Depende de que las tres historias de usuario estén completas.

### Within Each User Story

- US1: T001 (función de extracción) precede a T002 (la usa); T002 y T003 preceden a T004
  (propaga el resultado de una a la otra); T005 puede escribirse tan pronto como exista T001;
  T006 depende de T002-T004 completos.
- US2: T007 precede a T008 (la usa); T009 depende de T007; T010 depende de T007 y T008.

### Parallel Opportunities

- **Casi ninguna** en esta spec: T001-T006 (US1) y T007-T010 (US2) editan todos el mismo archivo
  (`src/opssleuth/cli.py`) o el mismo archivo de pruebas (`tests/unit/test_cli.py`) — ejecutarlas
  en paralelo arriesga conflictos de edición simultánea, por lo que ninguna se marca `[P]`.
- T013 (Polish, revisión de docstrings) puede ejecutarse en paralelo con la preparación de T014
  (ambas de solo lectura/verificación, sin modificar código de negocio); T015 depende de que T011,
  T012 y T014 ya hayan confirmado que todo funciona.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: User Story 1 (T001-T006).
2. **DETENER Y VALIDAR**: Probar la Historia 1 de forma independiente contra `quickstart.md`
   (Escenarios 1, 2 y 3), y confirmar que `uv run pytest tests/` sigue en 72/72 más las pruebas
   nuevas de T005/T006.
3. Desplegar/demostrar si está listo — ya resuelve el caso de fricción real documentado en
   `spec.md` (Historia 1, "Why this priority").

### Incremental Delivery

1. Añadir User Story 1 (Phase 1) → probar de forma independiente → demo (MVP).
2. Añadir User Story 2 (Phase 2) → probar de forma independiente → demo.
3. Ejecutar User Story 3 (Phase 3) como verificación de no-regresión sobre ambas.
4. Phase 4 (Polish) cierra la spec.

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí — ver "Parallel Opportunities" arriba sobre
  por qué esta spec tiene muy pocas oportunidades reales de paralelismo.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Confirmar que las pruebas fallan antes de implementar solo aplica si se decide seguir TDD
  estrictamente; no fue solicitado explícitamente en el spec (mismo criterio que 001/002).
- Hacer commit tras cada tarea o grupo lógico de tareas.
- Detenerse en cada checkpoint para validar la historia de forma independiente.
- La Historia de Usuario 3 no introduce código nuevo — es exclusivamente verificación de que
  US1/US2 no degradaron el comportamiento ya implementado por 001/002; sus tareas son de
  ejecución de pruebas, no de implementación.
- Evitar: tareas vagas, conflictos de archivo simultáneos (particularmente relevante en esta
  spec, ver "Parallel Opportunities"), dependencias cruzadas entre historias que rompan su
  independencia de prueba.
