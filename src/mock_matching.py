"""Temporary Member-2 replacement used only while matching is unfinished."""

from typing import List

try:
    from .auto_complete_data import AutoCompleteData
except ImportError:  # Allows direct execution from the src folder.
    from auto_complete_data import AutoCompleteData


def get_best_k_completions(prefix: str) -> List[AutoCompleteData]:
    """Return deterministic fake data so Member 3 can develop independently.

    Manual demo helpers:
    - type text containing 'none' -> zero matches
    - type text containing 'few'  -> two matches
    - anything else              -> five matches
    """

    if not prefix.strip():
        return []

    lowered = prefix.lower()
    if "none" in lowered:
        return []

    demo_results = [
        AutoCompleteData("Gamma: this is a demo.", "example.txt", 4, 14),
        AutoCompleteData("Alpha: this is a demo.", "example.txt", 1, 14),
        AutoCompleteData("Omega: this is a demo.", "example.txt", 5, 14),
        AutoCompleteData("Beta: this is a demo.", "example.txt", 2, 14),
        AutoCompleteData("Delta: this is a demo.", "example.txt", 3, 14),
    ]

    if "few" in lowered:
        return demo_results[:2]

    return demo_results
