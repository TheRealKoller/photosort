# Beispielbilder

Acht frei lizenzierte Urlaubsfotos als Arbeitsmaterial: echte Bilddaten für lokale Läufe der
Scan-/Bewertungs-Pipeline, für Bildflächen in Penpot-Entwürfen und für Sichtprüfungen im Browser.

**Dies sind keine Familienfotos.** Die Projektregel "nie Bilddaten im Repository" schützt Daniels
private Aufnahmen — sie bleiben ausschließlich auf OpenCloud, lokal nur als Cache. Fremde, frei
lizenzierte Fotos fallen nicht darunter und dürfen hier liegen. Der CI-Schritt "keine Bilddatei
unter e2e/ oder design/ im Git-Index" bewacht genau die beiden Verzeichnisse, in die Werkzeuge
selbsttätig Bilder schreiben (Playwright-Artefakte, Penpot-Formexporte); dieses Verzeichnis gehört
bewusst zu keinem der beiden.

## Herkunft und Lizenz

Alle acht von [Unsplash](https://unsplash.com), unter der
[Unsplash-Lizenz](https://unsplash.com/license): kostenlose Nutzung, kommerziell wie privat, ohne
Pflicht zur Namensnennung. Die Namensnennung steht hier trotzdem — sie kostet nichts und macht die
Herkunft ohne Nachschlagen nachvollziehbar. Der Dateiname trägt Fotograf und Foto-ID; die ID führt
über `https://unsplash.com/photos/<id>` zum Original.

| Datei | Fotograf | Motiv | Erwartete Kategorien |
|---|---|---|---|
| `aj-robsin-BuQ1RZckYW4-unsplash.jpg` | AJ Robsin | Elefantenkuh mit Jungtier in der Savanne | tier, landschaft |
| `allen-taylor-gnc08q6Q_YU-unsplash.jpg` | Allen Taylor | Paar in der Stranddüne | menschen |
| `charles-robert-k4CfXBfSlNg-unsplash.jpg` | Charles Robert | Frau mit Sofortbildkamera am Strand | menschen, gegenstand |
| `damiano-baschiera-hFXZ5cNfkOk-unsplash.jpg` | Damiano Baschiera | Rialtobrücke mit Gondel, Venedig | gebaeude-bauwerk, fahrzeug |
| `jack-ward-rknrvCrfS1k-unsplash.jpg` | Jack Ward | Klippendorf der Cinque Terre | gebaeude-bauwerk, landschaft |
| `julian-timmerman-Fn27DlI8bZ8-unsplash.jpg` | Julian Timmerman | Holzsteg zu einer bewachsenen Felseninsel | landschaft |
| `ron-dauphin-k-8-eX4Y3no-unsplash.jpg` | Ron Dauphin | Zebra in der Steppe | tier, landschaft |
| `ryan-spencer-XGKaRnWjv1c-unsplash.jpg` | Ryan Spencer | Weiße Gasse mit Meerblick | gebaeude-bauwerk, landschaft |

Die Kategoriespalte ist eine Erwartung zum Gegenlesen, keine Zusicherung — sie sagt, was ein
Klassifizierungslauf plausibel liefern sollte, und macht einen groben Fehlgriff sofort sichtbar.

## Zwei Eigenschaften, die vor dem ersten Einsatz zählen

**Kein EXIF.** Die Dateien tragen weder Aufnahmedatum noch Kameramodell noch GPS-Koordinaten —
Unsplash entfernt das. Für alles, was PhotoSort aus EXIF liest, sind sie damit unbrauchbar, solange
die Werte nicht vorher gesetzt werden: Zeit- und Ortscluster (Spec 0051) sehen hier acht Fotos ohne
Zeitpunkt und ohne Position.

**Verkleinert auf 2048 px lange Kante** (JPEG, Qualität 82) — aus 25,3 MB Originalen werden 3,7 MB.
Für Bildflächen, Sichtprüfungen und Klassifizierung reicht das vollständig. Für die Schärfe gilt es
nicht: `scoring.py::compute_sharpness` rechnet die Laplace-Varianz auf dem **vollen** Bild ohne
Downscale, die Kennzahl hängt also unmittelbar an der Kantenlänge. Absolute Schärfewerte aus diesem
Satz sind deshalb nicht mit denen echter Kameradateien vergleichbar; der Vergleich der acht Bilder
untereinander bleibt gültig, weil alle gleich behandelt wurden.
