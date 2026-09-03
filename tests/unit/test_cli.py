"""Pruebas unitarias del bucle conversacional de la CLI (`opssleuth.cli`)."""

from opssleuth import cli
from opssleuth.clarification.engine import (
    CampoExtraidoLLM,
    Contradiccion,
    EvaluacionDescripcion,
    MultiplesProblemas,
    PreguntaSugerida,
)
from opssleuth.domain.case import Aclaracion, Caso, DescripcionVaciaError


class FakeClarificationEngine:
    """Motor de aclaración de prueba: evaluaciones predefinidas, sin llamadas reales."""

    def __init__(self, evaluaciones):
        self._evaluaciones = list(evaluaciones)
        self.llamadas_evaluar = []

    def evaluar(self, texto, contexto):
        self.llamadas_evaluar.append(texto)
        return self._evaluaciones.pop(0)

    def generar_preguntas(self, evaluacion, contexto):
        return [
            Aclaracion(pregunta=p.pregunta, campo_objetivo=p.campo_objetivo)
            for p in evaluacion.preguntas_sugeridas
        ]


def _evaluacion(
    sistema_presente=False,
    sintoma_presente=False,
    momento_presente=False,
    preguntas=None,
    contradiccion_detectada=False,
    contradiccion_descripcion=None,
    multiples_detectado=False,
    problemas=None,
):
    return EvaluacionDescripcion(
        sistema_afectado=CampoExtraidoLLM(
            presente=sistema_presente, valor="Facturación" if sistema_presente else None
        ),
        sintoma=CampoExtraidoLLM(
            presente=sintoma_presente, valor="Error 500" if sintoma_presente else None
        ),
        momento=CampoExtraidoLLM(
            presente=momento_presente, valor="Desde ayer" if momento_presente else None
        ),
        preguntas_sugeridas=preguntas or [],
        contradiccion=Contradiccion(
            detectada=contradiccion_detectada, descripcion=contradiccion_descripcion
        ),
        multiples_problemas=MultiplesProblemas(
            detectado=multiples_detectado, problemas_identificados=problemas or []
        ),
    )


class TestDeteccionDeIntencion:
    def test_detecta_intencion_de_nuevo_caso(self):
        assert cli._es_intencion_nuevo_caso("quiero reportar otro problema")
        assert cli._es_intencion_nuevo_caso("Tengo un NUEVO CASO que reportar")
        assert not cli._es_intencion_nuevo_caso("el sistema sigue fallando")

    def test_detecta_solicitud_de_resumen(self):
        assert cli._es_solicitud_de_resumen("¿me puedes dar un resumen?")
        assert cli._es_solicitud_de_resumen("recuérdame cuál era el problema")
        assert not cli._es_solicitud_de_resumen("el error sigue apareciendo")

    def test_detecta_no_puedo_aportar_mas_informacion(self):
        assert cli._indica_que_no_puede_aportar_mas("no tengo más información")
        assert not cli._indica_que_no_puede_aportar_mas("empezó ayer a las 3pm")

    def test_detecta_confirmacion(self):
        assert cli._es_confirmacion("sí")
        assert cli._es_confirmacion("Si")
        assert not cli._es_confirmacion("no")


class TestSolicitarDescripcion:
    def test_registra_descripcion_en_primer_intento(self, monkeypatch):
        entradas = iter(["el login no funciona desde ayer"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_descripcion(caso)

        assert caso.descripcion_inicial.texto == "el login no funciona desde ayer"

    def test_rechaza_vacia_y_reintenta(self, monkeypatch):
        entradas = iter(["   ", "el login no funciona"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_descripcion(caso)

        assert caso.descripcion_inicial.texto == "el login no funciona"

    def test_no_vuelve_a_solicitar_si_ya_esta_registrada(self, monkeypatch):
        def _fallar_si_se_llama(prompt):
            raise AssertionError("no debería pedirse la descripción de nuevo")

        monkeypatch.setattr(cli, "_leer_entrada", _fallar_si_se_llama)

        caso = Caso()
        caso.registrar_descripcion("ya registrada")

        cli._solicitar_descripcion(caso)  # no debe lanzar ni pedir entrada

        assert caso.descripcion_inicial.texto == "ya registrada"


class TestProcesarIntake:
    def test_descripcion_completa_no_genera_preguntas(self, monkeypatch):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "no debería llamarse")
        motor = FakeClarificationEngine(
            [_evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True)]
        )
        caso = Caso()
        caso.registrar_descripcion(
            "El módulo de facturación devuelve error 500 desde ayer."
        )

        cli._procesar_intake(caso, motor)

        assert caso.estado_informacion == "completa"
        assert caso.aclaraciones == []

    def test_descripcion_incompleta_formula_preguntas_y_completa_campos(self, monkeypatch):
        respuestas = iter(["Facturación", "Error 500"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = FakeClarificationEngine(
            [
                _evaluacion(
                    momento_presente=True,
                    preguntas=[
                        PreguntaSugerida(
                            campo_objetivo="sistema_afectado", pregunta="¿Qué sistema?"
                        ),
                        PreguntaSugerida(
                            campo_objetivo="sintoma", pregunta="¿Qué error observas?"
                        ),
                    ],
                ),
                # evaluaciones de contradicción para cada respuesta de aclaración
                _evaluacion(momento_presente=True),
                _evaluacion(momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("no funciona desde ayer")

        cli._procesar_intake(caso, motor)

        assert caso.descripcion_inicial.sistema_afectado.valor == "Facturación"
        assert caso.descripcion_inicial.sintoma.valor == "Error 500"
        assert caso.estado_informacion == "completa"
        assert len(caso.aclaraciones) == 2

    def test_deteccion_de_multiples_problemas_pide_confirmacion(self, monkeypatch):
        respuestas = iter(["El login, es más urgente"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = FakeClarificationEngine(
            [
                _evaluacion(
                    multiples_detectado=True,
                    problemas=["Login no funciona", "Reportes vacíos"],
                    preguntas=[
                        PreguntaSugerida(
                            campo_objetivo="problema_principal",
                            pregunta="¿Cuál priorizamos?",
                        )
                    ],
                ),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("el login no funciona y los reportes salen vacíos")

        cli._procesar_intake(caso, motor)

        aclaracion_problema = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "problema_principal"
        )
        assert aclaracion_problema.respuesta == "El login, es más urgente"

    def test_no_puedo_aportar_mas_marca_sin_confirmar_y_continua(self, monkeypatch):
        respuestas = iter(["no tengo más información", "Error 500"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = FakeClarificationEngine(
            [
                _evaluacion(
                    preguntas=[
                        PreguntaSugerida(
                            campo_objetivo="sistema_afectado", pregunta="¿Qué sistema?"
                        ),
                        PreguntaSugerida(
                            campo_objetivo="sintoma", pregunta="¿Qué error observas?"
                        ),
                    ],
                    momento_presente=True,
                ),
                _evaluacion(momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("no funciona desde ayer")

        cli._procesar_intake(caso, motor)

        sistema_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "sistema_afectado"
        )
        assert sistema_aclaracion.sin_confirmar is True
        assert sistema_aclaracion.respuesta is None
        sintoma_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "sintoma"
        )
        assert sintoma_aclaracion.respuesta == "Error 500"

    def test_contradiccion_se_marca_y_no_descarta_datos(self, monkeypatch):
        respuestas = iter(["Hace una semana, no ayer"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = FakeClarificationEngine(
            [
                _evaluacion(
                    sistema_presente=True,
                    sintoma_presente=True,
                    preguntas=[
                        PreguntaSugerida(campo_objetivo="momento", pregunta="¿Cuándo?")
                    ],
                ),
                _evaluacion(
                    sistema_presente=True,
                    sintoma_presente=True,
                    contradiccion_detectada=True,
                    contradiccion_descripcion="La fecha no coincide con lo dicho antes.",
                ),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("el sistema falla desde ayer")

        cli._procesar_intake(caso, motor)

        momento_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "momento"
        )
        assert momento_aclaracion.contradice_descripcion_original is True
        assert momento_aclaracion.respuesta == "Hace una semana, no ayer"
        # el dato original no se pierde: sigue en la descripción inicial original
        assert "desde ayer" in caso.descripcion_inicial.texto
