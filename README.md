![Continuous integration check on the main branch](https://github.com/tacgomes/investir/actions/workflows/ci.yml/badge.svg)

# Investir

You can use investir to view the stock buying and selling orders placed
with an investment platform, dividends paid out, interest on cash
received, cash deposits or withdraws made, cost basis of the current
holdings, and the realised capital gains (or losses) calculated in
accordance to the HMRC [share identification rules].

A CSV file with your account activity is required as input. This file
can be exported from your investment platform. Only the Freetrade and
Trading 212 platforms are supported, but the code is structured in a way
that simplifies adding support for more.

## Disclaimer

The reporting provided by this software is intended for informational
purposes only, and it should not be relied upon for any serious tax
related matter, such as filling the Self Assessment tax return. The
author of this software is not a tax accountant or has any affinity with
tax law. The information provided can be erroneous or not correct for
your specific circumstances.

## Installation

This software is not distributed on the Python Package Index (PyPI). You
will have to install it from its source which can be achieved by cloning
this repo and executing the following command:

    pip3 install --user --editable .

## Usage

Some examples in how to use this software are described next.

View the stock buying and selling orders placed:

    investir orders data/freetrade.csv

View the stock sell orders for Microsoft placed in the 2021/2022 tax
year:

    investir orders --tax-year 2021 --ticker MSFT --disposals data/freetrade.csv

View the dividends paid out:

    investir dividends data/freetrade.csv

View the dividends paid out by Microsoft:

    investir dividends --ticker MSFT data/freetrade.csv

View the interest on cash paid out:

    investir interest data/freetrade.csv

View the cash deposits and cash withdrawals made:

    investir transfers data/freetrade.csv

View the capital gains or losses:

    investir capital-gains data/freetrade.csv

View the capital gains or losses for the 2021/2022 tax year:

    investir capital-gains --tax-year 2021 data/freetrade.csv

View the capital losses for any tax year:

    investir capital-gains --losses data/freetrade.csv

View the cost basis of the current holdings:

    investir holdings data/freetrade.csv

View the cost basis for the Microsoft holding and show the average cost
per share as well:

    investir holdings --ticker MSFT --show-avg-cost data/freetrade.csv

Use the `-h` option for a subcommand view all the available options and
filters.

Multiple CSV files can be used as input, including from different
investment platforms.

## Limitations

* Other than dividend payments, the CSV files exported from a
  investment platform do not provide information regarding corporate
  actions that can affect the portfolio. Examples of such actions are
  stock splits, reverse stock splits, or ticker symbol changes (e.g FB
  to META). In that scenario the reports created will not be accurate
  unless the CSV is manually edited to account for those actions.

* No special handling takes place for the accumulation class of shares
  for an investment fund, where income from dividends or interest are
  automatically reinvested back into the fund. This means that in
  practice you might have to pay more tax on your income and less tax on
  capital gains when you sell the fund than what is reported.

* Multi-currency accounts in Trading 212 are not supported and the
  program will terminate if encounters transactions whose base currency
  is not in pound sterling (GBP). These transactions can be ignored
  instead by using the `--no-strict` option in the command line.

[share identification rules]: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
