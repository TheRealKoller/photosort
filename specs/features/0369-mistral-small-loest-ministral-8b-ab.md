# 0369 - Mistral Small 2603 löst Ministral 8B als Modellwahl ab

**Status:** Implemented ([PR #371](https://github.com/TheRealKoller/photosort/pull/371))
**Erstellt:** 2026-09-09
**Bezug:** [Issue #369](https://github.com/TheRealKoller/photosort/issues/369)

## Ziel

Das Modellangebot des Cloud-Anbieters Mistral soll aktuell bleiben. Neben dem günstigen
Voreinstellungs-Modell steht heute eine stärkere Alternative zur Wahl; diese soll durch ein
neueres, leistungsfähigeres Modell (`mistral-small-2603`) ersetzt werden. Anlass ist kein
erlebtes Qualitätsproblem, sondern die Pflege der zweiten Anbieteroption: Wird sie nicht
gepflegt, veraltet sie unbemerkt und steht im Bedarfsfall nicht mehr sinnvoll zur Verfügung.

Betroffen ist ausschließlich der Betreiber der Installation — die Modellwahl ist eine
Deployment-Entscheidung für beide Cloud-Funktionen gemeinsam (Kategorie-Vorschläge und
Sehenswürdigkeits-Erkennung), kein Feld pro Projekt und keine Einstellung in der Oberfläche.
Die Auswahl bleibt bewusst kurz und kuratiert: zwei Modelle je Anbieter, nicht drei.

Dies ist der **erste Fall, in dem ein wählbarer Wert zurückgenommen statt ergänzt wird**. Der
mit Spec [`0304`](./0304-cloud-modell-je-anbieter-waehlbar.md) gebaute Mechanismus wird dabei
nur angewendet, nicht verändert.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich bei Mistral ein aktuelleres, stärkeres
Modell als bisher wählen können, damit die zweite Anbieteroption auf einem gepflegten Stand
bleibt und ich bei Bedarf ohne weitere Vorarbeit darauf wechseln kann.

## Akzeptanzkriterien

Gegenüber dem Issue-Body durch `test-engineer` auf Testbarkeit geschärft; die fachliche Aussage
ist unverändert, ergänzt sind die konkreten Werte und Orte, an denen sie prüfbar wird.

- [ ] **K1** `mistral-small-2603` ist als Modell des Anbieters Mistral wählbar.
- [ ] **K2** `ministral-8b-2512` ist nicht mehr wählbar und hinterlässt **keinen Preiseintrag**;
      Mistral bietet weiterhin genau zwei Modelle zur Auswahl (`== 2`, nicht „mindestens zwei").
- [ ] **K3** Ohne gesetztes `LANDMARK_MODEL` bleiben aufgelöstes Modell (`ministral-3b-2512`) und
      Kostenschätzung je Bild ($0,0003) unverändert.
- [ ] **K4** Der Preis des neuen Modells ist gegen die offizielle Anbieterdokumentation
      verifiziert und als Pflichtfelder `source_url` (https, offizielle Anbieterdomain) und
      `verified_on` hinterlegt. Gelingt die Verifikation nicht, wird das Modell **nicht**
      aufgenommen (ADR [`0059`](../decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md)
      Punkt 5) — ein geschätzter oder aus Websuch-Aggregaten abgeleiteter Preis ist kein Ersatz.
- [ ] **K5** Die Kostenschätzung vor dem Start weist für das neue Modell $0,000504 je Bild aus
      (gerundet ~$0,0005), sichtbar als `price_per_image_usd`, und nicht „nicht erfasst".
- [ ] **K6** Eine Konfiguration `LANDMARK_PROVIDER=mistral` + `LANDMARK_MODEL=ministral-8b-2512`
      bricht den Start mit einer Meldung ab, die den beanstandeten Wert, den eingestellten
      Anbieter, beide gültigen Werte und die Voreinstellung nennt — und **keinen weiteren
      Settings-Wert**. Kein stiller Rückfall, kein Lauf mit einem anderen Modell.
- [ ] **K7** Bereits durchgeführte Klassifizierungen behalten gespeicherte Modellangabe und
      eingefrorene Ist-Kosten wörtlich und werden nicht nachgerechnet. **Der aus der Modell-ID
      abgeleitete Anbieter eines solchen Altlaufs ist danach `null`** — die Oberfläche zeigt die
      Modell-ID allein, statt einen Anbieter zu raten (ADR
      [`0068`](../decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md)
      Punkt 6).
- [ ] **K8** `.env.example` **und** `docs/setup.md` nennen die geänderte Auswahl samt
      Kostenschätzung je Bild.

### Anmerkung zu K7

K7 ist der einzige Punkt, an dem sich für Daniel sichtbar etwas ändert, das der Issue-Wortlaut
„unverändert" nicht erwarten lässt: Ein Altlauf, der mit `ministral-8b-2512` gerechnet hat,
verliert in der Lauf-Bilanz sein Anbieter-Label. Modell-ID und Betrag bleiben wörtlich stehen.
Das ist keine Regression, sondern der von ADR 0068 Punkt 6 ausdrücklich vorgesehene Pfad für
„Altlauf, entferntes Modell"; ein geratener Anbieter wäre eine Behauptung über die
Vergangenheit, die der Code nicht belegen kann. Die betroffene Menge dürfte klein bis leer sein
— das Modell war seit dem 2026-09-06 wählbar und war nie Voreinstellung.

## Datenmodell-Bezug

Keine Änderung. Kein neues Feld, keine Migration, kein geänderter gespeicherter Wert. Die
persistierten Modell-IDs und eingefrorenen Beträge vergangener Läufe
(`criterion_scoring_runs.landmark_cost_usd`, `remote_category_classification_runs.cost_usd`)
bleiben, wie sie sind — genau darauf beruht K7. `docs/architecture.md` ist nicht betroffen (die
Datei nennt keine Modell-IDs).

## Architektur / Umsetzung

**Ansatz in einem Satz:** Reiner Registry-/Preistabellen-Austausch innerhalb des mit Spec
[`0304`](./0304-cloud-modell-je-anbieter-waehlbar.md)/ADR
[`0059`](../decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md)
bereits gebauten Mechanismus — der zweite Mistral-Eintrag in
`cloud_vision.py::VISION_MODELS_BY_PROVIDER` wird ersetzt, sein Preiseintrag in
`pricing.py::MODEL_PRICING` mitgeführt. Kein neuer Mechanismus, kein neues Feld, keine
Migration, keine Frontend-Änderung.

**Keine neue ADR.** ADR 0059 hat die tragenden Festlegungen bereits getroffen (kuratierte
Registry als einzige Quelle des Wählbaren, Preisverifikation als Pflichtfeld, `None` statt `0`,
Startvalidierung). Diese Story *wendet* sie an, sie ändert keine.

### Der verifizierte Preis

| Prüfung | Quelle | Ergebnis |
|---|---|---|
| Modell-ID | `https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03` (abgerufen 2026-09-09) | `mistral-small-2603` (Produktname „Mistral Small 4", Release 2026-03-16). **Nicht** den gleitenden Alias `mistral-small-latest` eintragen — er wandert unter uns weg. |
| Preis | dieselbe Modellkarte **und** `https://mistral.ai/pricing/api/` (abgerufen 2026-09-09) | **$0,15/MTok Eingabe, $0,60/MTok Ausgabe** |
| Gegenprobe | `https://mistral.ai/pricing/api/` | reproduziert die bereits im Produkt stehenden $0,10 (3B) und $0,15 (8B) — die Seite liefert nicht irgendeine Zahl, sondern die, gegen die die Bestandseinträge verifiziert wurden |

**Der Preis ist asymmetrisch — und das widerlegt eine Verallgemeinerung, die heute im Code
steht.** Der Kommentar in `pricing.py` behauptet bei beiden Ministral-Einträgen „symmetrische
Preisgestaltung, anders als bei Anthropic". Das galt für die Ministral-Familie, nicht für
Mistral als Anbieter. Der Kommentar ist im selben Commit auf die Familie einzugrenzen.
Rechnerisch trägt die Asymmetrie ohne Codeänderung: `estimate_usd_per_image` ist
`compute_cost_usd` über der Annahme und gewichtet Ein-/Ausgabe ohnehin getrennt.

**Abgeleitete Schätzung je Bild:** (2 880 × 0,15 + 120 × 0,60) / 10⁶ = **$0,000504**,
dokumentiert als ~$0,0005. Höher als die Voreinstellung ($0,0003). Die Zahl für die Doku ist
**abzuleiten, nicht abzuschreiben** — sie kommt aus `estimate_usd_per_image`.

### Vision-Fähigkeit: belegt, mit offen dokumentierter Lücke

Zwei erstparteiliche Quellen sagen ausdrücklich „accepts both text and image inputs"
(Ankündigung `https://mistral.ai/news/mistral-small-4/`, offizielle Modellkarte
`https://huggingface.co/mistralai/Mistral-Small-4-119B-2603`). Die Seite
`https://docs.mistral.ai/capabilities/vision`, die Bildeingabe über `/v1/chat/completions`
regelt, **listet das Modell nicht** — sie ist allerdings erkennbar einen Release-Zyklus veraltet
(nennt Mistral Medium 3.1, während die Übersicht bereits 3.5 führt).

**Entscheidung Daniels (2026-09-09):** Das Modell wird aufgenommen, die Lücke offen
dokumentiert — in Spec, Code-Kommentar und `docs/setup.md`. Es ist nicht die Voreinstellung und
wird nur nach bewusster Umstellung aktiv. Die Belegkette gehört wörtlich und ehrlich in den
Kommentar: was belegt ist, mit Abrufdatum, **plus** dem Vermerk, dass die Fähigkeitsseite das
Modell zum Abrufzeitpunkt nicht führt. Verboten ist beides — die Fähigkeitsseite als Beleg zu
zitieren, obwohl sie das Modell nicht führt, und die Lücke wegzulassen. Die Risikobewertung
steht im Abschnitt „Security", Punkt E.

### Die drei Entwurfsentscheidungen

**1. `ministral-8b-2512` wird vollständig entfernt — Konstante, Registry-Eintrag *und*
Preiseintrag.** Die Alternative wäre, den Preiseintrag als „historischen" Wert stehenzulassen.
Dagegen: Ist-Kosten werden im Moment des Laufs berechnet und in den Lauf-Spalten **eingefroren**
(ADR [`0051`](../decisions/0051-ist-kostenerfassung-remote-laeufe.md) Punkt 4);
`compute_cost_usd` wird ausschließlich mit `settings.resolved_landmark_model()` aufgerufen, also
nie mit einem Modell außerhalb der Registry. Ein zurückgelassener Preiseintrag hätte damit
*keinen* Leser, wäre aber weiterhin eine gepflegte Tatsachenbehauptung mit Quelle und Datum, die
bisher **kein** Test deckt (die Invariante ist eine Teilmengenprüfung). Genau die Bauform, die
driftet. K7 ist durch die eingefrorenen Spalten erfüllt, nicht durch die Preistabelle.

Verworfen wurde aus demselben Grund eine zweite „Historien"-Zuordnungstabelle: Abstraktion auf
Vorrat für ein Modell, das drei Tage im Produkt stand.

**2. Die Konstante heißt `MISTRAL_VISION_MODEL_SMALL`, nicht mehr `MISTRAL_VISION_MODEL_8B`.**
Der bisherige Name kodiert die Parameterzahl und wäre für Small 4 (119B, 6,5B aktiv) schlicht
falsch. Familienname statt Rollenname folgt dem etablierten Gegenstück
`ANTHROPIC_VISION_MODEL_SONNET`. **In den Kommentar gehört der Stolperstein:** dass „Small" hier
das *stärkere* der beiden wählbaren Mistral-Modelle bezeichnet, ist Mistrals
Produktnamensgebung, kein Vertipper — ohne diesen Satz liest der nächste Leser die
Registry-Reihenfolge als Fehler.

**3. `ASSUMED_USAGE_BY_PROVIDER["mistral"]` bleibt bei 2 880/120 — unverändert.** Sie hängt an
unserer Bildquelle und unserem Prompt, nicht am Modell (ADR 0059 Punkt 3); das neue Modell erbt
sie. Sie *darf* hier auch gar nicht angefasst werden: die Kalibrierungsauflage bindet sie an die
exakte Reproduktion von $0,0003 für das Voreinstellungs-Modell, und K3 hängt daran. Der
Kommentar hält stattdessen fest, dass die Annahme ab dieser Story **zwei Modellfamilien**
desselben Anbieters abdeckt und für `mistral-small-2603` unkalibriert ist (siehe Security S14).

### Betroffene Dateien

**Backend (`backend/src/photosort/`)**

| Datei | Änderung |
|---|---|
| `cloud_vision.py` | `MISTRAL_VISION_MODEL_8B = "ministral-8b-2512"` → `MISTRAL_VISION_MODEL_SMALL = "mistral-small-2603"`, samt neu geschriebenem Kommentar (Modell-ID, Belegkette zur Vision-Fähigkeit inkl. der offenen Lücke, Namens-Stolperstein); Registry-Tupel `"mistral"` entsprechend. Reihenfolge bleibt: Voreinstellung zuerst. |
| `pricing.py` | Import und `MODEL_PRICING`-Schlüssel folgen der Umbenennung; Eintrag `input_usd_per_mtok=0.15`, `output_usd_per_mtok=0.60`, `source_url="https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03"`, `verified_on=date(2026, 9, 9)`. Der 8B-Absatz im Kopfkommentar wird **ersetzt, nicht ergänzt**; die Behauptung „symmetrisch" wird auf die Ministral-Familie eingegrenzt; der Kommentar an `ASSUMED_USAGE_BY_PROVIDER` bekommt den Familien-Vermerk aus Entwurfsentscheidung 3. |

**Tests (`backend/tests/`)** — rot vor grün:

| Datei | Änderung |
|---|---|
| `test_cloud_vision.py` | Die beiden Tests, die die alte ID ausgeschrieben abgreifen, werden durch **einen** Test mit voller Tupel-Gleichheit ersetzt: `VISION_MODELS_BY_PROVIDER["mistral"] == ("ministral-3b-2512", "mistral-small-2603")` — pinnt K1, K2, K3 und die Reihenfolge in einer Assertion und bleibt nicht-tautologisch (ausgeschriebene IDs, bestehende Absicht aus Spec 0304). Die generischen Geschwistertests (`>= 2`) und `test_the_first_entry_is_the_unchanged_default_of_each_provider` bleiben **unverändert**. |
| `test_pricing.py` | Invariante `selectable ⊆ MODEL_PRICING` wird zur **Mengengleichheit** — der einzige generische Zwang, den 8B-Preiseintrag wirklich zu entfernen (K2). **Neu:** Literal-Pin `estimate_usd_per_image("mistral-small-2603", "mistral") == approx(0.000504)` plus Assertion, dass Ein- und Ausgabepreis verschieden sind (K5, und der einzige Schutz gegen ein vertauschtes oder versehentlich symmetrisch übernommenes Preispaar). **Neu:** `compute_cost_usd("ministral-8b-2512", …) is None`. Die $0,0052-/$0,0003-Pins bleiben unangetastet. |
| `test_config.py` | **Neu:** K6-Regression mit dem tatsächlich entfallenen Wert. Kein Produktionscode dafür — der Feldvalidator leistet das bereits, sobald das Modell die Registry verlässt; der Test pinnt es. Der `.env.example`-Anwesenheitstest geht in der neuen zweiseitigen Doku-Prüfung auf. |
| `test_api_projects.py` | **Neu:** K7 auf API-Ebene mit `landmark_model="ministral-8b-2512"` **und** gesetztem `landmark_cost_usd` — Modellangabe und Betrag wörtlich erhalten, abgeleiteter Anbieter `null`. |

**Konfiguration/Doku (im selben PR):**

| Datei | Änderung |
|---|---|
| `.env.example` | Zeile 71–73: `ministral-8b-2512 (~$0,00045/Bild)` → `mistral-small-2603 (~$0,0005/Bild)`, plus Umstellungshinweis (Security S16). |
| `docs/setup.md` | Zeile 311, Tabellenzeile `mistral`: wählbare Werte und Spalte „Schätzung je Bild" (`~$0,0003 / ~$0,0005`); Umstellungshinweis und die Probelauf-Empfehlung aus Security S18. |
| `.github/workflows/ci.yml` | Der Compose-Passthrough-Override setzt statt des Voreinstellungswerts `mistral-small-2603` — lässt die neue ID einmal außerhalb von pytest durch den echten Betriebspfad laufen. Der Default-Fall (leerer Wert) bleibt unverändert. |

**Der Doku-Test wird zweiseitig** (`test_config.py`): Die heutige Prüfung fordert nur die
*Anwesenheit* jedes wählbaren Modells — die veraltete `.env.example`-Zeile zum entfallenen
Modell bliebe damit grün stehen, und `docs/setup.md` hat bislang **überhaupt keinen Test**. Neu
gilt je Datei: (a) die per Modell-ID-Muster extrahierten Tokens sind **mengengleich** zur Menge
der wählbaren Modelle, (b) Selbstschutz — jede wählbare Modell-ID matcht das Muster (sonst engt
eine neue Namensfamilie die Prüfung still ein), (c) der aus `estimate_usd_per_image` abgeleitete
Betrag steht im Format `~$0,dddd` in der Datei. Geltungsbereich ausdrücklich nur betreiberseitige
Artefakte — `specs/**` und Quellkommentare dürfen die Historie nennen.

**Bewusst nicht angefasst** (jeweils geprüft, nicht vermutet): `docs/architecture.md`,
`frontend/` (keine Zeile — siehe UI/UX), `alembic/` (keine Migration), Voreinstellung,
Anbieterwahl, Anthropic-Auswahl, `ASSUMED_USAGE_BY_PROVIDER`.

### Reihenfolge der Umsetzung

1. Tests rot: `test_cloud_vision.py` (Tupel-Gleichheit), `test_pricing.py` (Mengengleichheit,
   Betrags-Pin, `None`-Pin), `test_config.py` (K6-Regression, zweiseitiger Doku-Test),
   `test_api_projects.py` (K7).
2. `cloud_vision.py` grün: Konstante umbenennen, Registry-Eintrag ersetzen, Kommentar neu.
3. `pricing.py` grün: Preiseintrag ersetzen, Kopfkommentar korrigieren, Familien-Vermerk.
4. `.env.example`, `docs/setup.md`, `ci.yml` — durch den zweiseitigen Doku-Test ein roter Test,
   keine Fleißaufgabe.
5. Gesamtcheck (`ruff`, `mypy --strict`, `pytest` mit Coverage-Gate ≥ 80 %).

### Bekannte Grenze, nicht in dieser Story gelöst

Mistral Small 4 ist ein Hybrid mit umschaltbarem „reasoning effort". Ob und wie
Reasoning-Tokens auf den Ausgabepreis von $0,60/MTok durchschlagen, ist nicht verifiziert. Die
**Ist**-Kosten bleiben davon unberührt (sie rechnen mit den tatsächlich gemeldeten Tokens), die
**Vorab-Schätzung** könnte dagegen zu niedrig ausfallen. Auffangen lässt sich das hier nicht:
`ASSUMED_USAGE_BY_PROVIDER` ist je *Anbieter* geschlüsselt, und ihre Ausgabekomponente
anzuheben verschöbe die Schätzung des Voreinstellungs-Modells — genau das, was K3 verbietet.
Entschärft wird es durch den harten Deckel `_MAX_RESPONSE_TOKENS = 256` in beiden Clients
(höchstens $0,00015 Ausgabekosten je Aufruf, siehe Security S13). Zeigt die erste reale
Rechnung deutlich mehr als 120 Ausgabe-Tokens je Bild, ist das der Anlass für eine eigene Story
(Verbrauchsannahme je *Modell* statt je Anbieter, mit eigener ADR) — nicht für eine stille
Korrektur hier.

## UI/UX

**Nicht relevant** — keine Frontend-Datei wird geändert. Geprüft, nicht vermutet:

- `price_per_image_usd` wird im Frontend **ausschließlich auf `null` geprüft**
  (`ClassificationEstimate.tsx:90`, Hinweiszeile „kein Preis hinterlegt") und **nie als Betrag
  gerendert**. `formatUsd` formatiert allein die Summen über die Fotomenge. K5 ist damit erfüllt,
  sobald der Preiseintrag existiert: Die Hinweiszeile verschwindet, die Summen werden gerechnet.
  Eine Formatierungsänderung an `formatUsd` ist ausdrücklich **nicht** Teil dieser Story — für
  Summen ist das Verhalten identisch mit dem heutigen Voreinstellungsmodell ($0,0003), das
  Verhalten ändert sich durch diese Story an keiner Stelle.
- Der Zweig für `provider === null` existiert samt Test bereits
  (`ClassificationProgress.tsx`, Testfall `model: 'ein-entferntes-modell'`) und deckt K7 ab. Ein
  zusätzlicher Testfall mit der tatsächlich entfallenen ID ist die ehrlichere Absicherung
  (Security S10), bleibt aber optional — die Aussage ist auf API-Ebene gepinnt.
- Keine Frontend-Datei nennt eine Mistral-Modell-ID.

Randbefund, **nicht** Teil dieser Story: Der Kommentar an `formatUsd`
(`frontend/src/utils/formatStats.ts`) verweist auf eine `$0.0052`-Pro-Bild-Darstellung in
`ClassificationSection.tsx`, die es dort nicht mehr gibt.

## Security

**Sicherheitsrelevant** (Konsultation `security-engineer`, 2026-09-09). Keine neue
Angriffsflächen-*Klasse*: derselbe Anbieter, dieselbe Endpunkt-Konstante
`MISTRAL_CHAT_COMPLETIONS_URL`, dasselbe Secret `MISTRAL_API_KEY`, kein neuer Endpunkt, kein
neues Feld, keine Migration, keine neue Eingabe von außen. Die Angriffsfläche wächst nicht — sie
tauscht einen Wert. Sicherheitlich neu sind drei Dinge: die **erste tatsächliche Entfernung**
eines Modells, der **erste Modellwechsel, der eine bestehende Betreiberkonfiguration ungültig
macht**, und das **erste wählbare Modell, dessen Vision-Fähigkeit nicht auf der
Fähigkeitsübersicht des Anbieters steht**.

### A. „Kein stiller Fallback" trägt nach dem Wechsel unverändert

- **S1** Der Validator bleibt wörtlich ein `@field_validator("landmark_model")`. Kein Umbau zu
  `@model_validator(mode="after")` — auch nicht mit der Begründung, diese Story ändere ja nur die
  Wertemenge. Grund unverändert (Spec 0304, S7/S8): pydantic hängt bei einem Modell-Validator das
  **vollständige Settings-Dict** als Fehler-Eingabe an die `ValidationError`, womit `SECRET_KEY`,
  `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY` und `OPENCLOUD_APP_TOKEN` im Startup-Traceback und in
  `exc.errors()`/`exc.json()` landen. Der Code-Kommentar, der das festhält, bleibt erhalten.
- **S2** Der Secret-Leak-Test aus Spec 0304 muss weiterlaufen. Verdrahtet er `ministral-8b-2512`
  als Beispielwert, wird er **angepasst, nicht gelöscht**.
- **S3** Der Startfehler ist der **einzige** Ausgang für eine Konfiguration mit dem entfallenen
  Wert. Verboten: eine Alias-/Migrationszuordnung `ministral-8b-2512 → mistral-small-2603`, eine
  Deprecation-Warnung mit Weiterlauf, ein `try/except` um `settings = Settings()`. Ein Alias wäre
  genau der stille Modellwechsel, den K6 ausschließt — und gefährlicher als der heutige Zustand,
  weil er das **abgerechnete** vom **konfigurierten** Modell entkoppelte.
- **S4** Exakter Stringvergleich gegen die Registry bleibt: kein `strip()`, kein `lower()`, kein
  Normalisieren. Der versendete Wert muss byte-identisch ein Registry-Element sein.
- **S5** Die Fehlermeldung nennt beanstandeten Wert, Anbieter, erlaubte Liste und Voreinstellung
  — alles öffentliche Herstellerbezeichnungen bzw. Betreibereingaben (geprüft, kein Befund).
  **Muss:** Sie wächst nicht um weitere Konfigurationsangaben (Basis-URLs, Vorhandensein von
  Keys, Concurrency-Werte), und sie darf einen Ersatzwert *nennen*, aber niemals *anwenden*.
- **S6** Keine Laufzeit-Zuweisung an `settings.landmark_model`/`.landmark_provider` in
  Produktivcode. Zusätzlich: **kein Fixture, kein Seed, kein Compose-Override, kein CI-Schritt
  setzt den entfallenen Wert**, sonst stirbt der jeweilige Stack beim Start.

### B. Der Modellwert erreicht den Anbieter weiterhin nur aus der kuratierten Registry

- **S7** Unverändert genau ein Weg: `Settings.resolved_landmark_model()` →
  Konstruktor-Parameter `model` der Clients → Feld `"model"` im Request-**Body**. Die
  Provider-URLs bleiben Modulkonstanten, der Wert landet nie in URL oder Pfad — **kein
  SSRF-Zuwachs**. **Muss:** Die neue Modell-ID taucht in
  `landmark.py`/`remote_classification.py`/`worker.py`/`api/` **nicht als Literal** auf; sie
  steht ausschließlich in `cloud_vision.py` und als Schlüssel in `pricing.py`.
- **S8** Der alte Preiseintrag muss **vollständig** verschwinden — die heutige Invariante ist
  eine Teilmengenprüfung und fängt einen stehengebliebenen Eintrag nicht. Er wäre keine akute
  Lücke (unerreichbar), aber eine alternde, unbeaufsichtigte Preisbehauptung mit
  `verified_on`-Stempel, die bei einer späteren Wiederaufnahme stillschweigend wieder gälte. Bei
  einer Wiederaufnahme wird `verified_on` **neu** verifiziert, nie aus dem Altbestand geerbt.

### C. Historische Läufe bleiben unverändert und verraten die heutige Konfiguration nicht

- **S9** `provider_for_vision_model("ministral-8b-2512")` liefert `None`, und das bleibt der
  Ausgang. Verboten sind alle drei naheliegenden „Verbesserungen": Rückfall auf
  `settings.landmark_provider`, eine Präfix-Heuristik (`ministral-*` → `mistral`), ein
  Nachschlagen in einer Alt-/Schattenregistry. Die Heuristik wäre fachlich richtig und
  sicherheitlich trotzdem falsch: eine Antwort über die Vergangenheit darf die heutige
  Betriebseinstellung nicht preisgeben (ADR 0068 Punkt 6).
- **S10** Dieser `None`-Zweig ist ab dieser Story **kein hypothetischer mehr**, sondern der
  reguläre Zustand jedes Altlaufs mit dem entfallenen Modell.
- **S11** Erfasste Ist-Kosten werden **nicht** nachgerechnet; sie sind eingefrorene Spalten,
  `compute_cost_usd()` läuft ausschließlich im Worker während des Laufs, `api/stats.py` summiert
  nur gespeicherte Spalten. **Muss:** kein neuer Lesepfad, der aus gespeicherten Tokens plus
  **heutiger** `MODEL_PRICING` einen Betrag rekonstruiert — er lieferte für Altläufe `None` und
  verwandelte eine erfasste Kostenangabe in „nicht erfasst".

### D. Die Kostenabsicherung bleibt wirksam

Die Schätzung ist seit Spec [`0296`](./0296-klassifizierung-ein-ausloeser-cloud-checkbox.md) die
einzige verbliebene Absicherung vor der kostenpflichtigen Aktion.

- **S12** Die Preisverifikation nach ADR 0059 Punkt 5 wird **nicht** von Spec 0304 geerbt:
  `source_url` und `verified_on` stehen für 0,15/0,60 **selbst** ein. Der Host-Allowlist-Test
  erlaubt `mistral.ai` und Subdomains — `docs.mistral.ai` erfüllt ihn, Ankündigungsblog und
  HuggingFace-Modellkarte sind als **Preis**quelle ausgeschlossen (sie taugen nur als
  Fähigkeitsbeleg, siehe E).
- **S13 Erstes asymmetrisch bepreistes Mistral-Modell.** Die Ausgabeseite ist durch
  `_MAX_RESPONSE_TOKENS = 256` in **beiden** Clients hart gedeckelt — höchstens $0,00015
  Ausgabekosten je Aufruf. Die Vervierfachung des Ausgabepreises kann den Betrag je Bild damit
  nicht davonlaufen lassen. **Muss:** Der Deckel bleibt; wer ihn anhebt, stellt diese Rechnung
  neu.
- **S14 Die Verbrauchsannahme wird erstmals über eine Modellfamiliengrenze hinweg geerbt.**
  `ASSUMED_USAGE_BY_PROVIDER` ist je Provider geführt und am Ministral-3-Tiling kalibriert;
  `mistral-small-2603` gehört einer anderen Familie an, die gefährliche Abweichungsrichtung ist
  die **Unter**schätzung. **Entscheidung: die Annahme wird nicht verändert** (K3 hängt daran).
  **Muss stattdessen:** der Kommentar hält fest, dass sie ab dieser Story zwei Modellfamilien
  desselben Anbieters abdeckt und für das neue Modell unkalibriert ist. Größenordnung: rund
  $0,0005 gegenüber ~$0,0003; selbst ein Faktor 2 bei den Bild-Tokens bliebe im Zehntelcent-
  Bereich je Bild. Auflösung bleibt der Abgleich der ersten realen Rechnung.
- **S15** `LANDMARK_MODEL` bleibt in `docker-compose.yml` an **beide** Backend-Dienste
  verdrahtet — nur der Worker ruft an, nur das Backend schätzt; sieht einer der beiden die
  Variable nicht, zeigt die Oberfläche einen anderen Preis als den, der bezahlt wird, ohne dass
  irgendetwas fehlschlägt.
- **S16 Doku-Muss:** Der entfallene Wert wird nicht stillschweigend aus der Tabelle gestrichen,
  sondern mit dem Umstellungshinweis versehen: *eine bestehende Konfiguration mit dem alten Wert
  lässt Backend und Worker beim Start scheitern — das ist beabsichtigt, der Wert ist neu zu
  wählen.* Ohne diesen Satz wirkt der Startfehler wie ein Defekt.

### E. Vision-Fähigkeit belegt, aber nicht auf der Fähigkeitsübersicht gelistet

Dokumentierte, tragbare **Integritäts**lücke, kein Blocker.

- **Der plausible Ausfall ist laut, nicht still.** Ein Modell ohne Bildunterstützung weist einen
  `image_url`-Content-Part mit 4xx zurück; `raise_for_vision_api_status()` macht daraus einen
  Fehler, der Aufruf zählt als `failed_calls` und ist in der Lauf-Bilanz sichtbar. Der Betreiber
  merkt es beim ersten Lauf, nicht erst auf der Rechnung.
- **Der stille Fall — Bild angenommen, aber nur der Prompt bewertet — ist strukturell nicht
  erkennbar.** Keine Antwortform unterscheidet ihn von einer echten Klassifizierung.
- **Schadenshöhe begrenzt, deshalb ohne Code-Gegenmaßnahme verhältnismäßig.**
  Klassifizierungsergebnisse sind Vorschläge in PhotoSorts eigener Datenbank. Der
  OpenCloud-Client hat ausschließlich lesende Operationen — es gibt **keinen Pfad, über den eine
  Fehlklassifizierung ein Familienfoto verschiebt, umbenennt oder löscht**. Ein Lauf ist
  wiederholbar, Kandidaten tragen `origin=remote` und ihre Konfidenz, die Lauf-Bilanz nennt das
  benutzte Modell. Der Schaden ist eine falsche Aussage über Fotos plus die Kosten dieses einen
  Laufs — keine Datenveränderung, kein Datenabfluss.
- **S17 Die angemessene Gegenmaßnahme ist Beleglage, nicht Code** (siehe „Vision-Fähigkeit" im
  Architektur-Abschnitt).
- **S18** `docs/setup.md` empfiehlt beim **erstmaligen** Umstellen auf ein nicht voreingestelltes
  Modell einen kleinen Probelauf mit Sichtprüfung einiger Ergebnisse, bevor der ganze Bestand
  klassifiziert wird. Eine automatisierte Kanarienvogel-Prüfung wäre unverhältnismäßig — sie
  kostet bei jedem Lauf Geld und erkennt den stillen Fall auch nur wahrscheinlich.
- **S19 Verschärfte Aufnahmeregel, ab dieser Story projektweit.** Ein wählbares Modell braucht
  **zwei** belegte Tatsachen, nicht eine: verifizierter Token-Preis (Quelle auf der
  Anbieterdomäne, testerzwungen) **und** belegte Vision-Fähigkeit, jeweils mit zitierter Quelle
  und Abrufdatum im Code. Steht die Fähigkeit nicht auf der Fähigkeitsübersicht des Anbieters,
  wird die Lücke am Eintrag vermerkt statt geglättet.

### Geprüft, kein Befund

- **Kein neuer Empfänger, kein neuer Einwilligungsbedarf.** Ein anderes Modell **desselben**
  Anbieters ist derselbe Empfänger unter denselben Vertragsbedingungen — der Consent-Zeitstempel
  wird nicht zurückgesetzt.
- **Datenumfang je Bild unverändert:** dieselbe `display`-Cache-Variante, derselbe Prompt.
- **Fehlerpfade unverändert:** weder API-Key noch Base64-Bilddaten in Meldung oder Log.
- **API-Vertrag:** `ClassificationEstimateOut.model` liefert eine andere Zeichenkette, keine
  zusätzliche Angabe; der Auth-Torwächter bleibt; `model` wird weiterhin als regulärer Textknoten
  gerendert.

### Bewusst akzeptierte Restrisiken

1. **Verfügbarkeit statt stillem Weiterlauf:** eine bestehende `.env` mit dem entfallenen Wert
   legt Backend und Worker beim Start still. Genau so gewollt (K6); in einer Minute behebbar.
   Bedingung: die wörtliche Einhaltung von S16.
2. **Unkalibrierte Verbrauchsannahme für die neue Modellfamilie** (S14), aufgelöst über den
   Rechnungsabgleich.
3. **Der stille „Bild ignoriert"-Fall** (E) — begrenzt durch den ausschließlich lesenden
   OpenCloud-Zugriff, die Wiederholbarkeit des Laufs und die pro Lauf ausgewiesene Modellangabe.

### Nachzuziehen am Sicherheitskonzept

Drei Ergänzungen am bestehenden Abschnitt „Modellwahl je Anbieter als Betriebseinstellung
`LANDMARK_MODEL`" in [`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md),
im selben PR: (a) die erste tatsächliche Modell-Entfernung und die damit erstmals produktiv
erreichbare `None`-Rückgabe von `provider_for_vision_model()`; (b) die verschärfte
Aufnahmeregel „zwei belegte Tatsachen je wählbarem Modell" (S19); (c) die Grenze der
providerweit geführten Verbrauchsannahme, sobald ein Anbieter zwei Modellfamilien in der
Auswahl hat.

## Teststrategie

Vollständig auf **Backend-Unit-Ebene**, ergänzt um einen Integrationstest auf API-Ebene für K7.
Kein Frontend-Test, kein E2E-Fall — es gibt kein UI-Feld, keine sichtbare Änderung, keine neue
Route. Kein neuer Produktionscode, das Coverage-Gate (≥ 80 %) ist unberührt.

Die konkrete Testliste steht im Architektur-Abschnitt bei den betroffenen Dateien. Die tragende
Einsicht dahinter: **Bei einer Rücknahme werden Teilmengen-Invarianten zur Mengengleichheit.**
`⊆` sichert die Aufnahme, `==` sichert die Rücknahme — sonst bleiben Karteileichen in jeder
abhängigen Tabelle und in der Betriebsdoku dauerhaft grün stehen. Das betrifft hier drei
Stellen: `MODEL_PRICING`, das Registry-Tupel und die beiden Betriebsdoku-Dateien.

Die drei Edge Cases, die ohne die neuen Tests durchrutschen würden:

- **drei statt zwei Mistral-Modelle** — alle bestehenden Registry-Tests prüfen `>= 2`;
- **vertauschtes oder symmetrisch übernommenes Preispaar** — der Ordnungstest („stärker ⇒
  teurer") bleibt bei allen Fehlvarianten grün, weil auch $0,00045 und $0,0017 über $0,0003
  liegen;
- **veraltete Doku-Zeile** — der heutige Test prüft nur Anwesenheit, `docs/setup.md` gar nicht.

**Nicht automatisierbar** (bekannte Grenze, unverändert aus ADR 0059): die inhaltliche
Richtigkeit der Preiswerte gegen echte Anbieter-Abrechnungen. Ersatzverfahren bleibt der
Abgleich der ersten realen Rechnung mit den Ist-Kosten auf der Statistikseite. Ebenso nicht
testbar: ob die Preisquelle zum Zeitpunkt der Umsetzung erreichbar ist — gelingt die
Verifikation nicht, bricht die Story ab (K4), statt einen geschätzten Preis zu übernehmen.

**Review-Punkt ohne Test:** dass die Konstante mit dem Wert auch ihren Namen wechselt
(`…_8B` → `…_SMALL`) lässt sich nicht sinnvoll testen und gehört in das `review-tests`-Review.

## Offene Fragen

Keine. Die einzige Produktentscheidung — das Modell trotz fehlender Listung auf der
Fähigkeitsseite aufnehmen und die Lücke offen dokumentieren — hat Daniel am 2026-09-09
getroffen (siehe Architektur-Abschnitt).

## Out of Scope

- Modelle ohne Code-Änderung frei konfigurierbar machen — die Auswahl bleibt ausdrücklich
  kuratiert und geprüft.
- Ein Wechsel der Voreinstellung, eines Anbieters oder der Anthropic-Modellauswahl.
- Eine allgemeine Regel dafür, wie Modelle künftig abgekündigt und entfernt werden. Dies ist der
  erste Entfernungsfall; eine allgemeine Festlegung wäre eine eigene Story.
- **Eine über den Registry-Fall hinausgehende Testkonvention für Rücknahmen.** Die vier hier
  angewendeten Muster (Teilmenge → Mengengleichheit, zweiseitige Doku-Tests, abgeleitet statt
  abgeschrieben geprüfte Beträge, Literal-Pin bei erstmals asymmetrischen Zahlenpaaren) werden
  **in diesem PR** in [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md)
  festgeschrieben — allerdings ausschließlich an der bestehenden ADR-0059-Sektion (Punkt 11),
  also für Registry-gebundene Betriebseinstellungen. Draußen bleibt ihre Verallgemeinerung auf
  beliebige zurückgenommene Werte (Kategorien, Kriterien, Feldwerte einer Enumeration) — das
  wäre eine eigene Story, ebenso wie der Abkündigungs-*Prozess* aus dem vorstehenden Punkt.
- Eine Änderung an `formatUsd` oder der Betragsdarstellung im Frontend (siehe UI/UX).
- Eine Verbrauchsannahme je Modell statt je Anbieter (siehe „Bekannte Grenze").
