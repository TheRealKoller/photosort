# 0010 - UI-Komponentenbibliothek: Tailwind CSS + Radix UI + shadcn/ui

**Status:** Accepted
**Datum:** 2026-08-02

## Kontext

Das Frontend besteht aus 9+ Views/Komponenten (`App.tsx`, `pages/*`, `FolderBrowser`, `RatingButtons`, `RatingBadge`, `PhotoImage`), die vollständig implementiert, aber unstyled sind (reines semantisches HTML/JSX, siehe `architecture/0004-design-system.md`, Abschnitt "Bekannte Lücken"). `index.css`/`favicon.svg` tragen noch unreflektierte Vite-Template-Reste (lila Akzentfarbe, `#social`-Regeln). Das Design-System-Dokument definiert bereits inhaltliches Vokabular (4 Bewertungsfarben+Symbole, 3 Prozess-Status-Farben, Vorschlags-Badge, Busy-Button, Skeleton-Ladezustände, Touch-Ziele ≥44px, WCAG-AA), hält aber ausdrücklich fest: "Noch keine Komponentenbibliothek gewählt … läuft über `architect`/ADR." Diese ADR trifft diese Wahl. Auslöser ist die Feature-Spec `features/0012-visual-redesign.md` ("warm & persönlich"-Stilrichtung).

Randbedingungen aus `architecture/0004-design-system.md` und den Designprinzipien: PWA mit Mobilfunk-Nutzung ("Durchsatz vor Erklärung", keine Web-Fonts nachladen), zwei bekannte Nutzer (kein Enterprise-Anspruch), Wartbarkeit durch eine KI als einziger Entwickler (`decisions/0001-tech-stack.md`: "gut dokumentiert, ausgereiftes Tooling" als wiederkehrendes Kriterium).

## Entscheidung

- **Styling:** Tailwind CSS (Utility-First, PostCSS-Build via Vite-Plugin).
- **Primitives:** Radix UI (unstyled, zugängliche Verhaltens-Primitives — Dialog, Progress u.ä., wo gebraucht).
- **Komponenten:** shadcn/ui-Muster — Komponenten werden als Quellcode ins Repo kopiert (`frontend/src/components/ui/`), nicht als Laufzeit-Abhängigkeit installiert. Kein zusätzliches `node_modules`-Paket "shadcn/ui" selbst, nur `tailwindcss`, `@radix-ui/react-*` (je nach genutzter Primitive), `class-variance-authority`, `clsx`/`tailwind-merge` als tatsächliche neue `package.json`-Einträge.

## Begründung

- **Bundle-Size/PWA-Performance:** shadcn/ui liefert keine eigene Laufzeitbibliothek — Komponenten sind Tailwind-Klassen + dünne Radix-Wrapper im eigenen Code, vom Bundler wie jeder andere App-Code behandelt und tree-shakebar. Tailwinds Production-Build purged ungenutzte Utility-Klassen (`content`-Scan über `frontend/src/**`), das CSS-Ergebnis bleibt klein. Alternativen mit fertigem Komponenten-Runtime (Chakra UI, Mantine) bringen ein eigenes CSS-in-JS-Laufzeitsystem (z.B. Emotion) mit, das zur Laufzeit Styles berechnet — mehr JS-Payload und Rechenaufwand auf Mobilgeräten, die laut Designprinzipien gleichrangig zu Desktop sind. Das widerspräche "Durchsatz vor Erklärung"/Mobilfunk-Nutzung stärker als der gewählte Ansatz.
- **Zugänglichkeit ohne Zusatzaufwand:** Radix-Primitives bringen Tastaturbedienbarkeit/ARIA-Semantik für die Fälle mit, wo natives HTML nicht reicht (z.B. künftig ein Dialog). Für die meisten bestehenden Views (Buttons, Formulare, Listen) genügt weiterhin natives HTML mit Tailwind-Klassen — die bestehenden guten Muster (native `<button>`, kein `div`-Onclick, siehe Design-System "Bekannte Lücken"/UX-Review 0005) bleiben unverändert gültig und werden durch die Bibliothek nicht verdrängt.
- **Wartbarkeit durch KI-Entwicklung:** Tailwind und shadcn/ui gehören zu den am besten dokumentierten/trainierten Frontend-Stacks überhaupt (Konsistenz mit dem in `decisions/0001-tech-stack.md` genannten Kriterium). Der Copy-in-Repo-Ansatz von shadcn/ui bedeutet außerdem: Komponenten liegen als lesbarer, editierbarer Code im eigenen Repo statt hinter einer fremden Paket-API versteckt — bei einem Ein-Personen-KI-Projekt ohne Team-Koordinationsbedarf ein klarer Vorteil, da spätere Anpassungen (z.B. Design-System-Farben) direkt im Code statt über Theme-Override-APIs einer Fremdbibliothek passieren.
- **Bereits verfügbarer Skill:** Im Environment existiert bereits ein Skill `ui-design-system`, der exakt für "React UI component systems with TailwindCSS + Radix + shadcn/ui" ausgelegt ist — spricht zusätzlich für Konsistenz mit vorhandenem Tooling statt eine weitere, unbegleitete Wahl zu treffen.
- **Warum nicht Tailwind pur (ohne Radix/shadcn):** Die im Design-System dokumentierten Muster (Busy-Button, Skeleton, Vorschlags-Badge mit gedämpfter/voller Füllung) sind wiederkehrende, komponentenartige Bausteine — sie in jeder View einzeln aus rohen Tailwind-Klassen zusammenzusetzen widerspräche der eigentlichen Absicht ("Komponentenbibliothek einführen statt weiter reinem CSS"), auf die die Spec explizit abzielt.
- **Warum nicht Material UI (MUI):** Bringt eine eigene, visuell markante Designsprache mit, die gegen die gewünschte Stilrichtung "warm & persönlich" (statt neutral/business-artig) einen aktiven Gegenwind erzeugt — Umgestalten wäre aufwändiger als bei einem unstyled-Primitives-Ansatz.

## Konsequenzen

- Neue `package.json`-Abhängigkeiten (Frontend): `tailwindcss`, `postcss`, `autoprefixer`, `@radix-ui/react-*` (nur die tatsächlich genutzten Primitives, schrittweise ergänzt statt vorab alle), `class-variance-authority`, `clsx`, `tailwind-merge`.
- Neue Konfigurationsdateien: `tailwind.config.ts`, `postcss.config.js`; `frontend/src/index.css` wird auf Tailwind-Direktiven + Design-Tokens (CSS-Variablen für die im Design-System definierten Farben) umgestellt, Template-Reste (`#aa3bff`, `#social`) entfallen dabei.
- `frontend/src/components/ui/` entsteht als neues Verzeichnis für kopierte shadcn/ui-Basiskomponenten (Button, Card, Badge, Progress o.ä.) — Konvention für künftige Features: neue wiederkehrende UI-Bausteine werden dort ergänzt statt pro View neu erfunden.
- Kein Lock-in in eine Fremd-API — spätere Anpassungen bleiben normaler Code-Change, keine ADR-pflichtige Bibliothekswahl pro Komponente. Ein Wechsel weg von Tailwind selbst (grundlegender als Komponentenwahl) bliebe architekturrelevant und bräuchte eine neue ADR.
- `architecture/0004-design-system.md` wird mit dieser ADR referenziert und im Abschnitt "Grundbausteine"/"Bekannte Lücken" aktualisiert (Komponentenbibliothek ist ab jetzt gewählt, nicht mehr offen).
