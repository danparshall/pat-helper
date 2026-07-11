"""Orchestration: fan-out → quote-check → adversarial verify → synthesis.

Stage design (see docs/plans/main/20260709_pat_helper_v1_plan.md):
1. Fan out lens × model cells concurrently (bounded by a semaphore); each
   cell retried with exponential backoff; a dead cell becomes a recorded
   coverage gap, never a crashed run.
2. Mechanical quote-check every finding (zero API cost); ungrounded findings
   are demoted, not deleted.
3. Adversarial verify HIGH/MEDIUM grounded findings; the refuter is always a
   DIFFERENT model than the finder. Refuted findings are demoted.
4. One synthesis call (first provider that proved healthy) dedups/merges and
   records convergence. If synthesis fails, survivors pass through unmerged.
"""

from __future__ import annotations

import asyncio
import json
import logging

from pat_helper.config import ReviewConfig
from pat_helper.latex import FlattenedPaper
from pat_helper.models import (
    FINDINGS_SCHEMA,
    SYNTHESIS_SCHEMA,
    VERDICT_SCHEMA,
    Finding,
    LensSpec,
    ReviewRun,
    Severity,
)
from pat_helper.prompts import SHARED_HEADER, synthesis_prompt, verify_prompt
from pat_helper.providers.base import Provider, TruncatedOutputError
from pat_helper.quotecheck import check_quote

log = logging.getLogger("pat_helper")


async def _with_retries(config: ReviewConfig, factory):
    last_exc: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            return await factory()
        except TruncatedOutputError:
            raise  # deterministic for a given input — retrying burns the same tokens
        except Exception as exc:  # noqa: BLE001 — provider errors are heterogeneous
            last_exc = exc
            if attempt < config.max_retries and config.backoff_base:
                await asyncio.sleep(config.backoff_base * 2**attempt)
    assert last_exc is not None
    raise last_exc


def _parse_findings(payload: dict, lens: LensSpec, model: str) -> list[Finding]:
    findings = []
    for item in payload["findings"]:
        findings.append(
            Finding(
                lens=lens.key,
                model=model,
                quote=item["quote"],
                evidence=item["evidence"],
                severity=Severity(item["severity"]),
                suggested_fix=item["suggested_fix"],
                models=[model],
            )
        )
    return findings


async def _run_cell(
    paper_prefix: str,
    lens: LensSpec,
    provider: Provider,
    config: ReviewConfig,
    sem: asyncio.Semaphore,
) -> tuple[list[Finding], str | None]:
    """Run one lens × model cell. Returns (findings, gap-or-None).

    Prompt order is cache-shaped: the system prompt is the constant
    SHARED_HEADER and the paper is the first (cacheable) user block; the
    per-lens instruction follows the paper, so every lens call on a provider
    shares one cached prefix."""
    system = SHARED_HEADER
    user = (paper_prefix, f"\n\n# YOUR LENS\n\n{lens.prompt}")
    try:
        async with sem:
            payload = await _with_retries(
                config,
                lambda: provider.complete_json(system, user, FINDINGS_SCHEMA),
            )
        return _parse_findings(payload, lens, provider.name), None
    except Exception as exc:  # noqa: BLE001
        gap = f"{lens.key} × {provider.name}: failed after retries ({exc})"
        log.warning(gap)
        return [], gap


def _critique_block(f: Finding) -> str:
    return (
        f"# CRITIQUE (from model: {f.model})\n"
        f"lens: {f.lens}\n"
        f"severity: {f.severity}\n"
        f"quote: {f.quote}\n"
        f"evidence: {f.evidence}\n"
        f"suggested_fix: {f.suggested_fix}\n"
    )


async def _verify(
    paper_text: str,
    finding: Finding,
    refuter: Provider,
    config: ReviewConfig,
    sem: asyncio.Semaphore,
) -> None:
    # Same paper prefix as the lens calls; only the critique varies per call.
    user = (f"# PAPER\n\n{paper_text}", f"\n\n{_critique_block(finding)}")
    try:
        async with sem:
            payload = await _with_retries(
                config,
                lambda: refuter.complete_json(verify_prompt(), user, VERDICT_SCHEMA),
            )
        finding.verified = payload["verdict"]
        finding.verify_notes = f"[{refuter.name}] {payload['reasoning']}"
    except Exception as exc:  # noqa: BLE001
        finding.verified = "upheld"
        finding.verify_notes = f"verification unavailable ({refuter.name}: {exc})"


async def run_review(
    paper: FlattenedPaper,
    providers: list[Provider],
    lenses: list[LensSpec],
    config: ReviewConfig,
) -> ReviewRun:
    run = ReviewRun(paper_name=paper.name)
    sem = asyncio.Semaphore(config.concurrency)
    paper_prefix = f"# PAPER\n\n{paper.text}"

    # --- Stage 1: fan out lens × model cells ---
    # Cache priming: a cache entry is readable only once the writing request
    # has started streaming, so N concurrent identical-prefix calls all miss.
    # Run the first cell per provider to completion (writing the entry), then
    # fan out the rest — costs ~1 call of latency, the fan-out reads the cache.
    pairs = [(lens, provider) for lens in lenses for provider in providers]
    n_prime = min(len(providers), len(pairs))  # lens-major order: one cell per provider
    prime_results = await asyncio.gather(
        *(_run_cell(paper_prefix, lens, prov, config, sem) for lens, prov in pairs[:n_prime])
    )
    rest_results = await asyncio.gather(
        *(_run_cell(paper_prefix, lens, prov, config, sem) for lens, prov in pairs[n_prime:])
    )
    cell_results = list(prime_results) + list(rest_results)
    raw_findings: list[Finding] = []
    healthy: dict[str, bool] = {}
    idx = 0
    for _lens in lenses:
        for provider in providers:
            findings, gap = cell_results[idx]
            idx += 1
            if gap:
                run.gaps.append(gap)
            else:
                healthy[provider.name] = True
            raw_findings.extend(findings)

    # --- Stage 2: mechanical quote-check ---
    grounded: list[Finding] = []
    for f in raw_findings:
        match = check_quote(f.quote, paper, config.fuzzy_threshold)
        f.grounded = match.found
        f.grounding_score = match.score
        f.location_label = match.location.label if match.location else None
        if match.found:
            grounded.append(f)
        else:
            f.verify_notes = "quote not found in paper text"
            run.demoted.append(f)

    # --- Stage 3: adversarial verify (different model refutes) ---
    # The verify system prompt differs from the lens one, so verify calls have
    # their OWN cache prefix — prime it per refuter (first call runs alone),
    # exactly as stage 1 primes the lens prefix.
    by_name = {p.name: i for i, p in enumerate(providers)}
    if len(providers) > 1:
        to_verify = [f for f in grounded if str(f.severity) in config.verify_severities]

        def refuter_of(f: Finding) -> Provider:
            return providers[(by_name[f.model] + 1) % len(providers)]

        primed: set[str] = set()
        prime_batch: list[Finding] = []
        rest_batch: list[Finding] = []
        for f in to_verify:
            if refuter_of(f).name in primed:
                rest_batch.append(f)
            else:
                primed.add(refuter_of(f).name)
                prime_batch.append(f)
        await asyncio.gather(
            *(_verify(paper.text, f, refuter_of(f), config, sem) for f in prime_batch)
        )
        await asyncio.gather(
            *(_verify(paper.text, f, refuter_of(f), config, sem) for f in rest_batch)
        )
    survivors = []
    for f in grounded:
        if f.verified == "refuted":
            run.demoted.append(f)
        else:
            survivors.append(f)

    # --- Stage 4: synthesis (dedup / merge / rank) ---
    if survivors:
        synth_provider = next((p for p in providers if healthy.get(p.name)), providers[0])
        user = "# VERIFIED FINDINGS\n\n" + json.dumps(
            [f.to_json() for f in survivors], indent=2, ensure_ascii=False
        )
        try:
            payload = await _with_retries(
                config,
                lambda: synth_provider.complete_json(
                    synthesis_prompt(),
                    user,
                    SYNTHESIS_SCHEMA,
                    max_output_tokens=config.synthesis_max_output_tokens,
                ),
            )
            merged = []
            for item in payload["findings"]:
                models = item.get("models") or []
                f = Finding(
                    lens=item["lens"],
                    model=models[0] if models else synth_provider.name,
                    quote=item["quote"],
                    evidence=item["evidence"],
                    severity=Severity(item["severity"]),
                    suggested_fix=item["suggested_fix"],
                    models=models,
                )
                # Re-ground merged quotes (synthesis must not alter quotes; trust but verify)
                match = check_quote(f.quote, paper, config.fuzzy_threshold)
                f.grounded = match.found
                f.grounding_score = match.score
                f.location_label = match.location.label if match.location else None
                if match.found:
                    merged.append(f)
                else:
                    f.verify_notes = "synthesis altered the quote; demoted"
                    run.demoted.append(f)
            run.findings = merged
        except Exception as exc:  # noqa: BLE001
            run.gaps.append(
                f"synthesis × {synth_provider.name}: failed ({exc}); passing through unmerged"
            )
            run.findings = survivors

    for p in providers:
        log.info(
            "cache usage %s: cached_input_tokens=%d uncached_input_tokens=%d",
            p.name,
            p.cached_input_tokens,
            p.uncached_input_tokens,
        )
    return run
