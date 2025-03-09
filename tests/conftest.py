import pytest

from investir.config import config


@pytest.fixture(autouse=True)
def config_reset():
    config.reset()
    yield


def pytest_addoption(parser):
    parser.addoption(
        "--regen-outputs",
        action="store_true",
        default=False,
        help="Regenerate expected outputs for the CLI tests",
    )
