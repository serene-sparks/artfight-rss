#!/usr/bin/env python3
"""Simple test to check TOML file contents."""

import tomllib
from pathlib import Path

def test_toml():
    """Test TOML file parsing."""
    config_path = Path("config.toml")
    
    if not config_path.exists():
        print("❌ config.toml not found")
        return
    
    print(f"📄 Reading {config_path}")
    
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        
        print(f"✅ Successfully loaded TOML")
        print(f"📋 Keys found: {list(data.keys())}")
        
        for key, value in data.items():
            print(f"  {key}: {type(value).__name__} = {value}")
            
    except Exception as e:
        print(f"❌ Error reading TOML: {e}")

if __name__ == "__main__":
    test_toml() 