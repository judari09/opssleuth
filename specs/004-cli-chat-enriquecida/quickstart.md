# Quickstart: CLI Chat Enriquecida

Guía de validación manual de extremo a extremo para esta funcionalidad. No repite detalles de
diseño — ver `data-model.md` y `research.md` para eso. Requiere que las fases de recepción de
incidencia (001), búsqueda de logs (002) y conversación adaptativa (003) ya estén validadas por
separado — esta spec solo cambia cómo se presenta esa conversación, no su comportamiento.

## Prerrequisitos

- Los mismos de `specs/001-recepcion-incidencia/quickstart.md`,
  `specs/002-busqueda-logs/quickstart.md` y `specs/003-conversacion-adaptativa/quickstart.md`
  (Python 3.13, `uv sync`, proveedor `claude`/`ollama`/`gemini` configurado vía
  `OPSSLEUTH_LLM_PROVIDER`).
- Un archivo de logs de prueba disponible localmente (puede reutilizarse el mismo generador que
  `002-busqueda-logs/quickstart.md`).
- Una terminal con soporte de color (para los escenarios 1 a 4) y, por separado, un mecanismo para
  simular un entorno sin color (para el escenario 5 — ver ese escenario para el comando exacto).

## Ejecutar el agente

Igual que en 001/002/003:

```sh
uv run python -m opssleuth.cli
```

## Escenarios de validación

### 1. Diferenciación visual usuario/sistema (US1 / FR-001, FR-002)

1. Iniciar un caso nuevo y completar 2-3 intercambios (descripción, alguna aclaración).
2. **Esperado**: cada entrada del usuario lleva una etiqueta textual de rol ("Tú" o equivalente)
   reforzada con color/estilo; cada respuesta del sistema lleva una etiqueta textual de rol
   distinta ("OpsSleuth" o equivalente) reforzada con un color/estilo diferente al del usuario.
3. **Esperado**: revisando el historial visible en pantalla tras varios intercambios, se puede
   identificar el origen de cada mensaje sin leer su contenido completo.

### 2. Renderizado legible de contenido estructurado (US2 / FR-003)

1. Completar una búsqueda de evidencia en logs que produzca una apreciación con varios hallazgos
   (ver `002-busqueda-logs/quickstart.md`, escenario 6).
2. **Esperado**: la apreciación se muestra con listas/énfasis renderizados de forma legible (p. ej.
   viñetas, texto en negrita) — sin los símbolos de marcado (`-`, `**`, `#`) visibles como texto
   plano sin procesar.
3. Repetir con una respuesta de una sola línea (p. ej. una pregunta de aclaración simple).
4. **Esperado**: se muestra clara y legible, sin necesitar estructura adicional ni verse afectada
   por el renderizado Markdown.

### 3. Indicador de actividad (US3 / FR-004)

1. Iniciar una búsqueda de evidencia en logs (aportando una fuente válida).
2. **Esperado**: mientras se procesa la búsqueda, aparece una indicación visual de que el sistema
   está trabajando (no una pantalla sin actividad aparente) hasta que el resultado está listo.
3. Repetir observando el momento en que se evalúa la descripción inicial o una respuesta de
   aclaración (justo después de escribirlas).
4. **Esperado**: también en esos momentos aparece una indicación de actividad mientras se espera la
   respuesta del proveedor de modelo.

### 4. Distinción visual de errores (US3 / FR-005)

1. Forzar un error de comunicación con el proveedor configurado (p. ej. una API key inválida
   temporalmente, o desconectando el proveedor local de Ollama si se usa ese proveedor).
2. **Esperado**: el mensaje de error ("No pude evaluar la descripción..." o "No pude completar la
   búsqueda en los logs...") se distingue visualmente (color/marca de advertencia) de una respuesta
   normal del sistema.

### 5. Degradación sin soporte de color (Edge case / FR-006, SC-003)

1. Ejecutar la CLI redirigiendo la salida a un archivo, o forzando la variable de entorno
   `NO_COLOR=1`, y repetir un intercambio breve (descripción + una aclaración).
2. **Esperado**: la CLI se ejecuta sin errores; la salida es texto plano legible; la etiqueta
   textual de rol ("Tú"/"OpsSleuth") sigue apareciendo y permite distinguir el origen de cada
   mensaje, aunque no haya color aplicado.

### 6. No regresión: comportamiento conversacional idéntico (SC-004)

1. Ejecutar íntegramente los escenarios de `specs/001-recepcion-incidencia/quickstart.md`,
   `specs/002-busqueda-logs/quickstart.md` y `specs/003-conversacion-adaptativa/quickstart.md`.
2. **Esperado**: el comportamiento observable (qué se pregunta, cuándo se invita a aportar logs,
   cómo se combinan las aclaraciones, cuándo se dispara la búsqueda de evidencia, qué resultados se
   producen) es idéntico al descrito en esas specs — la única diferencia observable debe ser de
   presentación (etiquetas, color, formato), nunca de secuencia o contenido de la conversación.

## Notas

- Todos los escenarios anteriores corresponden 1:1 a los criterios de aceptación en `spec.md`. Un
  escenario que no se comporte como se describe indica una regresión respecto a la especificación,
  no solo un defecto de esta guía.
- El escenario 6 es el más importante de validar con cuidado: esta spec no debe cambiar ningún
  resultado funcional de 001/002/003, solo su presentación.
