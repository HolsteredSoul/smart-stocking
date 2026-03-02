"""
SmartStock — Centralised constants.

Move magic numbers here so they can be adjusted in one place instead of
hunting through scoring functions, cache managers, and UI code.
"""

# ---------------------------------------------------------------------------
# Value strategy scoring thresholds  (metric_max_value, points_awarded)
# ---------------------------------------------------------------------------

# P/E ratio — lower is better
PE_THRESHOLDS = [
    (15, 25),
    (20, 17),
    (30,  8),
]

# P/B ratio — lower is better
PB_THRESHOLDS = [
    (1.5, 20),
    (2.5, 12),
    (3.5,  4),
]

# EV/EBITDA — lower is better
EV_EBITDA_THRESHOLDS = [
    (10, 20),
    (15, 12),
    (20,  4),
]

# P/S ratio — lower is better
PS_THRESHOLDS = [
    (2, 20),
    (4, 12),
    (8,  5),
]

# ---------------------------------------------------------------------------
# Growth strategy thresholds  (growth_pct_min, points_awarded)
# ---------------------------------------------------------------------------

REVENUE_GROWTH_THRESHOLDS = [
    (15, 40),
    (10, 30),
    ( 5, 20),
    ( 0, 10),
]

EPS_GROWTH_THRESHOLDS = [
    (20, 40),
    (15, 30),
    (10, 20),
    ( 0, 10),
]

PROFIT_MARGIN_THRESHOLDS = [
    (20, 20),
    (10, 10),
]

# ---------------------------------------------------------------------------
# Quality strategy thresholds
# ---------------------------------------------------------------------------

ROE_THRESHOLDS = [
    (20, 30),
    (15, 20),
    (10, 10),
]

DEBT_EQUITY_THRESHOLDS = [
    (0.5,  25),
    (1.0,  15),
    (2.0,   5),
]

CURRENT_RATIO_THRESHOLDS = [
    (2.0, 25),
    (1.5, 15),
    (1.0,  5),
]

PROFIT_MARGIN_QUALITY_THRESHOLDS = [
    (15, 20),
    (10, 10),
    ( 5,  5),
]

# Piotroski F-Score bonus per signal
PIOTROSKI_POINTS_PER_SIGNAL = 3  # max 9 total

# ---------------------------------------------------------------------------
# Volatility strategy thresholds
# ---------------------------------------------------------------------------

VOLATILITY_THRESHOLDS = [
    (0.15, 50),
    (0.20, 40),
    (0.25, 30),
    (0.30, 20),
]

BETA_THRESHOLDS = [
    (0.8, 40),
    (1.0, 30),
    (1.2, 20),
]

# ---------------------------------------------------------------------------
# Momentum scoring parameters
# ---------------------------------------------------------------------------

# Weighted returns across lookback periods
MOMENTUM_PERIOD_WEIGHTS = {
    "1m":  0.10,
    "3m":  0.20,
    "6m":  0.30,
    "12m": 0.40,
}

# RSI-14 bands: (rsi_min, rsi_max, multiplier)
RSI_ADJUSTMENTS = [
    (40, 70,  1.05),   # healthy momentum — bonus
    (75, 100, 0.95),   # overbought — penalty
]

# Volume confirmation multiplier when price up on high volume
VOLUME_CONFIRM_MULTIPLIER = 1.05
VOLUME_CONFIRM_RATIO      = 1.20  # recent vol must exceed this × avg vol

# 52-week positioning
HIGH_52W_PROXIMITY_THRESHOLD = -0.05  # within 5% of 52-week high → bonus
HIGH_52W_BONUS_MULTIPLIER    =  1.05
LOW_52W_PROXIMITY_THRESHOLD  =  0.20  # within 20% above 52-week low → penalty
LOW_52W_PENALTY_MULTIPLIER   =  0.92

# ---------------------------------------------------------------------------
# Cache expiry (seconds)
# ---------------------------------------------------------------------------

PRICE_CACHE_TTL_SECS          =     300   # 5 minutes
FUNDAMENTALS_CACHE_TTL_SECS   = 604_800   # 7 days
MARKET_HOURS_CACHE_TTL_SECS   =     300   # 5 minutes during trading hours
AFTER_HOURS_CACHE_TTL_SECS    =   3_600   # 1 hour after market close

# ---------------------------------------------------------------------------
# Score tier thresholds  (used in app.py score_tier())
# ---------------------------------------------------------------------------

SCORE_TIERS = [
    (80, "Excellent", "#28a745"),
    (60, "Good",      "#17a2b8"),
    (40, "Average",   "#ffc107"),
    ( 0, "Weak",      "#dc3545"),
]
