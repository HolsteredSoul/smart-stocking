"""
Enhanced UI Components for SmartStock
Advanced reusable UI components with additional functionality
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import base64
import io
import json
import os
from pathlib import Path
import logging

# Import the SessionStateManager
from utils.session_state_manager import SessionStateManager

class EnhancedUIComponents:
    """Enhanced UI components with advanced functionality"""
    
    @staticmethod
    def show_welcome_section():
        """Display welcome section with app overview"""
        st.markdown("""
        ## Welcome to SmartStock! 📈
        
        SmartStock is a comprehensive multi-strategy stock screening tool that helps you analyze stocks 
        using proven investment strategies. Whether you're looking for value, growth, income, or 
        low-volatility stocks, SmartStock has you covered.
        
        ### Features:
        - **Multi-Strategy Analysis**: Momentum, Value, Growth, Quality, Income, and Low Volatility
        - **Interactive Visualizations**: Dynamic charts and graphs to understand your stocks better
        - **Customizable Screening**: Adjust parameters to match your investment style
        - **Custom Weights**: Fine-tune strategy importance
        - **Export**: Download results as CSV or Excel
        - **Stock Comparison**: Compare multiple stocks side by side
        
        ### Quick Start:
        1. 📊 **Select Strategies**: Choose which investment strategies to apply
        2. 📝 **Enter Tickers**: Input the stocks you want to analyze
        3. 🚀 **Run Analysis**: Click the button and let SmartStock do the work
        4. 📈 **Review Results**: Explore detailed analysis and visualizations
        5. 📑 **Export**: Download results in CSV or Excel format
        """)
        
        with st.expander("⚡ Important: Rate Limits"):
            st.warning("""
            **Yahoo Finance Rate Limits**
            
            SmartStock uses free data sources which have rate limits:
            - **Recommended**: 5 or fewer stocks per analysis
            - **Maximum**: 10 stocks (may trigger rate limits)
            - **Wait time**: 1-2 seconds between stock requests
            
            If you get rate limit errors:
            1. Try fewer stocks
            2. Wait a few minutes before trying again
            3. Use preset lists for quick testing
            """)
        
        with st.expander("📚 Learn About Investment Strategies"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Momentum**: Stocks with strong price performance
                - Looks for upward price trends
                - Considers moving averages
                - Identifies stocks with positive momentum
                
                **Value**: Undervalued stocks with strong fundamentals
                - Low P/E, P/B ratios
                - High dividend yields
                - Strong balance sheets
                
                **Growth**: Companies with expanding earnings
                - Revenue and earnings growth
                - Expanding profit margins
                - Market share gains
                """)
            
            with col2:
                st.markdown("""
                **Quality**: Financially sound companies
                - High return on equity (ROE)
                - Low debt levels
                - Consistent earnings
                
                **Income**: Dividend-paying stocks
                - High dividend yields
                - Sustainable payout ratios
                - Dividend growth history
                
                **Low Volatility**: Stable stock performance
                - Lower price fluctuations
                - Defensive characteristics
                - Lower beta values
                """)
    
    @staticmethod
    def show_advanced_strategy_selector(strategies: Dict[str, str], 
                                     selected_strategies: List[str] = None,
                                     custom_weights: Dict[str, float] = None,
                                     strategy_params: Dict[str, Dict[str, Any]] = None) -> Tuple[List[str], Dict[str, float], Dict[str, Dict[str, Any]]]:
        """Create an advanced strategy selection interface with custom weights and parameters"""
        # Initialize session state using SessionStateManager
        SessionStateManager.initialize_strategy_params()
        
        # Ensure strategy_params is properly initialized
        if selected_strategies is None:
            selected_strategies = []
        if custom_weights is None:
            custom_weights = {}
        if strategy_params is None:
            strategy_params = {}
        
        st.markdown("### 🎯 Select Your Investment Strategies")
        
        # Create columns for strategy selection
        cols = st.columns(3)
        
        new_selected_strategies = []
        
        for i, (strategy, description) in enumerate(strategies.items()):
            with cols[i % 3]:
                checkbox = st.checkbox(
                    strategy,
                    value=strategy in selected_strategies,
                    help=description,
                    key=f"strategy_{strategy}"
                )
                if checkbox:
                    new_selected_strategies.append(strategy)
        
        # Add custom weights option in expander
        with st.expander("⚙️ Strategy Weights and Parameters", expanded=len(new_selected_strategies) > 0):
            if not new_selected_strategies:
                st.info("Select strategies above to configure weights and parameters")
            else:
                st.markdown("#### Adjust Strategy Weights")
                st.info("Drag sliders to adjust how much each strategy influences the final score, or choose a preset blend.")

                # --- Preset Blends ---
                all_strategies = list(strategies.keys())
                presets = {
                    "Custom": None,
                    "Classic Value": {"Momentum": 0.1, "Value": 0.5, "Growth": 0.1, "Quality": 0.2, "Income": 0.1, "Low Volatility": 0.0},
                    "Balanced Growth": {"Momentum": 0.2, "Value": 0.2, "Growth": 0.4, "Quality": 0.1, "Income": 0.05, "Low Volatility": 0.05},
                    "Dividend Focus": {"Momentum": 0.05, "Value": 0.2, "Growth": 0.05, "Quality": 0.1, "Income": 0.5, "Low Volatility": 0.1},
                    "Momentum Tilt": {"Momentum": 0.6, "Value": 0.1, "Growth": 0.1, "Quality": 0.1, "Income": 0.05, "Low Volatility": 0.05},
                    "Defensive": {"Momentum": 0.05, "Value": 0.15, "Growth": 0.1, "Quality": 0.2, "Income": 0.1, "Low Volatility": 0.4}
                }
                preset_names = list(presets.keys())
                preset_choice = st.selectbox("Choose a preset strategy blend:", preset_names, key="strategy_preset")

                if preset_choice != "Custom":
                    preset_weights = presets[preset_choice]
                    # Set all strategies, zero for unused
                    custom_weights = {s: preset_weights.get(s, 0.0) for s in all_strategies}
                    # Only include strategies with nonzero weights for selection
                    new_selected_strategies = [s for s, w in custom_weights.items() if w > 0]
                    # Normalize just in case
                    total = sum(custom_weights.values())
                    if total > 0:
                        for s in custom_weights:
                            custom_weights[s] /= total

                # Robust error handling for weights
                for s in new_selected_strategies:
                    if s not in custom_weights:
                        custom_weights[s] = 0.0
                        st.warning(f"Strategy '{s}' missing weight, defaulting to 0.")
                
                # Initialize total weight tracker and normalized weights
                total_weight = sum(custom_weights.get(strategy, 1.0) for strategy in new_selected_strategies)
                normalized_weights = {}
                
                # Normalize existing weights
                if total_weight > 0:
                    for strategy in new_selected_strategies:
                        normalized_weights[strategy] = custom_weights.get(strategy, 1.0) / total_weight
                else:
                    # Default to equal weights
                    for strategy in new_selected_strategies:
                        normalized_weights[strategy] = 1.0 / len(new_selected_strategies)
                
                # Show weight sliders using N-1 approach
                n = len(new_selected_strategies)
                new_raw_weights = {}
                cols = st.columns(2)
                for i, strategy in enumerate(new_selected_strategies[:-1]):
                    with cols[i % 2]:
                        current_weight = normalized_weights.get(strategy, 1.0 / n)
                        new_raw_weights[strategy] = st.slider(
                            f"{strategy} Weight",
                            min_value=0.0,
                            max_value=1.0,
                            value=float(current_weight),
                            step=0.01,
                            format="%.2f",
                            key=f"weight_{strategy}"
                        )
                # Auto-calculate last weight
                sum_n_1 = sum(new_raw_weights.values())
                last_strategy = new_selected_strategies[-1]
                last_weight = 1.0 - sum_n_1
                with cols[(n-1) % 2]:
                    st.markdown(f"**{last_strategy} Weight**")
                    st.markdown(f"<div style='font-size:1.5em; color:{'red' if last_weight < 0 or last_weight > 1 else 'green'};'>{last_weight:.2f}</div>", unsafe_allow_html=True)
                # Build new_weights dict
                new_weights = dict(new_raw_weights)
                new_weights[last_strategy] = max(0.0, min(1.0, last_weight))
                if last_weight < 0 or last_weight > 1:
                    st.error("Invalid weights! Please adjust sliders so total does not exceed 1.0.")
                
                # Show pie chart of weights
                fig = px.pie(
                    names=list(new_weights.keys()),
                    values=list(new_weights.values()),
                    title="Strategy Weight Distribution"
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
                
                # Advanced Parameters
                st.markdown("#### Advanced Strategy Parameters")
                st.info("Configure detailed parameters for each selected strategy.")
                
                new_params = {}
                
                # Parameter definitions for each strategy (default values and descriptions)
                param_definitions = {
                    "Momentum": {
                        "short_period": {"default": 50, "desc": "Short-term moving average period", "min": 10, "max": 100, "step": 5},
                        "long_period": {"default": 200, "desc": "Long-term moving average period", "min": 50, "max": 300, "step": 10},
                        "weight_1m": {"default": 0.1, "desc": "Weight for 1-month returns", "min": 0.0, "max": 1.0, "step": 0.05},
                        "weight_3m": {"default": 0.2, "desc": "Weight for 3-month returns", "min": 0.0, "max": 1.0, "step": 0.05},
                        "weight_6m": {"default": 0.3, "desc": "Weight for 6-month returns", "min": 0.0, "max": 1.0, "step": 0.05},
                        "weight_12m": {"default": 0.4, "desc": "Weight for 12-month returns", "min": 0.0, "max": 1.0, "step": 0.05},
                    },
                    "Value": {
                        "pe_excellent": {"default": 15, "desc": "Excellent P/E threshold", "min": 5, "max": 30, "step": 1},
                        "pe_good": {"default": 20, "desc": "Good P/E threshold", "min": 10, "max": 40, "step": 1},
                        "pb_excellent": {"default": 1.5, "desc": "Excellent P/B threshold", "min": 0.5, "max": 5.0, "step": 0.1},
                        "dividend_min": {"default": 0.02, "desc": "Minimum dividend yield for bonus", "min": 0.0, "max": 0.05, "step": 0.005},
                    },
                    "Growth": {
                        "revenue_excellent": {"default": 15, "desc": "Excellent revenue growth (%)", "min": 5, "max": 30, "step": 1},
                        "eps_excellent": {"default": 20, "desc": "Excellent EPS growth (%)", "min": 5, "max": 30, "step": 1},
                    },
                    "Quality": {
                        "roe_excellent": {"default": 20, "desc": "Excellent ROE threshold (%)", "min": 10, "max": 30, "step": 1},
                        "debt_excellent": {"default": 0.5, "desc": "Excellent debt to equity", "min": 0.1, "max": 2.0, "step": 0.1},
                    },
                    "Income": {
                        "yield_excellent": {"default": 4.0, "desc": "Excellent yield threshold (%)", "min": 2.0, "max": 8.0, "step": 0.5},
                        "payout_sweet_min": {"default": 0.3, "desc": "Minimum ideal payout ratio", "min": 0.1, "max": 0.5, "step": 0.05},
                        "payout_sweet_max": {"default": 0.6, "desc": "Maximum ideal payout ratio", "min": 0.4, "max": 0.8, "step": 0.05},
                    },
                    "Low Volatility": {
                        "vol_excellent": {"default": 0.15, "desc": "Excellent volatility threshold", "min": 0.05, "max": 0.3, "step": 0.01},
                        "beta_excellent": {"default": 0.8, "desc": "Excellent beta threshold", "min": 0.5, "max": 1.5, "step": 0.1},
                    }
                }
                
                # Create parameter controls for each selected strategy
                for strategy in new_selected_strategies:
                    new_params[strategy] = {}
                    
                    # Get current parameters
                    current_params = strategy_params.get(strategy, {})
                    
                    # Create header for each strategy
                    st.markdown(f"### {strategy} Parameters")
                    
                    # Get parameter definitions for this strategy
                    strategy_param_defs = param_definitions.get(strategy, {})
                    
                    if not strategy_param_defs:
                        st.info(f"No configurable parameters for {strategy}")
                        continue
                    
                    # Create controls for each parameter
                    param_cols = st.columns(2)
                    param_idx = 0
                    
                    for param_name, param_info in strategy_param_defs.items():
                        with param_cols[param_idx % 2]:
                            # Get parameter value using SessionStateManager for safety
                            default_value = param_info["default"]
                            current_value = SessionStateManager.get_param_value(strategy, param_name, default_value)
                            
                            # Create slider with safe values
                            new_value = st.slider(
                                f"{param_info['desc']}",
                                min_value=float(param_info["min"]),
                                max_value=float(param_info["max"]),
                                value=float(current_value),
                                step=float(param_info["step"]),
                                key=f"param_display_{strategy}_{param_name}"  # New key pattern
                            )
                            
                            # Safely store the value
                            SessionStateManager.set_param_value(strategy, param_name, new_value)
                            
                            # Also store in the new params for returning
                            new_params[strategy][param_name] = float(new_value)
                            
                            param_idx += 1
                    
                    # Add a separator between strategies
                    st.divider()
                
                # Show reset button
                if st.button("Reset All Parameters to Defaults"):
                    # Use SessionStateManager to safely reset parameters
                    for strategy in new_selected_strategies:
                        strategy_defaults = {}
                        for param_name, param_info in param_definitions.get(strategy, {}).items():
                            strategy_defaults[param_name] = param_info["default"]
                        
                        # Set defaults for this strategy
                        SessionStateManager.set_strategy_params(strategy, strategy_defaults)
                        
                        # Update new_params for return value
                        new_params[strategy] = strategy_defaults.copy()
                        
                        # Also reset weights
                        new_weights[strategy] = 1.0 / len(new_selected_strategies)
                    
                    st.rerun()
        
        return new_selected_strategies, new_weights, new_params
    
    @staticmethod
    def show_comparison_interface(results_df: pd.DataFrame):
        """Add interface for comparing multiple stocks side by side"""
        st.subheader("📊 Stock Comparison")
        
        # Multi-select for stocks
        if results_df is not None and not results_df.empty:
            # Get top 10 stocks as default
            if len(results_df) >= 3:
                default_stocks = results_df.nlargest(3, 'composite_score').index.tolist()
            else:
                default_stocks = results_df.index.tolist()
                
            selected_stocks = st.multiselect(
                "Select stocks to compare:",
                options=results_df.index.tolist(),
                default=default_stocks,
                help="Choose 2-5 stocks for best comparison visualization"
            )
            
            if not selected_stocks:
                st.info("Please select stocks to compare")
                return
                
            if len(selected_stocks) > 5:
                st.warning("Comparing more than 5 stocks may make visualizations difficult to read")
            
            # Create comparison table
            comparison_df = results_df.loc[selected_stocks]
            
            # Display metrics side by side
            metrics = ['composite_score', 'current_price', 'pe_ratio', 'market_cap', 'dividend_yield', 'volatility']
            available_metrics = [m for m in metrics if m in comparison_df.columns]
            
            # Format and display the table
            formatted_df = comparison_df[available_metrics].copy()
            
            if 'market_cap' in formatted_df.columns:
                formatted_df['market_cap'] = formatted_df['market_cap'].apply(
                    lambda x: f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.1f}M"
                )
            
            if 'current_price' in formatted_df.columns:
                formatted_df['current_price'] = formatted_df['current_price'].apply(lambda x: f"${x:.2f}")
                
            if 'pe_ratio' in formatted_df.columns:
                formatted_df['pe_ratio'] = formatted_df['pe_ratio'].apply(
                    lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
                )
                
            if 'dividend_yield' in formatted_df.columns:
                formatted_df['dividend_yield'] = formatted_df['dividend_yield'].apply(
                    lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                )
                
            if 'volatility' in formatted_df.columns:
                formatted_df['volatility'] = formatted_df['volatility'].apply(
                    lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
                )
            
            if 'composite_score' in formatted_df.columns:
                formatted_df['composite_score'] = formatted_df['composite_score'].apply(lambda x: f"{x:.1f}")
            
            # Rename columns for display
            column_renames = {
                'composite_score': 'Overall Score',
                'current_price': 'Price',
                'pe_ratio': 'P/E Ratio',
                'market_cap': 'Market Cap',
                'dividend_yield': 'Dividend Yield',
                'volatility': 'Volatility'
            }
            
            formatted_df = formatted_df.rename(columns=column_renames)
            
            # Display table
            st.dataframe(formatted_df)
            
            # Add visual comparison of strategy scores
            st.subheader("Strategy Score Comparison")
            
            # Identify strategy score columns
            strategy_cols = [col for col in comparison_df.columns if col.endswith('_score') and col != 'composite_score']
            
            if strategy_cols:
                categories = [col.replace('_score', '').title() for col in strategy_cols]
                
                if len(strategy_cols) >= 3:
                    # Radar chart works well with 3+ axes
                    fig = go.Figure()
                    
                    for i, ticker in enumerate(selected_stocks):
                        values = [comparison_df.loc[ticker, col] for col in strategy_cols]
                        values.append(values[0])
                        text_categories = categories + [categories[0]]
                        
                        fig.add_trace(go.Scatterpolar(
                            r=values,
                            theta=text_categories,
                            fill='toself',
                            name=ticker,
                            line_color=px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]
                        ))
                    
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(visible=True, range=[0, 100])
                        ),
                        showlegend=True,
                        title="Strategy Score Comparison",
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Grouped bar chart for 1-2 strategies (radar is useless with <3 axes)
                    bar_data = []
                    for ticker in selected_stocks:
                        for col, cat in zip(strategy_cols, categories):
                            bar_data.append({
                                'Stock': ticker,
                                'Strategy': cat,
                                'Score': comparison_df.loc[ticker, col]
                            })
                    bar_df = pd.DataFrame(bar_data)
                    
                    fig = px.bar(
                        bar_df,
                        x='Stock',
                        y='Score',
                        color='Strategy',
                        barmode='group',
                        title='Strategy Score Comparison',
                        text_auto='.1f'
                    )
                    fig.update_layout(yaxis_range=[0, 100], height=450)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Add bar chart comparison of overall scores
            fig = px.bar(
                comparison_df, 
                y='composite_score',
                title="Composite Score Comparison",
                color=comparison_df.index,
                labels={'composite_score': 'Composite Score', 'index': 'Stock'},
                text_auto='.1f'
            )
            
            fig.update_layout(
                xaxis_title="Stock",
                yaxis_title="Composite Score",
                showlegend=False,
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # PDF comparison report
            if st.button("📑 Generate Comparison PDF Report"):
                pdf_bytes = EnhancedUIComponents._generate_comparison_pdf(
                    results_df, selected_tickers
                )
                if pdf_bytes:
                    st.download_button(
                        "📥 Download PDF Report",
                        data=pdf_bytes,
                        file_name="smartstock_comparison.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                else:
                    st.error("PDF generation failed. Please install fpdf2: pip install fpdf2")
        else:
            st.info("No analysis results yet. Please run a screening first in the Screening tab.")
    
    @staticmethod
    def show_backtest_interface(tickers: List[str] = None):
        """Add interface for backtesting strategies"""
        st.header("📈 Strategy Backtesting")
        
        if not tickers:
            st.warning("No tickers selected. Please run a screening first or enter tickers manually.")
            tickers = st.text_input(
                "Enter tickers for backtesting (comma-separated)",
                value="AAPL, MSFT, GOOGL, AMZN, TSLA",
                help="Enter stock symbols separated by commas (e.g., AAPL, MSFT, GOOGL)"
            )
            
            if tickers:
                tickers = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
        
        if tickers:
            st.write(f"Backtesting with {len(tickers)} stocks: {', '.join(tickers[:5])}" + 
                    ("..." if len(tickers) > 5 else ""))
            
            # Create config section
            st.subheader("Backtest Configuration")
            
            col1, col2 = st.columns(2)
            
            # Date range selection
            with col1:
                # Use date input for more precise dates
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now() - timedelta(days=365*2),  # Default to 2 years ago
                    help="Start date for the backtest period"
                )
                
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now() - timedelta(days=7),  # Default to a week ago
                    help="End date for the backtest period"
                )
                
                if start_date >= end_date:
                    st.error("Start date must be before end date")
            
            # Strategy selection
            with col2:
                rebalance_period = st.selectbox(
                    "Rebalance Period",
                    options=["monthly", "quarterly", "yearly"],
                    index=0,
                    help="How often to rebalance the portfolio"
                )
                
                top_n = st.slider(
                    "Top Stocks to Include",
                    min_value=1,
                    max_value=min(20, len(tickers)),
                    value=min(5, len(tickers)),
                    help="Number of top-ranked stocks to include in the portfolio"
                )
                
                initial_capital = st.number_input(
                    "Initial Capital ($)",
                    min_value=1000,
                    max_value=1000000,
                    value=10000,
                    step=1000,
                    help="Starting capital for the backtest"
                )
            
            # Strategy selection using the enhanced strategy selector
            strategies = {
                "Momentum": "12-month price momentum and trend analysis",
                "Value": "Low P/E, P/B ratios and undervaluation metrics",
                "Growth": "Revenue and earnings growth acceleration",
                "Quality": "High ROE, stable earnings, strong fundamentals",
                "Income": "High dividend yield and payout sustainability",
                "Low Volatility": "Lower price volatility and risk metrics"
            }
            
            selected_strategies, weights, params = EnhancedUIComponents.show_advanced_strategy_selector(
                strategies,
                selected_strategies=["Momentum", "Value"],  # Default to two strategies
                custom_weights={},
                strategy_params={}
            )
            
            # Benchmark comparison
            benchmark_options = {
                "SPY": "S&P 500 ETF",
                "QQQ": "NASDAQ 100 ETF",
                "IWM": "Russell 2000 ETF",
                "DIA": "Dow Jones Industrial Average ETF",
                "None": "No benchmark comparison"
            }
            
            benchmark = st.selectbox(
                "Benchmark for Comparison",
                options=list(benchmark_options.keys()),
                index=0,
                format_func=lambda x: f"{x} - {benchmark_options[x]}",
                help="Compare your strategy against a market benchmark"
            )
            
            # Run backtest button
            if st.button("▶️ Run Backtest", type="primary"):
                if not selected_strategies:
                    st.error("Please select at least one strategy to backtest")
                elif start_date >= end_date:
                    st.error("Start date must be before end date.")
                else:
                    with st.spinner("Running backtest… fetching historical prices and scoring the universe."):
                        from services.data_service import DataService
                        from models.strategy_config import StrategyConfig
                        bt_config = StrategyConfig(
                            strategies=selected_strategies,
                            tickers=tickers,
                            custom_weights=weights,
                        )
                        result = DataService().run_backtest(
                            config=bt_config,
                            start_date=str(start_date),
                            end_date=str(end_date),
                            top_n=top_n,
                        )

                    if "error" in result:
                        st.error(f"Backtest failed: {result['error']}")
                        st.info("Showing illustrative sample results instead.")
                        EnhancedUIComponents.show_sample_backtest_results(
                            tickers=tickers,
                            start_date=start_date,
                            end_date=end_date,
                            strategies=selected_strategies,
                            rebalance_period=rebalance_period,
                            initial_capital=initial_capital,
                            benchmark=benchmark if benchmark != "None" else None,
                            top_n=top_n,
                        )
                    else:
                        EnhancedUIComponents._show_real_backtest_results(
                            result=result,
                            initial_capital=initial_capital,
                            benchmark=benchmark if benchmark != "None" else None,
                        )
    
    @staticmethod
    def _show_real_backtest_results(result: dict, initial_capital: float, benchmark: str = None):
        """Display real backtest results returned by DataService.run_backtest()."""
        st.subheader("Backtest Results")
        st.caption(
            f"Equal-weight portfolio of top {result.get('n_stocks', '?')} stocks: "
            + ", ".join(result.get("top_tickers", []))
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Return", f"{result['total_return_pct']:.1f}%")
        with col2:
            st.metric("Ann. Return", f"{result['ann_return_pct']:.1f}%")
        with col3:
            st.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
        with col4:
            st.metric("Max Drawdown", f"{result['max_drawdown_pct']:.1f}%")

        pv = result.get("portfolio_values")
        if pv is not None and not pv.empty:
            # Scale to initial capital
            pv_scaled = pv * (initial_capital / 100)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pv_scaled.index, y=pv_scaled["Portfolio Value"],
                mode="lines", name="Strategy Portfolio",
                line=dict(color="#636EFA", width=2),
            ))
            fig.update_layout(
                title="Portfolio Value Over Time",
                xaxis_title="Date", yaxis_title="Portfolio Value ($)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def _generate_comparison_pdf(results_df, tickers: List[str]) -> bytes:
        """Generate a PDF report comparing selected stocks. Returns PDF bytes or None."""
        try:
            from fpdf import FPDF
        except ImportError:
            return None

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        _SCORE_TIERS = [
            (80, "Excellent"), (60, "Good"), (40, "Average"), (0, "Weak")
        ]

        def _tier(score):
            for threshold, label in _SCORE_TIERS:
                if score >= threshold:
                    return label
            return "Weak"

        for ticker in tickers:
            if ticker not in results_df.index:
                continue
            row = results_df.loc[ticker]
            pdf.add_page()

            # Header
            pdf.set_font("Helvetica", "B", 18)
            pdf.cell(0, 10, f"SmartStock Report: {ticker}", ln=True)
            pdf.set_font("Helvetica", "", 11)
            name = str(row.get("name", ""))
            score = float(row.get("composite_score", 0))
            pdf.cell(0, 7, f"{name}  |  Score: {score:.1f} ({_tier(score)})", ln=True)
            pdf.cell(0, 7, f"Sector: {row.get('sector', 'N/A')}  |  Price: ${row.get('current_price', 0):.2f}", ln=True)
            pdf.ln(4)

            # Key metrics table
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Key Metrics", ln=True)
            pdf.set_font("Helvetica", "", 10)
            metrics = [
                ("P/E Ratio",       f"{row.get('pe_ratio', float('nan')):.1f}"   if not pd.isna(row.get('pe_ratio', float('nan'))) else "N/A"),
                ("P/B Ratio",       f"{row.get('pb_ratio', float('nan')):.2f}"   if not pd.isna(row.get('pb_ratio', float('nan'))) else "N/A"),
                ("P/S Ratio",       f"{row.get('ps_ratio', float('nan')):.2f}"   if not pd.isna(row.get('ps_ratio', float('nan'))) else "N/A"),
                ("Div Yield",       f"{row.get('dividend_yield', 0)*100:.2f}%"),
                ("ROE",             f"{row.get('roe', float('nan'))*100:.1f}%"   if not pd.isna(row.get('roe', float('nan'))) else "N/A"),
                ("Debt/Equity",     f"{row.get('debt_to_equity', float('nan')):.2f}" if not pd.isna(row.get('debt_to_equity', float('nan'))) else "N/A"),
            ]
            col_w = 95
            for i, (label, value) in enumerate(metrics):
                if i % 2 == 0:
                    pdf.cell(col_w, 7, f"{label}: {value}", border=0)
                else:
                    pdf.cell(col_w, 7, f"{label}: {value}", border=0, ln=True)
            if len(metrics) % 2 != 0:
                pdf.ln(7)
            pdf.ln(4)

            # Strategy scores
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Strategy Scores", ln=True)
            pdf.set_font("Helvetica", "", 10)
            score_cols = {
                "Momentum": "momentum_score", "Value": "value_score",
                "Growth": "growth_score", "Quality": "quality_score",
                "Income": "income_score", "Low Volatility": "volatility_score",
            }
            for strat, col in score_cols.items():
                val = row.get(col)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    bar_w = int(float(val) / 100 * 80)
                    pdf.cell(40, 6, strat, border=0)
                    pdf.cell(bar_w, 6, "", border=0, fill=False)
                    pdf.cell(0, 6, f"  {float(val):.1f} ({_tier(float(val))})", ln=True)

        return bytes(pdf.output())

    @staticmethod
    def show_sample_backtest_results(tickers: List[str], start_date, end_date,
                                     strategies: List[str], rebalance_period: str,
                                     initial_capital: float, benchmark: str = None, top_n: int = 5):
        """Show sample backtest results for demonstration"""
        st.subheader("Backtest Results")
        
        # Create simple metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_return = 0.145  # 14.5%
            st.metric(
                "Total Return",
                f"{total_return:.1%}",
                delta=f"{total_return - 0.11:.1%}",  # Compare to benchmark
                delta_color="normal"
            )
        
        with col2:
            annual_return = 0.118  # 11.8%
            st.metric(
                "Annual Return",
                f"{annual_return:.1%}",
                delta=f"{annual_return - 0.098:.1%}",  # Compare to benchmark
                delta_color="normal"
            )
        
        with col3:
            sharpe = 0.85
            st.metric(
                "Sharpe Ratio",
                f"{sharpe:.2f}",
                delta=f"{sharpe - 0.72:.2f}",  # Compare to benchmark
                delta_color="normal"
            )
        
        with col4:
            max_dd = -0.218  # -21.8%
            st.metric(
                "Max Drawdown",
                f"{max_dd:.1%}",
                delta=f"{max_dd - (-0.24):.1%}",  # Compare to benchmark
                delta_color="inverse"  # Lower is better for drawdown
            )
        
        # Create sample equity curve
        st.subheader("Portfolio Performance")
        
        # Generate sample equity curve data
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Sample data generation
        np.random.seed(42)  # For reproducibility
        equity_values = [initial_capital]
        
        # Add some randomness but with an uptrend
        for i in range(1, len(date_range)):
            daily_return = np.random.normal(0.0002, 0.013)  # Mean positive return with volatility
            new_value = equity_values[-1] * (1 + daily_return)
            equity_values.append(new_value)
        
        # Create a DataFrame
        equity_df = pd.DataFrame({
            'date': date_range,
            'portfolio_value': equity_values
        })
        
        # Sample benchmark data
        if benchmark:
            benchmark_values = [initial_capital]
            for i in range(1, len(date_range)):
                daily_return = np.random.normal(0.00015, 0.01)  # Slightly lower return
                new_value = benchmark_values[-1] * (1 + daily_return)
                benchmark_values.append(new_value)
            
            equity_df['benchmark'] = benchmark_values
        
        # Create the plotly figure
        fig = go.Figure()
        
        # Add the portfolio line
        fig.add_trace(go.Scatter(
            x=equity_df['date'],
            y=equity_df['portfolio_value'],
            mode='lines',
            name='Strategy',
            line=dict(color='#1f77b4', width=2)
        ))
        
        # Add benchmark if selected
        if benchmark:
            fig.add_trace(go.Scatter(
                x=equity_df['date'],
                y=equity_df['benchmark'],
                mode='lines',
                name=benchmark,
                line=dict(color='#ff7f0e', width=2, dash='dot')
            ))
        
        # Add annotations for key events
        annotations = []
        
        # Sample rebalance dates
        if rebalance_period == "monthly":
            rebalance_dates = pd.date_range(start=start_date, end=end_date, freq='M')
        elif rebalance_period == "quarterly":
            rebalance_dates = pd.date_range(start=start_date, end=end_date, freq='Q')
        else:  # yearly
            rebalance_dates = pd.date_range(start=start_date, end=end_date, freq='Y')
        
        # Add rebalance markers
        for date in rebalance_dates:
            if date in equity_df['date'].values:
                idx = equity_df[equity_df['date'] == date].index[0]
                fig.add_trace(go.Scatter(
                    x=[date],
                    y=[equity_df.loc[idx, 'portfolio_value']],
                    mode='markers',
                    marker=dict(symbol='triangle-down', size=10, color='green'),
                    name='Rebalance',
                    showlegend=bool(idx == 0)  # Only show in legend once
                ))
        
        # Layout
        fig.update_layout(
            title="Portfolio Equity Curve",
            xaxis_title="Date",
            yaxis_title="Portfolio Value ($)",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            hovermode="x unified",
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show drawdown chart
        st.subheader("Drawdown Analysis")
        
        # Calculate drawdown
        equity_df['peak'] = equity_df['portfolio_value'].cummax()
        equity_df['drawdown'] = (equity_df['portfolio_value'] / equity_df['peak'] - 1) * 100
        
        if benchmark:
            equity_df['benchmark_peak'] = equity_df['benchmark'].cummax()
            equity_df['benchmark_drawdown'] = (equity_df['benchmark'] / equity_df['benchmark_peak'] - 1) * 100
        
        # Create drawdown chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=equity_df['date'],
            y=equity_df['drawdown'],
            mode='lines',
            name='Strategy Drawdown',
            line=dict(color='#d62728', width=2),
            fill='tozeroy',
            fillcolor='rgba(214, 39, 40, 0.2)'
        ))
        
        if benchmark:
            fig.add_trace(go.Scatter(
                x=equity_df['date'],
                y=equity_df['benchmark_drawdown'],
                mode='lines',
                name=f'{benchmark} Drawdown',
                line=dict(color='#ff7f0e', width=2, dash='dot')
            ))
        
        fig.update_layout(
            title="Portfolio Drawdown",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            hovermode="x unified",
            height=400,
            yaxis=dict(tickformat='.1f')
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show position allocation
        st.subheader("Position Allocation")
        
        # Create sample position data
        position_data = []
        
        sample_positions = tickers[:top_n]
        
        for i, ticker in enumerate(sample_positions):
            # Sample weighting
            weight = 1.0 / len(sample_positions)
            value = equity_df['portfolio_value'].iloc[-1] * weight
            shares = value / (100 + 10*i)  # Mock price
            
            position_data.append({
                'ticker': ticker,
                'shares': shares,
                'price': (100 + 10*i),
                'value': value,
                'weight': weight
            })
        
        # Create DataFrame
        position_df = pd.DataFrame(position_data)
        
        # Display as table
        st.dataframe(position_df)
        
        # Create pie chart of positions
        fig = px.pie(
            position_df,
            values='value',
            names='ticker',
            title='Current Portfolio Allocation'
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add report download button
        st.subheader("Download Backtest Report")
        
        if st.button("📊 Generate Detailed Backtest Report (PDF)"):
            st.info("Generating PDF backtest report...")
            
            # In a real implementation, you would generate the PDF here
            st.markdown("PDF report will be provided here once implemented")
        
        # Add trades table
        st.subheader("Trade History")
        
        # Sample trade data
        trades = []
        
        for i, date in enumerate(rebalance_dates):
            for ticker in sample_positions:
                action = "BUY" if i == 0 else np.random.choice(["BUY", "SELL"])
                price = 100 + 10 * sample_positions.index(ticker) + np.random.normal(0, 5)
                shares = np.random.randint(10, 100)
                
                trades.append({
                    'date': date,
                    'ticker': ticker,
                    'action': action,
                    'shares': shares,
                    'price': price,
                    'value': shares * price
                })
        
        # Create DataFrame
        trades_df = pd.DataFrame(trades)
        trades_df = trades_df.sort_values('date', ascending=False)
        
        # Display as table
        st.dataframe(trades_df)
    
    @staticmethod
    def save_user_preferences(preferences: Dict[str, Any]) -> bool:
        """Save user preferences to file"""
        try:
            # Create the .streamlit directory if it doesn't exist
            os.makedirs('.streamlit', exist_ok=True)
            
            prefs_file = '.streamlit/user_prefs.json'
            
            with open(prefs_file, 'w') as f:
                json.dump(preferences, f, indent=2)
                
            return True
        except Exception as e:
            st.error(f"Failed to save preferences: {str(e)}")
            return False
    
    @staticmethod
    def load_user_preferences() -> Dict[str, Any]:
        """Load user preferences from file"""
        try:
            prefs_file = '.streamlit/user_prefs.json'
            
            if os.path.exists(prefs_file):
                with open(prefs_file, 'r') as f:
                    return json.load(f)
            
            return {}
        except Exception as e:
            st.warning(f"Failed to load preferences: {str(e)}")
            return {}
    
    @staticmethod
    def show_settings_page(current_preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """Display and update user settings"""
        if current_preferences is None:
            current_preferences = EnhancedUIComponents.load_user_preferences()
        
        st.title("⚙️ Settings & Preferences")
        
        preferences = {}
        
        # Create settings sections
        st.header("General Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            preferences['default_lookback'] = st.selectbox(
                "Default Lookback Period",
                options=["1 Month", "3 Months", "6 Months", "1 Year", "2 Years"],
                index=3,  # Default to 1 Year
                help="Default time period for historical data"
            )
            
            preferences['default_scoring'] = st.selectbox(
                "Default Scoring Method",
                options=["Rank Aggregation", "Percentile Scoring", "Custom Weights"],
                index=0,
                help="How strategy scores are combined by default"
            )
        
        with col2:
            preferences['default_min_market_cap'] = st.slider(
                "Default Minimum Market Cap ($B)",
                min_value=0.1,
                max_value=10.0,
                value=current_preferences.get('default_min_market_cap', 1.0),
                step=0.1,
                help="Default minimum market capitalization in billions"
            )
            
            preferences['max_stocks'] = st.slider(
                "Maximum Stocks to Analyze",
                min_value=5,
                max_value=50,
                value=current_preferences.get('max_stocks', 10),
                step=5,
                help="Maximum number of stocks to analyze at once"
            )
        
        # API Keys section
        st.header("API Keys")
        st.markdown("Add API keys to enable additional data sources (optional)")
        
        api_keys_expander = st.expander("API Key Configuration", expanded=False)
        with api_keys_expander:
            col1, col2 = st.columns(2)
            
            with col1:
                preferences['alpha_vantage_key'] = st.text_input(
                    "Alpha Vantage API Key",
                    value=current_preferences.get('alpha_vantage_key', ""),
                    type="password",
                    help="Get a free key at alphavantage.co"
                )
                
                preferences['finnhub_key'] = st.text_input(
                    "Finnhub API Key",
                    value=current_preferences.get('finnhub_key', ""),
                    type="password",
                    help="Get a free key at finnhub.io"
                )
            
            with col2:
                preferences['fmp_key'] = st.text_input(
                    "Financial Modeling Prep API Key",
                    value=current_preferences.get('fmp_key', ""),
                    type="password",
                    help="Get a free key at financialmodelingprep.com"
                )
                
                preferences['polygon_key'] = st.text_input(
                    "Polygon.io API Key",
                    value=current_preferences.get('polygon_key', ""),
                    type="password",
                    help="Get a free key at polygon.io"
                )
        
        # Default Strategy Weights
        st.header("Default Strategy Weights")
        st.markdown("Set default weights for each strategy")
        
        # Get current strategy weights
        current_weights = current_preferences.get('strategy_weights', {})
        
        strategies = {
            "Momentum": "12-month price momentum and trend analysis",
            "Value": "Low P/E, P/B ratios and undervaluation metrics",
            "Growth": "Revenue and earnings growth acceleration",
            "Quality": "High ROE, stable earnings, strong fundamentals",
            "Income": "High dividend yield and payout sustainability",
            "Low Volatility": "Lower price volatility and risk metrics"
        }
        
        weights = {}
        total_weight = 0
        
        cols = st.columns(3)
        for i, (strategy, description) in enumerate(strategies.items()):
            with cols[i % 3]:
                weight = st.slider(
                    f"{strategy} Weight",
                    min_value=0.0,
                    max_value=1.0,
                    value=current_weights.get(strategy, 1.0/len(strategies)),
                    step=0.05,
                    key=f"default_weight_{strategy}"
                )
                weights[strategy] = weight
                total_weight += weight
        
        # Normalize the weights
        if total_weight > 0:
            preferences['strategy_weights'] = {k: v/total_weight for k, v in weights.items()}
        else:
            # If all weights are zero, use equal weights
            preferences['strategy_weights'] = {k: 1.0/len(strategies) for k in strategies}
        
        # Show the weight distribution
        fig = px.pie(
            names=list(preferences['strategy_weights'].keys()),
            values=list(preferences['strategy_weights'].values()),
            title="Strategy Weight Distribution"
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
        
        # Visual preferences
        st.header("Visual Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            preferences['chart_theme'] = st.selectbox(
                "Chart Theme",
                options=["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn"],
                index=1,  # Default to plotly_white
                help="Visual theme for charts and visualizations"
            )
            
            preferences['default_chart_height'] = st.slider(
                "Default Chart Height",
                min_value=300,
                max_value=800,
                value=current_preferences.get('default_chart_height', 500),
                step=50,
                help="Default height for charts in pixels"
            )
        
        with col2:
            preferences['show_welcome'] = st.checkbox(
                "Show Welcome Section",
                value=current_preferences.get('show_welcome', True),
                help="Show the welcome section on app startup"
            )
            
            preferences['show_tooltips'] = st.checkbox(
                "Show Detailed Tooltips",
                value=current_preferences.get('show_tooltips', True),
                help="Show detailed tooltips for controls"
            )
        
        # Save Settings button
        if st.button("💾 Save Settings", type="primary"):
            success = EnhancedUIComponents.save_user_preferences(preferences)
            if success:
                st.success("Settings saved successfully!")
                st.rerun()
            else:
                st.error("Failed to save settings. Please try again.")
        
        # Reset button
        if st.button("Reset to Defaults"):
            default_preferences = {
                'default_lookback': "1 Year",
                'default_scoring': "Rank Aggregation",
                'default_min_market_cap': 1.0,
                'max_stocks': 10,
                'strategy_weights': {s: 1.0/len(strategies) for s in strategies},
                'chart_theme': "plotly_white",
                'default_chart_height': 500,
                'show_welcome': True,
                'show_tooltips': True,
                'alpha_vantage_key': "",
                'finnhub_key': "",
                'fmp_key': "",
                'polygon_key': ""
            }
            
            success = EnhancedUIComponents.save_user_preferences(default_preferences)
            if success:
                st.success("Settings reset to defaults!")
                st.rerun()
            else:
                st.error("Failed to reset settings. Please try again.")
        
        return preferences
