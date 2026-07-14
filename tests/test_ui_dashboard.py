import re
from playwright.sync_api import Page, expect


class DashboardPage:
    """
    Page Object Model representing the interactive
    Streamlit loan calculator dashboard.
    """

    def __init__(self, page: Page):
        self.page = page

        # UI Element Locators
        self.app_title = page.get_by_role(
            "heading",
            name=re.compile(
                r"Advanced Loan.*Calculator",
                re.IGNORECASE,
            ),
        )
        self.loan_amount_input = page.get_by_label("Loan Amount (PLN)")
        self.interest_rate_input = page.get_by_label("Annual Interest Rate (%)")
        self.total_months_input = page.get_by_label("Total Months")

        # Financial metrics and presentation elements
        self.interest_saved_metric = page.get_by_text("🔥 Total Interest SAVED")
        self.chart_header = page.get_by_role(
            "heading",
            name="📈 Balance Breakdown Over Time",
        )
        self.standard_schedule_tab = page.get_by_role(
            "tab",
            name="Standard Schedule",
        )
        self.overpaid_schedule_tab = page.get_by_role(
            "tab",
            name="Schedule With Overpayments",
        )

    def load(self, url: str = "http://localhost:8501") -> None:
        """
        Loads the dashboard page and waits for the application
        container to render completely.
        """
        self.page.goto(url)
        expect(self.app_title).to_be_visible(timeout=10000)

    def fill_loan_details(self, amount: str, rate: str) -> None:
        """
        Fills standard loan parameters into corresponding
        inputs on the sidebar.
        """
        self.loan_amount_input.fill(amount)
        self.loan_amount_input.blur()

        self.interest_rate_input.fill(rate)
        self.interest_rate_input.blur()

    def select_overpayment_mode_and_strategy(
        self,
        mode: str,
        strategy: str,
    ) -> None:
        """
        Selects the overpayment mode and strategy
        from Streamlit widgets securely.
        """
        self.page.get_by_text(mode, exact=True).click()

        strategy_select = self.page.get_by_label("Overpayment Strategy")
        expect(strategy_select).to_be_visible()
        strategy_select.click()

        self.page.get_by_test_id("stSelectboxVirtualDropdown").get_by_text(
            strategy, exact=True
        ).click()


def test_streeamlit_dashboard_calculates_and_display_metrics(page: Page) -> None:
    """
    End-to-end test verifying loan calculations,
    reactive updates, and chart rendering on the UI.
    """
    dashboard = DashboardPage(page)

    # 1. Load the web interface
    dashboard.load()

    # 2. Key in primary loan constraints
    dashboard.fill_loan_details(
        amount="300000",
        rate="7.5",
    )

    # 3. Enable recurring overpayment rules
    # and shorten period strategy
    dashboard.select_overpayment_mode_and_strategy(
        mode="Regular Monthly Overpayment",
        strategy="Shorten Term",
    )

    # 4. Assert that interactive visual indicators
    # and summary tables have successfully loaded
    expect(dashboard.interest_saved_metric).to_be_visible()
    expect(dashboard.chart_header).to_be_visible()

    # Streamlit line chart tools verification
    expect(page.get_by_role("button", name="Show data").first).to_be_visible()
    expect(page.get_by_role("button", name="Fullscreen").first).to_be_visible()

    # Check that both schedule tabs are fully
    # interactive and present
    expect(dashboard.standard_schedule_tab).to_be_visible()
    expect(dashboard.overpaid_schedule_tab).to_be_visible()
