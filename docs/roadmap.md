# Roadmap y registro de specs

OpsSleuth se desarrolla con [Spec Kit](https://github.com/github/spec-kit)
(`.specify/`, integrado como skills de Claude Code bajo
`.claude/skills/speckit-*`): cada funcionalidad nace como una spec en
`specs/[###-nombre]/` (`spec.md` → `plan.md` → `tasks.md` →
implementación), y `specs/ESTADO_SPECS.md` es el registro central que evita
que una spec nueva contradiga una decisión ya tomada por una anterior.

## Specs implementadas

| # | Nombre | Resumen |
| --- | --- | --- |
| 001 | Recepción de Incidencia | Captura la descripción inicial, mantiene contexto conversacional, formula preguntas de aclaración cuando falta el sistema afectado, el síntoma o el momento — o se detectan contradicciones/múltiples problemas. |
| 002 | Búsqueda en Archivos de Logs | Invita a aportar evidencia de logs una vez completada la recepción; localiza entradas relacionadas sin cargar el archivo completo, aísla por horario cuando se conoce, y consolida una apreciación inicial. Migró el motor de aclaración de 001 a LangChain/LangGraph. |
| 003 | Conversación Adaptativa | Reconoce una ruta de logs aportada en el mismo mensaje que la descripción inicial, y permite responder de una vez el lote inicial de aclaraciones pendientes — sin romper el flujo guiado paso a paso para quien no combina información. |
| 004 | CLI Chat Enriquecida | Etiquetas de rol obligatorias (reforzadas con color), renderizado Markdown de respuestas estructuradas, indicador visual de actividad/errores — sin alterar el comportamiento conversacional existente. |
| 005 | Consultas a Bases de Datos | Segunda fuente de evidencia, independiente de los logs: consultas simples o con cruces entre varias tablas, validadas por una barandilla de seguridad de dos capas antes de ejecutarse. |

Ver el detalle completo, decisiones arquitectónicas y contratos compartidos en
`specs/ESTADO_SPECS.md` (en el repositorio) — esta página resume, no
reemplaza, ese registro.

## Fuera de alcance (reservado para specs futuras)

- Generación de un diagnóstico o respuesta final a partir de la evidencia ya
  recopilada (la apreciación inicial que producen 002/005 es un insumo, no un
  diagnóstico).
- Persistencia duradera de casos y evidencia entre sesiones, y detección o
  redacción de datos sensibles en descripciones/logs.
- Fuentes de observabilidad adicionales (métricas, trazas, APM, etc.) más
  allá de archivos de logs y bases de datos.

Cualquier spec futura que toque una de estas áreas, o que necesite un cuarto
proveedor de modelo, una nueva fuente de evidencia, o persistencia de casos,
debe seguir los patrones ya establecidos (ver [Arquitectura](architecture.md))
en vez de introducir un mecanismo paralelo — ese es, precisamente, el
propósito de `specs/ESTADO_SPECS.md`.
