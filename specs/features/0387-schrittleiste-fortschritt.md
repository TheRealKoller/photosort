# 0387 - Schrittleiste zeigt den Fortschritt und verdeckt die Kopfzeile nicht mehr

**Status:** Implemented ([PR #389](https://github.com/TheRealKoller/photosort/pull/389))
**Erstellt:** 2026-09-10
**Bezug:** [Issue #387](https://github.com/TheRealKoller/photosort/issues/387) (fasst zusätzlich den zuvor getrennt erfassten Befund #330 mit)

## Ziel

Die Schrittleiste der Pipeline hat zwei voneinander unabhängige Schwächen, die dieselbe Leiste
betreffen und deshalb gemeinsam behoben werden.

**Sie verdeckt die Kopfzeile.** Auf den Schrittseiten bleiben heute zwei Leisten gleichzeitig am
oberen Rand stehen. Sobald eine Seite lang genug zum Scrollen ist, liegt die Schrittleiste über
der Kopfzeile und verdeckt sie vollständig — samt „Abmelden" und dem Weg zurück ins Projekt.
Diese Bedienelemente sind dann nur noch erreichbar, indem man ganz nach oben scrollt. Mit dem
Demo-Bestand fällt das nicht auf, weil die geprüften Seiten kürzer als der Bildschirm sind; im
echten Betrieb mit vielen Fotos tritt es auf.

**Und sie zeigt den Fortschritt nicht.** Die Leiste sagt, welcher Schritt gerade offen ist, aber
nicht, wie weit der Durchlauf insgesamt gediehen ist. Gleichzeitig trägt sie neben jedem
gesperrten Schritt einen eigenen kleinen Auslöser, über den der Sperrgrund abrufbar ist — er
bringt Unruhe in eine Leiste, die Orientierung geben soll, und kostet Platz, der auf schmalen
Geräten für die Treffflächen fehlt.

Die gestalterische Antwort darauf ist in sechs Entwurfsrunden entstanden und liegt in der
Design-Quelle bereits vor (Baustein `step-marker` und Ansicht `schrittleiste` in
`design/penpot/`). Diese Spec ist deren Umsetzung im Produkt.

Beide Punkte teilen sich eine dritte Ursache: Für keine der beiden Fragen — was gilt, wenn
mehrere Bereiche gleichzeitig oben stehen bleiben, und wie ein gesperrter Schritt seinen Grund
preisgibt — trifft das Design-System heute eine tragfähige Festlegung. Es beschreibt stattdessen
den jetzigen, fehlerhaften Stand. Diese Festlegungen werden mit dieser Spec nachgezogen, sonst
beschreibt die verbindliche Quelle weiterhin das, was gerade abgelöst wird.

## User Story

Als Nutzer, der eine lange Pipeline-Schrittseite durchscrollt, möchte ich Kopfzeile und
Schrittleiste durchgehend sehen und bedienen können, auf einen Blick erkennen, wie weit der
Durchlauf insgesamt gediehen ist, und bei einem gesperrten Schritt den Grund direkt an ihm
erfahren, damit ich mich jederzeit orientieren und weiterbewegen kann, ohne an den Seitenanfang
zurückzukehren.

## Akzeptanzkriterien

Die Kriterien sind gegenüber dem Issue-Body auf Testbarkeit geschärft (`test-engineer`,
Schritt 3 des `spec-writer`-Ablaufs) — dieselbe Aussage, nur falsifizierbar formuliert. Der
Issue-Body bleibt unverändert die fachliche Fassung.

### Beide Leisten bleiben bedienbar

- [ ] Im gescrollten Zustand bleiben beide fixierten Leisten gleichzeitig vollständig sichtbar —
      keine verdeckt die andere ganz oder teilweise. Das gilt auf allen fünf Pipeline-Schrittseiten
      (gleiche Hülle, gleiche Leiste); nachgewiesen wird es an einer Schrittseite in beiden
      Breiten.
- [ ] Die Kopfzeile steht oben, die Schrittleiste unmittelbar darunter — **ohne Lücke und ohne
      Überlappung** (Unterkante Kopfzeile = Oberkante Schrittleiste).
- [ ] „Abmelden", der Weg zurück ins Projekt und die Auswahl eines erreichbaren Schritts sind im
      gescrollten Zustand bedienbar: Ein Zeigerdruck auf die Mitte des Bedienelements liefert
      dieses Element selbst und nicht eine darüberliegende Fläche.
- [ ] Auf schmalen Geräten fällt der dauerhaft fixierte Bereich schlanker aus: Die
      Orientierungszeile ist nicht mehr Teil des fixierten Bereichs und scrollt mit dem Inhalt
      weg; die Zahl der fixierten Bereiche bleibt zwei. Auch dort verdeckt nichts einander, und
      die dort sichtbaren Bedienelemente sind erreichbar.
- [ ] Das Verhalten aller übrigen Ansichten am oberen Seitenrand bleibt unverändert.

### Der Fortschritt ist ablesbar

- [ ] Unter den Schritten zeigt ein durchgehender Balken den zurückgelegten Weg; die rechte Kante
      des gefüllten Teils liegt auf der waagerechten Mitte des Schritts, auf dem man gerade steht.
- [ ] Der Balken ist in beiden Breiten dieselbe, einzige Fassung (ein DOM-Baum) und trägt
      denselben Wert.

### Der Sperrgrund steht am gesperrten Schritt

- [ ] Der eigene Auslöser neben gesperrten Schritten entfällt ersatzlos.
- [ ] Der gesperrte Schritt selbst gibt seinen Grund preis — am Rechner beim Überfahren, am
      Telefon beim Antippen. Die Gründe bleiben inhaltlich unverändert.
- [ ] Jeder gesperrte Schritt ist per Tabulator erreichbar und gibt dort per Eingabe/Leertaste
      seinen Grund preis; Escape schließt und gibt den Fokus zurück. (Heute ist der Grund für
      Tastaturnutzer gar nicht erreichbar.)
- [ ] Ein gesperrter Schritt bleibt als gesperrt erkennbar, ist kein Link und löst keine
      Navigation aus (die Route bleibt unverändert).

### Die Leiste folgt dem Entwurf

- [ ] Die Umrandung fasst nur noch das Zeichen des Schritts; die Beschriftung steht ohne
      Umrandung daneben und ist **kein Nachfahre** des umrandeten Elements.
- [ ] In der schmalen Fassung tragen die Schritte keine Beschriftung und verteilen sich über die
      volle Breite: Jeder Schritt ist bei 360 px an den vier Ecken eines 44×44-Bereichs treffbar
      und überlappt die Trefferfläche des Nachbarn nicht. Der Name des aktuellen Schritts steht
      weiterhin ausgeschrieben in der Orientierungszeile.
- [ ] Kein Schritt verschwindet, die Reihenfolge bleibt, und die vier Schrittzustände bleiben
      ohne Rückgriff auf Farbe allein unterscheidbar. Sind mehrere Merkmale gleichzeitig wahr
      (z.B. erledigt und gesperrt), gilt eine festgelegte, dokumentierte Rangfolge — sie bleibt
      die heutige (Haken vor Schloss, „aktuell" gewinnt gegen „erledigt").
- [ ] Welche Schritte erreichbar, erledigt oder gesperrt sind, wird unverändert hergeleitet —
      diese Spec ändert die Darstellung, nicht die Regeln.

### Was verbindlich nachgezogen wird

- [ ] Das Design-System beschreibt danach, wie sich mehrere gleichzeitig fixierte Bereiche am
      oberen Rand zueinander verhalten, einschließlich der Abweichung auf schmalen Geräten.
- [ ] Das Design-System beschreibt danach, dass ein gesperrter Schritt seinen Grund selbst
      preisgibt, statt weiterhin einen eigenen Auslöser daneben vorzuschreiben.
- [ ] Eine Regressionsabsicherung stellt für eine Schrittseite im gescrollten Zustand sicher,
      dass die sichtbaren Bereiche der beiden fixierten Leisten sich nicht überschneiden —
      geprüft in einer schmalen und einer breiten Fassung.
- [ ] Der Eintrag zu diesem Befund unter „Bekannte Lücken" des Testkonzepts ist entfernt, sobald
      die Absicherung greift.

## Datenmodell-Bezug

Keiner. Die Spec ändert ausschließlich die Darstellung im Frontend; weder Entitäten noch
Schnittstellen noch die Herleitung der Schrittzustände werden angefasst
([`docs/architecture.md`](../../docs/architecture.md) bleibt unverändert).

## Architektur / Umsetzung

Die Story bündelt drei technisch unabhängige Probleme in einer Komponente. Sie werden auch
technisch getrennt gelöst: die Überlagerung ist ein **Layout-Vertrag zwischen App-Hülle und
Schrittleiste**, der Fortschrittsbalken und der Sperrgrund sind **Umbauten innerhalb der
Schrittleiste**. Nur der erste Teil fasst Code außerhalb von `Stepper.tsx` an.

### 1. Die Überlagerung: ein Höhen-Token, kein gemessener Wert und keine Verschmelzung der Leisten

Heute stehen beide Leisten auf `sticky top-0 z-10` (`frontend/src/App.tsx`,
`frontend/src/components/Stepper.tsx`); die im DOM spätere Leiste gewinnt. Gewählt wird der
**versetzte Haftpunkt über ein geteiltes Höhen-Token**:

- In `frontend/src/index.css` im `@theme`-Block ein Token `--spacing-header: 3.5rem` (56 px).
  Daraus erzeugt Tailwind v4 die Utilities `h-header` (Kopfzeile) und `top-header`
  (Schrittleiste). **Ein Wert, zwei Aufrufstellen** — kein zweiter, unabhängig gepflegter
  Zahlenwert.
- Die Kopfzeile in `App.tsx` bekommt `h-header` **statt** `py-3` (Border-Box, `border-b` ist
  eingerechnet; Inhalt sind `h-8`-Bedienelemente, die mittig stehen). `px-4 sm:px-6` bleibt.
- Die Schrittleiste tauscht `top-0` gegen `top-header`. Alles andere an ihr (`z-10`, `bg-bg/95`,
  `backdrop-blur-sm`, `border-b`) bleibt unverändert — auch, damit die begründete Freigabe für
  `bg-bg/95` in `designSystem.contract.test.ts` an ihrer Fundstelle gültig bleibt.

**Absicherung gegen den stillen Fehlschlag:** Eine unbekannte Utility ist in Tailwind kein
Buildfehler; `top-header` würde wirkungslos bleiben und die Leiste wäre gar nicht mehr haftend.
Deshalb im Vertragstest (`frontend/src/designSystem.contract.test.ts`) der dort bereits
vorhandene `producesRule`-Mechanismus (echter Tailwind-Lauf) für `h-header` und `top-header`
**plus Gegenprobe** mit einem erfundenen Namen. Erzeugt der `--spacing-*`-Namensraum wider
Erwarten keine `top-`-Utility, ist der Rückfallweg **gleichwertig und ebenfalls einquellig**:
`--header-height: 3.5rem` in `:root` und `h-(--header-height)`/`top-(--header-height)`. Nicht
zulässig ist in beiden Fällen ein zweiter, freihändiger Pixelwert an der Schrittleiste.

**Warum kein gemessener Wert (ResizeObserver → CSS-Variable):** Die Kopfzeile hat bereits eine
verbindliche, im Prüfsatz gebundene Eigenschaft — sie bricht bei keiner Breite in eine zweite
Zeile um (`e2e/tests/project-nav.spec.ts`, AK7 der Spec 0298/0347). Ihre Höhe ist damit eine
Konstante des Systems und keine Schätzung. Eine Laufzeitmessung führte ein im Projekt bisher
nicht vorhandenes Muster (Layout-Messung in der App-Hülle), einen Sprung beim ersten Render und
in jsdom nicht vorhandene Beobachter-APIs ein — Kosten ohne Gegenwert.

**Warum die Kopfzeile jetzt nicht umbrechen darf:** Mit fester Höhe wäre ein Umbruch stilles
Abschneiden statt sichtbaren Wachsens. Deshalb entfällt `flex-wrap` an der Kopfzeile, und
„Angemeldet als …" bekommt `min-w-0`/`truncate`. Damit schlägt zu enger Inhalt künftig laut an
(`e2e/tests/no-horizontal-scroll.spec.ts` bei 360 px) statt unsichtbar zu verschwinden.

**Verworfen: die Schrittleiste in die App-Hülle hochziehen** (beide Leisten in einem gemeinsamen
haftenden Block). Die Hülle müsste dafür Projektabfrage, Schrittzustände und Routen-Parameter der
Pipeline kennen — Fachlogik eines Teilbereichs wandert in den Rahmen, der heute bewusst nur
Marke, Navigationsgruppe und Abmelden trägt. Der Versatz löst dasselbe Problem ohne diese
Kopplung.

**Stapelordnung bleibt unangetastet:** Beide Leisten behalten `z-10`. Die Trennung ist ab jetzt
**geometrisch**, nicht über die Stapelordnung; Panels und Popover liegen weiterhin per Portal auf
`z-50` über beiden. Die Aussage „Panel über Kopfzeile und Stepper, beide `z-10`" in
`ProjectNav.tsx` bleibt damit wahr und wird nicht angefasst.

### 2. Was auf schmalen Geräten dauerhaft fixiert bleibt

Festgelegt und zu dokumentieren: **fixiert bleiben in beiden Breiten Kopfzeile und Schrittleiste
(Markenreihe + Fortschrittsbalken)**. Die Orientierungszeile „Schritt 3 von 5: …" — heute Teil
der haftenden Leiste und nur unterhalb `sm:` sichtbar — **wandert aus dem `<nav>` heraus** und
steht als nicht haftender Absatz unmittelbar darüber. Sie scrollt mit der Seite weg.

Damit ist der dauerhaft fixierte Bereich schmal rund 120 px statt rund 145 px, und — wichtiger —
**die haftende Leiste ist in beiden Breiten dieselbe**: ein DOM-Baum, kein zweiter Zweig, keine
breitenabhängige Sonderkonstruktion. Der Name des aktuellen Schritts steht schmal weiterhin
ausgeschrieben in dieser Zeile (Akzeptanzkriterium erfüllt); dass sie nach dem Scrollen nicht
mehr sichtbar ist, ist tragbar, weil der aktuelle Schritt in der Leiste durch Akzentrand, fetten
Schnitt und `aria-current="step"` markiert bleibt.

### 3. Der gesperrte Schritt trägt seinen Grund selbst

Der eigene `i`-Auslöser neben gesperrten Schritten entfällt ersatzlos; **der gesperrte Schritt
ist selbst der Popover-Auslöser**. Wiederverwendet wird das bereits dokumentierte Muster
„Info-Popover für situative Kurzerklärungen" samt geräteunabhängigem Öffnungsverhalten
(Radix-Popover aus `frontend/src/components/ui/popover.tsx`; Vorlage: das heutige
`BlockedReasonPopover` und `CriterionDetailsPopover.tsx`). **Kein neues Primitiv, keine neue
Abhängigkeit, kein Radix-Tooltip** — das ARIA-Tooltip-Muster ist hover/focus-only und öffnet
nicht per Tippen, was das Akzeptanzkriterium „am Telefon beim Antippen" verfehlt.

Verbindlich am Auslöser:

- **`<button type="button">` mit `aria-disabled="true"`, nie `disabled`.** `disabled` nimmt das
  Element aus der Tab-Reihenfolge *und* schaltet Zeigerereignisse ab — genau die heutige Lücke
  („für Tastaturnutzer gar nicht erreichbar"). `aria-disabled` sagt „dieser Schritt lässt sich
  nicht öffnen" und lässt ihn fokussierbar. Es wird kein `<Link>` gerendert; es gibt keinen
  Navigationspfad. Der heutige `<span aria-disabled tabIndex={-1}>` entfällt.
- **Öffnen:** Klick/Tippen (Radix, nativ), Überfahren nur bei
  `matchMedia('(hover: hover) and (pointer: fine)')` — dieselbe Mechanik samt
  `justOpenedByHoverRef`-Klickunterdrückung wie heute. **Neu und nötig:** beim Öffnen per
  Überfahren muss `onOpenAutoFocus` unterdrückt werden (`event.preventDefault()`), sonst springt
  der Fokus beim bloßen Darüberfahren in das Panel — beim heutigen, nicht fokussierbaren Auslöser
  war das folgenlos, beim neuen wäre es ein Rückschritt. Verlässt der Zeiger einen per Überfahren
  geöffneten Auslöser, schließt das Panel wieder; der Grace-Bereich über die Portal-Grenze aus
  Spec 0041 wird **nicht** übernommen (der Panelinhalt ist ein Satz ohne Bedienelement, es gibt
  nichts zu erreichen).
- **Tastatur:** Tabulator erreicht den Schritt, Eingabe/Leertaste öffnet, Fokus geht ins Panel,
  Escape schließt und gibt den Fokus zurück (alles Radix-Voreinstellung). Zusätzlich steht der
  Grund als `sr-only`-Text im Baum und ist per `aria-describedby` am Auslöser verlinkt — damit
  hat Screenreader-Bedienung den Grund auch ohne Öffnen. Der zugängliche Name bleibt „Schritt 4
  von 5: Kriterien-Bewertung, blockiert".
- **Fokussierbare Elemente in der Leiste: genau fünf**, eines je Schritt (heute: vier bis sieben,
  weil gesperrte Schritte zwei Knoten hatten und der Schritt selbst keiner war). Das ist eine
  gute, in jsdom prüfbare Invariante.
- Die Schließen-Schaltfläche im Panel bleibt (der einzige nicht-räumliche Weg zurück beim
  Tippen).

Die Gründe selbst (`getBlockedReason`) und die Herleitung von erreichbar/erledigt/gesperrt
(`computeStepStates`) bleiben **wortgleich und logikgleich** — die Spec ändert die Darstellung,
nicht die Regeln.

### 4. Der Fortschrittsbalken: vorhandenes Primitiv, und die Spaltengeometrie ist tragend

Der Balken ist **keine neue Komponente**, sondern das bestehende
`frontend/src/components/ui/progress.tsx` (natives `<progress>`, Spur `--separator`, Füllung
`--accent`, `h-2`, `rounded-xs`) mit `aria-hidden="true"`. Begründung: Ein berechneter
Prozentwert lässt sich weder als Tailwind-Klasse ausdrücken (willkürliche Werte sind verboten,
dynamische Klassennamen erzeugt Tailwind ohnehin nicht) noch per Inline-Style, den das Frontend
heute an keiner einzigen Stelle verwendet. `<progress value max>` füllt exakt `value/max` der
Breite — genau die gesuchte Aussage, ohne neues Muster. `aria-hidden`, weil die Information
vollständig und besser im Schrittlisten-Baum steht (`aria-current`, Zustand im Namen,
Orientierungszeile); ein zweites, prozentual vorgelesenes Fortschrittselement wäre Lärm.

Der Wert kommt aus einer **exportierten reinen Funktion** in
`frontend/src/utils/pipelineSteps.ts` (Muster wie `computeStepStates`/`sortCategoryKeys`,
unit-getestet, kein Ausdruck im JSX):

```
stepProgress(activeIndex) -> { value: 2 * activeIndex + 1, max: 2 * PIPELINE_STEPS.length }
```

also 10/30/50/70/90 % — die Mitte der jeweiligen Schrittspalte. Negativer/unbekannter Index ⇒
`value: 0`.

**Damit das stimmt, ist die Spaltengeometrie tragend und kein Kosmetikdetail:** Die fünf Schritte
stehen in **exakt gleich breiten Spalten ohne Abstand zwischen den Spalten**
(`<ol className="flex">`, je `<li className="min-w-0 flex-1 basis-0">`), und der Balken liegt als
Geschwister **im selben Kasten** direkt darunter. Nur dann liegt das Ende der Füllung wirklich
unter der Spaltenmitte. Ein `gap-*` am `<ol>` verschöbe die Spaltenmitten gegenüber der
Balkenskala (bei `gap-3` um bis zu ~5 px an den Rändern) — der sichtbare Abstand zwischen den
Marken kommt deshalb aus einer Polsterung **innerhalb** der Spalte, nicht aus einem
Spaltenabstand. Umgesetzt als `px-1` am spaltenfüllenden Bedienelement (nachgezogen bei der
Umsetzung; ein `mx-1` am Marker selbst wäre neben dessen `w-full` über die Spalte
hinausgelaufen — die Wirkung ist dieselbe, 8 px zwischen zwei Marken, und die tragende Zusage
„kein Spaltenabstand am `<ol>`" bleibt unberührt). Dieser Zusammenhang gehört als Kommentar an
die Stelle, sonst „räumt" ihn die nächste Überarbeitung weg.

Die heutigen Verbindungslinien zwischen den Schritten
(`<span className="h-0.5 flex-1 bg-separator" />`) entfallen ersatzlos — der durchgehende Balken
ist ihr Nachfolger.

### 5. Das Schloss bleibt dateilokal — der Symbolsatz wächst nicht

**Entscheidung: Der Zwölf-Zeichen-Satz in `frontend/src/components/ui/icon.tsx` bleibt bei
zwölf.** Das Schloss bleibt ein dateilokales SVG und zieht mit der Marke in die neue Datei um.
Gründe:

1. Der Satz ist keine Sammlung, sondern eine **belegte Ableitung**: alle zwölf Zeichen sind
   nachgewiesene Lucide-Pfade des Boards (ADR 0055 Punkt 7a). Ein dreizehntes hätte diesen Beleg
   nicht — es wäre eine Gestaltungsentscheidung ohne Vorlage, und genau dagegen ist der Satz
   ausdrücklich geschützt.
2. Der Penpot-Entwurf, der hier maßgeblich ist, **entscheidet die Frage selbst in dieselbe
   Richtung**: Er führt „schloss" als benannte Lücke und hält fest, dass eine Erweiterung des
   Satzes „in eine eigene Story" gehört.
3. Die Reichweite steht in keinem Verhältnis zum Nutzen: ein dreizehntes Zeichen berührt
   `icon.tsx`, dessen Tests, die parametrisierten Vertragszusagen, die Penpot-Nutzlast samt
   Kardinalitäten in `verify.js` und die Aussage „Zwölfer-Symbolsatz" in Design-System und ADR —
   für **einen** Aufrufer, der heute funktioniert.

Umsetzung: Der Kommentarblock in `icon.tsx`, der die dokumentierten Lücken des Satzes aufzählt,
bekommt das Schloss als **siebte** benannte Lücke (nach `↳` als sechster). Die Penpot-Lücke
„schloss" in `design/penpot/views.json` bleibt bestehen und wird **nicht** geschlossen — einzig
ihre Ortsangabe wird nachgezogen (das Schloss lebt ab jetzt in `StepMarker.tsx` statt in
`Stepper.tsx`), damit die Design-Quelle keinen Stand beschreibt, den es nicht mehr gibt.

### 6. Komponentenschnitt: die Marke wird eigener Baustein, die Leiste bleibt Ansicht

Der Entwurf ist an dieser Stelle maßgeblich und weicht vom heutigen Code ab: **Der Baustein ist
allein die Marke, nicht Marke plus Beschriftung.** Umsetzung:

- **Neu: `frontend/src/components/StepMarker.tsx`** — rein präsentational, ohne Zustand, ohne
  Routing. Props: `auspraegung: 'erledigt' | 'aktuell' | 'ausstehend' | 'blockiert'`, die
  Schrittnummer und `istErledigt` (bei der Umsetzung ergänzt; Vorgabewert
  `auspraegung === 'erledigt'`). Die dritte Prop ist nötig, weil Zustandsbenennung und
  Glyphenwahl **zwei verschiedenen Rangfolgen** folgen (siehe Edge Case 2): ein erledigter,
  inzwischen wieder gesperrter Schritt heißt „blockiert" und zeigt trotzdem den Haken — ohne
  diese Angabe könnte der Marker die Glyphe nicht wählen. Gesetzt wird sie nur dort, wo beide
  Aussagen auseinanderfallen. Rendert die umrandete Fläche mit genau einer Glyphe
  (Haken / Nummer / Schloss), setzt `data-step-state`, enthält das lokale `LockIcon`. Größe:
  `h-8 w-full sm:size-8 sm:shrink-0` — schmal über die Spalte gedehnt, ab `sm:` quadratisch.
  Tokens aus `design/penpot/components.json` (`radius.md`, `text.xs`, Flächen/Umriss/Schrift je
  Ausprägung).
- Die Zustände **überfahren/gedrückt** kommen vom umschließenden Bedienelement und werden am
  Marker als `group-hover:`/`group-active:` ausgedrückt (das umschließende Element trägt
  `group`). Das ist die erste Verwendung des `group`-Musters im Projekt und deshalb ausdrücklich
  zu kommentieren. **Nicht** zulässig hier: `aria-disabled:`-Varianten als Stilquelle — der
  Zustandsscanner der Penpot-Nutzlast (`frontend/penpot/payload.test.ts`) verlangte dann eine
  Achse `aria-disabled` in `components.json`, die der Entwurf nicht führt. „Blockiert" ist eine
  **Ausprägung**, kein Zustand.
- **`Stepper.tsx` behält** die Leiste als Ansicht: Skip-Link (unverändert), Orientierungszeile
  (jetzt außerhalb des `<nav>`), `<nav>` mit `<ol>`, je Schritt genau ein Bedienelement (`<Link>`
  oder gesperrter `<button>`), Beschriftung ohne Umrandung neben der Marke (`hidden sm:block`,
  umbrechend, nie gekürzt), Sperrgrund-Popover, Fortschrittsbalken.
- Trefferfläche: Das Bedienelement füllt die Spalte und trägt `tap-target` (**nur** senkrecht
  aufspannend) statt des bisherigen `tap-target-square` am Marker. Damit gibt es keinen
  waagerechten Überhang und keine überlappenden Trefferflächen zwischen Nachbarn — die
  12-px-Regel für aufgespannte Bedienelemente ist erfüllt, ohne einen Spaltenabstand zu brauchen
  (siehe 4.). Schmal ist jede Spalte ~72 px breit.
- **`design/penpot/components.json`:** `quellen` des Bausteins `step-marker` wandert von
  `src/components/Stepper.tsx` auf `src/components/StepMarker.tsx` — der Nutzlasttest prüft die
  Existenz der genannten Produktdatei und scannt sie auf getragene Zustände. Sonst nichts an der
  Nutzlast; Kardinalitäten bleiben.

### Wiederverwendet vs. neu

| Sache | Herkunft |
|---|---|
| Sperrgrund-Popover, geräteunabhängiges Öffnen | wiederverwendet (`ui/popover.tsx`, Muster „Info-Popover", Mechanik aus `CriterionDetailsPopover.tsx`) |
| Fortschrittsbalken | wiederverwendet (`ui/progress.tsx`, natives `<progress>`) |
| Ableitung erreichbar/erledigt/gesperrt, Sperrgründe | unverändert (`utils/pipelineSteps.ts`) |
| Reine Funktion statt Ausdruck im JSX | wiederverwendetes Projektmuster (`stepProgress`) |
| Symbolsatz | unverändert bei zwölf; Schloss bleibt dateilokal |
| Höhen-Token für fixierte Bereiche | **neu** (`--spacing-header` im `@theme`-Block, zwei Aufrufstellen) |
| `group-hover:`/`group-active:` | **neu** im Projekt, auf `StepMarker.tsx` begrenzt |
| `aria-disabled`-Bedienelement als Popover-Auslöser | **neu** im Projekt |
| Ausgelagerter Baustein `StepMarker` | **neu**, folgt dem Entwurf |

### Betroffene Dateien

Produktcode

- `frontend/src/index.css` — Höhen-Token im `@theme`-Block
- `frontend/src/App.tsx` — Kopfzeile auf feste Höhe, kein Umbruch, Nutzername gekürzt statt
  umbrechend
- `frontend/src/components/Stepper.tsx` — Versatz, Orientierungszeile heraus, Spaltenlayout,
  Balken, gesperrter Schritt als Auslöser, Verbindungslinien entfallen
- `frontend/src/components/StepMarker.tsx` — **neu**
- `frontend/src/components/ui/icon.tsx` — nur der Lückenkommentar (siebte Lücke)
- `frontend/src/utils/pipelineSteps.ts` — `stepProgress`

Tests

- `frontend/src/components/StepMarker.test.tsx` — **neu**
- `frontend/src/components/Stepper.test.tsx` — Umbau (fünf fokussierbare Elemente, kein eigener
  Info-Auslöser mehr, Tastaturweg zum Grund, `aria-describedby`, Balkenwert je aktivem Schritt)
- `frontend/src/utils/pipelineSteps.test.ts` — `stepProgress`
- `frontend/src/designSystem.contract.test.ts` — `h-header`/`top-header` erzeugen tatsächlich
  Regeln (mit Gegenprobe)
- `frontend/src/App.test.tsx` — Kopfzeile, soweit betroffen
- `frontend/penpot/payload.test.ts` — nur, falls die Quellenzuordnung explizit erwähnt ist
- `e2e/tests/sticky-header.spec.ts` — die bisher bewusst ausgelassene Zusicherung **disjunkter
  y-Bereiche** beider fixierter Leisten im gescrollten Zustand; der Spec läuft ohne Änderung an
  `e2e/playwright.config.ts` bereits in beiden Breiten (360/1280). Der Kommentarblock „BEWUSST
  NICHT ENTHALTEN" wird durch die Begründung der jetzt geltenden Zusage ersetzt.

Doku im selben PR

- `specs/architecture/0004-design-system.md`: (a) das Verhalten mehrerer gleichzeitig fixierter
  Bereiche am oberen Rand einschließlich der Abweichung auf schmalen Geräten aus 1./2.; (b) der
  gesperrte Schritt gibt seinen Grund selbst preis — der Eintrag „daneben ein
  `i`-Popover-Trigger" im Muster „Sticky Stepper-Fortschrittsnavigation" wird abgelöst; (c) der
  Baustein ist die Marke allein, Beschriftung ohne Umrandung; (d) das Schloss als siebte Lücke
  des Symbolsatzes.
- `specs/architecture/0002-testkonzept.md`: Eintrag „Zwei sticky `top-0`-Elemente überlagern sich
  auf den Pipeline-Routen" aus „Bekannte Lücken" entfernen und die Zeile zu `sticky-header` in
  der Spec-Tabelle nachziehen (der Vorbehalt „**Nicht** enthalten: … disjunkter y-Bereiche"
  fällt).
- `docs/architecture.md` und `docs/setup.md` bleiben **unverändert**: weder Komponentenschnitt
  des Systems noch Datenmodell noch lokales Setup ändern sich. Das ist geprüft, nicht vergessen.

### Reihenfolge der Umsetzung

Von innen nach außen, jeder Schritt rot vor grün:

1. `stepProgress` in `utils/pipelineSteps.ts` (reine Funktion, Test zuerst).
2. Höhen-Token in `index.css` + Vertragstest, dass beide Utilities Regeln erzeugen.
3. Kopfzeile in `App.tsx` auf das Token; Schrittleiste auf `top-header`. **Danach ist Teil (1)
   der Story vollständig** — guter Zwischenstand für einen Commit und den Rot-Nachweis des
   e2e-Specs (mit erzwungenem `top-0` an der Leiste muss die neue Zusicherung rot sein; dieser
   Nachweis gehört in die PR-Beschreibung).
4. `StepMarker.tsx` mit Test — vier Ausprägungen, Glyphenwahl, `data-step-state`.
5. `Stepper.tsx` umbauen: Orientierungszeile heraus, Spaltenlayout, Marke + Beschriftung,
   Verbindungslinien entfernen, Balken darunter.
6. Gesperrten Schritt zum Auslöser machen, eigenen `i`-Auslöser entfernen; Tastatur- und
   Zeigerwege testen.
7. Penpot-Quellenzuordnung, Lückenkommentar in `icon.tsx`, e2e-Zusicherung, Doku.

Schritt 3 und die Schritte 4–6 sind voneinander unabhängig; scheitert einer, blockiert er den
anderen nicht.

### Keine ADR

Die ADR-Auslöser aus `CLAUDE.md` (neue Technologie, Grundstruktur des Datenmodells, externe
Abhängigkeit) treffen alle nicht zu: kein Backend-/Datenmodell-Bezug, keine neue Abhängigkeit
(Radix, Tailwind, Lucide sind vorhanden, der Symbolsatz wächst ausdrücklich nicht). Die einzige
Festlegung mit Reichweite über diese Spec hinaus — wie sich mehrere gleichzeitig fixierte
Bereiche am oberen Rand zueinander verhalten — hat durch die Akzeptanzkriterien bereits einen
benannten Ort: das Design-System. Eine ADR daneben schüfe ein zweites Abbild derselben Regel, und
zwei Abbilder driften.

## UI/UX

Die Schrittleiste wird aus zwei voneinander unabhängigen Problemen des bisherigen Sticky-Stepper-Musters heraus umgestaltet — die neue Gestalt folgt dem Penpot-Entwurf (`schrittleiste`-Ansicht und `step-marker`-Baustein in `design/penpot/`).

### Layout und Fixierung

Beide Leisten (Kopfzeile + Schrittleiste) bleiben in beiden Breiten fixiert oben, ohne sich zu überlagern — ihre Verteilung nutzt ein gemeinsames Höhen-Token `--spacing-header: 3.5rem` (56px) im `@theme`-Block von `index.css`. **Kopfzeile** setzt `h-header`, **Schrittleiste** rückt via `top-header` ab; damit ist ein Wert die Quelle für beide Entfernungen. Dieser Zusammenhang wird im Vertragstest (`designSystem.contract.test.ts`) mit echtem Tailwind-Durchlauf gegen einen erfundenen Namen geprüft (Absicherung gegen stillen Fehlschlag von `top-header`).

Auf **schmalen Geräten** fixiert bleibt allein die Kopfzeile und die Schrittmarken-Reihe mit Fortschrittsbalken (~120px insgesamt); die darunter liegende Orientierungszeile „Schritt 3 von 5: Kriterien-Bewertung" wird zum nicht-haftenden Absatz und scrollt weg. Sie steht weiterhin als ausgeschriebener Name des aktuellen Schritts zur Verfügung, auch nach dem Scrolling — der aktive Schritt ist in der Leiste durch Akzentrand, fetten Schnitt und `aria-current="step"` dauermarkiert. Die Reduktion von ~145px auf ~120px fixierter Höhe schlankt den genutzten Platz spürbar, besonders bei dem breite-beschränkten Inhaltsbereich der Seite.

### Vier Schrittzustände — ohne Farbe allein unterscheidbar

Der Marker ist **nicht die Verbindungslinie**, sondern allein die Glyphe und ihre Umrandung. Vier Ausprägungen nach dem Entwurf:

- **erledigt:** Fläche `color.surface`, Umriss `color.border-control`, weißes **Häkchen** (Symbol bestätigt; nicht nur Grün). Im `group-hover:` wird die Fläche `color.overlay` und die Schrift `color.text-h`.
- **aktuell:** Fläche `color.overlay`, Umriss `color.accent` (Ring-Signal statt nur Farbe), **fettgedruckte Beschriftung** auf Breit, `aria-current="step"`. Im `group-hover:` verstärken sich Umriss und Schrift zusätzlich.
- **ausstehend:** Fläche `color.surface`, Umriss `color.border-control`, `color.text`, als echter `<Link>`. Im `group-hover:` analog zu erledigt.
- **blockiert:** Fläche `color.surface`, Umriss `color.border` (gedämpfter), Schrift `color.text-muted`, **Schloss-Symbol** (Form sagt „nicht verfügbar"), `aria-disabled="true"` (nicht `disabled`), kein `<Link>`. Der Schritt ist als Ganzes der Popover-Auslöser für den Grund; im `group-hover:` wird die Fläche `color.overlay` und die Schrift `color.text-h`.

### Breiten und Spalten-Geometrie

**Schmal (<sm):** Fünf Marker verteilen sich über die volle Inhaltsbreite ohne Abstand zwischen den Spalten, je Marker `h-8 w-full` (gedehnt rechteckig). Beschriftung `hidden`, nur die Glyphe sichtbar. Die Spaltengeometrie ist **tragend**: die Füllung des Fortschrittsbalkens endet unter der Mitte der Spalte, deshalb keine `gap` am `<ol>`, sondern Abstand **innerhalb** der Spalte — `px-1` am spaltenfüllenden Bedienelement (siehe Architektur, Punkt 4).

**Breit (≥sm):** Fünf Marker bleiben quadratisch `size-8 sm:shrink-0`, Beschriftung daneben unbegrenzt umbruchend, nie gekürzt. Gleiche Spalten-Geometrie — keine Abstände zwischen Spalten, Marker-Abstand innen.

### Fortschrittsbalken

Durchgehender, flüssiger Balken direkt unter den Marken, niedriges `h-2` in `color.separator` (Spur) und `color.accent` (Füllung). Die Füllung folgt der Spaltenlösung: Längen von 10/30/50/70/90% (reine Funktion `stepProgress()` in `utils/pipelineSteps.ts`, unit-getestet, nicht inline im JSX). Der Balken liegt als Geschwister im selben Kasten direkt unter `<ol>`, kein separates Element. `aria-hidden="true"`, da die Information im Schrittlisten-Baum vollständig steht (`aria-current="step"`, Zustandsnamen, Orientierungszeile).

**Bekannte Lücke:** Das Board führt diesen Balken mit durchgängiger Füllung bis zur Schrittkante (nicht nur zur Spalten-Mitte) — die Spalten-Geometrie wird hier **notwendig** vom Design-System festgelegt (siehe unten), um Abweichung zu vermeiden.

### Sperrgrund am gesperrten Schritt

Der blockierte Schritt trägt als Bedienelement (`<button type="button" aria-disabled="true">`) selbst den Popover-Auslöser (das `BlockedReasonPopover`-Muster, wiederverwendet aus Spec 0041 / `CriterionDetailsPopover`). Das Popover öffnet über Klick/Tippen und (bei `hover`-Zeiger) Überfahren. Der Grund wird zusätzlich als `sr-only`-Text im DOM stehen und per `aria-describedby` am Auslöser verlinkt — damit Screenreader-Nutzung den Grund auch ohne Öffnen bekommt.

**Zugänglichkeit:** Tabulator erreicht jeden Schritt (genau fünf fokussierbare Elemente), Eingabe/Leertaste öffnet das Popover beim blockierten Schritt, Escape schließt und gibt den Fokus zurück. Ein eigener `i`-Button neben blockierten Schritten entfällt ersatzlos.

### Design-System: Festlegungen

Zwei Einträge sind im Design-System (`specs/architecture/0004-design-system.md`) nachzuziehen und nicht vorher an anderer Stelle festzulegen:

1. **Mehrere gleichzeitig fixierte Bereiche am oberen Rand:** Das bisherige Sticky-Stepper-Muster (`sticky top-0 z-10`) wird ergänzt um die Regel, dass **Kopfzeile und Schrittleiste beide fixiert bleiben und sich nicht überlagern, über ein gemeinsames Höhen-Token**. Auf schmalen Geräten wird die fixierte Gesamthöhe schlanker (Orientierungszeile scrollt), die Regel bleibt: keine Überlagierung, beide vollständig sichtbar.

2. **Gesperrter Schritt preist seinen Grund selbst preis:** Das Muster „Sticky Stepper-Fortschrittsnavigation" wird darin korrigiert, dass ein blockierter Schritt seinen Grund nicht mehr über einen eigenen `i`-Auslöser neben sich preisgibt, sondern der **Schritt selbst ist der Popover-Auslöser** (Info-Popover-Muster, wiederverwendet). Der Grund ist für Tastaturnutzer dadurch (über Tab + Enter) erreichbar — bisher nicht.

Die Werte und Farb-Token (`erledigt`, `aktuell`, etc. nach `step-marker`-Baustein in Penpot) und die Spalten-Geometrie (fünf gleichbreite Spalten ohne Abstand, Abstand innen) sind Umbauten innerhalb des bestehenden Musters, keine neuen Festlegungen.

## Teststrategie

Festgelegt vor der Umsetzung (`test-engineer`, 2026-09-10). Die Spec bündelt drei technisch
unabhängige Teile; sie bekommen drei getrennte Nachweisketten. Leitsatz: **jede Zusage wird auf
der niedrigsten Ebene geprüft, die sie überhaupt widerlegen kann.** Arithmetik gehört in den
Unit-Test, Struktur/Rollen/Tastaturweg nach jsdom, und in e2e geht ausschließlich, was echte
Geometrie oder echtes CSS braucht (Aufnahmekriterium der e2e-Ebene). Ein e2e-Fall, der eine
jsdom-Zusicherung nachbaut, ist ein Muss-Fix-Finding.

### Ebenen im Überblick

| Zusage | Ebene | Datei |
|---|---|---|
| `stepProgress` liefert 10/30/50/70/90 %, Rand-/Fehlwerte ⇒ 0 | Unit | `frontend/src/utils/pipelineSteps.test.ts` |
| Vier Ausprägungen, Glyphenwahl, `data-step-state`, keine Zustandsachse `aria-disabled` | Komponente | `frontend/src/components/StepMarker.test.tsx` (neu) |
| Genau fünf fokussierbare Elemente, Sperrgrund per Tastatur/Zeiger, `aria-describedby`, Balkenwert je aktivem Schritt, Orientierungszeile außerhalb des `<nav>`, Beschriftung außerhalb der Umrandung | Komponente | `frontend/src/components/Stepper.test.tsx` |
| Kopfzeile ohne Umbruch, Nutzername gekürzt statt umbrechend | Komponente | `frontend/src/App.test.tsx` |
| `h-header`/`top-header` erzeugen echte Regeln; kein zweiter Pixelwert; kein `top-0` mehr an der Leiste | Vertrag (echter Tailwind-Lauf) | `frontend/src/designSystem.contract.test.ts` |
| Quellenzuordnung des Bausteins `step-marker` zeigt auf die neue Datei | Nutzlast | `frontend/penpot/payload.test.ts` |
| Disjunkte, fugenlose y-Bereiche beider fixierter Leisten; Bedienbarkeit im gescrollten Zustand | e2e (360 **und** 1280) | `e2e/tests/sticky-header.spec.ts` |
| Gleich breite, abstandslose Spalten; rechte Kante der Balkenfüllung auf der Spaltenmitte des aktiven Schritts | e2e (360 **und** 1280) | `e2e/tests/stepper-progress.spec.ts` (neu) |
| Trefferflächen der Schritte bei 360 px, ohne Überlappung mit dem Nachbarn | e2e (360) | `e2e/tests/tap-targets.spec.ts` |

Unverändert bestehende Prüfungen, die diese Spec **mit** absichern und deshalb grün bleiben
müssen (kein neuer Code, aber Teil der Abnahme): `no-horizontal-scroll` deckt `/pipeline/scan`
bei 360 px bereits ab — das neue Fünf-Spalten-Layout und der entfallene `flex-wrap` der Kopfzeile
schlagen dort an, statt still abzuschneiden; `project-nav` misst die Kopfzeilenhöhe bei 360 px
gegen dieselbe Kopfzeile ohne Projektbezug — mit `h-header` bleibt das eine gültige, jetzt
zusätzlich token-gebundene Aussage; der erste Fall in `sticky-header.spec.ts` sichert
„**genau ein** sticky Element auf der Foto-Route" und ist damit bereits der Nachweis für
„Das Verhalten aller übrigen Ansichten am oberen Seitenrand bleibt unverändert".

### Unit: `stepProgress`

Reine Funktion, Tabellentest über alle fünf gültigen Indizes (`{1,10}`, `{3,10}`, `{5,10}`,
`{7,10}`, `{9,10}`) plus die Randfälle `-1`, `5` (ein Index hinter dem letzten Schritt) und ein
nicht-ganzzahliger bzw. `NaN`-Wert ⇒ `value: 0`, `max` immer `2 * PIPELINE_STEPS.length`. **`max`
wird aus `PIPELINE_STEPS.length` hergeleitet, nie als `10` erwartet** — sonst ist der Test bei
einer sechsten Pipeline-Stufe still falsch statt rot. Zusätzlich eine Invariante statt fünf
Einzelwerte: `value` wächst streng monoton mit `activeIndex` und liegt immer echt zwischen `0`
und `max` (der Balken ist nie voll — „fertig" gibt es in dieser Pipeline nicht, siehe
`isDone: false` für `kuratierung`).

Der Unit-Test beweist die **Zahl**, nie die **Deckungsgleichheit mit der Spaltenmitte**. Das ist
die Trennlinie zu e2e und der Grund, warum der offene Punkt unten so entschieden wird, wie er
entschieden wird.

### Komponente (jsdom): `StepMarker`

Neuer, rein präsentationaler Baustein ⇒ Tabellentest über die vier Ausprägungen mit je drei
Zusicherungen: gesetztes `data-step-state`, **genau eine** Glyphe (Haken / Nummer / Schloss — die
Abfrage über alle drei möglichen Glyphen zusammen muss Länge 1 ergeben, sonst wäre „Haken *und*
Nummer" grün), und kein eigener zugänglicher Name (der kommt vom umschließenden Bedienelement;
Glyphen `aria-hidden`). Vier verschiedene `data-step-state`-Werte, Mengengröße 4 — das ist die
Zusage „ohne Rückgriff auf Farbe allein unterscheidbar" in ihrer prüfbaren Form, und sie wird
über **alle vier** Ausprägungen geprüft, nicht wie bisher über drei.

Der Zustandsträger ist neu geteilt: `group` sitzt am Bedienelement in `Stepper.tsx`,
`group-hover:`/`group-active:` am Marker. Für den Penpot-Zustandsscanner zählt nur die Datei, die
in `quellen` steht — die Umhängung der Quellenzuordnung ist deshalb keine Kosmetik, sondern die
Bedingung dafür, dass der bestehende Scanner überhaupt noch die richtige Datei liest (siehe
„Vertrag und Nutzlast").

### Komponente (jsdom): `Stepper`

Umbau der bestehenden Datei. Bleibt inhaltlich gültig und wird **wortgleich** weitergeführt: die
drei Sperrgrund-Texte, die Reihenfolge der fünf Schritte, `aria-current="step"`, die
Skip-Link-Position vor dem `<nav>`, der zugängliche Name `Schritt N von 5: …, <Zustand>`. Die
e2e-Selektoren hängen an diesen Namen — eine Änderung dort wäre eine Änderung an drei Ebenen
zugleich und ist in dieser Spec nicht vorgesehen.

Neu bzw. geändert:

- **Genau fünf fokussierbare Elemente** (Kernnachweis, siehe „Die drei kritischen Zusagen").
- **Der gesperrte Schritt ist ein `<button>` mit `aria-disabled="true"`** — geprüft wird beides
  zugleich: `aria-disabled` ist gesetzt **und** das Attribut `disabled` ist *nicht* gesetzt
  **und** `tabindex` ist nicht `-1`. Der heutige Test sichert genau das Gegenteil zu
  (`toHaveAttribute('tabIndex', '-1')`) und wird ersetzt, nicht ergänzt.
- **„Lässt sich weiterhin nicht auslösen"** als echter Negativtest: der gesperrte Schritt ist kein
  Link (keine `link`-Rolle, kein `href`), und ein Klick darauf ändert die Route nicht. Dafür
  bekommt der Render-Helfer eine Standort-Sonde (kleine Komponente mit `useLocation()`, deren Pfad
  im DOM steht) — heute war „keine Navigation" strukturell unmöglich (`<span>`), ab jetzt ist es
  eine Verhaltenszusage und braucht einen Test.
- **`aria-describedby`**: das referenzierte Element existiert, liegt im Baum und trägt exakt den
  Sperrgrund-Wortlaut. Geprüft über die ID-Auflösung, nicht über eine Textsuche irgendwo im
  Dokument — sonst bestünde der Test auch bei einer verwaisten ID.
- **Balkenwert am gerenderten Element**: `value`/`max` des `<progress>` je aktivem Schritt, und
  die `progressbar`-Rolle ist im Baum **nicht** auffindbar (`aria-hidden="true"`). Beide zusammen,
  sonst ist „der Balken ist da" entweder unbelegt oder doppelt vorgelesen.
- **Orientierungszeile außerhalb des `<nav>`**: innerhalb des `<nav>` ist „Schritt N von 5" nicht
  mehr zu finden, und die Zeile steht im Dokument **vor** dem `<nav>` (`compareDocumentPosition`
  gegen die Bitmaske, nicht per Gleichheit). Eine reine „ist vorhanden"-Prüfung ginge an der
  Aussage vorbei.
- **Beschriftung ohne Umrandung**: die Beschriftung ist **kein Nachfahre** des Markers
  (`marker.contains(label) === false`), liegt aber im selben Bedienelement. Das ist die in jsdom
  prüfbare Hälfte von „Die Umrandung fasst nur noch das Zeichen des Schritts"; die Umrandung
  selbst ist CSS und gehört nicht hierher.
- **Ein DOM-Baum, keine zweite Fassung**: die bestehende Kardinalitätszusicherung (fünf
  `listitem`, jede Beschriftung genau einmal) bleibt und wird um den Balken erweitert — genau
  **ein** `<progress>` in der Leiste. Das ist zugleich die prüfbare Form von „Der Balken ist in
  beiden Breiten vorhanden und folgt derselben Logik": es gibt nur eine Fassung, also kann sie
  nicht auseinanderlaufen. **Kein zweiter jsdom-Lauf in einer zweiten Breite** — jsdom hat kein
  Layout, das wäre der immer-grüne Test, den das Testkonzept ausschließt.
- **Zeigerverhalten**, wiederverwendetes Muster aus `CriterionDetailsPopover.test.tsx` samt der
  dort dokumentierten `user-event`-Falle (Schließen per `fireEvent.mouseLeave` mit
  `relatedTarget`, nicht per `userEvent.unhover()`): Überfahren öffnet nur bei
  `matchMedia(...).matches === true`, Klick/Tippen öffnet unabhängig davon, Verlassen des
  Auslösers schließt ein per Überfahren geöffnetes Panel, ein per Klick geöffnetes bleibt stehen.
- **Neu und in dieser Toolchain zu verifizieren statt anzunehmen — Fokus beim Überfahren:** Nach
  einem Hover-Öffnen liegt der Fokus **nicht** im Panel (`onOpenAutoFocus`-Unterdrückung), nach
  einem Tastatur-/Klick-Öffnen **sehr wohl**. Zwei Fälle als Partition, nicht ein Positivfall —
  sonst wäre „Fokus springt nie" von „Fokus springt immer" nicht zu unterscheiden. Verhält sich
  Radix in jsdom hier anders als erwartet, wird der Befund im Testkonzept festgehalten, statt den
  Test wegzulassen.

### Die drei kritischen Zusagen

#### (a) Disjunkte y-Bereiche der beiden fixierten Leisten, schmal und breit

Ausschließlich e2e — `position: sticky` ohne Layout-Engine ist eine Zeichenkette. Umgesetzt im
bestehenden zweiten Fall von `e2e/tests/sticky-header.spec.ts`, der dafür gebaut wurde; der
Kommentarblock „BEWUSST NICHT ENTHALTEN" wird durch die Begründung der jetzt geltenden Zusage
ersetzt. Der Spec steht **weder** in `MOBILE_ONLY` **noch** in `DESKTOP_ONLY` und läuft damit
unverändert in beiden Breiten (360/1280); die eigene flache Viewport-Höhe von 300 px bleibt, weil
die Pipeline-Seiten mit dem Demo-Bestand sonst gar nicht scrollen und der Fall leer bestünde.
**Diese Zweibreitigkeit ist Teil der Zusage und darf nicht in einer Konfigurationsdatei still
verschwinden:** `e2e/tests/toolchain.spec.ts` bekommt dafür eine Assertion, dass kein
Viewport-Projekt diesen Spec ausschließt (dieselbe Mechanik, mit der `toolchain` bereits
`retries`/`workers`/die Projektliste bindet; `MOBILE_ONLY`/`DESKTOP_ONLY` werden dafür aus
`playwright.config.ts` exportiert).

Gemessen wird im **gescrollten** Zustand — und nur dort. Ungescrollt liegen zwischen Kopfzeile und
Leiste die 24 px `py-6` des `<main>`; eine Messung vor dem Scrollen prüfte die Polsterung statt
der Fixierung.

Erhalten bleiben die bestehenden Vorbedingungen (es wurde weiter gescrollt, als die Leiste
ursprünglich vom Seitenanfang entfernt war; **genau zwei** sticky Elemente; beide vollständig im
Sichtbereich). Neu dazu, in dieser Reihenfolge:

1. **Zuordnung statt Sortierung:** Die Kopfzeile (`banner`) hat die kleinere Oberkante, die Leiste
   (`navigation`, Name „Fortschritt der Pipeline") die größere. „Oben" ist eine Zusage der Spec,
   keine Hilfsannahme des Tests.
2. **Disjunkt:** `Unterkante(Kopfzeile) ≤ Oberkante(Leiste) + 1` (Subpixel-Toleranz, wie das im
   Spec bereits vorhandene `TOP_TOLERANCE`).
3. **Fugenlos:** `|Oberkante(Leiste) − Unterkante(Kopfzeile)| ≤ 1`. Das ist die eigentlich
   tragende Zusicherung, weil sie **in beide Richtungen** anschlägt: ein zu kleines Höhen-Token
   überlappt (2.), ein zu großes erzeugt eine sichtbare Fuge mit durchscrollendem Inhalt (3.).
   Zusammen binden sie die Behauptung „ein Wert, zwei Aufrufstellen" an das gerenderte Ergebnis
   statt an den Quelltext.
4. **Bedienbarkeit als Treffertest, nicht als Sichtbarkeit:** Im gescrollten Zustand liefert
   `document.elementFromPoint()` in der Mitte der „Abmelden"-Schaltfläche, in der Mitte des
   Auslösers der Projektnavigation und in der Mitte des ersten Schritts jeweils dieses Element
   selbst oder einen Nachfahren. `toBeVisible()` allein wäre hier wertlos: das heutige Fehlerbild
   ist eine vollständig **überdeckte**, aber laut DOM sichtbare Kopfzeile. Damit ist auch
   „`bg-bg/95` plus `backdrop-blur-sm` legt sich über den Nachbarn" abgedeckt, was reine
   Kastengeometrie nicht sieht.
5. **Schmal zusätzlich:** Die Orientierungszeile ist im gescrollten Zustand **nicht** mehr im
   Sichtbereich (ihre Unterkante liegt oberhalb des Viewports) — der prüfbare Kern von „Was schmal
   fixiert bleibt". Die Kardinalität „genau zwei sticky Elemente" ist die Gegenprobe dazu: würde
   die Zeile versehentlich mithaften, wären es drei.

**Rot-Nachweis (Pflicht, gehört in die PR-Beschreibung):** mit erzwungenem `top-0` an der Leiste
sind (2.), (3.) und (4.) rot; mit einem Token von `4rem` bei unveränderter Kopfzeilenhöhe ist (3.)
rot und (2.) grün — dieser zweite Nachweis belegt, dass die Fugen-Assertion nicht bloß eine
schwächere Kopie der Überlappungs-Assertion ist.

#### (b) Der gefüllte Balkenteil endet unter der Mitte des aktiven Schritts

Diese Zusage zerfällt in drei Teile, die auf drei verschiedenen Ebenen liegen und einzeln nichts
beweisen:

1. **Der Anteil** `value/max` — Unit-Test von `stepProgress`.
2. **Der gerenderte Wert** am `<progress>` — jsdom.
3. **Die Deckungsgleichheit von Anteil und Spaltenmitte** — nur e2e. Sie hängt an gleich breiten,
   abstandslosen Spalten und an einem Balken, der exakt denselben x-Bereich aufspannt wie die
   Schrittliste. Ein einziges `gap-3` am `<ol>` verschiebt die Spaltenmitten gegenüber der
   Balkenskala, ohne dass (1.) oder (2.) es merken.

Neuer Spec `e2e/tests/stepper-progress.spec.ts`, in beiden Breiten (kein Eintrag in
`MOBILE_ONLY`/`DESKTOP_ONLY` — die Spaltenaufteilung wechselt an `sm:` von „Marke über volle
Spaltenbreite" auf „Marke plus Beschriftung", ein zweiter Lauf ist hier also kein Leerlauf).
Ablauf je Lauf:

- Der aktive Schritt wird **aus dem DOM** hergeleitet: das `<li>`, das das Element mit
  `aria-current="step"` enthält, und dessen Index in der Liste. Nicht aus der aufgerufenen URL —
  ein Redirect des Routen-Wächters führte sonst dazu, dass die falsche Spalte gemessen wird und
  der Fall trotzdem grün ist.
- **Vorbedingung Spaltengeometrie:** fünf `<li>` mit `width > 0`, paarweise gleich breit
  (max. 1 px Abweichung, Subpixel-Rundung) und lückenlos aneinander
  (`x[i+1] − (x[i] + w[i]) ≤ 1`). Das ist die Zusicherung, die ein `gap-*` am `<ol>` unmittelbar
  rot macht.
- **Vorbedingung Balkenkasten:** linke und rechte Kante des `<progress>` stimmen mit der linken
  Kante des ersten und der rechten Kante des letzten `<li>` überein (≤ 1 px). Ohne sie wäre die
  Rechnung unten auf einen anderen Kasten bezogen als die Spalten.
- **Die Zusage:** `x(Balken) + Breite(Balken) · value/max` liegt auf der waagerechten Mitte des
  aktiven `<li>`, Toleranz **≤ 1 px**. `value` und `max` werden dabei vom gerenderten Element
  gelesen, nicht angenommen, und zusätzlich gegen `2·Index + 1` bzw. `2·5` geprüft — sonst
  bestünde die Rechnung auch mit einem festgefahrenen Wert.
- **Zwei Messungen, die sich unterscheiden müssen:** derselbe Ablauf auf `/pipeline/scan`
  (Index 0) und `/pipeline/ausschuss` (Index 1). Beide Schritte sind immer erreichbar, werden also
  nie umgeleitet. Die beiden ermittelten x-Positionen müssen verschieden sein. **Index 0 ist
  bewusst dabei**, weil er die empfindlichste Spalte ist: ein `gap-3` verschöbe die Mitte dort um
  ~4,8 px, in der *mittleren* Spalte dagegen um exakt 0 px — ein Fall, der nur den mittleren
  Schritt misst, wäre gegen genau den Fehler blind, gegen den er geschrieben wurde.

**Rot-Nachweis (Pflicht, PR-Beschreibung):** mit `gap-3` am `<ol>` ist der Fall rot.

**Was hier bewusst *nicht* gemessen wird:** die tatsächlich gemalte Kante der Füllung. Sie liegt in
einem Browser-Pseudo-Element (`::-webkit-progress-value`), das in keiner `boundingBox()` auftaucht
— dieselbe Grenze, die das Testkonzept schon bei den Trefferflächen festhält. Der Spec rechnet die
Kante deshalb aus dem gerenderten `value/max` und dem echten Balkenkasten aus und trägt damit
**eine** unbewiesene Annahme: dass Chromium ein `<progress>` mit `appearance-none` linear über
seinen Inhaltskasten füllt. Das ist eine Eigenschaft der Plattform, keine unseres Codes; sie wird
unten als benannte Lücke geführt statt stillschweigend mitgenommen.

#### (c) Sperrgrund per Tastatur erreichbar, genau fünf fokussierbare Elemente

jsdom, `Stepper.test.tsx` — echte Geometrie ist hier nicht im Spiel, also gehört es nicht nach
e2e. Zwei Nachweise, die zusammengehören:

**Die Invariante (Struktur).** Innerhalb des `<nav>` gibt es genau fünf fokussierbare Elemente,
eines je Schritt. Ermittelt über die Standard-Kandidatenmenge (`a[href]`,
`button:not([disabled])`, `[tabindex]:not([tabindex="-1"])`), eingegrenzt auf das `<nav>` — der
Skip-Link steht davor und darf nicht mitzählen. Geprüft in **drei** Zuständen, weil die Zahl heute
je nach Zustand zwischen vier und sieben schwankt und eine einzelne Messung das nicht sichtbar
macht:

1. kein Schritt gesperrt (fünf Links),
2. drei Schritte gesperrt (zwei Links, drei Knöpfe),
3. drei Schritte gesperrt **und ein Sperrgrund geöffnet** — weiterhin fünf. Das ist zugleich der
   Nachweis, dass das Panel samt Schließen-Schaltfläche per Portal *außerhalb* der Leiste landet;
   ohne diesen dritten Zustand wäre „genau fünf" eine Aussage über den Ruhezustand allein.

Zusätzlich: die Menge der fünf ist genau die Menge der fünf Schritt-Bedienelemente (Abgleich über
`data-step-state`/zugänglichen Namen), nicht irgendwelche fünf Knoten.

**Der Weg (Verhalten).** Ein Tastaturlauf ohne jeden Mauszeiger, mit `matchMedia`-Stub auf
`matches: false` (Telefonfall — dort darf Überfahren gar nichts tun, und trotzdem muss der Grund
erreichbar sein):

- `user.tab()` bis zum gesperrten Schritt; das Element hat den Fokus (`toHaveFocus`).
- `{Enter}` öffnet das Panel, der Sperrgrund steht im Text, der Fokus liegt danach **im Panel**.
- `{Escape}` schließt und gibt den Fokus **an den Auslöser zurück**.
- Dasselbe noch einmal mit der Leertaste statt der Eingabetaste — die Spec sagt beides zu, und bei
  einem `<button>` mit `aria-disabled` ist das keine Selbstverständlichkeit, sondern der Punkt.

Der Fall wird für **einen** gesperrten Schritt vollständig durchgespielt und für die beiden
anderen auf „Panel öffnet, richtiger Wortlaut" verkürzt — die drei Wortlaute sind ohnehin schon je
ein eigener, unveränderter Fall aus der heutigen Datei. Ergänzend die Abwesenheitszusage: es gibt
**keinen** eigenen Info-Auslöser mehr (keine Schaltfläche mit dem Namensmuster „Grund für Sperrung
von …") — der bisherige Positivtest darauf wird gestrichen, nicht umbenannt.

### Entscheidung zum offenen Punkt: ja, e2e sichert die waagerechte Lage der Füllkante zu

Der `architect` hat offengelassen, ob e2e zusätzlich zusichert, dass die rechte Kante der
Balkenfüllung auf der waagerechten Mitte des aktiven Schritts liegt. **Entscheidung: ja**, in der
unter (b) beschriebenen Form (gerechnete Kante aus `value/max` und echtem Balkenkasten, nicht
gemessenes Pseudo-Element).

Begründung:

1. **Ohne sie ruht die eigentliche Produktzusage auf einem Kommentar.** Der Unit-Test beweist
   „10 %", der jsdom-Test beweist „das Attribut steht dran" — die sichtbare Aussage ist aber die
   *räumliche Koinzidenz* von 10 % und Spaltenmitte. Genau dafür bezeichnet der
   Architekturabschnitt die Spaltengeometrie ausdrücklich als „tragend und kein Kosmetikdetail"
   und vermerkt vorsorglich, sonst „räume sie die nächste Überarbeitung weg". Ein Kommentar räumt
   niemanden auf; eine rote Prüfung schon. Zwei grüne Tests neben einer sichtbar falschen Anzeige
   sind der Fehlermodus, gegen den dieses Testkonzept an mehreren Stellen anschreibt.
2. **Das Aufnahmekriterium der e2e-Ebene ist erfüllt, und zwar knapp und sauber.** Gleich breite
   Spalten, fehlender Spaltenabstand und deckungsgleiche Kästen sind Layout — in jsdom
   grundsätzlich unsichtbar. Der Fall dupliziert keine bestehende Zusicherung, sondern schließt
   exakt die Lücke *zwischen* zwei bestehenden.
3. **Die Kosten sind klein und der Rot-Nachweis trivial führbar.** Ein Spec, zwei Seitenaufrufe,
   keine Zustandsänderung, keine Wartezeiten, kein neues Werkzeug; `gap-3` am `<ol>` macht ihn rot.
4. **Die naheliegende Alternative wäre schlechter.** Ein Referenzbildvergleich ist im Testkonzept
   ausdrücklich nicht aufgenommen (eigenes Sprunghaftigkeitsproblem), und ein Pixel-Abgriff der
   Füllfarbe wäre neue Maschinerie für eine Aussage, die die Rechnung genauso trägt.

**Wogegen die Entscheidung ausdrücklich nicht schützt:** gegen eine nicht-lineare Darstellung des
nativen `<progress>` durch den Browser. Das ist als Lücke benannt (siehe (b) und „Nachzuziehen im
Testkonzept") und keine stille Annahme. Eine Rückfrage an Daniel war dafür nicht nötig: das
Restrisiko ist rein gestalterisch (eine um wenige Pixel verschobene Füllkante), es geht kein
Datenverlust und keine Fehlbedienung damit einher, und die Kosten der Absicherung liegen im
Bereich eines einzelnen Specs — damit ist es eine technische Entscheidung und keine
Produktabwägung.

### Trefferflächen: die Schrittleiste kommt in `tap-targets.spec.ts`

Der Wechsel von `tap-target-square` am Marker auf `tap-target` am spaltenfüllenden Bedienelement
ist genau die Änderung, die die im Testkonzept benannten Fehlerklassen auslöst: waagerechter
Überhang und **überlappende Trefferflächen benachbarter Bedienelemente**. Die Schrittleiste ist
auf jeder Pipeline-Seite dauerhaft sichtbar und damit heißer Pfad nach derselben Begründung, mit
der Spec 0298 den Kopfzeilen-Auslöser aufgenommen hat.

Aufgenommen werden **zwei** Bedienelemente bei 360 px: der erste Schritt (Randspalte, dort ist ein
Überhang am wahrscheinlichsten) und ein **gesperrter** Schritt — letzterer ist der neue
`aria-disabled`-Knopf, und der Treffertest ist zugleich der Nachweis, dass Zeigerereignisse ihn
überhaupt erreichen (mit `disabled` täten sie es nicht, und der Sperrgrund wäre am Telefon
unerreichbar). Die Kardinalitätszusicherung des Specs wandert damit von **neun** auf **elf**; sie
ist der Grund, warum das Hinzufügen nicht still leerlaufen kann.

### Vertrag und Nutzlast

**`designSystem.contract.test.ts`** (die einzige Frontend-Ebene mit CSS-Assertions):

- `producesRule('h-header')` und `producesRule('top-header')` sind `true`, mit **Gegenprobe** auf
  einen erfundenen Namen (etwa `top-headr`), die `false` sein muss. Jede Utility bekommt einen
  eigenen `compile()`-Lauf — `build()` arbeitet inkrementell, ein gemeinsamer Lauf färbte den
  zweiten Kandidaten am ersten grün. Das ist die Absicherung gegen den stillen Fehlschlag: eine
  unbekannte Utility ist in Tailwind kein Buildfehler.
- **Einquelligkeit:** `--spacing-header` (bzw. `--header-height` im Rückfallweg) kommt in
  `index.css` genau einmal vor, und weder `App.tsx` noch `Stepper.tsx` tragen einen zweiten,
  freihändigen Pixel-/`rem`-Wert für dieselbe Höhe.
- **Abwesenheit:** `Stepper.tsx` trägt kein `top-0` mehr (Positiv-Gegenprobe: es trägt
  `top-header`), und `App.tsx` trägt kein `flex-wrap` mehr an der Kopfzeile (Gegenprobe: die Datei
  enthält weiterhin `flex`). Reine Abwesenheitsprüfungen ohne Gegenprobe bestehen auch bei einer
  versehentlich leer gelesenen Datei.
- Unverändert gültig bleibt die begründete Freigabe für `bg-bg/95` an ihrer Fundstelle — der Umbau
  fasst die Zeile nicht an. Falls doch, ist die Freigabeliste mitzuziehen.

**`frontend/penpot/payload.test.ts`:** `quellen` des Bausteins `step-marker` ist **exakt**
`['src/components/StepMarker.tsx']` (Gleichheit, nicht „enthält" — ein stehengebliebener
Alteintrag ließe den Zustandsscanner weiter die falsche Datei lesen und wäre still grün). Der
bestehende Scanner ist damit automatisch die Absicherung gegen `aria-disabled:` als Stilquelle: er
verlangte dann eine Achse `aria-disabled` in `components.json`, die der Entwurf nicht führt.
`group-hover:`/`group-active:` erkennt er bereits (`group-`-Präfix im Muster) und bildet sie auf
die geführten Ausprägungen `hover`/`active` ab — kein Nutzlast-Eingriff nötig. Kardinalitäten
bleiben unverändert.

### Edge Cases

1. **Kein aktiver Schritt** (`activeStepId` nicht in `PIPELINE_STEPS`, Index `-1`): Balkenwert 0,
   keine Orientierungszeile, kein `aria-current` — und die Leiste rendert trotzdem fünf Schritte
   mit fünf fokussierbaren Elementen.
2. **Erledigt *und* gesperrt zugleich** (real erreichbar: `gate` ist bestätigt, der
   Ausschuss-Lauf danach aber nicht mehr erfolgreich): die vier Ausprägungen sind ausschließend,
   also braucht die Abbildung `(isDone, isReachable, isCurrent) → Ausprägung` eine festgelegte
   Rangfolge. Sie wird **nicht neu erfunden**: es gilt weiter die heutige Reihenfolge (blockiert ▸
   aktuell ▸ erledigt ▸ ausstehend für die Zustandsbenennung, Haken vor Schloss für die Glyphe,
   wie heute im Code). Geprüft als **vollständige Wahrheitstabelle** über alle acht Kombinationen,
   nicht über die drei bequemen Fälle — sonst wandert die Rangfolge bei der nächsten Umgestaltung
   still.
3. **Aktiv *und* gesperrt zugleich** (per Deep-Link theoretisch, vom Routen-Wächter normalerweise
   umgeleitet; die Leiste ist rein präsentational und muss es trotzdem tragen): heutiges Verhalten
   bleibt, `blockiert` gewinnt in der Benennung. Teil derselben Wahrheitstabelle.
4. **Drei Schritte gleichzeitig gesperrt:** fünf fokussierbare Elemente, drei Popover-Auslöser,
   und das Öffnen eines Grundes öffnet die anderen nicht (unabhängige Zustände — ein geteilter
   `useState` wäre der klassische Fehler an dieser Stelle).
5. **Kein Schritt gesperrt:** kein `<button>`, kein `aria-describedby`, kein Popover — und
   trotzdem fünf fokussierbare Elemente.
6. **Leerer Sperrgrund** (`getBlockedReason` liefert für `scan`/`ausschuss` `''`, defensiver
   Fallback): kein leeres Panel und kein leeres `aria-describedby`-Ziel. In jsdom prüfbar, indem
   ein Zustand konstruiert wird, in dem `scan` als gesperrt gemeldet wird.
7. **Zeigergerät ohne Hover** (`matches: false`): Überfahren öffnet nichts, Tippen öffnet.
   Gegenprobe `matches: true`: Überfahren öffnet, und der unmittelbar folgende Klick schließt
   nicht wieder (bestehende `justOpenedByHoverRef`-Mechanik).
8. **Sehr schmale Spalte:** bei 360 px sind die Spalten ~72 px breit — die 44-px-Trefferfläche
   passt waagerecht hinein. Abgedeckt durch `tap-targets` (Treffertest, keine Kastenmessung) und
   durch `no-horizontal-scroll` auf `/pipeline/scan`.
9. **Lange Beschriftungen ab `sm:`** („Ausschuss-Erkennung", „Kategorie-Kuratierung"): umbrechend,
   nie gekürzt — in jsdom nur als Abwesenheit von `truncate` prüfbar; dass nichts überläuft, deckt
   `no-horizontal-scroll` ab. Bewusst keine eigene e2e-Zusicherung.
10. **Kopfzeile mit langem Nutzernamen** bei 360 px: `truncate`/`min-w-0` greifen statt Umbruch;
    jsdom prüft, dass der Name weiterhin gerendert wird, `no-horizontal-scroll` deckt die Folge
    ab. Das ist der bewusste Tausch „still abschneiden" gegen „laut anschlagen" aus dem
    Architekturabschnitt.

### Was bewusst nicht geprüft wird

- **Die gemalte Kante der Balkenfüllung** (Pseudo-Element, siehe oben) — gerechnet statt gemessen,
  Restannahme benannt.
- **Die vier Schrittseiten jenseits von `/pipeline/scan`** in e2e: die fixierte Anordnung ist eine
  Eigenschaft von App-Hülle und Leiste, nicht der einzelnen Seite; fünf Seitenaufrufe je Breite
  wären fünffache Laufzeit für dieselbe Aussage. Dass es dieselbe Leiste ist, ist strukturell
  belegt (ein `Stepper`, ein DOM-Baum) und in jsdom gebunden.
- **Optische Urteile**: Kontrast und Farbwahl der vier Ausprägungen liegen im Kontrastblock des
  Design-Vertrags; ob die Leiste „ruhiger wirkt", bleibt Sichtprüfung.
- **Die Penpot-Datei selbst** — geprüft wird die Nutzlast im Repository, nicht der Stand im
  fremden Dienst.

### Nachzuziehen im Testkonzept (`specs/architecture/0002-testkonzept.md`)

Vom `test-engineer` bewusst nicht vorweggenommen — der `developer` zieht es im selben PR nach,
sobald die Absicherung tatsächlich grün läuft:

1. **Entfernen:** der Eintrag „Zwei sticky `top-0`-Elemente überlagern sich auf den
   Pipeline-Routen" unter „Bekannte Lücken" (Akzeptanzkriterium dieser Spec). Er wird gestrichen,
   nicht umformuliert.
2. **Nachziehen:** die Zeile `sticky-header` in der Tabelle „Umfang: welche Specs es gibt und
   woran jeder scheitert" — der Vorbehalt „**Nicht** enthalten: … disjunkter y-Bereiche" fällt weg
   und wird durch die jetzt geltende Zusage ersetzt (disjunkt, fugenlos, Treffertest auf
   Abmelden/Navigations-Auslöser/ersten Schritt, in beiden Breiten).
3. **Neue Tabellenzeile** für `stepper-progress` mit der Angabe, was ihn bei kaputtem Layout rot
   macht (ungleiche oder abständige Spalten, verschobener Balkenkasten, zwei gleiche Messungen).
4. **Zeile `tap-targets`:** „Geprüfte Bedienelemente: **neun**" wird zu **elf**, mit der Begründung
   für die Aufnahme der beiden Schritt-Bedienelemente.
5. **Neue Frontend-Sektion** für die in dieser Spec erstmals auftretenden Muster, mit den
   projektweit gültigen Regeln, die sich daraus ergeben:
   - **Eine gerechnete Verhältniszahl, deren Aussage eine räumliche Koinzidenz ist, ist durch
     ihren Unit-Test nicht bewiesen.** Der Unit-Test sichert den Anteil; die Deckungsgleichheit
     mit dem Layout sichert nur die Ebene, die Layout sieht.
   - **Ein Zustandsträger, der über zwei Dateien verteilt ist (`group` am Elternteil, `group-*` am
     Kind), macht die `quellen`-Zuordnung der Penpot-Nutzlast zur tragenden Angabe** — sie wird mit
     Gleichheit geprüft, nicht mit „enthält".
   - **`aria-disabled` statt `disabled` ist eine Testzusage, keine Stilfrage:** geprüft wird das
     Vorhandensein des einen *und* die Abwesenheit des anderen, plus „löst keine Navigation aus".
   - **Ein per Überfahren geöffnetes Panel darf den Fokus nicht nehmen** — als Partition
     (Hover/Tastatur) geprüft, sonst ist „springt nie" von „springt immer" nicht zu unterscheiden.
   - **Ein geteiltes Höhen-Token wird am gerenderten Ergebnis gebunden, nicht am Quelltext:**
     `producesRule` mit Gegenprobe, Einquelligkeit als Abwesenheit eines zweiten Werts, und in e2e
     die **fugenlose** Naht, die in beide Richtungen anschlägt.
   - **Die Zuordnung eines Specs zu beiden Viewport-Projekten ist selbst eine Zusage** und wird in
     `toolchain.spec.ts` gebunden, sobald „in beiden Breiten geprüft" Teil eines
     Akzeptanzkriteriums ist.
6. **Bekannte Lücke, neu aufzunehmen:** dass ein natives `<progress>` seinen Inhaltskasten linear
   füllt, ist eine Annahme über die Plattform und in dieser Toolchain nicht gemessen; sichtbar
   würde eine Abweichung nur bei einer Sichtprüfung.
7. **Dokumentkopf** („Letzte Aktualisierung") wie üblich fortschreiben.

## Security

Nicht relevant. Die Spec ändert ausschließlich die Darstellung im Frontend: kein Datenmodell-
Bezug, keine neue Eingabe von außen, keine berührte Auth-, Berechtigungs- oder Secret-Stelle,
keine neue oder veränderte Schnittstelle, keine veränderte Sichtbarkeit von Daten zwischen den
beiden Nutzern. Die Herleitung, welche Schritte erreichbar sind, und die Sperrgründe bleiben
wortgleich und logikgleich; die Erreichbarkeit eines Schritts war ohnehin nie eine
Sicherheitsgrenze, sondern eine Führungshilfe — die Autorisierung liegt unverändert im Backend.

## Offene Fragen

Keine. Der einzige offene Punkt der Story — ob der Zwölf-Zeichen-Symbolsatz um ein Schloss
wächst — ist im Abschnitt „Architektur / Umsetzung", Punkt 5, entschieden: er wächst nicht.

## Entscheidungen

- **Der Zwölf-Zeichen-Symbolsatz wächst nicht** — das Schloss bleibt ein dateilokales SVG und
  zieht mit der Marke nach `StepMarker.tsx` um. Damit ist der einzige offene Punkt der Story
  entschieden (Begründung: „Architektur / Umsetzung", Punkt 5).
- **Versetzter Haftpunkt über ein geteiltes Höhen-Token** (`--spacing-header`) statt
  Laufzeitmessung oder Verschmelzung der beiden Leisten; die Kopfzeilenhöhe ist durch eine
  bereits gebundene Zusage („bricht bei keiner Breite um") eine Systemkonstante.
- **Schmal fixiert bleiben Kopfzeile + Markenreihe + Fortschrittsbalken**; die Orientierungszeile
  verlässt das `<nav>` und scrollt mit. Damit ist die haftende Leiste in beiden Breiten dieselbe
  (ein DOM-Baum). Das erfüllt die Vorgabe der Story, diese Festlegung bei der Umsetzung zu
  treffen und zu dokumentieren.
- **Der gesperrte Schritt ist selbst der Popover-Auslöser** — `<button aria-disabled>`, nie
  `disabled`; Radix-Popover statt Tooltip (ein Tooltip öffnet nicht per Tippen).
- **Fortschrittsbalken über das vorhandene `<progress>`-Primitiv**, Wert aus der reinen Funktion
  `stepProgress`; die gleich breiten, abstandsfreien Spalten sind dafür tragende Geometrie.
- **`StepMarker.tsx` wird als eigener Baustein ausgelagert**, weil der Penpot-Entwurf den
  Baustein als die Marke allein definiert.
- **e2e sichert die Lage der Balkenfüllung zu** (gerechnete Kante gegen die Spaltenmitte,
  Toleranz ≤ 1 px) — ohne sie ruhte die eigentliche Produktzusage nur auf einem Kommentar
  (`test-engineer`). Benannte Restannahme: Chromium füllt ein `<progress appearance-none>` linear
  über seinen Inhaltskasten; das wird als Lücke im Testkonzept geführt.
- **Akzeptanzkriterien auf Testbarkeit geschärft** (`test-engineer`): komparative Formulierungen
  („darf sich nicht verschlechtern", „größere Trefffläche als heute") und nicht falsifizierbare
  Zusagen („zu jedem Zeitpunkt bedienbar", „wird bei der Umsetzung festgelegt") sind durch
  prüfbare ersetzt. Die fachliche Aussage bleibt dieselbe; der Issue-Body wurde nicht angefasst.
- **Keine ADR angelegt** — geprüft, nicht übergangen (Begründung im Abschnitt „Keine ADR").
- **`security-engineer` nicht konsultiert (Schritt 3):** Die Story hat keinen konkret benennbaren
  Bezug zu Auth, externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, dem
  Datenmodell oder der Sichtbarkeit von Daten zwischen den beiden Nutzern — sie ändert
  ausschließlich die Darstellung bereits angezeigter Information im Frontend.
- `architect` konsultiert (Schritt 1), `ux-ui-designer` konsultiert (Schritt 2),
  `test-engineer` konsultiert (Schritt 3).

## Out of Scope

- Der Symbolsatz wächst nicht; ein dreizehntes Zeichen wäre eine eigene Story.
- Die Schrittleiste bleibt so breit wie der Inhaltsbereich (`max-w-5xl` des `<main>`) statt
  randlos wie die Kopfzeile.
- Das geräteunabhängige Öffnungsverhalten wird **nicht** in einen geteilten Hook ausgelagert —
  es bliebe auch nach dieser Spec bei zwei Aufrufstellen; die etablierte Praxis lagert ab dem
  dritten aus.
- Der Skip-Link bleibt unverändert.
- Die Herleitung, welche Schritte erreichbar/erledigt/gesperrt sind, und die Sperrgründe selbst
  bleiben unverändert.
