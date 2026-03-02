import asyncio
import datetime
import random
import time
from typing import Any, Dict, List, Optional

import streamlit as st
import yfinance as yf

from services.data_service import DataService

# Setup logging lazily to avoid duplicated handlers when Streamlit reruns
_LOGGER = None


def _get_logger():
    """Get module logger with safe initialization."""
    global _LOGGER
    if _LOGGER is None:
        import logging

        _LOGGER = logging.getLogger(__name__)
        if not _LOGGER.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.INFO)
    return _LOGGER

class DataCacheManager:
    """
    Stock data cache manager that stores fetched stock data in Streamlit's session state.
    Prevents duplicate API calls for the same ticker data across different pages and components.
    
    Features:
    - Data type specific expiry times
    - Market-hours awareness for smarter cache expiry
    - Cache statistics tracking
    - Memory management to prevent excessive cache growth
    """
    
    def __init__(self, max_cache_size: int = 200, data_service: Optional[DataService] = None):
        """
        Initialize the data cache manager.
        
        Args:
            max_cache_size: Maximum number of ticker/data_type combinations to keep in cache
        """
        # Initialize cache in session state if not exists
        if 'stock_data_cache' not in st.session_state:
            st.session_state.stock_data_cache = {}
            st.session_state.cache_timestamps = {}
            st.session_state.cache_stats = {
                'hits': 0,
                'misses': 0,
                'refreshes': 0,
                'last_trim': time.time()
            }
        
        self.max_cache_size = max_cache_size
        self.data_service = data_service or DataService()
        
        # Define expiry times (in seconds) for different data types
        self.expiry_seconds = {
            # Price data (shorter expiry)
            'price': 5 * 60,                 # 5 minutes for price data
            'intraday': 2 * 60,              # 2 minutes for intraday data
            'technical': 5 * 60,             # 5 minutes for technical indicators
            'chart_data': 5 * 60,            # 5 minutes for chart data
            
            # Fundamental data (longer expiry)
            'fundamental': 24 * 60 * 60,      # 24 hours (1 day) for fundamental ratios
            'financial': 7 * 24 * 60 * 60,    # 7 days for financial statements
            'profile': 7 * 24 * 60 * 60,      # 7 days for company profiles
            'summary': 24 * 60 * 60,          # 24 hours for company summaries
            'institutional': 7 * 24 * 60 * 60, # 7 days for institutional ownership
            'insider': 7 * 24 * 60 * 60,      # 7 days for insider transactions
            
            # Default fallback
            'default': 60 * 60                # 1 hour default
        }
    
    def get_stock_data(self, 
                       ticker: str, 
                       data_type: str = 'price', 
                       force_refresh: bool = False) -> Any:
        """
        Get stock data from cache or fetch if needed.
        
        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            data_type: Type of data ('price', 'fundamental', etc.)
            force_refresh: Whether to bypass cache and force new fetch
            
        Returns:
            The requested stock data
        """
        # Normalize ticker to uppercase
        ticker = ticker.upper()
        cache_key = f"{ticker}_{data_type}"
        
        # Check if we need to fetch new data
        need_fetch = (
            force_refresh or 
            cache_key not in st.session_state.stock_data_cache or
            self._is_cache_expired(cache_key)
        )
        
        # Periodically trim cache if it's grown too large
        self._maybe_trim_cache()
        
        if need_fetch:
            # Fetch fresh data and update cache
            _get_logger().info(f"Fetching fresh data for {cache_key}")
            try:
                data = self.data_service.fetch_data_sync(ticker, data_type)
            except Exception as exc:
                _get_logger().error(f"Error fetching data for {cache_key}: {exc}")
                if cache_key in st.session_state.stock_data_cache:
                    _get_logger().info(
                        f"Returning expired data for {cache_key} due to fetch error"
                    )
                    st.session_state.cache_timestamps[cache_key] = time.time()
                    st.warning(
                        f"⚠️ Using cached data for {ticker} due to API error: {str(exc)[:100]}..."
                    )
                    return st.session_state.stock_data_cache[cache_key]
                raise

            st.session_state.stock_data_cache[cache_key] = data
            st.session_state.cache_timestamps[cache_key] = time.time()

            if force_refresh:
                st.session_state.cache_stats['refreshes'] += 1
            else:
                st.session_state.cache_stats['misses'] += 1

            return data
        else:
            # Return cached data
            _get_logger().debug(f"Returning cached data for {cache_key}")
            st.session_state.cache_stats['hits'] += 1
            return st.session_state.stock_data_cache[cache_key]
    
    def get_multiple_stock_data(self, 
                               tickers: List[str], 
                               data_type: str = 'price',
                               force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get data for multiple tickers efficiently.
        
        Args:
            tickers: List of stock symbols
            data_type: Type of data to fetch
            force_refresh: Whether to bypass cache
            
        Returns:
            Dictionary mapping tickers to their data
        """
        result = {}
        tickers_to_fetch = []
        
        # First check cache for all tickers
        for ticker in tickers:
            ticker = ticker.upper()
            cache_key = f"{ticker}_{data_type}"
            
            if (not force_refresh and 
                cache_key in st.session_state.stock_data_cache and 
                not self._is_cache_expired(cache_key)):
                # Use cached data
                result[ticker] = st.session_state.stock_data_cache[cache_key]
                st.session_state.cache_stats['hits'] += 1
            else:
                # Need to fetch this ticker
                tickers_to_fetch.append(ticker)
        
        # If we have tickers to fetch, do it efficiently in batch if possible
        if tickers_to_fetch:
            try:
                # Try to fetch multiple tickers at once if the service supports it
                batch_data = self.data_service.fetch_multiple_data_sync(
                    tickers_to_fetch, data_type
                )
                
                # Update cache and result with batch data
                for ticker, data in batch_data.items():
                    cache_key = f"{ticker}_{data_type}"
                    st.session_state.stock_data_cache[cache_key] = data
                    st.session_state.cache_timestamps[cache_key] = time.time()
                    result[ticker] = data
                
                st.session_state.cache_stats['misses'] += len(tickers_to_fetch)
                
            except ValueError:
                # Fall back to individual fetches if batch not supported
                for ticker in tickers_to_fetch:
                    result[ticker] = self.get_stock_data(ticker, data_type, force_refresh)
        
        return result
    
    def clear_cache(self, ticker: Optional[str] = None, data_type: Optional[str] = None) -> None:
        """
        Clear specific ticker or entire cache.
        
        Args:
            ticker: Specific ticker to clear (or None for all tickers)
            data_type: Specific data type to clear (or None for all types)
        """
        keys_to_remove = []
        
        for key in list(st.session_state.stock_data_cache.keys()):
            should_remove = True
            
            if ticker is not None:
                # Only remove if it matches the ticker
                ticker_part = key.split('_')[0]
                should_remove = should_remove and ticker_part.upper() == ticker.upper()
                
            if data_type is not None:
                # Only remove if it matches the data_type
                if '_' in key:
                    data_type_part = key.split('_', 1)[1]
                    should_remove = should_remove and data_type_part == data_type
            
            if should_remove:
                keys_to_remove.append(key)
        
        # Remove the identified keys
        for key in keys_to_remove:
            if key in st.session_state.stock_data_cache:
                del st.session_state.stock_data_cache[key]
            if key in st.session_state.cache_timestamps:
                del st.session_state.cache_timestamps[key]
        
        _get_logger().info(f"Cleared {len(keys_to_remove)} items from cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache usage.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = (st.session_state.cache_stats['hits'] + 
                         st.session_state.cache_stats['misses'] + 
                         st.session_state.cache_stats['refreshes'])
        
        hit_rate = 0
        if total_requests > 0:
            hit_rate = st.session_state.cache_stats['hits'] / total_requests
        
        stats = {
            'cache_size': len(st.session_state.stock_data_cache),
            'unique_tickers': len(set(k.split('_')[0] for k in st.session_state.stock_data_cache.keys())),
            'hit_rate': hit_rate,
            'hits': st.session_state.cache_stats['hits'],
            'misses': st.session_state.cache_stats['misses'],
            'refreshes': st.session_state.cache_stats['refreshes'],
            'total_requests': total_requests
        }
        
        return stats
    
    def _is_cache_expired(self, cache_key: str) -> bool:
        """
        Check if cached data is expired with market awareness.
        
        Args:
            cache_key: The cache key to check
            
        Returns:
            True if cache is expired, False otherwise
        """
        if cache_key not in st.session_state.cache_timestamps:
            return True
            
        timestamp = st.session_state.cache_timestamps[cache_key]
        
        # Extract ticker and data_type from cache_key
        parts = cache_key.split('_', 1)
        ticker = parts[0]
        data_type = parts[1] if len(parts) > 1 else 'default'
        
        # Get appropriate expiry time
        expiry = self.expiry_seconds.get(data_type, self.expiry_seconds['default'])
        
        # For price data, check if market is open
        if data_type in ['price', 'intraday', 'technical', 'chart_data']:
            is_market_open = self._is_market_open(ticker)
            if not is_market_open:
                # Extend cache lifetime when market is closed
                expiry = max(expiry * 4, 60 * 60)  # At least 1 hour when closed
        
        return (time.time() - timestamp) > expiry
    
    def _is_market_open(self, ticker: str) -> bool:
        """
        Check if the market for this ticker is currently open.
        
        Args:
            ticker: Stock symbol to check
            
        Returns:
            True if market is open, False otherwise
        """
        # This is a simplified version - in a real implementation, you should:
        # 1. Use a proper market calendar library
        # 2. Handle different exchanges and timezones
        # 3. Consider holidays
        
        # For now, assume US market hours (9:30 AM - 4:00 PM Eastern, weekdays)
        now = datetime.datetime.now()
        
        # Weekday check (0 = Monday, 4 = Friday)
        is_weekday = 0 <= now.weekday() <= 4
        
        # US Market hours check (simplified)
        is_market_hours = 9 <= now.hour < 16  # 9:30 AM to 4:00 PM Eastern
        
        return is_weekday and is_market_hours
    
    def _fetch_stock_data(self, ticker: str, data_type: str) -> Any:
        """
        Fetch stock data from appropriate API with retry logic.
        
        Args:
            ticker: Stock symbol
            data_type: Type of data to fetch
            
        Returns:
            The fetched data
        """
        return self._fetch_stock_data_with_retry(ticker, data_type)
        
    def _fetch_stock_data_with_retry(self, ticker: str, data_type: str, max_retries=3):
        """
        Fetch stock data with retry logic for rate limiting
        
        Args:
            ticker: Stock symbol
            data_type: Type of data to fetch
            max_retries: Maximum number of retry attempts
            
        Returns:
            The fetched data
        """
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                return self.data_service.fetch_data_sync(ticker, data_type)
            except Exception as exc:
                last_error = exc
                retry_count += 1
                error_message = str(exc).lower()
                if "rate limit" in error_message or "too many requests" in error_message:
                    wait_time = (2 ** retry_count) + random.uniform(0, 1)
                    _get_logger().warning(
                        f"Rate limited for {ticker}. Waiting {wait_time:.2f}s before retry {retry_count}/{max_retries}"
                    )
                    if retry_count == 1:
                        st.warning(
                            f"⏳ API rate limit hit for {ticker}. Waiting between requests. This is normal!"
                        )
                    time.sleep(wait_time)
                else:
                    _get_logger().error(f"Error fetching {data_type} data for {ticker}: {exc}")
                    time.sleep(1)
        _get_logger().error(f"Max retries ({max_retries}) exceeded for {ticker}")
        if last_error:
            raise last_error
        raise RuntimeError(f"Failed to fetch data for {ticker} after {max_retries} attempts")
    
    def _fetch_multiple_stock_data(self, tickers: List[str], data_type: str,
                                   period: str = "1y") -> Dict[str, Any]:
        """
        Fetch price data for multiple tickers in a single yfinance batch request.

        Uses ``yf.download()`` with all tickers at once (much faster and uses
        fewer rate-limit slots than individual calls).  Falls back to sequential
        fetching if the batch call fails.

        Args:
            tickers:   List of stock symbols.
            data_type: Currently supports ``"price"``; falls back to sequential
                       for ``"fundamentals"``.
            period:    yfinance period string (e.g. ``"1y"``).

        Returns:
            Dict mapping each ticker to a DataFrame of OHLCV data.
        """
        if data_type != "price":
            # Fundamentals must still be fetched individually via the Ticker API
            raise NotImplementedError(
                f"Batch fetching is only implemented for 'price' data; "
                f"got '{data_type}'. Use individual Ticker calls for fundamentals."
            )

        try:
            tickers_str = " ".join(tickers)
            raw = yf.download(
                tickers_str,
                period=period,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )

            result: Dict[str, Any] = {}

            if len(tickers) == 1:
                # Single-ticker download returns a flat DataFrame, not grouped
                ticker = tickers[0]
                if not raw.empty:
                    result[ticker] = raw.dropna(how="all")
            else:
                for ticker in tickers:
                    try:
                        df = raw[ticker].dropna(how="all")
                        if not df.empty:
                            result[ticker] = df
                    except KeyError:
                        pass  # Ticker not in batch result — skip silently

            _get_logger().info(
                f"Batch fetch returned data for {len(result)}/{len(tickers)} tickers."
            )
            return result

        except Exception as exc:
            _get_logger().warning(
                f"Batch fetch failed ({exc}); falling back to sequential fetching."
            )
            # Fall back: fetch each ticker individually
            result = {}
            for ticker in tickers:
                try:
                    df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
                    if not df.empty:
                        result[ticker] = df
                except Exception:
                    pass
            return result
    
    def _maybe_trim_cache(self) -> None:
        """
        Trim cache if it has grown too large or too old.
        """
        # Check if we need to trim (do this occasionally, not on every request)
        if (len(st.session_state.cache_timestamps) > self.max_cache_size or
            time.time() - st.session_state.cache_stats.get('last_trim', 0) > 3600):  # 1 hour
            
            self._trim_cache()
            st.session_state.cache_stats['last_trim'] = time.time()
    
    def _trim_cache(self) -> None:
        """
        Trim cache to contain only the most recently used tickers.
        """
        if len(st.session_state.cache_timestamps) <= self.max_cache_size:
            return
            
        # Sort by timestamp (most recent first)
        sorted_keys = sorted(
            st.session_state.cache_timestamps.keys(),
            key=lambda k: st.session_state.cache_timestamps[k],
            reverse=True
        )
        
        # Keep only the most recent max_cache_size keys
        keys_to_keep = set(sorted_keys[:self.max_cache_size])
        
        # Remove old keys
        keys_to_remove = []
        for key in st.session_state.cache_timestamps:
            if key not in keys_to_keep:
                keys_to_remove.append(key)
        
        # Do the actual removal
        for key in keys_to_remove:
            if key in st.session_state.stock_data_cache:
                del st.session_state.stock_data_cache[key]
            if key in st.session_state.cache_timestamps:
                del st.session_state.cache_timestamps[key]
        
        _get_logger().info(f"Trimmed cache: removed {len(keys_to_remove)} old items")
    
    def test_yahoo_fetch(self, ticker="AAPL") -> bool:
        """
        Test if Yahoo Finance API is working or rate limited.
        Returns True if working, False if rate limited.
        """
        try:
            # Create a custom user agent to reduce likelihood of rate limiting
            stock = yf.Ticker(ticker)
            stock.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
            
            # Try to get a small amount of data
            hist = stock.history(period="5d")
            if hist.empty:
                return False
                
            return True
        except Exception as e:
            error_message = str(e).lower()
            if "rate limit" in error_message or "too many requests" in error_message:
                return False
            _get_logger().error(f"Error testing Yahoo Finance: {str(e)}")
            return False
            
    def render_cache_stats_ui(self) -> None:
        """
        Render a small UI component showing cache statistics.
        For debugging and monitoring purposes.
        """
        stats = self.get_cache_stats()
        
        with st.expander("Data Cache Statistics", expanded=False):
            # API Status Section
            st.subheader("API Status")
            
            # Test Yahoo Finance
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("Yahoo Finance API Status:")
            with col2:
                if st.button("Test"):
                    with st.spinner("Testing Yahoo Finance..."):
                        if self.test_yahoo_fetch():
                            st.success("✅ Working")
                        else:
                            st.error("❌ Rate Limited")
                            st.warning("Using cached data until rate limit resets.")
            
            # Cache Statistics
            st.subheader("Cache Statistics")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Cache Size", f"{stats['cache_size']} items")
                st.metric("Unique Tickers", stats['unique_tickers'])
            
            with col2:
                st.metric("Hit Rate", f"{stats['hit_rate']:.1%}")
                st.metric("API Calls Saved", stats['hits'])
            
            st.write("---")
            st.write("Cache Contents:")
            
            # Show the most recently used items
            recent_items = sorted(
                st.session_state.cache_timestamps.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Show top 10
            
            for key, timestamp in recent_items:
                parts = key.split('_', 1)
                ticker = parts[0]
                data_type = parts[1] if len(parts) > 1 else 'unknown'
                
                age_seconds = time.time() - timestamp
                if age_seconds < 60:
                    age_str = f"{age_seconds:.0f}s ago"
                elif age_seconds < 3600:
                    age_str = f"{age_seconds/60:.0f}m ago"
                else:
                    age_str = f"{age_seconds/3600:.1f}h ago"
                
                st.text(f"{ticker}: {data_type} (cached {age_str})")
            
            st.write("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Clear All Cache"):
                    self.clear_cache()
                    st.success("Cache cleared!")
                    st.rerun()
            
            with col2:
                if st.button("Extend Cache Expiry"):
                    # Extend all cache expiry times by updating timestamps
                    for key in st.session_state.cache_timestamps:
                        st.session_state.cache_timestamps[key] = time.time()
                    st.success("Cache expiry extended for all items!")
                    st.rerun()
                    
            with col3:
                if st.button("Rate Limited Mode"):
                    # Make all cache entries very fresh to avoid API calls
                    for key in st.session_state.cache_timestamps:
                        # Add some random jitter to avoid all expiring at once
                        st.session_state.cache_timestamps[key] = time.time() + random.uniform(0, 60)
                    st.success("Enabled rate-limit protection mode!")
                    st.info("App will use cached data for the next hour.")
                    st.rerun()
