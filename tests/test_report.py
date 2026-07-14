"""Behavior tests for pat_helper.report — deterministic markdown rendering."""

from pat_helper.models import Finding, ReviewRun, Severity
from pat_helper.report import render


def _finding(**kw):
    base = dict(
        lens="empirical-rigor",
        model="claude",
        quote="The effect size is 0.31 standard deviations",
        evidence="No confidence interval or standard error is reported for this estimate.",
        severity=Severity.MEDIUM,
        suggested_fix="Report the SE / CI alongside the point estimate.",
        grounded=True,
        grounding_score=1.0,
        location_label="methods.tex:3",
        models=["claude"],
    )
    base.update(kw)
    return Finding(**base)


def _run(findings, demoted=(), gaps=()):
    return ReviewRun(
        paper_name="fixture",
        findings=list(findings),
        demoted=list(demoted),
        gaps=list(gaps),
    )


def test_sections_ordered_by_severity():
    run = _run(
        [
            _finding(severity=Severity.LOW, evidence="low thing"),
            _finding(severity=Severity.HIGH, evidence="high thing"),
            _finding(severity=Severity.POSITIVE, evidence="nice thing"),
            _finding(severity=Severity.MEDIUM, evidence="medium thing"),
        ]
    )
    out = render(run)
    i_high = out.index("high thing")
    i_med = out.index("medium thing")
    i_low = out.index("low thing")
    i_pos = out.index("nice thing")
    assert i_high < i_med < i_low < i_pos


def test_every_finding_renders_full_provenance():
    f = _finding(models=["claude", "gemini"])
    out = render(_run([f]))
    assert f.lens in out
    assert f.quote in out
    assert f.evidence in out
    assert f.suggested_fix in out
    assert f.location_label in out
    # Convergence: contributing models are listed
    assert "claude" in out and "gemini" in out


def test_ungrounded_findings_go_to_appendix_not_main_body():
    good = _finding(evidence="grounded finding body")
    bad = _finding(
        grounded=False,
        grounding_score=0.2,
        quote="This sentence does not exist in the paper.",
        evidence="hallucinated critique",
    )
    out = render(_run([good], demoted=[bad]))
    appendix_start = out.index("Appendix")
    assert out.index("grounded finding body") < appendix_start
    assert out.index("hallucinated critique") > appendix_start


def test_unverifiable_finding_renders_with_check_artifact_tag():
    """An unverifiable finding is a promissory note the paper wrote — it must
    render in the main body (not the appendix) with an explicit prompt to
    check the external artifact, at full severity."""
    conditional = _finding(
        evidence="version pins asserted to live in the replication package",
        verified="unverifiable",
        verify_notes="[google] The paper states the details are in the replication package.",
    )
    refuted = _finding(
        evidence="a genuinely refuted critique",
        verified="refuted",
    )
    out = render(_run([conditional], demoted=[refuted]))
    appendix_start = out.index("Appendix")
    body = out[:appendix_start]
    assert "version pins asserted" in body
    assert "unverifiable" in body
    assert "check external artifact" in body
    # The tag is specific to unverifiable findings, not verification generally
    assert "check external artifact" not in out[appendix_start:]


def test_coverage_gaps_are_reported():
    out = render(_run([_finding()], gaps=["causal-id × gpt: failed after retries"]))
    assert "causal-id × gpt" in out


def test_zero_findings_renders_clean_report():
    out = render(_run([]))
    assert "No findings" in out
