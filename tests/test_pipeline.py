"""Behavior tests for pat_helper.pipeline — orchestration with fake providers.

No live API calls. FakeProvider decides its response by which schema it is
handed (findings / verdict / synthesis), mirroring how the real pipeline
distinguishes call kinds.
"""

import asyncio
from pathlib import Path

import pytest

from pat_helper.config import ReviewConfig
from pat_helper.latex import load_paper
from pat_helper.models import FINDINGS_SCHEMA, SYNTHESIS_SCHEMA, VERDICT_SCHEMA, LensSpec
from pat_helper.pipeline import run_review
from pat_helper.prompts import SHARED_HEADER
from pat_helper.providers.base import Provider, TruncatedOutputError

FIXTURES = Path(__file__).parent / "fixtures"

GROUNDED_QUOTE = "Standard errors are clustered at the region level."
SECOND_GROUNDED_QUOTE = "We use a difference-in-differences design with staggered adoption."
FABRICATED_QUOTE = "This sentence appears nowhere in the manuscript."


def _user_text(user) -> str:
    """Normalize the provider `user` argument (str or (prefix, suffix) tuple)
    to the full text the model would read."""
    return "".join(user) if isinstance(user, tuple) else user


def make_finding(quote=GROUNDED_QUOTE, severity="HIGH"):
    return {
        "quote": quote,
        "evidence": "Test evidence for this critique.",
        "severity": severity,
        "suggested_fix": "Do the thing.",
    }


class FakeProvider(Provider):
    def __init__(
        self,
        name,
        findings=None,
        fail_times=0,
        fail_always=False,
        verdict="upheld",
        truncate_synthesis=False,
        synthesis_echo=None,
        events=None,
    ):
        self.name = name
        self.findings = findings if findings is not None else [make_finding()]
        self.remaining_failures = fail_times
        self.fail_always = fail_always
        self.verdict = verdict
        self.truncate_synthesis = truncate_synthesis
        self.synthesis_echo = synthesis_echo  # explicit synthesis output override
        self.events = events  # shared list of ("start"|"end", provider, kind)
        self.calls = []  # list of (kind, system, user)
        self.call_caps = []  # list of (kind, max_output_tokens)

    async def complete_json(
        self, system: str, user, schema: dict, *, max_output_tokens: int | None = None
    ) -> dict:
        if schema is FINDINGS_SCHEMA:
            kind = "findings"
        elif schema is VERDICT_SCHEMA:
            kind = "verdict"
        elif schema is SYNTHESIS_SCHEMA:
            kind = "synthesis"
        else:
            kind = "unknown"
        self.calls.append((kind, system, user))
        self.call_caps.append((kind, max_output_tokens))
        if self.events is not None:
            self.events.append(("start", self.name, kind))
            await asyncio.sleep(0)  # yield so concurrent calls can interleave
            self.events.append(("end", self.name, kind))
        if kind == "synthesis" and self.truncate_synthesis:
            raise TruncatedOutputError("output truncated: stop_reason=max_tokens")
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
            if self.synthesis_echo is not None:
                return {"findings": self.synthesis_echo}
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
                assert f"model: {p.name}" not in _user_text(user)


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
                assert FABRICATED_QUOTE not in _user_text(user)


async def test_synthesis_receives_only_survivors(paper):
    liar = FakeProvider("liar", findings=[make_finding(quote=FABRICATED_QUOTE)])
    ok = FakeProvider("fake-b")
    run = await run_review(paper, [liar, ok], lenses(1), config())
    synth_calls = [(k, u) for p in (liar, ok) for k, _s, u in p.calls if k == "synthesis"]
    assert synth_calls, "synthesis was never called"
    for _k, user in synth_calls:
        assert FABRICATED_QUOTE not in _user_text(user)
    assert run.findings  # merged output came back


async def test_refuted_findings_are_demoted_not_deleted(paper):
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter", verdict="refuted")
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    # finder's HIGH finding gets refuted by the other provider -> demoted
    assert any(f.verified == "refuted" for f in run.demoted)


async def test_unverifiable_findings_stay_in_main_report(paper):
    """A critique the refuter cannot check against the text (the paper merely
    asserts the material exists in an external artifact) must NOT be demoted —
    it survives to synthesis at full severity, tagged unverifiable."""
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter", verdict="unverifiable")
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    assert run.demoted == []
    # The finding reached synthesis carrying its verdict
    synth_calls = [u for p in (finder, refuter) for k, _s, u in p.calls if k == "synthesis"]
    assert synth_calls, "synthesis was never called"
    assert '"verified": "unverifiable"' in _user_text(synth_calls[0])


async def test_synthesis_input_includes_verified_state(paper):
    """Survivors' verification state is part of the synthesis contract —
    without it the merge cannot preserve verdicts."""
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter")  # default verdict: upheld
    await run_review(paper, [finder, refuter], lenses(1), config())
    synth_calls = [u for p in (finder, refuter) for k, _s, u in p.calls if k == "synthesis"]
    assert synth_calls, "synthesis was never called"
    assert '"verified": "upheld"' in _user_text(synth_calls[0])


async def test_synthesis_preserves_verified_state(paper):
    """Verification state must survive the synthesis merge into the final
    report: 'unverifiable' passes through; the 'none' sentinel maps to None."""
    echo = [
        {**make_finding(), "lens": "l0", "models": ["finder"], "verified": "unverifiable"},
        {
            **make_finding(quote=SECOND_GROUNDED_QUOTE),
            "lens": "l0",
            "models": ["refuter"],
            "verified": "none",
        },
    ]
    finder = FakeProvider("finder", synthesis_echo=echo)
    refuter = FakeProvider("refuter", verdict="unverifiable")
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    by_quote = {f.quote: f for f in run.findings}
    assert by_quote[GROUNDED_QUOTE].verified == "unverifiable"
    assert by_quote[SECOND_GROUNDED_QUOTE].verified is None


def test_verdict_schema_and_verify_prompt_agree():
    """Every verdict the schema permits must be defined in the refuter prompt —
    a verdict the prompt never explains will never be returned."""
    from pat_helper.models import VERDICT_SCHEMA as vs
    from pat_helper.prompts import verify_prompt

    prompt = verify_prompt()
    for verdict in vs["properties"]["verdict"]["enum"]:
        assert f'"{verdict}"' in prompt, f"verdict {verdict!r} not defined in _verify.md"


async def test_synthesis_call_carries_the_synthesis_output_cap(paper):
    """Synthesis output scales with finding count (110 findings truncated the
    16k default on 2026-07-09), so the pipeline must request the larger
    synthesis-specific cap on that call — and only that call."""
    provs = [FakeProvider("fake-a"), FakeProvider("fake-b")]
    await run_review(paper, provs, lenses(2), config(synthesis_max_output_tokens=54321))
    caps = [(k, cap) for p in provs for k, cap in p.call_caps]
    synth_caps = [cap for k, cap in caps if k == "synthesis"]
    assert len(synth_caps) == 1, "expected exactly one synthesis call"
    assert synth_caps == [54321]
    # Lens and verify calls keep the provider's own default (no override)
    assert all(cap is None for k, cap in caps if k != "synthesis")


async def test_truncated_synthesis_is_not_retried_and_passes_through_unmerged(paper):
    """Truncation is deterministic — retrying an over-cap synthesis burns the
    same tokens again. One attempt, an explicit gap, unmerged pass-through."""
    truncating = FakeProvider("fake-a", truncate_synthesis=True)
    other = FakeProvider("fake-b")
    run = await run_review(paper, [truncating, other], lenses(1), config())
    synthesis_attempts = sum(
        1 for p in (truncating, other) for k, _s, _u in p.calls if k == "synthesis"
    )
    assert synthesis_attempts == 1
    assert any("truncated" in g for g in run.gaps)
    # Survivors passed through unmerged (each finding still credits one model)
    assert run.findings
    assert all(len(f.models) == 1 for f in run.findings)


async def test_low_severity_findings_skip_verification(paper):
    low = FakeProvider("low", findings=[make_finding(severity="LOW")])
    other = FakeProvider("other", findings=[make_finding(severity="LOW")])
    await run_review(paper, [low, other], lenses(1), config())
    verdict_calls = [k for p in (low, other) for k, _s, _u in p.calls if k == "verdict"]
    assert verdict_calls == []


# --- Prompt-caching restructure (docs/plans/main/20260711_prompt_caching.md) ---
# The paper must be a byte-identical cacheable prefix shared across calls;
# the volatile part (lens prompt / critique block) follows it.


async def test_verify_calls_put_paper_in_cacheable_prefix(paper):
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter")
    await run_review(paper, [finder, refuter], lenses(1), config())
    verdict_calls = [(s, u) for p in (finder, refuter) for k, s, u in p.calls if k == "verdict"]
    assert verdict_calls, "no verify calls were made"
    for _system, user in verdict_calls:
        assert isinstance(user, tuple), "verify user prompt must be (cacheable, volatile)"
        prefix, suffix = user
        assert prefix == f"# PAPER\n\n{paper.text}"
        assert "# CRITIQUE" in suffix
        assert "# CRITIQUE" not in prefix


async def test_lens_calls_put_paper_in_prefix_and_lens_in_suffix(paper):
    prov = FakeProvider("fake-a")
    lens_list = lenses(2)
    await run_review(paper, [prov, FakeProvider("fake-b")], lens_list, config())
    findings_calls = [(s, u) for k, s, u in prov.calls if k == "findings"]
    assert len(findings_calls) == 2
    for system, user in findings_calls:
        # system is the constant shared header — no per-lens text in it
        assert system == SHARED_HEADER
        assert isinstance(user, tuple), "lens user prompt must be (cacheable, volatile)"
        prefix, suffix = user
        assert prefix == f"# PAPER\n\n{paper.text}"
    # each call's suffix carries exactly one lens prompt, and every lens is
    # covered — guards against one lens's text being duplicated into another's
    # call while its own is dropped
    suffixes = [u[1] for _s, u in findings_calls]
    carried = []
    for s in suffixes:
        present = [lens.key for lens in lens_list if lens.prompt in s]
        assert len(present) == 1, f"suffix must carry exactly one lens prompt, got {present}"
        carried.append(present[0])
    assert sorted(carried) == sorted(lens.key for lens in lens_list)


async def test_reordered_prompts_preserve_all_content_exactly_once(paper):
    """Guard against dropping or duplicating content while reordering: what
    the model reads (system + full user text) must contain the paper, the
    lens text, and the critique content exactly once."""
    prov_a, prov_b = FakeProvider("fake-a"), FakeProvider("fake-b")
    lens_list = lenses(1)
    await run_review(paper, [prov_a, prov_b], lens_list, config())
    for p in (prov_a, prov_b):
        for kind, system, user in p.calls:
            full = system + _user_text(user)
            if kind == "findings":
                assert full.count(paper.text) == 1
                assert full.count(lens_list[0].prompt) == 1
                assert full.count(SHARED_HEADER) == 1
            elif kind == "verdict":
                assert full.count(paper.text) == 1
                # critique block content (evidence text appears once)
                assert full.count("Test evidence for this critique.") == 1


def _barrier_respected(events, kind, n):
    """True iff the first n `kind` calls (the priming batch) all end before
    any further `kind` call starts."""
    seq = [e for e in events if e[2] == kind]
    start_pos = [i for i, e in enumerate(seq) if e[0] == "start"]
    end_pos = [i for i, e in enumerate(seq) if e[0] == "end"]
    if len(start_pos) <= n:
        return True  # nothing beyond the priming batch
    return start_pos[n] > end_pos[n - 1]


async def test_first_lens_cell_per_provider_completes_before_fan_out(paper):
    """Cache priming: one findings call per provider must complete (writing
    the cache entry) before the remaining fan-out calls launch."""
    events = []
    provs = [FakeProvider("fake-a", events=events), FakeProvider("fake-b", events=events)]
    await run_review(paper, provs, lenses(4), config())
    seq = [e for e in events if e[2] == "findings"]
    starts = [e for e in seq if e[0] == "start"]
    # the priming batch covers every provider (one cell each)
    assert {e[1] for e in starts[: len(provs)]} == {p.name for p in provs}
    assert _barrier_respected(events, "findings", len(provs))


async def test_first_verify_call_per_refuter_completes_before_fan_out(paper):
    """Verify calls have their own cache prefix (different system prompt), so
    the verify stage must prime per refuter too."""
    events = []
    findings = [make_finding(), make_finding(quote=SECOND_GROUNDED_QUOTE)]
    prov_a = FakeProvider("fake-a", findings=list(findings), events=events)
    prov_b = FakeProvider("fake-b", findings=list(findings), events=events)
    await run_review(paper, [prov_a, prov_b], lenses(1), config())
    verdicts = [e for e in events if e[2] == "verdict" and e[0] == "start"]
    assert len(verdicts) == 4, "expected 2 HIGH findings per provider to be verified"
    assert _barrier_respected(events, "verdict", 2)  # one priming call per refuter
