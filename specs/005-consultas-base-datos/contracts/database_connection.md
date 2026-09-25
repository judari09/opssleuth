# Contrato: Conexión a Base de Datos (`crear_motor_bd`)

Punto de integración único con SQLAlchemy (ver `research.md`, Decisión 1) — mecanismo de
modularidad para esta funcionalidad, análogo a `crear_modelo_chat()` para el motor de modelo de
lenguaje (`specs/002-busqueda-logs/contracts/chat_model_provider.md`), pero confinado por el
camino **por defecto** del Principio II (no la excepción de "estándar de abstracción de terceros
maduro" — ver `research.md`, Decisión 1, para el porqué de esa distinción).

## Interfaz

```python
def crear_motor_bd() -> FuenteDeBaseDeDatosConfigurada | None:
    """Lee OPSSLEUTH_DB_URL y OPSSLEUTH_DB_TABLAS_PERMITIDAS. Si OPSSLEUTH_DB_URL
    no está configurada, devuelve None (fuente no disponible — Edge Case de
    spec.md). Si está configurada pero OPSSLEUTH_DB_TABLAS_PERMITIDAS falta o
    está vacía, lanza TablasPermitidasNoConfiguradasError. En caso contrario,
    construye el Engine de SQLAlchemy, valida contra la base de datos real qué
    tablas de OPSSLEUTH_DB_TABLAS_PERMITIDAS existen efectivamente, y devuelve
    un objeto que agrupa el Engine (uso interno de database/tools.py, nunca
    expuesto a domain/) y la FuenteDeBaseDeDatos de dominio correspondiente
    (sin credenciales — ver data-model.md)."""
    ...
```

`crear_motor_bd()` NO realiza ninguna consulta de negocio — solo construye y valida la conexión,
mismo criterio ya aplicado a `crear_modelo_chat()` (Regla 5 de `chat_model_provider.md`: los
errores de comunicación se propagan en el punto donde se invoca al modelo, no en la fábrica).

## Reglas del contrato

1. `crear_motor_bd()` es la ÚNICA función del proyecto que instancia un `Engine` de SQLAlchemy —
   cualquier otro módulo que necesite ejecutar una consulta DEBE recibirlo como parámetro, nunca
   construirlo por su cuenta.
2. `OPSSLEUTH_DB_URL` (sin valor por defecto) es el único mecanismo de configuración de la
   conexión — si no está definida, la fuente de base de datos simplemente no está disponible para
   ningún caso (Edge Case de `spec.md`); esto NO es un error.
3. `OPSSLEUTH_DB_TABLAS_PERMITIDAS` (lista separada por comas, sin valor por defecto) DEBE estar
   configurada y no vacía cuando `OPSSLEUTH_DB_URL` lo está — si falta, `crear_motor_bd()` DEBE
   lanzar `TablasPermitidasNoConfiguradasError` antes de construir ninguna conexión (ver
   `research.md`, Decisión 4). Nunca existe un valor por defecto equivalente a "todas las tablas".
4. Ninguna credencial ni la URL de conexión completa DEBE terminar en un objeto de dominio visible
   desde `Caso` (`FuenteDeBaseDeDatos` solo expone `motor`, derivado del esquema de la URL, nunca
   la URL en sí — ver `data-model.md`).
5. `crear_motor_bd()` DEBE verificar, contra la base de datos real, qué tablas de
   `OPSSLEUTH_DB_TABLAS_PERMITIDAS` existen efectivamente — las que no existan se omiten (con una
   advertencia registrada, no un fallo del arranque completo) en vez de dejar que una consulta
   futura falle de forma menos clara al referenciarlas.
6. `OPSSLEUTH_DB_TIMEOUT_SEGUNDOS` (opcional, por defecto 10) configura el tiempo de espera por
   consulta aplicado vía `execution_options`, cuando el DBAPI del dialecto configurado lo soporta
   (mejor esfuerzo — ver `research.md`, Decisión 8).
7. Si `OPSSLEUTH_DB_URL` está configurada pero la base de datos no es accesible al momento de
   verificar las tablas permitidas (credenciales inválidas, host inaccesible), `crear_motor_bd()`
   DEBE lanzar `ConexionBaseDeDatosError` — un fallo de comunicación en tiempo de ejecución, no un
   error de configuración (a diferencia de la Regla 3) — que el llamador (`opssleuth.cli`) DEBE
   capturar e informar, continuando el resto de la conversación sin evidencia de base de datos
   (US1, Escenario 3 de `spec.md`).

## Implementación

- SQLite (soporte incluido en la biblioteca estándar de Python, sin driver adicional) es el motor
  de referencia usado en `quickstart.md` y en las pruebas automatizadas de esta spec. Otros
  motores (PostgreSQL, MySQL, etc.) requieren que quien opere la herramienta instale el driver
  DBAPI correspondiente (p. ej. `psycopg`) — no son dependencias de este proyecto.
- Variables de entorno nuevas: `OPSSLEUTH_DB_URL`, `OPSSLEUTH_DB_TABLAS_PERMITIDAS`,
  `OPSSLEUTH_DB_TIMEOUT_SEGUNDOS` (opcional). Se suman a las ya establecidas en
  `specs/ESTADO_SPECS.md` — ninguna reemplaza ni reutiliza el propósito de una existente.

**Nota de verificación de implementación**: los nombres exactos de los parámetros de
`Connection.execution_options` y del mecanismo de "solo lectura" por dialecto (Regla de
`research.md`, Decisión 3) deben confirmarse contra la documentación de `sqlalchemy` instalada al
momento de implementar — no se asumen aquí (mismo criterio de riesgo ya aplicado en
`chat_model_provider.md`).
