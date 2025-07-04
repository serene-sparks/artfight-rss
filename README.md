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