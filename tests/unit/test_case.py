"""Pruebas unitarias de las reglas de dominio de ``Caso``."""

import pytest

from opssleuth.domain.case import (
    Aclaracion,
    CampoExtraido,
    Caso,
    DescripcionVaciaError,
)


class TestRegistrarDescripcion:
    """Pruebas de ``Caso.registrar_descripcion`` (FR-002, FR-011)."""

    def test_registra_descripcion_no_vacia(self):
        caso = Caso()
        descripcion = caso.registrar_descripcion(
            "El módulo de facturación devuelve error 500 desde ayer."
        )

        assert caso.descripcion_inicial is descripcion
        assert descripcion.texto == "El módulo de facturación devuelve error 500 desde ayer."
        assert caso.estado_informacion == "pendiente_aclaracion"

    def test_recorta_espacios_en_los_extremos(self):
        caso = Caso()
        caso.registrar_descripcion("  no funciona  ")

        assert caso.descripcion_inicial.texto == "no funciona"

    @pytest.mark.parametrize("texto_vacio", ["", "   ", "\n\t"])
    def test_rechaza_descripcion_vacia_o_solo_espacios(self, texto_vacio):
        caso = Caso()

        with pytest.raises(DescripcionVaciaError):
            caso.registrar_descripcion(texto_vacio)

        assert caso.descripcion_inicial is None
        assert caso.estado_informacion == "pendiente_descripcion"


class TestEstadoInformacion:
    """Pruebas de las transiciones de ``Caso.estado_informacion`` (FR-008, FR-009)."""

    def test_estado_inicial_es_pendiente_descripcion(self):
        assert Caso().estado_informacion == "pendiente_descripcion"

    def test_marcar_informacion_completa_requiere_descripcion(self):
        caso = Caso()

        with pytest.raises(DescripcionVaciaError):
            caso.marcar_informacion_completa()

    def test_marcar_informacion_completa_tras_registrar_descripcion(self):
        caso = Caso()
        caso.registrar_descripcion("no funciona el login")

        caso.marcar_informacion_completa()

        assert caso.estado_informacion == "completa"


class TestEstadoCaso:
    """Pruebas del ciclo de vida de ``Caso.estado_caso`` (FR-013, FR-014)."""

    def test_estado_inicial_es_activo(self):
        assert Caso().estado_caso == "activo"

    def test_finalizar_marca_estado_terminal(self):
        caso = Caso()

        caso.finalizar()

        assert caso.estado_caso == "finalizado"


class TestContextoConversacional:
    """Pruebas de acumulación de contexto y resumen (FR-004, FR-005)."""

    def test_agregar_mensaje_preserva_orden(self):
        caso = Caso()

        caso.agregar_mensaje("user", "primer mensaje")
        caso.agregar_mensaje("assistant", "segunda respuesta")

        assert caso.mensajes == [
            {"role": "user", "content": "primer mensaje"},
            {"role": "assistant", "content": "segunda respuesta"},
        ]

    def test_resumen_sin_descripcion_indica_pendiente(self):
        caso = Caso()

        assert "no se ha registrado" in caso.resumen().lower()

    def test_resumen_incluye_descripcion_original_y_no_se_pierde_tras_aclaraciones(self):
        caso = Caso()
        caso.registrar_descripcion("El módulo de facturación devuelve error 500 desde ayer.")
        caso.agregar_aclaracion(
            Aclaracion(
                pregunta="¿Qué aplicación se ve afectada?",
                campo_objetivo="sistema_afectado",
                respuesta="Facturación",
            )
        )

        resumen = caso.resumen()

        assert "El módulo de facturación devuelve error 500 desde ayer." in resumen
        assert "¿Qué aplicación se ve afectada?" in resumen
        assert "Facturación" in resumen

    def test_resumen_marca_aclaraciones_sin_confirmar(self):
        caso = Caso()
        caso.registrar_descripcion("no funciona")
        caso.agregar_aclaracion(
            Aclaracion(
                pregunta="¿Cuándo empezó a ocurrir?",
                campo_objetivo="momento",
                sin_confirmar=True,
            )
        )

        resumen = caso.resumen()

        assert "sin confirmar" in resumen.lower()

    def test_resumen_senala_contradiccion_sin_descartar_datos(self):
        caso = Caso()
        caso.registrar_descripcion("El error empezó ayer.")
        caso.agregar_aclaracion(
            Aclaracion(
                pregunta="¿Cuándo exactamente notaste el problema?",
                campo_objetivo="momento",
                respuesta="En realidad empezó hace una semana.",
                contradice_descripcion_original=True,
            )
        )

        resumen = caso.resumen()

        assert "El error empezó ayer." in resumen
        assert "En realidad empezó hace una semana." in resumen
        assert "contradice" in resumen.lower()


class TestExtensionEvidenciaLogs:
    """Pruebas de la extensión de ``Caso`` para la spec 002 (creado_en/fuentes_logs/apreciacion_logs)."""

    def test_creado_en_se_puebla_automaticamente(self):
        caso = Caso()

        assert caso.creado_en is not None

    def test_fuentes_logs_vacia_por_defecto(self):
        assert Caso().fuentes_logs == []

    def test_apreciacion_logs_none_por_defecto(self):
        assert Caso().apreciacion_logs is None


class TestDescripcionProblemaCamposFaltantes:
    """Pruebas de ``DescripcionProblema.campos_faltantes`` (FR-006)."""

    def test_todos_los_campos_faltantes_por_defecto(self):
        caso = Caso()
        descripcion = caso.registrar_descripcion("no funciona")

        assert descripcion.campos_faltantes() == ["sistema_afectado", "sintoma", "momento"]

    def test_ningun_campo_faltante_cuando_todos_presentes(self):
        caso = Caso()
        descripcion = caso.registrar_descripcion(
            "El módulo de facturación devuelve error 500 desde ayer."
        )
        descripcion.sistema_afectado = CampoExtraido(presente=True, valor="Facturación")
        descripcion.sintoma = CampoExtraido(presente=True, valor="Error 500")
        descripcion.momento = CampoExtraido(presente=True, valor="Desde ayer")

        assert descripcion.campos_faltantes() == []
