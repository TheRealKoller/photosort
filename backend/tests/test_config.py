from photosort.config import Settings


def test_settings_have_sane_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql")
    assert settings.redis_url.startswith("redis://")
    assert settings.opencloud_base_url == ""
    assert settings.opencloud_app_token == ""
    assert settings.opencloud_username == ""
    assert settings.opencloud_drive_name == ""


def test_rate_limit_storage_uri_falls_back_to_redis_url() -> None:
    # rate_limit_storage_uri wird hier explizit leer gesetzt, da der Testlauf selbst
    # RATE_LIMIT_STORAGE_URI=memory:// exportiert (siehe conftest.py) - explizite Kwargs haben
    # bei pydantic-settings Vorrang vor Umgebungsvariablen.
    settings = Settings(
        _env_file=None, redis_url="redis://example:6379/2", rate_limit_storage_uri=""
    )

    assert settings.resolved_rate_limit_storage_uri() == "redis://example:6379/2"


def test_rate_limit_storage_uri_override_takes_precedence() -> None:
    settings = Settings(
        _env_file=None, redis_url="redis://example:6379/2", rate_limit_storage_uri="memory://"
    )

    assert settings.resolved_rate_limit_storage_uri() == "memory://"
