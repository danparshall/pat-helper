# 20261014_paper_finder_kickoff

**Date:** 2026-10-14
**Branch:** paper-finder
**Surface:** claude-code
**Machine:** Dans-MacBook-Air
**Session:** Dan (air, pat-helper, 20261012T2355, opus-5.5) · /Users/dan/.claude/projects/-Users-dan-code-pat-helper/1862baee-a6de-4635-8ff3-ca67a0307dd0.jsonl · —

Continues `docs/convos/main/20261012_power_side_detection_review.md` (same session).

## Summary

The power-side review raised the question of how to apply pat-helper's
citation findings. Its sources lens never checked a citation; it can only see
the draft's own tags. So we started a workflow for *getting* the cited sources:
a library-only paper repo (`~/code/paper-library`, LITE, private on GitHub;
text + `index.jsonl` in git, PDFs in Syncthing-shared `~/data/paper-library`)
and a `pat_helper.paperfind` module with three operations: `collect` (copy
another repo's `papers/` only), `find` (library first, then OpenAlex →
open-access PDF → `%PDF` check → pymupdf text), and `export` (a per-review
`sources/` folder + manifest, the input the source-check stage expects).

**Contamination incident.** While looking for the cited papers, this session
read the verification repo's own claim check of the same draft (summary,
~5 ledger rows, STATUS entry) and proposed it as ground truth. Dan rejected
that: pat-helper is under test, and another repo's check must not inform it.
CLAUDE.md now restricts cross-repo reading to `papers/` and `papers/text/`.
This session's judgments about the power-side report's substance are not
independent; calibration on power-side must be run by a clean session.

A web search subagent tested on one unsourced claim (subtransmission line
lengths/ratings) found one primary planning document (ODEC radial 69 kV line
caps: 10,000 consumers, 50 MW, 700 MW-miles) and otherwise only snippets,
403s and paywalls. It kept "read on page" distinct from "seen in snippet"
unprompted, which is the property any web step must preserve.

## Topics Explored

- Why free-text OpenAlex search + word overlap is unsafe (live smoke test).
- Name formats in OpenAlex ("Surname, Given").
- Dan's physics aside on the ODEC caps (√N aggregate noise, flat-load
  signature, rural long radial lines) — belongs to the power-side work, not
  this branch; recorded here only as the reason "tidbits" from planning
  criteria are wanted.

## Provisional Findings

- Live smoke test v1 (free-text query, ≥60% word overlap): 1 correct refusal
  (Llama 3 not in top 5), **2 wrong-paper matches** — Follum & Pierre 2015
  resolved to Follum's PNNL report (downloaded!), Hart 1992 resolved to a
  2012 Wiley paper (stopped only by a 403).
- v2 (structured citation; title Jaccard ≥ 0.8, cited surname among authors,
  year ±1, 25 results scored): Llama 3 downloaded from arXiv (verified: right
  paper, 357k chars); both IEEE papers resolve to the correct DOI and report
  `no-open-pdf`. 3/3 correct.
- Open access covers arXiv-style sources well; IEEE/Wiley and handbooks are
  the gap. Those need Dan's own PDFs (via `collect`) or another route.

## Decisions Made

- New repo `paper-library` (LITE): source papers only — no summaries,
  reviews or claim checks, by design.
- Text in git, PDFs in `~/data/paper-library/pdfs` (via `data/` symlink).
- pymupdf (AGPL noted) + httpx added to pat-helper.
- `find` takes a structured citation (title, author surname, year); a wrong
  source is worse than no source.
- No email sent to OpenAlex (no polite-pool `mailto`); add only if Dan asks.

## Results

- `pat_helper/paperfind.py`, `tests/test_paperfind.py` (18 tests; 76/76 suite).

## Addendum (same session): catalog, not copies

Dan reversed the copy design: take each repo's PAPER_SUMMARIES/PAPER_INDEX,
not its papers, with every entry pointing back to the source. `collect` was
replaced by `catalog` (verbatim copies under `catalogs/<repo>/` +
`catalog.jsonl`, `~/`-relative paths, source git SHA). `find` checks the
catalog with the same title/author/year discipline; `export` reads catalog
papers in place.

First real catalog (paper-library `7055cd5`): 856 entries from
verification 165, econ-impact 212, policy-levers 42, general-ai-abilities
437. Live run exposed: 67 entries with no `File:` pointer (now kept as
visible `repo:L<line>` rows, previously silently dropped); 31 pointing at a
missing PDF; the same paper in two repos (Rahman 2026, `-` vs `_` in the
file name) reported as ambiguous (now deduplicated).

Contamination check (count-only, headings only): 4 verification entries
mention power-side/claim-check terms (Choukse 2025; Leklem & Maheshwari
2026; von Meier et al. 2014; Stewart et al. 2016). pat-helper's own code
never reads summary text — only headings, file names and the papers —
so exposure is limited to agents opening the copied summaries directly.

Dan also asked that hard-constraint facts like the ODEC caps be actively
sought and surfaced; recorded as standing guidance in dotfiles
`personal_info.md` (`22518d6`), and the ODEC note + inferences filed as
verification#71.

**Rule clarified by Dan (later the same session):** other repos'
`PAPER_INDEX.md`, `PAPER_SUMMARIES.md` and paper texts are all fine to read
as needed (index → summary → paper). What's off limits is comparing notes
with *other citation checks* of the draft. The summary-text guard above is
withdrawn; pat-helper and paper-library CLAUDE.md updated (`7ac01c3`,
`f4ba5ec`).

## Next steps (proposed order)

1. **Citation extraction + coverage report** (this branch): parse a draft's
   Sources section into `Citation`s (script first, model fallback), run
   `find` on all, report catalog / downloaded / no-open-pdf / not-found
   counts. Mechanical; tells us whether the finder is good enough before
   building on it. Power-side draft is the test case.
2. **Redesign `source-check`** (its branch's July plan): must run without a
   second provider; must handle "no source for this number" as well as
   "citation mischaracterized"; decide claim-centric vs critique-centric.
3. **Calibrate on power-side** — clean session only (this one saw the
   verification repo's check).

## Open Questions

- (Filed as tasks below) Fix the 67 pointerless and 31 missing-PDF entries.
- A pat-helper lens (or a search-agent prompt) for hard-constraint facts?
- Citations from a draft → `Citation` objects: by hand, or extracted by a
  model from the draft's reference list?
- Paywalled sources: Dan's institutional access? Claude in Chrome rescue?
- Library id uses OpenAlex's publication year (Llama 3 → 2025 although
  cited 2024). Keep, or prefer the cited year?
- Where does `find` plug into the review pipeline — before the review
  (sources folder ready) or after (only for flagged citations)?

## Captured Tasks

- [econ-impact#94: Fix 40 PAPER_SUMMARIES entries with no File: pointer](https://github.com/danparshall/econ-impact/issues/94) — captured 2026-10-14
- [general-ai-abilities#50: Fix 55 PAPER_SUMMARIES entries: 27 no File: pointer, 28 missing PDF](https://github.com/danparshall/general-ai-abilities/issues/50) — captured 2026-10-14
- [verification#72: Fix 3 PAPER_SUMMARIES entries pointing at a missing PDF](https://github.com/danparshall/verification/issues/72) — captured 2026-10-14
- [verification#71: Hard caps from utility planning criteria (ODEC) + power-side inferences](https://github.com/danparshall/verification/issues/71) — captured 2026-10-14
