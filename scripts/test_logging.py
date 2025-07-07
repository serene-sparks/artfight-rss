#!/usr/bin/env python3
"""Test script for the new logging configuration."""

import os
import sys
from pathlib import Path

# Add the artfight_rss directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'artfight_rss'))

from artfight_rss.logging_config import setup_logging, get_logger


def test_logging():
    """Test the new logging configuration."""
    print("🧪 Testing New Logging Configuration")
    print("=" * 50)

    # Set up logging
    setup_logging()
    
    # Get loggers for different modules
    main_logger = get_logger("artfight_rss.main")
    artfight_logger = get_logger("artfight_rss.artfight")
    monitor_logger = get_logger("artfight_rss.monitor")
    discord_logger = get_logger("artfight_rss.discord_bot")
    
    print("\n📝 Testing different log levels:")
    print("-" * 30)
    
    # Test different log levels
    main_logger.debug("This is a DEBUG message from main module")
    main_logger.info("This is an INFO message from main module")
    main_logger.warning("This is a WARNING message from main module")
    main_logger.error("This is an ERROR message from main module")
    
    artfight_logger.debug("This is a DEBUG message from artfight module")
    artfight_logger.info("This is an INFO message from artfight module")
    artfight_logger.warning("This is a WARNING message from artfight module")
    
    monitor_logger.info("This is an INFO message from monitor module")
    monitor_logger.warning("This is a WARNING message from monitor module")
    
    discord_logger.info("This is an INFO message from discord_bot module")
    discord_logger.error("This is an ERROR message from discord_bot module")
    
    print("\n✅ Logging test completed!")
    print("\n📁 Check the following log files:")
    print(f"  - {Path('logs/artfight-rss.log')}")
    print(f"  - {Path('logs/artfight-rss-error.log')}")
    
    print("\n🔍 The logs should show:")
    print("  - Timestamp in format: YYYY-MM-DD HH:MM:SS")
    print("  - Module name and line number (in debug mode)")
    print("  - Log level (DEBUG, INFO, WARNING, ERROR)")
    print("  - Message content")
    print("  - Different log levels for different modules")


if __name__ == "__main__":
    test_logging() 