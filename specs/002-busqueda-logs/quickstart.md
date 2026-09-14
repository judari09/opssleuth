# Quickstart: Búsqueda en Archivos de Logs

Guía de validación manual de extremo a extremo para esta funcionalidad. No repite detalles de
diseño — ver `data-model.md` y `contracts/` para eso. Requiere que la fase de recepción de
incidencia (001) ya haya sido validada por separado — esta funcionalidad se activa a
continuación de ella (FR-014).

## Prerrequisitos

- Los mismos de `specs/001-recepcion-incidencia/quickstart.md` (Python 3.13, `uv sync`,
  proveedor Claude u Ollama configurado vía `OPSSLEUTH_LLM_PROVIDER`).
- Un archivo de logs de prueba disponible localmente. Puede generarse uno mínimo así:

  ```sh
  printf '2026-09-03T14:01:02 INFO servicio-facturacion iniciado\n2026-09-03T14:02:10 INFO factura creada id=1001\n2026-09-03T14:15:47 ERROR servicio-facturacion timeout al conectar con base de datos\n2026-09-03T14:15:48 ERROR factura id=1002 fallo con codigo 500\n2026-09-03T14:20:00 INFO factura creada id=1003\n' > /tmp/facturacion.log
  ```

## Ejecutar el agente

Igual que en 001:

```sh
uv run python -m opssleuth.cli
```

Con el proveedor local (Ollama), para validar la modularidad del motor de búsqueda igual que
ya se hizo para el de aclaración:

```sh
export OPSSLEUTH_LLM_PROVIDER=ollama
export OPSSLEUTH_OLLAMA_MODEL=<modelo-descargado-con-soporte-de-tool-calling>
uv run python -m opssleuth.cli
```

**Nota**: a diferencia del flujo de aclaración (que no usa herramientas), el flujo de búsqueda
de logs requiere que el modelo local configurado soporte tool calling (`bind_tools` vía
LangChain). No todo modelo válido para el escenario 1 de
`001-recepcion-incidencia/quickstart.md` sirve necesariamente aquí — verificar la nota de
memoria del proyecto sobre modelos locales fiables (`qwen2.5:7b-instruct` confirmado con salida
estructurada; su soporte de tool calling debe verificarse por separado antes de asumirlo).

Los escenarios siguientes son idénticos independientemente del proveedor configurado.

## Escenarios de validación

### 1. Invitación proactiva y aporte por ruta de archivo (US1 / FR-001, FR-002, FR-014)

1. Completar la recepción de una incidencia (ver `001-recepcion-incidencia/quickstart.md`,
   escenario 1) con una descripción completa, p. ej. sobre el servicio de facturación.
2. **Esperado**: en cuanto la información de la descripción queda completa, el sistema invita
   proactivamente a aportar logs, sin que el usuario tenga que pedirlo.
3. Indicar la ruta al archivo de prueba (`/tmp/facturacion.log`).
4. **Esperado**: el sistema confirma que registró esa fuente de logs para el caso.
5. Repetir el paso 3 con una ruta inexistente (p. ej. `/tmp/no-existe.log`).
6. **Esperado**: el sistema informa que no pudo acceder al archivo y permite indicar otra ruta
   o pegar los logs directamente, en vez de fallar sin explicación.

### 2. Aporte de logs pegados en el chat (US1 / FR-003, FR-004, FR-015)

1. Con un caso activo sin fuente de logs aún, pegar en el chat 3 líneas de log (por debajo del
   umbral de 4).
2. **Esperado**: el sistema usa ese contenido directamente sin generar un archivo.
3. Iniciar un caso nuevo y, esta vez, pegar 6 líneas de log.
4. **Esperado**: el sistema informa que generó un archivo con ese contenido, indicando su
   ubicación/nombre, antes de continuar con la búsqueda (FR-015) — el contenido no se envía
   directamente como contexto del modelo.

### 3. Localización de entradas por horario conocido (US2 / FR-005, FR-006)

1. Con el archivo de prueba aportado, y una descripción/aclaración que indique un momento del
   incidente cercano a `14:15` (p. ej. "empezó a fallar sobre las 14:15").
2. **Esperado**: el sistema aísla y prioriza las entradas de ese horario (las líneas `ERROR` de
   `14:15:47`/`14:15:48`), sin requerir que el usuario indique manualmente dónde están en el
   archivo.

### 4. Localización sin horario conocido (US2 / FR-007)

1. Repetir el escenario 3 pero con una descripción que no menciona ninguna hora.
2. **Esperado**: el sistema localiza igualmente las entradas relevantes basándose en el
   sistema afectado/síntoma descritos (p. ej. buscando por "facturacion" o "ERROR").

### 5. Sin coincidencias (US2 / FR-008, SC-003)

1. Aportar un archivo de logs que no contiene ninguna entrada relacionada con el problema
   descrito (p. ej. logs de un componente completamente distinto).
2. **Esperado**: el sistema informa explícitamente que no encontró entradas relacionadas con
   el incidente, en vez de omitir el resultado o fabricar una apreciación sin evidencia real.

### 6. Apreciación inicial y persistencia en el contexto (US3 / FR-009, FR-010)

1. Continuando el escenario 3 (coincidencias encontradas), dejar que el sistema concluya la
   búsqueda.
2. **Esperado**: el sistema presenta una apreciación inicial coherente con las entradas
   `ERROR` encontradas (timeout de base de datos, fallo con código 500).
3. Continuar la conversación varios intercambios más y pedir al sistema que recuerde lo
   encontrado en los logs.
4. **Esperado**: la apreciación sigue disponible en el contexto del caso sin tener que repetir
   la búsqueda.

### 7. Volumen grande de coincidencias (Edge case / FR-009a)

1. Generar un archivo de logs con varios cientos de líneas `ERROR` relacionadas con el mismo
   componente descrito.
2. **Esperado**: la apreciación inicial se limita a un conjunto acotado de entradas
   representativas e indica explícitamente que existen más coincidencias disponibles, en vez
   de intentar listarlas todas.

### 8. Varias fuentes de logs consolidadas (Edge case / FR-013, FR-010a)

1. Aportar una segunda fuente de logs para el mismo caso (otra ruta de archivo distinta, o
   pegando contenido adicional).
2. **Esperado**: el sistema permite analizar ambas fuentes, y produce una única apreciación
   inicial consolidada que combina hallazgos de ambas — no dos apreciaciones separadas.

### 9. Solicitud de contexto del proyecto (US4 / FR-011, FR-012)

1. Aportar un archivo de logs que use terminología o códigos internos no explicados en la
   descripción del problema (p. ej. `codigo_interno=X471` sin contexto previo).
2. **Esperado**: el sistema pregunta al usuario por contexto general del proyecto antes de
   continuar, y una vez respondida, incorpora esa información para interpretar los logs.
3. Repetir con un archivo de logs cuyo contenido es claro y autoexplicativo.
4. **Esperado**: el sistema NO formula preguntas de contexto de proyecto innecesarias.

### 10. Regresión: migración del motor de aclaración a LangChain (Decisión 9)

Esta spec amplía su alcance para migrar `ClarificationEngine` (001) a la nueva arquitectura
basada en `BaseChatModel` (ver `research.md`, Decisión 9, y
`contracts/clarification_migration.md`). El comportamiento observable NO debe cambiar.

1. Ejecutar íntegramente los escenarios 1 a 5 de
   `specs/001-recepcion-incidencia/quickstart.md` (captura de descripción, persistencia de
   contexto, aclaración ante ambigüedad, "no puedo aportar más", casos secuenciales,
   descripción vacía) contra el código migrado.
2. **Esperado**: todos los escenarios se comportan exactamente igual que antes de la migración
   — mismas preguntas formuladas, misma detección de contradicciones/múltiples problemas, mismo
   límite de 4 preguntas. Cualquier diferencia de comportamiento observable es una regresión de
   la migración, no un cambio de alcance aceptable.
3. Repetir con ambos proveedores (`OPSSLEUTH_LLM_PROVIDER=claude` y `=ollama`) para confirmar que
   la sustituibilidad garantizada por `BaseChatModel` sigue siendo real en la práctica, no solo
   en el contrato.

## Notas

- Todos los escenarios anteriores corresponden 1:1 a los criterios de aceptación en `spec.md`.
  Un escenario que no se comporte como se describe indica una regresión respecto a la
  especificación, no solo un defecto de esta guía.
- La generación de una respuesta final/diagnóstico a partir de la apreciación producida aquí
  está explícitamente fuera de alcance de esta spec (ver `spec.md`, Assumptions) — no debe
  validarse como parte de este quickstart.
