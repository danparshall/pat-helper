<!-- Generated during: convos/20260716_source_check_implementation.md -->

# Step 14 fixture gate — three runs, 2026-07-16

Plan: `plans/20260714_source_check_stage.md` Part C step 14. Fixture paper
(`tests/fixtures/`) with a truthful Svanberg (2024) citation at 14 percent;
`citation-mismatch` defect inflates the paper's characterization to 40
percent; `tests/fixtures/sources/svanberg_2024.txt` is the checkable source.
Command: `uv run python harness/run.py tests/fixtures/main.tex --sources
tests/fixtures/sources` (defaults: anthropic=claude-opus-4-8, openai=gpt-5.5,
google=gemini-3.1-pro-preview; 8 lenses; judge gpt-5.6-terra).

| run | code state | recall | source-check summary | outcome |
|---|---|---|---|---|
| 1 | Part B as landed (`1f51c54`) | 3/3 | 1 checked: 0 upheld, 0 refuted, 1 unresolved | check call never fired — evidence-side comparison citation ("Brynjolfsson, Li & Raymond (2023)") tripped the >1-distinct-citations abort |
| 2 | + quote-first extraction | 3/3 | 2 checked: 0 upheld, 0 refuted, 2 unresolved | check calls fired; Gate A false-rejected an honest critique-confirmed because checker reported authors as printed ("Svanberg, M.") vs bare surname comparison |
| 3 | + token-based surname gate (`e31d74c`) | 3/3 | **2 checked: 2 upheld, 0 refuted, 0 unresolved** | defect recalled via source-check-upheld path — step-14 exit criterion met |

Diagnostic between runs 2 and 3 (single direct check call, anthropic):
payload was textbook-correct — `identity_matches_citation: true`,
`resolution: critique-confirmed`, `source_quote` grounded verbatim
("Access to generative AI increases task completion by 14 percent on
average."), reasoning correctly noting 40 ≠ 14 — isolating Gate A's
string comparison as the false-rejector.

Renderer note (run 3): the merged Svanberg finding renders
`verification: softened`, not `upheld` — synthesis most-conservative-wins
merged the source-check-upheld finding with a text-only-softened sibling
(argumentation lens). Open question in the convo doc: should source-grounded
verdicts outrank the text-only lattice?

Cache telemetry (per run, review stage): anthropic ~10.7–11.7k cached /
~36k uncached input tokens; openai and google 0 cached (fixture below their
minimum caching thresholds). Recall judge: 3 defects × 1 call each.

Both planted-defect siblings (`wrong-number`, `weakened-id`) were HIT on all
three runs — the stage change did not disturb baseline recall.
