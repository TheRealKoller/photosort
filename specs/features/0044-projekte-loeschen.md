# 0044 - Projekte löschen

**Status:** Accepted
**Erstellt:** 2026-08-16
**Bezug:** `specs/inbox/0019-projekte-loeschen.md` (Ursprungs-Idee), idea-sharpener-Gespräch mit Daniel

## Ziel

Nutzer sollen ein Projekt und alle zugehörigen PhotoSort-Daten löschen können, um nicht mehr benötigte Projekte aus der Anwendung zu entfernen. Gelöscht werden ausschließlich PhotoSort-eigene Daten (Datensätze, Bewertungen, Scores, lokaler Thumbnail-Cache) — die Original-Fotos auf OpenCloud bleiben unangetastet, PhotoSort greift dort weiterhin nur lesend zu. Da die Aktion irreversibel ist, ist eine hohe Bestätigungshürde (Eintippen des Projektnamens) vorgesehen.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich ein Projekt vollständig aus PhotoSort löschen können, nachdem ich den Projektnamen zur Bestätigung eingetippt habe, damit ich nicht mehr benötigte Projekte entfernen kann, ohne versehentlich Daten zu verlieren.

## Akzeptanzkriterien

**Voraussetzung (Cascade-Fix)**
- [ ] `CriterionScoringRun` bekommt eine `rankings`-Relationship (`cascade="all, delete-orphan"`) zu `PhotoRanking`. Löschen eines `CriterionScoringRun` (direkt oder kaskadierend über `Project`) entfernt alle zugehörigen `PhotoRanking`-Zeilen ohne `IntegrityError`/`ForeignKeyViolation`. Ohne diesen Fix schlägt jede Löschung eines Projekts mit abgeschlossenem Kuratierungslauf (Spec 0037) fehl.

**Backend-Endpunkt**
- [ ] `DELETE /projects/{project_id}` mit JSON-Body `{"confirm_name": "<string>"}` liefert bei existierendem Projekt und `confirm_name.strip() == project.name` (case-sensitiv) `204 No Content`, entfernt Projekt + alle abhängigen `Photo`/`Rating`/`PhotoScore`/`PhotoCriterionScore`/`ScanRun`/`ScoringRun`/`CriterionScoringRun`/`PhotoRanking`-Zeilen vollständig, in einer Transaktion.
- [ ] `400 Bad Request`, wenn `confirm_name` nicht exakt mit `project.name` übereinstimmt — keine Löschung. Serverseitige Prüfung zusätzlich zur clientseitigen Texteingabe-Bestätigung (schützt gegen direkte API-Nutzung ohne die UI, z.B. curl/Skript).
- [ ] `404` mit `detail`, wenn `project_id` unbekannt — auch bei einem zweiten `DELETE` auf eine bereits gelöschte `project_id` (nicht idempotent-`204`).
- [ ] `409` mit `detail`, wenn der jeweils neueste `ScanRun`, `ScoringRun` oder `CriterionScoringRun` `status=RUNNING` ist; Projekt bleibt dabei unverändert. Ein nicht mehr aktueller `RUNNING`-Altlauf blockiert nicht.
- [ ] `401` ohne gültigen Auth-Header (bestehendes Router-Pattern).
- [ ] Kein Owner-Check: jeder eingeloggte Nutzer kann jedes Projekt löschen, unabhängig davon, wer es angelegt hat (bewusste Produktentscheidung, siehe Entscheidungen).
- [ ] Nach erfolgreichem `204` werden `thumbnail_path`/`display_path` (aus `photo.id`/`photo.etag`, vor dem DB-Delete gelesen) aller ehemaligen Fotos best-effort entfernt (`unlink(missing_ok=True)`); Cleanup-Fehler werden geloggt, ändern nicht die `204`-Antwort und brechen den Cleanup weiterer Dateien nicht ab.

**Frontend**
- [ ] "Projekt löschen"-Button (neue Button-Variante `variant="destructive"`) in einer eigenen, vom übrigen Workflow klar abgesetzten Section am Ende der Projekt-Detailseite.
- [ ] Klick öffnet `DeleteProjectDialog.tsx` (neue Radix `AlertDialog`-Komponente): Warntext ("kann nicht rückgängig gemacht werden", Original-Fotos auf OpenCloud bleiben erhalten), Texteingabefeld zur Bestätigung des Projektnamens.
- [ ] Löschen-Button ist deaktiviert, bis die Eingabe strikt (keine Trimmung im Vergleich, case-sensitiv) mit `project.name` übereinstimmt — führende/nachgestellte Leerzeichen und abweichende Groß-/Kleinschreibung zählen explizit nicht als Match.
- [ ] Während des Requests: Eingabefeld + alle Buttons deaktiviert (bestehendes `Button`-`busy`-Muster).
- [ ] Bei `409`: Fehlermeldung im Dialog, Löschen-Button + Eingabefeld deaktiviert, Abbrechen-Button bleibt aktiv (einziger Weg, den Dialog regulär zu verlassen), kein automatisches Polling/Retry.
- [ ] Bei `404`: Hinweistext, automatische Navigation zur Projektliste ohne Timer (risikofrei, da das Projekt bereits nicht mehr existiert).
- [ ] Bei `400` (Namens-Mismatch, sollte durch die Frontend-Freischaltlogik praktisch nie auftreten): generische Fehlermeldung, Dialog bleibt offen.
- [ ] Bei sonstigem Fehler (Netzwerk/5xx): Retry-Button, löst denselben Request erneut aus, eingegebener Text bleibt erhalten.
- [ ] Bei Erfolg: Dialog schließt, Navigation zu `/projects` (Projektliste).

## Datenmodell-Bezug

Keine neue Tabelle. Ergänzt eine fehlende `relationship` (`CriterionScoringRun.rankings`, cascade) — reine ORM-Metadaten-Korrektur, keine Alembic-Migration nötig (kein Schema-Change). Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Kein neues ADR nötig. Keine neue Technologie-*Grundstruktur*, keine neue Datenmodell-Grundstruktur (reine Vervollständigung einer bereits bestehenden Kaskade), keine architekturrelevante neue Abhängigkeit im ADR-pflichtigen Sinn: `@radix-ui/react-alert-dialog` ist durch ADR [`decisions/0011-ui-component-library.md`](../decisions/0011-ui-component-library.md) bereits als möglicher künftiger Radix-Baustein vorgesehen ("Dialog … wo gebraucht") — hier eine technische Detailentscheidung, keine eigene ADR.

**0. Voraussetzung: Cascade-Lücke bei `PhotoRanking` schließen.** `PhotoRanking` (FK auf `criterion_scoring_runs.id`) hat aktuell keine ORM-`relationship` und die DB-FK kein `ondelete=CASCADE` (wie im gesamten Projekt üblich — Kaskaden laufen konsequent über ORM-`relationship`, nicht DB-`ondelete`). Ohne Korrektur schlägt jede Projektlöschung mit abgeschlossenem Kuratierungslauf mit `ForeignKeyViolation` fehl. Fix: neue `relationship` in `models.py`:
```python
class CriterionScoringRun(Base):
    ...
    rankings: Mapped[list[PhotoRanking]] = relationship(cascade="all, delete-orphan")
```
Rein ORM-seitig, keine Migration nötig. Muss vor dem Löschendpunkt implementiert und mit eigenem Test abgesichert werden.

**1. Aktiver Lauf während der Löschung → blockieren (409), nicht tolerieren.** `DELETE /projects/{project_id}` prüft vor dem Löschen den Status des jeweils letzten Laufs aller drei Run-Typen (Wiederverwendung der bereits vorhandenen `_latest_*_run`-Helfer in `projects.py`). Ist einer davon `RUNNING`, antwortet der Endpunkt mit `409`. Begründung gegen "trotzdem löschen": ein aktiver Job schreibt periodisch Checkpoints auf Zeilen, die die Löschung währenddessen entfernen würde, und legt laufend neue `PhotoRanking`-Zeilen an — das Ergebnis wäre nicht deterministisch. Den Watchdog-Mechanismus (Spec 0034/ADR 0019) für einen aktiven Abbruch zu nutzen wäre genau die Komplexität, die ADR 0019 bereits bewusst zurückgestellt hat — Blockieren ist die einfachere, korrekte Lösung; der Nutzer wartet den laufenden Schritt ab und versucht die Löschung danach erneut.

**2. Cache-Cleanup: nach dem DB-Commit, synchron im selben Request, best-effort.** Reihenfolge: 404-Prüfung → 409-Prüfung → `confirm_name`-Prüfung (400 bei Mismatch) → `(photo_id, etag)` aller Projekt-Fotos laden → `session.delete(project)` + `commit()` (maßgeblicher, transaktional abgesicherter Schritt) → erst danach best-effort Cache-Dateien entfernen. Dateisystem-Operationen sind nicht Teil der DB-Transaktion; ein Datei-Fehler darf die eigentlich verlangte Datenlöschung nicht verhindern. Neue Hilfsfunktion in `thumbnails.py`:
```python
def delete_cached_variants(cache_dir: Path, photo_id: int, etag: str) -> None:
    for path in (thumbnail_path(cache_dir, photo_id, etag), display_path(cache_dir, photo_id, etag)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Cache-Datei konnte nicht gelöscht werden: %s", path)
```
`missing_ok=True` deckt den Race-Fall "Datei bereits weg" ab. Endpunkt antwortet immer mit `204` nach erfolgreichem DB-Delete, unabhängig vom Cache-Cleanup-Ergebnis. Kein neuer Hintergrund-Job — synchrones Unlinking ist bei zwei Nutzern und lokalem Dateisystem schnell genug.

**3. Serverseitige Namens-Verifikation.** `DELETE`-Request nimmt zusätzlich zur `project_id` den Projektnamen im Body entgegen (`{"confirm_name": "<string>"}`, Pydantic-Model mit `max_length`); Backend vergleicht `confirm_name.strip() == project.name` (case-sensitiv, identisch zur Frontend-Logik) und antwortet bei Nichtübereinstimmung mit `400`, keine Löschung. Schützt gegen direkte API-Nutzung ohne die clientseitige Bestätigungs-UX (curl, Skript, Race Condition) — eine rein clientseitige Prüfung wäre gegen genau diesen Vektor wirkungslos.

**4. Bestätigungsdialog: `@radix-ui/react-alert-dialog`, keine Eigenbau-Lösung.** Anders als die native Lösung in Spec 0043 braucht dieser Fall erzwungenen Fokus-Trap, `role="alertdialog"`-Semantik, kein Schließen per Klick außerhalb/Escape (bewusst kein "versehentliches Wegklicken" bei einer irreversiblen Aktion), Fokus-Rückgabe beim Schließen — das ist der Zweck von `AlertDialog` gegenüber dem allgemeineren `Dialog`. Erster echter Modal-Baustein im Projekt, konsistent mit dem shadcn/ui-Copy-in-Repo-Muster aus ADR 0011.

**Betroffene Dateien / Umsetzungsreihenfolge:**

Backend (TDD):
1. `backend/src/photosort/models.py` — `rankings`-Relationship ergänzen (Voraussetzung für alles Weitere).
2. `backend/src/photosort/thumbnails.py` — `delete_cached_variants()` ergänzen (isoliert testbar, keine DB-Abhängigkeit).
3. `backend/src/photosort/api/projects.py` — `DELETE /projects/{project_id}`: 404 → 409 → 400 (confirm_name) → Foto-Liste laden → `session.delete(project)` + `commit()` → Cache-Cleanup-Schleife → `204`.

Frontend:
4. `frontend/package.json` — `@radix-ui/react-alert-dialog` ergänzen.
5. `frontend/src/components/ui/alert-dialog.tsx` — neue Basiskomponente (Radix-Wrapper).
6. `frontend/src/components/ui/button.tsx` — neue Variante `destructive`.
7. `frontend/src/api/projects.ts` — `deleteProject(id: number, confirmName: string): Promise<void>`.
8. `frontend/src/components/DeleteProjectDialog.tsx` — Texteingabe-Bestätigung, ruft `deleteProject` auf, navigiert bei Erfolg zur Projektliste.
9. Integration in `frontend/src/pages/ProjectDetailPage.tsx` (eigene Section am Seitenende). Hinweis für spätere Konsistenz: Spec 0042 (Accepted, noch nicht umgesetzt) verschiebt Header-/Sekundärnavigations-Verantwortung nach `ProjectPipelineLayout.tsx` — die Löschen-Aktion könnte dorthin mitwandern, das ist aber nicht Teil dieser Spec und kein Überschneidungsrisiko (0042 ändert an `ProjectDetailPage.tsx` nichts, was diese Spec nicht auch selbst anfasst).

`docs/architecture.md` wird im selben PR um den neuen Löschendpunkt/die vervollständigte Kaskade ergänzt.

## UI/UX

**Sichtbare Oberfläche:** Ja.

**Platzierung:** Neue, separate Section am Ende der Projekt-Detailseite, nach der Kategorie-Kuratierung-Section — bewusst weit weg von den häufig genutzten Trigger-Buttons (Scan/Scoring/Gate), um versehentliche Klicks zu vermeiden. Button-Text: "Projekt löschen".

**Button-Styling:** Neue Variante `variant="destructive"` (Rotton `--status-failed`, analog bestehenden Fehlerbannern), identische Formsprache (`rounded-md`, `shadow-warm`) wie andere Buttons — nur die Farbe signalisiert Destruktivität, keine Extra-Dramatik.

**AlertDialog-Aufbau:**
- Kopfzeile: "Projekt löschen?"
- Warntexte: (1) "Diese Aktion kann nicht rückgängig gemacht werden." (2) "Die Fotos auf OpenCloud bleiben erhalten — nur die PhotoSort-Daten (Bewertungen, Kategorien, Einstellungen) für dieses Projekt werden gelöscht." (3) Aufforderung zur exakten Eingabe des Projektnamens.
- Texteingabefeld: Label "Projektname zur Bestätigung", responsive Breite (`min(100%, 28rem)`), Vergleich exakt (kein Trim, case-sensitiv).
- Buttons: "Abbrechen" (`variant="ghost"`) immer aktiv außer während eines laufenden Requests; "Projekt löschen" (`variant="destructive"`) `disabled` bis exakter Match, zeigt Busy-Zustand während des Requests.

**Fehlerdarstellung im Dialog:**
- `409`: Alert-Banner im Dialog ("Projekt hat noch einen laufenden Scan-/Bewertungslauf. Bitte abwarten und erneut versuchen."), Löschen-Button + Eingabefeld deaktiviert, Abbrechen bleibt aktiv als einziger Weg, den Dialog zu verlassen. Kein automatisches Polling — bewusst verworfen als unnötige Komplexität für einen seltenen Randfall; Nutzer schließt manuell und versucht später erneut.
- `404`: Hinweistext ("Projekt wurde nicht gefunden — möglicherweise bereits gelöscht."), automatische Navigation zur Projektliste ohne Timer (risikofrei, da kein Datenverlust mehr möglich).
- Sonstiger Fehler: Alert-Banner mit "Erneut versuchen"-Button (bekanntes Retry-Muster aus Projektliste/Foto-Ansichten), eingegebener Text bleibt erhalten.
- Erfolg: Dialog schließt automatisch, Navigation zu `/projects`, keine separate Erfolgsmeldung (die Projektliste spricht für sich).

**Design-System-Bezug:** Bestätigungsdialoge sind laut `specs/architecture/0004-design-system.md` nur für destruktive, schwer rückgängig zu machende Aktionen vorgesehen (Logout/Bewertung ändern sind bewusst bestätigungslos) — Projekt-Löschung ist der erste "harte" Fall dieser Art im Projekt und etabliert das Muster für künftige ähnlich irreversible Aktionen. Design-System wird um die neue `destructive`-Button-Variante und das Bestätigungsdialog-Muster ergänzt (gehört zur Umsetzung dieser Spec).

**Edge Cases:** Sehr langer Projektname — Eingabefeld/Label brechen um (`word-break`), eine längere Eingabe ist eine natürliche, akzeptierte Bremse gegen versehentliche Löschung. Touch-Ziele ≥44px (bestehende Norm).

## Security

Sicherheitsrelevant: ja (echte, irreversible Datenlöschung; fehlender Owner-Check).

**Bedrohungen und Gegenmaßnahmen:**
- Auth-Durchsetzung: `DELETE /projects/{project_id}` hängt am bestehenden `dependencies=[Depends(get_current_user)]`-Torwächter — konsistent mit allen anderen Projekt-Endpunkten.
- Kein Owner-Konzept, jeder eingeloggte Nutzer kann jedes Projekt löschen — bewusst so entschieden (Daniel: "Das ist ok, jeder Nutzer darf löschen"), konsistent mit dem projektweiten Grundsatz "kein Innentäter-Modell zwischen Daniel und seiner Frau" (`architecture/0003-securitykonzept.md`). Keine neue Angriffsflächen-Klasse gegenüber bereits akzeptierten Präzedenzfällen (z.B. `GET /projects/{id}/photos` ohne Projekt-Zugehörigkeitsprüfung).
- **Serverseitige Namens-Verifikation (Muss-Kriterium):** siehe Architektur-Abschnitt Punkt 3 — schützt gegen direkte API-Nutzung ohne die clientseitige Bestätigungs-UX.
- Cache-Cleanup verwendet ausschließlich serverseitig aus `Photo.id`/`etag` abgeleitete Dateipfade (bestehendes Muster), nie aus Nutzereingabe konstruierte Pfade — kein Path-Traversal-Risiko.
- Kaskadierender DB-Delete läuft in einer Transaktion, um bei Teilausfall keine verwaisten Zeilen zu hinterlassen.
- `409` bei aktivem Lauf verhindert Race Conditions zwischen laufendem Job und Löschung (primär Datenintegrität, verwandt mit Sicherheitsaspekt).

**Bewusst akzeptiertes Restrisiko** (wird nach Merge in `specs/architecture/0003-securitykonzept.md` nachgetragen): Kein Soft-Delete/Undo/Audit-Log — ein versehentlicher oder durch einen kompromittierten Account ausgelöster Löschvorgang ist unwiderruflich und nicht nachvollziehbar, wer/wann gelöscht hat. Akzeptiert für dieses Zwei-Nutzer-Tool, gemildert durch die serverseitige Namens-Bestätigung; die Original-Fotos auf OpenCloud bleiben in jedem Fall unberührt, sodass im schlimmsten Fall nur PhotoSort-Metadaten verloren gehen, nicht die Fotos selbst.

**Datenschutz-Einordnung:** Datenschutzfreundlich (explizite Nutzerkontrolle über eigene Daten), kein DSGVO-Konflikt. Löscht keine Originalfotos (bleiben auf OpenCloud) und löscht ohne Owner-Konzept auch die `Rating`-Daten des jeweils anderen Nutzers mit — datenschutzrechtlich unproblematisch (keine Drittverarbeitung), konsistent mit dem bestätigten "kein Innentäter-Modell"-Grundsatz.

## Teststrategie

Erstes ORM-Cascade-Delete-Problem über eine Zwischenebene hinweg (jede Elterntabelle braucht ihre eigene explizite Cascade, keine Transitivität) und erstes `@radix-ui/react-alert-dialog` mit striktem, nicht-trimmendem Texteingabe-Gate im Projekt.

**Backend (`pytest`):** Modell-Ebene (`test_models.py`): Cascade-Tests für direkten `CriterionScoringRun`-Delete und volle `Project`-Kette über alle acht abhängigen Tabellen (TDD: zuerst rot ohne den Fix aus AK1). API-Ebene (`test_api_projects.py`): Minimalfall (Projekt ohne Daten), voller Datengraph inkl. Kuratierungslauf, `404` bei unbekannter ID und bei Doppellöschung, je ein `409` pro Run-Typ, `400` bei Namens-Mismatch, Erfolg durch den jeweils "anderen" Nutzer (kein Owner-Check), Cache-Cleanup (Datei vorhanden → weg), fehlende Cache-Datei (kein 500), Cleanup-`OSError` ändert Antwort nicht. Kein neuer 401-Test nötig (bestehender introspektiver Router-Test deckt die neue Route automatisch mit ab).

**Frontend (`vitest`):** Unit: reine Namens-Vergleichsfunktion (Whitespace/Case-Fälle). Integration (`DeleteProjectDialog.test.tsx`, `MemoryRouter`+`QueryClientProvider`, gemockte `api/projects.ts`): Button-Freischaltung nur bei exaktem Match, Busy-Zustand, Erfolg+Navigation, `409`/`404`/generischer Fehler je einzeln (inkl. Abbrechen-Button bleibt bei 409 aktiv), Retry-Aufrufzähler. Ergänzung der bestehenden `button.test.tsx`-Matrix um die neue `destructive`-Variante (kein eigenes neues Testmuster nötig).

**Testkonzept-Ergänzung:** `specs/architecture/0002-testkonzept.md` wird um zwei neue, projektweit wiederverwendbare Muster ergänzt: "ORM-Cascade-Delete über eine Zwischenebene hinweg" (Backend-Teil) und "Radix AlertDialog mit strikter Texteingabe-Bestätigung" (Frontend-Teil). Umsetzung ist Teil des `developer`-Workflows für diese Spec.

## Entscheidungen

- **Löschumfang bewusst auf PhotoSort-Daten begrenzt:** die Original-Fotos auf OpenCloud werden nicht gelöscht — PhotoSort bleibt dort rein lesend, das war nie zur Debatte (Daniel, Schärfen-Gespräch).
- **Bestätigung durch Eintippen des Projektnamens** statt einfachem OK/Abbrechen-Dialog — höhere Hürde gegen versehentliches Löschen, da irreversibel (Daniel, Schärfen-Gespräch).
- **Kein Owner-Check:** jeder eingeloggte Nutzer kann jedes Projekt löschen — explizit von Daniel bestätigt ("Das ist ok, jeder Nutzer darf löschen"), konsistent mit dem bestehenden Muster gleichberechtigter Nutzer in der App (kein Rollenmodell, siehe ADR 0003).
- **Cascade-Bugfix als Voraussetzung entdeckt** (nicht Teil der ursprünglichen Idee): `PhotoRanking` hatte keine funktionierende Kaskade — ohne Fix wäre die Löschung jedes Projekts mit abgeschlossenem Kuratierungslauf fehlgeschlagen. Vom `architect`-Agenten bei der Umsetzungsplanung gefunden und in AK1/Architektur-Abschnitt Punkt 0 aufgenommen.
- **Serverseitige Namens-Verifikation ergänzt** (über die ursprüngliche Idee hinaus): auf Empfehlung von `security-engineer` nimmt der DELETE-Request den Projektnamen zusätzlich im Body entgegen und prüft ihn serverseitig — eine rein clientseitige Bestätigung wäre gegen direkte API-Nutzung wirkungslos.
- **Kein automatisches Polling im 409-Fall:** ursprünglicher UX-Entwurf sah automatisches Nachpollen des Job-Status im Dialog vor — als unnötige Komplexität für einen seltenen Randfall verworfen; stattdessen einfache Fehlermeldung, manuelles Schließen und späteres Wiederholen.
- **Kein Soft-Delete/Undo/Audit-Log:** bewusst akzeptiertes Restrisiko für dieses Zwei-Nutzer-Tool (siehe Abschnitt Security) — Aufwand steht in keinem Verhältnis zum Nutzen, zumal die Original-Fotos ohnehin erhalten bleiben.
- **409-Dialogverhalten geschärft** (test-engineer-Fund): im 409-Fall bleibt der Abbrechen-Button aktiv, nur Löschen-Button und Eingabefeld werden deaktiviert — sonst gäbe es keinen regulären Weg mehr, den Dialog zu verlassen (Radix `AlertDialog` unterbindet ESC/Außenklick bewusst).
- **404-Dialogverhalten geschärft** (test-engineer-Fund): automatische Navigation zur Projektliste ohne Timer, da die Situation risikofrei ist (Projekt existiert bereits nicht mehr).

## Offene Fragen

Keine.

## Out of Scope

- Löschen der Original-Fotos auf OpenCloud.
- Soft-Delete, Undo-Funktion, Wiederherstellung nach Löschung.
- Audit-Log, wer wann welches Projekt gelöscht hat.
- Owner-/Berechtigungskonzept zwischen den beiden Nutzern (weiterhin gleichberechtigt).
- Aktiver Abbruch eines laufenden Scan-/Scoring-Laufs, um die Löschung zu erzwingen (stattdessen: blockieren via 409).
- Batch-Löschen mehrerer Projekte gleichzeitig.
- Bestätigung per SMS/E-Mail (für ein Zwei-Nutzer-Tool nicht nötig).
