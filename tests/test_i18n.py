"""Translation completeness and financial-state preservation across languages."""

import ast
from decimal import Decimal
from pathlib import Path
from string import Formatter

import pytest
from streamlit.testing.v1 import AppTest

from src.i18n import LANGUAGES, Translator, load_catalog
from src.messages import InputError
from src.models import OverpaymentStrategy, RepaymentModel

ROOT = Path(__file__).resolve().parents[1]


def switch(app: AppTest, language: str) -> AppTest:
    app.get("button_group")[0].set_value(language).run()
    assert not app.exception
    assert not app.error
    return app


def test_catalogs_have_matching_keys_and_placeholders() -> None:
    pl, en = load_catalog("pl"), load_catalog("en")
    assert pl.keys() == en.keys()
    for key in pl:
        assert pl[key].strip() and en[key].strip(), key

        def fields(template: str) -> set[str]:
            return {
                name
                for _, name, _, _ in Formatter().parse(template)
                if name is not None
            }

        assert fields(pl[key]) == fields(en[key]), key


def test_all_literal_translation_and_domain_codes_exist() -> None:
    catalog = load_catalog("en")
    for path in [ROOT / "app.py", *list((ROOT / "src").glob("*.py"))]:
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"t", "InputError", "CalculationError"}
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    assert node.args[0].value in catalog, (path, node.args[0].value)


@pytest.mark.parametrize(
    "language,expected", [("pl", "4 748,90 zł"), ("en", "4,748.90 PLN")]
)
def test_money_localization_is_presentation_only(language: str, expected: str) -> None:
    amount = Decimal("4748.90")
    assert Translator(language).money(amount) == expected
    assert amount == Decimal("4748.90")


def test_domain_error_has_stable_code_and_translated_fields() -> None:
    code = "validation.name_use_at_most_two_decimal_places"
    error = InputError(code, name="Outstanding principal")
    assert "Outstanding principal" in str(error)
    assert "Pozostały kapitał" in Translator("pl").error(error)
    assert "Outstanding principal" in Translator("en").error(error)
    assert error.code == code


def test_default_polish_and_language_switch_preserve_single_overpayment() -> None:
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not app.exception
    assert app.title[0].value == "Kalkulator nadpłaty kredytu hipotecznego"
    app.radio(key="mode").set_value("single").run()
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="op_month").set_value(3)
    app.number_input(key="op_amount").set_value(300.0).run()
    before = app.tabs[1].dataframe[0].value.copy()
    switch(app, "en")
    assert app.title[0].value == "Mortgage overpayment calculator"
    assert app.radio(key="mode").value == "single"
    assert app.number_input(key="op_month").value == 3
    assert app.tabs[1].dataframe[0].value.equals(before)
    switch(app, "pl")
    assert app.tabs[1].dataframe[0].value.equals(before)


def test_switch_preserves_mixed_strategy_and_amounts() -> None:
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.selectbox(key="repayment_model").set_value(RepaymentModel.GENERAL).run()
    app.radio(key="mode").set_value("regular").run()
    app.selectbox(key="strategy").set_value(OverpaymentStrategy.MIXED).run()
    app.number_input(key="shorten").set_value(200.0)
    app.number_input(key="reduce").set_value(100.0).run()
    before = app.tabs[1].dataframe[0].value.copy()
    for language in ["en", "pl", "en"]:
        switch(app, language)
        assert app.selectbox(key="strategy").value == OverpaymentStrategy.MIXED
        assert app.number_input(key="shorten").value == 200.0
        assert app.number_input(key="reduce").value == 100.0
        assert app.tabs[1].dataframe[0].value.equals(before)


def test_switch_preserves_irregular_rows_without_duplicate_application() -> None:
    from datetime import date

    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.date_input(key="start_date").set_value(date(2026, 1, 15)).run()
    app.radio(key="mode").set_value("irregular").run()
    app.session_state["overpayment_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [
            {"date": "2026-01-20", "amount": 300.0, "strategy": "REDUCE_INSTALLMENT"}
        ],
    }
    app.run()
    assert not app.exception
    before = app.tabs[1].dataframe[0].value.copy()
    for language in ["en", "pl", "en"]:
        switch(app, language)
        assert app.tabs[1].dataframe[0].value.equals(before)
        assert app.tabs[1].dataframe[0].value.overpayment.sum() == 300.0


def test_switch_preserves_quote_result_and_its_inputs() -> None:
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="rate").set_value(0.0).run()
    app.number_input(key="goal_payment").set_value(1000.0)
    app.button(key="goal_submit").click().run()
    expected = app.session_state.goal_result
    for language in ["en", "pl"]:
        switch(app, language)
        assert app.session_state.goal_result == expected
        label = Translator(language)("ui.minimum_additional_overpayment")
        metric = next(m for m in app.metric if m.label == label)
        assert metric.value == Translator(language).money(Decimal("1000"))
    app.number_input(key="goal_months").set_value(2).run()
    assert "goal_result" not in app.session_state


@pytest.mark.parametrize("language", LANGUAGES)
def test_invalid_date_is_translated_without_exposing_exception(language: str) -> None:
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    switch(app, language)
    app.checkbox(key="custom_first").check().run()
    app.date_input(key="first_date").set_value(
        app.date_input(key="start_date").value
    ).run()
    assert not app.exception
    text = app.error[0].value
    assert ("Pierwsza rata" if language == "pl" else "First payment") in text


def test_switch_preserves_rate_changes_and_amendments() -> None:
    from datetime import date

    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.date_input(key="start_date").set_value(date(2026, 1, 15))
    app.number_input(key="amount").set_value(12000.0)
    app.number_input(key="months").set_value(12)
    app.number_input(key="rate").set_value(0.0).run()
    for key, row in [
        ("rate_editor", {"date": "2026-06-20", "rate_percent": 2.0}),
        ("annex_editor", {"date": "2026-01-21", "target_payment": 1200.0}),
    ]:
        app.session_state[key] = {
            "edited_rows": {},
            "deleted_rows": [],
            "added_rows": [row],
        }
    app.run()
    assert not app.exception
    assert not app.error
    before = app.tabs[1].dataframe[0].value.copy()
    for language in ["en", "pl", "en"]:
        switch(app, language)
        assert app.tabs[1].dataframe[0].value.equals(before)
    # Edit an existing row after a switch, then switch back without duplicating it.
    app.session_state["rate_editor"] = {
        "edited_rows": {0: {"rate_percent": 3.0}},
        "deleted_rows": [],
        "added_rows": [],
    }
    app.run()
    updated = app.tabs[1].dataframe[0].value.copy()
    assert not updated.equals(before)
    switch(app, "pl")
    assert app.tabs[1].dataframe[0].value.equals(updated)
    assert len(app.session_state["draft_rate_editor"]) == 1


def test_switch_preserves_general_term_instructions() -> None:
    from datetime import date

    app = AppTest.from_file(str(ROOT / "app.py")).run()
    app.selectbox(key="repayment_model").set_value(RepaymentModel.GENERAL).run()
    app.date_input(key="start_date").set_value(date(2026, 1, 10)).run()
    app.session_state["term_editor"] = {
        "edited_rows": {},
        "deleted_rows": [],
        "added_rows": [{"date": "2026-02-10", "remaining_months": 10}],
    }
    app.run()
    expected = app.tabs[1].dataframe[0].value.copy()
    for language in ["en", "pl"]:
        switch(app, language)
        assert app.tabs[1].dataframe[0].value.equals(expected)
