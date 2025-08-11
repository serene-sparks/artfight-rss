#!/usr/bin/env python3
"""Test script for automatic cookie refresh functionality."""

import asyncio
import logging
import os
import sys

# Add the artfight_feed directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_feed'))

from artfight_feed.artfight import ArtFightClient
from artfight_feed.cache import RateLimiter
from artfight_feed.config import settings
from artfight_feed.database import ArtFightDatabase


async def test_cookie_refresh():
    """Test the automatic cookie refresh functionality."""
    # Set up logging to see debug messages
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    print("Testing automatic cookie refresh functionality...")
    print("=" * 60)

    # Initialize components

    # Use permanent database path from config
    database = ArtFightDatabase(settings.db_path)
    rate_limiter = RateLimiter(database, 60)  # 60 second interval

    # Create ArtFight client
    client = ArtFightClient(rate_limiter, database)

    try:
        # Show initial authentication info
        print("\nInitial authentication info:")
        auth_info = client.get_authentication_info()
        print(f"  Laravel session: {auth_info['current_cookies']['laravel_session']}")
        print(f"  CF clearance: {auth_info['current_cookies']['cf_clearance']}")

        # Test with a known username
        username = "fourleafisland"

        print(f"\nTesting attacks for user: {username}")
        print("-" * 40)

        # Get attacks
        attacks = await client.get_user_attacks(username)
        print(f"Found {len(attacks)} attacks")

        # Show updated authentication info
        print("\nUpdated authentication info after attacks request:")
        auth_info = client.get_authentication_info()
        print(f"  Laravel session: {auth_info['current_cookies']['laravel_session']}")
        print(f"  CF clearance: {auth_info['current_cookies']['cf_clearance']}")

        print(f"\nTesting defenses for user: {username}")
        print("-" * 40)

        # Get defenses
        defenses = await client.get_user_defenses(username)
        print(f"Found {len(defenses)} defenses")

        # Show final authentication info
        print("\nFinal authentication info after defenses request:")
        auth_info = client.get_authentication_info()
        print(f"  Laravel session: {auth_info['current_cookies']['laravel_session']}")
        print(f"  CF clearance: {auth_info['current_cookies']['cf_clearance']}")

    except Exception as e:
        print(f"Error testing cookie refresh: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_cookie_refresh())
