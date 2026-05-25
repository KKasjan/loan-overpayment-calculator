import streamlit as st
from datetime import date
from decimal import Decimal
from src.calculator import calculate_simulation_summary
from src.models import LoanParameters, Overpayment, OverpaymentStrategy

# Page configuration
st.set_page_config(
    page_title="Advanced Loan Calculator",
    page_icon="💰",
    layout="wide",
)

st.title("Advanced Loan Overpayment Calculator 💰")
st.markdown(
    "Replicating complex banking mechanisms with daily interest compounding."
)

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
    step=0.1,
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

# Building baseline loan parameters
loan_params = LoanParameters(
    amount=Decimal(str(amount)),
    annual_interest_rate=Decimal(str(interest_rate / 100)),
    start_date=date.today(),
    payment_day=int(payment_day),
    total_month=int(months),
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
    ]
)

overpayments = []

if overpayment_type == "Regular Monthly Overpayment":
    monthly_op_amount = st.sidebar.number_input(
        "Monthly Overpayment Amount (PLN)",
        min_value=100,
        value=1000,
        step=100,
    )
    strategy_label = st.sidebar.selectbox(
        "Overpayment Strategy", ["Shorten Term", "Reduce Installment"]
    )

    strategy = (
        OverpaymentStrategy.SHORTEN_TERM
        if strategy_label == "Shorten Term"
        else OverpaymentStrategy.REDUCE_INSTALLMENT
    )

    # Generate recurring overpayments for each month of the loan term
    # We assume the overpayment occurs on the same day
    # as the regular installment
    current_op_date = loan_params.start_date
    for i in range(loan_params.total_month):
        # Emulate moving to the next month
        if current_op_date.month == 12:
            current_op_date = date(
                current_op_date.year + 1,
                1,
                loan_params.payment_day,
            )
        else:
            current_op_date = date(
                current_op_date.year,
                current_op_date.month + 1,
                loan_params.payment_day,
            )

        overpayments.append(
            Overpayment(
                date=current_op_date,
                amount=Decimal(str(monthly_op_amount)),
                strategy=strategy,
            )
        )

elif overpayment_type == "Single One-Time Overpayment":
    single_op_amount = st.sidebar.number_input(
        "One-Time Amount (PLN)",
        min_value=100,
        value=1000,
        step=100,
    )
    op_month_delta = st.sidebar.number_input(
        "In which month of loan life?",
        min_value=1,
        max_value=loan_params.total_month,
        value=12,
    )
    strategy_label = st.sidebar.selectbox(
        "Overpayment Strategy", ["Shorten Term", "Reduce Installment"]
    )

    strategy = (
        OverpaymentStrategy.SHORTEN_TERM
        if strategy_label == "Short Term"
        else OverpaymentStrategy.REDUCE_INSTALLMENT
    )

    # Calculate target date for the single overpayment execution
    target_year = loan_params.start_date.year + (
        loan_params.start_date.month + op_month_delta - 1
    ) // 12
    target_month = (
        loan_params.start_date.month + op_month_delta
    ) % 12 + 1

    overpayments.append(

        Overpayment(
            date=date(
                target_year,
                target_month,
                loan_params.payment_day,
            ),
            amount=Decimal(str(single_op_amount)),
            strategy=strategy,
        )
    )

# ==========================================
# EXECUTE MATHEMATICAL ENGINE
# ==========================================
summary = calculate_simulation_summary(loan_params, overpayments)

# ==========================================
# MAIN VIEW: SUMMARY DASHBOARD
# ==========================================
st.write("## 📊 Simulation Summary Dashboard")

# Row 1: General Cost Comparison
st.subheader("Financial Comparison")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Total Cost (Standard)",
        value=f"{summary.total_paid_standard:,.2f} PLN"
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
    f"{summary.months_saved} months shorter!"
    if summary.months_saved > 0
    else None
)
with col3:
    st.metric(
        label="🔥 Total Interest SAVE",
        value=f"{summary.total_interest_saved:,.2f} PLN",
        delta=term_delta,
        delta_color="normal",
    )

# Row 2: Operational Simulation Metrics
st.subheader("Simulation Metrics")
col4, col5 = st.columns(2)

with col4:
    st.metric(
        label="Total Overpayments Deposited",
        value=f"{summary.total_overpayments_made:,.2f} PLN"
    )

actual_term_delta = (
    f"-{summary.months_saved} months"
    if summary.months_saved > 0
    else None
)

with col5:
    st.metric(
        label="Actual Loan Term",
        value=f"{months - summary.months_saved} months",
        delta=actual_term_delta,
        delta_color="inverse"
    )

# ==========================================
# VISUALIZATIONS: INTEREST & BALANCE CHARTS
# ==========================================
st.write("## 📈 Balance Breakdown Over Time")

# FIX: Using the correct attribute names from your SimulationSummary model
if summary.standard_schedule and summary.overpayment_schedule:
    import pandas as pd

    df_standard = pd.DataFrame(
        [vars(r) for r in summary.standard_schedule]
    )
    df_overpayment = pd.DataFrame(
        [vars(r) for r in summary.overpayment_schedule]
    )

    # Dynamic detection of the remaining principal column name
    possible_fields = [
        "remaining_balance",
        "outstanding_principal",
        "outstanding_balance",
        "remaining_principal",
        "balance",
    ]
    balance_col = next(
        (f for f in possible_fields if f in df_standard.columns),
        None
    )

    if balance_col:
        # Create a unified DataFrame structured specifically
        # for the line chart
        chart_df = pd.DataFrame(
            index=range(max(len(df_standard), len(df_overpayment)))
        )

        # Cast Decimal values to float as Streamlit charting
        # libraries require float types
        chart_df["Standard Schedule"] = (
            df_standard[balance_col].astype(float)
        )
        chart_df["With Overpayments"] = (
            df_overpayment[balance_col].astype(float)
        )

        # Render the interactive line chart within the application UI
        st.line_chart(chart_df)
    else:
        st.warning(
            "Principal column not found. Available columns: "
            + ", ".join(df_standard.columns)
        )

    # ==========================================
    # FULL AMORTIZATION SCHEDULES (TABLES)
    # ==========================================
    st.write("## 📋 Detailed Amortization Schedules")

    # Initialize tab containers to cleanly organize
    # the data without cluttering the view
    tab1, tab2 = st.tabs(
        ["Standard Schedule", "Schedule With Overpayments"]
    )

    with tab1:
        st.write("### Base Loan Plan (No Overpayments)")
        # Render an interactive, sortable data table for
        # the standard schedule
        st.dataframe(df_standard, use_container_width=True)

    with tab2:
        st.write("### Accelerated Plan (With Overpayments)")
        # Render an interactive, sortable data table for
        # the overpaid schedule
        st.dataframe(df_overpayment, use_container_width=True)

else:
    st.info(
        "No tracking data available to render charts and schedules."
    )
