"""
Session State Manager for SmartStock
Provides robust handling of session state with type validation
"""

import streamlit as st
from typing import Any, Dict, Optional, List, Union
import logging

logger = logging.getLogger("SmartStock")

class SessionStateManager:
    """Robust session state management with type validation"""
    
    @staticmethod
    def initialize_strategy_params():
        """Ensure strategy_params exists and has correct structure"""
        if 'strategy_params' not in st.session_state:
            st.session_state.strategy_params = {}
    
    @staticmethod
    def get_param_value(strategy: str, param_name: str, default_value: float) -> float:
        """
        Safely retrieve parameter value with type checking
        
        Parameters:
        -----------
        strategy : str
            Strategy name
        param_name : str
            Parameter name
        default_value : float
            Default value to return if parameter doesn't exist or is invalid
            
        Returns:
        --------
        float
            Parameter value or default if not found/invalid
        """
        try:
            SessionStateManager.initialize_strategy_params()
            
            # Check if strategy exists
            if strategy not in st.session_state.strategy_params:
                return default_value
                
            # Check if parameter exists
            if param_name not in st.session_state.strategy_params[strategy]:
                return default_value
                
            # Get stored value
            value = st.session_state.strategy_params[strategy][param_name]
            
            # Type check and conversion
            if isinstance(value, (list, tuple, dict)):
                # If it's not a numeric type, use default
                logger.warning(f"Parameter {strategy}.{param_name} has invalid type {type(value)}, using default")
                return default_value
                
            # Try numeric conversion
            try:
                numeric_value = float(value)
                return numeric_value
            except (ValueError, TypeError):
                logger.warning(f"Parameter {strategy}.{param_name} could not be converted to float")
                return default_value
                
        except Exception as e:
            # Fall back to default on any error
            logger.error(f"Error getting param {strategy}.{param_name}: {str(e)}")
            return default_value
    
    @staticmethod        
    def set_param_value(strategy: str, param_name: str, value: Any):
        """
        Safely store parameter value with type validation
        
        Parameters:
        -----------
        strategy : str
            Strategy name
        param_name : str
            Parameter name
        value : Any
            Value to store (will be converted to float)
        """
        SessionStateManager.initialize_strategy_params()
        
        # Ensure strategy exists
        if strategy not in st.session_state.strategy_params:
            st.session_state.strategy_params[strategy] = {}
            
        # Store value with type validation
        try:
            # Ensure value is numeric
            numeric_value = float(value)
            st.session_state.strategy_params[strategy][param_name] = numeric_value
        except (ValueError, TypeError):
            # Skip storing invalid values
            logger.error(f"Error storing invalid param value for {strategy}.{param_name}: {value}")
            pass
    
    @staticmethod
    def reset_all_params():
        """Reset all parameters to defaults"""
        if 'strategy_params' in st.session_state:
            del st.session_state.strategy_params
        
        # Also remove any widgets with param_ prefix
        keys_to_remove = [k for k in st.session_state.keys() if k.startswith('param_')]
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
                
        logger.info("All parameters reset to defaults")
    
    @staticmethod
    def get_strategy_params(strategy: str) -> Dict[str, float]:
        """
        Get all parameters for a strategy
        
        Parameters:
        -----------
        strategy : str
            Strategy name
            
        Returns:
        --------
        Dict[str, float]
            Dictionary of parameter name to value
        """
        SessionStateManager.initialize_strategy_params()
        
        if strategy not in st.session_state.strategy_params:
            return {}
            
        return st.session_state.strategy_params[strategy]
    
    @staticmethod
    def set_strategy_params(strategy: str, params: Dict[str, Any]):
        """
        Set all parameters for a strategy
        
        Parameters:
        -----------
        strategy : str
            Strategy name
        params : Dict[str, Any]
            Dictionary of parameter name to value
        """
        SessionStateManager.initialize_strategy_params()
        
        st.session_state.strategy_params[strategy] = {}
        
        # Validate and store each parameter
        for param_name, value in params.items():
            SessionStateManager.set_param_value(strategy, param_name, value)
    
    @staticmethod
    def debug_session_state():
        """
        Display debug information about session state
        """
        st.header("Session State Debug")
        
        with st.expander("Raw Session State"):
            # Filter out large objects
            filtered_state = {}
            for key, value in st.session_state.items():
                if key in ['analysis_results', 'backtest_results']:
                    filtered_state[key] = f"<{type(value).__name__} object>"
                else:
                    filtered_state[key] = value
                    
            st.json(filtered_state)
        
        # Show types of each parameter value
        st.subheader("Parameter Value Types")
        
        parameter_types = {}
        for key, value in st.session_state.items():
            if key.startswith('param_'):
                parameter_types[key] = {
                    "type": type(value).__name__,
                    "value": str(value)
                }
        
        if parameter_types:
            st.json(parameter_types)
        else:
            st.info("No parameter values found in session state")
        
        # Show strategy_params structure
        st.subheader("Strategy Parameters")
        
        if 'strategy_params' in st.session_state:
            # Convert all values to strings for display
            pretty_params = {}
            for strategy, params in st.session_state.strategy_params.items():
                pretty_params[strategy] = {}
                for param_name, value in params.items():
                    pretty_params[strategy][param_name] = {
                        "type": type(value).__name__,
                        "value": str(value)
                    }
            
            st.json(pretty_params)
        else:
            st.info("No strategy_params found in session state")
    
    @staticmethod
    def check_for_parameter_errors() -> bool:
        """
        Check for parameter errors and provide recovery options
        
        Returns:
        --------
        bool
            True if errors were found, False otherwise
        """
        error_found = False
        error_details = []
        
        # Check for list-type parameters (which cause slider errors)
        for key, value in st.session_state.items():
            if key.startswith('param_') and isinstance(value, (list, tuple, dict)):
                error_found = True
                error_details.append(f"Parameter '{key}' has invalid type: {type(value).__name__}")
        
        # Check strategy_params for invalid types
        if 'strategy_params' in st.session_state:
            for strategy, params in st.session_state.strategy_params.items():
                if not isinstance(params, dict):
                    error_found = True
                    error_details.append(f"Strategy '{strategy}' parameters has invalid type: {type(params).__name__}")
                    continue
                    
                for param_name, value in params.items():
                    try:
                        # Try to convert to float
                        float(value)
                    except (ValueError, TypeError):
                        error_found = True
                        error_details.append(f"Parameter '{strategy}.{param_name}' has invalid value: {value} ({type(value).__name__})")
        
        if error_found:
            st.error("⚠️ Parameter type errors detected:")
            for detail in error_details:
                st.write(f"- {detail}")
                
            if st.button("🔄 Reset Parameters Now", key="error_reset_button"):
                SessionStateManager.reset_all_params()
                st.success("Parameters reset successfully!")
                st.rerun()
        
        return error_found
