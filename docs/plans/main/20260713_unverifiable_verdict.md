# Unverifiable Verdict Implementation Plan

**Goal:** Add a fourth adversarial-verify verdict, `unverifiable`, so a paper's self-claims about external artifacts can no longer refute critiques about those artifacts — such findings stay in the main report, severity intact, tagged for the author to check.

**Originating conversation:** `docs/convos/main/20260713_unverifiable_verdict_design.md`

**Context:** Run 1 of the 07-11/07-12 paid v9 runs produced the first confirmed "adversarial verify kills a true finding" instance: the google refuter killed `model-versions-removed` by citing the paper's own "complete replication package" boilerplate — circular, since the planted defect had removed exactly the in-text details that boilerplate vouches for. Three sampled run-1 refutations used the same move. It cost a real recall point.

**Confidence:** High on the rule itself (confirmed failure mode, three instances, clear epistemic argument — a document cannot vouch for itself against a critique of what it omits). Medium on the prompt wording — risk of overcorrection is real and is exactly what the calibration rerun (step C) measures.

**Architecture:** Four small, mechanically-coupled changes: (1) `VERDICT_SCHEMA` enum + `_verify.md` gain `unverifiable` with an evidentiary rule; (2) pipeline routing unchanged (only `refuted` demotes) but merged-finding parsing gains `verified`; (3) `SYNTHESIS_SCHEMA` + `_synthesis.md` pass `verified` through merge (most-conservative-wins) — today verification state dies at synthesis, so without this the new verdict would never reach the report; (4) renderer tags `unverifiable` findings with an explicit "check external artifact" note. Then a verify-only calibration rerun against run 1's refuted findings.

**Branch:** main (repo convention — small validated changes commit directly; see STATUS.md 07-12 session)

**Tech Stack:** Python 3.12, uv, pytest, dataclasses; prompts are markdown files in `pat_helper/lenses/`; fake providers in `tests/` (no live API calls in the suite).

---

## Orientation for the implementing engineer

Read these first (all paths relative to repo root `/Users/dan/code/pat-helper/`):

- `pat_helper/models.py` — `Finding` (has `verified: str | None`, currently `"upheld" | "softened" | "refuted"`), `VERDICT_SCHEMA`, `SYNTHESIS_SCHEMA`. Schema **object identity matters**: tests and fake providers distinguish call kinds by which schema object is passed — extend the existing dicts in place, do not create new ones.
- `pat_helper/pipeline.py` — stage 3 (`_verify`, verdict written to `finding.verified`; survivor filter at ~line 208: only `"refuted"` demotes) and stage 4 (synthesis parse at ~line 232: merged `Finding`s are rebuilt WITHOUT `verified` — this is the state-loss bug we're fixing in passing).
- `pat_helper/lenses/_verify.md` — the refuter prompt. Its check #2 ("does the paper already address this elsewhere") is the hook the circular refutation abused.
- `pat_helper/lenses/_synthesis.md` — merge rules.
- `pat_helper/report.py` — `_render_finding` already renders `*verification:* {verified}` + notes; routing (main vs appendix) is decided in `pipeline.py`, not here.
- `tests/test_pipeline.py` — mirror `test_refuted_findings_are_demoted_not_deleted` (~line 175) and note `FakeProvider("name", verdict=...)` (~line 49). `tests/test_report.py` — mirror `test_ungrounded_findings_go_to_appendix_not_main_body`.

**Testing Plan**

I will add pipeline integration tests (fake providers, real `run_review`) that ensure: a finding whose refuter returns `unverifiable` (a) is NOT demoted, (b) reaches synthesis as a survivor, and (c) after synthesis, the merged finding still carries `verified="unverifiable"` when the fake synthesis output echoes it — and carries `verified=None` when synthesis returns `"none"`. I will add a report test that an `unverifiable` finding renders in the main body (not the appendix) and its rendered text contains the check-external-artifact tag. I will add a prompt/schema drift-guard test that every verdict in `VERDICT_SCHEMA`'s enum appears in `verify_prompt()`'s text (so the prompt and schema can't silently diverge — this guards behavior: a verdict the prompt never defines will never be returned).

NOTE: I will write *all* tests before I add any implementation behavior.

## Part A — TDD the verdict (bite-sized steps)

1. In `tests/test_pipeline.py`, write `test_unverifiable_findings_stay_in_main_report`: finder produces a HIGH finding, refuter's `FakeProvider` verdict is `"unverifiable"`; assert the finding is not in `run.demoted`, and `verified == "unverifiable"` on the surviving finding.
2. Write `test_synthesis_preserves_verified_state`: fake synthesis output includes `"verified": "unverifiable"` on a merged item; assert the post-synthesis `run.findings` entry has `verified == "unverifiable"`. Also assert `"verified": "none"` maps to `None`. (Check how the existing fake provider fabricates synthesis output — it likely echoes input findings; extend it to include `verified`.)
3. Write `test_synthesis_input_includes_verified_state`: assert the JSON handed to the synthesis call contains the survivors' `verified` values (`Finding.to_json` already emits it — this pins the contract).
4. In `tests/test_report.py`, write `test_unverifiable_finding_renders_with_check_artifact_tag`: build a `ReviewRun` with a finding `verified="unverifiable"` in `findings` (main body); assert rendered output places it before any appendix header and contains the tag text (e.g. `check external artifact`).
5. In the prompt-contract test file (wherever `verify_prompt()` is already tested — grep `verify_prompt` in `tests/`), write `test_verdict_schema_and_verify_prompt_agree`: every string in `VERDICT_SCHEMA["properties"]["verdict"]["enum"]` appears in `verify_prompt()`.
6. Run `uv run pytest` — confirm the new tests FAIL and all existing tests still pass.
7. `models.py`: add `"unverifiable"` to `VERDICT_SCHEMA` verdict enum; update the `Finding.verified` comment; add `"verified": {"type": "string", "enum": ["upheld", "softened", "refuted", "unverifiable", "none"]}` to `SYNTHESIS_SCHEMA` item properties and to its `required` list. (String `"none"` rather than a JSON-null union — Gemini's structured-output handling of union types has bitten this repo before; see STATUS.md 07-09 evening.)
8. `pipeline.py` stage-4 parse: set `verified` on the rebuilt merged `Finding` from `item["verified"]`, mapping `"none"` → `None`. Survivor filter: no change (only `"refuted"` demotes — verify this stays true with the new verdict).
9. `report.py` `_render_finding`: when `verified == "unverifiable"`, render the verification fragment as `*verification:* unverifiable — **check external artifact:** the paper asserts this material exists outside the text; confirm it does` (exact wording flexible; the test pins a stable substring).
10. Run `uv run pytest` — all green (expect 50 existing + 5 new).
11. Commit (code + tests, one commit).

## Part B — prompt edits (no code)

12. `_verify.md`: amend check #2 to scope it to **in-text** content: the paper "already addresses" a criticism only via substantive text you can read (a limitations paragraph, a robustness table, a footnote with content) — an assertion that material exists in an external artifact (replication package, supplement, unpublished appendix, dataset) is a claim, not an address.
13. `_verify.md`: add the verdict definition: `"unverifiable"`: the critique concerns material the paper asserts exists in an artifact you cannot inspect. A self-claim is not evidence — do not refute on its basis, and do not uphold as if the material is confirmed absent; return `unverifiable` so the author checks the artifact. Keep the existing "when in doubt on (1), lean refuted" rule scoped to quote-misreading only.
14. `_synthesis.md`: add rule 7: every input finding carries a `verified` state; the merged finding's `verified` is the most conservative among its contributors — `unverifiable` > `softened` > `upheld` > `none` — never invented, never dropped.
15. Rerun `uv run pytest` (drift-guard test from step 5 now passes against the edited prompt). Commit prompt edits.

## Part C — calibration rerun (analysis; no TDD per the exploratory exception)

16. Write `harness/reverify.py` (Python, checkpointed per the experiment-data rules): parse the demoted appendix of `data/harness_out_v9/review_2026-07-11.md`, selecting only findings with `*verification:* refuted` (ungrounded-quote demotions have no verdict and are excluded). Rebuild `Finding` objects (lens, quote, evidence, severity, suggested_fix, finder model from the `*Models:*` line; original refuter is recoverable from the `[provider]` prefix in the notes).
17. For each, call the verify stage with the **same refuter** as run 1 (isolates the prompt change; rotation stays out of scope), new `_verify.md`, `VERDICT_SCHEMA` with four verdicts. Write results incrementally (JSONL checkpoint, resume-safe, conditions recorded per entry).
18. Emit a comparison table (old verdict → new verdict + reasoning snippet) to `data/harness_out_v9/reverify_2026-07-14.md` (quotes the unpublished draft → stays under gitignored `data/`). Announce before running: it's a paid, parallel batch — expect ~10–25 verify calls, paper prefix cached after the priming call, so roughly cents-to-$1.
19. Score it: **success** = the three known self-claim kills (model-versions, temperature-experiment, API-cost) flip to `unverifiable`, AND kills whose refutation cites actual in-text evidence stay `refuted`. **Overcorrection signal** = refutations grounded in substantive in-text passages flipping to `unverifiable`. Summarize counts in the convo doc's Results section.

## Edge cases

- **Verify-call failure fallback** (`pipeline._verify` except-branch) sets `verified="upheld"` — leave as is; an unreachable refuter is not evidence either way and the finding staying in the report is the safe default.
- **LOW/POSITIVE findings** never enter verify (`config.verify_severities`) and have `verified=None` → synthesis fake/real must emit `"none"` for them; the `"none"` mapping in step 8 covers it.
- **Synthesis pass-through-unmerged path** (synthesis failure): survivors keep their real `verified` values untouched — confirm no test assumes `verified is None` post-failure.
- **Provider schema quirks:** the new `SYNTHESIS_SCHEMA` field must survive Gemini's `response_json_schema` path (`additionalProperties: False` + enum is already the house style — no unions, no nulls).
- **Cache prefixes:** `_verify.md` is the verify-stage system prompt → its cache prefix changes once; lens and synthesis prefixes: synthesis system prompt also changes (rule 7). One-time cache re-write, no code impact.
- **reverify.py parse fragility:** the demoted-appendix format is stable for this one file; pin the parser to it and fail loudly on unparsed entries rather than skipping silently (count parsed vs. expected).

## Plan Footer

**Testing Details** All new tests exercise behavior through `run_review` with fake providers or through `render` on constructed runs: demotion routing (does an `unverifiable` finding land in the main body?), state propagation (does the verdict survive the synthesis merge into the final report?), and prompt/schema agreement (can the refuter actually return every verdict the schema permits?). No test inspects types or mocks-only behavior; the fake-provider synthesis echo is extended, not stubbed around.

**Implementation Details**
- Extend schema dicts in place — object identity is load-bearing for call-kind detection in tests
- `"none"` string sentinel instead of JSON null in `SYNTHESIS_SCHEMA` (Gemini union-type history)
- Only `refuted` demotes — the survivor filter is already correct; the change is schema/prompt/parse/render
- Most-conservative-wins ordering for merged `verified`: unverifiable > softened > upheld > none
- Renderer tag substring pinned by test; exact prose free to improve
- Same-refuter replay in Part C to isolate the prompt variable
- Checkpoint + resume in `reverify.py`; new output file, never overwrite run-1 artifacts

**What could change:** Dan's pending skim of the demoted appendices may surface additional true-kills with *different* failure modes (not self-claim circularity) — the prompt rule may need broadening beyond external artifacts. If the calibration rerun shows overcorrection, the `_verify.md` wording (steps 12–13) is the only knob to iterate; schema and routing should be stable. A public-facing (non-author) audience may later want a config that re-enables base-rate discounting of self-claims.

**Questions**
- Should `softened` findings' verify notes also render in the main body? (They do today via `_render_finding`; no change proposed — flagging that the passthrough makes them appear post-synthesis where they previously vanished. This is strictly more information, but the report gets slightly longer.)
- Part C replays only run 1's refuted set. Worth also replaying run 2 / morning-run refuted findings for a larger n? Cheap to add; more paid calls.

---
