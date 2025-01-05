import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def download_dynamic_stocks(tickers, output_csv="stocks_dynamic.csv"):
    """
    Download daily close prices for the given tickers from (today - 1 year)
    up to (today - 1 day), and store them in a CSV file.

    :param tickers: list of stock tickers (e.g., ["AMZN", "KO", "MSFT"])
    :param output_csv: path/filename for the output CSV
    """
    # 1) Calculate dynamic dates
    today = datetime.now()
    end_date = today - timedelta(days=1)        # Yesterday
    start_date = end_date - timedelta(days=365) # 1 year prior to yesterday

    start_str = start_date.strftime("%Y-%m-%d")
    end_str   = end_date.strftime("%Y-%m-%d")

    print(f"Fetching data from {start_str} to {end_str} ...")

    # 2) Initialize an empty DataFrame to store all tickers
    stocks_df = pd.DataFrame()

    # 3) Loop through each ticker and download data
    for ticker in tickers:
        print(f"  - Fetching data for {ticker} ...")
        ticker_data = yf.Ticker(ticker)
        hist_data   = ticker_data.history(start=start_str, end=end_str)

        # If there's no data, skip
        if hist_data.empty:
            print(f"    No data found for {ticker} in the specified period.")
            continue

        # Only keep the "Close" column
        stocks_df[ticker] = hist_data["Close"]

    # 4) If stocks_df is not empty, save to CSV
    if not stocks_df.empty:
        # Round for readability (optional)
        stocks_df = stocks_df.round(2)

        # Write to CSV
        stocks_df.to_csv(output_csv, index=True)
        print(f"Data successfully saved to '{output_csv}'.")
    else:
        print("No data was retrieved for any tickers.")

if __name__ == "__main__":
    # Example usage
    tickers_list = ["AMZN", "KO", "MSFT"]  # Add or modify as needed
    download_dynamic_stocks(tickers_list, output_csv="stocks_dynamic.csv")
