# 0119 - Der Motivwechsel vermerkt eine Grenze, statt eine zu eröffnen; die Unantastbarkeit entfällt

**Status:** Accepted
**Datum:** 2026-09-20
**Bezug:** Spec [`0506`](../features/0506-cluster-als-anlass.md), ADR
[`0109`](./0109-motivwechsel-trennt-in-einem-vorgelagerten-durchlauf.md) (Punkt 1, die Trennwirkung
des erzwungenen Starts — wird hier abgelöst), ADR
[`0117`](./0117-der-anlass-als-einheit-eigene-schwellen-dauergrenze-und-mindestgroesse.md)
(Punkt 3, die verbliebene unantastbare Grenze — wird hier abgelöst), ADR
[`0118`](./0118-sehenswuerdigkeit-trennt-nicht-mehr-und-eine-eigene-ausdehnungsgrenze-fuers-zusammenlegen.md)
(Punkt 2, zweiter Absatz — der Inhalt von `UNBREAKABLE_CAUSES` — wird hier abgelöst), ADR
[`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (Punkt 1, die Eindämmung der
Motivstärken — hier gelesen und nicht geändert)

**Umfang:** rund 130 Zeilen gegen einen Richtwert von 100. Die Entscheidung löst drei ADRs in
benannten Teilen ab, und zwei ihrer Punkte (der nicht aufgeschobene Vermerk, die mitfallende
Rücksetzung) sind ohne ihre Ausfallrichtung nicht anwendbar.

## Kontext

Die Einheit, um die es geht, ist der Anlass: ein Ausflug, ein Abend, ein Kindergeburtstag. Der
Motivwechsel schneidet quer dazu. Er trennt dort, wo weder Zeitlücke noch Schritt noch Ausdehnung
noch Dauer einen Wechsel des Anlasses anzeigen — innerhalb eines Ausflugs wechselt das Gezeigte
mehrfach, ohne dass ein zweiter Anlass begänne. Solange er eine Grenze **allein** eröffnen kann,
hängt die Zahl der Events an einer Modellaussage über Bildinhalte statt an der Reise.

Die Folge trifft nicht nur die Anzeige: Liegt die Eventzahl auf oder über dem Album-Richtwert,
vergibt `selection.py::_quotas` nach „Abdeckung zuerst" jedem Event genau einen Platz, und die
Gewichtung nach Größe beginnt gar nicht erst. Die Zahlen dazu stehen im Messprotokoll der Spec 0506.

## Entscheidung

### 1. Die vorgelagerte Stufe vermerkt, sie erzeugt nicht

`motif_change_starts` bleibt unverändert — Motivbild, Bestätigungsfenster, rückwirkende Lage und
die geteilte Grenze aus ADR 0109 gelten wie bisher. Was fällt, ist die Wirkung ihres Ergebnisses:
Ein gelieferter Index eröffnet **kein** Event mehr. Er fügt `motivwechsel` der Ursachenmenge einer
Grenze hinzu, die der Signal-Durchlauf an derselben Stelle ohnehin zieht; fällt er auf keine solche
Grenze, bleibt er wirkungslos.

**Der Vermerk wird nicht aufgeschoben.** Ein Index ohne gleichzeitige Signalgrenze wird verworfen,
nie auf die nächste Grenze übertragen. Eine Ursachenmenge sagt aus, welche Signale **diese** Grenze
gemeldet haben; ein nachgetragener Vermerk behauptete eine Mitursache an einer Stelle, an der der
Wechsel nicht stattgefunden hat, und die Statistik zählte ihn dort mit.

**Zwei Zusagen folgen daraus, beide maschinell prüfbar:**

- `motivwechsel` steht **nie allein** in einer Ursachenmenge; die Spalte „alleinige Ursache" der
  Trennursachen-Statistik steht für ihn dauerhaft auf 0.
- Die Gliederung ist von der ersten Stufe **vollständig unabhängig**: Unter einem nie erreichbaren
  Bestätigungsfenster liefert `explain_events` dieselbe Eventfolge wie am Betriebswert; allein die
  Ursachenmengen unterscheiden sich. Das ist die stärkere der beiden Formen und die eigentliche
  Zusage.

**Die Rücksetzung fällt mit.** Ein erzwungener Start rief `begin` auf allen Signalen und setzte
damit Ausdehnung und Dauer zurück; ohne ihn laufen beide über den Motivwechsel hinweg weiter. Die
Richtung ist benannt, nicht übersehen: Der Durchlauf kann dadurch an **späterer** Stelle eine Grenze
ziehen, die er vorher nicht mehr brauchte. Die Eventzahl fällt deshalb nicht um genau die Zahl der
entfallenen erzwungenen Starts.

### 2. Der Name bleibt im Ursachenvorrat

`BOUNDARY_MOTIF_CHANGE` bleibt in `BOUNDARY_CAUSES`. Der Vorrat ist ein Berichtswortschatz, und
„war beteiligt" bleibt eine Zahl, die sich bewegt: Wie oft ein Motivwechsel mit einer echten
Ursache zusammenfällt, ist die Größe, an der eine spätere Änderung dieser Entscheidung gemessen
würde. Ohne das Symbol gäbe es sie nicht mehr.

### 3. `UNBREAKABLE_CAUSES` entfällt ersatzlos

Kein Vorrat, keine leere Menge, keine Prüfung in `_may_merge`. Das Kriterium dafür steht in ADR 0118
Punkt 2 und gilt hier für den ganzen Vorrat statt für einen Eintrag: Er ist kein Wortschatz, sondern
eine an **jeder Kante** gelesene Regel, und ein leerer Vorrat behauptete dort eine Sperre ohne
Gegenstand.

Inhaltlich trägt ihn nichts mehr. Eine Grenze mit `motivwechsel` führt nach Punkt 1 stets auch eine
echte Ursache, und gegen die prüfen die drei verbliebenen Riegel ohnehin. Ein Segment allein zu
lassen, weil an seiner Kante ein Motiv wechselte, während Zeitlücke, Dauer und Ausdehnung das
Zusammenlegen erlauben, wäre genau die Trennwirkung, die Punkt 1 aufhebt — nur auf der dritten Stufe
statt im Durchlauf.

**Der Berichtsgrund `MERGE_BLOCK_UNBREAKABLE` bleibt** in `MERGE_BLOCK_REASONS` und steht dauerhaft
auf 0. Dieselbe Ungleichbehandlung wie in ADR 0118 Punkt 2: Der Vorrat der Sperrgründe ist ein
Wortschatz, und die Null ist der Nachweis. Ohne die Zeile wäre eine Riegel-Diagnose nicht mehr gegen
die frühere zu halten, in der `unantastbar` der größte Blocker war.

**Nicht gewählt: ein leerer `frozenset` mit Begründung.** Er hielte einen Begriff für eine künftige
Ursache bereit, die unantastbar sein soll — zum Preis einer an jeder Kante gelesenen Regel, die nie
etwas entscheidet, und einer Zeile in `_may_merge`, die kein Test scharf stellen kann. Eine künftige
Unantastbarkeit ist eine eigene Entscheidung und bringt ihren Vorrat mit.

## Konsequenzen

- ADR 0109 bekommt einen Teil-Vermerk: Punkt 1, die Wirkung des erzwungenen Starts, gilt nicht mehr.
  Unverändert gelten die zweistufige Anlage, der Wechselbegriff (Punkt 2), Bestätigungsfenster und
  rückwirkende Lage (Punkt 3), wer mitredet (Punkt 4) und die geteilte Grenze (Punkt 5).
- ADR 0117 bekommt einen **zweiten** Teil-Vermerk auf Punkt 3: Von den zwei unantastbaren Grenzen
  bleibt keine. Die drei übrigen Riegel, die Nachbarwahl, die Terminierung und die werfende
  Rundenobergrenze gelten unverändert.
- ADR 0118 bekommt einen Teil-Vermerk auf Punkt 2, zweiter Absatz: Der dort beschriebene Inhalt von
  `UNBREAKABLE_CAUSES` entfällt mit dem Vorrat. Punkt 2 erster Absatz, Punkt 1, 3 und 4 gelten
  unverändert.
- **Zwei Zusagen der Spec 0477 sind aufgehoben:** „Ändert sich, was auf den Fotos zu sehen ist,
  beginnt ein neues Event" und „ein motivgetrenntes Einzelbild darf allein bestehen". Die Spec bleibt
  `Implemented`; weiter gilt von ihr der **Begriff** des Motivwechsels, nicht seine Wirkung.
- **Die Kontrollflusswirkung der Motivstärke auf die Gliederung fällt auf null.** Keine vom Modell
  gelieferte Zahl bewegt danach noch eine Event-Grenze. Die Konsequenz aus ADR 0109, eine Änderung an
  `MOTIF_PRESENCE_THRESHOLD` verschiebe zweierlei, fällt damit: Sie verschiebt wieder nur, welche
  Fotos der Auswahlvorschlag als Motivträger sieht. Das Vergleichsverbot aus ADR 0091 Punkt 1 gilt
  unverändert — `carried_motifs` behält mit dem Auswahlvorschlag seinen auswählenden Leser.
- **Die ausgeschöpfte Reichweite eines Sehenswürdigkeitsnamens wächst erneut** (M9): Events werden
  größer, ein Name benennt mehr Fotos und unterdrückt deren Koordinate und Ortsnamen. Die drei
  Schranken aus ADR 0118 (`EVENT_MAX_SPAN`, `MERGE_EXTENT_MAX_METERS`, Zahl der Kandidatenfotos)
  gelten unverändert und bleiben endlich; nur der ausgeschöpfte Anteil steigt.
- **Größere Events sind die getragene Kehrseite.** Ein Anlass kann ein Fünftel der Kandidaten eines
  Laufs umfassen. Gegen Überverschmelzung stehen ab jetzt allein Zeitlücke, Dauer, Schritt und
  Ausdehnung.
- Die Empfindlichkeitsmessung (`--motiv`) misst danach eine Gliederung, die sich unter keiner
  Kombination mehr ändert; ihre Spalten „Events", „Ein-Bild-Cluster", „größtes Event" und „längste
  Dauer" sind über alle Zeilen gleich. Sie bleibt genau deshalb: Diese Gleichheit **ist** der
  Nachweis, dass die Stufe keine Grenze mehr erzeugt.
- Die Gliederung ändert sich für **jeden** Lauf. Bestehende Läufe behalten ihre Events, bis sie neu
  berechnet werden. Keine Migration, keine Schemaänderung, kein neues Feld in der API.
- `docs/architecture.md` (Abschnitt Event) und `specs/architecture/0003-securitykonzept.md` ziehen im
  selben Pull Request nach.
