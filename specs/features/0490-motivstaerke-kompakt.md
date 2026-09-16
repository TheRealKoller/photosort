# 0490 - Motivstärke kompakt auf einen Blick

**Status:** Accepted
**Erstellt:** 2026-09-16
**Bezug:** [Issue #490](https://github.com/TheRealKoller/photosort/issues/490)

**Zum Umfang:** Diese Spec überschreitet den Richtwert von rund 200 Zeilen, weil dreizehn
geschärfte Akzeptanzkriterien, der vollständige Umbauplan einer bestehenden Komponente und die
Liste der dabei leer werdenden Zusagen zusammen in einem Dokument stehen müssen — getrennt
gelesen führt jede Hälfte in die Irre.

## Ziel

Die Motivstärke eines Fotos steht heute als Liste aus acht Balken mit Prozentzahlen und braucht
dafür rund 290 Bildpunkte Höhe. Wer ein Foto beurteilt, sieht dadurch weniger vom Foto und muss auf
dem Telefon scrollen, um alle Motive zu sehen. Die Stärke aller acht Motive soll auf einen Blick
erfassbar sein und dabei einen Bruchteil des Platzes belegen — ohne dass der genaue Wert verloren
geht und ohne dass die Möglichkeit entfällt, ein falsch erkanntes Motiv zu korrigieren.

## User Story

Als Person, die ihre Reisefotos durchsieht, möchte ich die Stärke aller acht Motive eines Fotos auf
einen Blick erfassen, ohne dass die Anzeige den Platz des Fotos einnimmt, damit ich schneller
beurteilen kann, worum es auf dem Bild geht.

## Akzeptanzkriterien

- [ ] **AK1 — Reihe statt Liste.** Die Motivstärke erscheint als Reihe von acht Symbolen — eines je
      Motiv, nebeneinander in einer Zeile — an Stelle der bisherigen Balkenliste. Die Reihe trägt
      genau acht Einträge in Registry-Reihenfolge (nie nach Stärke sortiert), auch bei
      unvollständigem Stärkevektor; in der Motivsektion steht danach kein Balken mehr.
- [ ] **AK2 — Füllung von unten, Umriss bleibt.** Jedes Symbol füllt sich von unten nach oben
      entsprechend der Stärke seines Motivs. Der ungefüllte Teil bleibt als Umriss sichtbar, sodass
      die Symbolform immer vollständig erkennbar ist und ein schwach vertretenes Motiv nicht
      abgeschnitten wirkt: Die vollständige Umrissebene ist bei jeder Stärke vorhanden,
      einschließlich Stärke 0 und Stärke 1.
- [ ] **AK3 — Vier Farbstufen aus dem bestehenden Vorrat.** Die Füllung ist farblich abgestuft:
      stark vertreten grün, mittel gelb, schwach rot, nicht vertreten gedämpft. Die Stufe entsteht
      aus der wirksamen Stärke gegen die beiden Grenzen aus `GET /motifs` — beide Grenzen
      einschließend (`>=`) —, nie aus `present`. Die verwendeten Farben stammen ausschließlich aus
      dem bestehenden Farbvorrat des Projekts; es entstehen keine frei gewählten Zwischentöne und
      kein neues Farbtoken.
- [ ] **AK4 — Farbe ist nicht der einzige Träger.** Die Füllhöhe zeigt dieselbe Information, sodass
      die Anzeige auch ohne Farbunterscheidung lesbar bleibt. Füllhöhe und angezeigter Wert stammen
      aus demselben gerundeten Prozentwert und können nicht auseinanderlaufen; zusätzlich nennt der
      zugängliche Name jedes Symbols den Wert als Text.
- [ ] **AK5 — Ein Symbol je Motiv.** Für jedes der acht Motive gibt es ein Symbol: Menschen
      `user-round`, Landschaft `mountain-snow`, Bauwerk & Sehenswürdigkeit `landmark`, Stadt &
      Straße `building-2`, Tiere `paw-print`, Essen & Trinken `utensils`, Aktivität `footprints`,
      Detail & Stimmung `sparkles`. Ein Schlüssel ohne Eintrag zerreißt die Reihe nicht, sondern
      bekommt ein neutrales Ersatzsymbol.
- [ ] **AK6 — Aufklappende Detailzeile.** Ein Klick oder Tippen auf ein Symbol öffnet unterhalb der
      Reihe eine Zeile mit dem vollen Motivnamen und dem genauen Wert. Ein zweiter Klick auf
      dasselbe Symbol schließt sie, ein Klick auf ein anderes Symbol wechselt sie; das geöffnete
      Symbol ist als solches ausgezeichnet und verweist auf die Zeile.
- [ ] **AK7 — Lokal nicht beurteilbar.** Ist ein Motiv lokal nicht beurteilbar, steht das an der
      Stelle des Werts in dieser aufgeklappten Zeile. In der Symbolreihe selbst muss dieser Fall
      nicht von „gar nicht vertreten" unterschieden werden — er trägt dort dieselbe leere Füllung.
- [ ] **AK8 — Korrektur bleibt erreichbar.** Dort, wo Motive heute korrigiert werden können, bleiben
      „Trifft zu", „Trifft nicht zu" und „Zurücknehmen" erreichbar — in derselben aufgeklappten
      Zeile, mit dem Motivnamen im zugänglichen Namen. „Zurücknehmen" erscheint nur, solange eine
      Korrektur besteht; eine laufende Korrektur sperrt nur die Schaltflächen dieser Zeile.
- [ ] **AK9 — Nur-Lese-Stelle.** Dort, wo die Motivliste heute nur zum Ansehen dient, erscheinen
      keine Korrekturschaltflächen — auch nicht nach dem Aufklappen einer Zeile. Name und genauer
      Wert bleiben abrufbar.
- [ ] **AK10 — Zeigen ergänzt, ersetzt nicht.** Zeigen mit der Maus blendet Name und Wert eines
      Symbols ein, ohne dass ein Klick nötig ist; ein angeheftetes Symbol wird durch Zeigen auf ein
      anderes nicht verdrängt. Auf Geräten ohne Maus ist der Klick der vollständige Weg zu allen
      Angaben — keine Angabe und keine Aktion ist allein über Zeigen erreichbar: Die Zeile nach
      einem Klick trägt dieselben Angaben und dieselben Schaltflächen wie die Zeile beim Zeigen.
- [ ] **AK11 — An allen Stellen.** Die neue Darstellung ersetzt die Balkenliste an allen Stellen, an
      denen Motivstärken heute erscheinen (Einzelbildansicht und Info-Popover der Kachel); eine
      Balkenliste für Motivstärken bleibt nirgends stehen.
- [ ] **AK12 — Telefonbreite.** Auf Telefonbreite (360 px) bleiben alle acht Symbole in einer Zeile
      lesbar, ohne waagerechtes Scrollen: Alle acht liegen auf derselben Zeile, keines ist auf
      Breite 0 gedrückt, und die Seite scrollt nicht waagerecht.
- [ ] **AK13 — Die vier Fotozustände.** Die bisher unterschiedenen Zustände eines Fotos bleiben
      unterscheidbar: noch nicht klassifiziert (Satz statt Reihe, keine acht Nulleinträge),
      klassifiziert, nur lokal beurteilt (Grundlagenzeile plus AK7), als Dokument oder
      Bildschirmabbildung ausgeschlossen (Ausschlusstext, Reihe einsehbar und schreibgeschützt).

## Datenmodell-Bezug

Keine Änderung. Die Stufen entstehen aus Feldern, die die Antwort bereits trägt: `PhotoOut.motifs[]`
(`key`, `strength`, `correction`, `present`), `PhotoOut.motif_assessment` und `strength_bands` aus
`GET /motifs`.

## Architektur / Umsetzung

Gewählter Ansatz: Die Balkenliste weicht einer Reihe aus acht Füllstandssymbolen mit einer
aufklappenden Zeile darunter. Reiner Frontend-Umbau — **kein Backend-Anteil**, keine Änderung an
`GET /motifs`, `GET /photos` oder am Korrekturweg. Die Grundlagen stehen in ADR
[`0113`](../decisions/0113-motivstaerke-als-fuellstandssymbol.md); sie ist vor der Umsetzung zu
lesen und entscheidet die vier Punkte, die die Akzeptanzkriterien offenlassen.

### Die vier Farbstufen

Aus der wirksamen Stärke gegen `strength_bands` aus `GET /motifs` — `present` wird dafür **nie**
gelesen (ADR 0113 Punkt 1):

| wirksame Stärke | Füllung | Utility |
|---|---|---|
| `>= strength_bands.strong` | grün | `text-status-success` |
| `>= strength_bands.medium` | gelb | `text-status-running` |
| `> 0` | rot | `text-status-failed` |
| `=== 0` oder lokal nicht beurteilbar | keine | — |

Der ungefüllte Teil und der Fall „keine Füllung" tragen `text-text-muted`, **nicht**
`text-text-disabled` (das ist ohne Disabled-Variante vertraglich verboten). Kein neues Farbtoken;
die drei Tokens liegen in der Kontrastmatrix bereits mit der grafischen Schwelle (3:1) auf allen
vier Flächen.

### Neue Dateien

- **`frontend/src/utils/motifIcons.ts`** — `motifIconName(motifKey): IconName`. Die acht
  Zuordnungen als `Map`, nicht als Objekt-Lookup (ein Schlüssel wie `"toString"` trifft sonst
  `Object.prototype`, dieselbe Begründung wie in `utils/motifLabels.ts`). Unbekannter Schlüssel →
  `tag`.
- **`frontend/src/utils/motifStrength.ts`** — `motifFillStep(strength, bands, assessable):
  'strong' | 'medium' | 'weak' | 'none'`. Reine Funktion mit den Bändern als **explizitem**
  Parameter, beide Grenzen inklusiv (`>=`) wie im Backend.
- **`frontend/src/components/MotifStrengthSymbol.tsx`** — zeichnet dasselbe `<Icon>` zweimal
  übereinander: unten vollständig in `text-text-muted`, darüber deckungsgleich in der Bandfarbe,
  beschnitten auf die unteren `Math.round(strength * 100)` Prozent. Beide `aria-hidden`; die
  Aussage trägt der zugängliche Name der Schaltfläche. Der Füllstand nutzt **denselben gerundeten
  Prozentwert wie der angezeigte Text** — Höhe und Zahl können nicht auseinanderlaufen.
- **`frontend/src/index.css`, `@layer utilities`** — das Beschnitt-Rezept an genau einer Stelle
  (`clip-path: inset(calc(100% - var(--motif-fill)) 0 0 0)`), die Aufrufstelle übergibt nur
  `--motif-fill` als Prozentwert über `style`. Kein willkürlicher Tailwind-Wert — eine
  `[--motif-fill:…]`- oder `clip-path-[…]`-Utility im TSX löst die Vertragsregel „keine
  willkürlichen Werte" aus.

### Geänderte Dateien

- **`frontend/src/components/MotifStrengthList.tsx` → `MotifStrengthSection.tsx`** (Umbenennung:
  „Liste" beschreibt die Oberfläche nicht mehr). **Die Props bleiben unverändert** — beide
  Aufrufstellen ändern nur Import und Elementnamen. Erhalten bleiben unverändert: die vier
  Fotozustände (Satz statt Reihe ohne Kopfzeile, Ausschlusstext, Grundlagenzeile, Skeleton), das
  Glossar, der Fehler-`Alert`, `rowsEditable = editable && !excluded`, der Nachschlag je Schlüssel
  über eine `Map` statt über den Index der Antwortliste.

  Neuer Aufbau: `<ul aria-label="Motive" class="flex">` mit acht `<li class="flex-1">`, darin je
  eine `<button>` in Registry-Reihenfolge, darunter **außerhalb** der Liste die Detailzeile. Der
  zugängliche Name `Motive` der Liste bleibt erhalten — zwei Abwesenheitszusagen anderer Ansichten
  hängen daran.
  - Jede Schaltfläche: `tap-target` (nur die kurze Achse), **kein** `tap-target-square`, **kein**
    `h-11`. Zugänglicher Name = `{Motivname}: {Wert}`, wobei der Wert das Korrekturwort, „lokal
    nicht beurteilbar" oder der Prozentwert ist — alle Angaben stehen damit auch ohne Aufklappen
    zur Verfügung. `aria-expanded` (folgt **nur** dem Anheften, nicht dem Zeigen), `aria-controls`
    auf die Detailzeile, `data-motif-key`, `data-motif-corrected` wie bisher.
  - Zustand: `pinnedKey` (Klick, umschaltend) und `hoveredKey` (Zeigen). Angezeigt wird
    `pinnedKey ?? hoveredKey` — **sobald etwas angeheftet ist, überschreibt Zeigen nichts mehr**,
    sonst wechselte die Zeile unter dem Zeiger auf dem Weg zu den Korrekturschaltern. Der
    angeheftete Schlüssel überlebt den Fotowechsel der Detailansicht; die Zeile zeigt dann die
    Werte des neuen Fotos.
  - Detailzeile: voller Motivname, genauer Wert in `font-mono` (`formatCriterionPercent`), bei
    `source === 'local' && !locally_assessable` an Stelle des Werts „lokal nicht beurteilbar", bei
    bestehender Korrektur an Stelle des Werts „Trifft zu (korrigiert)" / „Trifft nicht zu
    (korrigiert)". Nur bei `rowsEditable` darin „Trifft zu" / „Trifft nicht zu" / „Zurücknehmen"
    unverändert wie heute (`size="sm"`, `gap-3`, `aria-pressed`, `aria-label` mit Motivnamen,
    `busy` je Motiv). **Ist nichts gewählt, steht dort der Satz „Symbol antippen für Details"**
    statt einer leeren Fläche — die Zeile behält ihre Höhe, und die Reihe springt beim ersten Klick
    nicht. Die Id der Zeile existiert auch in diesem Zustand (`aria-controls` zeigt nie ins Leere).
  - **Kein Popover** und kein `title`-Attribut: Die Reihe steht im Kachel-Popover bereits in
    einem Panel, und ein zweites darin ist nicht zulässig.
- **`frontend/src/components/ui/icon.tsx`** — acht benannte Importe und acht `ICONS`-Einträge
  (`user-round`, `mountain-snow`, `landmark`, `building-2`, `paw-print`, `utensils`, `footprints`,
  `sparkles`). Der Doku-Block nennt den Satz ab jetzt als zwanzig statt zwölf.
- **`frontend/penpot/icons.test.ts`** (Zusage über die Symbolzahl), **`design/penpot/verify.js`**
  (`ERWARTETE_SYMBOLE`, Zeile 55) und **`frontend/penpot/payload.test.ts`** (Freigabeeintrag mit
  Datei, **Zeile** und Wert). `design/penpot/icons.json` wird **erzeugt** (`toMatchFileSnapshot`)
  und nie von Hand geschrieben.
- **`frontend/src/pages/PhotoDetailPage.tsx`**, **`frontend/src/components/CriterionDetailsPopover.tsx`**
  — Import und Elementname.
- **`e2e/tests/tap-targets.spec.ts`** — die Korrekturschaltfläche ist erst nach einem Klick auf
  ein Symbol da; die Suche wird auf `data-testid="motifs-section"` umgestellt. Die Symbolreihe
  selbst kommt **nicht** in den Prüfsatz (ADR 0113 Punkt 5), `EXPECTED_CONTROL_COUNT` bleibt 21.
- **`docs/architecture.md`**, **`specs/architecture/0004-design-system.md`**,
  **`.claude/skills/design-system/SKILL.md`** und **`.claude/skills/penpot-design/SKILL.md`**
  (Zeile 137, „zwölf Symbole") — im selben Pull Request.

### Entfällt

Die `Progress`-Verwendung in diesem Baustein und die lokale Komponente `MotifRow`.
`components/ui/progress.tsx` selbst bleibt (fünf weitere Aufrufstellen), `tone="neutral"`
ebenso (`CriterionDetailsPopover`).

### Reihenfolge

1. Symbole: `icon.tsx` und die drei Wächterstellen, Schnappschuss erzeugen lassen.
2. `utils/motifStrength.ts` und `utils/motifIcons.ts` mit ihren Tests.
3. `index.css`-Utility und `MotifStrengthSymbol.tsx` mit Test.
4. `MotifStrengthSection.tsx`: Umbenennung mit Testumzug, dann der Umbau.
5. Beide Aufrufstellen und deren Tests.
6. `e2e/tests/tap-targets.spec.ts`.
7. Doku.

## UI/UX

**Stand:** Arbeitsstand
**Penpot-Seite:** Entwurf — motivstaerke-kompakt
**Schlüssel:** motivstaerke-kompakt

In Penpot liegen der Variantencontainer `motiv-bereich` (Achse `zustand` mit `regelfall`,
`gewaehlt`, `schreibgeschuetzt`, `nicht-klassifiziert`) und `motiv-reihe` als Einzelteil. Die
Bilddetailansicht selbst ist dort bewusst nicht entworfen (Folge-Issue #497).

**Layout.** Acht Symbole nebeneinander in Registry-Reihenfolge, jedes ein Achtel der Reihenbreite:
bei 360 px Gerätebreite rund 41 px, im Kachel-Popover rund 32 px. Vertikal über `tap-target` auf
44 px aufgespannt. Darunter die Detailzeile mit gleichbleibender Höhe.

**Zustände.** Ladend: der bestehende Skeleton. Fehler einer Korrektur: der bestehende `Alert`, der
den Motivnamen nennt, auch wenn dieses Motiv gerade nicht aufgeklappt ist. Die vier Fotozustände
wie in AK13 — bei fehlender Erhebung erscheint weiterhin **ein Satz an Stelle der Reihe**, nie acht
ungefüllte Symbole: Acht Umrisse sind von „erhoben, aber nichts erkannt" nicht zu unterscheiden.

**Barrierefreiheit.** Beide Symbolebenen sind `aria-hidden`; die Aussage trägt der zugängliche Name
der Schaltfläche (`{Motivname}: {Wert}`). Damit ist jede Angabe ohne Zeigen und ohne Aufklappen
erreichbar. Die waagerechte 44-px-Trefferfläche wird bewusst unterschritten — acht à 44 px brauchen
352 px zuzüglich Zwischenräumen und vertragen sich nicht mit AK12; WCAG 2.5.8 (AA, 24 × 24 px)
bleibt auf beiden Achsen deutlich überschritten.

**Design-System.** Drei Muster beschreiben nach dieser Änderung eine Oberfläche, die es nicht mehr
gibt, und werden im selben Pull Request neu gefasst — in `specs/architecture/0004-design-system.md`
(Zeilen ~361/371/373) und in ihren Kurzfassungen in `.claude/skills/design-system/SKILL.md`
(~184/186/187): „Mehrwertige Eigenschaft als Stärkeliste", „‚Noch nicht erhoben' ist keine Null",
„Nicht korrigierbare Einstufung benennt ihren einzigen Weg zurück". Ebenfalls nachzuziehen: der
Symbolsatz „die zwölf Board-Symbole" (Zeilen ~168/170/174).

**Die Zusage „kein Akzent als Füllung" wird für die Motivstärke aufgehoben.** Sie ist nicht
dadurch gewahrt, dass die Füllung Status- statt Akzenttokens nennt: `--accent-2` (album-würdig) und
`--status-success` tragen denselben Wert `#00E676`, `--danger` (aussortiert) und `--status-failed`
denselben Wert `#FF3D00`. Die Füllung ist damit optisch der Akzent. Getragen wird die Aufhebung von
der Füllhöhe als zweitem, farbunabhängigem Träger (AK4); die Neufassung der drei Muster spricht das
aus, statt die alte Zusage weiterzuführen.

## Security

**nicht relevant.** Reiner Frontend-Umbau der Darstellung: kein Backend-Anteil, keine neue Eingabe
von außen, keine berührte Auth-, Berechtigungs- oder Secret-Stelle, keine Änderung am Datenmodell
und keine veränderte Sichtbarkeit von Daten zwischen den beiden Nutzern. Der Korrekturweg bleibt
unverändert derselbe bestehende Endpunkt.

## Teststrategie

Kein Backend-Anteil, also keine `pytest`-Zeile und kein Einfluss auf `--cov-fail-under=80`.

- **Unit:** `motifFillStep` (vier Stufen gegen Bänder, die als Parameter hereinkommen) und
  `motifIconName` (acht Zuordnungen, `tag`-Rückfall, Prototyp-Durchgriff), tabellengetrieben.
- **Komponente:** `MotifStrengthSymbol` (beide Ebenen vorhanden und `aria-hidden`, Bandfarbe am
  oberen Symbol, `--motif-fill` mit demselben gerundeten Prozentwert wie der Text) und
  `MotifStrengthSection` (Reihenstruktur, zugänglicher Name je Schaltfläche, Vorrang
  `pinnedKey`/`hoveredKey`, Detailzeile, Korrekturweg, die vier Fotozustände, Lade-/Fehlerzustand,
  Glossar).
- **Integration:** `PhotoDetailPage` (Korrektur und Rücknahme gehen **nach dem Aufklappen** an den
  Endpunkt; ausgeschlossenes Foto bietet auch nach dem Aufklappen keinen Schalter) und
  `CriterionDetailsPopover` (auch nach dem Aufklappen kein Korrekturschalter, Name und Wert aber
  abrufbar).
- **E2E:** `tap-targets` umgestellt. AK12 bekommt einen schmalen Nachweis als **Erweiterung eines
  bestehenden Specs** (bei 360 px: acht Symbole, gleiche Oberkante, jedes ≥ 24 px) statt eines
  neunten Specs — sonst bliebe die Zahl, auf die sich ADR 0113 Punkt 5 stützt, nirgends geprüft.

**Zwei Methodenregeln.** Ein Wert, der als Text und als Geometrie erscheint, wird an **einer**
Stelle gerundet; der Fall, der das absichert, ist die Stärke größer null, die auf 0 % rundet.
Bandgrenzen stehen im Test als `bands.strong` bzw. als Bruch, nie als Dezimalliteral — sonst prüft
der Test die Kalibrierung statt die Stufung.

**Bewusst nicht getestet:** der tatsächlich sichtbare Füllstand (`clip-path` ist CSS, jsdom hat
keine Layout-Engine — zugesichert wird der übergebene Wert, nie ein gemessener Anteil), die
Wahrnehmbarkeit der Bandfarben (liegt bereits in der Kontrastmatrix) und die Tastaturbedienung des
nativen `<button>`.

**Bestehende Zusagen, die durch den Umbau leer wahr werden** — sie bleiben grün und müssen trotzdem
angefasst werden, sonst schwächen sie sich still ab:

- `renders no button at all when the list is read-only` wird **rot**, weil die acht Symbole selbst
  Schaltflächen sind; zu schärfen auf „keine **Korrektur**schaltfläche".
- Jede Abwesenheitszusage über einen Korrekturschalter (`CriterionDetailsPopover.test.tsx`,
  `PhotoDetailPage.test.tsx`) braucht den Klick auf ein Symbol **vor** der negativen Assertion.
- `shows no band word anywhere outside the statistics table` prüft nur `document.body.textContent`;
  die Werte wandern in `aria-label` und werden dort nicht erfasst. Muss die zugänglichen Namen
  einbeziehen.
- Der S19-Test (Registry-Text als reine Textknoten) muss Detailzeile und zugänglichen Namen mit
  abdecken.

`specs/architecture/0002-testkonzept.md` wird ergänzt: die Geometrie, die jsdom nicht sieht; der
Wert, der an zwei Stellen erscheint; die Zeigen/Anheften-Doppelquelle ohne Radix; die
Abwesenheitszusage, die eine Interaktion leer macht; das Bedienelement, das bewusst nicht in den
Trefferflächen-Prüfsatz gehört. Im selben Zug wird der Tabelleneintrag zu `tap-targets` korrigiert
— er nennt „dreizehn (`EXPECTED_CONTROL_COUNT`)", im Code stehen 21.

## Entscheidungen

- Farbstufe aus `strength_bands`, nie aus `present`: Die Präsenzgrenze 0.5 liegt mitten im
  mittleren Band (1/3); aus beiden Skalen zugleich wäre die Stufe „schwach" unerreichbar (ADR 0113).
- Füllstand über zwei übereinanderliegende Symbole mit `clip-path` statt Verlauf oder Maske im SVG —
  letztere brauchen je Symbol eine eindeutige Id in `ui/icon.tsx`, deren Ausgabe zugleich der
  Penpot-Schnappschuss ist.
- Kein neues Farbtoken; die Token-Kardinalität ist eingefroren und zöge drei weitere Pflegestellen
  nach.
- Zuordnung Motiv → Symbol im Frontend, nicht als Feld an `MotifOut`: Ein Symbolname ist eine
  Eigenschaft des ausgelieferten Symbolsatzes, den das Backend nicht kennt.
- AK12 bekommt einen Nachweis als Erweiterung eines bestehenden E2E-Specs statt eines eigenen.
- Beim Fotowechsel bleibt ein angeheftetes Symbol angeheftet — die Komponente kann den Wechsel
  mangels Fotoidentität in den Props nicht erkennen, und die Props bleiben unverändert. Abgesichert
  wird, dass die Zeile nach dem Prop-Wechsel den neuen Wert zeigt, nie einen stehengebliebenen alten.
- `security-engineer` nicht konsultiert (Schritt 3): kein konkret benennbarer Bezug zu Auth,
  externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, Datenmodell oder
  Datensichtbarkeit zwischen den beiden Nutzern — reiner Frontend-Umbau der Darstellung auf
  bestehenden Feldern.

## Offene Fragen

Keine.

## Out of Scope

- Der Entwurf der Bilddetailansicht selbst (Folge-Issue #497).
- Jede Änderung an Modell, Schwellen oder Kalibrierung der Motiverkennung.
- Die Motivdarstellung auf der Fotokachel und in der Statistiktabelle — beide zeigen keine
  Stärkevektoren und bleiben unverändert.
