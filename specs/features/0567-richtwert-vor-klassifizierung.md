# 0567 - Richtwert vor der Klassifizierung einstellbar, sofort wirksam und standardmäßig 150

**Status:** Implemented ([PR #572](https://github.com/TheRealKoller/photosort/pull/572))
**Erstellt:** 2026-10-04
**Bezug:** [#567](https://github.com/TheRealKoller/photosort/issues/567), ADR [0131](../decisions/0131-richtwert-vorbelegung-fest-150-statt-zehntel-der-bilderzahl.md)

Umfang über dem Richtwert, weil die Akzeptanzkriterien je Kriterium die Testebene tragen und vier Konsultationen vollständig übernommen sind.

## Ziel

Der Richtwert bestimmt, wie groß der Auswahlvorschlag eines Projekts wird. Heute wirkt eine Erhöhung auf der Kuratierungsseite erst nach einem erneuten Klassifizierungslauf, obwohl sofortige Wirkung zugesagt ist; der Richtwert ist erst nach der Klassifizierung einstellbar; und ohne eigene Angabe gilt ein Zehntel der Bilderzahl statt eines festen Standards von 150.

## User Story

Als kuratierender Nutzer möchte ich die Zielgröße des Auswahlvorschlags schon vor der Klassifizierung festlegen und später bei der Kuratierung mit sofortiger Wirkung nachjustieren können, wobei ohne eigene Angabe ein fester Standard von 150 Bildern gilt — damit der Vorschlag beim ersten Ansehen schon die Größe hat, die ich für ein Album will, und ich die Wirkung jeder Änderung sofort sehe.

## Akzeptanzkriterien

Testebene in Klammern.

**Standard**

- [ ] Ohne eigene Angabe (`selection_target = NULL`) ist `effective_target(None)` = 150, unabhängig von der Bilderzahl. Geprüft für 0, 1, 149, 150, 151 und 10 000 Projektfotos. Dabei steht 150 genau einmal als Zahl im Test (am Konstantenwert `DEFAULT_TARGET`), alle anderen Fälle importieren die Konstante. (pytest Unit `test_selection.py`)
- [ ] Der Standard wächst nicht mit: Ein Projekt ohne eigene Angabe bekommt durch einen weiteren Scan Fotos hinzu, und `GET /projects/{id}` liefert vorher und nachher `effective_selection_target == 150` und `selection_target is None`. (pytest API)
- [ ] Wo der Richtwert einstellbar ist (Klassifizierung und Kuratierung), gilt: Ohne eigene Angabe ist das Feld leer, und der Hinweis „Standard: 150 Bilder“ zeigt `effective_selection_target` vom Server. Mit eigener Angabe zeigt das Feld die Zahl, dazu „eigene Angabe“ und die Aktion „Auf Standard zurücksetzen“. Die Fixture verwendet einen Serverwert ≠ 150, damit belegt ist, dass die Zahl aus der Antwort stammt und nicht im Frontend fest verdrahtet ist. Der Text „ein Zehntel“ kommt nirgends mehr vor. (vitest `SelectionTargetField`)
- [ ] „Auf Standard zurücksetzen“ sendet `PUT` mit `null`. Danach gilt `selection_target is None` und `effective_selection_target == 150`, und der Vorschlag wird nach 150 neu berechnet. (vitest: Request-Body `null`; pytest API: Persistenz und Neuberechnung)
- [ ] 150 ist ein Ziel, keine Obergrenze: Bei m < 150 auswahlfähigen Fotos und genug Events gilt |Vorschlag| = m. Der Album-Entwurf zeigt dann eine neutrale Zeile (`text-muted`, kein `role="alert"`/`Alert`). Bei |Vorschlag| ≥ Richtwert fehlt die Zeile. (pytest Unit über die bestehende Matrix `|Ergebnis| == max(T, m)`; vitest `utils/albumDraft.ts` als reine Funktion plus ein Rendertest)
- [ ] Mindestabdeckung: Bei T ≤ Zahl der Events/Personen bekommt jedes Event bzw. jede festgelegte Person einen Platz, und der Vorschlag wird größer als T. Diese Fälle bestehen weiter, nur ohne `photo_count`-Argument. Der Hinweis „kleinerer Vorschlag“ erscheint dann nicht. (pytest Unit, bestehende Invarianten-Helfer; vitest)

**Angabe vor der Klassifizierung**

- [ ] `ClassificationSection` (Kriterien-Schritt) rendert `SelectionTargetField` über dem Auslöser, auch ohne bisherigen Lauf und ohne dass die Kuratierungsseite besucht wurde. (vitest)
- [ ] `PUT` ohne erfolgreichen Lauf → 200. Der Wert wird gespeichert, und keine `photo_rankings`-Zeile ändert sich. (pytest API)
- [ ] Ist vor dem ersten Lauf T gesetzt, hat der Vorschlag des ersten erfolgreichen Laufs die Größe nach T. Der Test wählt T ≠ 150 und T > Eventzahl, sonst ist der Fall vom Standard bzw. von der Mindestabdeckung nicht unterscheidbar. (pytest Worker-Integration)
- [ ] Ein zweiter Lauf ohne Änderung verwendet weiter dasselbe T. Nach dem Entfernen (`null`) verwendet der nächste Lauf 150. (pytest Worker-Integration)
- [ ] Die Kuratierungsseite nutzt dieselbe Komponente `SelectionTargetField`, eine zweite Kopie gibt es nicht. Der bestehende Kuratierungstest läuft unverändert grün. (vitest)
- [ ] Der Richtwert gilt für das Projekt: Nutzer A setzt T, Nutzer B liest per `GET /projects/{id}` dasselbe `selection_target`/`effective_selection_target`, und die Vorschlagsgröße in B's Album-Entwurf richtet sich nach T. (pytest API mit zwei authentifizierten Clients)
- [ ] Ist der *neueste* Kriterien-Lauf `running`, antwortet `PUT` mit 409. Die Meldung enthält „Klassifizierung“, der gespeicherte Wert bleibt unverändert, und es gibt keine Neuberechnung. Ist der Lauf beendet (`succeeded` **und** `failed`), antwortet `PUT` mit 200. (pytest API)
- [ ] Oberfläche bei laufendem Lauf: Das Feld ist `disabled`, und der Grund steht per `aria-describedby` am Feld. Eine vorher getippte, nicht gespeicherte Eingabe bleibt beim Wechsel auf `running` und zurück stehen. Wechselt die Projektantwort auf einen nicht laufenden Status, ist das Feld ohne Neuladen wieder bedienbar (rerender mit neuer Query-Antwort). (vitest)

**Sofortige Wirkung (Fehler)**

- [ ] Nach einem erfolgreichen Lauf wird T per `PUT` erhöht und danach gesenkt, ohne neuen Lauf. Die Zahl der vorgeschlagenen Fotos folgt jeweils `max(T, Mindestabdeckung)` bis zur Kandidatenzahl. **Vorbedingungen werden im Test selbst geprüft:** Eventzahl < T_alt < T_neu ≤ Kandidatenzahl, und die Vorschlagsgröße vorher ist ≠ der Größe nachher. Ein Aufbau mit T ≤ Eventzahl ändert nichts und belegt den Fehler deshalb nicht. Der Test wird vor jeder Backend-Änderung geschrieben und zuerst rot oder grün dokumentiert. (pytest API)
- [ ] Im selben Test zeigen `GET` Kuratierungsliste, `GET /projects/{id}/album-draft` (beide Nutzer) und `GET` Endauswahl den neuen Vorschlagsanteil. (pytest API)
- [ ] `useSetSelectionTargetMutation` invalidiert bei Erfolg `['project', id]` und den Präfix `['photos', id]`. Ausdrücklich geprüft werden Album-Entwurf-Key, Kandidatenvorrat-Key und Endauswahl-Key `['photos', id, SELECTION_QUERY_SEGMENT]`. (vitest Hook-Test)
- [ ] Die genannte Zahl entspricht der Rechengrundlage: Nach `PUT` (bzw. nach einem Lauf) ist `effective_selection_target` gleich dem T, mit dem `_apply_run_selection` gerechnet hat. Geprüft wird das über die Vorschlagsgröße bei reichlich Kandidaten und T > Eventzahl. (pytest API)
- [ ] Speichern scheitert (409, 422, 500): Ein Alert erscheint, und der Feldinhalt bleibt die Eingabe des Nutzers. Der bestehende Test bleibt erhalten und zieht in den Test der neuen Komponente um. (vitest)

**Wirkung auf Album-Entwürfe und Endauswahl**

- [ ] Für **beide** Nutzer, mit unterschiedlichen Fotos je Nutzer: Ein Foto mit `ALBUM_WORTHY` außerhalb des neuen Vorschlags bleibt im Entwurf. Ein Foto mit `REJECTED` innerhalb des neuen Vorschlags bleibt gestrichen. Geprüft nach Erhöhen und nach Senken. (pytest API)
- [ ] `FinalSelectionDecision` (aufgenommen und ausgeschlossen) bleibt nach jedem `PUT` unverändert in der Endauswahl. Nur Fotos ohne Entscheidung wechseln. Der Aufbau enthält mindestens ein Foto ohne Entscheidung, das tatsächlich wechselt (Gegenprobe gegen „nichts ändert sich“). (pytest API)
- [ ] Die Zahl der `Rating`- und `FinalSelectionDecision`-Zeilen ist vor und nach `PUT` gleich. (pytest API)

**Bestehende Projekte**

- [ ] Projekt mit eigener Angabe und Bestandslauf: Nach der Umstellung sind `selection_target`, `effective_selection_target` und alle `selection_position` unverändert. (pytest API)
- [ ] Projekt ohne eigene Angabe, dessen Bestandslauf nach dem alten Zehntel berechnet wurde (Positionen direkt geseedet, Größe ≠ 150): `GET /projects/{id}` liefert `effective_selection_target == 150`. Vorschlag, Entwürfe beider Nutzer und Endauswahl gleichen bitgenau dem Zustand vorher. Wiederholte `GET`-Aufrufe berechnen nichts neu. (pytest API)
- [ ] Ende der Übergangszeit: (a) Ein anschließender **gescheiterter** Lauf lässt die Positionen unverändert. (b) Ein erfolgreicher Lauf **oder** ein `PUT` setzt die Vorschlagsgröße auf 150 bzw. auf die neue Zahl. (a) und (b) sind getrennte Fälle. (pytest Worker-Integration und API)
- [ ] Beim Ende der Übergangszeit bleiben eigene Aufnahmen, Streichungen und Endauswahl-Entscheidungen beider Nutzer erhalten, mit demselben Aufbau wie oben. (pytest API)
- [ ] Die Hinweiszeile „kleinerer Vorschlag“ erscheint in der Übergangszeit nur, wenn tatsächlich die Kandidaten ausgehen. Siehe Teststrategie, Punkt „Übergangszeit und Hinweis“. (vitest)

**Begriffe und Abgrenzung**

- [ ] Neue und geänderte Texte (Feldhinweis, Sperrgrund, 409-Meldung, Hinweiszeile) sagen „Klassifizierung“. (vitest bzw. pytest per Textprüfung an den neuen Stellen)
- [ ] Das Verfahren bleibt unverändert: Alle bestehenden Unit-Fälle in `test_selection.py` (Invarianten, Permutationen, Größenmatrix) bleiben grün. Geändert wird nur die Signatur `effective_target(configured)`. Es gibt kein Feld je Nutzer (kein neuer Spaltenwert, keine Nutzer-ID im Schema von `PUT`). (pytest Unit)

## Datenmodell-Bezug

Keine Schemaänderung. `projects.selection_target` (`NULL` = Standard) bleibt; die Vorbelegung 150 wird nie in die Spalte geschrieben. `docs/architecture.md` (Projekt/`selection_target`) wird auf die feste Vorbelegung 150 nachgezogen.

## Architektur / Umsetzung

**Ansatz.** Ein großer Teil ist schon vorhanden und wird weiterverwendet, nicht neu gebaut: `projects.selection_target` (`NULL` = nicht selbst eingestellt), `PUT /projects/{id}/selection-target` mit synchroner Neuberechnung (`worker.py::rebuild_run_selection` → `_apply_run_selection`, der eine Rechenweg für alle Auslöser), der 409-Wächter `api/projects.py::_reject_while_a_criterion_run_is_active` und `ProjectOut.selection_target`/`effective_selection_target`. Die Story ändert drei Dinge: (1) feste Vorbelegung 150 (ADR [0131](../decisions/0131-richtwert-vorbelegung-fest-150-statt-zehntel-der-bilderzahl.md), löst ADR 0097 Punkt 1 teilweise ab), (2) das Richtwert-Feld steht zusätzlich im Klassifizierungs-Schritt, (3) für die sofortige Wirkung gibt es einen Nachweis von Anfang bis Ende.

**Datenmodell / Migration.** Keine Schemaänderung, keine Alembic-Revision, kein Backfill. `NULL` bleibt „Standard“, eine eigene Angabe bleibt unverändert. Die Umstellung rechnet nichts neu: `selection_position` bleibt bis zum nächsten Auslöser stehen. Damit sind Vorschlag, beide Album-Entwürfe und Endauswahl unmittelbar danach unverändert. Die Übergangszeit endet beim nächsten *erfolgreichen* Lauf oder bei der nächsten Richtwert-Änderung. Ein gescheiterter Lauf schreibt `selection_position` nicht. Den Docstring der Migration `e7f8a9b0c1d2` nicht anfassen, er ist historisch.

**Backend, in dieser Reihenfolge:**
1. `backend/src/photosort/selection.py`: `DEFAULT_TARGET_DIVISOR` wird durch `DEFAULT_TARGET = 150` ersetzt. `effective_target(configured: int | None) -> int` verliert `photo_count`. Alle Aufrufstellen gleichzeitig umstellen:
   - `worker.py::_apply_run_selection`: die `photo_count`-Abfrage entfällt.
   - `api/projects.py::_to_single_project_out` bzw. der Aufbau von `ProjectOut` (um Z. 713): `photo_count` bleibt als Feld erhalten, speist den Richtwert aber nicht mehr.
   - `event_probe.py::quota_reach`: `project_photos` bleibt nur als Messgröße der Auswertungsgrenze. Den Satz „Der Richtwert rechnet auf den N Fotos des Projekts“ in `_quota_lines` passend umformulieren.
   - Kommentare in `models.py::Project` und `frontend/src/api/types.ts` nachziehen.
2. Sofortige Wirkung: Als Erstes ein Test auf API-Ebene in `tests/test_api_projects.py`. Ablauf: Projekt mit erfolgreichem Lauf, mehreren Events und genug bewerteten Kandidaten; Richtwert per `PUT` erhöhen und wieder senken; danach `GET` auf Album-Entwurf, Kuratierungsliste und Endauswahl lesen. Erwartet wird, dass die Zahl der `proposed`-Fotos wächst bzw. schrumpft. Der Lesepfad ist laut Code durchgehend live: Alle Lesestellen in `api/photos.py` werten `selection_position` des neuesten erfolgreichen Laufs aus, und `rebuild_run_selection` beschreibt genau diesen Lauf. Einen fehlerhaften Codepfad habe ich beim Lesen nicht gefunden [INFERENCE]. Wahrscheinlichste Ursache des gemeldeten Fehlers: `_quotas` gibt bei `T ≤ Eventzahl` jedem Event genau einen Platz. Eine Erhöhung unterhalb der Eventzahl ändert dann nichts. Das ist die zugesagte Abdeckungsregel und kein Fehler; bei der alten Vorbelegung (ein Zehntel) ist dieser Fall häufig. Wird der Test rot, liegt der Fix ausschließlich in `rebuild_run_selection`/`_apply_run_selection`, also im einen Rechenweg, ohne zweiten Pfad. Bleibt er grün, kommt kein Backend-Fix hinzu, und der Test bleibt als Regressionsnachweis stehen.
3. Vor dem ersten Lauf ist schon heute alles richtig und wird nur per Test festgehalten: `PUT` ohne erfolgreichen Lauf speichert, und `rebuild_run_selection` tut dann nichts. Der Lauf liest den Richtwert erst unmittelbar vor seinem Erfolgsvermerk, also gilt der vorher eingestellte Wert für den ersten Vorschlag und für jeden weiteren.
4. Sperre: Der vorhandene Wächter gibt 409 zurück, solange der *neueste* Kriterien-Lauf `running` ist. Den Meldungstext auf „Klassifizierung“ prüfen. Der Text sagt das schon, das Wort bleibt also.

**Erhalt von Nutzerzuständen.** Dafür gibt es keinen eigenen Code, die Erhaltung folgt aus der Struktur. „Aufgenommen“ und „gestrichen“ sind `Rating.status` (`ALBUM_WORTHY`/`REJECTED`) je Nutzer, Endauswahl-Entscheidungen sind `FinalSelectionDecision`. Beide hängen an keinem Lauf und werden von `_apply_run_selection` nie geschrieben, denn die Funktion schreibt nur `photo_rankings.selection_position`. Der Album-Entwurf (`api/photos.py::_draft_photo_ids`) und die Endauswahl (um Z. 1727) werden beim Lesen als Vereinigung von Vorschlag und eigener Entscheidung gebildet. Ein neuer Richtwert verschiebt deshalb nur den Vorschlagsanteil und Fotos ohne Entscheidung. Die Tests in `test_api_projects.py` halten das fest: aufgenommene, gestrichene und entschiedene Fotos bleiben nach `PUT` unverändert, und zwar für beide Nutzer.

**Frontend:**
1. Neue Komponente `frontend/src/components/SelectionTargetField.tsx`, herausgezogen aus `pages/pipeline/KuratierungStepPage.tsx`. Feld, Commit bei Blur oder Enter, Fehler-Alert, Hinweis „Vorschlag neu berechnet“ und `useSetSelectionTargetMutation` ziehen unverändert mit um. Die Kuratierungsseite nutzt danach die Komponente, damit es keine zweite Kopie gibt.
2. Standard oder eigene Angabe erkennbar: `selection_target === null` bedeutet weiterhin leeres Feld. Der Hinweis lautet sinngemäß „Standard: 150 Bilder“ und zeigt `effective_selection_target` vom Server. Ist eine eigene Angabe gesetzt, steht im Hinweis „eigene Angabe“ und daneben eine Aktion „Auf Standard zurücksetzen“, die `null` sendet. Den Text „ein Zehntel der Bilderzahl“ entfernen.
3. Einbau in `components/ClassificationSection.tsx`, gerendert von `KriterienStepPage.tsx`, über dem Auslöser. Dort gibt es die Kuratierung noch nicht, der Richtwert lässt sich also vor dem ersten Lauf einstellen.
4. Sperre in der Oberfläche: Die Komponente erhält `project.last_criterion_scoring_run?.status === 'running'` als Prop (oder liest den Status selbst) und setzt dann `disabled`, mit sichtbarem Grund über `aria-describedby` („Während die Klassifizierung läuft, lässt sich der Richtwert nicht ändern.“). Der Feldinhalt wird dabei nie zurückgesetzt. Die Angleichung beim Rendern (`lastSavedTarget`) überschreibt nur, wenn sich der *gespeicherte* Wert ändert. Ein trotzdem eintreffender 409 erscheint wie jeder Fehler als Alert, die Eingabe bleibt im Feld (vorhandenes Verhalten, Test beibehalten). Der 2-s-Poll von `useProjectQuery` gibt das Feld nach Laufende von selbst wieder frei.
5. Aktualisierung ohne Neuladen: `useSetSelectionTargetMutation` invalidiert bereits `['project', id]` und den Präfix `['photos', id]`. Darunter fallen Album-Entwurf (`draftQueryKey`), Kandidatenvorrat und Endauswahl (`['photos', id, SELECTION_QUERY_SEGMENT]`). Im Hook-Test ergänzen, dass auch der Endauswahl-Key invalidiert wird.
6. Kleinerer Vorschlag mangels auswahlfähiger Fotos: In `pages/AlbumDraftPage.tsx` eine neutrale Zeile (Textstil `text-muted`, kein `Alert`) einfügen, wenn der Vorschlagsanteil kleiner als `effective_selection_target` ist **und** die auswahlfähigen Kandidaten erschöpft sind (siehe Entscheidungen). Abgeleitet wird das in `utils/albumDraft.ts` neben `draftSizeText` aus den vorhandenen Zählungen, ohne neues API-Feld.
7. Begriff: In neuen oder geänderten Texten heißt der Schritt „Klassifizierung“.

**Tests, die ersetzt werden (nicht angepasst):** alle Fälle, die das Zehntel behaupten, in `test_selection.py`, `test_api_projects.py` (u. a. Z. ~1966), `test_event_probe.py` (`effective_target(None, n)`), `test_demo_state.py` (falls die Größe des Demo-Vorschlags davon abhängt) sowie die Frontend-Fabriken mit `effective_selection_target: 1`, wo der Text geprüft wird.

**Doku:** `docs/architecture.md` Abschnitt Projekt/`selection_target` (Z. ~1519-1526): Vorbelegung 150, Verweis auf ADR 0131.

**Reihenfolge:** selection.py samt Aufrufstellen und Tests → Nachweistests im Backend (sofortige Wirkung, vor dem ersten Lauf, Nutzerzustände) → `SelectionTargetField` herausziehen → Einbau in den Klassifizierungs-Schritt samt Sperre → Hinweis im Album-Entwurf → Doku.

## UI/UX

Die Story hat eine sichtbare Oberfläche: ein gemeinsames Richtwert-Feld (`SelectionTargetField`) im Klassifizierungs-Schritt und in der Kuratierung, dazu eine neutrale Zeile im Album-Entwurf. Ein neues Muster entsteht nicht. Es gelten diese Muster aus `specs/architecture/0004-design-system.md`: „Nicht verfügbare Aktion“ (deaktiviert, Begründung an fester Stelle, nie ausgeblendet), „Meldungen — Toast-Optik, kein Toast-Verhalten“ (Fehler inline als `Alert`), Fehlerzustand in der Ausnahme „reiner Formularfehler ohne eigene Wiederholaktion“ und „Auffangkorb … keine Fehler-Optik“ für den neutralen Hinweis.

**Ablauf und Lage**
- **Klassifizierungs-Schritt** (`ClassificationSection`): Das Feld steht über dem Auslöser „Klassifizierung starten“, mit demselben Aufbau wie in der Kuratierung. Darüber steht der Erklärsatz aus der Kuratierung unverändert: „Der Richtwert ist ein Ziel, keine Obergrenze — reicht der Bildbestand nicht, wird der Vorschlag kleiner; damit jeder Foto-Moment vorkommt, kann er auch größer werden.“ Der Satz davor („Der Vorschlag deckt alle Foto-Momente ab …“) bleibt nur in der Kuratierung stehen.
- **Kuratierung**: Das Feld wird an derselben Stelle durch die Komponente ersetzt; sichtbar ändert sich dort nur der Hinweistext.
- Beschriftung (unverändert): „Richtwert (Bilder)“, `<label htmlFor>`. Gespeichert wird bei Blur oder Enter, wie bisher; es gibt keine Speichern-Schaltfläche.

**Zustände des Feldes (Hinweiszeile `p` in `text-sm text-text-muted`, per `aria-describedby` am Feld)**
1. **Standard** (`selection_target === null`): Das Feld ist leer, Platzhalter `150`. Hinweis wörtlich: „Standard: {effective_selection_target} Bilder.“ Der Wert kommt vom Server. Der Text „ein Zehntel der Bilderzahl“ entfällt überall.
2. **Eigene Angabe**: Das Feld zeigt die Zahl. Hinweis wörtlich: „Eigene Angabe – Standard wäre 150 Bilder.“ Die 150 ist die Konstante aus dem Frontend-Typkommentar bzw. eine benannte Konstante, nicht `effective_selection_target`. Daneben steht in derselben Zeile `Button variant="ghost" size="sm"` „Auf Standard zurücksetzen“; die Schaltfläche sendet `null` und erscheint nur in diesem Zustand. Danach wird das Feld leer, der Fokus geht ins Feld (die Schaltfläche verschwindet, und der Fokus darf nicht auf `body` fallen), und es gilt Zustand 1.
3. **Gespeichert**: An die Hinweiszeile wird „ Vorschlag neu berechnet.“ angehängt, 4 s lang (`SAVED_HINT_MS`, unverändert). Vor dem ersten Lauf entfällt der Zusatz und wird ersetzt durch „ Gilt für den nächsten Vorschlag.“. Grund: Es wurde nichts neu berechnet, und die Hinweiszeile darf nichts Falsches behaupten. Erkannt wird der Fall daran, dass es keinen erfolgreichen Lauf gibt. Diese Feldangabe liefert das Projekt bereits; bei der Umsetzung prüfen.
4. **Speichert gerade**: Das Feld bleibt bedienbar, Zurücksetzen ist deaktiviert (Busy-Button-Muster). Es gibt keinen eigenen Spinner am Feld.
5. **Gesperrt** (`last_criterion_scoring_run?.status === 'running'`): Feld und Zurücksetzen sind `disabled` (Token `--text-disabled` nur über die `disabled:`-Variante), der Feldinhalt bleibt stehen. Unter dem Hinweis steht als eigener Satz in `text-sm text-text` (nicht `muted`, weil er die Bedienung erklärt) wörtlich: „Während die Klassifizierung läuft, lässt sich der Richtwert nicht ändern.“ Die id des Satzes kommt zusätzlich in `aria-describedby`. Er wird bewusst nicht als Live-Region ausgeführt, weil der Zustand mit dem Start der Klassifizierung eintritt und dort bereits angekündigt wird. Der 2-s-Poll gibt das Feld nach dem Laufende von selbst frei; der Satz verschwindet dann ohne Meldung. Begründung für `disabled` statt `aria-disabled`: Beim Eingabefeld gibt es außer dem Grund nichts zu erreichen, und der Grund steht sichtbar daneben. Das ist anders als beim gesperrten Schritt der Schrittleiste, dessen Grund nur im Popover steht.
6. **Fehler** (auch ein trotzdem eintreffender 409): `Alert variant="error"`, Titel „Richtwert nicht gespeichert“, Text `error.detail` des Servers. Fehlt er, lautet der Text „Der Richtwert konnte nicht gespeichert werden.“ Die Eingabe bleibt im Feld, und ein erneutes Blur/Enter ist die Wiederholung; es gibt kein zweites „Erneut versuchen“. Der Fehler verschwindet, sobald die Eingabe dem gespeicherten Wert wieder entspricht (vorhandenes Verhalten). Der Text des 409 vom Server muss „Klassifizierung“ sagen.
7. **Ungültige Eingabe** (0, negativ, keine ganze Zahl): unverändert wie heute; die Validierung wird nicht neu gestaltet.

**Album-Entwurf: kleinerer Vorschlag**
- Unter der Kopfzeile (`draftSizeText`) steht eine Zeile in `text-sm text-text-muted`, ohne `Alert`, ohne Symbol, ohne Fehlerfarbe und ohne `role`. Sie erscheint nur, wenn der Vorschlagsanteil kleiner ist als `effective_selection_target` und die auswahlfähigen Kandidaten erschöpft sind. Wortlaut: „Der Vorschlag umfasst {n} Fotos statt etwa {Richtwert} – mehr auswahlfähige Fotos gibt dieses Projekt nicht her.“
- Liegt der Vorschlag über dem Richtwert (Abdeckungsregel), gibt es keine Zeile: Das sagt der Erklärsatz zum Richtwert schon.
- Die Zeile ist ein Hinweis und nichts, das behoben werden müsste; einen Weg zur Korrektur gibt es nicht. Das folgt der Linie von `draftSizeText` („kein zweiter Ton“).

**Begriff**: In allen neuen oder geänderten Texten heißt es „Klassifizierung“, nie „Kriterien-Bewertung“ oder „Scoring“.

**Barrierefreiheit**
- Am Feld hängt `aria-describedby` mit der Hinweis-id und, wenn gesperrt, mit der id des Sperrsatzes. Der Standard bzw. die eigene Angabe steht als Text da, nicht nur als Leere oder Farbe.
- „Auf Standard zurücksetzen“ ist ein echter `<button>` mit Mindesthöhe nach Design-System (`h-11 sm:h-8`, wie auf heißen Pfaden). Sein zugänglicher Name ist identisch mit dem sichtbaren Text.
- Die Bestätigung „Vorschlag neu berechnet.“ ist wie bisher Teil der beschriebenen Hinweiszeile; es kommt keine neue Live-Region hinzu. Fehler kommen über `Alert` mit `role="alert"` (Komponentenstandard).
- 360 px: Feld und Zurücksetzen-Schaltfläche umbrechen untereinander (`flex flex-wrap gap-3`), ohne waagerechtes Scrollen.

**Design-System**: keine Ergänzung nötig. Alle Zustände sind vorhandene Muster, und der Skill `design-system` bleibt unverändert.

## Teststrategie

- **Ebenen.** Unit (pytest `test_selection.py`): Standard 150, unabhängig von der Bilderzahl. Die Größen- und Abdeckungsmatrix bleibt und verliert nur `photo_count`. Worker-Integration: erster und weiterer Lauf mit vorher gesetztem T, gescheiterter Lauf ohne Schreibwirkung. API (`test_api_projects.py`): Kern der Story, also sofortige Wirkung, 409, beide Nutzer und Übergangszeit. vitest: `SelectionTargetField`, Einbau in `ClassificationSection`, Sperre, Hook-Invalidierung, `albumDraft.ts`. **Kein E2E.** Die einzige Kette über Schichten hinweg (PUT → Invalidierung → Neurendern) ist durch den API-Test plus den Hook-Invalidierungstest geschlossen. Das Polling ist bestehendes Verhalten.
- **Ersetzen statt anpassen.** Alle Fälle, die ein Zehntel behaupten (`test_selection.py`, `test_api_projects.py` ~Z. 1966, `test_event_probe.py`, ggf. `test_demo_state.py`, Frontend-Fixtures mit `effective_selection_target: 1` und Textprüfung), werden durch Fälle für 150 ersetzt. Eine still geänderte Erwartung in einem Fall, der den Richtwert nur als Vehikel nutzt, ist ein Finding.
- **Nachweistest für den gemeldeten Fehler.** Laut Architekt ist die Ursache nicht gefunden [INFERENCE: wahrscheinlich T ≤ Eventzahl]. Deshalb prüft der Test seine Vorbedingung selbst (T > Eventzahl, Kandidaten ≥ T_neu, Größe ändert sich). Sonst wäre er grün, ohne irgendetwas zu belegen. Zusätzlich gibt es einen expliziten Fall „Erhöhung unterhalb der Eventzahl ändert nichts“. Er dokumentiert die Abdeckungsregel als gewollt und macht den Unterschied zum Fehler sichtbar.
- **Edge Cases.** T ≤ Eventzahl. T > Kandidatenzahl. Entfernen (`null`) vor und nach dem ersten Lauf. 409 nur beim *neuesten* Lauf `running`; ein älterer `running`-Lauf unter einem neueren beendeten blockiert nicht. Nach `failed` wieder änderbar. Gescheiterter Lauf in der Übergangszeit. Zwei Nutzer mit disjunkten Entscheidungen. Eingabe bleibt beim Wechsel der Sperre stehen. Validierungsfehler (0, negativ) ergibt 422 plus Alert; die bestehenden Grenzen bleiben.
- **Übergangszeit und Hinweis (technische Anforderung an die Umsetzung, keine Produktfrage).** Wird die Hinweiszeile nur aus „Vorschlagsanteil < `effective_selection_target`“ abgeleitet, erscheint sie bei jedem Bestandsprojekt ohne eigene Angabe fälschlich. Dort ist der Vorschlag nach dem alten Zehntel klein, obwohl genug Fotos da sind, und die Zeile behauptet eine falsche Ursache. Die Ableitung muss an „Kandidaten erschöpft“ hängen, z. B. Vorschlagsanteil == Zahl auswahlfähiger Kandidaten. Pflichtfall in vitest: Vorschlag < Richtwert, aber Kandidaten > Vorschlag → keine Zeile. Ob die vorhandenen Zählungen das hergeben, prüft der Architekt bzw. die Umsetzung. Fehlt die Zahl, braucht es doch ein API-Feld; das widerspricht dem Architekturabschnitt („ohne neues API-Feld“) und gehört dorthin zurück.
- **Testkonzept.** Eine kleine Ergänzung in der Sektion zu ADR 0097 (`selection.py`) ist nötig, sonst bleibt alles unverändert. Neue projektweite Regel: *Ein Regressionstest für einen gemeldeten Fehler ohne gefundene Ursache prüft im Test selbst, dass sein Aufbau den Fehler zeigen könnte (Parameter im wirksamen Bereich, Vorher ≠ Nachher), und hat einen Gegenfall im unwirksamen Bereich.* Dazu ein Satz zur Übergangszeit ohne Migration: Bestandszustand wird über direkt geseedete Positionen hergestellt, „Lesen rechnet nicht neu“ wird über wiederholte `GET`s geprüft, und das Ende wird je Auslöser einzeln geprüft, einschließlich des Nicht-Auslösers „gescheiterter Lauf“. Die Ergänzung habe ich nicht geschrieben (Auftrag: nur Rückgabe). Ich übernehme sie auf Zuruf.
- **Selbst entschiedene Punkte knapp unter der Abgabeschwelle.** (1) Kein E2E. Rein technisch, weil jede Schichtgrenze einzeln belegt ist. (2) Hinweiszeile an „Kandidaten erschöpft“ gebunden. Das ist die wörtliche Lesart des bestehenden AC („mangels auswahlfähiger Fotos“), keine neue Produktaussage.

## Security

**Einstufung: sicherheitsrelevant, aber ohne Blocker.** Die Story bringt keinen neuen Endpunkt, kein Secret, keine Umgebungsvariable, keinen Cloud-Aufruf und keinen Bilddatenfluss. Sie nutzt `PUT /projects/{id}/selection-target` stärker als bisher. Das Feld gibt es dann auch im Klassifizierungs-Schritt, und man kann es auf `null` zurücksetzen. Außerdem ändert sich, wie der wirksame Richtwert berechnet wird. Grundlage ist der Abschnitt „Der Auswahlvorschlag mit Richtwert“ im Sicherheitskonzept (Spec 0429/ADR 0097). Er gilt weiter. Hier steht nur, was diese Story daran berührt.

### Bedrohungen und Gegenmaßnahmen

**S1 – Eingabe `target`: Werte und Grenzen (muss bleiben).**
- `SelectionTargetUpdate.target` behält `Annotated[int, Field(ge=1, le=MAX_SELECTION_TARGET)] | None` und hat **keinen Vorgabewert**.
- Ein fehlendes Feld ergibt `422`. Es setzt den Wert nicht still zurück.
- `0`, negative Werte, Werte über `MAX_SELECTION_TARGET`, Strings, Kommazahlen und `true` ergeben `422`, und zwar bevor geschrieben wird.
- `null` ist ein zulässiger Wert und bedeutet „zurück zum Standard“. Die Vorbelegung 150 wird **nie** in die Spalte geschrieben. Steht sie dort, ist „Standard“ nicht mehr von „eigene Angabe“ zu unterscheiden, und eine spätere Änderung der Vorbelegung erreicht das Projekt nicht mehr.
- Der feste Deckel schützt vor Überlauf: Ohne ihn würde ein Wert jenseits von 2^63 einen `500` auslösen statt eines `422`. Gegen Last schützt er nicht (siehe S3).
- Die Aktion „Auf Standard zurücksetzen“ sendet wörtlich `{"target": null}`. Das Frontend schickt nie ein leeres Objekt.
- Nachweis: ein parametrisierter Test in `test_api_projects.py`. Er prüft die abgelehnten Werte samt fehlendem Feld mit „`422`, Spalte unverändert, `selection_position` unverändert“ und `null` mit „Spalte `NULL`, `effective_selection_target == 150`“.

**S2 – Authentifizierung und Projektbindung (unverändert, muss bleiben).**
- Der Endpunkt hängt am router-weiten Torwächter `dependencies=[Depends(get_current_user)]` in `api/projects.py`. Ohne JWT antwortet er `401`.
- Das Projekt kommt ausschließlich aus dem Pfadparameter. Die Reihenfolge der Prüfungen ist `404` → `409` → schreiben.
- Der Körper trägt genau `target`. Weder er noch ein Query-Parameter bestimmt eine Lauf-, Event- oder Foto-Id.
- Die neue Frontend-Komponente `SelectionTargetField` bildet den Pfad nur aus der numerischen Projekt-Id des geladenen Projekts, nie aus Freitext.

**S3 – Neuberechnung als Lastauslöser: bewusst getragen, kein Rate-Limiting.**
- Jeder `PUT` rechnet synchron die Greedy-Vergabe über den auswahlfähigen Bestand des neuesten erfolgreichen Laufs.
- Die Kosten sind durch diesen Bestand nach oben begrenzt. Ein großer Richtwert heißt „alles auswählen“ und kostet nicht mehr.
- Die Story vervielfacht die Auslöser nicht. Gespeichert wird bei Blur oder Enter, nicht bei jedem Tastendruck. Auf dieser Debounce-freien Form muss es bleiben: kein Speichern per `onChange`.
- Es gibt keinen Cloud-Aufruf, also keinen Kostenpfad, der ein gestohlenes JWT lohnend machte.
- Kein Rate-Limiting, wie im übrigen API-Bereich („kein Innentäter-Modell“). Vor dem ersten Lauf macht `rebuild_run_selection` nichts.
- `effective_target` verliert `photo_count`. Die Zählabfrage in `_apply_run_selection` entfällt, die Last sinkt also etwas.

**S4 – Sichtbarkeit zwischen beiden Nutzern: keine neue Datenklasse.**
- Richtwert und Vorschlag sind Eigenschaften des Projekts bzw. des Laufs, nicht des Nutzers. Ändert ein Nutzer den Richtwert, ändert sich der Vorschlag auch für den anderen. Das ist das vorhandene Projektmodell (ADR 0003: beide sehen alle Projekte) und keine neue Asymmetrie.
- Muss: `user_id` fließt in keine Abfrage und keine Schreibanweisung von `rebuild_run_selection`/`_apply_run_selection`.
- Muss: `_apply_run_selection` schreibt ausschließlich `photo_rankings.selection_position` des neuesten erfolgreichen Laufs **dieses** Projekts. `Rating` und `FinalSelectionDecision` beider Nutzer schreibt es nie. Sonst überschriebe der Richtwert eines Nutzers die eigenen Entscheidungen des anderen.
- Die geplanten Tests „Nutzerzustände bleiben erhalten, für beide Nutzer“ sind genau dieser Nachweis. Sie müssen ausdrücklich mit zwei verschiedenen Nutzern laufen.
- Die Projektbindung liegt allein am Laufprädikat aus `_latest_successful_criterion_scoring_run_id(session, project_id)`, denn `photo_rankings` hat keine `project_id`. Ein Test mit zwei Projekten hält fest, dass ein `PUT` auf Projekt A die `selection_position` von Projekt B nicht verändert.
- Der neue Hinweis im Album-Entwurf („kleinerer Vorschlag“) wird nur aus Zählungen abgeleitet, die die Antwort schon enthält. Er braucht kein neues API-Feld und keine nutzerübergreifende Zahl.

**S5 – Sperre während des Laufs, Wettlauf.**
- Maßgeblich ist der Server: `_reject_while_a_criterion_run_is_active` antwortet `409`, solange der neueste Kriterien-Lauf `running` ist, und zwar **vor** jedem Schreibvorgang.
- Das `disabled` in der Oberfläche ist nur Bedienkomfort und keine Schutzmaßnahme. Ein direkter `PUT` muss weiterhin `409` bekommen, ohne Schreibvorgang. Test: laufender Lauf ⇒ `409`, `selection_target` und `selection_position` unverändert.
- Der Meldungstext bleibt fest, ohne eingesetzte Werte. Das Frontend zeigt ihn nur als Textknoten.
- Restrisiko, wie im Sicherheitskonzept schon für diese Wächterklasse vermerkt („eine Höflichkeitsprüfung, keine Sperre“): Der Wächter sieht weder einen eingereihten, noch nicht gestarteten Job noch einen Lauf, der zwischen Prüfung und `commit` fertig wird. In diesem schmalen Fenster kann der neue Lauf mit dem alten Richtwert abschließen, während die Oberfläche schon den neuen zeigt. Folge ist nur eine Abweichung des Vorschlags, die der nächste Auslöser wieder behebt. Es gibt keine Rechteausweitung, keinen Datenabfluss und keine Zerstörung von Nutzerentscheidungen. Bewusst ohne Zeilensperre, die zudem unter SQLite nicht prüfbar wäre.

**S6 – Frontend.**
- Neue Texte („Standard: 150 Bilder“, „eigene Angabe“, Sperrgrund über `aria-describedby`) sind feste Zeichenketten oder Zahlen vom Server und werden als React-Textknoten gerendert.
- Kein `dangerouslySetInnerHTML`, und die Server-Fehlermeldung wird nicht als HTML gerendert.
- Kein Wert kommt aus URL oder Query-Parameter.

### Ausdrücklich geprüft, ohne Befund

- Kein Secret, keine `.env`, kein Consent-Schalter, keine Kostenschätzung, kein Bilddatenfluss.
- Kein neuer Fremdtext in Persistenz, Antwort oder Log.
- Keine Schemaänderung und keine Migration, also keine Altbestandsfrage.
- Die Umstellung rechnet nichts neu und verändert keine Daten.

### Sicherheitskonzept

Ein neuer Abschnitt ist nicht nötig. Mit dem umsetzenden Pull Request kommt eine kurze Fortschreibung in den Abschnitt „Der Auswahlvorschlag mit Richtwert“:
- Die Vorbelegung ist jetzt fest 150 (ADR 0131), unabhängig von der Bilderzahl.
- Das Feld gibt es zusätzlich im Klassifizierungs-Schritt.
- Die Ankerzeilen kommen in die Tabelle: S1 Werte/`null`, S4 schreibt nur `selection_position` + Bindung an das Projekt, S5 `409` ohne Schreibvorgang.

## Entscheidungen

- Hinweiszeile „kleinerer Vorschlag“ hängt an „Kandidaten erschöpft“ (Vorschlagsanteil == Zahl auswahlfähiger Kandidaten), nicht allein an „Vorschlagsanteil < Richtwert“ — sonst erschiene sie in der Übergangszeit bei Bestandsprojekten mit falscher Ursache. Liefern die vorhandenen Zählungen die Kandidatenzahl nicht, kommt ein API-Feld dazu.
- Keine Migration und kein Merker für die Übergangszeit; sie endet mit dem nächsten Auslöser von selbst.
- Ein gemeinsames `SelectionTargetField` für Klassifizierungs-Schritt und Kuratierung.
- Kein E2E-Test; jede Schichtgrenze ist einzeln belegt.
- Kein Rate-Limiting und keine Zeilensperre gegen das Wettlauf-Fenster beim 409-Wächter (bestehende Linie des Sicherheitskonzepts).
- Alle vier Konsultationen (architect, ux-ui-designer, test-engineer, security-engineer) haben stattgefunden; keine Produktentscheidung offen.

## Offene Fragen

Keine.

## Out of Scope

- Änderungen am Auswahlverfahren selbst (Verteilung auf Foto-Momente, Motivmischung, Personen-Abdeckung).
- Ein Richtwert je Nutzer.
