"""FakeProvider — respuestas deterministas, sin GPU ni red (invariante #7).

Permite que toda la suite de tests corra sin DMR ni Foundry levantados.
"""

from __future__ import annotations

import hashlib
from typing import Any

from comparador.gateway.base import ChatMessage, Response


def _fill_from_schema(node: dict[str, Any], defs: dict[str, Any]) -> Any:
    """Rellena un valor de ejemplo mínimo que valida contra un JSON Schema.

    No pretende ser un generador de JSON Schema completo: cubre lo suficiente
    (object/array/string/number/integer/boolean/enum/anyOf/$ref) para que las
    respuestas estructuradas de FakeProvider validen contra los esquemas
    Pydantic del proyecto (p.ej. ChangeUnit y los esquemas de análisis futuros).
    """
    if "$ref" in node:
        ref_name = node["$ref"].rsplit("/", 1)[-1]
        return _fill_from_schema(defs[ref_name], defs)

    if "anyOf" in node:
        branches = [b for b in node["anyOf"] if b.get("type") != "null"]
        return _fill_from_schema(branches[0], defs) if branches else None

    if "enum" in node:
        return node["enum"][0]

    node_type = node.get("type")
    if node_type == "object":
        props = node.get("properties", {})
        return {name: _fill_from_schema(prop, defs) for name, prop in props.items()}
    if node_type == "array":
        if "prefixItems" in node:
            return [_fill_from_schema(item, defs) for item in node["prefixItems"]]
        min_items = node.get("minItems", 0)
        item_schema = node.get("items", {})
        return [_fill_from_schema(item_schema, defs) for _ in range(min_items)]
    if node_type == "string":
        if node.get("format") == "date-time":
            return "1970-01-01T00:00:00Z"
        return ""
    if node_type in ("number", "integer"):
        return node.get("minimum", 0)
    if node_type == "boolean":
        return False
    return None


def _pseudo_embedding(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [digest[i % len(digest)] / 255.0 for i in range(dim)]
    norm = sum(v * v for v in raw) ** 0.5 or 1.0
    return [v / norm for v in raw]


class FakeProvider:
    """Provider determinista para tests y desarrollo sin modelos reales."""

    def __init__(self, *, embedding_dim: int = 8) -> None:
        self._embedding_dim = embedding_dim

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        role: str,
        schema: dict[str, Any] | None = None,
    ) -> Response:
        last_content = messages[-1]["content"] if messages else ""
        if schema is not None:
            defs = schema.get("$defs", {})
            parsed = _fill_from_schema(schema, defs)
            return Response(
                text="",
                parsed=parsed,
                provider="fake",
                model=f"fake-{role}",
                latency_ms=0,
            )
        return Response(
            text=f"[fake:{role}] {last_content[:80]}",
            provider="fake",
            model=f"fake-{role}",
            latency_ms=0,
        )

    async def chat_vision(
        self,
        messages: list[ChatMessage],
        images: list[bytes],
        *,
        role: str,
    ) -> Response:
        return Response(
            text=f"[fake-vision:{role}] {len(images)} imagen(es)",
            provider="fake",
            model=f"fake-{role}",
            latency_ms=0,
        )

    async def embed(self, texts: list[str], *, role: str) -> list[list[float]]:
        return [_pseudo_embedding(text, self._embedding_dim) for text in texts]
