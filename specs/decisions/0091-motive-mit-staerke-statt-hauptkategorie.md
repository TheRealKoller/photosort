# 0091 - Motive mit Stärke statt einer Hauptkategorie: acht Motive, ein Stärkevektor je Foto, die Korrektur als eigene Aussage

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** Spec `specs/features/0427-*.md`, ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (das Event als
Partition, hier die verbleibende), ADR
[`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md) (Auswahl ohne
Backfill, hier im Partitionsschlüssel berührt), ADR
[`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md) (Erreichbarkeit entlang
der Fremdschlüsselkanten — die drei neuen Tabellen hängen darin)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung acht Punkte trägt und
drei ADRs ablöst, deren weitergeltende Anteile in der Statuszeile aufzuschlüsseln sind.

**Löst ab (Superseded):**

- [`0049`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) — das feste
  Kategorien-Set mit deterministischer Vorrangreihenfolge ist der Kern jener Entscheidung und
  entfällt vollständig. Weiter gelten, hier übernommen: der Prompt entsteht ausschließlich aus der
  Registry und nie aus einem Literal, aus Datenbankinhalten oder aus einer früheren Modellantwort
  (Abschnitt 1/5); das Antwortschema ist geschlossen und zweistufig validiert (Abschnitt 5); die
  Feinlabels samt kanonischer Registry und Ähnlichkeitsauflösung sind unberührt (Abschnitt 6); die
  Eingabevalidierung prüft gegen ein geschlossenes Vokabular statt gegen eine foto-skopierte Menge
  (Abschnitt 8); das Frontend spiegelt das Set nicht, sondern lädt es (Abschnitt 9).
- [`0067`](./0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md) — die tragende Grenze
  jener Entscheidung („die Zahl des Modells berührt die Auswahl nicht") ist bewusst aufgegeben: die
  Zahl **ist** ab hier die Auswahlgrundlage. Weiter gilt, hier übernommen: die Zahl hängt am
  Schlüssel und nicht an einer Position oder an der Herkunft (Punkt 2), und die Auswertung läuft in
  SQL statt über einen JSON-Zugriff, den SQLite und PostgreSQL unterschiedlich schreiben (Punkt 4).
  Punkt 3 („kein Wert wird erfunden", Neutralwert `None`, nie `0.0`) fällt mit Punkt 5 dieser ADR.
- [`0069`](./0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) — es
  gibt keine Haupt- und keine Nebenkategorie mehr, die zu unterscheiden wären; `is_primary`, die
  Konfidenzschwelle `SECONDARY_CATEGORY_MIN_CONFIDENCE` und die konfidenzgewichtete Dämpfung des
  Sortierschlüssels (`CONFIDENCE_RANK_PENALTY`) entfallen. Weiter gilt, hier übernommen: eine
  Mehrfachaussage über ein Foto gehört in persistierte Zeilen und nicht in eine zur Lesezeit
  expandierte JSON-Struktur (Punkt 1).

## Kontext

Die Kategorie eines Fotos entsteht heute aus einer Rangliste: `resolve_category` reduziert alle in
Frage kommenden Motive auf das mit der kleinsten `precedence`, unabhängig davon, wie deutlich das
Modell sie gesehen hat. Ein Gesicht im Hintergrund gewinnt gegen eine klar erkannte Kathedrale.
Eine Messung an 20 Fehlzuordnungen zeigt die Ursache: die richtige Kategorie stand jedes Mal in der
Kandidatenliste des Modells, nur die Auflösung traf in der Hälfte der Fälle die falsche. Das Modell
ist nicht die Fehlerquelle, der Mechanismus ist es — ein Foto zeigt mehreres zugleich, und die
Reduktion auf ein Element wirft genau die Information weg, die die Albumauswahl braucht.

## Entscheidung

### 1. Acht Motive in einem eigenen reinen Modul; Set, Vorrangreihenfolge und Auffangwert entfallen

Neues Modul `backend/src/photosort/motifs.py`, dieselbe Reinheitsauflage wie `categories.py`: keine
DB-, Netzwerk- oder Bildverarbeitungs-Abhängigkeit, Kriterien-Keys nur als Strings, Konsistenz mit
`criteria.py` per Invariantentest statt per Import. `categories.py` entfällt vollständig, mit ihm
`CATEGORY_REGISTRY`, `precedence`, `resolve_category`, `secondary_categories`,
`CATEGORY_NOT_RECOGNIZED` und `SECONDARY_CATEGORY_MIN_CONFIDENCE`.

`MOTIF_REGISTRY` trägt genau acht Einträge in Anzeigereihenfolge, je mit `key`, `display_name`,
`definition` und `delimitation` — dieselbe Doppelrolle wie bisher (Prompt-Grundlage **und**
UI-Erklärung, eine Quelle): `menschen`, `landschaft`, `bauwerk_sehenswuerdigkeit`, `stadt_strasse`,
`tiere`, `essen_trinken`, `aktivitaet`, `detail_stimmung`. Ein `precedence`-Attribut gibt es nicht
und darf nicht wieder entstehen; ein Invariantentest hält fest, dass die Registry keine Ordnung
kennt, die eine Auswahl tragen könnte.

Jede bisherige Kategorie hat eine benannte Entsprechung oder fällt begründet weg:
`menschen`→`menschen`, `tier`→`tiere`, `landschaft`→`landschaft`,
`gebaeude_bauwerk`→`bauwerk_sehenswuerdigkeit`, `essen_trinken`→`essen_trinken`,
`sport_aktivitaet`→`aktivitaet`, `fahrzeug`→`stadt_strasse` (ein Fahrzeug ist Teil der Straßenszene,
kein eigenes Motiv), `pflanze`/`gegenstand`/`kunst_kreatives`→`detail_stimmung`,
`innenraum` entfällt (ein Innenraum ist ein Aufnahmeort, kein Motiv — das Foto trägt die Motive
dessen, was darin zu sehen ist), `nicht_erkannt` entfällt (kein erkennbares Motiv heißt durchgehend
niedrige Stärken, keine Auffangkategorie), `dokument_screenshot` entfällt als Motiv und wird
Ausschluss-Signal (Punkt 2).

Eine erkannte Sehenswürdigkeit bleibt kein eigenes Motiv: sie verstärkt
`bauwerk_sehenswuerdigkeit` (Punkt 4), und `PhotoLandmarkDetection` bleibt unberührt die Quelle des
Namens für die Benennung eines Events.

### 2. Der Stärkevektor ist eine persistierte Zeilenmenge; die Kopfzeile trägt Grundlage und Ausschluss

Zwei neue Tabellen statt einer JSON-Spalte:

- `photo_motif_assessments` — 1:1 zu `Photo` (`photo_id` als Primary Key und Fremdschlüssel).
  `source` (`cloud` | `local`, `SQLEnum(native_enum=False)`), `excluded_document: bool` (NOT NULL,
  **ohne jeden Default**, damit ein Schreibpfad, der die Spalte vergisst, laut scheitert statt still
  ein Foto auszuschließen), `provider: str | None` (`NULL` für eine lokale Grundlage),
  `computed_at`. Die **Abwesenheit** dieser Zeile ist der Zustand „noch nicht klassifiziert" und
  damit unterscheidbar von „nichts erkannt" (Vektor vorhanden, Stärken niedrig). Diese Zeile ist
  zugleich das Skip-Kriterium des Cloud-Teilschritts und die Erfolgs-Ableitung seines Status — die
  Rolle, die bisher `photo_category_classifications` trug.
- `photo_motif_strengths` — 1:N, Fremdschlüssel auf `photo_motif_assessments.photo_id`,
  `UniqueConstraint(photo_id, motif_key)`, `strength: float` in `[0, 1]`. Eine Stärke kann ohne
  Kopfzeile nicht existieren, und eine neue Grundlage ersetzt den gesamten Vektor eines Fotos.

**Verworfen: eine JSON-Abbildung `motif_key -> Stärke`.** Die Albumauswahl-Story wird je Motiv
sortieren und schwellen; eine JSON-Struktur zu Zeilen zu expandieren ist in SQLite und PostgreSQL
unterschiedlich zu schreiben — dieselbe Portabilitätsfalle, die ADR 0067 Punkt 4 bereits eine
redundante Spalte gekostet hat, und ADR 0069 Punkt 1 hat für dieselbe Frage bereits gegen JSON
entschieden.

`excluded_document` ist ein Wahrheitswert und keine Stärke mit Schwelle: das Modell beantwortet
„ist dieses Foto eine Text-/Bildschirm-/Dokumentabbildung" selbst, und der Lesepfad schließt ein so
markiertes Foto aus jeder Motivauswahl aus. Eine Stärke mit Grenzwert hätte genau die feste
Schwelle wieder eingeführt, die diese Entscheidung abschafft.

### 3. Genau eine Grundlage je Foto: die Modellaussage schlägt die lokale Erkennung, es wird nie gemischt

`source` unterscheidet die beiden Grundlagen, und sie treten nie gegeneinander an. Liegt eine
Cloud-Aussage vor, bestimmt allein sie alle acht Stärken; die lokale Erkennung liefert keinen
Gegenkandidaten und keinen Ergänzungswert. Genau das gemeinsame Einwerfen lokaler und remoter
Kandidaten in **eine** Menge (ADR 0049 Abschnitt 3) hat die nachgewiesenen Fehlzuordnungen mit
erzeugt: zwei Signale unterschiedlicher Skala im selben Topf.

Im Schreibpfad heißt das: der Cloud-Teilschritt schreibt bzw. ersetzt die Kopfzeile immer und setzt
`source='cloud'`. Der Kriterien-Lauf schreibt eine lokale Kopfzeile **nur**, wenn für das Foto keine
Zeile existiert oder die vorhandene `source='local'` trägt — eine Cloud-Grundlage wird nie von einem
lokalen Lauf überschrieben. Die Reihenfolge im verketteten Lauf (Cloud-Teilschritt vor
Kriterien-Bewertung, ADR 0068) macht das ohne Zusatzzustand richtig.

### 4. Lokale Stärke: Flächenanteil für Objekt-Erkennungen, Ganzbild-Konfidenz für Szenen-Signale

`LOCAL_MOTIF_SIGNALS` in `motifs.py` bildet die bereits berechneten lokalen Signale auf Motive ab,
mit zwei unterschiedlichen Arten, und die Art folgt der Messung statt einer Konvention:

- **Flächengewichtet** (`kind="area"`): ein erkanntes Objekt wirkt nach seinem Anteil am Bild, nicht
  nach seiner Anwesenheit. Die Stärke ist `min(1, Summe der Flächenanteile / Sättigungsanteil)` über
  die Bounding-Boxen der jeweiligen Allow-Liste — `menschen` aus den Gesichts-Boxen, `tiere`,
  `essen_trinken` und `stadt_strasse` aus der einen COCO-Detektorausgabe. Summiert, nicht das
  Maximum: fünf kleine Personen sind ein Personenbild. Überlappende Boxen zählen dabei doppelt; das
  Ergebnis ist geklemmt, der Effekt bewusst hingenommen.
- **Ganzbild-Konfidenz** (`kind="scene"`): `landschaft` und `bauwerk_sehenswuerdigkeit` stammen aus
  der Szenen-Klassifikation, die keine Boxen liefert. Ihre Konfidenz ist bereits eine Aussage über
  das ganze Bild; eine Flächengewichtung gibt es dort nicht zu berechnen.
  `bauwerk_sehenswuerdigkeit` ist `max(Szenen-Konfidenz, Sehenswürdigkeits-Konfidenz)` — so
  verstärkt eine erkannte Sehenswürdigkeit das Motiv, ohne eine erfundene Summe zu bilden.
- `aktivitaet` und `detail_stimmung` sind lokal nicht beurteilbar und bleiben bei `0` — die bewusst
  akzeptierte Grenze der lokalen Grundlage, nicht ein Fehlerfall.

Die Sättigungsanteile sind dokumentiert-unkalibrierte Startwerte derselben Klasse wie
`SHARPNESS_NORMALIZATION_CEILING`: es gibt keinen Fotokorpus im Repository, gegen den sie kalibriert
werden könnten. Sie stehen ausschließlich in dieser Registry, nie zusätzlich im Worker.

Die Berechnung liegt im Kriterien-Lauf, wo die Detektionen samt Boxen ohnehin vorliegen — kein
zweiter Detektoraufruf, keine neue Kriterien-Spalte. Die Boxen selbst werden nicht persistiert; die
Stärke ist das Ergebnis, das die Anwendung braucht.

### 5. Die Korrektur ist eine eigene Aussage, die jeden Lauf überlebt; die wirksame Stärke entsteht im Lesepfad

Dritte neue Tabelle `photo_motif_corrections`: `photo_id` (Fremdschlüssel auf `photos`, Kaskade),
`user_id`, `motif_key`, `applies: bool`, `updated_at`, `UniqueConstraint(photo_id, motif_key)`.
Nicht am Lauf und nicht an der Kopfzeile — deshalb überlebt sie jede erneute Klassifizierung ohne
Sonderfallcode. Eine fehlende Zeile heißt „nicht korrigiert" (dasselbe Muster wie bei `Rating`), das
Entfernen einer Korrektur ist das Löschen der Zeile. `user_id` hält fest, wer zuletzt korrigiert
hat; die Korrektur selbst ist eine Aussage über das **Foto** und nicht über einen Geschmack, deshalb
steht der Nutzer nicht im Unique-Constraint. Der Schlüsselraum sind **ausschließlich die acht
Motive**; `dokument_screenshot` ist nicht korrigierbar, und ein fälschlich ausgeschlossenes Foto
kommt allein über einen erneuten Klassifizierungslauf zurück. Geprüft wird der Schlüssel gegen
`is_motif_key` — es gibt keine zweite, weitere Schlüsselmenge für Korrekturen.

Eine Korrektur trägt nie eine Zahl. Die **wirksame** Stärke entsteht im Lesepfad: `applies=true`
ergibt `1.0`, `applies=false` ergibt `0.0`, keine Zeile ergibt die Stärke der Grundlage. Sie wird
**nicht** in die Stärkezeile materialisiert — eine materialisierte Korrektur müsste nach jedem Lauf
erneut angewendet werden, und genau dieses Nachziehen ist die Stelle, an der sie verloren geht. Der
Ausdruck lebt an **einer** Stelle (`motif_strengths.py`, DB-nah, neben dem reinen `motifs.py`) und
wird von jedem lesenden Pfad von dort bezogen; ein Wächtertest hält fest, dass keine zweite Fassung
desselben `CASE` entsteht.

Eine fehlende Stärke in einer Cloud-Aussage ist `0.0` und nicht „keine Angabe" — das ist die
bewusste Abkehr von ADR 0067 Punkt 3. Der Prompt verlangt alle acht Zahlen; ein nicht genanntes
Motiv ist damit die Aussage „nicht zu sehen", nicht ein fehlender Wert. Der Vektor ist vollständig
oder er existiert nicht (Punkt 2), ein halb gefüllter Zwischenzustand gibt es nicht.

### 6. Die Rangfolge-Partition verliert die Kategorie-Dimension

`photo_rankings` verliert `category_key` und `is_primary`; der Unique-Constraint geht von
`(criterion_scoring_run_id, photo_id, category_key)` zurück auf
`(criterion_scoring_run_id, photo_id)`. Die Partition ist damit allein das Event (ADR 0087), und ein
Foto steht pro Lauf wieder in genau einer Zeile. Der Sortierschlüssel ist wieder der reine
`rank_score`; die konfidenzgewichtete Dämpfung entfällt, weil es die Partition nicht mehr gibt,
innerhalb derer sie verglich.

Der manuelle Kategorie-Override (`photo_scores.category_override`,
`PUT`/`DELETE /photos/{id}/category-override`, `worker.py::reassign_photo_category`) entfällt
ersatzlos: „das Foto umhängen" ist keine Handlung mehr, die das Datenmodell kennt. Seine Aufgabe
übernimmt die Motivkorrektur aus Punkt 5, und sie braucht dafür keinen Schreibzugriff auf die
Rangfolge und keine Sperre — der Grund, aus dem `reassign_photo_category` mit `with_for_update()`
arbeiten musste, fällt mit ihr weg. Ebenso entfällt `category_diff.py`: es vergleicht die
Kategoriezuordnung zweier Läufe und hat nach dieser Umstellung keinen Gegenstand mehr.

### 7. Kein Backfill, kein ungefragter Cloud-Lauf, und die alten Kategoriedaten fallen

Bestandsfotos erhalten Stärken erst bei einem Lauf, den der Nutzer selbst auslöst — es gibt keine
Migration, die Stärken aus `detected_category_confidences` ableitet. Eine solche Ableitung wäre eine
Modellaussage, die das Modell nie getroffen hat, und ein automatischer Lauf wären ungefragte
Cloud-Kosten. Bis dahin fehlt die Kopfzeile, und genau das zeigt die Oberfläche als „noch nicht
klassifiziert" statt als „nichts erkannt".

`photo_category_classifications` wird gelöscht, ebenso `photo_scores.category_override` und die
beiden Rangfolge-Spalten aus Punkt 6. Eine Tabelle ohne Leser stehen zu lassen, verschiebt nur die
Frage, was sie bedeutet, auf die nächste Änderung. Die Feinlabels (`fine_labels`,
`photo_fine_labels`), die Sehenswürdigkeits-Zeilen und die Lauf-/Kostentabellen bleiben unberührt;
der Cloud-Aufruf liefert die Feinlabels unverändert mit.

Der Rückwärtsweg jeder dieser Migrationen stellt die Struktur wieder her, nie die Daten — und die
Löschung der Nebenzeilen (`WHERE is_primary = false`) muss dem Constraint-Tausch in Punkt 6
vorausgehen, sonst ist der Weg an einer echten Datenbank nicht ausführbar.

### 8. Stärkebänder sind eine Anzeigekonvention der Statistik, nie eine Zugehörigkeitsschwelle

Die Statistik weist je Motiv drei Zahlen aus (stark / mittel / schwach) plus den Mittelwert der
Stärke. Die beiden Bandgrenzen (`2/3`, `1/3`) stehen in `motifs.py`, gehen in die Antwort ein (das
Frontend spiegelt sie nicht) und sind ausdrücklich **keine** Auswahlschwelle: kein Codepfad, der
über Zugehörigkeit oder Auswahl entscheidet, liest sie. Ein reines „Stärke > 0" wäre keine Auskunft
— ein Achter-Vektor aus einer Modellantwort trägt fast überall eine kleine Zahl, und acht nahezu
gleiche Zahlen sind keine Verteilung.

Da ein Foto zu mehreren Motiven zählt, ergibt die Summe über alle Motive nicht die Anzahl der
Fotos. Diese Zählweise steht als Erklärung in der Oberfläche, nicht nur in dieser ADR. Dazu tritt
die Anzahl der Fotos **ohne** Kopfzeile als eigene Zahl — sie fehlen in jeder Motivzahl, und ohne
diesen Ausweis sähe der Bestand kleiner aus, als er ist.

## Konsequenzen

- Die Auswahl eines Fotos hängt ab hier an einer Modellzahl. Das ist die bewusste Umkehr von ADR
  0067 Punkt 1 und nur tragbar, weil die Zahl je Motiv verglichen wird und nie zwischen zwei
  Motiven: es gibt keine zweite Skala mehr im selben Vergleich.
- Ohne Cloud-Aussage sind zwei der acht Motive strukturell nicht erreichbar. Die Grundlage steht
  deshalb an jeder Ausgabe, statt sie aus der Stärke erraten zu müssen.
- Ob die Stärkewerte des Modells gegen eine Referenz nachjustiert werden müssen, ist hier **nicht**
  entschieden und lässt sich erst beurteilen, wenn Korrekturen vorliegen. Ebenso offen bleibt die
  Wahl eines spezialisierten Modells für die Motiv-Erkennung.
- Wie die Albumauswahl die Motivmischung nutzt und wie die Korrekturen auf die Bewertung
  zurückwirken, bleibt jeweils einer eigenen Entscheidung überlassen. Diese ADR legt dafür die
  Datengrundlage fest und keine Auswahlregel.
