"""Pruebas unitarias de `consultar_evidencia_bd` con el agente mockeado."""

import contextlib
import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from opssleuth.database import engine as database_engine
from opssleuth.database.engine import DatabaseSearchEngineError, consultar_evidencia_bd
from opssleuth.database.factory import FuenteDeBaseDeDatosConfigurada
from opssleuth.domain.case import Caso
from opssleuth.domain.database_evidence import FuenteDeBaseDeDatos


def _fuente_configurada():
    return FuenteDeBaseDeDatosConfigurada(
        engine=MagicMock(),
        fuente=FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas"]),
        timeout_segundos=10,
    )


def _anunciar_actividad_nulo(_mensaje):
    return contextlib.nullcontext()


def _tool_message_consulta(filas, consulta="SELECT * FROM facturas"):
    return ToolMessage(
        content=json.dumps({"filas": filas, "hay_mas": False, "consulta_ejecutada": consulta}),
        name="ejecutar_consulta_sql",
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
    monkeypatch.setattr(database_engine, "construir_agente", construir_agente_mock)
    return construir_agente_mock, agente_mock


class TestConsultarEvidenciaBDConResultados:
    def test_registra_entradas_a_partir_de_los_tool_messages_reales(self, monkeypatch):
        mensajes = [
            _tool_message_consulta([{"id": 1007, "estado": "fallida"}]),
            AIMessage(content="Encontré la factura 1007 en estado fallida."),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("La factura 1007 falló desde las 14:15.")

        apreciacion = consultar_evidencia_bd(
            MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
        )

        assert len(apreciacion.entradas_destacadas) == 1
        assert apreciacion.entradas_destacadas[0].fila == {"id": 1007, "estado": "fallida"}
        assert apreciacion.entradas_destacadas[0].consulta == "SELECT * FROM facturas"
        assert "1007" in apreciacion.resumen

    def test_sin_resultados_refleja_ausencia_explicitamente(self, monkeypatch):
        mensajes = [AIMessage(content="No encontré nada, pero igual algo relevante.")]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("no funciona")

        apreciacion = consultar_evidencia_bd(
            MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
        )

        assert apreciacion.entradas_destacadas == []
        assert apreciacion.resumen == (
            "No se encontraron filas en la base de datos relacionadas con el incidente descrito."
        )

    def test_propaga_error_del_proveedor_como_database_search_engine_error(self, monkeypatch):
        _mockear_construir_agente(monkeypatch, excepcion=RuntimeError("fallo de comunicación"))
        caso = Caso()
        caso.registrar_descripcion("no funciona")

        with pytest.raises(DatabaseSearchEngineError) as exc_info:
            consultar_evidencia_bd(
                MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
            )

        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_intento_de_consulta_rechazada_no_genera_evidencia_ni_interrumpe(self, monkeypatch):
        """Un intento de escritura/fuera de alcance se rechaza *dentro* de la
        herramienta (mismo mensaje de error como ToolMessage, no una
        excepción) — el bucle del agente continúa con normalidad y no se
        registra ninguna EntradaBDRelevante a partir del rechazo (Escenario 3
        de la Historia 2, `quickstart.md`)."""
        mensajes = [
            ToolMessage(
                content=json.dumps({"error": "La consulta referencia una tabla fuera de alcance."}),
                name="ejecutar_consulta_sql",
                tool_call_id="call_1",
            ),
            _tool_message_consulta([{"id": 1007, "estado": "fallida"}]),
            AIMessage(content="No pude modificar el dato, pero encontré la factura 1007."),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("actualiza el estado de la factura 1007 a pagada")

        apreciacion = consultar_evidencia_bd(
            MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
        )

        assert len(apreciacion.entradas_destacadas) == 1
        assert apreciacion.entradas_destacadas[0].fila == {"id": 1007, "estado": "fallida"}

    def test_invoca_anunciar_actividad_antes_de_presentar_el_resultado(self, monkeypatch):
        mensajes = [AIMessage(content="Nada relevante.")]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("no funciona")
        llamadas = []

        def anunciar_espia(mensaje):
            llamadas.append(mensaje)
            return contextlib.nullcontext()

        consultar_evidencia_bd(MagicMock(), caso, _fuente_configurada(), anunciar_espia)

        assert len(llamadas) == 1


class TestConsultarEvidenciaBDConCruceDeTablas:
    """Historia 3: correlación con cruce entre varias tablas."""

    def test_resuelve_incidente_cuya_evidencia_requiere_cruzar_tres_tablas(self, monkeypatch):
        mensajes = [
            _tool_message_consulta(
                [{"id": 1007, "nombre": "Ana", "estado_servicio": "timeout"}],
                consulta=(
                    "SELECT f.id, u.nombre, e.estado AS estado_servicio FROM facturas f "
                    "JOIN usuarios u ON f.usuario_id = u.id "
                    "JOIN eventos_servicio e ON e.id = f.id WHERE f.id = 1007"
                ),
            ),
            AIMessage(
                content="La usuaria Ana fue afectada por un timeout del servicio de facturación."
            ),
        ]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion(
            "¿Qué usuario fue afectado por el timeout que causó el fallo de la factura 1007?"
        )

        apreciacion = consultar_evidencia_bd(
            MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
        )

        assert len(apreciacion.entradas_destacadas) == 1
        assert apreciacion.entradas_destacadas[0].fila == {
            "id": 1007,
            "nombre": "Ana",
            "estado_servicio": "timeout",
        }
        assert "Ana" in apreciacion.resumen

    def test_cruce_sin_resultados_refleja_ausencia_explicitamente(self, monkeypatch):
        mensajes = [AIMessage(content="No encontré ninguna relación entre esas tablas.")]
        _mockear_construir_agente(monkeypatch, resultado_invoke={"messages": mensajes})
        caso = Caso()
        caso.registrar_descripcion("¿qué usuario fue afectado por un incidente inexistente?")

        apreciacion = consultar_evidencia_bd(
            MagicMock(), caso, _fuente_configurada(), _anunciar_actividad_nulo
        )

        assert apreciacion.entradas_destacadas == []
        assert apreciacion.resumen == (
            "No se encontraron filas en la base de datos relacionadas con el incidente descrito."
        )
