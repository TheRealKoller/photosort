# 0110 - Das Seitenverhältnis ist ein Serverdatum, und die Rasterkachel steht neben der Fotokarte

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** [GitHub-Issue #489](https://github.com/TheRealKoller/photosort/issues/489), Spec 0489

**Umfang:** leicht über dem Richtwert von rund 100 Zeilen, weil die Entscheidung fünf Punkte trägt
und die Ausfallrichtung bei unbekanntem Seitenverhältnis ohne ihre beiden Randfälle nicht eindeutig
anwendbar ist.

## Kontext

Die Fotoübersicht soll jedes Bild vollständig zeigen und die Bilder zeilenweise justiert setzen:
Alle Bilder einer Zeile stehen auf gemeinsamer Höhe, die Zeile füllt die verfügbare Breite bündig
aus, und um ein Bild entsteht weder Beschnitt noch Rand. Zwei Randbedingungen schneiden die
Lösungsmenge:

- Ein justiertes Raster kann seine Zeilen erst umbrechen und skalieren, wenn die Seitenverhältnisse
  **aller** Bilder der Zeile bekannt sind. PhotoSort lädt Bilder über `PhotoImage` authentifiziert
  als Blob; das Verhältnis eines Bildes steht damit erst fest, nachdem es geladen ist. Ein Layout,
  das darauf wartet, ordnet sich bei jedem eintreffenden Bild neu.
- Die Foto-Karte `components/PhotoCard.tsx` lebt heute genau einmal und wird von vier Ansichten
  benutzt (Raster, Kuratierung, gemeinsame Endauswahl, Duplikatsvergleich). Sie beschneidet
  quadratisch, trägt Kartenkörper, Statuszeile und Fußzeile. Drei der vier Ansichten sollen
  unverändert bleiben.

## Entscheidung

### 1. Das Seitenverhältnis wird persistiert und mit jedem Foto ausgeliefert

`Photo` bekommt die Spalte `aspect_ratio: float | None` — Breite geteilt durch Höhe, **nach**
Anwendung der EXIF-Orientierung, also so, wie das Bild gezeigt wird. `PhotoOut.aspect_ratio` reicht
sie auf **allen** Lesepfaden aus, nicht nur auf dem der Rasteransicht; ein je Abfragemodus
verschiedenes `PhotoOut` wäre eine zweite, driftende Abbildung desselben Fotos.

`NULL` heißt „nicht bekannt" und ist ein regulärer Zustand, kein Fehler: Jeder Lesepfad antwortet
für ein solches Foto fehlerfrei, und die Oberfläche hat dafür eine benannte Ausfallrichtung
(Punkt 4).

### 2. Gespeichert wird das Verhältnis, nicht Breite und Höhe

Zwei Pixelmaße wären an genau einer der beiden Schreibstellen (Punkt 3) eine Unwahrheit: Die
Nachhol-Runde liest aus dem zwischengespeicherten Vorschaubild und kennt die Maße des Originals
nicht, nur sein Verhältnis. Ein Feldpaar, dessen Bedeutung davon abhängt, welcher Schreibweg es
gefüllt hat, ist an jeder Lesestelle eine Falle.

Ein Wert außerhalb von `0.05 <= aspect_ratio <= 20.0` wird nicht gespeichert (`NULL`): Die
Zeilenhöhe entsteht aus der Summe der Verhältnisse einer Zeile, und ein entartetes Verhältnis zöge
die ganze Zeile auf eine unbrauchbare Höhe, nicht nur sein eigenes Bild.

### 3. Zwei Schreibstellen: der Scan und eine lokale Nachhol-Runde

- **Der Scan** ist der Regelweg. `thumbnails.py::generate_variants` kennt das Bild nach
  `exif_transpose` bereits und gibt sein Verhältnis zurück; der Wert reist über `ScanExifResult` in
  den sequentiellen Teil von `_process_scan_block` und wird dort geschrieben. Es entsteht kein
  zusätzlicher Download und kein zusätzliches Dekodieren.
- **Die Nachhol-Runde** füllt den Bestand. Sie läuft zu Beginn eines Projekt-Scans über die Fotos
  des Projekts mit `aspect_ratio IS NULL` und liest das Verhältnis aus dem **lokal
  zwischengespeicherten Vorschaubild** — ohne Netz, ohne OpenCloud-Abruf, ohne das Original.
  Fehlt die Cache-Datei oder ist sie nicht lesbar, bleibt der Wert `NULL` und wird beim nächsten
  Scan erneut versucht.

Es gibt **keinen** Merker-Spalte nach dem Muster von `camera_probed`. Der Merker dort verhindert
einen wiederholten Netzzugriff je Bestandsfoto; hier kostet ein erneuter Versuch einen lokalen
Dateizugriff, und `aspect_ratio IS NULL` ist bereits selbst die Abbruchbedingung.

### 4. Das justierte Raster wird gerechnet, nicht eingekauft

Die Zeilenaufteilung entsteht in einer reinen Funktion im Frontend (Verhältnisse, Containerbreite,
Zwischenraum, Zielzeilenhöhe hinein — Zeilen mit je Bild einer Breite und einer gemeinsamen Höhe
heraus). Es kommt **keine** Layout-Bibliothek hinzu: Der Kern ist eine zeilenweise Aufteilung mit
anschließender Skalierung auf die Restbreite, und er ist als reine Funktion ohne DOM vollständig
testbar — eine Bibliothek brächte dafür eine dauerhaft zu pflegende Abhängigkeit samt eigener
DOM-Annahmen mit.

Verbindlich für diese Funktion:

- **Ein Bild ohne bekanntes Verhältnis** wird mit `3:2` eingeplant und innerhalb seines Feldes
  eingepasst (`object-fit: contain`). Es bekommt dadurch einen Rand — das ist die bewusste
  Ausfallrichtung: Beschneiden ist ausgeschlossen, und ein Rand an einem einzelnen Bild ist
  sichtbar falsch statt still falsch.
- **Die letzte, unvollständige Zeile wird nicht aufgezogen.** Sie behält die Zielzeilenhöhe und
  steht linksbündig. Eine auf volle Breite gestreckte Einzelaufnahme wäre um ein Vielfaches höher
  als jede Zeile über ihr.

### 5. Die Rasterkachel ist eine eigene Komponente, keine Ausprägung der Fotokarte

`components/PhotoCard.tsx` bleibt **unverändert** und behält seine drei Aufrufstellen (Kuratierung,
gemeinsame Endauswahl, Duplikatsvergleich). Die Rasteransicht bekommt eine eigene Kachel neben den
bestehenden `*PhotoTile`-Komponenten.

Die beiden teilen nichts, was eine Prop trennen könnte: Die Fotokarte ist ein Kartenkörper mit
fester quadratischer Bildfläche, sichtbarer Statuszeile und Fußzeile; die Rasterkachel ist eine
Bildfläche mit eigenem Seitenverhältnis, ohne Körper, ohne Fußzeile, mit Zeichen in der Bildecke
und einer erst auf Anforderung eingeblendeten Zeile. Eine Prop, die jede einzelne dieser
Festlegungen umkehrt, sind zwei Komponenten in einer Datei.

Damit fällt die Design-System-Festlegung „die Foto-Karte lebt genau einmal und wird von allen
Foto-Ansichten benutzt" für die Rasteransicht, und ebenso die Festlegung „das Kennzeichen sitzt im
Kartenkörper, nicht in der Bildecke" — letztere gilt unverändert für die Fotokarte und ausdrücklich
nicht für die Rasterkachel, deren Bildfläche kein Textbadge trägt, sondern zwei Zeichen.

## Konsequenzen

- Eine Alembic-Migration kommt hinzu (additive, nullbare Spalte; keine Datenwanderung).
- Bestandsfotos zeigen ihr richtiges Verhältnis erst nach dem nächsten Projekt-Scan. Bis dahin
  greift die Ausfallrichtung aus Punkt 4; die Ansicht ist benutzbar, nur nicht randfrei.
- Der Demo-Bestand (`demo_state.py`) erzeugt heute ausschließlich Bilder im Format 4:3. Ein
  justiertes Raster ist an lauter gleichen Verhältnissen von einem Spaltenraster nicht zu
  unterscheiden; der Demo-Bestand muss deterministisch gemischte Hoch-, Quer- und Breitformate
  liefern, sonst prüft der E2E-Prüfstack die Zusage nicht.
- Der E2E-Spec `grid-columns.spec.ts` misst für die Fotoübersicht heute eine feste Spaltenzahl und
  gleiche Kachelbreiten je Zeile. Beides gilt dort nicht mehr und wird durch die Zusagen des
  justierten Rasters ersetzt (gemeinsame Höhe je Zeile, bündiges Zeilenende); für den
  Duplikatsvergleich bleibt der Spec unverändert.
