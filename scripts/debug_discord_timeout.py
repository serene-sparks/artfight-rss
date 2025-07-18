#!/usr/bin/env python3
"""Debug script for Discord bot timeout issues on remote servers."""

import asyncio
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands

from artfight_rss.config import settings


async def debug_discord_timeout():
    """Debug Discord bot timeout issues."""
    print("🔍 Discord Bot Timeout Debug")
    print("=" * 40)
    
    print(f"Discord enabled: {settings.discord_enabled}")
    print(f"Bot token: {'Set' if settings.discord_token else 'Not set'}")
    print(f"Channel ID: {settings.discord_channel_id}")
    print(f"Guild ID: {settings.discord_guild_id}")
    
    if not settings.discord_enabled or not settings.discord_token:
        print("❌ Discord not properly configured")
        return
    
    # Test different timeout values
    timeout_values = [30, 60, 120, 300]  # 30s, 1m, 2m, 5m
    
    for timeout in timeout_values:
        print(f"\n🧪 Testing with {timeout}s timeout...")
        
        # Create bot instance
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        ready_event = asyncio.Event()
        
        @bot.event
        async def on_ready():
            print(f"✅ Bot logged in as: {bot.user}")
            ready_event.set()
        
        @bot.event
        async def on_connect():
            print(f"🔗 Bot connected to Discord gateway")
        
        @bot.event
        async def on_disconnect():
            print(f"🔌 Bot disconnected from Discord gateway")
        
        start_time = time.time()
        
        # Create a task for the bot startup
        bot_task = asyncio.create_task(bot.start(settings.discord_token))
        
        try:
            # Wait for either the bot to be ready or timeout
            print(f"Attempting to connect and become ready with {timeout}s timeout...")
            
            # Wait for the ready event (which means bot is fully operational)
            await asyncio.wait_for(ready_event.wait(), timeout=timeout)
            
            elapsed = time.time() - start_time
            print(f"✅ Success! Bot ready in {elapsed:.1f}s")
            print("✅ Bot is ready and operational!")
            
            # Test sending a message
            if settings.discord_channel_id:
                target_channel = None
                for guild in bot.guilds:
                    for channel in guild.text_channels:
                        if channel.id == settings.discord_channel_id:
                            target_channel = channel
                            break
                    if target_channel:
                        break
                
                if target_channel:
                    try:
                        await target_channel.send("🔧 **Timeout Debug Test**\nBot is working correctly!")
                        print("✅ Test message sent successfully!")
                    except Exception as e:
                        print(f"❌ Failed to send test message: {e}")
                else:
                    print("⚠️ Target channel not found")
            
            break  # Success, no need to test longer timeouts
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"❌ Timeout after {elapsed:.1f}s (limit: {timeout}s)")
            print("This suggests:")
            print("- Slow network connection")
            print("- Discord API rate limiting")
            print("- Firewall/proxy issues")
            print("- Discord service issues")
            print("- Bot not added to server or invalid token")
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Error after {elapsed:.1f}s: {e}")
            
        finally:
            # Cancel the bot task and close the bot
            bot_task.cancel()
            try:
                await asyncio.wait_for(bot_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            
            try:
                await bot.close()
            except:
                pass
    
    print(f"\n📊 Summary:")
    print(f"- Recommended timeout: {timeout}s or higher")
    print(f"- Network connectivity: {'Good' if 'Success' in locals() else 'Poor'}")
    print(f"- Discord API status: {'Responsive' if 'Success' in locals() else 'Slow/Unresponsive'}")


if __name__ == "__main__":
    asyncio.run(debug_discord_timeout()) 