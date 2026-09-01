"""Member 3 - interactive serving / CLI layer.

This module intentionally depends only on a search function with the contract:
    get_best_k_completions(prefix: str) -> List[AutoCompleteData]

For now `main.py` injects a mock implementation. When Member 2 finishes, the
same CLI can be connected to the real matching function without rewriting the
serving logic.
"""

from typing import Callable, List, Sequence, Tuple

try:
    from .auto_complete_data import AutoCompleteData
except ImportError:
    from auto_complete_data import AutoCompleteData

WELCOME_MSG = "The system is ready. Enter your text:"
GET_INPUT = "Enter more text (# to restart, ~ to quit):"
QUIT_MESSAGE = "~"
RESTART_MESSAGE = "#"
NO_MATCHES = "No suggestions found."
EMPTY_INPUT = "Please enter some text."
BEST_MATCHES = 5

SearchFunction = Callable[[str], List[AutoCompleteData]]


def prepare_results(results: Sequence[AutoCompleteData]) -> List[AutoCompleteData]:
    """Return at most five results in the required final display order.

    Current Member-3 decision:
    - higher score first
    - alphabetical completed_sentence for equal scores

    If Member 2 later guarantees this exact ordering, this function can stay as
    a harmless final guard or be removed after the team agrees on one owner.
    """

    return sorted(
        results,
        key=lambda item: (-item.score, item.completed_sentence.lower()),
    )[:BEST_MATCHES]


def format_suggestions(results: Sequence[AutoCompleteData]) -> str:
    """Format results using all fields required by the assignment."""

    if not results:
        return NO_MATCHES

    lines = [f"Here are {len(results)} suggestions:"]
    for rank, result in enumerate(results, start=1):
        displayed_sentence = result.completed_sentence.lstrip()
        lines.append(
            f"{rank}. {displayed_sentence} "
            f"({result.source_text}:{result.offset}, score={result.score})"
        )
    return "\n".join(lines)


def process_input(
    current_query: str,
    new_text: str,
    search_function: SearchFunction,
) -> Tuple[str, str]:
    """Process one Enter press without doing terminal I/O.

    This separation makes the serving behavior easy to unit-test.

    Returns:
        (updated_query, text_to_print)
    """

    # '#' means the user finished the current sentence and wants a fresh query.
    if new_text.endswith(RESTART_MESSAGE):
        return "", "Query reset. Start a new sentence."

    updated_query = current_query + new_text

    if not updated_query.strip():
        return updated_query, EMPTY_INPUT

    results = search_function(updated_query)
    results = prepare_results(results)
    return updated_query, format_suggestions(results)


def run_cli(search_function: SearchFunction) -> None:
    """Run the online/serving loop."""

    current_query = ""
    print(WELCOME_MSG)

    while True:
        try:
            additional_input = input(f"{GET_INPUT} {current_query}")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if additional_input.endswith(QUIT_MESSAGE):
            print("Goodbye.")
            break

        current_query, output = process_input(
            current_query=current_query,
            new_text=additional_input,
            search_function=search_function,
        )
        print(output)


def format_semantic_suggestions(results) -> str:
    """Format semantic rank separately from the Part A edit score."""

    if not results:
        return NO_MATCHES
    lines = [f"Here are {len(results)} semantic suggestions:"]
    for rank, result in enumerate(results, start=1):
        lines.append(
            f"{rank}. {result.completed_sentence.lstrip()} "
            f"({result.source_text}:{result.offset}, "
            f"semantic_similarity={result.similarity:.4f})"
        )
    return "\n".join(lines)


def run_semantic_cli(search_function) -> None:
    """Run an explicit semantic-search mode; Part A behavior stays untouched."""

    print("Semantic search mode (Gemini Embeddings). Enter ~ to quit.")
    while True:
        try:
            query = input("Semantic query: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if query.endswith(QUIT_MESSAGE):
            print("Goodbye.")
            break
        if not query.strip():
            print(EMPTY_INPUT)
            continue
        try:
            print(format_semantic_suggestions(search_function(query)))
        except Exception as exc:
            print(f"Semantic search unavailable: {exc}")
            print("The basic autocomplete mode is still available without --semantic.")
