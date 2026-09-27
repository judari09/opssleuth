# Pruebas y calidad

## Ejecutar la suite

```sh
uv run pytest tests/
```

Todas las pruebas viven bajo `tests/unit/` y se ejecutan sin necesidad de
credenciales de ningún proveedor real: los `BaseChatModel`/`Engine` se
sustituyen por dobles de prueba (fakes/stubs) inyectados directamente —
consecuencia directa de que la lógica de negocio solo dependa de tipos
abstractos (Principio II).

## Qué cubre cada módulo de pruebas

| Archivo | Cubre |
| --- | --- |
| `test_case.py` | Entidades de dominio de `domain/case.py` (`Caso`, `campos_faltantes`, `resumen`). |
| `test_log_evidence.py` / `test_database_evidence.py` | Entidades de dominio de evidencia de logs/BD. |
| `test_evaluar_descripcion.py` | Motor de aclaración (`clarification.engine`) con un `BaseChatModel` fake. |
| `test_buscar_evidencia.py` | Orquestación de `evidence.engine.buscar_evidencia` — extracción determinista de `ToolMessage`, consolidación entre fuentes, límites. |
| `test_tools.py` | Herramientas de `evidence.tools` (`buscar_texto`, `leer_contexto`, `contar_lineas`, `preguntar_al_usuario`) contra archivos reales en disco. |
| `test_consultar_evidencia_bd.py` | Orquestación de `database.engine.consultar_evidencia_bd`. |
| `test_database_tools.py` | Herramientas de `database.tools`, incluida la barandilla de seguridad end-to-end contra una BD SQLite real. |
| `test_database_validacion.py` | `validar_consulta()` — casos de SQL inválido, múltiples sentencias, tablas fuera de alcance, CTEs. |
| `test_database_factory.py` | `crear_motor_bd()` — variable no configurada, tablas inexistentes, error de conexión. |
| `test_cli.py` | Bucle conversacional completo (`ejecutar_conversacion`), incluida la detección de ruta de logs en el mensaje inicial y las aclaraciones combinadas. |
| `test_console.py` | Presentación (`presentation.console`): etiquetas de rol, degradado a ASCII del banner, indicador de actividad. |

## Cómo se prueban los flujos con LLM sin llamar a un proveedor real

Tanto `evaluar_descripcion` como los dos agentes (`evidence.agent`,
`database.agent`) reciben el `BaseChatModel` como parámetro — las pruebas
inyectan una implementación fake de `BaseChatModel` que responde de forma
determinista (incluida su forma de `bind_tools`), en vez de mockear un SDK de
proveedor concreto. Esto es posible precisamente porque ningún módulo de
negocio importa `langchain_anthropic`/`langchain_ollama`/`langchain_google_genai`
directamente (Principio II) — el punto de inyección es siempre el tipo
abstracto.

## Validación manual end-to-end

Cada spec bajo `specs/*/quickstart.md` documenta escenarios de validación
manual paso a paso (con un proveedor real) que complementan la suite
automatizada — útiles para verificar comportamiento dependiente del modelo
subyacente (p. ej. si un modelo local concreto soporta tool calling de forma
fiable) que una prueba unitaria con un fake no puede capturar.

## Estado actual

La suite completa pasa en verde (`uv run pytest tests/`); el número exacto de
pruebas crece con cada spec — ver `specs/ESTADO_SPECS.md` para el conteo
registrado al cierre de cada una.
