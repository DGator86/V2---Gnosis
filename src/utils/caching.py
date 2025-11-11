"""
Caching utilities.
Simple in-memory and Redis-backed caching.
"""

from typing import Any, Optional, Callable
from functools import wraps
import hashlib
import json


# Simple in-memory cache
_memory_cache = {}


def cache_in_memory(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    """
    Store value in memory cache.
    
    Parameters
    ----------
    key : str
        Cache key
    value : Any
        Value to cache
    ttl_seconds : int, optional
        Time to live (not implemented in simple version)
    """
    _memory_cache[key] = value


def get_from_memory(key: str) -> Optional[Any]:
    """
    Retrieve value from memory cache.
    
    Parameters
    ----------
    key : str
        Cache key
        
    Returns
    -------
    Any or None
        Cached value or None if not found
    """
    return _memory_cache.get(key)


def clear_memory_cache() -> None:
    """Clear all memory cache."""
    _memory_cache.clear()


def cached(ttl_seconds: int = 300):
    """
    Decorator to cache function results.
    
    Parameters
    ----------
    ttl_seconds : int
        Time to live in seconds (default 300 = 5 minutes)
        
    Returns
    -------
    decorator
        Caching decorator
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_data = {
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            key_str = json.dumps(key_data, sort_keys=True)
            cache_key = hashlib.md5(key_str.encode()).hexdigest()
            
            # Check cache
            cached_value = get_from_memory(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache_in_memory(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    
    return decorator


class RedisCache:
    """
    Redis-backed cache (placeholder for production use).
    """
    
    def __init__(self, host: str = 'localhost', port: int = 6379):
        """
        Initialize Redis connection.
        
        Parameters
        ----------
        host : str
            Redis host
        port : int
            Redis port
        """
        self.host = host
        self.port = port
        # In production: import redis; self.client = redis.Redis(host=host, port=port)
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in Redis."""
        # Placeholder: self.client.set(key, json.dumps(value), ex=ttl_seconds)
        pass
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        # Placeholder: return json.loads(self.client.get(key))
        return None
    
    def delete(self, key: str) -> None:
        """Delete key from Redis."""
        # Placeholder: self.client.delete(key)
        pass
