# Feature Specification: Conversación Adaptativa

**Feature Branch**: `003-conversacion-adaptativa`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "Mejorar el dinamismo de la conversación del CLI de OpsSleuth: actualmente el flujo (recepción de incidencia + búsqueda de evidencia en logs) es una secuencia rígida de pasos guiados. Esto es apropiado para un usuario nuevo, pero se vuelve tedioso para un usuario con más experiencia en la herramienta, que preferiría poder avanzar más rápido (p. ej. aportar varios datos a la vez, saltarse pasos ya cubiertos, o ir directo a aportar el log sin esperar cada pregunta una por una) sin perder la capacidad de aclaración/guía cuando realmente falta información. La spec debe definir cómo detectar o permitir esta mayor fluidez sin romper el comportamiento ya implementado y probado de las specs 001 (Recepción de Incidencia) y 002 (Búsqueda en Archivos de Logs) — ver specs/ESTADO_SPECS.md para las decisiones y contratos ya establecidos que esta nueva spec debe respetar."

## Clarifications

### Session 2026-09-14

- Q: El primer prompt del flujo lee una sola línea de entrada; el paso dedicado de logs
  (spec 002) sabe acumular varias líneas hasta una línea en blanco cuando detecta contenido
  pegado. ¿El reconocimiento de evidencia en el mensaje inicial (Historia 1) debe cubrir
  también contenido de log pegado multilínea, o solo una ruta de archivo (una línea)? → A:
  Solo una ruta de archivo reconocible en el mensaje inicial (una línea); el contenido de
  log pegado multilínea sigue exclusivamente a cargo del paso dedicado ya existente — el
  primer prompt no cambia su mecanismo de lectura de una sola línea.
- Q: El "batching" de aclaraciones pendientes (Historia 2), ¿debe cubrir solo el lote
  inicial de preguntas generadas juntas tras evaluar la descripción inicial
  (`sistema_afectado`/`sintoma`/`momento`, más `problema_principal` si aplica), o cualquier
  conjunto de aclaraciones pendientes en cualquier momento de la conversación (incluidas
  las que surjan incrementalmente más adelante, p. ej. por una contradicción)? → A: Solo el
  lote inicial generado juntas tras evaluar la descripción inicial; las aclaraciones que
  surjan después en la conversación se siguen formulando una por una, como hoy — no se
  introduce una cola de aclaraciones pendientes de estado persistente.
- Q: Cuando el mensaje inicial combina descripción + ruta de logs pero aún quedan
  aclaraciones pendientes, ¿la ruta se valida/lee de inmediato, o se registra la referencia
  y se difiere su validación real al mismo punto en que hoy se dispara la búsqueda de
  evidencia (recepción completa)? → B: Se registra la referencia tal cual; la validación
  real (y su posible mensaje de error) se difiere hasta que la recepción de la incidencia
  esté completa — mismo punto de fase ya implementado y probado por la spec 002, sin
  intercalar avisos de logs en medio del flujo de aclaración de la descripción.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aportar la descripción y la ruta de logs en un mismo mensaje (Priority: P1)

Un usuario que ya conoce la herramienta escribe, en su primer mensaje del caso, tanto la
descripción del problema como una ruta de archivo de log reconocible, en vez de esperar a
que el sistema se la pida explícitamente en un paso posterior. El sistema reconoce ambas
piezas de información en ese único mensaje y no vuelve a solicitar la evidencia de logs que
el usuario ya aportó. Fuera de alcance: contenido de log pegado directamente (multilínea)
en el mensaje inicial — ese caso sigue a cargo del paso dedicado ya existente (spec 002),
porque el primer prompt del flujo solo lee una línea de entrada (ver Clarifications).

**Why this priority**: Es el caso de fricción más visible y frecuente detectado en uso
real: el sistema ignoraba la referencia a logs ya incluida en el mensaje inicial y volvía
a pedirla en un paso separado, obligando al usuario a repetir información que ya había
dado. Resolverlo por sí solo ya entrega valor perceptible sin tocar el resto del flujo.

**Independent Test**: Puede probarse iniciando un caso con un mensaje que combine
descripción del problema y una ruta de archivo de log válida, y verificando que el sistema
registra ambos sin formular la pregunta "¿puedes aportar los logs relacionados?".

**Acceptance Scenarios**:

1. **Given** un caso recién iniciado, **When** el usuario envía en su primer mensaje una
   descripción completa del problema junto con una ruta de archivo de log reconocible,
   **Then** el sistema registra la descripción y la fuente de logs sin volver a pedir la
   evidencia por separado.
2. **Given** un caso recién iniciado, **When** el usuario envía en su primer mensaje solo la
   descripción del problema junto con contenido de log pegado (varias líneas, sin forma de
   ruta de archivo), **Then** el sistema no lo trata como evidencia de logs automáticamente
   — conserva la descripción y, al completar la recepción, sigue invitando explícitamente a
   aportar logs mediante el paso dedicado ya existente (ver Clarifications, Sesión
   2026-09-14).
3. **Given** un mensaje inicial que combina descripción y una referencia a una ruta de logs
   que resulta inválida o inaccesible (p. ej. una ruta que no existe), **When** la recepción
   de la incidencia se completa y el sistema intenta validar esa fuente (mismo punto de
   fase en que hoy se dispara la búsqueda de evidencia, ver Clarifications), **Then**
   conserva la descripción del problema, informa que no pudo acceder a esa evidencia, y
   ofrece al usuario aportarla de nuevo — sin descartar la descripción ya recibida.

---

### User Story 2 - Responder de una vez el lote inicial de aclaraciones pendientes (Priority: P2)

Cuando el sistema genera, tras evaluar la descripción inicial, más de una pregunta de
aclaración pendiente a la vez (p. ej. falta el sistema afectado y el momento del
incidente), un usuario con experiencia responde ambas en un único mensaje de texto libre en
vez de contestar una por una en el orden en que se le preguntan. El sistema interpreta la
respuesta combinada, la asocia correctamente a cada campo pendiente, y solo vuelve a
preguntar por lo que realmente siga faltando. Fuera de alcance: aclaraciones que surjan más
adelante en la conversación (p. ej. por una contradicción detectada en una respuesta
posterior) — esas se siguen formulando una por una, como hoy (ver Clarifications).

**Why this priority**: Reduce directamente el número de intercambios necesarios para
completar la recepción de la incidencia, que es la queja concreta sobre "tener que
responder pregunta por pregunta". Depende de que exista más de una aclaración pendiente a
la vez, por lo que es un escalón por encima de la Historia 1 en cuanto a la información que
el sistema debe correlacionar.

**Independent Test**: Puede probarse forzando una descripción inicial a la que le falten
dos campos (p. ej. solo el síntoma, sin sistema afectado ni momento), y verificando que una
única respuesta que cubra ambos datos evita que el sistema pregunte por el segundo campo
por separado.

**Acceptance Scenarios**:

1. **Given** el sistema tiene dos o más preguntas de aclaración pendientes, **When** el
   usuario responde en un solo mensaje con información que cubre todas ellas, **Then** el
   sistema registra cada dato en el campo correspondiente y no repite ninguna de esas
   preguntas.
2. **Given** el sistema tiene dos o más preguntas de aclaración pendientes, **When** el
   usuario responde en un solo mensaje que solo cubre parte de ellas, **Then** el sistema
   registra los datos aportados y sigue preguntando únicamente por los campos que
   permanecen sin información.
3. **Given** el sistema tiene preguntas de aclaración pendientes, **When** el usuario
   responde de forma ambigua o sin relación clara con ninguno de los campos pendientes,
   **Then** el sistema mantiene el comportamiento de aclaración existente (vuelve a
   preguntar o marca el dato como sin confirmar si el usuario indica que no puede
   aportarlo) sin inventar una correlación incorrecta.

---

### User Story 3 - Preservar el flujo guiado completo para quien lo necesita (Priority: P1)

Un usuario nuevo en la herramienta, o uno que aporta la información de forma incompleta o
fragmentada, sigue recibiendo el mismo comportamiento guiado paso a paso que ya ofrecen las
specs 001 y 002: preguntas de aclaración una por una cuando la respuesta combinada no cubre
todo, e invitación explícita a aportar evidencia de logs cuando no la aportó de entrada.

**Why this priority**: Es la condición de no regresión de todo el esfuerzo: la mayor
fluidez para usuarios experimentados (Historias 1 y 2) no debe degradar la experiencia
guiada ya implementada y probada para el resto de los casos. Tiene la misma prioridad que
la Historia 1 porque ambas deben cumplirse simultáneamente para que la funcionalidad sea
aceptable.

**Independent Test**: Puede probarse repitiendo íntegramente los escenarios de validación
ya documentados en `specs/001-recepcion-incidencia/quickstart.md` y
`specs/002-busqueda-logs/quickstart.md` y verificando que su resultado no cambia.

**Acceptance Scenarios**:

1. **Given** un usuario que envía una descripción inicial vaga o incompleta, **When** el
   sistema evalúa la descripción, **Then** sigue formulando las preguntas de aclaración
   correspondientes una a la vez, igual que hoy.
2. **Given** un caso con la recepción de incidencia ya completa y sin evidencia de logs
   aportada en el mensaje inicial, **When** la recepción concluye, **Then** el sistema
   sigue invitando explícitamente a aportar evidencia de logs, igual que hoy.
3. **Given** cualquiera de los escenarios de validación de 001 o 002, **When** se ejecutan
   sin combinar información entre pasos, **Then** el comportamiento observable es idéntico
   al descrito en esas specs.

---

### Edge Cases

- ¿Qué pasa si el usuario aporta, en el mensaje inicial, una referencia a logs que en
  realidad es parte de la descripción del problema (p. ej. menciona el nombre de un
  archivo de log sin intención de aportarlo como evidencia todavía)? El sistema no debe
  registrar una fuente de logs por error a partir de una simple mención textual — solo a
  partir de una referencia con forma reconocible de ruta de archivo (mismo criterio de
  ruta ya usado en el paso dedicado de 002; ver Clarifications, Sesión 2026-09-14, sobre
  el alcance acotado a rutas en el mensaje inicial).
- ¿Qué pasa si la respuesta combinada de la Historia 2 introduce una contradicción con el
  contexto ya registrado (p. ej. menciona un sistema distinto al ya confirmado)? El sistema
  debe seguir aplicando la detección de contradicción ya existente (spec 001) para cada
  dato extraído, sin que el hecho de venir en una respuesta combinada la desactive.
- ¿Qué pasa si el usuario mezcla, en el mismo mensaje inicial, la descripción de más de un
  problema distinto además de la evidencia de logs? El sistema mantiene el comportamiento
  ya existente de pedir confirmación de cuál investigar (spec 001) antes de decidir a cuál
  de los problemas asociar la evidencia de logs aportada.
- ¿Qué pasa si el usuario intenta "saltarse" un paso que en realidad es obligatorio (p. ej.
  pide iniciar la búsqueda de logs sin haber aportado nunca una descripción del problema)?
  El sistema no debe permitirlo: la descripción inicial del problema sigue siendo un
  requisito de entrada de todo caso (FR-001/FR-002 de 001).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Al recibir el primer mensaje de un caso nuevo, el sistema DEBE detectar si,
  además de la descripción del problema, el mensaje contiene una referencia reconocible a
  una **ruta de archivo de log** (una sola línea), usando el mismo criterio de
  reconocimiento de rutas ya establecido por la spec 002 para el paso dedicado de
  evidencia. Contenido de log pegado directamente (multilínea) queda fuera de alcance de
  esta detección en el mensaje inicial — ver Clarifications, Sesión 2026-09-14.
- **FR-002**: Si el sistema detecta una ruta de logs en el mensaje inicial, DEBE registrarla
  como fuente de logs del caso (sin validar aún su accesibilidad, ver FR-003) y NO debe
  volver a formular la invitación explícita a aportar logs para esa fuente ya cubierta.
- **FR-003**: La validación real de accesibilidad de una fuente de logs registrada a partir
  del mensaje inicial (FR-002) DEBE diferirse al mismo punto de fase en que hoy se dispara
  la búsqueda de evidencia (recepción de la incidencia completa) — no antes, para no
  intercalarla con el flujo de aclaración de la descripción. Si en ese momento resulta
  inválida o inaccesible, el sistema DEBE conservar la descripción del problema ya recibida,
  informar del problema de acceso, y volver a invitar al usuario a aportar la evidencia
  (mismo mensaje de error ya usado por el paso dedicado de 002).
- **FR-004**: Cuando el lote inicial de preguntas de aclaración generado tras evaluar la
  descripción inicial tenga dos o más preguntas pendientes a la vez, el sistema DEBE
  aceptar una única respuesta de texto libre que cubra más de una de ellas, asociando cada
  dato reconocido al campo de aclaración correspondiente. Las aclaraciones que surjan
  después de ese lote inicial (p. ej. por una contradicción detectada más adelante) quedan
  fuera de este comportamiento y se siguen formulando una por una (ver Clarifications).
- **FR-005**: Tras procesar una respuesta combinada del lote inicial (FR-004), el sistema
  DEBE seguir formulando únicamente las preguntas correspondientes a los campos que
  continúen sin información — nunca repetir una pregunta ya resuelta por la respuesta
  combinada.
- **FR-006**: El sistema DEBE seguir aplicando, sobre cada dato extraído de una respuesta
  combinada, la misma detección de contradicción con el contexto previo ya definida por la
  spec 001 — la fusión de varias respuestas en un solo mensaje no exime de esta validación.
- **FR-007**: Cuando el usuario no aporte toda la información de una vez (mensaje inicial
  sin evidencia de logs, o respuesta que no cubre todas las aclaraciones pendientes), el
  sistema DEBE preservar exactamente el comportamiento guiado paso a paso ya implementado
  por 001 y 002 (una pregunta de aclaración a la vez; invitación explícita a aportar logs
  tras completar la recepción).
- **FR-008**: El sistema DEBE seguir exigiendo la descripción inicial del problema como
  primer requisito de todo caso nuevo — ninguna forma de fluidez añadida por esta spec
  puede omitir ese paso (FR-001/FR-002 de 001).
- **FR-009**: El sistema DEBE seguir aplicando el comportamiento ya existente de
  confirmación de "problema principal" (spec 001) cuando el mensaje inicial describe más
  de un problema distinto, antes de asociar cualquier evidencia de logs aportada en ese
  mismo mensaje a uno de ellos.

### Key Entities

- **Caso**: entidad ya existente (`src/opssleuth/domain/case.py`, specs 001/002); esta
  spec no introduce campos nuevos, solo cambia en qué momento de la conversación se pueden
  poblar `descripcion_inicial`, `aclaraciones` y `fuentes_logs` a partir de un mismo
  mensaje del usuario.
- **Aclaración**: entidad ya existente (`Aclaracion`, spec 001); esta spec no cambia su
  forma, solo permite que varias aclaraciones pendientes se resuelvan a partir de una única
  respuesta del usuario en vez de una respuesta por pregunta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario que aporta descripción y evidencia de logs en el mismo mensaje
  inicial completa la recepción de la incidencia con evidencia registrada sin que el
  sistema le pida el log una segunda vez.
- **SC-002**: El número de intercambios necesarios para completar la recepción de la
  incidencia, cuando el usuario aporta toda la información pendiente en una sola respuesta,
  se reduce a como máximo un intercambio por bloque de información combinada (en vez de uno
  por campo individual).
- **SC-003**: El 100% de los escenarios de validación ya documentados en
  `specs/001-recepcion-incidencia/quickstart.md` y `specs/002-busqueda-logs/quickstart.md`
  sigue comportándose exactamente igual (sin regresiones) cuando el usuario no combina
  información entre pasos.
- **SC-004**: Ningún dato aportado en un mensaje combinado (descripción + logs, o varias
  aclaraciones a la vez) se pierde o se asocia al campo incorrecto respecto al mismo dato
  aportado paso a paso.

## Assumptions

- El mecanismo de reconocimiento de "referencia a ruta de archivo de log" en el mensaje
  inicial reutiliza el criterio heurístico de una sola línea ya implementado para el paso
  dedicado de evidencia en la spec 002 (`_parece_ruta_de_archivo`), en vez de introducir uno
  nuevo — evita duplicar lógica de detección (Principio IV, simplicidad). No se extiende el
  mecanismo de lectura multilínea del paso dedicado al primer prompt del flujo (ver
  Clarifications, Sesión 2026-09-14).
- La correlación de una respuesta combinada con varios campos de aclaración pendientes
  reutiliza el mismo motor de evaluación basado en LLM ya usado por 001/002
  (`evaluar_descripcion` / `crear_modelo_chat()`), sin introducir un mecanismo de
  interpretación paralelo — ver `specs/ESTADO_SPECS.md`, sección "Motor de modelo de
  lenguaje (LLM)".
- Esta spec no introduce un modo o bandera explícita de "usuario experimentado" que el
  usuario deba activar: la mayor fluidez se ofrece de forma transparente cuando el usuario
  aporta la información combinada por su cuenta, y el flujo guiado sigue disponible de
  forma automática cuando no lo hace. Si una spec futura necesita un modo explícito
  configurable, deberá justificarlo por separado.
- No se modifica el comportamiento de la búsqueda de evidencia en logs en sí (spec 002,
  `buscar_evidencia`/agente LangGraph) — esta spec solo afecta en qué momento de la
  conversación se recopila y registra la información de entrada, no cómo se analiza.
- Sin persistencia duradera de casos entre sesiones (consistente con la decisión ya
  registrada en `specs/ESTADO_SPECS.md`) — esta spec no cambia ese alcance.
