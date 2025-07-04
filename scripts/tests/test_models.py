"""Tests for data models."""

from datetime import datetime

from artfight_rss.models import ArtFightAttack, TeamStanding


def test_artfight_attack_creation():
    """Test creating an ArtFightAttack."""
    attack = ArtFightAttack(
        id="test123",
        title="Test Attack",
        description="A test attack",
        attacker_user="attacker_user",
        attacker_user="attacker_user",
        fetched_at=datetime.now(),
        url="https://artfight.net/attack/123"
    )

    assert attack.id == "test123"
    assert attack.title == "Test Attack"
    assert attack.attacker_user == "attacker_user"
    assert attack.attacker_user == "attacker_user"


def test_artfight_attack_to_rss_item():
    """Test converting ArtFightAttack to RSS item."""
    attack = ArtFightAttack(
        id="test123",
        title="Test Attack",
        description="A test attack",
        attacker_user="attacker_user",
        attacker_user="attacker_user",
        fetched_at=datetime(2023, 1, 1, 12, 0, 0),
        url="https://artfight.net/attack/123"
    )

    rss_item = attack.to_rss_item()

    assert rss_item["title"] == "Attack on attacker_user by attacker_user"
    assert rss_item["description"] == "A test attack"
    assert rss_item["link"] == "https://artfight.net/attack/123"
    assert rss_item["guid"] == "test123"


def test_team_standing_creation():
    """Test creating a TeamStanding."""
    standing = TeamStanding(
        name="Test Team",
        score=100,
        side="attack",
        last_switch=datetime.now()
    )

    assert standing.name == "Test Team"
    assert standing.score == 100
    assert standing.side == "attack"


def test_team_standing_to_rss_item():
    """Test converting TeamStanding to RSS item."""
    standing = TeamStanding(
        name="Test Team",
        score=100,
        side="attack",
        last_switch=datetime(2023, 1, 1, 12, 0, 0)
    )

    rss_item = standing.to_rss_item()

    assert rss_item["title"] == "Team Test Team Update"
    assert "Score: 100" in rss_item["description"]
    assert "Side: Attack" in rss_item["description"]
