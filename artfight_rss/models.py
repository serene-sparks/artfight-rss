"""Data models for the ArtFight webhook service."""

from datetime import UTC, datetime
from typing import Optional

from feedgen.feed import FeedGenerator
from pydantic import HttpUrl
from sqlmodel import SQLModel, Field as SQLField


class ArtFightAttack(SQLModel, table=True):
    """Represents an ArtFight attack."""

    __tablename__ = "attacks"

    id: str = SQLField(primary_key=True, description="Unique attack ID")
    title: str = SQLField(description="Attack title")
    description: str | None = SQLField(default=None, description="Attack description")
    image_url: str | None = SQLField(default=None, description="Attack image URL")
    attacker_user: str = SQLField(description="Attacker's username")
    defender_user: str = SQLField(description="Defender's username")
    fetched_at: datetime = SQLField(description="When the attack was first fetched")
    url: str = SQLField(description="URL to the attack on ArtFight")
    first_seen: datetime = SQLField(description="When this attack was first seen")
    last_updated: datetime = SQLField(description="When this attack was last updated")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        return {
            "title": self.title,
            "description": self.description or f"New attack: '{self.title}' by `{self.attacker_user}` on `{self.defender_user}`.\n\n![Image]({self.image_url})",
            "link": str(self.url),
            "published": self.fetched_at,
            "entry_id": str(self.url),
            "author": self.attacker_user,
            "image_url": str(self.image_url) if self.image_url else None,
        }


class ArtFightDefense(SQLModel, table=True):
    """Represents an ArtFight defense."""

    __tablename__ = "defenses"

    id: str = SQLField(primary_key=True, description="Unique defense ID")
    title: str = SQLField(description="Defense title")
    description: str | None = SQLField(default=None, description="Defense description")
    image_url: str | None = SQLField(default=None, description="Defense image URL")
    defender_user: str = SQLField(description="Defender's username")
    attacker_user: str = SQLField(description="Attacking user's username")
    fetched_at: datetime = SQLField(description="When the attack was first fetched")
    url: str = SQLField(description="URL to the defense on ArtFight")
    first_seen: datetime = SQLField(description="When this defense was first seen")
    last_updated: datetime = SQLField(description="When this defense was last updated")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        return {
            "title": self.title,
            "description": self.description or f"`{self.attacker_user}` attacked `{self.defender_user}` with '{self.title}'.\n\n![Image]({self.image_url})\n\n[View on ArtFight]({self.url})",
            "link": str(self.url),
            "published": self.fetched_at,
            "entry_id": str(self.url),
            "author": self.attacker_user,
            "image_url": str(self.image_url) if self.image_url else None,
        }


class TeamStanding(SQLModel, table=True):
    """Represents a team standing update."""

    __tablename__ = "team_standings"

    id: int | None = SQLField(default=None, primary_key=True, description="Primary key")
    team1_percentage: float = SQLField(description="Percentage of team 1 (0.0-100.0)")
    fetched_at: datetime = SQLField(description="When the standing was first fetched")
    leader_change: bool = SQLField(default=False, description="Whether this represents a leader change")
    first_seen: datetime = SQLField(description="When this standing was first seen")
    last_updated: datetime = SQLField(description="When this standing was last updated")
    
    # Additional team metrics
    team1_users: int | None = SQLField(default=None, description="Number of users on team 1")
    team1_attacks: int | None = SQLField(default=None, description="Number of attacks by team 1")
    team1_friendly_fire: int | None = SQLField(default=None, description="Number of friendly fire attacks by team 1")
    team1_battle_ratio: float | None = SQLField(default=None, description="Battle ratio for team 1 (0.0-100.0)")
    team1_avg_points: float | None = SQLField(default=None, description="Average points per user for team 1")
    team1_avg_attacks: float | None = SQLField(default=None, description="Average attacks per user for team 1")
    
    team2_users: int | None = SQLField(default=None, description="Number of users on team 2")
    team2_attacks: int | None = SQLField(default=None, description="Number of attacks by team 2")
    team2_friendly_fire: int | None = SQLField(default=None, description="Number of friendly fire attacks by team 2")
    team2_battle_ratio: float | None = SQLField(default=None, description="Battle ratio for team 2 (0.0-100.0)")
    team2_avg_points: float | None = SQLField(default=None, description="Average points per user for team 2")
    team2_avg_attacks: float | None = SQLField(default=None, description="Average attacks per user for team 2")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        team1_name = "Team 1"
        team2_name = "Team 2"
        team1_image = None
        team2_image = None

        # Get team names and images from config if available
        from .config import settings
        if settings.teams:
            team1_name = settings.teams.team1.name
            team2_name = settings.teams.team2.name
            team1_image = settings.teams.team1.image_url
            team2_image = settings.teams.team2.image_url

        leader_image = team1_image if self.team1_percentage > 50 else team2_image
        if self.leader_change:
            leader = team1_name if self.team1_percentage > 50 else team2_name
            title = f"Leader Change: {leader} takes the lead!"
            description = f"{team1_name}: {self.team1_percentage:.5f}%, {team2_name}: {100-self.team1_percentage:.5f}%.\n\n![Image]({leader_image})"
        else:
            title = "Team Standings Update"
            description = f"{team1_name}: {self.team1_percentage:.5f}%, {team2_name}: {100-self.team1_percentage:.5f}%.\n\n![Image]({leader_image})"

        return {
            "title": title,
            "description": description,
            "link": str(leader_image) if leader_image else "",
            "published": self.fetched_at,
            "entry_id": f"team-standings-{self.fetched_at.strftime('%Y%m%d%H%M%S')}",
            "author": None,
            "image_url": str(leader_image) if leader_image else None,
        }


class RateLimit(SQLModel, table=True):
    """SQLAlchemy model for rate_limits table."""
    __tablename__ = "rate_limits"

    key: str = SQLField(primary_key=True, description="Rate limit key")
    last_request: datetime = SQLField(description="When the last request was made")
    min_interval: int = SQLField(description="Minimum interval between requests in seconds")


class CacheEntry(SQLModel, table=True):
    """Cache entry for storing data between requests."""

    key: str = SQLField(primary_key=True, description="Cache key")
    data: str = SQLField(description="Cached data as JSON string")
    timestamp: datetime = SQLField(description="When this entry was created")
    ttl: int = SQLField(description="Time to live in seconds")

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        age = (datetime.now(UTC) - self.timestamp).total_seconds()
        return age > self.ttl


class AtomFeed:
    """Atom feed generator using feedgen library."""

    def __init__(self, title: str, description: str, link: str, feed_id: str):
        self.fg = FeedGenerator()
        self.fg.title(title)
        self.fg.description(description)
        self.fg.link(href=link)
        self.fg.id(feed_id)
        self.fg.language('en')
        self.fg.updated(datetime.now(UTC))

    def add_item(self, title: str, description: str, link: str,
                 published: datetime, entry_id: str,
                 author: str | None = None,
                 image_url: str | None = None) -> None:
        """Add an item to the Atom feed."""
        fe = self.fg.add_entry()
        fe.title(title)
        fe.description(description)
        fe.link(href=link)
        fe.published(published)
        fe.id(entry_id)

        if author:
            fe.author(name=author)

        if image_url:
            # Add image as content with markdown
            fe.content(f'{description}\n\n![Image]({image_url})', type='text/markdown')

    def to_atom_xml(self) -> str:
        """Convert to Atom XML format."""
        return self.fg.atom_str(pretty=True).decode('utf-8')
