# Contrato: Migración del Motor de Aclaración (001) a LangChain

Este documento describe el resultado de migrar el motor de aclaración de incidencias — ya
implementado y probado en 001 — a la arquitectura basada en LangChain adoptada por esta spec (ver
`research.md`, Decisiones 1 y 9). **Supersede** a
[`specs/001-recepcion-incidencia/contracts/clarification_engine.md`](../../001-recepcion-incidencia/contracts/clarification_engine.md)
como descripción del mecanismo de intercambiabilidad — ese documento se conserva como registro
histórico de la arquitectura original (con una nota que apunta aquí), no se reescribe.

## Qué cambia y qué no cambia

**No cambia** (comportamiento y entidades de dominio, ver
[`specs/001-recepcion-incidencia/data-model.md`](../../001-recepcion-incidencia/data-model.md)):

- `EvaluacionDescripcion`, `CampoExtraidoLLM`, `PreguntaSugerida`, `Contradiccion`,
  `MultiplesProblemas`, `Aclaracion` — mismos campos, mismas reglas de validación.
- Las 6 reglas de comportamiento del contrato original de 001 (sin efectos secundarios en
  `evaluar`; máximo 4 preguntas; sustituibilidad; errores envueltos en excepción de dominio;
  `generar_preguntas` determinista sin llamada adicional al modelo; contradicciones preservan
  ambos valores) — se preservan íntegramente, ahora como reglas de la función migrada (ver más
  abajo).
- El esquema de salida estructurada (`evaluacion_schema.json`, en
  `001-recepcion-incidencia/contracts/`) — sigue siendo el esquema objetivo de la salida
  estructurada, ahora obtenida vía el mecanismo estándar de `BaseChatModel` en vez de
  `messages.parse()`/`output_config.format` nativo de la API de Claude.

**Sí cambia** (mecanismo de invocación del modelo):

- La jerarquía `ClarificationEngine` (Protocol) + `ClaudeClarificationEngine` +
  `OllamaClarificationEngine` se reemplaza por una función simple, parametrizada por
  `BaseChatModel` (ver `contracts/chat_model_provider.md`).
- `clarification/factory.py` se elimina — la selección de proveedor pasa a `crear_modelo_chat()`
  (compartida con el flujo de búsqueda de logs).

## Interfaz migrada

```python
def evaluar_descripcion(
    chat_model: BaseChatModel, texto: str, contexto: list[dict]
) -> EvaluacionDescripcion:
    """Evalúa `texto` dado el `contexto` (historial de la conversación del caso)
    usando `chat_model` para obtener EvaluacionDescripcion como salida
    estructurada (equivalente funcional a ClarificationEngine.evaluar original).
    Sin efectos secundarios sobre el Caso (Regla 1 preservada)."""
    ...


def generar_preguntas(
    evaluacion: EvaluacionDescripcion, contexto: list[dict]
) -> list[Aclaracion]:
    """Sin cambios respecto a la implementación original de 001 — transformación
    determinista de evaluacion.preguntas_sugeridas, sin llamada adicional al
    modelo (Regla 5 preservada). No depende de BaseChatModel en absoluto."""
    ...
```

`generar_preguntas` no recibe `chat_model` porque nunca lo necesitó — sigue siendo pura lógica de
transformación, ahora expuesta como función de módulo en vez de método de una clase base
compartida (`BaseClarificationEngine`), que deja de existir como tal.

## Reglas del contrato (preservadas de 001, adaptadas a la nueva forma)

1. `evaluar_descripcion` NO DEBE tener efectos secundarios sobre el `Caso`.
2. `generar_preguntas` NO DEBE generar más de 4 preguntas (`sistema_afectado`, `sintoma`,
   `momento`, `problema_principal`).
3. El comportamiento observable (mismas entradas → misma clase de salida) DEBE ser idéntico
   independientemente de si `chat_model` es una instancia de `ChatAnthropic` o `ChatOllama` —
   sustituibilidad ahora garantizada por `BaseChatModel` en vez de por dos clases que implementan
   el mismo `Protocol`.
4. Errores de comunicación con el proveedor subyacente DEBEN propagarse como
   `ClarificationEngineError` (definida en `clarification/engine.py`, preservada). La
   implementación migrada DEBE capturar las excepciones que LangChain/el integration package
   correspondiente propaguen y relanzarlas como `ClarificationEngineError` (conservando la
   excepción original como `__cause__`) — el mapeo exacto de tipos de excepción de
   `langchain_core`/`langchain-anthropic`/`langchain-ollama` a capturar se confirma durante la
   implementación (ver `research.md`, Decisión 1, nota de riesgo).
5. `generar_preguntas` DEBE seguir siendo una transformación determinista — NO DEBE realizar una
   llamada adicional a `chat_model`.
6. Cuando `evaluacion.contradiccion.detectada = true`, la CLI DEBE seguir conservando ambos
   valores en el contexto del `Caso` — sin cambios respecto a 001.

## Estrategia de migración de pruebas

`tests/unit/test_claude_engine.py` y `tests/unit/test_ollama_engine.py` se migran (no se
reescriben desde cero) a `tests/unit/test_evaluar_descripcion.py`, preservando cada caso de
prueba existente (detección de campos presentes/ausentes, detección de contradicción, detección
de múltiples problemas, propagación de errores como `ClarificationEngineError`), pero mockeando
`BaseChatModel`/la instancia concreta correspondiente en vez del cliente `anthropic`/`ollama`
crudo. El `quickstart.md` de 001 (escenarios 1–5) DEBE volver a ejecutarse manualmente como prueba
de regresión tras la migración — ver `quickstart.md` de esta spec, sección de regresión.
