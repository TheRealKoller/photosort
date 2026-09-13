# 0431 - Zwei Album-Entwürfe vergleichen und gemeinsam die Endauswahl treffen

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [Issue #431](https://github.com/TheRealKoller/photosort/issues/431) (Story unter dem Zielbild [#424](https://github.com/TheRealKoller/photosort/issues/424))

**Umfang:** ein Mehrfaches des Richtwerts von rund 200 Zeilen. Vier Abschnitte tragen ihn, jeder aus
einem eigenen Grund: „Architektur / Umsetzung" führt die betroffenen Dateien je Pull Request auf,
weil der `developer` sie ohne eigene Planung abarbeitet; „Security" führt die Auflagen einzeln
abhakbar samt Angriffsmodell; „Teststrategie" benennt die Zusicherungen, die ohne eigenen Testfall
still brechen — eine falsch abgeleitete Endauswahl wirft keine Ausnahme, sie liefert eine andere,
plausibel aussehende Bildmenge; „UI/UX" tritt an die Stelle eines Entwurfs, den es für diese Story
nicht gibt, und legt die Kachel mit zwei benannten Haltungen fest, für die es im Bestand kein
Vorbild gibt.

## Ziel

Nach Story 6 ([#430](https://github.com/TheRealKoller/photosort/issues/430)) hat jeder der beiden
Nutzer seinen eigenen Album-Entwurf, und der eine sieht den des anderen nicht. Damit gibt es zwei
Meinungen, aber kein Album — und keine Antwort auf die Frage, welche Fotos ein Export überhaupt
mitnehmen soll. Diese Frage ist seit der ersten Export-Spec offen und hat sie zum Stillstand
gebracht.

Diese Story führt die beiden Entwürfe zusammen. Sie zeigt je Event, worin sie sich unterscheiden,
lässt die beiden Nutzer die Unterschiede gemeinsam durchgehen, und hält das Ergebnis als
**Endauswahl des Projekts** fest — die Menge, die das Album ausmacht und die der Export später
nimmt. Sie ist der Abschluss des Umbaus: Erst mit ihr hat die Kette aus Events, Motiven,
Albumtauglichkeit, Vorschlag und Einzelentwurf ein gemeinsames Ergebnis.

**Warum der Durchgang kurz ist:** Beide Entwürfe gehen vom selben Auswahlvorschlag aus. Ein
Unterschied entsteht deshalb nur dort, wo mindestens einer aktiv eingegriffen hat — etwas
zusätzlich aufgenommen oder etwas gestrichen hat. Alles, was keiner angefasst hat, ist bei beiden
gleich und steht nicht zur Debatte.

**Reihenfolge:** Setzt Story 6 ([#430](https://github.com/TheRealKoller/photosort/issues/430))
voraus; ohne zwei Entwürfe gibt es nichts zu vergleichen. Der Export
([#263](https://github.com/TheRealKoller/photosort/issues/263)) setzt umgekehrt auf dieser Story
auf.

## User Story

Als einer von zwei Nutzern, die gemeinsam ein Album aus einer Reise machen, möchte ich sehen, worin
sich unsere beiden Entwürfe unterscheiden, und diese Stellen zusammen an einem Gerät durchgehen,
damit am Ende eine Endauswahl steht, hinter der wir beide stehen und die als Album gilt.

## Akzeptanzkriterien

**Die Vergleichsansicht**

- [ ] Die Ansicht stellt die beiden Album-Entwürfe gegenüber, gegliedert chronologisch nach Events. Ein benanntes Event zeigt seinen Namen, ein unbenanntes den bestehenden Ersatztext der Entwurfsansicht.
- [ ] Sie ist jederzeit zugänglich und zeigt den jeweils aktuellen Stand beider Entwürfe. Es gibt keinen Zustand „fertig" je Nutzer und nichts, was den Zugang sperrt: Kein Bedienelement der Seite trägt jemals `disabled`; die gedrückte Schaltfläche trägt während der laufenden Entscheidung `busy` und bleibt für Zeigerereignisse erreichbar.
- [ ] Zu jedem gezeigten Bild ist erkennbar, wie jeder der beiden Nutzer dazu steht: aufgenommen, gestrichen, oder nie angefasst. Die Zahl der Haltungszeilen ist die Zahl der Teilnehmer, auch wenn ein Teilnehmer nie etwas angefasst hat.
- [ ] Die Haltung des einen Nutzers wird nie als die des anderen dargestellt. Beide Stände stehen getrennt und benannt nebeneinander; die Zuordnung entsteht aus dem vorangestellten Namen, nie aus Reihenfolge oder Position in `ratings[]`.
- [ ] Hat nur einer der beiden bisher überhaupt etwas an seinem Entwurf getan, ist das kein Sonderfall: Seine Eingriffe sind dann die Unterschiede, der andere steht auf dem reinen Vorschlag.

**Zwei Sichten, ein Ort**

- [ ] Die Ansicht lässt sich umschalten zwischen „nur die Unterschiede" — die Arbeitssicht zum Abarbeiten — und „die ganze Endauswahl" — die Ergebnissicht, chronologisch nach Event.
- [ ] Die Arbeitssicht zeigt ausschließlich Bilder, über die die beiden uneins sind.
- [ ] Die Ergebnissicht zeigt die Endauswahl vollständig, unabhängig davon, ob ein Bild strittig war.
- [ ] Sind keine Unterschiede offen, sagt die Arbeitssicht das, statt leer zu bleiben.

**Gemeinsam entscheiden**

- [ ] Für jedes strittige Bild bietet die Arbeitssicht beide Entscheidungen an: aufnehmen oder nicht.
- [ ] Die Entscheidung gilt sofort für das Projekt. Sie wird nicht bestätigt, nicht abgestimmt, und es wird auf niemanden gewartet — die beiden sitzen beim Entscheiden zusammen vor einem Gerät.
- [ ] Wer angemeldet ist, spielt für die Wirkung der Entscheidung keine Rolle: Eine mit dem Token des einen Nutzers geschriebene Entscheidung ist beim Lesen mit dem Token des anderen identisch, und jeder kann jede Entscheidung ändern.
- [ ] Ein einmal entschiedenes Bild ist nicht mehr strittig und verschwindet aus der Arbeitssicht.

**Die Endauswahl**

- [ ] Die Endauswahl gehört dem Projekt, nicht einem Nutzer. Sie wird getrennt von den beiden Entwürfen geführt.
- [ ] Bilder, die in beiden Entwürfen stehen, sind ohne Zutun Teil der Endauswahl.
- [ ] Ein solches Bild lässt sich trotzdem noch herausnehmen. Einigkeit ist eine Vorbelegung, keine Sperre.
- [ ] Ein strittiges Bild, über das noch nicht gemeinsam entschieden wurde, gehört **nicht** zur Endauswahl. Automatische Zugehörigkeit gibt es allein bei Einigkeit.
- [ ] Die beiden Einzelentwürfe bleiben durch eine gemeinsame Entscheidung unverändert. Jeder sieht in seinem Entwurf weiter das, was er selbst gewählt hat, und es bleibt nachvollziehbar, wer was wollte.
- [ ] Ändert ein Nutzer später seinen Einzelentwurf, bleibt eine bereits getroffene gemeinsame Entscheidung für dieses Bild bestehen. Das Bild wird dadurch nicht erneut strittig; ändern lässt sich die Endauswahl nur in dieser Ansicht.
- [ ] Die Endauswahl ist jederzeit weiter änderbar. Es gibt kein Abschließen, kein Einfrieren und keine benannten Fassungen.
- [ ] Sie bleibt erhalten: Ein Abruf nach neuer Anmeldung liefert sie unverändert.
- [ ] Sie ist die Menge, die als Album gilt. Die Ergebnissicht zeigt genau diese Menge; dass der Export ([#263](https://github.com/TheRealKoller/photosort/issues/263)) sie nimmt, wird mit jener Story abgenommen, nicht hier.

**Ein neuer Vorschlagslauf**

- [ ] Getroffene gemeinsame Entscheidungen überleben einen neuen Vorschlagslauf, genauso wie die Einzelentscheidungen es in Story 6 tun.
- [ ] Ordnet der neue Lauf ein Bild der Endauswahl einem anderen Event zu, erscheint es an seiner neuen Stelle.

**Bedienung**

- [ ] Die Unterschiede lassen sich zügig durchgehen: eine Entscheidung kostet einen Handgriff, ohne Bestätigungsschritt und ohne Dialog.
- [ ] Die Ansicht ist auf dem Handy vollständig bedienbar: Bei 360 px trägt keine der beiden Sichten waagerechten Überlauf, und jedes Bedienelement der Kachel ist an den vier Ecken seiner 44-px-Fläche treffbar.
- [ ] Liegt für einen der beiden Entwürfe noch kein Auswahlvorschlag vor, benennt die Ansicht den fehlenden Schritt, statt leer zu bleiben.

**Ablösung der bisherigen Vergleichsseite**

- [ ] Die bestehende Seite „Vergleich", die pro Foto die eigene Bewertung der des anderen gegenüberstellt, wird mit dieser Story abgelöst. Danach gibt es genau einen Ort, an dem die beiden Stände gegenübergestellt werden.

**Spannung, die aufzulösen ist**

- [ ] Story 6 sagt für den Einzelentwurf zu, dass neben der Bewertung keine zweite, daneben liegende Auswahlebene entsteht. Die Endauswahl dieser Story ist eine Ebene **über** beiden Entwürfen, nicht daneben. Beim Umsetzen ist zu zeigen, dass die Zusage aus Story 6 dadurch unberührt bleibt — der Einzelentwurf bekommt keine zweite Ebene.

## Datenmodell-Bezug

Neu: `FinalSelectionDecision` (Tabelle `final_selection_decisions`) — `photo_id` als Primärschlüssel
und Fremdschlüssel auf `photos.id`, `included: bool` (NOT NULL, ohne Vorgabewert), `updated_at`.
**Ohne Nutzerbezug**: Die Entscheidung gehört dem Projekt, nicht einem Nutzer.

Unverändert: `Rating` (die Albumentscheidung je Nutzer aus Story 6), `PhotoRanking`
(`selection_position`, der Auswahlvorschlag aus Story 5). Beide bekommen **keine** neue Spalte und
**keinen** neuen Enum-Wert.

Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0099`](../decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) festgehalten
und dort begründet. Sie löst keine bestehende ADR ab — die Endauswahl ist eine Ebene **über** den
beiden Entwürfen aus ADR [`0098`](../decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md),
nicht deren Änderung. Kein Kopfzeilen-Nachtrag an einer bestehenden ADR.

### Gewählter Ansatz

**Gespeichert wird nur die ausdrückliche Entscheidung; die Endauswahl selbst ist abgeleitet.** Mit
`n` = Zahl der Nutzer und

    im Entwurf(u,p) = (Albumentscheidung(u,p) = album_worthy) ∨ (vorgeschlagen(p) ∧ keine Albumentscheidung(u,p))
    drin_zahl(p)    = #{u : im Entwurf(u,p)}
    Endauswahl(p)   = Entscheidung(p), falls vorhanden; sonst drin_zahl(p) == n
    strittig(p)     = keine Entscheidung(p) ∧ 0 < drin_zahl(p) < n

Daraus folgen die beiden Zusagen, die miteinander in Spannung stehen, **ohne durchsetzenden Code**:
Einigkeit ist eine Vorbelegung, weil sie nur im Zweig ohne Entscheidung wirkt; und eine getroffene
Entscheidung überlebt jede spätere Entwurfsänderung und jeden neuen Vorschlagslauf, weil beide
ausschließlich in denselben Zweig hineinwirken. Ein strittiges, unentschiedenes Bild gehört
**nicht** zur Endauswahl — automatische Zugehörigkeit gibt es allein bei Einigkeit.

Die Zahl **zwei** steht an keiner Stelle im Code. „Alle einig" / „nicht alle einig" ist für jede
Nutzerzahl definiert und fällt bei zwei Nutzern mit der Aussage der Story zusammen.

**Warum der Durchgang kurz ist, ist eine Folge und keine Zusicherung:** Ohne eine einzige
Bewertungszeile sind alle Nutzer per Definition einig (beide Entwürfe sind der Vorschlag). Jedes
strittige Bild trägt also mindestens eine Albumentscheidung. Dafür braucht es keinen eigenen
Mechanismus und keinen Filter.

### Datenmodell und Migration

Neue Tabelle `final_selection_decisions` (`backend/src/photosort/models.py`, Klasse
`FinalSelectionDecision`):

- `photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), primary_key=True)` — Muster
  `PhotoAlbumSuitability`/`PhotoLandmarkDetection`. „Höchstens eine Entscheidung je Foto" ist damit
  strukturell wahr, ohne eigenen Unique-Constraint.
- `included: Mapped[bool]` — **NOT NULL, kein `default`, kein `server_default`.** Jede Zeile wird
  ausdrücklich geschrieben; ein Vorgabewert erfände eine Entscheidung, die niemand getroffen hat.
- `updated_at: Mapped[datetime]` mit `server_default=func.now(), onupdate=func.now()` (Muster
  `Rating`).
- **Kein `user_id`, kein `decided_by`, keine Lauf-Bindung** (ADR 0099 Punkt 3). Die Abwesenheit der
  Zeile heißt „unentschieden"; es gibt keinen Weg zurück in diesen Zustand.

Eine Alembic-Revision unter `backend/alembic/versions/` (`down_revision` auf den zum
Umsetzungszeitpunkt tatsächlichen Head — zum Zeitpunkt dieser Spec `f6a7b8c9d0e1`), getestet im
Muster von `backend/tests/test_migration_albumentscheidung.py`, plus Durchlauf von
`test_postgres_ddl_compatibility.py`:

1. `upgrade()`: `op.create_table` mit den drei Spalten, `photo_id` als Primärschlüssel **und**
   Fremdschlüssel auf `photos.id`. Der echte Fremdschlüssel ist Pflicht, nicht Geschmack: Die
   Löschzusage prüft Erreichbarkeit über die Kanten in `Base.metadata`, eine bloß logische Spalte
   fiele still aus der Prüfung heraus (siehe Docstring von `PhotoRanking.event_id`).
2. `downgrade()`: `op.drop_table`. Der Docstring benennt, dass damit alle gemeinsamen
   Entscheidungen verloren sind — die Struktur wird wiederhergestellt, nie die Daten.
3. Geprüft an **beiden** Artefakten (gerenderte Postgres-DDL und ein `INSERT` gegen das aus
   `Base.metadata` erzeugte Schema): `included` ist `NOT NULL` und trägt **keinen** Default.

`backend/src/photosort/project_deletion.py` nimmt die Tabelle auf — vor `photos`, an der Stelle, die
`reversed(Base.metadata.sorted_tables)` vorgibt. Der bestehende Vollständigkeitswächter fängt ein
Vergessen; die Anweisung lautet
`delete(FinalSelectionDecision).where(FinalSelectionDecision.photo_id.in_(photo_ids))`.

### Reine Funktion: `backend/src/photosort/album_selection.py`

Neu, **rein und DB-frei** — dasselbe Muster wie `selection.py`/`events.py`/`quality.py`: keine
Session, kein Modell, kein SQL-Ausdruck, kein Enum-Import aus `models.py`. Die Regel aus ADR 0099
Punkte 1 und 2 lebt hier und **nur** hier:

```python
@dataclass(frozen=True)
class SelectionState:
    included: bool
    contested: bool

def selection_state(
    *, taken: int, rejected: int, user_count: int, proposed: bool, decision: bool | None
) -> SelectionState: ...
```

- `drin_zahl = (user_count - rejected) if proposed else taken`.
- `included = decision if decision is not None else (user_count > 0 and drin_zahl == user_count)`.
- `contested = decision is None and 0 < drin_zahl < user_count`.
- **Kein Clamp** auf `[0, user_count]`: `taken + rejected <= user_count` gilt strukturell
  (`uq_rating_photo_user` plus Fremdschlüssel auf `users`). Ein Clamp verbärge den Bruch dieser
  Invariante, statt ihn zu zeigen.

### API — Schreiben: `backend/src/photosort/api/album_decisions.py` (neu)

`PUT /photos/{photo_id}/album-decision`, Body `{"included": bool}`, Antwort
`AlbumDecisionOut {photo_id, included, updated_at}`.

- **Eigenes Modul und eigener Router**, weil die Entscheidung keinen Nutzer kennt: Der Endpunkt
  nimmt **kein** `current_user` entgegen. Genau deshalb kann der Router seinen Torwächter
  router-weit tragen (`APIRouter(tags=["album"], dependencies=[Depends(get_current_user)])`) — und
  genau deshalb wird er in `test_auth_guard.py::_protected_router_operations()` mitgeführt. Damit
  bekommt dieser Endpunkt das **Vollständigkeitsnetz**, das `photos.router` und `ratings.router`
  bewusst nicht haben (Auflage S1 der Spec 0430). Er gehört nicht nach `api/ratings.py`: dessen
  Gegenstand ist die Aussage **eines** Nutzers.
- Registrierung in `backend/src/photosort/main.py` (`app.include_router(album_decisions.router)`)
  und in `photosort/api/__init__.py`.
- `404` für ein unbekanntes Foto (Muster `_get_photo_or_404`). Projektbindung ausschließlich über
  die globale `photo_id`, wie bei `PUT /photos/{id}/rating` — es gibt keine Projekt-Mitgliedschaft,
  beide Nutzer sehen alle Projekte.
- Upsert mit `session.flush()` **vor** `commit`; bei `IntegrityError` die Zeile erneut lesen und die
  Änderung darauf anwenden bzw. `409` (Muster `ratings.py::_write_own_rating`,
  `photos.py::set_motif_correction`). Wiederholte identische Aufrufe bleiben folgenlos.
- **Kein `DELETE`.** „Wieder strittig werden" ist kein Zustand, den die Story kennt; ändern heißt
  den anderen Wert schreiben.

### API — Lesen: `backend/src/photosort/api/photos.py`

**Drei neue Felder an `PhotoOut`, auf allen Lesepfaden befüllt** (Muster `RankingOut.proposed`,
ADR 0098 Punkt 3 — ein je Query-Modus verschiedenes `PhotoOut` wäre die zweite, driftende
Abbildung):

- `final_selection_decision: bool | null` — die persistierte gemeinsame Entscheidung, `null` =
  keine. **Nicht** `album_decision` benennen: so heißt bereits `ratings.status`, die Entscheidung
  eines **Nutzers**.
- `in_final_selection: bool` — das Ergebnis von `selection_state(...).included`.
- `contested: bool` — das Ergebnis von `selection_state(...).contested`.

`_to_photo_out` bekommt dafür zwei **pflichtige** Schlüsselwortparameter
(`decisions: Mapping[int, bool]`, `user_count: int`) — ohne Vorgabewert, damit ein vergessener
Aufrufer unter `mypy --strict` scheitert statt still „nicht im Album" zu antworten. Vier Aufrufer:
Listing-Zweig, Entwurfszweig, Alternativen-Endpunkt, neuer Endpunkt. Zwei neue Helfer, je eine
Abfrage pro Anfrage, unabhängig von der Fotoanzahl:

- `_final_selection_decisions(session, photo_ids) -> dict[int, bool]` (Muster `_ranking_by_photo_id`).
- `_participants(session) -> list[AlbumParticipantOut]` — eine ausdrückliche Projektion auf
  `user_id` und `username`, **nie** eine Serialisierung des `User`-Objekts (Auflage S8).

**Der Nenner stammt auf dem neuen Endpunkt aus derselben Leseoperation wie die Teilnehmerliste**
(`user_count = len(participants)`), nicht aus einer zweiten, unabhängigen Zählung — Auflage S8.
Gingen beide auseinander, behauptete die Ansicht Einigkeit über zwei Teilnehmer, während die Regel
über drei rechnet; kein Feld der Antwort sähe dabei widersprüchlich aus. Die übrigen drei Lesepfade
(Listing, Entwurf, Alternativen) liefern keine Teilnehmerliste und zählen deshalb über
`_user_count(session) -> int` (`select(func.count()).select_from(User)`); dort ist der Nenner das
einzige, was sie von der Nutzermenge brauchen.

**Umbenennung und Extraktion (verbindlich, vor dem neuen Endpunkt):** `DraftContent` →
`PlacedPhotos`, `EMPTY_DRAFT` → `EMPTY_PLACEMENT`, und die Schritte (3) und (4) von
`_draft_photo_ids` werden zur reinen, privaten Funktion
`_place_in_events(rows, spans, position_by_event_id) -> PlacedPhotos`. Beide Zweige rufen sie auf.
Zweimal geschrieben ordneten Entwurf und Endauswahl dieselben Fotos verschieden — sichtbar, ohne
dass eine Prüfung rot würde.

**Neu: `GET /projects/{project_id}/album-selection`**, Antwort

```python
class AlbumParticipantOut(BaseModel):   # user_id, username
class AlbumSelectionOut(BaseModel):     # participants, has_proposal, items
```

- `participants`: **alle** Nutzer, nach `user_id` sortiert. Ohne sie bliebe der Nutzer unsichtbar,
  der noch nie etwas angefasst hat — genau der Fall, den die Story ausdrücklich als „kein
  Sonderfall" benennt. Der `username` ist über `PhotoOut.ratings[]` bereits heute sichtbar; es
  entsteht keine neue Datenklasse.
- `has_proposal`: „mindestens eine Rangzeile des letzten erfolgreichen Laufs trägt
  `selection_position`". Er trennt die beiden Leerzustände, die die Story getrennt verlangt („kein
  Auswahlvorschlag" vs. „keine Unterschiede offen") — aus den Kandidatenzeilen abgeleitet, ohne
  eigene Abfrage.
- **Kein `total`**, keine Seitenweise: Die Menge wird als Ganzes geliefert, wie der Entwurfszweig.
  Ein `total == len(items)` lüde dazu ein, etwas zu blättern, das nicht geblättert wird.

Ablauf, fünf Abfragen, keine je Foto:

1. Letzter erfolgreicher Lauf (`_latest_successful_criterion_scoring_run_id`). Keiner → leere
   Antwort mit `has_proposal: false`, Teilnehmerliste trotzdem befüllt.
2. Die Events des Laufs, einmal, als Spannenliste und Positionsabbildung (wie `_draft_photo_ids`).
3. **Kandidatenmenge** (Obermenge, in **einer** Abfrage): Fotos des Projekts mit
   `ranking.selection_position IS NOT NULL` **oder** vorhandener Entscheidungszeile **oder**
   `Photo.id IN (SELECT Rating.photo_id WHERE Rating.status IS NOT NULL)`. Sie ist vollständig:
   Ohne jede Bewertungszeile sind alle Nutzer einig, und Zugehörigkeit ohne Entscheidung setzt den
   Vorschlag voraus.
4. Hydratation der Kandidaten (`_photos_by_id` — `photo.ratings` samt `Rating.user` ist dort bereits
   eager geladen), Entscheidungen, Nutzerzahl, wirksame Motivstärken.
5. **Filter über den Zustand:** behalten wird, was `contested ∨ in_final_selection ∨ Entscheidung
   vorhanden` erfüllt — derselbe `selection_state`-Aufruf, den `_to_photo_out` danach für die
   Felder benutzt. Danach `_place_in_events` und `_to_photo_out` mit `curation_position=None` (die
   Endauswahl ist keine numerierte Auswahl; eine Zahl hier wäre eine Rangaussage über eine Menge,
   die keinen Rang kennt).

**Der dritte Teil der Antwortmenge ist keine Redundanz** (ADR 0099 Punkt 5): Ein ausdrücklich
herausgenommenes Bild gehört nicht zur Endauswahl und verschwände sonst aus beiden Sichten — die
Entscheidung ließe sich dann nicht mehr ändern. Es bleibt stattdessen mit einem Anzeigezustand
stehen, genau wie ein gestrichenes Foto im Entwurf (ADR 0071 Entscheidung 3). Kein Ausschluss bildet
die Menge.

`_to_photo_out` bekommt die Cache-Schlüssel-Auflage (Auflage S5 der Spec 0430) **erweitert**: Die
Antwort des neuen Endpunkts ist nutzerunabhängig in ihrer Menge, aber `PhotoOut.suggestion` bleibt
nutzerabhängig — die Auflage gilt für ihn wie für die übrigen Lesepfade. Die SICHERHEIT-Passage am
Docstring wird um den neuen Endpunktnamen ergänzt, nicht umgeschrieben.

### Der Nachweis, dass der Einzelentwurf unberührt bleibt

Die „Spannung, die aufzulösen ist", wird an prüfbaren Stellen aufgelöst statt zugesichert. Die vier
hier genannten sind der Ausgangspunkt; **verbindlich sind die sieben** aus dem Abschnitt
„Teststrategie" — die drei zusätzlichen decken die Gegenrichtung, den Alternativen-Endpunkt und das
Frontend ab, und der Wächter unter Punkt 3 misst dort Funktionsrümpfe statt Dateien:

1. `ratings` bekommt keine Spalte, `RatingStatus` keinen Wert — Kardinalitätsfall wie im Bestand.
2. `final_selection_decisions` hat keinen Nutzerbezug — ein struktureller Fall auf die
   Spaltenmenge der Tabelle (`{photo_id, included, updated_at}`).
3. Weder `_draft_photo_ids` noch `draft_alternatives` nennen `FinalSelectionDecision` — struktureller
   Wächter im Muster von `test_models.py::test_exactly_the_two_known_modules_write_taken_at`,
   Prüfung auf **Gleichheit** der Fundmenge.
4. Verhaltensnachweis: Vor und nach einer gemeinsamen Entscheidung sind die **Antwortmenge** von
   `GET /projects/{id}/photos?draft=true` und die `ratings[]` **beider** Nutzer identisch.

### Frontend

- **Neu:** `frontend/src/pages/AlbumSelectionPage.tsx` unter
  `PROJECT_ROUTE_PATHS.selection = '/projects/:projectId/selection'`, Titel „Endauswahl". **Eine**
  Abfrage, **zwei** Sichten: Arbeitssicht filtert auf `contested`, Ergebnissicht auf
  `in_final_selection` (plus die ausdrücklich herausgenommenen als Anzeigezustand). Umschalter als
  lokaler Zustand, Vorbelegung Arbeitssicht; kein Suchparameter, keine zweite Route.
- **Neu:** `frontend/src/api/albumSelection.ts` (`getAlbumSelection`, `setAlbumDecision`),
  `frontend/src/hooks/useAlbumSelection.ts` (`useAlbumSelectionQuery`, `useAlbumDecisionMutation`).
  Query-Key `['photos', projectId, 'selection']` — derselbe breite Präfix wie überall, damit eine
  Bewertung aus Raster/Einzelbild/Entwurf ihn mit invalidiert. Die Entscheidungsmutation schreibt
  den betroffenen Eintrag **fort** und nimmt den eigenen Schlüssel von der Invalidierung aus (Muster
  `useDraftDecisionMutation`, ADR 0098 Punkt 6).
- **Neu:** `frontend/src/utils/albumSelection.ts`, rein: `applyAlbumDecision(selection, written)`
  (setzt `final_selection_decision`, und daraus `contested = false`, `in_final_selection = included`
  — der einzige lokal ausgewertete Teil der Regel, und er ist exakt, weil eine Entscheidung immer
  überschreibt), `participantStance(photo, participant) -> 'taken' | 'struck' | 'untouched'` (liest
  ausschließlich `ratings[]` über `user_id`, nie über Position oder `some()`), plus die Textbausteine
  der Leerzustände.
- **Verschoben:** `groupDraftByDay`/`DraftDay`/`DraftEventGroup` aus `utils/albumDraft.ts` nach
  `frontend/src/utils/eventGrouping.ts` als `groupPhotosByDay`/`PhotoDay`/`PhotoEventGroup`, samt
  Tests. Beide Ansichten gliedern dieselbe Antwortform; eine zweite Kopie wäre genau die „zweite
  Wahrheit über dieselbe Liste", vor der der bestehende Docstring warnt.
- **`utils/albumDraft.ts::isInAlbum` wird auf der neuen Seite ausdrücklich NICHT benutzt.** Seine
  Aussage (`status !== 'rejected'`) gilt nur innerhalb der Antwortmenge des Entwurfszweigs; die
  Antwort der Endauswahl enthält auch Fotos, die in keinem Entwurf stehen. Die Zugehörigkeit kommt
  hier vom Server.
- **Neu:** `frontend/src/components/SelectionPhotoTile.tsx` — eigene Kachel auf `PhotoCard`, nicht
  eine zweite Ausprägung von `CurationPhotoTile`: jene trägt Zweizustand und Alternativen des
  Entwurfs, die es hier nicht gibt. Sie zeigt je Teilnehmer benannt die Haltung und trägt die eine
  Trefferfläche der gemeinsamen Entscheidung. Die Gestaltung steht im Abschnitt „UI/UX".
- **Entfällt:** `pages/PhotoComparePage.tsx` (+ Test), `PROJECT_ROUTE_PATHS.compare`, der
  Nav-Eintrag `compare` (an seine Stelle tritt `selection` mit der Beschriftung „Endauswahl"), die
  Route in `App.tsx`. `PhotoDetailPage.tsx` führt seinen Link „Zur Vergleichsansicht" auf die neue
  Seite. **Kein Redirect.**
- `frontend/src/api/types.ts`: die drei `PhotoOut`-Felder, `AlbumSelectionOut`,
  `AlbumParticipantOut`, `AlbumDecisionOut`.

### Demo-Instanz und e2e

`backend/src/photosort/demo_state.py` legt heute für **alle** Nutzer dieselben Bewertungen an. Diese
Eigenschaft bleibt für den bestehenden Block; **nach** `rebuild_run_selection` kommt ein benannter
Dissens-Block hinzu, der aus dem **tatsächlichen** Vorschlag wählt statt zu raten (vorher steht
nicht fest, welches Foto vorgeschlagen ist):

1. ein vorgeschlagenes Foto, von Nutzer 1 gestrichen → strittig;
2. ein nicht vorgeschlagenes Kandidatenfoto, von Nutzer 2 aufgenommen → strittig;
3. ein strittiges Foto mit `included=true` → „gemeinsam entschieden, drin";
4. ein einig-drinnes Foto mit `included=false` → „einig, aber herausgenommen".

Ohne diesen Block zeigte die Arbeitssicht auf der Demo-Instanz dauerhaft „keine Unterschiede", und
kein Test würde rot. Der Nachweis dagegen ist ein Kardinalitätsfall in `test_demo_state.py`.

e2e: `no-horizontal-scroll.spec.ts` (Eintrag „Vergleich"/`/compare` → „Endauswahl"/`/selection`, mit
mindestens einer Kachel als Vorbedingung, dazu beide Sichten bei 360 px), `project-nav.spec.ts`
(`PRIMARY_LABELS`, Abstandsmeldung), `popover-position.spec.ts` und `tap-targets.spec.ts` ziehen die
neue Route nach. Kein neuer Spec.

### Reihenfolge der Umsetzung — zwei Pull Requests

Jeder Schnitt ist für sich grün, für sich mergebar und hinterlässt keinen Zustand mit zwei Orten für
dieselbe Gegenüberstellung.

**PR 1 — „Die Endauswahl als Projektentscheidung" (Backend)**

1. `album_selection.py` + `backend/tests/test_album_selection.py` — rein, ohne Session, zuerst grün.
2. `models.py` (`FinalSelectionDecision`) + Alembic-Revision + `test_migration_endauswahl.py` +
   Durchlauf `test_postgres_ddl_compatibility.py`.
3. `api/album_decisions.py` + `main.py`/`api/__init__.py` + `test_api_album_decisions.py`;
   `test_auth_guard.py::_protected_router_operations` um den neuen Router; **zusätzlich der eigene,
   pfadbenannte 401-Nachweis** (Auflage S1) und die Pfad-Id-Grenzen `Path(ge=1, le=_MAX_PHOTO_ID)`
   (Auflage S3, die Grenze muss den Wert `1` des Vollständigkeitstests zulassen);
   `test_openapi_beschreibungen.py` um den neuen Pfad.
4. `api/photos.py`: die drei `PhotoOut`-Felder, `_to_photo_out`-Pflichtparameter, die zwei Helfer,
   Umbenennung `DraftContent` → `PlacedPhotos` und Extraktion `_place_in_events`, danach
   `GET /projects/{id}/album-selection`.
5. `project_deletion.py`, `demo_state.py` (+ `test_demo_state.py`).
6. `docs/architecture.md`: Eintrag `FinalSelectionDecision` im Datenmodell, die zwei Endpunkte in
   der Endpunktliste, die drei `PhotoOut`-Felder. `docs/setup.md` bleibt unberührt — keine neue
   Umgebungsvariable, kein neuer Setup-Schritt.
7. `specs/architecture/0003-securitykonzept.md`: der neue Abschnitt, die Ankerzeilen und die
   Kopfzeile (siehe „Pflege des Sicherheitskonzepts" im Abschnitt „Security").

**PR 2 — „Die gemeinsame Ansicht löst den Vergleich ab" (Frontend)**

1. `utils/eventGrouping.ts` (Verschiebung samt Tests), `api/types.ts`, `api/albumSelection.ts`,
   `hooks/useAlbumSelection.ts`, `utils/albumSelection.ts` — die reinen Teile zuerst.
2. `components/SelectionPhotoTile.tsx`, `pages/AlbumSelectionPage.tsx` samt Tests.
3. `utils/projectRoutes.ts`, `App.tsx`, `PhotoDetailPage.tsx`; Wegfall von `PhotoComparePage`.
4. e2e: `no-horizontal-scroll`, `project-nav`, `popover-position`, `tap-targets`.
5. `docs/architecture.md`: Navigation, Route, Seite, Wegfall der Vergleichsseite.

### Breaking Changes

- `PhotoOut` wächst um drei Felder (additiv, nicht brechend). Betroffen ist ausschließlich das
  eigene Frontend.
- Die Route `/projects/:id/compare` entfällt ohne Weiterleitung; `PhotoComparePage` entfällt
  ersatzlos. Ein Backend-Endpunkt entfällt dabei **nicht** — die Seite las das Standard-Listing.
- Das dritte Hauptziel der Projektnavigation heißt „Endauswahl" statt „Vergleich". Spec
  [`0347`](./0347-navigation-nebenbereich.md) AK1 nennt die alte Beschriftung; die Spec bleibt als
  abgeschlossenes Dokument unangetastet, `e2e/tests/project-nav.spec.ts` wird umgeschrieben, nicht
  gelöscht.
- Bestandsdaten: Es gibt vor dieser Story keine Entscheidungszeilen. Die Endauswahl eines
  bestehenden Projekts ist damit genau die Schnittmenge der beiden Entwürfe — kein Migrationsschritt
  berechnet rückwirkend etwas.

## UI/UX

Es gibt für diese Story **keinen Penpot-Entwurf**; die Gestaltung entsteht aus dem Design-System
[`0004`](../architecture/0004-design-system.md) und den bestehenden Bausteinen.

### Ein Ort, zwei Sichten

Route `/projects/:projectId/selection`, Titel „Endauswahl", Navigationsplatz des entfallenden
Eintrags „Vergleich". **Eine** Abfrage, **zwei** lokal gefilterte Sichten; der Umschalter lädt
nichts nach (ADR 0099 Punkt 6). Vorbelegung ist die Arbeitssicht — dort fängt die Arbeit an.

Umschalter: zwei `Button variant="ghost" size="sm"` nebeneinander (`gap-2`), beschriftet
„Unterschiede" und „Endauswahl". Der aktive trägt den Aktivstil der Projektnavigation
(`border border-border-control bg-overlay text-text-h`), der inaktive bleibt `ghost`. Beide bleiben
jederzeit bedienbar — kein `disabled`, keine zweite Route, kein Suchparameter.

### Die Haltung beider Nutzer auf einer Kachel

`SelectionPhotoTile` setzt auf `PhotoCard` auf und trägt in der Fußzeile **je Teilnehmer eine
eigene Zeile**: der `username` vorangestellt, dahinter das Kennzeichen seiner Haltung. Zwei
untereinander liegende, benannte Zeilen sind die Zusicherung „die Haltung des einen wird nie als die
des anderen dargestellt" — die Zuordnung entsteht aus dem vorangestellten Namen, nie aus Position,
Reihenfolge oder Farbe allein.

Das Kennzeichen ist der bestehende `RatingBadge`, nicht ein neues Symbol:

| Haltung | Kennzeichen | Zugänglicher Name |
|---|---|---|
| aufgenommen | `RatingBadge status="album_worthy"` (Symbol `book`, Ton `album-worthy`) | „Album-würdig" |
| gestrichen | `RatingBadge status="rejected"` (Symbol `x-circle`, Ton `rejected`, `data-struck`) | „Verworfen" |
| nie angefasst | Gedankenstrich „–" mit zugänglichem Namen, wie in `PhotoCard` bei `status === null` | „keine Bewertung" |

**Das Symbol `check` ist ausgeschlossen** — es ist im Produkt bereits die Erfolgsmeldung
(`ui/alert.tsx`), und eine Doppelbelegung bräche „Bewertungsstufen auf einen Blick unterscheidbar"
(Docstring `RatingBadge`). Die dort festgehaltene harte Regel gilt hier unverändert: **kein
Bewertungszustand wird allein durch seine Farbfläche dargestellt**, insbesondere nicht als farbiger
Punkt, Rahmen oder Balkensegment ohne Symbol oder Text. Verletzung heißt: die beiden Haltungen sind
ohne Farbwahrnehmung nicht mehr unterscheidbar.

Die Kachel trägt **keine** Motivstärkeliste — anders als `CurationPhotoTile`. Sie trägt die
Haltungen und die eine Entscheidung, sonst nichts.

### Die drei Anzeigezustände der Ergebnissicht

| Zustand | Bedingung | Darstellung | Aktion |
|---|---|---|---|
| einig drin | `final_selection_decision === null && in_final_selection` | Standardkachel, kein Zusatzkennzeichen | „Herausnehmen" |
| gemeinsam entschieden, drin | `final_selection_decision === true` | Standardkachel **plus** Kennzeichen „gemeinsam entschieden" | „Herausnehmen" |
| gemeinsam entschieden, heraus | `final_selection_decision === false` | Bildfläche gedämpft, Dateiname durchgestrichen — dasselbe Muster wie ein gestrichenes Foto im Entwurf (ADR 0071 Entscheidung 3); Kennzeichen und Bedienelement bleiben voll deckend | „Aufnehmen" |

Der Unterschied zwischen den ersten beiden ist eine **eigene Angabe**, kein Farbton: Einigkeit ist
eine Vorbelegung, eine Entscheidung ist eine getroffene Aussage. Ohne sichtbaren Unterschied wäre
nicht erkennbar, ob jemand das Bild schon angesehen hat.

### Die Trefferfläche: ein Handgriff

**Arbeitssicht** (nur `contested`): zwei Schaltflächen je Kachel — „Aufnehmen"
(`Button variant="default" size="sm"`) und „Nicht aufnehmen" (`variant="secondary" size="sm"`).
Ein Druck schreibt die Entscheidung sofort; **kein Dialog, kein Bestätigungsschritt, keine
Abstimmung**. Das Bild ist danach nicht mehr strittig und verlässt die Arbeitssicht.

**Ergebnissicht:** eine Schaltfläche je Kachel, je nach Zustand „Herausnehmen"
(`variant="secondary"`) oder „Aufnehmen" (`variant="default"`).

**`variant="destructive"` ist auf dieser Seite unzulässig.** Die Kollisionsregel im Docstring von
`ui/button.tsx` ist verbindlich: gefülltes `--danger` mit dunkler Tinte bei Radius 6px ist formgleich
mit dem Kennzeichen „Aussortiert"; `destructive` darf auf keiner Ansicht stehen, die
Bewertungs-Kennzeichen zeigt — und diese Seite zeigt sie je Teilnehmer. Verletzung heißt: Bedienelement
und Bewertungskennzeichen werden verwechselbar.

Während eine Entscheidung läuft, trägt **nur die gedrückte** Schaltfläche `busy` (die Komponente
sperrt sich damit selbst gegen Doppeldruck). Die Trefferflächen-Aufspannung auf 44 px bringt
`Button` über `tap-target` bereits mit — sie wird **nicht** über eigene Höhenklassen nachgebaut.

### Zustände der Seite

- **Ladend:** Skeleton-Kacheln im bestehenden Muster; die Seite bleibt bedienbar.
- **Fehler:** `Alert` oberhalb der Liste mit Wiederholmöglichkeit.
- **Leer A — kein Auswahlvorschlag** (`has_proposal === false`): benennt den fehlenden Schritt und
  führt zur Pipeline. Wortlaut aus der bestehenden Konstante `DRAFT_EMPTY_TEXT`
  (`AlbumDraftPage.tsx`) — ein zweiter, abweichender Satz für denselben Sachverhalt wäre eine
  zweite Wahrheit.
- **Leer B — keine Unterschiede offen** (Arbeitssicht, `has_proposal === true`, nichts strittig):
  sagt ausdrücklich, dass nichts offen ist, und verweist auf die Ergebnissicht.

Die beiden Leerzustände sind **getrennt** und werden nie zusammengefasst: Sie verlangen
verschiedene Handlungen — einmal einen Lauf starten, einmal nichts tun.

### Barrierefreiheit und Responsivität

- Jede Haltung ist dreifach codiert (Name des Teilnehmers, eigenes Symbol, zugänglicher Name) und
  nie allein farbig.
- Alle Bedienelemente sind über Tastatur erreichbar und tragen 44-px-Trefferflächen.
- Bei 360 px bleibt die Kachel vollständig bedienbar: Haltungszeilen und Bedienelement stapeln
  senkrecht, das Raster fällt auf zwei Spalten. Kein waagerechter Überlauf (`no-horizontal-scroll`
  deckt beide Sichten ab).
- Farbpaare stammen aus den Tokens des Design-Systems; der bestehende Vertragstest über
  `index.css` prüft die Kontraste.

## Security

Das Feature ist **sicherheitsrelevant**: eine neue Tabelle mit Migration, der erste Schreibendpunkt
des Projekts **ohne** `current_user`, ein Lesepfad, dessen Kandidatenmenge aus drei Quellen stammt,
von denen zwei keine Projektspalte haben, und die erste Antwort, die den vollständigen
Kontenbestand ausliefert. Keine neuen Secrets, kein neuer externer Dienst, kein Cloud-Aufruf, kein
zusätzlicher Bilddatenfluss, kein neuer Fremdtext in Antwort, Persistenz oder Log. Die Auflagen
S1–S14 der Spec 0430 gelten unverändert weiter; S5 dort wird hier erweitert (S7 unten), nicht
ersetzt.

**S1 — Der Endpunkt ohne `current_user` trägt seinen Torwächter router-weit, steht in
`_protected_router_operations()` und bekommt zusätzlich einen eigenen, pfadbenannten
401-Nachweis.** Gilt für `PUT /photos/{photo_id}/album-decision` und jeden weiteren Endpunkt, der
je an `album_decisions.router` hängt. Angriffsmodell: Ein Endpunkt ohne nutzerbezogenen Parameter
ist der einzige, dessen Authentifizierung an der Funktionssignatur **nicht sichtbar** ist — es gibt
keinen `current_user`, dessen Fehlen auffiele. Die Router-Dependency greift vor der
Body-Validierung (am Bestand belegt: `PUT /projects/{id}/cameras/{camera_id}/time-offset` liefert
im Vollständigkeitstest ohne Token und ohne Body `401`), und ihre Entfernung würde von diesem Test
gefangen. Nicht gefangen werden zwei andere Wege: ein in `_protected_router_operations()`
vergessener Router (die Parametrisierung erzeugt dann schlicht weniger Fälle, ohne rot zu werden)
und eine spätere Verschiebung des Endpunkts nach `api/photos.py`/`api/ratings.py`, deren Router
bewusst keine router-weite `dependencies`-Liste tragen. In beiden Fällen ist der Endpunkt still
öffentlich: ein unauthentifizierter Schreibzugriff, der die Bildmenge des Albums ändert. Der eigene
401-Nachweis ist die einzige Prüfung, die eine Verschiebung überlebt; die gewählten Grenzen der
Pfad-Id (S3) müssen den vom Vollständigkeitstest eingesetzten Wert `1` zulassen, sonst antwortet er
`422` statt `401`.

**S2 — Die Projektbindung des Lesepfads ist eine UND-Bedingung über die gesamte Kandidatenmenge,
nie ein Glied ihrer ODER-Verknüpfung.** Gilt für `GET /projects/{project_id}/album-selection`:
`Photo.project_id == project_id` steht außerhalb des `or_(...)` aus den drei Quellen, und der
Rangzweig ist zusätzlich an `criterion_scoring_run_id` des letzten erfolgreichen Laufs **dieses**
Projekts gebunden. Angriffsmodell: Zwei der drei Quellen sind projektblind —
`final_selection_decisions` hat nur `photo_id`, `Rating` nur `(photo_id, user_id)`, und
`PhotoRanking` trägt keine `project_id`. Ein in die ODER-Verknüpfung gerutschtes Projektprädikat ist
syntaktisch unauffällig und lässt jedes jemals bewertete oder entschiedene Foto **aller** Projekte
in die Antwort. Folge: Die Endauswahl eines Projekts enthält kohärent aussehende Fotos eines
anderen — und das ist die Menge, die der Export nimmt. `_photos_by_id` filtert nur nach Id und ist
ausdrücklich **keine** zweite Verteidigungslinie.

**S3 — Der Schreibendpunkt bindet ausschließlich über die globale `photo_id`, und diese Id ist
deklarativ begrenzt.** Muster `PUT /photos/{id}/rating`: keine Projektauflösung, keine
Mitgliedschaftsprüfung — beide Nutzer sehen alle Projekte, es gibt keine Grenze, die hier zu
ziehen wäre. `404` für ein unbekanntes Foto (`_get_photo_or_404`), ohne Rückspiegelung des
übergebenen Werts. Die Pfad-Id trägt `Path(ge=1, le=…)` mit einer eigenen Konstante im Muster
`_MAX_PHOTO_ID`. Angriffsmodell: Ein Pydantic-`int` ist unbeschränkt und landet direkt in
`session.get(Photo, photo_id)`; jenseits von 2^63 wirft SQLite einen `OverflowError` und der
Endpunkt antwortet `500` statt `404`. Die heute unbegrenzten Pfad-Ids der Bestandsendpunkte werden
dabei **nicht** mitgezogen — das ist nicht Gegenstand dieser Story.

**S4 — Der Body kennt genau ein Feld, ohne Vorgabewert, ohne `null` und ohne stillschweigend
verworfene Zusatzfelder.** `included: bool` ist pflichtig; ein leerer Body, ein fehlendes Feld oder
`null` ergibt `422` und schreibt keine Zeile. Angriffsmodell: Die Spalte trägt bewusst **kein**
`default` und **kein** `server_default`, weil die Abwesenheit der Zeile „unentschieden" bedeutet.
Ein aus Bequemlichkeit gesetzter Vorgabewert `False` am Eingabemodell verlegt genau diese
Entscheidung in die Auswertung einer fehlerhaften Anfrage: Ein abgeschnittener oder leerer Body
nähme das Foto aus dem Album, mit `200` als Antwort und ohne dass eine Anzeige das als falsch
ausweist. Es gibt keinen Weg zurück nach „unentschieden" — ein so entstandener Zustand ist nicht
korrigierbar, nur überschreibbar.

**S5 — Die Antwort des Schreibendpunkts ist der persistierte Zustand, nie die Rückspiegelung des
Bodys, und die Oberfläche schreibt genau diesen Wert fort.** `AlbumDecisionOut` wird nach dem
`flush` aus der Zeile gebildet; `applyAlbumDecision(selection, written)` liest ausschließlich
`written` aus der Server-Antwort, nie den lokal beabsichtigten Wert. Angriffsmodell: Die Mutation
nimmt ihren eigenen Query-Schlüssel von der Invalidierung aus (Muster `useDraftDecisionMutation`),
damit sich die Ergebnissicht nach einem Handgriff nicht neu ordnet. Ein Echo des Bodys zeigt
deshalb nach einem verlorenen Wettlauf dauerhaft eine Zugehörigkeit an, die so nicht gespeichert
ist — sichtbar erst nach einem vollständigen Neuladen, und bis dahin entscheiden die beiden anhand
einer Anzeige, die etwas anderes behauptet als die Datenbank.

**S6 — Gleichzeitiges Schreiben entscheidet der Primärschlüssel, und zwar innerhalb der
Transaktion.** `session.flush()` **vor** `commit`, damit der Primärschlüssel auf `photo_id` hier
greift; bei `IntegrityError` wird die Zeile erneut gelesen und die Änderung darauf angewandt
(Muster `ratings.py::_write_own_rating`, `photos.py::set_motif_correction`). Wiederholte identische
Aufrufe bleiben folgenlos außer `updated_at`. Angriffsmodell: Die Arbeitssicht lädt zum schnellen
Durchklicken ein, und jede Kachel trägt zwei Schaltflächen; zwei gleichzeitige Anfragen sehen beide
„keine Zeile" und fügen beide ein. Ohne diese Behandlung ist das Ergebnis eine `500` auf einen
alltäglichen Doppeldruck, und der Aufrufer weiß nicht, welcher der beiden Werte gilt. Bewusst
getragen bleibt „der letzte Schreibende gewinnt": Es gibt keine Optimistic-Locking-Prüfung, weil
die beiden ausdrücklich vor **einem** Gerät sitzen.

**S7 — Die Cache-Schlüssel-Auflage gilt auch hier, und die Nutzerunabhängigkeit der Antwortmenge
ist ausdrücklich kein Grund, den Nutzer aus dem Schlüssel zu lassen.** Bekommt
`GET /projects/{id}/album-selection` eine Antwort-Zwischenspeicherung, ein `ETag` oder ein
`Cache-Control` über `no-store` hinaus, oder wird der Client-Query-Cache je persistiert
(`persistQueryClient` o.ä.), muss der Schlüssel den Nutzer enthalten — der Query-Schlüssel
`['photos', projectId, 'selection']` tut das nicht. Von den zwei Ursachen aus S5 der Spec 0430
trifft hier nur eine zu: Die **Menge** ist nutzerunabhängig, `PhotoOut.suggestion` bleibt es nicht.
**Eine Ursache genügt; die Abwesenheit der anderen ist keine Erlaubnis.** Angriffsmodell: Das
Frontend ist eine PWA mit Workbox (`registerType: 'autoUpdate'`), der Service-Worker-Cache ist je
Browserprofil geteilt, das JWT liegt in `localStorage`, und zwei Personen an einem Gerät ist hier
nicht der Randfall, sondern der beschriebene Regelfall. Bei Verletzung sieht der eine den
Vorschlagszustand des anderen als seinen eigenen, auf einer Seite, deren ganze Aussage die Trennung
der beiden Stände ist.

**S8 — `participants` trägt genau `user_id` und `username`, und seine Länge ist der Nenner der
Regel.** Die Liste entsteht aus einer ausdrücklichen Projektion auf zwei Spalten, nie aus einer
Serialisierung des `User`-Objekts (`password_hash`, `created_at` dürfen den Endpunkt nicht
erreichen); `user_count` stammt aus **derselben** Leseoperation wie die Liste, nicht aus einer
zweiten, unabhängigen Zählung. Angriffsmodell zweifach. Erstens ist dies der erste Endpunkt, der
den vollständigen Kontenbestand ausliefert — ein `model_validate(User)` mit `from_attributes`
schöbe den Passwort-Hash in eine Antwort, die im Browser beider Nutzer und in jedem Cache landet.
Zweitens: Gehen Liste und Nenner auseinander, behauptet die Ansicht eine Einigkeit über zwei
Teilnehmer, während die Regel über drei rechnet — die Endauswahl wäre dann kleiner als die Anzeige
sie zeigt, ohne dass ein Feld der Antwort widersprüchlich aussieht.

**S9 — Die drei neuen `PhotoOut`-Felder haben an keinem der vier Aufrufer einen Vorgabewert.**
`decisions` und `user_count` sind pflichtige Schlüsselwortparameter von `_to_photo_out`.
Angriffsmodell: Ein vergessener Aufrufer wirft keine Ausnahme und liefert keinen Fehlercode — er
antwortet `in_final_selection: false` für jedes Foto, plausibel und still. Das ist die Menge, die
als Album gilt und die der Export nimmt; der Fehler zeigt sich erst an einem leeren Album, nicht an
der Stelle, an der er entsteht. `mypy --strict` ist hier die einzige Prüfung, die ihn vor der
Laufzeit fängt.

**S10 — Die neue Seite rendert jeden fremdbestimmten Text ausschließlich als React-Textknoten.**
Gilt für `AlbumSelectionPage.tsx`, `SelectionPhotoTile.tsx` und jeden von ihnen genutzten Baustein,
namentlich für `username` (aus `participants` und `ratings[]`) und den Dateinamen (aus der Antwort
des externen WebDAV-Systems): nie über `dangerouslySetInnerHTML`, nie in `href`, `src` oder
`style`, nie in eine per `innerHTML` gebaute Einblendung, nie in eine URL. Keine zweite
Sanitierung — beide Werte sind es im Bestand nicht und brauchen es als Textknoten auch nicht. Bei
Verletzung läuft der eingeschleuste Inhalt im Browser **beider** Nutzer, während das JWT in
`localStorage` liegt.

**Bewusst getragene Restrisiken.**

- **Eine gemeinsame Entscheidung ist keinem Urheber zuzuordnen** — kein `user_id`, kein
  `decided_by`, keine Historie, kein Veto. Wer ein Bild herausnimmt, hinterlässt außer `updated_at`
  keine Spur, und ein versehentlicher Druck ist nicht als solcher erkennbar. Tragbar, weil die
  Zuordenbarkeit, die ADR 0003 verlangt, unangetastet weiterbesteht: Die beiden `Rating`-Zeilen
  bleiben unverändert und benannt, und sie sind es, die sagen, wer was wollte. Getragen wird das
  zusätzlich von zwei Eigenschaften, die aus anderem Grund ohnehin gelten und hier
  sicherheitstragend werden: Jede Entscheidung ist über dieselbe Ansicht mit einem Handgriff
  umkehrbar, und ein ausdrücklich herausgenommenes Bild bleibt sichtbar in der Antwortmenge
  stehen — fiele es heraus, wäre eine Fehlentscheidung über die Oberfläche nicht mehr korrigierbar.
  Zwischen den beiden Nutzern gilt kein Innentäter-Modell.
- **Der Nenner der Regel ist die globale Nutzerzahl.** Ein drittes, administrativ angelegtes Konto
  ändert die Endauswahl **jedes** Projekts, ohne dass ein Schreibzugriff stattfindet: Fotos, über
  die die beiden bisher einig waren, werden strittig und gehören damit nicht mehr zur Endauswahl.
  Tragbar bei einem geschlossenen Zwei-Personen-System ohne Self-Signup; benannt, weil der Weg
  dahin (ein CLI-Aufruf) keinerlei Bezug zu dieser Ansicht hat und die Wirkung deshalb überrascht.

**Ausdrücklich geprüft und ohne Befund:** keine neue Datenklasse zwischen den beiden Nutzern — die
namentliche Fremdbewertung steht heute schon in `PhotoOut.ratings[]` und wird auf der abgelösten
Vergleichsseite bereits namentlich angezeigt; „nie angefasst" war als Abwesenheit eines Eintrags
ebenso bereits ableitbar. Die drei neuen `PhotoOut`-Felder sind Projektaussagen und tragen auf
keinem Lesepfad ein nutzerbezogenes Datum. Kein `DELETE`, also kein Pfad, der eine bestehende
Entscheidung ersatzlos entfernt. Keine Berührung von Secrets, `.env`, Consent-Schalter,
Kostenschätzung oder Bilddatenfluss. Kein Rate-Limiting nötig, konsistent mit der übrigen API. Die
`downgrade()`-Migration verliert alle gemeinsamen Entscheidungen — das steht in ihrem Docstring und
ist kein Datenverlust, den ein Angreifer auslösen könnte. Ein Nutzerwechsel im geladenen Frontend
ist heute nicht möglich (kein Logout, kein Persistieren des Query-Caches); der In-Memory-Cache
überlebt ihn deshalb nicht — S7 wehrt ausschließlich die künftige Einführung einer Persistenz ab.

### Pflege des Sicherheitskonzepts (Teil von PR 1)

`specs/architecture/0003-securitykonzept.md` bekommt einen Abschnitt unter `## Angriffsflächen`,
hinter „Der Album-Entwurf je Nutzer", mit den vier über diese Story hinaus gültigen Aussagen:

1. Ein Endpunkt ohne nutzerbezogenen Parameter ist der einzige, dessen Authentifizierung an der
   Signatur unsichtbar ist — Torwächter router-weit **plus** Listeneintrag **plus** eigener
   pfadbenannter 401-Nachweis. Die Doppelung trägt, weil der Listeneintrag weder sein eigenes
   Vergessen noch eine spätere Verschiebung des Endpunkts überlebt.
2. Die Cache-Schlüssel-Auflage in ihrer dritten Fassung: Auch die **Abwesenheit** einer der beiden
   Ursachen von Anfang an ist keine Erlaubnis, solange ein einziges Feld der Antwort nutzerabhängig
   ist. Geltungsbereich erweitert um jede künftige Persistenz des Client-Query-Caches, nicht nur um
   die HTTP-Ebene.
3. Bei einer Kandidatenmenge aus mehreren projektblinden Quellen ist die Projektbindung eine
   UND-Bedingung über die Vereinigung, nie ein Glied ihrer ODER-Verknüpfung. Ausfallrichtung:
   kohärent aussehende Fremddaten statt einer erkennbar falschen Menge.
4. Erstmals eine Projektentscheidung ohne Urheber: Eine Tabelle ohne Nutzerbezug darf keine Aussage
   tragen, deren Rücknahme nicht über dieselbe Oberfläche möglich ist. Dazu: Hängt eine abgeleitete
   Menge an der globalen Nutzerzahl, ändert das Anlegen eines Kontos sie ohne jeden Schreibzugriff.

Dazu die Ankerliste (Zeile „Auth-Torwächter als Router-Dependency" um `album_decisions` erweitern,
zwei weitere Ankerzeilen für S2 und S8) und die Kopfzeile „Letzte Aktualisierung".

## Teststrategie

Zwei Pull Requests, je ein eigener Rot-Grün-Zyklus. **Die reine Funktion zuerst:**
`album_selection.py::selection_state` ist ohne Session vollständig prüfbar und muss grün sein,
bevor Migration und Endpunkte ihren ersten Fall bekommen. Innerhalb von PR 1 gilt dieselbe
Reihenfolge zwischen Schema und API — ein Endpunktfall gegen das alte Schema ist nicht rot,
sondern ein Importfehler.

**Die Fixture-Falle dieser Story, vorweg:** `conftest.py::authenticated_api_client` seedet genau
**einen** Nutzer; der zweite kommt über `_make_second_user`. Bei einem Nutzer ist jedes
vorgeschlagene, unangefasste Foto in der Endauswahl und nichts ist strittig. Jeder Fall, dessen
Aussage „alle einig" oder „strittig" lautet, legt den zweiten Nutzer deshalb **ausdrücklich** an —
sonst ist er inhaltsleer und trotzdem grün.

### Die Zusicherungen, die ohne eigenen Testfall still brechen

Falschergebnis statt Ausnahme, grüne Suite, kein Fehlerbild. Diese Liste ist verbindlich.

1. **Einigkeit ist Vorbelegung, keine Sperre.** Ein einig-drinnes Foto ohne Entscheidungszeile
   lässt sich mit `included: false` herausnehmen und danach wieder aufnehmen. Eine Umsetzung, die
   den Konsenszweig vor die Entscheidung stellt, besteht jeden anderen Fall.
2. **Eine Entscheidung überlebt beide Änderungswege — und jeder Weg braucht beide Richtungen im
   selben Fall.** (a) Spätere Entwurfsänderung: einig→uneins **und** uneins→einig lassen
   `final_selection_decision` und `in_final_selection` unverändert, `contested` bleibt `false`.
   (b) Neuer Vorschlagslauf, auch wenn das Foto danach nicht mehr vorgeschlagen ist. Getrennt
   geschrieben besteht jede Hälfte auch bei einer Umsetzung, die die Entscheidung immer oder nie
   gewinnen lässt.
3. **Ein strittiges, unentschiedenes Bild gehört nicht zur Endauswahl — geprüft als Nachsatz JEDES
   Falls.** Helfer `assert_selection_invariants` mit drei Aussagen: nie `contested` und
   `in_final_selection` zugleich; `contested` ⇒ keine Entscheidung; Entscheidung vorhanden ⇒
   `in_final_selection == final_selection_decision`. Einzelfälle prüfen das nur dort, wo jemand
   daran gedacht hat, und der Bruch zeigt sich typischerweise in einem anderen Aufbau.
4. **`drin_zahl` liest bei vorgeschlagenen Fotos die Streichungen, bei nicht vorgeschlagenen die
   Aufnahmen — die beiden Trennfälle sind nicht symmetrisch.** Vorgeschlagen, einer aufgenommen,
   einer unangefasst → **einig drin** (eine Umsetzung, die hier `taken` zählt, liest „strittig").
   Nicht vorgeschlagen, einer aufgenommen → **strittig** (eine Umsetzung, die hier
   `user_count - rejected` zählt, liest „einig drin"). Jeder Fall allein lässt die andere Hälfte
   durch.
5. **Zeilenvorhandensein ist keine Aussage.** `taken`/`rejected` zählen über `Rating.status`, nie
   über die Existenz der Zeile — seit ADR 0098 kann eine Zeile allein den Favoriten tragen. Zwei
   beobachtbare Fälle: eine reine Favoritenzeile des anderen Nutzers lässt ein vorgeschlagenes Foto
   einig drin, und bringt ein nicht vorgeschlagenes gar nicht erst in die Antwort.
6. **`n` ist der Nutzerbestand, und der Beweis dafür ist `n = 1`.** Bei genau einem Nutzer ist
   jedes vorgeschlagene, unangefasste Foto in der Endauswahl und nichts strittig; ein hartkodiertes
   `== 2` liefert dort flächendeckend `in_final_selection: false`. Ein dritter Nutzer wird dafür
   nicht erfunden — die Kardinalität ist Parameter der reinen Funktion.
7. **`user_count == 0` ist kein Konsens.** Ohne den `user_count > 0`-Wächter wäre `0 == 0` wahr und
   jedes vorgeschlagene Foto Teil der Endauswahl einer nutzerlosen Instanz.
8. **Kein Clamp.** `rejected > user_count` liefert weder `included` noch `contested` und wird nicht
   zurechtgerückt. Der Fall hält die Abwesenheit fest; ein später eingefügter Clamp wird rot.
9. **Die Kandidatenmenge ist ein ODER dreier Prädikate, und jedes braucht einen Fall, der nur über
   es hineinkommt.** Je ein Foto ausschließlich über `selection_position`, ausschließlich über die
   Entscheidungszeile, ausschließlich über eine Bewertungszeile. Dazu die Gegenprobe (keines der
   drei → erscheint nicht) und der Fall, der Kandidaten- von Antwortmenge trennt: ein von **beiden**
   gestrichenes, unentschiedenes Foto ist Kandidat und erscheint trotzdem nicht. Ohne ihn ist eine
   Umsetzung, die den Zustandsfilter ganz weglässt, in allen übrigen Fällen grün.
10. **Ein ausdrücklich herausgenommenes Bild bleibt in der Antwort.** `included: false` auf einem
    Foto, das weder vorgeschlagen noch bewertet ist — es steht weiter da, sonst wäre die
    Entscheidung entgegen dem Akzeptanzkriterium nicht mehr änderbar.
11. **Die drei Felder stehen auf allen vier Lesepfaden mit demselben Wert.** Feldgleichheit über
    Listing, Entwurfszweig, Alternativen-Endpunkt und den neuen Endpunkt für dasselbe Foto (Muster
    `test_present_is_identical_in_the_listing_and_in_the_draft`).
12. **`has_proposal` trennt die beiden Leerzustände.** Kein erfolgreicher Lauf → `false`, leere
    `items`, `participants` **trotzdem befüllt**; erfolgreicher Lauf ohne eine einzige
    `selection_position` → ebenfalls `false`; mindestens eine → `true`. Ein Fall, der nur die leere
    Liste prüft, lässt beide Leerzustände zusammenfallen — die Oberfläche schickt den Nutzer dann in
    die Pipeline, obwohl dort nichts zu tun ist.
13. **`participants` führt jeden Nutzer, auch den ohne jede Bewertung** — nach `user_id` sortiert,
    Kardinalität gleich dem Nutzerbestand. Aus `ratings[]` abgeleitet fehlte genau der Nutzer, den
    die Story ausdrücklich als „kein Sonderfall" benennt.
14. **Ein neuer Lauf verschiebt das entschiedene Foto an seine neue Stelle.** Die Rangzeile hat
    Vorrang vor der Zeitzuordnung.
15. **`_place_in_events` wird von beiden Zweigen aufgerufen, nicht zweimal geschrieben.** Derselbe
    Bestand liefert im Entwurfszweig und in der Endauswahl dieselbe Event-Zuordnung und dieselbe
    Reihenfolge innerhalb jedes Events — das Paar gehört in **einen** Fall.
16. **`curation_position` ist auf dem neuen Endpunkt `null`.** Eine Zahl wäre eine Rangaussage über
    eine Menge, die keinen Rang kennt.
17. **`included` ist NOT NULL und trägt keinen Default — geprüft an beiden Artefakten.** Gerenderte
    Postgres-DDL ohne `DEFAULT` und ein `INSERT` ohne die Spalte gegen das aus `Base.metadata`
    erzeugte Schema. Unter SQLite ist BOOLEAN ein INTEGER; ein versehentliches
    `server_default=sa.text("0")` bliebe ohne die DDL-Hälfte unsichtbar, und die Modellseite allein
    zu vergessen fällt erst produktiv auf.
18. **Der Body erzwingt dieselbe Ausdrücklichkeit wie die Spalte.** `{}` und `{"included": null}`
    ergeben `422`. Sonst hat die Spalte keinen Vorgabewert und die API schon.
19. **Die Zeile bleibt einzig, und es gibt keinen Weg zurück.** Zweimal derselbe Wert → `200`,
    weiterhin genau eine Zeile, nur `updated_at` wandert; Gegenwert → dieselbe Zeile mit
    gewechseltem `included`. Kein `DELETE` auf dem Pfad.
20. **Der `IntegrityError`-Zweig wird ausgeführt** (Muster `test_api_motif_corrections.py`: `flush`
    per Monkeypatch einmalig werfend). Danach genau eine Zeile mit dem zuletzt geschriebenen Wert
    und keine `500` auf einen alltäglichen Doppeldruck.
21. **Die Demo-Instanz zeigt alle vier Zustände, und sie tut es deterministisch.** Zwei Neuaufbauten
    erzeugen dieselben Foto-Ids in denselben Rollen — die Auswahl aus dem tatsächlichen Vorschlag
    ist der Ort, an dem eine `set`-Iteration unbemerkt sprunghaft wird. Ohne Nutzer und mit genau
    einem Nutzer schreibt der Block nichts; bei `n = 1` ist Dissens arithmetisch unmöglich.
22. **Die Oberfläche leitet die Zugehörigkeit nie selbst her.** `isInAlbum` und jede andere
    Ableitung aus `ratings[]` bleiben von der neuen Seite fern; `in_final_selection` kommt vom
    Server. `applyAlbumDecision` ist der einzige lokal ausgewertete Teil und schreibt alle drei
    Felder gemeinsam fort.
23. **Die Haltung wird je Teilnehmer zugeordnet, nie über die Reihenfolge.** Der Aufbau: `ratings[]`
    genau umgekehrt zu `participants` sortiert, und nur der **zweite** Teilnehmer trägt eine
    Bewertung. `ratings[0]` und `some()` bestehen jeden natürlich gebauten Fall.
24. **Je Teilnehmer genau eine Haltungszeile, auch ohne Bewertung.** Die Zahl der Zeilen ist die
    Kardinalität von `participants`, nie die von `ratings[]`.
25. **Weder Umschalten noch Entscheiden lädt nach.** Zähler auf dem gemockten `getAlbumSelection`:
    genau ein Aufruf über Umschalten und eine Entscheidung hinweg, und die Id-Folge der
    Ergebnissicht ist vor und nach der Entscheidung identisch.
26. **Die beiden Leerzustände sind getrennt und nie beide da.** `has_proposal: false` zeigt **die
    Konstante** `DRAFT_EMPTY_TEXT` — geprüft über Identität mit der importierten Konstante, nie über
    ein kopiertes Literal, dazu ein struktureller Fall, dass der Satz unter `frontend/src/` genau
    einmal als Literal vorkommt.
27. **Kein `check`-Symbol und kein `variant="destructive"` auf dieser Seite** — beides als
    Abwesenheit im gerenderten DOM geprüft, nicht als Absichtserklärung.
28. **Die alte Route entfällt ohne Weiterleitung.** `/projects/:id/compare` rendert nichts und
    leitet nirgendwohin; ohne den Fall ist sowohl ein vergessener Wegfall als auch ein
    eingeschlichener Redirect unsichtbar.

### Der Nachweis, dass der Einzelentwurf unberührt bleibt: sieben Stellen, nicht vier

Die vier Stellen aus „Architektur / Umsetzung" tragen die Zusage nicht allein. Verbindlich sind:

1. `ratings` bekommt keine Spalte, `RatingStatus` keinen Wert — Kardinalitätsfall wie im Bestand.
2. `final_selection_decisions` hat keinen Nutzerbezug — struktureller Fall auf die **Gleichheit**
   der Spaltenmenge mit `{photo_id, included, updated_at}`.
3. Struktureller Wächter über `_draft_photo_ids` und `draft_alternatives`, Prüfung auf **Gleichheit**
   der Fundmenge. **Die Einheit ist der Funktionsrumpf, nicht die Datei** (AST, nicht Textsuche):
   `_to_photo_out` liegt im selben Modul und liest `FinalSelectionDecision` zwingend, weil die drei
   Felder auf allen Lesepfaden stehen. Ein Wächter auf Dateiebene wäre entweder dauerhaft rot oder
   so weit gefasst, dass er nichts zusichert. Die Selbstschutz-Gegenproben des Musters gelten auf
   derselben Granularität: je erkannte Leseform ein Mikrotest gegen ein literales Schnipsel, eine
   Gegenprobe für das bloße Nennen des Namens in einem Kommentar, und eine Positiv-Gegenprobe gegen
   die leere Fundmenge.
4. Verhaltensnachweis **Entscheidung ⇒ Entwurf**: vor und nach einer gemeinsamen Entscheidung sind
   die **vollständige Id-Folge** und `total` von `GET /projects/{id}/photos?draft=true` sowie die
   `ratings[]` **beider** Nutzer identisch. Verglichen wird die Folge, nicht die Menge.
5. Verhaltensnachweis **Entwurf ⇒ Entscheidung** (die Gegenrichtung, die 4 nicht abdeckt): Nach
   einer Änderung der Albumentscheidung eines Nutzers sind `final_selection_decision`,
   `in_final_selection` und `contested` des Fotos unverändert.
6. Der Alternativen-Endpunkt ist ebenfalls unberührt: seine Antwortmenge und ihre Reihenfolge sind
   vor und nach einer gemeinsamen Entscheidung identisch.
7. Frontend-Wächter: `AlbumDraftPage.tsx` und `CurationPhotoTile.tsx` nennen keines der drei neuen
   Felder, und `AlbumSelectionPage`/`SelectionPhotoTile` importieren `isInAlbum` nicht. Die Felder
   stehen am `PhotoOut` des Entwurfszweigs und liegen dort griffbereit; ohne diesen Wächter ist die
   zweite Ebene im Einzelentwurf jederzeit einen Renderaufruf entfernt.

### Unit (pytest, rein, ohne Session)

`backend/tests/test_album_selection.py`, ohne Session, ohne Modellimport:

- Punkte 4, 7, 8 und die vollständige Wahrheitstafel über `proposed × decision ∈ {None, true,
  false}`.
- **Die Kardinalität als Achse:** `pytest.mark.parametrize` über `user_count ∈ {1, 2, 3, 4}` mit je
  den Belegungen „alle drin", „keiner drin", „einer fehlt". Bei `n = 1` ist `contested` für keine
  Belegung erreichbar — das ist die Aussage, nicht ein Randfall.
- Eine Entscheidung überschreibt in **beide** Richtungen und unabhängig von jeder Belegung der
  übrigen Parameter (Punkte 1 und 2 auf reiner Ebene, bevor eine Session im Spiel ist).
- `SelectionState` ist `frozen` — eine Zuweisung an `included` wirft.

### Integration (pytest, In-Memory-SQLite, `httpx.ASGITransport`)

**PR 1 — Schreibendpunkt** (`test_api_album_decisions.py`): Punkte 18–20; `404` für ein unbekanntes
Foto ohne Rückspiegelung des Werts; `401` ohne Token, zusätzlich über den router-weiten Torwächter
in `test_auth_guard.py::_protected_router_operations()`; `PUT` mit dem Token des einen Nutzers und
Lesen mit dem des anderen ergibt dasselbe Ergebnis; `test_openapi_beschreibungen.py` führt den neuen
Pfad.

**PR 1 — Migration** (`test_migration_endauswahl.py`, Muster
`test_migration_albumentscheidung.py`): die Revision hängt am tatsächlichen Head
(`test_migration_chain.py`); `photo_id` ist Primärschlüssel **und** Fremdschlüssel unter
ausgeschriebenem Namen; `included` nach Punkt 17 an beiden Artefakten; `updated_at` ist ein
zonenloser Zeitstempel mit `server_default`; der `downgrade()` legt die Tabelle ab und sein Docstring
benennt den Verlust aller gemeinsamen Entscheidungen. `test_postgres_ddl_compatibility.py` bekommt
den Durchlauf für upgrade und downgrade.

**PR 1 — Leseendpunkt** (`test_api_photos.py`): Punkte 1–3, 5, 6, 9–16, dazu die sieben Stellen des
Nachweisblocks; `assert_selection_invariants` als Nachsatz jedes Falls beider neuer Blöcke; ein
`project_id` eines fremden Projekts liefert `404`, ein Projekt ohne Lauf `200` mit leerer Liste und
befüllten `participants`.

**PR 1 — Löschzusage und Demo** (`test_project_deletion.py`, `test_demo_state.py`): der
Vollständigkeitswächter gegen `Base.metadata` greift über den echten Fremdschlüssel, dazu ein
Zeilenfall im Muster `test_the_project_deletion_removes_the_motif_rows_too`. Punkt 21 als
Kardinalitätsfall über die vier benannten Zustände;
`test_rated_project_covers_every_album_decision_and_the_favorite_marker` bleibt unverändert grün,
und `test_runs_without_any_user_and_writes_no_ratings` ebenso.

### Frontend-Komponente (vitest + Testing Library)

- **Reine Ableitungen zuerst und getrennt von der Komponente:** `applyAlbumDecision`,
  `participantStance`, die Textbausteine — tabellengetrieben, ohne Router, ohne QueryClient.
  Punkte 22 und 23.
- Die Verschiebung `groupDraftByDay` → `eventGrouping.ts::groupPhotosByDay` ist **verhaltensfrei**
  und hat keinen Rot-Zustand. Es gilt der Nachweis ohne Rot-Grün des Testkonzepts: Importe und
  Namen ändern sich, **Rümpfe und Erwartungen nicht**, die Testknoten-Menge bleibt gleichmächtig mit
  gleichem Ausgang. Eine dabei geänderte Erwartung ist ein Finding, keine Lösung.
- `SelectionPhotoTile`: Punkte 23, 24, 27; die drei Haltungen mit ihrem zugänglichen Namen,
  assertiert **innerhalb der jeweiligen Zeile**, nie tileweit — eine tileweite Textsuche besteht
  auch dann, wenn beide Zeilen dieselbe Haltung zeigen. Die Zusagen von `RatingBadge` werden am
  Aufrufer nicht erneut bewiesen; bewiesen wird die Zuordnung Name → Haltung.
- `AlbumSelectionPage`: Vorbelegung Arbeitssicht; Punkt 25; ein entschiedenes Bild verlässt die
  Arbeitssicht sofort, ohne dass sich die Ergebnissicht umordnet; Punkt 26; die drei
  Anzeigezustände der Ergebnissicht samt der Beschriftung ihrer jeweils einen Schaltfläche; ladend
  (Skeleton) und Fehler (Alert mit Wiederholung, die genau eine neue Anfrage auslöst).
- `useAlbumDecisionMutation`: schreibt den betroffenen Eintrag fort und nimmt den eigenen
  Query-Key von der Invalidierung aus — zwei Schlüssel, einer unangetastet, einer invalidiert.
- Zweiter Druck während laufender Mutation: eine **Menge** laufender Foto-Ids, nicht eine einzelne
  (Muster `rejectingPhotoIds`); nur die gedrückte Schaltfläche trägt `busy`.
- Routing: Punkt 28; `PhotoComparePage.test.tsx` entfällt mit der Seite; `projectRoutes.test.ts` und
  `ProjectNav.test.tsx` führen `selection`/„Endauswahl" statt `compare`/„Vergleich";
  `PhotoDetailPage` verlinkt auf die neue Route.

### E2E (`e2e/`, Playwright/Chromium)

Kein neuer Spec. Zwei ziehen nach, einer wird ergänzt, einer bleibt unberührt:

- **`no-horizontal-scroll`** — der Eintrag „Vergleich"/`/compare` wird zu „Endauswahl"/`/selection`
  mit `requiresTile: true`. Dazu **zwei** Messungen statt einer: die Ergebnissicht ist ein anderes
  DOM als die Arbeitssicht, und die heutige Schleife misst je Route genau einmal.
- **`project-nav`** — `PRIMARY_LABELS` trägt „Endauswahl"; die Abstandsmeldung, die heute
  „Vergleich" wörtlich nennt, wird umgeschrieben, nicht gelöscht.
- **`tap-targets`** — **Ergänzung, kein Nachziehen:** der Spec fährt `/compare` heute gar nicht an.
  Neu geprüft werden die beiden Entscheidungsschaltflächen einer Kachel der Arbeitssicht und die
  beiden Umschalter; `EXPECTED_CONTROL_COUNT` wird bewusst angehoben. Die Aufspannung auf 44 px
  entsteht über ein `::after`-Pseudoelement und ist in jsdom prinzipiell nicht messbar — das
  Aufnahmekriterium ist damit erfüllt. Rot-Nachweis im Pull Request.
- **`popover-position`** — **unverändert.** Der Spec fährt `/compare` nicht an, und die neue Kachel
  trägt keine Motivstärkeliste und damit kein Popover.
- **`grid-columns`** bekommt **keinen** Eintrag: Der Spec deckt allein das Foto-Raster ab, auch die
  Album-Entwurfsseite steht nicht darin, und der akute Fehlermodus bei 360 px liegt bereits bei
  `no-horizontal-scroll`. Ein zweiter Rasterspec ohne belegten Rot-Nachweis wäre der immer-grüne
  Spec, den das Aufnahmekriterium ausschließt.

### Edge Cases, die die Story nicht nennt

- Beide Nutzer haben dasselbe Foto gestrichen, niemand hat entschieden: es erscheint nicht. Der Weg
  zurück führt über den Einzelentwurf.
- Ein Foto trägt eine Entscheidung, aber weder Rangzeile noch Bewertungszeile — der Zustand nach
  einem neuen Lauf, der es fallen lässt.
- Ein Foto trägt ausschließlich eine Favoritenzeile (Punkt 5).
- Ein Lauf ohne jede `selection_position`: `has_proposal: false`, obwohl der Lauf erfolgreich war.
- Genau ein Nutzer im Bestand (Punkt 6) und gar kein Nutzer (Punkt 7).
- Ein Foto der Endauswahl, das der neue Lauf einem Event zuordnet, in dem es zuvor nicht stand.
- Ein Event ohne ein einziges Bild der Endauswahl: die Gruppe fällt in der Ergebnissicht weg, in der
  Arbeitssicht ist sie kein eigener Zustand.
- Zweiter Druck auf dieselbe Kachel, während die erste Entscheidung läuft.
- Ein Nutzer ohne jede Bewertungszeile steht trotzdem mit Namen und Haltungszeile auf jeder Kachel.

### Coverage

Das Gate ist nicht gefährdet: der Bestand liegt bei 97 % gegen ein Gate von 80 %, die berührten
Module bei 98–100 %, die Migration zählt nicht mit (`--cov=photosort` erfasst `alembic/` nicht) und
die größte Codemenge liegt im Frontend, für das es kein Gate gibt. Die Zahl sagt hier nichts: Jede
der 28 Zusicherungen oben bricht bei vollständig ausgeführten Zeilen.

### Pflege des Testkonzepts (Teil von PR 1)

`specs/architecture/0002-testkonzept.md` bekommt eine neue Backend-Sektion hinter der
ADR-0098-Sektion, mit fünf projektweit gültigen Mustern: (1) **Eine Regel, die für jede Kardinalität
`n` gilt, während das Produkt nur `n = 2` kennt, wird über den Parameter geprüft, nicht über einen
erfundenen dritten Gegenstand — und der trennende Integrationsfall ist der entartete `n = 1`**; dazu
die Falle, dass die Standard-Fixture genau einen Nutzer seedet und jede Aussage über „alle" dort leer
besteht. (2) **Eine abgeleitete Menge mit überschreibendem Sonderfall braucht beide Richtungen im
selben Fall** — die Vorbelegung wirkt nur in Abwesenheit, die Entscheidung überlebt jede Änderung der
Vorbelegungs-Eingänge; getrennt geschrieben besteht jede Hälfte auch bei einer Umsetzung, die immer
oder nie überschreibt. (3) **Liegen der verbotene und der pflichtige Zugriff im selben Modul, ist die
Einheit des strukturellen Wächters der Funktionsrumpf, nicht die Datei** — samt Gegenproben auf
derselben Granularität. (4) **Eine Kandidaten-Obermenge aus einem ODER mehrerer Prädikate braucht je
Prädikat einen Fall, der nur über es hineinkommt, eine Gegenprobe und einen Fall, der Kandidaten- von
Antwortmenge trennt.** (5) **Ein Prädikat, das in der Antwort unbeobachtbar ist, hat seinen Nachweis
an der Ableitung, nicht an der Antwort.** Dazu ein Einzelpunkt: Ein Textbaustein, der an zwei Orten
gilt, wird über **Identität mit der Konstante** geprüft, plus Einmaligkeit des Literals im
Quellbaum — eine Zeichenkettengleichheit besteht auch gegen eine Kopie.

Zwei Nachträge an Ort und Stelle in der E2E-Tabelle desselben Dokuments: Die Zeile zu
`no-horizontal-scroll` nennt „Foto-Vergleich", der mit dieser Story entfällt; die Zeile zu
`tap-targets` nennt elf geprüfte Bedienelemente, der Spec führt derzeit dreizehn und danach mehr; die
Zeile zu `popover-position` nennt `CurateCategoriesPage` statt der tatsächlich angefahrenen
Album-Entwurfsseite. Die beiden letzten sind Altdrift und werden bei dieser Gelegenheit auf den
wirksamen Stand gezogen.

## Entscheidungen

- Die Endauswahl wird **abgeleitet**, gespeichert wird ausschließlich die ausdrückliche
  Projektentscheidung (ADR 0099). Damit gelten „Einigkeit ist Vorbelegung, keine Sperre" und „eine
  Entscheidung überlebt Entwurfsänderungen und neue Vorschlagsläufe" beide, ohne durchsetzenden
  Code.
- **Ein strittiges, unentschiedenes Bild gehört nicht zur Endauswahl.** Die Story spricht das nicht
  aus; die Kriterien „Bilder, die in beiden Entwürfen stehen, sind **ohne Zutun** Teil der
  Endauswahl" und „Für jedes strittige Bild wird eine Entscheidung getroffen" beantworten es
  zusammen. Als technische Detailentscheidung innerhalb der akzeptierten Story entschieden, nicht
  erneut zurückgefragt.
- Die Zahl **zwei** steht an keiner Stelle im Code — „alle einig"/„nicht alle einig" ist für jede
  Nutzerzahl definiert und fällt bei zwei Nutzern mit der Aussage der Story zusammen.
- **Kein `DELETE`** auf der gemeinsamen Entscheidung: „wieder strittig werden" ist kein Zustand, den
  die Story kennt.
- Die Demo-Instanz bekommt einen benannten Dissens-Block. Ohne ihn zeigte die Arbeitssicht dort
  dauerhaft „keine Unterschiede", ohne dass eine Prüfung rot würde.
- Ein ausdrücklich herausgenommenes Bild bleibt in der Antwortmenge (Anzeigezustand, Muster ADR 0071
  Entscheidung 3) — sonst wäre die Entscheidung entgegen dem Akzeptanzkriterium nicht mehr änderbar.
- Alle vier Konsultationen des `spec-writer`-Ablaufs sind gelaufen; keine wurde übersprungen.
- **Der Nenner der Einigkeitsregel stammt auf dem neuen Endpunkt aus derselben Leseoperation wie die
  Teilnehmerliste** (Auflage S8). Der Architekturentwurf sah dort zunächst eine eigene Zählung vor;
  gingen beide auseinander, rechnete die Regel über eine andere Nutzerzahl, als die Ansicht anzeigt,
  ohne dass ein Feld der Antwort widersprüchlich aussähe. Die übrigen drei Lesepfade zählen weiter
  über `_user_count`, weil sie keine Teilnehmerliste führen.
- **Der Schreibendpunkt bekommt neben dem Listeneintrag einen eigenen, pfadbenannten 401-Nachweis**
  (Auflage S1). Er ist der einzige Endpunkt, dem die Authentifizierung nicht an der Signatur
  anzusehen ist, und der Listeneintrag überlebt weder sein eigenes Vergessen noch eine spätere
  Verschiebung des Endpunkts.
- **Die Nachweise für „der Einzelentwurf bleibt unberührt" sind sieben, nicht vier.** Der
  strukturelle Wächter misst **Funktionsrümpfe statt Dateien**: `_to_photo_out` liegt im selben
  Modul und liest die Entscheidungen zwingend, eine Fundmenge auf Dateiebene wäre deshalb entweder
  dauerhaft rot oder ohne Aussage.
- **`variant="destructive"` und das Symbol `check` sind auf der neuen Seite unzulässig** und werden
  als Abwesenheit im gerenderten DOM geprüft. `check` ist im Produkt die Erfolgsmeldung, und die
  Kollisionsregel in `ui/button.tsx` untersagt `destructive` auf jeder Ansicht mit
  Bewertungs-Kennzeichen — diese Seite zeigt sie je Teilnehmer.
- **`tap-targets` bekommt die neue Seite hinzu** (die alte Vergleichsseite stand nie darin), und
  `grid-columns` bewusst nicht: Der akute Fehlermodus bei 360 px liegt bereits bei
  `no-horizontal-scroll`, ein zweiter Rasterspec ohne Rot-Nachweis wäre immer grün.

## Offene Fragen

Keine.

## Out of Scope

- Der Export selbst ([#263](https://github.com/TheRealKoller/photosort/issues/263)). Diese Spec legt
  fest, **was** exportiert wird, nicht wie.
- Das Auswerten der Unterschiede als Feedback ans Modell und jede Form von Diagnose — Story 8
  ([#432](https://github.com/TheRealKoller/photosort/issues/432)).
- Eine Historie oder ein Verlauf der gemeinsamen Entscheidungen. Festgehalten wird der jeweils
  geltende Stand, nicht sein Zustandekommen.
- Abstimmen, Zustimmen, Vetorecht, Benachrichtigungen oder ein Zustand „wartet auf den anderen".
- Ein Zustand „mein Entwurf ist fertig" je Nutzer.
- Mehr als zwei Nutzer.
