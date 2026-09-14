"""Pruebas unitarias de las herramientas de búsqueda de logs (sin mock de modelo)."""

import json

import pytest

from opssleuth.evidence.tools import crear_herramienta_preguntar, crear_herramientas_busqueda

CONTENIDO_PRUEBA = """\
2026-09-03T14:01:02 INFO servicio-facturacion iniciado
2026-09-03T14:02:10 INFO factura creada id=1001
2026-09-03T14:15:47 ERROR servicio-facturacion timeout al conectar con base de datos
2026-09-03T14:15:48 ERROR factura id=1002 fallo con codigo 500
2026-09-03T14:20:00 INFO factura creada id=1003
"""


@pytest.fixture
def archivo_logs(tmp_path):
    ruta = tmp_path / "facturacion.log"
    ruta.write_text(CONTENIDO_PRUEBA, encoding="utf-8")
    return str(ruta)


@pytest.fixture
def herramientas(archivo_logs):
    buscar_texto, leer_contexto, contar_lineas = crear_herramientas_busqueda(archivo_logs)
    return {
        "buscar_texto": buscar_texto,
        "leer_contexto": leer_contexto,
        "contar_lineas": contar_lineas,
    }


class TestBuscarTexto:
    def test_encuentra_coincidencias(self, herramientas):
        resultado = json.loads(herramientas["buscar_texto"].invoke({"patron": "ERROR"}))

        assert len(resultado["coincidencias"]) == 2
        assert resultado["coincidencias"][0]["numero_linea"] == 3
        assert "timeout" in resultado["coincidencias"][0]["contenido"]
        assert resultado["hay_mas"] is False

    def test_sin_coincidencias(self, herramientas):
        resultado = json.loads(
            herramientas["buscar_texto"].invoke({"patron": "PATRON_INEXISTENTE"})
        )

        assert resultado["coincidencias"] == []
        assert resultado["hay_mas"] is False

    def test_respeta_maximo_resultados_y_marca_hay_mas(self, herramientas):
        resultado = json.loads(
            herramientas["buscar_texto"].invoke({"patron": "INFO", "maximo_resultados": 1})
        )

        assert len(resultado["coincidencias"]) == 1
        assert resultado["hay_mas"] is True

    def test_incluye_ventana_de_contexto(self, herramientas):
        resultado = json.loads(herramientas["buscar_texto"].invoke({"patron": "timeout"}))

        contexto = resultado["coincidencias"][0]["contexto"]
        assert any("factura creada id=1001" in linea for linea in contexto)


class TestLeerContexto:
    def test_lee_lineas_alrededor_del_numero_indicado(self, herramientas):
        resultado = json.loads(
            herramientas["leer_contexto"].invoke(
                {"numero_linea": 3, "lineas_antes": 1, "lineas_despues": 1}
            )
        )

        numeros = [linea["numero_linea"] for linea in resultado["lineas"]]
        assert numeros == [2, 3, 4]

    def test_recorta_en_los_bordes_del_archivo(self, herramientas):
        resultado = json.loads(
            herramientas["leer_contexto"].invoke(
                {"numero_linea": 1, "lineas_antes": 5, "lineas_despues": 1}
            )
        )

        numeros = [linea["numero_linea"] for linea in resultado["lineas"]]
        assert numeros[0] == 1


class TestContarLineas:
    def test_cuenta_todas_las_lineas(self, herramientas):
        resultado = json.loads(herramientas["contar_lineas"].invoke({}))

        assert resultado["total_lineas"] == 5


class TestPreguntarAlUsuario:
    def test_invoca_el_callback_inyectado(self):
        llamadas = []

        def callback(pregunta):
            llamadas.append(pregunta)
            return "Es un microservicio de facturación en Python."

        herramienta = crear_herramienta_preguntar(callback)
        respuesta = herramienta.invoke({"pregunta": "¿Qué tecnología usa el sistema?"})

        assert llamadas == ["¿Qué tecnología usa el sistema?"]
        assert respuesta == "Es un microservicio de facturación en Python."
