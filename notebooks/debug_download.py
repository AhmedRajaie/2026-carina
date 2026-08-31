import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import yfinance as yf

candidate_tickers = ["AAPL"]


def download_stock_data(tickers, start_date="2015-01-01", end_date="2024-12-31"):
    """Download stock data from Yahoo Finance one ticker at a time."""
    for ticker in tickers:
        try:
            print('attempt', ticker)
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                actions=False,
            )
            print('download type', type(df), 'empty?', getattr(df, 'empty', None), 'cols', getattr(df, 'columns', None))

            if df is None or df.empty:
                print('empty continue')
                continue

            if isinstance(df.columns, pd.MultiIndex):
                if "Close" in df.columns.get_level_values(0):
                    df = df["Close"]
                elif "Adj Close" in df.columns.get_level_values(0):
                    df = df["Adj Close"]
                else:
                    print('multiindex no close')
                    continue

            if isinstance(df, pd.Series):
                df = df.to_frame(name="Close")
                print('series to frame ok', df.head())

            df = df.reset_index().copy()
            df.columns = [str(c).lower() for c in df.columns]
            print('after reset cols', df.columns)

            if "date" not in df.columns and "datetime" in df.columns:
                df = df.rename(columns={"datetime": "date"})
            if "close" not in df.columns and "adj close" in df.columns:
                df = df.rename(columns={"adj close": "close"})
            if "close" not in df.columns:
                print('no close col'); continue

            df = df[["date", "close"]].copy()
            df["date"] = pd.to_datetime(df["date"])
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
            df["ticker"] = ticker
            print('SUCCESS', ticker, df.shape)
            return df

        except Exception as exc:
            print('Ticker', ticker, 'failed:', type(exc).__name__, exc)

    raise ValueError("No stock data could be downloaded for the provided tickers.")


stock_df = download_stock_data(candidate_tickers)
print(stock_df.head())
