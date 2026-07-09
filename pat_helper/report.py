"""Deterministic markdown renderer. Code, not model — provenance can't be dropped.

Demoted findings (ungrounded quotes, refuted critiques) render in an appendix
rather than disappearing: seeing what the models got wrong is part of the
point of this tool.
"""

from __future__ import annotations

from datetime import date

from pat_helper.models import SEVERITY_ORDER, Finding, ReviewRun

_SEVERITY_TITLES = {
    "HIGH": "HIGH severity",
    "MEDIUM": "MEDIUM severity",
    "LOW": "LOW severity",
    "POSITIVE": "Strengths (keep these)",
}


def _render_finding(f: Finding) -> str:
    models = ", ".join(f.models or [f.model])
    loc = f" — `{f.location_label}`" if f.location_label else ""
    lines = [
        f"### [{f.lens}]{loc}",
        "",
        f"> {f.quote}",
        "",
        f"**Why:** {f.evidence}",
        "",
        f"**Suggested fix:** {f.suggested_fix}",
        "",
        f"*Models:* {models}"
        + (f" · *grounding:* {f.grounding_score:.2f}" if f.grounding_score is not None else "")
        + (f" · *verification:* {f.verified}" if f.verified else ""),
    ]
    if f.verify_notes:
        lines.append(f"  *notes:* {f.verify_notes}")
    lines.append("")
    return "\n".join(lines)


def render(run: ReviewRun, run_date: date | None = None) -> str:
    out: list[str] = [f"# Review: {run.paper_name}", ""]
    if run_date:
        out += [f"*Generated {run_date.isoformat()}*", ""]

    if not run.findings:
        out += ["**No findings survived review.**", ""]
    else:
        for sev in SEVERITY_ORDER:
            group = [f for f in run.findings if f.severity == sev]
            if not group:
                continue
            out += [f"## {_SEVERITY_TITLES[str(sev)]}", ""]
            for f in group:
                out.append(_render_finding(f))

    if run.gaps:
        out += ["## Coverage gaps", ""]
        out += [f"- {g}" for g in run.gaps]
        out.append("")

    if run.demoted:
        out += [
            "## Appendix — demoted findings",
            "",
            "These critiques were produced by a model but failed mechanical",
            "quote-grounding or were refuted under adversarial verification.",
            "They are kept for transparency; treat them as examples of what",
            "model reviewers get wrong.",
            "",
        ]
        for f in run.demoted:
            out.append(_render_finding(f))

    return "\n".join(out)
