import streamlit as st
import pandas as pd
from datetime import date
from decimal import Decimal
from src.calculator import get_next_payment_date, calculate_simulation_summary
from src.models import (
    LoanParameters,
    Overpayment,
    OverpaymentStrategy,
    SimulationSummary,
)

# Page configuration
st.set_page_config(
    page_title="Advanced Loan Calculator",
    page_icon="💰",
    layout="wide",
)

st.title("Advanced Loan Overpayment Calculator 💰")
st.markdown("Replicating complex banking mechanisms with daily interest compounding.")

# ==========================================
# SIDEBAR: INPUT PARAMETERS
# ==========================================
st.sidebar.header("📋 1. Loan Parameters")

amount = st.sidebar.number_input(
    "Loan Amount (PLN)",
    min_value=1000,
    value=300000,
    step=10000,
)
interest_rate = st.sidebar.number_input(
    "Annual Interest Rate (%)",
    min_value=0.0,
    max_value=20.0,
    value=7.5,
    step=0.01,
)
months = st.sidebar.number_input(
    "Total Months",
    min_value=1,
    max_value=420,
    value=360,
    step=12,
)
payment_day = st.sidebar.slider(
    "Monthly Payment Day",
    min_value=1,
    max_value=28,
    value=10,
)

st.sidebar.markdown("---")

# ==========================================
# SIDEBAR: OVERPAYMENT CONFIGURATION
# ==========================================
st.sidebar.header("💸 2. Overpayment Settings")

overpayment_type = st.sidebar.radio(
    "Overpayment Mode",
    [
        "No Overpayments",
        "Regular Monthly Overpayment",
        "Single One-Time Overpayment",
    ],
)

# Auxiliary variables for collecting overpayment data
strategy_label = None
monthly_op_amount = 0.0
monthly_shorten = 0.0
monthly_reduce = 0.0
single_op_amount = 0.0
single_shorten = 0.0
single_reduce = 0.0
op_month_delta = 1

strategy_options = ["Shorten Term", "Reduce Installment", "Mixed"]
strategy_mapping = {
    "Shorten Term": OverpaymentStrategy.SHORTEN_TERM,
    "Reduce Installment": OverpaymentStrategy.REDUCE_INSTALLMENT,
    "Mixed": OverpaymentStrategy.MIXED,
}

if overpayment_type == "Regular Monthly Overpayment":
    strategy_label = st.sidebar.selectbox("Overpayment Strategy", strategy_options)
    strategy = strategy_mapping[strategy_label]

    if strategy == OverpaymentStrategy.MIXED:
        monthly_shorten = st.sidebar.number_input(
            "Monthly Shorten Part (PLN)",
            min_value=0,
            value=500,
            step=100,
        )
        monthly_reduce = st.sidebar.number_input(
            "Monthly Reduce Part (PLN)",
            min_value=0,
            value=500,
            step=100,
        )
        monthly_op_amount = float(monthly_shorten + monthly_reduce)
        st.sidebar.info(f"Total Monthly: {monthly_op_amount:,.2f} PLN")
    else:
        monthly_op_amount = st.sidebar.number_input(
            "Monthly overpayment amount (PLN)", min_value=100, value=1000, step=100
        )

elif overpayment_type == "Single One-Time Overpayment":
    op_month_delta = int(
        st.sidebar.number_input(
            "In which month of loan life?",
            min_value=1,
            max_value=int(months),
            value=12,
        )
    )
    strategy_label = st.sidebar.selectbox("Overpayment Strategy", strategy_options)
    strategy = strategy_mapping[strategy_label]

    if strategy == OverpaymentStrategy.MIXED:
        single_shorten = st.sidebar.number_input(
            "One-Time Shorten Part (PLN)",
            min_value=0,
            value=1000,
            step=100,
        )
        single_reduce = st.sidebar.number_input(
            "One-Time Reduce Part (PLN)",
            min_value=0,
            value=1000,
            step=100,
        )
        single_op_amount = float(single_shorten + single_reduce)
        st.sidebar.info(f"Total One-Time: {single_op_amount:,.2f} PLN")
    else:
        single_op_amount = st.sidebar.number_input(
            "One-Time Overpayment Amount (PLN)",
            min_value=100,
            value=1000,
            step=100,
        )


# ==========================================
# CACHED CALCULATION WRAPPER
# ==========================================
@st.cache_data
def run_simulation(
    amount_val: float,
    rate_val: float,
    months_val: int,
    payment_day_val: int,
    start_date_val: date,
    overpayment_mode: str,
    strategy_val: str | None,
    monthly_op_val: float,
    monthly_shorten_val: float,
    monthly_reduce_val: float,
    op_month_delta_val: int,
    single_op_val: float,
    single_shorten_val: float,
    single_reduce_val: float,
) -> SimulationSummary:
    """
    Calculator packaging with Streamlit cache for increased performance.

    All inputs are primitive types or basic date objects to guarantee
    deterministic caching behavior.
    """
    loan_params = LoanParameters(
        amount=Decimal(str(amount_val)),
        annual_interest_rate=Decimal(str(rate_val / 100)),
        start_date=start_date_val,
        payment_day=payment_day_val,
        total_month=months_val,
    )

    overpayments_list = []

    if overpayment_mode == "Regular Monthly Overpayment" and strategy_val:
        strat = strategy_mapping[strategy_val]
        amt_shorten = (
            Decimal(str(monthly_shorten_val))
            if strat == OverpaymentStrategy.MIXED
            else None
        )
        amt_reduce = (
            Decimal(str(monthly_reduce_val))
            if strat == OverpaymentStrategy.MIXED
            else None
        )
        total_op = Decimal(str(monthly_op_val))

        curr_op_date = loan_params.start_date
        for _ in range(loan_params.total_month):
            curr_op_date = get_next_payment_date(
                curr_op_date,
                loan_params.payment_day,
            )
            overpayments_list.append(
                Overpayment(
                    date=curr_op_date,
                    amount=total_op,
                    strategy=strat,
                    amount_shorten=amt_shorten,
                    amount_reduce=amt_reduce,
                )
            )

    elif overpayment_mode == "Single One-Time Overpayment" and strategy_val:
        strat = strategy_mapping[strategy_val]
        amt_shorten = (
            Decimal(str(single_shorten_val))
            if strat == OverpaymentStrategy.MIXED
            else None
        )
        amt_reduce = (
            Decimal(str(single_reduce_val))
            if strat == OverpaymentStrategy.MIXED
            else None
        )
        total_op = Decimal(str(single_op_val))

        curr_op_date = loan_params.start_date
        for _ in range(op_month_delta_val):
            curr_op_date = get_next_payment_date(
                curr_op_date,
                loan_params.payment_day,
            )
            overpayments_list.append(
                Overpayment(
                    date=curr_op_date,
                    amount=total_op,
                    strategy=strat,
                    amount_shorten=amt_shorten,
                    amount_reduce=amt_reduce,
                )
            )

    return calculate_simulation_summary(loan_params, overpayments_list)


today_date = date.today()

# Launching a precision engine with cache optimization
summary = run_simulation(
    amount_val=float(amount),
    rate_val=float(interest_rate),
    months_val=int(months),
    payment_day_val=int(payment_day),
    start_date_val=today_date,
    overpayment_mode=overpayment_type,
    strategy_val=strategy_label,
    monthly_op_val=float(monthly_op_amount),
    monthly_shorten_val=float(monthly_shorten),
    monthly_reduce_val=float(monthly_reduce),
    op_month_delta_val=op_month_delta,
    single_op_val=float(single_op_amount),
    single_shorten_val=float(single_shorten),
    single_reduce_val=float(single_reduce),
)

# ==========================================
# MAIN VIEW: SUMMARY DASHBOARD
# ==========================================
st.write("## 📊 Simulation Summary Dashboard")

st.subheader("Financial Comparison")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Total Cost (Standard)",
        value=f"{summary.total_paid_standard:,.2f} PLN",
    )
with col2:
    cost_delta = None
    if overpayment_type != "No Overpayments":
        saved_amount = (
            summary.total_paid_standard - summary.total_paid_with_overpayments
        )
        cost_delta = f"-{saved_amount:,.2f} PLN"
    st.metric(
        label="Total Cost (with Overpayments)",
        value=f"{summary.total_paid_with_overpayments:,.2f} PLN",
        delta=cost_delta,
        delta_color="inverse",
    )

term_delta = (
    f"{summary.months_saved} months shorter!" if summary.months_saved > 0 else None
)
with col3:
    st.metric(
        label="🔥 Total Interest SAVED",
        value=f"{summary.total_interest_saved:,.2f} PLN",
        delta=term_delta,
        delta_color="normal",
    )

st.subheader("Simulation Metrics")
col4, col5 = st.columns(2)

with col4:
    st.metric(
        label="Total Overpayments Deposited",
        value=f"{summary.total_overpayments_made:,.2f} PLN",
    )

actual_term_delta = (
    f"-{summary.months_saved} months" if summary.months_saved > 0 else None
)

with col5:
    st.metric(
        label="Actual Loan Term",
        value=f"{months - summary.months_saved} months",
        delta=actual_term_delta,
        delta_color="inverse",
    )

# ==========================================
# VISUALIZATIONS: INTEREST & BALANCE CHARTS
# ==========================================
st.write("## 📈 Balance Breakdown Over Time")

if summary.standard_schedule and summary.overpayment_schedule:
    df_standard = pd.DataFrame([vars(r) for r in summary.standard_schedule])
    df_overpayment = pd.DataFrame([vars(r) for r in summary.overpayment_schedule])

    max_len = max(len(df_standard), len(df_overpayment))
    chart_df = pd.DataFrame(index=range(max_len))

    chart_df["Standard Schedule"] = (
        df_standard["remaining_balance"]
        .astype(float)
        .reindex(range(max_len), fill_value=0.0)
    )
    chart_df["With Overpayments"] = (
        df_overpayment["remaining_balance"]
        .astype(float)
        .reindex(range(max_len), fill_value=0.0)
    )

    st.line_chart(chart_df)

    # ==========================================
    # FULL AMORTIZATION SCHEDULES (TABLES)
    # ==========================================
    st.write("## 📋 Detailed Amortization Schedules")

    tab1, tab2 = st.tabs(["Standard Schedule", "Schedule With Overpayments"])

    # Configure tabular presentation columns dynamically
    # for premium bank-ledger styling
    schedule_columns_config = {
        "installment_number": st.column_config.NumberColumn(
            "Installment No.", format="%d"
        ),
        "payment_date": st.column_config.DateColumn(
            "Payment Date", format="YYYY-MM-DD"
        ),
        "days_in_period": st.column_config.NumberColumn("Days in Period", format="%d"),
        "total_installment": st.column_config.NumberColumn(
            "Total Installment (PLN)", format="%.2f"
        ),
        "principal": st.column_config.NumberColumn(
            "Principal Part (PLN)", format="%.2f"
        ),
        "interest": st.column_config.NumberColumn("Interest Part (PLN)", format="%.2f"),
        "overpayment": st.column_config.NumberColumn(
            "Overpayment (PLN)", format="%.2f"
        ),
        "remaining_balance": st.column_config.NumberColumn(
            "Outstanding Principal (PLN)", format="%.2f"
        ),
    }

    with tab1:
        st.write("### Base Loan Plan (No Overpayments)")
        st.dataframe(
            df_standard,
            use_container_width=True,
            column_config=schedule_columns_config,
        )

    with tab2:
        st.write("### Accelerated Plan (With Overpayments)")
        st.dataframe(
            df_overpayment,
            use_container_width=True,
            column_config=schedule_columns_config,
        )

else:
    st.info("No tracking data available to render charts and schedules.")
