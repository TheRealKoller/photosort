# 0078 - Maschinelle Formatierung: `ruff format` und Prettier, exakt fixiert, ohne auslösenden Automatismus

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** [Issue #400](https://github.com/TheRealKoller/photosort/issues/400), Spec [`../features/0400-einheitliche-code-formatierung.md`](../features/0400-einheitliche-code-formatierung.md)

## Kontext

PhotoSort wird vollständig von KI-Agenten entwickelt. Der Code ist heute stilistisch bemerkenswert einheitlich — in den TypeScript-Bäumen ausnahmslos (einfache Anführungszeichen, keine Semikolons), im Backend zu über 97 %. Diese Einheitlichkeit ist jedoch nirgends zugesichert: Sie entsteht allein daraus, dass jeder Agenten-Lauf den umgebenden Code nachahmt. Am Bestand gemessen (11.09.2026, `ruff 0.16.4` bzw. `prettier 3.9.6`):

| Baum | Dateien, die vom kanonischen Format abweichen |
|---|---|
| `backend/` ohne `alembic/versions` | 60 von 110 |
| `backend/alembic/versions` | 22 von 22 |
| `scripts/` | 9 von 15 |
| `frontend/` (`src/` + `penpot/`) | 123 von 187 |
| `e2e/` | 18 von 23 |

Für die Zeilenbreite im Frontend gibt es überhaupt keine Regel — 378 der 35.264 Zeilen liegen über 100 Zeichen, 34 über 120. Bricht ein Lauf das Muster, fällt das niemandem auf, und ab dann mischen sich Formatierungsänderungen in inhaltliche Diffs.

Zwei Nebenbefunde aus derselben Messung, die die Dringlichkeit zeigen:

- `ruff` steht in beiden `pyproject.toml` als `ruff>=0.7`. In den drei real vorhandenen lokalen Umgebungen liefen zum Messzeitpunkt **drei verschiedene Versionen**: `0.16.1` (`scripts/.venv`), `0.16.2` (`backend/.venv`), `0.16.4` (`~/.local/bin`). Eine offene untere Schranke fixiert nichts.
- `ruff` ändert den Stable Style bei **Minor**-Bumps — der "Ruff 2026 style guide" in 0.15.0 tat das zuletzt. Prettier sagt über sich selbst, dass sogar ein Patch-Release die Ausgabe verändern kann.

## Entscheidung

### 1. Python: `ruff format` ist der kanonische Formatierer

Kein Black, kein zweites Werkzeug. `ruff` ist in beiden Python-Bäumen bereits als Linter im Einsatz, `line-length = 100` steht in beiden `pyproject.toml`, und beide CI-Jobs (`backend`, `demo-scripts`) installieren es ohnehin. Ein zweites Werkzeug brächte eine zweite Version, eine zweite Konfigurationsquelle für dieselbe Zeilenbreite und einen zweiten Installationsschritt — für ein Ergebnis, das sich vom Black-kompatiblen `ruff format` nicht unterscheidet.

Gemessene Auswirkung: `backend/` +1.033/−1.195 Zeilen, `scripts/` +26/−61 Zeilen. Der Diff schrumpft netto, weil der Formatierer von Hand umgebrochene Ausdrücke wieder zusammenzieht.

### 2. `alembic/versions` wird formatiert, aber weiterhin nicht gelintet

Heute steht in `backend/pyproject.toml`:

```toml
[tool.ruff]
extend-exclude = ["alembic/versions"]
```

`extend-exclude` unter `[tool.ruff]` gilt für **beide** Werkzeuge. Bliebe es dort stehen, wäre `alembic/versions` vom Formatierer ausgenommen — nicht weil das entschieden wurde, sondern geerbt. Der Ausschluss wird deshalb auf den Linter verengt:

```toml
[tool.ruff.lint]
exclude = ["alembic/versions/*"]
```

Der Grund für den Lint-Ausschluss ist der Regelinhalt: von Alembic erzeugte Migrationen tragen `Union[str, Sequence[str], None]` (UP007), veraltete `typing`-Importe (UP035) und unsortierte Importe (I001) — real 125 Befunde. Der **Formatierer** hat dagegen keine Meinung, die generierter Code verletzen könnte; er normalisiert nur. Die Ausgabe von `alembic revision --autogenerate` ist linksbündig eingerückt und dadurch schlecht lesbar; formatiert wird sie zum normalen Python-Code des Repositorys.

**Verifiziert, kein Nebenschaden:** Nach dem Formatieren aller 22 Migrationsdateien behält jede ihre `revision: str = "..."`-Zeile in der Form, die `backend/tests/test_migration_chain.py` zeilenweise sucht (22 von 22). Das ist die einzige Stelle im Repository, die Migrations-Quelltext als Text liest; alle übrigen `test_migration_*.py` importieren das Modul und führen `upgrade()`/`downgrade()` aus — formatunabhängig.

**Fallstrick, der aus dieser Entscheidung folgt:** `alembic revision --autogenerate` erzeugt ab sofort jedes Mal eine unformatierte Datei. Der Formatierlauf gehört danach zum Anlegen einer Migration.

**Zur Mustersyntax:** Das schlichte `exclude = ["alembic/versions"]` unter `[tool.ruff.lint]` wirkt **nicht** (gemessen: 125 Befunde bleiben stehen) — anders als unter `[tool.ruff]`, wo dieselbe Schreibweise greift. Erst ein Glob (`alembic/versions/*`) schließt aus. Das ist eine stille Falle und deshalb hier festgehalten.

### 3. E501 bleibt aktiv, bekommt aber eine getrennte, weitere Grenze

`ruff` listet E501 ausdrücklich **nicht** unter den formatierer-konfliktträchtigen Regeln (das sind `W191`, `E111`, `E114`, `E117`, `D203`, `D206`, `D300`, `Q000`–`Q004`, `COM812`, `COM819`, `ISC002` — von denen keine in PhotoSorts `select = ["E", "F", "I", "UP", "B"]` liegt). Es warnt aber: der Formatierer bricht Zeilen nur nach bestem Bemühen um, formatierter Code **darf** die Zeilenbreite überschreiten.

Genau das tritt im Bestand an **einer** Stelle ein. `backend/tests/test_config.py:258` beginnt einen Docstring mit einem Anführungszeichen (`""""Verstaendliche Fehlermeldung" ist ...`). Der Formatierer setzt zur Entschärfung ein Leerzeichen ein (`""" "Verstaendliche ...`) — und schiebt die Zeile damit selbst auf 101 Zeichen. Der Linter meldet danach E501 auf einer Zeile, die der Formatierer erzeugt hat und die er nicht kürzen kann. Ein `# noqa` ist dort unmöglich: die beanstandete Zeile liegt innerhalb eines Stringliterals.

Entschieden wird die von `ruff` selbst vorgesehene Stellschraube, in **beiden** Python-Bäumen:

```toml
[tool.ruff.lint.pycodestyle]
max-line-length = 110
```

`line-length = 100` bleibt unverändert die Zielbreite des Formatierers; E501 schlägt erst ab 111 Zeichen an. Verifiziert: mit dieser Einstellung ist `ruff check` auf dem vollständig formatierten Backend grün (`All checks passed!`), ebenso `mypy --strict` (40 Quelldateien, keine Befunde).

**Warum nicht `ignore = ["E501"]`,** was `ruff` als Alternative nennt: E501 ist im Repository das einzige, was überlange **Kommentare und Docstrings** in Schranken hält — und PhotoSorts Code besteht zu erheblichen Teilen aus langer erklärender Prosa, die der Formatierer grundsätzlich nicht umbricht. E501 ganz abzuschalten gäbe genau dort die Zusicherung auf, wo der Formatierer sie nicht ersetzen kann. Die weitere Grenze behält den Wächter gegen eine 300-Zeichen-Kommentarzeile und nimmt ihm nur die zehn Zeichen Spielraum, die der Formatierer selbst braucht.

Dies ist zugleich die Umsetzung des Akzeptanzkriteriums "wo Formatierer und Linter sich widersprechen, wird die Linter-Regel angepasst, nicht die Formatierung abgeschwächt": angepasst wird ausschließlich die Linter-Grenze, `line-length = 100` bleibt.

### 4. `ruff format` fasst keine Markdown-Datei an

`ruff` formatiert seit 0.16.0 standardmäßig **Python-Codeblöcke in Markdown-Dateien**. Gemessen: ein `ruff format .` in einem Verzeichnis mit einer `probe.md` schreibt darin `x   =    1` zu `x = 1` um und meldet "1 file reformatted".

Das steht dem Akzeptanzkriterium entgegen, dass Markdown ausdrücklich ausgenommen bleibt. Heute ist der Fall nur latent — unter `backend/` und `scripts/` liegt keine einzige `.md`-Datei —, aber er tritt in dem Moment ein, in dem jemand dort eine anlegt. Der Ausschluss wird deshalb **aktiv** konfiguriert, in beiden Bäumen:

```toml
[tool.ruff.format]
exclude = ["*.md"]
```

Verifiziert: damit bleibt die Markdown-Datei unverändert.

### 5. TypeScript: Prettier, nicht oxfmt

Die naheliegende Alternative wäre `oxfmt` aus demselben Projekt wie das bereits eingesetzte `oxlint`. Sie wird **verworfen**. Stand 11.09.2026:

- `oxfmt` steht bei **0.67.0**. Kein 1.0, kein angekündigter 1.0-Termin. Die letzte ausdrückliche Selbsteinschätzung des Projekts ist "Beta, auf dem Weg zu stable" (Beta-Ankündigung 24.02.2026); die heutige Dokumentation vermeidet sowohl "beta" als auch "stable".
- Die viel zitierte Zahl "100 % der Prettier-Konformitätstests" gilt **ausdrücklich nur für JS/TS**. Für CSS und JSON — beide laut Akzeptanzkriterium im Geltungsbereich — gibt es keine vergleichbare Zahl und keine Reifegradangabe.
- `oxfmt` kennt **keine** Datei-weite Ignore-Direktive (`oxfmt-ignore-file`, `oxfmt-ignore-start/end`); der zugehörige Issue ist seit 06.05.2026 offen.
- `sortPackageJson` ist standardmäßig **an** und ordnet `package.json` ungefragt um — eine Datei, die `release-please` per JSONPath bearbeitet.
- Markdown behandelt `oxfmt` nicht selbst, sondern über ein gebündeltes Prettier. Es ist damit kein Prettier-Ersatz, sondern eine Prettier-Kapselung mit einer zusätzlichen Versionsebene dazwischen.

Eine Regel, die **verbindlich** sein und in CI blockieren soll, darf nicht auf einem Werkzeug mit 0.x-Versionsschema und unvermessener CSS-/JSON-Ausgabe stehen. Ein Formatierer, dessen Ausgabe sich noch bewegt, erzeugt genau die Diff-Unruhe, die diese Entscheidung beseitigen soll. Entschieden wird **Prettier 3.9.6**.

Das ist ausdrücklich **keine** Entscheidung gegen `oxfmt` auf Dauer: Der Wechsel ist eine Konfigurations- und Lockfile-Änderung plus ein einmaliger Durchformatier-Diff, also derselbe Handgriff wie diese Einführung. Erreicht `oxfmt` 1.0 mit vermessener CSS-/JSON-Konformität, ist das eine neue ADR wert — kein Grund, heute darauf zu warten.

### 6. Die Optionen schreiben den geltenden Stil fest

```
singleQuote: true
semi: false
printWidth: 100
```

Alle drei müssen explizit gesetzt werden — Prettiers Voreinstellungen sind das Gegenteil (`singleQuote: false`, `semi: true`, `printWidth: 80`). `trailingComma: "all"` und `arrowParens: "always"` bleiben auf der Voreinstellung, weil sie den Bestand bereits treffen.

`printWidth: 100` ist bewusst dieselbe Zahl wie `line-length` im Backend. Damit gibt es **eine** Zeilenbreite im Projekt statt zweier, und der Diff beschränkt sich im Kern auf Zeilenumbrüche statt auf einen Stilwechsel: `frontend/` +1.372/−1.013 Zeilen über 123 Dateien (bei 35.264 Zeilen Bestand), `e2e/` +124/−107 über 18 Dateien (bei 2.799 Zeilen).

**Verifiziert auf dem formatierten Stand:** `oxlint` meldet exakt dieselben 10 Warnungen wie vorher und keinen Fehler (Exit 0); `tsc -b --noEmit` im Frontend und `tsc --noEmit` in `e2e/` sind grün; von 1.567 Vitest-Fällen schlägt genau **einer** fehl (siehe Abschnitt 10). Die erzeugten Penpot-Nutzlasten `design/penpot/tokens.json` und `icons.json` bleiben byte-gleich — das Formatieren der Erzeuger unter `frontend/penpot/` ändert deren Ausgabe nicht.

### 7. Beide TypeScript-Bäume, eine Konfiguration im Wurzelverzeichnis

`frontend/` und `e2e/` werden **beide** erfasst und tragen **denselben** Stil. Eine Kopie der Konfiguration je Baum wäre eine zweite Quelle der Wahrheit für dieselbe Regel. Gemessen am echten Baum:

- **`.prettierrc.json` gehört ins Repository-Wurzelverzeichnis.** Prettier sucht die Konfiguration vom Pfad der zu formatierenden **Datei** aufwärts, unabhängig vom Arbeitsverzeichnis. Verifiziert: `prettier --find-config-path src/App.tsx` aus `frontend/` heraus und `--find-config-path lib/auth.ts` aus `e2e/` heraus liefern beide `../.prettierrc.json`. **Kein Flag nötig.**
- **`.prettierignore` gehört ebenfalls ins Wurzelverzeichnis, wird von dort aber nicht gefunden.** Prettier sucht die Ignore-Datei **nicht** aufwärts, sondern liest die Vorgabe relativ zum **Arbeitsverzeichnis**. Verifiziert: ohne Flag meldet ein Lauf aus `e2e/` eine dort abgelegte `PROBE.md` als abweichend, obwohl `*.md` in der Wurzel-Ignore-Datei steht. Beide Aufrufe brauchen deshalb **`--ignore-path ../.prettierignore`**.
- **`--ignore-path` ersetzt die Vorgabe vollständig, es ergänzt sie nicht.** Verifiziert mit einer Probe, die nur von einer lokalen `.gitignore` erfasst wird: ohne Flag ausgeschlossen, mit `--ignore-path ../.prettierignore` wieder sichtbar, mit beiden Pfaden erneut ausgeschlossen. Folge: Die Wurzel-Ignore-Datei muss **selbsttragend** sein und darf sich nicht darauf verlassen, dass `frontend/.gitignore` `dist/` nennt.
- **Muster in der Ignore-Datei sind relativ zu deren Verzeichnis, nicht zum Arbeitsverzeichnis.** Verifiziert: das Muster `e2e/lib/` schließt `lib/auth.ts` auch dann aus, wenn der Lauf aus `e2e/` heraus startet. In der Wurzeldatei stehen also repo-weite Pfade, so wie man sie liest.
- **`node_modules` bleibt ausgeschlossen, auch mit `--ignore-path`** — das ist kein Ignore-Datei-Mechanismus, sondern in Prettier fest verdrahtet. Verifiziert.

Nebennutzen der Wurzel-Ablage: Ein versehentliches `npx prettier --write .` aus dem Repository-Wurzelverzeichnis findet die Ignore-Datei über die Vorgabe und lässt die 219 Markdown-Dateien in Ruhe. Läge sie unter `frontend/`, wäre dieser Griff ein Massenschaden an Specs und ADRs.

**Die tragende Folge von `--ignore-path`: `/.prettierignore` ist ab sofort die einzige Ausschlussquelle, und sie muss jeden einschlägigen `.gitignore`-Eintrag spiegeln.** Das ist keine Stilfrage, sondern ein gemessener Sicherheitsbefund (11.09.2026, `prettier 3.9.6`). Weil die `.gitignore`-Auswertung mit dem Flag entfällt und Prettier **auch in Punktverzeichnisse absteigt**, erfasst ein lokaler Lauf aus `e2e/` heraus sonst genau die Verzeichnisse, die das Sicherheitskonzept als schützenswert führt:

- `e2e/.auth/state.json` trägt den gespeicherten Anmeldezustand mit einem 30 Tage gültigen, nicht widerrufbaren JWT. Gemessen: `prettier --check .` meldet die Datei als abweichend, `prettier --write .` — also `scripts/format.sh` — **schreibt sie neu**.
- **Leckkanal, ebenfalls gemessen:** Bei einem Parse-Fehler gibt Prettier einen Code-Frame **mit dem Dateiinhalt** aus; im Versuch stand der Token-Wert wörtlich in der Ausgabe. Eine halb geschriebene `state.json` aus einem abgebrochenen Lauf genügt, damit das Token im Terminal oder im Protokoll eines Agenten-Laufs landet.
- Dasselbe gilt für `e2e/artifacts/`, `e2e/test-results/` und `e2e/playwright-report/` — Playwright-Traces enthalten Netzwerkinhalte samt Login-Request und `localStorage`-Zustand.

**CI ist davon nicht betroffen** (`npm run format:check` steht dort vor Chromium und Stackstart, die Verzeichnisse existieren zum Prüfzeitpunkt nicht), **lokal aber sehr wohl** — und lokal läuft der schreibende Befehl. Die Wurzel-Ignore-Datei trägt deshalb zwingend auch `e2e/.auth/`, `e2e/artifacts/`, `e2e/test-results/`, `e2e/playwright-report/`, `e2e/scratch/` und `frontend/dist-ssr/`. Verifiziert: mit diesen Einträgen meldet der Lauf aus `e2e/` „All matched files use Prettier code style!".

**Die Regel gilt über diese sechs Einträge hinaus und dauerhaft:** Jeder `.gitignore`-Eintrag, der unterhalb von `frontend/` oder `e2e/` greift und eine von Prettier unterstützte Endung treffen kann, muss in `/.prettierignore` gespiegelt werden — auch jeder künftige. Sonst laufen die beiden Dateien still auseinander, und der Formatierer greift auf unversionierte lokale Inhalte zu. Weil genau diese Zusicherung still bricht (lokal fällt sie nur als „eine Datei mehr formatiert" auf, in CI gar nicht), wird sie mechanisch gehalten (Abschnitt 8).

**Die Spiegelung ist vollständig, ohne Ausnahmeliste** (Review-Fund und Entscheidung Daniels, 11.09.2026). Ein erster Umsetzungsstand führte nur die elf offensichtlichen Einträge; nachgemessen erfasste Prettier **vierzehn** weitere. `/.prettierignore` trägt deshalb zusätzlich `.vscode/`, `__pycache__/`, `*.egg-info/`, `build/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.vite/`, `logs/`, `photo-cache/`, `.idea/` und `*.ntvs*`. Die meisten davon können unter `frontend/` oder `e2e/` heute gar nicht entstehen — es sind Artefakte der Python-Werkzeugkette oder Bausteine der Vite-Vorlage. Sie stehen trotzdem dort, weil die Asymmetrie die Entscheidung trägt: Ein überflüssiger Eintrag kostet eine Zeile in einer Datei, die ohnehin nur Ausschlüsse führt; ein fehlender kostet eine still umgeschriebene, unversionierte lokale Datei — bei `e2e/.auth/` war genau das ein Sicherheitsbefund. Und nur die vollständige Liste lässt den Wächtertest aus Abschnitt 8 seine Erwartung mechanisch aus den `.gitignore`-Dateien ableiten; jede Ausnahmeliste wäre eine Ermessensentscheidung, die später jemand ohne Kenntnis des Anlasses neu treffen müsste.

**Zwei gemessene Eigenschaften, an denen die Erhebung dieser Liste hängt** — beide sind der Grund, warum die Liste *gemessen* und nicht überlegt gehört:

- **Die Dateiendung trägt die Entscheidung nicht, das Verzeichnis trägt sie.** Ein Eintrag wie `logs` oder `.idea` sieht nach einer Endung aus, die Prettier nicht kennt, trifft aber ein *Verzeichnis*, in dem eine `.json` liegen kann. Wer nach Endungen filtert, findet allein `.vscode/` und hält die Spiegelung fälschlich für vollständig — genau dieser Fehler ist im Review einmal unterlaufen. `*.ntvs*` ist der einzige Datei-Glob der Liste, weil sein nachgestelltes `*` ihn `foo.ntvs.json` treffen lässt; alle übrigen (`*.log`, `*.local`, `*.suo`, `*.sln`, `*.sw?`, `.DS_Store`, `.coverage`) schließen den Dateinamen nach hinten ab und können eine unterstützte Endung strukturell nicht treffen.
- **Ein wörtlich aus einer `.gitignore` übernommenes Muster kann wirkungslos sein.** `frontend/.gitignore` schreibt `.vscode/*`. Dieser Schrägstrich *in der Mitte* bindet das Muster an das Verzeichnis der Ignore-Datei — hier die Repository-Wurzel — und ließe `frontend/.vscode/` unberührt. Nur `.vscode/`, mit Schrägstrich ausschließlich am Ende, greift auf jeder Ebene. Mit vier Varianten nachgemessen. Ebenso nachgemessen: Der Wiedereinschluss `!.vscode/extensions.json` bleibt wirkungslos, weil gitignore-Semantik eine Datei unterhalb eines ausgeschlossenen Verzeichnisses nicht wieder einschließen kann; er wird deshalb nicht gespiegelt, und eine künftige, dann versionierte `extensions.json` bliebe unformatiert.

**Die Python-Hälfte ist nicht betroffen:** `ruff` behält `respect-gitignore = true`, und `[tool.ruff.format] exclude` **ergänzt** die Vorgabe, statt sie zu ersetzen (gemessen). `.env` ist für beide Werkzeuge unerreichbar — Prettier wählt im Verzeichnislauf nur Dateien mit unterstützter Endung, und für `.env` gibt es keinen Parser.

**Falle:** Ein `"prettier"`-Schlüssel in einer `package.json` **überschattet** die Wurzel-Konfiguration still. Verifiziert: mit einem solchen Schlüssel meldet `--find-config-path` nicht mehr `../.prettierrc.json`, sondern `package.json`. Keine Warnung, kein Fehler. Deshalb wird die Abwesenheit dieses Schlüssels mechanisch gehalten (Abschnitt 8).

Die npm-Skripte sind in beiden Bäumen wortgleich:

```json
"format": "prettier --ignore-path ../.prettierignore --write .",
"format:check": "prettier --ignore-path ../.prettierignore --check ."
```

### 8. Versionen werden exakt fixiert, und die vier Fixierungen werden mechanisch gekoppelt

| Werkzeug | Ort | Wert |
|---|---|---|
| `ruff` | `backend/pyproject.toml` (`[project.optional-dependencies] dev`) | `ruff==0.16.4` statt `ruff>=0.7` |
| `ruff` | `scripts/pyproject.toml` (dito) | `ruff==0.16.4` statt `ruff>=0.7` |
| `prettier` | `frontend/package.json` (`devDependencies`) + `package-lock.json` | `"prettier": "3.9.6"` — ohne Caret |
| `prettier` | `e2e/package.json` (dito) + `package-lock.json` | `"prettier": "3.9.6"` — ohne Caret |

Die Schreibweise ohne Caret folgt dem bereits im Repository bestehenden Vorbild `e2e/package.json`, wo `@playwright/test`, `@types/node` und `typescript` exakt stehen, und Prettiers eigener Empfehlung ("Even a patch release of Prettier can result in slightly different formatting"). Für `ruff` gibt es kein Lockfile; die exakte Angabe **ist** die Fixierung. Sie muss exakt sein, weil `ruff` den Stable Style bei Minor-Bumps ändern darf.

**Warum `0.16.4` und nicht der neueste Stand** (Entscheidung Daniels, 11.09.2026): Zum Entscheidungszeitpunkt war `0.16.7` einen Tag alt (PyPI-Upload 10.09.2026). Genau dieses Fenster ist das, in dem eine kompromittierte Veröffentlichung am wahrscheinlichsten noch unentdeckt ist — und `ruff` landet über `[dev]` auf dem Entwicklerrechner, auf dem auch `gh`-Token und Repository-Schreibzugriff liegen. `0.16.4` ist länger verfügbar, lag bereits lokal installiert vor und ist zugleich die Version, mit der der Kontextabschnitt dieser ADR seine Bestandsmessungen gemacht hat: Pin und Messung decken sich damit, statt auseinanderzufallen. Der Preis sind drei Patch-Stände; der Gegenwert ist, dass die Fixierung nicht auf einer Veröffentlichung von gestern ruht. Ein späteres Hochziehen des Pins ist ein eigener, kleiner Vorgang — er kostet die Neuberechnung des Formatier-Diffs, falls sich die Ausgabe zwischen den Ständen bewegt hat.

**Damit steht dieselbe Zahl an vier Stellen — das ist der Preis dafür, dass jeder Baum für sich installierbar bleibt, und er wird nicht weggeredet, sondern mechanisch abgesichert.** Ein Wächtertest unter `scripts/tests/` (CI-Job `demo-scripts`) hält:

1. beide `pyproject.toml` nennen **dieselbe** `ruff`-Version,
2. beide `package.json` nennen **dieselbe** `prettier`-Version,
3. alle vier Angaben sind **exakt** (kein `>=`, kein `~`, kein `^`, kein `*`),
4. keine `package.json` im Repository trägt einen `"prettier"`-Schlüssel, der die Wurzel-Konfiguration überschatten würde.

**Ein dritter Wächtertest hält die Spiegelungspflicht aus Abschnitt 7** — `/.prettierignore` gegen die `.gitignore`-Einträge unterhalb von `frontend/` und `e2e/`, mit den fünf `e2e/`-Verzeichnissen als fest zugesicherter Mindestmenge. Begründung wie bei den anderen beiden: Es ist eine Zusicherung, die still bricht, und eine still brechende Zusicherung ohne Test ist keine.

Das ist die Antwort auf die Duplikation, nicht ihre Vermeidung. Sie ist einer Vermeidung vorzuziehen, weil die Duplikation ohnehin entsteht: die beiden `ruff`-Pins sind unvermeidbar, solange `backend/` und `scripts/` getrennte Python-Projekte mit getrennten CI-Jobs sind. Ein Mechanismus, der alle vier Stellen erfasst, ist besser als ein Sonderweg, der nur die Prettier-Hälfte strukturell löst und für die `ruff`-Hälfte trotzdem einen Test braucht.

**Verworfen: Prettier nur in `frontend/` installieren und von dort aus `../e2e` mitformatieren.** Das spart genau eine Fixierung, macht aber das Frontend-Paket zum Eigentümer eines fremden Baums, und wer nur `e2e/` ausgecheckt-installiert hat, könnte nicht mehr formatieren. Der Wächtertest wäre trotzdem nötig (siehe oben).

**Verworfen: eine `package.json` im Wurzelverzeichnis** mit einer einzigen Prettier-Fixierung. Sie löste die Duplikation strukturell, erzwänge aber einen eigenen CI-Job (`npm ci` im Wurzelverzeichnis, den kein bestehender Job macht) — und ein neuer Job-Name muss von Hand in `required_status_checks.contexts` der Branch Protection nachgetragen werden und blockiert bis dahin nichts (ADR [`0064`](./0064-pr-titel-pruefung-eigener-blockierender-workflow.md), Abschnitt 6). Eine Durchsetzung, die erst nach einem manuellen Schritt greift, ist für diese Story die schlechtere Wahl.

**Falle beim Umsetzen:** Die bestehenden lokalen `.venv` tragen ältere `ruff`-Versionen (`0.16.1`/`0.16.2`). Vor dem Durchformatieren müssen beide Bäume mit dem neuen Pin neu installiert werden, sonst entsteht ein Diff, den CI später nicht bestätigt. Gegenprobe: `uvx ruff@0.16.4 format --check .` muss dasselbe sagen wie die lokale Installation.

### 9. Geltungsbereich und Ausschlüsse

**Erfasst:**

- `backend/**/*.py` einschließlich `alembic/versions` (Abschnitt 2)
- `scripts/**/*.py`
- `frontend/src/**/*.{ts,tsx,css}`, `frontend/penpot/**/*.ts`, `frontend/*.json`, `frontend/vite.config.ts`, `frontend/index.html`
- `e2e/**/*.ts`, `e2e/*.json`

**Ausgeschlossen, jeweils mit Grund:**

| Ausschluss | Grund |
|---|---|
| **Alle `*.md`** | Akzeptanzkriterium. In den TypeScript-Bäumen über `/.prettierignore`, im Backend/`scripts` über `[tool.ruff.format] exclude` (Abschnitt 4). Handgesetzte Umbrüche tragen dort Absatzstruktur. |
| `frontend/package-lock.json`, `e2e/package-lock.json` | werden von `npm` erzeugt und bei jeder Installation neu geschrieben; ein Formatierer darauf erzeugt endlose Scheindifferenzen. |
| `dist/`, `node_modules/` | Bauartefakte bzw. Fremdcode. `node_modules` ignoriert Prettier von sich aus; `dist/` **nicht** — und die `.gitignore`-Vorgabe entfällt, sobald `--ignore-path` gesetzt ist (Abschnitt 7), der Eintrag ist also tragend. |
| `design/` **vollständig** | `tokens.json` und `icons.json` sind **erzeugt**: `frontend/penpot/tokens.test.ts` und `icons.test.ts` schreiben sie per `toMatchFileSnapshot` aus `JSON.stringify(x, null, 2)`. Ein Formatierer, der diese Dateien anfasst, bringt den Snapshot-Test zu Fall. Die vier `seed-*.js`/`verify.js` und `components.json`/`views.json` sind handgeschriebene Nutzlast, über die `frontend/penpot/payload.test.ts` statische AST-Zusicherungen trifft; sie wird als Text in eine Penpot-Sitzung eingefügt (ADR [`0066`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)). Ein Verzeichnis, zwei Gründe, eine Regel. |
| `assets/beispielbilder/`, `*.svg`, `*.tflite`/`*.hdf5`/`*.task`/`*.onnx` | keine von einem der beiden Formatierer behandelte Sprache; kein Eintrag nötig, hier nur der Vollständigkeit halber benannt. |
| `backend/alembic/script.py.mako` | keine Python-Datei nach Endung; `ruff` fasst sie nicht an. |
| `e2e/.auth/`, `e2e/artifacts/`, `e2e/test-results/`, `e2e/playwright-report/`, `e2e/scratch/`, `frontend/dist-ssr/` | lokale, unversionierte Laufartefakte — bis hierher von der `.gitignore`-Auswertung getragen, die mit `--ignore-path` entfällt. `e2e/.auth/state.json` trägt ein 30 Tage gültiges JWT, die Playwright-Traces tragen Netzwerkinhalte samt Login-Request. Gemessener Sicherheitsbefund, siehe Abschnitt 7. |
| `.vscode/`, `__pycache__/`, `*.egg-info/`, `build/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.vite/`, `logs/`, `photo-cache/`, `.idea/`, `*.ntvs*` | der Rest der vollständigen `.gitignore`-Spiegelung (Abschnitt 7). Kein Quelltext, und die meisten können unter einem npm-Baum gar nicht entstehen — sie stehen dort, damit die Regel mechanisch bleibt statt von einem Urteil über den „realistischen" Fall abzuhängen. `.vscode/` ist der einzige mit realem Anlass: VS Code legt dort `.json` ab, und `frontend/.gitignore` nennt `.vscode/extensions.json` namentlich. |

Der Geltungsbereich wird **nicht** durch die Aufrufzeile allein bestimmt, sondern durch Konfigurationsdateien (`/.prettierignore`, `[tool.ruff.format] exclude`, `[tool.ruff] extend-exclude`). Dadurch sind der lokale Befehl und die CI-Prüfung zwangsläufig deckungsgleich — sie können nicht auseinanderlaufen, weil sie denselben Geltungsbereich aus derselben Quelle lesen.

Nach dieser Entscheidung gibt es **keinen** handgeschriebenen Quelltextbaum des Repositorys mehr ohne Formatzusicherung. Ohne Zusicherung bleibt allein Markdown — dort ausdrücklich gewollt.

**Berichtigung einer früheren Messung.** In einem Zwischenstand dieser Entscheidung stand, `e2e/` benutze Semikolons am Anweisungsende und die Aufnahme des Baums sei deshalb ein Stilwechsel. Das war falsch. Die Zahl (28 Import-Zeilen mit `;`) stammte aus einem rekursiven `grep` über `e2e/`, das `e2e/node_modules` mit einschloss. Über `git ls-files` gemessen tragen **zwei** Zeilen im ganzen Baum ein abschließendes Semikolon, und beide stehen in Blockkommentaren (`frontend/src` hat zur Gegenprobe acht). `e2e/` ist im selben Hausstil geschrieben wie das Frontend; die Aufnahme ist kein Stilwechsel, sondern dieselbe Festschreibung wie dort. Der gemessene Diff bestätigt das: +124/−107 Zeilen, überwiegend nachgezogene Zeilenumbrüche und Komma am Ende mehrzeiliger Argumentlisten.

### 10. Die einzige inhaltliche Anpassung, die die Formatierung erzwingt

`frontend/src/designSystem.contract.test.ts` führt Freigabelisten, deren Einträge **wörtliche Ausschnitte aus Quellzeilen** sind. Ein Eintrag spannt über eine Quellzeile, die heute 110 Zeichen lang ist:

```
snippet: "aspect-square overflow-hidden rounded-md', isRejected && 'opacity-40'"
```

Prettier bricht diese Zeile in `frontend/src/components/PhotoCard.tsx:83` um (`cn(` über drei Zeilen), und der Ausschnitt findet sich danach auf keiner einzelnen Zeile mehr. Der Test schlägt zweifach an: "nicht freigegeben" für den neuen Fundort und "verwaiste Freigabe ohne Fundstelle" für den alten Eintrag.

Das ist **die einzige** Stelle im gesamten Repository, an der die Durchformatierung eine inhaltliche Nachführung erzwingt. Die Nachführung ist eine Zeile: der Ausschnitt wird auf den Teil verkürzt, der nach dem Umbruch auf einer Zeile steht (`isRejected && 'opacity-40'`); die Begründung des Eintrags bleibt unverändert.

Sie gehört in denselben Pull Request wie die Durchformatierung. Sie dort herauszuhalten hieße, einen Pull Request mit rotem CI zu mergen — die Abmachung, dass CI nach **jedem** Merge grün ist, wiegt schwerer als die Reinheit des Diffs. Im Pull Request wird sie als **eigener Commit** geführt, damit sie im mechanischen Rest nicht untergeht.

**Vier weitere Stellen derselben Gefahrenklasse wurden geprüft und sind nachweislich unberührt** — sie laufen im `e2e`-Job und im Frontend-Prüfsatz quer über Baumgrenzen hinweg:

| Stelle | liest | Ergebnis |
|---|---|---|
| `e2e/tests/toolchain.spec.ts:126` | `backend/src/photosort/demo_state.py`, `/^CONFIRM_LITERAL = "([^"]+)"$/m` | Datei wird formatiert, die Zeile nicht (Modulkonstante in Spalte 0) |
| `e2e/tests/toolchain.spec.ts:177` | dieselbe Datei, `/^DEMO_PROJECT_PREFIX = "([^"]+)"$/m` | ebenso unverändert |
| `e2e/tests/toolchain.spec.ts:306` | `frontend/src/auth/token.ts`, `/^const TOKEN_STORAGE_KEY = '([^']+)'$/m` | Datei byte-gleich; das Muster verlangt **einfache** Anführungszeichen, die `singleQuote: true` erhält |
| `frontend/penpot/payload.test.ts:1110` | `e2e/lib/viewports.ts`, zeilenweise Schlüsselnamen | Datei byte-gleich |

Diese vier sind der Grund, warum eine Formatierungsstory nicht mit "Formatieren ist verhaltenserhaltend" abgehakt werden darf: Es gibt in diesem Repository Zusicherungen, die an der **Zeilenstruktur fremden Quelltexts** hängen, und drei davon laufen im teuersten CI-Job.

### 11. Die Prüfung sitzt in den bestehenden CI-Jobs, nicht in einem eigenen

| Job | neuer Schritt | Position |
|---|---|---|
| `backend` | `ruff format --check --output-format=github .` | unmittelbar vor `Lint (ruff)` |
| `demo-scripts` | `ruff format --check --output-format=github .` | unmittelbar vor `Lint (ruff)` |
| `frontend` | `npm run format:check` | unmittelbar vor `Lint` |
| `e2e` | `npm run format:check` | unmittelbar vor `Type check (tsc)` |

Kein eigener `formatierung`-Job. Gründe:

- **Kosten null.** Jeder der vier Jobs hat das passende Werkzeug nach seinem Installationsschritt bereits liegen. Ein eigener Job müsste Python **und** Node einrichten und beide Werkzeuge ein zweites Mal installieren, um dasselbe zu prüfen.
- **Kein neuer Required Status Check.** Ein neuer Job-Name müsste von Hand in `required_status_checks.contexts` der Branch Protection nachgetragen werden, sonst blockiert er nicht (ADR [`0064`](./0064-pr-titel-pruefung-eigener-blockierender-workflow.md), Abschnitt 6). Als Schritt innerhalb der vier bestehenden Jobs ist die Prüfung ab dem Merge blockierend, ohne dass Daniel etwas einstellen muss.
- **Fehlt früh.** Der Schritt steht jeweils vor Lint/Typprüfung/Test und damit vor allem Teuren.

Die Stelle im `e2e`-Job ist die früheste, an der die Prüfung überhaupt laufen kann: Sie braucht `node_modules`, steht also hinter `npm ci`/`npm audit signatures`. Alles davor sind statische Nachweise, die in Sekunden laufen; alles dahinter ist teuer (Chromium-Installation, Image-Bau, Prüfstack, Seeding). Der Job begründet diese Position bereits selbst für die Typprüfung ("bewusst vor den teuren Schritten … er kostet Sekunden") — die Formatprüfung bekommt denselben Platz.

`--output-format=github` (seit `ruff` 0.16.0 für den Formatierer verfügbar) schreibt die abweichenden Stellen als GitHub-Annotationen direkt an die Zeile im Diff.

### 12. Ein Befehl zum Formatieren — und ausdrücklich kein Automatismus

`scripts/format.sh` formatiert das ganze Repository in einem Aufruf: `ruff format` in `backend/` und `scripts/`, `npm run format` in `frontend/` und `e2e/`. Das folgt dem im Verzeichnis etablierten Muster (`render-diagrams.sh`, `fetch-label-embedder-model.sh`, `merge-main-into-branch.sh`): ein Handgriff, der mehrere Bäume betrifft, ist ein Shell-Skript unter `scripts/`.

Das Skript enthält **keine** Stiloptionen und **keine** Dateilisten — es ruft die Werkzeuge mit ihrer jeweiligen Konfiguration auf und ist damit reine Bequemlichkeit, keine zweite Quelle der Wahrheit. Zwei Vorbedingungen prüft es aber, je Baum, und bricht sonst mit einer Meldung ab, die sagt was zu tun ist:

- **`ruff`-Version:** Es **liest** den Pin aus der `pyproject.toml` des jeweiligen Baums (kein zweiter Ort, an dem die Zahl steht) und vergleicht ihn mit dem, was das aufgerufene `ruff --version` meldet. Das fängt genau den Fall ab, der heute im Repository real vorliegt — eine `.venv` mit einer älteren Version, die einen Diff erzeugt, den CI nicht bestätigt.
- **`node_modules`:** fehlt es in `frontend/` oder `e2e/`, bricht das Skript mit dem Hinweis auf `npm ci` ab, statt einen halb formatierten Baum zu hinterlassen. Die Prettier-Version selbst braucht keine Gegenprobe: `npm ci` installiert genau das, was im Lockfile steht.

**Es entsteht keine eingecheckte Datei, die Formatierung bei einer Dateiänderung oder einem Commit auslöst.** Kein Git-Hook, kein `lefthook`/`husky`/`simple-git-hooks`/`pre-commit`, keine Editor- oder Agenten-Hook-Konfiguration im Repository, kein `prepare`/`postinstall`-Skript, das einen Hook installiert.

Der Grund ist derselbe, aus dem die Prüfung in CI sitzt: Ein Hook, der beim Commit still Dateien umschreibt, verändert einen Stand, den der Entwickler gerade geprüft hat — bei einem Agenten-Lauf heißt das, dass der committete Inhalt nicht mehr der ist, gegen den die Tests liefen. Eine Prüfung, die **meldet** statt zu verändern, lässt die Kontrolle beim Aufrufer.

Diese Abwesenheit wird mechanisch gehalten, nicht nur dokumentiert: ein Wächtertest unter `scripts/tests/` (CI-Job `demo-scripts`), im Muster der dortigen Nachbartests — Suchraum über `git ls-files`, mit Gegenprobe und Selbstschutz gegen einen leeren Suchraum. Die Abwesenheit einer Datei ist die einzige Zusage dieser Story, die von einem Lauf, der sie bricht, nicht bemerkt würde; ein Test ist hier keine Zugabe, sondern die einzige wirksame Form.

## Begründung

- **`ruff format` statt Black:** dasselbe Werkzeug, dieselbe Konfigurationsdatei, dieselbe Zeilenbreite, kein zusätzlicher Installationsschritt. Das Ergebnis ist Black-kompatibel.
- **Prettier statt oxfmt:** Eine verbindliche, CI-blockierende Regel darf nicht auf einem 0.x-Werkzeug mit unvermessener CSS-/JSON-Ausgabe und fehlender Datei-Ignore-Direktive stehen. Der spätere Wechsel kostet einen Durchformatier-Diff — nicht mehr als diese Einführung.
- **Beide TypeScript-Bäume, eine Konfiguration in der Wurzel:** `e2e/` ist im selben Hausstil geschrieben wie das Frontend (gemessen), der Diff ist klein, und danach hat kein handgeschriebener Baum mehr eine Lücke. Die Wurzel-Ablage ist keine Bequemlichkeit, sondern das, was Prettiers Auflösungsverhalten trägt (aufwärts für die Konfiguration, nicht aufwärts für die Ignore-Datei — beides gemessen).
- **Exakte Fixierung, vierfach, per Test gekoppelt:** Belegt durch drei verschiedene `ruff`-Versionen in drei lokalen Umgebungen desselben Repositorys unter derselben `>=0.7`-Angabe. Die Duplikation ist unvermeidbar, solange die vier Bäume getrennt installierbar bleiben; also wird sie gehalten statt versteckt.
- **`printWidth` 100 = `line-length` 100:** Eine Zahl für das ganze Projekt. Zwei Breiten wären eine Regel, die man nachschlagen muss.
- **E501 mit weiterer Grenze statt abgeschaltet:** Der Formatierer übernimmt die Zeilenbreite für alles, was er umbrechen kann. Was übrig bleibt — lange Kommentare und Docstrings — ist genau das, was PhotoSorts Code massenhaft enthält und wofür E501 der einzige Wächter ist.
- **`alembic/versions` formatiert, nicht gelintet:** Die beiden Ausschlüsse hatten nie denselben Grund; sie standen nur zufällig in derselben Zeile.
- **Prüfung in bestehenden Jobs:** kostenlos, sofort blockierend, kein Einstellungsschritt außerhalb des Codes.
- **Kein Hook:** Ein Werkzeug, das beim Commit still schreibt, entzieht dem Aufrufer die Kontrolle über den Stand, den er gerade geprüft hat.

## Konsequenzen

- **Zwei neue Konfigurationsdateien im Wurzelverzeichnis** (`/.prettierrc.json`, `/.prettierignore`), zwei neue devDependencies (`frontend/`, `e2e/`), ein neues Skript unter `scripts/`, je zwei neue Abschnitte in beiden `pyproject.toml`, vier neue CI-Schritte, zwei neue Wächtertests.
- **Eine neue externe Dauerabhängigkeit:** Prettier. Reines Entwicklungswerkzeug, geht in kein Container-Image ein, hat keinen Laufzeitanteil am Produkt.
- **Jeder Agenten-Lauf muss den Formatierbefehl kennen.** Er steht in `docs/setup.md` zusammen mit dem, was bei roter CI-Prüfung zu tun ist. Er wird **nicht** zusätzlich in `CLAUDE.md` oder eine Agenten-Datei geschrieben: eine Regel, die die CI hart durchsetzt und die ein einziger Befehl behebt, braucht keine vierte Textstelle, die driften kann.
- **Nach dem Anlegen einer Migration** (`alembic revision --autogenerate`) muss formatiert werden, sonst ist die CI-Prüfung rot.
- **`git blame` wird für die durchformatierten Zeilen einmalig unbrauchbar.** Das ist der bekannte Preis jeder Durchformatierung und wird getragen. Eine `.git-blame-ignore-revs`-Datei ist **nicht** Teil dieser Entscheidung: Sie wirkt nur bei lokal konfiguriertem `blame.ignoreRevsFile`, GitHubs Weboberfläche berücksichtigt sie automatisch, und ihr Nutzen steht und fällt damit, dass der Durchformatier-Commit tatsächlich sortenrein ist.
- **Abgrenzung:** Markdown bleibt ohne Formatzusicherung (Akzeptanzkriterium) — die Absatzstruktur der Spec- und ADR-Dateien bleibt Handarbeit. Ein anderer handgeschriebener Baum ohne Zusicherung bleibt nicht übrig.
- **`docs/architecture.md` bleibt unberührt:** weder Systemarchitektur noch Datenmodell ändern sich. Betroffen ist allein `docs/setup.md` (Formatierbefehl, Verhalten bei roter Prüfung) — im selben Pull Request wie die Änderung, nicht nachgezogen.
- **Was diese Entscheidung nicht zusichert:** keine Aussage über Code**qualität** — ein durchformatierter Ausdruck kann unlesbar bleiben. Keine Aussage über Namensgebung, Struktur oder Kommentarinhalt. Und keinen Schutz davor, dass jemand die Konfiguration selbst ändert; dagegen hilft nur das Review.
