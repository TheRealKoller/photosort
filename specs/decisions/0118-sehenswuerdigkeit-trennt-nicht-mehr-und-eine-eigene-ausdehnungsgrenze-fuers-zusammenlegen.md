# 0118 - Die Sehenswürdigkeit trennt nicht mehr, und das Zusammenlegen bekommt seine eigene Ausdehnungsgrenze

**Status:** Accepted
**Teilweise abgelöst:** Punkt 2, zweiter Absatz — der dort festgelegte Inhalt von
`UNBREAKABLE_CAUSES` („dort bleibt allein `motivwechsel`") entfällt mit dem Vorrat selbst; die
Unterscheidung Wortschatz/Regel, die ihn begründet, gilt weiter und trägt in ADR
[`0119`](./0119-der-motivwechsel-vermerkt-eine-grenze-statt-eine-zu-eroeffnen.md) dessen
Abschaffung. Unverändert gelten Punkt 2 erster Absatz (`BOUNDARY_LANDMARK` bleibt in
`BOUNDARY_CAUSES`), Punkt 1, Punkt 3 und Punkt 4. Der Berichtsgrund `MERGE_BLOCK_UNBREAKABLE` bleibt
bestehen und steht ab dann dauerhaft auf 0, statt eindeutig den Motivwechsel zu nennen.
**Datum:** 2026-09-19
**Bezug:** Spec [`0506`](../features/0506-cluster-als-anlass.md), ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (Abschnitt 3,
zweiter Absatz — die Sehenswürdigkeit als Trennsignal — wird hier abgelöst), ADR
[`0117`](./0117-der-anlass-als-einheit-eigene-schwellen-dauergrenze-und-mindestgroesse.md)
(Punkt 3: Riegel (c) und die zweite unantastbare Grenze werden hier abgelöst), ADR
[`0107`](./0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md)
(bleibt vollständig in Kraft, siehe Punkt 3)

**Umfang:** rund 135 Zeilen gegen einen Richtwert von 100. Die Entscheidung trägt vier Punkte, sie
löst zwei ADRs in benannten Teilen ab, und zwei ihrer Punkte (die Reichweite des Namens, die
Ausfallrichtung der neuen Grenze) sind ohne ihre Konsequenz nicht anwendbar.

## Kontext

Vier Messungen an Projekt 3 liegen vor (Spec 0506, Abschnitt „Messprotokoll"); die Abnahme ist bei
20,5 % Ein-Bild-Clustern gegen ein Ziel von ≤ 12,1 % verfehlt. Zwei Befunde tragen diese
Entscheidung.

**Die Sehenswürdigkeit trennt häufig und trennt schlecht.** Sie ist alleinige Ursache von 8,0 % der
Grenzen und eröffnet dabei zu 60 % ein zu kleines Segment — die höchste Quote aller sechs Ursachen.
Zugleich entstanden 42,3 % der Erkennungen **ohne jeden Ortshinweis**, und 18 Events werden von
genau einem von vielen Fotos benannt. Eine Trennung, die regelmäßig von einer einzigen ortsblinden
Erkennung ausgelöst wird, ist kein Beleg dafür, dass hier ein anderer Anlass begann.

**Das Zusammenlegen ist für ausdehnungsgetrennte Segmente strukturell unpassierbar.** Riegel (c)
prüft `EVENT_EXTENT_MAX_METERS` am Ergebnis — dieselbe Bedingung, deren Überschreitung die
Trennung ausgelöst hat. Was die Ausdehnung getrennt hat, kann die dritte Stufe deshalb nie wieder
zusammenlegen. Block F belegt die Folge: `unantastbar` ist bei 7 von 18 gesperrten Segmenten an
jeder Kante der Grund, `ausdehnung` bei 3.

## Entscheidung

### 1. `LandmarkChangeSignal` entfällt; der Name bleibt am Event

Die Klasse entfällt vollständig — aus `default_signals()` **und** als Klasse. Sie bleibt nicht als
nie meldendes Signal stehen: Die Liste ist der Erweiterungspunkt für Signale, die trennen, und ein
Eintrag, der das nicht mehr tut, macht sie zu einer Liste mit zwei Bedeutungen. Der Bericht liest
seinen Ursachenvorrat ohnehin aus `BOUNDARY_CAUSES` und nicht aus der Signalliste; eine Attrappe
kaufte dort nichts.

**Der Name bleibt unverändert am Event.** `events.landmark_name`, `place_kind='landmark'`, die
Rangfolge in `_place_of` und die Anzeige ändern sich nicht. Was fällt, ist allein die
**Trennwirkung**.

### 2. Der Ursachenvorrat behält `sehenswuerdigkeit`, die Sperre verliert sie

Die beiden Vorräte werden **ungleich** behandelt, und das ist der Kern dieses Punktes.

`BOUNDARY_LANDMARK` **bleibt** in `BOUNDARY_CAUSES`. Der Vorrat ist ein Berichtswortschatz, und
seine Aufgabe ist die Vergleichbarkeit zweier Messungen: Das Messprotokoll der Spec 0506 führt die
Zeile `sehenswuerdigkeit` mit 10 beteiligten und 7 alleinigen Grenzen. Verschwände das Symbol,
hätte die Nachmessung eine Zeile weniger, und kein Leser könnte unterscheiden, ob die Ursache
weggefallen oder nie gemessen worden ist. Die Zeile mit `0 (0,0 %)` **ist** der Nachweis, dass
diese Entscheidung gewirkt hat — dieselbe ehrliche Null, die das Projekt bei `kein_nachbar` bereits
trägt.

`BOUNDARY_LANDMARK` **fällt** aus `UNBREAKABLE_CAUSES`; dort bleibt allein `motivwechsel`.
`UNBREAKABLE_CAUSES` ist kein Wortschatz, sondern eine an jeder Kante gelesene Regel. Ein Eintrag,
der nie treffen kann, ist dort keine ehrliche Null, sondern eine falsche Aussage über das laufende
System — er behauptet eine Sperre, für die es keinen Gegenstand gibt. Der Berichtsgrund
`MERGE_BLOCK_UNBREAKABLE` bleibt davon unberührt und wird dadurch **eindeutig**: Er nennt ab jetzt
ausschließlich den Motivwechsel, wo er vorher zwei Ursachen zusammenzog.

### 3. Der eine Name eines Events ist ab jetzt eine Regel, keine Zusicherung

`_name_of` nimmt den Namen des frühesten benannten Fotos. Das war bisher ein defensiver Zweig
hinter der Zusicherung „ein Event trägt höchstens einen Namen, dafür sorgt `LandmarkChangeSignal`"
(`events.py:742`). Diese Zusicherung fällt mit dem Signal: Ein Event **darf** ab jetzt Fotos mit
verschiedenen Namen enthalten, und der früheste gewinnt. Die Regel ist damit die normale
Berechnung und braucht ihren eigenen Fall, statt weiter als Vorsichtsmaßnahme beschrieben zu sein.

**Die Reichweite des Namens wächst, und das ist die getragene Kehrseite.** Ein Name benennt jetzt
ein potenziell größeres Event und verdrängt dort weiterhin dessen Koordinatenstufe: Ein Event mit
Namen bekommt keinen Ortsnamen (`locality_of_event`) und keine Koordinate. Eine einzelne
ortsblinde Erkennung kann dadurch einem ganzen Ausflug ihren Namen geben, wo vorher nur der
abgetrennte Teil ihn trug. Das ist keine neue Fehlerquelle, sondern eine größere Reichweite der
bestehenden; ihre Behebung ist die Plausibilisierung des Namens und gehört zu Issue #514, nicht
hierher. ADR 0107 bleibt davon unberührt und gilt vollständig — das Namensregister verhindert ab
jetzt keine Zerlegung mehr, sondern entscheidet, **welchen** Namen ein Event trägt.

### 4. Das Zusammenlegen prüft `MERGE_EXTENT_MAX_METERS`, nicht die Trennschwelle

Riegel (c) prüft ab jetzt eine eigene, größere Grenze. Sie **muss** größer sein als
`EVENT_EXTENT_MAX_METERS`, sonst ist die Stufe für genau die Segmente unpassierbar, die die
Ausdehnung getrennt hat.

**Herleitung, nicht Kalibrierung** (ein Kalibrierungslauf entfällt, Begründung im Messprotokoll):
`MERGE_EXTENT_MAX_METERS = 1500,0` — die Trennschwelle plus **einen** Schritt
(`EVENT_EXTENT_MAX_METERS + EVENT_STEP_MAX_METERS`). Zugeschlagen wird ein Segment unter
`MIN_EVENT_PHOTOS`, heute also ein einzelnes Foto ohne eigene Ausdehnung; die Box wächst damit
genau um dessen Abstand zur Box des Nachbarn. Ein Schritt über `EVENT_STEP_MAX_METERS` ist im
Maßstab dieses Projekts bereits ein Ortswechsel und trennt für sich. Mehr als einen Schritt
zuzulassen hieße, eine Trennung aufzulösen, die das Projekt selbst einen Ortswechsel nennt;
weniger hieße, die Stufe weiter leerlaufen zu lassen.

Der Wert ist ein **Literal**, keine gerechnete Summe zweier Konstanten: Die sieben Schwellen werden
überall als Modulattribut gelesen, damit ein Prüflauf sie verschieben kann, und eine beim Import
gebundene Summe folgte dieser Verschiebung nicht. Die Herleitung steht als Kommentar an der
Konstante, die Relation als Ungleichung im Prüfsatz — im Muster von `MERGE_MAX_GAP`.

**Was dadurch fällt:** Die Zusage „kein Event überschreitet `EVENT_EXTENT_MAX_METERS`, weder als
Ergebnis des Durchlaufs noch als Ergebnis des Zusammenlegens" gilt so nicht mehr. An ihre Stelle
tritt: **Kein Event überschreitet `MERGE_EXTENT_MAX_METERS`**, und kein Event **aus dem Durchlauf**
überschreitet `EVENT_EXTENT_MAX_METERS`. Die Ausfallrichtung bleibt endlich und bezifferbar: Die
Ausdehnung eines Events ist in beiden Stufen nach oben beschränkt, nur durch zwei verschiedene
Zahlen.

## Konsequenzen

- ADR 0087 bekommt einen **dritten** Teil-Vermerk: Abschnitt 3, zweiter Absatz (die Sehenswürdigkeit
  als Trennsignal) gilt nicht mehr. Unberührt bleiben das Protokoll, die nicht kurzgeschlossene
  Auswertung, die Liste als Erweiterungspunkt — und die Regel, dass ein leerer oder zu langer Name
  als nicht vorhanden gilt und **verworfen statt abgeschnitten** wird. Nur ihre Begründung wechselt:
  Sie trägt nicht mehr das Trennsignal, sondern `events.landmark_name` und die Anzeige.
- ADR 0117 bekommt einen Teil-Vermerk auf Punkt 3: Riegel (c) prüft eine eigene Grenze, und von den
  zwei unantastbaren Grenzen bleibt eine. Die übrigen drei Riegel, die Nachbarwahl, die
  Terminierung und die werfende Rundenobergrenze gelten unverändert.
- **Die Kontrollflusswirkung des Sehenswürdigkeit-Namens fällt auf null** (Sicherheitskonzept M9,
  Fortschreibung): Er erzeugt keine Grenze mehr und hält keine mehr fest. Was bleibt und **wächst**,
  ist seine Benennungsreichweite (Punkt 3) — begrenzt auf ein Event und damit weiter durch die Zahl
  der Kandidatenfotos gedeckelt. Alle vier bestehenden Auflagen gelten unverändert.
- Die Gliederung ändert sich für **jeden** Lauf. Bestehende Läufe behalten ihre Events, bis sie neu
  berechnet werden. Keine Migration, keine Schemaänderung, kein neues Feld in der API.
- Drei Codekommentare begründen heute eine geltende Regel mit dem entfallenden Signal
  (`landmark.py:49`, `landmark.py:289`, `models.py:1367`) und einer beschreibt eine Demo-Lage damit
  (`demo_state.py:1131`). Die Regeln bleiben, die Begründungen ziehen im selben Pull Request nach.
- `docs/architecture.md` (Abschnitt Event) und `specs/architecture/0003-securitykonzept.md` ziehen
  im selben Pull Request nach.
- Die beiden Änderungen sind getrennt nachweisbar, ohne getrennt ausgeliefert zu werden: Block B
  weist `sehenswuerdigkeit` mit 0 aus, Block F weist aus, welcher Grund danach noch sperrt.
