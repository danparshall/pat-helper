"""Deterministic merged-verdict computation over synthesis contributors.

When synthesis merges several findings into one, the merged verdict is not
the model's to decide — it is computed here from the contributors' verdicts
and provenance tiers. Design (Dan's decision (b), see
docs/active/source-check/convos/20260731_verdict_lattice_brainstorm.md):

- Source-grounded verdicts (checked against the actual cited source) outrank
  text-only ones. Conservatism applies WITHIN a tier, not across tiers.
- Outranked text-tier softenings/unverifiable flags are not discarded: their
  notes are carried as annotations so the reader sees the dissent.

Everything consumed is schema-validated enums and structured fields — no
free text is ever matched against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pat_helper.models import Finding

# Most conservative first. None (never verified) is least conservative.
# "refuted" is unreachable today (refuted findings demote pre-synthesis) but
# the lattice handles it rather than crash — issue #2 (symmetric propagation)
# will make it live, and checked-and-wrong outranks cannot-check.
_CONSERVATISM = ["refuted", "unverifiable", "softened", "upheld", None]
# Verdicts whose text-tier notes are worth carrying when the source tier
# decided: they carry cautionary content an upheld contributor lacks.
_ANNOTATABLE = ("softened", "unverifiable")


@dataclass
class MergeResult:
    verified: str | None
    provenance: str | None
    annotations: list[str] = field(default_factory=list)


def _most_conservative(contributors: list[Finding]) -> Finding:
    return min(contributors, key=lambda f: _CONSERVATISM.index(f.verified))


def merge_verdict(contributors: list[Finding]) -> MergeResult:
    """Compute the merged verdict, provenance, and carried annotations.

    If any contributor is source-tier, the merged verdict is the most
    conservative within the source tier and provenance is "source";
    text-tier softened/unverifiable notes are carried as annotations.
    Otherwise the most conservative contributor overall decides and its
    provenance passes through.
    """
    source_tier = [f for f in contributors if f.verify_provenance == "source"]
    if source_tier:
        winner = _most_conservative(source_tier)
        annotations = [
            f"[outranked text-only {f.verified}] {f.verify_notes}"
            for f in contributors
            if f.verify_provenance != "source" and f.verified in _ANNOTATABLE
        ]
        return MergeResult(
            verified=winner.verified, provenance="source", annotations=annotations
        )
    winner = _most_conservative(contributors)
    return MergeResult(verified=winner.verified, provenance=winner.verify_provenance)
