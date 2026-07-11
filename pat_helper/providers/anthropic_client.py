"""Anthropic provider. Verified against claude-api skill 2026-07-10 / 2026-07-11.

- AsyncAnthropic resolves ANTHROPIC_API_KEY (or an `ant auth login` profile).
- Structured output via output_config.format json_schema.
- Adaptive thinking; SDK auto-retries 429/5xx (max_retries default 2).
- Always streams: adaptive-thinking tokens count against max_tokens, and the
  SDK refuses non-streaming requests above ~16k (HTTP timeout risk). Streaming
  lets synthesis run with a large cap; get_final_message() keeps the return
  shape identical to messages.create().
- Prompt caching: the (prefix, suffix) user form renders as two content
  blocks with `cache_control: ephemeral` on the first. Caching is a prefix
  match over tools → system → messages; reads ~0.1× input price, writes
  1.25×; min cacheable prefix on opus-4-8 is 4096 tokens (smaller inputs
  silently don't cache — no error).
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from pat_helper.providers.base import Provider, TruncatedOutputError, parse_json_strict

log = logging.getLogger("pat_helper")


class AnthropicProvider(Provider):
    def __init__(self, model: str, max_output_tokens: int = 8192):
        self.name = "anthropic"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = AsyncAnthropic()

    async def complete_json(
        self,
        system: str,
        user: str | tuple[str, str],
        schema: dict,
        *,
        max_output_tokens: int | None = None,
    ) -> dict:
        cap = max_output_tokens or self.max_output_tokens
        if isinstance(user, tuple):
            prefix, suffix = user
            content: str | list[dict] = [
                {"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": suffix},
            ]
        else:
            content = user
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=cap,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
        ) as stream:
            response = await stream.get_final_message()
        usage = response.usage
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        written = getattr(usage, "cache_creation_input_tokens", 0) or 0
        uncached = (getattr(usage, "input_tokens", 0) or 0) + written
        self.cached_input_tokens += cached
        self.uncached_input_tokens += uncached
        log.debug("anthropic cache: read=%d written=%d uncached=%d", cached, written, uncached)
        if response.stop_reason == "max_tokens":
            raise TruncatedOutputError(
                f"anthropic/{self.model} hit max_tokens={cap} "
                f"(output_tokens={response.usage.output_tokens}, incl. thinking)"
            )
        text = next(b.text for b in response.content if b.type == "text")
        return parse_json_strict(text)
