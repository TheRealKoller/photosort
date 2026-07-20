# 0004 - Frontend-Anwendungsgrundgerüst: Routing und Server-State

**Status:** Accepted
**Datum:** 2026-07-20

## Kontext

Das Frontend ist bisher reines Vite/React-Template ohne Router, ohne API-Client, ohne Server-State-Management (`frontend/package.json` enthält nur `react`/`react-dom`, siehe [`decisions/0001-tech-stack.md`](./0001-tech-stack.md)). Ursprünglich im Zuge der Spec "Minimales Projekt-Frontend" (0005) entworfen; seit der Reihenfolge-Entscheidung vom 2026-07-20 (siehe `specs/roadmap.md`) führt tatsächlich Spec "Auth-Implementierung" (0006) beide Bibliotheken zuerst ein (`ProtectedRoute` braucht Routing, der Login-`useMutation`-Aufruf braucht React Query) — die hier getroffene Entscheidung gilt unverändert für beide sowie für die nachfolgende Spec "Manuelle Kategorisierung" (Grid/Swipe/Vergleich, Foto-Pagination, Bewertungs-Mutationen), die direkt darauf aufbaut, ohne es zu ersetzen. Beide hier gewählten Bibliotheken sind neue externe Abhängigkeiten und damit laut `CLAUDE.md` architekturrelevant.

## Entscheidung

- **Routing:** `react-router` (v7, "declarative mode": `BrowserRouter`/`Routes`/`Route`, kein Einsatz der Loader/Action-Datenschicht des Frameworks). Routen-URL trägt Navigations- und Filterzustand (z.B. spätere Filter-Query-Parameter in Spec 0002), nicht die Server-Daten selbst.
- **Server-State/Datenzugriff:** `@tanstack/react-query` für sämtliche Backend-Aufrufe (Queries für Lesezugriffe, Mutations für Schreibzugriffe), obenauf auf einem schlanken, selbstgeschriebenen Fetch-Wrapper (kein zusätzliches HTTP-Client-Paket wie `axios` — `fetch` genügt, die Bibliothek liefert nur den Wrapper, nicht den Transport).
- Beide Bibliotheken werden unabhängig voneinander eingesetzt: Routing entscheidet nicht über Daten-Laden (keine Router-Loader), React Query entscheidet nicht über URL-Struktur.

## Begründung

- **Warum React Router statt selbstgebautem Switch:** Standard-Bibliothek im React-Ökosystem (passt zur in `0001-tech-stack.md` genannten Priorität "gut dokumentiert, ausgereiftes Tooling"), verbreitetste Trainingsdatenbasis — relevant, da die Codebasis primär von einer KI gewartet wird. Verschachtelte Routen (`/projects/:id`, später `/projects/:id/photos/:photoId`) und `useSearchParams` für Filterzustand (von Spec 0002 explizit gefordert: "Filterzustand im URL-Query-Parameter") werden ohne Zusatzaufwand unterstützt.
- **Warum kein Router mit Datenschicht (Loader/Actions):** Der Polling-Bedarf für den Scan-Status (Endpunkt neu abfragen, solange `status == running`, automatisch stoppen danach) ist mit reinen Router-Loadern deutlich umständlicher (kein eingebautes Intervall-Refetch, kein Cache-Invalidierungsmodell) als mit einer dedizierten Server-State-Bibliothek. Zwei separate Datenwege (Loader für Erstladen, eigene Lösung fürs Polling) wären genau die Art von uneinheitlichem Muster, die diese Rolle vermeiden soll.
- **Warum TanStack Query statt eigenem `useEffect`/`useState`-Fetch-Hook:** Der entscheidende Punkt ist der Scan-Status: `refetchInterval` als Funktion des zuletzt geladenen Werts (aktiv nur solange `last_scan?.status === "running"`, sonst aus) ist eine eingebaute, gut getestete Fähigkeit der Bibliothek — von Hand nachgebaut bräuchte es eigene Intervall-/Cleanup-/Race-Condition-Logik (Doppel-Requests bei schnellem Route-Wechsel, verpasstes Abschalten des Pollings). Cache-Invalidierung nach der Scan-Trigger-Mutation (`queryClient.invalidateQueries`) ersetzt manuelles Neuladen. Für Spec 0002 (paginiertes Foto-Listing, Bewertungs-Mutationen mit optimistischem Update) ist dasselbe Werkzeug direkt wiederverwendbar, statt dass dort ein zweites Datenzugriffsmuster entsteht.
- **Warum kein größerer Zusatz wie `axios`:** `fetch` deckt alles ab, was gebraucht wird (JSON, Query-Parameter, Status-Codes); ein eigener, kleiner Wrapper reicht, um Basis-URL, JSON-Parsing und einheitliche Fehlerbehandlung (Backend-`detail`-Feld aus 4xx-Antworten) an einer Stelle zu bündeln. Eine weitere HTTP-Bibliothek wäre hier reine Redundanz zu `fetch`.
- **Zukunftsfähigkeit für Auth:** Der Fetch-Wrapper ist die einzige Stelle, die tatsächlich HTTP-Requests baut (ein "Choke Point" für Header). Wenn die separate Auth-Spec später einen Authorization-Header/Token-Refresh braucht, wird das dort ergänzt, ohne Routing oder React-Query-Nutzung anzufassen. Das ist keine vorgezogene Auth-Implementierung, nur eine Struktur, die einem späteren Auth-Layer nicht im Weg steht.

## Konsequenzen

- Zwei neue Frontend-Abhängigkeiten (`react-router`, `@tanstack/react-query`) in `frontend/package.json`, zusätzlicher Test-Aufwand: Komponenten, die Routing/Query nutzen, brauchen in Tests einen `MemoryRouter`- bzw. `QueryClientProvider`-Wrapper (Konvention für `test-engineer`).
- Kein Server-Side-Rendering und keine Router-Loader — falls ein späteres Feature SSR oder Such-maschinen-Indexierung bräuchte, wäre das eine neue ADR (aktuell irrelevant: privates Zwei-Nutzer-PWA-Tool, kein öffentlicher Inhalt).
- React Query führt einen eigenen In-Memory-Cache mit eigenem Lebenszyklus (`QueryClientProvider` in `main.tsx`) ein — Entwickler müssen Query-Keys konsistent benennen (`["project", id]`, `["projects"]`, `["opencloud", "browse", path]`), sonst drohen Stale-Data-Bugs. Wird in der Umsetzung der Feature-Spec als Konvention festgehalten.
