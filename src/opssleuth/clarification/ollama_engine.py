"""Implementación de ``ClarificationEngine`` basada en modelos locales vía Ollama.

Único módulo del proyecto que depende del SDK ``ollama`` (Principio II de la
constitución) — ningún otro módulo debe importar ``ollama`` directamente. Existe
para demostrar y verificar en código la modularidad del motor de aclaración (ver
research.md, Decisión 4): es intercambiable con `ClaudeClarificationEngine` sin
cambios en `Caso` ni en la CLI.
"""

from __future__ import annotations

import os

import ollama

from opssleuth.clarification.engine import (
    INSTRUCCIONES_EVALUACION,
    BaseClarificationEngine,
    ClarificationEngineError,
    EvaluacionDescripcion,
)

VARIABLE_ENTORNO_MODELO = "OPSSLEUTH_OLLAMA_MODEL"
"""Variable de entorno que indica qué modelo local usar (sin valor por defecto)."""


class ModeloOllamaNoConfiguradoError(ClarificationEngineError):
    """Se lanza si no se configuró un modelo para el proveedor Ollama."""


class OllamaClarificationEngine(BaseClarificationEngine):
    """Motor de aclaración basado en modelos locales servidos por Ollama.

    Ver `contracts/clarification_engine.md` → `OllamaClarificationEngine`.

    Parameters
    ----------
    client : ollama.Client, optional
        Cliente de Ollama a usar. Si no se proporciona, se crea uno con
        ``ollama.Client()`` (por defecto contra ``http://localhost:11434``).
    modelo : str, optional
        Nombre del modelo local ya descargado en Ollama. Si no se proporciona,
        se lee de la variable de entorno `VARIABLE_ENTORNO_MODELO`
        (``OPSSLEUTH_OLLAMA_MODEL``). No hay valor por defecto fijado en el
        código (ver research.md, Decisión 4).

    Raises
    ------
    ModeloOllamaNoConfiguradoError
        Si no se proporciona `modelo` y la variable de entorno tampoco está
        configurada.
    """

    def __init__(
        self,
        client: ollama.Client | None = None,
        modelo: str | None = None,
    ) -> None:
        self._client = client or ollama.Client()
        self._modelo = modelo or os.environ.get(VARIABLE_ENTORNO_MODELO)
        if not self._modelo:
            raise ModeloOllamaNoConfiguradoError(
                f"Debe configurarse la variable de entorno {VARIABLE_ENTORNO_MODELO} "
                "con el nombre de un modelo ya descargado en Ollama "
                "(ollama pull <modelo>)."
            )

    def evaluar(self, texto: str, contexto: list[dict]) -> EvaluacionDescripcion:
        """Evalúa `texto` invocando un modelo local a través de Ollama.

        Reenvía `contexto` como historial de conversación, igual que
        `ClaudeClarificationEngine` — el contrato no distingue entre proveedores
        en este aspecto — y usa el parámetro `format` de `ollama.Client.chat`
        (JSON Schema de `EvaluacionDescripcion`) para obtener una respuesta
        estructurada.

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
            Si ocurre un error de comunicación con la instancia de Ollama.
        """
        mensajes = [
            {"role": "system", "content": INSTRUCCIONES_EVALUACION},
            *contexto,
            {"role": "user", "content": texto},
        ]
        try:
            respuesta = self._client.chat(
                model=self._modelo,
                messages=mensajes,
                format=EvaluacionDescripcion.model_json_schema(),
            )
        except (ollama.ResponseError, ConnectionError) as error:
            raise ClarificationEngineError(
                "Error al comunicarse con la instancia de Ollama."
            ) from error
        return EvaluacionDescripcion.model_validate_json(respuesta.message.content)
