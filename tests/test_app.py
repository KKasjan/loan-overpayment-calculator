from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def app_start() -> AppTest:
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert not app.error
    from src.models import RepaymentModel

    app.selectbox(key="repayment_model").set_value(RepaymentModel.GENERAL).run()
    assert not app.exception
    assert not app.error
    return app


@pytest.mark.parametrize("month", [1, 12])
def test_overpayment_occurs_only_in_selected_month(month: int) -> None:
    app = app_start()
    app.radio(key="mode").set_value("Jednorazowa").run()
    app.number_input(key="op_month").set_value(month)
    app.number_input(key="op_amount").set_value(1000.0).run()
    assert not app.exception
    assert not app.error
    schedule = app.tabs[1].dataframe[0].value
    paid = schedule[schedule.overpayment > 0]
    assert len(paid) == 1
    assert paid.iloc[0].installment_number == month
    assert paid.iloc[0].overpayment == 1000.0
    assert schedule.overpayment.sum() == 1000.0


def test_short_term_single_overpayment_does_not_crash() -> None:
    app = app_start()
    app.number_input(key="months").set_value(3).run()
    app.radio(key="mode").set_value("Jednorazowa").run()
    assert not app.exception
    assert not app.error
    assert app.number_input(key="op_month").value == 3
    app.number_input(key="months").set_value(1).run()
    assert not app.exception
    assert not app.error
    assert app.number_input(key="op_month").value == 1


def test_zero_mixed_means_no_overpayments() -> None:
    app = app_start()
    app.radio(key="mode").set_value("Regularne miesięczne").run()
    app.selectbox(key="strategy").set_value("Mixed").run()
    app.number_input(key="shorten").set_value(0.0)
    app.number_input(key="reduce").set_value(0.0).run()
    assert not app.exception
    assert not app.error
    assert app.tabs[1].dataframe[0].value.overpayment.sum() == 0


def test_invalid_first_payment_is_reported_without_traceback() -> None:
    app = app_start()
    app.checkbox(key="custom_first").check().run()
    app.date_input(key="first_date").set_value(
        app.date_input(key="start_date").value
    ).run()
    assert not app.exception
    assert app.error


def test_dashboard_labels_describe_future_payments_and_end_date() -> None:
    app = app_start()
    labels = {m.label for m in app.metric}
    assert "Do zapłaty bez nadpłat" in labels
    assert "Data końcowego rozliczenia" in labels
    assert len(app.tabs[0].dataframe[0].value) > 0
    assert len(app.tabs[1].dataframe[0].value) > 0


def test_irregular_editor_adds_two_dated_overpayments() -> None:
    from datetime import date

    app = app_start()
    app.date_input(key="start_date").set_value(date(2026, 1, 10)).run()
    app.radio(key="mode").set_value("Nieregularne").run()
    app.session_state["overpayment_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [
            {"date": "2026-01-15", "amount": 1000.0, "strategy": "REDUCE_INSTALLMENT"},
            {"date": "2026-02-15", "amount": 2000.0, "strategy": "SHORTEN_TERM"},
        ],
    }
    app.run()
    assert not app.exception
    assert not app.error
    assert app.tabs[1].dataframe[0].value.overpayment.sum() == 3000.0


def test_rate_editor_applies_change_and_invalid_rate_is_reported() -> None:
    from datetime import date

    app = app_start()
    app.date_input(key="start_date").set_value(date(2026, 1, 10)).run()
    app.session_state["rate_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": "2026-02-15", "rate_percent": 5.0}],
    }
    app.run()
    assert not app.exception
    assert not app.error
    schedule = app.tabs[1].dataframe[0].value
    assert schedule.iloc[1].annual_interest_rate == 0.05
    app.session_state["rate_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": "2026-02-15", "rate_percent": -1.0}],
    }
    app.run()
    assert not app.exception
    assert app.error


def test_term_editor_updates_accelerated_scenario_only() -> None:
    from datetime import date

    app = app_start()
    app.date_input(key="start_date").set_value(date(2026, 1, 10)).run()
    app.session_state["term_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": "2026-02-10", "remaining_months": 10}],
    }
    app.run()
    assert not app.exception
    assert not app.error
    assert len(app.tabs[0].dataframe[0].value) == 360
    assert len(app.tabs[1].dataframe[0].value) == 11


def test_ing_default_has_separate_annex_and_inverse_quote() -> None:
    from src.models import RepaymentModel

    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert not app.error
    assert app.selectbox(key="repayment_model").value == RepaymentModel.ING
    assert not any(s.key == "strategy" for s in app.selectbox)
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="rate").set_value(0.0).run()
    app.number_input(key="goal_payment").set_value(1000.0)
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    metric = next(m for m in app.metric if m.label == "Minimalna dodatkowa nadpłata")
    assert metric.value == "1,000.00 PLN"


def test_ing_exact_date_and_midperiod_annex_event_table() -> None:
    from datetime import date

    app = AppTest.from_file(str(APP_PATH)).run()
    app.date_input(key="start_date").set_value(date(2026, 1, 15))
    app.slider(key="payment_day").set_value(15)
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="rate").set_value(0.0).run()
    app.radio(key="mode").set_value("Jednorazowa").run()
    app.checkbox(key="exact_op_date").check().run()
    app.date_input(key="single_date").set_value(date(2026, 1, 20))
    app.number_input(key="op_amount").set_value(300.0)
    app.session_state["annex_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": "2026-01-21", "target_payment": 1100.0}],
    }
    app.run()
    assert not app.exception
    assert not app.error
    events = next(
        frame.value
        for frame in app.dataframe
        if "payment_before" in frame.value.columns
    )
    assert events.iloc[0].payment_after == 975.0
    assert events.iloc[1].payment_after == 1063.64
    assert len(app.tabs[1].dataframe[0].value) == 11


def test_ing_invalid_annex_shows_input_error() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    when = app.date_input(key="start_date").value.isoformat()
    app.session_state["annex_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": when, "target_payment": 1.0}],
    }
    app.run()
    assert not app.exception
    assert app.error


def test_total_bank_balance_and_principal_input_produce_identical_schedules() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="accrued").set_value(100.0).run()
    expected = app.tabs[0].dataframe[0].value.copy()
    app.selectbox(key="balance_kind").set_value(
        "Łączne saldo: kapitał + naliczone odsetki"
    ).run()
    app.number_input(key="amount").set_value(12100.0).run()
    assert not app.exception
    assert not app.error
    assert app.tabs[0].dataframe[0].value.equals(expected)
    app.number_input(key="accrued").set_value(12100.0).run()
    assert not app.exception
    assert app.error
