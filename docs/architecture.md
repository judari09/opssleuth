# Arquitectura

## Vista de módulos

```text
src/opssleuth/
├── domain/            entidades puras (Caso, DescripcionProblema, FuenteDeLogs,
│                       FuenteDeBaseDeDatos, ApreciacionInicial*...) — sin SDKs
├── clarification/      motor de aclaración: evaluar_descripcion / generar_preguntas
├── evidence/           búsqueda de evidencia en logs
│   ├── tools.py         buscar_texto, leer_contexto, contar_lineas, preguntar_al_usuario
│   ├── agent.py          construye el agente LangGraph (create_agent) sobre esas tools
│   └── engine.py         orquesta: 1 agente por fuente, consolida en 1 apreciación
├── database/           consulta a bases de datos
│   ├── factory.py        crear_motor_bd(): Engine de SQLAlchemy + alcance de tablas
│   ├── validacion.py      validar_consulta(): barandilla de seguridad (sqlglot)
│   ├── tools.py           listar_tablas_disponibles, describir_tabla, ejecutar_consulta_sql
│   ├── agent.py           construye el agente LangGraph sobre esas tools
│   └── engine.py          orquesta la consulta y consolida la apreciación
├── llm/
│   └── factory.py        crear_modelo_chat(): único punto que importa SDKs de proveedor
├── presentation/
│   └── console.py        único módulo que importa `rich` (etiquetas de rol, Markdown,
│                          indicador de actividad, banner)
└── cli.py               bucle conversacional: orquesta las fases anteriores
```

Cada flecha de dependencia apunta hacia abajo o hacia `domain/`: `cli.py`
depende de `clarification`, `evidence`, `database`, `llm` y `presentation`,
nunca al revés; y ninguno de esos paquetes importa `rich` (solo
`presentation/console.py` lo hace) ni un SDK de proveedor de modelo (solo
`llm/factory.py` los importa). Esta separación es la aplicación concreta del
Principio II de la constitución (ver más abajo).

## Los cuatro principios no negociables

El proyecto se rige por `.specify/memory/constitution.md` (v1.1.0). Toda
revisión de código los verifica explícitamente:

### I. Cumplimiento SOLID

Cada módulo tiene una única razón para cambiar: `domain/` solo cambia si
cambian las reglas de negocio sobre un `Caso`; `evidence/tools.py` solo si
cambia cómo se busca en un archivo de logs; `llm/factory.py` solo si cambia
cómo se selecciona/construye un proveedor. Las implementaciones concretas
(`ChatAnthropic`, `ChatOllama`, `ChatGoogleGenerativeAI`) son intercambiables
detrás de `BaseChatModel` sin que ningún consumidor lo note (Sustitución de
Liskov).

### II. Arquitectura modular y reemplazable

Todo módulo expone sus dependencias externas detrás de una capa de
abstracción — con una excepción documentada explícitamente en la
constitución: **un estándar de terceros maduro y ampliamente adoptado puede
asumir el rol de esa capa**, en vez de una interfaz propia redundante. Este
proyecto invoca esa excepción dos veces:

- `langchain_core.language_models.BaseChatModel` como abstracción de
  proveedor de modelo de chat (en vez de un `Protocol` propio — así empezó
  este proyecto en la spec 001, y se migró deliberadamente en la 002; ver
  `specs/002-busqueda-logs/contracts/chat_model_provider.md` en el
  repositorio).
- El propio grafo de `langchain.agents.create_agent` (LangGraph) como
  mecanismo de bucle agéntico — ver [Flujo del agente](agent-workflow.md).

El acoplamiento a esos paquetes queda confinado a puntos de integración
explícitos: **una única función de fábrica** por cada uno
(`crear_modelo_chat()`, `construir_agente()` en `evidence/agent.py` y
`database/agent.py`). El resto del código de negocio solo ve el tipo
abstracto (`BaseChatModel`, el grafo compilado), nunca la implementación
concreta.

`sqlalchemy`/`sqlglot` (spec 005) y `rich` (spec 004) siguen en cambio el
camino **por defecto** del principio (sin invocar la excepción): quedan
confinados a un paquete/módulo propio (`database/`, `presentation/console.py`)
sin pretender ser el mecanismo de intercambiabilidad general del proyecto.

### III. Docstrings obligatorios

Todo el código de `src/opssleuth/` sigue el formato **numpydoc** (secciones
`Parameters`, `Returns`, `Raises`) en cada clase, método y función pública.
Esta misma página de documentación — y toda la sección
[Referencia de código](reference/index.md) — se genera automáticamente a
partir de esos docstrings vía `mkdocstrings`, nunca escrita a mano por
separado: si el código cambia, la documentación se regenera y queda
sincronizada.

### IV. Simplicidad ante todo

Ejemplos concretos de esta disciplina en el código actual:

- **Cómputo determinista sobre auto-enumeración del LLM**: cuando hay que
  acotar o deduplicar una lista de resultados (entradas de log, filas de
  BD), se hace en código de aplicación a partir de los `ToolMessage` reales
  que las herramientas devolvieron — nunca pidiendo al modelo que enumere
  libremente en su respuesta (ver `_extraer_entradas_de_mensajes` en
  `evidence/engine.py` y `database/engine.py`).
- **Sin persistencia todavía**: un `Caso` vive en memoria de proceso durante
  la conversación — decisión explícita por simplicidad, no una limitación
  técnica, hasta que una spec futura la necesite de verdad.
- **Sin capa de configuración paralela**: cada proveedor nuevo (Gemini, un
  cuarto futuro) se añade dentro de `crear_modelo_chat()`, reutilizando las
  mismas variables de entorno (`OPSSLEUTH_LLM_PROVIDER`) en vez de introducir
  un mecanismo de selección alternativo.

## Entidades de dominio

```text
Caso
├── descripcion_inicial: DescripcionProblema | None
│     ├── sistema_afectado / sintoma / momento : CampoExtraido
├── aclaraciones: list[Aclaracion]
├── mensajes: list[dict]                # contexto multi-turno
├── fuentes_logs: list[FuenteDeLogs]
├── apreciacion_logs: ApreciacionInicialLogs | None
│     └── entradas_destacadas: list[EntradaLogRelevante]
├── fuentes_bd: list[FuenteDeBaseDeDatos]
└── apreciacion_bd: ApreciacionInicialBD | None
      └── entradas_destacadas: list[EntradaBDRelevante]
```

`FuenteDeBaseDeDatos` nunca contiene la cadena de conexión ni credenciales —
esas viven únicamente en el `Engine` de SQLAlchemy que construye
`database.factory.crear_motor_bd()`, envuelto en
`FuenteDeBaseDeDatosConfigurada` (uso interno del paquete `database/`, nunca
expuesto a `domain/`). Ver la referencia completa en
[reference/domain.md](reference/domain.md).

## Por qué un solo `Caso` a la vez

Una conversación puede contener varios casos secuenciales, pero solo uno
activo a la vez — sin colaboración multiusuario sobre un mismo caso. Esa
restricción la aplica quien gestiona el ciclo de vida de los casos
(`opssleuth.cli.ejecutar_conversacion`), no la clase `Caso` en sí, que no
tiene visibilidad de otras instancias.
