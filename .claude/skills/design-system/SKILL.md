---
name: design-system
description: Kapselt PhotoSorts Design-System (Farben, Formsprache, wiederkehrende UI-Muster) und die gewählte Komponentenbibliothek (Tailwind CSS + Radix UI + shadcn/ui) für konsistente Frontend-Arbeit. Nutze diesen Skill IMMER, wenn an Code in frontend/src/ gearbeitet wird — neue oder geänderte React-Komponenten/Views, Styling, Farb-/Abstandsentscheidungen — oder wenn Design-System-Konformität geprüft/reviewt werden soll, auch wenn die Worte "Design-System"/"UI/UX" nicht explizit fallen (z.B. "bau eine neue Ansicht", "style diese Komponente", "mach das ansprechender", "review das Frontend").
---

# PhotoSort Design-System

Schnellreferenz für konsistente UI-Arbeit in diesem Repo. Die eigentliche Quelle der Wahrheit sind [`specs/architecture/0004-design-system.md`](../../../specs/architecture/0004-design-system.md) (lebendes Dokument, gepflegt vom `ux-ui-designer`-Agenten) und [`specs/decisions/0011-ui-component-library.md`](../../../specs/decisions/0011-ui-component-library.md) — bei Unsicherheit oder Widerspruch dort nachschlagen statt zu raten, dieser Skill ist nur die griffige Zusammenfassung für den täglichen Gebrauch.

## Warum dieser Skill existiert

Das Design-System-Dokument ist lang und wächst mit jeder Spec weiter — beim eigentlichen Bauen einer Komponente will man nicht jedes Mal das ganze Dokument durchsuchen. Dieser Skill liefert die Werte/Muster, die in praktisch jeder Frontend-Änderung gebraucht werden, direkt griffbereit. Er dupliziert das Dokument nicht als Kopie — bei einer Design-Entscheidung, die hier nicht abgedeckt ist, ins Dokument schauen und diesen Skill danach ergänzen, statt im Code zu raten.

## Designprinzipien (Kurzform)

- **Sachlich, kompakt, informationsdicht.** PhotoSort ist in der Nutzung ein Arbeitswerkzeug für lange Sichtungssitzungen. (Ersetzt das frühere Prinzip „warm & persönlich" — das ist ausdrücklich zurückgenommen.)
- **Die Fotos sind der Star, nicht die Oberfläche.** Die Oberfläche steht unmittelbar neben dem Bild und beeinflusst dessen Farbwahrnehmung: farbneutral und dunkel, damit sie hinter das Bild zurücktritt statt es einzufärben. Chrome-Flächen zurückhaltend, Farbintensität auf Bedienelemente/Status begrenzt, nicht auf große Flächen.
- **Durchsatz vor Erklärung.** Kernaufgabe ist zügiges Durchsehen potenziell tausender Fotos — jede zusätzliche Interaktion pro Foto multipliziert sich. Kein Onboarding/Tutorial-Text, der beim zweiten Mal stört.
- **Bewertungsstufen auf einen Blick unterscheidbar.** Per Farbe UND Symbol, nicht nur Text — wichtig bei kleinen Grid-Kacheln.
- **Touch und Tastatur gleichrangig.** PWA-Nutzung auf Mobilgeräten ist kein Nebenfall.
- **Ehrliche Ladezustände statt erzwungenes Warten.** Sichtbar machen, was noch lädt/nicht bereit ist, statt zu blockieren.

## Farbpalette (Design-Tokens)

Aktueller Stand aus `architecture/0004-design-system.md` — bei Änderungen dort zuerst aktualisieren, dann hier nachziehen. Alle Rohwerte stehen ausgeschrieben in `frontend/src/index.css` (`:root`), die Zuordnung zu Utilities im `@theme`-Block.

**Es gibt nur EIN Farbschema: dunkel.** Kein heller Modus, kein Umschalter, kein `prefers-color-scheme`, keine `dark:`-Klassen. Ein heller Grund ist für die Kernaufgabe die schlechtere Wahl, nicht eine gleichwertige Alternative. (Ausdrückliche Rücknahme der früheren Hell/Dunkel-Doppelung.)

**Vier Flächenstufen ersetzen Schatten als Tiefenmittel:**

| Token | Wert | Wofür |
|---|---|---|
| `--bg` / `bg-bg` | `#0B0C10` | tiefster Grund, Bildfokus |
| `--surface` / `bg-surface` | `#14161F` | Standardfläche, Panels, Eingabefelder |
| `--elevated` / `bg-elevated` | `#1E2230` | Karten, Popover, Meldungen, Status-Pillen |
| `--overlay` / `bg-overlay` | `#262B3D` | Dialoge, Sekundär-Button, Hover-Fläche |

**Vier Akzente:** `--accent #FFB000` (Auswahl/Favorit/aktiv) · `--info #00E5FF` · `--danger #FF3D00` (aussortiert) · `--accent-2 #00E676` (album-würdig). `--accent-strong`/`--accent-2-strong` zeigen auf denselben Wert wie `--accent`/`--accent-2` — auf dunklem Grund trägt der Akzent selbst 7,67–10,67:1, eine getrennte Textstufe ist nicht nötig. Für Text/Symbole AUF gefüllter Akzentfläche `--accent-fg` (`#0B0C10`).

**Akzent und Favorit teilen den Wert, aber nicht den Namen.** `--accent` und `--rating-favorite` sind beide `#FFB000`. Die frühere Regel „Akzent und Bewertungsfarben getrennt halten" ist damit zurückgenommen; die semantische Trennung überlebt in den Tokennamen, also weiterhin das rollenrichtige Token verwenden.

**Vier Textstufen:** `--text-h #FFFFFF` (Überschrift/Primär) · `--text #A0A5B5` (Fließtext) · `--text-muted #8D92A4` (Metadaten, Hotkeys, Platzhalter) · `--text-disabled #3E4252`.

- **`--text-disabled` ausschließlich auf tatsächlich deaktivierten Elementen** — nie auf Inhaltstext. Nur als `disabled:` / `has-[:disabled]:` / `group-disabled:`-Variante (statisch geprüft). Es liegt bewusst unter 3:1; WCAG nimmt inaktive Bedienelemente aus.
- **Textstufe 2 und 3 sind nur schwach unterscheidbar.** Hierarchie darf nicht über `--text` gegen `--text-muted` allein aufgebaut werden — Abstand, Schnitt und Reihenfolge müssen sie tragen. Ein Leerzustandstext ist die Hauptaussage der Seite und steht in `--text`, nicht in `--text-muted`.

- **Zwei nicht-textliche Rollen, die leicht übersehen werden:** `--text-disabled` ist zusätzlich die **Fläche des Skeleton-Platzhalters** (`--elevated` misst dort nur 1,23:1 gegen den Seitengrund — der Ladezustand wäre unsichtbar). Und `--border` ist zusätzlich die **gedrückte Fläche** unaufdringlicher/sekundärer Schaltflächen (`active:bg-border`); darauf gehören nur `--text` (5,49:1) oder `--text-h`, **nie** `--text-muted` (4,36:1) oder `--danger-text` (4,33:1) — statisch geprüft.

**Rahmen in zwei Rollen — hier wird am häufigsten falsch gegriffen:**

- `--border` (`#2A2E3D`, `border-border`) ist **rein dekorativ**: Panelkante, Tabellenlinie, Karten- und Dialogumriss. 1,04–1,45:1 — als **einziger Umriss eines Bedienelements ist es ein unsichtbarer Button**.
- `--border-control` (`#727891`, `border-border-control`) ist der **sichtbare Umriss eines Bedienelements**: Sekundär-Button, Eingabefeld, Kontrollkästchen, Schalter, Select. ≥3:1 auf allen vier Flächen. In `ui/button.tsx`, `ui/input.tsx`, `ui/switch.tsx`, `ui/checkbox.tsx` ist `border-border` deshalb statisch verboten (Ausnahme: der `disabled:`-Zustand).

**`--danger` vs. `--danger-text`:** `--danger` (`#FF3D00`) ist **grafisch** — Flächen, Rahmen, Symbole, Fehlerrand am Feld. Für **Text** in Aussortiert-Farbe gilt ausnahmslos `--danger-text` (`#FF5A26`); `text-danger` ist statisch verboten.

**Bewertungsfarben:** `favorite #FFB000` + `star` · `album_worthy #00E676` + `book` · `rejected #FF3D00` + `x-circle` · unbewertet neutrales „–"-Badge. Alle drei `--rating-*-fg` tragen dieselbe dunkle Tinte `#0B0C10`, bleiben aber **drei getrennte Tokens** — dass eine gemeinsame Tinte hält, ist eine Eigenschaft dieser Palette, keine Regel. Bei voller Füllung immer die tonspezifische `--rating-<ton>-fg` verwenden.

**Kein Bewertungszustand darf allein über seine Farbfläche dargestellt werden** — nicht als farbiger Punkt, Rahmen oder Balkensegment ohne begleitendes Symbol oder Text. In Graustufen liegen Favorit und Album-würdig bei nur 1,10:1 zueinander; die Mehrfachcodierung (zugänglicher Name + eigenes Symbol + `data-struck` beim Aussortierten) ist die einzige Stütze.

**Prozess-Status und Status-Pillen** stehen auf der **Toast-Konstruktion**: Fläche `--elevated`, farbiger 1px-Rand, farbige Beschriftung (`components/StatusTag.tsx`, `--status-<zustand>-tint`/`-strong`). Die reinen Flächenfarben `--status-running`/`-success`/`-failed` bleiben Flächenfarben (Punkt, Balkenfüllung), nie Textfarbe; auf gefüllter Erfolgsfläche `--status-success-fg`.

**Kategorie-Chips haben eigene Farben** (Rücknahme von „Kategorie-Chips immer neutral"): dreizehn Paare `--chip-<slug>-bg`/`-fg`, aufgelöst über eine nach `category_key` geschlüsselte Konstante in `components/CategoryBadge.tsx` (`Object.hasOwn`-Lookup, unbekannter Key → neutrales Paar, kein Absturz und kein leeres Badge). „Nicht erkannt" ist bewusst neutral. **Drei verbindliche Regeln halten Chip und Bewertung auseinander** — „Menschen" liegt farblich praktisch auf dem Favorit-Amber:

1. **Gefüllt ↔ getönt:** Bewertung = voll gefüllte Fläche mit dunkler Tinte, Kategorie-Chip = getönte Fläche mit heller, bunter Schrift.
2. **Radius 6px (Bewertung) ↔ 16px (Chip).**
3. **Gegenecken-Platzierung** auf der Kachel.

**Schrift:** `--sans` = **Inter** (400/500/600/700), `--mono` = **JetBrains Mono** (400), self-gehostet über `@fontsource` — die PWA muss offline funktionieren, und ein CDN-Link wäre zusätzlich ein Abfluss von Nutzungsdaten an einen Dritten. **Es gibt keine Display-Schrift** (`font-heading` ist gestrichen); Überschriften sind Inter in unterschiedlichen Schnitten.

Typoskala (Größe, Standardschnitt): `text-xs` 12px · `text-sm` 14px · `text-base` 16px Regular · `text-lg` 20px Medium · `text-xl` 24px Regular · `text-2xl` 40px Semi-Bold · `text-3xl` 64px Bold. **`text-4xl` und größer erzeugen keine Regel mehr.** Seitenüberschriften tragen die großen Stufen erst ab `sm:` (`text-xl sm:text-2xl`, Anmeldung `text-2xl sm:text-3xl`) — bei 360px läuft ein umbruchloses deutsches Wort in 40/64px über den Rand, und horizontales Scrollen der Seite ist ein Ausschlusskriterium. Eine explizite `font-*`-Utility an der Aufrufstelle gewinnt weiterhin über den Standardschnitt. Die Board-Rolle „Beschriftung" (Versalien) entsteht über `text-xs font-semibold uppercase tracking-wide`, nicht dadurch, dass `text-xs` sie mitbringt.

**Kontrast:** jede Text-/Symbolfarbe erreicht WCAG-AA gegen **die Fläche, auf der sie tatsächlich steht** (4,5:1 Fließtext, 3:1 grafisch und Bedienelement-Umrisse) — besonders zu prüfen bei Text, der auf `--elevated` oder `--overlay` landet statt auf `--bg`. Nachgerechnet in `frontend/src/designSystem.contract.test.ts`; zwei begründete Ausnahmen: `--text-disabled` und `--border`. Neue Farbwerte nie schätzen, sondern dort in die Matrix aufnehmen.

## Symbole

Zwölf Symbole, mehr gibt es nicht: `star · book · x-circle · cog · image · check · info · chevron-down · search · folder · camera · tag`.

- **Immer über `components/ui/icon.tsx`** (`<Icon name="star" size={16} />`). Das ist die **einzige** Datei, die aus `lucide-react` importieren darf — statisch geprüft. Nur **benannte Importe** in einem **statischen Objektliteral**: ein Namespace-Import oder ein berechneter Zugriff auf das Paket-Objekt hebelt das Tree-Shaking aus und zöge den vollen Satz (~32 MB entpackt) ins Bundle.
- Größen 14/16/18/24 (Default 16), Strichstärke 2 und Einfärbung über `currentColor` sind zentral gesetzt — nicht an der Aufrufstelle wiederholen.
- Symbole sind **standardmäßig `aria-hidden`**: ein Symbol ersetzt nie ein Label, es begleitet es. `title` schaltet auf `role="img"` für den seltenen Alleinstand. `data-icon` ist der Selektor für Tests.
- **Den Satz nicht erweitern.** Fünf dokumentierte Lücken bleiben Textzeichen bzw. bestehende Komponenten: `×` (Schließen/Entfernen — es gibt kein neutrales Kreuz, `x-circle` ist das Aussortiert-Symbol), `✎` (Übersteuerungs-Marker), `○` („nicht gelaufen" → `StatusDot`), `●●○` (`QualityMeter`), `–` (unbewertetes Badge). Sie mit einem beliebigen weiteren Lucide-Symbol zu füllen wäre eine Gestaltungsentscheidung ohne Vorlage.

## Formsprache & Spacing

- **Radius:** `rounded-xs` 4px (Hotkey-Kästchen, Fortschrittsbalken) · `rounded-sm` 6px (Buttons, Eingabefelder, Bewertungs-Badges, Status-Pillen) · `rounded-md` 8px (Meldungen, Popover, Icon-Kacheln, Bildflächen) · `rounded-lg` 12px (Panels, Karten) · `rounded-xl` 16px (Dialog, Kategorie-Chips).
- **`rounded-full` nur noch an dieser abschließenden Liste** — jede weitere Fundstelle ist ein Fehler (statisch geprüft): Schalter-Spur und -Knauf, `StatusDot`, die Lade-Spinner (Button, `StatusTag`, `FolderBrowser`), die runden Backdrops der Popover-Trigger über einer Fotokachel. (Rücknahme von „kleine Bedienelemente sind volle Pillen".)
- **Keine Schatten.** `shadow-warm*` und die Schatten-Tokens sind gestrichen; Tiefe entsteht über die vier Flächenstufen. (Rücknahme von „Schatten für Karten, Rahmen im Dark Mode".)
- **Spacing:** 8-Punkt-Raster 4/8/12/16/24/32/48/64px über Tailwinds `p-1 … p-16`. Keine Zwischenwerte, kein eigenes Token.
- **Zwischen fokussierbaren Elementen mindestens 8px** (sonst läuft die abgesetzte Fokuskontur ins Nachbarelement), **zwischen aufgespannten Trefferflächen mindestens 12px**. Die 4er-Stufe ist eine Stufe für **Innen**abstände, nicht für Abstände zwischen Bedienelementen.
- **12-Spalten-Raster** für Seitenlayouts: `grid-cols-12 gap-x-3` (12px Gutter).
- **Keine `.washed`-Bildbehandlung mehr** — auf dem neutral-dunklen Grund treten Fotos von selbst hervor. Die einzige zulässige Dämpfung eines Fotos ist die Bildfläche der aussortierten Karte.

## Trefferflächen: 32px sichtbar, 44px treffbar

Die frühere Regel „mindestens 44×44px für jedes interaktive Element" war eine **Größen**regel und ist zu einer **Trefferflächen**regel geworden. Bedienelemente tragen die kompakten Maße (Standard-Schaltfläche **32px** hoch, `h-8`); die Trefferfläche kommt über ein transparentes Pseudo-Element:

- `tap-target` — spannt **nur die kurze Achse** auf. Standardfall für beschriftete Bedienelemente.
- `tap-target-square` — beide Achsen. Nur für Symbol-Schaltflächen und ähnliche, die tatsächlich in beiden Achsen zu klein sind.

**Vier Regeln, ohne die die Aufspannung schlechter auffindbare Fehler erzeugt als die, die sie behebt:**

1. **Nur die kurze Achse aufspannen** — sonst entstehen breite unsichtbare Flächen, die Nachbarklicks schlucken.
2. **Mindestens 12px Abstand zwischen aufgespannten Bedienelementen.** Die Aufspannung ragt bis zu 6px je Seite über das Sichtbare hinaus; in einer Überlappung gewinnt das obenliegende Element — bei Bewertungsschaltflächen ist das ein **falsch gesetzter Datenwert**, kein Schönheitsfehler. Wo 12px nicht möglich sind, den Abstand erhöhen, nicht die Aufspannung weglassen.
3. **Zeilenweise Listen nicht aufspannen.** Dort ist die **Zeile selbst** die Trefferfläche und bleibt mindestens 44px hoch (`min-h-11`).
4. **Nie innerhalb eines beschneidenden Containers** (`overflow: hidden`) — das Pseudo-Element wird still abgeschnitten (statisch geprüft für denselben Knoten). Dasselbe gilt für `<input>`: ein ersetztes Element trägt keine Pseudo-Elemente. Dort das Element sichtbar groß genug machen.

**Heißer Pfad** (Bewertungsschaltflächen, Weiter/Zurück, Kategorie-Zuordnung): am Telefon **sichtbar** ≥44px (`h-11 sm:h-8`), am Desktop 32px. Man zielt auf das, was man sieht, und ein Fehlgriff schreibt hier eine falsche Bewertung.

## Zustände: „gedrückt" ist Pflicht, Fokus ist global

- **Jede `hover:`-Variante in `components/ui/` braucht eine `active:`-Variante daneben** (statisch geprüft). Tailwind bindet `hover:` an `@media (hover: hover)` — am Telefon fällt der Zustand ersatzlos weg, ein Fingertipp erzeugte sonst gar keine sichtbare Rückmeldung.
- **Fokus: genau eine globale Regel** in `index.css` (`:focus-visible`, 2px `--accent`, 2px Versatz, transparent). In `.tsx` sind `focus-visible:`-, `ring-offset`- und **`outline-none`**-Utilities **verboten** (statisch geprüft). Eine hartkodierte Ring-Versatzfarbe ist auf den Seitengrund verdrahtet und erzeugt auf `--elevated`/`--overlay` einen falsch getönten Kranz — und `outline-none` hebelt die globale Regel **vollständig** aus: sie steht in `@layer base`, jede Utility in `@layer utilities`, und bei Cascade Layers gewinnt die spätere Ebene unabhängig von der Spezifität.
- **Auswahl anliegend, Fokus abgesetzt.** Der Akzent bedeutet gleichzeitig ausgewählt/aktiv/fokussiert/Favorit. Auswahl und Aktiv sind immer eine durchgezogene Kante **am Element** (ohne Abstand), Fokus immer eine **abgesetzte** Kontur mit 2px Luft — der Fokus trägt damit zusätzlich zur Farbe eine Formaussage.
- **Bewegung:** nur Farb- und Deckkraftübergänge bis 150ms, nie Bewegung von Layout oder Position. `motion-reduce:animate-none` an jeder Animation.
- **Kontrollkästchen und Schalter** haben abgeleitete Werte (das Board liefert sie nicht): Kästchen 18px, Radius 4px, `--border-control`, gesetzt in `--accent`; Schalter 48×24px mit 20px-Knauf, Zustand zusätzlich über die **Knaufposition**, nicht nur über die Farbe.

## Komponentenbibliothek: Tailwind CSS + Radix UI + shadcn/ui

Praktisch relevant:

- **shadcn/ui-Komponenten werden als Quellcode kopiert**, nicht als npm-Paket installiert — sie leben in `frontend/src/components/ui/` und sind normaler, editierbarer App-Code. Neue wiederkehrende UI-Bausteine (Button, Card, Badge, Progress, …) dort ablegen statt pro View neu zu erfinden.
- **Radix-Primitives nur dort einsetzen, wo natives HTML nicht reicht** (z.B. Dialog, Popover). Für Buttons/Formulare/Listen bleibt natives HTML + Tailwind-Klassen der Standard — kein `div`-Onclick, keine unnötige Abstraktion über ein natives `<button>`.
- **Utility-Klassen direkt in JSX**, keine neue CSS-in-JS-Laufzeit, keine `styled-components`-artige Abstraktion — widerspräche der Bundle-Size-Begründung der ADR.
- **`Button`-Ausprägungen:** `default` = primär (gefüllte Akzentfläche), `secondary` und `outline` = sekundär (Fläche `--overlay`, Umriss `--border-control` — auf eine Ausprägung vereinheitlicht, es gibt keine vierte gefüllte), `ghost` = unaufdringlich, `link` = Inline-Text. Jede trägt `hover:` **und** `active:`.
- **`Button`, `variant="link"`:** die kompakten `link`-Klassen (`p-0 h-auto min-h-0 min-w-0`) sind über `compoundVariants` gegen die Größen-Klassen (`h-8 min-w-8 px-4 py-2`) abgesichert, mit Regressionstest — kein weiteres Prüfen vor dem Einsatz nötig. Der Link bekommt bewusst **keine** Trefferflächen-Aufspannung: eine unsichtbare 44px-Fläche um Fließtext würde Nachbarklicks schlucken.
- **`Dialog` (`components/ui/dialog.tsx`):** natives `<dialog>`, keine neue Abhängigkeit. Fokusfalle und Esc sind in **eigenem JS** implementiert — jsdom implementiert weder `showModal()` noch Fokusfalle noch Esc, die Zusage wäre sonst untestbar. Verbindlich: Erstfokus auf der **am wenigsten eingreifenden** Aktion (Abbrechen), nie auf einer bestätigenden oder löschenden; Esc schließt, ein Klick auf den verdunkelten Hintergrund **nicht**; Fokusrückgabe an das auslösende Element; Hintergrund scrollt nicht mit; keine Öffnungs-/Schließanimation.
- **`Button`, `asChild` + `disabled`:** blockiert echte Interaktion über `pointer-events-none` + `tabIndex={-1}` (nicht nur `aria-disabled`), da das native `disabled`-Attribut nicht an beliebige Kind-Elemente wie `<a href>`/`Link` gebunden werden kann und ein reiner `preventDefault()`-Handler bei `react-router`-`Link` zu spät käme (Radix `Slot` ruft immer zuerst den Handler des Kindes auf).

## Wiederkehrende Muster

- **Busy-Button:** während einer laufenden Anfrage/eines laufenden Hintergrundprozesses wird der auslösende Button `disabled` (nicht ausgeblendet) und zeigt Spinner-Icon und/oder veränderten Label-Text. Gilt für **jeden** auslösenden Button im Produkt, nicht nur für neue.
- **Skeleton-Ladezustand:** Platzhalterblöcke in `--elevated` mit dezentem Puls (kein Shimmer-Lauflicht) statt Text wie "Lädt…", wo Inhalte schrittweise eintrudeln (Grid, Listen). Für einzelne nachladende Bereiche reicht ein dezenter Inline-Indikator.
- **Vorschlags-Badge:** volle Füllung = von einem Menschen entschieden; **Toast-Konstruktion** (Fläche `--elevated`, farbiger 1px-Rand, farbige Beschriftung) + `cog`-Präfix = maschineller Vorschlag, noch offen. Bewusst **keine** Deckkraft-Tinte mehr: über einer Tinte ist Kontrast statisch nicht rechenbar und damit dauerhaft ungeprüft. `aria-label` immer mit Präfix "Vorschlag: …", nie nur der Stufenname.
- **Meldungen — Toast-Optik, kein Toast-Verhalten** (`components/ui/alert.tsx`, drei Ausprägungen): Fläche `--elevated`, farbiger 1px-Rand, Symbol 18px, Titel in Primärtext, Beitext in Sekundärtext. Erfolg `check`, Warnung `info` (**nicht** `star` — das ist im Produkt das Favorit-Symbol), Fehler `x-circle` mit Text in `--danger-text`. Symbol **und** Titeltext sind Pflicht; die Meldung trägt ihre Bedeutung nie allein über die Umrissfarbe. Meldungen bleiben **inline und kontextnah** (Banner über der betroffenen Ansicht) mit "Erneut versuchen"-Button, nie die ganze App blockierend und **nie schwebend/selbst verschwindend** — das wäre neues Verhalten, nicht neue Optik. Backend-`detail`-Text wörtlich als regulärer Textknoten im **Beitext** anzeigen, nicht umformulieren, nicht in den kuratierten Titel und nie als Markup.
- **Standalone vs. App-Shell:** Bildschirme ohne bestehenden Session-Kontext (aktuell nur Login) laufen als eigenständiger, zentrierter Kartenbereich ohne App-Shell-Kopfzeile. Beide Varianten wrappen den Seiteninhalt in ein `<main>`-Landmark.
- **Bestätigung von Aktionen:** nur für destruktive, schwer rückgängig zu machende Aktionen — bei schnellen, korrigierbaren Aktionen (Bewertung setzen, Logout) reicht direktes visuelles Feedback ohne Dialog.
- **Nicht verfügbare Aktion (Feature-Flag/Vorbedingung)** (noch nicht implementiert, vorgesehen für Spec 0024, rein lokale Kategorie-/Top-Foto-Auswahl ohne Cloud-Anbindung, siehe `decisions/0015-lokale-kategorie-klassifikation.md`): anders als Busy-Button (vorübergehend beschäftigt) bleibt der Bereich sichtbar, aber dauerhaft/bedingt `disabled` (Konfig-Schalter `category_selection_enabled` aus, oder Phase-A-Lauf fehlt), mit neutralem Erklärtext darunter (kein `Alert`, da kein Fehler) — nach Möglichkeit proaktiv aus bereits geladenen Daten abgeleitet, nicht erst nach einem fehlgeschlagenen Request.
- **Kategorie-Kennzeichnung** (Kürzel-Schema korrigiert für die künftige Spec 0037, noch nicht implementiert): zweiter, von `RatingBadge` getrennter Chip (`components/CategoryBadge.tsx`) mit dem **eigenen Farbpaar der jeweiligen Kategorie**, getönt statt gefüllt und mit Radius 16px statt 6px — die drei Regeln oben halten ihn von der Bewertung auseinander. Positions-/Sichtbarkeitsregel unverändert (Gegenecke zur Rating-Badge, nur solange keine eigene Bewertung existiert). **`category_key` ist ein freier String, kein festes Enum mehr** — kein L/D/M-Kürzel-Schema. Grid-Kachel zeigt stattdessen die ersten drei Zeichen von `category_key` in Großbuchstaben (z.B. "LAN" für "landschaft"), ausgeschriebener Name nur als `aria-label`/`title`. In der neuen, nach Kategorie gruppierten Kuratierungsansicht dient derselbe `category_key` als ausgeschriebene Abschnittsüberschrift: generisch werden Unterstriche → Leerzeichen und erster Buchstabe groß (z.B. "Landschaft"); `category_key` mit Sonderzeichen (Umlaute) nutzen ein explizites Mapping in `categoryLabels.ts` (z.B. "gebaeude" → "Gebäude", implementiert mit Spec 0045), ohne dass für künftige Kriterien jeweils ein Mapping-Eintrag nötig ist — der generische Fallback deckt alle unbekannten Keys ab. Kategorien-Reihenfolge: alphabetisch nach `category_key`.
- **Gateführter Sammel-Review mit Einmal-Bestätigung** (noch nicht implementiert, vorgesehen für Spec 0037): verpflichtender Zwischenschritt, der eine automatisch erzeugte Liste zeigt, aber nur eine einzige Abschluss-Bestätigung statt einer pro Element verlangt. Erweiterung der bestehenden gefilterten Grid-Ansicht (Banner + Abschluss-Button), kein eigener neuer Screen. Nachfolgeschritt bleibt bis Bestätigung im Zustand "Nicht verfügbare Aktion".
- **Automatisch übersprungener Schritt** (noch nicht implementiert, vorgesehen für Spec 0037): ist die Gate-Vorbedingung trivial erfüllt (z.B. leere Liste), automatisch bestätigen statt zu blockieren — aber mit dauerhaft sichtbarem Erklärtext an der Stelle, wo sonst der Bestätigungsstatus steht, nie ein flüchtiger Toast.
- **In-place Nachrücken (Backfill) statt Reflow** (noch nicht implementiert, vorgesehen für Spec 0037): wird eine Kachel aus einem festen N-Slots-Raster entfernt und ein Nachfolgekandidat existiert, bleibt die Kachel an ihrer Position (kurzer Skeleton, dann nächstes Foto) statt die übrigen Kacheln neu anzuordnen. Kein weiterer Kandidat mehr vorhanden: Kachel bleibt als "Leerer Zustand"-Variante an derselben Stelle (kein Verschwinden, kein Fehler-Styling).
- **Grobe Qualitäts-Einordnung statt Rohwert** (noch nicht implementiert): kein numerischer Score — stattdessen 3 Stufen ("Einfache"/"Gute"/"Hohe Bildqualität") aus dem bestehenden `local_quality_score` abgeleitet, dargestellt als neutrales Drei-Punkte-Meter (`●●●`/`●●○`/`●○○`, `aria-hidden`) + ausgeschriebener Stufenname als eigentlicher Text. Kein Stern-Symbol (Kollision mit `favorite`-★), keine Prozess-Status-Farbe. Nur in der Detailansicht, nicht auf der Grid-Kachel.
- **Statischer Hilfetext auf Label-Ebene** (noch nicht implementiert, vorgesehen für Spec 0008): natives `<details>/<summary>` statt `title`-Attribut für kurze, unveränderliche Erklärungen zu einzelnen Werten/Labels (z.B. "Entfernt"/"Übersprungen" bei den Scan-Statistiken auf `ProjectDetailPage`). **Nicht `title` allein verwenden** — auf Touchgeräten meist nicht auslösbar, verletzt "Touch- und Tastatur-gleichwertig". `<details>` ist nativ touch-/tastatur-/screenreaderbedienbar, ohne neue Abhängigkeit, bleibt standardmäßig eingeklappt (kein Dauertext für wiederkehrende Nutzer, siehe "Verlässlichkeit statt Onboarding"). `<summary>` mit `underline decoration-dotted` als zusätzliche visuelle Andeutung neben der nativen Auslassungsmarkierung. Nur für tatsächlich erklärungsbedürftige Labels, nicht flächendeckend auf ein ganzes `<dl>` anwenden.
- **Info-Popover für situative Kurzerklärungen** (implementiert mit Spec 0040, Referenz `frontend/src/components/CriterionDetailsPopover.tsx` auf `components/ui/popover.tsx`): `i`-Trigger-Button (32px sichtbar, `tap-target-square` für die 44px-Trefferfläche, `aria-label` beschreibt den Zweck) öffnet einen Radix-`Popover` auf `--elevated` mit strukturiertem Erklärtext — Popover statt Tooltip, da Tooltips auf Touch nicht zuverlässig öffnen; Ausnahme von "Radix nur wo natives HTML nicht reicht", weil freie/floating Positionierung gebraucht wird (`<details>` würde stattdessen Inhalt verschieben). Öffnet per Klick/Tap überall, zusätzlich per Hover nur bei `matchMedia('(hover: hover) and (pointer: fine)')` (zur Interaktionszeit geprüft, nicht gecacht), mit Schutz gegen die Hover-vor-Klick-Falle. Standardlösung für jede Kurzerklärung, die mehr Fläche als ein Satz oder freie Positionierung braucht (sonst `<details>/<summary>`).
- **Sticky Stepper-Fortschrittsnavigation** (`components/Stepper.tsx`): horizontale `<nav><ol>`-Leiste, 5 Schritt-Marker à 32px sichtbar mit `tap-target-square` (44px Trefferfläche) und Radius 8px, Verbindungslinie dazwischen, `sticky top-0` mit `bg-bg/95 backdrop-blur-sm border-b border-border`, Abstand 12px zwischen den Markern (aufgespannte Trefferflächen). Vier Zustände, Farbe nie alleiniges Signal, zusätzlich als `data-step-state` im DOM: **erledigt** = Umriss und Häkchen in `--accent-2`; **aktuell** = voll gefüllt `--accent` mit `--accent-fg`, **fetter Schnitt** und `aria-current="step"` — über Schnitt UND Farbe, nie über Farbe allein; **ausstehend** = umrandeter Marker (`--border-control`) mit Schrittnummer, echter `<Link>`; **blockiert** = `--border`-Umriss, Schloss-Symbol und Beschriftung in `--text-muted`, kein `<Link>` (`aria-disabled` + `tabIndex={-1}`), Grund über den Info-Popover-Trigger statt Dauertext. „Aktuell" gewinnt gegen „erledigt" — wo man steht, ist die wichtigere Information; das Häkchen bleibt trotzdem sichtbar, und die Zustandsbenennung steht ohnehin im `aria-label`. Jedes Element mit vollem `aria-label` ("Schritt 2 von 5: …, erledigt"). Bleibt auf allen Breakpoints horizontal, Labels erst ab `sm:` sichtbar, darunter ersetzt durch eine Orientierungszeile über der Leiste. Erster Skip-Link im Produkt davor, damit Tastaturnutzung nicht durch alle 5 Einträge tabben muss.
- **Redirect statt disabled Deep-Link** (noch nicht implementiert, vorgesehen für Spec 0042 — Weiterentwicklung von "Nicht verfügbare Aktion" für Routen statt Sections): ruft jemand die Route eines noch nicht erreichbaren Pipeline-Schritts direkt auf (oder die Basis-Route ohne `:step`), wird auf den höchsten erreichbaren Schritt umgeleitet (`Navigate replace`, kein Toast) statt dort eine leere disabled-Ansicht zu zeigen. Kein stiller Bruch, da der blockierte Schritt in der Stepper-Leiste sichtbar + mit Grund abrufbar bleibt und der Redirect deterministisch ist (dieselbe URL → dasselbe Ziel).
- **Dauerhaft sichtbare Kostenschätzung am Auslöser** (umgesetzt; ersetzt das frühere Muster "Bestätigungsdialog vor kostenpflichtiger Aktion", das ausdrücklich zurückgenommen ist): Eine Aktion mit echtem externem Kostenrisiko (Cloud-Abrechnung) bekommt KEINEN Modal-Dialog, sondern eine Schätzung unmittelbar am Auslöser, dauerhaft sichtbar vor dem Klick — Fotoanzahl, geschätzter Betrag, plus expliziter Unsicherheitshinweis ("Schätzung, keine exakte Abrechnung"). Sie deckt ALLE Kostenanteile ab, die der Auslöser freigibt, nicht nur den auffälligsten. Eager beim Seitenaufruf laden (Eager-Zähler-Muster oben). Auslöse-Button bleibt disabled, solange die Schätzung nicht ladbar ist UND Kosten entstehen würden (kein Bypass); ist die kostenpflichtige Option abgewählt, ist die Schätzung keine Vorbedingung. "Bestätigung von Aktionen" gilt damit wieder nur für destruktive/schwer rückgängig zu machende Aktionen.
- **Checkbox für laufbezogene Freigabe neben Switch für Dauereinstellung** (umgesetzt, `components/ui/checkbox.tsx`): natives `<input type="checkbox">` mit `accent-color`, keine neue Abhängigkeit (analog `switch.tsx`); Touch-Ziel über das umschließende `<label>` (`min-h-11`), Klick auf den Text schaltet mit. Die Formwahl ist bedeutungstragend: `Switch` = dauerhafte Einstellung (z.B. Projekt-Einwilligung), `Checkbox` = Einmal-Entscheidung dieses Durchlaufs. Das laufbezogene Element kann die Erlaubnis nie ersetzen — ohne sie ist es abgewählt, deaktiviert und mit Verweis auf die Einstellung versehen.
- **Zustandsabhängige Datenschutz-Zusicherung** (umgesetzt): Eine Aussage wie "läuft vollständig lokal — kein Foto verlässt diesen Server" NIE absolut formulieren, wenn sie von einem Bedienzustand abhängt. An genau diesen Zustand binden, nur zeigen wenn zutreffend, im Gegenzustand die ebenso konkrete Gegenaussage. Eine unzutreffende Zusicherung ist kein Textfehler, sondern führt zu Entscheidungen auf falscher Grundlage.
- **Mehrfachkandidaten-Vergleich mit Override-Aktion** (noch nicht implementiert, vorgesehen für Spec 0055 — Kurskorrektur 2026-08-23, ersetzt den vorherigen Entwurf "Lokal-vs-Remote-Vergleich mit Override-Aktion", der noch von genau einer Remote-Kategorie pro Foto ausging): erweitert `CriterionDetailsList`/`CriterionDetailsPopover` um eine Gruppe **"Kategorie-Kandidaten"**, aber nur eingeblendet, wenn für ein Foto **mehr als ein** Kandidat existiert (lokal qualifizierende Kriterien + 0-3 offene Remote-Label zusammen) — bei nur einem Kandidaten bleibt die bestehende einzeilige "Kategorie"-Anzeige unverändert (kein Overhead im häufigsten Fall). Jeder Kandidat eine eigene Zeile, absteigend nach Score/Konfidenz sortiert, mit Label (einheitlicher `formatCategoryKey`-Fallback für lokal UND remote), Herkunft ("Lokal erkannt" oder Anbietername als Chip), Konfidenz (`formatCriterionPercent`) und genau einer von drei Statuszeilen: Hinweis-Chip "Aktuell" ohne Button (aktuell wirksam, kein Override) / Hinweis-Chip "Manuell übernommen" + Busy-Button "Zurücksetzen" (aktuelles Override-Ziel) / Busy-Button "Übernehmen" (`PUT .../category-override`, Body `{"category_key": "..."}`, weder aktuell wirksam noch Override-Ziel). Ein verwaister Override (Kandidat nicht mehr in der aktuellen Liste) bleibt als zusätzliche Zeile am Ende sichtbar statt zu verschwinden. Aktiver Override zusätzlich als dezenter Kachel-Marker (Stift-Symbol `✎` in halbtransparentem `--bg`-Kreis, gleiche Backdrop-Technik wie der `CriterionDetailsPopover`-Trigger, `aria-label="Kategorie manuell übersteuert"`) direkt auf der Grid-/Kuratierungskachel sichtbar, ohne Popover öffnen zu müssen. Bewusst **kein** Skeleton-Backfill wie beim Verwerfen-Muster: das Foto wechselt sichtbar in seine neue Cluster×Kategorie-Sektion — das ist die gewollte Rückmeldung, keine Positionsstabilität nötig.
- **Auffangkorb-Kategorie mit erklärend dezentem Signal** (implementiert, Referenz `frontend/src/pages/CurateCategoriesPage.tsx`): eine Kategorie, die kein Erkennungsergebnis ausdrückt, sondern dessen Fehlen (`"unerkannt"` → "Nicht erkannt"), steht innerhalb ihrer Gruppierungsebene **immer zuletzt** (exportierte, unit-getestete reine Sortierfunktion `sortCategoryKeys` statt Sortier-Ausdruck im JSX) und trägt einen kurzen strukturellen Hinweistext direkt unter der Überschrift. **Keine Fehler-Optik**: kein `Alert`, kein `role="alert"`, keine Fehlerfarbe, kein Icon/Badge — das Fehlen einer Erkennung ist kein Fehler. Kachel-Ebene (Grid, Marker, Buttons) bleibt identisch zu jeder normalen Kategorie.
- **Feinlabel-Chips als visuelle Zusatzkennzeichnung, unterschieden von Kategorie-Badges** (neu mit Spec 0289, noch nicht implementiert): zusätzlich zur Pflicht-Kategorie werden bis zu zwei frei formulierte Feinlabels am Foto angezeigt (z.B. "Urlaub", "Blüte"). Sie sind Zusatzinformation, keine kategoriale Einordnung, und müssen visuell klar unterschieden werden. Praktisch: verwende einen unterschiedlichen `tone` (z.B. `tone="secondary"`) oder Styling-Signal (umrandet statt gefüllt, kleinere Größe, subtilere Farbe) als die Kategorie-Badge (`tone="neutral"`). Platziere Feinlabel-Chips räumlich deutlich getrennt (separate Zeile, unter/neben, nicht direkt nebeneinander), damit keine Verwechslung als "Kategorie + Unterkategorie"-Paar entstehen kann. **Auch bei „Nicht erkannt"**: Feinlabels sichtbar lassen — wichtig für die Häufigkeitsauswertung zum Erkennen fehlender Kategorien. Kein Icon/Symbol auf Feinlabel-Chips (um sie nicht mit Bewertungs-Symbolen zu verwechseln).

## Barrierefreiheit

- Interaktive Elemente mit Symbolen bekommen `aria-label`, nicht nur ein Icon ohne Text-Alternative. **Ein Symbol ersetzt nie ein Label, es begleitet es** — `Icon` ist deshalb standardmäßig `aria-hidden`.
- Formularfelder mit erkennbarem Zweck bekommen den passenden `autocomplete`-Wert (z.B. `username`, `current-password`).
- Zentrale Abläufe vollständig per Tastatur bedienbar, mit sichtbarem Fokus (die eine globale Regel, siehe oben).
- **Kontrast gegen die Fläche, auf der das Element tatsächlich steht** — nicht gegen die, für die das Token gedacht war. Besonders bei Text, der auf `--elevated` oder `--overlay` landet statt auf `--bg`.
- **„Gedrückt" ist ein Pflichtzustand** jedes Bedienelements: Touch hat keinen Hover.
- **Trefferfläche ≥44×44 CSS-px**, sichtbar ≥32px; auf dem heißen Pfad am Telefon sichtbar ≥44px. Die vier Aufspannungsregeln oben gelten immer.
- **Kein Zustand nur über Farbe** — Bewertungen, Prozessstatus und Stepper-Stufen tragen zusätzlich Symbol, Text, Schnitt oder Position.
- Kein systematisches Screenreader-Testing nötig (zwei bekannte Nutzer, kein Enterprise-Anspruch) — semantisches HTML + Labels reichen als Mindeststandard.
- **Bekannte Lücken, nicht neu erzeugen:** `StatusDot` und `QualityMeter` haben keine achromatische Eigenunterscheidung; sie sind bewusst **begleitend** zu einem Text daneben, nie alleintragend. Neue Stellen dieser Art sind nicht zulässig.

## Beim Testen: Selektor-Stabilität

Tests selektieren über `getByRole`/`getByLabelText`/`aria-*`/semantische `data-*`-Attribute (`data-suggested`, `data-status`, `data-icon`, `data-step-state`, `data-category-key`, `data-struck`) — **nie** über CSS-Klassennamen oder Snapshots. Beim Einbau/Ändern einer Komponente mit UI-Bibliothek: bestehende Rollen/Labels/`data-*`-Attribute erhalten, damit Tests ohne Assertion-Anpassung grün bleiben. Ändert sich zwangsläufig eine Rolle (z.B. natives `<button>` → Radix-Trigger mit anderer impliziter Rolle), das im PR explizit benennen.

## Sicherheit: kein `dangerouslySetInnerHTML`

Datei-/Ordnernamen aus OpenCloud sind außerhalb der Anwendung entstandener Text. Immer als React-Kinder (Text) übergeben, **nie** über `dangerouslySetInnerHTML` oder als HTML-String-Prop an eine shadcn/ui- oder Radix-Komponente — auch nicht bei neuen Tooltip-/Dialog-/Popover-Komponenten. Siehe `specs/architecture/0003-securitykonzept.md`, Abschnitt "Angriffsflächen → Frontend".

## Was statisch geprüft wird (und deshalb nicht verhandelbar ist)

`frontend/src/designSystem.contract.test.ts` ist die **einzige** Testebene mit CSS-Assertions — Komponententests bekommen bewusst keine, sie würden die nächste gestalterische Überarbeitung nicht überleben. Der Test schlägt fehl bei:

- einem Text-/Symbol-/Umrisswert, der gegen seine tatsächliche Fläche unter der Schwelle liegt (vollständige Matrix, selbst gerechnet);
- einem gestrichenen Token oder einer gestrichenen Utility irgendwo in `frontend/src/**`, `index.html` oder `vite.config.ts` (beide Schreibweisen: CSS-Variable **und** Utility);
- `text-danger`, `border-border` in einem Bedienelement-Primitive, `text-text-disabled` ohne Disabled-Variante;
- `focus-visible:`/`ring-offset`/`outline-none` in einer `.tsx`, mehr als einer `:focus-visible`-Regel in `index.css`;
- `text-text-muted`/`text-danger-text` auf der gedrückten Fläche `bg-border`;
- `rounded-full` außerhalb der abschließenden Liste;
- einem `lucide-react`-Import außerhalb von `ui/icon.tsx`, einem Namespace-Import oder einem berechneten Zugriff auf das Paket-Objekt;
- einem zusammengebauten Klassennamen in `badge.tsx`/`icon.tsx`/`CategoryBadge.tsx`;
- einem `className`, das Trefferflächen-Utility und `overflow-hidden` zugleich trägt;
- einer `hover:`-Variante ohne `active:`-Variante in `components/ui/`;
- einer verwendeten Design-Utility, die beim echten Tailwind-Lauf **keine Regel** erzeugt (eine unbekannte Utility ist in Tailwind kein Buildfehler, sondern erzeugt still gar nichts — genau die Fehlerart, die ein grüner Build sonst durchwinkt).

Neue Werte, neue Chip-Kategorien und neue Vordergrund-Tokens dort in die Matrix aufnehmen, nicht daran vorbeibauen.

**Was der Test NICHT findet:** jsdom hat keine Layout-Engine. Tatsächlich gerenderte Größen, Abstände zwischen aufgespannten Trefferflächen, ein beschneidender *Vorfahre*, eine verschwundene Fläche, ein Umbruch bei 360px und die visuelle Unterscheidbarkeit von Auswahl und Fokus bleiben Sache der Sichtprüfung in Telefon- und Desktopbreite.

## Bei Abweichungen

Erweist sich beim Bauen einer Komponente ein hier festgehaltener Wert/ein hier festgehaltenes Muster als unpraktisch, oder wird eine neue Design-Entscheidung nötig: zuerst `specs/architecture/0004-design-system.md` aktualisieren (das ist die Aufgabe des `ux-ui-designer`-Agenten bei Review/Umsetzung), danach diesen Skill nachziehen — nie stillschweigend im Code abweichen, ohne das Dokument nachzuführen.
