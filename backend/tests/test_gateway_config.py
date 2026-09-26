"""§2.2: cambiar de Fase 1 a Fase 2 debe ser cambiar config, no reescribir código."""

from pathlib import Path

import pytest

from comparador.gateway import DMRProvider, FakeProvider, GatewayConfig, build_gateway, load_config
from comparador.gateway.errors import RoleNotConfiguredError

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_YAML = REPO_ROOT / "config" / "models.yaml"


def test_load_config_reads_fase1_models_yaml():
    config = load_config(MODELS_YAML)

    assert config.provider == "dmr"
    assert config.base_url == "http://localhost:12434/engines/llama.cpp/v1"
    assert set(config.roles) == {"analista_texto", "analista_vision", "embedder"}
    assert config.roles["embedder"].model == "ai/embeddinggemma"
    assert config.concurrency == 4


def test_build_gateway_dmr_does_not_touch_the_network():
    config = load_config(MODELS_YAML)
    gateway = build_gateway(config)

    assert isinstance(gateway, DMRProvider)


def test_build_gateway_fake_provider():
    config = GatewayConfig(provider="fake", roles={})
    gateway = build_gateway(config)

    assert isinstance(gateway, FakeProvider)


def test_dmr_provider_raises_typed_error_for_unknown_role():
    config = load_config(MODELS_YAML)
    gateway = build_gateway(config)

    with pytest.raises(RoleNotConfiguredError):
        gateway._resolve_model("rol_inexistente")
