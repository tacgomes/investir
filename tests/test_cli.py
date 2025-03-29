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

PROJECT_DIR = Path(__file__).parent.parent
DATA_FILE1 = str(PROJECT_DIR / "data" / "freetrade.csv")
DATA_FILE2 = str(PROJECT_DIR / "data" / "trading212_multi-currency.csv")
TEST_DIR = PROJECT_DIR / "tests" / "test_cli"
EX_OK = getattr(os, "EX_OK", 0)


@pytest.fixture
def execute(tmp_path) -> Callable:
    def _wrapper(
        args: Sequence[str],
        quiet: bool = True,
        verbose: bool = False,
        cache: bool = True,
        offline: bool = True,
    ) -> Result:
        opts = []

        if quiet:
            opts.append("--quiet")

        if verbose:
            opts.append("--verbose")

        if cache:
            opts.append("--cache-dir")
            opts.append(tmp_path)

        if offline:
            opts.append("--offline")

        runner = CliRunner(mix_stderr=False)
        return runner.invoke(app, [*opts, *args])

    return _wrapper


test_data1 = [
    # Orders
    ("orders", "orders"),
    ("orders --tax-year 2023", "orders_ty2023"),
    ("orders --ticker SWKS", "orders_swks"),
    ("orders --acquisitions", "orders_acquisitions"),
    ("orders --disposals", "orders_disposals"),
    (
        "orders --tax-year 2023 --ticker SWKS",
        "orders_ty2023_swks",
    ),
    (
        "orders --tax-year 2023 --acquisitions",
        "orders_ty2023_acquisitions",
    ),
    (
        "orders --tax-year 2023 --disposals",
        "orders_ty2023_disposals",
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
        "orders --tax-year 2023 --ticker SWKS --acquisitions",
        "orders_ty2023_swks_acquisitions",
    ),
    (
        "orders --tax-year 2023 --ticker SWKS --disposals",
        "orders_ty2023_swks_disposals",
    ),
    # Dividends
    ("dividends", "dividends"),
    ("dividends --tax-year 2023", "dividends_ty2023"),
    ("dividends --ticker AAPL", "dividends_aapl"),
    ("dividends --tax-year 2023 --ticker AAPL", "dividends_ty2023_aapl"),
    # Interest
    ("interest", "interest"),
    ("interest --tax-year 2023", "interest_ty2023"),
    # Transfers
    ("transfers", "transfers"),
    ("transfers --tax-year 2023", "transfers_ty2023"),
    ("transfers --deposits", "transfers_deposits"),
    ("transfers --withdrawals", "transfers_withdrawals"),
    ("transfers --tax-year 2023 --deposits", "transfers_ty2023_deposits"),
    ("transfers --tax-year 2023 --withdrawals", "transfers_ty2023_withdrawals"),
    # Capital gains
    ("capital-gains", "capital_gains"),
    ("capital-gains --tax-year 2023", "capital_gains_ty2023"),
    ("capital-gains --ticker SWKS", "capital_gains_swks"),
    ("capital-gains --ticker AMZN", "capital_gains_amzn"),
    ("capital-gains --gains", "capital_gains_gains"),
    ("capital-gains --losses", "capital_gains_losses"),
    ("capital-gains --ticker SWKS --gains", "capital_gains_swks_gains"),
    ("capital-gains --ticker SWKS --losses", "capital_gains_swks_losses"),
    ("capital-gains --tax-year 2023 --gains", "capital_gains_ty2023_gains"),
    ("capital-gains --tax-year 2023 --losses", "capital_gains_ty2023_losses"),
    (
        "capital-gains --tax-year 2023 --ticker SWKS --gains",
        "capital_gains_ty2023_swks_gains",
    ),
    (
        "capital-gains --tax-year 2023 --ticker SWKS --losses",
        "capital_gains_ty2023_swks_losses",
    ),
    # Holdings
    ("holdings", "holdings"),
    ("holdings --ticker SWKS", "holdings_swks"),
    # Output formats
    ("orders --output text", "orders"),
    ("orders --output csv", "orders_csv"),
    ("orders --output json", "orders_json"),
    ("orders --output html", "orders_html"),
    ("dividends --output text", "dividends"),
    ("dividends --output csv", "dividends_csv"),
    ("dividends --output json", "dividends_json"),
    ("dividends --output html", "dividends_html"),
    ("interest --output text", "interest"),
    ("interest --output csv", "interest_csv"),
    ("interest --output json", "interest_json"),
    ("interest --output html", "interest_html"),
    ("transfers --output text", "transfers"),
    ("transfers --output csv", "transfers_csv"),
    ("transfers --output json", "transfers_json"),
    ("transfers --output html", "transfers_html"),
    ("capital-gains --output text", "capital_gains"),
    ("capital-gains --tax-year 2023 --output csv", "capital_gains_csv"),
    ("capital-gains --tax-year 2023 --output json", "capital_gains_json"),
    ("capital-gains --tax-year 2023 --output html", "capital_gains_html"),
    ("holdings --output text", "holdings"),
    ("holdings --output csv", "holdings_csv"),
    ("holdings --output json", "holdings_json"),
    ("holdings --output html", "holdings_html"),
]


@pytest.mark.parametrize("cmd,expected", test_data1)
def test_cli_output(request, execute, cmd, expected):
    expected_output = TEST_DIR / expected
    result = execute([*shlex.split(cmd), DATA_FILE1])

    if request.config.getoption("--regen-outputs"):
        expected_output.write_text(result.stdout)
    else:
        assert not result.stderr
        assert result.exit_code == EX_OK

        assert expected_output.exists()
        assert (
            result.stdout.splitlines()
            == expected_output.read_text(encoding="utf-8").splitlines()
        )


test_data2 = [
    ("orders --output text", "orders_multicur_text"),
    ("orders --output csv", "orders_multicur_csv"),
    ("orders --output json", "orders_multicur_json"),
    ("orders --output html", "orders_multicur_html"),
    ("dividends --output text", "dividends_multicur_text"),
    ("dividends --output csv", "dividends_multicur_csv"),
    ("dividends --output json", "dividends_multicur_json"),
    ("dividends --output html", "dividends_multicur_html"),
    ("interest --output text", "interest_multicur_text"),
    ("interest --output csv", "interest_multicur_csv"),
    ("interest --output json", "interest_multicur_json"),
    ("interest --output html", "interest_multicur_html"),
    ("transfers --output text", "transfers_multicur_text"),
    ("transfers --output csv", "transfers_multicur_csv"),
    ("transfers --output json", "transfers_multicur_json"),
    ("transfers --output html", "transfers_multicur_html"),
]


@pytest.mark.parametrize("cmd,expected", test_data2)
def test_cli_output_multiple_currencies(request, execute, cmd, expected):
    expected_output = TEST_DIR / expected
    result = execute([*shlex.split(cmd), DATA_FILE2])

    if request.config.getoption("--regen-outputs"):
        expected_output.write_text(result.stdout)
    else:
        assert not result.stderr
        assert result.exit_code == EX_OK

        assert expected_output.exists()
        assert (
            result.stdout.splitlines()
            == expected_output.read_text(encoding="utf-8").splitlines()
        )


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
    result = execute(["orders", "--tax-year", "2009", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_dividends_command_no_results(execute):
    result = execute(["dividends", "--tax-year", "2009", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_transfers_command_no_results(execute):
    result = execute(["transfers", "--tax-year", "2009", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_interest_command_no_results(execute):
    result = execute(["interest", "--tax-year", "2009", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_capital_gains_command_no_results(execute):
    result = execute(["capital-gains", "--tax-year", "2009", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_holdings_no_results(execute):
    result = execute(["holdings", "--ticker", "NOTFOUND", DATA_FILE1])
    assert not result.stdout
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_quiet_and_verbose_options_are_mutually_exclusive(execute):
    result = execute(["--quiet", "--verbose", "orders", DATA_FILE1])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_acquisitions_and_disposals_options_are_mutually_exclusive(execute):
    result = execute(["orders", "--acquisitions", "--disposals", DATA_FILE1])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_deposits_and_withdrawals_options_are_mutually_exclusive(execute):
    result = execute(["transfers", "--deposits", "--withdrawals", DATA_FILE1])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_gains_and_losses_options_are_mutually_exclusive(execute):
    result = execute(["capital-gains", "--gains", "--losses", DATA_FILE1])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_capital_gains_command_tax_year_required(execute):
    result = execute(["capital-gains", "--output", "json", DATA_FILE1])
    assert not result.stdout
    assert "Usage:" in result.stderr
    assert result.exit_code != EX_OK


def test_invocation_without_any_argument(execute):
    result = execute([], quiet=False, cache=False, offline=False)
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
    result = execute(["--version"], cache=False)
    version = importlib.metadata.version("investir")
    assert result.stdout.strip() == f"investir {version}"
    assert not result.stderr
    assert result.exit_code == EX_OK


def test_verbose_option(execute):
    result = execute(["orders", DATA_FILE1], quiet=False, verbose=True)
    assert "INFO" in result.stderr
    assert "DEBUG" in result.stderr
    assert result.stdout
    assert result.exit_code == EX_OK


def test_default_verbosity(execute):
    result = execute(["orders", DATA_FILE1], quiet=False)
    assert "INFO" in result.stderr
    assert "DEBUG" not in result.stderr
    assert result.stdout
    assert result.exit_code == EX_OK


@pytest.mark.network
@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="Skipping test to avoid hitting API limits for Yahoo Finance",
)
def test_capital_gains_with_splits_downloaded_from_internet(execute):
    data_file = str(TEST_DIR / "orders_with_share_splits.csv")
    result = execute(["capital-gains", data_file], offline=False)

    assert not result.stderr
    assert result.exit_code == EX_OK


@pytest.mark.network
@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="Skipping test to avoid hitting API limits for Yahoo Finance",
)
def test_holdings_with_unrealised_gain_loss_calculated(execute):
    result = execute(
        ["holdings", "--show-gain-loss", "--ticker", "MSFT", DATA_FILE1], offline=False
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
    assert "Calculated amount" in result.stderr
    assert result.exit_code != EX_OK


def test_tax_calculator_error(execute):
    csv_file = TEST_DIR / "tax_calculator_error.csv"
    for cmd in ["capital-gains", "holdings"]:
        result = execute([cmd, str(csv_file)])
        assert "Records appear to be incomplete" in result.stderr
        assert result.exit_code != EX_OK
