"""Renderizado de la conversación de la CLI (ver spec 004, `research.md`).

Único módulo del proyecto que importa `rich` (Principio II de la constitución
— excepción no aplicable aquí, ver `research.md`, Decisión 1: se sigue el
camino por defecto del principio, confinando la dependencia detrás de esta
capa propia, no adoptando el tipo de `rich` como mecanismo de
intercambiabilidad del proyecto). Ningún otro módulo debe importar `rich`
directamente.
"""

from __future__ import annotations

import sys
from contextlib import AbstractContextManager

from rich.console import Console
from rich.markdown import Markdown

ETIQUETA_SISTEMA = "OpsSleuth"
"""Etiqueta textual de rol para los mensajes del sistema (FR-002)."""

ETIQUETA_USUARIO = "Tú"
"""Etiqueta textual de rol para las entradas del usuario (FR-001)."""

ESTILO_SISTEMA = "bold cyan"
"""Estilo/color que refuerza `ETIQUETA_SISTEMA` — nunca el único mecanismo de
diferenciación (la etiqueta textual es obligatoria, ver Clarifications de
`spec.md`, Sesión 2026-09-16)."""

ESTILO_USUARIO = "bold green"
"""Estilo/color que refuerza `ETIQUETA_USUARIO`, distinto de `ESTILO_SISTEMA`."""

ESTILO_ERROR = "bold red"
"""Estilo/color para mensajes de error o advertencia (FR-005), distinto de
`ESTILO_SISTEMA`."""

BANNER_OPSSLEUTH = r"""
 ██████╗ ██████╗ ███████╗███████╗██╗     ███████╗██╗   ██╗████████╗██╗  ██╗
██╔═══██╗██╔══██╗██╔════╝██╔════╝██║     ██╔════╝██║   ██║╚══██╔══╝██║  ██║
██║   ██║██████╔╝███████╗███████╗██║     █████╗  ██║   ██║   ██║   ███████║
██║   ██║██╔═══╝ ╚════██║╚════██║██║     ██╔══╝  ██║   ██║   ██║   ██╔══██║
╚██████╔╝██║     ███████║███████║███████╗███████╗╚██████╔╝   ██║   ██║  ██║
 ╚═════╝ ╚═╝     ╚══════╝╚══════╝╚══════╝╚══════╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝
"""
"""Banner de bienvenida mostrado una vez al iniciar la CLI (`main()`)."""

BANNER_OPSSLEUTH_ASCII = r"""
  ___              _____ _            _   _
 / _ \ _ __  ___  / ____| | ___ _   _| |_| |__
| | | | '_ \/ __| \___ \| |/ _ \ | | | __| '_ \
| |_| | |_) \__ \ ____) | |  __/ |_| | |_| | | |
 \___/| .__/|___/|_____/|_|\___|\__,_|\__|_| |_|
      |_|
"""
"""Alternativa de `BANNER_OPSSLEUTH` compuesta solo de caracteres ASCII, usada
como respaldo cuando la terminal no puede representar los caracteres de
dibujo de caja del banner principal (ver `mostrar_banner`)."""


def _forzar_utf8_en_flujos_estandar() -> None:
    """Reconfigura `sys.stdout`/`sys.stderr` a UTF-8 antes de construir `_console`.

    En algunas consolas Windows, `sys.stdout.encoding` resuelve a la página
    de códigos del sistema (p. ej. `cp1252`) en vez de UTF-8 — cualquier
    carácter fuera de ese repertorio (acentos, caracteres de dibujo de
    caja/bloque del banner, etc.) hace fallar la escritura con
    `UnicodeEncodeError`, e interrumpe la aplicación (verificado
    empíricamente). Peor aún: una vez que la escritura subyacente de `rich`
    falla una vez sobre una instancia de `Console`, esa instancia queda en un
    estado interno inconsistente que hace fallar también los mensajes
    siguientes — por eso este resguardo actúa antes de construir `_console`,
    no reactivamente en cada llamada (FR-006 de spec 004: la app nunca debe
    interrumpirse por esto). `errors="replace"` es una defensa adicional:
    UTF-8 ya puede codificar cualquier carácter Unicode, así que en la
    práctica no debería activarse.

    Sin efecto si `sys.stdout`/`sys.stderr` no exponen `.reconfigure()` (p.
    ej. algunos entornos de prueba que sustituyen estos flujos) — se ignora
    en silencio en vez de fallar la importación de este módulo.
    """
    for flujo in (sys.stdout, sys.stderr):
        reconfigure = getattr(flujo, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


_forzar_utf8_en_flujos_estandar()

_console = Console()
"""Instancia de `Console` usada por defecto cuando no se inyecta una — detecta
automáticamente la capacidad de color/formato de la terminal de destino
(FR-006)."""


def mostrar_mensaje_sistema(
    texto: str, *, es_error: bool = False, console: Console | None = None
) -> None:
    """Muestra un mensaje del sistema con su etiqueta textual de rol (FR-002).

    La etiqueta (`ETIQUETA_SISTEMA`) se imprime siempre como texto, reforzada
    con color/estilo — nunca depende únicamente del color (FR-001/FR-002,
    Clarifications de `spec.md`). El contenido de `texto` se renderiza como
    Markdown (listas, énfasis, encabezados) en vez de como texto plano con
    marcado sin procesar (FR-003, `research.md` Decisión 4).

    Parameters
    ----------
    texto : str
        Contenido del mensaje a mostrar.
    es_error : bool, optional
        Si `True`, aplica `ESTILO_ERROR` a la etiqueta en vez de
        `ESTILO_SISTEMA`, distinguiendo visualmente un fallo o advertencia de
        una respuesta normal (FR-005). `False` por defecto.
    console : rich.console.Console or None, optional
        Instancia de `Console` a usar; si no se aporta, se usa la instancia de
        módulo por defecto. Permite inyectar un `Console` en memoria en
        pruebas (`research.md`, Decisión 7).
    """
    c = console or _console
    estilo = ESTILO_ERROR if es_error else ESTILO_SISTEMA
    c.print(f"[{estilo}]{ETIQUETA_SISTEMA}:[/{estilo}]")
    c.print(Markdown(texto))


def leer_entrada_usuario(prompt: str = "", *, console: Console | None = None) -> str:
    """Muestra `prompt` (si lo hay) y lee una línea de entrada del usuario (FR-001).

    Si `prompt` no está vacío, se muestra primero vía `mostrar_mensaje_sistema`
    — unifica el patrón ya existente en `cli.py`, donde la pregunta del
    sistema se pasaba como argumento de `_leer_entrada`. A continuación se
    muestra la etiqueta textual de rol del usuario (`ETIQUETA_USUARIO`,
    reforzada con `ESTILO_USUARIO`) y se lee la línea con `input()` estándar
    — no `Console.input`, para preservar exactamente el valor devuelto por el
    mecanismo ya probado (`research.md`, Decisión 2).

    Parameters
    ----------
    prompt : str, optional
        Mensaje del sistema a mostrar antes de leer la entrada. Cadena vacía
        (por defecto) cuando no hay nada que mostrar — p. ej. al leer líneas
        sucesivas de contenido pegado.
    console : rich.console.Console or None, optional
        Instancia de `Console` a usar; si no se aporta, se usa la instancia de
        módulo por defecto.

    Returns
    -------
    str
        Texto escrito por el usuario, exactamente como lo devuelve `input()`.
    """
    c = console or _console
    if prompt:
        mostrar_mensaje_sistema(prompt, console=c)
    c.print(f"[{ESTILO_USUARIO}]{ETIQUETA_USUARIO}:[/{ESTILO_USUARIO}]", end=" ")
    return input()


def mostrar_actividad(
    mensaje: str, *, console: Console | None = None
) -> AbstractContextManager[object]:
    """Indica visualmente actividad mientras se ejecuta un bloque `with` (FR-004).

    Envuelve `rich.console.Console.status`: muestra `mensaje` junto con un
    indicador transitorio mientras el bloque `with` se ejecuta, y lo limpia
    automáticamente al salir. Pensado para las llamadas al proveedor de
    modelo subyacente, que ya toman varios segundos en uso real
    (`research.md`, Decisión 5).

    Parameters
    ----------
    mensaje : str
        Texto a mostrar junto al indicador de actividad.
    console : rich.console.Console or None, optional
        Instancia de `Console` a usar; si no se aporta, se usa la instancia de
        módulo por defecto.

    Returns
    -------
    AbstractContextManager
        Gestor de contexto de `rich` (`Status`) — úsese con `with`.
    """
    c = console or _console
    return c.status(mensaje)


def mostrar_banner(texto: str = BANNER_OPSSLEUTH, *, console: Console | None = None) -> None:
    """Muestra un banner de bienvenida como texto literal (p. ej. arte ASCII).

    A diferencia de `mostrar_mensaje_sistema`, NO añade la etiqueta de rol del
    sistema ni renderiza `texto` como Markdown — un banner es contenido
    decorativo de arranque, no un mensaje conversacional. Se imprime con
    `no_wrap=True`/`overflow="crop"`: si `texto` excede el ancho de la
    terminal, se recorta en vez de reflowearse — el reflujo de párrafo (el
    comportamiento por defecto de `Console.print`) rompería la alineación de
    un arte ASCII con caracteres de dibujo de caja, mucho peor visualmente
    que un recorte.

    Si `texto` usa caracteres (p. ej. de dibujo de caja/bloque) que la
    terminal de destino no puede codificar — algunas consolas Windows sin
    soporte VT moderno caen en una ruta de renderizado que codifica con la
    página de códigos del sistema (p. ej. cp1252), incapaz de representarlos,
    y sin este resguardo la app entera se interrumpiría con un
    `UnicodeEncodeError` — se reintenta con `BANNER_OPSSLEUTH_ASCII` (o, si
    se pasó explícitamente otro `texto`, con su versión ASCII vía
    `.encode("ascii", "replace").decode("ascii")`) en vez de fallar. Nunca
    debe interrumpir el arranque de la aplicación (FR-006 de spec 004). El
    reintento usa un `Console` nuevo apuntando al mismo `file` que `c`
    (nunca el mismo objeto `Console` que ya falló): un intento de escritura
    fallido dentro de esa ruta de renderizado deja el búfer interno del
    objeto en un estado inconsistente que hace fallar cualquier impresión
    posterior sobre ese mismo objeto, incluso con contenido puramente ASCII
    — verificado empíricamente; el flujo/archivo de destino en sí no queda
    afectado, por lo que un `Console` nuevo sobre el mismo `file` sí procede
    con normalidad.

    Parameters
    ----------
    texto : str, optional
        Texto literal a mostrar. Por defecto, `BANNER_OPSSLEUTH`.
    console : rich.console.Console or None, optional
        Instancia de `Console` a usar; si no se aporta, se usa la instancia de
        módulo por defecto.
    """
    c = console or _console
    try:
        c.print(texto, style=ESTILO_SISTEMA, no_wrap=True, overflow="crop", markup=False)
    except UnicodeError:
        alternativo = (
            BANNER_OPSSLEUTH_ASCII
            if texto is BANNER_OPSSLEUTH
            else texto.encode("ascii", "replace").decode("ascii")
        )
        Console(file=c.file).print(
            alternativo, style=ESTILO_SISTEMA, no_wrap=True, overflow="crop", markup=False
        )
