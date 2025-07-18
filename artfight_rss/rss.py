"""Atom feed generation for Discord RSS bots."""

from urllib.parse import urljoin

from .config import settings
from .models import ArtFightAttack, ArtFightDefense, AtomFeed, TeamStanding


class AtomGenerator:
    """Generate Atom feeds for Discord RSS bots."""

    def __init__(self) -> None:
        """Initialize Atom generator."""
        self.base_url = f"http://{settings.host}:{settings.port}"

    def generate_user_feed(self, username: str, attacks: list[ArtFightAttack]) -> AtomFeed:
        """Generate Atom feed for a user's attacks."""
        feed_url = urljoin(self.base_url, f"/rss/{username}")
        feed_id = f"artfight-attacks-{username}"

        feed = AtomFeed(
            title=f"ArtFight Attacks on {username}",
            description=f"Recent attacks on {username}'s ArtFight profile",
            link=feed_url,
            feed_id=feed_id
        )

        # Add attacks to feed
        for attack in attacks:
            feed.add_item(
                title=attack.title,
                description=attack.description or f"New attack: '{attack.title}' by {attack.attacker_user} on {attack.defender_user}.",
                link=str(attack.url),
                published=attack.fetched_at,
                entry_id=str(attack.url),
                author=attack.attacker_user,
                image_url=str(attack.image_url) if attack.image_url else None
            )

        return feed

    def generate_team_changes_feed(self, standings: list[TeamStanding]) -> AtomFeed:
        """Generate Atom feed for team standing changes."""
        feed_url = urljoin(self.base_url, "/rss/standings")
        feed_id = "artfight-team-standings"

        feed = AtomFeed(
            title="ArtFight Team Standing Changes",
            description="Team standing changes: daily updates and leader changes",
            link=feed_url,
            feed_id=feed_id
        )

        # Add standings to feed
        for standing in standings:
            # Use the enhanced to_atom_item method from the model
            atom_item = standing.to_atom_item()
            
            feed.add_item(
                title=atom_item["title"],
                description=atom_item["description"],
                link=atom_item["link"] or feed_url,
                published=atom_item["published"],
                entry_id=atom_item["entry_id"],
                image_url=atom_item["image_url"]
            )

        return feed



    def generate_user_defense_feed(self, username: str, defenses: list[ArtFightDefense]) -> AtomFeed:
        """Generate Atom feed for a user's defenses."""
        feed_url = urljoin(self.base_url, f"/rss/{username}/defenses")
        feed_id = f"artfight-defenses-{username}"

        feed = AtomFeed(
            title=f"ArtFight Defenses by {username}",
            description=f"Recent defenses by {username} on ArtFight",
            link=feed_url,
            feed_id=feed_id
        )

        # Add defenses to feed
        for defense in defenses:
            feed.add_item(
                title=defense.title,
                description=defense.description or f"New defense: '{defense.title}' by `{defense.attacker_user}` on `{defense.defender_user}`.\n\n![Image]({defense.image_url})",
                link=str(defense.url),
                published=defense.fetched_at,
                entry_id=str(defense.url),
                author=defense.attacker_user,
                image_url=str(defense.image_url) if defense.image_url else None
            )

        return feed

    def generate_multiuser_attacks_feed(self, usernames: list[str], attacks: list[ArtFightAttack]) -> AtomFeed:
        """Generate Atom feed for multiple users' attacks."""
        if len(usernames) > settings.max_users_per_feed:
            usernames = usernames[:settings.max_users_per_feed]

        usernames_str = "+".join(usernames)
        feed_url = urljoin(self.base_url, f"/rss/attacks/{usernames_str}")
        feed_id = f"artfight-attacks-{usernames_str}"

        feed = AtomFeed(
            title=f"ArtFight Attacks - {usernames_str}",
            description=f"Recent attacks by {usernames_str} on ArtFight",
            link=feed_url,
            feed_id=feed_id
        )

        # Add attacks to feed
        for attack in attacks:
            feed.add_item(
                title=attack.title,
                description=attack.description or f"New attack: '{attack.title}' by {attack.attacker_user} on {attack.defender_user}.",
                link=str(attack.url),
                published=attack.fetched_at,
                entry_id=str(attack.url),
                author=attack.attacker_user,
                image_url=str(attack.image_url) if attack.image_url else None
            )

        return feed

    def generate_multiuser_defenses_feed(self, usernames: list[str], defenses: list[ArtFightDefense]) -> AtomFeed:
        """Generate Atom feed for multiple users' defenses."""
        if len(usernames) > settings.max_users_per_feed:
            usernames = usernames[:settings.max_users_per_feed]

        usernames_str = "+".join(usernames)
        feed_url = urljoin(self.base_url, f"/rss/defenses/{usernames_str}")
        feed_id = f"artfight-defenses-{usernames_str}"

        feed = AtomFeed(
            title=f"ArtFight Defenses - {usernames_str}",
            description=f"Recent defenses by {usernames_str} on ArtFight",
            link=feed_url,
            feed_id=feed_id
        )

        # Add defenses to feed
        for defense in defenses:
            feed.add_item(
                title=defense.title,
                description=defense.description or f"New defense: '{defense.title}' by {defense.attacker_user} on {defense.defender_user}.",
                link=str(defense.url),
                published=defense.fetched_at,
                entry_id=str(defense.url),
                author=defense.attacker_user,
                image_url=str(defense.image_url) if defense.image_url else None
            )

        return feed

    def generate_multiuser_combined_feed(self, usernames: list[str], attacks: list[ArtFightAttack], defenses: list[ArtFightDefense]) -> AtomFeed:
        """Generate combined Atom feed for multiple users' attacks and defenses."""
        if len(usernames) > settings.max_users_per_feed:
            usernames = usernames[:settings.max_users_per_feed]

        usernames_str = "+".join(usernames)
        feed_url = urljoin(self.base_url, f"/rss/combined/{usernames_str}")
        feed_id = f"artfight-combined-{usernames_str}"

        feed = AtomFeed(
            title=f"ArtFight Activity - {usernames_str}",
            description=f"Recent attacks and defenses by {usernames_str} on ArtFight",
            link=feed_url,
            feed_id=feed_id
        )

        # Combine attacks and defenses and sort by publish date (newest first)
        all_items = []

        # Add attacks with type indicator
        for attack in attacks:
            all_items.append({
                'type': 'attack',
                'item': attack,
                'fetched_at': attack.fetched_at
            })

        # Add defenses with type indicator
        for defense in defenses:
            all_items.append({
                'type': 'defense',
                'item': defense,
                'fetched_at': defense.fetched_at
            })

        # Sort by fetched_at (newest first)
        all_items.sort(key=lambda x: x['fetched_at'], reverse=True)

        # Add items to feed in chronological order
        for item_data in all_items:
            if item_data['type'] == 'attack':
                attack = item_data['item']
                feed.add_item(
                    title=attack.title,
                    description=attack.description or f"New attack: '{attack.title}' by {attack.attacker_user} on {attack.defender_user}.",
                    link=str(attack.url),
                    published=attack.fetched_at,
                    entry_id=str(attack.url),
                    author=attack.attacker_user,
                    image_url=str(attack.image_url) if attack.image_url else None
                )
            else:  # defense
                defense = item_data['item']
                feed.add_item(
                    title=defense.title,
                    description=defense.description or f"New defense: '{defense.title}' by {defense.attacker_user} on {defense.defender_user}.",
                    link=str(defense.url),
                    published=defense.fetched_at,
                    entry_id=str(defense.url),
                    author=defense.attacker_user,
                    image_url=str(defense.image_url) if defense.image_url else None
                )

        return feed


# Global Atom generator instance
rss_generator = AtomGenerator()
