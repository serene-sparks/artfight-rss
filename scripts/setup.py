#!/usr/bin/env python3
"""Setup script for ArtFight Webhook Service."""

import shutil
from pathlib import Path


def main():
    """Run the setup process."""
    print("🎨 ArtFight Webhook Service Setup")
    print("=" * 40)

    # Check if config.toml exists
    config_path = Path("config.toml")
    if config_path.exists():
        print("⚠️  config.toml already exists. Skipping configuration setup.")
    else:
        # Copy example config
        example_config = Path("config.example.toml")
        if example_config.exists():
            shutil.copy(example_config, config_path)
            print("✅ Created config.toml from example")
            print("📝 Please edit config.toml with your Discord webhook URLs and ArtFight usernames")
        else:
            print("❌ config.example.toml not found")

    # Check if .env exists
    env_path = Path(".env")
    if env_path.exists():
        print("⚠️  .env already exists. Skipping environment setup.")
    else:
        # Copy example env
        example_env = Path("env.example")
        if example_env.exists():
            shutil.copy(example_env, env_path)
            print("✅ Created .env from example")
            print("📝 Please edit .env with your environment variables")
        else:
            print("❌ env.example not found")

    # Create cache directory for SQLite database
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)
    print("✅ Created cache directory for SQLite database")

    print("\n🚀 Setup complete!")
    print("\nNext steps:")
    print("1. Edit config.toml with your Discord webhook URLs and ArtFight usernames")
    print("2. Edit .env with your environment variables (optional)")
    print("3. Install dependencies: uv sync")
    print("4. Run the service: uv run python -m artfight_rss.main")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
