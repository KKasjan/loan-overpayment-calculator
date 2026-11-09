"""Remaining user-facing settings and recoverable quote failures."""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def app_start(language: str) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.date_input(key="start_date").set_value(date(2026, 1, 15))
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="rate").set_value(0.0).run()
    app.get("button_group")[0].set_value(language).run()
    assert not app.exception
    assert not app.error
    return app


@pytest.mark.parametrize("language", ["pl", "en"])
def test_bank_installment_setting_changes_schedule_without_changing_principal(
    language: str,
) -> None:
    app = app_start(language)
    app.checkbox(key="use_current").check().run()
    app.number_input(key="current_payment").set_value(1500.0).run()
    assert not app.exception
    assert not app.error
    schedule = app.tabs[0].dataframe[0].value
    assert schedule.iloc[0].total_installment == 1500.0
    assert schedule.principal.sum() == 12000.0
    assert schedule.iloc[-1].remaining_balance == 0


@pytest.mark.parametrize("language", ["pl", "en"])
def test_fixed_rate_end_setting_produces_translated_extrapolation_warning(
    language: str,
) -> None:
    app = app_start(language)
    app.checkbox(key="has_fixed").check().run()
    app.date_input(key="fixed_until").set_value(date(2026, 6, 15)).run()
    assert not app.exception
    assert not app.error
    phrase = (
        "wykracza poza okres"
        if language == "pl"
        else "extends beyond the fixed-rate period"
    )
    assert any(phrase in caption.value for caption in app.caption)


@pytest.mark.parametrize("language", ["pl", "en"])
def test_infeasible_goal_displays_error_and_clears_previous_result(
    language: str,
) -> None:
    app = app_start(language)
    app.number_input(key="goal_payment").set_value(1000.0)
    app.button(key="goal_submit").click().run()
    assert "goal_result" in app.session_state
    app.number_input(key="goal_months").set_value(12)
    app.button(key="goal_submit").click().run()
    assert not app.exception
    assert "goal_result" not in app.session_state
    assert app.error
    phrase = (
        "przynajmniej jedna rata" if language == "pl" else "At least one installment"
    )
    assert phrase in app.error[0].value


def test_bank_installment_below_interest_is_a_handled_input_error() -> None:
    app = app_start("en")
    app.checkbox(key="use_current").check().run()
    app.number_input(key="rate").set_value(12.0)
    app.number_input(key="current_payment").set_value(1.0).run()
    assert not app.exception
    assert "does not cover interest" in app.error[0].value
