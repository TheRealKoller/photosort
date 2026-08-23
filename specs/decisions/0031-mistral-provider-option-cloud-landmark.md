# 0031 - Mistral als konfigurierbare Cloud-Provider-Alternative für `landmark` (Anthropic bleibt Default)

**Status:** Accepted
**Datum:** 2026-08-23
**Bezug:** [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) (Accepted — Punkt 1 wird durch diese ADR **teilweise** superseded, siehe unten; Begründung/restliche Punkte bleiben unverändert gültig), [`features/0035-klassifizierung-qualitaet-inhalt-recherche.md`](../features/0035-klassifizierung-qualitaet-inhalt-recherche.md) (Mistral-Security-Recherche, Abschnitt 3), [`inbox/0034-bildklassifizierung-mistral-modelle.md`](../inbox/0034-bildklassifizierung-mistral-modelle.md) (Ursprung), künftige Feature-Spec `specs/features/0054-mistral-provider-option-cloud-landmark.md`.

## Kontext

Daniel möchte aus EU-Hosting-/Datenschutz-Erwägungen die Möglichkeit haben, die Cloud-Sehenswürdigkeit-Erkennung (`landmark`-Kriterium) wahlweise über Mistral (Sitz Frankreich/EU) statt Anthropic (USA) laufen zu lassen. Im Devil's-Advocate-Gespräch wurde ihm gespiegelt, dass laut Spec 0035 Mistrals Zero-Data-Retention nur im kostenpflichtigen "Scale"-Tarif verfügbar ist und die DPA-Lage für Privatkonten dort weiterhin unklar/widersprüchlich dokumentiert ist — anders als bei Anthropic, wo ADR 0025 das inzwischen geklärt hat (DPA/SCCs gelten für jede API-Key-Nutzung automatisch, unabhängig vom Kontotyp). Daniel möchte trotzdem umsetzen: das reine Vorhandensein der Wahlmöglichkeit reicht ihm — ein bewusst akzeptiertes, dokumentiertes Restrisiko, keine technische Fehleinschätzung.

**Ausdrücklich kein Themenwechsel zu ADR 0025 Punkt 1:** Dort wurde entschieden, Anthropic statt Mistral als *alleinigen* Provider zu verwenden ("Provider: Anthropic … nicht Mistral"). Diese ADR kehrt diese Entscheidung nicht um — Anthropic bleibt der empfohlene Default aus genau den dort genannten Gründen (geklärte DPA-Lage, native Batch-API/Prompt-Caching, Kontinuität der vorhandenen Recherche). Sie hebt lediglich die dort implizite *Exklusivität* auf: Mistral wird als zweite, bewusst risikobehaftete, **konfigurierbare** Option ergänzt, keine Ablösung.

Ausdrücklich außerhalb des Scopes: die lokale mediapipe-basierte Inhaltsklassifizierung (ADR 0015) bleibt unverändert rein lokal — diese ADR betrifft ausschließlich das bereits Cloud-basierte `landmark`-Kriterium.

## Entscheidung

### 1. Teilweise Supersession von ADR 0025 Punkt 1: Provider wird konfigurierbar, Anthropic bleibt Default

`landmark` bekommt eine zweite, wählbare Provider-Implementierung. Die Wahl ist **keine Runtime-/Projekt-Einstellung** (kein UI, kein `Project`-Feld) — sie bleibt eine reine Betreiber-/Deployment-Entscheidung über eine Umgebungsvariable, strikt getrennt vom bestehenden Nutzer-Einwilligungsmechanismus (Punkt 4). Begründung für Env-Var statt Datenbank-Feld: analog zu den bereits etablierten reinen Betriebsparametern des Projekts (`scan_download_concurrency`, `landmark_api_concurrency`) — welchem der beiden Anbieter man als Betreiber vertraut, ist konzeptionell dasselbe wie "wie stark darf ich meinen OpenCloud-Server parallel belasten", nicht "worin willigt der Nutzer für sein Projekt ein" (das bleibt Punkt 4/ADR 0025 Punkt 5 unverändert).

ADR 0025 Punkt 1 bleibt inhaltlich als Empfehlung gültig (Anthropic default, aus den dort genannten Gründen) — nur die Formulierung "nicht Mistral" als *einzige* Option wird durch diese ADR superseded. Der Status von ADR 0025 wird um einen Verweis hierher ergänzt (kein Neuschreiben ihrer Begründung).

**DPA-Restrisiko bei Mistral bleibt bestehen und ist bewusst akzeptiert** (Daniels ausdrückliche Produktentscheidung, keine technische): Zero-Data-Retention nur im kostenpflichtigen Tarif, DPA-Zugriff für Privatkonten laut Spec 0035 nicht eindeutig geklärt. Wird in der Spec (Security-Abschnitt, `security-engineer`-Konsultation) als dokumentiertes Restrisiko festgehalten, kein Blocker.

### 2. Neues `MistralLandmarkClient` in `landmark.py`, exakt analog `AnthropicLandmarkClient`

Implementiert `LandmarkClientLike` (bereits provider-neutral geschnitten, ADR 0025 Punkt 2) — direkter `httpx`-REST-Aufruf, kein Mistral-SDK (Minimalismus-Prinzip ADR 0006, dieselbe Begründung wie bei Anthropic). Recherchierte, für die Implementierung verbindliche API-Fakten (`research-engineer`, 2026-08-23, gegen offizielle `docs.mistral.ai`-Quellen geprüft):

- **Endpunkt:** `https://api.mistral.ai/v1/chat/completions` (neue Konstante `MISTRAL_CHAT_COMPLETIONS_URL`) — derselbe Endpunkt wie für reine Text-Completions, kein separater Vision-Pfad.
- **Auth:** `Authorization: Bearer <api_key>`-Header (abweichend von Anthropics `x-api-key`+`anthropic-version`-Kombination).
- **Bild-Content-Block — wichtige Schema-Abweichung von Anthropic/OpenAI:** `{"type": "image_url", "image_url": "data:<mime>;base64,<...>"}`. Bei Mistral ist `image_url` ein **flacher String** (Data-URI), **kein** verschachteltes `{"url": "..."}`-Objekt wie im OpenAI-Schema — vom Mistral-Cookbook bestätigt, developer soll das 1:1 übernehmen, nicht das vertrautere OpenAI-Schema annehmen.
- **Nativer JSON-Mode nutzen:** `response_format: {"type": "json_object"}` im Request-Body mitschicken. Mistral unterstützt das nativ, Anthropic (dort bleibt die bestehende reine Prompt-Anweisung unverändert) nicht — erhöht die Zuverlässigkeit des zurückgelieferten JSON ohne nennenswerten Zusatzaufwand (ein zusätzliches Body-Feld). Bewusst **nicht** genutzt: das zusätzliche Assistant-Message-Prefixing-Feature (`{"role": "assistant", "content": "{", "prefix": true}`) — ein zweiter Zuverlässigkeitsmechanismus lohnt sich für dieses eng umrissene Klassifikationsformat nicht.
- **Response-Parsing:** `response.json()["choices"][0]["message"]["content"]` liefert den rohen JSON-Text als String (Standard-Chat-Completion-Schema, strukturell analog OpenAI) → `json.loads(...)`.
- **Gemeinsame Hilfsfunktion statt Code-Duplikation:** Die Extraktion von `name`/`confidence` aus dem geparsten JSON-Objekt sowie das Klemmen von `confidence` auf `[0, 1]` (bestehende Logik in `landmark.py::_parse_detection`) wird in eine provider-neutrale Hilfsfunktion ausgelagert (z.B. `_landmark_detection_from_json(parsed: Any) -> LandmarkDetection`), die beide Clients nach der jeweils providerspezifischen Extraktion des rohen JSON-**Texts** aus ihrer unterschiedlichen Response-Hülle aufrufen (Anthropic: `content`-Blockliste mit `type=="text"`; Mistral: `choices[0].message.content` direkt). Kein neues Muster, reine Verhinderung von Duplikation.
- **Modell:** Ministral-3-Familie (aktuell aktive, güns­tigste vision-fähige Modelllinie laut Mistral-eigener Modellübersicht, Stand 2026-08). Die früher naheliegenden Pixtral-Modelle sind bereits deprecated/retired (`pixtral-12b-2409`: retired seit 31.12.2025; `pixtral-large-2411`: Retirement 31.5.2026) — **nicht** für eine Neuimplementierung verwenden. Die exakte Modell-ID (`ministral-3-8b-...` vs. `-14b-...` vs. ein `-latest`-Alias) ist — exakt wie `ANTHROPIC_LANDMARK_MODEL` in ADR 0025 — eine technische Detailentscheidung des `developer`-Agenten beim TDD-Einstieg, **nicht** hier festgelegt: Modell-IDs ändern sich im Projektverlauf nachweislich häufig (bei Anthropic bereits mehrfach, jetzt auch bei Mistral: Pixtral binnen eines Jahres komplett abgelöst). Die Recherche fand für die exakte Schreibweise zwei widersprüchliche Kandidaten-Strings — developer soll die aktuell gültige ID über `console.mistral.ai` oder `GET /v1/models` verifizieren, keinen der recherchierten Strings ungeprüft übernehmen.
- **Fehlerbehandlung:** analog Anthropic — `LandmarkApiError` (bereits provider-neutral benannt, keine Umbenennung nötig) bei `response.status_code >= 400`, Meldung nur mit Statuscode/Reason-Phrase (kein Response-Body-Parsing nötig, unabhängig vom nicht abschließend recherchierten Mistral-Fehler-JSON-Schema — das bestehende Anthropic-Muster verlässt sich ohnehin nur auf `httpx.Response`-Metadaten, kein anbieterspezifisches Risiko). Sicherheits-Muss-Kriterium unverändert: niemals Secret/Bilddaten in der Fehlermeldung.
- **Timeout:** `LANDMARK_REQUEST_TIMEOUT_SECONDS` (60s) wiederverwendet, kein separater Wert — kein Hinweis in der Recherche auf grundsätzlich andere Antwortzeit-Charakteristik.
- **Offene, vor Implementierung zu verifizierende Punkte** (Recherche konnte sie nicht abschließend belegen, siehe Quellenbewertung unten): exakte Bild-Limits (Auflösung/Größe/Anzahl pro Request — für ein einzelnes, bereits auf 2048×2048 begrenztes Bild aus dem `display`-Cache voraussichtlich unkritisch) und das genaue 4xx/5xx-Fehler-JSON-Schema (für die gewählte, body-freie Fehlerbehandlung ohnehin nicht relevant).

### 3. Provider-Auswahl über Settings-Dispatch, `worker.py` bleibt unverändert

- `Settings.landmark_provider: Literal["anthropic", "mistral"] = "anthropic"` (env `LANDMARK_PROVIDER`) — `Literal` statt eines neuen Enums (Minimalismus, ADR 0006): Pydantic validiert einen ungültigen `.env`-Wert bereits beim Prozessstart (`ValidationError`), dasselbe Frühwarn-Prinzip wie `Field(ge=1)` bei den bestehenden Concurrency-Feldern.
- Neues Secret `Settings.mistral_api_key: str = ""` (env `MISTRAL_API_KEY`), exakt nach dem `anthropic_api_key`-Muster.
- `build_landmark_client()` wird zur kleinen Dispatch-Factory:

  ```python
  def build_landmark_client() -> LandmarkClientLike:
      if settings.landmark_provider == "mistral":
          return MistralLandmarkClient(api_key=settings.mistral_api_key)
      return AnthropicLandmarkClient(api_key=settings.anthropic_api_key)
  ```

- `worker.py::run_criterion_scoring` ändert sich **nicht** — `build_landmark_client` ist dort bereits als injizierbarer `Callable[[], LandmarkClientLike]`-Default-Parameter verankert (ADR 0025 Punkt 2/5). Die Provider-Wahl bleibt vollständig hinter der Factory verborgen, kein neuer Verzweigungspunkt in der aufrufenden Pipeline. Keine Breaking Changes: ein Deployment ohne gesetztes `LANDMARK_PROVIDER` verhält sich exakt wie bisher (Default `"anthropic"`, `ANTHROPIC_API_KEY` weiterhin die einzige benötigte Variable).

### 4. Consent-Mechanismus bleibt unverändert providerunabhängig

`Project.cloud_landmark_detection_enabled`/`cloud_landmark_consent_at` (ADR 0025 Punkt 5) werden **nicht** angetastet. Ein Nutzer, der die Cloud-Landmark-Erkennung für ein Projekt einwilligt, konsentiert "Cloud-Verarbeitung des Fotos für dieses Kriterium" — welcher Anbieter dahintersteckt, ist eine Betreiber-Entscheidung (Punkt 1/3), keine, die pro Projekt oder pro Nutzer variieren soll. Keine neue Consent-UI, kein neuer Endpunkt.

### 5. Neue additive Spalte `photo_landmark_detections.provider`, um Provenienz bei einem späteren Umschalten nicht stillschweigend zu verlieren

ADR 0025 Punkt 3 legt bewusst fest, dass ein Foto mit bereits vorhandener `landmark`-Zeile bei einem erneuten Lauf **nicht** erneut an die Cloud geschickt wird. Kombiniert mit einer jetzt konfigurierbaren, global umschaltbaren Provider-Wahl entsteht dadurch ein reales Szenario: schaltet Daniel `LANDMARK_PROVIDER` mitten im Projektverlauf von `anthropic` auf `mistral` um, behalten bereits gescorte Fotos ihre alten, Anthropic-basierten Werte, während neu gescorte Fotos Mistral-basierte Werte bekommen — ohne jede Möglichkeit, das im Nachhinein zu unterscheiden, weder für Debugging/Qualitätsvergleich noch um bei Bedarf gezielt nur die Werte eines Providers neu zu berechnen.

Die Marginalkosten, das jetzt mitzuerfassen, sind gering (ein zusätzliches `str`-Feld, im selben Upsert wie `name`/`confidence` geschrieben, keine Zusatzabfrage) — ein späteres Nachrüsten würde dagegen, exakt wie bei ADR 0025 Punkt 6 für den Landmark-Namen begründet, den Wert für bereits gescorte Fotos dauerhaft verlieren, da diese beim nächsten Lauf ohnehin übersprungen werden. Deshalb: neue Spalte `photo_landmark_detections.provider: str` (Werte `"anthropic"`/`"mistral"`, additive Migration, kein Platzhalter — wird atomar mit `name`/`confidence` aus derselben Anfrage gesetzt). Reine Persistenz-Vorbereitung, keine UI-Auswertung in v1 (analog zur bereits etablierten Zurückhaltung bei `name` selbst).

## Begründung

- Erfüllt Daniels EU-Hosting-Wunsch als echte, aber bewusst risikobehaftete Option, ohne den bereits validierten Anthropic-Default zu verändern oder ADR 0025 in der Substanz zu widerrufen.
- Wiederverwendet das in ADR 0025 etablierte Protocol/Factory-Testbarkeitsmuster vollständig — eine zweite Implementierung + ein kleiner Dispatch, kein neues Architekturmuster.
- Hält die Provider-Wahl als reine Deploy-Entscheidung strikt von der Nutzer-Einwilligung getrennt — vermeidet eine UI-/Datenmodell-Erweiterung für einen Anwendungsfall (Laufzeit-Umschaltung durch den Nutzer selbst), für den in einem Zwei-Personen-Familienprojekt kein Bedarf erkennbar ist.
- Die neue `provider`-Spalte verhindert eine stille, unbemerkte Vermischung der Datenherkunft bei einem späteren Umschalten — zu vernachlässigbaren Zusatzkosten, exakt die bereits in ADR 0025 Punkt 6 etablierte "jetzt billig, später ggf. unmöglich nachzurüsten"-Abwägung.

## Konsequenzen

- **Neue Backend-Abhängigkeit:** keine (wieder reiner `httpx`-Aufruf, `httpx` bereits vorhanden).
- **Neues Secret:** `MISTRAL_API_KEY` (`.env.example`, `Settings.mistral_api_key`) — leer bleibt unkritisch, solange `LANDMARK_PROVIDER` nicht auf `mistral` gesetzt ist.
- **Neue Env-Var:** `LANDMARK_PROVIDER` (Default `anthropic`, optional `mistral`) — dokumentierte, `Literal`-validierte Deployment-Einstellung, kein neuer Betriebsparameter im Sinne einer Concurrency-Obergrenze.
- **Neue Migration:** additiv, eine Spalte `photo_landmark_detections.provider: str`.
- **`docs/architecture.md`/`README.md`/`docs/setup.md`** (Owner `architect`) werden bei Umsetzung um `MistralLandmarkClient`, `LANDMARK_PROVIDER`/`MISTRAL_API_KEY` und die neue Spalte ergänzt.
- **ADR 0025 Status-Zeile** wird um einen Verweis auf diese ADR ergänzt (Punkt 1 dort teilweise superseded) — der übrige Inhalt von ADR 0025 bleibt unverändert stehen.
- Ein späterer, dritter Provider oder ein tatsächlicher *Wechsel* des Defaults (Mistral statt Anthropic als Default) bleibt architekturrelevant und braucht wiederum eine neue ADR, kein stillschweigendes Umschwenken.
