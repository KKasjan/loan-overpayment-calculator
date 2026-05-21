from datetime import date
from decimal import Decimal
from src.calculator import get_next_payment_dat, calculate_daily_interest


# Test 1 - standard month-to-month transition
def test_get_next_payment_date_standard() -> None:
    start = date(2026, 1, 10)
    assert get_next_payment_dat(start, 10) == date(2026, 2, 10)


# Test 2 - switching to a shorter month (January 31 -> February)
def test_get_next_month_payment_short_month() -> None:
    start = date(2026, 1, 31)
    assert get_next_payment_dat(start, 31) == date(2026, 2, 28)


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

    assert calculate_daily_interest(
        balance,
        rate,
        start,
        end,
    ) == expected_interest
