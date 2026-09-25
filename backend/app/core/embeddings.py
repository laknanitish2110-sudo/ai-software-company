"""Lightweight text embedding for semantic memory search.

Uses a simple TF-IDF-like bag-of-words approach that runs locally with zero
external dependencies. This avoids burning LLM API credits on embeddings
while still providing meaningful semantic similarity for memory retrieval.

The vector dimension is fixed at 384 (hash-projected from vocabulary).
"""

import hashlib
import math
import re

EMBEDDING_DIM = 384
MODEL_NAME = "local-tfidf-384"


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
    return int(h, 16) % EMBEDDING_DIM


def _hash_sign(token: str) -> int:
    h = hashlib.sha1(token.encode()).hexdigest()
    return 1 if int(h, 16) % 2 == 0 else -1


def embed_text(text: str) -> list[float]:
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * EMBEDDING_DIM

    vec = [0.0] * EMBEDDING_DIM
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


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
