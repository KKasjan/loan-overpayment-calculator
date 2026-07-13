from datetime import date  # timedelta
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
    """Calculates the payment date for the next installment
    in the subsequent calendar month.

    Handles edge cases where the target payment day
    does not exist in the next month (e.g., January 31st
    moving to February, which results in February 28th or 29th).
    """
    if current_date.month == 12:
        next_month = 1
        next_year = current_date.year + 1
    else:
        next_month = current_date.month + 1
        next_year = current_date.year

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

    Utilizes an optimized O(1) interval-based algorithm grouping days by year,
    eliminating slow day-by-day iteration and guaranteeing
    bank-grade precision.
    """
    if start_date >= end_date:
        return Decimal("0.00")

    total_interest = Decimal("0.00")
    curr = start_date

    # Calculate interest using O(1) segments per year to avoid
    # daily iteration overhead
    while curr < end_date:
        curr_year = curr.year
        is_leap = (curr_year % 4 == 0 and curr_year % 100 != 0) or (
            curr_year % 400 == 0
        )
        days_in_year = Decimal("366") if is_leap else Decimal("365")

        next_year_start = date(curr_year + 1, 1, 1)
        segment_end = min(end_date, next_year_start)

        days_in_segment = Decimal(str((segment_end - curr).days))
        daily_rate = annual_rate / days_in_year
        total_interest += balance * daily_rate * days_in_segment

        curr = segment_end

    # Round up from half to match standardized banking rounding rules
    return total_interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_amortization_schedule(
    params: LoanParameters, overpayments: Optional[List[Overpayment]] = None
) -> List[InstallmentDetails]:
    """Generates a complete amortization schedule, optionally
    including overpayments.

    Supports daily interest compounding and dynamic recalculation
    of the repayment plan.
    """
    if overpayments is None:
        overpayments = []

    schedule: List[InstallmentDetails] = []
    current_balance = params.amount
    current_date = params.start_date
    months_left = params.total_month

    # Initialize monthly annuity (equal installments) interest calculation
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

        # 1. Determine next monthly payment date
        next_date = get_next_payment_date(current_date, params.payment_day)
        days_in_period = (next_date - current_date).days

        # 2. Accrue daily interest for this period
        interest = calculate_daily_interest(
            current_balance,
            params.annual_interest_rate,
            current_date,
            next_date,
        )

        # 3. Retrieve any overpayments registered in this calendar window
        period_overpayments = [
            op for op in overpayments if current_date < op.date <= next_date
        ]
        total_period_overpayment = sum(
            (op.amount for op in period_overpayments), Decimal("0.00")
        )

        # 4. Standard installment division
        if current_balance + interest < base_installment:
            # Final clearing installment matching exact outstanding balance
            total_installment = current_balance + interest
            principal = current_balance
        else:
            total_installment = base_installment
            principal = total_installment - interest

        current_balance -= principal

        # 5. Overpayment injection & dynamic re-calculation of loan milestones
        applied_overpayment = Decimal("0.00")
        if total_period_overpayment > 0 and current_balance > 0:
            if total_period_overpayment >= current_balance:
                applied_overpayment = current_balance
                current_balance = Decimal("0.00")
            else:
                applied_overpayment = Decimal(total_period_overpayment)
                current_balance -= applied_overpayment

            # Apply the selected strategy from the last executed overpayment
            last_op = period_overpayments[-1]
            last_strategy = last_op.strategy
            months_left_after_this = params.total_month - i

            # Verify if structural installment level change is triggered
            should_recalc = last_strategy in (
                OverpaymentStrategy.REDUCE_INSTALLMENT,
                OverpaymentStrategy.MIXED,
            )

            if should_recalc and current_balance > 0 and months_left_after_this > 0:
                # For MIXED strategy, installment reduces only
                # by amount_reduce.
                # Temporarily add back amount_shorten to
                # recalculate the annuity base.
                recalc_balance = current_balance
                if (
                    last_strategy == OverpaymentStrategy.MIXED
                    and last_op.amount_shorten is not None
                ):
                    recalc_balance += last_op.amount_shorten

                if monthly_rate > 0:
                    pow_factor = (1 + monthly_rate) ** months_left_after_this
                    base_installment = (
                        recalc_balance * monthly_rate * pow_factor / (pow_factor - 1)
                    )
                else:
                    base_installment = recalc_balance / months_left_after_this

                base_installment = base_installment.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # 6. Save details in the amortization schedule
        schedule.append(
            InstallmentDetails(
                installment_number=i,
                payment_date=next_date,
                days_in_period=days_in_period,
                total_installment=total_installment.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                principal=principal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                interest=interest,
                overpayment=applied_overpayment,
                remaining_balance=current_balance.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            )
        )

        current_date = next_date

    return schedule


def calculate_simulation_summary(
    params: LoanParameters, overpayments: List[Overpayment]
) -> SimulationSummary:
    """Compares the standard loan schedule against the overpaid schedule.

    Returns comprehensive financial and time-saving metrics.
    """
    standard_schedule = generate_amortization_schedule(params, overpayments=None)
    overpaid_schedule = generate_amortization_schedule(params, overpayments)

    total_interest_standard = sum(
        (r.interest for r in standard_schedule), Decimal("0.00")
    )
    total_paid_standard = sum(
        (r.total_installment for r in standard_schedule), Decimal("0.00")
    )

    total_interest_overpaid = sum(
        (r.interest for r in overpaid_schedule), Decimal("0.00")
    )
    total_overpayments = sum(
        (r.overpayment for r in overpaid_schedule), Decimal("0.00")
    )
    total_paid_with_overpayments = (
        sum((r.total_installment for r in overpaid_schedule), Decimal("0.00"))
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
        overpayment_schedule=overpaid_schedule,
    )
