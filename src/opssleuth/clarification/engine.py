"""Motor de aclaración (ver contracts/clarification_migration.md).

Migrado a la arquitectura basada en LangChain adoptada por la spec 002 (ver
``specs/002-busqueda-logs/research.md``, Decisión 9): en vez de un contrato
``Protocol`` propio con una implementación por proveedor, este módulo expone
dos funciones simples parametrizadas por un ``BaseChatModel`` ya construido
(inyectado por el llamador, típicamente vía
``opssleuth.llm.factory.crear_modelo_chat()``). Este módulo no importa
``langchain_anthropic``/``langchain_ollama`` ni ningún SDK de proveedor
directamente (Principio II de la constitución).
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from opssleuth.domain.case import Aclaracion, CampoObjetivo

INSTRUCCIONES_EVALUACION = """\
Eres el motor de evaluación de incidencias de OpsSleuth, una herramienta de \
apoyo para equipos de soporte técnico. Analiza el último mensaje del usuario, \
teniendo en cuenta el historial de la conversación (contexto), y devuelve una \
evaluación estructurada con:

1. Para cada uno de estos 3 campos, si está presente en el mensaje y su valor \
extraído (null si no está presente):
   - sistema_afectado: el sistema o aplicación afectada.
   - sintoma: el síntoma o error observado.
   - momento: cuándo ocurrió o con qué frecuencia ocurre.
2. preguntas_sugeridas: una pregunta puntual y natural en español por cada campo \
ausente (máximo 3). Si además detectas que el mensaje describe más de un problema \
distinto, agrega una pregunta adicional con campo_objetivo="problema_principal" \
pidiendo que el usuario confirme cuál investigar. Vacío si no falta ningún campo \
y no hay múltiples problemas.
3. contradiccion: indica si el mensaje contradice algo ya dicho en el contexto de \
la conversación (p. ej. una fecha, sistema o síntoma distinto a lo mencionado \
antes). Si no hay contexto previo o no hay contradicción, detectada=false y \
descripcion=null.
4. multiples_problemas: indica si el mensaje describe más de un problema o \
incidencia distinta mezclados en el mismo texto. Si describe un solo problema, \
detectado=false y problemas_identificados=[].

No inventes valores: marca un campo como presente solo si el texto lo indica de \
forma explícita o inequívoca."""


class ClarificationEngineError(Exception):
    """Error de comunicación con el proveedor subyacente del motor de aclaración.

    `evaluar_descripcion` captura las excepciones que el proveedor subyacente
    (a través de LangChain) propague y las relanza como esta excepción,
    conservando la excepción original como `__cause__`. Se captura de forma
    amplia (`Exception`) porque acotar el mapeo a tipos de excepción concretos
    de cada proveedor (p. ej. `anthropic.APIError`) requeriría importar esos
    SDKs directamente en este módulo, lo cual violaría el confinamiento del
    acoplamiento a terceros exigido por la excepción del Principio II (ver
    ``specs/002-busqueda-logs/research.md``, Decisión 1, nota de riesgo).
    """


class CampoExtraidoLLM(BaseModel):
    """Evaluación de presencia/valor de un campo requerido, tal como la produce el modelo.

    Attributes
    ----------
    presente : bool
        Si el campo está presente en el texto evaluado.
    valor : str or None
        Valor extraído del texto si ``presente`` es True; None en caso contrario.
    """

    model_config = ConfigDict(extra="forbid")

    presente: bool
    valor: str | None = None


class PreguntaSugerida(BaseModel):
    """Una pregunta de aclaración sugerida por la evaluación.

    Attributes
    ----------
    campo_objetivo : {"sistema_afectado", "sintoma", "momento", "problema_principal"}
        A qué campo (o a la confirmación del problema principal) apunta la pregunta.
    pregunta : str
        Texto de la pregunta sugerida.
    """

    model_config = ConfigDict(extra="forbid")

    campo_objetivo: CampoObjetivo
    pregunta: str


class Contradiccion(BaseModel):
    """Evaluación de si el texto analizado contradice el contexto previo.

    Attributes
    ----------
    detectada : bool
        Si se detectó una contradicción con el contexto.
    descripcion : str or None
        Explicación breve de la inconsistencia; None si ``detectada`` es False.
    """

    model_config = ConfigDict(extra="forbid")

    detectada: bool
    descripcion: str | None = None


class MultiplesProblemas(BaseModel):
    """Evaluación de si el texto analizado describe más de un problema distinto.

    Attributes
    ----------
    detectado : bool
        Si se detectaron múltiples problemas en el texto.
    problemas_identificados : list of str
        Etiquetas breves de cada problema distinto identificado; vacío si
        ``detectado`` es False.
    """

    model_config = ConfigDict(extra="forbid")

    detectado: bool
    problemas_identificados: list[str] = Field(default_factory=list, max_length=5)


class EvaluacionDescripcion(BaseModel):
    """Salida estructurada de `evaluar_descripcion` (ver evaluacion_schema.json).

    Attributes
    ----------
    sistema_afectado : CampoExtraidoLLM
        Evaluación del sistema o aplicación afectada.
    sintoma : CampoExtraidoLLM
        Evaluación del síntoma o error observado.
    momento : CampoExtraidoLLM
        Evaluación del momento o frecuencia de ocurrencia.
    preguntas_sugeridas : list of PreguntaSugerida
        Preguntas de aclaración puntuales para los campos ausentes y/o la
        confirmación del problema principal.
    contradiccion : Contradiccion
        Evaluación de contradicción con el contexto previo.
    multiples_problemas : MultiplesProblemas
        Evaluación de si el texto describe más de un problema distinto.
    """

    model_config = ConfigDict(extra="forbid")

    sistema_afectado: CampoExtraidoLLM
    sintoma: CampoExtraidoLLM
    momento: CampoExtraidoLLM
    preguntas_sugeridas: list[PreguntaSugerida] = Field(default_factory=list, max_length=4)
    contradiccion: Contradiccion
    multiples_problemas: MultiplesProblemas


def evaluar_descripcion(
    chat_model: BaseChatModel, texto: str, contexto: list[dict]
) -> EvaluacionDescripcion:
    """Evalúa `texto` dado el `contexto` de la conversación del caso.

    Sin efectos secundarios sobre el `Caso` (Regla 1 del contrato). Usa
    `langchain.agents.create_agent` con `response_format=EvaluacionDescripcion`
    (sin herramientas) para obtener la salida estructurada — el modelo produce
    directamente una instancia de `EvaluacionDescripcion` en
    ``resultado["structured_response"]``.

    Parameters
    ----------
    chat_model : BaseChatModel
        Modelo de chat ya construido (ver `opssleuth.llm.factory.crear_modelo_chat`).
    texto : str
        Texto a evaluar (descripción inicial o respuesta de aclaración).
    contexto : list of dict
        Historial de la conversación del caso, en formato ``role``/``content``.

    Returns
    -------
    EvaluacionDescripcion
        Evaluación estructurada de campos, contradicción y múltiples problemas.

    Raises
    ------
    ClarificationEngineError
        Si ocurre un error de comunicación con el proveedor subyacente.
    """
    agente = create_agent(
        model=chat_model,
        tools=[],
        system_prompt=INSTRUCCIONES_EVALUACION,
        response_format=EvaluacionDescripcion,
    )
    mensajes = [*contexto, {"role": "user", "content": texto}]
    try:
        resultado = agente.invoke({"messages": mensajes})
    except Exception as error:
        raise ClarificationEngineError(
            "Error al comunicarse con el proveedor de modelo subyacente."
        ) from error
    return resultado["structured_response"]


def generar_preguntas(
    evaluacion: EvaluacionDescripcion, contexto: list[dict]
) -> list[Aclaracion]:
    """Transforma `evaluacion.preguntas_sugeridas` en objetos `Aclaracion`.

    Transformación determinista (Regla 5 del contrato) — NO realiza una
    llamada adicional al modelo. Sin cambios de comportamiento respecto a la
    implementación original de 001.

    Parameters
    ----------
    evaluacion : EvaluacionDescripcion
        Evaluación previamente producida por `evaluar_descripcion`.
    contexto : list of dict
        Historial de la conversación del caso (sin uso en la transformación
        determinista, presente por simetría con `evaluar_descripcion`).

    Returns
    -------
    list of Aclaracion
        Una `Aclaracion` sin responder por cada pregunta sugerida.
    """
    del contexto  # no se usa: la transformación es determinista
    return [
        Aclaracion(pregunta=sugerida.pregunta, campo_objetivo=sugerida.campo_objetivo)
        for sugerida in evaluacion.preguntas_sugeridas
    ]
