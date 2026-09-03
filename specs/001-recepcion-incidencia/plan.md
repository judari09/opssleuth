# Implementation Plan: Recepción de Incidencia

**Branch**: `001-recepcion-incidencia` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-recepcion-incidencia/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implementar la primera fase del agente OpsSleuth: la recepción de la incidencia. Al iniciar
un caso, el sistema solicita al usuario que describa el problema, mantiene esa descripción
(y cualquier aclaración posterior) como contexto durante toda la conversación, y formula
preguntas de aclaración puntuales cuando la descripción no cubre los 3 campos mínimos
(sistema/aplicación afectada, síntoma, momento/frecuencia). El enfoque técnico usa la API de
Mensajes de Claude (Anthropic) con salida estructurada (`output_config.format`) como
proveedor remoto por defecto para evaluar de forma fiable la presencia de esos campos y
generar las preguntas, detrás de una interfaz (`ClarificationEngine`) reemplazable. Para
demostrar y garantizar esa modularidad (Principio II), se incluye además una segunda
implementación de referencia basada en Ollama, que permite ejecutar el mismo contrato contra
modelos locales, seleccionable sin cambios en el resto del sistema. Todo esto en una
aplicación CLI en Python que mantiene el contexto de la conversación en memoria durante el
proceso.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: `anthropic` (SDK oficial de Claude/Anthropic, proveedor remoto por
defecto), `ollama` (cliente oficial de Ollama, proveedor local alternativo — modularidad de
modelo, Principio II), `pydantic` (definición del esquema de salida estructurada, compartido
por ambos proveedores)

**Storage**: N/A — el contexto del caso vive en memoria de proceso durante la conversación
(sin persistencia duradera en esta fase; ver `research.md`, Decisión 2)

**Testing**: `pytest`, con el cliente de Anthropic mockeado en pruebas unitarias del motor
de aclaración

**Target Platform**: Aplicación de línea de comandos (CLI), multiplataforma
(Windows/Linux/macOS)

**Project Type**: Proyecto único (single project)

**Performance Goals**: Interacción conversacional interactiva; una llamada a la API de
Claude por turno relevante. Sin objetivo numérico estricto de latencia en esta fase (más
allá de SC-005 del spec: recepción típica en menos de 5 intercambios de mensajes).

**Constraints**: Con el proveedor por defecto (Claude), requiere `ANTHROPIC_API_KEY` (o un
perfil activo vía `ant auth login`) y acceso de red saliente a la API de Claude. Con el
proveedor alternativo (Ollama), requiere una instancia de Ollama accesible localmente
(`http://localhost:11434` por defecto) con el modelo deseado ya descargado (`ollama pull
<modelo>`); no requiere red saliente ni credenciales de Anthropic. La selección de
proveedor y modelo es configurable por el usuario (ver `research.md`, Decisión 4); no se fija
un único proveedor obligatorio.

**Scale/Scope**: Un usuario por conversación; un caso activo a la vez por conversación,
pudiendo haber varios casos secuenciales dentro de la misma conversación (ver
Clarifications en `spec.md`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Cumplimiento de Principios SOLID | El diseño separa dominio (`Caso`, entidades en `data-model.md`), el contrato del motor de aclaración (`ClarificationEngine`, responsabilidad única: evaluar + generar preguntas) y sus implementaciones concretas (Claude, Ollama). Los consumidores (gestión de `Caso`, CLI) dependen de la abstracción, no de `anthropic` ni de `ollama` directamente (Inversión de Dependencias); ambas implementaciones son sustituibles entre sí sin alterar la corrección del sistema (Sustitución de Liskov). | PASS |
| II. Arquitectura Modular y Reemplazable | El motor de NLU/aclaración se expone mediante un contrato explícito (`contracts/clarification_engine.md`). Esta fase incluye dos implementaciones reales que lo satisfacen — `ClaudeClarificationEngine` (remoto) y `OllamaClarificationEngine` (local) — seleccionables mediante configuración, demostrando en código la intercambiabilidad exigida por el principio, no solo en teoría. | PASS |
| III. Documentación Obligatoria mediante Docstrings | Toda clase/función nueva en `src/opssleuth/` DEBE llevar docstring numpydoc (backend Python; no aplica frontend en esta fase). Se marca como tarea de implementación obligatoria, no opcional. | PASS (a verificar en implementación) |
| IV. Simplicidad ante Todo | Se descartó explícitamente el uso de Managed Agents, heurísticas híbridas y almacenamiento persistente por no estar justificados por una necesidad presente (ver `research.md`, Decisiones 0-2). Una sola llamada a la API de Mensajes por turno, sin capas adicionales. | PASS |

No se identifican violaciones que requieran registrarse en `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/001-recepcion-incidencia/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── clarification_engine.md
│   └── evaluacion_schema.json
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── opssleuth/
    ├── __init__.py
    ├── cli.py                    # Bucle conversacional / punto de entrada de la CLI
    ├── domain/
    │   ├── __init__.py
    │   └── case.py                # Entidades: Caso, DescripcionProblema, CampoExtraido, Aclaracion
    └── clarification/
        ├── __init__.py
        ├── engine.py               # Contrato ClarificationEngine (Protocol) + EvaluacionDescripcion
        ├── claude_engine.py        # Implementación ClaudeClarificationEngine (adaptador sobre `anthropic`)
        ├── ollama_engine.py        # Implementación OllamaClarificationEngine (adaptador sobre `ollama`, modelos locales)
        └── factory.py               # Selección del proveedor configurado (claude|ollama) -> ClarificationEngine

tests/
└── unit/
    ├── test_case.py                # Reglas de dominio de Caso (estado, transiciones)
    ├── test_claude_engine.py       # ClaudeClarificationEngine con cliente Anthropic mockeado
    └── test_ollama_engine.py       # OllamaClarificationEngine con cliente Ollama mockeado
```

**Structure Decision**: Proyecto único (Opción 1 del template), ya que esta es una
aplicación CLI en Python sin componente de frontend ni backend/API separados. El motor de
aclaración se aísla en `clarification/` detrás del contrato `engine.py` (Principio II); el
dominio puro (`domain/case.py`) no depende de ningún SDK de proveedor de modelo — solo
`claude_engine.py` depende de `anthropic` y solo `ollama_engine.py` depende de `ollama`,
manteniendo ambas dependencias externas detrás de la misma abstracción. `factory.py`
concentra la única decisión de "qué proveedor usar" en un solo lugar (Responsabilidad
Única), leída de configuración (p. ej. variable de entorno `OPSSLEUTH_LLM_PROVIDER`,
por defecto `claude`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla no aplica.
