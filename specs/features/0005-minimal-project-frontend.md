# 0005 - Minimales Projekt-Frontend

**Status:** Implemented ([PR #2](https://github.com/TheRealKoller/photosort/pull/2), 2026-07-22)
**Erstellt:** 2026-07-20
**Akzeptiert:** 2026-07-20
**Bezug:** Als fehlendes Prerequisite beim Schärfen von Spec 0002 (Manuelle Kategorisierung) entdeckt, siehe `specs/features/0002-manual-categorization.md` Abschnitt "Architektur / Umsetzung"; jetzt im idea-sharpener-Gespräch vom 2026-07-20 selbst geschärft.

## Ziel

Nutzer benötigen eine minimale Web-Oberfläche, um OpenCloud-Projekte selbst anzulegen, zu übersehen und zu aktualisieren, statt dies über direkte API-Aufrufe tun zu müssen. Diese Spec liefert das Frontend-Grundgerüst (Routing, API-Client) sowie die drei Kernseiten für Projektverwaltung, die Spec 0001 (Backend) bereits ermöglicht, aber noch nicht sichtbar macht. Sie ist gleichzeitig die Basis (Routing-Konvention, API-Client-Muster, Navigation), auf der Spec 0002 (Manuelle Kategorisierung) ihre eigenen Ansichten aufbaut — und ist damit die erste sichtbare Oberfläche von PhotoSort überhaupt.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich Projekte über eine Weboberfläche anlegen, in einer Liste übersehen und pro Projekt einen Foto-Scan anstoßen können, damit ich OpenCloud-Ordner ohne direkte API-Interaktion in PhotoSort nutzbar mache.

## Akzeptanzkriterien

**Projektliste (`/`)**

- [ ] `/` lädt via `GET /projects`; jede Karte zeigt Name, `opencloud_path` und Scan-Kurzstatus. Vier sichtbar unterscheidbare Zustände: `running`, `success`, `failed` und "noch nie gescannt" (`last_scan == null`).
- [ ] Leerzustand (`GET /projects` → `[]`): Hinweistext + Link zu `/projects/new`, keine kommentarlos leere Liste.
- [ ] Lade- und Fehlerzustand sind optisch von Leerzustand unterscheidbar — ein Backend-Fehler darf nicht wie "keine Projekte" aussehen.
- [ ] Jede Karte verlinkt auf `/projects/:id`; ein Link zu `/projects/new` ist immer sichtbar, auch bei nicht-leerer Liste.

**Projekt-Anlage (`/projects/new`)**

- [ ] Namensfeld: Pflichtfeld; Submit bei leerem/reinem Whitespace-Namen blockiert oder mit sichtbarem Validierungsfehler.
- [ ] FolderBrowser lädt initial die Wurzelebene (`GET /opencloud/browse` ohne `path`) und zeigt nur Verzeichnisse.
- [ ] Klick auf Ordnereintrag lädt genau eine Ebene tiefer über den vom Backend gelieferten `path`; Breadcrumb erlaubt Rücksprung zu jeder vorherigen Ebene, ohne dass eine bereits geladene Ebene erneut angefragt wird (Cache pro Pfad).
- [ ] Leere Unterordner-Ebene (`GET /opencloud/browse` → `[]`): "keine Unterordner"-Hinweis statt leerer Fläche; der aktuell angezeigte Ordner bleibt trotzdem als Zielordner bestätigbar.
- [ ] Backend-Fehler beim Browse (400 + `detail`): Inline-Fehlermeldung im FolderBrowser, Submit bleibt deaktiviert, keine kaputte Restseite.
- [ ] Submit → `POST /projects` mit `name` + zuletzt bestätigtem `path`; Submit-Button deaktiviert, solange die Anfrage läuft (Doppelklick-Schutz).
- [ ] 201 → Navigation zu `/projects/:id` der neuen ID.
- [ ] 409 (Namenskonflikt): `detail` wird angezeigt, Formular (Name + gewählter Pfad) bleibt erhalten, kein Redirect.
- [ ] 400 (ungültiger/nicht gefundener Ordner): `detail` wird angezeigt, Formular bleibt editierbar, FolderBrowser-Auswahl wird nicht automatisch zurückgesetzt.
- [ ] Abbrechen-Link zurück zu `/`.

**Projekt-Detail (`/projects/:id`)**

- [ ] Lädt/zeigt `GET /projects/{id}`; 404 → eigener "Projekt nicht gefunden"-Zustand statt leerer/kaputter Seite.
- [ ] "Aktualisieren"-Button aktiv, wenn kein Scan läuft (`last_scan == null` oder `status != "running"`).
- [ ] Klick löst `POST /projects/{id}/scan` aus; Button wird synchron mit dem Klick deaktiviert (nicht erst nach Antwort) und bleibt es, bis entweder Polling `running` bestätigt oder der Trigger selbst fehlschlägt (dann wieder aktivierbar + Fehlermeldung).
- [ ] Doppelklick vor Eintreffen der ersten 202-Antwort löst genau einen `POST .../scan`-Request aus, nicht zwei.
- [ ] Nach 202 (`{"status":"queued"}`): Invalidierung/Refetch von `GET /projects/{id}`; Polling ist aktiv, solange `last_scan.status == "running"`, und stoppt exakt beim ersten `success`/`failed`-Response.
- [ ] `success`: `photos_added`/`photos_updated`/`photos_removed`/`files_skipped` je einzeln angezeigt — auch wenn ein Zähler `0` ist.
- [ ] `failed`: `error_message` angezeigt, "Aktualisieren" sofort wieder aktivierbar (kein Dauer-Fehlerzustand).
- [ ] Verlassen der Seite während aktivem Polling und Rückkehr: kein doppeltes Intervall, keine Fetches nach Unmount.
- [ ] Zurück-Link zur Projektliste.

## Datenmodell-Bezug

Keine neuen Entitäten. Konsumiert ausschließlich die in Spec 0001 bereits implementierten Modelle/Schemas `Project`/`ProjectOut`/`ScanSummary`, siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Architektur / Umsetzung

**Abhängigkeit (Prerequisite-Spec):** Setzt gemäß [`roadmap.md`](../roadmap.md) eine bereits implementierte Auth-Spec voraus (Login-Screen, geschützte Routen, Token-Handling gemäß [`decisions/0003-auth-model.md`](../decisions/0003-auth-model.md)) — das ist explizit **nicht** Teil dieser Spec. Diese Spec liefert nur das Routing-/API-Client-Grundgerüst und die drei Kernrouten; wo später ein Auth-Layer eingehängt wird, ist unten (API-Client) berücksichtigt, aber nicht vorweggenommen.

**Neue Abhängigkeit / ADR:** Routing (`react-router`) und Server-State-Management (`@tanstack/react-query`) sind neue externe Abhängigkeiten und damit laut `CLAUDE.md` architekturrelevant — festgehalten in [`decisions/0004-frontend-app-shell.md`](../decisions/0004-frontend-app-shell.md). React Router (declarative mode, keine Loader/Actions) für Routen und URL-Zustand; TanStack Query für sämtlichen Server-Zugriff, weil der Scan-Status-Polling-Bedarf (`refetchInterval` nur solange `status == "running"`) mit reinen Router-Loadern deutlich umständlicher wäre und dieselbe Bibliothek von Spec 0002 direkt wiederverwendet wird.

**Backend:** keine funktionalen Änderungen an den Endpunkten selbst — die Spec konsumiert die in Spec 0001 bereits implementierten Endpunkte (`GET/POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/scan`, `GET /opencloud/browse`) 1:1. Zwei kleine, in dieser Spec mit umzusetzende Backend-Härtungen (siehe Security): CORS-Konfiguration und Path-Traversal-Fix in `opencloud/client.py::_join`.

### Frontend — neue Komponenten

```
frontend/src/
  main.tsx                 # QueryClientProvider + BrowserRouter, rendert App
  App.tsx                  # Routen-Tabelle (<Routes>/<Route>) + minimales Layout/Nav
  pages/
    ProjectListPage.tsx     # "/"                     — Projektliste
    ProjectCreatePage.tsx   # "/projects/new"         — Formular + FolderBrowser
    ProjectDetailPage.tsx   # "/projects/:projectId"  — Projektdaten, Scan-Trigger/-Status
  components/
    FolderBrowser.tsx       # kontrollierte Ordner-Navigation
  api/
    client.ts                # Fetch-Wrapper: request<T>(), ApiError-Klasse, Basis-URL
    types.ts                  # ProjectOut, ScanSummary, BrowseEntry
    projects.ts                # listProjects, createProject, getProject, triggerScan
    opencloud.ts                # browseFolder(path)
  hooks/
    useProjects.ts               # useProjectsQuery, useProjectQuery (mit refetchInterval), useCreateProjectMutation, useTriggerScanMutation
    useOpenCloudBrowse.ts         # useOpenCloudBrowseQuery(path)
```

**API-Client (`api/client.ts`):** schlanker `fetch`-Wrapper (`request<T>(path, init): Promise<T>`), keine zusätzliche HTTP-Bibliothek. Basis-URL aus `import.meta.env.VITE_API_BASE_URL` (neue Env-Variable, `.env.example`/`docker-compose.yml` werden bei der Umsetzung ergänzt). Bei nicht-2xx-Antworten wird eine `ApiError(status, detail)` geworfen (`detail` aus dem Backend-JSON-Feld). `client.ts` ist die einzige Stelle, die tatsächlich HTTP-Requests baut — die spätere Auth-Spec kann hier einen `Authorization`-Header ergänzen, ohne Routing oder React-Query-Nutzung anzufassen.

**React-Query-Nutzung:** Query-Keys: `["projects"]`, `["project", id]`, `["opencloud", "browse", path]`. `useProjectQuery(id)` pollt via `refetchInterval` nur solange `last_scan?.status === "running"` — stoppt automatisch, sobald der Scan fertig ist. `useTriggerScanMutation` invalidiert nach Erfolg `["project", id]`. Doppel-Klick-Schutz: „Aktualisieren"-Button ist disabled, wenn `mutation.isPending || project.last_scan?.status === "running"`.

**Ordner-Browser (`components/FolderBrowser.tsx`):** `GET /opencloud/browse?path=` liefert pro Aufruf nur die direkten Unterordner eines Pfads — "Navigation" entsteht rein client-seitig durch Pfad-Drilldown: kontrollierte Komponente (`value: string`, `onChange: (path: string) => void`), lädt über `useOpenCloudBrowseQuery(value)` die Kinder des aktuellen Pfads (React-Query cached jede Ebene unter ihrem eigenen Key). Klick auf einen Unterordner ruft `onChange(entry.path)`; ein aus `value` abgeleiteter Breadcrumb-Pfad erlaubt den Sprung auf jede übergeordnete Ebene inkl. Drive-Root. Kein separater "Ordner bestätigen"-Schritt: der aktuell angezeigte Ordner ist immer der Kandidat für `opencloud_path`, echte Bestätigung ist das Formular-Submit selbst.

### Umsetzungsreihenfolge

1. `api/client.ts` + `api/types.ts` (Fehlerbehandlung, Basis-URL) — TDD mit gemocktem `fetch`.
2. `api/projects.ts` + `api/opencloud.ts` (reine Fetch-Funktionen, unabhängig von React testbar).
3. `hooks/` (React-Query-Hooks inkl. Polling-Logik) — Tests mit `QueryClientProvider`-Wrapper.
4. Routing-Grundgerüst (`main.tsx`/`App.tsx`, drei leere Routen) + `MemoryRouter` in Tests.
5. `pages/ProjectListPage.tsx`, dann `components/FolderBrowser.tsx` + `pages/ProjectCreatePage.tsx`, zuletzt `pages/ProjectDetailPage.tsx`.
6. Backend-Härtungen (CORS-Middleware, Path-Traversal-Fix in `_join`) — unabhängig von der Frontend-Reihenfolge, aber vor Merge/Deploy dieser Spec abgeschlossen.

## UI/UX

Erste sichtbare Oberfläche von PhotoSort überhaupt. Bezug: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md), das mit dieser Spec initial angelegt wurde.

### Projektliste (`/`)

- Layout: einspaltige Liste von Projekt-Karten (mobil), auf breiteren Viewports zweispaltiges Wrap-Grid. Jede Karte ist als Ganzes tap-bar (≥44×44px) und verlinkt auf `/projects/:id`.
- Kurzstatus pro Karte als Badge (generische Prozess-Status-Farben aus dem Design-System): `running` = neutraler Akzentton + rotierendes Icon, `success` = Grün + Haken, `failed` = Rot + Warnsymbol.
- Ladezustand: Skeleton-Platzhalterkarten statt Vollbild-Spinner. Fehlerzustand: kontextnahes Banner mit "Erneut versuchen". Leerzustand: Hinweistext + Button "Neues Projekt anlegen".
- Kopfbereich trägt zusätzlich einen "Neues Projekt"-Button, auch wenn bereits Projekte existieren.

### Projekt-Anlage (`/projects/new`)

- Einspaltiges Formular (mobil wie Desktop gleich aufgebaut): Namensfeld oben, darunter der `FolderBrowser`.
- `FolderBrowser`: Breadcrumb-Leiste oben (jedes Segment klickbar), darunter eine Liste der direkten Unterordner als vollflächig tap-bare Zeilen (≥44px Höhe, Ordner-Icon + Name). Tap navigiert eine Ebene tiefer — kein separater Bestätigen-Schritt.
  - Ladezustand pro Ebene: Skeleton-Zeilen nur innerhalb der Ordner-Liste. Leere Unterordner-Ebene: Textzeile "Keine Unterordner".
  - Breadcrumb und Zeilen vollständig per Tastatur bedienbar.
- Validierungsfehler vom Backend (400/409): Banner am Formularanfang mit dem `detail`-Text wörtlich, zusätzlich optische Markierung des betroffenen Bereichs (Namensfeld bei 409, Ordner-Browser bei 400).
- Submit-Button deaktiviert, solange die Anfrage unterwegs ist (Busy-Button-Muster), inkl. Inline-Indikator im Button selbst. Abbrechen-Link zurück zu `/`.

### Projekt-Detail (`/projects/:id`)

- Kopfbereich: Projektname, OpenCloud-Pfad, darunter der letzte Scan-Status.
- "Aktualisieren"-Button: deaktiviert und mit Inline-Indikator ("Scan läuft…"), solange die Trigger-Anfrage unterwegs ist oder der per Polling beobachtete Status `running` ist — ein einziges, durchgängiges Busy-Zeichen.
- Noch nie gescannt: neutrale Meldung "Noch nicht gescannt", Button sofort nutzbar.
- Status `running`: Statuszeile mit rotierendem Icon, Text per `aria-live="polite"` nur bei tatsächlichem Statuswechsel angekündigt.
- Status `success`: Zähler als kleine Stat-Reihe, auf schmalen Viewports zweispaltig umbrechend.
- Status `failed`: Fehler-Banner mit `error_message` wörtlich; Button bleibt danach normal nutzbar. Zurück-Link zur Projektliste.

### Design-System-Ergänzungen (im Zuge dieser Spec vorgenommen)

`specs/architecture/0004-design-system.md` initial angelegt bzw. um folgende, ab jetzt projektweit gültige Muster ergänzt: generische Prozess-Status-Farben (`running`/`success`/`failed`, getrennt von den Foto-Bewertungsfarben aus Spec 0002, aber dieselben Grün-/Rottöne wiederverwendend), das Muster "Aktions-Button während laufender Anfrage" (Busy-Button), Erweiterung des Fehler-/Ladezustand-Musters auf Formulare und Listen.

## Security

**Sicherheitsrelevant:** Ja — erstes Feature mit echtem Browser-Frontend, das die API cross-origin aufruft, sowie erster Nutzereingabe-Pfad (Ordner-Browser/Projekt-Anlage), der in den OpenCloud-Client fließt. Sicherheitskonzept: [`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md).

- **CORS (Muss-Kriterium):** Backend (`backend/src/photosort/main.py`) hat aktuell keine `CORSMiddleware` konfiguriert. Sobald das Frontend (eigener Origin/Port) Requests aus dem Browser stellt, muss eine explizite, restriktive CORS-Konfiguration ergänzt werden: nur die konfigurierte Frontend-Origin erlauben, kein Wildcard `*`. Ohne diesen Fix könnte jede beliebige Website im selben Netzwerksegment Anfragen an die API stellen.
- **Path-Traversal in `opencloud/client.py::_join` (Muss-Kriterium):** `_join()` filtert `..`-Segmente nicht heraus. Über den `path`-Parameter von `GET /opencloud/browse` (vom FolderBrowser dieser Spec direkt genutzt) sowie über den beim Anlegen eines Projekts gewählten Ordnerpfad kann ein Aufrufer mit `..`-Segmenten aus dem vorgesehenen Wurzelverzeichnis herauslaufen. Fix: `..`-Segmente nach Normalisierung ablehnen/herausfiltern, bevor der Pfad in eine WebDAV-Anfrage einfließt — muss vor Merge dieser Spec umgesetzt sein.
- **Eingabevalidierung Ordner-Browser/Projekt-Anlage:** wird serverseitig durch die o.g. `_join`-Korrektur abgesichert; das Frontend bildet keine eigene, parallele Pfad-Validierung nach (Backend-`detail`-Text wörtlich anzeigen statt Client-seitig zu duplizieren).
- **Auth (bekannter, projektweiter Zustand, kein neuer Befund dieser Spec):** `get_current_user` existiert weiterhin nicht; die mit dieser Spec sichtbar gemachten Endpunkte sind damit weiterhin ungeschützt — bereits vor dieser Spec bestehender Zustand (Spec 0001). Diese Spec setzt laut Architektur-Abschnitt eine bereits implementierte Auth-Spec als Prerequisite voraus (Stakeholder-Entscheidung vom 2026-07-20) — **Implementierung/Deployment dieser Spec ist blockiert, bis `get_current_user` real gegen JWT prüft**, analog zum Blocker-Muster in Spec 0002.
- **CSRF/Token-Transport:** noch keine Auth-Entscheidung zu Bearer- vs. Cookie-Übertragung getroffen — betrifft diese Spec nicht direkt, wird im Sicherheitskonzept als offene Lücke geführt.

## Entscheidungen (2026-07-20, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Auth-Reihenfolge:** Diese Spec baut auf einer bereits implementierten, separaten Auth-Spec auf und ist implementierungsseitig blockiert, bis diese existiert — Login/geschützte Routen/Token-Handling sind explizit nicht Teil dieser Spec.
- **Ordner-Browser:** visueller, navigierbarer Ordner-Browser auf Basis von `GET /opencloud/browse` (Breadcrumb-Drilldown) statt reiner Text-Pfadeingabe.
- **Scan-Trigger-UI:** gehört zum Scope dieser Spec — Projekt-Detailseite mit "Aktualisieren"-Button und Scan-Status-Anzeige, statt einer separaten späteren Erweiterung.
- **Routing/Server-State:** `react-router` + `@tanstack/react-query`, siehe neue ADR [`decisions/0004-frontend-app-shell.md`](../decisions/0004-frontend-app-shell.md).
- **Design-System:** wird mit dieser Spec initial angelegt (statt wie ursprünglich in Spec 0002 vorgesehen), da dieses Feature zeitlich zuerst kommt und die erste sichtbare Oberfläche ist.
- **Path-Traversal-Fix:** wird als kleines Muss-Kriterium in diese Spec mit aufgenommen statt als separates Ticket verschoben zu werden.
- **Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird mit dieser Spec initial angelegt, analog zu Testkonzept/Design-System.
- **Testebenen:** Unit-Tests für `FolderBrowser` (kontrolliert, ohne Router/Query) und `api/client.ts`; Integrationstests für Seiten mit echtem `MemoryRouter`/`QueryClientProvider`, API an der Modulgrenze gemockt (`vi.mock`, kein MSW). Kein E2E-Setup (analog Spec 0002) — manueller Smoke-Test vor Merge bleibt Pflicht.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec. Die verbleibende Prerequisite (Auth-Implementierung) ist eine eigene, noch zu schärfende Spec — siehe `specs/roadmap.md`.

## Out of Scope

Login-Screen, geschützte Routen, Token-Speicherung/-Handling (separate Auth-Spec, blockierendes Prerequisite). Bearbeiten/Löschen bestehender Projekte, mehrere Ordner pro Projekt, Umbenennen. Foto-Anzeige/-Kategorisierung selbst (Spec 0002). Komponentenbibliothek/Theming über das initiale Design-System hinaus.
