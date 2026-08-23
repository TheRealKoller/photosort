# 0054 - Mistral als wählbare Cloud-Provider-Alternative zu Anthropic für das `landmark`-Kriterium

**Status:** Accepted
**Erstellt:** 2026-08-23
**Bezug:** [`inbox/0034-bildklassifizierung-mistral-modelle.md`](../inbox/0034-bildklassifizierung-mistral-modelle.md) (Ursprung, Daniel selbst, interaktive Session), [`features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](./0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) (Implemented, bestehendes `landmark`-Kriterium), [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md) (Anthropic-Wahl, Punkt 1 teilweise superseded), [`decisions/0031-mistral-provider-option-cloud-landmark.md`](../decisions/0031-mistral-provider-option-cloud-landmark.md) (neue ADR dieser Spec), [`features/0035-klassifizierung-qualitaet-inhalt-recherche.md`](./0035-klassifizierung-qualitaet-inhalt-recherche.md) (Datenschutz-Recherchegrundlage Mistral).

## Ziel

Das bestehende, produktive `landmark`-Kriterium (Sehenswürdigkeit-Erkennung, Spec 0047) unterstützt bisher ausschließlich Anthropic als Cloud-Provider. Diese Spec macht Mistral als zweite, konfigurierbare Provider-Option verfügbar — Daniel möchte aus EU-Hosting-/Datenschutz-Erwägungen die Wahlmöglichkeit haben, Familienfoto-Daten statt an einen US-Anbieter an einen EU-nativen Anbieter (Mistral AI SAS, Frankreich) zu schicken. Anthropic bleibt Default und weiterhin die empfohlene Option.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich per Konfiguration wählen können, ob die Cloud-Sehenswürdigkeits-Erkennung über Anthropic oder Mistral läuft, damit ich Familienfotos wahlweise an einen EU-nativen Anbieter statt an einen US-Anbieter schicken kann.

## Akzeptanzkriterien

**Konfiguration & Datenmodell:**
- [ ] `Settings.landmark_provider: Literal["anthropic", "mistral"] = "anthropic"` (env `LANDMARK_PROVIDER`) — ohne gesetzte Env ist der Wert `"anthropic"`; ein nicht in der `Literal`-Menge enthaltener Wert lässt `Settings()` beim Prozessstart mit `pydantic.ValidationError` fehlschlagen, kein stiller Fallback.
- [ ] `Settings.mistral_api_key: str = ""` neu, exakt nach dem bestehenden `anthropic_api_key`-Muster (kein Format-Check, nur über Env-Variable gesetzt, nie eingecheckt).
- [ ] Neue additive Spalte `photo_landmark_detections.provider: str`, atomar im selben Upsert wie `name`/`confidence` gesetzt.
- [ ] Ein Foto, das in einem früheren Lauf bereits mit einem Provider gescort wurde, wird bei einem Folgelauf mit geändertem `LANDMARK_PROVIDER` weiterhin übersprungen (bestehendes Skip-Verhalten aus ADR 0025 bleibt providerunabhängig) — sein `provider`-Feld bleibt beim alten Wert stehen, wird nicht überschrieben.

**`MistralLandmarkClient`:**
- [ ] Implementiert `LandmarkClientLike` (`async def detect(image_bytes, mime_type) -> LandmarkDetection`), direkter `httpx`-REST-Aufruf gegen `https://api.mistral.ai/v1/chat/completions` (neue Konstante `MISTRAL_CHAT_COMPLETIONS_URL`), kein Mistral-SDK.
- [ ] Request trägt `Authorization: Bearer <api_key>` (nicht `x-api-key` wie bei Anthropic), Bild-Content-Block als flacher String `{"type": "image_url", "image_url": "data:<mime>;base64,<...>"}` (kein verschachteltes `{"url": ...}`-Objekt — Verwechslungsgefahr mit dem OpenAI-Format), `response_format: {"type": "json_object"}` im Body (nativer JSON-Mode).
- [ ] Response-Parsing über `response.json()["choices"][0]["message"]["content"]` → `json.loads(...)`.
- [ ] 4xx/5xx → `LandmarkApiError` mit Statuscode/Reason-Phrase, kein Body-Parsing der Fehlermeldung; Netzwerkfehler werden gewrappt; Fehlermeldungen betten nie den API-Key oder Base64-Bilddaten ein (identisch zum Anthropic-Client).
- [ ] Timeout: bestehende `LANDMARK_REQUEST_TIMEOUT_SECONDS` (60s) wiederverwendet, keine eigene Konstante.
- [ ] Modell-ID (Ministral-3-Familie, da Pixtral-Modellnamen deprecated/retired sind) wird vom `developer`-Agenten vor Implementierung gegen `console.mistral.ai`/`GET /v1/models` verifiziert, nicht ungeprüft aus dieser Spec übernommen.

**Gemeinsame Parsing-Hilfsfunktion (Refactoring):**
- [ ] `_parse_detection` wird aufgeteilt in eine providerneutrale Funktion (z.B. `_landmark_detection_from_json(parsed: Any) -> LandmarkDetection`), die beide Clients nach ihrer jeweils providerspezifischen Extraktion des rohen JSON-Texts aufrufen; `[0,1]`-Klemmung und Typvalidierung (`name` kein String → Fehler) leben nur noch dort, nicht mehr dupliziert.
- [ ] Alle bestehenden Anthropic-Fehlerfall-Tests (`test_landmark.py`) bleiben nach dem Refactoring ohne Assertion-Änderung grün.

**Dispatch-Factory:**
- [ ] `build_landmark_client()` wird zur Dispatch-Factory zwischen `AnthropicLandmarkClient` (unverändert) und `MistralLandmarkClient` je nach `settings.landmark_provider` — `worker.py` ändert sich nicht (Factory bleibt injizierbarer `Callable[[], LandmarkClientLike]`-Parameter).
- [ ] `build_landmark_client()` wird weiterhin nie in einem automatisierten Test aufgerufen (bestehende Konvention unverändert).

**Keine Breaking Changes:**
- [ ] Deployments ohne gesetztes `LANDMARK_PROVIDER` verhalten sich exakt wie bisher (Default `anthropic`, identischer Codepfad, identisches Verhalten).
- [ ] Der bestehende Einwilligungsmechanismus (`Project.cloud_landmark_detection_enabled`, `PUT /projects/{id}/cloud-landmark-consent`) bleibt unverändert und providerunabhängig — die Provider-Wahl ist eine globale Deployment-Entscheidung, kein Projekt-Feld, keine Runtime-/UI-Wahl.

**Dokumentation:**
- [ ] `.env.example` bekommt `MISTRAL_API_KEY`/`LANDMARK_PROVIDER`-Einträge.
- [ ] `docs/setup.md` dokumentiert die neue Umgebungsvariable (Anthropic = USA/Default, Mistral = EU-hosted/Alternative).

## Datenmodell-Bezug

Additive Migration: neue Spalte `photo_landmark_detections.provider: str` (siehe [`docs/architecture.md`](../docs/architecture.md)). Keine Änderung an `Project`, `PhotoCriterionScore` oder dem bestehenden Consent-Feldpaar.

## Architektur / Umsetzung

Siehe [`decisions/0031-mistral-provider-option-cloud-landmark.md`](../decisions/0031-mistral-provider-option-cloud-landmark.md) (Accepted, superseded teilweise Punkt 1 von [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md) — Anthropic bleibt Default/Empfehlung) für die vollständige Begründung. Zusammenfassung:

- **Provider-Wahl ist eine globale Deployment-Einstellung, keine Runtime-/Projekt-Einstellung:** `Settings.landmark_provider: Literal["anthropic", "mistral"] = "anthropic"` (env `LANDMARK_PROVIDER`), neues Secret `Settings.mistral_api_key: str = ""` (env `MISTRAL_API_KEY`). Strikt getrennt vom bestehenden, unveränderten Consent-Mechanismus (ADR 0025 Punkt 5) — Einwilligung betrifft "Cloud-Verarbeitung ja/nein", nicht den Anbieter.
- **`build_landmark_client()` (`backend/src/photosort/landmark.py`) wird zur kleinen Dispatch-Factory** zwischen `AnthropicLandmarkClient` (unverändert) und neuem `MistralLandmarkClient`. `worker.py::run_criterion_scoring` ändert sich nicht — `build_landmark_client` ist dort bereits als injizierbarer Default-Parameter verankert.
- **`MistralLandmarkClient`** implementiert `LandmarkClientLike`, exakt analog `AnthropicLandmarkClient` (kein SDK, direkter `httpx`-REST-Aufruf, `httpx.MockTransport`-testbar): Endpunkt `https://api.mistral.ai/v1/chat/completions`, Auth `Authorization: Bearer <key>`, Bild-Content-Block als flacher `image_url`-String, `response_format: {"type": "json_object"}`, Response-Text unter `choices[0].message.content`. Modell: Ministral-3-Familie (Pixtral-Modelle sind deprecated/retired) — exakte Modell-ID ist wie bei `ANTHROPIC_LANDMARK_MODEL` eine TDD-Detailentscheidung des `developer`-Agenten.
- **Gemeinsame, provider-neutrale Hilfsfunktion** für die `name`/`confidence`-Extraktion + `[0,1]`-Klemmung aus dem geparsten JSON (Refactoring von `_parse_detection`), um Duplikation zwischen beiden Clients zu vermeiden.
- **Empfohlene Umsetzungsreihenfolge für `developer`:** (1) gemeinsame Parsing-Hilfsfunktion extrahieren + testen (reine Funktion, kein Netzwerk), (2) `MistralLandmarkClient` inkl. `httpx.MockTransport`-Tests analog `AnthropicLandmarkClient`, (3) `Settings`-Felder + `build_landmark_client()`-Dispatch, (4) additive Migration `photo_landmark_detections.provider`, (5) `.env.example`/`docs/setup.md`/`docs/architecture.md`.
- **Keine neue Backend-Abhängigkeit:** reiner `httpx`-Aufruf, `httpx` bereits vorhanden.

## UI/UX

Nicht relevant (idea-sharpener, Schritt 7, strukturell begründet — kein AskUserQuestion nötig): Die Provider-Wahl ist eine reine Deploy-/Env-Einstellung ohne jede sichtbare Oberfläche. Der `landmark`-Name selbst wird bereits laut ADR 0025 in keiner UI angezeigt (reine Persistenz-Vorbereitung); auch das neue `provider`-Feld hat keinen UI-Bezug.

## Security

Sicherheitsrelevant, ja (`security-engineer`-Konsultation, 2026-08-23) — zweiter externer Cloud-Anbieter im bereits produktiven `landmark`-Scoring-Pfad (Spec 0047/ADR 0025), neues Secret. Vollständige Herleitung siehe `specs/architecture/0003-securitykonzept.md`, Abschnitt "Cloud-Vision-API".

**Keine neue Angriffsflächen-Klasse:** dieselbe Datenexpositions-Begrenzung wie beim bestehenden Anthropic-Pfad (Vorfilterung, nur `display`-Cache-Variante, kein GPS/EXIF-Zugriff, Skip bereits gescorter Fotos), derselbe Consent-Mechanismus (`Project.cloud_landmark_detection_enabled`, laut ADR 0031 unverändert providerunabhängig, kein neuer Endpunkt), dieselbe SSRF-Einschätzung (fester Ziel-Host `https://api.mistral.ai/v1/chat/completions`, kein nutzergesteuerter Pfad).

**Provider-Wahl bewusst außerhalb der Nutzer-Einwilligung:** `Settings.landmark_provider` (env `LANDMARK_PROVIDER`, Default `"anthropic"`) ist eine reine Betreiber-/Deployment-Entscheidung (ADR 0031 Punkt 1/4), kein `Project`-Feld, kein UI-Berührungspunkt. Der Consent-Schalter deckt weiterhin nur "Cloud-Verarbeitung ja/nein" ab, nicht "welcher Anbieter".

**Secrets:** `MISTRAL_API_KEY` über `Settings.mistral_api_key`, exakt das bestehende `ANTHROPIC_API_KEY`-Muster. Muss-Kriterium, providerneutral: `MistralLandmarkClient`/`LandmarkApiError` darf nie Key oder Base64-Bilddaten in Meldung/Log einbetten.

**DPA-/Rechtsraum-Restrisiko bei Mistral (bewusst akzeptiert, kein Blocker):** Mistral AI SAS (Frankreich/EU) bietet EU-natives Hosting — der von Daniel gewünschte Vorteil gegenüber Anthropic. Anders als bei Anthropic (dort per Nachrecherche geklärt, ADR 0025) bleibt hier die DPA-/ZDR-Lage ungeklärt: Zero Data Retention nur im kostenpflichtigen "Scale"-Tarif, DPA-Zuordnung für Privatkonten laut Spec-0035-Recherche widersprüchlich dokumentiert ("Commercial Customers" vs. "Consumers"). Daniel wurde dieser Unterschied im Devil's-Advocate-Gespräch explizit gespiegelt und hat die Wahlmöglichkeit trotzdem bestätigt — das reine Vorhandensein der EU-Option reicht ihm, auch ohne geklärte ZDR-/DPA-Garantie. Eine Produktentscheidung Daniels, kein technisches Restrisiko dieser Konsultation.

`specs/architecture/0003-securitykonzept.md` wurde im Rahmen dieser Konsultation bereits providerneutral aktualisiert (Abschnitt "Cloud-Vision-API" umbenannt/erweitert, neuer Restrisiko-Bullet).

## Teststrategie

Struktur analog Spec 0047. `specs/architecture/0002-testkonzept.md` wurde bereits ergänzt (neue Unterektion "Zweite `LandmarkClientLike`-Implementierung + providerneutrale Parsing-Hilfsfunktion + `Literal`-Provider-Dispatch", kein neues Grundprinzip nötig).

**Testebenen:**
- **Unit (`test_landmark.py`):** `MistralLandmarkClient` komplett über `httpx.MockTransport` (kein `unittest.mock.patch`), analog dem bestehenden Anthropic-Testblock. `_landmark_detection_from_json` zusätzlich direkt gegen ein bereits geparstes Dict getestet, ohne HTTP.
- **Unit (`test_config.py`):** Default/Override/ungültiger-Wert für `landmark_provider`, Default für `mistral_api_key`.
- **Integration (`test_worker_criterion_scoring.py`, In-Memory-DB, Fake-`LandmarkClientLike`):** `provider`-Wert wird korrekt persistiert; Umschalt-Regressionstest (altes `provider`-Feld bleibt bei Providerwechsel unverändert).
- **Migration (`test_models.py`):** neue Spalte per `inspect()` verifiziert.

**Relevante Edge Cases:**
1. Mistral-Response ohne erwartetes `choices`/`message`/`content`-Feld → `LandmarkApiError`.
2. `image_url` als flacher String statt fälschlich verschachteltem `{"url": ...}` — expliziter Regressionstest (Verwechslungsgefahr mit OpenAI-Format).
3. Unbekannter `LANDMARK_PROVIDER`-Wert → `ValidationError` beim Prozessstart, nicht stiller Fallback.
4. Gemeinsame Parsing-Hilfsfunktion mit beiden Provider-Rohformen durchlaufen.
5. Provider-Wechsel zwischen zwei Läufen desselben Fotos (Skip bleibt providerunabhängig, `provider`-Feld nicht überschrieben).
6. Confidence-Klemmung (`>1`, `<0`) — jetzt über die gemeinsame Funktion einmal statt zweimal geprüft.

## Entscheidungen (2026-08-23, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Scope bewusst auf `landmark` begrenzt:** Die heute lokale, mediapipe-basierte Inhaltsklassifizierung (ADR 0015) auf Cloud/Mistral umzustellen ist ausdrücklich eine spätere, separate Idee — Daniel hat das im Klärungsgespräch selbst als "später" markiert, keine Vorwegnahme in dieser Spec.
- **Devil's-Advocate-Ergebnis, von Daniel bestätigt:** Der ursprünglich angenommene Datenschutzvorteil von Mistral ("EU-Sitz") ist laut bestehender Recherche (Spec 0035) nicht klar belegt — Zero Data Retention nur im kostenpflichtigen Tarif, DPA-Lage für Privatkonten unklar. Daniel wurde das explizit gespiegelt (Optionen: trotzdem umsetzen / erst nachrecherchieren / zurückstellen) und hat sich für "trotzdem umsetzen wie geplant" entschieden — die reine Wahlmöglichkeit reicht ihm, unabhängig vom tatsächlich belegten Datenschutzgewinn.
- **Neue ADR statt Editieren von ADR 0025:** `architect` hat sich für eine neue ADR-Datei (`decisions/0031-mistral-provider-option-cloud-landmark.md`) statt einer nachträglichen Änderung von ADR 0025 entschieden — ADR 0025 bleibt als historisches Dokument unangetastet (nur die Status-Zeile bekam einen Verweis-Pointer auf ADR 0031), superseded wird ausdrücklich nur die dortige Exklusivitäts-Aussage in Punkt 1 ("nicht Mistral"), nicht die übrige Begründung.
- **Neue Spalte `photo_landmark_detections.provider`:** eigenständige technische Entscheidung von `architect` (kein Rückfrage-Charakter) — verhindert, dass bei einem späteren Umschalten von `LANDMARK_PROVIDER` die Herkunft bereits gescorter Fotos stillschweigend unklar wird.
- **Provider-Wahl global statt pro Projekt:** bewusst als Deployment-/Env-Entscheidung gehalten, nicht als weiteres `Project`-Feld — konsistent mit Daniels ursprünglicher Vorgabe im Klärungsgespräch ("Settings/Umgebungsvariable"), kein Runtime-UI-Selektor.
- **`ux-ui-designer` nicht konsultiert (Schritt 7):** strukturell begründet — reine Deploy-/Env-Einstellung ohne jede sichtbare Oberfläche, kein UI-Berührungspunkt (der `landmark`-Name selbst wird laut ADR 0025 ohnehin in keiner UI angezeigt).

## Offene Fragen

Keine — alle im Sharpening-Gespräch aufgetretenen Unklarheiten wurden mit Daniel geklärt (siehe Abschnitt "Entscheidungen").

## Out of Scope

- Lokale mediapipe-Klassifizierung (ADR 0015) auf Mistral/Cloud umstellen — separate, spätere Idee.
- UI-Selektor zur Runtime-Änderung des Providers — Provider-Wahl bleibt eine Deployment-/Umgebungs-Entscheidung.
- Batch-API- oder Caching-Optimierungen für Mistral — nur Baseline-REST-Implementierung, analog Anthropic v1 (Spec 0047).
- Kostenvergleich zwischen Mistral und Anthropic — nicht Teil der Entscheidungsgrundlage, Provider wird per `.env` konfiguriert.
- Anzeige des Landmark-Namens oder des Providers in der UI — weiterhin reine Persistenz-Vorbereitung wie in Spec 0047.
