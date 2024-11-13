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

A CSV file with your account activity is required as input. This file
can be exported from your investment platform. Presently, only
_Freetrade_ and _Trading 212_ are supported, but the project modularity
facilitates adding support for more.

The Yahoo Finance API can be used to find the share sub-division or
share consolidation events executed for a given corporation, and that
information is considered when calculating the capital gains.

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
                                                 Tax year 2021-2022
--------------------------------------------------------------------------------------------------------------------
  Date Disposed   Date Acquired   ISIN           Name           Quantity   Cost (£)   Proceeds (£)   Gain/loss (£)
--------------------------------------------------------------------------------------------------------------------
  2021-08-25      Section 104     US5949181045   Microsoft   13.00246544    2366.57        2952.48          585.91
  2021-09-01      Section 104     US83088M1027   Skyworks     1.24584888     167.16         153.21          -13.95
  2021-09-13      2021-09-13      GB00BLDYK618   SMT         34.00000000     443.65         474.83           31.18
  2021-09-13      2021-09-26      GB00BLDYK618   SMT         40.00000000     482.67         558.62           75.95
  2021-09-13      Section 104     GB00BLDYK618   SMT         14.00000000     189.85         195.52            5.67
  2021-11-02      Section 104     US0378331005   Apple       26.22913238    2647.31        3653.35         1006.04
  2022-01-27      Section 104     US83088M1027   Skyworks     1.24584888     167.21         178.13           10.92
--------------------------------------------------------------------------------------------------------------------
Number of disposals:                                 7       Gains in the year, before losses:             £1715.67
Disposal proceeds:                            £8166.14       Losses in the year:                             £13.95
Allowable costs (including purchase price):   £6464.42

                                                 Tax year 2022-2023
--------------------------------------------------------------------------------------------------------------------
  Date Disposed   Date Acquired   ISIN           Name           Quantity   Cost (£)   Proceeds (£)   Gain/loss (£)
--------------------------------------------------------------------------------------------------------------------
  2022-09-20      Section 104     US0231351067   Amazon      48.31896981    3493.12        4941.53         1448.41
  2022-10-14      Section 104     US5949181045   Microsoft    1.32642000     324.79         319.76           -5.03
  2022-12-16      Section 104     US83088M1027   Skyworks     8.30000000    1094.16         979.69         -114.47
  2023-03-03      Section 104     US83088M1027   Skyworks     2.10000000     277.20         312.95           35.75
--------------------------------------------------------------------------------------------------------------------
Number of disposals:                                 4       Gains in the year, before losses:             £1484.16
Disposal proceeds:                            £6553.93       Losses in the year:                            £119.50
Allowable costs (including purchase price):   £5189.27
```

View cost, allocation weight, and unrealised gain/loss for open
positions:

```console
$ investir holdings --show-gain-loss data/freetrade.csv
---------------------------------------------------------------------------------------------------------------------
  ISIN           Name        Cost (£)   Allocation (%)       Quantity   Average Cost (£)   Unrealised Gain/Loss (£)
---------------------------------------------------------------------------------------------------------------------
  GB00BLDYK618   SMT          2196.81            55.88   162.00000000              13.56                    -696.37
  US5949181045   Microsoft     882.35            22.44     3.62439184             243.45                     314.96
  US0378331005   Apple         301.70             7.67     3.00000000             100.57                     225.20
  US83088M1027   Skyworks      301.08             7.66     2.29594360             131.13                    -145.75
  US70450Y1038   PayPal        249.59             6.35     4.13171759              60.41                      29.08
---------------------------------------------------------------------------------------------------------------------
                              3931.53           100.00                                                      -272.88
---------------------------------------------------------------------------------------------------------------------
```

View share buying and selling orders placed:

```console
$ investir orders data/freetrade.csv
----------------------------------------------------------------------------------------------------------------------------
  Date         ISIN           Name        Ticker   Total Cost (£)   Net Proceeds (£)       Quantity   Price (£)   Fees (£)
----------------------------------------------------------------------------------------------------------------------------
  2021-04-07   US0378331005   Apple       AAPL            1940.99                       20.13713692       96.15       4.76
  2021-06-05   US0378331005   Apple       AAPL             998.48                        9.09199546      109.33       4.47
  2021-06-11   US5949181045   Microsoft   MSFT            2715.44                       15.00246544      180.19      12.20
  2021-08-12   US83088M1027   Skyworks    SWKS            1497.76                       11.21263989      132.98       6.71
  2021-08-25   US5949181045   Microsoft   MSFT                               2939.35    13.00246544      227.07      13.13
  2021-08-26   GB00BLDYK618   SMT         SMT             2386.66                      176.00000000       13.49      11.90
  2021-09-01   US83088M1027   Skyworks    SWKS                                152.47     1.24584888      122.98       0.74
  2021-09-13   GB00BLDYK618   SMT         SMT                                1228.97    88.00000000       13.97       0.00
  2021-09-13   GB00BLDYK618   SMT         SMT              443.65                       34.00000000       13.03       0.78
  2021-09-26   GB00BLDYK618   SMT         SMT              482.67                       40.00000000       12.05       0.56
  2021-11-02   US0378331005   Apple       AAPL                               3643.81    26.22913238      139.29       9.54
  2022-01-27   US83088M1027   Skyworks    SWKS                                177.34     1.24584888      142.98       0.79
----------------------------------------------------------------------------------------------------------------------------
  2022-04-10   US70450Y1038   PayPal      PYPL             249.59                        4.13171759       60.05       1.46
  2022-05-12   US5949181045   Microsoft   MSFT             843.26                        2.95081184      284.09       4.95
  2022-07-09   US0231351067   Amazon      AMZN            3464.02                       48.31896981       71.27      20.36
  2022-09-20   US0231351067   Amazon      AMZN                               4912.43    48.31896981      102.27      29.10
  2022-09-28   US83088M1027   Skyworks    SWKS             499.95                        3.97500146      125.03       2.94
  2022-10-14   US5949181045   Microsoft   MSFT                                317.88     1.32642000      241.07       1.88
  2022-12-16   US83088M1027   Skyworks    SWKS                                973.95     8.30000000      118.03       5.74
  2023-03-03   US83088M1027   Skyworks    SWKS                                311.13     2.10000000      149.02       1.82
----------------------------------------------------------------------------------------------------------------------------
                                                         15522.47           14657.33                                133.83
----------------------------------------------------------------------------------------------------------------------------
```

View dividends paid out:

```console
$ investir dividends data/freetrade.csv
----------------------------------------------------------------------------------
  Date         ISIN           Name        Ticker   Amount (£)   Tax widhheld (£)
----------------------------------------------------------------------------------
  2022-02-12   US0378331005   Apple       AAPL           1.37               0.24
  2022-03-09   US5949181045   Microsoft   MSFT           3.44               0.61
  2022-03-15   US83088M1027   Skyworks    SWKS           2.50               0.44
----------------------------------------------------------------------------------
  2022-05-13   US5949181045   Microsoft   MSFT           4.12               0.72
  2022-06-08   US0378331005   Apple       AAPL           1.64               0.28
----------------------------------------------------------------------------------
                                                        13.07               2.29
----------------------------------------------------------------------------------
```

View interest on cash earned:

```console
$ investir interest data/freetrade.csv
--------------------------
  Date         Amount (£)
---------------------------
  2021-10-15         1.70
  2022-01-15         1.59
---------------------------
  2022-04-15         1.61
  2022-07-15         1.58
  2023-01-15         1.81
---------------------------
                     8.29
---------------------------
```

View cash deposits and withdrawals made:

```console
$ investir transfers data/freetrade.csv
---------------------------------------------
  Date         Deposited (£)   Withdrew (£)
---------------------------------------------
  2021-03-02         6000.00
---------------------------------------------
  2021-07-28         4000.00
  2022-02-24                         400.00
---------------------------------------------
  2022-04-08                         100.00
  2023-01-03         2000.00
---------------------------------------------
                    12000.00         500.00
---------------------------------------------
```

> [!TIP]
> Each command supports various options that can be used to filter the
> output based on several criteria. Use the `--help` option for any
> command for a description of all the available options.

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

## Limitations ⚠️

* No special handling takes place for the accumulation class of shares
  for an investment fund, where income from dividends or interest are
  automatically reinvested back into the fund. This means that in
  practice you might have to pay more tax on your income and less tax on
  capital gains when you sell the fund than what is reported.

* Multi-currency accounts in Trading 212 are not supported and the
  program will terminate if encounters transactions whose base currency
  is not in pound sterling (GBP). These transactions can be ignored
  instead by using the `--no-strict` command-line option.

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
[virtual environment]: https://docs.python.org/3/library/venv.html
[editable install]: https://setuptools.pypa.io/en/latest/userguide/development_mode.html
