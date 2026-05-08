from __future__ import annotations


class NL2SQLAgentError(Exception):
    """Base project error."""


class ConfigurationError(NL2SQLAgentError):
    """Raised when config is missing or invalid."""


class StartupError(NL2SQLAgentError):
    """Raised when application startup fails."""


__all__ = [
    "ConfigurationError",
    "NL2SQLAgentError",
    "StartupError",
]
