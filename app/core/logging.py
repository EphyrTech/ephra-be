import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from app.core.config import settings

def setup_logging(log_dir: str = "logs"):
    """
    Configure application logging.
    
    Args:
        log_dir (str): Directory to store log files
        
    Returns:
        logging.Logger: Configured logger
    """
    # Create logs directory if it doesn't exist
    Path(log_dir).mkdir(exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Create separate loggers for different components
    api_logger = logging.getLogger("api")
    db_logger = logging.getLogger("db")
    auth_logger = logging.getLogger("auth")
    
    # Log startup message
    logger.info(f"Logging initialized. Level: {settings.LOG_LEVEL}")
    logger.info(f"Environment: {settings.ENV}")
    
    return logger

# Create a function to get a logger for a specific component
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific component.
    
    Args:
        name (str): Name of the component
        
    Returns:
        logging.Logger: Logger for the component
    """
    return logging.getLogger(name)
