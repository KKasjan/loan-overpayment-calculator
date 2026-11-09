"""Independent numerical examples and invariants for the audit findings."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from src.calculator import (
    annuity_payment,
    calculate_daily_interest,
    calculate_simulation_summary,
    collection_date,
    generate_amortization_schedule,
    payment_dates,
)
from src.models import (
    DayCount,
    InstallmentMethod,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    RateChange,
    ShorteningPolicy,
    TermChange,
)
from src.scenarios import (
    build_overpayments,
    build_rate_changes,
    build_term_changes,
    percent_input,
)

D = Decimal


def loan(**kwargs) -> LoanParameters:
    return replace(
        LoanParameters(D("12000"), D("0"), date(2026, 1, 10), 10, 12), **kwargs
    )


def op(
    amount: str, when: date, strategy=OverpaymentStrategy.SHORTEN_TERM
) -> Overpayment:
    return Overpayment(D(amount), strategy, when)


@pytest.mark.parametrize(
    "value", [D("NaN"), D("Infinity"), D("-1"), D("0"), D("1.001")]
)
def test_invalid_principal_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        loan(amount=value)


@pytest.mark.parametrize("value", [D("NaN"), D("Infinity"), D("-0.1"), D("1.01")])
def test_invalid_rate_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        loan(annual_interest_rate=value)


@pytest.mark.parametrize("months", [0, -1, 421, 1.5, True])
def test_invalid_term_is_rejected(months) -> None:
    with pytest.raises(ValueError):
        loan(total_month=months)


def test_negative_mixed_allocation_is_rejected() -> None:
    with pytest.raises(ValueError):
        Overpayment(
            D("100"), OverpaymentStrategy.MIXED, date(2026, 2, 10), D("-100"), D("200")
        )


@pytest.mark.parametrize("day", [date(2026, 1, 9), date(2027, 2, 10)])
def test_out_of_range_overpayment_is_not_silently_dropped(day) -> None:
    with pytest.raises(ValueError):
        generate_amortization_schedule(loan(), [op("100", day)])


def test_start_date_payment_is_applied_and_prior_interest_is_not_lost() -> None:
    p = loan(accrued_interest=D("12.34"))
    s = generate_amortization_schedule(p, [op("12000", p.start_date)])
    assert len(s) == 1
    assert s[0].payment_date == p.start_date
    assert s[0].interest == D("12.34")
    assert s[0].total_installment == D("12.34")
    assert s[0].overpayment == D("12000")


def test_oversized_same_day_mixed_payment_is_capped_and_order_independent() -> None:
    p = loan()
    ops = [
        op("9000", date(2026, 1, 20)),
        op("9000", date(2026, 1, 20), OverpaymentStrategy.REDUCE_INSTALLMENT),
    ]
    a = calculate_simulation_summary(p, ops)
    b = calculate_simulation_summary(p, list(reversed(ops)))
    assert a.overpayment_schedule == b.overpayment_schedule
    assert a.total_overpayments_made == D("12000")
    assert a.unused_overpayments == D("6000")


def test_later_reduce_does_not_erase_previous_shortening() -> None:
    p = loan()
    s = generate_amortization_schedule(
        p,
        [
            op("2000", date(2026, 2, 10)),
            op("1000", date(2026, 3, 10), OverpaymentStrategy.REDUCE_INSTALLMENT),
        ],
    )
    assert s[2].total_installment == D("900.00")
    assert len(s) < 12


def test_whole_month_shortening_changes_term_and_payment() -> None:
    p = loan(shortening_policy=ShorteningPolicy.WHOLE_MONTHS)
    s = generate_amortization_schedule(p, [op("500", date(2026, 2, 10))])
    assert s[0].contractual_months_remaining == 10
    assert s[1].total_installment == D("1050.00")
    assert len(s) == 11


def test_separate_term_instruction_does_not_change_standard_scenario() -> None:
    p = loan(term_changes=(TermChange(date(2026, 2, 10), 10),))
    result = calculate_simulation_summary(p, [])
    assert len(result.standard_schedule) == 12
    assert len(result.overpayment_schedule) == 11
    assert result.overpayment_schedule[1].total_installment == D("1100")


def test_term_extension_and_non_due_instruction_are_rejected() -> None:
    for change in [
        TermChange(date(2026, 2, 10), 12),
        TermChange(date(2026, 2, 11), 10),
    ]:
        with pytest.raises(ValueError):
            calculate_simulation_summary(loan(term_changes=(change,)), [])


def test_rate_change_splits_daily_interest_at_effective_date() -> None:
    p = loan(
        amount=D("10000"),
        annual_interest_rate=D(".12"),
        rate_changes=(RateChange(date(2026, 1, 20), D(".06")),),
    )
    s = generate_amortization_schedule(p)
    # 10000 * (.12 * 10 + .06 * 21) / 365 = 67.397260...
    assert s[0].interest == D("67.40")
    assert (
        s[0].total_installment
        < generate_amortization_schedule(replace(p, rate_changes=()))[
            0
        ].total_installment
    )


def test_leap_year_conventions_and_cross_year_interest() -> None:
    a, b = date(2024, 2, 1), date(2024, 3, 1)
    assert calculate_daily_interest(D("10000"), D(".12"), a, b) == D("95.08")
    assert calculate_daily_interest(
        D("10000"), D(".12"), a, b, day_count=DayCount.ACTUAL_365
    ) == D("95.34")
    assert calculate_daily_interest(
        D("10000"), D(".12"), date(2023, 12, 31), date(2024, 1, 2)
    ) == D("6.57")
    with pytest.raises(ValueError):
        calculate_daily_interest(D("10000"), D(".12"), b, a)


def test_calendar_annuity_matches_independent_discount_factors() -> None:
    p = loan(
        amount=D("10000"),
        annual_interest_rate=D(".12"),
        total_month=3,
        installment_method=InstallmentMethod.CALENDAR,
    )
    discount = Fraction(1)
    pv = Fraction(0)
    for days in [31, 28, 31]:
        discount /= 1 + Fraction(12, 100) * Fraction(days, 365)
        pv += discount
    expected = D(10000) * D(pv.denominator) / D(pv.numerator)
    actual = annuity_payment(
        p.amount, p.annual_interest_rate, payment_dates(p), p.start_date, p
    )
    assert abs(actual - expected) <= D(".005")
    s = generate_amortization_schedule(p)
    assert abs(s[-1].total_installment - s[0].total_installment) <= D(".02")


@pytest.mark.parametrize("rate", ["0", ".075", ".20"])
@pytest.mark.parametrize("strategy", list(OverpaymentStrategy))
def test_long_schedule_reconciles_capital_interest_and_cash(rate, strategy) -> None:
    p = loan(
        amount=D("300000"),
        annual_interest_rate=D(rate),
        total_month=420,
        installment_method=InstallmentMethod.CALENDAR,
        start_date=date(2026, 2, 1),
        payment_day=28,
    )
    ops = build_overpayments(
        p,
        "regular",
        strategy,
        D("1000"),
        shorten=D("400") if strategy == OverpaymentStrategy.MIXED else None,
        reduce=D("600") if strategy == OverpaymentStrategy.MIXED else None,
    )
    s = generate_amortization_schedule(p, ops)
    assert all(
        r.principal >= 0 and r.interest >= 0 and r.remaining_balance >= 0 for r in s
    )
    assert sum((r.principal + r.overpayment for r in s), D(0)) == p.amount
    assert sum(
        (r.total_installment + r.overpayment for r in s), D(0)
    ) == p.amount + sum((r.interest for r in s), D(0))
    assert s[-1].remaining_balance == 0


def test_payment_dates_handle_same_month_first_payment_and_month_end() -> None:
    p = loan(start_date=date(2026, 1, 1))
    assert payment_dates(p)[0] == date(2026, 1, 10)
    dates = payment_dates(loan(payment_day=31, first_payment_date=date(2026, 1, 31)))
    assert dates[:3] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_collection_calendar_does_not_move_interest_dates() -> None:
    p = loan(shift_collection_dates=True)
    assert collection_date(date(2026, 5, 3), p) == date(2026, 5, 4)
    assert collection_date(date(2026, 12, 24), p) == date(2026, 12, 28)
    base = loan(start_date=date(2026, 4, 3), payment_day=3)
    a = generate_amortization_schedule(base)
    b = generate_amortization_schedule(replace(base, shift_collection_dates=True))
    assert a[0].payment_date == b[0].payment_date == date(2026, 5, 3)
    assert a[0].interest == b[0].interest
    assert b[0].collection_date == date(2026, 5, 4)


def test_fixed_period_rejects_early_changes_and_warns_about_future() -> None:
    end = date(2031, 1, 10)
    with pytest.raises(ValueError):
        loan(fixed_until=end, rate_changes=(RateChange(date(2030, 1, 10), D(".05")),))
    result = calculate_simulation_summary(loan(total_month=120, fixed_until=end), [])
    assert any("fixed_rate" in w for w in result.warnings)


def test_costs_are_separate_from_principal_and_interest() -> None:
    p = loan(upfront_cost=D("100"), monthly_cost=D("10"))
    result = calculate_simulation_summary(p, [op("12000", date(2026, 1, 20))])
    assert result.total_cost_standard == D("220")
    assert result.total_cost_overpaid == D("110")
    assert result.total_paid_standard == D("12220")
    assert result.total_paid_with_overpayments == D("12110")
    assert result.total_interest_saved == 0


def test_scenario_builders_parse_decimal_percent_and_irregular_rows() -> None:
    assert percent_input("7,51") == D(".0751")
    assert (
        len(
            build_overpayments(
                loan(),
                "single",
                OverpaymentStrategy.REDUCE_INSTALLMENT,
                D("1000"),
                month=12,
            )
        )
        == 1
    )
    assert (
        build_overpayments(
            loan(),
            "regular",
            OverpaymentStrategy.MIXED,
            D(0),
            shorten=D(0),
            reduce=D(0),
        )
        == []
    )
    rows = [
        {"date": "2026-01-20", "amount": "1000,50", "strategy": "REDUCE_INSTALLMENT"},
        {"date": "2026-02-20", "amount": "2000", "strategy": "SHORTEN_TERM"},
    ]
    result = build_overpayments(
        loan(), "irregular", OverpaymentStrategy.REDUCE_INSTALLMENT, D(0), rows=rows
    )
    assert [r.amount for r in result] == [D("1000.50"), D("2000")]
    assert build_rate_changes([{"date": "2026-02-20", "rate_percent": "7,51"}])[
        0
    ].annual_interest_rate == D(".0751")
    assert (
        build_term_changes([{"date": "2026-02-10", "remaining_months": 10.0}])[
            0
        ].remaining_months
        == 10
    )
    with pytest.raises(ValueError):
        build_term_changes([{"date": "2026-02-10", "remaining_months": 10.5}])


def test_upward_rate_change_reprices_payment_without_negative_principal() -> None:
    p = loan(
        amount=D("300000"),
        annual_interest_rate=D(".075"),
        total_month=360,
        installment_method=InstallmentMethod.CALENDAR,
        rate_changes=(RateChange(date(2026, 2, 15), D(".20")),),
    )
    s = generate_amortization_schedule(p)
    assert s[1].total_installment > s[0].total_installment
    assert all(row.principal >= 0 for row in s)
    assert s[-1].remaining_balance == 0
