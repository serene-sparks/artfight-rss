# Team Standings Plot Generator

This module provides functionality to generate ArtFight team standings plots with dual y-axes showing both percentage standings and total team scores.

## Features

- **Dual Y-Axis Plot**: Shows team percentages (primary) and total team scores (secondary)
- **Team Colors**: Uses configured team colors from the config file
- **Leader Change Markers**: Highlights when team leadership changes
- **Flexible Output**: Can generate Discord files or save to disk
- **Standalone Script**: Can be run independently of the main application

## Usage

### Standalone Script

The `generate_team_plot.py` script can be used to generate plots independently:

```bash
# Basic usage with default settings
python scripts/generate_team_plot.py

# Custom team names
python scripts/generate_team_plot.py --team1 "Red Team" --team2 "Blue Team"

# Use team names from config file
python scripts/generate_team_plot.py --use-config-teams

# Custom database and output paths
python scripts/generate_team_plot.py --db-path data/custom.db --output plots/standings.png

# Verbose logging
python scripts/generate_team_plot.py --verbose
```

### Command Line Options

- `--team1`, `-t1`: Name of the first team (default: "Team 1")
- `--team2`, `-t2`: Name of the second team (default: "Team 2")
- `--use-config-teams`: Use team names from configuration file
- `--db-path`, `-d`: Path to the SQLite database (default: from config)
- `--output`, `-o`: Output path for the plot (default: team_standings_plot.png)
- `--verbose`, `-v`: Enable verbose logging

### Programmatic Usage

```python
from artfight_feed.plotting import generate_team_standings_plot, save_team_standings_plot

# Generate Discord file
discord_file = generate_team_standings_plot("Team 1", "Team 2")

# Save to file
success = save_team_standings_plot(
    output_path=Path("team_standings.png"),
    team1_name="Team 1",
    team2_name="Team 2"
)
```

## Plot Features

### Primary Y-Axis (Percentages)
- Shows team percentage standings over time
- Blue line for Team 1 percentage
- Gray dashed line at 50% (center)
- Orange star markers for leader changes

### Secondary Y-Axis (Team Scores)
- Shows total team scores (users × avg_points)
- Uses team colors from configuration
- Drawn behind percentage lines
- Gray axis labels to distinguish from percentage axis

### Visual Elements
- **Grid**: Light gray grid for readability
- **Legend**: Combined legend showing all plot elements
- **Title**: Dynamic title with team names
- **Date Formatting**: X-axis shows dates in MM/DD HH:MM format

## Dependencies

The plotting functionality requires:
- `matplotlib` (for plotting)
- `sqlite3` (for database access)
- `discord.py` (for Discord file generation)

These are imported locally to avoid making them main dependencies.

## Configuration

Team colors and names are automatically pulled from the configuration file if available. If no team configuration is found, default colors (red/teal) and names ("Team 1"/"Team 2") are used.

## Database Schema

The plotting functions expect a `team_standings` table with the following columns:
- `team1_percentage`: Float percentage (0.0-100.0)
- `fetched_at`: DateTime when data was fetched
- `leader_change`: Boolean indicating leader change
- `team1_users`, `team2_users`: Number of users per team
- `team1_avg_points`, `team2_avg_points`: Average points per user
- Additional metrics columns for detailed data

## Error Handling

The functions handle various error conditions:
- Missing database file
- No data in database
- Missing matplotlib dependency
- Invalid data formats
- File system errors

All errors are logged and the functions return appropriate fallback values (None for Discord files, False for save operations). 