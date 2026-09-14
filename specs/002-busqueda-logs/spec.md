# Feature Specification: Búsqueda en Archivos de Logs

**Feature Branch**: `002-busqueda-logs`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Este sistema debe ser el apoyo indispensable para cualquier equipo de soporte tecnico en la fase de investigacion, identificacion y diagnostico del problema reportado en el sistema o aplicacion por lo tanto el sistema debe ser capaz de buscar y recopilar informacion de distintas fuentes de informacion y a partir de ellas darle una respuesta al usuario a partir de las evidencias que contiene, dado que ya para el flujo se cuenta con una descripcion adecuada en el contexto del agente, esta sera una de las herramientas de investigacion, el agente debera ser capaz de realizar una busqueda de cuales son las entradas de logs que puedan estar relacionadas con el incidente descrito ubicandolas segun el contexto o si es posible y se dispone de la hora del incidente aislar los logs correspondientes a ese horario y con esto dar una apreciacion de lo que se ha visto en los logs cargando este primer diagnostico en el contexto para posteriormente dar una respuesta final. RF1: el usuario puede escoger si desea pasar una ruta al archivo de logs correspondiente o pasar los logs por escrito al chat. RF2: El modelo debe tener herramientas y hacer uso de estas mismas para ubicar informacion facilmente y eficazmente dentro del mismo archivo o los logs correspondiente, reduciendo asi el gasto de tokens al intentar leer todo el archivo. RF3: Si el usuario llegara a pegar mas de 4 lineas de logs en el chat estas no se enviaran directamente como contexto o input para el modelo si no que se generara un archivo para que asi pueda hacer consultas a la informacion suministrada. Adicionalmente, el modelo puede solicitar informacion general al usuario sobre el proyecto si es necesaria, para entender los logs o el problema descrito previamente."

## Clarifications

### Session 2026-09-03

- Q: Cuando la búsqueda encuentra un volumen muy grande de entradas coincidentes, ¿cómo
  debe manejarlo la apreciación inicial? → A: Limitar la apreciación a un conjunto acotado
  de entradas representativas (p. ej. las más relevantes o recientes), indicando que hay
  más coincidencias disponibles si el usuario las quiere ver.
- Q: Cuando se aportan varias fuentes de logs para el mismo caso (FR-013), ¿la apreciación
  inicial debe ser una sola consolidada o una independiente por fuente? → A: Apreciación
  inicial consolidada por caso, combinando los hallazgos de todas las fuentes de logs
  aportadas en un único resumen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aportar la evidencia de logs a analizar (Priority: P1)

Un integrante del equipo de soporte técnico que ya describió el problema (fase previa de
recepción de la incidencia) es invitado proactivamente por el sistema, en cuanto esa
descripción queda completa, a aportar los logs relacionados. El sistema le permite elegir
entre indicar la ruta a un archivo de logs ya descargado localmente, o pegar directamente
el contenido de los logs en la conversación.

**Why this priority**: Sin evidencia de logs disponible no hay nada que buscar ni
analizar; es el punto de entrada obligatorio de esta herramienta de investigación y la
base de la que dependen las demás capacidades. Es el MVP mínimo indispensable.

**Independent Test**: Puede probarse aportando una ruta a un archivo de logs existente y
verificando que el sistema la acepta y la usa como fuente; y, por separado, pegando
contenido de logs directamente en la conversación y verificando que también se acepta
como fuente de evidencia.

**Acceptance Scenarios**:

1. **Given** un caso cuya recepción de incidencia (spec 001) acaba de quedar con la
   información completa, **When** no hay evidencia de logs aportada todavía, **Then** el
   sistema invita proactivamente al usuario a aportar logs, sin que este tenga que
   solicitarlo.
2. **Given** un caso con el problema ya descrito, **When** el usuario indica la ruta a un
   archivo de logs accesible, **Then** el sistema la registra como fuente de evidencia
   para ese caso.
3. **Given** un caso con el problema ya descrito, **When** el usuario pega el contenido de
   los logs directamente en la conversación, **Then** el sistema lo registra como fuente
   de evidencia para ese caso.
4. **Given** que el usuario pega más de 4 líneas de contenido de logs en la conversación,
   **When** el sistema procesa ese mensaje, **Then** ese contenido NO se envía
   directamente como parte del contexto/entrada del modelo, sino que se guarda en un
   archivo (informando al usuario su ubicación/nombre) sobre el cual se realizarán las
   búsquedas posteriores.
5. **Given** que el usuario pega 4 líneas de logs o menos, **When** el sistema procesa ese
   mensaje, **Then** el contenido puede usarse directamente sin necesidad de generar un
   archivo.
6. **Given** que el usuario indica una ruta de archivo que no existe o no es accesible,
   **When** el sistema intenta acceder a ella, **Then** informa al usuario que no pudo
   acceder al archivo y le permite indicar otra ruta o pegar los logs directamente.

---

### User Story 2 - Localizar entradas de log relacionadas con el incidente (Priority: P2)

Con la evidencia de logs ya aportada, el sistema busca dentro de ella cuáles son las
entradas relacionadas con el incidente descrito, sin necesidad de procesar el contenido
completo de una sola vez. Si se conoce la hora aproximada del incidente, el sistema aísla
las entradas correspondientes a ese periodo; si no, localiza entradas relevantes según el
contenido de la descripción del problema (sistema afectado, síntoma).

**Why this priority**: Es la capacidad central que hace útil a esta herramienta frente a
simplemente tener el archivo disponible: sin una localización eficaz de las entradas
relevantes, el equipo de soporte tendría que revisar el archivo manualmente. Depende de
que exista evidencia aportada (US1).

**Independent Test**: Puede probarse aportando un archivo de logs de gran tamaño junto con
la hora aproximada del incidente, y verificando que el sistema aísla las entradas de ese
horario sin requerir que el usuario indique manualmente en qué parte del archivo están.
También puede probarse sin hora conocida, verificando que el sistema encuentra entradas
relacionadas con el contenido del problema descrito.

**Acceptance Scenarios**:

1. **Given** una fuente de logs aportada y una hora aproximada del incidente ya conocida en
   el contexto del caso, **When** el sistema busca evidencia, **Then** aísla y prioriza las
   entradas correspondientes a ese horario.
2. **Given** una fuente de logs aportada sin hora del incidente conocida, **When** el
   sistema busca evidencia, **Then** localiza entradas relacionadas con el sistema
   afectado o el síntoma descritos en el caso.
3. **Given** una fuente de logs de gran tamaño, **When** el sistema realiza la búsqueda,
   **Then** no requiere cargar ni procesar la totalidad del contenido de una sola vez para
   encontrar las entradas relevantes.
4. **Given** una fuente de logs aportada, **When** el sistema no encuentra ninguna entrada
   relacionada con el incidente, **Then** informa explícitamente al usuario que no
   encontró coincidencias, en lugar de omitir el resultado silenciosamente.

---

### User Story 3 - Obtener una apreciación inicial de lo encontrado en los logs (Priority: P3)

Una vez localizadas las entradas relevantes, el sistema elabora una apreciación inicial
(resumen) de lo que se observa en los logs respecto al incidente, y la incorpora al
contexto del caso para que quede disponible más adelante al momento de dar una respuesta
final (la generación de esa respuesta final es una capacidad de una fase posterior, fuera
de esta especificación).

**Why this priority**: Es el valor final entregado por esta herramienta — sin esta
apreciación, localizar entradas de log no aporta una conclusión útil al equipo de
soporte. Depende de que existan entradas localizadas (US2).

**Independent Test**: Puede probarse completando una búsqueda de logs y verificando que el
sistema presenta una apreciación inicial coherente basada en las entradas encontradas, y
que dicha apreciación sigue disponible si se le pregunta al sistema más adelante en la
misma conversación.

**Acceptance Scenarios**:

1. **Given** que el sistema localizó entradas de log relacionadas con el incidente,
   **When** finaliza la búsqueda, **Then** presenta al usuario una apreciación inicial de
   lo observado en esas entradas.
2. **Given** que se generó una apreciación inicial de los logs, **When** la conversación
   continúa, **Then** dicha apreciación permanece disponible en el contexto del caso para
   referencias posteriores.
3. **Given** que no se encontraron entradas relacionadas con el incidente, **When** el
   sistema concluye la búsqueda, **Then** la apreciación inicial refleja explícitamente la
   ausencia de evidencia encontrada, en vez de presentar una conclusión fabricada.

---

### User Story 4 - Solicitar contexto del proyecto cuando sea necesario para interpretar los logs (Priority: P4)

Dado que esta herramienta se usa para dar soporte a distintos productos y proyectos
propios, cuando el sistema encuentra información en los logs o en el problema descrito que
no puede interpretar sin conocer más sobre el proyecto o sistema al que pertenecen (por
ejemplo, terminología propia, nombres de componentes o convenciones de formato
desconocidas), puede solicitar al usuario información general sobre ese proyecto.

**Why this priority**: Mejora la calidad de la búsqueda y de la apreciación entregada,
pero el sistema puede intentar operar sin ella cuando el contenido es suficientemente
claro por sí mismo; por eso se prioriza después de las capacidades centrales de búsqueda y
apreciación (US2, US3), a las que sirve de apoyo.

**Independent Test**: Puede probarse aportando logs con terminología o estructura propia
de un proyecto no descrita previamente y verificando que el sistema pregunta por contexto
del proyecto antes de continuar; y, por separado, aportando logs con contenido claro y
verificando que el sistema no formula esa pregunta innecesariamente.

**Acceptance Scenarios**:

1. **Given** que el sistema encuentra contenido en los logs o en el problema descrito que
   no puede interpretar sin contexto adicional del proyecto, **When** procesa esa
   información, **Then** solicita al usuario información general sobre el proyecto o
   sistema correspondiente.
2. **Given** que el usuario aporta el contexto del proyecto solicitado, **When** el sistema
   continúa la búsqueda, **Then** incorpora esa información para interpretar los logs y el
   problema descrito.
3. **Given** que el sistema ya cuenta con suficiente información para interpretar los logs
   (porque el contenido es claro o el contexto ya fue aportado antes), **When** procesa la
   búsqueda, **Then** no vuelve a solicitar contexto del proyecto innecesariamente.

---

### Edge Cases

- ¿Qué ocurre si la ruta de archivo indicada no existe o no es accesible? El sistema lo
  informa y permite indicar otra ruta o pegar los logs directamente (ver US1, Escenario 5).
- ¿Qué ocurre si el archivo o el contenido pegado está vacío o no contiene texto
  interpretable como logs? El sistema debe informar que no pudo interpretar contenido de
  logs válido y solicitar una fuente distinta.
- ¿Qué ocurre si el usuario pega el contenido de los logs fragmentado en varios mensajes
  sucesivos? El sistema debe considerar el conjunto acumulado de líneas pegadas para
  decidir si supera el umbral de 4 líneas (RF3) y generar el archivo correspondiente si
  corresponde.
- ¿Qué ocurre si el usuario quiere aportar más de una fuente de logs para el mismo caso
  (por ejemplo, logs de dos servicios distintos)? El sistema debe permitir aportar y
  analizar más de una fuente dentro del mismo caso, y consolidar los hallazgos de todas
  ellas en una única apreciación inicial (ver FR-010a).
- ¿Qué ocurre si la hora del incidente indicada no coincide con ninguna entrada del
  archivo (por ejemplo, el archivo no cubre ese periodo)? El sistema debe informarlo en
  vez de presentar entradas de un horario distinto sin advertirlo.
- ¿Qué ocurre si la búsqueda encuentra un volumen muy grande de entradas coincidentes? El
  sistema debe limitar la apreciación inicial a un conjunto acotado de entradas
  representativas (las más relevantes o recientes), indicando que existen más
  coincidencias disponibles en lugar de intentar incluirlas todas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir al usuario aportar evidencia de logs de dos formas:
  indicando la ruta a un archivo de logs local, o pegando el contenido directamente en la
  conversación.
- **FR-002**: El sistema DEBE informar al usuario si la ruta de archivo indicada no existe
  o no es accesible, y permitirle indicar otra ruta o pegar los logs directamente.
- **FR-003**: Cuando el usuario pegue en la conversación más de 4 líneas de contenido de
  logs (contando el total acumulado si se pega en varios mensajes), el sistema NO DEBE
  usar ese contenido directamente como parte del contexto o entrada enviada al modelo;
  DEBE generar un archivo con ese contenido (ver FR-015) y realizar las búsquedas
  posteriores sobre él.
- **FR-004**: Cuando el usuario pegue 4 líneas de logs o menos, el sistema DEBE poder
  usar ese contenido directamente sin necesidad de generar un archivo.
- **FR-005**: El sistema DEBE localizar, dentro de la fuente de logs aportada, las
  entradas relacionadas con el incidente descrito previamente en el contexto del caso, sin
  necesidad de cargar o procesar la totalidad del contenido de una sola vez.
- **FR-006**: Si se dispone de la hora o el horario aproximado del incidente en el
  contexto del caso, el sistema DEBE aislar y priorizar las entradas de log
  correspondientes a ese periodo.
- **FR-007**: Si no se dispone de la hora del incidente, el sistema DEBE localizar
  entradas relevantes basándose en el contenido de la descripción del incidente (sistema
  afectado, síntoma).
- **FR-008**: El sistema DEBE informar explícitamente al usuario cuando no se encuentren
  entradas de log relacionadas con el incidente, en lugar de omitir ese resultado
  silenciosamente.
- **FR-009**: El sistema DEBE elaborar una apreciación inicial de lo observado en las
  entradas de log encontradas, relacionándolo con el incidente descrito.
- **FR-009a**: Cuando el número de entradas coincidentes sea muy grande, el sistema DEBE
  limitar la apreciación inicial a un conjunto acotado de entradas representativas (las
  más relevantes o recientes) e indicar al usuario que existen más coincidencias
  disponibles, en vez de intentar incluirlas todas.
- **FR-010**: El sistema DEBE incorporar esa apreciación inicial al contexto del caso, de
  forma que permanezca disponible para referencias posteriores dentro de la misma
  conversación.
- **FR-010a**: Cuando se hayan aportado varias fuentes de logs para el mismo caso
  (FR-013), el sistema DEBE producir una única apreciación inicial consolidada que combine
  los hallazgos de todas las fuentes, en vez de una apreciación independiente por cada
  fuente.
- **FR-011**: El sistema DEBE poder solicitar al usuario información general sobre el
  proyecto o sistema al que pertenecen los logs, cuando esa información sea necesaria para
  interpretar correctamente las entradas encontradas o el problema descrito.
- **FR-012**: El sistema NO DEBE solicitar información de contexto del proyecto cuando ya
  cuenta con información suficiente para interpretar los logs y el problema descrito.
- **FR-013**: El sistema DEBE permitir aportar y analizar más de una fuente de logs dentro
  de un mismo caso.
- **FR-014**: El sistema DEBE invitar proactivamente al usuario a aportar evidencia de
  logs en cuanto la recepción de la incidencia (spec 001) quede con la información
  completa, sin requerir que el usuario solicite explícitamente esta capacidad.
- **FR-015**: Cuando el sistema genere un archivo a partir de logs pegados en el chat
  (FR-003), DEBE informar al usuario que generó dicho archivo, incluyendo su
  ubicación/nombre, antes de continuar con la búsqueda.

### Key Entities

- **Fuente de Logs**: Representa el origen de los logs a analizar en un caso: una ruta a
  un archivo local, o un archivo generado a partir de contenido pegado por el usuario
  (cuando supera el umbral de 4 líneas). Se asocia al caso en investigación.
- **Entrada de Log Relevante**: Una línea o fragmento de log identificado como relacionado
  con el incidente, con su contenido y, si es identificable, su marca de tiempo.
- **Apreciación Inicial de Logs**: Resumen único por caso, elaborado a partir de las
  entradas relevantes encontradas en todas las fuentes de logs aportadas (o de la ausencia
  de ellas) — consolidado, no uno independiente por fuente — incorporado al contexto del
  caso para uso posterior en el diagnóstico final.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dada una fuente de logs de gran tamaño (cientos de miles de líneas) y una
  hora aproximada del incidente, el sistema aísla las entradas de ese horario sin que el
  usuario tenga que indicar manualmente en qué sección del archivo buscar.
- **SC-002**: El 100% de las veces que el usuario pega más de 4 líneas de logs en la
  conversación, ese contenido se maneja mediante un archivo generado (informando al
  usuario su ubicación) en lugar de enviarse directamente como contexto.
- **SC-003**: El 100% de las búsquedas sin coincidencias resultan en un mensaje explícito
  de "no se encontraron entradas relacionadas", nunca en una apreciación fabricada sin
  evidencia real.
- **SC-004**: Un usuario puede aportar una fuente de logs y obtener una apreciación
  inicial en menos de 5 intercambios de mensajes en el caso típico (sin contar las
  posibles preguntas de contexto de proyecto).
- **SC-005**: El sistema solicita contexto del proyecto únicamente cuando el contenido de
  los logs o del problema no es interpretable sin él; ante logs y descripciones claras, no
  se generan preguntas de contexto de proyecto innecesarias.

## Assumptions

- Esta funcionalidad asume que ya existe una descripción del incidente en el contexto del
  caso (fase de recepción de la incidencia, spec 001) antes de aportar evidencia de logs.
- El alcance de esta funcionalidad se limita a aportar evidencia de logs, localizar
  entradas relevantes y producir una apreciación inicial incorporada al contexto. La
  generación de una respuesta final o diagnóstico consolidado a partir de esa apreciación
  (y de otras fuentes de evidencia) se considera una fase posterior del agente, fuera del
  alcance de esta especificación.
- Consistente con la spec 001: el tratamiento de posibles datos sensibles (credenciales,
  información personal) que puedan aparecer en el contenido de los logs queda fuera de
  alcance en esta fase; no se realiza detección, advertencia ni redacción automática.
- Consistente con la spec 001: la evidencia de logs y la apreciación generada viven en el
  contexto de la conversación mientras dura el caso, sin persistencia duradera más allá de
  la sesión en esta fase.
- Se asume que los archivos de logs son de texto plano (en cualquier formato de log común),
  sin necesidad de soportar formatos binarios o estructurados propietarios en esta fase.
- Un caso puede tener más de una fuente de logs aportada (por ejemplo, de distintos
  servicios); cada fuente se busca de forma independiente, pero sus hallazgos se
  consolidan en una única apreciación inicial por caso (ver FR-010a).
