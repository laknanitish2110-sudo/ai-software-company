"""Semantic text embedding for memory search.

Primary: NVIDIA NV-Embed-QA via API (1024-dim, high quality).
Fallback: local TF-IDF bag-of-words (384-dim, zero API cost).

The module auto-selects: if NVIDIA_API_KEY is set, uses the API;
otherwise falls back to local TF-IDF. Both produce normalized vectors.
"""

import hashlib
import json
import logging
import math
import re
from typing import Optional

import httpx

from app.core.config import NVIDIA_API_KEY, NVIDIA_BASE_URL

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────

LOCAL_DIM = 384
LOCAL_MODEL_NAME = "local-tfidf-384"

NVIDIA_EMBED_MODEL = "nvidia/llama-3.2-nv-embedqa-1b-v2"
NVIDIA_EMBED_DIM = 768
NVIDIA_EMBED_URL = f"{NVIDIA_BASE_URL}/embeddings"

_use_api: Optional[bool] = None
_api_tested: bool = False


def _should_use_api() -> bool:
    global _use_api, _api_tested
    if _use_api is not None:
        return _use_api
    if not NVIDIA_API_KEY:
        _use_api = False
        logger.info("Embeddings: using local TF-IDF (no API key)")
        return False
    if not _api_tested:
        _api_tested = True
        try:
            resp = httpx.post(
                NVIDIA_EMBED_URL,
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
                json={"model": NVIDIA_EMBED_MODEL, "input": ["test"], "input_type": "query", "encoding_format": "float"},
                timeout=10,
            )
            if resp.status_code == 200:
                _use_api = True
                logger.info(f"Embeddings: NVIDIA API verified ({NVIDIA_EMBED_MODEL})")
                return True
            else:
                logger.warning(f"Embeddings: NVIDIA API returned {resp.status_code}, using local fallback")
                _use_api = False
                return False
        except Exception as e:
            logger.warning(f"Embeddings: NVIDIA API unreachable ({e}), using local fallback")
            _use_api = False
            return False
    return _use_api


# ── Public API ────────────────────────────────────────────────────────

EMBEDDING_DIM = LOCAL_DIM
MODEL_NAME = LOCAL_MODEL_NAME


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Uses API if available, local fallback otherwise."""
    if _should_use_api():
        try:
            return _embed_api(text)
        except Exception as e:
            logger.warning(f"API embedding failed, using local fallback: {e}")
            return _embed_local(text)
    return _embed_local(text)


async def embed_text_async(text: str) -> list[float]:
    """Async version of embed_text for use in async contexts."""
    if _should_use_api():
        try:
            return await _embed_api_async(text)
        except Exception as e:
            logger.warning(f"Async API embedding failed, using local fallback: {e}")
            return _embed_local(text)
    return _embed_local(text)


async def embed_batch_async(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed multiple texts in batches. More efficient than calling embed_text_async in a loop."""
    if not texts:
        return []
    if _should_use_api():
        try:
            results = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_results = await _embed_batch_api_async(batch)
                results.extend(batch_results)
            return results
        except Exception as e:
            logger.warning(f"Batch API embedding failed, using local fallback: {e}")
    return [_embed_local(t) for t in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (handles dimension mismatch)."""
    min_len = min(len(a), len(b))
    if min_len == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(min_len))
    mag_a = math.sqrt(sum(x * x for x in a[:min_len]))
    mag_b = math.sqrt(sum(x * x for x in b[:min_len]))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def get_model_info() -> dict:
    """Return current embedding model info (checks API availability on first call)."""
    if _should_use_api():
        return {"model": NVIDIA_EMBED_MODEL, "dim": NVIDIA_EMBED_DIM, "type": "api"}
    return {"model": LOCAL_MODEL_NAME, "dim": LOCAL_DIM, "type": "local"}


def get_current_dim() -> int:
    """Return the embedding dimension of the currently active model."""
    if _should_use_api():
        return NVIDIA_EMBED_DIM
    return LOCAL_DIM


# ── NVIDIA API embedding ─────────────────────────────────────────────

def _embed_api(text: str) -> list[float]:
    """Synchronous API call for embedding."""
    resp = httpx.post(
        NVIDIA_EMBED_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": NVIDIA_EMBED_MODEL,
            "input": [text],
            "input_type": "query",
            "encoding_format": "float",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


async def _embed_api_async(text: str) -> list[float]:
    """Async API call for single text embedding."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            NVIDIA_EMBED_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_EMBED_MODEL,
                "input": [text],
                "input_type": "query",
                "encoding_format": "float",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


async def _embed_batch_api_async(texts: list[str]) -> list[list[float]]:
    """Async API call for batch text embedding."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            NVIDIA_EMBED_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_EMBED_MODEL,
                "input": texts,
                "input_type": "query",
                "encoding_format": "float",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = [None] * len(texts)
        for item in data["data"]:
            embeddings[item["index"]] = item["embedding"]
        return embeddings


# ── Local TF-IDF fallback ────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more",
            "most", "other", "some", "such", "no", "only", "own", "same",
            "than", "too", "very", "just", "because", "about", "this",
            "that", "these", "those", "it", "its", "i", "me", "my",
            "we", "our", "you", "your", "he", "him", "his", "she",
            "her", "they", "them", "their", "what", "which", "who",
            "when", "where", "how", "if", "then", "else"}
    return [t for t in tokens if t not in stop and len(t) > 1]


def _hash_to_index(token: str) -> int:
    h = hashlib.md5(token.encode()).hexdigest()
    return int(h, 16) % LOCAL_DIM


def _hash_sign(token: str) -> int:
    h = hashlib.sha1(token.encode()).hexdigest()
    return 1 if int(h, 16) % 2 == 0 else -1


def _embed_local(text: str) -> list[float]:
    """Local TF-IDF embedding (no API call, zero cost)."""
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * LOCAL_DIM

    vec = [0.0] * LOCAL_DIM
    bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    all_tokens = tokens + bigrams

    for token in all_tokens:
        idx = _hash_to_index(token)
        sign = _hash_sign(token)
        idf = 1.0 + math.log(2.0) if token in bigrams else 1.0
        vec[idx] += sign * idf

    magnitude = math.sqrt(sum(x * x for x in vec))
    if magnitude > 0:
        vec = [x / magnitude for x in vec]
    return vec
