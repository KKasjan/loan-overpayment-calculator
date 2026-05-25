from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from src.models import (
    LoanParameters,
    InstallmentDetails,
    Overpayment,
    OverpaymentStrategy,
    SimulationSummary,
)


def get_next_payment_date(current_date: date, payment_day: int) -> date:
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


def generate_amortization_schedule(
        params: LoanParameters,
        overpayments: Optional[List[Overpayment]] = None
) -> List[InstallmentDetails]:
    """
    Generates an amortization schedule, optionally including overpayments,
    supporting daily interest compounding.
    """
    if overpayments is None:
        overpayments = []

    schedule: List[InstallmentDetails] = []
    current_balance = params.amount
    current_date = params.start_date
    months_left = params.total_month

    # Initial base installment calculation
    monthly_rate = params.annual_interest_rate / Decimal("12")
    if monthly_rate > 0:
        base_installment = (
            current_balance
            * (monthly_rate * (1 + monthly_rate) ** months_left)
            / ((1 + monthly_rate) ** months_left - 1)
        )
    else:
        base_installment = current_balance / months_left

    base_installment = base_installment.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    for i in range(1, params.total_month + 1):
        if current_balance <= 0:
            break

        # 1. Set a due date for your next installment
        next_date = get_next_payment_date(current_date, params.payment_day)
        days_in_period = (next_date - current_date).days

        # 2. Calculate interest accrued for this period
        interest = calculate_daily_interest(
            current_balance,
            params.annual_interest_rate,
            current_date,
            next_date,
        )

        # 3. Check if there's an overpayment scheduled for this
        # installment period. Look for overpayments that happen
        # between current_date (exclusive) and next
        period_overpayments = [
            op for op in overpayments if current_date < op.date <= next_date
        ]
        total_period_overpayment = sum(op.amount for op in period_overpayments)

        # 3. Calculate standard installment components
        if current_balance + interest < base_installment:
            # Final installment – ​​pays exactly what is left
            total_installment = current_balance + interest
            principal = current_balance
        else:
            total_installment = base_installment
            principal = total_installment - interest

        # Apply standard payment and overpayment to the balance
        current_balance -= principal

        # 4. Handle overpayment logic if it exists
        applied_overpayment = Decimal("0.00")
        if total_period_overpayment > 0 and current_balance > 0:
            # Can't overpay more than the remaining balance
            if total_period_overpayment >= current_balance:
                applied_overpayment = current_balance
                current_balance = Decimal("0.00")
            else:
                applied_overpayment = total_period_overpayment
                current_balance -= applied_overpayment

            # Apply strategies re-calculation based on the LAST overpayment
            # in this period
            last_strategy = period_overpayments[-1].strategy
            months_left_after_this = params.total_month - i

            if (
                last_strategy == OverpaymentStrategy.REDUCE_INSTALLMENT
                and current_balance > 0
                and months_left_after_this > 0
            ):
                # Recalculate base installment for the remaining
                # term but lower balance
                if monthly_rate > 0:
                    base_installment = (
                       current_balance
                       * (monthly_rate * (1 + monthly_rate)
                          ** months_left_after_this)
                       / ((1 + monthly_rate) ** months_left_after_this - 1)
                    )
                else:
                    base_installment = current_balance / months_left_after_this

                base_installment = base_installment.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                # For SHORTEN_TERM, we do nothing to the base_installment.
                # The loop will just naturally end earlier because
                # current_balance drops to 0 sooner.

        # 5. Saves installment details
        schedule.append(
            InstallmentDetails(
                installment_number=i,
                payment_date=next_date,
                days_in_period=days_in_period,
                total_installment=total_installment,
                principal=principal,
                interest=interest,
                overpayment=applied_overpayment,
                remaining_balance=current_balance.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
        )

        # Move the time indicator to the next month
        current_date = next_date

    return schedule


def calculate_simulation_summary(
        params: LoanParameters, overpayments: List[Overpayment]
) -> SimulationSummary:
    """Compares the standard loan schedule against the overpaid schedule.

    Returns financial benefits and savings metrics.
    """
    standard_schedule = generate_amortization_schedule(
        params,
        overpayments=None
    )
    overpaid_schedule = generate_amortization_schedule(params, overpayments)

    total_interest_standard = sum(r.interest for r in standard_schedule)
    total_paid_standard = sum(r.total_installment for r in standard_schedule)

    total_interest_overpaid = sum(r.interest for r in overpaid_schedule)
    total_overpayments = sum(r.overpayment for r in overpaid_schedule)
    total_paid_with_overpayments = (
        sum(r.total_installment for r in overpaid_schedule)
        + total_overpayments
    )

    interest_saved = total_interest_standard - total_interest_overpaid
    months_saved = len(standard_schedule) - len(overpaid_schedule)

    return SimulationSummary(
        total_paid_standard=total_paid_standard.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        total_paid_with_overpayments=total_paid_with_overpayments.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        total_interest_saved=interest_saved.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        months_saved=months_saved,
        total_overpayments_made=total_overpayments.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        standard_schedule=standard_schedule,
        overpayment_schedule=overpaid_schedule
    )
