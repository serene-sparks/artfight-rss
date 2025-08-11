"""Logging configuration for the ArtFight RSS service."""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

from .config import settings


def setup_logging() -> None:
    """Set up logging configuration following FastAPI best practices."""
    
    # Define log levels based on debug setting
    if settings.debug:
        root_level = "DEBUG"
        artfight_level = "DEBUG"
        http_level = "DEBUG"
        uvicorn_level = "INFO"
    else:
        root_level = "INFO"
        artfight_level = "INFO"
        http_level = "WARNING"
        uvicorn_level = "WARNING"

    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Logging configuration dictionary
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(client_addr)s - %(request_line)s - %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "detailed" if settings.debug else "default",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": logs_dir / "artfight-feed.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": logs_dir / "artfight-feed-error.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "level": "ERROR",
            },
        },
        "loggers": {
            # Root logger
            "": {
                "handlers": ["console", "file", "error_file"],
                "level": root_level,
                "propagate": False,
            },
            # Application loggers
            "artfight_feed": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.artfight": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.database": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.cache": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.monitor": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.rss": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.discord_bot": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            "artfight_feed.config": {
                "handlers": ["console", "file", "error_file"],
                "level": artfight_level,
                "propagate": False,
            },
            # HTTP client loggers
            "httpx": {
                "handlers": ["console", "file"],
                "level": http_level,
                "propagate": False,
            },
            "httpcore": {
                "handlers": ["console", "file"],
                "level": http_level,
                "propagate": False,
            },
            # FastAPI and Uvicorn loggers
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": uvicorn_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": uvicorn_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console", "file", "error_file"],
                "level": uvicorn_level,
                "propagate": False,
            },
            "fastapi": {
                "handlers": ["console", "file"],
                "level": uvicorn_level,
                "propagate": False,
            },
            # Discord.py loggers
            "discord": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "discord.http": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
            "discord.gateway": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
            # SQLite loggers
            "sqlite3": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
            # Other third-party loggers
            "asyncio": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    # Apply the configuration
    logging.config.dictConfig(logging_config)

    # Log the configuration
    logger = logging.getLogger("artfight_feed")
    logger.info(f"Logging configured - Debug mode: {settings.debug}")
    logger.info(f"Log files: {logs_dir}/artfight-feed.log, {logs_dir}/artfight-feed-error.log")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name) 