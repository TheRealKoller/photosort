# 0142 - HEIC-Dekodierung über pillow-heif

**Status:** Accepted
**Datum:** 2026-11-08
**Bezug:** [Issue #627](https://github.com/TheRealKoller/photosort/issues/627), Spec
[`0627`](../features/0627-heic-fotos-anzeigen.md)

## Kontext

`.heic` und `.heif` stehen in `opencloud/client.py::IMAGE_EXTENSIONS` und werden gescannt, aber
Pillow dekodiert ohne HEIF-Plugin nicht. Der Bildpfad (`thumbnails.py::generate_variants`) liefert
deshalb dauerhaft `None`, der Bild-Endpunkt 404, und auch die EXIF-Extraktoren bleiben für diese
Dateien leer, weil `worker.py::_EXIF_CANDIDATE_EXTENSIONS` nur JPEG nennt. Die betroffenen Fotos
sind im Projekt vorhanden, aber unsichtbar und unbewertet.

## Entscheidung

### 1. `pillow-heif` als einzige neue Abhängigkeit

`pillow_heif.register_heif_opener()` wird beim Import eines gemeinsamen Moduls
(`photosort/image_codecs.py`) registriert; `thumbnails.py` und `opencloud/exif.py` importieren
dieses Modul. Danach dekodiert `Image.open` HEIC/HEIF über dieselbe Pillow-API wie JPEG/PNG.

**Was gilt:** Pillow bleibt die alleinige Bild-I/O-Bibliothek des Projekts. **Wofür:** jeder
Dekodier- und EXIF-Pfad im Backend und im Worker. **Bei Verletzung:** ein zweiter I/O-Weg über
CLI, ImageMagick oder einen Subprozess ist untersagt — die strukturelle Abschirmung der
historisch CVE-trächtigen Decoder-Pfade ginge verloren.

### 2. HEIC/HEIF werden EXIF-Kandidaten

`.heic` und `.heif` kommen in `_EXIF_CANDIDATE_EXTENSIONS`. Gelesen wird aus demselben
128-KiB-Range-Fenster wie bei JPEG (`worker.py::_EXIF_RANGE_BYTES`). Am 2026-11-08 mit einer
echten iPhone-13-mini-HEIC verifiziert: EXIF liegt bei Byte 1529, `DateTimeOriginal`,
`Make`/`Model` und GPS sind aus den ersten 128 KiB lesbar. Ein nicht lesbares Fenster ergibt
unverändert „kein Wert", nie einen Scan-Abbruch.

### 3. Keine Sonderbehandlung im Bildpfad

`generate_variants`, `exif_transpose`, die RGB-Konvertierung und der Best-effort-`except`-Block
bleiben unverändert. Kein Format-Zweig, keine Fallunterscheidung nach Endung.

### 4. Kein Nachhol-Pfad für Bestandsprojekte

Unveränderte Fotos mit gesetztem `camera_probed` werden weiterhin übersprungen. Die Reparatur
bestehender Projekte ist ausdrücklich nicht Teil der Entscheidung; das Projekt wird neu angelegt
und neu eingelesen.

## Begründung

- **`pyheif`** verlangt ein systemweit installiertes libheif (apt) und bringt keinen eigenen
  Decoder mit; das wäre ein zusätzlicher Image-Build-Schritt und eine zweite Quelle für die
  libheif-Version. `pillow-heif` liefert libheif im Wheel mit.
- **ImageMagick/`heif-convert` als Subprozess** wäre ein zweiter Bild-I/O-Weg neben Pillow und
  widerspräche Entscheidung 1.
- **Dekodierung im Browser** ist auf Safari beschränkt; Backend-Bewertung und Klassifizierung
  brauchen das Bild ohnehin serverseitig, und die App liefert ausschließlich JPEG-Cache-Varianten.
- **Nur das in HEIC eingebettete Vorschaubild** rettet das Raster, aber nicht die
  Display-Auflösung (2048 px), die Bewertung oder die Klassifizierung; es wäre eine dauerhafte
  zweite Bildquelle mit schlechterer Qualität.
- **Verfügbarkeit:** `pillow-heif` 1.8.1 (BSD-3-Clause) liefert cp312-manylinux_2_28-Wheels für
  x86_64 und aarch64 mit gebündeltem libheif (verifiziert 2026-11-08 gegen PyPI). Das passt zum
  bestehenden `python:3.12-slim`-Image ohne apt-Paket.

## Konsequenzen

- Das Backend-Image wächst um ca. 6 MB je Architektur.
- Ein nativer Decoder für fremde Dateien kommt hinzu. Das Sicherheitskonzept führt `pillow-heif`
  als lokale Bild-Abhängigkeit; die bestehende Best-effort-Grenze (jede Exception → `None`, kein
  Scan-Abbruch) bleibt unverändert.
- Jeder Prozess, der Bilder dekodiert, muss das Registrierungsmodul importieren. Ein künftiger
  Einstiegspunkt, der nur Pillow importiert, verliert HEIC still; die Tests decken den Weg über
  `generate_variants` und die drei EXIF-Extraktoren ab, nicht die Existenz des Imports.
- Tests erzeugen HEIC-Dateien im Speicher über pillow-heif; es wird kein Binär-Fixture
  eingecheckt.
- Bestehende Projekte bleiben bis zum Neu-Einlesen ohne HEIC-Vorschauen (Entscheidung 4).
