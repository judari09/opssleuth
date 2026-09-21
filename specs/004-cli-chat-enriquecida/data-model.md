# Data Model: CLI Chat Enriquecida

Esta spec **no introduce ni modifica entidades de dominio** (ver `spec.md`, "Key Entities"). `Caso`
y sus entidades asociadas (`DescripcionProblema`, `CampoExtraido`, `Aclaracion`, `FuenteDeLogs`,
`EntradaLogRelevante`, `ApreciacionInicialLogs`) se usan exactamente con la forma ya documentada en
`specs/001-recepcion-incidencia/data-model.md` y `specs/002-busqueda-logs/data-model.md` — es un
cambio exclusivamente de presentación sobre la conversación ya modelada.

## Superficie nueva (sin entidades de dominio)

El único "dato" nuevo introducido por esta spec no es una entidad de dominio, sino un parámetro de
control de presentación en una función ya existente:

| Dato | Tipo | Vive en | Se usa en |
|---|---|---|---|
| `es_error` | `bool` (por defecto `False`) | Parámetro de `_imprimir` (`cli.py`) / `mostrar_mensaje_sistema` (`presentation/console.py`) | Cableado explícitamente a `True` en los 2 mensajes de fallo de comunicación con el proveedor (`_procesar_intake`, `_buscar_y_presentar_apreciacion_logs`) — ver `research.md`, Decisión 6 |

No hay una entidad "Mensaje de chat" o similar persistida en `Caso` — el historial de la
conversación sigue viviendo exclusivamente en `Caso.mensajes` (lista de `dict` `role`/`content`,
ya establecida desde la spec 001), sin cambios de forma. La presentación (etiqueta de rol, color,
renderizado Markdown) se calcula en el momento de imprimir/leer, no se almacena.

## Por qué no hay entidades nuevas

- La diferenciación visual (Historia 1) y el renderizado legible (Historia 2) son puramente
  transformaciones de presentación sobre texto que `Caso` ya modela — no requieren un nuevo tipo de
  dato para existir.
- El indicador de actividad (Historia 3) es un efecto visual transitorio durante una llamada
  síncrona (`evaluar_descripcion`/`buscar_evidencia`) — no sobrevive más allá de esa llamada, no
  hay estado que persistir.
