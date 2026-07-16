"""CLI: pat-helper review paper.tex [--providers ...] [--lenses ...] [--out dir]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from pat_helper.config import ReviewConfig
from pat_helper.latex import load_paper
from pat_helper.pipeline import run_review
from pat_helper.prompts import LENS_KEYS, load_lenses
from pat_helper.report import render

# Env var each provider's SDK resolves by default. Auth can also come from
# non-env mechanisms (e.g. `ant auth login`), which is why availability is
# probed by construction rather than by checking these vars — see
# docs/plans/main/20260709_v1_hardening_try_except.md.
PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
}


def configure_logging() -> None:
    """Make pat_helper INFO records (e.g. the per-run cache-usage summary)
    visible on stderr.

    The handler goes on the package logger, not the root logger, so
    third-party SDK chatter stays at the default WARNING threshold. Idempotent
    across repeated entry-point invocations in one process.
    """
    log = logging.getLogger("pat_helper")
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.StreamHandler()  # binds sys.stderr
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)


def _build_providers(names: list[str], config: ReviewConfig) -> tuple[list, list[str]]:
    """Construct requested providers; unconstructable ones become coverage gaps.

    Returns (providers, startup_gaps). Raises SystemExit if none are usable.
    """
    providers = []
    gaps: list[str] = []
    for name in names:
        model = config.models[name]
        try:
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
        except Exception as exc:  # noqa: BLE001 — SDK auth errors are heterogeneous;
            # the gap records the concrete type so logic bugs stay visible.
            gaps.append(
                f"{name} unavailable at startup: {type(exc).__name__} "
                f"— check {PROVIDER_ENV_VARS[name]}"
            )
    if not providers:
        raise SystemExit("No usable providers; check .env against .env.example.")
    return providers, gaps


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
    rev.add_argument(
        "--sources",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory of extracted-text files for works the paper cites "
        "('strict mode'): unverifiable findings are checked against the "
        "actual sources and auto-resolved. Omit for today's relaxed behavior.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    load_dotenv()
    config = ReviewConfig(sources_dir=args.sources)
    for override in args.model:
        provider, _, model_id = override.partition("=")
        if not model_id or provider not in config.models:
            raise SystemExit(f"bad --model override: {override!r}")
        config.models[provider] = model_id

    provider_names = [p.strip() for p in args.providers.split(",") if p.strip()]
    providers, startup_gaps = _build_providers(provider_names, config)
    for gap in startup_gaps:
        print(f"WARNING: {gap}", file=sys.stderr)
    lenses = load_lenses([k.strip() for k in args.lenses.split(",") if k.strip()])
    paper = load_paper(args.paper)

    print(
        f"Reviewing {paper.name}: {len(lenses)} lenses × {len(providers)} models "
        f"({', '.join(p.name + '=' + config.models[p.name] for p in providers)})",
        file=sys.stderr,
    )
    run = asyncio.run(run_review(paper, providers, lenses, config))
    run.gaps[:0] = startup_gaps

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
