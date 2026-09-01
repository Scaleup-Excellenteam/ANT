"""Local Flask UI for autocomplete and simulated satellite resilience.

Run from the repository root with::

    python -m src.ui.web_app
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from flask import Flask, jsonify, render_template, request

from ..auto_complete_data import AutoCompleteData
from ..cli import BEST_MATCHES, EMPTY_INPUT, prepare_results
from ..contextual import ContextualCompletionError, ContextualResult, GeminiSuggestionClient
from ..enhanced_cli import DEFAULT_CONTEXT
from ..matching import get_best_k_completions
from ..satellite import (
    DataUnavailableError,
    SatelliteResilienceService,
    SatelliteState,
    build_shared_satellite_service,
)
from ..translation import GoogleTranslationService, TranslationError, TranslationService

CORPUS_MODE = "corpus"
AI_MODE = "ai"
TRANSLATION_MODE = "translation"
VALID_MODES = {CORPUS_MODE, AI_MODE, TRANSLATION_MODE}

CorpusSearch = Callable[[str], List[AutoCompleteData]]


class ContextualGenerator(Protocol):
    def generate(self, prefix: str, context: str, count: int = 5) -> ContextualResult:
        ...


def create_app(
    corpus_search: CorpusSearch = get_best_k_completions,
    contextual_generator: Optional[ContextualGenerator] = None,
    translation_service: Optional[TranslationService] = None,
    satellite_service: Optional[SatelliteResilienceService] = None,
) -> Flask:
    """Application factory with injectable boundaries for deterministic tests."""
    app = Flask(__name__)
    generator = contextual_generator or GeminiSuggestionClient()
    translator = translation_service or GoogleTranslationService()
    satellite = satellite_service or build_shared_satellite_service()
    app.extensions["satellite_resilience"] = satellite

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/search")
    def api_search():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be JSON."}), 400
        query = str(payload.get("query", "")).strip()
        mode = str(payload.get("mode", CORPUS_MODE)).strip().lower()
        context = str(payload.get("context", DEFAULT_CONTEXT)).strip() or DEFAULT_CONTEXT
        if not query:
            return jsonify({"error": EMPTY_INPUT}), 400
        if mode not in VALID_MODES:
            return jsonify({"error": "Invalid mode. Use corpus, ai, or translation."}), 400
        response, status_code = run_search_request(
            query, mode, corpus_search, generator, translator, context
        )
        return jsonify(response), status_code

    @app.get("/api/satellite/status")
    def satellite_status():
        return jsonify(satellite.status())

    @app.post("/api/satellite/health")
    def satellite_health():
        satellite.check_health()
        return jsonify(satellite.status())

    @app.post("/api/satellite/simulate-disconnect")
    def satellite_disconnect():
        try:
            satellite.simulate_disconnect()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(satellite.status())

    @app.post("/api/satellite/reconnect")
    def satellite_reconnect():
        state = satellite.reconnect()
        status_code = 200 if state == SatelliteState.ONLINE else 503
        return jsonify(satellite.status()), status_code

    @app.post("/api/satellite/simulate-latency")
    def satellite_latency():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be JSON."}), 400
        try:
            latency_ms = int(payload.get("latency_ms"))
            if latency_ms < 0 or latency_ms > 30000:
                raise ValueError
            satellite.set_simulated_latency(latency_ms)
        except (TypeError, ValueError):
            return jsonify({"error": "latency_ms must be between 0 and 30000."}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(satellite.status())

    @app.get("/api/satellite/pending")
    def satellite_pending():
        operations = [item.to_dict() for item in satellite.pending_operations()]
        return jsonify({"count": len(operations), "operations": operations})

    @app.get("/api/satellite/cache")
    def satellite_cache():
        records = [item.to_dict() for item in satellite.cached_values()]
        return jsonify({"count": len(records), "records": records})

    @app.get("/api/satellite/data/<path:key>")
    def satellite_read(key: str):
        try:
            result = satellite.read(key)
        except DataUnavailableError as exc:
            return jsonify({"error": str(exc), "satellite": satellite.status()}), 503
        return jsonify({"result": result.to_dict(), "satellite": satellite.status()})

    @app.post("/api/satellite/data")
    def satellite_write():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be JSON."}), 400
        key = str(payload.get("key", "")).strip()
        if not key or "value" not in payload:
            return jsonify({"error": "A non-empty key and value are required."}), 400
        try:
            result = satellite.write(
                "upsert",
                {"key": key, "value": payload["value"]},
                operation_id=payload.get("operation_id"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        status_code = 202 if result.queued else 200
        return jsonify({"operation": result.to_dict(), "satellite": satellite.status()}), status_code

    return app


def run_search_request(
    query: str,
    mode: str,
    corpus_search: CorpusSearch,
    contextual_generator: ContextualGenerator,
    translation_service: TranslationService,
    context: str = DEFAULT_CONTEXT,
) -> Tuple[Dict[str, Any], int]:
    started = time.perf_counter()
    if mode == TRANSLATION_MODE:
        try:
            translation = translation_service.translate_to_english(query)
        except TranslationError as exc:
            return {"mode": mode, "query": query, "error": str(exc), "results": []}, 503
        search_query = translation.translated_text
    else:
        translation = None
        search_query = query

    if mode in {CORPUS_MODE, TRANSLATION_MODE}:
        results = prepare_results(corpus_search(search_query))
        response: Dict[str, Any] = {
            "mode": mode,
            "query": query,
            "search_query": search_query,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
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
        }
        if translation is not None:
            response["detected_language"] = translation.detected_source_language
        return response, 200

    try:
        result = contextual_generator.generate(query, context, BEST_MATCHES)
    except (ContextualCompletionError, ValueError) as exc:
        return {"mode": mode, "query": query, "error": str(exc), "results": []}, 503
    return (
        {
            "mode": mode,
            "query": query,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "gemini_ms": result.latency_ms,
            "model": result.model,
            "count": len(result.suggestions),
            "results": [
                {"text": suggestion.text, "ai_generated": True}
                for suggestion in result.suggestions
            ],
        },
        200,
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("AUTOCOMPLETE_LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    app = create_app()
    print("Local demo UI: http://127.0.0.1:5000")
    print("Satellite controls use a local simulator, not a physical satellite link.")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
