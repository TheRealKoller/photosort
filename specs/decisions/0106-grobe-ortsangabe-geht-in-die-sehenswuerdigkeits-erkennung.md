# 0106 - Die grobe Ortsangabe geht in die Sehenswürdigkeits-Erkennung ein

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** ADR [`0025`](./0025-cloud-landmark-erkennung.md) Punkt 4 (dessen zweite Hälfte hier
fällt), ADR [`0102`](./0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md)
(Ortszelle und Stufenbegriff), ADR
[`0105`](./0105-ortsnamen-aus-dem-lokalen-datensatz-als-auszug-auf-einem-volume.md) (der lokale
Auflöser, dessen Auskunft hier erstmals nach außen wirkt), Spec
`specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md`

## Kontext

ADR 0025 Punkt 4 hat die Sehenswürdigkeits-Erkennung ausdrücklich auf Bildinhalt und
LLM-Weltwissen beschränkt: „Kein GPS-/EXIF-Zugriff … die Erkennung stützt sich ausschließlich auf
Bildinhalt". Das Ergebnis ist im Betrieb an einer echten Reise unzureichend — Fotos bekommen
erkennbar falsche Sehenswürdigkeiten zugeordnet, und weil der erkannte Name die Benennung der
Fotogruppen trägt, zerfällt eine Reise in mehr Gruppen, als sie Orte hatte.

Seit ADR 0102/0105 liegt zu einer vergröberten Ortszelle eine **lokal** aufgelöste Ortsauskunft
vor. Das Sicherheitskonzept hält dazu fest, dass dabei kein zweiter Empfänger von Ortsdaten
entsteht. **Genau das ändert diese Entscheidung**, und Daniel hat sie in Kenntnis dieser Folge
getroffen (Refinement zu Story #469, 2026-09-14).

## Entscheidung

### 1. Der Aufnahmeort geht als grobe Ortsangabe in die Erkennung ein

ADR 0025 Punkt 4 gilt in seiner ersten Hälfte unverändert weiter (Bildgrundlage bleibt die
`display`-Variante, nie das Original). Seine zweite Hälfte — kein Standortbezug in der Erkennung —
fällt. Die Ortsangabe geht in den Prompt desselben Aufrufs; es entsteht kein zusätzlicher Aufruf
und kein zusätzlicher Empfänger über den bereits eingewilligten Cloud-Vision-Anbieter hinaus.

### 2. Zwei Stufen, in dieser Reihenfolge, beide dauerhaft

1. **Ortsname**, wenn zur Zelle des Fotos einer aufgelöst ist — derselbe Name und dieselbe
   Stufenprüfung, die die Event-Benennung verwendet (`places.py::usable_locality`, also
   `matched_level` aus `neighbourhood`/`locality` und gesetztes `locality`). Es gibt keine zweite
   Fassung von „ein Ortsname gilt als aufgelöst".
2. **Grobe Koordinate**, sonst.
3. **Nichts**, wenn das Foto keine eigene Koordinate trägt.

Die Koordinatenstufe ist kein Übergangszustand bis zu einer besseren Namensauflösung. Sie greift
dauerhaft und bevorzugt dort, wo sich kein Ortsname auflösen lässt.

### 3. Was das System verlässt, ist nie feiner als eine Zelle von 1 Nachkommastelle

Die Koordinatenstufe rundet auf **1 Nachkommastelle** (rund 11 km in der Breite, weniger in der
Länge), über eine eigene Funktion neben `places.py::place_cell`. Das ist keine Anzeigerundung,
sondern die Grenze dessen, was dieses System an Ortsdaten der Familie herausgibt: eine
Größenordnung gröber als die in der Oberfläche gezeigte Zelle (2 Nachkommastellen, rund 1,1 km).

**Grund:** Die Stufe greift genau dort, wo kein Ortsname aufzulösen war — in dünn besiedelten
Gegenden, wo eine Koordinate mehr über die Familie verrät als in einer Stadt. Eine Zelle dieser
Größe benennt eine Landschaft, kein einzelnes Gehöft, und reicht dem Modell für seine Aufgabe:
welche Sehenswürdigkeit kommt hier überhaupt in Frage.

**Wer diesen Wert ändert, ändert eine Datenschutzentscheidung**, nicht eine Genauigkeit. Eine
Verfeinerung gibt mehr über jedes Foto ohne auflösbaren Ortsnamen preis und braucht eine eigene
ADR, keine stillschweigende Anpassung.

### 4. Nur die gemessene Koordinate des Fotos selbst

Eine über `events.py::infer_locations` **übernommene** Koordinate geht nie in die Erkennung ein.
Die Story spricht vom *bekannten* Aufnahmeort, und der Ort dient hier zugleich als Prüfmaßstab:
Passt er nicht zur erkannten Sehenswürdigkeit, wird der Treffer verworfen (Punkt 5). Eine
Schätzung in dieser Rolle verwürfe richtige Treffer für Fotos, die nie einen eigenen Ort hatten.
Das entspricht der bereits in `events.py` geltenden Trennung: eine Ortsaussage über eine Einheit
entsteht nicht aus Schätzungen.

Ein Foto ohne eigene Koordinate wird unverändert erkannt; das Fehlen ist kein Fehlerfall.

### 5. Die Prüfung „passt der Ort zur Sehenswürdigkeit" führt das Modell selbst

Der Ortsdatensatz dieses Projekts führt ausschließlich die GeoNames-Klassen `P` und `A` (Orte und
Verwaltungsebenen); Bauwerke und Berge fallen aus dem Auszug. Ein lokaler Abgleich „liegt diese
Sehenswürdigkeit an dieser Koordinate" ist damit im Bestand nicht möglich und wäre ein zweiter
Datensatz mit eigenem Bezugs-, Prüf- und Betriebsweg.

Stattdessen trägt der Prompt die Ortsangabe samt Auflage: Nennt das Modell eine Sehenswürdigkeit,
die nicht zu diesem Ort passt, gilt der Treffer als unsicher — er wird nicht genannt bzw. mit
niedriger Konfidenz gemeldet und fällt damit unter die Grenze aus ADR 0107.

### 6. In den Prompt geht ein sanitierter Ortsname oder ein Zahlenpaar, nie freier Text

Der Ortsname stammt aus einem von Dritten geschriebenen Datensatz und ist bereits am Schreibrand
durch `places.py::sanitize_place_name` gegangen (Zeichensanitisierung, Längengrenze 80, verworfen
statt abgeschnitten). Die Ortsangabe im Prompt besteht aus **genau** diesem einen Namen oder aus
den zwei gerundeten Zahlen — kein Viertel, keine Region, kein Land, kein zusammengesetzter
Anzeigename, keine weitere Zeichenkette aus der Datenbank. Andernfalls entstünde über den
Ortsdatensatz ein Einschleusungsweg in den Prompt.

**Kein Ortsname und keine Koordinate gehört je in eine Logzeile** — die Auflage aus `places.py`
gilt unverändert auch für den neuen Aufrufpfad, einschließlich der Fehlerbehandlung des
Cloud-Aufrufs.

## Konsequenzen

- Die Ortsauskunft wird im Lauf **früher** gebraucht als bisher: für die Zellen der
  Landmark-Kandidaten vor der Cloud-Phase, statt erst für die Zellen fertiger Events. Dieselbe
  Funktion, dieselbe Tabelle, derselbe Auflöser; die Event-Phase findet ihre Zellen danach
  überwiegend bereits abgelegt vor und baut dann gar keinen Auflöser mehr.
- **Die abgelegte Ortsspur wächst in der Zeilenzahl**, nicht in der Art: `place_lookups` trägt
  künftig die Zellen aller Landmark-Kandidaten eines Projekts, nicht nur die der Events ohne
  Sehenswürdigkeit. Es bleiben Zellen desselben Projekts unter derselben projektgebundenen
  Lebensdauer (ADR 0102).
- Das Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, Abschnitte „Standortdaten"
  und „Cloud-Vision-API", Owner `security-engineer`) braucht die Fortschreibung, dass Ortsdaten das
  System jetzt **doch** verlassen — in vergröberter Form, nur bei erteilter Einwilligung und
  laufbezogener Freigabe, an den bereits vorhandenen Empfänger. Der Satz „Ein zweiter Empfänger
  entsteht dabei nicht" bleibt wahr, der Satz über den vollständig internen Verbleib nicht.
- Die Datenschutz-Aussage in der Oberfläche wird sonst unwahr: `ClassificationSection.tsx` sagt
  heute „Dieser Durchlauf sendet Fotos an X". Sie muss die grobe Ortsangabe nennen, im selben Pull
  Request wie die Umsetzung.
- `docs/architecture.md` zieht im selben Pull Request nach. Keine neue Abhängigkeit, keine neue
  Umgebungsvariable, keine Migration aus dieser ADR.
