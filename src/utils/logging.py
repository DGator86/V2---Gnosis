"""
Logging utilities.
Structured logging for the framework.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup a logger with consistent formatting.
    
    Parameters
    ----------
    name : str
        Logger name
    level : str
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_file : str, optional
        Path to log file (if None, logs to console only)
        
    Returns
    -------
    logging.Logger
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Default framework logger
default_logger = setup_logger('gnosis')


def log_pipeline_step(step: str, symbol: str, message: str) -> None:
    """
    Log a pipeline step.
    
    Parameters
    ----------
    step : str
        Step name
    symbol : str
        Symbol being processed
    message : str
        Log message
    """
    default_logger.info(f"[{step}] {symbol}: {message}")


def log_error(error: Exception, context: str = "") -> None:
    """
    Log an error with context.
    
    Parameters
    ----------
    error : Exception
        Exception to log
    context : str
        Additional context
    """
    default_logger.error(f"{context}: {type(error).__name__}: {str(error)}", exc_info=True)
