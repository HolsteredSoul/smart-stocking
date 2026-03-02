"""
Visualization utilities for SmartStock
Creates interactive charts using Plotly
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import plotly.figure_factory as ff

class ChartBuilder:
    """Builds various interactive charts for the stock screener"""
    
    def __init__(self):
        self.theme = "plotly_white"
        self.color_scheme = px.colors.qualitative.Set3
    
    def create_strategy_comparison(self, results_df: pd.DataFrame, strategies: List[str]) -> go.Figure:
        """Create a radar chart comparing strategies for top stocks"""
        # Check if DataFrame is empty or missing required column
        if results_df.empty or 'composite_score' not in results_df.columns:
            return None
        
        # Check if we have strategies to display
        if not strategies:
            return None
        
        # Get top 5 stocks by composite score
        try:
            top_stocks = results_df.nlargest(5, 'composite_score')
        except:
            # If nlargest fails, just take first 5
            top_stocks = results_df.head(5)
        
        if top_stocks.empty:
            return None
        
        # Prepare data for radar chart
        categories = []
        
        for strategy in strategies:
            score_column = f"{strategy.lower()}_score"
            if score_column in top_stocks.columns:
                categories.append(strategy)
        
        if not categories:
            return None
        
        # Create traces for each stock
        traces = []
        for idx, (ticker, row) in enumerate(top_stocks.iterrows()):
            values = []
            for strategy in categories:
                score_column = f"{strategy.lower()}_score"
                values.append(row[score_column] if pd.notna(row[score_column]) else 0)
            
            trace = go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name=ticker,
                line=dict(color=self.color_scheme[idx % len(self.color_scheme)])
            )
            traces.append(trace)
        
        if not traces:
            return None
        
        # Create layout
        layout = go.Layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            showlegend=True,
            title="Strategy Comparison - Top 5 Stocks"
        )
        
        return go.Figure(data=traces, layout=layout)
    
    def create_correlation_heatmap(self, results_df: pd.DataFrame) -> go.Figure:
        """Create a correlation heatmap of strategy scores"""
        # Check if DataFrame is empty
        if results_df.empty:
            return None
        
        # Select score columns
        score_columns = [col for col in results_df.columns if col.endswith('_score')]
        
        if not score_columns:
            return None
        
        # Calculate correlation matrix
        try:
            corr_matrix = results_df[score_columns].corr()
        except:
            return None
        
        # Clean up column names for display
        display_names = [col.replace('_score', '').title() for col in score_columns]
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=display_names,
            y=display_names,
            colorscale='RdBu',
            zmid=0,
            text=np.round(corr_matrix.values, 2),
            texttemplate='%{text}',
            textfont={"size": 12},
            colorbar=dict(title="Correlation")
        ))
        
        fig.update_layout(
            title="Strategy Score Correlations",
            width=800,
            height=600
        )
        
        return fig
    
    def create_risk_return_scatter(self, results_df: pd.DataFrame) -> go.Figure:
        """Create a risk-return scatter plot"""
        # Check if DataFrame is empty or missing required columns
        if results_df.empty or 'composite_score' not in results_df.columns:
            return None
        
        # Use volatility as risk measure
        if 'volatility' not in results_df.columns:
            # Calculate a simple volatility proxy if not present
            results_df['volatility'] = 0.20  # Placeholder
        
        # Create scatter plot
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=results_df['volatility'],
            y=results_df['composite_score'],
            mode='markers+text',
            text=results_df.index,
            textposition="top center",
            marker=dict(
                size=10,
                color=results_df['composite_score'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Composite Score")
            ),
            hovertemplate="<b>%{text}</b><br>" +
                         "Volatility: %{x:.2%}<br>" +
                         "Score: %{y:.1f}<br>" +
                         "<extra></extra>"
        ))
        
        fig.update_layout(
            title="Risk-Return Profile",
            xaxis_title="Volatility (Risk)",
            yaxis_title="Composite Score (Return Potential)",
            showlegend=False,
            width=800,
            height=600
        )
        
        # Add quadrant lines and labels if enough data exists
        if not results_df.empty and len(results_df) > 1:
            median_vol = results_df['volatility'].median()
            median_score = results_df['composite_score'].median()

            fig.add_hline(y=median_score, line_dash="dash", line_color="gray")
            fig.add_vline(x=median_vol, line_dash="dash", line_color="gray")

            # Quadrant label positions
            vol_min = results_df['volatility'].min()
            vol_max = results_df['volatility'].max()
            score_min = results_df['composite_score'].min()
            score_max = results_df['composite_score'].max()

            quadrant_annotations = [
                (vol_min,       score_max * 0.97, "Sweet Spot",            "green"),
                (median_vol * 1.02, score_max * 0.97, "High Risk / High Reward", "orange"),
                (vol_min,       score_min * 1.04, "Safe but Slow",          "#1f77b4"),
                (median_vol * 1.02, score_min * 1.04, "Avoid",             "#dc3545"),
            ]
            for ax, ay, text, color in quadrant_annotations:
                fig.add_annotation(
                    x=ax, y=ay, text=text, showarrow=False,
                    font=dict(color=color, size=11), opacity=0.65,
                    xanchor="left",
                )

        return fig
    
    def create_score_distribution(self, results_df: pd.DataFrame) -> go.Figure:
        """Create distribution plots for strategy scores"""
        # Check if DataFrame is empty
        if results_df.empty:
            return None
        
        score_columns = [col for col in results_df.columns if col.endswith('_score')]
        
        if not score_columns:
            return None
        
        fig = go.Figure()
        
        for i, col in enumerate(score_columns):
            strategy_name = col.replace('_score', '').title()
            
            # Skip if no valid data for this column
            if results_df[col].dropna().empty:
                continue
            
            fig.add_trace(go.Box(
                y=results_df[col],
                name=strategy_name,
                boxpoints='outliers',
                jitter=0.3,
                pointpos=-1.8,
                marker=dict(color=self.color_scheme[i % len(self.color_scheme)])
            ))
        
        fig.update_layout(
            title="Strategy Score Distributions",
            yaxis_title="Score",
            showlegend=False,
            width=1000,
            height=600
        )
        
        return fig
    
    def create_top_stocks_bar(self, results_df: pd.DataFrame, n_stocks: int = 10) -> go.Figure:
        """Create bar chart of top stocks by composite score"""
        top_stocks = results_df.nlargest(n_stocks, 'composite_score')
        
        fig = go.Figure(data=[
            go.Bar(
                x=top_stocks.index,
                y=top_stocks['composite_score'],
                marker_color=self.color_scheme[0],
                text=top_stocks['composite_score'].round(1),
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title=f"Top {n_stocks} Stocks by Composite Score",
            xaxis_title="Stock",
            yaxis_title="Composite Score",
            showlegend=False,
            width=800,
            height=500
        )
        
        return fig
    
    def create_factor_contribution(self, results_df: pd.DataFrame, ticker: str) -> go.Figure:
        """Create waterfall chart showing factor contributions to composite score"""
        if ticker not in results_df.index:
            return go.Figure()
        
        stock_data = results_df.loc[ticker]
        score_columns = [col for col in results_df.columns if col.endswith('_score')]
        
        # Prepare data for waterfall
        factors = []
        values = []
        
        # Start with base (average of all stocks)
        base_score = results_df['composite_score'].mean()
        factors.append("Market Average")
        values.append(base_score)
        
        # Add each factor contribution
        for col in score_columns:
            factor_name = col.replace('_score', '').title()
            avg_factor = results_df[col].mean()
            stock_factor = stock_data[col]
            contribution = stock_factor - avg_factor
            
            factors.append(factor_name)
            values.append(contribution)
        
        # Add final score
        factors.append("Final Score")
        values.append(stock_data['composite_score'] - sum(values[1:]) - base_score)
        
        # Create waterfall chart
        fig = go.Figure(go.Waterfall(
            name="Score Contribution",
            orientation="v",
            measure=["absolute"] + ["relative"] * (len(factors) - 2) + ["total"],
            x=factors,
            y=values,
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        
        fig.update_layout(
            title=f"Score Composition for {ticker}",
            showlegend=True,
            width=800,
            height=500
        )
        
        return fig
    
    def create_performance_trend(self, price_data: Dict[str, pd.DataFrame], ticker: str) -> go.Figure:
        """Create price trend chart with technical indicators"""
        if ticker not in price_data or price_data[ticker].empty:
            return go.Figure().add_annotation(text="Price data not available")
        
        df = price_data[ticker].copy()
        
        # Calculate indicators
        df['SMA_50'] = df['Close'].rolling(50).mean()
        df['SMA_200'] = df['Close'].rolling(200).mean()
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Middle'] + 2 * df['BB_Std']
        df['BB_Lower'] = df['BB_Middle'] - 2 * df['BB_Std']
        
        # Create candlestick chart
        fig = go.Figure()
        
        # Add candlestick
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price'
        ))
        
        # Add moving averages
        fig.add_trace(go.Scatter(
            x=df.index, y=df['SMA_50'],
            name='SMA 50',
            line=dict(color='blue', width=1)
        ))
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['SMA_200'],
            name='SMA 200',
            line=dict(color='red', width=1)
        ))
        
        # Add Bollinger Bands
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Upper'],
            name='BB Upper',
            line=dict(color='gray', width=1, dash='dash')
        ))
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Lower'],
            name='BB Lower',
            line=dict(color='gray', width=1, dash='dash'),
            fill='tonexty',
            fillcolor='rgba(68, 68, 68, 0.1)'
        ))
        
        fig.update_layout(
            title=f"{ticker} Price Chart with Technical Indicators",
            yaxis_title="Price",
            xaxis_title="Date",
            xaxis_rangeslider_visible=False,
            width=1000,
            height=600
        )
        
        return fig