"""Pure scenario construction and input parsing, independently testable from Streamlit."""

from src.messages import InputError

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
    validate_money,
)


def decimal_input(value: Any) -> Decimal:
    try:
        number = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise InputError("validation.invalid_number_value", value=value) from None
    if not number.is_finite():
        raise InputError("validation.a_number_must_be_finite")
    return number


def percent_input(value: Any) -> Decimal:
    return decimal_input(value) / Decimal("100")


def date_input(value: Any) -> date:
    if type(value) is date:
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise InputError(
            "validation.use_an_iso_date_yyyy_mm_dd_value", value=value
        ) from None


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
            row_strategy = OverpaymentStrategy(str(row["strategy"]))
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
            raise InputError(
                "validation.overpayment_month_is_outside_the_remaining_loan_term"
            )
        dates = [dates[month - 1]]
    elif mode != "regular":
        raise InputError("validation.unknown_overpayment_mode")
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
            raise InputError("validation.remaining_months_must_be_an_integer")
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


def principal_from_balance(
    balance: Decimal, accrued_interest: Decimal, *, includes_interest: bool
) -> Decimal:
    """Normalize a bank balance without capitalizing already accrued interest.

    The total option means principal + interest only, excluding fees/insurance.
    Both amounts must be reported for the same state date.
    """
    validate_money(balance, "Balance", positive=True)
    validate_money(accrued_interest, "Accrued interest")
    principal = balance - accrued_interest if includes_interest else balance
    if principal <= 0:
        raise InputError(
            "validation.accrued_interest_must_be_less_than_the_total_balance"
        )
    return principal
