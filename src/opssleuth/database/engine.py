"""Orquestación de la consulta de evidencia en base de datos (ver contracts/database_query_engine.md).

Este módulo no importa `sqlalchemy`/`sqlglot` directamente (Principio II de la
constitución) — recibe un `BaseChatModel` y una
`FuenteDeBaseDeDatosConfigurada` ya construidos como parámetros. Tampoco
importa `opssleuth.presentation` directamente — el anuncio de actividad
(FR-011) se recibe inyectado como `anunciar_actividad`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage

from opssleuth.database.agent import MAXIMO_ITERACIONES_AGENTE_BD, construir_agente
from opssleuth.database.factory import FuenteDeBaseDeDatosConfigurada
from opssleuth.domain.case import Caso
from opssleuth.domain.database_evidence import ApreciacionInicialBD, EntradaBDRelevante

MAXIMO_ENTRADAS_DESTACADAS = 20
"""Límite de entradas representativas en la apreciación final (FR-006)."""


class DatabaseSearchEngineError(Exception):
    """Error de comunicación con el proveedor subyacente del motor de consulta a base de datos.

    `consultar_evidencia_bd` captura las excepciones que el proveedor
    subyacente (a través de LangChain) propague y las relanza como esta
    excepción, conservando la excepción original como `__cause__`. Se captura
    de forma amplia (`Exception`) por el mismo motivo documentado en
    `LogSearchEngineError` — ver `opssleuth.evidence.engine.LogSearchEngineError`.
    Errores de conexión/ejecución contra la base de datos en sí (no el
    proveedor de modelo) NO se propagan como esta excepción — se capturan
    dentro de la propia herramienta `ejecutar_consulta_sql` (ver
    `opssleuth.database.tools`) y se devuelven al agente como un resultado de
    error explícito, para que el bucle continúe en vez de interrumpirse.
    """


def _extraer_entradas_de_mensajes(
    mensajes, fuente: FuenteDeBaseDeDatosConfigurada
) -> list[EntradaBDRelevante]:
    """Extrae `EntradaBDRelevante` de los `ToolMessage` reales de `ejecutar_consulta_sql`.

    Nunca a partir de texto libre generado por el modelo (Regla 7 del
    contrato) — solo de los resultados que la herramienta realmente devolvió.

    Parameters
    ----------
    mensajes : list
        Mensajes del estado final del agente (`resultado["messages"]`).
    fuente : FuenteDeBaseDeDatosConfigurada
        Fuente de la que provienen estos mensajes.

    Returns
    -------
    list of EntradaBDRelevante
        Entradas extraídas, en el orden en que las devolvió la herramienta.
    """
    entradas: list[EntradaBDRelevante] = []
    for mensaje in mensajes:
        if not isinstance(mensaje, ToolMessage):
            continue
        if mensaje.name != "ejecutar_consulta_sql":
            continue
        try:
            datos = json.loads(mensaje.content)
        except (json.JSONDecodeError, TypeError):
            continue
        filas = datos.get("filas")
        consulta_ejecutada = datos.get("consulta_ejecutada")
        if not filas or not consulta_ejecutada:
            continue
        for fila in filas:
            try:
                entradas.append(
                    EntradaBDRelevante(
                        fuente=fuente.fuente,
                        consulta=consulta_ejecutada,
                        fila=fila,
                    )
                )
            except (KeyError, ValueError):
                continue
    return entradas


def _limitar(entradas: list[EntradaBDRelevante]) -> tuple[list[EntradaBDRelevante], bool]:
    """Acota `entradas` a `MAXIMO_ENTRADAS_DESTACADAS` (FR-006).

    Parameters
    ----------
    entradas : list of EntradaBDRelevante
        Entradas acumuladas de la consulta.

    Returns
    -------
    tuple[list of EntradaBDRelevante, bool]
        Las entradas destacadas (acotadas) y si hay más resultados de los
        que se muestran.
    """
    hay_mas = len(entradas) > MAXIMO_ENTRADAS_DESTACADAS
    return entradas[:MAXIMO_ENTRADAS_DESTACADAS], hay_mas


def consultar_evidencia_bd(
    chat_model: BaseChatModel,
    caso: Caso,
    fuente: FuenteDeBaseDeDatosConfigurada,
    anunciar_actividad: Callable[[str], AbstractContextManager],
) -> ApreciacionInicialBD:
    """Localiza evidencia relevante en `fuente` y elabora una apreciación inicial.

    Invoca un agente sobre la fuente de base de datos configurada, registra
    de forma determinista cada `EntradaBDRelevante` a partir de los
    resultados reales de la herramienta `ejecutar_consulta_sql`, y anuncia
    visiblemente (FR-011) antes de invocar al agente.

    Parameters
    ----------
    chat_model : BaseChatModel
        Modelo de chat ya construido.
    caso : Caso
        Caso en investigación (descripción, aclaraciones).
    fuente : FuenteDeBaseDeDatosConfigurada
        Conexión y alcance de tablas ya construidos (ver
        `opssleuth.database.factory.crear_motor_bd`).
    anunciar_actividad : Callable[[str], AbstractContextManager]
        Gestor de contexto (inyectado — nunca importado directamente de
        `opssleuth.presentation`) que anuncia visiblemente la consulta en
        curso mientras se ejecuta.

    Returns
    -------
    ApreciacionInicialBD
        Apreciación inicial, con `entradas_destacadas` acotadas (FR-006) y
        `resumen` explícito cuando no se encontró evidencia.

    Raises
    ------
    DatabaseSearchEngineError
        Si ocurre un error de comunicación con el proveedor de modelo
        subyacente.
    """
    agente = construir_agente(chat_model, fuente, caso)
    try:
        # Un único anuncio envuelve todo el bucle agéntico (que puede incluir
        # varias llamadas a herramientas, incluidas 0+ consultas SQL reales),
        # no una por cada llamada individual — mismo patrón ya usado por
        # `_buscar_y_presentar_apreciacion_logs` (spec 004) al envolver
        # `buscar_evidencia`. Satisface FR-011 (nunca se consulta en
        # silencio) sin fragmentar la indicación de actividad en múltiples
        # parpadeos por cada tool-call del agente.
        with anunciar_actividad("Consultando la base de datos..."):
            resultado = agente.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Consulta la base de datos configurada para encontrar "
                                "información relacionada con el incidente descrito y "
                                "resume lo que encuentres."
                            ),
                        }
                    ]
                },
                config={"recursion_limit": MAXIMO_ITERACIONES_AGENTE_BD},
            )
    except Exception as error:
        raise DatabaseSearchEngineError(
            "Error al comunicarse con el proveedor de modelo subyacente durante "
            "la consulta a la base de datos."
        ) from error

    mensajes = resultado["messages"]
    entradas = _extraer_entradas_de_mensajes(mensajes, fuente)
    entradas_destacadas, hay_mas = _limitar(entradas)

    if not entradas_destacadas:
        resumen = "No se encontraron filas en la base de datos relacionadas con el incidente descrito."
    else:
        resumen = mensajes[-1].text if mensajes else ""

    return ApreciacionInicialBD(
        resumen=resumen,
        entradas_destacadas=entradas_destacadas,
        hay_mas_resultados=hay_mas,
        generada_en=datetime.now(timezone.utc),
    )
