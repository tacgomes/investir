import logging
import os
import shlex
from collections.abc import Iterable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from investir.cli import app

PROJECT_DIR = Path(__file__).parent.parent
DATA_FILE = str(PROJECT_DIR / "data" / "freetrade.csv")
OUTPUTS_DIR = PROJECT_DIR / "tests" / "test_cli"
EX_OK = getattr(os, "EX_OK", 0)


@pytest.fixture(name="execute")
def fixture_execute() -> Iterable:
    def _execute(args: list[str]) -> Result:
        runner = CliRunner(mix_stderr=False)
        global_opts = ["--offline", "--cache-file", os.devnull]
        return runner.invoke(app, global_opts + args)

    logging.disable()
    yield _execute
    logging.disable(logging.NOTSET)


test_data = [
    # Orders
    ("orders", "orders"),
    ("orders --tax-year 2022", "orders_ty2022"),
    ("orders --ticker SWKS", "orders_swks"),
    ("orders --acquisitions", "orders_acquisitions"),
    ("orders --disposals", "orders_disposals"),
    (
        "orders --tax-year 2022 --ticker SWKS",
        "orders_ty2022_swks",
    ),
    (
        "orders --tax-year 2022 --acquisitions",
        "orders_ty2022_acquisitions",
    ),
    (
        "orders --tax-year 2022 --disposals",
        "orders_ty2022_disposals",
    ),
    (
        "orders --ticker SWKS --acquisitions",
        "orders_swks_acquisitions",
    ),
    (
        "orders --ticker SWKS --disposals",
        "orders_swks_disposals",
    ),
    (
        "orders --tax-year 2022 --ticker SWKS --acquisitions",
        "orders_ty2022_swks_acquisitions",
    ),
    (
        "orders --tax-year 2022 --ticker SWKS --disposals",
        "orders_ty2022_swks_disposals",
    ),
    # Dividends
    ("dividends", "dividends"),
    ("dividends --tax-year 2022", "dividends_ty2022"),
    ("dividends --ticker AAPL", "dividends_aapl"),
    ("dividends --tax-year 2022 --ticker AAPL", "dividends_ty2022_aapl"),
    # Interest
    ("interest", "interest"),
    ("interest --tax-year 2022", "interest_ty2022"),
    # Transfers
    ("transfers", "transfers"),
    ("transfers --tax-year 2022", "transfers_ty2022"),
    ("transfers --deposits", "transfers_deposits"),
    ("transfers --withdrawals", "transfers_withdrawals"),
    ("transfers --tax-year 2022 --deposits", "transfers_ty2022_deposits"),
    ("transfers --tax-year 2022 --withdrawals", "transfers_ty2022_withdrawals"),
    # Capital gains
    ("capital-gains", "capital_gains"),
    ("capital-gains --tax-year 2022", "capital_gains_ty2022"),
    ("capital-gains --ticker SWKS", "capital_gains_swks"),
    ("capital-gains --ticker AMZN", "capital_gains_amzn"),
    ("capital-gains --gains", "capital_gains_gains"),
    ("capital-gains --losses", "capital_gains_losses"),
    ("capital-gains --ticker SWKS --gains", "capital_gains_swks_gains"),
    ("capital-gains --ticker SWKS --losses", "capital_gains_swks_losses"),
    ("capital-gains --tax-year 2022 --gains", "capital_gains_ty2022_gains"),
    ("capital-gains --tax-year 2022 --losses", "capital_gains_ty2022_losses"),
    (
        "capital-gains --tax-year 2022 --ticker SWKS --gains",
        "capital_gains_ty2022_swks_gains",
    ),
    (
        "capital-gains --tax-year 2022 --ticker SWKS --losses",
        "capital_gains_ty2022_swks_losses",
    ),
    # Holdings
    ("holdings", "holdings"),
    ("holdings --ticker SWKS", "holdings_swks"),
]


@pytest.mark.parametrize("cmd,expected", test_data)
def test_cli_output(request, execute, cmd, expected):
    expected_output = OUTPUTS_DIR / expected
    result = execute(shlex.split(cmd) + [DATA_FILE])

    if request.config.getoption("--regen-outputs"):
        expected_output.write_text(result.stdout)
    else:
        assert not result.stderr
        assert result.exit_code == EX_OK

        assert expected_output.exists()
        assert result.stdout == expected_output.read_text(encoding="utf-8")


def test_capital_gains_multiple_input_files(execute):
    expected_output = OUTPUTS_DIR / "capital_gains"
    data_file1 = str(PROJECT_DIR / "data" / "trading212_2021-2022.csv")
    data_file2 = str(PROJECT_DIR / "data" / "trading212_2022-2023.csv")
    result = execute(["capital-gains", data_file1, data_file2])

    assert not result.stderr
    assert result.exit_code == EX_OK

    assert expected_output.exists()
    assert result.stdout == expected_output.read_text(encoding="utf-8")


def test_orders_command_no_results(execute):
    result = execute(["orders", "--tax-year", "2008", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_dividends_command_no_results(execute):
    result = execute(["dividends", "--tax-year", "2008", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_transfers_command_no_results(execute):
    result = execute(["transfers", "--tax-year", "2008", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_interest_command_no_results(execute):
    result = execute(["interest", "--tax-year", "2008", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_capital_gains_command_no_results(execute):
    result = execute(["capital-gains", "--tax-year", "2008", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_holdings_no_results(execute):
    result = execute(["holdings", "--ticker", "NOTFOUND", DATA_FILE])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_orders_command_mutually_exclusive_filters(execute):
    result = execute(["orders", "--acquisitions", "--disposals", DATA_FILE])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_transfers_command_mutually_exclusive_filters(execute):
    result = execute(["transfers", "--deposits", "--withdrawals", DATA_FILE])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_capital_gains_command_mutually_exclusive_filters(execute):
    result = execute(["capital-gains", "--gains", "--losses", DATA_FILE])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK
