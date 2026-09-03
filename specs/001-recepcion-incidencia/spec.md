# Feature Specification: Recepción de Incidencia

**Feature Branch**: `001-recepcion-incidencia`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Este sistema debe ser el apoyo indispensable para cualquier equipo de soporte tecnico en la fase de investigacion, identificacion y diagnostico del problema reportado en el sistema o aplicacion por lo tanto el sistema debe ser capaz de buscar y recopilar informacion de distintas fuentes de informacion y a partir de ellas darle una respuesta al usuario a partir de las evidencias que pueda tener a la mano, como primera fase de este agente debe existir la funcionalidad de la recepcion de la incidencia, permitir al usuario describir el error encontrado y que este guarde esta descripcion como parte del contexto de la solucion. RF1: El sistema al inicio de cada caso debe solicitarle al usuario la descripcion del problema que ha encontrado o que le han reportado. RF2: El sistema guardara esta informacion como parte del contexto de toda la conversacion para que asi siempre tenga idea de lo que esta buscando. RF3: Si una descripcion puede parecer demasiado ambigua debera hacer preguntas al usuario para entender bien el problema."

## Clarifications

### Session 2026-08-31

- Q: Dentro de una misma conversación, ¿el sistema debe soportar un único caso para
  siempre, varios casos secuenciales, o varios casos en paralelo? → A: Una conversación
  puede albergar varios casos, pero de forma secuencial (se cierra/finaliza uno antes de
  iniciar el siguiente); nunca dos casos activos a la vez en la misma conversación.
- Q: ¿Un caso puede ser visto/aportado por varios usuarios (colaborativo), o es exclusivo
  del usuario/sesión que lo abrió? → A: El caso es exclusivo del usuario/sesión que lo
  abrió; no hay colaboración multiusuario sobre el mismo caso en esta fase.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar la descripción inicial del problema (Priority: P1)

Un integrante del equipo de soporte técnico inicia un nuevo caso en el sistema. Antes de
cualquier otra acción, el sistema le solicita que describa el problema o error que
encontró (o que le fue reportado). El usuario escribe la descripción y el sistema la
registra como el punto de partida del caso.

**Why this priority**: Sin esta capacidad no existe caso que investigar: es el punto de
entrada obligatorio de todo el flujo de diagnóstico y la base sobre la que se apoyan las
demás fases del agente (búsqueda de evidencia, correlación, respuesta). Es el MVP mínimo
indispensable.

**Independent Test**: Puede probarse iniciando un caso nuevo y verificando que el sistema
solicita explícitamente la descripción del problema antes de continuar, y que dicha
descripción queda registrada asociada al caso una vez el usuario la envía.

**Acceptance Scenarios**:

1. **Given** un usuario que inicia un caso nuevo, **When** el caso comienza, **Then** el
   sistema le solicita explícitamente que describa el problema o error encontrado antes de
   realizar cualquier otra acción.
2. **Given** que el sistema ha solicitado la descripción del problema, **When** el usuario
   envía una descripción, **Then** el sistema la registra como la descripción inicial del
   caso y confirma al usuario que fue recibida.
3. **Given** un caso ya iniciado con su descripción registrada, **When** el usuario intenta
   iniciar el mismo caso nuevamente, **Then** el sistema no vuelve a solicitar la
   descripción desde cero, sino que reconoce el caso existente.
4. **Given** un caso previo ya finalizado dentro de la conversación, **When** el usuario
   indica que tiene un nuevo problema que reportar, **Then** el sistema inicia un caso
   nuevo y vuelve a solicitar la descripción del problema, sin mezclar su contexto con el
   del caso anterior.
5. **Given** un caso activo aún sin finalizar, **When** el usuario intenta iniciar un caso
   adicional en la misma conversación, **Then** el sistema no procesa dos casos en
   paralelo: informa que hay un caso en curso y solicita confirmación antes de darlo por
   finalizado y abrir uno nuevo.

---

### User Story 2 - Mantener el contexto del caso disponible durante toda la conversación (Priority: P2)

Mientras el equipo de soporte continúa interactuando con el sistema dentro de un mismo
caso (haciendo preguntas, aportando más detalles, revisando hallazgos), el sistema
mantiene siempre presente la descripción original del problema y todo lo que se ha
aportado sobre él, de forma que ninguna respuesta o acción posterior pierde de vista qué
es lo que se está investigando.

**Why this priority**: Un agente que "olvida" el problema original a mitad de la
conversación obliga al usuario a repetirse y genera desconfianza; mantener el contexto es
lo que permite que las fases posteriores (búsqueda de evidencia, diagnóstico) trabajen
sobre información consistente. Depende de que exista una descripción inicial (US1), por
lo que es la segunda prioridad.

**Independent Test**: Puede probarse iniciando un caso, registrando una descripción,
sosteniendo varios intercambios adicionales con el sistema (sin repetir la descripción
original) y verificando que el sistema sigue pudiendo referirse correctamente al problema
original en cualquier punto de la conversación.

**Acceptance Scenarios**:

1. **Given** un caso con una descripción inicial ya registrada, **When** el usuario
   continúa la conversación aportando información adicional o respondiendo preguntas,
   **Then** el sistema conserva la descripción original junto con la información nueva
   como parte del contexto del caso.
2. **Given** un caso con contexto acumulado (descripción inicial + aclaraciones), **When**
   se le solicita al sistema en cualquier momento que resuma o recuerde el problema que se
   está investigando, **Then** el sistema responde de forma consistente con la descripción
   original y las aclaraciones recibidas, sin contradicciones ni omisiones relevantes.
3. **Given** un caso en curso, **When** el usuario aporta un dato adicional sobre el
   problema, **Then** ese dato queda incorporado al contexto del caso y disponible para
   referencias posteriores dentro de la misma conversación.

---

### User Story 3 - Solicitar aclaraciones ante descripciones ambiguas (Priority: P3)

Cuando la descripción que el usuario proporciona no contiene suficiente información para
entender el problema (por ejemplo, no indica qué sistema o aplicación se vio afectado, qué
error o síntoma se observó, o cuándo ocurrió), el sistema, en lugar de continuar con
información insuficiente, le hace al usuario preguntas puntuales para completar los datos
que faltan antes de considerar el caso listo para avanzar.

**Why this priority**: Mejora la calidad del caso capturado y evita diagnósticos basados
en información incompleta, pero el sistema puede operar (con una descripción básica) sin
esta capacidad; por eso se prioriza después de la captura (US1) y la persistencia del
contexto (US2), de los cuales depende (las aclaraciones se incorporan al mismo contexto
que US2 mantiene).

**Independent Test**: Puede probarse enviando una descripción deliberadamente vaga o
incompleta (por ejemplo, "no funciona") y verificando que el sistema, en vez de aceptarla
sin más, responde con preguntas específicas orientadas a completar los datos faltantes; al
responderlas, el caso queda con una descripción suficientemente clara.

**Acceptance Scenarios**:

1. **Given** que el usuario envía una descripción del problema que carece de elementos
   clave para el diagnóstico (sistema/aplicación afectado, síntoma observado, momento en
   que ocurrió), **When** el sistema evalúa la descripción, **Then** el sistema identifica
   la ambigüedad y formula al usuario preguntas puntuales sobre los datos faltantes en
   lugar de continuar sin ellos.
2. **Given** que el sistema ha formulado preguntas de aclaración, **When** el usuario las
   responde, **Then** el sistema incorpora las respuestas al contexto del caso junto con la
   descripción original.
3. **Given** que el usuario envía una descripción ya suficientemente clara y completa,
   **When** el sistema la evalúa, **Then** el sistema no formula preguntas de aclaración
   innecesarias y continúa con el flujo del caso.
4. **Given** que el sistema ha formulado preguntas de aclaración, **When** el usuario
   indica explícitamente que no puede aportar más detalles, **Then** el sistema deja de
   insistir y continúa el caso con la mejor información disponible, dejando constancia de
   qué datos quedaron sin confirmar.

---

### Edge Cases

- ¿Qué ocurre si el usuario envía una descripción vacía o compuesta solo por espacios/
  ruido sin contenido útil? El sistema debe volver a solicitar una descripción explicando
  que no pudo interpretar contenido válido.
- ¿Qué ocurre si el usuario intenta saltarse la descripción inicial y pide directamente un
  diagnóstico o resultado? El sistema debe insistir en obtener al menos una descripción
  mínima antes de avanzar a fases posteriores.
- ¿Qué ocurre si el usuario, durante la ronda de aclaraciones, aporta información que
  contradice lo dicho en la descripción original? El sistema debe conservar ambos datos en
  el contexto y señalar la inconsistencia al usuario en vez de descartar silenciosamente
  uno de los dos.
- ¿Qué ocurre si el usuario aporta una descripción extremadamente extensa con múltiples
  problemas mezclados? El sistema debe identificar que hay más de un problema y pedir al
  usuario que confirme cuál es el problema principal a investigar en este caso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Al iniciar un caso nuevo, el sistema DEBE solicitar explícitamente al
  usuario que describa el problema o error que encontró o que le fue reportado, antes de
  realizar cualquier otra acción del caso.
- **FR-002**: El sistema DEBE registrar la descripción proporcionada por el usuario como la
  descripción inicial del caso.
- **FR-003**: El sistema DEBE confirmar al usuario que su descripción fue recibida y
  registrada.
- **FR-004**: El sistema DEBE mantener la descripción inicial del caso, junto con toda
  información adicional aportada, disponible como contexto durante el resto de la
  conversación asociada a ese caso.
- **FR-005**: El sistema DEBE poder recuperar y referenciar correctamente el problema
  original en cualquier punto posterior de la conversación del caso, sin requerir que el
  usuario lo repita.
- **FR-006**: El sistema DEBE evaluar si la descripción recibida contiene la información
  mínima necesaria para el diagnóstico: sistema o aplicación afectada, síntoma o error
  observado, y momento o frecuencia en que ocurre.
- **FR-007**: Si la descripción no contiene esa información mínima, el sistema DEBE
  formular al usuario preguntas puntuales dirigidas específicamente a los datos faltantes,
  en lugar de continuar con información insuficiente.
- **FR-008**: El sistema DEBE incorporar las respuestas a las preguntas de aclaración al
  contexto del caso, junto con la descripción original.
- **FR-009**: El sistema NO DEBE formular preguntas de aclaración cuando la descripción ya
  contiene la información mínima necesaria.
- **FR-010**: El sistema DEBE permitir al usuario indicar que no puede aportar más
  información durante una ronda de aclaraciones, y en ese caso DEBE continuar el caso con
  la información disponible, dejando constancia de los datos que quedaron sin confirmar.
- **FR-011**: El sistema DEBE rechazar una descripción vacía o sin contenido interpretable
  y volver a solicitarla, indicando al usuario que no pudo interpretar la anterior.
- **FR-012**: El sistema NO DEBE realizar detección, advertencia o redacción de datos
  sensibles (credenciales, información personal) dentro de la descripción del problema o
  de las aclaraciones en esta fase; dicho tratamiento queda fuera de alcance y se considera
  una posible mejora futura.
- **FR-013**: El sistema DEBE permitir que, una vez finalizado un caso dentro de una
  conversación, el usuario inicie un caso nuevo en esa misma conversación, solicitando de
  nuevo la descripción del problema y manteniendo el contexto del caso nuevo separado del
  de los casos anteriores.
- **FR-014**: El sistema DEBE mantener como máximo un caso activo a la vez por
  conversación; si el usuario intenta iniciar un caso adicional mientras uno sigue activo,
  el sistema DEBE informarlo y solicitar confirmación antes de finalizar el caso en curso y
  abrir uno nuevo.
- **FR-015**: El sistema NO DEBE compartir el contexto de un caso entre distintos
  usuarios o sesiones; cada caso es exclusivo del usuario/sesión que lo originó en esta
  fase.

### Key Entities

- **Caso**: Representa una incidencia individual en investigación. Incluye la descripción
  inicial del problema, el estado de la información recopilada (completa/pendiente de
  aclaración), el estado del caso (activo/finalizado) y el historial de aclaraciones
  asociadas. Es la unidad sobre la que se mantiene el contexto. Una conversación puede
  contener varios Casos a lo largo del tiempo, pero solo uno puede estar activo a la vez;
  el contexto de cada Caso se mantiene separado del de los demás.
- **Descripción del Problema**: El relato inicial, en lenguaje natural, que el usuario
  aporta sobre el error o incidencia encontrada. Puede incluir el sistema/aplicación
  afectada, el síntoma observado y el momento en que ocurrió.
- **Aclaración**: Par de pregunta formulada por el sistema y respuesta aportada por el
  usuario, generado cuando la descripción inicial resulta ambigua o incompleta. Se asocia
  al Caso y pasa a formar parte de su contexto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los casos nuevos inician con el sistema solicitando la
  descripción del problema antes de cualquier otra interacción del caso.
- **SC-002**: En una conversación de caso con al menos 10 intercambios posteriores a la
  descripción inicial, el sistema referencia correctamente el problema original el 100% de
  las veces que se le solicita, sin que el usuario necesite repetirlo.
- **SC-003**: Ante una descripción incompleta (falta al menos uno de: sistema afectado,
  síntoma, momento de ocurrencia), el sistema formula preguntas de aclaración relevantes a
  los datos faltantes en el 100% de los casos, en vez de continuar sin ellos.
- **SC-004**: Ante una descripción ya completa, el sistema no formula preguntas de
  aclaración innecesarias en el 100% de los casos.
- **SC-005**: Un usuario puede completar la recepción de su incidencia (descripción inicial
  más, si aplica, ronda de aclaraciones) en menos de 5 intercambios de mensajes en el caso
  típico.

## Assumptions

- El alcance de esta funcionalidad se limita a la recepción, evaluación de ambigüedad,
  aclaración y almacenamiento en contexto de la descripción inicial del caso. La búsqueda
  de evidencia en fuentes de observabilidad y la generación de un diagnóstico o respuesta
  final se consideran fases posteriores del agente, fuera del alcance de esta
  especificación.
- La interacción con el usuario ocurre en una conversación de tipo texto/chat entre el
  usuario de soporte técnico y el sistema; no se contempla en esta fase la recepción de
  incidencias por otros canales (formularios web, integraciones con sistemas de tickets,
  correo, etc.).
- Una conversación puede contener varios casos a lo largo del tiempo, pero de forma
  secuencial: solo un caso puede estar activo a la vez por conversación (confirmado con el
  solicitante).
- Cada caso es exclusivo del usuario/sesión que lo abrió; no se contempla colaboración
  multiusuario (varias personas aportando al mismo caso) en esta fase (confirmado con el
  solicitante).
- Los criterios mínimos de completitud de una descripción (sistema/aplicación afectada,
  síntoma observado, momento/frecuencia) se basan en prácticas estándar de intake de
  incidentes en soporte técnico y sirven como línea base para decidir si se requieren
  aclaraciones.
- El tratamiento de posibles datos sensibles (credenciales, información personal) que el
  usuario incluya en la descripción o en sus aclaraciones queda fuera de alcance en esta
  fase; no se realiza detección, advertencia ni redacción automática (confirmado con el
  solicitante).
