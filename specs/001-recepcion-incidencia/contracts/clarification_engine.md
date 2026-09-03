# Contrato: Motor de Aclaración (ClarificationEngine)

Este es el contrato arquitectónico (Principio II de la constitución) que debe implementar
cualquier motor usado para evaluar descripciones de incidencias y generar preguntas de
aclaración. La implementación inicial usa la API de Claude (ver `research.md`, Decisión 0),
pero el resto del sistema (gestión de `Caso`, CLI) solo depende de esta interfaz — nunca de
la implementación concreta.

## Interfaz (Python `Protocol`)

```python
class ClarificationEngine(Protocol):
    def evaluar(self, texto: str, contexto: list[dict]) -> EvaluacionDescripcion:
        """Evalúa `texto` dado el `contexto` (historial de la conversación del caso):
        (a) si cubre los 3 campos requeridos, (b) si contradice información ya
        presente en `contexto` (relevante al evaluar respuestas de aclaración), y
        (c) si describe más de un problema distinto (relevante al evaluar la
        descripción inicial). Una sola llamada al modelo produce las tres
        evaluaciones a la vez — ver EvaluacionDescripcion."""
        ...

    def generar_preguntas(
        self, evaluacion: EvaluacionDescripcion, contexto: list[dict]
    ) -> list[Aclaracion]:
        """Transforma `evaluacion.preguntas_sugeridas` (ya producido por `evaluar`)
        en objetos `Aclaracion` con `respuesta=None`. Es una transformación
        determinista — NO realiza una llamada adicional al modelo (ver Regla 5)."""
        ...
```

## Tipo de retorno: `EvaluacionDescripcion`

Corresponde a la salida estructurada (structured output) definida en
`evaluacion_schema.json`. Contiene:

- Para cada uno de los 3 campos requeridos (`sistema_afectado`, `sintoma`, `momento`): si
  está presente y su valor extraído.
- `preguntas_sugeridas`: preguntas puntuales para los campos ausentes, y opcionalmente una
  pregunta con `campo_objetivo="problema_principal"` cuando se detectan múltiples problemas.
- `contradiccion`: si el texto evaluado contradice el contexto previo, y una descripción
  breve de la inconsistencia (Edge Case "el usuario aporta información que contradice lo
  dicho en la descripción original", spec.md).
- `multiples_problemas`: si el texto evaluado describe más de un problema distinto, y las
  etiquetas de cada uno (Edge Case "descripción extremadamente extensa con múltiples
  problemas mezclados", spec.md).

## Reglas del contrato

1. `evaluar` NO DEBE tener efectos secundarios sobre el `Caso`; solo devuelve el resultado
   de la evaluación (principio de responsabilidad única).
2. `generar_preguntas` NO DEBE generar más preguntas que campos ausentes en `evaluacion` más,
   si aplica, la pregunta de confirmación de problema principal (máximo 4: `sistema_afectado`,
   `sintoma`, `momento`, `problema_principal`).
3. Cualquier implementación alternativa (p. ej. basada en reglas, u otro proveedor de LLM)
   DEBE poder sustituir a la implementación basada en Claude sin requerir cambios en el
   código consumidor (`Caso`, CLI) — Principio II (Sustitución de Liskov aplicada al
   contrato).
4. Errores de comunicación con el proveedor subyacente DEBEN propagarse como
   `ClarificationEngineError` (definida en `engine.py`), nunca como una excepción específica
   del SDK del proveedor, para no acoplar a los consumidores a la implementación concreta.
   Cada implementación DEBE capturar las excepciones propias de su SDK subyacente y
   relanzarlas como `ClarificationEngineError` (conservando la excepción original como
   `__cause__`): en `ClaudeClarificationEngine`, como mínimo `anthropic.APIError` y
   `anthropic.APIConnectionError`; en `OllamaClarificationEngine`, como mínimo
   `ollama.ResponseError` y errores de conexión (p. ej. `ConnectionError`) al no encontrar una
   instancia de Ollama accesible.
5. `generar_preguntas` DEBE ser una transformación determinista de
   `evaluacion.preguntas_sugeridas` en `list[Aclaracion]` (con `respuesta=None`,
   `sin_confirmar=False`, `contradice_descripcion_original=False`) — NO DEBE realizar una
   llamada adicional al modelo subyacente. La generación de las preguntas ocurre íntegramente
   dentro de `evaluar`, en la misma llamada estructurada que evalúa los campos, las
   contradicciones y los múltiples problemas (evita una segunda llamada redundante al modelo,
   Principio IV).
6. Cuando `evaluacion.contradiccion.detectada = true`, la implementación consumidora (CLI)
   DEBE conservar ambos valores en el contexto del `Caso` — el motor NUNCA descarta uno de
   los dos silenciosamente; solo señala la inconsistencia (ver `data-model.md`,
   `Aclaracion.contradice_descripcion_original`).

## Implementaciones de referencia

Existen dos implementaciones concretas de este contrato en esta fase, para demostrar y
verificar en código la modularidad exigida por el Principio II (ver `research.md`,
Decisión 4). Ambas devuelven el mismo tipo `EvaluacionDescripcion` y son intercambiables sin
cambios en `Caso` ni en la CLI.

### `ClaudeClarificationEngine` (proveedor remoto por defecto)

- Usa `anthropic.Anthropic().messages.parse(...)` con `output_config.format` apuntando al
  esquema de `evaluacion_schema.json` (ver `research.md`, Decisión 3).
- Modelo: `claude-sonnet-5` (ver `research.md`, Decisión 1).
- El historial de conversación (`contexto`) se reenvía como `messages` en cada llamada,
  dado que la API de Claude es sin estado (ver `research.md`, Decisión 2).
- Requiere `ANTHROPIC_API_KEY` (o perfil `ant auth login`) y acceso de red saliente.

### `OllamaClarificationEngine` (proveedor local alternativo)

- Usa el cliente oficial `ollama` (p. ej. `ollama.chat(model=..., messages=..., format=
  <json_schema>)`) contra una instancia de Ollama accesible localmente
  (`http://localhost:11434` por defecto).
- Modelo: configurable por el usuario vía `OPSSLEUTH_OLLAMA_MODEL` (sin valor por defecto
  fijado en el código — depende de qué modelos tenga descargados el usuario; ver
  `research.md`, Decisión 4).
- El historial de conversación (`contexto`) se reenvía igual que en `ClaudeClarificationEngine`
  — el contrato no distingue entre proveedores en este aspecto.
- No requiere red saliente ni credenciales de Anthropic; requiere que Ollama esté en
  ejecución localmente con el modelo configurado ya descargado (`ollama pull <modelo>`).
- **Nota documentada (regla 4 del contrato)**: la fiabilidad de la salida estructurada
  depende del modelo local elegido por el usuario; puede ser menor que con Claude según el
  modelo. Esto no rompe el contrato — sigue devolviendo `EvaluacionDescripcion` válida o
  lanzando `ClarificationEngineError` — pero es una diferencia de comportamiento conocida
  entre implementaciones que se deja documentada aquí.

### Selección del proveedor: `factory.py`

Una única función de fábrica (`crear_motor_aclaracion() -> ClarificationEngine`) lee la
variable de entorno `OPSSLEUTH_LLM_PROVIDER` (`claude` por defecto, o `ollama`) y devuelve la
implementación correspondiente. Es el único punto del sistema que importa ambos módulos de
implementación (`claude_engine.py`, `ollama_engine.py`); todo lo demás depende solo de
`ClarificationEngine`.
