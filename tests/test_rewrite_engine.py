"""Tests for RewriteEngine.generate_async().

These tests run without a live Ollama / cloud LLM instance. The fallback path
is tested by mocking httpx to raise errors, which causes the rewrite functions
to return the stub hint.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ats_matcher.models import Bullet, PhraseMatch, ResumeData, Section, Role
from ats_matcher.rewrite_engine import RewriteEngine, _strip_thinking


def _make_resume() -> ResumeData:
    bullet = Bullet(
        bullet_id="b1",
        text="Led cross-functional teams to deliver projects on time.",
        paragraph_index=0,
        section_title="Experience",
        role_title="Engineer",
    )
    role = Role(title="Engineer", bullets=[bullet])
    section = Section(title="Experience", roles=[role])
    return ResumeData(sections=[section], bullet_index={"b1": bullet})


def _make_match(phrase: str, match_type: str, bullet_id: str | None) -> PhraseMatch:
    return PhraseMatch(
        phrase=phrase,
        match_type=match_type,
        similarity=0.5,
        evidence_bullet_id=bullet_id,
        evidence_text=None,
    )


def _mock_openai_response(content: str) -> MagicMock:
    """Build a mock HTTP response in OpenAI chat completions format."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


# ── generate_async: fallback when Ollama is unreachable ───────────────────────

@pytest.mark.asyncio
async def test_generate_async_fallback_on_connection_error(monkeypatch):
    """When Ollama is down, suggestion_text falls back to 'Add keyword: X'."""
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    resume = _make_resume()
    matches = [_make_match("kubernetes", "missing", "b1")]

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert suggestions[0].suggestion_text == "Add keyword: kubernetes"
    assert suggestions[0].bullet_id == "b1"
    assert suggestions[0].phrase == "kubernetes"


@pytest.mark.asyncio
async def test_generate_async_skips_exact_matches(monkeypatch):
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    resume = _make_resume()
    matches = [_make_match("python", "exact", "b1")]

    engine = RewriteEngine()
    suggestions = await engine.generate_async(matches, resume)
    assert suggestions == []


@pytest.mark.asyncio
async def test_generate_async_skips_no_evidence(monkeypatch):
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    resume = _make_resume()
    matches = [_make_match("docker", "missing", None)]

    engine = RewriteEngine()
    suggestions = await engine.generate_async(matches, resume)
    assert suggestions == []


@pytest.mark.asyncio
async def test_generate_async_uses_ollama_response(monkeypatch):
    """When Ollama responds, suggestion_text is the model output."""
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    resume = _make_resume()
    matches = [_make_match("kubernetes", "missing", "b1")]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Led cross-functional teams using Kubernetes to deliver projects on time."}
    }

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert "Kubernetes" in suggestions[0].suggestion_text
    assert suggestions[0].original_text == "Led cross-functional teams to deliver projects on time."


# ── HuggingFace provider tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_async_huggingface_success(monkeypatch):
    """HuggingFace provider uses OpenAI-compat endpoint and returns model output."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "test-hf-token")

    resume = _make_resume()
    matches = [_make_match("kubernetes", "missing", "b1")]

    mock_resp = _mock_openai_response(
        "Led cross-functional teams using Kubernetes to deliver projects on time."
    )

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert "Kubernetes" in suggestions[0].suggestion_text
    call_args = mock_client.post.call_args
    assert "/chat/completions" in call_args[0][0]


@pytest.mark.asyncio
async def test_generate_async_huggingface_fallback(monkeypatch):
    """HuggingFace provider falls back to stub hint on error."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "test-hf-token")

    resume = _make_resume()
    matches = [_make_match("docker", "missing", "b1")]

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("503 Service Unavailable")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert suggestions[0].suggestion_text == "Add keyword: docker"


@pytest.mark.asyncio
async def test_generate_async_missing_hf_token_falls_back_to_ollama(monkeypatch):
    """When HF_TOKEN is missing, engine falls back to ollama provider."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    engine = RewriteEngine()
    assert engine._config.name == "ollama"


@pytest.mark.asyncio
async def test_generate_async_sends_auth_header(monkeypatch):
    """Cloud provider sends Authorization: Bearer header."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "my-secret-key")

    resume = _make_resume()
    matches = [_make_match("python", "semantic_weak", "b1")]

    mock_resp = _mock_openai_response("Used Python to lead cross-functional teams.")

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        await engine.generate_async(matches, resume)

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("Authorization") == "Bearer my-secret-key"


@pytest.mark.asyncio
async def test_default_provider_is_huggingface(monkeypatch):
    """Default provider from YAML is huggingface."""
    monkeypatch.delenv("REWRITE_PROVIDER", raising=False)
    monkeypatch.setenv("HF_TOKEN", "test-token")

    engine = RewriteEngine()
    assert engine._config.name == "huggingface"


# ── Thinking mode / strip tests ───────────────────────────────────────────────

def test_strip_thinking_removes_think_blocks():
    raw = '<think>\nLet me think about this...\nThe keyword is kubernetes.\n</think>\nLed teams using Kubernetes to deliver on time.'
    assert _strip_thinking(raw) == "Led teams using Kubernetes to deliver on time."


def test_strip_thinking_handles_no_think_block():
    raw = "Led teams using Kubernetes to deliver on time."
    assert _strip_thinking(raw) == raw


def test_strip_thinking_handles_multiple_blocks():
    raw = '<think>first thought</think>partial <think>second thought</think> result'
    assert _strip_thinking(raw) == "partial result"


@pytest.mark.asyncio
async def test_thinking_false_strips_output(monkeypatch):
    """When thinking=false, <think> blocks are stripped from model output."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("REWRITE_THINKING", "false")

    resume = _make_resume()
    matches = [_make_match("kubernetes", "missing", "b1")]

    raw_output = '<think>\nLet me think...\n</think>\nLed teams using Kubernetes to deliver on time.'
    mock_resp = _mock_openai_response(raw_output)

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert "<think>" not in suggestions[0].suggestion_text
    assert "Kubernetes" in suggestions[0].suggestion_text


@pytest.mark.asyncio
async def test_thinking_true_keeps_output(monkeypatch):
    """When thinking=true, <think> blocks are preserved in model output."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("REWRITE_THINKING", "true")

    resume = _make_resume()
    matches = [_make_match("kubernetes", "missing", "b1")]

    raw_output = '<think>\nReasoning here...\n</think>\nLed teams using Kubernetes.'
    mock_resp = _mock_openai_response(raw_output)

    with patch("ats_matcher.rewrite_engine.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RewriteEngine()
        suggestions = await engine.generate_async(matches, resume)

    assert len(suggestions) == 1
    assert "<think>" in suggestions[0].suggestion_text


@pytest.mark.asyncio
async def test_env_overrides_yaml_model(monkeypatch):
    """HF_MODEL env var overrides the model in YAML config."""
    monkeypatch.setenv("REWRITE_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

    engine = RewriteEngine()
    assert engine._config.model == "meta-llama/Llama-3.1-8B-Instruct"


@pytest.mark.asyncio
async def test_system_prompt_includes_no_think_suffix(monkeypatch):
    """When thinking=false, system prompt includes the no_think_suffix."""
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("REWRITE_THINKING", "false")

    engine = RewriteEngine()
    assert "Do not include any thinking" in engine._config.system_prompt


@pytest.mark.asyncio
async def test_system_prompt_excludes_no_think_suffix_when_thinking(monkeypatch):
    """When thinking=true, system prompt does NOT include the no_think_suffix."""
    monkeypatch.setenv("REWRITE_PROVIDER", "ollama")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("REWRITE_THINKING", "true")

    engine = RewriteEngine()
    assert "Do not include any thinking" not in engine._config.system_prompt
