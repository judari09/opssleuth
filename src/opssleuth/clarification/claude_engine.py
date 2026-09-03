"""Implementación de ``ClarificationEngine`` basada en la API de Mensajes de Claude.

Único módulo del proyecto que depende del SDK ``anthropic`` (Principio II de la
constitución) — ningún otro módulo debe importar ``anthropic`` directamente.
"""

from __future__ import annotations

import anthropic

from opssleuth.clarification.engine import (
    INSTRUCCIONES_EVALUACION,
    BaseClarificationEngine,
    ClarificationEngineError,
    EvaluacionDescripcion,
)

MODELO_POR_DEFECTO = "claude-sonnet-5"
"""Modelo de Claude usado por defecto (ver research.md, Decisión 1)."""


class ClaudeClarificationEngine(BaseClarificationEngine):
    """Motor de aclaración basado en la API de Mensajes de Claude (Anthropic).

    Ver `contracts/clarification_engine.md` → `ClaudeClarificationEngine`.

    Parameters
    ----------
    client : anthropic.Anthropic, optional
        Cliente de Anthropic a usar. Si no se proporciona, se crea uno con
        ``anthropic.Anthropic()``, que resuelve credenciales desde el entorno
        (``ANTHROPIC_API_KEY`` o un perfil de ``ant auth login``).
    modelo : str, optional
        Identificador del modelo de Claude a usar. Por defecto
        `MODELO_POR_DEFECTO` (``claude-sonnet-5``).
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        modelo: str = MODELO_POR_DEFECTO,
    ) -> None:
        self._client = client or anthropic.Anthropic()
        self._modelo = modelo

    def evaluar(self, texto: str, contexto: list[dict]) -> EvaluacionDescripcion:
        """Evalúa `texto` invocando la API de Mensajes de Claude con salida estructurada.

        Reenvía `contexto` como el historial de `messages` de la conversación,
        dado que la API de Claude es sin estado (ver research.md, Decisión 2), y
        usa `output_config.format` (vía `messages.parse`) para garantizar una
        respuesta conforme al esquema de `EvaluacionDescripcion` (ver research.md,
        Decisión 3).

        Parameters
        ----------
        texto : str
            Texto a evaluar (descripción inicial o respuesta de aclaración).
        contexto : list of dict
            Historial de la conversación del caso, en formato ``role``/``content``.

        Returns
        -------
        EvaluacionDescripcion
            Evaluación estructurada de campos, contradicción y múltiples problemas.

        Raises
        ------
        ClarificationEngineError
            Si ocurre un error de comunicación con la API de Claude.
        """
        mensajes = [*contexto, {"role": "user", "content": texto}]
        try:
            respuesta = self._client.messages.parse(
                model=self._modelo,
                max_tokens=1024,
                system=INSTRUCCIONES_EVALUACION,
                messages=mensajes,
                output_format=EvaluacionDescripcion,
            )
        except (anthropic.APIError, anthropic.APIConnectionError) as error:
            raise ClarificationEngineError(
                "Error al comunicarse con la API de Claude."
            ) from error
        return respuesta.parsed_output
