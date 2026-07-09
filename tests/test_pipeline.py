"""Behavior tests for pat_helper.pipeline — orchestration with fake providers.

No live API calls. FakeProvider decides its response by which schema it is
handed (findings / verdict / synthesis), mirroring how the real pipeline
distinguishes call kinds.
"""

from pathlib import Path

import pytest

from pat_helper.config import ReviewConfig
from pat_helper.latex import load_paper
from pat_helper.models import FINDINGS_SCHEMA, SYNTHESIS_SCHEMA, VERDICT_SCHEMA, LensSpec
from pat_helper.pipeline import run_review
from pat_helper.providers.base import Provider

FIXTURES = Path(__file__).parent / "fixtures"

GROUNDED_QUOTE = "Standard errors are clustered at the region level."
FABRICATED_QUOTE = "This sentence appears nowhere in the manuscript."


def make_finding(quote=GROUNDED_QUOTE, severity="HIGH"):
    return {
        "quote": quote,
        "evidence": "Test evidence for this critique.",
        "severity": severity,
        "suggested_fix": "Do the thing.",
    }


class FakeProvider(Provider):
    def __init__(self, name, findings=None, fail_times=0, fail_always=False, verdict="upheld"):
        self.name = name
        self.findings = findings if findings is not None else [make_finding()]
        self.remaining_failures = fail_times
        self.fail_always = fail_always
        self.verdict = verdict
        self.calls = []  # list of (kind, system, user)

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        if schema is FINDINGS_SCHEMA:
            kind = "findings"
        elif schema is VERDICT_SCHEMA:
            kind = "verdict"
        elif schema is SYNTHESIS_SCHEMA:
            kind = "synthesis"
        else:
            kind = "unknown"
        self.calls.append((kind, system, user))
        if self.fail_always:
            raise RuntimeError("permanent failure")
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise RuntimeError("flaky failure")
        if kind == "findings":
            return {"findings": self.findings}
        if kind == "verdict":
            return {"verdict": self.verdict, "reasoning": "because"}
        if kind == "synthesis":
            # Echo back merged findings: one merged finding crediting two models
            return {
                "findings": [
                    {**make_finding(), "lens": "l0", "models": ["fake-a", "fake-b"]},
                ]
            }
        raise AssertionError(f"unexpected schema kind {kind}")


def lenses(n=8):
    return [LensSpec(key=f"l{i}", prompt=f"lens prompt {i}") for i in range(n)]


@pytest.fixture()
def paper():
    return load_paper(FIXTURES / "main.tex")


def config(**kw):
    base = dict(max_retries=2, backoff_base=0.0, concurrency=8)
    base.update(kw)
    return ReviewConfig(**base)


async def test_fan_out_issues_one_findings_call_per_lens_model_cell(paper):
    provs = [FakeProvider("fake-a"), FakeProvider("fake-b"), FakeProvider("fake-c")]
    await run_review(paper, provs, lenses(8), config())
    for p in provs:
        assert sum(1 for k, _, _ in p.calls if k == "findings") == 8


async def test_flaky_cell_is_retried_and_succeeds(paper):
    flaky = FakeProvider("flaky", fail_times=2)  # fails twice, then succeeds
    run = await run_review(paper, [flaky, FakeProvider("fake-b")], lenses(1), config())
    assert run.gaps == []
    assert any(f.quote == GROUNDED_QUOTE for f in run.findings)


async def test_dead_provider_degrades_to_gap_without_killing_run(paper):
    dead = FakeProvider("dead", fail_always=True)
    ok = FakeProvider("fake-b")
    run = await run_review(paper, [dead, ok], lenses(2), config())
    # 2 lenses x dead provider = 2 gaps, each naming the provider
    assert len(run.gaps) == 2
    assert all("dead" in g for g in run.gaps)
    # And the healthy provider's findings still made it through
    assert run.findings


async def test_refuter_is_never_the_finder(paper):
    provs = [FakeProvider("fake-a"), FakeProvider("fake-b"), FakeProvider("fake-c")]
    await run_review(paper, provs, lenses(3), config())
    for p in provs:
        for kind, _system, user in p.calls:
            if kind == "verdict":
                # The verify prompt embeds the finder model's name
                assert f"model: {p.name}" not in user


async def test_ungrounded_findings_are_demoted_and_skip_verification(paper):
    liar = FakeProvider("liar", findings=[make_finding(quote=FABRICATED_QUOTE)])
    ok = FakeProvider("fake-b")
    run = await run_review(paper, [liar, ok], lenses(1), config())
    demoted_quotes = [f.quote for f in run.demoted]
    assert FABRICATED_QUOTE in demoted_quotes
    # No verify call was made about the fabricated quote
    for p in (liar, ok):
        for kind, _s, user in p.calls:
            if kind == "verdict":
                assert FABRICATED_QUOTE not in user


async def test_synthesis_receives_only_survivors(paper):
    liar = FakeProvider("liar", findings=[make_finding(quote=FABRICATED_QUOTE)])
    ok = FakeProvider("fake-b")
    run = await run_review(paper, [liar, ok], lenses(1), config())
    synth_calls = [
        (k, u) for p in (liar, ok) for k, _s, u in p.calls if k == "synthesis"
    ]
    assert synth_calls, "synthesis was never called"
    for _k, user in synth_calls:
        assert FABRICATED_QUOTE not in user
    assert run.findings  # merged output came back


async def test_refuted_findings_are_demoted_not_deleted(paper):
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter", verdict="refuted")
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    # finder's HIGH finding gets refuted by the other provider -> demoted
    assert any(f.verified == "refuted" for f in run.demoted)


async def test_low_severity_findings_skip_verification(paper):
    low = FakeProvider("low", findings=[make_finding(severity="LOW")])
    other = FakeProvider("other", findings=[make_finding(severity="LOW")])
    await run_review(paper, [low, other], lenses(1), config())
    verdict_calls = [k for p in (low, other) for k, _s, _u in p.calls if k == "verdict"]
    assert verdict_calls == []
