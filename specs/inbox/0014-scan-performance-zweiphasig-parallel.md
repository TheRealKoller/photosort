# 0014 - Scan-Performance: zweiphasig mit Parallelisierung

**Typ:** Idee
**Erfasst:** 2026-08-09
**Status:** Unrefined

## Rohtext

Den Scan kann man ggf. verbessern. In Schritt eins alle Files erkennen (ohne Download etc.), das wird schonmal gespeichert. Mit der Information kann ein %-Fortschrittsbalken erstellt werden. Danach kann das Herunterladen der Informationen und die Thumbnail-Erzeugung parallel gemacht werden. Wenn jedes verarbeitete Bild dann noch korrekt verzeichnet wird, kann selbst nach einem Neustart wieder aufgesetzt werden.
