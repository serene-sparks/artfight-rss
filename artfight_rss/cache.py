"""Caching system for the ArtFight RSS service using the database."""

from datetime import UTC, datetime
from typing import Any


def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SQLiteCache:
    """Database-based cache with TTL support."""

    def __init__(self, database) -> None:
        """Initialize cache with database instance."""
        self.database = database

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        return self.database.get_cache(key)

    def set(self, key: str, data: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        self.database.set_cache(key, data, ttl)

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        self.database.delete_cache(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self.database.clear_cache()

    def cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        self.database.cleanup_expired_cache()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.database.get_cache_stats()


class RateLimiter:
    """Rate limiter to prevent overwhelming ArtFight."""

    def __init__(self, database, min_interval: int) -> None:
        """Initialize rate limiter."""
        self.database = database
        self.min_interval = min_interval

    def can_request(self, key: str) -> bool:
        """Check if a request can be made."""
        last_request = self.database.get_rate_limit(key)
        if last_request is None:
            return True

        time_since_last = (datetime.now(UTC) - last_request).total_seconds()
        return time_since_last >= self.min_interval

    def record_request(self, key: str) -> None:
        """Record that a request was made."""
        self.database.set_rate_limit(key, self.min_interval)

    def wait_if_needed(self, key: str) -> None:
        """Wait if rate limit would be exceeded."""
        if not self.can_request(key):
            # In a real implementation, you might want to sleep here
            # For now, we'll just return and let the caller handle it
            pass
