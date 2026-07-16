"""Load lens/verify/synthesis prompts from the lenses/ data directory.

Prompts are plain markdown files — readable, forkable, and the primary
teaching surface of this project. Code should never embed review-lens text.
"""

from __future__ import annotations

from pathlib import Path

from pat_helper.models import LensSpec

LENSES_DIR = Path(__file__).parent / "lenses"

# Canonical lens order (also the report grouping order within a severity)
LENS_KEYS = [
    "empirical-rigor",
    "causal-id",
    "prior-work",
    "framing-coalition",
    "argumentation",
    "sources",
    "structure-scoping",
    "reproducibility",
]

SHARED_HEADER = """\
You will receive the full text of a working paper (flattened LaTeX).
Report findings as JSON matching the schema you have been given.

Hard rules:
- "quote" must be copied VERBATIM from the paper text — it will be
  mechanically checked against the source, and findings whose quote cannot
  be located are discarded. Quote the exact sentence(s) your critique is
  about; do not paraphrase inside the quote field.
- Report only findings through your assigned lens.
- Prefer a few consequential findings over many trivial ones.
- If you find nothing worth reporting through this lens, return an empty
  findings array — that is a valid and useful answer.
"""


def load_lenses(keys: list[str] | None = None) -> list[LensSpec]:
    selected = keys or LENS_KEYS
    specs = []
    for key in selected:
        path = LENSES_DIR / f"{key}.md"
        specs.append(LensSpec(key=key, prompt=path.read_text()))
    return specs


def verify_prompt() -> str:
    return (LENSES_DIR / "_verify.md").read_text()


def synthesis_prompt() -> str:
    return (LENSES_DIR / "_synthesis.md").read_text()


def source_check_prompt() -> str:
    return (LENSES_DIR / "_source_check.md").read_text()
