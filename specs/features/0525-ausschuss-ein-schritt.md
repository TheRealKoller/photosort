# 0525 - Der Ausschuss wird ein Schritt: Übersicht, Detailansicht, Sammelbestätigung

**Status:** Accepted
**Erstellt:** 2026-09-23
**Bezug:** [Issue #525](https://github.com/TheRealKoller/photosort/issues/525), ADR
[`0121`](../decisions/0121-der-ausschuss-wird-ein-schritt-uebersicht-detail-und-abschluss-aktion.md),
ADR [`0104`](../decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md), ADR
[`0111`](../decisions/0111-vergleichsansicht-zeigt-das-praedikat-nicht-die-entscheidungszeile.md),
Specs [`0374`](./0374-duplikate-vergleichen.md), [`0486`](./0486-duplikate-durchgehen.md).

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Der Abschnitt `## Abgelöste Zusagen`
muss die Zusagen der Vorgänger-Specs namentlich führen — ohne diese Liste hält der Umsetzungslauf
einen bewusst umgeschriebenen Test für eine Regression —, und `## Security` trägt zehn Auflagen in
der geschützten Dreiteilung.

## Ziel

Der Ausschuss-Schritt besteht heute aus zwei Karten und einem Umweg: erst die Ausschuss-Erkennung
anstoßen, dann im Ausschuss-Gate in die normale Fotoansicht wechseln, dort Kachel für Kachel
übernehmen und bei Duplikaten auf eine separate Vergleichsseite springen. Was ein Bild in den
Ausschuss gebracht hat, steht nirgends.

Ziel ist ein einziger Schritt: Erkennung, Sichtung und Bestätigung werden eins. Danach steht eine
eigene Übersicht aller Ausschussbilder, in der jedes Bild seinen Grund sichtbar trägt. Ein Klick
öffnet eine Detailansicht mit dem Bild in groß, in der man dem Vorschlag zustimmen oder ihn aufheben
kann — bei Duplikaten mit der zugehörigen Duplikatgruppe direkt daneben. Ein Bestätigungsbutton in
der Übersicht übernimmt alle zu diesem Zeitpunkt offenen Vorschläge in einem Zug, manuelle
Änderungen eingeschlossen. Der Schritt bleibt danach jederzeit erneut aufrufbar und bestätigbar,
Anpassungen sind später möglich. Übersicht und Detailansicht werden neu gestaltet.

## User Story

Als Nutzer möchte ich den Ausschuss an einer Stelle sehen, nach Gründen unterscheiden, jedes Bild
groß prüfen und alle offenen Vorschläge mit einem Griff übernehmen können, damit das Aussortieren
ein zusammenhängender, jederzeit wiederholbarer Schritt wird statt eines Umwegs über mehrere
Ansichten.

## Akzeptanzkriterien

- [ ] **AK1 — Ein Schritt statt zwei Karten.** Erkennung und Gate sind ein einziger Pipeline-Schritt;
      die bisher getrennte Karte für die Erkennung und die für das Gate entfallen. `StepId` umfasst
      nur noch `scan | ausschuss | kriterien | kuratierung`; der Stepper zeigt vier Schritte.
- [ ] **AK2 — Erkennen und blicken in einem.** Der Schritt stößt das Aussortieren an und führt danach
      unmittelbar in die Übersicht der Ausschussbilder — ohne Umweg über die normale Fotoansicht.
- [ ] **AK3 — Die Übersicht ist eigene Ansicht.** Die Übersicht zeigt alle Ausschussbilder als eigene
      Ansicht statt als Filter der Fotoliste.
- [ ] **AK4 — Der Grund ist sichtbar und unterscheidbar.** Bei jedem Bild ist der Grund der
      Markierung deutlich erkennbar, und die Gründe sind voneinander unterscheidbar (Duplikat gegen
      geringe Qualität), nicht nur ein Sammelzustand. Der Grund kommt als eigenes Feld vom Server
      (`reason`) und ist `duplicate` genau dann, wenn `PhotoScore.duplicate_of IS NOT NULL`, sonst
      `low_quality` — dieselbe Ableitung wie `api/photos.py::_suggestion_reason`, keine zweite.
- [ ] **AK5 — Klick öffnet das Großbild.** Ein Klick auf ein Bild öffnet eine Detailansicht mit dem
      Bild in groß.
- [ ] **AK6 — Zustimmen und Aufheben wirken sofort.** In der Detailansicht kann dem Vorschlag
      zugestimmt oder er aufgehoben werden; beides wirkt unmittelbar auf den Zustand des Bildes.
      „Aufheben" (`keep`) gibt es nur, wo `duplicates.py::keep_possible_for` wahr ist — bei einer
      Ablehnung wegen geringer Qualität (kein Duplikat) erscheint es nicht; dort ist die einzige
      mögliche Handlung „zustimmen" (`discard`). Das ist gelesene Asymmetrie aus ADR 0104 Punkt 3,
      keine neue Regel.
- [ ] **AK7 — Schließen verliert nichts.** Das Schließen der Detailansicht führt zurück in die
      Übersicht, ohne den Sichtungsfortschritt zu verlieren (geladene Seiten und gesetzte
      Kennzeichen bleiben).
- [ ] **AK8 — Duplikatgruppe in derselben Ansicht.** Ist ein Bild wegen eines Duplikats im Ausschuss,
      zeigt die Detailansicht zusätzlich die zugehörige Duplikatgruppe zur Entscheidung — kein
      separater Seitenwechsel. Die Gruppe kommt aus dem bestehenden
      `GET /projects/{id}/duplicate-groups/{photo_id}`; ist sie nicht (mehr) vorhanden (`404`), zeigt
      die Detailansicht einen leeren Gruppenbereich statt eines Fehlers.
- [ ] **AK9 — Eine Sammelbestätigung.** Die Übersicht trägt einen Bestätigungsbutton; ein Klick
      übernimmt alle zu diesem Zeitpunkt offenen Vorschläge in einem Zug. Die Menge bestimmt der
      **Server** (keine Id-Liste im Body); ein zweiter Aufruf ist idempotent.
- [ ] **AK10 — Manuell geänderte bleiben unangetastet.** Bereits manuell geänderte Bilder bleiben bei
      der Übernahme unangetastet und werden so übernommen, wie sie sind. Das leistet die
      Auswahlbedingung `duplicates.py::has_open_suggestion` („wer eine Entscheidungszeile trägt, ist
      kein offener Vorschlag"), nicht eine Nachfilterung.
- [ ] **AK11 — Erneut aufrufbar.** Nach der Bestätigung bleibt der Schritt erneut aufrufbar; weitere
      Anpassungen sind möglich, und es kann erneut bestätigt werden.
- [ ] **AK12 — Eine Abschluss-Aktion, keine Einzelpflicht.** Die Bestätigung bleibt eine einzige
      Abschluss-Aktion in der Übersicht. Eine Pflicht, jedes Bild einzeln zu bestätigen, entsteht
      nicht — die Einzeländerung in der Detailansicht ist möglich, aber keine Bedingung.
- [ ] **AK13 — Der nächste Schritt hängt an der Bestätigung.** Die Freigabe des nächsten Schritts
      hängt weiterhin an der Bestätigung: `kriterien.isReachable` bleibt
      `category_selection_enabled && gate_confirmed_at !== null`.
- [ ] **AK14 — Alle Zustände vollständig.** Der Schritt ist in allen Zuständen vollständig: noch nicht
      gelaufen, läuft (Fortschritt), fehlgeschlagen, ladend, Fehler, leer (kein Ausschuss gefunden /
      automatisch übersprungen) bleiben sichtbar nachvollziehbar.
- [ ] **AK15 — Neu gestaltet nach Design-System.** Übersicht und Detailansicht sind neu gestaltet und
      folgen dem Design-System (`specs/architecture/0004-design-system.md`) und der Design-Nutzlast
      (`design/penpot/views.json`, Schlüssel `ausschuss`).
- [ ] **AK16 — Abgelöste Zusagen benannt.** Die Zusagen, die diese Überarbeitung ablöst, sind
      ausdrücklich benannt (siehe `## Abgelöste Zusagen`) und werden nicht stillschweigend ungültig.

## Abgelöste Zusagen

Diese Zusagen gelten ab dieser Spec **nicht mehr**. Wer die Umsetzung prüft, hält die daran
gebundenen Tests für bewusst umgeschrieben, nicht für Regressionen.

- **ADR 0104, Folge-Notiz** „Form und Bedienung des Gates — eine Liste, eine Abschluss-Aktion, keine
  Einzelbestätigungspflicht — bleiben unberührt": Die **Form** (Liste im Gate-Modus der Fotoliste)
  und die **Bedienung** lösen sich ab. „Keine Einzelbestätigungspflicht" und „eine Abschluss-Aktion"
  gelten unverändert weiter. Ebenso löst sich die Aufzählung der Schreibwege („einen Endpunkt je
  Aufnahme und einen je Gruppe") ab, soweit der Einzel-Schreibweg jetzt auch Unschärfe-Ablehnungen
  annimmt.
- **Spec 0486, AK7**, soweit er den Einstieg „Duplikate vergleichen" **aus dem Ausschuss-Schritt**
  heraus trägt: Dieser Einstieg entfällt. Der listenweite Einstieg in der nach Vorschlägen
  gefilterten **Fotoliste** und der kachelgenaue Einstieg (im Gate-Modus) waren gate-gebunden bzw.
  listenweit; der listenweite Einstieg der Fotoliste bleibt, der kachelgenaue entfällt mit dem
  Gate-Modus (siehe unten).
- **Spec 0037 / Spec 0042**: der `?gate=1`-Modus der `PhotoGridPage` samt „Ausschuss gesichtet,
  weiter"-Button, die `GateStepPage` und die Zusage „fünf Schritte, darunter ein eigener
  Ausschuss-Gate".
- **Spec 0489 AK12 / Daniels Entscheidung vom 2026-09-14**, dass „Übernehmen" und „Vergleichen" nur
  im Gate-Modus unter der Kachel stehen: Mit dem Gate-Modus entfallen beide Kachel-Aktionen.
- **Spec 0375 / Spec 0358**: der Wortlaut „Weiter: Ausschuss-Gate" und der Eintrag `gate` in
  `RUN_FIELD_BY_STEP`/`getBlockedReason`.

**Unberührt bleiben** ADR 0104 Punkte 1–3 (der Stern über `PhotoScore.duplicate_of`, das
projektweite Datum ohne `user_id`, das Überlebenden-Prädikat samt Asymmetrie und Sicherheitsauflage),
ADR 0111 Punkt 1, die übrigen Akzeptanzkriterien der Spec 0486, die Sicherheitsauflagen S1–S11 der
Spec 0374, `DUPLICATE_CONSEQUENCE_TEXT` und die Duplikat-Erkennung selbst.

## Datenmodell-Bezug

**Keine Migration, keine neue Spalte, keine Änderung an `photo_duplicate_decisions`.** Betroffen sind
eine neue Antwortform (`AusschussEntryOut` samt Liste), die Semantik des bestehenden
`POST /{id}/confirm-ausschuss-gate` (die Menge wird serverseitig geschrieben), die erweiterte
Vorbedingung des bestehenden Einzel-Schreibwegs und das Frontend-Schrittmodell. Die
Endpunktübersicht in [`docs/architecture.md`](../../docs/architecture.md) wird im selben Pull Request
nachgezogen.

## Architektur / Umsetzung

**Grundlage:** ADR [`0121`](../decisions/0121-der-ausschuss-wird-ein-schritt-uebersicht-detail-und-abschluss-aktion.md).

Ein Lese-Endpunkt trägt die Übersicht, ein Query-Parameter derselben Schritt-Route die Detailansicht,
ein projektweiter Schreibweg den Abschluss, ein erweiterter Einzel-Schreibweg die Entscheidung am
Bild. Es wird **kein** neues Datenmodell-Feld eingeführt: der Schritt hängt weiter an
`ScoringRun.gate_confirmed_at`, die Übersicht an `PhotoScore.suggested_status` und
`photo_duplicate_decisions`.

### Backend

1. **Neuer Lese-Endpunkt** `GET /projects/{project_id}/ausschuss` in `api/photos.py` (dort liegt
   bereits der Gruppen-Index aus Spec 0486). Antwortmodell `AusschussOut { items: [AusschussEntryOut],
   total: int, open_count: int }` und `AusschussEntryOut { photo: PhotoOut, reason: "duplicate" |
   "low_quality", decision: "keep" | "discard" | null, group_anchor_photo_id: int | null }`.

   - **Bestand (projektweit):** jede Aufnahme mit `PhotoScore.suggested_status IS NOT NULL` **oder**
     einer Zeile in `photo_duplicate_decisions` — offen, angenommen und aufgehoben zusammen. Der
     Bestand wird in **einer** Anweisung mit ausgeschriebener Projektbindung gebildet (siehe
     `## Security`, S1/S6).
   - **`reason`** über die vorhandene `_suggestion_reason`; **`group_anchor_photo_id`** über
     `duplicates.py::representative_of` auf `load_duplicate_links` (`null`, wenn keine Gruppe).
   - **`decision`** ist der **gespeicherte Zeilenwert** (`photo_duplicate_decisions`), ausdrücklich
     nicht die Auswertung `effective_decision_for`: Die Übersicht zeigt den Sichtungsfortschritt, und
     ein unwirksames `keep` (Unschärfe-Ablehnung ohne Gruppe) bleibt als gespeicherte Handlung
     sichtbar. Die Detailansicht zieht dieselbe Größe, damit Übersicht und Detail über denselben
     Bildzustand sprechen.
   - **`open_count`** ist projektweit die Anzahl der Aufnahmen mit **offenem Vorschlag**
     (`duplicates.py::has_open_suggestion`) — unabhängig von `limit`/`offset`. Der Bestätigungsbutton
     nennt genau diese Zahl.
   - **Paginierung** wie die Fotoliste: `limit` (Vorgabe 60, `ge=1, le=200`), `offset` (`ge=0`),
     Reihenfolge `Photo.taken_at, Photo.id`, `total` = Größe des Gesamtbestands.
   - **`photo_id`-Filter für die Detailansicht:** ein optionaler Query-Parameter
     (`ge=1, le=MAX_QUERY_POSITION`). Ist er gesetzt, liefert `items` **genau den passenden Eintrag
     oder eine leere Liste**; `total`/`open_count` bleiben projektweit, `limit`/`offset` sind in
     diesem Zweig ohne Wirkung (Muster: der Alternativ-Zweig der Fotoliste, Spec 0374 S4/S14). Damit
     ist der Deep-Link `?photo=<id>` auch für eine Aufnahme außerhalb der geladenen Seite definiert:
     nicht im Ausschuss-Bestand ⇒ leere Liste ⇒ benannter „nicht (mehr) im Ausschuss"-Zustand mit
     Rückweg, **kein** stiller leerer Screen.
   - **Auth:** `photos.router` trägt **keine** router-weite `dependencies`-Liste; der Endpunkt trägt
     seine Dependency **ausgeschrieben** (`current_user`) und bekommt einen eigenen, pfadbenannten
     `401`-Fall sowie einen Eintrag in
     `tests/test_openapi_beschreibungen.py::DOCUMENTED_ROUTES`.

2. **Abschluss-Schreibweg** `POST /projects/{id}/confirm-ausschuss-gate` (`api/projects.py`) wird
   erweitert: In **einer** Transaktion schreibt er für jede Aufnahme mit
   `duplicates.py::has_open_suggestion` (projektweit, in einer Anweisung) die Zeile `discard` und
   setzt danach `gate_confirmed_at`, falls es leer ist. Der Body bleibt leer (keine Id-Liste). Der
   Vorbedingungs-`409` ohne erfolgreichen `ScoringRun` bleibt unverändert, ebenso die Idempotenz.

3. **Einzel-Schreibweg** `PUT /projects/{id}/photos/{photo_id}/duplicate-decision`
   (`api/duplicate_decisions.py`, bestehend) erweitert seine Vorbedingung von „hat Duplikat-Gruppe"
   auf „hat Gruppe **oder** offenen Vorschlag", projektgebunden wie bisher. Die Antwort bleibt die
   Gruppe; für eine Aufnahme **ohne** Gruppe ist sie der leere Stand (`position = 0`, `total = 0`,
   `previous_photo_id = null`, `next_photo_id = null`, `items = []`). `409` bleibt unverändert. Die
   Anzeige bietet „aufheben" dort nicht an, wo `keep_possible_for` falsch ist; der Server weist einen
   trotzdem abgesetzten `keep` **nicht** ab (Auflage S4 der Spec 0486 gilt unverändert — siehe
   `## Security`, S10).

### Frontend

4. **Schrittmodell** (`utils/pipelineSteps.ts`): `StepId = 'scan' | 'ausschuss' | 'kriterien' |
   'kuratierung'`; `PIPELINE_STEPS` verliert `gate` (Label „Ausschuss"); `ausschuss.isDone =
   gate_confirmed_at !== null`, `isReachable = true`; `kriterien.isReachable` unverändert;
   `RUN_FIELD_BY_STEP` verliert `gate`; der `gate`-Zweig in `getBlockedReason` entfällt, der
   `kriterien`-Text bleibt Wort für Wort „Bestätige zuerst den Ausschuss oben.". `PipelineStepView`
   verliert `GateStepPage`; `GateStepPage.tsx` entfällt. Die beiden wörtlichen „von 5"-Stellen in
   `Stepper.tsx` (Orientierungszeile und zugänglicher Name) ziehen auf „von 4" nach.

5. **`AusschussStepPage.tsx`** trägt alles: Trigger + Zustände (noch nicht gelaufen / läuft mit
   Fortschritt / fehlgeschlagen / success) wie heute, darunter bei `success` die **Übersicht** der
   Ausschussbilder. Ist `?photo=<id>` gesetzt, rendert dieselbe Seite die **Detailansicht** statt der
   Übersicht (kein Dialog, kein Seitenwechsel): Großbild (`PhotoImage`, Variante `display`), darunter
   die Entscheidungszeile, bei `reason === 'duplicate'` zusätzlich die Duplikatgruppe über den
   bestehenden `useDuplicateGroupQuery`. Die Detailansicht liest ihren Eintrag über den
   `photo_id`-Filter des Ausschuss-Endpunkts; die Gruppe wird über den bestehenden
   `useDuplicateDecisionMutation`/`useDuplicateGroupDecisionMutation` entschieden. Erfolg der
   Zusatzabfrage und der Entscheidungen invalidiert den Ausschuss-Query-Key.

6. **Übersicht:** Kachelraster wie die Fotoliste (gerechnete Zeilen), je Kachel Dateiname,
   Grund-Kennzeichen und Entscheidungszustand. Neue API-Schicht `frontend/src/api/ausschuss.ts` und
   Hook `useAusschussQuery` unter dem Query-Key-Präfix `['photos', projectId, …]`, damit die
   bestehenden Entscheidungs-Mutationen die Übersicht mit invalidieren. Bestätigung über den
   bestehenden `useConfirmAusschussGateMutation`.

7. **Rückbau** (`pages/PhotoGridPage.tsx`): der `?gate=1`-Modus, sein Bestätigungsaufruf
   (`handleConfirmGate`) und die daran gebundenen Kachel-Aktionen „Übernehmen"/„Vergleichen"
   entfallen ersatzlos. Der listenweite Einstieg „Duplikate vergleichen" (abhängig nur von
   `filterParam === 'suggested'` und `first_photo_id !== null`) **bleibt** — die `DuplicateComparePage`
   bleibt damit erreichbar und wird von dieser Story nicht entfernt.

### Doku und E2E

8. **`docs/architecture.md`** (Endpunktblock, geänderte Semantik von `confirm-ausschuss-gate`,
   Schrittmodell, Abschnitt zur Vergleichsansicht), **`specs/architecture/0003-securitykonzept.md`**
   (neuer Abschnitt mit S1–S10, Ankerzeile für S1/S3) und
   **`specs/architecture/0002-testkonzept.md`** (neuer Musterabschnitt, siehe `## Teststrategie`)
   werden im selben Pull Request nachgezogen.

9. **E2E:** `e2e/tests/stepper-progress.spec.ts::STEP_COUNT` 5 → 4 (bewusste, benannte Änderung);
   `e2e/tests/no-horizontal-scroll.spec.ts` leitet seinen Duplikat-Einstieg heute aus dem
   `?gate=1`-Modus plus Kachel-Link ab und wird auf den listenweiten Einstieg der Fotoliste
   umgestellt. `e2e/lib/demo.ts` (Bestätigungs-/Navigationspfad) wird auf die neue Schritt-Route
   gezogen.

### Reihenfolge der Umsetzung

1. Lese-Endpunkt samt `AusschussEntryOut`, Auth, 401-Fall und `DOCUMENTED_ROUTES`.
2. Abschluss-Schreibweg (Massen-`discard` in einer Transaktion).
3. Einzel-Schreibweg (erweiterte Vorbedingung, leerer Gruppenstand).
4. Schrittmodell (`pipelineSteps.ts`, `Stepper.tsx`, `PipelineStepView.tsx`).
5. `AusschussStepPage.tsx`: Übersicht → Detailansicht → Abschluss.
6. Rückbau in `PhotoGridPage.tsx`; E2E-Anpassungen; Demo-Bestand.
7. Doku (`docs/architecture.md`, Security-, Testkonzept).

## UI/UX

**Design-Quelle:** `design/penpot/views.json`, Schlüssel `ausschuss` (Seite „Ansicht — Ausschuss"),
Stand `ausgearbeitet`; Design-System `specs/architecture/0004-design-system.md`. Die Design-Nutzlast
führt die Detailansicht bisher als **Lücke** mit der Begründung, die Einzelprüfung liege in den
Ansichten „Duplikate vergleichen"/„Bilddetail". **Diese Lücke wird geschlossen** — Daniel hat
entschieden, dass AK8 (Duplikatgruppe in der Detailansicht, kein separater Seitenwechsel) Vorrang
hat. Die Nutzlast wird im Umsetzungs-PR entsprechend nachgezogen.

### Übersicht

- **Kachelraster** wie die Fotoliste (gerechnete Zeilen über `justifiedRows`), Kacheln als
  `<ul>`/`<li>`, die Bildfläche als `<button>`.
- **Grund-Kennzeichen je Kachel:** sichtbares **Zeichen und Wort** — „Duplikat" (Stapel aus drei
  versetzten Kartenumrissen, `--accent`) gegen „Geringe Bildqualität" (Symbol `image`,
  `--danger-text`). Farbe trägt nie allein: Das Wort steht daneben.
- **Entscheidungszeile je Kachel**, getrennt vom Grund: „Vorgeschlagen" (offen) / „Ausschuss" /
  „Behalten".
- **Bestätigungsbutton** in der Übersicht, beschriftet mit der Zahl der offenen Vorschläge
  (`open_count`). Bei `open_count == 0` ist er `disabled` mit neutralem Erklärtext.

### Detailansicht (inline, `?photo=<id>`)

- Großbild plus darunter die Entscheidungszeile; bei `reason === 'duplicate'` die Duplikatgruppe
  daneben (Mitglieder mit `DuplicatePhotoTile`).
- Schließen über eine Schaltfläche **und** `Esc`; beide führen über `navigate(-1)`/Entfernen des
  `photo`-Parameters zurück in die Übersicht, ohne geladene Seiten oder gesetzte Kennzeichen zu
  verlieren.
- Ist die Aufnahme nicht (mehr) im Ausschuss-Bestand (leere Antwort des `photo_id`-Filters), zeigt
  die Detailansicht einen benannten Zustand mit Rückweg statt eines leeren Screens.

### Zustände

- **noch nicht gelaufen:** Trigger-Button, Statuszeile „Noch nicht vorgeschlagen".
- **läuft:** Fortschritt („X von Y", dezil-gedrosselte `aria-live`-Ansage) wie heute.
- **fehlgeschlagen:** Alert mit „Erneut versuchen".
- **ladend:** Skeleton-Platzhalter mit `role="status"`.
- **Fehler der Übersicht:** Alert mit „Erneut versuchen".
- **leer / kein Ausschuss gefunden / automatisch übersprungen:** dauerhaft sichtbare, erklärende
  Zeile (kein flüchtiger Hinweis); der Bestätigungsbutton ist `disabled` mit neutralem Text.
- **bereits bestätigt:** Zustand samt Zeitstempel, Schritt bleibt erneut aufrufbar.

### Barrierefreiheit und Responsivität

Zustände nie allein über Farbe; die Bestätigung bleibt die einzige Abschluss-Aktion, ist aber kein
Pflichtschritt je Bild. Raster und Detailansicht folgen der bestehenden Breakpoint-Leiter; kein
waagerechtes Scrollen bei 360 px.

## Security

Sicherheitsrelevant, ohne neue Vertrauensgrenze: kein Secret, keine Umgebungsvariable, kein externer
Dienst, kein neuer Freitext, keine neue Aufzählbarkeit, keine Änderung an Authentifizierung oder
Sichtbarkeit zwischen den beiden Nutzern. Neu ist die **Reichweite eines Schreibwegs** — von „eine
Aufnahme / eine Gruppe" auf „alle offenen Vorschläge des Projekts, vom Server bestimmt" — und ein
**vierter Lesepfad** über dasselbe Prädikat, das den Cloud-Abfluss begrenzt (ADR 0104 Punkt 3). Die
Auflagen S1–S11 der Spec 0374 gelten unverändert weiter.

- **S1 — Der Massenweg bindet seine Menge ausgeschrieben an das Projekt, in derselben Anweisung, die
  die offenen Vorschläge auswählt.** `duplicates.py::has_open_suggestion` ist ein Prädikat über
  `PhotoScore` mit korrelierter Unterabfrage auf `photo_duplicate_decisions` und trägt **selbst keine
  Projektbedingung** — sie kommt allein aus dem umgebenden Join auf `Photo`. Bedrohung: Eine Auswahl,
  die nur `has_open_suggestion()` trifft oder ihr eine zweite Anweisung ohne
  `Photo.project_id == project_id` voranstellt, liefert jeden offenen Vorschlag der ganzen Instanz;
  ein Aufruf ohne Body schriebe `discard` über **alle** Projekte. Die Projektbedingung steht als
  UND-Glied in derselben Anweisung, nie als nachgelagerter Filter über einer bereits gebildeten Menge.
  Nachweis: ein Test mit mindestens zwei Projekten, von denen eines offene Vorschläge trägt.
- **S2 — Der Massenweg schreibt ausschließlich `discard`, und der Body bleibt ohne Id-Vorrat.** Ein
  Massen-`keep` wäre die einzige Richtung, die den abfließenden Bestand **vergrößert**, und zugleich
  ein Massen-Schreibweg auf beliebige Fotos; er ist untersagt. Der Aufruf bleibt bodyfrei; eine
  mitgeschickte Id-Liste wird zurückgewiesen, nie gelesen (`extra="forbid"` bleibt).
- **S3 — Eine Transaktion, ein `commit`; der Zeitstempel wird nie überschrieben.** Massen-Schreibweg
  und `gate_confirmed_at` liegen in einer Transaktion; ein halb geschriebener Bestand wäre eine
  willkürliche Teilmenge im abfließenden Bestand. `gate_confirmed_at` wird nur bei `NULL` gesetzt. Ein
  gleichzeitiger Einzel-Schreibvorgang auf dieselbe Aufnahme wird `409`, nie `500`.
- **S4 — Bestehende Entscheidungen bleiben unangetastet, und zwar durch die Auswahlbedingung, nicht
  durch Nachfilterung.** `has_open_suggestion` schließt jede Aufnahme mit Zeile aus; ein `discard` auf
  eine manuell behaltene Aufnahme wäre deren stille Rücknahme. Nachweis: ein Fall mit gesetzter
  Entscheidungszeile, der beweist, dass die Zeile unverändert bleibt.
- **S5 — Der neue Lese-Endpunkt trägt den Torwächter ausgeschrieben.** `GET /projects/{project_id}/
  ausschuss` liegt in `photos.router` (ohne router-weite `dependencies`): eigener `current_user`,
  eigener pfadbenannter `401`-Fall, Eintrag in `DOCUMENTED_ROUTES`. `project_id` deklarativ begrenzt
  (`ge=1, le=MAX_QUERY_POSITION`), Paginierung begrenzt, `404` ohne Spiegelung des übergebenen
  Werts, `401` vor jeder Aussage über das Projekt.
- **S6 — Der Lesepfad ist projektgebunden, auch der Gruppenanker.** `PhotoScore.duplicate_of` zeigt
  auf `photos.id` **ohne** Projektbedingung; `group_anchor_photo_id` und jeder Eintrag stammen aus
  einer projektbegrenzten Menge (`load_duplicate_links` bzw. derselben ausgeschriebenen Bedingung).
  Eine unbekannte oder fremde `photo_id` liefert eine leere Liste, ununterscheidbar von einer
  unbekannten; der Anker ist keine Zugriffsmarke, weil die Folgeanfrage erneut über `project_id`
  läuft.
- **S7 — `reason` und `decision` stammen aus `duplicates.py`/`_suggestion_reason`, nie aus
  `PhotoOut.suggestion` und nie aus einer TypeScript-Ableitung.** ADR 0111 Punkt 1 gilt unverändert:
  `PhotoOut.suggestion` fällt nach jeder Entscheidung und bei eigener Albumbewertung auf `null`. Eine
  zweite Fassung in TS sieht der Wächter nicht, weil er nur `backend/src` liest — eine Anzeige, die
  vom Prädikat wegläuft, bestimmte dann mit, was den Homeserver verlässt.
- **S8 — Sichtbarkeit zwischen den beiden Nutzern: unverändert, mit einer Cache-Auflage.** Die
  Entscheidung bleibt projektweit und nutzerlos; die Antwort trägt aber `PhotoOut` mit
  `suggestion`/`ratings` und ist damit eine **Funktion des anfragenden Nutzers** — die S10-Auflage
  aus Spec 0374 gilt für diesen vierten Endpunkt unverändert: jede Zwischenspeicherung, ein `ETag`
  oder ein `Cache-Control` über `no-store` hinaus muss den Nutzer im Schlüssel führen.
- **S9 — Die Abflussgrenze bleibt unangetastet (ADR 0104 Punkt 3).** Das Überlebenden-Prädikat wird
  nicht angefasst; die vier cloud-bestimmenden Abfragen (`worker.py::run_criterion_scoring`,
  `worker.py::select_remote_category_candidates`, `api/projects.py::_count_remote_category_candidates`,
  `::_count_landmark_candidates`) bleiben unverändert, und kein Eintrag in
  `tests/test_ausschuss_ueberlebende.py::_ERWARTETE_VERWENDUNGEN` wird gesenkt oder entfernt. Der
  Massenweg schreibt nur `discard` und **verkleinert** den abfließenden Bestand — fail-closed.
  Untersagt bleibt, das Prädikat in den neuen Lesepfad zu duplizieren: Der Lesepfad zieht
  `has_open_suggestion`/`_suggestion_reason`, er schreibt sie nicht aus.
- **S10 — Die Erweiterung des Einzel-Schreibwegs öffnet kein neues Abflussrisiko; ein akzeptiertes,
  aber unwirksames `keep` bleibt bewusst möglich.** Die Vorbedingung wechselt auf „hat Gruppe **oder**
  offenen Vorschlag", bleibt aber ein serverseitig **pro Foto** beantwortetes, projektgebundenes
  Prädikat — kein Massenweg, kein Id-Vorrat. `keep` wirkt konstruktiv nur bei „Duplikat",
  `discard` ist fail-closed. Ein `keep` auf eine Unschärfe-Ablehnung ohne Gruppe ist wirkungslos; der
  Server weist es **nicht** ab. Grund: Auflage S4 der Spec 0486 hat diese Frage bereits entschieden —
  eine serverseitige Abweisung wäre eine zweite Regel neben ADR 0104 Punkt 3 und liefe dem
  gruppenweiten Schreibweg entgegen, der dieselbe Zeile für dasselbe Mitglied schreibt. Die Anzeige
  versteckt den Knopf (AK6). Bei Verletzung (Anzeige bietet einen wirkungslosen `keep` an) sieht der
  Nutzer eine Handlung ohne Wirkung — aber keine Aufnahme verlässt den Homeserver.

**Ausdrücklich geprüft und ohne Befund:** Der Massenweg verkleinert nur (das Restrisiko „ein
gruppenweites `keep` macht in einem Klick viele Aufnahmen zu Cloud-Kandidaten" aus Spec 0374 wird
nicht erweitert, eher gemindert); keine neue Aufzählbarkeit (beide Nutzer sehen alle Projekte, ein
unbekanntes Projekt ist `404`, die `401` greift davor); kein neuer XSS-Sink (die neuen Felder sind
Aufzählungswert, `int`, `null` und `PhotoOut`-Textknoten). Die große In-Memory-Id-Menge des
Massenwegs ist eine Robustheits-, keine Sicherheitsfrage.

## Teststrategie

**Ebenen:** Backend-Integration (neue Endpunkte gegen echte In-Memory-DB über
`authenticated_api_client`), Backend-Unit nur, wo reine Funktionen neu sind, Frontend-Unit
(`vitest`/Testing Library), E2E nur als Anpassung bestehender Specs.

- **Lese-Endpunkt** (neue Datei `backend/tests/test_api_ausschuss.py`): Vereinigung aus offenem
  Vorschlag **und** Entscheidungszeile (mit dem Fall, der in der Schnittmenge liegt — ein Test je
  Ursache bestünde auch gegen eine Umsetzung, die nur eine liest); `reason`-Parität gegen
  `_suggestion_reason`; `decision` ist der gespeicherte Wert und ändert sich nicht durch ein eigenes
  `Rating` des Anfragenden; `group_anchor_photo_id` mit/ohne/verschwundener Gruppe; `open_count` als
  projektweite, von `limit`/`offset` unabhängige Zahl; Paginierung über `total` und
  Überlappungsfreiheit zweier Seiten; Leerfälle (`200` mit leerem `items` — auch ohne erfolgreichen
  `ScoringRun` und bei Projekt ohne Fotos, **nicht** `404`/`409`); `photo_id`-Filter liefert genau
  den Eintrag, für eine Id außerhalb des Bestands eine leere Liste; `404`/`422`; eigener
  pfadbenannter `401`-Fall; Eintrag in `DOCUMENTED_ROUTES`.
- **Sammel-Schreibweg** (`test_api_projects.py`): Zeilenzählung in `photo_duplicate_decisions` je
  offener Aufnahme; **bereits entschiedene bleiben unangetastet** (manuell `keep` bleibt `keep`);
  Idempotenz zweimal hintereinander; nach erneutem Lauf nur die dann offenen; `open_count == 0` (keine
  Zeile, Gate gesetzt); `409` ohne erfolgreichen Lauf; erzwungener Abbruch vor dem `commit` ⇒ null
  Zeilen und Gate `null`.
- **Prädikat-Wächter** (`test_ausschuss_ueberlebende.py`): Der neue Lesepfad und der Massenweg dürfen
  „offen" nicht von Hand schreiben; `_ERWARTETE_VERWENDUNGEN` wächst um die neuen Stellen — als
  **benannte** Änderung im PR, und in keinem Fall wird ein Eintrag gesenkt.
- **Einzel-Schreibweg** (`test_api_duplicate_decisions.py`): Der bestehende `404`-Fall für die
  Aufnahme ohne Gruppe wird zur `200`-Annahme (bewusst benannte Erwartungsänderung); `404` nur noch
  ohne Gruppe **und** ohne Vorschlag; leere Antwortform (`position = 0`, `total = 0`, beide Nachbarn
  `null`); `409` unverändert.
- **Frontend:** `AusschussStepPage.test.tsx` (Zustände, `open_count == 0`, Bestätigungsdialog,
  Fehlerfall, Detailansicht bei `?photo`, „aufheben" bei `low_quality` über die **Anzahl** der
  Bedienelemente), neue `useAusschuss.test.tsx` (Key unter `['photos', projectId, …]`),
  Detailansicht-Gruppe (`404` ⇒ leerer Zustand, nicht Fehleralert; anderer Fehler ⇒ Alert mit
  Wiederholung), `pipelineSteps.test.ts` und `Stepper.test.tsx` (kein `gate`, Wortlaut des
  Blockiergrunds, „von 4"), `PhotoGridPage.test.tsx` (Abwesenheit des Gate-Bestätigungsaufrufs über
  den Aufrufzähler der gemockten API-Funktion), `api/ausschuss.test.ts`.
- **E2E:** `stepper-progress.spec.ts::STEP_COUNT` 5 → 4; `no-horizontal-scroll.spec.ts` auf den neuen
  Einstieg umgestellt. **Kein neuer** E2E-Spec: Der Demo-Bestand trägt keine Entscheidungszeile, und
  „Specs sind lesend" schließt das Anlegen per Klick aus.

**Vier wiederverwendbare Muster** werden ins `specs/architecture/0002-testkonzept.md` aufgenommen:
(1) ein Bestand mit zwei Ursachen wird über die Wahrheitstabelle beider Ursachen geprüft, mit dem
Fall in der Schnittmenge; (2) zeigt eine Ebene den Rohwert und eine den wirksamen Zustand, ist die
Differenz der Testgegenstand; (3) die Zusagen eines Mengen-Schreibwegs sind nur über Zeilenzahlen und
einen erzwungenen Abbruch prüfbar; (4) das Wegfallen eines Schritts wird an seinen benannten
Abhängigkeiten nachgezogen (`STEP_COUNT`, `no-horizontal-scroll`), nie still. Dazu der Einzelpunkt:
ein Deep-Link-Parameter außerhalb der geladenen Seite ist ein regulärer Zustand mit definierter
Antwort.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR `0121` angelegt; ein Lese-Endpunkt mit eigenem
  Antwortmodell, Detailansicht per `?photo`, projektweiter Abschluss-Schreibweg, erweiterter
  Einzel-Schreibweg.
- `ux-ui-designer` konsultiert (Schritt 2): Übersicht als Kachelraster, Detailansicht inline (kein
  Dialog), Grund-Kennzeichen mit Zeichen **und** Wort, Bestätigungsbutton mit `open_count`. Die
  Design-Lücke `detailansicht` der Nutzlast wird geschlossen.
- `test-engineer` konsultiert (Schritt 3): Teststrategie und vier Muster; Schärfung der
  Antwortform-ACs (Reihenfolge, `total`/`open_count`, `decision` als Rohwert, leere Antwortform des
  Einzel-Schreibwegs, `?photo` außerhalb des Bestands); Testkonzept ergänzt.
- `security-engineer` konsultiert (Schritt 3): sicherheitsrelevant, zehn Auflagen S1–S10;
  Sicherheitskonzept ergänzt.
- **Design-Konflikt zugunsten des Akzeptanzkriteriums entschieden** (Daniel, 2026-09-23): Der
  Penpot-Entwurf ließ die Detailansicht als Lücke offen und verwies auf „Duplikate
  vergleichen"/„Bilddetail"; AK8 verlangt die Gruppe in derselben Ansicht. Die Detailansicht wird
  inline gebaut, die Nutzlast im Umsetzungs-PR nachgezogen.
- **`decision` ist der gespeicherte Zeilenwert, nicht `effective_decision_for`** — vom Spec-Autor
  entschieden: Die Übersicht zeigt den Sichtungsfortschritt; ein unwirksames `keep` bleibt als
  gespeicherte Handlung sichtbar. Übersicht und Detail ziehen dieselbe Größe.
- **`open_count` und der `photo_id`-Filter** liegen am selben Lese-Endpunkt (statt eines zweiten
  Endpunkts) — vom Spec-Autor entschieden, mit dem Alternativ-Zweig der Fotoliste als Muster.
- **Die `DuplicateComparePage` bleibt** — vom Spec-Autor entschieden (die Frage kam aus der
  Testkonsultation): Der listenweite Einstieg der Fotoliste (Spec 0486 AK7) trägt sie weiter, und
  diese Story verlangt ihre Entfernung nicht. Abgelöst ist allein der Einstieg aus dem
  Ausschuss-Schritt.
- **Auflage S4 der Spec 0486 bleibt in Kraft** — vom Spec-Autor gegen den Vorschlag des
  `security-engineer` (serverseitige Abweisung des unwirksamen `keep`) entschieden: Eine solche
  Abweisung wäre eine zweite Regel neben ADR 0104 Punkt 3 und liefe dem gruppenweiten Schreibweg
  entgegen. Der Vorschlag ist als S10 festgehalten; eine Änderung wäre ein eigener Vorgang.
- **Der `mcp`-Weg für die Board-/Issue-Operationen** wurde nicht benötigt; die Schreibzugriffe
  (`issue-anlegen` entfällt, `board-status-setzen`) liefen über `gh`.

## Offene Fragen

Keine.

## Out of Scope

- Die Duplikat-Erkennung selbst (welche Aufnahmen eine Gruppe bilden, welcher gewinnt) — unverändert.
- Eine Rücknahme einer Entscheidung nach „noch nicht entschieden" — gibt es weiterhin nicht.
- Die Duplikat-Vergleichsansicht (`DuplicateComparePage`) selbst: Sie bleibt bestehen und wird nicht
  umgebaut; nur ihr Einstieg aus dem Ausschuss-Schritt entfällt.
- Die normale, nach Vorschlägen gefilterte Fotoliste (`?filter=suggested`) und ihr listenweiter
  Duplikat-Einstieg — bleiben unverändert.
- Eine serverseitige Abweisung des wirkungslosen `keep` (siehe S10).
