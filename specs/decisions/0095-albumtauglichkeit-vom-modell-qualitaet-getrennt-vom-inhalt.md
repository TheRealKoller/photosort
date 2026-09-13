# 0095 - Albumtauglichkeit vom Modell: der Qualitätswert trennt sich vom Bildinhalt, die Modellstufe führt

**Frühere Nummer:** 0093 (bis 2026-09-13), aufgelöste Dublette mit 0093-laufstand-in-der-ausgabe-des-laufs-gelesen-nicht-erfragt.md.

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** Spec [`features/0428-albumtauglichkeit-vom-modell.md`](../features/0428-albumtauglichkeit-vom-modell.md)

**Grenzt ein:** [`0002`](./0002-hybrid-ai-scoring.md) — dort die Konsequenz „darf nie Voraussetzung
für die Kernfunktion sein". Sie gilt unverändert für Scan, Ausschuss-Gate und die lokale Bewertung;
allein der Album-Entwurf setzt ab hier die Cloud-Freigabe voraus (Abschnitt 1). ADR 0002 trägt
dafür den Vermerk „Teilweise abgelöst" und bleibt `Accepted`.

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sieben Punkte trägt, von
denen jeder für sich eine eigene Zusage ausspricht.

## Kontext

Der Rang-Score mischt heute Qualitätsmessungen und Inhaltssignale bei gleichem Gewicht, und zwei
Kompositionskriterien melden ohne erkennbares Subjekt bzw. ohne erkanntes Gesicht aktiv einen
schlechten Wert. Ein Foto ohne Personen wird dadurch zweifach abgewertet, und keine der lokalen
Messungen sieht, was ein Bild für ein Album unbrauchbar macht: geschlossene Augen, verdeckte
Gesichter, angeschnittene Personen, langweilige Komposition.

## Entscheidung

### 1. Der Album-Entwurf setzt die Cloud-Freigabe voraus; die Kernfunktion bleibt cloudfrei

Scan, Ausschuss-Gate und die lokale Bewertung laufen vollständig ohne Cloud — ohne Freigabe
verlässt kein Byte den Homeserver, und kein Schritt davon ändert sein Ergebnis. Was ohne Freigabe
nicht entsteht, ist allein der Album-Entwurf: kein Qualitätswert, keine Rangfolge, keine
Qualitätsstufe. Die Oberfläche benennt die fehlende Freigabe und bietet sie an, statt eine leere
Liste zu zeigen.

Es gibt keinen Rückfall auf einen rein lokal gebildeten Qualitätswert — weder projektweit noch für
ein einzelnes Foto, dessen Modellaufruf fehlgeschlagen ist. Ein solches Foto behält seine
Event-Zugehörigkeit und bleibt im einsehbaren Vorrat, trägt aber `NULL` als Qualitätswert und
erscheint nicht im Entwurf; der nächste Lauf holt es nach.

### 2. Die Albumtauglichkeit ist eine fünfstufige Modellaussage mit Begründung, im bestehenden Aufruf

Das Vision-Modell nennt je Foto eine ganze Zahl von 1 bis 5 und dazu eine kurze Begründung. Der
Prompt beschreibt jede der fünf Stufen mit einem Anker und nennt darin ausdrücklich geschlossene
Augen, verdeckte Gesichter, angeschnittene Personen und langweilige Komposition. Die Zahl wird
intern auf `[0, 1]` normiert (`(Stufe − 1) / 4`).

Die Frage geht an den bestehenden Klassifizierungsaufruf, der jedes Ausschuss-überlebende Foto
ohnehin erreicht. **Es entsteht kein zweiter Aufruf je Foto** — weder ein eigener Teilschritt noch
ein Anhängen an die Sehenswürdigkeits-Erkennung, die nur eine Kandidatenteilmenge erreicht.

Fünf Stufen mit Ankern statt einer stufenlosen Zahl: der Abstand zwischen zwei Stufen ist eine
feste Größe, an der Abschnitt 3 seine Ordnungszusage aufhängen kann.

### 3. Die Modellstufe führt, die lokalen Messungen korrigieren sie innerhalb ihrer Stufe

Der Qualitätswert eines Fotos ist

```
Q = clamp(M + span · (2·L − 1), 0, 1)
```

mit `M` der normierten Modellstufe, `L` dem gewichteten Mittel der vorhandenen lokalen
Qualitäts-/Kompositionskriterien und `span = 0,1`. Liegt für ein Foto kein einziges lokales
Kriterium vor, ist `Q = M`.

**Zusicherung:** `2 · span = 0,2` ist kleiner als der Abstand zweier benachbarter Modellstufen
(`0,25`). Damit kann ein Foto mit der niedrigeren Modellstufe ein Foto mit der höheren durch noch
so gute lokale Messwerte **nie** überholen — die lokalen Messungen ordnen ausschließlich innerhalb
einer Stufe. Ein Invariantentest prüft das über die Extremwerte `L = 0` und `L = 1`; wer `span`
über `0,125` hebt, bricht ihn.

### 4. Inhaltssignale gehen nicht in den Qualitätswert ein

In den Qualitätswert gehen genau die lokalen Kriterien ein, die keine Inhaltsaussage treffen:
`sharpness`, `exposure`, `aesthetics`, `goldener_schnitt`, `symmetrie`, `horizont`, `freiraum`.

Nicht enthalten sind die sieben Kriterien mit `presence_threshold` (`content_people`, `tier`,
`gebaeude`, `landschaft`, `fahrzeug`, `essen_trinken`, `landmark`) — ein Invariantentest hält fest,
dass kein Eintrag der Gewichtstabelle eine `presence_threshold` trägt. Ebenfalls nicht enthalten
ist `content_landscape`: es misst Texturarmut, und „mehr gleichförmige Fläche" ist keine Aussage
über Bildgüte. Es bleibt als eigenständiges Kriterium bestehen.

Daraus folgt unmittelbar: zwei Fotos, die sich ausschließlich im Bildinhalt unterscheiden, tragen
denselben Qualitätswert.

### 5. Ein nicht messbares Kriterium wird weggelassen, nicht als schlechter Wert gewertet

`goldener_schnitt` ohne erkennbares Subjekt und `freiraum` ohne erkanntes Gesicht liefern **keinen
Wert** statt `0.0`. Das Mittel in Abschnitt 3 renormiert auf die tatsächlich vorhandenen Kriterien,
ein fehlendes Kriterium senkt den Wert also nicht.

Zu unterscheiden sind dabei zwei Fälle, und sie werden verschieden behandelt:

- **Nicht messbar** — die Detektion lief, das Foto trägt das Merkmal nicht. Eine aus einem früheren
  Lauf vorhandene Kriterienzeile wird **gelöscht**. Ohne das Löschen bliebe der alte `0.0`-Wert
  wirksam und die Entscheidung dieses Abschnitts liefe für den Bestand ins Leere.
- **Nicht berechnet** — Detektor oder Modell standen nicht zur Verfügung, oder die Berechnung ist
  fehlgeschlagen. Eine vorhandene Zeile bleibt **unberührt**; ein Infrastrukturproblem darf keinen
  gültigen Messwert vernichten.

### 6. Die Albumtauglichkeit ist eine eigene Tabelle, nicht ein Feld der Motiv-Kopfzeile

`photo_album_suitability` (`photo_id` als Primärschlüssel, `level`, `reason`, `provider`,
`computed_at`) hängt an `photos`, nicht an `photo_motif_assessments`. Die Motiv-Kopfzeile ist eine
Aussage über den Bildinhalt und existiert auch auf lokaler Grundlage; die Albumtauglichkeit ist
eine Aussage über die Bildgüte und gibt es nur mit Cloud-Grundlage. Genau diese Trennung ist der
Gegenstand von Abschnitt 4 — sie im Datenmodell wieder zusammenzulegen, hieße sie aufzugeben.

Persistiert wird die Stufe `1..5`, nicht zusätzlich der normierte Wert: die Normierung ist eine
reine Funktion, eine zweite Spalte daneben wäre ein zweiter Ort für dieselbe Aussage.

`reason` ist der einzige neue Fremdtext-Kanal dieser Antwort. Er wird zeichensaniert und
längenbegrenzt und dabei **gekürzt statt verworfen** — anders als ein Feinlabel trägt er keine
Identität, an der ein gekürzter Wert Schaden anrichten könnte. Ohne brauchbare Begründung steht
dort `NULL`, nie eine leere Zeichenkette.

### 7. Nachbewertet wird über die Kandidatenauswahl, nicht über einen neuen Mechanismus

Kandidat des Modellaufrufs ist ab hier auch ein Foto, das bereits eine Cloud-Kopfzeile, aber noch
keine Albumtauglichkeit trägt. Ein erneuter Klassifizierungslauf holt den Bestand damit nach, ohne
Re-Scan und ohne einen zweiten Auslöser; die Vorab-Kostenschätzung folgt zwangsläufig, weil sie
dieselbe Auswahlfunktion benutzt.

**Das Übersprungen-Kriterium bleibt dabei zusammengesetzt** — eine Cloud-Kopfzeile **und** eine
Albumtauglichkeitszeile. Eine Lockerung auf nur eines der beiden schickt bereits vollständig
bewertete Fotos erneut an den Anbieter: Kosten und wiederholte Datenexposition.

## Konsequenzen

- Die Antwort je Foto wächst um eine Zahl und einen Satz. Die Ausgabe-Schranke des Clients und die
  Kostenannahme je Bild sind zusammen neu herzuleiten, unter Einhaltung von
  `Schranke ≥ 2 × Annahme`.
- `photo_rankings.rank_score` und `rank_position` werden nullable. `NULL` heißt „kein
  Qualitätswert, weil keine Modellbewertung" — `event_id` bleibt `NOT NULL`, die Gliederung nach
  Events ist keine Cloud-Leistung.
- Motivabhängige Gewichte (Horizont bei Landschaft, Freiraum bei Porträt) bleiben möglich: sowohl
  das lokale Mittel als auch der Qualitätswert nehmen die Gewichtstabelle als Parameter entgegen.
  Welche Gewichte je Motiv gelten, entscheidet diese ADR nicht.
- Die Stufengrenzen der angezeigten Qualitätsstufe liegen ab hier auf den Stufenmitten `0,375` und
  `0,625`. Sonst erschiene dieselbe Modellstufe je nach lokaler Korrektur in zwei verschiedenen
  Anzeigestufen.
- Unberührt bleibt die Zusage aus ADR [`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md),
  dass Motivstärken stets innerhalb eines Motivs verglichen werden und nie zwischen zweien: die
  Albumtauglichkeit ist keine Motivstärke, und sie wird ausschließlich zwischen Fotos derselben
  Frage verglichen.
