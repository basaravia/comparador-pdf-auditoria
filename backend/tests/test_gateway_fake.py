"""Invariante #7: toda la suite corre con FakeProvider, sin GPU ni red."""

import pytest

from comparador.gateway import FakeProvider
from comparador.schemas import ChangeUnit


@pytest.fixture
def gateway() -> FakeProvider:
    return FakeProvider()


async def test_chat_without_schema_is_deterministic(gateway: FakeProvider):
    messages = [{"role": "user", "content": "compara estos dos párrafos"}]
    r1 = await gateway.chat(messages, role="analista_texto")
    r2 = await gateway.chat(messages, role="analista_texto")

    assert r1.text == r2.text
    assert r1.provider == "fake"
    assert "compara estos dos párrafos" in r1.text


async def test_chat_with_schema_fills_a_valid_change_unit(gateway: FakeProvider):
    schema = ChangeUnit.model_json_schema()
    response = await gateway.chat(
        [{"role": "user", "content": "clasifica este cambio"}],
        role="analista_texto",
        schema=schema,
    )

    assert response.parsed is not None
    change_unit = ChangeUnit(**response.parsed)
    assert change_unit.kind in ("insert", "delete", "replace", "format", "visual", "move")


async def test_chat_vision_reports_image_count(gateway: FakeProvider):
    response = await gateway.chat_vision(
        [{"role": "user", "content": "compara estas regiones"}],
        images=[b"fake-png-bytes-a", b"fake-png-bytes-b"],
        role="analista_vision",
    )

    assert "2 imagen" in response.text


async def test_embed_is_deterministic_and_normalized(gateway: FakeProvider):
    [vec_a] = await gateway.embed(["el plazo será de treinta días"], role="embedder")
    [vec_a_again] = await gateway.embed(["el plazo será de treinta días"], role="embedder")
    [vec_b] = await gateway.embed(["un texto completamente distinto"], role="embedder")

    assert vec_a == vec_a_again
    assert vec_a != vec_b
    norm = sum(v * v for v in vec_a) ** 0.5
    assert norm == pytest.approx(1.0)
