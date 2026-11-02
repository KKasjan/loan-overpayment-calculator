"""ING workflow regressions, with independent zero-rate and daily-interest oracles.

These are model tests, not a claim of reproducing an individual bank contract.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.calculator import calculate_simulation_summary
from src.ing import LoanState, quote_payment, required_overpayment, simulate_ing
from src.models import (
    AnnexInstruction,
    DayCount,
    InstallmentMethod,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    RateChange,
    RepaymentModel,
)

D = Decimal


def parameters(**kwargs: Any) -> LoanParameters:
    values: dict[str, Any] = dict(
        amount=D("12000.00"),
        annual_interest_rate=D("0"),
        start_date=date(2026, 1, 15),
        payment_day=15,
        total_month=12,
        repayment_model=RepaymentModel.ING,
        installment_method=InstallmentMethod.CALENDAR,
    )
    values.update(kwargs)
    return LoanParameters(**values)


def op(when: date, amount: str = "300.00") -> Overpayment:
    return Overpayment(D(amount), OverpaymentStrategy.REDUCE_INSTALLMENT, when)


def test_overpayment_reduces_payment_without_changing_maturity() -> None:
    result = simulate_ing(parameters(), [op(date(2026, 1, 20))])
    assert len(result.schedule) == 12
    event = result.events[0]
    assert event.payment_before == D("1000.00")
    assert event.payment_after == D("975.00")
    assert event.remaining_months == 12
    assert event.maturity == date(2027, 1, 15)


def test_separate_midperiod_annex_can_raise_payment_for_one_whole_month() -> None:
    params = parameters(annexes=(AnnexInstruction(date(2026, 1, 21), D("1063.64")),))
    result = simulate_ing(params, [op(date(2026, 1, 20))])
    reduction, annex = result.events
    assert reduction.payment_after == D("975.00")
    assert annex.payment_before == D("975.00")
    assert annex.payment_after == D("1063.64")
    assert annex.remaining_months == 11
    assert len(result.schedule) == 11
    assert sum(r.principal + r.overpayment for r in result.schedule) == D("12000.00")


def test_limit_too_low_for_one_month_is_explicit_error() -> None:
    params = parameters(annexes=(AnnexInstruction(date(2026, 1, 21), D("1000")),))
    with pytest.raises(ValueError, match="nie wystarcza"):
        simulate_ing(params, [op(date(2026, 1, 20))])


def test_inverse_zero_interest_exact_minimum_and_one_cent_less() -> None:
    params = parameters()
    quote = required_overpayment(params, date(2026, 1, 20), 1, D("1000"))
    assert quote.overpayment == D("1000.00")
    assert quote.payment_after_annex == D("1000.00")
    assert quote.remaining_months == 11
    assert quote.maturity == date(2026, 12, 15)
    new = replace(params, annexes=(AnnexInstruction(quote.date, D("1000")),))
    assert (
        len(simulate_ing(new, [op(quote.date, str(quote.overpayment))]).schedule) == 11
    )
    with pytest.raises(ValueError, match="nie wystarcza"):
        simulate_ing(new, [op(quote.date, str(quote.overpayment - D("0.01")))])


def test_inverse_includes_existing_overpayment_and_can_need_zero() -> None:
    when = date(2026, 1, 20)
    assert required_overpayment(
        parameters(), when, 1, D("1000"), [op(when)]
    ).overpayment == D("700.00")
    assert required_overpayment(parameters(), when, 1, D("1100")).overpayment == D(
        "0.00"
    )


def test_daily_interest_independent_expected_segments_and_multiple_same_day() -> None:
    params = parameters(annual_interest_rate=D("0.12"), current_installment=D("1100"))
    result = simulate_ing(
        params, [op(date(2026, 1, 20), "100"), op(date(2026, 1, 20), "200")]
    )
    # 12000 * .12 * 5/365 + 11700 * .12 * 26/365, rounded once.
    assert result.schedule[0].interest == D("119.74")
    assert result.events[0].amount == D("300.00")
    assert simulate_ing(params, [op(date(2026, 1, 20))]).schedule == result.schedule


def test_due_day_order_regular_payment_then_overpayment_then_annex() -> None:
    when = date(2026, 2, 15)
    params = parameters(annexes=(AnnexInstruction(when, D("1100")),))
    result = simulate_ing(params, [op(when)])
    row = result.schedule[0]
    assert row.total_installment == D("1000")
    assert row.principal == D("1000")
    assert row.overpayment == D("300")
    assert row.remaining_balance == D("10700")
    assert result.events[0].payment_after == D("972.73")
    assert result.events[1].payment_after == D("1070")
    assert row.contractual_months_remaining == 10


def test_full_payoff_midperiod_caps_capital_and_settles_interest_once() -> None:
    params = parameters(annual_interest_rate=D("0.12"))
    result = simulate_ing(params, [op(date(2026, 1, 20), "20000")])
    assert len(result.schedule) == 1
    assert result.schedule[0].interest == D("19.73")
    assert result.schedule[0].overpayment == D("12000")
    assert result.schedule[0].payment_date == date(2026, 1, 20)
    summary = calculate_simulation_summary(params, [op(date(2026, 1, 20), "20000")])
    assert summary.unused_overpayments == D("8000")


def test_same_due_full_payoff_reconciles_cash() -> None:
    result = simulate_ing(
        parameters(monthly_cost=D("10")), [op(date(2026, 2, 15), "20000")]
    )
    assert len(result.schedule) == 1
    assert sum(r.additional_cost for r in result.schedule) == D("10")
    assert sum(r.principal + r.overpayment for r in result.schedule) == D("12000")
    assert sum(r.total_installment + r.overpayment for r in result.schedule) == D(
        "12000"
    )


@pytest.mark.parametrize("day_count", list(DayCount))
def test_leap_year_and_inverse_nonzero_rate_minimality(day_count: DayCount) -> None:
    params = parameters(
        start_date=date(2028, 1, 15),
        annual_interest_rate=D("0.075"),
        day_count=day_count,
    )
    when = date(2028, 2, 20)
    quote = required_overpayment(params, when, 1, D("1100"))
    state = simulate_ing(params, [], stop_date=when).state
    shorter = state.dates[:-1]
    assert quote_payment(
        replace(state, balance=state.balance - quote.overpayment), shorter, params
    ) <= D("1100")
    if quote.overpayment:
        assert quote_payment(
            replace(state, balance=state.balance - quote.overpayment + D("0.01")),
            shorter,
            params,
        ) > D("1100")


def test_earlier_overpayment_reduces_first_period_interest() -> None:
    params = parameters(annual_interest_rate=D("0.12"))
    early = simulate_ing(params, [op(date(2026, 1, 20))])
    later = simulate_ing(params, [op(date(2026, 1, 25))])
    assert early.schedule[0].interest < later.schedule[0].interest


def test_future_rate_change_not_used_in_today_quote() -> None:
    params = parameters(annual_interest_rate=D("0.05"))
    future = replace(params, rate_changes=(RateChange(date(2026, 6, 20), D("0.10")),))
    assert required_overpayment(
        params, params.start_date, 1, D("1100")
    ) == required_overpayment(future, params.start_date, 1, D("1100"))
    result = simulate_ing(future, [])
    assert any(e.kind == "Zmiana oprocentowania" for e in result.events)


@pytest.mark.parametrize("months,rate", [(360, "0.075"), (420, "0.20"), (3, "0")])
def test_long_schedule_principal_cash_and_payment_ceiling(
    months: int, rate: str
) -> None:
    params = parameters(
        total_month=months, annual_interest_rate=D(rate), amount=D("300000.00")
    )
    result = simulate_ing(params, [op(date(2026, 1, 20))])
    assert result.schedule[-1].remaining_balance == 0
    assert all(r.principal >= 0 for r in result.schedule)
    assert sum(r.principal + r.overpayment for r in result.schedule) == params.amount
    assert sum(
        r.total_installment + r.overpayment for r in result.schedule
    ) == params.amount + sum(r.interest for r in result.schedule)


def test_bank_bounds_validated_against_target_and_actual_candidate() -> None:
    with pytest.raises(ValueError, match="maksimum"):
        AnnexInstruction(date(2026, 1, 20), D("1100"), maximum_payment=D("1000"))
    params = parameters(
        annexes=(
            AnnexInstruction(date(2026, 1, 21), D("1100"), minimum_payment=D("1080")),
        )
    )
    with pytest.raises(ValueError, match="poniżej minimum"):
        simulate_ing(params, [op(date(2026, 1, 20))])


def test_invalid_strategies_dates_and_inverse_targets_are_rejected() -> None:
    params = parameters()
    with pytest.raises(ValueError, match="każda nadpłata"):
        simulate_ing(
            params,
            [
                Overpayment(
                    D("100"), OverpaymentStrategy.SHORTEN_TERM, params.start_date
                )
            ],
        )
    with pytest.raises(ValueError, match="zakresem"):
        simulate_ing(params, [op(date(2025, 1, 20))])
    with pytest.raises(ValueError, match="przynajmniej"):
        required_overpayment(params, params.start_date, 12, D("1000"))
    with pytest.raises(ValueError, match="dodatnią"):
        required_overpayment(params, params.start_date, 0, D("1000"))


def test_annex_applies_only_to_accelerated_summary() -> None:
    params = parameters(annexes=(AnnexInstruction(date(2026, 1, 21), D("1100")),))
    summary = calculate_simulation_summary(params, [op(date(2026, 1, 20))])
    assert len(summary.standard_schedule) == 12
    assert len(summary.overpayment_schedule) == 11


def test_quote_does_not_capitalize_accrued_interest() -> None:
    params = parameters()
    state = LoanState(
        params.start_date,
        D("12000"),
        D("100"),
        D("1000"),
        (date(2026, 2, 15), date(2026, 3, 15)),
    )
    assert quote_payment(state, state.dates, params) == D("6050")


@pytest.mark.parametrize("day", [10, 15, 31])
@pytest.mark.parametrize("rate", ["0", "0.075", "0.20"])
def test_repeated_overpayments_reprice_without_losing_prior_annex(
    day: int, rate: str
) -> None:
    from src.calculator import payment_dates

    params = parameters(
        amount=D("300000"),
        payment_day=day,
        total_month=336,
        annual_interest_rate=D(rate),
    )
    dates = payment_dates(params)
    baseline = simulate_ing(params, [])
    cap = baseline.schedule[0].total_installment + D("100")
    params = replace(params, annexes=(AnnexInstruction(dates[1], cap),))
    payments = [op(dates[0], "300"), op(dates[1], "300"), op(dates[2], "300")]
    result = simulate_ing(params, payments)
    annex = next(e for e in result.events if e.kind.startswith("Aneks"))
    last_op = result.events[-1]
    assert last_op.payment_after <= last_op.payment_before
    assert last_op.maturity == annex.maturity
    assert result.schedule[-1].remaining_balance == 0


def test_annex_builder_parses_optional_bounds() -> None:
    from src.scenarios import build_annexes

    result = build_annexes(
        [
            {
                "date": "2026-01-20",
                "target_payment": "1 100,00",
                "minimum_payment": None,
                "maximum_payment": float("nan"),
            }
        ]
    )
    assert result == (AnnexInstruction(date(2026, 1, 20), D("1100")),)


def test_confirmed_ing_balance_includes_accrued_interest() -> None:
    from src.scenarios import principal_from_balance

    principal = principal_from_balance(
        D("739933.42"), D("2346.13"), includes_interest=True
    )
    assert principal == D("737587.29")
    params = parameters(
        amount=principal,
        start_date=date(2026, 11, 2),
        total_month=336,
        payment_day=15,
        first_payment_date=date(2026, 11, 15),
        annual_interest_rate=D("0.0645"),
        accrued_interest=D("2346.13"),
        current_installment=D("4748.90"),
    )
    first = simulate_ing(params, []).schedule[0]
    assert first.total_installment == D("4748.90")
    assert first.interest == D("4040.56")
    assert first.principal == D("708.34")
    # Confirms interest settlement with supplied bank installment, not its derivation.
    assert first.remaining_balance == D("736878.95")


@pytest.mark.parametrize(
    "balance,interest", [("100", "100"), ("100", "101"), ("100", "-1")]
)
def test_invalid_total_balance_split_is_rejected(balance: str, interest: str) -> None:
    from src.scenarios import principal_from_balance

    with pytest.raises(ValueError):
        principal_from_balance(D(balance), D(interest), includes_interest=True)
