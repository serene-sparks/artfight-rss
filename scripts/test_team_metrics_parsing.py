#!/usr/bin/env python3
"""Test script for team metrics parsing."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from artfight_feed.artfight import ArtFightClient
from artfight_feed.database import ArtFightDatabase
from artfight_feed.cache import SQLiteCache
from artfight_feed.config import settings
from artfight_feed.cache import RateLimiter

# Sample HTML from the events page
SAMPLE_HTML = """
<div class="row">
    <div class="col-md-6">
        <div class="card mt-3">
            <div class="card-header text-center" style="background-color: rgba(186, 140, 37, 0.2); --darkreader-inline-bgcolor: var(--darkreader-background-ba8c2533, rgba(149, 112, 30, 0.2));" data-darkreader-inline-bgcolor="">
                <strong><a href="/team/21.fossils" style="color: rgb(186, 140, 37); --darkreader-inline-color: var(--darkreader-text-ba8c25, #ddb252);" data-darkreader-inline-color="">Fossils</a></strong>
            </div>
            <div class="card-body text-center">
                <h4>50.04% <small>points</small></h4>
                <h4>272912 <small>users</small></h4>
                <h4>685194 <small>attacks</small></h4>
                <h4>320485 <small>friendly fire attacks</small></h4>
                <h4>49.98% <small>battle ratio</small></h4>
                <h4>172.35 <small>average points</small></h4>
                <h4>2.51 <small>average attacks</small></h4>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card mt-3">
            <div class="card-header text-center" style="background-color: rgba(211, 94, 136, 0.2); --darkreader-inline-bgcolor: var(--darkreader-background-d35e8833, rgba(137, 37, 73, 0.2));" data-darkreader-inline-bgcolor="">
                <strong><a href="/team/22.crystals" style="color: rgb(211, 94, 136); --darkreader-inline-color: var(--darkreader-text-d35e88, #d5668e);" data-darkreader-inline-color="">Crystals</a></strong>
            </div>
            <div class="card-body text-center">
                <h4>49.96% <small>points</small></h4>
                <h4>272900 <small>users</small></h4>
                <h4>685755 <small>attacks</small></h4>
                <h4>318152 <small>friendly fire attacks</small></h4>
                <h4>50.02% <small>battle ratio</small></h4>
                <h4>172.11 <small>average points</small></h4>
                <h4>2.51 <small>average attacks</small></h4>
            </div>
        </div>
    </div>
</div>
"""

async def test_team_metrics_parsing():
    """Test the team metrics parsing functionality."""
    print("🧪 Testing Team Metrics Parsing")
    print("=" * 50)

    # Initialize components
    database = ArtFightDatabase(db_path=settings.db_path)
    cache = SQLiteCache(database)
    rate_limiter = RateLimiter(database, settings.request_interval)
    client = ArtFightClient(rate_limiter, database)

    try:
        print("\n📋 Sample HTML:")
        print(SAMPLE_HTML.strip())

        print("\n📋 Configured Teams:")
        if settings.teams:
            print(f"  Team 1: {settings.teams.team1.name} -> {settings.teams.team1.color}")
            print(f"  Team 2: {settings.teams.team2.name} -> {settings.teams.team2.color}")
        else:
            print("  No teams configured, using fallback names")

        # Test parsing the team metrics from the sample HTML
        print("\n🔍 Testing team metrics parsing:")
        print("-" * 40)

        metrics = client._parse_team_metrics_from_html(SAMPLE_HTML)

        print(f"  Parsed metrics: {metrics}")

        # Test creating a TeamStanding object with the metrics
        print("\n🔍 Testing TeamStanding creation:")
        print("-" * 40)

        from artfight_feed.models import TeamStanding
        from datetime import datetime, UTC

        standing = TeamStanding(
            team1_percentage=50.04,
            fetched_at=datetime.now(UTC),
            leader_change=False,
            **metrics
        )

        print(f"  Team 1 percentage: {standing.team1_percentage:.2f}%")
        print(f"  Team 2 percentage: {100-standing.team1_percentage:.2f}%")
        
        if standing.team1_users:
            print(f"  Team 1 users: {standing.team1_users:,}")
        if standing.team2_users:
            print(f"  Team 2 users: {standing.team2_users:,}")
            
        if standing.team1_attacks:
            print(f"  Team 1 attacks: {standing.team1_attacks:,}")
        if standing.team2_attacks:
            print(f"  Team 2 attacks: {standing.team2_attacks:,}")
            
        if standing.team1_friendly_fire:
            print(f"  Team 1 friendly fire: {standing.team1_friendly_fire:,}")
        if standing.team2_friendly_fire:
            print(f"  Team 2 friendly fire: {standing.team2_friendly_fire:,}")
            
        if standing.team1_battle_ratio:
            print(f"  Team 1 battle ratio: {standing.team1_battle_ratio:.2f}%")
        if standing.team2_battle_ratio:
            print(f"  Team 2 battle ratio: {standing.team2_battle_ratio:.2f}%")
            
        if standing.team1_avg_points:
            print(f"  Team 1 avg points: {standing.team1_avg_points:.2f}")
        if standing.team2_avg_points:
            print(f"  Team 2 avg points: {standing.team2_avg_points:.2f}")
            
        if standing.team1_avg_attacks:
            print(f"  Team 1 avg attacks: {standing.team1_avg_attacks:.2f}")
        if standing.team2_avg_attacks:
            print(f"  Team 2 avg attacks: {standing.team2_avg_attacks:.2f}")

        # Test RSS feed generation
        print("\n🔍 Testing RSS feed generation:")
        print("-" * 40)

        atom_item = standing.to_atom_item()
        print(f"  Title: {atom_item['title']}")
        print(f"  Description length: {len(atom_item['description'])} characters")
        print(f"  Description preview: {atom_item['description'][:200]}...")

        # Summary
        print("\n📊 Test Summary:")
        print(f"  Team metrics parsed successfully: {'✅' if any(metrics.values()) else '❌'}")
        print(f"  Team 1 metrics found: {sum(1 for k, v in metrics.items() if k.startswith('team1_') and v is not None)}/6")
        print(f"  Team 2 metrics found: {sum(1 for k, v in metrics.items() if k.startswith('team2_') and v is not None)}/6")

        if any(metrics.values()):
            print("✅ Team metrics parsing is working correctly!")
        else:
            print("❌ No team metrics were parsed")

    except Exception as e:
        print(f"❌ Error testing team metrics parsing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Ensure client is closed
        await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_team_metrics_parsing()) 