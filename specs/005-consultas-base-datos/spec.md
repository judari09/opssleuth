# Feature Specification: Consultas a Bases de Datos

**Feature Branch**: `005-consultas-base-datos`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "Añadir al agente OpsSleuth la capacidad de consultar bases de datos como una nueva fuente de evidencia para el diagnóstico, complementando la búsqueda en archivos de logs (spec 002). El agente debe poder ejecutar consultas tanto sencillas (una sola tabla) como complejas — incluyendo cruces (joins) entre más de dos tablas — para encontrar la información necesaria para un diagnóstico correcto, de forma análoga a como ya explora archivos de logs con un bucle de herramientas sin cargar todo el contenido de una vez. Dado que se trata de conectar un LLM a una base de datos real, el acceso debe quedar acotado estrictamente a operaciones de solo lectura (sin INSERT/UPDATE/DELETE ni DDL), y probablemente a un conjunto de tablas/esquema permitido — esto es una barandilla de seguridad central del diseño, no un detalle menor. Ver specs/ESTADO_SPECS.md para las decisiones y contratos ya establecidos (arquitectura LangChain/LangGraph, motor de modelo compartido, patrón de herramientas ya usado por la búsqueda de logs) que esta nueva spec debe respetar y reutilizar donde aplique."

## Clarifications

### Session 2026-09-21

- Q: ¿La conexión a la base de datos y el conjunto de tablas permitidas se configuran una sola
  vez por quien opera OpsSleuth (vía variables de entorno, análogo a `OPSSLEUTH_LLM_PROVIDER`), o
  el usuario puede aportarlas/seleccionarlas durante la conversación? → A: Configuradas una sola
  vez mediante variables de entorno en `.env` — mismo mecanismo ya establecido para el resto de
  configuración sensible del proyecto (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`); el usuario nunca
  las aporta ni las selecciona conversacionalmente.
- Q: Cuando el sistema decide consultar la base de datos, ¿debe anunciarlo de forma visible al
  usuario antes de ejecutar la consulta, o puede hacerlo de forma silenciosa y mostrar solo el
  resultado? → A: El sistema anuncia visiblemente cuándo va a consultar la base de datos
  (reutilizando el indicador de actividad ya implementado en spec 004) antes de presentar el
  resultado — coherente con tratar la base de datos como una fuente de datos real sobre la que el
  sistema actúa, no solo aportada pasivamente por el usuario.
- Q: ¿La consulta a base de datos requiere que la evidencia de logs ya se haya explorado primero
  (dependencia secuencial, como la Historia 2 depende de la Historia 1 en spec 002), o es una
  fuente de evidencia independiente que el sistema puede usar en cualquier momento del
  diagnóstico, con o sin evidencia de logs? → B: Es una fuente de evidencia independiente — el
  sistema puede consultar la base de datos configurada en cualquier momento del diagnóstico, tenga
  o no evidencia de logs disponible; un caso con base de datos configurada pero sin logs aportados
  igual puede beneficiarse de esta fuente.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar evidencia relevante en una tabla (Priority: P1) 🎯 MVP

Un integrante del equipo de soporte técnico está investigando un incidente ya descrito (y,
opcionalmente, con evidencia de logs ya aportada). El sistema, configurado con acceso a una base
de datos relevante para el sistema afectado, consulta esa base de datos para localizar registros
relacionados con el incidente (p. ej. el estado de una transacción, un pedido, una sesión) sin que
el usuario tenga que escribir la consulta él mismo.

**Why this priority**: Es la capacidad mínima que entrega valor por sí sola: correlacionar el
incidente con el estado real de los datos en la base de datos del sistema afectado, en vez de
depender únicamente de lo que aparece en los logs. Sin esta capacidad no existe la nueva fuente de
evidencia que pide esta spec.

**Independent Test**: Puede probarse con un caso cuya descripción/evidencia de logs apunte a un
registro identificable (p. ej. un ID de factura o de transacción), y verificando que el sistema
consulta la base de datos configurada y localiza el registro correspondiente, incorporándolo a la
evidencia del caso.

**Acceptance Scenarios**:

1. **Given** un caso con una base de datos configurada como fuente disponible, **When** el sistema
   identifica un dato del incidente que puede verificarse en esa base de datos (p. ej. un
   identificador mencionado en la descripción o en los logs), **Then** anuncia visiblemente que va
   a consultarla, consulta la tabla correspondiente, y localiza el registro relacionado, sin
   requerir que el usuario escriba la consulta.
2. **Given** una consulta que no encuentra ningún registro relacionado con el incidente, **When**
   el sistema termina de consultar, **Then** lo refleja explícitamente en la evidencia (nunca
   fabrica un resultado ni asume que el registro existe).
3. **Given** una base de datos configurada mediante credenciales inválidas o inaccesible en el
   momento de la consulta, **When** el sistema intenta consultarla, **Then** informa que no pudo
   completar la consulta y continúa el diagnóstico con la evidencia ya disponible por otras
   fuentes, sin interrumpir el resto de la conversación.

---

### User Story 2 - Acceso de solo lectura, acotado y a prueba de fallos (Priority: P1)

El sistema nunca ejecuta contra la base de datos configurada una operación que modifique datos o
esquema (inserción, actualización, borrado, creación/alteración de tablas), y nunca consulta tablas
fuera del conjunto explícitamente permitido para el diagnóstico — sin importar cómo esté redactada
la pregunta del usuario o cómo razone el modelo subyacente.

**Why this priority**: Es la condición no negociable de todo el esfuerzo, explícitamente señalada
como central por quien solicitó la spec: conectar un modelo de lenguaje a una base de datos real
sin esta garantía representa un riesgo directo de pérdida o corrupción de datos de producción. Sin
esta historia, ninguna de las demás es aceptable para desplegarse, independientemente de cuán útil
sea el diagnóstico resultante.

**Independent Test**: Puede probarse intentando forzar, mediante instrucciones directas al sistema
o descripciones de incidente diseñadas para inducirlo, una consulta de escritura o una consulta
sobre una tabla no permitida, y verificando que ninguna de las dos llega a ejecutarse contra la
base de datos real — el sistema la rechaza antes de intentarlo.

**Acceptance Scenarios**:

1. **Given** cualquier situación en la que el sistema decida consultar la base de datos, **When**
   formula la consulta, **Then** esa consulta es exclusivamente de lectura — nunca inserta,
   actualiza, borra datos, ni crea, modifica o elimina estructuras (tablas, columnas, índices,
   etc.).
2. **Given** una consulta que el sistema construye o que un usuario intenta inducir (directa o
   indirectamente) referenciando una tabla fuera del conjunto explícitamente permitido, **When**
   el sistema evalúa esa consulta, **Then** la rechaza sin ejecutarla contra la base de datos real,
   e informa que esa evidencia no está disponible dentro del alcance permitido.
3. **Given** un intento de consulta de escritura o fuera de alcance ya rechazado, **When** el
   sistema continúa la conversación, **Then** el rechazo no interrumpe ni degrada el resto del
   diagnóstico — sigue disponible la evidencia ya obtenida por otras vías.

---

### User Story 3 - Correlacionar información cruzando varias tablas (Priority: P2)

Cuando la evidencia relevante para el diagnóstico no vive en una sola tabla (p. ej. es necesario
relacionar una transacción con el usuario que la originó y con el estado de un servicio asociado),
el sistema construye y ejecuta consultas que cruzan información de más de dos tablas dentro del
alcance permitido, para llegar a una conclusión que ninguna consulta aislada a una sola tabla
podría entregar.

**Why this priority**: Amplía sustancialmente la calidad del diagnóstico en casos donde la causa
raíz solo es visible al correlacionar varias entidades relacionadas, pero depende de que ya exista
la capacidad básica de consulta (Historia 1) y las mismas garantías de seguridad (Historia 2) —
es una extensión de complejidad sobre la base ya establecida, no una capacidad independiente.

**Independent Test**: Puede probarse con un caso cuya causa raíz solo es identificable
relacionando registros de al menos tres tablas distintas dentro del alcance permitido (p. ej.
transacción + usuario + estado de un servicio dependiente), y verificando que el sistema construye
una consulta que cruza esas tablas y obtiene el resultado correlacionado, en vez de quedarse con
resultados parciales de consultas aisladas a una sola tabla.

**Acceptance Scenarios**:

1. **Given** un incidente cuya evidencia relevante está distribuida entre varias tablas
   relacionadas dentro del alcance permitido, **When** el sistema investiga, **Then** construye y
   ejecuta una consulta que cruza la información de esas tablas para obtener el dato correlacionado,
   en vez de limitarse a consultas de una sola tabla.
2. **Given** un cruce entre tablas que no produce ningún resultado relacionado con el incidente,
   **When** el sistema termina de consultar, **Then** lo refleja explícitamente en la evidencia,
   igual que en el caso de una consulta simple sin resultados (Historia 1, Escenario 2).
3. **Given** una consulta compleja que tardaría en devolver un volumen de resultados
   desproporcionado para el diagnóstico, **When** el sistema la ejecuta, **Then** acota el volumen
   de resultados que incorpora como evidencia a un conjunto representativo, indicando que existen
   más resultados disponibles si aplica (mismo criterio ya establecido para la evidencia de logs,
   spec 002).

---

### Edge Cases

- ¿Qué pasa si no hay ninguna base de datos configurada como fuente disponible para el caso? El
  sistema no debe intentar consultar nada ni bloquear el resto del diagnóstico — simplemente no
  dispone de esa fuente de evidencia, igual que hoy un caso puede completarse sin evidencia de
  logs si el usuario no la aporta.
- ¿Qué pasa si la pregunta o descripción del usuario, directa o indirectamente, intenta persuadir
  al sistema de ejecutar una operación de escritura o de acceder a una tabla fuera de alcance
  (p. ej. pidiendo explícitamente "actualiza el registro X" o mencionando una tabla no permitida)?
  El sistema debe rechazarlo igual que en la Historia 2 — la restricción no depende de que la
  petición sea o no intencionada.
- ¿Qué pasa si una consulta (simple o con cruces) tarda un tiempo perceptible en completarse? El
  sistema debe indicarlo visualmente como ya hace para otras operaciones de latencia perceptible
  (spec 004), y no debe dejar la conversación sin respuesta indefinidamente — debe existir un
  límite razonable de tiempo/iteraciones tras el cual el sistema informa que no pudo completar esa
  vía de evidencia y continúa con lo ya disponible.
- ¿Qué pasa si el mismo dato aparece tanto en la evidencia de logs como en la de base de datos, y
  ambas coinciden o se contradicen? El diagnóstico consolidado debe reflejar ambas fuentes sin
  descartar ninguna — ver FR-009.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir consultar una base de datos configurada como fuente de
  evidencia adicional para el diagnóstico, complementando (no sustituyendo) la evidencia de logs ya
  cubierta por la spec 002.
- **FR-002**: Toda consulta que el sistema ejecute contra la base de datos configurada DEBE ser
  exclusivamente de lectura — bajo ninguna circunstancia (incluida una instrucción directa o
  indirecta del usuario) el sistema DEBE ejecutar una operación que inserte, actualice o borre
  datos, ni que cree, modifique o elimine estructuras de la base de datos.
- **FR-003**: El sistema DEBE limitar el acceso a un conjunto explícitamente permitido de
  tablas/esquema — toda consulta que referencie una tabla fuera de ese conjunto DEBE rechazarse
  antes de ejecutarse contra la base de datos real.
- **FR-004**: El sistema DEBE poder resolver consultas simples, acotadas a una sola tabla, cuando
  eso baste para encontrar la evidencia relevante.
- **FR-005**: El sistema DEBE poder resolver consultas complejas que crucen información de más de
  dos tablas dentro del alcance permitido, cuando el diagnóstico lo requiera.
- **FR-006**: El sistema DEBE acotar el volumen de resultados de una consulta que incorpora como
  evidencia a un conjunto representativo, indicando cuando existan más resultados disponibles de
  los mostrados — mismo criterio ya establecido para la evidencia de logs (spec 002, FR-009a).
- **FR-007**: Si la base de datos configurada no está disponible o la consulta no puede
  completarse por un error de comunicación, el sistema DEBE informarlo y continuar el diagnóstico
  con la evidencia ya disponible por otras fuentes, sin interrumpir el resto de la conversación.
- **FR-008**: Cuando una consulta se rechaza por no ser de solo lectura o por referenciar una
  tabla fuera de alcance (FR-002/FR-003), el sistema DEBE informar que esa evidencia no está
  disponible dentro del alcance permitido, sin exponer detalles internos de la base de datos
  (nombres de tablas no permitidas, estructura del esquema) que no aporten valor al diagnóstico.
- **FR-009**: La evidencia obtenida de la base de datos DEBE incorporarse al diagnóstico
  consolidado del caso junto con la evidencia de logs ya existente (si la hay) — nunca como un
  resultado aislado que el usuario deba correlacionar manualmente.
- **FR-010**: Toda entrada registrada como evidencia de base de datos DEBE provenir del resultado
  real de una consulta efectivamente ejecutada — nunca de una enumeración libre generada por el
  modelo (mismo principio ya aplicado a la evidencia de logs, spec 002).
- **FR-011**: El sistema DEBE anunciar visiblemente al usuario cuándo va a consultar la base de
  datos configurada, antes de presentar el resultado — reutilizando el indicador de actividad ya
  establecido para operaciones de latencia perceptible (spec 004) — nunca de forma silenciosa (ver
  Clarifications, Sesión 2026-09-21).

### Key Entities

- **Fuente de Base de Datos**: la conexión configurada mediante variables de entorno (`.env`) sobre
  la que el sistema puede consultar, junto con el conjunto de tablas/esquema permitido para esa
  fuente (Historia 2) — nunca aportada ni seleccionada por el usuario durante la conversación (ver
  Clarifications, Sesión 2026-09-21).
- **Consulta Ejecutada**: una consulta de solo lectura real, junto con su resultado, usada como
  evidencia del caso — nunca una consulta o resultado hipotético.
- **Evidencia de Base de Datos**: el conjunto de hallazgos obtenidos de las consultas ejecutadas
  para un caso, incorporado al diagnóstico consolidado junto con la evidencia de logs existente
  (FR-009).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las consultas ejecutadas contra la base de datos configurada, en
  cualquier caso de uso, son de solo lectura y quedan dentro del conjunto de tablas permitido —
  verificado tanto en uso normal como en intentos deliberados de inducir lo contrario.
- **SC-002**: Un incidente cuya causa raíz solo es identificable correlacionando datos de al menos
  tres tablas distintas se diagnostica correctamente sin que el usuario tenga que escribir ninguna
  consulta manualmente.
- **SC-003**: Cuando la base de datos configurada no está disponible, el 100% de los casos
  continúan hasta completarse con la evidencia restante, sin que el usuario perciba un bloqueo o
  fallo total de la conversación.
- **SC-004**: El comportamiento conversacional y de diagnóstico ya existente (recepción de
  incidencia, búsqueda de logs, conversación adaptativa, presentación enriquecida — specs
  001-004) permanece idéntico para los casos que no tienen una base de datos configurada como
  fuente.

## Assumptions

- **Configuración de la conexión y del alcance permitido**: la conexión a la base de datos y el
  conjunto de tablas/esquema permitido se configuran una única vez, mediante variables de entorno
  en `.env` (análogo a `OPSSLEUTH_LLM_PROVIDER`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY` ya
  establecidos) — el usuario nunca las aporta ni las selecciona conversacionalmente. Confirmado
  explícitamente (ver Clarifications, Sesión 2026-09-21).
- **Motor de base de datos**: esta spec no asume un motor de base de datos específico (PostgreSQL,
  MySQL, SQL Server, etc.) — el mecanismo concreto de conexión y qué motores se soportan es una
  decisión técnica que corresponde a la fase de planificación, no al alcance funcional de esta
  spec.
- **Independencia respecto a la evidencia de logs**: la consulta a base de datos no depende de que
  la evidencia de logs ya se haya explorado — es una fuente de evidencia independiente, usable en
  cualquier momento del diagnóstico, con o sin evidencia de logs disponible (confirmado, ver
  Clarifications, Sesión 2026-09-21).
- **Varias fuentes de base de datos por caso**: se asume que, igual que con las fuentes de logs
  (spec 002, FR-013), un caso puede tener más de una fuente de base de datos configurada
  disponible, sin que eso cambie el comportamiento descrito aquí.
- **Sin cambios en el motor de modelo de lenguaje**: esta spec reutiliza el mismo mecanismo de
  intercambiabilidad ya establecido (`BaseChatModel` vía `crear_modelo_chat()`) y el mismo patrón
  de agente con uso de herramientas ya implementado para la búsqueda de logs (spec 002) — no
  introduce un motor de razonamiento paralelo.
- **Fuera de alcance**: la generación de un diagnóstico o respuesta final consolidada a partir de
  toda la evidencia recopilada (logs + base de datos) sigue fuera de alcance de esta spec, tal
  como ya lo estaba para la evidencia de logs (ver `specs/ESTADO_SPECS.md`, "Fuera de alcance") —
  esta spec entrega la evidencia de base de datos, no el diagnóstico final.
