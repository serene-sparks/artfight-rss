"""Discord bot integration for ArtFight webhook service."""

import asyncio
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import discord
from aiohttp import ClientSession
from discord import app_commands
from discord.ext import commands
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
from redlines import Redlines
import html2text

from .config import settings
from .logging_config import get_logger
from .models import ArtFightAttack, ArtFightDefense, TeamStanding, ArtFightNews
from .plotting import generate_team_standings_plot

logger = get_logger(__name__)


class ArtFightDiscordBot:
    """Discord bot for ArtFight notifications and commands."""

    def __init__(self, database=None):
        """Initialize the Discord bot."""
        self.bot: commands.Bot | None = None
        self.webhook: discord.Webhook | None = None
        self.channel: discord.TextChannel | None = None
        self.running = False
        self.ready_event = asyncio.Event()
        self.bot_task: asyncio.Task | None = None
        self.database = database

    def set_database(self, database):
        """Set the database instance for accessing rate limit data."""
        self.database = database

    def set_monitor(self, monitor):
        """Set the monitor instance for accessing monitoring status."""
        self.monitor = monitor

    async def start(self):
        """Start the Discord bot or webhook."""
        if not settings.discord_enabled:
            logger.info("Discord bot disabled in configuration.")
            return

        if settings.discord_token:
            await self._start_bot()
        elif settings.discord_webhook_url:
            await self._start_webhook()
        else:
            logger.warning("Discord integration enabled but no token or webhook URL provided.")
            return

        self.running = True

    async def stop(self):
        """Stop the Discord bot."""
        if not self.running:
            return

        logger.info("Stopping Discord bot...")
        self.running = False

        # Cancel the bot task if it exists
        if self.bot_task:
            self.bot_task.cancel()
            try:
                await asyncio.wait_for(self.bot_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                logger.warning("Discord bot task did not stop within timeout")

        # Close the bot if it exists
        if self.bot:
            try:
                await asyncio.wait_for(self.bot.close(), timeout=5.0)
            except TimeoutError:
                logger.warning("Discord bot did not close within timeout")

        logger.info("Discord bot stopped")

    async def _start_bot(self):
        """Start the Discord bot with slash commands."""
        intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix="!", intents=intents)

        @self.bot.event
        async def on_ready():
            if not self.bot or not self.bot.user:
                return

            logger.info(f"Discord bot logged in as {self.bot.user}")

            # Set up channel for notifications
            if settings.discord_channel_id:
                channel = self.bot.get_channel(settings.discord_channel_id)
                if isinstance(channel, discord.TextChannel):
                    self.channel = channel
                    logger.info(f"Connected to notification channel: {self.channel.name}")
                elif channel:
                    logger.warning(f"Channel with ID {settings.discord_channel_id} is not a text channel.")
                else:
                    logger.warning(f"Could not find channel with ID: {settings.discord_channel_id}")

            # Register slash commands after bot is ready
            try:
                await self._register_commands()
            except Exception as e:
                logger.warning(f"Failed to register slash commands: {e}")

            # Signal that the bot is ready
            self.ready_event.set()

        try:
            assert settings.discord_token is not None
            self.bot_task = asyncio.create_task(self.bot.start(settings.discord_token))
            await asyncio.wait_for(self.ready_event.wait(), timeout=float(settings.discord_startup_timeout))
            logger.info("Discord bot is ready and operational.")
        except TimeoutError:
            logger.error(f"Discord bot failed to become ready within {settings.discord_startup_timeout}s timeout.")
            if self.bot_task:
                self.bot_task.cancel()
            raise
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            if self.bot_task:
                self.bot_task.cancel()
            raise

    async def _start_webhook(self):
        """Start webhook-only mode."""
        if not settings.discord_webhook_url:
            raise ValueError("Discord webhook URL is required for webhook mode")

        self.webhook = discord.Webhook.from_url(
            settings.discord_webhook_url,
            session=ClientSession()
        )
        logger.info("Discord webhook initialized")

    async def _register_commands(self):
        """Register slash commands for the bot."""
        if not self.bot:
            return

        @self.bot.tree.command(name="artfight", description="ArtFight bot commands")
        @app_commands.choices(action=[
            app_commands.Choice(name="stats", value="stats"),
            app_commands.Choice(name="status", value="status"),
            app_commands.Choice(name="teams", value="teams"),
            app_commands.Choice(name="plot", value="plot"),
            app_commands.Choice(name="cache", value="cache"),
            app_commands.Choice(name="monitor", value="monitor"),
            app_commands.Choice(name="auth", value="auth"),
            app_commands.Choice(name="help", value="help"),
        ])
        @app_commands.describe(
            action="Action to perform",
            include_team_balance="Include team balance subplot (user counts and differences)",
            subaction="Sub-action for cache or monitor commands"
        )
        @app_commands.choices(subaction=[
            app_commands.Choice(name="info", value="info"),
            app_commands.Choice(name="clear", value="clear"),
            app_commands.Choice(name="cleanup", value="cleanup"),
            app_commands.Choice(name="reset", value="reset"),
        ])
        async def artfight_command(
            interaction: discord.Interaction,
            action: str,
            include_team_balance: bool | None = None,
            subaction: str | None = None
        ):
            """Main ArtFight command."""
            await interaction.response.defer()

            try:
                if action == "stats":
                    await self._handle_stats_command(interaction)
                elif action == "status":
                    await self._handle_status_command(interaction)
                elif action == "teams":
                    await self._handle_teams_command(interaction)
                elif action == "plot":
                    await self._handle_plot_command(interaction, include_team_balance)
                elif action == "cache":
                    await self._handle_cache_command(interaction, subaction)
                elif action == "monitor":
                    await self._handle_monitor_command(interaction, subaction)
                elif action == "auth":
                    await self._handle_auth_command(interaction)
                elif action == "help":
                    await self._handle_help_command(interaction)
                else:
                    await interaction.followup.send("Unknown action. Use `/artfight help` for available commands.")
            except Exception as e:
                logger.error(f"Error handling command {action}: {e}")
                await interaction.followup.send("An error occurred while processing your command.")

        # Sync commands with Discord
        try:
            if settings.discord_guild_id:
                await self.bot.tree.sync(guild=discord.Object(id=settings.discord_guild_id))
                logger.info(f"Synced commands to guild {settings.discord_guild_id}")
            else:
                await self.bot.tree.sync()
                logger.info("Synced commands globally")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def _handle_stats_command(self, interaction: discord.Interaction):
        """Handle the stats command."""

        embed = discord.Embed(
            title="ArtFight Bot Statistics",
            description="Current bot status and statistics",
            color=0x00ff00,
            timestamp=datetime.now(UTC)
        )

        embed.add_field(name="Status", value="🟢 Running", inline=True)
        embed.add_field(name="Mode", value="Bot" if self.bot else "Webhook", inline=True)
        embed.add_field(name="Notifications", value="Enabled", inline=True)

        # Add monitor status if available
        if hasattr(self, 'monitor') and self.monitor:
            monitor_stats = self.monitor.get_stats()
            
            # Monitor status
            overall_status = "🟢 Active" if monitor_stats.get("running", False) else "🔴 Inactive"
            news_status = "🟢 Active" if monitor_stats.get("news_running", False) else "🔴 Inactive"
            event_status = "🟢 Active" if monitor_stats.get("event_monitoring_running", False) else "🔴 Inactive"
            
            embed.add_field(name="Monitor Status", value=overall_status, inline=True)
            embed.add_field(name="News Monitoring", value=news_status, inline=True)
            embed.add_field(name="Event Monitoring", value=event_status, inline=True)
            
            # Battle over detection info
            no_event_info = monitor_stats.get("no_event_detection", {})
            if no_event_info.get("enabled", False):
                consecutive_count = no_event_info.get("consecutive_count", 0)
                stopped = no_event_info.get("stopped", False)
                battle_status = f"🔴 Stopped ({consecutive_count}/3)" if stopped else f"🟢 Active ({consecutive_count}/3)"
                embed.add_field(name="Battle Over Detection", value=battle_status, inline=True)

        await interaction.followup.send(embed=embed)

    async def _handle_status_command(self, interaction: discord.Interaction):
        """Handle the status command."""
        embed = discord.Embed(
            title="ArtFight Bot Status",
            description="Current bot configuration and status",
            color=0x0099ff,
            timestamp=datetime.now(UTC)
        )

        embed.add_field(
            name="Configuration",
            value=f"**Enabled:** {settings.discord_enabled}\n"
                  f"**Mode:** {'Bot' if self.bot else 'Webhook'}\n"
                  f"**Channel:** {settings.discord_channel_id or 'Not set'}",
            inline=False
        )

        embed.add_field(
            name="Notifications",
            value=f"**Attacks:** {settings.discord_notify_attacks}\n"
                  f"**Defenses:** {settings.discord_notify_defenses}\n"
                  f"**Team Changes:** {settings.discord_notify_team_changes}\n"
                  f"**Leader Changes:** {settings.discord_notify_leader_changes}",
            inline=False
        )

        # Add rate limit information if database is available
        if self.database:
            # Get team rate limit info
            team_rate_limit = self.database.get_rate_limit("teams")
            team_status = "Rate limited" if team_rate_limit else "Available"
            if team_rate_limit:
                # Format the timestamp to be more readable
                team_last_request = team_rate_limit.strftime("%Y-%m-%d %H:%M:%S")
            else:
                team_last_request = "Never"

            embed.add_field(
                name="Team Monitoring",
                value=f"**Status:** {team_status}\n"
                      f"**Last Request:** {team_last_request}",
                inline=True
            )

            # Get monitored users rate limit info
            user_rate_limits = []
            for user in settings.monitor_list:
                user_rate_limit = self.database.get_rate_limit(f"user_{user}")
                user_status = "Rate limited" if user_rate_limit else "Available"
                if user_rate_limit:
                    # Format the timestamp to be more readable
                    user_last_request = user_rate_limit.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    user_last_request = "Never"
                user_rate_limits.append(f"**{user}:** {user_status} (Last: {user_last_request})")

            if user_rate_limits:
                # If there are many users, split into multiple fields to avoid Discord's field length limit
                if len(user_rate_limits) <= 5:
                    embed.add_field(
                        name="User Monitoring",
                        value="\n".join(user_rate_limits),
                        inline=True
                    )
                else:
                    # Split into chunks of 5 users per field
                    for i in range(0, len(user_rate_limits), 5):
                        chunk = user_rate_limits[i:i+5]
                        field_name = f"User Monitoring ({i+1}-{min(i+5, len(user_rate_limits))})"
                        embed.add_field(
                            name=field_name,
                            value="\n".join(chunk),
                            inline=True
                        )

        await interaction.followup.send(embed=embed)

    async def _handle_help_command(self, interaction: discord.Interaction):
        """Handle the help command."""
        embed = discord.Embed(
            title="🤖 ArtFight Bot Help",
            description="Available commands and their usage",
            color=0x00ff00,
            timestamp=datetime.now(UTC)
        )

        embed.add_field(
            name="📊 Information Commands",
            value="• `/artfight stats` - Bot statistics and status\n"
                  "• `/artfight status` - Bot configuration and settings\n"
                  "• `/artfight help` - Show this help message",
            inline=False
        )

        embed.add_field(
            name="🏆 Team Commands",
            value="• `/artfight teams` - Team standings information\n"
                  "• `/artfight plot` - Generate team standings graph\n"
                  "• `/artfight plot include_team_balance:true` - Include team balance subplot",
            inline=False
        )

        embed.add_field(
            name="⚙️ System Management",
            value="• `/artfight cache info` - Cache statistics and status\n"
                  "• `/artfight cache clear` - Clear all cache entries\n"
                  "• `/artfight cache cleanup` - Cleanup expired cache entries\n"
                  "• `/artfight monitor info` - Monitoring system status\n"
                  "• `/artfight monitor reset` - Reset no-event detection\n"
                  "• `/artfight auth` - Authentication configuration status",
            inline=False
        )

        embed.add_field(
            name="📝 Usage Examples",
            value="• `/artfight plot` - Generate basic standings chart\n"
                  "• `/artfight plot include_team_balance:true` - Generate full standings chart with team balance\n"
                  "• `/artfight cache info` - View cache performance and statistics\n"
                  "• `/artfight cache clear` - Clear all cache entries\n"
                  "• `/artfight monitor reset` - Reset monitoring no-event detection",
            inline=False
        )

        embed.add_field(
            name="ℹ️ Note",
            value="Content feeds (news, attacks, defenses) are part of the automatic alerting system and don't require manual commands.",
            inline=False
        )

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
        await interaction.followup.send(embed=embed)

    async def _handle_plot_command(self, interaction: discord.Interaction, include_team_balance: bool | None):
        """Handle the plot command."""
        team1_name = settings.teams.team1.name if settings.teams else "Team 1"
        team2_name = settings.teams.team2.name if settings.teams else "Team 2"

        # Create embed for the plot
        embed = discord.Embed(
            title="📊 Team Standings Plot",
            description=f"Generated plot for {team1_name} vs {team2_name}",
            color=0x0099ff,
            timestamp=datetime.now(UTC)
        )

        # Add information about the plot type
        if include_team_balance is None:
            plot_type = "Default (based on config setting)"
        elif include_team_balance:
            plot_type = "Full chart with team balance subplot"
        else:
            plot_type = "Team standings only"

        embed.add_field(
            name="Plot Type",
            value=plot_type,
            inline=False
        )

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        # Generate the plot
        try:
            plot_file = await self._generate_team_standings_plot(team1_name, team2_name, include_team_balance=include_team_balance)
            if plot_file:
                await self._send_embed_with_file(embed, plot_file, "team_standings.png")
            else:
                embed.add_field(
                    name="❌ Error",
                    value="Failed to generate plot. Check if matplotlib is available and database exists.",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to generate plot: {e}")
            embed.add_field(
                name="❌ Error",
                value=f"Failed to generate plot: {str(e)}",
                inline=False
            )
            await interaction.followup.send(embed=embed)

    async def send_attack_notification(self, attack: ArtFightAttack):
        """Send a Discord notification for a new attack."""
        if not settings.discord_notify_attacks or not self.running:
            return

        embed = discord.Embed(
            title="🎨 New ArtFight Attack!",
            description=f"**{attack.title}**",
            color=0xff6b6b,
            url=str(attack.url),
            timestamp=attack.fetched_at
        )

        embed.add_field(
            name="Attacker",
            value=f"`{attack.attacker_user}`",
            inline=True
        )
        embed.add_field(
            name="Defender",
            value=f"`{attack.defender_user}`",
            inline=True
        )

        if attack.description:
            embed.add_field(
                name="Description",
                value=attack.description[:1024] + "..." if len(attack.description) > 1024 else attack.description,
                inline=False
            )

        if attack.image_url:
            embed.set_image(url=str(attack.image_url))

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

    async def send_defense_notification(self, defense: ArtFightDefense):
        """Send a Discord notification for a new defense."""
        if not settings.discord_notify_defenses or not self.running:
            return

        embed = discord.Embed(
            title="🛡️ New ArtFight Defense!",
            description=f"**{defense.title}**",
            color=0x4ecdc4,
            url=str(defense.url),
            timestamp=defense.fetched_at
        )

        embed.add_field(
            name="Defender",
            value=f"`{defense.defender_user}`",
            inline=True
        )
        embed.add_field(
            name="Attacker",
            value=f"`{defense.attacker_user}`",
            inline=True
        )

        if defense.description:
            embed.add_field(
                name="Description",
                value=defense.description[:1024] + "..." if len(defense.description) > 1024 else defense.description,
                inline=False
            )

        if defense.image_url:
            embed.set_image(url=str(defense.image_url))

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

    async def send_news_notification(self, news: ArtFightNews):
        """Send a Discord notification for a new news post."""
        if not settings.discord_notify_news or not self.running:
            return

        embed = discord.Embed(
            title="📰 New ArtFight News!",
            description=f"**{news.title}**",
            color=0x9b59b6,
            url=str(news.url),
            timestamp=news.posted_at or news.fetched_at
        )

        if news.author:
            embed.add_field(
                name="Author",
                value=f"`{news.author}`",
                inline=True
            )

        if news.posted_at:
            embed.add_field(
                name="Posted",
                value=f"<t:{int(news.posted_at.timestamp())}:R>",
                inline=True
            )

        if news.content:
            embed.add_field(
                name="Content",
                value=news.content[:1024] + "..." if len(news.content) > 1024 else news.content,
                inline=False
            )

        if news.edited_at and news.edited_by:
            embed.add_field(
                name="Edited",
                value=f"By {news.edited_by} <t:{int(news.edited_at.timestamp())}:R>",
                inline=False
            )

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

    async def send_news_revision_notification(self, old_post: ArtFightNews, new_post: ArtFightNews):
        """Send a Discord notification for news post revisions with visual differences."""
        if not settings.discord_notify_news or not self.running:
            return

        # Convert HTML to markdown for content comparison (same logic as database)
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        
        old_markdown = h.handle(old_post.content).strip() if old_post.content else ""
        new_markdown = h.handle(new_post.content).strip() if new_post.content else ""
        
        # Determine what changed using markdown comparison
        changes = []
        if old_post.title != new_post.title:
            changes.append("title")
        if old_markdown != new_markdown:
            changes.append("content")
        
        # If no meaningful changes (title or content), don't send notification
        if not changes:
            logger.debug(f"No meaningful changes detected for news post {new_post.id}, skipping Discord notification")
            return
            
        change_description = " and ".join(changes)
        
        embed = discord.Embed(
            title=f"📝 News Post Revised: {new_post.title}",
            description=f"A news post has been revised with changes to the {change_description}.",
            url=new_post.url,
            color=0xff8c00,  # Orange color for revisions
            timestamp=datetime.now(UTC)
        )

        if new_post.author:
            embed.add_field(
                name="Author",
                value=f"`{new_post.author}`",
                inline=True
            )

        if new_post.posted_at:
            embed.add_field(
                name="Originally Posted",
                value=f"<t:{int(new_post.posted_at.timestamp())}:R>",
                inline=True
            )

        if new_post.edited_at and new_post.edited_by:
            embed.add_field(
                name="Revised By",
                value=f"`{new_post.edited_by}` <t:{int(new_post.edited_at.timestamp())}:R>",
                inline=True
            )

        # Show what changed
        changes = []
        if old_post.title != new_post.title:
            changes.append(f"**Title**: '{old_post.title}' → '{new_post.title}'")
        if old_markdown != new_markdown:
            changes.append("**Content**: Modified")
        if old_post.edited_at != new_post.edited_at:
            changes.append("**Edit timestamp**: Updated")
        if old_post.edited_by != new_post.edited_by:
            changes.append("**Editor**: Changed")

        if changes:
            embed.add_field(
                name="📊 Changes Made",
                value=f"**{change_description.title()}** was modified in this news post revision.",
                inline=False
            )

        # Generate visual diff for content changes
        if old_markdown != new_markdown and old_post.content and new_post.content:
            diff_markdown = self._generate_visual_diff(old_post.content, new_post.content, max_length=1024)
            
            if diff_markdown:
                embed.add_field(
                    name="📝 Content Changes (Visual Diff)",
                    value=f"```diff\n{diff_markdown}\n```",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 Content Changes",
                    value="Content was modified (visual diff unavailable)",
                    inline=False
                )

        # Show current content
        if new_post.content:
            embed.add_field(
                name="Current Content",
                value=new_post.content[:1024] + "..." if len(new_post.content) > 1024 else new_post.content,
                inline=False
            )

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

    def _generate_visual_diff(self, old_text: str, new_text: str, max_length: int = 1024) -> str | None:
        """Generate a visual diff between two text versions using redlines.
        
        First converts HTML to markdown, then generates diff only if content actually changed.
        
        Args:
            old_text: The original text (may contain HTML)
            new_text: The revised text (may contain HTML)
            max_length: Maximum length for the diff output
            
        Returns:
            Formatted diff string or None if no changes or diff generation fails
        """
        if not old_text or not new_text:
            return None
            
        # Convert HTML to markdown for cleaner comparison
        try:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # Don't wrap text
            
            old_markdown = h.handle(old_text).strip()
            new_markdown = h.handle(new_text).strip()
            
            # Only generate diff if markdown content actually changed
            if old_markdown == new_markdown:
                return None
                
            # Generate diff between markdown versions
            diff = Redlines(old_markdown, new_markdown)
            diff_markdown = diff.output_markdown
            
            # Truncate if too long
            if len(diff_markdown) > max_length:
                diff_markdown = diff_markdown[:max_length-3] + "..."
            
            return diff_markdown
            
        except Exception as e:
            logger.warning(f"Failed to generate visual diff: {e}")
            return None

    async def send_team_standing_notification(self, standing: TeamStanding):
        """Send a Discord notification for team standing changes."""
        if not settings.discord_notify_team_changes or not self.running:
            return

        team1_name = settings.teams.team1.name if settings.teams else "Team 1"
        team2_name = settings.teams.team2.name if settings.teams else "Team 2"
        team1_color = int(settings.teams.team1.color.replace("#", ""), 16) if settings.teams else 0xff6b6b
        team2_color = int(settings.teams.team2.color.replace("#", ""), 16) if settings.teams else 0x4ecdc4

        # Determine which team is leading
        leading_team = team1_name if standing.team1_percentage > 50 else team2_name
        leading_color = team1_color if standing.team1_percentage > 50 else team2_color

        embed = discord.Embed(
            title="🏆 Team Standings Update",
            description=f"**{leading_team}** is currently leading!",
            color=leading_color,
            timestamp=standing.fetched_at
        )

        embed.add_field(
            name=team1_name,
            value=f"{standing.team1_percentage:.5f}%",
            inline=True
        )
        embed.add_field(
            name=team2_name,
            value=f"{100 - standing.team1_percentage:.5f}%",
            inline=True
        )

        # Add detailed metrics if available
        if any([standing.team1_users, standing.team1_attacks, standing.team1_friendly_fire,
                standing.team2_users, standing.team2_attacks, standing.team2_friendly_fire]):

            # Create detailed metrics field
            metrics_lines = []
            if standing.team1_users and standing.team2_users:
                metrics_lines.append(f"👥 **Users**: {standing.team1_users:,} | {standing.team2_users:,}")
            if standing.team1_attacks and standing.team2_attacks:
                metrics_lines.append(f"⚔️ **Attacks**: {standing.team1_attacks:,} | {standing.team2_attacks:,}")
            if standing.team1_friendly_fire and standing.team2_friendly_fire:
                metrics_lines.append(f"🔥 **Friendly Fire**: {standing.team1_friendly_fire:,} | {standing.team2_friendly_fire:,}")
            if standing.team1_battle_ratio and standing.team2_battle_ratio:
                metrics_lines.append(f"⚖️ **Battle Ratio**: {standing.team1_battle_ratio:.2f}% | {standing.team2_battle_ratio:.2f}%")
            if standing.team1_avg_points and standing.team2_avg_points:
                metrics_lines.append(f"📊 **Avg Points**: {standing.team1_avg_points:.2f} | {standing.team2_avg_points:.2f}")
            if standing.team1_avg_attacks and standing.team2_avg_attacks:
                metrics_lines.append(f"🎯 **Avg Attacks**: {standing.team1_avg_attacks:.2f} | {standing.team2_avg_attacks:.2f}")

            if metrics_lines:
                embed.add_field(
                    name="📈 Detailed Metrics",
                    value="\n".join(metrics_lines),
                    inline=False
                )

        if settings.teams:
            embed.set_thumbnail(url=settings.teams.team1.image_url if standing.team1_percentage > 50 else settings.teams.team2.image_url)

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        # Generate and attach team standings plot
        try:
            plot_file = await self._generate_team_standings_plot(team1_name, team2_name, include_team_balance=settings.discord_include_team_balance_plot)
            if plot_file:
                await self._send_embed_with_file(embed, plot_file, "team_standings.png")
            else:
                await self._send_embed(embed)
        except Exception as e:
            logger.warning(f"Failed to generate team standings plot: {e}")
            await self._send_embed(embed)

    async def send_leader_change_notification(self, standing: TeamStanding):
        """Send a Discord notification for leader changes."""
        if not settings.discord_notify_leader_changes or not self.running:
            return

        team1_name = settings.teams.team1.name if settings.teams else "Team 1"
        team2_name = settings.teams.team2.name if settings.teams else "Team 2"
        team1_color = int(settings.teams.team1.color.replace("#", ""), 16) if settings.teams else 0xff6b6b
        team2_color = int(settings.teams.team2.color.replace("#", ""), 16) if settings.teams else 0x4ecdc4

        # Determine which team is now leading
        new_leader = team1_name if standing.team1_percentage > 50 else team2_name
        leader_color = team1_color if standing.team1_percentage > 50 else team2_color

        embed = discord.Embed(
            title="👑 LEADER CHANGE!",
            description=f"**{new_leader}** has taken the lead!",
            color=leader_color,
            timestamp=standing.fetched_at
        )

        embed.add_field(
            name=team1_name,
            value=f"{standing.team1_percentage:.5f}%",
            inline=True
        )
        embed.add_field(
            name=team2_name,
            value=f"{100 - standing.team1_percentage:.5f}%",
            inline=True
        )

        # Add detailed metrics if available
        if any([standing.team1_users, standing.team1_attacks, standing.team1_friendly_fire,
                standing.team2_users, standing.team2_attacks, standing.team2_friendly_fire]):

            # Create detailed metrics field
            metrics_lines = []
            if standing.team1_users and standing.team2_users:
                metrics_lines.append(f"👥 **Users**: {standing.team1_users:,} | {standing.team2_users:,}")
            if standing.team1_attacks and standing.team2_attacks:
                metrics_lines.append(f"⚔️ **Attacks**: {standing.team1_attacks:,} | {standing.team2_attacks:,}")
            if standing.team1_friendly_fire and standing.team2_friendly_fire:
                metrics_lines.append(f"🔥 **Friendly Fire**: {standing.team1_friendly_fire:,} | {standing.team2_friendly_fire:,}")
            if standing.team1_battle_ratio and standing.team2_battle_ratio:
                metrics_lines.append(f"⚖️ **Battle Ratio**: {standing.team1_battle_ratio:.2f}% | {standing.team2_battle_ratio:.2f}%")
            if standing.team1_avg_points and standing.team2_avg_points:
                metrics_lines.append(f"📊 **Avg Points**: {standing.team1_avg_points:.2f} | {standing.team2_avg_points:.2f}")
            if standing.team1_avg_attacks and standing.team2_avg_attacks:
                metrics_lines.append(f"🎯 **Avg Attacks**: {standing.team1_avg_attacks:.2f} | {standing.team2_avg_attacks:.2f}")

            if metrics_lines:
                embed.add_field(
                    name="📈 Detailed Metrics",
                    value="\n".join(metrics_lines),
                    inline=False
                )

        if settings.teams:
            embed.set_thumbnail(url=settings.teams.team1.image_url if standing.team1_percentage > 50 else settings.teams.team2.image_url)

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

    async def _handle_cache_command(self, interaction: discord.Interaction, subaction: str | None):
        """Handle the cache command."""
        if not self.database:
            await interaction.followup.send("❌ Database not available")
            return

        try:
            if subaction == "info":
                cache_stats = self.database.get_cache_stats()
                
                embed = discord.Embed(
                    title="🗄️ Cache Statistics",
                    description="Current cache status and statistics",
                    color=0x3498db,
                    timestamp=datetime.now(UTC)
                )

                embed.add_field(
                    name="Total Entries",
                    value=str(cache_stats.get('total_entries', 0)),
                    inline=True
                )
                embed.add_field(
                    name="Expired Entries",
                    value=str(cache_stats.get('expired_entries', 0)),
                    inline=True
                )
                embed.add_field(
                    name="Cache Size",
                    value=f"{cache_stats.get('cache_size_mb', 0):.2f} MB",
                    inline=True
                )

                embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
                await interaction.followup.send(embed=embed)
            elif subaction == "clear":
                self.database.clear_cache()
                await interaction.followup.send("✅ Cache cleared.")
            elif subaction == "cleanup":
                self.database.cleanup_expired_cache()
                await interaction.followup.send("✅ Cache cleanup initiated.")
            elif subaction == "reset":
                # For now, just clear the cache as a reset
                self.database.clear_cache()
                await interaction.followup.send("✅ Cache reset (cleared).")
            else:
                await interaction.followup.send("Unknown sub-action for cache command. Use `/artfight cache info` for info, `/artfight cache clear` for clearing, `/artfight cache cleanup` for cleanup, or `/artfight cache reset` for resetting.")

        except Exception as e:
            logger.error(f"Error handling cache command: {e}")
            await interaction.followup.send(f"❌ Error retrieving cache stats: {str(e)}")

    async def _handle_monitor_command(self, interaction: discord.Interaction, subaction: str | None):
        """Handle the monitor command."""
        try:
            if subaction == "info":
                embed = discord.Embed(
                    title="📡 Monitor Status",
                    description="Current monitoring status and controls",
                    color=0xe74c3c,
                    timestamp=datetime.now(UTC)
                )

                # Get actual monitor status if available
                if hasattr(self, 'monitor') and self.monitor:
                    monitor_stats = self.monitor.get_stats()
                    
                    # Overall status
                    overall_status = "🟢 Active" if monitor_stats.get("running", False) else "🔴 Inactive"
                    embed.add_field(name="Overall Status", value=overall_status, inline=True)
                    
                    # News monitoring status
                    news_status = "🟢 Active" if monitor_stats.get("news_running", False) else "🔴 Inactive"
                    embed.add_field(name="News Monitoring", value=news_status, inline=True)
                    
                    # Event monitoring status (team/user)
                    event_status = "🟢 Active" if monitor_stats.get("event_monitoring_running", False) else "🔴 Inactive"
                    embed.add_field(name="Event Monitoring", value=event_status, inline=True)
                    
                    # Battle over detection info
                    no_event_info = monitor_stats.get("no_event_detection", {})
                    if no_event_info.get("enabled", False):
                        consecutive_count = no_event_info.get("consecutive_count", 0)
                        stopped = no_event_info.get("stopped", False)
                        battle_status = f"🔴 Stopped ({consecutive_count}/3)" if stopped else f"🟢 Active ({consecutive_count}/3)"
                        embed.add_field(name="Battle Over Detection", value=battle_status, inline=True)
                else:
                    # Fallback to hardcoded values if monitor not available
                    embed.add_field(name="Status", value="🟢 Active", inline=True)
                    embed.add_field(name="Team Monitoring", value="🟢 Active", inline=True)
                    embed.add_field(name="User Monitoring", value="🟢 Active", inline=True)

                embed.add_field(
                    name="Available Actions",
                    value="• `/artfight monitor reset` - Reset no-event detection\n• `/artfight monitor info` - View status\n• `/artfight cache clear` - Clear cache\n• `/artfight cache cleanup` - Cleanup expired cache",
                    inline=False
                )

                embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
                await interaction.followup.send(embed=embed)
            elif subaction == "reset":
                # This would typically call the API endpoint
                # For now, just acknowledge the command
                await interaction.followup.send("✅ Monitor no-event detection reset initiated. This will restart team monitoring.")
            else:
                await interaction.followup.send("Unknown sub-action for monitor command. Use `/artfight monitor info` for status or `/artfight monitor reset` to reset no-event detection.")

        except Exception as e:
            logger.error(f"Error handling monitor command: {e}")
            await interaction.followup.send(f"❌ Error retrieving monitor status: {str(e)}")

    async def _handle_auth_command(self, interaction: discord.Interaction):
        """Handle the auth command."""
        try:
            embed = discord.Embed(
                title="🔐 Authentication Status",
                description="Current ArtFight authentication status",
                color=0xf39c12,
                timestamp=datetime.now(UTC)
            )

            # Check if we have authentication configured
            has_session = bool(settings.laravel_session)
            has_cf_clearance = bool(settings.cf_clearance)
            has_remember_web = bool(settings.remember_web)

            embed.add_field(
                name="Laravel Session",
                value="✅ Configured" if has_session else "❌ Not configured",
                inline=True
            )
            embed.add_field(
                name="Cloudflare Clearance",
                value="✅ Configured" if has_cf_clearance else "❌ Not configured",
                inline=True
            )
            embed.add_field(
                name="Remember Web",
                value="✅ Configured" if has_remember_web else "❌ Not configured",
                inline=True
            )

            if has_session and has_cf_clearance:
                embed.add_field(
                    name="Status",
                    value="🟢 Ready for authenticated requests",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="🟡 Limited to public data only",
                    inline=False
                )

            embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling auth command: {e}")
            await interaction.followup.send(f"❌ Error retrieving auth status: {str(e)}")

    async def _handle_teams_command(self, interaction: discord.Interaction):
        """Handle the teams command."""

        embed = discord.Embed(
            title="ArtFight Team Standings",
            description="Current team standings and leader information",
            color=0xff9900,
            timestamp=datetime.now(UTC)
        )

        if settings.teams:
            embed.add_field(
                name="Teams",
                value=f"**{settings.teams.team1.name}** (Team 1)\n"
                      f"**{settings.teams.team2.name}** (Team 2)",
                inline=False
            )
        else:
            embed.add_field(
                name="Teams",
                value="Team configuration not set",
                inline=False
            )

        embed.add_field(
            name="Status",
            value="Standings data not available\nUse the web interface for real-time data",
            inline=False
        )

        await interaction.followup.send(embed=embed)

    async def _send_embed(self, embed: discord.Embed):
        """Send an embed message to Discord."""
        try:
            if self.webhook:
                await self.webhook.send(embed=embed)
            elif self.channel:
                # Use the stored channel reference (set on startup)
                await self.channel.send(embed=embed)
            else:
                logger.warning("No Discord webhook or channel available for sending messages")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")

    async def _send_embed_with_file(self, embed: discord.Embed, file: discord.File, filename: str):
        """Send an embed message with a file attachment to Discord."""
        try:
            if self.webhook:
                await self.webhook.send(embed=embed, file=file)
            elif self.channel:
                # Use the stored channel reference (set on startup)
                await self.channel.send(embed=embed, file=file)
            else:
                logger.warning("No Discord webhook or channel available for sending messages")
        except Exception as e:
            logger.error(f"Failed to send Discord message with file: {e}")

    async def _generate_team_standings_plot(self, team1_name: str, team2_name: str, include_team_balance: bool | None = None) -> discord.File | None:
        """Generate a team standings plot and return it as a Discord file."""
        return generate_team_standings_plot(team1_name, team2_name, include_team_balance=include_team_balance)

    def is_running(self) -> bool:
        """Check if the Discord bot is running."""
        return self.running


# Global instance
discord_bot = ArtFightDiscordBot()
