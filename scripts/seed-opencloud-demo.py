#!/usr/bin/env python3
"""Seeds a local OpenCloud demo container with a small set of bundled example photos.

Eigenstaendiges Dev-/Demo-Tooling, bewusst ausserhalb von backend/src/photosort/ (siehe
specs/features/0009-local-opencloud-demo-stack.md, specs/decisions/0009-local-opencloud-demo-stack.md,
specs/decisions/0010-demo-seed-script-as-compose-service.md). Laeuft als eigener Compose-Service
(profile "seed") im selben Docker-Netzwerk wie der opencloud-demo-Container - siehe README.md.

Spricht denselben Graph-API-/WebDAV-Codepfad wie das Produktiv-Backend
(backend/src/photosort/opencloud/client.py) direkt per httpx an, nutzt aber bewusst KEINEN Import
von dort (eigenstaendiges Tool, kein Upload-Feature im Produktivcode - siehe ADR 0009).
"""

from __future__ import annotations

from urllib.parse import urlparse

# Hostnamen, die als "eindeutig der lokale Demo-Container" gelten (Security-Muss-Kriterium,
# specs/architecture/0003-securitykonzept.md, Abschnitt "Docker-Compose-Netzwerk"):
# "opencloud-demo" ist der Servicename im gemeinsamen Compose-Netzwerk (siehe ADR 0010, der
# Normalfall bei Ausfuehrung als "seed"-Compose-Service); "localhost"/"127.0.0.1"/"::1" decken den
# seltener genutzten Fall ab, dass jemand das Skript direkt gegen den auf 127.0.0.1 gebundenen
# Host-Port startet (z.B. fuer einen manuellen Test ausserhalb von Docker).
_DEMO_HOSTS = frozenset({"opencloud-demo", "localhost", "127.0.0.1", "::1"})


class SeedError(Exception):
    """Raised for any unrecoverable failure while seeding the demo OpenCloud space."""


def validate_demo_base_url(base_url: str) -> None:
    """Bricht mit einer klaren SeedError ab, falls `base_url` nicht offensichtlich auf den
    lokalen OpenCloud-Demo-Container zeigt - verhindert, dass ein versehentlicher Lauf mit der
    produktiven .env (echte OPENCLOUD_BASE_URL) Fotos in einen echten Familien-Space schreibt
    (Security-Muss-Kriterium, specs/features/0009-local-opencloud-demo-stack.md)."""
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in _DEMO_HOSTS:
        raise SeedError(
            f"'{base_url}' sieht nicht wie der lokale OpenCloud-Demo-Container aus (erwartet: "
            f"http://<{'|'.join(sorted(_DEMO_HOSTS))}>:<port>). Abbruch, um nicht versehentlich "
            "in einen echten OpenCloud-Space zu schreiben. Falls dies tatsaechlich der "
            "Demo-Container ist, den Hostnamen pruefen bzw. _DEMO_HOSTS anpassen."
        )
