"""Streamlit interface; financial scenario construction lives in src.scenarios."""

from calendar import monthrange
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

import pandas as pd
import streamlit as st

from src.i18n import Translator

from src.calculator import calculate_simulation_summary, get_next_payment_date
from src.models import (
    DayCount,
    InstallmentMethod,
    LoanParameters,
    RepaymentModel,
    Overpayment,
    OverpaymentStrategy,
    ShorteningPolicy,
    SimulationSummary,
)
from src.scenarios import (
    build_overpayments,
    build_annexes,
    build_rate_changes,
    build_term_changes,
    decimal_input,
    percent_input,
    principal_from_balance,
)

SELECTION_KEYS = (
    "repayment_model",
    "balance_kind",
    "mode",
    "strategy",
    "method",
    "policy",
    "day_count",
)


def restore_selections() -> None:
    """Re-serialize canonical choices when displayed option strings change language."""
    for selection_key in SELECTION_KEYS:
        saved_key = "selection_" + selection_key
        if saved_key in st.session_state:
            st.session_state[selection_key] = st.session_state[saved_key]


Selection = TypeVar("Selection")


def remember_selection(key: str, value: Selection) -> Selection:
    st.session_state["selection_" + key] = value
    return value


st.session_state.setdefault("language", "pl")
initial_text = Translator(st.session_state.language)
st.set_page_config(
    page_title=initial_text("ui.mortgage_calculator"),
    page_icon=":material/payments:",
    layout="wide",
)
with st.container(horizontal=True, horizontal_alignment="right"):
    st.segmented_control(
        "PL / EN",
        ["pl", "en"],
        required=True,
        format_func=str.upper,
        key="language",
        on_change=restore_selections,
        label_visibility="collapsed",
    )
t = Translator(st.session_state.language)

EDITOR_KEYS = ("rate_editor", "term_editor", "annex_editor", "overpayment_editor")
if st.session_state.get("previous_language", "pl") != st.session_state.language:
    for editor_key in EDITOR_KEYS:
        draft_key = "draft_" + editor_key
        if draft_key in st.session_state:
            st.session_state["base_" + editor_key] = st.session_state[draft_key]
        st.session_state.pop(editor_key, None)
st.session_state.previous_language = st.session_state.language


def localized_editor(data: pd.DataFrame, *, key: str, **kwargs: Any) -> pd.DataFrame:
    """Keep canonical editor rows when translated column configuration changes."""
    base_key = "base_" + key
    if base_key not in st.session_state:
        st.session_state[base_key] = data
    result = st.data_editor(st.session_state[base_key], key=key, **kwargs)
    st.session_state["draft_" + key] = result.copy()
    return result


def localized_table(frame: pd.DataFrame, money_columns: list[str]) -> Any:
    """Format display values while retaining numeric sorting and raw export data."""

    def format_money_cell(value: Any) -> str:
        return "" if pd.isna(value) else t.money(value)

    formats: dict[Any, Any] = {column: format_money_cell for column in money_columns}
    if "annual_interest_rate" in frame:
        formats["annual_interest_rate"] = lambda value: t.percent(value)
    return frame.style.format(formats)


st.title(t("ui.mortgage_overpayment_calculator"))
st.caption(t("ui.daily_simple_interest_results_depend_on_the_selected_assumptions"))

st.sidebar.header(t("ui.loan_parameters"))
repayment_model = remember_selection(
    "repayment_model",
    st.sidebar.selectbox(
        t("ui.repayment_model"),
        list(RepaymentModel),
        index=1,
        format_func=lambda x: t("enum." + x.value.lower()),
        key="repayment_model",
    ),
)
is_ing = repayment_model == RepaymentModel.ING

balance_kind = remember_selection(
    "balance_kind",
    st.sidebar.selectbox(
        t("ui.which_balance_are_you_entering"),
        ["principal", "total"],
        format_func=lambda value: t("balance." + value),
        key="balance_kind",
    ),
)
balance_includes_interest = balance_kind == "total"
amount = st.sidebar.number_input(
    t("ui.total_ing_balance_pln")
    if balance_includes_interest
    else t("ui.outstanding_principal_pln"),
    min_value=0.01,
    value=300000.0,
    step=1000.0,
    key="amount",
)
rate = st.sidebar.number_input(
    t("ui.annual_interest_rate"),
    min_value=0.0,
    max_value=20.0,
    value=7.5,
    step=0.01,
    key="rate",
)
months = st.sidebar.number_input(
    t("ui.remaining_installments"),
    min_value=1,
    max_value=420,
    value=360,
    step=12,
    key="months",
)
payment_day = st.sidebar.slider(
    t("ui.contractual_payment_day"), 1, 31, 10, key="payment_day"
)

st.sidebar.header(t("ui.overpayments"))
mode = remember_selection(
    "mode",
    st.sidebar.radio(
        t("ui.overpayment_mode"),
        ["none", "regular", "single", "irregular"],
        format_func=lambda value: t("mode." + value),
        key="mode",
    ),
)
strategies = list(OverpaymentStrategy)
strategy = OverpaymentStrategy.REDUCE_INSTALLMENT
op_amount = Decimal("0")
shorten = reduce = None
op_month = 1
if mode in ("regular", "single"):
    if not is_ing:
        strategy = remember_selection(
            "strategy",
            st.sidebar.selectbox(
                t("ui.strategy"),
                strategies,
                format_func=lambda value: t("strategy." + value.value),
                key="strategy",
            ),
        )
    else:
        st.sidebar.caption(
            t(
                "ui.every_overpayment_reduces_the_installment_shortening_the_term_requires"
            )
        )
    if mode == "single":
        if "op_month" not in st.session_state:
            st.session_state.op_month = min(12, int(months))
        elif int(st.session_state.op_month) > int(months):
            st.session_state.op_month = int(months)
        selected_month = st.sidebar.number_input(
            t("ui.installment_number_for_overpayment"),
            1,
            int(months),
            value=None,
            key="op_month",
        )
        op_month = int(selected_month or 1)
    if strategy == OverpaymentStrategy.MIXED:
        shorten = decimal_input(
            st.sidebar.number_input(
                t("ui.amount_for_term_reduction_pln"),
                min_value=0.0,
                value=500.0,
                step=100.0,
                key="shorten",
            )
        )
        reduce = decimal_input(
            st.sidebar.number_input(
                t("ui.amount_for_installment_reduction_pln"),
                min_value=0.0,
                value=500.0,
                step=100.0,
                key="reduce",
            )
        )
        op_amount = shorten + reduce
    else:
        op_amount = decimal_input(
            st.sidebar.number_input(
                t("ui.overpayment_amount_pln"),
                min_value=0.0,
                value=1000.0,
                step=100.0,
                key="op_amount",
            )
        )
    if op_amount == 0:
        st.sidebar.info(t("ui.an_amount_of_pln_0_means_no_additional_payments"))

single_date = None
if (
    is_ing
    and mode == "single"
    and st.sidebar.checkbox(
        t("ui.specify_the_overpayment_booking_date"), key="exact_op_date"
    )
):
    single_date = st.sidebar.date_input(
        t("ui.overpayment_booking_date"),
        value=date.today(),
        key="single_date",
        format="YYYY-MM-DD",
    )

st.sidebar.header(t("ui.loan_state_date"))
start = st.sidebar.date_input(
    t("ui.balance_date"), value=date.today(), key="start_date", format="YYYY-MM-DD"
)
first_date = None
if st.sidebar.checkbox(t("ui.specify_the_exact_next_payment_date"), key="custom_first"):
    first_date = st.sidebar.date_input(
        t("ui.next_payment_date"),
        value=get_next_payment_date(start, payment_day),
        key="first_date",
        format="YYYY-MM-DD",
    )
accrued = decimal_input(
    st.sidebar.number_input(
        t("ui.interest_accrued_as_of_the_balance_date_pln"),
        min_value=0.0,
        value=0.0,
        key="accrued",
    )
)
if balance_includes_interest:
    st.sidebar.caption(t("ui.enter_the_interest_shown_in_the_ing_balance_breakdown"))
else:
    st.sidebar.caption(
        t("ui.principal_excludes_interest_enter_interest_already_accrued_as_of")
    )
current_payment = None
if st.sidebar.checkbox(t("ui.use_the_current_bank_installment"), key="use_current"):
    current_payment = decimal_input(
        st.sidebar.number_input(
            t("ui.current_principal_and_interest_installment_pln"),
            min_value=0.01,
            value=2000.0,
            key="current_payment",
        )
    )

st.sidebar.header(t("ui.calculation_assumptions"))
if is_ing:
    method = InstallmentMethod.CALENDAR
    policy = ShorteningPolicy.KEEP_PAYMENT
    st.sidebar.caption(
        t("ui.calendar_installment_this_model_requires_reconciliation_with_the_ing")
    )
else:
    method = remember_selection(
        "method",
        st.sidebar.selectbox(
            t("ui.installment_calculation_method"),
            list(InstallmentMethod),
            index=1,
            format_func=lambda x: t("enum." + x.value.lower()),
            key="method",
        ),
    )
    policy = remember_selection(
        "policy",
        st.sidebar.selectbox(
            t("ui.term_reduction_method"),
            list(ShorteningPolicy),
            format_func=lambda x: t("enum." + x.value.lower()),
            key="policy",
        ),
    )
day_count = remember_selection(
    "day_count",
    st.sidebar.selectbox(
        t("ui.interest_day_count_convention"),
        list(DayCount),
        format_func=lambda x: x.value,
        key="day_count",
    ),
)
shift = st.sidebar.checkbox(
    t("ui.show_collection_dates_adjusted_for_polish_sundays_and_holidays"),
    key="shift_dates",
)
fixed_until = None
if st.sidebar.checkbox(t("ui.the_loan_has_a_fixed_rate_period"), key="has_fixed"):
    fixed_until = st.sidebar.date_input(
        t("ui.first_day_after_the_current_fixed_rate_period"),
        value=date(
            start.year + 5,
            start.month,
            min(start.day, monthrange(start.year + 5, start.month)[1]),
        ),
        key="fixed_until",
        format="YYYY-MM-DD",
    )

st.subheader(t("ui.scenarios_and_additional_costs"))
st.caption(t("ui.enter_future_rates_yourself_these_are_scenarios_not_forecasts"))
with st.expander(t("ui.interest_rate_changes")):
    rate_rows = localized_editor(
        pd.DataFrame(
            {"date": pd.Series(dtype="str"), "rate_percent": pd.Series(dtype="float64")}
        ),
        num_rows="dynamic",
        key="rate_editor",
        column_config={
            "date": st.column_config.TextColumn(
                t("ui.change_date_yyyy_mm_dd"), required=True
            ),
            "rate_percent": st.column_config.NumberColumn(
                t("ui.interest_rate"), min_value=0, max_value=100, required=True
            ),
        },
        alt=t("ui.rate_change_dates_and_annual_interest_rates_in_percent"),
    )
annex_rows = pd.DataFrame()
term_rows = pd.DataFrame()
if is_ing:
    with st.expander(t("ui.amendments_installment_selection_and_term_reduction")):
        st.caption(t("ui.enter_the_amendment_effective_date_and_the_principal_and"))
        annex_rows = localized_editor(
            pd.DataFrame(
                {
                    "date": pd.Series(dtype="str"),
                    "target_payment": pd.Series(dtype="float64"),
                    "minimum_payment": pd.Series(dtype="float64"),
                    "maximum_payment": pd.Series(dtype="float64"),
                }
            ),
            num_rows="dynamic",
            key="annex_editor",
            column_config={
                "date": st.column_config.TextColumn(
                    t("ui.effective_date_yyyy_mm_dd"), required=True
                ),
                "target_payment": st.column_config.NumberColumn(
                    t("ui.installment_ceiling_pln"), min_value=0.01, required=True
                ),
                "minimum_payment": st.column_config.NumberColumn(
                    t("ui.ing_minimum_optional"), min_value=0.01
                ),
                "maximum_payment": st.column_config.NumberColumn(
                    t("ui.ing_maximum_optional"), min_value=0.01
                ),
            },
            alt=t("ui.amendment_dates_installment_ceilings_and_optional_ing_limits"),
        )
else:
    with st.expander(t("ui.separate_term_reduction_instructions")):
        st.caption(t("ui.use_a_contractual_payment_date_enter_the_number_of"))
        term_rows = localized_editor(
            pd.DataFrame(
                {
                    "date": pd.Series(dtype="str"),
                    "remaining_months": pd.Series(dtype="int64"),
                }
            ),
            num_rows="dynamic",
            key="term_editor",
            column_config={
                "date": st.column_config.TextColumn(
                    t("ui.instruction_date_yyyy_mm_dd"), required=True
                ),
                "remaining_months": st.column_config.NumberColumn(
                    t("ui.remaining_installments"),
                    min_value=1,
                    max_value=420,
                    step=1,
                    required=True,
                ),
            },
            alt=t("ui.instruction_dates_and_new_installment_counts"),
        )
irregular_rows = pd.DataFrame()
if mode == "irregular":
    st.subheader(t("ui.irregular_overpayments"))
    st.caption(
        t("ui.dates_mean_effective_principal_reduction_dates_in_the_ing")
        if is_ing
        else t("ui.enter_dates_as_yyyy_mm_dd_and_choose_a")
    )
    irregular_rows = localized_editor(
        pd.DataFrame(
            {
                "date": pd.Series(dtype="str"),
                "amount": pd.Series(dtype="float64"),
                "strategy": pd.Series(dtype="str"),
                "shorten": pd.Series(dtype="float64"),
                "reduce": pd.Series(dtype="float64"),
            }
        ),
        num_rows="dynamic",
        key="overpayment_editor",
        column_config={
            "date": st.column_config.TextColumn(
                t("ui.overpayment_date_yyyy_mm_dd"), required=True
            ),
            "amount": st.column_config.NumberColumn(
                t("ui.amount_pln"), min_value=0.01, required=True
            ),
            "shorten": st.column_config.NumberColumn(
                t("ui.for_term_reduction_pln"), min_value=0
            ),
            "reduce": st.column_config.NumberColumn(
                t("ui.for_installment_reduction_pln"), min_value=0
            ),
            "strategy": st.column_config.SelectboxColumn(
                t("ui.strategy"),
                options=[OverpaymentStrategy.REDUCE_INSTALLMENT.value]
                if is_ing
                else [item.value for item in strategies],
                format_func=lambda value: t("strategy." + value),
                required=True,
            ),
        },
        alt=t("ui.irregular_overpayment_dates_amounts_and_allocations"),
    )
with st.expander(t("ui.future_additional_costs_and_insurance")):
    upfront = st.number_input(
        t("ui.one_off_future_costs_pln"), min_value=0.0, value=0.0, key="upfront"
    )
    monthly = st.number_input(
        t("ui.fixed_costs_per_remaining_installment_pln"),
        min_value=0.0,
        value=0.0,
        key="monthly_cost",
    )
    insurance = st.number_input(
        t("ui.annual_balance_based_insurance_rate"),
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        key="insurance",
    )
    st.caption(t("ui.premium_opening_balance_annual_rate_12_one_off_costs"))


@st.cache_data(max_entries=128, ttl=3600)
def run_simulation(
    params: LoanParameters, overpayments: list[Overpayment]
) -> SimulationSummary:
    return calculate_simulation_summary(params, overpayments)


try:
    principal = principal_from_balance(
        decimal_input(amount), accrued, includes_interest=balance_includes_interest
    )
    st.sidebar.caption(
        t("balance.breakdown", principal=t.money(principal), accrued=t.money(accrued))
    )
    params = LoanParameters(
        repayment_model=repayment_model,
        annexes=build_annexes(
            [
                {str(k): v for k, v in row.items()}
                for row in annex_rows.to_dict("records")
            ]
        ),
        amount=principal,
        annual_interest_rate=percent_input(rate),
        start_date=start,
        payment_day=payment_day,
        total_month=int(months),
        first_payment_date=first_date,
        accrued_interest=accrued,
        current_installment=current_payment,
        installment_method=method,
        day_count=day_count,
        shortening_policy=policy,
        shift_collection_dates=shift,
        fixed_until=fixed_until,
        rate_changes=build_rate_changes(
            [
                {str(k): v for k, v in row.items()}
                for row in rate_rows.to_dict("records")
            ]
        ),
        term_changes=build_term_changes(
            [
                {str(k): v for k, v in row.items()}
                for row in term_rows.to_dict("records")
            ]
        ),
        upfront_cost=decimal_input(upfront),
        monthly_cost=decimal_input(monthly),
        annual_balance_insurance_rate=percent_input(insurance),
    )
    ops = build_overpayments(
        params,
        mode,
        strategy,
        op_amount,
        month=int(op_month),
        shorten=shorten,
        reduce=reduce,
        rows=[
            {str(k): v for k, v in row.items()}
            for row in irregular_rows.to_dict("records")
        ],
    )
    if single_date is not None and op_amount > 0:
        ops = [
            Overpayment(op_amount, OverpaymentStrategy.REDUCE_INSTALLMENT, single_date)
        ]
    summary = run_simulation(params, ops)
except (ValueError, ArithmeticError, KeyError, TypeError) as error:
    st.error(t("validation.input_error", error=t.error(error)))
    st.stop()

if is_ing:
    from src.ing import required_overpayment, simulate_ing

    st.subheader(t("ui.overpayment_and_separate_amendment"))
    st.caption(t("ui.on_a_payment_date_the_order_is_installment_rate"))

    @st.cache_data(max_entries=128, ttl=3600)
    def ing_events(params: LoanParameters, ops: list[Overpayment]):
        return simulate_ing(params, ops).events

    event_results = ing_events(params, ops)
    if event_results:
        event_frame = pd.DataFrame([asdict(e) for e in event_results])
        for col in [
            "amount",
            "balance",
            "payment_before",
            "payment_after",
            "target_payment",
        ]:
            event_frame[col] = pd.to_numeric(event_frame[col])
        event_frame["kind"] = event_frame["kind"].map(lambda code: t("event." + code))
        st.dataframe(
            localized_table(
                event_frame,
                [
                    "amount",
                    "balance",
                    "payment_before",
                    "payment_after",
                    "target_payment",
                ],
            ),
            hide_index=True,
            key="ing_events",
            alt=t("ui.history_of_installment_reductions_and_subsequent_amendments"),
            column_config={
                "date": t("ui.date"),
                "kind": t("ui.event"),
                "amount": t("ui.overpayment_pln"),
                "balance": t("ui.principal"),
                "payment_before": t("ui.installment_before"),
                "payment_after": t("ui.installment_after"),
                "remaining_months": t("ui.remaining_installments"),
                "maturity": t("ui.contract_maturity"),
                "target_payment": t("ui.installment_ceiling"),
            },
        )
    if params.annexes:
        without_annex = run_simulation(replace(params, annexes=()), ops)
        st.caption(
            t(
                "summary.annex_effect",
                count=len(without_annex.overpayment_schedule),
                date=without_annex.overpayment_schedule[-1].payment_date,
                saved=t.money(
                    without_annex.total_interest_overpaid
                    - summary.total_interest_overpaid
                ),
            )
        )
    with st.expander(
        t("ui.how_much_should_i_overpay_to_shorten_the_term"), expanded=True
    ):
        st.caption(
            t("ui.the_additional_overpayment_quote_includes_earlier_entered_events_it")
        )
        with st.container(border=True):
            goal_date = st.date_input(
                t("ui.planned_booking_and_amendment_date"),
                value=start,
                key="goal_date",
                format="YYYY-MM-DD",
            )
            goal_months = st.number_input(
                t("ui.number_of_months_to_shorten_the_term"),
                min_value=1,
                max_value=419,
                value=1,
                key="goal_months",
            )
            goal_payment = st.number_input(
                t("ui.maximum_installment_after_amendment_pln"),
                min_value=0.01,
                value=float(
                    current_payment or summary.standard_schedule[0].total_installment
                ),
                key="goal_payment",
            )
            find_goal = st.button(
                t("ui.calculate_required_overpayment"), key="goal_submit"
            )
        goal_signature = (
            params,
            ops,
            goal_date,
            int(goal_months),
            decimal_input(goal_payment),
        )
        if st.session_state.get("goal_signature") != goal_signature:
            st.session_state.pop("goal_result", None)
        if find_goal:
            st.session_state.pop("goal_result", None)
            try:
                goal = required_overpayment(
                    params,
                    goal_date,
                    int(goal_months),
                    decimal_input(goal_payment),
                    ops,
                )
                st.session_state.goal_result = goal
                st.session_state.goal_signature = goal_signature
            except (ValueError, ArithmeticError) as error:
                st.error(t("validation.goal_error", error=t.error(error)))
        if "goal_result" in st.session_state:
            goal = st.session_state.goal_result
            st.metric(t("ui.minimum_additional_overpayment"), t.money(goal.overpayment))
            st.markdown(
                t(
                    "summary.goal",
                    reduced=t.money(goal.payment_after_overpayment),
                    amended=t.money(goal.payment_after_annex),
                    count=goal.remaining_months,
                    date=goal.maturity,
                )
            )
            st.caption(t("ui.this_quote_uses_the_rate_effective_on_the_operation"))

st.subheader(t("ui.future_payment_comparison"))
a, b, c = st.columns(3)
a.metric(t("ui.payable_without_overpayments"), t.money(summary.total_paid_standard))
b.metric(
    t("ui.payable_with_overpayments"), t.money(summary.total_paid_with_overpayments)
)
c.metric(t("ui.interest_saved"), t.money(summary.total_interest_saved))
a, b, c = st.columns(3)
a.metric(t("ui.applied_overpayments"), t.money(summary.total_overpayments_made))
b.metric(t("ui.remaining_payments"), str(len(summary.overpayment_schedule)))
c.metric(
    t("ui.final_settlement_date"), str(summary.overpayment_schedule[-1].payment_date)
)
st.caption(
    t(
        "summary.details",
        principal=t.money(params.amount),
        standard_interest=t.money(summary.total_interest_standard),
        overpaid_interest=t.money(summary.total_interest_overpaid),
        standard_cost=t.money(summary.total_cost_standard),
        overpaid_cost=t.money(summary.total_cost_overpaid),
        unused=t.money(summary.unused_overpayments),
        saved_months=summary.months_saved,
    )
)
with st.expander(t("ui.simulation_assumptions_and_limitations"), expanded=True):
    st.markdown(t("assumptions.details"))
    for warning in summary.warnings:
        st.caption(t(warning))

standard_df = pd.DataFrame([asdict(row) for row in summary.standard_schedule])
overpaid_df = pd.DataFrame([asdict(row) for row in summary.overpayment_schedule])
st.subheader(t("ui.outstanding_principal_over_time"))
chart_parts: list[pd.Series] = []
for label, frame in [
    (t("ui.without_overpayments"), standard_df),
    (t("ui.with_overpayments"), overpaid_df),
]:
    series = pd.Series(
        [float(params.amount)] + [float(x) for x in frame.remaining_balance],
        index=pd.to_datetime([params.start_date] + frame.payment_date.tolist()),
        name=label,
    )
    chart_parts.append(series.groupby(level=0).last())
chart = pd.concat(chart_parts, axis=1).sort_index().ffill().fillna(float(params.amount))
chart_rows = (
    chart.rename_axis("date")
    .reset_index()
    .melt(id_vars="date", var_name="scenario", value_name="balance")
)
chart_rows["balance_label"] = chart_rows.balance.map(t.money)
st.vega_lite_chart(
    chart_rows,
    {
        "mark": "line",
        "encoding": {
            "x": {
                "field": "date",
                "type": "temporal",
                "title": t("ui.contractual_or_final_settlement_date"),
                "axis": {"format": "%Y-%m-%d"},
            },
            "y": {
                "field": "balance",
                "type": "quantitative",
                "title": t("ui.principal_pln"),
                "axis": {"format": ".0f"},
            },
            "color": {"field": "scenario", "type": "nominal", "title": None},
            "tooltip": [
                {
                    "field": "date",
                    "type": "temporal",
                    "title": t("ui.date"),
                    "format": "%Y-%m-%d",
                },
                {"field": "scenario", "type": "nominal", "title": t("ui.scenario")},
                {
                    "field": "balance_label",
                    "type": "nominal",
                    "title": t("ui.principal_pln"),
                },
            ],
        },
        "params": [{"name": "zoom", "select": "interval", "bind": "scales"}],
    },
    alt=t("ui.balance_comparison_from_the_start_date_to_repayment"),
)

st.caption(t("ui.table_and_chart_balances_are_aggregated_at_installment_dates"))
for tab, frame, name in zip(
    st.tabs([t("ui.without_overpayments"), t("ui.with_overpayments")]),
    [standard_df, overpaid_df],
    ["standard", "overpaid"],
):
    with tab:
        display = frame.copy()
        for column in [
            "total_installment",
            "principal",
            "interest",
            "overpayment",
            "remaining_balance",
            "additional_cost",
            "annual_interest_rate",
        ]:
            display[column] = display[column].astype(float)
        st.dataframe(
            localized_table(
                display,
                [
                    "total_installment",
                    "principal",
                    "interest",
                    "overpayment",
                    "remaining_balance",
                    "additional_cost",
                ],
            ),
            hide_index=True,
            key=f"schedule_{name}",
            alt=t(
                "schedule.alt",
                scenario=t("ui.without_overpayments")
                if name == "standard"
                else t("ui.with_overpayments"),
            ),
            column_config={
                "installment_number": st.column_config.NumberColumn(
                    t("ui.payment_number"), format="%d"
                ),
                "payment_date": st.column_config.DateColumn(
                    t("ui.settlement_date"), format="YYYY-MM-DD"
                ),
                "collection_date": st.column_config.DateColumn(
                    t("ui.collection_date"), format="YYYY-MM-DD"
                ),
                "days_in_period": st.column_config.NumberColumn(
                    t("ui.days_in_period"), format="%d"
                ),
                "total_installment": st.column_config.NumberColumn(
                    t("ui.installment_pln")
                ),
                "principal": st.column_config.NumberColumn(t("ui.principal_pln")),
                "interest": st.column_config.NumberColumn(t("ui.interest_pln")),
                "overpayment": st.column_config.NumberColumn(t("ui.overpayment_pln")),
                "remaining_balance": st.column_config.NumberColumn(
                    t("ui.outstanding_principal_pln")
                ),
                "additional_cost": st.column_config.NumberColumn(
                    t("ui.additional_costs_pln")
                ),
                "annual_interest_rate": st.column_config.NumberColumn(
                    t("ui.rate_at_period_end")
                ),
                "contractual_months_remaining": st.column_config.NumberColumn(
                    t("ui.remaining_contractual_installments"), format="%d"
                ),
            },
        )
        st.download_button(
            t("ui.download_csv"),
            frame.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{name}.csv",
            mime="text/csv",
            key=f"download_{name}",
        )
