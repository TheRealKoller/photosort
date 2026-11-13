# 0146 - Automatisch entschiedene Duplikatgruppen: Lauf-Merker am Verlierer, Auflösung als Gewinnerregel

**Status:** Accepted — Punkt 1 (Gewinnerregel getrennt nach Gruppenart) ist Daniel vor der
Umsetzung vorgelegt und am 2026-11-12 wie empfohlen bestätigt worden.
**Datum:** 2026-11-12
**Bezug:** Spec [`0639`](../features/0639-automatisch-entschiedene-duplikatgruppen.md); ADR
[`0104`](./0104-ausschuss-entscheidung-uebersteuert-den-automaten.md) (Entscheidungstabelle,
Überlebens-Prädikat), ADR
[`0145`](./0145-mehrstufige-duplikaterkennung-zeitfenster-und-stern-ohne-bruecken.md) (Kanten
„praktisch identisch“/„ähnlich“, Stern)

## Kontext

`assign_duplicate_groups` wählt den Gewinner nach der Schärfe auf der `display`-Variante
(höchstens 2048 px); eine verkleinerte Kopie kann dabei schärfer messen als ihr Original. Die
Auflösung des Originals ist nirgends gespeichert. Jede Gruppe ist ein offener Fall, auch wenn alle
Mitglieder praktisch identisch sind.

## Entscheidung

### 1. Zwei Durchgänge: identische Sterne nach Auflösung, dann der bisherige Stern

Durchgang 1 baut Sterne **nur über identische Kanten**, Ordnung
`(pixel_count unbekannt, −pixel_count, Zeit nicht verlässlich, taken_at, photo_id)`: höchste
Auflösung, dann die ältere verlässliche Aufnahmezeit, zuletzt die kleinere `photo_id`. Pfad und
Dateiname gehen nie ein. Ein Foto ohne identischen Partner bleibt frei. Durchgang 2 ist der Stern
aus ADR 0145 Punkt 4 (identische und ähnliche Kanten, `(−sharpness, photo_id)`) über die
verbliebenen freien Fotos.

Rückgabe: `loser → winner` wie bisher, dazu die Menge der Gewinner aus Durchgang 1. Jede Gruppe
aus Durchgang 1 ist bauartbedingt vollständig identisch; eine teilweise automatische Gruppe
entsteht nicht.

*Ausfallrichtung:* Eine Kopie mit kleinerer Auflösung wird nie Gewinner ihres identischen Sterns.
Ein ähnliches Foto, das früher mit identischen Kopien in einem Stern lag, kann nach Durchgang 1
ungruppiert bleiben — es läuft dann weiter (falsch-negativ, ADR 0145 S3).

### 2. Auflösung ist eine Spalte am Foto, geschrieben vom Scan

`Photo.pixel_count: int | None` (Breite × Höhe nach `exif_transpose`) und
`Photo.pixel_count_probed: bool` (NOT NULL, `server_default false` in Modell und Migration).

- Voller Arbeitsposten: aus `image.size` in `thumbnails.py::generate_variants`, derselben
  Dekodierung wie das Seitenverhältnis; unbedingt geschrieben, auch zurück auf `None`.
- Unveränderte Datei ohne Merker: ein eigener Nachhol-Posten liest **nur** die Maße aus dem
  bestehenden Range-Fenster (`_EXIF_RANGE_BYTES`; Pillow liest JPEG-SOF, PNG-IHDR und HEIF-`ispe`
  aus dem Kopf, ohne zu dekodieren) und schreibt **keine** andere Spalte. Zeit, Ort und Kamera
  eines unveränderten HEIC bleiben unberührt. Der Merker wird auch ohne Fund gesetzt.

*Ausfallrichtung:* Kein Wert heißt „Auflösung unbekannt“ — keine automatische Entscheidung, nie
eine geschätzte Zahl. Ohne Merker läse jeder Scan den Bestand erneut über das Netz.

### 3. Die automatische Entscheidung ist ein Lauf-Merker am Verlierer, keine Entscheidungszeile

`PhotoScore.auto_decided: bool` (NOT NULL, `server_default false`). `photo_duplicate_decisions`
bleibt allein Nutzerentscheidung; kein Lauf schreibt oder löscht dort.

- `run_project_scoring` setzt den Merker projektweit auf `false` **im selben Commit**, der den
  `RUNNING`-Lauf anlegt.
- Gesetzt wird er **nur im SUCCESS-Commit**, für die Verlierer eines Sterns aus Durchgang 1, wenn
  der Gewinner `sharpness ≥ SHARPNESS_REJECT_THRESHOLD` hat, `pixel_count` aller Mitglieder
  bekannt ist und kein Mitglied eine Entscheidungszeile trägt — die letzte Bedingung als
  `NOT EXISTS` in derselben `UPDATE`-Anweisung, nicht aus einem früher gelesenen Stand.
- Jeder Nutzer-Schreibweg über `_write` (Einzel- und Gruppenweg) setzt den Merker für alle
  Mitglieder des Sterns in derselben Transaktion auf `false`; die Menge bestimmt der Server aus der
  projektgebundenen Kantenliste.

Invariante: Der Merker steht nur an Verlierern (`duplicate_of IS NOT NULL`,
`suggested_status = REJECTED`) eines Sterns ohne Entscheidungszeile, und nur nach dem erfolgreichen
Lauf, der ihn gesetzt hat. Bei Verletzung gälte eine Gruppe zugleich als automatisch und als vom
Nutzer entschieden, oder ein fehlgeschlagener Lauf hielte eine automatische Entscheidung fest, die
kein Lauf mehr feststellt.

### 4. „Offen“ schließt den Merker aus; das Überlebens-Prädikat bleibt unverändert

`duplicates.py::has_open_suggestion()` und `has_open_suggestion_for()` erhalten das UND-Glied
`auto_decided = false` — nur dort, nie an einer Aufrufstelle. Damit verlassen automatisch
entschiedene Aufnahmen `open_count`, Filter `suggested`, `PhotoOut.suggestion`, Gruppen- und
Projektabschluss ohne weitere Änderung.

`survives_ausschuss()`/`survives_ausschuss_for()` bleiben unverändert; ein Verlierer ohne Zeile
überlebt schon heute nicht. Untersagt ist, den Merker ins Überlebens-Prädikat zu ziehen: Er wäre
eine zweite, laufabhängige Grenze des Homeservers (ADR 0104 Punkt 3), und ein fehlgeschlagener
Lauf änderte dann die Cloud-Kandidatenmenge.

Das Gate-Autoset des Laufs gilt bei null **offenen** Vorschlägen (abgelehnte minus automatisch
entschiedene Aufnahmen); `suggestions_found` zählt weiter alle Abgelehnten.

### 5. Die Kennzeichnung kommt vom Server, je Gruppe

`duplicates.py` bestimmt die automatisch entschiedenen Repräsentanten aus Kantenliste und Merker.
`DuplicateLink` bleibt ohne Entscheidungsauskunft; die Gruppenreihenfolge hängt weiter an keinem
Wert, den eine Entscheidung ändert. Je Aufnahme bleibt `effective_decision ∈ {keep, discard}`;
`decision` bleibt die gespeicherte Nutzerzeile.

## Konsequenzen

- Migration `8c0f0296e1cd` (Vorgänger `6299223059c8`): drei Spalten, kein Backfill, keine neue
  Tabelle; `project_deletion.py` bleibt unberührt.
- ADR 0145 Punkt 4 (Sortierschlüssel) und ADR 0111 Punkt 1 (Satz „unterscheidet nicht mehr, ob ein
  Zustand vom Automaten oder vom Nutzer stammt“) erhalten den Vermerk `**Teilweise abgelöst:**`
  auf diese ADR. ADR 0104 bleibt unverändert.
- Bestandsprojekte erhalten automatische Entscheidungen erst nach einem Scan (Nachhol-Posten) und
  einem anschließenden Ausschuss-Lauf.
- Der Demo-Bestand bekommt eine dritte, automatisch entschiedene Gruppe; die Gruppen 7 und 3
  bleiben offen. `docs/architecture.md`, Sicherheitskonzept und Skill `browse-app` ziehen nach.
