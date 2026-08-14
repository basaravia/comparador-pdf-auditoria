"""Carga de models.yaml y construcción del ModelGateway (§2.2).

Cambiar de Fase 1 (DMR) a Fase 2 (Foundry, WP-11) es cambiar este archivo de
configuración, no reescribir el pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from comparador.gateway.base import ModelGateway, RoleConfig
from comparador.gateway.dmr import DMRProvider
from comparador.gateway.fake import FakeProvider

Provider = Literal["dmr", "fake"]


class GatewayConfig(BaseModel):
    provider: Provider
    base_url: str | None = None
    roles: dict[str, RoleConfig]
    concurrency: int = 4


def load_config(path: Path) -> GatewayConfig:
    data = yaml.safe_load(path.read_text())
    return GatewayConfig.model_validate(data)


def build_gateway(config: GatewayConfig) -> ModelGateway:
    if config.provider == "fake":
        return FakeProvider()
    if config.provider == "dmr":
        if not config.base_url:
            raise ValueError("provider 'dmr' requiere 'base_url' en models.yaml")
        return DMRProvider(
            base_url=config.base_url,
            roles=config.roles,
            concurrency=config.concurrency,
        )
    raise ValueError(f"provider desconocido: {config.provider}")
