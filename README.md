[![CI badge][ci-badge]][ci-url]
[![Coverage badge][coverage-badge]][coverage-url]
[![Version badge][version-badge]][pypi-url]
[![Python versions badge][pyversions-badge]][pypi-url]
[![License badge][license-badge]][license-url]

# Investir

**Investir** is command-line utility to analyse your account activity on
share investing platforms. It can provide the information required to
fill out the Capital Gains SA108 form for the Self Assessment tax
return. The gain or loss is calculated based on the HMRC [share
identification rules]. **Investir** also facilitates viewing the cost,
allocation weight and unrealised gain/loss for open positions, share
buying and selling orders placed, dividends paid out, interest on cash
earned, and cash deposits or withdrawals made.

A comma-separated values (CSV) file with your account activity is
required as input. This file can be exported from your investment
platform(s) of choice. At the moment, only _Freetrade_ and _Trading 212_
are supported, but the structure of the codebase facilitates adding
support for additional brokers.

Yahoo Finance is queried to find the share sub-division and share
consolidation events executed for a given company, and that information
is taken into account when calculating the capital gains.

Share sub-division or share consolidation events executed for a given
company are queried from Yahoo Finance, and this information is taken
into account when calculating the capital gains.

Capital gains can also be calculated for orders not realised in pound
sterling. In this case, it is necessary to convert the monetary values
to sterling first. The historical exchange rates used in these
conversions can be sourced from Yahoo Finance, the [exchange rates][hmrc-rates]
published by HMRC each month, or a local comma-separated values (CSV)
file.

## Disclaimer 🔥

The information provided by **Investir** might be inaccurate or simply
not correct for your specific circumstances. Use the software at your
own risk and always seek advice from a professional accountant before
submitting your Self-Assessment tax return.

## Installation

Before installing **Investir**, it is recommended to create a [virtual
environment] for the installation:

    $ python -m venv .venv
    $ source .venv/bin/activate

**Investir** can be installed from the Python Package Index (PyPI):

    (.venv)$ python -m pip install investir

If you type `investir` and press the enter key, **Investir**'s command
help should now be displayed.

## Usage

This section provides some examples in how to use **Investir**'s
command-line interface.

> [!TIP]
> **Investir** can process more than one CSV file as input, including
> CSVs from different investment platforms.

View a capital gains report with the information required to fill out
the Capital Gains SA108 form for the Self Assessment tax return:

```console
$ investir capital-gains data/freetrade.csv
Capital Gains Tax Report 2021/22
6th April 2021 to 5th April 2022

  Disposal Date   Identification          Security Name   ISIN              Quantity   Cost (GBP)   Proceeds (GBP)   Gain/loss (GBP)
--------------------------------------------------------------------------------------------------------------------------------------
  25/08/2021      Section 104             Microsoft       US5949181045   13.00246544      2366.57          2952.48            585.91
  01/09/2021      Section 104             Skyworks        US83088M1027    1.24584888       167.16           153.21            -13.95
  13/09/2021      Same day                SMT             GB00BLDYK618   34.00000000       443.65           474.83             31.18
  13/09/2021      Bed & B. (2021-09-26)   SMT             GB00BLDYK618   40.00000000       482.67           558.62             75.95
  13/09/2021      Section 104             SMT             GB00BLDYK618   14.00000000       189.85           195.52              5.67
  02/11/2021      Section 104             Apple           US0378331005   26.22913238      2647.31          3653.35           1006.04
  27/01/2022      Section 104             Skyworks        US83088M1027    1.24584888       167.21           178.13             10.92

Number of disposals:                             7      Gains in the year, before losses:   £1715.67
Disposal proceeds:                        £8166.14      Losses in the year:                   £13.95
Allowable costs (incl. purchase price):   £6464.42      Net gain or loss:                   £1701.72

Capital Gains Tax Report 2022/23
6th April 2022 to 5th April 2023

  Disposal Date   Identification   Security Name   ISIN              Quantity   Cost (GBP)   Proceeds (GBP)   Gain/loss (GBP)
-------------------------------------------------------------------------------------------------------------------------------
  20/09/2022      Section 104      Amazon          US0231351067   48.31896981      3493.12          4941.53           1448.41
  14/10/2022      Section 104      Microsoft       US5949181045    1.32642000       324.79           319.76             -5.03
  16/12/2022      Section 104      Skyworks        US83088M1027    8.30000000      1094.16           979.69           -114.47
  03/03/2023      Section 104      Skyworks        US83088M1027    2.10000000       277.20           312.95             35.75

Number of disposals:                             4      Gains in the year, before losses:   £1484.16
Disposal proceeds:                        £6553.93      Losses in the year:                  £119.50
Allowable costs (incl. purchase price):   £5189.27      Net gain or loss:                   £1364.66
```

View cost, allocation weight, and unrealised gain/loss for open
positions:

```console
$ investir holdings --show-gain-loss data/freetrade.csv
  Security Name   ISIN           Cost (GBP)       Quantity   Current Value (GBP)   Gain/Loss (GBP)   Weight (%)
-----------------------------------------------------------------------------------------------------------------
  SMT             GB00BLDYK618      2196.81   162.00000000               1758.51           -438.30        43.81
  Microsoft       US5949181045       882.35     3.62439184               1215.85            333.50        30.29
  Apple           US0378331005       301.70     3.00000000                576.70            275.00        14.37
  Skyworks        US83088M1027       301.08     2.29594360                165.24           -135.83         4.12
  PayPal          US70450Y1038       249.59     4.13171759                298.00             48.41         7.42
```

View share buying and selling orders placed:

```console
$ investir orders data/freetrade.csv
  Date         Security Name   ISIN           Ticker   Cost (GBP)   Proceeds (GBP)       Quantity   Price (GBP)   Fees (GBP)
------------------------------------------------------------------------------------------------------------------------------
  07/04/2021   Apple           US0378331005   AAPL        1940.99                     20.13713692         96.15         4.76
  05/06/2021   Apple           US0378331005   AAPL         998.48                      9.09199546        109.33         4.47
  11/06/2021   Microsoft       US5949181045   MSFT        2715.44                     15.00246544        180.19        12.20
  12/08/2021   Skyworks        US83088M1027   SWKS        1497.76                     11.21263989        132.98         6.71
  25/08/2021   Microsoft       US5949181045   MSFT                         2939.35    13.00246544        227.07        13.13
  26/08/2021   SMT             GB00BLDYK618   SMT         2386.66                    176.00000000         13.49        11.90
  01/09/2021   Skyworks        US83088M1027   SWKS                          152.47     1.24584888        122.98         0.74
  13/09/2021   SMT             GB00BLDYK618   SMT                          1228.97    88.00000000         13.97         0.00
  13/09/2021   SMT             GB00BLDYK618   SMT          443.65                     34.00000000         13.03         0.78
  26/09/2021   SMT             GB00BLDYK618   SMT          482.67                     40.00000000         12.05         0.56
  02/11/2021   Apple           US0378331005   AAPL                         3643.81    26.22913238        139.29         9.54
  27/01/2022   Skyworks        US83088M1027   SWKS                          177.34     1.24584888        142.98         0.79
------------------------------------------------------------------------------------------------------------------------------
  10/04/2022   PayPal          US70450Y1038   PYPL         249.59                      4.13171759         60.05         1.46
  12/05/2022   Microsoft       US5949181045   MSFT         843.26                      2.95081184        284.09         4.95
  09/07/2022   Amazon          US0231351067   AMZN        3464.02                     48.31896981         71.27        20.36
  20/09/2022   Amazon          US0231351067   AMZN                         4912.43    48.31896981        102.27        29.10
  28/09/2022   Skyworks        US83088M1027   SWKS         499.95                      3.97500146        125.03         2.94
  14/10/2022   Microsoft       US5949181045   MSFT                          317.88     1.32642000        241.07         1.88
  16/12/2022   Skyworks        US83088M1027   SWKS                          973.95     8.30000000        118.03         5.74
  03/03/2023   Skyworks        US83088M1027   SWKS                          311.13     2.10000000        149.02         1.82
------------------------------------------------------------------------------------------------------------------------------
                                                         15522.47         14657.33                                    133.83
```

View dividends paid out:

```console
$ investir dividends data/freetrade.csv
  Date         Security Name   ISIN           Ticker   Net Amount (GBP)   Widthheld Amount (GBP)
--------------------------------------------------------------------------------------------------
  12/02/2022   Apple           US0378331005   AAPL                 1.37                     0.24
  09/03/2022   Microsoft       US5949181045   MSFT                 3.44                     0.61
  15/03/2022   Skyworks        US83088M1027   SWKS                 2.50                     0.44
--------------------------------------------------------------------------------------------------
  13/05/2022   Microsoft       US5949181045   MSFT                 4.12                     0.72
  08/06/2022   Apple           US0378331005   AAPL                 1.64                     0.28
--------------------------------------------------------------------------------------------------
                                                                  13.07                     2.29
```

View interest on cash earned:

```console
$ investir interest data/freetrade.csv
  Date         Amount (GBP)
-----------------------------
  15/10/2021           1.70
  15/01/2022           1.59
-----------------------------
  15/04/2022           1.61
  15/07/2022           1.58
  15/01/2023           1.81
-----------------------------
                       8.29
```

View cash deposits and withdrawals made:

```console
$ investir transfers data/freetrade.csv
  Date         Deposit (GBP)   Withdrawal (GBP)
-------------------------------------------------
  02/03/2021         6000.00
-------------------------------------------------
  28/07/2021         4000.00
  24/02/2022                             400.00
-------------------------------------------------
  08/04/2022                             100.00
  03/01/2023         2000.00
-------------------------------------------------
                    12000.00             500.00
```

> [!TIP]
> Each command supports various options that can be used to filter the
> output based on several criteria. Use the `--help` option for any
> command for a description of all the available options.

## Exchange Rates File

The historical exchange rates used to convert monetary values to
sterling can be sourced from a local comma-separated values (CSV) file.
The following example should be self-explanatory regarding the format
that is required:

    Date,Currency,Rate
    2025-03-17,USD,1.293198
    2025-03-17,EUR,1.188523
    ...

To create a file with exchange rates sourced from Google Finance, on any
cell of a Google Sheets spreadsheet, enter the following formula and
then download the spreadsheet as a comma-separated values file:

    =QUERY(GOOGLEFINANCE("GBPUSD", "close", "01/01/2020", TODAY()), "select Col1, 'USD', Col2 label 'USD' 'Currency', Col2 'Rate'")

This formula will populate the spreadsheet with the `GBP` to `USD`
exchange rates from the beginning of 2020 up to the present date. The
formula can be adjusted to provide rates for other currencies as well.

## Hacking

To modify **Investir** and evaluate the changes, clone this repository and
execute an [editable install]:

    $ git clone https://github.com/tacgomes/investir.git
    $ cd investir
    $ python -m venv .venv
    $ source .venv/bin/activate
    (.venv)$ python -m pip install --editable .[lint,test]

> [!NOTE]
> Linters and test packages used by this project will also be installed.

[ci-badge]: https://github.com/tacgomes/investir/actions/workflows/ci.yml/badge.svg
[coverage-badge]: https://codecov.io/github/tacgomes/investir/graph/badge.svg?token=I0HHSSD83O
[version-badge]: https://img.shields.io/pypi/v/investir.svg
[pyversions-badge]: https://img.shields.io/pypi/pyversions/investir.svg
[license-badge]: https://img.shields.io/pypi/l/investir.svg

[ci-url]: https://github.com/tacgomes/investir/actions?query=branch%3Amain
[coverage-url]: https://codecov.io/github/tacgomes/investir?displayType=list
[pypi-url]: https://pypi.org/project/investir/
[license-url]: https://github.com/tacgomes/investir/blob/master/LICENSE

[share identification rules]: https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
[hmrc-rates]: https://www.trade-tariff.service.gov.uk/exchange_rates
[virtual environment]: https://docs.python.org/3/library/venv.html
[editable install]: https://setuptools.pypa.io/en/latest/userguide/development_mode.html
