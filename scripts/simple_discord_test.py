#!/usr/bin/env python3
"""Simple Discord embed test."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import discord

from artfight_rss.config import settings


async def simple_test():
    """Send a simple Discord embed."""
    print("Simple Discord Embed Test")
    print("=" * 30)

    if not settings.discord_enabled or not settings.discord_token:
        print("❌ Discord not configured")
        return

    # Create bot instance
    intents = discord.Intents.default()
    from discord.ext import commands
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"✅ Bot ready: {bot.user}")

        # Find the target channel
        target_channel = None
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.id == settings.discord_channel_id:
                    target_channel = channel
                    break
            if target_channel:
                break

        if not target_channel:
            print("❌ Target channel not found")
            await bot.close()
            return

        print(f"✅ Found target channel: {target_channel.name}")

        # Create and send a simple embed
        embed = discord.Embed(
            title="🎨 Test ArtFight Notification",
            description="This is a test embed message from the ArtFight bot!",
            color=0xff6b6b,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Test Field", value="This is a test field", inline=True)
        embed.add_field(name="Status", value="✅ Working!", inline=True)
        embed.set_footer(text="ArtFight Bot Test", icon_url="https://artfight.net/favicon.ico")

        try:
            await target_channel.send(embed=embed)
            print("✅ Embed sent successfully!")
        except Exception as e:
            print(f"❌ Failed to send embed: {e}")

        await bot.close()

    try:
        await bot.start(settings.discord_token)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(simple_test())
