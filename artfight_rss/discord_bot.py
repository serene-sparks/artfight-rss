"""Discord bot integration for ArtFight webhook service."""

import asyncio
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import ClientSession

from .config import settings
from .logging_config import get_logger
from .models import ArtFightAttack, ArtFightDefense, TeamStanding

logger = get_logger(__name__)


class ArtFightDiscordBot:
    """Discord bot for ArtFight notifications and commands."""

    def __init__(self):
        """Initialize the Discord bot."""
        self.bot: commands.Bot | None = None
        self.webhook: discord.Webhook | None = None
        self.channel: discord.TextChannel | None = None
        self.running = False
        self.ready_event = asyncio.Event()
        self.bot_task: asyncio.Task | None = None

    async def start(self):
        """Start the Discord bot."""
        if not settings.discord_enabled:
            logger.info("Discord bot disabled in configuration")
            return

        if not settings.discord_token and not settings.discord_webhook_url:
            logger.warning("Discord bot enabled but no token or webhook URL provided")
            return

        try:
            if settings.discord_token:
                # Start bot in background task to avoid blocking
                import asyncio
                self.bot_task = asyncio.create_task(self._start_bot())
                
                # Wait for the bot to be ready with timeout
                startup_timeout = float(settings.discord_startup_timeout)
                logger.info(f"Waiting for Discord bot to be ready (timeout: {startup_timeout}s)...")
                await asyncio.wait_for(self.ready_event.wait(), timeout=startup_timeout)
                logger.info("Discord bot is ready and operational")
                
            elif settings.discord_webhook_url:
                await self._start_webhook()

            self.running = True
            logger.info("Discord bot started successfully")
        except asyncio.TimeoutError:
            logger.error(f"Discord bot failed to become ready within {settings.discord_startup_timeout}s")
            logger.error("This may be due to:")
            logger.error("- Invalid bot token")
            logger.error("- Bot not added to server")
            logger.error("- Incorrect permissions")
            logger.error("- Network connectivity issues")
            raise
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            raise

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
            except asyncio.TimeoutError:
                logger.warning("Discord bot task did not stop within timeout")

        # Close the bot if it exists
        if self.bot:
            try:
                await asyncio.wait_for(self.bot.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Discord bot did not close within timeout")

        logger.info("Discord bot stopped")

    async def _start_bot(self):
        """Start the Discord bot with slash commands."""
        intents = discord.Intents.default()
        # Only enable message content if we need it for commands
        # intents.message_content = True  # Commented out to avoid privileged intents

        self.bot = commands.Bot(command_prefix="!", intents=intents)

        @self.bot.event
        async def on_ready():
            if not self.bot:
                return
                
            logger.info(f"Discord bot logged in as {self.bot.user}")

            # Set up channel for notifications
            if settings.discord_channel_id:
                # Try to find the channel by searching through all guilds
                target_channel = None
                for guild in self.bot.guilds:
                    for channel in guild.text_channels:
                        if channel.id == settings.discord_channel_id:
                            target_channel = channel
                            break
                    if target_channel:
                        break

                if target_channel:
                    self.channel = target_channel
                    logger.info(f"Connected to notification channel: {self.channel.name}")
                else:
                    logger.warning(f"Could not find channel with ID: {settings.discord_channel_id}")
                    logger.warning("Available channels:")
                    for guild in self.bot.guilds:
                        logger.warning(f"  Guild: {guild.name}")
                        for channel in guild.text_channels:
                            logger.warning(f"    - {channel.name} (ID: {channel.id})")

            # Register slash commands after bot is ready
            try:
                await self._register_commands()
            except Exception as e:
                logger.warning(f"Failed to register slash commands: {e}")

            # Signal that the bot is ready
            self.ready_event.set()

        # Start the bot
        if not settings.discord_token:
            raise ValueError("Discord token is required for bot mode")
        
        # Start the bot (no timeout here, handled at higher level)
        try:
            logger.info("Starting Discord bot...")
            await self.bot.start(settings.discord_token)
        except asyncio.CancelledError:
            logger.info("Discord bot startup cancelled")
            raise
        except Exception as e:
            logger.error(f"Discord bot startup failed: {e}")
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
        @app_commands.describe(
            action="Action to perform",
            username="ArtFight username (for user-specific commands)"
        )
        @app_commands.choices(action=[
            app_commands.Choice(name="stats", value="stats"),
            app_commands.Choice(name="status", value="status"),
            app_commands.Choice(name="teams", value="teams"),
            app_commands.Choice(name="help", value="help"),
        ])
        async def artfight_command(
            interaction: discord.Interaction,
            action: str,
            username: str | None = None
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
        # This would need to be implemented to get actual stats from the monitor
        embed = discord.Embed(
            title="ArtFight Bot Statistics",
            description="Current bot status and statistics",
            color=0x00ff00,
            timestamp=datetime.now(UTC)
        )

        embed.add_field(name="Status", value="🟢 Running", inline=True)
        embed.add_field(name="Mode", value="Bot" if self.bot else "Webhook", inline=True)
        embed.add_field(name="Notifications", value="Enabled", inline=True)

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

        await interaction.followup.send(embed=embed)

    async def _handle_teams_command(self, interaction: discord.Interaction):
        """Handle the teams command."""
        # This would need to be implemented to get actual team standings
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

    async def _handle_help_command(self, interaction: discord.Interaction):
        """Handle the help command."""
        embed = discord.Embed(
            title="ArtFight Bot Help",
            description="Available commands and features",
            color=0x7289da,
            timestamp=datetime.now(UTC)
        )

        embed.add_field(
            name="Commands",
            value="`/artfight stats` - Show bot statistics\n"
                  "`/artfight status` - Show bot status and configuration\n"
                  "`/artfight teams` - Show team standings\n"
                  "`/artfight help` - Show this help message",
            inline=False
        )

        embed.add_field(
            name="Features",
            value="• Real-time attack notifications\n"
                  "• Real-time defense notifications\n"
                  "• Team standing updates\n"
                  "• Leader change alerts\n"
                  "• Rich embed messages with images",
            inline=False
        )

        embed.add_field(
            name="Support",
            value="For more information, visit the project repository or contact the bot administrator.",
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
            value=f"{standing.team1_percentage:.2f}%",
            inline=True
        )
        embed.add_field(
            name=team2_name,
            value=f"{100 - standing.team1_percentage:.2f}%",
            inline=True
        )

        if settings.teams:
            embed.set_thumbnail(url=settings.teams.team1.image_url if standing.team1_percentage > 50 else settings.teams.team2.image_url)

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

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
            value=f"{standing.team1_percentage:.2f}%",
            inline=True
        )
        embed.add_field(
            name=team2_name,
            value=f"{100 - standing.team1_percentage:.2f}%",
            inline=True
        )

        embed.add_field(
            name="🎉",
            value=f"Congratulations to **{new_leader}** for taking the lead!",
            inline=False
        )

        if settings.teams:
            embed.set_thumbnail(url=settings.teams.team1.image_url if standing.team1_percentage > 50 else settings.teams.team2.image_url)

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        await self._send_embed(embed)

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

    def is_running(self) -> bool:
        """Check if the Discord bot is running."""
        return self.running


# Global instance
discord_bot = ArtFightDiscordBot()
