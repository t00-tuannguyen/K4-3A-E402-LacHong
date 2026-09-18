"""Hybrid retrieval over the official announcement archive.

The retriever is deliberately local and deterministic for the CP3 demo:

* BM25 operates on Vietnamese text after lower-casing and removing accents.
* The embedding leg uses a stable feature-hashed vector of tokens and
  token-bigrams.  It requires no model download and remains available when the
  LLM quota is exhausted.

Routing vocabulary lives in each announcement's ``retrieval_terms`` field, so
adding a new announcement does not require a Python code change.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Iterable

from codebase.core_ai.normalization import TextNormalizer, fold_text


TOKEN_RE = re.compile(r"[a-z0-9]+(?:[/_-][a-z0-9]+)*")
STOPWORDS = {
    "a", "anh", "ban", "bot", "cai", "cho", "co", "cua", "em", "gi", "ha",
    "hoi", "la", "minh", "mot", "nay", "nhe", "nhi", "oi", "the", "thi",
    "toi", "tro", "ly", "va", "vay", "voi",
}


def tokenize(value: str, *, normalizer: TextNormalizer | None = None) -> list[str]:
    normalized = normalizer.normalize(value) if normalizer else fold_text(value)
    return [token for token in TOKEN_RE.findall(normalized) if token not in STOPWORDS]


def _source_document(source: dict[str, Any]) -> str:
    """Index official text plus the announcement's declared search metadata.

    Metadata is intentionally read generically: a new announcement can add
    ``subject_terms``, field availability or routing terms without requiring a
    retriever code change.  The metadata narrows retrieval only; the answer is
    still composed from the original official content/field response.
    """

    def flatten(value: Any) -> list[str]:
        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                parts.append(str(key))
                parts.extend(flatten(item))
            return parts
        if isinstance(value, list):
            return [part for item in value for part in flatten(item)]
        return [str(value)] if value not in (None, "") else []

    metadata = (
        source.get("key_entities", {}),
        source.get("retrieval_terms", []),
        source.get("subject_terms", []),
        source.get("claim_coverage", []),
        source.get("field_availability", {}),
        source.get("default_route", {}),
        source.get("routing_rules", []),
    )
    return " ".join(
        str(part)
        for part in (
            source.get("title", ""),
            source.get("content", ""),
            source.get("source_channel", ""),
            source.get("author", ""),
            *(" ".join(flatten(item)) for item in metadata),
        )
        if part
    )


def _embedding_features(value: str, *, normalizer: TextNormalizer | None = None) -> Iterable[tuple[str, float]]:
    tokens = tokenize(value, normalizer=normalizer)
    for token in tokens:
        yield f"token:{token}", 1.0
        if len(token) >= 5:
            for index in range(len(token) - 2):
                yield f"tri:{token[index:index + 3]}", 0.18
    for left, right in zip(tokens, tokens[1:]):
        yield f"bigram:{left}_{right}", 0.65


def hashed_embedding(
    value: str,
    dimensions: int = 384,
    *,
    normalizer: TextNormalizer | None = None,
) -> tuple[float, ...]:
    """Build a stable, normalized local embedding without external downloads."""
    vector = [0.0] * dimensions
    for feature, weight in _embedding_features(value, normalizer=normalizer):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return tuple(vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


@dataclass(frozen=True)
class RetrievalResult:
    source: dict[str, Any]
    score: float
    bm25_score: float
    embedding_score: float

    @property
    def source_id(self) -> str:
        return str(self.source["id"])

    def prompt_record(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "title": self.source["title"],
            "content": self.source["content"],
            "key_entities": self.source.get("key_entities", {}),
            "field_availability": self.source.get("field_availability", {}),
            "retrieval_score": round(self.score, 4),
        }


class HybridRetriever:
    """Small-corpus BM25 + local-embedding retriever."""

    def __init__(
        self,
        sources: list[dict[str, Any]],
        *,
        bm25_weight: float = 0.65,
        embedding_weight: float = 0.35,
        k1: float = 1.5,
        b: float = 0.75,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.sources = sources
        self.bm25_weight = bm25_weight
        self.embedding_weight = embedding_weight
        self.k1 = k1
        self.b = b
        self.normalizer = normalizer
        self.documents = [_source_document(source) for source in sources]
        self.tokenized_documents = [tokenize(document, normalizer=self.normalizer) for document in self.documents]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokenized_documents]
        self.document_lengths = [len(tokens) for tokens in self.tokenized_documents]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths)
            if self.document_lengths else 0.0
        )
        self.document_frequency = Counter(
            token
            for document in self.tokenized_documents
            for token in set(document)
        )
        self.document_embeddings = [hashed_embedding(document, normalizer=self.normalizer) for document in self.documents]

    def _bm25(self, query_tokens: list[str], index: int) -> float:
        if not query_tokens or not self.sources:
            return 0.0
        frequencies = self.term_frequencies[index]
        document_length = self.document_lengths[index]
        score = 0.0
        for token in set(query_tokens):
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            document_frequency = self.document_frequency.get(token, 0)
            inverse_frequency = math.log(
                1 + (len(self.sources) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            length_normalization = 1 - self.b
            if self.average_document_length:
                length_normalization += self.b * document_length / self.average_document_length
            score += inverse_frequency * (
                frequency * (self.k1 + 1)
                / (frequency + self.k1 * length_normalization)
            )
        return score

    def search(self, query: str, *, top_k: int = 3) -> list[RetrievalResult]:
        query_tokens = tokenize(query, normalizer=self.normalizer)
        query_embedding = hashed_embedding(query, normalizer=self.normalizer)
        raw_bm25 = [self._bm25(query_tokens, index) for index in range(len(self.sources))]
        max_bm25 = max(raw_bm25, default=0.0)
        normalized_bm25 = [score / max_bm25 if max_bm25 else 0.0 for score in raw_bm25]
        embedding_scores = [
            max(0.0, cosine_similarity(query_embedding, embedding))
            for embedding in self.document_embeddings
        ]
        results = [
            RetrievalResult(
                source=source,
                score=(
                    self.bm25_weight * normalized_bm25[index]
                    + self.embedding_weight * embedding_scores[index]
                ),
                bm25_score=normalized_bm25[index],
                embedding_score=embedding_scores[index],
            )
            for index, source in enumerate(self.sources)
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:max(1, top_k)]
