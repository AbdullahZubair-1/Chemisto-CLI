"""Central configuration for the gateway service.

All OpenRouter credentials and model identifiers live here, loaded from
environment variables / .env. Nothing here is duplicated in the CLI.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    id: str
    label: str


def _model(index: int, default_id: str, default_label: str) -> ModelConfig:
    model_id = os.getenv(f"CHEMISTO_MODEL_{index}", default_id)
    label = os.getenv(f"CHEMISTO_MODEL_{index}_LABEL", default_label)
    return ModelConfig(id=model_id, label=label)


@dataclass(frozen=True)
class GatewaySettings:
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_site_url: str
    openrouter_app_name: str
    openrouter_timeout_seconds: float
    host: str
    port: int
    models: list[ModelConfig] = field(default_factory=list)

    @property
    def default_model(self) -> ModelConfig:
        return self.models[0]

    def model_by_id(self, model_id: str) -> ModelConfig | None:
        return next((m for m in self.models if m.id == model_id), None)


def load_settings() -> GatewaySettings:
    models = [
        _model(1, "meta-llama/llama-3.3-70b-instruct:free", "Llama 3.3 70B (free)"),
        _model(2, "mistralai/mistral-7b-instruct:free", "Mistral 7B (free)"),
        _model(3, "qwen/qwen-2.5-72b-instruct:free", "Qwen 2.5 72B (free)"),
    ]
    return GatewaySettings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL", "https://github.com/AbdullahZubair-1/Chemisto-CLI"),
        openrouter_app_name=os.getenv("OPENROUTER_APP_NAME", "Chemisto CLI"),
        openrouter_timeout_seconds=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60")),
        host=os.getenv("GATEWAY_HOST", "127.0.0.1"),
        port=int(os.getenv("GATEWAY_PORT", "8000")),
        models=models,
    )


settings = load_settings()
