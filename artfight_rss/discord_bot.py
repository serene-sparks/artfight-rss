"""Discord bot integration for ArtFight webhook service."""

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

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
        except asyncio.TimeoutError:
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
            value=f"{standing.team1_percentage:.5f}%",
            inline=True
        )
        embed.add_field(
            name=team2_name,
            value=f"{100 - standing.team1_percentage:.5f}%",
            inline=True
        )

        if settings.teams:
            embed.set_thumbnail(url=settings.teams.team1.image_url if standing.team1_percentage > 50 else settings.teams.team2.image_url)

        embed.set_footer(text="ArtFight Bot", icon_url="https://artfight.net/favicon.ico")

        # Generate and attach team standings plot
        try:
            plot_file = await self._generate_team_standings_plot(team1_name, team2_name)
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

    async def _generate_team_standings_plot(self, team1_name: str, team2_name: str) -> discord.File | None:
        """Generate a team standings plot and return it as a Discord file."""
        try:
            # Import matplotlib here to avoid adding it as a main dependency
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import sqlite3
            
            # Get database path
            db_path = settings.db_path
            if not db_path.exists():
                logger.warning("Database file not found for plotting")
                return None
            
            # Fetch standings data
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT team1_percentage, fetched_at, leader_change
                FROM team_standings
                ORDER BY fetched_at ASC
            """)
            
            data = cursor.fetchall()
            conn.close()
            
            if not data:
                logger.warning("No team standings data found for plotting")
                return None
            
            # Parse the data
            team1_percentages = []
            fetched_times = []
            leader_changes = []
            
            for row in data:
                team1_percentage, fetched_at_str, leader_change = row
                
                # Parse the datetime string
                try:
                    fetched_at = datetime.fromisoformat(fetched_at_str)
                except ValueError:
                    # Try alternative format if needed
                    fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")
                
                team1_percentages.append(team1_percentage)
                fetched_times.append(fetched_at)
                leader_changes.append(bool(leader_change))
            
            # Create the plot
            fig, ax = plt.subplots(1, 1, figsize=(12, 8))
            
            # Plot team percentages over time
            ax.plot(fetched_times, team1_percentages, 'b-', linewidth=2, label=f'{team1_name} %')
            
            # Add a horizontal line at 50% to show the center
            ax.axhline(y=50, color='gray', linestyle='--', alpha=0.7, label='Center (50%)')
            
            # Highlight leader changes
            leader_change_times = [fetched_times[i] for i in range(len(leader_changes)) if leader_changes[i]]
            leader_change_percentages = [team1_percentages[i] for i in range(len(leader_changes)) if leader_changes[i]]
            
            if leader_change_times:
                ax.scatter(leader_change_times, leader_change_percentages, 
                           color='orange', s=100, zorder=5, label='Leader Change', marker='*')
            
            # Format the plot
            ax.set_ylabel('Percentage (%)', fontsize=12)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_title(f'ArtFight Team Standings Over Time\n{team1_name} vs {team2_name}', 
                          fontsize=14, fontweight='bold')
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            
            # Calculate y-axis limits based on largest distance from 50%
            differences = [abs(p - 50) for p in team1_percentages]
            max_distance = max(differences)
            
            # Set min and max at 15% more than the largest distance from 50%
            padding = max_distance * 0.15
            y_min = max(0, 50 - max_distance - padding)
            y_max = min(100, 50 + max_distance + padding)
            
            ax.set_ylim(y_min, y_max)
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Adjust layout
            plt.tight_layout()
            
            # Save plot to bytes buffer
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            
            # Close the figure to free memory
            plt.close(fig)
            
            # Create Discord file
            file = discord.File(buffer, filename="team_standings.png")
            
            logger.info("Team standings plot generated successfully")
            return file
            
        except ImportError:
            logger.warning("matplotlib not available for plotting")
            return None
        except Exception as e:
            logger.error(f"Failed to generate team standings plot: {e}")
            return None

    def is_running(self) -> bool:
        """Check if the Discord bot is running."""
        return self.running


# Global instance
discord_bot = ArtFightDiscordBot()
