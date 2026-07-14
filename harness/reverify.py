"""Re-run adversarial verification on previously-refuted findings.

Calibration replay for the 'unverifiable' verdict
(docs/plans/main/20260713_unverifiable_verdict.md, Part C): parse the demoted
appendix of a rendered review file, select the findings that were demoted by
refutation (``*verification:* refuted``), rebuild Finding objects, and re-run
the verify stage with the SAME refuter model against the same
(defect-injected) paper — isolating the verify-prompt change as the only
variable.

Usage:
    uv run python harness/reverify.py data/harness_out_v9/review_2026-07-11.md \
        --paper data/harness_out_v9/mutated/task_exposure_v9.tex \
        [--out data/harness_out_v9]

Checkpointed + resume-safe: each verdict is appended to
``<out>/reverify_checkpoint_<review-stem>.jsonl`` as it lands, keyed by a
content hash and stamped with the exact conditions (verify-prompt sha256,
refuter provider + model). Re-running skips finished entries; entries whose
verify call failed are NOT checkpointed and will be retried.

Known caveat, recorded per entry: the renderer does not include severity for
appendix entries, so original severities are unrecoverable — every replayed
critique is presented to the refuter as HIGH. (Run 1 verified only
HIGH/MEDIUM findings, so the distortion is at most one level.)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from pat_helper.cli import _build_providers, configure_logging  # noqa: E402
from pat_helper.config import ReviewConfig  # noqa: E402
from pat_helper.latex import load_paper  # noqa: E402
from pat_helper.models import Finding, Severity  # noqa: E402
from pat_helper.pipeline import _verify  # noqa: E402
from pat_helper.prompts import verify_prompt  # noqa: E402

APPENDIX_MARKER = "## Appendix — demoted findings"


def parse_refuted(review_md: str) -> list[dict]:
    """Extract refuted findings from a rendered review's demoted appendix.

    Returns dicts with lens, location, quote, evidence, suggested_fix,
    finder (model), refuter, old_notes. Fails loudly on entries it cannot
    parse rather than skipping silently.
    """
    if APPENDIX_MARKER not in review_md:
        raise SystemExit(f"no demoted appendix found (marker: {APPENDIX_MARKER!r})")
    appendix = review_md.split(APPENDIX_MARKER, 1)[1]
    entries = re.split(r"\n(?=### \[)", appendix)
    out: list[dict] = []
    n_refuted_markers = appendix.count("*verification:* refuted")
    for entry in entries:
        if "*verification:* refuted" not in entry:
            continue
        header = re.match(r"### \[(?P<lens>[^\]]+)\](?: — `(?P<loc>[^`]+)`)?", entry)
        blocks = [b.strip() for b in entry.split("\n\n") if b.strip()]
        quote = evidence = fix = models_block = None
        for b in blocks:
            if b.startswith("> "):
                quote = b[2:]
            elif b.startswith("**Why:** "):
                evidence = b[len("**Why:** ") :]
            elif b.startswith("**Suggested fix:** "):
                fix = b[len("**Suggested fix:** ") :]
            elif b.startswith("*Models:*"):
                models_block = b
        if not (header and quote and evidence and fix and models_block):
            raise SystemExit(f"unparseable refuted entry:\n{entry[:400]}")
        finder = re.search(r"\*Models:\* ([^ ·\n]+)", models_block).group(1)
        notes_m = re.search(r"\*notes:\* \[(?P<refuter>[^\]]+)\] (?P<notes>.*)", models_block, re.S)
        if not notes_m:
            raise SystemExit(f"refuted entry has no [refuter]-prefixed notes:\n{entry[:400]}")
        out.append(
            {
                "lens": header.group("lens"),
                "location": header.group("loc"),
                "quote": quote,
                "evidence": evidence,
                "suggested_fix": fix,
                "finder": finder,
                "refuter": notes_m.group("refuter"),
                "old_notes": notes_m.group("notes").strip(),
            }
        )
    if len(out) != n_refuted_markers:
        raise SystemExit(
            f"parsed {len(out)} refuted entries but appendix contains "
            f"{n_refuted_markers} refuted markers — parser missed some"
        )
    return out


def entry_key(e: dict) -> str:
    basis = "\n".join((e["quote"], e["evidence"], e["refuter"]))
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


async def amain(args) -> int:
    load_dotenv()
    config = ReviewConfig()
    review_path = Path(args.review)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / f"reverify_checkpoint_{review_path.stem}.jsonl"

    entries = parse_refuted(review_path.read_text())
    print(f"Parsed {len(entries)} refuted findings from {review_path}", file=sys.stderr)

    done: dict[str, dict] = {}
    if ckpt_path.exists():
        for line in ckpt_path.read_text().splitlines():
            rec = json.loads(line)
            done[rec["key"]] = rec
        print(f"Resume: {len(done)} entries already checkpointed", file=sys.stderr)

    todo = [e for e in entries if entry_key(e) not in done]
    prompt_sha = hashlib.sha256(verify_prompt().encode()).hexdigest()[:16]

    if todo:
        refuter_names = sorted({e["refuter"] for e in todo})
        providers, gaps = _build_providers(refuter_names, config)
        if gaps:
            raise SystemExit(f"cannot build all refuters: {gaps}")
        by_name = {p.name: p for p in providers}
        paper = load_paper(Path(args.paper))
        sem = asyncio.Semaphore(config.concurrency)

        async def replay(e: dict) -> dict | None:
            f = Finding(
                lens=e["lens"],
                model=e["finder"],
                quote=e["quote"],
                evidence=e["evidence"],
                severity=Severity.HIGH,  # original severity unrecoverable; see module docstring
                suggested_fix=e["suggested_fix"],
                models=[e["finder"]],
            )
            await _verify(paper.text, f, by_name[e["refuter"]], config, sem)
            if f.verify_notes and f.verify_notes.startswith("verification unavailable"):
                print(f"  RETRY-NEXT-RUN {e['lens']}: {f.verify_notes}", file=sys.stderr)
                return None  # not checkpointed -> retried on resume
            return {
                "key": entry_key(e),
                "conditions": {
                    "verify_prompt_sha256_16": prompt_sha,
                    "refuter_provider": e["refuter"],
                    "refuter_model": config.models[e["refuter"]],
                    "replayed_severity": "HIGH (original unrecoverable)",
                    "source_review": str(review_path),
                    "run_date": date.today().isoformat(),
                },
                **e,
                "new_verdict": f.verified,
                "new_notes": f.verify_notes,
            }

        # Prime one call per refuter (writes the cache entry), then fan out.
        primed: set[str] = set()
        prime_batch, rest_batch = [], []
        for e in todo:
            (rest_batch if e["refuter"] in primed else prime_batch).append(e)
            primed.add(e["refuter"])
        results = []
        for batch in (prime_batch, rest_batch):
            for rec in await asyncio.gather(*(replay(e) for e in batch)):
                if rec is not None:
                    results.append(rec)
                    with ckpt_path.open("a") as fh:  # checkpoint per result
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    done[rec["key"]] = rec
        for p in providers:
            print(
                f"cache usage {p.name}: cached={p.cached_input_tokens} "
                f"uncached={p.uncached_input_tokens}",
                file=sys.stderr,
            )

    # --- Render comparison table from ALL checkpointed results ---
    rows = [done[entry_key(e)] for e in entries if entry_key(e) in done]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["new_verdict"]] = counts.get(r["new_verdict"], 0) + 1
    today = date.today().isoformat()
    lines = [
        f"# Reverify replay — {today}",
        "",
        f"Source: `{review_path.name}` demoted appendix (old verdict for every row: **refuted**).",
        f"Same refuter as the original run; verify prompt sha256[:16] `{prompt_sha}`.",
        f"Replayed severity: HIGH for all (originals unrecoverable from rendered appendix).",
        "",
        f"**{len(rows)}/{len(entries)} replayed** · new verdicts: "
        + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        "",
        "| # | lens | location | refuter | old | new | new reasoning (first 300 chars) |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows):
        snippet = (r["new_notes"] or "").replace("|", "/").replace("\n", " ")[:300]
        lines.append(
            f"| {i} | {r['lens']} | {r['location'] or '—'} | {r['refuter']} "
            f"| refuted | **{r['new_verdict']}** | {snippet} |"
        )
    out_path = out_dir / f"reverify_{today}.md"
    out_path.write_text("\n".join(lines) + "\n")
    print(f"{len(rows)}/{len(entries)} replayed → {out_path}", file=sys.stderr)
    return 0


def main() -> int:
    configure_logging()  # cache-usage summary is INFO; without this it is dropped
    parser = argparse.ArgumentParser()
    parser.add_argument("review", help="Rendered review .md whose demoted appendix to replay")
    parser.add_argument("--paper", required=True, help="Path to the SAME (mutated) main .tex")
    parser.add_argument("--out", default=str(REPO / "harness" / "out"))
    return asyncio.run(amain(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
