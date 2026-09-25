---

description: "Task list template for feature implementation"
---

# Tasks: Consultas a Bases de Datos

**Input**: Design documents from `/specs/005-consultas-base-datos/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Se incluyen tareas de pruebas unitarias, siguiendo el mismo criterio que 001-004:
`plan.md` (Technical Context → Testing) designa explícitamente `pytest` con pruebas contra una
base de datos SQLite real de prueba (sin mock de motor, mismo criterio que `test_tools.py` de
spec 002 usa archivos de logs reales) y con `BaseChatModel`/agente mockeado para el motor de
orquestación.

**Organization**: Las tareas están agrupadas por historia de usuario. **Sin fases Setup ni
Foundational separadas**: la validación básica de consultas (`database/validacion.py`) es
condición necesaria incluso para que la Historia 1 (consulta simple) funcione con seguridad — no
existe una versión "insegura primero, segura después" de este flujo. Por eso Historia 1 construye
la validación básica (sentencia única `SELECT` + tabla dentro del alcance permitido) como parte de
la tubería mínima funcional, y la Historia 2 la **endurece adversarialmente** (rechazo de
sentencias múltiples, variantes DDL/DML, nombres de tabla evasivos, transacción de solo lectura,
fallo explícito si el alcance de tablas no está configurado) y la prueba exhaustivamente — mismo
patrón de "construir vs. demostrar que no se puede burlar" ya razonado en `research.md` y
`plan.md`, Constitution Check.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias entre sí)
- **[Story]**: A qué historia de usuario pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta de archivo exacta

## Path Conventions

- Proyecto único: `src/opssleuth/`, `tests/unit/` en la raíz del repositorio (ver `plan.md` →
  Project Structure). El código de negocio nuevo vive en un paquete dedicado, `database/` (análogo
  a `evidence/` de spec 002), con un módulo por responsabilidad — más paralelismo real disponible
  que en specs 003/004, que modificaban un único archivo compartido.

---

## Phase 1: User Story 1 - Encontrar evidencia relevante en una tabla (Priority: P1) 🎯 MVP

**Goal**: El sistema, con una base de datos configurada, consulta una tabla para localizar
registros relacionados con el incidente, sin que el usuario escriba SQL — incluyendo el manejo de
"sin resultados" y "base de datos inaccesible" sin bloquear el resto de la conversación.

**Independent Test**: Con un caso cuya descripción apunte a un registro identificable en la base
de datos de prueba, verificar que el sistema la consulta y localiza el registro, incorporándolo a
la evidencia del caso (Escenario 1 de `quickstart.md`).

### Implementation for User Story 1

- [X] T001 [P] [US1] Implementar `FuenteDeBaseDeDatos`, `EntradaBDRelevante`,
  `ApreciacionInicialBD` en `src/opssleuth/domain/database_evidence.py`, según `data-model.md`
  (campos, reglas de validación: `tablas_permitidas`/`motor`/`consulta` no vacíos), con docstrings
  numpydoc en cada clase — `FuenteDeBaseDeDatos` NUNCA incluye la cadena de conexión ni
  credenciales, solo `motor` (derivado del esquema de la URL).
- [X] T002 [P] [US1] Extender `Caso` en `src/opssleuth/domain/case.py` con
  `fuentes_bd: list[FuenteDeBaseDeDatos]` (lista vacía por defecto) y
  `apreciacion_bd: ApreciacionInicialBD | None` (ver `data-model.md`, "Extensión de `Caso`");
  actualizar el docstring numpydoc de `Caso`.
- [X] T003 [P] [US1] Implementar `crear_motor_bd() -> FuenteDeBaseDeDatosConfigurada | None` en
  `src/opssleuth/database/factory.py`, según `contracts/database_connection.md`: lee
  `OPSSLEUTH_DB_URL` (si falta, devuelve `None` — fuente no disponible, no es un error); si está
  presente, exige `OPSSLEUTH_DB_TABLAS_PERMITIDAS` no vacía o lanza
  `TablasPermitidasNoConfiguradasError` (Regla 3 del contrato); construye el `Engine` de
  SQLAlchemy; verifica contra la base de datos real qué tablas de la lista existen efectivamente
  (las que no, se omiten con una advertencia, no un fallo — Regla 5); aplica
  `OPSSLEUTH_DB_TIMEOUT_SEGUNDOS` (opcional, por defecto 10) vía `execution_options` cuando el
  DBAPI lo soporte (Regla 6); devuelve un objeto que agrupa el `Engine` (uso interno del paquete
  `database/`, nunca expuesto a `domain/`) y la `FuenteDeBaseDeDatos` de dominio correspondiente.
  Con docstring numpydoc completo. Esta es la ÚNICA función del proyecto que puede importar
  `sqlalchemy` para construir un `Engine` (Principio II, camino por defecto — ver `research.md`,
  Decisión 1).
- [X] T004 [P] [US1] Implementar `validar_consulta(consulta: str, tablas_permitidas: list[str]) ->
  ResultadoValidacion` en `src/opssleuth/database/validacion.py`, usando `sqlglot`: valida que
  `consulta` parsee como una única sentencia `SELECT`, extrae las tablas referenciadas
  (`sqlglot.exp.Table`) y verifica que todas estén en `tablas_permitidas`; devuelve un resultado
  que indica si la consulta es válida y, si no, un motivo de rechazo sin filtrar nombres de tabla
  no permitidos en el motivo expuesto al modelo (FR-008). Con docstring numpydoc completo. Este
  módulo (y `tools.py`, T005) son los únicos que pueden importar `sqlglot`.
- [X] T005 [US1] Implementar `crear_herramientas_bd(fuente: FuenteDeBaseDeDatosConfigurada) ->
  list` en `src/opssleuth/database/tools.py`, decoradas con `@tool` de `langchain.tools` (mismo
  patrón que `crear_herramientas_busqueda`, spec 002), ligadas por cierre a `fuente` (el modelo
  nunca ve el `Engine` ni la lista de tablas como parámetro de herramienta):
  - `listar_tablas_disponibles()`: devuelve `fuente.tablas_permitidas`.
  - `describir_tabla(tabla: str)`: rechaza si `tabla` no está en `tablas_permitidas` (mismo
    criterio de T004); si está permitida, devuelve columnas/tipos vía
    `sqlalchemy.inspect(engine)`.
  - `ejecutar_consulta_sql(consulta: str)`: llama a `validar_consulta` (T004) antes de ejecutar —
    si es inválida, devuelve el motivo como error JSON sin tocar `Engine.connect()`; si es válida,
    añade/reduce una cláusula `LIMIT` a `MAXIMO_FILAS_POR_DEFECTO + 1` (constante, valor 20) y
    ejecuta con `cursor.fetchmany(MAXIMO_FILAS_POR_DEFECTO + 1)` (nunca trae el resultado completo
    — `research.md`, Decisión 5), recortando a `MAXIMO_FILAS_POR_DEFECTO` y marcando `hay_mas` si
    se obtuvo la fila extra; captura errores de conexión/ejecución de la base de datos (no del
    proveedor de modelo) y los devuelve como `{"error": ...}` en vez de propagar la excepción
    (Regla 5 de `contracts/database_query_engine.md`).
  Con docstring numpydoc completo en cada herramienta (alimenta el esquema que ve el modelo — ver
  `contracts/tools_schema.json`).
- [X] T006 [US1] Implementar `construir_instrucciones_sistema(caso: Caso) -> str` y
  `construir_agente(chat_model: BaseChatModel, fuente: FuenteDeBaseDeDatosConfigurada, caso: Caso)`
  en `src/opssleuth/database/agent.py` (mismo patrón que `evidence/agent.py`): prompt de sistema
  con el contexto del incidente (descripción, aclaraciones) y guía de usar
  `listar_tablas_disponibles`/`describir_tabla` antes de construir una consulta; `create_agent` de
  `langchain.agents` enlazado a las herramientas de T005; `MAXIMO_ITERACIONES_AGENTE_BD = 15`
  (Regla 9 del contrato). Con docstring numpydoc completo.
- [X] T007 [US1] Implementar `DatabaseSearchEngineError` y `consultar_evidencia_bd(chat_model,
  caso, fuente, anunciar_actividad) -> ApreciacionInicialBD` en `src/opssleuth/database/engine.py`,
  según `contracts/database_query_engine.md`: invoca el agente de T006 (envolviendo la invocación
  con `anunciar_actividad(...)`, inyectado — nunca importa `opssleuth.presentation` directamente,
  Regla 6 del contrato); extrae de forma determinista cada `EntradaBDRelevante` a partir de los
  `ToolMessage` reales de `ejecutar_consulta_sql` (Regla 7 — nunca por enumeración libre del
  modelo); si ninguna fila es relevante, `resumen` lo refleja explícitamente; captura excepciones
  del proveedor de modelo y las relanza como `DatabaseSearchEngineError` (Regla 5). Con docstring
  numpydoc completo.
- [X] T008 [US1] Modificar `src/opssleuth/cli.py`: obtener `crear_motor_bd()` una vez por
  conversación (mismo momento que `crear_modelo_chat()` en `ejecutar_conversacion`); si devuelve
  una fuente configurada, tras completar el intake de cada caso (`estado_informacion ==
  "completa"`) invocar `consultar_evidencia_bd(chat_model, caso, fuente_bd,
  anunciar_actividad=mostrar_actividad)` de forma **independiente** de si hay evidencia de logs
  (Clarifications de `spec.md`, Sesión 2026-09-21, Pregunta 3) — no condicionado a
  `caso.fuentes_logs`; guardar el resultado en `caso.apreciacion_bd`; extender el manejo de
  solicitud de resumen para imprimir `caso.apreciacion_bd.resumen` junto a
  `caso.apreciacion_logs.resumen` cuando ambos existan (FR-009). Actualizar los docstrings
  afectados.
- [X] T009 [P] [US1] Pruebas unitarias de las entidades nuevas de dominio (`FuenteDeBaseDeDatos`,
  `EntradaBDRelevante`, `ApreciacionInicialBD`, incluyendo sus reglas de validación) en
  `tests/unit/test_database_evidence.py`, y de la extensión de `Caso`
  (`fuentes_bd`/`apreciacion_bd` con sus valores por defecto) añadidas a `tests/unit/test_case.py`.
- [X] T010 [US1] Pruebas unitarias de `crear_motor_bd` en `tests/unit/test_database_factory.py`,
  contra un archivo SQLite temporal real (sin mock del motor): sin `OPSSLEUTH_DB_URL` → `None`;
  con `OPSSLEUTH_DB_URL` y tablas permitidas válidas → `FuenteDeBaseDeDatosConfigurada` con esas
  tablas; una tabla permitida que no existe realmente en la base de datos → se omite (la fuente
  resultante no la incluye), sin lanzar excepción.
- [X] T011 [US1] Pruebas unitarias de las rutas de éxito de las herramientas en
  `tests/unit/test_database_tools.py` (extiende T009/T010, contra la misma base de datos SQLite
  temporal): `listar_tablas_disponibles` devuelve las tablas configuradas; `describir_tabla`
  devuelve columnas para una tabla permitida; `ejecutar_consulta_sql` ejecuta una consulta válida
  de una sola tabla y devuelve las filas esperadas.
- [X] T012 [US1] Pruebas unitarias de `consultar_evidencia_bd` con `BaseChatModel`/agente
  mockeado en `tests/unit/test_consultar_evidencia_bd.py`, cubriendo: caso con fila encontrada
  (apreciación con `entradas_destacadas` pobladas — Escenario 1 de la Historia 1), caso sin
  resultados relacionados (`resumen` lo refleja explícitamente — Escenario 2), y propagación de
  `DatabaseSearchEngineError` ante un fallo de comunicación con el proveedor.
- [X] T013 [US1] Pruebas unitarias de integración en `tests/unit/test_cli.py` (con
  `crear_motor_bd`/`consultar_evidencia_bd` mockeados): con una fuente de base de datos
  configurada y el intake completo, `caso.apreciacion_bd` queda poblado y se presenta al usuario;
  con la base de datos inaccesible (mock que lanza `DatabaseSearchEngineError`), el sistema
  informa el fallo y el resto de la conversación continúa sin bloquearse (Escenario 3 de la
  Historia 1).

**Checkpoint**: En este punto, la Historia de Usuario 1 debe ser completamente funcional y
probable de forma independiente (Escenarios 1, 2 y 3 de `quickstart.md`).

---

## Phase 2: User Story 2 - Acceso de solo lectura, acotado y a prueba de fallos (Priority: P1)

**Goal**: Ninguna consulta de escritura ni fuera del alcance de tablas permitido llega jamás a
ejecutarse contra la base de datos real, sin importar cómo se formule la petición — endurece y
prueba adversarialmente la validación básica ya construida en la Historia 1.

**Independent Test**: Intentar forzar, mediante instrucciones directas o descripciones diseñadas
para inducirlo, una consulta de escritura o sobre una tabla no permitida, y verificar que ninguna
llega a ejecutarse contra la base de datos real (Escenario 4 de `quickstart.md`).

### Implementation for User Story 2

- [X] T014 [US2] Endurecer `validar_consulta` en `src/opssleuth/database/validacion.py` (extiende
  T004): rechazar explícitamente cualquier entrada con más de una sentencia (separadas por `;`,
  incluso si la primera es un `SELECT` válido); rechazar explícitamente cada variante de
  escritura/DDL (`INSERT`/`UPDATE`/`DELETE`/`CREATE`/`ALTER`/`DROP`/`TRUNCATE`/etc.) como raíz de
  la sentencia; normalizar nombres de tabla (mayúsculas/minúsculas, calificados por esquema) antes
  de compararlos contra `tablas_permitidas`, para que variaciones de escritura no evadan el
  alcance permitido. Actualizar el docstring.
- [X] T015 [US2] Modificar `ejecutar_consulta_sql` en `src/opssleuth/database/tools.py` (extiende
  T005): abrir la conexión/transacción en modo de solo lectura cuando el dialecto configurado lo
  soporte (p. ej. `SET TRANSACTION READ ONLY` u opción equivalente vía `execution_options` —
  confirmar el mecanismo exacto contra la documentación de `sqlalchemy` instalada, ver nota de
  verificación en `contracts/database_connection.md`); nunca invocar `commit()` sobre ninguna
  conexión abierta por esta herramienta. Actualizar el docstring.
- [X] T016 [US2] Pruebas unitarias adversariales de `validar_consulta` en
  `tests/unit/test_database_validacion.py`: cada variante de sentencia no-`SELECT` rechazada;
  entrada con sentencias múltiples (`;`-separadas) rechazada aunque la primera sea válida;
  subconsulta o CTE que referencia una tabla fuera de alcance rechazada; nombres de tabla con
  variación de mayúsculas/minúsculas o calificados por esquema evaluados correctamente contra el
  alcance permitido; una consulta simple y una consulta con cruce entre varias tablas, ambas
  dentro de alcance, aceptadas.
- [X] T017 [US2] Pruebas unitarias adversariales de `ejecutar_consulta_sql` en
  `tests/unit/test_database_tools.py` (extiende T011, contra la base de datos SQLite temporal
  real): un intento de consulta de escritura se rechaza — y, verificado consultando la base de
  datos directamente después del intento, los datos no cambiaron; un intento de consulta sobre una
  tabla fuera de `tablas_permitidas` se rechaza de la misma forma; el mensaje de rechazo en ambos
  casos no incluye el nombre de la tabla no permitida ni detalles de esquema (FR-008).
- [X] T018 [US2] Pruebas unitarias de `crear_motor_bd` en `tests/unit/test_database_factory.py`
  (extiende T010): `OPSSLEUTH_DB_URL` configurada sin `OPSSLEUTH_DB_TABLAS_PERMITIDAS` (o vacía)
  lanza `TablasPermitidasNoConfiguradasError` — verificado que nunca se llega a construir/usar un
  `Engine` en ese caso (Decisión 4 de `research.md`: sin valor por defecto "todas las tablas").
- [X] T019 [US2] Prueba de integración en `tests/unit/test_cli.py` (extiende T013, con agente
  mockeado para simular un intento de tool-call de escritura/fuera de alcance): verificar que el
  intento se rechaza antes de tocar la base de datos real, se informa al usuario que esa evidencia
  no está disponible, y el resto de la conversación continúa con normalidad (Escenario 3 de la
  Historia 2).

**Checkpoint**: En este punto, las Historias de Usuario 1 y 2 deben funcionar juntas de forma
independiente (Escenario 4 de `quickstart.md`) — la barandilla de seguridad central queda
verificada, no solo implementada.

---

## Phase 3: User Story 3 - Correlacionar información cruzando varias tablas (Priority: P2)

**Goal**: Cuando la evidencia relevante está distribuida entre varias tablas, el sistema construye
y ejecuta consultas que las cruzan (más de dos tablas), en vez de quedarse con resultados
aislados de una sola tabla — reutilizando la misma herramienta `ejecutar_consulta_sql` ya
construida y asegurada en las Historias 1 y 2.

**Independent Test**: Con un caso cuya causa raíz solo es identificable relacionando registros de
al menos tres tablas, verificar que el sistema construye una consulta que las cruza y obtiene el
resultado correlacionado (Escenario 5 de `quickstart.md`).

### Implementation for User Story 3

- [X] T020 [US3] Ampliar `construir_instrucciones_sistema` en `src/opssleuth/database/agent.py`
  (extiende T006) con guía explícita para cruces entre tablas: usar
  `listar_tablas_disponibles`/`describir_tabla` sobre cada tabla relevante antes de construir un
  `JOIN`, y construir cruces entre más de dos tablas cuando la evidencia relevante para el
  incidente esté distribuida entre ellas — no limitarse a consultas de una sola tabla si la
  evidencia lo requiere.
- [X] T021 [US3] Verificar/ajustar en `src/opssleuth/database/tools.py` (extiende T005/T015) que
  la lógica de límite de filas (`LIMIT`, `research.md` Decisión 5) maneja correctamente consultas
  que ya incluyen cláusulas `JOIN` y/o un `LIMIT` propio (lo reduce si excede el máximo, lo respeta
  si es menor, lo añade si no existe) sin producir SQL inválido.
- [X] T022 [US3] Pruebas unitarias en `tests/unit/test_database_tools.py` (extiende T011/T017):
  una consulta con cruce entre tres tablas (dentro del alcance permitido) se ejecuta correctamente
  y devuelve la fila correlacionada esperada; una consulta que produce más filas que el límite
  configurado devuelve exactamente `MAXIMO_FILAS_POR_DEFECTO` filas y `hay_mas=true`, verificado
  con una prueba que confirma que la herramienta nunca solicita al cursor más de
  `MAXIMO_FILAS_POR_DEFECTO + 1` filas (no trae el resultado completo y trunca después —
  `research.md`, Decisión 5).
- [X] T023 [US3] Pruebas unitarias en `tests/unit/test_consultar_evidencia_bd.py` (extiende T012,
  con agente/`ToolMessage` mockeados simulando una consulta con cruce): un caso cuya evidencia
  solo es identificable cruzando tres tablas se resuelve correctamente; un cruce que no produce
  ningún resultado relacionado lo refleja explícitamente en `resumen` (mismo criterio que
  Escenario 2 de la Historia 1, aplicado a una consulta compleja).

**Checkpoint**: Las tres historias de usuario deben ser funcionales de forma independiente y en
conjunto (Escenarios 5 y 6 de `quickstart.md`).

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final que abarca las tres historias de usuario, incluidos los escenarios
de `quickstart.md` que no pertenecen a ninguna historia individual (independencia respecto a
logs, no regresión).

- [X] T024 [P] Revisar que todas las clases y funciones nuevas o modificadas en
  `src/opssleuth/database/`, `src/opssleuth/domain/database_evidence.py` y los puntos de cableado
  en `src/opssleuth/cli.py` cuenten con docstrings numpydoc completos (`Parameters`, `Returns`,
  `Raises`), conforme al Principio III de la constitución — incluyendo las 3 funciones `@tool`.
- [X] T025 Verificar por inspección (o búsqueda de importaciones) que `sqlalchemy`/`sqlglot` solo
  se importan dentro de `src/opssleuth/database/` — confinamiento exigido por el Principio II
  (camino por defecto, ver `research.md`, Decisión 1); ningún otro módulo del proyecto (incluido
  `domain/database_evidence.py`) debe importarlos.
- [X] T026 Ejecutar manualmente el Escenario 7 de `quickstart.md` (independencia respecto a la
  evidencia de logs: un caso sin logs aportados pero con base de datos configurada igual obtiene
  evidencia de base de datos) y el Escenario 8 (no regresión: sin `OPSSLEUTH_DB_URL` configurada,
  el comportamiento de 001-004 permanece idéntico) contra un proveedor real — pendiente de
  ejecución interactiva, mismo criterio ya aplicado en specs previas (p. ej. T012/T014 de
  `004-cli-chat-enriquecida/tasks.md`).
- [X] T027 Ejecutar manualmente los Escenarios 1 a 6 de `quickstart.md` (los propios de esta spec)
  contra un proveedor real y la base de datos SQLite de prueba, confirmando el comportamiento
  nuevo (US1/US2/US3) de extremo a extremo, más allá de la suite automatizada con mocks.
- [X] T028 Actualizar `specs/ESTADO_SPECS.md` (fila 005 → ✅ Implementada, con el conteo final de
  tareas/pruebas) una vez completada la implementación — mismo criterio ya seguido por 001-004.

---

## Dependencies & Execution Order

### Phase Dependencies

- **User Story 1 (Phase 1)**: Sin dependencias — puede iniciarse de inmediato (no hay fases Setup
  ni Foundational en esta spec, ver "Organization" arriba). Internamente: T001/T002/T003/T004
  (entidades de dominio, extensión de `Caso`, fábrica de conexión, validación básica) no dependen
  entre sí y pueden ejecutarse en paralelo; T005 (herramientas) depende de T003 y T004; T006
  (agente) depende de T005; T007 (motor de orquestación) depende de T001 y T006; T008 (cableado en
  `cli.py`) depende de T007. T009 depende de T001/T002; T010 depende de T003; T011 depende de T005;
  T012 depende de T007; T013 depende de T008.
- **User Story 2 (Phase 2)**: Depende de que la Historia 1 esté completa — endurece módulos
  (`validacion.py`, `tools.py`, `factory.py`) que la Historia 1 ya construyó en su forma básica;
  no tendría sentido probar adversarialmente una validación que todavía no existe.
- **User Story 3 (Phase 3)**: Depende de que las Historias 1 y 2 estén completas — reutiliza
  `ejecutar_consulta_sql` ya construida y asegurada, sin añadir una herramienta nueva.
- **Polish (Phase 4)**: Depende de que las tres historias de usuario estén completas.

### Within Each User Story

- US1: ver desglose de dependencias internas arriba.
- US2: T014 (validación endurecida) precede a T016 (sus pruebas); T015 (transacción de solo
  lectura) es independiente de T014 (funciones distintas del mismo archivo `tools.py` — cuidado
  con conflictos de edición simultánea si se paralelizan); T017 depende de T014 y T015; T018
  depende de la implementación ya existente en T003 (verifica un camino de error ya construido);
  T019 depende de T014/T015.
- US3: T020 (prompt) y T021 (límite de filas con JOIN) son independientes entre sí (funciones
  distintas); T022 depende de T021; T023 depende de T020.

### Parallel Opportunities

- T001, T002, T003, T004 (Historia 1): archivos distintos, sin dependencias entre sí — pueden
  ejecutarse en paralelo.
- T009 (pruebas de dominio) puede ejecutarse en paralelo con la implementación de T005-T008, una
  vez completos T001/T002.
- T024 (Polish, revisión de docstrings) puede ejecutarse en paralelo con T025 (ambas de solo
  lectura/verificación); T026/T027 dependen de que toda la implementación esté completa; T028
  depende de que T026/T027 ya hayan confirmado que todo funciona.
- Fuera de estos casos, la mayoría de las tareas dentro de una misma historia tienen una
  dependencia de datos real (cada módulo nuevo consume el anterior en la tubería
  fábrica→validación→herramientas→agente→motor→CLI) — no se marcan `[P]` para evitar sugerir un
  paralelismo que en la práctica requeriría que una tarea posterior espere igualmente a que la
  anterior termine.

---

## Parallel Example: User Story 1 (inicio)

```bash
# Sin dependencias entre sí — lanzar en paralelo al iniciar la Historia 1:
Task: "Implementar FuenteDeBaseDeDatos/EntradaBDRelevante/ApreciacionInicialBD en src/opssleuth/domain/database_evidence.py"
Task: "Extender Caso con fuentes_bd/apreciacion_bd en src/opssleuth/domain/case.py"
Task: "Implementar crear_motor_bd() en src/opssleuth/database/factory.py"
Task: "Implementar validar_consulta() en src/opssleuth/database/validacion.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: User Story 1 (T001-T013).
2. **DETENER Y VALIDAR**: Probar la Historia 1 de forma independiente contra `quickstart.md`
   (Escenarios 1, 2 y 3), y confirmar que `uv run pytest tests/` sigue pasando en su totalidad
   (incluidas las pruebas nuevas). **No desplegar todavía**: la Historia 1 por sí sola ya incluye
   la validación básica de solo-lectura/alcance (T004/T005), pero la Historia 2 es la que la
   endurece y prueba adversarialmente — dado el encuadre de "barandilla central, no negociable"
   del propio pedido de esta spec, se recomienda completar también la Historia 2 antes de
   considerar esta funcionalidad lista para un entorno con datos reales.
3. Completar Phase 2: User Story 2 (T014-T019) antes de cualquier despliegue con una base de datos
   real.

### Incremental Delivery

1. Añadir User Story 1 (Phase 1) → probar de forma independiente.
2. Añadir User Story 2 (Phase 2) → probar de forma independiente → recién aquí la funcionalidad es
   aceptable para desplegarse (ver nota de MVP arriba).
3. Añadir User Story 3 (Phase 3) → probar de forma independiente → demo.
4. Phase 4 (Polish) cierra la spec.

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí — ver "Parallel Opportunities" arriba.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Confirmar que las pruebas fallan antes de implementar solo aplica si se decide seguir TDD
  estrictamente; no fue solicitado explícitamente en el spec (mismo criterio que 001-004).
- Hacer commit tras cada tarea o grupo lógico de tareas.
- Detenerse en cada checkpoint para validar la historia de forma independiente.
- A diferencia de otras historias de este proyecto, la Historia 2 de esta spec no es "solo
  verificación sin código nuevo" (como lo fue la Historia 3 de `003-conversacion-adaptativa`) —
  incluye código real (transacción de solo lectura, endurecimiento de la validación) además de
  pruebas adversariales; se mantiene como historia separada porque su propósito (demostrar que la
  barandilla no se puede burlar) es conceptualmente distinto del de la Historia 1 (que la consulta
  básica funciona).
- Evitar: tareas vagas, conflictos de archivo simultáneos, dependencias cruzadas entre historias
  que rompan su independencia de prueba.
