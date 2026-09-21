"""Capa de presentación de la CLI de OpsSleuth.

Único paquete del proyecto que puede importar `rich` (Principio II de la
constitución). Ningún otro módulo debe importar `rich` directamente — deben
usar las funciones expuestas por `opssleuth.presentation.console`.
"""

from __future__ import annotations
