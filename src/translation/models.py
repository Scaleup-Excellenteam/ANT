"""Small contracts for translating user input before autocomplete search."""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    translated_text: str
    detected_source_language: Optional[str] = None


class TranslationError(Exception):
    """Raised when translation cannot produce a usable English query."""


class TranslationService(Protocol):
    def translate_to_english(self, text: str) -> TranslationResult:
        """Translate `text` into English, using source-language auto-detection."""
