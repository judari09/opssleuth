# Research: Búsqueda en Archivos de Logs

## Decisión 0: Arquitectura de búsqueda — agente con uso de herramientas (tool use), no llamada única

**Decisión**: A diferencia de 001 (una sola llamada estructurada por evaluación), RF2 exige que
el modelo *localice* información dentro de un archivo potencialmente grande sin cargarlo
completo. Esto requiere un bucle agéntico de uso de herramientas (tool use): el modelo decide
qué buscar, ejecuta búsquedas acotadas, inspecciona resultados y repite hasta tener evidencia
suficiente para elaborar la apreciación inicial.

**Rationale**: Cargar el archivo completo en el contexto contradice explícitamente RF2 ("reduciendo
así el gasto de tokens al intentar leer todo el archivo") y no escala a los archivos de
"cientos de miles de líneas" de SC-001. Un bucle de tool use permite que el modelo ejecute
búsquedas dirigidas (por patrón, por rango horario) y solo reciba en el contexto los fragmentos
relevantes.

**Alternatives considered**:
- Cargar el archivo completo (truncado) en el contexto: rechazado — viola RF2/SC-001
  directamente y no es viable para archivos grandes.
- Pre-procesamiento determinista (grep externo) sin intervención del modelo, seguido de una sola
  llamada de resumen: rechazado como decisión única — el modelo necesita poder iterar (ver
  Decisión 3 más abajo) y ajustar su búsqueda cuando el primer intento no encuentra nada
  relevante (US2, Escenario 4) o necesita pedir contexto de proyecto (US4).

## Decisión 1: Adopción de LangChain/LangGraph como capa de abstracción de modelo — y ampliación de alcance a migrar el motor de 001

**Decisión (revisada — reemplaza la decisión original de esta sección)**: Se adopta el
ecosistema LangChain/LangGraph como la capa de abstracción sobre proveedores de modelo de
lenguaje para **todo** el proyecto, no solo para esta funcionalidad. Concretamente:

- `langchain_core.language_models.BaseChatModel` sustituye al contrato `Protocol` propio
  (`ClarificationEngine`) como el mecanismo de intercambiabilidad entre Claude y Ollama —
  amparado por la excepción de "estándar de abstracción de terceros maduro" añadida al
  Principio II de la constitución (v1.1.0, ver `.specify/memory/constitution.md`).
- El alcance de esta spec (002) se amplía explícitamente, por decisión directa del usuario, para
  incluir la **migración** del motor de aclaración de 001 (`ClarificationEngine`,
  `ClaudeClarificationEngine`, `OllamaClarificationEngine`, `clarification/factory.py`) a esta
  misma arquitectura basada en LangChain, además de construir el motor de búsqueda de logs nuevo
  directamente sobre ella. Esta migración se trata como trabajo de esta spec (tareas dedicadas en
  `tasks.md`), no como una spec separada.
- Una única función de fábrica compartida, `crear_modelo_chat() -> BaseChatModel`
  (`src/opssleuth/llm/factory.py`, nueva ubicación compartida — ver Project Structure en
  `plan.md`), reemplaza tanto a `clarification/factory.py` (001) como al `evidence/factory.py`
  que se había planificado originalmente para 002. Lee las mismas variables de entorno ya
  establecidas (`OPSSLEUTH_LLM_PROVIDER`, `OPSSLEUTH_OLLAMA_MODEL`) y devuelve una instancia
  configurada de `ChatAnthropic` (paquete `langchain-anthropic`) o `ChatOllama` (paquete
  `langchain-ollama`).
- Tanto el flujo de aclaración (001, migrado) como el de búsqueda de logs (002, nuevo) dependen
  únicamente del tipo abstracto `BaseChatModel` — nunca de `ChatAnthropic`/`ChatOllama`
  directamente ni de los SDKs `anthropic`/`ollama` en código de negocio — preservando Inversión
  de Dependencias (Principio I) dentro de la excepción constitucional.

**Rationale**: El usuario solicitó explícitamente esta adopción, señalando la interfaz estándar
que LangChain provee entre distintos proveedores de modelo como forma de favorecer la
modularidad. Evaluado contra la constitución: el Principio II original exigía que toda
dependencia externa se expusiera "detrás de una capa de abstracción **propia del proyecto**" —
en tensión directa con usar `BaseChatModel` como el contrato mismo. Se resolvió mediante una
enmienda explícita a la constitución (v1.0.0 → v1.1.0, MINOR) que permite que un estándar de
terceros maduro cumpla ese rol cuando envolverlo en una interfaz propia sería una capa redundante
sin comportamiento adicional (lo cual violaría, a su vez, el Principio IV de simplicidad). Esta
resolución se documenta en el propio archivo de la constitución (Sync Impact Report) y aquí, para
que quede trazable la razón del cambio de arquitectura entre 001 y 002.

Un beneficio concreto y verificable de esta adopción, más allá del argumento de "interfaz
estándar": desaparece la necesidad de dos factories separadas (una por motor) y de dos clases de
adaptador por proveedor (`ClaudeXEngine`/`OllamaXEngine`) en cada motor — ver Decisión 3 más
abajo, donde además desaparece la asimetría Tool Runner (Claude) vs. bucle manual (Ollama) que la
arquitectura original de 002 había planificado, porque `BaseChatModel.bind_tools()` es una
operación estándar disponible en ambos proveedores vía LangChain.

**Alternatives considered**:
- Mantener el patrón `Protocol` propio de 001 sin cambios, y construir 002 sobre él (decisión
  original de esta sección, ver historial de research.md previo a esta revisión): descartado por
  decisión explícita del usuario, quien priorizó la interfaz estándar de LangChain sobre mantener
  el mecanismo de modularidad hecho a medida.
- Adoptar LangChain solo para 002 (motor nuevo) y dejar 001 con su arquitectura original: 
  descartado por decisión explícita del usuario ("extiende el alcance de esta spec a modernizar
  los engine anteriores") — tener dos mecanismos de modularidad distintos conviviendo en el mismo
  proyecto (Protocol propio para aclaración, LangChain para búsqueda) sería en sí mismo una forma
  de inconsistencia arquitectónica que el Principio II busca evitar.
- Envolver `BaseChatModel` en un `Protocol` propio adicional (mantener la superficie de 001
  intacta, con LangChain como implementación oculta detrás): esta era la opción "B" evaluada con
  el usuario (LangChain como detalle de implementación bajo el contrato propio); el usuario
  eligió explícitamente la opción contraria (LangChain reemplaza el contrato propio).

**Nota de riesgo a verificar durante la implementación**: la sintaxis exacta de
`with_structured_output`, `bind_tools`, la jerarquía de excepciones de `langchain_core` y las
construcciones de LangGraph (`create_react_agent` vs. un `StateGraph` a medida) referenciadas en
este documento se describen a nivel conceptual, con base en conceptos estables y ampliamente
documentados del ecosistema LangChain/LangGraph. Este proyecto no cuenta con una skill/fuente de
documentación en vivo dedicada a LangChain (a diferencia de la skill `claude-api` usada para
verificar los detalles de la API de Anthropic) — por lo tanto, antes de implementar cada tarea que
use estas construcciones, se DEBE verificar la sintaxis exacta contra la documentación instalada
(versión fijada en `pyproject.toml`) en vez de asumir que el nombre de método o parámetro descrito
aquí es literal.

## Decisión 2: Modelo de Claude — reutilizar `claude-sonnet-5`, sin escalar a Opus

**Decisión**: El proveedor Claude, ahora instanciado como `ChatAnthropic(model="claude-sonnet-5",
...)`, mantiene `claude-sonnet-5` como modelo por defecto (mismo modelo que 001), con un nivel de
esfuerzo/razonamiento moderado como punto de partida para el flujo de búsqueda de logs (ver nota
de riesgo: el mecanismo exacto para pasar `effort`/parámetros equivalentes de la API de Claude a
través de `ChatAnthropic` debe verificarse contra la documentación de `langchain-anthropic`
instalada).

**Rationale**: `ESTADO_SPECS.md` establece `claude-sonnet-5` como decisión compartida y exige no
cambiar a Opus sin justificar una necesidad concreta de mayor capacidad — no existe tal necesidad
aquí: tanto la evaluación de descripciones (001) como la búsqueda-y-resumen de logs (002) son
tareas acotadas, no problemas de razonamiento de horizonte largo. La adopción de LangChain no
cambia esta decisión — solo cambia el mecanismo de instanciación del modelo, no el modelo elegido.

**Alternatives considered**:
- `claude-opus-5`: rechazado — mayor costo sin que la tarea lo justifique; contradice la decisión
  compartida en ESTADO_SPECS.md.
- `claude-haiku-4-5`: rechazado — capacidad de tool use agéntico y de razonamiento sobre
  fragmentos de logs ambiguos es menos fiable en el tier más económico; el ahorro no compensa el
  riesgo de apreciaciones de baja calidad (SC-003).

## Decisión 3: LangGraph como bucle agéntico unificado — una sola implementación para ambos proveedores

**Decisión (revisada — reemplaza la decisión original "Tool Runner vs. bucle manual" de esta
sección)**: El bucle agéntico de búsqueda de logs se implementa una única vez, usando LangGraph
(p. ej. el agente ReAct preconstruido `langgraph.prebuilt.create_react_agent`, o un `StateGraph`
a medida si se necesita control más fino sobre el bookkeeping determinista de la Decisión 6),
parametrizado por cualquier `BaseChatModel` — Claude u Ollama. No existen ya dos clases de
adaptador por proveedor (`ClaudeLogSearchEngine`/`OllamaLogSearchEngine`); existe una única
función/módulo de orquestación del agente que recibe el `BaseChatModel` ya configurado (vía
`crear_modelo_chat()`) como parámetro.

**Rationale**: La asimetría original (Tool Runner del SDK de Anthropic para Claude, bucle manual
para Ollama) era una consecuencia directa de que cada SDK (`anthropic`, `ollama`) expone
mecanismos de tool use distintos y no intercambiables. Al construir sobre `BaseChatModel`, el
método estándar de LangChain para enlazar herramientas (`.bind_tools(...)`) y el bucle de
ejecución que ofrece LangGraph son los mismos independientemente del proveedor subyacente — la
asimetría desaparece por construcción. Esto es una simplificación genuina (Principio IV): menos
código propio que mantener, y una demostración más fuerte de intercambiabilidad (Principio II)
que la arquitectura original, porque ahora es literalmente el mismo código el que se ejecuta con
cualquiera de los dos proveedores, no solo el mismo contrato implementado dos veces.

**Alternatives considered**:
- Mantener Tool Runner (Claude) + bucle manual (Ollama) como en la decisión original de esta
  sección: descartado — ya no aplica una vez que ambos proveedores se acceden vía la misma
  interfaz `BaseChatModel`; mantenerlo introduciría complejidad sin justificación (Principio IV).
- Un `StateGraph` de LangGraph completamente a medida desde el inicio, en vez de partir del
  agente ReAct preconstruido: se deja como decisión de implementación, no de arquitectura — el
  agente preconstruido es el punto de partida por simplicidad (Principio IV), y solo se
  reemplazaría por un grafo a medida si el bookkeeping determinista de la Decisión 6 no puede
  implementarse limpiamente como una capa alrededor de él (a evaluar durante la implementación).

## Decisión 4: Superficie de herramientas — 4 herramientas, sin parser de tiempo dedicado

**Decisión**: Se exponen 4 herramientas al modelo, ahora definidas con el decorador `@tool` de
LangChain (`langchain_core.tools`), que genera automáticamente el esquema de entrada a partir de
las anotaciones de tipo y el docstring de cada función Python (mismo espíritu que el decorador
`@beta_tool` del SDK de Anthropic usado en el diseño original, pero estándar entre proveedores):

1. `buscar_texto(patron, maximo_resultados)` — búsqueda por expresión regular sobre la fuente de
   logs activa, devolviendo hasta N coincidencias con su número de línea y una pequeña ventana de
   contexto por coincidencia.
2. `leer_contexto(numero_linea, lineas_antes, lineas_despues)` — devuelve las líneas alrededor de
   un número de línea específico, para ampliar el contexto de un hallazgo puntual.
3. `contar_lineas()` — devuelve el total de líneas de la fuente activa, para que el modelo pueda
   calibrar si un archivo es pequeño (quizás inspeccionable casi completo) o grande (requiere
   búsqueda dirigida).
4. `preguntar_al_usuario(pregunta)` — herramienta human-in-the-loop: pausa el bucle, imprime la
   pregunta en la CLI, lee la respuesta del usuario y la devuelve como resultado de la
   herramienta. Es el mecanismo concreto detrás de US4/FR-011 (solicitar contexto del proyecto).
   La inyección del callback de pregunta/respuesta (sin acoplar la herramienta a `stdin`/`stdout`
   directamente — Regla 4 del contrato) se implementa mediante un cierre (closure) que captura
   `preguntar_callback`, o mediante el mecanismo de LangGraph para argumentos de herramienta
   inyectados en tiempo de ejecución sin exponerlos al esquema que ve el modelo — la opción
   concreta se decide durante la implementación (ver nota de riesgo, Decisión 1).

No se introduce una herramienta separada de "búsqueda por rango horario". Cuando el caso tiene un
horario de incidente conocido (vía `Caso.creado_en` y/o el campo `momento` de la descripción), la
instrucción del sistema guía al modelo a construir el propio patrón regex de fecha/hora para
`buscar_texto` (p. ej. `2026-09-0[23]T1[4-6]:`), en vez de mantener un parser de formatos de
timestamp dedicado.

**Rationale**: Los formatos de timestamp en logs varían enormemente entre proyectos; construir y
mantener un parser genérico y fiable contradice el Principio IV para un caso de uso donde regex ya
resuelve el problema, delegando en el modelo la tarea de adaptar el patrón al formato real
observado. Mantener las herramientas en un número reducido (4) también sigue la guía de diseño de
superficie de herramientas: pocas herramientas con límites claros.

**Alternatives considered**:
- Herramienta dedicada `buscar_por_rango_horario(inicio, fin)` con parser de timestamps
  incorporado: rechazada — complejidad de parsing multiformato no justificada (Principio IV).
- Exponer lectura directa de rangos de bytes/offsets en vez de números de línea: rechazada — los
  logs son texto orientado a líneas (ver Assumptions de spec.md).

## Decisión 5: Anclaje temporal — extensión de `Caso` con `creado_en`

**Decisión**: Se añade el campo `creado_en: datetime` a la entidad `Caso` (ver `data-model.md`),
poblado automáticamente al crear el caso. Sirve como referencia temporal de respaldo cuando el
campo `momento` de la descripción del problema es relativo ("hace una hora", "esta mañana") en vez
de una hora absoluta.

**Rationale**: FR-006 exige aislar entradas de log por horario cuando se dispone de la hora del
incidente, pero esa hora suele expresarse de forma relativa en el lenguaje natural del usuario. Sin
un ancla temporal absoluta en el contexto del caso, el modelo no puede traducir "hace una hora" a
un patrón de búsqueda útil.

**Alternatives considered**:
- Pedir siempre al usuario una hora absoluta explícita: rechazado — no es coherente con cómo ya
  funciona `momento` en 001 (campo de texto libre).
- No añadir ningún anclaje temporal y dejar que el modelo asuma la hora actual del sistema
  operativo: rechazado — no es determinista ni reproducible en pruebas.

## Decisión 6: Cómputo determinista de `entradas_destacadas`, no auto-enumeración del LLM

**Decisión**: Igual que en 001 (transformación determinista, sin segunda llamada al modelo), la
lista final de `entradas_destacadas` en `ApreciacionInicialLogs` se acota y deduplica en código de
aplicación a partir de los resultados reales devueltos por las llamadas a
`buscar_texto`/`leer_contexto` durante el bucle de LangGraph, no mediante una enumeración libre
que el modelo redacte en su respuesta final. Con LangGraph, esto se implementa inspeccionando los
mensajes `ToolMessage` reales del estado del grafo tras cada ejecución de herramienta, en vez de
depender del texto de la respuesta final del modelo.

**Rationale**: FR-009a exige limitar la apreciación a "un conjunto acotado de entradas
representativas" cuando hay muchas coincidencias. Dejar que el modelo enumere manualmente esas
entradas en su texto de salida arriesga que invente o repita entradas que no observó realmente
(SC-003). Registrar de forma determinista cada entrada efectivamente recuperada vía herramientas
garantiza trazabilidad.

**Alternatives considered**:
- Pedir al modelo que enumere las entradas relevantes como parte de su respuesta de texto final:
  rechazado — riesgo de alucinación; dificulta la consolidación entre varias fuentes (FR-010a).

## Decisión 7: Consolidación entre varias fuentes de logs

**Decisión**: La función/módulo de orquestación del agente recibe la lista completa de
`FuenteDeLogs` del caso y es responsable de producir una única `ApreciacionInicialLogs`
consolidada (FR-010a). Cada fuente se busca de forma independiente (una fuente activa a la vez
para las herramientas de búsqueda), pero el bookkeeping determinista (Decisión 6) acumula
`entradas_destacadas` de todas las fuentes antes de aplicar el límite/deduplicación final y de
pedir al modelo la síntesis textual de la apreciación.

**Rationale**: Es la interpretación directa de FR-010a y de la clarificación de sesión
correspondiente. Mantener la búsqueda por fuente independiente evita la complejidad de
herramientas que operen sobre múltiples archivos simultáneamente.

**Alternatives considered**:
- Una apreciación independiente por fuente, luego una llamada adicional de "resumen de resúmenes":
  rechazado explícitamente por la clarificación de sesión y por Principio IV.

## Decisión 8: Almacenamiento de archivos generados a partir de logs pegados (RF3/FR-003/FR-015)

**Decisión**: Cuando el contenido pegado por el usuario supera el umbral de 4 líneas, se escribe a
un archivo temporal (vía el módulo estándar `tempfile`, con sufijo `.log` y un nombre legible)
dentro del directorio temporal del sistema. La ruta completa se informa al usuario (FR-015) antes
de continuar, y esa ruta se registra como una `FuenteDeLogs` de tipo "generada".

**Rationale**: `tempfile` es la solución estándar de la librería estándar de Python, sin
dependencias nuevas (Principio IV). No persistir de forma duradera es coherente con la decisión ya
establecida en 001/ESTADO_SPECS.md.

**Alternatives considered**:
- Mantener el contenido pegado únicamente en memoria sin escribir a disco: rechazado — FR-015
  exige informar una "ubicación/nombre" de archivo.

## Decisión 9: Migración del motor de 001 — alcance y estrategia de regresión

**Decisión**: La migración de `ClarificationEngine` (001) a la nueva arquitectura se trata como
un refactor de comportamiento preservado: `EvaluacionDescripcion`, `Aclaracion` y el resto de las
entidades de dominio de 001 no cambian; solo cambia el mecanismo de invocación del modelo. Se
reemplaza la jerarquía `ClarificationEngine` (Protocol) + `ClaudeClarificationEngine` +
`OllamaClarificationEngine` por una función simple `evaluar_descripcion(chat_model: BaseChatModel,
texto: str, contexto: list[dict]) -> EvaluacionDescripcion`, usando el método estándar de
`BaseChatModel` para salida estructurada (equivalente a `messages.parse()`/`output_config.format`
de la API de Claude, ahora expuesto de forma uniforme por LangChain). `generar_preguntas()` se
mantiene sin cambios de comportamiento — sigue siendo una transformación determinista sin llamada
adicional al modelo (Regla 5 del contrato original, preservada como regla de la nueva
implementación). Las pruebas existentes (`test_claude_engine.py`, `test_ollama_engine.py`) se
migran para mockear `BaseChatModel`/`ChatAnthropic`/`ChatOllama` en vez del cliente `anthropic`/
`ollama` crudo, preservando la intención de cada caso de prueba (detección de campos,
contradicción, múltiples problemas, propagación de errores).

**Rationale**: El usuario decidió explícitamente incluir esta migración dentro del alcance de 002.
Tratarla como refactor de comportamiento preservado (no como reescritura de reglas de negocio)
minimiza el riesgo sobre una funcionalidad ya validada en producción de pruebas (46/46 antes de
esta migración) — el `quickstart.md` de 001 sigue siendo la referencia de comportamiento esperado
y DEBE re-ejecutarse como prueba de regresión tras la migración (ver `quickstart.md` de esta spec).

**Alternatives considered**:
- Mantener `ClaudeClarificationEngine`/`OllamaClarificationEngine` como subclases delgadas sobre
  `BaseChatModel` (conservando la jerarquía de clases original): rechazado — con `BaseChatModel`
  ya unificando el comportamiento entre proveedores, mantener dos clases que no difieren en
  comportamiento (solo en qué instancia de `BaseChatModel` reciben) es una capa sin justificación
  (Principio IV); una función parametrizada por `BaseChatModel` es la forma más simple.

## Nuevas dependencias

Se añaden a `pyproject.toml` (como tarea de implementación, no en esta fase de planificación):
`langchain-core`, `langchain-anthropic`, `langchain-ollama`, `langgraph`. Los paquetes `anthropic`
y `ollama` permanecen como dependencias transitivas (usadas internamente por
`langchain-anthropic`/`langchain-ollama`), pero dejan de importarse directamente en código de
negocio de `opssleuth` — solo dentro de la función de fábrica compartida (ver Decisión 1).
`pydantic` se mantiene (usado por `EvaluacionDescripcion` y por la salida estructurada vía
`BaseChatModel.with_structured_output`, que en LangChain también se define con modelos Pydantic).

## Variables de entorno y configuración

No se introducen variables de entorno nuevas. Se reutilizan `OPSSLEUTH_LLM_PROVIDER`
(`claude`|`ollama`) y `OPSSLEUTH_OLLAMA_MODEL`, ya establecidas en 001, ahora leídas por la única
función de fábrica compartida `crear_modelo_chat()` en `src/opssleuth/llm/factory.py`.
