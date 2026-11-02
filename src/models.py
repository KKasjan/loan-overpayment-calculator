"""Validated simulation inputs. Rates are fractions, money is Decimal PLN."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class OverpaymentStrategy(Enum):
    REDUCE_INSTALLMENT = "REDUCE_INSTALLMENT"
    SHORTEN_TERM = "SHORTEN_TERM"
    MIXED = "MIXED"


class RepaymentModel(Enum):
    GENERAL = "Ogólny — dotychczasowe strategie"
    ING = "ING — nadpłata i osobny aneks (model do weryfikacji)"


class DayCount(Enum):
    ACTUAL_ACTUAL = "ACT/ACT (365/366)"
    ACTUAL_365 = "ACT/365"


class InstallmentMethod(Enum):
    MONTHLY = "Rata ze stopą miesięczną (roczna / 12)"
    CALENDAR = "Rata kalendarzowa (rzeczywiste daty)"


class ShorteningPolicy(Enum):
    KEEP_PAYMENT = "Utrzymanie wysokości raty"
    WHOLE_MONTHS = "Pełne miesiące i przeliczenie raty"


def validate_money(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name}: use a finite Decimal value.")
    if value < 0 or (positive and value == 0):
        raise ValueError(
            f"{name}: amount must be {'positive' if positive else 'non-negative'}."
        )
    if value != value.quantize(Decimal("0.01")):
        raise ValueError(f"{name}: use at most two decimal places.")


def validate_rate(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value <= 1:
        raise ValueError("Interest rate must be a finite Decimal between 0 and 1.")


def validate_date(value: date, name: str) -> None:
    if type(value) is not date:
        raise ValueError(f"{name}: use a calendar date.")


@dataclass(frozen=True)
class RateChange:
    date: date
    annual_interest_rate: Decimal

    def __post_init__(self) -> None:
        validate_date(self.date, "Rate change")
        validate_rate(self.annual_interest_rate)


@dataclass(frozen=True)
class TermChange:
    """Separate instruction applied after the installment on this contractual date."""

    date: date
    remaining_months: int

    def __post_init__(self) -> None:
        validate_date(self.date, "Term change")
        if (
            not isinstance(self.remaining_months, int)
            or isinstance(self.remaining_months, bool)
        ) or self.remaining_months < 1:
            raise ValueError("New remaining term must be a positive integer.")


@dataclass(frozen=True)
class AnnexInstruction:
    """Effective date and payment ceiling; bank bounds are supplied, never inferred."""

    date: date
    target_payment: Decimal
    minimum_payment: Decimal | None = None
    maximum_payment: Decimal | None = None

    def __post_init__(self) -> None:
        validate_date(self.date, "Annex")
        validate_money(self.target_payment, "Target payment", positive=True)
        for value in (self.minimum_payment, self.maximum_payment):
            if value is not None:
                validate_money(value, "Bank payment bound", positive=True)
        if (
            self.minimum_payment is not None
            and self.target_payment < self.minimum_payment
        ):
            raise ValueError("Wybrana rata jest poniżej podanego minimum ING.")
        if (
            self.maximum_payment is not None
            and self.target_payment > self.maximum_payment
        ):
            raise ValueError("Wybrana rata przekracza podane maksimum ING.")


@dataclass(frozen=True)
class Overpayment:
    amount: Decimal
    strategy: OverpaymentStrategy
    date: date
    amount_shorten: Decimal | None = None
    amount_reduce: Decimal | None = None

    def __post_init__(self) -> None:
        validate_money(self.amount, "Overpayment", positive=True)
        validate_date(self.date, "Overpayment")
        if not isinstance(self.strategy, OverpaymentStrategy):
            raise ValueError("Unknown overpayment strategy.")
        if self.strategy == OverpaymentStrategy.MIXED:
            if self.amount_shorten is None or self.amount_reduce is None:
                raise ValueError("Mixed strategy requires both allocation amounts.")
            validate_money(self.amount_shorten, "Shortening allocation")
            validate_money(self.amount_reduce, "Reduction allocation")
            if self.amount_shorten + self.amount_reduce != self.amount:
                raise ValueError(
                    "Mixed allocations must sum to the overpayment amount."
                )
        elif self.amount_shorten is not None or self.amount_reduce is not None:
            raise ValueError("Split amounts are allowed only for Mixed strategy.")


@dataclass(frozen=True)
class LoanParameters:
    amount: Decimal
    annual_interest_rate: Decimal
    start_date: date  # Balance and accrued interest are supplied as of this date.
    payment_day: int
    total_month: int
    repayment_model: RepaymentModel = RepaymentModel.GENERAL
    annexes: tuple[AnnexInstruction, ...] = ()
    first_payment_date: date | None = None
    accrued_interest: Decimal = Decimal("0.00")
    current_installment: Decimal | None = None
    day_count: DayCount = DayCount.ACTUAL_ACTUAL
    installment_method: InstallmentMethod = InstallmentMethod.MONTHLY
    shortening_policy: ShorteningPolicy = ShorteningPolicy.KEEP_PAYMENT
    rate_changes: tuple[RateChange, ...] = ()
    term_changes: tuple[TermChange, ...] = ()
    fixed_until: date | None = None
    shift_collection_dates: bool = False
    # Additional holidays allow the calendar to be reconciled with the bank.
    additional_holidays: tuple[date, ...] = ()
    upfront_cost: Decimal = Decimal("0.00")
    monthly_cost: Decimal = Decimal("0.00")
    annual_balance_insurance_rate: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        validate_money(self.amount, "Outstanding principal", positive=True)
        validate_rate(self.annual_interest_rate)
        validate_date(self.start_date, "Simulation start")
        if (
            not isinstance(self.total_month, int) or isinstance(self.total_month, bool)
        ) or not 1 <= self.total_month <= 420:
            raise ValueError("Remaining term must be an integer from 1 to 420 months.")
        if (
            not isinstance(self.payment_day, int) or isinstance(self.payment_day, bool)
        ) or not 1 <= self.payment_day <= 31:
            raise ValueError("Payment day must be an integer from 1 to 31.")
        if self.first_payment_date is not None:
            validate_date(self.first_payment_date, "First payment")
            if self.first_payment_date <= self.start_date:
                raise ValueError("First payment must be after the simulation start.")
        for value, name in [
            (self.accrued_interest, "Accrued interest"),
            (self.upfront_cost, "Upfront cost"),
            (self.monthly_cost, "Monthly cost"),
        ]:
            validate_money(value, name)
        if self.current_installment is not None:
            validate_money(
                self.current_installment, "Current installment", positive=True
            )
        validate_rate(self.annual_balance_insurance_rate)
        for convention, enum in [
            (self.day_count, DayCount),
            (self.installment_method, InstallmentMethod),
            (self.shortening_policy, ShorteningPolicy),
        ]:
            if not isinstance(convention, enum):
                raise ValueError("Unknown calculation convention.")
        if self.fixed_until is not None:
            validate_date(self.fixed_until, "Fixed rate end")
        for change in self.rate_changes:
            if change.date < self.start_date:
                raise ValueError("Rate change precedes the simulation start.")
            if self.fixed_until is not None and change.date < self.fixed_until:
                raise ValueError(
                    "Rate changes cannot occur within the fixed-rate period."
                )
        if len({c.date for c in self.rate_changes}) != len(self.rate_changes):
            raise ValueError("Only one rate change is allowed on each date.")
        if len({c.date for c in self.term_changes}) != len(self.term_changes):
            raise ValueError("Only one term instruction is allowed on each date.")
        if not isinstance(self.repayment_model, RepaymentModel):
            raise ValueError("Unknown repayment model.")
        if self.repayment_model == RepaymentModel.ING:
            if self.installment_method != InstallmentMethod.CALENDAR:
                raise ValueError("Model ING wymaga raty kalendarzowej.")
            if self.term_changes:
                raise ValueError("W modelu ING użyj aneksu z docelową ratą.")
        elif self.annexes:
            raise ValueError("Aneksy z docelową ratą wymagają modelu ING.")
        if len({a.date for a in self.annexes}) != len(self.annexes):
            raise ValueError("Dopuszczalny jest jeden aneks danego dnia.")
        for holiday in self.additional_holidays:
            validate_date(holiday, "Holiday")


@dataclass(frozen=True)
class InstallmentDetails:
    installment_number: int
    payment_date: date  # Contractual due date, or early final settlement date.
    days_in_period: int
    total_installment: Decimal
    principal: Decimal
    interest: Decimal
    overpayment: Decimal
    remaining_balance: Decimal
    collection_date: date | None = None
    annual_interest_rate: Decimal = Decimal("0")
    additional_cost: Decimal = Decimal("0.00")
    contractual_months_remaining: int = 0


@dataclass(frozen=True)
class SimulationSummary:
    total_paid_standard: Decimal
    total_paid_with_overpayments: Decimal
    total_interest_saved: Decimal
    months_saved: int
    total_overpayments_made: Decimal
    standard_schedule: list[InstallmentDetails]
    overpayment_schedule: list[InstallmentDetails]
    total_interest_standard: Decimal = Decimal("0.00")
    total_interest_overpaid: Decimal = Decimal("0.00")
    total_cost_standard: Decimal = Decimal("0.00")
    total_cost_overpaid: Decimal = Decimal("0.00")
    requested_overpayments: Decimal = Decimal("0.00")
    unused_overpayments: Decimal = Decimal("0.00")
    warnings: tuple[str, ...] = field(default_factory=tuple)
