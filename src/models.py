from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class OverpaymentStrategy(Enum):
    REDUCE_INSTALLMENT = "REDUCE INSTALLMENT"
    SHORTEN_TERM = "SHORTEN_TERM"


@dataclass(frozen=True)
class Overpayment:
    """Represents a single or recurring overpayment."""

    amount: Decimal
    strategy: OverpaymentStrategy
    date: date  # Exact date of the overpayment


@dataclass
class LoanParameters:
    """Mortgage/Consumer Loan Input Data."""

    amount: Decimal  # Amount outstanding
    annual_interest_rate: Decimal  # Annual interest rate
    start_date: date  # Credit launch date / simulation starting point
    payment_day: int  # Day of the month on which the installment is paid
    total_month: int  # Number of months remaining to pay


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
