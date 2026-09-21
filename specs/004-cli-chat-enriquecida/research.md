# Research: CLI Chat Enriquecida

## Decisión 1: Confinamiento de `rich` a un módulo nuevo (`presentation/console.py`), sin invocar la excepción constitucional

**Decisión**: `rich` queda confinado a un único módulo nuevo, `src/opssleuth/presentation/console.py`
— ningún otro módulo del proyecto lo importa directamente. `cli.py` sigue exponiendo `_imprimir`/
`_leer_entrada` como su propia interfaz interna (sin cambios de firma salvo la extensión aditiva de
`_imprimir`, ver Decisión 6), delegando en el módulo nuevo. Se sigue el camino **por defecto** del
Principio II ("exponer las dependencias externas detrás de una capa de abstracción propia del
proyecto"), no la excepción de "estándar de abstracción de terceros maduro" (v1.1.0) que ya cubre a
`BaseChatModel`.

**Rationale**: La excepción constitucional existe para el caso concreto de adoptar el tipo
abstracto de un paquete de terceros como el propio mecanismo de intercambiabilidad del proyecto
(varias implementaciones concretas — `ChatAnthropic`/`ChatOllama`/`ChatGoogleGenerativeAI` —
detrás de un contrato común, `BaseChatModel`, consumido por varios módulos). Aquí no existe ese
escenario: no hay una segunda librería de renderizado de terminal entre la que elegir en tiempo de
ejecución, ni varios consumidores que dependan de un tipo abstracto compartido — solo una
dependencia de presentación con un único consumidor (`cli.py`). El camino por defecto del
Principio II (confinar el import a un módulo propio) ya resuelve el requisito sin necesidad de
apoyarse en la excepción, evitando forzar una justificación que no aplica.

**Alternatives considered**:
- Importar `rich` directamente en `cli.py`: rechazado — viola el confinamiento exigido por el
  Principio II (la dependencia de terceros quedaría acoplada directamente al módulo de
  orquestación, en vez de detrás de una capa propia).
- Definir un `Protocol` propio de "motor de renderizado" con `RichRenderer` como única
  implementación: rechazado por Principio IV (simplicidad) — sin una segunda implementación real
  que intercambiar, el `Protocol` no aportaría comportamiento, solo indirección. Mismo criterio ya
  aplicado por `llm/factory.py` (una función simple, no una jerarquía de clases) antes de que
  existiera la necesidad real de múltiples proveedores.

## Decisión 2: `_imprimir`/`_leer_entrada` como delegadores delgados — sin tocar los demás puntos de llamada

**Decisión**: `_imprimir(mensaje: str, *, es_error: bool = False) -> None` y
`_leer_entrada(prompt: str) -> str` (ambas ya existentes en `cli.py`, punto de paso del 100% de la
entrada/salida de la conversación) mantienen exactamente su contrato de llamada actual — la única
adición es el parámetro `es_error` de `_imprimir`, con valor por defecto `False`, por lo que todo
call site existente de un solo argumento posicional sigue siendo válido sin modificarse. Sus
cuerpos pasan a delegar en `presentation.console.mostrar_mensaje_sistema`/`leer_entrada_usuario`.

**Rationale**: Verificado contra la suite de pruebas actual (`tests/unit/test_cli.py`, 87 pruebas):
ninguna prueba monkeypatchea ni hace aserciones sobre `_imprimir` (nunca se reemplaza su
implementación ni se captura su salida vía `capsys`/`capfd`); las pruebas que monkeypatchean
`_leer_entrada` lo hacen reemplazando la función completa por un doble de prueba — mientras su
firma (`prompt: str -> str`) no cambie, siguen funcionando sin modificación. Preservar estos
contratos logra el cambio de presentación pedido por la spec (FR-001 a FR-006) tocando únicamente
2 funciones ya existentes más los 6 puntos de cableado puntuales de las Decisiones 5 y 6 — en vez
de refactorizar ~15+ puntos de llamada distribuidos por todo `cli.py` para invocar
`presentation/console.py` directamente, lo que multiplicaría el riesgo de regresión sin aportar
valor adicional (FR-007 exige explícitamente que el comportamiento conversacional no cambie).

**Alternatives considered**:
- Reemplazar cada punto de llamada de `cli.py` (`_solicitar_descripcion`,
  `_formular_y_registrar_aclaracion`, etc.) para invocar `presentation/console.py` directamente,
  eliminando `_imprimir`/`_leer_entrada`: rechazado — mayor superficie de cambio sin beneficio
  funcional, mayor riesgo de regresión sobre el comportamiento ya probado de 001/002/003
  (Principio IV).

## Decisión 3: Etiqueta textual de rol obligatoria + degradación automática sin color

**Decisión**: `mostrar_mensaje_sistema` y `leer_entrada_usuario` siempre imprimen una etiqueta
textual de rol ("Tú" para el usuario, "OpsSleuth" para el sistema) como parte del texto, reforzada
—no sustituida— por color/estilo cuando la terminal lo soporta. El objeto `rich.console.Console`
usado internamente se construye con autodetección por defecto (sin forzar `force_terminal=True`),
de modo que en un entorno sin soporte de color (`NO_COLOR`, salida no interactiva, terminal
limitada) `rich` degrada automáticamente el estilo a texto plano — la etiqueta textual, al no
depender de esa degradación, sigue apareciendo igual.

**Rationale**: Implementa directamente la Clarification de la Sesión 2026-09-16 (Pregunta 2):
FR-001/FR-002 exigen la etiqueta textual como mecanismo obligatorio, no solo color, precisamente
para que FR-006 (funciona sin soporte de color) no deje al usuario sin la diferenciación que pide
la Historia 1. La autodetección de `rich.console.Console` es comportamiento ya incorporado en la
librería — no requiere código adicional del proyecto para lograr FR-006/SC-003.

**Alternatives considered**:
- Depender solo de color/estilo para la diferenciación, sin etiqueta textual: rechazado
  explícitamente en `/speckit-clarify` (Sesión 2026-09-16) por dejar sin efecto la diferenciación
  en entornos sin color o para usuarios con daltonismo.
- Forzar `force_terminal=True` en el `Console` para garantizar salida con estilo siempre: rechazado
  — produciría códigos ANSI ilegibles cuando la salida se redirige a un archivo o pipe, violando
  FR-006/SC-003 (el edge case de terminal sin soporte de color es explícito en `spec.md`).

## Decisión 4: Renderizado Markdown de todo mensaje del sistema vía `rich.markdown.Markdown`

**Decisión**: `mostrar_mensaje_sistema` renderiza `texto` con `rich.markdown.Markdown` antes de
imprimirlo (dentro del bloque con la etiqueta de rol) — se aplica uniformemente a cualquier mensaje
del sistema, sin distinguir de antemano si contiene o no marcado (listas, énfasis, encabezados);
para texto plano sin marcado, `Markdown` lo renderiza igual como un párrafo simple, sin efecto
visible.

**Rationale**: Satisface la Historia 2 (FR-003, SC-002) sin necesitar detectar caso por caso si un
mensaje "tiene" o "no tiene" estructura — un único punto de renderizado cubre ambos casos
(Acceptance Scenario 3 de la Historia 2: una respuesta de una sola línea sigue mostrándose clara).
Es además el escenario real ya observado en uso: las apreciaciones de logs producidas por el
motor de búsqueda (spec 002) ya contienen marcado Markdown genuino (encabezados `###`, listas,
énfasis `**...**`) generado por el LLM subyacente — confirmado en pruebas manuales durante la
implementación de la spec 003 (ver transcripciones de esa sesión).

**Alternatives considered**:
- Escribir un parser propio de listas/énfasis ad hoc: rechazado por Principio IV — reinventa una
  librería madura (`rich.markdown.Markdown`) que ya resuelve el problema, y que el propio usuario
  pidió usar.
- Detectar heurísticamente si un mensaje "parece" tener marcado antes de decidir renderizarlo como
  Markdown: rechazado — complejidad innecesaria; `Markdown` ya degrada de forma segura a texto
  plano legible cuando no hay marcado que interpretar.

## Decisión 5: Indicador de actividad en las 4 llamadas reales de latencia perceptible, no solo el ejemplo literal del spec

**Decisión**: `mostrar_actividad(mensaje)` (context manager basado en `rich.console.Console.status`)
envuelve las 4 llamadas de `cli.py` que invocan al proveedor de modelo subyacente:
`evaluar_descripcion` en `_procesar_intake`, en `_formular_y_registrar_aclaracion` y en
`_formular_y_registrar_aclaraciones_combinadas`; y `buscar_evidencia` en
`_buscar_y_presentar_apreciacion_logs`.

**Rationale**: La Historia 3 y FR-004 usan "p. ej." (ejemplo no exhaustivo) al citar la búsqueda de
logs como caso de "operación que toma un momento perceptible" — no la acotan a ese único caso. Las
3 llamadas a `evaluar_descripcion` son igual de perceptibles: se observaron latencias de varios
segundos en pruebas manuales reales contra el proveedor `gemini` durante la implementación de las
specs 002/003 (p. ej. ~5s para una evaluación estructurada simple). Omitir el indicador en esas 3
llamadas dejaría exactamente la misma "pantalla sin actividad aparente" que la Historia 3 identifica
como el problema a resolver, solo que en un punto distinto del flujo — no habría cumplido el
objetivo real de la historia, solo su redacción más literal.

**Alternatives considered**:
- Envolver únicamente la llamada a `buscar_evidencia` (la mencionada explícitamente en el texto de
  la spec): rechazado por sub-entregar el valor de UX real que motiva la Historia 3 — ver
  Rationale.
- Mover el indicador de actividad dentro de `clarification/engine.py`/`evidence/engine.py` (junto a
  la llamada real al modelo): rechazado — acoplaría esos módulos de negocio a `rich`/presentación,
  violando la separación ya establecida (Principio II) entre motor de razonamiento y capa de
  presentación; el indicador se activa/desactiva alrededor de la llamada desde `cli.py`, que ya es
  el orquestador de ambos.

## Decisión 6: `es_error` como flag explícito, no heurística sobre el texto del mensaje

**Decisión**: `_imprimir` gana un parámetro `es_error: bool = False`, cableado explícitamente a
`True` en los 2 mensajes de fallo de comunicación con el proveedor ya existentes: "No pude evaluar
la descripción..." (`_procesar_intake`) y "No pude completar la búsqueda en los logs..."
(`_buscar_y_presentar_apreciacion_logs`). El resto de los mensajes (incluida la nota de
contradicción, que es informativa, no un fallo) usan el valor por defecto `False`.

**Rationale**: Un flag explícito en el punto de llamada es más simple y robusto que intentar
inferir "es un error" a partir del contenido del texto (frágil ante cambios de redacción futuros).
El alcance se mantiene acotado a los 2 casos que la Historia 3 realmente ejercita en sus escenarios
de aceptación (fallo de comunicación con el proveedor) — no se extiende a la nota de contradicción
ni a otros mensajes informativos, que no son condiciones de fallo (Principio IV: no construir más
de lo que la spec pide).

**Alternatives considered**:
- Heurística de texto (p. ej. buscar "No pude" en el mensaje): rechazada — acopla la lógica de
  presentación a la redacción exacta de los mensajes de negocio, rompible por cualquier cambio de
  copy futuro sin relación con esta spec.
- Extender `es_error` (o una variante "advertencia") también a la nota de contradicción: rechazado
  por alcance — la Historia 3 y sus escenarios de aceptación solo cubren el caso de fallo de
  comunicación con el proveedor; ampliarlo especulativamente no está pedido ni probado por esta
  spec.

## Decisión 7: `Console` inyectable por parámetro, sin singleton oculto

**Decisión**: Cada función de `presentation/console.py` acepta un parámetro `console:
rich.console.Console | None = None`, usando una instancia de módulo por defecto cuando no se
provee. Las pruebas de `tests/unit/test_console.py` inyectan un `Console(file=io.StringIO(),
force_terminal=False)` para verificar en texto plano las etiquetas de rol y el renderizado
Markdown, sin depender de capturar stdout ni de parsear secuencias ANSI.

**Rationale**: Mismo patrón de inyección de dependencias ya usado en todo el proyecto para
`chat_model` (`BaseChatModel` como parámetro, nunca una instancia global oculta) — consistencia
arquitectónica (Principio I, Inversión de Dependencias) y testabilidad directa sin necesidad de
monkeypatchear internals de `rich`.

**Alternatives considered**:
- Un único `Console` global sin posibilidad de inyección: rechazado — dificultaría probar el
  contenido renderizado sin recurrir a `capsys`/parseo de ANSI, y rompería la consistencia con el
  patrón de inyección ya establecido en el resto del proyecto.

## Nuevas dependencias

- `rich` (paquete de terceros nuevo, confinado a `src/opssleuth/presentation/console.py` — ver
  Decisión 1). Se añade en la fase de implementación vía `uv add rich`.
