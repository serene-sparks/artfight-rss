"""Tests for data models."""

from datetime import datetime, timezone

from pydantic import HttpUrl

from artfight_rss.models import ArtFightAttack, TeamStanding


def test_artfight_attack_creation():
    """Test creating an ArtFightAttack."""
    attack = ArtFightAttack(
        id="test123",
        title="Test Attack",
        description="A test attack",
        attacker_user="attacker_user",
        defender_user="defender_user",
        fetched_at=datetime.now(timezone.utc),
        url=HttpUrl("https://artfight.net/attack/123")
    )

    assert attack.id == "test123"
    assert attack.title == "Test Attack"
    assert attack.attacker_user == "attacker_user"
    assert attack.defender_user == "defender_user"


def test_artfight_attack_to_atom_item():
    """Test converting ArtFightAttack to Atom item."""
    attack = ArtFightAttack(
        id="test123",
        title="Test Attack",
        description="A test attack",
        attacker_user="attacker_user",
        defender_user="defender_user",
        fetched_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        url=HttpUrl("https://artfight.net/attack/123")
    )

    atom_item = attack.to_atom_item()

    assert atom_item["title"] == "Test Attack"
    assert atom_item["description"] == "A test attack"
    assert atom_item["link"] == "https://artfight.net/attack/123"
    assert atom_item["entry_id"] == "https://artfight.net/attack/123"
    assert atom_item["author"] == "attacker_user"


def test_team_standing_creation():
    """Test creating a TeamStanding."""
    standing = TeamStanding(
        team1_percentage=60.0,
        fetched_at=datetime.now(timezone.utc),
        leader_change=False
    )

    assert standing.team1_percentage == 60.0
    assert standing.leader_change == False


def test_team_standing_to_atom_item():
    """Test converting TeamStanding to Atom item."""
    standing = TeamStanding(
        team1_percentage=60.0,
        fetched_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        leader_change=True
    )

    atom_item = standing.to_atom_item()

    assert "Team Standings Update" in atom_item["title"]
    assert "60.00000%" in atom_item["description"]
    assert atom_item["author"] is None
