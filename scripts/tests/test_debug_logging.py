#!/usr/bin/env python3
"""Test script for debug logging functionality."""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the artfight_rss directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_rss'))

from artfight_rss.artfight import ArtFightClient
from artfight_rss.cache import RateLimiter, SQLiteCache


async def test_debug_logging():
    """Test the debug logging functionality."""
    # Set up logging to see debug messages
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print("Testing debug logging functionality...")
    print("=" * 60)
    
    # Initialize components
    from pathlib import Path
    import tempfile
    
    # Create a temporary file for the cache
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        cache_path = Path(tmp.name)
    
    cache = SQLiteCache(cache_path)
    rate_limiter = RateLimiter(cache, 60)  # 60 second interval
    
    # Create ArtFight client
    client = ArtFightClient(cache, rate_limiter)
    
    try:
        # Test with a known username
        username = "fourleafisland"
        
        print(f"\nTesting attacks for user: {username}")
        print("-" * 40)
        
        # Get attacks
        attacks = await client.get_user_attacks(username)
        print(f"Found {len(attacks)} attacks")
        
        print(f"\nTesting defenses for user: {username}")
        print("-" * 40)
        
        # Get defenses
        defenses = await client.get_user_defenses(username)
        print(f"Found {len(defenses)} defenses")
        
        print(f"\nTesting team standings")
        print("-" * 40)
        
        # Get team standings
        standings = await client.get_team_standings()
        print(f"Found {len(standings)} team standings")
        
        print(f"\nTesting authentication info")
        print("-" * 40)
        
        # Get authentication info
        auth_info = client.get_authentication_info()
        print(f"Authentication info: {auth_info}")
        
    except Exception as e:
        print(f"Error testing debug logging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()
        
        # Clean up temporary file
        try:
            cache_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(test_debug_logging()) 