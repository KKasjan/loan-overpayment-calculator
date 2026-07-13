# Advanced Loan Overpayment Calculator 💰

![CI Pipeline](https://github.com/KKasjan/loan-overpayment-calculator/actions/workflows/ci.yml/badge.svg)
[➡️ View on GitHub](https://github.com/KKasjan/loan-overpayment-calculator)

A professional, lightweight Python tool designed to simulate mortgage loan repayment schedules and calculate the exact financial benefits of overpayments, replicating complex banking mechanisms.

## 🎯 Purpose

This project is a premium engineering showcase designed to demonstrate production-grade software development, clean architecture (PEP 8), defensive programming, and robust automated test suites (both Unit and E2E Browser Automation). It is tailored specifically to highlight the skills required for an Automation QA Engineer / SDET role:

* **Financial Precision Engine**: Replaces unstable floating-point mathematics with the Python Decimal module to eliminate cumulative rounding errors, guaranteeing accurate financial schedules down to the last penny (0.01 PLN).
* **Bank-Grade Simulation**: Replicates commercial banking standards (such as ING or mBank), compounding interest daily on the exact calendar day span of each month (28/29/30/31 days) and adjusting dynamically for leap years (365 vs. 366 days).
* **High-Performance Presentation Layer**: Built on Streamlit, optimized with aggressive caching via @st.cache_data. Features safe presentation-level type conversion to prevent Apache Arrow serialization crashes and uses st.column_config for premium ledger formatting.
* **Test-Driven Rigor**: Covered by a complete, robust suite of unit tests verifying edge-case dates, interest accumulation, and loan life-cycle termination.
* **Page Object Model (POM) UI Suite**: Guarded by Playwright end-to-end browser tests written in Python using modular POM patterns, eliminating flaky waits via native auto-waiting assertions.
* **Automated Quality Gates**: Powered by GitHub Actions, running linting (Ruff), type-checking (MyPy), unit tests, and headless browser UI tests with automatic preservation of coverage reports and JUnit XML artifacts.

## 🚀 Features

* **Interactive Web Dashboard**: Adjust loan variables (amount, interest rate, term, monthly payment day) and immediately see the financial impact of overpayments in real time.
* **Daily Compounding Engine**: Uses an optimized $O(1)$ interval segment algorithm grouping days by calendar year, avoiding slow daily loops while maintaining perfect accuracy across leap years.
* **Annuity Baseline (Equal Installments)**: Computes the exact monthly installment amortization factor using standard financial math before evaluating custom overpayment paths.
* **Flexible Overpayment Strategies**:
    * `SHORTEN_TERM`: Overpayments slice the principal debt directly, automatically keeping monthly payments constant while shrinking the overall remaining duration of the loan.
    * `REDUCE_INSTALLMENT`: Slices the outstanding principal and recalculates the annuity factor for the remaining duration, offering instant cash-flow relief while keeping the original end date.
    * `MIXED`: Allows split-allocation of a single monthly overpayment, routing a specific portion to shorten the term and the remainder to reduce the installment.
* **Granular Visualizations**: A high-contrast monthly outstanding balance chart that contrasts the standard timeline against your accelerated path.
* **Tabular Bank Ledgers**: Interactive, fully sortable side-by-side data tables for standard and overpaid schedules, meticulously splayed and formatted.
* **Calendar-Aware Edge Handling**: Programmatically manages installment payment days (e.g., jumping from January 31st to February 28th or 29th without crashing the application).

## 📂 Project Structure

```text
loan-overpayment-calculator/
├── .github/
│   └── workflows/
│       └── ci.yml            # Expanded GitHub Actions configuration (Ruff, MyPy, Pytest, Playwright)
├── src/
│   ├── __init__.py           # Package initialization
│   ├── calculator.py         # Core Math Engine (Daily Interest Compounding, Amortization, Overpayments)
│   └── models.py             # Strictly typed financial Data Models & Validation Gates
│
├── tests/
│   ├── __init__.py           # Test package initialization
│   ├── test_calculator.py    # Backend Unit & Integration suite (Compounding, Term Shortening, Recalculations)
│   └── test_ui_dashboard.py  # Playwright E2E UI suite (POM-based browser interactions & dashboard verification)
│
├── .gitattributes            # Git attributes configuration
├── .gitignore                # Git exclusion directives
├── app.py                    # Streamlit Interactive Web Application Frontend
├── pyproject.toml            # Code quality tool configurations (Ruff, MyPy settings)
├── pytest.ini                # Pytest runner settings and environment hooks
├── README.md                 # Project documentation
└── requirements.txt          # Production and development dependencies
```

## 🔄 Local Quality Gates

To maintain production-grade standards and ensure zero technical debt, the project enforces strict quality checks locally before any code state is finalized:
* **Static Analysis**: `mypy` ensures explicit and strict type safety across all financial entities and data layers.
* **Linting**: `ruff check` scans the codebase for industry-standard compliance, potential bugs, and code smells.
* **Code Formatting**: `ruff format` guarantees a clean, consistent, and highly readable PEP 8-compliant code style.

## 🧪 Testing & Quality Assurance
Quality is engineered directly into the core of this system. The test suite guarantees that under any scenario, date shift, or extreme capital injection, the outstanding balance resolves to exactly 0.00 PLN at the end of the loan lifecycle.

**Running the Test Suite**

* Backend Unit & Integration Tests (Pytest)
  Validates core calculations, annuity math, leap year shifts, and overpayment state machines.

  1. Install the development and testing dependencies:
   ```bash
   pip install -r requirements.txt
   ```
  2. Run backend suite:
   ```bash
   pytest tests/test_calculator.py -v
   ```

* Frontend End-to-End Tests (Playwright)
  Validates UI responsiveness, User-facing Locators, dynamic Streamlit state re-renders, and chart controls stability under Chromium browser.

  1. Install browser binaries (First time setup):
   ```bash
   playwright install
   ```
  2. Run UI suite in headless mode (CI standard):
   ```bash
   pytest tests/test_ui_dashboard.py -v
   ```
   3. Run UI suite in headed mode to watch the automation in real-time:
   ```bash
   pytest tests/test_ui_dashboard.py -v --headed
   ```

## 🛠️ Technical Stack

* **Language:** Python 3.12+ (leveraging modern typing features)
* **Frontend Framework:** Streamlit (Reactive Python UI)
* **Data Engineering:** Pandas (DataFrames transformation for UI mapping)
* **Core Math Component:** Python Decimal (Bank-standard rounding via ROUND_HALF_UP)
* **Architecture:** Layered, domain-driven structure (Models ➔ Calculator Logic)
* **Testing Framework:**
   - Pytest (Test runner & execution environment)
   - Playwright (E2E Browser Automation via pytest-playwright)
* **Static Analysis & Style:** MyPy & Ruff
* **CI/CD Platform:** GitHub Actions

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
                                         ├── 1. Financial Comparison Metrics (PLN Format)
                                         ├── 2. Visual Balance Breakdown Line Charts
                                         └── 3. Filterable Amortization Tables (Tabs)
```

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
   playwright install
   ```

3. Launch the web-based interactive panel:
   ```bash
   streamlit run app.py
   ```

## 📈 Roadmap

[x] Establish strict Decimal model data layer with PEP 8 compliance.

[x] Build automated calendar-aware daily compounding engine.

[x] Implement SHORTEN_TERM logic with 0.00 PLN closure proofing.

[x] Implement REDUCE_INSTALLMENT term-preserving recalculation logic.

[x] Support MIXED term and installment split strategy.

[x] Add pure cached function wrappers to prevent Streamlit cache misses.

[x] Build a modular Page Object Model (POM) E2E Playwright test suite.

[x] Configure a robust GitHub Actions CI pipeline executing formatters, type-check
