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
            "PLN", timeout=20000
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
    expect(metric).to_contain_text("1,000.00 PLN", timeout=20000)
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
    expect(metric).to_contain_text("1,000.00 PLN", timeout=20000)
    expect(page.get_by_test_id("stException")).to_have_count(0)
    page.screenshot(path="test-results/ing-planner.png", full_page=True)
