"""
Logging engine for DHPE pipeline
Centralized logging with structured output
"""
import logging
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime


class LoggerEngine:
    """Engine for centralized logging"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str, level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
        """Get or create a logger with the specified configuration"""
        
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper()))
        logger.propagate = False
        
        # Remove existing handlers
        logger.handlers = []
        
        # Console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)  # Always debug to file
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def setup_pipeline_logging(cls, level: str = "INFO", log_dir: str = "logs") -> dict:
        """Set up logging for all pipeline components"""
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        loggers = {
            'main': cls.get_logger('dhpe.main', level, f"{log_dir}/main_{timestamp}.log"),
            'orchestration': cls.get_logger('dhpe.orchestration', level, f"{log_dir}/orchestration_{timestamp}.log"),
            'engines': cls.get_logger('dhpe.engines', level, f"{log_dir}/engines_{timestamp}.log"),
            'agents': cls.get_logger('dhpe.agents', level, f"{log_dir}/agents_{timestamp}.log"),
            'tracking': cls.get_logger('dhpe.tracking', level, f"{log_dir}/tracking_{timestamp}.log"),
            'feedback': cls.get_logger('dhpe.feedback', level, f"{log_dir}/feedback_{timestamp}.log"),
        }
        
        return loggers


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Convenience function to get a logger"""
    return LoggerEngine.get_logger(name, level)
