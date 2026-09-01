"""Temporary runnable entry point for Member 3 development.

Run from the project root with:
    python -m src.main

The matching layer lazily loads or builds Member 1's corpus index on the first
query, then reuses it for subsequent queries.
"""

import argparse

try:
    from .cli import run_cli, run_semantic_cli
    from .matching import get_best_k_completions
except ImportError:  # Also supports: python src/main.py
    from cli import run_cli, run_semantic_cli
    from matching import get_best_k_completions


def main() -> None:
    parser = argparse.ArgumentParser(description="Autocomplete and semantic corpus search")
    parser.add_argument(
        "--semantic", action="store_true", help="search by meaning with Gemini Embeddings"
    )
    args = parser.parse_args()
    if args.semantic:
        try:
            from .semantic import get_semantic_results
        except ImportError:
            from semantic import get_semantic_results
        run_semantic_cli(get_semantic_results)
    else:
        run_cli(get_best_k_completions)


if __name__ == "__main__":
    main()
