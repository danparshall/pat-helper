"""OpenAI provider. Idioms verified via web research 2026-07-09.

- AsyncOpenAI resolves OPENAI_API_KEY.
- Responses API with a raw json_schema text format (we carry schema dicts,
  not pydantic models, so we use the raw-schema shape rather than
  responses.parse(text_format=...)).
- SDK auto-retries connection errors, 408/409/429/5xx (max_retries default 2).
- Prompt caching is automatic on repeated prefixes — the (prefix, suffix)
  user form is just concatenated; identical prefix ordering is the whole game.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from pat_helper.providers.base import Provider, TruncatedOutputError, parse_json_strict, user_text

log = logging.getLogger("pat_helper")


class OpenAIProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "openai"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI()

    async def complete_json(
        self,
        system: str,
        user: str | tuple[str, str],
        schema: dict,
        *,
        max_output_tokens: int | None = None,
    ) -> dict:
        cap = max_output_tokens or self.max_output_tokens
        response = await self._client.responses.create(
            model=self.model,
            max_output_tokens=cap,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text(user)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "review_output",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        usage = getattr(response, "usage", None)
        total = getattr(usage, "input_tokens", 0) or 0
        cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
        self.cached_input_tokens += cached
        self.uncached_input_tokens += total - cached
        log.debug("openai cache: read=%d uncached=%d", cached, total - cached)
        if (
            response.status == "incomplete"
            and response.incomplete_details is not None
            and response.incomplete_details.reason == "max_output_tokens"
        ):
            raise TruncatedOutputError(f"openai/{self.model} hit max_output_tokens={cap}")
        return parse_json_strict(response.output_text)
