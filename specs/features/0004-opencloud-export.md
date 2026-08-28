# 0004 - Export nach OpenCloud

**Status:** Superseded — Refinement veraltet, neu erfasst als Issue [`#263`](https://github.com/TheRealKoller/photosort/issues/263)
**Erstellt:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup

**Nachtrag (2026-08-28):** Auf Wunsch von Daniel zurückgezogen — das Refinement liegt zu lange zurück (Ausgangsgespräch beim Projekt-Setup) und seither gab es zu viele Änderungen am Projekt, um die Spec unverändert weiterzuverwenden. Die Idee selbst bleibt bestehen, wird aber frisch als Issue [`#263`](https://github.com/TheRealKoller/photosort/issues/263) neu durchlaufen (Status `Unrefined`) statt diese Spec fortzuschreiben. Diese Datei bleibt als historisches Dokument stehen.

## Ziel

Die als "Album-würdig"/"Favorit" markierten Fotos eines Projekts werden zurück auf die OpenCloud-Instanz exportiert, z.B. in einen neuen Ordner, sodass daraus ein Fotoalbum erstellt/gedruckt werden kann.

## User Story

Als Nutzer möchte ich mit einem Klick die finale Auswahl eines Projekts als neuen Ordner auf meiner OpenCloud-Instanz erzeugen, damit ich diesen für ein Fotoalbum weiterverwenden kann.

## Akzeptanzkriterien

- [ ] Nutzer kann für ein Projekt einen Export anstoßen, der die aktuell ausgewählten Fotos (Kriterium siehe offene Fragen) in einen neuen Zielordner auf OpenCloud kopiert.
- [ ] Export nutzt nach Möglichkeit serverseitiges `COPY` (WebDAV) statt Re-Upload, um Bandbreite zu sparen.
- [ ] Nutzer erhält eine Bestätigung/Zusammenfassung nach Abschluss (Anzahl exportierter Fotos, Zielpfad).
- [ ] Fehler beim Export einzelner Dateien brechen den Gesamtexport nicht ab, sondern werden gesammelt gemeldet.

## Datenmodell-Bezug

Kein neues Kernmodell; ggf. `ExportRun` zur Nachvollziehbarkeit (wann, was, wohin exportiert wurde).

## Offene Fragen

- Auswahlkriterium für den Export: nur `favorite`, oder `favorite` + `album_worthy`? Konfigurierbar pro Export?
- Umgang mit unterschiedlichen Bewertungen von Daniel und seiner Frau (siehe auch offene Frage in Spec 0002) — welche Fotos zählen als "final ausgewählt"?
- Namensschema für den Zielordner (z.B. `{Projektname}/Album` oder `{Projektname}-Album` auf oberster Ebene)?
- Soll wiederholter Export denselben Zielordner aktualisieren (Diff) oder immer einen neuen Ordner/Zeitstempel erzeugen?

## Out of Scope

Layout/Druckvorbereitung eines physischen Fotobuchs — vorerst nur Bereitstellung der Auswahl als Ordner.
