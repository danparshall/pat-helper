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

## Open Questions

- Populate the library: run `collect` on verification / econ-impact /
  policy-levers / general-ai-abilities `papers/`? (Not yet run.)
- Citations from a draft → `Citation` objects: by hand, or extracted by a
  model from the draft's reference list?
- Paywalled sources: Dan's institutional access? Claude in Chrome rescue?
- Library id uses OpenAlex's publication year (Llama 3 → 2025 although
  cited 2024). Keep, or prefer the cited year?
- Where does `find` plug into the review pipeline — before the review
  (sources folder ready) or after (only for flagged citations)?
