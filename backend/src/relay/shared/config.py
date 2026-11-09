from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DRIVER_PREFIXES = {
    "sqlite://": "sqlite+aiosqlite://",
    "postgresql://": "postgresql+asyncpg://",
    "postgres://": "postgresql+asyncpg://",
}

# Signs access tokens when nothing is configured: fine on a laptop and in tests, and
# main.py shouts at startup until SECRET_KEY is set to something nobody can guess.
DEV_SECRET_KEY = "insecure-dev-secret-change-me"  # noqa: S105 - it is not meant to be a secret


class Settings(BaseSettings):
    """Process configuration. Built once in main.py and passed to whoever needs it."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    database_url: str = Field(default="sqlite+aiosqlite:///./relay.db")
    secret_key: str = Field(default=DEV_SECRET_KEY, description="Signs access tokens (SECRET_KEY)")
    allow_insecure_secret_key: bool = Field(
        default=False,
        description=(
            "Start anyway with the development SECRET_KEY, which anyone can forge "
            "(ALLOW_INSECURE_SECRET_KEY). A laptop only, never a deployment."
        ),
    )
    admin_username: str | None = Field(
        default=None,
        description="Create this account if the database has nobody yet (ADMIN_USERNAME)",
    )
    admin_password: str | None = Field(
        default=None,
        description="Password for ADMIN_USERNAME, at least 8 characters (ADMIN_PASSWORD)",
    )
    version: str = Field(default="dev")
    log_level: str = Field(default="INFO")
    web_dist_dir: Path | None = Field(default=None, description="Exported web build to serve at /")
    stream_keepalive_seconds: float = Field(
        default=30.0,
        description=(
            "How long a live stream goes quiet before it sends a keepalive comment "
            "(STREAM_KEEPALIVE_SECONDS). Shorter than whatever sits in front of Relay "
            "closes an idle connection for, or the stream drops for nobody at all."
        ),
    )

    @field_validator("web_dist_dir", mode="before")
    @classmethod
    def _empty_means_disabled(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("database_url")
    @classmethod
    def _use_async_driver(cls, value: str) -> str:
        """Accept plain sqlite:// and postgresql:// URLs and pick the async driver."""
        for prefix, replacement in _DRIVER_PREFIXES.items():
            if value.startswith(prefix):
                return replacement + value.removeprefix(prefix)
        return value

    @field_validator("log_level")
    @classmethod
    def _normalise_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(f"unknown log level: {value}")
        return level
