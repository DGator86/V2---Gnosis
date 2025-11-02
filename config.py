"""
Configuration module for Gnosis DHPE system.
Loads environment variables and provides configuration dictionaries.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for API credentials and system parameters."""
    
    # Git API
    GIT_API_TOKEN = os.getenv('GIT_API_TOKEN')
    GIT_USERNAME = os.getenv('GIT_USERNAME')
    
    # ChatGPT API
    CHATGPT_API_KEY = os.getenv('CHATGPT_API_KEY')
    
    # Google Cloud API
    GOOGLE_CLOUD_API_KEY = os.getenv('GOOGLE_CLOUD_API_KEY')
    
    # N8n API
    N8N_API_KEY = os.getenv('N8N_API_KEY')
    
    # Alpaca API
    ALPACA_API_URL = os.getenv('ALPACA_API_URL', 'https://paper-api.alpaca.markets/v2')
    ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
    ALPACA_API_SECRET = os.getenv('ALPACA_API_SECRET')
    
    # Public Secret Key
    PUBLIC_SECRET_KEY = os.getenv('PUBLIC_SECRET_KEY')
    
    # DHPE System Configuration
    DHPE_CONFIG = {
        'kernel': {
            'kappa': 0.1,  # Screening parameter for Green's function
        },
        'weights': {
            'alpha_G': 1.0,   # Gamma weight
            'alpha_V': 0.5,   # Vanna weight
            'alpha_C': 0.3,   # Charm weight
        },
        'projector': {
            'mode': 'sticky-delta',
            'bins': 50,
        },
        'liquidity': {
            'span': 20,  # EWMA span for Amihud estimation
        },
    }


def get_alpaca_config():
    """Returns Alpaca API configuration dictionary."""
    return {
        'base_url': Config.ALPACA_API_URL,
        'key_id': Config.ALPACA_API_KEY,
        'secret_key': Config.ALPACA_API_SECRET,
    }


def get_dhpe_config():
    """Returns DHPE system configuration dictionary."""
    return Config.DHPE_CONFIG
