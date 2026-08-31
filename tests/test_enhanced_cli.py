from src.auto_complete_data import AutoCompleteData
from src.contextual import ContextualResult, ContextualServiceError, GeneratedSuggestion
from src.enhanced_cli import (
    AI_MODE,
    CORPUS_MODE,
    SessionState,
    format_generated_suggestions,
    process_session_input,
    prompt_for,
    run_feature_cli,
)


def corpus_search(_query):
    return [AutoCompleteData("Corpus sentence.", "archive.txt", 8, 20)]


class FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, prefix, context, count=5):
        self.calls.append((prefix, context, count))
        return ContextualResult(
            suggestions=(
                GeneratedSuggestion(
                    text=f"{prefix} for {context}.",
                    model="test-gemini",
                ),
            ),
            model="test-gemini",
            latency_ms=42,
        )


class FailingGenerator:
    def generate(self, prefix, context, count=5):
        raise ContextualServiceError("Gemini timed out. Your query was kept.")


def test_default_mode_preserves_part_a_corpus_output():
    result = process_session_input(SessionState(), "python", corpus_search, None)

    assert result.state.mode == CORPUS_MODE
    assert result.state.query == "python"
    assert "Corpus sentence." in result.output
    assert "archive.txt:8" in result.output
    assert "score=20" in result.output


def test_user_can_switch_to_ai_mode_and_get_labeled_output():
    generator = FakeGenerator()
    switched = process_session_input(SessionState(), "/mode ai", corpus_search, generator)
    result = process_session_input(switched.state, "We are", corpus_search, generator)

    assert result.state.mode == AI_MODE
    assert generator.calls == [("We are", "general, clear English", 5)]
    assert "AI-generated" in result.output
    assert "[AI-GENERATED]" in result.output
    assert "test-gemini" in result.output
    assert "42 ms" in result.output
    assert "no corpus source, offset, or Part A score" in result.output


def test_context_command_updates_context_without_calling_service():
    generator = FakeGenerator()
    state = SessionState(mode=AI_MODE)

    result = process_session_input(
        state, "/context formal legal writing", corpus_search, generator
    )

    assert result.state.context == "formal legal writing"
    assert result.state.query == ""
    assert generator.calls == []


def test_same_prefix_changes_with_user_context():
    generator = FakeGenerator()
    formal = process_session_input(
        SessionState(mode=AI_MODE, context="formal email"),
        "Thank you",
        corpus_search,
        generator,
    )
    playful = process_session_input(
        SessionState(mode=AI_MODE, context="playful story"),
        "Thank you",
        corpus_search,
        generator,
    )

    assert "formal email" in formal.output
    assert "playful story" in playful.output
    assert formal.output != playful.output


def test_switching_modes_resets_query_and_prompt_shows_mode():
    state = SessionState(query="existing text")
    result = process_session_input(state, "/mode ai", corpus_search, FakeGenerator())

    assert result.state.query == ""
    assert "AI" in prompt_for(result.state)
    assert result.state.context in prompt_for(result.state)


def test_hash_resets_query_but_preserves_mode_and_context():
    state = SessionState(mode=AI_MODE, query="draft", context="medical")
    result = process_session_input(state, "#", corpus_search, FakeGenerator())

    assert result.state == SessionState(mode=AI_MODE, query="", context="medical")


def test_ai_failure_is_clear_and_keeps_query():
    state = SessionState(mode=AI_MODE)
    result = process_session_input(state, "Hello", corpus_search, FailingGenerator())

    assert result.state.query == "Hello"
    assert "AI mode error" in result.output
    assert "timed out" in result.output


def test_ai_mode_without_generator_explains_corpus_fallback():
    state = SessionState(mode=AI_MODE)
    result = process_session_input(state, "Hello", corpus_search, None)

    assert "unavailable" in result.output
    assert "/mode corpus" in result.output


def test_generated_formatter_never_invents_corpus_metadata():
    result = ContextualResult(
        suggestions=(GeneratedSuggestion("Hello there.", "test-gemini"),),
        model="test-gemini",
        latency_ms=10,
    )

    output = format_generated_suggestions(result)

    assert "Here are 1 AI-generated suggestion:" in output
    assert "source=" not in output
    assert "score=" not in output
    assert ".txt:" not in output


def test_unknown_command_returns_help_without_changing_state():
    state = SessionState()
    result = process_session_input(state, "/unknown", corpus_search, None)

    assert result.state == state
    assert "Unknown command" in result.output
    assert "/mode corpus" in result.output


def test_tilde_exits_without_searching():
    result = process_session_input(SessionState(), "~", corpus_search, None)

    assert result.should_exit is True
    assert result.output == "Goodbye."


def test_full_ai_cli_flow(monkeypatch, capsys):
    inputs = iter(
        [
            "/mode ai",
            "/context concise professional email",
            "Thank you for",
            "~",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    run_feature_cli(corpus_search, FakeGenerator())

    output = capsys.readouterr().out
    assert "Mode changed to AI" in output
    assert "AI context updated: concise professional email" in output
    assert "[AI-GENERATED] Thank you for" in output
    assert "Goodbye." in output
