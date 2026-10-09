"""Shared multilingual sentence embedder (Hindi + English), loaded lazily once.

Uses plain `transformers` + mean pooling (the documented usage for intfloat/multilingual-e5 models).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from common import config


@lru_cache(maxsize=1)
def _model():
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(config.EMBED_MODEL)
    model = AutoModel.from_pretrained(config.EMBED_MODEL).eval()
    torch.set_grad_enabled(False)
    return tok, model


def encode(texts: list[str], kind: str = "passage", batch_size: int = 16) -> np.ndarray:
    """Return L2-normalised embeddings. e5 models expect 'query: ' / 'passage: ' prefixes."""
    import torch
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    prefix = ("query: " if kind == "query" else "passage: ") if "e5" in config.EMBED_MODEL else ""
    tok, model = _model()
    out = []
    for i in range(0, len(texts), batch_size):
        batch = tok([prefix + t for t in texts[i:i + batch_size]], padding=True, truncation=True,
                    max_length=256, return_tensors="pt")
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
