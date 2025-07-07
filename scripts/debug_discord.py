#!/usr/bin/env python3
"""Debug script for Discord bot connectivity."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import discord

from artfight_rss.config import settings


async def debug_discord():
    """Debug Discord bot connectivity."""
    print("Discord Bot Debug")
    print("=" * 20)

    print(f"Discord enabled: {settings.discord_enabled}")
    print(f"Bot token: {'Set' if settings.discord_token else 'Not set'}")
    print(f"Channel ID: {settings.discord_channel_id}")
    print(f"Guild ID: {settings.discord_guild_id}")

    if not settings.discord_enabled or not settings.discord_token:
        print("❌ Discord not properly configured")
        return

    # Create bot instance
    intents = discord.Intents.default()
    from discord.ext import commands
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"✅ Bot logged in as: {bot.user}")
        print(f"Bot ID: {bot.user.id}")

        # List all guilds (servers) the bot is in
        print(f"\nBot is in {len(bot.guilds)} server(s):")
        for guild in bot.guilds:
            print(f"  - {guild.name} (ID: {guild.id})")

            # List channels in this guild
            print("    Channels:")
            for channel in guild.text_channels:
                print(f"      - {channel.name} (ID: {channel.id})")

                # Check if this is our target channel
                if channel.id == settings.discord_channel_id:
                    print("        ✅ This is our target channel!")

                    # Check bot permissions in this channel
                    bot_member = guild.get_member(bot.user.id)
                    if bot_member:
                        permissions = channel.permissions_for(bot_member)
                        print("        Bot permissions:")
                        print(f"          - Send Messages: {permissions.send_messages}")
                        print(f"          - Embed Links: {permissions.embed_links}")
                        print(f"          - Attach Files: {permissions.attach_files}")
                        print(f"          - Read Messages: {permissions.read_messages}")

                        # Try to send a test message
                        try:
                            await channel.send("🔧 **Discord Bot Debug Test**\nThis is a test message to verify the bot is working!")
                            print("        ✅ Test message sent successfully!")
                        except Exception as e:
                            print(f"        ❌ Failed to send test message: {e}")

        # Stop the bot after debugging
        await bot.close()

    try:
        print("\nConnecting to Discord...")
        await bot.start(settings.discord_token)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(debug_discord())
