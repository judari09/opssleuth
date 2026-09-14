"""Entidades de dominio para la recepción de incidencias.

Este módulo no depende de ningún SDK de proveedor de modelo (Principio II de la
constitución): las entidades aquí definidas son puro estado y reglas de negocio,
consumidas tanto por la CLI como por las implementaciones de ``ClarificationEngine``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from opssleuth.domain.log_evidence import ApreciacionInicialLogs, FuenteDeLogs

EstadoInformacion = Literal["pendiente_descripcion", "pendiente_aclaracion", "completa"]
EstadoCaso = Literal["activo", "finalizado"]
CampoObjetivo = Literal["sistema_afectado", "sintoma", "momento", "problema_principal"]


class DescripcionVaciaError(ValueError):
    """Se lanza al intentar registrar una descripción sin contenido interpretable."""


@dataclass
class CampoExtraido:
    """Resultado de evaluar la presencia de un campo requerido en un texto.

    Attributes
    ----------
    presente : bool
        Si el campo está presente en el texto evaluado.
    valor : str or None
        Valor extraído del texto si ``presente`` es True; None en caso contrario.
    """

    presente: bool
    valor: str | None = None


@dataclass
class DescripcionProblema:
    """Descripción inicial del problema aportada por el usuario.

    Attributes
    ----------
    texto : str
        Texto original tal como lo escribió el usuario.
    sistema_afectado : CampoExtraido
        Evaluación de presencia/valor del sistema o aplicación afectada.
    sintoma : CampoExtraido
        Evaluación de presencia/valor del síntoma o error observado.
    momento : CampoExtraido
        Evaluación de presencia/valor del momento o frecuencia de ocurrencia.
    """

    texto: str
    sistema_afectado: CampoExtraido = field(
        default_factory=lambda: CampoExtraido(presente=False)
    )
    sintoma: CampoExtraido = field(default_factory=lambda: CampoExtraido(presente=False))
    momento: CampoExtraido = field(default_factory=lambda: CampoExtraido(presente=False))

    def campos_faltantes(self) -> list[CampoObjetivo]:
        """Devuelve los campos requeridos que aún no están presentes.

        Returns
        -------
        list of str
            Subconjunto de ``{"sistema_afectado", "sintoma", "momento"}`` cuyo
            ``CampoExtraido.presente`` es False, en ese orden fijo.
        """
        faltantes: list[CampoObjetivo] = []
        if not self.sistema_afectado.presente:
            faltantes.append("sistema_afectado")
        if not self.sintoma.presente:
            faltantes.append("sintoma")
        if not self.momento.presente:
            faltantes.append("momento")
        return faltantes


@dataclass
class Aclaracion:
    """Par de pregunta de aclaración formulada por el sistema y respuesta del usuario.

    Attributes
    ----------
    pregunta : str
        Pregunta puntual formulada por el sistema.
    campo_objetivo : {"sistema_afectado", "sintoma", "momento", "problema_principal"}
        A qué campo requerido (o a la confirmación del problema principal, cuando se
        detectan múltiples problemas en la descripción inicial) apunta la pregunta.
    respuesta : str or None
        Respuesta del usuario; None mientras está pendiente de respuesta.
    sin_confirmar : bool
        True si el usuario indicó explícitamente que no puede aportar más
        información para este campo (FR-010).
    contradice_descripcion_original : bool
        True si el sistema detectó que esta respuesta contradice la descripción
        original o una aclaración previa. Ambos valores se conservan igualmente en
        el contexto del caso; este campo solo marca la inconsistencia para que se
        señale al usuario, nunca descarta ninguno de los dos.
    """

    pregunta: str
    campo_objetivo: CampoObjetivo
    respuesta: str | None = None
    sin_confirmar: bool = False
    contradice_descripcion_original: bool = False


@dataclass
class Caso:
    """Incidencia individual en investigación dentro de una conversación.

    Una conversación puede contener varios casos a lo largo del tiempo, pero solo
    uno puede estar activo a la vez; esa restricción la aplica quien gestiona el
    ciclo de vida de los casos (la CLI), no esta clase, ya que ``Caso`` no tiene
    visibilidad de otras instancias.

    Attributes
    ----------
    id : str
        Identificador único del caso dentro de la conversación.
    descripcion_inicial : DescripcionProblema or None
        Descripción original aportada por el usuario; None antes de registrarla.
    aclaraciones : list of Aclaracion
        Historial de pares pregunta/respuesta de aclaración, en orden cronológico.
    estado_informacion : {"pendiente_descripcion", "pendiente_aclaracion", "completa"}
        Estado de completitud de la información recopilada.
    estado_caso : {"activo", "finalizado"}
        Estado del ciclo de vida del caso. ``"finalizado"`` es terminal para esta
        instancia.
    mensajes : list of dict
        Historial de mensajes (``role``, ``content``) usado como contexto
        multi-turno al invocar al motor de aclaración.
    creado_en : datetime
        Marca de tiempo de creación del caso. Sirve de anclaje temporal
        absoluto para interpretar expresiones relativas del campo ``momento``
        durante la búsqueda de evidencia en logs (ver
        ``specs/002-busqueda-logs/research.md``, Decisión 5).
    fuentes_logs : list of FuenteDeLogs
        Fuentes de logs aportadas para el caso (spec 002, FR-013).
    apreciacion_logs : ApreciacionInicialLogs or None
        Apreciación inicial consolidada de logs, una vez producida (spec 002,
        FR-010); None mientras no se haya buscado evidencia.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    descripcion_inicial: DescripcionProblema | None = None
    aclaraciones: list[Aclaracion] = field(default_factory=list)
    estado_informacion: EstadoInformacion = "pendiente_descripcion"
    estado_caso: EstadoCaso = "activo"
    mensajes: list[dict] = field(default_factory=list)
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fuentes_logs: list[FuenteDeLogs] = field(default_factory=list)
    apreciacion_logs: ApreciacionInicialLogs | None = None

    def registrar_descripcion(self, texto: str) -> DescripcionProblema:
        """Registra la descripción inicial del caso (FR-002).

        Parameters
        ----------
        texto : str
            Texto de la descripción aportada por el usuario.

        Returns
        -------
        DescripcionProblema
            La descripción registrada.

        Raises
        ------
        DescripcionVaciaError
            Si ``texto`` está vacío o no contiene contenido interpretable (FR-011).
        """
        if not texto or not texto.strip():
            raise DescripcionVaciaError(
                "La descripción no puede estar vacía ni contener solo espacios."
            )
        self.descripcion_inicial = DescripcionProblema(texto=texto.strip())
        self.estado_informacion = "pendiente_aclaracion"
        return self.descripcion_inicial

    def agregar_mensaje(self, role: str, content: str) -> None:
        """Agrega un mensaje al historial de contexto conversacional (FR-004).

        Parameters
        ----------
        role : str
            Rol del emisor del mensaje (p. ej. ``"user"`` o ``"assistant"``).
        content : str
            Contenido del mensaje.
        """
        self.mensajes.append({"role": role, "content": content})

    def agregar_aclaracion(self, aclaracion: Aclaracion) -> None:
        """Registra una nueva aclaración en el historial del caso.

        Parameters
        ----------
        aclaracion : Aclaracion
            Aclaración a registrar (pregunta con o sin respuesta).
        """
        self.aclaraciones.append(aclaracion)

    def marcar_informacion_completa(self) -> None:
        """Marca la información del caso como completa.

        Raises
        ------
        DescripcionVaciaError
            Si el caso no tiene una descripción inicial registrada.
        """
        if self.descripcion_inicial is None:
            raise DescripcionVaciaError(
                "No se puede marcar la información como completa sin una "
                "descripción inicial registrada."
            )
        self.estado_informacion = "completa"

    def finalizar(self) -> None:
        """Marca el caso como finalizado (estado terminal, FR-013/FR-014)."""
        self.estado_caso = "finalizado"

    def resumen(self) -> str:
        """Compone un resumen determinista y consistente del caso (FR-005).

        Reúne la descripción original y las aclaraciones registradas (respondidas o
        marcadas como sin confirmar) directamente desde el estado del caso, sin
        depender de una llamada al motor de aclaración — de forma que el resumen
        nunca contradiga ni omita información ya registrada (SC-002).

        Returns
        -------
        str
            Resumen legible del caso, o un mensaje indicando que aún no hay
            descripción registrada.
        """
        if self.descripcion_inicial is None:
            return "Todavía no se ha registrado una descripción del problema para este caso."

        lineas = [f"Problema reportado: {self.descripcion_inicial.texto}"]
        for aclaracion in self.aclaraciones:
            if aclaracion.respuesta is not None:
                sufijo = " (contradice información previa)" if (
                    aclaracion.contradice_descripcion_original
                ) else ""
                lineas.append(f"- {aclaracion.pregunta} -> {aclaracion.respuesta}{sufijo}")
            elif aclaracion.sin_confirmar:
                lineas.append(f"- {aclaracion.pregunta} -> (sin confirmar por el usuario)")
        return "\n".join(lineas)
