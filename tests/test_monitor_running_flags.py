import pytest
import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import shutil

from artfight_feed.database import ArtFightDatabase
from artfight_feed.monitor import ArtFightMonitor
from artfight_feed.cache import SQLiteCache, RateLimiter


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_monitor_flags.db"
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
def monitor(mock_cache, mock_rate_limiter, database):
    """Create a monitor instance for testing."""
    monitor = ArtFightMonitor(mock_cache, mock_rate_limiter, database)
    return monitor


class TestMonitorRunningFlags:
    """Test the monitor's separate running flags functionality."""

    def test_initial_flags_state(self, monitor):
        """Test that all running flags start as False."""
        assert monitor.running is False
        assert monitor.news_running is False
        assert monitor.event_monitoring_running is False

    def test_get_stats_includes_all_flags(self, monitor):
        """Test that get_stats includes all running flags."""
        stats = monitor.get_stats()
        
        assert "running" in stats
        assert "news_running" in stats
        assert "event_monitoring_running" in stats
        
        assert stats["running"] is False
        assert stats["news_running"] is False
        assert stats["event_monitoring_running"] is False

    @pytest.mark.asyncio
    async def test_start_sets_all_flags(self, monitor):
        """Test that start() sets the appropriate running flags."""
        # Mock settings to enable news monitoring
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_news = True
            mock_settings.monitor_list = ["testuser"]
            
            await asyncio.wait_for(monitor.start(), timeout=5.0)
            
            # Main running flag should be True
            assert monitor.running is True
            # Event monitoring should be True (team/user monitoring)
            assert monitor.event_monitoring_running is True
            # News monitoring should be True (enabled in settings)
            assert monitor.news_running is True

    @pytest.mark.asyncio
    async def test_start_without_news_monitoring(self, monitor):
        """Test that start() doesn't set news_running when news monitoring is disabled."""
        # Mock settings to disable news monitoring
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_news = False
            mock_settings.monitor_list = ["testuser"]
            
            await asyncio.wait_for(monitor.start(), timeout=5.0)
            
            # Main running flag should be True
            assert monitor.running is True
            # Event monitoring should be True (team/user monitoring)
            assert monitor.event_monitoring_running is True
            # News monitoring should be False (disabled in settings)
            assert monitor.news_running is False

    @pytest.mark.asyncio
    async def test_stop_clears_all_flags(self, monitor):
        """Test that stop() clears all running flags."""
        # Start the monitor first
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_news = True
            mock_settings.monitor_list = ["testuser"]
            
            await asyncio.wait_for(monitor.start(), timeout=5.0)
            assert monitor.running is True
            assert monitor.news_running is True
            assert monitor.event_monitoring_running is True
            
            # Now stop it
            await asyncio.wait_for(monitor.stop(), timeout=5.0)
            
            # All flags should be False
            assert monitor.running is False
            assert monitor.news_running is False
            assert monitor.event_monitoring_running is False

    @pytest.mark.asyncio
    async def test_start_news_monitoring_separately(self, monitor):
        """Test starting only news monitoring."""
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_news = True
            
            await asyncio.wait_for(monitor.start_news_monitoring(), timeout=5.0)
            
            # Only news flag should be True
            assert monitor.news_running is True
            assert monitor.event_monitoring_running is False
            assert monitor.running is False

    @pytest.mark.asyncio
    async def test_stop_news_monitoring_separately(self, monitor):
        """Test stopping only news monitoring."""
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_news = True
            
            # Start news monitoring
            await asyncio.wait_for(monitor.start_news_monitoring(), timeout=5.0)
            assert monitor.news_running is True
            
            # Stop news monitoring
            await asyncio.wait_for(monitor.stop_news_monitoring(), timeout=5.0)
            assert monitor.news_running is False
            assert monitor.event_monitoring_running is False
            assert monitor.running is False

    @pytest.mark.asyncio
    async def test_start_event_monitoring_separately(self, monitor):
        """Test starting only event monitoring."""
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_list = ["testuser"]
            
            await asyncio.wait_for(monitor.start_event_monitoring(), timeout=5.0)
            
            # Only event monitoring flag should be True
            assert monitor.event_monitoring_running is True
            assert monitor.news_running is False
            assert monitor.running is False

    @pytest.mark.asyncio
    async def test_stop_event_monitoring_separately(self, monitor):
        """Test stopping only event monitoring."""
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.monitor_list = ["testuser"]
            
            # Start event monitoring
            await asyncio.wait_for(monitor.start_event_monitoring(), timeout=5.0)
            assert monitor.event_monitoring_running is True
            
            # Stop event monitoring
            await asyncio.wait_for(monitor.stop_event_monitoring(), timeout=5.0)
            assert monitor.event_monitoring_running is False
            assert monitor.news_running is False
            assert monitor.running is False

    @pytest.mark.asyncio
    async def test_news_monitor_loop_uses_news_running_flag(self, monitor):
        """Test that the news monitor loop uses the news_running flag."""
        # Mock the _fetch_news_posts method to avoid actual API calls
        monitor._fetch_news_posts = AsyncMock()
        
        # Mock settings to avoid actual sleep intervals
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.news_check_interval_sec = 0.01  # Very short interval for testing
            
            # Set news_running to True to start the loop
            monitor.news_running = True
            
            # Create a task for the news monitor loop
            task = asyncio.create_task(monitor._news_monitor_loop())
            
            # Wait a bit for the loop to start and make at least one iteration
            await asyncio.sleep(0.05)
            
            # Stop the loop
            monitor.news_running = False
            
            # Wait for the task to complete with timeout
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                # If it times out, cancel the task
                task.cancel()
                await asyncio.sleep(0.01)  # Brief wait for cancellation
            
            # Verify that _fetch_news_posts was called at least once
            monitor._fetch_news_posts.assert_called()

    @pytest.mark.asyncio
    async def test_team_monitor_loop_uses_event_monitoring_flag(self, monitor):
        """Test that the team monitor loop uses the event_monitoring_running flag."""
        # Mock the _fetch_team_standings method to avoid actual API calls
        monitor._fetch_team_standings = AsyncMock()
        
        # Mock settings to avoid actual sleep intervals
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.team_check_interval_sec = 0.01  # Very short interval for testing
            
            # Set event_monitoring_running to True to start the loop
            monitor.event_monitoring_running = True
            
            # Create a task for the team monitor loop
            task = asyncio.create_task(monitor._team_monitor_loop())
            
            # Wait a bit for the loop to start and make at least one iteration
            await asyncio.sleep(0.05)
            
            # Stop the loop
            monitor.event_monitoring_running = False
            
            # Wait for the task to complete with timeout
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                # If it times out, cancel the task
                task.cancel()
                await asyncio.sleep(0.01)  # Brief wait for cancellation
            
            # Verify that _fetch_team_standings was called at least once
            monitor._fetch_team_standings.assert_called()

    @pytest.mark.asyncio
    async def test_user_monitor_loop_uses_event_monitoring_flag(self, monitor):
        """Test that the user monitor loop uses the event_monitoring_running flag."""
        # Mock the _fetch_user_activity method to avoid actual API calls
        monitor._fetch_user_activity = AsyncMock()
        
        # Mock settings to avoid actual sleep intervals
        with patch('artfight_feed.monitor.settings') as mock_settings:
            mock_settings.request_interval = 0.01  # Very short interval for testing
            
            # Set event_monitoring_running to True to start the loop
            monitor.event_monitoring_running = True
            
            # Create a task for the user monitor loop
            task = asyncio.create_task(monitor._user_monitor_loop())
            
            # Wait a bit for the loop to start and make at least one iteration
            await asyncio.sleep(0.05)
            
            # Stop the loop
            monitor.event_monitoring_running = False
            
            # Wait for the task to complete with timeout
            await asyncio.wait_for(task, timeout=1.0)
            
            # Verify that _fetch_user_activity was called at least once
            monitor._fetch_user_activity.assert_called()

    def test_battle_over_detection_stops_event_monitoring(self, monitor):
        """Test that battle over detection stops event monitoring, not news monitoring."""
        # Enable battle over detection
        monitor.battle_over_detection_enabled = True
        
        # Set both flags to True
        monitor.news_running = True
        monitor.event_monitoring_running = True
        
        # Simulate consecutive battle over detections
        monitor.consecutive_battle_over_count = 3
        
        # Call the method that should stop monitoring
        monitor._record_battle_over_detection()
        
        # Event monitoring should be stopped
        assert monitor.event_monitoring_running is False
        # News monitoring should remain running
        assert monitor.news_running is True
        # Main running flag should remain unchanged (legacy compatibility)
        # Note: battle over detection only affects event_monitoring_running, not the main running flag
        assert monitor.running is False  # This is the initial state, not changed by battle over detection

    @pytest.mark.asyncio
    async def test_reset_battle_over_detection_restarts_event_monitoring(self, monitor):
        """Test that resetting battle over detection restarts event monitoring."""
        # Enable battle over detection
        monitor.battle_over_detection_enabled = True
        
        # Set consecutive count to trigger stop condition
        monitor.consecutive_battle_over_count = 3
        monitor.event_monitoring_running = False
        
        # Mock the team task creation
        with patch.object(monitor, '_team_monitor_loop') as mock_loop:
            mock_task = Mock()
            mock_task.done.return_value = True
            monitor.team_task = mock_task
            
            # Reset battle over detection
            monitor.reset_battle_over_detection()
            
            # After reset, event monitoring should be restarted since it wasn't running
            assert monitor.event_monitoring_running is True
            # Consecutive count should be reset
            assert monitor.consecutive_battle_over_count == 0

    def test_individual_monitoring_flags_independence(self, monitor):
        """Test that individual monitoring flags can be controlled independently."""
        # Start with all flags False
        monitor.running = False
        monitor.news_running = False
        monitor.event_monitoring_running = False
        
        # Set only news monitoring
        monitor.news_running = True
        assert monitor.news_running is True
        assert monitor.event_monitoring_running is False
        assert monitor.running is False
        
        # Set only event monitoring
        monitor.news_running = False
        monitor.event_monitoring_running = True
        assert monitor.news_running is False
        assert monitor.event_monitoring_running is True
        assert monitor.running is False
        
        # Set only main running flag
        monitor.event_monitoring_running = False
        monitor.running = True
        assert monitor.news_running is False
        assert monitor.event_monitoring_running is False
        assert monitor.running is True


if __name__ == "__main__":
    pytest.main([__file__])
