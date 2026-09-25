"""Herramientas de consulta a base de datos para el agente (ver contracts/database_query_engine.md).

Este módulo (junto con `opssleuth.database.validacion`) es de los pocos que
pueden importar `sqlalchemy`/`sqlglot` directamente (Principio II de la
constitución). Cada herramienta se construye mediante una función de fábrica
que captura por cierre (closure) el recurso al que está ligada (el `Engine` y
la fuente configurada) — así el esquema que ve el modelo nunca incluye ese
recurso como parámetro.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
import sqlglot
from langchain.tools import tool
from sqlalchemy.exc import SQLAlchemyError

from opssleuth.database.factory import FuenteDeBaseDeDatosConfigurada
from opssleuth.database.validacion import validar_consulta

MAXIMO_FILAS_POR_DEFECTO = 20
"""Límite de filas devueltas por `ejecutar_consulta_sql` en una sola llamada."""

_DIALECTOS_SQLALCHEMY_A_SQLGLOT = {
    "postgresql": "postgres",
    "mssql": "tsql",
}
"""Traduce nombres de dialecto de SQLAlchemy a los que reconoce `sqlglot`
(difieren para algunos motores, p. ej. `"postgresql"` vs. `"postgres"`)."""


def _dialecto_sqlglot(nombre_sqlalchemy: str) -> str:
    """Traduce el nombre de dialecto de SQLAlchemy al equivalente de `sqlglot`.

    Parameters
    ----------
    nombre_sqlalchemy : str
        `Engine.dialect.name` (p. ej. ``"sqlite"``, ``"postgresql"``).

    Returns
    -------
    str
        Nombre de dialecto reconocido por `sqlglot`; si no hay traducción
        conocida, se devuelve `nombre_sqlalchemy` tal cual (varios coinciden,
        p. ej. ``"sqlite"``, ``"mysql"``).
    """
    return _DIALECTOS_SQLALCHEMY_A_SQLGLOT.get(nombre_sqlalchemy, nombre_sqlalchemy)


def _texto_con_limite_acotado(consulta: str, sentencia, limite: int, dialecto: str) -> str:
    """Devuelve el texto SQL a ejecutar, con la cláusula `LIMIT` acotada a `limite`.

    Nunca aumenta un `LIMIT` ya presente si es menor o igual que `limite` —
    respeta la intención del agente de pedir menos filas (`research.md`,
    Decisión 5). Cuando no hace falta reescribir nada, devuelve `consulta`
    (el texto original, sin pasar por el generador de SQL de `sqlglot`) en
    vez de regenerarlo innecesariamente.

    Parameters
    ----------
    consulta : str
        Texto SQL original, ya validado.
    sentencia : sqlglot.exp.Select
        `consulta` ya parseada.
    limite : int
        Límite superior de filas a aplicar.
    dialecto : str
        Dialecto de `sqlglot` a usar al regenerar el texto, si hace falta.

    Returns
    -------
    str
        Texto SQL a ejecutar.
    """
    limit_existente = sentencia.args.get("limit")
    if limit_existente is not None:
        try:
            valor_existente = int(limit_existente.expression.this)
        except (AttributeError, TypeError, ValueError):
            valor_existente = None
        if valor_existente is not None and valor_existente <= limite:
            return consulta
    try:
        return sentencia.limit(limite).sql(dialect=dialecto)
    except Exception:
        # Mejor esfuerzo: si el dialecto no es reconocido por sqlglot o la
        # regeneración falla, se usa el dialecto genérico de sqlglot en vez
        # de dejar la consulta sin acotar.
        return sentencia.limit(limite).sql()


def crear_herramientas_bd(fuente: FuenteDeBaseDeDatosConfigurada) -> list:
    """Crea las herramientas `listar_tablas_disponibles`, `describir_tabla` y `ejecutar_consulta_sql`.

    Ligadas por cierre a `fuente` — el modelo nunca ve el `Engine` ni la lista
    de tablas permitidas como parámetro de herramienta.

    Parameters
    ----------
    fuente : FuenteDeBaseDeDatosConfigurada
        Conexión y alcance de tablas ya construidos (ver
        `opssleuth.database.factory.crear_motor_bd`).

    Returns
    -------
    list
        Las 3 herramientas decoradas con `@tool`, listas para enlazar al agente.
    """
    engine = fuente.engine
    tablas_permitidas = fuente.fuente.tablas_permitidas
    timeout_segundos = fuente.timeout_segundos

    @tool
    def listar_tablas_disponibles() -> str:
        """Devuelve los nombres de las tablas a las que esta consulta tiene acceso.

        Usar al iniciar el análisis, para saber con qué tablas se puede
        trabajar sin necesidad de adivinar o asumir nombres.
        """
        return json.dumps({"tablas": tablas_permitidas}, ensure_ascii=False)

    @tool
    def describir_tabla(tabla: str) -> str:
        """Devuelve las columnas (nombre y tipo) de una tabla permitida.

        Usar antes de construir una consulta (simple o con cruces entre
        varias tablas) que referencie esa tabla, para conocer sus columnas
        reales. Rechaza la solicitud si `tabla` no está dentro del conjunto
        de tablas permitidas.

        Args:
            tabla: Nombre de la tabla permitida a describir.
        """
        if tabla.lower() not in {t.lower() for t in tablas_permitidas}:
            return json.dumps(
                {"error": "Esa tabla no está dentro del alcance permitido."}, ensure_ascii=False
            )
        inspector = sa.inspect(engine)
        columnas = [
            {"nombre": columna["name"], "tipo": str(columna["type"])}
            for columna in inspector.get_columns(tabla)
        ]
        return json.dumps({"columnas": columnas}, ensure_ascii=False)

    @tool
    def ejecutar_consulta_sql(consulta: str) -> str:
        """Valida y ejecuta una consulta de solo lectura contra la base de datos configurada.

        Usar para obtener filas concretas relacionadas con el incidente —
        consultas simples de una sola tabla, o consultas complejas con
        cruces (joins) entre más de dos tablas, según lo requiera el
        diagnóstico. La consulta se rechaza sin ejecutarse si no es una
        única sentencia SELECT, o si referencia alguna tabla fuera del
        conjunto permitido. El volumen de filas devuelto está acotado — si
        hay más resultados de los devueltos, la respuesta lo indica
        explícitamente en vez de omitirlo.

        Args:
            consulta: Texto SQL de una única sentencia SELECT de solo lectura.
        """
        resultado_validacion = validar_consulta(consulta, tablas_permitidas)
        if not resultado_validacion.es_valida:
            return json.dumps({"error": resultado_validacion.motivo_rechazo}, ensure_ascii=False)

        sql_final = _texto_con_limite_acotado(
            consulta,
            sqlglot.parse_one(consulta),
            MAXIMO_FILAS_POR_DEFECTO + 1,
            _dialecto_sqlglot(engine.dialect.name),
        )

        try:
            with engine.connect() as conexion:
                conexion = conexion.execution_options(timeout=timeout_segundos)
                try:
                    conexion.execute(sa.text("SET TRANSACTION READ ONLY"))
                except SQLAlchemyError:
                    pass  # mejor esfuerzo: no todo dialecto soporta esta sentencia
                resultado = conexion.execute(sa.text(sql_final))
                columnas = list(resultado.keys())
                filas_crudas = resultado.fetchmany(MAXIMO_FILAS_POR_DEFECTO + 1)
                # conexión se descarta al salir del `with` (rollback implícito);
                # nunca se llama a `commit()` sobre ella.
        except SQLAlchemyError as error:
            return json.dumps(
                {"error": f"No se pudo ejecutar la consulta: {error}"}, ensure_ascii=False
            )

        hay_mas = len(filas_crudas) > MAXIMO_FILAS_POR_DEFECTO
        filas = [dict(zip(columnas, fila)) for fila in filas_crudas[:MAXIMO_FILAS_POR_DEFECTO]]
        return json.dumps(
            {"filas": filas, "hay_mas": hay_mas, "consulta_ejecutada": consulta},
            ensure_ascii=False,
            default=str,
        )

    return [listar_tablas_disponibles, describir_tabla, ejecutar_consulta_sql]
