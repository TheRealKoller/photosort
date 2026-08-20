# 0039 - Kategorie-Kuratierung: Gruppierung nach Tagen und benannte Zeitfenster-Cluster

**Status:** Implemented ([PR #91](https://github.com/TheRealKoller/photosort/pull/91))
**Erstellt:** 2026-08-15
**Bezug:** Inbox-Eintrag [`specs/inbox/0020-kuratierung-tage-und-benannte-cluster.md`](../inbox/0020-kuratierung-tage-und-benannte-cluster.md), idea-sharpener-Gespräch mit Daniel

## Ziel

Auf der Kategorie-Kuratierungs-Seite (`/curate`, aus Spec [0037](./0037-gateführte-bewertungs-pipeline-mit-backfill.md)) werden Fotos aktuell nur nach Zeitfenster-Cluster (`cluster_key`) und Kategorie gruppiert, wobei die Cluster-Überschrift der technische, pro Lauf neu vergebene Bezeichner ist (z.B. "cluster-0"). Das sagt weder etwas über den Tag noch über die Tageszeit der Aufnahme aus und macht die Kuratierung schwerer nachvollziehbar.

Diese Spec ergänzt eine zusätzliche, übergeordnete Gruppierung nach Kalendertag sowie sprechende Tageszeit-Bezeichnungen samt exakter Uhrzeitspanne für die bestehenden Cluster — rein als Anzeigeverbesserung, ohne die zugrundeliegende Cluster-Bildungslogik zu verändern.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich auf der Kuratierungs-Seite die Fotos nach Tagen gruppiert sehen, und innerhalb eines Tages nach Zeitfenster-Clustern mit sprechenden Tageszeit-Bezeichnungen statt technischer Cluster-IDs, damit ich beim Kuratieren auf einen Blick erkenne, wann welche Fotos entstanden sind.

## Akzeptanzkriterien

1. **Tag-Gruppierung (Ebene 1, `<h2>`):** Fotos auf `/curate` werden primär nach Kalendertag gruppiert. Überschrift im Format "Wochentag TT.MM.JJJJ" (z.B. "Montag 20.07.2026"). Tage sind chronologisch aufsteigend sortiert.
2. **Cluster-Gruppierung (Ebene 2, `<h3>`) innerhalb eines Tages:** unverändert die bestehenden Zeitfenster-Cluster, aber chronologisch nach dem frühesten `taken_at` im Cluster sortiert — nicht mehr lexikographisch nach `cluster_key` (behebt nebenbei den latenten Sortier-Bug "cluster-10" < "cluster-2").
3. **Cluster-Überschrift:** zeigt Tageszeit-Bezeichnung + exakte Uhrzeitspanne der aktuell sichtbaren (Top-N-gefilterten) Fotos dieses Clusters, Format "Tageszeit (HH:MM–HH:MM Uhr)", z.B. "Nachmittags (12:00–14:00 Uhr)".
4. **Ein-Foto-/Ein-Minuten-Cluster:** enthält ein Cluster nur ein Foto oder mehrere Fotos derselben Minute, wird statt einer Spanne ein einzelner Zeitpunkt angezeigt: "Tageszeit (HH:MM Uhr)".
5. **Tageszeit-Bucket-Tabelle** (untere Grenze inklusiv, obere Grenze exklusiv, lückenlos):
   - Nachts: `[22:00, 05:00)`
   - Morgens: `[05:00, 08:00)`
   - Vormittags: `[08:00, 11:00)`
   - Mittags: `[11:00, 13:00)`
   - Nachmittags: `[13:00, 18:00)`
   - Abends: `[18:00, 22:00)`
6. **Frühestes-Foto-Regel:** sowohl Tag als auch Tageszeit-Bucket eines Clusters werden einheitlich vom chronologisch frühesten Foto im Cluster abgeleitet — gilt unverändert für Cluster, deren Fotos einen Mitternachtsübergang oder eine Tageszeit-Bucket-Grenze überspannen. Die angezeigte Uhrzeitspanne bleibt die exakte Min/Max-Spanne aller sichtbaren Fotos (kann bei einem mitternachtsübergreifenden Cluster z.B. "Nachts (23:50–00:10 Uhr)" lauten).
7. **Sticky Leerzustände auf allen drei Ebenen:** ein Tag/Cluster/eine Kategorie, der/die durch eine Live-Ablehnung vollständig leer wird, bleibt für die Dauer des Seitenbesuchs mit eigenem Leerzustandstext sichtbar statt spurlos zu verschwinden — "Keine Fotos für diesen Tag" (Tag), "Keine Fotos in dieser Tageszeit" (Cluster), "Keine Fotos in dieser Kategorie" (Kategorie, unverändert).
8. **Bestandsschutz:** Top-N-Query-Parameter, In-place-Nachrücken via Skeleton, Verwerfen-Button-Verhalten und Backlink bleiben unverändert funktionsfähig.
9. **Backend-Datenverfügbarkeit:** keine Änderung nötig — `PhotoOut.taken_at` liegt bereits pro Foto vor.
10. Die zugrundeliegende Cluster-Bildungslogik (1h-Zeitlücke, `assign_time_clusters`) bleibt unverändert.

## Datenmodell-Bezug

Keine Änderung. Verwendet ausschließlich bereits vorhandene Felder: `PhotoOut.taken_at` (naives Datetime, ISO-String ohne Zeitzone) und `PhotoRanking.cluster_key` (siehe [`docs/architecture.md`](../../docs/architecture.md), ADRs [0006](../decisions/0006-local-scoring-datamodel.md)/[0021](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md)).

## Architektur / Umsetzung

**Ansatz:** Reine Frontend-Änderung, kein Backend-Eingriff. `PhotoOut.taken_at` (`backend/src/photosort/api/photos.py:93`) liegt bereits pro Foto vor, unabhängig vom `ranking`-Objekt — Tag→Cluster-Gruppierung und Tageszeit-Label lassen sich vollständig client-seitig aus bereits vorhandenen Daten berechnen. Kein neues architekturrelevantes Muster, keine neue ADR nötig (technische Detailentscheidung innerhalb der bereits per ADR 0006/0021 akzeptierten Richtung: `cluster_key` ist bewusst freier String ohne UI-Festlegung).

**Wichtiger Datenformat-Hinweis:** `taken_at` ist ein naives Datetime (EXIF `DateTimeOriginal`, keine Zeitzone), serialisiert ohne `Z`/Offset (z.B. `"2026-07-20T10:00:00"`). Zeit-/Datumsextraktion deshalb per String-Slicing der ISO-Zeichenkette (`iso.slice(11, 16)` für `HH:MM`, `iso.slice(0, 10)` für den Kalendertag), NICHT über `Date`-Getter (`getHours()`/`getUTCHours()`) — deren Ergebnis hinge vom An-/Abwesenheitszustand eines `Z`-Suffix ab und wäre inkonsistent. Min/Max-Zeitpunkt-Vergleich innerhalb eines Clusters ebenfalls per reinem String-Vergleich (ISO-8601 sortiert lexikographisch = chronologisch), kein `Date`-Parsing nötig. Die bestehende Test-Fixture in `CurateCategoriesPage.test.tsx` (`taken_at: '...Z'`) spiegelt das reale Backend-Format nicht korrekt wider — beim Anfassen dieser Datei das `Z`-Suffix aus den Fixtures entfernen.

**Neue Datei `frontend/src/utils/timeOfDay.ts`** (reine Funktionen, analog `categoryLabels.ts`/`qualityLevel.ts`):
- `dayKeyOf(iso)`, `hourOf(iso)` — String-Slicing, siehe oben.
- `timeOfDayBucketLabel(hour)` — Lookup in der isolierten Bucket-Tabelle aus den Akzeptanzkriterien (Startstunde inklusiv, nächste Bucket-Startstunde exklusiv). Isoliert in einer Tabelle, damit Grenzen/Wortlaut bei Bedarf lokal angepasst werden können, ohne Komponentenlogik anzufassen.
- `formatTimeRange(minIso, maxIso)` → `"12:00–14:00 Uhr"`, kollabiert bei `minIso.slice(11,16) === maxIso.slice(11,16)` auf `"14:32 Uhr"` (Minuten-, nicht Sekundenpräzision).
- `formatClusterHeading(photos: {taken_at: string}[]): {dayKey: string; heading: string}` — findet min/max `taken_at` per String-Vergleich, leitet `dayKey` UND Tageszeit-Bucket vom chronologisch frühesten Foto ab, liefert die fertige Überschrift.
- `formatDayHeading(dayKey)` → Format "Wochentag TT.MM.JJJJ" (z.B. "Montag 20.07.2026"), Anzeige-Formatierung, nie für Vergleiche verwendet.

**Randfall-Regeln** (einheitliches Prinzip: frühestes Foto im Cluster entscheidet):
- Mitternachts-übergreifender Cluster → Tag = `dayKeyOf` des chronologisch frühesten Fotos im Cluster.
- Cluster, der eine Tageszeit-Grenze überschreitet → Bucket = `timeOfDayBucketLabel` der Stunde des chronologisch frühesten Fotos.
- Bewusster, dokumentierter Trade-off: die angezeigte Zeitspanne basiert nur auf den aktuell sichtbaren (Top-N-gefilterten) Fotos des Clusters, nicht zwingend auf dem vollständigen Backend-Cluster. Für eine reine Orientierungs-Anzeige akzeptabel, keine Backend-Aggregation nötig.

**Änderungen in `frontend/src/pages/CurateCategoriesPage.tsx`:**
- `groupByClusterAndCategory` (Zeile ~34-51) wird um eine Tag-Ebene erweitert: erster Durchlauf über `items` sammelt pro `cluster_key` alle zugehörigen Fotos (kategorieübergreifend) und berechnet einmal `formatClusterHeading(...)`; zweiter Durchlauf sortiert Fotos in `{[dayKey]: {[clusterKey]: {[categoryKey]: PhotoOut[]}}}` ein.
- Neuer `clusterMetaRef = useRef<Map<string, {dayKey: string; heading: string}>>()`: wird bei jedem Render für alle in `items` noch vorhandenen Cluster überschrieben, liefert für vollständig erschöpfte Cluster (keine Fotos mehr in `items`) die zuletzt bekannte Meta-Info — ohne diesen Cache ließe sich die Überschrift eines leeren Clusters nicht mehr berechnen. Einzige wirklich nicht-triviale Stelle dieser Änderung, braucht einen expliziten Regressionstest.
- Bestehendes Sticky-Leerzustand-Muster `knownGroupKeysRef` (JSON.stringify-Schlüsselpaar) wird von 2-Tupeln `[clusterKey, categoryKey]` auf 3-Tupel `[dayKey, clusterKey, categoryKey]` erweitert.
- Rendering: `<h2>` Tag (sortiert nach `dayKey`) → `<h3>` Cluster-Heading (sortiert nach dem ermittelten frühesten `taken_at`) → `<h4>` Kategorie (unverändert, eine Ebene tiefer).

**Reihenfolge der Umsetzung:** zuerst `timeOfDay.ts` + eigene Unit-Tests (reine Funktionen, keine Component-Abhängigkeit), danach die Gruppierungs-/Render-Änderung in `CurateCategoriesPage.tsx` inkl. Testanpassung, zuletzt der `clusterMetaRef`-Regressionstest für den Erschöpfungsfall.

Kein Backend-, kein `docs/architecture.md`-Update in diesem Schritt nötig.

## UI/UX

**Sichtbare Oberfläche:** Ja. Reine Frontend-Änderung der bestehenden Kategorie-Kuratierungs-Seite (`/curate`).

**Hierarchie & Typografie:**
- Tag-Überschrift (`<h2>`, z.B. "Montag 20.07.2026"): `text-xl`, `gap-6` (24px) Abstand zwischen Tagen.
- Cluster-Tageszeit-Überschrift (`<h3>`, z.B. "Nachmittags (12:00–14:00 Uhr)"): `text-lg`, `gap-4` (16px) zwischen Clustern innerhalb eines Tages.
- Kategorie-Überschrift (`<h4>`, unverändert): `text-sm`, `gap-2` (8px).
- Alle Überschriften nutzen `text-text-h` (bestehende Konvention).

**Layout:** Einfache, kontinuierliche Abfolge von Tagen ohne Einklappbarkeit. Begründung: die zwei wiederkehrenden Nutzer arbeiten ein Projekt in Sitzungen durch, nicht den ganzen Bestand auf einmal; zusätzliche Expand-Klicks würden das Durchsatz-Designprinzip verletzen. Bei sehr großen Projekten (>100 Tage) kann ein optionaler Sticky-Header/Springe-zu-Selektor als spätere Erweiterung ergänzt werden — nicht Teil dieser Spec.

> **Revidiert durch Spec [`0043`](./0043-kuratierung-tage-auf-zuklappbar.md) (2026-08-16):** Die Ablehnung der Einklappbarkeit gilt nicht mehr. Projekte sind seither größer geworden, die durchgehende Liste wurde bei vielen Tagen unübersichtlich — das überwiegt jetzt den ursprünglichen Durchsatz-Einwand. Der hier angedachte Sticky-Header/Springe-zu-Alternativ-Ansatz wurde im Rahmen von 0043 geprüft und verworfen (löst Navigation, aber nicht das Platzsparen-Ziel). Alle übrigen Festlegungen dieser Spec (Gruppierung, Sortierung, Sticky Leerzustand, Datenmodell) bleiben unverändert gültig.

**Sticky Leerzustand über alle Ebenen:** siehe Akzeptanzkriterium 7. Technisch: `knownGroupKeysRef` von `[clusterKey, categoryKey]` auf `[dayKey, clusterKey, categoryKey]` erweitert.

**Barrierefreiheit:** unverändert (semantisches HTML mit `<h2>`/`<h3>`/`<h4>`, bestehende `aria-label`-Konventionen auf Buttons bleiben erhalten).

## Security

Nicht relevant. Reine Anzeigelogik auf bereits über die bestehende, autorisierte API-Route sichtbaren Daten (`GET /projects/{project_id}/photos`) — keine neuen Eingaben von außen, keine neuen Berechtigungen, keine Änderung der Datensichtbarkeit zwischen den beiden Nutzern.

## Offene Fragen

Keine — alle im Gespräch aufgekommenen Punkte wurden geklärt (siehe Entscheidungen).

## Entscheidungen (2026-08-15, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Cluster-Benennung:** Tageszeit-Bezeichnung (morgens/vormittags/mittags/nachmittags/abends/nachts) + exakte Uhrzeitspanne kombiniert, nicht nur eine der beiden Varianten allein.
- **Mittags-Bucket:** auf 11:00–13:00 Uhr verbreitert (statt ursprünglich vorgeschlagener 11:00–12:00 Uhr), damit alle sechs Buckets eine plausible Breite haben.
- **Tages-Überschriftsformat:** kompakt mit Wochentag, z.B. "Montag 20.07.2026" (nicht das ausführlichere "Montag, 20. Juli 2026").
- **Mitternachts-übergreifender Cluster (Randfall):** als vernachlässigbar eingestuft — technische Detailentscheidung dem `architect`-Agenten überlassen (Tag/Bucket = frühestes Foto im Cluster entscheidet).
- **security-engineer nicht konsultiert (Schritt 8):** reine Anzeigelogik auf bereits sichtbaren, bestehenden Daten derselben autorisierten API-Route — keine neuen Eingaben, keine Berechtigungsänderung, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern.
- `specs/architecture/0002-testkonzept.md` wurde im Zuge dieser Spec um eine Sektion zu naiven Datums-/Uhrzeit-Strings (String-Slicing statt `Date`-Getter) ergänzt — als projektweit relevantes Muster für künftige Datums-/Uhrzeit-Ableitungen aus Backend-Feldern.

## Out of Scope

- ~~Änderung der 1h-Zeitfenster-Cluster-Bildungslogik selbst.~~ (teilweise aufgehoben durch Spec [`0051`](./0051-gps-landmark-cluster-bildung.md): GPS-Nähe und erkannte Sehenswürdigkeiten können ab dort zusätzlich zur Zeit einen Cluster-Split auslösen; die reine Tageszeit-Bezeichnung und -Anzeige dieser Spec bleiben unverändert gültig.)
- Backend-Aggregation für eine vollständige (nicht Top-N-gefilterte) Cluster-Zeitspanne.
- ~~Einklappbare/kollabierbare Tages-Abschnitte.~~ (revidiert durch Spec [`0043`](./0043-kuratierung-tage-auf-zuklappbar.md))
- Anpassung der Bucket-Grenzen/des Wortlauts über die in dieser Spec festgelegte Tabelle hinaus.
