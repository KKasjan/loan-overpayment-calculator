from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def get_next_payment_dat(current_date: date, payment_day: int) -> date:
    """Sets the next installment due date in the next calendar month.
    Supports cases where the payment date does not occur in a given month
    (e.g., the 31st of the month and the following month is February or April).
    """

    # Moving on to the next month
    if current_date.month == 12:
        next_month = 1
        next_year = current_date.year + 1
    else:
        next_month = current_date.month + 1
        next_year = current_date.year

    # Attempts to set the desired payment day.
    # If the month is too short (e.g., February),
    # revert to the last day of that month.
    target_day = payment_day
    while target_day > 20:
        try:
            return date(next_year, next_month, target_day)
        except ValueError:
            target_day -= 1

    return date(next_year, next_month, target_day)


def calculate_daily_interest(
        balance: Decimal,
        annual_rate: Decimal,
        start_date: date,
        end_date: date,
) -> Decimal:
    """Calculates interest accrued between two dates, compounded daily.
    The formula takes into account the actual number of days in a year
    (365 or 366 for leap years), which allows it to replicate the mechanism
    used by companies such as ING.
    """
    total_interest = Decimal("0.0")

    # Day-by-day transition to properly handle the leap year turn
    current_day = start_date
    while current_day < end_date:
        # Checking if a year is a leap year
        # A year is a leap year if it is divisible by 4 and not divisible
        # by 100, # or if it is divisible by 400.
        year = current_day.year
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        days_in_year = Decimal("366") if is_leap else Decimal("365")

        # Interest for one specific day
        daily_rate = annual_rate / days_in_year
        total_interest += balance * daily_rate

        current_day += timedelta(days=1)

    # Round to 2 decimal places (up from half, like in a bank)
    return total_interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
