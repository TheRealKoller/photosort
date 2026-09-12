# 0088 - Das Bausteinregister ist Handarbeit ohne eigene Soll-Struktur; die Standardseite wird umbenannt

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** [GitHub-Issue #440](https://github.com/TheRealKoller/photosort/issues/440),
[`features/0440-bausteinzustaende.md`](../features/0440-bausteinzustaende.md)

**Berührt außerdem (keine Ablösung):**
- [`decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)
  Abschnitte 1 und 4 (erzeugte Daten, handgeschriebene Aufbaulogik, Laufregel je Aufbaudatei):
  unverändert gültig. Es entsteht keine fünfte Nutzlast und keine neue Laufregel.
- [`decisions/0082-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md`](./0082-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md)
  Abschnitt 2 (`views.json` führt die Soll-Struktur): unverändert gültig **für Ansichten**.
  Abschnitt 2 unten entscheidet, dass das Register keine eigene Soll-Struktur bekommt.
- [`decisions/0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md`](./0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md)
  (eine Arbeitsseite ist Arbeitsstand und für `verify.js` nicht vorhanden): unverändert. Die
  Registerseite ist keine Arbeitsseite — sie bleibt.

## Kontext

Die Design-Datei kennt heute zwei Seitenklassen: die **Ansichtsseite** (ADR 0082 — Soll-Struktur in
`views.json`, von `verify.js` gezählt) und die **Arbeitsseite** eines Rundenlaufs (ADR 0073 —
Arbeitsstand, für `verify.js` nicht vorhanden, von Daniel weggeworfen). Issue #440 verlangt eine
dritte: eine dauerhaft benannte Seite, auf der die zwölf Bausteine mit ihren Ausprägungen und
Zuständen in beschrifteten Rastern nachschlagbar sind — ausdrücklich ohne Generator und ohne
Anspruch, einen Wiederaufbau der Datei zu überstehen.

Die naheliegende Antwort wäre eine fünfte Nutzlast (`seed-register.js`) in der Form von ADR 0066.
Sie ist aus demselben Grund falsch, aus dem es kein `seed-views.js` gibt: Ein Raster besteht aus
Position, Größe, Reihenfolge und Beschriftung, also fast vollständig aus Werten, und ADR 0066
Abschnitt 1 verbietet getippte Werte in einer Nutzlast. Der Bestand, der auf der Standardseite
liegt, verschärft die Lage: Dort stehen die **Varianten-Behälter** der Bibliothek, also die
Hauptinstanzen aller Bausteine.

## Entscheidung

### 1. Dritte Seitenklasse „Register": genau eine Seite, von Hand aufgebaut

Die Seite heißt `Bausteine — Zustände` und entsteht über den Skill `penpot-design`, Schritt 3
(„Entwerfen mit der Bibliothek"), in der Hauptsession. Es entsteht **kein** `seed-register.js`,
keine fünfte Zeile in der Schritttabelle und kein Eintrag in der Laufregel-Zuordnung von
`frontend/penpot/payload.test.ts`. Ein Rundenlauf (`penpot-entwurfsrunden`) ist hier nicht der Weg:
Es gibt nichts auszuwählen — die Rasteraufteilung steht in der Spec —, und der Umweg über eine
Arbeitsseite hieße, dieselbe Handarbeit zweimal zu leisten, weil Formen nicht über Seitengrenzen
wandern.

### 2. Keine eigene Soll-Struktur-Datei — die Soll-Aussage liegt bereits vollständig vor

Dies ist die bewusste Abweichung von ADR 0082 Abschnitt 2, und sie wendet dieselbe Regel an:
Das Repository führt, was ableitbar oder abzählbar ist. **Was** das Register zeigen muss, steht
abzählbar in `design/penpot/components.json` (Achsen, Ausprägungen, Zustände je Baustein) und in
`icons.json` (die zwölf Symbole); **wie** es angeordnet ist, steht als Rastertabelle im Abschnitt
„Architektur / Umsetzung" der Feature-Spec. Eine dritte Datei wiederholte `components.json` in
anderer Sortierung — genau die zweite, driftende Wertekopie, gegen die ADR 0066 antritt.

Der Unterschied zu einer Ansicht ist damit benannt: Für eine Ansicht gab es keine Quelle, aus der
ihre Struktur ableitbar wäre, für das Register gibt es sie.

**Eine Lücke wird auf der Seite sichtbar geführt, nicht geschlossen** (wortgleich die Regel aus
ADR 0082 Abschnitt 5): Ein Element, das die Anwendung verwendet und das die Bibliothek nicht als
Baustein führt, steht als benannter Eintrag auf der Seite. Es wird nicht nachgezeichnet und nicht
als Baustein ergänzt — das entscheidet eine eigene Story.

### 3. Für `verify.js` ist das Register per Bauart nicht vorhanden

**Kein Objekt des Registers trägt die Plugin-Daten `schluessel`, `ansicht` oder `breite`.** Das ist
die Bedingung dafür, dass die eingefrorenen Kardinalitäten unangetastet bleiben (zwölf Bausteine,
sieben Ansichten, dreißig Ansichtsbretter, sechs Ansichtsbehälter): Ein Register-Objekt mit
`schluessel` stünde in der Bausteinliste, gegen die der Zeichenkettenvergleich läuft, und der
Abgleich würde rot, ohne dass etwas fehlt. Ein Lauf nach dem Bau muss deshalb **dieselben Zahlen**
melden wie davor; das ist der mechanische Abschluss dieser Arbeit. Daraus folgt zugleich, dass in
`payload.test.ts` keine Kardinalität und keine zeilengebundene Freigabe angefasst wird.

### 4. Die Standardseite wird umbenannt, nicht ersetzt

Umbenennen erhält jede Form, jede Hauptinstanz und jede Plugin-Datenbindung. Neu anlegen und
verschieben hieße, Hauptinstanzen von Bibliothekskomponenten über Seitengrenzen umzuhängen: an der
Plugin-API ungemessen, und Penpot lässt ohnehin nur die **aktive** Seite beschreiben. Der Rückweg
nach einem misslungenen Umzug wäre `seed-components.js`, das auf einer bespielten Datei
fail-closed abbricht — und dessen Lauf alle von Hand entstandenen Ansichten kostete.

**Welche Seite den Bestand trägt, wird gemessen, nicht am Namen angenommen** (an den Plugin-Daten
`schluessel` der Varianten-Behälter). Ist `page.name` nicht schreibbar — vor dem Bau über
`penpot_api_info` zu klären statt anzunehmen —, wird das **gemeldet, nicht umgangen**: Daniel
benennt die Seite dann im Browser um. Ein Ersatzweg über Neuanlegen wird nicht gewählt.

### 5. Zwei Zonen auf einer Seite; am Bestand wird nichts angefasst

Das Register entsteht in einem freien Bereich **neben** dem Bestand, beide Zonen mit einer
Überschrift. Am Bestand wird nichts gelöscht, verschoben, umbenannt, in der Größe geändert oder in
seinen Plugin-Daten verändert — auch nicht am von Hand entstandenen Brett `Entwurf:
Sichtungsleiste`, das dort liegt und in keinem Commit auffindbar ist. Kollidiert die Fläche, weicht
das Register aus, nicht der Bestand.

Die Zellen des Registers sind Bibliotheks-**Instanzen** (`komponente.instance()`, Zustand über
`switchVariant`), nie nachgezeichnete Formen; die Hauptinstanz bleibt dabei unberührt.

### 6. Die abschließende Liste gilt auch für Ad-hoc-Entwurfscode

Was ein `execute_code`-Aufruf darf, bleibt die Liste aus ADR 0066 Abschnitt 5 Punkt 6. Sie ist hier
**nicht statisch prüfbar**, weil es keine Datei im Branch gibt, an der ein Test ansetzen könnte —
verbindlich ist sie trotzdem: kein Netzwerkzugriff, keine dynamische Codeerzeugung, kein DOM-
Zugriff, kein Zugriff auf andere Dateien oder Bibliotheken der Instanz, und **kein Löschen von
Objekten, die der Lauf nicht selbst angelegt hat**. Der letzte Punkt ist hier der tragende: Er ist
die einzige Zusicherung, die den Bestand aus Abschnitt 5 schützt.

## Begründung

Der tragende Gedanke ist die Unterscheidung aus ADR 0082, hier nur auf einen Fall angewandt, den
sie noch nicht kannte: Das Repository führt, was ableitbar oder abzählbar ist. Beim Register ist
beides schon geführt — die Menge in `components.json`, die Anordnung in der Spec. Eine dritte
Datei hätte die Verifizierbarkeit nicht erhöht, sondern eine Kopie geschaffen, die ab dem ersten
neuen Baustein von `components.json` abweicht, ohne dass ein Test das sähe.

Die zweite Überlegung ist die Asymmetrie der Fehlerkosten beim Umbenennen. Eine Seite trägt ihren
Namen billig; die Hauptinstanzen von 158 Varianten liegen nur einmal. Der teure Weg ist deshalb
nicht der, der mehr Arbeit macht, sondern der, der etwas anfasst, das nicht wiederherstellbar ist.

## Konsequenzen

- **Positiv:** Kein Generator, der nach einem Lauf altert. Keine dritte Wertekopie. Die
  eingefrorenen Kardinalitäten und die zeilengebundenen Freigaben bleiben unberührt, der Bau des
  Registers kann den Prüfsatz also nicht rot färben. Der Bibliotheksbestand bleibt nachweislich
  vollständig, weil nichts an ihm angefasst wird.
- **Negativ / bewusst getragen:**
  - **Das Register ist nach einem Instanzverlust nicht wiederherstellbar.** Es kommt ausschließlich
    durch erneute Handarbeit zurück, dann aber mit Vorlage: Die Rastertabelle der Spec und
    `components.json` sagen vollständig, was zu bauen ist — mehr, als ADR 0082 einer Ansicht lassen
    kann.
  - **Das Register altert still.** Kommt ein Baustein, eine Ausprägung oder ein Zustand hinzu, fällt
    das Fehlen im Register **nicht** auf: `verify.js` sieht die Seite nicht, und kein Test kann
    Penpot lesen. Wer einen Baustein ergänzt, ergänzt das Register von Hand — oder die Seite ist ab
    dann unvollständig, ohne dass irgendwo etwas rot wird. Das ist der Preis von Abschnitt 3.
  - **Die Seite kostet Hauptsessionzeit mit verbundener Instanz**, und ihr Abschluss hängt an
    Daniels Sichtprüfung.
- **Folgearbeit:** Ob die auf der Seite benannten Lücken (aufklappende Menü- und Infoflächen,
  Schriftmuster) als Bausteine in die Bibliothek aufgenommen werden, entscheidet eine eigene Story.
