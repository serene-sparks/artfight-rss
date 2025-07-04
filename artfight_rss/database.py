"""Permanent database system for ArtFight RSS service."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

from .models import ArtFightAttack, ArtFightDefense, TeamStanding


class ArtFightDatabase:
    """Permanent database for storing ArtFight data."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path."""
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database and tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Create attacks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attacks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    attacker_user TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Create defenses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS defenses (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    defender_user TEXT NOT NULL,
                    attacker_user TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Create rate limiting table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT PRIMARY KEY,
                    last_request TEXT NOT NULL,
                    min_interval INTEGER NOT NULL
                )
            """)
            
            # Create team standings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS team_standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team1_percentage REAL NOT NULL,
                    fetched_at TEXT NOT NULL,
                    leader_change INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attacks_attacker_user ON attacks(attacker_user)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attacks_fetched_at ON attacks(fetched_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_defenses_attacker_user ON defenses(attacker_user)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_defenses_fetched_at ON defenses(fetched_at)")
            
            conn.commit()

    def save_attacks(self, attacks: List[ArtFightAttack]) -> None:
        """Save attacks to database, updating existing ones."""
        if not attacks:
            return
            
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            for attack in attacks:
                conn.execute("""
                    INSERT OR REPLACE INTO attacks 
                    (id, title, description, image_url, attacker_user, attacker_user, 
                     fetched_at, url, first_seen, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attack.id,
                    attack.title,
                    attack.description,
                    str(attack.image_url) if attack.image_url else None,
                    attack.attacker_user,
                    attack.attacker_user,
                    attack.fetched_at.isoformat(),
                    str(attack.url),
                    now,  # first_seen
                    now   # last_updated
                ))
            conn.commit()

    def save_defenses(self, defenses: List[ArtFightDefense]) -> None:
        """Save defenses to database, updating existing ones."""
        if not defenses:
            return
            
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            for defense in defenses:
                # Check if this defense already exists
                cursor = conn.execute(
                    "SELECT first_seen FROM defenses WHERE id = ?", 
                    (defense.id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    conn.execute("""
                        UPDATE defenses SET 
                        title = ?, description = ?, image_url = ?, defender_user = ?,
                        attacker_user = ?, fetched_at = ?, url = ?, last_updated = ?
                        WHERE id = ?
                    """, (
                        defense.title,
                        defense.description,
                        str(defense.image_url) if defense.image_url else None,
                        defense.defender_user,
                        defense.attacker_user,
                        defense.fetched_at.isoformat(),
                        str(defense.url),
                        now,
                        defense.id
                    ))
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO defenses 
                        (id, title, description, image_url, defender_user, attacker_user, 
                         fetched_at, url, first_seen, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        defense.id,
                        defense.title,
                        defense.description,
                        str(defense.image_url) if defense.image_url else None,
                        defense.defender_user,
                        defense.attacker_user,
                        defense.fetched_at.isoformat(),
                        str(defense.url),
                        now,  # first_seen
                        now   # last_updated
                    ))
            conn.commit()

    def get_attacks_for_user(self, username: str, limit: Optional[int] = None) -> List[ArtFightAttack]:
        """Get attacks for a user, ordered by creation date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT id, title, description, image_url, attacker_user, attacker_user, 
                       fetched_at, url
                FROM attacks 
                WHERE attacker_user = ? 
                ORDER BY fetched_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor = conn.execute(query, (username,))
            rows = cursor.fetchall()
            
            attacks = []
            for row in rows:
                (id_, title, description, image_url, attacker_user, attacker_user, 
                 fetched_at, url) = row
                
                # Parse datetime
                fetched_dt = datetime.fromisoformat(fetched_at)
                
                # Convert URLs back to HttpUrl objects
                from pydantic import HttpUrl, parse_obj_as
                image_url_http = parse_obj_as(HttpUrl, image_url) if image_url else None
                url_http = parse_obj_as(HttpUrl, url)
                
                attack = ArtFightAttack(
                    id=id_,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    attacker_user=attacker_user,
                    defender_user="TDB",
                    fetched_at=fetched_dt,
                    url=url_http
                )
                attacks.append(attack)
            
            return attacks

    def get_defenses_for_user(self, username: str, limit: Optional[int] = None) -> List[ArtFightDefense]:
        """Get defenses for a user, ordered by creation date (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT id, title, description, image_url, defender_user, attacker_user, 
                       fetched_at, url
                FROM defenses 
                WHERE defender_user = ? 
                ORDER BY fetched_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor = conn.execute(query, (username,))
            rows = cursor.fetchall()
            
            defenses = []
            for row in rows:
                (id_, title, description, image_url, defender_user, attacker_user, 
                 fetched_at, url) = row
                
                # Parse datetime
                fetched_dt = datetime.fromisoformat(fetched_at)
                
                # Convert URLs back to HttpUrl objects
                from pydantic import HttpUrl, parse_obj_as
                image_url_http = parse_obj_as(HttpUrl, image_url) if image_url else None
                url_http = parse_obj_as(HttpUrl, url)
                
                defense = ArtFightDefense(
                    id=id_,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    defender_user=defender_user,
                    attacker_user=attacker_user,
                    fetched_at=fetched_dt,
                    url=url_http
                )
                defenses.append(defense)
            
            return defenses

    def get_existing_defense_ids(self, username: str) -> set[str]:
        """Get set of existing defense IDs for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM defenses WHERE defender_user = ?", 
                (username,)
            )
            return {row[0] for row in cursor.fetchall()}

    def get_existing_attack_ids(self, username: str) -> set[str]:
        """Get set of existing attack IDs for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM attacks WHERE attacker_user = ?", 
                (username,)
            )
            return {row[0] for row in cursor.fetchall()}

    def get_rate_limit(self, key: str) -> Optional[datetime]:
        """Get last request time for rate limiting."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT last_request FROM rate_limits WHERE key = ?", 
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return datetime.fromisoformat(row[0])
            return None

    def set_rate_limit(self, key: str, min_interval: int) -> None:
        """Set rate limit for a key."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rate_limits (key, last_request, min_interval)
                VALUES (?, ?, ?)
            """, (key, now, min_interval))
            conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Count records
            attack_count = conn.execute("SELECT COUNT(*) FROM attacks").fetchone()[0]
            defense_count = conn.execute("SELECT COUNT(*) FROM defenses").fetchone()[0]
            rate_limit_count = conn.execute("SELECT COUNT(*) FROM rate_limits").fetchone()[0]
            team_count = conn.execute("SELECT COUNT(*) FROM team_standings").fetchone()[0]
            
            # Get team standings statistics
            team_stats = {}
            if team_count > 0:
                # Get latest standing
                latest = conn.execute("""
                    SELECT team1_percentage, fetched_at FROM team_standings 
                    ORDER BY fetched_at DESC LIMIT 1
                """).fetchone()
                if latest:
                    team_stats["latest_team1_percentage"] = latest[0]
                    team_stats["latest_fetched_at"] = latest[1]
                
                # Get leader change count
                leader_changes = conn.execute("""
                    SELECT COUNT(*) FROM team_standings WHERE leader_change = 1
                """).fetchone()[0]
                team_stats["total_leader_changes"] = leader_changes
                
                # Get date range
                date_range = conn.execute("""
                    SELECT MIN(fetched_at), MAX(fetched_at) FROM team_standings
                """).fetchone()
                if date_range[0] and date_range[1]:
                    team_stats["first_recorded"] = date_range[0]
                    team_stats["last_recorded"] = date_range[1]
            
            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                "total_attacks": attack_count,
                "total_defenses": defense_count,
                "total_rate_limits": rate_limit_count,
                "total_team_standings": team_count,
                "team_standings_stats": team_stats,
                "database_path": str(self.db_path),
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
            }

    def save_team_standings(self, standings: List[TeamStanding]) -> None:
        """Save team standings to database with leader change detection and history preservation."""
        if not standings:
            return
            
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get previous team1 percentage to detect leader changes
            cursor = conn.execute("""
                SELECT team1_percentage FROM team_standings 
                ORDER BY fetched_at DESC
                LIMIT 1
            """)
            previous_row = cursor.fetchone()
            
            # Determine if there's a leader change
            leader_change = False
            if previous_row and standings:
                previous_team1_percentage = previous_row[0]
                current_team1_percentage = standings[0].team1_percentage
                
                # Leader change occurs when team1 percentage crosses 50%
                previous_leader_team1 = previous_team1_percentage > 50.0
                current_leader_team1 = current_team1_percentage > 50.0
                leader_change = previous_leader_team1 != current_leader_team1
            
            # Insert new standing (don't delete previous ones)
            if standings:
                standing = standings[0]  # Only one standing now
                # Set leader_change flag if this is a leader change
                standing.leader_change = leader_change
                
                conn.execute("""
                    INSERT INTO team_standings 
                    (team1_percentage, fetched_at, leader_change, first_seen, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    standing.team1_percentage,
                    standing.fetched_at.isoformat(),
                    1 if standing.leader_change else 0,  # SQLite boolean as integer
                    now,  # first_seen
                    now   # last_updated
                ))
            conn.commit()
            
            if leader_change:
                team1_name = "Team 1"
                team2_name = "Team 2"
                # Get team names from config if available
                from .config import settings
                if settings.teams:
                    team1_name = settings.teams.team1.name
                    team2_name = settings.teams.team2.name
                
                new_leader = team1_name if current_team1_percentage > 50.0 else team2_name
                print(f"🚨 Leader change detected! New leader: {new_leader}")

    def get_team_standings(self) -> List[TeamStanding]:
        """Get current team standings."""
        return self.get_latest_team_standings()

    def get_latest_team_standings(self) -> List[TeamStanding]:
        """Get the most recent team standings."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT team1_percentage, fetched_at, leader_change
                FROM team_standings 
                ORDER BY fetched_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                (team1_percentage, fetched_at, leader_change) = row
                
                # Parse datetime
                fetched_at_dt = datetime.fromisoformat(fetched_at)
                
                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change)
                )
                return [standing]
            
            return []

    def get_team_standings_history(self, limit: Optional[int] = None) -> List[TeamStanding]:
        """Get team standings history, ordered by fetch time (newest first)."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT team1_percentage, fetched_at, leader_change
                FROM team_standings 
                ORDER BY fetched_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            standings = []
            for row in rows:
                (team1_percentage, fetched_at, leader_change) = row
                
                # Parse datetime
                fetched_at_dt = datetime.fromisoformat(fetched_at)
                
                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change)
                )
                standings.append(standing)
            
            return standings

    def get_team_standing_changes(self, days: int = 30) -> List[TeamStanding]:
        """Get team standing changes for RSS feed: last update of each day and all leader changes."""
        with sqlite3.connect(self.db_path) as conn:
            # Get standings from the last N days
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get all standings from the last N days
            cursor = conn.execute("""
                SELECT team1_percentage, fetched_at, leader_change
                FROM team_standings 
                WHERE fetched_at >= ?
                ORDER BY fetched_at DESC
            """, (cutoff_date,))
            
            all_standings = []
            for row in cursor.fetchall():
                (team1_percentage, fetched_at, leader_change) = row
                fetched_at_dt = datetime.fromisoformat(fetched_at)
                
                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change)
                )
                all_standings.append(standing)
            
            if not all_standings:
                return []
            
            # Group standings by date
            standings_by_date = {}
            for standing in all_standings:
                date_key = standing.fetched_at.date()
                if date_key not in standings_by_date:
                    standings_by_date[date_key] = []
                standings_by_date[date_key].append(standing)
            
            # Get the last standing of each day
            daily_last_standings = []
            for date_key, day_standings in standings_by_date.items():
                # Sort by time and get the latest
                day_standings.sort(key=lambda s: s.fetched_at, reverse=True)
                daily_last_standings.append(day_standings[0])
            
            # Get all leader changes
            leader_changes = [standing for standing in all_standings if standing.leader_change]
            
            # Combine and deduplicate (leader changes might be the same as daily last)
            combined_standings = daily_last_standings + leader_changes
            
            # Remove duplicates based on fetched_at (within 1 second tolerance)
            unique_standings = []
            seen_times = set()
            for standing in combined_standings:
                # Round to nearest second for deduplication
                time_key = standing.fetched_at.replace(microsecond=0)
                if time_key not in seen_times:
                    seen_times.add(time_key)
                    unique_standings.append(standing)
            
            # Sort by fetched_at (newest first)
            unique_standings.sort(key=lambda s: s.fetched_at, reverse=True)
            
            return unique_standings 