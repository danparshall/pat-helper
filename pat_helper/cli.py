"""CLI: pat-helper review paper.tex [--providers ...] [--lenses ...] [--out dir]"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from pat_helper.config import ReviewConfig
from pat_helper.latex import load_paper
from pat_helper.pipeline import run_review
from pat_helper.prompts import LENS_KEYS, load_lenses
from pat_helper.report import render


def _build_providers(names: list[str], config: ReviewConfig):
    providers = []
    for name in names:
        model = config.models[name]
        if name == "anthropic":
            from pat_helper.providers.anthropic_client import AnthropicProvider

            providers.append(AnthropicProvider(model, config.max_output_tokens))
        elif name == "openai":
            from pat_helper.providers.openai_client import OpenAIProvider

            providers.append(OpenAIProvider(model, config.max_output_tokens))
        elif name == "google":
            from pat_helper.providers.google_client import GoogleProvider

            providers.append(GoogleProvider(model, config.max_output_tokens))
        else:
            raise SystemExit(f"unknown provider: {name}")
    return providers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pat-helper")
    sub = parser.add_subparsers(dest="command", required=True)
    rev = sub.add_parser("review", help="Review a LaTeX paper")
    rev.add_argument("paper", type=Path, help="Path to the main .tex file")
    rev.add_argument(
        "--providers",
        default="anthropic,openai,google",
        help="Comma-separated subset of: anthropic,openai,google",
    )
    rev.add_argument(
        "--model",
        action="append",
        default=[],
        metavar="PROVIDER=MODEL_ID",
        help="Override a model id, e.g. --model openai=gpt-5.6-sol (repeatable)",
    )
    rev.add_argument(
        "--lenses",
        default=",".join(LENS_KEYS),
        help="Comma-separated subset of lens keys",
    )
    rev.add_argument("--out", type=Path, default=Path("."), help="Output directory")
    args = parser.parse_args(argv)

    load_dotenv()
    config = ReviewConfig()
    for override in args.model:
        provider, _, model_id = override.partition("=")
        if not model_id or provider not in config.models:
            raise SystemExit(f"bad --model override: {override!r}")
        config.models[provider] = model_id

    provider_names = [p.strip() for p in args.providers.split(",") if p.strip()]
    providers = _build_providers(provider_names, config)
    lenses = load_lenses([k.strip() for k in args.lenses.split(",") if k.strip()])
    paper = load_paper(args.paper)

    print(
        f"Reviewing {paper.name}: {len(lenses)} lenses × {len(providers)} models "
        f"({', '.join(config.models[n] for n in provider_names)})",
        file=sys.stderr,
    )
    run = asyncio.run(run_review(paper, providers, lenses, config))

    today = date.today()
    out_path = args.out / f"review_{paper.name}_{today.isoformat()}.md"
    out_path.write_text(render(run, run_date=today))
    print(
        f"{len(run.findings)} findings · {len(run.demoted)} demoted · "
        f"{len(run.gaps)} gaps → {out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
