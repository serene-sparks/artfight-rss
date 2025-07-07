# ArtFight RSS Service

A Python RSS service that monitors ArtFight profiles and team standings

## Features

- **Profile Monitoring**: Watch multiple ArtFight user profiles for new attacks and defenses
- **Team Standings**: Monitor team standings with color-based parsing and leader change detection
- **RSS Feed Generation**: Creates RSS feeds for existing Discord RSS bots
- **Rate Limiting**: Configurable request intervals to avoid overwhelming ArtFight
- **SQLite Caching**: Persistent SQLite-based caching to minimize redundant requests
- **Whitelist Support**: Control which profiles can be monitored
- **Historical Tracking**: Preserve team standings history and detect leader changes
- **Optimized Pagination**: Early termination when no new content is found

## Installation

### Quick "production" Setup (Recommended)

#### 1. Create a Dedicated User
```bash
# Create a system user for the service
sudo useradd -r -s /bin/false artfight-rss

# Create a group (optional, will use user name as group)
sudo groupadd artfight-rss
```

#### 2. Clone the Repository
```bash
# Clone to a suitable location
sudo git clone <your-repo-url> /opt/artfight-rss
cd /opt/artfight-rss

# Set ownership to the service user
sudo chown -R artfight-rss:artfight-rss /opt/artfight-rss
```

#### 3. Configure the Service
```bash
# Copy the example configuration
sudo -u artfight-rss cp config.example.toml config.toml

# Edit the configuration (as the service user)
sudo -u artfight-rss nano config.toml
```

**Important Configuration Steps:**
- Set your ArtFight authentication cookies (`laravel_session`, `cf_clearance`, `remember_web`)
- Configure team colors to match ArtFight's progress bars
- Add usernames to the whitelist (highly recommended)
- Adjust request intervals if needed

#### 4. Install as Systemd Service
```bash
# Run the systemd setup script
sudo python scripts/setup_systemd.py
```

The script will:
- Create a Python virtual environment
- Install all dependencies
- Create and enable the systemd service
- Start the service automatically

#### 5. Verify Installation
```bash
# Check service status
sudo systemctl status artfight-rss

# View logs
sudo journalctl -u artfight-rss -f

# Test the service
curl http://localhost:8000/health
```

### Manual Installation (Development)

If you prefer to run manually or for development:

#### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd artfight-webhook

# Install dependencies using uv
uv sync
```

#### 2. Configure
```bash
cp config.example.toml config.toml
# Edit config.toml with your settings
```

#### 3. Run
```bash
# Development
DEBUG=1 uv run python -m artfight_rss.main

# Production
uv run uvicorn artfight_rss.main:app --host 0.0.0.0 --port 8000
```

## Warnings

- This service is not affiliated with ArtFight.net or any of its developers.
- This service is not responsible for any data loss or other issues that may occur.
- This service is not responsible for any legal issues that may arise from the use of this service.
- This service is designed to be used for personal use only.
- This service is designed by a professional moron and is not guaranteed to work.
- This service is designed by a professional moron and is not guaranteed to be secure.
- Use at your own risk.
- Be kind to the ArtFight server. Please.
- Did I mention that this service is designed by a professional moron?

## Configuration

### Authentication Setup

Since ArtFight requires authentication, you'll need to provide session cookies:

1. **Log into ArtFight.net** in your browser
2. **Open Developer Tools** (F12) and go to the Network tab
3. **Navigate to any page** on ArtFight (like your profile)
4. **Find the request** and look at the Cookie header
5. **Extract these cookies:**
   - `laravel_session` - The main session cookie
   - `cf_clearance` - Cloudflare clearance cookie
   - `remember_web` - Remember web cookie (optional but recommended)

6. **Add them to your `config.toml` file:**
   ```toml
   laravel_session = "your_laravel_session_value_here"
   cf_clearance = "your_cf_clearance_value_here"
   remember_web = "your_remember_web_value_here"
   ```

### Configuration Options

The service uses a TOML configuration file with the following sections:

#### General Settings
- `request_interval_sec`: Minimum seconds between requests to ArtFight (default: 300)
- `team_check_interval_sec`: How often to check team standings (default: 3600)
- `page_request_delay_sec`: Delay between page requests during pagination (default: 3.0)
- `page_request_wobble`: Random wobble factor for delays (default: 0.2)

#### Team Configuration
If you want to monitor team standings, you can configure the teams and their colors.

If the colors are not set, the first bar will be used as team1. This is not recommended as the first bar may not be the correct team.

```toml
[teams]
team1 = { name = "Fossils", color = "#BA8C25" }
team2 = { name = "Crystals", color = "#D35E88" }
```

#### Whitelist
If you want to limit the users that can be monitored, you can add them to the whitelist.
This is highly, highly recommended. If you don't, you will probably be banned from ArtFight if some bot decides to scrape your instance.

```toml
whitelist = [
    "example_user",
    "another_user"
]
```

## Usage

### Service Management (Systemd Installation)

If you installed using the systemd setup script:

```bash
# View service status
sudo systemctl status artfight-rss

# View logs
sudo journalctl -u artfight-rss -f

# Stop service
sudo systemctl stop artfight-rss

# Start service
sudo systemctl start artfight-rss

# Restart service
sudo systemctl restart artfight-rss

# Disable service (won't start on boot)
sudo systemctl disable artfight-rss

# Enable service (will start on boot)
sudo systemctl enable artfight-rss
```

### Manual Usage (Development)

For development or manual installation:

```bash
# Development mode with debug logging
DEBUG=1 uv run python -m artfight_rss.main

# Production mode
uv run uvicorn artfight_rss.main:app --host 0.0.0.0 --port 8000
```

### Updating the Service

To update dependencies or the application:

```bash
# Update dependencies (systemd installation)
sudo -u artfight-rss /opt/artfight-rss/venv/bin/pip install -e /opt/artfight-rss --upgrade

# Restart the service
sudo systemctl restart artfight-rss
```

## API Endpoints

- `GET /health`: Health check
- `GET /auth/status`: Authentication status and information
- `GET /rss/{username}/attacks`: RSS feed for a specific user's attacks
- `GET /rss/{username}/defenses`: RSS feed for a specific user's defenses
- `GET /rss/standings`: RSS feed for team standing changes (daily updates + leader changes)
- `POST /webhook/teams`: Manual trigger for team check
- `GET /cache/stats`: Cache statistics
- `POST /cache/clear`: Clear cache
- `POST /cache/cleanup`: Cleanup expired cache

## RSS Integration

The service generates RSS feeds that can be consumed by an RSS reader. The project is designed with Discord in mind, but it can be used with any RSS reader.

- **User Attack Feeds**: `/rss/{username}/attacks` - Contains recent attacks on the user
- **User Defense Feeds**: `/rss/{username}/defenses` - Contains recent defenses by the user
- **Team Changes Feed**: `/rss/standings` - Contains team standing changes (daily updates and leader changes)

### Example RSS Bot Configuration

For Discord RSS bots like [RSS Bot](https://github.com/DarkView/RSSCord) or similar:

1. **User Attack Feed:**
   ```
   URL: http://your-server:8000/rss/username
   ```

2. **User Defense Feed:**
   ```
   URL: http://your-server:8000/rss/username/defenses
   ```

4. **Team Changes Feed:**
   ```
   URL: http://your-server:8000/rss/standings
   ```

## Discord Bot Integration

The service now includes direct Discord bot functionality with rich embed messages, eliminating the need for external RSS bots.

### Features

- **Rich Embed Messages**: Beautiful Discord embeds with images, colors, and formatted text
- **Real-time Notifications**: Instant notifications for new attacks, defenses, and team changes
- **Slash Commands**: Interactive bot commands for status and statistics
- **Dual Mode Support**: Both bot token and webhook modes supported
- **Configurable Notifications**: Enable/disable specific notification types
- **User Monitoring**: Monitor specific users for new activity

### Setup

#### Option 1: Discord Bot Token (Recommended)

1. **Create a Discord Application:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Go to the "Bot" section and click "Add Bot"
   - Copy the bot token

2. **Configure Bot Permissions:**
   - In the Bot section, enable these permissions:
     - Send Messages
     - Use Slash Commands
     - Embed Links
     - Attach Files
   - Copy the application ID for guild-specific commands

3. **Invite Bot to Server:**
   - Go to OAuth2 > URL Generator
   - Select "bot" scope
   - Select the permissions above
   - Use the generated URL to invite the bot

4. **Update Configuration:**
   ```toml
   # Discord Bot Configuration
   discord_enabled = true
   discord_token = "your_bot_token_here"
   discord_guild_id = 123456789012345678  # Optional: for guild-specific commands
   discord_channel_id = 123456789012345678  # Channel for notifications
   
   # Notification settings
   discord_notify_attacks = true
   discord_notify_defenses = true
   discord_notify_team_changes = true
   discord_notify_leader_changes = true
   
   # User monitoring
   [[users]]
   username = "example_user"
   enabled = true
   ```

#### Option 2: Discord Webhook

1. **Create Webhook:**
   - In your Discord server, go to Server Settings > Integrations > Webhooks
   - Click "New Webhook" and give it a name
   - Copy the webhook URL

2. **Update Configuration:**
   ```toml
   discord_enabled = true
   discord_webhook_url = "https://discord.com/api/webhooks/..."
   
   # Notification settings
   discord_notify_attacks = true
   discord_notify_defenses = true
   discord_notify_team_changes = true
   discord_notify_leader_changes = true
   ```

### Bot Commands

When using bot token mode, the following slash commands are available:

- `/artfight stats` - Show bot statistics and status
- `/artfight status` - Show bot configuration and settings
- `/artfight teams` - Show current team standings
- `/artfight help` - Show help and available commands

### Notification Types

#### Attack Notifications
- **Trigger**: New attack detected for monitored users
- **Content**: Attack title, attacker, defender, description, and image
- **Color**: Red theme with attack emoji

#### Defense Notifications
- **Trigger**: New defense detected for monitored users
- **Content**: Defense title, defender, attacker, description, and image
- **Color**: Teal theme with shield emoji

#### Team Standing Updates
- **Trigger**: Regular team standing checks
- **Content**: Current percentages, leading team, and team images
- **Color**: Team-specific colors

#### Leader Change Alerts
- **Trigger**: When the leading team changes
- **Content**: Special celebration message with team information
- **Color**: Team-specific colors with crown emoji

### Configuration Options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `discord_enabled` | bool | false | Enable Discord bot functionality |
| `discord_token` | string | null | Discord bot token (required for bot mode) |
| `discord_guild_id` | int | null | Discord guild ID for guild-specific commands |
| `discord_channel_id` | int | null | Discord channel ID for notifications |
| `discord_webhook_url` | string | null | Discord webhook URL (alternative to bot) |
| `discord_notify_attacks` | bool | true | Send notifications for new attacks |
| `discord_notify_defenses` | bool | true | Send notifications for new defenses |
| `discord_notify_team_changes` | bool | true | Send notifications for team changes |
| `discord_notify_leader_changes` | bool | true | Send notifications for leader changes |

### User Monitoring

To monitor specific users for new attacks and defenses:

```toml
[[users]]
username = "artist1"
enabled = true

[[users]]
username = "artist2"
enabled = true
```

The bot will check these users at the configured `request_interval` and send Discord notifications for any new activity.

### Troubleshooting Discord Bot

#### Bot Not Responding
- Verify the bot token is correct
- Check that the bot has proper permissions
- Ensure the bot is online in your server

#### No Notifications
- Verify `discord_enabled = true` in config
- Check notification settings are enabled
- Ensure monitored users are configured
- Check bot logs for errors

#### Bot Startup Timeout (Remote Servers)
If you're getting "Discord bot startup timed out" errors on remote servers:

1. **Increase timeout**: Set `discord_startup_timeout = 300` in your config (5 minutes)
2. **Test connectivity**: Run `python scripts/debug_discord_timeout.py`
3. **Check network**: Ensure server can reach Discord API (no firewall/proxy blocking)
4. **Rate limiting**: Discord may rate limit connections from new IPs
5. **Alternative**: Use webhook mode instead of bot mode for notifications

Common causes:
- Slow network connections on remote servers
- Discord API rate limiting for new connections
- Firewall or proxy blocking Discord connections
- Discord service issues

#### Webhook Issues
- Verify webhook URL is correct and not expired
- Check webhook permissions in Discord
- Ensure webhook is in the correct channel

## Team Standings Features

### Leader Change Detection
Automatically detects when the leading team changes and flags these events in the RSS feed with special titles like "Leader Change: Team Name takes the lead!"

### Historical Tracking
- Preserves all team standings history in the database
- Provides daily snapshots and leader change events
- Tracks statistics over time

### User Attack and Defense Feeds

### Kind as Possible to the ArtFight Server
- Early termination for scraping
- Configurable request delays with random wobble to avoid cloudflare detection. As much as this service is very kind to the ArtFight server, it's probably still not something they want. Please be kind to the server. Please.
- Efficient pagination with smart caching

## Logging and Monitoring

### Logging Configuration

The service uses a comprehensive logging system following FastAPI best practices:

#### Log Levels
- **DEBUG**: Detailed debugging information (headers, request/response content, parsing details)
- **INFO**: Important activity tracking (service startup, user monitoring, data fetching)
- **WARNING**: Non-critical issues (authentication failures, missing data)
- **ERROR**: Critical errors that need attention

#### Log Output
- **Console**: Human-readable format with timestamps and log levels
- **File**: Detailed format with module names and line numbers
- **Error File**: Separate file for ERROR level messages only

#### Log Files
- `logs/artfight-rss.log` - All log messages with detailed formatting
- `logs/artfight-rss-error.log` - Error messages only

#### Configuration
Logging is automatically configured based on the `debug` setting in your config:
- `debug = true`: DEBUG level for application modules, INFO for HTTP clients
- `debug = false`: INFO level for application modules, WARNING for HTTP clients

#### Testing Logging
```bash
# Test the logging configuration
python scripts/test_logging.py
```

#### Testing Shutdown Handling
```bash
# Test shutdown handling
python scripts/test_shutdown.py

# Test server startup and shutdown
python scripts/test_server_shutdown.py
```

### Graceful Shutdown

The service supports graceful shutdown with proper signal handling:

- **Ctrl+C (SIGINT)**: Graceful shutdown with cleanup
- **SIGTERM**: Graceful shutdown for systemd services
- **Timeout Protection**: 5-second timeout for component shutdown
- **Background Task Cleanup**: Proper cancellation of monitoring loops
- **Discord Bot**: Proper startup and shutdown with timeout protection
- **FastAPI Lifespan**: Uses FastAPI's lifespan context manager for proper startup/shutdown

#### Shutdown Behavior
- **Immediate Response**: The server responds to Ctrl+C within 1-2 seconds
- **Clean Cancellation**: Background tasks are cancelled gracefully
- **Discord Bot**: Bot startup and shutdown are handled with proper timeout protection
- **Monitor Loops**: Team monitoring loops are cancelled and cleaned up

#### Testing Shutdown
```bash
# Test automatic shutdown after 10 seconds
uv run python scripts/test_shutdown.py

# Test server shutdown handling
uv run python scripts/test_server_shutdown.py

# Test manual server startup and shutdown
uv run python scripts/test_manual_shutdown.py
```

#### Manual Testing
To test shutdown manually:
1. Start the server: `uv run python -m artfight_rss.main`
2. Wait for startup to complete (Discord bot login, etc.)
3. Press Ctrl+C in the terminal
4. The server should shut down gracefully within 3-5 seconds

### Health Checks
```bash
# Check if service is running
curl http://localhost:8000/health

# Check authentication status
curl http://localhost:8000/auth/status

# View statistics
curl http://localhost:8000/stats
```

## Architecture

- **FastAPI**: Web framework for API endpoints
- **BeautifulSoup**: HTML parsing for ArtFight pages
- **Pydantic**: Data validation and settings management
- **SQLite**: Persistent database for caching and history
- **TOML**: Configuration file format
- **uv**: Modern Python package management

## Development

Install development dependencies:
```bash
uv sync --extra dev
```

Run tests:
```bash
uv run pytest
```

Format code:
```bash
uv run black .
uv run isort .
```

Type checking:
```bash
uv run mypy .
```

Linting:
```bash
uv run ruff check .
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Using Docker

```bash
# Build image
docker build -t artfight-rss .

# Run container
docker run -d \
  --name artfight-rss \
  -p 8000:8000 \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/cache:/app/cache \
  artfight-rss
``` 

## Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status artfight-rss

# View detailed logs
sudo journalctl -u artfight-rss -n 50

# Check if config.toml exists and is readable
sudo -u artfight-rss test -r /opt/artfight-rss/config.toml && echo "Config OK" || echo "Config missing/unreadable"
```

#### Authentication Issues
- Ensure all required cookies are set in `config.toml`
- Check `/auth/status` endpoint: `curl http://localhost:8000/auth/status`
- Cookies may expire - refresh them from your browser

#### Permission Issues
```bash
# Fix ownership
sudo chown -R artfight-rss:artfight-rss /opt/artfight-rss

# Fix permissions
sudo chmod 755 /opt/artfight-rss
sudo chmod 755 /opt/artfight-rss/cache
```

#### RSS Feed Issues
- Verify usernames are in the whitelist
- Check service is running: `curl http://localhost:8000/health`
- Test RSS feed directly: `curl http://localhost:8000/rss/username/attacks`

#### Team Standings Issues
- Verify team colors match ArtFight's progress bars exactly
- Check both teams are configured in `config.toml`
- Monitor team checking: `curl http://localhost:8000/stats`

### Getting Help

1. **Check the logs**: `sudo journalctl -u artfight-rss -f`
2. **Verify configuration**: Ensure `config.toml` is properly formatted
3. **Test endpoints**: Use `curl` to test individual endpoints
4. **Check ArtFight**: Verify the website structure hasn't changed

## AI Disclosures
This project was made with heavy assistance from AI. This can be very controvertial in art spaces and I want to clarify why I decided to go this route.

AI in software engineering is practically mandatory for modern employment. I don't like this. I would love to write code by hand, but I also need to be hirable and experienced
with the tools of the trade. Any and all AI use is done with heavy supervision and a lot of handholding.

- Estimated percentage of code initially written by AI prompting: 80%.
- Estimated percentage of code revised by a human: 60%

Tools used:
- Cursor
- Claude