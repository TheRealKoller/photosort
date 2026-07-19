# Design-System

**Status:** Living Document (kein Lifecycle, wird laufend aktualisiert)
**Letzte Aktualisierung:** 2026-07-19 (initial angelegt im Zuge der UI/UX-Verfeinerung von [`features/0002-manual-categorization.md`](../features/0002-manual-categorization.md) — erstes Feature mit sichtbarer Oberfläche)

## Ausgangslage

Das Frontend ist zum Zeitpunkt der Anlage dieses Dokuments reines Vite-Scaffold ohne eigene UI-Komponenten (`frontend/src/App.tsx` zeigt nur einen Platzhaltertext). `index.css` und `public/favicon.svg` enthalten unveränderte Reste des Vite/Template-Ausgangszustands (u.a. lila Akzentfarbe `#aa3bff`/`#863bff`, `#social`/`.button-icon`-Regeln ohne Bezug zu PhotoSort). Dieses Dokument ist deshalb bewusst schlank und als Ausgangspunkt zu verstehen, nicht als abschließendes System — es wird mit den ersten echten Komponenten (Spec 0002) verfeinert und korrigiert, wo sich Annahmen als unpraktisch erweisen.

Noch keine Komponentenbibliothek gewählt. Eine solche Wahl ist eine externe Abhängigkeit und läuft über `architect`/ADR (`specs/decisions/`) — dieses Dokument trifft dazu keine Entscheidung, sondern hält nur fest, was ohne Bibliothek an Grundbausteinen gebraucht wird.

## Designprinzipien

Für genau zwei bekannte, wiederkehrende Nutzer (Daniel und seine Frau) statt eines anonymen Publikums:

- **Durchsatz vor Erklärung.** Kernaufgabe ist das zügige Durchsehen von potenziell tausenden Fotos. Jede zusätzliche Interaktion (Klick, Ladezeit, Bestätigungsdialog) pro Foto multipliziert sich spürbar — Bedienung so knapp wie möglich halten (z.B. Tastatur-Shortcuts, direktes Tap-Feedback statt Zwischenschritten).
- **Verlässlichkeit statt Onboarding.** Da die Nutzer das Werkzeug wiederholt nutzen, keine Erklärtexte/Tutorials, die beim zweiten Mal stören — stattdessen stabile, gleichbleibende Interaktionsmuster (gleiche Taste macht immer dasselbe, gleiche Position für gleiche Aktion).
- **Bewertungsstufen auf einen Blick unterscheidbar.** Favorit/Album-würdig/Verworfen/unbewertet müssen sich per Farbe und Symbol unterscheiden, nicht nur per Text — wichtig bei kleinen Grid-Kacheln.
- **Touch- und Tastatur-gleichwertig.** PWA-Nutzung auf Mobilgeräten ist kein Nebenfall, sondern gleichrangig zur Desktop-Nutzung mitzudenken.
- **Ehrliche Ladezustände statt Warten erzwingen.** Wo Daten (Thumbnails, Bewertungen) noch nicht bereit sind, wird das sichtbar gemacht statt den Nutzer blockierend warten zu lassen (siehe `architecture/0001-overview.md`: Bild-Endpunkt liefert 404 statt zu warten).

## Grundbausteine

- **Komponentenbibliothek:** keine gewählt. Views werden vorerst mit React + plain CSS gebaut. Falls sich beim Bau der Grid-Ansicht (Spec 0002) Bedarf an Virtualisierung für tausende Kacheln zeigt, ist das ein Kandidat für eine ADR, keine Design-System-Entscheidung.
- **Farbpalette:** Die bestehenden CSS-Variablen in `frontend/src/index.css` (`--text`, `--text-h`, `--bg`, `--border`, `--accent`, jeweils mit Dark-Mode-Variante über `prefers-color-scheme`) sind brauchbare neutrale Basis und werden übernommen. Die lila Akzentfarbe (`--accent: #aa3bff` / dark `#c084fc`) ist unreflektierter Template-Rest, keine bewusste Markenentscheidung — wird vorerst als neutraler Akzent (z.B. aktiver Filter, Fokus-Ring) weiterverwendet, kann aber jederzeit ohne Produktauswirkung geändert werden.
  - **Semantische Bewertungsfarben** (neu, für Spec 0002 festgelegt):
    - `favorite`: warmer Gold-/Gelbton (z.B. `#d9a441` hell / `#f0c674` dunkel) + Stern-Symbol
    - `album_worthy`: Grünton (z.B. `#3f9142` hell / `#7fce82` dunkel) + Haken-Symbol
    - `rejected`: Rotton (z.B. `#c94f4f` hell / `#e08080` dunkel) + Kreuz-Symbol
    - `unbewertet`: neutral, `--border`-Farbe, kein Symbol (bewusst unauffällig — Aufmerksamkeit soll auf bewerteten/zu bewertenden Fotos liegen)
    - Alle vier Farben gegen `--bg` (hell/dunkel) auf mind. WCAG-AA-Kontrast (4.5:1 für Text/Symbole) geprüft, siehe Barrierefreiheit unten.
- **Typografie:** bestehender `--sans`-Stack (`system-ui, 'Segoe UI', Roboto, sans-serif`) übernehmen, keine Web-Fonts nachladen (Performance, PWA/Mobilfunk).
- **Spacing-Skala:** noch nicht etabliert, wird mit Spec 0002 eingeführt: 4px-Basis (4/8/12/16/24/32px), passend zu den bereits genutzten Werten in `index.css` (z.B. `margin: 32px 0`).
- **Touch-Ziele:** mindestens 44×44px für interaktive Elemente (Bewertungs-Buttons, Navigationspfeile) — Standard-Empfehlung für zuverlässige Touch-Bedienung auf Mobilgeräten.

## Wiederkehrende Muster

Werden mit Spec 0002 erstmals konkret gebraucht und hier als Ausgangspunkt festgehalten (nicht abschließend):

- **Ladezustand:** Skeleton-/Platzhalter-Kacheln statt Spinner-Vollbild, wo Inhalte schrittweise eintrudeln (Grid); dezenter Inline-Indikator, wo einzelne Bilder nachladen (Einzelbild-Ansicht).
- **Fehlerzustand:** inline, kontextnah (z.B. Banner über der betroffenen Ansicht mit "Erneut versuchen"), nicht die ganze App blockierend.
- **Leerer Zustand:** kurzer erklärender Text + ggf. Handlungsoption (z.B. "Keine Fotos mit diesem Filter — Filter zurücksetzen"), kein leeres Nichts.
- **Noch nicht verarbeiteter Inhalt** (z.B. Thumbnail vom Worker noch nicht erzeugt, Backend liefert 404): generischer Bild-Platzhalter mit klarer Kennzeichnung "wird noch verarbeitet", kein endloser Spinner, keine blockierte Navigation.
- **Bestätigung von Aktionen:** bei schnellen, jederzeit korrigierbaren Aktionen (z.B. Bewertung setzen) genügt direktes visuelles Feedback (Farbwechsel der Kachel/des Buttons) ohne zusätzlichen Bestätigungsdialog — Bestätigungsdialoge nur für destruktive, schwer rückgängig zu machende Aktionen.

## Barrierefreiheit

Angemessenes Maß für ein privates Zwei-Nutzer-Projekt, kein Enterprise-Anspruch:

- Kontrastverhältnis Text/Symbole gegen Hintergrund mind. WCAG-AA (4.5:1), da auch das bestehende Farbschema hell/dunkel das schon weitgehend erfüllt.
- Zentrale Abläufe (Einzelbild-Ansicht: bewerten, navigieren) vollständig per Tastatur bedienbar — ergibt sich ohnehin aus dem Shortcut-Akzeptanzkriterium in Spec 0002, wird hier als generelle Anforderung an alle zukünftigen interaktiven Ansichten festgehalten.
- Interaktive Elemente mit Symbolen (z.B. Bewertungs-Buttons) bekommen `aria-label`, nicht nur ein Icon ohne Text-Alternative.
- Kein systematisches Screenreader-Testing vorgesehen (Aufwand steht in keinem Verhältnis zu zwei bekannten Nutzern) — Grundstruktur (semantisches HTML, Labels) reicht als Mindeststandard.

## Bekannte Lücken

- Keine Komponentenbibliothek/kein Styling-System über plain CSS hinaus gewählt — bei wachsender View-Zahl ggf. Thema für `architect`.
- `index.css`/`favicon.svg` enthalten Template-Reste ohne Bezug zu PhotoSort (lila Branding, `#social`-Regeln) — Aufräumen ist noch nicht passiert, aktuell unkritisch, da noch keine echten Views existieren.
- Spacing-Skala und Bewertungsfarben sind mit diesem Dokument neu festgelegt, aber noch durch keine tatsächliche Implementierung geprüft — werden beim Bau von Spec 0002 voraussichtlich noch angepasst.
