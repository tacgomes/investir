import csv
import importlib
import os
import re
import shlex
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from investir.cli import app
from investir.config import config

PROJECT_DIR = Path(__file__).parent.parent
DATA_FILE = str(PROJECT_DIR / "data" / "freetrade.csv")
TEST_DIR = PROJECT_DIR / "tests" / "test_cli"
EX_OK = getattr(os, "EX_OK", 0)


@pytest.fixture(name="execute")
def fixture_execute() -> Callable:
    def _execute(
        args: Sequence[str],
        global_opts: Sequence[str] = [
            "--quiet",
            "--offline",
            "--cache-file",
            os.devnull,
        ],
    ) -> Result:
        config.reset()
        runner = CliRunner(mix_stderr=False)
        return runner.invoke(app, [*global_opts, *args])

    return _execute


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
    expected_output = TEST_DIR / expected
    result = execute([*shlex.split(cmd), DATA_FILE])

    if request.config.getoption("--regen-outputs"):
        expected_output.write_text(result.stdout)
    else:
        assert not result.stderr
        assert result.exit_code == EX_OK

        assert expected_output.exists()
        assert result.stdout == expected_output.read_text(encoding="utf-8")


def test_capital_gains_multiple_input_files(execute):
    expected_output = TEST_DIR / "capital_gains"
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


def test_verbosity_mutually_exclusive_filters(execute):
    result = execute(["--quiet", "--verbose", "orders", DATA_FILE])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


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


def test_invocation_without_any_argument(execute):
    result = execute([], global_opts=[])
    assert not result.stderr
    assert "Options" in result.stdout
    assert "Commands" in result.stdout
    assert re.search(
        r"orders.*dividends.*transfers.*interest.*capital-gains.*holdings",
        result.stdout,
        re.DOTALL,
    )
    assert result.exit_code == EX_OK


def test_version_option(execute):
    result = execute(["--version"], global_opts=[])
    version = importlib.metadata.version("investir")
    assert result.stdout.strip() == f"investir {version}"
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_verbose_option(execute):
    result = execute(
        ["orders", DATA_FILE],
        global_opts=[
            "--verbose",
            "--offline",
            "--cache-file",
            os.devnull,
        ],
    )
    assert "INFO" in result.stderr
    assert "DEBUG" in result.stderr
    assert result.stdout
    assert result.exit_code == EX_OK


def test_default_verbosity(execute):
    result = execute(
        ["orders", DATA_FILE],
        global_opts=[
            "--offline",
            "--cache-file",
            os.devnull,
        ],
    )
    assert "INFO" in result.stderr
    assert "DEBUG" not in result.stderr
    assert result.stdout
    assert result.exit_code == EX_OK


@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="Skipping test to avoid hitting API limits for Yahoo Finance",
)
def test_capital_gains_with_splits_downloaded_from_internet(execute):
    data_file = str(TEST_DIR / "orders_with_share_splits.csv")
    result = execute(
        ["capital-gains", data_file],
        global_opts=[
            "--quiet",
            # "--offline",  # Get splits from the Internet
            "--cache-file",
            os.devnull,
        ],
    )

    assert not result.stderr
    assert result.exit_code == EX_OK


@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="Skipping test to avoid hitting API limits for Yahoo Finance",
)
def test_holdings_with_unrealised_gain_loss_calculated(execute):
    result = execute(
        ["holdings", "--show-gain-loss", "--ticker", "MSFT", DATA_FILE],
        global_opts=[
            "--quiet",
            "--cache-file",
            os.devnull,
        ],
    )
    assert "Not available" not in result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_parser_not_found_error(execute, tmp_path):
    csv_file = tmp_path / "transactions.csv"
    with csv_file.open("w", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Uknown"])
        writer.writeheader()

    result = execute(["orders", str(csv_file)])
    assert "Unable to find a parser for" in result.stderr
    assert not result.stdout
    assert result.exit_code != EX_OK


def test_total_amount_error(execute):
    csv_file = TEST_DIR / "total_amount_error.csv"
    result = execute(["orders", str(csv_file)])
    assert not result.stdout
    assert "Calculated amount" in result.stderr
    assert result.exit_code != EX_OK


def test_tax_calculator_error(execute):
    csv_file = TEST_DIR / "tax_calculator_error.csv"
    result = execute(["capital-gains", str(csv_file)])
    assert not result.stdout
    assert "Records appear to be incomplete" in result.stderr
    assert result.exit_code != EX_OK
