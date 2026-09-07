# 0062 - Projektweites Löschen als metadatengeordnete Mengenlöschung, nicht als ORM-Kaskade

**Status:** Accepted
**Datum:** 2026-09-07
**Bezug:** [GitHub-Issue #162](https://github.com/TheRealKoller/photosort/issues/162), [`features/0044-projekte-loeschen.md`](../features/0044-projekte-loeschen.md)

**Berührt außerdem (keine Ablösung):** Die ORM-`relationship`-Kaskaden (`cascade="all, delete-orphan"`) bleiben unverändert die Kaskadenform des Projekts für **einzelne** Zeilen — `session.delete(photo)` beim Re-Scan (`worker.py`), `session.delete(rating)`, `session.delete(existing)` im Cloud-Vision-Fehlerpfad. DB-seitiges `ondelete=CASCADE` wird weiterhin nirgends verwendet. Diese ADR entscheidet ausschließlich den einen Fall „ein ganzes Projekt samt aller abhängigen Zeilen".

## Kontext

Spec 0044 soll `DELETE /projects/{project_id}` einführen. Der Entwurf von 2026-08-16 sah dafür `await session.delete(project)` vor und verließ sich auf die ORM-Kaskaden entlang `Project.photos`/`Project.scan_runs`/… — ein einzeiliger, deklarativer Weg, der zu diesem Zeitpunkt acht abhängige Tabellen betraf.

Seither ist das Datenmodell gewachsen. Am Projekt hängen heute (Stand 2026-09-07) **dreizehn** abhängige Tabellen, und die pro Foto entstehende Zeilenmenge ist deutlich größer geworden: `photo_criterion_scores` hält bis zu 15 Zeilen je Foto (`criteria.py::CRITERIA_REGISTRY`), `photo_rankings` eine Zeile je Foto **je Kuratierungslauf**, dazu `photo_fine_labels` (0–2), `photo_category_classifications`, `photo_landmark_detections`, `photo_cloud_vision_errors`, `photo_scores`, `ratings`.

Die projektweit dokumentierte Größenannahme ist „mehrere tausend Fotos pro Projekt" (ADR [`0002`](./0002-hybrid-ai-scoring.md), Specs 0001/0002/0035/0038). Bei 5.000 Fotos und drei Kuratierungsläufen liegt die abhängige Zeilenmenge in der Größenordnung von 10<sup>5</sup>. Eine ORM-Kaskade lädt diese Zeilen sämtlich als Python-Objekte in den Identity-Map und setzt anschließend **ein DELETE je Zeile** ab. Das ist für einen synchronen HTTP-Request nicht tragfähig — nicht als Optimierungsfrage, sondern als Frage, ob der Endpunkt in der vorgesehenen Form („`204`, danach Navigation zur Projektliste") überhaupt funktioniert.

Ein zweiter Umstand kommt hinzu: die vollständige, geordnete Mengenlöschung eines Projekts **existiert bereits** — `demo_state.py::purge_demo_state` (Spec [`0174`](../features/0174-browser-zugang-fuer-claude.md)) räumt seine Demo-Projekte genau so ab, zeilenweise über `delete(Model).where(...)` in Fremdschlüssel-Reihenfolge. Ohne bewusste Entscheidung entstünden mit dem neuen Endpunkt **zwei** Stellen, die je für sich vollständig aufzählen, was alles an einem Projekt hängt — und zwei solche Listen driften.

Erschwerend: die Testsuite läuft gegen SQLite In-Memory (`conftest.py`) **ohne** `PRAGMA foreign_keys=ON`. Eine falsche Löschreihenfolge fällt dort strukturell nicht auf; sie fiele erst unter echtem Postgres im Betrieb auf. Eine Lösung, die auf handgepflegter Reihenfolge beruht, braucht deshalb eine Absicherung, die nicht von der Fremdschlüssel-Durchsetzung der Testdatenbank abhängt.

## Entscheidung

1. **Ein gemeinsames Modul `backend/src/photosort/project_deletion.py`** hält die einzige Aufzählung dessen, was am Projekt hängt. `api/projects.py::delete_project` und `demo_state.py::purge_demo_state` benutzen es beide; `purge_demo_state` verliert seine eigene Liste.

2. **Gelöscht wird als Mengenlöschung** (`delete(Model).where(<spalte>.in_(...))`), nicht über die ORM-Kaskade. Eine Löschung kostet dadurch eine feste, kleine Zahl von Anweisungen statt einer je Zeile, und lädt keine Zeile in den Speicher.

3. **Die Reihenfolge wird nicht von Hand behauptet, sondern aus den ORM-Metadaten abgeleitet.** Ein Test hält die Anweisungsfolge des Moduls gegen `reversed(Base.metadata.sorted_tables)` (SQLAlchemys topologische Fremdschlüssel-Sortierung) und schlägt fehl, sobald beides auseinanderläuft. Das ersetzt die Absicherung, die eine Testdatenbank ohne Fremdschlüssel-Durchsetzung nicht leisten kann.

4. **Vollständigkeit wird erzwungen, nicht erinnert.** Ein zweiter Test bestimmt über die Fremdschlüsselkanten von `Base.metadata` alle Tabellen, die `projects` **erreichen**, und verlangt, dass jede davon im Modul vorkommt. Eine künftige projektgebundene Tabelle, die niemand registriert, lässt diesen Test fehlschlagen. Tabellen, die `projects` nicht erreichen, fallen automatisch heraus — `users` und `fine_labels` sind Eltern, keine Kinder, und bleiben damit ohne eigene Ausnahmeliste unangetastet (`fine_labels` ist projektübergreifendes Vokabular, siehe ADR [`0032`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md); `users` sind die beiden Accounts).

5. **Der lokale Thumbnail-Cache wird über berechnete Pfade geräumt, nie über ein Verzeichnismuster.** Die `(photo_id, etag)`-Paare des Projekts werden **vor** der Zeilenlöschung gelesen; geräumt wird über `thumbnails.py`. Kein `glob`, kein `rmtree` — die Cache-Dateinamen sind flache Hash-Schlüssel ohne Projektzuordnung, ein Muster träfe auf einem geteilten Volume fremde Dateien (übernommen aus `purge_demo_state`, dort bereits so begründet).

## Begründung

Die naheliegende Alternative — bei der ORM-Kaskade bleiben — ist deklarativ und ordnet sich selbst, scheitert aber an der dokumentierten Größenannahme des Projekts. Sie wäre zudem nicht einmal wartungsärmer: sie verlangt, dass **jede** neue Kindtabelle eine `relationship` mit `cascade="all, delete-orphan"` bekommt, und genau diese Zusage ist bereits einmal gerissen (`photo_rankings` seit Spec 0037 ohne Kaskade, Punkt 0 der Spec 0044). Die Zusicherung aus Punkt 4 ist strenger als die bisherige Konvention: sie beruht auf einem Test, nicht auf einer Gewohnheit.

DB-seitiges `ondelete=CASCADE` mit `passive_deletes=True` wäre performant und selbstordnend, verlangte aber eine Migration über dreizehn Fremdschlüssel und verschöbe eine Löschregel an einen Ort, den die Testsuite (SQLite, Fremdschlüssel aus) gar nicht beobachtet. Der Gewinn gegenüber Punkt 2 ist gering, der Eingriff groß.

## Konsequenzen

- Eine neue projektgebundene Tabelle muss ab jetzt in `project_deletion.py` registriert werden; der Vollständigkeitstest erzwingt das und benennt die Datei in seiner Fehlermeldung.
- `purge_demo_state` wird schlanker und teilt ab jetzt das Verhalten des Endpunkts — ein Unterschied zwischen „Demo aufräumen" und „Projekt löschen" kann nicht mehr unbemerkt entstehen.
- Der Löschvorgang läuft weiterhin synchron im Request. Er ist damit an eine feste, kleine Anweisungszahl gebunden statt an die Zeilenmenge; ein Hintergrundjob bleibt unnötig.
- Die ORM-Kaskaden bleiben bestehen und bleiben nötig — sie tragen das Löschen **einzelner** Fotos/Bewertungen. Der Vollständigkeitstest dieser ADR prüft sie nicht mit; die bestehende Konvention „je neue Kindtabelle ein `test_deleting_photo_cascades_to_*`" (Testkonzept) bleibt dafür in Kraft.
- Fremdschlüsselverletzungen bei falscher Reihenfolge bleiben unter SQLite unsichtbar. Die Absicherung dagegen ist Punkt 3, nicht die Testdatenbank. Das ist bewusst getragenes Restrisiko und ergänzt den bestehenden Eintrag „Migrationsverhalten gegen echtes Postgres" unter „Bekannte Lücken" im Testkonzept.
