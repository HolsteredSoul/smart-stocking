# SmartStock: Multi-Strategy Stock Screener

A comprehensive stock screening application built with Streamlit that implements multiple investment strategies including Momentum, Value, Growth, Quality, Income, and Low Volatility.

---

## Quick Start — Run it in 5 minutes (no coding experience needed)

> **What is this?** SmartStock is a personal stock research tool that runs on your computer. You type in a few stock tickers (like AAPL, MSFT, TSLA), choose what you care about (growth? income? low risk?), and it scores and ranks them for you with clear charts and plain-English explanations.

### Step 1 — Check if Python is installed

Open a **Terminal** (Mac) or **Command Prompt** (Windows):

- **Mac**: Press `⌘ + Space`, type `Terminal`, press Enter
- **Windows**: Press the Windows key, type `cmd`, press Enter

Then type this and press Enter:

```
python --version
```

If you see something like `Python 3.10.x` or higher, you're good. If you get an error:

> **Install Python**: Go to [python.org/downloads](https://www.python.org/downloads/), click the big yellow "Download Python" button, and run the installer. On Windows, **tick the "Add Python to PATH" checkbox** before clicking Install.

### Step 2 — Download SmartStock

**Option A — If you have Git installed:**

```
git clone https://github.com/HolsteredSoul/smart-stocking.git
cd smart-stocking
```

**Option B — Download as a ZIP (easier for beginners):**

1. Go to the GitHub page for this project
2. Click the green **"Code"** button → **"Download ZIP"**
3. Unzip the downloaded file to a folder you can find easily (e.g. your Desktop)
4. In your Terminal/Command Prompt, navigate into the folder:
   - **Mac**: `cd ~/Desktop/smart-stocking`
   - **Windows**: `cd C:\Users\YourName\Desktop\smart-stocking`

### Step 3 — Install the required packages

Copy and paste this command, then press Enter. It will download everything SmartStock needs (takes 1–3 minutes):

```
pip install -r requirements.txt
```

You'll see a lot of text scroll by — that's normal. Wait until you get back to the `>` or `$` prompt.

> **Having trouble?** If you see a "permission denied" error, try: `pip install --user -r requirements.txt`

### Step 4 — Launch the app

```
streamlit run app.py
```

Your default web browser will open automatically at `http://localhost:8501`. If it doesn't, copy that address and paste it into your browser.

> **To stop the app** later: click back into the Terminal window and press `Ctrl + C`.

---

### Your first screen (2-minute walkthrough)

Once the app opens in your browser:

**1. Tell it your goal** *(top of the Screening page)*

Pick one of the plain-English goals, for example:
- *"I want steady income (dividends)"* — focuses on high-yield, stable companies
- *"I want long-term growth"* — focuses on revenue and earnings growth
- *"I want low-risk, stable stocks"* — focuses on low volatility

**2. Choose your stocks** *(Stock Selection section)*

Either type tickers yourself (e.g. `AAPL, MSFT, JNJ`) or click **"Or choose a preset list"** and pick something like *"Dividend Aristocrats"* or *"Blue Chip Stability"* from the dropdown. Start with 5 stocks to keep it fast.

**3. Click "Run Analysis"**

SmartStock fetches live data from Yahoo Finance and scores each stock. This takes 15–60 seconds depending on how many stocks you chose.

**4. Read your results** *(switch to the "Analysis" tab)*

- The **⭐ Top Pick** card highlights the best-scoring stock for your goal
- The **results table** shows each stock's score with a tier label (Excellent / Good / Average / Weak)
- Click any stock name in the dropdown to see a detailed breakdown, including a chart that shows *exactly why* it scored the way it did

**5. Export** if you want to save your results — use the CSV, Excel, or PDF buttons below the table.

---

### If the data won't load (rate limit fix)

Yahoo Finance limits how often you can fetch data for free. If you see an error or empty results:

1. Wait 2–3 minutes and try again
2. Reduce the number of stocks (start with just 3–5)
3. Click **"Try Demo Mode"** to explore the app with simulated data while you wait

---

### Optional: Keep data fresher with free API keys

The app works fine without these, but adding them unlocks faster data and better reliability:

1. Get a free key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key) (5 sec sign-up)
2. Create a file at `.streamlit/secrets.toml` in the app folder
3. Add this line (replace with your actual key):
   ```toml
   ALPHA_VANTAGE_API_KEY = "YOUR_KEY_HERE"
   ```
4. Restart the app

---



- **Multi-Strategy Analysis**: Apply up to 6 different investment strategies simultaneously
- **Interactive Visualizations**: Dynamic charts and graphs using Plotly (radar charts, bar charts, score distributions)
- **Customizable Screening**: Adjust strategy weights, thresholds, and parameters to match your investment style
- **Preset Strategy Blends**: Choose from Classic Value, Balanced Growth, Dividend Focus, Momentum Tilt, or Defensive presets
- **Stock Comparison**: Side-by-side analysis of multiple stocks with radar chart overlays
- **Export Options**: Download results in CSV or Excel format
- **Multiple Data Sources**: Yahoo Finance (primary), with optional Alpha Vantage, Finnhub, FMP, and Polygon.io fallbacks
- **Smart Caching**: Session-based data cache with market-hours awareness to minimize API calls
- **Demo Mode**: Simulated data for testing when APIs are rate-limited
- **Save & Load Strategies**: Persist your custom strategy configurations as JSON files

## Project Structure

```
smartstock/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── readme.md                       # Project documentation
├── .gitignore                      # Git ignore file
├── services/
│   ├── __init__.py
│   └── data_service.py             # Data fetching, scoring, and screening pipeline
├── models/
│   ├── __init__.py
│   └── strategy_config.py          # Strategy definitions and configuration models
├── utils/
│   ├── __init__.py
│   ├── visualization.py            # Chart generation (Plotly)
│   ├── enhanced_ui.py              # Advanced UI components and settings
│   ├── data_cache_manager.py       # Session-based data caching
│   └── session_state_manager.py    # Robust parameter state handling
├── pages/
│   ├── __init__.py
│   └── troubleshooting.py          # Diagnostics and debugging page
├── tests/
│   └── test_strategies.py          # Strategy tests
├── .streamlit/
│   ├── secrets.toml                # API keys (not in repo)
│   └── strategies/                 # Saved strategy configurations
└── assets/                         # Static assets
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/smartstock.git
cd smartstock
```

2. Create a virtual environment:
```bash
python -m venv smartstock-env
source smartstock-env/bin/activate  # On Windows: smartstock-env\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Set up API keys for additional data sources:
Create a `.streamlit/secrets.toml` file:
```toml
ALPHA_VANTAGE_API_KEY = "your_key_here"
FINNHUB_API_KEY = "your_key_here"
FMP_API_KEY = "your_key_here"
POLYGON_API_KEY = "your_key_here"
```

5. Run the application:
```bash
streamlit run app.py
```

## Usage

### Stock Screening

1. **Select Strategies**: Choose which investment strategies to apply (Momentum, Value, Growth, etc.)
2. **Customize Weights**: Adjust how much each strategy contributes to the final score, or pick a preset blend
3. **Fine-tune Parameters**: Tweak specific thresholds for each strategy (P/E cutoffs, growth rates, etc.)
4. **Enter Tickers**: Input stock symbols or select from preset lists (FAANG, Dividend Kings, etc.)
5. **Run Analysis**: Click "Run Analysis" to process the stocks
6. **Review Results**: Explore detailed analysis, visualizations, and per-stock breakdowns

### Stock Comparison

1. Run a screening first to populate results
2. Navigate to the Comparison page
3. Select 2-5 stocks to compare side by side
4. Review radar charts and score comparisons

## Investment Strategies

| Strategy | Focus | Key Metrics |
|----------|-------|-------------|
| **Momentum** | Price trend strength | 1/3/6/12-month returns, SMA 50/200 |
| **Value** | Undervaluation | P/E, P/B, EV/EBITDA, dividend yield |
| **Growth** | Earnings expansion | Revenue growth, EPS growth, profit margins |
| **Quality** | Financial strength | ROE, debt/equity, current ratio, margins |
| **Income** | Dividend sustainability | Yield, payout ratio, dividend growth |
| **Low Volatility** | Price stability | Annualized volatility, beta, downside deviation |

## Scoring Methods

1. **Rank Aggregation**: Sums ranks across strategies (Greenblatt's Magic Formula approach)
2. **Percentile Scoring**: Converts scores to percentiles for equal weighting
3. **Custom Weights**: Manual weight assignment to each strategy

## Configuration

### Data Sources
- **Yahoo Finance**: Primary data source via `yfinance` (free, rate-limited)
- **Alpha Vantage**: Alternative for fundamental data (free tier: 5 calls/min)
- **Finnhub**: Real-time and historical data (free tier: 60 calls/min)
- **Financial Modeling Prep**: Company financials and historical prices
- **Polygon.io**: Comprehensive market data API

### Rate Limit Tips
- Recommended: 5 or fewer stocks per analysis
- Wait 1-2 minutes between analyses if rate-limited
- Use Demo Mode for testing without API calls
- Add API keys for additional fallback sources

## Testing

### Unit tests (no API calls, no Streamlit required)

```bash
pip install pandas numpy aiohttp pytest
python -m pytest tests/test_strategies.py -v
```

Expected output: **8 passed, 1 skipped** (the `TestDataService` integration test
is skipped unless the flag below is set).

### Integration tests (real Yahoo Finance API)

```bash
RUN_INTEGRATION_TESTS=true python -m pytest tests/test_strategies.py -v
```

This runs `TestDataService.test_fetch_stock_data` which makes live network calls.
Ensure you are not rate-limited before running.

### CI

A GitHub Actions workflow runs the unit tests on every push:
`.github/workflows/ci.yml`

## Docker

```bash
docker build -t smartstock .
docker run -p 8501:8501 smartstock
```

Open `http://localhost:8501` in your browser.

## Project Structure

```
smart-stocking/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata and tool config
├── Dockerfile                      # Container image
├── .github/workflows/ci.yml        # CI pipeline
├── services/
│   └── data_service.py             # Data fetching, scoring, backtest engine
├── models/
│   ├── strategy_config.py          # StrategyConfig, strategy classes, StrategyFactory
│   └── constants.py                # Centralised scoring thresholds and constants
├── utils/
│   ├── visualization.py            # Plotly chart builders
│   ├── enhanced_ui.py              # Advanced UI, PDF export, backtest UI
│   ├── data_cache_manager.py       # Session-based data caching + batch fetch
│   └── session_state_manager.py    # Robust parameter state handling
├── pages/
│   └── troubleshooting.py          # Diagnostics page
├── tests/
│   └── test_strategies.py          # Unit + integration tests
└── .streamlit/
    ├── config.toml                 # Streamlit server/theme config
    └── secrets.toml                # API keys (not committed)
```

## License

This project is licensed under the MIT License — see the LICENSE file for details.

## Disclaimer

SmartStock is for informational purposes only. Always conduct your own research and consult with financial professionals before making investment decisions. Past performance does not guarantee future results.

---

**Version**: 1.1
**Last Updated**: March 2026
