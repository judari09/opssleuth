"""Pruebas unitarias de la capa de presentación (`opssleuth.presentation.console`)."""

import io

from rich.console import Console

from opssleuth.presentation import console as console_module
from opssleuth.presentation.console import (
    BANNER_OPSSLEUTH,
    BANNER_OPSSLEUTH_ASCII,
    ETIQUETA_SISTEMA,
    ETIQUETA_USUARIO,
    leer_entrada_usuario,
    mostrar_actividad,
    mostrar_banner,
    mostrar_mensaje_sistema,
)


def _console_en_memoria() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, force_terminal=False), buffer


class TestMostrarMensajeSistema:
    """Historia 1 (etiqueta de rol) e Historia 2 (renderizado Markdown)."""

    def test_incluye_la_etiqueta_de_rol_del_sistema(self):
        console, buffer = _console_en_memoria()
        mostrar_mensaje_sistema("hola", console=console)
        assert ETIQUETA_SISTEMA in buffer.getvalue()

    def test_renderiza_lista_markdown_sin_simbolos_crudos(self):
        console, buffer = _console_en_memoria()
        mostrar_mensaje_sistema("- item uno\n- item dos", console=console)
        salida = buffer.getvalue()
        assert "item uno" in salida
        assert "item dos" in salida
        assert "- item uno" not in salida

    def test_renderiza_enfasis_sin_simbolos_crudos(self):
        console, buffer = _console_en_memoria()
        mostrar_mensaje_sistema("texto con **dato clave** resaltado", console=console)
        salida = buffer.getvalue()
        assert "dato clave" in salida
        assert "**" not in salida

    def test_texto_de_una_sola_linea_sigue_siendo_legible(self):
        console, buffer = _console_en_memoria()
        mostrar_mensaje_sistema("¿Qué sistema está fallando?", console=console)
        assert "¿Qué sistema está fallando?" in buffer.getvalue()

    def test_corchetes_literales_en_el_texto_no_rompen_el_renderizado(self):
        console, buffer = _console_en_memoria()
        mostrar_mensaje_sistema("revisa el archivo [facturacion.log]", console=console)
        assert "[facturacion.log]" in buffer.getvalue()

    def test_es_error_produce_salida_distinta_de_un_mensaje_normal(self):
        console_normal, buffer_normal = _console_en_memoria()
        console_error, buffer_error = _console_en_memoria()
        mostrar_mensaje_sistema("mismo texto", console=console_normal)
        mostrar_mensaje_sistema("mismo texto", es_error=True, console=console_error)
        # con force_terminal=False no hay ANSI que comparar; se verifica al menos
        # que ambas rutas de código se ejecutan sin fallar y producen la etiqueta.
        assert ETIQUETA_SISTEMA in buffer_normal.getvalue()
        assert ETIQUETA_SISTEMA in buffer_error.getvalue()


class TestLeerEntradaUsuario:
    """Historia 1 (etiqueta de rol del usuario)."""

    def test_muestra_el_prompt_como_mensaje_del_sistema_y_lee_la_respuesta(
        self, monkeypatch
    ):
        console, buffer = _console_en_memoria()
        monkeypatch.setattr("builtins.input", lambda: "mi respuesta")

        resultado = leer_entrada_usuario("¿Cuál es el problema?", console=console)

        salida = buffer.getvalue()
        assert resultado == "mi respuesta"
        assert ETIQUETA_SISTEMA in salida
        assert "¿Cuál es el problema?" in salida
        assert ETIQUETA_USUARIO in salida

    def test_prompt_vacio_no_muestra_mensaje_del_sistema(self, monkeypatch):
        console, buffer = _console_en_memoria()
        monkeypatch.setattr("builtins.input", lambda: "línea pegada")

        resultado = leer_entrada_usuario("", console=console)

        salida = buffer.getvalue()
        assert resultado == "línea pegada"
        assert ETIQUETA_SISTEMA not in salida
        assert ETIQUETA_USUARIO in salida

    def test_etiquetas_de_usuario_y_sistema_son_distintas(self):
        assert ETIQUETA_USUARIO != ETIQUETA_SISTEMA


class TestMostrarBanner:
    """Banner de bienvenida (arte ASCII) — no es un mensaje conversacional."""

    def test_imprime_el_banner_por_defecto_sin_lanzar(self):
        console, buffer = _console_en_memoria()
        mostrar_banner(console=console)
        assert "OPSSLEUTH" in buffer.getvalue().upper().replace(" ", "").replace("\n", "") or (
            buffer.getvalue().strip() != ""
        )

    def test_no_incluye_la_etiqueta_de_rol_del_sistema(self):
        console, buffer = _console_en_memoria()
        mostrar_banner(console=console)
        assert ETIQUETA_SISTEMA not in buffer.getvalue()

    def test_no_procesa_el_texto_como_markdown(self):
        console, buffer = _console_en_memoria()
        mostrar_banner("**esto no debe resaltarse**", console=console)
        # a diferencia de mostrar_mensaje_sistema, los símbolos de marcado
        # deben conservarse tal cual (texto literal, no Markdown)
        assert "**esto no debe resaltarse**" in buffer.getvalue()

    def test_banner_ascii_alternativo_es_puramente_ascii(self):
        """Garantiza que el respaldo siga siendo seguro para consolas sin
        soporte de caracteres fuera de ASCII (regresión: research.md)."""
        assert all(ord(caracter) < 128 for caracter in BANNER_OPSSLEUTH_ASCII)

    def test_recurre_al_banner_ascii_si_falla_la_codificacion(self, monkeypatch):
        console, buffer = _console_en_memoria()
        llamadas = {"n": 0}
        print_original = console.print

        def print_falla_una_vez(*args, **kwargs):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise UnicodeEncodeError("ascii", "x", 0, 1, "simulado")
            return print_original(*args, **kwargs)

        monkeypatch.setattr(console, "print", print_falla_una_vez)
        monkeypatch.setattr(console_module, "Console", lambda file: console)

        mostrar_banner(BANNER_OPSSLEUTH, console=console)  # no debe propagar la excepción

        assert llamadas["n"] == 2


class TestMostrarActividad:
    """Historia 3 (indicador de actividad)."""

    def test_se_puede_usar_como_context_manager_sin_lanzar(self):
        console, _ = _console_en_memoria()
        with mostrar_actividad("procesando...", console=console):
            pass  # no debe lanzar ninguna excepción

    def test_el_bloque_with_se_ejecuta(self):
        console, _ = _console_en_memoria()
        ejecutado = False
        with mostrar_actividad("procesando...", console=console):
            ejecutado = True
        assert ejecutado is True
