# 0116 - Restdauer je laufendem Teilschritt: Servermessung, Spanne im Frontend, keine Gesamtrestzeit

**Status:** Accepted
**Datum:** 2026-09-17
**Bezug:** [GitHub-Issue #481](https://github.com/TheRealKoller/photosort/issues/481), Spec 0481

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sechs Punkte trägt und
der sechste — das Entfallen der Gesamtrestzeit — ohne seine drei Gründe nicht von einer vertagten
Umsetzung zu unterscheiden wäre.

## Kontext

Ein laufender Klassifizierungslauf zeigt heute je Teilschritt nur „X von Y". Er soll zusätzlich
sagen, wie lange der laufende Teilschritt noch dauert — als grobe Spanne, ohne Wert, solange keiner
belastbar ist, und ohne dass die Angabe im Zwei-Sekunden-Takt springt.

Drei Randbedingungen schneiden die Lösungsmenge:

- Der Lauf hat vier Teilschritte (`ClassificationPhase`). Drei führen eigene Zähler mit bekanntem
  Nenner; `ranking` hat keine gezählte Menge, weil es über Partitionen arbeitet.
- Der Bestand kennt zu einem Lauf genau einen Startzeitpunkt (`CriterionScoringRun.started_at`) und
  einen fortlaufend überschriebenen `last_progress_at`. Wann ein **einzelner** Teilschritt begonnen
  hat, steht nirgends: `last_progress_at` wird in der Folgephase weitergeschrieben.
- `ProjectOut` samt `last_criterion_scoring_run` wird während eines Laufs alle zwei Sekunden
  abgefragt. Was dort hinzukommt, wird in dieser Taktung mitgerechnet (ADR 0103, Punkt 1).

## Entscheidung

### 1. Der Beginn des laufenden Teilschritts wird persistiert

`CriterionScoringRun` bekommt die Spalte `phase_started_at: datetime | None` (naives UTC wie jede
andere Zeitspalte). Sie beschreibt den Beginn genau des Teilschritts, den `phase` nennt.

`phase` und `phase_started_at` werden **ausschließlich gemeinsam** gesetzt, über eine einzige
Funktion in `worker.py`. Sie ist die einzige Stelle im Modul, an der `.phase` einer
`CriterionScoringRun` zugewiesen wird; ein Quelltext-Wächtertest hält das fest. Fällt die Bindung,
rechnet die Messung den Beginn des **vorigen** Teilschritts mit dem Fortschritt des aktuellen
gegen: Die Restdauer ist dann zu groß, und zwar ohne Fehler, ohne Ausnahme und ohne Testrot.

`NULL` heißt „kein laufender Teilschritt" (beendet, abgebrochen, oder Altzeile) — nie „gerade
begonnen". Mit `phase = NULL` fällt auch `phase_started_at` auf `NULL` zurück.

### 2. Gemessen wird im Backend, ausgeliefert wird eine Zahl, nicht ein Text

`CriterionScoringRunSummary` bekommt **ein** additives Feld `phase_remaining_seconds: float | None`
— die geschätzte Restdauer des in `phase` genannten Teilschritts. Kein Feld je Teilschritt und
keines an `CloudPhaseSummaryOut`: Zu jedem Zeitpunkt läuft genau ein Teilschritt, ein erledigter hat
keine Restdauer und ein ausstehender keine Messgrundlage. Dass nach Abschluss, Fehlschlag und
Abbruch keine Restdauer mehr dasteht, ist damit eine Eigenschaft der Antwort (`phase` ist `NULL`,
das Feld ist es mit) und keine Regel der Oberfläche.

Die Rechnung ist der Durchsatz **seit Beginn des Teilschritts**, nicht der eines gleitenden
Fensters: `(total − processed) · (now − phase_started_at) / processed`. Ein gleitendes Fenster
bildete jede kurze Schwankung ab, und genau die soll die Anzeige nicht zeigen.

Die Zuordnung „welcher Zähler gehört zu welchem Teilschritt" steht dabei serverseitig; das Frontend
hängt den einen gelieferten Wert an die Zeile, die auf `running` steht, und bildet die Zuordnung
nicht nach.

Eine im Frontend aus aufeinanderfolgenden Abfragen gebildete Messung ist ausgeschlossen: Sie
überlebt keinen Neuaufbau der Seite, liefert den beiden Nutzern für denselben Lauf verschiedene
Zahlen und rechnet mit der Uhr des Klienten gegen einen Zeitstempel des Servers.

### 3. Belastbarkeit entscheidet der Server, `null` heißt „noch nicht abschätzbar"

`phase_remaining_seconds` ist `null`, solange eine der Bedingungen fehlt: bekannter Nenner größer
null, mindestens drei verarbeitete Einheiten und mindestens fünfzehn Sekunden seit Beginn des
Teilschritts. Beide Schwellen sind benannte Konstanten.

`null` heißt nie „keine Restdauer" und nie „sofort fertig". Die Oberfläche schreibt dort sichtbar
hin, dass die Restdauer noch nicht abschätzbar ist — kein leeres Feld.

### 4. Die Spanne entsteht im Frontend aus einer festen Leiter

Das Backend liefert eine Sekundenzahl, das Frontend bildet daraus die angezeigte Spanne über eine
feste, grobe Stufenleiter (Stufen im Verhältnis von etwa 1:2, z. B. 2–5, 5–10, 10–20 Minuten) mit
je einem Randtext nach unten und nach oben. Es wird nie eine Einzelzahl gezeigt.

Die Spanne ist eine Entscheidung über die gezeigte Genauigkeit, kein Vertrauensbereich: Eine
serverseitig gerechnete Ober- und Untergrenze behauptete eine Genauigkeitsaussage, die die Messung
nicht hergibt.

Die Ruhe der Anzeige trägt sich auf drei Mittel: den kumulierten Durchsatz aus Punkt 2, die
Schwellen aus Punkt 3 und die Stufenleiter. Dazu kommt eine Zusage im Frontend: **Ein geänderter
Stufentext wird erst übernommen, wenn er in zwei aufeinanderfolgenden Antworten steht.** Der
Wechsel des Teilschritts setzt diese Verzögerung zurück; ein Stufentext des vorigen Teilschritts
darf nie in den nächsten hineinragen.

### 5. Der Teilschritt „Rangfolge" trägt einen Erfahrungswert, kein gemessenes Datum

Für `ranking` ist `phase_remaining_seconds` **immer** `null`; er hat keine gezählte Menge und
bekommt auch keine geschätzte. Die Oberfläche zeigt dort einen festen Erfahrungswert, der sich vom
gemessenen Text sowohl im Wortlaut („erfahrungsgemäß") als auch in der Auszeichnung unterscheidet
und als solcher maschinenlesbar gekennzeichnet ist. Er darf nie die Form „noch ca. A–B" tragen: Er
steht unmittelbar neben gemessenen Angaben und würde sonst als eine gelesen.

### 6. Eine Gesamtrestzeit für den ganzen Lauf entfällt

Sie wäre zu Beginn des Laufs nicht belastbar zu bilden, und nur dann sollte sie es geben:

- Zum Startzeitpunkt liegt keine einzige Durchsatzmessung vor, und es gibt keinen gespeicherten
  Durchsatz vergangener Läufe. Die Geschwindigkeit hängt an der Maschine (lokale Inferenz) und an
  der Antwortzeit des Cloud-Anbieters.
- Die Menge des Landmark-Anteils ist vor dem ersten erfolgreichen Lauf eines Projekts strukturell
  unbekannt — dieselbe Lücke, die die Kostenvorschau dort bereits ausweist.
- Der Anteil aus Punkt 5 hat überhaupt keine Menge. Eine Summe ohne ihn wäre systematisch zu klein.

Eine erst im Verlauf ableitbare Gesamtrestzeit ist damit ausgeschlossen, nicht vertagt. Wer sie
später will, braucht zuerst gespeicherte Dauern je Teilschritt über mehrere Läufe hinweg — das ist
eine eigene Entscheidung, keine Erweiterung dieser.

## Konsequenzen

- Eine Alembic-Migration kommt hinzu (additive, nullbare Spalte, keine Datenwanderung).
- Läufe, die zum Zeitpunkt der Migration bereits laufen, zeigen keine Restdauer, bis sie den
  nächsten Teilschritt betreten. Das ist der reguläre `NULL`-Zweig, kein Fehlerfall.
- Der naive-UTC-Zeitpunkt wird jetzt an zwei Stellen gebraucht (Worker und Lesepfad) und bekommt
  deshalb genau eine Definition. Zwei Uhren mit verschiedener Zeitzonenbehandlung ergäben eine
  Restdauer, die um Stunden danebenliegt, ohne dass etwas fehlschlägt.
- Die übrigen Läufe (Scan, Ausschuss-Bewertung) bekommen **keine** Restdauer. Sie führen keinen
  Teilschritt-Zeiger und fielen nicht unter diese Entscheidung.
