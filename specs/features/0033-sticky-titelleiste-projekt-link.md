# 0033 - Sticky Titelleiste mit Projekt-Kontext-Link

**Status:** Implemented ([PR #99](https://github.com/TheRealKoller/photosort/pull/99))
**Erstellt:** 2026-08-09
**Bezug:** [`inbox/0009-sticky-titelleiste-zurueck-link.md`](../inbox/0009-sticky-titelleiste-zurueck-link.md), [`features/0006-auth.md`](./0006-auth.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-09

**Nachtrag (2026-09-06, `architect`-Konsultation zu Spec [`0298`](./0298-projektnavigation-in-der-kopfzeile.md)):** Diese Spec bleibt bewusst `Implemented` und wird **nicht** auf `Superseded` gesetzt — Spec 0298 löst nur einen Teil von ihr ab (gleiches Vorgehen wie Spec [`0045`](./0045-kategorien-aus-statistiken-ableiten.md) gegenüber Spec 0038; eine vollständige Supersession würde falsch darstellen, was weiterhin gilt). Die Akzeptanzkriterien unten bleiben unverändert stehen, sie beschreiben korrekt den damals gebauten und akzeptierten Zustand. Abgelöst durch Spec 0298 sind:

- **AK2/AK4/AK8** — der einzelne Kopfzeilen-Link mit dem zugänglichen Namen "Projekt" und dem Ziel `/projects/{projectId}` geht in einer Navigationsgruppe mit vier gleichrangigen Zielen auf (Projektübersicht/Fotos/Vergleich/Einstellungen) und existiert danach nicht mehr als eigenständiges, andersartiges Element.
- **Die ausdrückliche Festlegung, dass `/projects/:projectId/curate` keinen Kopfzeilen-Link trägt** (in `App.tsx` als Kommentar an `PROJECT_ROUTES` festgehalten, hier durch die abschließende Aufzählung der Projekt-Routen in AK2 impliziert). Spec 0298 kehrt sie ausdrücklich um: die Kategorie-Kuratierung zählt seither als Route mit Projektkontext und zeigt die Navigationsgruppe. Der Grund für die Umkehr ist derselbe, der 2026-08-09 für die übrigen Seiten galt — von dort führte gar kein direkter Weg zu den Projektzielen.

Unverändert gültig bleiben **AK1** (sticky Kopfzeile), **AK3** (kein Projektkontext auf `/`, `/projects/new`, `/login` — insbesondere matcht `/projects/new` weiterhin nicht als `projectId`), **AK5**, **AK6** und **AK7** (die dort entfernten Duplikate bleiben entfernt; die dort ausdrücklich geschützten Links "Zurück zum Grid" und "Zur Vergleichsansicht" auf der Foto-Detailansicht bleiben auch unter Spec 0298 erhalten).

## Ziel

Der bestehende App-Header (`AppShell` in `frontend/src/App.tsx`) bleibt beim Scrollen nicht am oberen
Bildschirmrand — nach langem Scrollen durch viele Fotos (Grid-/Detailansicht) ist der bisherige
"Zurück zum Projekt"-Link am jeweiligen Seitenende schwer erreichbar. Diese Spec macht den Header
sticky und ergänzt ihn um einen Link, der von jeder Seite mit Projektkontext direkt zur
Projekt-Detailseite führt — statt zurückzuscrollen, ist die Rücknavigation dann immer sofort
sichtbar. Bestehende, dadurch redundant gewordene Seiten-Links entfallen; Links mit abweichendem
Ziel/Zusatznutzen bleiben unverändert bestehen.

## User Story

Als Nutzer der App (Daniel oder seine Frau, beim Durchsehen/Bewerten vieler Fotos) möchte ich von
jeder Seite innerhalb eines Projekts sofort, ohne zu scrollen, zur Projekt-Detailseite zurück
navigieren können, damit mich lange Fotolisten nicht mehr von der Ausgangsseite trennen.

## Akzeptanzkriterien

- [ ] **AK1 (sticky Header):** `AppShell`s `<header>` bleibt beim Scrollen einer Seite am oberen
      Viewport-Rand sichtbar (`sticky top-0 z-10 bg-bg`). Manueller Smoke-Test vor Merge (durch eine
      Fotoliste scrollen, Header bleibt sichtbar, kein Layout-Overlap, Light/Dark) — CSS-Sticky-
      Verhalten ist in `jsdom` nicht automatisiert prüfbar.
- [ ] **AK2 (Link erscheint mit Projektkontext):** Auf jeder Route, deren `pathname` gegen eine der
      vier Projekt-Routen matcht (`/projects/:projectId`, `/projects/:projectId/photos`,
      `/projects/:projectId/photos/:photoId`, `/projects/:projectId/compare`), rendert der Header
      genau einen zusätzlichen Link mit zugänglichem Namen "Projekt".
- [ ] **AK3 (Link fehlt ohne Projektkontext):** Auf `/`, `/projects/new` und `/login` rendert der
      Header keinen Link mit Namen "Projekt". Insbesondere matcht `/projects/new` **nicht** als
      Projektkontext (explizite Routen-Aufzählung statt Wildcard-Pattern, das `"new"` fälschlich als
      `projectId` lesen würde).
- [ ] **AK4 (Linkziel ist immer die Projekt-Detailseite):** `href` des Links ist auf allen vier
      Projekt-Routen exakt `/projects/{projectId}` (aus der aktuellen URL extrahiert) — unabhängig
      von Subpfad (`/photos`, `/photos/:photoId`, `/compare`) und unabhängig von Query-Parametern
      (z.B. `?filter=...` auf der Grid-Seite beeinflusst das Ziel nicht). Nicht kontextabhängig eine
      Ebene zurück.
- [ ] **AK5 (Design-System-Konformität):** Link ist über das bestehende `Button asChild` + `Link`-
      Muster implementiert (wie die PhotoSort-Wortmarke), Light/Dark-konsistent, erfüllt das
      44×44px-Touch-Ziel durch Wiederverwendung der bestehenden Button-Größenvariante.
- [ ] **AK6 (Barrierefreiheit):** Link hat zugänglichen Namen ("Projekt", Icon dekorativ/
      `aria-hidden`) und ist als natives `<a>` ohne Zusatzaufwand tastaturbedienbar.
- [ ] **AK7 (Konsolidierung — nur echte Duplikate entfernt):** Entfernt werden ausschließlich Links,
      die zum selben Ziel führen wie der neue Header-Link oder zur bereits vorhandenen PhotoSort-
      Wortmarke: "Zurück zum Projekt" auf `PhotoGridPage.tsx:217` und `PhotoComparePage.tsx:109`;
      "Zurück zur Projektliste" auf `ProjectDetailPage.tsx:171,192,542`. **Unverändert bleiben:**
      `PhotoDetailPage.tsx`s vier "Zurück zum Grid"-Links (bewahren den aktiven Filter, Ziel
      `/projects/{id}/photos{filterQuery}` ≠ Projekt-Detailseite) und der "Zur Vergleichsansicht"-
      Link (kein Zurück-Link, anderes Ziel).
- [ ] **AK8 (Self-Link auf der Projekt-Detailseite):** Auf `/projects/{id}` selbst zeigt der
      Header-Link auf dieselbe URL — keine Ausblendung oder Deaktivierung (bewusst einfach gehalten).

## Datenmodell-Bezug

Keine Änderung. Reines Frontend-Navigationsfeature, `projectId` wird ausschließlich aus der bereits
vorhandenen URL gelesen, keine neue Entität, kein neuer API-Aufruf.

## Architektur / Umsetzung

**Ansatz:** Erweiterung der bestehenden `AppShell` (`frontend/src/App.tsx`) um Sticky-Positionierung
und einen routenabhängigen Link. Kein neuer Context/State-Layer — `AppShell` liegt in derselben
Datei wie die Routen-Definitionen und liest die aktuelle Route direkt über `react-router`s
`useLocation()` + `matchPath()`.

**Betroffene Dateien:**

- `frontend/src/App.tsx` — Sticky-Header-CSS, neue Pfad-Matching-Logik, neuer Link im Header,
  gemeinsame Pfadmuster-Konstante (`PROJECT_ROUTES`).
- `frontend/src/pages/PhotoGridPage.tsx` — Entfernen des redundanten "Zurück zum Projekt"-Links
  (Zeile 217, AK7).
- `frontend/src/pages/PhotoComparePage.tsx` — Entfernen des redundanten "Zurück zum Projekt"-Links
  (Zeile 109, AK7).
- `frontend/src/pages/ProjectDetailPage.tsx` — Entfernen der drei redundanten "Zurück zur
  Projektliste"-Links (Zeilen 171, 192, 542, AK7).
- `frontend/src/App.test.tsx` — Erweiterung um Testfälle für Sichtbarkeit/Ziel des neuen Links.

**Neues Muster — Routen-Parameter außerhalb einer Page-Komponente lesen:** Eine einzige Modul-
Konstante `PROJECT_ROUTES` in `App.tsx` (Pfadmuster + zugehöriges Element für die vier
`:projectId`-Routen) speist **sowohl** die `<Route>`-Erzeugung **als auch** den `matchPath`-Aufruf
in `AppShell` — eine Quelle der Wahrheit statt zweier parallel gepflegter Listen (verhindert, dass
eine künftige `:projectId`-Route nur in `<Routes>` ergänzt wird, aber stillschweigend keinen
Header-Link bekommt). Explizite Aufzählung der vier Pfadmuster statt eines Wildcards wie
`/projects/:projectId/*`, da ein Wildcard `/projects/new` fälschlich als Projektkontext mit
`projectId="new"` matchen würde.

```ts
const PROJECT_ROUTES: { path: string; element: JSX.Element }[] = [
  { path: '/projects/:projectId', element: <ProjectDetailPage /> },
  { path: '/projects/:projectId/photos', element: <PhotoGridPage /> },
  { path: '/projects/:projectId/photos/:photoId', element: <PhotoDetailPage /> },
  { path: '/projects/:projectId/compare', element: <PhotoComparePage /> },
]

function useProjectIdFromRoute(): string | null {
  const location = useLocation()
  for (const { path } of PROJECT_ROUTES) {
    const match = matchPath(path, location.pathname)
    if (match?.params.projectId) return match.params.projectId
  }
  return null
}
```

> **Korrektur bei der Umsetzung (PR #99):** Dieses Codebeispiel matcht `/projects/new`
> fälschlich mit `projectId="new"` und verletzt damit AK3 — durch TDD im Rot-Schritt entdeckt.
> Die tatsächliche Implementierung ergänzt einen `RESERVED_PROJECT_ID_SEGMENTS`-Ausschluss und
> nutzt `ReactElement` statt `JSX.Element` (Typprüfungsfehler unter dem Projekt-`tsconfig`).
> Details siehe `specs/architecture/0002-testkonzept.md`.

`AppShell` rendert den Link nur, wenn `useProjectIdFromRoute()` nicht `null` liefert (AK2/AK3), Ziel
ist immer `/projects/${projectId}` (AK4).

**Neues Muster — Sticky App-Shell-Header:** `<header className="sticky top-0 z-10 bg-bg ...">`
(ergänzt bestehende Klassen). `z-10` ist der erste Eintrag einer projektweiten Z-Index-Konvention —
bleibt unter Radix-Portal-Overlays (Dialoge/Tooltips landen per Portal mit eigenen, höheren Werten
außerhalb des normalen Baums). `bg-bg` wird auf dem Header jetzt explizit gesetzt (bisher trug nur
der äußere Wrapper die Hintergrundfarbe), damit scrollender Inhalt im Sticky-Zustand nicht sichtbar
durchscheinen kann, falls eine künftige Seite einen abweichenden Hintergrund einführt. `<main>`
bleibt strukturell unverändert — normales Dokumentfluss-Scrollen genügt, da kein Vorfahre von
`<header>` `overflow`/`transform` setzt (würde den Sticky-Kontext brechen).

**Umsetzungsreihenfolge für `developer`:**

1. `PROJECT_ROUTES`-Konstante + Umbau der `<Routes>`-Erzeugung in `App.tsx` (rein strukturell, keine
   Verhaltensänderung — eigener erster TDD-Zyklus: bestehende Routen funktionieren unverändert).
2. `useProjectIdFromRoute()` + bedingter Link-Render in `AppShell` (AK2, AK3, AK4, AK8).
3. Sticky-CSS auf `<header>` (AK1) — separat testbar/reviewbar von Schritt 2.
4. Barrierefreiheit/Touch-Ziel des neuen Links (AK5, AK6) — im selben Zyklus wie Schritt 2.
5. Entfernen der vier redundanten Seiten-Links (AK7) — bewusst zuletzt, damit zwischenzeitlich nie
   eine Navigationsmöglichkeit fehlt.

**ADR-Pflicht:** Keine neue ADR. Weder neue Technologie noch externe Abhängigkeit noch
Datenmodell-Änderung — `react-router`, `matchPath` und Tailwind sind bereits akzeptierte Bausteine
(ADR [`0004`](../decisions/0004-frontend-app-shell.md), [`0011`](../decisions/0011-ui-component-library.md)).
Reine Implementierungsdetail-Entscheidung innerhalb bereits akzeptierter Richtungen. `docs/architecture.md`
bleibt unverändert (kein neuer Service, keine Datenmodell-/API-Änderung).

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) —
Sticky-App-Shell-Header mit kontextabhängigem Link ist ein neues wiederverwendbares Muster, wird
dort unter "Wiederkehrende Muster" ergänzt.

- **Platzierung:** neuer Button zwischen der PhotoSort-Wortmarke (links) und dem Nutzerbereich
  (rechts) im Header.
- **Gestaltung:** `variant="ghost"` (konsistent mit der Wortmarke), Text "Projekt" mit
  vorangestelltem Chevron-Icon (`‹`, dekorativ/`aria-hidden`) — klar unterscheidbar vom Home-Link
  "PhotoSort". Auf schmalen Mobile-Viewports darf der Text bei Platzmangel auf das Icon reduziert
  werden (Breakpoint-Entscheidung der Umsetzung); Baseline ist Text + Icon.
- **Projekt-Detailseite:** Link zeigt auf sich selbst, keine Ausblendung/Deaktivierung (AK8) — für
  zwei bekannten Nutzer harmlos, keine zusätzliche Zustandslogik nötig.
- **Sticky-Impact auf Mobile:** Header-Höhe bleibt unverändert (`py-3`, ca. 44–50px inkl.
  Text/Icons) — kein spürbarer Verlust an Bildfläche beim Fotoansehen; der Sticky-Ansatz selbst
  stand als Auslöser der Idee nicht zur Debatte.
- **Zustände:** kein Ladezustand (reiner Link, keine Anfrage), keine Fehlerzustände.
- **Barrierefreiheit:** zugänglicher Name über den Text "Projekt", vollständig tastaturbedienbar
  über das native `<a>`-Element (via `Link`, `Button asChild`), Touch-Ziel ≥44×44px durch
  bestehende Button-Größenvariante (`h-11`).

## Security

**Nicht relevant.** `security-engineer` wurde nicht konsultiert (siehe "Entscheidungen" unten) —
die Änderung führt keine neue externe Eingabe, keinen neuen Berechtigungs-Check und keine neue
Datensichtbarkeit zwischen den beiden Nutzern ein. Der Link verweist erneut auf eine `projectId`,
die im aktuellen Routen-Kontext bereits sichtbar/aktiv ist; keine neue Möglichkeit, auf fremde
Projekte zuzugreifen (Backend-Autorisierung für `/projects/{id}` bleibt unverändert, nur ein
zusätzlicher Client-seitiger Link auf eine bereits im Browser sichtbare ID).

## Teststrategie

- **Testebene:** ausschließlich Integrationsebene, Erweiterung des bestehenden `App.test.tsx`
  (echter `MemoryRouter` nötig, da `AppShell` `useLocation()` selbst liest und nicht separat
  exportiert ist — konsistent mit dem dort bereits etablierten Muster). Parametrisiert über alle
  sechs Routen (mit/ohne Projektkontext) je Präsenz und `href` des Headerlinks. Plus
  Regressionstests in `PhotoGridPage.test.tsx`/`PhotoComparePage.test.tsx`/
  `ProjectDetailPage.test.tsx` (Abwesenheit der entfernten Links; Unverändertheit der
  `PhotoDetailPage`-Links wird nicht neu getestet, nur nicht angefasst).
- **E2E:** keine (Testkonzept schließt Playwright grundsätzlich aus) — manueller Smoke-Test für AK1
  (echtes Sticky-Scrollverhalten, Light/Dark) und die reale Touch-Ziel-Größe.
- **Edge Cases (als explizite Testfälle):**
  1. `/projects/new` matcht keine der vier Projekt-Routen → kein Header-Link (explizite Enumeration
     statt Wildcard).
  2. Nicht-numerische `projectId` (z.B. `/projects/abc/photos`) → Route-Param ist unconstrained,
     matcht trotzdem → Link zeigt auf `/projects/abc` (keine Client-Validierung, konsistent mit AK4).
  3. Unbekannter Pfad (`*`-Catch-all, liegt außerhalb der `AppShell`-Verschachtelung) → sofortiges
     `<Navigate to="/" replace>`, `AppShell` wird nie mit veraltetem Projektkontext gemountet.
  4. Query-Parameter (`?filter=...`) beeinflussen den Match/Ziel-Link nicht.
  5. Verschachtelte `:photoId`-Route (`/projects/1/photos/42`) → Link zeigt auf `/projects/1`.
  6. Self-Link auf der Projekt-Detailseite (AK8).
- **Testkonzept:** `specs/architecture/0002-testkonzept.md` wird beim Review des umgesetzten
  Branches (nicht schon jetzt beim Schärfen) um einen Unterabschnitt "Routenabhängiges Rendering in
  einer geteilten Layout-Komponente" ergänzt (`test-engineer`-Zuständigkeit).

## Entscheidungen (2026-08-09, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Linkziel immer die Projekt-Detailseite, nicht kontextabhängig eine Ebene zurück:**
  Stakeholder-Entscheidung — der Link führt von jeder Seite mit Projektkontext direkt zu
  `/projects/{projectId}`, unabhängig davon wie tief man in der Seitenhierarchie ist.
- **Bestehender Header wird erweitert statt eines separaten neuen Elements:** Sticky-Verhalten und
  Projekt-Link werden in die bereits vorhandene `AppShell` integriert statt eine zweite,
  unabhängige Leiste einzuführen.
- **Auslöser:** konkretes Alltagsproblem, kein rein hypothetischer Wunsch — der bisherige
  Zurück-Link am Seitenende war nach Scrollen durch viele Fotos schwer erreichbar.
- **Konsolidierung nur für echte Duplikate (Devil's-Advocate-Ergebnis, per Rückfrage bestätigt):**
  Die Recherche ergab, dass nicht alle bestehenden "Zurück zu..."-Links Duplikate des neuen
  Header-Links sind — `PhotoDetailPage.tsx`s "Zurück zum Grid" bewahrt den aktiven Filter
  (`filterQuery`) und führt zu einem anderen Ziel als die Projekt-Detailseite, "Zur
  Vergleichsansicht" ist gar kein Zurück-Link. Der Stakeholder hat entschieden, nur echte 1:1-
  Duplikate zu entfernen (AK7) statt konsequent alles auf den einen Header-Link zu vereinheitlichen,
  um diesen Zusatznutzen nicht zu verlieren.
- **Routing-Mechanismus (`matchPath` statt neuer Context):** technische Detailentscheidung des
  `architect`, keine Rückfrage nötig — `AppShell` liegt bereits in derselben Datei wie die
  Routen-Definitionen, ein neuer React-Context wäre unnötiger Overhead.
- **`security-engineer` nicht konsultiert (Schritt 8):** strukturelle Begründung — die Idee berührt
  weder Auth, externe Schnittstellen, Secrets, neue Eingaben von außen, Berechtigungen, das
  Datenmodell noch die Sichtbarkeit von Daten zwischen den beiden Nutzern. Der Link verlinkt
  lediglich erneut auf eine `projectId`, die im aktuellen Routen-Kontext bereits sichtbar/aktiv ist.
- **Priorität — Mittel:** vom `requirements-engineer` in der Roadmap-Einordnung vergeben und nach
  Abschluss der Schärfung bestätigt. Begründung: echte UX-Verbesserung für ein bestehend produktiv
  genutztes Feature (Navigation im Projekt), ausgelöst durch ein konkretes Alltagsproblem —
  schwächer als "Hoch"-Items mit aktivem Bug/Verwirrung an bereits produktivem Kernverhalten (z.B.
  Spec 0030), aber stärker als "Niedrig" (rein optionale Features/Tooling). Kein Konflikt mit
  bereits Geplantem, "Mittel" war nach Spec 0032 (Implemented) unbesetzt.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

Entfernen/Ändern von `PhotoDetailPage.tsx`s "Zurück zum Grid"- oder "Zur Vergleichsansicht"-Links;
generische Breadcrumb-Navigation über mehrere Ebenen; Umbau der Header-Navigation auf ein
kontextabhängiges "eine Ebene zurück"-Verhalten; neue Abhängigkeit (z.B. Icon-Bibliothek) für das
Chevron-Symbol, falls sich das im Umsetzungsschritt als nötig herausstellt — dann Rückfrage an
`architect` statt stillschweigender Einführung.
