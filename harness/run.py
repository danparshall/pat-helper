"""Planted-error harness: inject defects -> run review -> score recall.

Usage:
    uv run python harness/run.py tests/fixtures/main.tex \
        [--defects harness/defects.yaml] [--out harness/out] \
        [--providers anthropic,openai,google]

Live API calls — not part of pytest. Recall is scored by an LLM judge
(cheap model) matching surviving findings against each defect description;
unmatched findings are reported as "extras", not counted as false positives.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from pat_helper.config import JUDGE_MODEL, ReviewConfig  # noqa: E402
from pat_helper.injector import inject  # noqa: E402
from pat_helper.latex import load_paper  # noqa: E402
from pat_helper.pipeline import run_review  # noqa: E402
from pat_helper.prompts import load_lenses  # noqa: E402
from pat_helper.providers.anthropic_client import AnthropicProvider  # noqa: E402
from pat_helper.providers.google_client import GoogleProvider  # noqa: E402
from pat_helper.providers.openai_client import OpenAIProvider  # noqa: E402
from pat_helper.report import render  # noqa: E402

# Judge-provider dispatch. Kept out of _build_providers so the judge picks its
# own model (JUDGE_MODEL[1]) independent of the review fan-out's config.models.
_JUDGE_CLASSES = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "matched": {"type": "boolean"},
        "finding_index": {"type": ["integer", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["matched", "finding_index", "reasoning"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """\
You judge whether an automated paper-review finding identified a specific
planted defect. Match on substance, not wording: the finding counts if a
reasonable author reading it would discover the planted problem. Return
matched=true with the 0-based index of the best-matching finding, or
matched=false with finding_index=null.
"""


async def judge_defect(judge, defect: dict, findings: list[dict]) -> dict:
    user = (
        f"# PLANTED DEFECT\n{defect['description']}\n"
        f"(mutated text: {defect['mutated']!r} in {defect['file']}:{defect['line']})\n\n"
        f"# FINDINGS\n{json.dumps(findings, indent=2, ensure_ascii=False)}"
    )
    return await judge.complete_json(JUDGE_SYSTEM, user, JUDGE_SCHEMA)


async def amain(args) -> int:
    load_dotenv()
    config = ReviewConfig()

    main_tex = Path(args.paper).resolve()
    src_dir = main_tex.parent
    out_dir = Path(args.out)
    mutated_dir = out_dir / "mutated"

    defects = yaml.safe_load(Path(args.defects).read_text())
    manifest = inject(src_dir, defects, mutated_dir)
    print(f"Injected {len(manifest)} defects into {mutated_dir}", file=sys.stderr)

    from pat_helper.cli import _build_providers

    provider_names = [p.strip() for p in args.providers.split(",") if p.strip()]
    providers = _build_providers(provider_names, config)
    paper = load_paper(mutated_dir / main_tex.name)
    run = await run_review(paper, providers, load_lenses(), config)
    print(
        f"Review done: {len(run.findings)} findings, {len(run.demoted)} demoted, "
        f"{len(run.gaps)} gaps",
        file=sys.stderr,
    )

    judge = _JUDGE_CLASSES[JUDGE_MODEL[0]](JUDGE_MODEL[1])
    findings_json = [f.to_json() for f in run.findings]
    results = []
    for defect in manifest:
        verdict = await judge_defect(judge, defect, findings_json)
        results.append((defect, verdict))
        status = "HIT " if verdict["matched"] else "MISS"
        print(f"  {status} {defect['id']}: {verdict['reasoning'][:100]}", file=sys.stderr)

    hits = sum(1 for _, v in results if v["matched"])
    matched_idx = {v["finding_index"] for _, v in results if v["matched"]}
    extras = [f for i, f in enumerate(findings_json) if i not in matched_idx]

    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    lines = [
        f"# Harness run — {today}",
        "",
        f"**Recall: {hits}/{len(manifest)}**  ·  models: "
        + ", ".join(config.models[n] for n in provider_names),
        "",
        "| defect | expected lens | result | judge reasoning |",
        "|---|---|---|---|",
    ]
    for defect, verdict in results:
        res = "HIT" if verdict["matched"] else "MISS"
        reason = verdict["reasoning"].replace("|", "/")
        lines.append(f"| {defect['id']} | {defect['lens_expected']} | {res} | {reason} |")
    lines += ["", f"## Extras ({len(extras)} findings matched no planted defect)", ""]
    lines += [f"- [{f['lens']}] {f['evidence']}" for f in extras]
    (out_dir / f"harness_{today}.md").write_text("\n".join(lines) + "\n")
    (out_dir / f"review_{today}.md").write_text(render(run))
    print(f"Recall {hits}/{len(manifest)} → {out_dir}/harness_{today}.md", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", help="Path to main .tex of the SOURCE paper")
    parser.add_argument("--defects", default=str(REPO / "harness" / "defects.yaml"))
    parser.add_argument("--out", default=str(REPO / "harness" / "out"))
    parser.add_argument("--providers", default="anthropic,openai,google")
    return asyncio.run(amain(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
