# 0400 - Einheitliche Code-Formatierung ist verbindlich

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** https://github.com/TheRealKoller/photosort/issues/400

## Ziel

PhotoSort wird vollständig von KI-Agenten entwickelt. Der Code ist heute stilistisch erstaunlich
einheitlich — im Frontend ausnahmslos (844 Import-Zeilen mit einfachen Anführungszeichen, keine
einzige mit doppelten; 882 ohne Semikolon, keine mit), im Backend zu über 97 %. Diese
Einheitlichkeit beruht aber allein darauf, dass jeder Agenten-Lauf den umgebenden Code nachahmt.
Zugesichert ist sie nirgends: 60 von 110 Python-Dateien weichen vom kanonischen Format ab, und für
die Zeilenbreite im Frontend gibt es überhaupt keine Regel (352 Zeilen über 100 Zeichen). Bricht
ein Lauf das Muster, fällt das niemandem auf — und ab dann mischen sich Formatierungsänderungen in
inhaltliche Diffs.

Diese Story macht die Formatierung deshalb zu einer maschinell hergestellten und maschinell
geprüften Eigenschaft, statt sie einer Gewohnheit zu überlassen. Nutznießer sind Daniel und die
entwickelnden Agenten; für Nutzer von PhotoSort ändert sich nichts.

Der Zeitpunkt ist günstig: Derzeit ist kein Pull Request offen, und die Branches mit noch nicht
übernommener Arbeit betreffen je nur wenige Code-Dateien. Je später die einmalige
Durchformatierung erfolgt, desto größer wird sie.

Herkunft: abgetrennt beim Refinement von #398 (früheres Qualitäts-Feedback nach Dateiänderungen).
Dort war Formatierung ursprünglich Teil des Vorschlags und wurde bewusst herausgelöst, weil sie
eine eigenständige Konventionsentscheidung ist.

## User Story

Als Entwickler an PhotoSort (Daniel oder ein entwickelnder Agent) möchte ich, dass die
Formatierung des Codes maschinell hergestellt und geprüft wird, damit ein Diff nur inhaltliche
Änderungen zeigt und die stilistische Einheitlichkeit nicht davon abhängt, dass jeder Lauf den
Nachbarcode richtig nachahmt.

## Akzeptanzkriterien

Die Kriterien tragen die Schärfungen des `test-engineer` (Prüfbarkeit) und die beiden
Ergänzungen des `security-engineer` (K11, K12). Wo die Story ein Kriterium als Wirkung
formuliert hatte, steht jetzt der Befehl, an dem die Wirkung gemessen wird.

- [ ] **K1** Automatische Formatierung gilt für beide Hälften der Codebasis: für Python und für
      die TypeScript-Bäume (TypeScript/TSX, CSS, JSON). Erfasst sind alle vier Bäume —
      `backend/`, `scripts/`, `frontend/`, `e2e/`.
- [ ] **K2** Markdown ist ausdrücklich ausgenommen. Die eingecheckten Spec-, ADR- und
      Dokumentationsdateien behalten ihre handgesetzten Zeilenumbrüche, weil diese dort
      Absatzstruktur tragen. Der Ausschluss ist **aktiv konfiguriert**, nicht bloß Nebenwirkung:
      `[tool.ruff.format] exclude = ["*.md"]` in beiden `pyproject.toml` und `*.md` in
      `/.prettierignore`.
- [ ] **K3** Die TypeScript-Formatierung schreibt den bereits geltenden Stil fest, statt ihn
      umzukehren: einfache Anführungszeichen, keine Semikolons am Anweisungsende, Zeilenbreite
      100 — dieselbe Breite wie im Backend. Damit beschränkt sich der Durchformatier-Diff im Kern
      auf Zeilenumbrüche statt auf einen Stilwechsel.
- [ ] **K4** Die Codebasis wird einmalig vollständig durchformatiert; danach melden die vier
      Läufe `ruff format --check .` (in `backend/`, `scripts/`) und `npm run format:check` (in
      `frontend/`, `e2e/`) je **null** abweichende Dateien. *(Geschärft: "erfasste Datei" ist
      sonst nicht entscheidbar; so hängt das Kriterium an genau den Befehlen, die später in CI
      stehen.)*
- [ ] **K5** Die Formatierung wird in CI geprüft, und eine Abweichung lässt die Prüfung rot
      werden. Eine nur dokumentierte Konvention genügt ausdrücklich nicht: Das Projekt hat
      zweimal festgehalten, dass eine Regel ohne mechanische Prüfung als Rauschen ignoriert wird.
- [ ] **K6** Die verwendeten Formatierer-Versionen sind exakt festgelegt — vier Angaben **und**
      die dazu passende Auflösung in beiden `package-lock.json`. Nachgewiesen durch
      `scripts/tests/test_formatierer_fixierung.py` und durch die Gegenprobe
      `uvx ruff@0.16.4 format --check .`. *(Geschärft: "lokal und in CI dasselbe Ergebnis" ist
      eine Wirkung, kein Prüfgegenstand; die Lockfile-Auflösung ist das, was CI tatsächlich
      installiert.)*
- [ ] **K7** Die bestehenden Lint- und Typprüfungen laufen nach der Durchformatierung unverändert
      grün: `ruff check`, `mypy --strict`, `tsc` und `npm run build` sind grün; `oxlint` meldet 0
      Fehler und **dieselbe Warnungszahl wie vor der Durchformatierung** (gemessen: 10).
      Formatierer und Linter widersprechen sich nicht; wo sie es täten, wird die Linter-Regel
      angepasst, nicht die Formatierung abgeschwächt. *(Geschärft: `oxlint` ist mit Warnungen
      grün — neu entstandene Warnungen fielen sonst niemandem auf.)*
- [ ] **K8** Es entsteht keine eingecheckte Datei, die Formatierung bei einer Dateiänderung oder
      einem Commit automatisch auslöst. Maschinell gefasst: kein verwalteter Pfad trägt einen
      Git-Hook-Namen, keinen Hook-Werkzeug-Konfigurationsnamen, keinen npm-Lebenszyklus-Schlüssel,
      kein Hook-Werkzeug als Abhängigkeit und keine Editor-/Agenten-Konfiguration mit
      Formatier-Auslöser; gehalten durch `scripts/tests/test_keine_automatische_formatierung.py`.
      *(Verbindliche Randbedingung, übernommen aus #398: eine im Repository liegende
      Automatisierung wirkte ab dem Merge auf jede Session, auch auf fremde und automatisiert
      laufende. Geschärft: "keine Datei, die X tut" ist nicht maschinell entscheidbar, die vier
      Musterfamilien sind es.)*
- [ ] **K9** `docs/setup.md` nennt `scripts/format.sh` wörtlich und sagt, was zu tun ist, wenn die
      CI-Formatprüfung rot wird. *(Geschärft: ein wörtlicher Pfad ist prüfbar, "nennt den Befehl"
      nicht. Bewusst **ohne** Wächtertest — eine Doku-Bindung wäre hier Formulierungspolizei.)*
- [ ] **K10** Die einmalige Durchformatierung erfolgt getrennt von jeder inhaltlichen Änderung,
      damit sie in der Historie als reine Formatierung erkennbar bleibt und einen inhaltlichen
      Diff nicht überdeckt.
- [ ] **K11** `/.prettierignore` spiegelt die `.gitignore`-Einträge **vollständig und
      mechanisch**: jeden Eintrag, der unterhalb von `frontend/` oder `e2e/` greift und eine von
      Prettier unterstützte Endung treffen kann — ohne Ausnahmeliste und ohne Ermessen darüber,
      welcher Fall "realistisch" auftritt. Sicherheitstragend und deshalb zusätzlich namentlich:
      `e2e/.auth/`, `e2e/artifacts/`, `e2e/test-results/`, `e2e/playwright-report/`,
      `e2e/scratch/`. Begründung: `--ignore-path` ersetzt die `.gitignore`-Auswertung
      vollständig, und `e2e/.auth/state.json` trägt ein 30 Tage gültiges, nicht widerrufbares
      JWT. Gehalten durch `scripts/tests/test_prettierignore_spiegelung.py`, der seine Erwartung
      genau deshalb mechanisch aus den `.gitignore`-Dateien ableiten kann. *(Neu,
      `security-engineer`; auf die vollständige Spiegelung erweitert am 2026-09-11, Entscheidung
      Daniels — siehe Abschnitt 4.)*
- [ ] **K12** Die Durchformatierung wird vor dem Eröffnen von PR A durch einen
      **Reproduktionsnachweis** abgenommen: Auf dem Elternstand des Durchformatier-Commits
      erzeugt ein Lauf der fixierten Werkzeuge einen byte-gleichen Baum
      (`git diff --quiet <chore-commit>` endet mit 0). Das ist die Bedingung, unter der auf das
      Copilot-Review für PR A verzichtet wird. *(Neu, `security-engineer`.)*

## Datenmodell-Bezug

Keiner. Die Story ändert ausschließlich die Textform bestehender Quelldateien sowie
Werkzeug-, CI- und Dokumentationsdateien. Es entsteht, entfällt und verändert sich keine
Entität, keine Tabelle und keine Migration; `docs/architecture.md` bleibt unberührt.

## Architektur / Umsetzung

Die Entscheidungen dieses Abschnitts sind in ADR
[`0080`](../decisions/0080-maschinelle-formatierung-ruff-format-und-prettier.md) festgehalten und
dort mit Messwerten belegt. Hier steht, was daraus konkret zu tun ist.

### 1. Die gewählten Werkzeuge

**Python: `ruff format`** in beiden Bäumen (`backend/`, `scripts/`). `ruff` ist bereits als Linter
im Einsatz, `line-length = 100` steht bereits in beiden `pyproject.toml`, beide CI-Jobs
installieren es ohnehin. Kein Black.

**TypeScript: Prettier 3.9.6** in beiden Bäumen (`frontend/`, `e2e/`). Nicht `oxfmt` — das steht
bei 0.67.0, hat kein 1.0 und keinen angekündigten Termin, seine "100 % Prettier-Konformität" gilt
ausdrücklich nur für JS/TS und nicht für CSS/JSON, es kennt keine Datei-weite Ignore-Direktive,
und `sortPackageJson` ordnet standardmäßig `package.json` um. Eine CI-blockierende Regel darf
nicht auf einem Werkzeug stehen, dessen Ausgabe sich noch bewegt. Der spätere Wechsel auf `oxfmt`
nach dessen 1.0 kostet eine Konfigurationsänderung plus einen Durchformatier-Diff — derselbe
Handgriff wie diese Einführung, also kein Grund, heute darauf zu warten.

### 2. Python-Konfiguration (identisch in `backend/pyproject.toml` und `scripts/pyproject.toml`)

```toml
[tool.ruff.format]
exclude = ["*.md"]

[tool.ruff.lint.pycodestyle]
max-line-length = 110
```

**`exclude = ["*.md"]` ist nicht optional.** `ruff` formatiert seit 0.16.0 standardmäßig
Python-Codeblöcke *innerhalb* von Markdown-Dateien — gemessen: `ruff format .` schreibt in einer
`probe.md` `x   =    1` zu `x = 1` um. Heute liegt unter `backend/` und `scripts/` keine
`.md`-Datei, der Fall ist also latent; er tritt ein, sobald jemand dort eine anlegt. Das
Akzeptanzkriterium "Markdown ist ausgenommen" verlangt die aktive Konfiguration.

**`max-line-length = 110` löst den einzigen echten Formatierer/Linter-Konflikt im Bestand.**
`backend/tests/test_config.py:258` beginnt einen Docstring mit einem Anführungszeichen. Der
Formatierer schiebt zur Entschärfung ein Leerzeichen ein und bringt die Zeile damit selbst auf
101 Zeichen; ein `# noqa` ist unmöglich, weil die beanstandete Zeile in einem Stringliteral liegt.
`line-length = 100` bleibt unverändert die Zielbreite des Formatierers, E501 schlägt erst ab 111
an. Verifiziert: `ruff check` ist damit auf dem vollständig formatierten Backend grün,
`mypy --strict` ebenfalls.

E501 wird **nicht** abgeschaltet (die zweite von `ruff` genannte Möglichkeit): es ist im
Repository der einzige Wächter gegen überlange Kommentare und Docstrings — genau die Textsorte,
die PhotoSorts Code massenhaft enthält und die der Formatierer grundsätzlich nicht umbricht. Damit
ist auch das Akzeptanzkriterium erfüllt: angepasst wird die Linter-Grenze, nicht die Formatierung.

### 3. `backend/alembic/versions`: formatiert, weiterhin nicht gelintet

Der heutige Eintrag `extend-exclude = ["alembic/versions"]` steht unter `[tool.ruff]` und gilt
damit für **beide** Werkzeuge. Er wird auf den Linter verengt:

```toml
# ENTFERNEN aus [tool.ruff]:  extend-exclude = ["alembic/versions"]
[tool.ruff.lint]
exclude = ["alembic/versions/*"]
```

**Achtung, stille Falle:** Das schlichte `exclude = ["alembic/versions"]` unter `[tool.ruff.lint]`
wirkt **nicht** — gemessen bleiben alle 125 Befunde stehen. Erst der Glob `alembic/versions/*`
schließt aus. Unter `[tool.ruff]` greift dieselbe Schreibweise dagegen.

Der Lint-Ausschluss bleibt, weil von Alembic erzeugte Migrationen `Union[str, Sequence[str], None]`
(UP007), veraltete `typing`-Importe (UP035) und unsortierte Importe (I001) tragen. Der Formatierer
hat dagegen keine Meinung, die generierter Code verletzen könnte; er normalisiert nur — und die
linksbündige Einrückung der Autogenerate-Ausgabe wird dadurch zu normalem Projekt-Python.

**Verifiziert:** Nach dem Formatieren aller 22 Migrationsdateien behält jede die
`revision: str = "..."`-Zeile in der Form, die `backend/tests/test_migration_chain.py` zeilenweise
sucht (22 von 22). Das ist die einzige Stelle im Repository, die Migrations-Quelltext als Text
liest.

**Folge für den Alltag:** `alembic revision --autogenerate` erzeugt ab sofort jedes Mal eine
unformatierte Datei. Der Formatierlauf gehört danach zum Anlegen einer Migration.

### 4. Prettier-Konfiguration: eine Datei in der Wurzel, für beide TypeScript-Bäume

`frontend/` und `e2e/` tragen denselben Stil. Eine Kopie der Konfiguration je Baum wäre eine
zweite Quelle der Wahrheit für dieselbe Regel. Am echten Baum gemessen, wo Prettier was sucht:

| Datei | wird gefunden | Folge |
|---|---|---|
| `/.prettierrc.json` | **ja**, aufwärts vom Pfad der Datei | kein Flag nötig |
| `/.prettierignore` | **nein**, nur relativ zum Arbeitsverzeichnis | `--ignore-path ../.prettierignore` in beiden Aufrufen |

Verifiziert: `prettier --find-config-path src/App.tsx` aus `frontend/` und
`--find-config-path lib/auth.ts` aus `e2e/` liefern beide `../.prettierrc.json`. Ohne
`--ignore-path` meldet dagegen ein Lauf aus `e2e/` eine dort abgelegte `PROBE.md` als abweichend,
obwohl `*.md` in der Wurzel-Ignore-Datei steht.

Zwei weitere gemessene Eigenschaften, die die Ignore-Datei bestimmen:

- **`--ignore-path` ersetzt die Vorgabe vollständig, es ergänzt sie nicht.** Verifiziert mit einer
  Probe, die nur eine lokale `.gitignore` erfasst: ohne Flag ausgeschlossen, mit
  `--ignore-path ../.prettierignore` wieder sichtbar, mit beiden Pfaden erneut ausgeschlossen. Die
  Wurzel-Ignore-Datei muss deshalb **selbsttragend** sein — auf `frontend/.gitignore` ist kein
  Verlass mehr. `node_modules` bleibt trotzdem ausgeschlossen (fest in Prettier verdrahtet, kein
  Ignore-Datei-Mechanismus; verifiziert).
- **Muster sind relativ zum Verzeichnis der Ignore-Datei, nicht zum Arbeitsverzeichnis.**
  Verifiziert: `e2e/lib/` schließt `lib/auth.ts` auch bei einem Lauf aus `e2e/` heraus aus. In der
  Wurzeldatei stehen also repo-weite Pfade, so wie man sie liest.

`/.prettierrc.json` (neu):

```json
{
  "singleQuote": true,
  "semi": false,
  "printWidth": 100
}
```

Alle drei müssen gesetzt werden — Prettiers Voreinstellungen sind jeweils das Gegenteil (`false`,
`true`, `80`). `trailingComma: "all"` und `arrowParens: "always"` bleiben auf der Voreinstellung,
weil sie den Bestand bereits treffen. `printWidth: 100` ist bewusst dieselbe Zahl wie
`line-length` im Backend: eine Zeilenbreite im ganzen Projekt.

`/.prettierignore` (neu) — jeder Eintrag mit `#`-Kommentar begründet:

```
*.md
package-lock.json
dist/
node_modules/
design/
e2e/.auth/
e2e/artifacts/
e2e/test-results/
e2e/playwright-report/
e2e/scratch/
frontend/dist-ssr/
.vscode/
__pycache__/
*.egg-info/
build/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.vite/
logs/
photo-cache/
.idea/
*.ntvs*
```

`*.md` ist die aktive Umsetzung des Akzeptanzkriteriums (verifiziert: Prettier erfasst `*.md` im
Verzeichnislauf standardmäßig; mit dem Eintrag nicht mehr). `package-lock.json` ohne Pfadpräfix,
damit es in **jedem** Baum greift — npm schreibt die Datei bei jeder Installation neu. `dist/` ist
tragend, seit die `.gitignore`-Vorgabe durch `--ignore-path` entfällt. `design/` steht für die
Penpot-Nutzlast (siehe 6.) und greift nur bei einem Lauf aus der Wurzel, gehört aber hierher,
damit die Absicht an einer Stelle nachlesbar ist.

**Die letzten sechs Einträge sind ein Sicherheitsbefund, keine Aufräumarbeit (K11).** Weil
`--ignore-path` die Vorgabe *ersetzt*, entfällt die `.gitignore`-Auswertung — und Prettier steigt
auch in Punktverzeichnisse ab. Gemessen: Ein lokaler Lauf aus `e2e/` erfasst ohne diese Einträge
`e2e/.auth/state.json` mit dem gespeicherten, 30 Tage gültigen und nicht widerrufbaren JWT und
**schreibt die Datei neu**; bei einem Parse-Fehler (etwa aus einem abgebrochenen Lauf) gibt
Prettier einen Code-Frame **mit dem Dateiinhalt** aus, in dem das Token wörtlich steht. Dasselbe
gilt für die Playwright-Artefakte, deren Traces Netzwerkinhalte samt Login-Request und
`localStorage`-Zustand tragen. CI ist nicht betroffen (dort existieren die Verzeichnisse zum
Prüfzeitpunkt noch nicht) — lokal läuft aber gerade der **schreibende** Befehl.

**Daraus folgt eine Dauerregel, die über diese sechs Einträge hinausgeht:** Solange
`--ignore-path` gesetzt ist, ist `/.prettierignore` die einzige Ausschlussquelle. Jeder
`.gitignore`-Eintrag, der unterhalb von `frontend/` oder `e2e/` greift und eine von Prettier
unterstützte Endung treffen kann, muss dort gespiegelt werden — auch jeder künftige. Weil genau
diese Zusicherung still bricht (lokal fällt sie nur als "eine Datei mehr formatiert" auf, in CI
gar nicht), hält sie ein dritter Wächtertest, `scripts/tests/test_prettierignore_spiegelung.py`.
Die Regel steht zusätzlich dauerhaft im Sicherheitskonzept.

**Die Spiegelung ist vollständig, nicht nach Ermessen — und die Liste stammt aus einer Messung**
(Review-Fund und Entscheidung Daniels, 2026-09-11). Ein erster Entwurf dieses Abschnitts führte
nur die elf oberen Einträge; nachgemessen erfasste Prettier darüber hinaus **vierzehn** weitere
Kandidaten. Erhoben wurde das nicht durch Nachdenken, sondern durch je ein `PROBE.json` in jedem
in Frage kommenden Verzeichnis unter `frontend/`, gefolgt von
`prettier --ignore-path ../.prettierignore --check .`:

```bash
cd frontend && for d in build .venv .vite .mypy_cache htmlcov .pytest_cache logs .idea \
    __pycache__ .ruff_cache probe.egg-info photo-cache .vscode; do
  mkdir -p "$d" && printf '{  "a":   1 }\n' > "$d/PROBE.json"; done
./node_modules/.bin/prettier --ignore-path ../.prettierignore --check . 2>&1 | grep PROBE
```

Zwei Erkenntnisse daraus, die den nächsten Leser davor bewahren, denselben Weg zu gehen:

- **Die Frage nach der Dateiendung trägt die Entscheidung nicht — die nach dem Verzeichnis trägt
  sie.** Ein Eintrag wie `logs` oder `.idea` sieht nach einer Endung aus, die Prettier nicht
  kennt, trifft aber ein *Verzeichnis*, in dem eine `.json` liegen kann. Wer nach Endungen
  filtert, findet nur `.vscode/` und hält die Spiegelung fälschlich für vollständig — genau
  dieser Fehler ist im Review einmal passiert. `*.ntvs*` ist der einzige Datei-Glob der Liste,
  weil sein nachgestelltes `*` ihn `foo.ntvs.json` treffen lässt; alle übrigen (`*.log`,
  `*.local`, `*.suo`, `*.sln`, `*.sw?`, `.DS_Store`, `.coverage`) schließen den Dateinamen nach
  hinten ab und können eine unterstützte Endung strukturell nicht treffen.
- **Ein wörtlich aus einer `.gitignore` übernommenes Muster kann wirkungslos sein.**
  `frontend/.gitignore` schreibt `.vscode/*`; dieser Schrägstrich *in der Mitte* bindet das
  Muster an das Verzeichnis der Ignore-Datei, hier also an die Repository-Wurzel, und ließe
  `frontend/.vscode/` unberührt. Nur `.vscode/` — Schrägstrich ausschließlich am Ende — greift
  auf jeder Ebene. Nachgemessen mit vier Varianten. Ebenso nachgemessen: Der Wiedereinschluss
  `!.vscode/extensions.json` bleibt wirkungslos, weil gitignore-Semantik eine Datei unterhalb
  eines ausgeschlossenen Verzeichnisses nicht wieder einschließen kann; er wird deshalb nicht
  gespiegelt.

Die meisten der nachgetragenen Einträge können unter `frontend/` oder `e2e/` heute gar nicht
entstehen — es sind Artefakte der Python-Werkzeugkette (`.venv/`, `__pycache__/`, `.mypy_cache/`,
`.pytest_cache/`, `.ruff_cache/`, `htmlcov/`, `*.egg-info/`) oder Bausteine der Vite-Vorlage
(`logs`, `.idea/`, `*.ntvs*`). Sie stehen trotzdem dort, und **das ist der Punkt:** Die
Asymmetrie trägt die Entscheidung. Ein überflüssiger Eintrag kostet eine Zeile in einer Datei,
die ohnehin nur Ausschlüsse führt; ein fehlender kostet eine still umgeschriebene, unversionierte
lokale Datei — bei `e2e/.auth/` war genau das ein Sicherheitsbefund. Und nur die vollständige
Liste lässt `test_prettierignore_spiegelung.py` seine Erwartung mechanisch aus den
`.gitignore`-Dateien ableiten; jede Ausnahmeliste wäre eine Ermessensentscheidung, die später
jemand ohne Kenntnis des Anlasses neu treffen müsste.

Die Python-Hälfte ist davon nicht betroffen: `ruff` behält `respect-gitignore = true`, und
`[tool.ruff.format] exclude` **ergänzt** die Vorgabe, statt sie zu ersetzen. `.env` ist für beide
Werkzeuge unerreichbar — Prettier wählt im Verzeichnislauf nur Dateien mit unterstützter Endung,
für `.env` gibt es keinen Parser.

**Nebennutzen der Wurzel-Ablage:** Ein versehentliches `npx prettier --write .` aus dem
Repository-Wurzelverzeichnis findet die Ignore-Datei über die Vorgabe und lässt die
Markdown-Dateien in Ruhe. Läge sie unter `frontend/`, wäre dieser Griff ein Massenschaden an
Specs und ADRs.

**Falle:** Ein `"prettier"`-Schlüssel in einer `package.json` **überschattet** die
Wurzel-Konfiguration still. Verifiziert: `--find-config-path` meldet dann `package.json` statt
`../.prettierrc.json`, ohne Warnung. Die Abwesenheit dieses Schlüssels wird deshalb mechanisch
gehalten (siehe 5.).

npm-Skripte, in `frontend/package.json` und `e2e/package.json` **wortgleich**:

```json
"format": "prettier --ignore-path ../.prettierignore --write .",
"format:check": "prettier --ignore-path ../.prettierignore --check ."
```

Beide Skripte lesen denselben Geltungsbereich aus derselben Konfiguration — lokaler Befehl und
CI-Prüfung können nicht auseinanderlaufen.

### 5. Versionsfixierung: vier Stellen, mechanisch gekoppelt

| Werkzeug | Datei | heute | künftig |
|---|---|---|---|
| `ruff` | `backend/pyproject.toml` | `ruff>=0.7` | `ruff==0.16.4` |
| `ruff` | `scripts/pyproject.toml` | `ruff>=0.7` | `ruff==0.16.4` |
| `prettier` | `frontend/package.json` + `package-lock.json` | — | `"prettier": "3.9.6"` |
| `prettier` | `e2e/package.json` + `package-lock.json` | — | `"prettier": "3.9.6"` |

**Warum `0.16.4` und nicht der neueste Stand** (Entscheidung Daniels, 2026-09-11): `0.16.7` war
zum Entscheidungszeitpunkt einen Tag alt. Genau dieses Fenster ist das, in dem eine
kompromittierte Veröffentlichung am wahrscheinlichsten noch unentdeckt ist — und `ruff` landet
über `[dev]` auf dem Entwicklerrechner, auf dem auch `gh`-Token und Repository-Schreibzugriff
liegen. `0.16.4` ist länger verfügbar, lag bereits lokal installiert vor und ist zugleich die
Version, mit der ADR 0080 ihre Bestandsmessungen gemacht hat: Pin und Messung decken sich damit.

Dass `>=0.7` nichts fixiert, ist am Bestand messbar: in den drei real vorhandenen lokalen
Umgebungen liefen drei verschiedene Versionen (`0.16.1` in `scripts/.venv`, `0.16.2` in
`backend/.venv`, `0.16.4` auf dem PATH). `ruff` darf den Stable Style bei Minor-Bumps ändern;
Prettier sagt über sich selbst, dass sogar ein Patch-Release die Ausgabe verändern kann. Beide
Angaben müssen exakt sein, in allen vier Zeilen ohne Caret.

**Wie das Auseinanderdriften verhindert wird.** Nicht durch Vermeidung der Duplikation — sie ist
unvermeidbar, solange `backend/` und `scripts/` getrennte Python-Projekte mit getrennten CI-Jobs
sind und `frontend/`/`e2e/` getrennte npm-Projekte mit getrennten Lockfiles. Die beiden
`ruff`-Pins bräuchten ohnehin einen Wächter; ein Mechanismus, der **alle vier** Stellen erfasst,
ist besser als ein Sonderweg, der nur die Prettier-Hälfte strukturell löst. Also: ein Wächtertest
`scripts/tests/test_formatierer_fixierung.py` (CI-Job `demo-scripts`) mit vier Zusicherungen:

1. beide `pyproject.toml` nennen dieselbe `ruff`-Version,
2. beide `package.json` nennen dieselbe `prettier`-Version,
3. alle vier Angaben sind exakt (kein `>=`, `~`, `^`, `*`),
4. keine `package.json` im Repository trägt einen `"prettier"`-Schlüssel (die Überschattungsfalle
   aus 4.).

Der `test-engineer` hat vier weitere Zusicherungen vorgeschlagen, die in denselben Test gehören —
sie schließen Lücken derselben Fehlerklasse und stehen ausgearbeitet im Abschnitt
`## Teststrategie`: Exaktheit **positiv je Ökosystem** statt als Zeichen-Blacklist (eine
Blacklist ließe den nackten Eintrag `ruff` ohne Operator und das npm-`"latest"` durch); genau
**eine** Prettier-Konfigurationsquelle im ganzen Repository (der `"prettier"`-Schlüssel ist nur
eine von dreizehn, die die Wurzeldatei still überschatten, und `ruff.toml` hätte gegenüber
`pyproject.toml` ebenso lautlos Vorrang); die **Lockfile-Auflösung** trägt denselben Wert wie die
Deklaration (`npm ci` installiert, was im Lockfile steht); und beide npm-Skripte sind wortgleich
und tragen `--ignore-path ../.prettierignore` (fällt das Flag in einem Baum weg, erfasst dieser
Lauf plötzlich Markdown — still).

Ein **dritter** Wächtertest, `scripts/tests/test_prettierignore_spiegelung.py`, hält die
Spiegelungspflicht aus 4. (K11).

**Verworfen: Prettier nur in `frontend/` installieren und `../e2e` mitformatieren.** Spart genau
eine Fixierung, macht aber das Frontend-Paket zum Eigentümer eines fremden Baums, und wer nur
`e2e/` installiert hat, könnte nicht mehr formatieren. Der Wächtertest wäre trotzdem nötig.

**Verworfen: eine `package.json` im Wurzelverzeichnis.** Löste die Duplikation strukturell,
erzwänge aber einen eigenen CI-Job (`npm ci` in der Wurzel macht kein bestehender Job) — und ein
neuer Job-Name muss von Hand in die Branch Protection nachgetragen werden und blockiert bis dahin
nichts (ADR [`0064`](../decisions/0064-pr-titel-pruefung-eigener-blockierender-workflow.md),
Abschnitt 6). Eine Durchsetzung, die erst nach einem manuellen Schritt greift, ist hier die
schlechtere Wahl.

**Falle beim Umsetzen:** Die bestehenden lokalen `.venv` tragen ältere Versionen. Vor dem
Durchformatieren müssen beide Python-Bäume mit dem neuen Pin neu installiert werden
(`uv pip install -e ".[dev]"`), sonst entsteht ein Diff, den CI später nicht bestätigt.
Gegenprobe: `uvx ruff@0.16.4 format --check .` muss dasselbe sagen.

### 6. Geltungsbereich und Ausschlüsse

**Erfasst:** `backend/**/*.py` einschließlich `alembic/versions`; `scripts/**/*.py`;
`frontend/src/**/*.{ts,tsx,css}`, `frontend/penpot/**/*.ts`, `frontend/*.json`,
`frontend/vite.config.ts`, `frontend/index.html`; `e2e/**/*.ts`, `e2e/*.json`. Verifiziert mit der
finalen Aufrufform: der Frontend-Lauf meldet 123 Dateien, alle `.ts`/`.tsx`/`.css` — JSON und HTML
sind bereits konform und erzeugen keinen Diff; der e2e-Lauf meldet 18 Dateien, `tsconfig.json`
ausdrücklich als unverändert.

**Ausgeschlossen:**

- **Alle `*.md`** — Akzeptanzkriterium; handgesetzte Umbrüche tragen dort Absatzstruktur.
- **`design/` vollständig.** `tokens.json` und `icons.json` sind *erzeugt*:
  `frontend/penpot/tokens.test.ts` und `icons.test.ts` schreiben sie per `toMatchFileSnapshot` aus
  `JSON.stringify(x, null, 2)` — ein Formatierer darauf bringt den Snapshot-Test zu Fall. Die vier
  `seed-*.js`/`verify.js` sowie `components.json`/`views.json` sind handgeschriebene Nutzlast,
  über die `frontend/penpot/payload.test.ts` statische AST-Zusicherungen trifft und die als Text
  in eine Penpot-Sitzung eingefügt wird (ADR
  [`0066`](../decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)). Ein Verzeichnis,
  zwei Gründe, eine Regel.
- `package-lock.json` (beide Bäume), `dist/`, `node_modules/` — siehe `.prettierignore`.
- `assets/beispielbilder/`, `*.svg`, `*.tflite`/`*.hdf5`/`*.task`/`*.onnx`,
  `backend/alembic/script.py.mako` — keine von einem der beiden Formatierer behandelte Sprache;
  kein Eintrag nötig.

**Nach dieser Story gibt es keinen handgeschriebenen Quelltextbaum des Repositorys mehr ohne
Formatzusicherung.** Ohne Zusicherung bleibt allein Markdown — dort ausdrücklich gewollt.

### 7. Die einzige inhaltliche Nachführung — und vier geprüfte Beinahe-Fälle

`frontend/src/designSystem.contract.test.ts` führt Freigabelisten, deren Einträge wörtliche
Ausschnitte aus Quellzeilen sind. Ein Eintrag spannt über eine Quellzeile, die heute 110 Zeichen
lang ist. Prettier bricht die zugehörige Zeile in `frontend/src/components/PhotoCard.tsx` um
(`cn(` über drei Zeilen); der Ausschnitt steht danach auf keiner einzelnen Zeile mehr. Der Test
schlägt zweifach an ("nicht freigegeben" für den neuen Fundort, "verwaiste Freigabe ohne
Fundstelle" für den alten Eintrag). Die Nachführung ist eine Zeile: der Ausschnitt wird auf den
Teil verkürzt, der nach dem Umbruch auf einer Zeile steht; die Begründung des Eintrags bleibt
wörtlich unverändert.

Das ist **die einzige** solche Stelle im Repository. Verifiziert auf dem durchformatierten Stand:
1.566 von 1.567 Vitest-Fällen grün (dieser eine rot), `oxlint` exakt dieselben 10 Warnungen und 0
Fehler wie vorher, `tsc -b --noEmit` (Frontend) und `tsc --noEmit` (e2e) grün, `ruff check` grün,
`mypy --strict` grün. Die erzeugten Penpot-Nutzlasten `design/penpot/tokens.json` und `icons.json`
bleiben byte-gleich.

**Vier weitere Stellen derselben Gefahrenklasse — geprüft, nachweislich unberührt.** Sie hängen an
der Zeilenstruktur *fremden* Quelltexts und laufen quer über Baumgrenzen; drei davon im
`e2e`-Job, der lokal ohne vollständigen Docker-Prüfstack nicht läuft und deshalb statisch geprüft
wurde:

| Stelle | liest | Ergebnis |
|---|---|---|
| `e2e/tests/toolchain.spec.ts` (CONFIRM_LITERAL) | `backend/src/photosort/demo_state.py`, zeilenverankertes Muster | Datei wird formatiert, diese Zeile nicht (Modulkonstante in Spalte 0) |
| `e2e/tests/toolchain.spec.ts` (DEMO_PROJECT_PREFIX) | dieselbe Datei | ebenso unverändert |
| `e2e/tests/toolchain.spec.ts` (TOKEN_STORAGE_KEY) | `frontend/src/auth/token.ts` | Datei byte-gleich; das Muster verlangt **einfache** Anführungszeichen, die `singleQuote: true` erhält |
| `frontend/penpot/payload.test.ts` | `e2e/lib/viewports.ts`, zeilenweise Schlüsselnamen | Datei byte-gleich |

Diese vier sind der Grund, warum "Formatieren ist verhaltenserhaltend" hier nicht als Abnahme
genügt. Beim Durchformatieren ist jede davon erneut zu prüfen, falls der Diff von den oben
gemessenen Dateien abweicht.

### 8. CI-Prüfung: Schritte in den bestehenden Jobs, kein eigener Job

| Job in `.github/workflows/ci.yml` | neuer Schritt | Position |
|---|---|---|
| `backend` | `ruff format --check --output-format=github .` | unmittelbar vor `Lint (ruff)` |
| `demo-scripts` | `ruff format --check --output-format=github .` | unmittelbar vor `Lint (ruff)` |
| `frontend` | `npm run format:check` | unmittelbar vor `Lint` |
| `e2e` | `npm run format:check` (`working-directory: e2e`) | unmittelbar vor `Type check (tsc)` |

Kein eigener `formatierung`-Job: Jeder der vier Jobs hat das passende Werkzeug nach seinem
Installationsschritt bereits liegen (Zusatzkosten praktisch null), ein neuer Job-Name müsste von
Hand in `required_status_checks.contexts` nachgetragen werden und blockierte bis dahin nichts
(ADR [`0064`](../decisions/0064-pr-titel-pruefung-eigener-blockierender-workflow.md), Abschnitt 6),
und der Schritt steht jeweils vor allem Teuren.

Die Stelle im `e2e`-Job ist die **früheste, an der die Prüfung überhaupt laufen kann**: sie braucht
`node_modules`, steht also hinter `npm ci`/`npm audit signatures`. Alles davor sind statische
Nachweise in Sekunden; alles dahinter ist teuer (Chromium, Image-Bau, Prüfstack, Seeding). Der Job
begründet genau diese Position bereits selbst für die Typprüfung — die Formatprüfung bekommt
denselben Platz.

`--output-format=github` (seit `ruff` 0.16.0 auch für den Formatierer) schreibt die abweichenden
Stellen als Annotation direkt an die Zeile im Diff.

### 9. Lokaler Befehl: `scripts/format.sh`, und ausdrücklich kein Automatismus

`scripts/format.sh` (neu, ausführbar) formatiert das ganze Repository in einem Aufruf:
`ruff format` in `backend/` und `scripts/`, `npm run format` in `frontend/` und `e2e/`. Das folgt
dem im Verzeichnis etablierten Muster (`render-diagrams.sh`, `fetch-label-embedder-model.sh`,
`merge-main-into-branch.sh`).

Das Skript enthält **keine** Stiloptionen und **keine** Dateilisten — es ruft die Werkzeuge mit
ihrer jeweiligen Konfiguration auf und ist damit reine Bequemlichkeit, keine zweite Quelle der
Wahrheit. Zwei Vorbedingungen prüft es aber je Baum und bricht sonst mit einer Meldung ab, die
sagt, was zu tun ist:

- **`ruff`-Version:** Es **liest** den Pin aus der `pyproject.toml` des jeweiligen Baums (kein
  zweiter Ort, an dem die Zahl steht) und vergleicht ihn mit `ruff --version`. Das fängt genau den
  Fall ab, der heute real vorliegt — eine `.venv` mit älterer Version, die einen Diff erzeugt, den
  CI nicht bestätigt. Die Prüfung läuft für **beide** Python-Bäume getrennt, weil beide eine
  eigene `.venv` haben.
- **`node_modules`:** fehlt es in `frontend/` oder `e2e/`, bricht das Skript mit dem Hinweis auf
  `npm ci` ab, statt einen halb formatierten Stand zu hinterlassen. Für Prettier braucht es keine
  Versions-Gegenprobe: `npm ci` installiert genau das, was im Lockfile steht — das ist die
  Fixierung selbst.

**Es entsteht keine eingecheckte Datei, die Formatierung bei einer Dateiänderung oder einem Commit
auslöst.** Kein Git-Hook, kein `lefthook`/`husky`/`simple-git-hooks`/`pre-commit`, keine Editor-
oder Agenten-Hook-Konfiguration im Repository, kein `prepare`/`postinstall`-Skript, das einen Hook
installiert. Grund: Ein Hook, der beim Commit still Dateien umschreibt, verändert einen Stand, den
der Entwickler gerade geprüft hat — bei einem Agenten-Lauf heißt das, dass der committete Inhalt
nicht mehr der ist, gegen den die Tests liefen. Eine Prüfung, die *meldet* statt zu verändern,
lässt die Kontrolle beim Aufrufer.

**Architektonischer Ort der Prüfbarkeit dieser Abwesenheit:** ein Wächtertest
`scripts/tests/test_keine_automatische_formatierung.py` (CI-Job `demo-scripts`), im Muster der
dortigen Nachbartests — Suchraum über `git ls-files` statt `rglob` (damit nicht verwaltete
Arbeitskopien und Worktrees nicht hineinfallen), mit Gegenprobe und Selbstschutz gegen einen
leeren Suchraum. Die Abwesenheit einer Datei ist die einzige Zusage dieser Story, die von einem
Lauf, der sie bricht, nicht bemerkt würde; ein Test ist hier keine Zugabe, sondern die einzige
wirksame Form.

### 10. Aufteilung auf zwei Pull Requests und Merge-Reihenfolge

Die Abhängigkeit ist wechselseitig und wird in genau dieser Richtung aufgelöst: **die
Konfiguration muss existieren, bevor formatiert wird — und der Code muss formatiert sein, bevor
die Prüfung scharf geschaltet wird.** Daraus folgt zwingend `PR A → PR B`, und daraus folgt, dass
die Konfiguration in PR A liegt. Läge sie in PR B, wäre PR A ein Diff, den niemand nachrechnen
kann — und das Nachrechnen-Können ist die einzige Begründung dafür, auf ein Review zu verzichten.

**PR A — `chore: Codebasis einmalig maschinell durchformatieren (Spec 0400)`**

| Commit | Dateien |
|---|---|
| `docs(spec): Spec 0400 und ADR 0080 anlegen` | `specs/features/0400-einheitliche-code-formatierung.md`, `specs/decisions/0080-maschinelle-formatierung-ruff-format-und-prettier.md`, `specs/architecture/0003-securitykonzept.md` (Dauerregel zur `--ignore-path`-Spiegelung — sie gilt ab PR A, nicht erst ab PR B) |
| `build(format): Formatierer festlegen und Versionen exakt fixieren` | `.prettierrc.json` (neu, Wurzel), `.prettierignore` (neu, Wurzel), `backend/pyproject.toml`, `scripts/pyproject.toml`, `frontend/package.json`, `frontend/package-lock.json`, `e2e/package.json`, `e2e/package-lock.json` |
| `test(scripts): Formatier-Skript testgetrieben anlegen` | `scripts/tests/test_format_sh.py` (neu, zuerst rot), `scripts/format.sh` (neu) |
| `chore(format): Codebasis einmalig durchformatieren` | rein maschinell, alle vier Bäume |
| `test(frontend): Freigabe-Ausschnitt im Design-Vertrag an den Umbruch anpassen` | `frontend/src/designSystem.contract.test.ts` (ein `snippet`, siehe 7.) |

CI nach dem Merge von A: grün. Es gibt noch keine Formatprüfung, und alle bestehenden Prüfungen
sind auf dem formatierten Stand nachweislich grün (siehe 7.).

**PR B — `ci: Formatierung verbindlich prüfen (Spec 0400)`**

| Datei | Art |
|---|---|
| `.github/workflows/ci.yml` | vier neue Schritte (siehe 8.) |
| `scripts/tests/test_keine_automatische_formatierung.py` | neu, Wächtertest gegen auslösende Dateien (siehe 9.) |
| `scripts/tests/test_formatierer_fixierung.py` | neu, Wächtertest über die vier Versions-Pins (siehe 5.) |
| `scripts/tests/test_prettierignore_spiegelung.py` | neu, Wächtertest über die `.gitignore`-Spiegelung (K11, siehe 4.) |
| `specs/architecture/0002-testkonzept.md` | neue Sektion zu ADR 0080 / Spec 0400 (siehe `## Teststrategie`) |
| `docs/setup.md` | Formatierbefehl + was bei roter Prüfung zu tun ist |
| `specs/features/0400-einheitliche-code-formatierung.md` | Status auf `Implemented`, beide PR-Verweise |

CI nach dem Merge von B: grün, weil der Code seit A bereits mit exakt diesen Versionen und dieser
Konfiguration formatiert ist.

**Zwingende Regeln für die Abfolge:**

1. **PR B wird erst von `main` abgezweigt, nachdem PR A gemergt ist.** Zweigt er früher ab, ist
   seine eigene CI rot, und er ist nicht mergebar.
2. **Solange PR A offen ist, veraltet sein Diff mit jedem anderen Merge auf `main`.** Nach jedem
   Abgleich mit `main` (`scripts/merge-main-into-branch.sh`) muss `scripts/format.sh` erneut
   laufen und das Ergebnis nachcommittet werden. Das Zeitfenster ist kurz zu halten — beide PRs
   möglichst direkt nacheinander.
3. **Für PR A wird ausdrücklich kein Copilot-Review angefordert** (Vorgabe Daniels). Das weicht
   von der Konvention in `CLAUDE.md` ab, nach der ein PR mit Code-Dateien ein Copilot-Review
   erhält; die Abweichung ist bewusst und auf PR A beschränkt. **PR B erhält ein Copilot-Review**
   — er enthält mit den drei Wächtertests echte Code-Dateien.

   **Was den Verzicht trägt — und was ihn ausdrücklich nicht trägt.** "Formatierung ist
   verhaltenserhaltend" trägt nicht: Ein geändertes Zeichen in einem Stringliteral, ein gekippter
   Vergleich, ein negiertes `if`, eine als "zusammengezogen" getarnt entfernte Wächterzeile oder
   ein zusätzlicher Eintrag in einer `package-lock.json` sähen in einem Diff über 200+ Dateien
   genauso aus wie ein Zeilenumbruch. Ein grüner Prüfsatz trägt ebenfalls nicht — ein Literal,
   das kein Test festnagelt, überlebt ihn. Und die CI-Formatprüfung aus PR B trägt auch nicht:
   Sie belegt nur, dass der Endzustand ein Fixpunkt des Formatierers ist, und das ist ein
   eingeschmuggeltes Literal genauso. **Was trägt, ist Reproduzierbarkeit — und sie ist eine
   Eigenschaft je Commit, nicht des PR als Ganzes:**

   | Commit | wie er abgenommen wird |
   |---|---|
   | `docs(spec)` | `git show --stat` listet ausschließlich Dateien unter `specs/` — Pfadprüfung, kein Lesen nötig |
   | `build(format)` | **wird Zeile für Zeile gelesen.** Acht Dateien, darunter beide `pyproject.toml` und beide Lockfiles. Lockfile-Anteil zusätzlich mechanisch: außer dem Prettier-Eintrag ändert sich kein `resolved`/`integrity`/`version` eines bestehenden Pakets |
   | `test(scripts)` | wird gelesen — handgeschriebener Code, überschaubarer Umfang |
   | `chore(format)` | **wird nicht gelesen, sondern reproduziert** (K12): auf dem Elternstand die fixierten Werkzeuge laufen lassen, danach muss `git diff --quiet <chore-commit>` mit 0 enden. Trifft das zu, enthält der Commit nachweislich nichts als Formatiererausgabe — vollständig, ohne menschliches Urteil |
   | `test(frontend)` | eine Zeile, wird gelesen |

   Reproduziert wird zweckmäßig über `uvx ruff@0.16.4` und `npx prettier@3.9.6` statt über
   `.venv`/`node_modules`, damit der Nachweis nicht an derselben lokalen Installation hängt, die
   den Diff erzeugt hat. Die Vertrauenskette schließt sich damit: Die Fixierung der
   Werkzeugversionen steht in dem einen Commit, der gelesen wird. Das ist zugleich die Antwort
   darauf, warum der Verzicht vertretbar ist — ein Sprachmodell, das 200 Dateien überfliegt, gibt
   eine schwächere Zusicherung als ein byte-genauer Reproduktionsnachweis, und den kann Copilot
   nicht führen.

5. **`scripts/format.sh` bekommt eigene Tests, und zwar in PR A.** `CLAUDE.md` kennt keine
   Ausnahme vom TDD-Zwang, und das Skript liegt auf der Verzweigungsseite des im Testkonzept
   geführten Kriteriums (es parst den `ruff`-Pin aus einer `pyproject.toml`, parst
   `ruff --version`, vergleicht beide und prüft `node_modules` in zwei Bäumen). Der
   unangenehme Fehlerfall ist still: Liefert die Pin-Extraktion den Leerstring, besteht der
   Vergleich `"" == ""`, und das Skript formatiert mit der falschen Version genau den Diff, den es
   verhindern soll. Der Copilot-Verzicht für PR A bleibt davon unberührt — er begründet sich über
   das Nachrechnen des *Formatier*-Commits, und die handgeschriebenen Commits werden ohnehin
   gelesen.
4. **`style:` ist in diesem Repository kein zulässiger Commit-/PR-Typ.** Zulässig sind die zehn
   Typen aus `CLAUDE.md`. Für die Durchformatierung ist `chore:` der richtige Typ, für die
   Konfiguration `build:`, für die CI-Prüfung `ci:`. Keiner der drei löst einen
   `release-please`-Versions-Bump aus — für eine reine Formatierungsstory ist das richtig.

### 11. Reihenfolge der Umsetzung

1. **Konfiguration schreiben** (`/.prettierrc.json`, `/.prettierignore`, beide `pyproject.toml`,
   beide `package.json`), `prettier` in beiden TypeScript-Bäumen exakt installieren, beide
   Python-`.venv` mit dem neuen `ruff`-Pin neu installieren.
2. **Rot-Nachweis führen:** `ruff format --check .` in beiden Python-Bäumen und
   `npm run format:check` in beiden TypeScript-Bäumen melden die abweichenden Dateien. Das ist der
   "rote" Ausgangspunkt dieser Story — die dauerhaften Testartefakte (CI-Schritte, zwei
   Wächtertests) entstehen testgetrieben erst in PR B.
3. **`scripts/format.sh` schreiben** und den Rot-Nachweis über dieses Skript wiederholen, damit
   von Anfang an der Befehl den Diff erzeugt, der später dokumentiert wird.
4. **Durchformatieren** — ein Lauf, ein Commit, nichts von Hand nachbessern.
5. **Reproduktionsnachweis führen (K12):** Ein zweiter `scripts/format.sh`-Lauf auf dem
   formatierten Stand lässt `git status` sauber (Idempotenz — ein Werkzeug, das beim zweiten Lauf
   noch etwas ändert, ist falsch konfiguriert). `git show --stat` des Formatier-Commits gegen die
   Ausschlussliste halten: keine `*.md`, nichts unter `design/`, keine `package-lock.json`, kein
   `alembic/script.py.mako`. Und die Gegenprobe gegen die lokale Installation:
   `uvx ruff@0.16.4 format --check .` in beiden Python-Bäumen.
6. **Gesamtprüfsatz lokal fahren:** `ruff check` + `mypy src` + `pytest` im Backend, `ruff check` +
   `pytest` in `scripts/`, `oxlint` + `tsc -b --noEmit` + `vitest run` + `npm run build` im
   Frontend, `tsc --noEmit` in `e2e/`. Erwartet wird genau ein Fehlschlag: der Design-Vertragstest
   aus 7.
7. **Den einen `snippet` nachführen**, Prüfsatz erneut fahren, die Stellen aus 7. gegenprüfen
   (Inventar **neu erheben**, nicht aus der Spec übernehmen — siehe `## Teststrategie`), PR A
   eröffnen. **PR A wird nicht gemergt, bevor sein `e2e`-Job grün ist** — das ist die einzige
   Stelle, an der die drei zeilenverankerten Leser in `e2e/tests/toolchain.spec.ts` tatsächlich
   ausgeführt werden.
8. Nach dem Merge von A: **PR B** — alle drei Wächtertests zuerst (rot gegen absichtlich angelegte
   Köderzustände, dann grün), danach die vier CI-Schritte, `docs/setup.md` und die
   Testkonzept-Sektion.

## UI/UX

Nicht relevant. Die Story ändert ausschließlich die Textform bestehender Quelldateien sowie
Werkzeug-, CI- und Dokumentationsdateien. Es entsteht, entfällt und verändert sich keine
dargestellte Oberfläche, kein Zustand und kein angezeigtes Datum; die erfassten CSS-Dateien werden
umgebrochen, nicht in ihrer Wirkung verändert. Für Nutzer von PhotoSort ändert sich nichts — das
sagt die Story selbst in ihrem Zielabschnitt.

## Teststrategie

Die Story erzeugt zwei Arten von Nachweis, und sie liegen in verschiedenen PRs. **PR A hat keine
eigenen Testartefakte für die Durchformatierung** — sein Nachweis ist, dass der bestehende
Prüfsatz auf dem umgeschriebenen Baum grün bleibt und dass der Diff reproduzierbar maschinell ist
(K12). **PR B bringt die dauerhaften Artefakte:** vier CI-Schritte und drei Wächtertests, jeder
testgetrieben gegen absichtlich angelegte Köderzustände. `scripts/format.sh` ist die eine
Ausnahme in PR A: handgeschriebene Verzweigungslogik, also Test vor Skript (Abschnitt 10, Regel 5).

### Abnahme von PR A: vier Läufe, nicht drei

`scripts/tests` läuft **nicht** mit dem Backend-Prüfsatz mit (`testpaths = ["tests"]` gilt
unterhalb von `backend/`). Hier ist das keine Formalie: 9 Dateien unter `scripts/` werden
umgeschrieben, **und** `scripts/format.sh` fällt neu in den Suchraum von
`scripts/tests/test_main_abgleich_verdrahtung.py`, der über `git ls-files -- scripts .claude`
zählt und dort eine Einmaligkeits-Zusicherung hält.

| Baum | Befehl | Erwartung |
|---|---|---|
| `backend/` | `ruff check . && mypy src && pytest --cov=photosort --cov-report=term-missing --cov-fail-under=80` | grün, Coverage ≥ 80 |
| `scripts/` | `ruff check . && pytest` | grün |
| `frontend/` | `npm run lint && npm run typecheck && npm run test -- --run && npm run build` | **vor** der Snippet-Nachführung genau 1 Fehlschlag, danach 0; `oxlint`: 0 Fehler und dieselbe Warnungszahl wie vorher (gemessen: 10) |
| `e2e/` | `npm run typecheck` | grün (Playwright-Specs laufen lokal nicht) |

**Akzeptierter Erwartungswert, präzise:**

- Vor der Nachführung: **genau ein** roter Fall, `designSystem.contract.test.ts`, und er schlägt
  **zweifach** an ("nicht freigegeben" für den neuen Fundort, "verwaiste Freigabe ohne Fundstelle"
  für den alten Eintrag). Schlägt er nur einfach an, oder schlägt zusätzlich etwas anderes an, ist
  die Lage **nicht** die gemessene — dann hält der Lauf an, statt weiterzumachen.
- Nach der Nachführung: **null** Fehlschläge in allen vier Bäumen. Die absolute Fallzahl (1.567
  zum Messzeitpunkt) ist **kein** Abnahmekriterium — sie bewegt sich mit jedem `main`-Merge;
  "null rot" ist es.
- **Coverage:** Die Zahl vor und nach der Durchformatierung notieren. `ruff format` kann
  Anweisungen auf mehrere Zeilen verteilen und die gemessene Quote um Bruchteile verschieben.
  Erwartung: unverändert ≥ 80. Ein Absacken unter 80 durch reine Formatierung wäre ein echter
  Befund (das Gate stünde dann auf der Kippe), kein Rauschen.
- **Erzeugte Penpot-Nutzlast:** Nach dem vollständigen `vitest`-Lauf muss `git status -- design/`
  sauber sein. `frontend/penpot/tokens.test.ts` und `icons.test.ts` sind über
  `toMatchFileSnapshot` **Erzeuger** — sie schreiben `design/penpot/tokens.json`/`icons.json` bei
  Abweichung neu, **ohne rot zu werden**. Ein stiller Diff dort ist der unauffälligste Schaden,
  den diese Story anrichten kann.

**Worktree-Fallen, falls PR A nicht im Haupt-Checkout entsteht:** `PYTHONPATH=<worktree>/backend/src`
voranstellen, sonst importiert der Lauf den Code des Haupt-Checkouts; und
`backend/src/photosort/assets/label_embedder.onnx` einmal hineinkopieren, sonst scheitern zwei
Fälle in `test_label_embedding.py` ohne Bezug zur Story. Beide Fehlschläge sähen aus wie echte
Befunde und zerstörten die Erwartung "genau ein Fehlschlag".

### Die Risikoklasse "Test liest fremden Quelltext zeilenverankert"

Abschnitt 7 nennt fünf Stellen. **Diese Liste wird nicht übernommen, sondern neu erhoben** — sie
ist eine Momentaufnahme, und bis zum Umsetzungslauf können Merges auf `main` neue Leser dieser
Bauart hinzufügen.

1. **Inventar mechanisch neu erheben, vor dem Formatieren:**

   ```bash
   grep -rn "readFileSync\|toMatchFileSnapshot\|read_text\|readlines()" \
     --include=*.ts --include=*.tsx --include=*.py \
     backend/tests frontend/src frontend/penpot e2e scripts/tests | grep -v node_modules
   ```

   Der Bestand trägt **mehr** Leser als die fünf genannten — `frontend/penpot/payload.test.ts`
   liest an sechs Stellen `frontend/src`-Quelltext, `backend/tests/test_categories.py` liest
   Modulquelltext über `inspect.getfile`. Die meisten sind formatierungsimmun (`ast.parse`,
   `toContain` über den ganzen Dateiinhalt). Die Aussage "das ist die einzige solche Stelle" gilt
   nur für die **zeilenverankerte** Teilmenge; diese Unterscheidung wird beim Lauf getroffen, nicht
   vorausgesetzt.
2. **Schnittmenge bilden:** Zieldateien des Inventars ∩ Dateiliste des Formatier-Diffs. Jede
   Schnittmenge wird einzeln angesehen; alles außerhalb ist unberührt.
3. **Für die drei lokal nicht laufenden Stellen literal gegenprüfen.** Der `e2e`-Job braucht den
   vollen Docker-Prüfstack, `npm run typecheck` sieht diese regulären Ausdrücke nicht. Nach dem
   Formatieren, drei Befehle, jeder muss **genau eine** Zeile liefern:

   ```bash
   grep -cE '^CONFIRM_LITERAL = "[^"]+"$'         backend/src/photosort/demo_state.py
   grep -cE '^DEMO_PROJECT_PREFIX = "[^"]+"$'     backend/src/photosort/demo_state.py
   grep -cE "^const TOKEN_STORAGE_KEY = '[^']+'$" frontend/src/auth/token.ts
   ```
4. **Die bindende Bestätigung** ist der `e2e`-Job auf PR A selbst. Er läuft ohne Pfadfilter auf
   jedem `pull_request`. Verbindlich: kein Merge, bevor er grün ist; wird er rot, sind diese drei
   Stellen die ersten Verdächtigen. Das gehört als benannte Zeile in den PR-Body.

**Eine Gefahr derselben Klasse, die in Abschnitt 7 nicht steht:** `ruff format` vereinheitlicht
Python-Stringliterale auf **doppelte** Anführungszeichen. Jedes Muster, das einfache
Anführungszeichen in Python-Quelltext erwartet, bricht — spiegelbildlich zum
`TOKEN_STORAGE_KEY`-Fall, bei dem `singleQuote: true` gerade rettet. Bei der Inventur in Schritt 1
ist das die zweite Frage neben der Zeilenverankerung.

### `scripts/tests/test_keine_automatische_formatierung.py` (K8)

**Der naheliegende Entwurf scheitert, und das ist der tragende Punkt:** Ein Volltextscan nach
`husky`/`lefthook`/`pre-commit`/`simple-git-hooks` ist am eigenen Bestand sofort rot — genau diese
Wörter stehen in dieser Spec, in ADR 0080 und im Testkonzept. Eine `specs/`-Ausnahme nähme
ausgerechnet den Ort aus, an dem später jemand eine Hook-Datei ablegen könnte. Geprüft werden
deshalb **Pfade und strukturierte Konfigurationsschlüssel**, und nur die vierte Familie ist ein
Textscan.

Suchraum: `git ls-files -z` über das ganze Repository, dünner Leser nach dem Vorbild von
`verwaltete_dateien()` in `scripts/tests/test_board_referenzfreiheit.py` — **nie `rglob`**
(gemessen: `rglob` sieht 5297 statt 658 Pfade, weil Worktrees und nicht verwaltete Arbeitskopien
hineinfallen). Zweiter Leser für die strukturierten Dateien über `json` und `tomllib` (Stdlib in
3.12, keine neue Abhängigkeit — konsistent mit dem Verzicht auf PyYAML in den Nachbartests).

**Familie 1 — verbotene Pfade und Dateinamen:** Präfixe `.husky/`, `.githooks/`, `.hooks/`;
Dateinamen `.pre-commit-config.yaml`/`.yml`, `lefthook.{yml,yaml,toml,json}` samt
`.lefthook.*`/`lefthook-local.*`, `.simple-git-hooks.json`, `simple-git-hooks.{json,js,cjs}`.

**Familie 2 — Git-Hook-Namen an beliebiger Stelle.** Der Kern: `core.hooksPath` kann auf **jedes**
Verzeichnis zeigen, ein Pfadpräfix fängt das nicht. Git-Hook-Namen sind aber eine dokumentierte,
geschlossene Menge (`pre-commit`, `commit-msg`, `pre-push`, `post-checkout`, … — vollständige
Liste im Test als `frozenset`). Verglichen wird `Path(pfad).stem` **und** `Path(pfad).name`, damit
`pre-commit` wie `pre-commit.sh` fällt. Am Bestand gemessen: **0 Treffer** über alle 658
verwalteten Pfade, keine Ausnahme nötig — dieser Messwert gehört in den Kopfkommentar, damit die
nächste Änderung ihn nachrechnet statt ihn zu glauben. `update` steht bewusst mit drin: ein
Fundstück namens `update` ohne Endung ist ein richtiger Alarm.

**Familie 3 — strukturierte Konfigurationsschlüssel, als Totalverbot:**

- **(3a)** Keine verwaltete `package.json` führt `preinstall`/`install`/`postinstall`/`prepare`
  unter `scripts`. Totalverbot statt "prüfe, ob das Skript einen Hook installiert" — dieselbe
  Begründung wie beim Substring-Totalverbot in `test_main_abgleich_verdrahtung.py`: In einer Datei
  mit einem Zweck schlägt die Totalaussage die Kontextanalyse. Kosten heute: null.
- **(3b)** Kein Hook-Werkzeug (`husky`, `lefthook`, `simple-git-hooks`, `pre-commit`,
  `lint-staged`, `pretty-quick`, `@lefthook/cli`, `yorkie`) in `dependencies`/`devDependencies`
  einer `package.json` oder in `dependencies`/`optional-dependencies` einer `pyproject.toml`. Das
  fängt den Vektor **vor** der Hook-Datei — das Werkzeug kommt zuerst als Abhängigkeit.
- **(3c)** Keine verwaltete Editor-/Agenten-Konfiguration mit Formatier-Auslöser:
  `.vscode/settings.json` (`editor.formatOnSave`, `editor.codeActionsOnSave`), `.idea/`, und in
  `.claude/settings.json` der Schlüssel `hooks`. Am Bestand ist **keine** dieser Dateien
  verwaltet; geprüft wird also nur, *falls* sie auftaucht. Das ist die Stelle mit dem
  Testkonzept-Vorbehalt "ein Muster ohne mögliche Gegenprobe wird nicht heimlich mitgeführt" — die
  Gegenprobe ist hier notgedrungen synthetisch, und genau das steht als Kommentar am Test.
  `.claude/settings.local.json` ist nicht verwaltet und fällt über `git ls-files` korrekt heraus;
  das ist gewollt, eine lokale Einstellung wirkt nicht auf fremde Sessions.

**Familie 4 — der eine Textscan, mit Ausnahmen:** Muster `core.hooksPath`, byteweise verglichen
(der Suchraum enthält Binärdateien), Ausnahmen `CHANGELOG.md`, `specs/` und die Testdatei selbst.
Ein eingecheckter Einrichtungsbefehl (`git config core.hooksPath .githooks`) ist der einzige Weg,
wie eine verwaltete Datei einen Hook scharf schaltet, ohne dass die Hook-Datei selbst verwaltet
ist.

**Selbstschutz — vier Zusicherungen, jede mit eigenem Testnamen:**

| Test | Zusicherung | Grund |
|---|---|---|
| `test_der_suchraum_hat_eine_plausible_groesse` | `len(verwaltete_pfade()) >= 400` (Ist: 658) | fängt den Totalausfall der Aufzählung, nicht jede gelöschte Datei |
| `test_die_gepruefte_konfiguration_liegt_im_suchraum` | alle vier Konfigurationspfade sind Schlüssel des Abbilds | Familie 3 prüft sonst nichts und meldet trotzdem "sauber" |
| `test_die_konfiguration_wurde_wirklich_geparst` | `frontend/package.json` hat einen nicht-leeren `scripts`-Block mit `build` | ein Parser, der still `{}` liefert, macht jedes Totalverbot vakuum-grün |
| `test_ein_leerer_suchraum_scheitert_laut_statt_still` | die reine Funktion wirft `ValueError` | wortgleich zum Muster in `test_board_referenzfreiheit.py` |

**Gegenprobe je Musterfamilie**, parametrisiert auf synthetischem Abbild — vier Köder
(`.husky/pre-commit`; `tools/git/pre-commit`; `{"scripts":{"prepare":"husky"}}`;
`git config core.hooksPath .githooks`), jeder muss rot färben. Dazu die Gegenrichtung
(`test_der_bestand_wird_nicht_faelschlich_gemeldet`): `.github/workflows/` und hook-freie
Nachbardateien lösen nichts aus. Ohne diese zweite Richtung wäre ein Muster, das alles trifft, von
einem korrekten nicht zu unterscheiden.

**Mutationsprobe, verbindlich und im Kopfkommentar zu vermerken:** Nach Grün je Familie einmal
real anlegen, rot sehen, zurücknehmen. Der triviale Rot-Lauf zu Beginn belegt hier nichts — der
Bestand ist sauber, der Test startet grün.

### `scripts/tests/test_formatierer_fixierung.py` (K6)

**(a)** Beide `pyproject.toml` nennen dieselbe `ruff`-Version — strukturiert über `tomllib` aus
`project.optional-dependencies.dev` gelesen, gesucht wird der Eintrag, dessen Paketname (vor dem
ersten Zeichen aus `=<>~!`) `ruff` lautet. **Nicht** per Regex über den Rohtext, sonst zählt eine
auskommentierte Zeile mit. **(b)** Beide `package.json` nennen dieselbe `prettier`-Version
(`devDependencies.prettier`, `json.loads`).

**(c) Exaktheit positiv je Ökosystem, nicht als Zeichen-Blacklist.** Hier hat die naheliegende
Fassung ein Loch: "enthält kein `>=`, `~`, `^`, `*`" lässt **beide** realistischen Fehlerformen
durch — den nackten Eintrag `ruff` ohne jeden Operator und das npm-`"latest"`. Zwei positive
Formen stattdessen:

```python
_PEP508_EXAKT = re.compile(r"^ruff\s*==\s*\d+\.\d+(\.\d+)?$")      # kein Wildcard, kein zweiter Clause
_NPM_EXAKT    = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")   # kein ^ ~ >= x * ||, kein "latest", kein npm:-Alias
```

Je eine parametrisierte Negativtabelle dazu — `ruff`, `ruff>=0.7`, `ruff==0.16.*`,
`ruff==0.16.4,<0.17` bzw. `^3.9.6`, `~3.9.6`, `3.x`, `latest`, `*`, `npm:prettier@3.9.6` — jeder
Fall muss abgewiesen werden. **Diese Tabelle ist die eigentliche Substanz der Zusicherung**; die
Prüfung am echten Bestand ist grün und belegt für sich nichts.

**(d)** Keine verwaltete `package.json` trägt einen `"prettier"`-Schlüssel. Suchraum ist **jede**
`package.json` aus `git ls-files`, nicht die beiden bekannten — ein künftiger dritter npm-Baum
soll nicht dadurch durchrutschen, dass niemand an die Liste denkt.

**(e) `(d)` verallgemeinert: genau eine Prettier-Konfigurationsquelle im ganzen Repository**, und
das ist `/.prettierrc.json`. Der `"prettier"`-Schlüssel ist nur eine von dreizehn Quellen, die die
Wurzeldatei still überschatten (`.prettierrc`, `.prettierrc.{json,json5,yml,yaml,toml,js,cjs,mjs}`,
`prettier.config.{js,cjs,mjs,ts}`). Zusicherung: genau ein Treffer, Pfad ohne Verzeichnisanteil;
analog genau eine verwaltete `.prettierignore` in der Wurzel. Und die `ruff`-Entsprechung derselben
Fehlerklasse: **keine verwaltete `ruff.toml`/`.ruff.toml`** — sie hätte gegenüber dem
`[tool.ruff]`-Abschnitt der `pyproject.toml` im selben Verzeichnis lautlos Vorrang.

**(f) Die Lockfile-Auflösung trägt denselben Wert wie die Deklaration** —
`packages["node_modules/prettier"].version` in beiden `package-lock.json`. `npm ci` installiert,
was im Lockfile steht; ohne diese Zusicherung prüft der Wächter eine Zahl, die nicht die
installierte ist.

**(g) Beide `package.json` führen `format` und `format:check` wortgleich**, und beide Befehle
enthalten `--ignore-path ../.prettierignore`. Fällt das Flag in **einem** Baum weg, erfasst dieser
Lauf plötzlich die Markdown-Dateien — still, bis jemand in `e2e/` eine `.md` ablegt. Verglichen
werden die Zeichenketten der beiden Bäume gegeneinander plus die Anwesenheit des Flags; keine
eingefrorene Literalkonstante.

**(h) Eine Zeilenbreite im ganzen Projekt, als Gleichheit geprüft:** `printWidth` aus
`/.prettierrc.json` == `line-length` aus beiden `pyproject.toml`; dazu die Gleichheit der beiden
`[tool.ruff.format].exclude`-Werte und der beiden `[tool.ruff.lint.pycodestyle].max-line-length`.
Alles Gleichheiten zwischen Dateien, keine Buchhaltungskonstanten.

**Selbstschutz:** alle vier Versionsangaben nicht-leer und aus vier verschiedenen Dateien (ein
Parser, der still `None` liefert, ließe `None == None` bestehen — der wahrscheinlichste Defekt
dieses Tests); die `package.json`-Aufzählung liefert ≥ 2 Pfade und enthält beide bekannten; eine
fehlende Datei scheitert mit `ValueError` unter Nennung des Pfades statt mit `KeyError`.

### `scripts/tests/test_prettierignore_spiegelung.py` (K11)

Koppelt `/.prettierignore` an die `.gitignore`-Einträge unterhalb von `frontend/` und `e2e/` und
sichert die fünf `e2e/`-Verzeichnisse (`.auth/`, `artifacts/`, `test-results/`,
`playwright-report/`, `scratch/`) als **Mindestmenge** fest zu, mit Gegenprobe. Begründung wie bei
den anderen beiden: Das ist die Zusicherung, die still bricht — ein fehlender Eintrag fällt lokal
nur als "eine Datei mehr formatiert" auf, und in CI gar nicht, weil die betroffenen Verzeichnisse
dort zum Prüfzeitpunkt nicht existieren.

### `scripts/tests/test_format_sh.py` (PR A)

Zugeschnitten auf die reine Parse-/Vergleichslogik, etwa 8 Fälle nach dem Muster von
`scripts/tests/test_merge_main_into_branch.py`: Pin aus einer synthetischen `pyproject.toml`
lesen; `ruff --version` gegen ein Fake-`ruff` auf dem `PATH`; je ein Abbruchfall pro Vorbedingung
mit Exit-Code ≠ 0 **und** einer Meldung, die den Handgriff nennt. Der tragende Fall ist der stille:
Liefert die Pin-Extraktion den Leerstring, darf der Vergleich **nicht** bestehen.

### Bewusst nicht getestet

- **Dass `ruff format` und Prettier korrekt formatieren.** Fremdverhalten, durch exakte Pins
  fixiert. Eine Nachbildung der Formatierregeln wäre eine zweite, schlechtere Quelle der Wahrheit.
- **Die Formatierung selbst zeichenweise.** Das Werkzeug *ist* die Zusage.
- **Die Doku-Bindung zu `docs/setup.md` (K9).** Ein Wächtertest nach dem Muster von
  `test_setup_docs.py` wäre hier Formulierungspolizei.

### Testkonzept

`specs/architecture/0002-testkonzept.md` bekommt eine neue Sektion hinter der ADR-0061-Erweiterung
im Block "Repo-Konsistenztests", weil genau deren Regelwerk hier zum zweiten Mal angewandt und an
vier Stellen erweitert wird:

1. **Ein Abwesenheits-Test, dessen verbotene Begriffe legitim im Repository stehen, prüft Form
   statt Text.** Ist der verbotene Begriff *als Begriff* legitim, ist das Verbot ein Pfad-,
   Dateinamens- oder Konfigurationsschlüssel-Verbot — nie ein Wortverbot.
2. **Exaktheit einer Versionsangabe wird positiv formuliert, je Ökosystem getrennt.** Eine
   gemeinsame Zeichen-Blacklist lässt den nackten PEP-508-Eintrag und das npm-`"latest"` durch.
   Fortsetzung der Whitelist-statt-Blacklist-Regel aus der Spec-0343-Sektion.
3. **Ein Test, der eine *installierte* Version zusichern will, liest das Lockfile, nicht nur die
   Deklaration.**
4. **"Formatieren ist verhaltenserhaltend" ist keine Abnahme.** Vor jeder repo-weiten
   Umformatierung wird das Inventar der zeilenverankerten Leser neu erhoben, mit der Dateiliste
   des Diffs geschnitten und je Schnittmenge geprüft; eine frühere Messung wird nicht übernommen.
   Zweite Gefahrenquelle derselben Klasse: `ruff format` vereinheitlicht auf doppelte
   Anführungszeichen.

Dazu drei kleinere Nachträge: unter "Bekannte Lücken" die Werkzeug-Signaturlage (siehe
`## Security`); unter "Was bewusst nicht getestet wird" das Formatierverhalten der Werkzeuge
selbst; unter "Werkzeuge im Überblick" `ruff format` und Prettier 3.9.6 mit ihren vier
CI-Schritten.

Das Coverage-Gate ist unberührt: Der `backend`-Job misst `--cov=photosort`, alle neuen Tests
liegen unter `scripts/tests/` im Job `demo-scripts` ohne Gate.

## Security

**Einstufung: sicherheitsrelevant, kein Blocker.** Kein Anwendungscode-Verhalten, kein Endpunkt,
keine Änderung an Auth, Berechtigungen oder Datensichtbarkeit zwischen den beiden Nutzern, keine
neue Eingabe von außen, kein Laufzeitanteil (beide Formatierer gehen in kein Container-Image ein).
Die Relevanz liegt vollständig in der Entwicklungs-Lieferkette und im Geltungsbereich der
Werkzeuge auf dem Entwicklerrechner. Die Dauerregeln stehen zusätzlich in
`specs/architecture/0003-securitykonzept.md`.

### S1 — Der Formatierer verliert die `.gitignore`-Auswertung und erfasst damit das gespeicherte JWT

Gemessen mit `prettier 3.9.6` am 2026-09-11. `--ignore-path` ersetzt Prettiers Vorgabe
vollständig, damit entfällt die `.gitignore`-Auswertung; Prettier steigt dabei **auch in
Punktverzeichnisse ab**. Der Wurzel-`.gitignore` hält heute genau die Verzeichnisse aus dem
künftigen Formatierbereich, die das Sicherheitskonzept als schützenswert führt: `e2e/.auth/`
(Anmeldezustand mit 30 Tage gültigem, nicht widerrufbarem JWT), `e2e/artifacts/`,
`e2e/test-results/`, `e2e/playwright-report/` (Traces mit Netzwerkinhalten samt Login-Request und
`localStorage`-Zustand), `e2e/scratch/`.

Gemessen: `prettier --check .` aus `e2e/` meldet `.auth/state.json` als abweichend;
`prettier --write .` — also `scripts/format.sh` — **schreibt die Datei mit dem JWT neu**.
**Leckkanal:** Bei einem Parse-Fehler gibt Prettier einen Code-Frame **mit dem Dateiinhalt** aus;
im Versuch stand der Token-Wert wörtlich in der Ausgabe. Eine halb geschriebene `state.json` aus
einem abgebrochenen Lauf genügt, damit das Token im Terminal oder im Protokoll eines
Agenten-Laufs landet.

**CI ist nicht betroffen** — `npm run format:check` steht im `e2e`-Job vor Chromium, Stackstart
und Seeding, die Verzeichnisse existieren dort zum Prüfzeitpunkt nicht. Der Befund betrifft
ausschließlich lokale Läufe, dort aber genau die Dateien, die das Konzept als "nie hochladen"
führt — und lokal läuft der schreibende Befehl.

**Gegenmaßnahme (verbindlich, K11):** die sechs zusätzlichen `/.prettierignore`-Einträge aus
Abschnitt 4, gehalten durch `test_prettierignore_spiegelung.py`. **Der tragende Grundsatz reicht
darüber hinaus:** Solange `--ignore-path` gesetzt ist, ist `/.prettierignore` die einzige
Ausschlussquelle; jeder `.gitignore`-Eintrag unterhalb von `frontend/` oder `e2e/`, der eine von
Prettier unterstützte Endung treffen kann, muss dort gespiegelt werden — auch jeder künftige.

**Die Python-Hälfte ist nicht betroffen:** `ruff` behält `respect-gitignore = true` (gemessen),
und `[tool.ruff.format] exclude` ergänzt die Vorgabe, statt sie zu ersetzen. `.env` ist für beide
Werkzeuge unerreichbar — für `.env` gibt es keinen Prettier-Parser.

### S2 — Prettier als neue Abhängigkeit der Entwicklungs-Lieferkette

Prettier erreicht weder das ausgelieferte Bundle noch ein Container-Image; die Wirkung einer
kompromittierten Version bliebe auf Entwicklerrechner und CI-Runner begrenzt — also auf den Ort,
an dem `gh`-Token und Repository-Schreibzugriff liegen (dieselbe Einstufung wie
`@playwright/test`, Spec 0174). Gegen npm-Registry und OSV geprüft (2026-09-11):
`prettier@3.9.6`, MIT, **null Laufzeit-Abhängigkeiten**, **kein Installationsskript**, 56 Dateien
/ ~9,95 MB entpackt, veröffentlicht 2026-07-21, keine Advisory. `ruff@0.16.4`: keine Advisory,
keine `requires_dist`. Gegenmaßnahmen ohne neue Mechanik: Lockfile mit Integritäts-Hash in beiden
Bäumen, Installation ausschließlich per `npm ci` (nie `npm install`), exakte Version ohne Caret.

Zwei Einschränkungen, die ehrlich benannt gehören:

- **`npm audit signatures` läuft nur im `e2e`-Job, nicht im `frontend`-Job.** Die Prettier-Kopie
  unter `frontend/` ist damit nicht signaturgeprüft. Das ist keine von dieser Story geschaffene
  Lücke — sie besteht heute für sämtliche 30+ Frontend-Pakete —, aber die Story vergrößert den
  ungeprüften Satz um eines. Die Schließung ist **bewusst eine eigene Story** (Entscheidung
  Daniels, 2026-09-11): Der Schritt könnte auf dem bestehenden Paketsatz sofort rot werden und
  dann eine reine Formatierungsstory blockieren.
- **Auch im `e2e`-Job prüft der Schritt für Prettier nur die Registry-Signatur, keine
  Provenance.** Gemessen: `prettier@3.9.6` trägt `dist.signatures`, die Attestierungs-Abfrage der
  Registry antwortet dagegen `Not found` — anders als `@playwright/test`, das eine Attestierung
  trägt. Der Nachweis lautet also "npm hat dieses Tarball signiert", nicht "dieses Tarball stammt
  aus dem Prettier-Repository". Gegen ein Kontoübernahme- oder Release-Pipeline-Szenario schützt
  er nicht.

**Zur `ruff`-Version:** Der Pin ist `0.16.4`, nicht der zum Entscheidungszeitpunkt neueste Stand
`0.16.7` — siehe Abschnitt 5 der Umsetzung und ADR 0080.

### S3 — Änderung an `.github/workflows/ci.yml`: geprüft, kein Befund

Das Repository ist öffentlich, CI läuft also auch auf Pull Requests Fremder. Geprüft und negativ:
Der Workflow bleibt auf `on: pull_request` (nie `pull_request_target`), die Workflow-`permissions:
contents: read` bleiben unverändert, keiner der vier neuen Schritte referenziert `secrets.*`,
fordert erweiterte Rechte oder legt einen neuen Job an. Die neuen Schritte führen keinen fremden
Inhalt aus, den die Jobs nicht ohnehin ausführen: `ruff format --check` und `prettier --check`
**parsen** nur; die tatsächliche Ausführung von PR-Inhalt steckt unverändert in `npm ci`
(Lifecycle-Skripte), `npm run lint/test/build` und `docker compose build`. Die Reihenfolge im
`e2e`-Job ist richtig: Die Formatprüfung steht **hinter** `npm audit signatures`, die
Lieferkettenprüfung bleibt der erste Schritt nach der Installation.

Eine Eigenschaft ist tragend: **`--output-format=github` gibt keinen Dateiinhalt aus** (gemessen:
nur `::error …file=…,line=…::… File would be reformatted`), während die Vorgabe-Ausgabe von
`ruff format --check` einen Inhalts-Diff druckt. Der Schalter ist damit zugleich die
konservativere Ausgabeform und nicht bloß Kosmetik.

### S4 — `scripts/format.sh` liest den `ruff`-Pin aus `pyproject.toml`

Heute kein Angriffspfad, weil der Wert nur verglichen und nicht in eine Aufrufstruktur eingesetzt
wird. Die Form wird trotzdem jetzt festgeschrieben, weil die naheliegende künftige Erweiterung
("falsche Version? dann installiere ich sie eben") genau hier ansetzt und das Skript auf einem
Rechner läuft, auf dem auch ein fremder PR-Branch ausgecheckt sein kann:

- Der Wert wird **verankert und zeichenklassenbegrenzt** gelesen, nicht per `grep ruff | cut`.
  Vorbild steht bereits im Repository (`ci.yml`, Schritt "Read pinned label-embedder model hash").
  Ein leeres oder mehrdeutiges Leseergebnis **bricht ab**, statt weiterzulaufen.
- Der gelesene Wert wird **ausschließlich verglichen**, immer in Anführungszeichen — nie in
  `eval`, nie in eine Kommandozeile, nie als Glob- oder Regex-Muster, nie in einen
  `uv pip install`/`uvx`-Aufruf.
- `set -euo pipefail`, wie in den bestehenden Skripten unter `scripts/`.

### S5 — Der ungereviewte Durchformatier-Diff

Vollständig behandelt in Abschnitt 10, Regel 3 der Umsetzung: was den Verzicht auf das
Copilot-Review für PR A trägt (Reproduzierbarkeit je Commit, K12) und was ihn ausdrücklich nicht
trägt ("Formatierung ist verhaltenserhaltend", ein grüner Prüfsatz, die CI-Formatprüfung aus
PR B). Die Lockfile-Diffs im `build(format)`-Commit sind dabei die Stelle mit dem höchsten
Tarnwert und werden deshalb gelesen, nicht nachgerechnet.

### Ausdrücklich nicht sicherheitsrelevant

Damit nicht danach gesucht wird: Anwendungsverhalten, Endpunkte, Auth, Berechtigungen,
Datensichtbarkeit zwischen den beiden Nutzern, Bilddaten, Secrets in Code/Specs/Logs,
Docker-Compose-Netzwerk, OpenCloud-Client.

## Entscheidungen

- `ruff format` statt Black — dasselbe Werkzeug, dieselbe Konfigurationsdatei, dieselbe
  Zeilenbreite, kein zusätzlicher Installationsschritt; Ergebnis ist Black-kompatibel.
- Prettier statt oxfmt — oxfmt ist 0.67.0 ohne 1.0-Termin, seine Konformitätszahl gilt nur für
  JS/TS, CSS/JSON sind unvermessen, Datei-weite Ignore-Direktive fehlt. Eine blockierende Regel
  darf nicht auf beweglicher Ausgabe stehen. Wechsel nach oxfmt 1.0 bleibt ausdrücklich offen.
- `printWidth: 100` = `line-length: 100` — eine Zeilenbreite im ganzen Projekt statt zweier.
- Exakte Pins statt `>=`/Caret — belegt durch drei verschiedene `ruff`-Versionen in drei lokalen
  Umgebungen desselben Repos unter derselben `>=0.7`-Angabe.
- E501 bleibt, mit `max-line-length = 110` statt `ignore = ["E501"]` — der Formatierer übernimmt
  die Breite für alles, was er umbrechen kann; für lange Kommentare und Docstrings, die er nie
  anfasst, bleibt E501 der einzige Wächter.
- `alembic/versions`: formatiert, nicht gelintet — die beiden Ausschlüsse hatten nie denselben
  Grund, sie standen nur zufällig in derselben Zeile.
- `ruff format` darf kein Markdown anfassen — aktiv konfiguriert, weil `ruff` seit 0.16.0
  Python-Codeblöcke in `.md` umschreibt (gemessen).
- `design/` ausgeschlossen — zwei erzeugte JSON-Dateien hängen an `toMatchFileSnapshot`, die
  übrige Nutzlast an statischen AST-Zusicherungen.
- Prüfung in bestehenden CI-Jobs statt eigenem Job — kostenlos, sofort blockierend, kein manueller
  Eintrag in die Branch Protection nötig.
- Ein Handgriff-Skript, kein Hook — ein Hook, der beim Commit still schreibt, entzieht dem
  Aufrufer den Stand, den er gerade geprüft hat.
- **`e2e/` ist mit erfasst (Entscheidung Daniels, 2026-09-11).** Der `architect` hatte den Baum
  zunächst ausgrenzen wollen, weil er dort Semikolons gemessen hatte; die Messung war durch ein
  rekursives `grep` über `e2e/node_modules` verfälscht. Über `git ls-files` gemessen tragen zwei
  Zeilen im ganzen Baum ein abschließendes Semikolon, beide in Blockkommentaren — `e2e/` ist im
  selben Hausstil geschrieben wie das Frontend. Damit hat kein handgeschriebener Quelltextbaum des
  Repositorys mehr eine Formatierungslücke.
- **Die Formatierer-Konfiguration liegt in PR A, nicht in PR B (Entscheidung Daniels,
  2026-09-11).** Daniels ursprüngliche Aufteilung hätte sie PR B zugewiesen; dann wäre PR A ein
  Diff gewesen, den niemand nachrechnen kann — und das Nachrechnen-Können ist genau die
  Begründung, mit der auf das Copilot-Review für PR A verzichtet wird.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story hat keinen konkret benennbaren Bezug
  zu einer sichtbaren Oberfläche. Sie ändert die Textform von Quelldateien sowie Werkzeug-, CI-
  und Dokumentationsdateien; keine dargestellte Ansicht, kein Zustand und kein angezeigtes Datum
  entsteht, entfällt oder ändert sich.
- **Der `ruff`-Pin ist `0.16.4`, nicht der neueste Stand `0.16.7` (Entscheidung Daniels,
  2026-09-11).** `0.16.7` war einen Tag alt; das ist das Fenster, in dem eine kompromittierte
  Veröffentlichung am wahrscheinlichsten noch unentdeckt ist, und `ruff` landet über `[dev]` auf
  dem Rechner, auf dem `gh`-Token und Repository-Schreibzugriff liegen. `0.16.4` bringt zudem Pin
  und ADR-Messung zur Deckung.
- **`npm audit signatures` im `frontend`-Job wird eine eigene Story (Entscheidung Daniels,
  2026-09-11).** Die Lücke ist nicht von dieser Story verursacht — sie besteht für sämtliche 30+
  Frontend-Pakete —, aber diese Story legt ein Paket mehr hinein. Sie hier zu schließen hieße, dass
  eine reine Formatierungsstory an einem fremden Befund hängen bleiben kann.
- **`scripts/format.sh` bekommt eigene Tests, und sie liegen in PR A.** Entschieden nach
  `CLAUDE.md`, die keine Ausnahme vom TDD-Zwang kennt; das Skript liegt auf der Verzweigungsseite
  des im Testkonzept geführten Kriteriums. Begründung, warum das den Copilot-Verzicht für PR A
  nicht berührt: Abschnitt 10, Regel 5.
- **Die ADR trägt die Nummer 0078, nicht 0075.** Der `architect` hatte sie zunächst als `0075`
  angelegt — die Nummer war bereits an
  [`0075-abgleich-mit-main-fasst-den-lokalen-main-ref-nicht-mehr-an`](../decisions/0075-abgleich-mit-main-fasst-den-lokalen-main-ref-nicht-mehr-an.md)
  vergeben. Aufgefallen beim Schreiben des Sicherheitskonzept-Abschnitts, vor dem ersten Commit
  bereinigt.
- `test-engineer` und `security-engineer` wurden beide konsultiert (Schritt 3). Der
  `security-engineer` bewusst und nicht übersprungen: Ein Diff über 200+ Dateien, der ohne Review
  gemergt werden soll, ist eine Restrisiko-Frage und keine technische Detailfrage. Sein Befund S1
  (siehe `## Security`) war ohne diese Konsultation nicht zu haben.

## Offene Fragen

Keine.

## Out of Scope

- **Markdown-Formatierung.** Ausdrücklich ausgenommen (Akzeptanzkriterium) und aktiv
  konfiguriert — handgesetzte Umbrüche tragen in Specs, ADRs und Doku Absatzstruktur.
- **Jede Automatisierung, die Formatierung bei Dateiänderung oder Commit auslöst.** Verbindliche
  Randbedingung aus der Story; die Abwesenheit wird per Wächtertest gehalten.
- **Ein Wechsel auf `oxfmt`.** Bleibt nach dessen 1.0 als eigene Story offen; er kostet dann
  dieselbe Art Handgriff wie diese Einführung.
- **Inhaltliche Änderungen an formatiertem Code.** Die Durchformatierung ist rein maschinell; die
  einzige Ausnahme ist der eine nachzuführende Ausschnitt im Design-Vertragstest (Abschnitt 7).
- **Eine Lockerung bestehender Lint- oder Typregeln.** Angepasst wird allein die E501-Grenze auf
  110, und zwar weil der Formatierer selbst die eine betroffene Zeile erzeugt.
