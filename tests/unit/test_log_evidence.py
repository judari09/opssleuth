"""Pruebas unitarias de las entidades de dominio de evidencia de logs."""

import pytest

from opssleuth.domain.log_evidence import (
    ApreciacionInicialLogs,
    EntradaLogRelevante,
    FuenteDeLogs,
)


class TestFuenteDeLogs:
    def test_crea_fuente_con_ruta_valida(self):
        fuente = FuenteDeLogs(ruta="/tmp/app.log", origen="ruta_usuario")

        assert fuente.ruta == "/tmp/app.log"
        assert fuente.origen == "ruta_usuario"
        assert fuente.aportada_en is not None

    @pytest.mark.parametrize("ruta_invalida", ["", "   ", "\n\t"])
    def test_rechaza_ruta_vacia_o_solo_espacios(self, ruta_invalida):
        with pytest.raises(ValueError):
            FuenteDeLogs(ruta=ruta_invalida, origen="ruta_usuario")

    def test_origen_contenido_pegado(self):
        fuente = FuenteDeLogs(ruta="/tmp/pegado_123.log", origen="contenido_pegado")

        assert fuente.origen == "contenido_pegado"


class TestEntradaLogRelevante:
    def test_crea_entrada_valida(self):
        fuente = FuenteDeLogs(ruta="/tmp/app.log", origen="ruta_usuario")
        entrada = EntradaLogRelevante(
            fuente=fuente,
            numero_linea=42,
            contenido="ERROR timeout al conectar con base de datos",
            marca_de_tiempo="2026-09-03T14:15:47",
        )

        assert entrada.numero_linea == 42
        assert entrada.marca_de_tiempo == "2026-09-03T14:15:47"

    def test_marca_de_tiempo_es_opcional(self):
        fuente = FuenteDeLogs(ruta="/tmp/app.log", origen="ruta_usuario")
        entrada = EntradaLogRelevante(fuente=fuente, numero_linea=1, contenido="algo")

        assert entrada.marca_de_tiempo is None

    @pytest.mark.parametrize("numero_invalido", [0, -1, -100])
    def test_rechaza_numero_linea_menor_que_uno(self, numero_invalido):
        fuente = FuenteDeLogs(ruta="/tmp/app.log", origen="ruta_usuario")

        with pytest.raises(ValueError):
            EntradaLogRelevante(fuente=fuente, numero_linea=numero_invalido, contenido="algo")


class TestApreciacionInicialLogs:
    def test_apreciacion_sin_entradas_es_valida(self):
        apreciacion = ApreciacionInicialLogs(
            resumen="No se encontraron entradas de log relacionadas con el incidente descrito."
        )

        assert apreciacion.entradas_destacadas == []
        assert apreciacion.hay_mas_coincidencias is False

    def test_apreciacion_con_entradas_y_mas_coincidencias(self):
        fuente = FuenteDeLogs(ruta="/tmp/app.log", origen="ruta_usuario")
        entradas = [
            EntradaLogRelevante(fuente=fuente, numero_linea=i, contenido=f"ERROR {i}")
            for i in range(1, 4)
        ]

        apreciacion = ApreciacionInicialLogs(
            resumen="Se encontraron varios errores de timeout.",
            entradas_destacadas=entradas,
            hay_mas_coincidencias=True,
        )

        assert len(apreciacion.entradas_destacadas) == 3
        assert apreciacion.hay_mas_coincidencias is True
        assert apreciacion.generada_en is not None
