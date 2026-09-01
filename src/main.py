"""Temporary runnable entry point for Member 3 development.

Run from the project root with:
    python -m src.main

The matching layer lazily loads or builds Member 1's corpus index on the first
query, then reuses it for subsequent queries.
"""

import logging

try:
    from .cli import run_cli
    from .logging_config import configure_logging
    from .matching import get_best_k_completions
except ImportError:  # Also supports: python src/main.py
    from cli import run_cli
    from logging_config import configure_logging
    from matching import get_best_k_completions

logger = logging.getLogger("application")


def main() -> None:
    log_path = configure_logging()
    logger.info("Application startup; log_file=%s", log_path)
    try:
        run_cli(get_best_k_completions)
    except Exception:
        logger.exception("Unexpected application failure")
        raise
    finally:
        logger.info("Application shutdown")


if __name__ == "__main__":
    main()
