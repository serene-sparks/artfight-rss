#!/usr/bin/env python3
"""Debug script to check environment variable loading and configuration."""

import os

from artfight_rss.config import settings

print("🔍 Environment Variable Debug")
print("=" * 50)

print("📋 Environment Variables:")
print(f"  LARAVEL_SESSION: {os.environ.get('LARAVEL_SESSION', 'NOT SET')}")
print(f"  CF_CLEARANCE: {os.environ.get('CF_CLEARANCE', 'NOT SET')}")
print(f"  REMEMBER_WEB: {os.environ.get('REMEMBER_WEB', 'NOT SET')}")

print("\n⚙️  Loaded Configuration Settings:")
print("  Authentication:")
print(f"    laravel_session: {settings.laravel_session}")
print(f"    cf_clearance: {settings.cf_clearance}")
print(f"    remember_web: {settings.remember_web}")

print("\n  Server Settings:")
print(f"    host: {settings.host}")
print(f"    port: {settings.port}")
print(f"    debug: {settings.debug}")

print("\n  ArtFight Settings:")
print(f"    artfight_base_url: {settings.artfight_base_url}")

print("\n  Request Settings:")
print(f"    request_interval: {settings.request_interval}s")
print(f"    team_check_interval: {settings.team_check_interval_sec}s")
print(f"    team_switch_threshold: {settings.team_switch_threshold_sec}h")
print(f"    page_request_delay: {settings.page_request_delay_sec}s")
print(f"    page_request_wobble: {settings.page_request_wobble}")

print("\n  Database Settings:")
print(f"    db_path: {settings.db_path}")
print(f"    cache_db_path: {settings.cache_db_path}")

print("\n  User Monitoring:")
print(f"    users: {len(settings.users)} configured")
for i, user in enumerate(settings.users, 1):
    print(f"      {i}. {user.username} (enabled: {user.enabled})")
print(f"    whitelist: {len(settings.whitelist)} entries")

print("\n🔍 Boolean Checks:")
print(f"  bool(settings.laravel_session): {bool(settings.laravel_session)}")
print(f"  bool(settings.cf_clearance): {bool(settings.cf_clearance)}")
print(f"  bool(settings.remember_web): {bool(settings.remember_web)}")

print("\n✅ Configuration loaded successfully!")
