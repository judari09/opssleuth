"""Validación de consultas SQL propuestas por el agente (ver contracts/database_query_engine.md).

Barandilla de seguridad central de esta funcionalidad (Historia 2, spec 005):
toda consulta se valida aquí ANTES de ejecutarse contra la base de datos real.
Este módulo (junto con `opssleuth.database.tools`) es de los pocos que pueden
importar `sqlglot` (Principio II de la constitución).
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


@dataclass
class ResultadoValidacion:
    """Resultado de validar una consulta propuesta por el agente.

    Attributes
    ----------
    es_valida : bool
        `True` si la consulta puede ejecutarse contra la base de datos real.
    motivo_rechazo : str or None
        Motivo del rechazo si `es_valida` es `False`; `None` en caso
        contrario. NUNCA incluye el nombre de una tabla no permitida ni
        detalles del esquema (FR-008 del spec) — solo indica la naturaleza
        genérica del rechazo.
    """

    es_valida: bool
    motivo_rechazo: str | None = None


def _nombres_tablas_referenciadas(consulta: exp.Expression) -> set[str]:
    """Extrae los nombres de tabla realmente referenciados por `consulta`.

    Excluye los alias de CTE (`WITH x AS (...)`) del resultado — `sqlglot`
    los expone como `exp.Table` en la cláusula `FROM`/`JOIN` que los usa,
    pero no son tablas reales de la base de datos; las tablas referenciadas
    *dentro* de la CTE sí se incluyen (se recorren igual que el resto de la
    consulta). Los nombres se normalizan a minúsculas y se ignora cualquier
    esquema/base de datos que los califique (Principio IV: los operadores
    configuran `OPSSLEUTH_DB_TABLAS_PERMITIDAS` con nombres de tabla simples,
    sin prefijo de esquema — ver `quickstart.md`).

    Parameters
    ----------
    consulta : sqlglot.exp.Expression
        Consulta ya parseada.

    Returns
    -------
    set of str
        Nombres de tabla referenciados, en minúsculas, sin alias de CTE.
    """
    alias_cte = {cte.alias_or_name.lower() for cte in consulta.find_all(exp.CTE)}
    return {
        tabla.name.lower()
        for tabla in consulta.find_all(exp.Table)
        if tabla.name.lower() not in alias_cte
    }


def validar_consulta(consulta: str, tablas_permitidas: list[str]) -> ResultadoValidacion:
    """Valida que `consulta` sea segura de ejecutar contra la base de datos real.

    Dos condiciones, ambas obligatorias (Reglas 2-3 de
    `contracts/database_query_engine.md`):

    1. `consulta` DEBE parsear como una única sentencia `SELECT` — se
       rechaza cualquier texto con más de una sentencia (separadas por
       `;`), o cuya raíz no sea `SELECT` (p. ej. `INSERT`/`UPDATE`/`DELETE`/
       `CREATE`/`ALTER`/`DROP`/etc., o texto que no parsea como SQL válido).
    2. Toda tabla referenciada (excluidos los alias de CTE) DEBE estar en
       `tablas_permitidas` (comparación insensible a mayúsculas/minúsculas y
       a la calificación de esquema — ver `_nombres_tablas_referenciadas`).

    Parameters
    ----------
    consulta : str
        Texto SQL propuesto por el agente.
    tablas_permitidas : list of str
        Tablas a las que esta consulta puede acceder.

    Returns
    -------
    ResultadoValidacion
        `es_valida=True` si `consulta` cumple ambas condiciones; en caso
        contrario, `es_valida=False` con un `motivo_rechazo` genérico que
        nunca revela qué tabla concreta causó el rechazo.
    """
    try:
        sentencias = sqlglot.parse(consulta)
    except Exception:
        return ResultadoValidacion(
            es_valida=False, motivo_rechazo="La consulta no es SQL válido."
        )

    sentencias = [s for s in sentencias if s is not None]
    if len(sentencias) != 1:
        return ResultadoValidacion(
            es_valida=False,
            motivo_rechazo="Solo se permite una única sentencia SQL por consulta.",
        )

    sentencia = sentencias[0]
    if not isinstance(sentencia, exp.Select):
        return ResultadoValidacion(
            es_valida=False, motivo_rechazo="Solo se permiten sentencias SELECT de solo lectura."
        )

    permitidas_normalizadas = {tabla.lower() for tabla in tablas_permitidas}
    referenciadas = _nombres_tablas_referenciadas(sentencia)
    if not referenciadas.issubset(permitidas_normalizadas):
        return ResultadoValidacion(
            es_valida=False,
            motivo_rechazo=(
                "La consulta referencia una o más tablas fuera del alcance permitido."
            ),
        )

    return ResultadoValidacion(es_valida=True)
