# 0043 - Tage in der Kuratierungsansicht auf-/zuklappbar

**Status:** Implemented ([PR #100](https://github.com/TheRealKoller/photosort/pull/100))
**Erstellt:** 2026-08-16
**Bezug:** `specs/inbox/0024-kuratierung-tage-zuklappbar.md` (Ursprungs-Idee), revidiert Teile von Spec [`0039`](./0039-kuratierung-tage-und-benannte-cluster.md)

## Ziel

Bei Projekten mit vielen Tagen wird die durchgehende Tages-Liste in der Kuratierungsansicht unübersichtlich. Tage sollen einzeln sowie über zwei globale Aktionen ("Alle aufklappen"/"Alle zuklappen") auf- und zugeklappt werden können, um Platz zu sparen und organisierter durch ein großes Projekt zu arbeiten. Ein zugeklappter Tag bleibt über eine kompakte Kurzinfo (Fotoanzahl) identifizierbar, ohne dass man ihn öffnen muss.

## User Story

Als Nutzer (Daniel oder Partnerin) möchte ich Tage in der Kuratierungsansicht einzeln und über eine "Alle auf-/zuklappen"-Aktion zu- und aufklappen können, damit ich bei Projekten mit vielen Tagen Platz spare und mich gezielt auf einzelne Tage konzentrieren kann.

## Akzeptanzkriterien

- [ ] Die gesamte Tages-Kopfzeile (Wochentag+Datum, Kurzinfo) ist ein `<button type="button" aria-expanded aria-controls>`; kein separates Icon als alleiniger interaktiver Träger — die klickbare Fläche umfasst die ganze Kopfzeile (Touch-Ziel ≥44px).
- [ ] Beim ersten Rendern/nach Reload sind alle Tage aufgeklappt (leere Menge zugeklappter Tage als Default) — kein `localStorage`/`sessionStorage`/Query-Param, keine Persistierung.
- [ ] Klick auf den Trigger eines Tages ändert ausschließlich dessen eigenen Klapp-Zustand; andere Tage bleiben unverändert, auch bei mehreren gleichzeitig zugeklappten Tagen.
- [ ] Ist ein Tag zugeklappt, wird der komplette darunterliegende Cluster/Kategorie/Foto-Teilbaum per conditional JSX nicht gerendert (nicht nur CSS-versteckt).
- [ ] Kurzinfo `(X Fotos)` wird in der Kopfzeile **nur angezeigt, wenn der Tag zugeklappt ist**; im aufgeklappten Zustand fehlt sie (die Fotos sind dort direkt sichtbar).
- [ ] Fotoanzahl ist eine reine Ableitung aus bereits geladenen Daten (Summe `photos.length` über alle Cluster/Kategorien des Tages aus `groups[dayKey]`, z.B. `countPhotosInDay(...)`), kein neuer State/Request.
- [ ] Zwei globale Buttons oberhalb der Tag-Liste: "Alle Tage aufklappen" leert die zugeklappte-Tage-Menge vollständig; "Alle Tage zuklappen" befüllt sie mit allen aktuell vorhandenen `dayKey`s. Beide bleiben auch bei genau einem Tag im Projekt sichtbar und funktionsfähig.
- [ ] Ein Tag mit 0 sichtbaren Fotos (Sticky-Leerzustand aus Spec 0039) bleibt auch zugeklappt sichtbar und zeigt korrekt `(0 Fotos)`; der Leerzustandstext selbst gilt als Teil des Cluster-Teilbaums und wird bei Zugeklapptheit mit ausgeblendet.
- [ ] Wird während der Sitzung das letzte Foto eines zugeklappten Tages abgelehnt, aktualisiert sich `(X Fotos)` beim nächsten Render live, ohne dass sich der Klapp-Zustand dieses oder eines anderen Tages ändert.
- [ ] Ein `dayKey`, der erst nach einem Klick auf "Alle Tage zuklappen" neu in `groups` auftaucht, ist nicht automatisch mit-zugeklappt, sondern erscheint aufgeklappt (Default-Verhalten, kein rückwirkendes Einsammeln).
- [ ] `aria-expanded`/`aria-controls` sind korrekt gesetzt und verknüpft (IDs aus `dayKey`, Format `YYYY-MM-DD`, bereits ID-sicher); Klapp-Zustand ist nicht nur über Farbe/Symbol erkennbar.
- [ ] Bestandsschutz: Top-N-Query-Parameter, In-place-Nachrücken via Skeleton, Verwerfen-Button-Verhalten, Backlink sowie `clusterMetaRef`/`knownGroupKeysRef`-Sticky-Verhalten aus Spec 0039 bleiben unverändert funktionsfähig, auch innerhalb eines klappbaren Teilbaums. Insbesondere: Kollabieren/Expandieren eines Tages während eine Verwerfen-Mutation für eines seiner Fotos noch läuft, hinterlässt keine dauerhaft hängende Skeleton-Kachel nach erneutem Aufklappen.

## Datenmodell-Bezug

Keines. Reine Ableitung aus bereits vorhandenen, clientseitig geladenen `PhotoOut`-Daten (siehe [`docs/architecture.md`](../../docs/architecture.md)). Kein neuer Endpoint, kein neues Feld.

## Architektur / Umsetzung

Reine Frontend-Änderung, kein Backend-Eingriff, keine neue Abhängigkeit. Keine neue ADR nötig — technische Detailentscheidung innerhalb der bereits akzeptierten Richtung von ADR [`decisions/0011-ui-component-library.md`](../decisions/0011-ui-component-library.md): dort ist Radix explizit nur "wo gebraucht" vorgesehen, native HTML-Muster (Button, `aria-*`) bleiben für Fälle ohne komplexe Interaktions-/Fokuslogik gültig. Ein Auf-/Zuklappen einzelner, bereits vollständig geladener DOM-Abschnitte ohne Animation, ohne Fokus-Trap, ohne serverseitig gerenderten Zwischenzustand ist genau so ein Fall — `@radix-ui/react-collapsible` würde primär animierte Höhenübergänge und SSR-Robustheit liefern, die hier nicht gebraucht werden. Ein natives `<button aria-expanded aria-controls>` + bedingtes Rendering der Kindelemente ist etabliert, zugänglich und ohne zusätzliche `package.json`-Abhängigkeit umsetzbar.

**Betrifft ausschließlich `frontend/src/pages/CurateCategoriesPage.tsx`** (revidiert den UI/UX-Abschnitt von Spec 0039, der Klappbarkeit ursprünglich als Out-of-Scope abgelehnt hatte — siehe "Entscheidungen"). Kein Überschneidungsrisiko mit Spec 0042 (Accepted, noch nicht umgesetzt): 0042 restrukturiert `ProjectDetailPage.tsx`/führt `KuratierungStepPage.tsx` ein, fasst `CurateCategoriesPage.tsx` selbst nicht an (verifiziert: kein Treffer für `/curate` in Spec 0042 außer dem unveränderten Link-Ziel). Beide Features können unabhängig voneinander bzw. in beliebiger Reihenfolge umgesetzt werden.

**State-Design:**
- Neuer lokaler State in `CurateCategoriesPage.tsx`, kein Context (Projekt hat kein `createContext`/`useContext`-Pattern, hier auch nicht nötig — Zustand ist nur innerhalb dieser einen Seite relevant):
  ```ts
  const [collapsedDayKeys, setCollapsedDayKeys] = useState<Set<string>>(new Set())
  ```
  Leeres Set = alles aufgeklappt (Default), erfüllt direkt "beim Reload ist immer alles aufgeklappt" ohne Sonderfall-Logik.
- Einzeln klappen: Toggle-Funktion, die den `dayKey` im Set hinzufügt/entfernt (neues `Set`, keine Mutation).
- Global: "Alle Tage aufklappen" → `setCollapsedDayKeys(new Set())`; "Alle Tage zuklappen" → `setCollapsedDayKeys(new Set(dayKeys))` (nutzt die bereits vorhandene, pro Render aus `groups` abgeleitete `dayKeys`-Liste).
- Rendering: bei `collapsedDayKeys.has(dayKey)` wird der Cluster-Teilbaum gar nicht gerendert statt nur per CSS versteckt — spart bei großen Projekten auch tatsächliche Render-Arbeit.

**Zusammenspiel mit `knownGroupKeysRef`/`clusterMetaRef` (Sticky-Leerzustand-Mechanik aus Spec 0039):** Kein Konflikt, keine Änderung nötig. Die Kopfzeile eines Tages wird unabhängig vom Klapp-Zustand bei jedem Render neu aus `groups[dayKey]` abgeleitet — Klappen betrifft nur, ob die Kindelemente gerendert werden. Wird während einer Sitzung das letzte Foto eines zugeklappten Tages abgelehnt, aktualisiert sich die Kurzinfo deshalb live, ohne dass der Klapp-Zustand davon weiß. `knownGroupKeysRef` hält `dayKey`s sessionlang sticky — ein `collapsedDayKeys`-Eintrag für einen erschöpften Tag wird also nie verwaist.

**Kurzinfo-Berechnung:** eigene Top-Level-Funktion `countPhotosInDay(...)`, reine Ableitung aus vorhandenen Props (Summe `photos.length` über alle Cluster/Kategorien des Tages), unabhängig unit-testbar, kein neuer State/Request.

**Umsetzungsreihenfolge:**
1. `countPhotosInDay` als reine Top-Level-Funktion + Unit-Tests.
2. `collapsedDayKeys`-State + Toggle-/Global-Funktionen, zunächst ohne UI-Verdrahtung, Tests für Set-Übergänge.
3. Render-Änderung: Tages-Kopfzeile zum klickbaren Trigger + Kurzinfo ausbauen, Cluster-Teilbaum conditional rendern.
4. Zwei globale Buttons mit vorhandener `Button`-Komponente.
5. Regressionstest für das Zusammenspiel mit dem Sticky-Leerzustand.

Kein `docs/architecture.md`-Update nötig (kein neuer Systembaustein, kein neues Datenmodell, keine neue Abhängigkeit).

## UI/UX

**Sichtbare Oberfläche:** Ja. Reine Frontend-Änderung der bestehenden Kategorie-Kuratierungs-Seite (`/curate`), Erweiterung der in Spec 0039 eingeführten Tag-Gruppierung.

**Tages-Kopfzeile (klappbar):** Der gesamte Tages-Überschriftsbereich wird zu einem semantischen `<button type="button">` mit `aria-expanded={!isCollapsed}` und `aria-controls` (verweist auf die `id` des Cluster-Containers des Tages) umgebaut — kein separater winziger Icon-Button daneben. Label: dekoratives Symbol (`▼`/`▶`, `aria-hidden`) + Wochentag/Datum + Kurzinfo, wenn zugeklappt:
- **Aufgeklappt:** `▼ Montag 20.07.2026`
- **Zugeklappt:** `▶ Montag 20.07.2026 (47 Fotos)`

Button-Padding sorgt für ein Touch-Ziel von mindestens 44px. Zustand wird über das Symbol UND `aria-expanded` getragen, nicht nur über Farbe.

**Globale Buttons:** Zwei sekundäre, textbasierte Buttons oberhalb der Tag-Liste: "Alle aufklappen" und "Alle zuklappen" — setzen den Klapp-Zustand aller Tage einheitlich. Sekundärer Ton (Hilfsfunktion, keine Akzentfarbe).

**Kurzinfo-Format:** ausschließlich Fotoanzahl `(X Fotos)`. Kein Slot-Belegungs-Indikator ("X von Y Kategorien verfügbar") — das wäre eine technische Implementierungsdetail-Metrik statt Nutzerinformation und würde das Designprinzip "Durchsatz vor Erklärung" verletzen (Kategorie-Leerzustände sind ohnehin sichtbar, sobald ein Tag aufgeklappt wird).

**Keine Animation:** Sofortiges Auf-/Zuklappen ohne CSS-Transition — passt zu "Durchsatz vor Erklärung" (wiederkehrende Power-User, keine Erklär-Übergänge nötig) und ist technisch konsistent damit, dass der Teilbaum per conditional Rendering komplett auf-/abgebaut wird, nicht nur ein-/ausgeblendet.

**Betroffene Zustände:**
- Leerer Tag (Sticky-Leerzustand, 0 Fotos): bleibt sichtbar, zugeklappt zeigt `▶ Montag 20.07.2026 (0 Fotos)` — kein Sonderfall nötig.
- Sehr großer Tag mit vielen Clustern: der eigentliche Anwendungsfall, normales Muster ohne visuelle Sonderbehandlung.

**Kein Design-System-Update nötig:** Nutzt bestehende Buttons, Icons und Spacing-Tokens. Ein generisches Muster "Einklappbare Abschnitte mit globalem Batch-Control" könnte bei einem zweiten Anwendungsfall im Design-System dokumentiert werden, ist für diese Einzel-Implementierung aber noch nicht reif dafür.

## Security

Nicht relevant. `security-engineer` nicht konsultiert (siehe "Entscheidungen") — reine clientseitige UI-Zustandsänderung ohne neue Backend-Schnittstelle, ohne neues Datenfeld, ohne Auswirkung auf Auth/Berechtigungen oder die Sichtbarkeit von Daten zwischen den beiden Nutzern.

## Teststrategie

Erstes eigenes (nicht-natives) Disclosure-Widget im Projekt — anders als das bestehende `<details>`/`<summary>`-Muster (Spec 0030) ist `aria-expanded` hier ein von React literal gesetztes DOM-Attribut, kein browser-computed Wert, daher direkt via `getByRole('button', { expanded })`/`toHaveAttribute` in jsdom testbar.

**Unit:** `countPhotosInDay(...)` als reine Funktion — leerer Tag (0), ein/mehrere Cluster/Kategorien, Cluster mit `photos.length === 0`.

**Integration (`CurateCategoriesPage.test.tsx`):** Trigger-Rendering/Toggle über `getByRole('button', { expanded })`; Cluster-Teilbaum-Sichtbarkeit über `queryBy*`/`null` (nicht `toBeVisible`); Kurzinfo-Text nur zugeklappt vorhanden; globale Buttons bei gemischtem Vorzustand; Live-Update-Test (letztes Foto eines zugeklappten Tages wird verworfen → Zähler aktualisiert sich, Klapp-Zustand bleibt); Bestandsschutz-Regressionstests (Top-N, Skeleton, Verwerfen, Backlink, `clusterMetaRef`/`knownGroupKeysRef`) mit dem neuen Trigger-Wrapper um die Kopfzeile.

**E2E:** kein dediziertes Setup nötig, wie projektweit üblich.

**Nicht automatisiert testbar:** Touch-Ziel ≥44px (jsdom hat keine Layout-Engine) — manueller visueller Smoke-Test vor Merge.

**Testkonzept-Ergänzung:** `specs/architecture/0002-testkonzept.md` wird um eine kurze Sektion zum kontrollierten `aria-expanded`/`aria-controls`-Widget (`useState<Set>`, Gegenstück zum nativen `<details>`) ergänzt, damit das `<details>`-Testmuster (Prüfung über `open`-Attribut statt `aria-expanded`) nicht versehentlich übertragen wird. Umsetzung dieser Ergänzung ist Teil des `developer`-Workflows für diese Spec.

## Entscheidungen

- **Revision von Spec 0039:** Spec 0039 hatte Klappbarkeit von Tagen explizit als Out-of-Scope abgelehnt ("zusätzliche Expand-Klicks würden das Durchsatz-Designprinzip verletzen"). Diese Entscheidung wird hier bewusst revidiert — Begründung (Daniel, 2026-08-16): Projekte sind seither größer geworden, die durchgehende Liste wird bei vielen Tagen unübersichtlich; das überwiegt jetzt den ursprünglichen Durchsatz-Einwand.
- **Alternativ-Ansatz geprüft und verworfen:** Der in Spec 0039 selbst angedachte Alternativ-Ansatz "Sticky-Header/Springe-zu-Selektor" wurde im Rahmen dieses Schärfen-Gesprächs geprüft und verworfen — er löst die Navigation, aber nicht das explizit genannte Ziel "Platz sparen".
- **Keine neue Abhängigkeit:** `@radix-ui/react-collapsible` bewusst nicht eingeführt (siehe "Architektur / Umsetzung") — natives Button+conditional-Rendering-Muster reicht, keine ADR nötig.
- **Kein Slot-Belegungs-Indikator:** Ein ursprünglich erwogener "X von Y Kategorien noch verfügbar"-Zusatz in der Kurzinfo wurde verworfen (technisches Implementierungsdetail statt Nutzerinformation, verletzt "Durchsatz vor Erklärung").
- **Kurzinfo-Sichtbarkeit korrigiert:** Der erste UX-Entwurf hatte die Sichtbarkeit versehentlich umgekehrt (Fotoanzahl nur aufgeklappt sichtbar). Korrigiert auf die ursprünglich mit Daniel abgestimmte Fassung: Kurzinfo erscheint, wenn der Tag zugeklappt ist — das ist der Zweck der Kurzinfo (Übersicht ohne Aufklappen).
- **`security-engineer` nicht konsultiert (Schritt 8):** reine clientseitige UI-Zustandsänderung ohne Auth-, Schnittstellen-, Secrets-, Berechtigungs- oder Datenmodell-Bezug und ohne Auswirkung auf die Sichtbarkeit von Daten zwischen den beiden Nutzern.

## Offene Fragen

Keine.

## Out of Scope

- Persistierung des Klapp-Zustands über Reload/Sitzungen hinweg.
- Änderung der Tag-Gruppierungs-/Cluster-Bildungslogik selbst (Spec 0039 bleibt fachlich unverändert).
- Keyboard-Shortcuts fürs Klappen.
- Animierte Übergänge beim Auf-/Zuklappen.
- Ein Slot-Belegungs-Indikator ("X von Y Kategorien verfügbar") in der Kurzinfo.
