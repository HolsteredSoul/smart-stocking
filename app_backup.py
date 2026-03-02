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
from models.strategy_config import StrategyConfig, Strategy, StrategyFactory, BacktestResult
from utils.visualization import ChartBuilder
from utils.enhanced_ui import EnhancedUIComponents
from utils.pdf_export import PDFGenerator
from utils.backtest import BacktestEngine, PortfolioOptimizer
from utils.data_cache_manager import DataCacheManager
from pages.troubleshooting import troubleshooting_page

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
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
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
                ["📊 Screening", "📈 Analysis", "🔍 Comparison", "📉 Backtesting", "⚙️ Settings", "🔧 Troubleshooting"]
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
                        st.experimental_rerun()
            
            st.divider()
            
            # Add info and about sections
            with st.expander("About SmartStock"):
                st.markdown("""
                **SmartStock** is a comprehensive stock screening tool that implements multiple investment strategies.
                
                Features:
                - Multiple investment strategies
                - Interactive visualizations
                - Backtesting capabilities
                - PDF report generation
                
                Version: 2.0.0
                """)
        
        # Render the appropriate page based on navigation
        if navigation == "📊 Screening":
            screening_page(data_service)
        elif navigation == "📈 Analysis":
            analysis_page(data_service)
        elif navigation == "🔍 Comparison":
            comparison_page(data_service)
        elif navigation == "📉 Backtesting":
            backtesting_page(data_service)
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
    st.title("Analysis Results")
    
    if st.session_state.analysis_results is None:
        st.info("No analysis results yet. Please run a screening first in the Screening tab.")
        return
    
    results_df = st.session_state.analysis_results
    
    # Check if DataFrame is empty
    if results_df.empty:
        st.warning("No analysis results to display. The screening may have failed due to rate limits or no stocks met the criteria.")
        st.info("Try running the analysis again with fewer stocks, or wait a few minutes before retrying.")
        return
    
    # Check if required columns exist
    if 'composite_score' not in results_df.columns:
        st.error("Analysis results are incomplete. Please try running the screening again.")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Stocks Analyzed", len(results_df))
    
    with col2:
        top_score = results_df['composite_score'].max()
        st.metric("Top Composite Score", f"{top_score:.2f}")
    
    with col3:
        avg_score = results_df['composite_score'].mean()
        st.metric("Average Score", f"{avg_score:.2f}")
    
    with col4:
        strategies_used = len(st.session_state.selected_strategies)
        st.metric("Strategies Applied", strategies_used)
    
    # Display results table
    st.subheader("Detailed Results")
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_score = st.slider(
            "Minimum composite score",
            0.0, 
            float(results_df['composite_score'].max()) if len(results_df) > 0 else 100.0, 
            0.0,
            help="Filter stocks by minimum score"
        )
    
    with col2:
        # Only show columns that exist in the DataFrame
        available_columns = [col for col in results_df.columns if col not in ['name']]
        default_sort = 'composite_score' if 'composite_score' in available_columns else available_columns[0]
        
        sort_by = st.selectbox(
            "Sort by",
            available_columns,
            index=available_columns.index(default_sort) if default_sort in available_columns else 0
        )
    
    with col3:
        sort_order = st.selectbox("Order", ["Descending", "Ascending"])
    
    # Apply filters and sorting
    filtered_df = results_df[results_df['composite_score'] >= min_score]
    
    # Sort
    ascending = sort_order == "Ascending"
    filtered_df = filtered_df.sort_values(sort_by, ascending=ascending)
    
    # Display
    if len(filtered_df) > 0:
        st.dataframe(
            filtered_df.style.highlight_max(subset=['composite_score'], color='lightgreen')
                           .highlight_min(subset=['volatility'] if 'volatility' in filtered_df.columns else [], color='lightblue')
                           .format(precision=2),
            use_container_width=True
        )
        
        # Export options
        st.subheader("Export Options")
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            # CSV Export
            csv = filtered_df.to_csv(index=True).encode('utf-8')
            st.download_button(
                "📄 Download as CSV",
                csv,
                file_name=f"smartstock_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with export_col2:
            # Excel Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                filtered_df.to_excel(writer, sheet_name='Results')
                # Could add additional sheets with metadata
            
            buffer.seek(0)
            
            st.download_button(
                "📊 Download as Excel",
                buffer,
                file_name=f"smartstock_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        
        with export_col3:
            # PDF Report
            if st.button("📑 Generate PDF Report", key="analysis_pdf_btn", use_container_width=True):
                with st.spinner("Generating PDF report..."):
                    try:
                        # Create PDF generator
                        pdf_generator = PDFGenerator()
                        
                        # Create config dict
                        config = {
                            'strategies': st.session_state.selected_strategies,
                            'scoring_method': 'Custom Weights' if st.session_state.custom_weights else 'Rank Aggregation',
                            'lookback_period': '1 Year',  # Default
                            'min_market_cap': 1000,  # Default in millions
                            'exclude_sectors': []
                        }
                        
                        # Generate PDF
                        pdf_buffer = pdf_generator.generate_report(
                            filtered_df,
                            config,
                            include_charts=True,
                            include_details=True
                        )
                        
                        # Add download button
                        st.download_button(
                            "📥 Download PDF Report",
                            pdf_buffer,
                            file_name=f"smartstock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
        
        # Individual stock details
        st.subheader("Stock Details")
        
        selected_stock = st.selectbox(
            "Select a stock to view details",
            filtered_df.index.tolist()
        )
        
        if selected_stock:
            stock_detail_view(selected_stock, results_df)
    else:
        st.info("No stocks match the current filter criteria. Try adjusting the minimum score.")

def stock_detail_view(ticker: str, results_df: pd.DataFrame):
    """Display detailed view for a single stock"""
    stock_data = results_df.loc[ticker]
    
    # Stock header
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(f"### {ticker} - {stock_data.get('name', 'N/A')}")
    
    with col2:
        st.metric("Current Price", f"${stock_data.get('current_price', 0):.2f}")
    
    with col3:
        st.metric("Market Cap", f"${stock_data.get('market_cap', 0)/1e9:.1f}B" if stock_data.get('market_cap', 0) >= 1e9 
                 else f"${stock_data.get('market_cap', 0)/1e6:.1f}M")
    
    # Create tabs for different aspects
    tabs = st.tabs(["Overview", "Strategy Scores", "Financial Metrics", "Export"])
    
    # Overview tab
    with tabs[0]:
        col1, col2 = st.columns(2)
        
        with col1:
            key_metrics = [
                ("Composite Score", f"{stock_data.get('composite_score', 0):.1f}"),
                ("P/E Ratio", f"{stock_data.get('pe_ratio', 0):.1f}" if pd.notna(stock_data.get('pe_ratio')) else "N/A"),
                ("P/B Ratio", f"{stock_data.get('pb_ratio', 0):.2f}" if pd.notna(stock_data.get('pb_ratio')) else "N/A"),
                ("EV/EBITDA", f"{stock_data.get('ev_ebitda', 0):.1f}" if pd.notna(stock_data.get('ev_ebitda')) else "N/A")
            ]
            
            for label, value in key_metrics:
                st.metric(label, value)
        
        with col2:
            more_metrics = [
                ("Dividend Yield", f"{stock_data.get('dividend_yield', 0)*100:.2f}%" if pd.notna(stock_data.get('dividend_yield')) else "N/A"),
                ("Beta", f"{stock_data.get('beta', 0):.2f}" if pd.notna(stock_data.get('beta')) else "N/A"),
                ("Volatility", f"{stock_data.get('volatility', 0)*100:.1f}%" if pd.notna(stock_data.get('volatility')) else "N/A"),
                ("Sector", stock_data.get('sector', 'N/A'))
            ]
            
            for label, value in more_metrics:
                st.metric(label, value)
    
    # Strategy scores tab
    with tabs[1]:
        strategy_scores = {}
        
        for strategy in st.session_state.selected_strategies:
            score_column = f"{strategy.lower()}_score"
            if score_column in stock_data:
                strategy_scores[strategy] = stock_data[score_column]
        
        if strategy_scores:
            # Create bar chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=list(strategy_scores.keys()),
                y=list(strategy_scores.values()),
                text=[f"{score:.1f}" for score in strategy_scores.values()],
                textposition='auto',
                marker_color='lightblue'
            ))
            
            fig.update_layout(
                title="Strategy Scores",
                xaxis_title="Strategy",
                yaxis_title="Score",
                yaxis_range=[0, 100],
                showlegend=False,
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show radar chart
            categories = list(strategy_scores.keys())
            values = list(strategy_scores.values())
            
            # Close the loop for a complete polygon
            categories.append(categories[0])
            values.append(values[0])
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name=ticker
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )
                ),
                showlegend=False,
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Financial metrics tab
    with tabs[2]:
        # Group metrics by category
        valuation_metrics = [
            ("P/E Ratio", f"{stock_data.get('pe_ratio', 0):.1f}" if pd.notna(stock_data.get('pe_ratio')) else "N/A"),
            ("P/B Ratio", f"{stock_data.get('pb_ratio', 0):.2f}" if pd.notna(stock_data.get('pb_ratio')) else "N/A"),
            ("P/S Ratio", f"{stock_data.get('ps_ratio', 0):.2f}" if pd.notna(stock_data.get('ps_ratio')) else "N/A"),
            ("EV/EBITDA", f"{stock_data.get('ev_ebitda', 0):.1f}" if pd.notna(stock_data.get('ev_ebitda')) else "N/A")
        ]
        
        growth_metrics = [
            ("Revenue Growth", f"{stock_data.get('revenue_growth', 0)*100:.1f}%" if pd.notna(stock_data.get('revenue_growth')) else "N/A"),
            ("EPS Growth", f"{stock_data.get('eps_growth', 0)*100:.1f}%" if pd.notna(stock_data.get('eps_growth')) else "N/A"),
            ("Profit Margin", f"{stock_data.get('profit_margin', 0)*100:.1f}%" if pd.notna(stock_data.get('profit_margin')) else "N/A"),
            ("Revenue", f"${stock_data.get('revenue', 0)/1e9:.1f}B" if stock_data.get('revenue', 0) >= 1e9 else "N/A")
        ]
        
        quality_metrics = [
            ("ROE", f"{stock_data.get('roe', 0)*100:.1f}%" if pd.notna(stock_data.get('roe')) else "N/A"),
            ("Debt/Equity", f"{stock_data.get('debt_to_equity', 0):.2f}" if pd.notna(stock_data.get('debt_to_equity')) else "N/A"),
            ("Current Ratio", f"{stock_data.get('current_ratio', 0):.2f}" if pd.notna(stock_data.get('current_ratio')) else "N/A")
        ]
        
        income_metrics = [
            ("Dividend Yield", f"{stock_data.get('dividend_yield', 0)*100:.2f}%" if pd.notna(stock_data.get('dividend_yield')) else "N/A"),
            ("Payout Ratio", f"{stock_data.get('payout_ratio', 0)*100:.1f}%" if pd.notna(stock_data.get('payout_ratio')) else "N/A")
        ]
        
        # Display in expandable sections
        with st.expander("Valuation Metrics", expanded=True):
            cols = st.columns(2)
            for i, (label, value) in enumerate(valuation_metrics):
                with cols[i % 2]:
                    st.metric(label, value)
        
        with st.expander("Growth Metrics", expanded=True):
            cols = st.columns(2)
            for i, (label, value) in enumerate(growth_metrics):
                with cols[i % 2]:
                    st.metric(label, value)
        
        with st.expander("Quality Metrics", expanded=True):
            cols = st.columns(2)
            for i, (label, value) in enumerate(quality_metrics):
                with cols[i % 2]:
                    st.metric(label, value)
        
        with st.expander("Income Metrics", expanded=True):
            cols = st.columns(2)
            for i, (label, value) in enumerate(income_metrics):
                with cols[i % 2]:
                    st.metric(label, value)
    
    # Export tab
    with tabs[3]:
        st.subheader("Export Stock Report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Generate Excel Report", key="stock_excel_btn", use_container_width=True):
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    # Main sheet with overview
                    overview_data = pd.DataFrame({
                        'Metric': ['Ticker', 'Name', 'Current Price', 'Market Cap', 'Sector', 'Industry',
                                 'Composite Score', 'P/E Ratio', 'P/B Ratio', 'Dividend Yield', 'Beta',
                                 'Volatility'],
                        'Value': [ticker, stock_data.get('name', 'N/A'),
                                f"${stock_data.get('current_price', 0):.2f}",
                                f"${stock_data.get('market_cap', 0)/1e9:.1f}B" if stock_data.get('market_cap', 0) >= 1e9 
                                else f"${stock_data.get('market_cap', 0)/1e6:.1f}M",
                                stock_data.get('sector', 'N/A'), stock_data.get('industry', 'N/A'),
                                f"{stock_data.get('composite_score', 0):.1f}",
                                f"{stock_data.get('pe_ratio', 0):.1f}" if pd.notna(stock_data.get('pe_ratio')) else "N/A",
                                f"{stock_data.get('pb_ratio', 0):.2f}" if pd.notna(stock_data.get('pb_ratio')) else "N/A",
                                f"{stock_data.get('dividend_yield', 0)*100:.2f}%" if pd.notna(stock_data.get('dividend_yield')) else "N/A",
                                f"{stock_data.get('beta', 0):.2f}" if pd.notna(stock_data.get('beta')) else "N/A",
                                f"{stock_data.get('volatility', 0)*100:.1f}%" if pd.notna(stock_data.get('volatility')) else "N/A"]
                    })
                    
                    overview_data.to_excel(writer, sheet_name='Overview', index=False)
                    
                    # Strategy scores sheet
                    strategy_data = []
                    for strategy in st.session_state.selected_strategies:
                        score_column = f"{strategy.lower()}_score"
                        if score_column in stock_data:
                            strategy_data.append({
                                'Strategy': strategy,
                                'Score': stock_data[score_column]
                            })
                    
                    if strategy_data:
                        pd.DataFrame(strategy_data).to_excel(writer, sheet_name='Strategy Scores', index=False)
                    
                    # Add all available metrics
                    full_data = pd.DataFrame(stock_data).reset_index()
                    full_data.columns = ['Metric', 'Value']
                    full_data.to_excel(writer, sheet_name='All Metrics', index=False)
                
                buffer.seek(0)
                
                st.download_button(
                    "📥 Download Excel Report",
                    buffer,
                    file_name=f"{ticker}_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
        
        with col2:
            if st.button("📑 Generate PDF Report", key="stock_pdf_btn", use_container_width=True):
                with st.spinner("Generating PDF report..."):
                    try:
                        # Create PDF generator
                        pdf_generator = PDFGenerator()
                        
                        # Generate PDF
                        pdf_buffer = pdf_generator.generate_mini_report(
                            ticker,
                            stock_data
                        )
                        
                        # Add download button
                        st.download_button(
                            "📥 Download PDF Report",
                            pdf_buffer,
                            file_name=f"{ticker}_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")

def comparison_page(data_service: DataService):
    """Page for comparing multiple stocks"""
    st.title("Stock Comparison")
    
    if st.session_state.analysis_results is None:
        st.info("No analysis results yet. Please run a screening first in the Screening tab.")
        return
    
    results_df = st.session_state.analysis_results
    
    if results_df.empty:
        st.warning("No analysis results to display. Please run a screening first in the Screening tab.")
        return
    
    # Use the comparison interface from EnhancedUIComponents
    EnhancedUIComponents.show_comparison_interface(results_df)
    
    # Add PDF export for comparison
    st.subheader("Export Comparison Report")
    
    if st.button("📑 Generate Comparison PDF", key="comparison_pdf_btn"):
        with st.spinner("Generating PDF comparison report..."):
            try:
                # Get the selected stocks from the comparison interface
                # (In a real implementation, this would be passed from the comparison interface)
                if len(results_df) >= 3:
                    selected_stocks = results_df.nlargest(3, 'composite_score').index.tolist()
                else:
                    selected_stocks = results_df.index.tolist()
                
                # Create PDF generator
                pdf_generator = PDFGenerator()
                
                # Generate comparison PDF
                pdf_buffer = pdf_generator.generate_comparison_report(
                    results_df,
                    selected_stocks
                )
                
                # Add download button
                st.download_button(
                    "📥 Download Comparison Report",
                    pdf_buffer,
                    file_name=f"stock_comparison_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error generating comparison PDF: {str(e)}")

def backtesting_page(data_service: DataService):
    """Page for backtesting strategies"""
    st.title("Strategy Backtesting")
    
    # Get tickers from analysis results or input
    tickers = st.session_state.selected_tickers if st.session_state.selected_tickers else []
    
    # Use the backtesting interface from EnhancedUIComponents
    EnhancedUIComponents.show_backtest_interface(tickers)
    
    # If backtest results exist, show additional analysis
    if st.session_state.backtest_results is not None:
        st.subheader("Detailed Backtest Analysis")
        
        # In a real implementation, this would display actual backtest results
        st.info("Advanced backtest analysis will be implemented here")
        
        # Add optimizer section
        with st.expander("Portfolio Optimization", expanded=False):
            st.subheader("Optimize Portfolio Weights")
            
            objective = st.selectbox(
                "Optimization Objective",
                ["Maximize Sharpe Ratio", "Maximize Returns", "Minimize Volatility"],
                index=0,
                help="What to optimize for"
            )
            
            if st.button("Run Optimization", key="run_optimization_btn"):
                with st.spinner("Optimizing portfolio weights..."):
                    st.info("Portfolio optimization will be implemented here")

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
        
        # Calculate composite score
        scores = [data[f'{strategy.lower()}_score'] for strategy in ['Momentum', 'Value', 'Growth', 'Quality', 'Income', 'Low Volatility']]
        data['composite_score'] = np.mean(scores)
        
        demo_data.append(data)
    
    df = pd.DataFrame(demo_data)
    df.set_index('ticker', inplace=True)
    
    return df

if __name__ == "__main__":
    main()
