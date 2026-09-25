"""Bucle conversacional de la CLI de OpsSleuth.

Orquesta la recepción de incidencias (spec 001: descripción inicial, contexto
de la conversación, aclaración ante ambigüedad), la búsqueda de evidencia en
logs (spec 002) y la consulta de evidencia en base de datos (spec 005).
Depende únicamente de `opssleuth.domain.case`, del módulo de aclaración
(`opssleuth.clarification.engine`) y de un `BaseChatModel` ya construido
(inyectado vía `opssleuth.llm.factory.crear_modelo_chat`) — nunca de un SDK de
proveedor de modelo concreto directamente (Principio II de la constitución).
La presentación (etiquetas de rol, color, renderizado Markdown, indicador de
actividad — spec 004) se delega en `opssleuth.presentation.console`, el único
módulo que importa `rich`; `cli.py` no importa `rich`/`sqlalchemy`/`sqlglot`
directamente.
"""

from __future__ import annotations

import os
import tempfile

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from opssleuth.clarification.engine import (
    ClarificationEngineError,
    EvaluacionDescripcion,
    evaluar_descripcion,
    generar_preguntas,
)
from opssleuth.database.engine import DatabaseSearchEngineError, consultar_evidencia_bd
from opssleuth.database.factory import (
    ConexionBaseDeDatosError,
    FuenteDeBaseDeDatosConfigurada,
    crear_motor_bd,
)
from opssleuth.domain.case import Aclaracion, CampoExtraido, Caso, DescripcionVaciaError
from opssleuth.domain.log_evidence import FuenteDeLogs
from opssleuth.evidence.engine import LogSearchEngineError, buscar_evidencia
from opssleuth.llm.factory import crear_modelo_chat
from opssleuth.presentation.console import (
    leer_entrada_usuario,
    mostrar_actividad,
    mostrar_banner,
    mostrar_mensaje_sistema,
)

FRASES_SALIDA = ("salir", "exit", "quit")
FRASES_NUEVO_CASO = ("nuevo caso", "otro problema", "reportar otro", "quiero reportar")
FRASES_RESUMEN = ("resumen", "resume el problema", "recuerda", "recuérdame", "recapitula")
FRASES_NO_PUEDO_APORTAR_MAS = (
    "no tengo más información",
    "no puedo aportar más información",
    "no sé más",
    "no tengo más detalles",
    "eso es todo lo que sé",
    "no tengo esa información",
)
FRASES_CONFIRMACION = ("si", "sí", "yes", "y", "s", "confirmo", "correcto")

CAMPOS_DE_DESCRIPCION = ("sistema_afectado", "sintoma", "momento")

UMBRAL_LINEAS_PEGADAS = 4
"""Umbral de líneas pegadas a partir del cual se genera un archivo temporal (FR-003/FR-004)."""


def _leer_entrada(prompt: str) -> str:
    """Lee una línea de entrada del usuario desde stdin.

    Delega en `opssleuth.presentation.console.leer_entrada_usuario` (spec
    004): muestra `prompt` (si lo hay) como mensaje del sistema con su
    etiqueta de rol, luego la etiqueta de rol del usuario, y lee la línea.

    Parameters
    ----------
    prompt : str
        Mensaje mostrado antes de esperar la entrada.

    Returns
    -------
    str
        Texto escrito por el usuario.
    """
    return leer_entrada_usuario(prompt)


def _imprimir(mensaje: str, *, es_error: bool = False) -> None:
    """Muestra un mensaje del sistema al usuario.

    Delega en `opssleuth.presentation.console.mostrar_mensaje_sistema` (spec
    004): añade la etiqueta de rol del sistema y renderiza `mensaje` como
    Markdown.

    Parameters
    ----------
    mensaje : str
        Texto a mostrar.
    es_error : bool, optional
        Si `True`, distingue visualmente `mensaje` como un fallo o
        advertencia (p. ej. un error de comunicación con el proveedor de
        modelo) en vez de una respuesta normal (FR-005 de spec 004). `False`
        por defecto.
    """
    mostrar_mensaje_sistema(mensaje, es_error=es_error)


def _es_intencion_nuevo_caso(texto: str) -> bool:
    """Determina si el texto indica la intención de reportar un problema nuevo.

    Parameters
    ----------
    texto : str
        Mensaje del usuario.

    Returns
    -------
    bool
        True si el texto contiene alguna de las frases reconocidas de inicio de
        caso nuevo (FR-013).
    """
    normalizado = texto.strip().lower()
    return any(frase in normalizado for frase in FRASES_NUEVO_CASO)


def _es_solicitud_de_resumen(texto: str) -> bool:
    """Determina si el texto solicita un resumen del caso (FR-005).

    Parameters
    ----------
    texto : str
        Mensaje del usuario.

    Returns
    -------
    bool
        True si el texto contiene alguna de las frases reconocidas de solicitud
        de resumen.
    """
    normalizado = texto.strip().lower()
    return any(frase in normalizado for frase in FRASES_RESUMEN)


def _indica_que_no_puede_aportar_mas(texto: str) -> bool:
    """Determina si el usuario indica que no puede aportar más información (FR-010).

    Parameters
    ----------
    texto : str
        Respuesta del usuario a una pregunta de aclaración.

    Returns
    -------
    bool
        True si el texto contiene alguna de las frases reconocidas.
    """
    normalizado = texto.strip().lower()
    return any(frase in normalizado for frase in FRASES_NO_PUEDO_APORTAR_MAS)


def _es_confirmacion(texto: str) -> bool:
    """Determina si el texto es una confirmación afirmativa.

    Parameters
    ----------
    texto : str
        Respuesta del usuario a una pregunta de confirmación sí/no.

    Returns
    -------
    bool
        True si el texto normalizado coincide con una respuesta afirmativa.
    """
    return texto.strip().lower() in FRASES_CONFIRMACION


def _solicitar_descripcion(caso: Caso) -> None:
    """Solicita y registra la descripción inicial del problema.

    Si el caso ya tiene una descripción registrada, no vuelve a solicitarla —
    reconoce el caso existente (Acceptance Scenario 3 de US1). Rechaza
    descripciones vacías o sin contenido interpretable y vuelve a solicitarlas
    (FR-011).

    Parameters
    ----------
    caso : Caso
        Caso al que se le registrará la descripción inicial.
    """
    if caso.descripcion_inicial is not None:
        _imprimir("Ya tengo registrada la descripción de este caso.")
        return

    _imprimir(
        "Antes de continuar, cuéntame: ¿qué problema o error encontraste, "
        "o qué te reportaron?"
    )
    while caso.descripcion_inicial is None:
        texto = _leer_entrada("> ")
        try:
            caso.registrar_descripcion(texto)
        except DescripcionVaciaError:
            _imprimir(
                "No pude interpretar contenido válido en tu mensaje anterior. "
                "Por favor, describe el problema nuevamente."
            )
            continue
        caso.agregar_mensaje("user", texto)
        _imprimir("Gracias, recibí tu descripción del problema.")


def _aplicar_campos_evaluados(
    caso: Caso,
    evaluacion: EvaluacionDescripcion,
    campos: tuple[str, ...] = CAMPOS_DE_DESCRIPCION,
) -> None:
    """Copia los campos evaluados por el motor a la descripción del caso (FR-006).

    Parameters
    ----------
    caso : Caso
        Caso cuya `descripcion_inicial` se actualizará.
    evaluacion : EvaluacionDescripcion
        Evaluación estructurada producida por `ClarificationEngine.evaluar`.
    campos : tuple of str, optional
        Subconjunto de `CAMPOS_DE_DESCRIPCION` a copiar; por defecto los 3. Se
        restringe a los campos aún pendientes al procesar una respuesta
        combinada a varias aclaraciones (Historia 2, spec 003), para no
        sobrescribir un campo ya confirmado que esta evaluación no mencione.
    """
    descripcion = caso.descripcion_inicial
    if "sistema_afectado" in campos:
        descripcion.sistema_afectado = CampoExtraido(
            presente=evaluacion.sistema_afectado.presente, valor=evaluacion.sistema_afectado.valor
        )
    if "sintoma" in campos:
        descripcion.sintoma = CampoExtraido(
            presente=evaluacion.sintoma.presente, valor=evaluacion.sintoma.valor
        )
    if "momento" in campos:
        descripcion.momento = CampoExtraido(
            presente=evaluacion.momento.presente, valor=evaluacion.momento.valor
        )


def _confirmar_problema_principal(caso: Caso, evaluacion: EvaluacionDescripcion) -> None:
    """Pide confirmación del problema principal cuando se detectan varios (edge case).

    Ver spec.md, Edge Case "descripción extremadamente extensa con múltiples
    problemas mezclados".

    Parameters
    ----------
    caso : Caso
        Caso en curso.
    evaluacion : EvaluacionDescripcion
        Evaluación de la descripción inicial, con `multiples_problemas` poblado.
    """
    if not evaluacion.multiples_problemas.detectado:
        return

    problemas = evaluacion.multiples_problemas.problemas_identificados
    listado = "; ".join(f"{i + 1}) {p}" for i, p in enumerate(problemas))
    pregunta = (
        f"Parece que describes más de un problema ({listado}). "
        "¿Cuál de ellos quieres que investiguemos primero?"
    )
    caso.agregar_mensaje("assistant", pregunta)
    respuesta = _leer_entrada(f"{pregunta} ")
    caso.agregar_mensaje("user", respuesta)
    caso.agregar_aclaracion(
        Aclaracion(pregunta=pregunta, campo_objetivo="problema_principal", respuesta=respuesta)
    )


def _formular_y_registrar_aclaracion(
    caso: Caso, chat_model: BaseChatModel, aclaracion: Aclaracion
) -> None:
    """Formula una pregunta de aclaración estándar y registra la respuesta.

    Incorpora la respuesta al contexto del caso (FR-008), detecta si el usuario
    indica que no puede aportar más información (FR-010), y detecta
    contradicciones con el contexto ya registrado sin descartar ningún dato
    (edge case de contradicción). Muestra un indicador de actividad mientras
    se evalúa la respuesta (FR-004 de spec 004).

    Parameters
    ----------
    caso : Caso
        Caso en curso.
    chat_model : BaseChatModel
        Modelo de chat usado para evaluar la respuesta en busca de contradicciones.
    aclaracion : Aclaracion
        Aclaración a formular (con `respuesta=None`).
    """
    caso.agregar_mensaje("assistant", aclaracion.pregunta)
    respuesta = _leer_entrada(f"{aclaracion.pregunta} ")

    if _indica_que_no_puede_aportar_mas(respuesta):
        caso.agregar_mensaje("user", respuesta)
        aclaracion.sin_confirmar = True
        caso.agregar_aclaracion(aclaracion)
        _imprimir(
            "Entendido, seguimos con la información disponible. Queda constancia "
            "de que este dato no se pudo confirmar."
        )
        return

    caso.agregar_mensaje("user", respuesta)
    aclaracion.respuesta = respuesta

    try:
        with mostrar_actividad("Pensando..."):
            evaluacion_respuesta = evaluar_descripcion(chat_model, respuesta, caso.mensajes)
    except ClarificationEngineError:
        evaluacion_respuesta = None

    if evaluacion_respuesta is not None and evaluacion_respuesta.contradiccion.detectada:
        aclaracion.contradice_descripcion_original = True
        _imprimir(
            "Noté una posible inconsistencia con lo que mencionaste antes: "
            f"{evaluacion_respuesta.contradiccion.descripcion} "
            "Voy a conservar ambos datos en el contexto del caso."
        )

    caso.agregar_aclaracion(aclaracion)

    if aclaracion.campo_objetivo in CAMPOS_DE_DESCRIPCION:
        setattr(
            caso.descripcion_inicial,
            aclaracion.campo_objetivo,
            CampoExtraido(presente=True, valor=respuesta),
        )


def _formular_y_registrar_aclaraciones_combinadas(
    caso: Caso, chat_model: BaseChatModel, preguntas_de_campos: list[Aclaracion]
) -> list[Aclaracion]:
    """Presenta el lote inicial de aclaraciones pendientes en un único turno (US2, spec 003).

    Combina las preguntas de `preguntas_de_campos` (2 o más) en un solo
    mensaje, lee una única respuesta, y la reevalúa con el mismo motor usado
    para la descripción inicial (`evaluar_descripcion`) para extraer los
    campos que cubra — aplicando (`_aplicar_campos_evaluados`) solo los campos
    que en ese momento sigan en `campos_faltantes()`, para no sobrescribir un
    campo ya confirmado que esta respuesta no mencione (`research.md`,
    Decisión 3 de spec 003). Si el usuario indica que no puede aportar más
    información (FR-010 de 001), marca todas las preguntas del lote como sin
    confirmar, igual que hace `_formular_y_registrar_aclaracion` para una sola
    pregunta. Las preguntas cuyo campo siga sin cubrir se devuelven para que
    el llamador las formule una por una (bucle existente, sin cambios).
    Muestra un indicador de actividad mientras se evalúa la respuesta
    combinada (FR-004 de spec 004).

    Parameters
    ----------
    caso : Caso
        Caso en curso.
    chat_model : BaseChatModel
        Modelo de chat usado para evaluar la respuesta combinada.
    preguntas_de_campos : list of Aclaracion
        Lote inicial de aclaraciones pendientes (2 o más), con `respuesta=None`.

    Returns
    -------
    list of Aclaracion
        Subconjunto de `preguntas_de_campos` cuyo campo sigue sin información,
        para continuar por el bucle de aclaración uno-por-uno existente.
    """
    listado = " ".join(f"{i + 1}) {a.pregunta}" for i, a in enumerate(preguntas_de_campos))
    pregunta_combinada = (
        f"Para continuar, cuéntame: {listado} (puedes responder todo junto en un solo mensaje)"
    )
    caso.agregar_mensaje("assistant", pregunta_combinada)
    respuesta = _leer_entrada(f"{pregunta_combinada} ")

    if _indica_que_no_puede_aportar_mas(respuesta):
        caso.agregar_mensaje("user", respuesta)
        for aclaracion in preguntas_de_campos:
            aclaracion.sin_confirmar = True
            caso.agregar_aclaracion(aclaracion)
        _imprimir(
            "Entendido, seguimos con la información disponible. Queda constancia "
            "de que estos datos no se pudieron confirmar."
        )
        return []

    caso.agregar_mensaje("user", respuesta)

    try:
        with mostrar_actividad("Pensando..."):
            evaluacion_respuesta = evaluar_descripcion(chat_model, respuesta, caso.mensajes)
    except ClarificationEngineError:
        evaluacion_respuesta = None

    if evaluacion_respuesta is not None:
        campos_pendientes_antes = caso.descripcion_inicial.campos_faltantes()
        _aplicar_campos_evaluados(caso, evaluacion_respuesta, campos=campos_pendientes_antes)
        if evaluacion_respuesta.contradiccion.detectada:
            _imprimir(
                "Noté una posible inconsistencia con lo que mencionaste antes: "
                f"{evaluacion_respuesta.contradiccion.descripcion} "
                "Voy a conservar ambos datos en el contexto del caso."
            )

    pendientes: list[Aclaracion] = []
    for aclaracion in preguntas_de_campos:
        if aclaracion.campo_objetivo in caso.descripcion_inicial.campos_faltantes():
            pendientes.append(aclaracion)
            continue
        aclaracion.respuesta = respuesta
        if evaluacion_respuesta is not None and evaluacion_respuesta.contradiccion.detectada:
            aclaracion.contradice_descripcion_original = True
        caso.agregar_aclaracion(aclaracion)

    return pendientes


def _parece_ruta_de_archivo(texto: str) -> bool:
    """Heurística: ¿`texto` tiene forma de intento de ruta de archivo?

    Distingue un intento de ruta que resultó inaccesible (para el mensaje de
    FR-002) de la primera línea de contenido pegado: las rutas típicamente
    contienen un separador de directorio o una extensión reconocible y no
    contienen espacios ni saltos de línea; las líneas de log típicamente sí
    contienen espacios (timestamp, nivel, mensaje).

    Parameters
    ----------
    texto : str
        Línea de entrada del usuario.

    Returns
    -------
    bool
        True si `texto` parece un intento de ruta de archivo.
    """
    if "\n" in texto or " " in texto or len(texto) > 260:
        return False
    return "/" in texto or "\\" in texto or texto.lower().endswith((".log", ".txt"))


def _extraer_ruta_candidata(texto: str) -> str | None:
    """Busca un token con forma de ruta de archivo de log dentro de `texto` libre.

    Reutiliza el criterio de reconocimiento de `_parece_ruta_de_archivo` (Historia
    1, spec 003), aplicándolo a cada token de `texto` separado por espacios en vez
    de a la línea completa — permite detectar una ruta mencionada dentro de una
    oración más larga (p. ej. la descripción inicial del problema). Si varios
    tokens cumplen el criterio, se devuelve el último, porque el patrón de uso
    observado coloca la ruta al final de la oración (ver `research.md`, Decisión 1).

    Parameters
    ----------
    texto : str
        Texto libre en el que buscar una posible ruta de archivo.

    Returns
    -------
    str or None
        El último token de `texto` que parece una ruta de archivo, o `None` si
        ninguno lo parece.
    """
    candidatas = [token for token in texto.split() if _parece_ruta_de_archivo(token)]
    return candidatas[-1] if candidatas else None


def _acumular_lineas_pegadas(primera_linea: str) -> list[str]:
    """Acumula líneas de contenido pegado, empezando por `primera_linea`.

    Sigue leyendo líneas sucesivas hasta una línea en blanco (o EOF), que
    señala el fin del contenido — cubre el caso en que el usuario pega el
    contenido fragmentado en varios mensajes sucesivos (Edge Case, spec.md).

    Parameters
    ----------
    primera_linea : str
        Primera línea ya leída, que inicia la acumulación.

    Returns
    -------
    list of str
        Todas las líneas acumuladas, en orden.
    """
    lineas = list(primera_linea.splitlines()) or [primera_linea]
    while True:
        try:
            siguiente = _leer_entrada("")
        except EOFError:
            break
        if siguiente == "":
            break
        lineas.extend(siguiente.splitlines() or [siguiente])
    return lineas


def _registrar_contenido_pegado(caso: Caso, lineas: list[str]) -> None:
    """Registra contenido de logs pegado según el umbral `UMBRAL_LINEAS_PEGADAS`.

    Por encima del umbral, genera un archivo temporal, informa su ubicación
    (FR-015) y lo registra como `FuenteDeLogs` (FR-003). En o por debajo del
    umbral, usa el contenido directamente como contexto conversacional del
    caso, sin generar archivo ni `FuenteDeLogs` (FR-004).

    Parameters
    ----------
    caso : Caso
        Caso al que se le registrará la fuente o el contexto.
    lineas : list of str
        Líneas de contenido pegado ya acumuladas.
    """
    if len(lineas) > UMBRAL_LINEAS_PEGADAS:
        descriptor, ruta = tempfile.mkstemp(prefix="opssleuth_logs_", suffix=".log")
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write("\n".join(lineas))
        _imprimir(
            f"El contenido que pegaste ({len(lineas)} líneas) lo guardé en un "
            f"archivo para poder consultarlo sin saturar el contexto: {ruta}"
        )
        caso.fuentes_logs.append(FuenteDeLogs(ruta=ruta, origen="contenido_pegado"))
        return

    contenido = "\n".join(lineas)
    caso.agregar_mensaje("user", f"Contenido de logs aportado:\n{contenido}")
    _imprimir("Anotado el contenido de logs que compartiste.")


def _solicitar_evidencia_logs(caso: Caso, ruta_candidata: str | None = None) -> None:
    """Invita proactivamente a aportar evidencia de logs y registra la fuente (US1).

    Se invoca en cuanto la recepción de la incidencia queda con información
    completa (FR-014). Acepta una ruta de archivo o contenido pegado
    directamente (FR-001); si la ruta indicada no es accesible, informa y
    permite reintentar con otra ruta o pegar los logs directamente (FR-002).

    Parameters
    ----------
    caso : Caso
        Caso con la recepción de incidencia ya completa.
    ruta_candidata : str or None, optional
        Ruta de logs ya detectada en el mismo mensaje que la descripción
        inicial (Historia 1, spec 003 — ver `_procesar_intake`). Si se aporta,
        se valida directamente (reutilizando la misma rama de
        validación/reintento de más abajo) en vez de formular la invitación
        interactiva — la validación de su accesibilidad queda así diferida
        hasta este punto de la conversación, no antes (`research.md`, Decisión
        2 de spec 003).
    """
    if caso.fuentes_logs:
        return

    if ruta_candidata is not None:
        entrada = ruta_candidata
    else:
        entrada = _leer_entrada(
            "Ahora que tengo clara la descripción, ¿puedes aportar los logs "
            "relacionados? Indica la ruta a un archivo, o pega el contenido "
            "directamente (si son varias líneas, termina con una línea en blanco): "
        )

    while True:
        candidata = entrada.strip()
        if candidata and os.path.isfile(candidata):
            caso.fuentes_logs.append(FuenteDeLogs(ruta=candidata, origen="ruta_usuario"))
            _imprimir(f"Fuente de logs registrada: {candidata}")
            return

        if candidata and _parece_ruta_de_archivo(candidata):
            entrada = _leer_entrada(
                f"No pude acceder a '{candidata}' como archivo. Revisa la ruta e "
                "inténtalo de nuevo, o pega el contenido de los logs directamente: "
            )
            continue

        lineas = _acumular_lineas_pegadas(entrada)
        _registrar_contenido_pegado(caso, lineas)
        return


def _preguntar_al_usuario_cli(pregunta: str) -> str:
    """Implementación del callback de `preguntar_al_usuario` para la CLI (US4).

    Parameters
    ----------
    pregunta : str
        Pregunta formulada por el agente de búsqueda de logs.

    Returns
    -------
    str
        Respuesta escrita por el usuario.
    """
    return _leer_entrada(f"{pregunta} ")


def _buscar_y_presentar_apreciacion_logs(caso: Caso, chat_model: BaseChatModel) -> None:
    """Invoca `buscar_evidencia` y presenta la apreciación resultante (US2/US3).

    Guarda el resultado en `Caso.apreciacion_logs` (FR-010) para que quede
    disponible en el contexto del caso para referencias posteriores. Muestra
    un indicador de actividad mientras se ejecuta la búsqueda (FR-004 de spec
    004) — si el agente invoca `preguntar_al_usuario` durante la búsqueda
    (spec 002, US4), el indicador se pausa automáticamente alrededor del
    mensaje/lectura intercalados (comportamiento nativo de
    `rich.console.Console.status`), sin afectar el valor leído.

    Parameters
    ----------
    caso : Caso
        Caso con al menos una fuente de logs aportada.
    chat_model : BaseChatModel
        Modelo de chat a usar para la búsqueda.
    """
    try:
        with mostrar_actividad("Buscando en los logs aportados..."):
            apreciacion = buscar_evidencia(
                chat_model, caso, caso.fuentes_logs, _preguntar_al_usuario_cli
            )
    except LogSearchEngineError:
        _imprimir(
            "No pude completar la búsqueda en los logs en este momento (error "
            "de comunicación con el motor de búsqueda).",
            es_error=True,
        )
        return

    caso.apreciacion_logs = apreciacion
    _imprimir(apreciacion.resumen)
    if apreciacion.hay_mas_coincidencias:
        _imprimir(
            "Hay más coincidencias además de las mostradas arriba; puedo "
            "profundizar si lo necesitas."
        )


def _consultar_y_presentar_apreciacion_bd(
    caso: Caso, chat_model: BaseChatModel, fuente_bd: FuenteDeBaseDeDatosConfigurada
) -> None:
    """Invoca `consultar_evidencia_bd` y presenta la apreciación resultante (spec 005).

    Guarda el resultado en `Caso.apreciacion_bd` (FR-009) para que quede
    disponible en el contexto del caso para referencias posteriores. Se
    invoca de forma **independiente** de si hay evidencia de logs para el
    caso (Clarifications de `specs/005-consultas-base-datos/spec.md`, Sesión
    2026-09-21, Pregunta 3) — nunca condicionada a `caso.fuentes_logs`.

    Parameters
    ----------
    caso : Caso
        Caso con la recepción de incidencia ya completa.
    chat_model : BaseChatModel
        Modelo de chat a usar para la consulta.
    fuente_bd : FuenteDeBaseDeDatosConfigurada
        Conexión y alcance de tablas ya construidos (ver
        `opssleuth.database.factory.crear_motor_bd`).
    """
    try:
        apreciacion = consultar_evidencia_bd(
            chat_model, caso, fuente_bd, anunciar_actividad=mostrar_actividad
        )
    except DatabaseSearchEngineError:
        _imprimir(
            "No pude completar la consulta a la base de datos en este momento "
            "(error de comunicación con el motor de consulta).",
            es_error=True,
        )
        return

    caso.apreciacion_bd = apreciacion
    _imprimir(apreciacion.resumen)
    if apreciacion.hay_mas_resultados:
        _imprimir(
            "Hay más resultados además de los mostrados arriba; puedo "
            "profundizar si lo necesitas."
        )


def _procesar_intake(caso: Caso, chat_model: BaseChatModel) -> str | None:
    """Ejecuta el flujo completo de recepción de una incidencia para un caso.

    Solicita y registra la descripción inicial (FR-001-003, FR-011), evalúa los
    3 campos requeridos y detecta si describe múltiples problemas (FR-006),
    confirma cuál es el problema principal si aplica, y formula preguntas de
    aclaración para los campos que sigan faltando (FR-007, FR-009), marcando la
    información como completa cuando ya no falten campos (FR-008). Además,
    detecta si el mensaje inicial ya incluye una ruta de logs (Historia 1, spec
    003) — de forma independiente al éxito de la evaluación del LLM, porque la
    detección es puramente léxica. Cuando el lote inicial de preguntas de
    aclaración tiene 2 o más pendientes, las presenta combinadas en un único
    turno (Historia 2, spec 003) antes de recurrir al bucle uno-por-uno para lo
    que siga faltando. Muestra un indicador de actividad mientras se evalúa la
    descripción inicial (FR-004 de spec 004).

    Parameters
    ----------
    caso : Caso
        Caso recién creado (sin descripción registrada) o ya iniciado.
    chat_model : BaseChatModel
        Modelo de chat a usar para evaluar la descripción y las respuestas.

    Returns
    -------
    str or None
        Ruta de logs candidata detectada en el mensaje inicial (FR-001 de spec
        003), o `None` si no se detectó ninguna. La validación de su
        accesibilidad se difiere al llamador (ver `_solicitar_evidencia_logs`).
    """
    _solicitar_descripcion(caso)
    ruta_candidata = _extraer_ruta_candidata(caso.descripcion_inicial.texto)

    try:
        with mostrar_actividad("Pensando..."):
            evaluacion = evaluar_descripcion(
                chat_model, caso.descripcion_inicial.texto, caso.mensajes
            )
    except ClarificationEngineError:
        _imprimir(
            "No pude evaluar la descripción en este momento (error de "
            "comunicación con el motor de aclaración). Continuaré con la "
            "descripción tal como la registraste.",
            es_error=True,
        )
        return ruta_candidata

    _aplicar_campos_evaluados(caso, evaluacion)
    _confirmar_problema_principal(caso, evaluacion)

    aclaraciones_sugeridas = generar_preguntas(evaluacion, caso.mensajes)
    preguntas_de_campos = [
        a for a in aclaraciones_sugeridas if a.campo_objetivo in CAMPOS_DE_DESCRIPCION
    ]

    if not preguntas_de_campos:
        caso.marcar_informacion_completa()
        return ruta_candidata

    if len(preguntas_de_campos) >= 2:
        preguntas_de_campos = _formular_y_registrar_aclaraciones_combinadas(
            caso, chat_model, preguntas_de_campos
        )

    for aclaracion in preguntas_de_campos:
        if aclaracion.campo_objetivo not in caso.descripcion_inicial.campos_faltantes():
            continue  # ya se respondió como efecto de una aclaración anterior
        _formular_y_registrar_aclaracion(caso, chat_model, aclaracion)

    if not caso.descripcion_inicial.campos_faltantes():
        caso.marcar_informacion_completa()

    return ruta_candidata


def _intentar_crear_motor_bd() -> FuenteDeBaseDeDatosConfigurada | None:
    """Intenta construir la conexión a base de datos configurada (spec 005).

    Envuelve `crear_motor_bd()`: si la base de datos está configurada pero no
    es accesible (`ConexionBaseDeDatosError`), informa al usuario y devuelve
    `None` — la conversación continúa sin esa fuente de evidencia (US1,
    Escenario 3 de `specs/005-consultas-base-datos/spec.md`). Un error de
    configuración (`TablasPermitidasNoConfiguradasError`) se deja propagar
    sin capturar, igual que las excepciones de configuración equivalentes de
    `crear_modelo_chat()` — es un fallo del operador, no del entorno de
    ejecución.

    Returns
    -------
    FuenteDeBaseDeDatosConfigurada or None
        La fuente configurada, o `None` si no está configurada o no es
        accesible en este momento.
    """
    try:
        return crear_motor_bd()
    except ConexionBaseDeDatosError:
        _imprimir(
            "No pude conectarme a la base de datos configurada; continuaré "
            "sin esa fuente de evidencia.",
            es_error=True,
        )
        return None


def ejecutar_conversacion(chat_model: BaseChatModel | None = None) -> None:
    """Ejecuta el bucle principal de la conversación de OpsSleuth.

    Gestiona el ciclo de vida de los casos dentro de la conversación: al inicio
    (o tras finalizar uno) crea un caso nuevo y ejecuta su intake; mientras un
    caso está activo, responde a solicitudes de resumen (FR-005) y a la
    intención de reportar un problema nuevo, bloqueando casos en paralelo hasta
    que se confirme finalizar el actual (FR-013, FR-014). Si hay una base de
    datos configurada (spec 005), la construye una única vez para toda la
    conversación (mismo patrón que `chat_model`) y, tras completar el intake
    de cada caso, consulta esa fuente de forma independiente de si hay
    evidencia de logs.

    Parameters
    ----------
    chat_model : BaseChatModel, optional
        Modelo de chat a usar. Si no se proporciona, se crea uno mediante
        `crear_modelo_chat()` según la variable de entorno
        `OPSSLEUTH_LLM_PROVIDER`.
    """
    chat_model = chat_model or crear_modelo_chat()
    caso: Caso | None = None
    fuente_bd = _intentar_crear_motor_bd()

    while True:
        if caso is None or caso.estado_caso == "finalizado":
            caso = Caso()
            _imprimir("--- Nuevo caso ---")
            ruta_candidata = _procesar_intake(caso, chat_model)
            _imprimir(caso.resumen())
            if caso.estado_informacion == "completa":
                _solicitar_evidencia_logs(caso, ruta_candidata=ruta_candidata)
                if caso.fuentes_logs:
                    _buscar_y_presentar_apreciacion_logs(caso, chat_model)
                if fuente_bd is not None:
                    # Independiente de la evidencia de logs (spec 005,
                    # Clarifications Sesión 2026-09-21, Pregunta 3) — nunca
                    # condicionado a `caso.fuentes_logs`.
                    _consultar_y_presentar_apreciacion_bd(caso, chat_model, fuente_bd)

        entrada = _leer_entrada(
            "\n¿Algo más sobre este caso? (o 'nuevo caso' / 'salir'): "
        )

        if entrada.strip().lower() in FRASES_SALIDA:
            _imprimir("Hasta luego.")
            return

        if _es_intencion_nuevo_caso(entrada):
            if caso.estado_caso == "activo":
                confirmacion = _leer_entrada(
                    "Hay un caso en curso. ¿Confirmas que quieres darlo por "
                    "finalizado y abrir uno nuevo? (sí/no): "
                )
                if not _es_confirmacion(confirmacion):
                    _imprimir("De acuerdo, seguimos con el caso actual.")
                    continue
            caso.finalizar()
            continue

        if _es_solicitud_de_resumen(entrada):
            _imprimir(caso.resumen())
            if caso.apreciacion_logs is not None:
                _imprimir(caso.apreciacion_logs.resumen)
            if caso.apreciacion_bd is not None:
                _imprimir(caso.apreciacion_bd.resumen)
            continue

        if entrada.strip() and os.path.isfile(entrada.strip()):
            # Fuente de logs adicional aportada en cualquier momento (FR-013).
            caso.fuentes_logs.append(FuenteDeLogs(ruta=entrada.strip(), origen="ruta_usuario"))
            _imprimir(f"Fuente de logs adicional registrada: {entrada.strip()}")
            _buscar_y_presentar_apreciacion_logs(caso, chat_model)
            continue

        caso.agregar_mensaje("user", entrada)
        _imprimir("Anotado como parte del contexto de este caso.")


def main() -> None:
    """Punto de entrada de la CLI (``python -m opssleuth.cli``).

    Muestra el banner de bienvenida (texto literal, sin etiqueta de rol ni
    Markdown — ver `mostrar_banner`) antes de arrancar la conversación. Antes
    de arrancar la conversación, carga las variables de entorno definidas en
    un archivo ``.env`` en el directorio de trabajo (si existe), sin
    sobrescribir las que ya estén definidas en el entorno — así
    `crear_modelo_chat` (y cualquier otra lectura de `os.environ`) las ve
    igual que si se hubieran exportado manualmente.
    """
    mostrar_banner()
    load_dotenv()
    try:
        ejecutar_conversacion()
    except (KeyboardInterrupt, EOFError):
        _imprimir("\nHasta luego.")


if __name__ == "__main__":
    main()
