# cli

Punto de entrada (`python -m opssleuth.cli`) y bucle conversacional que
orquesta la recepción de incidencias, la búsqueda de evidencia en logs y la
consulta a bases de datos. Solo se documentan aquí sus dos funciones
públicas — el resto son funciones internas (prefijo `_`) que implementan
cada paso del flujo descrito en [Inicio](../index.md#que-hace-hoy).

## opssleuth.cli

::: opssleuth.cli
