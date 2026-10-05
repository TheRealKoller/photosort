# 0134 - Die Kuratierungskachel folgt dem Seitenverhältnis, und ihre Knöpfe schrumpfen aufs Symbol

**Status:** Accepted
**Datum:** 2026-10-05
**Bezug:** [GitHub-Issue #579](https://github.com/TheRealKoller/photosort/issues/579), Spec 0579
**Löst ab:** ADR 0110 Punkt 5, soweit er die Fotokarte betrifft (feste quadratische Bildfläche,
Kennzeichen im Kartenkörper). Für die Rasterkachel gilt Punkt 5 unverändert.

## Kontext

Die Fotokacheln der Kuratierung (Album-Entwurf, Endauswahl, Alternativen in Band, Reihe und
Hinzufügen-Panel) sollen das Foto vollständig und ohne Leerraum zeigen, in Reihen gleicher Höhe
von etwa 280 px am Rechner. Unter jedem Foto stehen bis zu zwei Handgriffe nebeneinander, als
Symbol mit Kurzwort. Ein Hochformat in einer solchen Reihe ist oft schmaler als zwei beschriftete
Knöpfe. Daniel hat entschieden: Die Zeilenhöhe bleibt, das Foto bleibt randlos, und die Knöpfe
geben nach.

## Entscheidung

### 1. Das justierte Raster gilt auch für die Kuratierung

Jedes Kuratierungsraster setzt seine Kacheln mit `utils/justifiedRows.ts` aus
`PhotoOut.aspect_ratio`. Es gibt keine Spaltenklasse und keine quadratische Bildfläche mehr.
Kachelbreite und Bildhöhe gehen als gerechnete Zahl in `style`, nie als Zeichenkette oder
Custom-Property.

Konstanten der Kuratierung: Zielhöhe 280 px, Untergrenze 200 px, Obergrenze 350 px, Abstand
`GRID_GAP_PX`. Die Obergrenze ist ein neuer, optionaler Parameter `maxRowHeight` von
`justifiedRows`. Eine Reihe, deren bündige Höhe darüber läge, wird wie die letzte Reihe gesetzt:
Zielhöhe, natürliche Breiten, linksbündig. Ohne ihn stünde am Telefon ein einzelnes Hochformat
auf voller Breite und etwa 490 px hoch. Ohne den Parameter rechnet die Funktion wie bisher.

Band und Hinzufügen-Panel folgen auf die **gerechnete** Reihe der auslösenden Kachel. Die
Spaltenzahl wird nicht mehr aus dem gerenderten Raster gelesen. Das Feld „Foto hinzufügen“ ist
eine Zelle der Reihe mit festem Planungsverhältnis 2:3.

### 2. Randlos für jedes Foto ab 1:2

Ein Foto wird mit seinem eigenen Verhältnis geplant, höchstens aber mit der Untergrenze
`ICON_HANDLES_WIDTH_PX / MIN_ROW_HEIGHT` = 100 / 200 = 0,5. Ein noch schmaleres Foto wird in
einem Feld dieser Breite eingepasst (`object-contain`) und bekommt seitliche Kachelfläche. Das
ist dieselbe Ausfallrichtung wie bei unbekanntem Verhältnis (ADR 0110 Punkt 4). Würde ein
schmaleres Foto ohne diese Untergrenze gesetzt, ragten selbst die Symbolknöpfe in die
Nachbarkachel. `ICON_HANDLES_WIDTH_PX` sind zwei sichtbar 44 px breite Symbolknöpfe mit 12 px
Abstand.

### 3. Beschriftet oder nur Symbol: eine reine Funktion der Kachelbreite

Jede Kachelart nennt die Breite, die ihre Knopfzeile **mit** Kurzwörtern braucht
(`HANDLES_FULL_WIDTH_PX`). Ist die gerechnete Kachelbreite kleiner, zeigen **alle** Knöpfe dieser
Kachel nur ihr Symbol. Gemischte Zeilen gibt es nicht. Entschieden wird aus der Zahl des
Layouts, nicht durch Messen im DOM: Messen und Umschalten änderte die Breite, auf die gemessen
wurde, und die Zeile könnte zwischen beiden Formen pendeln.

- Der zugängliche Name bleibt in beiden Formen `{Handlung}: {Pfad}`. Das Wort ist immer
  vorlesbar.
- Ein reiner Symbolknopf ist sichtbar 32 px groß, auf dem heißen Pfad am Telefon 44 px, und
  bekommt `tap-target-square`.
- Bei Überfahren mit einem Zeigegerät und bei Tastaturfokus erscheint über dem Knopf sein
  Kurzwort (`aria-hidden`, undurchsichtig `--overlay`, nicht bedienbar). Am ersten Knopf der
  Zeile ist es linksbündig, am zweiten rechtsbündig ausgerichtet und darf in der Kachelbreite
  umbrechen. So verlässt es die Kachel nie. Am Telefon gibt es diese Beschriftung nicht; dort
  tragen Symbol und vorgelesener Name.
- Während einer laufenden Anfrage ersetzt der Spinner das Symbol, statt neben ihm zu stehen.
  Sonst wüchse ein beschrifteter Knopf über die angesetzte Breite hinaus.

Eine Kachelbreite unter der angesetzten Breite mit beschrifteten Knöpfen ist ein Überlauf in
die Nachbarkachel. Die Werte stehen deshalb neben der jeweiligen Kachel, und ein E2E-Fall hält
sie an der tatsächlich gerenderten Schrift fest.

### 4. Das Zustandskennzeichen sitzt in der Bildecke, als Symbol

Vorschlag, Aufgenommen und Gestrichen erscheinen als Symbolkennzeichen oben links über der
Bildfläche, auf der undurchsichtigen Fläche des Badges. Ohne Farbe unterscheidbar sind sie an
der Symbolfolge: `cog`+`book`, `book`, `x-circle`. Das volle Wort aus `utils/albumStateLabels.ts`
ist der zugängliche Name; die Datei bleibt die eine Begriffsquelle. Die Ecke oben rechts ist
nicht mehr reserviert: Der Info-Auslöser entfällt auf allen Kuratierungskacheln.

### 5. Der Symbolsatz wächst um `repeat` und `plus`

`repeat` steht für „Alternativen“ und „Tauschen“. Auch `plus` wird nötig, weil „Hinzufügen“ in
schmalen Kacheln ein Symbol braucht. Damit entfällt die Lücke `+` als Textzeichen: Das Feld
„Foto hinzufügen“ nutzt ebenfalls `plus`. Ein Symbolname kommt nur über `ui/icon.tsx` und die
drei Penpot-Prüfstellen hinzu.

## Konsequenzen

- `PhotoCard` bleibt der eine Baustein der Kuratierung und deckt jetzt auch die Kandidaten in
  Band, Reihe und Panel ab. Sie verliert Statuszeile, quadratische Bildfläche und den Slot oben
  rechts. Der Dateiname steht nur noch in der Bei-Bedarf-Leiste und im `alt`.
- `CriterionDetailsPopover` und `MotifAssessmentMarker` haben keine Aufrufstelle mehr und
  entfallen.
- Am Telefon (360 px) stehen meist zwei Hochformate je Reihe, mit Symbolknöpfen. Ein Querformat
  steht allein und mit Kurzwörtern.
- Fotos schmaler als 1:2 zeigen seitliche Kachelfläche. Das ist bewusst: Beschnitt ist
  ausgeschlossen, und ein Überlauf der Knöpfe ebenfalls.
