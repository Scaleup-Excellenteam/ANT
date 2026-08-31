from dataclasses import dataclass


@dataclass
class AutoCompleteData:
    """Represents one autocomplete result returned by the matching layer."""

    completed_sentence: str
    source_text: str
    offset: int
    score: int
