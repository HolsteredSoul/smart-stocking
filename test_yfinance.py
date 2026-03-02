import yfinance as yf
import pandas as pd

def test_yfinance():
    try:
        msft = yf.Ticker("MSFT")
        hist = msft.history(period="1mo")
        print(f"Success! Got {len(hist)} rows of data")
        print(hist.head())
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing yfinance...")
    test_yfinance()