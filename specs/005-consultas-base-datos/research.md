# Research: Consultas a Bases de Datos

## Decisión 1: SQLAlchemy Core (no ORM) como capa de conexión, confinada a un paquete nuevo `database/`

**Decisión**: Se usa `sqlalchemy` (Core: `Engine`, `Connection`, `text()` — no el ORM) como
mecanismo de conexión agnóstico de motor. El import queda confinado exclusivamente a
`src/opssleuth/database/factory.py` (construcción del `Engine`) y `src/opssleuth/database/tools.py`
(ejecución de consultas) — ningún otro módulo del proyecto importa `sqlalchemy` directamente.

**Rationale**: A diferencia de `BaseChatModel` (spec 002), aquí no hay varios módulos de negocio
independientes que necesiten depender de un tipo abstracto compartido de terceros — solo el
paquete `database/` nuevo consume la conexión. Se sigue por tanto el camino **por defecto** del
Principio II (confinar la dependencia de terceros detrás de una capa propia del proyecto), el
mismo ya aplicado a `rich` en `presentation/console.py` (spec 004) y a los SDKs de proveedor en
`llm/factory.py` — no se invoca la excepción de "estándar de abstracción de terceros maduro"
porque su condición (el tipo de terceros como mecanismo de intercambiabilidad consumido por
varios módulos) no aplica aquí.

**Alternatives considered**:
- Un driver específico de un solo motor (p. ej. `psycopg` directo para PostgreSQL): rechazado — la
  spec (Assumptions) no asume un motor específico; SQLAlchemy permite que quien opera la
  herramienta elija el motor vía la URL de conexión (`OPSSLEUTH_DB_URL`) sin cambiar código.
- El ORM de SQLAlchemy (mapeo de modelos): rechazado — no hay entidades de dominio que mapear a
  tablas; Core (ejecución de SQL parametrizado/validado sobre un `Engine`) es exactamente lo que
  se necesita, sin la complejidad adicional de definir modelos ORM para tablas que ni siquiera se
  conocen de antemano (Principio IV).

## Decisión 2: `sqlglot` para validar y parsear las consultas — no una heurística por regex

**Decisión**: Toda consulta que el agente proponga se valida con `sqlglot` antes de ejecutarse:
(a) debe parsear como una única sentencia `SELECT` (se rechaza cualquier texto con más de una
sentencia, o cuya raíz no sea `SELECT`); (b) se extraen las tablas referenciadas
(`sqlglot.exp.Table`) y se comparan contra el conjunto permitido (`OPSSLEUTH_DB_TABLAS_PERMITIDAS`)
— si alguna tabla referenciada no está en ese conjunto, la consulta se rechaza sin ejecutarse.

**Rationale**: Reconocer correctamente qué tablas referencia una consulta arbitraria (incluidas
subconsultas, CTEs, alias, nombres calificados por esquema) es precisamente el tipo de problema
donde una heurística por expresiones regulares es a la vez más código y menos segura que usar un
parser SQL real — aquí la simplicidad real (Principio IV) está en apoyarse en una librería madura
y auditada para la pieza más crítica de seguridad del diseño, no en reinventarla. `sqlglot` es
pura Python, sin dependencias de un motor de base de datos concreto, y expone exactamente la
API necesaria (`parse`, `exp.Table`) para esta validación.

**Alternatives considered**:
- Regex sobre el texto de la consulta para detectar palabras clave prohibidas
  (`INSERT`/`UPDATE`/`DELETE`/etc.) y nombres de tabla: rechazado — trivialmente evadible
  (comentarios, mayúsculas/minúsculas mezcladas, nombres calificados, subconsultas) y no ofrece
  garantías reales pese a aparentar simplicidad.
- El kit de herramientas SQL ya incluido en el ecosistema LangChain
  (`langchain_community.agent_toolkits.sql`): rechazado — sus garantías de solo-lectura y de
  alcance de tablas no están bajo control directo de este proyecto y requerirían auditarse de
  todos modos; dado que esta es "una barandilla de seguridad central, no un detalle menor"
  (encuadre explícito del usuario), se prefiere una validación propia, simple y verificable
  directamente en el código de este proyecto.

## Decisión 3: Defensa en profundidad — validación de la sentencia + transacción de solo lectura

**Decisión**: Además de la validación de Decisión 2 (rechazar antes de ejecutar), toda consulta
se ejecuta dentro de una transacción/conexión abierta en modo de solo lectura cuando el motor
subyacente lo soporta (p. ej. `SET TRANSACTION READ ONLY` en PostgreSQL vía
`connection.execution_options(...)`, o el mecanismo equivalente del dialecto configurado) — nunca
se hace `commit()`; toda conexión se descarta (rollback implícito) al finalizar la consulta.

**Rationale**: La validación de texto (Decisión 2) es la primera barrera, pero no cubre
exhaustivamente cada función o procedimiento con efectos secundarios que un motor concreto pueda
exponer dentro de una sentencia técnicamente `SELECT`. Abrir la conexión en modo de solo lectura
es una segunda capa independiente, a nivel de motor, que no depende de haber anticipado
correctamente cada caso en el parser. Documentado explícitamente porque, tal como señaló quien
pidió esta spec, esta garantía es central y no un detalle — se prefiere ser transparente sobre sus
capas y sus límites conocidos en vez de presentarla como una garantía absoluta.

**Residual risk documentado (no oculto)**: ni la validación de texto ni el modo de solo lectura a
nivel de conexión sustituyen la buena práctica operativa de que las credenciales configuradas en
`OPSSLEUTH_DB_URL` correspondan, en la base de datos real, a un rol con permisos de solo lectura
a nivel del motor — se documenta como recomendación operativa en `quickstart.md`, como tercera capa
fuera del control del código de este proyecto.

## Decisión 4: Alcance de tablas obligatorio — sin valor por defecto "todas las tablas"

**Decisión**: `crear_motor_bd()` exige que `OPSSLEUTH_DB_TABLAS_PERMITIDAS` esté configurada
explícitamente (lista separada por comas) cuando `OPSSLEUTH_DB_URL` está presente — si falta,
lanza un error explícito (`TablasPermitidasNoConfiguradasError`) en vez de permitir todas las
tablas por defecto.

**Rationale**: Un valor por defecto "sin restricción" para el alcance de tablas contradiría
directamente FR-003 y el encuadre de esta spec como barandilla de seguridad central — el fallo
seguro (fail-safe) es no habilitar la funcionalidad en absoluto si el alcance no se declaró
explícitamente, no asumir acceso total. Mismo patrón ya establecido por
`ModeloOllamaNoConfiguradoError` (`llm/factory.py`): configuración incompleta de un proveedor
opcional se rechaza explícitamente, no se completa con un supuesto implícito.

## Decisión 5: Acotamiento de resultados — `fetchmany`, no traer todo y truncar después

**Decisión**: La herramienta `ejecutar_consulta_sql` nunca materializa el resultado completo de la
consulta en memoria. Añade (o reduce, si ya existe una mayor) una cláusula `LIMIT` a la consulta
parseada antes de ejecutarla, fijándola en `MAXIMO_FILAS_POR_DEFECTO + 1`, y además usa
`cursor.fetchmany(MAXIMO_FILAS_POR_DEFECTO + 1)` sobre el resultado — si se obtiene la fila extra,
se descarta y se marca `hay_mas=True` en la respuesta (mismo patrón `hay_mas` ya usado por
`buscar_texto`, spec 002).

**Rationale**: Un cruce entre varias tablas (Historia 3) puede producir, por error o por diseño,
un volumen de filas desproporcionado (p. ej. un producto cartesiano accidental). Traer el
resultado completo a memoria antes de acotarlo —como sí es aceptable para un archivo de logs
local (`research.md` de spec 002, Decisión de releer el archivo en cada llamada)— no es aceptable
aquí: un cruce mal formado contra una base de datos real podría intentar devolver millones de
filas antes de llegar al punto de truncar. Acotar en el propio SQL y al leer el cursor evita ese
escenario en el origen.

## Decisión 6: Tres herramientas nuevas, análogas a las de búsqueda de logs

**Decisión**: Se exponen tres herramientas `@tool` en `database/tools.py`, ligadas por cierre al
`Engine`/alcance de tablas activos (mismo patrón de `crear_herramientas_busqueda`, spec 002):

- `listar_tablas_disponibles()`: devuelve los nombres de las tablas permitidas (el subconjunto de
  `OPSSLEUTH_DB_TABLAS_PERMITIDAS` que existe realmente en la base de datos).
- `describir_tabla(tabla: str)`: devuelve columnas y tipos de una tabla permitida (rechaza si
  `tabla` no está en el conjunto permitido, mismo criterio que Decisión 2).
- `ejecutar_consulta_sql(consulta: str)`: valida (Decisiones 2-3) y ejecuta una consulta de solo
  lectura, acotada (Decisión 5), devolviendo las filas como resultado.

**Rationale**: Mismo rol que `contar_lineas`/`buscar_texto`/`leer_contexto` cumplen para logs: una
herramienta de calibración inicial (aquí, descubrir qué tablas/columnas existen, en vez de asumir
que el modelo "adivina" nombres de columnas), y una herramienta de ejecución acotada. Sin esta
calibración, construir cruces correctos entre "más de dos tablas" (Historia 3) sería mucho más
propenso a error — el modelo necesita conocer las columnas reales antes de poder unirlas
correctamente.

**Alternatives considered**:
- Una única herramienta que solo ejecuta SQL, sin `listar_tablas_disponibles`/`describir_tabla`:
  rechazado — obligaría al modelo a adivinar el esquema o a usar `ejecutar_consulta_sql` con
  `SELECT * FROM information_schema...` como sustituto improvisado, lo cual sería más difícil de
  validar de forma consistente que exponer una herramienta de introspección dedicada y ya acotada
  al alcance permitido.
- Una herramienta estructurada (tabla + columnas + filtros + joins como argumentos tipados, sin
  SQL libre): rechazada — no puede expresar con naturalidad cruces arbitrarios entre más de dos
  tablas con condiciones variadas (Historia 3, pedido explícito del usuario) sin terminar
  reinventando, en los argumentos de la herramienta, un lenguaje de consultas equivalente a SQL
  pero con más código propio y peor cubierto por herramientas de validación maduras (Principio
  IV).

## Decisión 7: Fuente única de base de datos en esta implementación (la spec permite más de una)

**Decisión**: `Caso.fuentes_bd: list[FuenteDeBaseDeDatos]` se modela como lista (igual que
`fuentes_logs`), pero `crear_motor_bd()` construye como máximo **una** fuente a partir de
`OPSSLEUTH_DB_URL`/`OPSSLEUTH_DB_TABLAS_PERMITIDAS` en esta implementación — no se parsean
múltiples conexiones nombradas.

**Rationale**: La spec (Assumptions) permite que en el futuro un caso tenga más de una fuente de
base de datos sin que el comportamiento descrito cambie, pero no lo exige para esta primera
implementación, y el pedido original del usuario no menciona varias bases de datos. Construir
ahora un esquema de configuración para N conexiones nombradas sería complejidad no solicitada
(Principio IV). Modelar el campo como lista (en vez de un único opcional) deja la extensión futura
abierta sin necesitar rediseñar `Caso` si una spec futura la pide.

## Decisión 8: Sin límite de tiempo de ejecución garantizado a nivel universal — mejor esfuerzo

**Decisión**: Se aplica `Connection.execution_options(timeout=OPSSLEUTH_DB_TIMEOUT_SEGUNDOS)`
(por defecto 10s) al ejecutar cada consulta, cuando el DBAPI/dialecto configurado lo soporta. El
límite de iteraciones del bucle agéntico (`MAXIMO_ITERACIONES_AGENTE_BD`, mismo valor que spec 002:
15) sigue siendo la garantía principal de que la conversación no queda bloqueada indefinidamente.

**Rationale**: El soporte de tiempo de espera por consulta varía según el DBAPI subyacente (no es
una garantía uniforme de SQLAlchemy Core en todos los dialectos) — se documenta como mejor
esfuerzo, no como garantía absoluta, en vez de afirmar una garantía que el código no puede cumplir
de forma consistente entre motores.

## Nuevas dependencias

- `sqlalchemy` (Core) — conexión agnóstica de motor, confinada a `database/factory.py` y
  `database/tools.py` (Decisión 1).
- `sqlglot` — parseo y validación de las consultas propuestas por el agente (Decisión 2).
- Ningún driver de motor específico (`psycopg`/`pymysql`/etc.) se añade como dependencia del
  proyecto — se asume que quien opera la herramienta instala el driver correspondiente al motor
  que configure en `OPSSLEUTH_DB_URL`, salvo SQLite, cuyo soporte ya viene incluido en la
  biblioteca estándar de Python y es el motor de referencia usado en `quickstart.md`/pruebas.
