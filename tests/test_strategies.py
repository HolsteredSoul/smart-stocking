"""
Unit Tests for SmartStock
Tests core functionality to ensure reliability
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
import asyncio

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from models.strategy_config import (
    StrategyConfig, 
    StrategyFactory, 
    MomentumStrategy,
    ValueStrategy,
    GrowthStrategy,
    QualityStrategy,
    IncomeStrategy,
    LowVolatilityStrategy,
    CustomStrategy
)

from services.data_service import DataService

class TestStrategyConfig(unittest.TestCase):
    """Test StrategyConfig functionality"""
    
    def test_period_conversion(self):
        """Test period conversion methods"""
        config = StrategyConfig(
            strategies=["Momentum", "Value"],
            tickers=["AAPL", "MSFT"],
            lookback_period="1 Year"
        )
        
        self.assertEqual(config.get_period_days(), 365)
        self.assertEqual(config.get_yfinance_period(), "1y")
        
        # Test different periods
        config.lookback_period = "3 Months"
        self.assertEqual(config.get_period_days(), 90)
        self.assertEqual(config.get_yfinance_period(), "3mo")
    
    def test_weight_retrieval(self):
        """Test weight retrieval for strategies"""
        custom_weights = {
            "Momentum": 2.0,
            "Value": 1.0
        }
        
        config = StrategyConfig(
            strategies=["Momentum", "Value", "Growth"],
            tickers=["AAPL", "MSFT"],
            custom_weights=custom_weights
        )
        
        self.assertEqual(config.get_weight("Momentum"), 2.0)
        self.assertEqual(config.get_weight("Value"), 1.0)
        self.assertEqual(config.get_weight("Growth"), 1.0)  # Default weight
    
    def test_param_retrieval(self):
        """Test parameter retrieval"""
        advanced_params = {
            "Momentum": {
                "short_period": 30,
                "long_period": 150
            }
        }
        
        config = StrategyConfig(
            strategies=["Momentum", "Value"],
            tickers=["AAPL", "MSFT"],
            advanced_params=advanced_params
        )
        
        self.assertEqual(config.get_param("test_param", "default"), "default")
        
        # For real implementation, we'd need to extract the strategy-specific params

class TestStrategyFactory(unittest.TestCase):
    """Test StrategyFactory functionality"""
    
    def test_create_strategy(self):
        """Test strategy creation"""
        # Test creating a single strategy
        strategy = StrategyFactory.create_strategy("Momentum", weight=1.5)
        self.assertIsInstance(strategy, MomentumStrategy)
        self.assertEqual(strategy.weight, 1.5)
        
        # Test with parameters
        params = {
            "short_period": 30,
            "long_period": 150
        }
        
        strategy = StrategyFactory.create_strategy("Momentum", weight=1.0, params=params)
        self.assertEqual(strategy.get_param("short_period"), 30)
        self.assertEqual(strategy.get_param("long_period"), 150)
    
    def test_create_strategies(self):
        """Test creating multiple strategies"""
        strategy_names = ["Momentum", "Value", "Growth"]
        weights = {
            "Momentum": 2.0,
            "Value": 1.5
        }
        
        strategies = StrategyFactory.create_strategies(strategy_names, weights)
        
        self.assertEqual(len(strategies), 3)
        self.assertIsInstance(strategies[0], MomentumStrategy)
        self.assertIsInstance(strategies[1], ValueStrategy)
        self.assertIsInstance(strategies[2], GrowthStrategy)
        
        self.assertEqual(strategies[0].weight, 2.0)
        self.assertEqual(strategies[1].weight, 1.5)
        self.assertEqual(strategies[2].weight, 1.0)  # Default weight

class TestMomentumStrategy(unittest.TestCase):
    """Test MomentumStrategy functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create sample price data
        dates = pd.date_range(start='2020-01-01', periods=300, freq='D')
        
        # AAPL with uptrend
        aapl_data = pd.DataFrame({
            'Open': np.linspace(100, 150, 300) + np.random.normal(0, 2, 300),
            'High': np.linspace(105, 155, 300) + np.random.normal(0, 2, 300),
            'Low': np.linspace(95, 145, 300) + np.random.normal(0, 2, 300),
            'Close': np.linspace(100, 150, 300) + np.random.normal(0, 1, 300),
            'Volume': np.random.randint(1000000, 5000000, 300)
        }, index=dates)
        
        # MSFT with downtrend
        msft_data = pd.DataFrame({
            'Open': np.linspace(200, 150, 300) + np.random.normal(0, 2, 300),
            'High': np.linspace(205, 155, 300) + np.random.normal(0, 2, 300),
            'Low': np.linspace(195, 145, 300) + np.random.normal(0, 2, 300),
            'Close': np.linspace(200, 150, 300) + np.random.normal(0, 1, 300),
            'Volume': np.random.randint(1000000, 5000000, 300)
        }, index=dates)
        
        self.price_data = {
            'AAPL': aapl_data,
            'MSFT': msft_data
        }
    
    def test_calculate_score(self):
        """Test momentum score calculation"""
        strategy = MomentumStrategy()
        
        scores = strategy.calculate_score(self.price_data)
        
        self.assertIsInstance(scores, pd.Series)
        self.assertEqual(len(scores), 2)
        self.assertIn('AAPL', scores.index)
        self.assertIn('MSFT', scores.index)
        
        # AAPL should have higher momentum score due to uptrend
        self.assertGreater(scores['AAPL'], scores['MSFT'])

class TestValueStrategy(unittest.TestCase):
    """Test ValueStrategy functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create sample fundamental data
        self.fundamentals = pd.DataFrame({
            'name': ['Apple Inc.', 'Microsoft Corp', 'High PE Stock', 'Low PE Stock'],
            'current_price': [150, 200, 300, 50],
            'market_cap': [2e12, 1.8e12, 5e11, 1e11],
            'pe_ratio': [25, 30, 50, 10],
            'pb_ratio': [15, 12, 8, 1.2],
            'ps_ratio': [7, 8, 10, 2],
            'ev_ebitda': [18, 16, 20, 5],
            'dividend_yield': [0.005, 0.015, 0.001, 0.04]
        }, index=['AAPL', 'MSFT', 'HIGH', 'LOW'])
    
    def test_calculate_score(self):
        """Test value score calculation"""
        strategy = ValueStrategy()
        
        scores = strategy.calculate_score(self.fundamentals)
        
        self.assertIsInstance(scores, pd.Series)
        self.assertEqual(len(scores), 4)
        
        # LOW should have highest value score due to low PE, PB, etc.
        self.assertGreater(scores['LOW'], scores['AAPL'])
        self.assertGreater(scores['LOW'], scores['MSFT'])
        self.assertGreater(scores['LOW'], scores['HIGH'])
        
        # HIGH should have lowest value score
        self.assertLess(scores['HIGH'], scores['AAPL'])
        self.assertLess(scores['HIGH'], scores['MSFT'])

class TestCustomStrategy(unittest.TestCase):
    """Test CustomStrategy functionality"""
    
    def test_custom_strategy_creation(self):
        """Test creating and using a custom strategy"""
        # Define a simple custom scoring function
        def custom_scoring(data: pd.DataFrame) -> pd.Series:
            """Simple scoring based on price to market cap ratio"""
            scores = {}
            for ticker, row in data.iterrows():
                if 'current_price' in row and 'market_cap' in row:
                    # Lower price to market cap ratio is better
                    ratio = row['current_price'] / (row['market_cap'] / 1e9)
                    scores[ticker] = max(0, min(100, 100 - ratio * 10))
                else:
                    scores[ticker] = 0
            return pd.Series(scores)
        
        # Create the custom strategy
        strategy = CustomStrategy(
            name="Price to Market Cap",
            description="Evaluates stocks based on price to market cap ratio",
            metrics=["current_price", "market_cap"],
            scoring_function=custom_scoring
        )
        
        # Test data
        test_data = pd.DataFrame({
            'current_price': [100, 200, 300],
            'market_cap': [1e12, 5e11, 1e11]
        }, index=['AAPL', 'MSFT', 'SMALL'])
        
        scores = strategy.calculate_score(test_data)
        
        self.assertIsInstance(scores, pd.Series)
        self.assertEqual(len(scores), 3)
        
        # AAPL should have best score due to high market cap relative to price
        self.assertGreater(scores['AAPL'], scores['MSFT'])
        self.assertGreater(scores['AAPL'], scores['SMALL'])
        
        # SMALL should have worst score due to low market cap
        self.assertLess(scores['SMALL'], scores['MSFT'])

# Skip data service tests unless in integration test mode
@unittest.skipIf(os.environ.get('RUN_INTEGRATION_TESTS') != 'true', 
                "Skipping integration tests")
class TestDataService(unittest.TestCase):
    """Integration tests for DataService"""
    
    def test_fetch_stock_data(self):
        """Test fetching stock data"""
        data_service = DataService()
        tickers = ["AAPL", "MSFT"]
        
        # Use asyncio to run the async function
        loop = asyncio.get_event_loop()
        price_data = loop.run_until_complete(
            data_service._fetch_stock_data_async(tickers, "1mo")
        )
        
        self.assertIsInstance(price_data, dict)
        self.assertGreaterEqual(len(price_data), 1)  # At least one ticker should return data
        
        for ticker, df in price_data.items():
            self.assertIsInstance(df, pd.DataFrame)
            self.assertIn('Close', df.columns)
            self.assertGreater(len(df), 0)

if __name__ == '__main__':
    unittest.main()
