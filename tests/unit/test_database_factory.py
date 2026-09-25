"""Pruebas unitarias de `crear_motor_bd` contra una base de datos SQLite real."""

import pytest
import sqlalchemy as sa

from opssleuth.database.factory import (
    TablasPermitidasNoConfiguradasError,
    crear_motor_bd,
)


def _crear_base_de_datos_de_prueba(ruta) -> None:
    engine = sa.create_engine(f"sqlite:///{ruta}")
    with engine.begin() as conexion:
        conexion.execute(
            sa.text("CREATE TABLE facturas (id INTEGER PRIMARY KEY, estado TEXT)")
        )
        conexion.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT)"))
        conexion.execute(sa.text("INSERT INTO facturas VALUES (1007, 'fallida')"))
    engine.dispose()


class TestCrearMotorBD:
    def test_sin_url_devuelve_none(self, monkeypatch):
        monkeypatch.delenv("OPSSLEUTH_DB_URL", raising=False)
        monkeypatch.delenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", raising=False)

        assert crear_motor_bd() is None

    def test_url_con_tablas_permitidas_validas_construye_fuente(self, monkeypatch, tmp_path):
        ruta_db = tmp_path / "prueba.db"
        _crear_base_de_datos_de_prueba(ruta_db)
        monkeypatch.setenv("OPSSLEUTH_DB_URL", f"sqlite:///{ruta_db}")
        monkeypatch.setenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", "facturas,usuarios")

        configurada = crear_motor_bd()

        assert configurada is not None
        assert configurada.fuente.motor == "sqlite"
        assert set(configurada.fuente.tablas_permitidas) == {"facturas", "usuarios"}
        assert configurada.timeout_segundos == 10

    def test_url_sin_tablas_permitidas_lanza_error(self, monkeypatch, tmp_path):
        ruta_db = tmp_path / "prueba.db"
        _crear_base_de_datos_de_prueba(ruta_db)
        monkeypatch.setenv("OPSSLEUTH_DB_URL", f"sqlite:///{ruta_db}")
        monkeypatch.delenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", raising=False)

        with pytest.raises(TablasPermitidasNoConfiguradasError):
            crear_motor_bd()

    def test_url_con_tablas_permitidas_vacia_lanza_error(self, monkeypatch, tmp_path):
        ruta_db = tmp_path / "prueba.db"
        _crear_base_de_datos_de_prueba(ruta_db)
        monkeypatch.setenv("OPSSLEUTH_DB_URL", f"sqlite:///{ruta_db}")
        monkeypatch.setenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", "   ")

        with pytest.raises(TablasPermitidasNoConfiguradasError):
            crear_motor_bd()

    def test_tabla_configurada_inexistente_se_omite_sin_lanzar(self, monkeypatch, tmp_path):
        ruta_db = tmp_path / "prueba.db"
        _crear_base_de_datos_de_prueba(ruta_db)
        monkeypatch.setenv("OPSSLEUTH_DB_URL", f"sqlite:///{ruta_db}")
        monkeypatch.setenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", "facturas,tabla_inexistente")

        configurada = crear_motor_bd()

        assert configurada.fuente.tablas_permitidas == ["facturas"]

    def test_timeout_configurable_por_variable_de_entorno(self, monkeypatch, tmp_path):
        ruta_db = tmp_path / "prueba.db"
        _crear_base_de_datos_de_prueba(ruta_db)
        monkeypatch.setenv("OPSSLEUTH_DB_URL", f"sqlite:///{ruta_db}")
        monkeypatch.setenv("OPSSLEUTH_DB_TABLAS_PERMITIDAS", "facturas")
        monkeypatch.setenv("OPSSLEUTH_DB_TIMEOUT_SEGUNDOS", "30")

        configurada = crear_motor_bd()

        assert configurada.timeout_segundos == 30
