"""Orchestration: fan-out → quote-check → adversarial verify → synthesis.

Stage design (see docs/plans/main/20260709_pat_helper_v1_plan.md):
1. Fan out lens × model cells concurrently (bounded by a semaphore); each
   cell retried with exponential backoff; a dead cell becomes a recorded
   coverage gap, never a crashed run.
2. Mechanical quote-check every finding (zero API cost); ungrounded findings
   are demoted, not deleted.
3. Adversarial verify HIGH/MEDIUM grounded findings; the refuter is always a
   DIFFERENT model than the finder. Refuted findings are demoted.
3.5. Source check ("strict mode", only with --sources): `unverifiable`
   findings are resolved against author-supplied source texts — the checker
   is a third model where possible, and its verdict is honored only after
   two zero-cost mechanical gates (identity match, source-quote grounding).
   See docs/active/source-check/plans/20260714_source_check_stage.md.
4. One synthesis call (first provider that proved healthy) dedups/merges and
   records convergence. If synthesis fails, survivors pass through unmerged.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pat_helper.config import ReviewConfig
from pat_helper.latex import FlattenedPaper, load_text_source
from pat_helper.models import (
    FINDINGS_SCHEMA,
    SOURCE_CHECK_SCHEMA,
    SYNTHESIS_SCHEMA,
    VERDICT_SCHEMA,
    Finding,
    LensSpec,
    ReviewRun,
    Severity,
)
from pat_helper.prompts import SHARED_HEADER, source_check_prompt, synthesis_prompt, verify_prompt
from pat_helper.providers.base import Provider, TruncatedOutputError
from pat_helper.quotecheck import check_quote
from pat_helper.sourcecheck import (
    AMBIGUOUS,
    build_index,
    extract_citation,
    file_sha256,
    match,
)

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


def _append_note(finding: Finding, note: str) -> None:
    finding.verify_notes = f"{finding.verify_notes} {note}" if finding.verify_notes else note


# Source text passed to a check call is capped so a book-length extraction
# cannot blow the context window. A gated demotion must never rest on a
# truncated read, so truncation forbids "critique-contradicted".
SOURCE_CHAR_CAP = 400_000


async def _source_check_one(
    finding: Finding,
    checker: Provider,
    source: FlattenedPaper,
    path: Path,
    digest: str,
    citation: tuple[str, str],
    config: ReviewConfig,
    sem: asyncio.Semaphore,
) -> None:
    """Run one check call and apply the mechanical gates before any verdict change."""
    tag = f"[source-check:{checker.name} {path.name}@{digest[:8]}]"
    truncated = len(source.text) > SOURCE_CHAR_CAP
    # Cache-shaped like the other stages: the source text is the cacheable
    # prefix shared by every check against this (checker, source) pair.
    user = (f"# SOURCE\n\n{source.text[:SOURCE_CHAR_CAP]}", f"\n\n{_critique_block(finding)}")
    try:
        async with sem:
            payload = await _with_retries(
                config,
                lambda: checker.complete_json(source_check_prompt(), user, SOURCE_CHECK_SCHEMA),
            )
    except Exception as exc:  # noqa: BLE001
        _append_note(finding, f"{tag} check failed ({exc}); left unresolved")
        return
    resolution = payload["resolution"]
    quote = payload["source_quote"]
    # Gate A (zero API cost): the checker-read identity must match the
    # citation — reuses the deterministic matcher against a one-entry index.
    identity_ok = (
        payload["identity_matches_citation"]
        and match(citation, {path: payload["identity"]}) == path
    )
    # Gate B (zero API cost): a resolution-deciding quote must actually appear
    # in the source text.
    quote_ok = check_quote(quote, source, config.fuzzy_threshold).found
    if resolution == "critique-confirmed" and identity_ok:
        finding.verified = "upheld"
        _append_note(
            finding, f'{tag} critique-confirmed — source: "{quote}" ({payload["reasoning"]})'
        )
        return
    if resolution == "critique-contradicted" and identity_ok and quote_ok and not truncated:
        finding.verified = "refuted"
        _append_note(
            finding,
            f'{tag} critique-contradicted — exonerating source quote: "{quote}"'
            f" ({payload['reasoning']})",
        )
        return
    reasons = []
    if not identity_ok:
        reasons.append("source identity does not match the citation")
    if resolution == "critique-contradicted" and not quote_ok:
        reasons.append("source quote did not ground in the source text")
    if resolution == "critique-contradicted" and truncated:
        reasons.append("source was truncated for the check; demotion not honored")
    detail = f" [{'; '.join(reasons)}]" if reasons else ""
    _append_note(finding, f"{tag} unresolved{detail}: {payload['reasoning']}")


async def _run_source_check(
    survivors: list[Finding],
    providers: list[Provider],
    by_name: dict[str, int],
    healthy: dict[str, bool],
    config: ReviewConfig,
    run: ReviewRun,
    sem: asyncio.Semaphore,
) -> list[Finding]:
    """Stage 3.5: resolve `unverifiable` findings against supplied sources.

    Returns the new survivor list (contradicted findings move to demoted).
    Citation→file resolution is deterministic; the model never picks the file.
    Unmatched/ambiguous entries keep their verdict and gain an explanatory note.
    """
    queue = [f for f in survivors if f.verified == "unverifiable"]
    if not queue:
        return survivors
    index_provider = next((p for p in providers if healthy.get(p.name)), providers[0])
    try:
        index = await build_index(config.sources_dir, index_provider, config)
    except Exception as exc:  # noqa: BLE001
        run.gaps.append(f"source-check: index build failed ({exc}); stage skipped")
        return survivors
    if not index:
        log.warning(
            "source-check: no indexable files in %s; all findings stay unresolved",
            config.sources_dir,
        )

    # Checker rotation: a third provider where one exists (≠ finder, ≠ refuter);
    # with two providers the checker falls back to the refuter (offset 1).
    offset = 2 if len(providers) >= 3 else 1
    checkable: list[tuple[Finding, Provider, Path, tuple[str, str]]] = []
    for f in queue:
        citation = extract_citation(f"{f.quote}\n{f.evidence}")
        if citation is None:
            _append_note(
                f, "[source-check] no single citation found in the critique; left unresolved"
            )
            continue
        label = f"{citation[0]} ({citation[1]})"
        target = match(citation, index)
        if target is None:
            _append_note(
                f, f"[source-check] no matching source supplied for {label}; left unresolved"
            )
            continue
        if target is AMBIGUOUS:
            _append_note(
                f,
                f"[source-check] citation {label} is ambiguous across the supplied sources;"
                " left unresolved",
            )
            continue
        checker = providers[(by_name[f.model] + offset) % len(providers)]
        checkable.append((f, checker, target, citation))

    sources: dict[Path, tuple[FlattenedPaper, str]] = {}
    for _f, _c, path, _cit in checkable:
        if path not in sources:
            sources[path] = (load_text_source(path), file_sha256(path))

    # Prime-then-fan-out per (checker, source): each pair has its own cache
    # prefix, so the first call per pair runs alone to write the cache entry.
    primed: set[tuple[str, Path]] = set()
    prime_batch: list[tuple[Finding, Provider, Path, tuple[str, str]]] = []
    rest_batch: list[tuple[Finding, Provider, Path, tuple[str, str]]] = []
    for item in checkable:
        key = (item[1].name, item[2])
        (rest_batch if key in primed else prime_batch).append(item)
        primed.add(key)
    for batch in (prime_batch, rest_batch):
        await asyncio.gather(
            *(
                _source_check_one(
                    f, checker, sources[path][0], path, sources[path][1], citation, config, sem
                )
                for f, checker, path, citation in batch
            )
        )

    kept: list[Finding] = []
    for f in survivors:
        if f.verified == "refuted":
            run.demoted.append(f)  # symmetric with stage-3 refutation
        else:
            kept.append(f)
    n_upheld = sum(1 for f in queue if f.verified == "upheld")
    n_refuted = sum(1 for f in queue if f.verified == "refuted")
    run.source_check_summary = (
        f"{len(queue)} unverifiable finding(s) checked: {n_upheld} upheld, "
        f"{n_refuted} refuted, {len(queue) - n_upheld - n_refuted} unresolved"
    )
    return kept


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

    # --- Stage 3.5: source check ("strict mode", only with --sources) ---
    if config.sources_dir is not None:
        survivors = await _run_source_check(
            survivors, providers, by_name, healthy, config, run, sem
        )

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
                verified = item.get("verified", "none")
                f = Finding(
                    lens=item["lens"],
                    model=models[0] if models else synth_provider.name,
                    quote=item["quote"],
                    evidence=item["evidence"],
                    severity=Severity(item["severity"]),
                    suggested_fix=item["suggested_fix"],
                    models=models,
                    verified=None if verified == "none" else verified,
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
