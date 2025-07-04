#!/usr/bin/env python3
"""Setup script for creating and enabling a systemd service for ArtFight RSS Service."""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(f"STDOUT: {result.stdout}")
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    
    if check and result.returncode != 0:
        print(f"Command failed with return code: {result.returncode}")
        sys.exit(1)
    
    return result

def check_root():
    """Check if running as root."""
    if os.geteuid() != 0:
        print("❌ This script must be run as root (use sudo)")
        print("   Example: sudo python scripts/setup_systemd.py")
        sys.exit(1)

def get_project_root() -> Path:
    """Get the project root directory."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    return project_root

def get_user_input(prompt: str, default: Optional[str] = None) -> str:
    """Get user input with optional default."""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"{prompt}: ").strip()

def read_config_value(config_file: Path, key: str, default: str) -> str:
    """Read a value from config.toml using simple parsing."""
    if not config_file.exists():
        return default
    
    try:
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key) and "=" in line:
                    # Extract the value after the equals sign
                    value = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    return value
        return default
    except Exception:
        return default

def create_venv(project_root: Path, user: str, group: str):
    """Create a Python virtual environment."""
    venv_path = project_root / "venv"
    
    print(f"Creating virtual environment: {venv_path}")
    
    # Create virtual environment
    run_command([sys.executable, "-m", "venv", str(venv_path)])
    
    # Set ownership
    run_command(["chown", "-R", f"{user}:{group}", str(venv_path)])
    
    # Get the Python executable path
    python_path = venv_path / "bin" / "python"
    pip_path = venv_path / "bin" / "pip"
    
    print("✅ Virtual environment created")
    return python_path, pip_path

def install_dependencies(pip_path: Path, project_root: Path, user: str, group: str):
    """Install dependencies in the virtual environment."""
    print("Installing dependencies...")
    
    # Upgrade pip first
    run_command([str(pip_path), "install", "--upgrade", "pip"])
    
    # Install dependencies from pyproject.toml
    run_command([str(pip_path), "install", "-e", str(project_root)])
    
    # Set ownership again after installation
    run_command(["chown", "-R", f"{user}:{group}", str(project_root / "venv")])
    
    print("✅ Dependencies installed")

def create_systemd_service(project_root: Path, user: str, group: str, host: str, port: int, python_path: Path):
    """Create the systemd service file."""
    service_content = f"""[Unit]
Description=ArtFight RSS Service
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={project_root}
Environment=PYTHONPATH={project_root}
ExecStart={python_path} -m uvicorn artfight_rss.main:app --host {host} --port {port}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=artfight-rss

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
#ProtectSystem=strict
ProtectHome=yes
#ReadWritePaths={project_root}

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("/etc/systemd/system/artfight-rss.service")
    print(f"Creating systemd service file: {service_file}")
    
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print("✅ Systemd service file created")

def setup_directories(project_root: Path, user: str, group: str):
    """Set up directories and permissions."""
    # Create data directory if it doesn't exist
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Create cache directory if it doesn't exist
    cache_dir = project_root / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # Set ownership
    run_command(["chown", "-R", f"{user}:{group}", str(project_root)])
    
    # Set permissions
    run_command(["chmod", "755", str(project_root)])
    run_command(["chmod", "755", str(data_dir)])
    run_command(["chmod", "755", str(cache_dir)])
    
    print("✅ Directory permissions set")

def enable_and_start_service():
    """Enable and start the systemd service."""
    # Reload systemd daemon
    run_command(["systemctl", "daemon-reload"])
    
    # Enable the service
    run_command(["systemctl", "enable", "artfight-rss"])
    
    # Start the service
    run_command(["systemctl", "start", "artfight-rss"])
    
    print("✅ Service enabled and started")

def verify_database_path(project_root: Path, user: str):
    """Verify that the database path in config.toml is writable."""
    config_file = project_root / "config.toml"
    if not config_file.exists():
        print("❌ config.toml not found!")
        return False
    
    try:
        # Simple TOML parsing for db_path using standard library
        db_path_str = "data/artfight_data.db"  # Default path
        
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("db_path") and "=" in line:
                    # Extract the value after the equals sign
                    value = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    db_path_str = value
                    break
        
        db_path = project_root / db_path_str
        
        # Check if the directory is writable
        db_dir = db_path.parent
        if not db_dir.exists():
            print(f"❌ Database directory does not exist: {db_dir}")
            print(f"   Please ensure the directory exists and is writable by user '{user}'")
            return False
        
        # Test if the user can write to the directory
        test_file = db_dir / ".test_write"
        try:
            test_file.touch()
            test_file.unlink()
            print(f"✅ Database path is writable: {db_path}")
            return True
        except (PermissionError, OSError):
            print(f"❌ Database path is not writable: {db_path}")
            print(f"   Directory: {db_dir}")
            print(f"   User: {user}")
            print(f"   Please ensure the directory is writable by user '{user}'")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying database path: {e}")
        return False

def check_service_status():
    """Check the service status."""
    print("\n🔍 Checking service status...")
    run_command(["systemctl", "status", "artfight-rss"], check=False)
    
    print("\n📋 Service management commands:")
    print("  View logs:     journalctl -u artfight-rss -f")
    print("  Stop service:  sudo systemctl stop artfight-rss")
    print("  Start service: sudo systemctl start artfight-rss")
    print("  Restart:       sudo systemctl restart artfight-rss")
    print("  Disable:       sudo systemctl disable artfight-rss")

def main():
    """Main setup function."""
    print("🚀 ArtFight RSS Service - Systemd Setup")
    print("=" * 50)
    
    # Check if running as root
    check_root()
    
    # Get project root
    project_root = get_project_root()
    print(f"📁 Project root: {project_root}")
    
    # Check if config.toml exists
    config_file = project_root / "config.toml"
    if not config_file.exists():
        print("❌ config.toml not found!")
        print("   Please create a config.toml file first:")
        print(f"   cp {project_root}/config.example.toml {project_root}/config.toml")
        print("   Then edit it with your settings.")
        sys.exit(1)
    
    # Check if pyproject.toml exists
    pyproject_file = project_root / "pyproject.toml"
    if not pyproject_file.exists():
        print("❌ pyproject.toml not found!")
        print("   This script requires a pyproject.toml file for dependency installation.")
        sys.exit(1)
    
    # Read host and port from config file
    config_file = project_root / "config.toml"
    default_host = read_config_value(config_file, "host", "0.0.0.0")
    default_port = read_config_value(config_file, "port", "8000")
    
    # Get user input
    print("\n📝 Configuration:")
    user = get_user_input("Service user", "artfight-rss")
    group = get_user_input("Service group", user)
    host = get_user_input("Service host", default_host)
    port = get_user_input("Service port", default_port)
    
    # Validate host
    if not host or host.strip() == "":
        print("❌ Host cannot be empty.")
        sys.exit(1)
    
    # Validate port
    try:
        port_int = int(port)
        if port_int < 1 or port_int > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        print("❌ Invalid port number. Must be between 1 and 65535.")
        sys.exit(1)
    
    # Check if user exists
    try:
        subprocess.run(["id", user], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"❌ User '{user}' does not exist!")
        print(f"   Create the user first: sudo useradd -r -s /bin/false {user}")
        sys.exit(1)
    
    # Check if group exists
    try:
        subprocess.run(["getent", "group", group], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"❌ Group '{group}' does not exist!")
        print(f"   Create the group first: sudo groupadd {group}")
        sys.exit(1)
    
    print(f"\n✅ Configuration validated:")
    print(f"   User: {user}")
    print(f"   Group: {group}")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    
    # Confirm installation
    print(f"\n⚠️  This will:")
    print(f"   - Create a Python virtual environment in {project_root}/venv")
    print(f"   - Install dependencies from pyproject.toml")
    print(f"   - Create systemd service: /etc/systemd/system/artfight-rss.service")
    print(f"   - Set ownership of {project_root} to {user}:{group}")
    print(f"   - Enable and start the service")
    print(f"   - The service will run on {host}:{port}")
    
    confirm = input("\nContinue? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Installation cancelled")
        sys.exit(0)
    
    try:
        # Create virtual environment
        python_path, pip_path = create_venv(project_root, user, group)
        
        # Install dependencies
        install_dependencies(pip_path, project_root, user, group)
        
        # Setup directories
        setup_directories(project_root, user, group)
        
        # Verify database path is writable
        if not verify_database_path(project_root, user):
            print("❌ Database path verification failed. Please fix the configuration.")
            sys.exit(1)
        
        # Create systemd service
        create_systemd_service(project_root, user, group, host, port_int, python_path)
        
        # Enable and start service
        enable_and_start_service()
        
        # Check status
        check_service_status()
        
        print("\n🎉 ArtFight RSS Service has been successfully installed as a systemd service!")
        print(f"   The service is now running on http://{host}:{port}")
        print(f"   RSS feeds will be available at:")
        print(f"   - http://{host}:{port}/rss/username/attacks")
        print(f"   - http://{host}:{port}/rss/username/defenses")
        print(f"   - http://{host}:{port}/rss/standings")
        print(f"\n📁 Virtual environment: {project_root}/venv")
        print(f"   To update dependencies: sudo -u {user} {pip_path} install -e {project_root} --upgrade")
        
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        print("   Check the error messages above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main() 