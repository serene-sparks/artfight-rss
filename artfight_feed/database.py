"""Permanent database system for ArtFight RSS service."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import settings
from .models import ArtFightAttack, ArtFightDefense, TeamStanding, CacheEntry, ArtFightNews, NewsRevision


def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def validate_and_apply_limit(requested_limit: int | None) -> int | None:
    """Validate and apply limit based on configuration."""
    if requested_limit is None:
        return settings.max_feed_items

    # Validate requested limit
    if requested_limit < 1:
        raise ValueError(f"Limit must be at least 1, got {requested_limit}")

    # Ensure the requested limit doesn't exceed the configured maximum
    return min(requested_limit, settings.max_feed_items)


class ArtFightDatabase:
    """Permanent database for storing ArtFight data."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path."""
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def migrate(self) -> None:
        """Run Alembic migrations for this database."""
        import subprocess
        import sys
        import os
        
        try:
            # Get the project root directory (where alembic.ini is located)
            # For test databases, use the current working directory as it should be the project root
            import os
            project_root = Path(os.getcwd())
            
            # Verify alembic.ini exists
            if not (project_root / "alembic.ini").exists():
                raise RuntimeError(f"Could not find alembic.ini in {project_root}")
            
            # Set the database URL environment variable for Alembic
            db_url = f"sqlite:///{self.db_path}"
            env = {**os.environ, "DATABASE_URL": db_url}
            
            # Run alembic upgrade head with explicit config file
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", str(project_root / "alembic.ini"), "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=project_root,
                env=env
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Migration failed: {result.stderr}\nstdout: {result.stdout}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to run migrations: {e}")

    def _init_database(self) -> None:
        """Initialize the SQLite database connection."""
        # Ensure the database directory exists
        self.db_path.parent.mkdir(exist_ok=True)
        

    def save_attacks(self, attacks: list[ArtFightAttack]) -> None:
        """Save attacks to database, updating existing ones."""
        if not attacks:
            return

        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            for attack in attacks:
                conn.execute("""
                    INSERT OR REPLACE INTO attacks
                    (id, title, description, image_url, attacker_user, defender_user,
                     fetched_at, url, first_seen, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attack.id,
                    attack.title,
                    attack.description,
                    str(attack.image_url) if attack.image_url else None,
                    attack.attacker_user,
                    attack.defender_user,
                    attack.fetched_at.isoformat(),
                    str(attack.url),
                    now,  # first_seen
                    now   # last_updated
                ))
            conn.commit()

    def save_defenses(self, defenses: list[ArtFightDefense]) -> None:
        """Save defenses to database, updating existing ones."""
        if not defenses:
            return

        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            for defense in defenses:
                conn.execute("""
                    INSERT OR REPLACE INTO defenses
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

    def get_attacks_for_users(self, usernames: list[str], limit: int | None = None) -> list[ArtFightAttack]:
        """Get attacks for multiple users, ordered by creation date (newest first)."""
        if not usernames:
            return []

        # Validate and apply limit
        validated_limit = validate_and_apply_limit(limit)

        with sqlite3.connect(self.db_path) as conn:
            # Create placeholders for the IN clause
            placeholders = ','.join(['?' for _ in usernames])
            query = f"""
                SELECT id, title, description, image_url, attacker_user, defender_user,
                       fetched_at, url, first_seen, last_updated
                FROM attacks
                WHERE attacker_user IN ({placeholders})
                ORDER BY fetched_at DESC
            """

            if validated_limit:
                query += f" LIMIT {validated_limit}"

            cursor = conn.execute(query, usernames)
            rows = cursor.fetchall()

            attacks = []
            for row in rows:
                (id_, title, description, image_url, attacker_user, defender_user,
                 fetched_at, url, first_seen, last_updated) = row

                # Parse datetime and ensure timezone awareness
                fetched_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))
                first_seen_dt = ensure_timezone_aware(datetime.fromisoformat(first_seen))
                last_updated_dt = ensure_timezone_aware(datetime.fromisoformat(last_updated))

                attack = ArtFightAttack(
                    id=id_,
                    title=title,
                    description=description,
                    image_url=image_url,
                    attacker_user=attacker_user,
                    defender_user=defender_user,
                    fetched_at=fetched_dt,
                    url=url,
                    first_seen=first_seen_dt,
                    last_updated=last_updated_dt
                )
                attacks.append(attack)

            return attacks

    def get_defenses_for_users(self, usernames: list[str], limit: int | None = None) -> list[ArtFightDefense]:
        """Get defenses for multiple users, ordered by creation date (newest first)."""
        if not usernames:
            return []

        # Validate and apply limit
        validated_limit = validate_and_apply_limit(limit)

        with sqlite3.connect(self.db_path) as conn:
            # Create placeholders for the IN clause
            placeholders = ','.join(['?' for _ in usernames])
            query = f"""
                SELECT id, title, description, image_url, defender_user, attacker_user,
                       fetched_at, url, first_seen, last_updated
                FROM defenses
                WHERE defender_user IN ({placeholders})
                ORDER BY fetched_at DESC
            """

            if validated_limit:
                query += f" LIMIT {validated_limit}"

            cursor = conn.execute(query, usernames)
            rows = cursor.fetchall()

            defenses = []
            for row in rows:
                (id_, title, description, image_url, defender_user, attacker_user,
                 fetched_at, url, first_seen, last_updated) = row

                # Parse datetime and ensure timezone awareness
                fetched_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))
                first_seen_dt = ensure_timezone_aware(datetime.fromisoformat(first_seen))
                last_updated_dt = ensure_timezone_aware(datetime.fromisoformat(last_updated))

                defense = ArtFightDefense(
                    id=id_,
                    title=title,
                    description=description,
                    image_url=image_url,
                    defender_user=defender_user,
                    attacker_user=attacker_user,
                    fetched_at=fetched_dt,
                    url=url,
                    first_seen=first_seen_dt,
                    last_updated=last_updated_dt
                )
                defenses.append(defense)

            return defenses

    def get_existing_defense_ids(self, username: str) -> set[str]:
        """Get all existing defense IDs for a user from the database."""
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

    def get_existing_news_ids(self) -> set[int]:
        """Get set of existing news post IDs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM news")
            return {row[0] for row in cursor.fetchall()}

    def get_existing_news_by_id(self, news_id: int) -> ArtFightNews | None:
        """Get an existing news post by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, title, content, author, posted_at, edited_at, edited_by,
                       url, fetched_at, first_seen, last_updated
                FROM news WHERE id = ?
            """, (news_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            (id_, title, content, author, posted_at, edited_at, edited_by,
             url, fetched_at, first_seen, last_updated) = row

            # Parse datetime and ensure timezone awareness
            fetched_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))
            first_seen_dt = ensure_timezone_aware(datetime.fromisoformat(first_seen))
            last_updated_dt = ensure_timezone_aware(datetime.fromisoformat(last_updated))
            
            # Parse optional datetime fields
            posted_dt = None
            if posted_at:
                posted_dt = ensure_timezone_aware(datetime.fromisoformat(posted_at))
            
            edited_dt = None
            if edited_at:
                edited_dt = ensure_timezone_aware(datetime.fromisoformat(edited_at))

            return ArtFightNews(
                id=id_,
                title=title,
                content=content,
                author=author,
                posted_at=posted_dt,
                edited_at=edited_dt,
                edited_by=edited_by,
                url=url,
                fetched_at=fetched_dt,
                first_seen=first_seen_dt,
                last_updated=last_updated_dt
            )

    def get_next_revision_number(self, news_id: int) -> int:
        """Get the next revision number for a news post."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT MAX(revision_number) FROM news_revisions WHERE news_id = ?
            """, (news_id,))
            
            result = cursor.fetchone()
            if result[0] is None:
                return 1
            return result[0] + 1

    def save_news_revision(self, revision: 'NewsRevision') -> None:
        """Save a news revision to the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO news_revisions
                (news_id, revision_number, title, content, author, posted_at, edited_at, edited_by,
                 url, fetched_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                revision.news_id,
                revision.revision_number,
                revision.title,
                revision.content,
                revision.author,
                revision.posted_at.isoformat() if revision.posted_at else None,
                revision.edited_at.isoformat() if revision.edited_at else None,
                revision.edited_by,
                revision.url,
                revision.fetched_at.isoformat(),
                revision.created_at.isoformat()
            ))
            conn.commit()

    def save_news(self, news_posts: list[ArtFightNews]) -> list[tuple[ArtFightNews, ArtFightNews | None]]:
        """Save news posts to database, updating existing ones and creating revisions for changes.
        
        Returns a list of tuples: (current_post, old_post_if_revised)
        """
        if not news_posts:
            return []

        now = datetime.now(UTC)
        results = []

        with sqlite3.connect(self.db_path) as conn:
            for news in news_posts:
                # Check if this news post already exists
                existing_news = self.get_existing_news_by_id(news.id)
                
                # Check if this is a revision of an existing news post
                if existing_news:
                    # Convert HTML to markdown for content comparison
                    import html2text
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.ignore_images = False
                    h.body_width = 0
                    
                    old_markdown = h.handle(existing_news.content).strip() if existing_news.content else ""
                    new_markdown = h.handle(news.content).strip() if news.content else ""
                    
                    # Check for any changes (including metadata changes)
                    title_changed = existing_news.title != news.title
                    content_changed = old_markdown != new_markdown
                    editor_changed = existing_news.edited_by != news.edited_by
                    edit_date_changed = existing_news.edited_at != news.edited_at
                    
                    # Create revision for ANY changes (title, content, editor, or edit date)
                    if title_changed or content_changed or editor_changed or edit_date_changed:
                        # Create revision record for the old post
                        revision = NewsRevision(
                            news_id=existing_news.id,
                            revision_number=self.get_next_revision_number(existing_news.id),
                            title=existing_news.title,
                            content=existing_news.content,
                            author=existing_news.author,
                            posted_at=existing_news.posted_at,
                            edited_at=existing_news.edited_at,
                            edited_by=existing_news.edited_by,
                            url=existing_news.url,
                            fetched_at=existing_news.fetched_at,
                            created_at=now
                        )
                        self.save_news_revision(revision)
                        
                        # Update the existing news post
                        conn.execute("""
                            UPDATE news SET
                                title = ?, content = ?, edited_at = ?, edited_by = ?,
                                fetched_at = ?, last_updated = ?
                            WHERE id = ?
                        """, (
                            news.title,
                            news.content,
                            news.edited_at.isoformat() if news.edited_at else None,
                            news.edited_by,
                            news.fetched_at.isoformat(),
                            now.isoformat(),
                            news.id
                        ))
                        results.append((news, existing_news))
                    else:
                        # No changes at all, just update fetch time
                        conn.execute("""
                            UPDATE news SET fetched_at = ?, last_updated = ?
                            WHERE id = ?
                        """, (news.fetched_at.isoformat(), now.isoformat(), news.id))
                        results.append((news, None))
                else:
                    # New news post
                    conn.execute("""
                        INSERT INTO news
                    (id, title, content, author, posted_at, edited_at, edited_by,
                     url, fetched_at, first_seen, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news.id,
                    news.title,
                    news.content,
                    news.author,
                    news.posted_at.isoformat() if news.posted_at else None,
                    news.edited_at.isoformat() if news.edited_at else None,
                    news.edited_by,
                    news.url,
                    news.fetched_at.isoformat(),
                        now.isoformat(),  # first_seen
                        now.isoformat()   # last_updated
                ))
                    results.append((news, None))
            
            conn.commit()
        
        return results

    def get_news(self, limit: int | None = None) -> list[ArtFightNews]:
        """Get news posts, ordered by ID (newest first) for correct alerting."""
        # TODO: This is not correct, we need to order by posted_at or fetched_at
        # but we need to make sure we get the correct news post order.
        # Good enough unless something shows otherwise
        
        # Validate and apply limit
        validated_limit = validate_and_apply_limit(limit)

        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT id, title, content, author, posted_at, edited_at, edited_by,
                       url, fetched_at, first_seen, last_updated
                FROM news
                ORDER BY id DESC
            """

            if validated_limit:
                query += f" LIMIT {validated_limit}"

            cursor = conn.execute(query)
            rows = cursor.fetchall()

            news_posts = []
            for row in rows:
                (id_, title, content, author, posted_at, edited_at, edited_by,
                 url, fetched_at, first_seen, last_updated) = row

                # Parse datetime and ensure timezone awareness
                fetched_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))
                first_seen_dt = ensure_timezone_aware(datetime.fromisoformat(first_seen))
                last_updated_dt = ensure_timezone_aware(datetime.fromisoformat(last_updated))
                
                # Parse optional datetime fields
                posted_dt = None
                if posted_at:
                    posted_dt = ensure_timezone_aware(datetime.fromisoformat(posted_at))
                
                edited_dt = None
                if edited_at:
                    edited_dt = ensure_timezone_aware(datetime.fromisoformat(edited_at))

                news = ArtFightNews(
                    id=id_,
                    title=title,
                    content=content,
                    author=author,
                    posted_at=posted_dt,
                    edited_at=edited_dt,
                    edited_by=edited_by,
                    url=url,
                    fetched_at=fetched_dt,
                    first_seen=first_seen_dt,
                    last_updated=last_updated_dt
                )
                news_posts.append(news)

            return news_posts

    def get_rate_limit(self, key: str) -> datetime | None:
        """Get last request time for rate limiting."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT last_request FROM rate_limits WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return ensure_timezone_aware(datetime.fromisoformat(row[0]))
            return None

    def set_rate_limit(self, key: str, min_interval: int) -> None:
        """Set rate limit for a key."""
        now = datetime.now(UTC).isoformat()
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
            news_count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]

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
                "total_news": news_count,
                "team_standings_stats": team_stats,
                "database_path": str(self.db_path),
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
            }

    def save_team_standings(self, standings: list[TeamStanding]) -> None:
        """Save team standings to database with leader change detection and history preservation."""
        if not standings:
            return

        now = datetime.now(UTC).isoformat()

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
                    (team1_percentage, fetched_at, leader_change, first_seen, last_updated,
                     team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                     team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    standing.team1_percentage,
                    standing.fetched_at.isoformat(),
                    1 if standing.leader_change else 0,  # SQLite boolean as integer
                    now,  # first_seen
                    now,  # last_updated
                    standing.team1_users,
                    standing.team1_attacks,
                    standing.team1_friendly_fire,
                    standing.team1_battle_ratio,
                    standing.team1_avg_points,
                    standing.team1_avg_attacks,
                    standing.team2_users,
                    standing.team2_attacks,
                    standing.team2_friendly_fire,
                    standing.team2_battle_ratio,
                    standing.team2_avg_points,
                    standing.team2_avg_attacks
                ))
            conn.commit()

            if leader_change:
                team1_name = "Team 1"
                team2_name = "Team 2"
                # Get team names from config if available
                if settings.teams:
                    team1_name = settings.teams.team1.name
                    team2_name = settings.teams.team2.name

                new_leader = team1_name if current_team1_percentage > 50.0 else team2_name
                print(f"🚨 Leader change detected! New leader: {new_leader}")

    def get_team_standings(self) -> list[TeamStanding]:
        """Get current team standings."""
        return self.get_latest_team_standings()

    def get_latest_team_standings(self) -> list[TeamStanding]:
        """Get the most recent team standings."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT team1_percentage, fetched_at, leader_change,
                       team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                       team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
                FROM team_standings
                ORDER BY fetched_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if row:
                (team1_percentage, fetched_at, leader_change,
                 team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                 team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row

                # Parse datetime and ensure timezone awareness
                fetched_at_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))

                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change),
                    first_seen=fetched_at_dt,
                    last_updated=fetched_at_dt,
                    team1_users=team1_users,
                    team1_attacks=team1_attacks,
                    team1_friendly_fire=team1_friendly_fire,
                    team1_battle_ratio=team1_battle_ratio,
                    team1_avg_points=team1_avg_points,
                    team1_avg_attacks=team1_avg_attacks,
                    team2_users=team2_users,
                    team2_attacks=team2_attacks,
                    team2_friendly_fire=team2_friendly_fire,
                    team2_battle_ratio=team2_battle_ratio,
                    team2_avg_points=team2_avg_points,
                    team2_avg_attacks=team2_avg_attacks
                )
                return [standing]

            return []

    def get_team_standings_history(self, limit: int | None = None) -> list[TeamStanding]:
        """Get team standings history, ordered by fetch time (newest first)."""
        # Validate and apply limit
        validated_limit = validate_and_apply_limit(limit)

        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT team1_percentage, fetched_at, leader_change,
                       team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                       team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
                FROM team_standings
                ORDER BY fetched_at DESC
            """

            if validated_limit:
                query += f" LIMIT {validated_limit}"

            cursor = conn.execute(query)
            rows = cursor.fetchall()

            standings = []
            for row in rows:
                (team1_percentage, fetched_at, leader_change,
                 team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                 team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row

                # Parse datetime and ensure timezone awareness
                fetched_at_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))

                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change),
                    first_seen=fetched_at_dt,
                    last_updated=fetched_at_dt,
                    team1_users=team1_users,
                    team1_attacks=team1_attacks,
                    team1_friendly_fire=team1_friendly_fire,
                    team1_battle_ratio=team1_battle_ratio,
                    team1_avg_points=team1_avg_points,
                    team1_avg_attacks=team1_avg_attacks,
                    team2_users=team2_users,
                    team2_attacks=team2_attacks,
                    team2_friendly_fire=team2_friendly_fire,
                    team2_battle_ratio=team2_battle_ratio,
                    team2_avg_points=team2_avg_points,
                    team2_avg_attacks=team2_avg_attacks
                )
                standings.append(standing)

            return standings

    def get_team_standing_changes(self, days: int = 30, limit: int | None = None) -> list[TeamStanding]:
        """Get team standing changes for RSS feed: last update of each day and all leader changes."""
        # Validate and apply limit
        validated_limit = validate_and_apply_limit(limit)

        with sqlite3.connect(self.db_path) as conn:
            # Get standings from the last N days
            cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

            # Get all standings from the last N days
            cursor = conn.execute("""
                SELECT team1_percentage, fetched_at, leader_change,
                       team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                       team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks
                FROM team_standings
                WHERE fetched_at >= ?
                ORDER BY fetched_at DESC
            """, (cutoff_date,))

            all_standings = []
            for row in cursor.fetchall():
                (team1_percentage, fetched_at, leader_change,
                 team1_users, team1_attacks, team1_friendly_fire, team1_battle_ratio, team1_avg_points, team1_avg_attacks,
                 team2_users, team2_attacks, team2_friendly_fire, team2_battle_ratio, team2_avg_points, team2_avg_attacks) = row
                fetched_at_dt = ensure_timezone_aware(datetime.fromisoformat(fetched_at))

                standing = TeamStanding(
                    team1_percentage=team1_percentage,
                    fetched_at=fetched_at_dt,
                    leader_change=bool(leader_change),
                    first_seen=fetched_at_dt,
                    last_updated=fetched_at_dt,
                    team1_users=team1_users,
                    team1_attacks=team1_attacks,
                    team1_friendly_fire=team1_friendly_fire,
                    team1_battle_ratio=team1_battle_ratio,
                    team1_avg_points=team1_avg_points,
                    team1_avg_attacks=team1_avg_attacks,
                    team2_users=team2_users,
                    team2_attacks=team2_attacks,
                    team2_friendly_fire=team2_friendly_fire,
                    team2_battle_ratio=team2_battle_ratio,
                    team2_avg_points=team2_avg_points,
                    team2_avg_attacks=team2_avg_attacks
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

            # Get the first standing of each day
            daily_first_standings = []
            for _date_key, day_standings in standings_by_date.items():
                # Sort by time and get the earliest
                day_standings.sort(key=lambda s: s.fetched_at)
                daily_first_standings.append(day_standings[0])

            # Get all leader changes
            leader_changes = [standing for standing in all_standings if standing.leader_change]

            # Combine and deduplicate (leader changes might be the same as daily first)
            combined_standings = daily_first_standings + leader_changes

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

            # Apply limit if specified
            if validated_limit:
                unique_standings = unique_standings[:validated_limit]

            return unique_standings

    # Cache methods
    def get_cache(self, key: str) -> Any | None:
        """Get value from cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, timestamp, ttl FROM cache_entries WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            data_str, timestamp_str, ttl = row
            timestamp = ensure_timezone_aware(datetime.fromisoformat(timestamp_str))

            # Check if expired
            age = (datetime.now(UTC) - timestamp).total_seconds()
            if age > ttl:
                # Remove expired entry
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return None

            return json.loads(data_str)

    def set_cache(self, key: str, data: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        data_str = json.dumps(data, default=str)
        timestamp = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries (key, data, timestamp, ttl)
                VALUES (?, ?, ?, ?)
            """, (key, data_str, timestamp, ttl))
            conn.commit()

    def delete_cache(self, key: str) -> None:
        """Delete value from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()

    def clear_cache(self) -> None:
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

    def cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        with sqlite3.connect(self.db_path) as conn:
            # Get all entries
            cursor = conn.execute("SELECT key, timestamp, ttl FROM cache_entries")
            expired_keys = []

            for row in cursor.fetchall():
                key, timestamp_str, ttl = row
                timestamp = ensure_timezone_aware(datetime.fromisoformat(timestamp_str))
                age = (datetime.now(UTC) - timestamp).total_seconds()

                if age > ttl:
                    expired_keys.append(key)

            # Delete expired entries
            if expired_keys:
                placeholders = ','.join('?' * len(expired_keys))
                conn.execute(f"DELETE FROM cache_entries WHERE key IN ({placeholders})", expired_keys)
                conn.commit()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
            total_entries = cursor.fetchone()[0]

            return {
                "total_entries": total_entries,
                "database_path": str(self.db_path),
            }
