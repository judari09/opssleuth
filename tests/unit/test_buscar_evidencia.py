"""Pruebas unitarias de `buscar_evidencia` con el agente de búsqueda mockeado."""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from opssleuth.domain.case import Caso
from opssleuth.domain.log_evidence import FuenteDeLogs
from opssleuth.evidence import engine as evidence_engine
from opssleuth.evidence.engine import LogSearchEngineError, buscar_evidencia


def _fuente(ruta="/tmp/app.log"):
    return FuenteDeLogs(ruta=ruta, origen="ruta_usuario")


def _tool_message_busqueda(coincidencias, nombre="buscar_texto"):
    return ToolMessage(
        content=json.dumps({"coincidencias": coincidencias, "hay_mas": False}),
        name=nombre,
        tool_call_id="call_1",
    )


def _mockear_construir_agente(monkeypatch, resultado_invoke=None, excepcion=None):
    """Reemplaza `construir_agente` por un doble cuyo `.invoke()` es controlable."""
    agente_mock = MagicMock()
    if excepcion is not None:
        agente_mock.invoke.side_effect = excepcion
    else:
        agente_mock.invoke.return_value = resultado_invoke
    construir_agente_mock = MagicMock(return_value=agente_mock)
    monkeypatch.setattr(evidence_engine, "construir_agente", construir_agente_mock)
    return construir_agente_mock, agente_mock


class TestBuscarEvidenciaSinFuentes:
    def test_sin_fuentes_no_invoca_ningun_agente(self, monkeypatch):
        construir_agente_mock, _ = _mockear_construir_agente(monkeypatch)

        apreciacion = buscar_evidencia(MagicMock(), Caso(), [], lambda p: "")

        assert apreciacion.entradas_destacadas == []
        assert "no se aportó" in apreciacion.resumen.lower()
        construir_agente_mock.assert_not_called()


class TestBuscarEvidenciaConCoincidencias:
    def test_registra_entradas_a_partir_de_los_tool_messages_reales(self, monkeypatch):
        fuente = _fuente()
        mensajes = [
            _tool_message_busqueda(
                [{"numero_linea": 3, "contenido": "ERROR timeout al conectar con base de datos"}]
            ),
            AIMessage(content="Encontré un timeout de base de datos relacionado con el incidente."),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("El sistema de facturación falla desde las 14:15.")

        apreciacion = buscar_evidencia(MagicMock(), caso, [fuente], lambda p: "")

        assert len(apreciacion.entradas_destacadas) == 1
        assert apreciacion.entradas_destacadas[0].numero_linea == 3
        assert apreciacion.entradas_destacadas[0].fuente is fuente
        assert "timeout" in apreciacion.resumen.lower()
        assert apreciacion.hay_mas_coincidencias is False

    def test_sin_coincidencias_refleja_ausencia_explicitamente(self, monkeypatch):
        mensajes = [AIMessage(content="No encontré nada relevante, pero aquí hay algo igual.")]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("no funciona")

        apreciacion = buscar_evidencia(MagicMock(), caso, [_fuente()], lambda p: "")

        assert apreciacion.entradas_destacadas == []
        assert apreciacion.resumen == (
            "No se encontraron entradas de log relacionadas con el incidente descrito."
        )

    def test_propaga_error_del_proveedor_como_log_search_engine_error(self, monkeypatch):
        _mockear_construir_agente(monkeypatch, excepcion=RuntimeError("fallo de comunicación"))
        caso = Caso()
        caso.registrar_descripcion("no funciona")

        with pytest.raises(LogSearchEngineError) as exc_info:
            buscar_evidencia(MagicMock(), caso, [_fuente()], lambda p: "")

        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestLimiteYConsolidacion:
    def test_acota_y_marca_hay_mas_coincidencias_con_volumen_grande(self, monkeypatch):
        coincidencias = [
            {"numero_linea": i, "contenido": f"ERROR {i}"} for i in range(1, 31)
        ]
        mensajes = [
            _tool_message_busqueda(coincidencias),
            AIMessage(content="Se encontraron muchos errores similares."),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("errores repetidos")

        apreciacion = buscar_evidencia(MagicMock(), caso, [_fuente()], lambda p: "")

        assert len(apreciacion.entradas_destacadas) == evidence_engine.MAXIMO_ENTRADAS_DESTACADAS
        assert apreciacion.hay_mas_coincidencias is True

    def test_deduplica_entradas_repetidas(self, monkeypatch):
        coincidencia = {"numero_linea": 5, "contenido": "ERROR repetido"}
        mensajes = [
            _tool_message_busqueda([coincidencia]),
            _tool_message_busqueda([coincidencia], nombre="leer_contexto"),
            AIMessage(content="Encontré un error."),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("error puntual")

        apreciacion = buscar_evidencia(MagicMock(), caso, [_fuente()], lambda p: "")

        assert len(apreciacion.entradas_destacadas) == 1

    def test_consolida_varias_fuentes_en_una_unica_apreciacion(self, monkeypatch):
        fuente_a = _fuente("/tmp/servicio_a.log")
        fuente_b = _fuente("/tmp/servicio_b.log")

        agente_mock = MagicMock()
        agente_mock.invoke.side_effect = [
            {
                "messages": [
                    _tool_message_busqueda([{"numero_linea": 1, "contenido": "ERROR en A"}]),
                    AIMessage(content="Hallazgo en el servicio A."),
                ]
            },
            {
                "messages": [
                    _tool_message_busqueda([{"numero_linea": 7, "contenido": "ERROR en B"}]),
                    AIMessage(content="Hallazgo en el servicio B."),
                ]
            },
        ]
        monkeypatch.setattr(
            evidence_engine, "construir_agente", MagicMock(return_value=agente_mock)
        )
        caso = Caso()
        caso.registrar_descripcion("fallo intermitente entre dos servicios")

        apreciacion = buscar_evidencia(MagicMock(), caso, [fuente_a, fuente_b], lambda p: "")

        rutas = {entrada.fuente.ruta for entrada in apreciacion.entradas_destacadas}
        assert rutas == {"/tmp/servicio_a.log", "/tmp/servicio_b.log"}
        assert "servicio A" in apreciacion.resumen
        assert "servicio B" in apreciacion.resumen
        # una única apreciación consolidada, no una por fuente (FR-010a)
        assert agente_mock.invoke.call_count == 2
