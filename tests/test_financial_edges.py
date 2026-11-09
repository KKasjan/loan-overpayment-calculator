"""Boundary schedules, infeasible goals, and independent reconciliation defenses."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src import calculator, ing
from src.messages import CalculationError, InputError
from src.models import (
    AnnexInstruction,
    InstallmentMethod,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    RateChange,
    RepaymentModel,
)

D = Decimal
START = date(2026, 1, 15)


def loan(*, bank: bool = False, **changes: Any) -> LoanParameters:
    base = LoanParameters(D("12000"), D("0"), START, 15, 12)
    if bank:
        base = replace(
            base,
            repayment_model=RepaymentModel.ING,
            installment_method=InstallmentMethod.CALENDAR,
        )
    return replace(base, **changes)


@pytest.mark.parametrize("day", [0, 32, True, 1.5])
def test_next_date_rejects_invalid_payment_day(day: Any) -> None:
    with pytest.raises(InputError):
        calculator.get_next_payment_date(START, day)


def test_empty_remaining_dates_require_no_general_annuity() -> None:
    params = loan()
    assert calculator.annuity_payment(params.amount, D("0"), [], START, params) == 0


def test_remaining_count_reports_balance_if_available_dates_are_insufficient() -> None:
    params = loan()
    assert calculator._remaining_count(
        D("12000"),
        D("1000"),
        [date(2026, 2, 15), date(2026, 3, 15)],
        START,
        params,
        D("0"),
    ) == (2, D("10000"))


def test_remaining_count_rejects_payment_below_period_interest() -> None:
    with pytest.raises(InputError) as caught:
        calculator._remaining_count(
            D("12000"), D("1"), [date(2026, 2, 15)], START, loan(), D("0.12")
        )
    assert (
        caught.value.code
        == "validation.installment_does_not_cover_interest_choose_calendar_annuity_or"
    )


@pytest.mark.parametrize("bank", [False, True])
def test_current_payment_must_cover_interest(bank: bool) -> None:
    params = loan(bank=bank, annual_interest_rate=D("0.12"), current_installment=D("1"))
    with pytest.raises(InputError) as caught:
        calculator.generate_amortization_schedule(params)
    assert "does_not_cover_interest" in caught.value.code


@pytest.mark.parametrize("bank", [False, True])
def test_future_rate_changes_outside_original_horizon_are_rejected(bank: bool) -> None:
    params = loan(bank=bank, rate_changes=(RateChange(date(2027, 2, 15), D("0.05")),))
    with pytest.raises(InputError):
        calculator.generate_amortization_schedule(params)


def test_bank_model_rejects_amendment_outside_horizon() -> None:
    params = loan(bank=True, annexes=(AnnexInstruction(date(2027, 2, 15), D("1100")),))
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(params, [])
    assert (
        caught.value.code
        == "validation.amendment_or_rate_change_is_outside_the_simulation_range"
    )


def test_ing_entry_point_rejects_general_model() -> None:
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(loan(), [])
    assert caught.value.code == "validation.select_the_ing_model"


def test_bank_quote_with_no_future_dates_is_rejected() -> None:
    state = ing.LoanState(START, D("100"), D("12.34"), D("100"), ())
    with pytest.raises(InputError) as caught:
        ing.quote_payment(state, (), loan(bank=True))
    assert (
        caught.value.code
        == "validation.no_future_installments_are_available_for_recalculation"
    )


def test_zero_principal_quote_only_settles_accrued_interest() -> None:
    dates = (date(2026, 2, 15),)
    state = ing.LoanState(START, D("0"), D("12.34"), D("100"), dates)
    assert ing.quote_payment(state, dates, loan(bank=True)) == D("12.34")


def test_one_remaining_installment_cannot_be_shortened_by_a_month() -> None:
    params = loan(
        bank=True, total_month=1, annexes=(AnnexInstruction(START, D("12000")),)
    )
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(params, [])
    assert (
        caught.value.code
        == "validation.too_few_installments_remain_to_shorten_the_term_by"
    )


@pytest.mark.parametrize(
    "when", [date(2026, 1, 14), date(2027, 1, 15), date(2027, 1, 16)]
)
def test_quote_date_must_be_within_open_loan_period(when: date) -> None:
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(loan(bank=True), [], stop_date=when)
    assert (
        caught.value.code
        == "validation.the_quote_date_must_precede_the_final_installment"
    )


def test_amendment_cannot_follow_same_day_full_payoff() -> None:
    when = date(2026, 1, 20)
    params = loan(bank=True, annexes=(AnnexInstruction(when, D("1100")),))
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(
            params,
            [Overpayment(D("12000"), OverpaymentStrategy.REDUCE_INSTALLMENT, when)],
        )
    assert (
        caught.value.code == "validation.the_amendment_falls_after_full_loan_repayment"
    )


@pytest.mark.parametrize("quote_date", [date(2026, 1, 20), date(2026, 1, 21)])
def test_quote_after_payoff_is_not_a_zero_cost_loan_goal(quote_date: date) -> None:
    with pytest.raises(InputError) as caught:
        ing.simulate_ing(
            loan(bank=True),
            [
                Overpayment(
                    D("12000"),
                    OverpaymentStrategy.REDUCE_INSTALLMENT,
                    date(2026, 1, 20),
                )
            ],
            stop_date=quote_date,
        )
    assert (
        caught.value.code
        == "validation.the_loan_was_repaid_before_the_selected_quote_date"
    )


def test_inverse_goal_requires_removal_of_existing_same_day_amendment() -> None:
    params = loan(bank=True, annexes=(AnnexInstruction(START, D("1100")),))
    with pytest.raises(InputError) as caught:
        ing.required_overpayment(params, START, 1, D("1100"))
    assert (
        caught.value.code
        == "validation.remove_the_amendment_on_the_quote_date_the_planned"
    )


def test_capital_overpayment_cannot_erase_already_accrued_interest() -> None:
    params = loan(bank=True, accrued_interest=D("500"))
    with pytest.raises(InputError) as caught:
        ing.required_overpayment(params, START, 1, D("100"))
    assert (
        caught.value.code
        == "validation.the_installment_ceiling_does_not_cover_accrued_interest_settle"
    )


@pytest.mark.parametrize("method", list(InstallmentMethod))
def test_rate_change_preserves_shortening_achieved_before_it(
    method: InstallmentMethod,
) -> None:
    params = loan(
        installment_method=method,
        rate_changes=(RateChange(date(2026, 3, 1), D("0.12")),),
    )
    schedule = calculator.generate_amortization_schedule(
        params,
        [Overpayment(D("2000"), OverpaymentStrategy.SHORTEN_TERM, date(2026, 2, 15))],
    )
    assert schedule[0].total_installment == D("1000")
    assert schedule[1].interest == D("41.42")  # 9000 * 12% * 14 / 365
    assert len(schedule) == 10
    assert schedule[-1].remaining_balance == 0
    assert sum(row.principal + row.overpayment for row in schedule) == D("12000")


def test_unrealistically_low_current_payment_warns_about_large_final_settlement() -> (
    None
):
    summary = calculator.calculate_simulation_summary(
        loan(total_month=3, current_installment=D("200")), []
    )
    assert [row.total_installment for row in summary.standard_schedule] == [
        D("200"),
        D("200"),
        D("11600"),
    ]
    assert (
        "validation.a_payment_exceeds_the_initial_installment_by_more_than"
        in summary.warnings
    )


def test_custom_holidays_and_pre_2025_christmas_eve() -> None:
    params = loan(shift_collection_dates=True, additional_holidays=(date(2026, 1, 2),))
    assert calculator.collection_date(date(2026, 1, 2), params) == date(2026, 1, 5)
    assert calculator.collection_date(date(2024, 12, 24), params) == date(2024, 12, 24)


@pytest.mark.parametrize("bank", [False, True])
def test_balance_based_insurance_is_charged_separately_from_principal(
    bank: bool,
) -> None:
    summary = calculator.calculate_simulation_summary(
        loan(
            bank=bank,
            annual_balance_insurance_rate=D("0.012"),
            monthly_cost=D("10"),
            upfront_cost=D("100"),
        ),
        [],
    )
    assert summary.standard_schedule[0].additional_cost == D("22")
    assert summary.standard_schedule[-1].additional_cost == D("11")
    assert summary.total_cost_standard == D("298")  # 100 + 12*10 + (12+11+...+1)
    assert summary.total_paid_standard == D("12298")


@pytest.mark.parametrize(
    "bank,field,code",
    [
        (
            False,
            "remaining_balance",
            "validation.schedule_ended_with_outstanding_principal",
        ),
        (False, "principal", "validation.principal_reconciliation_failed"),
        (
            False,
            "total_installment",
            "validation.payment_and_interest_reconciliation_failed",
        ),
        (True, "principal", "validation.ing_model_principal_reconciliation_failed"),
        (
            True,
            "total_installment",
            "validation.ing_model_payment_reconciliation_failed",
        ),
    ],
)
def test_reconciliation_rejects_corrupted_ledger_rows(
    monkeypatch, bank: bool, field: str, code: str
) -> None:
    """Fault injection checks the defensive ledger boundary, not normal bank behavior."""
    module = ing if bank else calculator
    original = module.InstallmentDetails

    def corrupt(*args: Any, **kwargs: Any):
        row = original(*args, **kwargs)
        return replace(row, **{field: getattr(row, field) + D("0.01")})

    monkeypatch.setattr(module, "InstallmentDetails", corrupt)
    with pytest.raises(CalculationError) as caught:
        calculator.generate_amortization_schedule(loan(bank=bank))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "amount,remaining,payment", [("1000", 10, "1000"), ("10500", 1, "500")]
)
def test_whole_month_shortening_keeps_exact_months_and_one_final_payment(
    amount: str, remaining: int, payment: str
) -> None:
    from src.models import ShorteningPolicy

    params = loan(shortening_policy=ShorteningPolicy.WHOLE_MONTHS)
    schedule = calculator.generate_amortization_schedule(
        params,
        [Overpayment(D(amount), OverpaymentStrategy.SHORTEN_TERM, date(2026, 2, 15))],
    )
    assert schedule[0].contractual_months_remaining == remaining
    assert len(schedule) == remaining + 1
    assert schedule[1].total_installment == D(payment)
    assert sum(row.principal + row.overpayment for row in schedule) == D("12000")
