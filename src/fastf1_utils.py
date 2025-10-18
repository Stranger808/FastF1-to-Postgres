# -*- coding: utf-8 -*-
"""
Created on Wed Aug 13 10:08:49 2025

@author: bradl
"""

import logging
import warnings

class CriticalMessageHandler(logging.Handler):
    """Custom handler that raises exceptions for specific log messages"""
    
    def __init__(self, critical_messages=None, exception_type=RuntimeError):
        super().__init__()
        self.critical_messages = critical_messages or []
        self.exception_type = exception_type
    
    def emit(self, record):
        message = record.getMessage()
        for critical_msg in self.critical_messages:
            if critical_msg in message:
                raise self.exception_type(f"{critical_msg} (Logger: {record.name})")

def setup_critical_warning_handler(logger_name, critical_messages, 
                                 exception_type=RuntimeError, 
                                 log_level=logging.WARNING):
    """
    Set up a handler that raises exceptions for specific log messages
    
    Args:
        logger_name (str): Name of the logger to monitor
        critical_messages (list): List of message strings that should raise exceptions
        exception_type (Exception): Type of exception to raise (default: RuntimeError)
        log_level (int): Log level to monitor (default: logging.WARNING)
    
    Returns:
        logging.Handler: The handler that was added (for removal if needed)
    """
    logger = logging.getLogger(logger_name)
    
    # Create and configure the critical handler
    critical_handler = CriticalMessageHandler(critical_messages, exception_type)
    critical_handler.setLevel(log_level)
    
    # Add to logger
    logger.addHandler(critical_handler)
    
    return critical_handler

def setup_critical_warnings_handler(critical_messages, exception_type=RuntimeError):
    """
    Set up a handler for Python warnings module
    
    Args:
        critical_messages (list): List of message strings that should raise exceptions
        exception_type (Exception): Type of exception to raise (default: RuntimeError)
    """
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        message_str = str(message)
        
        for critical_msg in critical_messages:
            if critical_msg in message_str:
                raise exception_type(f"{critical_msg} (from {filename}:{lineno})")
        
        # If not critical, just issue the warning normally
        warnings._showwarning_orig(message, category, filename, lineno, file, line)
    
    # Store original handler
    if not hasattr(warnings, '_showwarning_orig'):
        warnings._showwarning_orig = warnings.showwarning
    
    warnings.showwarning = warning_handler

def remove_critical_handler(logger_name, handler):
    """Remove a critical handler from a logger"""
    logger = logging.getLogger(logger_name)
    logger.removeHandler(handler)

def setup_logger_with_file(logger_name, log_file, log_level=logging.DEBUG):
    """
    Set up a logger with file output
    
    Args:
        logger_name (str): Name of the logger
        log_file (str): Path to log file
        log_level (int): Logging level
    
    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.propagate = False
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger