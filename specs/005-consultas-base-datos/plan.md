# Implementation Plan: Consultas a Bases de Datos

**Branch**: `005-consultas-base-datos` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-consultas-base-datos/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Añade una tercera fuente de evidencia para el diagnóstico — consultas a una base de datos
configurada — complementaria e independiente de la búsqueda en logs (spec 002). Reutiliza
exactamente el patrón ya establecido de agente LangGraph con herramientas acotadas (Principio II):
un nuevo paquete `database/` (análogo a `evidence/`) expone 3 herramientas (`listar_tablas_disponibles`,
`describir_tabla`, `ejecutar_consulta_sql`) que un agente usa para localizar filas relacionadas con
el incidente, incluyendo cruces entre más de dos tablas. La barandilla de seguridad central
(Historia 2, P1) se implementa como validación en dos capas antes de cualquier ejecución: (1)
`sqlglot` valida que la consulta propuesta sea una única sentencia `SELECT` y que toda tabla
referenciada esté dentro del conjunto explícitamente permitido (`OPSSLEUTH_DB_TABLAS_PERMITIDAS`);
(2) la conexión se abre en modo de solo lectura cuando el dialecto lo soporta, y nunca se hace
`commit()`. La conexión y el alcance de tablas se configuran una única vez vía variables de entorno
(`OPSSLEUTH_DB_URL`/`OPSSLEUTH_DB_TABLAS_PERMITIDAS`), nunca conversacionalmente — ver
Clarifications de `spec.md`. Cada consulta ejecutada se anuncia visiblemente al usuario
(reutilizando el indicador de actividad de spec 004) antes de mostrar el resultado.

## Technical Context

**Language/Version**: Python 3.13 (mismo proyecto que 001-004)

**Primary Dependencies**: `sqlalchemy` (Core, no ORM — conexión agnóstica de motor, confinada a
`database/factory.py`/`database/tools.py`, ver `research.md` Decisión 1) y `sqlglot` (validación
de las consultas propuestas por el agente — parseo de sentencia única `SELECT` y extracción de
tablas referenciadas, ver `research.md` Decisión 2). Reutiliza sin cambios `langchain-core`,
`langgraph`, `crear_modelo_chat()` (spec 002) y `mostrar_actividad()` (spec 004) ya existentes.

**Storage**: La base de datos consultada es externa y ya existente (configurada por quien opera la
herramienta) — este proyecto no la crea, migra ni administra, solo la consulta de forma acotada.
Sin cambios en el almacenamiento propio del proyecto (`Caso` sigue en memoria de proceso, sin
persistencia duradera — consistente con `specs/ESTADO_SPECS.md`).

**Testing**: `pytest`, con el mismo patrón ya establecido: pruebas unitarias de las herramientas
(`database/tools.py`) contra una base de datos SQLite real en un archivo temporal (sin mock de
motor — mismo criterio que `test_tools.py` de spec 002 usa archivos de logs reales de prueba, no
mocks del sistema de archivos), y pruebas de `consultar_evidencia_bd`
(`database/engine.py`) con `BaseChatModel`/agente mockeado (mismo patrón que
`test_buscar_evidencia.py`). Casos de prueba dedicados para la barandilla de seguridad (Historia
2): consultas de escritura y consultas fuera de alcance deben rechazarse sin llegar a
`Engine.connect()`, verificable inspeccionando que los datos de la base de datos de prueba no
cambian.

**Target Platform**: Aplicación de línea de comandos (CLI), multiplataforma — misma aplicación que
001-004.

**Project Type**: Proyecto único (single project) — extensión del mismo proyecto de 001-004.

**Performance Goals**: Ninguna consulta debe materializar en memoria más filas de las que el
límite acotado permite (`MAXIMO_FILAS_POR_DEFECTO + 1`, ver `research.md` Decisión 5) —
particularmente relevante para consultas con cruces entre varias tablas (Historia 3), donde un
cruce mal formado podría producir un volumen de filas desproporcionado.

**Constraints**: Mismos requisitos de proveedor de modelo ya establecidos
(`OPSSLEUTH_LLM_PROVIDER`; con Ollama, el modelo local configurado debe soportar tool calling,
mismo requisito ya documentado por spec 002). Nuevo: si `OPSSLEUTH_DB_URL` está configurada,
`OPSSLEUTH_DB_TABLAS_PERMITIDAS` DEBE estarlo también y no vacía — sin este valor, la
funcionalidad se rechaza explícitamente en vez de asumir acceso sin restricción (ver
`research.md`, Decisión 4). Motor de base de datos no asumido por el proyecto — SQLite (incluido
en la biblioteca estándar) es el motor de referencia para pruebas/quickstart; otros motores
requieren que el operador instale su driver DBAPI correspondiente.

**Scale/Scope**: Una fuente de base de datos por caso en esta implementación (`Caso.fuentes_bd`
modelado como lista, pero poblado con 0 o 1 elemento — ver `research.md`, Decisión 7; la spec
permite más de una fuente en el futuro sin cambiar el comportamiento descrito). Independiente de
la evidencia de logs (Clarifications, Sesión 2026-09-21, Pregunta 3) — ambas fuentes se consultan
por separado y se presentan consolidadas (FR-009).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Cumplimiento de Principios SOLID | El diseño separa dominio (`FuenteDeBaseDeDatos`, `EntradaBDRelevante`, `ApreciacionInicialBD`, y la extensión de `Caso`, sin dependencia de `sqlalchemy`/`sqlglot`), la función de fábrica de conexión (`crear_motor_bd`, responsabilidad única: construir y validar el `Engine` configurado — nunca ejecuta consultas de negocio) y el motor de orquestación (`consultar_evidencia_bd`, agente LangGraph con las 3 herramientas nuevas), que dependen del tipo abstracto `BaseChatModel` inyectado — nunca de una implementación concreta de proveedor. `mostrar_actividad` se recibe inyectado (no se importa `opssleuth.presentation` directamente desde `database/`), preservando Inversión de Dependencias entre capas. | PASS |
| II. Arquitectura Modular y Reemplazable | `sqlalchemy`/`sqlglot` quedan confinados al paquete `database/` nuevo — se sigue el camino por defecto del principio (capa de abstracción propia), no la excepción de "estándar de abstracción de terceros maduro", porque aquí no hay varios módulos de negocio independientes que necesiten compartir el tipo abstracto de terceros como mecanismo de intercambiabilidad (a diferencia de `BaseChatModel`) — ver `research.md`, Decisión 1, para el razonamiento completo. Se documentan dos contratos nuevos (`contracts/database_connection.md`, `contracts/database_query_engine.md`), mismo patrón que spec 002. | PASS |
| III. Documentación Obligatoria mediante Docstrings | Toda clase/función nueva en `src/opssleuth/database/` y `src/opssleuth/domain/database_evidence.py` DEBE llevar docstring numpydoc, incluyendo las 3 funciones `@tool` (cuyo docstring alimenta además el esquema que ve el modelo — mismo criterio que spec 002). Se marca como tarea de implementación obligatoria. | PASS (a verificar en implementación) |
| IV. Simplicidad ante Todo | Se descartó explícitamente: un driver de un solo motor en vez de SQLAlchemy (Decisión 1); una heurística por regex en vez de `sqlglot` para la validación de seguridad más crítica del diseño (Decisión 2 — aquí la librería madura es la opción *más simple y correcta*, no la más compleja); una herramienta estructurada de construcción de consultas (tabla+filtros+joins tipados) en vez de SQL libre validado, que terminaría reinventando un lenguaje de consultas equivalente con más código propio (Decisión 6); soporte de múltiples fuentes de base de datos nombradas en esta primera implementación, cuando la spec solo lo permite sin exigirlo (Decisión 7). | PASS |

No se identifican violaciones que requieran registrarse en `Complexity Tracking`. Las dos
dependencias nuevas (`sqlalchemy`, `sqlglot`) están justificadas explícitamente: son, cada una en
su rol, la opción madura y auditada para el problema que resuelven (conexión agnóstica de motor;
validación de seguridad de las consultas), evitando reinventar ambas con código propio menos
confiable — consistente con por qué el proyecto ya adoptó LangChain/LangGraph en la spec 002.

## Project Structure

### Documentation (this feature)

```text
specs/005-consultas-base-datos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── database_connection.md    # Contrato: crear_motor_bd() -> conexión configurada
│   ├── database_query_engine.md  # Contrato: consultar_evidencia_bd() (agente LangGraph)
│   └── tools_schema.json         # Referencia de contenido de las 3 herramientas nuevas
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── opssleuth/
    ├── __init__.py
    ├── cli.py                    # Extendido: tras completar el intake, si
    │                              # crear_motor_bd() devuelve una fuente configurada,
    │                              # invoca consultar_evidencia_bd() (independiente de
    │                              # si hay evidencia de logs); presenta
    │                              # caso.apreciacion_bd junto a caso.apreciacion_logs
    │                              # al resumir el caso (FR-009)
    ├── domain/
    │   ├── __init__.py
    │   ├── case.py                  # Extendido: Caso.fuentes_bd, Caso.apreciacion_bd
    │   ├── log_evidence.py          # Sin cambios (spec 002)
    │   └── database_evidence.py     # Nuevo: FuenteDeBaseDeDatos, EntradaBDRelevante,
    │                                # ApreciacionInicialBD (ver data-model.md)
    ├── llm/                        # Sin cambios (factory.py)
    ├── clarification/              # Sin cambios (engine.py)
    ├── presentation/                # Sin cambios (console.py) — mostrar_actividad se
    │                                # inyecta en database/engine.py, no se importa ahí
    ├── evidence/                    # Sin cambios (motor de búsqueda de logs, spec 002)
    └── database/                    # Nuevo paquete — motor de consulta a base de datos
        ├── __init__.py
        ├── factory.py                 # crear_motor_bd() -> FuenteDeBaseDeDatosConfigurada | None
        │                              # (único punto de integración con sqlalchemy para
        │                              # construir el Engine; lee OPSSLEUTH_DB_URL/
        │                              # OPSSLEUTH_DB_TABLAS_PERMITIDAS/
        │                              # OPSSLEUTH_DB_TIMEOUT_SEGUNDOS)
        ├── validacion.py               # Validación de consultas con sqlglot (sentencia
        │                              # única SELECT, extracción/verificación de tablas
        │                              # referenciadas — usado por tools.py)
        ├── tools.py                    # Herramientas @tool: listar_tablas_disponibles,
        │                              # describir_tabla, ejecutar_consulta_sql (operan
        │                              # sobre un Engine — sin dependencia de proveedor de
        │                              # modelo alguno)
        ├── agent.py                    # Construcción del agente LangGraph que enlaza las
        │                              # herramientas al chat_model recibido
        └── engine.py                    # DatabaseSearchEngineError;
                                        # consultar_evidencia_bd(chat_model, caso, fuente,
                                        # anunciar_actividad) -> ApreciacionInicialBD;
                                        # bookkeeping determinista de entradas_destacadas

tests/
└── unit/
    ├── test_case.py                 # Extendido: pruebas de Caso.fuentes_bd/apreciacion_bd
    ├── test_database_evidence.py    # Nuevo: reglas de dominio de FuenteDeBaseDeDatos/
    │                               # EntradaBDRelevante/ApreciacionInicialBD
    ├── test_database_factory.py     # Nuevo: crear_motor_bd() — sin OPSSLEUTH_DB_URL (None),
    │                               # sin OPSSLEUTH_DB_TABLAS_PERMITIDAS (error), tablas
    │                               # inexistentes omitidas, contra SQLite real de prueba
    ├── test_database_validacion.py  # Nuevo: validación con sqlglot — sentencia no-SELECT
    │                               # rechazada, múltiples sentencias rechazadas, tabla
    │                               # fuera de alcance rechazada, tabla permitida aceptada
    ├── test_database_tools.py       # Nuevo: listar_tablas_disponibles/describir_tabla/
    │                               # ejecutar_consulta_sql contra SQLite real de prueba —
    │                               # incluye verificar que un intento de escritura NO
    │                               # modifica los datos de prueba
    └── test_consultar_evidencia_bd.py  # Nuevo: consultar_evidencia_bd() con
                                        # BaseChatModel/agente mockeado
```

**Structure Decision**: Se mantiene el proyecto único ya establecido (Opción 1 del template). Se
introduce un paquete `database/` nuevo, con una convención de nombres análoga a `evidence/`
(`factory.py` para el punto de integración con el motor de conexión — análogo a `llm/factory.py`;
`tools.py`/`agent.py`/`engine.py` con los mismos roles que en `evidence/`), más un módulo
`validacion.py` adicional que no tiene equivalente en `evidence/` porque la búsqueda de logs no
necesita validar/rechazar la entrada del modelo antes de ejecutarla — aquí sí, y es la pieza más
crítica de seguridad del diseño, por lo que se aísla en su propio módulo con pruebas dedicadas en
vez de mezclarla dentro de `tools.py`. Las entidades de dominio nuevas se añaden a `domain/`, y
`Caso` se extiende in-place en `case.py`, mismo patrón ya usado por spec 002.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — la Constitution Check anterior no registra ningún PASS condicionado a
justificación adicional más allá de la ya incluida en la tabla.
