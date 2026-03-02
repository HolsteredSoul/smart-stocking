"""
SmartStock: Multi-Strategy Stock Screener
Enhanced main Streamlit application with advanced features
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import io
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import plotly.graph_objects as go

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import our custom modules
from services.data_service import DataService
from models.strategy_config import StrategyConfig, ScreeningResult
from utils.visualization import ChartBuilder
from utils.enhanced_ui import EnhancedUIComponents
from utils.data_cache_manager import DataCacheManager
from pages.troubleshooting import troubleshooting_page

# Canonical mapping: strategy display name -> score column name in DataFrames
# This MUST match the column names produced by DataService._run_screening_async()
STRATEGY_SCORE_COLUMNS = {
    'Momentum': 'momentum_score',
    'Value': 'value_score',
    'Growth': 'growth_score',
    'Quality': 'quality_score',
    'Income': 'income_score',
    'Low Volatility': 'volatility_score',
}

# Configure the Streamlit page
st.set_page_config(
    page_title="SmartStock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'selected_tickers' not in st.session_state:
    st.session_state.selected_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
if 'selected_strategies' not in st.session_state:
    st.session_state.selected_strategies = ["Momentum", "Value"]
if 'custom_weights' not in st.session_state:
    st.session_state.custom_weights = {}
if 'strategy_params' not in st.session_state:
    st.session_state.strategy_params = {}
# Backtest removed in MVP
if 'user_preferences' not in st.session_state:
    st.session_state.user_preferences = EnhancedUIComponents.load_user_preferences()
    
# Initialize data cache manager
if 'data_cache_manager' not in st.session_state:
    st.session_state.data_cache_manager = DataCacheManager()

def main():
    """Main application function"""
    
    try:
        # Initialize data service with API keys from preferences
        data_service = initialize_data_service()
        
        # Clean up data service at the end
        import atexit
        atexit.register(cleanup_data_service, data_service)
        
        # Create sidebar navigation
        with st.sidebar:
            st.title("SmartStock 📈")
            
            navigation = st.radio(
                "Navigation",
                ["📊 Screening", "📈 Analysis", "🔍 Comparison", "⚙️ Settings", "🔧 Troubleshooting"]
            )
            st.divider()
            
            # Add Data Cache info
            cache_manager = st.session_state.data_cache_manager
            cache_stats = cache_manager.get_cache_stats()
            
            with st.expander("💾 Data Cache", expanded=False):
                st.info(f"Cache has saved {cache_stats['hits']} API calls")  
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Hit Rate", f"{cache_stats['hit_rate']:.1%}")
                with col2:
                    st.metric("Items Cached", cache_stats['cache_size'])
                    
                if st.button("📊 View Cache Details"):
                    cache_manager.render_cache_stats_ui()
            
            st.divider()
            
            # Load saved strategies
            saved_strategies = load_saved_strategies()
            
            if saved_strategies:
                st.subheader("Saved Strategies")
                strategy_name = st.selectbox(
                    "Load Strategy",
                    options=list(saved_strategies.keys()),
                    index=0
                )
                
                if st.button("Load", key="load_strategy_btn"):
                    if strategy_name in saved_strategies:
                        strategy_config = saved_strategies[strategy_name]
                        load_strategy(strategy_config)
                        st.success(f"Loaded strategy: {strategy_name}")
                        st.rerun()
            
            st.divider()
            
            # Add info and about sections
            with st.expander("About SmartStock"):
                st.markdown("""
                **SmartStock** is a comprehensive stock screening tool that implements multiple investment strategies.
                
                Features:
                - Multiple investment strategies
                - Interactive visualizations
                - CSV/Excel export
                - Stock comparison tools
                
                Version: 1.0 MVP
                """)
        
        # Render the appropriate page based on navigation
        if navigation == "📊 Screening":
            screening_page(data_service)
        elif navigation == "📈 Analysis":
            analysis_page(data_service)
        elif navigation == "🔍 Comparison":
            comparison_page(data_service)
        elif navigation == "⚙️ Settings":
            settings_page()
        elif navigation == "🔧 Troubleshooting":
            troubleshooting_page()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.error("Please try restarting the application")

def cleanup_data_service(data_service):
    """Cleanup the data service and its resources"""
    try:
        # Close any open sessions
        import asyncio
        if hasattr(data_service, 'session') and data_service.session is not None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(data_service.close_session())
            loop.close()
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")

def initialize_data_service() -> DataService:
    """Initialize data service with API keys from preferences"""
    data_service = DataService()
    
    # Set API keys from preferences if available
    preferences = st.session_state.user_preferences
    
    if 'alpha_vantage_key' in preferences and preferences['alpha_vantage_key']:
        data_service.alpha_vantage_key = preferences['alpha_vantage_key']
    
    if 'finnhub_key' in preferences and preferences['finnhub_key']:
        data_service.finnhub_key = preferences['finnhub_key']
        
    if 'fmp_key' in preferences and preferences['fmp_key']:
        data_service.fmp_key = preferences['fmp_key']
        
    if 'polygon_key' in preferences and preferences['polygon_key']:
        data_service.polygon_key = preferences['polygon_key']
    
    return data_service

def load_saved_strategies() -> Dict[str, Dict]:
    """Load saved strategies from file"""
    try:
        strategies_dir = '.streamlit/strategies'
        os.makedirs(strategies_dir, exist_ok=True)
        
        saved_strategies = {}
        
        for file_name in os.listdir(strategies_dir):
            if file_name.endswith('.json'):
                strategy_name = file_name.replace('.json', '')
                file_path = os.path.join(strategies_dir, file_name)
                
                import json
                with open(file_path, 'r') as f:
                    strategy_config = json.load(f)
                    saved_strategies[strategy_name] = strategy_config
        
        return saved_strategies
    except Exception as e:
        st.sidebar.error(f"Error loading strategies: {str(e)}")
        return {}

def save_strategy(name: str, config: Dict) -> bool:
    """Save a strategy configuration to file"""
    try:
        strategies_dir = '.streamlit/strategies'
        os.makedirs(strategies_dir, exist_ok=True)
        
        file_path = os.path.join(strategies_dir, f"{name}.json")
        
        import json
        with open(file_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving strategy: {str(e)}")
        return False

def load_strategy(config: Dict):
    """Load a strategy configuration into session state"""
    if 'strategies' in config:
        st.session_state.selected_strategies = config['strategies']
    
    if 'tickers' in config:
        st.session_state.selected_tickers = config['tickers']
    
    if 'custom_weights' in config:
        st.session_state.custom_weights = config['custom_weights']
    
    if 'strategy_params' in config:
        st.session_state.strategy_params = config['strategy_params']

def screening_page(data_service: DataService):
    """Page for setting up and running stock screening"""
    st.title("SmartStock: Multi-Strategy Stock Screener")
    
    # Add welcome section if enabled in preferences
    if st.session_state.user_preferences.get('show_welcome', True):
        EnhancedUIComponents.show_welcome_section()
    
    # Strategy selection
    st.header("Stock Screening Configuration")
    
    # Define strategies
    strategies = {
        "Momentum": "12-month price momentum and trend analysis",
        "Value": "Low P/E, P/B ratios and undervaluation metrics",
        "Growth": "Revenue and earnings growth acceleration",
        "Quality": "High ROE, stable earnings, strong fundamentals",
        "Income": "High dividend yield and payout sustainability",
        "Low Volatility": "Lower price volatility and risk metrics"
    }
    
    # Use enhanced strategy selector
    selected_strategies, custom_weights, strategy_params = EnhancedUIComponents.show_advanced_strategy_selector(
        strategies,
        selected_strategies=st.session_state.selected_strategies,
        custom_weights=st.session_state.custom_weights,
        strategy_params=st.session_state.strategy_params
    )
    
    # Store selected strategies in session state
    st.session_state.selected_strategies = selected_strategies
    st.session_state.custom_weights = custom_weights
    st.session_state.strategy_params = strategy_params
    
    # Ticker input
    st.subheader("Stock Selection")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        tickers_input = st.text_area(
            "Enter stock tickers (comma-separated)",
            value=", ".join(st.session_state.selected_tickers),
            height=100,
            help="Enter stock symbols separated by commas (e.g., AAPL, MSFT, GOOGL). Due to rate limits, fewer stocks are recommended."
        )
    
    with col2:
        # Add preset ticker lists
        preset_lists = {
            "S&P 500 Sample": ["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "BRK-B", "UNH", "JNJ", "JPM", "XOM"],
            "Tech Leaders": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "ORCL", "CSCO", "INTC", "IBM"],
            "Dividend Kings": ["JNJ", "PG", "KO", "PEP", "WMT", "MCD", "MMM", "CVX", "XOM", "CL"],
            "FAANG": ["META", "AAPL", "AMZN", "NFLX", "GOOGL"],
            "Small Test (5)": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]  # Added smaller test set
        }
        
        selected_preset = st.selectbox("Or choose a preset list:", ["Custom"] + list(preset_lists.keys()))
        
        if selected_preset != "Custom":
            tickers_input = ", ".join(preset_lists[selected_preset])
    
    # Parse tickers
    if tickers_input:
        tickers = [ticker.strip().upper() for ticker in tickers_input.split(",") if ticker.strip()]
        st.session_state.selected_tickers = tickers
        
        # Get max stocks from preferences
        max_stocks = st.session_state.user_preferences.get('max_stocks', 10)
        
        if len(tickers) > max_stocks:
            st.warning(f"⚠️ Warning: Analyzing more than {max_stocks} stocks may trigger rate limits. Consider using fewer tickers.")
        elif len(tickers) > 5:
            st.info("💡 Tip: Analyzing 5 or fewer stocks at a time reduces rate limit issues.")
        elif len(tickers) > 0:
            st.success(f"✅ Selected {len(tickers)} stocks for analysis")
    
    # Advanced settings in expander
    with st.expander("⚙️ Advanced Settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Get default lookback from preferences
            default_lookback_idx = ["1 Month", "3 Months", "6 Months", "1 Year", "2 Years"].index(
                st.session_state.user_preferences.get('default_lookback', "1 Year")
            )
            
            lookback_period = st.selectbox(
                "Analysis lookback period",
                ["1 Month", "3 Months", "6 Months", "1 Year", "2 Years"],
                index=default_lookback_idx,
                help="How far back to look for historical data"
            )
            
            # Get default scoring method from preferences
            default_scoring_idx = ["Rank Aggregation", "Percentile Scoring", "Custom Weights"].index(
                st.session_state.user_preferences.get('default_scoring', "Rank Aggregation")
            )
            
            scoring_method = st.selectbox(
                "Scoring method",
                ["Rank Aggregation", "Percentile Scoring", "Custom Weights"],
                index=default_scoring_idx,
                help="How to combine strategy scores"
            )
        
        with col2:
            # Get default min market cap from preferences
            default_min_cap = st.session_state.user_preferences.get('default_min_market_cap', 1.0)
            
            min_market_cap = st.number_input(
                "Minimum market cap (B)",
                min_value=0.1,
                value=default_min_cap,
                step=0.1,
                help="Filter out small-cap stocks (in billions)"
            ) * 1000  # Convert to millions
            
            exclude_sectors = st.multiselect(
                "Exclude sectors",
                ["Technology", "Healthcare", "Energy", "Financials", "Consumer", "Industrial", "Materials", "Utilities"],
                help="Sectors to exclude from analysis"
            )
    
    # Save strategy section
    with st.expander("💾 Save Current Strategy", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            strategy_name = st.text_input(
                "Strategy Name",
                value="My Strategy",
                help="Give your strategy a name"
            )
        
        with col2:
            if st.button("Save Strategy", key="save_strategy_btn", use_container_width=True):
                if not strategy_name:
                    st.error("Please enter a strategy name")
                elif not selected_strategies:
                    st.error("Please select at least one strategy")
                else:
                    # Create strategy config
                    strategy_config = {
                        'strategies': selected_strategies,
                        'tickers': st.session_state.selected_tickers,
                        'lookback_period': lookback_period,
                        'scoring_method': scoring_method,
                        'min_market_cap': min_market_cap,
                        'exclude_sectors': exclude_sectors,
                        'custom_weights': custom_weights,
                        'strategy_params': strategy_params
                    }
                    
                    # Save the strategy
                    success = save_strategy(strategy_name, strategy_config)
                    
                    if success:
                        st.success(f"Strategy '{strategy_name}' saved successfully!")
    
    # Run analysis button
    if st.session_state.selected_strategies and st.session_state.selected_tickers:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            run_button = st.button("🚀 Run Analysis", key="run_analysis_btn", type="primary", use_container_width=True)
        
        with col2:
            # Add cache control
            cache_status = st.empty()
            cache_manager = st.session_state.data_cache_manager
            api_working = cache_manager.test_yahoo_fetch()
            if api_working:
                cache_status.success("✅ API Ready")
            else:
                cache_status.warning("⚠️ Rate Limited")
        
        if run_button:
            with st.spinner("Analyzing stocks... This may take a moment."):
                try:
                    # Create strategy config
                    config = StrategyConfig(
                        strategies=st.session_state.selected_strategies,
                        tickers=st.session_state.selected_tickers,
                        lookback_period=lookback_period,
                        scoring_method=scoring_method,
                        min_market_cap=min_market_cap,
                        exclude_sectors=exclude_sectors,
                        custom_weights=custom_weights,
                        advanced_params=strategy_params
                    )
                    
                    # Check API status before running
                    cache_manager = st.session_state.data_cache_manager
                    api_status = cache_manager.test_yahoo_fetch()
                    
                    if not api_status:
                        st.warning("⚠️ Yahoo Finance API is currently rate limited. Using cached data where available.")
                        # Extend cache expiry to avoid API calls
                        for key in st.session_state.cache_timestamps:
                            st.session_state.cache_timestamps[key] = time.time() + 60*10  # Add 10 min to current time
                        
                    # Run the analysis
                    results = data_service.run_screening(config)
                    st.session_state.analysis_results = results
                    
                    if len(results) > 0:
                        st.success(f"Analysis complete! Found {len(results)} qualifying stocks.")
                    else:
                        st.warning("No stocks could be analyzed due to rate limits.")
                        st.info("💡 **Troubleshooting Tips:**")
                        st.markdown("""
                        1. Wait 5-10 minutes and try again
                        2. Start with just 1-2 stocks
                        3. Use a VPN to change your IP address
                        4. Try the demo mode below for testing
                        """)
                        
                        # Add demo mode option
                        if st.button("🎮 Try Demo Mode (Simulated Data)", key="demo_mode_btn"):
                            st.session_state.analysis_results = create_demo_data(st.session_state.selected_tickers)
                            st.success("Demo data loaded! Switch to the Analysis tab to view results.")
                    
                    # Add helpful note about data sources
                    available_sources = ["Yahoo Finance (free)"]
                    if data_service.alpha_vantage_key:
                        available_sources.append("Alpha Vantage")
                    if data_service.finnhub_key:
                        available_sources.append("Finnhub")
                    if data_service.fmp_key:
                        available_sources.append("Financial Modeling Prep")
                    if data_service.polygon_key:
                        available_sources.append("Polygon.io")
                        
                    st.info(f"💡 Data sources used: {', '.join(available_sources)}")
                    
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")
                    st.error("Please check your tickers and try again.")
                    
                    # Provide helpful debugging info
                    with st.expander("🔧 Troubleshooting"):
                        st.markdown("""
                        **Common Issues:**
                        1. Invalid ticker symbols
                        2. Network connectivity
                        3. Rate limits (try fewer stocks)
                        
                        **Quick Fix:** Wait 10-15 minutes between analyses or try demo mode.
                        """)
    
    else:
        st.info("Please select at least one strategy and enter some tickers to begin analysis.")

def analysis_page(data_service: DataService):
    """Page for displaying analysis results"""
    st.title("📈 Analysis Results")
    
    if st.session_state.analysis_results is None:
        st.info("No analysis results yet. Please run a screening first in the Screening tab.")
        return
    
    results_df = st.session_state.analysis_results
    
    if results_df.empty:
        st.warning("No analysis results to display. The screening may have failed due to rate limits or no stocks met the criteria.")
        return
    
    if 'composite_score' not in results_df.columns:
        st.error("Analysis results are incomplete. Please try running the screening again.")
        return
    
    # --- Summary metrics row ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Analyzed", len(results_df))
    with col2:
        st.metric("Top Score", f"{results_df['composite_score'].max():.1f}")
    with col3:
        st.metric("Avg Score", f"{results_df['composite_score'].mean():.1f}")
    with col4:
        st.metric("Strategies", len(st.session_state.selected_strategies))
    
    st.divider()
    
    # --- Build a clean display table ---
    # Define user-friendly columns and their display format
    display_columns = {
        'composite_score': 'Score',
        'current_price': 'Price',
        'pe_ratio': 'P/E',
        'pb_ratio': 'P/B',
        'market_cap': 'Mkt Cap',
        'dividend_yield': 'Div Yield',
        'volatility': 'Volatility',
        'sector': 'Sector',
    }
    # Add strategy score columns using canonical mapping
    for strategy in st.session_state.selected_strategies:
        col_name = STRATEGY_SCORE_COLUMNS.get(strategy, f"{strategy.lower()}_score")
        if col_name in results_df.columns:
            display_columns[col_name] = f"{strategy}"
    
    available_display = {k: v for k, v in display_columns.items() if k in results_df.columns}
    
    # --- Filters row ---
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider(
            "Minimum score", 0.0,
            float(results_df['composite_score'].max()),
            0.0, help="Filter stocks by minimum composite score"
        )
    with col2:
        sort_options = list(available_display.values())
        sort_label = st.selectbox("Sort by", sort_options, index=0)
        # Reverse-lookup the actual column name
        sort_col = [k for k, v in available_display.items() if v == sort_label][0]
    with col3:
        sort_order = st.selectbox("Order", ["Descending", "Ascending"])
    
    # Apply filter & sort
    filtered_df = results_df[results_df['composite_score'] >= min_score].copy()
    filtered_df = filtered_df.sort_values(sort_col, ascending=(sort_order == "Ascending"))
    
    if filtered_df.empty:
        st.info("No stocks match the current filter criteria. Try lowering the minimum score.")
        return
    
    # Build formatted display DataFrame
    display_df = pd.DataFrame(index=filtered_df.index)
    display_df.index.name = 'Ticker'
    
    for col_key, col_label in available_display.items():
        if col_key == 'current_price':
            display_df[col_label] = filtered_df[col_key].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")
        elif col_key == 'market_cap':
            display_df[col_label] = filtered_df[col_key].apply(
                lambda x: f"${x/1e9:.1f}B" if x >= 1e9 else (f"${x/1e6:.0f}M" if pd.notna(x) else "N/A")
            )
        elif col_key == 'dividend_yield':
            display_df[col_label] = filtered_df[col_key].apply(
                lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
            )
        elif col_key == 'volatility':
            display_df[col_label] = filtered_df[col_key].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
            )
        elif col_key == 'sector':
            display_df[col_label] = filtered_df[col_key].fillna('N/A')
        elif col_key in ('pe_ratio', 'pb_ratio'):
            display_df[col_label] = filtered_df[col_key].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )
        else:  # Score columns
            display_df[col_label] = filtered_df[col_key].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "—"
            )
    
    st.dataframe(display_df, use_container_width=True, height=min(400, 35 * len(display_df) + 38))
    
    # --- Export row ---
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        csv = filtered_df.to_csv(index=True).encode('utf-8')
        st.download_button(
            "📄 Download CSV", csv,
            file_name=f"smartstock_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv", use_container_width=True
        )
    with export_col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, sheet_name='Results')
        buffer.seek(0)
        st.download_button(
            "📊 Download Excel", buffer,
            file_name=f"smartstock_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.ms-excel", use_container_width=True
        )
    
    st.divider()
    
    # --- Stock detail section ---
    st.subheader("Stock Details")
    selected_stock = st.selectbox(
        "Select a stock to view details",
        filtered_df.index.tolist()
    )
    if selected_stock:
        stock_detail_view(selected_stock, results_df)

def stock_detail_view(ticker: str, results_df: pd.DataFrame):
    """Display detailed view for a single stock"""
    stock_data = results_df.loc[ticker]
    
    # --- Helper to safely format values ---
    def fmt(key, fmt_str, suffix='', scale=1, fallback='N/A'):
        val = stock_data.get(key)
        if pd.isna(val) if isinstance(val, float) else val is None:
            return fallback
        return f"{fmt_str.format(val * scale)}{suffix}"
    
    # --- Stock header ---
    mkt_cap = stock_data.get('market_cap', 0)
    mkt_cap_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap >= 1e9 else f"${mkt_cap/1e6:.0f}M"
    
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        st.markdown(f"### {ticker} — {stock_data.get('name', 'N/A')}")
    with col2:
        st.metric("Price", f"${stock_data.get('current_price', 0):.2f}")
    with col3:
        st.metric("Mkt Cap", mkt_cap_str)
    with col4:
        st.metric("Score", f"{stock_data.get('composite_score', 0):.1f}")
    
    # --- Tabs ---
    tabs = st.tabs(["Overview", "Strategy Scores", "Financials", "Export"])
    
    # ---- Overview tab ----
    with tabs[0]:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("P/E Ratio", fmt('pe_ratio', '{:.1f}'))
            st.metric("P/B Ratio", fmt('pb_ratio', '{:.2f}'))
        with col2:
            st.metric("EV/EBITDA", fmt('ev_ebitda', '{:.1f}'))
            st.metric("P/S Ratio", fmt('ps_ratio', '{:.2f}'))
        with col3:
            st.metric("Div Yield", fmt('dividend_yield', '{:.2f}', '%', 100))
            st.metric("Beta", fmt('beta', '{:.2f}'))
        with col4:
            st.metric("Volatility", fmt('volatility', '{:.1f}', '%', 100))
            st.metric("Sector", stock_data.get('sector', 'N/A'))
    
    # ---- Strategy Scores tab ----
    with tabs[1]:
        strategy_scores = {}
        for strategy in st.session_state.selected_strategies:
            score_col = STRATEGY_SCORE_COLUMNS.get(strategy, f"{strategy.lower()}_score")
            if score_col in stock_data:
                strategy_scores[strategy] = stock_data[score_col]
        
        if not strategy_scores:
            st.info("No strategy scores available.")
        else:
            # Always show bar chart
            fig = go.Figure(go.Bar(
                x=list(strategy_scores.keys()),
                y=list(strategy_scores.values()),
                text=[f"{s:.1f}" for s in strategy_scores.values()],
                textposition='auto',
                marker_color=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3'][:len(strategy_scores)]
            ))
            fig.update_layout(yaxis_range=[0, 100], height=350, margin=dict(t=30, b=30))
            st.plotly_chart(fig, use_container_width=True)
            
            # Radar chart only if 3+ strategies
            if len(strategy_scores) >= 3:
                cats = list(strategy_scores.keys())
                vals = list(strategy_scores.values())
                cats.append(cats[0])
                vals.append(vals[0])
                fig = go.Figure(go.Scatterpolar(r=vals, theta=cats, fill='toself', name=ticker))
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    showlegend=False, height=400, margin=dict(t=30, b=30)
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # ---- Financials tab ----
    with tabs[2]:
        # Single clean grid instead of nested expanders
        all_metrics = [
            ("Valuation", [
                ("P/E Ratio", fmt('pe_ratio', '{:.1f}')),
                ("P/B Ratio", fmt('pb_ratio', '{:.2f}')),
                ("P/S Ratio", fmt('ps_ratio', '{:.2f}')),
                ("EV/EBITDA", fmt('ev_ebitda', '{:.1f}')),
            ]),
            ("Growth", [
                ("Revenue Growth", fmt('revenue_growth', '{:.1f}', '%', 100)),
                ("EPS Growth", fmt('eps_growth', '{:.1f}', '%', 100)),
                ("Profit Margin", fmt('profit_margin', '{:.1f}', '%', 100)),
                ("Revenue", f"${stock_data.get('revenue', 0)/1e9:.1f}B" if stock_data.get('revenue', 0) >= 1e9 else "N/A"),
            ]),
            ("Quality", [
                ("ROE", fmt('roe', '{:.1f}', '%', 100)),
                ("Debt/Equity", fmt('debt_to_equity', '{:.2f}')),
                ("Current Ratio", fmt('current_ratio', '{:.2f}')),
            ]),
            ("Income", [
                ("Div Yield", fmt('dividend_yield', '{:.2f}', '%', 100)),
                ("Payout Ratio", fmt('payout_ratio', '{:.1f}', '%', 100)),
            ]),
        ]
        
        for section_name, metrics in all_metrics:
            st.caption(section_name)
            cols = st.columns(4)
            for i, (label, value) in enumerate(metrics):
                with cols[i % 4]:
                    st.metric(label, value)
    
    # ---- Export tab ----
    with tabs[3]:
        if st.button("📊 Generate Excel Report", key="stock_excel_btn", use_container_width=True):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                overview_data = pd.DataFrame(stock_data).reset_index()
                overview_data.columns = ['Metric', 'Value']
                overview_data.to_excel(writer, sheet_name='Overview', index=False)
                
                strategy_data = []
                for strategy in st.session_state.selected_strategies:
                    sc = STRATEGY_SCORE_COLUMNS.get(strategy, f"{strategy.lower()}_score")
                    if sc in stock_data:
                        strategy_data.append({'Strategy': strategy, 'Score': stock_data[sc]})
                if strategy_data:
                    pd.DataFrame(strategy_data).to_excel(writer, sheet_name='Strategy Scores', index=False)
            
            buffer.seek(0)
            st.download_button(
                "📥 Download Excel Report", buffer,
                file_name=f"{ticker}_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel", use_container_width=True
            )
# Backtesting function removed in MVP

def comparison_page(data_service: DataService):
    """Page for comparing multiple stocks side by side"""
    if st.session_state.analysis_results is not None and not st.session_state.analysis_results.empty:
        EnhancedUIComponents.show_comparison_interface(st.session_state.analysis_results)
    else:
        st.title("🔍 Stock Comparison")
        st.info("No analysis results yet. Please run a screening first in the Screening tab.")

def settings_page():
    """Page for user settings and preferences"""
    # Load current preferences
    current_preferences = st.session_state.user_preferences
    
    # Show settings interface
    new_preferences = EnhancedUIComponents.show_settings_page(current_preferences)
    
    # Update session state if preferences changed
    if new_preferences and new_preferences != current_preferences:
        st.session_state.user_preferences = new_preferences

def create_demo_data(tickers: List[str]) -> pd.DataFrame:
    """Create demo data for testing purposes"""
    # Reuse the existing implementation
    import numpy as np
    import pandas as pd
    
    # Create realistic demo data
    demo_data = []
    
    stock_names = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corporation',
        'GOOGL': 'Alphabet Inc.',
        'AMZN': 'Amazon.com Inc.',
        'TSLA': 'Tesla Inc.',
        'META': 'Meta Platforms Inc.',
        'NFLX': 'Netflix Inc.',
        'NVDA': 'NVIDIA Corporation'
    }
    
    for ticker in tickers:
        # Generate realistic random data
        np.random.seed(hash(ticker) % 1000)  # Consistent data for same ticker
        
        data = {
            'ticker': ticker,
            'name': stock_names.get(ticker, f'{ticker} Corporation'),
            'current_price': np.random.uniform(50, 500),
            'market_cap': np.random.uniform(100e9, 3000e9),
            'pe_ratio': np.random.uniform(10, 50),
            'pb_ratio': np.random.uniform(1, 10),
            'ps_ratio': np.random.uniform(1, 20),
            'ev_ebitda': np.random.uniform(8, 30),
            'profit_margin': np.random.uniform(0.05, 0.35),
            'roe': np.random.uniform(0.10, 0.30),
            'debt_to_equity': np.random.uniform(0.1, 2.0),
            'current_ratio': np.random.uniform(1.0, 4.0),
            'revenue': np.random.uniform(10e9, 500e9),
            'revenue_growth': np.random.uniform(-0.05, 0.25),
            'eps_growth': np.random.uniform(-0.10, 0.30),
            'dividend_yield': np.random.uniform(0, 0.05),
            'payout_ratio': np.random.uniform(0.1, 0.8),
            'beta': np.random.uniform(0.5, 2.0),
            'sector': np.random.choice(['Technology', 'Healthcare', 'Consumer', 'Financial']),
            'industry': np.random.choice(['Software', 'Hardware', 'Retail', 'Services']),
            
            # Strategy scores
            'momentum_score': np.random.uniform(30, 90),
            'value_score': np.random.uniform(20, 80),
            'growth_score': np.random.uniform(40, 95),
            'quality_score': np.random.uniform(35, 85),
            'income_score': np.random.uniform(10, 60),
            'volatility_score': np.random.uniform(25, 75),
            
            # Composite score (weighted average)
            'volatility': np.random.uniform(0.15, 0.45)
        }
        
        # Calculate composite score using all 6 strategy score columns
        scores = [data['momentum_score'], data['value_score'], data['growth_score'],
                  data['quality_score'], data['income_score'], data['volatility_score']]
        data['composite_score'] = np.mean(scores)
        
        demo_data.append(data)
    
    df = pd.DataFrame(demo_data)
    df.set_index('ticker', inplace=True)
    
    return df

if __name__ == "__main__":
    main()





