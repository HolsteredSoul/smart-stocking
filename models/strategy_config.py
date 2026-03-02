"""
Strategy Configuration Models for SmartStock
Defines configuration dataclasses used by the screening pipeline.

Note: Strategy scoring logic lives in DataService (services/data_service.py).
These classes are data containers only.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd


@dataclass
class StrategyConfig:
    """Configuration for the screening process"""
    strategies: List[str]
    tickers: List[str]
    lookback_period: str = "1 Year"
    scoring_method: str = "Rank Aggregation"
    min_market_cap: float = 1000  # in millions
    exclude_sectors: List[str] = field(default_factory=list)
    custom_weights: Dict[str, float] = field(default_factory=dict)
    advanced_params: Dict[str, Any] = field(default_factory=dict)

    def get_period_days(self) -> int:
        """Convert lookback period string to days"""
        period_map = {
            "1 Month": 30,
            "3 Months": 90,
            "6 Months": 180,
            "1 Year": 365,
            "2 Years": 730,
        }
        return period_map.get(self.lookback_period, 365)

    def get_yfinance_period(self) -> str:
        """Convert lookback period to yfinance format"""
        period_map = {
            "1 Month": "1mo",
            "3 Months": "3mo",
            "6 Months": "6mo",
            "1 Year": "1y",
            "2 Years": "2y",
        }
        return period_map.get(self.lookback_period, "1y")

    def get_weight(self, strategy_name: str) -> float:
        """Get the weight for a specific strategy"""
        if not self.custom_weights:
            return 1.0
        return self.custom_weights.get(strategy_name, 1.0)

    def get_param(self, param_name: str, default: Any = None) -> Any:
        """Get an advanced parameter value"""
        return self.advanced_params.get(param_name, default)


@dataclass
class ScreeningResult:
    """Container for screening results"""
    timestamp: datetime
    config: StrategyConfig
    results: pd.DataFrame
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "config": {
                "strategies": self.config.strategies,
                "tickers": self.config.tickers,
                "lookback_period": self.config.lookback_period,
                "scoring_method": self.config.scoring_method,
                "min_market_cap": self.config.min_market_cap,
                "exclude_sectors": self.config.exclude_sectors,
                "custom_weights": self.config.custom_weights,
                "advanced_params": self.config.advanced_params,
            },
            "results": self.results.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ScreeningResult":
        """Create ScreeningResult from dictionary"""
        config = StrategyConfig(
            strategies=data["config"]["strategies"],
            tickers=data["config"]["tickers"],
            lookback_period=data["config"]["lookback_period"],
            scoring_method=data["config"]["scoring_method"],
            min_market_cap=data["config"]["min_market_cap"],
            exclude_sectors=data["config"]["exclude_sectors"],
            custom_weights=data["config"].get("custom_weights", {}),
            advanced_params=data["config"].get("advanced_params", {}),
        )
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            config=config,
            results=pd.DataFrame.from_dict(data["results"]),
            metadata=data.get("metadata", {}),
        )

    def get_top_stocks(self, n: int = 10) -> pd.DataFrame:
        """Get top N stocks by composite score"""
        return self.results.nlargest(n, "composite_score")

    def filter_results(
        self,
        min_score: float = 0,
        max_volatility: float = None,
        sectors: List[str] = None,
    ) -> pd.DataFrame:
        """Filter results by various criteria"""
        filtered = self.results[self.results["composite_score"] >= min_score]
        if max_volatility is not None and "volatility" in filtered.columns:
            filtered = filtered[filtered["volatility"] <= max_volatility]
        if sectors and "sector" in filtered.columns:
            filtered = filtered[filtered["sector"].isin(sectors)]
        return filtered


# ---------------------------------------------------------------------------
# Strategy classes — thin wrappers that delegate scoring to DataService.
# These exist so that tests and external code can use a typed, object-oriented
# API while keeping the actual scoring logic in one place (data_service.py).
# ---------------------------------------------------------------------------

class BaseStrategy:
    """Abstract base for all investment strategies."""

    def __init__(self, name: str, weight: float = 1.0, params: Dict[str, Any] = None):
        self.name = name
        self.weight = weight
        self.params = params or {}

    def get_param(self, key: str, default: Any = None) -> Any:
        """Return a strategy parameter value, or *default* if not set."""
        return self.params.get(key, default)

    def calculate_score(self, data) -> "pd.Series":
        raise NotImplementedError(f"{self.__class__.__name__} must implement calculate_score()")


class MomentumStrategy(BaseStrategy):
    """Scores stocks by price momentum (returns, moving averages, RSI, volume)."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Momentum", weight, params)

    def calculate_score(self, price_data: Dict) -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_momentum_scores(price_data)


class ValueStrategy(BaseStrategy):
    """Scores stocks by valuation metrics (P/E, P/B, P/S, EV/EBITDA)."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Value", weight, params)

    def calculate_score(self, fundamentals: "pd.DataFrame") -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_value_scores(fundamentals)


class GrowthStrategy(BaseStrategy):
    """Scores stocks by revenue, EPS growth and profit quality."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Growth", weight, params)

    def calculate_score(self, fundamentals: "pd.DataFrame") -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_growth_scores(fundamentals)


class QualityStrategy(BaseStrategy):
    """Scores stocks by balance-sheet quality (ROE, debt, liquidity)."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Quality", weight, params)

    def calculate_score(self, fundamentals: "pd.DataFrame") -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_quality_scores(fundamentals)


class IncomeStrategy(BaseStrategy):
    """Scores stocks by dividend yield and payout sustainability."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Income", weight, params)

    def calculate_score(self, fundamentals: "pd.DataFrame") -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_income_scores(fundamentals)


class LowVolatilityStrategy(BaseStrategy):
    """Scores stocks by low price volatility and market beta."""

    def __init__(self, weight: float = 1.0, params: Dict[str, Any] = None):
        super().__init__("Low Volatility", weight, params)

    def calculate_score(self, price_data: Dict) -> "pd.Series":
        from services.data_service import DataService
        return DataService().calculate_volatility_scores(price_data)


class CustomStrategy(BaseStrategy):
    """User-defined strategy with an arbitrary scoring function."""

    def __init__(
        self,
        name: str,
        description: str,
        metrics: List[str],
        scoring_function,
        weight: float = 1.0,
    ):
        super().__init__(name, weight)
        self.description = description
        self.metrics = metrics
        self._scoring_fn = scoring_function

    def calculate_score(self, data) -> "pd.Series":
        return self._scoring_fn(data)


class StrategyFactory:
    """Creates strategy instances by name."""

    _MAP: Dict[str, type] = {
        "Momentum":       MomentumStrategy,
        "Value":          ValueStrategy,
        "Growth":         GrowthStrategy,
        "Quality":        QualityStrategy,
        "Income":         IncomeStrategy,
        "Low Volatility": LowVolatilityStrategy,
    }

    @classmethod
    def create_strategy(
        cls,
        name: str,
        weight: float = 1.0,
        params: Dict[str, Any] = None,
    ) -> BaseStrategy:
        """Return a strategy instance for *name* with the given weight and params."""
        klass = cls._MAP.get(name)
        if klass is None:
            raise ValueError(f"Unknown strategy '{name}'. Valid names: {list(cls._MAP)}")
        return klass(weight=weight, params=params)

    @classmethod
    def create_strategies(
        cls,
        names: List[str],
        weights: Dict[str, float] = None,
    ) -> List[BaseStrategy]:
        """Return a list of strategy instances, one per name in *names*."""
        weights = weights or {}
        return [cls.create_strategy(n, weight=weights.get(n, 1.0)) for n in names]
