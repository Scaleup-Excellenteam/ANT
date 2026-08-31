"""Temporary runnable entry point for Member 3 development.

Run from the project root with:
    python -m src.main

The matching layer lazily loads or builds Member 1's corpus index on the first
query, then reuses it for subsequent queries.
"""

try:
    from .cli import run_cli
    from .matching import get_best_k_completions
except ImportError:  # Also supports: python src/main.py
    from cli import run_cli
    from matching import get_best_k_completions


def main() -> None:
    run_cli(get_best_k_completions)


if __name__ == "__main__":
    main()
