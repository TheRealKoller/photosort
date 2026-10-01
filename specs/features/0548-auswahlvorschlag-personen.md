# 0548 - Auswahlvorschlag berücksichtigt erkannte Personen

**Status:** Accepted
**Erstellt:** 2026-10-01
**Bezug:** [Issue #548](https://github.com/TheRealKoller/photosort/issues/548), ADR [`0129`](../decisions/0129-personen-als-abdeckungsziel-des-auswahlvorschlags-nach-der-phase-persons.md), Vorgänger [Spec 0292](./0292-personen-erkennen.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Story verschiebt einen Rechenschritt hinter eine Phase und hebt eine Zusage aus Spec 0292 auf, und Teststrategie und Security müssen beide Änderungen einzeln absichern.

## Ziel

PhotoSort erkennt Daniel und seine Frau auf den Fotos. Der automatische Auswahlvorschlag nutzt das bisher nicht. Er sorgt dafür, dass jedes Motiv, das in einem Event vorkommt, möglichst vertreten ist. Für Menschen gibt es dabei nur das Motiv „Menschen“, und das erfüllt jedes Bild mit Verwandten, Kindern oder Fremden genauso. Wer auf einer Reise fotografiert, ist selbst selten im Bild. Seine wenigen Bilder unterliegen im Vorschlag leicht den vielen Bildern der anderen, und im Album-Entwurf fehlen die beiden Nutzer dann in manchen Abschnitten.

Der Vorschlag soll eine der beiden Personen, die in einem Event vorkommt, dort genauso berücksichtigen wie ein vorkommendes Motiv. Der Vorschlag wird dadurch nicht größer, und reichen die Plätze nicht, gibt es keine Zusage.

## User Story

Als einer der beiden Nutzer möchte ich, dass der Auswahlvorschlag in jedem Event, in dem einer von uns vorkommt, möglichst auch ein Bild von dieser Person enthält, so wie heute von jedem vorkommenden Motiv, damit wir uns im Album-Entwurf in den Abschnitten der Reise selbst wiederfinden und nicht nur deren Orte und Motive, ohne dass der Vorschlag dadurch größer wird.

## Akzeptanzkriterien

**Wann eine Person in einem Event vorkommt**

- [ ] Eine festgelegte Person kommt in einem Event vor, wenn mindestens ein Bild des Events ihren Namen trägt, das für den Vorschlag in Frage kommt. In Frage kommen dieselben Bilder, an denen auch ein Motiv vorkommen kann.
- [ ] Es zählen genau die Namen, nach denen auch die Einschränkung der Ansicht auf eine Person filtert: erkannte und von Hand ergänzte. Ein von Hand entfernter Name zählt nicht.

**Abdeckung**

- [ ] Solange ein Event freie Plätze hat und dort noch eine Person oder ein Motiv unvertreten ist, geht der nächste Platz an ein Bild, das etwas davon trägt: den Namen einer unvertretenen Person oder ein unvertretenes Motiv. Ein Bild, das nichts Unvertretenes trägt, bekommt bis dahin keinen Platz. Die Regel ist dieselbe wie bei einem unvertretenen Motiv.
- [ ] Ein gewähltes Bild vertritt jede unvertretene Person und jedes unvertretene Motiv, die es trägt. Ein Bild mit beiden Namen vertritt beide Personen.
- [ ] Hat ein Event mindestens so viele Plätze, wie dort Motive und Personen zusammen vorkommen, ist jede dort vorkommende Person mit mindestens einem Bild vertreten.
- [ ] Die beiden Personen sind untereinander und mit jedem Motiv gleichrangig. Keine Person geht der anderen oder einem Motiv vor, und keine steht hinter ihnen zurück.
- [ ] Ist in einem Event noch eine Person oder ein Motiv unvertreten, geht der nächste Platz an das beste Bild unter allen Bildern, die etwas Unvertretenes tragen, gleich ob Person oder Motiv. Wie viel Unvertretenes ein Bild zugleich abdeckt, gibt ihm keinen Vorrang: Ein Bild mit unvertretener Person und unvertretenem Motiv vertritt beide, geht aber einem besseren Bild, das nur eines davon trägt, nicht vor.
- [ ] Hat ein Event weniger Plätze, als dort Motive und Personen zusammen vorkommen, entscheidet die Bildqualität, welche davon vertreten sind.
- [ ] Unter den Bildern einer Person wird dasselbe Bild gewählt, das die Regel innerhalb eines Motivs wählen würde: das beste, mit derselben Abwertung für Bilder, zu denen schon ein ähnliches gewählt ist.

**Der Umfang bleibt unberührt**

- [ ] Personen vergrößern den Vorschlag nie. Die Zahl der Bilder im ganzen Vorschlag und je Event ist dieselbe wie bei demselben Projekt ohne festgelegte Personen.
- [ ] Es gibt keine Zusage: Reichen die Plätze eines Events nicht, darf eine dort vorkommende Person unvertreten bleiben.
- [ ] In einem Event, in dem keine Person vorkommt, ist der Vorschlag derselbe wie bei demselben Projekt ohne festgelegte Personen. Dasselbe gilt für das ganze Projekt, solange keine Person festgelegt ist.

**Zeitpunkt der Wirkung**

- [ ] Nach einem Klassifizierungslauf berücksichtigt der Vorschlag die Namen, die nach diesem Lauf gelten, einschließlich der Erkennungen dieses Laufs. Das gilt auch beim ersten Lauf eines Projekts und auch dann, wenn die Personenerkennung in diesem Lauf entfällt.
- [ ] Eine Namenskorrektur, eine neu festgelegte oder eine entfernte Person verändert den bestehenden Vorschlag nicht sofort. Die Änderung wirkt spätestens mit dem nächsten Klassifizierungslauf.
- [ ] Nach dem Entfernen einer Person hat sie spätestens ab dem nächsten Klassifizierungslauf keinerlei Einfluss mehr auf den Vorschlag.

**Was unverändert weiter gilt**

- [ ] Gleicher Bildbestand, gleiche Einstellungen und gleiche Namen ergeben denselben Vorschlag.
- [ ] Die Einschränkung der Ansicht auf eine Person verändert den Vorschlag nicht.
- [ ] Motive, Motivstärken und Statistik sind nach einem Lauf mit erkannten Personen dieselben wie ohne Personen.
- [ ] Ein Lauf mit Cloud-Einwilligung schickt mit festgelegten Personen dieselben Anfragen an Dritte wie ohne.
- [ ] Im Album-Entwurf aufgenommene und gestrichene Bilder bleiben erhalten, wenn sich der Vorschlag wegen der Personen ändert.

## Datenmodell-Bezug

Keine neue Tabelle, keine Spalte, keine Migration. Gelesen wird die wirksame Personenzuordnung aus `photo_person_detections` und `photo_person_corrections` (Spec 0292); geschrieben wird wie bisher nur `photo_rankings.selection_position`. `docs/architecture.md` ist nachgezogen (Kriterien-Lauf, Phase `persons`, `selection_position`, wirksame Zuordnung).

## Architektur / Umsetzung

ADR [`0129`](../decisions/0129-personen-als-abdeckungsziel-des-auswahlvorschlags-nach-der-phase-persons.md) löst ADR 0097 in zwei Punkten teilweise ab: Punkt 4, also welche Bilder für einen Platz in Frage kommen, und Punkt 7, also wo im Kriterien-Lauf gerechnet wird. Es entstehen keine Migration, kein neues Modell, kein Endpunkt und keine Frontend-Änderung.

### Ansatz

Personen werden ein zweites Abdeckungsziel neben den Motiven. Sie stecken in derselben Greedy-Vergabe (`selection.py::_assign_event`) und laufen nicht über eine eigene Regel.

- **Eingeschränkte Menge:** Solange ein vorkommendes Motiv **oder** eine vorkommende Person unvertreten ist, kommen nur Bilder in Frage, die etwas davon tragen.
- **Wahl:** Unter diesen Bildern gewinnt der höchste Wert, `rank_score · 0,5^Σ ähnlichkeit`. Bei Gleichstand gewinnt die kleinere `photo_id`.
- **Wirkung der Wahl:** Das gewählte Bild vertritt alles Unvertretene, das es trägt. Die Zahl der dabei abgedeckten Ziele geht nie in den Wert ein.
- **Unberührt:** Die Kontingente (`_quotas`) bleiben unverändert. Das Ähnlichkeitsmaß (`_similarity`) und die Reihenfolge der Alternativen (`order_alternatives`) lesen weiterhin nur Motive.

### Betroffene Komponenten

- `backend/src/photosort/selection.py`
  - `SelectionCandidate` bekommt das Pflichtfeld `person_ids: frozenset[int]`, ohne Vorgabewert. Ein vergessener Aufrufer scheitert dann bei `mypy`, statt still „keine Personen“ zu liefern. Das Feld enthält nur Ids, nie einen Namen.
  - `_assign_event` führt neben `present`/`represented` (Motive) zwei eigene Mengen für Personen, `present_persons`/`represented_persons`.
    - Ein Kandidat kommt in Frage, wenn `unrepresented_motifs` und `unrepresented_persons` beide leer sind oder wenn er etwas aus einer der beiden Mengen trägt.
    - Nach der Wahl werden beide `represented`-Mengen fortgeschrieben.
    - Motivschlüssel und Personen-Ids kommen **nicht** in einen gemeinsamen Schlüsselraum, damit sie nicht kollidieren können.
  - Die Invariante „`best is None` ist unerreichbar“ gilt weiter. `present_persons` entsteht aus denselben Kandidaten, also hat jede vorkommende Person ein Trägerbild.
  - Der Modul-Docstring und der Docstring von `_assign_event` wechseln von „motivgeführt“ auf „motiv- und personengeführt“.
- `backend/src/photosort/worker.py`
  - `_apply_run_selection`: Nach `load_effective_strengths(session, eligible_ids)` folgt `persons.load_effective_persons(session, eligible_ids)` mit derselben Id-Liste. Gefüllt wird `person_ids=frozenset(a.person_id for a in persons_by_photo_id.get(photo_id, []))`.
  - `_build_grouping_and_rankings`: Der abschließende Aufruf `await _apply_run_selection(...)` entfällt. Der `flush` davor bleibt, weil die Rangzeilen für den nachfolgenden Aufrufer in der Datenbank stehen müssen.
  - `rebuild_run_grouping`: ruft nach `_build_grouping_and_rankings` ausdrücklich `_apply_run_selection(session, run, project_id)` auf.
  - `run_criterion_scoring`: ruft nach `_recognize_persons(...)` und vor `run.status = SUCCESS` `await _apply_run_selection(session, run, project.id)` auf. Vorschlag und Erfolgsvermerk landen so im selben Commit.
  - Der Kommentar über `_recognize_persons` („geht in … keinen Auswahlvorschlag ein“) wird korrigiert.
- `backend/src/photosort/persons.py`: keine Änderung. `load_effective_persons` bzw. `effective_person_assignments` wird wiederverwendet; das ist dieselbe wirksame Zuordnung, nach der der Personenfilter in `api/photos.py` filtert, also erkannt oder von Hand ergänzt, und von Hand entfernt zählt nicht.
- `backend/src/photosort/demo_state.py`: keine Änderung. `_seed_demo_persons` läuft schon vor `rebuild_run_selection`, also berücksichtigt der Demo-Vorschlag die Demo-Personen automatisch.

### Datenfluss

```
run_criterion_scoring
  … criteria → landmark → Motiv-Kopfzeilen
  → RANKING: _build_grouping_and_rankings (Events, Rangzeilen; KEIN Vorschlag mehr)
  → PERSONS: _recognize_persons (schreibt photo_person_detections je Block)
  → _apply_run_selection
       Rangzeilen des Laufs (rank_score NOT NULL) − excluded_document  = auswahlfähig
       + load_effective_strengths(auswahlfähig)   → motif_strengths
       + load_effective_persons(auswahlfähig)     → person_ids
       → selection.select_album_draft → photo_rankings.selection_position
  → SUCCESS (ein Commit mit dem Vorschlag)
```

**Pipeline-Reihenfolge:**

- Die Phasenfolge bleibt `… → ranking → persons`, und es gibt keinen neuen `ClassificationPhase`-Wert.
- Der Vorschlag rechnet unter der zuletzt gesetzten Phase: `persons`, oder `ranking`, wenn die Personenphase mangels Referenz oder Adapter entfällt.
- Bis zum Erfolgsvermerk hat der laufende Lauf keinen Vorschlag. Das ist unsichtbar, weil alle Lesepfade den letzten **erfolgreichen** Lauf lesen.
- Damit berücksichtigt schon der erste Lauf eines Projekts die Namen, die dieser Lauf ergeben hat.

### Auslöser

Es bleibt bei den drei Auslösern, alle über `_apply_run_selection`:

1. der Kriterien-Lauf,
2. `rebuild_run_grouping` (Versatz),
3. `rebuild_run_selection` (Richtwert).

`api/persons.py` (anlegen, Referenz, Korrektur `PUT /photos/{id}/persons/{person_id}`, `DELETE /persons/{id}`) löst **keinen** Neuaufbau aus. Personen werden bei jeder Berechnung **live** gelesen, wie die Motivstärken; einen Schnappschuss je Lauf gibt es nicht. Daraus folgt:

- Eine Korrektur wirkt nicht sofort, sondern beim nächsten Auslöser, spätestens mit dem nächsten Klassifizierungslauf.
- `delete_person` löscht Erkennungen und Korrekturen in einer Transaktion. Danach liefert `load_effective_persons` für die Person nichts mehr, sie hat also keinerlei Einfluss mehr.

### Determinismus und Gleichheit ohne Personen

- **Struktureller Determinismus wie bisher:** Kandidaten werden nach `photo_id` sortiert, Events nach `position` durchlaufen, Gleichstand entscheidet die kleinere `photo_id`. Personenmengen dienen nur für Schnittmengen- und Leerheitsprüfungen. Kein Schritt iteriert über sie, um eine Reihenfolge zu bilden.
- **Ohne Person in einem Event** sind `present_persons` und `unrepresented_persons` leer. Die eingeschränkte Menge ist dann genau die bisherige, also ist der Vorschlag dort identisch. Ohne festgelegte Person gilt das für das ganze Projekt.
- **Platzzahl:** `_quotas` liest keine Personen. Die Zahl der Bilder je Event und insgesamt ist deshalb unverändert, und eine Abdeckung wird nicht zugesagt.

### Was unverändert bleibt

- **Motive, Statistik, Cloud:** Motivstärken und Kopfzeilen, Statistik (`api/stats.py` liest kein `selection_position`) und Cloud-Anfragen bleiben gleich. Personen werden ausschließlich lesend in `_apply_run_selection` verwendet, also nach allen Cloud-Phasen und ohne Prompt-Änderung.
- **Import-Graph (ADR 0126 Punkt 1):** `selection.py` importiert kein Personenmodul, und `worker.py` importiert `persons` schon heute. Der Wächter `test_persons_import_graph.py` bleibt unverändert grün.
- **Album-Entwurf:** bleibt strukturell erhalten, ohne neuen Code. Der Entwurf ist zur Lesezeit Vorschlag ∪ Aufgenommen ∖ Gestrichen (ADR 0098 Punkt 1, `album_selection.py::selection_state`), und eigene Entscheidungen wirken nur im Zweig ohne Entscheidung.
- **Personenfilter der Ansicht:** liest nur und schreibt nie `selection_position`.

### Umsetzungsreihenfolge

1. `selection.py`: Feld `person_ids` und die erweiterte eingeschränkte Menge in `_assign_event`. Die reinen Tests in `tests/test_selection.py` passen `_candidate(...)` an; das ist die einzige Konstruktionsstelle.
2. `worker.py::_apply_run_selection`: Personen laden und durchreichen.
3. `worker.py`: Aufruf aus `_build_grouping_and_rankings` herausziehen, in `rebuild_run_grouping` und nach `_recognize_persons` in `run_criterion_scoring` einsetzen.
4. Kommentare und Docstrings nachziehen: `selection.py`, den Kommentar über `_recognize_persons`, den Docstring von `TestTheDraftIsPartOfTheRankingPhase` in `tests/test_worker_selection.py`. Der Phasen-Assert dort bleibt gültig.

### Bestehende Tests, deren Zusage fällt

Hinweis für die Teststrategie:

- `tests/test_worker_persons.py::test_a_recognised_person_is_no_motif` vergleicht im Zwilling mit und ohne Personen auch `PhotoRanking.selection_position`. Diese Zusage aus Spec 0292 hebt die Story auf. Der Vergleich wird auf Motivstärken, `rank_score`/`rank_position` und Statistik reduziert.
- `tests/test_worker_persons.py` (Reihenfolge `ranking` → `persons`) bleibt gültig. Neu nachzuweisen ist: Der Vorschlag entsteht nach `persons`, und schon der erste Lauf berücksichtigt dessen Erkennungen.

## UI/UX

Nicht relevant: Keine Ansicht, keine Eingabe, kein API-Feld und kein Schema ändern sich. Der Album-Entwurf zeigt unverändert den Vorschlag; welche Bilder darin stehen, entscheidet das Backend. Eine Anzeige, warum ein Bild im Vorschlag steht, ist Out of Scope.

## Security

Einstufung: **sicherheitsrelevant, kein Blocker.** Die wirksame Personenzuordnung (Spec 0292, ADR 0126) bekommt neben dem Personenfilter einen zweiten Verbraucher. Der Vorschlag hängt danach von Personen ab, und damit fällt die Zusage aus Spec 0292, er sei mit und ohne Personen derselbe. Es gibt kein Secret, keinen Endpunkt, keinen neuen Empfänger und keine Änderung an Auth oder an der Sichtbarkeit zwischen den beiden Nutzern. Die projektweite Fassung steht im Sicherheitskonzept, Abschnitt „Personen auf Fotos erkennen“, Fortschreibung Spec 0548.

- **S1 – Nur die Id, nur für diesen Lauf.** `_apply_run_selection` übernimmt aus `persons.load_effective_persons` ausschließlich `person_id`, nie `Person.name`, und zwar nur für die `eligible_ids` dieses Laufs. Damit erbt das Laden die Projektbindung der Rangzeilen (`criterion_scoring_run_id == run.id`, `Photo.project_id`). `selection.py` bleibt ohne Logger und importiert nur die Standardbibliothek, also weder ein Personen- noch ein Netzwerkmodul. Der Wächter `test_persons_import_graph.py` bleibt unverändert und muss nicht erweitert werden: Personendaten erreichen `selection.py` nur zur Laufzeit über `worker.py`, und diese Verbindungsstelle deckt der Nutzlast-Nachweis aus S3 ab.
- **S2 – Kein Paar (Foto, Person) in einem Log oder Fehlertext.** Weder `selection.py` noch `_apply_run_selection` schreibt eine Logzeile mit Personen-Ids. Keine Exception-Meldung formatiert einen `SelectionCandidate` (dessen `repr` enthält `person_ids`) oder eine Personenmenge. Grund: `str(exc)` landet in `criterion_scoring_runs.error_message`, und sowohl Log als auch Laufmeldung überleben die Löschung der Person. Nachweis per Review, kein Quelltexttest. `test_the_log_carries_no_name_and_no_embedding_value` bleibt bestehen.
- **S3 – Dieselben Anfragen an Dritte.** Der Vorschlag entsteht nach allen Cloud-Phasen, und kein Cloud-Kandidatenpfad liest `selection_position`. Heute lesen ihn nur `api/photos.py` und `demo_state.py`. Das AK „dieselben Anfragen an Dritte“ belegt der bestehende Test `test_worker_persons.py::test_the_cloud_sees_the_same_requests_with_and_without_persons`. Er läuft nach der Umstellung durch den ganzen Kriterien-Lauf samt Vorschlag nach `persons` und deckt damit die neue Stelle ab. Er bleibt **unverändert** und wird nicht verkürzt wie der Motiv-Zwilling. Ein neuer Test ist nicht nötig. Liest eine künftige Cloud-Auswahl den Vorschlag, entscheiden Personen mit, welche Bilder an Dritte gehen. Das verlangt eine neue Security-Konsultation, denn der Zwilling deckt nur den eigenen Lauf ab, nicht eine Kopplung über mehrere Läufe.
- **S4 – Eine entfernte Person wirkt nicht mehr.** Personen werden bei jeder Berechnung frisch gelesen; es gibt keinen Schnappschuss und keinen Zwischenspeicher von Personen-Ids über die Berechnung hinaus. `delete_person` entfernt Erkennungen und Korrekturen in einer Transaktion, `load_effective_persons` verbindet sie mit `Person`, und danach trägt keine Zuordnung mehr die Person. Nachweis: Nach dem Entfernen einer Person und einem Neuaufbau ist der Vorschlag gleich dem eines Projekts, in dem sie nie festgelegt war. **Nicht erreicht** werden bereits geschriebene `selection_position`. Beim letzten erfolgreichen Lauf bleiben sie bis zum nächsten Auslöser stehen, also bis zum nächsten erfolgreichen Kriterien-Lauf oder einer Richtwert- oder Versatzänderung; ein gescheiterter Lauf rechnet nicht neu. Bei älteren Läufen bleiben sie bis zur Projektlöschung. Sie tragen weder Id noch Name, und ältere Läufe stehen auf keinem Lesepfad.

Geprüft, ohne Befund:
- **Indirekte Offenlegung:** `proposed` sehen nur die beiden Nutzer, und die sehen die Zuordnung über den Personenfilter ohnehin direkt. Personen sind global und für beide gleich.
- **Ausgabekanäle:** Es gibt keinen Export und keinen weiteren Ausgabekanal.
- **Richtwert- und Versatz-Endpunkte:** Sie lesen jetzt auch Personen, behalten aber dieselbe Auth und liefern weiterhin nur dieselbe Markierung.

## Teststrategie

Der Schwerpunkt liegt auf DB-freien Unit-Tests (`tests/test_selection.py`). Die Integrationstests prüfen, woher die Namen kommen, wann sie wirken und wer den Neuaufbau auslöst. Es gibt keine E2E-, Frontend- oder Migrationsfälle. Die Muster stehen im Testkonzept, Sektionen zu ADR 0097 und ADR 0129.

**Unit, `select_album_draft`, neue Klasse `TestThePersonGuidedAssignment`.** `_candidate` bekommt `persons: frozenset[int] = frozenset()`. `assert_selection_invariants` bekommt (e): Hat ein Event mindestens so viele Plätze, wie dort Motive und Personen vorkommen, ist jedes davon vertreten.
- Eine Person in einem Event ohne vorkommendes Motiv: Ihr einziger Träger mit der niedrigsten Qualität bekommt Platz 2.
- Die Person ist schon vertreten, ein Motiv noch offen: Der Platz geht an den Motivträger und nicht an das bessere Bild ohne Unvertretenes. Der Fall trennt „nur wenn beide Mengen leer sind, ist jedes Bild wählbar“ von „sobald eine Menge leer ist“.
- Ein Bild mit beiden Namen vertritt beide. Ein Bild mit Person und Motiv vertritt beide (drei Ziele, zwei Plätze).
- Kein Zählbonus, in beiden Richtungen: Ein besseres Bild mit nur der Person schlägt ein schlechteres mit Person und Motiv, und ein besseres Bild mit nur dem Motiv schlägt ein schlechteres mit Person und Motiv.
- Weniger Plätze als Ziele: Die Qualität entscheidet, gegenläufig zur `photo_id` gebaut. Eine Person bleibt unvertreten, die Platzzahl bleibt gleich.
- Abwertung: Unter den Trägern einer Person fällt der zeitnahe Träger eines geteilten Motivs zurück. Ein geteilter Name allein wertet nicht ab.
- Gleichrang: Werden die beiden Personen-Ids vertauscht, ist die Abbildung identisch. Dasselbe gilt für einen Tausch Motiv ↔ Person, wenn alle Aufnahmen weiter als `SIMILARITY_TIME_WINDOW` auseinanderliegen.
- Umfang: Zwilling mit und ohne `person_ids` über eine `target`-Matrix ergibt dieselbe Platzzahl je Event. Ein Event ohne Person ist im Zwilling platzgleich, während die Person im Nachbar-Event dort nachweislich etwas ändert.
- Determinismus: `TestTheResultIsDeterministic._events()` bekommt Personen, darunter ein Bild mit beiden Namen und einen Gleichstand.

**Integration, `tests/test_worker_selection.py`, über `rebuild_run_selection`.**
- Wirksame Namen, parametrisiert: Ein erkannter Name zählt, ein von Hand ergänzter zählt, ein von Hand entfernter (Erkennung mit `applies=false`) zählt nicht.
- Eine Person, die nur auf einem ausgeschlossenen Dokument oder auf einem Foto ohne `rank_score` steht, kommt nicht vor.
- Gelöschte Person (`delete_person`): Nach dem Neuaufbau ist der Vorschlag gleich dem Zwilling ohne Person.
- Beide Neuaufbauten lesen live, parametrisiert über `rebuild_run_selection` und `rebuild_run_grouping`: Eine nach dem Lauf eingefügte Erkennung wirkt.

**Integration, `tests/test_worker_persons.py`, voller Lauf mit `FakeFaceAnalyzer` und `selection_target=1`.**
- Erster Lauf eines Projekts: Der rangschwächere Träger von Anna steht im Vorschlag. Gegenprobe ohne Erkennung: Er steht nicht darin. Dieser Fall wird rot, wenn der Vorschlag noch vor der Phase `persons` gerechnet wird.
- Die Phase entfällt (Lagen `nur-fremdes-modell` und `builder-scheitert`, jeweils mit alter Erkennung): Es entsteht trotzdem ein Vorschlag, und er berücksichtigt die stehende Erkennung.

**API, `tests/test_api_persons.py` und `tests/test_api_photos.py`.** Lage: ein veralteter Vorschlag mit einem von Hand gesetzten Platz, den ein Neuaufbau ändern würde.
- `PUT /photos/{id}/persons/{person_id}`, `POST /persons`, `POST /persons/{id}/references`, `DELETE /persons/{id}` und `GET /photos` mit Personen-Einschränkung lassen `selection_position` unverändert. Ein anschließendes `rebuild_run_selection` ändert ihn; beides steht als Paar in einem Fall.

**Angepasst:** `test_worker_persons.py::test_a_recognised_person_is_no_motif` vergleicht ohne `selection_position`, weil die Zusage aus Spec 0292 aufgehoben ist. Motivstärken, `rank_score`/`rank_position` und Statistik vergleicht der Fall weiter. `test_worker_selection.py::TestTheDraftIsPartOfTheRankingPhase` wird umbenannt in `TestTheDraftHasNoPhaseOfItsOwn`; Docstrings und Moduldocstring ziehen nach, die Assertions bleiben.

**Unverändert grün:**
- alle bestehenden Fälle in `test_selection.py` (Gleichheit ohne Personen);
- `test_worker_persons.py::test_the_cloud_sees_the_same_requests_with_and_without_persons`, `::test_the_phase_runs_after_ranking_and_before_success`, `::test_the_phase_does_not_run_and_leaves_old_detections`;
- `test_persons_import_graph.py`;
- `test_models.py::test_exactly_the_one_known_module_writes_selection_position`;
- `test_api_photos.py::TestTheDraft::test_only_untouched_places_follow_the_new_run`, der die Album-Entwurf-Entscheidungen unabhängig von der Ursache der Änderung prüft;
- `test_worker_selection.py::TestTheDraftIsPartOfTheRankingPhase::test_rebuilding_the_grouping_also_produces_the_draft`;
- `test_worker_rebuild_run_grouping.py`, `test_api_feedback_weights.py`, die Vorschlagsfälle in `test_demo_state.py`.

## Entscheidungen

- `architect` konsultiert (Schritt 1): Personen als zweites Abdeckungsziel in `_assign_event`, Vorschlag nach der Phase `persons`, Personen live gelesen; festgehalten in ADR 0129, ADR 0097 Kopfzeile ergänzt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story hat keinen `## Design`-Abschnitt und keine sichtbare Oberflächenänderung; sie ändert nur, welche Bilder das Backend als Vorschlag markiert, ohne neues Feld und ohne neue Anzeige.
- `test-engineer` konsultiert (Schritt 3): zwei Akzeptanzkriterien auf Prüfbarkeit geschärft, ohne fachliche Änderung (Abdeckung Punkt 1: der nächste Platz geht an ein Bild, das etwas Unvertretenes trägt, Person oder Motiv; Zeitpunkt Punkt 1: gilt auch, wenn die Personenerkennung in diesem Lauf entfällt); Testkonzept 0002 um eine Sektion ergänzt.
- `security-engineer` konsultiert (Schritt 3): sicherheitsrelevant, kein Blocker; Sicherheitskonzept 0003 im Personenabschnitt fortgeschrieben.
- „Nächster Klassifizierungslauf“ meint den nächsten **erfolgreichen** Lauf: Ein gescheiterter Lauf schreibt keinen Vorschlag, und alle Lesepfade lesen den letzten erfolgreichen Lauf.
- Eine Richtwert- oder Versatzänderung rechnet den Vorschlag neu und übernimmt dabei zwischenzeitliche Namenskorrekturen; das deckt das „spätestens“ der Zeitpunkt-Kriterien ab.
- Die Zusage aus Spec 0292, der Auswahlvorschlag sei mit und ohne Personen derselbe, fällt mit dieser Story.

## Offene Fragen

Keine.

## Out of Scope

- Zusätzliche Plätze oder ein Vorrang für Personen.
- Eine Anzeige, warum ein Bild im Vorschlag steht.
- Personen als Merkmal der Ähnlichkeit zwischen Bildern.
- Mehr als zwei Personen.
