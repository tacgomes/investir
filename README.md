# Investir

`investir` is a tool to view stock broker transactions in a more
readable way than the wide CSV file exported by the broker. At the
moment, the only broker supported is Freetrade.

In the future, the tool will also provide a capital gains tax report
based on the United Kingdom HM Revenue & Customs share identification
rules [1] [2].

## Installation

This project is not distributed on the Python Package Index (PyPI). You
can install it from source by executing:

    pip3 install --user --editable .

## Usage

To import a CSV file with a list of transactions and view them, run

    investir transactions.csv

Replace `transactions.csv` with the location for your CSV file. More
than one CSV input file can be given.


[1]: https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet/hs284-shares-and-capital-gains-tax-2023#rule
[2]: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
