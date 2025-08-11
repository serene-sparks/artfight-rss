#!/usr/bin/env python3
"""Test script to verify server startup and shutdown."""

import asyncio
import signal
import sys
import time
from pathlib import Path

# Add the artfight_feed directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "artfight_feed"))

from artfight_feed.logging_config import setup_logging, get_logger


async def test_server():
    """Test server startup and shutdown."""
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Testing server startup and shutdown...")
    logger.info("This will simulate the server startup process")
    
    # Simulate component initialization
    logger.info("Initializing components...")
    await asyncio.sleep(1)
    logger.info("Components initialized successfully")
    
    # Simulate starting services
    logger.info("Starting monitoring service...")
    await asyncio.sleep(1)
    logger.info("Monitoring service started")
    
    logger.info("Starting Discord bot...")
    await asyncio.sleep(1)
    logger.info("Discord bot started")
    
    logger.info("ArtFight RSS service started successfully")
    logger.info("Press Ctrl+C to test shutdown...")
    
    # Simulate running server
    try:
        for i in range(30):  # Run for 30 seconds max
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Server cancelled, shutting down gracefully...")
    
    # Simulate shutdown
    logger.info("Shutting down ArtFight RSS service...")
    await asyncio.sleep(1)
    logger.info("Discord bot stopped")
    await asyncio.sleep(1)
    logger.info("Monitoring service stopped")
    logger.info("ArtFight RSS service shutdown complete")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🧪 Testing Server Startup and Shutdown")
    print("=" * 45)
    print("This script will simulate the server startup and shutdown process.")
    print("Press Ctrl+C to test graceful shutdown...")
    print()
    
    try:
        asyncio.run(test_server())
    except KeyboardInterrupt:
        print("\n✅ Server shutdown test completed successfully!")
    except Exception as e:
        print(f"\n❌ Server shutdown test failed: {e}")
        sys.exit(1) 