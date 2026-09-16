"""Orquestación de la búsqueda de evidencia en logs (ver contracts/log_search_engine.md).

Este módulo no importa `langchain_anthropic`/`langchain_ollama` ni `anthropic`/
`ollama` directamente (Principio II de la constitución) — recibe un
`BaseChatModel` ya construido como parámetro.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage

from opssleuth.domain.case import Caso
from opssleuth.domain.log_evidence import ApreciacionInicialLogs, EntradaLogRelevante, FuenteDeLogs
from opssleuth.evidence.agent import MAXIMO_ITERACIONES_AGENTE, construir_agente

MAXIMO_ENTRADAS_DESTACADAS = 20
"""Límite de entradas representativas en la apreciación final (FR-009a)."""


class LogSearchEngineError(Exception):
    """Error de comunicación con el proveedor subyacente del motor de búsqueda de logs.

    `buscar_evidencia` captura las excepciones que el proveedor subyacente (a
    través de LangChain) propague y las relanza como esta excepción,
    conservando la excepción original como `__cause__`. Se captura de forma
    amplia (`Exception`) por el mismo motivo documentado en
    `ClarificationEngineError` — ver
    `opssleuth.clarification.engine.ClarificationEngineError`.
    """


def _extraer_entradas_de_mensajes(mensajes, fuente: FuenteDeLogs) -> list[EntradaLogRelevante]:
    """Extrae `EntradaLogRelevante` de los `ToolMessage` reales de `buscar_texto`/`leer_contexto`.

    Nunca a partir de texto libre generado por el modelo (Regla 5 del
    contrato, research.md Decisión 6) — solo de los resultados que las
    herramientas de búsqueda realmente devolvieron.

    Parameters
    ----------
    mensajes : list
        Mensajes del estado final del agente (`resultado["messages"]`).
    fuente : FuenteDeLogs
        Fuente de la que provienen estos mensajes.

    Returns
    -------
    list of EntradaLogRelevante
        Entradas extraídas, en el orden en que las devolvieron las herramientas.
    """
    entradas: list[EntradaLogRelevante] = []
    for mensaje in mensajes:
        if not isinstance(mensaje, ToolMessage):
            continue
        if mensaje.name not in ("buscar_texto", "leer_contexto"):
            continue
        try:
            datos = json.loads(mensaje.content)
        except (json.JSONDecodeError, TypeError):
            continue
        items = datos.get("coincidencias") or datos.get("lineas") or []
        for item in items:
            try:
                entradas.append(
                    EntradaLogRelevante(
                        fuente=fuente,
                        numero_linea=item["numero_linea"],
                        contenido=item["contenido"],
                    )
                )
            except (KeyError, ValueError):
                continue
    return entradas


def _limitar_y_deduplicar(
    entradas: list[EntradaLogRelevante],
) -> tuple[list[EntradaLogRelevante], bool]:
    """Deduplica y acota `entradas` a `MAXIMO_ENTRADAS_DESTACADAS` (FR-009a).

    Parameters
    ----------
    entradas : list of EntradaLogRelevante
        Entradas acumuladas de todas las fuentes.

    Returns
    -------
    tuple[list of EntradaLogRelevante, bool]
        Las entradas destacadas (acotadas y sin duplicados) y si hay más
        coincidencias de las que se muestran.
    """
    vistas: set[tuple[str, int]] = set()
    deduplicadas: list[EntradaLogRelevante] = []
    for entrada in entradas:
        clave = (entrada.fuente.ruta, entrada.numero_linea)
        if clave in vistas:
            continue
        vistas.add(clave)
        deduplicadas.append(entrada)

    hay_mas = len(deduplicadas) > MAXIMO_ENTRADAS_DESTACADAS
    return deduplicadas[:MAXIMO_ENTRADAS_DESTACADAS], hay_mas


def buscar_evidencia(
    chat_model: BaseChatModel,
    caso: Caso,
    fuentes: list[FuenteDeLogs],
    preguntar_callback: Callable[[str], str],
) -> ApreciacionInicialLogs:
    """Localiza evidencia relevante en `fuentes` y elabora una apreciación consolidada.

    Invoca un agente por fuente (una fuente activa a la vez), registra de
    forma determinista cada `EntradaLogRelevante` a partir de los resultados
    reales de las herramientas, y consolida los hallazgos de todas las
    fuentes en una única `ApreciacionInicialLogs` (FR-010a) — nunca una
    apreciación independiente por fuente.

    Parameters
    ----------
    chat_model : BaseChatModel
        Modelo de chat ya construido.
    caso : Caso
        Caso en investigación (descripción, aclaraciones, `creado_en`).
    fuentes : list of FuenteDeLogs
        Fuentes de logs a analizar.
    preguntar_callback : Callable[[str], str]
        Callback invocado por la herramienta `preguntar_al_usuario`.

    Returns
    -------
    ApreciacionInicialLogs
        Apreciación consolidada, con `entradas_destacadas` acotadas (FR-009a)
        y `resumen` explícito cuando no se encontró evidencia (FR-008, SC-003).

    Raises
    ------
    LogSearchEngineError
        Si ocurre un error de comunicación con el proveedor subyacente.
    """
    if not fuentes:
        return ApreciacionInicialLogs(
            resumen="No se aportó ninguna fuente de logs para analizar.",
            entradas_destacadas=[],
            hay_mas_coincidencias=False,
        )

    todas_las_entradas: list[EntradaLogRelevante] = []
    resumenes_por_fuente: list[str] = []

    try:
        for fuente in fuentes:
            agente = construir_agente(chat_model, fuente.ruta, preguntar_callback, caso)
            resultado = agente.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Busca en la fuente de logs activa las entradas "
                                "relacionadas con el incidente descrito y resume lo "
                                "que encuentres."
                            ),
                        }
                    ]
                },
                config={"recursion_limit": MAXIMO_ITERACIONES_AGENTE},
            )
            mensajes = resultado["messages"]
            todas_las_entradas.extend(_extraer_entradas_de_mensajes(mensajes, fuente))
            if mensajes:
                # `.text` (no `.content`/`str(...)`): algunos proveedores (p. ej.
                # Gemini) devuelven `content` como una lista de bloques con campos
                # adicionales (firmas de razonamiento, etc.) en vez de un string
                # plano; `.text` normaliza a texto solamente en cualquier proveedor.
                resumenes_por_fuente.append(mensajes[-1].text)
    except Exception as error:
        raise LogSearchEngineError(
            "Error al comunicarse con el proveedor de modelo subyacente durante "
            "la búsqueda de evidencia en logs."
        ) from error

    entradas_destacadas, hay_mas = _limitar_y_deduplicar(todas_las_entradas)

    if not entradas_destacadas:
        resumen = "No se encontraron entradas de log relacionadas con el incidente descrito."
    else:
        resumen = "\n\n".join(texto for texto in resumenes_por_fuente if texto)

    return ApreciacionInicialLogs(
        resumen=resumen,
        entradas_destacadas=entradas_destacadas,
        hay_mas_coincidencias=hay_mas,
        generada_en=datetime.now(timezone.utc),
    )
