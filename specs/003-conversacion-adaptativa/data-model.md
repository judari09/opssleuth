# Data Model: Conversación Adaptativa

Esta spec **no introduce ni modifica entidades de dominio**. `Caso`, `DescripcionProblema`,
`CampoExtraido`, `Aclaracion` (`src/opssleuth/domain/case.py`) y `FuenteDeLogs`
(`src/opssleuth/domain/log_evidence.py`) se usan exactamente con la forma ya documentada en
`specs/001-recepcion-incidencia/data-model.md` y `specs/002-busqueda-logs/data-model.md` — ver
`research.md`, Decisión 2, para la justificación explícita de por qué no se añade un campo nuevo
a `Caso` para la ruta de logs candidata del mensaje inicial.

## Flujo de datos nuevo (sin nuevas entidades)

Los dos comportamientos de esta spec se implementan como **datos que fluyen entre funciones ya
existentes de `src/opssleuth/cli.py`**, no como estado nuevo del dominio:

| Dato | Tipo | Vive en | Se resuelve en |
|---|---|---|---|
| Ruta de logs candidata del mensaje inicial | `str \| None` | Valor de retorno de `_procesar_intake` → parámetro de `_solicitar_evidencia_logs` | `_solicitar_evidencia_logs`: si no es `None`, se valida (mismo `os.path.isfile` ya usado hoy) antes de decidir si formular la invitación interactiva o registrar directamente una `FuenteDeLogs(origen="ruta_usuario")` |
| Lote de aclaraciones pendientes combinables | `list[Aclaracion]` (subconjunto de `preguntas_de_campos` con `campo_objetivo` en `CAMPOS_DE_DESCRIPCION`) | Variable local en `_procesar_intake` | `_formular_y_registrar_aclaraciones_combinadas`: produce cero o más `Aclaracion` ya registradas en `caso.aclaraciones` (mismo tipo y reglas que las que produce hoy `_formular_y_registrar_aclaracion`, uno por campo) más la lista de las que sigan pendientes, que continúan por el bucle uno-por-uno ya existente |

Ninguna `Aclaracion` producida por el camino combinado difiere en forma de una producida por el
camino uno-por-uno existente — mismos campos (`pregunta`, `campo_objetivo`, `respuesta`,
`sin_confirmar`, `contradice_descripcion_original`), mismas reglas de negocio (detección de
contradicción, "no puedo aportar más información"). Lo único que cambia es *cuántas* preguntas
se agrupan en un mismo turno de pregunta/respuesta antes de invocar la lógica de registro ya
existente.

## Por qué no hay entidades nuevas

- La "ruta candidata" no es un concepto de dominio persistente: solo tiene sentido durante la
  única llamada síncrona `_procesar_intake` → `_solicitar_evidencia_logs` dentro de
  `ejecutar_conversacion`. Modelarla como campo de `Caso` la haría sobrevivir más allá de esa
  ventana sin necesidad real (violaría el Principio IV).
- El "lote combinado" de aclaraciones no es una entidad — es una forma distinta de *generar* las
  mismas `Aclaracion` que ya existen como entidad desde la spec 001; no se necesita una entidad
  "RespuestaCombinada" o similar para representarlo.
