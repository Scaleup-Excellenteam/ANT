"""Runnable entry point for the integrated Parts A and B application.

Run from the project root with:
    python -m src.main

The matching layer lazily loads or builds Member 1's corpus index on the first
query, then reuses it for subsequent queries.
"""

try:
    from .contextual import GeminiSuggestionClient
    from .enhanced_cli import run_feature_cli
    from .matching import get_best_k_completions
    from .translation import GoogleTranslationService
except ImportError:  # Also supports: python src/main.py
    from contextual import GeminiSuggestionClient
    from enhanced_cli import run_feature_cli
    from matching import get_best_k_completions
    from translation import GoogleTranslationService


def main() -> None:
    run_feature_cli(
        corpus_search=get_best_k_completions,
        contextual_generator=GeminiSuggestionClient(),
        translation_service=GoogleTranslationService(),
    )


if __name__ == "__main__":
    main()
