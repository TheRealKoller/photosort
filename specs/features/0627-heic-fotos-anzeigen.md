# 0627 - HEIC-Fotos anzeigen

**Status:** Implemented ([PR #629](https://github.com/TheRealKoller/photosort/pull/629))
**Erstellt:** 2026-11-08
**Bezug:** [Issue #627](https://github.com/TheRealKoller/photosort/issues/627), ADR
[`0142`](../decisions/0142-heic-dekodierung-ueber-pillow-heif.md)

## Ziel

HEIC/HEIF-Fotos, die der Scan bereits als Bilddatei annimmt, sollen dekodiert und wie JPEG/PNG
angezeigt, bewertet und klassifiziert werden. Heute fehlt Pillow das HEIF-Plugin: `Image.open`
scheitert, der Best-effort-Block schluckt den Fehler, es entstehen keine Cache-Varianten, und der
Bild-Endpunkt antwortet dauerhaft 404. Dieselbe Lücke lässt EXIF, Bewertung und Klassifizierung
für diese Fotos ausfallen.

## User Story

Als Nutzer von PhotoSort möchte ich HEIC-Aufnahmen im Raster und in der Einzelbildansicht sehen und
wie JPEG/PNG bewerten lassen, damit ich sie vor dem Import nicht umwandeln muss.

## Akzeptanzkriterien

- [ ] `generate_variants` schreibt für `.heic` und `.heif` dieselben beiden JPEG-Varianten wie für
  JPEG/PNG: `_thumbnail.jpg` (lange Kante ≤ 400 px) und `_display.jpg` (lange Kante ≤ 2048 px),
  beide im Modus `RGB`/`L` abgelegt, mit gesetztem Seitenverhältnis als Rückgabewert.
- [ ] `worker.py::_EXIF_CANDIDATE_EXTENSIONS` enthält `.heic` und `.heif`. Die drei Extraktoren
  lesen Aufnahmedatum, GPS-Koordinate und Kamera aus demselben 128-KiB-Range-Fenster wie bei JPEG.
  Ohne verwertbaren EXIF-Wert gilt unverändert der Rückfall: WebDAV-Änderungsdatum, keine
  Koordinate, keine Kamera.
- [ ] HEIC/HEIF-Fotos nehmen an Bewertung, Ranking, Klassifizierung und Duplikat-Erkennung teil
  und zählen in den Fortschritts- und Statistikzahlen wie JPEG/PNG, weil die `display`-Cache-
  Variante vorhanden ist und kein Formatfilter existiert. Die bestehenden Aufrufstellen bleiben
  unverändert.
- [ ] Eine nicht dekodierbare Datei (beschädigt, nicht unterstützte Spielart) bricht den Scan
  nicht ab: keine Cache-Datei, keine Ausnahme nach außen, Bild-Endpunkt 404. Der Scan endet
  weiterhin `SUCCESS`, alle anderen Fotos des Ordners werden vollständig eingelesen.
- [ ] Bestehende Projekte bleiben unverändert: Ein unveränderter Etag führt für HEIC/HEIF auch
  ohne gesetztes `camera_probed` zu keiner Nachhol-Verarbeitung — kein Range-Request, kein
  Download, keine geänderten Foto-Felder. Repariert wird nur durch Neu-Einlesen des Projekts.
- [ ] Der Client erhält ausschließlich JPEG-Cache-Varianten; keine HEIC-Rohdaten, kein neuer
  Content-Type.

## Datenmodell-Bezug

Keine Änderung. `Photo.aspect_ratio` wird für HEIC über denselben Schreibweg gesetzt wie für JPEG
(Rückgabewert von `generate_variants`).

## Architektur / Umsetzung

1. **Abhängigkeit:** `pillow-heif>=1.8.1` in `backend/pyproject.toml`. Die cp312-Wheels für
   manylinux_2_28 x86_64 und aarch64 (je ca. 6 MB, BSD-3-Clause) bringen libheif mit; kein
   apt-Paket, kein zusätzlicher Build-Schritt im `python:3.12-slim`-Image (verifiziert 2026-11-08
   gegen PyPI).
2. **Registrierung an genau einer Stelle:** neues Modul `photosort/image_codecs.py` mit
   `pillow_heif.register_heif_opener(decode_threads=0)` auf Modulebene; importiert von
   `thumbnails.py` und `opencloud/exif.py`. API und Worker sind getrennte Prozesse, der
   Modulimport deckt beide. `decode_threads=0` schaltet die parallele Grid-Tile-Dekodierung ab
   (Sicherheitsauflage, siehe Security).
   Ein künftiger Dekodier-Einstiegspunkt, der Pillow ohne dieses Modul importiert, verliert HEIC
   still — die Tests unten belegen den Weg über `generate_variants` und die Extraktoren.
3. **Pillow bleibt die einzige Bild-I/O-Bibliothek:** kein libheif-CLI, kein ImageMagick, kein
   Subprozess. `generate_variants` bleibt inhaltlich unverändert; pillow-heif liefert ein
   Pillow-Bild, `exif_transpose` und die RGB-Konvertierung greifen wie bei JPEG.
4. **EXIF-Kandidaten erweitern:** `.heic`/`.heif` in `_EXIF_CANDIDATE_EXTENSIONS`. Das Fenster
   `_EXIF_RANGE_BYTES = 131_072` bleibt. Verifiziert am 2026-11-08 mit einer echten
   iPhone-13-mini-HEIC: EXIF-Magic bei Byte 1529, `DateTimeOriginal`, `Make`/`Model` und GPS aus
   den ersten 128 KiB lesbar; `generate_variants` erzeugt daraus 400×300 und 2048×1536 als JPEG.
   Der Test mit einer erzeugten Datei samt EXIF hält den Weg zusätzlich fest.
5. **Kein Nachhol-Pfad:** Bestehende Projekte werden nicht erneut verarbeitet — ein unveränderter
   Etag mit gesetztem `camera_probed` wird weiterhin übersprungen. Für `.heic`/`.heif`
   überspringt `worker.py::_classify_scan_entries` einen unveränderten Etag auch bei
   `camera_probed=False`; die einmalige Kamera-Nachhol-Runde gilt für sie nicht, weil sie sonst
   die vor dieser Story nie gelesenen HEIC-Bestandsfotos rückwirkend auslesen würde. Für JPEG/PNG
   bleibt die Nachhol-Runde unverändert. Vorgesehen ist, das Projekt neu anzulegen und alles neu
   einzulesen (Stakeholder-Entscheidung).

## UI/UX

Nicht relevant: keine neue Oberfläche, kein neuer Zustand, keine geänderte Interaktion. Der
bestehende 404-Platzhalter „Bild wird noch verarbeitet." bleibt unverändert — er trifft künftig
nur noch wirklich undekodierbare Dateien.

## Security

- **Neue Angriffsfläche:** ein zusätzlicher nativer Decoder (libheif) für fremde Dateien. Er wird
  ausschließlich über Pillow erreicht; die bestehende Regel „Pillow ist die alleinige
  Bild-I/O-Bibliothek" bleibt strukturell erhalten, es entsteht kein zweiter Dekodierpfad über
  CLI oder Subprozess.
- **Fehlergrenze unverändert:** jeder Dekodier-/Schreibfehler endet im breiten Best-effort-Block
  von `generate_variants` als `None`; `Image.DecompressionBombError` bleibt abgedeckt.
- **Auslieferung unverändert:** der Bild-Endpunkt liefert nur die JPEG-Cache-Varianten; HEIC wird
  nie an den Client gesendet.
- **Mitigation GHSA-35mc-3887-rr37:** pillow-heif 1.8.1 bündelt libheif 1.23.6, das beim
  parallelen Grid-Tile-Decoding einen Heap-Use-after-free hat (High, CVSS 7.5; Auslöser ist
  gewöhnliches Dekodieren einer fremden Datei, auch beim Thumbnailing). Die Registrierung mit
  `decode_threads=0` deaktiviert genau diesen Pfad (Workaround des Advisorys,
  `heif_context_set_max_decoding_threads(ctx, 0)`); ein Test im frischen Prozess belegt den Wert.
- **Restrisiko:** CPU-Amplifikation über abgeleitete Bilder bleibt bis libheif 1.23.7 möglich, das
  erst mit pillow-heif 1.9.0 kommt (am 2026-11-08 nicht auf PyPI). Der Dienst verarbeitet
  ausschließlich Dateien aus dem eigenen OpenCloud-Speicher, es gibt keinen offenen Upload.
- **Sicherheitskonzept:** `specs/architecture/0003-securitykonzept.md` wird bei der Umsetzung um
  `pillow-heif` als lokale Bild-Abhängigkeit ergänzt (Supply-Chain-Eintrag, Prüfung der
  Wheel-Herkunft, Sicherheitsauflage und Restrisiko).

## Teststrategie

- `tests/test_thumbnails.py`: HEIC-Bytes im Test über pillow-heif erzeugen (kein Binär-Fixture im
  Repository), `generate_variants` aufrufen, beide Dateien und das Seitenverhältnis prüfen; die
  Ausgabe über Pillow öffnen und das Format `JPEG` feststellen.
- `tests/test_exif.py`: erzeugte HEIC-Datei mit gesetztem EXIF (`DateTimeOriginal`, GPS,
  `Make`/`Model`) — alle drei Extraktoren liefern die Werte. Ohne EXIF: Rückfall wie bei JPEG.
- Negativfall: kaputte HEIC-Bytes — `generate_variants` liefert `None`, schreibt keine Datei,
  wirft nicht; im Scan neben einem guten HEIC endet der Lauf `SUCCESS` und nur das gute Foto hat
  beide Cache-Varianten.
- Bestandsschutz: unverändertes HEIC/HEIF mit `camera_probed=False` — weder Range-Request noch
  Download, Foto-Felder unverändert (Klassifikation und Scan).
- Sicherheitsauflage: ein frischer Prozess, der nur `photosort.opencloud.exif` importiert, sieht
  `pillow_heif.options.DECODE_THREADS == 0`.
- Bestehende JPEG/PNG-Tests bleiben unverändert grün (Regression).
- Manueller Smoke vor dem PR: eine echte iPhone-HEIC durch `generate_variants` und in der App
  sichtbar; zusätzlich eine echte HEIC mit EXIF gegen die drei Extraktoren.

## Offene Fragen

Keine.

## Out of Scope

- Nachhol-Berechnung für Bestandsprojekte; das Projekt wird neu angelegt und neu eingelesen.
- RAW, AVIF, TIFF und Video.
- HEIC-Export oder HEIC-Auslieferung an den Browser.
- HDR-Tonemapping; es gilt die vorhandene RGB-Konvertierung.
