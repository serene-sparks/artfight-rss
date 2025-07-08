# ArtFight RSS Service

A Python service that monitors ArtFight profiles and team standings and provides RSS feeds.

## Features

- **Profile Monitoring**: Watch multiple ArtFight user profiles for new attacks and defenses.
- **Team Standings**: Monitor team standings with color-based parsing and leader change detection.
- **RSS Feed Generation**: Creates RSS feeds compatible with popular RSS bots.
- **Direct Discord Integration**: Provides real-time, rich embed notifications for new activity, removing the need for an external RSS bot.
- **Respectful Scraping**: Configurable rate-limiting, request delays, and smart pagination to be kind to ArtFight servers.
- **Persistent Storage**: Uses a SQLite database to cache data and track history, minimizing redundant requests.
- **Access Control**: A user whitelist can be configured to control which profiles can be monitored.

## Installation

### Quick "production" Setup (Recommended)

This setup uses `systemd` to run the service in the background on a Linux server.

#### 1. Create a Dedicated User
It's good practice to run services under a dedicated, non-privileged user account.
```bash
# Create a system user for the service
sudo useradd -r -s /bin/false artfight-rss
```

#### 2. Clone the Repository
```bash
# Clone to a standard location like /opt
sudo git clone <your-repo-url> /opt/artfight-rss
cd /opt/artfight-rss

# Set ownership to the service user
sudo chown -R artfight-rss:artfight-rss /opt/artfight-rss
```

#### 3. Configure the Service
```bash
# As the service user, copy the example configuration
sudo -u artfight-rss cp config.example.toml config.toml

# Edit the configuration file
sudo -u artfight-rss nano config.toml
```

**Important Configuration Steps:**
- Set your ArtFight authentication cookies (`laravel_session`, `cf_clearance`). See the "Authentication" section below.
- To use the Discord bot, set `discord_enabled = true` and provide a bot token or webhook URL.
- It is highly recommended to add usernames to the `whitelist` if your service will be publicly accessible.

#### 4. Install as a Systemd Service
```bash
# Run the included setup script
sudo python scripts/setup_systemd.py
```

The script will automatically:
- Create a Python virtual environment for the project.
- Install all necessary dependencies.
- Create and enable a `systemd` service file.
- Start the service.

#### 5. Verify Installation
```bash
# Check the service status
sudo systemctl status artfight-rss

# View live logs
sudo journalctl -u artfight-rss -f

# Test the health check endpoint
curl http://localhost:8000/health
```

### Manual Installation (Development)

This method is for running the service manually, for example, during development.

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
nano config.toml
```

#### 3. Run
```bash
# Run in development mode with debug logging enabled
DEBUG=1 uv run python -m artfight_rss.main

# Run in production mode
uv run uvicorn artfight_rss.main:app --host 0.0.0.0 --port 8000
```

## Disclaimer

- This is an unofficial project and is not affiliated with ArtFight.net or its developers.
- Please use this service responsibly. Be mindful of the ArtFight servers and do not set request intervals too low.
- The user of this service is solely responsible for any consequences of its use.

## AI Disclosure
This project was created with significant assistance from AI tools (Cursor/Claude). This is a common practice in modern software development, and in the spirit of transparency, it's disclosed here. All AI-generated code was reviewed, revised, and tested by a human.

## Configuration

### Authentication

ArtFight requires you to be logged in to view profiles. You must provide session cookies in `config.toml`.

1.  **Log into ArtFight.net** in your web browser.
2.  **Open Developer Tools** (usually F12) and go to the "Network" tab.
3.  **Refresh the page** and click on any request to `artfight.net`.
4.  In the request details, find the **Request Headers** section and locate the `Cookie` header.
5.  **Copy the values** for `laravel_session` and `cf_clearance`.
6.  **Add them to your `config.toml` file:**
    ```toml
    laravel_session = "your_laravel_session_value_here"
    cf_clearance = "your_cf_clearance_value_here"
    ```

### General

-   `request_interval_sec`: Minimum seconds between requests for the same user (default: 300).
-   `team_check_interval_sec`: How often to check team standings (default: 3600).
-   `page_request_delay_sec`: Base delay between fetching pages of attacks/defenses (default: 3.0).
-   `page_request_wobble`: Random "wobble" added to the page delay to make requests less uniform (default: 0.2, which means ±20%).

### Teams

You can monitor team standings by configuring the teams and their colors. If colors are not set, the service might not be able to correctly identify the teams.

```toml
[teams]
team1 = { name = "Fossils", color = "#BA8C25", image_url = "https://images.artfight.net/2025/2025_Fossils.png" }
team2 = { name = "Crystals", color = "#D35E88", image_url = "https://images.artfight.net/2025/2025_Crystals.png" }
```

### Whitelist and Monitored Users

-   `whitelist`: A list of ArtFight usernames that are allowed to be requested via the API. **Highly recommended to prevent abuse.**
-   `monitor_list`: A list of users to monitor automatically for the Discord notifications.

```toml
whitelist = [
    "example_user",
    "another_user"
]

monitor_list = [
    "example_user"
]
```

## Usage

### Service Management (Systemd)
If you used the `setup_systemd.py` script, you can manage the service with these commands:

-   **View status:** `sudo systemctl status artfight-rss`
-   **View logs:** `sudo journalctl -u artfight-rss -f`
-   **Start/Stop/Restart:** `sudo systemctl start|stop|restart artfight-rss`
-   **Enable/Disable on boot:** `sudo systemctl enable|disable artfight-rss`

### Updating the Service
To update the application and its dependencies for a systemd installation:

```bash
# As the service user, update the code from git
sudo -u artfight-rss git pull

# As the service user, update dependencies
sudo -u artfight-rss /opt/artfight-rss/venv/bin/uv sync --quiet

# Restart the service to apply changes
sudo systemctl restart artfight-rss
```

## API Endpoints

The service provides several RESTful endpoints for fetching data.

#### Health and Status
- `GET /health`
  - A simple health check. Returns `{"status": "healthy"}` if the service is running.
- `GET /auth/status`
  - Checks if the provided authentication cookies are configured and still valid.

#### RSS Feeds
All RSS endpoints support an optional `limit` query parameter (e.g., `?limit=25`) to control the number of items returned. The default and maximum limit is configured in `config.toml`.

- `GET /rss/attacks/{usernames}`
  - Generates an RSS feed for attacks against one or more users.
  - For multiple users, separate usernames with a `+` (e.g., `user1+user2`).
- `GET /rss/defenses/{usernames}`
  - Generates an RSS feed for defenses made by one or more users.
- `GET /rss/combined/{usernames}`
  - Generates a single feed containing both attacks and defenses for the specified users.
- `GET /rss/standings`
  - Generates an RSS feed for team standing changes. It includes daily updates and special entries for leader changes.

#### Webhooks & Cache
- `POST /webhook/teams`
  - Manually triggers a check for team standings.
- `GET /cache/stats`
  - Returns statistics about the internal cache.
- `POST /cache/clear`
  - Clears the entire cache.
- `POST /cache/cleanup`
  - Clears only expired entries from the cache.

## RSS Integration

The generated RSS feeds can be used with any standard RSS reader or bot, such as MonitoRSS for Discord.

**Example URLs:**
- **Attacks on `example_user`:** `http://your-server-ip:8000/rss/attacks/example_user`
- **Defenses by `user1` and `user2`:** `http://your-server-ip:8000/rss/defenses/user1+user2`
- **Team Standings:** `http://your-server-ip:8000/rss/standings`

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
   monitor_list = [
       "example_user"
   ]
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
monitor_list = [
    "artist1",
    "artist2"
]
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

### Respectful Scraping
The service is designed to be as kind as possible to ArtFight's servers:
- **Early termination**: Stops fetching pages when no new content is found
- **Configurable delays**: Random delays between requests to avoid detection
- **Smart caching**: Minimizes redundant requests through persistent storage
- **Rate limiting**: Built-in rate limiting to prevent overwhelming the server

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

### Graceful Shutdown

The service supports graceful shutdown with proper signal handling:

- **Ctrl+C (SIGINT)**: Graceful shutdown with cleanup
- **SIGTERM**: Graceful shutdown for systemd services
- **Timeout Protection**: 5-second timeout for component shutdown
- **Background Task Cleanup**: Proper cancellation of monitoring loops
- **Discord Bot**: Proper startup and shutdown with timeout protection

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
- Test RSS feed directly: `curl http://localhost:8000/rss/attacks/username`

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
This project was made with heavy assistance from AI. This can be very
controvertial in art spaces and I want to clarify why I decided to go this
route.

AI in software engineering is practically mandatory for modern employment. I
don't like this. I would love to write code by hand, but I also need to be
hirable and experienced with the tools of the trade. Any and all AI use is done
with heavy supervision and a lot of handholding.

- Estimated percentage of code initially written by AI prompting: 80%.
- Estimated percentage of code revised by a human: 60%

Tools used:
- Cursor
- Claude
