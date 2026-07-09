"""Google Gemini provider. Idioms verified via web research 2026-07-09.

- google-genai SDK; client resolves GEMINI_API_KEY.
- Async via client.aio; JSON output via response_mime_type + response_schema.
- google-genai does NOT auto-retry by default (verified in SDK source) —
  retry options are enabled explicitly here.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from pat_helper.providers.base import Provider, parse_json_strict


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

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return parse_json_strict(response.text)
