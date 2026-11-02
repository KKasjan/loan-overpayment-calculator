import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        help="Run browser tests against a running Streamlit server.",
    )
    parser.addoption(
        "--app-url", default=os.environ.get("APP_URL", "http://127.0.0.1:8502")
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-e2e"):
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(reason="Use --run-e2e and start Streamlit first.")
                )


@pytest.fixture
def app_url(request):
    return request.config.getoption("--app-url")
