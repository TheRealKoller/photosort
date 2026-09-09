# 0347 - Einstellungen und Statistik kompakt im Navigationsmenü

**Status:** Accepted
**Erstellt:** 2026-09-09
**Bezug:** [Issue #347](https://github.com/TheRealKoller/photosort/issues/347)

## Ziel

Die Navigation eines Projekts führt heute vier gleichrangige Ziele: Projekt, Fotos, Vergleich und Einstellungen. Darin stecken zwei Probleme, die zusammengehören.

Die **Statistikseite fehlt in dieser Navigation ganz**. Sie ist ausschließlich über einen Link am Ende der Pipeline-Seite erreichbar — wer sie nicht kennt, findet sie nicht, und wer gerade an einer anderen Stelle im Projekt steht, muss erst dorthin zurück. Steht man auf ihr, zeigt die Navigation keinen Hinweis darauf, wo man ist.

Gleichzeitig belegen die **Einstellungen ein Viertel der Navigationsleiste**, obwohl sie — wie die Statistik — selten gebraucht werden. Beide bekommen damit dasselbe Gewicht wie die drei Ziele, zwischen denen beim Sortieren tatsächlich ständig gewechselt wird.

Beide Seiten werden deshalb zu einem gemeinsamen, kompakten Nebenbereich der Navigation zusammengefasst: von jeder Projektseite aus erreichbar, ohne den Platz und die Aufmerksamkeit der drei Hauptziele zu beanspruchen. Betroffen sind beide Nutzer von PhotoSort, auf allen Bildschirmgrößen.

## User Story

Als Nutzer eines PhotoSort-Projekts möchte ich Einstellungen und Statistik von jeder Projektseite aus über einen kompakten Nebenbereich der Navigation erreichen, damit ich beide jederzeit finde, ohne dass sie den ständig gebrauchten Zielen Platz wegnehmen.

## Akzeptanzkriterien

Fassung nach der Schärfung durch `test-engineer` — die Kriterien der Story sind inhaltlich unverändert, aber auf ein prüfbares Maß gebracht. Die beiden Schwellenwerte in AK4 und AK5 (75 %, Faktor 2) sind **Produktzusagen** und stehen deshalb hier und nicht nur im Testcode.

- [ ] **AK1 — Drei Hauptziele in fester Reihenfolge.** `nav[aria-label="Projektbereiche"]` enthält genau drei `<a>` in dieser DOM-Reihenfolge: „Projekt" → `/projects/{id}/pipeline`, „Fotos" → `/projects/{id}/photos`, „Vergleich" → `/projects/{id}/compare`. Kein weiteres `<a>` liegt in diesem Landmark.
- [ ] **AK2 — Nebenbereich mit genau zwei Einträgen.** „Einstellungen" (`/settings`) und „Statistik" (`/stats`) liegen nicht in der Leiste. Genau ein Auslöser (Button, zugänglicher Name „Projektbereiche") öffnet einen Bereich; ab 1024 px zeigt der Bereich ausschließlich diese beiden Einträge in dieser Reihenfolge.
- [ ] **AK3 — Von jeder Projektseite erreichbar.** Auf allen neun Routen mit Projektkontext sind Auslöser und Bereich vorhanden, einschließlich `/settings` und `/stats` selbst. Auf `/`, `/login` und `/projects/new` gibt es weder Leiste noch Auslöser noch Landmark.
- [ ] **AK4 — Der Auslöser ist erkennbar kompakter als ein weiteres Hauptziel.** Bei 1024 px sind die drei Hauptziele und der Auslöser gleichzeitig dargestellt, und die gemessene Breite des Auslösers beträgt **höchstens 75 % der Breite des schmalsten dargestellten Hauptziels**; die Kopfzeile bleibt dabei einzeilig. Bezugsgröße ist das mitgemessene schmalste Hauptziel, nie eine hartkodierte Pixelzahl — eine feste Zahl wäre auf Schriftgrad und heutigen Beschriftungssatz kalibriert.
- [ ] **AK5 — Genau ein Auslöser, sichtbar abgesetzte Gruppe.** Unterhalb 1024 px existiert **im DOM genau ein** Auslöser (Kardinalität, nicht „kein zweiter sichtbar"), und er ist dargestellt. Das geöffnete Panel zeigt fünf Einträge in der Reihenfolge Projekt, Fotos, Vergleich, Einstellungen, Statistik; die letzten beiden bilden eine eigene Gruppe unterhalb der ersten drei, abgesetzt durch eine gerenderte Trennlinie (`border-bottom` > 0 px, Farbe `--separator`, nicht transparent), **und** der senkrechte Abstand zwischen den beiden Gruppen ist **mindestens doppelt so groß** wie der größte Abstand zwischen zwei benachbarten Hauptzielen im Panel.
- [ ] **AK6 — Aktive Seite ohne Öffnen erkennbar.** Auf `/settings` und `/stats` trägt genau ein Eintrag im geöffneten Bereich `aria-current="page"`, **und** der geschlossene Auslöser trägt `aria-current="true"` sowie eine Auszeichnung, die nicht allein farblich ist (Rand + Fläche). Auf allen übrigen Routen mit Projektkontext trägt der Auslöser kein `aria-current` — ausdrücklich auch nicht auf `/curate`.
- [ ] **AK7 — Auswahl navigiert und schließt.** Die Auswahl eines Eintrags navigiert zur Zieladresse und der Bereich ist danach geschlossen — geprüft für einen Nebenbereichs-Eintrag **und** für ein Hauptziel im Bereich.
- [ ] **AK8 — Bezeichnung und Tastaturbedienung.** Der Auslöser trägt bei rein symbolischem Inhalt den zugänglichen Namen „Projektbereiche" (`textContent === ''`, Symbol `aria-hidden`), ist per Tastatur fokussierbar und mit Enter/Leertaste zu öffnen, per Escape zu schließen, wobei der Fokus auf den Auslöser zurückkehrt.
- [ ] **AK9 — Statistik-Link auf der Pipeline-Seite entfällt, keine Dopplung.** `ProjectPipelineLayout` rendert keinen Link auf `/projects/{id}/stats` mehr. „Nicht doppelt vertreten" heißt messbar: bei geöffnetem Bereich existiert im Dokument genau ein Link mit diesem `href`, bei geschlossenem keiner.
- [ ] **AK10 — Adressen unverändert.** `/projects/{id}/settings` und `/projects/{id}/stats` sind unverändert direkt aufrufbar und rendern ihre Seite — keine neue Route, kein Redirect, keine geänderte Adresse. `PROJECT_ROUTE_PATHS` bleibt bei neun Mustern.
- [ ] **AK11 — Seiteninhalte unverändert.** Kein Diff an `ProjectSettingsPage.tsx`/`ProjectStatsPage.tsx` und deren Testdateien. Das ist bewusst ein **Review-Kriterium am Diff, kein Testfall** — ein Test, der „hat sich nichts geändert" behauptet, ist eine Tautologie. Der Nachweis ist der unveränderte, weiterhin grüne Bestand von `ProjectStatsPage.test.tsx`/`ProjectSettingsPage.test.tsx`.

## Datenmodell-Bezug

Keiner. Reine Frontend-Umgruppierung bestehender Navigationsziele — keine neue oder geänderte Entität, keine Migration, kein neuer API-Aufruf. [`docs/architecture.md`](../../docs/architecture.md) ist nur an einer Stelle nachzuziehen (siehe „Architektur / Umsetzung", Abschnitt Doku-Pflege), das Datenmodell dort bleibt unberührt.

## Architektur / Umsetzung

**Ansatz:** Reines Frontend, dieselbe Bauweise wie Spec [`0298`](./0298-projektnavigation-in-der-kopfzeile.md) — kein Backend-Anteil, kein Datenmodell, keine Migration, kein neuer API-Aufruf, keine neue Laufzeit-Abhängigkeit, keine neue Route. Beide bestehenden Adressen (`/projects/:projectId/settings`, `/projects/:projectId/stats`) bleiben unverändert; Lesezeichen funktionieren, weil an `PROJECT_ROUTE_PATHS` und an `App.tsx`s Routentabelle nichts angefasst wird. Geändert wird ausschließlich, **wie** die Zieltabelle in `utils/projectRoutes.ts` gegliedert ist und **wie** `components/ProjectNav.tsx` sie darstellt.

**Keine ADR nötig.** Konkret geprüft: (a) *Neue Radix-Primitive?* Nein — der Nebenbereich ist wieder ein Auslöser mit `aria-expanded` über echten `<a>`-Elementen, genau das, was `components/ui/popover.tsx` liefert. Die Begründung aus Spec 0298 gegen `@radix-ui/react-dropdown-menu` (ARIA-`menu`-Muster nimmt der Seitennavigation ihre Link-Semantik) gilt hier **verschärft**: unterhalb `lg:` liegen jetzt *alle fünf* Navigationsziele im Panel; wären sie `menuitem`, hätte die Anwendung auf schmalen Bildschirmen überhaupt keine Navigationslinks mehr. (b) *Dreizehntes Symbol im Zwölfer-Satz (`ellipsis`)?* Bewusst nein — `chevron-down` ist bereits der Auslöser genau dieses Bedienelements, eine Erweiterung des Satzes wäre ADR-pflichtig (Teil-Ablösung von ADR 0055 Punkt 7) und zöge Board-Referenz und Vertragstest nach sich. `ux-ui-designer` hat das bestätigt.

### Ein Auslöser, ein Panel — bei jeder Breite dasselbe Bauteil

Die zentrale Entwurfsentscheidung, aus der alles Übrige folgt: Es gibt **genau eine** `Popover`-Instanz mit **genau einem** Auslöser im DOM, unabhängig von der Breite. Der Breakpoint steuert nur, welche Teile ihres Panels dargestellt werden:

| | Leiste (`hidden lg:flex`) | Auslöser (immer) | Panel |
|---|---|---|---|
| **≥ 1024 px** | Projekt, Fotos, Vergleich | sichtbar | Einstellungen, Statistik |
| **< 1024 px** | ausgeblendet | sichtbar | Projekt, Fotos, Vergleich · *Trenner* · Einstellungen, Statistik |

Der naheliegende Gegenentwurf — **zwei** `Popover`-Instanzen (eine `lg:hidden` mit allen fünf, eine `hidden lg:block` mit den zwei Nebeneinträgen) — ist ausdrücklich abgewählt. Er legte zwei Buttons mit demselben zugänglichen Namen ins DOM, machte jede Rollen-Query darauf mehrdeutig (auch in `e2e/tests/tap-targets.spec.ts` und `popover-position.spec.ts`, die den Auslöser bereits ansteuern) und stünde in Spannung zu AK5. Mit der Ein-Instanz-Lösung ist AK5 nicht nur visuell, sondern **im DOM** wahr und damit prüfbar.

Der Gruppen-Trenner hängt **am Block der Hauptziele, nicht am Block der Nebeneinträge**: der Hauptziel-Block trägt `mb-2 border-b border-separator pb-2 lg:hidden`, damit verschwindet der Trenner ab `lg:` automatisch mit dem Block, den er abtrennt. Ein Trenner am Nebenblock bräuchte eine zweite, gegenläufige `lg:`-Regel zum Wieder-Abschalten — eine stille Fehlerquelle.

**Zur Tokenwahl `--separator` (nachgetragen 2026-09-09 nach der Review-Runde):** Die ursprüngliche Begründung — „der dokumentierte Token für freistehende Linien **auf dem Grund**" — war falsch und ist hiermit zurückgenommen. Das `PopoverContent` steht auf `--elevated`, nicht auf dem Grund, und die Dreiteilung der Rahmenrollen schloss `--separator` dort bis dahin ausdrücklich aus. Maßgeblich ist stattdessen die mit dieser Spec eingeführte **benannte Ausnahme „Gruppentrenner auf `--elevated`/`--overlay`"** ([`architecture/0004-design-system.md`](../architecture/0004-design-system.md), Abschnitt „Rahmen in drei Rollen"): innerhalb von Panels und Popovern verwenden Gruppengrenzen `--separator` statt `--border`, weil die Flächenstufe selbst nicht zur Trennung ausreicht und die Regel speziell Kanten *zwischen* verschiedenen Flächen adressiert, nicht Unterteilungen *innerhalb* einer Fläche. Die Regel war an dieser Stelle also nicht verletzt, sondern unvollständig. Der Gegenentwurf `--border` ist verworfen: mit 1,04–1,45:1 wäre er faktisch keine Linie, und AK5 trüge dann allein der verdoppelte Abstand. Die Ausnahme ist in `index.css`, im Design-System-Dokument und im Vertragstest nachgezogen; der Korridor 2,0–2,5 bleibt auf `--bg`/`--surface` kalibriert, tragend ist dort die Zusicherung „`--separator` ist auf jeder der vier Flächen sichtbarer als `--border`".

### `frontend/src/utils/projectRoutes.ts` — Zieltabelle in zwei Gruppen

- `ProjectNavTargetId` wird um `'stats'` erweitert.
- `PROJECT_NAV_TARGETS` wird **aufgeteilt und dabei umbenannt**:
  - `PROJECT_NAV_PRIMARY_TARGETS` — `pipeline` („Projekt"), `photos` („Fotos"), `compare` („Vergleich"), in dieser Reihenfolge.
  - `PROJECT_NAV_SECONDARY_TARGETS` — `settings` („Einstellungen"), `stats` („Statistik"), in dieser Reihenfolge.
  - `ALL_PROJECT_NAV_TARGETS = [...PROJECT_NAV_PRIMARY_TARGETS, ...PROJECT_NAV_SECONDARY_TARGETS]` — Grundlage von `resolveActiveNavTargetId`.
- **Die Umbenennung ist Absicht, nicht Kosmetik.** Bliebe der Name `PROJECT_NAV_TARGETS` für „alle fünf" bestehen, änderte sich die Bedeutung eines Bezeichners still unter allen bestehenden Aufrufstellen hinweg. Der neue Name erzwingt, dass jede Stelle einmal angesehen wird, statt zufällig weiterzukompilieren.
- Neuer Eintrag `stats`: `label: 'Statistik'`, `buildPath: (id) => \`/projects/${id}/stats\``, `activeRoutePaths: [PROJECT_ROUTE_PATHS.stats]`.
- `resolveActiveNavTargetId('/projects/1/stats')` liefert damit `'stats'` statt bisher `null`. `/curate` bleibt unverändert `null` — die Kuratierung ist weiterhin kein Navigationsziel.
- Neu: `isSecondaryNavTargetId(id: ProjectNavTargetId | null): boolean` — reine Funktion, damit die Aktiv-Markierung des Auslösers ohne Rendering prüfbar ist statt als Inline-Ausdruck in der Komponente zu verschwinden. `isSecondaryNavTargetId(null) === false`.
- `PROJECT_ROUTE_PATHS`, `PROJECT_CONTEXT_ROUTE_PATHS`, `RESERVED_PROJECT_ID_SEGMENTS`, `matchProjectId`: **unverändert**.

### `frontend/src/components/ProjectNav.tsx`

- Der `<nav aria-label="Projektbereiche">` bekommt **`gap-3`** (bisher nur `flex items-center`). Zwingend, kein Geschmack: ab `lg:` steht der Auslöser jetzt direkt neben „Vergleich", und beide spannen ihre Trefferfläche per `tap-target` um bis zu 6 px je Seite auf — ohne die 12 px überlappten sie sich, und in einer Überlappung gewinnt das obenliegende Element.
- Die Leiste (`hidden items-center gap-3 lg:flex`) mappt **`PROJECT_NAV_PRIMARY_TARGETS`** statt aller Ziele.
- Am Auslöser-`Button` entfällt **`lg:hidden`** — er ist jetzt bei jeder Breite da. `variant="ghost" size="icon"`, `aria-label="Projektbereiche"`, `Icon name="chevron-down"` bleiben.
- **Aktiv-Markierung des geschlossenen Auslösers** (AK6):
  - Visuell: eigenes, dateilokales Literal `NAV_TRIGGER_ACTIVE_CLASSES = 'border border-accent bg-overlay text-accent'`, angehängt, wenn `isSecondaryNavTargetId(activeTargetId)`. Nicht farbe-allein: der ruhende Ghost-Button hat **gar keinen** Rand, der Rand selbst ist also der nicht-farbliche Träger der Aussage.
  - Zugänglich: `aria-current={isSecondaryActive ? 'true' : undefined}` am Button. Bewusst `'true'` und nicht `'page'` — der Auslöser ist kein Link auf die aktuelle Seite, aber sehr wohl „das aktuelle Element innerhalb der Menge" im Sinne der ARIA-Definition. Der Panel-Eintrag behält daneben sein `aria-current="page"`.
  - **Ausdrücklich abgewählt:** ein routenabhängiger zugänglicher Name (etwa „Projektbereiche (Statistik)"). Ein Bedienelement, dessen Name mit der Route wandert, ist desorientierend und bräche die stabilen Lokalisierer in `tap-targets.spec.ts`/`popover-position.spec.ts`.
- **Die Beschriftung des Auslösers bleibt „Projektbereiche"** (bestätigt durch `ux-ui-designer`). Randbedingung aus der Ein-Instanz-Entscheidung: es gibt genau **eine** Beschriftung für beide Darstellungen, sie darf nicht mit der Route wechseln, und ein per `lg:`-Klassen umgeschaltetes Doppel-`sr-only`-Paar ist verboten (in jsdom greift Tailwind nicht, der zugängliche Name wäre dort die Verkettung beider Texte). Unter dieser Bedingung ist „Projektbereiche" die bessere der Kandidaten: ab `lg:` ist es ein Oberbegriff für eine Teilmenge (mild ungenau, die übrigen stehen sichtbar daneben), „Weitere Bereiche"/„Mehr" wäre unterhalb `lg:` schlicht **falsch**, weil das Panel dort alles enthält.
- **Nicht anfassen:** die Zeile `layout === 'bar' ? 'tap-target' : 'min-h-11 w-full'` in `ProjectNavLink` steht wortgleich als Fundstelle in `TALL_CONTROL_ALLOWLIST` (`designSystem.contract.test.ts`). Jede Umformatierung bricht den Vertragstest und muss dort wortgleich nachgezogen werden — das ist zu **verifizieren, nicht anzunehmen**. Ebenso bleiben `NAV_LINK_ACTIVE_CLASSES`/`NAV_LINK_RESTING_CLASSES` zeichengleich (Bindung an `Stepper.tsx`). Das neue Auslöser-Literal wird dieser Bindung **nicht** hinzugefügt: ein Symbol-Button ist kein Board-Navigationselement.
- Kein neues Bauteil, keine Aufteilung in `ProjectNavMenu.tsx`: die Zusage „eine Zieltabelle, alle Darstellungen" ist nur so viel wert, wie sie in einer Datei nachlesbar bleibt.

### `frontend/src/pages/pipeline/ProjectPipelineLayout.tsx`

Der abschließende `<div className="flex flex-wrap gap-3">` mit dem „Statistik"-`Button` **entfällt vollständig** samt seines Kommentarblocks; die Seite endet danach mit dem `<Outlet>`-Container. Es bleibt keine Restnavigation am Seitenende zurück.

### Nachzuziehen: Spec 0298

Nach dem dort selbst angewandten Verfahren (**datierter Nachtrag statt `Superseded`**): Spec 0298 behält den Status `Implemented` und bekommt einen datierten Nachtrag, der einzeln benennt:

- **Abgelöst durch Spec 0347:** AK1 (vier gleichrangige Ziele → drei Hauptziele plus Auslöser), AK5 (Auslöser ist ab 1024 px jetzt sichtbar), AK6 (der Auslöser ist keine reine Schmalbild-Darstellung mehr; sein Panel führt fünf Einträge in zwei Gruppen), AK8b **nur für `/stats`** (dort wird jetzt markiert — für `/curate` gilt AK8b unverändert weiter), AK9b und das damit gegenstandslose AK9c (der Statistik-Button am Ende der Pipeline-Seite entfällt).
- **Unverändert gültig:** AK2, AK3a/b/c, AK4, AK7, AK8a (für die drei Hauptziele), AK8c, AK9a, AK10, AK11a/b/c, AK12, AK13, AK14.

Der Nachtrag gehört in **denselben PR** wie die Umsetzung — eine Spec, die nach dem Merge das Gegenteil des Codes behauptet, ist schädlicher als gar keine.

### Doku-Pflege

`docs/architecture.md` behauptet im Frontend-Aufzählungspunkt wörtlich „ab `lg:` vier einzelne Links, darunter ein Auslöser mit denselben vier Zielen" und wird damit falsch. Im selben PR nachzuziehen: dieser Satz **und** ein neuer „Letzte Aktualisierung"-Eintrag zu Spec 0347. Kein Datenmodell-Delta, keine Änderung an `docs/setup.md` oder am Root-`README.md`. `specs/architecture/0004-design-system.md` ist bereits im Rahmen dieser Spec fortgeschrieben.

### Umsetzungsplanung für `developer`

Strikt TDD, jeder Schritt einzeln rot → grün → refactor. Die Reihenfolge ist so gewählt, dass **zu keinem Zeitpunkt ein Ziel unerreichbar** ist: der Nebenbereich existiert vollständig, bevor der alte Statistik-Link fällt.

1. **`utils/projectRoutes.ts` + Test.** Reine Funktionen, ohne React sauber rot/grün. Aufteilung in Primär-/Sekundärgruppe, `stats`-Eintrag, `ALL_PROJECT_NAV_TARGETS`, `isSecondaryNavTargetId`. Die bestehenden Tests auf `toHaveLength(4)` und auf `resolveActiveNavTargetId('/…/stats') === null` gehen hier rot — sie sind **anzupassen, nicht zu löschen**; genau sie sind der Rot-Nachweis dieses Schritts.
2. **`ProjectNav.tsx` + Test, isoliert gerendert.** Leiste auf drei Ziele; Auslöser ohne `lg:hidden`; Panel mit den zwei Blöcken; `gap-3` am `<nav>`; Aktivmarker am Auslöser.
3. **`App.test.tsx` nachziehen.** `aria-current` je Route gemäß neuer Zuordnung (`/stats` markiert jetzt), Erreichbarkeit von „Statistik" aus der Kopfzeile, AK9-Dopplungsprüfung. Die Kriterien AK2/AK3b/AK4 aus Spec 0298 müssen unverändert grün bleiben — wird hier etwas rot, das nicht ausdrücklich abgelöst ist, ist es eine Regression.
4. **`ProjectPipelineLayout.tsx` entschlacken** — Abwesenheitstest zuerst schreiben (rot), dann den Block entfernen. Erst jetzt, nachdem Schritt 2/3 die Statistikseite über die Navigation erreichbar gemacht haben.
5. **E2E `project-nav.spec.ts` überarbeiten**, `tap-targets.spec.ts` nachziehen (siehe Teststrategie).
6. **Sichtprüfung mit Skill `browse-app`** bei 360 / 768 / 1024 / 1280 px: kein Zeilenumbruch der Kopfzeile, kein waagerechtes Scrollen, Trenner im Panel sichtbar abgesetzt, Auslöser-Aktivmarker auf `/settings` und `/stats` erkennbar **ohne** zu öffnen, Panel liegt über dem Inhalt.
7. **Doku und Spec-Nachtrag** (Spec 0298, `docs/architecture.md`, `specs/architecture/0002-testkonzept.md`) — im selben PR, nicht als Nachzieh-Commit.

**Bewusst außerhalb des Scopes dieser Umsetzung:** Der Breakpoint bleibt `lg:` (1024 px). Mit drei statt vier Beschriftungen wäre `md:` inzwischen vermutlich machbar — aber kein Akzeptanzkriterium verlangt es, und eine Verschiebung entwertete die gemessene Grenze aus Spec 0298 AK5/AK6 samt ihrer E2E-Absicherung. Die gewonnene Breite ist Sicherheitsreserve gegen den Zeilenumbruch, kein Anlass für eine zweite Änderung im selben PR.

## UI/UX

**Sichtbare Oberfläche:** Ja — Umgestaltung der Projekt-Navigationsgruppe in der Kopfzeile.

### Ablauf und Layout

Das Feature spaltet die bisherige vierteilige Navigation in zwei Ebenen: **drei Primärziele** (Projekt/Pipeline, Fotos, Vergleich) in der Kopfzeilenleiste, plus ein **Nebenbereich mit Auslöser** für die beiden Sekundärziele (Einstellungen, Statistik).

**Ab `lg:` (≥ 1024 px):** Leiste mit drei Link-Zielen nach dem bestehenden Board-Navigationselement-Rezept (Radius 8 px, Polsterung 12/8 px, `--border-control`-Rand ruhend, `--overlay`-Hintergrund aktiv, `--accent`-Rand/-Schrift aktiv). Daneben ein separater Ghost-Button mit `chevron-down`-Symbol, `aria-label="Projektbereiche"`. Sein Panel enthält genau die zwei Sekundärziele. Die Leiste bleibt einzeilig; der Auslöser benötigt deutlich weniger Platz als ein viertes Navigationsziel (AK4).

**Unterhalb `lg:`:** nur der Auslöser ist dargestellt (kein zweiter Auslöser). Sein Panel enthält alle fünf Ziele: erst die drei Primärziele, dann der Trenner, dann die zwei Sekundärziele.

### Zustände

- **Aktives Primärziel:** `aria-current="page"` plus `--accent`-Rand/-Schrift am Eintrag. Der geschlossene Auslöser bleibt ruhend.
- **Aktives Sekundärziel:** der **geschlossene** Auslöser trägt selbst den Aktivstil (`border border-accent bg-overlay text-accent`) und `aria-current="true"`; der Panel-Eintrag trägt zusätzlich `aria-current="page"`. Damit ist ohne Öffnen erkennbar, dass man auf einem Sekundärziel steht.
- **Ruhende Ziele:** Ghost-Stil, bei Überfahren `--overlay`-Hintergrund und hellere Schrift, beim Drücken `--border`-Hintergrund. Zu jeder `hover:`-Variante steht eine `active:`-Variante — am Telefon ist „gedrückt" der einzige Zustand, den es gibt.
- **Lade-/Fehlerzustände:** nicht zutreffend, die Navigation berührt keinen Datenvorgang.

### Keine semantische Gruppierung — bewusst

Die Absetzung der Sekundärgruppe im Panel ist **rein visuell** (Trennlinie plus größerer Abstand). Eine semantische Gruppierung (`role="group"` mit Label) ist ausdrücklich abgewählt:

- Der Panel-Inhalt liegt im Portal **außerhalb** des `navigation`-Landmarks. Eine Gruppierung bräuchte selbst eine Ankündigung, und ein zweites, gleichnamiges `<nav>` ist seit Spec 0298 abgewählt (zwei gleichnamige Landmarks sind ein Bedienbarkeitsfehler und machen jede Rollen-Query mehrdeutig).
- Ab `lg:` enthält das Panel nur die zwei Sekundärziele. Eine Gruppe mit Label bliebe dort eine sinnlose Ein-Gruppen-Struktur, und ein per `lg:`-Klassen umgeschaltetes Label ist wegen der jsdom-Falle verboten.
- Alle fünf Links bleiben in jedem Fall erreichbar, beschriftet und in der Linkliste — verloren geht ausschließlich die Untergliederung, nicht ein Ziel.

**Umsetzung des Trenners — Auflösung einer Abweichung zwischen den Konsultationen:** `architect` hängt den Trenner an den Block der Primärziele (`mb-2 border-b border-separator pb-2 lg:hidden`), `ux-ui-designer` schlug alternativ ein eigenes `<li role="separator" aria-hidden="true">` in einer flachen Liste vor. Verbindlich ist die Fassung von `architect`, weil die drei Primärzeilen ohnehin einen gemeinsamen `lg:hidden`-Container brauchen (sonst müsste jede Zeile die Klasse einzeln tragen) und `test-engineer` genau diesen gemeinsamen Vorfahren als prüfbare Struktur für AK5 heranzieht. Damit entfällt ein separates Trennelement ersatzlos — es gibt nichts, das `aria-hidden` tragen müsste. Für gültiges Listen-Markup werden die beiden Gruppen als **zwei `<ul>`** gerendert; der erste trägt die Trenner-Utilities `mb-2 border-b border-separator pb-2 lg:hidden`. Die Tokenwahl `--separator` auf der `--elevated`-Fläche des Panels folgt der benannten Ausnahme „Gruppentrenner auf `--elevated`/`--overlay`" des Design-Systems (Begründung im Abschnitt „Architektur / Umsetzung"), **nicht** der Regel „Linie auf dem Grund" — die trifft hier nicht zu. Ein `role="group"` oder ein Label kommt dabei ausdrücklich **nicht** hinzu.

### Bezug zum Design-System

Das Muster „Projekt-Navigationsgruppe in der Kopfzeile" in [`specs/architecture/0004-design-system.md`](../architecture/0004-design-system.md) ist im Rahmen dieser Spec bereits fortgeschrieben: Zweiteilung in Primär-/Sekundärziele, Aktivstil am geschlossenen Auslöser, Trenner und sein Breakpoint-Verhalten, Verweis auf die neuen Routen-Utilities. Keine neuen Tokens, kein dreizehntes Symbol, keine neue Lücke.

## Teststrategie

**Unit — `frontend/src/utils/projectRoutes.test.ts`:** Kardinalitäten (3 / 2 / 5), Reihenfolgen, Labels und `buildPath`. **Invariante statt Tabelle:** `ALL_PROJECT_NAV_TARGETS` ist exakt `[...primary, ...secondary]`, hat fünf **eindeutige** ids, und die beiden Teilmengen sind **disjunkt** — das ist der Wächter gegen den realistischsten Umbaufehler (ein Ziel landet beim Aufteilen in beiden Listen → doppelte React-Keys und eine doppelte Panelzeile). `isSecondaryNavTargetId` für jedes Ziel aus `ALL_…` gegen die Gruppenzugehörigkeit geprüft, plus `null`. `resolveActiveNavTargetId('/…/stats') === 'stats'`, `/curate` bleibt `null`. `PROJECT_ROUTE_PATHS` bleibt bei neun Mustern (Beleg für AK10).

**Komponente — `frontend/src/components/ProjectNav.test.tsx`:** Leiste (genau drei Links, Reihenfolge, `href`, sichtbarer Text = zugänglicher Name). Panel geöffnet: fünf Zeilen in fester Reihenfolge — **hier ausdrücklich fünf, nicht zwei**. Struktur der Gruppe (die in jsdom prüfbare Hälfte von AK5): die drei Hauptziel-Zeilen teilen sich innerhalb des Panels einen gemeinsamen Vorfahren, der keine der beiden Nebenzeilen enthält und nicht das Panel selbst ist — reine DOM-Struktur, keine CSS-Zusicherung. Markierung **pro Darstellung eingegrenzt** (Leiste / Panel / Auslöser, nie dokumentweit). Aktivmarker des Auslösers nicht allein farblich. Auswahl schließt und navigiert, je einmal für einen Neben- und einen Hauptzieleintrag. Tastatur: Enter öffnet, Escape schließt, Fokus kehrt zurück. Genau ein `navigation`-Landmark auch bei geöffnetem Panel.

**Integration — `frontend/src/App.test.tsx`:** der bestehende Synchronitäts-Wächter über die neun Projektkontext-Pfade bleibt, jetzt mit drei Zielen plus Auslöser je Pfad. **AK9 an genau einer Stelle prüfbar:** auf `/projects/1/pipeline/scan` bei geschlossenem Bereich kein Link mit `href="/projects/1/stats"`, bei geöffnetem genau einer. `/stats` und `/settings` routen unverändert (AK10, Lesezeichen-Beleg). `expectNoGroup()` auf `/` über die **fünf** Beschriftungen.

**Komponente — `frontend/src/pages/pipeline/ProjectPipelineLayout.test.tsx`:** der bestehende Test invertiert sich. **Nicht zur reinen Abwesenheitsprüfung verkommen lassen** — Anker im selben Test behalten (Schrittinhalt, Projektname/-pfad gerendert), dann: kein Link auf `/projects/1/stats`, und der bisherige `flex flex-wrap gap-3`-Container ist ganz verschwunden.

**Design-Vertrag — `frontend/src/designSystem.contract.test.ts`:** die `TALL_CONTROL_ALLOWLIST`-Fundstelle und das Aktiv-/Ruhend-Rezept bleiben wörtlich erhalten — **verifizieren, nicht annehmen**. Neu zu binden: die Trenner-Utilities (`mb-2 border-b border-separator pb-2 lg:hidden`) als Literal, was insbesondere die Token-Wahl `border-separator` sichert. `NAV_TRIGGER_ACTIVE_CLASSES` ist ein drittes, absichtlich abweichendes Rezept und wird der Stepper-Bindung nicht hinzugefügt.

**E2E — `e2e/tests/project-nav.spec.ts`** (nur was jsdom prinzipiell nicht kann; die bestehende Datei wird erweitert, keine neue angelegt):

- *Bestandsanpassung, sonst rot:* der Grenztest erwartet heute 4 sichtbare Ziele / Auslöser unsichtbar bei 1024 px und 0 / sichtbar bei 1023 px. Neu: **1024 → 3 sichtbare Ziele, Auslöser sichtbar; 1023 → 0 sichtbare Ziele, Auslöser sichtbar.** DOM-Vorbedingung bei **beiden** Breiten: `nav → locator('a')` genau 3, `button[aria-label="Projektbereiche"]` genau 1 (das ist zugleich die DOM-Hälfte von AK5).
- ⚠️ **Der Wirksamkeitsanker verschiebt sich:** bisher trug die Umkehrung *beider* Messgrößen den Beleg; jetzt ist die Auslöser-Sichtbarkeit auf beiden Seiten konstant `true`. Die „beide Messungen müssen sich unterscheiden"-Zusicherung muss ausschließlich an der Zahl der sichtbaren Ziele hängen (3 ≠ 0) — sie darf nicht auf ein Tupel gehen, das durch die konstante Hälfte immer „unterschiedlich genug" aussieht.
- *Neu (AK2/AK5-Panelinhalt über die Grenze):* Panel bei 1024 px öffnen → `panel.locator('a')` 5 (DOM), `panel.getByRole('link')` **2** („Einstellungen", „Statistik"); bei 1023 px → DOM 5, Rollen-Count **5** in fester Reihenfolge. `getByRole` sieht den Accessibility-Tree, `display:none` fällt heraus; die DOM-Zählung daneben schließt den trivialen Grün-Fall aus.
- *Neu (AK4):* bei 1024 px `boundingBox().width` des Auslösers gegen das Minimum der drei Hauptziel-Breiten, `≤ 0,75 ×`. Vorbedingungen: alle vier Elemente sichtbar, alle Breiten > 0.
- *Neu (AK5-Absetzung):* bei 360 px, Panel offen — Abstand Unterkante „Vergleich" → Oberkante „Einstellungen" **≥ 2 ×** größter Abstand zwischen zwei benachbarten Hauptzielen; zusätzlich `getComputedStyle` des trennenden Elements: `border-bottom-width > 0`, `border-bottom-style !== 'none'`, Alphakanal > 0.
- *Bestand, unverändert wertvoll:* Kopfzeilenhöhe bei 360 px, Einzeiligkeit bei 1024 px (Vorbedingungen von 4/0 auf 3/1 ziehen), Panel-Überlagerung bei 360 px — das Panel wächst um zwei Zeilen plus Trenner, die Zusage „vollständig im Sichtbereich" wird dadurch erst richtig scharf.
- **Rot-Nachweis Pflicht** für die drei neuen Zusicherungen: Trenner-Utilities entfernen → Abstandsprüfung rot; `size="icon"` durch `size="default"` mit Beschriftung ersetzen → AK4-Prüfung rot; `lg:hidden` am Hauptzielblock entfernen → Panelinhalts-Prüfung rot. Belege in die PR-Beschreibung.
- **Nebenbefund:** `e2e/tests/project-nav.spec.ts` trägt im Kopf „ROT-NACHWEIS STEHT NOCH AUS" aus Spec 0298 (in einer Remote-Session ohne Browser geschrieben). Dieser Branch fasst genau die Datei an und kann den Nachweis mitliefern — Empfehlung, keine Forderung.

**E2E — `e2e/tests/tap-targets.spec.ts` (Bestandsanpassung, sonst rot):** `navRows … toHaveCount(4)` → **5**. Empfehlung: zusätzlich die Zeile „Statistik" auf Treffbarkeit prüfen (sie ist das neu erreichbare Bedienelement), dann `EXPECTED_CONTROL_COUNT` 8 → **9**.

**Nicht betroffen (geprüft):** `popover-position.spec.ts` und `tap-targets.spec.ts` sind `MOBILE_ONLY`; `sticky-header`, `grid-columns`, `no-horizontal-scroll`, `empty-and-error-states`, `login`, `toolchain` und `e2e/lib/auth.ts` enthalten keinen dokumentweiten Button-/Dialog-Lokalisierer, der den ab jetzt auch bei 1280 px sichtbaren Auslöser neu treffen könnte. Backend unberührt, `--cov-fail-under=80` nicht tangiert.

### Edge Cases

1. **`/curate`** — kein Marker in der Leiste, **kein** Marker am Auslöser, keiner im Panel. Fängt die naheliegende Fehlimplementierung `activeTargetId === null ⇒ Nebenbereich aktiv` ab.
2. **Die Tabellen-Falle `it.each(['/stats','/curate'])`** — dieses Paar steht heute an drei Stellen und behauptet „kein Ziel aktiv". `/stats` muss dort **herausgenommen und als eigener Positivfall wieder aufgenommen** werden; wird es nur aus dem Array gestrichen, verschwindet die Zusage lautlos.
3. **Zwei gleichzeitige `aria-current`-Werte** auf `/settings`/`/stats` (`true` am Auslöser, `page` an der Zeile) — jede Zusicherung eingegrenzt auf Leiste, Panel oder Auslöser, nie dokumentweit.
4. **jsdom kennt keinen Breakpoint** — Tailwind greift dort nicht, der `lg:hidden`-Hauptzielblock liegt im Panel **immer** im DOM. Das Panel hat im Komponententest stets fünf Zeilen; ein `toHaveLength(2)` ist dort falsch und darf **nicht** durch ein `matchMedia`-Mock „repariert" werden — das prüfte den Mock, nicht Tailwind. Die Breakpoint-Zusage gehört ausschließlich in E2E.
5. **Ziel in beiden Gruppen** (Aufteil-Copy-Paste) → doppelter React-Key, doppelte Panelzeile; abgedeckt durch die Disjunktheits-/Eindeutigkeitsinvariante.
6. **Panelhöhe bei 360 × 900** mit fünf Zeilen plus Trenner — die bestehende „vollständig im Sichtbereich"-Zusage ist die Wächterin gegen ein unten herausragendes Panel.
7. **Fokusrückgabe bei Auswahl** — Radix gibt den Fokus beim Schließen an den Auslöser zurück, während gleichzeitig die Route wechselt; der Auswahl-Test baut nicht auf Fokus-Zusagen, sondern auf Pfad plus geschlossenem Panel.
8. **Query-String auf `/settings`** — kein neuer Fall nötig, die bestehende Trennung `pathname`/`search` ist bereits gebunden.

### Testkonzept nachzuziehen

[`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md) muss an drei Stellen ergänzt werden — jeweils an Ort und Stelle, keine neue Sektion, und **im selben PR wie der Code**, weil die Ergänzungen ein Muster beschreiben, das erst mit der Umsetzung entsteht:

1. **Sektion „Eine Zieltabelle, zwei Darstellungen":** (a) aus „zwei Darstellungen, zwei Auslöser-Zustände" wird „**ein** Auslöser, zwei Panel-Inhalte" — die Zusage ist damit eine DOM-**Kardinalität**, und die frühere Umkehrung zweier Messgrößen trägt den Breakpoint-Beleg nicht mehr; (b) `aria-current` liegt jetzt aus einem zweiten, vom Doppel-Rendering unabhängigen Grund doppelt vor, die Eingrenzungsregel gilt damit unabhängig von jsdom.
2. **E2E-Sektion, verallgemeinerte Regel:** *Eine „erkennbar/sichtbar"-Formulierung wird gegen eine im selben Lauf mitgemessene Bezugsgröße gestellt, nie gegen eine hartkodierte Pixelzahl.* Die Schwellenwerte selbst (75 %, Faktor 2) gehören in die Spec, nicht ins Testkonzept — sie sind Produktzusagen, keine Testmethodik.
3. **Umfangstabelle:** `project-nav`-Zeile um die drei neuen Zusicherungen ergänzen, `tap-targets`-Zeile auf fünf Panelzeilen und neun geprüfte Bedienelemente nachziehen.

Kein Eintrag unter „Bekannte Lücken" nötig — es fällt keine Zusage weg. Der dort geführte offene Punkt „Rot-Nachweis `project-nav` ausstehend" kann mit diesem Branch geschlossen werden.

## Security

**Nicht relevant.** `security-engineer` wurde nach der Skip-Prüfung des `spec-writer`-Ablaufs nicht konsultiert: Die Story hat keinen konkret benennbaren Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, dem Datenmodell oder der Sichtbarkeit von Daten zwischen den beiden Nutzern. Es werden ausschließlich bereits vorhandene, bereits erreichbare Navigationsziele umgruppiert — keine neue Route, kein neuer API-Aufruf, keine neue Eingabe, keine geänderte Zugriffsregel. Die betroffenen Seiten (`/settings`, `/stats`) stehen unverändert unter derselben Auth-Absicherung wie zuvor.

## Offene Fragen

Keine. Beide von `architect` weitergereichten Punkte (Beschriftung des Auslösers, Ausgestaltung des Trenners) sind durch `ux-ui-designer` entschieden, die beiden Abnahmemaße durch `test-engineer` festgelegt; die Abweichung zwischen den Trenner-Vorschlägen ist im Abschnitt UI/UX aufgelöst.

## Entscheidungen

- **Ein Auslöser statt zwei Popover-Instanzen** (`architect`). Zwei Instanzen legten zwei Buttons mit demselben zugänglichen Namen ins DOM und machten jede Rollen-Query mehrdeutig; mit einer Instanz ist AK5 im DOM prüfbar statt nur visuell.
- **Zieltabelle wird aufgeteilt und dabei umbenannt** (`architect`). Der Name `PROJECT_NAV_TARGETS` verschwindet bewusst, damit sich die Bedeutung eines Bezeichners nicht still unter allen Aufrufstellen ändert.
- **Trenner am Block der Primärziele, nicht als eigenes Element** — Auflösung der Abweichung zwischen `architect` und `ux-ui-designer` zugunsten des Blocks (Begründung im Abschnitt UI/UX).
- **Keine semantische Gruppierung des Nebenbereichs** (`ux-ui-designer`), rein visuelle Absetzung. Begründung im Abschnitt UI/UX.
- **Beschriftung bleibt „Projektbereiche"** (`ux-ui-designer`), routenunabhängig.
- **`chevron-down` bleibt, kein `ellipsis`** (`architect`, bestätigt durch `ux-ui-designer`) — eine Erweiterung des Zwölfer-Symbolsatzes wäre ADR-pflichtig und hier nicht nötig.
- **Keine ADR nötig** (`architect`): keine neue Technologie, keine neue Abhängigkeit, kein Datenmodell.
- **Gruppentrenner nutzt `--separator` auf `--elevated` — als benannte Regelausnahme, nicht als Einzelfall-Genehmigung** (`ux-ui-designer`, nach der Review-Runde zu diesem Branch). Die Dreiteilung der Rahmenrollen schloss `--separator` auf `--elevated`/`--overlay` bis dahin aus; ihre eigene Begründung („dort trennt die Flächenstufe") trifft auf eine Grenze *innerhalb* derselben Fläche aber nicht zu. Die Alternative `--border` (1,04–1,45:1) wurde als visuell untragbar verworfen. Die Ausnahme gilt allgemein für Panels und Popover mit Gruppengrenzen und ist an allen vier Stellen nachgezogen (`index.css`, Design-System-Dokument, Design-System-Eintrag der Navigationsgruppe, Vertragstest).
- **Abnahmemaße gegen mitgemessene Bezugsgrößen** (`test-engineer`): Auslöserbreite ≤ 75 % des schmalsten Hauptziels, Gruppenabstand ≥ 2 × größter Abstand innerhalb der Gruppe — statt hartkodierter Pixelzahlen, die auf den heutigen Schriftgrad kalibriert wären.
- **AK11 ist ein Review-Kriterium am Diff, kein Testfall** (`test-engineer`) — ein Test, der „hat sich nichts geändert" behauptet, ist eine Tautologie.
- **Breakpoint bleibt `lg:` (1024 px)** (`architect`) — mit drei Beschriftungen wäre `md:` vermutlich machbar, aber kein Akzeptanzkriterium verlangt es, und eine Verschiebung entwertete die gemessene Grenze aus Spec 0298 samt E2E-Absicherung.
- **`security-engineer` nicht konsultiert (Schritt 3):** kein konkret benennbarer Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, Datenmodell oder Datensichtbarkeit zwischen den beiden Nutzern — reine Umgruppierung bereits vorhandener, bereits erreichbarer Navigationsziele ohne Routen-, API- oder Datenänderung.

## Out of Scope

- Eine projektübergreifende, app-weite Einstellungsseite (existiert heute nicht und wird hier nicht eingeführt).
- Jede Änderung am Inhalt der Einstellungs- und der Statistikseite.
- Jede Änderung an der Kategorie-Kuratierung oder den Pipeline-Schritten.
- Verschiebung des Breakpoints von `lg:` auf `md:`.
- Erweiterung des Zwölfer-Symbolsatzes.
- **Verworfene einfachere Alternative:** Statistik als fünftes gleichrangiges Ziel in die bestehende Leiste zu hängen wäre deutlich einfacher und stellte die Erreichbarkeit ebenfalls her — es verfehlt aber die zweite Hälfte der Anforderung („soll wenig Platz wegnehmen") und verschärft die Enge der Leiste, statt sie zu lösen.
