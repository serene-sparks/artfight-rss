"""Data models for the ArtFight webhook service."""

from datetime import UTC, datetime
from typing import Optional

from feedgen.feed import FeedGenerator
from pydantic import HttpUrl
from sqlmodel import SQLModel, Field as SQLField


class ArtFightAttack(SQLModel, table=True):
    """Represents an ArtFight attack."""

    __tablename__ = "attacks" # type: ignore

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

    __tablename__ = "defenses" # type: ignore

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
    """Represents a team standing update.

    Supports any number of teams (ArtFight has run events with 2 teams in
    past years and 3 teams in 2026). Per-team data (percentage and detailed
    metrics) is stored as a JSON blob keyed by the team's config key
    (e.g. "team1", "team2", "team3", ...) so the schema doesn't need to
    change if the number of teams changes again.
    """

    __tablename__ = "team_standings" # type: ignore

    id: int | None = SQLField(default=None, primary_key=True, description="Primary key")
    team_data: str = SQLField(
        default="{}",
        description=(
            "JSON object keyed by team config key (team1, team2, ...) with "
            "per-team percentage and metrics, e.g. "
            '{"team1": {"percentage": 55.2, "users": 100, ...}, "team2": {...}}'
        ),
    )
    leader_key: str | None = SQLField(default=None, description="Config key of the currently leading team")
    fetched_at: datetime = SQLField(description="When the standing was first fetched")
    leader_change: bool = SQLField(default=False, description="Whether this represents a leader change")
    first_seen: datetime = SQLField(description="When this standing was first seen")
    last_updated: datetime = SQLField(description="When this standing was last updated")

    def get_team_data(self) -> dict:
        """Parse the team_data JSON blob into a dict."""
        import json
        try:
            return json.loads(self.team_data) if self.team_data else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_team_data(self, data: dict) -> None:
        """Serialize a dict of per-team data into the team_data column."""
        import json
        self.team_data = json.dumps(data)

    def percentages(self) -> dict[str, float]:
        """Return {team_key: percentage} for all teams that have a percentage."""
        return {
            key: team["percentage"]
            for key, team in self.get_team_data().items()
            if team.get("percentage") is not None
        }

    def team_metric(self, team_key: str, metric: str):
        """Get a single metric (users, attacks, friendly_fire, battle_ratio, avg_points, avg_attacks) for a team."""
        return self.get_team_data().get(team_key, {}).get(metric)

    def compute_leader_key(self) -> str | None:
        """Determine the config key of the team with the highest percentage."""
        percentages = self.percentages()
        if not percentages:
            return None
        return max(percentages, key=lambda k: percentages[k])

    def _team_display_names(self) -> dict[str, str]:
        """Map team config key -> display name, falling back to the key itself."""
        from .config import settings
        names = {}
        for key in self.get_team_data().keys():
            if settings.teams is not None:
                try:
                    names[key] = settings.teams[key].name
                except (KeyError, AttributeError):
                    names[key] = key
            else:
                names[key] = key
        return names

    def _team_image(self, team_key: str) -> str | None:
        from .config import settings
        if settings.teams is not None:
            try:
                return settings.teams[team_key].image_url
            except (KeyError, AttributeError):
                return None
        return None

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        team_data = self.get_team_data()
        names = self._team_display_names()
        leader_key = self.leader_key or self.compute_leader_key()
        leader_name = names.get(leader_key, leader_key) if leader_key else "Unknown"
        leader_image = self._team_image(leader_key) if leader_key else None

        description_parts = []

        if self.leader_change:
            title = f"Leader Change: {leader_name} takes the lead!"
        else:
            title = "Team Standings Update"

        for key, team in team_data.items():
            percentage = team.get("percentage")
            if percentage is not None:
                description_parts.append(f"**{names.get(key, key)}**: {percentage:.5f}%")

        # Add detailed metrics if any team has them
        metric_specs = [
            ("users", "Users", "{:,}"),
            ("attacks", "Attacks", "{:,}"),
            ("friendly_fire", "Friendly Fire", "{:,}"),
            ("battle_ratio", "Battle Ratio", "{:.2f}%"),
            ("avg_points", "Avg Points", "{:.2f}"),
            ("avg_attacks", "Avg Attacks", "{:.2f}"),
        ]
        has_metrics = any(
            team.get(metric_key) is not None
            for team in team_data.values()
            for metric_key, _, _ in metric_specs
        )
        if has_metrics:
            description_parts.append("")
            description_parts.append("**Detailed Metrics:**")
            for metric_key, label, fmt in metric_specs:
                values = [
                    (names.get(key, key), team.get(metric_key))
                    for key, team in team_data.items()
                    if team.get(metric_key) is not None
                ]
                if values:
                    formatted = ", ".join(f"{name}: {fmt.format(value)}" for name, value in values)
                    description_parts.append(f"**{label}**: {formatted}")

        description = "\n".join(description_parts)
        if leader_image:
            description += f"\n\n![Image]({leader_image})"

        return {
            "title": title,
            "description": description,
            "link": str(leader_image) if leader_image else "",
            "published": self.fetched_at,
            "entry_id": f"team-standings-{self.fetched_at.strftime('%Y%m%d%H%M%S')}",
            "author": None,
            "image_url": str(leader_image) if leader_image else None,
        }


class ArtFightNews(SQLModel, table=True):
    """Represents an ArtFight news post."""

    __tablename__ = "news" # type: ignore

    id: int = SQLField(primary_key=True, description="Unique news post ID")
    title: str = SQLField(description="News post title")
    content: str | None = SQLField(default=None, description="News post content (full content)")
    author: str | None = SQLField(default=None, description="Author of the news post")
    posted_at: datetime | None = SQLField(default=None, description="When the news post was posted")
    edited_at: datetime | None = SQLField(default=None, description="When the news post was last edited")
    edited_by: str | None = SQLField(default=None, description="Who edited the news post")
    url: str = SQLField(description="URL to the news post on ArtFight")
    fetched_at: datetime = SQLField(description="When the news post was first fetched")
    first_seen: datetime = SQLField(description="When this news post was first seen")
    last_updated: datetime = SQLField(description="When this news post was last updated")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        description = f"New ArtFight news post: {self.title}"
        if self.author:
            description += f"\n\nPosted by: {self.author}"
        if self.posted_at:
            description += f"\nPosted on: {self.posted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        if self.edited_at and self.edited_by:
            description += f"\nEdited by: {self.edited_by} on {self.edited_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        if self.content:
            # Truncate content to reasonable length for RSS
            content_preview = self.content[:500] + "..." if len(self.content) > 500 else self.content
            description += f"\n\n{content_preview}"

        return {
            "title": self.title,
            "description": description,
            "link": str(self.url),
            "published": self.posted_at or self.fetched_at,
            "entry_id": str(self.url),
            "author": self.author,
            "image_url": None,
        }


class NewsRevision(SQLModel, table=True):
    """Represents a revision of an ArtFight news post."""

    __tablename__ = "news_revisions" # type: ignore

    id: int | None = SQLField(default=None, primary_key=True, description="Primary key")
    news_id: int = SQLField(description="ID of the news post this revision is for")
    revision_number: int = SQLField(description="Revision number (1, 2, 3, etc.)")
    title: str = SQLField(description="News post title at this revision")
    content: str | None = SQLField(default=None, description="News post content at this revision")
    author: str | None = SQLField(default=None, description="Author of the news post")
    posted_at: datetime | None = SQLField(default=None, description="When the news post was posted")
    edited_at: datetime | None = SQLField(default=None, description="When the news post was edited to this revision")
    edited_by: str | None = SQLField(default=None, description="Who edited the news post to this revision")
    url: str = SQLField(description="URL to the news post on ArtFight")
    fetched_at: datetime = SQLField(description="When this revision was fetched")
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC), description="When this revision record was created")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        description = f"News post revision: {self.title}"
        if self.author:
            description += f"\n\nPosted by: {self.author}"
        if self.posted_at:
            description += f"\nPosted on: {self.posted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        if self.edited_at and self.edited_by:
            description += f"\nEdited by: {self.edited_by} on {self.edited_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        if self.content:
            # Truncate content to reasonable length for RSS
            content_preview = self.content[:500] + "..." if len(self.content) > 500 else self.content
            description += f"\n\n{content_preview}"

        return {
            "title": f"Revision {self.revision_number}: {self.title}",
            "description": description,
            "link": str(self.url),
            "published": self.edited_at or self.posted_at or self.fetched_at,
            "entry_id": f"{self.url}-rev-{self.revision_number}",
            "author": self.edited_by or self.author,
            "image_url": None,
        }


class RateLimit(SQLModel, table=True):
    """SQLAlchemy model for rate_limits table."""
    __tablename__ = "rate_limits" # type: ignore

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
