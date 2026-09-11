from __future__ import annotations

from photosort.cloud_vision import (
    DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER,
    CloudRequestThrottle,
)
from photosort.config import Settings, settings

# Die PROZESSWEITEN Schrittmacher-Instanzen, genau eine je Anbieter. Dieselbe Bauform wie
# rate_limit.py::limiter (das trotz des
# aehnlichen Namens etwas voellig anderes tut: es begrenzt EINGEHENDE Anfragen an
# POST /auth/login).
#
# Warum ein EIGENES Modul und nicht cloud_vision.py - Pflicht, keine Geschmacksfrage: die Registry
# liest `settings`, und cloud_vision.py darf `photosort.config` niemals importieren (config.py
# importiert cloud_vision.py fuer den LANDMARK_MODEL-Validator, die Gegenrichtung waere ein
# Importzyklus). Der MECHANISMUS (CloudRequestThrottle) bleibt deshalb
# dort, nur die INSTANZEN leben hier.
#
# Die Rate gilt fuer BEIDE Cloud-Teilschritte gemeinsam und fuer alle gleichzeitig laufenden Jobs:
# ein Lauf verlangsamt dadurch den anderen. Genau so gewollt - der Anbieter sieht ohnehin nur
# eine einzige Quelle.
#
# DIESES MODUL DARF BEIM IMPORT NICHT WERFEN (Sicherheits-Muss-Kriterium): die Instanzen
# entstehen zur Modul-Importzeit aus `60 / rate`, ein ZeroDivisionError hier waere ein
# gleichzeitiger Startfehler von Backend UND Worker. Abgesichert ist das in
# Settings.resolved_cloud_vision_requests_per_minute (gibt nie 0 zurueck), nicht durch eine
# Sonderbehandlung der Division; es bricht in
# tests/test_cloud_vision_throttle.py::TestBuildThrottles::
# test_no_interval_is_zero_and_nothing_divides_by_zero.


def build_throttles(app_settings: Settings) -> dict[str, CloudRequestThrottle]:
    """Baut je bekanntem Anbieter genau einen Schrittmacher aus einem Settings-Objekt.

    REINE Funktion ueber einem uebergebenen `Settings` statt eines Zugriffs auf das globale
    `settings`: sonst waere die Registry nur ueber `importlib.reload` pruefbar. Das Modul ruft sie
    beim Import genau einmal auf."""
    return {
        provider: CloudRequestThrottle(
            min_interval_seconds=60.0
            / app_settings.resolved_cloud_vision_requests_per_minute(provider)
        )
        for provider in DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER
    }


_THROTTLES: dict[str, CloudRequestThrottle] = build_throttles(settings)


def throttle_for_provider(provider: str) -> CloudRequestThrottle:
    """Der eine Schrittmacher dieses Anbieters - dieselbe Instanz bei jedem Abruf.

    Direkter Dict-Zugriff: ein unbekannter Anbieter ist ein `KeyError` und durch das `Literal` auf
    `Settings.landmark_provider` unerreichbar. Genau deshalb soll er laut scheitern, statt sich
    eine Voreinstellung auszudenken - ein still ungedrosselter Anbieter waere der Zustand, den
    diese Story abschafft."""
    return _THROTTLES[provider]
