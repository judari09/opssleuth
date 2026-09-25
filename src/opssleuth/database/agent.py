"""Construcción del agente de consulta a base de datos (ver contracts/database_query_engine.md).

Usa `langchain.agents.create_agent` — la misma construcción ya usada por
`opssleuth.evidence.agent.construir_agente` — parametrizada por un
`BaseChatModel` inyectado y enlazada a las herramientas de
`opssleuth.database.tools`.
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from opssleuth.database.factory import FuenteDeBaseDeDatosConfigurada
from opssleuth.database.tools import crear_herramientas_bd
from opssleuth.domain.case import Caso

MAXIMO_ITERACIONES_AGENTE_BD = 15
"""Límite de iteraciones del bucle agéntico (Regla 9 del contrato — evita bucles sin fin)."""


def construir_instrucciones_sistema(caso: Caso, fuente: FuenteDeBaseDeDatosConfigurada) -> str:
    """Construye el prompt de sistema del agente a partir del contexto del caso.

    Incluye guía explícita sobre usar `listar_tablas_disponibles`/
    `describir_tabla` antes de construir una consulta, y sobre construir
    cruces (joins) entre más de dos tablas cuando la evidencia relevante para
    el incidente esté distribuida entre ellas.

    Parameters
    ----------
    caso : Caso
        Caso en investigación, con su descripción y aclaraciones ya registradas.
    fuente : FuenteDeBaseDeDatosConfigurada
        Conexión y alcance de tablas ya construidos.

    Returns
    -------
    str
        Prompt de sistema para el agente de consulta a base de datos.
    """
    descripcion = caso.descripcion_inicial
    sistema_afectado = descripcion.sistema_afectado.valor if descripcion else None
    sintoma = descripcion.sintoma.valor if descripcion else None
    momento = descripcion.momento.valor if descripcion else None
    tablas = ", ".join(fuente.fuente.tablas_permitidas)

    return f"""\
Eres el motor de consulta a base de datos de OpsSleuth, una herramienta de \
apoyo para equipos de soporte técnico. Tu tarea es localizar, en la base de \
datos configurada, filas relacionadas con el siguiente incidente, usando las \
herramientas disponibles — nunca asumas el contenido de una tabla sin \
haberla consultado con una herramienta.

Contexto del incidente:
- Sistema o aplicación afectada: {sistema_afectado or "no especificado"}
- Síntoma: {sintoma or "no especificado"}
- Momento reportado del incidente: {momento or "no especificado"}

Tablas a las que tienes acceso: {tablas}

Instrucciones:
1. Usa `listar_tablas_disponibles` si necesitas recordar qué tablas están
disponibles, y `describir_tabla` sobre cada tabla relevante antes de
construir una consulta — nunca adivines nombres de columna.
2. Empieza con una consulta simple sobre una sola tabla si basta para
localizar la evidencia relevante.
3. Si la evidencia relevante está distribuida entre varias tablas
relacionadas (p. ej. una transacción, el usuario que la originó, y el
estado de un servicio asociado), construye una consulta que las cruce
(JOIN) — incluso entre más de dos tablas — en vez de quedarte con
resultados aislados de una sola tabla.
4. Toda consulta que ejecutes con `ejecutar_consulta_sql` DEBE ser una única
sentencia SELECT de solo lectura sobre las tablas listadas arriba —
cualquier otra cosa será rechazada.
5. Si no encuentras ninguna fila relevante, dilo explícitamente en tu
respuesta final — nunca fabriques una conclusión sin evidencia real.
6. Al terminar, redacta una apreciación breve y concreta de lo que
observaste en las filas relevantes, relacionándolo con el incidente
descrito."""


def construir_agente(
    chat_model: BaseChatModel, fuente: FuenteDeBaseDeDatosConfigurada, caso: Caso
):
    """Construye el agente de consulta a base de datos para la fuente configurada.

    Parameters
    ----------
    chat_model : BaseChatModel
        Modelo de chat ya construido (ver `opssleuth.llm.factory.crear_modelo_chat`).
    fuente : FuenteDeBaseDeDatosConfigurada
        Conexión y alcance de tablas ya construidos (ver
        `opssleuth.database.factory.crear_motor_bd`).
    caso : Caso
        Caso en investigación, usado para construir el prompt de sistema.

    Returns
    -------
    CompiledStateGraph
        Agente listo para invocar con `.invoke({"messages": [...]})`.
    """
    herramientas = crear_herramientas_bd(fuente)
    return create_agent(
        model=chat_model,
        tools=herramientas,
        system_prompt=construir_instrucciones_sistema(caso, fuente),
    )
