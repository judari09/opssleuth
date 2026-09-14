# Implementation Plan: Búsqueda en Archivos de Logs

**Branch**: `002-busqueda-logs` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-busqueda-logs/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implementar la segunda herramienta de investigación del agente OpsSleuth: la búsqueda de
evidencia en archivos de logs. Una vez que la recepción de la incidencia (spec 001) queda con
la información completa, el sistema invita proactivamente al usuario a aportar evidencia de
logs (ruta a un archivo local, o contenido pegado directamente en el chat). El modelo localiza,
mediante un bucle agéntico de uso de herramientas (búsqueda por patrón, lectura de contexto,
conteo de líneas), las entradas relacionadas con el incidente descrito — aislando por horario
si se conoce — sin cargar el archivo completo en el contexto. Al concluir, elabora una
apreciación inicial consolidada (entre todas las fuentes aportadas) que se incorpora al
contexto del caso para uso posterior. El modelo puede además solicitar contexto general del
proyecto al usuario, mediante una herramienta adicional que pausa el bucle para entrada por CLI.

**Decisión técnica adicional (incorporada tras revisión de esta spec, 2026-09-03)**: el proyecto
adopta el ecosistema LangChain/LangGraph como capa de abstracción de modelo de lenguaje —
`langchain_core.language_models.BaseChatModel` sustituye al contrato `Protocol` propio como
mecanismo de intercambiabilidad entre Claude y Ollama, amparado por una enmienda explícita a la
constitución (v1.0.0 → v1.1.0, ver `.specify/memory/constitution.md`). Por decisión directa del
usuario, el alcance de esta spec se amplía para incluir la **migración** del motor de aclaración
de incidencias de 001 (`ClarificationEngine`) a esta misma arquitectura, además de construir el
motor de búsqueda de logs nuevo directamente sobre ella — ver `research.md` (Decisiones 1, 3 y 9)
y `contracts/chat_model_provider.md`, `contracts/clarification_migration.md`,
`contracts/log_search_engine.md` para el detalle completo.

## Technical Context

**Language/Version**: Python 3.13 (mismo proyecto que 001)

**Primary Dependencies**: `langchain-core`, `langchain-anthropic`, `langchain-ollama`,
`langgraph` (nuevas — capa de abstracción de modelo de chat y bucle agéntico, ver `research.md`,
Decisión 1). `anthropic` y `ollama` permanecen como dependencias transitivas (usadas
internamente por los paquetes de integración de LangChain) pero dejan de importarse directamente
en código de negocio — solo dentro de la función de fábrica compartida
(`src/opssleuth/llm/factory.py`). `pydantic` se mantiene (esquema de `EvaluacionDescripcion` y
de la salida estructurada vía `BaseChatModel.with_structured_output`).

**Storage**: N/A para el contexto del caso (igual que 001, en memoria de proceso). Uso de
`tempfile` (librería estándar) para materializar como archivo el contenido de logs pegado que
supere el umbral de 4 líneas (FR-003/FR-015; ver `research.md`, Decisión 8) — sin persistencia
duradera más allá de la sesión, consistente con la decisión ya registrada en `ESTADO_SPECS.md`.

**Testing**: `pytest`, con `BaseChatModel`/`ChatAnthropic`/`ChatOllama` mockeados en pruebas
unitarias (en vez de los clientes crudos `anthropic`/`ollama` como en la versión original de
001) — tanto para el flujo de aclaración migrado como para el de búsqueda de logs nuevo.

**Target Platform**: Aplicación de línea de comandos (CLI), multiplataforma
(Windows/Linux/macOS) — misma aplicación que 001.

**Project Type**: Proyecto único (single project) — extensión del mismo proyecto de 001.

**Performance Goals**: Localizar entradas relevantes en archivos de "cientos de miles de
líneas" (SC-001) sin cargar el archivo completo en memoria del proceso del modelo — las
herramientas de búsqueda operan por streaming/iteración de líneas sobre el archivo en disco.
Apreciación inicial obtenida en menos de 5 intercambios de mensajes en el caso típico (SC-004).

**Constraints**: Mismos requisitos de proveedor que 001 según `OPSSLEUTH_LLM_PROVIDER`
(`ANTHROPIC_API_KEY`/`ant auth login` para Claude; instancia local de Ollama con el modelo
configurado ya descargado para Ollama). El flujo de búsqueda de logs requiere adicionalmente que
el modelo local configurado soporte tool calling (`bind_tools`) — requisito nuevo respecto a 001,
donde el flujo de aclaración no usaba herramientas. Los archivos de logs se asumen de texto plano
(ver Assumptions de `spec.md`).

**Scale/Scope**: Una fuente de logs activa a la vez por operación de búsqueda, pudiendo un caso
tener varias fuentes aportadas secuencialmente (FR-013) que se consolidan en una única
apreciación (FR-010a). Alcance ampliado: además del motor de búsqueda de logs nuevo, esta spec
cubre la migración completa del motor de aclaración de 001 a la nueva arquitectura, preservando
su comportamiento observable (ver `research.md`, Decisión 9, y `contracts/clarification_migration.md`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Cumplimiento de Principios SOLID | El diseño separa dominio (`FuenteDeLogs`, `EntradaLogRelevante`, `ApreciacionInicialLogs`, y la extensión de `Caso`, sin dependencia de SDK ni de LangChain), la función de fábrica compartida (`crear_modelo_chat`, responsabilidad única: seleccionar y construir el `BaseChatModel` configurado) y los módulos de orquestación (`evaluar_descripcion`/`generar_preguntas` migrados, `buscar_evidencia` nuevo), que dependen del tipo abstracto `BaseChatModel` inyectado — nunca de `ChatAnthropic`/`ChatOllama` concretos (Inversión de Dependencias). La herramienta `preguntar_al_usuario` invoca un callback inyectado en vez de acceder a stdin/stdout directamente. Ambos flujos son sustituibles entre proveedores sin alterar la corrección del sistema (Sustitución de Liskov), garantizada ahora por `BaseChatModel` en vez de por clases de adaptador propias. | PASS |
| II. Arquitectura Modular y Reemplazable | Se adopta `BaseChatModel` de LangChain como el "contrato explícito y estable" exigido por este principio, bajo la excepción explícita de "estándar de abstracción de terceros maduro" incorporada a la constitución en esta misma spec (v1.1.0) — evita envolver un estándar ya swappable en una interfaz propia redundante (lo que violaría el Principio IV). El acoplamiento a los paquetes concretos de LangChain queda confinado a `llm/factory.py` (punto de integración único y documentado), tal como exige la excepción. Se documenta el contrato en `contracts/chat_model_provider.md`, `contracts/clarification_migration.md` y `contracts/log_search_engine.md`. | PASS |
| III. Documentación Obligatoria mediante Docstrings | Toda clase/función nueva o migrada en `src/opssleuth/` DEBE llevar docstring numpydoc (backend Python), incluyendo las funciones `@tool` (cuyo docstring además alimenta el esquema que ve el modelo — ver `research.md`, Decisión 4). Se marca como tarea de implementación obligatoria. | PASS (a verificar en implementación) |
| IV. Simplicidad ante Todo | La adopción de LangChain se justificó explícitamente frente a la tensión con el Principio II original (ver enmienda a la constitución) precisamente para evitar una capa de abstracción propia redundante sobre un estándar ya intercambiable. Se descartó mantener dos mecanismos de modularidad distintos conviviendo en el proyecto (Protocol propio para aclaración, LangChain para búsqueda). Se descartó un parser de timestamps dedicado, una herramienta de rango horario separada, y una segunda llamada al modelo para enumerar `entradas_destacadas` — ver `research.md`, Decisiones 4 y 6. La unificación del bucle agéntico bajo LangGraph (Decisión 3) elimina la asimetría Tool Runner/bucle manual que la versión anterior de este plan había introducido, resultando en menos código propio, no más. | PASS |

No se identifican violaciones que requieran registrarse en `Complexity Tracking`. La única
"complejidad" añadida (una dependencia de terceros nueva y de peso considerable — el ecosistema
LangChain/LangGraph) está justificada explícitamente por decisión directa del usuario y
formalizada mediante la enmienda a la constitución, no como una excepción no justificada.

## Project Structure

### Documentation (this feature)

```text
specs/002-busqueda-logs/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── chat_model_provider.md      # Contrato central: crear_modelo_chat() -> BaseChatModel
│   ├── clarification_migration.md  # Contrato de la migración del motor de aclaración (001)
│   ├── log_search_engine.md        # Contrato del agente de búsqueda de logs (LangGraph)
│   └── tools_schema.json           # Referencia de contenido de las 4 herramientas
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── opssleuth/
    ├── __init__.py
    ├── cli.py                    # Extendido: invitación proactiva a aportar logs (FR-014),
    │                              # manejo de rutas/contenido pegado, invocación de
    │                              # buscar_evidencia(), preguntar_callback para
    │                              # preguntar_al_usuario; usa evaluar_descripcion() migrada
    │                              # en vez de ClarificationEngine
    ├── domain/
    │   ├── __init__.py
    │   ├── case.py                 # Extendido: Caso.creado_en, Caso.fuentes_logs,
    │   │                           # Caso.apreciacion_logs (ver data-model.md)
    │   └── log_evidence.py         # Nuevo: FuenteDeLogs, EntradaLogRelevante,
    │                               # ApreciacionInicialLogs
    ├── llm/                        # Nuevo paquete — reemplaza clarification/factory.py y el
    │   ├── __init__.py             # evidence/factory.py originalmente planificado
    │   └── factory.py               # crear_modelo_chat() -> BaseChatModel
    │                               # (único punto de integración con langchain-anthropic/
    │                               # langchain-ollama; lee OPSSLEUTH_LLM_PROVIDER/
    │                               # OPSSLEUTH_OLLAMA_MODEL)
    ├── clarification/              # Migrado — ya no contiene clases por proveedor ni factory
    │   ├── __init__.py
    │   └── engine.py                # evaluar_descripcion(chat_model, texto, contexto),
    │                               # generar_preguntas(evaluacion, contexto) (sin cambios de
    │                               # comportamiento), ClarificationEngineError (preservada)
    │                               # claude_engine.py, ollama_engine.py y factory.py se ELIMINAN
    └── evidence/                    # Nuevo paquete — motor de búsqueda de logs
        ├── __init__.py
        ├── engine.py                 # LogSearchEngineError; buscar_evidencia(chat_model, caso,
        │                            # fuentes, preguntar_callback) -> ApreciacionInicialLogs;
        │                            # bookkeeping determinista de entradas_destacadas
        ├── tools.py                  # Herramientas @tool: buscar_texto, leer_contexto,
        │                            # contar_lineas, preguntar_al_usuario (operan sobre un
        │                            # archivo — sin dependencia de SDK de proveedor alguno)
        └── agent.py                  # Construcción del agente LangGraph (create_react_agent o
                                      # StateGraph a medida) que enlaza las herramientas al
                                      # chat_model recibido

tests/
└── unit/
    ├── test_case.py                 # Extendido: pruebas de Caso.creado_en/fuentes_logs/apreciacion_logs
    ├── test_log_evidence.py         # Nuevo: reglas de dominio de FuenteDeLogs/EntradaLogRelevante/
    │                               # ApreciacionInicialLogs
    ├── test_evaluar_descripcion.py  # Migrado de test_claude_engine.py/test_ollama_engine.py:
    │                               # mismos casos de prueba, ahora mockeando BaseChatModel
    ├── test_tools.py                # Nuevo: buscar_texto/leer_contexto/contar_lineas sobre
    │                               # archivos de prueba (sin mock de modelo)
    └── test_buscar_evidencia.py     # Nuevo: buscar_evidencia() con BaseChatModel/agente
                                     # LangGraph mockeado
```

**Structure Decision**: Se mantiene el proyecto único ya establecido en 001 (Opción 1 del
template). Se introduce un paquete `llm/` nuevo que concentra el único punto de integración con
LangChain (`crear_modelo_chat`), del que dependen tanto `clarification/` (migrado, sin clases por
proveedor) como `evidence/` (nuevo). `clarification/` pierde `claude_engine.py`, `ollama_engine.py`
y `factory.py` — su responsabilidad se reduce a la lógica de evaluación/generación de preguntas en
sí, desacoplada de cómo se obtiene el modelo. `evidence/` sigue una convención de nombres
análoga (`engine.py` para el contrato y el bookkeeping determinista, `tools.py` para las
herramientas, `agent.py` para la construcción del grafo LangGraph), de modo que la estructura
siga siendo reconocible para quien conozca `clarification/`. Las entidades de dominio nuevas se
añaden a `domain/`, y `Caso` se extiende in-place en `case.py`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones que requieran esta tabla — la Constitution Check anterior documenta que la
dependencia nueva (LangChain/LangGraph) está justificada mediante decisión explícita del usuario
y formalizada mediante enmienda a la constitución (v1.1.0), no como una excepción tácita.
