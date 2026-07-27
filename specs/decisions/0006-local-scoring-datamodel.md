# 0006 - Datenmodell für automatische Fotobewertung (Phase A) und lokale Heuristiken ohne neue Abhängigkeit

**Status:** Accepted
**Datum:** 2026-07-27
**Bezug:** [`decisions/0002-hybrid-ai-scoring.md`](./0002-hybrid-ai-scoring.md), [`features/0003-automatic-best-photo-selection.md`](../features/0003-automatic-best-photo-selection.md)

## Kontext

ADR 0002 hat das zweiphasige Scoring bereits akzeptiert und ein künftiges `PhotoScore`-Modell skizziert. Beim Verfeinern von Spec 0003 zeigt sich, dass zwei konkrete Entscheidungen getroffen werden müssen, bevor implementiert werden kann:

1. **Wie wird ein automatischer Vorschlag von einer echten manuellen Bewertung unterschieden?** Das bestehende `Rating`-Modell (Spec 0002, bereits produktiv, PR #3) hat eine Unique-Constraint `(photo_id, user_id)` mit `user_id` als Pflicht-Foreign-Key auf `users` — es modelliert explizit "Bewertung eines Photos durch einen echten User". Das gesamte Frontend (Grid-, Detail-, Compare-Ansicht) geht von genau dieser Semantik aus; `PhotoComparePage.tsx` stellt strikt "Ich" (Username-Abgleich mit dem JWT) gegen "Andere" nebeneinander. Ein `source=auto`-Feld direkt am `Rating` würde entweder `user_id` nullable machen (und sich auf die Postgres-Eigenheit verlassen, dass NULL-Werte eine Unique-Constraint nicht verletzen — ein implizites, leicht zu übersehendes Verhalten) oder eine begründungslose Sonderregel einführen, wessen `user_id` eine Auto-Zeile bekommt. Beides verwässert ein bisher sauberes Modell und zwingt jede der drei Frontend-Ansichten, jede Rating-Zeile erst nach `source` zu unterscheiden, bevor sie "Ich"/"Andere" bestimmen kann.
2. **Womit werden Schärfe, Belichtung und Perceptual Hashing berechnet?** Das Backend hat aktuell nur `pillow>=11.0` als Bildverarbeitungs-Abhängigkeit. ADR 0002 nennt für Phase A explizit "perceptual hashing" und optional (nicht Teil dieser Spec) `mediapipe` für Augenerkennung. Naheliegende Kandidaten für Schärfe/Hashing wären `opencv-python-headless` und/oder `imagehash` (zieht seinerseits `numpy`/`scipy` nach sich) — beides spürbarer Footprint auf einem CPU-only-Homeserver-Image für eine vergleichsweise einfache Berechnung.

## Entscheidung

### Datenmodell: `PhotoScore` und `ScoringRun` als eigene Tabellen, `Rating` bleibt unangetastet

- **`PhotoScore`**: neue Tabelle, **1:1 zu `Photo`** (`photo_id` ist Primary Key, kein separates `id`+Unique-Constraint-Paar wie bei `Rating`, weil es keine Mehrfachzeilen pro Foto gibt). Enthält: `sharpness: float`, `exposure: float`, `phash: str | None` (64-bit dHash, hex-codiert), `duplicate_of: int | None` (selbstreferenzierender FK auf `photos.id`, zeigt auf das im Duplikat-/Burst-Cluster behaltene Foto), `cluster_key: str | None` (Gruppierungs-Label für Zeit-/Motiv-Cluster, pro Scoring-Lauf neu vergeben, keine eigene `Cluster`-Tabelle — Cluster haben keinen eigenen Lebenszyklus, der eine eigene Entität rechtfertigt), `local_quality_score: float | None`, `suggested_status: RatingStatus | None` (wiederverwendet das bestehende Enum aus `Rating` — Phase A wird darüber praktisch nur `REJECTED` setzen, offene Positivempfehlungen bleiben Phase B vorbehalten, aber das Feld muss dafür nicht erneut migriert werden), `computed_at: datetime`. **`cloud_aesthetic_score` wird bewusst NICHT jetzt schon als ungenutzte Spalte angelegt** — das ist erkennbar Phase-B-Gepäck; Phase B bringt seine eigene Migration mit, wenn sie tatsächlich ansteht.
- **`ScoringRun`**: neue Tabelle, analog zu `ScanRun` (`status`, `started_at`, `finished_at`, Zähler), aber mit `photos_total`/`photos_processed` für granularen Live-Fortschritt (siehe unten).
- **`Rating` bleibt exakt wie in Spec 0002** — keine neue Spalte, keine Migration/kein Backfill der bereits produktiven Daten. Ein automatischer Vorschlag ist niemals eine `Rating`-Zeile; er wird ausschließlich über `PhotoScore.suggested_status` transportiert und der API/dem Frontend als **eigenes, drittes Feld** neben `ratings: RatingOut[]` angeboten (`PhotoOut.suggestion: SuggestionOut | None`), nicht als Teil der `ratings`-Liste.
- Ein Vorschlag wird nur dann verbindlich, wenn der Nutzer ihn aktiv über den bestehenden `PUT /photos/{id}/rating`-Endpunkt bestätigt (UI füllt dabei lediglich `status` mit `suggested_status` vor) — genau derselbe Schreibpfad wie eine manuelle Bewertung. Es gibt **keinen** Code-Pfad, über den der Scoring-Job selbst eine `Rating`-Zeile schreibt oder überschreibt. Die Anforderung "überschreibt nie eine vorhandene manuelle Bewertung" ist damit strukturell garantiert, nicht nur durch eine zusätzliche Prüfung im Job.

### Berechnung: Schärfe, Belichtung, Perceptual Hash ausschließlich mit Pillow — keine neue Abhängigkeit

- **Schärfe**: Varianz eines 3×3-Laplace-Kernels via `PIL.ImageFilter.Kernel` + `PIL.ImageStat.Stat(...).var` — das klassische "Blur-Detection ohne OpenCV"-Verfahren, liefert dieselbe Kennzahl wie `cv2.Laplacian(...).var()`.
- **Belichtung**: Über-/Unterbelichtungsanteil aus dem Histogramm via `PIL.Image.histogram()`/`PIL.ImageStat.Stat`.
- **Perceptual Hash (Duplikat-/Burst-Erkennung)**: eigenes, ca. 15 Zeilen langes dHash (Difference Hash): Graustufen-Resize auf 9×8 Pixel, bitweiser Vergleich benachbarter Pixel → 64-Bit-Hash; Ähnlichkeit über Hamming-Distanz. dHash ist strukturell (nicht farb-)sensitiv und für den konkreten Zweck (Burst-Aufnahmen Sekunden auseinander, nahezu identischer Bildausschnitt) ausreichend und etabliert — die zusätzliche Rotations-/Beleuchtungs-Invarianz eines DCT-basierten pHash wird für dieses Szenario nicht gebraucht.
- Alle drei Berechnungen laufen auf der bereits vom Scan-Job erzeugten, lokal gecachten `display`-Variante (`thumbnails.py`/`variant_path`) — **kein erneuter OpenCloud-Download** für Phase A nötig.
- Damit kommt Phase A **ohne jede neue Abhängigkeit** aus (kein `opencv-python-headless`, kein `imagehash`, kein `numpy`/`scipy`). Das wurde bewusst geprüft und verworfen: Der Nutzen (etwas bewährterer/getesteter Code) steht in keinem guten Verhältnis zum Preis (spürbar größeres Docker-Image auf einem CPU-only-Homeserver, mehr transitive Abhängigkeiten/CVE-Fläche für ein vergleichsweise simples Verfahren).

### Fortschrittsanzeige: granularer Live-Fortschritt statt des groben Scan-Musters

Das bestehende `scan_project`-Muster (`ScanRun`) committet seine Zähler nur einmal am Ende — für den Scan (leichtgewichtiges WebDAV-Listing) ausreichend, weil kurz. Der Scoring-Job lädt und verarbeitet pro Foto ein Bild und kann über tausende Fotos mehrere Minuten laufen — genau dafür verlangt Spec 0003 explizit sichtbaren Fortschritt (eigenes Akzeptanzkriterium, nicht nur "läuft/fertig" wie beim Scan). Deshalb: `ScoringRun.photos_total` wird einmal zu Beginn gesetzt, `photos_processed` wird während der Verarbeitung periodisch (batchweise, z.B. alle 25 Fotos) zwischen-committet, sodass das Frontend per Polling (analog zum bestehenden `last_scan`/`POLL_INTERVAL_MS`-Muster) einen echten "X von Y"-Fortschritt anzeigen kann. Der Mehraufwand (ein zusätzliches Zählerfeld, periodisches statt einmaliges Commit) ist gering und direkt durch das Akzeptanzkriterium gerechtfertigt.

## Begründung

- Die Trennung von `PhotoScore` und `Rating` vermeidet jede Aufweichung der bestehenden, produktiven `Rating`-Semantik und macht "Vorschlag überschreibt nie manuelle Bewertung" zu einer strukturellen statt einer zu prüfenden Eigenschaft.
- Keine Migration/kein Backfill bestehender `ratings`-Daten nötig — die Tabelle bleibt unverändert.
- Der Verzicht auf eine neue Abhängigkeit hält das Image schlank und vermeidet eine Abwägung, die sich (Aufwand für Nutzen) hier nicht lohnt; sollte sich Phase B oder spätere Verfeinerungen als auf eine echte Bibliothek angewiesen erweisen, ist das eine eigene, dann begründete ADR.

## Konsequenzen

- Frontend muss die Compare-Ansicht um einen dritten, sichtbar von "Ich"/"Andere" unterschiedenen Zustand ("Vorschlag") erweitern, statt eine Auto-Zeile in die bestehende `ratings`-Liste einzumischen.
- `phash`/`cluster_key` sind so gebaut, dass Phase B (Zeitfenster + visuelle Ähnlichkeit) denselben Hash weiterverwenden kann, ohne ihn neu zu berechnen — das ist ein bewusster Vorentscheid für Wiederverwendbarkeit, aber kein Akzeptanzkriterium dieser Spec.
- `cloud_aesthetic_score` fehlt bewusst noch; Phase B bringt bei Bedarf eine eigene, additive Migration.
- Sollte sich das handgeschriebene dHash in der Praxis als unzureichend erweisen (z.B. zu viele False Positives/Negatives bei der Burst-Erkennung), ist der Wechsel auf eine Bibliothek ein lokal begrenzter Austausch der Implementierung in `scoring.py` — die Datenmodell-Entscheidung (Hash als String-Feld an `PhotoScore`) bleibt davon unberührt.
