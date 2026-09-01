"""Local Flask web UI for the autocomplete application.

Run from the project root with:
    python -m src.ui.web_app
"""

from __future__ import annotations

import time
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from flask import Flask, jsonify, render_template, request

# The persisted corpus index is built by the existing offline code with top-level
# module names under src/. Match that import style for normal local launches.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from auto_complete_data import AutoCompleteData
from cli import BEST_MATCHES, EMPTY_INPUT, prepare_results
from contextual import ContextualCompletionError, ContextualResult
from contextual import GeminiSuggestionClient
from enhanced_cli import DEFAULT_CONTEXT
from matching import get_best_k_completions

ENGLISH_MODE = "english"
GEMINI_MODE = "gemini"
VALID_MODES = {ENGLISH_MODE, GEMINI_MODE}

CorpusSearch = Callable[[str], List[AutoCompleteData]]


class ContextualGenerator(Protocol):
    def generate(self, prefix: str, context: str, count: int = 5) -> ContextualResult:
        ...


def create_app(
    corpus_search: CorpusSearch = get_best_k_completions,
    contextual_generator: Optional[ContextualGenerator] = None,
) -> Flask:
    """Create the Flask app with injectable services for tests."""
    app = Flask(__name__)
    generator = contextual_generator if contextual_generator is not None else GeminiSuggestionClient()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/search")
    def api_search():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be JSON."}), 400

        query = str(payload.get("query", "")).strip()
        mode = str(payload.get("mode", ENGLISH_MODE)).strip().lower()
        context = str(payload.get("context", DEFAULT_CONTEXT)).strip() or DEFAULT_CONTEXT

        if not query:
            return jsonify({"error": EMPTY_INPUT}), 400
        if mode not in VALID_MODES:
            return jsonify({"error": "Invalid mode. Use english or gemini."}), 400

        try:
            response, status = run_search_request(
                query=query,
                mode=mode,
                corpus_search=corpus_search,
                contextual_generator=generator,
                context=context,
            )
        except Exception as exc:
            return jsonify({"error": f"Unexpected search error: {exc}"}), 500
        return jsonify(response), status

    return app


def run_search_request(
    query: str,
    mode: str,
    corpus_search: CorpusSearch,
    contextual_generator: ContextualGenerator,
    context: str = DEFAULT_CONTEXT,
) -> Tuple[Dict[str, object], int]:
    """Run one API search request and return a JSON-ready response."""
    started = time.perf_counter()

    if mode == ENGLISH_MODE:
        results = prepare_results(corpus_search(query))
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return (
            {
                "mode": ENGLISH_MODE,
                "query": query,
                "elapsed_ms": elapsed_ms,
                "count": len(results),
                "results": [
                    {
                        "sentence": item.completed_sentence,
                        "score": item.score,
                        "source": item.source_text,
                        "offset": item.offset,
                    }
                    for item in results
                ],
            },
            200,
        )

    try:
        gemini_result = contextual_generator.generate(query, context, BEST_MATCHES)
    except (ContextualCompletionError, ValueError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return (
            {
                "mode": GEMINI_MODE,
                "query": query,
                "elapsed_ms": elapsed_ms,
                "results": [],
                "error": str(exc),
            },
            503,
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return (
        {
            "mode": GEMINI_MODE,
            "query": query,
            "elapsed_ms": elapsed_ms,
            "gemini_ms": gemini_result.latency_ms,
            "model": gemini_result.model,
            "count": len(gemini_result.suggestions),
            "results": [
                {
                    "text": suggestion.text,
                    "ai_generated": True,
                }
                for suggestion in gemini_result.suggestions
            ],
        },
        200,
    )


def main() -> None:
    app = create_app()
    print("Running on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
