# 0584 - Events fassen zusammenhängende Erlebnisse zusammen und tragen nur zutreffende Ortsnamen

**Status:** Implemented ([PR #588](https://github.com/TheRealKoller/photosort/pull/588))
**Erstellt:** 2026-10-06
**Bezug:** [Issue #584](https://github.com/TheRealKoller/photosort/issues/584), ADR [0135](../decisions/0135-einzelner-ortsausreisser-trennt-nicht-und-unbestaetigter-sehenswuerdigkeitsname-entfaellt.md)

## Ziel

In der Kuratierungsansicht gliedern Events die Fotos eines Projekts. Im echten Bestand ist diese Gliederung an zwei Stellen unzuverlässig:

- **Falscher Name:** Projekt 7, 30.05.2022: Ein Event heißt „Tower of London", die Fotos entstanden in Schottland.
- **Unnötige Aufteilung:** Projekt 7, 01.06.2022: „Aviemore, Granish (18:04 Uhr)", „Avielochan (18:06 Uhr)" und „Aviemore, Granish (18:07–19:33 Uhr)" sind ein einziges Erlebnis.

Ein Name, der sich nicht über den Aufnahmeort bestätigen lässt, wird weggelassen statt falsch angezeigt (Produktentscheidung Daniel).

## User Story

Als Daniel, der die Familienfotos kuratiert, möchte ich, dass die Fotos eines zusammenhängenden Erlebnisses in einem Event liegen und dieses Event nur einen Namen trägt, der zum tatsächlichen Aufenthaltsort passt, damit ich mich in der Kuratierungsansicht ohne Rätselraten zurechtfinde.

## Akzeptanzkriterien

### Zutreffender Name

- [ ] `_landmark_name_is_plausible` ist nur wahr, wenn zum Namen eine Auskunftszeile mit mindestens einem Punkt vorliegt und ein Punkt einer gemessenen Zelle näher liegt als `LANDMARK_PLAUSIBILITY_RADIUS_METERS` (`<`). Falsch ist sie bei: Auskunft `None`, keiner gemessenen Zelle (mit leerer oder gefüllter Punktmenge), keiner Zeile zum Namen, leerer Punktmenge.
- [ ] Ein Event, dessen Gewinnername entfällt, gleicht einem Event, das nie einen Namenskandidaten hatte: Überschrift nach dem Ort (`place_name`), sonst `Position N (Zeitspanne)`. Kein anderer Name rückt nach.
- [ ] Ein Event, das nur übernommene Koordinaten trägt, verliert seinen Sehenswürdigkeitsnamen.
- [ ] Läuft der Worker ohne Sehenswürdigkeitsauszug oder bei Hash-Abweichung, behält kein Event einen Namen ohne Zeile; der Lauf endet mit `SUCCESS`, es wird keine Zeile geschrieben.
- [ ] `rebuild_run_grouping` behält Namen mit abgelegter bestätigender Zeile und verwirft Namen ohne Zeile.
- [ ] Manuelle Abnahme (Daniel, nach erneuter Analyse von Projekt 7): Am 30.05.2022 heißt kein Event „Tower of London".

### Keine unnötige Aufteilung

- [ ] `location_excursions` liefert genau die Foto-Ids einer Folge von weniger als `LOCATION_CHANGE_CONFIRMING_PHOTOS` Fotos mit **gemessener** Koordinate, die jeweils weiter als `EVENT_STEP_MAX_METERS` vom Bezug liegen, wobei das nächste gemessene Foto wieder innerhalb dieser Schwelle am Bezug liegt. Fotos ohne eigene Messung zwischen Bezugs- und Rückkehrfoto, deren übernommene Koordinate weiter als `EVENT_STEP_MAX_METERS` vom Bezug liegt, gehören zum Ausreißer. Gerechnet wird am Symbol (Modulattribut, monkeypatch wirkt); Zahlenwerte stehen in keiner Testaussage außer `>= 2`.
- [ ] Ein Ausreißer bleibt Mitglied des umgebenden Events, verschiebt weder Schritt noch Ausdehnung und speist weder Zelle noch Ortsname noch Plausibilitätsprüfung. A–X–A, zeitlich eng, ergibt ein Event mit genau einer Zelle (A).
- [ ] Ein Wechsel ohne Rückkehr trennt wie bisher, ebenso ein Wechsel mit mindestens `LOCATION_CHANGE_CONFIRMING_PHOTOS` gemessenen Fotos am neuen Ort, auch mit späterer Rückkehr.
- [ ] Fotos am selben Ort im Abstand weniger Minuten liegen im selben Event (Bestandstests der Signale bleiben grün).
- [ ] Grenzen aus `zeitluecke`/`dauer` bleiben unberührt.
- [ ] Am Persistierten ändert sich nichts; Fotos behalten ihre Koordinaten.
- [ ] `event_probe`: Block B nennt die Zahl neutralisierter Fotos, Block C3 die Zahl der Namen ohne Auskunftszeile — nur als Zahlen, ohne Event- oder Zeitbezug.
- [ ] Manuelle Abnahme (Daniel): Projekt 7, 01.06.2022, 18:04–19:33 ist ein einziges Event; Vorher/Nachher-Messung mit `event_probe --project-id 7` und `--riegel` gemäß „Nachprüfbarkeit".

### Erneute Analyse

- [ ] Ohne Migration und Backfill liefern ein neuer Lauf und `rebuild_run_grouping` über unveränderte Daten die neue Gliederung und die neuen Namen (Integrationstest am Worker).

## Datenmodell-Bezug

Keine Änderung. Keine Migration, keine neue Spalte; die Ausreißer-Eigenschaft wird nirgends persistiert. `landmark_place_lookups` bleibt dreiwertig (nie nachgeschlagen / ohne Fund / mit Fund).

## Architektur / Umsetzung

Entscheidung: ADR 0135; ändert ADR 0123 in Teilen ab (Punkt 2 Zustand 1, Punkt 3, Punkt 4 „keine Zelle → Name bleibt").

**Ursachen (im Code geprüft, an Projekt-7-Daten noch nicht gemessen).**
- Ein Namenswechsel ist seit ADR 0118 kein Trennsignal mehr. Bei 1–2 Minuten Abstand trennen nur `schritt`/`ausdehnung`: Ein Foto liegt weit neben den übrigen. Stufe 3 heilt das nicht, weil `MERGE_EXTENT_MAX_METERS` beide Kanten des Einzelfotos sperrt. Die abweichenden Ortsnamen sind Folge der Zerlegung, nicht Ursache.
- `_landmark_name_is_plausible` lässt einen Namen ungeprüft stehen, wenn eine Auskunftszeile fehlt (Auszug fehlt auf dem Volume oder Request-Pfad) oder das Event keine gemessene Zelle hat.

**Ansatz.**
1. **Ausreißer-Vorstufe** `events.py::location_excursions(ordered, *, confirming_photos=None) -> frozenset[int]`, rein, linear, Muster `motif_change_starts`. Ausreißer: Folge von weniger als `LOCATION_CHANGE_CONFIRMING_PHOTOS` (= 2, unkalibriert) Fotos mit gemessener Koordinate (`measured_position`), jedes weiter als `EVENT_STEP_MAX_METERS` vom Bezug, das nächste gemessene Foto wieder innerhalb der Schwelle am Bezug. Bezug ist die letzte gemessene Koordinate vor der Folge, die selbst kein Ausreißer ist. Fotos ohne gemessene Koordinate zählen nie mit; solche zwischen Bezugs- und Rückkehrfoto, deren übernommene Koordinate weiter als `EVENT_STEP_MAX_METERS` vom Bezug liegt, gehören zum Ausreißer.
2. In `explain_events` gehen Ausreißer an **einer** Stelle als Kandidat ohne Ort ein (`dataclasses.replace(..., location=None, gps_lat=None, gps_lon=None)`), vor Signaldurchlauf, Stufe 3 und `_built`. Signale, `merge_small_segments` und `default_signals()` bleiben unverändert; kein neues Trennsignal.
3. **Fail-closed** in `_landmark_name_is_plausible` (siehe Akzeptanzkriterien). Aufrufort `_built`, Ablage in `landmark_place_lookups` und Worker-Nachschlagepfad bleiben; eine fehlende Zeile wird beim nächsten Lauf mit Auszug nachgeschlagen.
4. **Erneute Analyse:** Gliederung und Namen entstehen in `worker.py` (`build_events`) und `rebuild_run_grouping` jedes Mal neu aus persistierten Werten; kein Cache, keine Migration.
5. **Messkommando** `event_probe.py` läuft über `explain_events` und rechnet das neue Verhalten mit; dazu die zwei Aggregate (Block B, C3). Kommentar „Vorgabe `{}` lässt jeden Namen stehen (fail-open)" wird angepasst.
6. **Doku im selben PR:** `docs/setup.md` (Abschnitt zum Sehenswürdigkeitsauszug) und `docs/architecture.md` (Plausibilitätsprüfung) von fail-open auf fail-closed; Docstring `worker.py::_landmark_points_by_name` ohne „fail-open"; `specs/architecture/0002-testkonzept.md` „Bekannte Lücken" ergänzen: `LOCATION_CHANGE_CONFIRMING_PHOTOS` unkalibriert, ein echter Abstecher mit nur einem Foto verliert seinen Ort; Erkennungsweg ist Daniels Abnahme.

**Nachprüfbarkeit Projekt 7.** Vor und nach dem Umbau `docker compose exec -T backend python -m photosort.event_probe --project-id 7` sowie `--riegel`. Erwartet: weniger Grenzen mit Ursache `schritt`/`ausdehnung`; weniger von `ausdehnung` gesperrte Einzelfoto-Segmente (Block F); Ausreißerzahl > 0; in C3 weniger benannte Events um die unbestätigten Namen. Die konkreten Tage prüft Daniel in der Kuratierungsansicht, weil das Messkommando keine Events je Tag ausgibt.

**Reihenfolge.** (a) `location_excursions` mit Tests, (b) Einbindung in `explain_events`, (c) fail-closed, (d) Aggregate im Messkommando, (e) Doku.

## Teststrategie

- **Unit, rein** (`test_events.py`): `location_excursions` direkt; Einbindung über `_build`/`explain_events` mit `assert_event_invariants`; alle fail-closed-Zweige direkt.
- **Unit** (`test_event_probe.py`): beide Aggregate und Formwächter; `_adjustable_constants_of_events` erfasst `LOCATION_CHANGE_CONFIRMING_PHOTOS`.
- **Integration** (`test_worker_place_names.py`, `test_worker_rebuild_run_grouping.py`): fehlender Auszug, Hash-Abweichung, Neuaufbau mit und ohne abgelegte Zeile, A–X–A durch den Worker.
- **Manuell:** die zwei Projekt-7-Fälle samt Vorher/Nachher-Messung (kein Korpus im Repository).

**Edge Cases (Pflicht).** Ausreißer als erstes Foto (kein Bezug → kein Ausreißer) bzw. letztes (keine Rückkehr → trennt); X–X' hintereinander gilt als Wechsel, mit Schwelle 3 per monkeypatch beide neutralisiert; A–X–Y–A mit verschiedenen fernen Orten ist kein Ausreißer; A–∅–X–∅–A neutralisiert X; GPS-loses Foto neben X mit von X übernommener Koordinate wird mit neutralisiert und bestätigt nicht; A–X–A–X2–A ergibt zwei Ausreißer, Bezug bleibt A; Rückkehr und Ausreißerabstand knapp inner-/außerhalb von `EVENT_STEP_MAX_METERS` (am Symbol mit `EPSILON_METERS`); Zeitlücke direkt nach dem Ausreißer trennt weiterhin, X ist ortloses Mitglied des ersten Events; Ausreißer mit passendem Fundort bestätigt den Namen nicht; `location_excursions` über bereits neutralisierte Kandidaten liefert ∅.

**Umzukehrende Bestandstests (umstellen, nicht löschen, Rot-Beleg festhalten).** In `test_events.py` die fail-open-Fälle in `TestTheLandmarkNameNeedsAPlausiblePlace` und Namenswahl-Tests, die ohne Auskunft einen Namen erwarten (auf gemessene Kandidaten plus bestätigende Auskunft umstellen); in `test_worker_place_names.py` die Fälle „fehlender Auszug/Hash-Abweichung/leerer Fundort behält Namen" und `test_the_two_extracts_fail_independently`; `test_worker_criterion_scoring.py::test_without_an_embedder_the_run_completes_without_canonical_names`; in `test_event_probe.py` `test_without_a_stored_auskunft_the_name_stays` und `test_the_three_states_of_the_auskunft_do_not_collapse`.

## UI/UX

Nicht relevant. Nur das Backend ändert sich; Komponenten, Layout, Zustände und Texte im Frontend bleiben. Die Überschriftenformen, die häufiger auftreten (nur Ort; `Position N (Zeitspanne)`), bildet `frontend/src/utils/timeOfDay.ts` (`eventPlaceName` → `formatEventHeading`) bereits; das Design-System bleibt unverändert.

## Security

Sicherheitsrelevant, kein Blocker; die Angriffsfläche wird kleiner. Kein neuer Endpunkt, Auth-Pfad, API-Feld, Cloud-Aufruf, Secret und keine neue Eingabe von außen. Fortschreibung in `specs/architecture/0003-securitykonzept.md`.

- **S1 – Plausibilität fail-closed.** Kein Zweig lässt einen Namen im Zweifel stehen, auch nicht in `rebuild_run_grouping` (reicht weiter `None` durch, schlägt nichts nach). Fehlt der Auszug, endet der Lauf mit `SUCCESS`, das Log trägt nur das feste Grund-Token, kein Event trägt einen Sehenswürdigkeitsnamen. Die Prüfung kann weiterhin nur wegnehmen.
- **S2 – Ausreißer verliert seinen Ort nur für die Bildung.** `photos.gps_lat`/`gps_lon` werden nicht geschrieben; die Ausreißer-Eigenschaft wird nirgends persistiert. Es gehen weniger Zellen in `place_lookups`/`events.place_lat` ein, nie mehr.
- **S3 – Weniger Steuerbarkeit über EXIF.** Ein einzelnes präpariertes Foto bewirkt weder Trennung noch Zelle noch Namen; `location_excursions` ist linear.
- **S4 – Probe-Aggregate nur als Anzahl über den Lauf.** Keine Zeile je Foto, Event oder Name; keine Position, Zeit, Koordinate, kein Name, keine Entfernung (die Ausgabe gelangt ins öffentliche Repository). Das Kommando bleibt rein lesend.
- **S5 – Nichts Neues im Log.**

## Entscheidungen

- Unbestätigter Sehenswürdigkeitsname entfällt (fail-closed) — Produktentscheidung Daniel im Refinement.
- Ausreißer werden nur über gemessene Koordinaten erkannt; übernommene Orte am Ausreißer werden mit neutralisiert (ADR 0135 §1).
- Ausreißer verliert auch seine Zelle, nicht nur seine Wirkung auf die Signale, damit das vereinte Event einen Ort behält.
- Projekt-7-Fälle werden manuell abgenommen; das Messkommando gibt per Securitykonzept keine Events je Tag aus.
- Alle vier Konsultationen (architect, ux-ui-designer, test-engineer, security-engineer) liefen; keine übersprungen.

## Offene Fragen

- Keine. Die Ursachen sind aus dem Code abgeleitet; vor der Umsetzung bestätigt ein `event_probe --project-id 7 --riegel` auf Daniels Instanz, dass beide Fälle in diese Zweige fallen.

## Out of Scope

- Kalibrierung von `EVENT_STEP_MAX_METERS`, `EVENT_EXTENT_MAX_METERS`, `MERGE_EXTENT_MAX_METERS`.
- Änderungen an Ortsnamen-Auflösung (GeoNames, Zellkörnung) und an der Frontend-Überschrift.
- Manuelles Umbenennen oder Zusammenlegen von Events.
