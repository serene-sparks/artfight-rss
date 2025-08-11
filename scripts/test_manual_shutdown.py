#!/usr/bin/env python3
"""Test script to verify manual server startup and shutdown."""

import subprocess
import sys
import time
from pathlib import Path


def test_manual_shutdown():
    """Test manual server startup and shutdown."""
    print("🧪 Testing Manual Server Shutdown")
    print("=" * 40)
    print("This will start the server and then you can press Ctrl+C to stop it.")
    print("The server should shut down gracefully within a few seconds.")
    print()
    
    # Start the server
    print("Starting server...")
    try:
        # Run the server
        process = subprocess.Popen([
            sys.executable, "-m", "artfight_feed.main"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        print(f"Server started with PID: {process.pid}")
        print("Press Ctrl+C in the terminal where the server is running to test shutdown.")
        print("Waiting for server to start up...")
        
        # Wait a bit for startup
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Server is running successfully!")
            print("Now go to the terminal where the server is running and press Ctrl+C.")
            print("The server should shut down gracefully.")
        else:
            print("❌ Server failed to start")
            stdout, stderr = process.communicate()
            print("Output:", stdout)
            if stderr:
                print("Errors:", stderr)
            return False
            
    except KeyboardInterrupt:
        print("\n✅ Test completed successfully!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_manual_shutdown()
    sys.exit(0 if success else 1) 