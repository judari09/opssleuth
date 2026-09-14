"""Fábrica compartida de modelo de chat (ver contracts/chat_model_provider.md).

Único módulo del proyecto que puede importar ``langchain_anthropic``/
``langchain_ollama``/``langchain_google_genai`` (Principio II de la
constitución — excepción de "estándar de abstracción de terceros maduro"
añadida en la v1.1.0, ver ``.specify/memory/constitution.md``). El proveedor
``gemini`` (``ChatGoogleGenerativeAI``) se acoge a esa misma excepción: es,
igual que ``ChatAnthropic``/``ChatOllama``, una implementación de
``BaseChatModel`` mantenida por un paquete de terceros maduro y ampliamente
adoptado (``langchain-google-genai``), por lo que no requiere una interfaz
propia adicional — envolverla violaría el Principio IV (Simplicidad ante
Todo). Ningún otro módulo de negocio debe importar estos paquetes, ni
``anthropic``/``ollama``/``google-genai`` directamente — deben recibir un
``BaseChatModel`` ya construido como parámetro.
"""

from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

VARIABLE_ENTORNO_PROVEEDOR = "OPSSLEUTH_LLM_PROVIDER"
"""Variable de entorno que selecciona el proveedor: ``"claude"``, ``"ollama"`` o
``"gemini"``."""

VARIABLE_ENTORNO_MODELO_OLLAMA = "OPSSLEUTH_OLLAMA_MODEL"
"""Variable de entorno que indica qué modelo local usar (sin valor por defecto)."""

PROVEEDOR_POR_DEFECTO = "claude"

MODELO_CLAUDE_POR_DEFECTO = "claude-sonnet-5"
"""Modelo de Claude usado por defecto (ver research.md, Decisión 2)."""

MODELO_GEMINI_POR_DEFECTO = "gemini-3.6-flash"
"""Modelo de Gemini usado por defecto: disponible en la capa gratuita de la API
de Gemini (Google AI Studio) y con soporte de tool calling / salida
estructurada, requerido por ambos flujos (aclaración y búsqueda de logs).
`gemini-2.5-flash` (elección original) fue retirado para API keys nuevas
poco después de introducirse este proveedor — ver nota en
`chat_model_provider.md`, sección "Adición del proveedor gemini"."""


class ProveedorDesconocidoError(ValueError):
    """Se lanza cuando `VARIABLE_ENTORNO_PROVEEDOR` tiene un valor no reconocido."""


class ModeloOllamaNoConfiguradoError(ValueError):
    """Se lanza si no se configuró un modelo para el proveedor Ollama."""


def crear_modelo_chat() -> BaseChatModel:
    """Crea el `BaseChatModel` configurado según el proveedor seleccionado.

    Lee `VARIABLE_ENTORNO_PROVEEDOR` (`OPSSLEUTH_LLM_PROVIDER`, por defecto
    `PROVEEDOR_POR_DEFECTO`) y devuelve una instancia de `ChatAnthropic`,
    `ChatOllama` o `ChatGoogleGenerativeAI` — las tres implementan
    `BaseChatModel`, el mecanismo de intercambiabilidad del que dependen tanto
    el flujo de aclaración (`opssleuth.clarification.engine`) como el de
    búsqueda de logs (`opssleuth.evidence.engine`).

    Returns
    -------
    BaseChatModel
        `ChatAnthropic(model=MODELO_CLAUDE_POR_DEFECTO)` si el proveedor
        configurado es ``"claude"``, `ChatOllama(model=<modelo configurado>)`
        si es ``"ollama"``, o `ChatGoogleGenerativeAI(model=MODELO_GEMINI_POR_DEFECTO)`
        si es ``"gemini"``.

    Raises
    ------
    ProveedorDesconocidoError
        Si `VARIABLE_ENTORNO_PROVEEDOR` tiene un valor distinto de ``"claude"``,
        ``"ollama"`` o ``"gemini"``.
    ModeloOllamaNoConfiguradoError
        Si el proveedor es ``"ollama"`` y `VARIABLE_ENTORNO_MODELO_OLLAMA` no
        está configurada.
    """
    proveedor = os.environ.get(VARIABLE_ENTORNO_PROVEEDOR, PROVEEDOR_POR_DEFECTO).strip().lower()
    if proveedor == "claude":
        return ChatAnthropic(model=MODELO_CLAUDE_POR_DEFECTO)
    if proveedor == "ollama":
        modelo = os.environ.get(VARIABLE_ENTORNO_MODELO_OLLAMA)
        if not modelo:
            raise ModeloOllamaNoConfiguradoError(
                f"Debe configurarse la variable de entorno {VARIABLE_ENTORNO_MODELO_OLLAMA} "
                "con el nombre de un modelo ya descargado en Ollama "
                "(ollama pull <modelo>)."
            )
        return ChatOllama(model=modelo)
    if proveedor == "gemini":
        return ChatGoogleGenerativeAI(model=MODELO_GEMINI_POR_DEFECTO)
    raise ProveedorDesconocidoError(
        f"Proveedor desconocido en {VARIABLE_ENTORNO_PROVEEDOR}: {proveedor!r}. "
        'Valores admitidos: "claude", "ollama", "gemini".'
    )
