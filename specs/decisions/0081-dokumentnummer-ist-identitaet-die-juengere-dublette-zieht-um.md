# 0081 - Die Dokumentnummer ist Identität: die jüngere Dublette zieht um, keine Nummer wird recycelt

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** GitHub-Issue [`#406`](https://github.com/TheRealKoller/photosort/issues/406), Spec
`specs/features/0406-*.md`

## Kontext

Specs, ADRs und Konzeptdokumente tragen ihre Identität in ihrer vierstelligen Nummer; die
gebräuchlichste Form, sie zu nennen, ist die blanke Zahl („ADR 0069 Punkt 8") ohne Dateinamen.
Ist dieselbe Nummer zweimal vergeben, bezeichnet jede solche Nennung zwei Dokumente. Der Bestand
trägt heute eine solche Dublette (`specs/decisions/`, `0069`), und sie ist seit zwei Tagen
unbemerkt: `scripts/tests/test_verweisnummern_in_markdown.py` bindet den sichtbaren Linktext an
seine Zieldatei — bei einer Dublette passt der Text zu beiden Zielen, und die Prüfung bleibt grün.

Die Nummernräume der drei Verzeichnisse überlappen einander von Bauart wegen: Eine Feature-Spec
trägt die Nummer ihres Issues (ADR
[`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md)), `decisions/` und
`architecture/` zählen je für sich fortlaufend. Gemessen sind es 66 Nummern, die `decisions/` und
`features/` heute gemeinsam führen, und vier, die `architecture/` und `features/` teilen.

## Entscheidung

### 1. Eindeutig ist eine Nummer je Verzeichnis, nicht verzeichnisübergreifend

`specs/decisions/`, `specs/architecture/` und `specs/features/` sind drei getrennte Nummernräume.
Eine verzeichnisübergreifende Eindeutigkeit wird **nicht** eingeführt — sie wäre heute an 70
Stellen verletzt und stünde gegen ADR 0043.

### 2. Eine Dublette wird aufgelöst, nie ausgenommen — und es zieht die jüngere um

Es gibt keine Ausnahmeliste, in keiner Form und für keinen Einzelfall. Umzuziehen hat das
**jüngere** der beiden Dokumente: dasjenige, dessen einführender Commit später auf `main` liegt.
Es hat eine Nummer genommen, die bereits vergeben war; das ältere Dokument hat sie rechtmäßig.

Sind beide im selben Commit entstanden, zieht das Dokument mit den **wenigeren blanken Nennungen**
um (Nennungen, die nur die Zahl führen und deshalb von Hand zugeordnet werden müssen). Dieses
Kriterium ist nachrangig, nicht gleichrangig: Sonst entschiede die Reparatur, wer recht hatte.

### 3. Die neue Nummer ist die nächste freie; die alte wird nie wieder vergeben

Nächste freie Nummer des Verzeichnisses, keine Lücke wird gefüllt. Die durch den Umzug frei
werdende Nummer bleibt der zurückbleibenden Datei; sie wird nicht ein zweites Mal vergeben, auch
nicht nach einem späteren Löschen.

### 4. Umnummerieren ist keine Änderung der Entscheidung

Die Unveränderlichkeit einer angenommenen ADR (`specs/README.md`) steht einem Umzug nicht
entgegen: Geändert werden der Dateiname und das Nummern-Token der Titelzeile, kein Satz der
Entscheidung, keine Statuszeile, kein Teil-Vermerk. Eine ablösende ADR entsteht dafür **nicht** —
sie wäre eine falsche Auskunft über einen Entscheidungswechsel, den es nicht gibt.

Die umgezogene Datei bekommt dabei genau eine zusätzliche Kopfzeile:

```
**Frühere Nummer:** NNNN (bis JJJJ-MM-TT), aufgelöste Dublette mit <vollständiger Dateiname>.
```

Ohne sie bliebe jede Nennung außerhalb des Repositoriums — Issue-Kommentare, gemergte Pull
Requests, die Git-Historie — dauerhaft unauflösbar. Die Zeile ist ab ihrer Aufnahme selbst
unveränderlich.

### 5. Die Nennungen werden fundstellengenau umgeschrieben, nie per pauschaler Ersetzung

Eine Textersetzung über die alte Nummer schreibt die Nennungen des fremden gleichnamigen
Dokuments stillschweigend mit und meldet Erfolg. Verbindlich ist deshalb ein dreiteiliges
Verfahren, dessen dritter Teil die ersten beiden prüfbar macht:

1. **Inventar** — jede Fundstelle der alten Nummer im **gesamten** von Git verwalteten Bestand,
   nicht nur in Markdown, als `datei:zeile` festgehalten. Die Gesamtzahl wird notiert.
2. **Klassifikation** — jede einzelne Fundstelle wird genau einem der beiden Dokumente
   zugeordnet, bei blanken Nennungen durch Lesen des Satzes. Keine Fundstelle bleibt unzugeordnet;
   die Summe beider Klassen muss die Gesamtzahl aus Schritt 1 ergeben.
3. **Bilanz** — nach der Änderung wird gegen die vorab notierten Zahlen und die vorab notierte
   Menge betroffener Dateien abgeglichen. Eine Abweichung nach oben heißt: zu viel ersetzt.

Ersetzt wird je Fundstelle mit umgebendem Kontext im Suchmuster (`CLAUDE.md`, „Werkzeugwahl bei
Dateiarbeit"), nie musterbasiert über die blanke Zahl.

### 6. Die Prüfung liegt bei den Repo-Konsistenztests und wird mit der Auflösung ausgeliefert

`scripts/tests/`, CI-Job `demo-scripts`, kein neuer Job und kein neues Werkzeug. Ihre Meldung
nennt **beide** vollständigen Dateinamen — die Nummer allein ist genau das Mehrdeutige. Sie
entsteht im selben Pull Request wie die Auflösung der bestehenden Dublette: Sie ist beim Anlegen
rot, und dieser Rot-Lauf auf einem echten Defekt ist ihr tragender Wirksamkeitsbeleg.

## Begründung

- **Umzug statt Ausnahme:** Eine Ausnahmeliste würde die Mehrdeutigkeit festschreiben, statt sie
  zu beenden — und sie beträfe genau die Stellen, an denen ein Leser sie am wenigsten vermutet.
- **Alter vor Aufwand:** Ein Kriterium, das den Aufwand zum Maßstab macht, belohnt das Dokument
  mit den meisten Nennungen — also das, dessen falsche Nummer am teuersten geworden ist.
- **Frühere Nummer im Kopf statt im Gedächtnis:** Das Repository kann seine eigenen Verweise
  nachziehen, alles außerhalb nicht.
- **Bilanz statt Vorsatz:** „Keine pauschale Ersetzung" ist als Absicht nicht prüfbar. Vorab
  notierte Zahlen und eine vorab notierte Dateimenge sind es.

## Konsequenzen

- Die bestehende Dublette `0069` in `specs/decisions/` wird nach dieser Regel aufgelöst: Der
  jüngere Eintrag (Penpot-Ansichtsentwürfe, eingeführt am 2026-09-09 um 18:35, gegenüber 18:11)
  zieht auf [`0082`](./0082-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md);
  [`0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md`](./0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md)
  behält seine Nummer, und keine seiner Nennungen wird angefasst.
- Die Vergabe der nächsten freien Nummer bleibt Handarbeit. Diese Entscheidung verhindert die
  Kollision nicht, sie macht sie laut.
- Kein Effekt auf `specs/README.md` (die Namenskonvention ändert sich nicht), auf
  `test_verweisnummern_in_markdown.py` (andere Fehlerklasse, unverändert) und auf das Backend-
  Coverage-Gate.
- Ein späterer Wechsel — etwa doch eine verzeichnisübergreifende Eindeutigkeit oder eine
  maschinelle Nummernvergabe — braucht eine neue, diese ADR als „Superseded" markierende ADR.
