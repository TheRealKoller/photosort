from pathlib import Path

import pytest
from pydantic import ValidationError

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    MISTRAL_VISION_MODEL,
    VISION_MODELS_BY_PROVIDER,
)
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


def test_remote_category_classification_concurrency_defaults_to_two() -> None:
    # ADR 0032 Punkt 5: analog landmark_api_concurrency, aber eigenstaendig einstellbar.
    settings = Settings(_env_file=None)

    assert settings.remote_category_classification_concurrency == 2


def test_remote_category_classification_concurrency_is_env_overridable() -> None:
    settings = Settings(_env_file=None, remote_category_classification_concurrency=8)

    assert settings.remote_category_classification_concurrency == 8


def test_remote_category_classification_concurrency_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, remote_category_classification_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, remote_category_classification_concurrency=-1)


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 1 ab hier: die Modellwahl je Anbieter als zweite
# Betriebseinstellung neben der Anbieterwahl - gepruegt beim Prozessstart, kein stiller Fallback.


def test_landmark_model_defaults_to_empty_meaning_the_provider_default() -> None:
    """Akzeptanzkriterium "ohne gesetzte Einstellung exakt wie bisher": leer heisst "Voreinstellung
    des eingestellten Anbieters", nicht "kein Modell"."""
    settings = Settings(_env_file=None)

    assert settings.landmark_model == ""
    assert settings.resolved_landmark_model() == ANTHROPIC_VISION_MODEL


def test_an_unset_landmark_model_resolves_per_provider() -> None:
    """Beide Anbieter werden gleich behandelt - kein Sonderweg fuer einen von beiden."""
    settings = Settings(_env_file=None, landmark_provider="mistral")

    assert settings.resolved_landmark_model() == MISTRAL_VISION_MODEL


def test_a_configured_landmark_model_is_used_verbatim() -> None:
    second_anthropic_model = VISION_MODELS_BY_PROVIDER["anthropic"][1]

    settings = Settings(_env_file=None, landmark_model=second_anthropic_model)

    assert settings.resolved_landmark_model() == second_anthropic_model


def test_landmark_model_rejects_a_value_outside_the_curated_choice() -> None:
    """Akzeptanzkriterium: ein Wert ausserhalb der gepflegten Auswahl laesst die Anwendung beim
    Start scheitern, statt mitten in einem laufenden Durchgang still fehlzuschlagen."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_model="gpt-4o-mini")


def test_the_rejection_message_names_the_allowed_values() -> None:
    """"Verstaendliche Fehlermeldung" ist das Akzeptanzkriterium - eine Meldung, die nur "ungueltig"
    sagt, laesst den Betreiber ohne den Wert zurueck, den er einsetzen soll."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, landmark_model="gpt-4o-mini")

    message = str(excinfo.value)
    assert "LANDMARK_MODEL" in message
    for allowed in VISION_MODELS_BY_PROVIDER["anthropic"]:
        assert allowed in message


def test_landmark_model_rejects_a_model_that_belongs_to_the_other_provider() -> None:
    """Der Validator prueft gegen die Registry DES EINGESTELLTEN Anbieters (ADR 0059 Punkt 1) -
    ein fuer Anthropic gueltiges Modell unter `mistral` waere sonst ein Aufruf, den der Anbieter
    erst zur Laufzeit ablehnt, mitten im kostenpflichtigen Durchgang."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_provider="mistral", landmark_model=ANTHROPIC_VISION_MODEL)


def test_every_registry_model_of_a_provider_is_actually_configurable() -> None:
    """Gegenprobe zum Ablehnungsfall: die kuratierte Auswahl ist vollstaendig einstellbar, nicht
    nur teilweise."""
    for provider, models in VISION_MODELS_BY_PROVIDER.items():
        for model in models:
            settings = Settings(_env_file=None, landmark_provider=provider, landmark_model=model)

            assert settings.resolved_landmark_model() == model


def test_the_rejection_leaks_no_other_settings_value() -> None:
    """SECURITY-MUSS-KRITERIUM (Spec 0304, Abschnitt Security, Befund `security-engineer`
    2026-09-06): pydantic haengt an eine `ValidationError` die Eingabe an, an der die Pruefung
    scheiterte. Ein `@model_validator(mode="after")` machte das VOLLSTAENDIGE Settings-Dict zu
    dieser Eingabe - `SECRET_KEY`, beide Cloud-API-Keys und das OpenCloud-App-Token landeten
    damit im Startup-Traceback (`docker compose logs`) und in `exc.errors()`/`exc.json()`.

    Deshalb ein Feld-Validator. Geprueft wird gegen BEIDE Darstellungen: `str(exc)` kuerzt lange
    Eingaben und verdeckte das Problem teilweise - ein Test nur dagegen genuegt nicht."""
    markers = {
        "secret_key": "MARKER-SECRET-KEY-AAAA",
        "anthropic_api_key": "MARKER-ANTHROPIC-BBBB",
        "mistral_api_key": "MARKER-MISTRAL-CCCC",
        "opencloud_app_token": "MARKER-OPENCLOUD-DDDD",
    }

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, landmark_model="claude-opus-9", **markers)

    rendered = f"{excinfo.value}\n{excinfo.value.json()}\n{excinfo.value.errors()}"
    for marker in markers.values():
        assert marker not in rendered


def test_landmark_model_rejects_a_mistral_model_under_the_anthropic_provider() -> None:
    """Gegenrichtung zum Test darueber - beide Richtungen sind Pflicht (Fund `test-engineer`):
    die Registry ist asymmetrisch (anthropic mehrere Modelle, mistral eines), eine Implementierung
    mit Sonderbehandlung des Ein-Modell-Anbieters bestuende nur eine der beiden."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_provider="anthropic", landmark_model=MISTRAL_VISION_MODEL)


def test_a_whitespace_padded_model_is_rejected_rather_than_trimmed() -> None:
    """SECURITY-MUSS-KRITERIUM (Spec 0304, Abschnitt Security): der Vergleich ist ein exakter
    Stringvergleich, kein `strip()`/`lower()`. Ein toleriertes " claude-haiku-4-5 " waere ein
    validierter Wert, der so in keiner Registry steht - und ginge byte-abweichend an den
    Anbieter."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_model=f" {ANTHROPIC_VISION_MODEL} ")


def test_landmark_model_is_read_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Test, der nur das Konstruktor-Schluesselwort setzt, belegt den VARIABLENNAMEN nicht -
    und der ist das, was in `.env`/`docker-compose.yml` steht."""
    monkeypatch.setenv("LANDMARK_MODEL", VISION_MODELS_BY_PROVIDER["anthropic"][1])

    settings = Settings(_env_file=None)

    assert settings.resolved_landmark_model() == VISION_MODELS_BY_PROVIDER["anthropic"][1]


def test_an_invalid_provider_with_a_set_model_still_raises_a_validation_error() -> None:
    """Der Validator darf bei einem ungueltigen Anbieter nicht selbst mit einem `KeyError`
    aussteigen - der Startfehler soll die Feldmeldung des Anbieters sein, nicht ein Traceback."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, landmark_provider="openai", landmark_model=ANTHROPIC_VISION_MODEL)


def test_env_example_documents_every_selectable_model() -> None:
    """specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, Akzeptanzkriterium "die neue
    Einstellung ist dort dokumentiert, wo die bestehenden Betriebseinstellungen dokumentiert
    sind, samt Voreinstellung und waehlbaren Werten": ohne diesen Test veraltet die dokumentierte
    Auswahl beim ersten ergaenzten Modell, und der Betreiber erfaehrt von einer Moeglichkeit,
    die es gibt, nichts.

    Scheitert laut statt still, wenn die Datei nicht auffindbar ist."""
    env_example = Path(__file__).resolve().parents[2] / ".env.example"

    assert env_example.is_file(), f"{env_example} nicht gefunden"
    content = env_example.read_text(encoding="utf-8")

    assert "LANDMARK_MODEL=" in content
    for models in VISION_MODELS_BY_PROVIDER.values():
        for model in models:
            assert model in content, model
