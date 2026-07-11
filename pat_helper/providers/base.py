"""Common provider interface: one async method, JSON in / JSON out.

Providers raise on failure; retry policy lives in the pipeline (one place),
on top of whatever the vendor SDK already retries (429/5xx).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod


class TruncatedOutputError(RuntimeError):
    """The model hit its output-token cap; the payload is incomplete.

    Deterministic for a given input — callers should not retry, they should
    raise the cap (or reduce the input)."""


class Provider(ABC):
    name: str
    # Cache-usage accounting (updated per call, read for the run summary).
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0

    @abstractmethod
    async def complete_json(
        self,
        system: str,
        user: str | tuple[str, str],
        schema: dict,
        *,
        max_output_tokens: int | None = None,
    ) -> dict:
        """Run one completion forced to match `schema`; return the parsed object.

        `user` is either a plain prompt string or `(cacheable_prefix,
        volatile_suffix)`: the prefix is byte-identical across calls (the
        paper) and marked as a cache breakpoint on Anthropic; OpenAI and
        Gemini cache repeated prefixes automatically, so they just read the
        concatenation. The model always sees prefix + suffix, in that order.

        `max_output_tokens` overrides the provider's default cap for this call
        (used by synthesis, whose output scales with finding count)."""


def user_text(user: str | tuple[str, str]) -> str:
    """Flatten the user prompt to the single string the model reads."""
    return "".join(user) if isinstance(user, tuple) else user


def parse_json_strict(text: str) -> dict:
    """Parse model output as JSON, tolerating markdown code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return json.loads(stripped)
