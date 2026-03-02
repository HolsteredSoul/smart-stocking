# SmartStock TODO

> Tasks are organized by priority. Each item is scoped to one sitting.
> File paths reference the exact location of the change needed.

---

## Critical — Broken or Blocking

- [x] **Fix broken test imports** — `tests/test_strategies.py` imports 8 classes that don't exist: `StrategyFactory`, `MomentumStrategy`, `ValueStrategy`, `GrowthStrategy`, `QualityStrategy`, `IncomeStrategy`, `LowVolatilityStrategy`, `CustomStrategy`. Either implement these classes in `models/strategy_config.py` or rewrite the tests to match the current architecture (scoring logic lives in `services/data_service.py`). Currently ~83% of tests fail immediately on import.

- [x] **Delete `app_backup.py`** — A stale 1,061-line copy of an older version of the main app. It adds confusion and is not imported anywhere. Safe to delete.

- [x] **Fix composite score inconsistency in demo mode** — `app.py` lines 852–855 calculate composite score as a plain `np.mean()` of all 6 strategy scores, bypassing the 3 configurable scoring methods (Rank Aggregation, Percentile, Custom Weights) that live in `services/data_service.py`. Demo mode results should use the same calculation path as real data.

---

## High — Ease of Use & Guiding Users to the Best Picks

These tasks make the app useful for someone with no investment background.

- [x] **Add "Best Pick" spotlight card at the top of results** — Show the single highest-scoring stock prominently above the results table with its name, score, and a one-line reason (e.g., "Ranked #1 across your selected strategies"). Users should not have to read a table to find the winner. (`app.py`, Analysis page section)

- [x] **Add score tier labels and color coding** — A score of 72 is meaningless without context. Add a tier system: **Excellent** (80–100, green), **Good** (60–79, blue), **Average** (40–59, yellow), **Weak** (below 40, red). Apply these as colored badges in the results table and in the individual stock detail view. (`app.py`, `utils/enhanced_ui.py`)

- [x] **Add a plain-English summary sentence per stock** — Auto-generate a one-sentence description based on which strategies score highest, e.g. _"Strong momentum and growth stock with moderate valuation — suits an aggressive growth investor."_ Display it in the stock detail header. (`app.py`, individual stock detail section ~line 620)

- [x] **Add "Why this score?" breakdown in plain English** — Beneath each strategy score bar, show the 1–2 metrics that drove it. Example: _"Value score of 78 — low P/E (12.3) and P/B (1.4) signal the stock is underpriced."_ The factor data is already calculated in `data_service.py`; it just needs to be surfaced in the UI.

- [x] **Add a beginner "Investor Goal" selector** — At the top of the Screening page, offer 4–5 plain-English goals: _"I want steady income"_, _"I want long-term growth"_, _"I want low-risk stability"_, _"I want undervalued bargains"_, _"Balanced mix"_. Each maps to a preset strategy weight blend (presets already exist in `utils/enhanced_ui.py` lines 151–158). Hide the technical weight sliders by default; show them only in an "Advanced" expander.

- [x] **Label quadrants on the Risk vs. Score scatter plot** — The scatter plot in `utils/visualization.py:create_risk_return_scatter()` draws median lines but leaves quadrants blank. Add text annotations: _"Sweet Spot"_ (high score, low risk), _"High Risk / High Reward"_, _"Avoid"_ (low score, high risk), _"Safe but Slow"_. This makes the chart self-explanatory without needing a legend.

- [x] **Promote the Factor Contribution waterfall chart** — The `create_factor_contribution()` chart in `utils/visualization.py` shows exactly what drove each stock's score vs. the market average — it's the most insightful chart in the app but is buried. Move it to the top of the individual stock detail view, above the metric grid.

- [x] **Add sector diversification warning** — If the top 5 results are all from the same sector (e.g., all Technology), warn the user: _"Your top picks are heavily concentrated in one sector — consider diversifying."_ Calculate sector distribution from the results DataFrame in `app.py` after scoring.

- [x] **Add a "Recommended Stock Lists" shortcut** — Pre-load curated ticker sets with friendly names beyond the current technical presets. Examples: _"Dividend Aristocrats"_, _"Blue Chip Stability"_, _"High Growth Tech"_, _"Defensive Stocks"_. Include a short sentence describing each list. (`app.py`, ticker input section)

- [x] **Make the scoring method selector beginner-friendly** — The dropdown currently shows "Rank Aggregation", "Percentile Scoring", "Custom Weights" with no explanation. Add a tooltip or inline description for each: e.g., _"Rank Aggregation — compares stocks against each other (recommended for most users)"_.

---

## High — Stock Picking Technical Improvements

These tasks make the scores more accurate and meaningful.

- [x] **Add RSI (Relative Strength Index) to Momentum scoring** — Current momentum scoring only uses price returns and SMAs. Add RSI-14 as a component: RSI 40–70 = healthy momentum (bonus points), RSI > 70 = overbought (cap bonus), RSI < 30 = oversold (penalty). RSI can be calculated from the price data already fetched. (`services/data_service.py:calculate_momentum_scores()`)

- [x] **Add volume confirmation to Momentum scoring** — A price increase on above-average volume is a stronger momentum signal. Compare recent volume to the 20-day average volume; give a bonus when price is up and volume is elevated. (`services/data_service.py:calculate_momentum_scores()`)

- [x] **Add P/S ratio to Value scoring** — Current value scoring uses P/E, P/B, and EV/EBITDA. P/S (Price-to-Sales) ratio is a key metric especially for companies with low or negative earnings. P/S < 2 is generally cheap; P/S > 10 is expensive. Add it as a 4th component. (`services/data_service.py:calculate_value_scores()`)

- [ ] **Add sector-relative value thresholds** — The current value thresholds are absolute (e.g., P/E < 15 = max points). A P/E of 25 is cheap for software but expensive for retail. Normalise thresholds by sector median to make scoring relative to peers. Sector data is already present in fundamentals. (`services/data_service.py:calculate_value_scores()`)

- [ ] **Replace revenue growth dividend proxy in Income scoring with actual dividend history** — Current income scoring uses revenue growth as a proxy for dividend sustainability. `yfinance` provides the actual `dividends` time series — use it to check dividend consistency (paid every quarter) and dividend growth direction (increasing year-over-year). (`services/data_service.py:calculate_income_scores()`)

- [x] **Add Piotroski F-Score to Quality scoring** *(simplified — 3 of 9 signals)* — Implemented a simplified 3-signal version using available data: positive ROE (profitability), D/E < 1.0 (leverage), current ratio > 1.0 (liquidity). Full 9-signal version requires additional historical data not yet fetched. (`services/data_service.py:calculate_quality_scores()`)

- [x] **Add earnings quality check to Growth scoring** — High reported earnings growth can be misleading if cash flow from operations is not growing at a similar rate. Add a cash flow confirmation factor: if `operatingCashflow` growth matches or exceeds `epsGrowth`, give a bonus; if earnings are growing but cash flow is flat, apply a penalty. (`services/data_service.py:calculate_growth_scores()`)

- [x] **Add 52-week high/low positioning to Momentum scoring** — Stocks trading near their 52-week high with strong volume are in confirmed uptrends. Add a component: price within 5% of 52-week high = bonus, price within 20% of 52-week low = penalty. Derivable from fetched price data. (`services/data_service.py:calculate_momentum_scores()`)

- [x] **Normalize all strategy scores to be relative (percentile-within-screened-set), not absolute** — Currently all strategy scores are based on fixed thresholds (e.g., P/E < 15 = 30 pts). This means a set of 30 expensive tech stocks will all score low on value regardless of their relative ranking. Add a percentile normalization step after raw scoring so scores reflect rank within the screened universe. (`services/data_service.py:_calculate_composite_score()`)

---

## Medium — Incomplete Features

- [x] **Implement a basic backtest engine** — The backtest UI is fully built in `utils/enhanced_ui.py` lines 505–626 but returns hardcoded sample results. Implement the engine: for a given strategy config and date range, apply the scoring model at the start date, form a hypothetical equal-weight portfolio of the top N stocks, then calculate actual return using fetched historical price data. (`services/data_service.py` — new `run_backtest()` method)

- [x] **Implement PDF report export** — `utils/enhanced_ui.py:500` has a placeholder. Use `reportlab` or `fpdf2` (add to `requirements.txt`) to generate a single-page PDF per stock with the key metrics, score breakdown, and the factor contribution chart. (`utils/enhanced_ui.py`, export tab section)

- [x] **Implement batch ticker data fetching** — `utils/data_cache_manager.py:380–399` raises `NotImplementedError`. `yfinance.download()` accepts a list of tickers in one call and is significantly faster than looping. Implement the batch path for price data and fall back to individual calls for fundamentals. (`utils/data_cache_manager.py:fetch_multiple_tickers()`)

- [x] **Add missing strategy classes to satisfy tests** — Once a decision is made on whether to keep the test file or rewrite it, implement `StrategyFactory` and per-strategy classes (`MomentumStrategy`, `ValueStrategy`, etc.) as thin wrappers around the scoring methods in `data_service.py`. This gives a cleaner API and makes unit testing possible. (`models/strategy_config.py`)

---

## Low — Infrastructure & Maintenance

- [x] **Add GitHub Actions CI workflow** — Create `.github/workflows/ci.yml` to run `pytest tests/test_strategies.py::TestStrategyConfig` on every push and pull request. Blocks merges if tests fail.

- [x] **Add `pyproject.toml`** — Centralise project metadata, Python version requirement, tool config (black, isort, pytest settings). Makes the project installable with `pip install -e .` for development.

- [x] **Add `.streamlit/config.toml`** — Set explicit defaults for theme (light/dark), server port, and `maxUploadSize` instead of relying on Streamlit defaults. Prevents surprises across different deployment environments.

- [ ] **Add `Dockerfile` and `docker-compose.yml`** — `Dockerfile` added. `docker-compose.yml` not yet created.

- [x] **Add integration test documentation to README** — The `TestDataService` class is silently skipped unless `RUN_INTEGRATION_TESTS=true` is set. Document this in `README.md` so contributors know how to run the full test suite.

- [x] **Centralise magic numbers into a constants module** — Scoring thresholds (P/E < 15, ROE > 20%, etc.), cache expiry times (5 min, 7 days), and default weights are hardcoded in multiple files. Move them to `models/constants.py` so they can be adjusted in one place.

---

## Identified in v1.1 Review — Next Improvements

*Added from post-implementation review (March 2026). Priority order within each section.*

### Technical — Scoring & Data

- [ ] **Add sector-relative value thresholds** *(carries over from High section above)* — A P/E of 25 is cheap for software but expensive for retail. After fetching fundamentals, compute sector medians for P/E, P/B, P/S, EV/EBITDA across the screened set, then score each stock relative to its sector peers rather than against absolute cut-offs. (`services/data_service.py:calculate_value_scores()`)

- [ ] **Replace revenue-growth dividend proxy with actual dividend history** *(carries over from High section above)* — Fetch the `yfinance` `Ticker.dividends` Series for each ticker. Use it to check: (1) paid every quarter for the last 2 years, (2) year-over-year dividend growth direction. Bump sustainable/growing payers, penalise sporadic ones. (`services/data_service.py:calculate_income_scores()` + data-fetch pipeline)

- [ ] **Upgrade to full 9-signal Piotroski F-Score** — Current implementation covers 3 signals (ROE, D/E, current ratio). The remaining 6 signals — cash flow from operations positive, ROA improving YoY, accruals (CFO > net income), leverage trend, gross margin trend, asset turnover trend — require two years of income statement + cash flow data. Fetch them via `yfinance Ticker.financials` / `Ticker.cashflow` and integrate. (`services/data_service.py:calculate_quality_scores()`)

- [ ] **Add transaction costs and slippage to the backtest engine** — `run_backtest()` currently assumes zero cost. Add a configurable round-trip cost parameter (default 0.1% per trade) applied at portfolio formation. Also add a liquidity filter: exclude stocks with average daily dollar volume below a threshold (e.g. <$1M) to avoid unrealistic fills. (`services/data_service.py:run_backtest()`)

### UX — Discovery & Accessibility

- [ ] **Add a stock universe browser so users don't need to know ticker symbols** — Currently users must type tickers manually or pick a preset list. Add a searchable dropdown backed by a static list of S&P 500 (or Russell 2000) constituents — user types a company name and gets the ticker. A CSV of index constituents is small (~10 KB) and can ship with the repo. (`app.py`, ticker input section; new `data/sp500_tickers.csv`)

- [ ] **Add `docker-compose.yml`** — `Dockerfile` is present. A `docker-compose.yml` lets users start the whole app with a single `docker compose up` without needing to remember the `docker run` flags. Two-service version: `app` (Streamlit) + optional `nginx` reverse proxy for local HTTPS. (`docker-compose.yml` in root)

### Code Quality

- [ ] **Deduplicate `STRATEGY_SCORE_COLUMNS` between `app.py` and `data_service.py`** — The canonical mapping (`Momentum → momentum_score`, etc.) is defined in both files and must stay in sync manually. Move it to `models/constants.py` and import from there in both files. Low risk, one-line change in two files. (`models/constants.py`, `app.py`, `services/data_service.py`)
