import streamlit as st
from datetime import date
from decimal import Decimal
from src.calculator import calculate_simulation_summary
from src.models import LoanParameters

# Configuration
st.set_page_config(
    page_title="Advanced Loan Calculator",
    page_icon="💰",
    layout="wide"
)

st.title("Advanced Mortgage Loan Overpayment Calculator 💰")
st.markdown(
    "Replicating complex banking mechanisms with daily interest compounding."
)

st.sidebar.header("Loan Parameters")

# Sidebar entry form
amount = st.sidebar.number_input(
    "Loan Amount (PLN)",
    min_value=1000,
    value=10000,
    step=5000,
)
interest_rate = st.sidebar.number_input(
    "Annual Interest Rate (%)",
    min_value=0.0,
    max_value=20.0,
    value=0.0,
    step=0.1,
)
months = st.sidebar.number_input(
    "Total Months",
    min_value=1,
    max_value=420,
    value=60,
    step=12,
)

loan_params = LoanParameters(
    amount=Decimal(str(amount)),
    annual_interest_rate=Decimal(str(interest_rate / 100)),
    start_date=date.today(),
    payment_day=date.today().day if date.today().day <= 28 else 28,
    total_month=int(months)
)

overpayments = []

summary = calculate_simulation_summary(loan_params, overpayments)

st.write("## 📊 Standard Loan Metrics")

col1, col2 = st.columns(2)
with col1:
    st.metric(
        label="Total Paid (Standard)",
        value=f"{summary.total_paid_standard:,} PLN"
    )
with col2:
    st.metric(
        label="Total Expected Interest",
        value=f"{(summary.total_paid_standard - loan_params.amount):,} PLN",
    )

st.write("### Live Debugger for QA: ")
st.write(f"* Simulated amount: **{amount:,} PLN**")
st.write(f"* Interest rate: **{interest_rate}%**")
st.write(f"* Repayment period: **{months} ​​months**")
