# SmartStock: Multi-Strategy Stock Screener

A comprehensive stock screening application built with Streamlit that implements multiple investment strategies including Momentum, Value, Growth, Quality, Income, and Low Volatility.

## Features

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

SmartStock is for informational purposes only. Always conduct your own research and consult with financial professionals before making investment decisions. Past performance does not guarantee future results.

---

**Version**: 1.0 MVP
**Last Updated**: February 2026
