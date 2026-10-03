# 0566 - Übersichtsseite am Projektbeginn, die den geplanten Ablauf erklärt

**Status:** Implemented ([PR #571](https://github.com/TheRealKoller/photosort/pull/571))
**Erstellt:** 2026-10-03
**Bezug:** [Issue #566](https://github.com/TheRealKoller/photosort/issues/566)

Die Spec liegt deutlich über dem Richtwert von ~200 Zeilen, weil sie den vollständigen Wortlaut der Übersicht, das Umbenennungsinventar und die Gleichlauf-Teststrategie festlegt, die der Umsetzungslauf sonst raten müsste.

## Ziel

PhotoSort führt ein Projekt durch mehrere Schritte (Scan, Ausschuss, Klassifizierung, Kuratierung, danach Album-Entwurf und Endauswahl). Wer den Ablauf nicht im Kopf hat — konkret Daniels Frau als zweite Nutzerin —, versteht nicht, wozu die einzelnen Schritte da sind (z.B. warum erst der Ausschuss gesichtet werden muss, wozu die Klassifizierung dient), was automatisch passiert und was man selbst tun muss. Heute erklärt jede Schrittseite nur sich selbst in einer Zeile; den Zusammenhang erklärt niemand, und ohne Daniel kommt sie nicht weiter.

Eine Übersicht des gesamten Ablaufs, die beim ersten Öffnen eines Projekts von selbst erscheint und danach jederzeit aufrufbar ist, soll beiden Nutzern ermöglichen, ein Projekt ohne fremde Hilfe zu verstehen und durchzuarbeiten. Dazu gehört, dass jeder Schritt überall in der Oberfläche gleich heißt: Der dritte Schritt heißt bisher teils „Kriterien-Bewertung", teils „Klassifizierung" — künftig überall „Klassifizierung".

## User Story

Als Nutzerin oder Nutzer eines Projekts, die oder der den Ablauf von PhotoSort nicht im Kopf hat, möchte ich beim ersten Öffnen eines Projekts und danach jederzeit eine Übersicht aller Schritte sehen, die mir sagt, wozu jeder Schritt da ist, was automatisch läuft und was ich selbst tun muss, warum die Schritte in dieser Reihenfolge kommen und wo dieses Projekt gerade steht — damit ich ohne Hilfe weiterarbeiten kann und zum Beispiel verstehe, warum der Ausschuss vor der Klassifizierung kommt.

## Akzeptanzkriterien

**Inhalt der Übersicht**

- [ ] Die Übersicht nennt die vier Schritte Scan, Ausschuss, Klassifizierung und Kuratierung in der Reihenfolge und unter den Namen der Schrittleiste, danach die Stationen Album-Entwurf und Endauswahl. Es fehlt kein Schritt, keiner kommt hinzu. Die Namen der Schritte stammen aus derselben Quelle wie die Schrittleiste, die beiden Stationsnamen aus je einer bestehenden Quelle; geprüft wird auf exakte Gleichheit, nicht auf „enthält“.
- [ ] Zu jedem Schritt steht in höchstens zwei Sätzen Alltagssprache, wozu es ihn gibt. Begriffe, die sonst nirgends in der Oberfläche vorkommen, werden nicht verwendet. Jede in den Texten zitierte Bezeichnung („Aktualisieren“, „Ausschuss gesichtet, weiter“, „Klassifizierung starten“, „Unterschiede“ …) steht wörtlich so an ihrer Bedienstelle.
- [ ] Jeder Schritt ist erkennbar als „läuft von selbst“, „braucht dich“ oder „beides“ (Beispiel Ausschuss: die Anwendung erkennt, du prüfst und bestätigst). Die Unterscheidung hängt nicht allein an der Farbe: Kennzeichnung und Zustand stehen jeweils als Wort im Eintrag.
- [ ] Bei jedem Schritt mit Handlung steht, ob ihn einer von beiden einmal für das ganze Projekt erledigt (Scan, Ausschuss, Klassifizierung), ob jeder seinen eigenen macht (Album-Entwurf) oder ob beide gemeinsam entscheiden (Endauswahl). Die Kuratierung trägt keine solche Angabe.
- [ ] Für jeden Schritt mit Vorbedingung steht, was vorher erledigt sein muss und warum (Beispiel: Die Klassifizierung startet erst nach bestätigtem Ausschuss, damit aussortierte Fotos weder bewertet noch an einen Cloud-Dienst geschickt werden). Das sind alle Einträge außer Scan; jede Angabe nennt den vorausgesetzten Schritt mit seinem Namen und einen Grund.
- [ ] Die Übersicht sagt, dass ohne Cloud-Freigabe in den Projekteinstellungen kein Album-Entwurf entsteht, und zeigt, wo man die Freigabe erteilt: Es ist derselbe Text wie im Leerzustand des Album-Entwurfs, und ein Link führt auf die Projekteinstellungen dieses Projekts.

**Stand des Projekts**

- [ ] Für das geöffnete Projekt zeigt die Übersicht je Schritt, ob er erledigt, aktuell, offen oder gesperrt ist; läuft gerade ein Schritt oder ist ein Lauf fehlgeschlagen, steht das ebenfalls da. Höchstens ein Schritt ist „aktuell“. Die Anzeige folgt dem Projektstand, solange die Übersicht offen ist.
- [ ] Übersicht, Schrittleiste und Stand-Zeile der Projektübersicht nennen für dasselbe Projekt immer denselben nächsten Schritt und dieselben Zustände. Konkret:
  - Der „aktuelle“ Schritt der Übersicht ist der, den die Stand-Zeile nennt. Bei „Noch nicht gescannt“ ist das der Scan.
  - Es ist zugleich der Schritt, auf dem man über „Pipeline“ landet.
  - Nennt die Stand-Zeile keinen Schritt, nennt auch die Übersicht keinen.
  - Erledigt und gesperrt stimmen zwischen Übersicht und Schrittleiste je Schritt überein. „Abgeschaltet“ heißt in der Leiste „gesperrt“.
  - Das „aktuell“ der Schrittleiste sagt, wo man gerade steht, und ist kein Zustand.
  - Ein Lauf, den die Stand-Zeile nennt, steht mit demselben Status beim selben Schritt der Übersicht.
- [ ] Album-Entwurf und Endauswahl werden nie als „erledigt“ gezeigt, sondern als „jederzeit möglich“, sobald sie erreichbar sind; sonst als „gesperrt“. Erreichbar sind sie genau dann, wenn die Kuratierung erreichbar ist.
- [ ] Ist die Klassifizierung für ein Projekt abgeschaltet, sagt die Übersicht das und zeigt den Schritt nicht als offen, als aktuell oder mit Öffnen-Schaltfläche. Das gilt auch dann, wenn früher schon eine Klassifizierung gelaufen ist.
- [ ] Jeder erreichbare Schritt lässt sich aus der Übersicht mit einem Klick öffnen (genau eine Schaltfläche je Eintrag, Ziel wie in der Schrittleiste). Ein gesperrter Schritt hat kein Bedienelement und nennt wortgleich denselben Grund wie die Schrittleiste.

**Wann die Übersicht erscheint**

- [ ] Öffnet eine der beiden Personen ein Projekt zum ersten Mal, erscheint die Übersicht von selbst — egal über welchen Weg sie ins Projekt kommt, auch wenn die andere Person das Projekt angelegt oder die Übersicht dort schon gesehen hat. Bereits bestehende Projekte zählen mit: Das erste Öffnen nach Einführung gilt als erstes Mal.
  - „Jeder Weg“ heißt: jede Seite mit Projektbezug, auch ein Lesezeichen auf ein Foto.
  - Auf Seiten ohne Projektbezug erscheint sie nicht.
  - Wer das Projekt anlegt, sieht sie beim ersten Öffnen ebenfalls.
- [ ] Hat eine Person die Übersicht in einem Projekt geschlossen, erscheint sie für diese Person in diesem Projekt nicht mehr von selbst — auch nicht nach Neuladen, an einem anderen Tag oder auf einem anderen Gerät bzw. in einem anderen Browser. Für die andere Person und für andere Projekte ändert sich dadurch nichts. Auch der Klick auf einen Eintrag zählt als Schließen.
- [ ] Die Übersicht lässt sich mit einem Handgriff schließen (Schaltfläche „Schließen“ oder Esc); danach landet man beim nächsten anstehenden Schritt des Projekts. Das gilt auch, wenn man über ein Foto-Lesezeichen gekommen ist. Wer danach „Zurück“ wählt, bekommt die Übersicht nicht erneut.
- [ ] Von jeder Schrittseite eines Projekts aus lässt sich die Übersicht mit einem Klick öffnen, immer an derselben Stelle: ein Bedienelement „Ablauf“ im gemeinsamen Kopf der vier Schrittseiten, das beim Wechsel zwischen den Schritten stehen bleibt.
- [ ] Öffnen und Schließen ändern nichts am Projekt: Kein Schritt wird gestartet, bestätigt oder zurückgesetzt. Gemerkt wird ausschließlich, ob die Person die Übersicht in diesem Projekt schon gesehen hat, und zwar nur auf dem Server.
- [ ] Tastatur und Touch sind gleichwertig bedienbar; bei 360 px Breite ist alles ohne seitliches Scrollen lesbar. Lässt sich „schon gesehen“ nicht merken oder nicht lesen, bleibt das Projekt voll bedienbar — im Zweifel erscheint die Übersicht lieber einmal zu oft. Im Einzelnen:
  - Keine Funktion hängt am Überfahren mit der Maus, und jedes Bedienelement ist ab 44 × 44 px treffbar.
  - Bei 360 px liegt „Schließen“ ohne Scrollen im Bild.
  - Ein Fehler beim Lesen lässt die Übersicht erscheinen, ein Fehler beim Merken bleibt ohne Meldung.
  - Solange „schon gesehen“ noch nicht bekannt ist, erscheint sie nicht.

**Einheitlicher Name „Klassifizierung“**

- [ ] Der dritte Schritt heißt an jeder sichtbaren Stelle „Klassifizierung“: in der Schrittleiste samt „Schritt 3 von 4“, in Sperrgründen, auf der Schrittseite, in der Stand-Zeile der Projektübersicht (auch „… ist abgeschaltet“), in Hinweisen und Links auf Album-Entwurf und Endauswahl, in der Statuszeile während des Laufs (in jeder Phase), in der Übersicht und in angezeigten Meldungen.
- [ ] „Kriterien-Bewertung“ steht danach an keiner sichtbaren Stelle mehr, auch nicht in Leertexten, Screenreader-Beschriftungen oder Seitentiteln. Das gilt auch für Schreibweisen mit anderem Bindestrich oder Leerzeichen, für Zusammensetzungen und für den bisherigen Stand-Zeilen-Wortlaut „Kategorie-Bewertung“. Kommentare und interne Kennungen zählen nicht als sichtbar.
- [ ] Nur der Name ändert sich: Bedeutung, Reihenfolge, Sperrregeln und Verhalten des Schritts bleiben gleich; Links und Lesezeichen auf den Schritt (`/projects/:id/pipeline/kriterien`) funktionieren weiter.
- [ ] Die Anzeige, welcher Teil eines Klassifizierungslaufs gerade arbeitet, unterscheidet ihre Teilschritte weiterhin: Die Namen sind paarweise verschieden, und keiner davon heißt „Kriterien-Bewertung“ oder schlicht „Klassifizierung“ wie der ganze Schritt.

**Abgrenzung**

- [ ] Die Pipeline selbst bleibt unverändert: keine neuen Schritte, Regeln oder Sperren. Die bestehenden Tests der Schrittzustände, der Weiterleitung und der Sperrregeln bleiben bis auf den Wortlaut unverändert grün.
- [ ] Es gibt keine geführte Tour mit Hervorhebungen in der Oberfläche.

## Datenmodell-Bezug

Neue Zuordnungstabelle `project_overview_seen` (`user_id`, `project_id`, zusammengesetzter Primärschlüssel, beide Fremdschlüssel), Entität `ProjectOverviewSeen`; fehlende Zeile heißt „nicht gesehen“. Wird mit dem Projekt gelöscht. Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Ansatz in einem Satz:** Die Übersicht ist ein modaler Dialog, den ein Host in der `AppShell` auf jeder Route mit Projektkontext bereitstellt. Ihre Zustände leitet eine neue reine Funktion in `utils/pipelineSteps.ts` ausschließlich aus den Bausteinen ab, die schon Schrittleiste und Stand-Zeile speisen. „Schon gesehen“ liegt serverseitig in einer neuen Tabelle mit eigenem Endpunktpaar. Die Umbenennung ändert nur Labels, keine Kennungen.

### 1. Eine Ableitung für Übersicht, Schrittleiste und Stand-Zeile

Heute (alles in `frontend/src/utils/pipelineSteps.ts`):

| Was | Woher |
|---|---|
| Schrittmenge, Reihenfolge, Namen | `PIPELINE_STEPS[].label` |
| erledigt/erreichbar je Schritt | `computeStepStates(project)` |
| nächster Schritt (Frontier) | `getDefaultStepId` (= `getHighestReachableStepId`), auch Ziel der Weiterleitung `/projects/:id/pipeline` in `ProjectPipelineLayout` |
| Sperrgrund | `getBlockedReason(id, project)`, angezeigt im Popover von `components/Stepper.tsx::BlockedStep` |
| „Schritt N von 4“ | `Stepper.tsx`, aus `PIPELINE_STEPS.length` und Label (Orientierungszeile und `aria-label`) |
| Stand-Zeile der Projektübersicht | `deriveProjectStand` → `components/ProjectStandLine.tsx` (`pages/ProjectListPage.tsx`) |
| Lauf je Schritt | `RUN_FIELD_BY_STEP` + `runStatusOfStep` |

Neu ist `deriveWorkflowOverview(project): WorkflowOverviewEntry[]` in derselben Datei. Die Funktion ruft nur `computeStepStates`, `getDefaultStepId`, `getBlockedReason` und `runStatusOfStep` auf und kennt keine eigene Regel. Damit ist „derselbe nächste Schritt“ (AK) strukturell abgesichert und muss nicht nachgehalten werden.

- Einträge: `OverviewEntryId = StepId | 'album' | 'selection'`, in dieser Reihenfolge.
- Zustand je Schritt, mit Vorrang von oben nach unten:
  1. `abgeschaltet` (nur `kriterien` bei `category_selection_enabled === false`, Grund aus `getBlockedReason`)
  2. `gesperrt` (`!isReachable`, Grund aus `getBlockedReason`)
  3. `aktuell` (`id === getDefaultStepId(states)` und nicht `isDone`)
  4. `erledigt` (`isDone`)
  5. `offen`

  „Aktuell“ verwendet genau die Bedingung, unter der `deriveProjectStand` einen Schritt nennt. Im Randfall C (Frontier fällt auf einen erledigten Schritt zurück) gibt es deshalb kein „aktuell“; das passt zu „Klassifizierung ist abgeschaltet“.
- Lauf je Schritt: `runStatusOfStep` liefert `running` → „läuft“, `failed` → „fehlgeschlagen“, sonst nichts. Die Angabe steht unabhängig vom Zustand.
- Album-Entwurf und Endauswahl sind nie `erledigt`. Sie sind `jederzeit`, sobald `kuratierung.isReachable` gilt, sonst `gesperrt` mit `getBlockedReason('kuratierung', project)`. Der Album-Entwurf entsteht erst aus dem Klassifizierungslauf, und sein einziger Einstieg aus dem Ablauf liegt auf der Kuratierungsseite (`KuratierungStepPage` → „Album-Entwurf öffnen“).
- Klickziele: Schritte → `/projects/:id/pipeline/:step` (wie im Stepper), Album-Entwurf → `/projects/:id/album`, Endauswahl → `/projects/:id/selection`, Cloud-Freigabe → `/projects/:id/settings`.
- Abgrenzung: Das „aktuell“ des Steppers (`activeStepId` aus der URL) bleibt eine Positionsangabe („hier bist du“). Erledigt und gesperrt sind in beiden identisch, weil beide `computeStepStates` lesen.

Die festen Erklärtexte stehen in `utils/workflowOverview.ts`: Zweck, „läuft von selbst / braucht dich / beides“, Zuständigkeit (einmal fürs Projekt / jeder seinen / gemeinsam), Vorbedingung samt Grund und der Hinweis zur Cloud-Freigabe. Sie liegen als `Record<OverviewEntryId, …>` vor, damit ein Schritt ohne Text ein Typfehler ist. Die Schrittnamen kommen aus `PIPELINE_STEPS`, die Stationsnamen aus den bestehenden Labels („Album-Entwurf“, „Endauswahl“ aus `utils/projectRoutes.ts`), nicht als zweite Kopie.

### 2. „Schon gesehen“ je Person und Projekt

- **Modell:** `ProjectOverviewSeen` in `backend/src/photosort/models.py`, Tabelle `project_overview_seen`.
  - Primärschlüssel `(user_id, project_id)`, beide `ForeignKey` benannt (`fk_project_overview_seen_user_id`, `fk_project_overview_seen_project_id`).
  - Keine weitere Spalte, also auch kein Zeitstempel. Gemerkt wird nur die Tatsache.
  - Keine Zeile heißt „nicht gesehen“, damit zählen bestehende Projekte ohne Datenwanderung als ungesehen.
- **Migration:** `backend/alembic/versions/<kennung>_ablauf_uebersicht_gesehen.py`, `down_revision = b0814fc600bf` (heutiger Head). Die Kennung holt der Umsetzungslauf über `scripts/nummern.py migration ablauf-uebersicht-gesehen` und legt die Datei bei Exit 10 sofort an. Kommt vorher eine andere Revision auf `main`, gilt `nummern.py umhaengen`.
- **Löschen:** In `project_deletion.py::delete_projects` kommt `delete(ProjectOverviewSeen).where(project_id.in_(…))` vor die `projects`-Anweisung. Die Vollständigkeits- und Reihenfolgeprüfung in `tests/test_project_deletion.py` gegen `Base.metadata` macht das Fehlen rot. `users` werden nicht gelöscht.
- **API:** neues Modul `backend/src/photosort/api/project_overview.py`, Router `prefix="/projects"` mit `dependencies=[Depends(get_current_user)]`, eingehängt in `main.py`.
  - `GET /projects/{project_id}/overview-seen` → `200 {"seen": bool}`.
  - `PUT /projects/{project_id}/overview-seen` → `204` ohne Body, idempotent.
  - Beide antworten `404` bei unbekanntem Projekt.
  - `user_id` kommt allein aus `get_current_user` (JWT-`sub`), nie aus der Anfrage, und keine Antwort nennt den Zustand der anderen Person.
  - Beim `PUT` wird bei vorhandener Zeile nichts getan, sonst eingefügt und committet. Ein `IntegrityError` (zweiter Tab derselben Person, oder Projekt gleichzeitig gelöscht) führt zu `rollback`, dann zu erneuter Projektprüfung (`404`), sonst `204`. Nie `500`. Das Muster folgt `api/duplicate_decisions.py::_write`.
  - Bewusst **nicht** an `ProjectOut`: `ProjectOut` ist nutzerunabhängig und wird gepollt, und ein Fehler des Merkers darf das Laden des Projekts nicht mitreißen.
- **Frontend-Zugriff:**
  - `api/projectOverview.ts` (`getOverviewSeen`, `markOverviewSeen`) und `OverviewSeenOut` in `api/types.ts`.
  - Hook `hooks/useOverviewSeen.ts` mit Schlüssel `['overview-seen', username, projectId]`. Der Nutzername kommt aus `decodeUsername(getToken())` wie in der `AppShell`. Er steht im Schlüssel, weil der Abfrage-Cache eine Abmeldung im selben Tab überlebt.
  - `retry: false`, damit der Zweifelsfall sofort greift; `staleTime: Infinity`.
- **Fehlerverhalten:**
  - Lesefehler: Die Übersicht erscheint.
  - Schreibfehler: keine Anzeige, das Projekt bleibt bedienbar. Der lokale Abfragewert wird beim Schließen per `setQueryData` auf `seen: true` gesetzt. In dieser Sitzung erscheint die Übersicht dann nicht erneut, nach einem Neuladen schon (lieber einmal zu oft).
  - Öffnen und Schließen schreiben nichts außer diesem `PUT`.

### 3. Einbindung im Frontend

- **Dialog statt Route:** Neues `components/WorkflowOverviewDialog.tsx` auf dem bestehenden `components/ui/dialog.tsx`. Damit kommen Esc, Fokusfalle, Fokusrückgabe und Scroll-Sperre aus `lib/useModalDialog.ts`; Schließen ist ein Handgriff (Esc oder Schaltfläche, `cancelLabel` „Schließen“). Eine Route wäre die falsche Wahl: Sie müsste jeden Deep-Link umleiten, während der Dialog über der aufgerufenen Seite liegt.
- **Host:** Neues `components/ProjectOverviewHost.tsx`, das `App.tsx::AppShell` als `{projectId !== null && <ProjectOverviewHost key={projectId} … />}` rendert.
  - Es greift auf allen elf Mustern aus `utils/projectRoutes.ts::PROJECT_ROUTE_PATHS`, also auf jedem Einstiegsweg: Projektkarte, `/projects/:id`, Lesezeichen, Kopfnavigation, Foto-Deep-Link.
  - Es liest `useProjectQuery(id)` (gleicher Schlüssel `['project', id]` wie das Layout, keine zweite Anfrage, gepollt) und `useOverviewSeen`.
  - Automatisches Öffnen, wenn das Projekt geladen ist und `seen === false` oder die Abfrage fehlgeschlagen ist. Kein Öffnen, solange etwas lädt, bei `404` oder bei nicht-ganzzahliger `projectId`.
- **Schließen:** `setQueryData` gesehen, `markOverviewSeen` ohne Fehleranzeige, `navigate('/projects/:id/pipeline')`. Die bestehende Weiterleitung in `ProjectPipelineLayout` führt damit über dieselbe Frontier-Ableitung zum nächsten anstehenden Schritt. Ein Klick auf einen Eintrag merkt ebenso „gesehen“ und navigiert zu dessen Ziel.
- **Manuell öffnen:** Der Host stellt `ProjectOverviewContext` bereit (`useProjectOverview().open`). Der Auslöser sitzt im Kopf von `pages/pipeline/ProjectPipelineLayout.tsx`, neben `<h1>` (als `shrink-0`), und steht damit auf allen vier Schrittseiten an derselben Stelle. Ohne Provider wirft der Hook; Layout-Tests wickeln den Provider ein.
- **360 px:** Dialogbreite `min(32rem, 100vw-2rem)`. Lange Inhalte scrollen im Dialog, nie seitlich. Den Nachweis gehört in den bestehenden Prüfpfad `e2e/tests/no-horizontal-scroll.spec.ts` mit geöffnetem Dialog.
- **Folge für den Prüfstack:** Der modale Dialog läge sonst beim ersten Öffnen jedes Demo-Projekts über der geprüften Seite.
  - `e2e/setup/auth.setup.ts` markiert nach der Anmeldung über `GET /api/projects` und `PUT /api/projects/{id}/overview-seen` alle Projekte für `e2e-daniel` als gesehen.
  - Dasselbe gilt für die Ad-hoc-Werkzeuge (`e2e/lib/adhoc.ts::ensureAuthState`, genutzt von `browse-app`).
  - Für das erste Öffnen steht `e2e-zweiter-nutzer` bereit.

### 4. Umbenennung „Kriterien-Bewertung“ → „Klassifizierung“ (nur sichtbarer Text)

| Fundstelle | Wirkung | neu |
|---|---|---|
| `frontend/src/utils/pipelineSteps.ts:22` `PIPELINE_STEPS` label | Schrittleiste, „Schritt 3 von 4: …“ (Orientierungszeile und `aria-label`), Stand-Zeile „Weiter: …“/„… läuft…“/„… fehlgeschlagen“, Übersicht | „Klassifizierung“ |
| `pipelineSteps.ts:109` `getBlockedReason('kuratierung')` | Sperrgrund Kuratierung (Leiste und Übersicht) | „Führe zuerst die Klassifizierung oben aus.“ |
| `pipelineSteps.ts:150` `STAND_KATEGORIE_ABGESCHALTET` | Stand-Zeile Randfall C | „Klassifizierung ist abgeschaltet“; Konstante umbenannt in `STAND_KLASSIFIZIERUNG_ABGESCHALTET` |
| `frontend/src/components/ClassificationSection.tsx:193` | Statuszeile während des Laufs | in jeder Phase „Klassifizierung läuft…“; `isRemotePhase` entfällt |
| `frontend/src/utils/classificationSteps.ts:59` `STEP_LABELS.criteria` | Teilschrittliste (`ClassificationProgress`) | eigener Name, weder „Kriterien-Bewertung“ noch „Klassifizierung“ (Wortlaut siehe unten) |
| `frontend/src/pages/AlbumDraftPage.tsx:52` `DRAFT_EMPTY_TEXT` (auch in `AlbumSelectionPage`) | Leertext Album-Entwurf/Endauswahl | „… führe die Klassifizierung aus.“ |
| `AlbumDraftPage.tsx:515`, `AlbumSelectionPage.tsx:184` | Link-Text | „Zur Klassifizierung“ |
| `backend/src/photosort/api/projects.py:1132` (`_reject_while_a_criterion_run_is_active`, 409-Detail, angezeigt in `KuratierungStepPage`) | Fehlermeldung | „Fuer dieses Projekt laeuft gerade eine Klassifizierung. …“ |
| `backend/src/photosort/demo_state.py:1727` | sichtbare Fehlermeldung des Demo-Fehlerlaufs | „Klassifizierung abgebrochen (…)“ |

Nicht betroffen:

- Seitentitel (`index.html` hat nur „PhotoSort“, kein `document.title`).
- Die Überschrift von `KriterienStepPage` heißt schon „Klassifizierung“ (`ClassificationSection` `<h2>`).
- Worker-Fehlermeldungen (`worker.py::_fail_run`-Aufrufe) tragen den Namen nicht.
- e2e-Specs enthalten den Begriff nicht.

Bleibt unverändert:

- `StepId 'kriterien'`, die Route `/projects/:id/pipeline/kriterien` (Lesezeichen funktionieren weiter), `KriterienStepPage`, `RUN_FIELD_BY_STEP`, `ClassificationPhase 'criteria'`, alle Backend-Bezeichner.
- Code-Kommentare.
- Die Ausgaben der reinen Betreiber-CLI `criterion_probe.py`, `event_probe.py` und `place_probe.py` (keine Oberfläche).

Bestehende Tests mit dem alten Wortlaut ziehen mit: `Stepper.test.tsx`, `ProjectStandLine.test.tsx`, `pipelineSteps.test.ts`, `AlbumSelectionPage.test.tsx`, `KuratierungStepPage.test.tsx`, `ClassificationSection.test.tsx` sowie der Backend-Test zum 409-Detail bzw. zum Demo-Zustand, falls sie den Text prüfen.

### 5. Datenquellen der Zustände

Alle Daten liegen schon in `ProjectOut`; die Übersicht braucht kein neues Feld.

- Scan erledigt / läuft / fehlgeschlagen: `last_scan.status`
- Ausschuss erledigt: `last_scoring_run.gate_confirmed_at`; Lauf: `last_scoring_run.status`
- Klassifizierung erledigt / läuft / fehlgeschlagen: `last_criterion_scoring_run.status`; erreichbar: `category_selection_enabled && gate_confirmed_at`
- Abgeschaltet: `ProjectOut.category_selection_enabled` (instanzweiter Schalter `settings.category_selection_enabled`, je Projekt ausgeliefert)
- Kuratierung und die Stationen erreichbar: Klassifizierung erledigt
- Hinweis zur Cloud-Freigabe: statischer Text, Link auf Einstellungen. Den Zustand liefert `cloud_vision_detection_enabled`, falls die Spec ihn zeigen will.

### 6. ADR

Keine. Es gibt keine neue Technologie und keine externe Abhängigkeit. Die neue Tabelle ist eine Zuordnungstabelle nach dem bestehenden Nutzer-×-Objekt-Muster (`ratings`) und verändert die Grundstruktur nicht. Dass „gesehen“ serverseitig liegt, verlangt das AK „anderes Gerät/anderer Browser“. Der Stand bleibt Frontend-Ableitung, wie bisher.

### 7. Doku

`docs/architecture.md` ist im Worktree ergänzt:

- Schrittliste „Klassifizierung“, Kennung bleibt `kriterien`
- Komponente Ablaufübersicht
- Endpunktpaar `overview-seen`
- Entität `ProjectOverviewSeen`
- Löschliste (ohne Zahlwort; dabei die fehlenden `photo_person_*` ergänzt)
- e2e-Setup
- Zeile „Letzte Aktualisierung“

### Reihenfolge der Umsetzung

1. Backend-Modell, Migration, `project_deletion.py`
2. `api/project_overview.py` und `main.py`
3. Backend-Texte (projects.py 409, demo_state)
4. Frontend-Umbenennungen (pipelineSteps, classificationSteps, ClassificationSection, Album-Seiten)
5. `deriveWorkflowOverview`
6. `utils/workflowOverview.ts`
7. `api/projectOverview.ts` und `hooks/useOverviewSeen.ts`
8. `WorkflowOverviewDialog`, `ProjectOverviewHost` (mit Kontext), Einbindung in `AppShell`, Auslöser in `ProjectPipelineLayout`. Bestehende App- und Layout-Tests mocken `getOverviewSeen` mit `{seen: true}`.
9. e2e-Setup und Ad-hoc-Helfer

### Wortlaut, den der fachliche Teil der Spec festlegt

Die Architektur hängt nicht davon ab:

- der Name des Teilschritts `criteria` (Vorschlag: „Bildmerkmale“)
- die Erklärtexte je Eintrag
- die Zustandswörter („aktuell“, „jederzeit möglich“, „abgeschaltet“)
- die Beschriftung des Auslösers

## UI/UX

Das Feature hat eine sichtbare Oberfläche: den Dialog „Ablauf im Überblick“, einen Auslöser auf den Schrittseiten und neue Wörter in Schrittleiste und Teilschrittliste. Einen Penpot-Entwurf gibt es nicht (Bekannte Lücke in `0004-design-system.md`). Maßgeblich sind dieser Abschnitt und das Design-System.

### Dialog

- `WorkflowOverviewDialog` auf `components/ui/dialog.tsx`: `title` „Ablauf im Überblick“, `icon="info"`, `cancelLabel` „Schließen“.
- `description`: „Von den Fotos im OpenCloud-Ordner bis zur gemeinsamen Endauswahl. Bei jedem Schritt siehst du, wie weit dieses Projekt ist.“ Der Projektname steht dort bewusst nicht: Ein langer Name ohne Leerzeichen würde bei 360 px über den Rand laufen.
- Inhalt in zwei Listen:
  - `<ol aria-label="Schritte">` mit Scan, Ausschuss, Klassifizierung, Kuratierung (Namen aus `PIPELINE_STEPS`).
  - Darunter die Beschriftung „Danach“ (`<p>`, `text-xs font-semibold uppercase tracking-wide text-text-muted`) und `<ul aria-labelledby>` mit Album-Entwurf und Endauswahl (Namen aus `utils/projectRoutes.ts`).
  - Abstand zwischen den Einträgen `gap-6`, keine Trennlinien. `--border` wäre auf `--overlay` unsichtbar.
- Aufbau eines Eintrags (`<li>`, `flex flex-col gap-3`), von oben nach unten (zugleich die Lesereihenfolge):
  1. **Kopfzeile** `flex flex-wrap items-center gap-x-3 gap-y-1`:
     - Schrittmarke: nur bei den vier Schritten; `StepMarker` in einem `<span class="w-8 shrink-0">`, sonst dehnt er sich unter `sm` auf die volle Breite.
     - `<h3 class="text-base font-semibold text-text-h">` mit dem Namen.
     - Zustandswort.
     - gegebenenfalls Lauf-Kennzeichen.
  2. **Zweck** als `<p class="text-sm text-text">`, höchstens zwei Sätze (Wortlaut unten).
  3. **`<dl class="flex flex-col gap-2 text-sm">`** mit bis zu drei Paaren:
     - Je Paar `flex flex-col gap-1 sm:flex-row sm:gap-3`.
     - `dt`: `text-xs font-semibold uppercase tracking-wide text-text-muted sm:w-28 sm:shrink-0`.
     - `dd`: `text-text`; das erste Wort der Kennzeichnung steht in `font-semibold text-text-h`.
     - Paare: **Wer arbeitet** (Kennzeichnung), **Zuständig** (nur bei Schritten mit Handlung), **Vorher** (nur bei Schritten mit Vorbedingung).
  4. **Nur Album-Entwurf:** `DRAFT_CLOUD_CONSENT_TEXT` aus `AlbumDraftPage.tsx`, importiert und nicht kopiert, als `<p class="text-sm text-text">`.
  5. **Aktionszeile** `flex flex-wrap gap-3`:
     - Erreichbarer Eintrag: Schaltfläche „{Name} öffnen“ (`Button asChild size="sm"` mit `Link`). Beim Eintrag „aktuell“ in der Ausprägung `default`, sonst `secondary`.
     - Album-Entwurf zusätzlich: `secondary sm` „Zu den Projekteinstellungen“ → `/projects/:id/settings`. Wortgleich mit dem Leerzustand der Entwurfsseite.
     - Gesperrter oder abgeschalteter Eintrag: statt der Öffnen-Schaltfläche der Sperrgrund als `<p class="text-sm text-text">`. Der Text kommt unverändert aus `getBlockedReason` (bei den Stationen `getBlockedReason('kuratierung', project)`). „oben“ stimmt auch in der Übersicht, weil der vorausgesetzte Schritt darüber steht.
- Es gibt keine Lade- und keine Fehleransicht im Dialog. Der Host öffnet ihn nur mit geladenem Projekt, und ein Schreibfehler bei „gesehen“ bleibt unsichtbar.
- Zustände ändern sich während der Dialog offen ist mit dem gepollten Projekt. Kein `aria-live`, sonst würde jeder Poll vorgelesen.

### Wortlaut je Eintrag

Kein Text verwendet einen Begriff, der nicht schon in der Oberfläche steht. Die Bezeichnungen der Schaltflächen sind wörtlich zitiert. Ablageort: `utils/workflowOverview.ts`.

| Eintrag | Zweck | Wer arbeitet | Zuständig | Vorher |
|---|---|---|---|---|
| Scan | PhotoSort durchsucht den verknüpften OpenCloud-Ordner und nimmt die Fotos ins Projekt auf; die Original-Fotos bleiben auf OpenCloud unverändert. Ein neuer Scan übernimmt später neue, geänderte und entfernte Fotos. | **beides** – du startest ihn mit „Aktualisieren“, den Rest erledigt PhotoSort. | einer von euch, einmal für das ganze Projekt | – (Paar entfällt) |
| Ausschuss | PhotoSort schlägt unscharfe, überbelichtete oder doppelte Fotos als Ausschuss vor. Du gehst die Vorschläge durch, korrigierst, wo nötig, und bestätigst mit „Ausschuss gesichtet, weiter“. | **beides** – du startest mit „Ausschuss aussortieren“, PhotoSort erkennt, du prüfst und bestätigst. | einer von euch, einmal für das ganze Projekt | der Scan – geprüft werden nur Fotos, die der Scan ins Projekt aufgenommen hat. |
| Klassifizierung | PhotoSort bewertet jedes Foto, das nach dem Ausschuss übrig ist, nach Qualität und Bildinhalt und bildet daraus eine Rangfolge je Foto-Moment. Darauf bauen Kuratierung, Album-Entwurf und Endauswahl auf. | **beides** – du startest mit „Klassifizierung starten“ und wählst, ob die Cloud-Bilderkennung mitläuft; den Rest erledigt PhotoSort. | einer von euch, einmal für das ganze Projekt | der bestätigte Ausschuss – damit aussortierte Fotos weder bewertet noch an den Cloud-Anbieter geschickt werden. |
| Kuratierung | Aus der Klassifizierung stellt PhotoSort einen Vorschlag zusammen, der alle Foto-Momente abdeckt und in jedem die vorkommenden Motive mischt. Wie groß er ungefähr wird, legst du bei Bedarf mit dem Richtwert fest. | **läuft von selbst** – den Richtwert kannst du ändern, musst du aber nicht. | – (Paar entfällt) | die abgeschlossene Klassifizierung – der Vorschlag baut auf ihrer Rangfolge auf. |
| Album-Entwurf | Hier steht der Vorschlag als dein eigener Entwurf. Du greifst nur ein, wo dich etwas stört – streichen, tauschen oder ein Foto hinzufügen –, und bestätigen musst du nichts. | **beides** – PhotoSort schlägt vor, du greifst ein. | jeder für sich – jeder von euch hat seinen eigenen Entwurf | die abgeschlossene Klassifizierung, denn aus ihr entsteht der Vorschlag. Darunter: „Ohne Cloud-Freigabe entsteht kein Album-Entwurf. Die Freigabe erteilst du in den Projekteinstellungen.“ + „Zu den Projekteinstellungen“ |
| Endauswahl | PhotoSort vergleicht eure beiden Album-Entwürfe und zeigt unter „Unterschiede“ die Fotos, bei denen ihr uneins seid. Darüber entscheidet ihr gemeinsam; die ganze Auswahl steht unter „Endauswahl“. | **braucht dich** – PhotoSort zeigt die Unterschiede, entscheiden müsst ihr. | ihr beide gemeinsam | die abgeschlossene Klassifizierung, denn ohne Vorschlag gibt es nichts zu vergleichen. Am meisten bringt sie, wenn ihr beide euren Album-Entwurf durchgesehen habt. |

Warum diese Kennzeichnungen:

- Kein Schritt startet von selbst. Scan, Ausschuss und Klassifizierung brauchen je einen Klick, wie im Worker und an den Schaltflächen der Schrittseiten zu sehen. „läuft von selbst“ wäre bei ihnen ein falsches Versprechen, deshalb tragen sie „beides“.
- Nur die Kuratierung rechnet ihren Vorschlag ohne Auslöser neu.

### Zustandswörter und Darstellung

Der Zustand steht immer als Wort **und** als Glyphe da, nie nur als Farbe. Die Marke entspricht der Schrittleiste; `istErledigt` wird durchgereicht, damit Haken vor Schloss gilt wie dort.

| Zustand | Marke (`StepMarker`) | Wort in der Kopfzeile | Aktion |
|---|---|---|---|
| erledigt | `erledigt` (Haken) | „erledigt“, `text-sm text-text` | „{Name} öffnen“, sekundär |
| aktuell | `aktuell` (Akzentrand, Nummer) | „aktuell“, `text-sm font-bold text-text-h` | „{Name} öffnen“, **primär** |
| offen | `ausstehend` (Nummer) | „offen“ | sekundär |
| gesperrt | `blockiert` (Schloss) | „gesperrt“ | keine; Sperrgrund-Zeile |
| abgeschaltet (nur Klassifizierung) | `blockiert` (Schloss) | „abgeschaltet“ | keine; Grund „Diese Funktion ist derzeit nicht aktiviert.“ |
| jederzeit möglich (Stationen) | keine Marke | „jederzeit möglich“ | sekundär |
| gesperrt (Stationen) | keine Marke | „gesperrt“ | keine; Sperrgrund-Zeile |
| läuft (zusätzlich) | – | `StatusTag status="running" label="läuft…"` (Spinner, `motion-reduce`) | unverändert |
| fehlgeschlagen (zusätzlich) | – | `StatusTag status="failed" label="fehlgeschlagen"` | unverändert |

- Das Wort „aktuell“ steht nicht in `--accent`, weil auf der gedrückten Fläche `--border` nur `--text`/`--text-h` zulässig sind. Den Akzent trägt die Marke. Alle Textfarben auf `--overlay` liegen in der Kontrastmatrix des Vertragstests.
- **Schrittleiste mit denselben Wörtern:** Der zugängliche Name in `Stepper.tsx` nennt statt „ausstehend“/„blockiert“ künftig „offen“/„gesperrt“, zum Beispiel „Schritt 3 von 4: Klassifizierung, gesperrt“. `StepMarkerAuspraegung` und `data-step-state` bleiben unverändert. Das „aktuell“ der Leiste bleibt eine Ortsangabe (Architektur §1).

### Klickverhalten

- Navigieren kann nur die Schaltfläche „{Name} öffnen“, nicht der ganze Eintrag. Wer beim Lesen tippt, um das Scrollen anzuhalten, darf nicht von der Übersicht wegspringen.
- Ziel und Merken „gesehen“ wie in Architektur §1/§3.
- Ein gesperrter oder abgeschalteter Eintrag hat kein Bedienelement und kein Popover. Sein Grund steht offen im Text, damit ist er ohne Fokus lesbar. Er liegt deshalb nicht in der Tab-Reihenfolge, anders als in der Schrittleiste, wo der Grund hinter dem Schritt verborgen ist.
- „Schließen“ und Esc schließen und führen zum nächsten anstehenden Schritt. Ein Klick auf den Hintergrund schließt nicht (Vorgabe des Grundelements).

### Auslöser auf den Schrittseiten

- Ort: Kopf von `ProjectPipelineLayout`. Der Kopf wird zu `flex items-start gap-3`, links `min-w-0 flex-1` (`h1 truncate` und Pfad wie bisher), rechts der Auslöser.
- Bedienelement: `Button variant="secondary" size="sm" className="shrink-0"` mit `<Icon name="info" size={16} />` und der sichtbaren Beschriftung **„Ablauf“**, `aria-haspopup="dialog"`. Kein eigenes `aria-label`, der Name ist das sichtbare Wort.
- Trefferfläche über das eingebaute `tap-target` (sichtbar 32 px, treffbar 44 px). Zur `h1` 12 px, die `h1` ist nicht bedienbar.
- Erscheint auf allen vier Schrittseiten an derselben Stelle. Der Fokus kehrt nach dem Schließen dorthin zurück, denn das Layout bleibt beim Wechsel zwischen Schritten eingehängt.

### Teilschritt `criteria`

`STEP_LABELS.criteria` = **„Qualität und Bildinhalt“**.

- Die Phase berechnet je Foto genau die Werte, die Einzelbild und Großansicht unter den Überschriften „Qualität“ und „Bildinhalt“ zeigen.
- Die anderen Teilschritte heißen nach ihrem Ergebnis oder ihrer Tätigkeit: „Kategorie-Vorschläge“, „Sehenswürdigkeits-Erkennung“, „Rangfolge“, „Personen-Erkennung“. Der neue Name passt dazu.
- Der Vorschlag „Bildmerkmale“ wurde verworfen: Das Wort kommt sonst nirgends in der Oberfläche vor.

### 360 px, Scrollen, Tastatur

- Dialogbreite `min(32rem, 100vw-2rem)` = 328 px, Inhaltsbreite 280 px.
- Längste Kopfzeile: Marke + „Klassifizierung“ + „abgeschaltet“ ≈ 260 px. Ein Lauf-Kennzeichen bricht über `flex-wrap` um.
- `<dl>`-Paare stehen unter `sm` untereinander. Kein Text unter 12 px, keine festen Breiten außer der Marke.
- **Scrollen nur im Inhaltsbereich:** Titelzeile, Beschreibung und die Zeile mit „Schließen“ bleiben stehen. Damit erreicht man „Schließen“ am Telefon mit einem Tipp, ohne vorher zu scrollen. Seitlich wird nie gescrollt. Das ist eine neue, allgemeine Regel des Grundelements, siehe Design-System „Überlagerungen“. Sie bedeutet eine Änderung an `components/ui/dialog.tsx` und gilt für alle Dialoge:
  - `<dialog>`: `open:flex open:flex-col`.
  - Inneres Gerüst: `min-h-0`; Kopf, Beschreibung und Schaltflächenzeile `shrink-0`.
  - `children` in einem Bereich `flex min-h-0 flex-col gap-6 overflow-y-auto -m-1 p-1`.
- Fokus und Tastatur:
  - Erstfokus liegt auf „Schließen“ (Grundelement). Ein Enter oder Esc schließt also sofort.
  - Tab läuft danach in DOM-Reihenfolge durch die Öffnen-Schaltflächen der Einträge, im Album-Entwurf erst „Album-Entwurf öffnen“, dann „Zu den Projekteinstellungen“.
  - Danach wieder „Schließen“, die Fokusfalle hält den Kreis geschlossen.
  - Weil zwischen den Schaltflächen nur kurze Texte stehen, rollt Tab den Inhaltsbereich mit.
- Touch und Tastatur bedienen dieselben Elemente. Keine Funktion hängt an Überfahren.

### Folgen für Test und Umsetzung (über Architektur §4 hinaus)

- `Stepper.tsx`: Zustandswörter im zugänglichen Namen „offen“/„gesperrt“. Mitzuziehen sind `Stepper.test.tsx` (wird für die Umbenennung ohnehin angefasst) und der Suchausdruck `/, blockiert$/` in `e2e/tests/tap-targets.spec.ts`.
- `components/ui/dialog.tsx`: Inhaltsbereich scrollt, siehe oben; dazu ein Fall in `dialog.test.tsx`. Die Prüfung in `no-horizontal-scroll.spec.ts` mit geöffnetem Dialog bei 360 px zeigt zusätzlich, dass „Schließen“ ohne Scrollen im Sichtbereich liegt.
- Auslöser „Ablauf“ und die Öffnen-Schaltflächen gehören in die Trefferflächenprüfung (`tap-targets.spec.ts`).

## Security

Einstufung: **sicherheitsrelevant, kein Blocker.** Es gibt kein Secret, keinen externen Dienst, keinen Cloud-Aufruf und keinen Bilddatenfluss. Fremdtext entsteht weder in einer Antwort noch in der Persistenz noch im Log. Neu sind:

- die Tabelle `project_overview_seen` (`user_id`, `project_id`)
- das Endpunktpaar `GET`/`PUT /projects/{project_id}/overview-seen` im eigenen Router `api/project_overview.py`
- ein Host in der `AppShell`, der auf jeder Projektroute ungefragt liest und beim Schließen schreibt
- ein e2e-Setup, das per API schreibt

Abgeglichen mit `specs/architecture/0003-securitykonzept.md`. Dort ist ein Abschnitt ergänzt (siehe Ende).

**S1 — Beide Endpunkte hängen am Router-Torwächter und stehen im Vollständigkeitstest. Jeder hat zusätzlich seinen eigenen 401-Fall.**

- `router = APIRouter(prefix="/projects", dependencies=[Depends(get_current_user)])`.
- `tests/test_auth_guard.py::_protected_router_operations()` führt `project_overview.router`. Der Eintrag `projects.router` deckt das gemeinsame Präfix **nicht** ab, weil der Test Router durchläuft und keine Pfade. Ohne den Eintrag wäre ein später ergänzter Endpunkt dieses Routers ungeprüft.
- `tests/test_api_project_overview.py` hat je einen pfadbenannten Fall „ohne Token → `401`“ für `GET` und für `PUT`.

**S2 — `user_id` kommt ausschließlich aus `get_current_user`.**

- Kein Body-Modell und kein Query-Parameter. Der `PUT` nimmt keinen Körper entgegen.
- Gelesen und geschrieben wird genau die Zeile `(current_user.id, project_id)`.
- Nachweis: Hat B eine Zeile, liefert `GET` für A trotzdem `seen: false`. Ein `PUT` von A lässt den Zustand von B unverändert. Ein mitgeschicktes `user_id` in Query oder Body ändert nichts.

**S3 — Den Zustand der anderen Person liefert keine Antwort.**

- Die Antwort ist genau `{"seen": bool}`: kein `user_id`, kein `username`, kein Zeitstempel.
- Kein Feld an `ProjectOut`. Das Objekt ist für beide Nutzer gleich, wird gepollt, und sein Client-Schlüssel `['project', id]` trägt keine Identität. Der `QueryClient` überlebt den Nutzerwechsel im selben Tab (bekannte Lücke im Sicherheitskonzept).
- Kein Listen-, Statistik- oder Logpfad über die Tabelle.
- `GET` ist frei von Nebenwirkungen und legt nie eine Zeile an.

**S4 — Unbekanntes Projekt heißt `404` wie überall, sonst nie `500`.**

- Beide Endpunkte prüfen das Projekt **vor** Lesen oder Schreiben.
- Status und `detail` („Projekt nicht gefunden.“) sind wortgleich mit `api/projects.py::_get_project_or_404`. Für ein unbekanntes Projekt gibt es nie `200 {"seen": false}` und nie `204`.
- Ein eigenes Enumerationsorakel entsteht nicht: Beide Nutzer sehen alle Projekte (`GET /projects`), und es gibt bewusst keine Eigentümerprüfung (Docstring an `api/projects.py`, Fotoliste).
- `project_id: int`. Eine nicht ganzzahlige Id ergibt `422`.
- `PUT`: Gefangen wird nur `IntegrityError` (zweiter Tab oder gleichzeitige Projektlöschung), kein breiteres `except`. Danach folgen `rollback`, eine erneute Projektprüfung und `404` bzw. `204`. Eine Zeile zu einem Projekt, das es nicht gibt, entsteht nie, denn der Fremdschlüssel ist auch in der Testdatenbank durchgesetzt (Spec 0350).

**S5 — Die Projektlöschung erfasst die Tabelle, andere Projekte und `users` bleiben.**

- `project_deletion.py::delete_projects` führt `delete(ProjectOverviewSeen).where(ProjectOverviewSeen.project_id.in_(project_ids))` vor `projects`. Dieselbe Funktion nutzt `demo_state.py::purge_demo_state`.
- Reihenfolge und Vollständigkeit sichern die beiden Metadatentests in `tests/test_project_deletion.py`.
- `build_project_graph` legt für **beide** Nutzer je eine Zeile an. Damit zeigt der Verhaltenstest das Entfernen. Die Zeilen des behaltenen Projekts bleiben stehen.

**S6 — Eine Projekt-Id aus der Adresszeile geht nur als geprüfte Ganzzahl in einen API-Pfad.**

- `matchProjectId` liefert den dekodierten Rohwert ohne Prüfung (`'abc'`; `%2F`/`%3F` kommen als `/` bzw. `?` an).
- Der Host wandelt genau einmal um: `Number.isInteger(n) && n >= 1`. Sonst setzt er **keine** Anfrage ab, weder Projekt noch `GET` noch `PUT`.
- `getOverviewSeen`/`markOverviewSeen` nehmen `projectId: number`, nie `string`.
- Bei Verletzung lenkt ein präparierter Link einen `PUT` mit Bearer-Token auf einen anderen Pfad derselben API um.
- Nachweis: Für `/projects/abc/...` und für eine Id mit kodiertem `/` gibt es keinen Aufruf von `apiFetch`.
- Der Nutzername aus `decodeUsername` im Abfrageschlüssel trennt nur den Cache und ist keine Zugriffsentscheidung.
- CSRF entfällt nach ADR 0005, der Transport läuft nur über den Bearer-Header. `GET` liest nur, `PUT` ist idempotent, die CORS-Konfiguration bleibt unverändert.

**S7 — Der Dialog zeigt nur festen Text.**

Inhalt sind ausschließlich:

- Konstanten aus `utils/workflowOverview.ts`
- `PIPELINE_STEPS`-Labels und Stationsnamen aus `utils/projectRoutes.ts`
- die Literale aus `getBlockedReason`
- feste Zustandswörter

Ausgeschlossen sind:

- Projektname, `error_message` eines Laufs und `detail` vom Server
- `dangerouslySetInnerHTML` und Markdown-Rendering

Linkziele entstehen aus festen Pfaden und der numerischen Id aus S6.

**S8 — e2e-Setup und Ad-hoc-Werkzeug markieren nur im Prüfstack.**

- `e2e/setup/auth.setup.ts` und `e2e/lib/adhoc.ts` rufen `GET /api/projects` und `PUT /api/projects/{id}/overview-seen` über `page.request` relativ zur Seiten-Origin auf. Diese Origin ist die allowlist-gebundene `BASE_URL` aus `e2e/lib/baseUrl.ts`; eine eigene API-Adresse gibt es nicht.
- Das Token kommt aus `localStorage` wie in `e2e/lib/draft.ts::authHeader`. Es wird weder geloggt noch in eine Datei außerhalb des bestehenden Sitzungszustands geschrieben.
- Markiert werden nur die Ids aus der Antwort derselben Sitzung, nur für `e2e-daniel`.
- Bei einer Antwort ungleich 2xx folgt ein harter Abbruch, die Meldung nennt nur den Status. Es gibt kein stilles Weiterlaufen.
- Die Zugangsdaten von `e2e-zweiter-nutzer` stehen als Konstante neben `DEMO_USERNAME`/`DEMO_PASSWORD` in `e2e/lib/auth.ts`. Sie gelten nur in der demo-geseedeten Datenbank, `docker-compose.e2e.yml` setzt sie. Keine Überschreibung per Umgebungsvariable.
- Für Screenshots mit geöffnetem Dialog gilt unverändert die Screenshot-Hygiene (Spec 0321).

**Ausdrücklich geprüft und ohne Befund:**

- Ein Rate-Limiting ist nicht nötig, das passt zur übrigen API.
- Keine neue Abhängigkeit.
- Die Umbenennung ändert nur Text: das 409-Detail in `api/projects.py` und die Demo-Fehlermeldung. Beide sind feste Literale.
- Der Service Worker cacht keine API-Antworten (`vite.config.ts` hat kein `runtimeCaching`). Bekommt `GET …/overview-seen` je eine Zwischenspeicherung, ein `ETag` oder `Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten.

**`specs/architecture/0003-securitykonzept.md`** ist ergänzt:

- Ein neuer Abschnitt vor „Bewusst akzeptierte Restrisiken“ mit zwei projektweiten Aussagen:
  - Eine Projekt-Id aus der Adresszeile geht nur als geprüfte Ganzzahl in einen API-Pfad.
  - Ein nur für den Eigentümer sichtbarer Zustand hat genau einen Lesepfad, `ProjectOut` bleibt nutzerunabhängig.
- Der Kopfvermerk.

Bei der Umsetzung kommt `project_overview` in die Ankerzeile „Auth-Torwächter als Router-Dependency“. Die Zeile „`user_id` ausschließlich aus dem JWT-Claim“ wird um den neuen `PUT` samt Nachweis ergänzt.

## Teststrategie

Der Grundsatz bleibt: jede Zusage auf der niedrigsten Ebene, die sie widerlegen kann. Die projektweiten Muster stehen als neue Sektion „#566“ (Muster 1–7) im Testkonzept, hier nur die Zuordnung.

**Backend (pytest, `test_api_project_overview.py`)**
- **Person und Projekt:** eine Matrix Person × Projekt. A merkt P; erwartet ist „gesehen“ nur für (A, P), nicht für (B, P) und (A, Q).
- **Gerätewechsel:** ein zweiter Client mit frisch ausgestelltem Token derselben Person sieht (A, P) als gesehen.
- **Anlegen:** Ein Projekt, das B über `POST /projects` anlegt, ist für beide ungesehen.
- **„Anderer Tag“:** Die Spaltenmenge der Tabelle ist exakt `{user_id, project_id}`; es gibt also nichts, was verfallen könnte.
- **Rückgabewerte:** `PUT` ist idempotent (zweimal `204`, eine Zeile). Unbekanntes oder gelöschtes Projekt ergibt `404` bei GET und PUT.
- **Zugriffsschutz:** Der Router kommt in `test_auth_guard.py::_protected_router_operations()` und bekommt zusätzlich einen eigenen 401-Fall. Keine Antwort nennt den Stand der anderen Person.
- **Gleichzeitiges Schreiben:** Der `IntegrityError`-Zweig wird mit einer echten Zwischenschreibung zwischen Prüfung und Einfügen betreten, mit Zähler als Nachweis. Zweiter Tab ergibt `204` und eine Zeile, Projekt gelöscht ergibt `404`, nie `500`. Nach jedem `204` existiert die Zeile.
- **„Ändert nichts am Projekt“:** Schnappschuss aller Tabellen vor und nach dem `PUT`; einzige Differenz ist eine Zeile in `project_overview_seen`.
- **Löschen:** Die bestehende Vollständigkeitsprüfung in `test_project_deletion.py` greift automatisch.
- **Umbenennung:** Die 409-Meldung und die Demo-Fehlermeldung werden an ihrem Endpunkt bzw. im Demo-Zustand geprüft. Dazu kommt eine Abwesenheitsprüfung über `ast` für alle Zeichenketten außer Docstrings in `backend/src/photosort` (ohne die Betreiber-CLIs `*_probe.py`), mit Gegenprobe.

**Frontend (vitest)**
- **Gleichlauf:** Das 256-Lagen-Kreuzprodukt aus Spec 0375 wird als gemeinsamer Testhelfer genutzt. Je Lage wird verglichen, was die drei Anzeigen ausgeben: der „aktuelle“ Schritt der Übersicht gegen den Schritt der Stand-Zeile und gegen das Weiterleitungsziel, außerdem der Lauf. Die beobachteten Zustände je Eintrag werden in beide Richtungen gegen eine Erwartungstabelle gehalten:

  | Eintrag | erwartete Zustände |
  |---|---|
  | Scan | aktuell, erledigt |
  | Ausschuss | aktuell, offen, erledigt |
  | Klassifizierung | aktuell, offen, erledigt, gesperrt, abgeschaltet |
  | Kuratierung | aktuell, offen, gesperrt |
  | Album-Entwurf, Endauswahl | jederzeit möglich, gesperrt |

  Zusätzlich wird je beobachteter Klasse eine Vertreterlage mit Schrittleiste und Dialog im selben DOM gerendert. Verglichen werden die Glyphe je Schritt (`data-glyph`), der Sperrgrund aus dem Popover der Leiste gegen den Dialogtext und die Zustandswörter aller Schritte außer der aktuellen Leistenposition. Randfall C ist ein eigener Fall.
- **Inhalt:**
  - Die Schrittnamen der Übersicht sind exakt gleich der Liste der Schrittleiste, und jeder Eintrag hat höchstens zwei Sätze.
  - Kennzeichnung, Zuständigkeit und Vorbedingung bekommt je Eintrag einen Tabellentest.
  - Der Cloud-Hinweis ist der importierte Text aus dem Album-Entwurf, und der Link zeigt auf die Einstellungen.
  - Zitierte Bezeichnungen müssen als Literal im Quellbaum stehen.
- **Bedienung:**
  - Je erreichbarem Eintrag gibt es genau eine Schaltfläche mit dem richtigen Ziel; gesperrte Einträge haben kein Bedienelement.
  - Esc und „Schließen“ landen auf dem nächsten Schritt.
  - Der Auslöser „Ablauf“ ist auf allen vier Schrittseiten derselbe DOM-Knoten. Das belegt „immer an derselben Stelle“ ohne e2e.
  - Ein `aria-live` gibt es im Dialog nicht.
  - Die Tab-Reihenfolge durch die Öffnen-Schaltflächen wird geprüft. Was das Dialog-Grundelement selbst zusagt, wird nicht wiederholt.
- **Wann sie erscheint (Host, App-Ebene):**
  - Parametrisiert über alle Routen aus `PROJECT_ROUTE_PATHS`; die Fall-Liste muss als Menge gleich der Konstante sein.
  - Gegenprobe auf Routen ohne Projektbezug: kein Leseaufruf, kein Dialog.
  - Kein Erscheinen, solange das Projekt lädt, bei `404` oder bei nicht-ganzzahliger Id.
- **Fehlerfälle beim Lesen:** Ein Fehler lässt die Übersicht erscheinen, mit genau einem Aufruf ohne Wiederholung. Eine verspätete Antwort „gesehen“ lässt sie in keinem Commit aufblitzen.
- **Fehlerfälle beim Schreiben:** keine Meldung (`alert`/`status` leer), die Navigation findet trotzdem statt, und in derselben Sitzung erscheint die Übersicht nicht erneut. Nach Neuladen (frischer `QueryClient`) erscheint sie wieder.
- **Anfragefolge:** Ein Spion auf `apiFetch` zeigt: Die einzige schreibende Anfrage ist `PUT …/overview-seen`. Nichts wird in `localStorage` oder `sessionStorage` geschrieben.
- **Hook:** Der Test von `useOverviewSeen` läuft mit `new QueryClient()` ohne Vorgaben. Der Test-Standard des Projekts setzt bereits `retry: false`; damit würde ein vergessenes `retry: false` im Hook nicht auffallen. Polls des Projekts lösen keinen zweiten Leseaufruf aus. Nach einem Wechsel der angemeldeten Person wird ihr Cache nicht weiterverwendet.
- **Umbenennung, mechanischer Beleg:** Eine Prüfung über den Syntaxbaum (`ts.createSourceFile`) erfasst alle String- und Template-Literale, JSX-Texte und JSX-Attribute in `frontend/src` ohne Testdateien.
  - Gesucht wird nach `/Kriterien[-\u2010\u2011\u00AD\s]*Bewertung/i` und nach `Kategorie-Bewertung`; erwartet sind null Treffer.
  - Die Gegenprobe im selben Test findet den Begriff je Knotenart und nicht in einem Kommentar.
  - Ein Regex über ganze Literale, wie bei #558, reicht nicht: „Zur Kriterien-Bewertung“ ist JSX-Text und damit kein Literal.
  - Teilschritt-Namen sind paarweise verschieden, keiner ist gleich dem Schrittnamen. Die Statuszeile wird über alle Laufphasen parametrisiert.
  - Bestehende Tests zu Schrittzuständen und Sperrregeln bleiben bis auf den Wortlaut unverändert (Nachweis ohne Rot-Grün).

**e2e (Playwright)**
- **Setup, das für bestehende Tests „gesehen“ markiert:** `auth.setup.ts` markiert als `e2e-daniel` alle Projekte aus `GET /api/projects`. Danach sichert es je Projekt „gesehen“ zu, bei einer Anzahl exakt gleich der Projektliste und größer null. Ohne dieses Setup würden die bestehenden Treffertests unter dem Dialog rot; das ist zugleich der Rot-Nachweis.
- **Ad-hoc-Werkzeuge:** `ensureAuthState` markiert bei jedem Aufruf, nicht nur beim Neuanmelden. Ein Neu-Seeden legt die Projekte mit neuen Ids und ohne Merker neu an, und heute kehrt die Funktion bei vorhandenem Anmeldezustand vorher zurück.
- **360 px:** Geprüft wird in `no-horizontal-scroll` am Projekt „Demo — Fehlerzustand“ mit geöffnetem Dialog. Dort sind die Kopfzeilen mit Lauf-Kennzeichen am längsten.
  - Vorbedingung: Der Inhaltsbereich hat tatsächlich mehr Inhalt, als in ihn passt.
  - Geprüft wird: Seite und Dialog ohne seitlichen Überstand. „Schließen“ liegt vor und nach dem Scrollen im Bild.
- **Touch:** „Ablauf“, die Öffnen-Schaltflächen und „Schließen“ kommen in `tap-targets`. Im mobilen Viewport werden Öffnen und Schließen einmal per `tap()` ausgeführt. Der Ausdruck `/, blockiert$/` in `tap-targets` wird zu `/, gesperrt$/`.
- **Kein schreibender e2e-Fall mit `e2e-zweiter-nutzer`:** Das erste Erscheinen ist in jsdom belegt. Ein solcher Fall ließe sich mangels `DELETE` nur einmal je Seed ausführen.

**Testkonzept:** Ja, es musste ergänzt werden, und das ist erledigt:
- neue Sektion „#566“ mit den Mustern 1–7;
- ein Satz zum Setup-Projekt im Verlässlichkeitsregime;
- zwei benannte Lücken: der Wortschatz-Teil ist nur zum Teil mechanisch belegbar, und ein zweiter offener Tab derselben Person zeigt die Übersicht noch einmal;
- Datum aktualisiert.

**Was nicht automatisch prüfbar ist:** „Alltagssprache“ und „keine geführte Tour“ bleiben Sichtprüfung in `review-ux`.

## Entscheidungen

- „Aktuell“ in der Übersicht ist der nächste anstehende Schritt (Bedingung von `deriveProjectStand`), nicht der per URL geöffnete; „aktuell“ in der Schrittleiste bleibt Ortsangabe.
- Album-Entwurf und Endauswahl sind erreichbar genau dann, wenn die Kuratierung erreichbar ist; davor „gesperrt“ mit dem Sperrgrund der Kuratierung.
- „Gesehen“ wird beim Schließen bzw. beim Klick auf einen Eintrag gemerkt, nicht beim Anzeigen; ein Neuladen bei offener Übersicht zeigt sie erneut.
- Kein Zeitstempel in `project_overview_seen`; kein Feld an `ProjectOut`.
- Kennzeichnung: Scan, Ausschuss, Klassifizierung „beides“ (starten nur per Klick), Kuratierung „läuft von selbst“ ohne Zuständigkeitsangabe, Album-Entwurf „beides“, Endauswahl „braucht dich“.
- Teilschritt `criteria` heißt „Qualität und Bildinhalt“.
- Zugänglicher Name der Schrittleiste nennt „offen“/„gesperrt“ statt „ausstehend“/„blockiert“, damit Leiste und Übersicht dieselben Zustandswörter tragen.
- Das Dialog-Grundelement `components/ui/dialog.tsx` bekommt einen scrollenden Inhaltsbereich (gilt für alle Dialoge).
- `utils/projectRoutes.ts` führt bisher kein Label „Album-Entwurf“; die Umsetzung legt genau eine Quelle für beide Stationsnamen an, gegen die Übersicht und Test binden.
- `e2e/lib/adhoc.ts::ensureAuthState` markiert bei jedem Aufruf, nicht nur beim Neuanmelden.
- Sichtbares „Remote-Kategorisierung“ (`worker.py`, `ProjectStatsPage.tsx`, `ProjectSettingsPage.tsx`) bleibt: Es benennt die Cloud-Teilfunktion, nicht den Schritt, und kein Akzeptanzkriterium verlangt die Änderung.
- Kein ADR: Zuordnungstabelle nach bestehendem Nutzer-×-Objekt-Muster, keine neue Technologie.
- architect, ux-ui-designer, test-engineer und security-engineer konsultiert; keine Konsultation übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Änderungen an der Pipeline selbst (Schritte, Regeln, Sperren).
- Eine geführte Tour mit Hervorhebungen.
- Anzeige, ob die andere Person die Übersicht gesehen hat.
- Umbenennung interner Kennungen (`kriterien`, `criteria`) und der Route.
