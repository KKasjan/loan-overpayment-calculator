from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Any


class OverpaymentStrategy(Enum):
    """Strategies for loan overpayments."""

    REDUCE_INSTALLMENT = "REDUCE_INSTALLMENT"
    SHORTEN_TERM = "SHORTEN_TERM"
    MIXED = "MIXED"


@dataclass(frozen=True)
class Overpayment:
    """Represents a single or recurring overpayment."""

    amount: Decimal
    strategy: OverpaymentStrategy
    date: date  # Exact date of the overpayment

    amount_shorten: Decimal | None = None
    amount_reduce: Decimal | None = None

    def __post_init__(self) -> None:
        """
        QA Validation Gate to ensure data consistency inside the model.
        """
        if self.amount <= 0:
            raise ValueError("The overpayment amount must be greater than zero.")

        if self.strategy == OverpaymentStrategy.MIXED:
            if self.amount_shorten is None or self.amount_reduce is None:
                raise ValueError(
                    "Both amount_shorten and amount_reduce "
                    "must be provided for MIXED strategy."
                )
            if self.amount_shorten + self.amount_reduce != self.amount:
                raise ValueError(
                    f"Sum of split amounts ({self.amount_shorten} + "
                    f"{self.amount_reduce}) must equal the total "
                    f"overpayment amount ({self.amount})."
                )


@dataclass
class LoanParameters:
    """Input parameters for a mortgage or consumer loan."""

    amount: Decimal  # Amount outstanding
    annual_interest_rate: Decimal  # Annual interest rate
    start_date: date  # Credit launch date / simulation starting point
    payment_day: int  # Day of the month on which the installment is paid
    total_month: int  # Number of months remaining to pay

    def __post_init__(self) -> None:
        """QA validation gate protecting the mathematical
        engine from invalid data.
        """
        if self.amount <= 0:
            raise ValueError("The loan amount must be greater than zero.")
        if self.annual_interest_rate < 0 or self.annual_interest_rate > 1:
            raise ValueError("The annual percentage rate must be between 0% and 100%.")
        if self.total_month <= 0:
            raise ValueError("The loan period must be at least 1 month.")
        if not (1 <= self.payment_day <= 28):
            raise ValueError(
                "The installment payment date must be between "
                "1 and 28 (avoiding the February problem)"
            )


@dataclass(frozen=True)
class InstallmentDetails:
    """A single entry in the repayment schedule for a given month."""

    installment_number: int
    payment_date: date

    # How many days have passed since the previous repayment
    days_in_period: int
    total_installment: Decimal  # Total installment (principal + interest)
    principal: Decimal  # Capital installment (the part that reduces the debt)
    interest: Decimal  # Interest installment (profit for the bank)
    overpayment: Decimal  # Optional overpayment amount this month

    # Debt status AFTER this installment and overpayment have been paid
    remaining_balance: Decimal


@dataclass(frozen=True)
class SimulationSummary:
    """
    Summary comparing the standard schedule against the overpaid schedule.
    """

    total_paid_standard: Decimal  # Total cost without overpayments
    total_paid_with_overpayments: Decimal  # Total cost including overpayments
    total_interest_saved: Decimal  # Net interest savings
    months_saved: int  # Number of months shaved off the loan term
    total_overpayments_made: Decimal  # Total amount of extra capital injected
    standard_schedule: List[Any]  # Stores the full standard breakdown
    overpayment_schedule: List[Any]  # Stores the full overpaid breakdown
