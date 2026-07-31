"""Behavior tests for pat_helper.lattice — deterministic merged-verdict computation.

The lattice is a pure function over real Finding objects (no mocks, no
providers): given the contributors that synthesis merged into one output
finding, compute the merged verdict, its provenance tier, and any carried
annotations. Design: docs/active/source-check/convos/20260731_verdict_lattice_brainstorm.md
(Dan's decision (b): source-grounded verdicts outrank text-only ones;
outranked softenings survive as annotations).
"""

from pat_helper.lattice import merge_verdict
from pat_helper.models import Finding, Severity


def contrib(verified=None, provenance=None, notes=None):
    return Finding(
        lens="l0",
        model="m",
        quote="q",
        evidence="e",
        severity=Severity.HIGH,
        suggested_fix="fix",
        verified=verified,
        verify_provenance=provenance,
        verify_notes=notes,
    )


def test_source_upheld_outranks_text_softened():
    """The step-14 run-3 collision: a source-check-upheld finding merged with a
    text-only-softened sibling must render upheld — the ground-truth verdict
    wins — with the softening carried as an annotation, not discarded."""
    result = merge_verdict(
        [
            contrib("upheld", "source", "[checker] critique-confirmed"),
            contrib("softened", "text", "[refuter] overstated but real"),
        ]
    )
    assert result.verified == "upheld"
    assert result.provenance == "source"
    assert result.annotations == [
        "[outranked text-only softened] [refuter] overstated but real"
    ]


def test_source_softened_outranks_text_upheld():
    """Source tier wins in the deflating direction too; an upheld text-only
    contributor carries no cautionary content, so nothing is annotated."""
    result = merge_verdict(
        [
            contrib("softened", "source", "[checker] critique-narrowed"),
            contrib("upheld", "text", "[refuter] holds up"),
        ]
    )
    assert result.verified == "softened"
    assert result.provenance == "source"
    assert result.annotations == []


def test_source_tier_outranks_text_unverifiable_and_carries_its_note():
    """Text-only `unverifiable` is more conservative than source `upheld`, but
    conservatism only applies WITHIN a tier — the source verdict was checked
    against the actual cited source and outranks the unresolved flag. The
    flag's note survives as an annotation."""
    result = merge_verdict(
        [
            contrib("upheld", "source", "[checker] critique-confirmed"),
            contrib("unverifiable", "text", "[refuter] cannot check the artifact"),
        ]
    )
    assert result.verified == "upheld"
    assert result.provenance == "source"
    assert result.annotations == [
        "[outranked text-only unverifiable] [refuter] cannot check the artifact"
    ]


def test_two_source_contributors_take_most_conservative_within_tier():
    result = merge_verdict(
        [
            contrib("upheld", "source", "[checker] confirmed"),
            contrib("softened", "source", "[checker] narrowed"),
        ]
    )
    assert result.verified == "softened"
    assert result.provenance == "source"


def test_text_only_mixture_keeps_conservative_order():
    """No source tier present → today's most-conservative-wins behavior:
    unverifiable > softened > upheld > None."""
    softened = merge_verdict(
        [contrib("upheld", "text"), contrib("softened", "text")]
    )
    assert softened.verified == "softened"
    assert softened.provenance == "text"
    assert softened.annotations == []

    unverifiable = merge_verdict(
        [contrib("upheld", "text"), contrib("unverifiable", "text")]
    )
    assert unverifiable.verified == "unverifiable"
    assert unverifiable.provenance == "text"

    upheld = merge_verdict([contrib("upheld", "text"), contrib()])
    assert upheld.verified == "upheld"
    assert upheld.provenance == "text"


def test_exception_path_default_upheld_cannot_outrank_a_real_verdict():
    """_verify's failure path defaults to 'upheld' with provenance None — no
    model actually judged the critique. Merged with a real text-tier verdict,
    the unearned default must lose: conservatism (softened > upheld) decides,
    and the merged provenance is the real verdict's tier."""
    result = merge_verdict(
        [
            contrib("upheld", None, "verification unavailable (dead: boom)"),
            contrib("softened", "text", "[refuter] overstated but real"),
        ]
    )
    assert result.verified == "softened"
    assert result.provenance == "text"


def test_all_unverified_contributors_merge_to_none():
    result = merge_verdict([contrib(), contrib()])
    assert result.verified is None
    assert result.provenance is None
    assert result.annotations == []


def test_single_contributor_passes_through_unchanged():
    """The common 1:1 merge: verdict and provenance pass through, nothing is
    annotated."""
    result = merge_verdict([contrib("unverifiable", "text", "[refuter] no artifact")])
    assert result.verified == "unverifiable"
    assert result.provenance == "text"
    assert result.annotations == []
