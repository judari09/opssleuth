# Contrato: Consulta de Evidencia en Base de Datos (agente LangGraph)

Describe el módulo responsable de localizar evidencia relevante en la base de datos configurada y
elaborar una apreciación inicial. Sigue el mismo mecanismo de modularidad central que el resto del
proyecto — una única implementación, parametrizada por `BaseChatModel`
(`specs/002-busqueda-logs/contracts/chat_model_provider.md`), con el bucle agéntico conducido por
LangGraph — mismo patrón que `specs/002-busqueda-logs/contracts/log_search_engine.md`, aplicado
ahora a una fuente de base de datos en vez de una fuente de logs.

## Interfaz

```python
def consultar_evidencia_bd(
    chat_model: BaseChatModel,
    caso: Caso,
    fuente: FuenteDeBaseDeDatosConfigurada,
    anunciar_actividad: Callable[[str], AbstractContextManager],
) -> ApreciacionInicialBD:
    """Conduce un bucle agéntico de uso de herramientas (LangGraph) sobre la
    fuente de base de datos configurada, usando `chat_model` para razonar, con
    el fin de localizar filas relacionadas con el incidente descrito en `caso`
    (usando su descripción y aclaraciones como contexto), y devuelve una
    apreciación inicial (ver data-model.md, ApreciacionInicialBD).
    `anunciar_actividad` se invoca antes de cada consulta real ejecutada contra
    la base de datos (FR-011 de spec.md) — mismo mecanismo ya expuesto por
    `opssleuth.presentation.console.mostrar_actividad` (spec 004), inyectado
    aquí en vez de importado directamente (Principio II: este módulo no debe
    acoplarse a `rich` ni a la capa de presentación)."""
    ...
```

Independiente de `buscar_evidencia` (spec 002) — se invoca por separado, sin depender de que la
evidencia de logs ya se haya explorado (ver Clarifications de `spec.md`, Sesión 2026-09-21,
Pregunta 3).

## Superficie de herramientas

Las 3 herramientas se declaran con el decorador `@tool` de `langchain_core.tools` (esquema de
entrada auto-derivado de las anotaciones de tipo y el docstring de cada función Python — mismo
mecanismo que `contracts/tools_schema.json` de spec 002; ver `contracts/tools_schema.json` de esta
spec para la descripción funcional completa de cada una):

### `listar_tablas_disponibles`

Devuelve los nombres de las tablas a las que esta consulta tiene acceso.

- **Cuándo usarla**: al iniciar el análisis, para saber con qué tablas se puede trabajar, sin
  necesidad de que el modelo adivine o asuma nombres.
- **Parámetros**: ninguno.
- **Devuelve**: lista de nombres de tabla — exactamente `FuenteDeBaseDeDatos.tablas_permitidas`
  (ver `data-model.md`).

### `describir_tabla`

Devuelve las columnas (nombre y tipo) de una tabla permitida.

- **Cuándo usarla**: antes de construir una consulta (simple o con cruces) que referencie esa
  tabla, para conocer sus columnas reales.
- **Parámetros**: `tabla` (cadena).
- **Devuelve**: lista de columnas con su nombre y tipo.
- **Rechaza**: si `tabla` no está en el conjunto permitido — mismo criterio de la Regla 2 más
  abajo, aplicado también a la introspección de esquema (no solo a la ejecución de consultas).

### `ejecutar_consulta_sql`

Valida y ejecuta una consulta de solo lectura contra la base de datos configurada.

- **Cuándo usarla**: para obtener filas concretas relacionadas con el incidente — consultas
  simples (una tabla) o complejas (cruces entre más de dos tablas), según lo requiera el
  diagnóstico (Historias 1 y 3 de `spec.md`).
- **Parámetros**: `consulta` (cadena, texto SQL de una única sentencia `SELECT`).
- **Devuelve**: las filas del resultado (acotadas — ver Regla 4 más abajo), o un error explícito
  si la consulta fue rechazada (Regla 2) o falló al ejecutarse (Regla 5).
- **No devuelve**: más filas de las que el límite acotado permite — si hay más, el resultado lo
  indica explícitamente (`hay_mas`), mismo patrón que `buscar_texto` (spec 002).

## Tipo de retorno: `ApreciacionInicialBD`

Ver `data-model.md` para la forma completa de la entidad.

## Reglas del contrato

1. `consultar_evidencia_bd` DEBE invocarse independientemente de si existe evidencia de logs para
   el caso — nunca condicionada a que `buscar_evidencia` (spec 002) ya se haya ejecutado.
2. Toda consulta propuesta por el modelo DEBE validarse ANTES de ejecutarse contra la base de
   datos real: (a) DEBE parsear como una única sentencia `SELECT`; (b) toda tabla que referencie
   DEBE estar dentro de `FuenteDeBaseDeDatos.tablas_permitidas`. Si cualquiera de las dos
   condiciones falla, la consulta se rechaza sin ejecutarse — nunca se intenta "sanitizar" o
   corregir automáticamente una consulta que no cumple (ver `research.md`, Decisión 2).
3. Toda consulta que sí se ejecute DEBE hacerlo dentro de una conexión/transacción de solo lectura
   cuando el dialecto configurado lo soporte, y NUNCA debe hacerse `commit()` sobre ninguna
   conexión abierta por esta funcionalidad (ver `research.md`, Decisión 3).
4. El volumen de filas devuelto por `ejecutar_consulta_sql` en una sola llamada DEBE estar acotado
   (ver `research.md`, Decisión 5) — nunca debe materializarse en memoria el resultado completo de
   una consulta antes de acotarlo.
5. Errores de comunicación con el proveedor de modelo subyacente DEBEN propagarse como
   `DatabaseSearchEngineError` (definida en `database/engine.py`) — mismo criterio que
   `LogSearchEngineError` (spec 002). Errores de conexión/ejecución contra la base de datos en sí
   (no el proveedor de modelo) DEBEN capturarse dentro de la propia herramienta
   `ejecutar_consulta_sql` y devolverse como un resultado de error explícito al agente (mismo
   patrón que `buscar_texto` devuelve `{"error": ...}` ante un patrón regex inválido), para que el
   agente pueda decidir cómo continuar en vez de que la excepción interrumpa el bucle completo.
6. Antes de invocar al agente (que puede ejecutar 0 o más consultas reales durante su bucle),
   DEBE invocarse `anunciar_actividad` (FR-011 de `spec.md`) — nunca se consulta la base de datos
   de forma silenciosa. Un único anuncio envuelve todo el bucle agéntico de
   `consultar_evidencia_bd`, no uno por cada llamada individual a `ejecutar_consulta_sql` — mismo
   patrón ya usado por `_buscar_y_presentar_apreciacion_logs` (spec 004) al envolver
   `buscar_evidencia` en un único indicador de actividad.
7. El cómputo de `entradas_destacadas` (deduplicación, límite de tamaño) DEBE realizarse en código
   determinista, a partir únicamente de los `ToolMessage` reales producidos por
   `ejecutar_consulta_sql` durante la ejecución del grafo de LangGraph — NUNCA a partir de una
   enumeración libre redactada por el modelo en su respuesta final (mismo principio que Regla 5 de
   `log_search_engine.md`).
8. Cuando ninguna llamada a `ejecutar_consulta_sql` produjo filas relevantes (o no había ninguna
   fuente de base de datos configurada), `resumen` DEBE reflejarlo explícitamente.
9. Toda implementación DEBE aplicar un límite de iteraciones razonable sobre el bucle de LangGraph
   (`MAXIMO_ITERACIONES_AGENTE_BD`), para evitar bucles sin fin — mismo criterio que Regla 7 de
   `log_search_engine.md`.

## Implementación

- Construido sobre un agente LangGraph, mismo mecanismo que `evidence/agent.py` (spec 002) —
  `langchain.agents.create_agent` parametrizado por el `chat_model` recibido y enlazado a las 3
  herramientas de esta spec.
- Con el proveedor Ollama, requiere adicionalmente que el modelo local configurado soporte tool
  calling — mismo requisito ya documentado para el flujo de búsqueda de logs
  (`log_search_engine.md`, sección Implementación).
