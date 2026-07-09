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
    verified: str | None = None  # "upheld" | "softened" | "refuted" | None
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
        }


@dataclass
class ReviewRun:
    paper_name: str
    findings: list[Finding] = field(default_factory=list)  # main body (post-synthesis)
    demoted: list[Finding] = field(default_factory=list)  # ungrounded or refuted
    gaps: list[str] = field(default_factory=list)  # "lens × model: reason"


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
        "verdict": {"type": "string", "enum": ["upheld", "softened", "refuted"]},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "reasoning"],
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
                },
                "required": ["quote", "evidence", "severity", "suggested_fix", "lens", "models"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}
