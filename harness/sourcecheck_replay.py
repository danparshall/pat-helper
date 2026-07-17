"""Replay `unverifiable` findings through stage 3.5 (source check) — plan step 15.

Live-specimen validation for the source-check stage
(docs/active/source-check/plans/20260714_source_check_stage.md, Part C):
rebuild the findings that the 07-14 reverify replay left `unverifiable`
(from its checkpoint jsonl), point the stage at an author-supplied sources
dir, and run `_run_source_check` with the real providers — same rotation the
pipeline would use (checker = finder + offset 2). Dan adjudicates the
resolutions.

Usage:
    uv run python harness/sourcecheck_replay.py \
        data/harness_out_v9/reverify_checkpoint_review_2026-07-11.jsonl \
        --sources data/sources [--out data/harness_out_v9]

Re-run safety: the stage's own index sidecar (`sources_index.json`) caches
the identity reads, so repeat runs only pay for the check calls themselves.
Every run writes a fresh, fully-conditioned record (markdown table + raw
jsonl of each finding's final state) — nothing is overwritten except today's
own outputs, and the checkpoint input is read-only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from pat_helper.cli import _build_providers, configure_logging  # noqa: E402
from pat_helper.config import ReviewConfig  # noqa: E402
from pat_helper.models import Finding, ReviewRun, Severity  # noqa: E402
from pat_helper.pipeline import _run_source_check  # noqa: E402
from pat_helper.prompts import source_check_prompt  # noqa: E402
from pat_helper.sourcecheck import file_sha256  # noqa: E402

# Same order the v9 runs used; rotation offsets are relative to this list.
PROVIDER_ORDER = ["anthropic", "openai", "google"]


async def amain(args) -> int:
    load_dotenv()
    config = ReviewConfig(sources_dir=Path(args.sources))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in Path(args.checkpoint).read_text().splitlines()]
    specimens = [r for r in records if r["new_verdict"] == "unverifiable"]
    if not specimens:
        raise SystemExit("checkpoint contains no `unverifiable` findings — nothing to replay")
    print(f"{len(specimens)} unverifiable specimen(s) from {args.checkpoint}", file=sys.stderr)

    findings = [
        Finding(
            lens=r["lens"],
            model=r["finder"],
            quote=r["quote"],
            evidence=r["evidence"],
            severity=Severity.HIGH,  # original severity unrecoverable; same caveat as reverify
            suggested_fix=r["suggested_fix"],
            models=[r["finder"]],
            verified="unverifiable",
            verify_notes=r["new_notes"],
        )
        for r in specimens
    ]

    providers, gaps = _build_providers(PROVIDER_ORDER, config)
    if gaps:
        raise SystemExit(f"cannot build all providers (rotation needs all three): {gaps}")
    by_name = {p.name: i for i, p in enumerate(providers)}
    healthy = {p.name: True for p in providers}
    run = ReviewRun(paper_name="task_exposure_v9 (stage-3.5 replay)")
    sem = asyncio.Semaphore(config.concurrency)

    kept = await _run_source_check(findings, providers, by_name, healthy, config, run, sem)

    sources = sorted(
        p for p in Path(args.sources).iterdir() if p.is_file() and not p.name.startswith(".")
    )
    conditions = {
        "source_check_prompt_sha256_16": hashlib.sha256(
            source_check_prompt().encode()
        ).hexdigest()[:16],
        "models": config.models,
        "provider_order": PROVIDER_ORDER,
        "sources": {p.name: file_sha256(p)[:8] for p in sources if p.name != "sources_index.json"},
        "checkpoint": str(args.checkpoint),
        "replayed_severity": "HIGH (original unrecoverable)",
        "run_date": date.today().isoformat(),
    }

    today = date.today().isoformat()
    raw_path = out_dir / f"sourcecheck_replay_{today}.jsonl"
    with raw_path.open("w") as fh:
        for r, f in zip(specimens, findings, strict=True):
            fh.write(
                json.dumps(
                    {
                        "conditions": conditions,
                        "location": r["location"],
                        "lens": f.lens,
                        "finder": r["finder"],
                        "refuter": r["refuter"],
                        "old_verdict": "unverifiable",
                        "new_verdict": f.verified,
                        "notes": f.verify_notes,
                        "demoted": f in run.demoted,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    lines = [
        f"# Source-check replay (stage 3.5) — {today}",
        "",
        f"Specimens: `unverifiable` rows of `{Path(args.checkpoint).name}`.",
        f"Prompt sha256[:16] `{conditions['source_check_prompt_sha256_16']}` · "
        f"sources: {', '.join(f'{n}@{d}' for n, d in conditions['sources'].items())}",
        "",
        f"**Summary:** {run.source_check_summary or '(stage did not run)'}",
        "",
        "| # | lens | location | finder | refuter | old | new | notes (first 400 chars) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, (r, f) in enumerate(zip(specimens, findings, strict=True)):
        snippet = (f.verify_notes or "").replace("|", "/").replace("\n", " ")[:400]
        lines.append(
            f"| {i} | {f.lens} | {r['location'] or '—'} | {r['finder']} | {r['refuter']} "
            f"| unverifiable | **{f.verified}** | {snippet} |"
        )
    if run.gaps:
        lines += ["", "Gaps: " + "; ".join(run.gaps)]
    out_path = out_dir / f"sourcecheck_replay_{today}.md"
    out_path.write_text("\n".join(lines) + "\n")

    for p in providers:
        print(
            f"cache usage {p.name}: cached={p.cached_input_tokens} "
            f"uncached={p.uncached_input_tokens}",
            file=sys.stderr,
        )
    print(f"{len(kept)} kept / {len(run.demoted)} demoted → {out_path}", file=sys.stderr)
    return 0


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", help="reverify checkpoint .jsonl to draw specimens from")
    parser.add_argument("--sources", required=True, help="dir of extracted-text source files")
    parser.add_argument("--out", default=str(REPO / "harness" / "out"))
    return asyncio.run(amain(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
