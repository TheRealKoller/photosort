# 0321 - Design-System "Dark Utility Register": Ansichten nachziehen (Stufe 2)

**Status:** Implemented ([PR #337](https://github.com/TheRealKoller/photosort/pull/337))
**Erstellt:** 2026-09-05
**Bezug:** [Issue #321](https://github.com/TheRealKoller/photosort/issues/321)

## Ziel

Stufe 2 der zweistufigen Ablösung des Design-Systems. Stufe 1 ([`0320`](./0320-dark-utility-register.md), umgesetzt und gemergt) hat die Farbwelt, die Schriften, das Raster, die Grundelemente und den Symbolsatz getauscht — aber die **Formsprache** der Ansichten ist die alte geblieben: großzügige Abstände, runde Radien und Pillenformen, verteilt als Einzelentscheidungen in den Komponenten. Das Ergebnis ist bedienbar und lesbar, aber sichtbar uneinheitlich.

Dieser Zustand war ausdrücklich als **vorübergehend** akzeptiert, nicht als Endzustand. Diese Spec löst ihn auf und zieht die Ansichten gestalterisch auf das Board nach. Es drängt aus zwei Richtungen: Je länger der Zwischenzustand steht, desto mehr Neubau wächst hinein — die bereits akzeptierten Stories [`0044`](./0044-projekte-loeschen.md) und [`0058`](./0058-cloud-vision-status-transparenz.md) warten bewusst darauf, damit sie nicht zweimal durchs Design wandern. Und die Vorlage samt Begründungen ist jetzt frisch; später müsste sie sich jemand neu erarbeiten.

**Vorlage:** Board `photosort-design-system` (Stand V1.2) in der Figma-Datei "Photosort Dark", abgeschrieben als lebendes Dokument in [`specs/architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md). Das Board ist ein Desktop-Entwurf (2400px breit). PhotoSort ist auch eine mobile PWA — für Trefferflächen gilt die Projektregel als Untergrenze, auch wo die Maße des Boards darunter liegen.

## User Story

Als Nutzer von PhotoSort möchte ich eine durchgängig einheitlich gestaltete Oberfläche bedienen, damit die Anwendung in langen Sichtungssitzungen als ein Werkzeug wirkt und nicht als halb umgebaute Baustelle.

## Zuschnitt

**Alle Ansichten in einem Durchgang**, ein Pull Request: Anmeldung, Projektliste (inkl. Leerzustand), Projekt anlegen, Projekt-Einstellungen, Projekt-Statistik, die fünf Pipeline-Schritte, Kategorie-Kuratierung, Foto-Raster, Foto-Detail, Foto-Vergleich. Dazu die Bewertungsleiste und die Foto-Karte, die im Board eigene Zustände haben.

Bewusst gegen die Empfehlung entschieden, je Ansicht einen eigenen PR zu schneiden. Die Konsequenz ist bekannt und getragen: Die Sichtprüfung umfasst wieder alle Ansichten in zwei Breiten auf einmal — genau der Punkt, der bei Stufe 1 zuletzt offen blieb.

## Akzeptanzkriterien

### Gestaltung

- [ ] Alle Ansichten folgen der Formsprache des Boards: kompakte Maße, die Radienskala des Fundaments, die Abstände des 8-Punkt-Rasters. Runde Pillenformen bleiben nur an der bereits abschließend festgelegten Liste.
- [ ] Die Foto-Karte trägt die vier Zustände des Boards, die im Produkt vorkommen: neu, Favorit, Album-würdig, aussortiert — jeweils mit Textkennzeichen und eigenem Symbol. Der fünfte Board-Zustand "ausgewählt" ist von Daniel bewusst zurückgestellt (siehe "Entscheidungen"), weil PhotoSort heute keine Foto-Auswahl kennt.
- [ ] Der aussortierte Zustand ist ohne Farbwahrnehmung erkennbar: abgesenkte Deckkraft der Karte **und** durchgestrichener Dateiname.
- [ ] Die Bewertungsleiste folgt dem Board, mit sichtbarer Beschriftung je Eintrag und einem Kästchen, das die zugehörige Taste zeigt.
- [ ] Die Schrittnavigation trägt die drei Zustände des Board-Navigationselements (ruhend, überfahren, aktiv).
- [ ] Dekorative Trennlinien und Statuspunkte sind wieder als solche erkennbar — heute verschwinden mehrere davon praktisch auf dem Grund. **Nachweis:** An den im UI/UX-Abschnitt aufgezählten Stellen steht `--separator` (≥ 2,0:1 gegen `--bg` und `--surface`, in der Kontrastmatrix des Vertragstests nachgerechnet), und es verbleibt dort kein `--border` und kein Deckkraft-Modifikator auf einer Farb-Utility.
- [ ] Der unbestimmte Ladezustand der Fortschrittsanzeige folgt dem Board statt der Browser-Voreinstellung. **Nachweis zweistufig:** Der Vertragstest belegt über den tatsächlichen Tailwind-Lauf, dass die Zustandsbehandlung eine Regel erzeugt (eine unbekannte Variante ist in Tailwind kein Buildfehler und bliebe still wirkungslos); die Darstellung selbst ist Sichtprüfung im Browser.

### Keine funktionalen Verluste

- [ ] Jede Ansicht bleibt funktional identisch: gleiche Inhalte, gleiche Anzahl Elemente, gleiche Interaktionen. Es wird nichts entfernt und nichts hinzugefügt — mit der einen benannten Ausnahme (Dateiname auf der Fotokachel). **Nachweis:** Der bestehende `vitest`-Satz läuft am Ende jedes Etappen-Teilschritts vollständig grün, **ohne dass eine bestehende Testdatei geändert wurde**. Jede dennoch geänderte Testdatei ist in der PR-Beschreibung mit Grund aufgeführt.
- [ ] Die bestehenden Tastenkürzel bleiben unverändert belegt; sie werden lediglich sichtbar gemacht. Das sichtbare Kästchen eines Eintrags zeigt genau die Taste, die diese Bewertung tatsächlich auslöst (in `PhotoDetailPage.test.tsx` über alle drei Tasten geprüft); der zugängliche Name der Schaltfläche bleibt exakt `Favorit` / `Album-würdig` / `Verwerfen`.
- [ ] Alle Ansichten bleiben in Telefonbreite (360px) und Desktopbreite (1280px) vollständig bedienbar: kein horizontales Scrollen, nichts überlappt, nichts abgeschnitten. Für "kein horizontales Scrollen" ist `e2e/tests/no-horizontal-scroll.spec.ts` maßgeblich; Foto-Detail und Foto-Vergleich werden dort ergänzt. "Nichts überlappt, nichts abgeschnitten" bleibt Sichtprüfung.
- [ ] Die Trefferflächen bleiben eingehalten, auf dem heißen Pfad am Telefon weiterhin sichtbar mindestens 44px. **Nachweis:** `e2e/tests/tap-targets.spec.ts` bleibt unverändert grün, `EXPECTED_CONTROL_COUNT` bleibt 6.

### Abnahme

- [x] Alle vierzehn Ansichten sind in 360px und 1280px **sichtgeprüft**, ausschließlich gegen den synthetischen Demo-Stand (siehe "Security"), und die Prüfung ist in der PR-Beschreibung benannt. **Der ursprünglich geforderte Screenshot-Beleg im Pull Request entfällt** (Entscheidung Daniels vom 2026-09-06): Die Kommandozeile kann keine Bilder an einen Pull Request hängen — das Kriterium wäre nur über die Weboberfläche erfüllbar gewesen und damit bei jeder künftigen Umsetzung offen geblieben. Die Sichtprüfung selbst bleibt unverändert Pflicht.
- [ ] Die drei Bewertungszustände sind im Graustufentest an Karte und Kennzeichen unterscheidbar. **Abnahmekriterium wie im UI/UX-Abschnitt festgelegt:** Wort und Symbolsilhouette sind im Graustufen-Screenshot ablesbar, ohne die Farbfläche heranzuziehen; abgeschnittene Kennzeichentexte sind ein Fehlschlag, kein Randfall.
- [ ] Die Design-Dokumentation des Projekts gibt den neuen Stand wieder.

### Mitgenommene Aufräumpunkte aus Stufe 1

- [ ] Die Prüfung, an welchen Stellen vollrunde Formen zulässig sind, greift fundstellengenau statt dateiweise.
- [ ] Die Sperre des Hintergrund-Scrollens hinter einer Überlagerung trägt auch dann, wenn mehrere Überlagerungen gleichzeitig offen sind.

## Datenmodell-Bezug

Keiner. Diese Spec ändert ausschließlich die Darstellung im Frontend — keine neuen oder geänderten Entitäten, keine Backend-Berührung, keine Migration. Der einzige neu angezeigte Wert (Dateiname auf der Fotokachel) liegt bereits im vorhandenen Foto-Objekt vor.

## Architektur / Umsetzung

### Gewählter Ansatz

Die Formsprache wird **zentral** nachgezogen, nicht pro Ansicht. Stufe 1 hat die Token-Ebene bereits vollständig getauscht (`frontend/src/index.css`: vier Flächen, vier Akzente, vier Textstufen, Radienskala 4/6/8/12/16, Typoskala, 8-Punkt-Raster über Tailwinds Default-`--spacing`) — was in den Ansichten fehlt, ist nicht *ein weiterer Wertetausch*, sondern die **Verlagerung wiederholter Einzelentscheidungen in gemeinsame Bausteine plus ein statisches Netz, das ihre Rückkehr verhindert.** Drei Ebenen, in dieser Reihenfolge:

1. **Ein Token und vier statische Prüfungen** (`index.css`, `designSystem.contract.test.ts`) — sie machen aus "einheitlich" eine prüfbare Eigenschaft statt einer Sichtprüfung, die beim nächsten Feature wieder auseinanderläuft.
2. **Neue/erweiterte Bausteine**, die eine Board-Form genau einmal tragen: `PhotoCard`, `RatingBar`, das Board-Navigationselement im `Stepper`, das Textkennzeichen im `RatingBadge`, der unbestimmte `Progress`, der Icon-Button als `Button`-Aufruf statt neunmal handgerollt.
3. **Die Ansichten** greifen nur noch auf diese Bausteine zu und tragen selbst nur noch Layout (Raster, Abstände, Überschriftenstufen).

Das ist bewusst **kein Architekturumbau**: keine neue Abhängigkeit, kein neues Datenmodell, kein neues strukturelles Muster — `PhotoCard`/`RatingBar` sind zusammengesetzte Komponenten derselben Bauart wie die bestehenden unter `frontend/src/components/`. Deshalb **keine neue ADR** (siehe unten).

### Vorab getroffene Entscheidungen

**1. Die Foto-Kachel wird zu einer echten Karte und lebt genau einmal.** Heute ist sie in drei Ansichten hand-gebaut und dreimal verschieden: `pages/PhotoGridPage.tsx` (Link + Bild + absolut positionierte Badge + "Übernehmen"), `pages/CurateCategoriesPage.tsx` (Bild + `QualityMeter` + "Verwerfen") und `pages/PhotoComparePage.tsx` (`rounded-xl border p-2` + zwei Bewertungszeilen). Fünf Zustände in drei Kopien wären dreimal derselbe Fehler. Neu: `components/PhotoCard.tsx` trägt die Board-Karte (Radius 12px, Fläche `--elevated`, Rand `--border`, Polsterung 12px, Bildfläche Radius 8px), den Dateinamen, das Zustandskennzeichen und Slots für die Ecken-Overlays (`CriterionDetailsPopover`, `CategoryOverrideMarker`) und die Fußzeilen-Aktion.

**2. Das Zustandskennzeichen wandert aus der Bildecke in den Kartenkörper.** Board-treu und zugleich die Lösung eines echten Problems: ein Textbadge "ALBUM-WÜRDIG" über dem Foto braucht bei 360px und zwei Spalten (~170px Kachel) mehr Platz, als die Ecke hat, und die Ecke oben rechts ist laut Spec [`0040`](./0040-bewertungsdetails-info-popover.md) für den Info-Trigger reserviert. Im Kartenkörper entfällt zugleich der `pointer-events-none`-Kniff, mit dem die Badge heute Klicks an den darunterliegenden `<Link>` durchreicht.

**3. Der Zustand "neu" trägt das Wort "Neu", nicht das "–"-Badge.** `RatingBadge` behält sein neutrales "–" für seine übrigen Aufrufstellen (Vergleichsansicht: "Andere: –" heißt "hat nicht bewertet"); auf der Karte steht stattdessen die Board-Statuszeile "Neu" in `--text-muted`. Die in Spec [`0320`](./0320-dark-utility-register.md) festgehaltene Begründung für das "–" ("sonst ist *unbewertet* nicht von *Badge noch nicht geladen* unterscheidbar") bleibt damit erfüllt — das Wort "Neu" leistet das besser als der Strich. Kein Informationsverlust, keine stille Aufräumarbeit.

**4. Aussortiert: die Karte tritt zurück, die beiden Bedeutungsträger nicht.** Das Board dämpft die ganze Karte auf 40 % Deckkraft. ADR [`0055`](../decisions/0055-dark-utility-register-fundament.md) Abweichung 7 hat das bereits abgelehnt und ist bindend: Deckkraft auf einem Container mischt gegen den Seitengrund und ist statisch nicht nachrechenbar — weiße Schrift bei 40 % über `--bg` erreicht 3,79:1, die dunkle Tinte auf dem roten Badge wird praktisch unlesbar. Umgesetzt wird deshalb: **Bildfläche und dekorative Metadaten gedämpft, Zustandsbadge und Dateiname voll deckend**, der Dateiname zusätzlich durchgestrichen in `--text-muted` (nicht `--text-disabled` — er ist Inhalt, und die Regel "`--text-disabled` nur an tatsächlich deaktivierten Elementen" ist statisch geprüft). Optisch tritt die ganze Karte zurück, die Zusage "ohne Farbwahrnehmung erkennbar" trägt über Deckkraft **und** Durchstreichung **und** Symbol **und** Text. Das ist eine Präzisierung des AK-Wortlauts "ganze Karte", keine Rücknahme — die ADR bleibt unangetastet, es entsteht keine Nachfolge-ADR.

**5. Der Zustand "ausgewählt" wird zurückgestellt — die Karte trägt vier Zustände, nicht fünf.** PhotoSort kennt heute keine Foto-Auswahl, und "nichts wird hinzugefügt" verbietet, eine einzuführen. Der `architect` hatte vorgeschlagen, den Zustand trotzdem als getestete Prop ohne Aufrufer zu bauen (Präzedenzfall `ui/dialog.tsx` aus Stufe 1); **Daniel hat sich dagegen entschieden** (Rückfrage im `spec-writer`-Ablauf, 2026-09-05): Der Zustand entfällt vorerst und kommt erst mit der Story, die eine Foto-Auswahl tatsächlich einführt. `PhotoCard` bekommt also **keine** `selected`-Prop und kein `data-selected`. Die Abweichung vom Board-Wortlaut "fünf Zustände" ist bewusst und wird in der PR-Beschreibung als solche vermerkt.

**6. Die Schrittnavigation bekommt die drei Board-Zustände, behält aber ihre vier Schrittbedeutungen.** Board-Navigationselement: Radius 8px, 16/8px, Symbol 16px + 13px Text; ruhend `--surface`/`--border`/`--text`, überfahren `--overlay`/`--text-h`, aktiv `--overlay` + 1,5px `--accent` + Inter Bold `--accent`. Darauf liegen die vier vorhandenen Schrittzustände: *aktuell* = aktiv, *erledigt* und *ausstehend* = ruhend (unterschieden durch Haken vs. Nummer), *blockiert* = ruhend mit gedämpfter Beschriftung und Schloss-Symbol. Keine Sidebar (entschieden), die Leiste bleibt waagerecht; unterhalb `sm:` bleibt die heutige Marker-Darstellung samt Orientierungszeile "Schritt 3 von 5" — fünf beschriftete Nav-Elemente passen bei 360px nicht nebeneinander, und horizontales Scrollen ist Ausschlusskriterium.

**7. Die Bewertungsleiste ersetzt `RatingButtons` an Ort und Stelle.** Container `--surface`, Radius 8px, Polsterung 8px, Abstand 12px; je Eintrag Fläche `--elevated`, Radius 6px, 12/6px, Symbol 16px + sichtbare Beschriftung + Tasten-Kästchen (`--overlay`, Radius 4px, JetBrains Mono 10px, Schrift in der Zustandsfarbe). **Belegung bleibt 1 / 2 / 3** (entschieden) — übernommen wird die Form des Kästchens, nicht die Board-Beschriftung F/A/X. Einziger Aufrufer ist `pages/PhotoDetailPage.tsx`, wo die Tastenkürzel tatsächlich greifen; das Kästchen steht damit nirgends, wo es lügt.

**8. Sichtbare Trennlinien bekommen ein eigenes Token.** `--border #2A2E3D` erreicht 1,04–1,45:1 und ist laut Design-System ausdrücklich eine *dekorative* Linie — als Trennlinie auf `--bg` ist er schlicht unsichtbar, und `border-border/60` (Statistikseite) liegt bei 0,87:1. Neu: **`--separator`** in `:root` (Zielkorridor 2,0–2,5:1 gegen `--bg`/`--surface`, exakter Hexwert im UI/UX-Abschnitt), Utility `--color-separator` im `@theme`-Block, mit eigener Zeile in der Kontrastmatrix des Vertragstests. Aufrufstellen: `Stepper.tsx` (Verbindungslinie, Kopfzeilenrand), `App.tsx` (Kopfzeilenrand), `ProjectStatsPage.tsx` (Abschnitts- und Zeilentrenner, Tabellenrand), `StatusDot.tsx` (Rückfallfarbe "kein Status" — heute `bg-border` und damit unsichtbar), `ui/progress.tsx` (Spur), `PhotoImage.tsx` (Platzhalterfläche), `CurateCategoriesPage.tsx` (gestrichelter Leerplatz). `--border` bleibt unverändert für Karten-/Panelränder auf abgesetzter Fläche und als gedrückte Zustandsfläche.

**9. Der unbestimmte Fortschritt wird über Deckkraft dargestellt, nicht über Bewegung.** Das Design-System lässt ausschließlich Farb-/Deckkraftübergänge zu und verbietet Bewegung von Layout oder Position — ein wanderndes Segment (die Browser-Voreinstellung) ist genau das. Umgesetzt als `:indeterminate`-Zustand: volle Fläche in `--accent` mit dem bereits etablierten Puls (`animate-pulse motion-reduce:animate-none`, dieselbe Mechanik wie Skeleton und Spinner) auf der Spur in `--separator`. Betrifft `ui/progress.tsx`; Aufrufstellen (`ScanStepPage`, `AusschussStepPage`, `ClassificationSection`) bleiben unverändert.

### Die beiden Aufräumpunkte aus Stufe 1

**Fundstellengenaue Prüfung vollrunder Formen.** Heute ist `ROUNDED_FULL_ALLOWLIST` in `frontend/src/designSystem.contract.test.ts` (Block "Design-Vertrag: Formsprache und Skalen") nach **Dateien** geschlüsselt: sobald eine Datei einmal drinsteht, ist jedes weitere `rounded-full` darin unsichtbar — `ui/button.tsx` ist wegen des Lade-Spinners freigegeben und dürfte damit unbemerkt wieder eine vollrunde Schaltfläche bekommen. Umbau auf einen **generischen Helfer**:

- `allowlistedOccurrences(needle, entries)` sammelt alle Fundstellen als `{ label, line, text }` und gleicht jede gegen die Einträge `{ file, snippet, reason }` ab.
- Drei Fehlerklassen statt einer: (a) Fundstelle ohne passenden Eintrag, (b) Eintrag ohne Fundstelle (verwaiste Freigabe — der Grund, warum solche Listen verrotten), (c) `snippet`, das nur aus dem Suchbegriff selbst besteht (verhindert den stillen Rückfall auf Datei-Granularität).
- `stripComments` muss dafür **zeilentreu** werden (Kommentarinhalt durch Leerzeichen ersetzen, Zeilenumbrüche erhalten), sonst stimmen die gemeldeten Zeilennummern nicht.

Derselbe Helfer trägt die vier neuen Prüfungen dieser Stufe (siehe "Netz" unten) — er ist der eigentliche Gewinn, `rounded-full` nur sein erster Nutzer. Rot-Nachweis: eine zusätzliche `rounded-full`-Zeile in einer bereits gelisteten Datei muss den Test rot machen; genau das tut er heute nicht.

**Scroll-Sperre bei mehreren Überlagerungen.** `ui/dialog.tsx` merkt sich in seinem Effekt `document.body.style.overflow` und stellt ihn beim Aufräumen wieder her. Bei zwei gleichzeitig offenen Dialogen liest der zweite bereits `'hidden'` als "vorherigen" Wert; schließt danach der **erste** zuerst, schreibt er sein leeres `''` zurück und der Hintergrund scrollt, obwohl noch ein Dialog offen ist. Neu: `frontend/src/lib/scrollLock.ts` mit modulweitem Zähler — `lockBodyScroll(): () => void` sichert den Ausgangswert nur beim Übergang 0 → 1 und stellt ihn nur beim Übergang 1 → 0 wieder her; die zurückgegebene Freigabe ist über ein eigenes Flag **idempotent** (React ruft Effekt-Aufräumungen im StrictMode doppelt auf). `dialog.tsx` ruft nur noch `lockBodyScroll()` auf. Ein `resetBodyScrollLock()` wird in `setupTests.ts` per `afterEach` aufgerufen — Testhygiene für modulweiten Zustand, keine Produktions-API. Tests: zwei Dialoge, in beiden Schließreihenfolgen, plus ein bereits gesetztes `overflow` als Ausgangswert.

### Das Netz — vier neue statische Prüfungen

Alle in `designSystem.contract.test.ts` (die einzige Ebene mit CSS-Assertions; Komponententests bekommen weiterhin **keine**), alle über den fundstellengenauen Helfer, alle mit Begründung je Eintrag:

1. **Abstandsskala.** `p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|space-x|space-y` dürfen nur die acht Stufen `0/1/2/3/4/6/8/12/16` tragen. Heutige Verstöße u.a. `gap-1.5` (~14×), `gap-2.5`, `gap-3.5`, `py-3.5`, `px-5`, `mt-5`, `py-10`, `px-8/px-10`, `p-0.5`, `mb-7`. **Höhen/Breiten sind nicht betroffen** (`h-11`, `size-8`, `h-0.5` bleiben zulässig) — die Regel ist eine Abstands-, keine Größenregel.
2. **Keine willkürlichen Werte** (`text-[…]`, `h-[…]`, `w-[…]`, `p*-[…]`, `gap-[…]`) außerhalb der Liste. Freigegeben bleiben `ui/popover.tsx` (`max-h-[60vh]`), `ui/checkbox.tsx` (`size-[18px]`, abgeleitetes Board-Maß) und `ui/dialog.tsx` (`w-[min(32rem,…)]`). Zu entfernen: `ProjectListPage.tsx` `text-[10.5px]`, `ProjectPipelineLayout.tsx` `text-[10px]`, `LoginPage.tsx` `h-[50px]`.
3. **Keine Deckkraft-Modifikatoren auf Farb-Utilities** außerhalb der Liste (freigegeben: die drei Hintergrund-Abdunklungen `bg-black/60` im Dialog-Backdrop, `bg-bg/95` in den beiden sticky Kopfzeilen, `bg-bg/85` hinter dem Kennzeichen über einer Kachel). Trifft `border-border/60` (0,87:1) und `bg-border/60` — genau den Befund "Trennlinien verschwinden auf dem Grund", und zugleich die Fehlerklasse "Kontrast statisch nicht nachrechenbar".

4. **`opacity-*` fundstellengenau** — vom `test-engineer` in Schritt 3 ergänzt, nicht Teil der ursprünglichen Architektur-Planung. Sie sichert Entscheidung 4 dauerhaft ab, deren einziger sonstiger Nachweis ein einmaliger Ad-hoc-Lauf wäre. Freigabeliste und Begründung stehen im Abschnitt "Teststrategie".

Zusätzlich wandert **`h-11`/`min-h-11` auf die Liste**: zulässig nur auf dem heißen Pfad (Bewertungsleiste, Weiter/Zurück) und als Zeilenhöhe zeilenweiser Listen (Regel 3 der Trefferflächen). Heutige Verstöße: `App.tsx` (Wortmarke, Projekt-Link), `ProjectListPage.tsx` (Leerzustands-Schaltfläche), `CategorySelect.tsx`.

### Betroffene Dateien und Etappen

Die Etappen sind so geschnitten, dass **jede für sich grün endet** (`npm run lint`, `npm run typecheck`, `npx vitest run`) und einen eigenen Commit trägt. Innerhalb einer Etappe gilt der normale Rot-Grün-Zyklus: erst die Prüfung/den Test, der die Lücke zeigt, dann die Umsetzung.

**Etappe 1 — die beiden Aufräumpunkte** (keine sichtbare Änderung). `frontend/src/lib/scrollLock.ts` (neu) + `scrollLock.test.ts` (neu), `ui/dialog.tsx`, `ui/dialog.test.tsx` (zwei Dialoge, beide Schließreihenfolgen), `setupTests.ts`; `designSystem.contract.test.ts`: zeilentreues `stripComments`, generischer Helfer, `rounded-full` auf Fundstellen umgestellt.

**Etappe 2 — Token und Primitive.** `index.css` (`--separator` in `:root` + `@theme`), `designSystem.contract.test.ts` (Kontrastzeile), `ui/progress.tsx` (unbestimmter Zustand, Spur), `components/StatusDot.tsx`, `components/PhotoImage.tsx`; `components/RatingBadge.tsx` + `ui/badge.tsx` (sichtbares Textkennzeichen neben dem Symbol — `aria-label` bleibt wortgleich, sonst brechen `e2e/tests/tap-targets.spec.ts` und die Komponententests); die **neun** handgerollten Icon-Schaltflächen (`Stepper.tsx` ×2, `CriterionDetailsPopover.tsx` ×2, `ProjectSettingsPage.tsx` ×2, `ProjectStatsPage.tsx` ×2, `CurateCategoriesPage.tsx`) auf `<Button variant="ghost" size="icon">`.

**Etappe 3 — die drei zusammengesetzten Bausteine.** `components/PhotoCard.tsx` (neu) + Test: vier Zustände über `data`-Merkmale (`data-rating-status`, `data-struck`), Dateiname, Slots. Kein `data-selected` (Entscheidung 5). `components/RatingButtons.tsx` → Board-Bewertungsleiste inkl. Tasten-Kästchen (`aria-hidden`, sonst zerbricht der zugängliche Name "Favorit"), Datei-/Exportname bleibt, damit die Aufrufstelle unverändert bleibt. `components/Stepper.tsx` → Board-Navigationselement mit den drei Zuständen; das Schloss-Symbol bleibt Inline-SVG (der Zwölfer-Satz hat kein Schloss — dokumentierte Lücke, wird nicht stillschweigend mit einem beliebigen Lucide-Symbol gefüllt), der Haken wird `<Icon name="check">`.

**Etappe 4 — die Ansichten**, getrieben von den vier neuen Prüfungen (rot) plus Sichtprüfung, in vier grün endenden Teilschritten:

- **4a Hülle und Anmeldung:** `App.tsx`, `pages/LoginPage.tsx`, `components/BrandMark.tsx`.
- **4b Projektebene:** `ProjectListPage.tsx` (inkl. Leerzustand), `ProjectCreatePage.tsx`, `ProjectSettingsPage.tsx`, `ProjectStatsPage.tsx` (12-Spalten-Raster bleibt), `FolderBrowser.tsx`, `CategorySelect.tsx`.
- **4c Pipeline:** `pages/pipeline/ProjectPipelineLayout.tsx`, `ScanStepPage.tsx`, `AusschussStepPage.tsx`, `GateStepPage.tsx`, `KriterienStepPage.tsx`, `KuratierungStepPage.tsx`, `PipelineStepView.tsx`, `components/ClassificationSection.tsx`, `CloudVisionStatusList.tsx`, `StatusTag.tsx`.
- **4d Foto-Ansichten:** `PhotoGridPage.tsx`, `CurateCategoriesPage.tsx`, `PhotoComparePage.tsx` (alle drei auf `PhotoCard`), `PhotoDetailPage.tsx`, `CriterionDetailsList.tsx`, `CriterionDetailsPopover.tsx`, `CategoryBadge.tsx`, `QualityMeter.tsx`.

**Etappe 5 — Abnahme und Doku.** `e2e`-Prüfsatz lokal grün (`no-horizontal-scroll`, `tap-targets`, `grid-columns`, `sticky-header`, `popover-position`, `empty-and-error-states`); Screenshots aller Ansichten in 360px und 1280px über den `browse-app`-Skill für die PR-Beschreibung; Graustufen-Abnahme als eigener Ad-hoc-Lauf mit eingespeistem `html { filter: grayscale(1) }` an Raster und Bewertungsleiste; `specs/architecture/0004-design-system.md` und `.claude/skills/design-system/SKILL.md` auf den neuen Stand (neues Token, die vier neuen statischen Regeln, die achte Board-Abweichung aus Entscheidung 4, die neuen Bausteine).

### Fallstricke

- **Die e2e-Selektoren sind Vertragsfläche.** `photoTiles` = `listitem`, der ein `a[href*="/photos/"]` enthält (`PhotoCard` muss beides behalten); `getByRole('group', { name: 'Bewertung' })`; `getByRole('button', { name: 'Favorit'|'Album-würdig'|'Verwerfen', exact: true })`; `getByRole('banner')`; `getByRole('navigation', { name: 'Fortschritt der Pipeline' })`; `button[aria-haspopup="dialog"]`; die Überschriften der Routenliste in `no-horizontal-scroll.spec.ts`; `EXPECTED_CONTROL_COUNT = 6` in `tap-targets.spec.ts`. Kein zugänglicher Name, keine Rolle und keine Elementanzahl darf sich ändern.
- **Dichter werden heißt nicht enger werden.** Zwischen aufgespannten Trefferflächen bleiben 12px Pflicht (`gap-3`), zwischen fokussierbaren Elementen 8px — die Aufspannung ragt 6px je Seite über das Sichtbare hinaus, und in der Überlappung gewinnt das obenliegende Element. Bei der Bewertungsleiste ist das ein **falsch geschriebener Datenwert**.
- **`tap-target` nie in einen beschneidenden Container.** Die Bildfläche der Karte trägt `overflow-hidden`; die Ecken-Trigger (`CriterionDetailsPopover`, `CategoryOverrideMarker`) müssen Geschwister der Bildfläche bleiben, nicht Kinder.
- **Tailwind erkennt nur vollständige, statische Klassennamen.** Die vier Kartenzustände und die drei Nav-Zustände als ausgeschriebene `Record`-Einträge, kein Template-String.
- **Vier statisch geprüfte Verbote gelten unverändert:** kein `outline-none`/`focus-visible:`/`ring-offset` in `.tsx`; jede `hover:`-Variante unter `components/ui/` braucht eine `active:` daneben (betrifft die neuen Nav- und Leisten-Zustände); `--text-disabled` nur als `disabled:`-Variante; nur `ui/icon.tsx` importiert aus `lucide-react`.
- **Seitenüberschriften tragen die Board-Stufe erst ab `sm:`** (`text-xl sm:text-2xl`) — bei 360px läuft "Projekteinstellungen" in 40px über den Rand.
- **Komponententests bekommen keine CSS-Assertions** (Regel aus Stufe 1). Zustände werden über `data-*`/`aria-*` geprüft; alles Gerechnete oder Gestrichene gehört in den Vertragstest.
- **Der unbestimmte Fortschritt ist in jsdom nicht belegbar** — `:indeterminate` und die Browser-Pseudo-Elemente existieren dort nicht. Zusage: eine statische Prüfung, dass `ui/progress.tsx` den Zustand überhaupt behandelt, plus Sichtprüfung im Browser.
- **Der Vertragstest schließt sich selbst vom Scan aus** (`SELF_FILE`) — Allowlist-Snippets müssen echte Codezeilen der jeweiligen Datei sein, sonst schlägt die neue Prüfung "verwaister Eintrag" zu Recht an.

### Keine neue ADR

Keine der Entscheidungen dieser Stufe ist architekturrelevant im Sinne von `CLAUDE.md`: keine neue Technologie, keine Änderung am Datenmodell, keine neue externe Abhängigkeit. Der einzige Punkt mit ADR-Berührung ist die aussortierte Karte — dort wird ADR 0055 Abweichung 7 **eingehalten** und nur präzisiert (Entscheidung 4), nicht abgelöst. `docs/architecture.md`, `docs/setup.md` und das Root-`README.md` bleiben unberührt: keine neue Komponente des Systems, kein Setup-Schritt, keine Umgebungsvariable. Zu aktualisieren sind ausschließlich `specs/architecture/0004-design-system.md` und `.claude/skills/design-system/SKILL.md`, im selben PR.

## UI/UX

### 1. Das neue Token `--separator`

**Wert: `--separator: #474E68`** (`@theme`: `--color-separator`, Utilities `bg-separator` / `border-separator`).

Abgeleitet aus `--border #2A2E3D`, nicht frei gewählt: gleicher Farbton (227°) und praktisch gleiche Sättigung (18,9 % gegen 18,4 %), nur eine Helligkeitsstufe darüber. Die Trennlinie ist damit sichtbar dasselbe Material wie die Panelkante, nicht ein zweiter Grauton.

**Rechenweg** (WCAG 2.x relative Luminanz, dieselbe Rechnung wie die Kontrastmatrix des Board-Dokuments — `c_lin = c/12.92` für `c ≤ 0.04045`, sonst `((c+0.055)/1.055)^2.4`; `L = 0.2126·R + 0.7152·G + 0.0722·B`; Kontrast `(L_hell+0.05)/(L_dunkel+0.05)`):

| Farbe | R,G,B | L |
|---|---|---|
| `--separator #474E68` | 71, 78, 104 | **0,07788** |
| `--bg #0B0C10` | 11, 12, 16 | 0,00372 |
| `--surface #14161F` | 20, 22, 31 | 0,00821 |
| `--elevated #1E2230` | 30, 34, 48 | 0,01631 |
| `--overlay #262B3D` | 38, 43, 61 | 0,02478 |

- gegen `--bg`: (0,07788 + 0,05) / (0,00372 + 0,05) = 0,12788 / 0,05372 = **2,38:1**
- gegen `--surface`: 0,12788 / 0,05821 = **2,20:1**
- gegen `--elevated`: **1,93:1** · gegen `--overlay`: **1,71:1**

Beide Zielwerte liegen im vom Architektur-Abschnitt vorgegebenen Korridor 2,0–2,5:1. Zum Vergleich der heutige Zustand: `--border` erreicht 1,45 / 1,34 / 1,17 / 1,04 — auf `--bg` liegt der Sprung damit vom Faktor 1,45 auf 2,38.

**Zeile für die Kontrastmatrix des Vertragstests** (Format der bestehenden Matrix, alle vier Flächen):

| Vordergrund | auf `--bg` | auf `--surface` | auf `--elevated` | auf `--overlay` |
|---|---|---|---|---|
| Separator `#474E68` | 2,38 | 2,20 | 1,93 | 1,71 |

Die Werte auf `--elevated`/`--overlay` sind nachrichtlich und **keine** Zusage: dort gilt `--separator` nicht (siehe unten). Sie stehen trotzdem in der Matrix, damit die Zeile vollständig ist und ein späterer Wertewechsel alle vier Zahlen mitführt.

**Wo `--separator` gilt** — überall dort, wo eine Linie oder eine dekorative Fläche **unmittelbar auf `--bg` oder `--surface`** steht und dort die einzige Grenze ist:

- freistehende Trennlinien: Kopfzeilenrand in `App.tsx` und `Stepper.tsx`, Verbindungslinie zwischen den Schritten im `Stepper`, Abschnitts- und Zeilentrenner sowie Tabellenrand in `ProjectStatsPage.tsx`;
- dekorative Flächen, die sich vom Grund abheben müssen: Spur in `ui/progress.tsx`, Platzhalterfläche in `PhotoImage.tsx`, gestrichelter Leerplatz in `CurateCategoriesPage.tsx`, Rückfallfarbe "kein Status" in `StatusDot.tsx`.

**Wo `--border` unverändert bleibt:**

- als **Umriss einer abgesetzten Fläche** — Karten-, Panel- und Dialogkante auf `--elevated`/`--overlay`. Dort trennt die Flächenstufe, die Linie schärft nur die Kante; `--separator` wäre dort eine zweite, konkurrierende Aussage;
- als **gedrückte Zustandsfläche** (`active:bg-border`) — unverändert gültig samt der Regel, dass darauf nur `--text` und `--text-h` zulässig sind;
- am **deaktivierten Bedienelement** (`disabled:border-border`).

`--border-control #727891` bleibt unverändert der sichtbare **Umriss eines Bedienelements**. Die Dreiteilung lautet ab jetzt: `--border` = Kante einer Fläche · `--separator` = Linie auf dem Grund · `--border-control` = Umriss eines Bedienelements.

**Anmerkung zur Foto-Karte:** Sie behält laut Entscheidung 1 `--border`. Das ist richtig, weil ihre Lesbarkeit aus der Flächenstufe (`--elevated` auf `--bg`) kommt und der Rand nur die Ecke schärft — aber es ist bewusst eine schwache Linie (1,45:1 gegen `--bg`, 1,17:1 gegen die eigene Fläche). Wenn die Karte in der Sichtprüfung randlos wirkt, ist die Antwort **nicht** `--separator` am Kartenrand, sondern die Prüfung, ob die Innenpolsterung die Kante ausreichend zeigt.

### 2. Die vier Zustände der Foto-Karte

**Aufbau der Karte** (`components/PhotoCard.tsx`), von oben nach unten und zugleich die DOM-/Fokusreihenfolge:

```
<li>  role=listitem  (Rasterzelle, bleibt e2e-Vertragsfläche)
  Kartenkörper   rounded-lg  border border-border  bg-elevated  p-2 sm:p-3  flex flex-col gap-2
    ├─ Bildbereich  (position: relative)
    │    ├─ <a href=".../photos/:id">  block aspect-square overflow-hidden rounded-md
    │    │      └─ PhotoImage
    │    └─ Ecken-Overlays  (absolut, GESCHWISTER des <a>, nie darin)
    │         links oben:  CategoryOverrideMarker      rechts oben:  CriterionDetailsPopover
    ├─ Statuszeile   flex items-center justify-between gap-2   ← Kennzeichen + Dateiname
    └─ Fußzeilen-Aktion (Slot, optional: "Übernehmen" / "Verwerfen" / die Vergleichszeilen)
```

Bewusst `p-2 sm:p-3` statt durchgängig der 12px des Boards: Bei 360px und zwei Spalten misst die Kachel 158px; 12px Polsterung schrumpfen die Bildfläche von heute 158px auf 132px, also um 16 %. Das Board ist ein Desktop-Entwurf, und die Bildfläche ist auf dem Telefon die knappste Ressource der ganzen Anwendung. Mit 8px bleiben 140px. Beide Werte liegen auf der erlaubten Abstandsskala; ab `sm:` gilt das Board-Maß.

**Die Statuszeile** trägt links das Kennzeichen, rechts den Dateinamen (`justify-between`). Kennzeichen links, weil es je nach Zustand fehlt ("Neu" ist Text in derselben Position) und die linke Kante die ruhigere Ausrichtungskante ist.

**Wertetabelle der vier Zustände** (`data-rating-status` / `data-struck` als DOM-Merkmale — Komponententests prüfen diese, nie CSS):

| Zustand | Kennzeichentext (sichtbar) | Symbol (14px) | Fläche / Rand des Kennzeichens | Schrift im Kennzeichen | Dateiname | Deckkraft |
|---|---|---|---|---|---|---|
| **neu** | `Neu` (kein Badge-Körper) | — | keine Fläche, kein Rand | `--text-muted` (5,11:1 auf `--elevated`), `text-xs` | `--text`, normal | 100 % |
| **Favorit** | `Favorit` | `star` | `--rating-favorite #FFB000`, Rand transparent, `rounded-sm` (6px) | `--rating-favorite-fg #0B0C10` (10,67:1), `text-xs font-semibold` | `--text`, normal | 100 % |
| **Album-würdig** | `Album-würdig` | `book` | `--rating-album-worthy #00E676`, Rand transparent, `rounded-sm` | `--rating-album-worthy-fg #0B0C10` (11,71:1) | `--text`, normal | 100 % |
| **aussortiert** | `Verworfen` | `x-circle` | `--rating-rejected #FF3D00`, Rand transparent, `rounded-sm` | `--rating-rejected-fg #0B0C10` (5,51:1) | `--text-muted` + `line-through` | **`opacity-40` nur auf dem `<a>` der Bildfläche** |

Alle vier Kennzeichen sitzen links in der Statuszeile.

Weitere Festlegungen dazu:

- **Kennzeichentext = die vorhandenen Produktwörter**, nicht die Board-Wörter. `RATING_STATUS_LABELS` liefert Favorit / Album-würdig / **Verworfen**. "AUSGESONDERT" wäre ein viertes Wort für denselben Zustand, neben "Verwerfen" (Schaltfläche) und "Verworfen" (Filter) — das Board liefert hier eine Übersetzung, keine Vorgabe. Keine Versalien: die Board-Rolle "Beschriftung" ist im Design-System ausdrücklich nicht an `text-xs` gebunden, und `Album-würdig` in Versalien wäre bei 12px auf 140px Kachelbreite die längste Zeile der Karte.
- **Kein 10px.** Das Board zeichnet das Badge mit 10px; das Design-System setzt 12px als harte Untergrenze und die neue Prüfung "keine willkürlichen Werte" verbietet `text-[10px]`. Kennzeichen und Dateiname sind `text-xs`.
- **Deckkraft im aussortierten Zustand: `opacity-40`, ausschließlich auf dem `<a>`-Element der Bildfläche.** Der Board-Wert bleibt damit an der einen Stelle erhalten, an der er nichts unter eine Kontrastschwelle drückt (ADR 0055 Abweichung 7 wird eingehalten). "Dekorative Metadaten" aus Entscheidung 4 heißt eng: `aria-hidden`-Elemente **ohne eigenen Text** — konkret die Punktgruppe `●●○` des `QualityMeter`, nicht dessen ausgeschriebener Stufenname. Nicht gedämpft werden in jedem Fall: Kennzeichen, Dateiname, die beiden Ecken-Trigger (sie bleiben bedienbar und müssen ihren Kontrast behalten) und die Fußzeilen-Aktion.
- **Durchstreichung in `--text-muted`, nicht `--text-disabled`** — der Dateiname ist Inhalt, und die Regel "`--text-disabled` nur an tatsächlich deaktivierten Elementen" ist statisch geprüft. `#8D92A4` auf `--elevated` = 5,11:1.
- **Der fünfte Board-Zustand "ausgewählt" wird nicht gebaut** (Entscheidung 5, von Daniel zurückgestellt). `PhotoCard` bekommt weder eine `selected`-Prop noch `data-selected`, und es entsteht kein Auswahlpunkt und keine Akzentkante. Der Zustand kommt mit der Story, die eine Foto-Auswahl einführt.

**Der Dateiname bei 360px in zwei Spalten.**

Rechnung: 360 − 32 (`px-4` der Hülle) = 328; abzüglich `gap-3` = 316 / 2 = **158px Kachel**; abzüglich Rand 2px und `p-2` 16px = **140px Innenbreite**. Davon geht die Statuszeile zusätzlich für Kennzeichen und `gap-2` weg — im Zustand "Favorit" bleiben dem Dateinamen ca. 60px, im Zustand "Neu" ca. 100px.

Festlegung:

- **Nur der Basisname**, nicht der `relative_path` (dessen Ordnerteil ist auf 60px ohnehin unlesbar und steht bereits im `alt` des Bildes sowie im `aria-label` der "Übernehmen"-Schaltfläche).
- **`font-mono text-xs`** — dieselbe Regel wie beim Cloud-Pfad in der Projektliste: eine Dateikennung ist keine Fließtextzeile.
- **Eine Zeile, `truncate`** (`min-w-0 truncate`), kein Umbruch. Zwei Gründe: In einer Rasterzeile gleichen sich die Kartenhöhen aus, ein zweizeiliger Dateiname auf einer einzigen Karte macht **alle** Karten der Zeile höher — bei zwei Spalten ist das jede zweite Karte. Und eine feste Zeilenzahl hält die Fußzeilen-Aktion aller Karten auf gleicher Höhe, was für wiederholtes Tippen auf "Übernehmen"/"Verwerfen" mehr wert ist als der vollständige Name.
- **Die Durchstreichung bleibt bei `truncate` sichtbar**: `text-decoration: line-through` läuft über alle gerenderten Glyphen inklusive der Auslassungspunkte; abgeschnitten wird der Text, nicht die Linie. Damit die Streichung nie ganz verschwindet, trägt der Dateiname `min-w-6` — eine Karte mit extrem langem Kennzeichen darf ihn nicht auf null drücken.
- **Der Dateiname steht außerhalb des `<a>`** (in der Statuszeile, nicht im Bildbereich). Damit bleibt der zugängliche Name des Kachel-Links unverändert der `alt`-Text des Bildes — der e2e-Vertrag `listitem` mit `a[href*="/photos/"]` und die bestehenden Namen bleiben unberührt.

### 3. Der Graustufentest

**Was der Test ist:** Ad-hoc-Lauf mit eingespeistem `html { filter: grayscale(1) }` an Foto-Raster und Bewertungsleiste (Etappe 5). `grayscale(1)` rechnet mit denselben Koeffizienten 0,2126/0,7152/0,0722, aber auf den **gamma-kodierten** sRGB-Werten — das ist der Wert, den man am Bildschirm sieht.

**Ergebnis der drei Bewertungsflächen unter `grayscale(1)`:**

| Zustand | Fläche | Grauwert | Kontrast der reinen Flächen zueinander |
|---|---|---|---|
| Favorit | `#FFB000` | `#B4B4B4` (180) | Favorit ↔ Album: **1,08:1** |
| Album-würdig | `#00E676` | `#ADADAD` (173) | Favorit ↔ Verworfen: **2,94:1** |
| Verworfen | `#FF3D00` | `#626262` (98) | Album ↔ Verworfen: **2,72:1** |

**Ehrliche Lesart, und zugleich die Begründung des ganzen Abschnitts:** *Verworfen* trennt sich über die Luminanz sauber ab (Faktor 2,7–2,9). *Favorit* und *Album-würdig* tun das **nicht** — 1,08:1 ist als Helligkeitsunterschied nicht wahrnehmbar. Das ist keine Umsetzungslücke, sondern eine Eigenschaft der Board-Palette, die ADR 0055 festschreibt; das Design-System hält es unter "Kein Bewertungszustand allein über die Farbfläche" bereits als harte Regel fest. Ein Versuch, die Fläche eines der beiden Töne zu verschieben, wäre eine stillschweigende Palettenänderung an ADR 0055 vorbei und wird ausdrücklich **nicht** unternommen.

**Was den Test deshalb trägt — je Zustand ein nicht-farbliches Merkmal, das eine eigene Graustufen-Luminanz hat:**

| Zustand | Merkmal am **Kennzeichen** | Merkmal an der **Karte** | Luminanz-Nachweis in Graustufen |
|---|---|---|---|
| Favorit | Wort `Favorit` + `star` (kompakte, gezackte Silhouette) | Kennzeichen sitzt seit Entscheidung 2 **im Kartenkörper**, ist also selbst ein Kartenmerkmal | Tinte `#0C0C0C` auf Fläche `#B4B4B4` = **9,43:1**; Kennzeichenfläche gegen Kartenfläche `#222222` = **7,67:1** |
| Album-würdig | Wort `Album-würdig` + `book` (rechteckige Doppelseiten-Silhouette) | dito | Tinte auf Fläche = **8,72:1**; Fläche gegen Karte = **7,09:1**; **Wortlänge** 12 vs. 7 Zeichen → doppelte Kennzeichenbreite |
| Verworfen | Wort `Verworfen` + `x-circle` (Kreis mit Diagonalkreuz) | Bildfläche auf 40 % gedämpft **und** Dateiname durchgestrichen in `--text-muted` | Tinte auf Fläche `#626262` = **3,21:1**; Fläche gegen Karte = **2,61:1**, gegen die beiden anderen Kennzeichenflächen **2,94** bzw. **2,72:1** |

Die Zusage "an Karte **und** Kennzeichen unterscheidbar" ist erfüllt, weil Entscheidung 2 das Kennzeichen aus der Bildecke in den Kartenkörper holt: Die Karte trägt die Unterscheidung ab jetzt selbst, statt sie an ein Overlay auszulagern. Zusätzlich unterscheidet sich der aussortierte Zustand als **einziger** auch ohne Blick auf das Kennzeichen (gedämpftes Bild, gestrichener Name) — das ist genau der Zustand, dessen Verwechslung am teuersten ist.

**Abnahmekriterium für den Ad-hoc-Lauf:** Im Graustufen-Screenshot müssen sich die drei Zustände an **Wort und Symbolsilhouette** ablesen lassen, ohne die Farbfläche heranzuziehen. Ein Screenshot, in dem die Kennzeichentexte abgeschnitten sind, ist ein Fehlschlag des Tests, nicht ein Randfall.

### 4. Die Bewertungsleiste

`components/RatingButtons.tsx` behält Dateinamen, Exportnamen und Aufrufstelle (`PhotoDetailPage`); nur Form und Inhalt der Einträge ändern sich.

**Container:** `role="group" aria-label="Bewertung"` (unverändert), `bg-surface rounded-md p-2`, Abstand zwischen den Einträgen `gap-3` (12px — die Pflichtgrenze zwischen aufgespannten Trefferflächen, hier **kein** Gestaltungsspielraum: eine Überlappung schreibt hier einen falschen Datenwert).

**Ein Eintrag:** `rounded-sm` (6px), `px-3 py-2` (12/8px — die 6px des Boards liegen nicht auf der Abstandsskala), Inhalt `Symbol 16px` + `gap-1` + `Beschriftung` + `gap-1` + `Tasten-Kästchen`, Beschriftung `text-xs font-semibold`.

**Die sechs Zustände:**

| Zustand | Fläche | Rand | Beschriftung | Symbol | Umsetzung |
|---|---|---|---|---|---|
| ruhend | `--elevated` | 1px `--border-control` | `--text-h` | `--text` | Board zeichnet den Eintrag randlos; `--elevated` auf `--surface` misst 1,14:1 und wäre als Bedienelement unsichtbar. `--border-control` auf `--elevated` = **3,63:1** — dies ist **keine neue Abweichung**, sondern derselbe Fall wie die bereits dokumentierte Board-Abweichung 2. |
| überfahren | `--overlay` | unverändert | `--text-h` | `--text-h` | `hover:` |
| gedrückt | `--border` | unverändert | `--text` (5,49:1) | `--text` | `active:` — Pflicht neben jedem `hover:`; am Telefon der einzige existierende Zustand |
| aktiv (Bewertung gesetzt) | `--rating-<ton>` voll gefüllt | transparent (anliegende Kante = die Fläche selbst) | `--rating-<ton>-fg` | dito | `aria-pressed="true"`, `hover:opacity-85 active:opacity-70` wie heute |
| fokussiert | — | — | — | — | **keine eigene Darstellung**: die eine globale `:focus-visible`-Regel. Auf dem aktiven Eintrag liest man dadurch zwei Linien mit dunklem Spalt (Auswahl anliegend, Fokus abgesetzt). |
| deaktiviert | `--surface` | 1px `--border` | `--text-disabled` | dito | kommt unverändert aus dem `Button`-Primitive (`disabled:…` + `disabled:opacity-40`) |

**Sichtbare Beschriftung je Eintrag:** `Favorit` · `Album-würdig` · `Verwerfen` — wortgleich mit den heutigen `aria-label`n. Die e2e-Prüfung `getByRole('button', { name: …, exact: true })` bleibt damit gültig, und WCAG 2.5.3 "Label in Name" ist erfüllt (sichtbares Wort = zugänglicher Name).

**Das Tasten-Kästchen:**

- Inhalt `1` / `2` / `3` — die Belegung bleibt unverändert, sie wird nur sichtbar gemacht. **Nicht** die Board-Buchstaben F/A/X; übernommen wird die Form, nicht die Beschriftung.
- `inline-flex h-4 min-w-4 items-center justify-center rounded-xs bg-overlay px-1 font-mono text-xs leading-none` — `--overlay` als eigene, in jedem Zustand gleich bleibende Fläche. Das Kästchen bleibt dadurch auch auf dem gefüllten aktiven Eintrag eine lesbare Insel und braucht keine sechs eigenen Zustandsvarianten.
- **12px statt der 10px des Boards** — Untergrenze des Design-Systems und die neue Prüfung "keine willkürlichen Werte".
- Ziffernfarbe in der Zustandsfarbe (Board): `1` → `--rating-favorite` (7,67:1 auf `--overlay`), `2` → `--rating-album-worthy` (8,41:1), `3` → **`--danger-text #FF5A26`** (4,51:1). **Nicht** `--rating-rejected`: der Board-Ton erreicht auf `--overlay` nur 3,96:1 und ist hier Text. Das ist die bereits geltende `--danger`/`--danger-text`-Regel, keine neue Festlegung.
- `aria-hidden="true"` — sonst zerbricht der zugängliche Name.

**360px: warum die Einträge untereinander stehen.**

Rechnung für eine Reihe: 360 − 32 (`px-4`) − 16 (`p-2` des Containers) = 312px innen, minus 2 × `gap-3` = **288px für drei Einträge**. Ein Eintrag misst `px-3` (24) + Symbol 16 + `gap-1` (4) + Beschriftung + `gap-1` (4) + Kästchen 16 = 64 + Beschriftung; bei 12px Semi-Bold sind das ≈ 110 / 143 / 123px = **376px** plus 24px Abstände = 400px. Auch ohne Symbol und mit 8px Polsterung bleiben es 352px. **Drei Einträge mit sichtbarer Beschriftung und Kästchen passen bei 360px nicht nebeneinander** — und Kürzen der Beschriftung ist durch das Akzeptanzkriterium ausgeschlossen, horizontales Scrollen durch die Abnahme.

Festlegung: **`flex-col sm:flex-row`.** Unterhalb `sm:` steht jeder Eintrag als volle Zeile (`w-full justify-start`, Kästchen per `ml-auto` rechtsbündig), sichtbare Höhe **`h-11`** (44px, heißer Pfad — Allowlist-Eintrag bleibt), senkrechter Abstand `gap-3` (12px). Ab `sm:` die Board-Reihe: `h-8`, `tap-target` (nur kurze Achse — die Einträge sind breit genug), `gap-3`.

Das kostet auf dem Telefon ca. 60px Höhe gegenüber der heutigen umbrechenden Reihe. Getragen, und zwar aus dem Design-System selbst: Dichte "kippt bei Bedienelementen auf dem heißen Pfad und am Telefon generell". Der Nebeneffekt ist ein Gewinn — die drei Einträge stehen dann von oben nach unten in derselben Reihenfolge wie ihre Tasten 1/2/3, statt in einer je nach Breite unterschiedlich umbrechenden Reihe.

**Genau drei Schaltflächen** bleiben in der Gruppe (`toHaveCount(3)`); das Kästchen ist ein `<span>`, kein Bedienelement.

**Die Zeile "Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren" bleibt unverändert stehen.** Sie ist durch die Kästchen teilweise redundant, aber "es wird nichts entfernt" ist ein Akzeptanzkriterium, und der Pfeiltasten-Teil hat kein sichtbares Gegenstück. Gestaltung: `text-xs text-text-muted` (Metadatenzeile), nicht `text-sm text-text`.

### 5. Die Schrittnavigation

**Board-Navigationselement ab `sm:`**, `Stepper.tsx`:

| Board-Zustand | Fläche | Rand | Text |
|---|---|---|---|
| ruhend | `--surface` | 1px `--border-control` | `--text` |
| überfahren | `--overlay` | 1px `--border-control` | `--text-h` |
| aktiv | `--overlay` | **1,5px `--accent`** (anliegend) | `--accent`, `font-bold` |

Auch hier `--border-control` statt des Board-Rahmens `#2A2E3D`: das Element ist ein Bedienelement (Board-Abweichung 2, kein neuer Fall). Jede `hover:`-Variante bekommt eine `active:`-Variante daneben (`active:bg-border active:text-text`). Keine eigene Fokusdarstellung.

**Abbildung der vier vorhandenen Schrittbedeutungen auf die drei Board-Zustände:**

| Schrittbedeutung | Board-Zustand | Zusätzliches, nicht-farbliches Merkmal |
|---|---|---|
| aktuell | **aktiv** | `font-bold` + `aria-current="step"` (Farbe trägt es nie allein) |
| erledigt | ruhend | Glyphe = `<Icon name="check">` statt der Schrittnummer |
| ausstehend | ruhend | Glyphe = Schrittnummer |
| blockiert | ruhend | Glyphe = Schloss (Inline-SVG, dokumentierte Symbolsatz-Lücke), Beschriftung in `--text-muted`, `aria-disabled="true"`, `tabIndex={-1}`, daneben der unveränderte Grund-Popover-Trigger |

"aktuell" gewinnt weiterhin gegen "erledigt" (die Fallreihenfolge bleibt bedeutungstragend); dass ein Schritt erledigt ist, sagt dann der Haken.

**Maße und Layout ab `sm:`:** `rounded-md` (8px), `px-3 py-2` — 12/8px statt der 16/8px des Boards, damit die fünf ausgeschriebenen Beschriftungen ohne Kürzung in eine Reihe passen. Rechnung bei 1024px Fenster (Hülle `max-w-5xl`, `px-6` → 976px): Elementbreite = 24 (Polsterung) + 16 (Glyphe) + 4 (`gap-1`) + Beschriftung ⇒ 70 / 169 / 136 / 169 / 183 = 727px, plus vier Verbindungslinien und `gap-3` ⇒ ca. 775px. Passt. Bei kleineren Breiten sorgen `flex-1 basis-0 min-w-0` und eine **umbrechende, nie gekürzte** Beschriftung (`text-left`, kein `truncate`) dafür, dass die Reihe eine Reihe bleibt: Es entstehen zweizeilige Beschriftungen, kein horizontales Scrollen und nichts Abgeschnittenes. Die Glyphe (16px, `aria-hidden`) sitzt **innerhalb** des Nav-Elements, nicht mehr daneben.

Verbindungslinie zwischen den Elementen: `h-0.5 flex-1 bg-separator` (heute `bg-border` und damit praktisch unsichtbar). `h-0.5` ist eine Höhe, keine Abstandsstufe — von der neuen Abstandsprüfung nicht betroffen.

**Unterhalb `sm:`** bleibt alles wie heute (Entscheidung 6): die Marker-Darstellung (`size-8`, `rounded-md`, `tap-target-square`) plus die Orientierungszeile "Schritt 3 von 5: …". Fünf beschriftete Nav-Elemente passen bei 360px nicht nebeneinander, und horizontales Scrollen ist Ausschlusskriterium. Die Zeile bekommt `text-xs text-text-muted` statt `text-sm text-text` — sie ist Orientierung, nicht Inhalt.

**Keine Sidebar** (entschieden), die Leiste bleibt waagerecht und sticky; Kopfzeilenrand auf `--separator`.

### 6. Der unbestimmte Ladezustand der Fortschrittsanzeige

`ui/progress.tsx`, natives `<progress>` ohne `value` ⇒ `:indeterminate`.

**Darstellung:** Spur `--separator` (heute `--border`, 1,45:1 gegen `--bg` — genau der Befund "Statuspunkte und Linien verschwinden auf dem Grund"; jetzt 2,38:1). Im unbestimmten Zustand **volle Fläche in `--accent`** über die ganze Breite, mit dem bereits im Produkt etablierten Puls: `indeterminate:bg-accent indeterminate:animate-pulse motion-reduce:animate-none`, dazu die beiden Browser-Pseudo-Elemente (`::-webkit-progress-bar` auf `--accent`, `::-moz-progress-bar` neutralisiert), damit die Browser-Voreinstellung nicht durchschlägt. Höhe 8px, `rounded-xs` (4px) — unverändert.

**Bezug zur Bewegungsregel:** Das Design-System lässt ausschließlich Farb- und Deckkraftübergänge zu und verbietet Bewegung von Layout oder Position. Das wandernde Segment der Browser-Voreinstellung ist genau eine Positionsbewegung und fällt damit weg. `animate-pulse` ist eine reine Deckkraftanimation und dieselbe Mechanik wie Skeleton, Spinner und laufender Statuspunkt — es kommt **keine neue Bewegungsart** hinzu, nur eine weitere Aufrufstelle einer bereits zugelassenen.

**`prefers-reduced-motion`:** `motion-reduce:animate-none`, gleiche Behandlung wie an den drei bestehenden Stellen. Der Balken steht dann als volle Akzentfläche still. Das ist bewusst getragen, weil der Balken an **keiner** der drei Aufrufstellen (`ScanStepPage`, `AusschussStepPage`, `ClassificationSection`) allein steht: Über ihm steht jeweils eine Statuszeile mit `aria-live` bzw. der laufende `StatusDot`, die den Zustand "läuft" ausschreiben. Die Bedeutung hängt damit an Text, nicht an der Animation — was ohnehin die Grundregel ist. **Vorgabe an die Umsetzung:** Wenn eine der drei Aufrufstellen diese begleitende Statusaussage nicht hat, ist das ein Befund und wird dort ergänzt, statt den Balken um eine Bewegung zu erweitern.

**Nachweis:** In jsdom nicht belegbar (`:indeterminate` und die Pseudo-Elemente existieren dort nicht) — statische Prüfung, dass die Datei den Zustand behandelt, plus Sichtprüfung im Browser.

### 7. Vorgaben je Ansicht

**Projektweite Überschriftenleiter** (heute uneinheitlich — `CurateCategoriesPage` trägt `h1` und `h2` beide auf `text-xl`, bei 360px also gleich groß):

| Ebene | Utility | Verwendung |
|---|---|---|
| `h1` Seitenüberschrift | `text-xl sm:text-2xl` | jede Seite (Anmeldung: `text-2xl sm:text-3xl`) |
| `h2` Abschnitt | `text-lg` | Pipeline-Schritt, Statistik-Abschnitt, Tag in der Kuratierung |
| `h3` Untergruppe | `text-base` | Tageszeit-Cluster |
| `h4` kleinste Gruppe | `text-sm font-semibold` | Kategoriegruppe |
| Panel-/Tabellenkopf | `text-xs font-semibold uppercase tracking-wide` | Board-Rolle "Beschriftung" |

Erlaubte Abstandsstufen durchgängig `0/1/2/3/4/6/8/12/16`; die heutigen `gap-1.5`, `gap-2.5`, `gap-3.5`, `py-3.5`, `px-5`, `mt-5`, `py-10`, `px-8`, `px-10`, `p-0.5`, `mb-7` fallen weg.

| Ansicht | Überschrift | Container / Radius | Abstände | Was sich konkret ändert |
|---|---|---|---|---|
| **Anmeldung** (`LoginPage`) | `h1 text-2xl sm:text-3xl` | keine Karte (bleibt), Seite `px-4 sm:px-6 py-8` | Formular `gap-4`, Feldgruppe `gap-2`, Abstände `mb-6` | `px-8 py-10`→`px-4 sm:px-6 py-8`; `gap-3.5`→`gap-4`; `gap-1.5`→`gap-2`; `mb-7`→`mb-6`; Schaltfläche `h-[50px]`→`h-11 w-full`; Eingabefelder `h-12`→`h-11`. Verortungszeile `text-xs text-text-muted`. |
| **Projektliste** (`ProjectListPage`) | `h1 text-xl sm:text-2xl` | Zeilen-Karte `rounded-lg bg-elevated border-border` | Liste `gap-3`, Karteninhalt `px-4 py-3`, innen `gap-2` | Skeleton `rounded-xl`→`rounded-lg`; `gap-2.5`→`gap-2`; `px-4 py-3.5 sm:px-5`→`px-4 py-3`; Pfad `text-[10.5px]`→`font-mono text-xs`. Die Zeile bleibt **eine** Trefferfläche mit `min-h-11` (Trefferflächen-Regel 3, Allowlist-Eintrag mit dieser Begründung). |
| **Projektliste, Leerzustand** | `h2 text-lg` | Symbolkachel `size-16 rounded-md bg-elevated text-accent` | `px-4 py-8`, `gap-4` | `px-6 py-10`→`px-4 py-8`; `size-20`→`size-16`, `rounded-lg`→`rounded-md` (Icon-Kachel = 8px); `mb-6`/`mb-2` → ein `flex-col gap-4`; Schaltfläche `h-11 px-6`→ Standardmaß (kein heißer Pfad, kein `h-11`). |
| **Projekt anlegen** (`ProjectCreatePage`) | `h1 text-xl sm:text-2xl` | kein Panel (bleibt) | Seite `gap-6`, Formular `gap-4`, Feldgruppe `gap-2`, Aktionszeile `gap-3` | nur `gap-1.5`→`gap-2`; Beschriftungen `text-xs`. |
| **Projekt-Einstellungen** | `h1 text-xl sm:text-2xl` | Panel `rounded-lg border-border bg-surface p-4` | Seite `gap-6`, Panel innen `gap-4`, Zeilen `gap-3` | `rounded-xl`→`rounded-lg` (Panel = 12px); die zwei handgerollten Symbol-Schaltflächen → `<Button variant="ghost" size="icon">`. |
| **Projekt-Statistik** | `h1 text-xl sm:text-2xl`, `h2 text-lg` | Abschnitte ohne Karten-Chrome (bleibt), `border-t border-separator` | 12-Spalten-Raster `grid-cols-12 gap-x-3 gap-y-6` (bleibt), Abschnitte `pt-6`, Zeilen `py-2` | **`border-border/60` → `border-separator`** an Abschnitts-, Zeilen- und Tabellentrennern (heute 0,87:1, also faktisch keine Linie); Tabellenkopf in der Beschriftungsrolle; Kennzahlen in `font-mono`; die zwei handgerollten Symbol-Schaltflächen → `Button`. |
| **Fünf Pipeline-Schritte** (`ScanStepPage`, `AusschussStepPage`, `GateStepPage`, `KriterienStepPage`, `KuratierungStepPage`, `PipelineStepView`, `ClassificationSection`, `CloudVisionStatusList`, `StatusTag`) | `h2 text-lg` | Schrittinhalt ohne Panel; hervorgehobene Zeilen (Kostenschätzung) `rounded-md border-border bg-surface p-3` | Abschnitt `gap-3`, Kennzahlen-`dl` `gap-x-6 gap-y-1` bleibt, `gap-1.5`→`gap-2` | `gap-1.5`→`gap-2`; Fortschrittsspur `--separator`; `StatusDot` "kein Status" `bg-border`→`bg-separator`; Kennzahlenwerte `font-mono`. Keine Änderung an Inhalt, Reihenfolge oder Auslösern. |
| **Pipeline-Hülle** (`ProjectPipelineLayout`) | `h1 truncate text-xl sm:text-2xl` | — | `gap-6` | Pfadzeile `text-[10px]`→`font-mono text-xs` (willkürlicher Wert **und** unter 12px); Fußnavigation bleibt `flex-wrap gap-3`. |
| **Kategorie-Kuratierung** (`CurateCategoriesPage`) | `h1 text-xl sm:text-2xl`, `h2 text-lg` (Tag), `h3 text-base` (Tageszeit), `h4 text-sm font-semibold` (Kategorie) | Kacheln → `PhotoCard`; Leerplatz `rounded-lg border border-dashed border-separator` | Ebenen `gap-4`, Kachelraster `gap-3`, `gap-1.5`→`gap-2` | Die drei Überschriftenstufen werden erstmals unterscheidbar; hand-gebaute Kachel → `PhotoCard` mit `QualityMeter` und "Verwerfen" in der Fußzeile; gestrichelter Leerplatz auf `--separator`; die handgerollte Symbol-Schaltfläche → `Button`. Aufklapp-Zeile bleibt `min-h-11` (Listenzeile). |
| **Foto-Raster** (`PhotoGridPage`) | `h1 text-xl sm:text-2xl` | `PhotoCard`; Gate-Hinweis auf `ui/alert.tsx`-Konstruktion `rounded-md border-accent bg-elevated p-3` | Seite `gap-6`, Raster `gap-3`, Filterzeile `gap-2` | Kachel → `PhotoCard`: Kennzeichen wandert aus der Bildecke in den Kartenkörper, der `bg-bg/85`-Backdrop hinter dem Kennzeichen und der `pointer-events-none`-Kniff entfallen ersatzlos. Ecken-Trigger bleiben Geschwister der Bildfläche und behalten ihre `rounded-full`-Freigabe. Spaltenzahl 2/3/4 unverändert. |
| **Foto-Detail** (`PhotoDetailPage`) | `h1` existiert nicht (bleibt so — die Seite ist ein Bild, keine Textseite) | Bild `rounded-md` (Bildfläche = 8px), Vorschlagskasten `rounded-md border-accent bg-elevated p-3` | Seite `gap-4`, Aktionszeile `gap-3`, `gap-1.5`→`gap-2` | Bild `rounded-xl`→`rounded-md`; neue Bewertungsleiste (Abschnitt 4); Shortcut- und Zählzeile als `text-xs text-text-muted`; "Zurück"/"Weiter" bleiben heißer Pfad (`h-11 sm:h-8`, `gap-3`). |
| **Foto-Vergleich** (`PhotoComparePage`) | `h1 text-xl sm:text-2xl` | `PhotoCard` (ersetzt `rounded-xl border p-2`) | Raster `gap-3`, Zeilen in der Fußzeile `gap-2` | Kachel → `PhotoCard`, die zwei Bewertungszeilen ("Ich:" / "Andere:") ziehen in den Fußzeilen-Slot; `RatingBadge` behält dort sein neutrales "–" für "hat nicht bewertet". Rastersprünge 1/2/3 unverändert. |
| **Hülle** (`App.tsx`, `BrandMark`) | — | Kopfzeile `border-b border-separator bg-bg` | `px-4 sm:px-6 py-3`, `gap-3` | Kopfzeilenrand auf `--separator`; Wortmarke und Projekt-Link verlieren ihr `h-11` (kein heißer Pfad, keine Listenzeile) und tragen das Board-Maß mit `tap-target`; `gap-1`→`gap-2` zwischen den beiden Links (Mindestabstand zwischen fokussierbaren Elementen). |

**Vollrunde Formen** bleiben ausschließlich an der abschließenden Liste: Schalter-Spur/-Knauf, `StatusDot`, die drei Lade-Spinner und die runden Backdrops der beiden Popover-Trigger über einer Fotokachel. Es kommt keine neue Fundstelle hinzu.

### 8. Barrierefreiheit

**Was sich nicht ändern darf** (Vertragsfläche, wörtlich aus dem Architektur-Abschnitt und darüber hinaus geprüft):

- **Zugängliche Namen:** `Bewertung` (Gruppe), `Favorit` / `Album-würdig` / `Verwerfen` (exakt, ohne Zusatz), `Vorheriges Foto`, `Nächstes Foto`, `Alle Kategorien`, `Bewertungsdetails anzeigen`, `Schließen`, `Grund für Sperrung von <Schritt> anzeigen`, `Schritt N von 5: <Label>, <Status>`, `Fortschritt der Pipeline`, `Fotos werden geladen…`, `Projekte werden geladen…`, `Vorschlag übernehmen: <Pfad>`, `Verwerfen: <Pfad>`, `Unbewertet` und die drei `RatingBadge`-Namen.
- **Rollen und Struktur:** `banner`, `navigation`, `group`, `listitem` mit `a[href*="/photos/"]`, `dialog` über `aria-haspopup="dialog"`, `status` an den Ladelisten, `aria-live="polite"` an den Prozesszeilen, `aria-current="step"`, `aria-pressed` an den Bewertungseinträgen, `aria-expanded`/`aria-controls` an den Aufklapp-Zeilen der Kuratierung. Die Überschriften der Routenliste in `no-horizontal-scroll.spec.ts` bleiben wortgleich.
- **Elementanzahl:** exakt 3 Schaltflächen in der Bewertungsgruppe, 5 Einträge im Stepper, `EXPECTED_CONTROL_COUNT = 6`.
- **Fokusreihenfolge:** ergibt sich weiterhin allein aus der DOM-Reihenfolge, kein `tabindex > 0`. In der Foto-Karte bleibt sie Bild-Link → Ecken-Trigger → Fußzeilen-Aktion; Kennzeichen und Dateiname sind nicht fokussierbar und schieben sich zwischen Bild und Fußzeile, ohne die Reihenfolge der Bedienelemente zu verändern. Der Skip-Link bleibt das erste fokussierbare Element des Steppers. Beim `PhotoCard`-Umbau darf der Ecken-Trigger nicht vom Geschwister zum Kind der beschneidenden Bildfläche werden — das würde still seine Trefferfläche abschneiden.

**Wie die neuen sichtbaren Beschriftungen eingebunden werden, ohne den zugänglichen Namen zu verfälschen:**

- **Tasten-Kästchen `1`/`2`/`3`: `aria-hidden="true"`.** Ohne das lautete der Name "Favorit 1" und die `exact: true`-Prüfungen brechen. Die Tastenbelegung ist für Screenreader-Nutzer bereits über die Shortcut-Zeile im Text der Seite verfügbar; das Kästchen ist eine rein visuelle Wiederholung.
- **Sichtbare Beschriftung der Bewertungseinträge = wortgleich mit dem `aria-label`.** Damit ist WCAG 2.5.3 "Label in Name" erfüllt und Sprachsteuerung ("Klick Favorit") funktioniert.
- **Kennzeichentext auf der Foto-Karte:** Das `aria-label` des `RatingBadge` bleibt **unverändert** (`Favorit` / `Album-würdig` / `Verworfen` / `Vorschlag: …` / `Unbewertet`); der sichtbare Text ist wortgleich, das Symbol bleibt `aria-hidden`. Kein zusätzliches `role`, keine zweite Nennung.
- **Statuszeile "Neu":** reiner Text in `--text-muted`, **kein** `aria-label`, **kein** `RatingBadge`. Der Zustand "unbewertet" bleibt an seinen übrigen Aufrufstellen (Vergleichsansicht) über das "–"-Badge mit `aria-label="Unbewertet"` erhalten.
- **Dateiname:** regulärer Textknoten **außerhalb** des Kachel-Links, nicht `aria-hidden` (er ist Inhalt) und nicht in ein `aria-label` eingebaut. Der Name des Links bleibt der `alt`-Text des Bildes; der Name der Fußzeilen-Aktion bleibt `… : <relative_path>`. Es entsteht keine Doppelvorlesung, weil beide Elemente eigene, unterschiedliche Rollen haben.
- **Schrittbeschriftung im Nav-Element:** zieht in das Element hinein, bleibt `aria-hidden="true"`; der Name kommt weiterhin vollständig aus dem `aria-label` und enthält das sichtbare Wort. Glyphe (Nummer/Haken/Schloss) bleibt `aria-hidden`.
- **Kein neues `role`, kein neues Landmark, keine neue Live-Region.** Diese Spec ändert Darstellung; jede zusätzliche Semantik wäre die verbotene Funktionserweiterung.

**Kontrast — was die Umstellung nachweislich verbessert:** Trennlinien von 0,87–1,45:1 auf 2,38:1 (`--separator`), der Statuspunkt "kein Status" von 1,45:1 auf 2,38:1, das Kennzeichen der aussortierten Karte von weißer Schrift (3,55:1) bereits seit Stufe 1 auf dunkle Tinte (5,51:1). **Was ungeprüft bleibt und bewusst so bleibt:** die Kante der Foto-Karte (`--border`, 1,17–1,45:1) als reine Dekorationslinie neben der tragenden Flächenstufe.

**Trefferflächen, hart:** heißer Pfad (Bewertungseinträge, Weiter/Zurück, Kategorie-Zuordnung) am Telefon **sichtbar** ≥ 44px; zwischen aufgespannten Trefferflächen **immer** 12px; zwischen fokussierbaren Elementen ≥ 8px; keine Aufspannung innerhalb eines `overflow-hidden`-Containers.

**Ergänzung zur `h-11`-Liste:** Neben "heißer Pfad" und "Zeilenhöhe zeilenweiser Listen" braucht sie eine **dritte** Kategorie — *Eingabefelder und Kontrollkästchen*. Ein ersetztes Element trägt keine Pseudo-Elemente und löst seine Trefferfläche laut Design-System ausschließlich über die sichtbare Zeilenhöhe. Ohne diesen Eintrag zwingt die neue Prüfung die Anmeldefelder unter 44px, also genau gegen die Regel, die sie absichern soll. Betroffen: die beiden `Input`-Felder und die Absende-Schaltfläche der Anmeldung (letztere als "einzige Aktion des Bildschirms, einhändig bedient").

### Design-System-Nachtrag (Etappe 5)

In `specs/architecture/0004-design-system.md` und im Skill `.claude/skills/design-system/SKILL.md` nachzutragen — **nicht vorab, sondern in Etappe 5**: das Token `--separator` samt Dreiteilung `--border` / `--separator` / `--border-control`; die Überschriftenleiter aus Abschnitt 7; die vier neuen statischen Regeln; die achte Board-Abweichung aus Entscheidung 4; die dritte `h-11`-Kategorie; die neuen Bausteine `PhotoCard`, Bewertungsleiste, Board-Navigationselement, unbestimmter Fortschritt; und unter "Bekannte Lücken" der nachgerechnete Befund, dass Favorit und Album-würdig in Graustufen bei 1,08:1 liegen und ihre Unterscheidung ausschließlich über Wort und Symbolsilhouette tragen, sowie dass der Board-Kartenzustand "ausgewählt" bewusst noch nicht umgesetzt ist.

## Teststrategie

Diese Spec ändert Darstellung, nicht Verhalten — und genau daraus folgt ihr Testrisiko: Die vorhandene Frontend-Suite selektiert konventionsgemäß über Rollen, `aria-*` und semantische `data-*` und ist gegenüber einer reinen Umgestaltung **blind**. Das ist gewollt und bleibt so; es heißt aber, dass ein funktionaler Verlust hier nicht von selbst rot wird. Die Strategie besteht deshalb aus drei Teilen: **neue Logik wird testgetrieben gebaut** (Etappen 1–3), **die Formsprache wird statisch geprüft statt besichtigt** (das Netz), und **die bestehende Suite wird als Regressionsnetz bewusst unangetastet gelassen** (Etappe 4).

### Arbeitsteilung der Ebenen

| Ebene | Trägt in dieser Spec | Trägt hier ausdrücklich **nicht** |
|---|---|---|
| `vitest` + Testing Library (jsdom) | DOM-Struktur, Rollen, zugängliche Namen, Elementanzahl, `data-*`-Zustände, Interaktion, Modul-Logik (`scrollLock`) | alles Gerechnete, alles Responsive, jede Farb-/Maßaussage |
| `designSystem.contract.test.ts` (vitest, Umgebung `node`) | Kontrastzeile `--separator`, Abstandsskala, willkürliche Werte, Deckkraft-Modifikatoren, `rounded-full`, `opacity-*`, `h-11`, Behandlung des unbestimmten Fortschritts | Wirkung im Browser |
| Playwright (`e2e/`) | echte Geometrie bei 360px: kein waagerechtes Scrollen, Treffbarkeit 44px, Spaltenleiter, Sticky-Verhalten, Popover-Lage | Aussehen, Farbwerte, Graustufen |
| Sicht-/Ad-hoc-Prüfung | Board-Treue, Graustufen-Abnahme, unbestimmter Fortschritt | nichts, was auf einer der drei Ebenen prüfbar wäre |

**Harte Regel für diese Spec:** `sm:`-Verhalten (`flex-col sm:flex-row`, `p-2 sm:p-3`, `text-xl sm:text-2xl`) wird in jsdom **nie** geprüft — auch nicht ersatzweise über `toHaveClass('sm:flex-row')`. Eine solche Zusicherung prüft die Schreibweise, nicht die Wirkung, und wäre zugleich die verbotene CSS-Assertion im Komponententest. Zuständig ist Playwright bei 360px; wo Playwright es nicht misst, ist es Sichtprüfung und wird als solche benannt.

**Folgerung für die Schrittnavigation und die Bewertungsleiste:** Beide Umbrüche entstehen über Utilities auf **einem** DOM-Baum, nicht über zwei parallele Teilbäume (`hidden sm:flex` neben `flex sm:hidden`). Doppelte Markup-Zweige würden Rollen, Namen und Elementanzahl verdoppeln und damit sowohl `Stepper.test.tsx` als auch `EXPECTED_CONTROL_COUNT = 6` und `toHaveCount(3)` in den e2e-Specs brechen. Abgesichert wird das durch exakte Kardinalitäts-Assertionen (5 Schritte, 3 Bewertungseinträge), die bereits bestehen und unverändert grün bleiben müssen.

### Etappe 1a — `lib/scrollLock.ts` (echte Logik, volle Abdeckung)

Neu: `frontend/src/lib/scrollLock.test.ts`, jsdom, Unit-Ebene ohne React. Pflichtfälle, vollständig — das Modul ist klein, hat Reihenfolge- und Doppelaufruf-Semantik und ist der einzige Ort, an dem der heutige Fehler reproduzierbar ist:

1. **0 → 1:** Ausgangswert (leer) wird gesichert, `document.body.style.overflow` steht auf `hidden`.
2. **Zwei Sperren, Freigabe in Anlegereihenfolge (A, dann B):** nach der ersten Freigabe steht weiterhin `hidden`; erst die zweite stellt wieder her.
3. **Zwei Sperren, Freigabe in umgekehrter Reihenfolge (B, dann A):** identisches Ergebnis. Das ist der heute brechende Fall und der Grund des ganzen Umbaus.
4. **Vorbelegter Ausgangswert:** steht vor der ersten Sperre `overflow: scroll`, ist nach der letzten Freigabe wieder genau `scroll` gesetzt — nicht der leere String.
5. **Idempotenz der Freigabe:** dieselbe Freigabefunktion zweimal aufgerufen zählt nur einmal herunter. Nachweis in zwei Richtungen, sonst belegt er nichts: (a) A zweimal freigeben, während B noch offen ist → weiterhin `hidden`; (b) danach B freigeben → wiederhergestellt. Ohne (a) bestünde der Test auch bei einem nackten `count--`. React ruft Effekt-Aufräumungen im StrictMode doppelt auf (`main.tsx` rendert unter `StrictMode`); im Test greift das nicht, der Doppelaufruf wird deshalb hier direkt provoziert.
6. **`resetBodyScrollLock()`** setzt Zähler *und* gesicherten Wert zurück *und* räumt `body.style.overflow` ab; eine danach angelegte Sperre sichert wieder frisch. Ohne die dritte Zusage leckt `hidden` in die nächste Testdatei.

Auf Integrationsebene (`frontend/src/components/ui/dialog.test.tsx`, bestehende Datei): **zwei gleichzeitig offene Dialoge, beide Schließreihenfolgen**, über tatsächlich gerendertes React statt über die Modul-API — nur so ist belegt, dass `dialog.tsx` den Zähler wirklich benutzt. Der bestehende Test "keeps the background from scrolling while open" bleibt wortgleich. Der `afterEach`-Aufruf in `frontend/src/setupTests.ts` ist Testhygiene und keine Produktions-API; das gehört als Kommentar an die Aufrufstelle.

### Etappe 1b — `allowlistedOccurrences(needle, entries)`

Der Helfer ist kein Beiwerk: Er trägt am Ende vier statische Regeln, und im grünen Zustand liefern alle drei Fehlerklassen die leere Menge — die Produktivnutzung belegt also **nichts** über seine Fehlererkennung. Er bekommt deshalb eigene Selbsttests, aber eng begrenzte.

**Entwurfsvorgabe, ohne die es nicht geht:** Der Helfer nimmt die zu durchsuchenden Dateien als Parameter (`allowlistedOccurrences(needle, entries, files = sourceFiles)`). Getestet wird ausschließlich gegen **synthetische, im Test literal geschriebene** `files`-Listen — kein Dateisystem, keine Fixture-Dateien, keine temporären Verzeichnisse.

**Ort:** derselbe `frontend/src/designSystem.contract.test.ts`, eigener `describe`-Block. Nicht in eine eigene Datei auslagern — jede Datei unter `src/**` außer `SELF_FILE` wird vom Vertragstest selbst gescannt, und ein Helfer, der die Suchmuster (`text-[`, `rounded-full`, `/60`) als Literale trägt, würde die Regeln auslösen, die er implementiert.

Pflichtfälle (acht, mehr nicht):

1. Fundstelle ohne passenden Eintrag → gemeldet, mit Dateilabel und Zeilennummer im Text.
2. Fundstelle mit passendem Eintrag (Ausschnitt ist Teilzeichenkette der Zeile) → nicht gemeldet.
3. **Zweite Fundstelle in einer bereits gelisteten Datei**, deren Zeile nicht zum Ausschnitt passt → gemeldet. Das ist der eigentliche Zweck des Umbaus und zugleich sein permanenter Rot-Nachweis: Die heutige dateiweise Prüfung wäre hier grün. Ein separater, einmaliger Rot-Nachweis durch Anfassen einer echten Quelldatei entfällt damit.
4. Eintrag ohne jede Fundstelle (verwaiste Freigabe) → gemeldet.
5. Ausschnitt, der nur aus dem Suchbegriff selbst besteht → gemeldet, **auch wenn** es zu ihm passende Fundstellen gibt (sonst ließe sich Datei-Granularität still wiederherstellen).
6. Fundstelle nur in einem Zeilenkommentar → nicht gemeldet.
7. **Zeilentreue:** Eine Fundstelle **nach** einem mehrzeiligen Blockkommentar wird mit ihrer tatsächlichen Zeilennummer gemeldet. Direkt daneben eine Zusicherung auf `stripComments` selbst: Zeilenanzahl der Ausgabe = Zeilenanzahl der Eingabe.
8. Leere Eingabemenge → keine Meldung, aber auch kein stilles Bestehen einer Regel mit leerer Kandidatenmenge (siehe nächster Abschnitt).

**Nicht getestet** werden: das Einsammeln der Dateien (`walk`), die Inhalte der Freigabelisten selbst, und die Formatierung der Meldungstexte über die zwei geforderten Bestandteile hinaus.

### Das Netz — wie statische Prüfungen selbst abgesichert werden

Eine statische Prüfung hat genau einen ernsten Fehlermodus: Sie findet nichts und besteht deswegen. Jede der neuen Regeln bekommt deshalb zwei Dinge:

- **Eine Positiv-Gegenprobe im Produktivlauf**: Die Menge der überhaupt betrachteten Kandidaten ist nachweislich nicht leer (die Abstandsregel findet reichlich zulässige `gap-3`/`p-4`, die Deckkraftregel findet die drei freigegebenen Abdunklungen). Ein kaputter regulärer Ausdruck fällt damit auf, statt alles durchzuwinken. Dieselbe Vorkehrung tragen die bestehenden Blöcke bereits, sie wird hier nur fortgeschrieben.
- **Einen tabellengetriebenen Mikrotest des Erkenners gegen synthetische Zeilen.** Dafür wird der je Regel matchende Teil als reine Funktion herausgezogen (z.B. `spacingUtilities(line)`), statt den regulären Ausdruck inline in der Assertion zu vergraben.

Verbindliche Fälle je Regel:

**1. Abstandsskala.** Erkannt werden müssen `gap-1.5`, `gap-2.5`, `gap-3.5`, `py-3.5`, `px-5`, `mt-5`, `py-10`, `px-8`, `p-0.5`, `mb-7`, ebenso mit Variantenpräfix (`sm:gap-1.5`, `hover:py-3.5`) und als negativer Rand (`-mt-5`). **Nicht** erkannt werden dürfen: die acht zulässigen Stufen, sowie `h-11`, `size-8`, `h-0.5`, `min-w-6`, `w-full`, `max-w-5xl` — die Regel ist eine Abstands-, keine Größenregel, und ein Fehlalarm hier zwingt die Umsetzung dazu, sie wieder aufzuweichen.

**2. Keine willkürlichen Werte.** Erkannt: `text-[10px]`, `text-[10.5px]`, `h-[50px]`, `w-[240px]`, `gap-[3px]`, `p-[7px]`. **Nicht** erkannt: die arbiträren *Varianten* in `ui/progress.tsx` (`[&::-webkit-progress-bar]:bg-accent`) und `data-[state=open]:`-Selektoren — sie tragen ebenfalls eckige Klammern, sind aber keine willkürlichen Werte. Die drei Freigaben (`ui/popover.tsx`, `ui/checkbox.tsx`, `ui/dialog.tsx`) laufen über den Fundstellen-Helfer und tragen je eine Begründung.

**3. Keine Deckkraft-Modifikatoren auf Farb-Utilities.** Erkannt: `border-border/60`, `bg-border/60`, `text-text/70`. **Nicht** erkannt: Brüche, die keine Deckkraft sind — `w-1/2`, `h-1/3`, `basis-1/2`. Der Erkenner ist deshalb an die Farb-Namensräume zu binden (`bg-`/`text-`/`border-`/`fill-`/`stroke-` + Token-Name), nicht an das Vorkommen eines Schrägstrichs. Freigegeben bleiben genau die drei benannten Abdunklungen.

**4. `opacity-*` fundstellengenau — die vierte Prüfung, über die drei des Architektur-Abschnitts hinaus.** Begründung: Entscheidung 4 ("die Karte tritt zurück, die Bedeutungsträger nicht") setzt ADR 0055 Abweichung 7 um und ist die riskanteste Einzelentscheidung dieser Spec — ein späteres `opacity-40` am Kartenkörper statt am `<a>` drückt Kennzeichen und Dateinamen wieder unter die Kontrastschwelle, ohne dass irgendetwas rot wird. Der Graustufen-Lauf ist ein einmaliger Ad-hoc-Lauf und trägt das nicht. Die Regel ist billig, weil der Helfer bereits existiert: `opacity-` nur an gelisteten Fundstellen — heute `ui/button.tsx` (`disabled:opacity-40`, `hover:opacity-85`/`active:opacity-70`), `components/Stepper.tsx` (blockierte Beschriftung), `components/RatingButtons.tsx` (aktiver Eintrag), neu die eine Zeile in `PhotoCard.tsx`, deren Ausschnitt das `href`-tragende Element zeigt.

**Der unbestimmte Fortschritt** wird nicht per Zeichenkettensuche "behandelt der Zustand?" geprüft — das wäre eine Zusicherung über die Schreibweise. Genutzt wird stattdessen der bereits vorhandene stärkste Mechanismus des Vertragstests: der **tatsächliche Tailwind-Lauf** (`build([kandidat]) !== build([])`) belegt, dass `indeterminate:bg-accent` und `motion-reduce:animate-none` überhaupt eine Regel erzeugen — eine unbekannte Variante ist in Tailwind kein Buildfehler und bliebe sonst still wirkungslos. Dazu eine Fundstellenprüfung, dass `ui/progress.tsx` die Spur nicht mehr auf `bg-border` legt. Die *Darstellung* bleibt Sichtprüfung; `:indeterminate` und die Browser-Pseudo-Elemente existieren in jsdom nicht.

**Die Kontrastzeile `--separator`** folgt dem bestehenden Muster: Der Erwartungswert wird im Test gerechnet, nie abgeschrieben; die vier Zahlen aus dem UI/UX-Abschnitt sind Beleg, nicht Eingabe. Zugesichert wird der Korridor gegen `--bg` und `--surface` (≥ 2,0), die beiden übrigen Spalten sind nachrichtlich und tragen keine Schwelle.

### Etappe 3 — die drei zusammengesetzten Bausteine

**`frontend/src/components/PhotoCard.test.tsx` (neu).** Keine CSS-Assertion; geprüft wird über `data-rating-status`, `data-struck`, Rollen und sichtbaren Text. Pflicht:

- **Tabellengetrieben über die vier Zustände** (neu, Favorit, Album-würdig, aussortiert), nach der im Projekt etablierten Form der *paarweisen Verschiedenheit*: `data-rating-status`, sichtbarer Kennzeichentext und `data-icon` sind über die Zustände paarweise verschieden. Vier abgeschriebene Einzelfälle wären dieselbe Aussage mit mehr Zeilen und weniger Schärfe.
- **`data-struck`** ausschließlich im aussortierten Zustand.
- **Zustand "neu"** trägt den Text `Neu`, **kein** Badge und **kein** Element mit dem zugänglichen Namen `Unbewertet` — das ist der Prüfsatz zu Entscheidung 3 und verhindert, dass das "–"-Badge hier zurückkehrt.
- **e2e-Vertragsfläche**: Die Karte rendert als `listitem`, das ein `a[href*="/photos/"]` enthält.
- **Der Ecken-Slot ist Geschwister, nicht Kind des `<a>`** — `link.contains(trigger) === false`, `item.contains(trigger) === true`. Das ist die aus `PhotoGridPage.test.tsx` bekannte Zusicherung, die mit dem Baustein eine Ebene nach unten wandert; sie deckt zugleich den Fallstrick "`tap-target` nie in einen beschneidenden Container" auf Strukturebene ab.
- **Dateiname**: nur der Basisname (Eingabe `2024/07/IMG_0042.jpg` → sichtbar `IMG_0042.jpg`, der Ordnerteil kommt nicht vor), steht **außerhalb** des `<a>`, ist nicht `aria-hidden` und verändert den zugänglichen Namen des Kachel-Links nicht (der bleibt der `alt`-Text). Dazu der im Abschnitt "Security" geforderte Textknoten-Test — beide Zusagen liegen in derselben Datei und dürfen nicht gegeneinander wegoptimiert werden.
- **Fußzeilen-Slot**: übergebene Kinder werden gerendert und liegen nicht im `<a>`.
- **Kein `selected`, kein `data-selected`** — der fünfte Board-Zustand wird weder gebaut noch getestet (Entscheidung 5).

Testdaten nach bestehender Konvention: kleine literale Objekte in der Testdatei, keine geteilte Fixture-Datei.

**`RatingButtons.test.tsx` (bestehend, erweitert).** Die bestehenden sieben Fälle bleiben unverändert — sie sind der Nachweis "keine funktionalen Verluste" für diesen Baustein. Neu:

- `getByRole('button', { name: 'Favorit', exact: true })` (und die zwei anderen) findet weiterhin genau ein Element. Das ist die Zusicherung, dass das Tasten-Kästchen wirklich `aria-hidden` ist — ohne sie hieße der Name "Favorit 1" und der e2e-Vertrag bräche erst in CI.
- Genau **drei** Schaltflächen in der Gruppe; das Kästchen ist kein Bedienelement.
- Jeder Eintrag zeigt sichtbar seine Beschriftung.

**Neue Fehlerklasse, die diese Spec erst erzeugt: ein Kästchen, das lügt.** Die Ziffer steht in `RatingButtons`, die Belegung in `PhotoDetailPage` — sie können auseinanderlaufen, ohne dass irgendein bestehender Test etwas merkt. Pflicht daher in `frontend/src/pages/PhotoDetailPage.test.tsx`: der heutige Einzelfall "sets a rating via keyboard shortcut '1'" wird zur **Tabelle über alle drei Tasten**, und je Zeile wird zusätzlich zugesichert, dass die Schaltfläche des ausgelösten Status genau diese Ziffer sichtbar trägt. Ein Test, der nur die Anwesenheit der Ziffern prüft, erfüllt das nicht.

**`Stepper.test.tsx` (bestehend, erweitert).** Die beiden Zustandstests bleiben tragend (`data-step-state`, `aria-current`, `aria-disabled`, paarweise Verschiedenheit). Neu: die sichtbare Schrittbeschriftung zieht ins Nav-Element und bleibt `aria-hidden` — zugesichert wird, dass der zugängliche Name unverändert vollständig aus dem `aria-label` kommt (`Schritt N von 5: <Label>, <Status>`, wörtlich) und dass es weiterhin **genau fünf** Listeneinträge gibt. Der bestehende Test auf `size-8`/`tap-target-square` bleibt die einzige Klassen-Assertion dieser Datei — er sichert die Trefferfläche unterhalb `sm:`, die laut Entscheidung 6 unverändert bleibt, und wird nicht um weitere Klassennamen erweitert.

### Etappe 4 — Regressionsabsicherung: der Testdiff ist der Nachweis

"Jede Ansicht bleibt funktional identisch" ist das riskanteste Kriterium der Story und lässt sich nicht durch *neue* Tests absichern — es wird durch die **bestehenden** abgesichert, und zwar nur dann, wenn sie unangetastet bleiben. Verbindlich:

1. **Am Ende jedes Teilschritts (4a–4d) läuft `npx vitest run` vollständig grün, ohne dass eine bestehende Testdatei angefasst wurde.** Wo das nicht gelingt, ist die Ursache ein Befund, keine Testpflege.
2. **Jede Änderung an einer bestehenden `*.test.tsx` gilt bis zum Beleg des Gegenteils als funktionaler Verlust.** Sie braucht eine einzeilige Begründung in der Commit-Nachricht, und die PR-Beschreibung listet die angefassten Testdateien mit Grund auf. Das ist der Prüfsatz, den ein Reviewer tatsächlich lesen kann — der Produktivdiff dieser Spec ist dafür zu groß.
3. **Genau ein Wegfall ist vorab bekannt und genehmigt:** `PhotoGridPage.test.tsx`, "keeps the decorative rating-badge overlay pointer-events-none so clicks fall through to the tile link". Der abgesicherte Mechanismus hört auf zu existieren (das Kennzeichen verlässt die Bildecke). Der Test wird **ersetzt, nicht gelöscht**: An seine Stelle tritt die Zusicherung, dass Kennzeichen und Dateiname nicht innerhalb des `<a>` liegen und der Ecken-Trigger weiterhin dessen Geschwister ist. Ein ersatzloses Streichen wäre der Verlust der Zusage, nicht ihre Erfüllung.
4. **Die drei Foto-Ansichten behalten ihre eigenen Integrationstests.** Die vier Kartenzustände werden nicht in `PhotoGridPage.test.tsx`, `CurateCategoriesPage.test.tsx` und `PhotoComparePage.test.tsx` wiederholt — dafür gibt es `PhotoCard.test.tsx`. Die Seitentests prüfen weiterhin ihre eigene Sache: Kachelanzahl, Filter, "Übernehmen"/"Verwerfen", Popover-Trigger, die beiden Bewertungszeilen des Vergleichs.
5. **Etappe 4 hat keinen eigenen Rot-Schritt aus Komponententests** — ihr roter Ausgangspunkt sind die vier statischen Prüfungen aus dem Netz, die nach Etappe 2 rot stehen und Ansicht für Ansicht grün werden. Das ist der TDD-Zyklus dieser Etappe, und er ist in der Commit-Reihenfolge sichtbar zu machen.

### Etappe 5 — Browser-Ebene

**Der bestehende e2e-Satz bleibt unverändert und muss grün sein** — er ist hier kein Beiwerk, sondern trägt vier Akzeptanzkriterien allein: `no-horizontal-scroll` (360px), `tap-targets` (44px auf dem heißen Pfad, `EXPECTED_CONTROL_COUNT = 6` bleibt 6), `grid-columns` (2/3/4 Spalten, gleich breite Kacheln je Zeile — die `PhotoCard` darf die Leiter nicht verschieben), `sticky-header`, `popover-position`, `empty-and-error-states`.

**Eine Ergänzung ist Pflicht, ein neuer Spec nicht.** Der Routensatz von `e2e/tests/no-horizontal-scroll.spec.ts` enthält heute weder `/projects/:id/photos/:photoId` noch `/projects/:id/compare` — also ausgerechnet die Detailseite, auf der die neue Bewertungsleiste laut eigener Rechnung 400px bräuchte und deshalb umbricht, und die Vergleichsansicht, die auf `PhotoCard` umgestellt wird. Beide Routen werden der bestehenden Tabelle hinzugefügt; das Aufnahmekriterium ist erfüllt (echte Geometrie, in jsdom prinzipiell unprüfbar), und es entsteht kein zweiter Wahrheitsstand.

- Vergleich: Vorbedingung wie gehabt über die Überschrift `Vergleich`.
- Detailseite: Sie hat bewusst **kein** `h1` (siehe UI/UX-Abschnitt), die Überschriften-Vorbedingung greift dort also nicht. Ersatz: `getByRole('group', { name: 'Bewertung' })` ist sichtbar, plus die vorhandene Mindesthöhe des Inhaltsbereichs. Eine Route ohne wirksame Vorbedingung wäre genau der immer-grüne Spec, den das Testkonzept ausschließt.
- **Rot-Nachweis für die beiden neuen Zeilen** nach der Regel des Testkonzepts: einmal lokal ein 500px breites Element auf der Detailseite einfügen, den roten Lauf samt genannter Fundstelle in der PR-Beschreibung belegen.

**Graustufen-Abnahme** bleibt ein Ad-hoc-Lauf (`html { filter: grayscale(1) }` an Foto-Raster und Bewertungsleiste) und wird **nicht** zum Dauertest: Die nachrechenbare Hälfte der Zusage liegt bereits im Kontrast-Block des Vertragstests, und ein Referenzbildvergleich ist eine eigene, hier nicht geführte Diskussion. Abnahmekriterium ist das im UI/UX-Abschnitt festgelegte: Wort und Symbolsilhouette müssen sich ohne Farbfläche ablesen lassen; abgeschnittene Kennzeichentexte sind ein Fehlschlag, kein Randfall.

**Screenshots** aller vierzehn Ansichten in 360px und 1280px über den `browse-app`-Skill sind Abnahmebeleg, kein Testnachweis — sie stehen in der PR-Beschreibung, nicht im Repository, und entstehen ausschließlich gegen den synthetischen Demo-Stand (siehe "Security").

### Was bewusst nicht getestet wird

- **Aussehen einzelner Komponenten** (Farbwert, Radius, Polsterung, Deckkraftwirkung): Der Vertragstest prüft die Regeln, die Sichtprüfung das Ergebnis. Komponententests bekommen weiterhin keine CSS-Assertionen — die Ausnahme `tap-target`/`size-8` im `Stepper` bleibt die einzige und wird nicht ausgeweitet.
- **Responsives Umschalten** in jsdom (siehe oben).
- **Die Darstellung des unbestimmten Fortschritts** — statisch geprüft, dass die Zustandsbehandlung eine Regel erzeugt; die Wirkung ist Sichtprüfung.
- **Der nicht gebaute Kartenzustand "ausgewählt"** — keine Prop, kein Test, keine Vorbereitung.
- **Die `truncate`-Wirkung auf den Dateinamen** (Auslassungspunkte, sichtbar bleibende Durchstreichung): Die Folge — kein waagerechtes Scrollen bei 360px — ist e2e-geprüft, die Ursache nicht.
- **Pixelbasierter Referenzbildvergleich** — unverändert außerhalb dieser Spec.
- **Die Anmeldeseite in `no-horizontal-scroll`**: Der Spec-Satz läuft mit gespeichertem Anmeldezustand und würde von `/login` weggeleitet. Bleibt eine bewusste Lücke, gedeckt durch Sichtprüfung bei 360px (die Seite ändert `h-[50px]` → `h-11` und ihre Polsterung).

### Testkonzept-Nachtrag (Etappe 5)

Vier Punkte gehen über diesen Branch hinaus und sind in `specs/architecture/0002-testkonzept.md` nachzutragen — nicht vorab, sondern in Etappe 5:

1. **Frontend-Sektion, neuer Eintrag:** Muster "fundstellengenaue Freigabeliste" — drei Fehlerklassen, Dateiliste als Parameter, Selbsttests gegen synthetische Eingaben, und die Regel, dass ein solcher Helfer im vom Scan ausgenommenen `SELF_FILE` wohnt.
2. **Frontend-Sektion, neue Konvention:** modulweiter Zustand im Frontend (erstmals mit `lib/scrollLock.ts`) braucht eine `reset*()`-Funktion, die `setupTests.ts` per `afterEach` ruft, und diese Funktion räumt Zähler, gesicherten Wert und den beeinflussten DOM-Zustand ab. Dazu die Notiz, dass StrictMode-Doppel-Aufräumungen im Test nicht greifen und Idempotenz deshalb direkt provoziert werden muss.
3. **E2E-Sektion, Tabelle "Umfang":** `no-horizontal-scroll` erhält zwei Routen; die Detailseite nutzt eine Nicht-Überschriften-Vorbedingung (`group`-Rolle "Bewertung"), was als zulässige zweite Form der Vorbedingungs-Assertion festzuhalten ist.
4. **"Bekannte Lücken":** Anmeldeseite ist von `no-horizontal-scroll` nicht erfasst (gespeicherter Anmeldezustand leitet weg); Graustufen-Unterscheidbarkeit bleibt manuell; die Darstellung des unbestimmten Fortschritts ist nur statisch belegt.

Nicht nachzutragen: alles Übrige dieser Spec wendet bestehende Strategie an (Rollen-/`data-*`-Selektoren, keine CSS-Assertionen im Komponententest, Vertragstest als einzige CSS-Ebene, Fixture-Konvention, e2e-Aufnahmekriterium).

## Security

**Einstufung: sicherheitsrelevant, mit engem Zuschnitt.** Die Story ist reines Frontend-Styling ohne Backend-, Auth- oder Schnittstellenänderung. Sicherheitsrelevant ist genau ein Punkt: Mit dem Dateinamen auf der Fotokachel wird extern entstandener Text an einer Stelle sichtbar, an der er bisher nicht stand. Der Fall ist im Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, Angriffsfläche "Frontend") bereits benannt und die Gegenmaßnahme dort bereits festgelegt — diese Spec führt sie fort, sie erfindet nichts Neues.

### 1. Der Dateiname als Eingabe von außen

**Herkunft:** `PhotoOut.relative_path` wird im Backend aus dem WebDAV-Walk der OpenCloud befüllt (`worker.py`), stammt also aus keiner kontrollierten Aufzählung. Die Vertrauensgrenze dazu steht im Sicherheitskonzept: OpenCloud ist Daniels eigene Instanz und wird als *potenziell fehlerhaft antwortend*, nicht als *aktiv böswillig* behandelt.

**Kein Erstkontakt:** Derselbe Wert wird heute bereits in allen drei Foto-Ansichten gerendert — als `alt` (`PhotoGridPage`, `CurateCategoriesPage`, `PhotoComparePage`, `PhotoDetailPage`) und in `aria-label`-Vorlagen (`Vorschlag übernehmen: …`, `Verwerfen: …`). Neu ist allein die **Sichtbarkeit als Fließtext**, nicht die Eingabe.

**Warum der Punkt trotzdem nicht abgewinkt wird:** Seit ADR 0005 liegt das Session-Token in `localStorage`. Das Verbot von `dangerouslySetInnerHTML` für Datei-/Ordnernamen ist deshalb keine Stilkonvention, sondern die tragende Voraussetzung dieser Auth-Entscheidung — jedes eingeschleuste Skript liest das 30 Tage gültige, nicht widerrufbare JWT unmittelbar aus.

**Muss-Kriterien für die Umsetzung** (bestehendes Projektmuster, siehe Sicherheitshinweis zu `display_name`/`raw_label` in `frontend/src/api/types.ts`):

- Der Dateiname wird **ausschließlich als regulärer React-Textknoten** gerendert. Kein `dangerouslySetInnerHTML`, keine HTML-String-Prop, kein Markdown-/Rich-Text-Rendering.
- Er fließt **nie in `href`, `src`, `style` oder einen `url()`-Kontext**. Geprüft und derzeit erfüllt: Die Bildabrufe sind id-basiert (`/photos/{id}/image?variant=…` über `apiFetchBlob` + Object-URL), der Dateiname geht in keine URL ein. Diese Eigenschaft darf der `PhotoCard`-Umbau nicht aufweichen.
- **Zu bauen (klein, in Etappe 3):** ein Test in `PhotoCard.test.tsx` nach dem Vorbild von `CloudVisionStatusList.test.tsx` und `CriterionDetailsList.test.tsx` — "der Dateiname wird als Textknoten gerendert, nie über `dangerouslySetInnerHTML`" — plus ein einzeiliger Sicherheitskommentar an der Renderstelle. Das existiert im Bestand bereits dreimal und ist der billigste Weg, eine tragende Voraussetzung prüfbar statt erinnerbar zu halten.
- **Kein `title`-Attribut nötig, und wenn doch, ist es kein Sicherheitsthema:** React setzt `title` als Attribut ohne HTML-Parsing (Präzedenz `CategoryBadge.tsx`). Ob der abgeschnittene Name einen Tooltip bekommt, ist eine Barrierefreiheits-/Vertragsfrage (zugänglicher Name bzw. Beschreibung, siehe UI/UX-Abschnitt 8), keine Sicherheitsfrage.

**Ausdrücklich kein Handlungsbedarf:** keine Zeichensanierung, keine Whitelist, kein Escaping von Hand auf dem Dateinamen. Er ist Inhalt; ihn zu verstümmeln verletzt die Zusage "gleiche Inhalte" und schützt gegen nichts, was React nicht bereits abfängt.

**Bewusst getragenes Restrisiko:** Ein Dateiname mit Richtungssteuerzeichen (z.B. U+202E) oder exotischer Unicode-Formatierung kann die Statuszeile visuell verdrehen oder den Namen spoofen. Wirkung ausschließlich kosmetisch: Keine Aktion der Karte hängt am angezeigten Namen — Bild-Link, "Übernehmen" und "Verwerfen" arbeiten mit `photo.id` —, es gibt keinen Download- und keinen Ausführungspfad, und wer solche Namen in den Familienordner legen kann, hat ohnehin bereits Zugriff auf die Fotos selbst. Kein Gegenmittel vorgesehen; das passt zur bestehenden Vertrauensgrenze und begründet keinen neuen Eintrag im Sicherheitskonzept.

**Übermäßig langer oder umbruchloser Name** ist als Layout-Störung durch `min-w-0 truncate` + `min-w-6` (UI/UX-Abschnitt 2) bereits abgedeckt — erwähnt, damit die beiden Utilities nicht als reine Kosmetik wegoptimiert werden.

### 2. Der Dateiname als schützenswerter Inhalt — Screenshot-Hygiene

Dateinamen und Ordnerstruktur privater Familienfotos gelten im Projekt bereits als sensibles Datum, nicht nur als Metadatum (siehe die verbindliche Ausgabe-Hygiene in `backend/src/photosort/category_diff.py`, aus Spec 0217). Diese Story macht sie erstmals **im Foto-Raster sichtbar** und verlangt im selben Zug **Screenshots aller Ansichten im Pull Request** (Etappe 5, Akzeptanzkriterium "Abnahme"). Das Repository ist öffentlich, PR-Anhänge liegen öffentlich auf GitHub, und der CI-Schritt gegen Bilddateien greift nur im Arbeitsbaum, nicht an PR-Anhängen.

Muss-Kriterien:

- Screenshots und der Graustufen-Ad-hoc-Lauf entstehen **ausschließlich gegen den synthetischen Demo-Stand** (`browse-app` / `demo_state.py`, Pfade der Form `Demo/<slug>/foto-0001.jpg`), nie gegen Daniels Instanz oder echte Fotos. Das steht bereits im `browse-app`-Skill — ab dieser Story betrifft es zusätzlich zum Bildinhalt auch Dateinamen und Ordnerstruktur.
- In Spec, PR-Beschreibung und Commit-Messages steht **kein echter Dateiname und kein Pfad aus dem Familienbestand**; Beispiele werden selbst erzeugt.
- `e2e/artifacts/` bleibt gitignored; es wird kein Screenshot in den Arbeitsbaum eingecheckt.

### 3. Anmeldeansicht

Der Umbau ist rein maßlich (`h-12` → `h-11`, `h-[50px]` → `h-11 w-full`, Abstände, Überschriftenstufe). Autofill und Passwortmanager hängen an Attributen, nicht an Farben, Radien oder Höhen — solange die folgenden Punkte unverändert bleiben, ändert die Umgestaltung nichts daran. Prüfzusage, keine neue Maßnahme:

- `type="password"` am Passwortfeld, `autoComplete="username"` / `autoComplete="current-password"`, die `name`-Attribute und die `<label for>`-Verknüpfung bleiben wortgleich erhalten.
- Das Zurücksetzen des Passwortfelds im Fehlerfall (`onError: () => setPassword('')`) bleibt bestehen.
- Es entsteht **keine** Sichtbarkeitsumschaltung für das Passwort und kein Kopier-Affordance — das wäre ohnehin die durch die Akzeptanzkriterien verbotene Funktionserweiterung.
- Der Feldwert landet in keinem `title`, `data-*` oder sonstigen Attribut.
- Die dritte `h-11`-Kategorie ("Eingabefelder und Kontrollkästchen", UI/UX-Abschnitt 8) muss stehen, damit die neue Abstands-/Maßprüfung die Anmeldefelder nicht unter 44px drückt.

### 4. Fehlermeldungen quer durch die Ansichten

Der Umbau ändert die **Form**, nicht den Text. Muss-Kriterien:

- Kein Fehlertext wird ergänzt, verlängert oder um technische Details angereichert — kein HTTP-Statuscode, kein Endpunktpfad, kein Exception-Typ, kein Stacktrace, kein Fotopfad. Angezeigt bleibt genau das, was heute angezeigt wird (auf der Anmeldung `ApiError.detail`). Ein Restyling ist nicht der Ort, an dem Fehlermeldungen "hilfreicher" werden.
- Die bestehenden Sicherheitskommentare und Tests an den Stellen mit extern erzeugtem Text bleiben erhalten und grün: `CloudVisionStatusList` (`error_message`, Textknoten-Test), `CriterionDetailsList` (Feinlabels), `ui/alert.tsx`. Der Umbau der Alert-Konstruktionen (Gate-Hinweis im Foto-Raster, Vorschlagskasten der Detailseite) darf keine HTML-String-Prop einführen.

### 5. `frontend/src/lib/scrollLock.ts` — Qualität, nicht Sicherheit

Eine falsche Zählersemantik hinterlässt die Seite mit gesperrtem `body`-Scroll. Das ist ein Bedienbarkeitsfehler, keine Sicherheitslücke: kein Vertrauensübergang, keine Daten, keine Auth-Durchsetzung berührt; der Zähler ist modulweit und nur aus dem eigenen Anwendungscode erreichbar, es gibt keinen Angreifer, der ihn ansteuern könnte, und ein Neuladen behebt den Zustand. Der Punkt gehört vollständig in die Teststrategie. Kein Eintrag im Sicherheitskonzept.

### 6. Abhängigkeiten

Am Abschnitt "Architektur / Umsetzung" geprüft, nicht angenommen: Er sagt zweimal ausdrücklich "keine neue Abhängigkeit"; alle genannten Bausteine sind projekteigene Dateien (`PhotoCard.tsx`, `RatingButtons.tsx`, `Stepper.tsx`, `scrollLock.ts`) oder bereits vorhandene Tailwind-/Radix-Mittel, `lucide-react` bleibt einzige Symbolquelle und weiterhin nur über `ui/icon.tsx` importiert. `frontend/package.json` und `package-lock.json` kommen in keiner der fünf Etappen vor. Die Lieferkettenfläche aus dem Abschnitt "npm-Lieferkette des ausgelieferten Frontend-Bundles" wird damit nicht berührt. **Sollte in der Umsetzung doch ein Paket hinzukommen, ist diese Einschätzung hinfällig** — dann gilt ADR-Pflicht und eine erneute Security-Konsultation.

### Sicherheitskonzept-Nachtrag (Etappe 5)

Keine neue Angriffsfläche, kein neues Restrisiko, keine neue Lücke — in `specs/architecture/0003-securitykonzept.md` sind zwei Präzisierungen nachzutragen, zusammen mit dem Design-System-Nachtrag:

1. **Abschnitt "Frontend":** Mit dieser Spec wird der OpenCloud-Dateiname erstmals als *sichtbarer Text* gerendert (bisher nur `alt`/`aria-label`). Geprüft und **kein** Wegfall der ADR-0005-Voraussetzung — Textknoten-Rendering unverändert, kein neuer URL-/CSS-Kontext, abgesichert durch den Textknoten-Test in `PhotoCard.test.tsx`. Dazu das getragene Restrisiko der Unicode-Richtungssteuerzeichen in einem Halbsatz.
2. **Screenshot-Hygiene** (an "Browsergestützte Oberflächenprüfung" oder ans Ende von "Frontend"): Screenshots der Foto-Ansichten tragen ab dieser Story Dateiname und Ordnerstruktur, nicht mehr nur Bildinhalt. Die bestehende Regel "nur synthetische Demo-Daten" bekommt damit einen zweiten, unabhängigen Grund — festhalten, damit sie nicht später als reine Bilddaten-Regel gelesen und für "nur ein Screenshot der Rasteransicht" gelockert wird.

## Entscheidungen

Aus dem Refinement übernommen (Issue #321, dort abschließend geklärt): Zuschnitt als ein Durchgang mit einem Pull Request · Informationsdichte ändert den Inhalt nicht · Tastenkürzel bleiben 1/2/3, übernommen wird nur die Form des Kästchens · keine Sidebar, die waagerechte Schrittnavigation bekommt nur die Zustandswerte · der Dateiname auf der Fotokachel ist die eine bewusste Ergänzung, weil die Durchstreichung sonst keinen Träger hat.

Im `spec-writer`-Ablauf getroffen:

- **`architect` konsultiert (Schritt 1).** Ergebnis ist der Abschnitt "Architektur / Umsetzung" mit neun Vorab-Entscheidungen, den beiden Aufräumpunkten, drei neuen statischen Prüfungen und der Etappenfolge. Keine neue ADR, `docs/` unberührt.
- **Aussortierte Karte — Rückfrage an Daniel, beantwortet am 2026-09-05:** ADR 0055 Abweichung 7 wird eingehalten, der Wortlaut des Akzeptanzkriteriums ("Deckkraft der ganzen Karte") wird präzisiert. Gedämpft wird nur die Bildfläche (`opacity-40` auf dem `<a>`) plus textlose dekorative Elemente; Zustandsbadge und durchgestrichener Dateiname bleiben voll deckend. Die Alternative — Board-Wortlaut buchstäblich — hätte die Kontrastzusage für aussortierte Karten aufgegeben und eine ADR gebraucht, die 0055 Abweichung 7 ablöst.
- **Kartenzustand "ausgewählt" — Rückfrage an Daniel, beantwortet am 2026-09-05:** zurückgestellt. Gebaut werden vier statt fünf Zustände; der fünfte kommt mit der Story, die eine Foto-Auswahl einführt. Damit weicht die Umsetzung bewusst vom Board ab, was in der PR-Beschreibung zu vermerken ist. Der `architect` hatte das Gegenteil vorgeschlagen (Baustein ohne Aufrufer, Präzedenz `ui/dialog.tsx`); Daniels Entscheidung geht vor.
- **`ux-ui-designer` konsultiert (Schritt 2).** Ergebnis ist der Abschnitt "UI/UX". Abweichend vom `spec-writer`-Skill wurde er nicht auf dem Günstig-Modell aufgerufen: Sein Auftrag war hier keine checklistenartige Relevanzprüfung, sondern eine WCAG-Kontrastrechnung für ein neues Token und Board-Treue über vierzehn Ansichten.
- **Drei Design-Detailentscheidungen des `ux-ui-designer`**, sichtbar und deshalb hier festgehalten: Die Bewertungsleiste steht unterhalb `sm:` untereinander statt nebeneinander (arithmetisch belegt: ≈ 400px nötig, 288px verfügbar; Kürzen der Beschriftung verbietet ein Akzeptanzkriterium, horizontales Scrollen die Abnahme) · die Kartenpolsterung ist am Telefon 8px statt der 12px des Boards, weil die Bildfläche sonst um 16 % schrumpft · der Kennzeichentext heißt "Verworfen" statt "AUSGESONDERT" und steht nicht in Versalien, weil das Produkt dieses Wort bereits führt.
- **Die Shortcut-Zeile auf der Detailseite bleibt unverändert stehen.** Sie wird durch die neuen Tasten-Kästchen teilweise redundant, aber "es wird nichts entfernt" ist ein Akzeptanzkriterium, und der Pfeiltasten-Teil bekommt kein sichtbares Gegenstück. Sie wird lediglich als Metadatenzeile gesetzt (`text-xs text-text-muted`). Falls sie auf "←/→ navigieren" eingedampft werden soll, wäre das eine bewusste Streichung sichtbarer Information und damit Daniels Entscheidung.
- **Zwei Befunde am Bestand**, die die Story nicht benennt und die in der Umsetzung mitlaufen: Die `rounded-full`-Freigabeliste ist nicht nur dateiweise, sondern lässt auch verwaiste Einträge unbemerkt — der neue Helfer prüft beide Richtungen. Und `border-border/60` auf der Statistikseite liegt bei 0,87:1 und ist damit der eigentliche Kern des Akzeptanzkriteriums "Trennlinien verschwinden auf dem Grund".
- **`test-engineer` konsultiert (Schritt 3).** Ergebnis ist der Abschnitt "Teststrategie". Acht Akzeptanzkriterien wurden auf Testbarkeit geschärft und oben in dieser Fassung übernommen — im Kern durch die Angabe, welcher Prüfsatz das jeweilige Kriterium tatsächlich trägt. Der Nachtrag am Testkonzept `specs/architecture/0002-testkonzept.md` steht in Etappe 5.
- **Vierte statische Prüfung ergänzt (`opacity-*` fundstellengenau).** Der Architektur-Abschnitt sah drei vor; der `test-engineer` hat eine vierte vorgeschlagen und die Entscheidung an den `spec-writer` zurückgegeben. Übernommen: Entscheidung 4 operationalisiert die bindende ADR 0055 Abweichung 7 und wäre sonst nur durch einen einmaligen Ad-hoc-Graustufen-Lauf gedeckt, also danach dauerhaft ungeschützt; der Helfer existiert nach Etappe 1 ohnehin, die Freigabeliste hat vier bis fünf Einträge. Das ist eine technische Detailentscheidung innerhalb einer akzeptierten Spec und lag damit beim `spec-writer`, nicht bei Daniel.
- **Drei Befunde des `test-engineer`**, die die Story nicht benennt: (a) `e2e/tests/no-horizontal-scroll.spec.ts` erfasst heute weder die Foto-Detailseite noch den Foto-Vergleich — ausgerechnet die Detailseite trägt die umbrechende Bewertungsleiste; beide Routen kommen in die bestehende Tabelle, die Detailseite mit einer Nicht-Überschriften-Vorbedingung, weil sie bewusst kein `h1` hat. (b) Die sichtbare Tastenziffer lebt in `RatingButtons.tsx`, die Belegung in `PhotoDetailPage.tsx` — sie können stumm auseinanderlaufen, deshalb die Tabelle über alle drei Tasten. (c) Genau ein bestehender Test fällt planmäßig weg (`pointer-events-none` am Bewertungs-Overlay) und wird ersetzt, nicht gelöscht.
- **`security-engineer` konsultiert (Schritt 3).** Ergebnis: sicherheitsrelevant mit engem Zuschnitt, keine neue Bedrohungsklasse. Der Dateiname ist kein Erstkontakt (er steht heute schon in `alt` und `aria-label`), neu ist nur die Sichtbarkeit als Fließtext; das Verbot von `dangerouslySetInnerHTML` bleibt tragende Voraussetzung von ADR 0005, abgesichert durch einen Textknoten-Test. Der eigentliche Zugewinn ist die **Screenshot-Hygiene**: Die Story macht Dateinamen und Ordnerstruktur erstmals im Foto-Raster sichtbar und verlangt im selben Zug Screenshots im öffentlichen Pull Request — der CI-Schritt gegen Bilddateien greift nur im Arbeitsbaum, nicht an PR-Anhängen. Der Nachtrag am Sicherheitskonzept `specs/architecture/0003-securitykonzept.md` steht in Etappe 5.

- **Screenshot-Beleg im Pull Request — Rückfrage an Daniel, beantwortet am 2026-09-06:** entfällt. Das Abnahmekriterium ist auf die Sichtprüfung reduziert. Anlass war ein handfestes Werkzeugproblem: `gh` kann keine Bilder an einen Pull Request hängen, das geht ausschließlich über die Weboberfläche — ein Kriterium, das die Umsetzung selbst nie erfüllen kann, wäre bei jeder künftigen Story offen geblieben und hätte die Abnahme entwertet. Die Sichtprüfung aller vierzehn Ansichten in beiden Breiten und der Graustufen-Lauf sind unverändert Pflicht und haben stattgefunden. Derselbe Satz war im Design-System-Dokument als „mit Screenshot-Belegen im Pull Request" festgehalten und wurde mitgezogen — gefunden vom Copilot-Review, das die Aussage dort gegen den PR-Stand geprüft hat.

## Offene Fragen

Keine blockierenden. Die im Refinement offengelassenen Einzelfragen sind geklärt, die beiden Produktentscheidungen des `spec-writer`-Ablaufs sind von Daniel beantwortet und oben festgehalten. Die Shortcut-Zeile (siehe "Entscheidungen") ist mit einer akzeptanzkriterien-konformen Voreinstellung entschieden und kann von Daniel jederzeit widerrufen werden, ohne die Umsetzung zu blockieren.

## Out of Scope

Mehr Fotos je Reihe, zusätzliche Metadaten auf der Kachel, eine Foto-Mehrfachauswahl, eine Sidebar-Navigation, ein schwebendes Toast-System und jede Änderung der Tastenbelegung. Der Kartenzustand "ausgewählt" wird nicht gebaut (Entscheidung 5) — er kommt mit der Story, die eine Foto-Auswahl einführt. Die Stories [`0044`](./0044-projekte-loeschen.md) und [`0058`](./0058-cloud-vision-status-transparenz.md) bleiben eigene Vorhaben und werden erst nach dieser Spec gebaut.
