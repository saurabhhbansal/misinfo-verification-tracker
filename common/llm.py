"""Thin wrapper around the Groq chat API returning parsed JSON.

If GROQ_API_KEY is not set, `available()` is False and callers use their
non-LLM fallback path.
"""
from __future__ import annotations

import json
import logging
import re
import time

from common import config

log = logging.getLogger(__name__)
_client = None


def available() -> bool:
    return bool(config.GROQ_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _parse_json(text: str):
    text = text.strip()
    # tolerate ```json fences or text around the object
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    return json.loads(m.group(0) if m else text)


def chat_json(system: str, user: str, *, temperature: float = 0.1, retries: int = 3, max_tokens: int = 2048):
    """Send a prompt, return the parsed JSON object. Raises RuntimeError on failure."""
    if not available():
        raise RuntimeError("GROQ_API_KEY not configured")
    client = _get_client()
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return _parse_json(resp.choices[0].message.content)
        except Exception as e:  # rate limits (429), bad JSON, network
            last_err = e
            wait = 2 ** attempt * 3
            log.warning("LLM call failed (%s); retry in %ss", e, wait)
            time.sleep(wait)
    raise RuntimeError(f"LLM call failed: {last_err}")
