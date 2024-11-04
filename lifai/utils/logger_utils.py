import logging

def get_module_logger(module_name: str) -> logging.Logger:
    """Get a logger instance for the module with proper formatting."""
    logger = logging.getLogger(module_name)
    return logger 