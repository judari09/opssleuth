"""Pruebas unitarias de ``ClaudeClarificationEngine`` con el cliente `anthropic` mockeado."""

from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from opssleuth.clarification.claude_engine import ClaudeClarificationEngine
from opssleuth.clarification.engine import (
    CampoExtraidoLLM,
    ClarificationEngineError,
    Contradiccion,
    EvaluacionDescripcion,
    MultiplesProblemas,
    PreguntaSugerida,
)


def _evaluacion_completa() -> EvaluacionDescripcion:
    return EvaluacionDescripcion(
        sistema_afectado=CampoExtraidoLLM(presente=True, valor="Facturación"),
        sintoma=CampoExtraidoLLM(presente=True, valor="Error 500"),
        momento=CampoExtraidoLLM(presente=True, valor="Desde ayer"),
        preguntas_sugeridas=[],
        contradiccion=Contradiccion(detectada=False, descripcion=None),
        multiples_problemas=MultiplesProblemas(detectado=False, problemas_identificados=[]),
    )


def _evaluacion_incompleta() -> EvaluacionDescripcion:
    return EvaluacionDescripcion(
        sistema_afectado=CampoExtraidoLLM(presente=False, valor=None),
        sintoma=CampoExtraidoLLM(presente=False, valor=None),
        momento=CampoExtraidoLLM(presente=False, valor=None),
        preguntas_sugeridas=[
            PreguntaSugerida(campo_objetivo="sistema_afectado", pregunta="¿Qué sistema?"),
            PreguntaSugerida(campo_objetivo="sintoma", pregunta="¿Qué error observas?"),
        ],
        contradiccion=Contradiccion(detectada=False, descripcion=None),
        multiples_problemas=MultiplesProblemas(detectado=False, problemas_identificados=[]),
    )


def _cliente_mock(evaluacion: EvaluacionDescripcion) -> MagicMock:
    cliente = MagicMock()
    respuesta = MagicMock()
    respuesta.parsed_output = evaluacion
    cliente.messages.parse.return_value = respuesta
    return cliente


class TestEvaluar:
    def test_evalua_campos_presentes(self):
        cliente = _cliente_mock(_evaluacion_completa())
        engine = ClaudeClarificationEngine(client=cliente)

        evaluacion = engine.evaluar("error 500 en facturación desde ayer", [])

        assert evaluacion.sistema_afectado.presente is True
        assert evaluacion.sistema_afectado.valor == "Facturación"
        cliente.messages.parse.assert_called_once()

    def test_evalua_campos_ausentes_y_genera_preguntas_sugeridas(self):
        cliente = _cliente_mock(_evaluacion_incompleta())
        engine = ClaudeClarificationEngine(client=cliente)

        evaluacion = engine.evaluar("no funciona", [])

        assert [p.campo_objetivo for p in evaluacion.preguntas_sugeridas] == [
            "sistema_afectado",
            "sintoma",
        ]

    def test_detecta_contradiccion(self):
        evaluacion_esperada = EvaluacionDescripcion(
            sistema_afectado=CampoExtraidoLLM(presente=True, valor="Facturación"),
            sintoma=CampoExtraidoLLM(presente=True, valor="Error 500"),
            momento=CampoExtraidoLLM(presente=True, valor="Hace una semana"),
            preguntas_sugeridas=[],
            contradiccion=Contradiccion(
                detectada=True, descripcion="La fecha contradice la descripción original."
            ),
            multiples_problemas=MultiplesProblemas(detectado=False, problemas_identificados=[]),
        )
        cliente = _cliente_mock(evaluacion_esperada)
        engine = ClaudeClarificationEngine(client=cliente)

        evaluacion = engine.evaluar(
            "en realidad empezó hace una semana",
            [{"role": "assistant", "content": "¿cuándo empezó?"}],
        )

        assert evaluacion.contradiccion.detectada is True
        assert evaluacion.contradiccion.descripcion is not None

    def test_detecta_multiples_problemas(self):
        evaluacion_esperada = EvaluacionDescripcion(
            sistema_afectado=CampoExtraidoLLM(presente=False, valor=None),
            sintoma=CampoExtraidoLLM(presente=False, valor=None),
            momento=CampoExtraidoLLM(presente=False, valor=None),
            preguntas_sugeridas=[
                PreguntaSugerida(
                    campo_objetivo="problema_principal",
                    pregunta="Detecté más de un problema, ¿cuál priorizamos?",
                )
            ],
            contradiccion=Contradiccion(detectada=False, descripcion=None),
            multiples_problemas=MultiplesProblemas(
                detectado=True,
                problemas_identificados=["Login no funciona", "Reportes vacíos"],
            ),
        )
        cliente = _cliente_mock(evaluacion_esperada)
        engine = ClaudeClarificationEngine(client=cliente)

        evaluacion = engine.evaluar(
            "el login no funciona y además los reportes salen vacíos", []
        )

        assert evaluacion.multiples_problemas.detectado is True
        assert evaluacion.multiples_problemas.problemas_identificados == [
            "Login no funciona",
            "Reportes vacíos",
        ]

    def test_propaga_api_error_como_clarification_engine_error(self):
        cliente = MagicMock()
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        cliente.messages.parse.side_effect = anthropic.APIError(
            "fallo de la API", request, body=None
        )
        engine = ClaudeClarificationEngine(client=cliente)

        with pytest.raises(ClarificationEngineError) as exc_info:
            engine.evaluar("no funciona", [])

        assert isinstance(exc_info.value.__cause__, anthropic.APIError)

    def test_propaga_api_connection_error_como_clarification_engine_error(self):
        cliente = MagicMock()
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        cliente.messages.parse.side_effect = anthropic.APIConnectionError(request=request)
        engine = ClaudeClarificationEngine(client=cliente)

        with pytest.raises(ClarificationEngineError) as exc_info:
            engine.evaluar("no funciona", [])

        assert isinstance(exc_info.value.__cause__, anthropic.APIConnectionError)


class TestGenerarPreguntas:
    def test_transforma_preguntas_sugeridas_sin_llamar_al_cliente(self):
        cliente = _cliente_mock(_evaluacion_completa())
        engine = ClaudeClarificationEngine(client=cliente)
        evaluacion = _evaluacion_incompleta()

        aclaraciones = engine.generar_preguntas(evaluacion, [])

        assert [a.campo_objetivo for a in aclaraciones] == ["sistema_afectado", "sintoma"]
        assert all(a.respuesta is None for a in aclaraciones)
        # generar_preguntas es una transformación determinista (Regla 5 del
        # contrato): no debe invocar al cliente subyacente.
        cliente.messages.parse.assert_not_called()
