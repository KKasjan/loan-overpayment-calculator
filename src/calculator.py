"""Daily simple interest and dated repayment events; no daily capitalization."""

from calendar import isleap, monthrange
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from src.models import (
    DayCount,
    InstallmentDetails,
    InstallmentMethod,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    ShorteningPolicy,
    SimulationSummary,
    validate_money,
    validate_rate,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def get_next_payment_date(current_date: date, payment_day: int) -> date:
    """Next calendar month, clamping the original requested day to month end."""
    if (
        not isinstance(payment_day, int) or isinstance(payment_day, bool)
    ) or not 1 <= payment_day <= 31:
        raise ValueError("Payment day must be between 1 and 31.")
    year, month = current_date.year, current_date.month + 1
    if month == 13:
        year, month = year + 1, 1
    return date(year, month, min(payment_day, monthrange(year, month)[1]))


def payment_dates(params: LoanParameters) -> list[date]:
    first = params.first_payment_date
    if first is None:
        candidate = date(
            params.start_date.year,
            params.start_date.month,
            min(
                params.payment_day,
                monthrange(params.start_date.year, params.start_date.month)[1],
            ),
        )
        first = (
            candidate
            if candidate > params.start_date
            else get_next_payment_date(params.start_date, params.payment_day)
        )
    dates = [first]
    for _ in range(params.total_month - 1):
        dates.append(get_next_payment_date(dates[-1], params.payment_day))
    return dates


def calculate_daily_interest(
    balance: Decimal,
    annual_rate: Decimal,
    start_date: date,
    end_date: date,
    *,
    round_result: bool = True,
    day_count: DayCount = DayCount.ACTUAL_ACTUAL,
) -> Decimal:
    """Simple interest on [start, end); round once per settlement if requested."""
    validate_money(balance, "Interest principal")
    validate_rate(annual_rate)
    if end_date < start_date:
        raise ValueError("Interest period ends before it starts.")
    total = ZERO
    current = start_date
    while current < end_date:
        end = min(end_date, date(current.year + 1, 1, 1))
        denominator = (
            366 if day_count == DayCount.ACTUAL_ACTUAL and isleap(current.year) else 365
        )
        total += (
            balance * annual_rate * Decimal((end - current).days) / Decimal(denominator)
        )
        current = end
    return money(total) if round_result else total


def rate_on(params: LoanParameters, when: date) -> Decimal:
    rate = params.annual_interest_rate
    for change in sorted(params.rate_changes, key=lambda c: c.date):
        if change.date <= when:
            rate = change.annual_interest_rate
    return rate


def period_interest(
    params: LoanParameters, balance: Decimal, start: date, end: date
) -> Decimal:
    points = sorted(
        {start, end} | {c.date for c in params.rate_changes if start < c.date < end}
    )
    return sum(
        (
            calculate_daily_interest(
                balance,
                rate_on(params, a),
                a,
                b,
                round_result=False,
                day_count=params.day_count,
            )
            for a, b in zip(points, points[1:])
        ),
        ZERO,
    )


def annuity_payment(
    balance: Decimal,
    rate: Decimal,
    dates: list[date],
    start: date,
    params: LoanParameters,
) -> Decimal:
    """Level payment at the current rate; future rate changes are not forecasts."""
    if not dates:
        return ZERO
    if params.installment_method == InstallmentMethod.MONTHLY:
        monthly = rate / Decimal(12)
        if monthly == 0:
            return max(CENT, money(balance / len(dates)))
        factor = (1 + monthly) ** len(dates)
        return max(CENT, money(balance * monthly * factor / (factor - 1)))
    discount = Decimal(1)
    discounted_payments = ZERO
    largest_period_growth = ZERO
    previous = start
    for due in dates:
        growth = calculate_daily_interest(
            Decimal("1.00"),
            rate,
            previous,
            due,
            round_result=False,
            day_count=params.day_count,
        )
        largest_period_growth = max(largest_period_growth, growth)
        discount /= 1 + growth
        discounted_payments += discount
        previous = due
    return max(
        CENT,
        money(balance / discounted_payments),
        money(balance * largest_period_growth) + CENT,
    )


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    weekday_correction = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday_correction) // 451
    n = h + weekday_correction - 7 * m + 114
    return date(year, n // 31, n % 31 + 1)


def _reprice_settlement(
    balance: Decimal,
    interest: Decimal,
    rate: Decimal,
    future_dates: list[date],
    due: date,
    params: LoanParameters,
) -> Decimal:
    """Reprice the current payment using already accrued interest, without forecasting rates."""
    discounted_payments = Decimal(1)
    discount = Decimal(1)
    largest_growth = ZERO
    previous = due
    for future in future_dates:
        growth = (
            rate / 12
            if params.installment_method == InstallmentMethod.MONTHLY
            else calculate_daily_interest(
                Decimal("1.00"),
                rate,
                previous,
                future,
                round_result=False,
                day_count=params.day_count,
            )
        )
        largest_growth = max(largest_growth, growth)
        discount /= 1 + growth
        discounted_payments += discount
        previous = future
    return max(
        CENT,
        money((balance + interest) / discounted_payments),
        interest + CENT,
        money(balance * largest_growth) + CENT,
    )


def collection_date(due: date, params: LoanParameters) -> date:
    """Collection calendar only; it does not silently move interest due dates."""
    if not params.shift_collection_dates:
        return due
    result = due
    while True:
        easter = _easter(result.year)
        holidays = {
            (1, 1),
            (1, 6),
            (5, 1),
            (5, 3),
            (8, 15),
            (11, 1),
            (11, 11),
            (12, 25),
            (12, 26),
        }
        if result.year >= 2025:
            holidays.add((12, 24))
        public = (result.month, result.day) in holidays or result in {
            easter,
            easter + timedelta(days=1),
            easter + timedelta(days=49),
            easter + timedelta(days=60),
        }
        if (
            result.weekday() != 6
            and not public
            and result not in params.additional_holidays
        ):
            return result
        result += timedelta(days=1)
        # After a Sunday/holiday, collection is on a working (Mon-Fri) day.
        while result.weekday() >= 5:
            result += timedelta(days=1)


def _allocations(
    ops: list[Overpayment], balance: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Same-day instructions share a capped payment proportionally, independent of list order."""
    requested = sum((op.amount for op in ops), ZERO)
    applied = min(balance, requested)
    if not requested:
        return ZERO, ZERO, ZERO
    shortening = sum(
        (
            op.amount
            if op.strategy == OverpaymentStrategy.SHORTEN_TERM
            else (op.amount_shorten or ZERO)
            if op.strategy == OverpaymentStrategy.MIXED
            else ZERO
            for op in ops
        ),
        ZERO,
    )
    shorten = money(applied * shortening / requested)
    return applied, shorten, applied - shorten


def _remaining_count(
    balance: Decimal,
    payment: Decimal,
    dates: list[date],
    start: date,
    params: LoanParameters,
    rate: Decimal,
) -> tuple[int, Decimal]:
    for count, due in enumerate(dates, 1):
        interest = calculate_daily_interest(
            balance, rate, start, due, day_count=params.day_count
        )
        if balance + interest <= payment:
            return count, balance + interest
        if payment <= interest:
            raise ValueError(
                "Installment does not cover interest; choose calendar annuity or a higher payment."
            )
        balance -= payment - interest
        start = due
    return len(dates), balance


def generate_amortization_schedule(
    params: LoanParameters, overpayments: list[Overpayment] | None = None
) -> list[InstallmentDetails]:
    dates = payment_dates(params)
    ops = sorted(overpayments or [], key=lambda op: op.date)
    for op in ops:
        if not params.start_date <= op.date <= dates[-1]:
            raise ValueError("Overpayment is outside the simulation date range.")
    for change in params.rate_changes:
        if change.date > dates[-1]:
            raise ValueError("Rate change is outside the simulation date range.")
    for instruction in params.term_changes:
        if instruction.date not in dates[:-1]:
            raise ValueError(
                "Term instruction must follow a contractual installment before maturity."
            )
    balance, current = params.amount, params.start_date
    horizon = len(dates)
    current_rate = rate_on(params, current)
    payment = params.current_installment or annuity_payment(
        balance, current_rate, dates, current, params
    )
    schedule: list[InstallmentDetails] = []
    previous_shortening = False
    for index, due in enumerate(dates):
        if balance == 0 or index >= horizon:
            break
        opening_balance = balance
        interest = params.accrued_interest if index == 0 else ZERO
        applied = shorten = reduce = ZERO
        end = due
        period_ops = [
            op
            for op in ops
            if (current <= op.date if index == 0 else current < op.date)
            and op.date <= due
        ]
        cursor = current
        for event_date in sorted({op.date for op in period_ops if op.date < due}):
            interest += period_interest(params, balance, cursor, event_date)
            paid, short_part, reduce_part = _allocations(
                [op for op in period_ops if op.date == event_date], balance
            )
            balance -= paid
            applied += paid
            shorten += short_part
            reduce += reduce_part
            cursor = event_date
            if balance == 0:
                end = event_date
                break
        interest = money(interest + period_interest(params, balance, cursor, end))
        new_rate = rate_on(params, end)
        if balance and new_rate != current_rate:
            if previous_shortening:
                count, _ = _remaining_count(
                    opening_balance,
                    payment,
                    dates[index:horizon],
                    current,
                    params,
                    current_rate,
                )
                horizon = min(horizon, index + count)
            payment = _reprice_settlement(
                balance,
                interest,
                new_rate,
                dates[index + 1 : horizon],
                due,
                params,
            )
        if balance == 0 or index == horizon - 1 or balance + interest <= payment:
            principal = balance
            installment = balance + interest
        else:
            if payment <= interest:
                raise ValueError(
                    "Installment does not cover interest. Use calendar annuity or increase the current installment."
                )
            installment = payment
            principal = installment - interest
        balance -= principal
        paid, short_part, reduce_part = _allocations(
            [op for op in period_ops if op.date == due], balance
        )
        balance -= paid
        applied += paid
        shorten += short_part
        reduce += reduce_part
        remaining = dates[index + 1 : horizon]
        if balance and remaining:
            if shorten and params.shortening_policy == ShorteningPolicy.WHOLE_MONTHS:
                count, final = _remaining_count(
                    balance + reduce, payment, remaining, due, params, new_rate
                )
                # Floor the fractional term: a small increase in the payment is possible.
                if final < payment and count > 1:
                    count -= 1
                horizon = min(horizon, index + 1 + count)
                remaining = dates[index + 1 : horizon]
                payment = annuity_payment(balance, new_rate, remaining, due, params)
            elif reduce:
                # Subtract only the reduction allocation: earlier shortening is retained.
                payment = max(
                    CENT,
                    payment - annuity_payment(reduce, new_rate, remaining, due, params),
                )
            for instruction in params.term_changes:
                if instruction.date == due:
                    if instruction.remaining_months > len(remaining):
                        raise ValueError(
                            "Term instruction may only shorten the remaining contractual term."
                        )
                    horizon = index + 1 + instruction.remaining_months
                    remaining = dates[index + 1 : horizon]
                    payment = annuity_payment(balance, new_rate, remaining, due, params)
        current_rate = new_rate
        previous_shortening = previous_shortening or shorten > 0
        cost = money(
            params.monthly_cost
            + opening_balance * params.annual_balance_insurance_rate / 12
        )
        schedule.append(
            InstallmentDetails(
                installment_number=index + 1,
                payment_date=end,
                days_in_period=(end - current).days,
                total_installment=money(installment),
                principal=money(principal),
                interest=interest,
                overpayment=money(applied),
                remaining_balance=money(balance),
                collection_date=collection_date(end, params),
                annual_interest_rate=new_rate,
                additional_cost=cost,
                contractual_months_remaining=max(0, horizon - index - 1)
                if balance
                else 0,
            )
        )
        current = end
    if not schedule or schedule[-1].remaining_balance != 0:
        raise ArithmeticError("Schedule ended with outstanding principal.")
    capital = sum((r.principal + r.overpayment for r in schedule), ZERO)
    if capital != params.amount:
        raise ArithmeticError("Principal reconciliation failed.")
    cash = sum((r.total_installment + r.overpayment for r in schedule), ZERO)
    if cash != params.amount + sum((r.interest for r in schedule), ZERO):
        raise ArithmeticError("Payment and interest reconciliation failed.")
    return schedule


def calculate_simulation_summary(
    params: LoanParameters, overpayments: list[Overpayment]
) -> SimulationSummary:
    # Formal term instructions belong only to the accelerated scenario.
    standard = generate_amortization_schedule(replace(params, term_changes=()), [])
    overpaid = generate_amortization_schedule(params, overpayments)
    standard_interest = sum((r.interest for r in standard), ZERO)
    overpaid_interest = sum((r.interest for r in overpaid), ZERO)
    standard_cost = params.upfront_cost + sum(
        (r.additional_cost for r in standard), ZERO
    )
    overpaid_cost = params.upfront_cost + sum(
        (r.additional_cost for r in overpaid), ZERO
    )
    made = sum((r.overpayment for r in overpaid), ZERO)
    requested = sum((op.amount for op in overpayments), ZERO)
    warnings = [
        "Simulation assumptions require reconciliation with your ING contract and bank schedule."
    ]
    if params.fixed_until and dates_after_fixed(params):
        warnings.append(
            "The simulation extends beyond the fixed-rate period; supplied future rates are scenarios, not forecasts."
        )
    if params.installment_method == InstallmentMethod.CALENDAR:
        warnings.append(
            "Calendar annuity has an interest-coverage floor; at extreme rates this may shorten the projected term even without overpayments."
        )
    if params.installment_method == InstallmentMethod.MONTHLY:
        warnings.append(
            "Monthly annuity is combined with daily interest; the final installment can differ."
        )
    if any(
        r.total_installment > standard[0].total_installment * Decimal("1.05")
        for r in standard[1:]
    ):
        warnings.append(
            "A payment exceeds the initial installment by more than 5%; review dates, rates and final settlement."
        )
    if requested > made:
        warnings.append(
            "Some planned overpayments were capped or fell after early repayment; see unused overpayments."
        )
    return SimulationSummary(
        total_paid_standard=money(params.amount + standard_interest + standard_cost),
        total_paid_with_overpayments=money(
            params.amount + overpaid_interest + overpaid_cost
        ),
        total_interest_saved=money(standard_interest - overpaid_interest),
        months_saved=len(standard) - len(overpaid),
        total_overpayments_made=money(made),
        standard_schedule=standard,
        overpayment_schedule=overpaid,
        total_interest_standard=money(standard_interest),
        total_interest_overpaid=money(overpaid_interest),
        total_cost_standard=money(standard_interest + standard_cost),
        total_cost_overpaid=money(overpaid_interest + overpaid_cost),
        requested_overpayments=money(requested),
        unused_overpayments=money(requested - made),
        warnings=tuple(warnings),
    )


def dates_after_fixed(params: LoanParameters) -> bool:
    return (
        params.fixed_until is not None
        and payment_dates(params)[-1] > params.fixed_until
    )
