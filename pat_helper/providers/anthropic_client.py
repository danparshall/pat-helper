"""Anthropic provider. Verified against claude-api skill 2026-07-10.

- AsyncAnthropic resolves ANTHROPIC_API_KEY (or an `ant auth login` profile).
- Structured output via output_config.format json_schema.
- Adaptive thinking; SDK auto-retries 429/5xx (max_retries default 2).
- Always streams: adaptive-thinking tokens count against max_tokens, and the
  SDK refuses non-streaming requests above ~16k (HTTP timeout risk). Streaming
  lets synthesis run with a large cap; get_final_message() keeps the return
  shape identical to messages.create().
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from pat_helper.providers.base import Provider, TruncatedOutputError, parse_json_strict


class AnthropicProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "anthropic"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = AsyncAnthropic()

    async def complete_json(
        self, system: str, user: str, schema: dict, *, max_output_tokens: int | None = None
    ) -> dict:
        cap = max_output_tokens or self.max_output_tokens
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=cap,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            response = await stream.get_final_message()
        if response.stop_reason == "max_tokens":
            raise TruncatedOutputError(
                f"anthropic/{self.model} hit max_tokens={cap} "
                f"(output_tokens={response.usage.output_tokens}, incl. thinking)"
            )
        text = next(b.text for b in response.content if b.type == "text")
        return parse_json_strict(text)
