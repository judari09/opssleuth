"""Pruebas adversariales de `validar_consulta` — la barandilla de seguridad central (Historia 2)."""

import pytest

from opssleuth.database.validacion import validar_consulta

TABLAS_PERMITIDAS = ["facturas", "usuarios", "eventos_servicio"]


class TestSentenciasDeEscrituraRechazadas:
    @pytest.mark.parametrize(
        "consulta",
        [
            "INSERT INTO facturas (id, estado) VALUES (1, 'pagada')",
            "UPDATE facturas SET estado = 'pagada' WHERE id = 1007",
            "DELETE FROM facturas WHERE id = 1007",
            "CREATE TABLE nueva (id INTEGER)",
            "ALTER TABLE facturas ADD COLUMN nueva TEXT",
            "DROP TABLE facturas",
            "TRUNCATE TABLE facturas",
        ],
    )
    def test_rechaza_cada_variante_de_escritura_o_ddl(self, consulta):
        resultado = validar_consulta(consulta, TABLAS_PERMITIDAS)

        assert resultado.es_valida is False
        assert resultado.motivo_rechazo is not None


class TestSentenciasMultiplesRechazadas:
    def test_rechaza_sentencia_de_escritura_tras_un_select_valido(self):
        resultado = validar_consulta(
            "SELECT * FROM facturas; DROP TABLE facturas;", TABLAS_PERMITIDAS
        )

        assert resultado.es_valida is False

    def test_rechaza_dos_selects_separados_por_punto_y_coma(self):
        resultado = validar_consulta(
            "SELECT * FROM facturas; SELECT * FROM usuarios;", TABLAS_PERMITIDAS
        )

        assert resultado.es_valida is False


class TestTablasFueraDeAlcanceRechazadas:
    def test_rechaza_tabla_no_permitida_en_select_simple(self):
        resultado = validar_consulta("SELECT * FROM sqlite_master", TABLAS_PERMITIDAS)

        assert resultado.es_valida is False

    def test_rechaza_join_que_referencia_tabla_no_permitida(self):
        resultado = validar_consulta(
            "SELECT f.id FROM facturas f JOIN otra_tabla o ON f.id = o.factura_id",
            TABLAS_PERMITIDAS,
        )

        assert resultado.es_valida is False

    def test_rechaza_subconsulta_que_referencia_tabla_fuera_de_alcance(self):
        resultado = validar_consulta(
            "SELECT * FROM facturas WHERE usuario_id IN (SELECT id FROM otra_tabla)",
            TABLAS_PERMITIDAS,
        )

        assert resultado.es_valida is False

    def test_rechaza_cte_que_referencia_tabla_fuera_de_alcance(self):
        resultado = validar_consulta(
            "WITH x AS (SELECT id FROM otra_tabla) SELECT * FROM x",
            TABLAS_PERMITIDAS,
        )

        assert resultado.es_valida is False

    def test_motivo_de_rechazo_no_revela_el_nombre_de_la_tabla_no_permitida(self):
        resultado = validar_consulta(
            "SELECT * FROM tabla_secreta_interna", TABLAS_PERMITIDAS
        )

        assert "tabla_secreta_interna" not in resultado.motivo_rechazo


class TestNombresDeTablaNormalizados:
    def test_acepta_nombre_de_tabla_con_mayusculas_distintas(self):
        resultado = validar_consulta("SELECT * FROM FACTURAS", TABLAS_PERMITIDAS)

        assert resultado.es_valida is True

    def test_acepta_nombre_de_tabla_calificado_por_esquema(self):
        resultado = validar_consulta("SELECT * FROM main.facturas", TABLAS_PERMITIDAS)

        assert resultado.es_valida is True


class TestConsultasValidasAceptadas:
    def test_acepta_select_simple_de_una_tabla(self):
        resultado = validar_consulta(
            "SELECT * FROM facturas WHERE id = 1007", TABLAS_PERMITIDAS
        )

        assert resultado.es_valida is True

    def test_acepta_join_entre_tres_tablas_dentro_de_alcance(self):
        resultado = validar_consulta(
            """
            SELECT f.id, u.nombre, e.estado
            FROM facturas f
            JOIN usuarios u ON f.usuario_id = u.id
            JOIN eventos_servicio e ON e.id = f.id
            """,
            TABLAS_PERMITIDAS,
        )

        assert resultado.es_valida is True

    def test_acepta_cte_cuyas_tablas_internas_estan_permitidas(self):
        resultado = validar_consulta(
            "WITH x AS (SELECT id FROM facturas) SELECT * FROM x JOIN usuarios ON x.id = usuarios.id",
            TABLAS_PERMITIDAS,
        )

        assert resultado.es_valida is True


class TestEntradaNoSQLRechazada:
    def test_rechaza_texto_que_no_es_sql(self):
        resultado = validar_consulta("esto no es SQL en absoluto !!!", TABLAS_PERMITIDAS)

        assert resultado.es_valida is False

    def test_rechaza_cadena_vacia(self):
        resultado = validar_consulta("", TABLAS_PERMITIDAS)

        assert resultado.es_valida is False
