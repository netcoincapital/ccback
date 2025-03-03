import logging
import os
from datetime import datetime

def get_log_directory():
    """
    Create and return the log directory path for the current date
    
    Returns:
        str: Path to the log directory for today
    """
    # Create main Logs directory
    logs_dir = os.path.join(os.getcwd(), "Logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create date-specific directory
    today = datetime.now().strftime('%Y-%m-%d')
    today_dir = os.path.join(logs_dir, today)
    os.makedirs(today_dir, exist_ok=True)
    
    return today_dir

def setup_logger(name, level=logging.INFO):
    """
    Set up a logger with file and console handlers
    
    Args:
        name (str): Logger name (typically the module name without extension)
        level (int, optional): Logging level. Defaults to logging.INFO.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers = []
    
    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    log_dir = get_log_directory()
    log_file = os.path.join(log_dir, f"{name}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(module_path):
    """
    Get a logger for a module based on its file path
    
    Args:
        module_path (str): Full path of the module
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Extract module name without extension
    module_name = os.path.basename(module_path)
    if module_name.endswith('.py'):
        module_name = module_name[:-3]  # Remove .py extension
    
    return setup_logger(module_name, logging.DEBUG) 