"""DMRProvider — Docker Model Runner, Fase 1 (§2.2, §9 del documento de diseño).

DMR expone un endpoint OpenAI-compatible, así que este provider es una capa
delgada sobre el SDK oficial `openai`. La Fase 2 (AzureFoundryProvider, WP-11)
reutiliza casi todo este código: mismo endpoint /openai/v1, distinta auth.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from openai import APIError, AsyncOpenAI

from comparador.gateway.base import ChatMessage, Response, RoleConfig
from comparador.gateway.errors import ModelCallError, RoleNotConfiguredError

_TEMPERATURE = 0.0  # reproducibilidad del papel de trabajo (§4.10)


def _inject_images(messages: list[ChatMessage], images: list[bytes]) -> list[dict[str, Any]]:
    image_blocks = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64.b64encode(img).decode()}"},
        }
        for img in images
    ]
    out: list[dict[str, Any]] = [dict(m) for m in messages]
    if out and out[-1]["role"] == "user":
        out[-1] = {"role": "user", "content": [{"type": "text", "text": out[-1]["content"]}, *image_blocks]}
    else:
        out.append({"role": "user", "content": image_blocks})
    return out


class DMRProvider:
    def __init__(
        self,
        *,
        base_url: str,
        roles: dict[str, RoleConfig],
        concurrency: int = 4,
        api_key: str = "dmr-local",
        timeout: float = 60.0,
    ) -> None:
        self._roles = roles
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._semaphore = asyncio.Semaphore(concurrency)

    def _resolve_model(self, role: str) -> str:
        cfg = self._roles.get(role)
        if cfg is None:
            raise RoleNotConfiguredError(f"rol '{role}' no está en models.yaml")
        return cfg.model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        role: str,
        schema: dict[str, Any] | None = None,
    ) -> Response:
        model = self._resolve_model(role)
        response_format: dict[str, Any] | None = None
        if schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema, "strict": True},
            }
        try:
            async with self._semaphore:
                completion = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=_TEMPERATURE,
                    response_format=response_format,  # type: ignore[arg-type]
                )
        except APIError as exc:
            raise ModelCallError(f"chat falló para rol '{role}': {exc}") from exc

        content = completion.choices[0].message.content or ""
        parsed: dict[str, Any] | None = None
        if schema is not None:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ModelCallError(
                    f"respuesta de '{role}' no es JSON válido pese a schema pedido"
                ) from exc

        latency_ms = 0
        return Response(
            text=content,
            parsed=parsed,
            provider="dmr",
            model=model,
            latency_ms=latency_ms,
            raw=completion.model_dump(),
        )

    async def chat_vision(
        self,
        messages: list[ChatMessage],
        images: list[bytes],
        *,
        role: str,
    ) -> Response:
        model = self._resolve_model(role)
        payload = _inject_images(messages, images)
        try:
            async with self._semaphore:
                completion = await self._client.chat.completions.create(
                    model=model,
                    messages=payload,  # type: ignore[arg-type]
                    temperature=_TEMPERATURE,
                )
        except APIError as exc:
            raise ModelCallError(f"chat_vision falló para rol '{role}': {exc}") from exc

        content = completion.choices[0].message.content or ""
        return Response(
            text=content,
            provider="dmr",
            model=model,
            latency_ms=0,
            raw=completion.model_dump(),
        )

    async def embed(self, texts: list[str], *, role: str) -> list[list[float]]:
        model = self._resolve_model(role)
        try:
            async with self._semaphore:
                result = await self._client.embeddings.create(model=model, input=texts)
        except APIError as exc:
            raise ModelCallError(f"embed falló para rol '{role}': {exc}") from exc
        return [item.embedding for item in result.data]
