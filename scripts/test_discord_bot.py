#!/usr/bin/env python3
"""Test script for Discord bot functionality."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import UTC, datetime

from pydantic import HttpUrl

from artfight_feed.config import settings
from artfight_feed.discord_bot import discord_bot
from artfight_feed.models import ArtFightAttack, ArtFightDefense, TeamStanding


async def test_discord_bot():
    """Test Discord bot functionality."""
    print("Testing Discord Bot Functionality")
    print("=" * 40)

    # Check if Discord is enabled
    if not settings.discord_enabled:
        print("❌ Discord bot is disabled in configuration")
        print("Set discord_enabled = true in config.toml to enable")
        return

    # Check if we have required configuration
    if not settings.discord_token and not settings.discord_webhook_url:
        print("❌ No Discord token or webhook URL configured")
        print("Set either discord_token or discord_webhook_url in config.toml")
        return

    print("✅ Discord configuration found")

    try:
        # Start the Discord bot in the background
        print("Starting Discord bot...")
        bot_task = asyncio.create_task(discord_bot.start())

        # Wait for the bot to be ready
        try:
            await asyncio.wait_for(discord_bot.ready_event.wait(), timeout=10.0)
            print("✅ Discord bot started successfully")
        except TimeoutError:
            print("❌ Failed to start Discord bot (timeout)")
            print("This might be due to:")
            print("- Invalid bot token")
            print("- Bot not added to server")
            print("- Incorrect permissions")
            return

        # Create test data
        test_attack = ArtFightAttack(
            id="test_attack_1",
            title="Test Attack",
            description="This is a test attack for Discord bot testing",
            image_url=HttpUrl("https://via.placeholder.com/400x300/ff6b6b/ffffff?text=Test+Attack"),
            attacker_user="test_attacker",
            defender_user="test_defender",
            fetched_at=datetime.now(UTC),
            url=HttpUrl("https://artfight.net/~test_attacker/attacks/1")
        )

        test_defense = ArtFightDefense(
            id="test_defense_1",
            title="Test Defense",
            description="This is a test defense for Discord bot testing",
            image_url=HttpUrl("https://via.placeholder.com/400x300/4ecdc4/ffffff?text=Test+Defense"),
            defender_user="test_defender",
            attacker_user="test_attacker",
            fetched_at=datetime.now(UTC),
            url=HttpUrl("https://artfight.net/~test_defender/defenses/1")
        )

        test_standing = TeamStanding(
            team1_percentage=55.5,
            fetched_at=datetime.now(UTC),
            leader_change=True
        )

        # Send test notifications
        print("\nSending test notifications...")

        print("Sending test attack notification...")
        await discord_bot.send_attack_notification(test_attack)

        print("Sending test defense notification...")
        await discord_bot.send_defense_notification(test_defense)

        print("Sending test team standing notification...")
        await discord_bot.send_team_standing_notification(test_standing)

        print("Sending test leader change notification...")
        await discord_bot.send_leader_change_notification(test_standing)

        print("\n✅ Test notifications sent successfully!")
        print("Check your Discord channel/webhook for the test messages")

        # Wait a moment for messages to be sent
        await asyncio.sleep(2)

        print("\n✅ Test notifications sent successfully!")
        print("Check your Discord channel/webhook for the test messages")

    except Exception as e:
        print(f"❌ Error during Discord bot test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Stop the Discord bot
        print("\nStopping Discord bot...")
        await discord_bot.stop()

        # Cancel the background task
        if 'bot_task' in locals():
            bot_task.cancel()
            try:
                await asyncio.wait_for(bot_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

        print("✅ Discord bot stopped")


if __name__ == "__main__":
    asyncio.run(test_discord_bot())
