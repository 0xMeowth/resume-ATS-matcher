from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import httpx
import yaml

from ats_matcher.models import PhraseMatch, ResumeData, RewriteSuggestion

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are a professional resume editor. "
    "Rewrite the given resume bullet to incorporate the target keyword naturally and concisely. "
    "Keep the same tense, voice, and approximate length. "
    "Return only the rewritten bullet — no explanation, no preamble."
)

_DEFAULT_NO_THINK_SUFFIX = (
    "Do not include any thinking, reasoning, or explanation "
    "— output only the final rewritten bullet."
)

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "rewrite_llm.yaml"


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str | None
    timeout: float
    max_concurrent: int  # 0 = unlimited
    system_prompt: str
    thinking: bool


def _load_yaml() -> dict:
    path = _config_path()
    if not path.exists():
        logger.info("Config %s not found; using defaults.", path)
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _build_system_prompt(cfg: dict, thinking: bool) -> str:
    prompt = cfg.get("system_prompt", _DEFAULT_SYSTEM_PROMPT).strip()
    if not thinking:
        suffix = cfg.get("no_think_suffix", _DEFAULT_NO_THINK_SUFFIX).strip()
        prompt = prompt + " " + suffix
    return prompt


def _build_provider_config() -> ProviderConfig:
    cfg = _load_yaml()

    provider = os.getenv("REWRITE_PROVIDER", cfg.get("provider", "huggingface")).lower()
    thinking_env = os.getenv("REWRITE_THINKING")
    if thinking_env is not None:
        thinking = thinking_env.lower() in ("1", "true", "yes")
    else:
        thinking = cfg.get("thinking", False)

    system_prompt = _build_system_prompt(cfg, thinking)
    providers = cfg.get("providers", {})

    if provider == "huggingface":
        hf = providers.get("huggingface", {})
        api_key_env = hf.get("api_key_env", "HF_TOKEN")
        api_key = os.getenv(api_key_env)
        if not api_key:
            logger.warning("%s not set; falling back to ollama.", api_key_env)
            return _build_ollama_config(providers, system_prompt, thinking)
        return ProviderConfig(
            name="huggingface",
            base_url=os.getenv("HF_BASE_URL", hf.get("base_url", "https://router.huggingface.co/v1")),
            model=os.getenv("HF_MODEL", hf.get("model", "Qwen/Qwen2.5-7B-Instruct")),
            api_key=api_key,
            timeout=float(os.getenv("HF_TIMEOUT", str(hf.get("timeout", 60)))),
            max_concurrent=hf.get("max_concurrent", 0),
            system_prompt=system_prompt,
            thinking=thinking,
        )

    return _build_ollama_config(providers, system_prompt, thinking)


def _build_ollama_config(
    providers: dict | None = None,
    system_prompt: str | None = None,
    thinking: bool = False,
) -> ProviderConfig:
    ollama = (providers or {}).get("ollama", {})
    if system_prompt is None:
        system_prompt = _DEFAULT_SYSTEM_PROMPT
    return ProviderConfig(
        name="ollama",
        base_url=os.getenv("OLLAMA_BASE_URL", ollama.get("base_url", "http://localhost:11434")),
        model=os.getenv("OLLAMA_MODEL", ollama.get("model", "llama3.2")),
        api_key=None,
        timeout=float(os.getenv("OLLAMA_TIMEOUT", str(ollama.get("timeout", 30)))),
        max_concurrent=ollama.get("max_concurrent", 0),
        system_prompt=system_prompt,
        thinking=thinking,
    )


def _strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class RewriteEngine:
    def __init__(self) -> None:
        self._config = _build_provider_config()

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

    async def suggest_single(self, bullet_text: str, phrase: str) -> str:
        """Rewrite a single bullet to incorporate the given keyword."""
        config = self._config
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            if config.name == "ollama":
                return await _ollama_rewrite(client, bullet_text, phrase, config)
            return await _openai_compat_rewrite(client, bullet_text, phrase, config)

    async def generate_async(
        self, matches: List[PhraseMatch], resume: ResumeData
    ) -> List[RewriteSuggestion]:
        """LLM-powered rewrite. Falls back to stub hint on any error."""
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

        config = self._config
        sem = asyncio.Semaphore(config.max_concurrent) if config.max_concurrent > 0 else None

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            if config.name == "ollama":
                coros = [
                    _throttled(_ollama_rewrite(client, bullet.text, match.phrase, config), sem)
                    for match, bullet in candidates
                ]
            else:
                coros = [
                    _throttled(_openai_compat_rewrite(client, bullet.text, match.phrase, config), sem)
                    for match, bullet in candidates
                ]
            rewrites = await asyncio.gather(*coros)

        return [
            RewriteSuggestion(
                bullet_id=bullet.bullet_id,
                phrase=match.phrase,
                original_text=bullet.text,
                suggestion_text=rewritten,
            )
            for (match, bullet), rewritten in zip(candidates, rewrites)
        ]


async def _throttled(coro, sem: asyncio.Semaphore | None):
    if sem:
        async with sem:
            return await coro
    return await coro


def _build_user_msg(original_text: str, phrase: str) -> str:
    return (
        f'Bullet: "{original_text}"\n'
        f'Keyword to incorporate: "{phrase}"\n'
        "Rewritten bullet:"
    )


def _postprocess(text: str, config: ProviderConfig) -> str:
    text = text.strip()
    if not config.thinking:
        text = _strip_thinking(text)
    return text


async def _ollama_rewrite(
    client: httpx.AsyncClient,
    original_text: str,
    phrase: str,
    config: ProviderConfig,
) -> str:
    """POST to Ollama /api/chat. Returns stub hint on any error."""
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": _build_user_msg(original_text, phrase)},
        ],
        "stream": False,
    }
    try:
        resp = await client.post(f"{config.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        return _postprocess(resp.json()["message"]["content"], config)
    except Exception as exc:
        logger.warning("Ollama rewrite failed (%s); using stub hint.", exc)
        return f"Add keyword: {phrase}"


async def _openai_compat_rewrite(
    client: httpx.AsyncClient,
    original_text: str,
    phrase: str,
    config: ProviderConfig,
) -> str:
    """POST to OpenAI-compatible /chat/completions. Returns stub hint on any error."""
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": _build_user_msg(original_text, phrase)},
        ],
    }
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        resp = await client.post(
            f"{config.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return _postprocess(resp.json()["choices"][0]["message"]["content"], config)
    except Exception as exc:
        logger.warning("%s rewrite failed (%s); using stub hint.", config.name, exc)
        return f"Add keyword: {phrase}"
