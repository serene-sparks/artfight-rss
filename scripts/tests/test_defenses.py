#!/usr/bin/env python3
"""Test script for defense parsing functionality."""

import asyncio
import sys
import os
import logging

# Add the artfight_rss directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_rss'))

from artfight_rss.artfight import ArtFightClient
from artfight_rss.cache import RateLimiter
from artfight_rss.database import ArtFightDatabase
from artfight_rss.config import settings


async def test_defense_parsing():
    """Test the defense parsing functionality."""

    # Set up logging to see debug messages
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    print("Testing defense parsing...")
    
    # Initialize components
    from pathlib import Path
    import tempfile
    
    # Use permanent database path from config
    database = ArtFightDatabase(settings.db_path)
    rate_limiter = RateLimiter(database, 60)  # 60 second interval
    
    # Create ArtFight client
    client = ArtFightClient(rate_limiter, database)
    
    try:
        # Test with a known username (you'll need to replace with a real one)
        username = "fourleafisland"  # Replace with a real ArtFight username
        
        print(f"Fetching defenses for user: {username}")
        
        # Get defenses
        defenses = await client.get_user_defenses(username)
        
        print(f"Found {len(defenses)} defenses")
        
        for i, defense in enumerate(defenses, 1):
            print(f"\nDefense {i}:")
            print(f"  Title: {defense.title}")
            print(f"  Defender: {defense.defender_user}")
            print(f"  Target: {defense.attacker_user}")
            print(f"  URL: {defense.url}")
            if defense.description:
                print(f"  Description: {defense.description}")
            if defense.image_url:
                print(f"  Image: {defense.image_url}")
            print(f"  Fetched: {defense.fetched_at}")
        
        # Test RSS generation
        from artfight_rss.rss import rss_generator
        feed = rss_generator.generate_user_defense_feed(username, defenses)
        print(f"\nRSS Feed generated:")
        print(f"  Title: {feed.title}")
        print(f"  Description: {feed.description}")
        print(f"  Items: {len(feed.items)}")
        
    except Exception as e:
        print(f"Error testing defense parsing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_defense_parsing()) 