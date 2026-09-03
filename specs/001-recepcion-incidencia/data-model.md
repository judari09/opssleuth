# Data Model: Recepción de Incidencia

Entidades derivadas de `spec.md` (sección "Key Entities"), sin detalles de persistencia
(este alcance no incluye almacenamiento duradero — ver `research.md`, Decisión 2).

## Caso

Representa una incidencia individual en investigación dentro de una conversación.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `str` | Identificador único del caso dentro de la conversación (p. ej. UUID o secuencial). |
| `descripcion_inicial` | `DescripcionProblema \| None` | Descripción original aportada por el usuario. `None` antes de FR-001/FR-002. |
| `aclaraciones` | `list[Aclaracion]` | Historial de pares pregunta/respuesta de aclaración, en orden cronológico. |
| `estado_informacion` | `Literal["pendiente_descripcion", "pendiente_aclaracion", "completa"]` | Estado de completitud de la información recopilada. |
| `estado_caso` | `Literal["activo", "finalizado"]` | Estado del ciclo de vida del caso (FR-013, FR-014). |
| `mensajes` | `list[dict]` | Historial de mensajes (`role`, `content`) enviados/recibidos de la API de Claude, usado como contexto multi-turno (RF2). |

**Reglas de validación**:
- Un `Caso` no puede pasar a `estado_informacion = "completa"` sin `descripcion_inicial`
  distinta de vacía/sin contenido interpretable (FR-011).
- Solo un `Caso` puede estar `activo` por conversación a la vez (FR-014).
- `estado_caso = "finalizado"` es un estado terminal para ese caso; un nuevo caso en la
  misma conversación es una instancia distinta de `Caso` (FR-013).

**Transiciones de estado** (`estado_informacion`):

```
pendiente_descripcion --(FR-001/FR-002: se recibe descripción)--> pendiente_aclaracion | completa
pendiente_aclaracion --(FR-006/FR-007: evaluación determina campos faltantes)--> pendiente_aclaracion
pendiente_aclaracion --(FR-008/FR-009: aclaraciones suficientes, o FR-010: usuario no puede aportar más)--> completa
```

## DescripcionProblema

El relato inicial en lenguaje natural que el usuario aporta sobre el error o incidencia.

| Campo | Tipo | Descripción |
|---|---|---|
| `texto` | `str` | Texto original tal como lo escribió el usuario. |
| `sistema_afectado` | `CampoExtraido` | Evaluación de presencia/valor del sistema o aplicación afectada (FR-006). |
| `sintoma` | `CampoExtraido` | Evaluación de presencia/valor del síntoma o error observado. |
| `momento` | `CampoExtraido` | Evaluación de presencia/valor del momento o frecuencia de ocurrencia. |

## CampoExtraido

Resultado de la evaluación de un campo requerido dentro de una descripción o aclaración.
Corresponde a la salida estructurada (structured output) del motor de aclaración — ver
`contracts/evaluacion_schema.json`.

| Campo | Tipo | Descripción |
|---|---|---|
| `presente` | `bool` | Si el campo está presente en el texto evaluado. |
| `valor` | `str \| None` | Valor extraído del texto si `presente = true`; `None` en caso contrario. |

## Aclaracion

Par de pregunta formulada por el sistema y respuesta aportada por el usuario (FR-007,
FR-008), generado cuando la descripción inicial (o una aclaración previa) resulta
insuficiente.

| Campo | Tipo | Descripción |
|---|---|---|
| `pregunta` | `str` | Pregunta puntual formulada por el sistema, dirigida a un campo faltante específico o a la confirmación del problema principal. |
| `campo_objetivo` | `Literal["sistema_afectado", "sintoma", "momento", "problema_principal"]` | A qué campo requerido apunta la pregunta. `"problema_principal"` se usa cuando la evaluación detecta múltiples problemas en la descripción inicial (Edge Case "descripción extremadamente extensa con múltiples problemas mezclados", spec.md) y se pide al usuario confirmar cuál investigar. |
| `respuesta` | `str \| None` | Respuesta del usuario; `None` mientras está pendiente de respuesta. |
| `sin_confirmar` | `bool` | `true` si el usuario indicó explícitamente que no puede aportar más información para este campo (FR-010), dejando constancia de que quedó sin confirmar. |
| `contradice_descripcion_original` | `bool` | `true` si el sistema detectó que esta respuesta contradice la descripción original o una aclaración previa (`EvaluacionDescripcion.contradiccion.detectada`, Edge Case "el usuario aporta información que contradice lo dicho en la descripción original", spec.md). Ambos valores (el original y el nuevo) se conservan en `Caso.mensajes`/`Caso.aclaraciones`; este campo solo marca la inconsistencia para que se señale al usuario, nunca descarta ninguno de los dos. |

## Relaciones

```
Caso 1 ── 0..1 DescripcionProblema
Caso 1 ── 0..* Aclaracion
DescripcionProblema 1 ── 3 CampoExtraido (sistema_afectado, sintoma, momento)
```
