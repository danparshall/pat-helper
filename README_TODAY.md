# README_TODAY — verdict-lattice session state (written 2026-08-02)

Per your mid-session instruction ("push no matter what, README_TODAY if
anything concerns you"). Everything is committed and pushed on
`source-check`; nothing is blocked. Two things worth your eyes:

## 1. Gate verdict: `softened (source-checked)`, not `upheld (source-checked)`

The step-22 paid gate passed every mechanical check (recall 3/3, contributor
bookkeeping fully compliant — 0 gaps, tag + annotation render). But the
merged Svanberg finding shows `softened (source-checked)` because google's
checker returned `critique-narrowed` while anthropic's returned
`critique-confirmed` — two source-tier verdicts, and within-tier
conservatism picks softened. The lattice behaved exactly as designed and
tested; the question is **checker calibration**: google's own reasoning says
the 14%-vs-40% error is "fully validated" but it judged the critique's
central charge to be the construct mismatch. Details + options:
`docs/active/source-check/results/20260802_step22_lattice_gate.md`.

**If you need the report for use today:** the output is safe to use as-is —
the numeric error is plainly visible in the notes with both checkers'
verbatim source quotes. The only question is whether the `softened` label
undersells it.

## 2. Where everything is

- Code: Parts 1–4 of `plans/20260731_verdict_lattice_provenance.md` landed
  via TDD, commits `2f2c6d9`, `1c2b187`, `534e7d6`, `b634e85`. Suite 123/123.
- Gate outputs: `data/harness_out_v9/{review,harness}_2026-08-02.md`.
- Not exercised live: the Part 3 demoted digest (this run had 0 demoted) —
  covered by fakes only so far.
- Still carried: your extras/demoted skim (issue #1, snoozed-by-skip);
  symmetric propagation is issue #2.

Delete this file whenever you've read it — the durable record is in
results/ + RESEARCH_LOG.
