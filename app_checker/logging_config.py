"""Logging configuration for App Update Checker."""

import logging
import sys
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_DATA_DIR

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (usually __name__).
        
    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> None:
    """Setup logging configuration.
    
    Args:
        level: Logging level (default: INFO).
        log_file: Optional log file path.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers,
    )
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


logger = get_logger(__name__)