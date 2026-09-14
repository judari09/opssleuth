# Data Model: Búsqueda en Archivos de Logs

Entidades nuevas del dominio (`src/opssleuth/domain/log_evidence.py`), más una extensión de la
entidad `Caso` existente (`src/opssleuth/domain/case.py`, de 001). Todas son `dataclass` puras, sin
dependencia de ningún SDK de proveedor de modelo ni de LangChain — mismo principio ya aplicado a
`domain/case.py`. La adopción de LangChain/LangGraph como mecanismo de modularidad (ver
`research.md`, Decisión 1) afecta únicamente a cómo se invoca al modelo (`llm/factory.py`,
`evaluar_descripcion`, `buscar_evidencia`), nunca a la forma de estas entidades de dominio.

## Extensión de `Caso`

| Campo | Tipo | Descripción |
|---|---|---|
| `creado_en` | `datetime` | Marca de tiempo de creación del caso, poblada automáticamente en `Caso.__post_init__` (o al construir). Sirve de anclaje temporal absoluto para interpretar expresiones relativas del campo `momento` (ver `research.md`, Decisión 5). |
| `fuentes_logs` | `list[FuenteDeLogs]` | Fuentes de logs aportadas para el caso (US1, FR-013). Lista vacía por defecto. |
| `apreciacion_logs` | `ApreciacionInicialLogs \| None` | Apreciación inicial consolidada, una vez producida (FR-010). `None` mientras no se haya buscado evidencia. |

**Nota de compatibilidad**: estos campos son aditivos — no modifican el comportamiento ni la forma
de los campos existentes de `Caso` documentados en `specs/001-recepcion-incidencia/data-model.md`.

## `FuenteDeLogs`

Representa el origen de los logs a analizar (Key Entity "Fuente de Logs" del spec).

| Campo | Tipo | Descripción |
|---|---|---|
| `ruta` | `str` | Ruta absoluta al archivo de logs (indicada por el usuario, o generada a partir de contenido pegado — ver `origen`). |
| `origen` | `Literal["ruta_usuario", "contenido_pegado"]` | Distingue si la ruta fue indicada directamente por el usuario o generada por el sistema a partir de contenido pegado en el chat (FR-003/FR-015). |
| `aportada_en` | `datetime` | Momento en que se registró esta fuente para el caso. |

**Reglas**:
- Una `FuenteDeLogs` con `origen="contenido_pegado"` siempre corresponde a un archivo real en
  disco (ver `research.md`, Decisión 8) — no existe una variante "solo en memoria"; simplifica las
  herramientas de búsqueda, que siempre operan por ruta de archivo.
- `Caso.fuentes_logs` puede contener más de una entrada (FR-013); el orden de la lista es el orden
  de aportación.

## `EntradaLogRelevante`

Una línea o fragmento de log identificado como relacionado con el incidente (Key Entity "Entrada de
Log Relevante").

| Campo | Tipo | Descripción |
|---|---|---|
| `fuente` | `FuenteDeLogs` | Fuente de la que proviene esta entrada. |
| `numero_linea` | `int` | Número de línea (1-indexado) dentro de la fuente. |
| `contenido` | `str` | Texto de la línea (o fragmento de contexto) tal como se leyó del archivo — nunca reescrito ni resumido por el modelo, para evitar alucinación (ver `research.md`, Decisión 6). |
| `marca_de_tiempo` | `str \| None` | Marca de tiempo tal como aparece en el log, si es identificable en el texto; `None` si no se pudo identificar una. Se mantiene como texto libre (sin parseo estructurado — ver `research.md`, Decisión 4). |

**Reglas**:
- Toda instancia de `EntradaLogRelevante` DEBE originarse en el resultado real de una llamada a la
  herramienta `buscar_texto` o `leer_contexto` (Regla determinista, `research.md` Decisión 6) — no
  se construye a partir de texto libre generado por el modelo.

## `ApreciacionInicialLogs`

Resumen único por caso, consolidado entre todas las fuentes de logs aportadas (Key Entity
"Apreciación Inicial de Logs").

| Campo | Tipo | Descripción |
|---|---|---|
| `resumen` | `str` | Texto de la apreciación inicial elaborada por el modelo a partir de las entradas encontradas, relacionándolas con el incidente descrito (FR-009). Si no se encontró ninguna entrada relevante, el resumen lo refleja explícitamente (FR-008, SC-003) — nunca una conclusión fabricada. |
| `entradas_destacadas` | `list[EntradaLogRelevante]` | Conjunto acotado de entradas representativas (FR-009a), consolidado entre todas las fuentes (FR-010a), calculado de forma determinista (ver `research.md`, Decisión 6). |
| `hay_mas_coincidencias` | `bool` | `True` cuando el volumen real de coincidencias encontradas supera el límite aplicado a `entradas_destacadas` (FR-009a) — le indica al usuario que existen más resultados disponibles aunque no se listen todos. |
| `generada_en` | `datetime` | Momento en que se produjo la apreciación. |

**Reglas**:
- Existe como máximo una `ApreciacionInicialLogs` por caso a la vez (`Caso.apreciacion_logs`); no
  hay una apreciación independiente por fuente (FR-010a).
- `resumen` es producido por el motor de búsqueda (`LogSearchEngine`) al final del bucle agéntico,
  una vez que `entradas_destacadas` ya fue calculada de forma determinista — el modelo redacta el
  texto de síntesis a partir de esa lista ya acotada, no al revés.

## Diagrama de relaciones

```text
Caso (extendido)
├── creado_en: datetime
├── fuentes_logs: list[FuenteDeLogs]
│                          └── (0..N por caso, FR-013)
└── apreciacion_logs: ApreciacionInicialLogs | None
                              └── entradas_destacadas: list[EntradaLogRelevante]
                                                              └── fuente: FuenteDeLogs (referencia)
```

## Validaciones de dominio

Siguiendo el mismo estilo que `domain/case.py` (validación en el constructor/métodos de dominio,
sin dependencia de ningún SDK):

- `FuenteDeLogs.ruta` no puede ser una cadena vacía o solo espacios en blanco.
- `EntradaLogRelevante.numero_linea` debe ser >= 1.
- `ApreciacionInicialLogs.entradas_destacadas` vacía es válida y es precisamente la representación
  de "no se encontraron coincidencias" (FR-008) — el campo `resumen` es el que debe reflejarlo en
  texto, no una excepción ni un valor centinela separado.
