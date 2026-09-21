# Implementation Plan: CLI Chat Enriquecida

**Branch**: `004-cli-chat-enriquecida` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-cli-chat-enriquecida/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Cambio puramente de presentación sobre la CLI ya implementada (001/002/003): diferencia
visualmente las entradas del usuario de las respuestas del sistema mediante una etiqueta textual
de rol obligatoria (reforzada con color, nunca dependiente solo de él — Clarifications, Sesión
2026-09-16), renderiza el contenido estructurado de las respuestas del sistema (listas, énfasis)
de forma legible en vez de marcado sin procesar, e indica visualmente actividad ("pensando...",
"buscando en los logs...") y errores de comunicación con el proveedor — sin alterar en ningún caso
el comportamiento conversacional ya implementado (FR-007). Se construye con `rich`, confinada a un
único módulo nuevo (`src/opssleuth/presentation/console.py`) del que `src/opssleuth/cli.py` es el
único consumidor; `_imprimir`/`_leer_entrada` (los dos puntos de integración ya existentes por los
que pasa el 100% de la entrada/salida de la conversación) se convierten en delegadores delgados
hacia ese módulo, preservando exactamente sus firmas y contratos actuales — de ahí que no se
requiera tocar ningún otro punto de llamada de `cli.py` más allá de lo estrictamente necesario para
FR-004/FR-005 (indicación de actividad y distinción de errores).

## Technical Context

**Language/Version**: Python 3.13 (mismo proyecto que 001/002/003)

**Primary Dependencies**: `rich` (nueva — única dependencia añadida por esta spec). Confinada a
`src/opssleuth/presentation/console.py`: ningún otro módulo del proyecto debe importar `rich`
directamente (Principio II). No se acoge a la excepción constitucional de "estándar de abstracción
de terceros maduro" (v1.1.0) — esa excepción está pensada para adoptar el tipo abstracto de un
paquete de terceros como el propio mecanismo de intercambiabilidad del proyecto (caso de
`BaseChatModel`), y aquí no existe tal necesidad: no hay implementaciones de renderizado
intercambiables entre las que elegir en tiempo de ejecución, solo una dependencia de presentación
que se confina detrás de una capa propia — el camino por defecto (no la excepción) del Principio II
("exponer las dependencias externas detrás de una capa de abstracción propia del proyecto").

**Storage**: N/A — sin cambios respecto a 001/002/003.

**Testing**: `pytest`. `tests/unit/test_console.py` (nuevo) prueba
`src/opssleuth/presentation/console.py` directamente contra un `rich.console.Console` inyectado
que escribe a un buffer en memoria (`io.StringIO()`, `force_terminal=False`) — permite verificar
por texto plano que la etiqueta de rol está presente y que el contenido markdown se renderiza
(sin símbolos de marcado sin procesar), sin depender de captura de ANSI ni de la implementación
interna de `rich`. `tests/unit/test_cli.py` (existente, 87 pruebas) no requiere cambios: ninguna
prueba actual monkeypatchea ni hace aserciones sobre `_imprimir` (nunca se reemplaza ni se captura
su salida), y las que monkeypatchean `_leer_entrada` lo hacen reemplazando la función completa —
mantener su firma (`_leer_entrada(prompt: str) -> str`) intacta basta para que seguir pasando sin
modificación (verificado: cero coincidencias de `capsys`/`capfd` o monkeypatch de `_imprimir` en la
suite actual).

**Target Platform**: Aplicación de línea de comandos (CLI), multiplataforma — misma aplicación que
001/002/003. `rich` detecta automáticamente la capacidad de color/formato de la terminal de destino
(variable `NO_COLOR`, `isatty()`, terminales "dumb") y degrada su salida a texto plano sin
intervención adicional del código de este proyecto (FR-006).

**Project Type**: Proyecto único (single project) — extensión del mismo proyecto de 001/002/003.

**Performance Goals**: N/A — sin objetivos de rendimiento nuevos; el indicador de actividad
(FR-004) es una mejora de percepción sobre operaciones que ya toman varios segundos hoy (evaluación
de descripción/aclaraciones y búsqueda de evidencia en logs, ambas ya observadas en uso real con
latencias de varios segundos), no un cambio en su duración real.

**Constraints**: Ninguno nuevo respecto a la selección de proveedor de modelo ya establecida
(`OPSSLEUTH_LLM_PROVIDER`). Esta spec no depende de qué proveedor esté configurado — es ortogonal
al motor de LLM.

**Scale/Scope**: Cambios confinados a un módulo nuevo (`presentation/console.py`) y a
`src/opssleuth/cli.py` (delegación en `_imprimir`/`_leer_entrada`, más el cableado puntual de
`es_error=True` en los 2 mensajes de fallo de proveedor y de `mostrar_actividad(...)` alrededor de
las 4 llamadas a `evaluar_descripcion`/`buscar_evidencia`). Sin cambios en `domain/`, `llm/`,
`clarification/`, `evidence/` — ninguno de esos módulos conoce ni debe conocer `rich`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Cumplimiento de Principios SOLID | `presentation/console.py` tiene responsabilidad única (renderizar mensajes/leer entrada con estilo diferenciado) y es la única pieza del sistema que conoce `rich` — el resto de `cli.py` sigue dependiendo de las mismas dos funciones ya existentes (`_imprimir`/`_leer_entrada`), ahora delegadores delgados. Ningún módulo de dominio o de motor de LLM (`domain/`, `clarification/`, `evidence/`, `llm/`) cambia ni pasa a depender de `rich` — Inversión de Dependencias intacta. El `Console` es inyectable como parámetro opcional en cada función del módulo nuevo (mismo patrón de inyección ya usado para `chat_model` en el resto del proyecto), lo que mantiene el módulo abierto a pruebas sin acoplarlo a un singleton global oculto. | PASS |
| II. Arquitectura Modular y Reemplazable | `rich` (dependencia de terceros nueva) queda confinada a un único punto de integración explícito y documentado (`src/opssleuth/presentation/console.py`), tal como exige el principio para toda dependencia externa — sin necesidad de invocar la excepción de "estándar de abstracción de terceros maduro" (ver Technical Context: no hay implementaciones intercambiables de renderizado, solo confinamiento de una dependencia de presentación). `cli.py` sigue exponiendo la misma interfaz interna (`_imprimir`/`_leer_entrada`) al resto de su propio código — ningún otro módulo del proyecto necesita cambiar para que esta spec exista. | PASS |
| III. Documentación Obligatoria mediante Docstrings | Toda función nueva en `presentation/console.py` (`mostrar_mensaje_sistema`, `leer_entrada_usuario`, `mostrar_actividad`) y las funciones modificadas de `cli.py` (`_imprimir`, `_leer_entrada`, más los puntos de cableado de `es_error`/`mostrar_actividad`) DEBEN llevar/actualizar su docstring numpydoc — se marca como tarea de implementación obligatoria en `tasks.md`. | PASS (a verificar en implementación) |
| IV. Simplicidad ante Todo | Se descartó explícitamente: escribir un renderizador ANSI propio en vez de usar `rich` (reinventar una librería madura que el propio usuario pidió); definir un `Protocol` propio para "motor de renderizado" (no hay una segunda implementación que intercambiar — un módulo de confinamiento simple, igual que `llm/factory.py`, es suficiente); refactorizar todos los puntos de llamada de `cli.py` para invocar `presentation/console.py` directamente (innecesario: preservar `_imprimir`/`_leer_entrada` como delegadores logra el mismo resultado con cero riesgo de regresión sobre las 87 pruebas ya existentes); aplicar el indicador de actividad solo al ejemplo literal del spec (búsqueda de logs) en vez de a las 4 llamadas reales de latencia perceptible — se prefirió el alcance más útil ya justificado en `research.md`, pero manteniéndolo acotado a esas 4 llamadas exactas, no a "cualquier operación" de forma especulativa. | PASS |

No se identifican violaciones que requieran registrarse en `Complexity Tracking`. La única
dependencia nueva (`rich`) está justificada explícitamente: es la elección estándar de facto del
ecosistema Python para salida de terminal enriquecida (colores, Markdown, indicadores de
actividad), pedida además de forma explícita por el usuario en la descripción de esta spec.

## Project Structure

### Documentation (this feature)

```text
specs/004-cli-chat-enriquecida/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command) — sin entidades nuevas
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No se genera un directorio `contracts/` nuevo: `presentation/console.py` tiene un único consumidor
(`cli.py`, dentro del mismo proyecto) y no existe un concepto de implementación intercambiable
detrás de él (a diferencia de `chat_model_provider.md`, donde varios proveedores concretos
implementan `BaseChatModel` y varios flujos lo consumen) — mismo criterio ya aplicado por 003 para
justificar la ausencia de `contracts/` en un cambio de orquestación interna de un solo módulo.

### Source Code (repository root)

```text
src/
└── opssleuth/
    ├── __init__.py
    ├── cli.py                       # Modificado:
    │                                 # ~ _imprimir(mensaje, *, es_error=False) -> None: delega en
    │                                 #   presentation.console.mostrar_mensaje_sistema (firma
    │                                 #   ampliada con un parámetro con valor por defecto — no
    │                                 #   rompe ningún call site existente de un solo argumento)
    │                                 # ~ _leer_entrada(prompt) -> str: delega en
    │                                 #   presentation.console.leer_entrada_usuario (firma sin
    │                                 #   cambios)
    │                                 # ~ _procesar_intake / _buscar_y_presentar_apreciacion_logs:
    │                                 #   pasan es_error=True en sus 2 mensajes de fallo de
    │                                 #   proveedor (FR-005)
    │                                 # ~ _procesar_intake, _formular_y_registrar_aclaracion,
    │                                 #   _formular_y_registrar_aclaraciones_combinadas,
    │                                 #   _buscar_y_presentar_apreciacion_logs: envuelven sus
    │                                 #   llamadas a evaluar_descripcion/buscar_evidencia con
    │                                 #   presentation.console.mostrar_actividad(...) (FR-004)
    ├── presentation/                 # Nuevo paquete — único punto de integración con `rich`
    │   ├── __init__.py
    │   └── console.py                 # mostrar_mensaje_sistema(texto, *, es_error=False,
    │                                 # console=None); leer_entrada_usuario(prompt="", *,
    │                                 # console=None) -> str; mostrar_actividad(mensaje, *,
    │                                 # console=None) -> context manager
    ├── domain/                       # Sin cambios (case.py, log_evidence.py)
    ├── llm/                          # Sin cambios (factory.py)
    ├── clarification/                # Sin cambios (engine.py)
    └── evidence/                     # Sin cambios (engine.py, tools.py, agent.py)

tests/
└── unit/
    ├── test_console.py               # Nuevo: prueba presentation/console.py contra un Console
    │                                 # inyectado (io.StringIO(), force_terminal=False) — etiqueta
    │                                 # de rol presente en texto plano, markdown renderizado sin
    │                                 # símbolos crudos, distinción de es_error
    └── test_cli.py                   # Sin cambios (87 pruebas existentes) — _imprimir/
                                      # _leer_entrada preservan sus contratos de llamada
```

**Structure Decision**: Se mantiene el proyecto único ya establecido (Opción 1 del template), sin
paquetes de dominio nuevos. Se añade `presentation/` como paquete nuevo dedicado exclusivamente al
confinamiento de `rich`, siguiendo el mismo patrón ya usado por `llm/` para LangChain en la spec
002 (un paquete nuevo por cada dependencia de terceros que necesita quedar confinada detrás de un
punto de integración único). `cli.py` sigue siendo el único módulo de orquestación/presentación de
la aplicación — este cambio no introduce una segunda capa de presentación paralela, extiende la ya
existente.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — la Constitution Check anterior no registra ningún PASS condicionado a
justificación adicional más allá de la ya incluida en la tabla.
