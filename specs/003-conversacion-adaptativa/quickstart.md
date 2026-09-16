# Quickstart: Conversación Adaptativa

Guía de validación manual de extremo a extremo para esta funcionalidad. No repite detalles de
diseño — ver `data-model.md` y `research.md` para eso. Requiere que las fases de recepción de
incidencia (001) y búsqueda de logs (002) ya estén validadas por separado — esta spec solo
cambia *cuándo* dentro de esos flujos se puede aportar información, no su comportamiento interno.

## Prerrequisitos

- Los mismos de `specs/001-recepcion-incidencia/quickstart.md` y
  `specs/002-busqueda-logs/quickstart.md` (Python 3.13, `uv sync`, proveedor `claude`/`ollama`/
  `gemini` configurado vía `OPSSLEUTH_LLM_PROVIDER`).
- Un archivo de logs de prueba disponible localmente (puede reutilizarse el mismo generador que
  `002-busqueda-logs/quickstart.md`).

## Ejecutar el agente

Igual que en 001/002:

```sh
uv run python -m opssleuth.cli
```

Los escenarios siguientes son idénticos independientemente del proveedor configurado.

## Escenarios de validación

### 1. Descripción + ruta de logs en el mismo mensaje inicial (US1 / FR-001, FR-002)

1. Iniciar un caso nuevo y, en el primer mensaje, escribir una descripción completa del
   problema junto con la ruta al archivo de logs de prueba (p. ej. "el servicio de facturación
   empezó a fallar a las 14:15, el log está en test_logs/facturacion.log").
2. **Esperado**: el sistema registra la descripción y confirma la fuente de logs, **sin**
   formular la pregunta "¿puedes aportar los logs relacionados?".
3. **Esperado**: la búsqueda de evidencia se dispara igual que en el escenario 1 de
   `002-busqueda-logs/quickstart.md`, usando esa fuente.

### 2. Ruta inválida aportada en el mensaje inicial (US1 / FR-003)

1. Iniciar un caso nuevo con un mensaje que combine la descripción y una ruta de logs que no
   existe (p. ej. `no-existe.log`).
2. **Esperado**: el sistema conserva la descripción, completa la recepción con normalidad, y
   solo al llegar al punto en que hoy se dispararía la búsqueda de evidencia informa que no
   pudo acceder a esa ruta — no antes, no intercalado con las preguntas de aclaración (si las
   hubiera).
3. **Esperado**: a partir de ahí, el sistema permite indicar otra ruta o pegar los logs
   directamente, igual que en el escenario 1 de `002-busqueda-logs/quickstart.md`.

### 3. Contenido pegado en el mensaje inicial — fuera de alcance (US1, Edge Case)

1. Iniciar un caso nuevo y, en el primer mensaje, escribir solo la descripción del problema
   seguida de varias líneas de log pegadas (sin forma de ruta de archivo).
2. **Esperado**: el sistema NO trata ese contenido como evidencia de logs automáticamente;
   registra la descripción con normalidad y, al completar la recepción, sigue invitando
   explícitamente a aportar logs mediante el paso dedicado ya existente.

### 4. Responder de una vez el lote inicial de aclaraciones (US2 / FR-004, FR-005)

1. Iniciar un caso nuevo con una descripción a la que le falten 2 campos (p. ej. solo el
   síntoma: "el sistema falla").
2. **Esperado**: el sistema presenta las preguntas pendientes (sistema afectado, momento) en un
   único turno.
3. Responder en un solo mensaje cubriendo ambos datos (p. ej. "es el servicio de facturación,
   pasó ayer a las 14:15").
4. **Esperado**: el sistema registra ambos datos y no vuelve a preguntar por ninguno de los dos
   campos ya cubiertos.

### 5. Respuesta combinada parcial (US2 / FR-005)

1. Repetir el escenario 4, pero responder cubriendo solo uno de los dos campos pendientes.
2. **Esperado**: el sistema registra el dato aportado y sigue preguntando, ahora una por una
   (comportamiento existente de 001), únicamente por el campo que sigue faltando.

### 6. Respuesta combinada ambigua (US2 / FR-006, Edge Case)

1. Repetir el escenario 4, pero responder con un mensaje sin relación clara con los campos
   pendientes (p. ej. "no estoy seguro").
2. **Esperado**: el sistema mantiene el comportamiento de aclaración existente — no inventa una
   correlación incorrecta; si el mensaje se interpreta como "no puedo aportar más información"
   (FR-010 de 001), lo marca como dato sin confirmar; si no, vuelve a preguntar.
3. Repetir con una respuesta combinada que contradiga un dato ya confirmado antes en la
   conversación (p. ej. menciona un sistema distinto al ya registrado).
4. **Esperado**: el sistema señala la posible inconsistencia, igual que ya hace hoy para una
   respuesta individual (edge case de contradicción, spec 001).

### 7. No regresión: escenarios de 001 y 002 sin combinar información (US3 / FR-007, FR-008, FR-009)

1. Ejecutar íntegramente los escenarios de `specs/001-recepcion-incidencia/quickstart.md` y
   `specs/002-busqueda-logs/quickstart.md`, aportando la información paso a paso como allí se
   describe (sin combinar descripción+logs ni respuestas de aclaración).
2. **Esperado**: el comportamiento observable es idéntico al descrito en esas specs — mismas
   preguntas formuladas una por una, misma invitación explícita a aportar logs, mismo
   comportamiento de confirmación de "problema principal" ante múltiples problemas.

## Notas

- Todos los escenarios anteriores corresponden 1:1 a los criterios de aceptación en `spec.md`.
  Un escenario que no se comporte como se describe indica una regresión respecto a la
  especificación, no solo un defecto de esta guía.
- El escenario 3 documenta explícitamente un comportamiento *fuera de alcance* (contenido
  pegado en el mensaje inicial) — su resultado esperado es que el sistema se comporte igual
  que antes de esta spec, no una funcionalidad nueva a validar.
