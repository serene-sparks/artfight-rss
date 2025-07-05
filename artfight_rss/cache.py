"""Caching system for the ArtFight RSS service using SQLite."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteCache:
    """SQLite-based cache with TTL support."""

    def __init__(self, db_path: Path) -> None:
        """Initialize cache with database path."""
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database and tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ttl INTEGER NOT NULL
                )
            """)
            conn.commit()

    def _serialize_data(self, data: Any) -> str:
        """Serialize data to JSON string."""
        return json.dumps(data, default=str)

    def _deserialize_data(self, data_str: str) -> Any:
        """Deserialize data from JSON string."""
        return json.loads(data_str)

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, timestamp, ttl FROM cache_entries WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            data_str, timestamp_str, ttl = row
            timestamp = ensure_timezone_aware(datetime.fromisoformat(timestamp_str))

            # Check if expired
            age = (datetime.now(timezone.utc) - timestamp).total_seconds()
            if age > ttl:
                # Remove expired entry
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return None

            return self._deserialize_data(data_str)

    def set(self, key: str, data: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        data_str = self._serialize_data(data)
        timestamp = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries (key, data, timestamp, ttl)
                VALUES (?, ?, ?, ?)
            """, (key, data_str, timestamp, ttl))
            conn.commit()

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()

    def clear(self) -> None:
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

    def cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        with sqlite3.connect(self.db_path) as conn:
            # Get all entries
            cursor = conn.execute("SELECT key, timestamp, ttl FROM cache_entries")
            expired_keys = []

            for row in cursor.fetchall():
                key, timestamp_str, ttl = row
                timestamp = ensure_timezone_aware(datetime.fromisoformat(timestamp_str))
                age = (datetime.now(timezone.utc) - timestamp).total_seconds()

                if age > ttl:
                    expired_keys.append(key)

            # Delete expired entries
            if expired_keys:
                placeholders = ','.join('?' * len(expired_keys))
                conn.execute(f"DELETE FROM cache_entries WHERE key IN ({placeholders})", expired_keys)
                conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
            total_entries = cursor.fetchone()[0]

            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "total_entries": total_entries,
                "database_path": str(self.db_path),
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
            }


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

        time_since_last = (datetime.now(timezone.utc) - last_request).total_seconds()
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
