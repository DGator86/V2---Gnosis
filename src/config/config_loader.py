"""
Configuration loader for YAML settings.
"""

import yaml
import os
from typing import Dict, Any


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Parameters
    ----------
    config_path : str, optional
        Path to config file (defaults to src/config/settings.yaml)
        
    Returns
    -------
    dict
        Configuration dictionary
    """
    if config_path is None:
        # Default to settings.yaml in same directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'settings.yaml')
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_engine_config(config: Dict[str, Any], engine_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific engine.
    
    Parameters
    ----------
    config : dict
        Full configuration
    engine_name : str
        Engine name (e.g., 'hedge', 'liquidity', 'sentiment')
        
    Returns
    -------
    dict
        Engine-specific configuration
    """
    return config.get('engines', {}).get(engine_name, {})


def get_risk_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get risk management configuration.
    
    Parameters
    ----------
    config : dict
        Full configuration
        
    Returns
    -------
    dict
        Risk configuration
    """
    return config.get('risk', {})


def get_agent_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get agent configuration.
    
    Parameters
    ----------
    config : dict
        Full configuration
        
    Returns
    -------
    dict
        Agent configuration
    """
    return config.get('agents', {})
