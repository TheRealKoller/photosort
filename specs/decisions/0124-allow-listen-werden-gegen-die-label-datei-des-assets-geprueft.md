# 0124 - Jede kuratierte Allow-Liste wird gegen die Label-Datei ihres Modell-Assets geprüft

**Status:** Accepted
**Datum:** 2026-09-25
**Bezug:** Spec 0283 (Gebäude-Erkennung: vier tote Einträge, überarbeitete Allow-Liste, AK4
„automatische Prüfung gegen die Modell-Labels" — Dateiname zum Zeitpunkt dieser ADR noch nicht
vergeben, deshalb ohne Verweis), Spec
[`0217`](../features/0217-landschaft-erkennung-spezifitaets-vorrang.md) (AK-Teil „Schreibweise
gegen die Label-Liste verifizieren" — hier von einer Kommentar-Zusage zu einer geprüften Zusage
hochgestuft), [`0002-testkonzept.md`](../architecture/0002-testkonzept.md), ADR
[`0022`](./0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md)

## Kontext

Fünf kuratierte Allow-Listen filtern Modellausgaben auf inhaltlich zugelassene Klassen:
`ARCHITECTURE_CATEGORIES` und `LANDSCAPE_SCENE_CATEGORIES` gegen die 1000 ImageNet-1k-Klassen von
`efficientnet_lite0.tflite`, `VEHICLE_CATEGORIES`, `FOOD_CATEGORIES` und `ANIMAL_CATEGORIES` gegen
die 80 COCO-Klassen von `efficientdet_lite0.tflite` (die ersten vier in `criteria.py`,
`ANIMAL_CATEGORIES` in `classification.py` definiert). Die Auswahl ist eine reine Mengenzugehörigkeit
(`label.category in ALLOW_LISTE`): Ein Eintrag, den das Modell nie ausgibt, ist kein harmloser
Ballast, sondern eine stumme Lücke — die zugelassene Bauwerksart wird nie erkannt, und nichts
meldet das.

Genau dieser Fall lag vor. Vier Einträge von sechzehn in `ARCHITECTURE_CATEGORIES` entsprachen
keiner vom Modell gelieferten Bezeichnung: drei in falscher Schreibweise (`bell_cote`,
`triumphal_arch`, `suspension_bridge` statt mit Leerzeichen), einer unter fremdem Klassennamen
(`lighthouse` statt `beacon`). Der Kommentar über der Liste benannte die Klassen der Label-Datei
korrekt und hielt den Befund fest — die Liste selbst blieb unverändert, weil eine Korrektur eine
Verhaltensänderung ist und einer eigenen Story bedurfte (Spec 0283).

Die geltende Konvention (Spec 0217: „die exakte Schreibweise ist einmalig gegen die Label-Liste
zu verifizieren und im Code-Kommentar festzuhalten — kein modellladender Test") erklärt, warum
der Befund vier Jahre (Projektzeit) überlebte: Eine Verifikation ohne Test ist eine einmalige
Handlung. Sie hält den Zustand zum Zeitpunkt ihrer Ausführung fest, nicht gegen die nächste
Änderung. Zwei Beobachtungen belegen das — `criteria.py` nennt als Label-Datei des
Objekt-Detektors `labelmap.txt`, tatsächlich heißt sie `labels.txt`; und vier Einträge einer
Liste, deren Schreibweise ausdrücklich verifiziert sein sollte, waren falsch.

## Entscheidung

### 1. Die Label-Datei wird ohne Modell-Laden gelesen, und das ist keine Aufweichung der Konvention

Eine `.tflite`-Datei trägt ihre Metadaten als angehängtes ZIP-Archiv. `zipfile` aus der
Standardbibliothek liest `labels_without_background.txt` (bzw. `labels.txt`) daraus, ohne
`mediapipe`, ohne TensorFlow, ohne Inferenz, ohne das Modell zu instanziieren. Verifiziert:
`zipfile.ZipFile("efficientnet_lite0.tflite").read("labels_without_background.txt")` liefert 1000
Zeilen, die Objekt-Detektor-Datei entsprechend 90.

Die Konvention „kein modellladender Test" zielt auf das **Laden und Ausführen des Modells** —
Inferenz im Test ist langsam, speicherhungrig und in einem Testlauf ohne Bildmaterial
bedeutungslos. Das **Lesen der mitgelieferten Label-Datei** ist keiner dieser Fälle: ein
Dateizugriff auf ein bereits eingechecktes Asset, Größenordnung Millisekunden, dieselbe
Größenklasse wie der bestehende SHA-256-Integritätstest in
`backend/tests/test_classification.py`, der dieselbe Datei bereits liest. Die Konvention wird
damit nicht abgelöst, sondern präzisiert: Sie verbietet das Modell im Test, nicht das Asset.

### 2. Geprüft wird jede Eintragung jeder der fünf kuratierten Allow-Listen, und der Dateiname kommt aus dem Asset

Die Zusicherung lautet, **je Allow-Liste und je Modell-Asset**:

> Jeder Eintrag der Liste steht in der Label-Datei des Assets, gegen das die Liste filtert. Gilt
> für `ARCHITECTURE_CATEGORIES`, `LANDSCAPE_SCENE_CATEGORIES` (beide
> `efficientnet_lite0.tflite`) und `VEHICLE_CATEGORIES`, `FOOD_CATEGORIES`, `ANIMAL_CATEGORIES`
> (alle drei `efficientdet_lite0.tflite`) — jede künftige kuratierte Liste gegen ein Modell-Asset
> tritt hinzu. Bei Verletzung schlägt der Test fehl und nennt Liste, Eintrag und Asset.

Die fünf Listen liegen über **zwei** Modulpfade: vier in `photosort/criteria.py`, `ANIMAL_CATEGORIES`
in `photosort/classification.py` (dort definiert, in `criteria.py::animal_detections` und
`compute_tier_score` gefiltert). Der Test sammelt sie deshalb über beide Module, nicht über eines.

Die Richtung ist **Liste ⊆ Label-Datei**, nicht Gleichheit: Die Liste ist kuratiert und darf eine
echte Teilmenge bleiben. Geprüft wird allein, dass kein Eintrag ins Leere läuft.

Der Dateiname der Label-Datei wird aus dem ZIP-Inventar des Assets ermittelt, nicht im Test
hartkodiert. Ein hartkodierter Name wäre derselbe Fehler eine Ebene tiefer — er liefe bei
ausgetauschtem Asset ins Leere, und der Test wäre grün, ohne etwas über die Liste zu sagen.

**Warum alle fünf und nicht nur die Gebäude-Liste:** Die Fehlerklasse ist listenunabhängig, die
Ursache (eine von Hand gepflegte Schreibweise gegen eine maschinengenerierte Wortliste) ist bei
allen fünf dieselbe, und der Test ist eine Funktion über (Liste, Asset) — je weitere Liste eine
Zeile Aufruf, kein zweiter Bau. Das gilt auch für `ANIMAL_CATEGORIES`, die einzige Liste in einem
zweiten Modul: ihre zehn Klassennamen (`bird`, `cat`, `dog`, `horse`, `sheep`, `cow`, `elephant`,
`bear`, `zebra`, `giraffe`) sind ebenso von Hand gegen die maschinengenerierte `labels.txt` des
Objekt-Detektors geschrieben, und ein Schreibfehler darin ließe das `tier`-Kriterium stumm auf 0.0
fallen, ohne dass eine Ausnahme oder ein fehlschlagender Test das meldete. Die Beschränkung auf
`ARCHITECTURE_CATEGORIES` ließe vier Listen
mit identischem, belegtem Risiko ungeprüft; `LANDSCAPE_SCENE_CATEGORIES`, `VEHICLE_CATEGORIES`,
`FOOD_CATEGORIES` und `ANIMAL_CATEGORIES` waren zum Zeitpunkt dieser Entscheidung fehlerfrei, aber
nichts hielt das fest. Das ist eine Ausweitung der
**Prüfung**, nicht eine des Verhaltens: Kein Score ändert sich dadurch, keine Liste wird
inhaltlich angefasst.

### 3. Der Modell-SHA-Pin bleibt die zweite Hälfte

Der bestehende Integritätstest je Asset (`SCENE_CLASSIFIER_MODEL_SHA256` u.a.) bleibt
unverändert. Beide Tests zusammen decken die Lücke vollständig: Der eine stellt sicher, dass die
Datei die geprüfte ist, der andere, dass die Liste zu ihren Labels passt. Fällt einer, ist die
Grundlage der Erkennung eine andere als angenommen.

### 4. Keine Ausdehnung auf andere Behauptungen über Listeninhalte

Nicht geprüft werden: die Vollständigkeit der Liste (die kuratierte Auswahl ist der Zweck der
Liste), die Index-Behauptung zu `LANDSCAPE_SCENE_CATEGORIES` (Positionen 970/972-980) und die
inhaltliche Erkennungsgüte an echten Fotos. Die beiden letzteren sind mit demselben Verfahren
prüfbar und bewusst nicht Teil dieser Entscheidung — sie wären eine eigene Aussage mit eigener
Begründung. Was hier festgelegt ist, ist genau eine Regel: kein Listeneintrag läuft ins Leere.
