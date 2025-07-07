#!/usr/bin/env python3
"""Fixed test script for Discord bot functionality."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import UTC, datetime

import discord
from pydantic import HttpUrl

from artfight_rss.config import settings
from artfight_rss.models import ArtFightAttack, ArtFightDefense, TeamStanding


async def test_discord_bot_fixed():
    """Test Discord bot functionality with direct channel access."""
    print("Testing Discord Bot Functionality (Fixed)")
    print("=" * 50)

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

    # Create bot instance
    intents = discord.Intents.default()
    from discord.ext import commands
    bot = commands.Bot(command_prefix="!", intents=intents)

    target_channel = None

    @bot.event
    async def on_ready():
        nonlocal target_channel
        print(f"✅ Bot ready: {bot.user}")

        # Find the target channel directly
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.id == settings.discord_channel_id:
                    target_channel = channel
                    print(f"✅ Found target channel: {target_channel.name}")
                    break
            if target_channel:
                break

        if not target_channel:
            print("❌ Target channel not found")
            await bot.close()
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

        # Send test notifications directly to channel
        print("\nSending test notifications...")

        try:
            # Attack notification
            print("Sending test attack notification...")
            attack_embed = discord.Embed(
                title="🎨 New ArtFight Attack!",
                description=f"**{test_attack.title}**",
                color=0xff6b6b,
                url=str(test_attack.url),
                timestamp=test_attack.fetched_at
            )
            attack_embed.add_field(name="Attacker", value=f"`{test_attack.attacker_user}`", inline=True)
            attack_embed.add_field(name="Defender", value=f"`{test_attack.defender_user}`", inline=True)
            if test_attack.description:
                attack_embed.add_field(name="Description", value=test_attack.description[:1024], inline=False)
            if test_attack.image_url:
                attack_embed.set_image(url=str(test_attack.image_url))
            attack_embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
            await target_channel.send(embed=attack_embed)

            # Defense notification
            print("Sending test defense notification...")
            defense_embed = discord.Embed(
                title="🛡️ New ArtFight Defense!",
                description=f"**{test_defense.title}**",
                color=0x4ecdc4,
                url=str(test_defense.url),
                timestamp=test_defense.fetched_at
            )
            defense_embed.add_field(name="Defender", value=f"`{test_defense.defender_user}`", inline=True)
            defense_embed.add_field(name="Attacker", value=f"`{test_defense.attacker_user}`", inline=True)
            if test_defense.description:
                defense_embed.add_field(name="Description", value=test_defense.description[:1024], inline=False)
            if test_defense.image_url:
                defense_embed.set_image(url=str(test_defense.image_url))
            defense_embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
            await target_channel.send(embed=defense_embed)

            # Team standing notification
            print("Sending test team standing notification...")
            team1_name = settings.teams.team1.name if settings.teams else "Team 1"
            team2_name = settings.teams.team2.name if settings.teams else "Team 2"
            leading_team = team1_name if test_standing.team1_percentage > 50 else team2_name

            standing_embed = discord.Embed(
                title="🏆 Team Standings Update",
                description=f"**{leading_team}** is currently leading!",
                color=0xff9900,
                timestamp=test_standing.fetched_at
            )
            standing_embed.add_field(name=team1_name, value=f"{test_standing.team1_percentage:.2f}%", inline=True)
            standing_embed.add_field(name=team2_name, value=f"{100 - test_standing.team1_percentage:.2f}%", inline=True)
            standing_embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
            await target_channel.send(embed=standing_embed)

            # Leader change notification
            print("Sending test leader change notification...")
            leader_embed = discord.Embed(
                title="👑 LEADER CHANGE!",
                description=f"**{leading_team}** has taken the lead!",
                color=0xff6b6b,
                timestamp=test_standing.fetched_at
            )
            leader_embed.add_field(name=team1_name, value=f"{test_standing.team1_percentage:.2f}%", inline=True)
            leader_embed.add_field(name=team2_name, value=f"{100 - test_standing.team1_percentage:.2f}%", inline=True)
            leader_embed.add_field(name="🎉", value=f"Congratulations to **{leading_team}** for taking the lead!", inline=False)
            leader_embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
            await target_channel.send(embed=leader_embed)

            print("\n✅ All test notifications sent successfully!")
            print("Check your Discord channel for the test messages")

        except Exception as e:
            print(f"❌ Error sending notifications: {e}")
            import traceback
            traceback.print_exc()

        # Wait a moment for messages to be sent
        await asyncio.sleep(2)
        await bot.close()

    try:
        await bot.start(settings.discord_token)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")


if __name__ == "__main__":
    asyncio.run(test_discord_bot_fixed())
