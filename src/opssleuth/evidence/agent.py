"""Construcción del agente de búsqueda de logs (ver contracts/log_search_engine.md).

Usa `langchain.agents.create_agent` — la misma construcción ya usada por
`opssleuth.clarification.engine.evaluar_descripcion` — parametrizada por un
`BaseChatModel` inyectado y enlazada a las herramientas de
`opssleuth.evidence.tools`. Una única función de construcción sirve para
ambos proveedores (Claude, Ollama): `BaseChatModel.bind_tools()` es uniforme
entre ellos, por lo que no existe ya la asimetría Tool Runner/bucle manual que
tenía el diseño original de esta spec (ver research.md, Decisión 3).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from opssleuth.domain.case import Caso
from opssleuth.evidence.tools import crear_herramienta_preguntar, crear_herramientas_busqueda

MAXIMO_ITERACIONES_AGENTE = 15
"""Límite de iteraciones del bucle agéntico (Regla 7 del contrato — evita bucles sin fin)."""


def construir_instrucciones_sistema(caso: Caso) -> str:
    """Construye el prompt de sistema del agente a partir del contexto del caso.

    Incluye el ancla temporal (`Caso.creado_en`) y el momento del incidente
    (si se conoce) para que el modelo pueda construir sus propios patrones
    regex de fecha/hora al aislar entradas por horario (FR-006, ver
    research.md Decisión 4), y guía explícita sobre cuándo usar
    `preguntar_al_usuario` (FR-011/FR-012).

    Parameters
    ----------
    caso : Caso
        Caso en investigación, con su descripción y aclaraciones ya registradas.

    Returns
    -------
    str
        Prompt de sistema para el agente de búsqueda de logs.
    """
    descripcion = caso.descripcion_inicial
    sistema_afectado = descripcion.sistema_afectado.valor if descripcion else None
    sintoma = descripcion.sintoma.valor if descripcion else None
    momento = descripcion.momento.valor if descripcion else None

    return f"""\
Eres el motor de búsqueda de evidencia en logs de OpsSleuth, una herramienta \
de apoyo para equipos de soporte técnico. Tu tarea es localizar, dentro de la \
fuente de logs activa, las entradas relacionadas con el siguiente incidente, \
usando las herramientas disponibles — nunca asumas el contenido del archivo \
sin haberlo consultado con una herramienta.

Contexto del incidente:
- Sistema o aplicación afectada: {sistema_afectado or "no especificado"}
- Síntoma: {sintoma or "no especificado"}
- Momento reportado del incidente: {momento or "no especificado"}
- El caso se registró el (hora de referencia UTC): {caso.creado_en.isoformat()}

Instrucciones:
1. Si se conoce el momento del incidente (aunque sea relativo, p. ej. "hace \
una hora"), interprétalo usando la hora de referencia del caso como ancla, y \
construye tú mismo un patrón de expresión regular de fecha/hora adecuado al \
formato que observes en el archivo para usar con `buscar_texto`.
2. Si no se conoce el momento, busca por el sistema afectado o el síntoma \
descritos.
3. Usa `contar_lineas` al inicio para calibrar el tamaño de la fuente.
4. Si no encuentras ninguna coincidencia relevante, dilo explícitamente en tu \
respuesta final — nunca fabriques una conclusión sin evidencia real.
5. Usa `preguntar_al_usuario` ÚNICAMENTE cuando el contenido de los logs o del \
problema descrito use terminología, nombres de componentes o convenciones de \
formato propias del proyecto que no puedas interpretar sin más contexto. No la \
uses si el contenido ya es interpretable por sí mismo.
6. Al terminar, redacta una apreciación breve y concreta de lo que observaste \
en las entradas relevantes, relacionándolo con el incidente descrito."""


def construir_agente(
    chat_model: BaseChatModel, ruta_archivo: str, preguntar_callback: Callable[[str], str], caso: Caso
):
    """Construye el agente de búsqueda de logs para una fuente activa.

    Parameters
    ----------
    chat_model : BaseChatModel
        Modelo de chat ya construido (ver `opssleuth.llm.factory.crear_modelo_chat`).
    ruta_archivo : str
        Ruta absoluta a la fuente de logs activa.
    preguntar_callback : Callable[[str], str]
        Callback invocado por la herramienta `preguntar_al_usuario`.
    caso : Caso
        Caso en investigación, usado para construir el prompt de sistema.

    Returns
    -------
    CompiledStateGraph
        Agente listo para invocar con `.invoke({"messages": [...]})`.
    """
    herramientas = [
        *crear_herramientas_busqueda(ruta_archivo),
        crear_herramienta_preguntar(preguntar_callback),
    ]
    return create_agent(
        model=chat_model,
        tools=herramientas,
        system_prompt=construir_instrucciones_sistema(caso),
    )
