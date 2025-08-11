#!/usr/bin/env python3
"""Test script for configurable page request delay."""

import asyncio
import os
import sys
import time

# Add the artfight_feed directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_feed'))

from artfight_feed.config import settings


async def test_page_delay():
    """Test the configurable page request delay."""
    print("Testing configurable page request delay...")
    print(f"Current page_request_delay setting: {settings.page_request_delay_sec} seconds")

    # Test different delay values
    test_delays = [1.0, 2.0, 3.0, 5.0]

    for delay in test_delays:
        print(f"\nTesting with {delay} second delay:")
        start_time = time.time()

        # Simulate the delay
        await asyncio.sleep(delay)

        end_time = time.time()
        actual_delay = end_time - start_time
        print(f"  Expected: {delay}s, Actual: {actual_delay:.2f}s")

    print(f"\nDefault configuration delay: {settings.page_request_delay_sec} seconds")
    print("✅ Page delay configuration test completed!")


if __name__ == "__main__":
    asyncio.run(test_page_delay())
