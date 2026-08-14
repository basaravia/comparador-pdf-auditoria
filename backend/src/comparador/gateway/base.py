"""Contrato ModelGateway — ver docs/arquitectura.md §2.2.

Regla dura (invariante #2, CLAUDE.md): ninguna parte del pipeline fuera de este
paquete importa `openai` ni `httpx` directamente. Todo pasa por aquí.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict

from pydantic import BaseModel


class ChatMessage(TypedDict):
    role: str
    content: str


class RoleConfig(BaseModel):
    """Configuración de un rol lógico (analista_texto, embedder, ...) en models.yaml."""

    model: str


class Response(BaseModel):
    text: str
    parsed: dict[str, Any] | None = None
    provider: str
    model: str
    latency_ms: int
    raw: dict[str, Any] | None = None


class ModelGateway(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        role: str,
        schema: dict[str, Any] | None = None,
    ) -> Response: ...

    async def chat_vision(
        self,
        messages: list[ChatMessage],
        images: list[bytes],
        *,
        role: str,
    ) -> Response: ...

    async def embed(self, texts: list[str], *, role: str) -> list[list[float]]: ...
