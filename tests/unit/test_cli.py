"""Pruebas unitarias del bucle conversacional de la CLI (`opssleuth.cli`)."""

from unittest.mock import MagicMock

from opssleuth import cli
from opssleuth.clarification.engine import (
    CampoExtraidoLLM,
    ClarificationEngineError,
    Contradiccion,
    EvaluacionDescripcion,
    MultiplesProblemas,
    PreguntaSugerida,
)
from opssleuth.domain.case import Aclaracion, CampoExtraido, Caso, DescripcionVaciaError


class SecuenciaEvaluaciones:
    """Doble de prueba para `evaluar_descripcion`: evaluaciones predefinidas, sin llamadas reales.

    Se inyecta vía `monkeypatch.setattr(cli, "evaluar_descripcion", ...)`. `generar_preguntas`
    no necesita un doble: es una transformación determinista sin llamada al modelo (Regla 5
    del contrato), así que las pruebas usan la implementación real.
    """

    def __init__(self, evaluaciones):
        self._evaluaciones = list(evaluaciones)
        self.llamadas_evaluar = []

    def __call__(self, chat_model, texto, contexto):
        self.llamadas_evaluar.append(texto)
        return self._evaluaciones.pop(0)


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
        motor = SecuenciaEvaluaciones(
            [_evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True)]
        )
        caso = Caso()
        caso.registrar_descripcion(
            "El módulo de facturación devuelve error 500 desde ayer."
        )

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        assert caso.estado_informacion == "completa"
        assert caso.aclaraciones == []

    def test_dos_preguntas_pendientes_se_combinan_y_una_respuesta_completa_ambos_campos(
        self, monkeypatch
    ):
        """Con 2+ preguntas pendientes, se combinan en un turno (US2, spec 003)."""
        respuestas = iter(["Es el sistema de facturación, y el error es 500"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
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
                # única evaluación de la respuesta combinada — cubre ambos campos
                _evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("no funciona desde ayer")

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        assert caso.descripcion_inicial.sistema_afectado.valor == "Facturación"
        assert caso.descripcion_inicial.sintoma.valor == "Error 500"
        assert caso.estado_informacion == "completa"
        assert len(caso.aclaraciones) == 2

    def test_deteccion_de_multiples_problemas_pide_confirmacion(self, monkeypatch):
        respuestas = iter(["El login, es más urgente"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
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

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        aclaracion_problema = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "problema_principal"
        )
        assert aclaracion_problema.respuesta == "El login, es más urgente"

    def test_no_puedo_aportar_mas_en_pregunta_individual_tras_combinada_parcial(
        self, monkeypatch
    ):
        """La respuesta combinada cubre solo un campo (US2); el otro cae al bucle
        uno-por-uno existente, donde declinar sigue funcionando igual que en 001."""
        respuestas = iter(["Error 500", "no tengo más información"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
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
                # evaluación de la respuesta combinada: solo cubre síntoma
                _evaluacion(sintoma_presente=True, momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("no funciona desde ayer")

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        sintoma_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "sintoma"
        )
        assert sintoma_aclaracion.respuesta == "Error 500"
        sistema_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "sistema_afectado"
        )
        assert sistema_aclaracion.sin_confirmar is True
        assert sistema_aclaracion.respuesta is None

    def test_contradiccion_se_marca_y_no_descarta_datos(self, monkeypatch):
        respuestas = iter(["Hace una semana, no ayer"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
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

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        momento_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "momento"
        )
        assert momento_aclaracion.contradice_descripcion_original is True
        assert momento_aclaracion.respuesta == "Hace una semana, no ayer"
        # el dato original no se pierde: sigue en la descripción inicial original
        assert "desde ayer" in caso.descripcion_inicial.texto


class TestFormularAclaracionesCombinadas:
    """Pruebas unitarias de `_formular_y_registrar_aclaraciones_combinadas` (US2, spec 003)."""

    def _preguntas(self):
        return [
            Aclaracion(pregunta="¿Qué sistema?", campo_objetivo="sistema_afectado"),
            Aclaracion(pregunta="¿Cuándo?", campo_objetivo="momento"),
        ]

    def test_respuesta_cubre_todos_los_campos_pendientes_sin_sobrescribir_confirmados(
        self, monkeypatch
    ):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "Es facturación, fue ayer")
        motor = SecuenciaEvaluaciones(
            [_evaluacion(sistema_presente=True, momento_presente=True, sintoma_presente=True)]
        )
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        caso.registrar_descripcion("algo falla")
        # sintoma ya estaba confirmado antes de esta respuesta combinada
        caso.descripcion_inicial.sintoma = CampoExtraido(presente=True, valor="ya confirmado")

        pendientes = cli._formular_y_registrar_aclaraciones_combinadas(
            caso, MagicMock(), self._preguntas()
        )

        assert pendientes == []
        assert caso.descripcion_inicial.sistema_afectado.valor == "Facturación"
        assert caso.descripcion_inicial.momento.valor == "Desde ayer"
        # no se sobrescribe un campo ya confirmado que la respuesta no cubría (research.md, Decisión 3)
        assert caso.descripcion_inicial.sintoma.valor == "ya confirmado"
        assert len(caso.aclaraciones) == 2

    def test_respuesta_cubre_solo_parte_devuelve_pendientes_restantes(self, monkeypatch):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "Fue ayer")
        motor = SecuenciaEvaluaciones([_evaluacion(momento_presente=True)])
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        caso.registrar_descripcion("algo falla")

        pendientes = cli._formular_y_registrar_aclaraciones_combinadas(
            caso, MagicMock(), self._preguntas()
        )

        assert [a.campo_objetivo for a in pendientes] == ["sistema_afectado"]
        assert caso.descripcion_inicial.momento.valor == "Desde ayer"
        momento_aclaracion = next(a for a in caso.aclaraciones if a.campo_objetivo == "momento")
        assert momento_aclaracion.respuesta == "Fue ayer"

    def test_respuesta_ambigua_no_inventa_correlacion(self, monkeypatch):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "no estoy seguro")
        motor = SecuenciaEvaluaciones([_evaluacion()])
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        caso.registrar_descripcion("algo falla")

        pendientes = cli._formular_y_registrar_aclaraciones_combinadas(
            caso, MagicMock(), self._preguntas()
        )

        assert len(pendientes) == 2
        assert caso.aclaraciones == []

    def test_no_puedo_aportar_mas_marca_todo_el_lote_sin_confirmar(self, monkeypatch):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "no tengo más información")

        def _fallar_si_se_llama(*args, **kwargs):
            raise AssertionError("no debería evaluarse con el LLM si el usuario declina todo")

        monkeypatch.setattr(cli, "evaluar_descripcion", _fallar_si_se_llama)

        caso = Caso()
        caso.registrar_descripcion("algo falla")

        pendientes = cli._formular_y_registrar_aclaraciones_combinadas(
            caso, MagicMock(), self._preguntas()
        )

        assert pendientes == []
        assert len(caso.aclaraciones) == 2
        assert all(a.sin_confirmar for a in caso.aclaraciones)
        assert all(a.respuesta is None for a in caso.aclaraciones)

    def test_error_de_evaluacion_deja_todo_pendiente(self, monkeypatch):
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: "Es facturación")

        def _fallar(*args, **kwargs):
            raise ClarificationEngineError("boom")

        monkeypatch.setattr(cli, "evaluar_descripcion", _fallar)

        caso = Caso()
        caso.registrar_descripcion("algo falla")

        pendientes = cli._formular_y_registrar_aclaraciones_combinadas(
            caso, MagicMock(), self._preguntas()
        )

        assert len(pendientes) == 2


class TestExtraerRutaCandidata:
    """Pruebas de `_extraer_ruta_candidata` (US1, spec 003) — función pura, sin mock."""

    def test_detecta_ruta_al_final_de_una_oracion(self):
        assert (
            cli._extraer_ruta_candidata(
                "el servicio de facturacion fallo, revisa test_logs/facturacion.log"
            )
            == "test_logs/facturacion.log"
        )

    def test_sin_ningun_token_con_forma_de_ruta_devuelve_none(self):
        assert cli._extraer_ruta_candidata("el servicio de facturacion fallo desde ayer") is None

    def test_detecta_extension_txt(self):
        assert (
            cli._extraer_ruta_candidata("aquí está el log: salida.txt")
            == "salida.txt"
        )

    def test_con_varios_candidatos_devuelve_el_ultimo(self):
        assert (
            cli._extraer_ruta_candidata("revisa primero notas.log y luego facturacion.log")
            == "facturacion.log"
        )

    def test_detecta_separador_backslash(self):
        assert (
            cli._extraer_ruta_candidata(r"el archivo está en test_logs\facturacion.log")
            == r"test_logs\facturacion.log"
        )


class TestProcesarIntakeAclaracionesCombinadas:
    """Integración de `_procesar_intake` con el lote inicial de aclaraciones (US2, spec 003)."""

    def test_tres_campos_pendientes_se_combinan_en_un_solo_turno(self, monkeypatch):
        respuestas = iter(["Es facturación, fue ayer, el error es 500"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
            [
                _evaluacion(
                    preguntas=[
                        PreguntaSugerida(
                            campo_objetivo="sistema_afectado", pregunta="¿Qué sistema?"
                        ),
                        PreguntaSugerida(campo_objetivo="sintoma", pregunta="¿Qué error?"),
                        PreguntaSugerida(campo_objetivo="momento", pregunta="¿Cuándo?"),
                    ],
                ),
                # única evaluación de la respuesta combinada — cubre los 3 campos
                _evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("no funciona")

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        assert caso.estado_informacion == "completa"
        assert len(caso.aclaraciones) == 3

    def test_una_sola_pregunta_pendiente_no_usa_el_camino_combinado(self, monkeypatch):
        """Con menos de 2 pendientes, el comportamiento es idéntico al existente (US3)."""
        respuestas = iter(["Fue ayer"])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(respuestas))
        motor = SecuenciaEvaluaciones(
            [
                _evaluacion(
                    sistema_presente=True,
                    sintoma_presente=True,
                    preguntas=[
                        PreguntaSugerida(campo_objetivo="momento", pregunta="¿Cuándo?"),
                    ],
                ),
                # evaluación de contradicción de la respuesta individual (camino existente)
                _evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True),
            ]
        )
        caso = Caso()
        caso.registrar_descripcion("el sistema de facturación falla con error 500")

        monkeypatch.setattr(cli, "evaluar_descripcion", motor)
        cli._procesar_intake(caso, MagicMock())

        assert caso.estado_informacion == "completa"
        momento_aclaracion = next(
            a for a in caso.aclaraciones if a.campo_objetivo == "momento"
        )
        assert momento_aclaracion.respuesta == "Fue ayer"


class TestRutaCandidataEnMensajeInicial:
    """Integración de `_procesar_intake` + `_solicitar_evidencia_logs` (US1, spec 003).

    Cubre los 3 escenarios de aceptación de la Historia 1 de `spec.md`.
    """

    def test_ruta_valida_en_mensaje_inicial_se_registra_sin_pedir_de_nuevo(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "facturacion.log").write_text("ERROR algo falló\n", encoding="utf-8")
        texto_inicial = (
            "el servicio de facturacion fallo a las 14:15, revisa facturacion.log"
        )
        entradas = iter([texto_inicial])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))
        motor = SecuenciaEvaluaciones(
            [_evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True)]
        )
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        ruta_candidata = cli._procesar_intake(caso, MagicMock())
        # si _solicitar_evidencia_logs pidiera la evidencia de nuevo, `entradas` (ya
        # agotado) lanzaría StopIteration — confirma que no se vuelve a preguntar.
        cli._solicitar_evidencia_logs(caso, ruta_candidata=ruta_candidata)

        assert caso.estado_informacion == "completa"
        assert len(caso.fuentes_logs) == 1
        assert caso.fuentes_logs[0].ruta == "facturacion.log"
        assert caso.fuentes_logs[0].origen == "ruta_usuario"

    def test_ruta_invalida_en_mensaje_inicial_difiere_el_error(self, monkeypatch):
        prompts_intake = []
        texto_inicial = "el servicio de facturacion fallo, revisa no-existe.log"
        entradas_intake = iter([texto_inicial])

        def _leer_entrada_intake(prompt):
            prompts_intake.append(prompt)
            return next(entradas_intake)

        monkeypatch.setattr(cli, "_leer_entrada", _leer_entrada_intake)
        motor = SecuenciaEvaluaciones(
            [_evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True)]
        )
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        ruta_candidata = cli._procesar_intake(caso, MagicMock())

        assert ruta_candidata == "no-existe.log"
        assert caso.descripcion_inicial.texto == texto_inicial
        # ningún prompt formulado durante el intake menciona el error de acceso:
        # la validación todavía no se ha intentado (research.md, Decisión 2)
        assert not any("No pude acceder" in p for p in prompts_intake)

        prompts_evidencia = []
        entradas_evidencia = iter(["ERROR único", ""])

        def _leer_entrada_evidencia(prompt):
            prompts_evidencia.append(prompt)
            return next(entradas_evidencia)

        monkeypatch.setattr(cli, "_leer_entrada", _leer_entrada_evidencia)
        cli._solicitar_evidencia_logs(caso, ruta_candidata=ruta_candidata)

        assert any("No pude acceder" in p for p in prompts_evidencia)
        assert caso.fuentes_logs == []
        assert any("ERROR único" in m["content"] for m in caso.mensajes)

    def test_sin_ruta_en_mensaje_inicial_devuelve_none_y_sigue_invitacion_normal(
        self, monkeypatch
    ):
        texto_inicial = "el servicio de facturacion fallo desde ayer"
        entradas = iter([texto_inicial])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))
        motor = SecuenciaEvaluaciones(
            [_evaluacion(sistema_presente=True, sintoma_presente=True, momento_presente=True)]
        )
        monkeypatch.setattr(cli, "evaluar_descripcion", motor)

        caso = Caso()
        ruta_candidata = cli._procesar_intake(caso, MagicMock())

        assert ruta_candidata is None

        # sin ruta candidata, _solicitar_evidencia_logs debe formular la invitación
        # interactiva normal (comportamiento de 002, sin cambios)
        entradas_evidencia = iter(["línea pegada", ""])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas_evidencia))
        cli._solicitar_evidencia_logs(caso, ruta_candidata=ruta_candidata)

        assert any("línea pegada" in m["content"] for m in caso.mensajes)


class TestSolicitarEvidenciaLogs:
    """Pruebas de US1 (spec 002): aportar evidencia de logs por ruta o contenido pegado."""

    def test_registra_fuente_por_ruta_accesible(self, monkeypatch, tmp_path):
        archivo = tmp_path / "app.log"
        archivo.write_text("ERROR algo falló\n", encoding="utf-8")
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: str(archivo))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert len(caso.fuentes_logs) == 1
        assert caso.fuentes_logs[0].ruta == str(archivo)
        assert caso.fuentes_logs[0].origen == "ruta_usuario"

    def test_ruta_inaccesible_permite_reintentar_con_ruta_valida(self, monkeypatch, tmp_path):
        archivo = tmp_path / "app.log"
        archivo.write_text("ERROR algo falló\n", encoding="utf-8")
        entradas = iter(["/ruta/que/no/existe.log", str(archivo)])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert caso.fuentes_logs[0].ruta == str(archivo)

    def test_ruta_inaccesible_permite_cambiar_a_pegar_contenido(self, monkeypatch):
        entradas = iter(["/ruta/que/no/existe.log", "ERROR único", ""])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert caso.fuentes_logs == []
        assert any("ERROR único" in m["content"] for m in caso.mensajes)

    def test_contenido_pegado_por_debajo_del_umbral_no_genera_archivo(self, monkeypatch):
        entradas = iter(["línea 1\nlínea 2\nlínea 3", ""])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert caso.fuentes_logs == []
        assert any("línea 1" in m["content"] for m in caso.mensajes)

    def test_contenido_pegado_por_encima_del_umbral_genera_archivo(self, monkeypatch, tmp_path):
        contenido = "\n".join(f"línea {i}" for i in range(1, 6))  # 5 líneas > umbral de 4
        entradas = iter([contenido, ""])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert len(caso.fuentes_logs) == 1
        assert caso.fuentes_logs[0].origen == "contenido_pegado"
        with open(caso.fuentes_logs[0].ruta, encoding="utf-8") as archivo:
            assert archivo.read().count("línea") == 5

    def test_acumula_contenido_pegado_fragmentado_en_varios_mensajes(self, monkeypatch):
        entradas = iter(["línea 1", "línea 2", "línea 3", "línea 4", "línea 5", ""])
        monkeypatch.setattr(cli, "_leer_entrada", lambda prompt: next(entradas))

        caso = Caso()
        cli._solicitar_evidencia_logs(caso)

        assert len(caso.fuentes_logs) == 1  # 5 líneas acumuladas > umbral de 4
        assert caso.fuentes_logs[0].origen == "contenido_pegado"

    def test_no_vuelve_a_solicitar_si_ya_hay_fuente_registrada(self, monkeypatch):
        def _fallar_si_se_llama(prompt):
            raise AssertionError("no debería pedirse evidencia de logs de nuevo")

        monkeypatch.setattr(cli, "_leer_entrada", _fallar_si_se_llama)

        caso = Caso()
        caso.fuentes_logs.append(
            cli.FuenteDeLogs(ruta="/tmp/ya-registrado.log", origen="ruta_usuario")
        )

        cli._solicitar_evidencia_logs(caso)  # no debe lanzar ni pedir entrada
