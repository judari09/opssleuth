"""Fábrica de conexión a base de datos (ver contracts/database_connection.md).

Único módulo del proyecto (junto con `opssleuth.database.tools`) que puede
instanciar un `Engine` de `sqlalchemy` (Principio II de la constitución —
camino por defecto, no la excepción de "estándar de abstracción de terceros
maduro"; ver `specs/005-consultas-base-datos/research.md`, Decisión 1). Ningún
otro módulo de negocio debe importar `sqlalchemy` directamente — deben recibir
un `Engine` ya construido como parámetro.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from opssleuth.domain.database_evidence import FuenteDeBaseDeDatos

VARIABLE_ENTORNO_URL = "OPSSLEUTH_DB_URL"
"""Variable de entorno con la cadena de conexión (sin valor por defecto)."""

VARIABLE_ENTORNO_TABLAS_PERMITIDAS = "OPSSLEUTH_DB_TABLAS_PERMITIDAS"
"""Variable de entorno con las tablas permitidas, separadas por comas (sin
valor por defecto — nunca se asume "todas las tablas")."""

VARIABLE_ENTORNO_TIMEOUT = "OPSSLEUTH_DB_TIMEOUT_SEGUNDOS"
"""Variable de entorno opcional con el tiempo de espera por consulta, en
segundos (mejor esfuerzo, según lo soporte el DBAPI del dialecto)."""

TIMEOUT_POR_DEFECTO_SEGUNDOS = 10

_logger = logging.getLogger(__name__)


class TablasPermitidasNoConfiguradasError(ValueError):
    """Se lanza si `OPSSLEUTH_DB_URL` está configurada pero `OPSSLEUTH_DB_TABLAS_PERMITIDAS`
    no lo está (o está vacía).

    Fallo seguro (fail-safe) deliberado: no existe un valor por defecto
    equivalente a "todas las tablas" (ver `research.md`, Decisión 4). Esto es
    un error de configuración (falta explícita del operador) — se deja
    propagar sin capturar, igual que `ModeloOllamaNoConfiguradoError` en
    `llm/factory.py`, en vez de degradar silenciosamente.
    """


class ConexionBaseDeDatosError(Exception):
    """Se lanza si `OPSSLEUTH_DB_URL` está configurada pero la base de datos no es
    accesible al momento de construir la conexión (credenciales inválidas, host
    inaccesible, etc.).

    A diferencia de `TablasPermitidasNoConfiguradasError` (error de
    configuración, se deja propagar), este es un fallo de comunicación en
    tiempo de ejecución — el llamador (`opssleuth.cli`) DEBE capturarlo e
    informar al usuario, continuando el resto de la conversación sin
    evidencia de base de datos (US1, Escenario 3 de
    `specs/005-consultas-base-datos/spec.md`). Conserva la excepción
    original de `sqlalchemy` como `__cause__`.
    """


@dataclass
class FuenteDeBaseDeDatosConfigurada:
    """Conexión y alcance de base de datos ya construidos, listos para consultar.

    Agrupa el `Engine` de SQLAlchemy (uso interno del paquete `database/`,
    nunca expuesto a `domain/`) junto con la `FuenteDeBaseDeDatos` de dominio
    correspondiente (sin credenciales).

    Attributes
    ----------
    engine : sqlalchemy.Engine
        Conexión ya construida y lista para usar.
    fuente : FuenteDeBaseDeDatos
        Entidad de dominio asociada (motor, tablas permitidas).
    timeout_segundos : int
        Tiempo de espera por consulta a aplicar, mejor esfuerzo.
    """

    engine: sa.Engine
    fuente: FuenteDeBaseDeDatos
    timeout_segundos: int


def crear_motor_bd() -> FuenteDeBaseDeDatosConfigurada | None:
    """Crea la conexión a base de datos configurada, si la hay.

    Lee `OPSSLEUTH_DB_URL`; si no está definida, la fuente de base de datos
    simplemente no está disponible (`None`) — esto NO es un error (ver Edge
    Case de `spec.md`). Si está definida, exige `OPSSLEUTH_DB_TABLAS_PERMITIDAS`
    no vacía y verifica, contra la base de datos real, qué tablas configuradas
    existen efectivamente (las que no, se omiten con una advertencia).

    Returns
    -------
    FuenteDeBaseDeDatosConfigurada or None
        La conexión y fuente ya construidas, o `None` si `OPSSLEUTH_DB_URL`
        no está configurada.

    Raises
    ------
    TablasPermitidasNoConfiguradasError
        Si `OPSSLEUTH_DB_URL` está configurada pero
        `OPSSLEUTH_DB_TABLAS_PERMITIDAS` no lo está, está vacía, o ninguna de
        las tablas que enumera existe realmente en la base de datos.
    ConexionBaseDeDatosError
        Si `OPSSLEUTH_DB_URL` está configurada pero la base de datos no es
        accesible al intentar verificar las tablas configuradas.
    """
    url = os.environ.get(VARIABLE_ENTORNO_URL)
    if not url or not url.strip():
        return None

    tablas_configuradas = [
        tabla.strip()
        for tabla in os.environ.get(VARIABLE_ENTORNO_TABLAS_PERMITIDAS, "").split(",")
        if tabla.strip()
    ]
    if not tablas_configuradas:
        raise TablasPermitidasNoConfiguradasError(
            f"Debe configurarse la variable de entorno {VARIABLE_ENTORNO_TABLAS_PERMITIDAS} "
            f"con al menos una tabla, separadas por comas, cuando {VARIABLE_ENTORNO_URL} está "
            "configurada. No existe un valor por defecto de acceso sin restricción."
        )

    timeout_segundos = int(
        os.environ.get(VARIABLE_ENTORNO_TIMEOUT, str(TIMEOUT_POR_DEFECTO_SEGUNDOS))
    )

    engine = sa.create_engine(url.strip())
    motor = sa.engine.make_url(url.strip()).get_backend_name()

    try:
        inspector = sa.inspect(engine)
        tablas_reales = {tabla.lower(): tabla for tabla in inspector.get_table_names()}
    except SQLAlchemyError as error:
        raise ConexionBaseDeDatosError(
            "No se pudo conectar a la base de datos configurada para verificar "
            "las tablas permitidas."
        ) from error

    tablas_permitidas: list[str] = []
    for tabla in tablas_configuradas:
        nombre_real = tablas_reales.get(tabla.lower())
        if nombre_real is None:
            _logger.warning(
                "La tabla '%s' configurada en %s no existe en la base de datos; se omite.",
                tabla,
                VARIABLE_ENTORNO_TABLAS_PERMITIDAS,
            )
            continue
        tablas_permitidas.append(nombre_real)

    if not tablas_permitidas:
        raise TablasPermitidasNoConfiguradasError(
            f"Ninguna de las tablas configuradas en {VARIABLE_ENTORNO_TABLAS_PERMITIDAS} "
            "existe en la base de datos configurada."
        )

    fuente = FuenteDeBaseDeDatos(motor=motor, tablas_permitidas=tablas_permitidas)
    return FuenteDeBaseDeDatosConfigurada(
        engine=engine, fuente=fuente, timeout_segundos=timeout_segundos
    )
