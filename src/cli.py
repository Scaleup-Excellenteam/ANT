"""Member 3 - interactive serving / CLI layer.

This module intentionally depends only on a search function with the contract:
    get_best_k_completions(prefix: str) -> List[AutoCompleteData]

The Part B interface reuses these Part A formatting and query helpers from
`enhanced_cli.py`, keeping the original corpus behavior independently testable.
"""

import logging
from typing import Callable, List, Optional, Sequence, Tuple

try:
    from .auto_complete_data import AutoCompleteData
    from .translation import TranslationError, TranslationResult, TranslationService
except ImportError:
    from auto_complete_data import AutoCompleteData
    from translation import TranslationError, TranslationResult, TranslationService

WELCOME_MSG = "The system is ready. Enter your text:"
GET_INPUT = "Enter more text (# to restart, ~ to quit):"
QUIT_MESSAGE = "~"
RESTART_MESSAGE = "#"
TRANSLATE_COMMAND = "/translate"
ENGLISH_COMMAND = "/english"
TRANSLATION_MODE_ENABLED = "Translation mode enabled. Target language: English."
ENGLISH_MODE_ENABLED = "English mode enabled."
TRANSLATION_UNAVAILABLE = "Translation mode is unavailable: no translation service configured."
TRANSLATED_QUERY_PREFIX = "Translated English query:"
NO_MATCHES = "No suggestions found."
EMPTY_INPUT = "Please enter some text."
BEST_MATCHES = 5

SearchFunction = Callable[[str], List[AutoCompleteData]]
logger = logging.getLogger("cli")


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

    updated_query, output, _ = process_input_with_mode(
        current_query=current_query,
        new_text=new_text,
        search_function=search_function,
        translation_service=None,
        translation_mode=False,
    )
    return updated_query, output


def process_input_with_mode(
    current_query: str,
    new_text: str,
    search_function: SearchFunction,
    translation_service: Optional[TranslationService] = None,
    translation_mode: bool = False,
) -> Tuple[str, str, bool]:
    """Process one Enter press, including English/Translation mode commands."""

    command = new_text.strip().lower()
    if command == TRANSLATE_COMMAND:
        return current_query, TRANSLATION_MODE_ENABLED, True
    if command == ENGLISH_COMMAND:
        return current_query, ENGLISH_MODE_ENABLED, False

    # '#' means the user finished the current sentence and wants a fresh query.
    if new_text.endswith(RESTART_MESSAGE):
        logger.info("Query reset requested")
        return "", "Query reset. Start a new sentence.", translation_mode

    updated_query = current_query + new_text

    if not updated_query.strip():
        logger.debug("Empty query ignored")
        return updated_query, EMPTY_INPUT, translation_mode

    if translation_mode:
        if translation_service is None:
            return updated_query, TRANSLATION_UNAVAILABLE, translation_mode
        try:
            translation = translation_service.translate_to_english(updated_query)
        except TranslationError as exc:
            return updated_query, f"Translation failed: {exc}", translation_mode
        output = _format_translated_search(translation, search_function)
        return updated_query, output, translation_mode

    results = search_function(updated_query)
    results = prepare_results(results)
    return updated_query, format_suggestions(results), translation_mode


def _format_translated_search(
    translation: TranslationResult, search_function: SearchFunction
) -> str:
    translated_query = translation.translated_text
    results = search_function(translated_query)
    results = prepare_results(results)
    return "\n".join(
        [
            f"{TRANSLATED_QUERY_PREFIX} {translated_query}",
            format_suggestions(results),
        ]
    )


def run_cli(
    search_function: SearchFunction,
    translation_service: Optional[TranslationService] = None,
) -> None:
    """Run the online/serving loop."""

    current_query = ""
    translation_mode = False
    logger.info("CLI session started")
    print(WELCOME_MSG)

    while True:
        try:
            mode_label = "Translation" if translation_mode else "English"
            additional_input = input(f"[{mode_label}] {GET_INPUT} {current_query}")
        except (EOFError, KeyboardInterrupt):
            logger.info("CLI session ended by input interruption")
            print("\nGoodbye.")
            break

        if additional_input.endswith(QUIT_MESSAGE):
            logger.info("CLI session ended by user")
            print("Goodbye.")
            break

        current_query, output, translation_mode = process_input_with_mode(
            current_query=current_query,
            new_text=additional_input,
            search_function=search_function,
            translation_service=translation_service,
            translation_mode=translation_mode,
        )
        print(output)
