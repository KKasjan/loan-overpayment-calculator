"""Structured domain errors with stable codes and English diagnostic messages."""

from typing import Any

from src.i18n import load_catalog


class MessageError(Exception):
    def __init__(self, code: str, **parameters: Any) -> None:
        self.code = code
        self.parameters = parameters
        Exception.__init__(self, load_catalog("en")[code].format(**parameters))


class InputError(MessageError, ValueError):
    """A user-correctable validation error."""


class CalculationError(MessageError, ArithmeticError):
    """A failed numerical reconciliation."""
