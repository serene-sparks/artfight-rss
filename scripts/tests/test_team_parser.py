#!/usr/bin/env python3
"""Test script to verify team parser functionality."""

import asyncio
import logging
from datetime import datetime

from artfight_rss.artfight import ArtFightClient
from artfight_rss.cache import RateLimiter, SQLiteCache
from artfight_rss.database import ArtFightDatabase
from artfight_rss.config import settings

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Sample HTML from ArtFight home page
SAMPLE_HTML = """
<div class="progress">
    <div class="progress-bar" role="progressbar" style="width:49.999199486824%;background-color: #BA8C25;">50.00%</div>
    <div class="progress-bar" role="progressbar" style="width:50.000800513176%;background-color: #D35E88;">50.00%</div>
</div>
"""

# Sample configuration for testing
SAMPLE_CONFIG = """
[teams]
team1 = { name = "Team Alpha", color = "#BA8C25" }
team2 = { name = "Team Beta", color = "#D35E88" }
"""

async def test_team_parser():
    """Test the team parser with sample HTML."""
    print("🧪 Testing Team Parser")
    print("=" * 50)
    
    # Initialize components
    cache = SQLiteCache(db_path=settings.cache_db_path)
    rate_limiter = RateLimiter(cache, settings.request_interval)
    database = ArtFightDatabase(db_path=settings.db_path)
    client = ArtFightClient(rate_limiter, database)
    
    try:
        print(f"\n📋 Sample HTML:")
        print(SAMPLE_HTML.strip())
        
        print(f"\n📋 Configured Teams:")
        if settings.teams:
            print(f"  Team 1: {settings.teams.team1.name} -> {settings.teams.team1.color}")
            print(f"  Team 2: {settings.teams.team2.name} -> {settings.teams.team2.color}")
        else:
            print("  No teams configured, using fallback names")
        
        # Test parsing the sample HTML
        print(f"\n🔍 Testing team parsing:")
        print("-" * 40)
        
        standings = client._parse_team_standings_from_html(SAMPLE_HTML)
        
        print(f"  Teams found: {len(standings)}")
        
        for i, standing in enumerate(standings, 1):
            print(f"  Team {i}:")
            print(f"    Name: {standing.name}")
            print(f"    Score: {standing.score}")
            print(f"    Side: {standing.side}")
            print(f"    Last Switch: {standing.last_switch}")
        
        # Test with real ArtFight data if available
        print(f"\n🌐 Testing with real ArtFight data:")
        print("-" * 40)
        
        try:
            real_standings = await client.get_team_standings()
            print(f"  Real teams found: {len(real_standings)}")
            
            for i, standing in enumerate(real_standings, 1):
                print(f"  Team {i}:")
                print(f"    Name: {standing.name}")
                print(f"    Score: {standing.score}")
                print(f"    Side: {standing.side}")
                print(f"    Last Switch: {standing.last_switch}")
                
        except Exception as e:
            print(f"  Error fetching real data: {e}")
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"  Sample HTML parsed successfully: {'✅' if len(standings) > 0 else '❌'}")
        print(f"  Teams found in sample: {len(standings)}")
        
        if len(standings) == 2:
            print("✅ Team parser is working correctly!")
        else:
            print("⚠️  Expected 2 teams, but found different number")
            
    except Exception as e:
        print(f"❌ Error testing team parser: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Ensure client is closed
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_team_parser()) 