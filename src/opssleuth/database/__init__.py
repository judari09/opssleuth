"""Motor de consulta a base de datos de OpsSleuth (ver spec 005).

Único paquete del proyecto que puede importar `sqlalchemy`/`sqlglot`
(Principio II de la constitución — camino por defecto, no la excepción de
"estándar de abstracción de terceros maduro"; ver
`specs/005-consultas-base-datos/research.md`, Decisión 1). Ningún otro módulo
debe importar esos paquetes directamente.
"""

from __future__ import annotations
