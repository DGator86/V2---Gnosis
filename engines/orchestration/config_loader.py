"""
Configuration loader engine
Handles loading and validation of config.yaml
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigEngine:
    """Engine for loading and managing configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to config/config.yaml relative to project root
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value using dot notation
        Example: config.get("engines.hedge.polars_threads", 4)
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set config value using dot notation"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self, path: Optional[str] = None):
        """Save configuration back to file"""
        save_path = Path(path) if path else self.config_path
        with open(save_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
    
    @property
    def runtime(self) -> Dict[str, Any]:
        return self._config.get('runtime', {})
    
    @property
    def engines(self) -> Dict[str, Any]:
        return self._config.get('engines', {})
    
    @property
    def agents(self) -> Dict[str, Any]:
        return self._config.get('agents', {})
    
    @property
    def lookahead(self) -> Dict[str, Any]:
        return self._config.get('lookahead', {})
    
    @property
    def tracking(self) -> Dict[str, Any]:
        return self._config.get('tracking', {})
    
    @property
    def feedback(self) -> Dict[str, Any]:
        return self._config.get('feedback', {})
    
    @property
    def security(self) -> Dict[str, Any]:
        return self._config.get('security', {})
    
    @property
    def memory(self) -> Dict[str, Any]:
        return self._config.get('memory', {})
    
    @property
    def adapters(self) -> Dict[str, Any]:
        return self._config.get('adapters', {})


# Global config instance
_config_instance: Optional[ConfigEngine] = None


def get_config(config_path: Optional[str] = None) -> ConfigEngine:
    """Get or create global config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigEngine(config_path)
    return _config_instance
