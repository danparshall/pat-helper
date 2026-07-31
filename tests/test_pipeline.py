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
from pat_helper.models import (
    FINDINGS_SCHEMA,
    SOURCE_CHECK_SCHEMA,
    SOURCE_INDEX_SCHEMA,
    SYNTHESIS_SCHEMA,
    VERDICT_SCHEMA,
    LensSpec,
)
from pat_helper.pipeline import run_review
from pat_helper.prompts import SHARED_HEADER
from pat_helper.providers.base import Provider, TruncatedOutputError

FIXTURES = Path(__file__).parent / "fixtures"

GROUNDED_QUOTE = "Standard errors are clustered at the region level."
SECOND_GROUNDED_QUOTE = "We use a difference-in-differences design with staggered adoption."
FABRICATED_QUOTE = "This sentence appears nowhere in the manuscript."

# --- source-check fixtures (stage 3.5) ---
SOURCE_QUOTE = "Access to generative AI increases task completion by 14 percent."
SOURCE_TEXT = f"""\
The Productivity Effects of Generative AI
Svanberg, M. (2024). Working paper.

{SOURCE_QUOTE}
The estimated effect is concentrated among less-experienced workers.
"""
SVANBERG_IDENTITY = {
    "authors": ["Svanberg"],
    "year": "2024",
    "title": "The Productivity Effects of Generative AI",
}
# Evidence text carrying exactly one extractable citation
CITED_EVIDENCE = (
    "The paper attributes a 25 percent gain to Svanberg et al. (2024), "
    "which cannot be verified from the paper's own text."
)


def _user_text(user) -> str:
    """Normalize the provider `user` argument (str or (prefix, suffix) tuple)
    to the full text the model would read."""
    return "".join(user) if isinstance(user, tuple) else user


def make_finding(
    quote=GROUNDED_QUOTE, severity="HIGH", evidence="Test evidence for this critique."
):
    return {
        "quote": quote,
        "evidence": evidence,
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
        source_index=None,
        source_check_resolution="unresolved",
        source_check_quote=SOURCE_QUOTE,
        source_check_identity=None,
        source_check_identity_matches=True,
    ):
        self.name = name
        self.findings = findings if findings is not None else [make_finding()]
        self.remaining_failures = fail_times
        self.fail_always = fail_always
        self.verdict = verdict
        self.truncate_synthesis = truncate_synthesis
        self.synthesis_echo = synthesis_echo  # explicit synthesis output override
        self.events = events  # shared list of ("start"|"end", provider, kind)
        self.source_index = source_index  # dict of text-marker -> identity dict
        self.source_check_resolution = source_check_resolution
        self.source_check_quote = source_check_quote
        self.source_check_identity = source_check_identity
        self.source_check_identity_matches = source_check_identity_matches
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
        elif schema is SOURCE_INDEX_SCHEMA:
            kind = "source_index"
        elif schema is SOURCE_CHECK_SCHEMA:
            kind = "source_check"
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
        if kind == "source_index":
            text = _user_text(user)
            for marker, identity in (self.source_index or {}).items():
                if marker in text:
                    return dict(identity)
            raise AssertionError(
                f"{self.name} got a source-index call it cannot answer: {text[:120]!r}"
            )
        if kind == "source_check":
            return {
                "identity": dict(self.source_check_identity or SVANBERG_IDENTITY),
                "identity_matches_citation": self.source_check_identity_matches,
                "resolution": self.source_check_resolution,
                "source_quote": self.source_check_quote,
                "reasoning": "because",
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


# --- Stage 3.5: source check (docs/active/source-check/plans/20260714_source_check_stage.md)
# With --sources, `unverifiable` findings are resolved against author-supplied
# source texts. Without it, behavior is byte-identical to today (pinned below).


@pytest.fixture()
def sources_dir(tmp_path):
    d = tmp_path / "sources"
    d.mkdir()
    (d / "svanberg_2024.txt").write_text(SOURCE_TEXT)
    return d


SOURCE_MARKERS = {"Svanberg": SVANBERG_IDENTITY}


def _kinds(p):
    return [k for k, _s, _u in p.calls]


def _source_pair(resolution="unresolved", **checker_kw):
    """(finder, checker) pair: the finder raises one unverifiable-verdicted
    finding citing Svanberg et al. (2024); the checker resolves it. With two
    providers the checker (rotation offset 1 fallback) is also the refuter."""
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution=resolution,
        **checker_kw,
    )
    return finder, checker


async def test_source_check_goes_to_third_provider_and_index_to_first_healthy(
    paper, sources_dir
):
    """Checker rotation: with three providers the checker is finder+2 — never
    the finder, never the refuter. The index is built by the first healthy
    provider, once."""
    finder = FakeProvider(
        "fake-a",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
    )
    refuter = FakeProvider("fake-b", findings=[], verdict="unverifiable")
    checker = FakeProvider("fake-c", findings=[])
    await run_review(
        paper, [finder, refuter, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert "source_check" in _kinds(checker)
    assert "source_check" not in _kinds(finder)
    assert "source_check" not in _kinds(refuter)
    # index reads go to the first healthy provider only
    assert "source_index" in _kinds(finder)
    assert "source_index" not in _kinds(refuter)
    assert "source_index" not in _kinds(checker)


async def test_confirmed_resolution_enters_synthesis_as_upheld(paper, sources_dir):
    finder, checker = _source_pair("critique-confirmed")
    await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    synth = [u for p in (finder, checker) for k, _s, u in p.calls if k == "synthesis"]
    assert synth, "synthesis was never called"
    assert '"verified": "upheld"' in _user_text(synth[0])
    assert '"verified": "unverifiable"' not in _user_text(synth[0])


async def test_confirmed_resolution_carries_source_check_provenance_note(paper, sources_dir):
    """The resolved finding must say which checker read which file — the
    provenance note travels on the finding (observed via unmerged
    pass-through, the established synthesis-failure behavior)."""
    finder, checker = _source_pair("critique-confirmed")
    finder.truncate_synthesis = True  # force pass-through so notes are observable
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "upheld"
    assert "[source-check:checker" in f.verify_notes
    assert "svanberg_2024.txt" in f.verify_notes


async def test_contradicted_resolution_demotes_with_exonerating_source_quote(
    paper, sources_dir
):
    """The source exonerates the paper: the critique is demoted (symmetric
    with refuted) and the demotion carries the exonerating source quote."""
    finder, checker = _source_pair("critique-contradicted")
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.findings == []
    demoted = [f for f in run.demoted if f.evidence == CITED_EVIDENCE]
    assert len(demoted) == 1
    assert demoted[0].verified == "refuted"
    assert SOURCE_QUOTE in demoted[0].verify_notes
    # nothing survived, so synthesis never ran
    assert not any(k == "synthesis" for p in (finder, checker) for k in _kinds(p))


async def test_unresolved_resolution_stays_unverifiable(paper, sources_dir):
    finder, checker = _source_pair("unresolved")
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    synth = [u for p in (finder, checker) for k, _s, u in p.calls if k == "synthesis"]
    assert synth, "synthesis was never called"
    assert '"verified": "unverifiable"' in _user_text(synth[0])


async def test_identity_mismatch_gate_blocks_demotion(paper, sources_dir):
    """A checker that read the wrong source (identity ≠ citation) cannot
    demote, even when it says critique-contradicted — an index error may cost
    a check, never cause a silent wrong-source demotion."""
    finder, checker = _source_pair(
        "critique-contradicted", source_check_identity_matches=False
    )
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    synth = [u for p in (finder, checker) for k, _s, u in p.calls if k == "synthesis"]
    assert synth and '"verified": "unverifiable"' in _user_text(synth[0])


async def test_ungrounded_source_quote_gate_blocks_demotion(paper, sources_dir):
    """A demotion-enabling source quote must mechanically ground against the
    source text; a fabricated quote forces unresolved. The rejected quote is
    preserved in the note — without it a Gate B rejection cannot be diagnosed
    after the fact (observed live: step-15 Svanberg specimen, 2026-07-17)."""
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,  # pass-through so the note is observable
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution="critique-contradicted",
        source_check_quote="This sentence appears nowhere in the source document.",
    )
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "This sentence appears nowhere in the source document." in f.verify_notes


async def test_narrowed_resolution_softens_in_place(paper, sources_dir):
    """critique-narrowed: the source kills the critique's central charge but an
    actionable point survives — the finding stays IN the report at `softened`,
    not demoted, not full-severity. Ground truth: the step-15 Svanberg
    specimen (Dan, 2026-07-17): 'not TOTALLY wrong... I'd prefer the
    reminder'."""
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,  # pass-through so verdict + note are observable
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution="critique-narrowed",
    )
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "softened"
    assert "critique-narrowed" in f.verify_notes
    assert SOURCE_QUOTE in f.verify_notes
    assert "1 narrowed" in run.source_check_summary


async def test_narrowed_with_ungrounded_quote_falls_to_unresolved(paper, sources_dir):
    """A narrowing that cannot ground its source quote is not honored — the
    finding keeps the full unverifiable flag (the safe failure mode)."""
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution="critique-narrowed",
        source_check_quote="This sentence appears nowhere in the source document.",
    )
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "did not ground" in f.verify_notes


async def test_narrowed_with_identity_mismatch_falls_to_unresolved(paper, sources_dir):
    """Narrowing from the wrong source is an error, same as upholding from
    the wrong source: identity gate applies."""
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution="critique-narrowed",
        source_check_identity_matches=False,
    )
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert run.demoted == []
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "identity does not match" in f.verify_notes


async def test_unmatched_citation_stays_unverifiable_with_note(paper, sources_dir):
    """A citation with no matching source file costs no check call; the
    finding keeps its verdict and gains an explanatory note."""
    finder = FakeProvider(
        "finder",
        findings=[
            make_finding(evidence="Doe et al. (1999) is mischaracterized in the review section.")
        ],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,  # pass-through so the note is observable
    )
    checker = FakeProvider("checker", findings=[], verdict="unverifiable")
    run = await run_review(
        paper, [finder, checker], lenses(1), config(sources_dir=sources_dir)
    )
    assert not any(k == "source_check" for p in (finder, checker) for k in _kinds(p))
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "no matching source" in f.verify_notes


async def test_ambiguous_citation_stays_unverifiable_with_note(paper, tmp_path):
    """Two sources with the same (author, year): the model never picks the
    file, so the finding costs no check call, keeps its verdict, and gains an
    explanatory note (plan step 9: unmatched/ambiguous stay put)."""
    d = tmp_path / "sources"
    d.mkdir()
    (d / "one.txt").write_text(SOURCE_TEXT)
    (d / "two.txt").write_text(SOURCE_TEXT + "\nAppendix tables.\n")
    finder = FakeProvider(
        "finder",
        findings=[make_finding(evidence=CITED_EVIDENCE)],
        source_index=SOURCE_MARKERS,
        truncate_synthesis=True,  # pass-through so the note is observable
    )
    checker = FakeProvider("checker", findings=[], verdict="unverifiable")
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=d))
    assert not any(k == "source_check" for p in (finder, checker) for k in _kinds(p))
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "ambiguous" in f.verify_notes


async def test_citation_taken_from_quote_when_evidence_cites_comparison_works(paper, sources_dir):
    """Real critique prose name-drops comparison literature ('this figure is
    more reminiscent of X et al. (2023)...'). The disputed citation lives in
    the QUOTE — the paper's verbatim sentence — so evidence-side mentions of
    other works must not abort extraction. Caught live by the 2026-07-16
    fixture-gate run (defect resolved 'unresolved' instead of upheld)."""
    finder = FakeProvider(
        "finder",
        findings=[
            make_finding(
                quote=(
                    "Svanberg (2024) documents that access to generative AI"
                    " increases task completion by 14 percent."
                ),
                evidence=(
                    "The attributed figure looks suspect — it is more reminiscent of"
                    " Brynjolfsson, Li & Raymond (2023) — and cannot be verified from"
                    " the paper's text."
                ),
            )
        ],
        source_index=SOURCE_MARKERS,
    )
    checker = FakeProvider(
        "checker",
        findings=[],
        verdict="unverifiable",
        source_check_resolution="critique-confirmed",
    )
    await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    assert any(k == "source_check" for k in _kinds(checker)), (
        "the check call never fired: evidence-side comparison citation aborted extraction"
    )
    synth = [u for p in (finder, checker) for k, _s, u in p.calls if k == "synthesis"]
    assert synth and '"verified": "upheld"' in _user_text(synth[0])


async def test_year_near_miss_stays_unverifiable_with_version_mismatch_note(paper, sources_dir):
    """Citation year one off from the indexed source (working paper vs
    published version): never silently check the possibly-wrong version —
    stay put, but tell the author a version mismatch may explain it."""
    finder = FakeProvider(
        "finder",
        findings=[
            make_finding(
                evidence="The paper misstates Svanberg et al. (2025) on the productivity gain."
            )
        ],
        source_index=SOURCE_MARKERS,  # indexed source is Svanberg 2024
        truncate_synthesis=True,  # pass-through so the note is observable
    )
    checker = FakeProvider("checker", findings=[], verdict="unverifiable")
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    assert not any(k == "source_check" for p in (finder, checker) for k in _kinds(p))
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert "version mismatch" in f.verify_notes


async def test_no_sources_dir_makes_no_source_calls_and_pins_current_behavior(paper):
    """Regression pin for every existing user: without sources_dir, the run is
    byte-identical to today — no index reads, no check calls, unverifiable
    findings flow to synthesis untouched, and nothing new appears in the
    rendered report."""
    from pat_helper.report import render

    finder = FakeProvider("finder", findings=[make_finding(evidence=CITED_EVIDENCE)])
    refuter = FakeProvider("refuter", findings=[], verdict="unverifiable")
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    all_kinds = [k for p in (finder, refuter) for k in _kinds(p)]
    assert "source_index" not in all_kinds
    assert "source_check" not in all_kinds
    assert run.demoted == []
    assert run.gaps == []
    synth = [u for p in (finder, refuter) for k, _s, u in p.calls if k == "synthesis"]
    assert synth, "synthesis was never called"
    assert '"verified": "unverifiable"' in _user_text(synth[0])
    # the user-visible surface is unchanged: no source-check section renders
    assert "Source check" not in render(run)


# --- Verdict provenance (docs/active/source-check/plans/20260731_verdict_lattice_provenance.md)
# Provenance is set exactly where verdicts are set — "text" by the adversarial
# verifier, "source" by the source-check stage — and never parsed from notes.
# It is the input the lattice ranks on (source outranks text at merge time).


async def test_verify_success_sets_text_provenance(paper):
    finder = FakeProvider("finder", truncate_synthesis=True)  # pass-through
    refuter = FakeProvider("refuter")  # verify succeeds: upheld
    run = await run_review(paper, [finder, refuter], lenses(1), config())
    assert run.findings
    assert all(f.verify_provenance == "text" for f in run.findings)


async def test_failed_verification_leaves_provenance_unset(paper):
    """The verify exception path defaults to 'upheld' without any model having
    actually read the critique — that default must never carry a provenance
    tier, or it could outrank a real verdict at merge time."""
    finder = FakeProvider("finder", truncate_synthesis=True)  # pass-through
    dead = FakeProvider("dead", fail_always=True)  # refuter dies after retries
    run = await run_review(paper, [finder, dead], lenses(1), config())
    assert len(run.findings) == 1
    f = run.findings[0]
    assert f.verified == "upheld"
    assert "verification unavailable" in f.verify_notes
    assert f.verify_provenance is None


async def test_source_check_upheld_sets_source_provenance(paper, sources_dir):
    finder, checker = _source_pair("critique-confirmed")
    finder.truncate_synthesis = True  # pass-through so provenance is observable
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    f = run.findings[0]
    assert f.verified == "upheld"
    assert f.verify_provenance == "source"


async def test_source_check_softened_sets_source_provenance(paper, sources_dir):
    finder, checker = _source_pair("critique-narrowed")
    finder.truncate_synthesis = True
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    f = run.findings[0]
    assert f.verified == "softened"
    assert f.verify_provenance == "source"


async def test_source_check_refuted_sets_source_provenance(paper, sources_dir):
    """The demoted entry keeps its provenance — Part 3's demoted digest
    selects exactly the source-refuted entries by this field."""
    finder, checker = _source_pair("critique-contradicted")
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    demoted = [f for f in run.demoted if f.evidence == CITED_EVIDENCE]
    assert len(demoted) == 1
    assert demoted[0].verified == "refuted"
    assert demoted[0].verify_provenance == "source"


async def test_source_check_unresolved_keeps_text_provenance(paper, sources_dir):
    """An unresolved check changes nothing: the finding keeps the verdict AND
    the provenance the text-tier verifier gave it."""
    finder, checker = _source_pair("unresolved")
    finder.truncate_synthesis = True
    run = await run_review(paper, [finder, checker], lenses(1), config(sources_dir=sources_dir))
    f = run.findings[0]
    assert f.verified == "unverifiable"
    assert f.verify_provenance == "text"


async def test_synthesis_input_includes_provenance(paper):
    """Provenance is part of the synthesis contract: the merge (Part 2) needs
    it on every input finding to rank contributors."""
    finder = FakeProvider("finder")
    refuter = FakeProvider("refuter")
    await run_review(paper, [finder, refuter], lenses(1), config())
    synth = [u for p in (finder, refuter) for k, _s, u in p.calls if k == "synthesis"]
    assert synth, "synthesis was never called"
    assert '"verify_provenance": "text"' in _user_text(synth[0])
