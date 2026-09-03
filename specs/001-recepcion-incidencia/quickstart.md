# Quickstart: Recepción de Incidencia

Guía de validación manual de extremo a extremo para esta funcionalidad. No repite detalles
de diseño — ver `data-model.md` y `contracts/` para eso.

## Prerrequisitos

- Python 3.13 (`.python-version`).
- Dependencias instaladas: `anthropic`, `ollama`, `pydantic` (ver `research.md`).
- Según el proveedor de modelo elegido (`OPSSLEUTH_LLM_PROVIDER`, ver más abajo):
  - **Claude** (por defecto): variable de entorno `ANTHROPIC_API_KEY`, o un perfil activo
    vía `ant auth login`.
  - **Ollama** (local): una instancia de Ollama en ejecución localmente
    (`http://localhost:11434` por defecto) con el modelo deseado ya descargado
    (`ollama pull <modelo>`).

## Instalación

```sh
uv sync
```

## Ejecutar el agente

Con el proveedor por defecto (Claude):

```sh
uv run python -m opssleuth.cli
```

Con el proveedor local (Ollama) — demuestra la modularidad del motor de aclaración
(Principio II):

```sh
export OPSSLEUTH_LLM_PROVIDER=ollama
export OPSSLEUTH_OLLAMA_MODEL=<modelo-descargado-en-ollama>
uv run python -m opssleuth.cli
```

Los escenarios de validación siguientes son idénticos independientemente del proveedor
configurado — el comportamiento observable del sistema no debe depender de cuál esté activo,
solo la infraestructura subyacente.

## Escenarios de validación

### 1. Captura de descripción inicial (US1 / FR-001, FR-002, FR-003)

1. Ejecutar el CLI. **Esperado**: el sistema solicita explícitamente la descripción del
   problema antes de cualquier otra cosa.
2. Escribir una descripción completa, p. ej.: *"Desde ayer el módulo de facturación de la
   app de ventas devuelve error 500 al generar una factura."*
3. **Esperado**: el sistema confirma que la descripción fue recibida y no formula preguntas
   de aclaración (FR-009), porque los 3 campos (sistema, síntoma, momento) están presentes.

### 2. Persistencia del contexto (US2 / FR-004, FR-005)

1. Continuando la conversación anterior, hacer 3-4 intercambios adicionales sin repetir la
   descripción original (p. ej. preguntar "¿qué información necesitas de mí ahora?").
2. En cualquier punto, pedir al sistema que resuma el problema investigado.
3. **Esperado**: el resumen coincide con la descripción original (módulo de facturación,
   error 500, desde ayer) sin que el usuario la haya repetido.

### 3. Aclaración ante ambigüedad (US3 / FR-006, FR-007, FR-008)

1. Iniciar un caso nuevo (ver escenario 4) y escribir una descripción vaga: *"no funciona"*.
2. **Esperado**: el sistema no acepta la descripción sin más; formula preguntas puntuales
   sobre los campos faltantes (sistema/aplicación afectada, síntoma, momento).
3. Responder las preguntas.
4. **Esperado**: el sistema incorpora las respuestas al contexto del caso y dejar de pedir
   más aclaraciones si ya hay suficiente información.

### 3b. Usuario no puede aportar más información (FR-010)

1. Repetir el escenario 3, pero al ser preguntado, responder indicando explícitamente que no
   se puede aportar más detalle (p. ej. "no tengo más información por ahora").
2. **Esperado**: el sistema deja de insistir y continúa con la información disponible,
   dejando constancia de qué dato quedó sin confirmar.

### 4. Casos secuenciales en una misma conversación (FR-013, FR-014)

1. Con un caso activo y completo (por ejemplo, tras el escenario 1), indicar que se quiere
   reportar un problema nuevo mientras el caso anterior sigue activo.
2. **Esperado**: el sistema informa que hay un caso en curso y solicita confirmación antes de
   finalizarlo y abrir uno nuevo (no procesa dos casos en paralelo).
3. Confirmar el cierre e iniciar el caso nuevo con una descripción distinta.
4. **Esperado**: el sistema vuelve a solicitar la descripción del problema para el caso
   nuevo, y su contexto no se mezcla con el del caso anterior.

### 5. Descripción vacía (Edge case, FR-011)

1. Al ser solicitada la descripción, enviar un mensaje vacío o solo espacios.
2. **Esperado**: el sistema rechaza el contenido y vuelve a solicitar la descripción,
   indicando que no pudo interpretar la anterior.

## Notas

- Todos los escenarios anteriores corresponden 1:1 a los criterios de aceptación en
  `spec.md`. Un escenario que no se comporte como se describe indica una regresión respecto
  a la especificación, no solo un defecto de esta guía.
