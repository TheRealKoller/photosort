# 0009 - Lokaler OpenCloud-Demo-Stack statt selbstgebautem Mock

**Status:** Accepted
**Datum:** 2026-08-02

## Kontext

Spec 0009 ("Lokal ausprobieren ohne echten OpenCloud-Server") soll `docker compose up` ohne echte OpenCloud-Zugangsdaten ermöglichen. `OpenCloudClient` (`backend/src/photosort/opencloud/client.py`) spricht zwei Schnittstellen: Graph-API (`GET /graph/v1.0/me/drives`) und WebDAV (`PROPFIND` Depth 1, `GET` mit/ohne `Range`), Auth via HTTP Basic. `specs/architecture/0002-testkonzept.md` vermerkt als bekannte Lücke, dass es kein automatisiertes Integrationstest-Setup gegen eine echte OpenCloud-Instanz gibt und Vertragskonformität (`DavEntry`-Parsing, WebDAV-Eigenheiten) nur durch manuellen Smoke-Test vor Merge abgesichert ist.

Zwei Optionen wurden geprüft:

1. Ein selbstgebauter Mock-/Stub-Server (z.B. ein schlanker FastAPI-/WsgiDAV-Dienst), der Graph-API und WebDAV-Subset nachbildet.
2. Der offizielle OpenCloud-Single-Container (`opencloudeu/opencloud-rolling`, Docker Hub), der mit `IDM_CREATE_DEMO_USERS=true` fertige Demo-Nutzer (Passwort jeweils `demo`) anlegt und mit `PROXY_ENABLE_BASIC_AUTH=true` denselben HTTP-Basic-Auth-Mechanismus unterstützt, den `OpenCloudClient` bereits nutzt.

## Entscheidung

Wir verwenden den echten OpenCloud-Single-Container (Option 2) als optionalen, zusätzlichen Compose-Service — kein selbstgebauter Mock.

## Begründung

- Eliminiert Contract-Drift komplett: es ist derselbe Server (Graph-API + WebDAV-Verhalten), gegen den auch in Produktion gesprochen wird, statt einer zweiten, von uns gepflegten Nachbildung, die per Definition wieder auseinanderlaufen kann.
- Wird von OpenCloud selbst gebaut, getestet und aktuell gehalten — kein Wartungsaufwand für Protokoll-Feinheiten (WebDAV-XML-Namespaces, Graph-API-Response-Form) auf unserer Seite.
- Deutlich weniger Code als ein eigener Mock-Server, der Auth, PROPFIND-XML-Antworten und Range-Downloads plausibel genug nachbilden müsste, um für einen Demo-Zweck brauchbar zu sein.
- Einziger relevanter Nachteil ist ein schwererer Container (voller Server statt schlankem Stub) und dass Testfotos separat eingespielt werden müssen, da `OpenCloudClient` selbst keinen Upload kennt (kein Export-Feature, Spec 0004 noch nicht umgesetzt) — beides akzeptabel für einen rein lokalen, optionalen Ausprobier-Zweck.

## Konsequenzen

- Neue externe Docker-Image-Abhängigkeit: `opencloudeu/opencloud-rolling` (nur in einer optionalen Compose-Overlay-Datei, nicht im Standard-`docker-compose.yml`).
- Ein kleines, eigenständiges Seed-Skript (direkter WebDAV-`PUT` gegen den Demo-Container) wird benötigt, um Beispielfotos in den Demo-Space zu laden — bewusst unabhängig vom Produktivcode (`OpenCloudClient` bekommt dadurch keine Upload-Fähigkeit, das bleibt Aufgabe von Spec 0004).
- Der Demo-Container nutzt `:rolling`-Tag (kein gepinntes Release) — akzeptiert für einen lokalen Ausprobier-Stack; falls das künftig Probleme macht (Breaking Changes im Image), kann auf einen gepinnten Tag umgestellt werden, ohne dass das den Rest dieser Entscheidung berührt.
- Adressiert die in `architecture/0002-testkonzept.md` vermerkte Contract-Drift-Lücke nicht automatisiert (kein CI-Integrationstest) — reduziert aber das Risiko in der Praxis, da Daniel vor größeren Änderungen jetzt bequem manuell gegen einen echten Server statt nur gegen Fakes prüfen kann. Eine automatisierte CI-Anbindung wäre eine separate, spätere Spec.
