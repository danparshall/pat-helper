"""Request-shape tests for the (cacheable_prefix, volatile_suffix) user form.

Plan: docs/plans/main/20260711_prompt_caching.md. Fake SDK clients capture the
request kwargs each provider sends (same monkeypatch seam as test_cli.py) — no
live API calls. Behavior under test: what the vendor API would receive.

- Anthropic: tuple → two user content blocks, cache_control on the first
  (an explicit cache breakpoint; prefix-cached).
- OpenAI / Google: tuple → one concatenated user string (their caching is
  automatic on repeated prefixes; identical ordering is the whole game).
- Plain str → request shape unchanged for all three.
"""

from __future__ import annotations

from types import SimpleNamespace

from pat_helper.providers.anthropic_client import AnthropicProvider
from pat_helper.providers.google_client import GoogleProvider
from pat_helper.providers.openai_client import OpenAIProvider

SCHEMA = {"type": "object"}
OK_JSON = '{"ok": 1}'


class _CapturingAnthropicSDK:
    last: _CapturingAnthropicSDK

    def __init__(self, *args, **kwargs):
        _CapturingAnthropicSDK.last = self
        self.captured: dict = {}
        sdk = self

        class _Stream:
            def __init__(self, **kw):
                sdk.captured = kw

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get_final_message(self):
                return SimpleNamespace(
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=OK_JSON)],
                    usage=SimpleNamespace(
                        input_tokens=10,
                        output_tokens=1,
                        cache_read_input_tokens=0,
                        cache_creation_input_tokens=0,
                    ),
                )

        self.messages = SimpleNamespace(stream=_Stream)


class _CapturingOpenAISDK:
    last: _CapturingOpenAISDK

    def __init__(self, *args, **kwargs):
        _CapturingOpenAISDK.last = self
        self.captured: dict = {}

        async def create(**kw):
            self.captured = kw
            return SimpleNamespace(
                status="completed",
                incomplete_details=None,
                output_text=OK_JSON,
                usage=SimpleNamespace(
                    input_tokens=10,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                ),
            )

        self.responses = SimpleNamespace(create=create)


class _CapturingGoogleSDK:
    last: _CapturingGoogleSDK

    def __init__(self, *args, **kwargs):
        _CapturingGoogleSDK.last = self
        self.captured: dict = {}

        async def generate_content(**kw):
            self.captured = kw
            return SimpleNamespace(
                candidates=[SimpleNamespace(finish_reason="STOP")],
                text=OK_JSON,
                usage_metadata=SimpleNamespace(prompt_token_count=10, cached_content_token_count=0),
            )

        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def _patch(monkeypatch):
    monkeypatch.setattr(
        "pat_helper.providers.anthropic_client.AsyncAnthropic", _CapturingAnthropicSDK
    )
    monkeypatch.setattr("pat_helper.providers.openai_client.AsyncOpenAI", _CapturingOpenAISDK)
    monkeypatch.setattr("pat_helper.providers.google_client.genai.Client", _CapturingGoogleSDK)


# --- Anthropic ---


async def test_anthropic_tuple_renders_two_blocks_with_cache_control(monkeypatch):
    _patch(monkeypatch)
    prov = AnthropicProvider(model="test-model")
    result = await prov.complete_json("SYS", ("PREFIX", "SUFFIX"), SCHEMA)
    assert result == {"ok": 1}
    messages = _CapturingAnthropicSDK.last.captured["messages"]
    assert messages == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "PREFIX", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "SUFFIX"},
            ],
        }
    ]


async def test_anthropic_plain_string_request_unchanged(monkeypatch):
    _patch(monkeypatch)
    prov = AnthropicProvider(model="test-model")
    await prov.complete_json("SYS", "USER", SCHEMA)
    messages = _CapturingAnthropicSDK.last.captured["messages"]
    assert messages == [{"role": "user", "content": "USER"}]


# --- OpenAI ---


async def test_openai_tuple_concatenates_to_single_user_string(monkeypatch):
    _patch(monkeypatch)
    prov = OpenAIProvider(model="test-model")
    result = await prov.complete_json("SYS", ("PREFIX", "SUFFIX"), SCHEMA)
    assert result == {"ok": 1}
    inp = _CapturingOpenAISDK.last.captured["input"]
    assert inp == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "PREFIXSUFFIX"},
    ]


async def test_openai_plain_string_request_unchanged(monkeypatch):
    _patch(monkeypatch)
    prov = OpenAIProvider(model="test-model")
    await prov.complete_json("SYS", "USER", SCHEMA)
    inp = _CapturingOpenAISDK.last.captured["input"]
    assert inp == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USER"},
    ]


# --- Google ---


async def test_google_tuple_concatenates_to_single_contents_string(monkeypatch):
    _patch(monkeypatch)
    prov = GoogleProvider(model="test-model")
    result = await prov.complete_json("SYS", ("PREFIX", "SUFFIX"), SCHEMA)
    assert result == {"ok": 1}
    assert _CapturingGoogleSDK.last.captured["contents"] == "PREFIXSUFFIX"


async def test_google_plain_string_request_unchanged(monkeypatch):
    _patch(monkeypatch)
    prov = GoogleProvider(model="test-model")
    await prov.complete_json("SYS", "USER", SCHEMA)
    assert _CapturingGoogleSDK.last.captured["contents"] == "USER"
