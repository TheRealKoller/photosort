"""Die HTTP-Grenze zum Eye-Sidecar (Spec 0609, ADR 0138).

Ein Modul fuer beide Aufrufer: der Klassifizierungslauf (`analyse`) und der Ausloese-Endpunkt
(`health`, bevor er einen Job einreiht). Adresse nur aus den Settings, keine Weiterleitungen,
feste Zeitgrenze, Antwortdeckel - die Regeln stehen an EINER Stelle.

Das Modul ist reine I/O ohne Datenbank und ohne Jobwissen: es kennt weder `Photo` noch
`CriterionScoringRun`. Damit bleibt die Layering-Regel des Projekts intakt, dass die API-Schicht
`worker.py` nicht importiert.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from photosort.config import settings

# 30 s je Foto - feste Zeitgrenze, kein Retry (S3). Ein haengender Aufruf ist ein Fehlschlag der
# Phase, kein Grund, es gleich noch einmal zu versuchen: die Gewichte liegen lokal, ein Timeout
# heisst "Dienst antwortet nicht", und jeder Wiederholungsversuch verlaengerte nur den Lauf.
EYE_REQUEST_TIMEOUT_SECONDS = 30.0
# 1 MiB Antwortdeckel, geprueft WAEHREND des Lesens: die Analyse eines Fotos ist wenige Kilobyte
# gross, ein groesserer Koerper ist ein Defekt oder ein falscher Dienst hinter der Adresse.
EYE_MAX_RESPONSE_BYTES = 1024 * 1024
# Der Dienst nimmt ausschliesslich JPEG-Bytes der `display`-Variante, keinen Multipart-Koerper,
# keinen Pfad und keinen Feldparameter (S3).
EYE_CONTENT_TYPE = "image/jpeg"


class EyeClientLike(Protocol):
    """Die Teilmenge des Sidecars, die die Laufphase braucht - Tests setzen hier einen Fake ein."""

    async def health(self) -> bool: ...

    async def analyze(self, image_bytes: bytes) -> Mapping[str, Any]: ...

    async def aclose(self) -> None: ...


class EyeServiceUnavailableError(RuntimeError):
    """Der Dienst antwortet nicht, antwortet falsch oder ist nicht gesund.

    Bewusst ein eigener Fehlertyp: die Phase endet damit sofort, der Lauf auf `FAILED` - ein
    einzelnes unlesbares BILD wird dagegen uebersprungen, das ist nicht dieser Fehler.

    Die Meldung ist ein FESTER deutscher Satz ohne Host, Port, Version oder Stacktrace (S5) und
    wird so - unveraendert - als `error_message` persistiert."""


class EyeHttpClient:
    """`follow_redirects=False` verhindert, dass ein 302 den Verkehr auf einen anderen Host
    umlenkt; die Adresse kommt ausschliesslich aus den Settings (per Validator auf http/https
    eingegrenzt) und nie aus einer Anfrage. `transport` ist fuer Tests injizierbar
    (`httpx.MockTransport`)."""

    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=EYE_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )

    async def health(self) -> bool:
        """Nur der Status zaehlt; der Koerper wird nicht gelesen."""
        try:
            async with self._client.stream("GET", "/health") as response:
                return bool(response.status_code == 200)
        except httpx.HTTPError:
            return False

    async def analyze(self, image_bytes: bytes) -> Mapping[str, Any]:
        try:
            async with self._client.stream(
                "POST",
                "/analyze",
                content=image_bytes,
                headers={"content-type": EYE_CONTENT_TYPE},
            ) as response:
                if response.status_code != 200:
                    raise EyeServiceUnavailableError("Die Eye-Auswertung hat abgelehnt.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > EYE_MAX_RESPONSE_BYTES:
                        raise EyeServiceUnavailableError(
                            "Die Eye-Auswertung hat zu viel geliefert."
                        )
        except httpx.HTTPError as exc:
            raise EyeServiceUnavailableError("Die Eye-Auswertung ist nicht erreichbar.") from exc
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise EyeServiceUnavailableError("Die Eye-Auswertung war nicht lesbar.") from exc
        if not isinstance(payload, dict):
            raise EyeServiceUnavailableError("Die Eye-Auswertung war nicht lesbar.")
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()


def build_eye_client() -> EyeClientLike:
    """Der Client des Sidecars - Adresse allein aus den Settings, kein Request-Wert."""
    return EyeHttpClient(settings.eye_service_url)


async def eye_service_is_healthy() -> bool:
    """Ein einzelner `/health`-Blick, den der Ausloese-Endpunkt VOR dem Einreihen wirft.

    Der Client wird hier gebaut und wieder geschlossen: die Pruefung ist eine Anfrage, kein
    Zustand, und ein offener Client ueber die Anfrage hinaus waere ein Leck je Klick. Ein Fehler
    ist `False` - der Endpunkt antwortet dann `503`, statt einen Job einzureihen, der garantiert
    scheitert."""
    client = build_eye_client()
    try:
        return await client.health()
    finally:
        await client.aclose()
