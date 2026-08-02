# 0012 - Visuelles Redesign & UI-Komponentenbibliothek

**Status:** Accepted
**Erstellt:** 2026-08-02
**Akzeptiert:** 2026-08-02
**Bezug:** Idea-Sharpening-Gespräch mit Daniel im Chat, 2026-08-02 ("Die Anwendung soll ein ansprechendes Design bekommen"). Seit der allerersten Anlage von [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) wiederholt vertagte Lücke "kein Styling-System gewählt", zuletzt in jedem UX-Review von Spec 0002/0003/0005/0006 vermerkt.

## Ziel

Die Anwendung soll einen warmen, persönlichen visuellen Stil erhalten — passend zu Familien-Urlaubsfotos statt neutral/business-artig — und dabei von reinem ungestyltem HTML/JSX auf eine echte UI-Komponentenbibliothek (Tailwind CSS + Radix UI + shadcn/ui, siehe ADR [`decisions/0010-ui-component-library.md`](../decisions/0010-ui-component-library.md)) umgestellt werden. Das im Design-System-Dokument bereits inhaltlich definierte, aber nie visuell umgesetzte Vokabular (4 Bewertungsfarben+Symbole, 3 Prozess-Status-Farben, Vorschlags-Badge-Muster, Busy-Button, Skeleton-Ladezustände, Touch-Ziele, WCAG-AA) wird dabei erstmals tatsächlich sichtbar gemacht statt nur strukturell/textuell zu existieren. Zusätzlich werden drei bereits dokumentierte, kleine funktionale Lücken mit behoben, die ohnehin bei der Überarbeitung derselben Komponenten berührt werden.

## User Story

Als Daniel (und seine Frau als Endnutzerin) möchte ich, dass PhotoSort sich warm und persönlich anfühlt statt wie ein ungestyltes Entwickler-Werkzeug, damit die App zum Anlass (Familien-Urlaubsfotos durchsehen) passt und sich beim wiederholten Gebrauch angenehm statt technisch-neutral anfühlt.

## Akzeptanzkriterien

- [ ] Eine Komponentenbibliothek (Tailwind CSS + Radix UI + shadcn/ui, ADR 0010) ist eingeführt und ersetzt das bisherige unstyled HTML/JSX in allen 9 betroffenen Views/Komponenten (`App.tsx`/AppShell, `LoginPage`, `ProjectListPage`, `ProjectCreatePage`, `ProjectDetailPage`, `FolderBrowser`, `PhotoGridPage`, `PhotoDetailPage`, `PhotoComparePage`, `RatingButtons`/`RatingBadge`/`PhotoImage`).
- [ ] Vite-Template-Reste (`index.css` lila Akzentfarbe `#aa3bff`/`#863bff`, `#social`-Regeln, `favicon.svg`) sind entfernt/ersetzt.
- [ ] Terracotta-Akzentfarbe (`#d97757` hell / `#e8916d` dunkel) und warme Neutraltöne (siehe `architecture/0004-design-system.md`) sind als Design-Tokens (CSS-Variablen) umgesetzt.
- [ ] Die 4 Bewertungsfarben (favorite/album_worthy/rejected/unbewertet) sind visuell inkl. Symbol umgesetzt, unverändert gegenüber den bereits definierten Hex-Werten, WCAG-AA-Kontrast (4.5:1) gegen den neuen Hintergrund geprüft.
- [ ] Die 3 Prozess-Status-Farben (running/success/failed) sind visuell umgesetzt.
- [ ] Das Vorschlags-Badge-Muster (volle Füllung = entschieden, Umrandung/gedämpfte Fläche = Vorschlag) ist visuell umgesetzt.
- [ ] Skeleton-Ladezustände (statt reinem Text) sind umgesetzt, wo im Design-System vorgesehen (u.a. Grid).
- [ ] Interaktive Elemente erfüllen ≥44×44px Touch-Ziele tatsächlich messbar (nicht nur strukturelle Absicht).
- [ ] **Funktionaler Fix 1:** `RatingButtons` zeigen während einer laufenden Anfrage konsistent das Busy-Button-Muster (Inline-Indikator/Label-Wechsel, tatsächlich `disabled`) — behebt die bestehende Lücke, dass `disabled`- und `busy`-Prop bisher unabhängig sind.
- [ ] **Funktionaler Fix 2:** `PhotoDetailPage` und `PhotoComparePage` zeigen bei Ladefehler einen "Erneut versuchen"-Button (Klick löst `refetch()` aus), analog zu `PhotoGridPage`.
- [ ] **Funktionaler Fix 3:** `LoginPage`-Felder haben `autocomplete="username"` bzw. `autocomplete="current-password"`.
- [ ] Bestehende Testing-Library-Selektoren (`getByRole`/`getByLabelText`/`aria-*`/`data-suggested`/`data-status`) bleiben nach der Migration gültig — alle bestehenden Frontend-Tests laufen ohne Anpassung der Assertions weiter grün; eine zwangsläufige Rollenänderung (z.B. natives `<button>` → Radix-Trigger mit anderer impliziter Rolle) wird explizit im PR benannt, nicht stillschweigend gefixt.
- [ ] `docker-compose-check`/CI bleibt grün (neue Frontend-Abhängigkeiten ändern nichts an Build/Lint/Typecheck-Konfiguration außer den neuen Tailwind/PostCSS-Configs).

## Datenmodell-Bezug

Keines. Reine Frontend-Änderung, kein Backend-Code betroffen.

## Architektur / Umsetzung

**Komponentenbibliothek:** Tailwind CSS + Radix UI + shadcn/ui, siehe ADR [`decisions/0010-ui-component-library.md`](../decisions/0010-ui-component-library.md). shadcn/ui-Komponenten werden als Quellcode nach `frontend/src/components/ui/` kopiert (kein zusätzliches Laufzeit-Paket "shadcn/ui"); tatsächliche neue `frontend/package.json`-Abhängigkeiten: `tailwindcss`, `postcss`, `autoprefixer`, `@radix-ui/react-*` (nur genutzte Primitives, schrittweise ergänzt), `class-variance-authority`, `clsx`, `tailwind-merge`. Neue Konfigdateien: `tailwind.config.ts`, `postcss.config.js`.

**Betroffene Dateien:** `frontend/src/index.css` (Umstellung auf Tailwind-Direktiven + Design-Token-CSS-Variablen, Entfernen der Vite-Template-Reste), `frontend/public/favicon.svg`, `App.tsx`, `pages/LoginPage.tsx`, `pages/ProjectListPage.tsx`, `pages/ProjectCreatePage.tsx`, `pages/ProjectDetailPage.tsx`, `components/FolderBrowser.tsx`, `pages/PhotoGridPage.tsx`, `pages/PhotoDetailPage.tsx`, `pages/PhotoComparePage.tsx`, `components/RatingButtons.tsx`, `components/RatingBadge.tsx`, `components/PhotoImage.tsx`. Neu: `frontend/src/components/ui/` (Button, Card, Badge, Progress als shadcn/ui-Basiskomponenten).

**Migrationsansatz — Tokens zuerst, dann Komponente für Komponente:**
1. Tailwind/PostCSS-Setup + Design-Tokens als CSS-Variablen (Bewertungsfarben, Prozess-Status-Farben, Spacing-Skala 4/8/12/16/24/32px — alle Werte aus `architecture/0004-design-system.md` werden übernommen, nicht neu erfunden) + `components/ui/`-Basiskomponenten, ohne View-Änderungen.
2. View-für-View-Umstellung in Gruppen: (a) App-Shell + Login (Standalone-vs.-Shell-Layout-Parität), (b) Projekt-Seiten + FolderBrowser, (c) Grid/Detail/Compare + RatingButtons/RatingBadge.
3. Die drei funktionalen Fixes (Retry-Button, `autocomplete`, Busy-Button bei RatingButtons) werden dabei eingebaut, jeweils an der Stelle, wo die betroffene Komponente ohnehin umgestylt wird.

**Bezug zu bestehenden Werten:** Alle Farb-Hex-Werte, die Spacing-Skala, die Touch-Ziel-Vorgabe und die Muster (Busy-Button, Skeleton, Vorschlags-Badge, Fehlerzustand mit Retry) aus `architecture/0004-design-system.md` werden 1:1 als Design-Tokens/Komponentenvarianten übernommen — diese Spec macht sie erstmals visuell sichtbar, verändert ihre inhaltliche Definition aber nicht. Abweichungen, die sich bei der tatsächlichen Umsetzung als nötig erweisen (z.B. Kontrastanpassung für WCAG-AA), werden im Design-System-Dokument nachgetragen, nicht stillschweigend im Code entschieden.

**PR-Empfehlung (für den `developer`-Agenten, nicht bindend für die Spec-Struktur selbst):** mindestens zwei PRs — (1) Tailwind/shadcn-Fundament + Tokens + `components/ui/` ohne View-Änderungen, isoliert verifizierbar; (2) View-Migration in den oben genannten Gruppen, ggf. weiter aufgeteilt. Ein einzelner PR über 9+ Dateien plus neue Abhängigkeit erschwert Review und Bisektion bei Regressionen.

**ADR:** [`decisions/0010-ui-component-library.md`](../decisions/0010-ui-component-library.md) (neu, Accepted).

**Nicht betroffen:** `specs/architecture/0001-overview.md` (Systemarchitektur/Datenmodell, keine Frontend-Styling-Details) und `README.md` (neue npm-Abhängigkeiten ändern weder Env-Vars noch Docker-Compose-Setup).

## UI/UX

**Stilrichtung "warm & persönlich"** ersetzt die bisher stilistisch neutrale Basis (unreflektierter Vite-Template-Rest) durch eine bewusste, aber zurückhaltende Markenpersönlichkeit — passend zu Familien-Urlaubsfotos, nicht zu einem Business-Dashboard. Details siehe `architecture/0004-design-system.md` (aktualisiert), zentral:

- **Akzentfarbe:** Terracotta/Ziegelton (`#d97757` hell / `#e8916d` dunkel) ersetzt das lila Template-Relikt (`#aa3bff`/`#c084fc`) für Buttons, Links, Fokus-Ring, aktive Filter. Bewusst getrennt von `favorite` (Gold) und `rejected` (Rot) gehalten, damit Status- und Aktionsfarbe nicht verwechselbar werden.
- **Neutraltöne:** `--bg`/`--border`/`--text` werden von kühlem Weiß/Grau auf warme Creme-/Sandtöne umgestellt (hell: `#faf7f2`/`#e8e0d5`; dunkel: warmes Anthrazit `#1f1b18`/`#35302b`) — weniger klinisch, weniger Konkurrenz zur Fotofarbigkeit.
- **Bewertungsfarben** (favorite/album_worthy/rejected) bleiben unverändert — geprüft und für kompatibel befunden (Gold passt bereits zur neuen Akzentfarbe, Grün/Rot sind gelernte Ampel-Signalfarben, kein Stimmungsanstrich nötig/wünschenswert).
- **Formsprache:** durchgängig abgerundete Ecken (8px Standard, 12px für Karten/Dialoge), gemäßigt statt Pill-Design; dezente Schatten für Karten ("aufgelegtes Foto"), im Dark Mode Rahmen statt Schatten.
- **Bildsprache:** die Fotos bleiben visuell im Vordergrund — großzügiger Weißraum um Vorschauen, zurückhaltende Chrome-Flächen, Farbintensität bewusst auf Bedienelemente/Status begrenzt statt auf große Flächen.

**Umgesetzte Zustände (bisher nur strukturell/textuell im Design-System beschrieben, jetzt visuell konkretisiert):**
- Skeleton-Ladezustand: warm-neutrale Platzhalterblöcke mit dezentem Puls, kein Shimmer.
- Busy-Button: einheitliche `Button`-Komponente mit Spinner + Label-Wechsel — behebt zugleich die bekannte Inkonsistenz bei `RatingButtons`.
- Vorschlags-Badge: volle Füllung (entschieden) vs. Umrandung + 10–12% Deckkraft-Fläche (Vorschlag) statt bisher nur `data`-Attribut.
- Fehlerbanner mit "Erneut versuchen": einheitliche Komponente, jetzt auch in `PhotoDetailPage`/`PhotoComparePage` ergänzt.
- `autocomplete="username"`/`"current-password"` auf den Login-Feldern ergänzt.

**Umsetzung:** view-für-view in Gruppen (App-Shell/Login → Projekt-Seiten/FolderBrowser → Grid/Detail/Compare/RatingButtons), mind. 2 PRs, gemäß ADR 0010. Kein neuer Interaktionsablauf, keine neuen Bildschirme — reine visuelle/strukturelle Überarbeitung bestehender 9 Views plus Behebung der drei bestätigten funktionalen Lücken.

## Security

Sicherheitsrelevant mit begrenztem Scope: keine neuen Endpunkte/Eingaben/Auth-Änderungen, aber neue Frontend-Laufzeit-Abhängigkeiten (Radix UI) berühren die in ADR [`decisions/0005-auth-implementation.md`](../decisions/0005-auth-implementation.md) als tragende Voraussetzung festgehaltene Restrisiko-Abwägung für Session-Token in `localStorage` ("jedes künftige Feature, das Drittanbieter-Skripte einführt, macht diese Abwägung hinfällig").

**Geprüft:** Radix-UI-Primitives rendern über React-Kinder/`asChild`-Slot-Klonen, nicht über `dangerouslySetInnerHTML`/rohe HTML-Props — die Trigger-Bedingung "Drittanbieter-Skripte" aus ADR 0005 gilt als **nicht ausgelöst** (first-party gebündelter Build-Code, keine Tracking-/Embed-Skripte, keine neue injizierbare Content-Quelle). Der shadcn-Copy-in-Repo-Ansatz macht die neuen Basiskomponenten zusätzlich zu auditierbarem First-Party-Code statt einer Blackbox-Abhängigkeit.

**Muss-Kriterium:** Datei-/Ordnernamen aus OpenCloud werden in allen migrierten und neuen Views (inkl. künftiger Tooltip-/Dialog-/Popover-Komponenten) weiterhin ausschließlich als React-Kinder (Text) übergeben, nie über `dangerouslySetInnerHTML` oder als HTML-String-Prop an eine shadcn/ui- oder Radix-Komponente.

`specs/architecture/0003-securitykonzept.md` ist bereits im Zuge dieser Konsultation aktualisiert (neuer Eintrag "Angriffsflächen → Frontend", der die `dangerouslySetInnerHTML`-Konvention explizit auf Tailwind/Radix/shadcn ausweitet) — keine weitere Ergänzung nötig.

## Teststrategie

**Automatisiert testbar** (die drei funktionalen Fixes, nicht die reine Optik):
- Retry-Button auf `PhotoDetailPage`/`PhotoComparePage`: bei `query.isError` wird ein Button mit erkennbarer Rolle/Label gerendert; Klick löst `refetch()` aus (Integrationstest, `vi.mock` auf API-Modulebene, `isError`-State erzwingen).
- `LoginPage`: Username-Feld hat `autocomplete="username"`, Passwort-Feld `autocomplete="current-password"` (Unit-Test, `getByLabelText(...).autocomplete`).
- `RatingButtons`: Buttons sind während `busy=true` tatsächlich `disabled`, kein zweiter `onToggle`-Aufruf bei Doppelklick während laufender Anfrage.

**Bewusst nicht automatisiert** (konsistent mit bestehendem Testkonzept-Grundsatz "reine UI-Kosmetik nicht automatisiert testbar"): Terracotta-Farbwert, Radius-/Schatten-Werte, Layout-Feinheiten. Ausnahme: semantisch codierte Farben (Bewertungsstufen) bleiben über bestehende `data-*`-Attribute testbar, nicht über CSS.

**Absicherung bestehender Selektoren:** Bestehende Tests nutzen bereits `getByRole`/`getByLabelText`/`aria-*`/`data-suggested` (kein `getByClassName`/Snapshot-Tests) — richtige Grundlage, da Tailwind/shadcn nur Klassen/DOM-Verschachtelung ändert, nicht Rollen/Labels. Migrationsregel: bei jeder View-Migration müssen zugehörige Tests ohne Anpassung der Assertions grün bleiben; eine zwangsläufige Rollenänderung ist PR-pflichtig zu benennen. `data-suggested`/`data-status`-Attribute aus `RatingBadge` müssen beim Ersetzen durch shadcn-`Badge` erhalten bleiben.

**Kein visuelles Regressionstesting/Playwright:** Aufwand (Screenshot-Baseline-Pflege über 9+ Views, Flakiness bei Font-Rendering) steht in keinem Verhältnis zum Nutzen für ein Zwei-Personen-Projekt. Stattdessen pro PR-Gruppe (a/b/c) ein expliziter manueller Smoke-Test-Durchlauf inkl. Tastatur-Fokus-Reihenfolge (Radix-Fokus-Traps) und Mobile-Viewport, dokumentiert im PR analog zum bestehenden Muster.

**Edge Cases:** Dark Mode nach Token-Umstellung weiterhin funktionsfähig; Fokus-Sichtbarkeit bei Radix-Komponenten; `prefers-reduced-motion` falls Transitions eingeführt werden; der Busy-Button-Fix darf bestehende `aria-pressed`-Semantik nicht verändern.

`specs/architecture/0002-testkonzept.md` wird um die Selektor-Stabilitätsregel als wiederverwendbares Muster für künftige View-Migrationen ergänzt (siehe dort).

## Entscheidungen

- **Tailwind CSS + Radix UI + shadcn/ui** statt Tailwind pur oder einer fertigen Komponentenbibliothek (Chakra, Mantine, MUI) — architect-Konsultation, 2026-08-02, siehe ADR 0010. Keine Rückfrage nötig, da technische Detailentscheidung innerhalb der vom Stakeholder gewünschten Richtung ("Bibliothek einführen, Wahl liegt bei dir").
- **Mindestens zwei PRs** (Fundament, dann View-Migration in Gruppen) statt einem großen PR — architect-Empfehlung, Review-/Bisektions-Gründe.
- **Bewertungsfarben bleiben unverändert**, nur die Akzent-/Neutralfarben ändern sich — ux-ui-designer-Konsultation: Gold/Grün/Rot sind gelernte Ampel-Signalfarben, kein Stimmungsanstrich nötig.
- **Die drei bekannten funktionalen Lücken (Retry-Button, `autocomplete`, Busy-Button `RatingButtons`) werden mit dieser Spec behoben**, nicht separat — Daniel bestätigt im Sharpening-Gespräch: würden ohnehin bei der visuellen Überarbeitung derselben Komponenten berührt, separat zu fixen wäre doppelte Arbeit.
- **Kein visuelles Regressionstesting** — test-engineer-Konsultation: Aufwand/Nutzen-Verhältnis für ein Zwei-Personen-Projekt nicht gerechtfertigt, manueller Smoke-Test pro PR-Gruppe reicht.

## Out of Scope

- Neue Interaktionsabläufe oder neue Bildschirme — reine visuelle/strukturelle Überarbeitung bestehender Views.
- Automatisiertes visuelles Regressionstesting (Playwright/Screenshot-Vergleich).
- Weitere, bisher nicht dokumentierte funktionale Lücken über die drei bestätigten hinaus (z.B. Grid-Ladezustand als reiner Text statt Skeleton wird im Zuge der Migration ohnehin behoben, war aber schon vorher als Nice-to-have vermerkt, kein neues Muss-Kriterium dieser Spec über die AK-Liste hinaus).
- Änderung der repository-weiten Frontend-Coverage-Situation (kein Coverage-Gate für Frontend, bekannte, hier nicht adressierte Lücke aus dem Testkonzept).
