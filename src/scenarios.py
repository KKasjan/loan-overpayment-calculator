"""Pure scenario construction and input parsing, independently testable from Streamlit."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from src.calculator import payment_dates
from src.models import (
    LoanParameters,
    AnnexInstruction,
    Overpayment,
    OverpaymentStrategy,
    RateChange,
    TermChange,
)


def decimal_input(value: Any) -> Decimal:
    try:
        number = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid number: {value!r}") from None
    if not number.is_finite():
        raise ValueError("A number must be finite.")
    return number


def percent_input(value: Any) -> Decimal:
    return decimal_input(value) / Decimal("100")


def date_input(value: Any) -> date:
    if type(value) is date:
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"Use an ISO date (YYYY-MM-DD): {value!r}") from None


def build_overpayments(
    params: LoanParameters,
    mode: str,
    strategy: OverpaymentStrategy,
    amount: Decimal,
    *,
    month: int = 1,
    shorten: Decimal | None = None,
    reduce: Decimal | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> list[Overpayment]:
    if mode == "none":
        return []
    if mode == "irregular":
        result = []
        for row in rows or []:
            labels = {
                "Obniżenie raty": OverpaymentStrategy.REDUCE_INSTALLMENT,
                "Skrócenie okresu": OverpaymentStrategy.SHORTEN_TERM,
                "Mixed": OverpaymentStrategy.MIXED,
            }
            label = str(row["strategy"])
            row_strategy = (
                labels[label] if label in labels else OverpaymentStrategy(label)
            )
            result.append(
                Overpayment(
                    amount=decimal_input(row["amount"]),
                    date=date_input(row["date"]),
                    strategy=row_strategy,
                    amount_shorten=decimal_input(row["shorten"])
                    if row_strategy == OverpaymentStrategy.MIXED
                    else None,
                    amount_reduce=decimal_input(row["reduce"])
                    if row_strategy == OverpaymentStrategy.MIXED
                    else None,
                )
            )
        return result
    dates = payment_dates(params)
    if mode == "single":
        if (
            not isinstance(month, int) or isinstance(month, bool)
        ) or not 1 <= month <= len(dates):
            raise ValueError("Overpayment month is outside the remaining loan term.")
        dates = [dates[month - 1]]
    elif mode != "regular":
        raise ValueError("Unknown overpayment mode.")
    if amount == 0:
        return []
    return [
        Overpayment(
            amount=amount,
            strategy=strategy,
            date=when,
            amount_shorten=shorten,
            amount_reduce=reduce,
        )
        for when in dates
    ]


def build_rate_changes(rows: list[dict[str, Any]]) -> tuple[RateChange, ...]:
    return tuple(
        RateChange(date_input(row["date"]), percent_input(row["rate_percent"]))
        for row in rows
    )


def build_term_changes(rows: list[dict[str, Any]]) -> tuple[TermChange, ...]:
    result = []
    for row in rows:
        months = decimal_input(row["remaining_months"])
        if months != months.to_integral_value():
            raise ValueError("Remaining months must be an integer.")
        result.append(TermChange(date_input(row["date"]), int(months)))
    return tuple(result)


def build_annexes(rows: list[dict[str, Any]]) -> tuple[AnnexInstruction, ...]:
    def optional(value: Any) -> Decimal | None:
        if value is None or str(value).strip() in ("", "nan", "<NA>"):
            return None
        return decimal_input(value)

    return tuple(
        AnnexInstruction(
            date_input(row["date"]),
            decimal_input(row["target_payment"]),
            optional(row.get("minimum_payment")),
            optional(row.get("maximum_payment")),
        )
        for row in rows
    )
