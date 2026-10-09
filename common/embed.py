"""Shared multilingual sentence embedder (Hindi + English), loaded lazily once.

Uses plain `transformers` + mean pooling (the documented usage for intfloat/multilingual-e5 models).
"""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np

from common import config


_model_lock = threading.Lock()
_load_lock = threading.Lock()


def _model():
    # transformers' lazy imports are not thread-safe on first use, so the first load is serialised
    with _load_lock:
        return _load()


@lru_cache(maxsize=1)
def _load():
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(config.EMBED_MODEL)
    model = AutoModel.from_pretrained(config.EMBED_MODEL).eval()
    return tok, model


_cache: dict[str, np.ndarray] = {}
_cache_lock = threading.Lock()
CACHE_MAX = 20000


def encode(texts: list[str], kind: str = "passage", batch_size: int = 16) -> np.ndarray:
    """Return L2-normalised embeddings (cached per text). e5 models expect 'query: ' / 'passage: ' prefixes."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    prefix = ("query: " if kind == "query" else "passage: ") if "e5" in config.EMBED_MODEL else ""
    keys = [prefix + t for t in texts]
    with _cache_lock:
        todo = list(dict.fromkeys(k for k in keys if k not in _cache))
    if todo:
        vecs = _encode_raw(todo, batch_size)
        with _cache_lock:
            if len(_cache) > CACHE_MAX:
                _cache.clear()
            _cache.update(zip(todo, vecs))
    with _cache_lock:
        return np.vstack([_cache[k] for k in keys])


def _encode_raw(texts: list[str], batch_size: int) -> np.ndarray:
    import torch
    tok, model = _model()
    out = []
    # inference_mode per call: grad mode is thread-local and claims are verified in parallel threads
    with _model_lock, torch.inference_mode():
        for i in range(0, len(texts), batch_size):
            batch = tok(texts[i:i + batch_size], padding=True, truncation=True, max_length=256, return_tensors="pt")
            hidden = model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).float()
            emb = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            out.append(torch.nn.functional.normalize(emb, dim=-1).numpy())
    return np.vstack(out)


def similarity(queries: list[str], passages: list[str]) -> np.ndarray:
    """Cosine similarity matrix [len(queries), len(passages)]."""
    if not queries or not passages:
        return np.zeros((len(queries), len(passages)))
    return encode(queries, "query") @ encode(passages, "passage").T
