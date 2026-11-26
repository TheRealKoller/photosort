"""Die veroeffentlichte Schnittstellenbeschreibung traegt keine Geheimnisse und keine Infrastruktur.

`backend/openapi.json` liegt dauerhaft im oeffentlichen Repository. Beschrieben wird Verhalten an
der HTTP-Grenze; Werte aus `settings` und Umgebungsvariablen (Hosts, Ports, Tokens, Passwoerter,
Volume-Pfade) gehoeren nicht hinein. Der Test setzt SENTINEL-Werte fuer jedes geheimnis- und
infrastrukturtragende Feld und prueft die serialisierte Beschreibung - faende sich ein Wert dort,
stuende er auch in der eingecheckten Datei.

`servers` fehlt oder nennt nur `"/"`: eine absolute Serveradresse waere eine Deployment-Aussage,
die an keiner Stelle dieser Anwendung entschieden wird.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from photosort.config import settings
from photosort.main import create_app

ARTEFAKT: Final = Path(__file__).resolve().parents[1] / "openapi.json"

# Ein Wert je Feld, der in der Beschreibung nirgends vorkommen darf. Lang genug fuer den
# secret_key-Startwaechter, sonst ohne Bedeutung.
SENTINELS: Final[dict[str, str]] = {
    "secret_key": "sentinel-secret-key-32-characters-long-for-test",
    "opencloud_base_url": "https://sentinel-opencloud.invalid",
    "opencloud_username": "sentinel-opencloud-user",
    "opencloud_app_token": "sentinel-opencloud-app-token",
    "anthropic_api_key": "sentinel-anthropic-api-key",
    "database_url": "postgresql+psycopg://sentinel:sentinel@sentinel-host:5432/sentinel",
    "redis_url": "redis://sentinel-redis.invalid:6379/9",
    "auth_seed_user1_password": "sentinel-user1-password",
    "auth_seed_user2_password": "sentinel-user2-password",
}


def test_no_setting_value_reaches_the_published_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for feld, wert in SENTINELS.items():
        monkeypatch.setattr(settings, feld, wert)

    beschreibung = json.dumps(create_app().openapi(), ensure_ascii=False)

    gefunden = sorted(wert for wert in SENTINELS.values() if wert in beschreibung)
    assert not gefunden, f"Geheimnis-/Infrastrukturwerte in der Beschreibung: {gefunden}"


def test_the_description_names_no_absolute_server_address(monkeypatch: pytest.MonkeyPatch) -> None:
    for feld, wert in SENTINELS.items():
        monkeypatch.setattr(settings, feld, wert)

    spec = create_app().openapi()

    server = spec.get("servers")
    assert not server or server == [{"url": "/"}], server


def test_the_checked_in_artifact_names_no_absolute_server_address() -> None:
    spec = json.loads(ARTEFAKT.read_text(encoding="utf-8"))

    server = spec.get("servers")
    assert not server or server == [{"url": "/"}], server


def test_the_checked_in_artifact_has_no_blanket_sentinel_values() -> None:
    """Gegenprobe auf die eingecheckte Datei: kein Sentinel und kein offensichtlicher Platzhalter
    eines echten Secrets steht darin."""
    roh = ARTEFAKT.read_text(encoding="utf-8")

    for wert in SENTINELS.values():
        assert wert not in roh
    assert "opencloud_app_token" not in roh
