"""Streamlit interface; financial scenario construction lives in src.scenarios."""

from calendar import monthrange
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

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
)

st.set_page_config(
    page_title="Kalkulator nadpłaty kredytu",
    page_icon=":material/payments:",
    layout="wide",
)
st.title("Kalkulator nadpłaty kredytu hipotecznego")
st.caption(
    "Dzienne naliczanie odsetek prostych. Wyniki zależą od przyjętych zasad i scenariuszy oprocentowania."
)

st.sidebar.header("Parametry kredytu")
repayment_model = st.sidebar.selectbox(
    "Model spłaty",
    list(RepaymentModel),
    index=1,
    format_func=lambda x: x.value,
    key="repayment_model",
)
is_ing = repayment_model == RepaymentModel.ING

amount = st.sidebar.number_input(
    "Pozostały kapitał (PLN)", min_value=0.01, value=300000.0, step=1000.0, key="amount"
)
rate = st.sidebar.number_input(
    "Oprocentowanie roczne (%)",
    min_value=0.0,
    max_value=20.0,
    value=7.5,
    step=0.01,
    key="rate",
)
months = st.sidebar.number_input(
    "Pozostała liczba rat", min_value=1, max_value=420, value=360, step=12, key="months"
)
payment_day = st.sidebar.slider("Umowny dzień raty", 1, 31, 10, key="payment_day")

st.sidebar.header("Nadpłaty")
modes = {
    "Brak nadpłat": "none",
    "Regularne miesięczne": "regular",
    "Jednorazowa": "single",
    "Nieregularne": "irregular",
}
mode_label = st.sidebar.radio("Tryb nadpłat", list(modes), key="mode")
mode = modes[mode_label]
strategies = {
    "Obniżenie raty": OverpaymentStrategy.REDUCE_INSTALLMENT,
    "Skrócenie okresu": OverpaymentStrategy.SHORTEN_TERM,
    "Mixed": OverpaymentStrategy.MIXED,
}
strategy = OverpaymentStrategy.REDUCE_INSTALLMENT
op_amount = Decimal("0")
shorten = reduce = None
op_month = 1
if mode in ("regular", "single"):
    if not is_ing:
        strategy = strategies[
            st.sidebar.selectbox("Strategia", list(strategies), key="strategy")
        ]
    else:
        st.sidebar.caption(
            "Każda nadpłata obniża ratę. Skrócenie wymaga osobnego aneksu."
        )
    if mode == "single":
        if "op_month" not in st.session_state:
            st.session_state.op_month = min(12, int(months))
        elif int(st.session_state.op_month) > int(months):
            st.session_state.op_month = int(months)
        selected_month = st.sidebar.number_input(
            "Numer raty z nadpłatą",
            1,
            int(months),
            value=None,
            key="op_month",
        )
        op_month = int(selected_month or 1)
    if strategy == OverpaymentStrategy.MIXED:
        shorten = decimal_input(
            st.sidebar.number_input(
                "Część na skrócenie (PLN)",
                min_value=0.0,
                value=500.0,
                step=100.0,
                key="shorten",
            )
        )
        reduce = decimal_input(
            st.sidebar.number_input(
                "Część na obniżenie raty (PLN)",
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
                "Kwota nadpłaty (PLN)",
                min_value=0.0,
                value=1000.0,
                step=100.0,
                key="op_amount",
            )
        )
    if op_amount == 0:
        st.sidebar.info("Kwota 0 zł oznacza brak dodatkowych wpłat.")

single_date = None
if (
    is_ing
    and mode == "single"
    and st.sidebar.checkbox("Podaj datę zaksięgowania nadpłaty", key="exact_op_date")
):
    single_date = st.sidebar.date_input(
        "Data zaksięgowania nadpłaty", value=date.today(), key="single_date"
    )

st.sidebar.header("Stan kredytu na dzień")
start = st.sidebar.date_input(
    "Data stanu kapitału", value=date.today(), key="start_date"
)
first_date = None
if st.sidebar.checkbox("Podaj dokładny termin najbliższej raty", key="custom_first"):
    first_date = st.sidebar.date_input(
        "Najbliższa rata",
        value=get_next_payment_date(start, payment_day),
        key="first_date",
    )
accrued = decimal_input(
    st.sidebar.number_input(
        "Odsetki naliczone przed datą stanu (PLN)",
        min_value=0.0,
        value=0.0,
        key="accrued",
    )
)
current_payment = None
if st.sidebar.checkbox("Użyj aktualnej raty z banku", key="use_current"):
    current_payment = decimal_input(
        st.sidebar.number_input(
            "Aktualna rata kapitałowo-odsetkowa (PLN)",
            min_value=0.01,
            value=2000.0,
            key="current_payment",
        )
    )

st.sidebar.header("Założenia obliczeń")
if is_ing:
    method = InstallmentMethod.CALENDAR
    policy = ShorteningPolicy.KEEP_PAYMENT
    st.sidebar.caption(
        "Rata kalendarzowa; model wymaga porównania z harmonogramem ING."
    )
else:
    method = st.sidebar.selectbox(
        "Sposób wyliczania raty",
        list(InstallmentMethod),
        index=1,
        format_func=lambda x: x.value,
        key="method",
    )
    policy = st.sidebar.selectbox(
        "Sposób skracania okresu",
        list(ShorteningPolicy),
        format_func=lambda x: x.value,
        key="policy",
    )
day_count = st.sidebar.selectbox(
    "Konwencja naliczania odsetek",
    list(DayCount),
    format_func=lambda x: x.value,
    key="day_count",
)
shift = st.sidebar.checkbox(
    "Pokaż pobranie po niedzielach i świętach w Polsce", key="shift_dates"
)
fixed_until = None
if st.sidebar.checkbox("Kredyt ma okresowo stałe oprocentowanie", key="has_fixed"):
    fixed_until = st.sidebar.date_input(
        "Pierwszy dzień po obecnym okresie stałym",
        value=date(
            start.year + 5,
            start.month,
            min(start.day, monthrange(start.year + 5, start.month)[1]),
        ),
        key="fixed_until",
    )

st.subheader("Scenariusze i dodatkowe koszty")
st.caption(
    "Przyszłe stopy wpisujesz samodzielnie. Nie są prognozą. Brak zmiany oznacza utrzymanie ostatniej stopy."
)
with st.expander("Zmiany oprocentowania"):
    rate_rows = st.data_editor(
        pd.DataFrame(
            {"date": pd.Series(dtype="str"), "rate_percent": pd.Series(dtype="float64")}
        ),
        num_rows="dynamic",
        key="rate_editor",
        column_config={
            "date": st.column_config.TextColumn(
                "Data zmiany (YYYY-MM-DD)", required=True
            ),
            "rate_percent": st.column_config.NumberColumn(
                "Oprocentowanie (%)", min_value=0, max_value=100, required=True
            ),
        },
        alt="Daty zmian i roczne oprocentowanie w procentach",
    )
annex_rows = pd.DataFrame()
term_rows = pd.DataFrame()
if is_ing:
    with st.expander("Aneksy — wybór raty i skrócenie okresu"):
        st.caption(
            "Podaj datę wejścia aneksu w życie i limit raty kapitałowo-odsetkowej. "
            "Wybieramy najkrótszy pełny okres z ratą nieprzekraczającą limitu; wyliczona rata może być niższa. "
            "Opcjonalne minimum i maksimum przepisz z ING. Nie wyznaczamy bankowych widełek ani uprawnienia do bezpłatnego aneksu."
        )
        annex_rows = st.data_editor(
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
                    "Wejście w życie (YYYY-MM-DD)", required=True
                ),
                "target_payment": st.column_config.NumberColumn(
                    "Limit raty (PLN)", min_value=0.01, required=True
                ),
                "minimum_payment": st.column_config.NumberColumn(
                    "Minimum ING (opcjonalne)", min_value=0.01
                ),
                "maximum_payment": st.column_config.NumberColumn(
                    "Maksimum ING (opcjonalne)", min_value=0.01
                ),
            },
            alt="Daty aneksów, limity rat i opcjonalne widełki ING",
        )
else:
    with st.expander("Oddzielne dyspozycje skrócenia umowy"):
        st.caption(
            "Data musi być umownym terminem raty; podaj liczbę rat pozostałych PO tej racie. Możliwe warunki i opłaty sprawdź w ING."
        )
        term_rows = st.data_editor(
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
                    "Data dyspozycji (YYYY-MM-DD)", required=True
                ),
                "remaining_months": st.column_config.NumberColumn(
                    "Pozostałe raty", min_value=1, max_value=420, step=1, required=True
                ),
            },
            alt="Daty dyspozycji i nowa liczba rat",
        )
irregular_rows = pd.DataFrame()
if mode == "irregular":
    st.subheader("Lista nieregularnych nadpłat")
    st.caption(
        "Daty oznaczają zaksięgowanie nadpłaty na kapitale. W modelu ING wybierz Obniżenie raty; aneksy wpisz osobno."
        if is_ing
        else "Podaj daty YYYY-MM-DD i wybierz strategię. Dla Mixed uzupełnij obie części nadpłaty."
    )
    irregular_rows = st.data_editor(
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
                "Data nadpłaty (YYYY-MM-DD)", required=True
            ),
            "amount": st.column_config.NumberColumn(
                "Kwota (PLN)", min_value=0.01, required=True
            ),
            "shorten": st.column_config.NumberColumn("Na skrócenie (PLN)", min_value=0),
            "reduce": st.column_config.NumberColumn(
                "Na obniżenie raty (PLN)", min_value=0
            ),
            "strategy": st.column_config.SelectboxColumn(
                "Strategia",
                options=["Obniżenie raty"] if is_ing else list(strategies),
                required=True,
            ),
        },
        alt="Daty, kwoty i podział nieregularnych nadpłat",
    )
with st.expander("Przyszłe koszty dodatkowe i ubezpieczenia"):
    upfront = st.number_input(
        "Jednorazowe przyszłe koszty (PLN)", min_value=0.0, value=0.0, key="upfront"
    )
    monthly = st.number_input(
        "Stałe koszty za każdą pozostałą ratę (PLN)",
        min_value=0.0,
        value=0.0,
        key="monthly_cost",
    )
    insurance = st.number_input(
        "Roczna składka zależna od salda (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        key="insurance",
    )
    st.caption(
        "Składka = saldo na początku okresu × stawka roczna / 12. Jednorazowe koszty dodajemy do obu scenariuszy; koszty już poniesione nie należą do przyszłych płatności."
    )


@st.cache_data(max_entries=128, ttl=3600)
def run_simulation(
    params: LoanParameters, overpayments: list[Overpayment]
) -> SimulationSummary:
    return calculate_simulation_summary(params, overpayments)


try:
    params = LoanParameters(
        repayment_model=repayment_model,
        annexes=build_annexes(
            [
                {str(k): v for k, v in row.items()}
                for row in annex_rows.to_dict("records")
            ]
        ),
        amount=decimal_input(amount),
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
        rate_changes=build_rate_changes(rate_rows.to_dict("records")),
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
    st.error(f"Sprawdź dane wejściowe: {error}")
    st.stop()

if is_ing:
    from src.ing import required_overpayment, simulate_ing

    st.subheader("Nadpłata i osobny aneks")
    st.caption(
        "W dniu raty kolejność to: rata, zmiana stopy, nadpłata, aneks. Odsetki naliczamy codziennie, bez kapitalizacji."
    )

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
        st.dataframe(
            event_frame,
            hide_index=True,
            key="ing_events",
            alt="Historia obniżenia raty i późniejszych aneksów",
            column_config={
                "date": "Data",
                "kind": "Zdarzenie",
                "amount": "Nadpłata (PLN)",
                "balance": "Kapitał",
                "payment_before": "Rata przed",
                "payment_after": "Rata po",
                "remaining_months": "Pozostałe raty",
                "maturity": "Koniec umowy",
                "target_payment": "Limit raty",
            },
        )
    if params.annexes:
        without_annex = run_simulation(replace(params, annexes=()), ops)
        st.caption(
            f"Po samych nadpłatach: {len(without_annex.overpayment_schedule)} płatności, "
            f"koniec {without_annex.overpayment_schedule[-1].payment_date}. "
            f"Dodatkowa oszczędność odsetek po aneksach: "
            f"{without_annex.total_interest_overpaid - summary.total_interest_overpaid:,.2f} PLN."
        )
    with st.expander(
        "Ile nadpłacić, aby skrócić okres bez zwiększania raty?", expanded=True
    ):
        st.caption(
            "Wycena dodatkowej nadpłaty uwzględnia wcześniejsze wpisane zdarzenia. Zakłada aneks tego samego dnia; nie dodaje automatycznie operacji do harmonogramu. Limit dotyczy rat kapitałowo-odsetkowych, bez ubezpieczeń i opłat."
        )
        with st.form("required_overpayment_form"):
            goal_date = st.date_input(
                "Planowana data zaksięgowania i aneksu", value=start, key="goal_date"
            )
            goal_months = st.number_input(
                "O ile miesięcy skrócić okres",
                min_value=1,
                max_value=419,
                value=1,
                key="goal_months",
            )
            goal_payment = st.number_input(
                "Maksymalna rata po aneksie (PLN)",
                min_value=0.01,
                value=float(
                    current_payment or summary.standard_schedule[0].total_installment
                ),
                key="goal_payment",
            )
            find_goal = st.form_submit_button("Oblicz wymaganą nadpłatę")
        if find_goal:
            try:
                goal = required_overpayment(
                    params,
                    goal_date,
                    int(goal_months),
                    decimal_input(goal_payment),
                    ops,
                )
                st.metric(
                    "Minimalna dodatkowa nadpłata", f"{goal.overpayment:,.2f} PLN"
                )
                st.markdown(
                    f"Po samej nadpłacie rata: **{goal.payment_after_overpayment:,.2f} PLN**. "
                    f"Po aneksie: **{goal.payment_after_annex:,.2f} PLN**, "
                    f"pozostałe raty: **{goal.remaining_months}**, koniec: **{goal.maturity}**."
                )
                st.caption(
                    "To wycena przy stopie obowiązującej w dacie operacji. Późniejsze zmiany stopy mogą zmienić ratę. Przed akceptacją aneksu porównaj dostępny okres i widełki w ING."
                )
            except (ValueError, ArithmeticError) as error:
                st.error(f"Nie można wyznaczyć nadpłaty: {error}")

st.subheader("Porównanie przyszłych płatności")
a, b, c = st.columns(3)
a.metric("Do zapłaty bez nadpłat", f"{summary.total_paid_standard:,.2f} PLN")
b.metric("Do zapłaty z nadpłatami", f"{summary.total_paid_with_overpayments:,.2f} PLN")
c.metric("Zaoszczędzone odsetki", f"{summary.total_interest_saved:,.2f} PLN")
a, b, c = st.columns(3)
a.metric("Wykorzystane nadpłaty", f"{summary.total_overpayments_made:,.2f} PLN")
b.metric("Pozostała liczba płatności", str(len(summary.overpayment_schedule)))
c.metric(
    "Data końcowego rozliczenia", str(summary.overpayment_schedule[-1].payment_date)
)
st.caption(
    f"Kapitał: {params.amount:,.2f} PLN | Odsetki bez nadpłat: {summary.total_interest_standard:,.2f} PLN | "
    f"Odsetki z nadpłatami: {summary.total_interest_overpaid:,.2f} PLN | "
    f"Koszt poza kapitałem bez/z nadpłatami: {summary.total_cost_standard:,.2f} / {summary.total_cost_overpaid:,.2f} PLN | "
    f"Niewykorzystane planowane nadpłaty: {summary.unused_overpayments:,.2f} PLN | Mniej rat: {summary.months_saved}"
)
with st.expander("Założenia i ograniczenia symulacji", expanded=True):
    st.markdown(
        "Nadpłata w dacie początku obniża kapitał od tej daty. W dniu raty najpierw rozliczamy ratę, potem nadpłatę. "
        "W modelu ING po nadpłacie przeliczamy ratę z uwzględnieniem już naliczonych odsetek na najbliższy termin. W trybie ogólnym na kolejny termin. Zmiana stopy przelicza pierwszą ratę obejmującą nową stopę. Całkowitą spłatę kapitału i należnych odsetek rozliczamy w dniu nadpłaty. "
        "W trybie ogólnym rata kalendarzowa ma minimum pokrywające odsetki najdłuższego okresu. W modelu ING szukamy minimalnej raty w groszach rozliczającej saldo i odsetki do końca okresu, z końcową ratą nieprzekraczającą tego limitu. Nie jest to potwierdzony algorytm banku. Odsetki liczymy od dat umownych; przesunięcie daty pobrania nie zmienia odsetek. "
        "ING standardowo obniża ratę po nadpłacie, a skrócenie umowy jest osobną dyspozycją. "
        "[Zasady obsługi kredytu w ING](https://www.ing.pl/indywidualni/kredyty-i-pozyczki/kredyt-hipoteczny/mam-juz-kredyt). "
        "Nie potwierdzono zgodności z Twoją konkretną umową. Transze, karencja, zaległości i przewalutowanie nie są obsługiwane."
    )
    for warning in summary.warnings:
        st.caption(warning)

standard_df = pd.DataFrame([asdict(row) for row in summary.standard_schedule])
overpaid_df = pd.DataFrame([asdict(row) for row in summary.overpayment_schedule])
st.subheader("Pozostały kapitał w czasie")
chart_parts: list[pd.Series] = []
for label, frame in [("Bez nadpłat", standard_df), ("Z nadpłatami", overpaid_df)]:
    series = pd.Series(
        [float(params.amount)] + [float(x) for x in frame.remaining_balance],
        index=pd.to_datetime([params.start_date] + frame.payment_date.tolist()),
        name=label,
    )
    chart_parts.append(series.groupby(level=0).last())
chart = pd.concat(chart_parts, axis=1).sort_index().ffill().fillna(float(params.amount))
st.line_chart(
    chart,
    x_label="Data umowna lub końcowego rozliczenia",
    y_label="Kapitał (PLN)",
    alt="Porównanie salda od daty początkowej do spłaty",
)
st.caption(
    "Saldo w tabeli i na wykresie jest agregowane przy ratach; nadpłaty między ratami wpływają na odsetki od ich rzeczywistych dat."
)
for tab, frame, name in zip(
    st.tabs(["Bez nadpłat", "Z nadpłatami"]),
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
            display,
            hide_index=True,
            key=f"schedule_{name}",
            alt=f"Harmonogram {name}",
            column_config={
                "installment_number": st.column_config.NumberColumn(
                    "Nr płatności", format="%d"
                ),
                "payment_date": st.column_config.DateColumn(
                    "Termin rozliczenia", format="YYYY-MM-DD"
                ),
                "collection_date": st.column_config.DateColumn(
                    "Data pobrania", format="YYYY-MM-DD"
                ),
                "days_in_period": st.column_config.NumberColumn(
                    "Liczba dni", format="%d"
                ),
                "total_installment": st.column_config.NumberColumn(
                    "Rata (PLN)", format="%.2f"
                ),
                "principal": st.column_config.NumberColumn(
                    "Kapitał (PLN)", format="%.2f"
                ),
                "interest": st.column_config.NumberColumn(
                    "Odsetki (PLN)", format="%.2f"
                ),
                "overpayment": st.column_config.NumberColumn(
                    "Nadpłata (PLN)", format="%.2f"
                ),
                "remaining_balance": st.column_config.NumberColumn(
                    "Pozostały kapitał (PLN)", format="%.2f"
                ),
                "additional_cost": st.column_config.NumberColumn(
                    "Koszty dodatkowe (PLN)", format="%.2f"
                ),
                "annual_interest_rate": st.column_config.NumberColumn(
                    "Stopa na koniec okresu", format="percent"
                ),
                "contractual_months_remaining": st.column_config.NumberColumn(
                    "Pozostałe raty umowne", format="%d"
                ),
            },
        )
        st.download_button(
            "Pobierz CSV",
            frame.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{name}.csv",
            mime="text/csv",
            key=f"download_{name}",
        )
