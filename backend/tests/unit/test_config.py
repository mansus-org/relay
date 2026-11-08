import pytest
from pydantic import ValidationError

from relay.main import check_secret_key
from relay.shared.config import DEV_SECRET_KEY, Settings


def test_defaults_use_sqlite() -> None:
    settings = Settings()
    assert settings.database_url.startswith("sqlite+aiosqlite://")
    assert settings.log_level == "INFO"


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/relay")
    monkeypatch.setenv("VERSION", "1.2.3")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://u:p@db/relay"
    assert settings.version == "1.2.3"
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u@h/db", "postgresql+asyncpg://u@h/db"),
        ("postgres://u@h/db", "postgresql+asyncpg://u@h/db"),
        ("sqlite:///x.db", "sqlite+aiosqlite:///x.db"),
        ("sqlite+aiosqlite:///x.db", "sqlite+aiosqlite:///x.db"),
    ],
)
def test_database_url_gets_async_driver(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected


def test_rejects_unknown_log_level() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="LOUD")


def test_web_dist_dir_is_off_by_default_and_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().web_dist_dir is None
    monkeypatch.setenv("WEB_DIST_DIR", "")
    assert Settings().web_dist_dir is None
    monkeypatch.setenv("WEB_DIST_DIR", "/srv/web")
    assert str(Settings().web_dist_dir) == "/srv/web"


def test_a_relay_still_on_the_development_key_refuses_to_start() -> None:
    """That key is published in this repository, so anything signed with it can be forged."""
    with pytest.raises(RuntimeError, match="forge a session"):
        check_secret_key(Settings(secret_key=DEV_SECRET_KEY))


def test_running_on_the_development_key_has_to_be_said_out_loud() -> None:
    check_secret_key(Settings(secret_key=DEV_SECRET_KEY, allow_insecure_secret_key=True))


def test_a_key_nobody_else_knows_needs_no_permission() -> None:
    check_secret_key(Settings(secret_key="something-only-this-machine-knows"))
