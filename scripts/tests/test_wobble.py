#!/usr/bin/env python3
"""Test script for configurable wobble functionality."""

import asyncio
import os
import random
import sys

# Add the artfight_rss directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_rss'))

from artfight_rss.config import settings


async def test_wobble():
    """Test the configurable wobble functionality."""
    print("Testing configurable wobble functionality...")
    print("Current settings:")
    print(f"  page_request_delay: {settings.page_request_delay_sec} seconds")
    print(f"  page_request_wobble: {settings.page_request_wobble} (±{settings.page_request_wobble*100:.0f}%)")

    # Test different wobble settings
    test_configs = [
        (3.0, 0.0),   # No wobble
        (3.0, 0.1),   # ±10% wobble
        (3.0, 0.2),   # ±20% wobble
        (3.0, 0.5),   # ±50% wobble
    ]

    for base_delay, wobble in test_configs:
        print(f"\nTesting with base_delay={base_delay}s, wobble={wobble} (±{wobble*100:.0f}%):")

        delays = []
        for i in range(5):
            if wobble > 0:
                min_factor = 1.0 - wobble
                max_factor = 1.0 + wobble
                wobble_factor = random.uniform(min_factor, max_factor)
                actual_delay = base_delay * wobble_factor
            else:
                actual_delay = base_delay
                wobble_factor = 1.0

            delays.append(actual_delay)
            print(f"  Request {i+1}: {actual_delay:.2f}s (factor: {wobble_factor:.2f})")

        avg_delay = sum(delays) / len(delays)
        min_delay = min(delays)
        max_delay = max(delays)
        print(f"  Range: {min_delay:.2f}s - {max_delay:.2f}s (avg: {avg_delay:.2f}s)")

    print("\n✅ Wobble functionality test completed!")


if __name__ == "__main__":
    asyncio.run(test_wobble())
