"""CLI graceful degradation for missing API keys.

Plan: docs/plans/main/20260709_v1_hardening_try_except.md (Plan A).
Fake SDK clients raise (or succeed) at construction, monkeypatched into each
provider module — no live API calls.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import pat_helper.cli as cli
from pat_helper.config import JUDGE_MODEL, ReviewConfig

FIXTURE = Path(__file__).parent / "fixtures" / "main.tex"

EMPTY_FINDINGS = '{"findings": []}'


class _RaisingSDK:
    """Stands in for any SDK client whose constructor rejects missing creds."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("missing credentials")


class _FakeAnthropicSDK:
    def __init__(self, *args, **kwargs):
        async def create(**kwargs):
            block = SimpleNamespace(type="text", text=EMPTY_FINDINGS)
            return SimpleNamespace(content=[block])

        self.messages = SimpleNamespace(create=create)


class _FakeOpenAISDK:
    def __init__(self, *args, **kwargs):
        async def create(**kwargs):
            return SimpleNamespace(output_text=EMPTY_FINDINGS)

        self.responses = SimpleNamespace(create=create)


class _FakeGoogleSDK:
    def __init__(self, *args, **kwargs):
        async def generate_content(**kwargs):
            return SimpleNamespace(text=EMPTY_FINDINGS)

        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


_SDK_ATTRS = {
    "anthropic": ("pat_helper.providers.anthropic_client.AsyncAnthropic", _FakeAnthropicSDK),
    "openai": ("pat_helper.providers.openai_client.AsyncOpenAI", _FakeOpenAISDK),
    "google": ("pat_helper.providers.google_client.genai.Client", _FakeGoogleSDK),
}


def _patch_sdks(monkeypatch, broken: set[str] = frozenset()):
    for name, (attr, fake) in _SDK_ATTRS.items():
        monkeypatch.setattr(attr, _RaisingSDK if name in broken else fake)


def test_missing_openai_key_records_gap_and_continues(monkeypatch, tmp_path):
    _patch_sdks(monkeypatch, broken={"openai"})
    rc = cli.main(["review", str(FIXTURE), "--out", str(tmp_path)])
    assert rc == 0
    report = next(tmp_path.glob("review_*.md")).read_text()
    gap_lines = [ln for ln in report.splitlines() if "unavailable at startup" in ln]
    assert len(gap_lines) == 1
    assert "openai" in gap_lines[0]
    assert "OPENAI_API_KEY" in gap_lines[0]


def test_all_keys_missing_exits_cleanly(monkeypatch, tmp_path):
    _patch_sdks(monkeypatch, broken={"anthropic", "openai", "google"})
    expected = r"No usable providers; check \.env against \.env\.example\."
    with pytest.raises(SystemExit, match=expected):
        cli.main(["review", str(FIXTURE), "--out", str(tmp_path)])


def test_explicit_providers_subset_missing_key_exits(monkeypatch, tmp_path):
    _patch_sdks(monkeypatch, broken={"openai"})
    with pytest.raises(SystemExit, match=r"No usable providers"):
        cli.main(["review", str(FIXTURE), "--providers", "openai", "--out", str(tmp_path)])


def test_all_keys_present_no_startup_gaps(monkeypatch):
    _patch_sdks(monkeypatch)
    providers, gaps = cli._build_providers(["anthropic", "openai", "google"], ReviewConfig())
    assert [p.name for p in providers] == ["anthropic", "openai", "google"]
    assert gaps == []


def test_judge_provider_unavailable_fails_fast(monkeypatch):
    judge_provider = JUDGE_MODEL[0]
    _patch_sdks(monkeypatch, broken={judge_provider})
    from harness.run import build_judge

    with pytest.raises(SystemExit, match=rf"Judge model \({judge_provider}\) unavailable"):
        build_judge()


# --- source check (--sources) --------------------------------------------


def test_sources_flag_populates_config(monkeypatch, tmp_path):
    """--sources <dir> must reach the pipeline as config.sources_dir; omitting
    the flag must leave it None (relaxed mode, today's behavior)."""
    from pat_helper.models import ReviewRun

    _patch_sdks(monkeypatch)
    captured = []

    async def capture_run_review(paper, providers, lenses, config):
        captured.append(config)
        return ReviewRun(paper_name=paper.name)

    monkeypatch.setattr(cli, "run_review", capture_run_review)
    src = tmp_path / "sources"
    src.mkdir()

    rc = cli.main(["review", str(FIXTURE), "--sources", str(src), "--out", str(tmp_path)])
    assert rc == 0
    assert captured[0].sources_dir == src

    rc = cli.main(["review", str(FIXTURE), "--out", str(tmp_path)])
    assert rc == 0
    assert captured[1].sources_dir is None


# --- logging visibility -------------------------------------------------
# Regression: the 2026-07-11 paid v9 harness run silently dropped the per-run
# cache-usage summary (pipeline logs it at INFO on the "pat_helper" logger)
# because no entry point ever configured logging — Python's last-resort
# handler drops anything below WARNING.


@pytest.fixture()
def _reset_pat_helper_logger():
    import logging

    log = logging.getLogger("pat_helper")
    saved_level, saved_handlers, saved_propagate = log.level, list(log.handlers), log.propagate
    # Clean slate first: earlier tests may have run the entry point and left a
    # handler bound to the real stderr, which would defeat capsys assertions.
    log.handlers[:] = []
    log.setLevel(logging.NOTSET)
    yield
    log.setLevel(saved_level)
    log.handlers[:] = saved_handlers
    log.propagate = saved_propagate


def test_configure_logging_makes_pat_helper_info_visible_on_stderr(
    capsys, _reset_pat_helper_logger
):
    import logging

    cli.configure_logging()
    logging.getLogger("pat_helper").info("cache usage test-sentinel: cached=1 uncached=2")
    assert "test-sentinel" in capsys.readouterr().err


def test_cli_entry_point_emits_cache_usage_summary(
    monkeypatch, tmp_path, capsys, _reset_pat_helper_logger
):
    _patch_sdks(monkeypatch)
    cli.main(["review", str(FIXTURE), "--out", str(tmp_path)])
    assert "cache usage" in capsys.readouterr().err
