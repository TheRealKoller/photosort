# 0469 - Verlässliche und einheitliche Sehenswürdigkeitsnamen

**Status:** Implemented ([PR #487](https://github.com/TheRealKoller/photosort/pull/487))
**Erstellt:** 2026-09-14
**Bezug:** [Issue #469](https://github.com/TheRealKoller/photosort/issues/469)

**Zum Umfang:** Diese Spec überschreitet den Richtwert von rund 200 Zeilen. Sie trägt zwei ADRs,
die zusammen umgesetzt werden, und einen Security-Abschnitt aus zehn Muss-Kriterien, deren
Zusicherungen vom Kürzen ausgenommen sind.

## Ziel

Die Sehenswürdigkeitserkennung liefert bei einer Reise Ergebnisse, die weder verlässlich noch
untereinander einheitlich sind: Fotos bekommen erkennbar falsche Sehenswürdigkeiten zugeordnet, und
dieselbe Sehenswürdigkeit erscheint an verschiedenen Fotos unter verschiedenen Namen.

Das bleibt nicht folgenlos, weil erkannte Namen die Benennung der Fotogruppen tragen: Eine Reise
zerfällt in mehr Gruppen, als sie Orte hatte, und einzelne Gruppen tragen einen Namen, der nicht
zum Bild passt. Wer kuratiert, muss das von Hand wieder auseinandersortieren — genau die Arbeit,
die ihm das Projekt abnehmen soll.

Leitsatz für dieses Ziel: **Ein fehlendes Ergebnis ist besser als ein falsches.** Wo die Erkennung
sich nicht sicher ist, soll sie schweigen.

Betroffen sind beide Nutzer, sobald ein Projekt Fotos von unterwegs enthält.

## User Story

Als jemand, der die Fotos einer Reise kuratiert, möchte ich mich auf die erkannten
Sehenswürdigkeiten verlassen können — einheitlich benannt und im Zweifel lieber gar nicht genannt
—, damit die Gruppierung meiner Reisefotos den tatsächlich besuchten Orten entspricht und ich
keine falschen Zuordnungen von Hand aussortieren muss.

## Akzeptanzkriterien

### Unsichere Treffer werden verworfen

- [ ] Ein Treffer mit `confidence < LANDMARK_CONFIDENCE_THRESHOLD` ergibt keinen verwendbaren
      Namen. Die Grenze selbst gilt als sicher (`>=`, inklusiv — derselbe Vergleichssinn wie
      `presence_threshold`).
- [ ] Ein verworfener Treffer erscheint weder als Name am Foto noch als Benennung einer Gruppe:
      `usable_landmark_name` liefert `None`, `_landmark_names` liefert für dieses Foto `None`,
      `events.landmark_name` bleibt `None`. Die Zeile in `photo_landmark_detections` wird trotzdem
      vollständig geschrieben und von `api/stats.py` weiter gezählt.
- [ ] Zwei Datenlagen — ein Foto mit verworfener Erkennungszeile und ein Foto ganz ohne Zeile —
      erzeugen dieselbe Event-Bildung und dieselbe API-Antwort. Es entsteht kein zusätzlicher
      Anzeigezustand und kein Hinweis auf die verworfene Vermutung.
- [ ] Für jeden Konfidenzwert stimmen Bewertungs- und Namensurteil überein:
      `compute_landmark_score(d) >= CRITERIA_REGISTRY["landmark"].presence_threshold` genau dann,
      wenn `usable_landmark_name(name, d.confidence)` einen Namen liefert. `criteria.py` trägt kein
      eigenes Schwellenliteral mehr.

### Gleiche Sehenswürdigkeit, gleicher Name

- [ ] Ein gleicher normalisierter Name trifft immer denselben Registereintrag, ohne Ortsprüfung.
- [ ] Ein ähnlicher Name trifft, solange nicht beide Seiten einen aufgelösten, verschiedenen
      Ortsnamen tragen.
- [ ] Fotos, die dieselbe Sehenswürdigkeit zeigen, werden nicht mehr allein deshalb in getrennte
      Gruppen zerlegt, weil ihre Namen voneinander abweichen.
- [ ] Tragen beide Seiten einen aufgelösten, verschiedenen Ortsnamen, führt keine noch so hohe
      Ähnlichkeit sie zusammen. Trägt eine Seite keinen aufgelösten Ortsnamen, entscheidet die
      Ähnlichkeit allein — bewusst getragenes Restrisiko, siehe „Bekannte Lücken".

### Der Aufnahmeort verbessert die Erkennung

- [ ] Ist zu einem Foto eine eigene Koordinate gemessen, geht sie als grobe Ortsangabe in die
      Erkennung ein — nie als genaue Koordinate.
- [ ] Die Ortsangabe hat zwei Stufen: ein aufgelöster Ortsname (`usable_locality`), sonst eine
      grob gerundete Koordinate, sonst gar keine Angabe.
- [ ] Die Koordinatenstufe ist dauerhaft, kein Übergangszustand.
- [ ] `LANDMARK_PLACE_CELL_DIGITS == 1` (rund 11 km) und `LANDMARK_PLACE_CELL_DIGITS <
      PLACE_CELL_DIGITS`. Beides ist ausgeschrieben: das Literal macht die Datenschutzentscheidung
      laut, die Relation fängt eine Verschiebung der Anzeigekörnung.
- [ ] Fotos ohne gemessene Koordinate werden weiterhin erkannt. Das Fehlen der Ortsangabe
      verschlechtert das Ergebnis nicht und führt zu keinem Fehler.
- [ ] Der Prompt trägt die Auflage, bei Unstimmigkeit zwischen Ort und erkannter Sehenswürdigkeit
      `null` bzw. eine niedrige Konfidenz zu liefern; ein so gemeldeter Treffer fällt unter die
      Grenze aus der ersten Kriteriengruppe. Geprüft ist die Anwesenheit der Auflage im erzeugten
      Prompt.

### Geltungsbereich

- [ ] Die Verbesserungen wirken ab dem nächsten Erkennungslauf. Bereits erkannte
      Sehenswürdigkeiten aus früheren Läufen werden weder nachträglich verändert noch erneut
      erkannt.
- [ ] `rebuild_run_grouping` baut kein Einbettungsmodell.
- [ ] An einer echten Reise ist nachvollzogen, dass die Ergebnisse einheitlicher und plausibler
      sind als zuvor. Das ist eine Beobachtung **nach** dem Merge (Daniel, 2026-09-14) und kein
      Gate davor; ein Nachbessern wäre ein Folge-Issue.

## Datenmodell-Bezug

Additiv, eine Migration:

- Neue Tabelle `landmark_names` — `project_id` (Fremdschlüssel auf `projects.id`, `NOT NULL`),
  `normalized_name`, `display_name`, `embedding` (`SQLJSON`), `locality`, `created_at`,
  `UniqueConstraint(project_id, normalized_name)`.
- Neue Spalte `photo_landmark_detections.canonical_name`, nullable.

Siehe [`docs/architecture.md`](../../docs/architecture.md), das im selben Pull Request nachzieht.

## Architektur / Umsetzung

Zwei ADRs tragen diese Spec:
[`0106`](../decisions/0106-grobe-ortsangabe-geht-in-die-sehenswuerdigkeits-erkennung.md) (die grobe
Ortsangabe geht in die Erkennung ein; löst ADR 0025 Punkt 4 in seiner zweiten Hälfte ab) und
[`0107`](../decisions/0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md)
(eine Grenze für jede Verwendung des Namens, projektgebundenes Namensregister).

Rein im Backend, mit einer Ausnahme: Die Datenschutz-Aussage in der Oberfläche wird sonst unwahr
(Teil 1, Schritt 5). Kein neues Modell, keine neue Abhängigkeit, keine neue Umgebungsvariable.

### Teil 1 — Verlässlichkeit (ADR 0106, ADR 0107 Punkte 1–2)

1. **`places.py`** — `LANDMARK_PLACE_CELL_DIGITS = 1` und die zugehörige Vergröberungsfunktion
   neben `place_cell`, mit derselben `-0.0`-Normalisierung. Die Zelle, die das System verlässt;
   nie feiner.
2. **`landmark.py`** — die vier reinen Teile:
   - `LANDMARK_CONFIDENCE_THRESHOLD` zieht aus `criteria.py::_LANDMARK_PRESENCE_THRESHOLD` hierher
     um (Wert unverändert); `CRITERIA_REGISTRY["landmark"].presence_threshold` liest ihn von hier.
     Die Importrichtung ist erzwungen — `criteria.py` importiert bereits aus `landmark.py`.
   - `PlaceHint` und `place_hint_for(locality, gps_lat, gps_lon) -> PlaceHint | None`: die
     Stufenwahl (Ortsname → grobe Zelle → nichts) an genau einer Stelle.
   - `usable_landmark_name(name, confidence) -> str | None`: Grenze zuerst, danach
     `sanitize_landmark_name`. `None` heißt „kein verwendbarer Name", ununterscheidbar von „nie
     erkannt". In Teil 2 kommt der kanonische Name als weiterer Parameter dazu.
   - `_PROMPT` wird zu `_build_prompt(hint)`: Ortsangabe plus die Auflage, bei Unstimmigkeit
     zwischen Ort und erkannter Sehenswürdigkeit `null` bzw. eine niedrige Konfidenz zu liefern.
     In den Prompt geht **nur** der eine sanitierte Ortsname oder das gerundete Zahlenpaar, in
     einem abgegrenzten Datenfeld (Security S4).
   - `LandmarkClientLike.detect` bekommt den Hinweis als Parameter; beide Clients reichen ihn in
     ihren jeweiligen Nachrichtenaufbau durch. `_MAX_RESPONSE_TOKENS` bleibt — der Prompt wächst
     nur auf der Eingabeseite, und `pricing.py` schätzt dort ohnehin je Bild.
3. **`worker.py`, Landmark-Phase** — vor der Blockschleife die Ortsauskunft beschaffen: gemessene
   Zellen (`place_cell`) der Kandidatenfotos sammeln, `_place_infos(session, project.id, cells,
   build_place_resolver)`, je Foto `usable_locality`, daraus `place_hint_for`. Nur die **eigene**
   Koordinate des Fotos; `infer_locations` wird hier nicht benutzt. Ohne Auflöser (Datensatz fehlt)
   bleibt die Ortsnamensstufe leer und die Koordinatenstufe greift — kein Fehlerfall.
4. **`worker.py::_landmark_names`** — liest zusätzlich `confidence` und gibt jeden Namen durch
   `usable_landmark_name`. Das ist die eine Stelle, an der aus einer Zeile ein verwendbarer Name
   wird; die Erkennungszeile selbst wird unverändert vollständig geschrieben.
5. **`frontend/src/components/ClassificationSection.tsx`** — der Satz „Dieser Durchlauf sendet
   Fotos an X" nennt die grobe Ortsangabe mit, samt Test. Einziger Frontend-Eingriff.

**Ausdrücklich unverändert:** `api/stats.py` zählt `photo_landmark_detections`-Zeilen als Nachweis
dafür, dass Geld geflossen ist — es liest den Namen nie. Ein unsicherer Treffer hat ebenso gekostet
wie ein sicherer; dort darf **nicht** gefiltert werden.

### Teil 2 — Einheitlichkeit (ADR 0107 Punkte 3–5)

1. **`label_embedding.py`** — `normalize_label_text` und `cosine_similarity` ziehen aus
   `remote_classification.py` hierher um (öffentlich, Verhalten unverändert, Tests ziehen mit);
   `remote_classification.py` importiert sie von hier. Damit muss der Sehenswürdigkeits-Pfad nicht
   aus dem Kategorie-Pfad importieren.
2. **`landmark_names.py`** (neu, rein und DB-frei, Muster `places.py`) —
   `LANDMARK_NAME_SIMILARITY_THRESHOLD` (eigene Konstante, strenger als die der Feinlabels,
   dokumentiert-unkalibriert), `LandmarkNameEntry` (nicht frozen, die `id` wird nach dem Einfügen
   nachgesetzt — Muster `FineLabelSnapshotEntry`) und
   `resolve_canonical_landmark(raw_name, locality, entries, embedder)`: gleicher normalisierter
   Name trifft immer; Ähnlichkeit trifft nur, wenn nicht beide Seiten einen verschiedenen
   aufgelösten Ortsnamen tragen.
3. **`models.py` + Migration** (additiv) — Tabelle `landmark_names` und Spalte
   `photo_landmark_detections.canonical_name` wie unter „Datenmodell-Bezug".
   `project_deletion.py` bekommt die Löschanweisung in der per Test erzwungenen
   `reversed(sorted_tables)`-Ordnung, `tests/project_graph.py` die Tabelle.
4. **`worker.py`, Landmark-Phase** — Einbettungsmodell über `_try_build(build_embedder)` bauen,
   Registerschnappschuss des Projekts einmal laden, je Treffer **oberhalb der Grenze** auflösen,
   neue Einträge einfügen und die `id` am Schnappschuss nachsetzen (Muster
   `run_remote_category_classification`). Kein Einbetter, kein kanonischer Name, kein Laufabbruch.
5. **`worker.py::_landmark_names` / `usable_landmark_name`** — kanonischer Name vor Rohname. Eine
   Zeile ohne kanonischen Namen verhält sich exakt wie heute (kein Nachziehen von Altbestand).
6. **`events.py::LandmarkChangeSignal`** — Code unverändert, Selbstbeschreibung korrigiert: Der
   zeichengenaue Vergleich ist keine bewusste Vereinfachung mehr, die Vereinheitlichung liegt jetzt
   davor.

`docs/architecture.md` zieht im selben Pull Request nach (Owner `architect`), `docs/setup.md` nicht
— es entsteht kein neuer Setup-Schritt.

### Reihenfolge

Ein einziger Pull Request über beide Teile (Daniel, 2026-09-14). Teil 1 vor Teil 2, weil das
Namensregister den in Teil 1 beschafften Ortsnamen als Sperre braucht. Innerhalb jedes Teils:
reine Module zuerst, dann Datenmodell und Migration, dann `worker.py`, zuletzt Oberfläche und
Dokumentation.

**Für den Umsetzungslauf:** Die Alembic-Revisions-ID kollidiert bei Parallelarbeit, ohne dass git
einen Konflikt meldet — die eigene Migration zieht dann um und hängt ihre `down_revision` nach.
Pflicht-Nachbarn der Migration sind ein `test_migration_*` und
`test_postgres_ddl_compatibility.py`.

`_upsert_landmark_detection` muss `canonical_name` mit setzen — ob über einen zusätzlichen
Parameter oder separat, ist frei. Die Zusage lautet in beiden Fällen: `name` und `confidence` gehen
ungefiltert in die Zeile, `canonical_name` nur oberhalb der Grenze.

## UI/UX

Keine neue Interaktion, keine neue Komponente, kein neuer Zustand, keine Ergänzung des
Design-Systems. Ein wegen Unsicherheit verworfener Treffer erzeugt ausdrücklich keinen eigenen
Anzeigezustand; Event- und Gruppennamen werden nur in ihren Werten einheitlicher, nicht in ihrer
Darstellung.

Die einzige sichtbare Änderung ist die Datenschutz-Aussage in
`frontend/src/components/ClassificationSection.tsx` (`data-testid="classification-scope-text"`).
Sie muss die grobe Ortsangabe nennen, sonst ist sie unwahr — beide Stufen benannt, und erkennbar,
dass Fotos ohne Standortdaten nicht betroffen sind. Der lokale Durchlauf behält seinen Satz
unverändert.

## Security

Sicherheitsrelevant und tragend: Die Story hebt die Zusage des Sicherheitskonzepts auf, dass die
Ortsauskunft das System nicht verlässt (ADR 0025 Punkt 4 zweite Hälfte). Daniel hat das im
Refinement in Kenntnis dieser Folge entschieden. Die Fortschreibung steht in
`specs/architecture/0003-securitykonzept.md`, Abschnitte „Cloud-Vision-API" und „Standortdaten";
die Muss-Kriterien unten haben dort ihre Zeilen in der Ankerliste.

**Was unverändert weiter gilt** — und deshalb in dieser Story nicht neu verhandelt wird: Es
entsteht kein zweiter Empfänger (die Ortsangabe geht in den Prompt desselben Aufrufs, der das Foto
trägt). Die Einwilligung ist dieselbe (`Project.cloud_landmark_detection_enabled` plus
laufbezogenes Häkchen); ein eigener Schalter für den Ortsanteil entsteht bewusst nicht — wer das
Foto sendet, sendet den Ort mit oder verzichtet auf die Erkennung. Bereits erteilte Einwilligungen
bleiben gültig und werden nicht zurückgesetzt (Daniel, 2026-09-14); die aktualisierte
Oberflächen-Aussage trägt das allein. `PLACE_CELL_DIGITS = 2` und damit jede gespeicherte und an
den Browser ausgelieferte Ortskörnung bleibt unangetastet. `rebuild_run_grouping` fragt weiter
niemanden und löst keinen Vision-Aufruf aus.

**S1 — Eine Vergröberungsfunktion, an einem Rand; die Textform am Prompt.** Die Koordinatenstufe
rundet auf `LANDMARK_PLACE_CELL_DIGITS = 1` (rund 11 km) in **genau einer** Funktion neben
`places.py::place_cell`; nie an einer Aufrufstelle nachgerechnet. Die **Textform** entsteht an
**genau einer** anderen Stelle, unmittelbar am Prompt (`landmark.py`), aus denselben
`float`-Werten mit fester Nachkommastellenzahl — nie aus einem in der Datenbank abgelegten String,
nie aus `PhotoOut`/`EventOut`, und die Nachkommastellenzahl wird von der Konstante gelesen statt
ein zweites Mal geschrieben.

**Warum zwei Orte und nicht einer:** ADR 0102 Punkt 4 untersagt `places.py` das Zusammensetzen
zweier Ortswerte zu einer Zeichenkette und setzt das per Wächtertest durch
(`test_places.py::TestTheModuleBoundaryFromAdr0102` schlägt auf jede Formatzeichenkette mit zwei
Platzhaltern an). Diese Zusicherung wird für die Textform nicht aufgeweicht; sie zieht stattdessen
dorthin, wo sie ohnehin hingehört — in das Modul, das den ausgehenden Rand trägt.

Die `PlaceResolver`-Signaturgrenze deckt diesen Rand nicht: Der sendende Rand ist hier kein
Auflöser, sondern der Vision-Client. Ohne die eine Vergröberungsfunktion hinge die Zusage an einer
Aufrufstelle, und die zweite bekäme sie nicht mit.

**S2 — Die Namensstufe hat eine andere Schranke, und sie ist ausgeschrieben.** Hinaus geht genau
ein Wert aus `locality`: nie `neighbourhood` (die Ebene darf treffen, ihr Wert geht nie hinaus),
nie Region oder Land, nie die zusammengesetzte Form „Ort, Viertel" aus `events.py`, nie Straße
oder Hausnummer. Die Stufenprüfung ist `places.py::usable_locality`, es entsteht keine zweite
Fassung von „ein Ortsname gilt als aufgelöst".

**S3 — Nur die gemessene Koordinate des Fotos.** Eine über `events.py::infer_locations`
übernommene Koordinate geht nie in die Erkennung ein (ADR 0106 Punkt 4). Das ist nicht nur
Korrektheit: Eine Schätzung trüge Ortsdaten auch für Aufnahmen hinaus, die selbst nie eine hatten.
Ein Foto ohne eigene Koordinate wird unverändert erkannt; das Fehlen ist kein Fehlerfall.

**S4 — Die Ortsangabe ist ein Datum, nie eine Anweisung.** Der Ortsname stammt aus GeoNames, einem
von Dritten beschreibbaren Datensatz. Muss: (a) Die Angabe steht in einem **abgegrenzten
Datenfeld** am Ende des Prompts, nie in den Instruktionssatz hineingeschrieben, und die Instruktion
benennt das Feld als Angabe *über* das Foto. (b) Der Anfragekörper bleibt ein Python-Objekt an
`post_vision_request(..., json=body)`; es wird nie ein JSON-Text zusammengesetzt. (c) Es geht genau
der eine sanitierte Name oder das Zahlenpaar mit, keine weitere Zeichenkette aus der Datenbank
(ADR 0106 Punkt 6).

**S5 — Bezifferte obere Schranke der Einschleusung.** Ein gelungener Einschub kann höchstens
erreichen, dass das Modell einen gewählten Namen mit gewählter Konfidenz zurückgibt. Das ist
gedeckt: `sanitize_landmark_name` (Zeichen, 80, verwerfen statt kürzen), Konfidenzklemmung auf
`[0, 1]`, die eine Grenze aus ADR 0107 Punkt 1, Rendering ausschließlich als regulärer
React-Textknoten, `max_tokens = 256` als Kostenschranke. Nicht erreichbar: ein zweites Geheimnis in
der Anfrage, ein Werkzeug, eine Folgeanfrage, ein zweiter Empfänger; die Antwort geht in keine
Query, keinen Pfad und keine Kommandozeile. Neu gegenüber dem Bestand ist **eine** Wirkung: Ein
eingeschleuster Name kann über `landmark_names` die Anzeigeform eines Registereintrags besetzen
und mehrere Aufnahmen benennen statt einer — begrenzt auf ein Projekt und auf Namen oberhalb der
Grenze aus ADR 0107 Punkt 1.

**S6 — Weder Ortsname noch Koordinate in Log, Exception-Meldung oder Fehlerzeile.** `str(exc)`
eines fehlgeschlagenen Landmark-Aufrufs geht an zwei Senken: die WARNING-Zeile **und**
`photo_cloud_vision_errors.error_message`, das über `GET /projects/{id}/photos` an den Browser
ausgeliefert wird — persistiert und abrufbar, die stärkere Oberfläche als das Log. Die Auflage an
`LandmarkApiError` („niemals der API-Key, niemals Base64-Bilddaten") bekommt ihren dritten Posten:
niemals die Ortsangabe. `_log_cloud_vision_failure` behält seine heutigen Parameter; die
Ortsangabe wird ihm nicht zusätzlich durchgereicht. Die bestehende Auflage in `places.py`/
`geonames.py` gilt unverändert und erstreckt sich auf jedes in dieser Story neue Modul.

**S7 — Die Datenschutz-Aussage in der Oberfläche nennt die Ortsangabe.**
`ClassificationSection.tsx` (`data-testid="classification-scope-text"`), im selben Pull Request.
Sie ist der Text, an dem die Einwilligung hängt; bliebe sie bei „sendet Fotos", wäre die
Einwilligung für diese Datenklasse an einer Beschreibung erteilt, die sie nicht nennt.

**S8 — Das Namensregister hängt am Projekt, und der Mechanismus ist der Grund.**
`landmark_names.project_id` ist ein echter Fremdschlüssel auf `projects.id`, `NOT NULL` — wie
`place_lookups`, ausdrücklich nicht wie `fine_labels`. Ohne die Spalte wäre die Tabelle ein reiner
Fremdschlüssel-Elternteil, fiele aus `tests/project_graph.py::tables_reachable_from_projects`
heraus, und **beide** Vollständigkeitstests der Projektlöschung prüften sie stillschweigend nicht
mehr. `project_deletion.py` bekommt die Löschanweisung in Fremdschlüssel-Reihenfolge,
`build_project_graph` eine Zeile. `photo_landmark_detections.canonical_name` bleibt eine
gewöhnliche Textspalte, kein Fremdschlüssel auf das Register. Der Einbettungsvektor ist eine
verlustbehaftete Kodierung genau des Namens in derselben Zeile — er erbt dessen Einstufung, gehört
unter dieselbe Lebensdauer und in keine API-Antwort und kein Log.

**S9 — Keine neue Sichtbarkeit zwischen den beiden Nutzern.** Kein neuer Endpunkt, das Register
wird nicht ausgeliefert. Der Name erreicht die Oberfläche weiter ausschließlich über
`events.landmark_name` und damit über `worker.py::_landmark_names`; das bleibt die einzige Quelle
und wendet `sanitize_landmark_name` auf den zurückgegebenen Wert an, **gleich ob kanonischer Name
oder Rohname** — die Altbestandsdeckung darf nicht dadurch entfallen, dass ein neues Feld daneben
tritt. Keine nutzerabhängige Antwortmenge; die Cache-Schlüssel-Auflage aus
`api/photos.py::_to_photo_out` wächst nicht.

**S10 — `rebuild_run_grouping` lädt kein Einbettungsmodell** (ADR 0107 Punkt 5). Der Pfad läuft in
einem Request; ein 113-MB-Modell im Anfragepfad wäre ein Speicher- und Laufzeitvielfaches, das
eine authentifizierte Anfrage — auch eine mit gestohlenem JWT — wiederholt auslösen könnte.

**Ausdrücklich geprüft und ohne Befund:** kein neues Secret; keine neue Abhängigkeit und kein neues
Modell-Asset; keine neue Nutzereingabe von außen; keine Änderung an Auth oder Endpunktzuschnitt;
kein SSRF-Pfad (die Ortsauskunft liest eine lokale Datei, der Vision-Endpunkt ist eine Konstante);
`LandmarkChangeSignal` bekommt keine neue Kontrollflusswirkung.

## Teststrategie

Striktes TDD, ein Pull Request über beide Teile. Kein E2E-Spec: das Aufnahmekriterium der
E2E-Ebene (nur, was jsdom prinzipiell nicht kann) ist nicht erfüllt.

### Unit, Backend — rein, ohne Datenbank

- `places.py`, Vergröberungsfunktion: Rundung auf 1 Nachkommastelle, `-0.0`-Normalisierung auf
  **beiden** Achsen (Eingabe `-0.04`), Rundungsgrenze festgenagelt wie bei `place_cell`.
  `LANDMARK_PLACE_CELL_DIGITS == 1` als Literal **und** `< PLACE_CELL_DIGITS` als Relation.
- `landmark.py::place_hint_for`: die drei Ausgänge (Ortsname / gerundete Koordinate / nichts) und
  ihr Vorrang. Fall „Ortsname vorhanden **und** Koordinate vorhanden": der Hinweis trägt den Namen,
  und das gerundete Zahlenpaar taucht im Ergebnis **nicht** auf. Fall „Koordinate vorhanden,
  Ortsname nicht auflösbar (Stufe `region`, oder `sanitize_place_name` verwirft ihn)":
  Koordinatenstufe, nicht „nichts". Fall „keine Koordinate": nichts — und damit strukturell auch
  kein Ortsname.
- `landmark.py::usable_landmark_name`: Grenze **vor** Sanitisierung. Genau auf der Grenze
  verwendbar; darüber mit unbrauchbarem Namen `None`; darunter mit einwandfreiem Namen `None`.
- `landmark.py::_build_prompt`: mit und ohne Hinweis; die Unstimmigkeits-Auflage steht drin; der
  Hinweis wird aus `PlaceHint` **erzeugt**, nicht als zweites Literal geführt (Nachweis durch
  Veränderung der Quelle, Muster `test_classification_prompt.py`). Negativprobe gegen
  Prompt-Einschleusung: eine Messlage, deren `neighbourhood`/`region`/`country` einprägsame
  Zeichenfolgen tragen, und deren Ortsname Anführungszeichen, Klammern, Zeilenumbruch und einen
  Anweisungssatz enthält — im Prompt steht der eine sanitierte Name und sonst keine dieser
  Zeichenfolgen.
- `landmark_names.py::resolve_canonical_landmark`: gleicher normalisierter Name trifft **auch bei
  verschiedenen Ortsnamen** (Schnellweg ohne Ortsprüfung — eigener Fall, sonst wird das später als
  Bug „repariert"); Ähnlichkeit trifft bei gleichem Ortsnamen und bei fehlendem Ortsnamen auf einer
  Seite; die Sperre wird bei **Ähnlichkeit 1.0** geprüft, damit allein der verschiedene Ortsname
  die Ursache sein kann; ein neuer Eintrag ergänzt die Liste in-place, sodass ein zweiter ähnlicher
  neuer Name im selben Lauf auf ihn trifft. Modulgrenze wie `places.py`: `import_closure` zeigt
  weder `photosort.models` noch `sqlalchemy`, mit Gegenprobe.
- `label_embedding.py`: die beiden umgezogenen Helfer sind verhaltenserhaltend — die bestehenden
  Fälle ziehen unverändert mit um, nur gegen den neuen Importpfad.
- Ein Maßstab, zwei Verbraucher: parametrisierte Tabelle über Konfidenzwerte um die Grenze herum,
  die für jeden Wert die Übereinstimmung von Bewertungsurteil und Namensurteil prüft. Dazu
  `CRITERIA_REGISTRY["landmark"].presence_threshold == LANDMARK_CONFIDENCE_THRESHOLD` und ein
  Wächter, dass `criteria.py` kein eigenes Schwellenliteral mehr trägt.

### Integration, Backend — echte Session, Test-Doubles für Client und Einbetter

- Ortsauskunft vor der Blockschleife: je Foto die **eigene** Zelle; ein Foto, dessen Koordinate nur
  über `infer_locations` entstünde, bekommt keinen Hinweis. Dazu ein Syntaxbaum-Wächter, dass die
  Landmark-Phase `infer_locations` nicht aufruft — ein hinzugefügter Aufruf rötet sonst keinen
  Verhaltenstest, solange die Messlage echte Koordinaten trägt.
- Kein Auflöser (Datensatz fehlt): Fotos mit Koordinate erhalten die Koordinatenstufe, der Lauf
  läuft durch, keine Fehlerzeile.
- Kein Einbetter (`_try_build` liefert `None`): kein kanonischer Name, kein Laufabbruch, die
  Erkennungszeilen entstehen unverändert.
- Register am Kreuzfall: zwei Projekte, derselbe normalisierte Name — zwei Zeilen, keine
  Constraint-Verletzung, und die Zeile des einen Projekts wird für das andere nicht gelesen.
- `_landmark_names`: kanonischer Name vor Rohname; eine Zeile ohne kanonischen Namen verhält sich
  exakt wie heute; ein kanonischer Name, der die Sanitisierung nicht übersteht, fällt auf den
  Rohnamen zurück.
- Ununterscheidbarkeit: **ein** Testfall über zwei Datenlagen — Foto mit verworfener Zeile, Foto
  ohne Zeile — mit gleicher Event-Bildung und gleicher API-Antwort. Dazu der fachliche Folgefall:
  ein Event, dessen Treffer sämtlich verworfen wurden, fällt auf Ortsnamen bzw. Koordinate zurück.
- Einheitlichkeit: zwei Erkennungszeilen mit verschiedenem `name`, gleichem `canonical_name`
  ergeben **ein** Event statt zweier.
- Ein unterhalb der Grenze liegender Treffer erzeugt **keinen** Registereintrag, und ein späterer
  Lauf fragt ihn nicht erneut ab.
- `api/stats.py` bleibt ungefiltert: ein Lauf mit ausschließlich verworfenen Treffern weist die
  Zeilen und die Kosten weiterhin aus. Dazu ein Wächter, dass dort weder auf `confidence` noch auf
  `canonical_name` gefiltert wird — die Stelle sieht wie eine Inkonsistenz aus und ist keine.
- `rebuild_run_grouping` baut keinen Einbetter (Wächter auf die Aufrufstelle, Security S10).
- Logging-Auflage über die gesamte Phase einschließlich des Fehlerpfads eines scheiternden
  Cloud-Aufrufs, und einschließlich `photo_cloud_vision_errors.error_message`: `caplog` über alle
  Sätze, gesucht werden die einprägsamen Ortsnamen und Koordinatenzeichenfolgen **der Messlage**,
  nie ein allgemeines Zahlenmuster.
- Löschpfad: `landmark_names` wird in `tests/project_graph.py` mit angelegt; die bestehenden
  metadatengetriebenen Fälle in `test_project_deletion.py` erzwingen Reihenfolge und
  Vollständigkeit dann von selbst.

### Migration

Eigenes `test_migration_*` nach dem Muster von `test_migration_ortsauskunft.py`: additiv, beide
Richtungen, bestehende `photo_landmark_detections`-Zeilen überleben unverändert, `canonical_name`
ist nach dem `upgrade` überall `NULL` (kein Nachziehen), `UniqueConstraint(project_id,
normalized_name)` greift. Dazu die Pflicht-Nachbarn `test_migration_chain.py` und
`test_postgres_ddl_compatibility.py`.

### Signaturänderung

`LandmarkClientLike.detect` bekommt den Hinweis als Parameter: beide echten Clients legen ihn in
den Textteil, der Bildteil bleibt unverändert (Request-Form-Fall je Anbieter), und das
Protokoll-Double der Suite zieht mit.

### Frontend (`vitest`)

`ClassificationSection.test.tsx`: der Cloud-Satz nennt die grobe Ortsangabe, der lokale Satz nicht.

### Testkonzept

`specs/architecture/0002-testkonzept.md` wird im selben Pull Request um fünf Muster ergänzt, die
über diesen Branch hinausgelten: ein Maßstab an einer Stelle wird über die Übereinstimmung seiner
Verbraucher geprüft, nicht über zwei Literale; zwei ununterscheidbare Ursachen derselben
Abwesenheit werden als Gleichheit zweier Beobachtungen in **einem** Fall geprüft; eine Sperre wird
bei maximaler Gegenkraft geprüft (Ähnlichkeit 1.0); was in einen Prompt geht, wird über die
**Abwesenheit** der Nachbarfelder geprüft; eine ausgehende Körnung wird doppelt festgenagelt, als
Literal und als Relation zur Anzeigekörnung.

### Bewusst nicht geprüft

- Ob das Modell der Unstimmigkeits-Auflage folgt. Geprüft ist die Auflage im Prompt.
- Ob das Einbettungsmodell zwei Schreibweisen oder Sprachen derselben Sehenswürdigkeit als ähnlich
  bewertet. Kein Namenskorpus im Repository, kein Modell im Unit-Lauf;
  `LANDMARK_NAME_SIMILARITY_THRESHOLD` ist dokumentiert-unkalibriert. Erkennungsweg ist die
  Abnahme an einer echten Reise.

## Bekannte Lücken

- Die Zusage „nie zusammengezogen" trägt nur über die Ortsnamen-Sperre. Trägt eine Seite keinen
  aufgelösten Ortsnamen — also bevorzugt in dünn besiedelter Gegend —, entscheidet die Ähnlichkeit
  allein, und zwei verschiedene Sehenswürdigkeiten können verschmelzen. Bewusst getragen (Daniel,
  2026-09-14); die Gegenmaßnahme wäre gewesen, den Ähnlichkeitspfad ohne beidseitigen Ortsnamen zu
  sperren, was in genau diesen Gegenden gar nicht mehr vereinheitlicht hätte.
- `LANDMARK_NAME_SIMILARITY_THRESHOLD` ist dokumentiert-unkalibriert, gleiche Klasse wie die
  Feinlabel-Schwelle.
- Wird die Konfidenzgrenze später **gesenkt**, werden bislang verworfene Namen verwendbar, bleiben
  aber dauerhaft unkanonisiert — ihre Fotos werden nicht erneut abgefragt. Für diesen Altbestand
  gilt die Einheitlichkeit dann nicht. Eine Erhöhung der Grenze ist unproblematisch.
- Die Namensstufe der Ortsangabe ist in dünn besiedelter Gegend genauer als die Koordinatenstufe:
  Ein Siedlungsname benennt einen Aufenthalt schärfer als eine 11-km-Zelle. So gewollt (Daniel,
  2026-09-14); die Gegenmaßnahme wäre eine Einwohner- bzw. Ebenen-Untergrenze und eine eigene ADR.
- Das Coverage-Gate trägt diese Spec nicht (rund 4.500 Statements bei 97 % Ausgangslage). Tragend
  ist allein die namentliche Fallliste oben.

## Entscheidungen

- **Ein Pull Request über beide Teile** (Daniel, 2026-09-14). Der Vorschlag einer Aufteilung in
  zwei PRs (erst Verlässlichkeit, dann Einheitlichkeit) wurde vorgelegt und verworfen.
- **Koordinatenstufe auf 1 Nachkommastelle, rund 11 km** (Daniel, 2026-09-14), gewählt gegen
  0 Nachkommastellen (rund 111 km).
- **Das Kriterium „nie zusammengezogen" wird auf das eingeschränkt, was die Sperre leistet**
  (Daniel, 2026-09-14); das Restrisiko steht unter „Bekannte Lücken".
- **Die Abnahme an einer echten Reise ist eine Beobachtung nach dem Merge**, kein Gate davor
  (Daniel, 2026-09-14).
- **Die Namensstufe bleibt ohne Untergrenze** (Daniel, 2026-09-14).
- **Bereits erteilte Cloud-Einwilligungen bleiben gültig** (Daniel, 2026-09-14); die Migration
  setzt sie nicht zurück.
- **Der Mischzustand nach einer späteren Senkung der Grenze wird getragen, nicht verhindert**
  (technische Detailentscheidung); er steht unter „Bekannte Lücken".
- Alle vier Konsultationen des `spec-writer`-Ablaufs sind gelaufen: `architect` (ADRs 0106/0107),
  `ux-ui-designer`, `test-engineer`, `security-engineer`.

## Out of Scope

- Das Auflösen von Ortsnamen aus Koordinaten selbst (Spec 0434, umgesetzt). Diese Spec nutzt einen
  Ortsnamen, wenn einer vorliegt, und beschafft ihn nicht.
- Ein Nachziehen der Namen für bereits abgeschlossene Erkennungsläufe.
- Ein sichtbarer Hinweis darauf, dass ein Treffer verworfen wurde.
- Eine Änderung des Zahlwerts der Konfidenzgrenze. Geändert wird die Gleichheit des Maßstabs, nicht
  seine Höhe.
- Ein Wechsel des Erkennungsmodells. Die Abnahme wird mit dem heutigen Voreinstellungsmodell
  gemessen.
