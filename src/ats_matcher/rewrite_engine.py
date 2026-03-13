from __future__ import annotations

import asyncio
import logging
import os
from typing import List

import httpx

from ats_matcher.models import PhraseMatch, ResumeData, RewriteSuggestion

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
_OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))

_SYSTEM_PROMPT = (
    "You are a professional resume editor. "
    "Rewrite the given resume bullet to incorporate the target keyword naturally and concisely. "
    "Keep the same tense, voice, and approximate length. "
    "Return only the rewritten bullet — no explanation, no preamble."
)


class RewriteEngine:
    def __init__(self) -> None:
        pass

    def generate(
        self, matches: List[PhraseMatch], resume: ResumeData
    ) -> List[RewriteSuggestion]:
        """Synchronous stub — returns 'Add keyword: X' hints."""
        suggestions: List[RewriteSuggestion] = []
        for match in matches:
            if match.match_type == "exact":
                continue
            if not match.evidence_bullet_id:
                continue
            bullet = resume.bullet_index.get(match.evidence_bullet_id)
            if not bullet:
                continue
            suggestions.append(
                RewriteSuggestion(
                    bullet_id=bullet.bullet_id,
                    phrase=match.phrase,
                    original_text=bullet.text,
                    suggestion_text=f"Add keyword: {match.phrase}",
                )
            )
        return suggestions

    async def generate_async(
        self, matches: List[PhraseMatch], resume: ResumeData
    ) -> List[RewriteSuggestion]:
        """Async Ollama-powered rewrite. Falls back to stub hint on any error."""
        candidates = []
        for match in matches:
            if match.match_type == "exact":
                continue
            if not match.evidence_bullet_id:
                continue
            bullet = resume.bullet_index.get(match.evidence_bullet_id)
            if bullet:
                candidates.append((match, bullet))

        if not candidates:
            return []

        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            rewrites = await asyncio.gather(
                *[
                    _ollama_rewrite(client, bullet.text, match.phrase)
                    for match, bullet in candidates
                ]
            )

        return [
            RewriteSuggestion(
                bullet_id=bullet.bullet_id,
                phrase=match.phrase,
                original_text=bullet.text,
                suggestion_text=rewritten,
            )
            for (match, bullet), rewritten in zip(candidates, rewrites)
        ]


async def _ollama_rewrite(
    client: httpx.AsyncClient,
    original_text: str,
    phrase: str,
) -> str:
    """POST to Ollama /api/chat. Returns stub hint on any error."""
    user_msg = (
        f'Bullet: "{original_text}"\n'
        f'Keyword to incorporate: "{phrase}"\n'
        "Rewritten bullet:"
    )
    payload = {
        "model": _OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
    }
    try:
        resp = await client.post(f"{_OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning("Ollama rewrite failed (%s); using stub hint.", exc)
        return f"Add keyword: {phrase}"
