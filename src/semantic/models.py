"""Data records used by the semantic-search feature."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SemanticRecord:
    sentence_id: int
    original_text: str
    source_path: str
    offset: int
    vector: Tuple[float, ...]


@dataclass(frozen=True)
class SemanticResult:
    completed_sentence: str
    source_text: str
    offset: int
    similarity: float
