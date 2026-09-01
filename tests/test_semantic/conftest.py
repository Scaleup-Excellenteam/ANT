from typing import Dict, List, Sequence


class FakeEmbedder:
    def __init__(self, vectors: Dict[str, List[float]]) -> None:
        self.vectors = vectors
        self.document_calls = []
        self.query_calls = []

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        self.document_calls.append(list(texts))
        return [self.vectors[text] for text in texts]

    def embed_query(self, text: str) -> List[float]:
        self.query_calls.append(text)
        return self.vectors[text]
