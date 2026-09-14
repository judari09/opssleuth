"""Entidades de dominio para la evidencia de logs (ver data-model.md).

Este módulo no depende de ningún SDK de proveedor de modelo ni de LangChain
(Principio II de la constitución): las entidades aquí definidas son puro estado
y reglas de negocio, consumidas tanto por la CLI como por el motor de búsqueda
de logs (`opssleuth.evidence`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

OrigenFuente = Literal["ruta_usuario", "contenido_pegado"]


@dataclass
class FuenteDeLogs:
    """Origen de los logs a analizar en un caso.

    Attributes
    ----------
    ruta : str
        Ruta absoluta al archivo de logs (indicada por el usuario, o generada a
        partir de contenido pegado — ver `origen`).
    origen : {"ruta_usuario", "contenido_pegado"}
        Si la ruta fue indicada directamente por el usuario o generada por el
        sistema a partir de contenido pegado en el chat (FR-003/FR-015).
    aportada_en : datetime
        Momento en que se registró esta fuente para el caso.

    Raises
    ------
    ValueError
        Si `ruta` está vacía o contiene solo espacios en blanco.
    """

    ruta: str
    origen: OrigenFuente
    aportada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Valida `ruta` tras la construcción (ver Raises en el docstring de la clase)."""
        if not self.ruta or not self.ruta.strip():
            raise ValueError("La ruta de la fuente de logs no puede estar vacía.")


@dataclass
class EntradaLogRelevante:
    """Línea o fragmento de log identificado como relacionado con el incidente.

    Toda instancia DEBE originarse en el resultado real de una llamada a una
    herramienta de búsqueda (`buscar_texto`/`leer_contexto`) — nunca en texto
    libre generado por el modelo (ver research.md, Decisión 6).

    Attributes
    ----------
    fuente : FuenteDeLogs
        Fuente de la que proviene esta entrada.
    numero_linea : int
        Número de línea (1-indexado) dentro de la fuente.
    contenido : str
        Texto de la línea tal como se leyó del archivo.
    marca_de_tiempo : str or None
        Marca de tiempo tal como aparece en el log, si es identificable; None
        en caso contrario.

    Raises
    ------
    ValueError
        Si `numero_linea` es menor que 1.
    """

    fuente: FuenteDeLogs
    numero_linea: int
    contenido: str
    marca_de_tiempo: str | None = None

    def __post_init__(self) -> None:
        """Valida `numero_linea` tras la construcción (ver Raises en el docstring de la clase)."""
        if self.numero_linea < 1:
            raise ValueError("numero_linea debe ser >= 1.")


@dataclass
class ApreciacionInicialLogs:
    """Resumen único por caso, consolidado entre todas las fuentes de logs aportadas.

    Attributes
    ----------
    resumen : str
        Texto de la apreciación inicial. Si no se encontró ninguna entrada
        relevante, lo refleja explícitamente (FR-008, SC-003) — nunca una
        conclusión fabricada.
    entradas_destacadas : list of EntradaLogRelevante
        Conjunto acotado de entradas representativas (FR-009a), consolidado
        entre todas las fuentes (FR-010a).
    hay_mas_coincidencias : bool
        True cuando el volumen real de coincidencias supera el límite aplicado
        a `entradas_destacadas` (FR-009a).
    generada_en : datetime
        Momento en que se produjo la apreciación.
    """

    resumen: str
    entradas_destacadas: list[EntradaLogRelevante] = field(default_factory=list)
    hay_mas_coincidencias: bool = False
    generada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
