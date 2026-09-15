# 0486 - Duplikat-Gruppen in einem Durchgang, mit sichtbarer Vorauswahl

**Status:** Accepted
**Erstellt:** 2026-09-15
**Bezug:** [Issue #486](https://github.com/TheRealKoller/photosort/issues/486), ADR
[`0111`](../decisions/0111-vergleichsansicht-zeigt-das-praedikat-nicht-die-entscheidungszeile.md),
ADR [`0104`](../decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md)

**Diese Spec hebt drei Zusagen der Spec [`0374`](./0374-duplikate-vergleichen.md) bewusst auf:**
AK2 (kein Mitglied trägt eine Auszeichnung), AK6 (drei Zustände je Mitglied) und AK10 (der Zähler
zählt die offenen Gruppen). Wer die Umsetzung prüft, behandelt das als gewollt, nicht als
Regression. Die Spec 0374 bleibt im Übrigen gültig; ihre Sicherheitsauflagen S1–S11 gelten
unverändert weiter.

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Der Abschnitt `## Security` führt sieben
Auflagen in der geschützten Dreiteilung, und der Abschnitt `## Teststrategie` muss die
Bestandstests namentlich führen, die durch das Aufheben der drei Zusagen falsch werden — ohne diese
Liste hält der Umsetzungslauf einen bewusst umzuschreibenden Test für eine Regression.

## Ziel

Die Duplikatsansicht zeigt die Aufnahmen einer Serie nebeneinander, damit man selbst entscheiden
kann, welche bleibt. Zwei Dinge stehen dem heute im Weg.

Erstens ist sie nicht durchlaufbar: Die Überschrift nennt zwar, die wievielte Gruppe man gerade
sieht, aber es führt kein Weg zur nächsten. Nach jeder Gruppe muss man zurück in die Fotoliste und
dort eine neue Aufnahme suchen, über die man wieder einsteigt. Bei einer Urlaubsserie mit vielen
Duplikatgruppen ist das der Regelfall, und es macht das Sichten in einem Zug unmöglich.

Zweitens verschweigt sie, was ohne Zutun geschieht. Alle Aufnahmen einer Gruppe sehen gleich aus,
obwohl sie es nicht sind: Wer nichts entscheidet, für den gilt die Vorauswahl des Systems — die
Verlierer der Gruppe scheiden aus, die vom System gewählte Aufnahme bleibt. Man trifft also eine
Nicht-Entscheidung mit Wirkung, ohne die Wirkung zu sehen. Dazu kommt, dass der Einstieg in den
Vergleich schlecht auffindbar ist: Er hängt heute an einzelnen Kacheln und nur an solchen, die als
Duplikat vorgeschlagen sind.

Betrifft beide Nutzer und jedes Projekt mit Serienaufnahmen.

## User Story

Als Nutzer möchte ich beim Sichten des Ausschusses alle Duplikat-Gruppen in einem Durchgang
durchgehen und dabei von Anfang an sehen, welche Aufnahmen ohne mein Zutun ausscheiden, damit ich
nur noch dort eingreife, wo ich es anders will, statt jede Gruppe einzeln zu suchen und dabei zu
raten, worüber ich gerade entscheide.

## Akzeptanzkriterien

- [ ] **AK1 — Die Vorauswahl steht schon da.** Beim Öffnen einer Gruppe trägt jede Aufnahme bereits
      den Zustand, der ohne weiteres Zutun eintritt — dargestellt in derselben Form, die auch eine
      selbst getroffene Wahl hat. Die vom System behaltene Aufnahme steht als „behalten" da, die
      Verlierer stehen als „Ausschuss" da. Eine Aufnahme ohne dargestellten Zustand gibt es nicht.
      Das gilt auch für ein Mitglied **ohne `PhotoScore`-Zeile**: Ein Repräsentant braucht
      strukturell keine eigene Zeile, um referenziert zu werden, und eine fehlende Zeile wird wie
      `suggested_status = NULL, duplicate_of = NULL` gelesen (⇒ „behalten", änderbar).
      Hebt **AK2 der Spec 0374** auf.

- [ ] **AK2 — Die eigene Handlung ist ein Ändern, kein Erst-Entscheiden.** Es gibt keinen sichtbaren
      Zustand „noch nicht entschieden" mehr. Ob ein dargestellter Zustand vom System oder vom Nutzer
      stammt, wird nicht unterschieden und nicht angezeigt. Hebt **AK6 der Spec 0374** auf.

- [ ] **AK3 — Was sich nicht ändern lässt, sagt das.** Eine Aufnahme, deren Ausschuss nicht aus dem
      Duplikat folgt — namentlich eine wegen Unschärfe abgelehnte —, lässt sich in dieser Ansicht
      nicht auf „behalten" drehen. Sie zeigt ihren Ausschuss mitsamt dem Grund und bietet „behalten"
      gar nicht erst an, statt einen Klick anzunehmen, der still wirkungslos bleibt. Die bestehende
      Wirkungsregel (eine Ablehnung aus anderem Grund als dem Duplikat bleibt bestehen) wird dadurch
      **nicht** geändert.

- [ ] **AK4 — Der Hinweistext sagt weiterhin die Wahrheit.** Der feste Hinweis der Ansicht sagt,
      dass der dargestellte Zustand gilt, wenn man ihn nicht ändert. Er darf nicht mehr behaupten,
      es liege noch keine Entscheidung vor, und er darf nicht zusichern, dass unentschiedene
      Aufnahmen erhalten bleiben.

- [ ] **AK5 — Vor und zurück zwischen den Gruppen.** Aus der Ansicht heraus ist die nächste und die
      vorherige Duplikat-Gruppe erreichbar, ohne den Umweg über die Fotoliste. Ziel ist jeweils die
      **Repräsentanten-Id der Nachbargruppe**. An der ersten Gruppe ist „zurück" nicht bedienbar, an
      der letzten „vor" nicht — „nicht bedienbar" heißt `disabled`, nicht „fehlt". Eine bereits
      vollständig entschiedene Gruppe bleibt erreichbar und wird nicht übersprungen; ein Durchgang
      vom Einstieg aus besucht jede Gruppe genau einmal und endet nach `total` Schritten.

- [ ] **AK6 — Der Zähler bleibt konstant.** Die Überschrift zählt **alle** Duplikat-Gruppen des
      Projekts, nicht nur die noch offenen. Die Gesamtzahl ändert sich während des Durchgangs nicht,
      und die Position einer Gruppe verschiebt sich nicht dadurch, dass eine andere entschieden
      wird — zugesichert gegen **beide Schreibwege des Produkts**, nicht nur gegen zwei
      aufeinanderfolgende Lesevorgänge. Hebt **AK10 der Spec 0374** auf.

- [ ] **AK7 — Einstieg an beiden Stellen.** Ein Einstieg „Duplikate vergleichen" führt in die
      Ansicht, und zwar von zwei Stellen aus: aus dem Ausschuss-Schritt heraus, gleichrangig neben
      dem Sichten der Einzelvorschläge, und aus der nach Vorschlägen gefilterten Fotoliste heraus,
      als ein Weg für die ganze Liste statt nur für eine Kachel. Er führt zur ersten Duplikat-Gruppe.
      Der bestehende Weg je Kachel bleibt daneben erhalten. Der zugängliche Name des listenweiten
      Einstiegs überschneidet sich **nicht** mit dem des Kachel-Einstiegs
      (`Duplikate vergleichen: <Dateiname>`), und die Namen der Gruppennavigation überschneiden sich
      **nicht** mit den bestehenden `Vorherige/Nächste Aufnahme der Gruppe`.

- [ ] **AK8 — Kein Einstieg ins Leere.** Gibt es im Projekt keine einzige Duplikat-Gruppe, führt
      keiner der beiden Einstiege auf eine leere Ansicht: Er wird dann **nicht gerendert** — auch
      nicht während des Ladens, damit er nicht kurz aufblitzt.

## Datenmodell-Bezug

**Keine Migration, keine neue Spalte, keine Änderung an `photo_duplicate_decisions`.** Betroffen
sind ausschließlich Antwortformen (`DuplicateGroupPhotoOut`, `DuplicateGroupOut`, neu
`DuplicateGroupIndexOut`) und die Ableitungen in `duplicates.py`. Die Endpunktübersicht in
[`docs/architecture.md`](../../docs/architecture.md) wird im selben Pull Request nachgezogen.

## Architektur / Umsetzung

### Der angezeigte Zustand kommt vom Server und ist das Überlebens-Prädikat (AK1, AK2, AK3)

Die Ansicht zeigt nicht mehr die **Entscheidungszeile**, sondern die **Auswertung des
Überlebens-Prädikats** (ADR 0111). `DuplicateGroupPhotoOut` verliert `decision` und bekommt zwei
Felder:

- `effective_decision: DuplicateDecision` — `keep`, wenn das Foto den Ausschuss-Schritt überlebt,
  sonst `discard`. Das trägt AK1 (der unentschiedene Duplikat-Verlierer trägt
  `suggested_status = REJECTED` und steht damit von Anfang an als „Ausschuss" da) und AK2 (es gibt
  keinen dritten Wert, und aus der Antwort geht nicht hervor, ob der Zustand vom Automaten oder vom
  Nutzer stammt).
- `keep_possible: bool` — ob „behalten" für dieses Mitglied überhaupt etwas bewirken kann (AK3).
  `false` genau dann, wenn `duplicate_of IS NULL AND suggested_status IS NOT NULL`; ein solches
  Mitglied steht unveränderlich auf `discard`, weil kein Wert der Entscheidungszeile seinen Zustand
  ändert.

**Beide Werte werden in `duplicates.py` gebildet, auf der bestehenden privaten `_survives`** — nicht
in `api/photos.py` und nicht durch Delegation an `survives_ausschuss_for`. Drei Gründe, jeder
mechanisch:

1. `tests/test_ausschuss_ueberlebende.py::test_no_source_file_writes_the_survivor_condition_by_hand`
   nimmt `duplicates.py` ausdrücklich von der Prüfung aus und schlägt für jede andere Quelldatei an,
   die `suggested_status is (not) None` ausschreibt. `keep_possible` ausgeschrieben in
   `api/photos.py` wäre sofort rot — zu Recht.
2. Der Aufrufstellen-Wächter `_ERWARTETE_VERWENDUNGEN` (Sollgröße 7, davon 5 SQL-Fassungen) zählt
   Aufrufe der vier benannten Prädikatsfunktionen. Zwei neue Namen (`effective_decision_for`,
   `keep_possible_for`) lassen ihn unberührt. **Dieses Wörterbuch wird nicht angefasst** — und in
   keinem Fall wird ein Eintrag gesenkt oder entfernt, um den Wächter grün zu bekommen.
3. `survives_ausschuss_for` liefert für ein Mitglied **ohne `PhotoScore`-Zeile** `False` (es bildet
   den inneren Join nach). Eine Delegation dorthin zeigte den Gruppengewinner ohne Score-Zeile als
   unumkehrbaren Ausschuss — genau verkehrt.

`keep_possible_for(photo)` ist ausdrücklich **keine neue Regel**, sondern dasselbe Prädikat an einer
hypothetischen Entscheidung: `_survives(suggested_status, duplicate_of, DuplicateDecision.KEEP)`.
Die Asymmetrie aus ADR 0104 Punkt 3 wird dadurch gelesen, nicht geändert.

**Beide Funktionen behandeln `score is None` ausdrücklich** und lesen es wie
`suggested_status = NULL, duplicate_of = NULL` (⇒ `keep` / `keep_possible = true`). `load_duplicate_links`
joint `PhotoScore` äußer, weil `photo_scores.duplicate_of` auf `photos.id` zeigt und ein Repräsentant
deshalb keine eigene Zeile braucht. Ein `photo.score.suggested_status` an der Aufrufstelle wirft dort
`AttributeError` und reißt nicht eine Kachel, sondern die gesamte Gruppenantwort auf `500` — den
einzigen Zugang zur Ansicht.

**Der Grund hinter `keep_possible === false` wird nicht als Feld übertragen.** Er folgt aus der
Bedingung selbst: `duplicate_of IS NULL` ist genau das, woran `_suggestion_reason` `low_quality`
festmacht. Die Oberfläche rendert dort einen festen Text. Ein Backend-Test hält die Äquivalenz fest,
damit ein künftiger dritter Ablehnungsgrund laut auffällt statt still.

**Der gruppenweite Schreibweg bleibt unverändert** und schreibt auf **alle** Mitglieder, das
unveränderliche eingeschlossen. Die Menge bestimmt der Server aus dem Stern (Auflage S6 der Spec
0374); ein Herausfiltern wäre eine zweite Mengendefinition, und die dort geschriebene Zeile bleibt
ohnehin wirkungslos.

### Der Zähler und das Blättern (AK5, AK6)

In `duplicates.py`:

- `DuplicateLink.decided` und `open_group_representative_ids` **entfallen**; `load_duplicate_links`
  joint `PhotoDuplicateDecision` nicht mehr mit. Die Gruppenreihenfolge kennt keinen Unterschied
  zwischen offen und erledigt mehr.
- `group_position` wird zu `group_standing(representative_id, links) -> GroupStanding | None` mit
  `position`, `total`, `previous_id`, `next_id` — **eine** geordnete Liste
  (`all_group_representative_ids`), einmal berechnet. Die bisherige Vereinigung „offene Gruppen ∪
  die angesehene" entfällt ersatzlos.
- Reihenfolge unverändert: frühester `taken_at` der Mitglieder, bei Gleichstand die
  Repräsentanten-Id. Sie hängt an keinem Wert, den eine Entscheidung ändert — das ist die
  Stabilitätszusage aus AK6.

`DuplicateGroupOut` bekommt `previous_photo_id: int | null` und `next_photo_id: int | null` — die
Repräsentanten-Id der Nachbargruppe, `null` am Rand (AK5: dort nicht bedienbar).

**Kein Gruppenindex in der Route.** `/projects/:projectId/photos/:photoId/duplicates` bleibt
unverändert, `PROJECT_ROUTE_PATHS` bleibt bei zehn Einträgen. Der Pfadwert bleibt ein Anker-Foto —
beim Blättern das der Nachbargruppe, beim Einstieg über eine Kachel weiterhin das angeklickte.
Navigation per `navigate(...)` als Push (kein `replace`): Der Zurück-Knopf des Browsers ist dann
„vorherige Gruppe".

**Die Seite bleibt beim Gruppenwechsel montiert** (gleiche Route, anderer Parameter). `enlargedId`
und `decidingIds` müssen bei Änderung von `anchorId` zurückgesetzt werden, sonst zeigen sie auf
Fotos einer Gruppe, die nicht mehr da ist.

### Der Einstieg an zwei Stellen (AK7, AK8)

Neuer Lese-Endpunkt `GET /projects/{project_id}/duplicate-groups` →
`DuplicateGroupIndexOut { total: int, first_photo_id: int | null }`. Er braucht keine
Foto-Hydratation und kommt mit `load_duplicate_links` + `all_group_representative_ids` aus; `total`
ist dieselbe Zahl wie in `DuplicateGroupOut`. Er liegt in `api/photos.py`, trägt seine
Auth-Dependency **ausgeschrieben** (`photos.router` hat keine router-weite `dependencies`-Liste),
begrenzt `project_id` deklarativ wie die drei bestehenden Endpunkte (`ge=1`,
`le=MAX_QUERY_POSITION`) und bekommt einen Eintrag in
`test_openapi_beschreibungen.py::DOCUMENTED_ROUTES`.

Frontend: `useDuplicateGroupIndexQuery(projectId)` unter dem Schlüssel
`['photos', projectId, 'duplicates', 'index']` — dieselbe breite Invalidierung greift.

- **`pages/pipeline/AusschussStepPage.tsx`:** Schaltfläche „Duplikate vergleichen" neben
  „Vorschläge ansehen", beide nur bei `scoringStatus === 'success'`; die neue zusätzlich nur bei
  `total > 0`. Abfrage `enabled` an dieselbe Bedingung gehängt.
- **`pages/PhotoGridPage.tsx`:** ein Einstieg für die ganze Liste (nicht je Kachel), sichtbar nur bei
  `filterParam === 'suggested'` und `total > 0`, außerhalb des Kachelrasters. Abfrage
  `enabled: filterParam === 'suggested'`.
- Beide führen auf `/projects/{id}/photos/{first_photo_id}/duplicates`.

### Text und Kachel

- `DUPLICATE_HINT_TEXT` wird neu gefasst (AK4).
- `DUPLICATE_CONSEQUENCE_TEXT` bleibt **wortgleich** stehen: Er trägt die Sicherheitsauflage S4 der
  Spec 0374 (die Folge von „behalten" für den Datenabfluss).
- `DuplicatePhotoTile`: `ZUSTAENDE` verliert `undecided` und führt nur noch `keep`/`discard`;
  `data-duplicate-decision` trägt entsprechend nur noch zwei Werte. `aria-pressed` hängt an
  `effective_decision`. Bei `keep_possible === false` rendert die Kachel **keine**
  Wahlschaltflächen — weder „behalten" (AK3) noch „Ausschuss" (der wäre ebenso wirkungslos) —,
  sondern den Zustand samt Grund. Die Dämpfung (`data-dimmed`) folgt unverändert
  `effective_decision === 'discard' && !enlarged`; der Eintrag in
  `designSystem.contract.test.ts::OPACITY_ALLOWLIST` bleibt derselbe.

### Demo-Bestand

`demo_state.py::_seed_duplicate_project`: Der Repräsentant der zweiten Gruppe bekommt
`suggested_status = REJECTED` bei `duplicate_of = None` und `sharpness` unterhalb
`SHARPNESS_REJECT_THRESHOLD` — eine Serie unterhalb der Schärfeschwelle, deren Gewinner trotzdem
abgelehnt ist. Ohne diesen Zustand ist AK3 weder vorführbar noch im Browser prüfbar.
`suggestions_found` zählt ihn mit; `cluster_key` bleibt bei ihm `None`. Der Doku-Block derselben
Funktion („Je Gruppe trägt das erste Foto keinen Vorschlag") wird dadurch falsch und ist mit
anzupassen.

### Was ausdrücklich nicht angefasst wird

Das Überlebens-Prädikat selbst, seine fünf SQL- und zwei Objekt-Aufrufstellen, die Asymmetrie aus
Auflage S3 der Spec 0374, die drei bestehenden Endpunkte in ihrer Wirkung,
`photo_duplicate_decisions`, die Duplikat-Erkennung, das Ausschuss-Gate und der Filter `suggested`.
ADR 0104 bleibt vollständig gültig.

### Betroffene Dateien

**Backend** — `duplicates.py` (`GroupStanding`, `group_standing`, `all_group_representative_ids`,
`effective_decision_for`, `keep_possible_for`; Wegfall von `DuplicateLink.decided` und
`open_group_representative_ids`, schlankeres `load_duplicate_links`); `api/photos.py`
(`DuplicateGroupPhotoOut`, `DuplicateGroupOut`, `build_duplicate_group_out`, Index-Endpunkt);
`demo_state.py`. `api/duplicate_decisions.py` ändert sich nicht — beide Schreibwege antworten über
denselben Builder.

**Frontend** — `api/types.ts`, `api/duplicates.ts`, `hooks/useDuplicates.ts`,
`components/DuplicatePhotoTile.tsx`, `pages/DuplicateComparePage.tsx`, `pages/PhotoGridPage.tsx`,
`pages/pipeline/AusschussStepPage.tsx`.

**Doku** — `docs/architecture.md` (Endpunktblock, Abschnitt zur Vergleichsansicht) und
`specs/architecture/0003-securitykonzept.md` (drei Stellen, siehe `## Security`) im selben Pull
Request.

### Reihenfolge der Umsetzung

1. `duplicates.py`: Wegfall von `decided`/`open_group_representative_ids`,
   `all_group_representative_ids`, `group_standing`. Zähler über alle Gruppen und Nachbarn sind eine
   Einheit — getrennt wäre `group_position` zwischendurch weder das eine noch das andere.
2. `duplicates.py`: `effective_decision_for` und `keep_possible_for` auf `_survives`, mit der
   Wahrheitstabelle als Parametrisierung und dem `score is None`-Fall.
3. `api/photos.py`: Antwortform (`effective_decision`, `keep_possible`, `previous_photo_id`,
   `next_photo_id`, Wegfall von `decision`). Danach sind die Fälle beider Schreibwege anzupassen —
   sie teilen den Builder.
4. Index-Endpunkt samt 401-Fall, `DOCUMENTED_ROUTES` und Gleichheit von `total` gegen den
   Gruppen-Endpunkt.
5. Demo-Bestand.
6. Frontend: Typen, Client, beide Hooks.
7. Kachel: zwei Zustände, `keep_possible === false` ohne Wahl.
8. Seite: Überschrift/Zähler, neuer Hinweistext, Vor/Zurück samt Zurücksetzen von
   `enlargedId`/`decidingIds` beim Ankerwechsel.
9. Die zwei Einstiege in `PhotoGridPage` und `AusschussStepPage`, jeweils mit Gegenprobe für
   `total === 0`.
10. `docs/architecture.md` und `specs/architecture/0003-securitykonzept.md` nachziehen.

## UI/UX

### Zustandsdarstellung (AK1, AK2, AK3)

Alle Aufnahmen einer Gruppe tragen beim Öffnen bereits einen Zustand — `keep` (Symbol, Akzentrahmen,
Beschriftung „Behalten") oder `discard` (Symbol, Danger-Rahmen, Beschriftung „Ausschuss"). **Keine
Darstellung nutzt Farbe als einziges Unterscheidungsmerkmal:** Das Zustandswort steht als sichtbarer
Text neben Symbol und Rahmen.

Bei `keep_possible === false` rendert die Kachel keine Wahlschaltflächen und zeigt stattdessen den
Ausschusszustand samt Grund. Das ist bewusst **nicht** `disabled`: „nicht anwendbar" ist etwas
anderes als „kurzzeitig gesperrt".

### Texte

- **`DUPLICATE_HINT_TEXT` (neu):** „Der angezeigte Zustand jeder Aufnahme gilt, falls du ihn nicht
  änderst." Er benennt einen bestehenden Zustand statt einer ausstehenden Entscheidung und sichert
  nichts über „unentschiedene" Aufnahmen zu (AK4).
- **Fester Text bei `keep_possible === false`:** „Abgelehnt wegen geringer Bildqualität — lässt sich
  nicht ändern." (AK3)

### Dämpfung

Die bisherige Dämpfung der Verlierer-Kacheln bleibt unverändert. Ihre Bedeutung verschiebt sich von
„entschieden vs. unentschieden" zu „nicht die behaltene Aufnahme"; zusammen mit dem
Rahmenunterschied fällt der Blick zuerst auf die ungedämpfte Aufnahme. `OPACITY_ALLOWLIST` bleibt
unverändert.

### Gruppennavigation und Überschrift (AK5, AK6)

Die Gruppennavigation liegt **im Seitenkopf neben der Überschrift und ist immer sichtbar** — sie ist
ausdrücklich nicht an die Bildvergrößerung gekoppelt. Am Rand ist die jeweilige Schaltfläche
`disabled`. Ihre zugänglichen Namen (`Zur vorherigen Gruppe` / `Zur nächsten Gruppe`) überschneiden
sich nicht mit den bestehenden `Vorherige/Nächste Aufnahme der Gruppe` der Vergrößerung.

Überschrift: „Duplikat-Gruppe N von Total" über alle Gruppen des Projekts.

### Einstiege (AK7, AK8)

- **Ausschuss-Schritt:** „Duplikate vergleichen" neben „Vorschläge ansehen", gleiche Button-Variante
  (Gleichrangigkeit), beide nebeneinander.
- **Fotoliste mit Filter „Vorschläge":** ein listenweiter Einstieg oberhalb des Kachelrasters. Sein
  zugänglicher Name unterscheidet sich vom kachelgenauen `Duplikate vergleichen: <Dateiname>`.
- Beide werden bei `total === 0` und während des Ladens **ausgeblendet**, nicht deaktiviert.

### Zustände, Responsivität, Barrierefreiheit

Ladend: Skeleton-Platzhalter mit `role="status"`. Fehler: bestehender Alert mit „Erneut
versuchen". Leer: bestehender `DUPLICATE_EMPTY_TEXT`. Raster und Vergrößerung bleiben wie heute
(zwei Spalten unter `sm`, drei ab `sm`; Vergrößerung spannt die volle Breite). Kacheln bleiben
`<ul>`/`<li>`; die Bildfläche bleibt ein natives `<button>`; Wahlschaltflächen tragen
`aria-pressed` gemäß `effective_decision`.

## Security

Sicherheitsrelevant, aber ohne neue Vertrauensgrenze: kein Secret, keine Umgebungsvariable, kein
externer Dienst, kein Freitext, kein neuer Empfängerkreis, keine Änderung an Authentifizierung oder
Datensichtbarkeit zwischen den beiden Nutzern. Relevant ist, dass die Ansicht ab hier über dasselbe
Prädikat spricht, das bestimmt, welche Bilder den Homeserver Richtung Cloud-Anbieter verlassen (ADR
0104). Die Auflagen S1–S11 der Spec 0374 gelten unverändert weiter; die folgenden treten daneben.

- **S1 — Der neue Lese-Endpunkt trägt seine Auth-Dependency ausgeschrieben und einen eigenen,
  pfadbenannten 401-Fall.** `GET /projects/{project_id}/duplicate-groups` liegt in `photos.router`,
  und der trägt bewusst keine router-weite `dependencies`-Liste und keinen Vollständigkeitstest
  (Auflage S8 der Spec 0374). Ein vergessener `current_user`-Parameter wäre dort still öffentlich —
  keine 401, nur Daten. `project_id` ist deklarativ begrenzt (`ge=1`, `le=MAX_QUERY_POSITION`) wie an
  den drei bestehenden Endpunkten; ein unbeschränkter `int` erreicht die Datenbank und wird jenseits
  von 2^63 zu `500` statt `404`. Die 401 steht vor jeder Aussage über das Projekt, und die Antwort
  spiegelt den übergebenen Wert nicht.

- **S2 — `effective_decision` und `keep_possible` ziehen das eine Prädikat, nie eine zweite
  Fassung.** Beide entstehen in `duplicates.py` über `_survives` (`keep_possible` mit einem
  hypothetischen `KEEP`), nie als ausgeschriebene Bedingung an der Aufrufstelle. Kein Eintrag in
  `_ERWARTETE_VERWENDUNGEN` oder `_PRAEDIKATSNAMEN` wird gesenkt oder entfernt, um den Wächter grün
  zu bekommen. Eine Ableitung im Frontend aus `PhotoOut.suggestion` ist untersagt (ADR 0111 Punkt 1)
  — jenes Feld fällt bei eigener Albumbewertung und bei getroffener Entscheidung auf `null`, und
  eine TypeScript-Fassung des Prädikats sieht der Wächter nicht, weil er nur `backend/src` liest.
  Bei Verletzung zeigt die Ansicht einen anderen Zustand, als der Ausschuss-Schritt anwendet, oder
  die vier cloud-bestimmenden Abfragen laufen von der Anzeige weg — beides ohne Fehler und ohne
  Meldung.

- **S3 — Ein Mitglied ohne `PhotoScore`-Zeile beantwortet beide Felder, statt die Antwort zu
  zerreißen.** Der Repräsentant braucht strukturell keine eigene Zeile, um referenziert zu werden;
  `load_duplicate_links` joint `PhotoScore` genau deshalb äußer. Ein `photo.score.suggested_status`
  an der Aufrufstelle wirft dort `AttributeError` und trifft nicht eine Kachel, sondern die gesamte
  Gruppenantwort und damit den einzigen Zugang zur Ansicht (`500`). Beide Felder laufen deshalb über
  die Fassung, die `score is None` kennt und zur zurückhaltenden Seite fällt.

- **S4 — Die Unterdrückung der Wahlschaltflächen bei `keep_possible === false` ist eine Anzeige-,
  keine Durchsetzungsmaßnahme.** Der Server nimmt einen trotzdem abgesetzten `keep`-Aufruf auf ein
  unveränderliches Mitglied unverändert entgegen: Er schreibt die Zeile, antwortet mit dem vollen
  Gruppenstand und nennt darin weiterhin `effective_decision = DISCARD` und `keep_possible = false`.
  Eine neue Zurückweisung (`409`/`422`) wäre eine zweite Regel neben ADR 0104 Punkt 3 und liefe dem
  gruppenweiten Schreibweg entgegen, der dieselbe Zeile für dasselbe Mitglied schreibt.

- **S5 — Der gruppenweite Schreibweg bleibt unangetastet (Auflage S6 der Spec 0374).** Die Menge
  bestimmt der Server aus dem Stern, geschrieben wird auf alle Mitglieder, das unveränderliche
  eingeschlossen; kein clientseitiges Herausfiltern, keine Id-Liste im Körper
  (`DuplicateDecisionIn` behält `extra="forbid"` und sein eines Feld). Eine Ausnahme für das
  unveränderliche Mitglied wäre eine zweite Mengendefinition neben der des Servers.

- **S6 — `first_photo_id`, `previous_photo_id` und `next_photo_id` stammen ausschließlich aus
  derselben projektbegrenzten Kantenliste.** Sie werden über `load_duplicate_links(session,
  project.id)` und die Repräsentantenordnung gebildet, nie über eine eigene Abfrage auf
  `photo_scores` — dessen `duplicate_of` zeigt auf `photos.id` ohne Projektbedingung. Keine der drei
  Ids ist eine Zugriffsmarke: Die Folgeanfrage läuft erneut über `project_id` und löst eine fremde Id
  nicht auf (`404`). Ohne die Bindung nennt die Antwort dagegen Foto-Ids fremder Projekte, und der
  Durchgang endet an einer Gruppe, die es in diesem Projekt nicht gibt.

- **S7 — `DUPLICATE_CONSEQUENCE_TEXT` bleibt wortgleich und an der Handlung sichtbar (Auflage S4 der
  Spec 0374).** Er trägt die Folge von „behalten" für den Datenabfluss. Der Umbau der Ansicht darf
  ihn weder umformulieren noch hinter das Blättern oder einen eingeklappten Bereich schieben; sonst
  entscheidet der Nutzer über einen Abfluss, von dem er nichts weiß.

**Geprüft und ohne Befund:** `keep_possible === false` macht die Ableitung „wegen Unschärfe
abgelehnt" auch dort sichtbar, wo `PhotoOut.suggestion` bereits unterdrückt ist — der Empfängerkreis
bleibt jedoch derselbe authentifizierte Nutzerkreis, der `sharpness`/`exposure` ohnehin roh liest,
und nichts davon verlässt den Homeserver. Der neue Endpunkt schafft keine neue Aufzählbarkeit: Beide
Nutzer sehen alle Projekte, ein unbekanntes Projekt ist `404`, die 401 greift davor. Kein neuer
XSS-Sink (beide neuen Felder sind Aufzählungswert und Bool, der feste Text ist ein Literal der
Oberfläche). Die Cache-Schlüssel-Auflage S10 der Spec 0374 gilt für den neuen Endpunkt nicht — seine
Antwort trägt kein `PhotoOut` und ist keine Funktion des anfragenden Nutzers.

**`specs/architecture/0003-securitykonzept.md` wird im selben Pull Request an drei Stellen
ergänzt:** ein neuer Abschnitt unter „Angriffsflächen" mit S1–S7 in verkürzter Form und dem Vermerk,
dass ADR 0104 gelesen und nicht geändert wird; die Ankerzeile zum Ausschuss-Überlebenden-Prädikat um
die neuen Anzeige-Aufrufstellen und die Zusage „kein Eintrag wird gesenkt"; die Ankerzeile zum
Auth-Torwächter je Endpunkt um den neuen Index-Endpunkt mit seinem eigenen 401-Fall.

## Teststrategie

**Ebenen:** Backend-Unit (`duplicates.py`, reine Funktionen), Backend-Integration (beide Endpunkte
über `authenticated_api_client`), Frontend-Unit (`vitest`/Testing Library). **Kein neuer E2E-Spec** —
jede Zusage dieser Story ist in jsdom ausdrückbar.

- **Wahrheitstabelle** für `effective_decision_for`/`keep_possible_for` (Unit, ohne DB): 3 × 2 × 3
  Zeilen über `suggested_status ∈ {None, ALBUM_WORTHY, REJECTED}` × `duplicate_of ∈ {None, gesetzt}`
  × gespeicherte Entscheidung ∈ {keine, keep, discard}, Erwartung aus einer in Prosa
  ausgeschriebenen Funktion, nicht aus einer zweiten Verzweigungsfassung. Tragend sind die Zeilen,
  in denen die Auswertung vom Rohwert abweicht: keine Entscheidung + `duplicate_of` gesetzt +
  `REJECTED` → `discard` (AK1-Kern); keine Entscheidung + beides `NULL` → `keep`; gespeichertes
  `keep` + `duplicate_of NULL` + `REJECTED` → `discard` (AK3). `keep_possible` ist `false` genau in
  den sechs Zeilen `duplicate_of IS NULL ∧ suggested_status IS NOT NULL`, unabhängig von der
  gespeicherten Entscheidung. Zusätzliche Zeile: Mitglied **ohne `PhotoScore`** → `keep` / `true`.
- **`group_standing`** (Unit): Reihenfolge über eine vollständige Id-Folge; eine einzige Gruppe ⇒
  `previous_id`/`next_id` beide `None` bei `(1, 1)`; unbekannter Repräsentant ⇒ `None`. Dazu der
  **Kettendurchlauf** von der ersten Gruppe `next_id` folgend bis `None`: Die besuchte Folge gleicht
  der geordneten Repräsentantenliste, die Positionen sind `1..total`, und eine **vollständig
  entschiedene** Gruppe liegt mitten in der Kette (AK5).
- **Stabilität (AK6, Integration):** Drei Gruppen; Gruppe 2 lesen, Gruppe 1 über den gruppenweiten
  Schreibweg vollständig entscheiden, Gruppe 2 erneut lesen — `(position, total)` als Gleichheit
  zweier Beobachtungen, nicht gegen ein Literal. Danach bleibt Gruppe 1 über `previous_photo_id` und
  über `first_photo_id` erreichbar.
- **Index-Endpunkt (Integration):** eigener pfadbenannter 401-Fall; `total === 0` mit
  `first_photo_id is None`; Gleichheit von `total` zwischen Index und `DuplicateGroupOut` über
  demselben Bestand, mit Gegenprobe gegen die selbsterfüllende Variante (beide null);
  `first_photo_id` wird nicht gegen eine abgeschriebene Id geprüft, sondern über den Abruf (die
  Gruppe dazu hat `position == 1` und `previous_photo_id is None`).
- **Antwortform (Integration):** Feldmengen als Gleichheit — `{"photo", "effective_decision",
  "keep_possible"}` und `{"items", "position", "total", "previous_photo_id", "next_photo_id"}`. Das
  ist zugleich der Wächter dagegen, dass der Rohwert später als Zusatzfeld wieder mitreist.
- **Auflage S5 × AK3 (Integration):** „Alle behalten" auf eine Gruppe mit einem unveränderlichen
  Mitglied — danach steht auf allen Mitgliedern eine `keep`-Zeile, das unveränderliche zeigt aber
  weiterhin `discard` / `keep_possible = false`. Ohne diesen Fall wäre ein Schreibweg, der das
  Mitglied auslässt, von einem, der es einschließt, nicht zu unterscheiden.
- **Äquivalenz** `keep_possible is False ⟺ _suggestion_reason(score) == "low_quality"`, eingeschränkt
  auf Aufnahmen mit `suggested_status IS NOT NULL` (ohne Vorschlag ist die Grundfrage nicht gestellt,
  und über dem vollen Bestand ist die Aussage falsch), mit Gegenprobe gegen beide leeren Seiten.
- **Grund-Wächter:** eine Zusicherung, dass der Ausschuss-Lauf in `suggested_status` nur
  `None`/`REJECTED` schreibt. `RatingStatus` kennt `ALBUM_WORTHY`; trüge ein Repräsentant den, wäre
  `keep_possible === false` bei falschem Begründungstext.
- **Frontend Kachel:** Schlüsselmenge von `ZUSTAENDE` ist exakt `{keep, discard}`;
  `data-duplicate-decision` trägt genau diese zwei Werte, paarweise verschiedener Text und
  verschiedenes Symbol; `aria-pressed` folgt `effective_decision`. Bei `keep_possible === false` ist
  die **Anzahl** der Bedienelemente der Kachel 1 (nur die Bildfläche) — über die Zahl, nie über
  `queryByRole(name)`, das gegen ein umbenanntes Label blind ist —, plus Gegenprobe mit 3 im anderen
  Fall und dem sichtbaren Grundtext.
- **Frontend Seite:** Überschrift „Duplikat-Gruppe N von Total"; Gruppennavigation ohne jede
  Vergrößerung sichtbar; `disabled` genau dann, wenn der Nachbarwert `null` ist; Navigation als Push;
  Zielpfad `/projects/:id/photos/:nextId/duplicates`. **Rücksetzung beim Ankerwechsel in zwei
  getrennten Fällen:** (1) Kachel vergrößern → Gruppe wechseln → kein `verkleinern`-Element mehr;
  (2) eine nie auflösende Entscheidung starten → Gruppe wechseln → keine Kachel der neuen Gruppe ist
  gesperrt. Getrennt, weil eine Rücksetzung leicht nur einen der beiden Zustände erfasst. Neuer
  `DUPLICATE_HINT_TEXT`: Vorhandensein plus negative Zusagen (kein „bleibt/erhalten/noch
  nicht/offen").
- **Frontend Einstiege:** je Einstieg drei Fälle (vorhanden mit korrektem Ziel auf `first_photo_id`;
  nicht gerendert bei `total === 0`; nicht gerendert während des Ladens). Am Ausschuss-Schritt
  zusätzlich: beide Wege stehen nebeneinander. In der Fotoliste: der listenweite Weg genau einmal,
  der Kachel-Weg unverändert.

**Coverage (≥ 80 %):** unkritisch; zu beachten sind nur die beiden sonst ungetesteten Zweige
`first_photo_id is None` und der 401-Pfad des neuen Endpunkts, beide oben als Pflichtfälle geführt.

### Bestandstests, die bewusst falsch werden

Diese Tests sind heute grün und werden durch das Aufheben von AK2/AK6/AK10 der Spec 0374 falsch. Sie
dürfen umgeschrieben oder entfernt werden; wer sie für eine Regression hält, hat die Story verfehlt.
„Nur mechanisch" heißt: Aussage bleibt, Name/Feld/Funktion ändert sich.

**`backend/tests/test_duplicates.py`** —
`test_a_group_whose_every_member_is_decided_drops_out_of_the_reference_set` (falsch, ersatzlos
entfernen; Ersatz: eine vollständig entschiedene Gruppe **bleibt** in der Liste);
`test_a_single_undecided_member_keeps_its_whole_group_open` (falsch, geht im Ersatz auf);
`test_the_viewed_group_keeps_its_place_even_after_it_has_been_finished` (falsch in Werten und
Begründung: bisher `(1, 2)`/`(1, 1)`, neu `(1, 2)`/`(2, 2)`);
`test_the_counter_is_one_based_and_names_the_place_among_the_open_groups` (Werte bleiben, Name und
Docstring falsch); `test_the_groups_are_ordered_by_the_earliest_taken_at_of_their_members`,
`test_a_tie_between_two_groups_is_broken_by_the_representative_id`,
`test_the_position_of_an_unknown_representative_is_none` (nur mechanisch); Hilfsfunktion
`_link(..., decided=...)` und jeder Aufruf (`DuplicateLink.decided` entfällt).

**`backend/tests/test_api_duplicate_groups.py`** — `test_each_item_carries_its_own_decision_or_null`
(falsch, es gibt kein `null` mehr; neue Erwartung: das bisher „offene" Mitglied → `discard`, der
AK1-Kern); `test_a_finished_group_drops_out_of_the_reference_set_of_the_others` (falsch; neu offene
Gruppe `(2, 2)`, fertige `(1, 2)`); `test_the_item_carries_an_unextended_photo_out` (falsch in
beiden Feldmengen; die Gleichheit von `PhotoOut` gegen die Fotoliste bleibt richtig);
`test_the_counter_is_one_based_over_the_open_groups` (Werte bleiben, Name und Begründung falsch).

**`backend/tests/test_api_duplicate_decisions.py`** — nur mechanisch (`item["decision"]` →
`item["effective_decision"]`) in `test_a_single_decision_is_written_and_answered_in_the_group_form`,
`test_the_group_write_path_sets_every_member_in_one_call`,
`test_a_decision_survives_an_unchanged_rescoring`.
`test_both_write_paths_answer_in_the_same_form_as_the_read_path` bleibt unverändert gültig und wird
zum Wächter dafür, dass beide Schreibwege die Nachbar-Ids mitliefern.

**`backend/tests/test_demo_state.py`** —
`test_the_duplicate_project_holds_two_reachable_groups` (falsch: behauptet für jeden Repräsentanten
`duplicate_of is None` **und** `suggested_status is None`; Gruppe 2 bricht die zweite Hälfte
bewusst). `test_the_duplicate_project_leaves_every_group_undecided` bleibt gültig und wird nicht
angefasst.

**`backend/tests/test_ausschuss_ueberlebende.py`** — nicht anfassen. Schlägt
`test_no_source_file_writes_the_survivor_condition_by_hand` an, weil `keep_possible` in
`api/photos.py` ausgeschrieben wurde, ist das ein echter Fund, kein anzupassender Test.

**`frontend/src/api/duplicates.test.ts`** — `kennt keinen Weg zurueck nach "noch nicht entschieden"`
wird rot, sobald `getDuplicateGroupIndex` exportiert wird (die Sollmenge der Modul-Exporte ist
ausgeschrieben): Liste auf vier Einträge erweitern, nicht aufweichen. `GROUP`-Fixture braucht die
Nachbar-Ids.

**`frontend/src/components/DuplicatePhotoTile.test.tsx`** —
`traegt je Zustand einen eigenen Wert, Text und Symbol - paarweise verschieden` (falsch: drei
Zustände → zwei); `bietet KEINE Ruecknahme nach "noch nicht entschieden"` (formal weiter grün, Name
und Begründung falsch; umwidmen zu „genau zwei Wahlschaltflächen, solange `keep_possible`");
`nennt den Dateinamen in JEDEM zugaenglichen Namen der Kachel` (`toHaveLength(3)` ist jetzt
datenlageabhängig, braucht den zweiten Fall mit 1); `renderTile` und jeder `decision:`-Aufruf (Props
`effectiveDecision`/`keepPossible`); die Dämpfungs- und `aria-pressed`-Fälle nur mechanisch.

**`frontend/src/pages/DuplicateComparePage.test.tsx`** — `group()`-Helfer (trägt `decision: null`
und keine Nachbar-Ids, strukturell in jedem Fall der Datei);
`traegt eine unveraenderliche Hinweiszeile, die den Vorschlag des Systems nennt` (falsch, der neue
Text nennt keinen „Vorschlag des Systems"; Negativprüfung auf AK4 erweitern). Der Block
`die Vergroesserung` bleibt gültig, ist aber durch Label-Kollision gefährdet (siehe AK7).

**`frontend/src/pages/PhotoGridPage.test.tsx`** — `zeigt ihn NICHT bei %s` muss **verschärft**
werden: `queryByRole('link', { name: /Duplikate vergleichen/ })` greift auch den neuen listenweiten
Einstieg ab und ist heute nur grün, weil `renderPage()` ohne `?filter=suggested` läuft. Auf das
kachelgenaue Label einengen.

**`backend/tests/test_openapi_beschreibungen.py`** — Pflichteintrag in `DOCUMENTED_ROUTES` für
`("get", "/projects/{project_id}/duplicate-groups")`.

**`e2e/`** — `lib/demo.ts::openDuplicateGroup` wählt über `einstiege.last()` auf
`/^Duplikate vergleichen:/` und bleibt grün, solange der listenweite Einstieg dieses Muster nicht
trifft (AK7). `tests/tap-targets.spec.ts::EXPECTED_CONTROL_COUNT` wird um die beiden
Gruppennavigations-Schaltflächen erhöht — sie sind der heiße Pfad dieser Story, und ohne Aufnahme
fehlt der einzige Nachweis der 44-px-Zusage für sie.

Das Testkonzept `specs/architecture/0002-testkonzept.md` ist um die fünf verallgemeinerbaren Muster
dieser Story ergänzt.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR 0111 angelegt; die Ansicht zeigt das Überlebens-Prädikat
  statt der Entscheidungszeile.
- `ux-ui-designer` konsultiert (Schritt 2): Hinweistext, Grundtext, Dämpfung unverändert.
- `test-engineer` konsultiert (Schritt 3): Wahrheitstabelle, Kettendurchlauf, Liste der bewusst
  falsch werdenden Bestandstests; Testkonzept ergänzt.
- `security-engineer` konsultiert (Schritt 3): sicherheitsrelevant, sieben Auflagen S1–S7;
  Sicherheitskonzept im Umsetzungs-PR an drei Stellen zu ergänzen.
- **Gruppennavigation im Seitenkopf statt in der Vergrößerungssteuerung** — vom Spec-Autor
  entschieden: Der UI/UX-Entwurf hatte sie an die `controls` der vergrößerten Aufnahme gehängt; AK5
  verlangt sie aus der Ansicht heraus, also unabhängig von der Vergrößerung.
- **`_ERWARTETE_VERWENDUNGEN` bleibt unberührt** — vom Spec-Autor zwischen Architektur- und
  Security-Fassung aufgelöst: Die neuen Funktionen liegen in `duplicates.py` und rufen intern
  `_survives`, in `api/photos.py` kommt kein Aufruf einer benannten Prädikatsfunktion dazu. Die in
  beiden Fassungen tragende Zusage steht als Auflage S2: kein Eintrag wird gesenkt oder entfernt, um
  den Wächter grün zu bekommen.
- **Keine Delegation an `survives_ausschuss_for`** — es bildet den inneren Join nach und lieferte
  für ein Mitglied ohne `PhotoScore`-Zeile `False`.

## Offene Fragen

Keine.

## Out of Scope

- Die Wirkung der Entscheidungen auf den weiterlaufenden Bestand: „Ausschuss" bleibt unbedingt
  wirksam, „behalten" nur gegenüber der Duplikatablehnung.
- Die Duplikat-Erkennung selbst (welche Aufnahmen eine Gruppe bilden und welche das System wählt).
- Ein Weg, eine Entscheidung auf „noch nicht entschieden" zurückzunehmen.
- Ein Gruppenindex in der Route.
