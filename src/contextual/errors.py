"""Stable errors exposed by the contextual-completion boundary."""


class ContextualCompletionError(RuntimeError):
    """Base error safe for the CLI to handle without crashing."""


class ContextualConfigurationError(ContextualCompletionError):
    """The Gemini integration is not configured locally."""


class ContextualServiceError(ContextualCompletionError):
    """Gemini was unavailable or did not complete the request."""


class InvalidGeminiResponseError(ContextualCompletionError):
    """Gemini returned data that cannot be used as suggestions."""
