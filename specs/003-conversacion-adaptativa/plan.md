# Implementation Plan: Conversación Adaptativa

**Branch**: `003-conversacion-adaptativa` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-conversacion-adaptativa/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Reducir la rigidez del flujo guiado paso a paso de 001/002 para usuarios con más experiencia en
la herramienta, sin tocar el comportamiento ya implementado y probado para quien no combina
información. Dos comportamientos nuevos, ambos confinados a orquestación en `src/opssleuth/cli.py`
sobre funciones ya existentes (`evaluar_descripcion`, `generar_preguntas`, `_parece_ruta_de_archivo`,
`_solicitar_evidencia_logs`): (1) reconocer una ruta de archivo de log dentro del mismo mensaje que
la descripción inicial, registrarla sin volver a pedirla, y diferir su validación de accesibilidad
hasta el punto de fase en que hoy se dispara la búsqueda de evidencia; (2) cuando el lote inicial de
preguntas de aclaración generadas tras evaluar la descripción tiene 2 o más pendientes, aceptar una
única respuesta combinada (reevaluada con el mismo motor `evaluar_descripcion` ya usado para la
descripción inicial) y solo seguir preguntando una por una por lo que realmente siga faltando. Sin
entidades de dominio nuevas, sin dependencias nuevas, sin nuevos contratos — ver `research.md` para
el detalle de cada decisión y `data-model.md` para por qué no hace falta modelo de datos nuevo.

## Technical Context

**Language/Version**: Python 3.13 (mismo proyecto que 001/002)

**Primary Dependencies**: Ninguna nueva. Reutiliza `langchain-core`, `langchain-anthropic`,
`langchain-ollama`, `langchain-google-genai`, `langgraph`, `pydantic` ya presentes — esta spec no
añade ningún import de terceros nuevo; todo el cambio queda confinado a `src/opssleuth/cli.py`
sobre funciones ya expuestas por `clarification/engine.py` y `evidence/engine.py`.

**Storage**: N/A — sin cambios respecto a 001/002 (`Caso` en memoria de proceso, `tempfile` para
contenido pegado por encima del umbral, mecanismo no tocado por esta spec — ver `research.md`,
Decisión 4 de 002, y Assumptions de `spec.md`).

**Testing**: `pytest`, extendiendo `tests/unit/test_cli.py` (único archivo de pruebas afectado):
casos nuevos para `_extraer_ruta_candidata` (función pura, sin mock), para
`_formular_y_registrar_aclaraciones_combinadas` (con `BaseChatModel` mockeado, igual que las
pruebas existentes de `_procesar_intake`), y para la propagación de la ruta candidata entre
`_procesar_intake` y `_solicitar_evidencia_logs`. Los escenarios de no-regresión (US3) se cubren
re-ejecutando las pruebas ya existentes de `test_cli.py` sin modificarlas.

**Target Platform**: Aplicación de línea de comandos (CLI), multiplataforma — misma aplicación
que 001/002, sin cambios de plataforma.

**Project Type**: Proyecto único (single project) — extensión del mismo proyecto de 001/002, sin
paquetes nuevos.

**Performance Goals**: N/A — esta spec no cambia los objetivos de rendimiento ya establecidos por
002 (búsqueda en archivos de "cientos de miles de líneas" sin cargarlos completos); no toca la
fase de búsqueda en sí (ver `research.md`, Decisión 4). El objetivo propio de esta spec es de
reducción de intercambios conversacionales (SC-002 de `spec.md`), no de rendimiento de cómputo.

**Constraints**: Mismos requisitos de proveedor ya establecidos (`OPSSLEUTH_LLM_PROVIDER`
`claude`/`ollama`/`gemini`, ver `specs/002-busqueda-logs/contracts/chat_model_provider.md`). Sin
requisitos nuevos de proveedor — el batching de aclaraciones reutiliza `evaluar_descripcion`, que
ya funciona sin tool calling (a diferencia del flujo de búsqueda de logs).

**Scale/Scope**: Mismo alcance de "un caso a la vez por conversación" ya establecido. Alcance
explícitamente acotado por las Clarifications de `spec.md` (Sesión 2026-09-14): detección de
evidencia en el mensaje inicial limitada a rutas de archivo (no contenido pegado multilínea);
batching de aclaraciones limitado al lote inicial generado tras evaluar la descripción (no a
aclaraciones que surjan después en la conversación).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Cumplimiento de Principios SOLID | Los dos comportamientos nuevos se implementan como funciones de responsabilidad única añadidas a `cli.py` (`_extraer_ruta_candidata`: solo detección léxica; `_formular_y_registrar_aclaraciones_combinadas`: solo orquestar el lote combinado, delegando la extracción semántica a `evaluar_descripcion` ya existente y el registro de campo a `_aplicar_campos_evaluados` ya existente). `_procesar_intake` sigue teniendo una única razón de cambio ("orquestar el intake de un caso"); su cuerpo crece pero no gana una responsabilidad nueva. Ninguna función de negocio pasa a depender de una implementación concreta de proveedor (se sigue inyectando `BaseChatModel`, nunca `ChatAnthropic`/`ChatOllama`/`ChatGoogleGenerativeAI` directamente). | PASS |
| II. Arquitectura Modular y Reemplazable | Sin cambios al mecanismo de intercambiabilidad ya establecido (`BaseChatModel` vía `crear_modelo_chat()`, confinado a `llm/factory.py`). Esta spec no introduce un nuevo límite de módulo reemplazable — reutiliza `evaluar_descripcion`/`generar_preguntas`/`buscar_evidencia` tal como ya están contratados en `specs/002-busqueda-logs/contracts/`. Ver `research.md`, Decisión 4, sobre por qué no se añade un contrato nuevo. | PASS |
| III. Documentación Obligatoria mediante Docstrings | Las funciones nuevas (`_extraer_ruta_candidata`, `_formular_y_registrar_aclaraciones_combinadas`) y las funciones modificadas (`_procesar_intake`, `_solicitar_evidencia_logs`, `ejecutar_conversacion`) DEBEN llevar/actualizar su docstring numpydoc — se marca como tarea de implementación obligatoria en `tasks.md`. | PASS (a verificar en implementación) |
| IV. Simplicidad ante Todo | Se descartó explícitamente: una cola de aclaraciones pendientes de estado persistente (research.md, Decisión 3), un campo nuevo en `Caso` para la ruta candidata (Decisión 2), una heurística de reconocimiento de ruta nueva y paralela a la ya existente (Decisión 1), y un contrato nuevo sin un límite de módulo nuevo que lo justifique (Decisión 4). El diseño reutiliza el máximo de lógica ya implementada y probada por 001/002, añadiendo solo la orquestación estrictamente necesaria para los dos comportamientos pedidos por la spec. | PASS |

No se identifican violaciones que requieran registrarse en `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/003-conversacion-adaptativa/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command) — sin entidades nuevas
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No se genera un directorio `contracts/` nuevo — ver `research.md`, Decisión 4 ("Sin nuevos
contratos"). Los contratos ya vigentes (`specs/002-busqueda-logs/contracts/`) no cambian.

### Source Code (repository root)

```text
src/
└── opssleuth/
    ├── __init__.py
    ├── cli.py                    # ÚNICO archivo de código de negocio modificado:
    │                              # + _extraer_ruta_candidata(texto) -> str | None (nueva,
    │                              #   función pura, reutiliza el criterio de
    │                              #   _parece_ruta_de_archivo aplicado por token — Decisión 1)
    │                              # + _formular_y_registrar_aclaraciones_combinadas(caso,
    │                              #   chat_model, preguntas_de_campos) -> list[Aclaracion]
    │                              #   (nueva — Decisión 3; delega en evaluar_descripcion y
    │                              #   _aplicar_campos_evaluados ya existentes)
    │                              # ~ _procesar_intake: extrae la ruta candidata del texto
    │                              #   inicial y la devuelve (str | None); usa el camino
    │                              #   combinado cuando preguntas_de_campos tiene >= 2
    │                              #   pendientes, y el bucle uno-por-uno existente para el
    │                              #   resto (sin cambios en ese bucle)
    │                              # ~ _solicitar_evidencia_logs: nuevo parámetro opcional
    │                              #   ruta_candidata; si se aporta, valida esa ruta
    │                              #   directamente (reutilizando la rama de
    │                              #   validación/reintento ya existente) en vez de formular
    │                              #   la invitación interactiva (Decisión 2)
    │                              # ~ ejecutar_conversacion: propaga el valor de retorno de
    │                              #   _procesar_intake hacia _solicitar_evidencia_logs
    ├── domain/                     # Sin cambios (case.py, log_evidence.py)
    ├── llm/                        # Sin cambios (factory.py)
    ├── clarification/              # Sin cambios (engine.py) — se consume tal cual
    └── evidence/                    # Sin cambios (engine.py, tools.py, agent.py) — se consume
                                     # tal cual

tests/
└── unit/
    └── test_cli.py                 # Extendido: pruebas nuevas para _extraer_ruta_candidata,
                                     # _formular_y_registrar_aclaraciones_combinadas, y la
                                     # propagación de ruta_candidata en el flujo de
                                     # ejecutar_conversacion; pruebas existentes sin cambios
                                     # (cubren la no-regresión de US3)
```

**Structure Decision**: Se mantiene el proyecto único ya establecido en 001/002 (Opción 1 del
template), sin paquetes nuevos. Todo el cambio de código de negocio queda confinado a
`src/opssleuth/cli.py` — la capa de orquestación/presentación de la aplicación — porque lo que
cambia es *cuándo* dentro de la conversación se recopila la información, no *cómo* se evalúa
(`clarification/engine.py`), se busca evidencia (`evidence/engine.py`) o se construye el modelo
(`llm/factory.py`), que permanecen sin cambios y se siguen consumiendo exactamente por su
contrato ya documentado.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — la Constitution Check anterior no registra ningún PASS condicionado a
justificación adicional.
