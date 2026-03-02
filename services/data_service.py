"""
Data Service Module for SmartStock
Handles data fetching from various financial APIs
"""

import asyncio
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None  # type: ignore[assignment]

# Streamlit is optional — the scoring / data-fetching logic works without it.
# When running under pytest or as a plain script the stub below is used so that
# @st.cache_data decorators and UI helpers become harmless no-ops.
try:
    import streamlit as st
except ImportError:  # pragma: no cover
    class _StubSecrets:  # noqa: N801
        def get(self, key, default=""):
            return default

    class _StubSt:  # noqa: N801
        secrets = _StubSecrets()

        @staticmethod
        def cache_data(ttl=None, **kwargs):
            def _decorator(fn):
                return fn
            return _decorator

        @staticmethod
        def empty():
            class _P:
                def text(self, msg): pass
                def markdown(self, msg): pass
            return _P()

        @staticmethod
        def progress(val):
            class _Bar:
                def progress(self, val, text=""): pass
            return _Bar()

        @staticmethod
        def info(msg): pass

        @staticmethod
        def warning(msg): pass

        @staticmethod
        def error(msg): pass

        @staticmethod
        def success(msg): pass

    st = _StubSt()  # type: ignore[assignment]

from models.constants import STRATEGY_SCORE_COLUMNS  # single source of truth

class DataService:
    """Handles all data fetching and processing operations"""
    
    def __init__(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("SmartStock")
        
        # Try to get API keys, but don't fail if they're not available
        try:
            self.alpha_vantage_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
            self.finnhub_key = st.secrets.get("FINNHUB_API_KEY", "")
            self.fmp_key = st.secrets.get("FMP_API_KEY", "")
            self.polygon_key = st.secrets.get("POLYGON_API_KEY", "")
        except Exception:
            # If secrets aren't configured, use empty strings
            self.alpha_vantage_key = ""
            self.finnhub_key = ""
            self.fmp_key = ""
            self.polygon_key = ""
            
        # Initialize HTTP sessions
        self.session = None
        
        # Rate limiting with exponential backoff
        self.last_api_call = {}
        self.call_delay = {
            "yahoo": 1.0,
            "alpha_vantage": 13.0, 
            "finnhub": 1.0, 
            "fmp": 0.5,
            "polygon": 0.3
        }  # seconds between calls
        
        # Data source priorities
        self.data_sources = ["yahoo"]
        if self.alpha_vantage_key:
            self.data_sources.append("alpha_vantage")
        if self.finnhub_key:
            self.data_sources.append("finnhub")
        if self.fmp_key:
            self.data_sources.append("fmp")
        if self.polygon_key:
            self.data_sources.append("polygon")
            
        # Cache for API responses to reduce duplicate calls
        self.response_cache = {}
    
    def _run_sync(self, coro):
        """Execute an async coroutine from synchronous context safely."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        return asyncio.run(coro)

    # ------------------------------------------------------------------
    # Public synchronous helpers used by cache manager / other layers
    # ------------------------------------------------------------------

    def fetch_data_sync(self, ticker: str, data_type: str, period: str = "1y") -> Any:
        """Fetch data synchronously by delegating to async implementations."""
        if data_type in {"price", "intraday", "chart_data", "technical"}:
            data = self._run_sync(self._fetch_stock_data_async([ticker], period))
            return data.get(ticker)
        if data_type in {"fundamental", "financial", "profile", "summary",
                         "institutional", "insider"}:
            fundamentals = self._run_sync(self._get_fundamentals_async([ticker]))
            if fundamentals is None or fundamentals.empty:
                return None
            return fundamentals.loc[ticker] if ticker in fundamentals.index else None
        raise ValueError(f"Unsupported data_type '{data_type}' for fetch_data_sync")

    def fetch_multiple_data_sync(self, tickers: List[str], data_type: str, period: str = "1y") -> Dict[str, Any]:
        """Batch synchronous fetch helper."""
        if data_type in {"price", "intraday", "chart_data", "technical"}:
            return self._run_sync(self._fetch_stock_data_async(tickers, period))
        if data_type in {"fundamental", "financial", "profile", "summary",
                         "institutional", "insider"}:
            fundamentals = self._run_sync(self._get_fundamentals_async(tickers))
            if fundamentals is None or fundamentals.empty:
                return {}
            return fundamentals.to_dict(orient="index")
        raise ValueError(f"Unsupported data_type '{data_type}' for fetch_multiple_data_sync")

    def __del__(self):
        """Cleanup resources when the object is deleted"""
        try:
            # Check if there's an event loop running
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the close_session function to run
                loop.create_task(self.close_session())
            else:
                # If no loop is running, create a new one to close the session
                try:
                    asyncio.run(self.close_session())
                except RuntimeError:
                    # Handle "RuntimeError: There is no current event loop in thread"
                    pass
        except Exception as e:
            # Just log errors during cleanup
            print(f"Error during DataService cleanup: {str(e)}")
    
    async def initialize_session(self):
        """Initialize aiohttp session if not already created"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            
    async def close_session(self):
        """Close aiohttp session if open"""
        if self.session is not None:
            await self.session.close()
            self.session = None
            
    def _get_api_call_delay(self, source: str, attempt: int = 0) -> float:
        """Calculate delay with exponential backoff"""
        base_delay = self.call_delay.get(source, 1.0)
        jitter = random.uniform(0, 0.5)  # Add randomness to avoid thundering herd
        return base_delay * (2 ** attempt) + jitter
        
    async def _make_api_call(self, source: str, url: str, params: Dict = None, headers: Dict = None, 
                            max_retries: int = 3) -> Tuple[bool, Any]:
        """Make API call with rate limiting and exponential backoff"""
        await self.initialize_session()
        
        # Check cache first
        cache_key = f"{url}_{str(params)}"
        if cache_key in self.response_cache:
            return True, self.response_cache[cache_key]
        
        for attempt in range(max_retries):
            # Apply rate limiting
            now = time.time()
            if source in self.last_api_call:
                elapsed = now - self.last_api_call[source]
                delay = self._get_api_call_delay(source, attempt)
                if elapsed < delay:
                    wait_time = delay - elapsed
                    self.logger.debug(f"Rate limiting {source}: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            
            # Make the call
            try:
                self.last_api_call[source] = time.time()
                async with self.session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        # Cache successful response
                        self.response_cache[cache_key] = result
                        return True, result
                    elif response.status == 429:  # Rate limit
                        wait_time = self._get_api_call_delay(source, attempt + 2)  # Longer wait for rate limits
                        self.logger.warning(f"{source} rate limit hit. Waiting {wait_time:.2f}s before retry.")
                        await asyncio.sleep(wait_time)
                    else:
                        self.logger.warning(f"{source} API returned status {response.status}")
                        await asyncio.sleep(self._get_api_call_delay(source, attempt))
            except Exception as e:
                self.logger.warning(f"Error calling {source} API: {str(e)}")
                await asyncio.sleep(self._get_api_call_delay(source, attempt))
                
        return False, None
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def fetch_stock_data(_self, tickers: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Fetch historical data for multiple tickers (session-cached by Streamlit)"""
        return _self._run_sync(_self._fetch_stock_data_async(tickers, period))
        
    async def _fetch_stock_data_async(self, tickers: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Async implementation of fetch_stock_data"""
        data = {}
        
        # Create progress tracking
        progress_placeholder = st.empty()
        progress_placeholder.text(f"Fetching data for {len(tickers)} stocks...")
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def fetch_with_semaphore(ticker):
            async with semaphore:
                return ticker, await self._fetch_single_stock_async(ticker, period)
        
        # Create tasks for all tickers
        tasks = [fetch_with_semaphore(ticker) for ticker in tickers]
        
        # Process results as they complete
        for i, task in enumerate(asyncio.as_completed(tasks)):
            ticker, result = await task
            if result is not None and not result.empty:
                data[ticker] = result
            else:
                st.warning(f"No data retrieved for {ticker}")
                
            # Update progress
            progress = (i + 1) / len(tickers)
            progress_placeholder.text(f"Fetched {i+1}/{len(tickers)} stocks ({progress:.0%})")
        
        # Clear progress indicator
        progress_placeholder.empty()
        
        return data
    
    async def _fetch_single_stock_async(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data for a single stock asynchronously with multiple source fallbacks"""
        # Try each data source in order of priority
        for source in self.data_sources:
            try:
                if source == "yahoo":
                    data = await self._fetch_from_yahoo(ticker, period)
                elif source == "alpha_vantage" and self.alpha_vantage_key:
                    data = await self._fetch_from_alpha_vantage(ticker, period)
                elif source == "finnhub" and self.finnhub_key:
                    data = await self._fetch_from_finnhub(ticker, period)
                elif source == "fmp" and self.fmp_key:
                    data = await self._fetch_from_fmp(ticker, period)
                elif source == "polygon" and self.polygon_key:
                    data = await self._fetch_from_polygon(ticker, period)
                else:
                    continue
                    
                if data is not None and not data.empty:
                    self.logger.info(f"Successfully fetched {ticker} data from {source}")
                    return data
            except Exception as e:
                self.logger.warning(f"Error fetching {ticker} from {source}: {str(e)}")
                continue
                
        # If all sources failed, return empty DataFrame
        self.logger.warning(f"All data sources failed for {ticker}")
        return pd.DataFrame()
        
    async def _fetch_from_yahoo(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data from Yahoo Finance"""
        # Need to use ThreadPoolExecutor since yfinance is not async
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            try:
                # Apply rate limiting
                await asyncio.sleep(self._get_api_call_delay("yahoo"))
                
                def _fetch():
                    try:
                        stock = yf.Ticker(ticker)
                        # Add User-Agent header to reduce likelihood of rate limiting
                        stock.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
                        
                        # First try to get history
                        for attempt in range(3):
                            try:
                                hist = stock.history(period=period)
                                if hist.empty and attempt < 2:
                                    time.sleep(2 * (attempt + 1))  # Exponential backoff
                                    continue
                                break
                            except Exception as e:
                                if "Too Many Requests" in str(e) or "Rate limit" in str(e):
                                    wait_time = 5 * (attempt + 1)
                                    self.logger.warning(f"Rate limited during history fetch for {ticker}. Waiting {wait_time}s")
                                    time.sleep(wait_time)
                                    continue
                                raise
                        
                        if hist.empty:
                            self.logger.warning(f"Empty history for {ticker} after retries")
                            return pd.DataFrame()
                            
                        # Then get info with separate retries
                        for info_attempt in range(3):
                            try:
                                info = stock.info
                                if info and len(info) > 1:
                                    hist['market_cap'] = info.get('marketCap', np.nan)
                                    hist['pe_ratio'] = info.get('trailingPE', np.nan)
                                    hist['dividend_yield'] = info.get('dividendYield', 0)
                                    hist['beta'] = info.get('beta', np.nan)
                                break
                            except Exception as e:
                                self.logger.warning(f"Error getting info for {ticker} (attempt {info_attempt+1}): {str(e)}")
                                if info_attempt < 2:
                                    time.sleep(3 * (info_attempt + 1))
                        
                        return hist
                        
                    except Exception as e:
                        if "Too Many Requests" in str(e) or "Rate limit" in str(e):
                            self.logger.error(f"Rate limited for {ticker}: {str(e)}")
                            raise Exception(f"Rate limited: {str(e)}")
                        self.logger.error(f"Failed to fetch {ticker}: {str(e)}")
                        return pd.DataFrame()
                    
                return await loop.run_in_executor(pool, _fetch)
            except Exception as e:
                self.logger.warning(f"Error in Yahoo Finance fetch for {ticker}: {str(e)}")
                return pd.DataFrame()
            
    async def _fetch_from_alpha_vantage(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data from Alpha Vantage API"""
        try:
            # Convert period to Alpha Vantage format
            output_size = "full" if period in ["1y", "2y", "5y", "10y", "max"] else "compact"
            
            # Get daily time series
            base_url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": output_size,
                "apikey": self.alpha_vantage_key
            }
            
            success, data = await self._make_api_call("alpha_vantage", base_url, params)
            
            if not success or "Time Series (Daily)" not in data:
                return pd.DataFrame()
                
            # Parse the response
            time_series = data["Time Series (Daily)"]
            df = pd.DataFrame.from_dict(time_series, orient="index")
            
            # Rename columns
            df = df.rename(columns={
                "1. open": "Open",
                "2. high": "High",
                "3. low": "Low",
                "4. close": "Close",
                "5. volume": "Volume"
            })
            
            # Convert index to datetime and data to numeric
            df.index = pd.to_datetime(df.index)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
                
            # Add overview data if available
            try:
                overview_params = {
                    "function": "OVERVIEW",
                    "symbol": ticker,
                    "apikey": self.alpha_vantage_key
                }
                
                success, overview = await self._make_api_call("alpha_vantage", base_url, overview_params)
                
                if success and overview:
                    df['market_cap'] = float(overview.get('MarketCapitalization', np.nan))
                    df['pe_ratio'] = float(overview.get('PERatio', np.nan))
                    df['dividend_yield'] = float(overview.get('DividendYield', 0))
                    df['beta'] = float(overview.get('Beta', np.nan))
            except Exception as e:
                self.logger.warning(f"Error getting Alpha Vantage overview for {ticker}: {str(e)}")
                
            # Limit to the requested period
            if period == "1mo":
                df = df.iloc[:30]
            elif period == "3mo":
                df = df.iloc[:90]
            elif period == "6mo":
                df = df.iloc[:180]
            elif period == "1y":
                df = df.iloc[:252]
                
            return df
            
        except Exception as e:
            self.logger.warning(f"Error in Alpha Vantage fetch for {ticker}: {str(e)}")
            return pd.DataFrame()
            
    async def _fetch_from_finnhub(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data from Finnhub API"""
        try:
            # Convert period to timestamps
            end_date = datetime.now()
            
            if period == "1mo":
                start_date = end_date - timedelta(days=30)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "6mo":
                start_date = end_date - timedelta(days=180)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            elif period == "2y":
                start_date = end_date - timedelta(days=730)
            else:
                start_date = end_date - timedelta(days=365)  # Default to 1 year
                
            # Convert to UNIX timestamps
            from_timestamp = int(start_date.timestamp())
            to_timestamp = int(end_date.timestamp())
            
            # Set up request
            base_url = "https://finnhub.io/api/v1/stock/candle"
            params = {
                "symbol": ticker,
                "resolution": "D",  # Daily
                "from": from_timestamp,
                "to": to_timestamp,
                "token": self.finnhub_key
            }
            
            success, data = await self._make_api_call("finnhub", base_url, params)
            
            if not success or data.get('s') != 'ok':
                return pd.DataFrame()
                
            # Create DataFrame
            df = pd.DataFrame({
                'Open': data['o'],
                'High': data['h'],
                'Low': data['l'],
                'Close': data['c'],
                'Volume': data['v']
            }, index=pd.to_datetime(data['t'], unit='s'))
            
            # Get company profile for additional info
            profile_url = "https://finnhub.io/api/v1/stock/profile2"
            profile_params = {
                "symbol": ticker,
                "token": self.finnhub_key
            }
            
            success, profile = await self._make_api_call("finnhub", profile_url, profile_params)
            
            if success and profile:
                df['market_cap'] = profile.get('marketCapitalization', np.nan) * 1e6  # Convert from millions
                df['beta'] = profile.get('beta', np.nan)
                
            # Get basic financials for additional ratios
            metrics_url = "https://finnhub.io/api/v1/stock/metric"
            metrics_params = {
                "symbol": ticker,
                "metric": "all",
                "token": self.finnhub_key
            }
            
            success, metrics = await self._make_api_call("finnhub", metrics_url, metrics_params)
            
            if success and metrics and 'metric' in metrics:
                metrics_data = metrics['metric']
                df['pe_ratio'] = metrics_data.get('peBasicExclExtraTTM', np.nan)
                df['dividend_yield'] = metrics_data.get('dividendYieldIndicatedAnnual', 0) / 100  # Convert from percentage
                
            return df
            
        except Exception as e:
            self.logger.warning(f"Error in Finnhub fetch for {ticker}: {str(e)}")
            return pd.DataFrame()
            
    async def _fetch_from_fmp(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data from Financial Modeling Prep API"""
        try:
            # Map period to API parameter
            if period == "1mo":
                time_delta = "1month"
            elif period == "3mo":
                time_delta = "3month"
            elif period == "6mo":
                time_delta = "6month"
            elif period == "1y":
                time_delta = "1year"
            elif period == "2y":
                time_delta = "2year"
            else:
                time_delta = "1year"  # Default
                
            # Get historical data
            base_url = "https://financialmodelingprep.com/api/v3/historical-price-full"
            params = {
                "symbol": ticker,
                "timeseries": time_delta,
                "apikey": self.fmp_key
            }
            
            success, data = await self._make_api_call("fmp", base_url, params)
            
            if not success or 'historical' not in data:
                return pd.DataFrame()
                
            # Parse historical data
            historical = data['historical']
            df = pd.DataFrame(historical)
            
            # Format DataFrame
            df = df.rename(columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
                "date": "Date"
            })
            
            # Set index and sort
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
            df = df.sort_index()
            
            # Get company profile
            profile_url = "https://financialmodelingprep.com/api/v3/profile"
            profile_params = {
                "symbol": ticker,
                "apikey": self.fmp_key
            }
            
            success, profiles = await self._make_api_call("fmp", profile_url, profile_params)
            
            if success and profiles and len(profiles) > 0:
                profile = profiles[0]
                df['market_cap'] = profile.get('mktCap', np.nan)
                df['beta'] = profile.get('beta', np.nan)
                df['pe_ratio'] = profile.get('pe', np.nan)
                df['dividend_yield'] = profile.get('lastDiv', 0) / profile.get('price', 1) if profile.get('price', 0) > 0 else 0
                
            return df
            
        except Exception as e:
            self.logger.warning(f"Error in FMP fetch for {ticker}: {str(e)}")
            return pd.DataFrame()
            
    async def _fetch_from_polygon(self, ticker: str, period: str) -> pd.DataFrame:
        """Fetch data from Polygon.io API"""
        try:
            # Calculate date range
            end_date = datetime.now()
            
            if period == "1mo":
                start_date = end_date - timedelta(days=30)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "6mo":
                start_date = end_date - timedelta(days=180)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            elif period == "2y":
                start_date = end_date - timedelta(days=730)
            else:
                start_date = end_date - timedelta(days=365)  # Default to 1 year
                
            # Format dates for API
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")
            
            # Get aggregates (OHLC) data
            base_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
            params = {
                "apiKey": self.polygon_key,
                "sort": "asc"
            }
            
            success, data = await self._make_api_call("polygon", base_url, params)
            
            if not success or 'results' not in data:
                return pd.DataFrame()
                
            # Parse response
            results = data['results']
            df = pd.DataFrame(results)
            
            # Rename columns to standard format
            df = df.rename(columns={
                "o": "Open",
                "h": "High",
                "l": "Low",
                "c": "Close",
                "v": "Volume",
                "t": "timestamp"
            })
            
            # Convert timestamp to datetime (milliseconds to seconds)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            # Get ticker details
            details_url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
            details_params = {
                "apiKey": self.polygon_key
            }
            
            success, details = await self._make_api_call("polygon", details_url, details_params)
            
            if success and 'results' in details:
                ticker_details = details['results']
                df['market_cap'] = ticker_details.get('market_cap', np.nan)
                
                # Get financials for ratios
                financials_url = f"https://api.polygon.io/v2/reference/financials/{ticker}"
                financials_params = {
                    "apiKey": self.polygon_key,
                    "limit": 1
                }
                
                success, financials = await self._make_api_call("polygon", financials_url, financials_params)
                
                if success and 'results' in financials and len(financials['results']) > 0:
                    financial_data = financials['results'][0]
                    df['pe_ratio'] = financial_data.get('peRatio', np.nan)
                    df['dividend_yield'] = financial_data.get('dividendYield', 0)
                    
            return df
            
        except Exception as e:
            self.logger.warning(f"Error in Polygon fetch for {ticker}: {str(e)}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=3600)
    def get_fundamentals(_self, tickers: List[str]) -> pd.DataFrame:
        """Get fundamental data for multiple tickers using the async implementation"""
        return _self._run_sync(_self._get_fundamentals_async(tickers))
        
    async def _get_fundamentals_async(self, tickers: List[str]) -> pd.DataFrame:
        """Get fundamental data for multiple tickers"""
        fundamentals = []
        
        # Add progress indicator for user feedback
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        st.info("💡 Note: We're fetching data in parallel with rate limiting. This may take a moment...")
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
        
        async def fetch_fundamentals_for_ticker(ticker, index):
            """Fetch fundamentals for a single ticker with semaphore"""
            async with semaphore:
                status_text.text(f"Fetching data for {ticker}... ({index+1}/{len(tickers)})")
                
                try:
                    # Try multiple data sources in order
                    for source in self.data_sources:
                        fund_data = None
                        
                        if source == "yahoo":
                            fund_data = await self._get_yahoo_fundamentals(ticker)
                        elif source == "alpha_vantage" and self.alpha_vantage_key:
                            fund_data = await self._get_alpha_vantage_fundamentals(ticker)
                        elif source == "finnhub" and self.finnhub_key:
                            fund_data = await self._get_finnhub_fundamentals(ticker)
                        elif source == "fmp" and self.fmp_key:
                            fund_data = await self._get_fmp_fundamentals(ticker)
                        elif source == "polygon" and self.polygon_key:
                            fund_data = await self._get_polygon_fundamentals(ticker)
                        else:
                            continue
                            
                        if fund_data:  # If we got valid data
                            status_text.text(f"✓ Got data for {ticker} from {source}")
                            return fund_data
                    
                    # If all sources failed, return basic data
                    self.logger.warning(f"All sources failed for {ticker} fundamentals")
                    return {
                        'ticker': ticker,
                        'name': ticker,
                        'current_price': 0,
                        'market_cap': 0,
                        'pe_ratio': np.nan,
                        'pb_ratio': np.nan,
                        'ps_ratio': np.nan,
                        'ev_ebitda': np.nan,
                        'profit_margin': np.nan,
                        'roe': np.nan,
                        'debt_to_equity': np.nan,
                        'current_ratio': np.nan,
                        'revenue': 0,
                        'revenue_growth': np.nan,
                        'eps_growth': np.nan,
                        'dividend_yield': 0,
                        'payout_ratio': np.nan,
                        'beta': np.nan,
                        'sector': 'Unknown',
                        'industry': 'Unknown',
                        'dividend_consistent': False,
                        'dividend_growing': False,
                        'pio_cfo_positive': False,
                        'pio_roa_improving': False,
                        'pio_low_accruals': False,
                        'pio_leverage_falling': False,
                        'pio_gross_margin_improving': False,
                        'pio_asset_turnover_improving': False,
                    }
                    
                except Exception as e:
                    self.logger.error(f"Error fetching fundamentals for {ticker}: {str(e)}")
                    return {
                        'ticker': ticker,
                        'name': ticker,
                        'current_price': 0,
                    }
        
        # Create and run tasks for all tickers
        tasks = [fetch_fundamentals_for_ticker(ticker, i) for i, ticker in enumerate(tickers)]
        results = await asyncio.gather(*tasks)
        
        # Process results
        for i, result in enumerate(results):
            if result:  # If we got valid data
                fundamentals.append(result)
                
            # Update progress
            progress_bar.progress((i + 1) / len(tickers))
            
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Create DataFrame even if some stocks failed
        if fundamentals:
            df = pd.DataFrame(fundamentals)
            # Only set ticker as index if it exists
            if 'ticker' in df.columns:
                df = df.set_index('ticker')
            return df
        else:
            # Return empty DataFrame with expected columns if all requests failed
            columns = ['name', 'market_cap', 'pe_ratio', 'pb_ratio', 'ps_ratio', 'ev_ebitda', 
                      'profit_margin', 'roe', 'debt_to_equity', 'current_ratio', 'revenue', 
                      'revenue_growth', 'eps_growth', 'dividend_yield', 'payout_ratio', 'beta', 
                      'sector', 'industry', 'current_price']
            return pd.DataFrame(columns=columns)
            
    async def _get_yahoo_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Yahoo Finance"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            try:
                # Apply rate limiting
                await asyncio.sleep(self._get_api_call_delay("yahoo"))
                
                def _fetch():
                    stock = yf.Ticker(ticker)
                    
                    # Try to get basic info first
                    hist = stock.history(period="1d")
                    if hist.empty:
                        return None
                        
                    current_price = hist['Close'].iloc[-1] if not hist.empty else 0
                    
                    # Try to get fundamental info with retry
                    for attempt in range(3):
                        try:
                            time.sleep(1 + attempt)  # Increasing delay
                            info = stock.info
                            
                            if not info or len(info) <= 1:
                                raise Exception("Empty info received")
                                
                            # --- Piotroski signals 4-9 (require 2-year financials) ---
                            # Signal 4: CFO > 0
                            # Signal 5: ROA improving YoY
                            # Signal 6: Accruals (CFO/assets > net_income/assets)
                            # Signal 7: Long-term leverage decreasing YoY
                            # Signal 8: Gross margin improving YoY
                            # Signal 9: Asset turnover improving YoY
                            pio_cfo_positive = False
                            pio_roa_improving = False
                            pio_low_accruals = False
                            pio_leverage_falling = False
                            pio_gross_margin_improving = False
                            pio_asset_turnover_improving = False
                            try:
                                fin = stock.financials   # columns = most-recent .. oldest
                                cf  = stock.cashflow
                                bs  = stock.balance_sheet
                                if (fin is not None and not fin.empty and
                                        cf is not None and not cf.empty and
                                        bs is not None and not bs.empty and
                                        fin.shape[1] >= 2 and cf.shape[1] >= 2):
                                    # Helper: safe get from df by row label
                                    def _row(df, *labels):
                                        for lbl in labels:
                                            if lbl in df.index:
                                                vals = df.loc[lbl]
                                                return float(vals.iloc[0]), float(vals.iloc[1])
                                        return None, None

                                    cfo_curr, cfo_prev = _row(cf,
                                        'Operating Cash Flow', 'Total Cash From Operating Activities')
                                    net_curr, net_prev = _row(fin,
                                        'Net Income', 'Net Income Common Stockholders')
                                    rev_curr, rev_prev = _row(fin,
                                        'Total Revenue')
                                    gross_curr, gross_prev = _row(fin,
                                        'Gross Profit')
                                    ta_curr, ta_prev = _row(bs,
                                        'Total Assets')
                                    ltd_curr, ltd_prev = _row(bs,
                                        'Long Term Debt')

                                    if cfo_curr is not None:
                                        pio_cfo_positive = cfo_curr > 0

                                    if (ta_curr and ta_prev and ta_curr > 0 and ta_prev > 0
                                            and net_curr is not None and net_prev is not None):
                                        roa_curr = net_curr / ta_curr
                                        roa_prev = net_prev / ta_prev
                                        pio_roa_improving = roa_curr > roa_prev

                                        if cfo_curr is not None:
                                            pio_low_accruals = (cfo_curr / ta_curr) > (net_curr / ta_curr)

                                        if ltd_curr is not None and ltd_prev is not None:
                                            lev_curr = ltd_curr / ta_curr
                                            lev_prev = ltd_prev / ta_prev
                                            pio_leverage_falling = lev_curr < lev_prev

                                    if (rev_curr and rev_prev and gross_curr is not None
                                            and gross_prev is not None and rev_curr > 0 and rev_prev > 0):
                                        gm_curr = gross_curr / rev_curr
                                        gm_prev = gross_prev / rev_prev
                                        pio_gross_margin_improving = gm_curr > gm_prev

                                        if ta_curr and ta_curr > 0 and ta_prev and ta_prev > 0:
                                            at_curr = rev_curr / ta_curr
                                            at_prev = rev_prev / ta_prev
                                            pio_asset_turnover_improving = at_curr > at_prev

                            except Exception:
                                pass

                            # Dividend history signals (actual payment track record)
                            dividend_consistent = False
                            dividend_growing = False
                            try:
                                divs = stock.dividends
                                if not divs.empty:
                                    tz = divs.index.tz
                                    now = pd.Timestamp.now(tz=tz)
                                    two_yrs_ago = now - pd.DateOffset(years=2)
                                    one_yr_ago = now - pd.DateOffset(years=1)
                                    recent = divs[divs.index >= two_yrs_ago]
                                    dividend_consistent = len(recent) >= 4
                                    curr_yr = divs[divs.index >= one_yr_ago]
                                    prev_yr = divs[(divs.index >= two_yrs_ago) & (divs.index < one_yr_ago)]
                                    if not curr_yr.empty and not prev_yr.empty:
                                        dividend_growing = float(curr_yr.sum()) >= float(prev_yr.sum())
                            except Exception:
                                pass

                            # Extract fundamental data
                            return {
                                'ticker': ticker,
                                'name': info.get('longName', info.get('shortName', ticker)),
                                'market_cap': info.get('marketCap', 0),
                                'pe_ratio': info.get('trailingPE', np.nan),
                                'pb_ratio': info.get('priceToBook', np.nan),
                                'ps_ratio': info.get('priceToSalesTrailing12Months', np.nan),
                                'ev_ebitda': info.get('enterpriseToEbitda', np.nan),
                                'profit_margin': info.get('profitMargins', np.nan),
                                'roe': info.get('returnOnEquity', np.nan),
                                'debt_to_equity': info.get('debtToEquity', np.nan),
                                'current_ratio': info.get('currentRatio', np.nan),
                                'revenue': info.get('totalRevenue', 0),
                                'revenue_growth': info.get('revenueGrowth', np.nan),
                                'eps_growth': info.get('earningsGrowth', np.nan),
                                'dividend_yield': info.get('dividendYield', 0),
                                'payout_ratio': info.get('payoutRatio', np.nan),
                                'beta': info.get('beta', np.nan),
                                'sector': info.get('sector', 'Unknown'),
                                'industry': info.get('industry', 'Unknown'),
                                'current_price': info.get('currentPrice', current_price),
                                'dividend_consistent': dividend_consistent,
                                'dividend_growing': dividend_growing,
                                # Piotroski signals 4-9
                                'pio_cfo_positive': pio_cfo_positive,
                                'pio_roa_improving': pio_roa_improving,
                                'pio_low_accruals': pio_low_accruals,
                                'pio_leverage_falling': pio_leverage_falling,
                                'pio_gross_margin_improving': pio_gross_margin_improving,
                                'pio_asset_turnover_improving': pio_asset_turnover_improving,
                            }
                        except Exception as e:
                            if attempt == 2:  # Last attempt
                                return {
                                    'ticker': ticker,
                                    'name': ticker,
                                    'current_price': current_price,
                                    'market_cap': 0,
                                }
                    
                return await loop.run_in_executor(pool, _fetch)
            except Exception as e:
                self.logger.warning(f"Error in Yahoo fundamentals for {ticker}: {str(e)}")
                return None
                
    async def _get_alpha_vantage_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Alpha Vantage"""
        try:
            # Get company overview
            base_url = "https://www.alphavantage.co/query"
            params = {
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": self.alpha_vantage_key
            }
            
            success, data = await self._make_api_call("alpha_vantage", base_url, params)
            
            if not success or not data:
                return None
                
            # Get current price
            quote_params = {
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": self.alpha_vantage_key
            }
            
            success, quote = await self._make_api_call("alpha_vantage", base_url, quote_params)
            current_price = float(quote.get("Global Quote", {}).get("05. price", 0)) if success and quote else 0
            
            # Extract fundamental data
            return {
                'ticker': ticker,
                'name': data.get('Name', ticker),
                'market_cap': float(data.get('MarketCapitalization', 0)),
                'pe_ratio': float(data.get('PERatio', np.nan)),
                'pb_ratio': float(data.get('PriceToBookRatio', np.nan)),
                'ps_ratio': float(data.get('PriceToSalesRatioTTM', np.nan)),
                'ev_ebitda': float(data.get('EVToEBITDA', np.nan)),
                'profit_margin': float(data.get('ProfitMargin', np.nan)),
                'roe': float(data.get('ReturnOnEquityTTM', np.nan)),
                'debt_to_equity': float(data.get('DebtToEquity', np.nan)),
                'current_ratio': float(data.get('CurrentRatio', np.nan)),
                'revenue': float(data.get('RevenueTTM', 0)),
                'revenue_growth': float(data.get('QuarterlyRevenueGrowthYOY', np.nan)),
                'eps_growth': float(data.get('QuarterlyEarningsGrowthYOY', np.nan)),
                'dividend_yield': float(data.get('DividendYield', 0)),
                'payout_ratio': float(data.get('PayoutRatio', np.nan)),
                'beta': float(data.get('Beta', np.nan)),
                'sector': data.get('Sector', 'Unknown'),
                'industry': data.get('Industry', 'Unknown'),
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.warning(f"Error in Alpha Vantage fundamentals for {ticker}: {str(e)}")
            return None
            
    async def _get_finnhub_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Finnhub"""
        try:
            # Get company profile
            profile_url = "https://finnhub.io/api/v1/stock/profile2"
            profile_params = {
                "symbol": ticker,
                "token": self.finnhub_key
            }
            
            success, profile = await self._make_api_call("finnhub", profile_url, profile_params)
            
            if not success or not profile:
                return None
                
            # Get quote for current price
            quote_url = "https://finnhub.io/api/v1/quote"
            quote_params = {
                "symbol": ticker,
                "token": self.finnhub_key
            }
            
            success, quote = await self._make_api_call("finnhub", quote_url, quote_params)
            current_price = quote.get('c', 0) if success and quote else 0
            
            # Get metrics
            metrics_url = "https://finnhub.io/api/v1/stock/metric"
            metrics_params = {
                "symbol": ticker,
                "metric": "all",
                "token": self.finnhub_key
            }
            
            success, metrics = await self._make_api_call("finnhub", metrics_url, metrics_params)
            metrics_data = metrics.get('metric', {}) if success and metrics else {}
            
            # Extract data
            return {
                'ticker': ticker,
                'name': profile.get('name', ticker),
                'market_cap': profile.get('marketCapitalization', 0) * 1e6,  # Convert from millions
                'pe_ratio': metrics_data.get('peBasicExclExtraTTM', np.nan),
                'pb_ratio': metrics_data.get('pbAnnual', np.nan),
                'ps_ratio': metrics_data.get('psTTM', np.nan),
                'ev_ebitda': metrics_data.get('enterpriseValueOverEBITDATTM', np.nan),
                'profit_margin': metrics_data.get('netProfitMarginTTM', np.nan),
                'roe': metrics_data.get('roeTTM', np.nan),
                'debt_to_equity': metrics_data.get('totalDebtToEquityQuarterly', np.nan),
                'current_ratio': metrics_data.get('currentRatioQuarterly', np.nan),
                'revenue': metrics_data.get('revenueTTM', 0),
                'revenue_growth': metrics_data.get('revenueGrowthQuarterlyYoy', np.nan),
                'eps_growth': metrics_data.get('epsGrowthQuarterlyYoy', np.nan),
                'dividend_yield': metrics_data.get('dividendYieldIndicatedAnnual', 0) / 100,  # Convert from percentage
                'payout_ratio': metrics_data.get('payoutRatioTTM', np.nan),
                'beta': profile.get('beta', np.nan),
                'sector': profile.get('finnhubIndustry', 'Unknown'),  # Finnhub uses different terminology
                'industry': profile.get('finnhubIndustry', 'Unknown'),
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.warning(f"Error in Finnhub fundamentals for {ticker}: {str(e)}")
            return None
            
    async def _get_fmp_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Financial Modeling Prep"""
        try:
            # Get company profile
            profile_url = "https://financialmodelingprep.com/api/v3/profile"
            profile_params = {
                "symbol": ticker,
                "apikey": self.fmp_key
            }
            
            success, profiles = await self._make_api_call("fmp", profile_url, profile_params)
            
            if not success or not profiles or len(profiles) == 0:
                return None
                
            profile = profiles[0]
            
            # Get key metrics
            metrics_url = "https://financialmodelingprep.com/api/v3/key-metrics-ttm"
            metrics_params = {
                "symbol": ticker,
                "apikey": self.fmp_key
            }
            
            success, metrics = await self._make_api_call("fmp", metrics_url, metrics_params)
            metrics_data = metrics[0] if success and metrics and len(metrics) > 0 else {}
            
            # Get financial growth
            growth_url = "https://financialmodelingprep.com/api/v3/financial-growth"
            growth_params = {
                "symbol": ticker,
                "limit": 1,
                "apikey": self.fmp_key
            }
            
            success, growth = await self._make_api_call("fmp", growth_url, growth_params)
            growth_data = growth[0] if success and growth and len(growth) > 0 else {}
            
            # Extract data
            return {
                'ticker': ticker,
                'name': profile.get('companyName', ticker),
                'market_cap': profile.get('mktCap', 0),
                'pe_ratio': profile.get('pe', np.nan),
                'pb_ratio': metrics_data.get('pbRatioTTM', np.nan),
                'ps_ratio': metrics_data.get('priceToSalesRatioTTM', np.nan),
                'ev_ebitda': metrics_data.get('enterpriseValueOverEBITDATTM', np.nan),
                'profit_margin': metrics_data.get('netProfitMarginTTM', np.nan),
                'roe': metrics_data.get('roeTTM', np.nan),
                'debt_to_equity': metrics_data.get('debtToEquityTTM', np.nan),
                'current_ratio': metrics_data.get('currentRatioTTM', np.nan),
                'revenue': metrics_data.get('revenueTTM', 0),
                'revenue_growth': growth_data.get('revenueGrowth', np.nan),
                'eps_growth': growth_data.get('epsgrowth', np.nan),
                'dividend_yield': profile.get('lastDiv', 0) / profile.get('price', 1) if profile.get('price', 0) > 0 else 0,
                'payout_ratio': metrics_data.get('payoutRatioTTM', np.nan),
                'beta': profile.get('beta', np.nan),
                'sector': profile.get('sector', 'Unknown'),
                'industry': profile.get('industry', 'Unknown'),
                'current_price': profile.get('price', 0)
            }
            
        except Exception as e:
            self.logger.warning(f"Error in FMP fundamentals for {ticker}: {str(e)}")
            return None
            
    async def _get_polygon_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Polygon.io"""
        try:
            # Get ticker details
            details_url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
            details_params = {
                "apiKey": self.polygon_key
            }
            
            success, details = await self._make_api_call("polygon", details_url, details_params)
            
            if not success or 'results' not in details:
                return None
                
            ticker_data = details['results']
            
            # Get current price
            quote_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
            quote_params = {
                "apiKey": self.polygon_key
            }
            
            success, quote = await self._make_api_call("polygon", quote_url, quote_params)
            current_price = quote.get('ticker', {}).get('lastQuote', {}).get('p', 0) if success and quote else 0
            
            # Get financials
            financials_url = f"https://api.polygon.io/v2/reference/financials/{ticker}"
            financials_params = {
                "apiKey": self.polygon_key,
                "limit": 1
            }
            
            success, financials = await self._make_api_call("polygon", financials_url, financials_params)
            financial_data = financials.get('results', [{}])[0] if success and financials and 'results' in financials else {}
            
            # Extract data
            return {
                'ticker': ticker,
                'name': ticker_data.get('name', ticker),
                'market_cap': ticker_data.get('market_cap', 0),
                'pe_ratio': financial_data.get('ratios', {}).get('peRatio', np.nan),
                'pb_ratio': financial_data.get('ratios', {}).get('pbRatio', np.nan),
                'ps_ratio': financial_data.get('ratios', {}).get('priceToSalesRatio', np.nan),
                'ev_ebitda': financial_data.get('ratios', {}).get('evToEbitda', np.nan),
                'profit_margin': financial_data.get('ratios', {}).get('profitMargin', np.nan),
                'roe': financial_data.get('ratios', {}).get('roe', np.nan),
                'debt_to_equity': financial_data.get('ratios', {}).get('debtToEquity', np.nan),
                'current_ratio': financial_data.get('ratios', {}).get('currentRatio', np.nan),
                'revenue': financial_data.get('revenue', 0),
                'revenue_growth': financial_data.get('revenueDelta', np.nan),
                'eps_growth': financial_data.get('epsDelta', np.nan),
                'dividend_yield': financial_data.get('dividendYield', 0),
                'payout_ratio': financial_data.get('payoutRatio', np.nan),
                'beta': ticker_data.get('beta', np.nan),
                'sector': ticker_data.get('sic_description', 'Unknown'),
                'industry': ticker_data.get('sic_description', 'Unknown'),
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.warning(f"Error in Polygon fundamentals for {ticker}: {str(e)}")
            return None
    
    def run_screening(self, config) -> pd.DataFrame:
        """Run the complete screening process"""
        return self._run_sync(self._run_screening_async(config))
        
    async def _run_screening_async(self, config) -> pd.DataFrame:
        """Run the complete screening process asynchronously"""
        # Show progress
        st.info("🔄 Starting analysis... This may take a moment due to rate limits.")
        
        # Execute both data fetching operations concurrently
        price_data_task = self._fetch_stock_data_async(config.tickers, config.get_yfinance_period())
        fundamentals_task = self._get_fundamentals_async(config.tickers)
        
        # Wait for both to complete
        price_data, fundamentals = await asyncio.gather(
            price_data_task,
            fundamentals_task
        )
        
        # Check if we got any data
        if fundamentals.empty:
            st.error("Unable to fetch fundamental data for any stocks. This might be due to rate limiting. Please try again in a few minutes with fewer stocks.")
            return pd.DataFrame()
        
        # Apply filters
        fundamentals = self._apply_filters(fundamentals, config)
        
        if fundamentals.empty:
            st.warning("No stocks passed the filtering criteria.")
            return pd.DataFrame()
        
        # Calculate strategy scores
        strategy_scores = {}
        
        if "Momentum" in config.strategies:
            strategy_scores['momentum_score'] = self.calculate_momentum_scores(price_data)
        
        if "Value" in config.strategies:
            strategy_scores['value_score'] = self.calculate_value_scores(fundamentals)
        
        if "Growth" in config.strategies:
            strategy_scores['growth_score'] = self.calculate_growth_scores(fundamentals)
        
        if "Quality" in config.strategies:
            strategy_scores['quality_score'] = self.calculate_quality_scores(fundamentals)
        
        if "Income" in config.strategies:
            strategy_scores['income_score'] = self.calculate_income_scores(fundamentals)
        
        if "Low Volatility" in config.strategies:
            strategy_scores['volatility_score'] = self.calculate_volatility_scores(price_data)
        
        # Combine scores
        results = fundamentals.copy()

        for strategy, scores in strategy_scores.items():
            results[strategy] = scores.reindex(results.index, fill_value=0)

        # Percentile-normalise individual strategy scores within the screened universe
        # so that a score of 80 always means "better than 80% of the stocks analysed".
        # This makes absolute thresholds less important and scores more comparable
        # across different stock universes.
        if len(results) > 1:
            score_cols = [c for c in results.columns if c.endswith('_score')]
            for col in score_cols:
                results[col] = results[col].rank(pct=True) * 100

        # Calculate composite score
        if results.empty:
            st.warning("No stocks available for scoring.")
            return pd.DataFrame()

        results['composite_score'] = self._calculate_composite_score(results, config)
        
        # Add additional metrics
        results['volatility'] = self._calculate_volatility(price_data)
        
        # Sort by composite score
        results = results.sort_values('composite_score', ascending=False)
        
        st.success(f"✅ Analysis complete! Successfully analyzed {len(results)} stocks.")

        return results

    def run_backtest(
        self,
        config,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        cost_pct: float = 0.001,
        min_avg_daily_volume: int = 1_000_000,
    ) -> Dict[str, Any]:
        """
        Run a basic historical backtest.

        Steps:
        1. Fetch price data up to *start_date* and score the universe.
        2. Apply liquidity filter: exclude tickers whose average daily dollar
           volume over the forward period falls below *min_avg_daily_volume*.
        3. Select top-N stocks → equal-weight portfolio.
        4. Deduct *cost_pct* round-trip transaction cost at formation.
        5. Compute portfolio returns, max drawdown, and annualised Sharpe.

        Args:
            cost_pct: Round-trip transaction cost as a fraction (default 0.001 = 0.1%).
            min_avg_daily_volume: Minimum average daily dollar volume to include a stock.
        """
        if yf is None:
            return {"error": "yfinance is not installed; cannot run backtest."}

        try:
            # --- Step 1: Score universe at start_date ---
            hist_config_tickers = config.tickers
            price_hist = {}
            for ticker in hist_config_tickers:
                try:
                    df = yf.download(ticker, end=start_date, period="1y",
                                     auto_adjust=True, progress=False)
                    if not df.empty:
                        price_hist[ticker] = df
                except Exception:
                    pass

            if not price_hist:
                return {"error": "Could not fetch historical data for backtest start date."}

            momentum_s = self.calculate_momentum_scores(price_hist)
            valid_tickers = list(price_hist.keys())
            ranked = momentum_s.reindex(valid_tickers).fillna(0)
            # Select more candidates than needed so the liquidity filter has room
            candidate_tickers = ranked.nlargest(top_n * 2).index.tolist()

            if not candidate_tickers:
                return {"error": "No tickers available after ranking."}

            # --- Step 2 & 3: Fetch forward price + volume data ---
            fwd_data: Dict[str, pd.DataFrame] = {}
            for ticker in candidate_tickers:
                try:
                    df = yf.download(ticker, start=start_date, end=end_date,
                                     auto_adjust=True, progress=False)
                    if not df.empty:
                        fwd_data[ticker] = df
                except Exception:
                    pass

            if not fwd_data:
                return {"error": "Could not fetch forward price data for backtest period."}

            # --- Liquidity filter ---
            liquid_tickers = []
            for ticker, df in fwd_data.items():
                if 'Volume' in df.columns and 'Close' in df.columns:
                    avg_dollar_vol = float((df['Close'] * df['Volume']).mean())
                    if avg_dollar_vol >= min_avg_daily_volume:
                        liquid_tickers.append(ticker)
                else:
                    liquid_tickers.append(ticker)  # no volume data → include anyway

            # Re-rank among liquid candidates and take top_n
            liquid_ranked = ranked.reindex(liquid_tickers).dropna()
            top_tickers = liquid_ranked.nlargest(top_n).index.tolist()

            if not top_tickers:
                return {"error": "No liquid tickers remaining after liquidity filter."}

            fwd_prices = {t: fwd_data[t]['Close'] for t in top_tickers if t in fwd_data}

            # --- Step 4: Equal-weight portfolio with transaction costs ---
            price_df = pd.DataFrame(fwd_prices).dropna(how='all').ffill()
            norm = price_df / price_df.iloc[0]
            portfolio = norm.mean(axis=1)  # equal-weight
            # Deduct one-way cost at entry (sell cost paid at exit is reflected in returns)
            portfolio = portfolio * (1.0 - cost_pct)

            total_return = float((portfolio.iloc[-1] - 1.0) * 100)
            n_years = max((price_df.index[-1] - price_df.index[0]).days / 365.25, 1 / 365)
            ann_return = float((portfolio.iloc[-1] ** (1 / n_years) - 1) * 100)

            # Max drawdown
            rolling_max = portfolio.cummax()
            drawdown = (portfolio - rolling_max) / rolling_max
            max_drawdown = float(drawdown.min() * 100)

            # Annualised Sharpe (vs 4% risk-free)
            daily_ret = portfolio.pct_change().dropna()
            excess = daily_ret - 0.04 / 252
            sharpe = float(excess.mean() / excess.std() * (252 ** 0.5)) if excess.std() > 0 else 0.0

            portfolio_values = pd.DataFrame({
                "Date":            portfolio.index,
                "Portfolio Value": (portfolio * 100).values,
            }).set_index("Date")

            excluded = len(candidate_tickers) - len(liquid_tickers)
            return {
                "top_tickers":           top_tickers,
                "total_return_pct":      round(total_return, 2),
                "ann_return_pct":        round(ann_return, 2),
                "max_drawdown_pct":      round(max_drawdown, 2),
                "sharpe_ratio":          round(sharpe, 2),
                "portfolio_values":      portfolio_values,
                "n_stocks":              len(fwd_prices),
                "cost_pct":              cost_pct,
                "excluded_illiquid":     excluded,
            }

        except Exception as exc:
            self.logger.warning(f"Backtest error: {exc}")
            return {"error": str(exc)}

    def calculate_momentum_scores(self, price_data: Dict[str, pd.DataFrame]) -> pd.Series:
        """Calculate momentum scores for stocks using vectorized operations"""
        scores = {}
        
        # Pre-calculate return periods
        periods = {
            '1m': 21,   # ~1 month of trading days
            '3m': 63,   # ~3 months of trading days
            '6m': 126,  # ~6 months of trading days
            '12m': 252  # ~12 months of trading days
        }
        
        # Weights for different time periods
        weights = {'1m': 0.1, '3m': 0.2, '6m': 0.3, '12m': 0.4}
        
        for ticker, df in price_data.items():
            if df.empty:
                scores[ticker] = 0
                continue
            
            try:
                # Calculate all returns at once with vectorized operations
                returns = {}
                current_price = df['Close'].iloc[-1]
                
                for period_name, days in periods.items():
                    if len(df) >= days:
                        returns[period_name] = ((current_price / df['Close'].iloc[-days]) - 1) * 100
                    else:
                        returns[period_name] = 0
                
                # Moving averages (vectorized)
                sma_50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else current_price
                sma_200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else current_price
                
                # Calculate weighted momentum score
                momentum_score = sum(returns[period] * weights[period] for period in returns)
                
                # Adjust for moving average position
                if current_price > sma_50 > sma_200:
                    momentum_score *= 1.1  # Bonus for bullish trend
                elif current_price < sma_50 < sma_200:
                    momentum_score *= 0.9  # Penalty for bearish trend

                # RSI-14: penalise overbought (>75), reward healthy range (40-70)
                try:
                    delta = df['Close'].diff()
                    gain = delta.clip(lower=0).rolling(14).mean()
                    loss = (-delta.clip(upper=0)).rolling(14).mean()
                    rs = gain / loss.replace(0, float('nan'))
                    rsi = float((100 - 100 / (1 + rs)).iloc[-1]) if len(df) >= 14 else 50.0
                    if 40 <= rsi <= 70:
                        momentum_score *= 1.05   # healthy momentum zone
                    elif rsi > 75:
                        momentum_score *= 0.95   # overbought — risk of pullback
                except Exception:
                    pass

                # Volume confirmation: price up on above-average volume is stronger signal
                try:
                    if 'Volume' in df.columns and len(df) >= 20:
                        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
                        recent_vol = float(df['Volume'].iloc[-5:].mean())
                        price_up = df['Close'].iloc[-1] > df['Close'].iloc[-5]
                        if price_up and avg_vol > 0 and recent_vol > avg_vol * 1.2:
                            momentum_score *= 1.05  # strong volume confirmation
                except Exception:
                    pass

                # 52-week high/low positioning
                try:
                    n_days = min(252, len(df))
                    high_52 = float(df['Close'].iloc[-n_days:].max())
                    low_52  = float(df['Close'].iloc[-n_days:].min())
                    if high_52 > 0:
                        pct_from_high = (current_price - high_52) / high_52
                        if pct_from_high >= -0.05:
                            momentum_score *= 1.05   # within 5% of 52-week high
                    if low_52 > 0:
                        pct_from_low = (current_price - low_52) / low_52
                        if pct_from_low <= 0.20:
                            momentum_score *= 0.92   # within 20% of 52-week low
                except Exception:
                    pass

                # Normalize to 0-100 scale
                scores[ticker] = max(0, min(100, 50 + momentum_score))
                
            except Exception as e:
                self.logger.warning(f"Error calculating momentum for {ticker}: {str(e)}")
                scores[ticker] = 0
        
        return pd.Series(scores)
    
    def calculate_value_scores(self, fundamentals: pd.DataFrame) -> pd.Series:
        """Calculate value scores for stocks, normalised relative to sector peers.

        For each valuation metric (P/E, P/B, EV/EBITDA, P/S) the stock is scored
        against the median of stocks in the same sector within the screened set.
        If fewer than 3 peers share the same sector the absolute thresholds are used
        as a fallback so thinly-represented sectors still receive meaningful scores.
        """
        scores = {}

        # --- Pre-compute sector medians across the screened universe ---
        METRICS = ['pe_ratio', 'pb_ratio', 'ev_ebitda', 'ps_ratio']
        sector_col = 'sector' if 'sector' in fundamentals.columns else None
        sector_medians: Dict[str, Dict[str, float]] = {}

        if sector_col:
            for sector, group in fundamentals.groupby(sector_col):
                medians = {}
                for m in METRICS:
                    if m in group.columns:
                        valid = group[m].dropna()
                        valid = valid[valid > 0]
                        if len(valid) >= 3:
                            medians[m] = float(valid.median())
                sector_medians[sector] = medians

        def _relative_score(value: float, sector_median: float,
                            low_mult: float, mid_mult: float, high_mult: float,
                            pts_max: int, pts_mid: int, pts_low: int) -> int:
            """Score a metric relative to its sector median.

            Ratios < low_mult × median  → pts_max
            Ratios < mid_mult × median  → pts_mid
            Ratios < high_mult × median → pts_low
            Else → 0
            """
            ratio = value / sector_median
            if ratio < low_mult:
                return pts_max
            if ratio < mid_mult:
                return pts_mid
            if ratio < high_mult:
                return pts_low
            return 0

        def _absolute_pe(v: float) -> int:
            if v < 15: return 25
            if v < 20: return 17
            if v < 30: return 8
            return 0

        def _absolute_pb(v: float) -> int:
            if v < 1.5: return 20
            if v < 2.5: return 12
            if v < 3.5: return 4
            return 0

        def _absolute_evebitda(v: float) -> int:
            if v < 10: return 20
            if v < 15: return 12
            if v < 20: return 4
            return 0

        def _absolute_ps(v: float) -> int:
            if v < 2: return 20
            if v < 4: return 12
            if v < 8: return 5
            return 0

        for ticker, row in fundamentals.iterrows():
            try:
                score = 0
                sector = row.get(sector_col, '') if sector_col else ''
                s_med = sector_medians.get(sector, {})

                # P/E ratio — lower is better (max 25 pts)
                pe = row.get('pe_ratio')
                if pd.notna(pe) and pe > 0:
                    med = s_med.get('pe_ratio')
                    if med and med > 0:
                        score += _relative_score(pe, med, 0.7, 0.9, 1.15, 25, 17, 8)
                    else:
                        score += _absolute_pe(pe)

                # P/B ratio (max 20 pts)
                pb = row.get('pb_ratio')
                if pd.notna(pb) and pb > 0:
                    med = s_med.get('pb_ratio')
                    if med and med > 0:
                        score += _relative_score(pb, med, 0.6, 0.85, 1.10, 20, 12, 4)
                    else:
                        score += _absolute_pb(pb)

                # EV/EBITDA (max 20 pts)
                ev = row.get('ev_ebitda')
                if pd.notna(ev) and ev > 0:
                    med = s_med.get('ev_ebitda')
                    if med and med > 0:
                        score += _relative_score(ev, med, 0.7, 0.9, 1.15, 20, 12, 4)
                    else:
                        score += _absolute_evebitda(ev)

                # P/S ratio — lower is better (max 20 pts)
                ps = row.get('ps_ratio') if 'ps_ratio' in row.index else None
                if ps is not None and pd.notna(ps) and ps > 0:
                    med = s_med.get('ps_ratio')
                    if med and med > 0:
                        score += _relative_score(ps, med, 0.7, 0.9, 1.20, 20, 12, 5)
                    else:
                        score += _absolute_ps(ps)

                # Dividend yield bonus (max 15 pts)
                if pd.notna(row.get('dividend_yield')) and row['dividend_yield'] > 0.02:
                    score += 15

                scores[ticker] = min(100, score)

            except Exception:
                scores[ticker] = 0

        return pd.Series(scores)
    
    def calculate_growth_scores(self, fundamentals: pd.DataFrame) -> pd.Series:
        """Calculate growth scores for stocks"""
        scores = {}
        
        for ticker, row in fundamentals.iterrows():
            try:
                score = 0
                
                # Revenue growth scoring
                if pd.notna(row['revenue_growth']):
                    revenue_growth = row['revenue_growth'] * 100
                    if revenue_growth > 15:
                        score += 40
                    elif revenue_growth > 10:
                        score += 30
                    elif revenue_growth > 5:
                        score += 20
                    elif revenue_growth > 0:
                        score += 10
                
                # EPS growth scoring
                if pd.notna(row['eps_growth']):
                    eps_growth = row['eps_growth'] * 100
                    if eps_growth > 20:
                        score += 40
                    elif eps_growth > 15:
                        score += 30
                    elif eps_growth > 10:
                        score += 20
                    elif eps_growth > 0:
                        score += 10
                
                # Profit margin quality
                if pd.notna(row['profit_margin']):
                    profit_margin = row['profit_margin'] * 100
                    if profit_margin > 20:
                        score += 20
                    elif profit_margin > 10:
                        score += 10

                # Earnings quality: operating cash flow should back up reported EPS growth
                try:
                    ocf = row.get('operating_cashflow') if 'operating_cashflow' in row.index else None
                    revenue = row.get('revenue', 0) or 0
                    eps_g = row.get('eps_growth') if 'eps_growth' in row.index else None
                    if ocf is not None and pd.notna(ocf) and revenue > 0 and eps_g is not None and pd.notna(eps_g):
                        ocf_margin = ocf / revenue
                        if ocf_margin > 0.15 and eps_g > 0:
                            score = min(100, score + 10)   # cash flow confirms earnings growth
                        elif ocf_margin < 0.05 and eps_g > 0.15:
                            score = max(0, score - 10)     # earnings not backed by cash
                except Exception:
                    pass

                scores[ticker] = min(100, score)

            except Exception as e:
                scores[ticker] = 0

        return pd.Series(scores)

    def calculate_quality_scores(self, fundamentals: pd.DataFrame) -> pd.Series:
        """Calculate quality scores for stocks"""
        scores = {}
        
        for ticker, row in fundamentals.iterrows():
            try:
                score = 0
                
                # ROE scoring
                if pd.notna(row['roe']):
                    roe = row['roe'] * 100
                    if roe > 20:
                        score += 30
                    elif roe > 15:
                        score += 20
                    elif roe > 10:
                        score += 10
                
                # Debt to equity ratio
                if pd.notna(row['debt_to_equity']):
                    if row['debt_to_equity'] < 0.5:
                        score += 25
                    elif row['debt_to_equity'] < 1.0:
                        score += 15
                    elif row['debt_to_equity'] < 2.0:
                        score += 5
                
                # Current ratio
                if pd.notna(row['current_ratio']):
                    if row['current_ratio'] > 2.0:
                        score += 25
                    elif row['current_ratio'] > 1.5:
                        score += 15
                    elif row['current_ratio'] > 1.0:
                        score += 5
                
                # Profit margins
                if pd.notna(row['profit_margin']):
                    profit_margin = row['profit_margin'] * 100
                    if profit_margin > 15:
                        score += 20
                    elif profit_margin > 10:
                        score += 10
                    elif profit_margin > 5:
                        score += 5

                # Full Piotroski F-Score (9 signals, 3 pts each = max 27 bonus pts)
                # Signals 1-3: derivable from standard fundamentals
                # Signals 4-9: require 2-year income statement + cash flow data
                piotroski = 0
                # Signal 1: positive ROE (profitability proxy for ROA)
                if pd.notna(row.get('roe')) and row['roe'] > 0:
                    piotroski += 1
                # Signal 2: low leverage (D/E < 1)
                if pd.notna(row.get('debt_to_equity')) and row['debt_to_equity'] < 1.0:
                    piotroski += 1
                # Signal 3: adequate liquidity (current ratio > 1)
                if pd.notna(row.get('current_ratio')) and row['current_ratio'] > 1.0:
                    piotroski += 1
                # Signal 4: operating cash flow > 0
                if row.get('pio_cfo_positive', False):
                    piotroski += 1
                # Signal 5: ROA improving year-over-year
                if row.get('pio_roa_improving', False):
                    piotroski += 1
                # Signal 6: low accruals (CFO/assets > net income/assets)
                if row.get('pio_low_accruals', False):
                    piotroski += 1
                # Signal 7: long-term leverage ratio falling
                if row.get('pio_leverage_falling', False):
                    piotroski += 1
                # Signal 8: gross margin improving year-over-year
                if row.get('pio_gross_margin_improving', False):
                    piotroski += 1
                # Signal 9: asset turnover improving year-over-year
                if row.get('pio_asset_turnover_improving', False):
                    piotroski += 1
                score += piotroski * 3  # max 27 bonus pts; capped at 100 below

                scores[ticker] = min(100, score)

            except Exception as e:
                scores[ticker] = 0

        return pd.Series(scores)

    def calculate_income_scores(self, fundamentals: pd.DataFrame) -> pd.Series:
        """Calculate income/dividend scores for stocks"""
        scores = {}
        
        for ticker, row in fundamentals.iterrows():
            try:
                score = 0
                
                # Dividend yield scoring
                if row['dividend_yield'] > 0:
                    yield_pct = row['dividend_yield'] * 100
                    if yield_pct > 4:
                        score += 50
                    elif yield_pct > 3:
                        score += 40
                    elif yield_pct > 2:
                        score += 30
                    elif yield_pct > 1:
                        score += 20
                    elif yield_pct > 0:
                        score += 10
                
                # Payout ratio (sustainability check)
                if pd.notna(row['payout_ratio']):
                    if 0.3 < row['payout_ratio'] < 0.6:  # Sweet spot
                        score += 30
                    elif 0.2 < row['payout_ratio'] < 0.8:  # Acceptable
                        score += 20
                    elif row['payout_ratio'] < 0.2:  # Conservative
                        score += 10
                
                # Dividend history (actual track record — replaces revenue-growth proxy)
                div_consistent = row.get('dividend_consistent', False)
                div_growing = row.get('dividend_growing', False)
                if div_consistent:
                    score += 10  # paid at least quarterly for 2 years
                if div_growing:
                    score += 10  # dividend amount grew year-over-year
                elif not div_consistent and pd.notna(row.get('revenue_growth')) and row['revenue_growth'] > 0.05:
                    # Fallback proxy for stocks without dividend history data
                    score += 5
                
                scores[ticker] = min(100, score)
                
            except Exception as e:
                scores[ticker] = 0
        
        return pd.Series(scores)
    
    def calculate_volatility_scores(self, price_data: Dict[str, pd.DataFrame]) -> pd.Series:
        """Calculate low volatility scores for stocks"""
        scores = {}
        
        for ticker, df in price_data.items():
            if df.empty:
                scores[ticker] = 0
                continue
            
            try:
                # Calculate returns
                returns = df['Close'].pct_change()
                
                # Standard deviation of returns (lower is better)
                volatility = returns.std() * np.sqrt(252)  # Annualized
                
                # Beta (lower is better for low-vol strategy)
                beta = df['beta'].iloc[-1] if 'beta' in df and pd.notna(df['beta'].iloc[-1]) else 1.0
                
                # Assign scores
                vol_score = 0
                if volatility < 0.15:  # Less than 15% annual volatility
                    vol_score += 50
                elif volatility < 0.20:
                    vol_score += 40
                elif volatility < 0.25:
                    vol_score += 30
                elif volatility < 0.30:
                    vol_score += 20
                
                # Beta scoring
                beta_score = 0
                if beta < 0.8:
                    beta_score += 40
                elif beta < 1.0:
                    beta_score += 30
                elif beta < 1.2:
                    beta_score += 20
                
                # Downside deviation (only count negative returns)
                downside_returns = returns[returns < 0]
                downside_deviation = downside_returns.std() * np.sqrt(252)
                
                downside_score = 0
                if downside_deviation < 0.10:
                    downside_score += 10
                elif downside_deviation < 0.15:
                    downside_score += 5
                
                scores[ticker] = min(100, vol_score + beta_score + downside_score)
                
            except Exception as e:
                scores[ticker] = 0
        
        return pd.Series(scores)
    
    def _apply_filters(self, df: pd.DataFrame, config) -> pd.DataFrame:
        """Apply filtering criteria"""
        # Market cap filter
        df = df[df['market_cap'] >= config.min_market_cap * 1e6]
        
        # Sector exclusions
        if config.exclude_sectors:
            df = df[~df['sector'].isin(config.exclude_sectors)]
        
        return df
    
    def _calculate_composite_score(self, df: pd.DataFrame, config) -> pd.Series:
        """Calculate composite score based on selected strategies and weights"""
        
        def _get_score_col(strategy_name: str) -> str:
            """Map strategy display name to its DataFrame column name."""
            return STRATEGY_SCORE_COLUMNS.get(strategy_name, f"{strategy_name.lower()}_score")
        
        if config.scoring_method == "Rank Aggregation":
            ranks = pd.DataFrame()
            
            for strategy in config.strategies:
                score_column = _get_score_col(strategy)
                if score_column in df:
                    ranks[strategy] = df[score_column].rank(ascending=False)
            
            if hasattr(config, 'custom_weights') and config.custom_weights:
                for strategy in config.strategies:
                    if strategy in config.custom_weights:
                        ranks[strategy] = ranks[strategy] * config.custom_weights[strategy]
            
            total_ranks = ranks.sum(axis=1)
            if len(total_ranks) > 1 and total_ranks.max() > total_ranks.min():
                composite = 100 - (total_ranks - total_ranks.min()) / (total_ranks.max() - total_ranks.min()) * 100
            else:
                composite = pd.Series(50, index=total_ranks.index)
            
        elif config.scoring_method == "Percentile Scoring":
            scores = pd.DataFrame()
            
            for strategy in config.strategies:
                score_column = _get_score_col(strategy)
                if score_column in df:
                    scores[strategy] = df[score_column].rank(pct=True) * 100
            
            if hasattr(config, 'custom_weights') and config.custom_weights:
                for strategy in config.strategies:
                    if strategy in config.custom_weights:
                        weight = config.custom_weights.get(strategy, 1.0) 
                        scores[strategy] = scores[strategy] * weight
                        
                total_weight = sum(config.custom_weights.get(strategy, 1.0) for strategy in config.strategies)
                if total_weight > 0:
                    scores = scores / total_weight * len(config.strategies)
                    
            composite = scores.mean(axis=1)
            
        else:  # Custom weights
            scores = pd.DataFrame()
            default_weight = 1.0 / len(config.strategies)
            
            for strategy in config.strategies:
                score_column = _get_score_col(strategy)
                if score_column in df:
                    weight = config.custom_weights.get(strategy, default_weight) if hasattr(config, 'custom_weights') else default_weight
                    scores[strategy] = df[score_column] * weight
            
            composite = scores.sum(axis=1)
            
            if composite.max() > 100:
                composite = composite / composite.max() * 100
        
        return composite
    
    def _calculate_volatility(self, price_data: Dict[str, pd.DataFrame]) -> pd.Series:
        """Calculate annualized volatility for each stock"""
        volatilities = {}
        
        for ticker, df in price_data.items():
            if df.empty:
                volatilities[ticker] = np.nan
                continue
            
            returns = df['Close'].pct_change()
            volatility = returns.std() * np.sqrt(252)  # Annualized
            volatilities[ticker] = volatility
        
        return pd.Series(volatilities)
