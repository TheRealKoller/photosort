# 0485 - Parallel vergebene Nummern bleiben eindeutig

**Status:** Accepted
**Erstellt:** 2026-09-14
**Bezug:** GitHub-Issue [`#485`](https://github.com/TheRealKoller/photosort/issues/485)

Diese Spec überschreitet den Richtwert von ~200 Zeilen, weil sie zwei getrennte Nummernräume mit je
eigener Mechanik regelt und ihre Sicherheitsauflagen Ausfallrichtungen benennen, die still wirken.

## Ziel

Zwei Sessions, die gleichzeitig in eigenen Arbeitsständen an PhotoSort arbeiten, vergeben regelmäßig
dieselbe Nummer — für ein Entscheidungsdokument oder für eine Datenbankmigration. Zweimal innerhalb
von drei Tagen ist das passiert (2026-09-11 und 2026-09-14); zum Zeitpunkt der Schärfung laufen vier
Arbeitsstände parallel. Parallelarbeit ist damit der Normalfall, und die Kollision keine Ausnahme.

Zwei Dinge machen das teuer. Erstens fällt die Doppelvergabe spät auf: Die konkurrierende Nummer
liegt in einem Arbeitsstand, der noch nirgends veröffentlicht ist und für die Gegenseite deshalb
unsichtbar bleibt. Zweitens entscheidet die geltende Regel den häufigsten Fall überhaupt nicht: Sie
bestimmt das umzugspflichtige Dokument danach, welches von beiden später übernommen wurde, und wenn
noch keines übernommen ist, greift sie nicht. Am 2026-09-14 wichen beide Seiten unabhängig
voneinander nach derselben Regel aus — und landeten auf **derselben** Ersatznummer.

Bei den Datenbankmigrationen kommt ein Risiko hinzu, das über verlorene Zeit hinausgeht: Dort meldet
der Abgleich keinen Konflikt, weil zwei verschiedene Dateien entstehen. Sichtbar wird der Schaden
erst daran, dass die Migrationskette auseinanderfällt.

## User Story

Als Entwickler von PhotoSort möchte ich, dass eine Nummer, die ich in einem parallel laufenden
Arbeitsstand vergebe, verlässlich eindeutig bleibt, damit gleichzeitige Arbeit nicht in
Doppelvergaben, Abstimmungsrunden und nachträglichen Umbenennungen endet.

## Akzeptanzkriterien

- [ ] **AK 1 — beide Nummernräume.** Abgedeckt sind `vorschlag decisions`, `vorschlag architecture`
      und `migration <slug>`. `vorschlag features` liefert **nie** eine Zahl: Exit ≠ 0 und die
      Ausgabe enthält keine vierstellige Zahl — ein Aufrufer, der stdout greppt, darf auch
      versehentlich keine bekommen.
- [ ] **AK 2 — Frühwarnung während der Vergabe.** Im selben Lauf, in dem die Nummer ausgegeben wird,
      meldet der Zuteiler Kontention über Exit `10` und eine Befundzeile je kontrahierendem Branch,
      die Branchnamen und geführte Nummer nennt. Eine Nummer gilt auch dann als gesehen, wenn sie im
      Nachbar-Arbeitsbaum als angelegte, nicht `git add`-te Datei liegt.
- [ ] **AK 3 — nie dieselbe Ersatznummer, ohne Warten.** Drei je einzeln messbare Teile:
      (a) **Injektivität** — über *einer* Kontrahentenmenge mit festen Zählständen ist die Abbildung
      Branchname → Nummer injektiv, nachgewiesen als Eigenschaft über allen Permutationen der
      Eingabereihenfolge, nicht als Fallliste. (b) **Keine Abstimmung** — der Lauf setzt keine
      schreibende git-Operation ab, hält keine Sperrdatei, schläft und wiederholt nicht, und
      terminiert unter Zeitgrenze auch bei vier Nachbar-Arbeitsbäumen. (c) **Symmetriebedingung** —
      Teil (a) gilt nur, solange beide Seiten dieselbe Kontrahentenmenge sehen; im Fenster aus
      ADR 0108 Punkt 4 können beide dieselbe Zahl errechnen, und der nächste Lauf löst das zugunsten
      des rangniedrigeren Branches auf. Das ist zugesichertes Verhalten und wird als solches
      getestet, nicht als Verletzung von AK 3.
- [ ] **AK 4 — entscheidet ohne jeden Merge.** Bei null gemergten Beteiligten ist das Ergebnis
      definiert und seitenunabhängig: Rechnet man dieselbe Eingabe aus der Sicht jedes Kontrahenten,
      enthält die Ergebnismenge keine Dublette, und jede Seite erhält bei Wiederholung dasselbe.
- [ ] **AK 5 — genau eine gültige Regel.** ADR 0081 trägt den Teil-Vermerk für Punkt 2 und den
      ersten Satz von Punkt 3. Im Bestand weist keine Stelle mehr die abgelöste Regel als
      Handlungsanweisung aus — einschließlich des Meldungstextes des Wächtertests (siehe
      „Entscheidungen").
- [ ] **AK 6 — Migrationskennung.** Kennung = die ersten 12 Kleinbuchstaben-Hex aus
      `sha256(<Branch> + NUL + <Slug>)`. Gleiche Eingabe → gleiche Ausgabe; verschiedener Branch →
      verschiedene Kennung auch bei identischem Slug; die erzeugte `revision`-Zeile wird vom
      bestehenden Parser in `backend/tests/test_migration_chain.py` erkannt; bei verschobenem Head
      wird ohne Rückfrage nur die unterste eigene Migration umgehängt, und die aufgelöste Kette hat
      danach genau einen Kopf; `kette` macht die Reihenfolge lesbar, ohne eine Migrationsdatei zu
      öffnen.
- [ ] **AK 7 — Nachprüfung nach der Prüfrunde.** Die drei auslösenden Dinge (Nummern-Token,
      Dateiname, `down_revision`) stehen als geschlossene Aufzählung; jede Aufrufstelle unterscheidet
      die dokumentierten Exit-Codes einzeln, ohne Sammelzweig.
- [ ] **AK 8 — Sicherheitsnetz unberührt.** Die Prüflogik beider Netze bleibt unverändert; beide
      führen weiterhin ihre tragenden Testfunktionen namentlich; das neue Kennungsformat ist für den
      bestehenden Parser weiterhin sichtbar; beide laufen unverändert in ihren CI-Jobs.
- [ ] **AK 9 — Gegenprobe an den echten Vorfällen.** Zwei git-freie Tests mit literalen Branchnamen,
      die im selben Lauf auch das Versagen der alten Regel messen.

## Datenmodell-Bezug

Keine Entität berührt, keine Tabelle, kein Feld. Betroffen ist allein die **Kennung** künftiger
Alembic-Revisionen und deren `down_revision`-Verkettung; die 35 bestehenden Migrationen bleiben
bytegleich. `docs/architecture.md` bleibt unverändert — weder Systemarchitektur noch lokales Setup
noch das Rollenmodell ändern sich.

## Architektur / Umsetzung

Grundlage: ADR [`0108`](../decisions/0108-nummer-folgt-dem-rang-des-arbeitsstands.md);
ADR [`0081`](../decisions/0081-dokumentnummer-ist-identitaet-die-juengere-dublette-zieht-um.md)
trägt dazu einen Teil-Vermerk für Punkt 2 und den ersten Satz von Punkt 3.

### Gewählter Ansatz

Ein neues lokales Skript `scripts/nummern.py` ist **Zuteiler und Frühwarnung in einem**: Es liefert
die Nummer bzw. die Revisions-Kennung und meldet dabei, ob es eine Kontention gesehen hat. Es wird an
den Stellen aufgerufen, an denen eine Nummer entsteht oder nachträglich kippen kann. Die beiden
bestehenden Sicherheitsnetze (`scripts/tests/test_dokumentnummern_eindeutig.py`,
`backend/tests/test_migration_chain.py`) behalten ihre Prüflogik unverändert und laufen weiter in CI
(AK 8).

Kein CI-Job und kein Hook: In CI existiert weder ein zweiter Arbeitsbaum noch ein ungepushter Branch,
der zu prüfende Zustand ist dort gar nicht messbar; eine Hook-Konfiguration liegt nicht im
Repository und wäre weder testbar noch für Hintergrundläufe zugesichert.

### Kern: die Rechnung (rein, ohne git — hier liegt der Testschwerpunkt)

1. **Basis** = höchste Nummer des Verzeichnisses auf `origin/main`, plus 1. Nur `origin/main` — nie
   der eigene Blick, sonst rechnet jede Seite mit einer anderen Basis.
2. **Kontrahenten** = alle Branches, die im selben Nummernraum eine Nummer ≥ Basis führen, plus der
   eigene Branch; sortiert byteweise (C-Locale) nach dem vollständigen Branchnamen.
3. **Eigene Nummer** = Basis + Summe der Nummern, die rangniedrigere Kontrahenten sichtbar führen.

Der Branchname trägt die Ordnung, weil git denselben Branch nie in zwei Arbeitsbäumen auscheckt.
Beide Seiten rechnen dasselbe, jede für sich, ohne Nachricht und ohne Wartepunkt (AK 3, AK 4).

### Der Leser: vier Quellen, alle ohne `cd` in einen fremden Arbeitsbaum

- `git ls-tree -r -z --name-only origin/main -- <verzeichnis>` (Basis).
- `git ls-files --cached --others --exclude-standard -z` im eigenen Arbeitsbaum — fängt die Datei
  **vor** dem `git add`.
- Je Eintrag aus `git worktree list --porcelain -z`: `git ls-tree -r -z --name-only <branch> --
  <pfad>` für den committeten Stand **und** eine Verzeichnisauflistung von `<worktree>/<pfad>` für
  noch nicht committete Dateien. Die Arbeitsbäume teilen einen Ref-Speicher, deshalb funktioniert
  `ls-tree` auf einen Nachbarbranch aus dem eigenen Arbeitsbaum heraus.
- Jeder gepushte Branch, der **nicht** in `origin/main` enthalten ist, gelesen über
  `git for-each-ref --format=…` (nicht `git branch -r`, siehe S3).

Ein Branch ohne Arbeitsbaum und ohne `origin`-Gegenstück ist **kein** Kontrahent — sonst hielte ein
liegengebliebener Branch eine Nummer für immer besetzt.

**Die Nachbarauflistung wendet denselben Filter an wie der Blick auf den eigenen Arbeitsbaum.** Tut
sie es nicht, zählen zwei Seiten dieselbe Datei verschieden, und jede darauf gebaute
Determinismus-Zusage ist still falsch.

### Alembic (AK 6)

- **Kennung:** `sha256(<Branchname> + NUL + <Slug>)`, erste 12 Hex-Zeichen. Kollision konstruktiv
  ausgeschlossen, deterministisch wiederholbar. Die 35 bestehenden Migrationen bleiben unberührt.
- **Kette:** `down_revision` = Head von `origin/main`. Hat sich der Head verschoben, hängt der
  Abgleich mit `main` die eigene unterste Migration **ohne Rückfrage** hinter den neuen Head um; die
  bereits übernommene Migration wird nie angefasst. Mehrere eigene Migrationen behalten ihre interne
  Reihenfolge.
- **Sichtbar ohne Dateilesen:** Unterbefehl `kette` druckt die aufgelöste Reihenfolge; ein Umhängen
  erscheint als eigene Zeile (`<eigene Revision> hinter <neuer Head> gehängt`) im Abschlussbericht
  des `main`-Abgleichs.
- `alembic` wird **nicht** Abhängigkeit von `scripts/`; `kette` löst über denselben Zeilenparser auf,
  den `test_migration_chain.py` benutzt, und die Autorität über die echte Kette bleibt dort. Ein
  Bindetest misst, dass beide über den echten Bestand dasselbe sagen.

### Schnittstelle des Skripts (Exit-Codes wie `merge-main-into-branch.sh`)

| Unterbefehl | Ausgabe | Exit |
|---|---|---|
| `vorschlag <decisions\|architecture>` | die Nummer auf stdout | `0` ohne Kontention, `10` mit Kontention (Begründung auf stderr) |
| `migration <slug>` | Revisions-Kennung und `down_revision` | `0` / `10` (Head verschoben, Umhängen nötig) |
| `pruefen` | Befunde zeilenweise | `0` sauber, `10` Kontention aufgelöst, `20` echte Dublette im eigenen Baum |
| `kette` | aufgelöste Migrationskette | `0` |
| `vorschlag features` | Meldung „Nummer kommt vom Issue" | `≠0` — nie still eine Nummer liefern |

Ein unbekannter Exit-Code wird an keiner Aufrufstelle wie `0` behandelt.

### Betroffene Dateien

**Neu**
- `scripts/nummern.py` — Zuteiler und Wächter.
- `scripts/tests/test_nummern.py` — reine Rechnung, Leser, Exit-Codes, Gegenprobe an den beiden
  echten Vorfällen (AK 9).
- `scripts/tests/test_nummernvergabe_verankert.py` — Verankerung der Pflichtschritte (Muster:
  `test_werkzeugwahl_verankert.py`).

**Geändert**
- `CLAUDE.md`, Abschnitt „Konventionen": ein neuer Punkt „Nummernvergabe" in drei Sätzen.
- `.claude/agents/architect.md` — Pflichtschritt `vorschlag decisions` vor dem Anlegen einer ADR.
- `.claude/agents/developer.md` — Schritt 2: `migration <slug>` vor dem Anlegen einer Migration;
  Schritt 4: `pruefen` gehört in den Qualitätscheck; Folgeauftrag „Abgleich mit `main`":
  selbsttätiges Umhängen plus die Berichtszeile dazu.
- `.claude/skills/ship-feature/SKILL.md`, Schritt 6.2 — `pruefen` direkt nach dem `main`-Abgleich,
  und die Nachprüfung aus AK 7.
- `.claude/skills/spec-writer/SKILL.md` — ein Halbsatz: Die Spec-Nummer kommt vom Issue und fällt
  nicht unter die Rangregel.
- `specs/decisions/0081-…md` — nur der Kopf (Teil-Vermerk), kein Satz der Entscheidung.
- `scripts/tests/test_dokumentnummern_eindeutig.py` — **nur** der Meldungstext (siehe
  „Entscheidungen"), keine Zeile Prüflogik.
- `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md` — je eine
  neue Sektion (siehe unten).

**Bewusst nicht geändert:** `backend/tests/test_migration_chain.py`, `docs/`.

### AK 7: die Lücke hinter der Review-Runde

Der `main`-Abgleich liegt hinter der Review-Phase und ist damit die einzige inhaltliche Änderung, die
keine Review mehr sieht. Regelung in `ship-feature`, Schritt 6.2, nach dem Folgebericht des
Abgleichs:

- Berührt die Nachänderung **ausschließlich** Nummern-Token, Dateinamen und `down_revision`: Es
  laufen `review-architecture` auf dem neuen Diff, `nummern.py pruefen` und der volle
  `scripts/`-Testlauf. Das Ergebnis geht in den Abschlussbericht.
- Berührt sie mehr: vollständige Review-Runde erneut.

### Reihenfolge der Umsetzung

1. ADR 0108 und der Teil-Vermerk auf 0081 liegen bereits vor — nur lesen.
2. **Reine Rechnung zuerst** (`basis`, `kontrahenten`, `rang`, `nummer` als Funktionen ohne git):
   Tests rot, dann grün. Hier gehören beide AK-9-Gegenproben hinein, mit festen Branchnamen als
   Eingabe, ohne git, damit sie dauerhaft laufen.
3. **Leser** gegen ein Wegwerf-Repositorium (Fixture-Aufbau siehe Teststrategie).
4. **Unterbefehle und Exit-Codes** verdrahten, inklusive der `features`-Ablehnung.
5. **Alembic-Teil:** Kennungsableitung, `down_revision`-Ermittlung, Umhängen, `kette`.
6. **Verankerung:** `CLAUDE.md`, die beiden Agentendateien, die beiden Skills, dazu
   `test_nummernvergabe_verankert.py`; die beiden Konzeptdokumente.
7. Abschließend `scripts/check.sh` und beide Testsätze (`scripts/`, `backend/`) vollständig.

## UI/UX

Nicht relevant. Die Story berührt ausschließlich den Entwicklungsablauf (Skript,
Konventionsdokumente, Agenten- und Skill-Dateien, Migrations-Kennungen); keine der betroffenen
Dateien liegt unter `frontend/`, es entsteht weder Anzeige noch Eingabe in der Anwendung, und der
Issue-Body trägt keinen `## Design`-Abschnitt.

## Security

**Sicherheitsrelevant, schmal:** kein Anwendungscode, kein Endpunkt, kein Datenmodell, kein Frontend,
keine neue Abhängigkeit, kein Secret, keine Auth-/Berechtigungsänderung, kein Foto-, Orts- oder
Projektdatenbezug. Betroffen ist die Integrität des KI-gesteuerten Entwicklungsablaufs — plus
**eine** Stelle, die über den Entwicklungsrechner hinauswirkt: das Umhängen von `down_revision`.

**Kein fremder Branchname erreicht den Zuteiler.** Gemessen ist die Fetch-Refspec des Repositoriums
`+refs/heads/*:refs/remotes/origin/*`; `refs/pull/*` wird nicht geholt, und ein Fork-PR legt ohnehin
keinen Branch unter `refs/heads/*` des Ziel-Repositoriums an. Der einzige mittelbare Weg von außen
ist ein Issue-Titel fremder Autorschaft, aus dem eine Sitzung einen Branch-Slug bildet — und der
setzt Daniels `approved-for-agent`-Label voraus. Die Auflagen richten sich deshalb **nicht** gegen
einen Angreifer, sondern gegen Fehlbedienung und den eigenen künftigen Änderungsfehler.

**Pfad-Traversal und Zeilenumbrüche über einen Branchnamen sind strukturell ausgeschlossen**
(`git check-ref-format`, gemessen): `..`, Leerzeichen, `*`, LF und TAB werden abgewiesen. **Erlaubt**
sind dagegen `;`, `|`, `&`, `$(…)`, Backticks, Anführungszeichen und ein führender Bindestrich —
`git branch` weigert sich bei `-rf`, `git update-ref refs/heads/-rf HEAD` legt ihn gemessen trotzdem
an.

**S1 — Jeder Branchname und jeder Pfad geht als Listenelement an `subprocess.run`, nie über eine
Shell** (kein `shell=True`, keine String-Interpolation, kein `os.system`). **Und** jeder Aufruf, der
einen Branchnamen als Tree-ish nimmt, schiebt `--end-of-options` davor oder übergibt den voll
qualifizierten `refs/heads/<name>`. Gemessen: Die Listenform allein genügt nicht —
`["git","ls-tree","-r","--name-only","-rf","--","specs/decisions"]` endet mit Rückgabe `129`, mit
`--end-of-options` mit `0` und korrekter Ausgabe. Die Ausfallrichtung ohne S1 ist ausdrücklich
**keine** Codeausführung, sondern ein **unsichtbarer Kontrahent** — also genau die Doppelvergabe,
gegen die diese Spec geschrieben ist.

**S2 — Die Umgebung ist der zweite Eingabekanal und wird gesäubert.** Vor jedem `git`-Aufruf werden
`GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
`GIT_ALTERNATE_OBJECT_DIRECTORIES` und `GIT_CONFIG_COUNT` aus dem an `subprocess` übergebenen
Environment entfernt. Gemessen: Mit gesetztem `GIT_DIR`/`GIT_WORK_TREE` lasen sowohl `git ls-tree`
als auch `git worktree list --porcelain` ein **fremdes** Repository — die Basis käme still aus dem
falschen Nummernraum.

**S3 — NUL-getrennt lesen, nie zeilenweise.** `git ls-tree -z`, `git ls-files -z`,
`git worktree list --porcelain -z`, und die Branchliste über `git for-each-ref --format=…` statt
`git branch -r`. Gemessen: Ohne `-z` liefert `ls-tree --name-only` einen Namen mit Umlaut als
`"specs/decisions/0003-\303\244-umlaut.md"` — ein Nummernmuster greift dort nicht mehr, der
Kontrahent wird unsichtbar. `worktree list --porcelain` zerbricht an einem Zeilenumbruch im
Arbeitsbaumpfad, und `git branch -r` gibt die Zeile `origin/HEAD -> origin/main` aus, die kein
Branchname ist.

**S4 — Fail-closed an jedem Ausgang.** Von `0` / `10` / `20` löst nur `0` keine Handlung aus; still
falsch sein kann allein `0`. Exit `0` entsteht an genau einer Stelle. Ein `git`-Aufruf mit einer
unerwarteten Rückgabe hält den Lauf an und wird **nie** als „keine Nummern gefunden" verbucht.

**S5 — Die eigene Ausgabe wird geprüft, bevor sie einen Dateinamen bildet.** Die Revisionskennung
wird gegen `^[0-9a-f]{12}$` und der Slug gegen ein geschlossenes Muster aus Kleinbuchstaben, Ziffern
und Bindestrich mit Längengrenze geprüft, beides per `re.fullmatch` — nie `.match`/`.search`: `$`
passt auch unmittelbar vor einem abschließenden Zeilenumbruch. Der Slug ist der einzige Wert, der von
außerhalb des Skripts frei gewählt in einen Dateinamen läuft; kein Pfadtrenner, kein `..`, kein
führender Bindestrich.

**S6 — Das Umhängen fasst ausschließlich Revisionen an, die von `origin/main` nicht erreichbar sind;
lässt sich diese Menge nicht bestimmen, wird nicht umgehängt, sondern angehalten.** Das ist die
einzige Auflage mit Wirkung außerhalb des Entwicklungsrechners. Ändert sich Kennung oder
`down_revision` einer Revision, die auf Daniels Instanz **bereits ausgeführt** ist, findet
`alembic upgrade head` beim Containerstart den in `alembic_version` stehenden Wert nicht mehr und das
Backend startet nicht. Die bestehenden Kettentests fangen das **nicht**: Sie prüfen Auflösbarkeit,
Eindeutigkeit, genau einen Head und Erreichbarkeit — alles vier bleibt grün, wenn die Kette in sich
konsistent, gegenüber dem ausgerollten Stand aber verschoben ist. Fehlt der Ref `origin/main` oder
löst die Kette nicht auf, ist das „nicht gemessen", nicht „nichts umzuhängen".

**S7 — Außerhalb des eigenen Arbeitsbaums wird gelesen, nicht geschrieben, und nur benannt, nicht
geöffnet.** Kein `cd` und kein `git -C <fremder Pfad>` in einen fremden Arbeitsbaum (dessen Index
gehört einer parallel laufenden Sitzung), keine Rekursion, nur die eine Verzeichnisebene des
Nummernraums, nur Dateinamen, nie Dateiinhalte.

**S8 — Ausgabehygiene.** Selbst erzeugter Text und geprüfte Token, nie rohe `git`-Ausgabe: Keine
Meldung nennt die Remote-URL (`git remote get-url` kann `https://x-access-token:<token>@…` sein) oder
zitiert einen `fatal:`-Text. Ein Dateiname, der das Nummernmuster nicht besteht, wird **gezählt,
nicht zitiert**. Branchnamen und absolute Pfade fremder Arbeitsbäume gehören in den Chat-Bericht,
**nie** in einen PR-Body oder Issue-Kommentar — sie benennen ungemergte Arbeit fremder Sitzungen.

**Ausdrücklich geprüft und ohne Befund:** Die sha256-Ableitung ist keine Angriffsfläche — der
Branchname wird nie ausgeführt, die Ausgabe ist auf zwölf Hexziffern beschränkt, der NUL-Trenner
schließt die Mehrdeutigkeit zweier Eingabepaare aus, und Branchnamen sind kein Geheimnis. Kein neues
Secret, keine neue externe Abhängigkeit, kein neuer Empfängerkreis, keine Änderung an
Authentifizierung, Berechtigungen oder Datensichtbarkeit zwischen den beiden Nutzern.

`specs/architecture/0003-securitykonzept.md` erhält eine neue Angriffsflächen-Sektion (Inhalt: S1–S8)
und **eine** Zeile in der Ankerliste — nur für S6, weil allein deren Wegfall still bricht.

## Teststrategie

Kein Anwendungscode, kein Frontend, keine E2E-Ebene; `--cov-fail-under=80` ist nicht berührt, weil
keine Zeile unter `backend/src/photosort` entsteht. Alles Neue liegt unter `scripts/tests/` im
bestehenden CI-Job `demo-scripts` (ohne Coverage-Gate), aufgerufen mit `working-directory: scripts`.

**Drei Ebenen.**

1. **Rein (Schwerpunkt, `test_nummern.py`).** Die Rechnung ist eine Funktion über
   `(Basis, eigener Branch, {Branch → geführte Nummern})` ohne git, ohne Uhr, ohne Zufall. Hier
   liegen Injektivität (AK 3), der ungemergte Fall (AK 4), die Kennungsableitung (AK 6) und beide
   AK-9-Gegenproben. Diese Tests laufen dauerhaft, auch wenn die beteiligten Branches längst
   gelöscht sind.
2. **Integration gegen ein Wegwerf-Repositorium (`test_nummern.py`).** Der Leser mit vier Quellen
   gegen echte `git worktree add`-Nachbarn. Bauart, Umgebungsisolierung und Zeitgrenzen wie in
   `test_merge_main_into_branch.py`; `.git` ist im verbundenen Arbeitsbaum eine **Datei**, Zugriffe
   laufen über `git rev-parse --absolute-git-dir`.
3. **Statische Verankerung (`test_nummernvergabe_verankert.py`, Muster
   `test_werkzeugwahl_verankert.py`).** Konvention genau einmal in `CLAUDE.md`; Verdrahtung und
   Exit-Code-Behandlung an den Aufrufstellen (Reihenfolge über Zeichenoffsets, Muster
   `test_main_abgleich_verdrahtung.py`); Teil-Vermerk an ADR 0081; beide Sicherheitsnetze führen ihre
   tragenden Testfunktionen weiterhin.

`nummern.py` wird wie `seed-opencloud-demo.py` per Pfad geladen (`_load_module` in
`scripts/tests/conftest.py`) — `scripts/` ist bewusst kein importierbares Paket, und beide neuen
Testmodule brauchen dasselbe Skript.

### Fixture-Aufbau

Die neue Fixture entsteht in `test_nummern.py` und übernimmt von
`test_dokumentnummern_eindeutig.py` den Härtungsblock (alle `GIT_*` der Umgebung entfernen,
`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM=/dev/null`, `GIT_CEILING_DIRECTORIES` auf `tmp_path`,
Identitätsvariablen, `GIT_TERMINAL_PROMPT=0`), von `test_merge_main_into_branch.py` zusätzlich:
Zeitgrenze an **jedem** Unterprozess, `git init -b main` explizit, und ein bares `origin`.

```
tmp_path/
  origin.git/                    bar, main, führt specs/decisions/0105-basis.md   → Basis 0106
  haupt/                         Klon, eigener Branch
  haupt/.claude/worktrees/drin/  Arbeitsbaum INNERHALB des Haupt-Checkouts
  nachbar-a/                     Arbeitsbaum, Branch a/committet   → 0106 committet
  nachbar-b/                     Arbeitsbaum, Branch b/angelegt    → 0107 nur angelegt, kein add
```

Zwingende Zusicherungen: `0106` wird gefunden **und `a/committet` zugerechnet**; `0107` wird gefunden
**und `b/angelegt` zugerechnet** — die Zurechnung ist der Punkt, nicht das Finden, auf ihr ruht die
ganze Injektivität. Der Arbeitsbaum unter `haupt/.claude/worktrees/drin/` wird seinem eigenen Branch
zugerechnet, nie dem des Haupt-Checkouts. Der eigene Arbeitsbaum zählt genau einmal. **Mutationsprobe
im Docstring festhalten:** je einmal den `ls-tree`-Weg und den Verzeichnisweg entfernen; jedes Mal
muss genau einer der beiden Fälle rot werden — ohne diese Probe belegt ein grüner Lauf nur, dass
irgendein Weg getroffen hat. Kein `cd` in einen fremden Arbeitsbaum, in keinem Test.

### Edge Cases

**Rechnung:** Injektivität über allen Permutationen der Eingabereihenfolge; byteweise Sortierung
statt locale-abhängig (`feature/B-zwei` vs. `feature/a-eins`, dazu `-`/`/`/`_` und ein Name, der
Präfix eines anderen ist); ein Kontrahent führt mehrere Nummern; ein Branch mit Nummer < Basis ist
kein Kontrahent; leere Kontrahentenmenge → Basis unverändert; das Fenster aus ADR 0108 Punkt 4.

**Leser:** Symmetrie der Quellen (dieselbe Datei aus Sicht des eigenen Arbeitsbaums und des Nachbarn
gelesen ergibt dieselbe Menge — die Nachbarauflistung braucht denselben Filter); der eigene
Arbeitsbaum darf nicht doppelt zählen; ein Arbeitsbaum **innerhalb** des Haupt-Checkouts darf seine
Nummern nie dem Branch des Haupt-Checkouts zurechnen (zu **messen**, weil es an `.git/info/exclude`
hängt — einer Datei außerhalb des Repositoriums); die Pfeilform `origin/HEAD -> origin/main`; ein
veralteter Tracking-Ref eines squash-gemergten Branches (sein Tip ist nie Vorfahre von `origin/main`,
getragen wird das allein davon, dass seine Nummer < Basis ist); ein Branch ohne Arbeitsbaum und ohne
`origin`-Gegenstück; ein Nachbar mit losgelöstem HEAD (`detached` statt `branch refs/heads/…` — laut
behandeln, nie als leerer Name, der byteweise ganz vorn sortiert); `prunable`- und `bare`-Einträge;
Basis ausschließlich aus `origin/main`; fehlender `origin/main` → lauter Fehler, nie stillschweigend
Basis 1; leere `ls-tree`-Ausgabe → lauter Fehler (der stille Fall wäre hier der schlimmste: Basis 1,
ausgegeben würde `0001`); Dateinamen mit Umlaut und Leerzeichen; mitten im Merge listet
`git ls-files --cached` denselben Pfad je Stage mehrfach → Pfade zu einer Menge zusammenfassen.

**Migration:** fester Vektor `(Branch, Slug)` → exakt diese 12 Zeichen (der Test rechnet den Hash
**nicht** nach, sonst prüft er sich selbst); Mutationsprobe auf den NUL-Trenner (`("ab","c")` vs.
`("a","bc")` müssen verschieden sein); Form genau 12 Kleinbuchstaben-Hex und vom Parser des
bestehenden Netzes erkannt (fällt das, sieht das Netz die neuen Kennungen still nicht mehr — die
einzige Art, wie diese Story AK 8 verletzen könnte); die erzeugte Kennung ist in keiner der 35
bestehenden enthalten und die 35 bleiben bytegleich; zwei eigene Migrationen bei verschobenem Head →
nur die unterste hängt um, genau ein Kopf; mehrdeutiger Head → laut, nicht geraten; `kette` über den
echten Bestand als Bindetest zwischen beiden Parsern.

**Schnittstelle:** je Unterbefehl eine geschlossene Menge zulässiger Exit-Codes; `20` ist von `10` an
Ausgabe und Code unterscheidbar; `pruefen` auf sauberem Bestand gibt `0` — und eine leere Ausgabe
darf nie als „nichts gefunden" durchgehen, ohne dass zusätzlich belegt ist, dass überhaupt gelesen
wurde (Zähler statt Abwesenheit).

### AK-9-Gegenproben

Beide rein, ohne git, ohne Dateisystem, mit literalen Eingaben. Beide messen im **selben Lauf** auch
das Versagen der alten Regel; ohne diese zweite Hälfte wären sie Tautologien.

**Vorfall 1 — Dokumentnummer.** Basis `106`;
`feature/0469-verlaessliche-sehenswuerdigkeitsnamen` führt `106` und `107`; der eigene Branch steht
byteweise dahinter. Zugesichert: Die haltende Seite behält `106`, die eigene erhält `108`, in **einem**
Lauf. Gegenprobe daneben: die alte Regel („nächste freie Nummer") liefert **beiden** Seiten `106`.

**Vorfall 2 — Alembic.** `feature/0374-duplikate-vergleichen` und `feature/0434-ortsnamen-teil2`
vergaben dieselbe Kennung `d7e8f9a0b1c2`. Zugesichert mit diesen literalen Branchnamen: Die
abgeleiteten Kennungen sind verschieden, je 12 Kleinbuchstaben-Hex, beide ≠ `"d7e8f9a0b1c2"`, über
zwei Aufrufe stabil — und **auch bei identischem Slug** auf beiden Seiten verschieden.

`specs/architecture/0002-testkonzept.md` erhält eine neue, knappe Sektion (ca. 25–35 Zeilen) hinter
der `merge-main-into-branch.sh`-Sektion: die dritte Fixture-Bauform (n Arbeitsbäume mit je eigenem
Sichtbarkeitsgrad), die projektweite Filter-Symmetrie-Regel, Zusicherung als Eigenschaft statt
Fallliste, die drei Regeln für hash-abgeleitete Kennungen, und ein Eintrag unter „Bekannte Lücken":
Die Frühwarnung ist in CI strukturell unbeobachtbar, eine grüne CI belegt sie nicht.

## Entscheidungen

- `ux-ui-designer` nicht konsultiert (Schritt 2): kein konkret benennbarer Bezug zu einer sichtbaren
  Oberfläche — keine betroffene Datei liegt unter `frontend/`, und der Issue-Body trägt keinen
  `## Design`-Abschnitt.
- **Alembic-Kennung aus dem Branchnamen abgeleitet** statt handgewählter Hex-Folge (von Daniel am
  2026-09-14 bestätigt): Die Kollision ist damit konstruktiv ausgeschlossen statt nur früher
  sichtbar. Preis: Die neue Kennung sieht anders aus als die 35 bestehenden.
- **AK 7 wird gezielt nachgeprüft** statt mit einer vollständigen zweiten Review-Runde (von Daniel am
  2026-09-14 bestätigt).
- **AK 5 gegen AK 8, aufgelöst zugunsten beider:** Der Meldungstext von
  `test_dokumentnummern_eindeutig.py` gibt bei einer gefundenen Dublette die abgelöste Regel als
  Handlungsanweisung aus. AK 8 sagt zu, dass „was bislang laut wird, weiterhin laut wird" — das ist
  eine Zusage über die **Prüffunktion**, nicht über den Buchstaben der Datei. Die Prüflogik bleibt
  deshalb unverändert, und nur der Meldungstext nennt die neue Regel. Das Netz wird genauso laut
  (AK 8), und die abgelöste Regel gilt an keiner Stelle des Bestands weiter (AK 5).
- **`alembic` wird nicht Abhängigkeit von `scripts/`:** `kette` löst über denselben Zeilenparser auf,
  den `test_migration_chain.py` benutzt; ein Bindetest begrenzt das Restrisiko darauf, dass beide
  Parser über den echten Bestand dasselbe sagen.
- **Korrektur am Leser-Entwurf:** Für „gepushte, nicht in `origin/main` enthaltene Branches" ist
  `--no-merged origin/main` maßgeblich, nicht `--merged`; der Aufruf läuft ohnehin über
  `git for-each-ref` (S3).

## Offene Fragen

Keine.

## Out of Scope

- **Ein CI-Wächter für die Frühwarnung.** In CI existiert weder ein zweiter Arbeitsbaum noch ein
  ungepushter Branch; eine Prüfung dort wäre grün, ohne etwas zu wissen.
- **Verzeichnisübergreifende Eindeutigkeit** der Nummernräume (ADR 0081 Punkt 1 gilt unverändert).
- **Umnummerierung des Bestands.** Die 35 bestehenden Migrationen und alle vergebenen
  Dokumentnummern bleiben, wie sie sind.
- **Eine Zusicherung, dass der Ablauf zur Laufzeit wirklich aufruft und wirklich erneut reviewt.**
  Das ist LLM-interpretiert; die statische Verankerung prüft die Verdrahtung, nicht die Befolgung.
- **Aufräumen von `specs/architecture/0002-testkonzept.md`** (2375 Zeilen, Richtwert ~300 ohne
  Begründungssatz). Getrennt aufzuwerfen.
