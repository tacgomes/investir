![Continuous integration check on the main branch](https://github.com/tacgomes/investir/actions/workflows/ci.yml/badge.svg)

# Investir

This software permits to view the list of stock buy or sell orders
placed in a stock broker, dividends paid out, interest on cash given,
deposits/withdraws made, cost basis of the current holdings, and the
realised capital gains (or losses) calculated in accordance to the HMRC
share pooling rules [1] [2]. It requires as input a CSV export of your
activity feed that can be obtained from the broker. Currently, only the
[Freetrade] broker is supported.

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

View the stock buy or sell orders placed:

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

More than one CSV export can be used as input.

## Issues

Freetrade does not provide detail regarding stock splits events on the
CSV export, and therefore the information provided for assets whose
stock was splitted will not be correct unless the CSV is manually
adjusted for these events.

[Freetrade]: https://freetrade.io/
[1]: https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet/hs284-shares-and-capital-gains-tax-2023#rule
[2]: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
