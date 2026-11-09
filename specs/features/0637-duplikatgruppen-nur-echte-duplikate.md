# 0637 - Duplikatgruppen enthalten nur echte Duplikate

**Status:** Accepted
**Erstellt:** 2026-11-09
**Bezug:** Issue [#637](https://github.com/TheRealKoller/photosort/issues/637); ADR
[`0145`](../decisions/0145-mehrstufige-duplikaterkennung-zeitfenster-und-stern-ohne-bruecken.md)

Umfang über dem Richtwert: Jede der drei Prüfstufen, die Zeit-Herkunft und die Fortwirkung alter
Entscheidungen trägt eine eigene Ausfallrichtung; sie stehen vollständig, weil sie nur gemeinsam
die Zusage „nur echte Duplikate“ ergeben.

## Ziel

Die Ausschuss-Erkennung schlägt in großen Projekten Duplikatgruppen vor, die keine sind. Im
auslösenden Projekt waren es 444 Gruppen; eine enthielt 13 Aufnahmen über 392 Stunden, obwohl
höchstens zwei Paare echte Duplikate waren. Jeder Nicht-Gewinner gilt als Ausschuss und läuft
nicht in Bewertung, Kategorien und Album; gute, verschiedene Fotos gehen still verloren.

Künftig werden nur noch echte Duplikate als Gruppe vorgeschlagen. Ähnliche Bilder werden nur
innerhalb eines Zeitfensters zusammengefasst; praktisch identische Bilder, etwa ein Doppelimport
oder eine verkleinerte Kopie, unabhängig vom Zeitabstand. Die Erkennung wird mehrstufig: eine
großzügige Kandidatenstufe und genauere Prüfstufen.

**Nicht Teil dieser Story:** das automatische Verwerfen sicherer Duplikate ohne Nachfrage. Es
weicht den Grundsatz auf, dass ein Vorschlag erst durch den Nutzer verbindlich wird, und setzt
eine kalibrierte Erkennung voraus.

## User Story

Als Nutzer, der den Ausschuss eines großen Projekts durchgeht, möchte ich, dass nur echte
Duplikate als Gruppe vorgeschlagen werden, damit ich keine verschiedenen Fotos verliere und den
Ausschuss in vertretbarer Zeit abschließe.

## Akzeptanzkriterien

- [ ] **Ähnliche Bilder nur im Zeitfenster:** Liegen die Aufnahmezeiten zweier ähnlicher, aber
  nicht praktisch identischer Aufnahmen weiter auseinander als das festgelegte Zeitfenster,
  landen sie nie in derselben Gruppe.
- [ ] **Praktisch identische Bilder ohne Zeitgrenze:** Ein praktisch identisches Bild, etwa ein
  Doppelimport oder eine Kopie in einem anderen Ordner, wird auch bei beliebig großem Zeitabstand
  als Duplikat erkannt. Eine Aufnahmezeit braucht es dafür nicht.
- [ ] **Grenze zwischen beiden Fällen:** Eine Serienaufnahme mit leicht verschobenem Ausschnitt
  gilt **nicht** als praktisch identisch und wird außerhalb des Zeitfensters nicht gruppiert; eine
  bloß neu gespeicherte oder verkleinerte Kopie gilt als praktisch identisch.
- [ ] **Keine Brückengruppen:** Jede Aufnahme einer Gruppe ist der vorgeschlagenen
  Behalte-Aufnahme selbst ähnlich genug. Ähnlichkeitsketten verbinden keine Aufnahmen.
- [ ] **Fehlende Aufnahmezeit:** Eine Aufnahme ohne Aufnahmezeit wird nur als praktisch identisches
  Bild gruppiert, nie als bloß ähnliches.
- [ ] **Mehrstufige Prüfung:** Eine schnelle erste Stufe wählt Kandidatenpaare großzügig aus. Nur
  Paare, die auch die genaueren Prüfstufen bestehen, bilden eine Gruppe; ein Paar, das nur die
  erste Stufe besteht, ist kein Duplikat.
- [ ] **Ergebnis bleibt Vorschlag:** Jede Gruppe ist weiterhin ein Vorschlag. Ohne Entscheidung des
  Nutzers wird nichts endgültig verworfen. Die Bedienung von Vergleichsansicht, Ausschuss-Schritt,
  „behalten/verwerfen“ und Abschluss-Aktion bleibt gleich.
- [ ] **Regressionsfall aus dem Auslöser:** In einem Bestand nach dem Muster des auslösenden
  Projekts (13 Aufnahmen über rund 392 Stunden, höchstens zwei echte Paare) gibt es keine Gruppe
  aus ähnlichen Bildern über das Zeitfenster hinaus; die echten Paare werden weiterhin erkannt.
- [ ] **Lokal und ohne Kosten:** Alle Prüfstufen laufen auf dem Homeserver. Für die Duplikatprüfung
  verlässt keine Aufnahme den Server.
- [ ] **Frühere Entscheidungen:** Für Entscheidungen aus einem früheren Lauf, deren Gruppe nach
  dem Neulauf nicht mehr besteht, ist festgelegt und für den Nutzer erkennbar, ob sie weiter
  wirken — besonders für „verwerfen“.
- [ ] **Kalibriert:** Zeitfenster und Schwellen sind an einem echten Bestand geprüft. Für
  mindestens ein großes Projekt sind Gruppenzahl und Gruppengrößen vor und nach der Änderung
  dokumentiert.
- [ ] **Demo bleibt vorführbar:** Das Demo-Projekt zeigt weiterhin mindestens zwei
  Duplikatgruppen verschiedener Größe.

## Datenmodell-Bezug

Keine Migration, keine neue Spalte, keine neue Tabelle. `PhotoScore.phash` bleibt der grobe
64-Bit-dHash; die feine Signatur für die Stufen 2/3 lebt nur im Scoring-Lauf im Speicher. Neu sind
zwei additive Felder der Ausschuss-Antwort: `AusschussPhotoEntryOut.reason` bekommt den dritten
Wert `earlier_decision`, und `decision_effective: bool | Null` nennt die Wirksamkeit der
gespeicherten Zeile. `SuggestionOut.reason` bleibt zweiwertig. Siehe
[`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Grundlage ist ADR [`0145`](../decisions/0145-mehrstufige-duplikaterkennung-zeitfenster-und-stern-ohne-bruecken.md).
ADR 0104, ADR 0111 und Spec [`0525`](./0525-ausschuss-ein-schritt.md) bleiben in Kraft; geändert
wird die **Erkennung**, nicht der Stern, nicht die Entscheidungstabelle und nicht das
Überlebens-Prädikat.

### Stufen und Startwerte

Alle Vergleiche sind inklusiv (`≤`). Die Zahlen sind Startwerte; der Kalibrierlauf bestätigt oder
verschiebt sie. Die Entscheidung ist die Stufenfolge und die Ausfallrichtung, nicht der einzelne
Zahlenwert.

| Konstante in `scoring.py` | Startwert | Bedeutung |
|---|---:|---|
| `DUPLICATE_CANDIDATE_HAMMING` | 12 von 64 | Stufe 1: grober dHash, großzügiges Netz |
| `DUPLICATE_CANDIDATE_BANDS` | 13 | Bandzahl der exakten Kandidatensuche (= Grenze + 1) |
| `DUPLICATE_SIMILAR_HAMMING` | 8 von 64 | „ähnlich“: grober dHash nach Stufe 1 |
| `DUPLICATE_SIMILAR_FINE_HAMMING` | 64 von 256 | „ähnlich“: feiner dHash |
| `DUPLICATE_SIMILAR_TIME_WINDOW` | 15 min | Zeitfenster für „ähnlich“, paarweise |
| `IDENTICAL_FINE_HAMMING` | 16 von 256 | „praktisch identisch“: feiner dHash |
| `IDENTICAL_GRID_MAD` | 0.06 | „praktisch identisch“: z-normierte 32×32-Differenz |
| `IDENTICAL_FLAT_MAD` | 1.0 Graustufe | Sonderfall beidseitig varianzfreier Gitter |

**Stufe 1** vergleicht `int`-Hashes per `(a ^ b).bit_count()` innerhalb von 13 disjunkten
Bit-Bändern; bei Hamming `≤ 12` stimmt nach dem Schubfachprinzip mindestens ein Band exakt
überein. Die Trefferzusage ist exakt, kein Paar unter der Grenze geht verloren.

**Praktisch identisch** ist ein Paar genau dann, wenn `fine_hamming ≤ 16` **und**
`grid_mad ≤ 0.06`. Die z-Normierung entfernt globale Helligkeits-/Kontraständerungen, aber keine
geometrische Verschiebung. Sind beide Gitter varianzfrei, entscheidet die rohe mittlere
Grauwertdifferenz `≤ 1.0`; ist nur eines varianzfrei, ist das Paar nicht identisch.

**Ähnlich** ist ein Paar genau dann, wenn `coarse_hamming ≤ 8`, `fine_hamming ≤ 64`, beide Zeiten
verlässlich sind und `|Δt| ≤ 15 min`. Erst wird „praktisch identisch“ geprüft, dann „ähnlich“;
identische Paare sind zeitunabhängig, ähnliche nie.

### Stern ohne Brücken

`assign_duplicate_groups` ersetzt `assign_duplicate_clusters` samt Union-Find vollständig:

1. Alle Fotos absteigend nach `(-sharpness, photo_id)` sortieren.
2. Das erste noch nicht zugeordnete Foto wird Gewinner.
3. Mitglieder werden nur aus den noch freien Fotos genommen, die zu **diesem Gewinner** eine
   direkte Kante haben (identisch oder ähnlich im Fenster).
4. Für zwei **ähnliche** (nicht identische) Mitglieder desselben Sterns gilt zusätzlich paarweise
   `|Δt| ≤ DUPLICATE_SIMILAR_TIME_WINDOW`; ein Kandidat, der das gegen ein bereits aufgenommenes
   Mitglied verletzt, wird nicht aufgenommen.
5. Ausgabe als `loser → winner`; alle Mitglieder sind zugeordnet, der nächste freie Kandidat
   beginnt von vorn.

Ein Kettenmitglied, das nur über ein anderes Mitglied am Gewinner hängt, bleibt ungruppiert.

### Fehlende Aufnahmezeit

`taken_at` und `taken_at_original` sind `NOT NULL`; ohne EXIF schreibt der Scan beide aus
`last_modified`. Die Erkennung leitet „Zeit unsicher“ exakt und ohne Toleranz ab:
`taken_at_is_trusted(taken_at_original, last_modified) = taken_at_original != last_modified`.
Bei unsicherer Zeit ist nur „praktisch identisch“ eine Kante. Die Fensterprüfung liest
`taken_at` (kamerakorrigiert), nicht die Herkunftswerte. Die Gleichheit kann auch bei vorhandenem
EXIF gelten (EXIF-Zeit gleich mtime); dann werden ähnliche Bilder nicht gruppiert —
falsch-negativ, sicher.

### Frühere Entscheidungen

Die Semantik aus ADR 0104 Punkt 3 bleibt: `discard` wirkt unbedingt, `keep` nur solange
`duplicate_of IS NOT NULL`. Neu:

- `reason = "earlier_decision"`, wenn weder `duplicate_of` noch `suggested_status` vorliegt, aber
  eine Entscheidungszeile existiert.
- `decision_effective_for(photo)`: `None` ohne Zeile; `true` für `discard`; für `keep` genau dann
  `true`, wenn `duplicate_of IS NOT NULL`. Ein veralteter `keep` ohne Gruppe ist `false`, obwohl
  das Foto überlebt.
- Der Einzel-Schreibweg akzeptiert jede Aufnahme des Ausschuss-Bestands
  (`has_ausschuss_entry`, projektgebunden), nicht nur „Gruppe oder offener Vorschlag“ — sonst wäre
  ein alter `discard` sichtbar, aber nicht widerrufbar. Der Gruppen-Schreibweg bleibt unverändert.

### Kalibrierung: `duplicate_probe`

Neues, rein lesendes Modul nach dem Muster von `event_probe.py`:
`python -m photosort.duplicate_probe --project-id <N>`. Es öffnet je Foto die lokale
`display`-Variante, rechnet **dreimal über derselben gemessenen Teilmenge** (bisheriges Verfahren
als eingefrorene Referenz, neues Verfahren, Gegenlauf ohne Zeit-Herkunft) und gibt nur Projekt-Id,
Lauf-Id, Anzahlen, Größenverteilungen, größte Gruppe, größte Spanne ähnlicher Mitglieder und den
Anteil unsicherer Zeiten aus. Keine Pfade, Dateinamen, Zeitstempel oder Einzelfotos; fehlender
Cache heißt „nicht gemessen“ und wird nicht als 0 verbucht. Aufruf und Datenschutzsatz kommen nach
`docs/setup.md`.

### Betroffene Dateien

`scoring.py` (Signaturen, Paarprüfung, Stern), `worker.py` (`_compute_photo_metrics`,
`run_project_scoring`), `duplicates.py` (`decision_effective_for`), `api/photos.py`
(`reason`, `decision_effective`), `api/duplicate_decisions.py` (Vorbedingung),
`duplicate_probe.py` (neu), Frontend `AusschussStepPage.tsx`/`api/types.ts`; Tests und Doku.

## Teststrategie

Grundlage ist [`0002`](../architecture/0002-testkonzept.md). Keine neue Testebene: `pytest`
(Unit DB-frei, Integration gegen echte In-Memory-SQLite und echte `display`-Cache-Dateien),
`vitest`, kein neuer E2E-Fall.

Leitregeln: Jede Grenze kommt aus der Modulkonstanten (±1 Bit bzw. ±1 s), nie aus einer
abgeschriebenen Zahl. Jede Prüfstufe wird an einem Fall belegt, den sie allein entscheidet.
Bilder laufen durch die Produktionsfunktionen, nicht durch handgebaute Hashes.

| Zusage | Ebene |
|---|---|
| Praktisch identisch in vier Kopieformen (neu gespeichert, verkleinert, anderes Format, bytegleich) ohne Zeitgrenze; auch ohne `taken_at` | Unit `test_scoring.py` |
| Verschobener Ausschnitt: Kandidat der Stufe 1, aber nicht identisch; ähnlich innerhalb des Fensters gruppiert, außerhalb nie | Unit |
| Grenze des Fensters: exakt auf der Konstanten gruppiert, eine Sekunde darüber nicht | Unit |
| Keine Brückengruppen: Invariante „jedes Mitglied hat eine direkte Kante zum Gewinner“, Kette A~B~C mit A≁C, zwei Sterne | Unit |
| Fehlende Zeit: `taken_at_trusted=False` verbindet nur identisch, nie ähnlich | Unit |
| Stufe 1 exakt: jedes Paar auf und unter der Kandidatengrenze wird gefunden, keines darüber | Unit |
| Gewinner: höchste Schärfe, Tie-Break niedrigere Id, Ergebnis unabhängig von der Eingabereihenfolge; leere/kleine Menge | Unit |
| Worker: zwei echte `run_project_scoring`-Läufe; ähnlich im Fenster gruppiert, 392 h auseinander nicht; Kopie 392 h auseinander gruppiert; jedes Mitglied `duplicate_of == winner` | Integration `test_worker_score_project.py` |
| Bestehende Tests: `test_transitively_close_hashes_form_a_single_cluster` entfällt (kodiert die verbotene Brücke) und lebt als Referenz im Probe-Test; `DUPLICATE_HAMMING_THRESHOLD` wird ersetzt | `test_scoring.py` |
| Ausschuss: `earlier_decision` und `decision_effective` für eine Zeile ohne aktuellen Grund; veralteter `keep` ist `false`, `discard` `true`; Einzel-Schreibweg hebt einen alten `discard` auf | `test_api_ausschuss.py`, `test_api_duplicate_decisions.py` |
| Veraltete Entscheidung sichtbar: bestehender Fall `test_a_stale_keep_becomes_ineffective_while_a_stale_discard_keeps_working` bleibt; Entscheidungszeilen überleben den Neulauf | Integration |
| Frontend: „Aus früherem Lauf“ statt Grund-Kennzeichen; „wirkt nicht mehr“ nur bei `keep` + `false` + `keepPossible === false`; Bedienung unverändert | `vitest` |
| Probe: reine Zählfunktionen, Bericht ohne Bilddaten, „nicht gemessen“ statt 0, Read-only-Dreiteilung (Import-Graph, Schreibform-Wächter, `main()`-Schnappschuss) | `test_duplicate_probe.py` |
| Demo: zwei Gruppen der Größen 7 und 3, unverändert | `test_demo_state.py` |
| Lokal und ohne Kosten: autouse-Netzsperre deckt jeden neuen Fall | `conftest.py` |

## UI/UX

Kein neues Bedienelement, kein neuer Dialog, kein dritter Anzeigezustand. Zwei Textstellen kommen
hinzu:

- Hat ein Eintrag **keinen aktuellen Grund**, aber eine gespeicherte Entscheidung
  (`reason === 'earlier_decision'`), entfällt das Grund-Kennzeichen; neben dem Entscheidungswort
  steht `Aus früherem Lauf` (`text-xs text-text-muted`) — in Kachel und Detailzeile. Kein neues
  Symbol, keine Farbe.
- Ein gespeichertes `keep`, das nicht mehr wirkt (`keep === 'keep'`,
  `decision_effective === false`, `keepPossible === false`), trägt neben dem Entscheidungswort
  den Zusatz `wirkt nicht mehr`. Bei `keep_possible === true` entfällt der Zusatz: Die Aufnahme
  bleibt, „wirkt nicht mehr“ läse sich als Verlust. Für `discard` kein Zusatz; das Wort
  „Ausschuss“ trägt den Zustand.
- Der Client leitet beides nicht ab (dieselbe Regel wie `keep_possible`); die Felder kommen vom
  Server. `decision_effective` steht nur am Einzeleintrag, nicht an der Vergleichsansicht.

Beide Texte schließen einander aus: `earlier_decision` heißt „kein aktueller Grund“, „wirkt nicht
mehr“ erscheint nur bei einem aktuellen Grund. Demo, Ladezustände, Abschluss-Aktion und
Gruppenkopf bleiben unverändert.

## Security

Sicherheitsrelevant in geringem Umfang: kein neuer Endpunkt, kein Secret, keine neue Eingabe,
keine neue Abhängigkeit, kein Netzzugriff. Betroffen ist der **Ursprung** der Verlierermenge, die
mitbestimmt, welche Fotos den Homeserver Richtung Cloud-Anbieter verlassen, der Radius des
gruppenweiten Schreibwegs und eine Messausgabe im öffentlichen Repository.

- **S1 — Prädikat und Aufrufstellen bleiben.** Das Überlebens-Prädikat und seine vier
  cloud-bestimmenden Aufrufstellen bleiben wörtlich unverändert; die neuen Stufen liefern nur die
  Verlierermenge. Bei Verletzung verlassen verworfene Aufnahmen den Homeserver, behaltene fehlen,
  und die Kostenschätzung nennt eine andere Zahl als der Lauf sendet.
- **S2 — Ein Schreiber, ein Gruppenbegriff.** Neue Stufen schreiben ausschließlich
  `duplicate_of`/`suggested_status` in `run_project_scoring`; keine neue Spalte/Tabelle, kein
  zweiter Schreiber, keine persistierte Signatur. Die Kandidatenmenge bleibt der Bestand des
  Projekts. Bei Verletzung nennt `duplicate_of` einen Repräsentanten, den die projektgebundene
  Folgeabfrage nicht auflöst.
- **S3 — Ausfallrichtung „keine Gruppe“.** Fehlende Signatur, fehlende Zeit oder nicht bestandene
  Prüfstufe ergeben keine Gruppe; niemand wird allein auf Stufe 1 zum Verlierer. Eine falsche
  Gruppe nimmt ein gutes Foto still aus Bewertung, Kategorien, Album und Cloud-Kandidaten; ein
  verpasstes Duplikat kostet ein gedeckeltes Bild.
- **S4 — Jedes Mitglied direkt am Gewinner.** Die Mitgliedschaft wird gegen den endgültigen
  Repräsentanten geprüft, nie transitiv. Bei Verletzung behauptet die Ansicht eine
  Duplikatbeziehung, die es nicht gibt, und ein gruppenweites `discard` löscht verschiedene
  Inhalte.
- **S5 — Schranken bleiben.** In Projekten mit falschen Gruppen werden nach dem Neulauf **mehr**
  Aufnahmen Cloud-Kandidaten; Einwilligung, Kostenschätzung über dieselbe Menge und der
  ausdrücklich gestartete Lauf bleiben unverändert. Meldet der Lauf keine Vorschläge mehr, setzt
  `run_project_scoring` `gate_confirmed_at` selbst; das Gate sichtet Vorschläge, und ohne
  Vorschläge gibt es nichts zu sichten.
- **S6 — Nur die lokale `display`-Variante.** Kein Original, kein erneuter Download, kein
  Netzaufruf, kein Subprozess, keine neue Abhängigkeit (Pillow/Stdlib); Bild-I/O nur über
  `image_codecs.py`. Bei Verletzung entstünde ein zweiter, ungeprüfter Bildweg.
- **S7 — Konstanten, keine Betriebswerte.** Ein eigener Name je Zahl, nie `TIME_CLUSTER_GAP` oder
  die alte Duplikatschwelle mitbenutzt, nie aus `.env`, Settings, Query oder Body. Ein
  Laufzeithebel wäre ein Schalter an der Cloud-Grenze.
- **S8 — Signatur ist Bilddatum.** Die neuen Ähnlichkeitswerte bleiben im Speicher; sie erscheinen
  nicht in `PhotoOut`, Logs, Messausgabe oder einer Datei. Eine Signatur wäre ein stabiler
  Fingerabdruck; geloggt werden nur festes Grund-Token und Foto-Id.
- **S9 — Best-effort je Foto.** Breites `except Exception` bleibt (DecompressionBombError erbt
  nicht von `OSError`); `MAX_IMAGE_PIXELS` wird nicht angehoben; ein Fehler ergibt keine Signatur,
  keine Gruppe, keinen Abbruch. Kein Rückfall von Stufe 2 auf Stufe 1.
- **S10 — Hergeleitete Zeit ist keine Messung.** Der `last_modified`-Rückfall darf nicht als
  Aufnahmezeit gelten; die Gleichheitsregel behandelt ihn als „ohne Aufnahmezeit“, und nur
  praktisch identische Bilder werden dann gruppiert. Bei Verletzung behauptet eine Gruppe eine
  Nähe, die niemand gemessen hat.
- **S11 — Frühere Entscheidungen bleiben wahr.** Ein `discard` wirkt weiter, auch wenn die Gruppe
  zerfällt; keine Zeile wird gelöscht, überschrieben oder neu verankert. Die Sichtbarkeit kommt
  über `has_ausschuss_entry` und die neuen Felder; die Rückholbarkeit über den erweiterten
  Einzel-Schreibweg.
- **S12 — Messausgabe nur Aggregate.** Das Messkommando ruft die echte Gruppierungsfunktion, gibt
  nur Anzahlen/Klassen, Projekt-Id und Lauf-Id aus; keine Pfade, Namen, Zeitstempel, Koordinaten,
  Signaturen, Ähnlichkeitswerte oder Zeilen je Foto/Gruppe. Nur stdout, keine Datei, kein Logger,
  kein Endpunkt.
- **S13 — Demo bleibt synthetisch.** Bilder entstehen weiter mit Pillow im Seed; keine echten
  Dateinamen, Pfade, EXIF-Zeiten oder Koordinaten. Die Gruppen (7, 3) bleiben sichtbar.

Kein neuer Auth-Pfad, kein XSS-Sink, keine neue Datensichtbarkeit; Gruppenansicht und
Ausschuss-Bestand bleiben projektgebunden und authentifiziert. Im selben PR nachzuziehen:
`specs/architecture/0003-securitykonzept.md` (Ankerzeilen zur Gruppierung und zum
Ausschuss-Bestand, Restrisiko „verwaistes `discard`“).

## Entscheidungen

- **Drei Stufen statt einer Schwelle** (ADR 0145): Die 64-Bit-Distanz allein trennt Kopie und
  verschobenen Ausschnitt nicht; der feine dHash plus z-normiertes 32×32-Gitter trennt sie mit
  weitem Abstand (Messung: Kopie 0–2 Bit/≤ 0,004; 2-%-Beschnitt ≥ 28 Bit/≥ 0,08).
- **Stern statt Union-Find:** Brücken sind der Defekt; ein Kettenmitglied bleibt lieber Einzelfoto.
- **Kein Persistieren der feinen Signatur:** Sie entsteht in derselben Dekodierung; eine Spalte
  kostete Migration und Speicher ohne Nutzen.
- **Zeit-Herkunft per Gleichheit statt Merker:** Für den gefährlichen Fall (kein EXIF) exakt, für
  den harmlosen Fall konservativ; eine Spalte hätte für Bestandszeilen bis zum Re-Scan denselben
  Zustand. Zeigt die Messung einen nicht vernachlässigbaren Anteil, wird „Ableitung oder Flag“ als
  Produktentscheidung vorgelegt, nicht still entschieden.
- **`decision_effective` statt Gleichheit mit dem angezeigten Zustand:** Ein veralteter `keep`
  überlebt ohnehin; die Gleichheit sagte `true`, obwohl die Entscheidung nichts mehr bewirkt.
- **Einzel-Schreibweg auf den Ausschuss-Bestand erweitert:** Sonst wäre ein alter `discard`
  sichtbar, aber nicht widerrufbar. Der Gruppen-Schreibweg bleibt eng.
- **Kein ADR für die Demo:** Der Seed schreibt `duplicate_of` direkt und ist von der Erkennung
  unabhängig; die bestehenden Tests sichern die Zusage.

## Offene Fragen

Keine. Die Kalibrierung kann die Startwerte verschieben; ein hoher Anteil unsicherer Zeiten wird
als Produktentscheidung „Ableitung oder Merker“ vorgelegt, nicht still ausgeliefert.

## Out of Scope

- Automatisches Verwerfen sicherer Duplikate ohne Nachfrage.
- Persistierte Duplikatgruppen oder feine Signaturen; neue Tabellen/Spalten.
- Neue Abhängigkeiten (`imagehash`, OpenCV) und Cloud-Aufrufe für die Duplikatprüfung.
- Änderung von Stern, Entscheidungstabelle, Überlebens-Prädikat, Vergleichsansicht oder
  Abschluss-Aktion.
- Neue E2E-Tests und eine Laufzeit-Zusage.

## Abgelöste Zusagen

- Spec [`0525`](./0525-ausschuss-ein-schritt.md) AK4: `reason` ist nicht mehr nur
  `duplicate`/`low_quality`; der dritte Wert `earlier_decision` beschreibt einen Eintrag, dessen
  einzige Ursache eine gespeicherte Entscheidung ist.
- Spec 0525: Die Vorbedingung des Einzel-Schreibwegs ist nicht mehr „Gruppe oder offener
  Vorschlag“, sondern `has_ausschuss_entry()`.
- ADR [`0104`](../decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md),
  Konsequenz-Zeile „Die Duplikaterkennung bleibt unverändert“: redaktionell auf ADR 0145 gezogen;
  Status und übrige Punkte bleiben.

## Messergebnis

Wird nach dem Kalibrierlauf ergänzt (Gruppenzahl und Gruppengrößen vorher/nachher, größte Gruppe,
Stufenzahlen, Anteil unsicherer Zeiten, Stichprobe der echten Paare).
