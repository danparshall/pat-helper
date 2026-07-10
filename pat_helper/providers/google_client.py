"""Google Gemini provider. Idioms verified via web research 2026-07-09.

- google-genai SDK; client resolves GEMINI_API_KEY.
- Async via client.aio; JSON output via response_mime_type +
  response_json_schema. NOT response_schema: that field is an OpenAPI-subset
  proto that rejects our schemas' `additionalProperties` keys with
  400 INVALID_ARGUMENT (observed live 2026-07-09); response_json_schema
  accepts standard JSON Schema per the SDK docstring.
- google-genai does NOT auto-retry by default (verified in SDK source) —
  retry options are enabled explicitly here.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from pat_helper.providers.base import Provider, TruncatedOutputError, parse_json_strict


class GoogleProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "google"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = genai.Client(
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=4,
                    initial_delay=1.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    async def complete_json(
        self, system: str, user: str, schema: dict, *, max_output_tokens: int | None = None
    ) -> dict:
        cap = max_output_tokens or self.max_output_tokens
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=cap,
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        truncated = (
            response.candidates
            and response.candidates[0].finish_reason == types.FinishReason.MAX_TOKENS
        )
        if truncated:
            raise TruncatedOutputError(f"google/{self.model} hit max_output_tokens={cap}")
        return parse_json_strict(response.text)
