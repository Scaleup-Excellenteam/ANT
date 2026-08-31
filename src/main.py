"""Temporary runnable entry point for Member 3 development.

Run from the project root with:
    python -m src.main

When the partners finish:
1. connect Member 1's offline/init loading before the CLI starts;
2. replace the mock matching import with Member 2's real
   get_best_k_completions function.
"""

try:
    from .cli import run_cli
    from .mock_matching import get_best_k_completions
except ImportError:  # Also supports: python src/main.py
    from cli import run_cli
    from mock_matching import get_best_k_completions


def main() -> None:
    # TODO(Member 1 integration): initialize/load the real corpus structure here.

    # TODO(Member 2 integration): replace mock get_best_k_completions import
    # with the real implementation once Yazan hands it off.
    run_cli(get_best_k_completions)


if __name__ == "__main__":
    main()
