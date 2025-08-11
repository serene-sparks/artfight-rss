#!/usr/bin/env python3
"""Test script for configuration loading."""

import os
import sys
from pathlib import Path

# Add the artfight_feed directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'artfight_feed'))

from artfight_feed.config import get_config_paths, load_config, load_toml_config


def test_config_loading():
    """Test the configuration loading system."""
    print("Testing configuration loading...")

    # Test config paths
    print("\nPossible config paths:")
    for path in get_config_paths():
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {path}")

    # Test TOML loading
    config_file = Path("config.toml")
    if config_file.exists():
        print(f"\nLoading TOML config from {config_file}:")
        config_data = load_toml_config(config_file)
        for key, value in config_data.items():
            print(f"  {key}: {value}")

    # Test full config loading
    print("\nLoading full configuration:")
    settings = load_config()

    print(f"  Request interval: {settings.request_interval}")
    print(f"  Team check interval: {settings.team_check_interval_sec}")
    print(f"  ArtFight base URL: {settings.artfight_base_url}")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  Debug: {settings.debug}")
    print(f"  Cache DB path: {settings.cache_db_path}")
    print(f"  Users: {len(settings.users)} configured")
    for user in settings.users:
        print(f"    - {user.username} (enabled: {user.enabled})")
    print(f"  Whitelist: {settings.whitelist}")
    print(f"  Laravel session configured: {settings.laravel_session is not None}")
    print(f"  CF clearance configured: {settings.cf_clearance is not None}")


def test_environment_override():
    """Test environment variable overrides."""
    print("\n" + "="*50)
    print("Testing environment variable overrides...")

    # Set some environment variables
    os.environ["REQUEST_INTERVAL"] = "600"
    os.environ["DEBUG"] = "true"
    os.environ["PORT"] = "9000"

    print("Set environment variables:")
    print("  REQUEST_INTERVAL=600")
    print("  DEBUG=true")
    print("  PORT=9000")

    # Load config again
    settings = load_config()

    print("\nConfiguration after environment overrides:")
    print(f"  Request interval: {settings.request_interval} (should be 600)")
    print(f"  Debug: {settings.debug} (should be True)")
    print(f"  Port: {settings.port} (should be 9000)")

    # Clean up environment variables
    for key in ["REQUEST_INTERVAL", "DEBUG", "PORT"]:
        if key in os.environ:
            del os.environ[key]


if __name__ == "__main__":
    test_config_loading()
    test_environment_override()
