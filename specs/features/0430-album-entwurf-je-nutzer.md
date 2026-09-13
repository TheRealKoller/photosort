# 0430 - Album-Entwurf je Nutzer: chronologisch nach Event, austauschen, aufnehmen, streichen

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [Issue #430](https://github.com/TheRealKoller/photosort/issues/430) (Story unter dem Zielbild [#424](https://github.com/TheRealKoller/photosort/issues/424))

**Umfang:** ein Mehrfaches des Richtwerts von rund 200 Zeilen. Drei Abschnitte tragen ihn, jeder aus
einem eigenen Grund: „Architektur / Umsetzung" führt die betroffenen Dateien je Pull Request auf,
weil der `developer` sie ohne eigene Planung abarbeitet; „Security" führt die Auflagen einzeln
abhakbar samt Angriffsmodell; „Teststrategie" benennt die Zusicherungen, die ohne eigenen Testfall
still brechen — ein Fehler in der Verschmelzung von Vorschlag und eigener Entscheidung wirft keine
Ausnahme, er liefert einen anderen, plausibel aussehenden Entwurf.

## Ziel

Nach den Stories 1 bis 4 liegen Events, Motivstärken und Albumtauglichkeit im System, aber es gibt
keinen Ort, an dem daraus ein Album wird. Die heutige Kuratierungsansicht zeigt eine einstellbare
Anzahl bester Bilder je Event und stammt aus dem abgelösten Kategorien-Denken; nacharbeiten lässt
sich daran nichts.

Diese Story schafft den Album-Entwurf: die Ansicht, in der die vorgeschlagene Auswahl entlang der
Reise sichtbar wird und in der beide Nutzer sie zügig zu ihrem Album nacharbeiten. Sie ist das
erste sichtbare Ergebnis des gesamten Umbaus — ohne sie bleiben die vier Grundlagen-Stories ohne
Wirkung. Sie löst außerdem eine bereits gegebene Zusage ein: Die Begründung, mit der das Modell die
Albumtauglichkeit bewertet hat, steht dort am Bild, wo der Entwurf nachgearbeitet wird.

**Bestandsdaten:** Bei Fertigstellung wird der Bestand zurückgesetzt und vollständig neu berechnet.
Es sind keine bestehenden Bewertungen oder Auswahlstände zu überführen.

## User Story

Als Nutzer, der aus einer Reise ein Album zusammenstellt, möchte ich die vorgeschlagene Auswahl
chronologisch entlang der Events durchgehen und einzelne Bilder austauschen, zusätzlich aufnehmen
oder streichen können, damit aus dem automatischen Vorschlag zügig mein Album wird und meine
Entscheidungen erhalten bleiben, statt bei jedem Durchgang von vorn zu beginnen.

## Akzeptanzkriterien

**Der Entwurf**

- [ ] Der Album-Entwurf zeigt die vorgeschlagene Auswahl chronologisch nach Events; jedes Event trägt seine Bezeichnung.
- [ ] Innerhalb eines Events stehen die Bilder chronologisch nach ihrer korrigierten Aufnahmezeit, bei gleicher Zeit nach der kleineren Foto-Id. Die Motivmischung erscheint als eine Textzeile am Event, die die vorkommenden Motive benennt und keinen Stärkewert und keine Zahl enthält.
- [ ] Jeder Nutzer hat je Projekt genau einen Entwurf. Es gibt keine mehrfachen oder benannten Fassungen. Der Entwurf des einen Nutzers ist im Entwurf des anderen nicht sichtbar: ein von B aufgenommenes Bild erscheint nicht in A's Entwurf, ein von B gestrichenes bleibt in A's Entwurf.
- [ ] Der Entwurf bleibt zwischen Sitzungen unverändert erhalten.
- [ ] Die tatsächliche Anzahl der Bilder darf vom Richtwert abweichen, nach oben wie nach unten. Der Kopfbereich nennt Richtwert und Ist-Anzahl nebeneinander; in beiden Abweichungsrichtungen trägt die Ansicht kein Element mit `role="alert"`, keine Fehlerfarbe, keinen Schalter, der die Anzahl angleicht, und sendet keine Anfrage, die den Vorschlag ändert. Ist kein Richtwert eingestellt, steht dort der wirksame Wert, nie eine leere Stelle.
- [ ] Am Bild ist die Begründung sichtbar, mit der das Modell seine Albumtauglichkeit bewertet hat.
- [ ] Solange kein erfolgreicher Kriterien-Lauf vorliegt, ist der Entwurf leer — auch dann, wenn der Nutzer bereits Bilder aufgenommen hat. Die Ansicht benennt den fehlenden Schritt und verlinkt ihn, statt leer zu bleiben.

**Austauschen**

- [ ] Zu jedem Bild des Entwurfs lassen sich Alternativen aus demselben Event aufrufen.
- [ ] Die Alternativen sind sortiert: zuerst Bilder mit gleichem Motiv nach Qualität absteigend, danach die übrigen Bilder des Events. Zeitliche Nähe ist kein Sortierkriterium.
- [ ] Ein Austausch ist Streichen plus Aufnehmen in einem Handgriff. Die Eventgruppe zeigt danach beide Bilder: das neue als „Im Album", das ersetzte an seiner Position als „Gestrichen". Es rückt nichts nach und es entsteht keine Lücke.
- [ ] Ein Austausch ist umkehrbar: Das ersetzte Bild steht danach im selben Alternativen-Dialog, trägt dort die Kennzeichnung „zuvor im Album", und ein Druck darauf stellt beide Bewertungszeilen auf den Stand vor dem Austausch zurück.

**Aufnehmen und Streichen**

- [ ] Jedes Bild des Kandidatenbestands des Events kann in den Entwurf aufgenommen werden — also jedes mit einer Rangzeile im letzten erfolgreichen Lauf, unabhängig von Qualitätswert und Vorschlag. Ein im Ausschuss-Schritt aussortiertes Bild hat keine Rangzeile und erscheint nicht unter den Alternativen; aufnehmen lässt es sich weiterhin im Raster, und es erscheint dann im Entwurf.
- [ ] Ein Bild kann ersatzlos gestrichen werden. Es rückt nichts nach.
- [ ] Aufnehmen und Streichen sind dieselbe Geste wie die bestehende Bewertung eines Fotos durch diesen Nutzer. Es entsteht keine zweite, daneben liegende Auswahlebene.
- [ ] Die Bedeutung dieser Bewertung wird damit ausdrücklich neu gefasst: Sie sagt, ob das Bild ins Album soll, und ist keine Aussage über seine Qualität. Ein bewusst aufgenommener schlechter Schnappschuss und ein gestrichenes gutes Bild sind beide gewollte, widerspruchsfreie Zustände.
- [ ] Die Auszeichnung als Favorit bleibt davon unberührt und wirkt nicht auf den Entwurf.

**Ein neuer Vorschlagslauf**

- [ ] Manuelle Entscheidungen überleben einen neuen Vorschlagslauf: Ein aufgenommenes Bild bleibt im Entwurf, ein gestrichenes bleibt draußen.
- [ ] Ordnet der neue Lauf ein aufgenommenes Bild einem anderen Event zu, erscheint es im Entwurf an seiner neuen Stelle.
- [ ] Sortiert der neue Lauf ein aufgenommenes Bild aus, bleibt es im Entwurf und trägt dieselbe Kennzeichnung wie ein aufgenommenes Bild, das der Lauf zwar als Kandidaten führt, aber nicht vorschlägt — beide Datenlagen ergeben einen Anzeigezustand.
- [ ] Nur Plätze, die der Nutzer nie angefasst hat, werden aus dem neuen Vorschlag neu befüllt.

**Bedienung**

- [ ] Austauschen, Aufnehmen und Streichen sind auf dem Handy genauso vollständig bedienbar wie am Desktop.
- [ ] Viele Bilder hintereinander durchzugehen geht zügig: (a) Aufnehmen und Streichen sind ein Druck auf eine Fläche, ohne Bestätigungsschritt und ohne Dialog; (b) die Entscheidung löst kein Neuladen der Entwurfsliste aus, und die Kachel bleibt an ihrer Stelle; (c) Alternativen öffnen ist ein Druck, der Austausch der zweite.

**Ablösung der bisherigen Ansicht**

- [ ] Die bisherige Kategorien-Kuratierungsseite wird mit dieser Story abgelöst. Nach ihr gibt es genau einen Ort, an dem die Auswahl entsteht und nachgearbeitet wird.

## Datenmodell-Bezug

Geändert: `ratings` (`status` wird nullable und trägt nur noch die Albumentscheidung, neue Spalte
`favorite`). Gelesen, nicht geändert: `photo_rankings.selection_position` (der Vorschlag des Laufs),
`projects.selection_target` (der Richtwert), `photo_album_suitability` (Qualitätsstufe und
Begründung), `events` (Zeitspanne und Reihenfolge), `photo_motif_strengths` (die Motive einer
Alternative). Es entsteht **keine** Entwurfstabelle. Nachzuziehen in
[`docs/architecture.md`](../../docs/architecture.md): der Eintrag `Rating`, der Kuratierungszweig
von `GET /projects/{id}/photos`, die Endpunktliste und die Route.

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0098`](../decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md) festgehalten
und dort begründet. Sie löst ADR
[`0071`](../decisions/0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md)
(Entscheidungen 1 und 5) und ADR
[`0097`](../decisions/0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md)
(Punkt 6) jeweils teilweise ab; beide Kopfzeilen werden im ersten Pull Request nachgetragen —
Kopfzeile, nicht Entscheidungstext.

### Gewählter Ansatz

**Der Entwurf ist abgeleitet, nicht gespeichert:**
`Entwurf(u) = Vorschlag(letzter erfolgreicher Lauf) ∪ Aufgenommen(u) \ Gestrichen(u)`. Es entsteht
keine Entwurfstabelle und kein Entwurfsfeld. Damit sind „genau ein Entwurf je Nutzer", „überdauert
die Sitzung" und „nur unangefasste Plätze werden neu befüllt" strukturell wahr statt durchgesetzt:
**„nie angefasst" ist die Abwesenheit einer eigenen Albumentscheidung** für dieses Foto, dasselbe
Muster wie „unbewertet" (`Rating`) und „nicht korrigiert" (`PhotoMotifCorrection`). Der Entwurf
eines Events ist eine Menge, keine Liste fester Fächer — ein „Platz" ist kein persistiertes Objekt.

**Aufnehmen und Streichen sind die bestehende Bewertung.** Abbildung:

| Geste | Schreibvorgang | Zustand danach |
|---|---|---|
| aufnehmen / zurückholen | `PUT /photos/{id}/rating {"status":"album_worthy"}` | im Entwurf, angefasst |
| streichen | `PUT /photos/{id}/rating {"status":"rejected"}` | nicht im Entwurf, angefasst |
| austauschen (A→B) | streichen(A) + aufnehmen(B), zwei Aufrufe | beide angefasst |
| nie berührt | keine Zeile bzw. `status IS NULL` | der Vorschlag entscheidet |

Der Entwurfs-Lesepfad bildet **keine** zweite Auswahlebene ab und schreibt nichts; er liest
`selection_position` (Lauf) und `ratings` (Nutzer).

### Datenmodell und Migration

`backend/src/photosort/models.py`, Tabelle `ratings`:

- `status: Mapped[RatingStatus | None]` — Wertevorrat nur noch `ALBUM_WORTHY` | `REJECTED`, `NULL`
  heißt „keine Albumentscheidung". Der Docstring fasst die Bedeutung neu: die Zeile sagt, ob das
  Bild ins Album soll, und ist **keine** Aussage über die Bildgüte (die steht in
  `PhotoAlbumSuitability`).
- `favorite: Mapped[bool]`, `default=False`, `server_default=sa.false()` in Modell **und**
  Migration — nie die Zeichenkette `"false"`: die rendert wörtlich `DEFAULT 'false'`, ein
  Textliteral. Postgres wandelt es still um, SQLite legt den String `'false'` ab, der sich beim
  Lesen als **wahr** liest. Ein eigener Fall hält das an beiden Artefakten fest.
- `RatingStatus.FAVORITE` entfällt aus dem Enum. **`PhotoScore.suggested_status` benutzt dieselbe
  Enum-Klasse** und wird deshalb in derselben Migration mitgeführt — entweder eigener Wertevorrat
  oder Konvertierung der Bestandszeilen (Auflage S11).
- Invariante, am Endpunkt gehalten und getestet: Es gibt keine Zeile mit
  `status IS NULL AND favorite IS FALSE` — sie wird gelöscht.

Eine Alembic-Revision unter `backend/alembic/versions/` (`down_revision` auf den zum
Umsetzungszeitpunkt tatsächlichen Head), im Muster von `test_migration_selection.py` getestet, plus
Durchlauf von `test_postgres_ddl_compatibility.py`:

1. `batch_alter_table` (SQLite): `favorite` anlegen, `status` nullable machen.
2. Ein `UPDATE ratings SET favorite=true, status=NULL WHERE status='favorite'` — die Bestandsdaten
   werden laut Story ohnehin zurückgesetzt; die Konvertierung verhindert, dass ein nicht
   zurückgesetzter Bestand einen Lesepfad auf einen unbekannten Enum-Wert laufen lässt.
3. `downgrade()`: `status='favorite'` für Zeilen mit `favorite AND status IS NULL`, Spalte
   entfernen, `status` wieder NOT NULL. Stellt die Struktur wieder her, nie die Daten.

### API

**Bewertung (`api/ratings.py`)**

- `PUT /photos/{id}/rating`, Body `{"status": "album_worthy"|"rejected"}` — setzt die
  Albumentscheidung und lässt `favorite` **unberührt**. `user_id` weiterhin ausschließlich aus
  `current_user`.
- `DELETE /photos/{id}/rating` — nimmt **nur** die Albumentscheidung zurück (`status = NULL`); die
  Zeile bleibt stehen, solange `favorite` gesetzt ist, sonst wird sie gelöscht. Idempotent.
- **Neu:** `PUT /photos/{id}/favorite`, Body `{"favorite": bool}` — setzt/entfernt das Kennzeichen
  und lässt `status` unberührt; legt die Zeile bei Bedarf an und löscht sie, wenn danach beides
  leer ist. Muster und Fehlerbild wie `set_motif_correction` (`404` ohne Foto, `409` bei
  gleichzeitigem Schreibversuch über den Unique-Constraint nach `flush`).

**Lesepfad (`api/photos.py`)**

- `RatingOut` (in `PhotoOut.ratings[]`) wird zu
  `{user_id, username, status: RatingStatus|null, favorite: bool}`.
- `RatingFilter`: `unrated` heißt künftig „keine Albumentscheidung"
  (`own_rating.id IS NULL OR own_rating.status IS NULL`); `favorite` filtert auf die Spalte;
  `album_worthy`/`rejected` unverändert auf `status`. **Auch der `suggested`-Zweig und
  `_to_photo_out::has_own_rating` stellen auf „keine eigene Albumentscheidung" um**, nicht auf
  „keine eigene Zeile": Ein nur als Favorit markiertes Bild behält damit seinen Ausschuss-Vorschlag.
  Beide gemeinsam, sonst bricht der bestehende Paritätsfall
  `test_list_photos_suggested_filter_matches_has_suggestion_parity`.
- `RankingOut` bekommt **ein** neues Feld `proposed: bool` (`selection_position IS NOT NULL`),
  lauf-global und auf **allen** Lesepfaden befüllt, nicht nur im Entwurfsmodus.
- **Entwurfsmodus:** `selection: bool` wird zu `draft: bool`. `selection` bleibt als
  `None`-typisierter, schemaloser Parameter stehen (Muster `top_n_per_event`), damit ein
  stehengebliebener Aufrufer `422` bekommt statt still den Listing-Zweig.
  `_selection_photo_ids` wird zu `_draft_photo_ids(session, project_id, user_id)`: Fotos mit
  `selection_position IS NOT NULL` **oder** eigener Bewertung `album_worthy`, beide auf den letzten
  erfolgreichen Lauf bezogen, ohne Ablehnungsfilter; Reihenfolge
  `(events.position, photos.taken_at, photos.id)` — **innerhalb eines Events chronologisch nach der
  korrigierten Aufnahmezeit**, nicht nach `selection_position`. Der Sortierschlüssel ist damit
  total und für vorgeschlagene wie aufgenommene Bilder derselbe. Nach `selection_position` mit
  `NULLS LAST` zu sortieren ist ausgeschlossen: Ein aufgenommenes Bild hat keinen Platz im
  Vorschlag und stünde dann stets am Ende seiner Gruppe — ein Austausch ersetzte das Bild nicht an
  seiner Stelle, sondern verschöbe es ans Gruppenende. `curation_position` trägt weiterhin den
  Platz in der angezeigten Auswahl des Events (lückenlos ab 1 über die gelieferte Reihenfolge
  vergeben). `limit`/`offset` bleiben in diesem Zweig **vollständig** wirkungslos.
- **Event ohne Rangzeile:** `_event_and_location_by_photo_id` nimmt künftig eine fertige Abbildung
  `photo_id → event_id` entgegen statt der Rangzeilen. Der Entwurfszweig baut sie aus den
  Rangzeilen und ergänzt für aufgenommene Fotos ohne Rangzeile die Zuordnung über
  `events.py::event_for_time`.
- **Neu:** `GET /projects/{id}/draft-alternatives`, Parameter `event_id` (Pflicht), `photo_id`
  (Pflicht), `limit`/`offset` — alle mit `ge=1`/`le=_MAX_QUERY_POSITION` wie am bisherigen
  Kandidaten-Endpunkt. Liefert `PhotoListOut` mit `total` = Restmenge. Inhalt: die Fotos dieses
  Events im letzten erfolgreichen Lauf **abzüglich** der Fotos des Entwurfs dieses Nutzers
  (gestrichene sind also enthalten — daraus folgt die Umkehrbarkeit). Projektbindung ausschließlich
  über `criterion_scoring_run_id` aus dem Pfadparameter, in **jeder** Abfrage ausgeschrieben, auch
  der Zählabfrage. Löst `photo_id` in diesem Event dieses Laufs keine Zeile auf, ist die Antwort
  `200` mit `items: []` und `total: 0` — kein Fehlertext und keine Rückspiegelung übergebener Werte.
- `GET /projects/{id}/curation-candidates` entfällt ersatzlos (samt seiner Tests, umgeschrieben
  statt gelöscht).

### Reine Funktionen (DB-frei, wie `ranking.py`/`quality.py`/`events.py`/`selection.py`)

- `events.py::event_for_time(spans, taken_at) -> int` — Event-Zuordnung über Containment, sonst über
  den kleinsten Abstand zu einer Grenze, bei Gleichstand das frühere Event. Deterministisch, ohne
  Uhr.
- `selection.py`: `_carried_motifs` wird öffentlich (`carried_motifs`), dazu
  `order_alternatives(reference, candidates) -> list[int]` mit dem Sortierschlüssel
  `(0 wenn geteiltes Motiv sonst 1, -quality, photo_id)`; `quality is None` sortiert innerhalb
  seiner Gruppe ans Ende. Die Motivgrenze bleibt damit an genau einer Stelle
  (`MOTIF_PRESENCE_THRESHOLD`), und der bestehende strukturelle Wächter („kein auswählender
  Codepfad liest die Anzeigebänder") behält seine Aussage.

### Frontend

- **Neu:** `frontend/src/pages/AlbumDraftPage.tsx` unter der Route
  `PROJECT_ROUTE_PATHS.album = '/projects/:projectId/album'`. Gruppierung über `photo.event.id` (auf
  jedem Eintrag gesetzt), Reihenfolge = Antwortreihenfolge des Servers; die Ansicht bildet weder
  Auswahl noch Schwelle nach. Tag-/Event-Überschriften, Klapp-Zustand und die Leerzustände der
  bisherigen Seite werden übernommen, nicht neu erfunden.
- **Entfällt:** `CuratePage.tsx` (+ Test), `components/CurationCandidates.tsx`,
  `hooks/usePhotos.ts::useCurationCandidatesQuery`, `api/photos.ts::listCurationCandidates`,
  `utils/rankings.ts::curatedRanking` (+ Test; einziger Nutzer war `CuratePage`), der
  `curate`-Eintrag in `utils/projectRoutes.ts`.
- **Kachel:** `CurationPhotoTile` wird zur Entwurfskachel — die Begründung des Modells
  (`album_suitability.reason`) bleibt unverändert in der Fußzeile (reiner React-Textknoten, nie
  `dangerouslySetInnerHTML`, nie in `href`/`src`/`style`), an die Stelle von „Verwerfen" tritt der
  Zweizustand aufgenommen ⇄ gestrichen plus der Zugang zu den Alternativen. Ein Eintrag mit
  `ranking.proposed === false` und eigener Bewertung `album_worthy` wird als „aufgenommen, vom
  aktuellen Vorschlag nicht getragen" ausgewiesen. Die Gestaltung steht im Abschnitt „UI/UX".
- **Alternativen** werden erst beim Öffnen geladen (`enabled`-Muster) — eine Abfrage je geöffnetem
  Bild, nie eine je Kachel.
- **Durchsatz (verbindlich, ADR 0098 Punkt 6):** Eine Entscheidung löst **kein** Neuladen der
  Entwurfsliste aus. Der bestehende breite `invalidateQueries(['photos', projectId])` der
  Bewertungsmutation trifft den Entwurfsschlüssel mit; die Entwurfsansicht bekommt deshalb eine
  eigene Mutation, die (a) die Bewertung schreibt, (b) den betroffenen Eintrag im Cache der
  Entwurfsabfrage fortschreibt und (c) die übrigen Fotoabfragen des Projekts invalidiert. Ein gerade
  gestrichenes Bild bleibt dadurch an seiner Stelle stehen, auch wenn es beim nächsten vollständigen
  Laden nicht mehr Teil der Antwortmenge ist.
- `utils/ownRating.ts` bekommt `ownFavorite(ratings, username): boolean`; `ownRatingStatus` liefert
  künftig `RatingStatus | null` mit `null` auch bei vorhandener reiner Favoritenzeile.
- Bewertungsleiste (`RatingButtons`, Tastenbelegung in `PhotoDetailPage`), `RatingBadge`,
  `PhotoGridPage`-Filter, `PhotoComparePage` und `ProjectStatsPage` ziehen die Trennung von
  Albumentscheidung und Favorit nach.

### Reihenfolge der Umsetzung — drei Pull Requests

Die Story ist in einem PR nicht sinnvoll zu tragen: Sie ändert das Bewertungsmodell samt Migration,
ersetzt eine Ansicht vollständig und führt einen neuen Lese-Endpunkt ein. Jeder der drei Schnitte
ist für sich grün, für sich mergebar und hinterlässt keinen Übergangszustand mit zwei Auswahlwegen.

**PR 1 — „Bewertung heißt Albumentscheidung"**

1. `models.py` (Spalten, Enum, Docstrings) + Alembic-Revision + Migrationstest.
2. `api/ratings.py` (beide bestehenden Endpunkte, neuer Favoriten-Endpunkt), `RatingOut`,
   `RatingFilter`, `api/stats.py`.
3. `demo_state.py` (`_RATED_STATUS_ORDER` trägt den Favoriten nicht mehr im Statusvorrat).
4. Frontend: `api/types.ts`, `utils/ownRating.ts`, `RatingButtons`, `RatingBadge`,
   `PhotoDetailPage` (Tastenbelegung), `PhotoGridPage`, `PhotoComparePage`, `ProjectStatsPage`.
5. `docs/architecture.md` (Eintrag `Rating`), Kopfzeilen-Nachtrag in ADR 0071 und 0097.

**PR 2 — „Der Album-Entwurf"**

1. `events.py::event_for_time` (rein, mit Tests) — Datenzugriff kennt sie noch nicht.
2. `api/photos.py`: `proposed` an `RankingOut`, `_draft_photo_ids`, Umbau von
   `_event_and_location_by_photo_id` auf die Event-Abbildung, Parameter `draft`/`selection`-Riegel.
3. Frontend: `api/photos.ts`/`usePhotos.ts` (Entwurfsabfrage, eigene Entscheidungsmutation),
   `AlbumDraftPage.tsx` samt Route, Kachel-Umbau, Wegfall von `CuratePage` und `curatedRanking`.
4. e2e: `no-horizontal-scroll`, `popover-position` auf die neue Route.
5. `docs/architecture.md` (Kuratierungszweig, Route).

**PR 3 — „Austauschen"**

1. `selection.py::carried_motifs`/`order_alternatives` (rein, mit Tests).
2. `api/photos.py`: `GET /projects/{id}/draft-alternatives`; Wegfall von
   `GET /projects/{id}/curation-candidates`; Registerstellen (`test_openapi_beschreibungen.py`).
3. Frontend: Alternativen-Dialog an der Kachel, Austausch als zwei Schreibvorgänge, Wegfall von
   `CurationCandidates` und `useCurationCandidatesQuery`.
4. `docs/architecture.md` (Endpunktliste).

### Breaking Changes

- `ratings.status` verliert den Wert `favorite`; `RatingOut` wächst um `favorite` und macht `status`
  nullable. Betroffen ist ausschließlich das eigene Frontend.
- `GET /projects/{id}/photos?selection=true` endet in `422`; der Modus heißt `draft=true` und ist
  **nutzerabhängig**.
- `GET /projects/{id}/curation-candidates` entfällt ersatzlos.
- Die Route `/projects/:id/curate` entfällt ohne Weiterleitung.

## UI/UX

**Seitenaufbau.** Neue Seite `AlbumDraftPage` unter `/projects/:projectId/album`, Titel
„Album-Entwurf". Zwei Ebenen wie bisher: Tages-Abschnitt (klappbar, `aria-expanded`/`aria-controls`,
Klapp-Zustand wie in `CuratePage`), darin je Event eine Überschrift mit der Bezeichnung des Events
und der Anzahl seiner Bilder im Entwurf. Reihenfolge ist ausschließlich die Antwortreihenfolge des
Servers; die Seite sortiert nicht nach und bildet keine Auswahlregel und keine Schwelle nach.

**Motivmischung.** Unter der Event-Überschrift stehen die im Entwurf dieses Events vertretenen
Motivnamen als eine Textzeile, alphabetisch, **ohne Stärkewerte und ohne Rangfolge**. Keine Werte,
keine Balken, keine Reihung nach Stärke — ein Vergleich von Motivstärken untereinander findet an
keiner Stelle der Oberfläche statt. Auf der Kachel selbst erscheinen Motivnamen weiterhin nicht;
die Stärken stehen im Info-Popover.

**Richtwert.** Der Kopfbereich nennt den Richtwert und die tatsächliche Anzahl („142 von etwa 130").
Eine Abweichung nach oben wie nach unten ist ein neutraler Hinweis in der Farbe des Fließtextes —
kein Warnton, kein Fehlerzustand, keine Schaltfläche, die sie beseitigt.

**Die Entwurfskachel.** `CurationPhotoTile` trägt weiter Bild, Ecken-Marker und Info-Popover. Die
Fußzeile trägt `QualityMeter`, die Begründung des Modells (`album_suitability.reason`,
`line-clamp-2`, im DOM vollständig, reiner Textknoten) und **zwei** Trefferflächen nebeneinander:

- den Zweizustand der Albumentscheidung (`aria-pressed`), Beschriftung „Im Album" ⇄ „Gestrichen";
- „Alternativen", öffnet den Austausch-Dialog.

Die Fußzeile verliert damit bewusst ihre bisherige Ein-Trefferflächen-Regel. Beide Flächen sind auf
dem Telefon sichtbar mindestens 44px hoch (`h-11 sm:h-8`, wie die Bewertungsleiste), liegen mit 12px
Abstand nebeneinander und tragen den Dateinamen im zugänglichen Namen.

**Der Zustand „aufgenommen, nicht getragen".** Ein Eintrag mit `ranking.proposed === false` und
eigener Entscheidung `album_worthy` trägt ein `Badge` „nicht vorgeschlagen" über der Fußzeile. Er
wird nicht gedämpft und nicht ans Ende sortiert.

**Gestrichen.** Ein gestrichenes Foto bleibt an seiner Stelle und behält den bestehenden
Anzeigezustand der `PhotoCard` (gedämpfte Fläche, `RatingBadge`, durchgestrichener Dateiname). Es
verschwindet nicht, und nichts rückt nach.

**Alternativen — Dialog, kein Popover.** Der Austausch läuft in `ui/dialog`: Der Inhalt ist ein
Bildraster mit eigenem Blätterweg, das auf 360px Breite die volle Fläche braucht, und der Vorgang
verlangt Fokusfang und Escape. Der Dialog trägt als Titel den Event-Namen, darunter das Bezugsbild
klein und das Raster der Alternativen (`grid-cols-2 sm:grid-cols-3`), jede mit `QualityMeter`.
Reihenfolge ist die Antwortreihenfolge des Servers. Ein Tippen auf eine Alternative führt den
Austausch aus (streichen des Bezugsbilds, aufnehmen der Alternative), schließt den Dialog und setzt
den Fokus auf die nun an dieser Stelle stehende Kachel. Geladen wird erst beim Öffnen, eine Abfrage
je geöffnetem Bild.

**Umkehrbarkeit.** Das ausgetauschte Bild ist danach selbst Teil der Alternativen desselben Events
und trägt dort ein Abzeichen „zuvor im Album". Ein Tippen darauf holt es zurück. Es gibt keinen
eigenen Rückgängig-Knopf und keinen Verlauf.

**Zustände.** Ladend: Skeleton-Raster wie in `CuratePage`. Fehler: `Alert` mit der Meldung des
Servers und einem Wiederholen. Kein Entwurf: ein Text, der den fehlenden Schritt benennt („Noch kein
Auswahlvorschlag — führe die Kriterien-Bewertung aus"), nicht eine leere Liste. Event ohne Bilder im
Entwurf: Die Gruppe bleibt mit ihrer Überschrift stehen und sagt „Kein Bild im Entwurf", damit ein
leergeräumtes Event nicht verschwindet.

**Favorit neben der Albumentscheidung.** `RatingButtons` behält drei Einträge und die Belegung
1/2/3. „Favorit" (1) ist ab jetzt ein **unabhängiger** Zweizustand: Ein- und Ausschalten lässt
„Album-würdig" (2) und „Verwerfen" (3) unberührt, und umgekehrt. Sichtbar wird das dadurch, dass
Favorit gleichzeitig mit einem der beiden anderen gefüllt sein kann. `RatingBadge` zeigt beide
nebeneinander. Der Rasterfilter in `PhotoGridPage` behält seine Einträge; „unbewertet" heißt dort
künftig „keine Albumentscheidung", und „Favorit" filtert auf das eigene Kennzeichen.

**Barrierefreiheit.** Der Album-Zweizustand ist ein `button` mit `aria-pressed`, kein Umschalter mit
eigener Rolle. Der Dialog fängt den Fokus, schließt mit Escape und gibt den Fokus an die auslösende
Kachel zurück, wenn kein Austausch stattfand. Alle Trefferflächen sind mit Tab erreichbar und mit
Enter/Space auslösbar; kein Zustand hängt allein an Hover. Die Motivzeile bricht um, statt waagerecht
zu scrollen.

## Teststrategie

Drei Pull Requests, je ein eigener Rot-Grün-Zyklus. **Reine Funktionen zuerst:**
`selection.py::order_alternatives` und `events.py::event_for_time` sind ohne Session vollständig
prüfbar und müssen grün sein, bevor der Endpunkt, der sie aufruft, seinen ersten Fall bekommt.
Innerhalb von PR1 gilt dieselbe Reihenfolge zwischen Migration und API: erst das Schema samt
Konvertierung, dann die Endpunkte — ein Endpunktfall gegen das alte Schema ist nicht rot, sondern
ein Importfehler.

### Die Zusicherungen, die ohne eigenen Testfall still brechen

Falschergebnis statt Ausnahme, grüne Suite, kein Fehlerbild. Diese Liste ist verbindlich.

1. **Der Entwurf ist eine Vereinigung, keine Verkettung.** Ein Foto, das der Lauf vorschlägt UND
   das der Nutzer aufgenommen hat, steht genau einmal in der Antwort.
2. **Gestrichen wirkt in zwei Endpunkten verschieden — derselbe Fall prüft beides.** Ein
   gestrichenes Foto des Vorschlags bleibt im Entwurfszweig (mit `rejected` in `ratings[]`) UND
   steht zugleich unter den Alternativen seines Events. Zwei getrennte Fälle sind beide grün, wenn
   ein gemeinsamer Helfer eine der beiden Seiten falsch bedient.
3. **„Nur unangefasste Plätze werden neu befüllt" ist nur über zwei Läufe sichtbar.** Ein Fall,
   drei Fotos: unangefasst (folgt Lauf 2), aufgenommen (bleibt), gestrichen (bleibt draußen).
   Getrennt geschrieben bestehen die Hälften auch bei einer Implementierung, die immer oder nie den
   neuen Lauf gewinnen lässt.
4. **Die Reihenfolge des Entwurfs braucht einen totalen Sortierschlüssel.** Ein unvollständiges
   `ORDER BY` ist unter SQLite zufällig stabil und unter Postgres nicht — der Bruch erscheint erst
   produktiv, als Liste, die sich bei jedem Laden anders ordnet. Der Nachweis ist eine in
   geschüttelter Reihenfolge eingefügte Zeilenmenge plus eine Assertion auf die vollständige
   Id-Folge.
5. **Die Alternativen-Sortierung: `None` ans Ende seiner Gruppe.** Ein Bild ohne Qualitätswert, das
   ein Motiv mit dem Bezugsbild teilt, steht vor jedem Bild ohne geteiltes Motiv. Eine
   Implementierung, die alle `None` global ans Ende schiebt, besteht jeden Fall ohne diesen Aufbau.
6. **Qualität `0.0` ist kein fehlender Wert.** Ein Kandidat mit `0.0` steht vor jedem `None`
   derselben Gruppe; `quality or 0` verliert die Unterscheidung lautlos.
7. **Die Motivgruppe ist binär.** Drei geteilte Motive schlagen ein geteiltes nicht; entschieden
   wird allein „mindestens eines", und die Grenze ist `MOTIF_PRESENCE_THRESHOLD`, inklusiv, für
   alle Motive dieselbe.
8. **Zeitliche Nähe ist kein Sortierkriterium der Alternativen.** Ein zeitlich benachbarter
   Kandidat geringerer Qualität bleibt hinter dem entfernten höherer Qualität.
9. **Gleichstand bricht über die kleinere `photo_id`, und der Nachweis ist eine Permutation.** Der
   Aufbau muss echten Gleichstand enthalten, sonst ist der Fall leer.
10. **`event_for_time`: Enthaltensein schlägt Nähe.** Eine Zeit kurz vor dem Ende eines langen
    Events gehört diesem Event, auch wenn der Abstand zum `started_at` des nächsten kleiner ist als
    der zum eigenen `started_at` — genau der Fall, den eine Abstandsmessung nur gegen `started_at`
    falsch beantwortet.
11. **`event_for_time`: beide Grenzen inklusiv, berührende Spannen gehen an das frühere Event.**
    `ended_at(A) == started_at(B)` ist über zwei Aufnahmen derselben Sekunde mit Ortssprung
    erreichbar; ohne Fall hängt das Ergebnis an der Aufzählungsreihenfolge.
12. **`event_for_time`: bei exakt gleichem Abstand gewinnt das frühere Event.**
13. **Die Zuordnung liest die korrigierte Aufnahmezeit.** Ein gesetzter Kameraversatz, der das Foto
    in ein anderes Event schiebt, ist der einzige Fall, der `taken_at` von `taken_at_original`
    trennt.
14. **Die Rangzeile hat Vorrang vor der Zeitzuordnung.** Ordnet der neue Lauf ein aufgenommenes
    Foto einem anderen Event zu, steht es dort — nicht dort, wo seine Zeit hinzeigte.
15. **`DELETE /photos/{id}/rating` nimmt nur `status` zurück.** Eine Zeile mit `favorite=true`
    bleibt bestehen und trägt danach `status=NULL`; die naive Zeilenlöschung verliert den Favoriten
    ohne jede Meldung.
16. **Die Invariante „keine leere Bewertungszeile" gilt als Nachsatz jedes Falls.** Ein Helfer
    `assert_no_empty_rating_rows(session)` läuft am Ende **jedes** Falls in `test_api_ratings.py`,
    nicht nur dort, wo jemand daran gedacht hat.
17. **Zeilenvorhandensein ist keine Aussage mehr.** Drei Lesestellen kodieren heute „bewertet" als
    „Zeile existiert" und liefern nach der Trennung stumm falsche Werte, sobald eine Zeile nur den
    Favoriten trägt: `_to_photo_out::has_own_rating` (der Ausschuss-Vorschlag verschwindet),
    `RatingFilter.UNRATED` (das Foto fällt aus dem Filter), `api/stats.py` (`unrated` ist zu klein).
    Je ein Fall mit einer reinen Favoritenzeile.
18. **`group_by(Rating.status)` hat jetzt eine `NULL`-Gruppe.** `sum(counts.values())` zählt sie
    mit; `favorite` kommt aus der Spalte, nie aus dem Status.
19. **`limit`/`offset` bleiben im Entwurfszweig wirkungslos — nie halb.**
20. **Der abgeschaffte Parameter scheitert laut, in beiden Belegungen.** `selection=true` **und**
    `selection=false` ergeben `422`; der zweite ist der gefährlichere, weil er heute ein gültiger
    Aufruf ist und sonst still in den Listing-Zweig fiele.
21. **Die Projektbindung steht in jeder Abfrage des neuen Endpunkts, die Zählabfrage
    eingeschlossen.** Eine `event_id` aus einem fremden Projekt und eine aus einem älteren Lauf
    desselben Projekts liefern `200` mit leerer Liste **und** `total: 0`. Ein Fall, der `total`
    nicht mitprüft, lässt eine Zählabfrage ohne Lauf-Prädikat durch: plausible Zahl zu leerer
    Liste, nichts wird rot.
22. **Eine Entscheidung löst kein Neuladen der Entwurfsliste aus.** Zähler auf der gemockten
    `listPhotos`: nach dem Klick genau ein Aufruf, und die Id-Folge der Kacheln ist vor und nach
    dem Klick identisch.
23. **Zwei Datenformen, ein Anzeigezustand.** „Vom Nutzer aufgenommen, vom Lauf nicht mehr
    vorgeschlagen" kommt als `ranking: null` (aus dem Kandidatenbestand aussortiert) **und** als
    `ranking.proposed: false` (noch Kandidat, nicht gewählt). Ein Fall mit beiden Formen und einer
    Assertion darauf, dass die Kennzeichnung dieselbe ist.
24. **`tuple(RatingStatus)` schrumpft still.** `demo_state.py::_RATED_STATUS_ORDER` legt danach
    zwei statt drei Bewertungen an, und die Demo-Instanz verliert den Favoriten. Der bestehende
    Kardinalitätsfall wird auf die neue Zerlegung umgeschrieben, nicht gelöscht.
25. **Die alte Route entfällt ohne Weiterleitung.** Ein Fall auf `/projects/:id/curate`; ohne ihn
    ist sowohl ein vergessener Wegfall als auch ein eingeschlichener Redirect unsichtbar.

### Unit (pytest, rein, ohne Session)

- `order_alternatives`: Punkte 5–9, dazu leere Kandidatenliste, Bezugsbild ohne getragenes Motiv
  (reine Qualitätsordnung), und das Bezugsbild selbst nie unter den Kandidaten.
- `event_for_time`: Punkte 10–12, dazu genau ein Event, Zeit vor dem ersten und nach dem letzten
  Event, leere Spannenliste (`None`), Permutation der Spannenliste.
- Der strukturelle Wächter `TestTheStructuralGuardAgainstReadingTheDisplayBands` bekommt
  `api/photos.py` in `_SELECTING_MODULES` — mit dem Alternativen-Endpunkt ordnet erstmals eine
  API-Datei nach Motiv.

### Integration (pytest, In-Memory-SQLite, `httpx.ASGITransport`)

**PR1 — Bewertung heißt Albumentscheidung.** Punkte 15–18, 24, dazu: `PUT .../rating` lässt
`favorite` unberührt und umgekehrt; `status: "favorite"` ergibt `422`; `PUT .../favorite` bekommt
den vollständigen Sicherheitssatz des Bestands — `401` ohne Token, `404` für ein unbekanntes Foto,
und der BOLA-Fall „überschreibt nie die Zeile eines anderen Nutzers"; `PhotoOut.ratings[]` trägt
`favorite` je Nutzer.

**PR1 — Migration** (`test_migration_albumentscheidung.py`, Muster `test_migration_selection.py`):
`status='favorite'` → `favorite=true, status=NULL`, `album_worthy`/`rejected` → `favorite=false` mit
unverändertem Status, alle drei Bestandswerte in **einem** Fall nebeneinander; nach dem Upgrade
enthält `status` ausschließlich `NULL|album_worthy|rejected`; `favorite` ist `NOT NULL`, geprüft an
beiden Artefakten (gerenderte Postgres-DDL in `test_postgres_ddl_compatibility.py` und ein `INSERT`
gegen das Modellschema); `status` ist danach nullable; der `downgrade()` löscht die Zeilen ohne
Albumentscheidung und stellt `NOT NULL` wieder her — der Fall heißt nach dem Verlust, nicht nach der
Struktur; die Revision hängt am aktuellen Head. Zusätzlich: `photo_scores.suggested_status` trägt
nach dem Upgrade keinen Wert außerhalb des neuen Vorrats (Auflage S11).

**PR2 — Der Entwurf.** Punkte 1, 3, 4, 13, 14, 19, 20, dazu: die Antwort ist **nutzerabhängig** —
zwei Tokens über demselben Bestand liefern verschiedene Mengen (der bestehende
`test_response_is_independent_of_the_asking_user` kehrt seine Zusage um und wird umgeschrieben,
nicht gelöscht); `proposed` ist lauf-global (beide Nutzer sehen denselben Wert) und steht auf
**allen** Lesepfaden (Feldgleichheit zwischen Listing-, Entwurfszweig und dem neuen Endpunkt); kein
erfolgreicher Lauf → leere Antwort ohne Fehler, auch wenn der Nutzer bereits Fotos aufgenommen hat;
ein aufgenommenes Foto aus dem Ausschussbestand (nie eine Rangzeile gehabt) wird über
`event_for_time` eingeordnet; ein gestrichenes Foto, das weder vorgeschlagen noch je aufgenommen
war, gerät dadurch nicht in den Entwurf.

**PR3 — Austauschen.** Punkte 2, 21, dazu: ein aufgenommenes Foto ist keine Alternative, ein vom
**anderen** Nutzer aufgenommenes schon; ein Ausschuss-Foto ist keine Alternative (es hat keine
Rangzeile); die Sortierung des Endpunkts ist die von `order_alternatives`, geprüft über einen
Aufbau, dessen Sollreihenfolge sich sowohl von der `photo_id`- als auch von der
`rank_position`-Folge unterscheidet — sonst besteht der Fall auch ohne jede Sortierung;
`limit`/`offset` wirken hier sehr wohl und `total` ist die Restmenge, unabhängig von beiden;
unauflösbare `photo_id` → `200` mit leerer Liste, ohne Rückspiegelung des Werts; Parameter außerhalb
ihrer Grenzen und fehlende Pflichtparameter → `422`; `401` ohne Token;
`GET /projects/{id}/curation-candidates` antwortet `404`. Der Block `TestCurationCandidates` wird
auf den neuen Endpunkt umgeschrieben und behält dabei jede seiner Sicherheitszusagen.

### Frontend-Komponente (vitest + Testing Library)

- **Reine Ableitungen zuerst und getrennt von der Komponente:** Tages-/Eventgruppierung,
  Motivmischungstext, Kopfzeilentext, die Kennzeichnung „zuvor im Album" und die aus Punkt 23 —
  tabellengetrieben, ohne Router und ohne QueryClient.
- Die Motivmischung enthält **keine Zahl** — der Fall, der die Rangfolge-Eindämmung im Frontend
  hält.
- Kopfbereich: Richtwert und Ist-Anzahl in **beiden** Abweichungsrichtungen ohne Fehleroptik (kein
  `role="alert"`, kein angleichender Schalter, keine ausgehende Anfrage).
- Zweizustand „Im Album ⇄ Gestrichen" über `aria-pressed`; Punkte 22 und 23; die Mutation schreibt
  den betroffenen Eintrag im Cache fort und invalidiert die übrigen Fotoabfragen — zwei Query-Keys,
  einer unangetastet, einer invalidiert.
- Zustände: ladend (Skeleton), Fehler (Alert samt Retry, der genau eine neue Anfrage auslöst), kein
  Entwurf (benennt den fehlenden Schritt und verlinkt ihn), Event ohne Bilder (Gruppe bleibt mit
  ihrer Bezeichnung stehen).
- Die Begründung: vollständig im DOM trotz `line-clamp-2`, kein Träger ohne Begründung, nie als
  Markup, nie als Link — die vier Fälle aus `CurationPhotoTile.test.tsx` ziehen unverändert mit um.
- Die Kachel liest die eigene Bewertung ausschließlich über `ownRatingStatus`, nie über eine zweite
  Ableitung aus `ratings[]`.
- Alternativen-Dialog: die Abfrage läuft **erst beim Öffnen** (der Mock wird vor dem Klick nicht
  aufgerufen); nach dem Austausch trägt das ersetzte Bild dort „zuvor im Album" und ein Druck darauf
  stellt beide Bewertungszeilen zurück. Fokusfang, Escape und Fokusrückgabe werden **nicht** erneut
  geprüft — sie sind Zusage von `ui/dialog`.
- `RatingButtons`/`PhotoDetailPage`: drei Einträge und die Belegung 1/2/3 bleiben; Favorit ist
  unabhängig toggelbar, Favorit und Albumentscheidung können gleichzeitig gedrückt sein. Der
  tabellengetriebene Abgleich Ziffer ↔ Eintrag bleibt und bekommt beide Richtungen dazu: Taste 1
  ändert die Albumentscheidung nicht, Taste 2/3 den Favoriten nicht.
- `ProjectStatsPage`: die vier Zahlen zerlegen den Bestand nicht mehr, und die Anzeige behauptet es
  auch nicht.

### E2E (`e2e/`, Playwright/Chromium)

Kein neuer Spec. Drei bestehende ziehen nach:

- `no-horizontal-scroll` und `popover-position`: Route `/projects/:id/album`.
- `no-horizontal-scroll`: der Eintrag der Albumseite bekommt **mindestens eine Kachel als
  Vorbedingung**.
- `tap-targets`: die beiden neuen Kachelflächen gehören zum heißen Pfad; `EXPECTED_CONTROL_COUNT`
  wird bewusst angehoben. Dazu der geöffnete Alternativen-Dialog bei 360px als weiterer Fall in
  `no-horizontal-scroll`.

### Edge Cases, die die Story nicht nennt

- Ein Foto ist zugleich vorgeschlagen und aufgenommen (Punkt 1).
- Ein Foto ist gestrichen, war aber nie im Vorschlag und nie aufgenommen — es gerät dadurch nicht in
  den Entwurf.
- Zwei Events berühren sich zeitlich an genau einem Zeitpunkt (Punkt 11).
- Ein Lauf ohne Events: der Entwurf ist leer, ein aufgenommenes Foto erscheint nicht.
- Alle Fotos eines Events gestrichen: die Gruppe bleibt stehen und zeigt sie — das ist **nicht** der
  Zustand „Event ohne Bilder".
- Ein Ausschuss-Foto, das der Nutzer im Raster aufgenommen hat: im Entwurf über `event_for_time`,
  aber nie unter den Alternativen.
- Alternativen zu einer Alternative (das Bezugsbild ist selbst nicht im Entwurf).
- Ein Kandidat ohne Qualitätswert im Alternativenraster: „Noch nicht bewertet" und trotzdem wählbar.
- Zweiter Druck, während die erste Mutation läuft: eine **Menge** laufender Mutationen, nicht eine
  einzelne Id (Muster `rejectingPhotoIds`).
- Der Richtwert ist nicht eingestellt: der Kopfbereich nennt den wirksamen Wert, nie eine leere
  Stelle.

### Coverage

Das Gate ist nicht gefährdet: der Bestand liegt bei 97 % gegen ein Gate von 80 %, die berührten
Module bei 98–100 %. Die Migration zählt nicht mit (`--cov=photosort` erfasst `alembic/` nicht), und
die größte Codemenge dieser Story liegt im Frontend, für das es kein Gate gibt. Die Zahl sagt hier
nichts: jede der 25 oben genannten Zusicherungen bricht bei voll ausgeführten Zeilen.

**`specs/architecture/0002-testkonzept.md`** bekommt eine neue Backend-Sektion (nach der
ADR-0097-Sektion) für den ersten Testgegenstand des Projekts, dessen Ergebnis **keine Tabelle hat**,
mit sechs projektweit gültigen Mustern: (1) eine zur Lesezeit gebildete Menge braucht einen Fall auf
die Überschneidung ihrer Operanden und einen über zwei Zustände der Quelle; (2) sprechen zwei
Endpunkte von derselben Menge und meint der eine sie mit, der andere ohne einen Bestandteil, gehört
das Paar in **einen** Fall; (3) eine Reihenfolgezusage über eine aus zwei Quellen zusammengesetzte
Zeilenmenge braucht einen totalen Sortierschlüssel, und der Nachweis darf die Zufallsordnung von
SQLite nicht erben; (4) hört ein Zeilenvorhandensein auf, eine Aussage zu sein, werden seine
Lesestellen aufgezählt, und über allen Fällen der Datei läuft ein Invariantenhelfer; (5) verliert
ein Enum ein Element, bekommt jede Stelle, die es aufzählt, einen Fall auf ihre Kardinalität; (6)
eine Zuordnungsfunktion über Intervalle hat sechs Grenzfälle, und „Enthaltensein schlägt Nähe"
trennt allein. Dazu: zwei Datenformen mit einem Anzeigezustand; ein Endpunkt, dessen Projektbindung
an einer Lauf-Id hängt, prüft `total` mit; ein Dialog auf dem geprüften Grundelement beweist dessen
Zusagen nicht erneut; eine ersatzlos entfallende Route braucht einen Fall.

## Security

Das Feature ist **sicherheitsrelevant**: eine Datenmodell-Änderung mit Migration in beide
Richtungen, drei Schreibendpunkte auf derselben Zeile, ein neuer Lese-Endpunkt mit zwei
fremdgesteuerten Id-Parametern, und erstmals eine Listen-Antwort, deren **Menge** vom anfragenden
Nutzer abhängt. Keine neuen Secrets, kein neuer externer Dienst, kein Cloud-Aufruf, kein
zusätzlicher Bilddatenfluss. Die Auflagen S1–S8 aus Spec 0429 gelten unverändert weiter; S5 und S7
dort werden hier verschärft (S5/S14 unten), nicht ersetzt.

**S1 — Jeder der drei neuen bzw. geänderten Endpunkte trägt die Auth-Dependency ausgeschrieben, und
jeder bekommt seinen eigenen 401-Nachweis.** Gilt für `GET /projects/{id}/draft-alternatives`,
`PUT /photos/{id}/favorite` und jeden geänderten Endpunkt in `api/photos.py`/`api/ratings.py`.
Angriffsmodell: Beide Router tragen bewusst keine router-weite `dependencies`-Liste, und
`_protected_router_operations()` in `test_auth_guard.py` führt ausschließlich `projects`,
`opencloud`, `stats`, `cameras`, `motifs` — für diese beiden Router gibt es **kein**
Vollständigkeitsnetz. Ein vergessener `current_user`-Parameter ist still öffentlich: kein Fehler,
keine 401, nur Daten bzw. ein unauthentifizierter Schreibzugriff auf eine fremde Bewertungszeile.
`current_user.id` geht unverändert an `_to_photo_out`, nie ein Platzhalter wie `0` (der ließe
`PhotoOut.suggestion` auch für längst bewertete Fotos wieder aufblitzen).

**S2 — Die Projektbindung des Alternativen-Endpunkts steht ausgeschrieben in jeder Abfrage und
stammt ausschließlich aus dem Pfadparameter.** `criterion_scoring_run_id` aus
`_latest_successful_criterion_scoring_run_id(session, project_id)` steht in der Kandidatenabfrage,
in der Auflösung des Bezugsfotos (S3), in der Motivabfrage und in der Zählabfrage hinter `total`.
Angriffsmodell: `PhotoRanking` trägt keine `project_id`, und `event_id` ist ein globaler
Surrogatschlüssel — eine Id aus Projekt B identifiziert unter `/projects/A/…` eindeutig **fremde**
Rangzeilen. Ohne das Prädikat liefert der Endpunkt kohärente Fotos eines fremden Projekts statt
einer erkennbar falschen Menge; die Ausfallrichtung wird unauffälliger, nicht harmloser.
`_photos_by_id` filtert nur nach Id und ist ausdrücklich **keine** zweite Verteidigungslinie.

**S3 — `photo_id` wird ausschließlich über eine Rangzeile desselben Laufs und desselben `event_id`
aufgelöst; scheitert das, endet die Anfrage vor jeder weiteren Abfrage.** Nie über
`session.get(Photo, photo_id)`. Antwort dann `200` mit `items: []` **und** `total: 0`, ohne
Rückspiegelung der übergebenen Werte, ohne Fehlertext und auf demselben Antwortpfad wie eine leere
Trefferliste. Angriffsmodell: `photo_id` steuert allein die Sortierung — die Motive des
Bezugsbildes bestimmen, welche Fotos vorn stehen. Wird das Bezugsbild ohne Lauf-/Event-Prädikat
aufgelöst, ordnet ein fremdes Foto die eigene Antwort, und aus der beobachteten Reihenfolge lässt
sich das Motivprofil eines Bildes ablesen, das der Anfragende nie sehen darf — ein Leck über die
Sortierung, das keine Antwortzeile benennt. Ein abweichender Statuscode (`404`) oder ein Fehlertext
wäre daneben ein Existenz-Orakel über fremde Ids.

**S4 — Grenzen an allen vier Query-Parametern, deklarativ, vor jeder Verwendung.**
`event_id: Query(..., ge=1, le=_MAX_QUERY_POSITION)`, `photo_id` ebenso,
`limit: Query(60, ge=1, le=200)`, `offset: Query(0, ge=0, le=_MAX_QUERY_POSITION)` — dasselbe
Profil wie am bisherigen Kandidaten-Endpunkt. Angriffsmodell: Ein Pydantic-`int` ist unbeschränkt
und landet direkt im SQL-Vergleich; jenseits von 2^63 erzeugt SQLite einen `OverflowError` und
damit eine `500` statt einer leeren Liste. `limit <= 200` deckelt zugleich die schwere Hydratation
über `_photos_by_id` mit ihren `selectinload`s. Der bei `422` von FastAPI zurückgespiegelte Rohwert
wird ausschließlich als React-Textknoten gerendert, nie geloggt.

**S5 — Die Auflage „Nutzer im Schlüssel" bekommt eine zweite, unabhängige Ursache und wird dadurch
strenger.** Bekommt `GET /projects/{id}/photos` (in **beiden** Modi) oder
`GET /projects/{id}/draft-alternatives` eine Antwort-Zwischenspeicherung, ein `ETag` oder ein
`Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten. Bisher trug das
allein `PhotoOut.suggestion` — ab hier zusätzlich die **Menge**: Der Entwurfszweig liefert
Vorschlag ∪ eigene `album_worthy`, und `total` des Alternativen-Endpunkts ist die Restmenge nach
Abzug des eigenen Entwurfs. Beide Ursachen gelten unabhängig; der Wegfall einer hebt die Auflage
nicht auf. Angriffsmodell: Das Frontend ist eine PWA mit Workbox (`registerType: 'autoUpdate'`),
ein `runtimeCaching` für API-Antworten ist der naheliegende nächste Schritt, der
Service-Worker-Cache ist je Browserprofil geteilt, und das JWT liegt in `localStorage` — zwei
Personen an einem Gerät ist der realistische Familienfall. Bei Verletzung sieht der eine den
Entwurf des anderen als seinen eigenen, ohne dass irgendeine Anzeige das als falsch ausweist. Die
SICHERHEIT-Passage am Docstring von `_to_photo_out` wird **umgeschrieben, nicht gelöscht**: Der
entfallende Endpunktname wird durch den neuen ersetzt, und die zweite Ursache kommt hinzu.

**S6 — Die eigene Entscheidung wird an genau einer Stelle abgeleitet, und `favorite` fällt unter
dieselbe Regel wie `status`.** `PhotoOut.ratings[]` trägt die Bewertungen beider Nutzer und künftig
je Eintrag zusätzlich `favorite`; sichtbare Fremdbewertung ist gewollt und bleibt es. Die
Oberfläche liest den eigenen Zustand — Albumentscheidung **und** Favoritenkennzeichen —
ausschließlich über `findOwnRating`/`ownRatingStatus` (`utils/ownRating.ts`, Abgleich über den
`username`-Claim). Angriffsmodell: Das neue Feld lädt zur Zweitableitung ein, weil es allein
aussagekräftig aussieht — `ratings.some(r => r.favorite)` oder „erster Eintrag in `ratings[]`"
stellt die Auszeichnung des anderen als eigene dar. Ebenso wird die Entwurfszugehörigkeit eines
Fotos nie aus `ratings[]` irgendeines Nutzers nachgebaut; sie steht in der Antwortmenge und in
`RankingOut.proposed`. Prüfbar: ein nur vom anderen Nutzer als Favorit markiertes oder
aufgenommenes Foto erscheint in der eigenen Ansicht weder als Favorit noch als aufgenommen.

**S7 — Jeder Schreibendpunkt schreibt genau sein Feld, und `user_id` stammt ausschließlich aus
`current_user`.** `PUT /photos/{id}/rating` setzt nur `status`, `DELETE /photos/{id}/rating` nimmt
nur `status` zurück, `PUT /photos/{id}/favorite` setzt nur `favorite`; die Aufsuchbedingung ist
überall `(photo_id, current_user.id)`, nie eine Id aus Body oder Query. Angriffsmodell zweifach:
Erstens Broken Object-Level Authorization — eine `user_id` aus dem Body ließe Nutzer A die Zeile
von Nutzer B überschreiben. Zweitens der stille Verlust, dessentwegen die Trennung überhaupt
entsteht: Ein gemeinsamer Schreibpfad, der beide Felder aus einem teilbefüllten Modell schreibt,
setzt beim Markieren als Favorit die Albumentscheidung zurück — kein Fehler, keine Meldung, die
Entscheidung ist fort. Dasselbe gilt umgekehrt: `DELETE …/rating` darf die Zeile **nicht** pauschal
löschen, solange `favorite` gesetzt ist, sonst verschwindet die Auszeichnung mit der Rücknahme der
Albumentscheidung.

**S8 — Die verbotene Zeile kann über die API nicht entstehen.** `status` im Body von
`PUT …/rating` ist nicht nullable und trägt ausschließlich `album_worthy`/`rejected`; `null` ist
kein zulässiger Body-Wert, sondern ausschließlich das Ergebnis von `DELETE`. Die Löschung der
leergewordenen Zeile (`status IS NULL AND favorite IS FALSE`) steht an genau einer Stelle und wird
von jedem der drei Endpunkte durchlaufen. Angriffsmodell: Eine Zeile, die weder Albumentscheidung
noch Kennzeichen trägt, ist auf keinem Lesepfad als Fehler erkennbar — sie liest sich in
`ratings[]` wie eine Bewertung ohne Inhalt, unterdrückt zugleich `PhotoOut.suggestion`
(`has_own_rating` prüft die Existenz der Zeile, nicht ihren Inhalt) und macht das Foto dauerhaft
„bewertet", ohne dass ein Handgriff der Oberfläche sie wieder entfernen kann.

**S9 — Der Unique-Constraint entscheidet das gleichzeitige Schreiben, und zwar innerhalb der
Transaktion.** `session.flush()` **vor** `commit`, damit `uq_rating_photo_user` hier greift (Muster
`photos.py::set_motif_correction`); bei `IntegrityError` wird die eigene Zeile erneut gelesen und
die Änderung darauf angewandt. Angriffsmodell: Ab dieser Story schreiben drei Endpunkte auf
dieselbe Zeile, und die Oberfläche löst zwei davon aus derselben Tastenbelegung aus. Zwei
gleichzeitige Anfragen sehen beide „keine Zeile" und fügen beide ein; ohne diese Behandlung ist das
Ergebnis eine `500` auf einen alltäglichen Doppelklick, und der Aufrufer weiß nicht, welche der
beiden Entscheidungen gilt. Wiederholte identische Aufrufe bleiben folgenlos (außer `updated_at`);
`DELETE` antwortet `204`, ob eine Zeile bestand oder nicht.

**S10 — Die Migration vorwärts erzeugt keine Zeile außerhalb des neuen Vorrats und keine, die die
Invariante verletzt.** Reihenfolge: `favorite` anlegen **und** `status` nullable stellen in
**einem** `batch_alter_table` (SQLite kennt kein `ALTER COLUMN`), **danach**
`UPDATE ratings SET favorite = 1, status = NULL WHERE status = 'favorite'`. Die Konvertierung muss
nach dem Nullable-Stellen laufen — davor bricht sie an der noch bestehenden `NOT NULL`-Bedingung
ab. Angriffsmodell: Ohne
`server_default` bzw. Backfill tragen die Bestandszeilen `NULL` in einer nicht-nullable
Bool-Spalte; der erste Lesepfad, der sie anfasst, scheitert bei der Modellvalidierung mit einer
`500` auf **jeder** Fotoliste, die eine solche Zeile enthält — behebbar dann nur noch an der
Datenbank. Die Konvertierung erzeugt ausschließlich Zeilen mit `favorite = true`, verletzt die
Invariante also nicht.

**S11 — Jeder Lesepfad, der `favorite` heute aus `status` liest, wird mitgeführt — sonst bricht er
laut oder zählt still falsch.** Drei Stellen, abschließend: `PhotoScore.suggested_status` teilt
sich die Enum-Klasse `RatingStatus` mit `Rating.status` (`models.py`),
`api/photos.py::_filtered_photo_ids` bildet `RatingFilter` über `RatingStatus(rating_status.value)`
auf den Status ab, und `api/stats.py::_ratings_out` zählt über `counts.get(RatingStatus.FAVORITE,
0)`. Angriffsmodell und Ausfallverhalten: Verliert der Enum den Wert `favorite`, wirft eine
Bestandszeile `photo_scores.suggested_status = 'favorite'` beim Lesen einen `LookupError` — eine
`500` auf jeder Fotoliste, die dieses Foto enthält; `suggested_status` bekommt deshalb entweder
einen eigenen Wertevorrat oder wird in derselben Migration auf `NULL` konvertiert. Der Filterzweig
wirft für `rating_status=favorite` einen `ValueError` (`500` auf einem nutzererreichbaren
Query-Parameter) und muss auf die neue Spalte prüfen. Die Statistikzahl bricht dagegen **nicht** —
sie liest still `0` und behauptet damit, es gebe keine Favoriten; sie zählt künftig über
`favorite IS TRUE`, und `unrated` zählt — wie an allen drei Lesestellen — die Abwesenheit einer
**Albumentscheidung**, nicht die Abwesenheit der Zeile. Folge, bewusst getragen: Die vier Zahlen
zerlegen den Bestand nicht mehr überschneidungsfrei, und die Statistikseite darf das nicht
behaupten.

**S12 — Die Migration rückwärts stellt die Struktur wieder her, nie die Daten — und benennt, was
sie verwirft.** `UPDATE ratings SET status = 'favorite' WHERE favorite = 1 AND status IS NULL`,
danach `DELETE FROM ratings WHERE status IS NULL` (Zeilen, die das alte Schema nicht darstellen
kann), erst dann `status` wieder `NOT NULL` und `favorite` fallen lassen. Eine Zeile, die
Albumentscheidung **und** Favorit trägt, behält die Albumentscheidung; die Auszeichnung geht
verloren, weil das alte Schema beide nicht zugleich abbilden kann. Das steht im Docstring der
Migration. Angriffsmodell: Ohne die Löschung scheitert der `NOT NULL`-Aufbau mitten im
Rückwärtsweg und lässt die Tabelle in einem halb umgebauten Zustand zurück; ein ersatzweise
geschriebener Vorgabewert wäre schlimmer — er erfände eine Entscheidung, die niemand getroffen hat.

**S13 — `album_suitability.reason` erreicht die neue Seite ausschließlich als Textknoten.** Auf
`AlbumDraftPage.tsx` und jedem von ihr genutzten Baustein: nie über `dangerouslySetInnerHTML`, nie
in `href`, `src` oder `style`, nie in einen per `innerHTML` gebauten Tooltip, nie in eine URL.
Keine zweite Sanitierung — der Text ist am Parser saniert und gekappt (`album_suitability.py`) und
wird unverändert durchgereicht. Angriffsmodell: Der Text ist die Antwort eines Cloud-Modells auf
ein Bild, dessen Inhalt der Verfasser des Bildes bestimmt; ein Foto eines Textes, eines Schildes
oder eines Bildschirms kann die Ausgabe steuern. Ein als HTML gerenderter Treffer liegt persistiert
in der Datenbank und läuft im Browser **beider** Nutzer, während das JWT in `localStorage` liegt —
gespeichertes XSS mit Sitzungsübernahme als Ausgang.

**S14 — Die Menge des Entwurfszweigs wächst mit den eigenen Entscheidungen, und die
Event-Zuordnung darf dabei keine Abfrage je Foto auslösen.** S4 der Spec 0429 gilt unverändert
(`limit`/`offset` wirken in diesem Zweig ganz oder gar nicht), die Obergrenze ist aber nicht mehr
der auswahlfähige Bestand des Laufs: Aufgenommene Fotos ohne Rangzeile kommen hinzu, bis hin zu
jedem Foto des Projekts. Das wird getragen — die Menge wächst nur durch Handlungen des
Anfragenden selbst, und zwischen den beiden Nutzern gilt kein Innentäter-Modell. Verbindlich ist
die Komplexitätsklasse, nicht die Eingabegrenze: `events.py::event_for_time` ist eine reine
Funktion über die **einmal** geladene Eventliste des Laufs; die Zuordnung der rangzeilenlosen Fotos
läuft in einem Durchgang, nie als Abfrage je Foto. Angriffsmodell: Ein N+1-Muster an dieser Stelle
erzeugt eine Abfrage je aufgenommenem Foto in einem synchronen Request bei offener Transaktion —
der Unterschied zwischen einer Handvoll Abfragen und mehreren tausend, ausgelöst durch normale
Benutzung, ohne dass ein Parameter das begrenzte.

**Ausdrücklich geprüft und ohne Befund:** keine neue Datenklasse zwischen den beiden Nutzern —
`ratings[]` zeigt die Auszeichnung des anderen schon heute als `status='favorite'`; neu ist allein,
dass sie neben einer Albumentscheidung stehen kann. Keine Berührung von Secrets, `.env`,
Consent-Schalter, Kostenschätzung oder Bilddatenfluss; kein neuer Fremdtext in Antwort, Persistenz
oder Log. Kein Rate-Limiting nötig, konsistent mit der übrigen API. Die Bindung der
Schreibendpunkte allein an die globale `photo_id` bleibt unverändert — es gibt keine
Projekt-Mitgliedschaft, beide Nutzer sehen alle Projekte. Ein Laufzeit-Orakel am
Alternativen-Endpunkt wird nicht gesondert abgewehrt: Die Auflösung des Bezugsfotos ist eine
indexgestützte Einzelabfrage, und gegen die Antwort selbst gibt es nach S3 nichts zu messen.

**`specs/architecture/0003-securitykonzept.md`** bekommt einen neuen Abschnitt unter
`## Angriffsflächen`, hinter „Der Auswahlvorschlag mit Richtwert", mit den vier projektweiten
Aussagen: die Cache-Schlüssel-Auflage mit ihren nun zwei unabhängigen Ursachen; die beiden Router
ohne Vollständigkeitsnetz; **ein geteilter Wertevorrat als Kopplung ohne Fremdschlüsselbeziehung**
(projektweite Folgeregel: Verliert ein Enum einen Wert, wird vor der Migration erhoben, welche
Spalten ihn verwenden; jede davon wird in derselben Migration konvertiert oder bekommt einen
eigenen Vorrat); und: eine Spalte, deren Abwesenheit ein gültiger Zustand ist, braucht eine
Invariante mit genau einem durchsetzenden Ort.

## Entscheidungen

- **Der Entwurf wird abgeleitet, nicht gespeichert** (ADR 0098 Punkt 1). „Nie angefasst" ist die
  Abwesenheit einer eigenen Albumentscheidung; es entsteht keine Entwurfstabelle.
- **Favorit wird eine eigene, unabhängige Angabe** (`ratings.favorite`), `status` wird nullable und
  trägt nur noch die Albumentscheidung. Die beiden Alternativen sind verworfen: Beim dreiwertigen
  Feld zu bleiben hieße, dass jedes Markieren als Favorit eine bestehende Aufnahme- oder
  Streich-Entscheidung **still** zurücksetzt; „Favorit gilt als aufgenommen" hebt das
  Akzeptanzkriterium auf, dass die Auszeichnung auf den Entwurf nicht wirkt. Beide Alternativen
  verletzen ein ausdrückliches Akzeptanzkriterium der Story; die Wahl ist damit von der Story
  vorgegeben und keine offene Produktfrage.
- **Alternativen im Dialog, nicht im Popover** — ein Bildraster mit eigenem Blätterweg braucht auf
  360px Breite die volle Fläche, und der Austausch verlangt Fokusfang und Fokusrückgabe.
- **Die Story zerfällt in drei Pull Requests** (Bewertungsmodell → Entwurfsansicht → Austauschen).
  Jeder Schnitt ist für sich grün und hinterlässt keinen Zustand mit zwei Auswahlwegen.
- **„Unbewertet" heißt ab jetzt „keine Albumentscheidung"** (`status IS NULL`), an allen drei
  Stellen gleich: Rasterfilter, `unrated` auf der Statistikseite, und die Bedingung, unter der der
  Ausschuss-Vorschlag am Foto erscheint. Ein nur als Favorit markiertes Bild bleibt damit im Filter
  „Unbewertet" und behält seinen Vorschlag. Folge: Die vier Statistikzahlen zerlegen den Bestand
  nicht mehr überschneidungsfrei, und die Seite darf das nicht behaupten.
- **Innerhalb eines Events wird chronologisch sortiert** (korrigierte Aufnahmezeit, dann Foto-Id),
  nicht nach dem Platz im Vorschlag. Nach `selection_position NULLS LAST` zu sortieren stellte jedes
  aufgenommene Bild ans Gruppenende — ein Austausch verschöbe das Bild dann dorthin, statt es an
  seiner Stelle zu ersetzen.
- **Der Rückwärtsweg der Migration verliert Daten, und das steht dort.** `status NOT NULL` lässt
  sich nicht wiederherstellen, solange Zeilen mit `status IS NULL` existieren; der `downgrade()`
  löscht deshalb die reinen Favoritenzeilen, und eine Zeile mit Albumentscheidung **und** Favorit
  behält die Albumentscheidung. Der Docstring der Migration benennt beides.
- **`PhotoScore.suggested_status` teilt sich die Enum-Klasse mit `Rating.status`** und wird in
  derselben Migration mitgeführt. Ohne das wirft eine Bestandszeile `suggested_status='favorite'`
  beim Lesen einen `LookupError` — eine 500 auf jeder Fotoliste, die das Foto enthält.
- `architect` konsultiert (Schritt 1) — Ergebnis ist ADR 0098.
- `ux-ui-designer` konsultiert (Schritt 2); der Abschnitt „UI/UX" wurde anschließend gegen den
  Bestand nachgeschärft, weil die Rückmeldung der Architektur an vier Stellen widersprach
  (Wegfall von „Verwerfen" aus der Bewertungsleiste, Rasterfilter ohne Album-Status,
  widersprüchliche Tastenbelegung, `aria-modal` auf einem Popover).
- `test-engineer` konsultiert (Schritt 3) — Ergebnis sind die 25 benannten Zusicherungen und die
  Schärfung von acht Akzeptanzkriterien.
- `security-engineer` konsultiert (Schritt 3) — Ergebnis sind die Auflagen S1–S14.

## Offene Fragen

Keine. Die einzige Stelle, an der die Umsetzung eine Produktentscheidung berührt hätte — die
Auflösung des dreiwertigen Bewertungsfelds —, ist durch das Akzeptanzkriterium „Die Auszeichnung als
Favorit bleibt davon unberührt und wirkt nicht auf den Entwurf" bereits entschieden.

## Out of Scope

- Das Bilden des Vorschlags selbst (Richtwert, Verteilung über Events, Mischung je Motiv) — Spec
  [`0429`](./0429-auswahl-richtwert-und-mischung.md).
- Der Vergleich der beiden Nutzer-Entwürfe und die gemeinsame Endauswahl — Story 7.
- Das Auswerten der Korrekturen als Feedback und die Modelldiagnose — Story 8.
