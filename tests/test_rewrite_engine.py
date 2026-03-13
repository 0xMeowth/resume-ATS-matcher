"""Tests for RewriteEngine.generate_async().

These tests run without a live Ollama instance. The fallback path is tested by
mocking httpx to raise a connection error, which causes _ollama_rewrite() to
return the stub hint.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ats_matcher.models import Bullet, PhraseMatch, ResumeData, Section, Role
from ats_matcher.rewrite_engine import RewriteEngine, _ollama_rewrite


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


# ── generate_async: fallback when Ollama is unreachable ───────────────────────

@pytest.mark.asyncio
async def test_generate_async_fallback_on_connection_error():
    """When Ollama is down, suggestion_text falls back to 'Add keyword: X'."""
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
async def test_generate_async_skips_exact_matches():
    resume = _make_resume()
    matches = [_make_match("python", "exact", "b1")]

    engine = RewriteEngine()
    # No HTTP call should be made — exact matches are skipped regardless.
    suggestions = await engine.generate_async(matches, resume)
    assert suggestions == []


@pytest.mark.asyncio
async def test_generate_async_skips_no_evidence():
    resume = _make_resume()
    matches = [_make_match("docker", "missing", None)]

    engine = RewriteEngine()
    suggestions = await engine.generate_async(matches, resume)
    assert suggestions == []


@pytest.mark.asyncio
async def test_generate_async_uses_ollama_response():
    """When Ollama responds, suggestion_text is the model output."""
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
