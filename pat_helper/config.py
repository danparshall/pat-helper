"""All tunables in one place. Model IDs are config, never hardcoded in logic.

Model IDs verified 2026-07-09 (web research + claude-api skill):
- Anthropic flagship: claude-opus-4-8
- OpenAI: gpt-5.5 (stable flagship). gpt-5.6-sol launched 2026-07-09 (today) —
  switch once it proves stable. Mid-tier: gpt-5.6-terra.
- Google: gemini-3.1-pro-preview (flagship; still Preview — tighter rate
  limits). Stable alternative: gemini-2.5-pro. Mid-tier stable: gemini-3.5-flash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-5.5",
    "google": "gemini-3.1-pro-preview",
}

# Cheap model for harness recall-scoring (LLM-judge matching findings↔defects)
JUDGE_MODEL = ("anthropic", "claude-haiku-4-5")


@dataclass
class ReviewConfig:
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    max_retries: int = 2  # per lens×model cell, on top of SDK-level retries
    backoff_base: float = 0.5  # seconds; exponential (0 in tests)
    concurrency: int = 8  # max simultaneous provider calls
    fuzzy_threshold: float = 0.85  # quote-grounding fuzzy floor
    verify_severities: frozenset[str] = frozenset({"HIGH", "MEDIUM"})
    max_output_tokens: int = 8192
