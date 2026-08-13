from photosort.config import Settings


def test_settings_have_sane_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql")
    assert settings.redis_url.startswith("redis://")
    assert settings.opencloud_base_url == ""
    assert settings.opencloud_app_token == ""
    assert settings.opencloud_username == ""
    assert settings.opencloud_drive_name == ""
    assert settings.photo_cache_dir == "/data/photo-cache"


def test_auth_seed_user_placeholder_defaults_are_distinct() -> None:
    # Regressionsschutz (Review-Fund test-engineer): identische Platzhalter-Defaults fuer
    # beide Seed-User wuerden bei unveraendertem .env dazu fuehren, dass die idempotente
    # Seed-Migration nur EINEN statt zwei Accounts anlegt (der zweite Aufruf faende den
    # Username des ersten bereits vor und ueberspringt ihn still) - siehe seed.py::seed_user.
    settings = Settings(_env_file=None)

    assert settings.auth_seed_user1_username != settings.auth_seed_user2_username


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


def test_cors_allowed_origins_has_sane_local_dev_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins_list() == [
        "http://localhost:5173",
        "http://localhost:8080",
    ]


def test_cors_allowed_origins_list_parses_comma_separated_env_value() -> None:
    settings = Settings(_env_file=None, cors_allowed_origins="https://photos.example.com")

    assert settings.cors_allowed_origins_list() == ["https://photos.example.com"]


def test_category_selection_enabled_defaults_to_true() -> None:
    # Rein lokal/kostenlos (specs/features/0024-top-photo-selection-category-mix.md) - kein Grund
    # fuer einen restriktiven Default wie bei einem Cloud-Feature.
    settings = Settings(_env_file=None)

    assert settings.category_selection_enabled is True


def test_scan_download_concurrency_defaults_to_four() -> None:
    # specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020: echter
    # Betriebsparameter (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud), env-
    # ueberschreibbar via SCAN_DOWNLOAD_CONCURRENCY - Default 4 konservativ gewaehlt.
    settings = Settings(_env_file=None)

    assert settings.scan_download_concurrency == 4


def test_scan_download_concurrency_is_env_overridable() -> None:
    settings = Settings(_env_file=None, scan_download_concurrency=8)

    assert settings.scan_download_concurrency == 8


def test_cors_allowed_origins_list_strips_whitespace_around_entries() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=" https://a.example.com , https://b.example.com ",
    )

    assert settings.cors_allowed_origins_list() == [
        "https://a.example.com",
        "https://b.example.com",
    ]
