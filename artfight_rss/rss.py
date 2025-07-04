"""RSS feed generation for Discord RSS bots."""

from urllib.parse import urljoin

from pydantic import parse_obj_as, HttpUrl

from .config import settings
from .models import ArtFightAttack, ArtFightDefense, RSSFeed, TeamStanding


class RSSGenerator:
    """Generate RSS feeds for Discord RSS bots."""

    def __init__(self) -> None:
        """Initialize RSS generator."""
        self.base_url = f"http://{settings.host}:{settings.port}"

    def generate_user_feed(self, username: str, attacks: list[ArtFightAttack]) -> RSSFeed:
        """Generate RSS feed for a user's attacks."""
        feed_url = urljoin(self.base_url, f"/rss/{username}")

        # Convert attacks to RSS items
        items = []
        for attack in attacks:
            items.append(attack.to_rss_item())

        return RSSFeed(
            title=f"ArtFight Attacks on {username}",
            description=f"Recent attacks on {username}'s ArtFight profile",
            link=parse_obj_as(HttpUrl, feed_url),
            items=items
        )

    def generate_team_feed(self, standings: list[TeamStanding]) -> RSSFeed:
        """Generate RSS feed for team standings."""
        feed_url = urljoin(self.base_url, "/rss/teams")

        # Convert standings to RSS items
        items = []
        for standing in standings:
            items.append(standing.to_rss_item())

        return RSSFeed(
            title="ArtFight Team Standings",
            description="Current team standings and side switches",
            link=parse_obj_as(HttpUrl, feed_url),
            items=items
        )

    def generate_team_changes_feed(self, standings: list[TeamStanding]) -> RSSFeed:
        """Generate RSS feed for team standing changes."""
        feed_url = urljoin(self.base_url, "/rss/standings")

        # Convert standings to RSS items
        items = []
        for standing in standings:
            items.append(standing.to_rss_item())

        return RSSFeed(
            title="ArtFight Team Standing Changes",
            description="Team standing changes: daily updates and leader changes",
            link=parse_obj_as(HttpUrl, feed_url),
            items=items
        )

    def generate_empty_user_feed(self, username: str) -> RSSFeed:
        """Generate empty RSS feed for a user."""
        feed_url = urljoin(self.base_url, f"/rss/{username}")

        return RSSFeed(
            title=f"ArtFight Attacks on {username}",
            description=f"Recent attacks on {username}'s ArtFight profile",
            link=parse_obj_as(HttpUrl, feed_url),
            items=[]
        )

    def generate_empty_team_feed(self) -> RSSFeed:
        """Generate empty RSS feed for teams."""
        feed_url = urljoin(self.base_url, "/rss/teams")

        return RSSFeed(
            title="ArtFight Team Standings",
            description="Current team standings and side switches",
            link=parse_obj_as(HttpUrl, feed_url),
            items=[]
        )

    def generate_user_defense_feed(self, username: str, defenses: list[ArtFightDefense]) -> RSSFeed:
        """Generate RSS feed for a user's defenses."""
        feed_url = urljoin(self.base_url, f"/rss/{username}/defenses")

        # Convert defenses to RSS items
        items = []
        for defense in defenses:
            items.append(defense.to_rss_item())

        return RSSFeed(
            title=f"ArtFight Defenses by {username}",
            description=f"Recent defenses by {username} on ArtFight",
            link=parse_obj_as(HttpUrl, feed_url),
            items=items
        )

    def generate_empty_user_defense_feed(self, username: str) -> RSSFeed:
        """Generate empty RSS feed for a user's defenses."""
        feed_url = urljoin(self.base_url, f"/rss/{username}/defenses")

        return RSSFeed(
            title=f"ArtFight Defenses by {username}",
            description=f"Recent defenses by {username} on ArtFight",
            link=parse_obj_as(HttpUrl, feed_url),
            items=[]
        )


# Global RSS generator instance
rss_generator = RSSGenerator()
