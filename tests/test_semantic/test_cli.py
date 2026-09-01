from src.cli import format_semantic_suggestions
from src.semantic.models import SemanticResult


def test_semantic_output_labels_similarity_separately_from_part_a_score():
    output = format_semantic_suggestions(
        [SemanticResult("A matching sentence", "source.txt", 12, 0.87654)]
    )
    assert "semantic_similarity=0.8765" in output
    assert "score=" not in output
    assert "source.txt:12" in output
