# 0145 - Mehrstufige Duplikaterkennung: Kandidatenstufe, Zeitfenster und Stern ohne Brücken

**Status:** Accepted
**Datum:** 2026-11-09
**Bezug:** Issue [#637](https://github.com/TheRealKoller/photosort/issues/637), Spec
[`0637`](../features/0637-duplikatgruppen-nur-echte-duplikate.md); ADR
[`0006`](./0006-local-scoring-datamodel.md) (Pillow, keine neue Abhängigkeit), ADR
[`0104`](./0104-ausschuss-entscheidung-uebersteuert-den-automaten.md) (Stern, Entscheidungstabelle,
Überlebens-Prädikat), ADR
[`0111`](./0111-vergleichsansicht-zeigt-das-praedikat-nicht-die-entscheidungszeile.md)
(angezeigter Zustand)

Umfang über dem Richtwert: Stufenplan, Metrik, Sternregel, Zeit-Herkunft und die Fortwirkung
früherer Entscheidungen tragen je eine eigene Ausfallrichtung; sie stehen vollständig, weil sie
nur gemeinsam die Zusage „nur echte Duplikate“ ergeben.

## Kontext

Die Duplikatstufe verglich alle Foto-Paare über die Hamming-Distanz ihrer 64-Bit-dHashes
(Schwelle 6) und fasste sie transitiv per Union-Find zusammen. Eine Kette ähnlicher Aufnahmen
wurde dadurch zu einer Gruppe, obwohl nur benachbarte Paare tatsächlich ähnlich waren. Jeder
Nicht-Gewinner erhält `duplicate_of` und `suggested_status = REJECTED` und läuft nicht in
Kriterien, Kategorien und Album; bei falschen Gruppen gehen gute Fotos still verloren.

Die Erkennung muss drei Dinge zugleich leisten: ähnliche Bilder nur im Zeitfenster gruppieren,
praktisch identische Bilder zeitunabhängig erkennen und jede Gruppe flach um den Gewinner bauen.
Sie bleibt lokal, ohne neue Abhängigkeit, und der Scoring-Lauf öffnet die `display`-Variante nicht
erneut.

## Entscheidung

### 1. Drei Stufen statt einer transitiven Schwelle

**Stufe 1 — Kandidaten:** grober 64-Bit-dHash, Hamming
`≤ DUPLICATE_CANDIDATE_HAMMING = 12`, Kandidatensuche per Band-Bucketing.
**Stufe 2 — feiner dHash:** 256 Bit aus einem 17×16-Graustufenraster.
**Stufe 3 — Grauwertgitter:** 32×32, z-normalisiert, mittlere absolute Differenz.

Die feinen Signaturen entstehen im selben `_compute_photo_metrics`-Aufruf wie Schärfe, Belichtung
und grober dHash und werden nicht persistiert.

*Verworfen:* eine einzelne strengere Schwelle; Union-Find mit Nachfilter (die Kette entsteht vor
dem Filter); `imagehash`/OpenCV (neue Abhängigkeit); Persistenz der feinen Signatur (Migration und
Speicherkosten ohne Nutzen, da jeder Lauf neu rechnet).

*Ausfallrichtung:* Ein verpasstes Kandidatenpaar bleibt ungruppiert, das Foto bleibt im Bestand.
Ein falscher Kandidat kostet nur die genaueren Stufen.

### 2. „Praktisch identisch“ ist eine AND-Bedingung aus Struktur und Pixeln

```text
fine_hamming(a,b) ≤ IDENTICAL_FINE_HAMMING = 16 von 256
UND
grid_mad(a,b) ≤ IDENTICAL_GRID_MAD = 0.06   (z-normalisiert, 32×32)
```

Sind beide Gitter varianzfrei, entscheidet die rohe mittlere Grauwertdifferenz
`≤ IDENTICAL_FLAT_MAD = 1.0`; ist nur eines varianzfrei, ist das Paar nicht identisch.

Die z-Normierung entfernt globale Helligkeits- und Kontraständerungen, wie sie beim Neuspeichern
oder Verkleinern entstehen, aber keine geometrische Verschiebung. Genau das trennt eine Kopie von
einer Serienaufnahme mit verschobenem Ausschnitt.

*Verworfen:* rohe Pixeldifferenz ohne Normierung (eine Kopie mit anderem Kontrast fiele durch);
nur dHash (zu grob); „jede Bit-Abweichung = kein Duplikat“ (JPEG-Rauschen erzeugt falsche
Negative).

*Ausfallrichtung:* Ein echtes Duplikat, das eine Bedingung verfehlt, wird nicht gruppiert
(falsch-negativ, sicher). Ein falsch-positives „identisch“ würde ein gutes Foto verstecken; deshalb
zwei unabhängige Prüfungen und enge Startwerte. Der Restfall — ein realer Burst mit sehr kleiner
Verschiebung besteht beide Grenzen — wird am echten Bestand geprüft und sonst durch Nachziehen der
Grenzen geschlossen.

### 3. „Ähnlich“ gilt nur im Zeitfenster

```text
coarse_hamming ≤ DUPLICATE_SIMILAR_HAMMING = 8 von 64
UND fine_hamming ≤ DUPLICATE_SIMILAR_FINE_HAMMING = 64 von 256
UND beide taken_at_trusted
UND |a.taken_at − b.taken_at| ≤ DUPLICATE_SIMILAR_TIME_WINDOW = 15 min
```

Das Fenster wird paarweise geprüft, nicht nur gegen den Gewinner: Zwei ähnliche Mitglieder eines
Sterns dürfen nie weiter als das Fenster auseinanderliegen. Die 15 Minuten sind ein konservativer
Startwert in der Größenordnung des bestehenden `selection.py::SIMILARITY_TIME_WINDOW`; die
Bedeutung ist eine andere, die Konstante bleibt getrennt.

*Verworfen:* Zeitvorfilter schon in Stufe 1 (verlöre zeitunabhängige Kopien); Fenster nur gegen den
Gewinner (zwei Mitglieder könnten 2× Fenster auseinanderliegen); Union-Find über Similar-Kanten
(erzeugt die Brücken).

*Ausfallrichtung:* Ein ähnliches Paar außerhalb des Fensters wird nicht gruppiert
(falsch-negativ, sicher). Ein zu großes Fenster würde verschiedene Anlässe verbinden.

### 4. Der Stern wird gierig um den Gewinner gebaut, nicht transitiv

**Teilweise abgelöst:** Für **praktisch identische** Gruppen gilt seit Spec
[`0639`](../features/0639-automatisch-entschiedene-duplikatgruppen.md)/ADR
[`0146`](./0146-automatisch-entschiedene-duplikatgruppen.md) eine andere Gewinnerreihenfolge —
Auflösung (`pixel_count`) vor älterer verlässlicher Aufnahmezeit vor kleinerer `photo_id`. Die
Schärfe bleibt der Vorschlag für **ähnliche** Serien; die verkleinerte `display`-Variante macht sie
bei Kopien unzuverlässig. Sternform und direkte Kante gelten unverändert.

`assign_duplicate_groups` sortiert absteigend nach `(-sharpness, photo_id)`. Das erste freie Foto
wird Gewinner; aufgenommen werden nur freie Fotos mit **direkter** Kante zum Gewinner. Für zwei
ähnliche (nicht identische) Mitglieder gilt zusätzlich paarweise das Zeitfenster. Jedes Mitglied
wird genau einem Stern zugeordnet; der Gewinner zeigt nirgendwohin.

*Verworfen:* Union-Find plus „alle Komponentenmitglieder auf den Gewinner“ (Brücken); „jedes Foto
auf seinen ähnlichsten Nachbarn“ (mehrere konkurrierende Sterne, kein eindeutiger Gewinner);
Cliquenprüfung über alle Mitglieder (zu streng, zerlegt echte Bursts).

*Ausfallrichtung:* Ein Kettenmitglied, das nur über ein anderes Mitglied am Gewinner hängt, bleibt
ungruppiert und läuft weiter. Eine falsche Gruppe entsteht nicht.

### 5. Fehlende Aufnahmezeit ohne Migration

`Photo.taken_at` und `taken_at_original` sind `NOT NULL`; der Scan fällt bei fehlendem EXIF auf
`last_modified` zurück. Ein gespeicherter Herkunftsmerker fehlt. Die Erkennung leitet „Zeit
unsicher“ konservativ ab:

```python
def taken_at_is_trusted(taken_at_original: datetime, last_modified: datetime) -> bool:
    return taken_at_original != last_modified
```

Exakte Ungleichheit, keine Toleranz, keine Rundung. Bei unsicherer Zeit ist nur „praktisch
identisch“ eine Kante; „ähnlich“ nie. Die Fensterprüfung liest `taken_at` (kamerakorrigiert),
nicht die Herkunftswerte.

*Verworfen:* eine neue Spalte/Migration. Für Bestandszeilen ohne Re-Scan wäre sie bis zum
vollständigen Scan ebenfalls nur „unbekannt“, aber mit Migrations-, Schreibpfad- und
Re-Scan-Kosten. Der Vergleich ist für den gefährlichen Fall (fehlendes EXIF) exakt und für den
harmlosen Fall (EXIF-Zeit zufällig gleich mtime) konservativ.

*Ausfallrichtung:* Bei Gleichheit werden ähnliche Bilder nicht gruppiert — falsch-negativ, sicher.
Nie entsteht eine Similar-Gruppe ohne verlässliche Zeit.

### 6. Frühere Entscheidungen bleiben wirksam und werden sichtbar

ADR 0104 Punkt 3 bleibt unverändert: `discard` wirkt unbedingt, `keep` nur solange
`duplicate_of IS NOT NULL`. Verschwindet eine Gruppe, wird ein altes `keep` wirkungslos, ein altes
`discard` wirkt weiter. Ergänzt wird:

- `AusschussPhotoEntryOut.reason = "earlier_decision"`, wenn weder `duplicate_of` noch
  `suggested_status` vorliegt, aber eine Entscheidungszeile existiert. Die bisherige Ableitung
  würde dort fälschlich `low_quality` behaupten.
- `AusschussPhotoEntryOut.decision_effective: bool | None` aus
  `duplicates.py::decision_effective_for`: `None` ohne Zeile; `true` für `discard`; für `keep`
  genau dann `true`, wenn `duplicate_of IS NOT NULL`. Das ist die Wirksamkeitsbedingung der
  **gespeicherten** Zeile aus ADR 0104 Punkt 3, nicht die Gleichheit mit dem angezeigten Zustand.
  Ein veralteter `keep` ohne Gruppe ist deshalb `false`, obwohl das Foto ohnehin überlebt.
- Der Einzel-Schreibweg akzeptiert jede Aufnahme des Ausschuss-Bestands
  (`duplicates.py::has_ausschuss_entry`, projektgebunden), nicht nur „Gruppe oder offener
  Vorschlag“. Sonst wäre ein alter `discard` sichtbar, aber nicht widerrufbar.

Der Gruppen-Stapel braucht kein Wirksamkeitsfeld: Dort steht keine verschwundene Gruppe. Ein
`keep` auf dem Gewinner einer bestehenden Gruppe wäre `false` (redundant, nicht schädlich); der
Stapel zeigt es über `decision_counts`.

*Verworfen:* automatische Entwertung alter `discard`-Zeilen. Die Tabelle speichert keine Herkunft
(Duplikat gegen Unschärfe); Bestandszeilen ließen sich nicht unterscheiden, und absichtlich
verworfene Unschärfe-Fotos würden wieder auferstehen. *Verworfen:* die enge Vorbedingung
beibehalten — sie macht die stille Dauerwirkung unkorrigierbar.

*Ausfallrichtung:* Bliebe die Vorbedingung eng, würde ein guter Bestand dauerhaft ausgeschlossen.
Bliebe der Grund `low_quality`, wäre der Eintrag falsch begründet.

### 7. Kalibrierung wird gemessen, nicht behauptet

`duplicate_probe.py` ist rein lesend und rechnet über derselben gemessenen Teilmenge: bisheriges
Verfahren, neues Verfahren und einen Gegenlauf, der `taken_at_trusted` ignoriert. Es gibt nur
Projekt-Id, Lauf-Id, Anzahlen, Größenverteilungen, größte Gruppe, größte Spanne ähnlicher
Mitglieder und den Anteil unsicherer Zeiten aus. Die Zahlen stehen im `## Messergebnis` der Spec
und im PR-Bericht.

*Verworfen:* Kalibrierung nur über synthetische Pillow-Bilder; Ausgabe von Einzelwerten oder
Pfaden; Verzicht auf den Gegenlauf (die Größe der falsch-negativen Zeit-Menge bliebe unbekannt).

*Ausfallrichtung:* Fehlt der Cache eines Fotos, wird es als übersprungen gezählt und aus beiden
Läufen entfernt; es wird keine Zahl geschätzt und keine Gruppe erfunden.

### 8. Laufzeit ohne Trefferverlust

Stufe 1 nutzt `int`-Hashes, `int.bit_count()` und Band-Bucketing: 64 Bit in 13 disjunkte Bänder
(= Hamming-Grenze + 1); bei Hamming `≤ 12` stimmt mindestens eines der 13 Bänder exakt überein
(Schubfachprinzip). Innerhalb der Buckets wird die volle Distanz geprüft, Paare werden
dedupliziert. Die Trefferzusage ist exakt.

*Verworfen:* naives `O(n²)` über alle Paare; ungefähre Locality-Sensitive-Hashes
(Trefferverlust ohne Not).

## Konsequenzen

- `scoring.py::assign_duplicate_clusters`, `DuplicateCandidate`, `DUPLICATE_HAMMING_THRESHOLD` und
  `hamming_distance` entfallen; `compute_dhash` bleibt für `PhotoScore.phash`. Die feine Signatur
  wird nicht persistiert.
- `run_project_scoring` ändert nur die Duplikatstufe: `duplicate_of` und `suggested_status` werden
  weiterhin nur für Verlierer geschrieben; `cluster_key`, `suggestions_found` und das Gate-Autoset
  bleiben definitionsgleich.
- `duplicates.py` behält Stern und Überlebens-Prädikat; neu ist `decision_effective_for`.
- `AusschussPhotoEntryOut` bekommt `reason = "earlier_decision"` und `decision_effective`; der
  Einzel-Schreibweg akzeptiert den gesamten Ausschuss-Bestand. Das ist eine additive Antwortform,
  keine neue Tabelle.
- `duplicate_probe.py` bleibt als Messkommando im Repo; `docs/setup.md` dokumentiert Aufruf und
  Datenschutz, `docs/architecture.md` zieht Scoring- und Ausschuss-Abschnitt nach.
- ADR 0104 bleibt `Accepted`; ihre Konsequenz-Zeile „Die Duplikaterkennung bleibt unverändert“
  wird redaktionell auf diese ADR gezogen.
