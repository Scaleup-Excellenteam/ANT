"""Persistent vector index and dependency-injected semantic retrieval."""

import math
import pickle
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from ..init_offline import CorpusIndex
from .embeddings import EmbeddingProvider, EmbeddingServiceError
from .models import SemanticRecord, SemanticResult

INDEX_FORMAT_VERSION = 1


def _unit_vector(values: Sequence[float]) -> Tuple[float, ...]:
    magnitude = math.sqrt(sum(float(value) ** 2 for value in values))
    if magnitude == 0:
        raise EmbeddingServiceError("The embedding service returned a zero vector.")
    return tuple(float(value) / magnitude for value in values)


class SemanticIndex:
    def __init__(self, records: Optional[Iterable[SemanticRecord]] = None) -> None:
        self.records = list(records or [])

    @classmethod
    def build(
        cls,
        corpus: CorpusIndex,
        embedder: EmbeddingProvider,
        batch_size: int = 50,
        limit: Optional[int] = None,
    ) -> "SemanticIndex":
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        sentences = corpus.sentences[:limit] if limit is not None else corpus.sentences
        records: List[SemanticRecord] = []
        for start in range(0, len(sentences), batch_size):
            batch = sentences[start : start + batch_size]
            vectors = embedder.embed_documents([item.original_text for item in batch])
            if len(vectors) != len(batch):
                raise EmbeddingServiceError("Embedding count does not match corpus batch.")
            for sentence, vector in zip(batch, vectors):
                records.append(
                    SemanticRecord(
                        sentence_id=sentence.sentence_id,
                        original_text=sentence.original_text,
                        source_path=sentence.source_path,
                        offset=sentence.offset,
                        vector=_unit_vector(vector),
                    )
                )
        return cls(records)

    def search(
        self, query: str, embedder: EmbeddingProvider, k: int = 5
    ) -> List[SemanticResult]:
        if not query.strip() or k < 1:
            return []
        if not self.records:
            return []
        query_vector = _unit_vector(embedder.embed_query(query))
        expected_dimension = len(self.records[0].vector)
        if len(query_vector) != expected_dimension:
            raise EmbeddingServiceError(
                "Query and corpus embeddings have different dimensions. Rebuild the index."
            )
        scored = []
        for record in self.records:
            if len(record.vector) != expected_dimension:
                raise EmbeddingServiceError("The semantic index contains invalid vectors.")
            similarity = sum(a * b for a, b in zip(query_vector, record.vector))
            scored.append((similarity, record))
        scored.sort(key=lambda item: (-item[0], item[1].original_text.lower()))
        return [
            SemanticResult(
                completed_sentence=record.original_text,
                source_text=record.source_path,
                offset=record.offset,
                similarity=similarity,
            )
            for similarity, record in scored[:k]
        ]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            pickle.dump(
                {"version": INDEX_FORMAT_VERSION, "records": self.records},
                output,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    @classmethod
    def load(cls, path: Path) -> "SemanticIndex":
        with path.open("rb") as source:
            payload = pickle.load(source)
        if not isinstance(payload, dict) or payload.get("version") != INDEX_FORMAT_VERSION:
            raise ValueError("Unsupported semantic index format. Rebuild the index.")
        return cls(payload.get("records", []))
