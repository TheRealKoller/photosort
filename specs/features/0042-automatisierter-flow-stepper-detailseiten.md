# 0042 - Automatisierter Flow als Stepper-Übersicht mit Detailseiten je Schritt

**Status:** Accepted
**Erstellt:** 2026-08-15
**Bezug:** Inbox-Eintrag [`specs/inbox/0021-visualisierung-automatisierter-flow.md`](../inbox/0021-visualisierung-automatisierter-flow.md), idea-sharpener-Gespräch mit Daniel. Löst die in Spec [0037](./0037-gateführte-bewertungs-pipeline-mit-backfill.md) (Implemented) getroffene UI/UX-Entscheidung "kein neuer Wizard/Stepper" bewusst ab — siehe Entscheidungen.

## Ziel

Spec 0037 hat die bisherige Zwei-Sections-Struktur auf `ProjectDetailPage` zu fünf dauerhaft sichtbaren, nacheinander angeordneten Sections erweitert (Scan, Ausschuss-Erkennung, Ausschuss-Gate, Kriterien-Bewertung, Kategorie-Kuratierung), jede bei fehlender Vorbedingung `disabled` mit Erklärtext statt zu verschwinden. Mit fünf Schritten wird diese Einzelseiten-Darstellung unübersichtlich: es ist nicht auf einen Blick erkennbar, wie weit der Nutzer im Gesamtprozess ist, welcher Schritt gerade aktiv ist, und welche noch offen sind — alles konkurriert um Platz auf einer langen Seite.

Diese Spec ersetzt die fünf Inline-Sections durch eine kompakte Stepper-Fortschrittsübersicht am oberen Rand (erledigt/aktuell/ausstehend/blockiert je Schritt) und eine eigene Detailseite pro Schritt, auf der der Nutzer entweder die Aktion des Schritts durchführt/anstößt (z.B. Ausschuss-Gate bestätigen) oder — bei automatisch laufenden Hintergrund-Jobs — das Ergebnis (Statistiken) bzw. eine Live-Fortschrittsanzeige sieht. Reine Navigations-/Präsentationsschicht-Änderung: die fachliche Pipeline-Logik aus Spec 0037 (Endpunkte, Gate-Semantik, Backfill) bleibt vollständig unverändert.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich den automatisierten Bewertungs-Workflow als eine klare, schrittweise Fortschritts-Übersicht mit dedizierter Detailseite pro Schritt sehen, damit ich auf einen Blick erkenne, welche Schritte erledigt, welcher aktuell aktiv und welche noch blockiert sind — statt mit fünf teils deaktivierten Sections auf einer überlangen Seite umgehen zu müssen.

## Akzeptanzkriterien

**Route + Stepper-Leiste**

1. Neue verschachtelte Route `/projects/:projectId/pipeline` (Layout) mit Kind-Route `/projects/:projectId/pipeline/:step` (`:step ∈ {scan, ausschuss, gate, kriterien, kuratierung}`) rendert für jeden gültigen `:step`-Wert eine sticky `<nav aria-label="Fortschritt der Pipeline"><ol>`-Stepper-Leiste oberhalb der jeweiligen Detailseite. Die bisherige Route `/projects/:projectId` bleibt als reiner Redirect (`Navigate replace` auf `/projects/:projectId/pipeline`) erhalten — Bestandsschutz für bestehende Links/Bookmarks.
2. Der Stepper zeigt alle 5 Schritte in fester Reihenfolge (Scan, Ausschuss-Erkennung, Ausschuss-Gate, Kriterien-Bewertung, Kategorie-Kuratierung).

**Zustandsherleitung (`computeStepStates`, pure Funktion, kein neues Backend-Feld)**

3. `computeStepStates(project: ProjectOut): PipelineStepState[]` liefert je Schritt `{id, isDone, isReachable}`, exakt nach folgender Tabelle (1:1 aus dem bestehenden, bereits produktiven Gating-Verhalten von `ProjectDetailPage.tsx` übernommen, keine neue/strengere Logik):

   | Schritt | `isDone` | `isReachable` |
   |---|---|---|
   | `scan` | `last_scan?.status === 'success'` | `true` |
   | `ausschuss` | `last_scoring_run?.status === 'success'` | `true` (bewusst ungegatet, wie bisher — kein neues Gate auf `last_scan.status`) |
   | `gate` | `gate_confirmed_at !== null` (deckt Auto- und manuelle Bestätigung gleichermaßen ab) | `last_scoring_run?.status === 'success'` |
   | `kriterien` | `last_criterion_scoring_run?.status === 'success'` | `category_selection_enabled === true && gate_confirmed_at !== null` |
   | `kuratierung` | immer `false` (offener Review-Prozess ohne Abschlusssignal im Datenmodell) | `last_criterion_scoring_run?.status === 'success'` |

4. `getDefaultStepId(states)` (erster erreichbarer, noch nicht erledigter Schritt, Fallback `kuratierung`) und `getHighestReachableStepId(states)` (letzter erreichbarer Schritt in Reihenfolge) liefern für dieselbe Zustandskombination dasselbe Ziel — Basis-Route ohne `:step` und ein unerreichbarer Deep-Link landen konsistent am selben Ort.

**Klickbarkeit im Stepper**

5. Ein Schritt ist im Stepper genau dann ein klickbarer Link, wenn `isReachable === true` (ergibt automatisch: bereits erledigte Schritte sind immer klickbar — "rückwärts immer möglich" ohne separate Fallunterscheidung). Blockierte Schritte (`!isReachable`) bleiben in der Leiste sichtbar (nie ausgeblendet), sind nicht klickbar (`aria-disabled="true"`, `tabIndex={-1}`), zeigen den Grund über einen Popover-Trigger (Wiederverwendung des bestehenden Info-Popover-Musters aus Spec 0040).
6. Visueller Status je Schritt (Farbe nie alleiniges Signal, zusätzlich Icon/Form/Text): **erledigt** (gefüllter Kreis + Häkchen), **aktuell** (zusätzlicher Akzent-Ring + `aria-current="step"`, unabhängig davon ob der Schritt auch `isDone` ist), **ausstehend** (erreichbar, nicht erledigt, nicht aktuell), **blockiert** (gedämpft + Schloss-Icon + Popover-Grund).

**Detailseiten**

7. Fünf Detailseiten (`ScanStepPage`, `AusschussStepPage`, `GateStepPage`, `KriterienStepPage`, `KuratierungStepPage`) sind inhaltliche 1:1-Migrationen der bisherigen `ProjectDetailPage`-Sections (Trigger-Button inkl. Busy-Zustand, Statuszeile mit `aria-live`, Live-Fortschrittsanzeige, Ergebnis-Statistiken, Fehleranzeige mit Retry) — fachliche Logik, Zustände und Texte unverändert. Jede Seite bezieht `project`/`refetchProject` über `useOutletContext` vom Layout, kein eigener `useProjectQuery`-Aufruf je Detailseite.
8. `GateStepPage` erhält zusätzlich eine kurze, einzeilige Erklärung (Konsistenz mit den bereits beschrifteten Schritten Kriterien-Bewertung/Kuratierung) und behält das bestehende Muster "Automatisch übersprungener Schritt bleibt sichtbar nachvollziehbar": dauerhafter Text "Kein Ausschuss gefunden — automatisch bestätigt" bzw. "Ausschuss gesichtet am [Datum]", unabhängig davon zeigt der Stepper diesen Schritt als "erledigt".
9. Der bestehende Gate-Query-Param-Mechanismus (`?filter=suggested&gate=1` auf `PhotoGridPage.tsx`) bleibt inhaltlich unverändert bestehen. Einzige Änderung: das Redirect-Ziel nach erfolgreicher Gate-Bestätigung wechselt von `/projects/:id` auf `/projects/:id/pipeline` (ohne festen `:step`) — landet über `getDefaultStepId` automatisch beim nächsten sinnvollen Schritt.

**Redirect-Guard bei nicht erreichbarem/unbekanntem Schritt**

10. Direkter URL-Aufruf eines Schritts, der aktuell nicht erreichbar ist (`!isReachable`), eines unbekannten `:step`-Werts, oder der Basis-Route ohne `:step`: `Navigate replace` zum passenden Ziel (`getHighestReachableStepId` bzw. `getDefaultStepId`) — kein neuer History-Eintrag, kein Zurück-Button-Loop.
11. Der Redirect-Guard wird bei jedem Render neu aus den aktuellen (gepollten) Projektdaten abgeleitet, nicht nur beim ersten Mount der Route: wird ein Schritt während des Betrachtens durch einen Re-Scan/Re-Scoring-Vorgang nicht mehr erreichbar, erfolgt der Redirect automatisch beim nächsten Poll-Tick, ohne Nutzerinteraktion.

**Bestandsschutz**

12. Alle bestehenden Endpunkte/Mutationen (`POST /projects/{id}/score`, `POST /projects/{id}/confirm-ausschuss-gate`, `POST /projects/{id}/score-criteria`, `GET /projects/{id}/photos?top_n_per_category`) bleiben unverändert erreichbar und unverändert in ihrer Guard-Logik (401/403/409-Verhalten) — kein Backend-Eingriff, keine neue Migration.
13. Live-Polling (`useProjectQuery`, 2s-Intervall bei laufendem Job) bleibt zentral im Layout, unverändert in Intervall und Watchdog-Anbindung (ADR 0019).
14. Bekannte, unverändert übernommene Grenze aus Spec 0037: `CriterionScoringRunSummary` referenziert nicht die zugehörige `scoring_run_id` — nach einem Re-Scan/Re-Scoring kann die Stepper-Anzeige clientseitig kurzzeitig veraltet wirken, bis zum nächsten Trigger-Versuch (dort greift der bestehende 409-Staleness-Guard unverändert). Diese Spec behebt diese Grenze nicht, übernimmt sie unverändert.

**Barrierefreiheit**

15. `aria-current="step"` auf dem aktuellen Schritt, `aria-disabled="true"` + Popover-Grund auf blockierten Schritten, volles `aria-label` je Schritt-Element ("Schritt N von 5: [Label], [Status]"). Skip-Link vor der Stepper-Leiste zum Seiteninhalt. Alle interaktiven Kreise/Trigger erfüllen das bestehende 44×44px-Touch-Ziel.

## Datenmodell-Bezug

Keine Änderung. Reine Frontend-Restrukturierung — `computeStepStates` leitet den vollständigen Pipeline-Status ausschließlich aus bereits vorhandenen `ProjectOut`-Feldern ab (`last_scan`, `last_scoring_run` inkl. `gate_confirmed_at`, `last_criterion_scoring_run`, `category_selection_enabled`), siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Bezug:** Kein neues ADR nötig — keine neue Technologie, keine Datenmodell-Grundstruktur-Änderung, keine externe Abhängigkeit. Baut auf ADR [`decisions/0004-frontend-app-shell.md`](../decisions/0004-frontend-app-shell.md) (react-router, TanStack Query) auf und nutzt dort erstmals verschachtelte Routen + `Outlet`-Context — reine Anwendung der bereits gewählten Bibliothek, kein neuer Architektur-Baustein. Wird bei Umsetzung als neuer Eintrag in `docs/architecture.md` nachgetragen (Aufgabe des `architect`-Agenten im Umsetzungs-PR).

Reine Frontend-Restrukturierung: kein Backend-Eingriff, kein neues Datenmodell, keine neue Migration. Alle bestehenden Endpunkte/Mutationen bleiben unverändert (AK12).

### Routing

- Bestehende Route `/projects/:projectId` bleibt als reiner Redirect erhalten (Bestandsschutz für Bookmarks/Links von `ProjectListPage`), navigiert per `<Navigate to={\`/projects/${projectId}/pipeline\`} replace />` weiter — bewusst absoluter Template-String statt relativem `to="pipeline"`, konsistent mit dem im Projekt durchgehend etablierten Muster expliziter absoluter Pfade.
- Neu, verschachtelt (erste Verwendung von React-Router-Nested-Routes im Projekt, `App.tsx`):
  ```
  <Route path="/projects/:projectId/pipeline" element={<ProjectPipelineLayout />}>
    <Route path=":step" element={<PipelineStepView />} />
  </Route>
  ```
- **`ProjectPipelineLayout.tsx`** (neu, `frontend/src/pages/pipeline/`) übernimmt die bisherige Verantwortung von `ProjectDetailPage.tsx`: `useProjectQuery(id)`, Lade-/404-/Fehlerzustand (1:1 übernommen), Projekt-Header, Sekundärnavigation ("Fotos ansehen", "Bewertungen vergleichen", "Zurück zur Projektliste" — wandert vom Seitenende ins Layout, da sie zu keinem einzelnen Schritt gehört), Stepper-Leiste, Redirect-Guards. Rendert die Kind-Route über `<Outlet context={{ project, refetchProject: query.refetch }} />`.
- **`PipelineStepView.tsx`** (neu, dünn): liest `:step`, bildet ihn über eine feste `Record<StepId, ComponentType>`-Zuordnung (`utils/pipelineSteps.ts`) auf die jeweilige Detailseiten-Komponente ab.
- Fünf neue Detailseiten (`frontend/src/pages/pipeline/`): `ScanStepPage.tsx`, `AusschussStepPage.tsx`, `GateStepPage.tsx`, `KriterienStepPage.tsx`, `KuratierungStepPage.tsx`.
- Zentraler Guard im Layout statt je Detailseite: eine einzige Stelle für "Projekt nicht geladen" und "Schritt nicht erreichbar" statt fünffacher Duplikation.

### Zustandsherleitung

Neu, pur (`frontend/src/utils/pipelineSteps.ts`, kein Seiteneffekt, kein Fetch — analog `utils/timeOfDay.ts`/`utils/qualityLevel.ts`): `StepId`-Union, `PIPELINE_STEPS`-Liste (einzige Quelle der Wahrheit für Anzeigereihenfolge und Routing-Zuordnung), `computeStepStates`, `getDefaultStepId`, `getHighestReachableStepId` — siehe Akzeptanzkriterien 3-4 für die genauen Formeln.

### Stepper-Komponente

`frontend/src/components/Stepper.tsx` (presentational). Status-Ableitung fürs Rendering: `aktuell` = `step.id === aktuellesStepParam` (aus der URL, nicht algorithmisch hergeleitet); `erledigt` = `isDone`; `blockiert` = `!isReachable`; `ausstehend` = `isReachable && !isDone && !aktuell`. Klickbarkeit: einzige Regel `isReachable` (siehe AK5).

### Redirect-/Guard-Logik

Ausschließlich im `ProjectPipelineLayout`, zwei Fälle: `:step` fehlt → `Navigate` zu `getDefaultStepId`; `:step` unbekannt oder `!isReachable` → `Navigate` zu `getHighestReachableStepId`. Beide als `replace` (kein History-Eintrag). Kein neuer State — reine Ableitung aus bereits geladenem `project` bei jedem Render (erfüllt AK11 automatisch, kein zwischengespeicherter Navigationszustand).

### Gate-Mechanismus

Bleibt unverändert bestehen — `GateStepPage.tsx` ist ein reiner Statusanzeige-Wrapper mit Link zu `PhotoGridPage?filter=suggested&gate=1`. Einzige Änderung: `PhotoGridPage.tsx`, Gate-Bestätigungs-`onSuccess`-Navigationsziel wechselt von `/projects/${id}` auf `/projects/${id}/pipeline`.

### Polling

Bleibt zentral, unverändert in `hooks/useProjects.ts` — nur der Aufrufer wandert von `ProjectDetailPage` zu `ProjectPipelineLayout`. Die fünf Detailseiten lesen `project` ausschließlich über `useOutletContext`.

### Geteilter Hilfs-Hook `useTriggerConfirmation`

Bisher dateilokal in `ProjectDetailPage.tsx` ("nachweislich nur zweimal gebraucht, keine Auslagerung ohne dritten Konsumenten"). Mit dieser Spec entstehen mehrere getrennte Konsumenten-Dateien — die Bedingung für "dateilokal" entfällt. Wird nach `frontend/src/hooks/useTriggerConfirmation.ts` verschoben, Logik unverändert.

### Reihenfolge für den TDD-Einstieg

1. `utils/pipelineSteps.ts` (pure Funktionen, isoliert unit-testbar).
2. `hooks/useTriggerConfirmation.ts` (Verschieben, unveränderte Logik, Tests wandern mit).
3. `components/Stepper.tsx` (presentational, gegen `computeStepStates`-Testfixtures).
4. `pages/pipeline/ProjectPipelineLayout.tsx` (Daten-/Guard-/Redirect-Logik zuerst, dann Stepper-Einbindung).
5. Fünf Detailseiten, je 1:1-Migration des bestehenden Section-Inhalts samt bestehender Tests.
6. `App.tsx`-Routing-Umbau (Redirect-Route, verschachtelte Pipeline-Routen) + `PhotoGridPage.tsx`-Navigationsziel-Anpassung.
7. `ProjectDetailPage.tsx` + zugehöriger Test entfernen, sobald alle Inhalte migriert sind.

### Randfälle (Pflicht, ergänzt AK10/AK11)

- Unbekannter `:step`-Wert (Tippfehler in Bookmark/URL) → wie "nicht erreichbar" behandelt, Redirect zum höchsten erreichbaren Schritt.
- Re-Scan/Re-Scoring während der Nutzer auf einer späteren Detailseite ist: bestehende 409-Guards greifen unverändert beim nächsten Trigger-Versuch; die Stepper-Anzeige folgt automatisch dem neuen `ProjectOut`-Stand beim nächsten Poll.
- Alle fünf Schritte bereits `isDone`/erreicht → `getDefaultStepId` landet auf `kuratierung`, Stepper zeigt vier Haken + aktiven letzten Schritt.

## UI/UX

**Sichtbare Oberfläche:** Ja — ersetzt die bestehende Fünf-Sections-Seite durch eine Stepper-Fortschrittsleiste + fünf eigenständige Detailseiten. Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md), dort ergänzt um drei Muster: *Sticky Stepper-Fortschrittsnavigation*, *Redirect statt disabled Deep-Link*, sowie rückwirkend nachgetragen *Info-Popover für situative Kurzerklärungen* (bereits mit Spec 0040 implementiert, bisher nicht dokumentiert).

**Keine neue UI-Bibliothek nötig.** Vorhandene Bausteine reichen (`Button`, `Card`, `Badge`, `Progress`, `Alert`, `Skeleton`, `Popover`). Der Stepper selbst ist natives `<nav><ol>` + Tailwind, keine neue Radix-Primitive.

**Stepper-Leiste:** horizontal, `sticky top-0 z-10` mit `bg-bg/95 backdrop-blur-sm border-b border-border`. Kreise durchgängig 44×44px (auch nicht-klickbare, Touch-Ziel-Konsistenz vor Platzersparnis). Vier Zustände wie in Akzeptanzkriterium 6 beschrieben, Farbe nie alleiniges Signal. Responsiv: bleibt auf allen Breakpoints horizontal, Labels ab `sm:` sichtbar; darunter ersetzt eine einzeilige Orientierungszeile ("Schritt 3 von 5: Ausschuss-Gate") die Labels, verhindert Umbruch/Horizontal-Scroll (5×44px + Verbindungslinien passen ohne Labels in ca. 300px). Erster Skip-Link im Produkt ("Zum Seiteninhalt springen") vor der Leiste.

**Detailseiten:** 1:1-Migration der bisherigen Section-Inhalte, jede mit eigener `<h1>` (Projektname/-pfad wandert in den `ProjectPipelineLayout`-Header). Da nicht mehr fünf Sections um Platz konkurrieren, bekommen die drei bisher unkommentierten Schritte (Scan, Ausschuss-Erkennung, Ausschuss-Gate) dieselbe kurze Erklärzeile wie die beiden bereits beschrifteten Schritte. Fortschrittsbalken/Statistik-Layout behalten ihre bestehende Breite — mehr verfügbarer Platz wird nicht automatisch ausgenutzt. `GateStepPage` behält das Auto-Skip-Muster unverändert (siehe AK8).

**Musterbruch — Redirect statt disabled Deep-Link:** das bisherige Muster "Nicht verfügbare Aktion" (disabled + Erklärtext an fester Stelle, nie verschwindend/umleitend, aus Spec 0024/0037) galt für eine Einzelseiten-Struktur. Bei eigenen Routen pro Schritt ist ein Deep-Link auf einen nicht erreichbaren Schritt ein neuer Fall — eine disabled-Ansicht dort zu rendern wäre nicht sinnvoll (die Seite hat inhaltlich nichts zu zeigen, ihr Inhalt setzt Vorgänger-Daten voraus). Stattdessen: deterministischer Redirect zum höchsten erreichbaren Schritt (kein Toast). Das ist eine kontrollierte Weiterentwicklung, kein stiller Widerspruch — die Kernzusage bleibt erhalten, da der angeforderte Schritt weiterhin sichtbar als "blockiert" im Stepper markiert ist, mit Grund per Popover abrufbar. Im Design-System-Dokument als solche festgehalten.

**Barrierefreiheit:** siehe Akzeptanzkriterium 15.

## Security

**Nicht relevant.** Reine Frontend-Navigations-/Präsentationsschicht-Änderung ohne neue Endpunkte, ohne neue Eingaben von außen, ohne Änderung an Auth/Autorisierung (alle Routen hängen unverändert am bestehenden Router-Torwächter) und ohne Änderung der Datensichtbarkeit zwischen den beiden Nutzern. Die Redirect-/Guard-Logik liest ausschließlich bereits über die bestehende, autorisierte `GET /projects/{id}`-Route sichtbare Daten — kein neues IDOR-/Datenleck-Risiko.

## Teststrategie

`specs/architecture/0002-testkonzept.md` ist bereits ergänzt (neue Sektion "Mehrschritt-Routing mit rein abgeleitetem Redirect-Guard") — zwei neue Muster: (1) Redirect-Guard aus rein abgeleitetem, live nachpollendem State statt zwischengespeichertem Navigationszustand, (2) Migration einer Section-basierten Einzelseiten-Testsuite auf Multi-Page-Routing-Tests inkl. `createMemoryRouter`-Technik für History-Stack-Assertions.

**Testebenen:**
- **Unit** (`frontend/src/utils/pipelineSteps.test.ts`): Fixture-Tabelle über alle Zustandskombinationen aus Akzeptanzkriterium 3 (leer/teilweise/vollständig erledigt, Feature-Flag aus, Gate auto- vs. manuell bestätigt). Reine Funktion, kein Router/Query nötig.
- **Integration:** `ProjectPipelineLayout.test.tsx` (`MemoryRouter`+`QueryClientProvider`) — Redirect-Fälle (fehlend/unbekannt/unreachable → highest reachable), Reaktivität bei Poll-Änderung (AK11), History-Verhalten via `createMemoryRouter` (AK10 "kein Eintrag"), plus die aus `ProjectDetailPage.test.tsx` wandernden Tests (404, Lade-Zustand, Sekundärnavigation, Unmount-Polling-Cleanup). Fünf `*StepPage.test.tsx`: 1:1-Migration der bestehenden Section-`describe`-Blöcke, gerendert über `useOutletContext`-Mock. `hooks/useTriggerConfirmation.test.tsx` (neu, `renderHook`): volle Timing-Matrix einmal statt bisher dreifach dupliziert. `Stepper.test.tsx`: presentational mit minimalem `MemoryRouter`-Wrapper.
- **Bewusst nicht getestet:** visuelles Erscheinungsbild/Pixel-genaues Layout (Design-System-Konformität ist Review-Aufgabe, kein automatisierter Test).

**Edge Cases (Pflicht):**
- Alle Schritte erledigt; kein Schritt erledigt.
- `:step`-Tippfehler in der URL; direkter Aufruf von `/pipeline` ohne `:step`.
- Browser-Zurück-Button-Verhalten nach Redirect mit `replace` (kein zusätzlicher History-Eintrag).
- Rennen zwischen Redirect und laufendem 2s-Poll (Schritt wird während Betrachtung nicht mehr erreichbar).
- Gate automatisch bestätigt vs. manuell bestätigt — beide als "erledigt" im Stepper.
- `category_selection_enabled=false` blockiert `kriterien` trotz erfüllter Gate-Vorbedingung.
- `ausschuss` bleibt bewusst ungegatet (Regressionsschutz gegen ein künftiges, ungewolltes neues Gate).

## Entscheidungen (2026-08-15, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Bewusste Umkehrung von Spec 0037:** Spec 0037 hatte sich im UI/UX-Abschnitt explizit gegen einen Stepper/Wizard entschieden ("kein neuer Wizard/Stepper", alle 5 Sections dauerhaft auf einer Seite sichtbar). Per Rückfrage mit Daniel abgeglichen, inkl. einer expliziten leichteren Alternative (nur eine sticky Fortschrittsleiste ohne separate Detailseiten, bestehende Sections bleiben inline) — Daniel hat sich bewusst für die volle Version entschieden (Stepper + separate Detailseiten pro Schritt), nicht die leichtere Variante.
- **Umfang: genau die 5 Schritte aus Spec 0037**, nicht zusätzlich Export (Spec 0004, weiterhin `Proposed`, separate Spec).
- **Kein neues Backend-Feld:** der gesamte Stepper-Status wird client-seitig aus bereits vorhandenen `ProjectOut`-Feldern abgeleitet (`architect`-Konsultation).
- **`ausschuss`-Schritt bleibt bewusst ungegatet:** die bestehende Implementierung koppelt den "Ausschuss aussortieren"-Button nie an `last_scan.status` — dieses Verhalten wird unverändert übernommen, kein neues, strengeres Gate eingeführt (`test-engineer`-Konsultation, Regressionsschutz-Test).
- **Redirect statt disabled Deep-Link:** bewusste, dokumentierte Weiterentwicklung des bestehenden "Nicht verfügbare Aktion"-Musters für den neuen Mehrseiten-Kontext, nicht als stiller Widerspruch, sondern im Design-System-Dokument festgehalten (`ux-ui-designer`-Konsultation).
- **`architect` konsultiert (Schritt 6):** Routing-/Zustandsherleitungs-Architektur, siehe Architektur-Abschnitt. Keine neue ADR nötig (Begründung siehe dort).
- **`ux-ui-designer` konsultiert (Schritt 7):** sichtbare Oberfläche betroffen (Ablösung der Fünf-Sections-Seite), siehe UI/UX-Abschnitt. Design-System-Dokument bereits aktualisiert.
- **`test-engineer` konsultiert (Schritt 8):** testbares Verhalten (neue Routing-/Zustandsableitungslogik), siehe Teststrategie-Abschnitt. Testkonzept bereits aktualisiert.
- **`security-engineer` nicht konsultiert (Schritt 8):** reine Frontend-Navigations-/Präsentationsschicht-Änderung ohne neue Endpunkte, ohne neue Eingaben von außen, ohne Änderung an Auth/Autorisierung oder an der Datensichtbarkeit zwischen den beiden Nutzern — kein plausibles Gegenbeispiel für Sicherheitsrelevanz gefunden.
- **Roadmap-Priorität: Hoch** (`requirements-engineer`-Konsultation, 2026-08-15, nach Recherche/Devil's-Advocate bestätigt): strukturelle Navigations-Verbesserung der bereits produktiven, täglich genutzten 0037-Pipeline — vergleichbar mit früheren hochpriorisierten Verbesserungen an bereits ausgeliefertem Kernverhalten (0027/0030/0034). Kein Konflikt mit bereits Geplantem: Spec 0039 (Implemented, PR #91) betrifft ausschließlich den Inhalt der Kuratierungs-Detailseite, nicht die Navigationsebene darum; Spec 0041 (Accepted, Niedrig) ist orthogonal (Bewertungsdetails-Komfort).

## Offene Fragen

Keine — alle im Gespräch bzw. in den Fachkonsultationen aufgekommenen Punkte wurden geklärt.

## Out of Scope

- **Export (Spec 0004)** — bleibt eigenständige, separate, weiterhin `Proposed` Spec.
- **Änderung der fachlichen Pipeline-Logik selbst** (Endpunkte, Gate-Semantik, Backfill-Mechanik, 409-Staleness-Guards) — ausschließlich Navigations-/Präsentationsschicht betroffen.
- **Behebung der bekannten Grenze** "fehlende `scoring_run_id`-Referenz auf `CriterionScoringRunSummary`" (siehe Akzeptanzkriterium 14) — unverändert aus Spec 0037 übernommen, nicht Teil dieser Spec.
- **Mobile-optimierte Vertikal-Variante des Steppers** — bleibt horizontal auf allen Breakpoints, siehe UI/UX-Abschnitt.
