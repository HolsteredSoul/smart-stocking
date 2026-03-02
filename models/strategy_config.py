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
