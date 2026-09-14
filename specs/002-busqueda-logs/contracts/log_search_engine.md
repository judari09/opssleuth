# Contrato: Búsqueda de Evidencia en Logs (agente LangGraph)

Describe el módulo responsable de localizar evidencia relevante dentro de una o más fuentes de
logs y elaborar una apreciación inicial consolidada. A diferencia del diseño original de esta
spec (un `Protocol` propio `LogSearchEngine` con dos implementaciones por proveedor), esta versión
usa el mismo mecanismo de modularidad central que el resto del proyecto: una única
implementación, parametrizada por `BaseChatModel` (ver `contracts/chat_model_provider.md`), con el
bucle agéntico conducido por LangGraph — ver `research.md`, Decisiones 1 y 3, para el porqué de
este cambio de diseño.

## Interfaz

```python
def buscar_evidencia(
    chat_model: BaseChatModel,
    caso: Caso,
    fuentes: list[FuenteDeLogs],
    preguntar_callback: Callable[[str], str],
) -> ApreciacionInicialLogs:
    """Conduce un bucle agéntico de uso de herramientas (LangGraph) sobre
    `fuentes`, usando `chat_model` para razonar, con el fin de localizar
    entradas relacionadas con el incidente descrito en `caso` (usando su
    descripción, aclaraciones y `creado_en` como contexto), y devuelve una
    única apreciación inicial consolidada entre todas las fuentes (ver
    data-model.md, ApreciacionInicialLogs). `preguntar_callback` es invocado
    cuando el agente necesita contexto adicional del proyecto (US4/FR-011) —
    recibe la pregunta como texto y devuelve la respuesta del usuario."""
    ...
```

Una única función/módulo sirve para ambos proveedores — no existen ya `ClaudeLogSearchEngine`
ni `OllamaLogSearchEngine` como clases separadas; la diferencia entre proveedores queda
completamente confinada a qué instancia de `BaseChatModel` se le pasa (construida por
`crear_modelo_chat()`).

## Superficie de herramientas

Las 4 herramientas se declaran con el decorador `@tool` de `langchain_core.tools` (esquema de
entrada auto-derivado de las anotaciones de tipo y el docstring de cada función Python — ver
`research.md`, Decisión 4, y `contracts/tools_schema.json` para la descripción funcional completa
de cada una, ahora usada como referencia de contenido para los docstrings de las funciones
decoradas en vez de como JSON Schema consumido directamente):

### `buscar_texto`

Busca un patrón de expresión regular dentro de la fuente de logs actualmente activa.

- **Cuándo usarla**: para localizar líneas que mencionen un término, componente, código de error
  o patrón de fecha/hora específico, sin leer el archivo completo.
- **Parámetros**: `patron` (cadena, expresión regular), `maximo_resultados` (entero, por defecto
  20 — límite superior de coincidencias devueltas en una sola llamada).
- **Devuelve**: lista de coincidencias, cada una con `numero_linea`, `contenido` (la línea
  completa) y una pequeña ventana de líneas de contexto inmediatamente antes/después.
- **No devuelve**: el archivo completo ni un conteo exhaustivo de todas las coincidencias más
  allá de `maximo_resultados` — si hay más, el resultado lo indica explícitamente.

### `leer_contexto`

Lee un rango de líneas alrededor de un número de línea específico.

- **Cuándo usarla**: después de `buscar_texto`, cuando la ventana de contexto por defecto de una
  coincidencia no es suficiente.
- **Parámetros**: `numero_linea` (entero), `lineas_antes` (entero, por defecto 5),
  `lineas_despues` (entero, por defecto 5).
- **Devuelve**: las líneas solicitadas con su número de línea.

### `contar_lineas`

Cuenta el total de líneas de la fuente de logs actualmente activa.

- **Cuándo usarla**: al iniciar el análisis de una fuente, para calibrar si es un archivo pequeño
  o grande.
- **Parámetros**: ninguno.
- **Devuelve**: el número total de líneas.

### `preguntar_al_usuario`

Pausa el bucle y solicita información al usuario por la línea de comandos (human-in-the-loop).

- **Cuándo usarla**: únicamente cuando el contenido de los logs o del problema descrito no puede
  interpretarse sin conocer más sobre el proyecto o sistema al que pertenecen (US4/FR-011). No
  usarla cuando el contenido ya es interpretable por sí mismo (FR-012).
- **Parámetros**: `pregunta` (cadena).
- **Devuelve**: la respuesta del usuario como texto libre.
- **Efecto**: bloquea el bucle hasta que el usuario responde por la CLI, invocando
  `preguntar_callback` recibido por el módulo (mediante cierre/closure o el mecanismo de LangGraph
  para argumentos de herramienta inyectados en tiempo de ejecución — ver `research.md`, Decisión
  4, nota de implementación) — nunca accede a `stdin`/`stdout` directamente (preserva Inversión de
  Dependencias, Regla 4 más abajo).

## Tipo de retorno: `ApreciacionInicialLogs`

Ver `data-model.md` para la forma completa de la entidad — sin cambios respecto al diseño
original.

## Reglas del contrato

1. `buscar_evidencia` DEBE consolidar los hallazgos de todas las `fuentes` recibidas en una única
   `ApreciacionInicialLogs` — nunca una apreciación independiente por fuente (FR-010a).
2. El comportamiento observable DEBE ser idéntico independientemente de si `chat_model` es una
   instancia de `ChatAnthropic` o `ChatOllama` — sustituibilidad garantizada por `BaseChatModel`,
   no por dos implementaciones separadas.
3. Errores de comunicación con el proveedor subyacente DEBEN propagarse como
   `LogSearchEngineError` (definida en un módulo de dominio de esta funcionalidad), nunca como una
   excepción específica de LangChain o del SDK subyacente — el mapeo exacto de tipos de excepción
   a capturar se confirma durante la implementación (ver `research.md`, Decisión 1, nota de
   riesgo).
4. La herramienta `preguntar_al_usuario` NUNCA accede directamente a `stdin`/`stdout`; DEBE
   invocar el `preguntar_callback` recibido como parámetro de `buscar_evidencia`.
5. El cómputo de `entradas_destacadas` (deduplicación, límite de tamaño ante volúmenes grandes —
   FR-009a) DEBE realizarse en código determinista, a partir únicamente de los `ToolMessage`
   reales producidos durante la ejecución del grafo de LangGraph — NUNCA a partir de una
   enumeración libre redactada por el modelo en su respuesta final (ver `research.md`, Decisión
   6).
6. Cuando ninguna llamada a herramienta produjo resultados relevantes para ninguna fuente,
   `resumen` DEBE reflejarlo explícitamente (FR-008, SC-003).
7. Toda implementación DEBE aplicar algún límite de iteraciones razonable sobre el bucle de
   LangGraph, para evitar bucles sin fin.

## Implementación

- Construido sobre un agente LangGraph (p. ej. `langgraph.prebuilt.create_react_agent`, o un
  `StateGraph` a medida si el bookkeeping determinista de la Regla 5 lo requiere — ver
  `research.md`, Decisión 3) parametrizado por el `chat_model` recibido.
- Con el proveedor Ollama, requiere adicionalmente que el modelo local configurado
  (`OPSSLEUTH_OLLAMA_MODEL`) soporte tool calling — no todo modelo que sirve para el flujo de
  aclaración (que no usa herramientas) sirve necesariamente para este flujo; esta es una
  diferencia de requisitos nueva respecto a 001 que DEBE documentarse al usuario (p. ej. en la
  guía de quickstart y en mensajes de error si el modelo configurado no soporta tool calling).
