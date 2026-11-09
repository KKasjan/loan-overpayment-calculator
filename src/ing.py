"""Two-step repayment model. Calendar assumptions need individual bank calibration.

Events on one date: contractual payment, rate change, capital overpayment, annex.
Interest accrues on [previous date, event date), without capitalization. Dates of
operations are effective booking dates, not dates on which transfers were ordered.
An annex target is a ceiling: select the shortest whole-month term fitting it.
"""

from src.messages import InputError, CalculationError

from dataclasses import dataclass, replace
from datetime import date, date as CalendarDate
from decimal import Decimal

from src.calculator import (
    CENT,
    ZERO,
    calculate_daily_interest,
    collection_date,
    money,
    payment_dates,
    period_interest,
    rate_on,
)
from src.models import (
    AnnexInstruction,
    InstallmentDetails,
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    RepaymentModel,
    validate_date,
    validate_money,
)


@dataclass(frozen=True)
class LoanState:
    date: date
    balance: Decimal
    accrued_interest: Decimal
    payment: Decimal
    dates: tuple[CalendarDate, ...]


@dataclass(frozen=True)
class EventResult:
    date: date
    kind: str
    amount: Decimal
    balance: Decimal
    payment_before: Decimal
    payment_after: Decimal
    remaining_months: int
    maturity: CalendarDate | None
    target_payment: Decimal | None = None


@dataclass(frozen=True)
class IngSimulation:
    schedule: list[InstallmentDetails]
    events: list[EventResult]
    state: LoanState


@dataclass(frozen=True)
class OverpaymentQuote:
    overpayment: Decimal
    payment_after_overpayment: Decimal
    payment_after_annex: Decimal
    remaining_months: int
    maturity: CalendarDate
    target_payment: Decimal
    date: date


def _fits(
    state: LoanState,
    dates: tuple[CalendarDate, ...],
    payment: Decimal,
    params: LoanParameters,
) -> bool:
    """Every payment, including the last one, must fit the ceiling in cents."""
    balance = state.balance
    accrued = state.accrued_interest
    previous = state.date
    rate = rate_on(params, previous)
    for due in dates:
        interest = money(
            accrued
            + calculate_daily_interest(
                balance,
                rate,
                previous,
                due,
                round_result=False,
                day_count=params.day_count,
            )
        )
        if balance + interest <= payment:
            return True
        if payment <= interest:
            return False
        balance -= payment - interest
        previous, accrued = due, ZERO
    return balance == 0


def quote_payment(
    state: LoanState, dates: tuple[CalendarDate, ...], params: LoanParameters
) -> Decimal:
    """Minimum constant cent payment clearing principal and interest by maturity.

    Uses the current rate as a scenario; future rate changes reprice when effective.
    Already accrued interest is settled at the first due date, never capitalized.
    """
    if not dates:
        raise InputError(
            "validation.no_future_installments_are_available_for_recalculation"
        )
    if state.balance == 0:
        return money(state.accrued_interest)
    rate = rate_on(params, state.date)
    first_interest = money(
        state.accrued_interest
        + calculate_daily_interest(
            state.balance,
            rate,
            state.date,
            dates[0],
            round_result=False,
            day_count=params.day_count,
        )
    )
    low, high = 1, int((state.balance + first_interest) / CENT)
    while low < high:
        mid = (low + high) // 2
        if _fits(state, dates, CENT * mid, params):
            high = mid
        else:
            low = mid + 1
    return CENT * low


def select_annex(
    state: LoanState, instruction: AnnexInstruction, params: LoanParameters
) -> tuple[tuple[CalendarDate, ...], Decimal]:
    """Pick shortest strictly reduced contractual term within supplied bank bounds."""
    if len(state.dates) < 2:
        raise InputError(
            "validation.too_few_installments_remain_to_shorten_the_term_by"
        )
    # Payment decreases monotonically as candidate term grows.
    low, high = 1, len(state.dates) - 1
    while low < high:
        mid = (low + high) // 2
        if (
            quote_payment(state, state.dates[:mid], params)
            <= instruction.target_payment
        ):
            high = mid
        else:
            low = mid + 1
    dates = state.dates[:low]
    payment = quote_payment(state, dates, params)
    if payment > instruction.target_payment:
        raise InputError(
            "validation.the_installment_ceiling_is_insufficient_to_shorten_the_term"
        )
    if (
        instruction.minimum_payment is not None
        and payment < instruction.minimum_payment
    ):
        raise InputError(
            "validation.the_calculated_whole_month_installment_is_below_the_ing"
        )
    return dates, payment


def simulate_ing(
    params: LoanParameters,
    overpayments: list[Overpayment],
    *,
    stop_date: date | None = None,
) -> IngSimulation:
    """Run dated events, or inspect state after all events on stop_date."""
    if params.repayment_model != RepaymentModel.ING:
        raise InputError("validation.select_the_ing_model")
    dates = tuple(payment_dates(params))
    original_maturity = dates[-1]
    for op in overpayments:
        if op.strategy != OverpaymentStrategy.REDUCE_INSTALLMENT:
            raise InputError(
                "validation.in_the_ing_model_every_overpayment_reduces_the_installment"
            )
        if not params.start_date <= op.date <= original_maturity:
            raise InputError("validation.overpayment_is_outside_the_simulation_range")
    for event_date in [a.date for a in params.annexes] + [
        r.date for r in params.rate_changes
    ]:
        if not params.start_date <= event_date <= original_maturity:
            raise InputError(
                "validation.amendment_or_rate_change_is_outside_the_simulation_range"
            )
    if stop_date is not None:
        validate_date(stop_date, "Quote date")
        if not params.start_date <= stop_date < original_maturity:
            raise InputError(
                "validation.the_quote_date_must_precede_the_final_installment"
            )
    timeline = sorted(
        set(dates)
        | {op.date for op in overpayments}
        | {a.date for a in params.annexes}
        | {r.date for r in params.rate_changes}
        | ({stop_date} if stop_date is not None else set())
    )
    balance, accrued = params.amount, params.accrued_interest
    cursor = last_due = params.start_date
    state = LoanState(cursor, balance, accrued, ZERO, dates)
    payment = params.current_installment or quote_payment(state, dates, params)
    rows: list[InstallmentDetails] = []
    events: list[EventResult] = []
    pending_overpayment = ZERO
    opening_balance = balance
    for when in timeline:
        if stop_date is not None and when > stop_date:
            break
        if balance == 0:
            break
        accrued += period_interest(params, balance, cursor, when)
        cursor = when
        # Scheduled installment always precedes a same-day overpayment/annex.
        if when in dates:
            interest = money(accrued)
            installment = min(payment, balance + interest)
            if when == dates[-1]:
                installment = balance + interest
            if installment <= interest and balance:
                raise InputError(
                    "validation.the_installment_does_not_cover_interest_check_the_current"
                )
            principal = installment - interest
            balance -= principal
            dates = tuple(d for d in dates if d > when)
            cost = money(
                params.monthly_cost
                + opening_balance * params.annual_balance_insurance_rate / 12
            )
            rows.append(
                InstallmentDetails(
                    len(rows) + 1,
                    when,
                    (when - last_due).days,
                    installment,
                    principal,
                    interest,
                    pending_overpayment,
                    balance,
                    collection_date(when, params),
                    rate_on(params, when),
                    cost,
                    len(dates) if balance else 0,
                )
            )
            pending_overpayment, accrued = ZERO, ZERO
            last_due, opening_balance = when, balance

        def snapshot() -> LoanState:
            return LoanState(when, balance, accrued, payment, dates)

        def record(
            kind: str, paid: Decimal, before: Decimal, target: Decimal | None = None
        ) -> None:
            events.append(
                EventResult(
                    when,
                    kind,
                    paid,
                    balance,
                    before,
                    payment,
                    len(dates) if balance else 0,
                    dates[-1] if balance and dates else None,
                    target,
                )
            )

        if balance and any(r.date == when for r in params.rate_changes):
            before = payment
            payment = quote_payment(snapshot(), dates, params)
            record("rate_change", ZERO, before)
        requested = sum((op.amount for op in overpayments if op.date == when), ZERO)
        if balance and requested:
            before = payment
            paid = min(balance, requested)
            balance -= paid
            pending_overpayment += paid
            if balance:
                payment = quote_payment(snapshot(), dates, params)
            else:
                # Final capital overpayment also settles accrued interest that day.
                if rows and rows[-1].payment_date == when:
                    rows[-1] = replace(
                        rows[-1],
                        overpayment=rows[-1].overpayment + pending_overpayment,
                        remaining_balance=ZERO,
                        contractual_months_remaining=0,
                    )
                else:
                    cost = money(
                        params.monthly_cost
                        + opening_balance * params.annual_balance_insurance_rate / 12
                    )
                    rows.append(
                        InstallmentDetails(
                            len(rows) + 1,
                            when,
                            (when - last_due).days,
                            money(accrued),
                            ZERO,
                            money(accrued),
                            pending_overpayment,
                            ZERO,
                            collection_date(when, params),
                            rate_on(params, when),
                            cost,
                            0,
                        )
                    )
                payment, accrued, pending_overpayment, dates = ZERO, ZERO, ZERO, ()
            record("overpayment", paid, before)
        for annex in params.annexes:
            if annex.date == when:
                if not balance:
                    raise InputError(
                        "validation.the_amendment_falls_after_full_loan_repayment"
                    )
                before = payment
                dates, payment = select_annex(snapshot(), annex, params)
                record("annex", ZERO, before, annex.target_payment)
        if rows and rows[-1].payment_date == when and balance:
            # Due-date overpayments are aggregated into that due's table row.
            rows[-1] = replace(
                rows[-1],
                overpayment=rows[-1].overpayment + pending_overpayment,
                remaining_balance=balance,
                contractual_months_remaining=len(dates),
            )
            pending_overpayment = ZERO
            opening_balance = balance
        state = snapshot()
    if stop_date is None:
        if (
            balance
            or sum((r.principal + r.overpayment for r in rows), ZERO) != params.amount
        ):
            raise CalculationError(
                "validation.ing_model_principal_reconciliation_failed"
            )
        if sum(
            (r.total_installment + r.overpayment for r in rows), ZERO
        ) != params.amount + sum((r.interest for r in rows), ZERO):
            raise CalculationError("validation.ing_model_payment_reconciliation_failed")
    elif state.date != stop_date or not state.balance:
        raise InputError(
            "validation.the_loan_was_repaid_before_the_selected_quote_date"
        )
    return IngSimulation(rows, events, state)


def required_overpayment(
    params: LoanParameters,
    when: date,
    months_to_shorten: int,
    target_payment: Decimal,
    overpayments: list[Overpayment] | None = None,
) -> OverpaymentQuote:
    """Minimum additional capital payment in cents on an effective booking date.

    Assumes an annex effective that same day, after the additional overpayment.
    Existing events up to that date are included. Future events do not fund the goal.
    """
    validate_money(target_payment, "Target payment", positive=True)
    if (
        not isinstance(months_to_shorten, int)
        or isinstance(months_to_shorten, bool)
        or months_to_shorten < 1
    ):
        raise InputError(
            "validation.term_reduction_must_be_a_positive_integer_number_of"
        )
    if any(a.date == when for a in params.annexes):
        raise InputError(
            "validation.remove_the_amendment_on_the_quote_date_the_planned"
        )
    state = simulate_ing(params, overpayments or [], stop_date=when).state
    count = len(state.dates) - months_to_shorten
    if count < 1:
        raise InputError(
            "validation.at_least_one_installment_must_remain_after_term_reduction"
        )
    new_dates = state.dates[:count]

    def fits(cents: int) -> bool:
        trial = replace(state, balance=state.balance - cents * CENT)
        return _fits(trial, new_dates, target_payment, params)

    low, high = 0, int(state.balance / CENT) - 1
    if not fits(high):
        raise InputError(
            "validation.the_installment_ceiling_does_not_cover_accrued_interest_settle"
        )
    while low < high:
        mid = (low + high) // 2
        if fits(mid):
            high = mid
        else:
            low = mid + 1
    trial = replace(state, balance=state.balance - low * CENT)
    return OverpaymentQuote(
        low * CENT,
        quote_payment(trial, state.dates, params),
        quote_payment(trial, new_dates, params),
        count,
        new_dates[-1],
        target_payment,
        when,
    )
