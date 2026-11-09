"""Presentation-only localization; business calculations never depend on language."""

from functools import lru_cache
import json
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

LOCALES = Path(__file__).resolve().parents[1] / "locales"
LANGUAGES = ("pl", "en")


def load_catalog(language: str) -> dict[str, str]:
    if language not in LANGUAGES:
        raise ValueError("Unsupported language.")
    path = LOCALES / f"{language}.json"
    return _read_catalog(language, path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _read_catalog(language: str, version: int) -> dict[str, str]:
    """Invalidate cached translations when a locale file changes."""
    return json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))


class Translator:
    def __init__(self, language: str = "pl") -> None:
        self.language = language
        self.catalog = load_catalog(language)

    def __call__(self, key: str, **values: Any) -> str:
        return self.catalog[key].format(**values)

    def money(self, value: Decimal | float | int) -> str:
        rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        number = f"{rounded:,.2f}"
        if self.language == "pl":
            return (
                number.replace(",", " ").replace(".", ",") + " " + self("currency.unit")
            )
        return number + " " + self("currency.unit")

    def percent(self, value: Decimal | float | int) -> str:
        number = f"{Decimal(str(value)) * 100:.2f}"
        return (number.replace(".", ",") if self.language == "pl" else number) + "%"

    def error(self, error: Exception) -> str:
        from src.messages import MessageError

        if not isinstance(error, MessageError):
            return self("validation.invalid_input")
        values = dict(error.parameters)
        for key in ("name", "bound"):
            if key in values:
                values[key] = self("field." + str(values[key]))
        return self(error.code, **values)
