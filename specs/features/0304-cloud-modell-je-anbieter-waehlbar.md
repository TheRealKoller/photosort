# 0304 - Cloud-Modell je Anbieter wählbar machen (statt fest verdrahtet)

**Status:** Implemented ([PR #341](https://github.com/TheRealKoller/photosort/pull/341))
**Erstellt:** 2026-09-06
**Bezug:** [Issue #304](https://github.com/TheRealKoller/photosort/issues/304)

## Ziel

Welches Cloud-Modell PhotoSort für die Bilderkennung nutzt, steht heute je Anbieter fest im Code.
Ein Modellwechsel — auch ein probeweiser — verlangt deshalb eine Codeänderung und ein Release, und
er lässt sich nicht ohne weiteres zurücknehmen, wenn das neue Modell schlechter arbeitet.

Der wichtigere Teil ist aber eine Lücke, die davon unabhängig schon heute besteht: Die vor dem
Start angezeigte Kostenschätzung ist an den **Anbieter** gebunden, nicht an das tatsächlich
genutzte Modell. Die Ist-Kosten nach einem Lauf sind es dagegen sehr wohl. Seit dem Wegfall des
Bestätigungsdialogs (Spec [`0296`](./0296-klassifizierung-ein-ausloeser-cloud-checkbox.md)) ist
diese Schätzung die einzige verbliebene Absicherung gegen ungewollte Cloud-Kosten — ein
Modellwechsel gleich welcher Art macht sie unbemerkt falsch, ohne dass irgendwo etwas fehlschlägt.

Ziel ist deshalb zweierlei: die Modellwahl je Anbieter zu einer Betriebseinstellung machen — so wie
die Anbieterwahl es bereits ist — und die Kostenschätzung so an das tatsächlich genutzte Modell
binden, dass sie einen Modellwechsel nicht überleben kann, ohne ihn abzubilden.

**Bewusst nicht enthalten ist die Frage, welches Modell das bessere ist.** Diese Spec legt keine
andere Voreinstellung fest; sie macht den Wechsel und seine Rücknahme möglich und hält die
Kostenanzeige dabei ehrlich.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich das für die Bilderkennung genutzte Modell je
Anbieter aus einer gepflegten Auswahl über eine Betriebseinstellung wählen können und dabei eine
Kostenschätzung sehen, die zum eingestellten Modell passt, damit ich einen Modellwechsel an meinen
eigenen Fotos erproben und jederzeit zurücknehmen kann, ohne dafür ein Release zu brauchen — und
ohne dabei die Absicherung gegen ungewollte Cloud-Kosten zu verlieren.

## Akzeptanzkriterien

**Modellwahl als Betriebseinstellung**

- [x] Das für die Bilderkennung genutzte Modell ist je Anbieter als Betriebseinstellung wählbar —
      genauso, wie die Anbieterwahl selbst heute schon eine Betriebseinstellung ist.
- [x] Wählbar sind ausschließlich Modelle aus einer im Produkt gepflegten, geprüften Auswahl je
      Anbieter. Ein Wert außerhalb dieser Auswahl führt zu einer verständlichen Fehlermeldung beim
      Start; die Anwendung startet dann nicht, statt mitten in einem laufenden Durchgang still
      fehlzuschlagen.
- [x] Nach der Umsetzung stehen für mindestens einen Anbieter tatsächlich mindestens zwei Modelle
      zur Auswahl — darunter das stärkere Mistral-Modell, das den Anlass dieser Story bildet.
- [x] Beide Anbieter werden gleich behandelt; es entsteht kein Sonderweg für nur einen von beiden.
- [x] Ohne gesetzte Einstellung verhält sich die Installation exakt wie bisher — dieselben Modelle,
      dieselben Kosten, keine stillschweigende Änderung durch das Update allein.
- [x] Die Einstellung wirkt auf beide Cloud-Anteile (Kategorie-Vorschläge und
      Sehenswürdigkeits-Erkennung) einheitlich; es entstehen nicht zwei unterschiedliche Modelle
      nebeneinander.
- [x] Ein Wechsel ist ohne Datenverlust rücknehmbar: Zurückstellen auf das vorherige Modell stellt
      das vorherige Verhalten wieder her.

**Kostenschätzung bleibt wahrheitsgemäß**

- [x] Die vor dem Start angezeigte Kostenschätzung passt zum tatsächlich eingestellten Modell. Sie
      darf nicht weiter einen Preis anzeigen, der nur für ein anderes Modell galt.
- [x] Für jedes wählbare Modell ist ein Preis hinterlegt, der vor dem Festschreiben gegen die
      offizielle Anbieterdokumentation verifiziert wurde — mit Datum der Prüfung, wie bei den
      bestehenden Preisangaben.
- [x] Liegt für ein eingestelltes Modell dennoch kein Preis vor, wird das an der Kostenschätzung
      erkennbar gemacht, statt einen falschen Betrag auszuweisen.
- [x] Ein künftiger Modellwechsel kann die Schätzung nicht unbemerkt falsch werden lassen: Ein
      Modell ohne gepflegten Preis fällt auf, statt still den alten Betrag weiterzuzeigen.

**Betrieb bleibt nachvollziehbar**

- [x] Aus welchem Modell ein durchgeführter Lauf entstanden ist, bleibt nachträglich erkennbar — ein
      Vergleich zweier Modelle wäre sonst nicht auswertbar.
- [x] Die neue Einstellung ist dort dokumentiert, wo die bestehenden Betriebseinstellungen
      dokumentiert sind, samt Voreinstellung und wählbaren Werten.

## Datenmodell-Bezug

Zwei additive, nullable Spalten (Migration `a7b8c9d0e1f2`), siehe
[`docs/architecture.md`](../../docs/architecture.md):

| Tabelle | Spalte | Bedeutung |
|---|---|---|
| `criterion_scoring_runs` | `landmark_model: str \| None` | Modell-ID der Landmark-Phase dieses Laufs. Präfix wie bei `landmark_cost_usd`. |
| `remote_category_classification_runs` | `model: str \| None` | Modell-ID dieses Laufs. Kein Präfix — ein Lauf, ein Zweck. |

`NULL` heißt „nicht erfasst" (Zeile aus der Zeit vor der Migration), nicht „kein Modell" — exakt
das `ScanRun.total_files`-Idiom aus ADR 0051 Punkt 3. Bewusst **kein** Server-Default mit dem
damaligen Voreinstellungs-Modell: das wäre eine Behauptung über die Vergangenheit, die die
Migration nicht belegen kann, und sie wäre unumkehrbar.

Keine Änderung an bestehenden Spalten, keine Datenmigration. Die `provider`-Spalten der
Foto-Zeilen (`PhotoLandmarkDetection`, `PhotoCategoryClassification`, `PhotoFineLabel`) bleiben
unverändert — sie beantworten eine andere Frage (welchem Anbieter wurde dieses Bild übermittelt,
eine Datenschutz- statt einer Kostenfrage).

## Architektur / Umsetzung

Umgesetzt gemäß ADR
[`0059`](../decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md) —
dort stehen die Begründungen, hier steht, was zu tun ist. Die ADR ist eine **Teil-Ablösung von
ADR 0051 Punkt 2** (die Festlegung „zwei Preiskonstanten nebeneinander, nicht auseinander
abgeleitet" fällt); alle übrigen Punkte von ADR 0051 bleiben in Kraft.

**Ansatz in einem Satz:** Eine kuratierte Registry wählbarer Modelle je Anbieter in
`cloud_vision.py` wird über eine zweite Betriebseinstellung (`LANDMARK_MODEL`, leer =
Anbieter-Voreinstellung) beim Prozessstart validiert; die Vorab-Schätzung hört auf, eine eigene
Preiskonstante je Provider zu führen, und wird stattdessen aus derselben modell-geschlüsselten
Preistabelle abgeleitet, die schon die Ist-Kosten trägt.

### Die vier tragenden Entwurfsentscheidungen

1. **`COST_PER_IMAGE_USD` entfällt, statt auf Modell-Schlüssel umgestellt zu werden.** Ein
   Umschlüsseln verlangte für jedes neue Modell *zwei* handgepflegte Zahlen, deren
   Übereinstimmung nichts prüft — genau die Bauform, die den Defekt erzeugt hat. Die Schätzung
   wird `compute_cost_usd(model, angenommener_verbrauch)`: ein neues Modell braucht genau eine
   gepflegte Tatsache (seine verifizierten Token-Preise), die Schätzung folgt zwangsläufig. Die
   Verbrauchsannahme steht offen als `ASSUMED_USAGE_BY_PROVIDER` und ist so kalibriert, dass die
   Voreinstellungs-Modelle die heutigen Werte **exakt** reproduzieren (anthropic 4 600/120 →
   $0,0052; mistral 2 880/120 → $0,0003). Das macht „ohne gesetzte Einstellung exakt wie bisher"
   zu einer Testaussage.
2. **Preisverifikation wird strukturell.** `ModelPricing` bekommt die Pflichtfelder
   `source_url: str` und `verified_on: date`; ein Eintrag ohne sie ist nicht konstruierbar. Ein
   Modell ohne gegen die offizielle Anbieterdoku verifizierten Preis kommt **nicht** in die
   Registry — ein wählbares Modell ohne Preis wäre ein wählbarer Zustand ohne Kostenabsicherung.
3. **Das benutzte Modell wird je Lauf persistiert, nicht je Foto.** Ausschlaggebend: eine
   Foto-Zeile entsteht nur bei einem *Treffer* (`_upsert_landmark_detection` läuft nur bei
   erkanntem Namen). Ein Lauf, der 500 Aufrufe bezahlt und nichts erkennt, hinterließe dort keine
   Spur des Modells. Außerdem gehört das Modell als Preisgrundlage neben den eingefrorenen Betrag
   und die Tokens, deren Aufbewahrung ADR 0051 Punkt 3 aus demselben Grund begründet.
4. **Eine Modellauflösung je Phase, durchgereicht.** Der Worker liest
   `settings.resolved_landmark_model()` einmal vor der Foto-Schleife und benutzt denselben
   lokalen Wert für Client-Bau, Kostenrechnung und Modellspalte. Dadurch ist „angezeigt =
   abgerechnet = tatsächlich aufgerufen" strukturell wahr statt durch drei zufällig gleiche
   Lesevorgänge derselben globalen `settings`. Die vier Client-Konstruktoren und beide Factories
   bekommen `model` als **Pflichtparameter ohne Default** (Fund `test-engineer`): ein Default auf
   die Modulkonstante stellte die aufgelöste Kopplung wieder her, und ein vergessener Aufrufer
   fiele nicht beim Typecheck auf, sondern erst in der Cloud-Rechnung.

### Betroffene Dateien

**Backend (`backend/src/photosort/`)**

| Datei | Änderung |
|---|---|
| `cloud_vision.py` | `VISION_MODELS_BY_PROVIDER: dict[str, tuple[str, ...]]` (erstes Element = Voreinstellung), `default_vision_model_for_provider()` ersetzt `VISION_MODEL_BY_PROVIDER`/`vision_model_for_provider` (defensive Rückfallregel wörtlich erhalten). Modulkopf-Vermerk: **darf `photosort.config` nie importieren** (die Abhängigkeit läuft jetzt andersherum). |
| `config.py` | Feld `landmark_model: str = ""`, Methode `resolved_landmark_model()`, `@field_validator("landmark_model")` gegen die Registry **des eingestellten Providers**, Fehlermeldung nennt die erlaubten Werte. |
| `pricing.py` | `ModelPricing` + `source_url`/`verified_on`; `MODEL_PRICING` um `claude-sonnet-5` ergänzt; neu `AssumedImageUsage`, `ASSUMED_USAGE_BY_PROVIDER`, `estimate_usd_per_image(model, provider) -> float \| None`. Die Herleitungs-Dokumentation aus `remote_classification.py` wandert hierher. |
| `remote_classification.py` | `COST_PER_IMAGE_USD` und die beiden `*_CATEGORY_MODEL`-Aliase gelöscht; beide Clients bekommen `model` im Konstruktor; `build_category_classification_client(model)`. |
| `landmark.py` | dieselbe Änderung für beide Landmark-Clients und `build_landmark_client(model)`; `*_LANDMARK_MODEL`-Aliase gelöscht. |
| `worker.py` | je Cloud-Phase eine lokale `model`-Variable; injizierte Factory-Parameter werden `Callable[[str], ...]`, `_try_build(lambda: build_...(model))`; im bestehenden `finally` zusätzlich `run.landmark_model = model` bzw. `run.model = model`. |
| `models.py` | `CriterionScoringRun.landmark_model`, `RemoteCategoryClassificationRun.model`, beide nullable, Default `None`. |
| `api/projects.py` | `estimate_classification` löst das Modell auf und ruft `estimate_usd_per_image`; `ClassificationEstimateOut`: `price_per_image_usd: float \| None`, `estimated_cost_usd: float \| None`, neues Feld `model: str` (**nicht** `model_id` — pydantic v2 schützt den Namensraum `model_`). |
| `alembic/versions/a7b8c9d0e1f2_run_vision_model.py` | eine Revision auf Head `f4a5b6c7d8e9`, zwei additive nullable Spalten. |

**Frontend (`frontend/src/`)**

| Datei | Änderung |
|---|---|
| `api/types.ts` | `ClassificationEstimateOut`: beide Beträge `number \| null`, neu `model: string`. |
| `components/ClassificationSection.tsx` | dritter Zweig an der bestehenden `data-testid="classification-estimate"`-Stelle (siehe UI/UX). |

**Konfiguration/Doku (im selben PR):** `.env.example`, `docker-compose.yml` (beide Backend-Dienste),
`docs/setup.md`, `docs/architecture.md`, `.github/workflows/ci.yml` (Passthrough-Prüfung).

### Bewusst nicht Teil der Umsetzung

Keine Modellanzeige in der Oberfläche/Statistikseite (die Lauf-Spalten sind
Betreiber-Nachvollziehbarkeit, kein Anwender-Lesepfad — dieselbe eng begrenzte Ausnahme, die
ADR 0051 Punkt 3 für Tokens getroffen hat). Keine Blockade des Startknopfes bei unbekanntem
Preis. Keine automatische Verfallsprüfung der Preisangaben. Keine Umbenennung von
`LANDMARK_PROVIDER` (breaking für den laufenden Betrieb, sachfremd für diese Story).

## UI/UX

Sichtbare Oberfläche vorhanden, aber nur an **einer** Stelle: die Modellwahl selbst bekommt
ausdrücklich kein Bedienelement (Out of Scope), sichtbar wird allein die Kostenschätzung.

**Änderung:** `frontend/src/components/ClassificationSection.tsx`, an der bestehenden Stelle mit
`data-testid="classification-estimate"`. Dort gibt es heute zwei Zweige (`candidate_count === 0`
→ „Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten."; sonst der Betrag). Es
kommt ein dritter für `estimated_cost_usd === null` dazu:

> „~N Fotos · Keine Kostenangabe verfügbar. Dieser Durchlauf wird mit Cloud-Erkennung Kosten
> erzeugen."

**Begründung der Wortwahl:** „Keine Kostenangabe verfügbar" ist sachlich und klarer als „konnte
nicht geladen werden" — letzteres klänge nach Fehler, hier liegt aber kein Ladefehler vor,
sondern eine ehrliche Wissenslücke. „wird … Kosten erzeugen" macht die Tatsache explizit, ohne
zu dramatisieren. Die Kandidatenzahl bleibt vorangestellt: sie ist bekannt und für die
Freigabeentscheidung die wichtigere Zahl.

**Die Modell-ID wird im Hinweis NICHT genannt** (Entscheidung `ux-ui-designer`): sie ist eine
Betriebseinstellung, die der Betreiber selbst gesetzt hat, und für den Anwender ist eine
technische Kennung wie `claude-haiku-4-5` kein Mehrwert. Über die API ist sie als
`estimate.model` verfügbar, falls das später doch gebraucht wird.

**Visuelle Behandlung:** reiner Textknoten, `className="text-sm text-text"` wie die beiden
anderen Zweige — bewusst **kein** `Alert`: der ist im Projekt der Fehler-/Retry-Baustein. Der
Startknopf bleibt bedienbar; die bestehende Sperre hängt an der nicht *geladenen* Schätzung
(Ladefehler), nicht am fehlenden Betrag. Der Datenschutz-Absatz darüber bleibt unverändert — er
hängt allein am `cloudChecked`-Zustand.

**Zustandsabdeckung an dieser Stelle:**

| Fall | Anzeige |
|---|---|
| Cloud-Checkbox abgewählt | nicht sichtbar |
| angewählt, lädt | nicht sichtbar |
| angewählt, Ladefehler | `Alert` „Kostenschätzung konnte nicht geladen werden." + Startknopf gesperrt |
| `candidate_count === 0` | „Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten." |
| Kandidaten vorhanden, Preis bekannt | „~N Fotos · ~$X — Schätzung, keine exakte Abrechnung." |
| Kandidaten vorhanden, **Preis nicht hinterlegt** | der neue Hinweis oben |

Die Zweigreihenfolge ist verbindlich: `candidate_count === 0` gewinnt gegen den
Preis-Hinweis — sonst stünde „kein Preis hinterlegt", obwohl gar nichts zu bezahlen wäre.

## Security

**Sicherheitsrelevant** (Konsultation `security-engineer`, 2026-09-06; projektweite Einordnung
in [`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md)). Keine neue
Angriffsflächen-*Klasse*: derselbe Empfänger, derselbe Datenumfang pro Bild, derselbe
Consent-Bezug, kein neues Secret, kein neuer Endpunkt. Neu sind ein Betreiber-gesetzter Wert, der
im Feld `"model"` an einen externen Anbieter geht, und der Umbau der Schätzung, die seit Spec 0296
die **einzige verbliebene Absicherung** vor der kostenpflichtigen Aktion ist.

### Muss-Kriterien

**Kein unvalidierter Modellwert erreicht je einen Anbieter (fail-closed):**

- **S1** Der an einen Client übergebene Modellwert stammt ausschließlich aus
  `Settings.resolved_landmark_model()` — nie aus Request-Body, Query-Parameter, Job-Payload oder
  einer DB-Spalte (auch nicht aus der neuen Modellspalte eines früheren Laufs). Kein
  `os.environ`-Direktzugriff auf `LANDMARK_MODEL`.
- **S2** Der Vergleich gegen die Registry ist ein exakter Stringvergleich: kein `strip()`, kein
  `lower()`, kein Normalisieren. Ein toleriertes `" claude-haiku-4-5 "` wäre sonst ein validierter
  Wert, der so in keiner Registry steht.
- **S3** Geprüft wird gegen die Registry **des eingestellten Anbieters**; ein für `anthropic`
  gültiges Modell unter `mistral` ist ein Startfehler.
- **S4** Kein Produktivcode weist `landmark_model`/`landmark_provider` zur Laufzeit zu
  (`validate_assignment` ist aus — eine Zuweisung umginge den Validator); Monkeypatching bleibt
  auf Tests beschränkt.
- **S5** Der Invariantentest hält Registry-Schlüssel, `typing.get_args(...)` von
  `landmark_provider` und `MODEL_PRICING` deckungsgleich. Er hält die defensive Rückfallregel in
  `default_vision_model_for_provider()` unerreichbar.
- **S6** Der Modellwert landet im Request-**Body**, nie in URL/Pfad; die Provider-URLs bleiben
  feste Modulkonstanten. Kein SSRF-Zuwachs.

**Die Startvalidierung darf keine Secrets preisgeben** (Befund am Branch nachgemessen):

- **S7** Ein `@model_validator(mode="after")` hängt bei einem `ValueError` das **vollständige
  Settings-Dict** als Fehler-Eingabe an die `ValidationError` — `SECRET_KEY`,
  `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY` und `OPENCLOUD_APP_TOKEN` landen damit im
  Startup-Traceback (`docker compose logs`) und in `exc.errors()`/`exc.json()`. Verstößt direkt
  gegen den `CLAUDE.md`-Grundsatz „keine Secrets in Logs oder Fehlermeldungen". Umgesetzt ist
  deshalb ein `@field_validator("landmark_model")` — die Fehler-Eingabe ist dann nur der
  beanstandete Modellwert. `landmark_model` ist hinter `landmark_provider` deklariert, der
  Anbieter steht also in `info.data`.
- **S8** Ein Test setzt Marker-Werte für `SECRET_KEY`, beide Cloud-Keys und das OpenCloud-Token
  plus einen ungültigen `LANDMARK_MODEL` und prüft, dass keiner davon in `str(exc)` **und** in
  `exc.errors()`/`exc.json()` vorkommt. Ein Test nur gegen `str(exc)` genügt nicht — die Kürzung
  dort verdeckt das Problem teilweise.
- Ausdrücklich erlaubt: der beanstandete Wert, der eingestellte Anbieter und die zulässigen Werte.
  Modell-IDs sind keine Geheimnisse, und die Meldung soll handlungsfähig machen.

**Die Kostenabsicherung bleibt wirksam:**

- **S9** `null` schlägt unverfälscht bis in die Anzeige durch: kein `?? 0`, `|| 0`, `or 0.0`,
  keine Default-Koerzierung im API-Modell. Ein stilles „0,00 $" wäre die gefährlichste aller
  Anzeigen — es behauptete Kostenfreiheit.
- **S10** Die Oberfläche zeigt an der Stelle, an der sonst der Betrag steht, einen ausdrücklichen
  Hinweis — nicht Leerraum, nicht „—".
- **S11** Der Invariantentest „jedes Modell der Registry hat einen Preis" läuft in CI; er ist die
  erste Verteidigungslinie, die den `null`-Pfad unerreichbar hält.
- **S12** „Angezeigt = abgerechnet = tatsächlich aufgerufen" ist strukturell wahr: eine Auflösung
  je Cloud-Phase, durchgereicht (ADR 0059 Punkt 7). Prüfbar über eine gefälschte Factory plus
  `httpx.MockTransport` auf das `"model"`-Feld.
- **S13** `LANDMARK_MODEL` ist in `docker-compose.yml` an **beide** Backend-Dienste verdrahtet
  (Backend *und* Worker). Nur der Worker ruft an, nur das Backend schätzt: sieht einer der beiden
  die Variable nicht, zeigt die Oberfläche einen anderen Preis als den, der bezahlt wird — ohne
  dass irgendetwas fehlschlägt. Statisch in CI geprüft.
- **S14** Ein wählbares Modell ohne gegen die **offizielle** Anbieterdokumentation verifizierten
  Preis kommt nicht in die Registry (kein Websuch-Aggregat, kein Analogieschluss innerhalb einer
  Modellfamilie). Nichtverifizierbarkeit ist ein Blocker und eine Rückfrage an Daniel.
- **S15** `.env.example`/`docs/setup.md` nennen die wählbaren Werte je Anbieter **mit** Hinweis
  auf die Kostenwirkung: die Kostenobergrenze eines Laufs ist erstmals nach oben verstellbar, bei
  unverändert unbegrenzter Kandidatenzahl.

**Geprüft, kein Befund:**

- Die Modell-ID über `GET /projects/{id}/classify/estimate`: der Endpunkt hängt am
  router-weiten Auth-Guard, die Angabe ist eine öffentliche Herstellerbezeichnung, deren Auswahl
  ohnehin im öffentlichen Repository steht. **S16** Der Torwächter bleibt; der Endpunkt antwortet
  weiterhin bewusst auch ohne Consent mit `200` und ohne jede Bilddaten. **S17** Die Antwort
  wächst um genau dieses eine Feld — keine weiteren Konfigurationsangaben; `model` wird im
  Frontend als regulärer Textknoten gerendert.
- Die beiden neuen Lauf-Spalten: die Zusammenfassungs-Schemata führen ihre Felder explizit auf,
  eine additive Spalte wird nicht automatisch ausgeliefert. **S18** Diese Feldlisten bleiben
  explizit. **S19** Der persistierte Modellwert stammt aus demselben lokalen Wert wie der
  eingefrorene Betrag und wird im selben Commit geschrieben.

**Unverändert:** kein neues Secret; die bestehenden Muss-Kriterien für Fehlerpfade (weder API-Key
noch Base64-Bilddaten in Meldung/Log) gelten fort. Ein anderes Modell **desselben** Anbieters ist
derselbe Empfänger unter denselben Vertragsbedingungen — kein neuer Einwilligungsbedarf,
konsistent mit der für Spec 0217 getroffenen Entscheidung.

**Bewusst akzeptiertes Restrisiko:** der Start wird bei unbekanntem Preis nicht blockiert
(ADR 0059 Punkt 4) — eine Blockade bestrafte den Betreiber für einen Zustand, den er an der
Oberfläche nicht auflösen kann. Bedingung ist die wörtliche Einhaltung von S10.

## Teststrategie

Die Story hat drei Risikokerne auf drei Ebenen: die *Gültigkeitsregel* (Unit, `Settings`), die
*Zahl* (Unit `pricing.py` + API), und die *Identität von angezeigtem, abgerechnetem und
tatsächlich aufgerufenem Modell* (Integration, Worker). Keiner ist auf einer anderen Ebene
ersatzweise prüfbar. Frontend nur für den neuen Anzeigezweig; **keine neue E2E-Spec** (der
`null`-Pfad ist bei grünem Invariantentest in einer korrekt konfigurierten Instanz unerreichbar).

**Registry** (`test_cloud_vision.py`): jeder konfigurierbare Anbieter hat mindestens ein Modell;
geordnete, unveränderliche Tupel; keine Modell-ID unter zwei Anbietern; mindestens ein Anbieter
mit mindestens zwei Modellen; die Voreinstellungen gegen die **ausgeschriebenen** IDs
(`"claude-haiku-4-5"`/`"ministral-3b-2512"`) statt gegen die Konstanten — ein Vergleich mit der
Konstante wäre tautologisch und bliebe grün, wenn jemand ihren *Wert* ändert; Rückfallregel für
einen unbekannten Anbieter. Dazu (Nachtrag 2026-09-06) drei Fälle für das nachgereichte stärkere
Mistral-Modell: es ist wählbar (wieder gegen die ausgeschriebene ID `"ministral-8b-2512"`, aus
demselben Grund), es ist *nicht* die Voreinstellung, und **beide** Anbieter bieten mindestens zwei
Modelle — letzteres die schärfere Fassung des Akzeptanzkriteriums „kein Sonderweg für nur einen
von beiden".

**Startvalidierung** (`test_config.py`, alle Fälle über den Konstruktor, **nie** per Monkeypatch —
der umgeht den Validator): Voreinstellung je Anbieter; gesetzter Wert wörtlich übernommen;
Ablehnung außerhalb der Auswahl; die Meldung nennt Feldname, Anbieter und erlaubte Werte;
Ablehnung eines Modells des jeweils anderen Anbieters **in beiden Richtungen** (ursprünglich, weil
die Registry asymmetrisch war und eine Implementierung mit Sonderbehandlung des Ein-Modell-
Anbieters nur eine Richtung bestanden hätte; seit dem Nachtrag vom 2026-09-06 ist sie symmetrisch,
der Fall bleibt aber als Schutz gegen eine anbieterblinde Prüfung über die Gesamtmenge aller
Modelle); ein mit Leerzeichen gepolsterter Wert wird abgelehnt statt getrimmt; ungültiger
Anbieter *plus* gesetztes Modell ergibt `ValidationError`, keinen `KeyError`; jedes Registry-Modell
ist tatsächlich einstellbar (über die Registry parametrisiert, damit ein später ergänztes Modell
automatisch mitgeprüft wird); der Wert wird unter dem **Variablennamen** `LANDMARK_MODEL` aus der
Umgebung gelesen; die Ablehnung leakt kein anderes Settings-Feld (S8); `.env.example` nennt jedes
wählbare Modell.

**Preis und Schätzung** (`test_pricing.py`): Registry ⊆ `MODEL_PRICING`; Provider-Schlüssel von
Registry und `ASSUMED_USAGE_BY_PROVIDER` == `get_args` des `landmark_provider`-`Literal` (per
Introspektion, nicht gegen eine abgeschriebene Liste); alle Preise positiv; `ModelPricing` frozen;
jeder Eintrag hat `source_url`/`verified_on`, `verified_on` nicht in der Zukunft; **jede
`source_url` zeigt per `https` auf die offizielle Domain ihres Anbieters** (Host-Erlaubnisliste —
der einzige automatisierbare Teil von „kein Websuch-Aggregat"); Verbrauchsannahme in beiden
Richtungen positiv. Schätzung: die Voreinstellungs-Modelle reproduzieren die **literalen** Altwerte
`0.0052`/`0.0003` (`abs=1e-9`, damit die Assertion an einer fachlichen Änderung scheitert und nicht
an Float-Rauschen); Mistral bleibt der günstigere Anbieter; ein stärkeres Modell desselben
Anbieters wird höher geschätzt (der eigentliche Defektnachweis — providergebunden wären beide Werte
gleich), seit dem Nachtrag vom 2026-09-06 für **beide** Anbieter je einmal; die Schätzung ist exakt `compute_cost_usd` über der Annahme; ein nicht bepreistes Modell
und ein unbekannter Anbieter liefern `None` statt `0`; jedes wählbare Modell liefert einen Betrag.

**Clients** (`test_landmark.py`, `test_remote_classification.py`): je Client prüft ein
`httpx.MockTransport`-Fall, dass das im Konstruktor übergebene Modell im `"model"`-Feld des
Request-Bodys landet — mit einem **Sentinel** statt der Produktivkonstante, sonst wäre die
Assertion bei einem Client, der die Modulkonstante hartkodiert, tautologisch grün. Alle übrigen
Client-Tests (Fehlerfälle, Header, Timeout, `aclose`, Secret-Freiheit) bleiben ohne
Assertion-Anpassung grün.

**Worker** (`test_worker_criterion_scoring.py`, `test_worker_remote_category_classification.py`),
alle mit einem **nicht voreingestellten** Modell — bei der Voreinstellung stimmten alle drei
Stellen auch dann überein, wenn drei getrennte Lesevorgänge stattfänden: die Factory bekommt das
eingestellte Modell; Client-Bau, eingefrorener Betrag und Modellspalte sind **ein und derselbe
Wert** (mit Gegenprobe, dass der Betrag mit dem Voreinstellungs-Modell ein anderer wäre); ein Lauf
ohne Cloud-Phase lässt die Spalte `NULL`; ein Lauf, der nach der Cloud-Phase scheitert, hat die
Spalte trotzdem gefüllt; ein früherer Lauf behält sein Modell, wenn ein späterer ein anderes nutzt
(„rücknehmbar ohne Datenverlust"); ohne gesetzte Einstellung steht das unveränderte
Voreinstellungs-Modell in der Spalte.

**Persistenz** (`test_migration_run_vision_model.py`, Muster der bestehenden `test_migration_*.py`):
Revision kettet auf `f4a5b6c7d8e9`; beide Spalten werden angelegt; beide sind nullable;
Bestandszeilen behalten `NULL` statt eines Default-Modells; `downgrade` entfernt beide wieder und
lässt die Kostenspalten unberührt.

**API** (`test_api_classification_estimate.py`): die Schätzung nennt das Modell, auf das sie sich
bezieht; der Voreinstellungsfall pinnt auf der API-Ebene den **literalen** Altwert `0.0052` (ohne
diesen Anker prüfte die API-Ebene nach dem Umbau nur noch sich selbst); ein eingestelltes
Nicht-Voreinstellungs-Modell ändert den Preis; ein nicht bepreistes Modell liefert `200` mit
`null`-Beträgen und korrekter Kandidatenzahl (per Monkeypatch-Bypass erzeugt, weil der Zustand per
Konfiguration unerreichbar ist — der Pfad wird trotzdem gebaut, weil eine Absicherung, die nur aus
einem Test besteht, mit diesem Test verschwindet); null Kandidaten ergeben weiterhin `0.0`, nicht
`null` („nichts zu bezahlen" ≠ „unbekannt").

**Frontend** (`ClassificationSection.test.tsx`): der Hinweis erscheint statt eines Betrags, die
Kandidatenzahl bleibt sichtbar, und der Knoten enthält weder `$`/`USD` noch `NaN`/`undefined`; der
Startknopf bleibt bedienbar (Regressionsschutz — ein Guard auf `estimated_cost_usd === null`
machte das Produkt bei einem reinen Preispflege-Versäumnis unbenutzbar); bei null Kandidaten
gewinnt die „alles klassifiziert"-Meldung gegen den Preis-Hinweis. Die bestehenden Betragstests
bleiben unverändert grün.

**Betrieb:** der bestehende statische CI-Schritt „LANDMARK_PROVIDER/MISTRAL_API_KEY passthrough
(Spec 0057)" wird um `LANDMARK_MODEL` erweitert, für **beide** Dienste, Default- und
Override-Fall. Ohne das wäre die Story im Docker-Betrieb wirkungslos, und es fiele in keinem
Unit-Test auf.

**Der Wächtertest `test_the_category_phase_models_are_still_aliases_of_the_vision_models`
entfällt** — er bewachte die Gleichheit zweier getrennt geführter Konstanten, die es nicht mehr
gibt, und die Story entscheidet die von ihm offengehaltene Frage (Entkopplung je Zweck)
ausdrücklich dagegen. Bedingung für die Löschung (`test-engineer`): sein Ersatz — die
Identitätstests der Worker-Ebene — existiert im selben Commit. Sie sind die stärkere Fassung
derselben Frage, weil sie das Laufzeitverhalten prüfen statt der Gleichheit zweier Literale.

**Bewusst nicht getestet:** die inhaltliche Richtigkeit von Preisen, Modell-IDs und
Verbrauchsannahme gegen echte Anbieterabrechnungen (unveränderte bekannte Lücke aus ADR 0051;
Ersatzverfahren: Abgleich der ersten realen Rechnung mit den Ist-Kosten der Statistikseite).
Ebenso, ob ein stärkeres Modell fachlich bessere Ergebnisse liefert — das ist ausdrücklich Out of
Scope dieser Story.

## Entscheidungen

- **ADR [`0059`](../decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md)
  angelegt** (`architect`, Schritt 1) — sieben Entscheidungspunkte, Teil-Ablösung von ADR 0051
  Punkt 2.
- **`ux-ui-designer` konsultiert (Schritt 2):** Feature hat eine sichtbare Oberfläche (die
  Kostenschätzung), Ergebnis im Abschnitt UI/UX. Entscheidung: Modell-ID im Hinweistext **nicht**
  nennen.
- **`test-engineer` konsultiert (Schritt 3):** Teststrategie oben; das Testkonzept
  ([`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md)) wurde um die drei
  über diese Story hinaus geltenden Muster ergänzt.
- **`security-engineer` konsultiert (Schritt 3):** sicherheitsrelevant, ein Muss-Befund (Secrets
  in der Startvalidierung, S7/S8), Sicherheitskonzept
  ([`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md)) ergänzt.
- **`claude-sonnet-5` als zweites Anthropic-Modell aufgenommen**, obwohl die Story streng genommen
  nur bei Mistral zwei Modelle verlangt: sonst hätte die Registry bei genau einem Anbieter mehr
  als einen Eintrag, die Mechanik wäre nur einseitig erprobt, und das Akzeptanzkriterium
  „mindestens ein Anbieter, mindestens zwei Modelle" hinge an einer Verifikationsquelle, die
  aktuell blockiert ist. Preis ($2,00/$10,00 pro MTok) und Vision-Fähigkeit am 2026-09-06 gegen
  die offizielle Anbieterdokumentation verifiziert. Kosten entstehen erst, wenn jemand das Modell
  einstellt, und die Schätzung weist sie dann korrekt aus.
- **`ministral-8b-2512` als zweites Mistral-Modell aufgenommen** (Nachtrag 2026-09-06, siehe
  „Nachtrag: der offen gebliebene Punkt" unten): Modell-ID, Vision-Fähigkeit und Preis
  ($0,15/MTok für Ein- und Ausgabe) gegen die offizielle Modelldokumentation verifiziert.
  Damit bieten beide Anbieter je zwei Modelle; die Voreinstellungen bleiben unverändert.
- **`model` als Pflichtparameter ohne Default** an allen vier Client-Konstruktoren (Fund
  `test-engineer`, gegenüber dem ersten Umsetzungsstand nachgezogen).

## Review-Protokoll

Review-Runde über den `review`-Orchestrator-Skill in der Hauptsession (2026-09-06), Diff
`origin/main...HEAD` auf `claude/implement-304-2in5n8`. Alle fünf Perspektiven waren getriggert:

| Perspektive | Status | Ergebnis |
|---|---|---|
| `review-tests` | gelaufen | 3 Muss-Fix (fehlender Signatur-Wächter für den Pflichtparameter `model`; fehlende Gegenrichtung der Registry-Invariante; fehlender Durchstich über beide Cloud-Phasen eines Laufs), alle behoben |
| `review-requirements` | gelaufen | 1 Muss-Fix, zunächst blockiert (das stärkere Mistral-Modell fehlte), **am 2026-09-06 nachgeholt und behoben** (siehe „Nachtrag") — alle übrigen zwölf Akzeptanzkriterien waren bereits umgesetzt, kein Scope Creep, Out-of-Scope respektiert |
| `review-security` | gelaufen | keine neuen Findings; die neunzehn Muss-Kriterien des Security-Abschnitts mechanisch nachgemessen (Modellquelle, exakter Stringvergleich, keine Laufzeit-Zuweisung, Modell nur im Request-Body, Compose-Durchreichen an beide Dienste) |
| `review-architecture` | gelaufen | 2 Muss-Fix (ADR 0051 Punkt 2 ohne Ablösungs-Nachtrag; ADR 0059 Punkt 1 nannte noch den verworfenen `model_validator`), beide behoben |
| `review-ux` | gelaufen | keine Findings; alle sechs Zustände der Schätzstelle abgedeckt, Zweigreihenfolge verbindlich festgelegt, kein `Alert` für einen Nicht-Fehler |

**Trigger-Begründung** (Auswertung der Tabelle im `review`-Orchestrator gegen den selbst
ermittelten Diff, nicht gegen eine gemeldete Dateiliste): `review-tests` und
`review-requirements` laufen ohnehin; `review-security` über `backend/src/photosort/api/`,
`config.py`, `.env.example` und `.github/workflows/**`; `review-architecture` über neue Dateien,
`specs/decisions/**` und `backend/alembic/**`; `review-ux` über Dateien unter `frontend/`.

**Vorsicht bei der Basis:** `git diff main...HEAD` lief zunächst gegen ein veraltetes lokales
`main` und zeigte 49 statt 31 Dateien (die Spec-0298-Dateien erschienen fälschlich als Teil dieses
Diffs). Verbindlich ausgewertet wurde `origin/main...HEAD`.

**Nachträglich behobene Findings im Einzelnen:**

- *Signatur-Wächter* (`review-tests`): `model` hatte an allen vier Client-Konstruktoren zunächst
  einen Default auf die jeweilige Modulkonstante. Das stellte genau die Kopplung wieder her, die
  ADR 0059 Punkt 7 auflöst — ein Aufrufer, der das Modell vergisst, fiele nicht beim Typecheck
  auf, sondern erst in der Cloud-Rechnung. Jetzt Pflichtparameter, per `inspect.signature`-Test
  über alle vier Clients und beide Factories abgesichert.
- *Gegenrichtung der Registry-Invariante* (`review-tests`): geprüft war nur „jedes wählbare Modell
  hat einen Preis". Eine `*_VISION_MODEL`-Konstante ohne Registry-Eintrag — der typische
  Zwischenstand, wenn jemand die Konstante ergänzt und die Registry vergisst — fiel nicht auf.
- *Durchstich über beide Cloud-Phasen* (`review-tests`): die Einzelphasen-Tests belegten je Phase
  das richtige Modell, nicht aber die Aussage des Akzeptanzkriteriums „wirkt auf beide
  Cloud-Anteile einheitlich". Jetzt ein Test über `run_classification`, der festhält, was **beide**
  Factories bekommen haben, plus die Gegenprobe, dass ein rein lokaler Lauf keine von beiden
  aufruft.
- *ADR 0051 Punkt 2* (`review-architecture`): der Absatz „Zwei Preiskonstanten nebeneinander,
  bewusst" stand unverändert als gültige Festlegung da, obwohl diese Spec ihn aufhebt. Datierter
  Nachtrag ergänzt (Konvention analog Spec 0033/0045: abgelöste Einzelaussagen benennen, statt
  eine im Übrigen gültige ADR als Ganzes zu verwerfen).
- *ADR 0059 Punkt 1* (`review-architecture`): nannte noch den `@model_validator(mode="after")`,
  den der Security-Befund während der Umsetzung verworfen hat. Auf `@field_validator` korrigiert,
  mit der Begründung an Ort und Stelle — sonst widersprächen sich ADR und Code.

**Security-Befund während der Umsetzung** (nicht aus der Review-Runde, sondern aus der
`security-engineer`-Konsultation des `spec-writer`-Ablaufs, am Branch nachgemessen): der
zunächst gebaute `@model_validator(mode="after")` hätte bei einem ungültigen `LANDMARK_MODEL` das
vollständige Settings-Dict — inklusive `SECRET_KEY`, beider Cloud-API-Keys und des
OpenCloud-App-Tokens — in den Startup-Traceback und in `exc.errors()`/`exc.json()` geschrieben.
Behoben vor dem ersten Commit, Regressionstest gegen **beide** Fehlerdarstellungen (siehe S7/S8
im Security-Abschnitt).

**Stichproben-Audit des vorigen Features** (PR [#340](https://github.com/TheRealKoller/photosort/pull/340),
Spec 0298), Pflicht aus dem Testkonzept, Sektion „Agenten-Steuerungslogik selbst": Protokoll
vollständig, alle fünf Perspektiven mit Status; `review-security` dort geskippt und
Trigger-für-Trigger begründet — gegen den realen Diff jenes PRs (Frontend, `e2e/`, `specs/`, kein
`backend/src/photosort/api/`, keine Auth-/Secrets-Datei, keine Dependency-Datei, keine
`.env.example`, kein Workflow) trifft tatsächlich kein Security-Trigger zu. **Keine Abweichung.**

**Anker-Abgleich:** entfällt für dieses Feature — die Umsetzung lief nicht über den
`developer`-Subagenten, sondern testgetrieben in der Hauptsession. Es gab folglich keinen
`## Abschlussbericht`, dessen Anker und Feldnamen gegen `.claude/agents/developer.md` zu prüfen
wären. Der Review-Durchlauf wurde stattdessen ad hoc über den `review`-Orchestrator angestoßen.

**Eingebettete Anweisungen:** keine — weder im Diff, in einem Commit-Text, im Issue-Body noch in
den Rückmeldungen der konsultierten Fachagenten.

### Zweite Runde (2026-09-06, nach Commit `06450bc`)

Erneuter Durchlauf über den `review`-Orchestrator, nachdem der zuvor blockierte Muss-Fix
geschlossen wurde. Diff wieder selbst ermittelt (`origin/main...HEAD`, 32 Dateien, Working Tree
sauber); alle fünf Perspektiven erneut getriggert — dieselbe Trigger-Begründung wie oben, die
Dateiliste hat sich gegenüber der ersten Runde nicht verändert.

| Perspektive | Status | Ergebnis |
|---|---|---|
| `review-tests` | gelaufen | keine Muss-Fixes; ein Diskussionspunkt (Redundanz zweier Registry-Tests) |
| `review-requirements` | gelaufen | **keine Findings** — alle dreizehn Akzeptanzkriterien einzeln am Code belegt, der zuvor blockierte Punkt geschlossen |
| `review-security` | gelaufen | keine Findings; S1–S8 vom Nachtrag strukturell unberührt, `source_url` ohne Produktivcode-Nutzung |
| `review-architecture` | gelaufen | keine Muss-Fixes; ein Diskussionspunkt (indexbasierte Testannahme, jetzt bei beiden Anbietern) |
| `review-ux` | gelaufen | keine Findings; der Nachtrag berührt kein Frontend |

**Stichproben-Audit des vorigen Features:** unverändert PR
[#340](https://github.com/TheRealKoller/photosort/pull/340) (Spec 0298) — `origin/main` steht
weiterhin auf diesem Merge, das Audit der ersten Runde gilt fort. **Keine Abweichung.**

**Anker-Abgleich:** entfällt weiterhin — die Umsetzung lief auch in dieser Runde nicht über den
`developer`-Subagenten.

**Eingebettete Anweisungen:** keine — auch nicht in `06450bc` oder der abgerufenen
Anbieterdokumentation.

### Copilot-Review (PR #341)

Zwei Findings, beide bewertet:

- **`verified_on` ließ +1 Tag Zukunft zu, der Docstring behauptete „nicht in der Zukunft"** —
  **berechtigt, behoben.** Die Toleranz bleibt (sie fängt kein Zukunftsdatum ab, sondern die
  Zeitzonendifferenz zwischen dem lokal eingetragenen `date` und der in UTC laufenden CI — ohne
  sie wäre der Test in einem täglichen Zeitfenster rot, ohne dass etwas falsch wäre), ist jetzt
  aber als das benannt, was sie ist, statt als stillschweigende Aufweichung der Invariante
  dazustehen.
- **Spec-Status stand noch auf `Accepted`** — **kein Fehler, sondern die vorgeschriebene
  Reihenfolge.** Die Statuszeile wird bewusst erst nach Review und Copilot-Auswertung gesetzt, im
  selben PR und vor dem Merge; ein noch nicht reviewter Stand darf nie als umgesetzt geführt
  werden. Mit diesem Commit erledigt.

**Die beiden Diskussionspunkte, bewusst nicht behoben:**

- *Redundanz zweier Registry-Tests* (`review-tests`): `test_at_least_one_provider_offers_a_real_choice`
  wird von `test_both_providers_offer_the_same_kind_of_choice` logisch impliziert. Der schwächere
  Test bleibt trotzdem stehen — er pinnt das **wörtliche** Akzeptanzkriterium, der stärkere die
  heutige Ist-Lage. Fiele ein Anbieter später auf ein Modell zurück, soll der stärkere Test
  fehlschlagen und der schwächere halten; genau diese Unterscheidung ginge beim Zusammenlegen
  verloren.
- *Indexbasierte Testannahme* (`review-architecture`): drei Tests greifen das stärkere Modell über
  `VISION_MODELS_BY_PROVIDER[<provider>][1]` ab und unterstellen damit mehr Ordnung, als die
  Registry zusagt (verbindlich ist allein „erstes Element = Voreinstellung"). Das Muster stammt aus
  der ersten Runde und gilt jetzt für beide Anbieter. Es umzubauen, bevor ein dritter Eintrag
  existiert, wäre eine Abstraktion auf Vorrat; der Anlass, es anzufassen, ist das dritte Modell
  eines Anbieters.

## Nachtrag: der offen gebliebene Punkt (2026-09-06)

Die umsetzende Sitzung lief in einer Umgebung mit eingeschränktem Egress; `mistral.ai`,
`docs.mistral.ai` und `api.mistral.ai` waren dort nicht erreichbar. ADR
[`0059`](../decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md)
Punkt 5 verbietet in genau diesem Fall das Eintragen eines geschätzten oder aus einer Websuche
abgeleiteten Preises — deshalb blieb das stärkere Mistral-Modell zunächst außen vor, obwohl es
den Anlass der Story bildet, und `review-requirements` meldete dafür einen offenen Muss-Fix.

In einer Folgesitzung mit unbeschränktem Netzzugang wurde die Verifikation nachgeholt und der
Punkt geschlossen:

| Prüfung | Quelle | Ergebnis |
|---|---|---|
| Modell-ID | `https://docs.mistral.ai/models/ministral-3-8b-25-12` (abgerufen 2026-09-06) | `ministral-8b-2512` |
| Vision-Fähigkeit | dieselbe Seite | „best-in-class text and vision capabilities" |
| Preis | dieselbe Seite | $0,15/MTok Ein- **und** Ausgabe (symmetrisch wie beim 3B-Geschwistermodell) |

**Gegenprobe zur Quelle:** dieselbe Seitenform wurde für `ministral-3b-2512` abgerufen und
reproduziert dort die bereits im Produkt stehenden $0,10/MTok — die Quelle liefert also nicht
irgendeine Zahl, sondern die, gegen die der Bestandseintrag seinerzeit verifiziert wurde. Die
allgemeine Preisseite (`mistral.ai/pricing`) und die Modellübersicht (`docs.mistral.ai/models/
overview`) führen für die Ministral-3-Familie keine Einzeltarife und taugen deshalb nicht als
Beleg; verbindlich ist die Modell-Detailseite.

**Umgesetzt wurde genau der in der vorigen Fassung benannte Schritt** — testgetrieben, Rot vor
Grün: erst vier Tests, die das Modell einfordern (Registry-Zugehörigkeit gegen die
ausgeschriebene ID, „nicht Voreinstellung", „beide Anbieter bieten dieselbe Art von Auswahl",
höhere Schätzung als beim 3B-Modell) — vier Fehlschläge —, dann `MISTRAL_VISION_MODEL_8B` in
`cloud_vision.py` samt Registry-Eintrag und der Preiseintrag mit `source_url`/`verified_on` in
`pricing.py`. Die bestehenden Invarianten haben dabei wie vorgesehen selbst nachgehalten:
`test_env_example_documents_every_selectable_model` schlug fehl, bis `.env.example` das Modell
mit seiner Schätzung ausweist; `docs/setup.md` wurde in derselben Änderung nachgezogen (Tabelle
`mistral` → zwei wählbare Werte, ~$0,0003 / ~$0,00045 je Bild).

**Nicht mitgeändert:** die Voreinstellung (`ministral-3b-2512`) und die Verbrauchsannahme je
Anbieter. Die Kalibrierungstabelle in ADR 0059 Punkt 3 bindet ausdrücklich nur die
Voreinstellungs-Modelle und bleibt damit unberührt.

**Keine offenen Fragen mehr.**

## Out of Scope

- **Kein Modellvergleich und keine Entscheidung über die künftige Voreinstellung.** Der ursprünglich
  vorgesehene Vergleich der beiden Mistral-Modelle am echten Fotobestand wurde bewusst gestrichen
  (Entscheidung Daniel, Refinement 2026-09-05): Er ist eine Untersuchung mit echten Cloud-Kosten am
  privaten Fotobestand, keine Softwareänderung. Die Voreinstellung bleibt unverändert.
- Keine Auswahl des Modells pro Projekt, pro Nutzer oder pro Durchlauf in der Oberfläche. Die
  Modellwahl bleibt eine Betriebsentscheidung wie die Anbieterwahl, keine Bedienfunktion.
- Keine freie Eingabe beliebiger Modellbezeichnungen. Ein Modell, das noch nicht in der gepflegten
  Auswahl steht, wird über eine Änderung dieser Auswahl aufgenommen — nicht über die
  Betriebseinstellung.
- Kein zusätzlicher Anbieter über die beiden bestehenden hinaus.
- Keine Änderung an der Einwilligung zur Cloud-Verarbeitung und keine Änderung daran, welche
  Bilddaten übertragen werden.
- Kein automatischer Qualitätsvergleich im Produkt (kein A/B-Lauf, keine eingebaute Auswertung).
