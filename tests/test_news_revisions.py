import pytest
import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import shutil

from artfight_feed.database import ArtFightDatabase
from artfight_feed.models import ArtFightNews, NewsRevision
from artfight_feed.event_handlers import DiscordEventHandler, LoggingEventHandler
from artfight_feed.monitor import ArtFightMonitor
from artfight_feed.artfight import ArtFightClient
from artfight_feed.cache import SQLiteCache
from artfight_feed.cache import RateLimiter


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_news_revisions.db"
    yield db_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def database(temp_db_path):
    """Create a test database instance."""
    db = ArtFightDatabase(temp_db_path)
    # Run migrations to create the database schema
    db.migrate()
    return db

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for tests."""
    # Configure logging to capture all levels
    logging.basicConfig(level=logging.INFO)
    # Ensure the artfight_feed logger is at INFO level
    logging.getLogger('artfight_feed').setLevel(logging.INFO)

@pytest.fixture
def mock_artfight_client():
    """Create a mock ArtFight client."""
    client = Mock(spec=ArtFightClient)
    client.get_news_posts = AsyncMock()
    return client

@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock(spec=SQLiteCache)
    cache.get_stats.return_value = {}
    return cache

@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    return Mock(spec=RateLimiter)

@pytest.fixture
def monitor(mock_cache, mock_rate_limiter, database, mock_artfight_client):
    """Create a monitor instance for testing."""
    monitor = ArtFightMonitor(mock_cache, mock_rate_limiter, database)
    monitor.artfight_client = mock_artfight_client
    monitor.database = database
    
    # Set up event handlers for testing
    from artfight_feed.event_handlers import setup_event_handlers
    setup_event_handlers(monitor)
    
    return monitor


@pytest.fixture
def sample_news_post():
    """Create a sample news post for testing."""
    return ArtFightNews(
        id=1,
        title="Test News Post",
        content="<p>This is a test news post with <strong>HTML content</strong>.</p>",
        author="testuser",
        posted_at=datetime.now(timezone.utc),
        edited_at=None,
        edited_by=None,
        url="https://artfight.net/news/1",
        fetched_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_news_post_updated():
    """Create an updated version of the sample news post."""
    return ArtFightNews(
        id=1,
        title="Test News Post Updated",
        content="<p>This is an updated test news post with <em>different HTML content</em>.</p>",
        author="testuser",
        posted_at=datetime.now(timezone.utc),
        edited_at=datetime.now(timezone.utc),
        edited_by="testuser",
        url="https://artfight.net/news/1",
        fetched_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_news_post_title_only_change():
    """Create a news post with only title change."""
    return ArtFightNews(
        id=1,
        title="Test News Post - Title Changed",
        content="<p>This is a test news post with <strong>HTML content</strong>.</p>",  # Same content
        author="testuser",
        posted_at=datetime.now(timezone.utc),
        edited_at=datetime.now(timezone.utc),
        edited_by="testuser",
        url="https://artfight.net/news/1",
        fetched_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_news_post_content_only_change():
    """Create a news post with only content change."""
    return ArtFightNews(
        id=1,
        title="Test News Post",  # Same title
        content="<p>This is a test news post with <em>completely different content</em>.</p>",
        author="testuser",
        posted_at=datetime.now(timezone.utc),
        edited_at=datetime.now(timezone.utc),
        edited_by="testuser",
        url="https://artfight.net/news/1",
        fetched_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_news_post_no_meaningful_changes():
    """Create a news post with no meaningful changes (only metadata changes)."""
    return ArtFightNews(
        id=1,
        title="Test News Post",  # Same title
        content="<p>This is a test news post with <strong>HTML content</strong>.</p>",  # Same content
        author="testuser",
        posted_at=datetime.now(timezone.utc),
        edited_at=datetime.now(timezone.utc),  # Different timestamp
        edited_by="testuser",  # Different editor
        url="https://artfight.net/news/1",
        fetched_at=datetime.now(timezone.utc),  # Different fetch time
        first_seen=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc)
    )


class TestNewsRevisionDatabase:
    """Test the database logic for news revisions."""

    def test_get_next_revision_number_new_post(self, database):
        """Test getting revision number for a new news post."""
        revision_number = database.get_next_revision_number(1)
        assert revision_number == 1

    def test_get_next_revision_number_existing_revisions(self, database, sample_news_post):
        """Test getting revision number when revisions already exist."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Create a revision
        revision = NewsRevision(
            news_id=1,
            revision_number=1,
            title=sample_news_post.title,
            content=sample_news_post.content,
            author=sample_news_post.author,
            posted_at=sample_news_post.posted_at,
            edited_at=sample_news_post.edited_at,
            edited_by=sample_news_post.edited_by,
            url=sample_news_post.url,
            fetched_at=sample_news_post.fetched_at,
            created_at=datetime.now(timezone.utc)
        )
        database.save_news_revision(revision)
        
        # Get next revision number
        next_revision = database.get_next_revision_number(1)
        assert next_revision == 2

    def test_save_news_new_post(self, database, sample_news_post):
        """Test saving a new news post."""
        results = database.save_news([sample_news_post])
        
        assert len(results) == 1
        current_post, old_post = results[0]
        assert current_post.id == 1
        assert old_post is None
        
        # Verify it was saved to database
        saved_news = database.get_existing_news_by_id(1)
        assert saved_news is not None
        assert saved_news.title == "Test News Post"

    def test_save_news_title_change_creates_revision(self, database, sample_news_post, sample_news_post_title_only_change):
        """Test that title changes create a revision."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save updated news post with title change
        results = database.save_news([sample_news_post_title_only_change])
        
        assert len(results) == 1
        current_post, old_post = results[0]
        assert current_post.id == 1
        assert old_post is not None
        assert old_post.title == "Test News Post"
        assert current_post.title == "Test News Post - Title Changed"
        
        # Verify revision was created
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM news_revisions WHERE news_id = ?", (1,))
            revision_count = cursor.fetchone()[0]
            assert revision_count == 1

    def test_save_news_content_change_creates_revision(self, database, sample_news_post, sample_news_post_content_only_change):
        """Test that content changes create a revision."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save updated news post with content change
        results = database.save_news([sample_news_post_content_only_change])
        
        assert len(results) == 1
        current_post, old_post = results[0]
        assert current_post.id == 1
        assert old_post is not None
        assert old_post.content == "<p>This is a test news post with <strong>HTML content</strong>.</p>"
        assert current_post.content == "<p>This is a test news post with <em>completely different content</em>.</p>"
        
        # Verify revision was created
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM news_revisions WHERE news_id = ?", (1,))
            revision_count = cursor.fetchone()[0]
            assert revision_count == 1

    def test_save_news_metadata_changes_creates_revision(self, database, sample_news_post, sample_news_post_no_meaningful_changes):
        """Test that metadata changes (editor/date changes) create a revision."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save news post with only metadata changes
        results = database.save_news([sample_news_post_no_meaningful_changes])
        
        assert len(results) == 1
        current_post, old_post = results[0]
        assert current_post.id == 1
        assert old_post is not None  # Revision should be created for metadata changes
        
        # Verify revision was created
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM news_revisions WHERE news_id = ?", (1,))
            revision_count = cursor.fetchone()[0]
            assert revision_count == 1

    def test_save_news_both_title_and_content_changes(self, database, sample_news_post, sample_news_post_updated):
        """Test that both title and content changes create a revision."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save updated news post with both changes
        results = database.save_news([sample_news_post_updated])
        
        assert len(results) == 1
        current_post, old_post = results[0]
        assert current_post.id == 1
        assert old_post is not None
        
        # Verify revision was created
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM news_revisions WHERE news_id = ?", (1,))
            revision_count = cursor.fetchone()[0]
            assert revision_count == 1

    def test_save_news_html_to_markdown_conversion(self, database):
        """Test that HTML content is properly converted to markdown for comparison."""
        # Create news post with HTML content
        html_news = ArtFightNews(
            id=1,
            title="HTML Test",
            content="<p>This is <strong>bold</strong> and <em>italic</em> text.</p>",
            author="testuser",
            posted_at=datetime.now(timezone.utc),
            edited_at=None,
            edited_by=None,
            url="https://artfight.net/news/1",
            fetched_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc)
        )
        
        # Save initial news post
        database.save_news([html_news])
        
        # Create news post with equivalent markdown content
        markdown_equivalent_news = ArtFightNews(
            id=1,
            title="HTML Test",
            content="<p>This is <strong>bold</strong> and <em>italic</em> text.</p>",
            author="testuser",
            posted_at=datetime.now(timezone.utc),
            edited_at=datetime.now(timezone.utc),
            edited_by="testuser",
            url="https://artfight.net/news/1",
            fetched_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc)
        )
        
                # Save the equivalent content - should create revision due to metadata changes
        results = database.save_news([markdown_equivalent_news])
    
        assert len(results) == 1
        current_post, old_post = results[0]
        assert old_post is not None  # Revision created for metadata changes (edited_at, edited_by)
        
        # Verify revision was created for metadata changes
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM news_revisions WHERE news_id = ?", (1,))
            revision_count = cursor.fetchone()[0]
            assert revision_count == 1  # Revision created for metadata changes (edited_at, edited_by)


class TestNewsRevisionEventHandlers:
    """Test the event handlers for news revisions."""

    @pytest.fixture
    def mock_discord_bot(self):
        """Create a mock Discord bot."""
        bot = Mock()
        bot.send_news_revision_notification = AsyncMock()
        return bot

    @pytest.fixture
    def discord_handler(self, mock_discord_bot):
        """Create a Discord event handler with mocked bot."""
        handler = DiscordEventHandler()
        # Mock the global discord_bot import
        with patch('artfight_feed.event_handlers.discord_bot', mock_discord_bot):
            yield handler

    @pytest.fixture
    def logging_handler(self):
        """Create a logging event handler."""
        return LoggingEventHandler()

    @pytest.mark.asyncio
    async def test_discord_handler_post_revised(self, discord_handler, sample_news_post, sample_news_post_updated, mock_discord_bot):
        """Test Discord handler for post revised event."""
        revision_data = {
            'old_post': sample_news_post,
            'new_post': sample_news_post_updated
        }
        
        # Mock the global discord_bot import
        with patch('artfight_feed.event_handlers.discord_bot', mock_discord_bot):
            await discord_handler.handle_post_revised(revision_data)
        
        # Verify Discord notification was sent
        mock_discord_bot.send_news_revision_notification.assert_called_once_with(
            sample_news_post, sample_news_post_updated
        )

    @pytest.mark.asyncio
    async def test_logging_handler_post_revised(self, monitor, sample_news_post, sample_news_post_updated, caplog):
        """Test logging handler for post revised event."""
        # Save initial news post
        monitor.database.save_news([sample_news_post])
        
        # Save updated news post (should create revision and emit event)
        monitor.database.save_news([sample_news_post_updated])
        
        # Manually emit the post_revised event to trigger the logging handler
        revision_data = {
            'old_post': sample_news_post,
            'new_post': sample_news_post_updated
        }
        await monitor.emit_event('post_revised', revision_data)
        
        # Verify logging occurred
        assert "News post revised: Test News Post Updated (ID: 1)" in caplog.text
        assert "Content changed - Visual diff:" in caplog.text
        assert "Title changed: 'Test News Post' -> 'Test News Post Updated'" in caplog.text

    @pytest.mark.asyncio
    async def test_logging_handler_post_revised_title_only(self, monitor, sample_news_post, sample_news_post_title_only_change, caplog):
        """Test logging handler for post revised event with title change only."""
        # Save initial news post
        monitor.database.save_news([sample_news_post])
        
        # Save updated news post (should create revision and emit event)
        monitor.database.save_news([sample_news_post_title_only_change])
        
        # Manually emit the post_revised event to trigger the logging handler
        revision_data = {
            'old_post': sample_news_post,
            'new_post': sample_news_post_title_only_change
        }
        await monitor.emit_event('post_revised', revision_data)
        
        # Verify logging occurred
        assert "News post revised: Test News Post - Title Changed (ID: 1)" in caplog.text
        assert "Title changed: 'Test News Post' -> 'Test News Post - Title Changed'" in caplog.text
        # Content should not have changed
        assert "Content changed" not in caplog.text


class TestNewsRevisionMonitor:
    """Test the monitor logic for news revisions."""

    @pytest.mark.asyncio
    async def test_fetch_news_posts_detects_revision(self, monitor, sample_news_post, sample_news_post_updated):
        """Test that monitor detects news revisions and emits events."""
        # Set up mock to return updated news post
        monitor.artfight_client.get_news_posts.return_value = [sample_news_post_updated]
        
        # Mock event emission
        emitted_events = []
        original_emit_event = monitor.emit_event
        
        async def mock_emit_event(event_type, data):
            emitted_events.append((event_type, data))
        
        monitor.emit_event = mock_emit_event
        
        # Save initial news post
        monitor.database.save_news([sample_news_post])
        
        # Fetch news posts (should detect revision)
        await monitor._fetch_news_posts()
        
        # Verify revision event was emitted
        assert len(emitted_events) == 1
        event_type, event_data = emitted_events[0]
        assert event_type == 'post_revised'
        assert event_data['old_post'].id == 1
        assert event_data['new_post'].id == 1
        assert event_data['old_post'].title == "Test News Post"
        assert event_data['new_post'].title == "Test News Post Updated"

    @pytest.mark.asyncio
    async def test_fetch_news_posts_metadata_changes_creates_revision(self, monitor, sample_news_post, sample_news_post_no_meaningful_changes):
        """Test that monitor emits revision event when metadata changes occur."""
        # Set up mock to return news post with metadata changes
        monitor.artfight_client.get_news_posts.return_value = [sample_news_post_no_meaningful_changes]
        
        # Mock event emission
        emitted_events = []
        original_emit_event = monitor.emit_event
        
        async def mock_emit_event(event_type, data):
            emitted_events.append((event_type, data))
        
        monitor.emit_event = mock_emit_event
        
        # Save initial news post
        monitor.database.save_news([sample_news_post])
        
        # Fetch news posts (should detect revision due to metadata changes)
        await monitor._fetch_news_posts()
        
        # Verify revision event was emitted
        assert len(emitted_events) == 1
        event_type, event_data = emitted_events[0]
        assert event_type == 'post_revised'
        # event_data should be a dict with 'old_post' and 'new_post' keys
        assert 'old_post' in event_data
        assert 'new_post' in event_data
        assert event_data['new_post'].id == 1  # current_post
        assert event_data['old_post'].id == 1  # old_post (revision)

    @pytest.mark.asyncio
    async def test_fetch_news_posts_new_post_event(self, monitor, sample_news_post):
        """Test that monitor emits new_news event for new posts."""
        # Set up mock to return new news post
        monitor.artfight_client.get_news_posts.return_value = [sample_news_post]
        
        # Mock event emission
        emitted_events = []
        original_emit_event = monitor.emit_event
        
        async def mock_emit_event(event_type, data):
            emitted_events.append((event_type, data))
        
        monitor.emit_event = mock_emit_event
        
        # Fetch news posts (should detect new post)
        await monitor._fetch_news_posts()
        
        # Verify new_news event was emitted
        assert len(emitted_events) == 1
        event_type, event_data = emitted_events[0]
        assert event_type == 'new_news'
        assert event_data.id == 1
        assert event_data.title == "Test News Post"

    @pytest.mark.asyncio
    async def test_multiple_news_posts_emitted_in_chronological_order(self, monitor):
        """Test that multiple news posts are processed and events emitted in chronological order."""
        from datetime import datetime, timezone, timedelta
        
        # Create multiple news posts with different timestamps
        now = datetime.now(timezone.utc)
        
        # Create posts in reverse chronological order (oldest first)
        news_post_1 = ArtFightNews(
            id=1,
            title="First News Post",
            content="<p>This is the first news post.</p>",
            author="user1",
            posted_at=now - timedelta(hours=3),  # 3 hours ago
            edited_at=None,
            edited_by=None,
            url="https://artfight.net/news/1",
            fetched_at=now - timedelta(hours=3),
            first_seen=now - timedelta(hours=3),
            last_updated=now - timedelta(hours=3)
        )
        
        news_post_2 = ArtFightNews(
            id=2,
            title="Second News Post",
            content="<p>This is the second news post.</p>",
            author="user2",
            posted_at=now - timedelta(hours=2),  # 2 hours ago
            edited_at=None,
            edited_by=None,
            url="https://artfight.net/news/2",
            fetched_at=now - timedelta(hours=2),
            first_seen=now - timedelta(hours=2),
            last_updated=now - timedelta(hours=2)
        )
        
        news_post_3 = ArtFightNews(
            id=3,
            title="Third News Post",
            content="<p>This is the third news post.</p>",
            author="user3",
            posted_at=now - timedelta(hours=1),  # 1 hour ago
            edited_at=None,
            edited_by=None,
            url="https://artfight.net/news/3",
            fetched_at=now - timedelta(hours=1),
            first_seen=now - timedelta(hours=1),
            last_updated=now - timedelta(hours=1)
        )
        
        # Set up mock to return all three news posts
        monitor.artfight_client.get_news_posts.return_value = [news_post_1, news_post_2, news_post_3]
        
        # Mock event emission to capture order
        emitted_events = []
        original_emit_event = monitor.emit_event
        
        async def mock_emit_event(event_type, data):
            emitted_events.append((event_type, data))
        
        monitor.emit_event = mock_emit_event
        
        # Fetch news posts (should detect all three as new posts)
        await monitor._fetch_news_posts()
        
        # Verify all three new_news events were emitted
        assert len(emitted_events) == 3, f"Expected 3 events, got {len(emitted_events)}"
        
        # Verify all events are new_news events
        for event_type, event_data in emitted_events:
            assert event_type == 'new_news', f"Expected new_news event, got {event_type}"
        
        # Verify events are emitted in chronological order (oldest first)
        # The monitor processes posts in the order they're returned from the API
        # and emits events for each new post in that order
        assert emitted_events[0][1].id == 1, "First event should be for post ID 1"
        assert emitted_events[0][1].title == "First News Post"
        assert emitted_events[0][1].posted_at == now - timedelta(hours=3)
        
        assert emitted_events[1][1].id == 2, "Second event should be for post ID 2"
        assert emitted_events[1][1].title == "Second News Post"
        assert emitted_events[1][1].posted_at == now - timedelta(hours=2)
        
        assert emitted_events[2][1].id == 3, "Third event should be for post ID 3"
        assert emitted_events[2][1].title == "Third News Post"
        assert emitted_events[2][1].posted_at == now - timedelta(hours=1)
        
        # Verify the chronological order is maintained
        assert emitted_events[0][1].posted_at < emitted_events[1][1].posted_at, "First post should be older than second"
        assert emitted_events[1][1].posted_at < emitted_events[2][1].posted_at, "Second post should be older than third"
        
        # Verify all posts were saved to database
        saved_posts = monitor.database.get_news()
        assert len(saved_posts) == 3, f"Expected 3 posts in database, got {len(saved_posts)}"
        
        # Verify posts in database are ordered by ID (newest first as per get_news method)
        assert saved_posts[0].id == 3, "First post in database should be newest (ID 3)"
        assert saved_posts[1].id == 2, "Second post in database should be middle (ID 2)"
        assert saved_posts[2].id == 1, "Third post in database should be oldest (ID 1)"


class TestNewsRevisionIntegration:
    """Integration tests for the complete news revision flow."""

    @pytest.fixture
    def mock_discord_bot(self):
        """Create a mock Discord bot."""
        bot = Mock()
        bot.send_news_revision_notification = AsyncMock()
        bot.send_news_notification = AsyncMock()
        return bot

    @pytest.mark.asyncio
    async def test_complete_revision_flow(self, database, sample_news_post, sample_news_post_updated, mock_discord_bot):
        """Test the complete flow from database save to Discord notification."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save updated news post (should create revision)
        results = database.save_news([sample_news_post_updated])
        
        # Verify revision was created
        assert len(results) == 1
        current_post, old_post = results[0]
        assert old_post is not None
        
        # Create event handler and process revision
        discord_handler = DiscordEventHandler()
        
        revision_data = {
            'old_post': old_post,
            'new_post': current_post
        }
        
        # Mock the global discord_bot import
        with patch('artfight_feed.event_handlers.discord_bot', mock_discord_bot):
            await discord_handler.handle_post_revised(revision_data)
        
        # Verify Discord notification was sent
        mock_discord_bot.send_news_revision_notification.assert_called_once_with(
            old_post, current_post
        )

    @pytest.mark.asyncio
    async def test_metadata_changes_create_revision_but_no_discord_notification(self, database, sample_news_post, sample_news_post_no_meaningful_changes, mock_discord_bot):
        """Test that metadata changes create a revision but Discord notification is not sent."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save news post with metadata changes
        results = database.save_news([sample_news_post_no_meaningful_changes])
        
        # Verify revision was created for metadata changes
        assert len(results) == 1
        current_post, old_post = results[0]
        assert old_post is not None  # Revision should be created
        
        # Test the Discord bot's logic directly to verify it correctly identifies no substantial changes
        from artfight_feed.discord_bot import ArtFightDiscordBot
        
        # Create a real Discord bot instance but stub the webhook method
        discord_bot = ArtFightDiscordBot()
        
        # Mock the settings and set the bot to running state
        with patch('artfight_feed.discord_bot.settings') as mock_settings, \
             patch.object(discord_bot, 'webhook', new_callable=AsyncMock) as mock_webhook:
            
            # Configure mock settings
            mock_settings.discord_notify_news = True
            discord_bot.running = True
            
            # Call the notification method directly
            await discord_bot.send_news_revision_notification(old_post, current_post)
            
            # Verify webhook was NOT called (because no substantial changes)
            mock_webhook.send.assert_not_called()
        
        # Verify that the posts have the same title and content (markdown)
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        
        old_markdown = h.handle(old_post.content).strip() if old_post.content else ""
        new_markdown = h.handle(current_post.content).strip() if current_post.content else ""
        
        # Verify no substantial changes (title and content are the same)
        assert old_post.title == current_post.title, "Title should be the same"
        assert old_markdown == new_markdown, "Content (markdown) should be the same"
        
        # Verify that only metadata changed
        assert old_post.edited_at != current_post.edited_at, "Edit date should have changed"
        assert old_post.edited_by != current_post.edited_by, "Editor should have changed"

    @pytest.mark.asyncio
    async def test_substantial_changes_do_send_discord_notification(self, database, sample_news_post, sample_news_post_updated):
        """Test that substantial changes (title/content) DO send Discord notifications."""
        # Save initial news post
        database.save_news([sample_news_post])
        
        # Save updated news post with substantial changes
        results = database.save_news([sample_news_post_updated])
        
        # Verify revision was created
        assert len(results) == 1
        current_post, old_post = results[0]
        assert old_post is not None
        
        # Test the Discord bot's logic directly to verify it correctly identifies substantial changes
        from artfight_feed.discord_bot import ArtFightDiscordBot
        
        # Create a real Discord bot instance but stub the webhook method
        discord_bot = ArtFightDiscordBot()
        
        # Mock the settings and set the bot to running state
        with patch('artfight_feed.discord_bot.settings') as mock_settings, \
             patch.object(discord_bot, 'webhook', new_callable=AsyncMock) as mock_webhook:
            
            # Configure mock settings
            mock_settings.discord_notify_news = True
            discord_bot.running = True
            
            # Call the notification method directly
            await discord_bot.send_news_revision_notification(old_post, current_post)
            
            # Verify webhook WAS called (because there ARE substantial changes)
            mock_webhook.send.assert_called_once()
            
            # Verify the webhook was called with an embed
            call_args = mock_webhook.send.call_args
            assert call_args is not None  # Should have been called
            
            # The webhook.send should be called with embed as a keyword argument
            # Check that embed was passed
            assert 'embed' in call_args.kwargs
            embed = call_args.kwargs['embed']
            
            # Verify the embed contains the expected information
            assert embed.title is not None
            assert "News Post Revised" in embed.title
            assert embed.description is not None
            # The description should mention what changed, not the title
            assert "title and content" in embed.description.lower()  # Should mention what changed
            
            # Check that the title field contains the updated title
            title_field = None
            for field in embed.fields:
                if field.name == "📊 Changes Made":
                    title_field = field
                    break
            assert title_field is not None, "Changes Made field should exist"
            assert "Title" in title_field.value, "Changes field should mention title changes"
        
        # Verify that the posts have different title or content
        assert old_post.title != current_post.title, "Title should have changed"
        
        # Verify that metadata also changed
        assert old_post.edited_at != current_post.edited_at, "Edit date should have changed"
        assert old_post.edited_by != current_post.edited_by, "Editor should have changed"


if __name__ == "__main__":
    pytest.main([__file__])
