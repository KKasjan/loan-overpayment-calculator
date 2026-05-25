# Advanced Loan Overpayment Calculator 💰

[➡️ View on GitHub](https://github.com/KKasjan/loan-overpayment-calculator)

A professional, lightweight Python tool designed to simulate mortgage loan repayment schedules and calculate the exact financial benefits of overpayments, replicating complex banking mechanisms.

## 🎯 Purpose

This project serves as a premium showcase of a professional engineering workflow, specifically tailored for an Automation QA Engineer role:

* **Financial Precision Engine**: Handling exact monetary calculations using the `Decimal` module to eliminate floating-point errors.
* **Bank-Grade Simulation**: Replicating specific banking behaviors, such as daily interest compounding based on actual monthly calendars and leap years (matching standard practices of banks like ING).
* **Interactive Frontend**: Powered by a reactive Streamlit dashboard providing immediate financial metrics, visual trend comparison, and data drill-down.
* **Test-Driven Execution**: Covered by a complete, robust suite of unit, edge-case, and mathematical logic integration tests.
* **Automated Quality Gates**: Enforcing zero-technical-debt standards via a fully automated pipeline utilizing Ruff, MyPy, and Pytest.

## 🚀 Features

* **Interactive Web Dashboard**: User-friendly sidebar to adjust loan parameters (amount, interest rate, term, due day) and inject overpayment parameters on the fly with instant metrics rendering.
* **Daily Compounding Engine**: Calculates interest accrued day-by-day based on the exact calendar length of each month (28/29/30/31 days) and varying yearly scales (365 vs 366 days for leap years).
* **Annuity Baseline (Equal Installments)**: Computes a standard reference monthly installment using traditional amortization formulas before injecting overpayment variables.
* **Dual Overpayment Strategies**: 
    * `SHORTEN_TERM`: Overpayments directly slice the principal debt, automatically keeping the monthly installment fixed while shortening the overall life of the loan.
    * `REDUCE_INSTALLMENT`: Overpayments recalculate the base monthly requirement for the remaining period, offering immediate cash-flow relief while preserving the original term length.
* **Visual Analytics**: Interactive line charts that map out the outstanding principal balance breakdown month-by-month, contrasting the standard trajectory with the accelerated one.
* **Granular Data Inspection**: Fully populated, interactive, and sortable side-by-side tables for both amortization schedules (with and without overpayments).
* **Calendar-Aware Edge Handling**: Programmatically manages repayment dates landing on edge cases (e.g., jumping from January 31st to February 28th or 29th without crashing).

## 📂 Project Structure

```text
loan-overpayment-calculator/
├── src/
│   ├── __init__.py         # Initialization
│   ├── calculator.py       # Core Math Engine (Schedules, Daily Interest, Overpayments)
│   └── models.py           # Strictly typed financial Data Models & Data Structures
│
├── tests/
│   ├── __init__.py         # Test Initialization
│   └── test_calculator.py  # Unit & Integration suite (Leap years, Strategies, Zero-balance closures)
│
├── .gitattributes          # Git attributes configuration
├── app.py                  # Streamlit Interactive Web Application Frontend
├── pyproject.toml          # Tool configuration (Ruff linter, formatter, and environment)
├── pytest.ini              # Pytest framework settings
├── README.md               # Project documentation
└── requirements.txt        # Core development dependencies (streamlit, pandas, pytest, ruff, mypy)

## 🔄 Local Quality Gates
To maintain production-grade standards and ensure zero technical debt, the project enforces strict quality checks locally before any code state is finalized:
* **Static Analysis**: `mypy` ensures explicit and strict type safety across all financial entities and data layers.
* **Linting**: `ruff check` scans the codebase for industry-standard compliance, potential bugs, and code smells.
* **Code Formatting**: `ruff format` guarantees a clean, consistent, and highly readable PEP 8-compliant code style.

## 🧪 Testing & Quality Assurance
Quality is baked into the very core of this engine. The test suite guarantees that regardless of complex calendar dates, leap years, or extreme overpayment injections, the loan's final balance always drops to exactly 0.00 PLN.

**Running the Test Suite**

1. Install the development and testing dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the tests from the root directory:
   ```bash
   pytest -v
   ```

**The suite covers:**

* Annuity math validation.
* Leap year boundary transitions (365 vs 366 interest distribution).
* Calendar shifting for due dates.
* Overpayment math assertions for both SHORTEN_TERM and REDUCE_INSTALLMENT.

## 🛠️ Technical Stack

* **Language:** Python 3.12+ (leveraging modern typing features)
* **Frontend Framework:** Streamlit (Reactive Python UI)
* **Data Engineering:** Pandas (DataFrames transformation for UI mapping)
* **Core Math Component:** Python Decimal (Bank-standard rounding via ROUND_HALF_UP)
* **Architecture:** Layered, domain-driven structure (Models ➔ Calculator Logic)
* **Testing Framework:** Pytest
* **Static Analysis & Style:** MyPy & Ruff

## 📋 How It Works
The engine executes simulation tracks in sequential phases

```text
[ Input Parameters (UI Sidebar) ] ➔ [ Build Standard Schedule ]
                                         │
                                [ Inject Overpayments List ]
                                         │
                                [ Loop Month-by-Month ]
                                         ├── 1. Get exact payment date & day span
                                         ├── 2. Calculate precise daily interest
                                         ├── 3. Execute Overpayment Strategy
                                         └── 4. Recalculate remaining terms / base installment
                                         │
                                [ Compile Simulation Summary ]
                                         │
                                [ Render Streamlit UI Elements ]
                                         ├── 1. Financial Comparison Metrics
                                         ├── 2. Visual Balance Breakdown Line Charts
                                         └── 3. Filterable Amortization Tables (Tabs)

### Financial Compounding Formula

Unlike simplified tools that calculate interest monthly (`Principal * Rate / 12`), this engine iterates through each day within the period:

$$\Delta Interest = Balance \times \frac{Annual\ Rate}{Days\ in\ Year\ (365/366)}$$

This daily slice is accumulated and rounded to two decimal points at the monthly payment gate, matching real banking systems.

This daily slice is accumulated and rounded to two decimal points at the monthly payment gate, matching real banking systems.

## 💻 Installation & Usage

1. Clone the repository:
   ```bash
   git clone [https://github.com/KKasjan/loan-overpayment-calculator.git](https://github.com/KKasjan/loan-overpayment-calculator.git)
   cd loan-overpayment-calculator
   ```

2. Setup your local environment and ensure dependencies are met:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the web-based interactive panel:
   ```bash
   streamlit run app.py
   ```
## 🔮 Future Enhancements

* Dynamic Overpayment Triggers: Defining recurring rules (e.g., "overpay 1000 PLN every 3 months").
* Interest Rate Fluctuations: Support for macro-economic updates (WIBOR changes during the simulation).
* Export Profiles: Downloading generated amortization tables straight into Excel/CSV files directly from the UI.

## 📈 Roadmap

    [x] Establish strict Decimal model data layer.

    [x] Build automated leap-year-aware daily interest function.

    [x] Core engine implementation for classic amortization schedules.

    [x] Implement SHORTEN_TERM logic with 0.00 PLN closure proofing.

    [x] Implement REDUCE_INSTALLMENT dynamic recalculation logic.

    [x] Add side-by-side multi-scenario simulation wrapper.

    [x] Transition codebase to standardized English documentation and docstrings.

    [x] Add an interactive, production-grade Graphical Dashboard via Streamlit.