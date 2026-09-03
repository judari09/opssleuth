"""Bucle conversacional de la CLI de recepción de incidencias (OpsSleuth).

Orquesta las tres historias de usuario de esta funcionalidad: recepción de la
descripción inicial (US1), mantenimiento del contexto de la conversación (US2), y
aclaración ante descripciones ambiguas (US3). Depende únicamente de
`opssleuth.domain.case` y del contrato `ClarificationEngine` — nunca de un SDK de
proveedor de modelo concreto (Principio II de la constitución).
"""

from __future__ import annotations

from opssleuth.clarification.engine import (
    ClarificationEngine,
    ClarificationEngineError,
    EvaluacionDescripcion,
)
from opssleuth.clarification.factory import crear_motor_aclaracion
from opssleuth.domain.case import Aclaracion, CampoExtraido, Caso, DescripcionVaciaError

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
    caso: Caso, motor: ClarificationEngine, aclaracion: Aclaracion
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
    motor : ClarificationEngine
        Motor usado para evaluar la respuesta en busca de contradicciones.
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
        evaluacion_respuesta = motor.evaluar(respuesta, caso.mensajes)
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


def _procesar_intake(caso: Caso, motor: ClarificationEngine) -> None:
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
    motor : ClarificationEngine
        Motor de aclaración a usar para evaluar la descripción y las respuestas.
    """
    _solicitar_descripcion(caso)

    try:
        evaluacion = motor.evaluar(caso.descripcion_inicial.texto, caso.mensajes)
    except ClarificationEngineError:
        _imprimir(
            "No pude evaluar la descripción en este momento (error de "
            "comunicación con el motor de aclaración). Continuaré con la "
            "descripción tal como la registraste."
        )
        return

    _aplicar_campos_evaluados(caso, evaluacion)
    _confirmar_problema_principal(caso, evaluacion)

    aclaraciones_sugeridas = motor.generar_preguntas(evaluacion, caso.mensajes)
    preguntas_de_campos = [
        a for a in aclaraciones_sugeridas if a.campo_objetivo in CAMPOS_DE_DESCRIPCION
    ]

    if not preguntas_de_campos:
        caso.marcar_informacion_completa()
        return

    for aclaracion in preguntas_de_campos:
        if aclaracion.campo_objetivo not in caso.descripcion_inicial.campos_faltantes():
            continue  # ya se respondió como efecto de una aclaración anterior
        _formular_y_registrar_aclaracion(caso, motor, aclaracion)

    if not caso.descripcion_inicial.campos_faltantes():
        caso.marcar_informacion_completa()


def ejecutar_conversacion(motor: ClarificationEngine | None = None) -> None:
    """Ejecuta el bucle principal de la conversación de recepción de incidencias.

    Gestiona el ciclo de vida de los casos dentro de la conversación: al inicio
    (o tras finalizar uno) crea un caso nuevo y ejecuta su intake; mientras un
    caso está activo, responde a solicitudes de resumen (FR-005) y a la
    intención de reportar un problema nuevo, bloqueando casos en paralelo hasta
    que se confirme finalizar el actual (FR-013, FR-014).

    Parameters
    ----------
    motor : ClarificationEngine, optional
        Motor de aclaración a usar. Si no se proporciona, se crea uno mediante
        `crear_motor_aclaracion()` según la variable de entorno
        `OPSSLEUTH_LLM_PROVIDER`.
    """
    motor = motor or crear_motor_aclaracion()
    caso: Caso | None = None

    while True:
        if caso is None or caso.estado_caso == "finalizado":
            caso = Caso()
            _imprimir("--- Nuevo caso ---")
            _procesar_intake(caso, motor)
            _imprimir(caso.resumen())

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
            continue

        caso.agregar_mensaje("user", entrada)
        _imprimir("Anotado como parte del contexto de este caso.")


def main() -> None:
    """Punto de entrada de la CLI (``python -m opssleuth.cli``)."""
    try:
        ejecutar_conversacion()
    except (KeyboardInterrupt, EOFError):
        _imprimir("\nHasta luego.")


if __name__ == "__main__":
    main()
