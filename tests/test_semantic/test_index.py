import pickle

import pytest

from src.init_offline import CorpusIndex, SentenceRecord
from src.semantic.embeddings import EmbeddingServiceError
from src.semantic.index import SemanticIndex

from .conftest import FakeEmbedder


def make_corpus():
    corpus = CorpusIndex()
    corpus.sentences = [
        SentenceRecord(0, "The car needs fuel.", "the car needs fuel", "cars.txt", 8),
        SentenceRecord(1, "Bake bread in the oven.", "bake bread in the oven", "food.txt", 3),
        SentenceRecord(2, "A vehicle requires gasoline.", "a vehicle requires gasoline", "cars.txt", 15),
    ]
    return corpus


def test_paraphrased_query_returns_semantically_related_sentence_and_real_source():
    vectors = {
        "The car needs fuel.": [1.0, 0.0],
        "Bake bread in the oven.": [0.0, 1.0],
        "A vehicle requires gasoline.": [0.95, 0.05],
        "automobile running out of gas": [1.0, 0.0],
    }
    embedder = FakeEmbedder(vectors)
    index = SemanticIndex.build(make_corpus(), embedder, batch_size=2)

    results = index.search("automobile running out of gas", embedder, k=2)

    assert [result.source_text for result in results] == ["cars.txt", "cars.txt"]
    assert [result.offset for result in results] == [8, 15]
    assert results[0].similarity > results[1].similarity


def test_build_batches_documents_and_honors_limit():
    corpus = make_corpus()
    vectors = {record.original_text: [1.0, 0.0] for record in corpus.sentences}
    embedder = FakeEmbedder(vectors)

    index = SemanticIndex.build(corpus, embedder, batch_size=1, limit=2)

    assert len(index.records) == 2
    assert embedder.document_calls == [
        ["The car needs fuel."],
        ["Bake bread in the oven."],
    ]


def test_empty_query_does_not_call_provider():
    embedder = FakeEmbedder({})
    assert SemanticIndex().search("   ", embedder) == []
    assert embedder.query_calls == []


def test_zero_vector_is_rejected():
    corpus = make_corpus()
    embedder = FakeEmbedder({record.original_text: [0.0, 0.0] for record in corpus.sentences})
    with pytest.raises(EmbeddingServiceError, match="zero vector"):
        SemanticIndex.build(corpus, embedder)


def test_dimension_mismatch_requests_rebuild():
    corpus = make_corpus()
    vectors = {record.original_text: [1.0, 0.0] for record in corpus.sentences}
    vectors["query"] = [1.0, 0.0, 0.0]
    embedder = FakeEmbedder(vectors)
    index = SemanticIndex.build(corpus, embedder)
    with pytest.raises(EmbeddingServiceError, match="Rebuild"):
        index.search("query", embedder)


def test_index_round_trip(tmp_path):
    corpus = make_corpus()
    vectors = {record.original_text: [1.0, 0.0] for record in corpus.sentences}
    index = SemanticIndex.build(corpus, FakeEmbedder(vectors))
    path = tmp_path / "semantic.pickle"

    index.save(path)
    loaded = SemanticIndex.load(path)

    assert loaded.records == index.records


def test_unknown_index_version_is_rejected(tmp_path):
    path = tmp_path / "semantic.pickle"
    with path.open("wb") as output:
        pickle.dump({"version": 999, "records": []}, output)
    with pytest.raises(ValueError, match="Unsupported"):
        SemanticIndex.load(path)
