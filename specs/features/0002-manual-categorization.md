# 0002 - Manuelle Kategorisierung

**Status:** Accepted
**Erstellt:** 2026-07-19
**Akzeptiert:** 2026-07-19
**Bezug:** Ausgangsgespräch Projekt-Setup; geschärft im idea-sharpener-Gespräch vom 2026-07-19

## Ziel

Daniel und seine Frau können die Fotos eines Projekts in einer Oberfläche durchsehen und jeweils als **Favorit**, **Album-würdig** oder **Verwerfen** einstufen — schnell genug, um mehrere tausend Fotos in überschaubarer Zeit durchzugehen.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich die Fotos eines Projekts sowohl in einer Grid- als auch in einer Einzelbild-/Swipe-Ansicht schnell durchsehen und mit einem von drei Zuständen (Favorit, Album-würdig, Verwerfen) bewerten, damit am Ende jeder für sich eine kuratierte Auswahl hat, die sich mit der des anderen vergleichen lässt.

## Akzeptanzkriterien

- [ ] Grid-Ansicht: responsives Kachel-Raster, jede Kachel zeigt die eigene Bewertung des angemeldeten Nutzers als Badge (favorite/album_worthy/rejected/unbewertet); Fotos werden paginiert geladen (Batches statt Gesamt-Reload bei tausenden Fotos) — kein harter Zeit-Grenzwert als Kriterium, aber spürbar zügig.
- [ ] Einzelbild-/Swipe-Ansicht: Vor/Zurück-Navigation innerhalb der aktuell aktiven Filter-/Reihenfolge; Tap/Klick auf eine Grid-Kachel öffnet diese Ansicht beim gewählten Foto.
- [ ] Drei-Zustands-Bewertung pro Foto und Nutzer (`favorite`/`album_worthy`/`rejected`, unbewertet als Ausgangszustand): erneutes Setzen desselben Zustands toggelt zurück auf unbewertet; ein anderer Zustand überschreibt ohne Toggle-Rest.
- [ ] Nach dem Setzen einer Bewertung springt die Einzelbild-Ansicht automatisch zum nächsten unbewerteten Foto (in der aktiven Filter-/Reihenfolge); sind keine unbewerteten Fotos mehr vorhanden, erscheint eine Abschluss-Meldung statt eines Fehlers oder stillen Stehenbleibens.
- [ ] Bewertungen sind pro Nutzer getrennt gespeichert (Unique-Constraint Foto+Nutzer); die Bewertung eines Nutzers verändert nie die des anderen, auch nicht bei (quasi-)paralleler Bewertung desselben Fotos.
- [ ] Vergleichsansicht zeigt pro Foto beide Bewertungen (inkl. "unbewertet" als eigener, sichtbarer Zustand) nebeneinander; nur die eigene Bewertung ist dort editierbar, die des anderen Nutzers ist rein lesend.
- [ ] Filter in der Grid-/Listing-Ansicht: "unbewertet" sowie je einzeln nach Bewertungsstufe (favorite/album_worthy/rejected), bezogen auf die eigene Bewertung des angemeldeten Nutzers. Kein Datumsfilter im MVP.
- [ ] Tastatur-Shortcuts in der Einzelbild-Ansicht: `1`/`2`/`3` setzen/togglen die drei Bewertungsstufen, Pfeiltasten links/rechts navigieren; Shortcuts sind deaktiviert, während ein Eingabefeld fokussiert ist.
- [ ] Touch/Swipe-Bedienung: Swipe navigiert (vor/zurück), Bewertung erfolgt separat per Tap auf die Bewertungs-Buttons (nicht per Swipe, um versehentliche Bewertungen zu vermeiden); Oberfläche ist PWA-tauglich und auf Mobilgeräten bedienbar.
- [ ] Bild-Auflösungen: Grid nutzt Thumbnail-, Einzelbild-/Vergleichsansicht Display-Auflösung; ist eine Auflösung noch nicht vom Worker erzeugt, zeigt die Ansicht einen Platzhalter statt zu blockieren.

## Datenmodell-Bezug

Neu: `Rating` (photo_id, user_id, status, updated_at; Unique-Constraint photo_id+user_id; "unbewertet" = fehlende Zeile, kein Enum-Wert). Siehe [`architecture/0001-overview.md`](../architecture/0001-overview.md).

## Architektur / Umsetzung

**Abhängigkeiten (Prerequisite-Specs, noch nicht vorhanden):**

- **Auth:** Setzt voraus, dass Login/JWT gemäß [`decisions/0003-auth-model.md`](../decisions/0003-auth-model.md) bereits als eigene Spec umgesetzt ist — inkl. `User`-Modell und einer FastAPI-Dependency `get_current_user`. Spec 0002 implementiert **kein** Login selbst, konsumiert die Dependency nur. Alle unten genannten Endpunkte sind auth-pflichtig.
- **Minimales Projekt-Frontend:** Setzt ein bestehendes React-Routing- und API-Client-Grundgerüst voraus (Projektliste/-auswahl, Navigation, Fetch-Konvention) aus einer eigenen, noch fehlenden Spec. Spec 0002 ergänzt nur neue Routen/Views auf dieser Grundlage.

Empfohlene Umsetzungsreihenfolge: Auth-Spec → Minimales-Projekt-Frontend-Spec → Spec 0002.

### Backend — neue Komponenten

**Datenmodell** (`backend/src/photosort/models.py`, neue Alembic-Migration): `RatingStatus`-Enum (favorite/album_worthy/rejected) + `Rating`-Tabelle mit Unique-Constraint `(photo_id, user_id)`. "Unbewertet" wird nicht als Enum-Wert gespeichert, sondern als Fehlen einer Zeile — macht Toggle/Überschreiben zu einem einfachen Upsert über den Unique-Constraint.

**Neue Endpunkte** (folgen dem bestehenden Router-/Schema-Muster aus `api/projects.py`):

- `api/photos.py`: `GET /projects/{project_id}/photos?rating_status=&limit=&offset=` (Foto-Listing inkl. Bewertungen beider Nutzer, Filter nach eigener Bewertung, paginiert); `GET /photos/{photo_id}/image?variant=thumbnail|display` (Bild-Streaming aus lokalem Cache, 404 falls Worker die Auflösung noch nicht erzeugt hat).
- `api/ratings.py`: `PUT /photos/{photo_id}/rating` (Upsert der eigenen Bewertung); `DELETE /photos/{photo_id}/rating` (Reset auf unbewertet, idempotent).

**Thumbnails/Bild-Auflösungen:** Erzeugung im Worker beim Scan (zwei Auflösungen per Pillow), Ablagepfad deterministisch aus `photo_id`+`etag` — kein neues DB-Feld, automatische Invalidierung bei Foto-Änderung.

### Frontend — neue Komponenten

Neue Routen `/projects/:id/photos` (Grid), `/projects/:id/photos/:photoId` (Swipe/Einzelbild), `/projects/:id/compare` (Vergleichsansicht) auf dem Routing-/API-Grundgerüst der Projekt-Frontend-Spec. Navigation/Shortcuts operieren auf der zuletzt geladenen, gefilterten Foto-ID-Liste — kein serverseitiger "nächstes Foto"-Endpunkt nötig.

### Umsetzungsreihenfolge innerhalb von Spec 0002

1. `Rating`-Modell + Migration + Upsert-/Delete-Logik.
2. Foto-Listing-Endpunkt mit Filter/Pagination (nutzt `get_current_user`).
3. Thumbnail-Erzeugung im Worker + Bild-Serving-Endpunkt.
4. Frontend: Grid → Einzelbild/Swipe inkl. Shortcuts/Touch → Vergleichsansicht.

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) (im Zuge dieser Spec initial angelegt — erstes Feature mit sichtbarer Oberfläche).

- **Grid:** responsives CSS-Grid, Kachelgröße passt sich der Breite an. Jede Kachel zeigt Thumbnail + eigene Bewertung als Badge (Farbcodierung gemäß Design-System); Bewertung des anderen Nutzers wird hier bewusst nicht gezeigt (dafür die Vergleichsansicht). Filterleiste oberhalb, Filterzustand im URL-Query-Parameter. Thumbnails laden lazy; ob echte Virtualisierung bei sehr großen Mengen nötig wird, zeigt sich in der Umsetzung.
- **Einzelbild-/Swipe:** großflächige Darstellung (Display-Auflösung), minimale Chrome-UI, Vor/Zurück per Pfeil-Buttons/Swipe. Drei Bewertungs-Buttons fix positioniert, zeigen aktuelle eigene Bewertung farblich hervorgehoben, setzen sofort ohne Bestätigungsdialog. Fortschrittsanzeige ("42/1230"). Shortcut-Belegung als knapper, dauerhaft sichtbarer Hinweistext. Nach Bewertung automatischer Sprung zum nächsten unbewerteten Foto; sind keine mehr übrig, erscheint eine Abschluss-Meldung mit Option zurück zum Grid/zur Vergleichsansicht.
- **Vergleichsansicht:** Listen-/Grid-Layout, pro Foto beide Bewertungs-Badges (Daniel/Ehefrau) nebeneinander — auch auf schmalen Bildschirmen nebeneinander, nicht gestapelt, sonst geht der Vergleichszweck verloren. Klick öffnet dieselbe Einzelbild-Ansicht (Deep-Link), dort bleibt nur die eigene Bewertung editierbar.
- **Zustände:** Leer (Hinweistext + Filter-Reset-Option), Ladend (Skeleton-Kacheln im Grid, dezenter Inline-Indikator beim Bildwechsel), Fehler (Inline-Banner mit "Erneut versuchen"), Platzhalter bei noch nicht generierter Bild-Auflösung (generisches Platzhalterbild, Navigation bleibt möglich).
- **Responsivität/PWA:** alle drei Ansichten auf Smartphone-Breite nutzbar; Touch-Ziele mindestens 44×44px.

## Security

**Sicherheitsrelevant:** Ja — personenbezogen getrennte Daten (`Rating` pro `user_id`), neue auth-pflichtige Endpunkte, ein Datei-Streaming-Endpunkt für Fotos.

- **Autorisierung:** Alle vier Endpunkte erfordern `get_current_user` gemäß ADR `decisions/0003-auth-model.md` — auch der Bild-Endpunkt (exponiert Familienfotos). `user_id` für `PUT`/`DELETE /photos/{id}/rating` wird ausschließlich aus dem JWT-Claim abgeleitet, niemals aus Body/Query — sonst könnte Nutzer A per manipuliertem Request die Bewertung von Nutzer B überschreiben (Broken Object-Level Authorization). Muss-Kriterium, keine optionale Härtung.
- **Vergleichsansicht (AC) als gewollte Ausnahme:** beide Bewertungen nebeneinander sichtbar zu machen ist explizit gefordertes Verhalten, kein Datenleck. Grid-/Filter-Ansicht liefert dennoch standardmäßig nur die eigene Bewertung (Datenminimierung, keine Autorisierungsgrenze).
- **IDs:** kein IDOR im klassischen Sinn, da beide Nutzer laut Produktkontext ohnehin alle Projekte sehen dürfen — relevant bleibt nur, dass überhaupt ein gültiges JWT vorliegt.
- **Path-Traversal im Bild-Endpunkt:** Cache-Pfad wird serverseitig aus `photo_id`+`etag` gebildet (kein Client-Einfluss). Der `variant`-Query-Parameter muss gegen eine feste Allowlist (`thumbnail`/`display`) validiert werden, bevor er in eine Pfad-/Dateioperation einfließt — sonst klassisches Path-Traversal-Risiko. Cache-Pfad darf nie direkt aus `relative_path` (OpenCloud-Dateiname) ohne Normalisierung gebildet werden.
- **Content-Type:** explizit auf Basis des erlaubten Formats setzen (JPEG/PNG/HEIC), nicht ungeprüft von OpenCloud übernehmen, plus `X-Content-Type-Options: nosniff` (verhindert MIME-Sniffing-XSS bei falsch benannten Dateien) — Empfehlung, kein Blocker für dieses private Projekt.
- **CSRF:** abhängig davon, wie die Auth-Spec das JWT überträgt (Header vs. Cookie) — bei Cookie-Übertragung `SameSite=strict`/CSRF-Token nötig, bei Bearer-Header kein Risiko. Anforderung an die Auth-Spec, nicht an diese.
- **Blocker:** Diese Spec darf nicht implementiert/deployt werden, solange `get_current_user` nicht real gegen JWT prüft. Eine Platzhalter-Dependency (z.B. fest verdrahteter Nutzer) darf nicht nach `main`.

## Entscheidungen (2026-07-19, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Views:** Grid- und Einzelbild-/Swipe-Ansicht beide von Anfang an (nicht nacheinander gestaffelt).
- **Notizfunktion:** keine Kommentar-/Notizfunktion pro Foto im MVP.
- **Filter:** "unbewertet" + je Bewertungsstufe; kein Datumsfilter im MVP.
- **Konfliktbehandlung unterschiedlicher Bewertungen beim Export:** verschoben zu Spec 0004 (betrifft Export-Logik, nicht die Kategorisierung selbst).
- **Fehlende Prerequisites entdeckt und bewusst ausgegliedert:** Spec 0001 deckt kein Projekt-Frontend ab (→ eigene, vorgelagerte Spec) und keine Auth-Implementierung (→ eigene, separate Spec, getrennt von der Projekt-Frontend-Spec, da Auth und Projekt-UI unterschiedliche technische Bereiche sind).
- **Auto-Advance:** nach Bewertung automatisch zum nächsten unbewerteten Foto; am Ende der Liste erscheint eine Abschluss-Meldung.
- **Toggle:** erneutes Drücken derselben Bewertungstaste setzt zurück auf unbewertet.
- **Performance:** Pagination/Batch-Laden statt hartem Zeit-Grenzwert als Akzeptanzkriterium.
- **Kein E2E-Test-Setup** für dieses Feature (keine Infrastruktur vorhanden, Aufwand für Zwei-Personen-Projekt nicht gerechtfertigt) — Touch/Swipe-Gefühl wird stattdessen als manueller Smoke-Test vor Merge geprüft.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec selbst. Die während der Schärfung entdeckten Prerequisites (Auth-Spec, Projekt-Frontend-Spec) sind kein "offen" im Sinne dieser Spec, sondern eigene, noch zu schärfende Specs — siehe `specs/roadmap.md`.

## Out of Scope

Automatische Vorauswahl (Spec 0003), Export inkl. Konfliktbehandlung unterschiedlicher Bewertungen (Spec 0004), Kommentar-/Notizfunktion pro Foto, Datumsfilter. **Login/Auth-Implementierung** und **minimales Projekt-Anlage-/Ordner-Browser-Frontend** sind explizit nicht Teil dieser Spec, sondern eigene, vorgelagerte Specs (noch zu schärfen).
