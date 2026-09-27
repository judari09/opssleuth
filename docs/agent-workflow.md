# Flujo del agente (LangGraph)

Los dos motores de búsqueda de evidencia del proyecto —
[`evidence.agent`](reference/evidence.md) (logs) y
[`database.agent`](reference/database.md) (bases de datos) — no implementan
cada uno su propio bucle de decisión. Ambos llaman a
`langchain.agents.create_agent`, que construye y compila **el mismo grafo de
LangGraph** (el patrón ReAct de "razonar → actuar → observar"), parametrizado
por tres cosas distintas en cada caso: el `BaseChatModel` inyectado, el
conjunto de herramientas (`@tool`) enlazadas, y el prompt de sistema.

## El grafo

<img src="../assets/agent-graph.svg" alt="Grafo del agente: START, agent, tools, END" width="100%">

1. **`START → agent`**: el grafo arranca invocando al modelo con el prompt de
   sistema (construido por `construir_instrucciones_sistema(caso, ...)` —
   incluye el contexto del incidente y, para el agente de logs, el ancla
   temporal `Caso.creado_en`) y el mensaje inicial que pide iniciar la
   búsqueda.
2. **`agent`**: el nodo invoca `chat_model.bind_tools(herramientas).invoke(...)`.
   La respuesta puede traer texto, una o más `tool_calls`, o ambos.
3. **Decisión**: si la respuesta trae `tool_calls`, el grafo continúa hacia
   `tools`; si no, es la respuesta final y el grafo termina en `END`.
4. **`tools`**: ejecuta cada `tool_call` pendiente (p. ej. `buscar_texto` o
   `ejecutar_consulta_sql`) y añade su resultado al estado como un
   `ToolMessage`.
5. **`tools → agent`** (bucle): el modelo vuelve a invocarse, ahora con los
   `ToolMessage` en el historial, y el ciclo se repite hasta que decide que
   ya tiene suficiente evidencia.

Este bucle está acotado por `config={"recursion_limit": MAXIMO_ITERACIONES_AGENTE}`
(15 en ambos agentes) al invocar el grafo — nunca puede quedarse dando
vueltas indefinidamente sobre una fuente que no produce evidencia útil.

## Dos agentes, un mismo grafo

| | `evidence.agent` (búsqueda en logs) | `database.agent` (consulta a BD) |
| --- | --- | --- |
| Herramientas | `buscar_texto`, `leer_contexto`, `contar_lineas`, `preguntar_al_usuario` | `listar_tablas_disponibles`, `describir_tabla`, `ejecutar_consulta_sql` |
| Recurso ligado por cierre | ruta del archivo activo (`FuenteDeLogs.ruta`) | `Engine` de SQLAlchemy + tablas permitidas |
| Barandilla de seguridad | ninguna herramienta escribe; la búsqueda es de solo lectura por diseño | `validar_consulta()` (`sqlglot`): rechaza cualquier cosa que no sea un único `SELECT` sobre tablas permitidas, **antes** de tocar el `Engine` |
| Se invoca | una vez por `FuenteDeLogs` (varias fuentes → varios agentes, resultados consolidados) | una vez por conversación, sobre la única fuente configurada |
| Puede pausarse a mitad de análisis | sí — `preguntar_al_usuario` interrumpe para pedir contexto del proyecto que no puede inferirse de los logs | no — toda la información que necesita está en el esquema (`describir_tabla`) |

Las herramientas nunca exponen el recurso al que están ligadas como parámetro
visible para el modelo: `crear_herramientas_busqueda(ruta_archivo)` y
`crear_herramientas_bd(fuente)` son fábricas que capturan ese recurso por
cierre (closure), así que el esquema de la herramienta que ve el modelo (y
que efectivamente decide invocar) solo contiene los argumentos de negocio
(`patron`, `consulta`, etc.), nunca una ruta de archivo o una cadena de
conexión.

## De `ToolMessage` a apreciación — nunca al revés

Ambos motores de orquestación (`evidence.engine.buscar_evidencia`,
`database.engine.consultar_evidencia_bd`) aplican la misma regla al terminar
la invocación del grafo: las entradas que se muestran al usuario
(`EntradaLogRelevante`, `EntradaBDRelevante`) se extraen **únicamente** de los
`ToolMessage` reales que aparecen en `resultado["messages"]` — nunca del
texto libre de la respuesta final del modelo. Si el modelo redacta una
apreciación que menciona una entrada que su propia herramienta no devolvió,
esa entrada simplemente no aparece en `entradas_destacadas`. Este es el mismo
principio de "cómputo determinista sobre auto-enumeración del LLM" descrito
en [Arquitectura](architecture.md#iv-simplicidad-ante-todo).

## Cuándo el agente le pregunta a un humano

`preguntar_al_usuario` (solo en el agente de logs) es la única herramienta
que no consulta la fuente de evidencia — pausa el grafo, entrega el control a
un callback provisto por el llamador (`_preguntar_al_usuario_cli` en la CLI),
y reanuda con la respuesta como `ToolMessage`. El prompt de sistema es
explícito sobre cuándo usarla: únicamente cuando el contenido de los logs usa
terminología o convenciones propias del proyecto que el modelo no puede
interpretar sin más contexto — nunca como sustituto de una búsqueda adicional
que el propio agente podría hacer con `buscar_texto`.

## Errores del proveedor, no del grafo

Cualquier excepción que el proveedor subyacente (Anthropic, Google, Ollama)
propague durante `agente.invoke(...)` se captura ampliamente y se relanza
como `LogSearchEngineError`/`DatabaseSearchEngineError` (conservando la causa
original), para que la capa de negocio nunca dependa de tipos de excepción
específicos de un SDK concreto. Los errores de *ejecución* de una consulta
SQL contra la base de datos, en cambio, **no** se propagan así: se capturan
dentro de la propia herramienta `ejecutar_consulta_sql` y se devuelven al
agente como un resultado de error explícito en el `ToolMessage` — así el
bucle puede reaccionar (p. ej. reformular la consulta) en vez de
interrumpirse.
