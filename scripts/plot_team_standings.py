#!/usr/bin/env python3
"""
Script to plot ArtFight team standings over time using the plotting module.
This script reads data from the SQLite database and creates a visualization
showing which team is winning over time.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import sys
import os

# Add the parent directory to the path so we can import artfight_feed modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from artfight_feed.config import load_config
from artfight_feed.plotting import save_team_standings_plot

def get_team_names():
    """Get team names from config, or use defaults."""
    try:
        settings = load_config()
        if settings.teams:
            return settings.teams.team1.name, settings.teams.team2.name
    except Exception as e:
        print(f"Warning: Could not load team names from config: {e}")
    
    return "Team 1", "Team 2"

def fetch_standings_data(db_path):
    """Fetch team standings data from the database for statistics."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all standings ordered by time
    cursor.execute("""
        SELECT team1_percentage, fetched_at, leader_change,
               team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
               team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
        FROM team_standings
        ORDER BY fetched_at ASC
    """)
    
    data = cursor.fetchall()
    conn.close()
    
    if not data:
        print("No team standings data found in the database.")
        return None, None, None, None
    
    # Parse the data
    team1_percentages = []
    fetched_times = []
    leader_changes = []
    
    for row in data:
        (team1_percentage, fetched_at_str, leader_change,
         team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
         team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row
        
        # Parse the datetime string
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
        except ValueError:
            # Try alternative format if needed
            fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")
        
        team1_percentages.append(team1_percentage)
        fetched_times.append(fetched_at)
        leader_changes.append(bool(leader_change))
    
    return team1_percentages, fetched_times, leader_changes, len(data)

def print_statistics(team1_percentages, fetched_times, leader_changes, team1_name, team2_name):
    """Print statistics about the data."""
    print(f"\n📊 Team Standings Statistics")
    print("=" * 50)
    print(f"Total data points: {len(team1_percentages)}")
    print(f"Date range: {fetched_times[0].strftime('%Y-%m-%d %H:%M')} to {fetched_times[-1].strftime('%Y-%m-%d %H:%M')}")
    
    # Current standings
    current_team1 = team1_percentages[-1]
    current_team2 = 100 - current_team1
    current_leader = team1_name if current_team1 > 50 else team2_name
    
    print(f"\nCurrent standings:")
    print(f"  {team1_name}: {current_team1:.2f}%")
    print(f"  {team2_name}: {current_team2:.2f}%")
    print(f"  Current leader: {current_leader}")
    
    # Leader changes
    total_leader_changes = sum(leader_changes)
    print(f"\nLeader changes: {total_leader_changes}")
    
    if total_leader_changes > 0:
        change_times = [fetched_times[i] for i in range(len(leader_changes)) if leader_changes[i]]
        print("Leader change times:")
        for i, change_time in enumerate(change_times, 1):
            print(f"  {i}. {change_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Statistics
    print(f"\nStatistics:")
    print(f"  {team1_name} average: {sum(team1_percentages) / len(team1_percentages):.2f}%")
    print(f"  {team2_name} average: {sum([100 - p for p in team1_percentages]) / len(team1_percentages):.2f}%")
    print(f"  {team1_name} min: {min(team1_percentages):.2f}%")
    print(f"  {team1_name} max: {max(team1_percentages):.2f}%")
    print(f"  {team2_name} min: {min([100 - p for p in team1_percentages]):.2f}%")
    print(f"  {team2_name} max: {max([100 - p for p in team1_percentages]):.2f}%")

def main():
    """Main function."""
    print("🎨 ArtFight Team Standings Plotter")
    print("=" * 40)
    
    # Get team names
    team1_name, team2_name = get_team_names()
    print(f"Teams: {team1_name} vs {team2_name}")
    
    # Find database file
    db_paths = [
        Path("data/artfight.db"),
        Path("data/artfight_data.db"),
        Path("artfight_feed/data/artfight.db"),
        Path("artfight_feed/data/artfight_data.db"),
        Path("artfight_data.db"),
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ No database file found. Please ensure the database exists.")
        return
    
    print(f"📁 Using database: {db_path}")
    
    # Fetch data for statistics
    print("📊 Fetching team standings data...")
    result = fetch_standings_data(db_path)
    
    if result[0] is None:
        return
    
    team1_percentages, fetched_times, leader_changes, total_points = result
    
    print(f"✅ Found {total_points} data points")
    
    # Print statistics
    print_statistics(team1_percentages, fetched_times, leader_changes, team1_name, team2_name)
    
    # Create plot using the plotting module
    print("\n📈 Creating plot using plotting module...")
    output_path = Path("team_standings_plot.png")
    
    success = save_team_standings_plot(
        output_path=output_path,
        team1_name=team1_name,
        team2_name=team2_name,
        db_path=db_path
    )
    
    if success:
        print(f"💾 Plot saved as: {output_path}")
        print("✅ Plot generated successfully with team standings and user analysis!")
    else:
        print("❌ Failed to generate plot")
        return

if __name__ == "__main__":
    main() 