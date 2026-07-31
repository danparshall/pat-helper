"""Core data shapes for pat-helper.

Provenance-first: every Finding carries {lens, model(s), quote, evidence,
severity, suggested_fix} plus grounding and verification state. Demoted
findings (ungrounded or refuted) are kept, never deleted — they render in the
report appendix as a teachable artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    POSITIVE = "POSITIVE"


SEVERITY_ORDER = [Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.POSITIVE]


@dataclass
class SourceLocation:
    file: str
    line: int  # 1-indexed

    @property
    def label(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class LensSpec:
    key: str
    prompt: str


@dataclass
class Finding:
    lens: str
    model: str  # finder model (pre-synthesis); first contributor after merge
    quote: str
    evidence: str
    severity: Severity
    suggested_fix: str
    grounded: bool | None = None
    grounding_score: float | None = None
    location_label: str | None = None
    verified: str | None = None  # "upheld" | "softened" | "refuted" | "unverifiable" | None
    # Which tier produced the verdict: "text" (adversarial verify against the
    # paper text) or "source" (checked against the actual cited source).
    # Set exactly where verdicts are set; never parsed from notes. The verify
    # exception path leaves it None so its default can never outrank a real
    # verdict at merge time.
    verify_provenance: str | None = None
    verify_notes: str | None = None
    models: list[str] = field(default_factory=list)  # all contributing models

    def to_json(self) -> dict:
        return {
            "lens": self.lens,
            "model": self.model,
            "models": self.models or [self.model],
            "quote": self.quote,
            "evidence": self.evidence,
            "severity": str(self.severity),
            "suggested_fix": self.suggested_fix,
            "location": self.location_label,
            "grounding_score": self.grounding_score,
            "verified": self.verified,
            "verify_provenance": self.verify_provenance,
        }


@dataclass
class ReviewRun:
    paper_name: str
    findings: list[Finding] = field(default_factory=list)  # main body (post-synthesis)
    demoted: list[Finding] = field(default_factory=list)  # ungrounded or refuted
    gaps: list[str] = field(default_factory=list)  # "lens × model: reason"
    # Resolution counts from stage 3.5 (source check); None when the stage
    # did not run — the report renders the section only when set.
    source_check_summary: str | None = None


# --- JSON schemas handed to providers (identity matters: the pipeline and the
# tests distinguish call kinds by which schema object is passed). ---

_FINDING_PROPS = {
    "quote": {
        "type": "string",
        "description": "Verbatim quote from the paper that the critique is about",
    },
    "evidence": {"type": "string", "description": "Why this is a problem (or a strength)"},
    "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW", "POSITIVE"]},
    "suggested_fix": {"type": "string"},
}

FINDINGS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _FINDING_PROPS,
                "required": ["quote", "evidence", "severity", "suggested_fix"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

VERDICT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["upheld", "softened", "refuted", "unverifiable"],
        },
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "reasoning"],
    "additionalProperties": False,
}

# Stage 3.5 (source check) — cheap-model read of a source file's head, used to
# build the content-keyed index. Filenames are never trusted; identity comes
# from the text itself.
SOURCE_INDEX_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "authors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Author surnames, in the order listed by the source",
        },
        "year": {"type": "string", "description": "Publication year as printed, e.g. '2024'"},
        "title": {"type": "string"},
    },
    "required": ["authors", "year", "title"],
    "additionalProperties": False,
}

# Stage 3.5 — one check call per (unverifiable finding, matched source). The
# checker's opinion is honored only after two mechanical gates: source_quote
# must ground against the source text, and the reported identity must match
# the citation.
SOURCE_CHECK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "identity": {
            "type": "object",
            "properties": {
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Author surnames as printed (initials tolerated)",
                },
                "year": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["authors", "year", "title"],
            "additionalProperties": False,
            "description": "Who/what the supplied source ACTUALLY is, read from its text",
        },
        "identity_matches_citation": {
            "type": "boolean",
            "description": "Does the source's own identity match the citation in the critique?",
        },
        "resolution": {
            "type": "string",
            "enum": [
                "critique-confirmed",
                "critique-narrowed",
                "critique-contradicted",
                "unresolved",
            ],
        },
        "source_quote": {
            "type": "string",
            "description": "Verbatim quote from the SOURCE text that decides the resolution",
        },
        "reasoning": {"type": "string"},
    },
    "required": [
        "identity",
        "identity_matches_citation",
        "resolution",
        "source_quote",
        "reasoning",
    ],
    "additionalProperties": False,
}

SYNTHESIS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **_FINDING_PROPS,
                    "lens": {"type": "string"},
                    "models": {"type": "array", "items": {"type": "string"}},
                    # Merged verification is computed downstream by the lattice
                    # from these input ids — synthesis never reports a verdict.
                    # Plain integer arrays are safe for Gemini's structured-
                    # output path (unions are not).
                    "contributors": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Input finding ids merged into this output finding",
                    },
                    "echoes_demoted": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": (
                            "Ids from the DEMOTED (refuted against source) digest that this"
                            " finding echoes; empty when none apply"
                        ),
                    },
                },
                "required": [
                    "quote",
                    "evidence",
                    "severity",
                    "suggested_fix",
                    "lens",
                    "models",
                    "contributors",
                    "echoes_demoted",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}
