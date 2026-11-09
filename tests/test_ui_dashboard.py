"""Browser smoke and numerical checks; activate explicitly with --run-e2e."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class DashboardPage:
    def __init__(self, page: Page):
        self.page = page

    def load(self, url: str) -> None:
        self.page.goto(url)
        expect(
            self.page.get_by_role(
                "heading", name="Kalkulator nadpłaty kredytu hipotecznego", exact=True
            )
        ).to_be_visible(timeout=20000)
        # Numeric financial output confirms Streamlit has executed the script.
        expect(self.page.get_by_test_id("stMetricValue").first).to_contain_text(
            "zł", timeout=20000
        )
        sidebar = self.page.get_by_test_id("stSidebar")
        if not sidebar.is_visible():
            self.page.get_by_role("button", name="Open sidebar").click()


def test_dashboard_single_overpayment_and_chart(page: Page, app_url: str) -> None:
    dashboard = DashboardPage(page)
    dashboard.load(app_url)
    page.get_by_test_id("stRadio").get_by_text("Jednorazowa", exact=True).click()
    month = page.get_by_role("spinbutton", name="Numer raty z nadpłatą", exact=True)
    expect(month).to_be_visible()
    month.fill("12")
    month.press("Enter")
    amount = page.get_by_role("spinbutton", name="Kwota nadpłaty (PLN)", exact=True)
    amount.fill("1000")
    amount.press("Enter")
    metric = page.get_by_test_id("stMetric").filter(has_text="Wykorzystane nadpłaty")
    expect(metric).to_contain_text("1 000,00 zł", timeout=20000)
    expect(
        page.get_by_role("heading", name="Pozostały kapitał w czasie", exact=True)
    ).to_be_visible()
    page.get_by_role("tab", name="Z nadpłatami", exact=True).click()
    expect(page.get_by_role("button", name="Pobierz CSV", exact=True)).to_be_visible()
    expect(page.get_by_test_id("stException")).to_have_count(0)
    page.get_by_role(
        "heading", name="Kalkulator nadpłaty kredytu hipotecznego", exact=True
    ).scroll_into_view_if_needed()
    page.screenshot(path="test-results/dashboard.png", full_page=True)


def test_dashboard_short_term_does_not_crash(page: Page, app_url: str) -> None:
    DashboardPage(page).load(app_url)
    months = page.get_by_role("spinbutton", name="Pozostała liczba rat", exact=True)
    months.fill("3")
    months.press("Enter")
    page.get_by_test_id("stRadio").get_by_text("Jednorazowa", exact=True).click()
    expect(
        page.get_by_role("spinbutton", name="Numer raty z nadpłatą", exact=True)
    ).to_have_value("3")
    expect(page.get_by_test_id("stException")).to_have_count(0)


def test_ing_inverse_quote_in_browser(page: Page, app_url: str) -> None:
    DashboardPage(page).load(app_url)
    for label, value in [
        ("Pozostały kapitał (PLN)", "12000"),
        ("Oprocentowanie roczne (%)", "0"),
        ("Pozostała liczba rat", "12"),
    ]:
        field = page.get_by_role("spinbutton", name=label, exact=True)
        field.fill(value)
        field.press("Enter")
    target = page.get_by_role(
        "spinbutton", name="Maksymalna rata po aneksie (PLN)", exact=True
    )
    target.fill("1000")
    page.get_by_role("button", name="Oblicz wymaganą nadpłatę", exact=True).click()
    metric = page.get_by_test_id("stMetric").filter(
        has_text="Minimalna dodatkowa nadpłata"
    )
    expect(metric).to_contain_text("1 000,00 zł", timeout=20000)
    expect(page.get_by_test_id("stException")).to_have_count(0)
    page.screenshot(path="test-results/ing-planner.png", full_page=True)


def test_language_switch_preserves_inputs_results_and_csv(
    page: Page, app_url: str
) -> None:
    DashboardPage(page).load(app_url)
    for label, value in [
        ("Pozostały kapitał (PLN)", "12000"),
        ("Oprocentowanie roczne (%)", "0"),
        ("Pozostała liczba rat", "12"),
    ]:
        field = page.get_by_role("spinbutton", name=label, exact=True)
        field.fill(value)
        field.press("Enter")
    page.get_by_test_id("stRadio").get_by_text("Jednorazowa", exact=True).click()
    field = page.get_by_role("spinbutton", name="Numer raty z nadpłatą", exact=True)
    field.fill("1")
    field.press("Enter")
    field = page.get_by_role("spinbutton", name="Kwota nadpłaty (PLN)", exact=True)
    field.fill("300")
    field.press("Enter")
    expect(
        page.get_by_test_id("stMetric").filter(has_text="Wykorzystane nadpłaty")
    ).to_contain_text("300,00 zł")
    page.get_by_role("tab", name="Z nadpłatami", exact=True).click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Pobierz CSV", exact=True).click()
    original = download.value.path().read_bytes()
    page.get_by_role("radiogroup", name="PL / EN").get_by_text("EN", exact=True).click()
    expect(
        page.get_by_role("heading", name="Mortgage overpayment calculator", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("spinbutton", name="Outstanding principal (PLN)", exact=True)
    ).to_have_value("12000.00")
    expect(
        page.get_by_role(
            "spinbutton", name="Installment number for overpayment", exact=True
        )
    ).to_have_value("1")
    expect(
        page.get_by_test_id("stMetric").filter(has_text="Applied overpayments")
    ).to_contain_text("300.00 PLN")
    page.get_by_role("tab", name="With overpayments", exact=True).click()
    with page.expect_download() as download:
        page.get_by_role("button", name="Download CSV", exact=True).click()
    assert download.value.path().read_bytes() == original
    page.get_by_role(
        "heading", name="Mortgage overpayment calculator", exact=True
    ).scroll_into_view_if_needed()
    page.screenshot(path="test-results/language-en.png", full_page=True)
    page.get_by_role("radiogroup", name="PL / EN").get_by_text("PL", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Kalkulator nadpłaty kredytu hipotecznego", exact=True
        )
    ).to_be_visible()
    expect(
        page.get_by_role("spinbutton", name="Kwota nadpłaty (PLN)", exact=True)
    ).to_have_value("300.00")
    expect(page.get_by_test_id("stException")).to_have_count(0)


def test_language_switch_preserves_general_mixed_selectors(
    page: Page, app_url: str
) -> None:
    DashboardPage(page).load(app_url)
    page.get_by_test_id("stSelectbox").filter(has_text="Model spłaty").get_by_role(
        "combobox"
    ).click()
    page.get_by_role(
        "option", name="Ogólny — dotychczasowe strategie", exact=True
    ).click()
    page.get_by_test_id("stRadio").get_by_text(
        "Regularne miesięczne", exact=True
    ).click()
    page.get_by_test_id("stSelectbox").filter(has_text="Strategia").get_by_role(
        "combobox"
    ).click()
    page.get_by_role("option", name="Mixed", exact=True).click()
    for label, value in [
        ("Część na skrócenie (PLN)", "200"),
        ("Część na obniżenie raty (PLN)", "100"),
    ]:
        field = page.get_by_role("spinbutton", name=label, exact=True)
        field.fill(value)
        field.press("Enter")
    page.get_by_role("radiogroup", name="PL / EN").get_by_text("EN", exact=True).click()
    expect(
        page.get_by_role("radio", name="Regular monthly", exact=True)
    ).to_be_checked()
    expect(
        page.get_by_role(
            "spinbutton", name="Amount for term reduction (PLN)", exact=True
        )
    ).to_have_value("200.00")
    expect(
        page.get_by_role(
            "spinbutton", name="Amount for installment reduction (PLN)", exact=True
        )
    ).to_have_value("100.00")
    page.get_by_role("radiogroup", name="PL / EN").get_by_text("PL", exact=True).click()
    expect(
        page.get_by_role("radio", name="Regularne miesięczne", exact=True)
    ).to_be_checked()
    expect(
        page.get_by_role("spinbutton", name="Część na skrócenie (PLN)", exact=True)
    ).to_have_value("200.00")
    expect(page.get_by_test_id("stException")).to_have_count(0)
