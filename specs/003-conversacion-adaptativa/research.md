# Research: Conversación Adaptativa

## Decisión 1: Extracción de ruta de logs desde el mensaje inicial — reutilizar el criterio de `_parece_ruta_de_archivo`, aplicado por token

**Decisión**: FR-001 exige detectar una ruta de archivo de log dentro del mismo mensaje que la
descripción inicial. `_parece_ruta_de_archivo` (`src/opssleuth/cli.py`, ya usada por el paso
dedicado de 002) evalúa si una **línea completa** tiene forma de ruta (sin espacios, con `/`,
`\` o extensión `.log`/`.txt`). Para el mensaje inicial, la ruta aparece habitualmente como un
fragmento dentro de una oración más larga (p. ej. "...aquí está el archivo de log
test_logs\facturacion.log"), no como la línea completa. Se introduce una nueva función,
`_extraer_ruta_candidata(texto: str) -> str | None`, que divide `texto` en tokens separados por
espacio y aplica el mismo criterio de `_parece_ruta_de_archivo` a cada token individualmente,
devolviendo el **último** token que lo cumpla (o `None` si ninguno lo cumple).

**Rationale**: Reutiliza exactamente el mismo criterio de reconocimiento ya validado por 002
(mismos caracteres/extensiones), en vez de introducir una heurística nueva — consistente con la
decisión de Clarifications de esta spec y con el Principio IV (simplicidad: un solo lugar define
"qué parece una ruta"). Se elige el **último** token candidato porque el patrón observado en uso
real coloca la ruta al final de la oración ("el problema es X, aquí está el log: ruta"); si
apareciera más de un candidato, tomar el último evita construir lógica de desambiguación
adicional no solicitada por la spec.

**Alternatives considered**:
- Una expresión regular dedicada para "parece ruta dentro de texto libre": rechazada — duplica
  lógica que ya existe en `_parece_ruta_de_archivo`, violando Principio IV.
- Pedir al LLM (`evaluar_descripcion`) que también extraiga una posible ruta de logs como parte
  de `EvaluacionDescripcion`: rechazada — mezclaría una responsabilidad puramente léxica/de E/S
  (reconocer una ruta de archivo) dentro del motor de evaluación semántica de la descripción,
  y el criterio de reconocimiento de rutas de 002 es determinista y ya suficiente (Regla de
  "cómputo determinista sobre auto-enumeración del LLM" ya establecida en `ESTADO_SPECS.md`).
- Tomar el primer candidato en vez del último: rechazada por no coincidir con el patrón de uso
  real observado; sin más señal en la spec para preferirlo.

## Decisión 2: Validación diferida de la ruta candidata — sin nuevo campo en `Caso`

**Decisión**: Por la Clarification de la Sesión 2026-09-14 (Pregunta 3), la validación de
accesibilidad de la ruta candidata se difiere hasta que la recepción de la incidencia esté
completa. En vez de añadir un campo nuevo a `Caso` para guardar una "fuente de logs pendiente de
validar" (lo que ampliaría la entidad de dominio y contradiría el principio de esta spec de no
tocar el modelo de datos), `_procesar_intake` devuelve la ruta candidata (`str | None`) como
valor de retorno, y `ejecutar_conversacion` la pasa como parámetro opcional a
`_solicitar_evidencia_logs(caso, ruta_candidata=...)`. Si se aportó una candidata,
`_solicitar_evidencia_logs` valida directamente esa ruta (reutilizando la misma rama de código
que hoy valida una ruta escrita interactivamente) en vez de formular la pregunta "¿puedes
aportar los logs...?" — si es inválida, cae en la misma rama de reintento que ya existe hoy.

**Rationale**: Evita una migración de datos en `Caso` y mantiene la responsabilidad de
"¿hay una fuente de logs pendiente de esta conversación?" completamente local al flujo
síncrono de `ejecutar_conversacion` (que ya llama a `_procesar_intake` y
`_solicitar_evidencia_logs` en secuencia inmediata) — no se necesita persistirlo en el dominio.
Reutiliza ~toda la lógica de validación/reintento ya implementada y probada por 002 en
`_solicitar_evidencia_logs`, en vez de duplicarla.

**Alternatives considered**:
- Añadir `Caso.fuente_logs_candidata: str | None`: rechazada — introduce estado de dominio
  transitorio que solo tiene sentido durante una única llamada síncrona; los "Key Entities" de
  `spec.md` ya afirman que esta spec no agrega campos nuevos a `Caso`.
- Validar y registrar la ruta de inmediato en `_procesar_intake` (sin diferir): rechazada por la
  Clarification de la Sesión 2026-09-14 (Pregunta 3) — intercalaría un posible mensaje de error
  de logs en medio del flujo de aclaración de la descripción.

## Decisión 3: Respuesta combinada a varias aclaraciones — reutilizar `evaluar_descripcion` sobre el lote inicial

**Decisión**: Cuando `preguntas_de_campos` (en `_procesar_intake`) tiene 2 o más preguntas
pendientes, una nueva función `_formular_y_registrar_aclaraciones_combinadas(caso, chat_model,
preguntas_de_campos) -> list[Aclaracion]` presenta las preguntas pendientes en un único mensaje
combinado, lee una única respuesta, y la evalúa con el mismo `evaluar_descripcion(chat_model,
respuesta, caso.mensajes)` ya usado para la descripción inicial — reutilizando su capacidad
existente de extraer los 3 campos (`sistema_afectado`/`sintoma`/`momento`) y de detectar
contradicción, en vez de introducir un motor de interpretación nuevo. Se aplican (vía la función
ya existente `_aplicar_campos_evaluados`) solo los campos que **siguen faltando** en
`caso.descripcion_inicial.campos_faltantes()` en ese momento, para no sobrescribir un campo ya
confirmado. Los campos que la evaluación combinada no logró cubrir se devuelven como lista de
`Aclaracion` pendientes, que `_procesar_intake` resuelve con el bucle uno-por-uno ya existente
(`_formular_y_registrar_aclaracion`) — sin cambios en ese bucle. Con menos de 2 preguntas
pendientes, se usa directamente el bucle uno-por-uno existente (no hay nada que combinar).

**Rationale**: `evaluar_descripcion` ya sabe extraer los 3 campos de un texto libre — es
exactamente la capacidad que necesita el "batching": no hay diferencia estructural entre
"evaluar la descripción inicial" y "evaluar una respuesta que cubre varios campos pendientes a
la vez", ambas son "texto libre que puede mencionar sistema/síntoma/momento". Reutilizar el
mismo motor evita introducir un mecanismo de interpretación paralelo (ver `ESTADO_SPECS.md`,
sección "Motor de modelo de lenguaje (LLM)": "Cualquier spec futura que necesite razonamiento
con LLM debe usar `crear_modelo_chat()`/las funciones ya expuestas, no un mecanismo paralelo").
El fallback al bucle uno-por-uno para lo que quede sin cubrir satisface FR-005 y FR-007
(no-regresión) sin duplicar su lógica de manejo de "no puedo aportar más" y de detección de
contradicción por campo.

**Alternatives considered**:
- Una cola de aclaraciones pendientes de estado persistente que acepte respuestas parciales en
  cualquier turno futuro: rechazada por la Clarification de la Sesión 2026-09-14 (Pregunta 2) —
  fuera de alcance de esta spec.
- Parsear la respuesta combinada con reglas deterministas (p. ej. por posición o separadores):
  rechazada — el usuario responde en lenguaje natural libre (p. ej. "es el módulo de facturación
  y fue ayer a las 3pm"), que no tiene una estructura posicional fiable; `evaluar_descripcion`
  ya resuelve exactamente este problema de extracción semántica.

## Decisión 4: Sin nuevos contratos (`contracts/`)

**Decisión**: Esta spec no añade un nuevo archivo bajo `contracts/`. Los contratos ya
documentados (`chat_model_provider.md`, `clarification_migration.md`, `log_search_engine.md`,
todos en `specs/002-busqueda-logs/contracts/`) siguen vigentes sin cambios — esta spec no
introduce un nuevo límite de módulo intercambiable (no hay un nuevo proveedor, ni una nueva
herramienta del agente, ni un nuevo motor). Los cambios son orquestación interna de
`src/opssleuth/cli.py` sobre las mismas funciones ya contratadas (`evaluar_descripcion`,
`generar_preguntas`, `buscar_evidencia`).

**Rationale**: Principio IV (simplicidad) — un contrato nuevo estaría justificado si esta spec
introdujera un límite de reemplazabilidad nuevo (Principio II); no es el caso.

**Alternatives considered**:
- Documentar un "contrato de orquestación de intake" nuevo: rechazada — `cli.py` es la capa de
  presentación/orquestación de la aplicación, no un módulo con implementaciones intercambiables
  por proveedor; no aplica el mecanismo de contratos usado para los límites de LangChain/agente.
