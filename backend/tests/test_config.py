import pytest
from pydantic import ValidationError

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


def test_scan_download_concurrency_rejects_non_positive_values() -> None:
    # test-engineer-/security-engineer-Review-Fund (PR zu Spec 0036): fail-fast am
    # Konfigurationsrand statt eines stillen Clamps tief im Worker-Code (worker.py verlaesst sich
    # seitdem auf diese Validierung statt selbst zu klemmen).
    with pytest.raises(ValidationError):
        Settings(_env_file=None, scan_download_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, scan_download_concurrency=-1)


def test_opencloud_folder_count_concurrency_defaults_to_four() -> None:
    # specs/features/0050-dateianzahl-im-ordner-browser.md, ADR decisions/0028: echter
    # Betriebsparameter (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud beim parallelen
    # Zaehlen mehrerer Unterordner), analog scan_download_concurrency (ADR 0020).
    settings = Settings(_env_file=None)

    assert settings.opencloud_folder_count_concurrency == 4


def test_opencloud_folder_count_concurrency_is_env_overridable() -> None:
    settings = Settings(_env_file=None, opencloud_folder_count_concurrency=8)

    assert settings.opencloud_folder_count_concurrency == 8


def test_opencloud_folder_count_concurrency_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, opencloud_folder_count_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, opencloud_folder_count_concurrency=-1)


def test_cors_allowed_origins_list_strips_whitespace_around_entries() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=" https://a.example.com , https://b.example.com ",
    )

    assert settings.cors_allowed_origins_list() == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_anthropic_api_key_defaults_to_empty_string() -> None:
    # specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR
    # decisions/0025-cloud-landmark-erkennung.md: exakt das opencloud_app_token-Muster, kein
    # Format-Check - der Platzhalter existierte bereits in .env.example, war aber nie verdrahtet.
    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == ""


def test_landmark_api_concurrency_defaults_to_two() -> None:
    # ADR 0025 Punkt 3: bewusst konservativer als scan_download_concurrency (Default 4) - reales
    # Geld pro Anfrage und ein fremdes Rate-Limit.
    settings = Settings(_env_file=None)

    assert settings.landmark_api_concurrency == 2


def test_landmark_api_concurrency_is_env_overridable() -> None:
    settings = Settings(_env_file=None, landmark_api_concurrency=8)

    assert settings.landmark_api_concurrency == 8


def test_landmark_api_concurrency_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_api_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_api_concurrency=-1)


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 3 ab hier: Mistral als zweite, per Settings.landmark_provider
# waehlbare Cloud-Provider-Option fuer das landmark-Kriterium.


def test_landmark_provider_defaults_to_anthropic() -> None:
    settings = Settings(_env_file=None)

    assert settings.landmark_provider == "anthropic"


def test_landmark_provider_is_env_overridable() -> None:
    settings = Settings(_env_file=None, landmark_provider="mistral")

    assert settings.landmark_provider == "mistral"


def test_landmark_provider_rejects_an_unknown_value() -> None:
    # Akzeptanzkriterium der Spec: kein stiller Fallback auf "anthropic" bei einem Tippfehler,
    # sondern ein harter Fehlschlag beim Prozessstart.
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_provider="openai")


def test_mistral_api_key_defaults_to_empty_string() -> None:
    # Exakt das anthropic_api_key-Muster (kein Format-Check, nur ueber Env-Variable gesetzt).
    settings = Settings(_env_file=None)

    assert settings.mistral_api_key == ""
