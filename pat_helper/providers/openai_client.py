"""OpenAI provider. Idioms verified via web research 2026-07-09.

- AsyncOpenAI resolves OPENAI_API_KEY.
- Responses API with a raw json_schema text format (we carry schema dicts,
  not pydantic models, so we use the raw-schema shape rather than
  responses.parse(text_format=...)).
- SDK auto-retries connection errors, 408/409/429/5xx (max_retries default 2).
"""

from __future__ import annotations

from openai import AsyncOpenAI

from pat_helper.providers.base import Provider, parse_json_strict


class OpenAIProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "openai"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI()

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        response = await self._client.responses.create(
            model=self.model,
            max_output_tokens=self.max_output_tokens,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
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
        return parse_json_strict(response.output_text)
