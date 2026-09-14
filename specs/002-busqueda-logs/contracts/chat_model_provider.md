# Contrato: Proveedor de Modelo de Chat (`crear_modelo_chat`)

Este es el mecanismo de modularidad central (Principio II de la constitución, bajo la excepción
de "estándar de abstracción de terceros maduro" añadida en la enmienda v1.1.0 — ver
`.specify/memory/constitution.md`) del que dependen **ambos** flujos de razonamiento con LLM del
proyecto: el flujo de aclaración de incidencias (001, migrado por esta spec — ver
`contracts/clarification_migration.md`) y el flujo de búsqueda de evidencia en logs (002, ver
`contracts/log_search_engine.md`). Sustituye a los dos `factory.py` que existían/estaban
planificados por separado (`clarification/factory.py` de 001 y el `evidence/factory.py`
originalmente planificado para 002).

## Interfaz

```python
def crear_modelo_chat() -> BaseChatModel:
    """Lee OPSSLEUTH_LLM_PROVIDER (claude|ollama|gemini, por defecto claude) y
    devuelve una instancia configurada de BaseChatModel
    (langchain_core.language_models): ChatAnthropic si el proveedor es
    'claude', ChatOllama si es 'ollama', ChatGoogleGenerativeAI si es
    'gemini'."""
    ...
```

`BaseChatModel` (de `langchain_core.language_models`) es el tipo abstracto que consume todo el
resto del sistema — ningún módulo de negocio (dominio, orquestación de casos, CLI, el flujo de
aclaración ni el de búsqueda de logs) importa `langchain_anthropic`/`langchain_ollama`/
`langchain_google_genai` ni los SDKs `anthropic`/`ollama`/`google-genai` directamente. Esa
importación queda confinada a esta única función de fábrica, tal como exige la excepción
constitucional.

**Adición del proveedor `gemini` (2026-09-14)**: se agregó como tercer proveedor, motivado por
evaluar la capa gratuita de la API de Gemini como alternativa a Ollama en máquinas con
limitaciones de VRAM/RAM (ver incidente documentado en la conversación de esa fecha: un modelo
local de 0.8B fallaba con errores de tool-calling malformado, y el modelo local recomendado de
7B agotaba la memoria disponible). Se acoge a la **misma excepción constitucional** ya invocada
para `ChatAnthropic`/`ChatOllama` (Principio II, "estándar de abstracción de terceros maduro",
v1.1.0): `ChatGoogleGenerativeAI` (paquete `langchain-google-genai`) es igualmente una
implementación madura y ampliamente adoptada de `BaseChatModel`, por lo que no se justifica una
interfaz propia adicional solo para este tercer proveedor — hacerlo violaría el Principio IV
(Simplicidad ante Todo) de la misma forma que ya se argumentó para los dos proveedores
originales. No se requiere una nueva enmienda a la constitución: la excepción de la v1.1.0 no
enumera proveedores específicos, cubre genéricamente cualquier estándar de abstracción de
terceros que satisfaga sus condiciones (confinamiento a un único punto de integración,
dependencia del tipo abstracto en el resto del sistema).

## Reglas del contrato

1. `crear_modelo_chat()` es la ÚNICA función del proyecto que instancia `ChatAnthropic`,
   `ChatOllama` o `ChatGoogleGenerativeAI` — cualquier otro módulo que necesite un modelo de chat
   DEBE recibirlo como parámetro (inyección de dependencias), nunca construirlo por su cuenta.
2. La variable de entorno `OPSSLEUTH_LLM_PROVIDER` (`claude` por defecto, `ollama` o `gemini`)
   DEBE seguir siendo el único mecanismo de selección de proveedor — no se introduce una variable
   nueva ni un mecanismo paralelo (ver `ESTADO_SPECS.md`).
3. Con el proveedor `ollama`, `OPSSLEUTH_OLLAMA_MODEL` DEBE estar configurada; si no lo está, la
   función DEBE lanzar un error explícito antes de intentar construir el modelo (mismo
   comportamiento que `ModeloOllamaNoConfiguradoError` en la implementación original de 001,
   preservado en la migración).
4. Un valor de `OPSSLEUTH_LLM_PROVIDER` no reconocido DEBE lanzar un error explícito
   (`ProveedorDesconocidoError`, preservado de la implementación original de 001), en vez de
   caer silenciosamente a un proveedor por defecto.
5. Errores de comunicación con el proveedor subyacente (sea en el flujo de aclaración o en el de
   búsqueda de logs) DEBEN propagarse envueltos en el tipo de error de dominio correspondiente a
   cada flujo (`ClarificationEngineError`, `LogSearchEngineError`) en el punto donde se invoca al
   modelo — no en `crear_modelo_chat()` en sí, que solo construye la instancia y no realiza
   ninguna llamada de red.
6. Con el proveedor `gemini`, el modelo usado (`MODELO_GEMINI_POR_DEFECTO`) es fijo, igual que
   para `claude` — no se introduce una variable de entorno de selección de modelo Gemini, porque
   (a diferencia de Ollama) no es un modelo local descargable sino un servicio alojado con un
   único modelo recomendado para la capa gratuita. Si `GOOGLE_API_KEY`/`GEMINI_API_KEY` no está
   configurada, `langchain-google-genai` lanza un `pydantic.ValidationError` al construir la
   instancia (no se envuelve en un error propio, por la misma razón de simplicidad que ya aplica
   al proveedor `claude`: el fallo por credencial faltante no está cubierto por la Regla 3, que
   es específica de la validación adicional que sí existe para `ollama`).

## Implementación

- Proveedor `claude` (por defecto): `ChatAnthropic(model="claude-sonnet-5", ...)` — mismo modelo
  por defecto que la implementación original de 001 (ver `ESTADO_SPECS.md`, decisión compartida).
  Requiere `ANTHROPIC_API_KEY` (o un perfil activo vía `ant auth login`) y acceso de red saliente
  — sin cambios respecto al requisito ya documentado en 001.
- Proveedor `ollama`: `ChatOllama(model=<OPSSLEUTH_OLLAMA_MODEL>, ...)`. Requiere una instancia
  de Ollama accesible localmente con el modelo ya descargado y con soporte de tool calling (este
  último requisito es nuevo respecto a 001, porque el flujo de búsqueda de logs — a diferencia
  del de aclaración — necesita que el modelo local soporte `bind_tools`; ver
  `contracts/log_search_engine.md`).
- Proveedor `gemini` (nuevo): `ChatGoogleGenerativeAI(model="gemini-3.6-flash", ...)`. Requiere
  `GOOGLE_API_KEY` (o `GEMINI_API_KEY` como fallback, ambas leídas directamente por
  `langchain-google-genai`) y acceso de red saliente. `gemini-3.6-flash` soporta tool calling y
  salida estructurada, requisito de ambos flujos — verificado end-to-end contra la API real el
  2026-09-14 (`evaluar_descripcion` produjo una `EvaluacionDescripcion` estructurada correcta).
  **Nota histórica**: la elección original fue `gemini-2.5-flash`, retirado por Google para API
  keys nuevas (`404 NOT_FOUND ... no longer available to new users`) el mismo día en que se
  introdujo este proveedor, antes de que se hiciera la primera prueba con una API key real —
  corregido a `gemini-3.6-flash` (el modelo que el propio error de la API recomendó) tras
  reproducir el fallo. Dado que Google puede seguir retirando modelos de la capa gratuita sin
  aviso previo largo, si `crear_modelo_chat()` empieza a fallar con `gemini` y un
  `GoogleModelNotFoundError`/`404`, revisar primero si `MODELO_GEMINI_POR_DEFECTO` sigue vigente
  en la documentación oficial de modelos de Google AI Studio antes de asumir un bug de
  integración — el mensaje de error de la propia API suele nombrar el modelo de reemplazo
  recomendado.

**Nota de verificación de implementación**: los nombres exactos de los parámetros de construcción
de `ChatAnthropic`/`ChatOllama`/`ChatGoogleGenerativeAI` (equivalentes a `effort`, `thinking`,
etc. de la API nativa de Claude) deben confirmarse contra la documentación de
`langchain-anthropic`/`langchain-ollama`/`langchain-google-genai` instalada al momento de
implementar — no se asumen aquí (ver `research.md`, Decisión 1, nota de riesgo).
