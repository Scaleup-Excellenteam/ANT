"""Command-line builder for the persistent Gemini semantic index."""

import argparse

from ..init_offline import load_or_build_index
from .embeddings import EmbeddingServiceError, GeminiEmbedder
from .index import SemanticIndex
from .service import DEFAULT_SEMANTIC_INDEX_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Gemini semantic index")
    parser.add_argument("--limit", type=int, help="Embed only the first N corpus sentences")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--output", default=str(DEFAULT_SEMANTIC_INDEX_PATH))
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    corpus = load_or_build_index()
    try:
        semantic_index = SemanticIndex.build(
            corpus,
            GeminiEmbedder(),
            batch_size=args.batch_size,
            limit=args.limit,
        )
    except EmbeddingServiceError as exc:
        parser.exit(1, f"Semantic index build failed: {exc}\n")
    from pathlib import Path

    output = Path(args.output)
    semantic_index.save(output)
    print(f"Saved {len(semantic_index.records)} semantic records to {output}")


if __name__ == "__main__":
    main()
