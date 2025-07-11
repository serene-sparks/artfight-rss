# ArtFight RSS Service Setup Guide

This guide will help you set up the ArtFight RSS Service to monitor profiles and team standings, generating RSS feeds for Discord RSS bots.

## Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`
- Discord server with RSS bot permissions

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd artfight-webhook

# Install dependencies
uv sync
```

### 2. Configure Authentication

Since ArtFight requires authentication, you need to provide session cookies:

1. **Log into ArtFight.net** in your browser
2. **Open Developer Tools** (F12) and go to the Network tab
3. **Navigate to any page** on ArtFight (like your profile)
4. **Find the request** and look at the Cookie header
5. **Extract these cookies:**
   - `laravel_session` - The main session cookie
   - `cf_clearance` - Cloudflare clearance cookie
   - `remember_web` - Remember web cookie (optional but recommended)

### 3. Create Configuration

Copy the example configuration and edit it:

```bash
cp config.example.toml config.toml
```

Edit `config.toml` with your settings:

```toml
# ArtFight RSS Service Configuration

# General settings
request_interval = 300  # Minimum seconds between requests to ArtFight (5 minutes)
team_check_interval = 3600  # How often to check team standings (1 hour)
team_switch_threshold = 24  # Hours since last switch before forcing update
page_request_delay = 3.0  # Delay between page requests during pagination
page_request_wobble = 0.2  # Random wobble factor for delays

# ArtFight settings
artfight_base_url = "https://artfight.net"

# Authentication settings (REQUIRED)
laravel_session = "your_laravel_session_cookie_here"
cf_clearance = "your_cloudflare_clearance_cookie_here"
remember_web = "your_remember_web_cookie_here"

# Server settings
host = "0.0.0.0"
port = 8000
debug = true

# Team configuration
[teams]
team1 = { name = "Fossils", color = "#BA8C25" }
team2 = { name = "Crystals", color = "#D35E88" }

# User monitoring
monitor_list = [
    "your_artfight_username",
    "another_username"
]

# Whitelist of supported ArtFight profiles (optional)
# If empty, all profiles are allowed
whitelist = [
    "your_artfight_username",
    "another_username",
    "trusted_user"
]
```

### 4. Run the Service

#### Development
```bash
uv run python -m artfight_rss.main
```

#### Production - Manual Start
```bash
uv run uvicorn artfight_rss.main:app --host 0.0.0.0 --port 8000
```

#### Production - Systemd Service (Recommended)
For production deployment, install as a systemd service for automatic startup and management:

```bash
# Create a dedicated user (optional but recommended)
sudo useradd -r -s /bin/false artfight-rss

# Run the setup script
sudo python scripts/setup_systemd.py
```

The setup script will:
- Create a systemd service file at `/etc/systemd/system/artfight-rss.service`
- Set proper permissions and ownership
- Enable and start the service
- Configure automatic restarts

**Service Management:**
```bash
# View logs
journalctl -u artfight-rss -f

# Stop service
sudo systemctl stop artfight-rss

# Start service
sudo systemctl start artfight-rss

# Restart service
sudo systemctl restart artfight-rss

# Disable service
sudo systemctl disable artfight-rss
```

## Docker Deployment

### Using Docker Compose (Recommended)

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

## Configuration Details

### Team Configuration

The service uses team colors to accurately parse progress bars from ArtFight:

```toml
[teams]
team1 = { name = "Fossils", color = "#BA8C25" }
team2 = { name = "Crystals", color = "#D35E88" }
```

- **name**: Display name for the team in RSS feeds
- **color**: Hex color code that matches the team's progress bar on ArtFight

### User Monitoring

Configure which ArtFight users to monitor:

```toml
[[users]]
username = "user1"
enabled = true

[[users]]
username = "user2"
enabled = true
```

### Whitelist (Optional)

Control which profiles can be accessed via RSS feeds:

```toml
whitelist = [
    "user1",
    "user2",
    "trusted_user"
]
```

If the whitelist is empty or not configured, all profiles are allowed.

### Performance Settings

- `request_interval`: Minimum time between requests to avoid overwhelming ArtFight
- `team_check_interval`: How often to check for team standing updates
- `page_request_delay`: Delay between paginated requests
- `page_request_wobble`: Random variation in delays (±20% by default)

## API Endpoints

Once running, the service provides these endpoints:

### RSS Feeds
- `GET /rss/{username}` - RSS feed for user attacks
- `GET /rss/{username}/defenses` - RSS feed for user defenses
- `GET /rss/standings` - RSS feed for team standing changes (daily updates + leader changes)

### Management
- `GET /health` - Health check
- `GET /auth/status` - Authentication status and information
- `GET /stats` - Monitoring statistics
- `GET /users` - List configured users
- `POST /webhook/teams` - Manual team check trigger

### Cache Management
- `GET /cache/stats` - Cache statistics
- `POST /cache/clear` - Clear cache
- `POST /cache/cleanup` - Cleanup expired cache

## RSS Integration

The service generates RSS feeds that can be consumed by Discord RSS bots:

### Feed Types

1. **User Attack Feed**: `http://your-server:8000/rss/{username}`
   - Contains recent attacks on the specified user
   - Updates when new attacks are detected

2. **User Defense Feed**: `http://your-server:8000/rss/{username}/defenses`
   - Contains recent defenses by the specified user
   - Updates when new defenses are detected

3. **Team Changes Feed**: `http://your-server:8000/rss/standings`
   - Contains team standing changes (daily updates and leader changes)
   - Special titles for leader changes: "Leader Change: Team Name takes the lead!"

### Setting Up Discord RSS Bot

1. **Install a Discord RSS Bot** (examples):
   - [RSS Bot](https://github.com/DarkView/RSSCord)
   - [RSS Feed Bot](https://github.com/feather-rs/feather)
   - [RSS Bot](https://github.com/bestadamdagoat/RSShook)

2. **Add RSS Feeds:**
   ```
   User Attack Feed: http://your-server:8000/rss/username
User Defense Feed: http://your-server:8000/rss/username/defenses
Team Changes Feed: http://your-server:8000/rss/standings
   ```

3. **Configure Channels:**
   - Set up dedicated channels for different types of updates
   - Configure notification settings in your RSS bot

## Team Standings Features

### Color-Based Parsing
The service uses configured team colors to accurately identify which progress bar corresponds to which team, ensuring correct parsing regardless of the order they appear on the page.

### Leader Change Detection
Automatically detects when the leading team changes and creates special RSS entries with titles like "Leader Change: Fossils takes the lead!"

### Historical Tracking
- All team standings are preserved in the database
- Daily snapshots are created for tracking over time
- Leader changes are flagged and tracked separately

### Performance Optimizations
- Early termination when no new defenses are found on the first page
- Configurable delays with random wobble to avoid detection
- Smart caching to minimize redundant requests

## Monitoring and Logs

### Health Checks
```bash
# Check if service is running
curl http://localhost:8000/health

# Check authentication status
curl http://localhost:8000/auth/status

# View statistics
curl http://localhost:8000/stats
```

### Logs
The service provides detailed logging:
- Request/response logging for debugging
- Authentication status updates
- Team standing change notifications
- Error reporting

### Database
The service uses SQLite databases:
- `artfight_data.db` - Main database for attacks, defenses, and team standings

## Troubleshooting

### Authentication Issues
- Ensure all required cookies are correctly set in `config.toml`
- Check `/auth/status` endpoint for authentication status
- Cookies may expire - refresh them from your browser if needed

### RSS Feed Issues
- Verify the whitelist includes the usernames you're trying to access
- Check that the service is running and accessible
- Ensure your RSS bot can reach the service URL

### Performance Issues
- Adjust `request_interval` and `team_check_interval` if needed
- Monitor cache statistics to ensure efficient operation
- Check logs for any error messages

### Team Standings Issues
- Verify team colors match exactly with ArtFight's progress bars
- Check that both teams are configured in `config.toml`
- Monitor the `/stats` endpoint for team checking status 