"""Selección del proveedor de motor de aclaración configurado.

Único módulo del sistema que importa las dos implementaciones concretas de
`ClarificationEngine` (`claude_engine.py`, `ollama_engine.py`) — todo lo demás
depende únicamente del contrato en `engine.py` (Principio II de la constitución).
"""

from __future__ import annotations

import os

from opssleuth.clarification.claude_engine import ClaudeClarificationEngine
from opssleuth.clarification.engine import ClarificationEngine
from opssleuth.clarification.ollama_engine import OllamaClarificationEngine

VARIABLE_ENTORNO_PROVEEDOR = "OPSSLEUTH_LLM_PROVIDER"
"""Variable de entorno que selecciona el proveedor: ``"claude"`` u ``"ollama"``."""

PROVEEDOR_POR_DEFECTO = "claude"


class ProveedorDesconocidoError(ValueError):
    """Se lanza cuando `VARIABLE_ENTORNO_PROVEEDOR` tiene un valor no reconocido."""


def crear_motor_aclaracion() -> ClarificationEngine:
    """Crea la implementación de `ClarificationEngine` según la configuración.

    Lee la variable de entorno `VARIABLE_ENTORNO_PROVEEDOR`
    (``OPSSLEUTH_LLM_PROVIDER``, por defecto `PROVEEDOR_POR_DEFECTO`) y devuelve
    la implementación correspondiente.

    Returns
    -------
    ClarificationEngine
        `ClaudeClarificationEngine` si el proveedor configurado es ``"claude"``,
        o `OllamaClarificationEngine` si es ``"ollama"``.

    Raises
    ------
    ProveedorDesconocidoError
        Si la variable de entorno tiene un valor distinto de ``"claude"`` u
        ``"ollama"``.
    """
    proveedor = os.environ.get(VARIABLE_ENTORNO_PROVEEDOR, PROVEEDOR_POR_DEFECTO).strip().lower()
    if proveedor == "claude":
        return ClaudeClarificationEngine()
    if proveedor == "ollama":
        return OllamaClarificationEngine()
    raise ProveedorDesconocidoError(
        f"Proveedor desconocido en {VARIABLE_ENTORNO_PROVEEDOR}: {proveedor!r}. "
        'Valores admitidos: "claude", "ollama".'
    )
