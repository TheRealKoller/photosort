# 0349 - Verwaiste lokale Bildkopien nach jedem Scan aufräumen

**Status:** Accepted
**Erstellt:** 2026-09-10
**Bezug:** [Issue #349](https://github.com/TheRealKoller/photosort/issues/349)

## Ziel

PhotoSort legt von jedem Foto zwei herunterskalierte Kopien lokal ab, damit Raster- und
Einzelbildansicht schnell bleiben. Diese Kopien sind die einzigen echten Bilddaten der Familie,
die außerhalb von OpenCloud liegen.

Bekommt ein Foto auf OpenCloud eine neue Fassung, verschwindet es dort, oder wird ein Projekt
gelöscht, gehören die zugehörigen Kopien zu nichts mehr. Sie bleiben trotzdem liegen: über die
Oberfläche nicht mehr erreichbar, in keiner Speicheranzeige sichtbar und ohne Aussicht, je wieder
zu verschwinden. Der Rest wächst dadurch nur — und weil er unsichtbar ist, bemerkt ihn niemand.

Nach jedem Scan soll der lokale Bild-Cache deshalb nur noch das enthalten, was zu einem
tatsächlich vorhandenen Foto gehört. Nutzen für die beiden Nutzer des Systems: auf dem Homeserver
liegen keine unzuordenbaren Familienbilder mehr, und der ausgewiesene Speicherbedarf entspricht
wieder dem, was die Platte wirklich trägt.

## User Story

Als Nutzer von PhotoSort möchte ich, dass der lokale Bild-Cache nach jedem Scan automatisch von
Kopien befreit wird, die zu keinem vorhandenen Foto mehr gehören, damit auf dem Homeserver keine
unzuordenbaren Familienbilder liegen bleiben und der angezeigte Speicherbedarf der Wirklichkeit
entspricht.

## Akzeptanzkriterien

- [ ] Nach jedem erfolgreich abgeschlossenen Scan enthält der lokale Bild-Cache keine Datei mehr,
      auf die alle drei Bedingungen zugleich zutreffen: sie trägt das Namensschema der Bildkopien
      (`<64-stelliger Schlüssel>_thumbnail.jpg` bzw. `_display.jpg`), sie gehört zu keinem in
      PhotoSort vorhandenen Foto in seiner aktuellen Fassung, und ihre Änderungszeit liegt länger
      als die Schonfrist (eine Stunde) zurück. Jüngere Reste bleiben liegen und verschwinden beim
      ersten erfolgreichen Scan, der nach Ablauf ihrer Schonfrist läuft — nicht zwingend beim
      unmittelbar nächsten. Alles andere im Verzeichnis bleibt unangetastet. (Gegenüber dem
      Issue-Wortlaut geschärft — siehe „Entscheidungen", Zielkonflikt mit Kriterium 4.)
- [ ] Die Bereinigung erfasst alle bekannten Entstehungswege solcher Reste: ein Foto hat auf
      OpenCloud eine neue Fassung bekommen; ein Foto ist dort verschwunden und wurde beim Scan aus
      PhotoSort entfernt; ein Projekt wurde gelöscht und das Aufräumen seiner Kopien schlug damals
      fehl oder brach ab.
- [ ] Kopien, die zu einem vorhandenen Foto in seiner aktuellen Fassung gehören, bleiben
      ausnahmslos erhalten — auch die von Fotos aus anderen Projekten als dem gerade gescannten.
- [ ] Läuft zeitgleich ein Scan eines anderen Projekts, verliert dieser durch die Bereinigung
      keine der Kopien, die er gerade erzeugt. Operationalisiert über die drei Eigenschaften,
      die das tragen und einzeln prüfbar sind: (a) eine Kopie, zu der es (noch) keine sichtbare
      Foto-Zeile gibt, wird nicht entfernt, solange ihre Änderungszeit jünger als die Schonfrist
      ist; (b) die Verzeichnisaufnahme läuft vor dem Datenbank-Schnappschuss, damit jede in
      diesem Fenster committete Zeile ihre Datei schützt; (c) eine zwischen Aufnahme und
      Löschung neu geschriebene Datei ist wieder unantastbar.
- [ ] Der bereits heute vorhandene Rest verschwindet ohne gesonderten Anstoß: der erste Scan nach
      der Umsetzung räumt ihn mit auf.
- [ ] Die Bereinigung läuft ohne Zutun ab — kein neues Bedienelement, kein Bestätigungsschritt,
      keine Einstellung, keine Meldung in der Oberfläche.
- [ ] Lässt sich eine einzelne Datei nicht entfernen, bleibt der Scan trotzdem erfolgreich, die
      übrigen Reste werden dennoch entfernt, und der Pfad der gescheiterten Datei steht im Log.
      Eine Datei, die zwischenzeitlich bereits verschwunden ist, gilt dabei nicht als Fehlschlag
      und wird nicht gemeldet.
- [ ] Bricht ein Scan ab oder schlägt er fehl, findet keine Bereinigung statt; der nächste
      erfolgreiche Scan holt sie nach.
- [ ] Der auf der Projekt-Statistikseite ausgewiesene Speicherbedarf und der tatsächlich belegte
      Platz laufen nicht länger dauerhaft auseinander: nach einer Bereinigung entspricht die Summe
      der Dateigrößen im Bild-Cache der Summe der über alle Projekte ausgewiesenen Speicherbedarfe
      — bis auf Dateien, die jünger als die Schonfrist sind, und Dateien, die nicht dem
      Namensschema der Bildkopien folgen.

## Datenmodell-Bezug

**Keine Änderung.** Weder neue Entität noch neue Spalte, keine Migration. Gelesen werden
ausschließlich die bestehenden Felder `Photo.id` und `Photo.etag` (über alle Projekte hinweg),
aus denen sich der Cache-Schlüssel `sha256(photo_id:etag)` berechnet
(`thumbnails.py::cache_key`). Siehe [`docs/architecture.md`](../../docs/architecture.md),
Komponenten „Lokaler Cache" und „Worker".

## Architektur / Umsetzung

**Grundlage:** ADR [`0075`](../decisions/0075-verwaiste-bildkopien-verzeichnisdurchgang-mit-schonfrist.md)
(mit dieser Story angelegt; sie löst ADR [`0062`](../decisions/0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md)
**Punkt 5** in genau einem Teilsatz ab — der Kopf von 0062 trägt den Vermerk bereits).

> **Fünf verbindliche Auflagen aus den nachfolgenden Konsultationen gehen diesem Entwurf vor**,
> wo sie ihm widersprechen — sie sind hier eingearbeitet und stehen ausführlich in „Security"
> (Punkte 1, 2, 5) und „Teststrategie" (Auflagen 1, 2):
> `re.fullmatch` statt `.match`; `Path.lstat()` **plus** erneutes `S_ISREG` statt `Path.stat()`
> vor dem `unlink`; fail-closed bei leerer Gültigkeitsmenge; `await session.refresh(scan_run)`
> nach dem `rollback()` im Bereinigungs-Handler; `FileNotFoundError` beim `lstat` ist kein
> Fehlschlag.

Die Story bewegt sich vollständig in **Worker + Cache-Schicht**: keine Tabelle, keine Spalte,
keine Migration, kein Antwortfeld, keine Route, keine Oberfläche, keine neue Abhängigkeit
(`os.scandir`, `re`, `time` — Standardbibliothek). `api/stats.py` bleibt **unverändert**: die
Statistikseite misst schon heute genau die Menge, die nach der Bereinigung noch existiert — das
letzte Akzeptanzkriterium ist eine Folge der Bereinigung, keine eigene Änderung.

### Der Defekt in einem Satz

`thumbnails.py::cache_key` ist `sha256(f"{photo_id}:{etag}")`. Dieselbe Rechnung, die eine alte
Fassung **unerreichbar** macht, lässt sie auch aus jeder Löschmenge herausfallen: `api/photos.py`,
`measure_cache_usage` und `delete_cached_variants` rechnen alle drei aus **vorhandenen** Zeilen.
Was zu keiner Zeile mehr gehört, ist deshalb weder sichtbar noch löschbar. Wer diese Dateien
finden will, muss das Verzeichnis lesen — genau einmal, an genau einer Stelle, eng gemustert.

### Entwurfsentscheidungen

**1. Zwei reine Funktionen in `thumbnails.py`, die Orchestrierung in einem neuen
`cache_cleanup.py`.** Das Namensschema (`cache_key`, `_thumbnail.jpg`/`_display.jpg`) lebt in
`thumbnails.py`; das **Muster**, das dieses Schema wiedererkennt, gehört daneben — wer das eine
ändert, muss das andere in derselben Datei anfassen. `thumbnails.py` bleibt dabei
DB-frei/synchron, wie es `measure_cache_usage`/`delete_cached_variants` schon sind:

```python
# Nachtrag aus der Umsetzung: das Endanker ist `\Z`, nicht `$` - siehe Security Punkt 1.
CACHE_FILE_PATTERN = re.compile(r"^([0-9a-f]{64})_(?:thumbnail|display)\.jpg\Z")

@dataclass(frozen=True)
class CacheEntry:          # path, key, mtime
@dataclass(frozen=True)
class CacheSweepResult:    # deleted_files, freed_bytes, failed_files, kept_recent

def collect_cache_entries(cache_dir: Path) -> list[CacheEntry]
def delete_orphaned_entries(
    entries: Sequence[CacheEntry], valid_keys: AbstractSet[str], mtime_cutoff: float
) -> CacheSweepResult
```

Die Zeitgrenze kommt als **Parameter** herein, nicht aus `settings` — dadurch sind beide
Funktionen ohne Warten und ohne Uhr-Attrappe testbar (`tmp_path` + `os.utime`).

Die async-Klammer liegt in `backend/src/photosort/cache_cleanup.py` (eigenes Modul wie
`project_deletion.py`, nicht in den bereits 2.863 Zeilen langen `worker.py`):

```python
CACHE_CLEANUP_GRACE_SECONDS = 3600

async def cleanup_orphaned_cache(session, cache_dir: Path) -> CacheSweepResult
```

**2. Gelöscht wird nur, was fünf Bedingungen zugleich erfüllt** (ADR 0075 Punkt 2): direkter
Eintrag in `cache_dir` (**nicht rekursiv**), **reguläre** Datei (`os.scandir`,
`follow_symlinks=False` — kein Verzeichnis, kein Symlink), Name trifft `CACHE_FILE_PATTERN`
**exakt** (`re.fullmatch`, nie `.match` — siehe Security Punkt 1), Schlüssel nicht in der
Gültigkeitsmenge, Änderungszeit vor der Schonfrist-Grenze. Alles
andere bleibt liegen, ausdrücklich auch Unbekanntes. Hinzu kommt die **fail-closed-Bedingung**
(Security Punkt 5): Ist die Gültigkeitsmenge leer, obwohl Einträge vorhanden sind, wird nichts
gelöscht und eine WARNING geschrieben. Das ersetzt die Schutzwirkung, die das Verbot
in ADR 0062 Punkt 5 hatte: das Muster ist nicht „alles im Verzeichnis", sondern die exakte
Signatur der eigenen Schreiboperation.

**3. Gültigkeitsmenge = alle Fotos aller Projekte.**

```python
rows = (await session.execute(select(Photo.id, Photo.etag))).all()
valid_keys = {cache_key(photo_id, etag) for photo_id, etag in rows}
```

Bewusst **ohne** `where(project_id == ...)`: der Cache ist flach und projektübergreifend, eine
projektbezogene Menge wäre für ihn die falsche Frage und löschte fremde, gültige Kopien
(Akzeptanzkriterium 3). Spalten-Tupel statt `select(Photo)` — keine ORM-Objekte, kein
Identity-Map-Effekt nach dem Commit. Größenordnung bei mehreren tausend Fotos je Projekt: einige
zehntausend kurze SHA-256-Berechnungen, Millisekunden.

**4. Die Reihenfolge ist Teil der Lösung, nicht Geschmackssache: erst Verzeichnis, dann
Datenbank.**

```python
entries = await asyncio.to_thread(collect_cache_entries, cache_dir)   # T1
valid_keys = {...}                                                    # T2 > T1
result = await asyncio.to_thread(delete_orphaned_entries, entries, valid_keys, cutoff)
```

Nur so ist **jede** Zeile, die zwischen T1 und T2 committet, im Schnappschuss enthalten und
schützt ihre Datei. In der umgekehrten Reihenfolge wäre jede in diesem Fenster sichtbar gewordene
Datei ungeschützt. Der Schnappschuss wird nach einem Commit-Rand gezogen und sieht damit den
aktuellen Stand fremder Transaktionen.

**5. Das Nebenläufigkeitskriterium trägt die Schonfrist — hier ist der Kern.**
Ein paralleler Scan schreibt die Cache-Datei **vor** dem Commit der Foto-Zeile
(`_process_scan_block`: Zeile anlegen/`flush()` → Download+Thumbnail → Commit erst nach dem ganzen
Block, ADR 0020 Fallstrick 2). In diesem Fenster ist die Datei da und die Zeile für uns unsichtbar
— eine rein datenbankbasierte Bereinigung löschte genau das, was der andere Scan gerade erzeugt.
Deshalb:

```python
cutoff = time.time() - CACHE_CLEANUP_GRACE_SECONDS   # eine Stunde
```

Eine Datei, deren Zeile noch nicht committet ist, wurde **zwangsläufig eben erst geschrieben** —
Jugend schützt. Ein Scan committet spätestens je Block (`settings.scan_download_concurrency`,
Vorgabe 4); eine Stunde liegt um Größenordnungen darüber. `delete_orphaned_entries` liest die
Änderungszeit **unmittelbar vor dem `unlink`** erneut (`Path.lstat()` — **nicht** `Path.stat()`,
das einem untergeschobenen Symlink folgte, siehe Security Punkt 2; derselbe Aufruf liefert
`st_size` für die freigegebenen Bytes, und `S_ISREG` wird dabei erneut geprüft) und prüft erneut
gegen `cutoff` — ein zwischenzeitliches
Neuschreiben derselben Datei (Foto kehrt auf eine frühere Fassung zurück) macht sie sofort wieder
unantastbar. Beide Uhren stammen aus derselben Quelle (Host-Kernel: `st_mtime` und `time.time()`);
es wird **nie** gegen einen Datenbank-Zeitstempel verglichen.

Der Wert ist eine **Konstante**, keine Umgebungsvariable — ein Korrektheitsabstand, kein
Betriebsparameter; als Einstellung lüde er dazu ein, ihn auf 0 zu setzen und still
Akzeptanzkriterium 4 aufzugeben. `.env.example`/`docs/setup.md` bleiben deshalb unberührt.

**6. Aufgerufen wird hinter dem Fehler-`except`, nicht darin.** In `worker.py::run_project_scan`
wandert `return scan_run` aus dem `try` heraus; der Erfolgspfad fällt hinter den Handler durch:

```python
except Exception as exc:
    await _fail_run(session, scan_run, str(exc))
    return scan_run

# Nur erreichbar, wenn der Lauf SUCCESS ist (Akzeptanzkriterium: kein Aufräumen
# nach Abbruch/Fehlschlag) - und außerhalb des Handlers, damit ein Fehler beim
# Aufräumen einen bereits erfolgreichen Lauf nicht nachträglich auf FAILED setzt.
try:
    await cleanup_orphaned_cache(session, cache_dir)
except Exception:
    await session.rollback()
    await session.refresh(scan_run)   # Auflage 1 der Teststrategie - sonst MissingGreenlet
    logger.warning("Bereinigung des Bild-Caches fehlgeschlagen", exc_info=True)
return scan_run
```

Das `rollback()` im Handler ist nicht Kosmetik: schlägt die Schnappschuss-Abfrage fehl, ist die
Transaktion sonst blockiert, und der anschließende Zugriff auf `scan_run.id` in `scan_project`
(nach dem Commit expired) liefe in einen Folgefehler. `asyncio.CancelledError` propagiert
unverändert (arqs Buchhaltung), flippt den erfolgreichen Lauf aber nicht mehr auf `FAILED`.

Bewusst in `run_project_scan` und nicht in `scan_project`: dort ist die Bereinigung über die
bestehenden Tests mit `tmp_path`-Cache und Fake-Client beobachtbar, ohne `async_session_factory`
und echten `OpenCloudClient`.

**7. Best-effort je Datei.** `OSError` beim `lstat`/`unlink` → mit Pfad **loggen**, `failed_files`
hochzählen, weitermachen. **Ausnahme (Auflage 2 der Teststrategie): `FileNotFoundError` beim
`lstat` ist kein Fehlschlag** — er wird still übersprungen, weder gezählt noch geloggt. Weil die
Änderungszeit erst unmittelbar vor dem `unlink` gelesen wird, trifft die harmlose
Wettlaufsituation ab jetzt den `lstat` und nicht mehr das `missing_ok=True` des `unlink`. Dasselbe Muster wie
`delete_cached_variants`. Absolute Cache-Pfade gehören ins Log, nie in eine HTTP-Antwort.
Abschluss ist **eine** INFO-Zeile (entfernt / freigegebene Bytes / Fehlschläge / wegen Schonfrist
behalten) — keine Meldung in der Oberfläche, kein Bedienelement, keine Einstellung.

### Was die Bereinigung dadurch abdeckt

| Entstehungsweg | Deckung |
|---|---|
| Neue Fassung auf OpenCloud (`etag` gewechselt) | alte Schlüssel fallen aus der Gültigkeitsmenge, Dateien stammen aus einem früheren Scan → sofort im selben Durchgang |
| Foto verschwunden, Zeile beim Re-Scan entfernt | `session.delete(...)` ist Teil desselben Commits, der `SUCCESS` setzt → Schlüssel weg, bevor der Schnappschuss gezogen wird |
| Projektlöschung, deren Datei-Aufräumen scheiterte | gar keine Zeile mehr → Schlüssel ungültig, Dateien alt → derselbe Durchgang |
| Abgebrochener/zurückgerollter Scan-Block | Datei ohne Zeile → nach Ablauf der Schonfrist beim nächsten Scan |

### Betroffene Dateien

| Datei | Art |
|---|---|
| `backend/src/photosort/thumbnails.py` | erweitert: `CACHE_FILE_PATTERN`, `CacheEntry`, `CacheSweepResult`, `collect_cache_entries`, `delete_orphaned_entries` |
| `backend/src/photosort/cache_cleanup.py` | **neu**: `CACHE_CLEANUP_GRACE_SECONDS`, `cleanup_orphaned_cache` |
| `backend/src/photosort/worker.py` | `run_project_scan`: `return` aus dem `try` heraus, Aufruf hinter dem Handler |
| `backend/tests/test_thumbnails.py` | Tests der beiden reinen Funktionen |
| `backend/tests/test_cache_cleanup.py` | **neu**: Orchestrierung (Gültigkeitsmenge über alle Projekte, Reihenfolge, Grenze) |
| `backend/tests/test_worker_scan_project.py` | Tests der Anbindung (Erfolg räumt, Fehlschlag/Abbruch nicht, Dateifehler entwertet den Scan nicht) |
| `specs/decisions/0075-…md`, `specs/decisions/0062-…md` (Kopfvermerk) | angelegt/ergänzt |
| `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md` | ergänzt (Konsultationen Schritt 3) |
| `docs/architecture.md` | Komponenten „Lokaler Cache"/„Worker" + Kopfeintrag |

Nicht betroffen: `api/stats.py`, `api/photos.py`, `api/projects.py`, `project_deletion.py`,
`demo_state.py`, `models.py`, Migrationen, `frontend/`, `e2e/`, `.env.example`, `docs/setup.md`.

### Umsetzungsreihenfolge (TDD)

1. **Muster + Verzeichnisaufnahme** (`collect_cache_entries`): trifft nur `<64 hex>_thumbnail.jpg`
   /`_display.jpg`, ignoriert Fremddateien, Unterverzeichnisse, Symlinks; fehlendes Verzeichnis =
   leere Liste, kein Fehler.
2. **Löschentscheidung** (`delete_orphaned_entries`): gültiger Schlüssel bleibt; ungültiger +
   alt geht; ungültiger + jung bleibt (`kept_recent`); Neuschreiben zwischen Aufnahme und `unlink`
   rettet die Datei (per `os.utime` gestellt); `OSError` je Datei bricht nichts ab; `freed_bytes`.
3. **Orchestrierung** (`cleanup_orphaned_cache`): Gültigkeitsmenge über **alle** Projekte,
   Verzeichnis vor Datenbank, Grenze aus `time.time()`, beide Dateiteile über `asyncio.to_thread`,
   INFO-Logzeile.
4. **Anbindung in `run_project_scan`**: Erfolg räumt auf; `FAILED` und `CancelledError` räumen
   nicht; ein Fehler in der Bereinigung lässt den Lauf `SUCCESS` und die Session benutzbar.
5. **Bestandsschutz**: bestehende Scan-Tests bleiben grün (Regressionszusage für die
   `return`-Verschiebung); Ende-zu-Ende über zwei Projekte: Scan von A entfernt A-Reste **und**
   Reste eines gelöschten Projekts, lässt gültige B-Dateien und frische B-Dateien unberührt.

## UI/UX

**nicht relevant.** Keine Frontend-Datei ist betroffen, es entstehen keine neuen Daten, und kein
vorhandener Anzeigewert ändert Herkunft oder Format. Akzeptanzkriterium 6 schließt jede
Oberflächenänderung ausdrücklich aus (kein Bedienelement, kein Bestätigungsschritt, keine
Einstellung, keine Meldung). Der in Akzeptanzkriterium 9 genannte Speicherbedarf der
Projekt-Statistikseite wird unverändert berechnet und unverändert dargestellt — er stimmt danach
lediglich wieder, weil im Cache nichts Unzuordenbares mehr liegt.

## Teststrategie

Festgelegt durch `test-engineer`. Projektweite Konventionen und die daraus neu abgeleiteten Regeln
stehen im Testkonzept
([`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Sektion „Der
erste Testgegenstand, dessen Korrektheit an einer Datei-Änderungszeit hängt"); hier steht, was für
**diese** Story konkret zu prüfen ist.

### Zwei Auflagen an die Umsetzung — beide am laufenden Code nachgemessen

**1. Nach dem `rollback()` im Bereinigungs-Handler gehört ein `await session.refresh(scan_run)`.**
Der Entwurf fängt einen Fehler der Bereinigung ab und rollt zurück, damit die Transaktion nicht
blockiert bleibt. Genau dieses `rollback()` macht den Rückgabewert unbrauchbar:
`scan_project` liest unmittelbar danach `scan_run.id`. Nachgemessen am 2026-09-10 gegen die
Testdatenbank (`expire_on_commit=False`):

| Ablauf | Attributzugriff danach |
|---|---|
| `commit()` → `rollback()` ohne Anweisung dazwischen | funktioniert |
| `commit()` → `SELECT` → `rollback()` | **`sqlalchemy.exc.MissingGreenlet`** |
| `commit()` → `SELECT` → `rollback()` → `refresh()` | funktioniert |

Die Bereinigung setzt genau die mittlere Reihenfolge (Schnappschuss-Abfrage, dann Fehler, dann
`rollback()`). Ohne `refresh()` stürzt der Job also **nach einem erfolgreichen Scan** ab, der Lauf
steht auf `SUCCESS` und arq verbucht den Job als fehlgeschlagen — dieselbe Fehlerklasse wie der
Copilot-Fund zu `_fail_run` (PR #67), dort bereits so behoben. Der Fall ist nicht zufällig, sondern
strukturell, und braucht einen Test in der Bauform von
`test_fail_run_result_is_immediately_readable_without_a_fresh_query` (Attributzugriff ohne
dazwischenliegendes `await`, kein frisches `select`).

**2. `FileNotFoundError` beim `stat` ist kein Fehlschlag.** Weil die Änderungszeit unmittelbar vor
dem `unlink` erneut gelesen wird, trifft die harmlose Wettlaufsituation („eine andere Stelle hat
die Datei inzwischen entfernt") ab jetzt den `stat`-Aufruf und nicht mehr das `missing_ok=True` des
`unlink` — das dort vorgesehene Auffangnetz greift nie. Verbindlich: `FileNotFoundError` wird still
übersprungen (kein `failed_files`, keine WARNING-Zeile), jeder andere `OSError` zählt als Fehlschlag
und wird mit Pfad geloggt. Sonst meldet der Normalfall Fehler, die keine sind, und ein echtes
Rechteproblem geht im Rauschen unter (Akzeptanzkriterium 7 ist entsprechend formuliert).

### Ebenenverteilung

| Ebene | Gegenstand | Ort |
|---|---|---|
| Unit, dateisystemnah | `CACHE_FILE_PATTERN`, `collect_cache_entries` | `tests/test_thumbnails.py` |
| Unit, rein | `delete_orphaned_entries`, `CacheSweepResult` | `tests/test_thumbnails.py` |
| Integration, DB + Dateisystem | `cleanup_orphaned_cache` (Gültigkeitsmenge, Reihenfolge, Grenze, Log) | `tests/test_cache_cleanup.py` (neu) |
| Integration, Lauf | Anbindung in `run_project_scan`, Bestandsschutz, Zwei-Projekte-Fall | `tests/test_worker_scan_project.py` |
| Frontend/E2E | **nichts.** Keine Datei unter `frontend/`, keine Route, kein Antwortfeld, kein sichtbarer Zustand. | — |

Die Zuordnung folgt der bereits etablierten Arbeitsteilung von `thumbnails.py`: dort lebt die
Pfadbildung, also auch das Muster, das sie wiedererkennt — und dort sind beide Funktionen gegen
`tmp_path` prüfbar, ohne Datenbank, ohne Fake-Client und ohne Uhr.

### 1. Muster und Verzeichnisaufnahme (`collect_cache_entries`, `test_thumbnails.py`)

Bauform wie der bestehende `TestMeasureCacheUsage`-Block: eine Klasse, `tmp_path`, der lokale
Helfer `_write_variant`. **Erwartete Treffer entstehen über `thumbnail_path()`/`display_path()`,
nie als handgetippter Hex-String** — dieselbe Anti-Drift-Regel wie beim Cache-Cleanup der
Projektlöschung.

- Fehlendes Verzeichnis → leere Liste, **kein** Fehler (Gegenstück zu
  `test_missing_cache_directory_yields_zero`). Leeres Verzeichnis → leere Liste.
- Beide Varianten desselben Fotos werden als **zwei** Einträge aufgenommen, beide mit demselben
  Schlüssel; `CacheEntry` trägt Pfad, Schlüssel und Änderungszeit.
- **Nicht-Treffer als eigene Fallgruppe, und zwar schemaähnlich** — ein „irgendwas-fremdes.jpg"
  allein prüft das Muster nicht: 63 und 65 Hex-Stellen, Großbuchstaben im Hex-Teil, `.jpeg` statt
  `.jpg`, `_preview.jpg`, `_thumbnail.jpg` ohne Schlüssel, Präfix und Suffix um einen gültigen
  Namen herum.
- **Unterverzeichnis mit gültigem Namen** wird nicht aufgenommen (auch nicht rekursiv abgestiegen:
  eine gültig benannte Datei *darin* taucht nicht auf).
- **Symlink mit gültigem Namen** auf eine Datei außerhalb des Cache-Verzeichnisses wird nicht
  aufgenommen und nicht verfolgt — der Fall, der die Schutzwirkung des abgelösten Verbots aus
  ADR 0062 Punkt 5 ersetzt, und ohne eigenen Test nur eine Absichtserklärung.
- Änderungszeit im Eintrag entspricht der per `os.utime` gestellten (kein Vergleich gegen `now`).
- `OSError` beim Aufzählen einer einzelnen Datei bricht die Aufnahme nicht ab.

### 2. Löschentscheidung (`delete_orphaned_entries`, `test_thumbnails.py`)

Keine Uhr, keine Wartezeit: das Alter wird ausschließlich über `os.utime(pfad, (t, t))` erzeugt,
die Grenze kommt als Parameter herein. **Jeder Löschfall trägt eine Überlebens-Assertion auf einer
Nachbardatei** — ein Test, der nur „die verwaiste Datei ist weg" behauptet, bliebe grün, wenn die
Implementierung das Verzeichnis leerräumt.

- Gültiger Schlüssel + alt → bleibt. Ungültig + alt → weg. Ungültig + jung → bleibt und zählt in
  `kept_recent`. Der dritte Fall braucht das eigene Zählfeld: ohne es ist „bewusst behalten" von
  „gar nicht betrachtet" nicht zu unterscheiden, und der Fall, der Kriterium 4 trägt, bestünde leer.
- Grenzwert exakt auf `cutoff` — eine Seite festlegen und prüfen (`mtime < cutoff` löscht,
  `mtime == cutoff` bleibt).
- **Neuschreiben zwischen Aufnahme und `unlink`:** Einträge über `collect_cache_entries` aufnehmen,
  *danach* dieselbe Datei per `os.utime` auf „gerade eben" stellen, dann löschen lassen → Datei
  überlebt, `kept_recent == 1`. Ohne diesen Fall bliebe eine Implementierung grün, die die
  Änderungszeit aus dem Schnappschuss statt frisch liest.
- `freed_bytes` summiert die tatsächlichen Größen (zwei Dateien unterschiedlicher Größe), und
  **nur** die der gelöschten.
- `OSError` beim `unlink` (Muster: `monkeypatch` auf `Path.unlink` wie im bestehenden
  `test_delete_cached_variants_keeps_going_after_an_oserror_and_logs_the_path`) → `failed_files`
  hochgezählt, Pfad im Log, **die zweite verwaiste Datei ist trotzdem weg**. Die zweite Hälfte ist
  die eigentliche Zusage und braucht die zweite Datei im Aufbau.
- `OSError` beim `stat` (`monkeypatch` auf `Path.stat`, Muster aus
  `test_an_os_error_while_measuring_is_swallowed`) → dasselbe, Datei bleibt liegen.
- **`FileNotFoundError` beim `stat` → still übersprungen:** kein `failed_files`, `caplog` leer
  (Auflage 2). Aufbau: Eintrag aufnehmen, Datei danach löschen, dann `delete_orphaned_entries`.
- Leere Eingabe / leere Gültigkeitsmenge / alle Schlüssel gültig → jeweils Ergebnis mit vier Nullen.
- `CacheSweepResult` ist `frozen` (Bauform `test_cache_usage_is_frozen`).

### 3. Orchestrierung (`cleanup_orphaned_cache`, `tests/test_cache_cleanup.py`, neu)

`db_session`-Fixture, `tmp_path` als Cache-Verzeichnis, Fotos direkt als `Photo`-Zeilen angelegt
(kein Scan, kein Fake-Client) — die Ebene, auf der die Gültigkeitsmenge geprüft wird.

- **Projektübergreifend (Kriterium 3):** zwei Projekte, je ein Foto mit alten Cache-Dateien, dazu
  eine verwaiste alte Datei. Ergebnis: die verwaiste ist weg, **beide** Fotodateien sind da. Ein
  Aufbau mit nur einem Projekt hielte ein versehentliches `where(project_id == ...)` nicht auf —
  und genau das wäre der naheliegendste Fehler dieser Bauform.
- **Veralteter `etag` (Kriterium 2, erster Entstehungsweg):** Zeile trägt `etag-neu`, auf der Platte
  liegen die Dateien zu `etag-alt` (alt) und `etag-neu` (alt) → die alten weg, die aktuellen da.
- **Foto gelöscht / Projekt gelöscht (zweiter und dritter Entstehungsweg):** gar keine Zeile, nur
  Dateien → weg. Für den Projektfall zusätzlich mit einem zweiten, noch vorhandenen Projekt daneben.
- **Grenze aus `time.time()`:** eine Datei knapp innerhalb der Schonfrist (`now - 60`) bleibt, eine
  knapp außerhalb (`now - CACHE_CLEANUP_GRACE_SECONDS - 60`) geht. Hier — und nur hier — wird die
  Umrechnung „Konstante → Grenze" geprüft, mit großzügigem Abstand statt auf die Sekunde genau.
  Zusätzlich: `CACHE_CLEANUP_GRACE_SECONDS == 3600` festgenagelt, damit ein stilles Absenken
  auffällt (Kriterium 4 hängt allein an dieser Zahl).
- **Reihenfolge Verzeichnis → Datenbank, als beobachtete Abfolge in EINER Ereignisliste:** ein Spion
  um `cache_cleanup.collect_cache_entries` trägt `"verzeichnis"` ein, das
  `before_cursor_execute`-Ereignis der Engine (etabliertes Muster, `test_project_deletion.py`) trägt
  beim `SELECT` auf `photos` `"datenbank"` ein; Assertion auf die Reihenfolge in der gemeinsamen
  Liste. Zwei getrennte Listen wären kein Reihenfolgebeweis. Warum nicht über die Wirkung geprüft
  wird, steht unter „Was bewusst nicht getestet wird".
- **Beide Dateiteile laufen außerhalb der Event-Loop:** die Spione zeichnen `threading.get_ident()`
  auf, der Test vergleicht mit dem eigenen — beide müssen abweichen. Ein Fall, zwei Assertions;
  bisher steht diese Zusage nur in Docstrings.
- **Genau eine INFO-Zeile** je Aufruf mit den vier Zahlen (entfernt / freigegebene Bytes /
  Fehlschläge / wegen Schonfrist behalten), `caplog` auf INFO. Die Zusammenfassung enthält
  **keinen** Pfad; Pfade stehen ausschließlich in der WARNING-Zeile des Einzelfehlers.
- **Fehlendes Cache-Verzeichnis:** kein Fehler, Ergebnis mit vier Nullen, INFO-Zeile trotzdem da.

### 4. Anbindung in `run_project_scan` (`test_worker_scan_project.py`)

Wiederverwendet unverändert: `db_session`, `tmp_path`, `_make_project`, `_entry`, `_jpeg_bytes`,
`FakeOpenCloudClient` und seine Fehlervarianten. Ein neuer lokaler Helfer genügt —
`_write_orphan(cache_dir, key_source, age_seconds)`, der eine Datei über `thumbnail_path()`
schreibt und per `os.utime` altert. So sieht der Kern eines Anbindungstests aus:

- **Erfolg räumt auf:** eine gealterte verwaiste Datei plus ein gültiges Foto eines *anderen*
  Projekts mit ebenfalls gealterten Dateien; Scan von Projekt A über den Fake-Client → `SUCCESS`,
  verwaiste Datei weg, fremde gültige Dateien da, frisch erzeugte Dateien des gescannten Fotos da.
  Ein Fall, der Kriterium 1, 3 und 5 zugleich trägt.
- **Foto beim Re-Scan entfernt (Kriterium 2):** vorhandene `Photo`-Zeile mit gealterten
  Cache-Dateien, Client liefert keine Einträge → `photos_removed == 1` **und** die Dateien sind weg.
  Der Beleg dafür, dass der Schnappschuss nach dem Lösch-Commit gezogen wird.
- **Neue Fassung (Kriterium 2):** bestehende Zeile `old-etag` mit gealterten Dateien, Client meldet
  `new-etag` → alte Dateien weg, neu erzeugte da. Erweiterung des vorhandenen
  `test_scan_updates_photo_on_etag_change`, nicht dessen Ersatz.
- **Nebenläufigkeitsfenster (Kriterium 4):** eine **frisch** geschriebene verwaiste Datei — genau
  das, was ein paralleler Scan zwischen Dateischreiben und Commit hinterlässt — überlebt den Scan.
  Der wichtigste Einzelfall der Story; ohne ihn ist die Story eine Datenverlustquelle.
- **Fehlschlag räumt nicht (Kriterium 8):** `FakeOpenCloudClient(fail_with=OpenCloudError(...))`
  → `FAILED`, gealterte verwaiste Datei **noch da**.
- **Abbruch räumt nicht (Kriterium 8):** `WalkFailsWithCancelledErrorClient`,
  `pytest.raises(asyncio.CancelledError)` → Lauf `FAILED`, gealterte verwaiste Datei noch da. Die
  `CancelledError` propagiert unverändert; `project_id` wie im Bestandsfall **vor** dem Aufruf lesen.
- **Ein Dateifehler entwertet den Scan nicht (Kriterium 7):** `monkeypatch` auf `Path.unlink` für
  genau eine von zwei verwaisten Dateien → Lauf bleibt `SUCCESS`, die zweite ist weg, der Pfad steht
  im Log.
- **Ein Fehler der Bereinigung lässt den Lauf `SUCCESS` und die Session benutzbar (Auflage 1):**
  `monkeypatch.setattr(worker, "cleanup_orphaned_cache", …)`, das wirft (setzt voraus, dass `worker`
  den Namen auf Modulebene importiert). Assertions **ohne weiteres `await`**: `scan_run.status ==
  SUCCESS` und `scan_run.id is not None`, dazu eine WARNING-Zeile und eine anschließend erfolgreiche
  Abfrage über dieselbe Session. Ohne `refresh()` schlägt dieser Test mit `MissingGreenlet` fehl —
  das ist sein Zweck.
- **Kriterium 9 als Invariante:** zwei Projekte mit Fotos, dazu gealterter Rest; nach dem Scan ist
  die Summe aller Dateigrößen im Verzeichnis gleich der Summe von `measure_cache_usage` über beide
  Projekte. Die Verbindung zwischen Statistikseite und Verzeichnis gibt es im Produktivcode bewusst
  nicht — sie ist genau deshalb ein Test.

### 5. Bestandsschutz — der eigentliche Regressionsnachweis der `return`-Verschiebung

Mit der Anbindung läuft **jeder** erfolgreiche Scan der bestehenden Suite durch die Bereinigung,
mit `tmp_path` als Cache-Verzeichnis. Die rund 30 vorhandenen `run_project_scan`-Fälle in
`test_worker_scan_project.py` sind damit gleichzeitig der Nachweis, dass die `return`-Verschiebung
aus dem `try` heraus den Erfolgspfad unverändert lässt **und** dass die Bereinigung frisch erzeugte
Cache-Dateien nicht anfasst (alle darin geschriebenen Dateien sind jünger als die Schonfrist).
Verbindlich: **jede Anpassung, die an einem dieser Bestandsfälle nötig würde, ist ein Befund und
keine Nachpflege** — sie wäre der Beleg, dass die Bereinigung sichtbares Verhalten geändert hat.
`test_worker_fail_run.py`, `test_demo_state.py`, `test_project_deletion.py` und
`test_api_projects.py` bleiben unberührt; der Projekt-Löschpfad bekommt keine Zeile.

### Was bewusst nicht getestet wird

- **Kein Frontend-, kein E2E-Anteil — und das ist keine Lücke, sondern die Bauform der Story.**
  Es gibt keine Datei unter `frontend/`, keine Route, kein Antwortfeld, keinen Zustand, den eine
  Ansicht lesen könnte; das einzige Ergebnis nach außen ist eine Logzeile auf dem Server. Ein
  `vitest`- oder Playwright-Fall hätte hier keinen Gegenstand. Der einzige sichtbare Effekt —
  ein korrekter Speicherbedarf auf der Statistikseite — entsteht ohne jede Änderung an
  `api/stats.py` und ist oben als Backend-Invariante geprüft, wo er entsteht.
- **Kriterium 6 ist ein Review-, kein Testkriterium.** Die Abwesenheit eines Bedienelements, eines
  Bestätigungsschritts und einer Einstellung lässt sich nicht assertieren; sie wird im
  `review-requirements`-Durchlauf am Diff festgestellt (keine Datei unter `frontend/`, keine neue
  Route, kein neuer `Settings`-Eintrag, `.env.example` unverändert).
- **Zwei tatsächlich gleichzeitig laufende Scans.** Die Testdatenbank ist
  `sqlite+aiosqlite:///:memory:` ohne `StaticPool`; eine zweite Verbindung wäre eine andere
  Datenbank. Geprüft wird die Mechanik, die Kriterium 4 trägt (Jugend schützt, Verzeichnis vor
  Datenbank), nicht das Kriterium selbst. Steht unter „Bekannte Lücken" im Testkonzept.
- **Ob eine Stunde Schonfrist über der längsten realen Blockdauer liegt.** Plausibilisiert gegen
  `scan_download_concurrency` (Vorgabe 4), nicht gemessen. Ersatzverfahren: Blick auf `kept_recent`
  in der INFO-Zeile nach dem ersten größeren Parallellauf.
- **Das Mikrosekundenfenster zwischen letzter Zeitprüfung und `unlink`** — per Konstruktion nicht
  testbar (ADR 0075, „Konsequenzen"), Auswirkung im Trefferfall ist eine fehlende Vorschaudatei.
- **Verhalten unter echten Dateisystemrechten.** Fehlschläge werden über `monkeypatch` erzeugt, wie
  überall im Projekt: `chmod`-basierte Tests sind als root im Container wirkungslos.

### Coverage-Gate

`--cov-fail-under=80` ist hier kein Maßstab: Das Backend liegt bei ~97 %, die rund 120 neuen Zeilen
in zwei Modulen könnten vollständig ungetestet bleiben, ohne das Gate zu röten. Pflichtabdeckung
sind die oben namentlich benannten Fälle — insbesondere der Nebenläufigkeitsfall, der
`refresh()`-Fall und die Symlink-/Unterverzeichnis-Fälle.

## Security

Sicherheitsrelevant, kein Blocker. Kein neues Secret, keine neue Abhängigkeit, kein neuer
Endpunkt, keine Datenmodell-Änderung, keine Migration, keine Oberfläche, keine Änderung an Auth,
an der Sichtbarkeit zwischen den beiden Nutzern oder am Empfängerkreis (nichts verlässt den Host).
**Neu ist die Richtung des Vertrauens:** Bis hierher galt für jede Cache-Operation des Projekts
derselbe Satz — der Pfad wird aus `(photo_id, etag)` **berechnet**, nie gesucht (ADR 0062 Punkt 5).
Diese Story kehrt das an genau einer Stelle um: Ein **vorgefundener Verzeichniseintrag** entscheidet
über ein `unlink` auf den sensibelsten lokal vorhandenen Daten. Der Angreiferbezug ist dabei
schwach — `photo_cache` ist ein Docker-Volume, das nur in `backend` und `worker` gemountet ist; wer
dort schreibt, hat den Host bereits. Die Absicherung richtet sich deshalb gegen **Fehlkonfiguration
und den eigenen künftigen Änderungsfehler**, dessen Schadensbild ein stiller Totalverlust des
Bild-Caches wäre. Vollständige Herleitung in
[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt
„Verzeichnisgestützte Bereinigung verwaister Bildkopien" (M1–M7).

**1. Das Muster wird per `re.fullmatch` geprüft, nie per `.match`/`.search`. Muss.**
Nachgestellt und bestätigt (CPython, hier 3.14; die `$`-Semantik ist versionsübergreifend
dokumentiert): `re.compile(r"^[0-9a-f]{64}_(?:thumbnail|display)\.jpg$").match("<64 hex>_display.jpg\n")`
**trifft** und liefert den Schlüssel aus Gruppe 1 — `$` passt auch unmittelbar vor einem
abschließenden Zeilenumbruch, und ein Dateiname mit `\n` ist unter Linux anlegbar (ebenfalls
nachgestellt). `fullmatch` weist denselben Namen ab. Der Unterschied trägt die ganze Zusage aus ADR
0075 Punkt 2 („das Muster ist die exakte Signatur der eigenen Schreiboperation"): ein Name mit
angehängtem Zeilenumbruch ist **nicht**, was `thumbnail_path`/`display_path` schreiben. Kein
`re.IGNORECASE` — `hashlib.hexdigest()` liefert Kleinbuchstaben. Eigener Test mit einem
`…_display.jpg\n`-Namen (per `tmp_path` anlegbar), der nicht gelöscht werden darf.

**Nachtrag aus der Umsetzung (Review-Fund, 2026-09-10): das Endanker im Muster ist `\Z`, nicht
`$`.** Die Anker bleiben im Muster stehen — anders als in einer Zwischenfassung der Umsetzung
erwogen —, aber `$` wird durch `\Z` (absolutes Ende der Zeichenkette) ersetzt. Damit sind sie ein
zweites, unabhängiges Netz **unter** der `fullmatch`-Regel statt einer Verdopplung mit eigener
Schwäche: `fullmatch` braucht sie nicht, aber ein künftiges versehentliches `.match`/`.search`
bliebe dadurch sowohl auffällig **als auch harmlos**. Ohne Anker träfe ein `.match` jeden Namen,
der mit der Signatur nur **beginnt** (`<64 hex>_thumbnail.jpg.bak`), und löschte ihn; mit `^…$`
träfe es weiterhin den oben beschriebenen Zeilenumbruch-Fall. Eigene Testfälle prüfen deshalb
ausdrücklich `.match` gegen beide Namen — den Aufruf, den der Produktivcode nie macht.

**2. Die Wiederholungsprüfung unmittelbar vor dem `unlink` liest `lstat`, nicht `stat`. Muss.**
Nachgestellt: `Path.stat()` folgt einem Symlink und liefert `st_mode`, `st_size` und `st_mtime` des
**Ziels**. Ein zwischen Aufnahme und Löschung untergeschobener Symlink autorisierte damit seine
Entfernung über die Änderungszeit einer fremden Datei und verfälschte `freed_bytes` um deren Größe.
Mit `Path.lstat()` **plus erneutem `S_ISREG`** fällt er heraus; seine eigene Änderungszeit ist der
Moment seiner Erstellung und greift ohnehin die Schonfrist. Die Aufnahme benutzt dieselbe Sicht:
`os.scandir` mit `entry.is_file(follow_symlinks=False)` und `entry.stat(follow_symlinks=False)`.
Der eigentliche Datenverlust-Pfad ist unabhängig davon geschlossen — `Path.unlink` folgt keinem
Symlink, entfernt also den Link und nie sein Ziel (nachgestellt), und ein Hardlink teilt nur den
Inode, sodass an einer zweiten Stelle nichts verschwindet. TOCTOU bleibt damit auf das in ADR 0075
benannte Mikrosekunden-Fenster begrenzt, und dieses ist für eine **gültige** Datei gar nicht
erreichbar (ihr Schlüssel liegt in der Gültigkeitsmenge).

**3. Nicht rekursiv, und ausschließlich `unlink`. Muss.**
Kein `glob`, kein `rmtree`, kein `rmdir`, kein Abstieg in Unterverzeichnisse. Das schließt
Symlink-Schleifen, ein Ausbrechen aus dem Cache-Verzeichnis und das Entfernen eines Verzeichnisses
strukturell aus, nicht durch Prüfung. Pfad-Traversal ist doppelt versperrt: ein
`os.scandir`-`name` enthält nie einen Pfadtrenner, und Punkt 1 lässt ohnehin nur 64 Hexziffern plus
feste Endung durch. Der Löschpfad wird als `cache_dir / name` konstruiert, nie aus einer anderen
Quelle.

**4. Die Gültigkeitsmenge bleibt ungefiltert, und die Reihenfolge ist Teil der Absicherung. Muss.**
`select(Photo.id, Photo.etag)` **ohne** `where` — kein Projekt-, Nutzer-, Status- oder
Sichtbarkeitsfilter. Jeder künftige Filter an dieser Abfrage (Soft-Delete-Flag, „nur aktive
Projekte", eine Nutzergrenze) macht aus einer Bereinigung eine Löschung fremder, gültiger
Bilddaten. Der Test, der das festnagelt, ist der Zwei-Projekte-Fall aus Umsetzungsschritt 5:
Dateien des **nicht** gescannten Projekts bleiben unangetastet. Ebenso verbindlich: erst Verzeichnis
aufnehmen, dann Schnappschuss ziehen, und der Schnappschuss nach einem Commit-Rand
(`run_project_scan` committet unmittelbar davor) — umgekehrt wäre jede im Zwischenfenster sichtbar
gewordene Datei ungeschützt.

**5. Fail-closed bei leerer Gültigkeitsmenge. Muss — Ergänzung gegenüber ADR 0075 Punkt 2.**
Sind Einträge vorhanden, die Menge der gültigen Schlüssel aber leer, wird **nichts** gelöscht und
eine `WARNING` geschrieben (`CacheSweepResult` bleibt bei null gelöschten Dateien). Eine leere Menge
ist der einzige Zustand, in dem der Durchgang den kompletten Bild-Cache räumte, und zugleich das
Symptom praktisch jedes denkbaren Fehlers an Punkt 4 (falsche Datenbank, versehentlicher Filter,
unbrauchbare Session). Der Preis ist der Randfall „Installation ohne ein einziges Foto behält ihre
Reste" — vernachlässigbar gegen einen stillen Totalverlust und ausdrücklich **kein** Widerspruch zu
Akzeptanzkriterium 1/5, deren Fälle immer mindestens ein vorhandenes Foto voraussetzen. Eigener
Test.

**6. Das Log sieht nur Gemustertes und Zahlen. Muss.**
Ein Eintragsname, der Punkt 1 **nicht** bestanden hat, wird nie geloggt — weder als Name noch als
Pfad, weder auf DEBUG noch im Fehlerfall. Er ist die einzige Log-Injection-Fläche des Features
(Zeilenumbrüche und Steuerzeichen sind in Dateinamen erlaubt); gezählt wird er, benannt nicht.
Absolute Cache-Pfade **gemusterter** Dateien gehören dagegen ins Log (Diagnose des `OSError`-Falls,
dasselbe Muster wie `measure_cache_usage`/`delete_cached_variants`) und nie in eine HTTP-Antwort,
ein Antwortfeld oder eine `HTTPException`. Es tritt dabei nichts Schützenswertes aus: Der Dateiname
ist ein SHA-256 über `photo_id:etag` und trägt weder Motiv, Original-Dateinamen, Ordnerstruktur noch
Zeit- oder Ortsbezug; der absolute Pfad verrät interne Deployment-Struktur und bleibt genau deshalb
log-only. Die Abschluss-INFO-Zeile besteht aus reinen Zahlen (entfernt / freigegebene Bytes /
Fehlschläge / wegen Schonfrist behalten).

**7. Ein `photo_cache`-Volume gehört zu genau einer Datenbank. Muss (Betriebsauflage).**
Die Bereinigung koppelt Verzeichnis und Datenbankstand fest aneinander: Zwei Stacks, die sich
`photo_cache` teilen, aber nicht die Datenbank, löschen sich ab jetzt gegenseitig den Cache — was
bisher nur Verschwendung war. Muss-Kriterium M5 der Spec
[`0174`](./0174-browser-zugang-fuer-claude.md) (eigener Compose-Projektname `photosort-e2e` in
`docker-compose.e2e.yml`) bekommt damit einen zweiten, härteren Grund und darf nicht als reine
Hygiene zurückgebaut werden. Dass der Prüfstack zusätzlich keinen `worker` enthält und keinen Scan
auslöst, ist Umstand, nicht Zusicherung.

**8. Verfügbarkeit: die Kopien sind ableitbar, aber sie heilen nicht von selbst.**
Die Einstufung „Quelle der Wahrheit ist OpenCloud, kein Originalbild betroffen" trägt — mit einer
Präzisierung gegenüber ADR 0075, die dort als „es fehlt **eine** Vorschaudatei" formuliert ist. Am
Code nachgeprüft: Die `display`-Variante ist keine reine Anzeigedatei, sondern die Eingabe der
lokalen Kriterien-Bewertung (`worker.py::_compute_photo_metrics`, `if path.is_file()`), der
Landmark-Erkennung und der Remote-Kategorie-Klassifizierung; alle drei überspringen ein Foto ohne
lesbare Cache-Datei **stillschweigend**. Und ein Scan erzeugt Varianten nur für neue oder
`etag`-geänderte Fotos (`_classify_scan_entries`, `SkipReason.UNCHANGED_ETAG`) — die Datei kehrt
also erst zurück, wenn das Foto auf OpenCloud eine neue Fassung bekommt. Getragen wird das trotzdem:
Eine gültige Datei kann nur durch einen Fehler an Punkt 1–5 getroffen werden, nicht durch das Rennen;
das verbleibende Fenster erreicht ausschließlich eine Datei, die im Schnappschuss verwaist war und
in genau diesem Augenblick neu geschrieben wurde. Der fehlende Selbstheilungspfad ist vorbestehend
und im Sicherheitskonzept unter „Bekannte Lücken" geführt, nicht Gegenstand dieser Story.

**Ausdrücklich nicht betroffen:** Datentrennung zwischen den beiden Nutzern. Der Cache kennt keine
Nutzerdimension, gelesen werden ausschließlich `Photo.id` und `Photo.etag` — keine `Rating`-,
Nutzer-, EXIF- oder Ortsdaten —, und die projektübergreifende Gültigkeitsmenge ist die Bedingung
dafür, dass **keine** fremde gültige Datei gelöscht wird, nicht eine Aufweichung einer Grenze. Der
Nebeneffekt „ein Scan von Projekt A räumt Reste von Projekt B" vergrößert die Wirkung eines
gestohlenen JWT nicht: betroffen sind ausschließlich bereits unerreichbare Dateien, und derselbe
Token könnte mit `DELETE /projects/{id}` ungleich mehr vernichten.

## Entscheidungen

- **Zielkonflikt zwischen Akzeptanzkriterium 1 und 4, aufgelöst zugunsten von 4.** In ihrer
  wörtlichen Lesart sind beide nicht gleichzeitig erfüllbar: was ein paralleler Scan in dieser
  Sekunde schreibt, ist von außen nicht von einem Rest zu unterscheiden. Die Zusage lautet deshalb
  „kein **dauerhafter** Rest" statt „nach jedem Scan null Reste"; Kriterium 1 ist oben entsprechend
  formuliert. Der heute vorhandene Altbestand (Kriterium 5) ist davon nicht betroffen — er ist um
  Größenordnungen älter als die Schonfrist. Die Alternative wäre gewesen, Scans systemweit zu
  serialisieren; das setzt genau das voraus, was Kriterium 4 schützen will.
- **Schonfrist als Konstante, nicht als Umgebungsvariable** (ADR 0075 Punkt 4): ein
  Korrektheitsabstand, kein Betriebsparameter. Als Einstellung lüde der Wert dazu ein, ihn auf 0
  zu setzen und damit Kriterium 4 still aufzugeben.
- **ADR 0075 angelegt**, weil der Ansatz ADR 0062 Punkt 5 („nie über ein Verzeichnismuster")
  in genau einem Teilsatz ablöst. Ohne Verzeichnisdurchgang ist Kriterium 5 strukturell
  unerfüllbar: die Schlüssel des Altbestands sind nirgends mehr gespeichert.
- **Nachtrag `test-engineer` (Auflage 1): nach dem `rollback()` im Bereinigungs-Handler folgt
  `await session.refresh(scan_run)`.** Nachgemessen: ein `rollback()` nach einer Abfrage in
  derselben Transaktion expired alle Objekte, der nächste Attributzugriff scheitert mit
  `MissingGreenlet` — `scan_project` liest unmittelbar danach `scan_run.id`. Ohne den `refresh()`
  stürzt der Job nach einem erfolgreichen Scan ab. Diese Festlegung ergänzt Entwurfsentscheidung 6.
- **Nachtrag `test-engineer` (Auflage 2): `FileNotFoundError` beim `lstat` ist kein Fehlschlag.**
  Weil die Änderungszeit unmittelbar vor dem `unlink` erneut gelesen wird, greift das
  `missing_ok=True` des `unlink` für die harmlose Wettlaufsituation nie; sie trifft den `lstat`.
  Still überspringen statt als Fehler zählen und loggen.
- **Nachtrag `security-engineer` (drei Korrekturen am Entwurf, nicht bloß Bestätigungen):**
  `re.fullmatch` statt `.match` (empirisch bestätigt: `$` passt auch vor einem abschließenden
  Zeilenumbruch, und `<64 hex>_display.jpg\n` ist unter Linux anlegbar — das wäre zugleich die
  einzige Log-Injection-Fläche); `Path.lstat()` plus erneutes `S_ISREG` statt `Path.stat()` vor
  dem `unlink`, weil `stat()` einem untergeschobenen Symlink folgt und ihn über die Änderungszeit
  einer fremden Datei autorisierte; fail-closed bei leerer Gültigkeitsmenge, dem einzigen Zustand,
  in dem der Durchgang den kompletten Bild-Cache räumte.
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien 1, 4, 7 und 9 auf Testbarkeit
  geschärft, Testkonzept um eine eigene Sektion und drei benannte Lücken ergänzt.
- **`security-engineer` konsultiert (Schritt 3):** Sicherheitskonzept um den Abschnitt
  „Verzeichnisgestützte Bereinigung verwaister Bildkopien" (M1–M7) ergänzt; das bisherige
  Restrisiko aus Spec 0044/ADR 0062 Punkt 5 ist dort durchgestrichen und durch drei neue Einträge
  ersetzt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): kein konkret benennbarer Bezug zu einer
  sichtbaren Oberfläche — keine Frontend-Datei betroffen, keine neuen Daten, kein geänderter
  Anzeigewert; Akzeptanzkriterium 6 schließt jede Oberflächenänderung ausdrücklich aus.

## Offene Fragen

Keine.

## Out of Scope

- Ein Bedienelement, eine Einstellung oder eine Anzeige für die Bereinigung (durch
  Akzeptanzkriterium 6 ausgeschlossen).
- Eine Cache-Buchführung in der Datenbank (in ADR 0075 als Alternative verworfen).
- Änderungen am Projekt-Löschpfad (`api/projects.py::delete_project`,
  `project_deletion.py`, `demo_state.py`): er rechnet seine Pfade unverändert aus
  `(photo_id, etag)` und bekommt weiterhin kein `glob` und kein `rmtree` (ADR 0062 Punkte 1–4
  bleiben in Kraft).
- Eine zeitgesteuerte Bereinigung unabhängig vom Scan.
