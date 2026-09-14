"""Pruebas unitarias de `evaluar_descripcion`/`generar_preguntas` con `create_agent` mockeado.

Migrado de `test_claude_engine.py`/`test_ollama_engine.py` (ver
`specs/002-busqueda-logs/contracts/clarification_migration.md`, "Estrategia de
migración de pruebas"): mismos casos de prueba, ahora mockeando
`langchain.agents.create_agent` (tal como lo importa `opssleuth.clarification.engine`)
en vez del cliente `anthropic`/`ollama` crudo, ya que el comportamiento es el
mismo independientemente de qué `BaseChatModel` concreto se inyecte.
"""

from unittest.mock import MagicMock

import pytest

from opssleuth.clarification import engine as clarification_engine
from opssleuth.clarification.engine import (
    CampoExtraidoLLM,
    ClarificationEngineError,
    Contradiccion,
    EvaluacionDescripcion,
    MultiplesProblemas,
    PreguntaSugerida,
    evaluar_descripcion,
    generar_preguntas,
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


def _mockear_create_agent(monkeypatch, resultado_invoke=None, excepcion=None):
    """Reemplaza `create_agent` (importado en `clarification.engine`) por un doble.

    Devuelve `(create_agent_mock, agente_mock)` para permitir aserciones tanto
    sobre la construcción del agente como sobre la invocación.
    """
    agente_mock = MagicMock()
    if excepcion is not None:
        agente_mock.invoke.side_effect = excepcion
    else:
        agente_mock.invoke.return_value = resultado_invoke
    create_agent_mock = MagicMock(return_value=agente_mock)
    monkeypatch.setattr(clarification_engine, "create_agent", create_agent_mock)
    return create_agent_mock, agente_mock


class TestEvaluarDescripcion:
    def test_evalua_campos_presentes(self, monkeypatch):
        _, agente = _mockear_create_agent(
            monkeypatch, resultado_invoke={"structured_response": _evaluacion_completa()}
        )

        evaluacion = evaluar_descripcion(MagicMock(), "error 500 en facturación desde ayer", [])

        assert evaluacion.sistema_afectado.presente is True
        assert evaluacion.sistema_afectado.valor == "Facturación"
        agente.invoke.assert_called_once()

    def test_evalua_campos_ausentes_y_genera_preguntas_sugeridas(self, monkeypatch):
        _mockear_create_agent(
            monkeypatch, resultado_invoke={"structured_response": _evaluacion_incompleta()}
        )

        evaluacion = evaluar_descripcion(MagicMock(), "no funciona", [])

        assert [p.campo_objetivo for p in evaluacion.preguntas_sugeridas] == [
            "sistema_afectado",
            "sintoma",
        ]

    def test_detecta_contradiccion(self, monkeypatch):
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
        _mockear_create_agent(
            monkeypatch, resultado_invoke={"structured_response": evaluacion_esperada}
        )

        evaluacion = evaluar_descripcion(
            MagicMock(),
            "en realidad empezó hace una semana",
            [{"role": "assistant", "content": "¿cuándo empezó?"}],
        )

        assert evaluacion.contradiccion.detectada is True
        assert evaluacion.contradiccion.descripcion is not None

    def test_detecta_multiples_problemas(self, monkeypatch):
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
        _mockear_create_agent(
            monkeypatch, resultado_invoke={"structured_response": evaluacion_esperada}
        )

        evaluacion = evaluar_descripcion(
            MagicMock(), "el login no funciona y además los reportes salen vacíos", []
        )

        assert evaluacion.multiples_problemas.detectado is True
        assert evaluacion.multiples_problemas.problemas_identificados == [
            "Login no funciona",
            "Reportes vacíos",
        ]

    def test_propaga_error_del_proveedor_como_clarification_engine_error(self, monkeypatch):
        _mockear_create_agent(monkeypatch, excepcion=RuntimeError("fallo de comunicación"))

        with pytest.raises(ClarificationEngineError) as exc_info:
            evaluar_descripcion(MagicMock(), "no funciona", [])

        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestGenerarPreguntas:
    def test_transforma_preguntas_sugeridas_sin_llamar_al_modelo(self, monkeypatch):
        create_agent_mock, _ = _mockear_create_agent(
            monkeypatch, resultado_invoke={"structured_response": _evaluacion_completa()}
        )
        evaluacion = _evaluacion_incompleta()

        aclaraciones = generar_preguntas(evaluacion, [])

        assert [a.campo_objetivo for a in aclaraciones] == ["sistema_afectado", "sintoma"]
        assert all(a.respuesta is None for a in aclaraciones)
        # generar_preguntas es una transformación determinista (Regla 5 del
        # contrato): no debe invocar create_agent en absoluto.
        create_agent_mock.assert_not_called()
