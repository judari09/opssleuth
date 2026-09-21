# Feature Specification: CLI Chat Enriquecida

**Feature Branch**: `004-cli-chat-enriquecida`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "Como nueva spec necesitamos ahora crear la cli mas amigable y que pueda brindar una mejor experiencia para el usuario, esta sera tipo chat y se debe construir con rich permitiendo visualizar adecuadamente las respuestas entregadas por el llm y las entradas del usuario, cada una de ellas debe ser facilmente diferenciable"

## Clarifications

### Session 2026-09-16

- Q: La sección "Assumptions" interpreta "tipo chat" como una conversación de terminal secuencial
  con estilo (colores/etiquetas/paneles), no como una interfaz de pantalla completa (TUI) con
  áreas de desplazamiento independientes. ¿Es correcta esa interpretación, o se esperaba un layout
  fijo de chat (historial con scroll arriba, entrada fija abajo)? → A: Conversación secuencial con
  estilo, sin áreas de pantalla fijas ni actualización en vivo — confirmado, coherente con la
  elección explícita de `rich` sobre una librería de TUI.
- Q: FR-001/FR-002 piden una "marca visual (color, estilo o etiqueta)" sin especificar si debe
  incluir siempre una etiqueta textual de rol, o si el color/estilo por sí solo basta. ¿La
  diferenciación usuario/sistema debe incluir siempre una etiqueta textual, además de cualquier
  color/estilo, para que la distinción siga funcionando en un entorno sin color (FR-006)? → A: Sí,
  la etiqueta textual de rol (p. ej. un prefijo o nombre de rol) es obligatoria siempre; el
  color/estilo es un refuerzo adicional, nunca el único mecanismo de diferenciación — es la única
  forma de que FR-001/FR-002 y FR-006 sean consistentes entre sí.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diferenciar de un vistazo quién dijo qué (Priority: P1)

Un integrante del equipo de soporte técnico usa la CLI de OpsSleuth durante una investigación.
En cada intercambio de la conversación, puede distinguir de un vistazo — sin tener que leer el
contenido con atención — qué texto escribió él mismo y qué texto respondió el sistema, incluso
cuando la conversación ya lleva varios intercambios en pantalla.

**Why this priority**: Es el problema concreto planteado: hoy la conversación se imprime como
texto corrido, sin ninguna señal visual que distinga una entrada del usuario de una respuesta del
sistema, lo que dificulta seguir el hilo de una investigación con varios intercambios. Es la base
mínima sobre la que se apoya cualquier otra mejora visual.

**Independent Test**: Puede probarse ejecutando una conversación con varios intercambios (varias
entradas del usuario y varias respuestas del sistema) y verificando que cada una lleva una
etiqueta textual de rol distinta y consistente (reforzada con color/estilo) que permite
identificar su origen sin leer el texto.

**Acceptance Scenarios**:

1. **Given** una conversación en curso, **When** el usuario escribe una entrada, **Then** esa
   entrada se presenta con una etiqueta textual de rol distinta y consistente (reforzada con
   color/estilo) que la identifica como proveniente del usuario.
2. **Given** una conversación en curso, **When** el sistema responde (una pregunta de aclaración,
   una confirmación, un resultado de búsqueda, etc.), **Then** esa respuesta se presenta con una
   etiqueta textual de rol distinta y consistente (reforzada con color/estilo) que la identifica
   como proveniente del sistema, diferente a la usada para las entradas del usuario.
3. **Given** una conversación con múltiples intercambios ya en pantalla, **When** el usuario
   revisa el historial visible, **Then** puede identificar el origen de cada intercambio sin
   necesidad de leer su contenido completo.

---

### User Story 2 - Leer las respuestas del sistema con formato legible (Priority: P2)

Un usuario recibe del sistema respuestas que combinan texto libre con elementos estructurados —
listas de hallazgos, énfasis en datos clave, secuencias de eventos encontrados en logs — tal como
ya las produce el motor de aclaración y el de búsqueda de logs (specs 001/002). En vez de ver ese
formato como texto plano con símbolos de marcado sin procesar, lo ve presentado de forma legible
(listas con viñetas, texto resaltado, bloques diferenciados), facilitando la lectura de
apreciaciones largas.

**Why this priority**: Mejora directamente la legibilidad del resultado más denso que produce hoy
el sistema (la apreciación inicial de logs y las preguntas de aclaración combinadas de la spec
003), pero depende de que ya exista la diferenciación básica de la Historia 1 — es una mejora
sobre la base ya visible, no un requisito independiente de ella.

**Independent Test**: Puede probarse completando una búsqueda de evidencia en logs que produzca
una apreciación con varios hallazgos, y verificando que el resultado se presenta con estructura
legible (listas, énfasis) en vez de mostrar el texto de marcado sin procesar.

**Acceptance Scenarios**:

1. **Given** una respuesta del sistema que incluye una lista de puntos (p. ej. una secuencia de
   eventos encontrados en logs), **When** se presenta al usuario, **Then** se muestra como una
   lista legible, no como texto plano con los símbolos de marcado visibles.
2. **Given** una respuesta del sistema que resalta un dato clave (p. ej. un valor o término
   importante), **When** se presenta al usuario, **Then** ese dato se distingue visualmente del
   resto del texto.
3. **Given** una respuesta del sistema que es una pregunta o confirmación simple de una sola
   línea, **When** se presenta al usuario, **Then** se sigue mostrando de forma clara y legible,
   sin necesitar estructura adicional.

---

### User Story 3 - Reconocer cuándo el sistema está trabajando o hay un problema (Priority: P3)

Mientras el sistema procesa una solicitud que toma un momento perceptible (p. ej. buscar
evidencia en un archivo de logs), el usuario ve una indicación de que el sistema está trabajando,
en vez de una pantalla sin actividad aparente. Cuando ocurre un error de comunicación con el
proveedor de modelo (ya manejado por 001/002/003), el mensaje correspondiente se distingue
visualmente de una respuesta normal, para que el usuario note de inmediato que algo no salió como
se esperaba.

**Why this priority**: Es una mejora de percepción de estado, valiosa pero de menor impacto que
poder distinguir quién dijo qué (Historia 1) o poder leer las respuestas con comodidad (Historia
2) — el sistema ya informa estos casos hoy, solo que sin distinción visual.

**Independent Test**: Puede probarse iniciando una búsqueda de evidencia en logs y verificando que
aparece una indicación de actividad mientras se procesa; y, por separado, forzando un error de
comunicación con el proveedor y verificando que el mensaje de error se distingue visualmente de
una respuesta normal del sistema.

**Acceptance Scenarios**:

1. **Given** el sistema inicia una operación que toma un momento perceptible (p. ej. búsqueda de
   evidencia en logs), **When** el usuario espera el resultado, **Then** ve una indicación de que
   el sistema está trabajando, no una pantalla sin actividad aparente.
2. **Given** el sistema no puede comunicarse con el proveedor de modelo configurado (mismo
   comportamiento de error ya implementado por 001/002/003), **When** informa el error al
   usuario, **Then** ese mensaje se distingue visualmente (p. ej. color o marca de advertencia)
   de una respuesta normal del sistema.

---

### Edge Cases

- ¿Qué pasa si la terminal en la que corre la CLI no soporta color ni formato enriquecido (p. ej.
  salida redirigida a un archivo, o una terminal muy limitada)? El sistema debe seguir siendo
  utilizable y legible en texto plano, sin fallar ni producir salida corrupta, y la diferenciación
  de origen (usuario vs. sistema) debe seguir siendo reconocible mediante la etiqueta textual de
  rol (FR-001/FR-002), ya que no depende del color.
- ¿Qué pasa si una respuesta del sistema es inusualmente larga (p. ej. una apreciación de logs muy
  extensa)? Debe seguir siendo legible, sin que el formato enriquecido dificulte encontrar la
  información en vez de ayudar.
- ¿Qué pasa si el usuario pega contenido de logs con múltiples líneas como entrada (comportamiento
  ya existente de 002)? La diferenciación visual de "entrada del usuario" debe seguir aplicando a
  todo el bloque pegado, sin romper la lectura de su contenido línea por línea.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE presentar toda entrada del usuario con una etiqueta textual de rol
  (p. ej. un prefijo o nombre de rol) consistente que la identifique como proveniente del usuario,
  reforzada además con color/estilo — la etiqueta textual es obligatoria; el color/estilo nunca es
  el único mecanismo de diferenciación (ver Clarifications, Sesión 2026-09-16).
- **FR-002**: El sistema DEBE presentar toda respuesta o mensaje del sistema (preguntas de
  aclaración, confirmaciones, resultados de búsqueda, mensajes de estado) con una etiqueta textual
  de rol consistente que la identifique como proveniente del sistema, reforzada además con
  color/estilo, distinta de la etiqueta usada para las entradas del usuario (FR-001).
- **FR-003**: El sistema DEBE renderizar el contenido estructurado de sus propias respuestas
  (listas, énfasis) de forma legible, sin mostrar los símbolos de marcado sin procesar al usuario.
- **FR-004**: El sistema DEBE indicar visualmente cuándo está procesando una operación que toma un
  momento perceptible (p. ej. la búsqueda de evidencia en logs) antes de presentar el resultado.
- **FR-005**: El sistema DEBE distinguir visualmente un mensaje de error o advertencia (p. ej. un
  fallo de comunicación con el proveedor de modelo) de una respuesta normal del sistema.
- **FR-006**: El sistema DEBE seguir siendo utilizable — sin fallar ni producir salida
  ininteligible — cuando se ejecuta en un entorno sin soporte de color o formato enriquecido. Como
  la etiqueta textual de rol (FR-001/FR-002) no depende del color, la diferenciación de origen se
  conserva incluso en ese entorno — no solo la legibilidad.
- **FR-007**: Este cambio DEBE ser exclusivamente de presentación: el comportamiento conversacional
  ya implementado por las specs 001, 002 y 003 (qué se pregunta, cuándo se invita a aportar logs,
  cómo se combinan las aclaraciones, cuándo se dispara la búsqueda de evidencia, etc.) NO debe
  alterarse como efecto de esta funcionalidad.

### Key Entities

Esta funcionalidad no introduce ni modifica entidades de dominio — es exclusivamente un cambio de
presentación sobre la conversación ya modelada por `Caso` y sus entidades asociadas (specs
001/002/003).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los mensajes mostrados en una conversación (tanto entradas del usuario
  como respuestas del sistema) lleva una etiqueta textual de rol que permite identificar su origen
  sin leer el contenido, incluso sin depender de color.
- **SC-002**: El 100% de las respuestas del sistema que incluyen contenido estructurado (listas,
  énfasis) se muestran con ese formato aplicado, sin símbolos de marcado sin procesar visibles.
- **SC-003**: La CLI se ejecuta sin errores y produce salida legible en un entorno sin soporte de
  color/formato enriquecido, conservando la diferenciación de origen (SC-001) mediante la etiqueta
  textual de rol.
- **SC-004**: El comportamiento conversacional (orden de preguntas, momento en que se invita a
  aportar logs, resultados producidos) es idéntico al existente antes de este cambio, verificado
  contra los escenarios ya documentados en `specs/001-recepcion-incidencia/quickstart.md`,
  `specs/002-busqueda-logs/quickstart.md` y `specs/003-conversacion-adaptativa/quickstart.md`.

## Assumptions

- **Alcance de "tipo chat"**: conversación de terminal con mensajes presentados secuencialmente y
  con estilo visual diferenciado (colores, etiquetas de rol, bloques destacados) — no una interfaz
  de pantalla completa con áreas de desplazamiento independientes (TUI). Confirmado explícitamente
  (ver Clarifications, Sesión 2026-09-16).
- El campo de entrada del usuario (el prompt que solicita texto) también recibe un estilo visual
  consistente con la marca de "usuario", no solo los mensajes ya enviados — refuerza la
  diferenciación pedida sin ampliar el alcance funcional.
- El renderizado de contenido estructurado (Historia 2) aplica al texto que el sistema ya produce
  hoy (incluido el que ya usa marcado tipo lista/énfasis, como las apreciaciones de logs) — no se
  pide ni se asume que el sistema deba generar contenido nuevo o distinto; solo que su
  presentación visual cambie.
- Sin cambios en el mecanismo de entrada del usuario más allá de su estilo visual: la lectura de
  texto (incluida la acumulación de contenido pegado multilínea de la spec 002) sigue funcionando
  exactamente igual que hoy.
- Sin cambios en la selección de proveedor de modelo (`OPSSLEUTH_LLM_PROVIDER`) ni en ninguna
  decisión ya registrada en `specs/ESTADO_SPECS.md` — esta spec es puramente de presentación.
