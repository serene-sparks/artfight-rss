"""Data models for the ArtFight webhook service."""

import html
from datetime import datetime, timezone
from typing import Optional

from feedgen.feed import FeedGenerator
from pydantic import BaseModel, Field, HttpUrl


class ArtFightAttack(BaseModel):
    """Represents an ArtFight attack."""

    id: str = Field(..., description="Unique attack ID")
    title: str = Field(..., description="Attack title")
    description: str | None = Field(default=None, description="Attack description")
    image_url: HttpUrl | None = Field(default=None, description="Attack image URL")
    attacker_user: str = Field(..., description="Attacker's username")
    defender_user: str = Field(..., description="Defender's username")
    fetched_at: datetime = Field(..., description="When the attack was first fetched")
    url: HttpUrl = Field(..., description="URL to the attack on ArtFight")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        return {
            "title": self.title,
            "description": self.description or f"New attack: '{self.title}' by {self.attacker_user} on {self.defender_user}. <img src='{self.image_url}' />",
            "link": str(self.url),
            "published": self.fetched_at,
            "entry_id": str(self.url),
            "author": self.attacker_user,
            "image_url": str(self.image_url) if self.image_url else None,
        }


class ArtFightDefense(BaseModel):
    """Represents an ArtFight defense."""

    id: str = Field(..., description="Unique defense ID")
    title: str = Field(..., description="Defense title")
    description: str | None = Field(default=None, description="Defense description")
    image_url: HttpUrl | None = Field(default=None, description="Defense image URL")
    defender_user: str = Field(..., description="Defender's username")
    attacker_user: str = Field(..., description="Attacking user's username")
    fetched_at: datetime = Field(..., description="When the attack was first fetched")
    url: HttpUrl = Field(..., description="URL to the defense on ArtFight")

    def to_atom_item(self) -> dict:
        """Convert to Atom item format."""
        return {
            "title": self.title,
            "description": self.description or f"{self.attacker_user} attacked {self.defender_user} with '{self.title}'.<br/><img src='{self.image_url}' /><br/><a href='{self.url}'>View on ArtFight</a>",
            "link": str(self.url),
            "published": self.fetched_at,
            "entry_id": str(self.url),
            "author": self.attacker_user,
            "image_url": str(self.image_url) if self.image_url else None,
        }


class TeamStanding(BaseModel):
    """Represents a team standing update."""

    team1_percentage: float = Field(..., description="Percentage of team 1 (0.0-100.0)")
    fetched_at: datetime = Field(..., description="When the standing was first fetched")
    leader_change: bool = Field(default=False, description="Whether this represents a leader change")

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
            description = f"{team1_name}: {self.team1_percentage:.5f}%, {team2_name}: {100-self.team1_percentage:.5f}%. <img src='{leader_image}' />"
        else:
            title = "Team Standings Update"
            description = f"{team1_name}: {self.team1_percentage:.5f}%, {team2_name}: {100-self.team1_percentage:.5f}%. <img src='{leader_image}' />"
        
        return {
            "title": title,
            "description": description,
            "link": str(leader_image) if leader_image else "",
            "published": self.fetched_at,
            "entry_id": f"team-standings-{self.fetched_at.strftime('%Y%m%d%H%M%S')}",
            "author": None,
            "image_url": str(leader_image) if leader_image else None,
        }


class CacheEntry(BaseModel):
    """Cache entry for storing data between requests."""

    key: str = Field(..., description="Cache key")
    data: dict = Field(..., description="Cached data")
    timestamp: datetime = Field(..., description="When this entry was created")
    ttl: int = Field(..., description="Time to live in seconds")

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        age = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
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
        self.fg.updated(datetime.now(timezone.utc))

    def add_item(self, title: str, description: str, link: str, 
                 published: datetime, entry_id: str, 
                 author: Optional[str] = None, 
                 image_url: Optional[str] = None) -> None:
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
            # Add image as content with HTML
            fe.content(f'{description}<br/><img src="{image_url}" alt="Image" />', type='html')

    def to_atom_xml(self) -> str:
        """Convert to Atom XML format."""
        return self.fg.atom_str(pretty=True).decode('utf-8')
