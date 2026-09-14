# 0102 - Die Ortsauskunft hängt an der vergröberten Zelle und am Projekt, der Event-Name am Lauf

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** Spec `specs/features/0434-*.md`, ADR
[`0029`](./0029-gps-landmark-cluster-bildung.md) Punkt 6 und ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (das Event als
Lauf-Artefakt), Story #469 (zweite Verwendung der Auskunft)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sechs Punkte trägt und
vier davon eine Auflage über Ortsdaten der Familie mitführen, die vollständig stehen bleiben muss.

## Kontext

Ein Event ohne erkannte Sehenswürdigkeit heißt heute nach Nummer und Zeitspanne. ADR 0029 Punkt 6
hat Reverse-Geocoding ausgeschlossen, weil es eine neue Vertrauensgrenze schafft. Die Story hebt
diesen Ausschluss bewusst auf. Damit stehen zwei Dinge nebeneinander, die nicht zu einem werden
dürfen: die Auskunft, was an einem Ort liegt, und der Name, den ein Event in einem Lauf trägt.

## Abgrenzung zu ADR 0029 und ADR 0072

Beide bleiben `Accepted` und bekommen einen erweiterten Teil-Vermerk. Abgelöst wird ausschließlich
**ADR 0029 Punkt 6** (Reverse-Geocoding als Out-of-Scope samt der dortigen dreistufigen
Namensrangfolge) und, in ADR 0072, die Aussage, dass ein abgeleiteter **Orts**wert nie persistiert
wird. Unberührt bleibt ADR 0029 Punkt 3: der einem Foto **übernommene** Ort bleibt unpersistiert.
Die Herkunft der **Sehenswürdigkeits**namen aus `photo_landmark_detections` gilt unverändert.

## Entscheidung

### 1. Zwei Träger, und sie liegen auf verschiedenen Ebenen

- **`place_lookups`** — die Auskunft über einen Ort. Trägt `project_id` (echter Fremdschlüssel,
  NOT NULL) und ist **lauf-unabhängig**: sie gilt unabhängig davon, wer gerade fragt, wird einmal
  beschafft und danach wiederverwendet. Mit dem Projekt verschwindet sie.
- **`events.place_name`** — der Name, den **dieses** Event in **diesem** Lauf trägt. Additive,
  nullable Spalte. Ein neuer Lauf schreibt seine Events ohnehin neu; damit entstehen die Namen neu,
  ohne eigenen Mechanismus.

**Warum der Name nicht bei der Auskunft liegt.** Ob ein Event „Berlin" oder „Berlin, Kreuzberg"
heißt, hängt davon ab, was sonst im selben Lauf liegt. Das ist keine Eigenschaft des Ortes.

**Warum am Projekt und nicht projektübergreifend wie `fine_labels`.** Jede Zeile hier ist eine
Aussage darüber, wo die Familie war, kein allgemeiner Begriff. Sie überdauert den einzelnen Lauf
und ist damit die dauerhafteste Ortsspur des Systems; die Projektbindung hält ihre Lebensdauer an
der des Projekts fest.

### 2. Der Schlüssel ist die bereits vergröberte Zelle, und die Rundung steht an einer Stelle

Gefragt wird nie mit der Koordinate eines Fotos, sondern mit der auf `PLACE_CELL_DIGITS`
Nachkommastellen gerundeten Zelle — derselbe Wert, den `events.py::_rounded` heute schon für
`place_lat`/`place_lon` bildet. `UniqueConstraint(project_id, cell_lat, cell_lon)`.

Die Körnung ist damit **eine benannte Konstante**, nicht über den Code verteilt. Sie ist die
Stellschraube der Sicherheitsentscheidung: wie grob gefragt und abgelegt wird, gehört dorthin und
nicht in die Bequemlichkeit einer Aufrufstelle. Verlässt etwas das System, dann diese Zelle.

### 3. Die Auskunft steht in Stufen, und feiner als das Viertel wird nichts abgelegt

Vier benannte Spalten `neighbourhood`, `locality`, `region`, `country`, kein zusammengesetzter
Anzeigename und **kein offener Beutel** für alles, was eine Antwort sonst noch trägt. Antworten
tragen regelmäßig Straße und Hausnummer; diese Felder werden am Parser-Rand verworfen und erreichen
die Datenbank nie. Ein offener Beutel wäre genau der Weg, auf dem sie doch dort ankämen.

`matched_level` ist die **Aussage des Anbieters darüber, was er getroffen hat**, aus dem
geschlossenen Vorrat `PLACE_LEVELS = ("neighbourhood", "locality", "region", "country")` — keine
Ableitung daraus, welche Spalten gefüllt sind. Beides kann auseinanderfallen: eine Antwort auf
Regionsebene nennt oft trotzdem eine Stadt, und die liegt dann womöglich Dutzende Kilometer
entfernt. **In diesem Fall gewinnt die Anbieterangabe.** Ein Name gilt als aufgelöst, wenn
`matched_level ∈ {"neighbourhood", "locality"}` **und** `locality` gesetzt ist; sonst gilt „kein
Name aufgelöst", nie „dürftiger, aber brauchbarer Name". Ein Wert außerhalb des Vorrats wird im
Lesepfad zu „kein Name", nie zu einer 500 — Mitgliedschaftsprüfung statt Cast, Muster `place_kind`.

`place_name` und beide Namensstufen sind freier, extern erzeugter Text. Es gilt wortgleich die
Auflage für `landmark_name`: Sanitisierung und Längengrenze am Parser-Rand, ein leerer oder zu
langer Name wird **verworfen, nie abgeschnitten**, und gerendert wird ausschließlich als regulärer
React-Textknoten. Die Prüfung gilt auch für die zusammengesetzte Form „Ort, Viertel"; reißt sie die
Grenze, bleibt der Ortsname allein stehen.

### 4. Die Viertel-Ergänzung ist eine Aussage über den Lauf und lebt in `events.py`

`places.py` beantwortet ausschließlich „was liegt an dieser Zelle" und kennt die unspezifische
Stufe (`locality`). Die Gleichnamigkeitsprüfung über alle Events eines Laufs und das Anhängen des
Viertels liegen in `events.py`. Die Modulgrenze ist die Zusage: Story #469 fragt vor der
Event-Bildung und bekommt strukturell nie „Berlin, Kreuzberg" — sie kann es gar nicht erreichen.

Ergänzt wird nur bei **genau den** Events, die sich denselben Ortsnamen teilen, und nur, soweit ein
Viertel vorliegt; die übrigen bleiben beim Ortsnamen und sind über ihre Zeitspanne unterscheidbar.
Das gilt je Event einzeln — trägt von zwei gleichnamigen Events nur eines ein Viertel, bekommt nur
dieses den Zusatz.

### 5. Kein aufgelöster Name gefährdet je einen Lauf

Drei Ausgänge, und sie sind verschieden: **keine Antwort** (Netzfehler, Zeitüberschreitung, Dienst
unerreichbar) schreibt **keine Zeile** — sonst vergiftete eine vorübergehende Störung die Zelle
dauerhaft. Eine **Antwort ohne brauchbare Ebene** schreibt eine Zeile mit leeren Namensstufen, denn
das ist eine Auskunft und keine Störung; dieselbe Zelle wird nicht erneut gefragt. **Mehr als eine**
Ortszelle mit verschiedenen Ortsnamen im selben Event ergibt keinen Namen. In allen drei Fällen
behält das Event Nummer und Zeitspanne, und der Lauf läuft weiter. Geloggt wird ohne Koordinate und
ohne Namen; es entsteht **keine** neue Zählspalte an der Lauf-Zeile (die dortigen Zähler tragen
Ist-Kosten, und diese Auflösung ist keine).

**Beschafft wird ausschließlich im Worker.** `rebuild_run_grouping` läuft in einem Request
(Versatz-Endpunkt) und legt die Events eines Laufs neu an; es bekommt deshalb einen Auflöser, der
**nur den Bestand liest und niemanden fragt**. Ohne diese Grenze hinge eine Antwort an einem
fremden Dienst, und ein Request-Pfad könnte nach außen wirken. Die Kehrseite ist harmlos: eine noch
nie gefragte Zelle bleibt dort ohne Namen, bis der nächste Kriterien-Lauf sie beschafft.

### 6. Die Wegwahl steht hinter einem Protokoll und fällt erst nach der Messung

`places.py` kennt nur `PlaceResolver` (ein Protokoll mit einer Methode: Zelle → Antwort oder
nichts). Ob dahinter ein lokaler Datensatz oder ein externer Dienst steht, ist eine Implementierung
dieses Protokolls und ändert weder Datenmodell noch Lesepfad noch Oberfläche.

Gemessen wird vorher, an einem echten Projekt, über ein **rein lesendes** Kommando im
Produktivpaket (Muster `demo_state`, aber ohne jeden Schreibzugriff), das Daniel selbst laufen
lässt. Beide Kandidaten stehen dort in bewusst **wegwerfbarer** Form: die Messung darf die
Abhängigkeit nicht vorwegnehmen, deren Anschaffung sie gerade erst begründen soll. Die Ausgabe
trägt Zahlen, keine Koordinaten; Namensbeispiele stehen in einem eigenen, abschaltbaren Abschnitt,
damit die Zahlen für sich weitergegeben werden können. Fällt die Messung dürftig aus, ist das ein
Ergebnis — die Wegwahl darf auch „gar nicht" lauten.

**Zwei Bedingungen, an denen ein Weg vor jeder Messung scheitern darf.** Die dauerhafte
Wiederverwendung der Auskunft ist ein Akzeptanzkriterium, kein Bequemlichkeitsmerkmal: ein
Anbieter, dessen Bedingungen das Zwischenspeichern der Antwort befristen oder untersagen, scheidet
aus — an seinen Bedingungen, nicht an seiner Technik. Ebenso scheidet aus, wessen Bedingungen
rasterförmige Abfragen untersagen; gefragt wird hier von Bauart wegen mit gerundeten Zellen.
Beides wird in der Wegwahl-ADR am Wortlaut belegt, nicht am Volumen abgeschätzt. Die
Namensnennungspflicht der gewählten Quelle wird sichtbar erfüllt.

## Konsequenzen

- Eine rein additive Migration: neue Tabelle `place_lookups`, neue nullable Spalte
  `events.place_name`. **Kein Nachziehen** bestehender Läufe, keine Datenlöschung.
- `project_deletion.py` bekommt `place_lookups` (Position aus `Base.metadata` gemessen, nicht
  geraten), und `tests/project_graph.py::build_project_graph` legt eine Zeile davon an — sonst
  prüfen die beiden Vollständigkeitstests die neue Kante nicht.
- Der Ortsname wird zur **zweiten** Quelle einer Event-Überschrift. `formatEventHeading` bekommt
  eine dritte Stufe zwischen Sehenswürdigkeit und Nummer; die Zeitspanne bleibt in jedem Fall.
- Die Sicherheitsauflage zu Standortdaten wird neu gestellt (`security-engineer`) und deckt den
  **Messlauf mit ab** — er ist der erste tatsächliche Datenabfluss, nicht bloß eine Vorstufe.
- `docs/architecture.md` zieht im selben Pull Request nach; `docs/setup.md` bekommt den Aufruf des
  Messkommandos und, falls die Wegwahl ihn braucht, den Bezug des lokalen Datensatzes.
- Die Wegwahl selbst wird nach der Messung als **eigene ADR** festgehalten, mit den gemessenen
  Zahlen als Begründung.
