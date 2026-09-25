"""Genera una base de datos SQLite de prueba para el flujo de consultas a base
de datos (spec 005), narrativamente consistente con el incidente ya descrito
en `test_logs/facturacion.log` (specs 002/003/004): el mismo conjunto de
facturas, los mismos clientes y los mismos eventos de servicio alrededor del
timeout de las 14:15-14:17 del 2026-09-07.

Uso::

    uv run python test_db/generar_base_de_datos.py

Crea (o sobrescribe) `test_db/facturacion.db`. El esquema y los nombres de
tabla/columna coinciden con los ya documentados en
`specs/005-consultas-base-datos/quickstart.md` — usar exactamente esos
nombres al configurar `OPSSLEUTH_DB_TABLAS_PERMITIDAS`.
"""

from __future__ import annotations

import os
import sqlite3

RUTA_BASE_DE_DATOS = os.path.join(os.path.dirname(__file__), "facturacion.db")

# (id, nombre, email) — las mismas cuentas cliente que aparecen en
# test_logs/facturacion.log ("cliente=empresa-acme", etc.)
USUARIOS = [
    (1, "empresa-acme", "contacto@empresa-acme.com"),
    (2, "distribuidora-sur", "facturacion@distribuidora-sur.com"),
    (3, "comercial-norte", "pagos@comercial-norte.com"),
]

# (id, usuario_id, monto, estado, creada_en) — las 11 facturas del log, en el
# mismo orden y con los mismos horarios; 1007/1008/1009 quedan en "fallida"
# (mismo desenlace que el log: nunca se completó su generación).
FACTURAS = [
    (1001, 1, 1250.00, "pagada", "2026-09-07T09:02:11"),
    (1002, 2, 430.50, "pagada", "2026-09-07T09:47:33"),
    (1003, 1, 980.00, "pagada", "2026-09-07T10:30:18"),
    (1004, 3, 210.75, "pagada", "2026-09-07T11:40:09"),
    (1005, 2, 675.20, "pagada", "2026-09-07T13:02:57"),
    (1006, 1, 1500.00, "pagada", "2026-09-07T14:01:02"),
    (1007, 1, 890.00, "fallida", "2026-09-07T14:15:48"),
    (1008, 1, 340.00, "fallida", "2026-09-07T14:16:04"),
    (1009, 1, 560.00, "fallida", "2026-09-07T14:17:26"),
    (1010, 3, 340.00, "pagada", "2026-09-07T14:32:02"),
    (1011, 2, 520.00, "pagada", "2026-09-07T15:45:12"),
]

# (id, servicio, estado, detalle, ocurrido_en) — los mismos eventos WARN/ERROR/
# INFO de facturacion_db que aparecen en test_logs/facturacion.log.
EVENTOS_SERVICIO = [
    (1, "facturacion_db", "warn", "tiempo de respuesta elevado (820ms)", "2026-09-07T13:30:41"),
    (2, "facturacion_db", "warn", "pool de conexiones cerca del limite (18/20)", "2026-09-07T14:09:30"),
    (3, "facturacion_db", "timeout", "timeout al conectar tras 5000ms", "2026-09-07T14:15:47"),
    (4, "facturacion_db", "timeout", "timeout al conectar tras 5000ms", "2026-09-07T14:16:03"),
    (5, "facturacion_db", "reintento", "reintentando conexion (intento 1/3)", "2026-09-07T14:16:10"),
    (6, "facturacion_db", "timeout", "timeout al conectar tras 5000ms", "2026-09-07T14:17:25"),
    (7, "facturacion_db", "recuperado", "conexion restablecida", "2026-09-07T14:31:15"),
]


def generar() -> None:
    """Crea `facturacion.db` desde cero, con el esquema y los datos de prueba."""
    if os.path.exists(RUTA_BASE_DE_DATOS):
        os.remove(RUTA_BASE_DE_DATOS)

    conexion = sqlite3.connect(RUTA_BASE_DE_DATOS)
    try:
        conexion.executescript(
            """
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                email TEXT NOT NULL
            );

            CREATE TABLE facturas (
                id INTEGER PRIMARY KEY,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                monto REAL NOT NULL,
                estado TEXT NOT NULL,
                creada_en TEXT NOT NULL
            );

            CREATE TABLE eventos_servicio (
                id INTEGER PRIMARY KEY,
                servicio TEXT NOT NULL,
                estado TEXT NOT NULL,
                detalle TEXT NOT NULL,
                ocurrido_en TEXT NOT NULL
            );
            """
        )
        conexion.executemany("INSERT INTO usuarios VALUES (?, ?, ?)", USUARIOS)
        conexion.executemany("INSERT INTO facturas VALUES (?, ?, ?, ?, ?)", FACTURAS)
        conexion.executemany(
            "INSERT INTO eventos_servicio VALUES (?, ?, ?, ?, ?)", EVENTOS_SERVICIO
        )
        conexion.commit()
    finally:
        conexion.close()

    print(f"Base de datos de prueba creada en: {RUTA_BASE_DE_DATOS}")
    print(
        "Configura en .env: OPSSLEUTH_DB_URL=sqlite:///"
        + RUTA_BASE_DE_DATOS.replace("\\", "/")
    )
    print("OPSSLEUTH_DB_TABLAS_PERMITIDAS=usuarios,facturas,eventos_servicio")


if __name__ == "__main__":
    generar()
