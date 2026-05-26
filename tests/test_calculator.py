from datetime import date
from decimal import Decimal
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
