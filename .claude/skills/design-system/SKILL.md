---
name: design-system
description: Kapselt PhotoSorts Design-System (Farben, Formsprache, wiederkehrende UI-Muster) und die gewählte Komponentenbibliothek (Tailwind CSS + Radix UI + shadcn/ui) für konsistente Frontend-Arbeit. Nutze diesen Skill IMMER, wenn an Code in frontend/src/ gearbeitet wird — neue oder geänderte React-Komponenten/Views, Styling, Farb-/Abstandsentscheidungen — oder wenn Design-System-Konformität geprüft/reviewt werden soll, auch wenn die Worte "Design-System"/"UI/UX" nicht explizit fallen (z.B. "bau eine neue Ansicht", "style diese Komponente", "mach das ansprechender", "review das Frontend").
---

# PhotoSort Design-System

Schnellreferenz für konsistente UI-Arbeit in diesem Repo. Die eigentliche Quelle der Wahrheit sind [`specs/architecture/0004-design-system.md`](../../../specs/architecture/0004-design-system.md) (lebendes Dokument, gepflegt vom `ux-ui-designer`-Agenten) und [`specs/decisions/0011-ui-component-library.md`](../../../specs/decisions/0011-ui-component-library.md) — bei Unsicherheit oder Widerspruch dort nachschlagen statt zu raten, dieser Skill ist nur die griffige Zusammenfassung für den täglichen Gebrauch.

## Warum dieser Skill existiert

Das Design-System-Dokument ist lang und wächst mit jeder Spec weiter — beim eigentlichen Bauen einer Komponente will man nicht jedes Mal das ganze Dokument durchsuchen. Dieser Skill liefert die Werte/Muster, die in praktisch jeder Frontend-Änderung gebraucht werden, direkt griffbereit. Er dupliziert das Dokument nicht als Kopie — bei einer Design-Entscheidung, die hier nicht abgedeckt ist, ins Dokument schauen und diesen Skill danach ergänzen, statt im Code zu raten.

## Designprinzipien (Kurzform)

- **Warm & persönlich statt neutral/business-artig.** Familien-Urlaubsfotos, kein Dashboard-Gefühl.
- **Die Fotos sind der Star, nicht die Oberfläche.** Chrome-Flächen zurückhaltend, Farbintensität auf Bedienelemente/Status begrenzt, nicht auf große Flächen.
- **Durchsatz vor Erklärung.** Kernaufgabe ist zügiges Durchsehen potenziell tausender Fotos — jede zusätzliche Interaktion pro Foto multipliziert sich. Kein Onboarding/Tutorial-Text, der beim zweiten Mal stört.
- **Bewertungsstufen auf einen Blick unterscheidbar.** Per Farbe UND Symbol, nicht nur Text — wichtig bei kleinen Grid-Kacheln.
- **Touch und Tastatur gleichrangig.** PWA-Nutzung auf Mobilgeräten ist kein Nebenfall.
- **Ehrliche Ladezustände statt erzwungenes Warten.** Sichtbar machen, was noch lädt/nicht bereit ist, statt zu blockieren.

## Farbpalette (Design-Tokens)

Aktueller Stand aus `architecture/0004-design-system.md` — bei Änderungen dort zuerst aktualisieren, dann hier nachziehen:

- **Akzentfarbe (Terracotta):** `--accent: #bb4e2a` hell / `#e8916d` dunkel — Buttons, Links, Fokus-Ring, aktive Filter. **Hinweis:** der ursprüngliche Zielwert `#d97757` (hell) erreichte als Text-/Link-Farbe gegen den warmen Hintergrund nur 2.92:1 (< WCAG-AA 4.5:1) und wurde auf `#bb4e2a` (4.64:1, gleicher Farbton/Sättigung, nur dunkler) abgedunkelt — siehe `architecture/0004-design-system.md`. Getrennt von den Bewertungsfarben halten, damit Aktion und Status nicht verwechselbar sind. Für Text/Symbole AUF `--accent` (z.B. Button-Beschriftung) `--accent-fg` verwenden (`#fdfbf8` hell / `#140f0c` dunkel), nicht `--chip-fg`.
- **Neutraltöne:** hell `#faf7f2` (bg) / `#e8e0d5` (border); dunkel `#1f1b18` (bg) / `#35302b` (border) — warme Creme-/Sandtöne, nicht kühles Weiß/Grau.
- **Bewertungsfarben** (unverändert seit Spec 0002, bewusst nicht an die Terracotta-Richtung angepasst — Gold/Grün/Rot sind gelernte Ampel-Signalfarben):
  - `favorite`: `#d9a441` hell / `#f0c674` dunkel + Stern-Symbol
  - `album_worthy`: `#3f9142` hell / `#7fce82` dunkel + Haken-Symbol
  - `rejected`: `#c94f4f` hell / `#e08080` dunkel + Kreuz-Symbol
  - unbewertet: neutrale Border-Farbe, kein Symbol (bewusst unauffällig)
  - **Wichtig:** diese vier Hex-Werte NIE direkt als Text-/Symbolfarbe auf `--bg` verwenden — im Hellmodus erreichen sie dort nur 2.10–4.17:1 (< 4.5:1). Bei **voller Chip-Füllung** (entschiedene Bewertung) `--chip-fg` (`#000000`, ein einheitliches nahezu-schwarzes Ink für alle vier Farben/beide Modi, 4.71:1–8.71:1) als Symbolfarbe verwenden. Beim **gedämpften Vorschlags-Zustand** (10%-Deckkraft-Tint auf `--bg`, nicht auf der vollen Farbe) dagegen `--text-h` verwenden, nicht `--chip-fg` — `--chip-fg` ist modusunabhängig und wäre im Dunkelmodus gegen den dann ebenfalls dunklen `--bg`-Tint praktisch unsichtbar. Siehe `components/ui/badge.tsx`.
- **Prozess-Status-Farben** (running/success/failed — für Hintergrundprozesse wie Scan/Scoring, nicht Bewertungen): `success`/`failed` teilen sich die Töne mit `album_worthy`/`rejected`, `running` ist neutraler Akzent-Ton + rotierendes Icon. Gilt dieselbe Chip-Regel wie oben — Ausnahme nur für rein dekorative, `aria-hidden`-Icons mit redundantem Text daneben (dann reicht 3:1 statt 4.5:1, siehe `Alert`-Komponente).
- Alle Farben gegen den jeweiligen Hintergrund auf WCAG-AA (4.5:1 für Text/Symbole) prüfen — nicht rechnerisch annehmen, siehe die beiden offenen Lücken oben.

## Formsprache & Spacing

- **Radius:** 8px Standard (Buttons, Inputs), 12px für Karten/Dialoge — gemäßigt, kein Pill-Design.
- **Schatten:** dezent für Karten ("aufgelegtes Foto"). Im Dark Mode Rahmen statt Schatten verwenden (Schatten wirken auf dunklem Grund kaum/unsauber).
- **Spacing-Skala:** 4px-Basis — 4/8/12/16/24/32px, keine beliebigen Zwischenwerte.
- **Touch-Ziele:** mindestens 44×44px für jedes interaktive Element.

## Komponentenbibliothek: Tailwind CSS + Radix UI + shadcn/ui

Siehe ADR [`decisions/0011-ui-component-library.md`](../../../specs/decisions/0011-ui-component-library.md) für die volle Begründung. Praktisch relevant:

- **shadcn/ui-Komponenten werden als Quellcode kopiert**, nicht als npm-Paket installiert — sie leben in `frontend/src/components/ui/` und sind normaler, editierbarer App-Code. Neue wiederkehrende UI-Bausteine (Button, Card, Badge, Progress, …) dort ablegen statt pro View neu zu erfinden.
- **Radix-Primitives nur dort einsetzen, wo natives HTML nicht reicht** (z.B. Dialog, Popover). Für Buttons/Formulare/Listen bleibt natives HTML + Tailwind-Klassen der Standard — kein `div`-Onclick, keine unnötige Abstraktion über ein natives `<button>`.
- **Utility-Klassen direkt in JSX**, keine neue CSS-in-JS-Laufzeit, keine `styled-components`-artige Abstraktion — widerspräche der Bundle-Size-Begründung der ADR.
- **`Button`, `variant="link"`:** die kompakten `link`-Klassen (`p-0 h-auto min-h-0 min-w-0`) sind über `compoundVariants` gegen die Größen-Klassen (`h-11 min-w-11 px-4 py-2`) abgesichert, mit Regressionstest — kein weiteres Prüfen vor dem Einsatz nötig.
- **`Button`, `asChild` + `disabled`:** blockiert echte Interaktion über `pointer-events-none` + `tabIndex={-1}` (nicht nur `aria-disabled`), da das native `disabled`-Attribut nicht an beliebige Kind-Elemente wie `<a href>`/`Link` gebunden werden kann und ein reiner `preventDefault()`-Handler bei `react-router`-`Link` zu spät käme (Radix `Slot` ruft immer zuerst den Handler des Kindes auf).

## Wiederkehrende Muster

- **Busy-Button:** während einer laufenden Anfrage/eines laufenden Hintergrundprozesses wird der auslösende Button `disabled` (nicht ausgeblendet) und zeigt Spinner-Icon und/oder veränderten Label-Text. Gilt für **jeden** auslösenden Button im Produkt, nicht nur für neue.
- **Skeleton-Ladezustand:** warm-neutrale Platzhalterblöcke mit dezentem Puls (kein Shimmer) statt Text wie "Lädt…", wo Inhalte schrittweise eintrudeln (Grid, Listen). Für einzelne nachladende Bereiche reicht ein dezenter Inline-Indikator.
- **Vorschlags-Badge:** volle Füllung = von einem Menschen entschieden, Umrandung + 10–12% Deckkraft-Fläche = maschineller Vorschlag, noch offen. `aria-label` immer mit Präfix "Vorschlag: …", nie nur der Stufenname.
- **Fehlerzustand:** inline, kontextnah (Banner über der betroffenen Ansicht) mit "Erneut versuchen"-Button, nie die ganze App blockierend. Backend-`detail`-Text wörtlich anzeigen, nicht umformulieren.
- **Standalone vs. App-Shell:** Bildschirme ohne bestehenden Session-Kontext (aktuell nur Login) laufen als eigenständiger, zentrierter Kartenbereich ohne App-Shell-Kopfzeile. Beide Varianten wrappen den Seiteninhalt in ein `<main>`-Landmark.
- **Bestätigung von Aktionen:** nur für destruktive, schwer rückgängig zu machende Aktionen — bei schnellen, korrigierbaren Aktionen (Bewertung setzen, Logout) reicht direktes visuelles Feedback ohne Dialog.
- **Nicht verfügbare Aktion (Feature-Flag/Vorbedingung)** (noch nicht implementiert, vorgesehen für Spec 0024, rein lokale Kategorie-/Top-Foto-Auswahl ohne Cloud-Anbindung, siehe `decisions/0015-lokale-kategorie-klassifikation.md`): anders als Busy-Button (vorübergehend beschäftigt) bleibt der Bereich sichtbar, aber dauerhaft/bedingt `disabled` (Konfig-Schalter `category_selection_enabled` aus, oder Phase-A-Lauf fehlt), mit neutralem Erklärtext darunter (kein `Alert`, da kein Fehler) — nach Möglichkeit proaktiv aus bereits geladenen Daten abgeleitet, nicht erst nach einem fehlgeschlagenen Request.
- **Kategorie-Kennzeichnung** (noch nicht implementiert): zweiter, von `RatingBadge` getrennter `Badge tone="neutral"`-Chip (keine Bewertungsfarbe) für **3** Kategorien (Landschaft/Detailaufnahme/Menschen, Kürzel L/D/M — "Sehenswürdigkeit" entfällt für v1, lokal nicht erkennbar), auf der Grid-Kachel als Kürzel in der Gegenecke zur Rating-Badge, ausgeschriebener Name nur als `aria-label`/`title`.
- **Grobe Qualitäts-Einordnung statt Rohwert** (noch nicht implementiert): kein numerischer Score — stattdessen 3 Stufen ("Einfache"/"Gute"/"Hohe Bildqualität") aus dem bestehenden `local_quality_score` abgeleitet, dargestellt als neutrales Drei-Punkte-Meter (`●●●`/`●●○`/`●○○`, `aria-hidden`) + ausgeschriebener Stufenname als eigentlicher Text. Kein Stern-Symbol (Kollision mit `favorite`-★), keine Prozess-Status-Farbe. Nur in der Detailansicht, nicht auf der Grid-Kachel.

## Barrierefreiheit

- Interaktive Elemente mit Symbolen bekommen `aria-label`, nicht nur ein Icon ohne Text-Alternative.
- Formularfelder mit erkennbarem Zweck bekommen den passenden `autocomplete`-Wert (z.B. `username`, `current-password`).
- Zentrale Abläufe vollständig per Tastatur bedienbar.
- Kein systematisches Screenreader-Testing nötig (zwei bekannte Nutzer, kein Enterprise-Anspruch) — semantisches HTML + Labels reichen als Mindeststandard.

## Beim Testen: Selektor-Stabilität

Tests selektieren über `getByRole`/`getByLabelText`/`aria-*`/semantische `data-*`-Attribute (`data-suggested`, `data-status`) — **nie** über CSS-Klassennamen oder Snapshots. Beim Einbau/Ändern einer Komponente mit UI-Bibliothek: bestehende Rollen/Labels/`data-*`-Attribute erhalten, damit Tests ohne Assertion-Anpassung grün bleiben. Ändert sich zwangsläufig eine Rolle (z.B. natives `<button>` → Radix-Trigger mit anderer impliziter Rolle), das im PR explizit benennen.

## Sicherheit: kein `dangerouslySetInnerHTML`

Datei-/Ordnernamen aus OpenCloud sind außerhalb der Anwendung entstandener Text. Immer als React-Kinder (Text) übergeben, **nie** über `dangerouslySetInnerHTML` oder als HTML-String-Prop an eine shadcn/ui- oder Radix-Komponente — auch nicht bei neuen Tooltip-/Dialog-/Popover-Komponenten. Siehe `specs/architecture/0003-securitykonzept.md`, Abschnitt "Angriffsflächen → Frontend".

## Bei Abweichungen

Erweist sich beim Bauen einer Komponente ein hier festgehaltener Wert/ein hier festgehaltenes Muster als unpraktisch, oder wird eine neue Design-Entscheidung nötig: zuerst `specs/architecture/0004-design-system.md` aktualisieren (das ist die Aufgabe des `ux-ui-designer`-Agenten bei Review/Umsetzung), danach diesen Skill nachziehen — nie stillschweigend im Code abweichen, ohne das Dokument nachzuführen.
