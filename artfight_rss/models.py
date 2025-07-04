"""Data models for the ArtFight webhook service."""

import html
import xml.sax.saxutils
from datetime import datetime

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

    def to_rss_item(self) -> dict:
        """Convert to RSS item format."""
        return {
            "title": self.title,
            "description": self.description or f"New attack: '{self.title}' by {self.attacker_user} on {self.defender_user}",
            "link": str(self.url),
            "fetchDate": self.fetched_at.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "guid": str(self.url),
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

    def to_rss_item(self) -> dict:
        """Convert to RSS item format."""
        return {
            "title": self.title,
            "description": self.description or f"New defense: '{self.title}' by {self.attacker_user} on {self.defender_user}",
            "link": str(self.url),
            "fetchDate": self.fetched_at.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "guid": str(self.url),
        }


class TeamStanding(BaseModel):
    """Represents a team standing update."""

    team1_percentage: float = Field(..., description="Percentage of team 1 (0.0-100.0)")
    fetched_at: datetime = Field(..., description="When the standing was first fetched")
    leader_change: bool = Field(default=False, description="Whether this represents a leader change")

    def to_rss_item(self) -> dict:
        """Convert to RSS item format."""
        team1_name = "Team 1"
        team2_name = "Team 2"
        
        # Get team names from config if available
        from .config import settings
        if settings.teams:
            team1_name = settings.teams.team1.name
            team2_name = settings.teams.team2.name
        
        if self.leader_change:
            leader = team1_name if self.team1_percentage > 50 else team2_name
            title = f"Leader Change: {leader} takes the lead!"
        else:
            title = "Team Standings Update"
        return {
            "title": title,
            "description": f"{team1_name}: {self.team1_percentage:.4f}%, {team2_name}: {100-self.team1_percentage:.4f}%",
            "link": "https://artfight.net/teams",
            "fetchDate": self.fetched_at.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "guid": f"team-standings-{self.fetched_at.strftime('%Y%m%d%H%M%S')}",
        }


class CacheEntry(BaseModel):
    """Cache entry for storing data between requests."""

    key: str = Field(..., description="Cache key")
    data: dict = Field(..., description="Cached data")
    timestamp: datetime = Field(..., description="When this entry was created")
    ttl: int = Field(..., description="Time to live in seconds")

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl


class RSSFeed(BaseModel):
    """RSS feed configuration and data."""

    title: str = Field(..., description="Feed title")
    description: str = Field(..., description="Feed description")
    link: HttpUrl = Field(..., description="Feed link")
    items: list[dict] = Field(default_factory=list, description="Feed items")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update time")

    def to_rss_xml(self) -> str:
        """Convert to RSS XML format."""
        items_xml = ""
        for item in self.items:
            items_xml += f"""
            <item>
                <title>{html.escape(item['title'])}</title>
                <description>{html.escape(item['description'])}</description>
                <link>{item['link']}</link>
                <pubDate>{item['fetchDate']}</pubDate>
                <guid>{item['guid']}</guid>
            </item>
            """

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>{html.escape(self.title)}</title>
        <description>{html.escape(self.description)}</description>
        <link>{self.link}</link>
        <lastBuildDate>{self.last_updated.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
        {items_xml}
    </channel>
</rss>"""
