"""Application-scoped settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings

from docling_converter.workspace_paths import get_default_base_directory

ORGANIZATION_NAME = "docling-converter"
APPLICATION_NAME = "docling-converter"
BASE_DIRECTORY_KEY = "workspace/base_directory"

VLM_ENABLED_KEY = "picture_description/enabled"
VLM_API_URL_KEY = "picture_description/api_url"
VLM_MODEL_KEY = "picture_description/model"
VLM_API_KEY_KEY = "picture_description/api_key"

DEFAULT_VLM_API_URL = "http://localhost:11434/v1/chat/completions"
DEFAULT_VLM_MODEL = "granite3.2-vision:2b"


def load_base_directory(settings: QSettings | None = None) -> Path:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    value = str(store.value(BASE_DIRECTORY_KEY, "")).strip()
    return Path(value) if value else get_default_base_directory()


def save_base_directory(path: Path, settings: QSettings | None = None) -> None:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    store.setValue(BASE_DIRECTORY_KEY, str(path))


@dataclass
class VlmSettings:
    """Provider-agnostic config for VLM picture description.

    Any OpenAI-compatible chat-completions endpoint works here (local
    Ollama by default, but also LM Studio, vLLM, or a hosted API) --
    switching providers is just changing these fields, not code.
    """

    enabled: bool = False
    api_url: str = DEFAULT_VLM_API_URL
    model: str = DEFAULT_VLM_MODEL
    api_key: str = ""


def load_vlm_settings(settings: QSettings | None = None) -> VlmSettings:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    return VlmSettings(
        enabled=str(store.value(VLM_ENABLED_KEY, "false")).lower() == "true",
        api_url=str(store.value(VLM_API_URL_KEY, DEFAULT_VLM_API_URL)).strip()
        or DEFAULT_VLM_API_URL,
        model=str(store.value(VLM_MODEL_KEY, DEFAULT_VLM_MODEL)).strip()
        or DEFAULT_VLM_MODEL,
        api_key=str(store.value(VLM_API_KEY_KEY, "")).strip(),
    )


def save_vlm_settings(vlm_settings: VlmSettings, settings: QSettings | None = None) -> None:
    store = settings or QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    store.setValue(VLM_ENABLED_KEY, vlm_settings.enabled)
    store.setValue(VLM_API_URL_KEY, vlm_settings.api_url)
    store.setValue(VLM_MODEL_KEY, vlm_settings.model)
    store.setValue(VLM_API_KEY_KEY, vlm_settings.api_key)
