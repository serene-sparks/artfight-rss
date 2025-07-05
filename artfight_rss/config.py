"""Configuration management for the ArtFight webhook service."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class UserConfig(BaseModel):
    """Configuration for a single user to monitor."""

    username: str = Field(..., description="ArtFight username")
    enabled: bool = Field(default=True, description="Whether to monitor this user")


class TeamConfig(BaseModel):
    """Configuration for a team in ArtFight."""

    name: str = Field(..., description="Team name")
    color: str = Field(..., description="Team color hex code (e.g., #BA8C25)")
    image_url: str = Field(..., description="Team image URL for RSS feeds")


class TeamSettings(BaseModel):
    """Configuration for the two ArtFight teams."""

    team1: TeamConfig = Field(..., description="First team configuration")
    team2: TeamConfig = Field(..., description="Second team configuration")


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source for TOML configuration files."""

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Get field value from TOML config."""
        # Load TOML config from any available path
        for path in get_config_paths():
            if path.exists():
                config_data = load_toml_config(path)
                if config_data and field_name in config_data:
                    print(f"✅ Found {field_name} in TOML config: {path}")
                    return config_data[field_name], field_name, False

        return None, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        """Prepare field value for specific field types."""
        if value is None:
            return None

        if field_name == "users" and isinstance(value, list):
            # Handle users list - convert dicts to UserConfig objects
            return [UserConfig(**user) for user in value]
        elif field_name == "teams" and isinstance(value, dict):
            # Handle teams configuration - convert to TeamSettings object
            return TeamSettings(**value)
        elif field_name == "whitelist" and isinstance(value, list):
            # Handle whitelist
            return value
        elif field_name in ["cache_db_path", "db_path"] and isinstance(value, str):
            # Convert string path to Path object
            return Path(value)
        else:
            # Handle other simple values
            return value

    def __call__(self) -> dict[str, Any]:
        """Load all settings from TOML files."""
        print("🔍 Checking for TOML configuration files...")

        # Load TOML config from any available path
        for path in get_config_paths():
            print(f"  Checking path: {path}")
            if path.exists():
                print(f"  Found config file: {path}")
                config_data = load_toml_config(path)
                if config_data:
                    print(f"✅ Loaded configuration from: {path}")
                    print(f"  Config keys: {list(config_data.keys())}")

                    # Convert TOML data to be compatible with pydantic-settings
                    processed_data = {}

                    for key, value in config_data.items():
                        if key == "users":
                            # Handle users list - convert dicts to UserConfig objects
                            processed_data["users"] = [UserConfig(**user) for user in value]
                            print(f"  Processed {len(value)} users")
                        elif key == "teams":
                            # Handle teams configuration - convert to TeamSettings object
                            processed_data["teams"] = TeamSettings(**value)
                            print("  Processed teams configuration")
                        elif key == "whitelist":
                            # Handle whitelist
                            processed_data["whitelist"] = value
                            print(f"  Processed whitelist with {len(value)} entries")
                        elif key == "cache_db_path":
                            # Convert string path to Path object
                            processed_data["cache_db_path"] = Path(value)
                        elif key == "db_path":
                            # Convert string path to Path object
                            processed_data["db_path"] = Path(value)
                        else:
                            # Handle other simple values
                            processed_data[key] = value

                    print(f"  Returning processed data with keys: {list(processed_data.keys())}")
                    return processed_data

        print("❌ No configuration file found, using defaults and environment variables")
        return {}


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="",  # No prefix for environment variables
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize configuration sources with proper precedence."""
        return (
            init_settings,  # Highest precedence: explicit kwargs
            env_settings,   # Second: environment variables
            dotenv_settings,  # Third: .env file
            file_secret_settings,  # Fourth: file secrets
            TomlConfigSettingsSource(settings_cls),  # Fifth: TOML file (lowest precedence)
        )

    # General settings
    request_interval: int = Field(
        default=300,  # 5 minutes
        description="Minimum seconds between requests to ArtFight"
    )
    team_check_interval_sec: int = Field(
        default=3600,  # 1 hour
        description="How often to check team standings (seconds)"
    )
    team_switch_threshold_sec: int = Field(
        default=24 * 3600,  # 24 hours
        description="Seconds since last switch before forcing update"
    )
    page_request_delay_sec: float = Field(
        default=3.0,  # 3 seconds
        description="Delay between page requests during pagination (seconds)"
    )
    page_request_wobble: float = Field(
        default=0.2,  # ±20%
        description="Random wobble factor for page request delays (0.0 = no wobble, 0.2 = ±20%)"
    )

    # User monitoring
    users: list[UserConfig] = Field(
        default_factory=list,
        description="List of users to monitor"
    )

    whitelist: list[str] = Field(
        default_factory=list,
        description="List of supported ArtFight profiles"
    )

    # Team configuration
    teams: TeamSettings | None = Field(
        default=None,
        description="Configuration for the two ArtFight teams"
    )

    @field_validator('whitelist', mode='before')
    @classmethod
    def parse_whitelist(cls, v):
        """Parse whitelist from various sources."""
        if isinstance(v, str):
            # Handle JSON string from environment variable
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, treat as comma-separated string
                return [item.strip() for item in v.split(',') if item.strip()]
        elif isinstance(v, list):
            return v
        else:
            return []

    # Cache settings
    cache_db_path: Path = Field(
        default=Path("cache/artfight_cache.db"),
        description="Path to SQLite cache database"
    )

    # ArtFight settings
    artfight_base_url: str = Field(
        default="https://artfight.net",
        description="Base URL for ArtFight"
    )

    # Authentication settings
    laravel_session: str | None = Field(
        default=None,
        description="ArtFight Laravel session cookie for authenticated requests"
    )
    cf_clearance: str | None = Field(
        default=None,
        description="Cloudflare clearance cookie for bypassing protection"
    )
    remember_web: str | None = Field(
        default=None,
        description="ArtFight remember web cookie for persistent authentication"
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    live_reload: bool = Field(default=False, description="Enable live reload for development")

    # RSS feed settings
    max_users_per_feed: int = Field(default=5, description="Maximum number of users allowed in a single multiuser feed")
    max_feed_items: int = Field(default=50, description="Maximum number of items returned in a feed")

    @field_validator('max_feed_items')
    @classmethod
    def validate_max_feed_items(cls, v):
        """Validate that max_feed_items is at least 1."""
        if v < 1:
            raise ValueError(f"max_feed_items must be at least 1, got {v}")
        return v

    @field_validator('max_users_per_feed')
    @classmethod
    def validate_max_users_per_feed(cls, v):
        """Validate that max_users_per_feed is at least 1."""
        if v < 1:
            raise ValueError(f"max_users_per_feed must be at least 1, got {v}")
        return v

    # Database settings
    db_path: Path = Field(
        default=Path("data/artfight_data.db"),
        description="Path to the permanent SQLite database"
    )


def load_toml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file."""
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Could not load TOML config from {config_path}: {e}")
        return {}


def get_config_paths() -> list[Path]:
    """Get list of possible config file paths in order of preference."""
    current_dir = Path.cwd()
    return [
        current_dir / "config.toml",
        current_dir / "config" / "config.toml",
        current_dir / "artfight_rss" / "config.toml",
        Path.home() / ".config" / "artfight-rss" / "config.toml",
        Path("/etc/artfight-rss/config.toml"),
    ]


def load_toml_config_from_any_path() -> dict[str, Any]:
    """Load TOML configuration from the first available path."""
    for path in get_config_paths():
        if path.exists():
            config_data = load_toml_config(path)
            if config_data:
                print(f"Loaded configuration from: {path}")
                return config_data

    print("No configuration file found, using defaults and environment variables")
    return {}


def load_config() -> Settings:
    """Load configuration using the custom sources."""
    return Settings()


# Global settings instance
settings = load_config()
