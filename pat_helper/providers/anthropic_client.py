"""Anthropic provider. Verified against claude-api skill 2026-07-09.

- AsyncAnthropic resolves ANTHROPIC_API_KEY (or an `ant auth login` profile).
- Structured output via output_config.format json_schema.
- Adaptive thinking; SDK auto-retries 429/5xx (max_retries default 2).
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from pat_helper.providers.base import Provider, parse_json_strict


class AnthropicProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "anthropic"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = AsyncAnthropic()

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return parse_json_strict(text)
