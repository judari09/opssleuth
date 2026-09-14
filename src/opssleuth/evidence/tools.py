"""Herramientas de búsqueda de logs para el agente (ver contracts/log_search_engine.md).

Este módulo no depende de ningún SDK de proveedor de modelo ni de LangChain más
allá del decorador `@tool` (que solo describe el esquema de la herramienta, sin
acoplar la lógica de negocio a un proveedor concreto). Cada herramienta se
construye mediante una función de fábrica que captura por cierre (closure) el
recurso al que está ligada (la ruta de archivo activa, o el callback de
pregunta al usuario) — así el esquema que ve el modelo nunca incluye ese
recurso como parámetro (Regla 4 del contrato: `preguntar_al_usuario` nunca
accede directamente a stdin/stdout).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from langchain.tools import tool

MAXIMO_RESULTADOS_POR_DEFECTO = 20
LINEAS_DE_CONTEXTO_POR_DEFECTO = 2


def _leer_lineas(ruta_archivo: str) -> list[str]:
    """Lee todas las líneas de `ruta_archivo` (sin el terminador de línea).

    Se relee el archivo en cada llamada en vez de mantenerlo cacheado en
    memoria entre llamadas: simplifica la implementación (Principio IV) y el
    costo es aceptable para archivos de logs típicos — la restricción de no
    cargar el archivo completo (ver plan.md, Performance Goals) es sobre lo que
    se envía al **contexto del modelo**, no sobre la memoria del propio proceso
    que ejecuta la herramienta.

    Parameters
    ----------
    ruta_archivo : str
        Ruta absoluta al archivo de logs.

    Returns
    -------
    list of str
        Líneas del archivo, sin el terminador de línea.
    """
    with open(ruta_archivo, encoding="utf-8", errors="replace") as archivo:
        return [linea.rstrip("\n") for linea in archivo]


def crear_herramientas_busqueda(ruta_archivo: str) -> list:
    """Crea las herramientas `buscar_texto`, `leer_contexto` y `contar_lineas`.

    Ligadas por cierre a `ruta_archivo` — el modelo nunca ve esta ruta como
    parámetro de la herramienta.

    Parameters
    ----------
    ruta_archivo : str
        Ruta absoluta a la fuente de logs activa.

    Returns
    -------
    list
        Las 3 herramientas decoradas con `@tool`, listas para enlazar al agente.
    """

    @tool
    def buscar_texto(patron: str, maximo_resultados: int = MAXIMO_RESULTADOS_POR_DEFECTO) -> str:
        """Busca un patrón de expresión regular en la fuente de logs activa.

        Usar para localizar líneas que mencionen un término, componente,
        código de error o patrón de fecha/hora específico, sin leer el archivo
        completo. Devuelve hasta `maximo_resultados` coincidencias, cada una
        con su número de línea, el contenido de la línea y una pequeña ventana
        de contexto inmediatamente antes/después. Si hay más coincidencias de
        las devueltas, el resultado lo indica explícitamente (campo
        `hay_mas`) en vez de omitirlo silenciosamente.

        Args:
            patron: Expresión regular a buscar en cada línea de la fuente activa.
            maximo_resultados: Número máximo de coincidencias a devolver en esta llamada.
        """
        lineas = _leer_lineas(ruta_archivo)
        try:
            regex = re.compile(patron)
        except re.error as error:
            return json.dumps({"error": f"Patrón de expresión regular inválido: {error}"})

        coincidencias = []
        total_coincidencias = 0
        for indice, linea in enumerate(lineas):
            if not regex.search(linea):
                continue
            total_coincidencias += 1
            if len(coincidencias) >= maximo_resultados:
                continue
            inicio = max(0, indice - LINEAS_DE_CONTEXTO_POR_DEFECTO)
            fin = min(len(lineas), indice + LINEAS_DE_CONTEXTO_POR_DEFECTO + 1)
            coincidencias.append(
                {
                    "numero_linea": indice + 1,
                    "contenido": linea,
                    "contexto": lineas[inicio:fin],
                }
            )
        return json.dumps(
            {"coincidencias": coincidencias, "hay_mas": total_coincidencias > len(coincidencias)},
            ensure_ascii=False,
        )

    @tool
    def leer_contexto(numero_linea: int, lineas_antes: int = 5, lineas_despues: int = 5) -> str:
        """Lee las líneas alrededor de un número de línea específico.

        Usar después de `buscar_texto`, cuando la ventana de contexto por
        defecto de una coincidencia no basta para entender la secuencia de
        eventos alrededor de esa línea.

        Args:
            numero_linea: Número de línea (1-indexado) alrededor del cual leer contexto.
            lineas_antes: Cantidad de líneas a incluir antes de `numero_linea`.
            lineas_despues: Cantidad de líneas a incluir después de `numero_linea`.
        """
        lineas = _leer_lineas(ruta_archivo)
        inicio = max(0, (numero_linea - 1) - lineas_antes)
        fin = min(len(lineas), numero_linea + lineas_despues)
        resultado = [
            {"numero_linea": indice + 1, "contenido": lineas[indice]}
            for indice in range(inicio, fin)
        ]
        return json.dumps({"lineas": resultado}, ensure_ascii=False)

    @tool
    def contar_lineas() -> str:
        """Cuenta el número total de líneas de la fuente de logs activa.

        Usar al iniciar el análisis de una fuente, para calibrar si es un
        archivo pequeño (inspeccionable casi por completo) o grande (requiere
        búsqueda dirigida con `buscar_texto`).
        """
        return json.dumps({"total_lineas": len(_leer_lineas(ruta_archivo))})

    return [buscar_texto, leer_contexto, contar_lineas]


def crear_herramienta_preguntar(preguntar_callback: Callable[[str], str]):
    """Crea la herramienta `preguntar_al_usuario`, ligada a `preguntar_callback`.

    Parameters
    ----------
    preguntar_callback : Callable[[str], str]
        Función que recibe la pregunta como texto y devuelve la respuesta del
        usuario (implementada por la CLI — ver `contracts/log_search_engine.md`,
        Regla 4).

    Returns
    -------
    BaseTool
        La herramienta `preguntar_al_usuario` decorada con `@tool`.
    """

    @tool
    def preguntar_al_usuario(pregunta: str) -> str:
        """Pausa el análisis y pregunta al usuario por contexto del proyecto.

        Usar ÚNICAMENTE cuando el contenido de los logs o del problema
        descrito no puede interpretarse sin conocer más sobre el proyecto o
        sistema al que pertenecen (terminología propia, nombres de
        componentes o convenciones de formato desconocidas). No usar cuando
        el contenido ya es interpretable por sí mismo, ni para preguntas que
        una búsqueda adicional en los propios logs podría responder.

        Args:
            pregunta: Pregunta concreta a formular al usuario, en español.
        """
        return preguntar_callback(pregunta)

    return preguntar_al_usuario
