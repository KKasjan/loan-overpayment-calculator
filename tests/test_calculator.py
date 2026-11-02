from datetime import date
from decimal import Decimal
import pytest
from src.calculator import (
    get_next_payment_date,
    calculate_daily_interest,
    generate_amortization_schedule,
    calculate_simulation_summary,
)
from src.models import LoanParameters, Overpayment, OverpaymentStrategy


# Test 1 - standard month-to-month transition
def test_get_next_payment_date_standard() -> None:
    start = date(2026, 1, 10)
    assert get_next_payment_date(start, 10) == date(2026, 2, 10)


# Test 2 - switching to a shorter month (January 31 -> February)
def test_get_next_month_payment_short_month() -> None:
    start = date(2026, 1, 31)
    assert get_next_payment_date(start, 31) == date(2026, 2, 28)


# Test 3 - # Leap year interest calculation test
# (e.g., end of 2023 / beginning of 2024)
# Amount: PLN 100,000, Interest rate: 6% (0.06)
def test_calculate_daily_interest_leap_year() -> None:
    balance = Decimal("100000.00")
    rate = Decimal("0.06")

    # 3 days: December 30 (regular), December 31 (regular), January 1 (leap)
    start = date(2023, 12, 30)
    end = date(2024, 1, 2)

    # 2023: 2 days * (100,000 * 0.06 / 365) = 2 * 16.438,356 = 32.8767
    # 2024: 1 day * (100,000 * 0.06 / 366) = 1 * 16.393,442 = 16.3934
    # Total: 49.2701 -> rounded to 49.27
    expected_interest = Decimal("49.27")

    assert (
        calculate_daily_interest(
            balance,
            rate,
            start,
            end,
        )
        == expected_interest
    )


# Test 4 - Small loan simulation: PLN 10,000
# for 12 months, 8% interest rate
def test_generate_amortization_schedule_ends_at_zero() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0.08"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=12,
    )

    schedule = generate_amortization_schedule(params)

    # Checking if exactly 12 installments have been generated
    assert len(schedule) == 12
    # Checking whether exactly PLN 0 remains to be repaid
    # after the last installment
    assert schedule[-1].remaining_balance == Decimal("0.00")


@pytest.mark.parametrize(
    "shorten_day,reduce_day", [(15, 20), (20, 15), (20, 20), (10, 10)]
)
@pytest.mark.parametrize("use_mixed", [False, True])
def test_different_strategies_preserve_each_overpayment_allocation(
    shorten_day: int, reduce_day: int, use_mixed: bool
) -> None:
    params = LoanParameters(
        amount=Decimal("12000.00"),
        annual_interest_rate=Decimal("0"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=12,
    )
    overpayments = [
        Overpayment(
            amount=Decimal("2000.00") if use_mixed else Decimal("1000.00"),
            strategy=(
                OverpaymentStrategy.MIXED
                if use_mixed
                else OverpaymentStrategy.SHORTEN_TERM
            ),
            date=date(2026, 2 if shorten_day == 10 else 1, shorten_day),
            amount_shorten=Decimal("1000.00") if use_mixed else None,
            amount_reduce=Decimal("1000.00") if use_mixed else None,
        ),
        Overpayment(
            amount=Decimal("1000.00") if use_mixed else Decimal("2000.00"),
            strategy=OverpaymentStrategy.REDUCE_INSTALLMENT,
            date=date(2026, 2 if reduce_day == 10 else 1, reduce_day),
        ),
    ]
    schedule = generate_amortization_schedule(params, overpayments)
    assert schedule == generate_amortization_schedule(
        params, list(reversed(overpayments))
    )
    assert schedule[0].remaining_balance == Decimal("8000.00")
    assert schedule[0].overpayment == Decimal("3000.00")
    # Only 2000 reduces the next installment: (11000 - 2000) / 11.
    assert schedule[1].total_installment == Decimal("818.18")
    assert len(schedule) < 12
    assert schedule[-1].remaining_balance == Decimal("0.00")
    assert (
        sum((row.principal + row.overpayment for row in schedule), Decimal("0.00"))
        == params.amount
    )


# Test 5 - Loan: PLN 100,000, 60 months (5 years), 8%
def test_overpayment_short_term() -> None:
    params = LoanParameters(
        amount=Decimal("100000.00"),
        annual_interest_rate=Decimal("0.08"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=60,
    )

    # Adds a huge one-time overpayment of PLN 30,000 in the 5th month (in May)
    overpayments = [
        Overpayment(
            amount=Decimal("30000.00"),
            strategy=OverpaymentStrategy.SHORTEN_TERM,
            date=date(2026, 5, 10),
        )
    ]

    schedule = generate_amortization_schedule(params, overpayments)

    # With such a large overpayment, the loan should end MUCH
    # earlier than in the 60th month
    assert len(schedule) < 60
    assert schedule[-1].remaining_balance == Decimal("0.00")


# Test 6 - Loan: PLN 100,000, 60 months (5 years), 8%
def test_overpayment_reduce_installment() -> None:
    params = LoanParameters(
        amount=Decimal("100000.00"),
        annual_interest_rate=Decimal("0.08"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=60,
    )

    # Overpayment of PLN 30,000 in the 5th month,
    # but I want to reduce the installment
    overpayments = [
        Overpayment(
            amount=Decimal("30000.00"),
            strategy=OverpaymentStrategy.REDUCE_INSTALLMENT,
            date=date(2026, 5, 10),
        )
    ]

    schedule = generate_amortization_schedule(params, overpayments)

    # The installment in the 4th month (before the overpayment)
    # should be higher than the installment in the 7th month
    # (after the overpayment)
    installment_before = schedule[3].total_installment
    installment_after = schedule[6].total_installment
    assert installment_after < installment_before


# Test 7 - Simulation summary
def test_simulation_summary_calculation() -> None:
    params = LoanParameters(
        amount=Decimal("100000.00"),
        annual_interest_rate=Decimal("0.08"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=60,
    )

    overpayments = [
        Overpayment(
            amount=Decimal("30000.00"),
            strategy=OverpaymentStrategy.SHORTEN_TERM,
            date=date(2026, 2, 10),
        )
    ]

    summary = calculate_simulation_summary(params, overpayments)
    assert summary.total_interest_saved > Decimal("0.00")
    assert summary.months_saved > 0
    assert summary.total_overpayments_made == Decimal("30000.00")


# Test 8
def test_last_installment_clears_rounding_remainder() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=3,
    )

    schedule = generate_amortization_schedule(params)

    assert len(schedule) == 3
    assert schedule[0].total_installment == Decimal("3333.33")
    assert schedule[1].total_installment == Decimal("3333.33")
    assert schedule[2].total_installment == Decimal("3333.34")
    assert schedule[-1].remaining_balance == Decimal("0.00")

    total_principal = sum(
        (installment.principal for installment in schedule), Decimal("0.00")
    )
    assert total_principal == params.amount


# Test 9
def test_last_installment_clears_principal_and_interest() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0.12"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=3,
    )

    schedule = generate_amortization_schedule(params)

    assert len(schedule) == 3

    previous_balance = schedule[-2].remaining_balance
    last_installment = schedule[-1]

    assert last_installment.interest > Decimal("0.00")
    assert last_installment.principal == previous_balance
    assert (
        last_installment.total_installment
        == previous_balance + last_installment.interest
    )
    assert last_installment.remaining_balance == Decimal("0.00")

    total_principal = sum(
        (installment.principal for installment in schedule), Decimal("0.00")
    )
    assert total_principal == params.amount


# Test 10
def test_mid_period_overpayment_reduces_current_period_interest() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0.12"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=12,
    )

    overpayment = Overpayment(
        amount=Decimal("1000.00"),
        strategy=OverpaymentStrategy.SHORTEN_TERM,
        date=date(2026, 1, 20),
    )

    schedule = generate_amortization_schedule(
        params,
        overpayments=[overpayment],
    )

    first_installment = schedule[0]

    assert first_installment.payment_date == date(2026, 2, 10)
    assert first_installment.interest == Decimal("95.01")
    assert first_installment.overpayment == Decimal("1000.00")


def test_mid_period_full_principal_repayment_stops_interest() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0.12"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=12,
    )
    overpayment = Overpayment(
        amount=Decimal("10000.00"),
        strategy=OverpaymentStrategy.SHORTEN_TERM,
        date=date(2026, 1, 20),
    )

    # A later planned overpayment must not move the settlement date or be paid.
    later_overpayment = Overpayment(
        amount=Decimal("1000.00"),
        strategy=OverpaymentStrategy.SHORTEN_TERM,
        date=date(2026, 1, 25),
    )
    summary = calculate_simulation_summary(params, [later_overpayment, overpayment])
    schedule = summary.overpayment_schedule

    assert len(schedule) == 1
    settlement = schedule[0]
    assert settlement.payment_date == date(2026, 1, 20)
    assert settlement.days_in_period == 10
    # 10000 * 0.12 * 10 / 365, rounded once to cents.
    assert settlement.interest == Decimal("32.88")
    assert settlement.overpayment == params.amount
    assert settlement.principal == Decimal("0.00")
    assert settlement.total_installment == Decimal("32.88")
    assert settlement.remaining_balance == Decimal("0.00")

    total_principal = sum(
        (row.principal + row.overpayment for row in schedule),
        Decimal("0.00"),
    )
    assert total_principal == params.amount
    assert summary.total_overpayments_made == params.amount
    assert summary.total_paid_with_overpayments == Decimal("10032.88")


def test_multiple_overpayments_in_one_period_follow_actual_dates() -> None:
    params = LoanParameters(
        amount=Decimal("10000.00"),
        annual_interest_rate=Decimal("0.12"),
        start_date=date(2026, 1, 10),
        payment_day=10,
        total_month=12,
    )
    overpayments = [
        Overpayment(
            amount=Decimal("1000.00"),
            strategy=OverpaymentStrategy.SHORTEN_TERM,
            date=date(2026, 1, 15),
        ),
        Overpayment(
            amount=Decimal("2000.00"),
            strategy=OverpaymentStrategy.SHORTEN_TERM,
            date=date(2026, 1, 20),
        ),
    ]

    schedule = generate_amortization_schedule(params, overpayments)
    reversed_schedule = generate_amortization_schedule(
        params, list(reversed(overpayments))
    )

    first_installment = schedule[0]
    assert first_installment.payment_date == date(2026, 2, 10)
    assert first_installment.days_in_period == 31
    # (10000 * 5 + 9000 * 5 + 7000 * 21) * 0.12 / 365 = 79.561643...
    assert first_installment.interest == Decimal("79.56")
    assert first_installment.overpayment == Decimal("3000.00")
    assert first_installment.total_installment == Decimal("888.49")
    assert first_installment.principal == Decimal("808.93")
    assert first_installment.remaining_balance == Decimal("6191.07")

    assert schedule == reversed_schedule
    assert sum((row.overpayment for row in schedule), Decimal("0.00")) == Decimal(
        "3000.00"
    )
    assert (
        sum(
            (row.principal + row.overpayment for row in schedule),
            Decimal("0.00"),
        )
        == params.amount
    )
    assert schedule[-1].remaining_balance == Decimal("0.00")
