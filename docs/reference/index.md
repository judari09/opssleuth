# Referencia de código

Esta sección se genera automáticamente a partir de los docstrings numpydoc de
`src/opssleuth/` (vía [mkdocstrings](https://mkdocstrings.github.io/)) —
nunca se escribe a mano por separado, así que nunca queda desincronizada del
código fuente (Principio III de la constitución). Los miembros privados
(prefijo `_`) se omiten deliberadamente: reflejan detalles de implementación
interna, no el contrato público del módulo.

| Paquete | Contiene |
| --- | --- |
| [`domain`](domain.md) | Entidades puras (`Caso`, `FuenteDeLogs`, `FuenteDeBaseDeDatos`, apreciaciones...). Sin dependencias de terceros. |
| [`clarification`](clarification.md) | `evaluar_descripcion` / `generar_preguntas` — motor de aclaración de la recepción de incidencias. |
| [`evidence`](evidence.md) | Herramientas, agente y motor de orquestación de la búsqueda de evidencia en logs. |
| [`database`](database.md) | Fábrica de conexión, validación de consultas, herramientas, agente y motor de orquestación de la consulta a bases de datos. |
| [`llm`](llm.md) | `crear_modelo_chat()` — único punto de construcción de un `BaseChatModel`. |
| [`presentation`](presentation.md) | Renderizado de la CLI (etiquetas de rol, Markdown, indicador de actividad, banner). |
| [`cli`](cli.md) | Punto de entrada y bucle conversacional que orquesta todo lo anterior. |

Si buscas *cómo encajan* estos módulos entre sí en vez de la firma exacta de
una función, empieza por [Arquitectura](../architecture.md) o
[Flujo del agente](../agent-workflow.md).
