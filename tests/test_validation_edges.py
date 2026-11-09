"""Input boundaries: reject ambiguous or inconsistent financial instructions early."""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from src.i18n import Translator, load_catalog
from src.messages import InputError
from src.models import (
    AnnexInstruction,
    InstallmentMethod,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    RateChange,
    RepaymentModel,
    TermChange,
    validate_date,
)
from src.scenarios import (
    build_annexes,
    build_overpayments,
    date_input,
    decimal_input,
)

D = Decimal
START = date(2026, 1, 15)


def loan(**changes: Any) -> LoanParameters:
    return replace(LoanParameters(D("12000"), D("0.06"), START, 15, 12), **changes)


@pytest.mark.parametrize("value", [None, "2026-01-15", datetime(2026, 1, 15)])
def test_calendar_dates_do_not_accept_datetimes_or_strings(value: Any) -> None:
    with pytest.raises(InputError) as caught:
        validate_date(value, "Simulation start")
    assert caught.value.code == "validation.name_use_a_calendar_date"


@pytest.mark.parametrize("months", [0, -1, True, 1.5, "12"])
def test_term_instruction_requires_positive_integer(months: Any) -> None:
    with pytest.raises(InputError) as caught:
        TermChange(START, months)
    assert (
        caught.value.code == "validation.new_remaining_term_must_be_a_positive_integer"
    )


@pytest.mark.parametrize("day", [0, 32, True, 15.5, "15"])
def test_payment_day_rejects_out_of_range_and_noninteger_values(day: Any) -> None:
    with pytest.raises(InputError) as caught:
        loan(payment_day=day)
    assert caught.value.code == "validation.payment_day_must_be_an_integer_from_1_to"


@pytest.mark.parametrize(
    "field", ["day_count", "installment_method", "shortening_policy"]
)
def test_calculation_conventions_must_be_enum_values(field: str) -> None:
    with pytest.raises(InputError) as caught:
        loan(**{field: "unknown"})
    assert caught.value.code == "validation.unknown_calculation_convention"


def test_current_installment_and_nonnegative_costs_are_validated() -> None:
    assert loan(current_installment=D("1000")).current_installment == D("1000")
    with pytest.raises(InputError) as caught:
        loan(accrued_interest=D("-0.01"))
    assert caught.value.parameters["bound"] == "non-negative"
    assert "nieujemna" in Translator("pl").error(caught.value)
    with pytest.raises(InputError):
        loan(current_installment=D("0"))


def test_rate_change_cannot_precede_balance_date() -> None:
    with pytest.raises(InputError) as caught:
        loan(rate_changes=(RateChange(date(2026, 1, 14), D("0.05")),))
    assert caught.value.code == "validation.rate_change_precedes_the_simulation_start"


@pytest.mark.parametrize("kind", ["rate", "term", "annex"])
def test_duplicate_dated_instructions_are_rejected(kind: str) -> None:
    changes: dict[str, Any] = {}
    if kind == "rate":
        changes["rate_changes"] = (
            RateChange(START, D("0.05")),
            RateChange(START, D("0.06")),
        )
    elif kind == "term":
        changes["term_changes"] = (TermChange(START, 10), TermChange(START, 11))
    else:
        changes.update(
            repayment_model=RepaymentModel.ING,
            installment_method=InstallmentMethod.CALENDAR,
            annexes=(
                AnnexInstruction(START, D("1100")),
                AnnexInstruction(START, D("1200")),
            ),
        )
    with pytest.raises(InputError) as caught:
        loan(**changes)
    assert caught.value.code.startswith("validation.only_one_")


def test_fixed_rate_can_change_on_first_day_after_fixed_period() -> None:
    end = date(2026, 6, 15)
    params = loan(fixed_until=end, rate_changes=(RateChange(end, D("0.05")),))
    assert params.rate_changes[0].date == end


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"repayment_model": "ING"}, "validation.unknown_repayment_model"),
        (
            {"repayment_model": RepaymentModel.ING},
            "validation.the_ing_model_requires_calendar_installments",
        ),
        (
            {
                "repayment_model": RepaymentModel.ING,
                "installment_method": InstallmentMethod.CALENDAR,
                "term_changes": (TermChange(START, 10),),
            },
            "validation.use_a_target_installment_amendment_in_the_ing_model",
        ),
        (
            {"annexes": (AnnexInstruction(START, D("1100")),)},
            "validation.target_installment_amendments_require_the_ing_model",
        ),
    ],
)
def test_incompatible_repayment_instructions_are_rejected(
    changes: dict[str, Any], code: str
) -> None:
    with pytest.raises(InputError) as caught:
        loan(**changes)
    assert caught.value.code == code


def test_custom_holiday_must_be_a_calendar_date() -> None:
    assert loan(additional_holidays=(date(2026, 2, 16),)).additional_holidays
    with pytest.raises(InputError):
        loan(additional_holidays=("2026-02-16",))


@pytest.mark.parametrize(
    "shorten,reduce", [(None, D("100")), (D("100"), None), (D("40"), D("40"))]
)
def test_mixed_allocations_must_be_complete_and_sum_to_payment(
    shorten: Decimal | None, reduce: Decimal | None
) -> None:
    with pytest.raises(InputError) as caught:
        Overpayment(D("100"), OverpaymentStrategy.MIXED, START, shorten, reduce)
    assert caught.value.code in {
        "validation.mixed_strategy_requires_both_allocation_amounts",
        "validation.mixed_allocations_must_sum_to_the_overpayment_amount",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_shorten": D("100")},
        {"amount_reduce": D("100")},
        {"strategy": "SHORTEN_TERM"},
    ],
)
def test_single_strategy_cannot_accept_split_or_unknown_strategy(
    changes: dict[str, Any],
) -> None:
    values: dict[str, Any] = dict(
        amount=D("100"), strategy=OverpaymentStrategy.SHORTEN_TERM, date=START
    )
    values.update(changes)
    with pytest.raises(InputError):
        Overpayment(**values)


def test_annex_target_must_meet_supplied_minimum() -> None:
    with pytest.raises(InputError) as caught:
        AnnexInstruction(START, D("1000"), minimum_payment=D("1100"))
    assert (
        caught.value.code
        == "validation.selected_installment_is_below_the_supplied_ing_minimum"
    )


@pytest.mark.parametrize(
    "value", ["not a number", None, True, "NaN", "Infinity", "-Infinity"]
)
def test_input_parser_rejects_invalid_or_nonfinite_numbers(value: Any) -> None:
    with pytest.raises(InputError):
        decimal_input(value)


@pytest.mark.parametrize(
    "value", ["2026-02-30", "15/01/2026", None, datetime(2026, 1, 15)]
)
def test_date_parser_rejects_invalid_iso_dates(value: Any) -> None:
    with pytest.raises(InputError) as caught:
        date_input(value)
    assert caught.value.code == "validation.use_an_iso_date_yyyy_mm_dd_value"


def test_date_parser_accepts_existing_date_without_changing_it() -> None:
    assert date_input(START) == START


@pytest.mark.parametrize("month", [0, -1, 13, True, 1.5])
def test_single_payment_month_must_be_an_existing_integer_installment(
    month: Any,
) -> None:
    with pytest.raises(InputError) as caught:
        build_overpayments(
            loan(),
            "single",
            OverpaymentStrategy.REDUCE_INSTALLMENT,
            D("100"),
            month=month,
        )
    assert (
        caught.value.code
        == "validation.overpayment_month_is_outside_the_remaining_loan_term"
    )


def test_unknown_mode_and_empty_irregular_list() -> None:
    with pytest.raises(InputError) as caught:
        build_overpayments(
            loan(), "unknown", OverpaymentStrategy.REDUCE_INSTALLMENT, D("100")
        )
    assert caught.value.code == "validation.unknown_overpayment_mode"
    assert (
        build_overpayments(
            loan(), "irregular", OverpaymentStrategy.REDUCE_INSTALLMENT, D("0")
        )
        == []
    )


def test_irregular_mixed_payment_preserves_explicit_allocations() -> None:
    result = build_overpayments(
        loan(),
        "irregular",
        OverpaymentStrategy.REDUCE_INSTALLMENT,
        D("0"),
        rows=[
            {
                "date": "2026-01-20",
                "amount": "200,00",
                "strategy": "MIXED",
                "shorten": "150",
                "reduce": "50",
            }
        ],
    )
    assert result == [
        Overpayment(
            D("200"), OverpaymentStrategy.MIXED, date(2026, 1, 20), D("150"), D("50")
        )
    ]


def test_annex_parser_keeps_explicit_bank_bounds() -> None:
    result = build_annexes(
        [
            {
                "date": "2026-01-20",
                "target_payment": "1100",
                "minimum_payment": "1000,50",
                "maximum_payment": "1200",
            }
        ]
    )
    assert result == (
        AnnexInstruction(date(2026, 1, 20), D("1100"), D("1000.50"), D("1200")),
    )


def test_unsupported_language_and_unstructured_error_fallback() -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        load_catalog("de")
    for language in ("pl", "en"):
        translator = Translator(language)
        assert translator.error(TypeError("internal technical detail")) == translator(
            "validation.invalid_input"
        )


@pytest.mark.parametrize("first", [START, date(2026, 1, 14)])
def test_first_payment_must_be_after_balance_date(first: date) -> None:
    with pytest.raises(InputError) as caught:
        loan(first_payment_date=first)
    assert (
        caught.value.code
        == "validation.first_payment_must_be_after_the_simulation_start"
    )


def test_disabled_overpayments_do_not_use_configured_budget() -> None:
    assert (
        build_overpayments(
            loan(), "none", OverpaymentStrategy.REDUCE_INSTALLMENT, D("1000")
        )
        == []
    )


@pytest.mark.parametrize("language,expected", [("pl", "6,45%"), ("en", "6.45%")])
def test_rate_formatting_preserves_the_fractional_rate(
    language: str, expected: str
) -> None:
    rate = D("0.0645")
    assert Translator(language).percent(rate) == expected
    assert rate == D("0.0645")
