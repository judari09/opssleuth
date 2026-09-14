"""Bucle conversacional de la CLI de OpsSleuth.

Orquesta la recepción de incidencias (spec 001: descripción inicial, contexto
de la conversación, aclaración ante ambigüedad) y la búsqueda de evidencia en
logs (spec 002). Depende únicamente de `opssleuth.domain.case`, del módulo de
aclaración (`opssleuth.clarification.engine`) y de un `BaseChatModel` ya
construido (inyectado vía `opssleuth.llm.factory.crear_modelo_chat`) — nunca de
un SDK de proveedor de modelo concreto directamente (Principio II de la
constitución).
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
from opssleuth.domain.case import Aclaracion, CampoExtraido, Caso, DescripcionVaciaError
from opssleuth.domain.log_evidence import FuenteDeLogs
from opssleuth.evidence.engine import LogSearchEngineError, buscar_evidencia
from opssleuth.llm.factory import crear_modelo_chat

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

    Parameters
    ----------
    prompt : str
        Mensaje mostrado antes de esperar la entrada.

    Returns
    -------
    str
        Texto escrito por el usuario.
    """
    return input(prompt)


def _imprimir(mensaje: str) -> None:
    """Muestra un mensaje del sistema al usuario.

    Parameters
    ----------
    mensaje : str
        Texto a mostrar.
    """
    print(mensaje)


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


def _aplicar_campos_evaluados(caso: Caso, evaluacion: EvaluacionDescripcion) -> None:
    """Copia los 3 campos evaluados por el motor a la descripción del caso (FR-006).

    Parameters
    ----------
    caso : Caso
        Caso cuya `descripcion_inicial` se actualizará.
    evaluacion : EvaluacionDescripcion
        Evaluación estructurada producida por `ClarificationEngine.evaluar`.
    """
    descripcion = caso.descripcion_inicial
    descripcion.sistema_afectado = CampoExtraido(
        presente=evaluacion.sistema_afectado.presente, valor=evaluacion.sistema_afectado.valor
    )
    descripcion.sintoma = CampoExtraido(
        presente=evaluacion.sintoma.presente, valor=evaluacion.sintoma.valor
    )
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
    (edge case de contradicción).

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


def _solicitar_evidencia_logs(caso: Caso) -> None:
    """Invita proactivamente a aportar evidencia de logs y registra la fuente (US1).

    Se invoca en cuanto la recepción de la incidencia queda con información
    completa (FR-014). Acepta una ruta de archivo o contenido pegado
    directamente (FR-001); si la ruta indicada no es accesible, informa y
    permite reintentar con otra ruta o pegar los logs directamente (FR-002).

    Parameters
    ----------
    caso : Caso
        Caso con la recepción de incidencia ya completa.
    """
    if caso.fuentes_logs:
        return

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
    disponible en el contexto del caso para referencias posteriores.

    Parameters
    ----------
    caso : Caso
        Caso con al menos una fuente de logs aportada.
    chat_model : BaseChatModel
        Modelo de chat a usar para la búsqueda.
    """
    _imprimir("Buscando en los logs aportados...")
    try:
        apreciacion = buscar_evidencia(
            chat_model, caso, caso.fuentes_logs, _preguntar_al_usuario_cli
        )
    except LogSearchEngineError:
        _imprimir(
            "No pude completar la búsqueda en los logs en este momento (error "
            "de comunicación con el motor de búsqueda)."
        )
        return

    caso.apreciacion_logs = apreciacion
    _imprimir(apreciacion.resumen)
    if apreciacion.hay_mas_coincidencias:
        _imprimir(
            "Hay más coincidencias además de las mostradas arriba; puedo "
            "profundizar si lo necesitas."
        )


def _procesar_intake(caso: Caso, chat_model: BaseChatModel) -> None:
    """Ejecuta el flujo completo de recepción de una incidencia para un caso.

    Solicita y registra la descripción inicial (FR-001-003, FR-011), evalúa los
    3 campos requeridos y detecta si describe múltiples problemas (FR-006),
    confirma cuál es el problema principal si aplica, y formula preguntas de
    aclaración para los campos que sigan faltando (FR-007, FR-009), marcando la
    información como completa cuando ya no falten campos (FR-008).

    Parameters
    ----------
    caso : Caso
        Caso recién creado (sin descripción registrada) o ya iniciado.
    chat_model : BaseChatModel
        Modelo de chat a usar para evaluar la descripción y las respuestas.
    """
    _solicitar_descripcion(caso)

    try:
        evaluacion = evaluar_descripcion(
            chat_model, caso.descripcion_inicial.texto, caso.mensajes
        )
    except ClarificationEngineError:
        _imprimir(
            "No pude evaluar la descripción en este momento (error de "
            "comunicación con el motor de aclaración). Continuaré con la "
            "descripción tal como la registraste."
        )
        return

    _aplicar_campos_evaluados(caso, evaluacion)
    _confirmar_problema_principal(caso, evaluacion)

    aclaraciones_sugeridas = generar_preguntas(evaluacion, caso.mensajes)
    preguntas_de_campos = [
        a for a in aclaraciones_sugeridas if a.campo_objetivo in CAMPOS_DE_DESCRIPCION
    ]

    if not preguntas_de_campos:
        caso.marcar_informacion_completa()
        return

    for aclaracion in preguntas_de_campos:
        if aclaracion.campo_objetivo not in caso.descripcion_inicial.campos_faltantes():
            continue  # ya se respondió como efecto de una aclaración anterior
        _formular_y_registrar_aclaracion(caso, chat_model, aclaracion)

    if not caso.descripcion_inicial.campos_faltantes():
        caso.marcar_informacion_completa()


def ejecutar_conversacion(chat_model: BaseChatModel | None = None) -> None:
    """Ejecuta el bucle principal de la conversación de OpsSleuth.

    Gestiona el ciclo de vida de los casos dentro de la conversación: al inicio
    (o tras finalizar uno) crea un caso nuevo y ejecuta su intake; mientras un
    caso está activo, responde a solicitudes de resumen (FR-005) y a la
    intención de reportar un problema nuevo, bloqueando casos en paralelo hasta
    que se confirme finalizar el actual (FR-013, FR-014).

    Parameters
    ----------
    chat_model : BaseChatModel, optional
        Modelo de chat a usar. Si no se proporciona, se crea uno mediante
        `crear_modelo_chat()` según la variable de entorno
        `OPSSLEUTH_LLM_PROVIDER`.
    """
    chat_model = chat_model or crear_modelo_chat()
    caso: Caso | None = None

    while True:
        if caso is None or caso.estado_caso == "finalizado":
            caso = Caso()
            _imprimir("--- Nuevo caso ---")
            _procesar_intake(caso, chat_model)
            _imprimir(caso.resumen())
            if caso.estado_informacion == "completa":
                _solicitar_evidencia_logs(caso)
                if caso.fuentes_logs:
                    _buscar_y_presentar_apreciacion_logs(caso, chat_model)

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

    Antes de arrancar la conversación, carga las variables de entorno
    definidas en un archivo ``.env`` en el directorio de trabajo (si existe),
    sin sobrescribir las que ya estén definidas en el entorno — así
    `crear_modelo_chat` (y cualquier otra lectura de `os.environ`) las ve
    igual que si se hubieran exportado manualmente.
    """
    load_dotenv()
    try:
        ejecutar_conversacion()
    except (KeyboardInterrupt, EOFError):
        _imprimir("\nHasta luego.")


if __name__ == "__main__":
    main()
