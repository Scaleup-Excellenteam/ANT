"""Part B CLI with explicit corpus and Gemini-generated completion modes."""

from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Protocol

try:
    from .auto_complete_data import AutoCompleteData
    from .cli import EMPTY_INPUT, format_suggestions, prepare_results
    from .contextual import ContextualCompletionError, ContextualResult
except ImportError:  # Supports: python src/main.py
    from auto_complete_data import AutoCompleteData
    from cli import EMPTY_INPUT, format_suggestions, prepare_results
    from contextual import ContextualCompletionError, ContextualResult

CORPUS_MODE = "corpus"
AI_MODE = "ai"
DEFAULT_CONTEXT = "general, clear English"
HELP_TEXT = (
    "Commands: /mode corpus | /mode ai | /context <domain or style> | "
    "/help | # reset | ~ quit"
)

CorpusSearch = Callable[[str], List[AutoCompleteData]]


class ContextualGenerator(Protocol):
    def generate(self, prefix: str, context: str, count: int = 5) -> ContextualResult:
        ...


@dataclass(frozen=True)
class SessionState:
    mode: str = CORPUS_MODE
    query: str = ""
    context: str = DEFAULT_CONTEXT


@dataclass(frozen=True)
class InteractionResult:
    state: SessionState
    output: str
    should_exit: bool = False


def format_generated_suggestions(result: ContextualResult) -> str:
    """Clearly distinguish model output from Part A corpus matches."""
    count = len(result.suggestions)
    noun = "suggestion" if count == 1 else "suggestions"
    lines = [
        f"Here are {count} AI-generated {noun}:",
        (
            f"Gemini model: {result.model}; response time: {result.latency_ms} ms; "
            "no corpus source, offset, or Part A score."
        ),
    ]
    for rank, suggestion in enumerate(result.suggestions, start=1):
        lines.append(f"{rank}. [AI-GENERATED] {suggestion.text}")
    return "\n".join(lines)


def process_session_input(
    state: SessionState,
    new_text: str,
    corpus_search: CorpusSearch,
    contextual_generator: Optional[ContextualGenerator],
) -> InteractionResult:
    """Process one input line without terminal I/O so every mode is testable."""
    command = new_text.strip()

    if command == "~":
        return InteractionResult(state=state, output="Goodbye.", should_exit=True)

    if new_text.endswith("#"):
        return InteractionResult(
            state=replace(state, query=""),
            output=f"Query reset. Current mode: {state.mode.upper()}.",
        )

    if command.startswith("/"):
        return _process_command(state, command)

    updated_state = replace(state, query=state.query + new_text)
    if not updated_state.query.strip():
        return InteractionResult(state=updated_state, output=EMPTY_INPUT)

    if updated_state.mode == CORPUS_MODE:
        results = prepare_results(corpus_search(updated_state.query))
        return InteractionResult(
            state=updated_state,
            output=format_suggestions(results),
        )

    if contextual_generator is None:
        return InteractionResult(
            state=updated_state,
            output=(
                "AI mode is unavailable because no Gemini generator is configured. "
                "Your query was kept; use /mode corpus."
            ),
        )

    try:
        result = contextual_generator.generate(
            prefix=updated_state.query,
            context=updated_state.context,
            count=5,
        )
    except (ContextualCompletionError, ValueError) as exc:
        return InteractionResult(state=updated_state, output=f"AI mode error: {exc}")

    return InteractionResult(
        state=updated_state,
        output=format_generated_suggestions(result),
    )


def _process_command(state: SessionState, command: str) -> InteractionResult:
    parts = command.split(maxsplit=1)
    name = parts[0].lower()
    argument = parts[1].strip() if len(parts) == 2 else ""

    if name == "/help":
        return InteractionResult(state=state, output=HELP_TEXT)

    if name == "/mode":
        mode = argument.lower()
        if mode not in (CORPUS_MODE, AI_MODE):
            return InteractionResult(
                state=state,
                output="Invalid mode. Use /mode corpus or /mode ai.",
            )
        return InteractionResult(
            state=replace(state, mode=mode, query=""),
            output=f"Mode changed to {mode.upper()}. Query reset.",
        )

    if name == "/context":
        if not argument:
            return InteractionResult(
                state=state,
                output=f"Current AI context: {state.context}",
            )
        if len(argument) > 500:
            return InteractionResult(
                state=state,
                output="Context is too long; use at most 500 characters.",
            )
        return InteractionResult(
            state=replace(state, context=argument),
            output=f"AI context updated: {argument}",
        )

    return InteractionResult(state=state, output=f"Unknown command. {HELP_TEXT}")


def prompt_for(state: SessionState) -> str:
    context = f" | context={state.context}" if state.mode == AI_MODE else ""
    return f"[{state.mode.upper()}{context}] Enter more text: {state.query}"


def run_feature_cli(
    corpus_search: CorpusSearch,
    contextual_generator: Optional[ContextualGenerator] = None,
) -> None:
    """Run the integrated Part A + Part B interactive experience."""
    state = SessionState()
    print("The system is ready. Mode: CORPUS.")
    print(HELP_TEXT)

    while True:
        try:
            additional_input = input(prompt_for(state))
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        interaction = process_session_input(
            state=state,
            new_text=additional_input,
            corpus_search=corpus_search,
            contextual_generator=contextual_generator,
        )
        state = interaction.state
        print(interaction.output)
        if interaction.should_exit:
            break
