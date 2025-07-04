#!/usr/bin/env python3
"""Debug script to check whitelist loading."""

import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path.cwd()))

from artfight_rss.config import settings, load_toml_config, get_config_paths

def debug_whitelist():
    """Debug whitelist loading."""
    print("🔍 Debugging Whitelist Loading")
    print("=" * 50)
    
    # Check config paths
    print(f"\n📁 Config paths:")
    for i, path in enumerate(get_config_paths(), 1):
        exists = "✅" if path.exists() else "❌"
        print(f"  {i}. {path} {exists}")
    
    # Load raw TOML config
    print(f"\n📄 Raw TOML config:")
    for path in get_config_paths():
        if path.exists():
            print(f"  Loading from: {path}")
            raw_config = load_toml_config(path)
            print(f"  Raw config keys: {list(raw_config.keys())}")
            if "whitelist" in raw_config:
                print(f"  Raw whitelist: {raw_config['whitelist']}")
                print(f"  Raw whitelist type: {type(raw_config['whitelist'])}")
            else:
                print(f"  ❌ No whitelist found in raw config")
            break
    
    # Check settings
    print(f"\n⚙️ Settings:")
    print(f"  Settings whitelist: {settings.whitelist}")
    print(f"  Settings whitelist type: {type(settings.whitelist)}")
    print(f"  Settings whitelist length: {len(settings.whitelist)}")
    
    # Test whitelist functionality
    print(f"\n🧪 Whitelist Test:")
    test_user = "fourleafisland"
    if settings.whitelist:
        if test_user in settings.whitelist:
            print(f"  ✅ '{test_user}' is in whitelist")
        else:
            print(f"  ❌ '{test_user}' is NOT in whitelist")
    else:
        print(f"  ⚠️ Whitelist is empty or None")
    
    # Check all settings keys
    print(f"\n📋 All Settings Keys:")
    settings_dict = settings.model_dump()
    for key, value in settings_dict.items():
        if key == "whitelist":
            print(f"  {key}: {value} (type: {type(value)})")
        else:
            print(f"  {key}: {type(value).__name__}")

if __name__ == "__main__":
    debug_whitelist() 