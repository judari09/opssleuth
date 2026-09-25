"""Entidades de dominio para la evidencia de base de datos (ver data-model.md).

Este módulo no depende de `sqlalchemy`/`sqlglot` ni de ningún SDK de proveedor
de modelo (Principio II de la constitución): las entidades aquí definidas son
puro estado y reglas de negocio, consumidas tanto por la CLI como por el motor
de consulta a base de datos (`opssleuth.database`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FuenteDeBaseDeDatos:
    """Fuente de base de datos configurada y disponible para un caso.

    NUNCA contiene la cadena de conexión ni credenciales — esas viven
    únicamente dentro del `Engine` de SQLAlchemy construido por
    `opssleuth.database.factory.crear_motor_bd`, inyectado como parámetro allí
    donde se necesite, nunca serializado en esta entidad de dominio (ver
    `data-model.md`).

    Attributes
    ----------
    motor : str
        Nombre del motor de base de datos configurado (p. ej. ``"sqlite"``,
        ``"postgresql"``), derivado del esquema de `OPSSLEUTH_DB_URL` — solo
        para mostrar al usuario de forma segura, nunca la URL completa.
    tablas_permitidas : list of str
        Conjunto de tablas a las que esta fuente puede acceder (FR-003) —
        subconjunto de `OPSSLEUTH_DB_TABLAS_PERMITIDAS` que además existe
        realmente en la base de datos.
    aportada_en : datetime
        Momento en que se registró esta fuente como disponible para el caso.

    Raises
    ------
    ValueError
        Si `motor` está vacío, o si `tablas_permitidas` está vacía.
    """

    motor: str
    tablas_permitidas: list[str]
    aportada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Valida `motor`/`tablas_permitidas` tras la construcción (ver Raises)."""
        if not self.motor or not self.motor.strip():
            raise ValueError("El motor de la fuente de base de datos no puede estar vacío.")
        if not self.tablas_permitidas:
            raise ValueError(
                "La fuente de base de datos debe tener al menos una tabla permitida."
            )


@dataclass
class EntradaBDRelevante:
    """Fila de resultado identificada como relacionada con el incidente.

    Toda instancia DEBE originarse en el resultado real de una llamada a la
    herramienta `ejecutar_consulta_sql` — nunca en texto libre generado por el
    modelo (FR-010 del spec, mismo principio que `EntradaLogRelevante`).

    Attributes
    ----------
    fuente : FuenteDeBaseDeDatos
        Fuente de la que proviene esta entrada.
    consulta : str
        Texto de la consulta SQL realmente ejecutada que produjo esta fila —
        conservado para trazabilidad/auditoría.
    fila : dict of str to object
        Los valores de la fila, como mapa columna → valor, tal como los
        devolvió la base de datos.

    Raises
    ------
    ValueError
        Si `consulta` está vacía o contiene solo espacios en blanco.
    """

    fuente: FuenteDeBaseDeDatos
    consulta: str
    fila: dict[str, object]

    def __post_init__(self) -> None:
        """Valida `consulta` tras la construcción (ver Raises en el docstring de la clase)."""
        if not self.consulta or not self.consulta.strip():
            raise ValueError("La consulta de una EntradaBDRelevante no puede estar vacía.")


@dataclass
class ApreciacionInicialBD:
    """Resumen único por caso, consolidado entre todas las fuentes de base de datos consultadas.

    Misma forma que `ApreciacionInicialLogs` (spec 002), para que ambas
    apreciaciones se presenten de manera consistente al usuario (FR-009).

    Attributes
    ----------
    resumen : str
        Texto de la apreciación elaborada a partir de las filas encontradas,
        relacionándolas con el incidente descrito. Si no se encontró ninguna
        fila relevante, o no había ninguna fuente configurada, lo refleja
        explícitamente — nunca una conclusión fabricada.
    entradas_destacadas : list of EntradaBDRelevante
        Conjunto acotado de filas representativas (FR-006), consolidado entre
        todas las fuentes consultadas.
    hay_mas_resultados : bool
        `True` cuando el volumen real de resultados de alguna consulta superó
        el límite aplicado (FR-006).
    generada_en : datetime
        Momento en que se produjo la apreciación.
    """

    resumen: str
    entradas_destacadas: list[EntradaBDRelevante] = field(default_factory=list)
    hay_mas_resultados: bool = False
    generada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
