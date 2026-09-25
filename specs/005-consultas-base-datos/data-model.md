# Data Model: Consultas a Bases de Datos

Entidades nuevas del dominio (`src/opssleuth/domain/database_evidence.py`), más una extensión de
la entidad `Caso` existente (`src/opssleuth/domain/case.py`). Todas son `dataclass` puras, sin
dependencia de `sqlalchemy`/`sqlglot` ni de ningún SDK de proveedor de modelo — mismo principio ya
aplicado a `domain/case.py` y `domain/log_evidence.py`. La adopción de SQLAlchemy/`sqlglot` (ver
`research.md`, Decisiones 1-2) afecta únicamente a cómo se construye la conexión y se valida/
ejecuta una consulta (`database/factory.py`, `database/tools.py`), nunca a la forma de estas
entidades de dominio.

## Extensión de `Caso`

| Campo | Tipo | Descripción |
|---|---|---|
| `fuentes_bd` | `list[FuenteDeBaseDeDatos]` | Fuentes de base de datos configuradas y disponibles para el caso (Historia 1). Lista vacía por defecto — y, en esta implementación, con como máximo un elemento (ver `research.md`, Decisión 7). |
| `apreciacion_bd` | `ApreciacionInicialBD \| None` | Apreciación inicial consolidada de evidencia de base de datos, una vez producida (FR-009). `None` mientras no se haya consultado. |

**Nota de compatibilidad**: estos campos son aditivos — no modifican el comportamiento ni la forma
de los campos existentes de `Caso` (incluidos `fuentes_logs`/`apreciacion_logs` de spec 002).

## `FuenteDeBaseDeDatos`

Representa la disponibilidad de una base de datos configurada como fuente de evidencia (Key
Entity "Fuente de Base de Datos" del spec). **Nunca contiene la cadena de conexión ni credenciales**
— esas viven únicamente dentro del `Engine` de SQLAlchemy construido por `database/factory.py` e
inyectado como parámetro a `consultar_evidencia_bd`, nunca serializadas en un objeto de dominio
visible desde `Caso` (evita que una credencial termine, por accidente, en un log o en un mensaje
mostrado al usuario).

| Campo | Tipo | Descripción |
|---|---|---|
| `motor` | `str` | Nombre del motor de base de datos configurado (p. ej. `"postgresql"`, `"sqlite"`), derivado del esquema de `OPSSLEUTH_DB_URL` — solo para mostrar al usuario de forma segura, nunca la URL completa. |
| `tablas_permitidas` | `list[str]` | Conjunto de tablas a las que esta fuente puede acceder (FR-003) — subconjunto de `OPSSLEUTH_DB_TABLAS_PERMITIDAS` que además existe realmente en la base de datos. |
| `aportada_en` | `datetime` | Momento en que se registró esta fuente como disponible para el caso. |

**Reglas**:
- `tablas_permitidas` nunca puede estar vacía — `crear_motor_bd()` rechaza la configuración antes
  de llegar a construir una `FuenteDeBaseDeDatos` si no hay ninguna tabla permitida configurada
  (ver `research.md`, Decisión 4).
- Esta fuente se registra automáticamente al completarse la recepción de la incidencia si
  `OPSSLEUTH_DB_URL` está configurada — nunca la aporta ni la selecciona el usuario
  conversacionalmente (ver Clarifications de `spec.md`, Sesión 2026-09-21).

## `EntradaBDRelevante`

Una fila de resultado identificada como relacionada con el incidente (Key Entity "Consulta
Ejecutada" del spec, a nivel de cada fila individual).

| Campo | Tipo | Descripción |
|---|---|---|
| `fuente` | `FuenteDeBaseDeDatos` | Fuente de la que proviene esta entrada. |
| `consulta` | `str` | Texto de la consulta SQL realmente ejecutada que produjo esta fila — conservado para trazabilidad/auditoría (relevante dado que esta spec toca datos reales). |
| `fila` | `dict[str, object]` | Los valores de la fila, como mapa columna → valor, tal como los devolvió la base de datos — nunca reescritos ni resumidos por el modelo. |

**Reglas**:
- Toda instancia de `EntradaBDRelevante` DEBE originarse en el resultado real de una llamada a la
  herramienta `ejecutar_consulta_sql` (FR-010, mismo principio que `EntradaLogRelevante` de spec
  002) — nunca se construye a partir de texto libre generado por el modelo.

## `ApreciacionInicialBD`

Resumen único por caso, consolidado entre todas las fuentes de base de datos consultadas (Key
Entity "Evidencia de Base de Datos" del spec) — misma forma que `ApreciacionInicialLogs` (spec
002), para que ambas apreciaciones se presenten de manera consistente al usuario.

| Campo | Tipo | Descripción |
|---|---|---|
| `resumen` | `str` | Texto de la apreciación elaborada a partir de las filas encontradas, relacionándolas con el incidente descrito. Si no se encontró ninguna fila relevante, o no había ninguna fuente configurada, lo refleja explícitamente (FR-008/FR-009a del spec, equivalentes a FR-008/SC-003 de spec 002 para logs) — nunca una conclusión fabricada. |
| `entradas_destacadas` | `list[EntradaBDRelevante]` | Conjunto acotado de filas representativas (FR-006), consolidado entre todas las fuentes consultadas. |
| `hay_mas_resultados` | `bool` | `True` cuando el volumen real de resultados de alguna consulta superó el límite aplicado (FR-006) — informa al usuario que existen más resultados disponibles aunque no se listen todos. |
| `generada_en` | `datetime` | Momento en que se produjo la apreciación. |

**Reglas**:
- Existe como máximo una `ApreciacionInicialBD` por caso a la vez (`Caso.apreciacion_bd`) — mismo
  criterio de consolidación ya aplicado a `ApreciacionInicialLogs` (spec 002, FR-010a).
- Se presenta junto a `ApreciacionInicialLogs` (si existe) en el mismo punto de la conversación
  (p. ej. al pedir un resumen del caso) — nunca como un resultado aislado que el usuario deba ir a
  buscar por separado (FR-009).

## Diagrama de relaciones

```text
Caso (extendido, además de lo ya aportado por spec 002)
├── fuentes_bd: list[FuenteDeBaseDeDatos]
│                     └── (0..1 en esta implementación — research.md, Decisión 7)
└── apreciacion_bd: ApreciacionInicialBD | None
                          └── entradas_destacadas: list[EntradaBDRelevante]
                                                          └── fuente: FuenteDeBaseDeDatos (referencia)
```

## Validaciones de dominio

Siguiendo el mismo estilo que `domain/case.py`/`domain/log_evidence.py` (validación en el
constructor, sin dependencia de `sqlalchemy`/`sqlglot`):

- `FuenteDeBaseDeDatos.tablas_permitidas` no puede estar vacía.
- `FuenteDeBaseDeDatos.motor` no puede ser una cadena vacía o solo espacios en blanco.
- `EntradaBDRelevante.consulta` no puede ser una cadena vacía o solo espacios en blanco.
- `ApreciacionInicialBD.entradas_destacadas` vacía es válida y es precisamente la representación
  de "no se encontraron resultados relacionados" (Historia 1, Escenario 2) — el campo `resumen` es
  el que debe reflejarlo en texto, no una excepción ni un valor centinela separado.
