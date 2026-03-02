"""SmartStock: Troubleshooting Page
Provides utility tools for fixing common issues
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
from pathlib import Path

# Import the SessionStateManager
from utils.session_state_manager import SessionStateManager

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def troubleshooting_page():
    """Troubleshooting page with utility tools"""
    st.title("🔧 SmartStock Troubleshooting")
    
    st.markdown("""
    This page provides tools to fix common issues with SmartStock. 
    Use these options only if you're experiencing problems with the application.
    """)
    
    # Reset all strategy parameters
    st.header("Reset Strategy Parameters")
    
    st.warning("""
    **⚠️ Warning:** This will reset all strategy parameters to their default values. 
    Use this if you're experiencing errors with parameter values or seeing error messages 
    about type mismatches with sliders.
    """)
    
    # First check for parameter errors
    has_errors = SessionStateManager.check_for_parameter_errors()
    
    if not has_errors:
        st.success("No parameter errors detected.")
    
    if st.button("🔄 Reset All Parameters", type="primary", key="reset_params_button"):
        # Use the SessionStateManager to reset parameters
        SessionStateManager.reset_all_params()
        
        st.success("✅ All parameters have been reset successfully.")
        st.info("Return to the Screening page to continue using the application.")
    
    # Reset user preferences
    st.header("Reset User Preferences")
    
    st.warning("""
    **⚠️ Warning:** This will reset all user preferences to their default values.
    Use this if you're experiencing issues with saved preferences.
    """)
    
    if st.button("🔄 Reset User Preferences", type="primary"):
        if 'user_preferences' in st.session_state:
            del st.session_state.user_preferences
        
        # Also delete the preferences file if it exists
        prefs_file = '.streamlit/user_prefs.json'
        if os.path.exists(prefs_file):
            try:
                os.remove(prefs_file)
                st.success("✅ User preferences file deleted successfully.")
            except Exception as e:
                st.error(f"Error deleting preferences file: {str(e)}")
        
        st.success("✅ User preferences have been reset successfully.")
        st.info("Return to the Settings page to configure your preferences again.")
    
    # Clear all session state
    st.header("Reset Everything (Last Resort)")
    
    st.error("""
    **⚠️ DANGER ZONE ⚠️**
    
    This will reset ALL session state variables and effectively restart the application.
    Use this as a last resort if nothing else is working.
    """)
    
    danger_checkbox = st.checkbox("I understand this will reset everything")
    
    if danger_checkbox and st.button("⚠️ Reset All Session State", type="primary"):
        # Clear all session state variables
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.success("✅ All session state has been reset successfully.")
        st.info("Refresh the page to start fresh.")
    
    # Application information
    st.header("Application Information")
    
    st.markdown("""
    ### SmartStock Version
    Version: 1.0 MVP
    
    ### System Information
    - Python Version: {python_version}
    - Streamlit Version: {streamlit_version}
    
    ### Contact Support
    If you continue experiencing issues, please contact support or file an issue on the project repository.
    """.format(
        python_version=".".join(map(str, sys.version_info[:3])),
        streamlit_version=st.__version__
    ))
    
    # Add session state debugging
    st.header("Session State Debugging")
    st.info("This section provides advanced debugging information about the application state.")
    
    if st.button("Debug Session State", key="debug_button"):
        # Use the SessionStateManager to show debug info
        SessionStateManager.debug_session_state()
    
if __name__ == "__main__":
    troubleshooting_page()
