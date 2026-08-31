# Mean-Reversion Backtesting Project

This project implements a weekly mean-reversion equity strategy using Python. The strategy evaluates weekly price changes for a configurable list of tickers and generates trading signals based on predefined thresholds. It simulates positions and outputs performance statistics to assess the strategy's effectiveness.

## Overview

The mean-reversion strategy operates on the following logic:
- A long position is opened if a stock's price drops by 5% or more over the past week.
- A short position is opened if a stock's price rises by 10% or more over the past week.

The strategy is evaluated on a weekly basis for each ticker in the specified tradable universe.

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd mean-reversion-backtest
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the backtesting script, execute the following command:
```
python backtest.py
```

Make sure to configure the parameters at the top of the `backtest.py` file, including the ticker universe, position sizes, and thresholds for long and short signals.

## Performance Statistics

The backtesting script will output the following performance statistics:
- Total return
- Win rate (percentage of winning vs. losing trades)
- Longest streak of consecutive losing days
- Monthly P&L table
- Equity curve chart

## Note

This is a naive backtest and does not account for slippage, transaction costs, or execution latency. In a real-world scenario, the strategy would depend on high-speed and low-latency execution.