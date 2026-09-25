"""Pruebas unitarias de las herramientas de consulta a base de datos (`database/tools.py`).

Contra una base de datos SQLite real de prueba, sin mock del motor — mismo
criterio que `test_tools.py` (spec 002) usa archivos de logs reales.
"""

import json

import sqlalchemy as sa

from opssleuth.database.factory import FuenteDeBaseDeDatosConfigurada
from opssleuth.database.tools import MAXIMO_FILAS_POR_DEFECTO, crear_herramientas_bd
from opssleuth.domain.database_evidence import FuenteDeBaseDeDatos


def _fuente_de_prueba(tmp_path, filas_extra: int = 0) -> FuenteDeBaseDeDatosConfigurada:
    ruta_db = tmp_path / "prueba.db"
    engine = sa.create_engine(f"sqlite:///{ruta_db}")
    with engine.begin() as conexion:
        conexion.execute(
            sa.text("CREATE TABLE facturas (id INTEGER PRIMARY KEY, usuario_id INTEGER, estado TEXT)")
        )
        conexion.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT)"))
        conexion.execute(sa.text("INSERT INTO usuarios VALUES (1, 'Ana')"))
        conexion.execute(sa.text("INSERT INTO facturas VALUES (1007, 1, 'fallida')"))
        for i in range(filas_extra):
            conexion.execute(
                sa.text(f"INSERT INTO facturas VALUES ({2000 + i}, 1, 'ok')")
            )
    return FuenteDeBaseDeDatosConfigurada(
        engine=engine,
        fuente=FuenteDeBaseDeDatos(motor="sqlite", tablas_permitidas=["facturas", "usuarios"]),
        timeout_segundos=10,
    )


def _fuente_de_prueba_con_eventos(tmp_path) -> FuenteDeBaseDeDatosConfigurada:
    """Variante con una tercera tabla, para pruebas de cruces (Historia 3)."""
    ruta_db = tmp_path / "prueba_eventos.db"
    engine = sa.create_engine(f"sqlite:///{ruta_db}")
    with engine.begin() as conexion:
        conexion.execute(
            sa.text("CREATE TABLE facturas (id INTEGER PRIMARY KEY, usuario_id INTEGER, estado TEXT)")
        )
        conexion.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT)"))
        conexion.execute(
            sa.text(
                "CREATE TABLE eventos_servicio (id INTEGER PRIMARY KEY, servicio TEXT, estado TEXT)"
            )
        )
        conexion.execute(sa.text("INSERT INTO usuarios VALUES (1, 'Ana')"))
        conexion.execute(sa.text("INSERT INTO facturas VALUES (1007, 1, 'fallida')"))
        conexion.execute(
            sa.text("INSERT INTO eventos_servicio VALUES (1007, 'facturacion_db', 'timeout')")
        )
    return FuenteDeBaseDeDatosConfigurada(
        engine=engine,
        fuente=FuenteDeBaseDeDatos(
            motor="sqlite", tablas_permitidas=["facturas", "usuarios", "eventos_servicio"]
        ),
        timeout_segundos=10,
    )


class TestListarTablasDisponibles:
    def test_devuelve_las_tablas_configuradas(self, tmp_path):
        listar, _describir, _ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(listar.invoke({}))

        assert set(resultado["tablas"]) == {"facturas", "usuarios"}


class TestDescribirTabla:
    def test_devuelve_columnas_de_tabla_permitida(self, tmp_path):
        _listar, describir, _ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(describir.invoke({"tabla": "facturas"}))

        nombres_columnas = {columna["nombre"] for columna in resultado["columnas"]}
        assert nombres_columnas == {"id", "usuario_id", "estado"}

    def test_rechaza_tabla_fuera_de_alcance(self, tmp_path):
        _listar, describir, _ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(describir.invoke({"tabla": "sqlite_master"}))

        assert "error" in resultado


class TestEjecutarConsultaSQL:
    def test_ejecuta_consulta_simple_de_una_tabla(self, tmp_path):
        _listar, _describir, ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(
            ejecutar.invoke({"consulta": "SELECT * FROM facturas WHERE id = 1007"})
        )

        assert resultado["filas"] == [{"id": 1007, "usuario_id": 1, "estado": "fallida"}]
        assert resultado["hay_mas"] is False

    def test_ejecuta_consulta_con_join_entre_dos_tablas(self, tmp_path):
        _listar, _describir, ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(
            ejecutar.invoke(
                {
                    "consulta": (
                        "SELECT f.id, u.nombre FROM facturas f "
                        "JOIN usuarios u ON f.usuario_id = u.id WHERE f.id = 1007"
                    )
                }
            )
        )

        assert resultado["filas"] == [{"id": 1007, "nombre": "Ana"}]

    def test_intento_de_escritura_se_rechaza_y_no_modifica_los_datos(self, tmp_path):
        fuente = _fuente_de_prueba(tmp_path)
        _listar, _describir, ejecutar = crear_herramientas_bd(fuente)

        resultado = json.loads(
            ejecutar.invoke(
                {"consulta": "UPDATE facturas SET estado = 'pagada' WHERE id = 1007"}
            )
        )

        assert "error" in resultado
        with fuente.engine.connect() as conexion:
            estado = conexion.execute(
                sa.text("SELECT estado FROM facturas WHERE id = 1007")
            ).scalar()
        assert estado == "fallida"

    def test_tabla_fuera_de_alcance_se_rechaza_sin_ejecutar(self, tmp_path):
        _listar, _describir, ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(
            ejecutar.invoke({"consulta": "SELECT * FROM sqlite_master"})
        )

        assert "error" in resultado

    def test_mensaje_de_rechazo_no_revela_nombre_de_tabla_no_permitida(self, tmp_path):
        _listar, _describir, ejecutar = crear_herramientas_bd(_fuente_de_prueba(tmp_path))

        resultado = json.loads(
            ejecutar.invoke({"consulta": "SELECT * FROM tabla_secreta_interna"})
        )

        assert "tabla_secreta_interna" not in resultado["error"]

    def test_resultado_se_acota_y_marca_hay_mas(self, tmp_path):
        fuente = _fuente_de_prueba(tmp_path, filas_extra=30)
        _listar, _describir, ejecutar = crear_herramientas_bd(fuente)

        resultado = json.loads(ejecutar.invoke({"consulta": "SELECT * FROM facturas"}))

        assert len(resultado["filas"]) == MAXIMO_FILAS_POR_DEFECTO
        assert resultado["hay_mas"] is True

    def test_nunca_solicita_al_cursor_mas_de_maximo_mas_uno_filas(self, tmp_path, monkeypatch):
        """Verifica que el acotamiento usa `fetchmany` (research.md, Decisión 5) — nunca
        trae el resultado completo y trunca después."""
        fuente = _fuente_de_prueba(tmp_path, filas_extra=1000)
        _listar, _describir, ejecutar = crear_herramientas_bd(fuente)

        llamadas_fetchmany = []
        original_fetchmany = sa.CursorResult.fetchmany

        def fetchmany_espia(self, size=None):
            llamadas_fetchmany.append(size)
            return original_fetchmany(self, size)

        monkeypatch.setattr(sa.CursorResult, "fetchmany", fetchmany_espia)

        ejecutar.invoke({"consulta": "SELECT * FROM facturas"})

        assert llamadas_fetchmany == [MAXIMO_FILAS_POR_DEFECTO + 1]

    def test_ejecuta_consulta_con_cruce_entre_tres_tablas(self, tmp_path):
        fuente = _fuente_de_prueba_con_eventos(tmp_path)
        _listar, _describir, ejecutar = crear_herramientas_bd(fuente)

        resultado = json.loads(
            ejecutar.invoke(
                {
                    "consulta": (
                        "SELECT f.id, u.nombre, e.estado AS estado_servicio "
                        "FROM facturas f "
                        "JOIN usuarios u ON f.usuario_id = u.id "
                        "JOIN eventos_servicio e ON e.id = f.id "
                        "WHERE f.id = 1007"
                    )
                }
            )
        )

        assert resultado["filas"] == [
            {"id": 1007, "nombre": "Ana", "estado_servicio": "timeout"}
        ]
