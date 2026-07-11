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

# Cheap model for harness recall-scoring (LLM-judge matching findings↔defects).
# OpenAI mid-tier is the project's cheap default (~$0.25 / $2.00 per MTok input/output,
# vs. Anthropic Haiku ~$0.80 / $4.00). Matcher-not-generator task — mid-tier is plenty.
JUDGE_MODEL = ("openai", "gpt-5.6-terra")


@dataclass
class ReviewConfig:
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    max_retries: int = 2  # per lens×model cell, on top of SDK-level retries
    backoff_base: float = 0.5  # seconds; exponential (0 in tests)
    concurrency: int = 8  # max simultaneous provider calls
    fuzzy_threshold: float = 0.85  # quote-grounding fuzzy floor
    verify_severities: frozenset[str] = frozenset({"HIGH", "MEDIUM"})
    # Hard cap on TOTAL output per call — on Anthropic, adaptive-thinking tokens
    # count against this too. 8192 truncated the synthesis JSON on a 57-finding
    # fixture run (2026-07-09). 16000 was the non-streaming ceiling, but the
    # Anthropic client always streams now, and empirical-rigor × opus hit 16000
    # (thinking + recompute evidence) on the 2026-07-11 v9 run — a cap is not
    # spend, so 32000 buys headroom at zero marginal cost.
    max_output_tokens: int = 32000
    # Synthesis output scales with finding count (110 findings exceeded 16000
    # on the 2026-07-09 real-paper run), so the synthesis call gets its own,
    # larger cap. Requires streaming on Anthropic (SDK refuses non-streaming
    # requests above ~16k). ~2.5x headroom over the largest observed run.
    synthesis_max_output_tokens: int = 64000
