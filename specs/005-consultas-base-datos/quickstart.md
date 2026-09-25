# Quickstart: Consultas a Bases de Datos

Guía de validación manual de extremo a extremo para esta funcionalidad. No repite detalles de
diseño — ver `data-model.md`, `research.md` y `contracts/` para eso. Requiere que las fases
previas (001-004) ya estén validadas por separado — esta spec añade una nueva fuente de evidencia
independiente de la de logs.

## Prerrequisitos

- Los mismos de `specs/001-recepcion-incidencia/quickstart.md` (Python 3.13, `uv sync`, proveedor
  `claude`/`ollama`/`gemini` configurado vía `OPSSLEUTH_LLM_PROVIDER`).
- Una base de datos SQLite local de prueba. Se genera con:

  ```sh
  uv run python test_db/generar_base_de_datos.py
  ```

  Crea `test_db/facturacion.db` (no versionado — regenerable, ver `.gitignore`) con 3 tablas
  (`usuarios`, `facturas`, `eventos_servicio`) narrativamente consistentes con
  `test_logs/facturacion.log`: las mismas 11 facturas, los mismos 3 clientes
  (`empresa-acme`/`distribuidora-sur`/`comercial-norte`) y los mismos eventos de
  `facturacion_db` (WARN de degradación, timeouts, reintento, recuperación) alrededor del
  incidente de las 14:15-14:17 del 2026-09-07 — las facturas `1007`/`1008`/`1009` quedan en
  estado `fallida`, el resto en `pagada`.

## Configurar el acceso (una sola vez)

En `.env` (ver Clarifications de `spec.md`, Sesión 2026-09-21):

```sh
OPSSLEUTH_DB_URL=sqlite:///test_db/facturacion.db
OPSSLEUTH_DB_TABLAS_PERMITIDAS=usuarios,facturas,eventos_servicio
```

## Ejecutar el agente

Igual que en 001-004:

```sh
uv run python -m opssleuth.cli
```

## Escenarios de validación

### 1. Encontrar evidencia relevante en una tabla (US1 / FR-001, FR-004, FR-011)

1. Iniciar un caso y describir un incidente que mencione un identificador presente en la base de
   datos de prueba (p. ej. "la factura 1007 falló a las 14:15").
2. **Esperado**: el sistema anuncia visiblemente que va a consultar la base de datos (FR-011)
   antes de mostrar el resultado, consulta la tabla `facturas`, y localiza el registro
   correspondiente sin que el usuario tenga que escribir SQL.

### 2. Sin resultados relacionados (US1 / Escenario 2)

1. Describir un incidente que no tiene ningún registro relacionado en la base de datos de prueba.
2. **Esperado**: el sistema refleja explícitamente que no encontró evidencia relacionada en la
   base de datos, en vez de omitir el resultado o fabricar una conclusión.

### 3. Base de datos inaccesible (US1 / Escenario 3, FR-007)

1. Configurar `OPSSLEUTH_DB_URL` apuntando a un archivo SQLite inexistente o a una URL con
   credenciales inválidas, y repetir el escenario 1.
2. **Esperado**: el sistema informa que no pudo completar la consulta a la base de datos y
   continúa el resto del diagnóstico con normalidad, sin bloquear la conversación.

### 4. Rechazo de escritura o de tabla fuera de alcance (US2 / FR-002, FR-003, FR-008)

1. Con la configuración del prerrequisito, escribir una descripción de incidente que
   intente inducir al sistema a modificar datos (p. ej. "actualiza el estado de la factura 1007 a
   pagada") o a consultar una tabla no incluida en `OPSSLEUTH_DB_TABLAS_PERMITIDAS` (p. ej.
   mencionar una tabla `sqlite_master` o cualquier tabla no listada).
2. **Esperado**: ninguna operación de escritura ni ninguna consulta fuera de alcance llega a
   ejecutarse contra la base de datos real — verificar además, tras el intento, que los datos de
   prueba no cambiaron (`SELECT estado FROM facturas WHERE id = 1007` sigue devolviendo
   `'fallida'`). El sistema informa que esa evidencia no está disponible dentro del alcance
   permitido, sin interrumpir el resto del diagnóstico.

### 5. Correlación con cruce de tres tablas (US3 / FR-005)

1. Describir un incidente cuya causa raíz solo es identificable relacionando `facturas`,
   `usuarios` y `eventos_servicio` (p. ej. "¿qué cliente fue afectado por el timeout del servicio
   de facturación que causó el fallo de la factura 1007?").
2. **Esperado**: el sistema construye y ejecuta una consulta que cruza las tres tablas y obtiene
   el resultado correlacionado (el cliente `empresa-acme`, y los eventos de timeout de
   `facturacion_db` entre las 14:15 y 14:17), sin que el usuario tenga que indicar cómo relacionar
   las tablas — confirmado en vivo contra un proveedor real el 2026-09-23.

### 6. Volumen de resultados acotado (US3 / Escenario 3, FR-006)

1. Insertar en la base de datos de prueba varias decenas de filas adicionales que coincidirían con
   una consulta amplia (p. ej. muchas facturas del mismo usuario).
2. **Esperado**: la apreciación se limita a un conjunto acotado de filas representativas e indica
   explícitamente que existen más resultados disponibles, en vez de intentar listarlos todos.

### 7. Independencia respecto a la evidencia de logs (Edge Case, Clarifications Sesión 2026-09-21)

1. Completar un caso sin aportar ninguna evidencia de logs (declinar el paso de logs de spec 002),
   pero con la base de datos de prueba configurada y un incidente que sí es verificable en ella.
2. **Esperado**: el sistema igualmente consulta la base de datos y presenta la evidencia
   encontrada — la ausencia de evidencia de logs no bloquea ni condiciona esta fuente.

### 8. No regresión: comportamiento existente sin base de datos configurada (SC-004)

1. Sin `OPSSLEUTH_DB_URL` configurada, ejecutar íntegramente los escenarios de
   `specs/001-recepcion-incidencia/quickstart.md`, `specs/002-busqueda-logs/quickstart.md`,
   `specs/003-conversacion-adaptativa/quickstart.md` y `specs/004-cli-chat-enriquecida/quickstart.md`.
2. **Esperado**: el comportamiento es idéntico al ya documentado en esas specs — ningún mensaje ni
   paso adicional relacionado con base de datos aparece cuando no hay ninguna configurada.

## Notas

- Todos los escenarios anteriores corresponden 1:1 a los criterios de aceptación en `spec.md`. Un
  escenario que no se comporte como se describe indica una regresión respecto a la especificación,
  no solo un defecto de esta guía.
- El escenario 4 es el más importante de validar con cuidado — es la barandilla de seguridad
  central de esta spec (Historia 2, P1, no negociable).
- Recomendación operativa (no verificable desde el código de este proyecto, ver `research.md`,
  Decisión 3): las credenciales configuradas en `OPSSLEUTH_DB_URL` deberían, en un entorno real,
  corresponder a un rol de base de datos con permisos de solo lectura a nivel del motor, como capa
  adicional de defensa más allá de las validaciones que sí aplica este proyecto.
