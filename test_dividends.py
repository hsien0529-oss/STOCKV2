import yfinance as yf
import pandas as pd
import datetime

def test_dividends(ticker_symbol):
    print(f"Testing dividends for {ticker_symbol}...")
    ticker = yf.Ticker(ticker_symbol)
    divs = ticker.dividends
    
    if divs.empty:
        print("No dividends found.")
        return

    divs.index = divs.index.tz_localize(None)
    
    current_year = datetime.datetime.now().year
    print(f"Current Year: {current_year}")
    
    divs_cur = divs[divs.index.year == current_year]
    print(f"Dividends in {current_year}:")
    print(divs_cur)
    print(f"Sum {current_year}: {divs_cur.sum()}")
    
    last_year = current_year - 1
    divs_last = divs[divs.index.year == last_year]
    print(f"Dividends in {last_year}:")
    print(divs_last)
    print(f"Sum {last_year}: {divs_last.sum()}")

    last_last_year = current_year - 2
    divs_last_last = divs[divs.index.year == last_last_year]
    print(f"Dividends in {last_last_year}:")
    print(divs_last_last)
    print(f"Sum {last_last_year}: {divs_last_last.sum()}")

if __name__ == "__main__":
    test_dividends("2330.TW") # TSMC
    test_dividends("0050.TW") # ETF
