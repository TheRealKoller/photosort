# 0568 - Schrittseiten: eindeutige Beschriftungen, eine Hauptaktion, Weiterführung

**Status:** Accepted
**Erstellt:** 2026-10-04
**Bezug:** [Issue #568](https://github.com/TheRealKoller/photosort/issues/568)

Umfang über dem Richtwert von ~200 Zeilen, weil vier Schrittseiten mit je eigenen Zuständen, Wortlauten und Messungen in einer Spec stehen.

## Ziel

Auf den Schrittseiten eines Projekts (Scan, Ausschuss, Klassifizierung, Kuratierung) ist nicht erkennbar, was ein Knopf tut, welcher Knopf jetzt der nächste ist und wie es nach einem Schritt weitergeht. Beispiele aus dem Alltag:

- „Ausschuss aussortieren" sortiert nichts aus, sondern erkennt nur Vorschläge.
- Nach dem ersten Klick bleibt derselbe Knopf unverändert stehen; unklar ist, warum und was er jetzt tut (er startet eine neue Erkennung).
- Der Abschluss-Knopf des Ausschusses steht unter dem langen Fotoraster, Start- und Abschluss-Knopf sehen gleichrangig aus.
- „Ausschuss gesichtet, weiter" führt nicht weiter — man bleibt auf derselben Seite.

Ziel ist, dass beide Nutzer jeden Schritt ohne Deuten und Suchen durchgehen können: Die Beschriftung sagt, was passiert; es gibt immer genau eine erkennbare nächste Aktion; und nach dem Abschluss eines Schritts geht es ohne Suchen zum nächsten.

## User Story

Als Nutzer, der ein Projekt Schritt für Schritt vom Scan bis zum Album-Entwurf bringt, möchte ich auf jeder Schrittseite erkennen, was ein Knopf tatsächlich tut, ob ich einen Schritt zum ersten Mal oder erneut ausführe und welche Aktion jetzt die nächste ist, und nach dem Abschluss eines Schritts ohne Suchen zum nächsten gelangen — damit ich den Ablauf durchgehen kann, ohne Knöpfe zu deuten oder zu scrollen.

## Akzeptanzkriterien

Aus der Story übernommen und von `test-engineer` auf Testbarkeit geschärft; Schärfungen sind **fett**.

**Übergreifend**

- [ ] Jeder Startknopf nennt die Tätigkeit seines Laufs als Verb mit Gegenstand. **Ein Knopf, der nur Vorschläge erzeugt, enthält keines der Wörter „aussortieren“, „löschen“ oder „übernehmen“.**
- [ ] Während ein Lauf läuft, zeigt der gesperrte Knopf dieselbe Tätigkeit wie der Startknopf in der Verlaufsform **(beides aus derselben Konstante in `stepActionTexts.ts`)**. Die Statuszeile nennt den Schritt nur mit seinem Namen aus `PIPELINE_STEPS`.
- [ ] Solange ein Schritt keinen erfolgreichen Lauf hat, ist sein Startknopf die Hauptaktion **und es gibt keinen „Erneut …“-Knopf**. Nach einem erfolgreichen Lauf heißt der Knopf „Erneut <Verb des Startknopfs>“ und ist nachrangig gestaltet. Daneben steht ein Erklärsatz, der **ohne Hover, Aufklappen oder Fokus im DOM sichtbar ist** und sagt, was ein neuer Lauf bewirkt, auch für einen bestehenden Abschluss und für die Folgeschritte. **Beim Ausschuss zählt ein erfolgreicher Erkennungslauf auch ohne Bestätigung.**
- [ ] Auf jeder Schrittseite ist in jedem Zustand **der Tabelle höchstens ein Bedienelement als Hauptaktion gestaltet**. Ein Startknopf und eine Abschluss-Aktion sind nie beide Hauptaktion.
- [ ] Die Hauptaktion liegt beim Aufruf der Seite **bei 360 px und bei Desktop-Breite vollständig im Sichtbereich und ist treffbar** (`elementFromPoint`), unabhängig von der Zahl der Bilder. **Beim Scrollen bis zum Seitenende verdeckt sie weder die letzte Rasterzeile noch „Mehr laden“.**
- [ ] Ist der letzte Lauf eines Schritts fehlgeschlagen, gibt es auf der Seite genau einen Knopf, der den Lauf wiederholt. **Lade-Alerts mit „Erneut versuchen“, etwa für Bestand oder Schätzung, zählen nicht dazu.**
- [ ] Der Sperrgrund eines gesperrten Schritts in der Schrittleiste enthält die Beschriftung des zugehörigen Knopfs **wörtlich (ohne Anzahl)** und nicht das Wort „oben“.
- [ ] Der dritte Schritt heißt überall „Klassifizierung“. **Die Fassungen „Kriterien-Bewertung“, „Ausschuss aussortieren“, „Wird aussortiert…“, „Ausschuss gesichtet, weiter“ und „Aktualisieren“ (als Scan-Knopf) kommen in keinem Text der Oberfläche mehr vor.** Nennt die Ablauf-Übersicht aus #566 Handlungen, verwendet sie dieselben Konstanten.

**Hauptaktion je Schritt und Zustand**

| Schritt | nie gelaufen | läuft | fehlgeschlagen | erfolgreich |
|---|---|---|---|---|
| Scan | Fotos einlesen | keine (Fortschritt) | eine Wiederholung | „Weiter zum Ausschuss"; nachrangig „Erneut scannen" mit Erklärung |
| Ausschuss | Vorschläge erkennen | keine (Fortschritt) | eine Wiederholung | Abschluss offen oder Vorschläge offen: Abschluss-Aktion. Abgeschlossen und nichts offen (auch automatisch bei null Vorschlägen): „Weiter zur Klassifizierung". Jeweils nachrangig „Erneut erkennen" mit Erklärung |
| Klassifizierung | Klassifizierung starten | keine (Fortschritt) | eine Wiederholung | „Weiter zur Kuratierung"; nachrangig „Erneut klassifizieren" mit Erklärung und Kostenschätzung |
| Kuratierung | – | – | – | „Album-Entwurf öffnen" |

Die genauen Wortlaute legt die Umsetzung fest; die Tabelle legt fest, welche Aktion jeweils die Hauptaktion ist.

**Ergänzungen zur Tabelle:** **Ergänzungen:** (a) „läuft“ umfasst auch die Zeit zwischen dem Klick und der ersten Laufantwort (lokal ausgelöst). (b) Beim Ausschuss gilt die Abschluss-Aktion, wenn `gate_confirmed_at` leer ist oder noch Vorschläge offen sind. Solange die Zahl der offenen Vorschläge nicht geladen ist, steht die Abschluss-Aktion ohne Anzahl da. (c) Die Beschriftung ist bei Start und Wiederholung dieselbe. **(d) Ist der letzte Lauf fehlgeschlagen, gibt es keinen „Erneut …“-Knopf, auch wenn ein früherer Lauf erfolgreich war — sonst stünden zwei Wiederholungen da.**

**Scan**

- [ ] Bei einem nie gescannten Projekt sagt der Startknopf, dass die Fotos des verknüpften Ordners eingelesen werden. Der Knopf „Aktualisieren“ fehlt **in jedem Zustand**.
- [ ] Der Erklärsatz bei „Erneut …“ nennt neue, geänderte und entfernte Fotos und die Folge für einen bereits abgeschlossenen Ausschuss. *(Offener Punkt aus UX: Die fachliche Aussage dazu ist [INFERENCE] und muss bestätigt sein, bevor ein Test sie wörtlich festschreibt.)*

**Ausschuss**

- [ ] Startknopf oder Erklärzeile sagen ausdrücklich, dass noch nichts aussortiert wird.
- [ ] Die Abschluss-Aktion nennt die Zahl N der offenen Vorschläge **(Singular bei N = 1)**. Bei N = 0 oder unbekanntem N nennt sie nur das Abschließen.
- [ ] Die Abschluss-Aktion liegt **in drei Lagen** im Sichtbereich und ist treffbar: beim Aufruf, nach dem Scrollen ans Ende, nach einmal „Mehr laden“ und erneutem Scrollen ans Ende. **Das gilt auch in der Detailansicht (`?photo`) bei 360 px. Dort verdeckt die Leiste die Entscheidungsknöpfe und „Schließen“ nicht.**
- [ ] Ist der Schritt abgeschlossen und nichts offen, steht an der Stelle der Hauptaktion **ein Link** „Weiter zur Klassifizierung“ und kein gesperrter Knopf. Die Zeile mit dem Bestätigungszeitpunkt bleibt sichtbar.
- [ ] Erklärsatz zu „Erneut erkennen“: unverändert, enthält alle vier Aussagen.
- [ ] Null Vorschläge mit Auto-Abschluss: `AUSSCHUSS_EMPTY_TEXT` bleibt **auch nach einem Neuladen der Seite** stehen. Die Hauptaktion ist der Weiter-Link.

**Klassifizierung**: unverändert, dazu: **„Erneut klassifizieren“ und „Klassifizierung starten“ werden durch dieselbe Bedingung (`isTriggerDisabled`) gesperrt.** Bei Cloud-Nutzung steht `ClassificationEstimate` sowohl beim Startknopf als auch im RerunBlock.

**Kuratierung**: unverändert, dazu: **Es gibt kein Element `button`, dessen Name mit Start, „Erneut“ oder Abschluss beginnt. „Album-Entwurf öffnen“ ist ein Link.**

**Weiterführung nach Abschluss**

- [ ] Ziel der Weiterführung ist immer der nächste Schritt in der Reihenfolge.
- [ ] Ist die Ausschuss-Bestätigung erfolgreich (auch eine erneute), wechselt die Ansicht ohne Klick zu `/pipeline/kriterien`. **Der Wechsel kommt erst, wenn das Projekt nach der Bestätigung neu geladen ist. Die Ansicht springt nicht über den Guard zurück zum Ausschuss.** Er geschieht nur, wenn die Ausschussseite beim Eintreffen der Antwort noch angezeigt wird. **Browser-Zurück führt zur Ausschussseite, aus der Detailansicht zur Detailansicht derselben Aufnahme. Nach dem Wechsel liegt der Fokus auf der Überschrift der Klassifizierung. Bei einem normalen Aufruf der Klassifizierung wird der Fokus nicht gesetzt.**
- [ ] Endet ein Hintergrundlauf erfolgreich, wechselt die URL nicht. Der Weiter-Link wird Hauptaktion, und das Ergebnis bleibt sichtbar.
- [ ] Der Weiter-Link nennt den nächsten Schritt mit Namen. **Er erscheint auch beim erneuten Aufruf der Seite, weil er aus dem Zustand abgeleitet wird. Sein Klick löst keine Schreibanfrage aus.**
- [ ] Wer einen erledigten Schritt über die Schrittleiste oder die Adresse aufruft, bleibt dort **(keine Weiterleitung)**. Erneut bestätigen und erneut laufen lassen bleiben möglich.
- [ ] Ist der nächste Schritt nicht erreichbar (Klassifizierung abgeschaltet), gibt es keinen Wechsel und keinen Weiter-Link, sondern einen neutralen Text **ohne `role="alert"`**. Schlägt die Ausschuss-Bestätigung fehl, bleibt die URL gleich und der Fehler-Alert bleibt stehen, **bis eine neue Bestätigung ausgelöst wird. Der Fokus bleibt auf der Abschluss-Aktion.**

**Abgrenzung**: unverändert, dazu: **Erneute Läufe öffnen keinen Dialog. Backend und API sind nicht im Diff.**

## Datenmodell-Bezug

Keiner. Backend, API und Datenmodell bleiben unverändert.

## Architektur / Umsetzung

Reine Frontend-Story. Backend, API und Datenmodell bleiben unberührt: `computeStepStates`, `getFrontierStepId`, die Erreichbarkeit und die Schreibwege aus ADR 0121 (`confirm-ausschuss-gate`) ändern sich nicht. Neu sind eine reine Ableitung „Hauptaktion je Schritt und Zustand“, zwei gemeinsame Bausteine und die Navigation nach der Ausschuss-Bestätigung.

### 1. Texte und Ableitung (reine Logik, ohne React)

- **Neu `frontend/src/utils/stepActionTexts.ts`** (Blattmodul, nur Konstanten): Für jeden Schritt stehen hier die Startbeschriftung, die Verlaufsform, die „Erneut …“-Beschriftung mit Erklärsatz, die Beschriftung der Abschluss-Aktion (mit und ohne Anzahl), die Weiter-Beschriftung („Weiter zur Klassifizierung“ …) und der neutrale Text „nächster Schritt nicht erreichbar“. Alle Stellen, die eine Aktion nennen, lesen diese Datei: Seiten, `getBlockedReason`, `OVERVIEW_TEXTS`. Ein eigenes Blattmodul ist nötig, weil `pipelineSteps.ts` (Sperrgründe) und die neue Ableitung beide darauf zugreifen; ohne es entstünde ein Importzyklus.
- **Neu `frontend/src/utils/stepActions.ts`**: `deriveStepAction(stepId, project, { openCount, isTriggerPending })` liefert eine Union für die eine Hauptaktion:
  - `start`
  - `running` (Verlaufsform, Fortschritt)
  - `retry` (genau eine Wiederholung)
  - `confirm` (mit `openCount`)
  - `next` (`to` als Pfad und Beschriftung)
  - `nextUnavailable` (neutraler Text)
  - `open` (Kuratierung: „Album-Entwurf öffnen“)

  Dazu kommt `rerun: { label, explanation } | null`. `rerun` gibt es genau dann, wenn der Schritt einen erfolgreichen Lauf hat; beim Ausschuss ist das ein erfolgreicher Lauf auch ohne Bestätigung. Die Ableitung baut auf `computeStepStates` auf: Ob es weitergeht, zeigt `isReachable` des Folgeschritts. Eine eigene Erreichbarkeitsregel bekommt sie nicht (so wie es in `deriveWorkflowOverview` schon heute dokumentiert ist).
  - **Ausschuss:** `openCount` stammt aus `useAusschussQuery`, ist also nicht im `ProjectOut` enthalten. Solange es nicht geladen ist, ist der Wert `null`; die Ableitung zeigt dann `confirm` ohne Anzahl. `confirm` gilt, solange `gate_confirmed_at === null || openCount > 0`. Sonst gilt `next` oder `nextUnavailable`, also auch dann, wenn ein Lauf ohne Vorschläge den Schritt selbst bestätigt hat.
  - **`isTriggerPending`:** Damit wird der lokale Zustand der Mutation bzw. `useTriggerConfirmation` als `running` abgebildet. Die Seiten enthalten danach keine eigenen Zustandsbedingungen mehr.
- **Tests:** Ein Tabellentest gegen die Tabelle „Hauptaktion je Schritt und Zustand“, nach dem Muster von `workflowOverviewStates.test.ts`, das den Eingaberaum vollständig aufzählt. Er prüft: höchstens eine Hauptaktion, `rerun` nur nach einem Erfolg, bei einem Fehlschlag genau `retry`, kein `next` bei nicht erreichbarem Folgeschritt.

### 2. Gemeinsame Bausteine (`frontend/src/components/`)

- **`StepActionBar.tsx`** ist die haftende Fußleiste und rendert eine `StepAction`. Statuszeile und Hauptaktion stehen in ihr: mobil untereinander, Hauptaktion in voller Breite; ab `sm` links die Statuszeile als farbiger Text, rechts die Aktion. Für `next` und `open` rendert sie `<Button asChild><Link to=…>`, also echte Links. Für `running` zeigt sie die gesperrte Schaltfläche in der Verlaufsform mit `busy` und `Progress`.
  - **Haften ohne verdeckte letzte Rasterzeile:** Die Leiste nutzt `sticky bottom-0 z-10 border-t border-separator bg-bg` (deckend, wie die Kopfzeile in `App.tsx`) und ist das **letzte Element im Fluss** der Schrittseite. Sie ist kein `fixed`-Element. Weil sie ihren eigenen Platz im Fluss behält, schiebt sie die letzte Rasterzeile und „Mehr laden“ beim Scrollen bis zum Ende über sich. Einen Ausgleichsabstand in Leistenhöhe (Penpot-Lücke `haftleiste`) braucht es deshalb nicht. Dazu kommt `pb-[env(safe-area-inset-bottom)]` für Telefone. Auflage: Kein Vorfahr zwischen Leiste und Viewport darf `overflow` setzen; das ist heute im Layout erfüllt.
- **`RerunBlock.tsx`** sitzt im Schrittkopf unter der Erklärzeile. Er zeigt `Button variant="outline" size="sm"` mit der „Erneut …“-Beschriftung und den Erklärsatz als Text, der immer sichtbar ist (kein Tooltip). Ein optionaler `children`-Platz nimmt bei der Klassifizierung `ClassificationEstimate` auf. Es gibt keinen Bestätigungsdialog.
- **Fehlschlag:** `Alert` wird **ohne** `onRetry` gerendert, die einzige Wiederholung ist die `retry`-Aktion der Leiste. Betroffen sind `AusschussStepPage` (Zeile mit `scoringStatus === 'failed'`), `ScanStepPage` und `ClassificationSection` (die Alerts für Lauf- und Auslösefehler). Alerts mit `onRetry` für das *Laden* (Ausschuss-Bestand, Schätzung, Feinlabels) bleiben, weil sie keine Laufwiederholung sind.

### 3. Seiten

- **`ScanStepPage.tsx`, `AusschussStepPage.tsx`:**
  - Der Startknopf oben und die Statuszeile `aria-live` wandern in `StepActionBar`. Der Kopf bekommt `RerunBlock`.
  - Im Ausschuss entfällt der Abschluss-Knopf unter dem Raster samt `AUSSCHUSS_CONFIRM_TEXT`.
  - Die Bestätigungszeile mit Zeitpunkt und der dauerhafte Text für „keine Vorschläge“ (`AUSSCHUSS_EMPTY_TEXT`) bleiben im Inhalt stehen.
  - Die Fehlermeldung der Bestätigung (`confirmMutation.isError`) steht unmittelbar über der Leiste.
  - Die Detailansicht (`?photo`) zeigt die Leiste ebenfalls, weil die Abschluss-Aktion auf der Seite immer erreichbar sein muss.
- **`KriterienStepPage.tsx` / `components/ClassificationSection.tsx`:** Der Auslöser („Klassifizierung starten“) und die Laufstatuszeile wandern in die `StepActionBar` am Ende von `ClassificationSection`; die Seite bleibt eine reine Verdrahtung. Ergebnis-Bilanz, Cloud-Auswahl und Feinlabels bleiben im Inhalt. Die Sperrlogik `isTriggerDisabled` für die Kostenschätzung gilt unverändert für Start, `retry` und Erneut. Bei gewählter Cloud-Nutzung steht `ClassificationEstimate` bei jedem Auslöser, auch im `RerunBlock`.
- **`KuratierungStepPage.tsx`:** „Album-Entwurf öffnen“ wird aus `SelectionTargetField.action` herausgenommen und als `open` in `StepActionBar` gesetzt. Es ist die einzige Hauptaktion; `SelectionTargetField` bekommt dort kein `action` mehr.
- **`ProjectPipelineLayout.tsx`, `PipelineStepView.tsx`:** keine Änderung (Guard und Zuordnung bleiben).

### 4. Navigation

- **Nur nach erfolgreicher Ausschuss-Bestätigung:** In `AusschussStepPage` wird `confirmMutation.mutate(undefined, { onSuccess })` aufgerufen. Die Callbacks *je Aufruf* von TanStack Query laufen nach dem Unmount nicht mehr. Damit ist „nur solange man noch auf der Ausschussseite ist“ ohne eigenen Merker erfüllt.
  - In `onSuccess` zuerst `const { data } = await refetchProject()`. Erst danach, falls `computeStepStates(data)` die Klassifizierung als erreichbar meldet, `navigate(`/projects/${id}/pipeline/kriterien`)` **ohne** `replace` (Push, Browser-Zurück führt zur Ausschussseite).
  - Ein Wechsel vor dem Refetch liefe in den Guard des Layouts: Der läse noch `gate_confirmed_at === null` und leitete mit `replace` zurück. Die Invalidierung in `useConfirmAusschussGateMutation` wird nicht abgewartet und reicht dafür nicht.
  - Ist die Klassifizierung nicht erreichbar (abgeschaltet), wechselt die Seite nicht; `deriveStepAction` liefert `nextUnavailable`. Bei einem Fehler wird nicht gewechselt, und `Alert` bleibt stehen.
- **Kein Wechsel nach Hintergrundläufen:** Scan, Klassifizierung und Erkennung ohne Vorschläge rufen nirgends `navigate`. Der Poll ändert `project`, die Ableitung liefert `next`, und die Leiste zeigt den Weiter-Link. Den gibt es auch bei einem späteren Aufruf, weil er aus dem Zustand abgeleitet wird und nicht aus einem Ereignis. Ein Weiter-Link startet nichts.

### 5. Beschriftungen außerhalb der Seiten

- **`utils/pipelineSteps.ts::getBlockedReason`:** Ohne Ortsangabe „oben“. Der Text nennt die Aktion mit der Konstanten aus `stepActionTexts.ts`, z.B. Kriterien: „Bestätige zuerst den Ausschuss“ → die Beschriftung der Abschluss-Aktion; Kuratierung → die Startbeschriftung der Klassifizierung. Die Folgen in `pipelineSteps.test.ts`, `workflowOverviewStates.test.ts`, `Stepper.test.tsx` und `WorkflowOverviewDialog` (Sperrgrund wortgleich) gehen mit; die Gleichlauf-Tests prüfen das bereits strukturell.
- **`utils/workflowOverview.ts::OVERVIEW_TEXTS`:** Wo der Text Handlungen nennt, nutzt er die Konstanten bzw. dieselben Wortlaute. Der Schrittname „Klassifizierung“ steht schon in `PIPELINE_STEPS`; sichtbare Restfassungen wie „Kriterien-Bewertung“ und „Ausschuss aussortieren“ werden per grep im Frontend ersetzt.

### 6. Reihenfolge

1. `stepActionTexts.ts` und `stepActions.ts` samt Tabellentest
2. `getBlockedReason` und `OVERVIEW_TEXTS` auf die Konstanten umstellen
3. `StepActionBar` und `RerunBlock` mit Komponententests
4. Ausschuss inklusive Navigation, danach Scan, Klassifizierung, Kuratierung
5. E2E-Messung analog `e2e/tests/sticky-header.spec.ts`: Hauptaktion ohne Scrollen sichtbar (mobil/desktop) und letzte Rasterzeile am Ende nicht verdeckt; jsdom kann Sticky nicht messen.

Kein ADR: Es kommt weder eine neue Technologie noch eine Abhängigkeit noch eine Änderung am Datenmodell hinzu. Die haftende Leiste nutzt dasselbe CSS-Sticky-Muster wie Kopfzeile und Schrittleiste, nur am unteren Rand.

## UI/UX

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Schrittseite
**Schlüssel:** schrittseite

Schlüssel geprüft: erfüllt `^[a-z0-9][a-z0-9-]{2,39}$` und ist Mitglied von `design/penpot/views.json` (`ansichten[].schluessel`). Der Eintrag nennt die Breiten `mobile` und `desktop` und die Bausteine `button`, `alert`, `step-marker` und `progress`. Zustände: `ausschuss-nie-gelaufen`, `-laeuft`, `-fehlgeschlagen`, `-offen`, `-abgeschlossen`, `scan-erledigt`, `klassifizierung-erledigt`, `kuratierung`. Laut Lücke `vertretung` folgen Scan und Klassifizierung dem Ausschuss-Muster mit eigenen Beschriftungen.

### Aufbau der Schrittseite

Von oben nach unten:

1. **Schrittkopf:** `h2`, Erklärzeile und darunter `RerunBlock` (nur wenn `rerun` gesetzt ist).
2. **Inhalt:** Ergebnis, Bestätigungszeile, Raster, Bilanz.
3. **Fehlermeldung der Bestätigung**, falls vorhanden.
4. **`StepActionBar`** als letztes Element im Fluss.

Verhalten nach Breite:

- **Unter `sm`:** In der Leiste steht die Statuszeile über der Hauptaktion. Die Hauptaktion nimmt die volle Breite ein (`h-11`), und `gap-2` trennt beide.
- **Ab `sm`:** Die Statuszeile steht links, die Aktion rechts (`flex items-center justify-between gap-3`, Aktion `shrink-0`).

Die Leiste haftet unten (`sticky bottom-0 z-10 border-t border-separator bg-bg`, Innenabstand `py-3`, dazu `pb-[env(safe-area-inset-bottom)]`). Die Hauptaktion ist dadurch in jeder Scrolllage sichtbar (AK „ohne Scrollen“). Kein Element außer der Leiste haftet unten.

**Gestaltungsrang:**

- **Hauptaktion:** `Button` in `variant="default"`, Akzentfläche. Davon gibt es je Seite und Zustand genau eine.
- **„Erneut …“:** `Button variant="outline" size="sm"`, Umriss `--border-control`. Er steht im Kopf und damit räumlich getrennt von der Hauptaktion; Start und Abschluss sind so nie gleichrangig.
- **Erklärsatz:** steht als Fließtext daneben bzw. darunter (`text-sm text-text`, kein Tooltip, kein `<details>`), unter `sm` unter dem Knopf.

### Zustände je Hauptaktion (`StepAction`)

| `kind` | Leiste: Statuszeile | Leiste: Aktion |
|---|---|---|
| `start` | `StatusDot` + „Noch nicht …“ (wie heute) | Startknopf (default) |
| `running` | `StatusDot running` + Fortschrittstext („X von Y … verarbeitet“ bzw. „Dateien werden gezählt…“) + `Progress` (mit `value/max`, sobald der Nenner bekannt ist, sonst unbestimmt) | gesperrter Knopf in der Verlaufsform, `busy` (Spinner) |
| `retry` | `StatusDot failed` + „… fehlgeschlagen“, Fehlerdetail als `Alert` **ohne** `onRetry` im Inhalt | Startknopf mit derselben Beschriftung wie `start` (default), keine zweite Wiederholung |
| `confirm` | „N Vorschläge offen“ bzw. „Alle Vorschläge entschieden“ | Abschluss-Aktion (default), während der Anfrage `busy` |
| `next` | Ergebnis kurz („Erfolgreich“, „Ausschuss bestätigt“, Bilanz-Kurzform) | `Button asChild` + `Link`, default |
| `nextUnavailable` | neutraler Text, keine Aktion | – |
| `open` | – | `Link` „Album-Entwurf öffnen“ (default) |

Was nicht in die Leiste wandert, bleibt im Inhalt sichtbar:

- die Bestätigungszeile mit Zeitpunkt,
- `AUSSCHUSS_EMPTY_TEXT`,
- die Klassifizierungsbilanz.

Die **Kostenschätzung** (`ClassificationEstimate`) steht bei gewählter Cloud-Nutzung an beiden Auslösern:

- **beim Start:** als letztes Inhaltselement direkt über der Leiste. Die Klassifizierungsseite hat kein langes Raster, deshalb steht die Schätzung damit am Auslöser.
- **beim erneuten Auslösen:** im `RerunBlock`.

`isTriggerDisabled` sperrt alle drei Auslöser gleich.

### Beschriftungen (Vorschlag für `stepActionTexts.ts`)

Eine Story-Vorgabe wird bewusst abgewandelt: Die Tabelle nennt „Erneut scannen“. Das AK verlangt aber das gleiche Verb wie der Start, deshalb heißt der Knopf **„Erneut einlesen“**.

**Scan**

- **Start:** „Fotos einlesen“
- **Verlaufsform:** „Fotos werden eingelesen…“ (auch in der Statuszeile)
- **Erneut:** „Erneut einlesen“. Erklärsatz: „Erfasst neue, geänderte und entfernte Fotos im verknüpften Ordner. Ein bestätigter Ausschuss bleibt bestätigt; neu hinzugekommene Fotos prüft erst ‚Erneut erkennen‘.“ (Diese Aussage ist abgeleitet [INFERENCE] und noch zu prüfen, siehe offene Punkte.)
- **Weiter:** „Weiter zum Ausschuss“

**Ausschuss**

- **Start:** „Vorschläge erkennen“
- **Verlaufsform:** „Vorschläge werden erkannt…“
- **Erklärzeile im Kopf:** um „Es wird noch nichts aussortiert — du entscheidest danach.“ ergänzen
- **Abschluss mit Anzahl:** „{N} Vorschläge als Ausschuss übernehmen und abschließen“, bei N = 1 „1 Vorschlag …“
- **Abschluss ohne Anzahl:** „Ausschuss abschließen“. Gilt, wenn nichts mehr offen ist oder `openCount` noch `null` ist.
- **Erneut:** „Erneut erkennen“. Erklärsatz: „Bildet die Vorschläge neu. Ein bestehender Abschluss wird aufgehoben, die Klassifizierung ist bis zur erneuten Bestätigung gesperrt. Deine Einzelentscheidungen bleiben erhalten.“
- **Weiter:** „Weiter zur Klassifizierung“

**Klassifizierung**

- **Start:** „Klassifizierung starten“
- **Verlaufsform:** „Klassifizierung läuft…“. Heute steht dort „Wird klassifiziert…“; das widerspricht der Statuszeile und wird vereinheitlicht.
- **Erneut:** „Erneut klassifizieren“. Erklärsatz: „Berechnet Kategorien und Bewertungen aller Fotos neu“ + Satz zum Album-Vorschlag (Folge fachlich zu bestätigen)
- **Weiter:** „Weiter zur Kuratierung“

**Kuratierung:** „Album-Entwurf öffnen“

**Nächster Schritt nicht erreichbar:** „Der nächste Schritt ist in diesem Projekt ausgeschaltet.“ Bei Klassifizierung aus: „Die Klassifizierung ist in den Projekteinstellungen ausgeschaltet.“ Kein `Alert`, keine Fehlerfarbe.

**Weitere Textstellen**

- **Sperrgründe in der Schrittleiste:** z.B. „Schließe zuerst den Ausschuss ab (‚Ausschuss abschließen‘).“ Sie nennen nie „oben“ und verwenden dieselbe Konstante wie der Knopf. Die Anzahl entfällt dort.
- **Entfallende Fassungen:** „Ausschuss aussortieren“, „Wird aussortiert…“, „Aktualisieren“, „Ausschuss gesichtet, weiter“ und „Kriterien-Bewertung“ verschwinden aus allen sichtbaren Texten.

### Design-System (`specs/architecture/0004-design-system.md`)

**Wiederverwendet:**

- `Button` (`default`, `outline`, `busy`, `asChild`)
- `Alert`
- `Progress` (bestimmt/unbestimmt, Puls mit `motion-reduce`)
- `StatusDot`
- die Tokens `--bg`, `--separator`, `--accent`, `--border-control`, `--text`
- die Muster „Aktions-Button während laufender Anfrage“, „Determinierter Fortschritt“, „Dauerhaft sichtbare Kostenschätzung am Auslöser“ und „Bestätigung von Aktionen“ (kein Dialog vor einem erneuten Lauf)

**Ergänzung nötig:**

- **Neues Muster „Haftende Aktionsleiste am unteren Rand“** (Sticky im Fluss, kein `fixed`, deckend `bg-bg`, `border-separator`, safe-area, einzige untere Haftfläche, `z-10` wie die oberen Leisten). Das Muster „Mehrere gleichzeitig fixierte Bereiche“ bekommt den Hinweis, dass oben zwei Bereiche und unten einer haften.
- **Fortschreibung „Gateführter Sammel-Review“:** Die Abschluss-Aktion heißt nicht mehr „[Bereich] gesichtet, weiter“; nach erfolgreicher Bestätigung wechselt die Ansicht automatisch.
- **Neue Regel „Erneut-Auslöser“:** nachrangig (`outline sm`), im Kopf, mit dauerhaft sichtbarem Erklärsatz.
- Den Skill `design-system` im selben Schritt nachziehen.

### Barrierefreiheit

- **Live-Region:** Die Statuszeile der Leiste ist die einzige Live-Region des Laufstatus (`aria-live="polite"`). Die heutigen Live-Regionen im Kopf und im Fortschrittsblock entfallen bzw. wandern mit, damit nichts doppelt angesagt wird. Die Zehnerdrosselung (`…Decile`) bleibt. `Progress` ist dort `aria-hidden`, weil die Zahl als Text dasteht.
- **Landmarke:** Die Leiste ist eine `div`-Gruppe ohne eigene Landmarke (sie gehört zum `<main>`) und trägt `aria-label="Nächste Aktion"` als `role="group"`.
- **Link oder Button:** `next` und `open` sind Links (navigieren, starten nichts, Mittelklick/neuer Tab möglich). `start`, `retry`, `confirm` und Erneut sind `<button type="button">`. `running` ist ein `disabled` + `busy`-Button; Text und Breite bleiben stehen, die Seite springt nicht.
- **Fokus nach dem automatischen Wechsel** zur Klassifizierung: auf die Überschrift des Zielschritts (`h2` mit `tabIndex={-1}`, `ref.focus()` beim Eintritt nach diesem Wechsel). Vorbild ist `AlbumDraftPage`/`PersonsPage`. Ohne Fokussetzen bliebe der Fokus auf dem entfernten Abschluss-Knopf und fiele auf `body`. Der Fokus wird nicht bei jedem Seitenaufruf gesetzt, nur nach dem programmatischen Wechsel (z.B. über `navigate(…, { state: { focusHeading: true } })`).
- **Fokus nach einem erneuten Lauf:** Wird ein Knopf durch einen anderen ersetzt (z.B. Weiter → `running`), bleibt der Fokus in der Leiste. Die Aktion steht stabil an derselben Stelle.
- **Fehler:** Eine fehlgeschlagene Bestätigung ist ein `Alert` (`role="alert"`) direkt über der Leiste, der Fokus bleibt auf der Abschluss-Aktion.
- **Trefferfläche:** Leiste und Kopf halten 44px Trefferfläche ein, zwischen Bedienelementen ≥ 8px.

### Penpot-Lücken und was im Produkt gilt

- **`fortschrittsanteil`** (Spur ohne Füllstand): Das ist nur ein Darstellungsmangel des Entwurfs. Im Produkt zeigt `Progress` den Füllstand mit `value/max`, sobald der Nenner bekannt ist. Vorher ist der Balken unbestimmt (Puls), und der Text sagt „Dateien werden gezählt…“. Die Beschriftung des Bausteins wird nicht angezeigt.
- **`laufzustand`** (`busy` ohne Ladezeichen): gilt im Produkt nicht. Der `Button` mit `busy` zeigt den Spinner (`--accent`, `motion-reduce` beachtet) zusätzlich zur Verlaufsform und ist `disabled`.
- **`haftleiste`:** Der Abstand in Leistenhöhe, den der Entwurf fordert, entfällt. Weil die Leiste im Fluss haftet (`sticky`), behält sie ihren Platz und schiebt die letzte Rasterzeile und „Mehr laden“ beim Scrollen über sich. Das wird per E2E gemessen.
- **`vertretung`:** Scan und Klassifizierung übernehmen das Ausschuss-Muster mit den Beschriftungen oben.
- **`behaelter`, `pruefrahmen`, `kachelmasse`, `schrittzellen`, `seitengrund`:** reine Entwurfsartefakte ohne Folgen für das Produkt.

### Detailansicht `?photo` im Ausschuss

Die Architektur-Entscheidung, die Leiste auch dort zu zeigen, ist richtig und folgt aus dem AK „Abschluss-Aktion beim Aufruf der Seite erreichbar“. Die Detailansicht ist dieselbe Seite. Ohne Leiste hätte sie keine Hauptaktion, und man müsste erst schließen. Auflagen:

- Die Leiste darf die Entscheidungsknöpfe und „Schließen“ der Detailansicht nicht überdecken. Weil sie im Fluss liegt, ist das gegeben; das E2E-Maß schließt den Fall `?photo` bei 360px ein.
- `Esc` bleibt allein für das Schließen der Detailansicht zuständig; die Leiste hat keine Tastenkürzel.
- Der automatische Wechsel nach einer Bestätigung aus der Detailansicht pusht von der URL mit `?photo` aus. Browser-Zurück führt deshalb in die Detailansicht derselben Aufnahme. Das ist gewollt und erfüllt „zurück auf die Ausschussseite“.

## Security

**Ergebnis: nicht sicherheitsrelevant.** Die Story ändert nur das Frontend: Beschriftungen, die Gewichtung der Knöpfe, eine haftende Aktionsleiste und Weiter-Links. Sie fügt keinen Endpunkt hinzu, ändert weder Auth noch Berechtigungen, nimmt keine neue Eingabe von außen an und führt keine neue Schnittstelle nach außen ein. Ein Secret ist nicht beteiligt.

Abgleich mit `specs/architecture/0003-securitykonzept.md`. Die bestehenden Regeln gelten unverändert und schränken die Umsetzung ein:

- **Navigation und Weiter-Links:** Die Ziele werden als feste Pfade aus der numerischen Projekt-Id gebildet, zum Beispiel über `utils/projectRoutes.ts`. Ein Ziel kommt nie aus einem Query-Parameter, aus `document.referrer` oder aus `location.state`. Das ist die Regel aus Spec 0533, S11, und dem Frontend-Abschnitt zu Query-Parametern. Für den Wechsel nach der Ausschuss-Bestätigung gilt sie ebenso. Sonst entsteht eine offene Weiterleitung.
- **Texte:** Die Anzahlen in den Knöpfen, die Erklärsätze und der Sperrgrund erscheinen nur als React-Textknoten, ohne `dangerouslySetInnerHTML`.
- **Erneute Cloud-Klassifizierung ohne Bestätigungsdialog:** Das ist kein neuer Kostenpfad. Der Endpunkt, der Opt-in-Schalter für Cloud-Vision und das zusammengesetzte Skip-Kriterium bleiben unverändert. Das Skip-Kriterium verhindert, dass bereits bewertete Fotos noch einmal an den Anbieter gehen (siehe die zugehörige Zeile der Ankerliste). Die informierte Einwilligung bleibt erhalten, weil die Kostenschätzung laut Akzeptanzkriterium am erneuten Auslöser genauso steht wie beim ersten Lauf. Sie kommt weiter aus dem bestehenden `.../estimate`-Endpunkt und wird im Frontend nicht nachgerechnet. Das bekannte Restrisiko, dass ein gestohlenes JWT einen kostenpflichtigen Lauf auslösen kann, wächst nicht. Ein Dialog im Frontend hätte es ohnehin nicht begrenzt.

Das Sicherheitskonzept muss nicht ergänzt werden.

Die Grenze zur Produktentscheidung lag hier nicht knapp. Dass ein erneuter Lauf keinen Bestätigungsdialog bekommt, hat das Produkt bereits im Akzeptanzkriterium „Abgrenzung“ festgelegt. Sicherheitlich hängt daran nichts, weil die Kosten serverseitig über das Skip-Kriterium begrenzt sind.

## Teststrategie

**Unit (`stepActions.test.ts`, Muster wie `workflowOverviewStates.test.ts`).** Tabellentest über den vollständig aufgezählten Eingaberaum: Schritt × Laufstatus (keiner/läuft/fehlgeschlagen/erfolgreich) × `isTriggerPending` × für den Ausschuss `gate_confirmed_at` (leer/gesetzt) × `openCount` (`null`/0/1/n) × Erreichbarkeit des Folgeschritts.
- Invarianten über alle Fälle: genau eine Hauptaktion (`kind`). `rerun !== null` genau dann, wenn es einen erfolgreichen Lauf gab. Ein Fehlschlag ergibt genau `retry`. Ist der Folgeschritt nicht erreichbar, gibt es nie `next`. `next.to` ist der Pfad des nächsten Schritts aus `PIPELINE_STEPS`, nie fest kodiert.
- Die Erreichbarkeit kommt aus `computeStepStates` und wird nicht nachgebaut.
- Wortlaut gegen die Konstanten prüfen, nicht gegen Literale. Ausnahme ist ein kleiner Satz von Literal-Fällen für die Wortregeln (Verb gleich, Singular/Plural, keine verbotenen Wörter).
- `pipelineSteps.test.ts`: Der Sperrgrund enthält die Knopfkonstante und nicht „oben“.

**Komponente (vitest + Testing Library).**
- `StepActionBar`, je `kind`: Rolle (Link oder Button), `aria-disabled`/`busy` bei `running`, `role=group` mit Namen „Nächste Aktion“, genau eine `aria-live`-Region. Kein `role=alert` bei `nextUnavailable`.
- `RerunBlock`: Der Erklärsatz ist ohne Interaktion sichtbar. Kein `<details>`, kein `aria-expanded`, kein Dialog (Abwesenheit `within(block)`). `children` wird gerendert.
- Seiten-Integration (echter `QueryClientProvider` + `MemoryRouter`, `vi.mock` auf `api/*`, mit Standort-Sonde):
  - Ausschuss-Bestätigung erfolgreich: Refetch vor `navigate`. Prüfen über die Reihenfolge der Mock-Aufrufe und darüber, dass der Pfad der Sonde `/kriterien` ist und nicht zum Ausschuss zurückspringt. Dazu ein Push-Nachweis mit `MemoryRouter` + `navigate(-1)` → wieder `/ausschuss`. Fokus auf der `h2`.
  - Bestätigung fehlgeschlagen: Pfad unverändert, Alert vorhanden.
  - Klassifizierung abgeschaltet: kein Wechsel, neutraler Text.
  - Unmount vor `onSuccess`: Bestätigungsantwort über ein zurückgehaltenes Promise, vorher wegnavigieren, dann auflösen. Danach gibt es kein `navigate` zu `/kriterien`.
  - Hintergrundlauf endet erfolgreich (Projekt-Mock vom Status „läuft“ auf „erfolgreich“ umstellen): Pfad bleibt, Weiter-Link erscheint.
  - Fehlschlag: genau ein Wiederholungs-Button auf der Seite (Scan, Ausschuss, Klassifizierung). Ein Lade-Alert mit `onRetry` bleibt erlaubt.
  - `openCount` `null`: Abschluss ohne Anzahl. Nach dem Laden mit Anzahl.
  - `?photo`: Die Leiste ist gerendert.
  - Kuratierung: genau ein Link, keine Start-, Erneut- oder Abschluss-Buttons.
  - Kostenschätzung an beiden Auslösern. `isTriggerDisabled` sperrt Start, `retry` und Erneut.
- Umbenennung: Abwesenheit der Altfassungen über den bestehenden Wächter am Syntaxbaum (Muster aus #566, Testkonzept Punkt 6). Die neuen Altstrings werden dort ergänzt, mit Gegenprobe.

**E2E (Playwright).** Aufnahmekriterium erfüllt, weil sich Sticky und „ohne Scrollen“ nur mit echter Geometrie prüfen lassen. Neuer Layout-Spec `step-action-bar.spec.ts`, 360 px und Desktop, auf der Ausschussseite des Demoprojekts mit unbestätigtem Gate (Duplikat-Projekt, `gate_confirmed_at=None`) und, falls vorhanden, auf einer langen Ausschussliste („Große Sammlung“).
- Vorbedingungen gegen leeres Grün: Die Seite scrollt tatsächlich (`scrollHeight > clientHeight`). Die Abschluss-Aktion ist vorhanden. Für den Fall „Mehr laden“ ist der Knopf vorhanden und die Kachelzahl wächst. Gibt der Demo-Bestand keine zweite Seite her, muss der Seeder sie liefern (siehe Testkonzept).
- Zusicherungen:
  - Die Leiste liegt beim Aufruf, oben gescrollt und ganz unten gescrollt vollständig im Viewport. Die Hauptaktion ist an allen vier Ecken über `elementFromPoint` treffbar.
  - Am Seitenende liegt die Unterkante der letzten Kachel bzw. von „Mehr laden“ ≤ der Oberkante der Leiste, gemessen gegen die im selben Lauf gemessene Leistenbox.
  - `?photo` bei 360 px: Entscheidungsknöpfe und „Schließen“ sind treffbar.
- Rot-Nachweis im PR: `sticky` entfernen bzw. `fixed` setzen.
- **Kein E2E für die Navigation mit Browser-Zurück.** Sie ist in jsdom über `MemoryRouter` vollständig prüfbar (Aufnahmekriterium nicht erfüllt).
- **Ausnahme, falls gewünscht:** Ein einziger funktionaler Fall mit Bestätigung → `/kriterien` → `page.goBack()` → `/ausschuss` belegt das Zusammenspiel aus Refetch und Guard gegen den echten Server. Er verändert aber den Demo-Zustand und braucht Isolation, deshalb empfehle ich ihn nicht. Die Reihenfolge Refetch vor `navigate` ist im Komponententest belegt.

**Wichtigste Edge Cases:**
- `openCount` `null`, dann geladen
- 0 Vorschläge mit Auto-Abschluss, auch nach einem Neuladen
- `gate_confirmed_at` gesetzt, aber `openCount > 0`, also Vorschläge neu offen: weiter `confirm`
- Klassifizierung abgeschaltet: `nextUnavailable`, kein `navigate`
- Bestätigung fehlgeschlagen
- Erneute Bestätigung nach „Erneut erkennen“
- Unmount vor `onSuccess`
- Refetch liefert ein Projekt, in dem die Klassifizierung noch nicht erreichbar ist: kein Wechsel
- Fehlschlag beim Refetch: kein Wechsel, kein Absturz
- `?photo`: Browser-Zurück landet in der Detailansicht
- „Mehr laden“
- `isTriggerPending` vor der ersten Laufantwort
- Ein Lauf fehlgeschlagen nach einem früheren Erfolg: `retry` und `rerun` gleichzeitig? Die Tabelle sagt „eine Wiederholung“. Die Ableitung muss festlegen, dass `rerun` dann `null` ist, sonst gibt es zwei Wiederholungsknöpfe. **Bitte in der Spec klarstellen**, technisch ableitbar aus dem AK „genau eine Wiederholungsaktion“. Ich habe es so geschärft: beim Fehlschlag kein `rerun`.
- Fokus nach Weiter → `running` bleibt in der Leiste.

**Nicht automatisiert:** visueller Rang (Akzentfläche gegenüber outline) über die Klassen hinaus, das deckt der Design-Vertrag. Die fachliche Richtigkeit der Erklärsätze wird nur über Wortlaut-Konstanten geprüft.

## Testkonzept-Änderung: ja

1. **Tabelle des E2E-Satzes:** neue Zeile `step-action-bar`: haftende Fußleiste, Hauptaktion in drei Scrolllagen, keine verdeckte letzte Zeile/„Mehr laden“, `?photo` bei 360 px, Rot-Nachweis.
2. **Bestehender Spec `sticky-header` muss angepasst werden:** Er sichert auf Pipeline-Routen **genau zwei** sticky Elemente zu (`sticky-header.spec.ts:159`, `toBe(2)`). Mit der Leiste sind es drei, der Spec wird rot. Die Zusicherung wird auf „zwei oben haftende plus genau eine unten haftende (die Aktionsleiste)“ umgestellt. Die Kardinalität bleibt exakt, und der Zeilentext in der Tabelle wird fortgeschrieben. Gleiches gilt, falls `tap-targets` oder `no-horizontal-scroll` Pipeline-Routen messen: die Leiste dort aufnehmen bzw. nicht als Verdeckung werten.
3. **Neues Frontend-Muster (kurz):** Eine Navigation in `onSuccess` pro Aufruf einer Mutation wird mit drei Tests belegt: (a) Reihenfolge Refetch vor `navigate` über die Mock-Aufrufe, (b) Push-Nachweis mit `navigate(-1)` in `MemoryRouter`, (c) Unmount vor dem Auflösen eines zurückgehaltenen Promise → keine Navigation. Gilt projektweit für automatische Wechsel nach Mutationen.
4. **Demo-Seeder (nur falls nötig):** Hat kein Demo-Projekt eine unbestätigte Ausschussliste über mehr als eine Seite, braucht `demo_state.py` diesen Zustand. Kardinalitätszusicherung in `test_demo_state.py` gegen die Seitengröße, sonst bliebe der Fall „Mehr laden“ leer grün. Nicht im Repo geprüft, ob „Große Sammlung“ das schon erfüllt [INFERENCE: offen].

## Entscheidungen

- Kein ADR: keine neue Technologie, keine Abhängigkeit, keine Datenmodelländerung; die haftende Leiste nutzt das bestehende CSS-Sticky-Muster am unteren Rand.
- Leiste haftet im Fluss (`sticky`), nicht `fixed`; damit entfällt der Ausgleichsabstand aus der Penpot-Lücke `haftleiste`.
- Texte in eigenem Blattmodul `stepActionTexts.ts`, um einen Importzyklus mit `pipelineSteps.ts` zu vermeiden.
- Automatischer Wechsel erst nach `await refetchProject()`, als Push, über `onSuccess` je Aufruf.
- Die Fußleiste steht auch in der Ausschuss-Detailansicht `?photo`.
- Scan-Knopf heißt „Erneut einlesen“ statt „Erneut scannen“, weil das AK dasselbe Verb wie der Startknopf verlangt.
- Bei Fehlschlag kein `rerun`, abgeleitet aus dem AK „genau eine Wiederholung“.
- Kein E2E für Browser-Zurück; jsdom mit `MemoryRouter` prüft das vollständig.
- `security-engineer` konsultiert: nicht sicherheitsrelevant, Sicherheitskonzept bleibt unverändert.

## Offene Fragen

Keine an den Stakeholder. Bei der Umsetzung am Code zu belegen, bevor ein Test den Wortlaut festschreibt:

- **Erklärsatz zu „Erneut einlesen“:** Belegt ist, dass `gate_confirmed_at` am `ScoringRun` hängt und ein Scan es nicht setzt (`worker.py`); ob ein Rescan einen bestätigten Ausschuss aufhebt oder neue Fotos ungeprüft durchlässt, ist nicht belegt. Der Satz beschreibt das tatsächliche Verhalten.
- **Erklärsatz zu „Erneut klassifizieren“:** Was mit einem bestehenden Album-Vorschlag geschieht (Album-Entwurf liest den letzten erfolgreichen Lauf, `FinalSelectionDecision` ist laufunabhängig) wird am Code abgelesen und so beschrieben.
- Ob der Demo-Bestand eine unbestätigte Ausschussliste über mehr als eine Seite hat; sonst ergänzt `demo_state.py` den Zustand für den E2E-Fall „Mehr laden“.

## Out of Scope

- Fachliches Verhalten der Läufe, Erreichbarkeit/Sperre der Schritte, Inhalt der Ausschuss-Bestätigung.
- Bestätigungsdialog vor erneuten Läufen.
- Darstellung der Schrittleiste.
