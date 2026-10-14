"""pat-helper's Anthropic calls bill to a dedicated key, PAPER_ASSISTANT_KEY.

Dan keeps one Anthropic key reserved for this tool (2026-10-14). The provider
must use it, and must NOT fall back to the generic ANTHROPIC_API_KEY — on
2026-10-13 a run silently drained the general-purpose personal key.

Uses the real AsyncAnthropic client: construction makes no network call, and
the resolved key is the behavior under test.
"""

from __future__ import annotations

import pytest

import pat_helper.cli as cli
from pat_helper.config import ReviewConfig
from pat_helper.providers.anthropic_client import ANTHROPIC_KEY_ENV, AnthropicProvider


def test_key_env_name_is_paper_assistant_key():
    assert ANTHROPIC_KEY_ENV == "PAPER_ASSISTANT_KEY"


def test_provider_uses_dedicated_key_over_generic(monkeypatch):
    monkeypatch.setenv("PAPER_ASSISTANT_KEY", "sk-ant-dedicated")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-generic")
    prov = AnthropicProvider(model="test-model")
    assert prov._client.api_key == "sk-ant-dedicated"


def test_provider_refuses_generic_key_fallback(monkeypatch):
    monkeypatch.delenv("PAPER_ASSISTANT_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-generic")
    with pytest.raises(RuntimeError, match="PAPER_ASSISTANT_KEY"):
        AnthropicProvider(model="test-model")


def test_cli_gap_names_dedicated_key(monkeypatch):
    monkeypatch.delenv("PAPER_ASSISTANT_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-generic")
    with pytest.raises(SystemExit):
        cli._build_providers(["anthropic"], ReviewConfig())
    assert cli.PROVIDER_ENV_VARS["anthropic"] == "PAPER_ASSISTANT_KEY"
