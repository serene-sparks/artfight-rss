#!/usr/bin/env python3
"""Test script to verify proper shutdown handling."""

import asyncio
import signal
import sys
import time
from pathlib import Path

# Add the artfight_feed directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "artfight_feed"))

from artfight_feed.logging_config import setup_logging, get_logger


async def test_shutdown():
    """Test shutdown handling."""
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Starting shutdown test...")
    logger.info("Press Ctrl+C to test shutdown handling")
    
    # Simulate a long-running task
    try:
        for i in range(100):
            logger.info(f"Test iteration {i+1}/100")
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Task cancelled, shutting down gracefully...")
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down gracefully...")
    
    logger.info("Shutdown test completed")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🧪 Testing Shutdown Handling")
    print("=" * 40)
    print("This script will run for 100 seconds or until Ctrl+C is pressed.")
    print("Press Ctrl+C to test graceful shutdown...")
    print()
    
    try:
        asyncio.run(test_shutdown())
    except KeyboardInterrupt:
        print("\n✅ Shutdown test completed successfully!")
    except Exception as e:
        print(f"\n❌ Shutdown test failed: {e}")
        sys.exit(1)
`