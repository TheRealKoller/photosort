# 0429 - Auswahl mit Richtwert und Mischung: jedes Event, jedes Motiv, das Beste je Motiv

**Status:** Implemented ([PR #462](https://github.com/TheRealKoller/photosort/pull/462))
**Erstellt:** 2026-09-13
**Bezug:** [Issue #429](https://github.com/TheRealKoller/photosort/issues/429) (Story unter dem Zielbild [#424](https://github.com/TheRealKoller/photosort/issues/424))

**Umfang:** ein Mehrfaches des Richtwerts von rund 200 Zeilen. Drei Abschnitte tragen ihn, jeder aus
einem eigenen Grund: „Architektur / Umsetzung" führt die betroffenen Dateien je Schritt auf, weil
der `developer` sie ohne eigene Planung abarbeitet; „Security" führt acht einzeln abhakbare Auflagen
samt Angriffsmodell; „Teststrategie" benennt neunzehn Zusicherungen, die ohne eigenen Testfall still
brechen — ein Fehler in diesem Verfahren wirft keine Ausnahme, er liefert eine andere, plausibel
aussehende Auswahl.

## Ziel

Nach Scan und Ausschuss-Schritt soll aus den Fotos eines Projekts ein Auswahlvorschlag entstehen,
der die ganze Reise abbildet: etwa ein Zehntel der Bilder, über alle Events verteilt, in jedem
Event die dort vorkommenden Motive gemischt und darin jeweils das beste Bild.

Heute gibt es das nicht. Die Kuratierung zeigt je Event die besten bis zu zehn Bilder, und wie
viele es sind, stellt man beim Ansehen ein. Daraus folgen zwei Lücken. Erstens gibt es keinen
Gesamtumfang: Ein Event mit fünf Fotos bekommt genauso viele Plätze wie eines mit fünfhundert, und
bei einigen tausend Fotos entstehen je nach Einstellung einige hundert bis weit über tausend
Vorschläge. Zweitens gibt es seit der Umstellung auf Motive mit Stärke gar keine Motivmischung
mehr: Die besten Bilder eines Events sind schlicht die qualitativ besten — überwiegt dort ein
Motiv, zeigen alle Plätze dasselbe.

Diese Story schließt beide Lücken und ist der Kern des Umbaus. Sichtbar wird ihr Ergebnis erst mit
Story 6 (Album-Entwurf je Nutzer); hier entstehen die Auswahl und die Einstellung des Richtwerts.

## User Story

Als kuratierender Nutzer möchte ich einen Auswahlvorschlag bekommen, der einen von mir bestimmten
Gesamtumfang einhält, jedes Event der Reise berücksichtigt und in jedem Event die verschiedenen
Motive mit ihren jeweils besten Bildern mischt, damit ich einen Entwurf vor mir habe, der die
Reise abbildet, statt einer Liste, die von den bilderreichsten Momenten beherrscht wird.

## Akzeptanzkriterien

**Umfang**

- [ ] Der Vorschlag richtet sich nach einem Richtwert, der für ein Projekt auf ein Zehntel seiner Bilderzahl vorbelegt ist.
- [ ] Der Richtwert ist je Projekt als absolute Anzahl einstellbar.
- [ ] Der Richtwert ist ein Ziel, keine Obergrenze: Fehlt es an guten Bildern, umfasst der Vorschlag weniger.
- [ ] Ein Bild ohne Qualitätsurteil erscheint nicht im Vorschlag.

**Verteilung über die Events**

- [ ] Jedes Event des Projekts ist im Vorschlag vertreten.
- [ ] Reicht der Richtwert nicht für alle Events, wird der Vorschlag größer als der Richtwert — die Abdeckung geht vor.
- [ ] Ein bilderreiches Event bekommt mehr Plätze als ein bilderarmes, aber nicht im Verhältnis seiner Bilderzahl: Sein Anteil ist nach oben begrenzt.

**Mischung innerhalb eines Events**

- [ ] Ein Motiv gilt in einem Event als vorkommend, wenn mindestens ein Bild des Events es deutlich genug trägt. Die Grenze dafür ist für alle Motive dieselbe.
- [ ] Alle in einem Event vorkommenden Motive sind gleichrangig. Es gibt weder eine Rangfolge zwischen Motiven noch einen Vergleich ihrer Stärken untereinander.
- [ ] Solange ein Event freie Plätze hat und dort ein vorkommendes Motiv noch unvertreten ist, geht der nächste Platz an dieses Motiv.
- [ ] Hat ein Event weniger Plätze als vorkommende Motive, entscheidet die Bildqualität, welche Motive vertreten sind.
- [ ] Innerhalb eines Motivs wird das qualitativ beste Bild gewählt.

**Wie der Vorschlag zustande kommt**

- [ ] Die Plätze werden nacheinander vergeben. Ein Bild ist dabei umso weniger wert, je mehr ihm ähnliche Bilder bereits gewählt sind.
- [ ] Als ähnlich gelten Bilder desselben Events, desselben Motivs und zeitlich benachbarte Aufnahmen. Ein eigenes Maß für visuelle Ähnlichkeit wird nicht eingeführt.
- [ ] Gleicher Bildbestand und gleiche Einstellungen ergeben denselben Vorschlag. Es gibt keinen zufälligen und keinen von der Verarbeitungsreihenfolge abhängigen Anteil.

**Was unverändert weiter gilt**

- [ ] Ein einmal entstandener Vorschlag ändert sich nicht durch das Bedienen der Ansicht: Ein verworfenes Bild lässt kein anderes nachrücken.
- [ ] Der vollständige Bildbestand eines Events bleibt einsehbar. Was nicht im Vorschlag steht, ist weiterhin erreichbar.
- [ ] Duplikate und Serien werden weiterhin vorher im Ausschuss-Schritt abgefangen, nicht in der Auswahl.

**Was entfällt**

- [ ] Die bisherige Auswahlregel „die besten N je Event, N beim Ansehen gewählt" entfällt.

## Datenmodell-Bezug

Zwei neue nullable Spalten, beide in [`docs/architecture.md`](../../docs/architecture.md) im selben
Pull Request nachzuziehen:

- `projects.selection_target: int | None` — der eingestellte Richtwert. `NULL` heißt **nicht** „kein
  Richtwert", sondern „nicht selbst eingestellt"; der wirksame Wert ist dann ein Zehntel der
  Bilderzahl. Die Vorbelegung wird nie in die Spalte geschrieben.
- `photo_rankings.selection_position: int | None` — der 1-basierte Platz eines Fotos innerhalb
  seines Events, `NULL` heißt „gehört nicht zum Vorschlag". Ein Foto steht pro Lauf weiterhin in
  genau einer Rangzeile.

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0097`](../decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md)
festgehalten und dort vollständig begründet; sie löst die Auswahlregel aus ADR
[`0071`](../decisions/0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md)
teilweise ab. Die `**Teilweise abgelöst:**`-Kopfzeile in ADR 0071 wird im selben Pull Request
nachgetragen — Kopfzeile, nicht Entscheidungstext, der einzige zulässige Eingriff laut
[`specs/README.md`](../README.md).

### Gewählter Ansatz

Der Vorschlag ist ein **persistiertes Artefakt des Kriterien-Laufs**, kein Leseparameter. Berechnet
wird er von einer **reinen, DB-freien Funktion** in einem neuen Modul
`backend/src/photosort/selection.py` — dasselbe Muster wie `ranking.py`/`quality.py`/`events.py`:
Sortier- und Verteilungslogik ohne Session, alle Stellschrauben als benannte Modulkonstanten an
genau einer Stelle.

**Auswahlfähig** ist ein Kandidat des letzten erfolgreichen `CriterionScoringRun` mit
`rank_score IS NOT NULL` und ohne `excluded_document`. Der zweite Teil ist die fortgeschriebene
Zusage aus ADR 0091 Punkt 2: Ein als Dokument oder Bildschirmabbild erkanntes Foto erscheint in
keiner Motivauswahl, und der Vorschlag ist eine.

### Stufe 1 — Kontingente je Event

Mit `n_i` = auswahlfähige Kandidaten des Events, `m` = Events mit `n_i > 0`, `T` = wirksamer
Richtwert:

1. Jedes Event bekommt einen Platz. Bei `m > T` wird der Vorschlag größer als `T` — die Abdeckung
   geht vor.
2. Die restlichen `T − m` Plätze nach `w_i = √n_i` im Größte-Reste-Verfahren. Ein Event mit
   hundertfacher Bilderzahl bekommt das Zehnfache an Plätzen, nicht das Hundertfache.
3. Obergrenze je Event: `min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))`. Gekappte Plätze gehen an die nicht
   gekappten Events; die Verteilung wiederholt sich, bis nichts mehr frei ist oder alle Events an
   ihrer Obergrenze stehen.
4. Danach übrige Plätze verfallen — der Fall „es fehlt an guten Bildern", der Vorschlag ist dann
   kleiner als `T`.

### Stufe 2 — motivgeführte Vergabe je Event

Unabhängig von den übrigen Events; alles, was als ähnlich gilt, liegt im selben Event.

Ein Motiv **kommt vor**, wenn mindestens ein auswahlfähiges Bild es mit wirksamer Stärke
≥ `MOTIF_PRESENCE_THRESHOLD` (0,5) trägt. Die wirksame Stärke kommt ausschließlich über
`motif_strengths.py::effective_strength_expression`/`load_effective_strengths` (Korrekturen
inbegriffen). Diese Grenze ist **nicht** eines der Anzeigebänder aus `motifs.py` — ADR 0091 Punkt 8
untersagt, dass ein auswählender Codepfad jene liest — und wohnt deshalb in `selection.py`.

Wert eines noch nicht gewählten Bildes:

    wert(p) = rank_score(p) · 0,5 ^ Σ_{s gewählt} ähnlichkeit(p, s)

mit `ähnlichkeit = geteiltes_motiv · zeitnähe`; `geteiltes_motiv` ist 1, wenn ein Motiv existiert,
das beide mit mindestens `MOTIF_PRESENCE_THRESHOLD` tragen, sonst 0;
`zeitnähe = max(0, 1 − |Δt| / 15 min)`. Kein eigenes Maß für visuelle Ähnlichkeit.

Jeder Platz geht an das Bild mit dem höchsten Wert — aber solange ein vorkommendes Motiv
unvertreten ist, nur aus den Bildern, die ein solches Motiv tragen. Das gewählte Bild vertritt
**alle** unvertretenen Motive, die es trägt; es wird nie ein Motiv gegen ein anderes abgewogen und
keine Stärke mit einer anderen verglichen. Diese Menge kann nicht leer sein: Ein vorkommendes Motiv
hat per Definition ein Trägerbild, und ist dieses gewählt, gilt das Motiv als vertreten.
„Innerhalb eines Motivs das qualitativ beste Bild" heißt: das mit dem höchsten **Wert** — die
Abwertung ist Teil der Auswahl, nicht ein Zusatz daneben.

**Determinismus:** Kandidaten beim Funktionseintritt nach `photo_id` sortieren, Events nach
`position` durchlaufen, Gleichstand immer über die kleinere `photo_id` (Konvention aus
`ranking.py`). Kein Schritt liest eine Datenbankreihenfolge, eine Mengeniteration oder eine Uhr.

### Wann gerechnet wird

Genau eine Rechenstelle, drei Auslöser:

- Am Ende von `worker.py::_build_grouping_and_rankings`, unmittelbar nach den Rangzeilen,
  **innerhalb** der bestehenden Phase `RANKING` — kein neuer `ClassificationPhase`-Wert, keine neue
  Fortschrittsstufe in der Oberfläche. Damit sind der Kriterien-Lauf und `rebuild_run_grouping`
  (Kamera-Versatz) abgedeckt.
- Bei Änderung des Richtwerts: `rebuild_run_selection(session, project_id)` rechnet **nur** den
  Vorschlag des letzten erfolgreichen Laufs neu, aus persistierten Zeilen, ohne Cloud-Aufruf und
  ohne Bildverarbeitung, synchron im Endpunkt (Muster: `api/cameras.py` → `rebuild_run_grouping`).
  Events und Rangzeilen bleiben unangetastet.

Verhältnis zu Story 6 (Album-Entwurf je Nutzer, #430): Diese Story liefert **den einen Vorschlag je
Lauf** und die Einstellung dazu, sonst nichts. `selection_position` ist die Anknüpfung, die Story 6
vorfindet. Dass der Vorschlag persistiert ist statt zur Lesezeit gerechnet, ist dafür die
Voraussetzung: Er darf sich unter einem daran arbeitenden Nutzer nicht bewegen — eine
Motivkorrektur wirkt deshalb erst beim nächsten Neuaufbau.

### Betroffene Dateien, in Umsetzungsreihenfolge

1. **Datenmodell + Migration.** `backend/src/photosort/models.py` (beide Spalten aus dem
   Datenmodell-Bezug, nullable, Docstrings entsprechend), eine Alembic-Revision unter
   `backend/alembic/versions/` (zwei `add_column`, Rückwärtsweg stellt die Struktur wieder her, nie
   die Daten), dazu ein Migrationstest im Muster von `backend/tests/test_migration_events.py` und
   der Durchlauf von `test_postgres_ddl_compatibility.py`.
2. **`backend/src/photosort/selection.py`** — neu, rein, DB-frei. Konstanten
   `EVENT_SHARE_CAP = 0.25`, `MOTIF_PRESENCE_THRESHOLD = 0.5`, `SIMILARITY_DECAY = 0.5`,
   `SIMILARITY_TIME_WINDOW = timedelta(minutes=15)`, `DEFAULT_TARGET_DIVISOR = 10`;
   `effective_target(...)`; Datenklassen `SelectionCandidate` (`photo_id`, `taken_at`, `quality`,
   `motif_strengths`) und `SelectionEvent` (`event_id`, `position`, `candidates`);
   `select_album_draft(events, target) -> dict[int, int]` (Foto → Platz im Event).
3. **DB-naher Teil im Worker.** Laden der auswahlfähigen Kandidaten (inkl.
   `excluded_document`-Filter über `PhotoMotifAssessment` und `load_effective_strengths`), Aufruf
   der reinen Funktion, Schreiben von `selection_position`; Einbau in
   `_build_grouping_and_rankings`; neue Funktion `rebuild_run_selection`. Ein Wächtertest hält
   fest, dass `selection_position` nur an dieser einen Stelle geschrieben wird (Muster: die
   Schreibstellen-Wächter in `test_models.py`).
4. **Projekt-Einstellung.** `backend/src/photosort/api/projects.py`: `ProjectOut` um
   `selection_target: int | None` und `effective_selection_target: int`; neuer Endpunkt
   `PUT /projects/{project_id}/selection-target`, Body `{"target": int | null}` mit deklarativer
   Ober-/Untergrenze (`ge=1`, statischer Deckel im Muster von `_MAX_QUERY_POSITION`), ruft nach dem
   Schreiben `rebuild_run_selection` in derselben Transaktion und antwortet mit `ProjectOut`.
   `null` setzt auf die Vorbelegung zurück.
5. **Lesepfad.** `backend/src/photosort/api/photos.py`: `_top_n_per_event_photo_ids` wird zu
   `_selection_photo_ids` (Fotos mit `selection_position IS NOT NULL` des letzten erfolgreichen
   Laufs, sortiert nach `(events.position, selection_position)`, `curation_position` =
   `selection_position`); der Query-Parameter `top_n_per_event` weicht `selection: bool = False`.
   `GET /projects/{id}/curation-candidates` bleibt unverändert — der volle Vorrat bleibt einsehbar.
6. **`backend/src/photosort/demo_state.py`** — schreibt `PhotoRanking`-Zeilen selbst und muss den
   Vorschlag über dieselbe Funktion setzen, sonst zeigt die Demo-Instanz (und damit
   `browse-app`/E2E) eine leere Auswahl.
7. **Frontend.** `frontend/src/api/photos.ts` (`selection` statt `topNPerEvent`),
   `frontend/src/api/types.ts` (`ProjectOut`-Felder), `frontend/src/hooks/usePhotos.ts`
   (`useCurationQuery(projectId)` ohne `topN`, Query-Key entsprechend),
   `frontend/src/pages/CuratePage.tsx`, `frontend/src/pages/pipeline/KuratierungStepPage.tsx`,
   `frontend/src/utils/projectRoutes.ts`. **Entfällt:** `frontend/src/utils/curationTopN.ts` samt
   Test. Die Gestaltung steht im Abschnitt „UI/UX".
8. **`docs/architecture.md`** im selben PR: Eintrag `PhotoRanking` (neue Spalte, neue Auswahlregel),
   die Endpunktliste (`selection` statt `top_n_per_event`, neuer `PUT`-Endpunkt), der
   Projekt-Eintrag (Richtwert). `docs/setup.md` bleibt unberührt — keine neue Umgebungsvariable,
   kein neuer Setup-Schritt.

### Breaking Changes

- `GET /projects/{id}/photos?top_n_per_event=N` fällt ersatzlos weg; ein Aufruf mit dem alten
  Parameter endet in `422`. Betroffen ist ausschließlich das eigene Frontend, ein Übergangsweg mit
  beiden Parametern entsteht bewusst nicht — er wäre eine zweite Auswahlregel.
- Die Route `/projects/:id/curate?topN=N` verliert ihren Suchparameter; ein alter Link bleibt
  gültig, der Parameter wird ignoriert.
- `ProjectOut` wächst um zwei Felder (additiv, nicht brechend).
- Bestehende Tests kodieren die alte Regel (`backend/tests/test_api_photos.py`,
  `frontend/src/pages/CuratePage.test.tsx`,
  `frontend/src/pages/pipeline/KuratierungStepPage.test.tsx`, `frontend/src/api/photos.test.ts`):
  umschreiben statt löschen — derselbe Aufbau prüft künftig die neue Aussage.
- Bestandsläufe tragen `selection_position = NULL` in allen Zeilen und zeigen damit einen leeren
  Vorschlag, bis ein neuer Lauf oder eine Richtwert-Änderung ihn erzeugt. Es gibt keine Migration,
  die den Vorschlag rückwirkend berechnet.

## UI/UX

Es entsteht keine neue Ansicht. Die Story berührt zwei bestehende Seiten: die Kuratierungs-Schritt-
seite bekommt die Richtwert-Einstellung, die Kuratierungsansicht verliert ihren Top-N-Parameter.
Grundlage ist [`specs/architecture/0004-design-system.md`](../architecture/0004-design-system.md);
es entsteht kein neues Muster und keine neue Komponentenausprägung.

### Richtwert-Einstellung auf `KuratierungStepPage.tsx`

An die Stelle der heutigen Einstellung „Top-Fotos pro Foto-Moment" tritt die Richtwert-Eingabe. Der
erklärende Absatz darüber lautet künftig sinngemäß: Der Vorschlag deckt alle Foto-Momente ab und
mischt in jedem die vorkommenden Motive. Der Richtwert ist ein Ziel, keine Obergrenze — reicht der
Bildbestand nicht, wird der Vorschlag kleiner; damit jeder Foto-Moment vorkommt, kann er auch
größer werden.

- **Feld:** bestehende `Input`-Komponente, `type="number"`, `min={1}`, beschriftet
  `Richtwert (Bilder)`, Breite wie heute (`w-24`). Ein echtes `<label htmlFor=…>` bleibt.
- **Leer heißt Vorbelegung.** Ist `selection_target === null`, ist das Feld leer — es zeigt **nicht**
  die vorbelegte Zahl, sonst wäre „vom System vorbelegt" von „selbst eingestellt" nicht mehr zu
  unterscheiden. Die Zahl steht stattdessen im Hinweistext unter dem Feld: „Leer = ein Zehntel der
  Bilderzahl (zurzeit N)", mit N aus `effective_selection_target`, per `aria-describedby` an das
  Feld gebunden. **`0` ist kein gültiger Wert** — der Endpunkt setzt `ge=1` durch; das Leeren des
  Feldes ist der einzige Weg zur Vorbelegung.
- **Zurücksetzen:** Feld leeren und speichern (sendet `{"target": null}`). Kein eigener Knopf.
- **Gespeichert wird beim Verlassen des Feldes** (`onBlur`) und bei `Enter`, **nicht** bei jedem
  Tastendruck und nicht zeitgesteuert nach kurzer Pause: Jedes Speichern rechnet den gesamten
  Vorschlag neu, und beim Tippen von „150" entstünden sonst drei Neuberechnungen. Ein unveränderter
  Wert löst keinen Aufruf aus.
- **Rückmeldung:** Während der `PUT` läuft, ist das Feld deaktiviert und der Zustand am Feld
  erkennbar (bestehendes Lade-/Deaktiviert-Muster, kein blockierender Dialog). Danach genügt der
  Hinweis „Vorschlag neu berechnet" für wenige Sekunden; ein dauerhafter Erfolgshinweis entsteht
  nicht. Schlägt der Aufruf fehl, erscheint eine `Alert`-Meldung (`variant="error"`) unter dem Feld,
  und das Feld behält den eingegebenen Wert, statt ihn stillschweigend zurückzusetzen.
- **Der Knopf „Kuratierung öffnen"** bleibt, verliert aber den Suchparameter: `…/curate` statt
  `…/curate?topN=N`.
- **Responsiv:** Das heutige `flex flex-wrap items-end gap-3` trägt weiter — auf schmalen Geräten
  rutscht der Knopf unter das Feld. Das Feld bleibt schmal, nicht `w-full`.

### Kuratierungsansicht `CuratePage.tsx`

- Der Abruf läuft über `selection: true` statt `topN`; `useCurationQuery(projectId)` kennt kein
  `topN` mehr, und die Route ignoriert einen alten `?topN=`-Parameter.
- **Die Bedingung `photos.length < topN && remainingCandidateCount <= 0` entfällt ersatzlos.** Sie
  beantwortete die Frage „warum sind es weniger als N?" und setzt einen Leseparameter voraus, den es
  nicht mehr gibt. An ihre Stelle tritt ein Hinweis allein für den Fall, dass der Vorschlag **kleiner
  als der wirksame Richtwert** ist: ein knapper Satz über der Fotoliste, der sagt, wie viele Bilder
  der Vorschlag umfasst und dass der Bildbestand für mehr nicht reicht. Beide Zahlen liegen vor
  (`photos.length`, `effective_selection_target`).
  **Keine Fehler- oder Warnoptik:** schlichter Absatz in Sekundärtext, **kein** `Alert`, kein
  `role="alert"`, keine Warnfarbe, kein Symbol — dasselbe Muster wie bei der Auffangkorb-Gruppe und
  bei der fehlenden Cloud-Einwilligung. Der Richtwert ist ein Ziel und keine Obergrenze; ein
  kleinerer Vorschlag ist damit das zugesagte Normalverhalten und kein Warnfall, und eine Warnoptik
  suggerierte Handlungsdruck, den es nicht gibt — mehr Bilder gibt es schlicht nicht.
- Ist der Vorschlag **größer** als der Richtwert, sagt die Oberfläche nichts: Die Abdeckung aller
  Foto-Momente ist die zugesagte Eigenschaft, kein Überraschungsfall.
- Der aufklappbare Kandidatenvorrat je Event bleibt unverändert — er zeigt weiterhin den vollen
  Bestand, unabhängig davon, wie viele Bilder des Events im Vorschlag stehen.

### Zustände

- **Leer, weil noch kein Lauf:** unveränderter Text („noch keine Kuratierung verfügbar").
- **Leer, weil keine Cloud-Freigabe:** unveränderter Text. Ohne Cloud-Grundlage gibt es keinen
  Qualitätswert und damit keinen Vorschlag.
- **Leer, weil Bestandslauf:** Ein vor dieser Änderung entstandener Lauf trägt keinen Vorschlag. Die
  Ansicht zeigt denselben Leer-Text; ein neuer Lauf oder eine Richtwert-Änderung erzeugt ihn.
- **Ladend:** bestehende Skeleton-Kacheln.
- **Fehler beim Neuladen nach einer Richtwert-Änderung:** bestehende Fehlerbehandlung der Ansicht;
  der zuletzt geladene Vorschlag bleibt sichtbar.

## Security

Das Feature ist **sicherheitsrelevant**: ein neuer Schreib-Endpunkt, der eine Eingabe von außen
annimmt und daraufhin synchron im Request über den gesamten auswahlfähigen Bestand des Projekts
rechnet, dazu ein Lesepfad, der seinen deckelnden Parameter verliert. Keine neuen Secrets, keine
neue externe Schnittstelle, kein Cloud-Aufruf, kein zusätzlicher Bilddatenfluss. Acht Auflagen,
einzeln abhakbar.

**S1 — Der neue Endpunkt hängt am router-weiten Torwächter, nicht an einem vergessbaren
Parameter.** `PUT /projects/{project_id}/selection-target` wird an `projects.router` registriert
(der trägt `dependencies=[Depends(get_current_user)]`), nie an `photos.router`. Angriffsmodell:
`photos.router` setzt den Torwächter je Endpunkt, und für diesen Weg gibt es keinen
Vollständigkeitstest — ein dort vergessener `current_user`-Parameter ist still öffentlich: kein
Fehler, keine 401, nur ein unauthentifizierter Schreibzugriff auf eine Projekteinstellung samt
Neuberechnung. An `projects.router` erfasst
`test_auth_guard.py::test_all_project_opencloud_and_stats_routes_require_token` den neuen Pfad von
selbst, weil es `projects.router.routes` durchläuft. Prüfbar: Registrierung am Router, plus ein
grüner 401-Fall ohne Token.

**S2 — Die Projektbindung steht ausgeschrieben in jeder Anweisung, die eine Zeile auflöst, und
stammt ausschließlich aus dem Pfadparameter.** `rebuild_run_selection(session, project_id)` löst den
letzten erfolgreichen Lauf über `project_id` + `status == SUCCESS` auf (Muster
`worker.py::rebuild_run_grouping`); jede lesende und jede schreibende Anweisung des Neuaufbaus
trägt `criterion_scoring_run_id == <dieser Lauf>`. Angriffsmodell: `PhotoRanking` trägt keine
`project_id` — die Lauf-Id ist die einzige Projektbindung. Fehlt das Prädikat auch nur in der
Schreibanweisung, setzt ein Aufruf unter Projekt A `selection_position` auf Rangzeilen eines fremden
Laufs; das Ergebnis ist ein kohärenter, aber fremder Vorschlag, dem die Antwort nichts ansieht.
Weder `target` noch ein Query-Parameter darf je eine Lauf-, Event- oder Foto-Id beisteuern.

**S3 — Grenzen am `target`, deklarativ am Body, vor jeder Verwendung.** `ge=1` plus statischer
Deckel (Muster `_MAX_QUERY_POSITION`); `null` bleibt ein eigener zulässiger Wert (der Rückweg zur
Vorbelegung) und ist von „Feld fehlt" zu unterscheiden. Angriffsmodell: Ein Pydantic-`int` ist
unbeschränkt, der Wert wird in eine INTEGER-Spalte geschrieben und geht in
`⌈0,25·T⌉`/`⌈T/m⌉`/`T − m`; jenseits von 2^63 ergibt das unter SQLite einen `OverflowError` und
damit eine `500` statt einer `422`. **Ausdrücklich nicht** die Schranke gegen Überlast — dafür S4
und S5.

**S4 — Der Auswahlzweig verliert seine Antwort-Obergrenze; `limit`/`offset` dürfen darin nicht halb
wirken.** Der Kuratierungszweig von `GET /projects/{id}/photos` ignoriert `limit`/`offset` und
hydratisiert jedes gelieferte Foto vollständig (`_photos_by_id` mit seinen `selectinload`s,
`load_effective_strengths`, `_to_photo_out`). Bisher deckelte `top_n_per_event <= 10` je Event diese
Menge; mit `selection: bool` entfällt der Deckel ersatzlos, und die neue Obergrenze ist der
auswahlfähige Bestand des Laufs. Das wird bewusst getragen (die Ansicht zeigt den Vorschlag als
Ganzes, beide Nutzer sind die Vertrauensbasis) — verbindlich ist allein: Entweder `limit`/`offset`
werden im Auswahlmodus weiterhin vollständig ignoriert und das steht am Endpunkt, oder sie wirken
vollständig. Bei halber Wirkung zeigt die Ansicht einen abgeschnittenen Vorschlag als vollständigen
an, und der Hinweis „der Bildbestand reicht für mehr nicht" sagt etwas Falsches — ein Zustand, den
keine Anzeige als fehlerhaft ausweist.

**S5 — Die Greedy-Vergabe führt die Ähnlichkeitsabwertung fortgeschrieben mit.** Nach jeder Wahl
ein Durchgang über die verbliebenen Kandidaten, der `ähnlichkeit(p, s*)` auf einen je Kandidat
mitgeführten Summanden addiert — nie bei jeder Bewertung erneut über alle bereits Gewählten
summiert. Ergebnisgleich (die Ähnlichkeiten stehen additiv im Exponenten), aber `O(n_i · k_i)` statt
`O(n_i · k_i²)` je Event. Angriffsmodell: Der Richtwert ist nicht der treibende Faktor —
`k_i ≤ n_i`, ein Richtwert oberhalb des Bestands sättigt bei „alles auswählen". Treibend ist der
Bestand, und der wächst mit jedem Scan. In der quadratischen Form kostet ein Event mit tausend
Kandidaten bei vollem Kontingent ~10⁹ Bewertungen synchron im Request, bei offener Transaktion; in
der fortgeschriebenen ~10⁶. Prüfbar an der reinen Funktion: ein Event mit mindestens 2000
Kandidaten und `target` = Bestandsgröße läuft innerhalb der Testlaufzeit durch.

**S6 — `409`, solange der Kriterien-Lauf des Projekts läuft.** Der Endpunkt weist mit `409` ab und
schreibt und rechnet nichts, solange der neueste `CriterionScoringRun` des Projekts `RUNNING` ist
(Muster `api/cameras.py::_reject_while_a_run_is_active`, hier enger: nur dieser Lauftyp schreibt
`selection_position`, der Scan nicht). Angriffsmodell: Der laufende Lauf liest den Richtwert am Ende
seiner Phase `RANKING`. Ohne den Wächter schreibt der Endpunkt den neuen Wert, während der Lauf noch
mit dem alten rechnet — Ergebnis ist ein Vorschlag nach altem Richtwert unter einer Oberfläche, die
den neuen anzeigt. Die Abweichung heilt erst beim nächsten Auslöser und ist bis dahin nirgends als
Fehler sichtbar.

**S7 — Die Auflage „Nutzer im Schlüssel" gilt unverändert weiter und wandert nicht mit
`curation_position` mit.** Bekommt `GET /projects/{id}/photos` (in **beiden** Modi) oder
`GET /projects/{id}/curation-candidates` eine Antwort-Zwischenspeicherung, ein `ETag` oder ein
`Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten. Grund ist
`PhotoOut.suggestion`, nicht `curation_position`. Angriffsmodell: Mit dieser Story wird
`curation_position` endgültig ein lauf-globaler Wert, und daraus folgt **nicht**, dass die Antwort
nutzerunabhängig wäre — `_to_photo_out` setzt `suggestion` weiterhin genau dann, wenn der
*anfragende* Nutzer noch keine eigene Bewertung hat. Die PWA hält heute nur statische Dateien vor;
ein `runtimeCaching` für API-Antworten ist der naheliegende nächste Schritt, der
Service-Worker-Cache ist je Browserprofil geteilt, und das JWT liegt in `localStorage`. Die
SICHERHEIT-Passage am Docstring von `_to_photo_out` bleibt in voller Aussage stehen.

**S8 — `selection_position` bleibt lauf-global und wird nie aus einem Nutzerbezug abgeleitet.**
`user_id` fließt in keine Abfrage und in keine Schreibanweisung des Neuaufbaus, und es entsteht
keine je Nutzer verschiedene Position. Angriffsmodell: Wird der Vorschlag je nutzerbezogen, fällt er
unter dieselbe Cache-Schlüssel-Auflage wie `suggestion` (S7) — Story 6 findet die Spalte dann
bereits vermischt vor und kann die beiden Ebenen nicht mehr trennen. Dass der Richtwert eine
geteilte Projekteinstellung ist und beide Nutzer denselben Vorschlag sehen, ist damit konsistent:
Projekte haben keinen Eigentümer, und zwischen den beiden Nutzern gilt kein Innentäter-Modell.

**Ausdrücklich geprüft und ohne Befund:** keine neue XSS-Fläche (beide neuen Werte sind Zahlen; kein
neuer Fremdtext in Antwort, Persistenz oder Log; der bei `422` von FastAPI zurückgespiegelte Rohwert
wird als React-Textknoten gerendert und nicht geloggt); keine Berührung von Secrets, `.env`,
Consent-Schalter, Kostenschätzung oder Bilddatenfluss; kein Rate-Limiting nötig, konsistent mit der
übrigen API. Die motivgeführte Vergabe hält die Eindämmung aus ADR 0091 Punkt 1 ein, weil sie je
Motiv ausschließlich gegen eine für alle Motive gleiche Konstante prüft und nie zwei Stärken
vergleicht.

**Nicht geschlossen, bewusst:** Zwei synchron rechnende Endpunkte schreiben auf dieselben Rangzeilen
(`PUT …/time-offset` über `rebuild_run_grouping`, `PUT …/selection-target` über
`rebuild_run_selection`). S6 deckt Endpunkt-gegen-Lauf ab, nicht Endpunkt-gegen-Endpunkt. Beide Wege
erzeugen einen vollständigen, gültigen Vorschlag; der schlechteste Ausgang ist ein Vorschlag nach
altem Richtwert, und die Absicherung läge in `api/cameras.py`, außerhalb der Dateiliste dieser
Story.

## Teststrategie

### Ebenen und wo die Grenze liegt

**Unit — `backend/tests/test_selection.py` (neu, Schwerpunkt).** Das Verfahren ist DB-frei. Jede
Zusicherung, die sich als Abbildung `(Events mit Kandidaten, T) → {photo_id: Platz}` schreiben
lässt, wird hier und **nur** hier geprüft: beide Stufen, Determinismus, Grenzwerte, Gleichstände,
sämtliche Edge Cases unten. Kein Worker-Lauf wiederholt eine dieser Aussagen.

**Integration DB/Worker — `backend/tests/test_worker_selection.py` (neu).** Genau das, was die reine
Funktion nicht kennt: Bildung der Kandidatenmenge (letzter erfolgreicher Lauf,
`rank_score IS NOT NULL`, kein `excluded_document`, wirksame Stärken über
`load_effective_strengths`), das Schreiben der Spalte, die Einbettung in
`_build_grouping_and_rankings` innerhalb Phase `RANKING`, und `rebuild_run_selection`.

**API — `test_api_projects.py` / `test_api_photos.py`.** Die zwei neuen `ProjectOut`-Felder, der
`PUT`-Endpunkt samt Grenzen, der Lesepfad `selection=true` samt Sortierung und `curation_position`,
das Wegfallen von `top_n_per_event`.

**Frontend — `vitest`.** Bedienverhalten des Richtwert-Feldes, die zwei Änderungen an `CuratePage`,
die Parameterbildung in `api/photos.ts`.

**E2E — kein neuer Spec.** Das Aufnahmekriterium (echte Geometrie, echtes CSS, echter Browser-Stack)
ist nicht erfüllt: Das Feld ist eine bestehende `Input`-Ausprägung im bestehenden
`flex flex-wrap`-Container. Der Bestandssatz läuft unverändert mit, ist dabei aber **nicht
folgenlos**: Setzt `demo_state.py` den Vorschlag nicht, zeigt `/curate` auf der Demo-Instanz eine
leere Liste, und die dortigen Specs bleiben grün — ihre Vorbedingungen hängen an Überschrift und
Scrollhöhe, nicht an Kacheln. Der Nachweis dagegen ist ein Kardinalitätsfall in
`test_demo_state.py`.

### Zusicherungen, die ohne eigenen Fall still brechen

Ein Fehler in diesem Verfahren wirft keine Ausnahme und verletzt kein Schema — er liefert eine
andere, plausibel aussehende Auswahl. Jede folgende Aussage braucht einen Fall, der bei ihrer
Verletzung rot wird.

**Invarianten als Nachsatz jedes Falls** (Muster `assert_event_invariants`): ein Helfer
`assert_selection_invariants(events, target, result)` läuft am Ende **jedes** Falls der reinen
Funktion und prüft vier Dinge zugleich — (a) jedes Event mit `n_i > 0` hat mindestens einen Platz;
(b) kein Event hat mehr als `min(n_i, max(⌈T/m⌉, ⌈0,25·T⌉))`; (c) die Plätze eines Events sind exakt
`{1 … k}`, 1-basiert und lückenlos; (d) kein Foto erscheint zweimal.

1. **Determinismus über gemischte Eingabereihenfolge.** Dieselbe Menge in mehreren aufgezählten
   Permutationen (Event-Reihenfolge **und** Kandidaten-Reihenfolge je Event) ergibt dasselbe Dict;
   verglichen wird die vollständige Abbildung samt Plätzen, nicht die Fotomenge. Der Aufbau muss
   **nicht-trivial** sein: mehr Kandidaten als Plätze, mindestens ein echter
   `rank_score`-Gleichstand, zwei Events mit gleichem `n_i`. Über einem eindeutigen Aufbau bestünde
   der Fall auch bei einer Implementierung, die über ein `set` iteriert.
2. **Die Anteilskappe verkleinert den Vorschlag nie — nur fehlende Kandidaten tun das.** Als
   Eigenschaft über eine Matrix statt an Beispielen: bei ausreichend Kandidaten je Event gilt
   `|Ergebnis| == max(T, m)`, parametrisiert über `m ∈ {1, 2, 3, 4, 5, 8, 13}` ×
   `T ∈ {1, 2, 7, 10, 100}`. Deckt „Vorschlag wird größer als der Richtwert" (`m > T`) und den
   Normalfall in einer Form.
3. **„Vorschlag kann kleiner werden"** als eigener Fall: `Σ n_i < T` → exakt `Σ n_i` Plätze, übrige
   verfallen. Mit exakter Kardinalität, nicht `≤ T`.
4. **Die Obergrenze greift, und die gekappten Plätze wandern.** Zwei Aufbauten, weil
   `max(⌈T/m⌉, ⌈0,25·T⌉)` sonst von jeder seiner Hälften allein ununterscheidbar ist: einer mit
   `m = 3` (dort gewinnt `⌈T/m⌉`), einer mit `m = 8` (dort `⌈0,25·T⌉`). In beiden ein Event mit weit
   überwiegender Bilderzahl; Assertion: dieses Event steht **exakt** auf seiner Kappe und die
   Gesamtzahl bleibt `T`. Dazu ein Aufbau, in dem die Umverteilung ein **zweites** Event an seine
   Kappe drückt, sonst ist die Wiederholung der Schleife ungeprüft.
5. **Terminierung der Umverteilung.** Ein Aufbau, in dem nach der ersten Runde Plätze frei bleiben
   und **kein** Event sie aufnehmen kann (alle an `n_i`), muss enden. Geprüft über einen
   Rundenzähler mit fester Obergrenze in der Funktion, nicht über eine Zeitgrenze.
6. **Kein Bild ohne Qualitätsurteil.** DB-nah, in **einem** Fall gegen ein bewertetes Foto, das den
   Platz bekommt: ein Foto mit Rangzeile und `rank_score IS NULL` und ein Foto ganz ohne Rangzeile
   bleiben beide ohne `selection_position`. Getrennt geschrieben bestünden beide Hälften auch bei
   einem durchgehend leeren Vorschlag.
7. **`excluded_document` erscheint nie im Vorschlag — und zählt auch nicht als Motivträger.** Zwei
   Fälle. Erstens: das ausgeschlossene Foto trägt den **höchsten** `rank_score` des Events und
   bekommt trotzdem keinen Platz, während dasselbe Foto ohne das Flag ihn bekommt (Paar in einem
   Fall). Zweitens: ein Motiv, das **nur** von einem ausgeschlossenen Foto über der Grenze getragen
   wird, gilt nicht als vorkommend und darf die Vergabe nicht umlenken.
8. **Gleichrangigkeit der Motive = Permutationsinvarianz über die Motivschlüssel.** Werden zwei
   Motivschlüssel in der gesamten Eingabe konsistent vertauscht, ist das Ergebnis identisch. Das ist
   der prüfbare Ausdruck von „keine Rangfolge"; ein Fall, der nur „beide Motive sind vertreten"
   prüft, bestünde auch bei einer festen Vorrangliste. Dazu ein **struktureller** Wächter:
   `selection.py` nennt `motifs.py` nicht und liest keine der beiden Band-Konstanten (ADR 0091
   Punkt 8).
9. **„Das gewählte Bild vertritt alle unvertretenen Motive, die es trägt."** Drei vorkommende Motive
   A, B, C; ein Bild trägt A **und** B über der Grenze, weitere tragen je genau eines. Bei zwei
   Plätzen geht Platz 1 an das AB-Bild, Platz 2 **muss** an einen C-Träger gehen, auch wenn ein
   reiner B-Träger den höheren Wert hätte. Mit nur zwei Motiven ist diese Aussage nicht von
   „vertritt eines davon" unterscheidbar.
10. **Die Motivpflicht schlägt den höheren Wert.** Ein Aufbau, in dem das wertvollste verbliebene
    Bild ausschließlich ein bereits vertretenes Motiv trägt und trotzdem übergangen wird.
11. **Die Abwertung wirkt auch innerhalb der eingeschränkten Menge.** Ein bereits gewähltes Bild
    trägt A und B, unvertreten ist C; von zwei C-Trägern liegt einer zeitnah beim gewählten Bild und
    teilt mit ihm A — er muss zurückfallen.
12. **Die Ähnlichkeitsformel in vier prüfbaren Teilen.** (a) Zeitgleich, geteiltes Motiv → Faktor
    exakt `0,5`. (b) **Summation**: zwei bereits gewählte zeitgleiche Bilder desselben Motivs →
    `0,25`. (c) Kein geteiltes Motiv → **keine** Abwertung, egal wie klein `Δt`. (d) `Δt` genau
    `15 min` → Faktor 1, und `Δt` deutlich **darüber** → ebenfalls Faktor 1, nie größer. Der letzte
    Teil ist der gefährlichste Fall des Verfahrens: `1 − |Δt|/15min` ohne `max(0, …)` ergibt bei
    30 Minuten `−1`, also `0,5^−1 = 2` — eine **Aufwertung** gerade der weit entfernten Bilder, ohne
    Ausnahme und ohne auffälliges Fehlerbild.
13. **Die Motivgrenze ist inklusiv.** Paar „wirksame Stärke genau `0,5`" (trägt) /
    „`math.nextafter(0.5, 0.0)`" (trägt nicht), je einmal für „Motiv kommt vor" und für „geteiltes
    Motiv".
14. **Die Startwerte stehen als Literale in genau einem Fall** (`EVENT_SHARE_CAP == 0.25`,
    `MOTIF_PRESENCE_THRESHOLD == 0.5`, `SIMILARITY_DECAY == 0.5`,
    `SIMILARITY_TIME_WINDOW == timedelta(minutes=15)`, `DEFAULT_TARGET_DIVISOR == 10`). Alle
    **übrigen** Fälle rechnen gegen die Konstanten, damit eine spätere Kalibrierung eine Zahl ändert
    statt eine Testwelle auszulösen.
15. **`effective_target`.** `NULL` → `max(1, ⌈Bilderzahl/10⌉)`; die Paare `10 → 1` und `11 → 2`
    trennen `⌈·⌉` von `//`; `0 Bilder → 1`. Mitwachsend gegen fest in **einem** Fall: derselbe
    Bestand wächst, der wirksame Wert wächst bei `NULL` mit und bleibt bei einer eingestellten Zahl
    stehen — plus die Assertion, dass `projects.selection_target` dabei `NULL` **bleibt**. „Die
    Vorbelegung wird nie geschrieben" ist die eigentliche Zusage; ein Test nur auf den Rückgabewert
    bestünde auch bei eingeschriebener Vorbelegung.
16. **`curation_position` trägt `selection_position`, nicht `rank_position`.** Der Aufbau muss die
    beiden **auseinanderfallen** lassen (ein Foto mit `rank_position = 4` auf Platz 1).
17. **Anzeigereihenfolge `(events.position, selection_position)`.** Der Aufbau widerspricht bewusst
    der `photo_id`- und der `event_id`-Reihenfolge.
18. **`rebuild_run_selection` rechnet nur den Vorschlag.** Zustandsschnappschuss der Events und
    Rangzeilen (als Tupel **ohne** Ids) vor und nach dem Aufruf — unverändert; dazu ein
    Anti-Leerlauf-Nachweis, dass die Plätze tatsächlich neu vergeben wurden (ein vorher von Hand
    verfälschter Platz muss danach fort sein), sonst bestünde ein `return` am Funktionsanfang die
    Zusage. Und: null Aufrufe am Cloud-/Bildverarbeitungs-Doppel.
19. **Ein entstandener Vorschlag bewegt sich nicht durch Bedienen der Ansicht.** Eine Motivkorrektur
    nach dem Lauf ändert `selection_position` nicht — und ändert ihn nach `rebuild_run_selection`
    sehr wohl. Paar in einem Fall.

### Edge Cases

- **`m = 0`** — alle Events ohne auswahlfähige Kandidaten. `⌈T/m⌉` ist eine Division durch Null: das
  Ergebnis muss ein leeres Dict sein, ohne Ausnahme. Zusammen mit **„gar keine Events"** und
  **„Events, aber alle Kandidaten ohne `rank_score`"** derselbe Ausgang über drei Wege.
- **Ein Event mit `n_i = 0` neben Events mit Kandidaten** — es zählt nicht in `m` und bekommt keinen
  Platz. Zählte es mit, verschöbe sich die gesamte Verteilung.
- **`m > T`**, z.B. `T = 2` bei fünf Events: exakt fünf Plätze. `T − m` ist hier negativ — eine
  Restverteilung, die damit rechnet, zieht Plätze ab.
- **`T = 1`**: bei einem Event genau ein Platz, bei drei Events genau drei.
- **Ein einziges Event**: die Kappe ist `min(n_1, max(T, ⌈0,25·T⌉)) = min(n_1, T)`, das Event bekommt
  alles. Eine Implementierung ohne das `max` kappt hier auf ein Viertel.
- **Sehr großer Richtwert** (`T > Σ n_i`): jeder Kandidat bekommt einen Platz, je Event lückenlos
  bis `n_i`.
- **Zwei Events mit identischem `n_i` und damit identischem Rest**, bei genau einem verbleibenden
  Restplatz: der Stichentscheid läuft über `position`, nicht über die Iterationsreihenfolge.
- **Restverteilung ohne Reste** (alle Anteile gehen glatt auf) und **Restverteilung, in der alle
  Reste 0 sind**.
- **Alle Bilder ohne Motiv über der Grenze**: keine vorkommenden Motive, die Einschränkung greift
  nie, es gibt keine Abwertung — das Ergebnis ist die reine `rank_score`-Reihenfolge. Gegenprobe:
  mit Motiven fällt sie anders aus.
- **Identische `rank_score`-Werte**, eingegeben in absteigender `photo_id`-Reihenfolge: die kleinere
  `photo_id` gewinnt. Dazu der schärfere Fall, in dem erst die **abgewerteten** Werte gleich sind —
  ein `max(…, key=…)` ohne expliziten zweiten Schlüssel nimmt dort das zuerst gesehene Element.
- **`selection_target` an den Rändern des Endpunkts**: `1` → `200`, `0` → `422`, `-1` → `422`, der
  statische Deckel → `200`, Deckel + 1 → `422`, `null` → `200` **und die Spalte ist danach `NULL`**
  (Assertion auf die Spalte, nicht nur auf den Statuscode), `1.5` / `"viele"` → `422`.
- **Ein Bild ohne `taken_at` gibt es nicht** und soll es nicht geben: `Photo.taken_at` ist
  `NOT NULL`, `SelectionCandidate.taken_at` ist deshalb `datetime`, nicht `datetime | None`. Der
  Fall wird **strukturell** ausgeschlossen statt mit einem Testfall beantwortet; ein `| None` an
  dieser Stelle ist ein Finding, weil es einen Zweig einführt, den kein Produktivzustand erreicht.

### Migrationstest

Im Muster von `backend/tests/test_migration_events.py` (Revision per `importlib`, Vorher-Schema von
Hand, `upgrade`/`downgrade` gegen SQLite in `tmp_path`), plus Durchlauf von
`test_postgres_ddl_compatibility.py`. Er hält fünf Dinge fest:

1. `down_revision` zeigt auf den zum Umsetzungszeitpunkt **tatsächlichen** Head.
2. `upgrade()` legt genau die zwei Spalten an, beide **nullable**.
3. **Kein `server_default`, an beiden Artefakten geprüft**: in der gerenderten Postgres-DDL der
   Revision **und** über ein `INSERT` ohne die Spalten gegen das aus `Base.metadata` erzeugte
   Schema. `NULL` trägt hier Bedeutung („nicht selbst eingestellt" / „gehört nicht zum Vorschlag");
   ein Default `0` oder `10` machte aus beidem stillschweigend eine Aussage.
4. **Die Datenlosigkeit ist hier eine ausgesprochene Zusage** und bekommt deshalb Bestandszeilen:
   Bestandsprojekte und Bestands-Rangzeilen überstehen `upgrade()` unverändert und tragen danach in
   **allen** Zeilen `NULL`.
5. `downgrade()` entfernt beide Spalten und lässt die übrigen Spalten und alle Zeilen stehen; ein
   danach erneutes `upgrade()` liefert die Spalten **leer** zurück.

### Schreibstellen-Wächter auf `selection_position`

Im Muster von `test_models.py::test_exactly_the_two_known_modules_write_taken_at`: Durchgang über
`rglob("*.py")` des Produktivpakets mit einem Syntaxbaum-Erkenner, Prüfung der Fundmenge auf
**Gleichheit** gegen `{"worker.py"}`, nicht auf Teilmenge — findet der Wächter die erlaubte Stelle
nicht mehr, prüft er für sie nichts.

**Eine bewusste Abweichung vom `taken_at`-Wächter:** Dort zählt das Konstruktor-Schlüsselwort
ausdrücklich **nicht**, weil das Anlegen einer Zeile harmlos ist. Hier ist es die gefährliche
Handlung — `demo_state.py` legt `PhotoRanking`-Zeilen selbst an, und ein
`PhotoRanking(selection_position=…)` wäre dort eine zweite Vergaberegel neben dem Verfahren, mit
demselben Ergebnis-Aussehen und ohne roten Test. Der Erkenner zählt deshalb **vier** Formen:
Attributzuweisung, Dict-Schlüssel, `.values()`-Schlüsselwort und Konstruktor-Schlüsselwort. Dazu je
Form ein eigener Mikrotest gegen ein literales Schnipsel, zwei Gegenproben (Lesen und Vergleichen
zählen nie) und eine Positiv-Gegenprobe gegen die leere Fundmenge.

`demo_state.py` bezieht den Vorschlag folglich über dieselbe Worker-Funktion. Dass die
Demo-Projekte danach einen **nicht leeren** Vorschlag tragen (Kardinalität > 0, jedes Event
vertreten), ist ein eigener Fall in `test_demo_state.py` — er ist der einzige automatisierte Träger
dieser Aussage.

### Bestehende Tests: umschreiben, nicht löschen

- **`backend/tests/test_api_photos.py`** — jede Erwartung „die besten N je Event" wird zur Erwartung
  „die Fotos mit `selection_position`". Zwei Fälle brauchen einen bewussten Nachfolger statt einer
  Umbenennung: `test_rejects_top_n_per_event_outside_valid_range` prüft künftig, dass der Parameter
  **gar nicht mehr existiert** (`top_n_per_event=2` ergibt `422`, nicht nur `=11`);
  `test_the_event_does_not_depend_on_the_requested_top_n` wird zu „der Event-Wert ist derselbe mit
  und ohne `selection=true`". Fälle, die `top_n_per_event` nur als **Vehikel** für Rangdetails oder
  Partitionsgröße benutzen, wechseln den Parameter und behalten ihre Erwartung — **eine dort
  geänderte Erwartung ist ein Finding**, kein Nachziehen.
- **`frontend/src/api/photos.test.ts`** — `topNPerEvent: 3` wird zu `selection: true`; dazu neu der
  Gegenfall, dass ohne Auswahlmodus **kein** `selection`-Parameter mitgeht.
- **`frontend/src/pages/CuratePage.test.tsx`** — `renderPage()` verliert `?topN=3`; **ein** Fall
  behält die alte URL und sichert zu, dass der Parameter ignoriert wird statt zu stören. Die Fälle
  um `photos.length < topN && remainingCandidateCount <= 0` werden zum Paar „Vorschlag kleiner als
  der wirksame Richtwert → Hinweistext mit beiden Zahlen" / „Vorschlag größer → **kein** Hinweis",
  dazu ein eigener Fall auf die **Abwesenheit** der Fehler-/Warnoptik (kein `role="alert"`, kein
  Symbol) — ein Positivtest auf den Text allein bestünde jede Hülle.
- **`frontend/src/pages/pipeline/KuratierungStepPage.test.tsx`** — die vier Top-N-Fälle werden zu
  Richtwert-Fällen: Link ohne Suchparameter; Speichern bei `onBlur` und bei `Enter`; **kein** Aufruf
  bei unverändertem Wert; Feld leeren sendet `{"target": null}`; Feld während des `PUT` deaktiviert;
  bei Fehlschlag erscheint die `Alert`-Meldung und das Feld **behält** den eingegebenen Wert. Der
  Klemm-Fall (`clamps a typed value above the range`) wird zum Nachweis, dass das Feld **nicht**
  klemmt, sondern der Endpunkt entscheidet. Dazu ein Fall, dass das Feld bei
  `selection_target === null` **leer** ist und die Zahl nur im per `aria-describedby` gebundenen
  Hinweistext steht.
- **`frontend/src/utils/curationTopN.test.ts`** entfällt mit der Datei. Sein Gegenstand bekommt
  **keinen** Frontend-Nachfolger: Das Frontend kennt die Grenze nicht mehr, es setzt `min={1}` am
  Feld, und die Durchsetzung liegt allein am Endpunkt. Eine neue Ableitungsdatei nur, um den Test zu
  retten, wäre eine zweite Wahrheit über die Grenze.
- **Zwei Registerstellen und ein fehlender Wächter.** Der neue `PUT`-Endpunkt wird in die
  eingefrorene Routenliste in `test_openapi_beschreibungen.py` aufgenommen und von
  `test_auth_guard.py::_protected_router_operations` mitgeführt. Dazu der Wächter aus Zusicherung 8:
  Die strukturelle Prüfung „keine Datei des Auswahlpfads liest die Anzeigebänder" (ADR 0091 Punkt 8)
  existiert im Bestand **nicht**. Sie entsteht hier, weil `selection.py` die erste Datei ist, die
  sie verletzen könnte — Form wie
  `test_motif_strengths.py::TestTheStructuralGuardAgainstASecondCase`, mit `selection.py`,
  `ranking.py`, `quality.py` und `worker.py` in der verbotenen Menge und einem Selbstschutz-Fall,
  dass die Konstanten überhaupt noch existieren.

### Coverage und Grenze

`selection.py` wird über die Unit-Ebene vollständig erreicht; der DB-nahe Teil und der neue Endpunkt
tragen je Erfolgsfall und die dokumentierten `422`-Fälle. Das Gate von 80 % ist dabei **nicht** die
bindende Größe — bindend ist die Fallliste oben.

**Bewusst nicht geprüft:** ob die Auswahl *gut* ist. Die drei Startwerte sind
dokumentiert-unkalibriert, und es gibt keinen Fotokorpus im Repository, gegen den ein anderer Wert
zu belegen wäre. Die Tests sichern das Verfahren, nicht sein Ergebnisurteil.

## Entscheidungen

- **Deckelung des Event-Anteils** (Daniel, 2026-09-13): Wurzel-Dämpfung plus Kappe bei
  `max(gleicher Anteil, 25 % aller Plätze)`, gekappte Plätze werden umverteilt. Nicht: Wurzel ohne
  harte Kappe, nicht proportional mit Kappe.
- **Stärke der Ähnlichkeitsabwertung** (Daniel, 2026-09-13): halbieren (`0,5`) je bereits
  gewähltem ähnlichen Bild, Zeitfenster 15 Minuten linear auslaufend. Nicht milder (−20 %), nicht
  stärker (vierteln).
- **Vorbelegung bei wachsendem Bildbestand** (Daniel, 2026-09-13): mitwachsend — solange nichts
  eingestellt ist, ist der Richtwert immer ein Zehntel des aktuellen Bestands; eine eingestellte
  Zahl bleibt fest.
- Der Vorschlag wird persistiert statt zur Lesezeit gerechnet, als Spalte an `photo_rankings` statt
  als eigene Tabelle: Ein Foto steht pro Lauf in genau einer Zeile, diese Zusage bleibt unangetastet.
- Das Motiv, unter dem ein Foto seinen Platz bekam, wird **nicht** persistiert. Eine einzelne Spalte
  zwänge zur Wahl eines von mehreren getragenen Motiven — das wäre eine Rangfolge zwischen Motiven
  und widerspräche ADR 0091. Ableitbar bleibt es aus Stärken plus Grenze.
- Kein neuer `ClassificationPhase`-Wert: Der Vorschlag ist die Fortsetzung der Phase `RANKING`.
- `excluded_document`-Fotos sind nicht auswahlfähig — fortgeschriebene Zusage aus ADR 0091 Punkt 2,
  keine Erweiterung der Story.
- Nicht gefüllte Plätze verfallen, statt über die Kandidatenzahl hinaus umverteilt zu werden: „Der
  Richtwert ist ein Ziel, keine Obergrenze" heißt, dass ein nicht füllbarer Platz entfällt.
- Die drei Startwerte (0,25 / 0,5 / 15 min) sind dokumentiert-unkalibriert, in der Klasse von
  `TIME_CLUSTER_GAP` und `LOCAL_CORRECTION_SPAN`; sie zu ändern ist eine Zahl in `selection.py` plus
  Neuaufbau, keine Migration.
- **Gespeichert wird beim Verlassen des Feldes, nicht beim Tippen.** Ein zeitgesteuertes Speichern
  kurz nach der letzten Eingabe löste beim Tippen einer dreistelligen Zahl mehrere vollständige
  Neuberechnungen aus.
- **`0` ist kein Weg zur Vorbelegung**, nur das leere Feld. Der Endpunkt setzt `ge=1` durch; zwei
  Wege zum selben Zustand wären zwei Aussagen an einer Stelle.
- Der Deckel auf `target` ist **keine** Überlastschranke — Antwortgröße und Rechenzeit sättigen beim
  auswahlfähigen Bestand. Die Schranke liegt stattdessen in der Komplexitätsklasse: Die
  Ähnlichkeitsabwertung wird je Kandidat fortgeschrieben (S5).
- Ein neuer E2E-Spec entsteht nicht; das Aufnahmekriterium ist nicht erfüllt. Ersatz ist der
  Kardinalitätsfall in `test_demo_state.py`.
- Der strukturelle Wächter zu ADR 0091 Punkt 8 („kein auswählender Codepfad liest die
  Anzeigebänder") existiert im Bestand nicht und entsteht in diesem Pull Request, weil
  `selection.py` die erste Datei ist, die ihn verletzen könnte.
- `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` sind im
  Zuge dieser Spec fortgeschrieben; die dort bisher zugesagte Obergrenze der Kuratierungsantwort
  (`top_n <= 10` je Partition) gilt ausdrücklich nicht mehr.

## Offene Fragen

Keine.

## Out of Scope

- Der nutzerbezogene Album-Entwurf, sein Zustand und seine Bedienung (Story 6, [#430](https://github.com/TheRealKoller/photosort/issues/430)). Diese Story liefert den einen Vorschlag je Lauf und die Einstellung dazu.
- Ein eigenes Maß für visuelle Ähnlichkeit. Duplikate und Serien bleiben Sache des Ausschuss-Schritts.
- Eine Migration, die den Vorschlag für Bestandsläufe rückwirkend berechnet.
- Eine Kalibrierung der drei Startwerte an einem echten Fotokorpus.
