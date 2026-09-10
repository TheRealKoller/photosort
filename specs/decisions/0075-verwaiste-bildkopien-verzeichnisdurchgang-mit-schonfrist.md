# 0075 - Verwaiste Bildkopien: gemusterter Verzeichnisdurchgang mit Schonfrist, nach jedem erfolgreichen Scan

**Status:** Accepted
**Datum:** 2026-09-10
**Bezug:** [GitHub-Issue #349](https://github.com/TheRealKoller/photosort/issues/349), [`features/0349-verwaiste-bildkopien-aufraeumen.md`](../features/0349-verwaiste-bildkopien-aufraeumen.md), `architect`-Konsultation für Story #349 am 2026-09-10

**Löst teilweise ab:** [`decisions/0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md), **Punkt 5** — und zwar ausschließlich dessen absoluten Teil („nie über ein Verzeichnismuster"). Der Löschpfad des Projekts (`api/projects.py::delete_project`, `demo_state.py::purge_demo_state`) rechnet seine Cache-Pfade unverändert aus `(photo_id, etag)` aus und bekommt **kein** `glob` und **kein** `rmtree`; die Punkte 1–4 von ADR 0062 bleiben vollständig in Kraft. Neu ist genau **eine** zusätzliche Stelle, die das Cache-Verzeichnis liest — die Bereinigung nach dem Scan —, weil sie einen Rest aufräumen muss, dessen Schlüssel sich per Definition **nicht** mehr aus der Datenbank berechnen lässt. Abschnitt 2 dieser ADR nennt die Absicherungen, die an die Stelle der Schutzwirkung treten, die das Verbot in ADR 0062 hatte.

## Kontext

Der lokale Bild-Cache ist flach und projektübergreifend: eine Datei heißt
`<sha256(photo_id:etag)>_thumbnail.jpg` bzw. `_display.jpg` (`thumbnails.py::cache_key`). Der
`etag` im Schlüssel ist die Fassungs-Invalidierung — bekommt ein Foto auf OpenCloud eine neue
Fassung, ändert sich der Schlüssel, und die alten Dateien sind ab diesem Moment über keinen
Codepfad des Systems mehr erreichbar: der Bild-Endpunkt (`api/photos.py`) rechnet den Pfad aus
dem **aktuellen** `etag`, die Statistikseite misst nur die Pfade der **aktuellen** Fassungen
(`measure_cache_usage`), und `delete_cached_variants` löscht ausschließlich Pfade, die es aus
vorhandenen Zeilen berechnet hat. Genau das ist der Defekt aus Issue #349: unerreichbare Dateien
sind zugleich unlöschbare Dateien, weil dieselbe Rechnung, die sie unerreichbar macht, sie auch
aus jeder Löschmenge herausfallen lässt (in `delete_cached_variants` bereits als benannte Grenze
und in Spec 0044 als „Restrisiko 2" dokumentiert).

Drei Entstehungswege führen dorthin: neue Fassung auf OpenCloud (alter Schlüssel bleibt liegen),
beim Re-Scan entferntes Foto (`run_project_scan` löscht die Zeile, nie die Dateien), und ein
Projekt-Löschvorgang, dessen best-effort Dateiaufräumung damals scheiterte oder abbrach. Der Rest
wächst dadurch einseitig — er kann nie kleiner werden — und ist gleichzeitig unsichtbar: er taucht
in keiner Projektstatistik auf, weil die Statistik gezielt über vorhandene Fotos misst.

Eine Bereinigung, die nur aus der Datenbank ableitet, kann diesen Rest strukturell nicht finden.
Wer die Dateien finden will, muss das Verzeichnis lesen. Genau das verbietet ADR 0062 Punkt 5 —
mit einer Begründung, die weiterhin richtig ist: die Dateinamen tragen keine Projektzuordnung, das
Volume ist geteilt, ein Muster trifft potenziell Fremdes.

Erschwerend kommt die Nebenläufigkeit hinzu, und sie ist der eigentlich harte Teil. Scans mehrerer
Projekte können gleichzeitig laufen. Ein Scan schreibt eine Cache-Datei **vor** dem Commit der
zugehörigen Foto-Zeile (`_process_scan_block`: Zeile anlegen/`flush()` → Download+Thumbnail →
Commit erst nach dem ganzen Block, ADR 0020 Fallstrick 2). Zwischen „Datei existiert" und „Zeile ist
für andere Transaktionen sichtbar" liegt also ein Fenster in der Größenordnung einer Blockdauer.
Eine Bereinigung, die in diesem Fenster den Datenbankstand als Wahrheit nimmt, hält genau die
Dateien für verwaist, die ein anderer Scan gerade erzeugt — und löscht das Ergebnis fremder Arbeit.

## Entscheidung

**1. Ausgelöst wird nach jedem erfolgreich abgeschlossenen Scan, im selben Worker-Job.**
Kein eigener arq-Job, kein Cron-Eintrag, kein Bedienelement, keine Einstellung. Der Aufruf sitzt in
`run_project_scan` **hinter** dem `try/except`, das den Lauf auf `FAILED` setzt, erreicht also den
Abbruch- und den Fehlerpfad strukturell nicht (Akzeptanzkriterium „bei Abbruch/Fehlschlag keine
Bereinigung"). Ein Scan ist der richtige Auslöser, weil er der einzige Vorgang ist, der Schlüssel
ungültig macht — und weil er dieselbe Vorbedingung mitbringt, die die Bereinigung braucht: eine
gerade committete, vollständige Sicht auf die Fotos des Projekts.

**2. Der Durchgang liest das Verzeichnis, aber nur, was er selbst erzeugt haben kann.**
Gelöscht wird ausschließlich, was **alle** folgenden Bedingungen erfüllt:

- direkter Eintrag in `settings.photo_cache_dir`, **nicht rekursiv**;
- **reguläre Datei** (kein Verzeichnis, kein Symlink, kein Gerät — `os.scandir` ohne Symlink-Folgen);
- Name trifft exakt `^[0-9a-f]{64}_(thumbnail|display)\.jpg\Z` — dieselbe Form, die `cache_key` +
  `thumbnail_path`/`display_path` erzeugen;
- der 64-stellige Schlüssel liegt **nicht** in der Gültigkeitsmenge aus Punkt 3;
- die Änderungszeit liegt vor der Schonfrist-Grenze aus Punkt 4.

Alles andere bleibt unangetastet, ausdrücklich auch Unbekanntes. Das ist die Absicherung, die an die
Stelle des Verbots aus ADR 0062 Punkt 5 tritt: das Muster ist nicht „alles im Verzeichnis", sondern
die exakte Signatur der eigenen Schreiboperation. Das Muster gehört deshalb **neben** `cache_key`
in `thumbnails.py` — wer das Namensschema ändert, muss beides in derselben Datei anfassen.

**3. Gültig ist ein Schlüssel, wenn irgendein vorhandenes Foto ihn erzeugt — projektübergreifend.**
Die Menge ist `{cache_key(id, etag) für alle Zeilen aus photos}`, über **alle** Projekte, nicht nur
über das gerade gescannte (Akzeptanzkriterium „auch die von Fotos aus anderen Projekten"). Der Cache
ist flach und projektübergreifend; eine projektbezogene Menge wäre für ihn die falsche Frage.

**Die Reihenfolge ist Teil der Entscheidung, nicht Geschmackssache: zuerst das Verzeichnis lesen,
danach den Datenbank-Schnappschuss ziehen.** Nur so ist jede Zeile, die zwischen beiden Zeitpunkten
committet, im Schnappschuss enthalten und schützt ihre Datei. Umgekehrt wäre jede in diesem Fenster
sichtbar gewordene Datei ungeschützt. Der Schnappschuss wird als Spalten-Tupel (`select(Photo.id,
Photo.etag)`) gelesen, nicht als ORM-Objekte, und nach einem Commit-Rand — er sieht damit den
aktuellen Stand fremder Transaktionen, nicht den einer älteren Sicht.

**4. Eine Schonfrist von einer Stunde deckt das Fenster zwischen Dateischreiben und Commit ab.**
Gelöscht wird nur, was **älter** ist als `time.time() - 3600`. Das ist die strukturelle Antwort auf
das Nebenläufigkeitskriterium: eine Datei, deren Zeile noch nicht committet ist, wurde
zwangsläufig eben erst geschrieben — sie ist jung, und Jugend schützt. Ein Scan committet spätestens
je Block (Blockgröße `settings.scan_download_concurrency`, Vorgabe 4); eine Stunde liegt um Größen-
ordnungen über jeder realistischen Blockdauer, selbst bei großen Dateien über eine langsame
Verbindung. Die Änderungszeit wird **unmittelbar vor dem `unlink`** erneut gelesen und erneut
geprüft — ein zwischenzeitliches Neuschreiben derselben Datei (Foto kehrt auf eine frühere Fassung
zurück) macht sie damit sofort wieder unantastbar.

Der Wert ist eine **Konstante im Code**, keine Umgebungsvariable. Er ist kein Betriebsparameter,
sondern ein Korrektheitsabstand; als Einstellung lüde er dazu ein, ihn auf 0 zu setzen und damit
still die Zusage aus Akzeptanzkriterium 4 aufzugeben. Die Grenze selbst wird als Parameter in die
reine Funktion hineingereicht, damit Tests sie ohne Warten setzen können.

Beide Uhren stammen aus derselben Quelle: `st_mtime` der Datei und `time.time()` des Workers sind
beide der Host-Kernel. Es wird **nicht** gegen einen Datenbank-Zeitstempel verglichen.

**5. Best-effort je Datei; die Bereinigung kann den Scan nicht mehr entwerten.**
Ein `OSError` an einer einzelnen Datei wird mit Pfad **geloggt** und übersprungen, die übrigen Reste
verschwinden trotzdem — dasselbe Muster wie `delete_cached_variants`. Darüber hinaus fängt der
Aufrufer alles ab, was nicht `BaseException` ist, und lässt den Lauf `SUCCESS`: der Scan hat seine
Arbeit getan, bevor die Bereinigung begann. `asyncio.CancelledError` propagiert unverändert (arqs
Buchhaltung), setzt den bereits erfolgreichen Lauf aber nicht nachträglich auf `FAILED`. Absolute
Cache-Pfade gehören ins Log, nie in eine HTTP-Antwort.

**6. Kein Datenmodell, keine Abhängigkeit, keine Kennzahl.**
Keine Tabelle, keine Spalte, keine Migration, kein Antwortfeld, keine Oberfläche, kein neues Paket
(`os.scandir`, `re`, `time` — Standardbibliothek). Das Ergebnis ist **eine** INFO-Logzeile
(entfernte Dateien, freigegebene Bytes, Fehlschläge). Die Statistikseite braucht keine Änderung: sie
misst schon heute genau die Menge, die nach der Bereinigung noch existiert.

## Begründung

**Warum nicht gezielt statt suchend?** Die Bereinigung ließe sich auf die Schlüssel beschränken, die
dieser Scan selbst ungültig gemacht hat (alter `etag` vor der Aktualisierung, Schlüssel entfernter
Fotos) — vollständig aus der Datenbank ableitbar, kein Verzeichniszugriff, ADR 0062 Punkt 5 bliebe
unangetastet. Das scheitert an einem ausdrücklichen Akzeptanzkriterium: *der bereits heute
vorhandene Rest* soll ohne gesonderten Anstoß verschwinden. Dessen Schlüssel sind nirgends mehr
gespeichert. Ein Weg, der ihn nicht findet, löst den gemeldeten Defekt nur für die Zukunft und lässt
genau das liegen, was das Issue als Anlass nennt. Zusätzlich bliebe jeder Rest aus einem
abgestürzten oder zurückgerollten Block dauerhaft liegen.

**Warum keine Buchführung über die Cache-Dateien in der Datenbank?** Eine Tabelle „welche Datei
gehört zu welchem Foto" (oder eine Reservierung vor dem Schreiben) machte den Verzeichnisdurchgang
entbehrlich und löste die Nebenläufigkeit sauber über die Transaktion. Sie führt aber eine zweite
Wahrheit über einen Sachverhalt ein, der bereits vollständig aus `(photo_id, etag)` **berechenbar**
ist — mit allen Folgekosten: Migration, Pflege in jedem Schreibpfad, und ein neuer Fehlermodus
(Eintrag ohne Datei, Datei ohne Eintrag), der wieder einen Abgleich mit dem Verzeichnis verlangte.
Das ist mehr Datenmodell für weniger Sicherheit.

**Warum keine Serialisierung der Scans?** Ein instanzweiter Vorrang (Advisory Lock), der Scan und
Bereinigung gegeneinander ausschließt, erfüllte das Nebenläufigkeitskriterium trivial. Er nimmt aber
eine Fähigkeit weg, die das Akzeptanzkriterium selbstverständlich voraussetzt (zwei Projekte
gleichzeitig scannen), und tauscht einen kleinen, lokal begründbaren Zeitabstand gegen eine
systemweite Einschränkung. Ein Aufräumvorgang darf den Betrieb nicht umbauen.

**Warum keine Grenze aus den laufenden Scans statt einer festen Schonfrist?** Naheliegend wäre
`min(started_at)` aller `ScanRun`-Zeilen im Status `RUNNING` als Grenze — exakt statt pauschal. Das
vergleicht jedoch einen **Datenbank**-Zeitstempel mit einer **Dateisystem**-Änderungszeit: zwei
Uhren, deren Gleichlauf niemand zusichert, in einem Vergleich, dessen Fehlerfall stilles Löschen
fremder Arbeit ist. Zudem friert eine hängengebliebene `RUNNING`-Zeile die Bereinigung ein, bis der
Watchdog sie einsammelt. Die feste Schonfrist braucht nur eine Uhr und hat keinen Zustand.

**Warum kein Quarantäne-Verzeichnis** (erst verschieben, beim nächsten Durchgang löschen)? Es sähe
vorsichtiger aus, ist es aber nicht: eine verschobene Datei ist für die Anwendung genauso weg wie
eine gelöschte, solange es keinen Rückweg gibt — und ein Rückweg existierte nicht. Es bliebe ein
zweites Verzeichnis, das seinerseits aufgeräumt werden will.

## Konsequenzen

- Ein Rest, der **jünger** als die Schonfrist ist, überlebt bis zum nächsten erfolgreichen Scan. Die
  Zusage lautet damit „kein dauerhafter Rest", nicht „nach jedem Scan null Reste". Das ist die
  bewusst gewählte Seite des Zielkonflikts zwischen „vollständig aufräumen" und „einem parallelen
  Scan nichts wegnehmen"; die Feature-Spec formuliert ihr Akzeptanzkriterium entsprechend.
- Jeder erfolgreiche Scan liest das Cache-Verzeichnis einmal vollständig und berechnet einen
  Hash je Foto. Bei der dokumentierten Größenannahme (mehrere tausend Fotos je Projekt) sind das
  einige zehntausend Verzeichniseinträge und ebenso viele SHA-256-Berechnungen über kurze
  Zeichenketten — Millisekunden, in einem Thread ausgeführt, an einer Stelle, die ohnehin Minuten
  dauert. Beides ist bewusst nicht inkrementell.
- Wer künftig eine Datei in `photo_cache_dir` ablegt, die dem Muster aus Punkt 2 entspricht, ohne
  dass ein Foto sie erzeugt hat, verliert sie. Das Verzeichnis ist ein Cache und kein Ablageort;
  das Muster ist eng genug, dass ein Zufallstreffer ausscheidet.
- Es bleibt ein Restrisiko in der Größenordnung von Mikrosekunden: zwischen der letzten
  Zeitprüfung und dem `unlink` gibt es kein atomares „lösche nur, falls unverändert". Trifft es,
  fehlt **eine** Vorschaudatei, bis das Foto eine neue Fassung bekommt — dieselbe Auswirkung, die
  ein fehlgeschlagener Download beim Scan heute schon hat (`_generate_thumbnails` ist best-effort
  und wiederholt nichts). Kein Originalbild ist betroffen; die Quelle der Wahrheit bleibt OpenCloud.
- ADR 0062 Punkt 5 gilt für den Löschpfad des Projekts unverändert weiter. Es gibt ab jetzt genau
  **eine** Stelle im Code, die das Cache-Verzeichnis aufzählt; eine zweite braucht wieder eine
  Entscheidung.
