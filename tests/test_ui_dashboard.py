from playwright.sync_api import Page, expect
# from decimal import Decimal


def test_streamlit_dashboard_calculates_and_display_metrics(
        page: Page
) -> None:
    # 1. Opening the local dashboard
    # (Make sure streamlit run app.py is running in the background!)
    page.goto("http://localhost:8501")

    # 2. Waiting for the main application container to load
    # Streamlit assigns the 'section' tag to the main section
    expect(
        page.get_by_role(
            "heading",
            name="Advanced Loan Overpayment Calculator"
        )
    ).to_be_visible()

    # # 3. Interacting with sidebars - entering test data
    # Search for fields by their labels, which you defined
    # in st.number_input / st.slider
    loan_amount_input = page.get_by_label("Loan Amount (PLN)")
    loan_amount_input.fill("300000")

    interest_rate_input = page.get_by_label("Annual Interest Rate (%)")
    interest_rate_input.fill("7.5")

    # # 4. Selecting an overpayment strategy from the selector (st.selectbox)
    # In Streamlit, first click the selector and then the option that appears
    page.get_by_label("Overpayment Mode").click()
    page.get_by_text("Shorten Term").click()

    # # 5. Verifying results on screen
    # Streamlit for st.metric creates special containers
    # with a class or text structure.
    # Verifying that key information sections and charts
    # have physically appeared on the UI.
    expect(page.get_by_text("Total Interest SAVED")).to_be_visible()

    # Check if the chart has been rendered
    # Chart header verification
    expect(
        page.get_by_role("heading", name="Balance Breakdown Over Time")
    ).to_be_visible()

    # Verification of the interactive chart control buttons
    # that Streamlit generates
    expect(page.get_by_role("button", name="Show data").first).to_be_visible()
    expect(page.get_by_role("button", name="Fullscreen").first).to_be_visible()

    # Check if schedule table tabs (st.tabs) are visible
    expect(page.get_by_text("Detailed Amortization Schedule")).to_be_visible()
    expect(page.get_by_role("tab", name="Standard Schedule")).to_be_visible()
    expect(
        page.get_by_role(
            "tab",
            name="Schedule With Overpayments"
        )
    ).to_be_visible()
