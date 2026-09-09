# 0067 - Modellkonfidenz je Kategorie: persistiert, angezeigt, ausgewertet — und ohne jeden Einfluss auf die Kategorieauswahl

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [GitHub-Issue #299](https://github.com/TheRealKoller/photosort/issues/299), [`features/0299-kategorie-konfidenz-anzeigen.md`](../features/0299-kategorie-konfidenz-anzeigen.md), `architect`-Konsultation für Story #299 am 2026-09-09.

**Löst teilweise ab:** [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) — dort **Abschnitt 5, dritter Aufzählungspunkt** („**Konfidenzen entfallen ersatzlos**") und der Halbsatz in **Abschnitt 8** („`score` entfällt dort ersatzlos … für lokale Kandidaten allein wäre die Spalte irreführend halb gefüllt"). Alles Übrige von ADR 0049 bleibt unverändert in Kraft — insbesondere das feste Set samt Vorrangreihenfolge (Abschnitte 1/2), der gemeinsame Kandidatenpool aus lokalen und remoten Signalen (Abschnitt 3), die lokal bestimmbare Teilmenge (Abschnitt 4), die zweistufige Validierung der Modellantwort (Abschnitt 5 im Übrigen), die Feinlabel-Registry (Abschnitt 6) und die Override-Validierung gegen das geschlossene Vokabular (Abschnitt 8 im Übrigen). Deshalb trägt ADR 0049 den Vermerk **Teilweise abgelöst** und bleibt `Accepted`; die Abstufung ist in [`../README.md`](../README.md) beschrieben.

## Kontext

ADR 0049 hat die Konfidenzen der Remote-Klassifizierung mit einer Begründung gestrichen, die zum damaligen Zeitpunkt zutraf und in ihrer Form weiterhin gilt: *„Eine Zahl zu persistieren, die keinen Codepfad mehr beeinflusst, wäre irreführender Ballast."* Die Konfidenz war bis dahin ausschließlich Rechengröße der häufigkeits-/score-basierten Kategorieauswahl (ADR 0023/0032); mit deren Abschaffung verlor sie ihren einzigen Verwender. Die Streichung war damit keine Aussage über den Wert der Information, sondern über ihre damalige Verwendungslosigkeit.

Story #299 schafft genau diese fehlende Verwendung, und zwar drei davon: die Zahl macht wacklige Zuordnungen beim Kuratieren gezielt auffindbar, erklärt am einzelnen Foto, wie die Kategorie zustande kam, und erlaubt über alle Fotos hinweg eine Einschätzung der Erkennungsqualität. Damit ist die Voraussetzung der damaligen Streichung entfallen — nicht ihre Logik. Der Ballast-Einwand kehrt sich sogar um: Die Selbsteinschätzung des Modells existiert im Moment der API-Antwort ohnehin; sie nicht festzuhalten heißt, sie unwiederbringlich wegzuwerfen, denn ein zweiter Blick auf dasselbe Foto kostet einen weiteren kostenpflichtigen Cloud-Aufruf.

Zwei Vorgeschichten begrenzen, was hier entschieden werden darf:

- **ADR 0047** (Landschafts-Vorrang): Der Ansatz „höchster Wert gewinnt" ist im Produkt bereits **nachweislich gescheitert** — Werte unterschiedlicher Skalen wurden verglichen, und die unspezifischere Zahl gewann regelmäßig. ADR 0049 hat daraus die feste Vorrangreihenfolge gemacht.
- Die alte, mit Spec 0289 entfernte Spalte `photo_fine_labels.confidence` (Migration `d5e6f7a8b9c0`) war eine Konfidenz **je freiem Feinlabel**, nicht je Kategorie. Sie kommt hier nicht zurück; es gibt nichts zu revertieren, das alte Schema passt auf den neuen Bedarf nicht.

## Entscheidung

### 1. Die Konfidenz ist Anzeige- und Auswertungsinformation. Sie berührt die Kategorieauswahl nicht.

`categories.py::resolve_category` bleibt **unverändert** eine reine Funktion über der Kandidatenmenge, die allein `precedence` auswertet. Sie bekommt keinen Konfidenz-Parameter, keine Schwelle, keine Tie-Break-Regel. Kein Codepfad, der eine Kategorie *bestimmt*, liest die neuen Felder — sie werden ausschließlich gelesen von der API-Ausgabe (`PhotoOut`), der Statistik-Aggregation und dem Frontend.

Das ist die tragende Grenze dieser ADR, nicht eine Vorsichtsformel: Genau die Vermischung von „wie sicher war das Modell" mit „welche Kategorie gilt" hat ADR 0047 als Fehlschlag dokumentiert. Die Zahl, die das Modell nennt, ist außerdem gar nicht auf einer Skala mit den lokalen Kriterienwerten vergleichbar — der Vergleich, an dem der frühere Ansatz scheiterte, wäre hier derselbe.

Ein Invariantentest hält diese Grenze: `resolve_category` hat weiterhin genau einen Parameter, und die Kategorie eines Fotos ist unabhängig von jeder Konfidenz reproduzierbar.

### 2. Die Konfidenz gehört an den Schlüssel, nicht an die Herkunft

Persistiert wird eine Abbildung `category_key -> Konfidenz`, kein positionsparalleles Array und keine Liste von Paaren. Damit ist der Wert ohne Reihenfolgenannahme genau dem Kandidaten zugeordnet, zu dem er gehört, und die Zuordnung überlebt jede spätere Umsortierung der Kandidatenliste.

Daraus folgt unmittelbar der Umgang mit dem Fall, den ADR 0049 Abschnitt 8 als „irreführend halb gefüllte Spalte" abgelehnt hatte: **Die Zahl folgt dem Schlüssel, nicht der `origin`-Kennzeichnung.** Ein Kandidat, den nur ein lokales Signal beigesteuert hat, hat keine Zahl — dort steht nichts, nicht `0 %`. Ein Kandidat, den das Modell **auch** genannt hat, zeigt die Modellzahl, selbst wenn `_category_candidates_out` ihn als `origin="local"` ausweist (die lokale Herkunft ist die spezifischere Herkunftsaussage, die Modellzahl bleibt trotzdem eine gültige Modellaussage über denselben Schlüssel).

Die halb gefüllte Spalte ist damit kein Versehen, sondern die Aussage selbst: Sie zeigt, welche Kandidaten überhaupt aus einer Modellaussage stammen. Was ADR 0049 zu Recht ablehnte, war eine Spalte ohne Verwender — nicht eine Spalte mit Lücken.

### 3. Kein Wert wird erfunden, keiner wird zurechtgebogen

Drei Fälle, drei Male dasselbe Ergebnis „keine Zahl":

- **Altbestand.** Zeilen, die vor der Migration geschrieben wurden, tragen `NULL`. `NULL` heißt „nicht erhoben", `0.0` hieße „das Modell war sich zu 0 % sicher" — dieselbe Unterscheidung, die ADR [`0051`](./0051-ist-kostenerfassung-remote-laeufe.md) für die Ist-Kosten getroffen hat, und aus demselben Grund: kein `server_default`, keine Backfill-Schätzung.
- **Keine Modellaussage.** Nennt das Modell zu einer Kategorie keine Konfidenz, bleibt die Kategorie gültig und die Zahl fehlt.
- **Unplausible Modellaussage.** Ein Wert, der kein echter Zahlenwert ist oder außerhalb von `[0, 1]` liegt, wird **verworfen**, nicht geklemmt. Das weicht bewusst von `landmark.py::_landmark_detection_from_json` ab, das auf `[0, 1]` klemmt: Dort ist die Konfidenz ein Nebenwert einer einzelnen Erkennung; hier würde `1.4 -> 1.0` aus einer kaputten Antwort ausgerechnet die Aussage „100 % sicher" erzeugen — die stärkste Aussage, die das Produkt kennt, erfunden aus dem schwächsten Datum. Verwerfen ist die einzige Lesart, die nichts behauptet.

Ein verworfener Wert wird einmal je Vorkommen auf `WARNING` protokolliert, nach dem bestehenden Muster aus ADR [`0034`](./0034-strukturiertes-logging-cloud-vision-fehler.md) (`photo_id` + längenbegrenzter `%r`-Rohwert, nie die vollständige Antwort, nie Bilddaten, nie der Key) — ein systematisch danebenliegendes Modell soll auffallen, ohne dass der Lauf scheitert. Die Best-effort-Semantik der Klassifizierung bleibt unangetastet: Die Konfidenz ist **nie** ein Grund, ein Foto zu überspringen.

### 4. Zwei Spalten statt einer: die Abbildung für die Anzeige, ein Skalar für die Auswertung

`photo_category_classifications` bekommt beides:

- `detected_category_confidences` (JSON, nullable) — die Abbildung aus Punkt 2, für die Anzeige je Kandidat.
- `category_confidence` (Float, nullable) — die Konfidenz **zur aufgelösten Kategorie dieser Zeile** (`category_key`), also `detected_category_confidences.get(category_key)`.

Der Skalar ist bewusst redundant. Er wird gebraucht, weil sowohl die Statistik-Aggregation als auch jede künftige mengenmäßige Auswertung in SQL laufen muss: Ein `AVG` über einen aus JSON extrahierten Wert ist in SQLite und PostgreSQL unterschiedlich zu schreiben, und die Alternative — alle Klassifizierungszeilen eines Projekts nach Python zu laden — verträgt sich nicht mit der Größenannahme des Projekts (mehrere tausend Fotos, ADR 0002) und nicht mit der bestehenden Statistikseite, die pro Kennzahl genau eine Aggregatabfrage absetzt.

Die Redundanz ist tragbar, weil es **eine** schreibende Stelle gibt (`worker.py::run_remote_category_classification`, ein Objekt-Konstruktor) und beide Werte dort aus derselben Quelle in derselben Transaktion entstehen. Ein Test hält die Invariante `category_confidence == detected_category_confidences.get(category_key)` fest.

### 5. Ausgewertet wird nach der Modell-Kategorie, nicht nach der wirksamen Kategorie

Die aggregierte Auswertung auf der Statistikseite gruppiert über `photo_category_classifications.category_key` — die Kategorie, die das **Modell** aufgelöst bekommen hat. Sie gruppiert ausdrücklich **nicht** über `photo_rankings.category_key`, obwohl das der Maßstab des bereits vorhandenen Kategorien-Blocks ist (ADR 0049, `stats.py::_categories_out`).

Der Unterschied ist der Zweck: Der vorhandene Block beantwortet „wie ist mein Bestand verteilt" und muss dafür die *wirksame* Kategorie nehmen (lokale Signale + Remote + manueller Override zusammengeführt). Der neue Block beantwortet „wie gut arbeitet die Erkennung" und muss dafür die *Aussage des Modells über sich selbst* nehmen. Beides in eine Tabellenzeile zu mischen, hieße, eine Konfidenz neben eine Fotoanzahl zu stellen, die sich auf eine andere Menge bezieht — eine Zahl, die stimmt, neben einer Zahl, die stimmt, mit einer Aussage dazwischen, die falsch ist. Deshalb ein eigener Block mit eigener Grundmenge, die ihre Basis mit ausweist (wie viele Fotos überhaupt eine Zahl beisteuern).

Aus demselben Grund verändert ein manueller Override die Konfidenz nicht — er lebt in `photo_scores.category_override` und berührt die Klassifizierungszeile nicht. Das ist keine zusätzliche Vorkehrung, sondern eine Eigenschaft der bestehenden Datenmodell-Trennung; sie wird durch einen Test festgehalten, nicht durch Code.

### 6. Keine Schwelle im Backend. „Unsicher" ist eine Sicht, keine Domänenregel

Das gezielte Auffinden unsicherer Zuordnungen in der Kuratierung ist ein clientseitiger Filter über dem ohnehin vollständig geladenen Kuratierungs-Pool; der Schwellwert dafür ist eine Konstante der Oberfläche und existiert an genau einer Stelle im Frontend. Weder API noch Datenbank kennen einen Begriff von „unsicher".

Begründung: Eine Schwelle, die Backend und Frontend beide bräuchten, müsste über eine API-Antwort transportiert oder gespiegelt werden — Spiegelung hat ADR 0049 für kategoriales Wissen bereits ausgeschlossen, und ein neues Feld nur für eine Anzeigeschwelle vergrößert die API-Oberfläche für eine Frage, die keine fachliche ist. Die Statistik kommt ohne Schwelle aus (Mittelwert und Basisgrößen sind schwellenfrei aussagekräftig), womit der Zwang zur Zweitverwendung entfällt.

Auch nicht entschieden wird eine serverseitige Sortierung nach Konfidenz: Die Kuratierung ordnet innerhalb einer Partition nach Rangposition („bestes Foto der Partition zuerst"), und eine Umsortierung nach Konfidenz nähme dieser Ansicht genau die Aussage, für die es sie gibt.

### 7. Das Antwortschema wird erweitert, nicht ersetzt — und bleibt tolerant

Der Kategorien-Eintrag der Modellantwort wird von einem nackten Schlüssel zu einem Objekt aus Schlüssel und Konfidenz. Ein Eintrag, der weiterhin nur ein Schlüssel-String ist, bleibt **gültig** und liefert eine Kategorie ohne Zahl — dieselbe inhaltliche Toleranz, die ADR 0049 Abschnitt 5 für unbekannte Werte etabliert hat, angewandt auf die Form. Ein Modell, das die neue Anweisung ignoriert, verschlechtert damit die Anzeige, aber nicht die Klassifizierung.

Strukturell hart bleibt allein, was vorher hart war (`categories` fehlt oder ist keine Liste). Der Prompt entsteht weiterhin ausschließlich aus `CATEGORY_REGISTRY` und nie aus Datenbankinhalten oder vorherigen Antworten (ADR 0049, Abschnitt 1).

Die Kostenannahmen (`pricing.py::ASSUMED_USAGE_BY_PROVIDER`) sind vor dem Festschreiben nachzurechnen statt stillschweigend zu übernehmen — der Prompt wächst um eine Anweisung, die Antwort um bis zu drei Zahlen. Das ist derselbe Verifikationsauftrag, den ADR 0049 an dieser Stelle bereits erteilt hat, und dieselbe Größenordnung: klein gegenüber dem dominierenden Bildtoken-Anteil, aber nicht ungeprüft.

## Begründung

Die entscheidende Frage war nicht, ob eine Konfidenz nützlich ist, sondern ob sie mit der Begründung von ADR 0049 vereinbar bleibt. Sie ist es, wenn drei Bedingungen gelten, und diese ADR macht alle drei verbindlich: Die Zahl hat einen benannten Verwender (Punkt 1 nennt drei), sie beeinflusst keine Auswahl (Punkt 1), und sie behauptet nie mehr, als das Modell gesagt hat (Punkt 3). Fiele eine davon weg, wäre die Streichung von 2026-08-30 wieder die richtige Entscheidung.

Der Alternativweg — Unsicherheit aus vorhandenen Signalen ableiten (Übereinstimmung lokaler und entfernter Erkennung, Anzahl der Kandidaten) — ist bereits fachlich geprüft und verworfen worden. Er hätte technisch ohne jede Schema- und Prompt-Änderung ausgekommen und wäre deshalb der billigere Weg gewesen; er hätte aber genau das erzeugt, was Punkt 3 verbietet: eine gerechnete Zahl, die wie eine Messung aussieht, ohne eine zu sein. Der teurere Weg ist hier der ehrlichere.

## Konsequenzen

- Die Zahl erscheint **nur an Fotos, die nach dieser Änderung klassifiziert werden**. Fotos mit bereits vorhandener Klassifizierungszeile werden von `worker.py::select_remote_category_candidates` dauerhaft übersprungen (Kostenschutz, ADR 0032/0049) — es gibt heute keinen unterstützten Weg, eine erneute Klassifizierung anzustoßen. Für den Bestand bleibt die Angabe damit auf unbestimmte Zeit leer, nicht nur „bis zum nächsten Lauf". Das ist die ehrliche Fassung der Abgrenzung von Story #299; ein „Neu-Klassifizierung erzwingen" ist eine eigene Story, nicht Teil dieser Entscheidung.
- Ein Feld mehr in der Modellantwort ist ein Feld mehr, das ein Anbieterwechsel oder Modellwechsel anders beantworten kann. Die Toleranz aus Punkt 7 fängt das ohne Fehlschlag auf, aber die Anzeige kann bei einem Modell schlicht leer bleiben. Die `WARNING`-Zeilen aus Punkt 3 sind das Mittel, das zu bemerken.
- Modell-Selbsteinschätzungen sind bekanntermaßen schlecht kalibriert. Die Oberfläche muss die Zahl deshalb als Selbsteinschätzung ausweisen und darf sie nie als Trefferquote, Genauigkeit oder Qualität benennen. Das ist eine Anforderung der Story und zugleich die Bedingung, unter der diese ADR den Wert überhaupt persistiert.
- Der Skalar aus Punkt 4 ist die Stelle, an der eine künftige Auswertung ansetzt (z.B. „Erkennungsqualität über die Zeit"). Wer ihn entfernt, muss die Aggregation aus Punkt 5 mit entfernen — sie ist sein einziger Daseinsgrund.
