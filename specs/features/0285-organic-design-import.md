# 0285 - Import des Design-Systems „Organic" aus dem Claude-Design-Mockup

**Status:** Implemented
**Erstellt:** 2026-08-30
**Bezug:** Kein GitHub-Issue — direkte Anforderung von Daniel im Chat, unter Verweis auf das Claude-Design-Projekt [„PhotoSort UI Mockups"](https://claude.ai/design/p/86922c70-df0c-4c7b-86bd-e7125a3e76bf) (`PhotoSort.dc.html`, 12 Artboards + Desktop-Layouts, Design-System-Bundle `_ds/organic-f0aac5b3-.../`). Ergänzt/überschreibt Teile von [`0012-visual-redesign.md`](./0012-visual-redesign.md) und ADR [`0011`](../decisions/0011-visuelle-gestaltungsrichtung.md).

## Abweichung vom Spec-first-Grundsatz

Diese Spec wurde **nachgezogen**, nicht vorab erstellt. CLAUDE.md verlangt Spec vor Umsetzung; hier lag die Anforderung bereits in vollständig ausgestalteter Form vor — das Mockup ist die Spezifikation, samt eigenem Design-System-Bundle mit Tokens, Komponentenklassen und schriftlicher Gestaltungsanleitung (`readme.md`). Eine vorgelagerte Prosa-Spec hätte dem nichts hinzugefügt, das die Vorlage nicht präziser sagt. Festgehalten wird hier deshalb das, was das Mockup **nicht** entscheidet: die Abweichungen, die bei der Übernahme nötig waren, und ihre Begründung.

## Ziel

Die visuelle Gestaltung von PhotoSort auf das Design-System „Organic" umstellen: warmer Creme-/Sandgrund, Terracotta als Akzent, Salbei als gleichrangige zweite Stimme, Caprasimo über Figtree, stark abgerundete Formsprache mit Pillen für kleine Bedienelemente.

## User Story

Als Daniel möchte ich, dass die App so aussieht wie das Mockup, das ich in Claude Design entworfen habe, damit die tatsächliche Oberfläche und mein Entwurf nicht auseinanderlaufen.

## Akzeptanzkriterien

- [x] Farbrollen, Tonleitern (100–900), Schrift, Radien- und Abstandsskala der Vorlage liegen als Design-Tokens in `frontend/src/index.css` und sind über den `@theme`-Block als Tailwind-Utilities verfügbar.
- [x] Die Schriften Caprasimo und Figtree sind eingebunden, ohne die Offlinefähigkeit der PWA zu beschädigen.
- [x] Kleine Bedienelemente (Buttons, Eingabefelder, Chips, Icon-Buttons, Fortschrittsbalken) sind volle Pillen; Karten/Dialoge/Panels sind stark abgerundet und stehen auf `--surface`.
- [x] Die Bewertungsfarben sind die drei Töne der Vorlage (Ocker/Salbei/Ziegel).
- [x] Anmeldung, Projektliste (inkl. Leerzustand) und Stepper folgen den Artboards 1, 2 und 4.
- [x] Der Dunkelmodus bleibt erhalten.
- [x] Jede Text-/Symbolfarbe erreicht gegen ihren tatsächlichen Untergrund WCAG-AA (4,5:1), in **beiden** Farbschemata.
- [x] `specs/architecture/0004-design-system.md` und `.claude/skills/design-system/SKILL.md` geben den neuen Stand wieder.

## Out of Scope

- **Desktop-Artboard (D):** Die Vorlage zeigt drei Desktop-Layouts für die schweren Ansichten (Projektliste, Kuratierung, Foto-Detail) mit mehrspaltiger Anordnung. Das ist eine Layout-Änderung, keine Gestaltungsübernahme, und damit ein eigenständiges Thema — die bestehenden responsiven Layouts bleiben unverändert.
- **Umstellung auf Lucide-Icons:** Die Vorlage schreibt Lucide bei Strichstärke 2,75 vor. Das Produkt nutzt derzeit handgezeichnete Inline-SVGs und Textsymbole. Ein Icon-Set ist eine neue Abhängigkeit und damit ADR-pflichtig.
- **Verlagerung von Navigation:** Artboard 4 zeigt Zurück- und Einstellungen-Symbol in der Kopfzeile. Wo Navigation *liegt*, ist eine Informationsarchitektur-Entscheidung, keine visuelle — die bestehende Navigationsleiste bleibt, wo sie ist.
- **Fotominiaturen auf Projektkarten:** Artboard 2 zeigt je Projekt ein Vorschaubild. Dafür gibt es keine Datenquelle (die Projektliste liefert kein Titelbild); das wäre ein Backend-Feature, keine Gestaltung.

## Architektur / Umsetzung

Die Token-Ebene des Frontends war bereits die richtige Naht: Rohwerte in `:root`/`prefers-color-scheme`, Zuordnung zu Utilities im `@theme`-Block. Der Import tauscht daher überwiegend **Werte**, nicht Struktur — die Token-*Namen* bleiben, wodurch der Großteil der Komponenten ohne Änderung mitzieht.

**Betroffene Dateien:**
- `frontend/src/index.css` — Tokens, Tonleitern, Dunkelmodus, Basis-Schriftregeln, `.washed`-Utility.
- `frontend/src/components/ui/{button,input,card,popover,progress,badge}.tsx` — Formsprache (Pillen, Flächenfarbe, Display-Schrift auf Buttons).
- `frontend/src/components/{BrandMark,StatusTag}.tsx` — neu.
- `frontend/src/components/{Stepper,RatingButtons,RemoteCategoryClassificationSection}.tsx`, `frontend/src/pages/**` — Anwendung der Muster.

### Abweichungen von der Vorlage (jeweils mit Grund)

1. **Schrifteinbindung über `@fontsource` statt Google-Fonts-CDN.** Das Readme der Vorlage bindet die Schriften per `@import` von `fonts.googleapis.com` ein. PhotoSort ist eine PWA mit Offline-Anspruch; ein CDN-Link wäre offline ein Fehlschlag und zusätzlich ein Abfluss von Nutzungsdaten an einen Dritten. Die Schriften werden self-gehostet gebündelt und vom Service Worker precacht.

2. **Akzent aufgeteilt in `--accent` und `--accent-strong`.** Der Basiston `#c67139` erreicht gegen den Grund nur 3,03:1. Das Readme der Vorlage benennt das selbst und verweist für Text in Akzentfarbe auf die Rampenstufe 700. Genau so umgesetzt: `--accent` für Chrome, `--accent-strong` (`#8c491a`, 5,72:1) für Fließtext und Links.

3. **`--accent-fg` ist dunkle Tinte, nicht Creme.** Die Vorlage setzt für den Primärbutton Creme auf Terracotta — 3,03:1, verfehlt AA für die 14px-Beschriftung. Zwei Auswege wären möglich gewesen: die Füllung abdunkeln (wie das Projekt es 2026 schon einmal tat, `#d97757` → `#bb4e2a`) oder die Schrift abdunkeln. Gewählt wurde die Schrift, weil der Terracotta-Ton der Vorlage das Farbbild der gesamten Oberfläche trägt — ihn an jeder gefüllten Fläche abzudunkeln hätte den Import in seinem sichtbarsten Merkmal verfehlt. Dunkle Tinte erreicht 4,60:1 hell und 8,03:1 dunkel, gilt also in beiden Modi.

4. **`--chip-fg` entfällt zugunsten von `--rating-<ton>-fg`.** Die drei Bewertungstöne der Vorlage tragen keine gemeinsame Vordergrundfarbe mit AA: schwarz hält auf Ocker (7,88:1) und Salbei (4,99:1), fällt auf Ziegel auf 3,53:1; Creme hält auf Ziegel (5,00:1), fällt auf Ocker auf 2,24:1. Ein Vordergrund je Ton löst das, **ohne einen einzigen Farbwert der Vorlage zu verändern** — das war der Grund, diesen Weg der Alternative (Töne abdunkeln, bis ein gemeinsames Ink hält) vorzuziehen: dabei hätte der Ocker `#c9962c` auf `#85631d` gemusst und wäre kein Ocker mehr gewesen.

5. **Sekundärtext als eigener Ton statt über `opacity`.** Die Vorlage dämpft Sekundärtext durchgehend per Deckkraft. Deckkraft auf beliebigem Untergrund ist nicht kontrastprüfbar; stattdessen `--text: #645c50` (neutral-700) mit 5,53:1 auf `--bg` und 4,92:1 auf `--surface`.

6. **Dunkelmodus abgeleitet, nicht übernommen.** „Organic" definiert nur einen hellen Grund. Der Dunkelmodus war vor diesem Import vorhanden und wird nicht aufgegeben; die Palette ist aus denselben Tonleitern gespiegelt (Grund/Fläche aus den dunklen, Text/Akzente aus den hellen Stufen), damit die Farbfamilien identisch bleiben.

7. **Status-Pillen mit eigenen Tint/Strong-Tokenpaaren.** Artboard 2 zeigt getönte Pillen mit farbiger Beschriftung. Die vorhandenen `--status-*`-Farben sind nur als Flächenfarbe kalibriert; für die Pille braucht es je Zustand ein textfähiges Paar. Alle vier Paare erreichen ≥ 6,4:1 in beiden Modi.

8. **`.washed` gilt nicht für Bewertungsfotos.** Die Vorlage wäscht jedes Inhaltsfoto. In den Bewertungs- und Vergleichsansichten ist die Bildwirkung (Schärfe, Belichtung, Farbe) aber genau der Gegenstand der Entscheidung — eine kosmetische Wäsche würde verfälschen, worüber der Nutzer urteilt. Die Utility bleibt daher dekorativen Bildern vorbehalten.

## Teststrategie

Kein neuer fachlicher Code, daher überwiegend Regressionsschutz: Die 538 bestehenden Frontend-Tests müssen grün bleiben — sie prüfen durchgehend über Rollen, `aria-label` und `data-*`-Attribute statt über CSS-Klassen (Selektor-Stabilitätsregel aus `architecture/0002-testkonzept.md`) und sind gegenüber einer reinen Umgestaltung deshalb belastbar.

Neu hinzugekommen sind Tests genau dort, wo die Umstellung echte Verzweigungslogik erzeugt hat:
- `badge.test.tsx` — hält die Kopplung „Füllung und Vordergrund gehören zum selben Ton" fest, damit ein späteres Vereinheitlichen auf ein gemeinsames Ink (das AA brechen würde) auffällt.
- `StatusTag.test.tsx` — vier Zustände, Beschriftung, Laufindikator nur im laufenden Zustand, `aria-hidden` auf dem dekorativen Indikator.

Kontrastwerte wurden nicht geschätzt, sondern für jede Paarung ausgerechnet; die Ergebnisse stehen als Kommentar an der jeweiligen Token-Definition.

## Security

Keine sicherheitsrelevante Änderung im engeren Sinn. Ein Punkt mit Bezug zum Sicherheitskonzept: Die Schriften werden bewusst nicht von einer Fremd-CDN geladen, wodurch kein Nutzungsdatenabfluss (IP, Referrer, User-Agent bei jedem Seitenaufruf) an Google entsteht und die Angriffsfläche eines fremden Skript-/Ressourcen-Ursprungs entfällt.
