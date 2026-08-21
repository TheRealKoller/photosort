# 0047 - Sehenswürdigkeit-Erkennung (Landmark) via Cloud-Vision-API

**Status:** Implemented
**Erstellt:** 2026-08-19
**PR:** [#181](https://github.com/TheRealKoller/photosort/pull/181)
**Bezug:** [`inbox/0017-sehenswuerdigkeit-erkennung-cloud.md`](../inbox/0017-sehenswuerdigkeit-erkennung-cloud.md) (Ursprung, 2026-08-13 zurückgestellt, jetzt reaktiviert; nach Anlage dieser Spec gelöscht), ADR [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md), [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md) (ursprünglicher Cloud-Stopp, hier gezielt für dieses eine Kriterium revidiert), [`features/0035-klassifizierung-qualitaet-inhalt-recherche.md`](./0035-klassifizierung-qualitaet-inhalt-recherche.md) (Cloud-Provider-Recherchegrundlage), [`features/0037-gateführte-bewertungs-pipeline-mit-backfill.md`](./0037-gateführte-bewertungs-pipeline-mit-backfill.md) (CRITERIA_REGISTRY/`CriterionSource.CLOUD`), [`features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md`](./0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md) (dort Landmark explizit als Out-of-Scope mit Verweis hierher benannt), Idea-Sharpening-Gespräch mit Daniel am 2026-08-19.

## Ziel

Sehenswürdigkeit-Erkennung (Landmark) als neues Kriterium in der bestehenden Kriterien-Bewertungs-Pipeline (`PhotoCriterionScore`/`CRITERIA_REGISTRY`, Spec 0037): erkennt bekannte und weniger bekannte Wahrzeichen auf Reisefotos automatisch, mithilfe des Weltwissens eines Vision-LLM — lokal ist das laut bereits vorliegender Recherche (Spec 0035, ADR 0015) nicht wirtschaftlich lösbar. Diese Idee wurde am 2026-08-13 bewusst zurückgestellt (Cloud-Anbindung, Einwilligung, Kosten, DPA-Frage für Privatkonten nicht gerechtfertigt) und jetzt von Daniel im Sharpening-Gespräch ausdrücklich reaktiviert.

Diese Spec ist die **erste tatsächlich produktive Cloud-Abhängigkeit** im gesamten Kriterien-Scoring-Pfad — alle bisherigen sieben Kriterien laufen rein lokal. Familienfotos verlassen für dieses eine, projektweit deaktivierbare Kriterium erstmals den Homeserver.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass Fotos mit erkennbaren Sehenswürdigkeiten/Wahrzeichen automatisch als solche markiert werden, damit ich bei größeren Reiseprojekten nicht jedes Foto manuell durchsehen muss, um Sehenswürdigkeits-Aufnahmen zu finden — mit der Möglichkeit, diese Cloud-Verarbeitung pro Projekt bewusst ein-/auszuschalten.

## Akzeptanzkriterien

**Kriterien-Registrierung & Datenmodell:**
- [ ] Neues Kriterium `landmark` in `CRITERIA_REGISTRY` (`backend/src/photosort/criteria.py`): `display_name="Sehenswürdigkeit"`, `source=CriterionSource.CLOUD`, `category_eligible=True`, `category_presence_threshold=0.5` (neue Konstante `_LANDMARK_CATEGORY_PRESENCE_THRESHOLD`).
- [ ] `compute_landmark_score(detection: LandmarkDetection) -> float` ist rein, synchron, netzwerkfrei, klemmt auf `[0, 1]` — unit-testbar ohne Netzwerk, im Stil der bestehenden `compute_*`-Funktionen.
- [ ] Neue additive `Project`-Felder: `cloud_landmark_detection_enabled: bool` (Default `False`, `NOT NULL`), `cloud_landmark_consent_at: datetime | None`.
- [ ] Neue Tabelle `photo_landmark_detections`: `photo_id` (FK, Primary Key), `name: str`, `confidence: float`, `computed_at` — nur angelegt, wenn tatsächlich ein Name identifiziert wurde (kein Platzhalter). Landmark-Name wird **mitgespeichert** (mit Daniel bestätigt), auch ohne UI-Anzeige in v1.

**Einwilligung:**
- [ ] Neuer Endpunkt `PUT /projects/{id}/cloud-landmark-consent` (Body `{"enabled": bool}`) setzt `cloud_landmark_detection_enabled` und synchron `cloud_landmark_consent_at` (Zeitstempel bei Aktivierung, `NULL` bei Deaktivierung). Endpunkt hängt am bestehenden router-weiten Auth-Torwächter.
- [ ] Bei `cloud_landmark_detection_enabled=False` (Default) führt `run_criterion_scoring` **keinen** Netzwerkaufruf gegen die Anthropic-API aus — `build_landmark_client()` wird nicht aufgerufen, kein API-Key wird ausgelesen, kein Byte verlässt den Server (Test: Aufrufnachweis, nicht nur "keine DB-Zeile").
- [ ] `project.cloud_landmark_detection_enabled` wird beim Laufstart einmalig gelesen (kein Live-Reread während eines laufenden Laufs) — dokumentierte Vereinfachung, kein Race im technischen Sinn.

**Vorfilterung & Cloud-Aufruf:**
- [ ] Ein Foto wird nur an die Cloud gesendet, wenn im selben Lauf `content_landscape` **oder** `gebaeude` mindestens die jeweils registrierte `category_presence_threshold` erreicht (`>=`, inklusiv) — Wiederverwendung der bereits vorhandenen Registry-Schwellwerte, kein neuer doppelt gepflegter Grenzwert.
- [ ] Cloud-Aufruf nutzt ausschließlich die bestehende `display`-Cache-Variante (2048×2048), nie das Originalbild. Kein GPS-/EXIF-Zugriff.
- [ ] Ein Foto mit bereits vorhandener `PhotoCriterionScore(criterion_key="landmark")`-Zeile wird bei einem erneuten `score-criteria`-Lauf **nicht** erneut an die Cloud geschickt, unabhängig davon, ob es die Vorfilterung erneut passieren würde — bewusste, dokumentierte Ausnahme vom sonst projektweiten "jeder Lauf scort neu"-Prinzip (nur für `landmark`, alle sieben lokalen Kriterien bleiben unverändert).
- [ ] Nebenläufigkeit begrenzt auf `settings.landmark_api_concurrency` (`Field(default=2, ge=1)`, env `LANDMARK_API_CONCURRENCY`) — Block+`asyncio.gather(..., return_exceptions=True)`-Muster (ADR 0020), inkl. expliziter `CancelledError`-Prüfung/Weiterwurf (bekannter Fallstrick aus ADR 0020, hier erneut zu vermeiden).
- [ ] Timeout 60s pro Anfrage (Modul-Konstante, kein Settings-Feld).
- [ ] Ein einzelner fehlgeschlagener Cloud-Aufruf (Timeout, 4xx, 5xx) lässt den Lauf mit `status=success` abschließen; für das betroffene Foto entsteht keine `landmark`-Zeile; alle anderen Kriterien dieses Fotos bleiben unberührt. Kein Retry/Backoff — das Foto bleibt beim nächsten Lauf automatisch erneut Kandidat (kein `landmark`-Eintrag vorhanden), das ersetzt funktional einen dedizierten Retry-Mechanismus.

**Anbindung & Secrets:**
- [ ] Neues Modul `backend/src/photosort/landmark.py`: `LandmarkApiError(Exception)`, `LandmarkDetection` (`@dataclass(frozen=True)`: `name: str | None`, `confidence: float`), `LandmarkClientLike(Protocol)` mit `async def detect(...)`, `AnthropicLandmarkClient` (direkter `httpx`-REST-Aufruf, **kein** `anthropic`-SDK), `build_landmark_client()`-Factory (liest `settings.anthropic_api_key`) — `build_landmark_client()` wird nie in einem automatisierten Test aufgerufen (analog `build_face_detector`).
- [ ] `Settings.anthropic_api_key: str = ""` neu in `config.py`; `.env.example`-Kommentar für den dort bereits vorhandenen, aber nie verdrahteten `ANTHROPIC_API_KEY`-Platzhalter korrigiert (kein "Phase B"-Bezug mehr).
- [ ] `LandmarkApiError`/Fehlermeldungen betten niemals den API-Key oder Base64-Bilddaten ein — nur Statuscode/Reason-Phrase (analog `OpenCloudError`/`_raise_for_status`).

**Frontend:**
- [ ] `frontend/src/utils/categoryLabels.ts`: `CATEGORY_DISPLAY_NAME_OVERRIDES` bekommt `landmark: 'Sehenswürdigkeit'`.
- [ ] Neue Settings-Route `/projects/:projectId/settings` (`ProjectSettingsPage.tsx`) mit Toggle-Switch für die Cloud-Landmark-Einwilligung + Info-Popover (Muster: `CriterionDetailsPopover.tsx`), das erklärt, dass Fotos zur Analyse an die Anthropic-Cloud-API versendet werden.
- [ ] Sobald `landmark` in einem Lauf projektweit die 15%-Häufigkeitsschwelle (ADR 0023) erreicht, erscheint "Sehenswürdigkeit" automatisch als Kategorie in `/projects/:id/curate` — kein weiterer Code nötig.
- [ ] Kein zusätzlicher UI-Zustand während eines laufenden Cloud-Scoring-Laufs — bestehender "X von Y Fotos verarbeitet"-Fortschrittsindikator reicht.

## Datenmodell-Bezug

Additive Migration: zwei neue `Project`-Spalten (`cloud_landmark_detection_enabled`, `cloud_landmark_consent_at`), neue Tabelle `photo_landmark_detections` (1:1 zu `Photo`, analog `PhotoScore`). `PhotoCriterionScore` bekommt erstmals produktiv geschriebene `criterion_key="landmark"`-Zeilen mit `source=CriterionSource.CLOUD` (Enum-Wert existierte bereits, war bisher ungenutzt). Siehe `docs/architecture.md` (wird von `architect` bei Umsetzung ergänzt).

## Architektur / Umsetzung

Siehe [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md) (Accepted) für die vollständige Begründung. Zusammenfassung:

- **Provider: Anthropic Claude Vision, Haiku-Klasse** (nicht Mistral) — Kostenkontroll-Werkzeuge (Batch-API 50% Rabatt; Prompt-Caching, hier nur begrenzt wirksam, siehe ADR-Korrektur), Kontinuität zur bestehenden Recherche. DPA-Frage für Privatkonten war der Kernvorbehalt gegen den Providervergleich — nach Nachrecherche (`research-engineer`, 2026-08-19) geklärt: DPA/SCCs gelten für jede API-Key-Nutzung automatisch, unabhängig vom Kontotyp (Abgrenzung verläuft nach Produktkategorie API vs. Consumer, nicht nach Kontotyp). Verbleibendes, bewusst akzeptiertes Restrisiko: US-Rechenzentrum, Standard-Retention 7 Tage, keine Zero Data Retention ohne manuellen Sales-Kontakt.
- **Neues, isoliertes Modul `landmark.py`** statt Erweiterung von `criteria.py` selbst — hält den bestehenden synchronen `criteria.py`-Vertrag für alle sieben lokalen Kriterien unangetastet (analog zur Isolation von `aesthetics.py` für die einzige schwere neue Abhängigkeit, hier für die einzige neue externe Vertrauensgrenze).
- **Kostenoptimierung durch Vorfilterung + Skip bereits gescorter Fotos** statt Batch-API/Prompt-Caching in v1 (bewusste Scope-Entscheidung, spätere Option, kein Strukturbruch da `LandmarkClientLike` austauschbar bleibt).
- **Kein neues Retry-/Backoff-Muster** — das Projekt hat aktuell an keiner Stelle eine solche Infrastruktur; das Skip-bereits-gescort-Muster übernimmt die Funktion strukturell.
- Wiederverwendet drei bereits etablierte Muster: `build_*()`-Factory+Protocol-Testbarkeit (ADR 0015/0022), Block+`gather`-Nebenläufigkeit (ADR 0020), generische `category_eligible`-Registry (ADR 0023).

**Betroffene/neue Dateien:** `backend/src/photosort/landmark.py` (neu), `backend/src/photosort/criteria.py`, `backend/src/photosort/worker.py`, `backend/src/photosort/models.py` (+ Alembic-Migration), `backend/src/photosort/config.py`, `backend/src/photosort/api/projects.py` (neuer Endpunkt), `.env.example`, `frontend/src/utils/categoryLabels.ts`, `frontend/src/pages/ProjectSettingsPage.tsx` (neu) + Routing, `docs/architecture.md`, `docs/setup.md`/`README.md` (neue Umgebungsvariable).

## UI/UX

Sichtbare Oberfläche vorhanden, wenn auch klein (`ux-ui-designer`-Konsultation, 2026-08-19) — **ausdrücklich nicht "nicht relevant"**, da zwei echte Berührungspunkte bestehen:

1. **Neue Settings-Route `/projects/:projectId/settings`** (erste Konfigurationsseite dieser Art im Projekt — bisher keine dedizierte Projekteinstellungs-UI): Toggle-Switch "Cloud-Sehenswürdigkeit-Erkennung" + Info-Popover-Muster (analog `CriterionDetailsPopover.tsx`) mit neutralem, kurzem Erklärtext ("Fotos, die als Landschaft oder Gebäude erkannt wurden, werden zur Analyse an die Anthropic-Cloud-API versendet").
2. **`categoryLabels.ts`-Mapping-Eintrag** `landmark: 'Sehenswürdigkeit'` — sobald das Kriterium produktiv scort und die 15%-Häufigkeitsschwelle erreicht, erscheint "Sehenswürdigkeit" automatisch als eigene Kategorie in der bestehenden Kuratierungsansicht, ohne weiteren Code (ADR-0023-Mechanismus).

Kein zusätzlicher UI-Zustand während eines laufenden Cloud-Scoring-Laufs nötig — der bestehende, generische Fortschrittsindikator ("X von Y Fotos verarbeitet") deckt das ab; dass einzelne Fotos dabei an die Cloud gehen, muss nicht separat signalisiert werden (konsistent mit Spec 0038, wo andere Kriterien diese Ebene ebenfalls nicht extra anzeigen). Design-System (`specs/architecture/0004-design-system.md`) und der begleitende Skill brauchen keine Ergänzung — beide verwendeten Muster (Info-Popover, Toggle) sind bereits dokumentiert.

## Security

Sicherheitsrelevant, ja (`security-engineer`-Konsultation, 2026-08-19) — erste tatsächlich produktiv geschriebene `CriterionSource.CLOUD`-Anbindung, erster Pfad, auf dem echte Familienfoto-Bilddaten routinemäßig den Homeserver verlassen. Vollständige Herleitung siehe `specs/architecture/0003-securitykonzept.md`, Abschnitt "Cloud-Vision-API (`landmark.py`)".

**Datenexposition strukturell begrenzt:** nur Fotos mit bereits lokal erkanntem `content_landscape`/`gebaeude`-Score werden an die Cloud geschickt; ausschließlich die `display`-Cache-Variante (2048×2048), nie das Original; kein GPS-/EXIF-Zugriff; bereits gescorte Fotos werden bei Re-Läufen nicht erneut gesendet.

**Einwilligung:** projektweiter Opt-in-Schalter, Default `False`, muss am bestehenden Auth-Torwächter hängen (Muss-Kriterium). `run_criterion_scoring` darf `build_landmark_client` nur bei aktiviertem Schalter aufrufen (Muss-Kriterium, testseitig abzusichern). Reichweite bewusst projektweit statt personenbezogen — konsistent mit Spec 0037/dem "kein Innentäter-Modell"-Grundsatz. **Drittpersonen-Frage geklärt** (Rückfrage an Daniel, 2026-08-19): der einfache projektweite Schalter reicht — Daniel trifft als Verantwortlicher für die eigenen Familienfotos die Einwilligungsentscheidung für den gesamten Fotobestand, kein zusätzlicher technischer Mechanismus zum Ausschluss von Fotos mit erkennbaren Dritten/Kindern.

**Secrets:** `ANTHROPIC_API_KEY` über `Settings.anthropic_api_key`, exakt das bestehende `opencloud_app_token`-Muster. Muss-Kriterium: `LandmarkApiError` darf nie den Key oder Base64-Bilddaten in Meldung/Log einbetten.

**Rechtsraum/DPA:** Anthropic Inc. (USA), kein direktes EU-Hosting über die reine API. DPA/SCCs gelten laut Nachrecherche (`research-engineer`, 2026-08-19) automatisch für jede API-Key-Nutzung, unabhängig vom Kontotyp — die in Spec 0035 offen gelassene Frage ("gilt das auch für Privatkonten") ist damit geklärt, kein Blocker mehr. Verbleibendes, bewusst akzeptiertes Restrisiko: Standard-Retention 7 Tage, keine Zero Data Retention ohne manuellen Sales-Kontakt (für v1 nicht benötigt, spätere Option).

**SSRF:** kein Risiko, fester, im Code hinterlegter Ziel-Host (Anthropic Messages API).

**Verwandtes, bereits bestehendes Restrisiko verschärft sich geringfügig:** ein gestohlenes JWT (bestehendes `localStorage`-Token-Risiko) kann ab diesem Feature zusätzlich wiederholte, tatsächlich kostenpflichtige `score-criteria`-Läufe auslösen statt nur kostenloser lokaler Verarbeitung — kein neuer Auth-Bypass, für dieses Zwei-Personen-Projekt als geringes, akzeptiertes Restrisiko eingestuft, kein zusätzlicher Härtungsaufwand für v1.

`specs/architecture/0003-securitykonzept.md` wurde im Rahmen dieser Konsultation bereits um einen Vorausschau-Abschnitt ergänzt (Angriffsflächen, Vertrauensgrenzen, akzeptierte Restrisiken, bekannte Lücken).

## Teststrategie

Vollständig in `specs/architecture/0002-testkonzept.md` als neue Sektion **"Cloud-LLM-Vision-Client-Test-Double + Vorfilterung + Skip-bereits-gescorter-Fotos (`landmark.py`)"** festgehalten (`test-engineer`-Konsultation, 2026-08-19). Kernpunkte:

- `compute_landmark_score`: reine Unit-Tests, netzwerkfrei, im Stil der bestehenden `compute_*`-Funktionen.
- `landmark.py` isoliert getestet: `LandmarkClientLike`-Fake für Worker-Integrationstests; `httpx.MockTransport` für das HTTP-Mapping von `AnthropicLandmarkClient` (dasselbe Muster wie `test_opencloud_client.py`, nicht `unittest.mock.patch`). `build_landmark_client()` wird nie in einem automatisierten Test aufgerufen.
- `run_criterion_scoring`-Integrationstests: Vorfilter-Grenzfall exakt auf der Schwelle, Skip bereits gescorter Fotos (mit Regressionstest, dass die sieben lokalen Kriterien trotzdem neu berechnet werden), fehlgeschlagenes Foto wird beim nächsten Lauf automatisch wieder Kandidat, leerer Kandidatenpool nach Vorfilterung, Consent-AUS→Builder wird nie aufgerufen (Aufrufnachweis), begrenzte Nebenläufigkeit per `in_flight`-Zähler (kein Wall-Clock-Timing) plus `CancelledError`-durch-`gather`-Regressionstest (ADR-0020-Muster, zweite Anwendung).
- Migration: neue Spalten + Tabelle per `inspect()` verifiziert, plus Cascade-Test `test_deleting_photo_cascades_to_landmark_detection` (vorsorglich ergänzt — genau diese Art Lücke trat bei Spec 0044 bereits real auf).

**Relevante Edge Cases:** Consent AUS während laufendem Lauf (dokumentierte Vereinfachung: einmaliges Lesen beim Laufstart, kein Race im technischen Sinn, kein eigener Testfall nötig); leerer Kandidatenpool nach Vorfilterung; Foto ohne identifizierten Namen (kein `photo_landmark_detections`-Eintrag, aber `PhotoCriterionScore`-Zeile mit niedrigem/Null-Score).

**Nicht automatisiert testbar (bekannte Lücke, dokumentiert):** Erkennungsqualität/Kalibrierung selbst (echtes Modellverhalten gegen reale Fotos, kein Ground-Truth-Korpus im Repo) — automatisiert geprüft wird nur die Randfall-*Logik* (Schwellenwert-Vergleich, Klemmen), nicht die *Kalibrierung*, analog zum bestehenden Umgang mit `SHARPNESS_REJECT_THRESHOLD`. Ersatzverfahren: manueller Stichproben-Review durch Daniel nach den ersten produktiven Läufen (20-30 als `landmark` markierte Fotos plausibel/falsch durchsehen). Kein Merge-Blocker.

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, neue Sektion (siehe oben) plus neuer Eintrag unter "Bekannte Lücken" zum Überidentifikations-/Kalibrierungsrisiko.

## Entscheidungen (2026-08-19, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Reaktivierung:** Inbox 0017 wurde am 2026-08-13 bewusst zurückgestellt (Cloud-Anbindung, Einwilligung, Kosten, DPA nicht gerechtfertigt). Auf direkte Rückfrage im Sharpening-Gespräch hat Daniel bestätigt: die Zurückstellung gilt nicht mehr, das Feature soll jetzt umgesetzt werden.
- **DPA-Restrisiko (Rückfrage im Sharpening-Gespräch):** zunächst als bewusst akzeptiertes Restrisiko eingestuft (statt vorab verbindlich zu klären) — im Verlauf der Schärfung durch eine tatsächliche Nachrecherche (`research-engineer`) dann von "Restrisiko" zu "geklärt" herabgestuft (siehe Security-Abschnitt), die ursprüngliche Risikoakzeptanz-Entscheidung wurde dadurch nicht mehr benötigt, aber im Vorfeld bewusst getroffen.
- **Devil's-Advocate-Ergebnis:** manuelle Kategorisierung (Spec 0002) wurde als einfachere Alternative geprüft — Daniel hat bestätigt, dass automatische Erkennung trotzdem gebaut werden soll (Nutzen bei größeren Reiseprojekten).
- **Cloud-Provider (Rückfrage im Sharpening-Gespräch, dann technische Entscheidung):** Anthropic vs. Mistral war zunächst offen ("erst recherchieren lassen") — `architect` hat sich für Anthropic entschieden (siehe ADR 0025), da das vorgesehene Delegations-Werkzeug an `research-engineer` in seiner eigenen Subagenten-Session nicht verfügbar war (dieselbe strukturelle Einschränkung wie bei ADR 0024/`developer`-Subagenten — Subagenten können keine weitere Verschachtelungsebene an Subagenten starten). Vom Orchestrator nachgeholt: `research-engineer` hat die Provider-Entscheidung nachträglich mit aktuellen Fakten gegengeprüft, keine Korrektur der Kernentscheidung nötig, nur zwei zitierte Zahlen in ADR 0025 präzisiert (Batch-Rabatt/Prompt-Caching, siehe ADR-Änderungshistorie) — mithilfe des `claude-api`-Skills gegen die aktuelle Claude-API-Referenz geprüft, statt aus Trainingsdaten übernommen.
- **Einwilligungsmechanismus (Rückfrage im Sharpening-Gespräch):** globaler Schalter pro Projekt, Default AUS — analog zum in der Idee zunächst vermuteten `category_selection_enabled`-Muster, tatsächlich aber als eigenständiges, neues Pro-Projekt-Datenmodell-Feld umgesetzt (kein Vorbild dort, da `category_selection_enabled` ein globales Operator-Flag ist, keine Nutzer-Einwilligung).
- **Landmark-Name persistieren (Rückfrage von `architect` an Daniel, im Sharpening-Gespräch beantwortet):** Ja, der erkannte Name wird jetzt mitgespeichert (neue Tabelle `photo_landmark_detections`), auch ohne UI-Anzeige in v1 — vermeidet einen späteren, erneut kostenpflichtigen Cloud-Durchlauf aller bereits gescorten Fotos, falls der Name doch einmal angezeigt werden soll.
- **Drittpersonen-/Kinder-Einwilligung (Rückfrage von `security-engineer` an Daniel, im Sharpening-Gespräch beantwortet):** der einfache projektweite Schalter reicht — keine zusätzliche technische Einschränkung (z.B. Ausschluss von Fotos mit erkannten Personen) gewünscht.
- **`ux-ui-designer` bewusst konsultiert statt "nicht relevant" gesetzt (Schritt 7):** obwohl der Umfang klein ist, hat `architect` zwei echte UI-Berührungspunkte identifiziert (Einwilligungs-UI, automatische Kategorie-Erscheinung via ADR 0023) — Konsultation lief, keine Rückfrage an Daniel nötig (reine technische Platzierungsentscheidung).
- **Priorität — Mittel (nach Schärfung bestätigt, `requirements-engineer`-Vorschlag aus Schritt 2 übernommen):** strategisch bedeutsam (erste Cloud-Integration im Kriterien-Pfad, direkter Produktwert für Reiseprojekte), aber nicht blockierend für laufende Arbeit — kein akuter, von Daniel im Alltag bemerkter Missstand wie bei den Hoch-Einträgen, sondern eine bewusst nachgeholte, lange bekannte Erweiterung. **Kein Konflikt mit bereits Geplantem:** Mittel ist nach Implementierung von Spec 0045/0046 unbesetzt, verdrängt nichts.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- GPS-/Standort-basierte Landmark-Erkennung — ausschließlich Bildinhalt/LLM-Weltwissen, konsistent mit der ursprünglichen Idee ("GPS explizit Out-of-Scope").
- Weitere Cloud-Kriterien über `landmark` hinaus — alle anderen Kriterien bleiben lokal (Spec 0038-Entscheidung unverändert).
- Batch-API und Prompt-Caching — dokumentierte, spätere Optimierungsoption, kein Strukturbruch bei späterer Einführung.
- Retry-/Backoff-Infrastruktur — das Skip-bereits-gescort-Muster übernimmt diese Funktion strukturell.
- UI-Anzeige des erkannten Landmark-Namens (`photo_landmark_detections.name`) — wird jetzt nur persistiert, Anzeige ist eine eigene, spätere Spec mit eigener `ux-ui-designer`-Konsultation.
- Zero Data Retention / EU-Hosting bei Anthropic — bewusst akzeptiertes Restrisiko für v1, kein manueller Sales-Kontakt vorgesehen.
- Zusätzlicher technischer Mechanismus zum Ausschluss von Fotos mit erkennbaren Dritten/Kindern von der Cloud-Verarbeitung — bewusst nicht gewünscht (Daniels Entscheidung, siehe Security-Abschnitt).
- Per-Foto-Einwilligung — bewusst projektweit, nicht granularer.
