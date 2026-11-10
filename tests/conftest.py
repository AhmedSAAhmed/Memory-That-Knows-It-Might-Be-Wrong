"""Normal test runs stay offline; the formal evaluator explicitly enables APIs."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--live-evals", action="store_true", help="Enable real-provider failure evaluations")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--live-evals"):
        for item in items:
            if "eval" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Real providers require --live-evals"))
