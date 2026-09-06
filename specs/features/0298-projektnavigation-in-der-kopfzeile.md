# 0298 - Projektnavigation in der Kopfzeile

**Status:** Accepted
**Erstellt:** 2026-09-06
**Bezug:** GitHub-Issue [`#298`](https://github.com/TheRealKoller/photosort/issues/298), Vorgänger-Spec [`0033`](./0033-sticky-titelleiste-projekt-link.md) (teilweise abgelöst, dort als Nachtrag vermerkt), Design-System [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) und Board-Referenz [`architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md), Testkonzept [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), [`docs/architecture.md`](../../docs/architecture.md)

## Ziel

Die Navigationsziele eines Projekts — Pipeline, Fotos, Vergleich, Einstellungen — sind heute nur am Ende der Pipeline-Seite erreichbar. Wer im Fotoraster, in der Foto-Detailansicht oder in der Vergleichsansicht steht, kommt gar nicht direkt dorthin: erst zurück zum Projekt, dann ans Seitenende scrollen. Beim Durchsehen und Bewerten großer Fotomengen — der Kernbeschäftigung in PhotoSort, häufig am Handy — ist das ein täglich mehrfach wiederholter Umweg.

Ziel ist eine einheitliche Navigationsleiste in der ohnehin dauerhaft sichtbaren Kopfzeile, sodass jedes Projektziel von jeder Projektseite aus mit einem Klick und ohne Scrollen erreichbar ist.

## User Story

Als Nutzer, der beim Sichten und Bewerten durch lange Fotolisten scrollt, möchte ich die Navigationsziele meines Projekts jederzeit oben auf der Seite sehen und erreichen, damit ich nicht erst zum Seitenende scrollen oder über Umwege zurücknavigieren muss.

## Akzeptanzkriterien

Fachlich deckungsgleich mit dem Issue-Body von [`#298`](https://github.com/TheRealKoller/photosort/issues/298); durch `test-engineer` auf Testbarkeit geschärft. Gebündelte Kriterien sind geteilt (AK3, AK8, AK9, AK11), AK5/AK6 nennen jetzt die tatsächliche Breitengrenze, AK7 hat ein Abnahmemaß statt „nicht nennenswert", AK14 hält den Bestandsschutz aus dem Issue-Abschnitt „Bewusst nicht Teil dieser Story" als prüfbares Kriterium fest.

**Zuordnungstabelle (Grundlage von AK1/AK8, im Text nicht wiederholt):**

| Ziel | Beschriftung | Sprungziel | markiert aktiv auf |
|---|---|---|---|
| `pipeline` | Projekt | `/projects/{id}/pipeline` | `/projects/{id}`, `/projects/{id}/pipeline`, `/projects/{id}/pipeline/{step}` |
| `photos` | Fotos | `/projects/{id}/photos` | `/projects/{id}/photos`, `/projects/{id}/photos/{photoId}` |
| `compare` | Vergleich | `/projects/{id}/compare` | `/projects/{id}/compare` |
| `settings` | Einstellungen | `/projects/{id}/settings` | `/projects/{id}/settings` |

- [ ] **AK1** Die Kopfzeile enthält auf jeder Seite mit Projektbezug **genau eine** Navigationsgruppe mit **genau vier** Zielen, in der Reihenfolge der Zuordnungstabelle. Jedes Ziel ist ein echtes `<a>`-Element mit dem dort genannten `href`; die vier Ziele sind untereinander gleichrangig (kein Ziel ist Elternelement, Auslöser oder Sonderfall eines anderen).
- [ ] **AK2** Die Gruppe erscheint auf allen neun Routen mit Projektbezug: `/projects/{id}`, `/pipeline`, `/pipeline/{step}`, `/photos`, `/photos/{photoId}`, `/compare`, `/settings`, `/stats`, `/curate`. Auf `/curate` ist das neu — dort gab es bisher keinen Projektbezug in der Kopfzeile.
- [ ] **AK3a** Der bisherige eigenständige Kopfzeilen-Eintrag „‹ Projekt" (Ziel `/projects/{id}`) existiert nicht mehr; der zugängliche Name „Projekt" kommt in der Kopfzeile genau einmal vor, nämlich als Ziel der Gruppe mit dem Sprungziel `/projects/{id}/pipeline`.
- [ ] **AK3b** Die Gruppe ist **ein** Orientierungspunkt: genau ein `navigation`-Landmark mit dem zugänglichen Namen „Projektbereiche", zu jedem Zeitpunkt und in jeder Darstellung.
- [ ] **AK3c** Die Gruppe liest sich visuell als eine zusammengehörige Leiste (gestalterisches Urteil, nicht automatisiert prüfbar — siehe Teststrategie).
- [ ] **AK4** Auf `/`, `/projects/new`, `/login` und auf jedem unbekannten Pfad (Catch-all-Weiterleitung) erscheint **kein** Element der Gruppe: weder eines der vier Ziele, noch der Menü-Auslöser, noch das Landmark aus AK3b.
- [ ] **AK5** Ab einer Fensterbreite von 1024 px sind alle vier Ziele **gleichzeitig sichtbar** und einzeln anklickbar; der Menü-Auslöser aus AK6 ist dort nicht sichtbar.
- [ ] **AK6** Unterhalb von 1024 px ist stattdessen **ausschließlich** ein Menü-Auslöser sichtbar, dauerhaft und ohne Scrollen. Er öffnet auf Klick/Tippen ein Panel, das dieselben vier Ziele in derselben Reihenfolge anbietet. Die Auswahl eines Ziels navigiert dorthin **und** schließt das Panel; nach der Navigation ist kein geöffnetes Panel mehr vorhanden.
- [ ] **AK7** Bei 360 px ist die Kopfzeile auf einer Projektseite **genauso hoch** wie auf einer Seite ohne Projektbezug (Toleranz 1 px) — die Gruppe erzeugt also keine zusätzliche Kopfzeilenzeile und verschiebt den Seiteninhalt nicht nach unten.
- [ ] **AK8a** Auf jeder Route der Zuordnungstabelle trägt in jeder Darstellung **genau ein** Ziel `aria-current="page"`, und zwar das dort genannte.
- [ ] **AK8b** Auf `/projects/{id}/stats` und `/projects/{id}/curate` trägt **kein** Ziel `aria-current="page"` — die Gruppe erscheint dort vollständig, aber unmarkiert.
- [ ] **AK8c** Die Markierung ist nicht allein farblich: sie trägt zusätzlich Rahmen und fetten Schnitt, zeichengleich zum Schrittmarker in `components/Stepper.tsx`.
- [ ] **AK9a** Die Schaltflächen „Fotos ansehen", „Bewertungen vergleichen" und „Einstellungen" am Ende der Pipeline-Seite entfallen ersatzlos.
- [ ] **AK9b** Die Schaltfläche „Statistik" **bleibt** unverändert erhalten und zeigt weiterhin auf `/projects/{id}/stats` — sie ist kein Ziel der neuen Gruppe.
- [ ] **AK9c** Der umschließende `navigation`-Landmark mit dem Namen „Fotos" entfällt mit; das verbleibende „Statistik" steht ohne Landmark.
- [ ] **AK10** Die Schaltfläche „Zurück zum Projekt" am Ende der Kategorie-Kuratierung entfällt ersatzlos; an der Seite ändert sich sonst nichts.
- [ ] **AK11a** **Tastatur:** jedes der vier Ziele ist ein natives `<a href>` und damit ohne zusätzliche Verdrahtung per Tabulator erreichbar und per Eingabetaste auslösbar. Der Menü-Auslöser ist ein natives `<button>`, öffnet per Eingabe-/Leertaste, und die Escape-Taste schließt das Panel und gibt den Fokus an den Auslöser zurück.
- [ ] **AK11b** **Bezeichnung:** der zugängliche Name jedes Ziels ist genau seine Beschriftung aus der Zuordnungstabelle. Der Menü-Auslöser trägt, obwohl nur ein Symbol sichtbar ist, den zugänglichen Namen „Projektbereiche"; das Symbol selbst ist `aria-hidden`.
- [ ] **AK11c** **Trefferfläche:** bei 360 px liefert ein Treffertest an den vier Ecken des 44 × 44 px großen Bereichs um den Menü-Auslöser den Auslöser selbst oder einen seiner Nachfahren. Jede Zeile des geöffneten Panels ist mindestens 44 px hoch.
- [ ] **AK12** Das geöffnete Panel liegt vollständig im Sichtbereich und **über** dem Seiteninhalt: an seinen Prüfpunkten ist das Panel selbst (oder ein Nachfahre) das getroffene Element, obwohl es nachweislich ein Element des Seiteninhalts überdeckt.
- [ ] **AK13** Die Leiste führt keine Farbe, keinen Radius und keine Abstands-/Größenstufe außerhalb der Skalen des Design-Systems „Dark Utility Register" ein (das im Issue genannte „Organic" ist abgelöst, siehe Entscheidungen). Die gestalterische Gesamtwirkung ist Gegenstand des UI/UX-Reviews.
- [ ] **AK14** **Bestandsschutz:** „Zur Vergleichsansicht" und „Zurück zum Grid" auf der Foto-Detailansicht bleiben unverändert erhalten. Es entstehen keine weiteren Navigationsziele.

## Datenmodell-Bezug

Keiner. Reines Frontend: kein Backend-Anteil, keine neue oder geänderte Entität, keine Migration, kein neuer API-Aufruf. Die Story verschiebt ausschließlich vorhandene Navigationsziele zwischen zwei Stellen derselben Oberfläche. Die Ergänzung in [`docs/architecture.md`](../../docs/architecture.md) betrifft entsprechend nur den Frontend-Aufzählungspunkt (zwei neue Dateien), nicht das Datenmodell.

## Architektur / Umsetzung

**Ansatz:** Reines Frontend. Kein Backend-Anteil, kein Datenmodell, keine Migration, kein neuer API-Aufruf, keine neue Laufzeit-Abhängigkeit. Die vier Ziele wandern aus der Fußzeile der Pipeline-Seite in die bereits sticky Kopfzeile der `AppShell` (`frontend/src/App.tsx`) und lösen dort den bisherigen einzelnen „‹ Projekt"-Link ab (AK3a). Das Routenwissen, das heute als Konstanten in `App.tsx` liegt, zieht in ein eigenes Util-Modul um und wird dort zur einzigen Quelle der Wahrheit für drei Fragen zugleich: welche Routen es gibt, welcher Pfad Projektkontext hat, und welches der vier Navigationsziele gerade aktiv ist.

### Menü auf schmalen Bildschirmen: vorhandenes Popover, kein `@radix-ui/react-dropdown-menu`

Bewusste Entscheidung gegen eine neue Abhängigkeit, primär aus fachlichen und nicht aus Kostengründen: `@radix-ui/react-dropdown-menu` implementiert das ARIA-`menu`-Muster (`role="menu"`/`menuitem`), das für Anwendungsmenüs gedacht ist und Seitennavigation ihre Link-Semantik nimmt — die vier Ziele wären danach für Screenreader keine Links mehr und tauchten in keiner Linkliste auf. Das korrekte Muster für eine eingeklappte Navigation ist ein Auslöser mit `aria-expanded` über einem `<nav>` mit echten `<a>`; genau das ergibt sich aus dem vorhandenen `components/ui/popover.tsx`. Es liefert außerdem ohne Zutun alles, was die AKs verlangen: Portal mit `z-50` (Panel liegt über Kopfzeile und Stepper, beide `z-10` — AK12), kollisionsbewusste Platzierung samt Höhenschranke, Schließen per Escape/Klick außerhalb, Fokus ins Panel und zurück auf den Auslöser (AK11a). Popover bekommt damit seinen dritten Konsumenten (`CriterionDetailsPopover`, `Stepper`, neu `ProjectNav`) statt eines vierten parallelen Overlay-Mechanismus. Keine ADR nötig: keine neue Technologie, kein Datenmodell, keine externe Abhängigkeit.

### Neu: `frontend/src/utils/projectRoutes.ts`

Reines TypeScript ohne React-Import (Vorbild: `utils/pipelineSteps.ts`, das `PIPELINE_STEPS` für `Stepper` hält). Es liegt bewusst NICHT in `App.tsx`, sonst importierte `ProjectNav` aus der Datei, die `ProjectNav` rendert.

- `PROJECT_ROUTE_PATHS` — die neun Pfadmuster mit Projektkontext als benanntes `as const`-Objekt: `detail`, `photos`, `photoDetail`, `compare`, `settings`, `stats`, `pipelineBase`, `pipelineStep`, **`curate`** (neu aufgenommen, siehe unten).
- `PROJECT_CONTEXT_ROUTE_PATHS` — alle Werte daraus; ersetzt die bisherige, über zwei Stellen in `App.tsx` verteilte Aufzählung. Explizite Aufzählung statt Wildcard bleibt zwingend: ein `"/projects/:projectId/*"` würde `/projects/new` als Projektkontext mit `projectId="new"` lesen.
- `RESERVED_PROJECT_ID_SEGMENTS` (`new`) — unverändert aus `App.tsx` übernommen, samt des dortigen Warnkommentars, dass eine künftige literale Geschwister-Route unter `/projects/` hier von Hand nachzutragen ist.
- `matchProjectId(pathname): string | null` — reine Funktion (kein Hook), prüft `matchPath` gegen `PROJECT_CONTEXT_ROUTE_PATHS` und filtert die reservierten Segmente. Die bisherige `useProjectIdFromRoute()` in `App.tsx` schrumpft zum Einzeiler `matchProjectId(useLocation().pathname)`.
- `PROJECT_NAV_TARGETS` — die Tabelle der vier Ziele, je Eintrag: `id` (`'pipeline' | 'photos' | 'compare' | 'settings'`), `label`, `buildPath(projectId)` und `activeRoutePaths`. Die Reihenfolge im Array ist die Reihenfolge in der Leiste UND im Menü.
- `resolveActiveNavTargetId(pathname): ProjectNavTargetId | null` — reine Funktion, ermittelt das aktive Ziel über `activeRoutePaths`; gibt `null` zurück, sobald kein Projektkontext vorliegt.

Ziele und Zuordnung: siehe die Zuordnungstabelle unter Akzeptanzkriterien.

- Die Projektübersicht zeigt direkt auf `/pipeline` statt auf `/projects/{id}`: letzteres ist laut eigenem Kommentar ein reiner Bestandsschutz-Redirect für alte Lesezeichen, kein Ziel. Der Redirect-Zustand selbst zählt trotzdem als „Projektübersicht aktiv", damit der Marker während des kurzen Zwischenzustands nicht flackert.
- `/projects/{id}/stats` und `/projects/{id}/curate` zeigen die Gruppe, markieren aber **kein** Ziel als aktiv (`null`). Ein Link als aktiv zu markieren, der woanders hinführt, wäre schlechter als gar kein Marker. Die Statistikseite ist in den ursprünglichen Akzeptanzkriterien nicht aufgeführt, ist aber eine Projektseite und trägt heute schon den Kopfzeilen-Link — sie hier auszunehmen wäre eine Regression, kein erfülltes Kriterium (siehe Entscheidungen).
- **`curate` neu im Projektkontext (AK2):** kehrt die ausdrückliche Gegenfestlegung aus Spec [`0033`](./0033-sticky-titelleiste-projekt-link.md) um. Spec 0033 ist deshalb **nicht** auf `Superseded` gesetzt (nur ein Teil von ihr wird abgelöst, AK1/AK3/AK5–AK7 gelten unverändert weiter — gleiches Vorgehen wie Spec 0045 gegenüber Spec 0038); sie trägt stattdessen einen datierten Nachtrag, der Abgelöstes und Gültiges einzeln benennt. Dieser Nachtrag ist bereits geschrieben und Teil desselben PR.

### Neu: `frontend/src/components/ProjectNav.tsx`

Eine Komponente, eine Prop (`projectId: string`), zwei Darstellungen aus **einer** Zieltabelle:

- **Ein `<nav aria-label="Projektbereiche">` umschließt beide Zweige** — die Leiste (ein inneres `<div class="hidden lg:flex">` mit den vier `<Link>`) *und* den Menü-Auslöser (`lg:hidden`). Nicht der Leisten-Container selbst trägt das Label: läge es dort, gäbe es unterhalb `lg:` **gar keinen** Landmark, weil `display: none` das Element aus dem Accessibility-Tree nimmt — AK3b fordert ihn aber ausdrücklich „in jeder Darstellung". Korrigiert gegenüber der ursprünglichen Fassung dieses Abschnitts, siehe Entscheidungen.
- **Ab `lg:`** sind die vier `<Link>` der Leiste dargestellt. Der Breakpoint ist bewusst `lg:` und nicht `sm:`/`md:`: gemessen an den Board-Maßen (12px Semi-Bold, 12px Polsterung) brauchen Wortmarke + vier Beschriftungen + „Angemeldet als …" + „Abmelden" rund 800px, die Kopfzeile würde bei 768px in eine zweite Zeile umbrechen. Verbindliche Regel für die Umsetzung: **die Kopfzeile darf bei keiner Breite in eine zweite Zeile umbrechen** — bei 360/768/1024/1280 px sichtprüfen (Skill `browse-app`); passt es nachweislich schon bei `md:`, darf der Breakpoint dorthin wandern.
- **Unterhalb `lg:`** ein `PopoverTrigger` als `Button variant="ghost" size="icon"` mit festem `aria-label="Projektbereiche"` und dem Symbol `chevron-down` aus `ui/icon.tsx`. `aria-expanded`/`aria-haspopup` setzt Radix selbst. **Kein Import aus `lucide-react`** — das ist statisch verboten und nur in `ui/icon.tsx` erlaubt; der Zwölfer-Satz enthält kein `menu`-Symbol, und ihn zu erweitern wäre eine Design-System-Entscheidung, keine Umsetzungsentscheidung. Das Panel (`PopoverContent align="start"`, Breite/Polsterung per `className` auf `w-56 p-2` überschrieben — siehe Entscheidungen) enthält dieselben vier Ziele als zeilenweise Liste.
- Beide Darstellungen rendern über **denselben** internen Baustein (`ProjectNavLink` mit einer Prop `layout: 'bar' | 'row'`) — die Zieltabelle wird genau einmal gemappt, Beschriftung, Ziel und Aktiv-Ableitung existieren nur einmal.
- **Aktives Ziel** trägt `aria-current="page"` und ist zusätzlich nicht-farblich ausgezeichnet (fetter Schnitt + Akzentrand + Akzentschrift, wie der Aktiv-Zustand des Board-Navigationselements in `components/Stepper.tsx`). Nie über Farbe allein.
- **Kein `Button`-Wrapper für die Ziele**, sondern schlichte `<Link>` mit einem lokalen Klassenrezept — aus demselben Grund, aus dem `Stepper` es so hält: die drei Board-Zustände des Navigationselements (ruhend/überfahren/aktiv) sind keine `Button`-Ausprägung, und der Aktiv-Zustand braucht Rand, Schnitt und Farbe gemeinsam. Das Rezept bleibt **dateilokal** und wird nicht mit `Stepper` geteilt (etablierte „erst ab dem dritten Konsumenten auslagern"-Praxis).
- **Schließen nach Auswahl:** `open` wird kontrolliert gehalten; der `onClick` jedes Panel-Links setzt `open = false`. Radix schließt bei Navigation nicht von selbst, ein offen zurückbleibendes Panel über der neuen Seite wäre ein echter Fehler (AK6).

Verbindliche Vorgaben aus dem Design-Vertrag (statisch geprüft in `src/designSystem.contract.test.ts`, deshalb hier explizit):

- Mindestens **12px** (`gap-3`) zwischen den vier Zielen der Leiste — aufgespannte Trefferflächen dürfen sich nicht überlappen. Der bestehende `gap-2` zwischen Wortmarke und Gruppe bleibt unverändert (eigene, kommentierte Altentscheidung, nicht Teil dieser Story).
- Die Leisten-Einträge spannen per `tap-target` auf; die **Panel-Zeilen nicht** — dort ist die Zeile selbst die Trefferfläche und bekommt `min-h-11` (Regel „zeilenweise Listen werden nicht aufgespannt", Vorbild `ProjectListPage`/`CurateCategoriesPage`). Die `min-h-11`-Fundstelle braucht einen eigenen, wörtlichen Eintrag in `TALL_CONTROL_ALLOWLIST`.
- Kein `overflow-hidden` auf demselben Knoten wie `tap-target`.
- Zu jeder `hover:`-Variante gehört eine `active:`-Variante (am Telefon gibt es „überfahren" nicht).
- Keine willkürlichen Werte, Abstände nur auf den acht Stufen des 8-Punkt-Rasters.

**Beschriftungen:** „Projekt", „Fotos", „Vergleich", „Einstellungen" (endgültig, vom `ux-ui-designer` festgelegt). Technisch verbindlich: der **sichtbare Text ist zugleich der zugängliche Name** (kein zusätzliches `aria-label` an den vier Zielen), und jede Beschriftung steht genau einmal, nämlich in `PROJECT_NAV_TARGETS`.

### Geänderte Dateien

- `frontend/src/utils/projectRoutes.ts` **(neu)** und `projectRoutes.test.ts` **(neu)**.
- `frontend/src/components/ProjectNav.tsx` **(neu)** und `ProjectNav.test.tsx` **(neu)**.
- `frontend/src/App.tsx` — `PROJECT_ROUTES` behält die Zuordnung Pfad→Element, bezieht die Pfade aber aus `PROJECT_ROUTE_PATHS`; die `<Route>`-Deklarationen für Pipeline und Curate ebenso (Ausnahme: die verschachtelte Schritt-Route bleibt relativ `path=":step"`, ihr absolutes Muster wird nur zum Matchen gebraucht). `useProjectIdFromRoute` wird zum Wrapper um `matchProjectId`. Im Kopfzeilen-Markup ersetzt `{projectId !== null && <ProjectNav projectId={projectId} />}` den bisherigen „‹ Projekt"-Button. Rest der Kopfzeile (Wortmarke, „Angemeldet als …", „Abmelden", Sticky-Verhalten) unverändert.
- `frontend/src/App.test.tsx` — die bestehende Test-Gruppe zum „Projekt"-Link wird auf die Gruppe umgeschrieben, **nicht gelöscht**; der Self-Link-Test aus Spec 0033 AK8 wird zum Marker-Test dieser Spec.
- `frontend/src/pages/pipeline/ProjectPipelineLayout.tsx` — die drei Buttons „Fotos ansehen", „Bewertungen vergleichen", „Einstellungen" entfallen ersatzlos. **„Statistik" bleibt** (AK9b). Der umschließende `<nav aria-label="Fotos">` entfällt mit (AK9c): ein Landmark mit einem einzigen Eintrag und nun falschem Namen ist schlechter als kein Landmark; der Statistik-Button bleibt an derselben Stelle in einem schlichten Container.
- `frontend/src/pages/pipeline/ProjectPipelineLayout.test.tsx` — anpassen.
- `frontend/src/pages/CurateCategoriesPage.tsx` — „Zurück zum Projekt" am Seitenende entfällt ersatzlos.
- `frontend/src/pages/CurateCategoriesPage.test.tsx` — Regressionstest nach dem Vorbild der bestehenden „no longer renders its own …"-Tests in `PhotoGridPage`/`PhotoComparePage`.
- `frontend/src/pages/PhotoDetailPage.test.tsx` — Anwesenheitsprüfung für „Zur Vergleichsansicht"/„Zurück zum Grid" (AK14).
- `frontend/src/designSystem.contract.test.ts` — Eintrag in `TALL_CONTROL_ALLOWLIST` für die `min-h-11`-Panelzeile.
- `e2e/tests/project-nav.spec.ts` **(neu)**; `e2e/tests/tap-targets.spec.ts` und `e2e/tests/popover-position.spec.ts` — Lokalisierer auf `main` eingrenzen (siehe Teststrategie).
- `docs/architecture.md`, `specs/features/0033-sticky-titelleiste-projekt-link.md`, `specs/architecture/0004-design-system.md`, `specs/architecture/0002-testkonzept.md` — bereits im Rahmen dieser Spec ergänzt.

### Reihenfolge der Umsetzung

1. `utils/projectRoutes.ts` mit Tests — reine Funktionen, ohne React sauber rot/grün zu fahren. Enthält bereits `curate` und damit die AK2-Verhaltensänderung.
2. `App.tsx` auf das neue Modul umverdrahten, **ohne** die Kopfzeile zu ändern. Die bestehende `App.test.tsx` muss dabei bis auf einen Punkt grün bleiben: der Kopfzeilen-Link erscheint jetzt zusätzlich auf `/projects/:id/curate`. Reine Umverdrahtung von Verhalten trennen.
3. `ProjectNav.tsx` mit Tests, isoliert gerendert.
4. Einbau in die `AppShell`, Umbau der Kopfzeilen-Tests in `App.test.tsx` (AK1–AK4, AK8).
5. `ProjectPipelineLayout.tsx` entschlacken, danach `CurateCategoriesPage.tsx` — beides erst jetzt, damit zu keinem Zeitpunkt ein Ziel unerreichbar ist.
6. E2E: `project-nav.spec.ts` anlegen, die beiden dokumentweiten Lokalisierer eingrenzen.
7. Sichtprüfung bei 360/768/1024/1280 px (Skill `browse-app`): kein Zeilenumbruch der Kopfzeile, kein waagerechtes Scrollen, Panel liegt über dem Inhalt, Fokusreihenfolge.

## UI/UX

Die Projekt-Navigationsgruppe ist ein wiederkehrendes, responsives Navigationsmuster für alle Projektseiten (Pipeline, Fotoraster, Foto-Detail, Vergleich, Einstellungen, Statistik, Kategorie-Kuratierung) und ersetzt die bisherigen Navigationsziele — den einzelnen „Projekt"-Link (Spec 0033) und die drei Sekundär-Buttons am Ende der Pipeline-Seite.

**Darstellung ab `lg:` (≥ 1024px):** Vier gleichrangige Navigationsziele als `<Link>`-Elemente, gestaltet nach dem Board-Navigationselement — **dasselbe Klassenrezept wie der Schrittmarker in `Stepper.tsx` (~Zeilen 190–207)**, nicht neu hergeleitet:

- Radius 8px, Polsterung 12/8px.
- Ruhend: `border-border-control bg-surface text-text`. Ausdrücklich `--border-control`, **nicht** `--border` — Board-Abweichung 2; ein Bedienelement mit dem rein dekorativen `--border` wäre auf dunklem Grund unsichtbar, und der Design-Vertrag erzwingt das statisch.
- Überfahren: `hover:bg-overlay hover:text-text-h`, zwingend begleitet von `active:bg-border active:text-text` (am Telefon ist „gedrückt" der einzige Zustand, den es gibt).
- Aktiv: `border-accent bg-overlay font-bold text-accent` — die Schrift trägt **`--accent`**, nicht `--text-h`.

Aktives Ziel trägt zusätzlich `aria-current="page"`; die Auszeichnung läuft nie über Farbe allein, sondern über Rand, Schnitt und Farbe gemeinsam. Mindestens `gap-3` (12px) zwischen den Elementen; Trefferfläche über `tap-target` aufgespannt. Layout: `hidden lg:flex` in der bestehenden Kopfzeilenreihe.

**Bewusst ohne Glyphe**, anders als das Board-Navigationselement der Sidebar: der Zwölfer-Symbolsatz enthält passende Glyphen nur für zwei der vier Ziele (`image`, `cog`). Zwei Ziele mit Symbol neben zwei ohne würde die Gruppe zerreißen, statt sie als eine Leiste wirken zu lassen (AK3c). Den Satz dafür zu erweitern wäre eine eigene Design-System-Entscheidung und ist hier nicht getroffen.

**Darstellung unterhalb `lg:` (< 1024px):** Ein `PopoverTrigger`-Button (`variant="ghost" size="icon"`, `chevron-down`-Symbol, `aria-label="Projektbereiche"`, `lg:hidden`) öffnet ein `PopoverContent` (`align="start"`) mit den vier Zielen als zeilenweise Liste. Das geöffnete Panel liegt über dem Seiteninhalt (AK12). Panel-Zeilen werden **nicht** aufgespannt — die Zeile selbst ist die Trefferfläche und trägt `min-h-11` (AK11c). Aktives Ziel trägt `aria-current="page"` mit derselben visuellen Auszeichnung. Das Panel schließt nach Auswahl (kontrolliertes `open`, `onClick` setzt `open = false`).

**Betroffene Zustände:**

- Mit Projektkontext: Gruppe sichtbar, vier Ziele erreichbar.
- Ohne Projektkontext (Projektliste, Projekt anlegen, Anmeldung, unbekannter Pfad): Gruppe erscheint nicht (AK4).
- `/projects/:id/stats` und `/projects/:id/curate`: Gruppe vollständig sichtbar, **kein** Ziel als aktiv gekennzeichnet — beides sind Querschnittsansichten, kein Ziel der Gruppe.
- Kein Lade-, Leer- oder Fehlerzustand: die Gruppe hängt ausschließlich am `pathname`, nicht an einem API-Aufruf. Sie erscheint deshalb auch, während die darunterliegende Seite noch lädt oder fehlgeschlagen ist — genau dann ist ein Weg heraus am wertvollsten.

**Bezug zum Design-System:** Anwendung des bestehenden Musters „Board-Navigationselement" ([`architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md), Abschnitt 6) auf einen neuen Kontext (horizontal in der Kopfzeile statt vertikal in der Sidebar). Keine neuen Farbwerte, Radien, Abstände oder Zustände. Die Lücke „Kopfzeilen-Navigation" in [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) ist damit geschlossen und durch das dort neu aufgenommene Muster „Projekt-Navigationsgruppe in der Kopfzeile" ersetzt.

## Teststrategie

**Unit (`utils/projectRoutes.test.ts`, ohne Router/QueryClient).** Das Modul ist rein — die Fallunterscheidungen werden hier geprüft, nicht auf Rendering-Ebene: `matchProjectId` über alle neun Muster mit eingesetzten Parametern, plus die Abweisungsfälle `/`, `/projects/new`, `/login`, unbekannter Pfad; `resolveActiveNavTargetId` über alle neun Muster (inkl. der beiden Fälle mit Ergebnis `null`); `PROJECT_NAV_TARGETS` mit exakter Kardinalität (4) und fixierter Reihenfolge — die Anzeigereihenfolge ist die Array-Reihenfolge und hätte sonst keinen Wächter; `buildPath` je Ziel. Die Sonderfälle Query-Parameter, nicht-numerische `projectId` und verschachtelte `:photoId`-Route wandern aus `App.test.tsx` hierher, wo sie hingehören.

**Komponente (`ProjectNav.test.tsx`, echter `MemoryRouter`, keine API-Mocks nötig).** Beide Darstellungen kommen aus einer Tabelle: geprüft wird, dass die Leiste die vier Ziele mit den richtigen `href` rendert (AK1), dass ein Klick auf den Auslöser ein `dialog`-Panel öffnet, das per `within(panel)` dieselben vier Ziele in derselben Reihenfolge trägt (AK6), dass die Auswahl das Panel schließt (AK6), dass Escape schließt und den Fokus zurückgibt (AK11a), und dass der Auslöser den zugänglichen Namen „Projektbereiche" trägt (AK11b). Die Markierung (AK8a/8b) wird je Darstellung eingegrenzt geprüft, nie dokumentweit — siehe „Fallstricke".

**Integration (`App.test.tsx`, echter Router, gemockte `api/*`).** Nur, was die Verdrahtung von Kopfzeile und Routing betrifft: Gruppe auf allen neun Projektrouten vorhanden (AK2) und auf den vier Nicht-Projektrouten vollständig abwesend (AK4); die neun Muster sind zugleich der Synchronitäts-Wächter (jedes Muster muss real geroutet sein statt auf dem Catch-all zu landen); `aria-current` je Route gemäß Zuordnungstabelle (AK8a) und auf `/stats`/`/curate` nirgends (AK8b); genau ein `navigation`-Landmark „Projektbereiche" auch bei geöffnetem Panel (AK3b); der Name „Projekt" genau einmal in der Kopfzeile (AK3a).

**Regression durch Abwesenheit (AK9/AK10/AK14).** Nach dem etablierten Muster aus Spec 0033: `ProjectPipelineLayout.test.tsx` prüft die Abwesenheit der drei Schaltflächen und des Landmarks „Fotos", **und im selben Test die fortbestehende Anwesenheit von „Statistik"** — eine reine Abwesenheitsprüfung bestünde auch, wenn versehentlich alle vier entfernt würden. `CurateCategoriesPage.test.tsx` bekommt eine Abwesenheitsprüfung für „Zurück zum Projekt" (bislang gibt es dort gar keine Prüfung des Links, der Rot-Schritt ist also der neu geschriebene Test vor dem Entfernen). `PhotoDetailPage.test.tsx` bekommt eine Anwesenheitsprüfung für „Zur Vergleichsansicht"/„Zurück zum Grid" (AK14).

**E2E (`e2e/tests/project-nav.spec.ts`, neu).** Ausschließlich das, was jsdom prinzipiell nicht kann: der Breakpoint-Wechsel an der **exakten** Grenze (1024 px → genau vier sichtbare Ziele, kein Auslöser; 1023 px → genau umgekehrt; beide Messungen müssen sich unterscheiden) für AK5/AK6; die Kopfzeilenhöhe gegen dieselbe Kopfzeile ohne Projektbezug, und zwar bei **zwei** Breiten mit derselben Messtechnik: bei 360 px für AK7, und bei 1024 px für die verbindliche Regel „die Kopfzeile darf bei keiner Breite in eine zweite Zeile umbrechen" — 1024 px ist die schmalste Breite, bei der Wortmarke, vier Beschriftungen, „Angemeldet als …" und „Abmelden" gleichzeitig in eine Zeile müssen, und das `<header>` trägt `flex-wrap`, ein Umbruch liefe dort also still statt sichtbar über. Ohne diese zweite Messung ruhte die Regel allein auf der Schätzung „rund 800 px" aus dem Architektur-Abschnitt. Beide Messungen setzen voraus, dass bei der jeweiligen Breite auch die erwartete Darstellung zu sehen ist, sonst wäre der Höhenvergleich bei 1024 px leer. Dazu Sichtbereichs-Enthaltung und Überlagerung des geöffneten Panels für AK12. **Lokalisierer-Fallstrick dieser Ebene:** `page.getByRole()` matcht standardmäßig nur nicht-verborgene Elemente (Option `includeHidden`), sieht also den Accessibility-Tree und nicht das DOM — für die DOM-Kardinalität eines per `display: none` ausgeblendeten Zweigs ist zwingend ein `locator('a')`/Attribut-Lokalisierer nötig, sonst läuft die Zusicherung unterhalb `lg:` in ihre Zeitgrenze. Eigene Viewport-Breiten, an ein Playwright-Projekt gebunden (wie `grid-columns`). Rot-Nachweis bei Einführung im PR belegen. Erweitert statt neu: `tap-targets` nimmt den Menü-Auslöser und eine Panel-Zeile auf (AK11c).

**Statisch (`designSystem.contract.test.ts`).** AK13 fällt ohne neuen Testfall unter die bestehenden Scans über alle Produktivdateien. Zwei Eingriffe sind trotzdem nötig: ein fundstellengenauer Eintrag in `TALL_CONTROL_ALLOWLIST` für die `min-h-11`-Panelzeile (Kategorie „Zeilenhöhe einer zeilenweisen Liste"), und — falls die Zeichengleichheit des Klassenrezepts mit `Stepper.tsx` gehalten werden soll (AK8c) — eine Bindung der beiden Literale aneinander, mit positiver Gegenprobe. Zulässige Alternative: ein geteilter Konstanten-Export, dann entfällt die Regel.

**Nicht automatisiert prüfbar, und wodurch stattdessen abgesichert.** AK3c („wirkt als eine zusammengehörige Leiste") und die gestalterische Hälfte von AK13 sind gestalterische Urteile: `review-ux` plus Abnahme durch Daniel. Zwischenbreiten zwischen 360 px und 1024 px (768/900): Sichtprüfung im Umsetzungslauf, keine volle Breitenleiter. Dass umgekehrt jede künftig unter `/projects/` registrierte Route auch in `PROJECT_CONTEXT_ROUTE_PATHS` steht, ist zur Laufzeit nicht aufzählbar und bleibt Review-Pflicht — genau diese Richtung ist historisch zweimal gebrochen (Spec 0042/PR #101, Spec 0207). Alle drei stehen als benannte Lücken im Testkonzept.

**Fallstricke, die den Rot-Schritt sonst zum Rätsel machen** (ausführlich im Testkonzept, Sektion „Eine Zieltabelle, zwei Darstellungen"): In jsdom greifen Tailwind-Klassen nicht, beide Darstellungen liegen gleichzeitig im DOM — `toBeVisible()` ist als Beleg für den Breakpoint wertlos, Panel-Prüfungen grenzen mit `within(panel)` ein, `aria-current` liegt bei geöffnetem Panel doppelt vor und wird pro Darstellung geprüft. Zwei bestehende E2E-Specs greifen mit `page.locator('button[aria-haspopup="dialog"]')` dokumentweit und müssen auf `main` eingegrenzt werden, sonst treffen sie ab jetzt den Kopfzeilen-Auslöser — `tap-targets` würde rot, `popover-position` bliebe still grün und prüfte dreimal dasselbe Panel. Der still grüne Fall ist der gefährlichere.

**Edge Cases, die sonst übersehen werden:**

- `/projects/new` darf weiterhin nicht als Projektkontext matchen — als Abweisungsfall im Unit-Test **und** als Rendering-Fall in `App.test.tsx`. Der Umzug von `RESERVED_PROJECT_ID_SEGMENTS` in ein neues Modul ist genau die Gelegenheit, bei der die Zeile still verlorengeht.
- `/projects/{id}` (Redirect-Zwischenzustand) **und** `/projects/{id}/pipeline` (Basiszustand ohne `:step`) müssen beide „Projekt" schon als aktiv zeigen, sonst flackert der Marker. Der zweite Fall ist der, den bei Spec 0042 erst ein Copilot-Review gefunden hat.
- Prozentkodierte `projectId`-Werte bleiben bewusst außen vor: `matchPath` dekodiert, `buildPath` kodiert nicht, ein einseitiges `encodeURIComponent` bräche den Rundlauf. Über die Oberfläche unerreichbar (IDs sind ganzzahlig aus dem Backend), heute in `App.tsx` genauso. Abgesichert wird nur der Rundlauf für einen nicht-numerischen, zeichenharmlosen Wert (`abc`, bestehende Konvention).
- Der Test „Panel schließt nach Auswahl" braucht **beide** Hälften — Panel weg **und** Route gewechselt. Nur „Panel weg" bestünde auch, wenn das `onClick` die Navigation verschluckt.
- Solange das Panel geschlossen ist, hängt Radix seinen Inhalt gar nicht ein (kein `forceMount`); die vier Ziele existieren dann genau einmal. Nur Tests am geöffneten Panel brauchen `within` — eine dokumentweite Kardinalitäts-Assertion `toHaveLength(1)` auf `aria-current` wäre bei geöffnetem Panel falsch.
- `/curate` bekommt zum ersten Mal überhaupt Projektkontext in der Kopfzeile und braucht einen eigenen Testfall, nicht nur einen Tabelleneintrag.
- Die bestehenden „Projekt"-Link-Tests in `App.test.tsx` werden rot (der Name bleibt „Projekt", das `href` wechselt auf `/projects/{id}/pipeline`) — sie sind **anzupassen, nicht zu löschen**.
- Keine neuen jsdom-Globals nötig (verifiziert): `setupTests.ts` stubbt weder `ResizeObserver` noch `hasPointerCapture`, und die bestehenden `CriterionDetailsPopover`-Tests öffnen ihr Panel trotzdem per `userEvent.click()`. Mit `@radix-ui/react-dropdown-menu` wären beide Stubs nötig gewesen — die Bauteilwahl ist auch die testbarere.

## Security

**Nicht relevant** — `security-engineer` nicht konsultiert (siehe Entscheidungen). Die Story berührt weder Auth noch Secrets, externe Schnittstellen, Berechtigungen oder das Datenmodell, führt keine neue Eingabe von außen ein und ändert nichts an der Sichtbarkeit von Daten zwischen den beiden Nutzern. Sie verschiebt ausschließlich vorhandene Links zwischen zwei Stellen derselben, bereits durch `ProtectedRoute` geschützten Oberfläche; alle vier Ziele sind heute schon von jedem angemeldeten Nutzer erreichbar. Die einzige neue Datenverarbeitung ist das Lesen des `pathname` aus dem Router und das Zusammensetzen von Link-Zielen daraus — beides passiert heute in `App.tsx` bereits genauso, in unverändertem Umfang und mit unverändertem Ergebnis.

## Entscheidungen

- **`architect` konsultiert (Schritt 1).** Ansatz festgelegt: neues Util-Modul `utils/projectRoutes.ts` als einzige Quelle der Wahrheit, neue Komponente `ProjectNav.tsx`, Umsetzungsreihenfolge in sieben Schritten. Keine ADR angelegt — es entsteht keine neue Technologie, kein Datenmodell und keine externe Abhängigkeit.
- **Menü über das vorhandene Radix-Popover, nicht über `@radix-ui/react-dropdown-menu`.** Fachlich begründet, nicht über Bundle-Kosten: das ARIA-`menu`-Muster nähme den vier Zielen ihre Link-Semantik. Keine ADR-Pflicht, da die Entscheidung gerade *gegen* eine neue Abhängigkeit fällt.
- **Spec 0033 wird nicht auf `Superseded` gesetzt, sondern trägt einen datierten Nachtrag.** Nur AK2/AK4/AK8 und die ausdrückliche Curate-Ausnahme werden abgelöst; AK1/AK3/AK5–AK7 gelten unverändert weiter. Gleiches Vorgehen wie Spec 0045 gegenüber Spec 0038.
- **`ux-ui-designer` konsultiert (Schritt 2).** Beschriftungen, Auslöser-Bezeichnung, Zustandsrezept und die Pflege von `architecture/0004-design-system.md` festgelegt.
- **Der Zwölfer-Symbolsatz wird nicht erweitert; die vier Ziele tragen reinen Text.** Ein dreizehntes `menu`-Symbol wäre eine Design-System-Entscheidung mit Folgen für Board-Referenz, `icon.tsx` und Vertragstest. Der Auslöser nutzt stattdessen `chevron-down` (Board-Bedeutung „Dropdown"). Weil der Satz nur für zwei der vier Ziele (`image`, `cog`) eine passende Glyphe hat, bekommen die Ziele selbst gar keine — zwei mit und zwei ohne Symbol würde AK3c gerade verfehlen.
- **AK13 nennt im Issue „Organic"; maßgeblich ist „Dark Utility Register".** Organic ist seit Spec 0320 vollständig abgelöst, seine Farben, Radien und Abstände sind überholt. Vom `ux-ui-designer` ausdrücklich als notwendige Korrektur bestätigt, nicht als stille Umdeutung übernommen.
- **`test-engineer` konsultiert (Schritt 3).** Akzeptanzkriterien auf Testbarkeit geschärft (AK3/AK8/AK9/AK11 geteilt, AK5/AK6/AK7 mit Abnahmemaß versehen), Teststrategie und Edge Cases festgelegt, `architecture/0002-testkonzept.md` ergänzt.
- **`security-engineer` nicht konsultiert (Schritt 3):** Die Story hat keinen konkret benennbaren Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, dem Datenmodell oder der Sichtbarkeit von Daten zwischen den beiden Nutzern. Sie verschiebt vorhandene Links innerhalb derselben geschützten Oberfläche, ohne eine einzige neue Eingabe, Route oder Datenquelle einzuführen; jedes der vier Ziele ist heute schon von jedem angemeldeten Nutzer erreichbar.
- **`/projects/{id}/stats` bekommt die Gruppe, obwohl AK2 sie nicht nennt.** Die Statistikseite ist eine Projektseite und trägt heute bereits den Kopfzeilen-„Projekt"-Link. Sie auszunehmen wäre eine Regression gegenüber dem Ist-Zustand, kein erfülltes Kriterium — das ist eine Anforderungsauslegung und hier ausdrücklich festgehalten, damit `review-requirements` sie nicht als Scope Creep liest.
- **Der Statistik-Button am Ende der Pipeline-Seite bleibt.** AK9 nennt ihn nicht unter den entfallenden, und die Kopfzeilengruppe enthält ihn nicht — er wäre sonst unerreichbar.
- **Auf `/stats` und `/curate` ist kein Ziel als aktiv markiert.** Ein Link als aktiv zu markieren, der woanders hinführt, wäre schlechter als gar kein Marker. Sollte Daniel stattdessen „Projekt" markiert sehen wollen, ändert sich nur die Tabellenzeile, nicht die Teststrategie.
- **Der `navigation`-Landmark umschließt Leiste *und* Auslöser, nicht nur die Leiste** (Abweichung vom ursprünglichen Wortlaut dieses Architektur-Abschnitts, in der Umsetzung entschieden und hier nachgezogen statt stillschweigend übernommen). Die ursprüngliche Fassung schrieb „vier einzelne `<Link>` in einem `<nav aria-label="Projektbereiche">` (`hidden lg:flex`)" — das hätte das Label auf den unterhalb `lg:` ausgeblendeten Container gelegt. `display: none` nimmt ein Element aus dem Accessibility-Tree; unterhalb `lg:` hätte es damit **null** Landmarks gegeben, während AK3b „genau ein `navigation`-Landmark … in jeder Darstellung" fordert. Gebaut ist deshalb: `<nav aria-label="Projektbereiche">` außen, darin das `hidden lg:flex`-`<div>` der Leiste und der `lg:hidden`-Auslöser. **Bewusst in Kauf genommen:** der Panel-Inhalt liegt portalbedingt (`PopoverPrimitive.Portal`) außerhalb dieses `<nav>`; unterhalb `lg:` enthält der Landmark also nur den Auslöser, nicht die vier Ziele. Ein zweites, gleichnamiges `<nav>` um die Panelzeilen wäre die naheliegende Gegenmaßnahme und ist ausdrücklich abgewählt — zwei gleichnamige Landmarks nebeneinander sind ein Bedienbarkeitsfehler (Landmark-Liste des Screenreaders) und machten jede Rollen-Query darauf mehrdeutig, siehe Testkonzept-Punkt 3. Die vier Panelzeilen bleiben echte `<a>` und damit in jeder Linkliste; was ihnen fehlt, ist ausschließlich die Landmark-Einordnung.
- **Panelbreite `w-56` statt der Vorgabe-`w-72` des Popover-Primitivs, Polsterung `p-2` statt `p-4`** (Umsetzungsentscheidung innerhalb der bereits vorgesehenen „Breite/Polsterung per `className` überschrieben"-Freiheit). 224px statt 288px lässt dem Panel bei 360px sichtbar Rand, ohne dass die längste Beschriftung („Einstellungen") umbricht; `p-2` statt `p-4` passt zur zeilenweisen Liste, deren Zeilen ihre eigene Polsterung tragen. Beide Werte sind vertragskonform: `w-56` ist eine Größen-, keine Abstands-Utility (die Abstandsskala gilt nur für `gap`/`p`/`m`), `p-2` liegt auf dem 8-Punkt-Raster.
- **Board-Status nicht gesetzt.** Diese Spec entstand in einer Remote-Session, in der jeder Board-Zugriff mit `HTTP 403` endet (Spec [`0318`](./0318-remote-lebenszyklus-grenze.md)). Der Wechsel auf `In Progress` ist lokal nachzuholen.

## Offene Fragen

Keine. Die Story war über `refinement` bereits fachlich geschärft; die vier technischen Konsultationen haben keine Frage offengelassen, die eine Produktentscheidung wäre.

## Out of Scope

- **„Zur Vergleichsansicht" auf der Foto-Detailansicht bleibt erhalten.** Der Link erscheint dort nur im Abschlusszustand („Fertig! Keine weiteren unbewerteten Fotos.") und ist eine Handlungsaufforderung für den nächsten Arbeitsschritt, keine allgemeine Navigation — diese Führung ginge sonst verloren.
- **„Zurück zum Grid" auf der Foto-Detailansicht bleibt erhalten.** Der Link führt zu einem anderen Ziel als die Kopfzeile, weil er den aktiven Filter der Fotoliste bewahrt.
- **Keine neuen Navigationsziele.** Die Story verschiebt und vereinheitlicht ausschließlich bestehende.
- **Kein dreizehntes Symbol im Board-Symbolsatz.** Siehe Entscheidungen.
- **Kein Umbau der übrigen Kopfzeile.** Wortmarke, „Angemeldet als …" und „Abmelden" bleiben unverändert, ebenso das Sticky-Verhalten aus Spec 0033.
