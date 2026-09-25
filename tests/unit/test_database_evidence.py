"""Pruebas unitarias de las entidades de dominio de evidencia de base de datos."""

import pytest

from opssleuth.domain.database_evidence import (
    ApreciacionInicialBD,
    EntradaBDRelevante,
    FuenteDeBaseDeDatos,
)


class TestFuenteDeBaseDeDatos:
    def test_crea_fuente_valida(self):
        fuente = FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas", "usuarios"])

        assert fuente.motor == "sqlite"
        assert fuente.tablas_permitidas == ["facturas", "usuarios"]
        assert fuente.aportada_en is not None

    @pytest.mark.parametrize("motor_invalido", ["", "   ", "\n\t"])
    def test_rechaza_motor_vacio_o_solo_espacios(self, motor_invalido):
        with pytest.raises(ValueError):
            FuenteDeBaseDeDatos(motor=motor_invalido, tablas_permitidas=["facturas"])

    def test_rechaza_tablas_permitidas_vacia(self):
        with pytest.raises(ValueError):
            FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=[])


class TestEntradaBDRelevante:
    def test_crea_entrada_valida(self):
        fuente = FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas"])
        entrada = EntradaBDRelevante(
            fuente=fuente,
            consulta="SELECT * FROM facturas WHERE id = 1007",
            fila={"id": 1007, "estado": "fallida"},
        )

        assert entrada.consulta == "SELECT * FROM facturas WHERE id = 1007"
        assert entrada.fila == {"id": 1007, "estado": "fallida"}

    @pytest.mark.parametrize("consulta_invalida", ["", "   ", "\n\t"])
    def test_rechaza_consulta_vacia_o_solo_espacios(self, consulta_invalida):
        fuente = FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas"])

        with pytest.raises(ValueError):
            EntradaBDRelevante(fuente=fuente, consulta=consulta_invalida, fila={})


class TestApreciacionInicialBD:
    def test_apreciacion_sin_entradas_es_valida(self):
        apreciacion = ApreciacionInicialBD(
            resumen="No se encontraron filas relacionadas con el incidente descrito."
        )

        assert apreciacion.entradas_destacadas == []
        assert apreciacion.hay_mas_resultados is False

    def test_apreciacion_con_entradas_y_mas_resultados(self):
        fuente = FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas"])
        entradas = [
            EntradaBDRelevante(
                fuente=fuente, consulta="SELECT * FROM facturas", fila={"id": i}
            )
            for i in range(1, 4)
        ]

        apreciacion = ApreciacionInicialBD(
            resumen="Se encontraron varias facturas relacionadas.",
            entradas_destacadas=entradas,
            hay_mas_resultados=True,
        )

        assert len(apreciacion.entradas_destacadas) == 3
        assert apreciacion.hay_mas_resultados is True
        assert apreciacion.generada_en is not None
