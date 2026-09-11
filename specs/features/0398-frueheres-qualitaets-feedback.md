# 0398 - Früheres Qualitäts-Feedback

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** https://github.com/TheRealKoller/photosort/issues/398

**Umfang:** rund 394 statt der Richtwert-200 Zeilen. Grund: Das Ergebnis dieser Story ist eine
*Entscheidung*, deren Prüfgegenstand ausschließlich aus Zusicherungen besteht — fünfzehn
Akzeptanzkriterien, die je den Nachweis mitführen, an dem sie gemessen werden, und drei
Muss-Auflagen gegen genau einen Fehlermodus (den falsch-grünen Prüflauf), der unbemerkt bliebe,
wenn er nur gemeint statt aufgeschrieben wäre. Dazu die Auflösung eines Widerspruchs zwischen zwei
dieser Zusicherungen (K10 gegen S3) — eine bewusste Abweichung, die vom Kürzen ausgenommen ist.
Gekürzt wurde vorher um die historische Herleitung im Ziel und die Edge-Case-Liste, die die
Kriterien wiederholte.

## Ziel

Verstöße gegen Lint- und Typprüfung fallen heute spät auf: `.claude/agents/developer.md` prüft in
Schritt 3 erst nach Abschluss aller TDD-Zyklen, sonst bemerkt sie erst die CI. Beides kostet einen
Nachbesserungszyklus zu einem Zeitpunkt, an dem der Arbeitskontext schon weitergezogen ist.
Nutznießer sind Daniel und die entwickelnden Agenten; für Nutzer von PhotoSort ändert sich nichts.

Das Problem ist der **Zeitpunkt** der Rückmeldung, nicht die Anzahl der Aufrufe: Geprüft wird etwa
einmal je Feature-Lauf, nicht je Dateiänderung.

Die Story war bewusst ergebnisoffen geschnitten — automatisch feuernde Hooks waren eine Option
unter mehreren, ein begründetes „nein" ein zulässiges Ergebnis. Die Abwägung ist getroffen und
steht in ADR [`0083`](../decisions/0083-frueheres-qualitaets-feedback-ein-pruefbefehl-und-ein-pruefpunkt-je-tdd-einheit.md).

Bei der Ausarbeitung ist eine Lücke aufgefallen, die unabhängig vom Ausgang zu schließen war:
`.claude/agents/developer.md` kennt die mit Spec [`0400`](./0400-einheitliche-code-formatierung.md)
eingeführte Formatprüfung nicht. Sie blockiert seit PR #409 in allen vier CI-Jobs, steht aber in
keiner verwalteten Datei unter `.claude/`. Ein Lauf, der Schritt 3 wörtlich folgt, liefert einen
Branch ab, dessen Formatprüfung lokal nie gelaufen ist.

## User Story

Als Entwickler an PhotoSort (Daniel oder ein entwickelnder Agent) möchte ich, dass Verstöße gegen
Lint- und Typprüfung unmittelbar nach einer Dateiänderung sichtbar werden, damit ich sie im
laufenden Arbeitskontext behebe, statt sie am Ende eines Feature-Laufs oder erst nach einem
CI-Durchlauf aufzuräumen.

## Akzeptanzkriterien

Die Kriterien tragen die Schärfungen des `test-engineer` (Prüfbarkeit) und die vier Auflagen des
`security-engineer` (S1–S3 in K7/K8/K11, S4-Konformität in K11). Wo die Story ein Kriterium als
Wirkung formuliert hatte, steht jetzt der Nachweis, an dem die Wirkung gemessen wird. Zuordnung zu
den Issue-Kriterien: 1→K1, 2→K2, 3→K3, 4→K4 + K8/K9, 5→K5, 6→K6/K7, 7→K14.

- [ ] **K1** Die Entscheidung liegt als eigene ADR unter `specs/decisions/` (Status `Accepted`);
      der Abschnitt „Architektur / Umsetzung" verweist auf sie. Ein begründetes „nein" hätte das
      Kriterium ebenso erfüllt. *(Geschärft nur auf Ablageort und Verweis. **Bewusst ohne
      Wächtertest**: „ist begründet" ist eine Aussage über Prosa; jede maschinelle Fassung prüfte
      eine Formulierung — Präzedenz Spec 0400 K9. Geprüft im `review-requirements`-Durchlauf.)*
- [ ] **K2** Die ADR wägt die drei Wege (a) automatisch feuernde Prüfungen, (b) gebündeltes
      Prüfkommando, (c) häufigeres Prüfen im dokumentierten Ablauf gegeneinander ab — je
      mindestens ein Grund dafür und einer dagegen, und für (a) ausdrücklich der TDD-Grund: Ein
      Test gegen eine noch nicht existierende Funktion ist per Konstruktion ein `mypy`-Fehler, die
      Rot-Phase ist also absichtlich rot. *(Geschärft: „abgewogen" wird durch die Mindestform je
      Weg entscheidbar. Ohne Wächtertest, Begründung wie K1.)*
- [ ] **K3** Die ADR benennt je Arbeitsumgebung ausdrücklich, ob die Lösung wirkt: (i)
      Haupt-Checkout mit installierten Entwicklungsabhängigkeiten, (ii) **verbundener Arbeitsbaum**
      (`git worktree`) — die Regellage der Hintergrund-Läufe, in dem heute weder `backend/.venv`
      noch `frontend/node_modules` liegen, (iii) Cloud-Session, (iv) die Nicht-Wirkung einer
      ausschließlich lokal hinterlegten Konfiguration auf fremde Sessions. *(Geschärft: Die
      Umgebungsliste war offen; (ii) fehlte ganz und ist die Umgebung, in der die Lösung ohne
      Gegenmaßnahme nicht greift — siehe K10.)*
- [ ] **K4** Die ADR legt fest: Ein fehlschlagender Prüflauf **meldet nur** — er unterbricht die
      laufende Arbeit nicht und verändert keine Datei. *(Die maschinelle Hälfte dieser Zusage steht
      in K7 und K8; hier bleibt die Festlegung als Text.)*
- [ ] **K5** Es entsteht keine eingecheckte Datei, die ohne Zutun des Agenten ein Kommando
      ausführt. Maschinell gefasst durch die vier Musterfamilien in
      `scripts/tests/test_keine_automatische_formatierung.py`; für diese Story vor allem
      `.claude/settings.json` mit Schlüssel `hooks` und die Git-Hook-Familien. **Kein neuer
      Testcode** — Nachweis ist ein Lauf dieses Moduls auf dem fertigen Branch mit null Befunden,
      als Messung im Abschlussbericht. Der Modul-Docstring bekommt einen Satz, dass er ab jetzt
      auch diese Zusage trägt. *(Geschärft: „keine Datei, die X tut" ist nicht entscheidbar, die
      vier Familien sind es. Der Docstring-Zusatz ist nicht Kosmetik — ohne ihn kann ein späterer
      Zuschnitt des Moduls auf „Formatierung" die einzige mechanische Zusage dieser Story still
      mitnehmen.)*
- [ ] **K6** `scripts/check.sh` existiert, ist ausführbar (Ausführungsbit im Commit) und ruft in
      **einem** Lauf genau diese **zehn** Prüfungen auf, je mit dem Baum als Arbeitsverzeichnis —
      `backend`: `ruff format --check .`, `ruff check .`, `mypy src`; `scripts`:
      `ruff format --check .`, `ruff check .`; `frontend`: `npm run format:check`, `npm run lint`,
      `npm run typecheck`; `e2e`: `npm run format:check`, `npm run typecheck`. Zugesichert wird die
      **vollständige, geordnete Aufrufliste samt Argumenten wörtlich**, nicht der Ausgang allein.
      *(Geschärft: „prüft alle vier Bäume" ist an einem Exit-Code nicht von „ruft gar nichts auf"
      zu unterscheiden. Zehn, nicht neun — an `.github/workflows/ci.yml` nachgezählt. Argumente
      wörtlich, weil ein zusätzliches `--max-warnings 0`, ein `--output-format=github` oder ein
      verlorenes `:check` sonst unbemerkt bliebe: `check.sh` wäre dann strenger als die CI oder
      schreibend.)*
- [ ] **K7** `check.sh` schreibt nie. Keine aufgezeichnete Aufrufform trägt `ruff format` ohne
      `--check` oder `npm run format` ohne `:check`; im Skripttext (ganzzeilige Kommentare zuvor zu
      Leerzeilen normalisiert) steht kein `--write`, `--fix`, `--unsafe-fixes` und kein
      `format.sh`. *(Geschärft auf beide Ebenen — Text **und** Aufzeichnung. Ein verlorenes
      `--check`/`:check` ist der teuerste stille Fehler dieses Skripts: Es schriebe mitten im
      TDD-Zyklus Dateien um, und der Lauf endete trotzdem mit 0.)*
- [ ] **K8** Drei Ausgänge, tragend getrennt — und Ausgang `0` wird **verdient, nicht durch
      Abwesenheit erreicht**: Das Skript zählt die tatsächlich abgeschlossenen Prüfläufe mit.
      `0` = alle zehn gelaufen und grün; `1` = mindestens ein Baum ungeprüft, bei den geprüften
      kein Befund; `2` = mindestens ein Befund (auch dann, wenn zusätzlich ein Baum ungeprüft
      blieb — ein Befund löst Handlungsbedarf aus, und die Bilanz nennt den ungeprüften Baum
      ohnehin). Die Sammlung der Rückgabewerte steht als `if ! …; then`, nie als `bilanz=$?` hinter
      einem Befehl; `set +e` kommt nicht vor. Für **jede der zehn Prüfungen einzeln** ist
      nachgewiesen, dass ihr Fehlschlag zu Ausgang 2 führt und die Bilanz genau dieses
      (Baum, Prüfung)-Paar nennt und kein grünes. *(Geschärft: „meldet Befunde" ist schon durch
      einen einzigen korrekt verdrahteten Aufruf erfüllt — neun blinde Stellen blieben
      unentdeckt. Der Zähler ist Auflage S1 des `security-engineer`: Ohne ihn entsteht die 0 aus
      dem Ausbleiben von Befunden, und jeder Pfad, auf dem eine Prüfung gar nicht stattfindet —
      nicht erreichte Schleife, gescheitertes `cd`, unter `set -e` unerreichbare Bilanzzeile —,
      meldet „geprüft und sauber". Das ist der einzige Fehlermodus, den niemand bemerkt. Ein
      textuelles `|| true`-Verbot ist ausdrücklich **nicht** Teil der Auflage:
      `command -v ruff || true` und `grep -c '' || true` sind aus `scripts/format.sh` übernommene,
      legitime Bausteine.)*
- [ ] **K9** Ein roter Baum bricht den Lauf nicht ab: Schlägt die erste Prüfung fehl, laufen die
      übrigen neun vollständig, und die Bilanz nennt alle roten Paare. Zugleich steht
      `set -euo pipefail` im Skripttext. *(Geschärft: Beide Hälften gehören zugesichert, weil sie
      einander scheinbar widersprechen — ohne die erste ist der Sammellauf weg, ohne die zweite der
      Abbruch bei einem echten Skriptfehler.)*
- [ ] **K10** Vorbedingungen werden je Baum vor dem ersten Prüfaufruf dieses Baums geprüft. Ein
      Baum mit verletzter Vorbedingung wird **übersprungen und ausdrücklich als „nicht geprüft"
      gemeldet**, mit Nennung des Baums und des Handgriffs (`npm ci` wörtlich, nicht
      `npm install`); die übrigen Bäume werden trotzdem vollständig geprüft. Nachgewiesen auch für
      eine Verletzung im **letzten** Baum und für den Fall, dass **alle vier** Bäume betroffen
      sind. *(Entscheidung Daniels vom 2026-09-11 — Teilprüfung je Baum statt Komplettabbruch. Im
      verbundenen Arbeitsbaum fehlen `node_modules` und `.venv` (gemessen); genau dort arbeitet der
      `developer`-Agent, für den der Prüfpunkt gedacht ist. Ein Komplettabbruch ließe den Nutzen
      der Story beim Hauptnutznießer leerlaufen, und ein Agent, der zehnmal denselben Ausgang 1
      sieht, hört auf hinzusehen. Die tragende Trennung „nicht geprüft" gegen „sauber" überlebt
      vollständig in K8 und wird dadurch sogar sichtbarer.)*
- [ ] **K11** Kein Werkzeug wird aufgerufen, dessen Verfügbarkeit nicht vorher festgestellt wurde,
      und geprüft wird mit genau dem festgestellten Binary: (a) der stille Fall „leerer Pin gegen
      leere Versionsausgabe" wird für `check.sh` **eigenständig** geprüft, nicht aus
      `test_format_sh.py` geerbt; (b) Phase 2 ruft dasselbe `ruff` auf, dessen Version Phase 1
      geprüft hat (`<baum>/.venv/bin/` vor PATH); (c) `mypy` und die aufgerufenen npm-Skriptnamen
      sind ebenfalls Vorbedingung — ein fehlendes Werkzeug macht seinen Baum „nicht geprüft", nie
      „Befund". Die Pin-Extraktion folgt `scripts/format.sh` wörtlich: verankert,
      zeichenklassenbegrenzt, Abbruch bei leerem oder mehrdeutigem Leseergebnis, der gelesene Wert
      wird ausschließlich verglichen. *(Erweitert den ursprünglichen Entwurf. (a): `check.sh` ist
      eine **zweite Kopie** der Extraktionslogik — ein grüner Test im Nachbarmodul sagt über die
      Kopie nichts. (b): Version von `.venv/bin/ruff` geprüft und dann PATH-`ruff` aufgerufen wäre
      still falsch. (c): Ohne diese Erweiterung wäre die tragende Trennung nur für zwei der vier
      Werkzeuge eingelöst — ein fehlendes `mypy` landete als Befund in der Bilanz, ununterscheidbar
      von echten Typfehlern.)*
- [ ] **K12** `check.sh` ist aus jedem Arbeitsverzeichnis heraus aufrufbar und leitet die vier
      Bäume aus seinem eigenen Ablageort ab, nicht aus dem `cwd`.
- [ ] **K13** `.claude/agents/developer.md` nennt `scripts/check.sh` wörtlich und **genau
      zweimal**: einmal in Schritt 2 nach dem Refactor-Teilschritt und vor dem Commit der Einheit,
      einmal in Schritt 3. Ort und Reihenfolge über Zeichenoffsets innerhalb der Abschnitte
      (Vorbild: `MARKE_*` in `scripts/tests/test_main_abgleich_verdrahtung.py`), mit Selbstschutz:
      Werden die Abschnittsüberschriften oder die Ordnungsmarken nicht gefunden, scheitert der Test
      laut statt still. In `developer.md` steht danach **keines** der zehn Befehlsliterale mehr.
      Für den übrigen Suchraum `.claude/` wird die heutige Fundstellenmenge über `git ls-files`
      **gemessen**, bevor eine Abwesenheit dorthin ausgedehnt wird. Ausdrücklich **nicht** gebaut:
      ein Prüfer, der aus der Prosa herausliest, dass der Befehl tatsächlich läuft. *(Geschärft:
      „nicht mehr als Aufzählung neben dem Skriptnamen" ist Prosa; Kardinalität plus Ort ist
      prüfbar. Die Messung vor der Ausdehnung, weil eine Pfad-Ausnahme laut Testkonzept die letzte
      Wahl ist — ein rot startender Wächter auf einer fremden Skill-Datei wäre genau das.)*
- [ ] **K14** `docs/setup.md` nennt `scripts/check.sh` wörtlich, verweist für die Vorbedingungen
      auf den `format.sh`-Abschnitt statt sie zu wiederholen, und sagt je Ausgang (0/1/2), was zu
      tun ist — samt dem Satz, dass nichts automatisch läuft und der Befehl folglich nichts
      abzuschalten hat. *(Geschärft auf den wörtlichen Pfad. **Bewusst ohne Wächtertest** —
      Präzedenz Spec 0400 K9: eine Doku-Bindung wäre hier Formulierungspolizei.)*
- [ ] **K15** Der Umzug des Spielplatzes nach `scripts/tests/conftest.py` ändert keine Zusicherung
      von `test_format_sh.py`: gleiche Testfunktionen (Namen und Anzahl), Modul grün — **und** die
      im Modul-Docstring dokumentierte Mutationsprobe wird nach dem Umzug wiederholt (alle drei
      Wächter aus `format.sh` entfernt → genau
      `test_leerer_pin_und_leere_versionsausgabe_bestehen_nicht_gegeneinander` wird rot).
      *(Geschärft: „vorher und nachher grün" ist die schwächere Hälfte. Ein umgezogenes Fixture
      kann grün und zugleich zahnlos sein — etwa wenn die Attrappe die Versions-Umgebungsvariable
      nach der Parametrisierung nicht mehr auswertet. Dann bestehen alle Tests aus dem falschen
      Grund.)*

## Datenmodell-Bezug

Keiner. Die Story fügt ein Skript, eine Testdatei und Dokumentationsänderungen hinzu; es entsteht,
entfällt und verändert sich keine Entität, keine Tabelle und keine Migration.
`docs/architecture.md` bleibt unberührt.

## Architektur / Umsetzung

**Entscheidung:** ADR [`0083`](../decisions/0083-frueheres-qualitaets-feedback-ein-pruefbefehl-und-ein-pruefpunkt-je-tdd-einheit.md).
Weg (a) — Prüfungen, die nach einer Dateiänderung automatisch feuern — wird verworfen, in der
eingecheckten wie in der lokalen Ausprägung. Gebaut werden (b) `scripts/check.sh` und (c) ein
Prüfpunkt je TDD-Einheit im `developer`-Ablauf. Die Abwägung steht in der ADR und wird hier nicht
wiederholt.

### Betroffene und neue Dateien

| Datei | Art | Was |
|---|---|---|
| `scripts/check.sh` | neu | Prüft alle vier Bäume in einem Aufruf. Ausführungsbit im Commit. |
| `scripts/tests/test_check_sh.py` | neu | Verhalten des Skripts **und** Verankerung in `developer.md`. CI-Job `demo-scripts`. |
| `scripts/tests/conftest.py` | geändert | Nimmt den Spielplatz-Aufbau aus `test_format_sh.py` auf (Schritt 1). |
| `scripts/tests/test_format_sh.py` | geändert | Nur der Umzug; keine Zusicherung wird angefasst (K15). |
| `.claude/agents/developer.md` | geändert | Schritt 2 bekommt den Prüfpunkt, Schritt 3 den Skriptnamen statt der Befehlsaufzählung. |
| `docs/setup.md` | geändert | Prüfbefehl neben dem Formatierbefehl, je Ausgang ein Handgriff. |
| `specs/architecture/0003-securitykonzept.md` | geändert | Abschnitt 4, Zeilen 762–766 (Schritt 8). |

Nicht angefasst: `.github/workflows/ci.yml`, `CLAUDE.md`, `docs/architecture.md`,
`scripts/format.sh`, `scripts/tests/test_keine_automatische_formatierung.py`.

### Die zehn Prüfbefehle

| Baum | Befehle |
|---|---|
| `backend/` | `ruff format --check .`, `ruff check .`, `mypy src` |
| `scripts/` | `ruff format --check .`, `ruff check .` |
| `frontend/` | `npm run format:check`, `npm run lint`, `npm run typecheck` |
| `e2e/` | `npm run format:check`, `npm run typecheck` |

3 + 2 + 3 + 2 = **zehn**. Die Zahl ist tragend (K8), die Liste steht deshalb **literal** im Test —
nie als Ableitung aus „der CI-Reihenfolge". Die stimmt nur innerhalb eines Baums: Die CI läuft
`backend` → `frontend` → `demo-scripts` → `e2e`, `check.sh` läuft `backend` → `scripts` →
`frontend` → `e2e` (Python vor TypeScript, wie `format.sh`).

Kein `--output-format=github` (CI-eigen). Keine Tests, kein Build, keine `docker compose`-Prüfung,
kein `e2e`-Lauf. `npm run lint` erbt oxlints heutiges Verhalten unverändert (Warnungen, Exit 0) —
`check.sh` ist nirgends strenger als die CI.

**Die vier TypeScript-Prüfungen laufen ausschließlich als `npm run <skript>`** (S2), nie als
direkter `prettier`-/`tsc`-/`oxlint`-Aufruf: `--ignore-path ../.prettierignore` steckt im
npm-Skript, und diese Datei ist seit ADR 0080 die einzige Ausschlussquelle für Prettier. Was ein
direkter Aufruf aus `e2e/` heraus ins Protokoll druckt, steht im Abschnitt „Security".

### Aufbau des Skripts

**Phase 1 — Vorbedingungen, alle vier Bäume, bevor der erste Prüfbefehl läuft.** Das ist strenger
als K10 verlangt (dort: vor dem ersten Aufruf *dieses* Baums) und bewusst so: Wer erst am Ende
erfährt, dass zwei Bäume fehlten, hat die Ausgabe dazwischen unter falscher Annahme gelesen.

| Baum | Vorbedingung |
|---|---|
| `backend/`, `scripts/` | `ruff`-Binary auflösbar (`<baum>/.venv/bin/` vor PATH) **und** seine Version == dem aus `<baum>/pyproject.toml` gelesenen Pin |
| `backend/` | zusätzlich: `mypy`-Binary auflösbar, gleiche Auflösungsreihenfolge |
| `frontend/`, `e2e/` | `node_modules` vorhanden **und** die aufgerufenen Skriptnamen stehen in `package.json` |

Die Pin-Extraktion folgt `format.sh` wörtlich: verankert, zeichenklassenbegrenzt, Abbruch bei
leerem **oder** mehrdeutigem Leseergebnis, der gelesene Wert wird ausschließlich verglichen. Die
Prüfung der npm-Skriptnamen liest ebenso verankert und zeichenklassenbegrenzt aus `package.json`
und wertet **nur die Anwesenheit** des Schlüssels aus — der gelesene Wert wird nie benutzt. Kein
Parsen von `npm run`-Ausgabe.

Ein Baum mit verletzter Vorbedingung wird **übersprungen**, ausdrücklich als „nicht geprüft"
gemeldet (Baum + Handgriff, `npm ci` wörtlich) und erhöht den Zähler nicht. Die übrigen laufen.

**Phase 2 — Durchlauf mit Zähler.** Jeder der zehn Aufrufe steht als `if ! …; then befund…; fi`,
nie als `bilanz=$?` dahinter; `set +e` kommt nicht vor; `set -euo pipefail` steht im Skript.
Phase 2 ruft **dasselbe Binary**, das Phase 1 aufgelöst und geprüft hat (Array je Baum, wie
`RUFF_BINARIES` in `format.sh`) — geprüft und aufgerufen dürfen nicht auseinanderfallen. Ein roter
Baum bricht nichts ab.

**Bilanz und Ausgänge.** Am Ende: die roten `(Baum, Prüfung)`-Paare **und** die ungeprüften Bäume.

| Exit | Bedingung |
|---|---|
| `0` | Zähler `== 10` **und** kein Befund |
| `1` | kein Befund, aber Zähler `< 10` |
| `2` | mindestens ein Befund — **auch** wenn zusätzlich ein Baum ungeprüft blieb |

Der Gleichstand geht an `2`, weil Exit-Codes nach erforderlicher Handlung ordnen: Ein Befund
verlangt eine Änderung am **Arbeitsstand**, `1` nur eine an der **Umgebung**. Die Reihenfolge ist
selbstkorrigierend — wer `2` bekommt, behebt und läuft erneut und sieht danach `1`. Umgekehrt ginge
die Information verloren: Wer `1` bekäme, installierte `node_modules`, meldete „war nur die
Umgebung" — und der Befund stand die ganze Zeit da.

### Reihenfolge der Umsetzung

1. **Spielplatz nach `conftest.py` ziehen.** `test_format_sh.py` baut bereits einen temporären
   Repo-Abzug mit aufzeichnenden Attrappen auf isoliertem `PATH`; `test_check_sh.py` braucht
   denselben Aufbau plus eine `mypy`-Attrappe. Zu parametrisieren: aufzurufendes Skript, Menge der
   Attrappen, erwartete Bäume. **Leitplanke (K15):** reiner Umzug — gleiche Testfunktionen nach
   Namen und Anzahl, Modul grün, und die im Docstring dokumentierte Mutationsprobe wird
   **wiederholt**. Muss eine Zusicherung geändert werden, ist der Umzug falsch geschnitten und wird
   zurückgenommen statt angepasst.
2. **Phase 1**, testgetrieben: Pin-Vergleich je Python-Baum, `node_modules`, `mypy`,
   npm-Skriptnamen. Der stille Fall — leerer Pin gegen leere Versionsausgabe — wird für `check.sh`
   **eigenständig** geprüft (K11a); `check.sh` ist eine zweite Kopie der Extraktionslogik, ein
   grüner Test im Nachbarmodul sagt über sie nichts.
3. **Teilprüfung**: übersprungener Baum, Meldung, Zähler unverändert. Nachweise auch für eine
   Verletzung im **letzten** Baum und für **alle vier** betroffen (K10).
4. **Phase 2 mit Zähler und Bilanz.** Je Prüfung **einzeln** nachweisen, dass ihr Fehlschlag zu
   Ausgang `2` führt und die Bilanz genau dieses Paar nennt (K8) — zehn Fälle, nicht einer.
   **Falle:** `set -euo pipefail` muss im Text stehen, darf aber keinen der zehn Aufrufe abbrechen;
   deshalb die `if ! …`-Form.
5. **Statische Totalverbote am wirksamen Skripttext** (ganzzeilige Kommentare vorher zu Leerzeilen,
   sonst macht der Kopfkommentar die Prüfung rot, die er erklärt), im Muster von
   `test_format_sh.py` Abschnitt 1: `eval`, `uvx`, `pip install`, `uv pip`, `--write`, `--fix`,
   `--unsafe-fixes`, `format.sh`, `npx`, `prettier`, `--ignore-path`, `git `, `hooksPath`,
   `.git/hooks`, `settings.json` — dazu `npm ci` und `npm install` an der Ausführungsposition
   statt am Skripttext, samt Gegenprobe (Begründung in S3). Dazu Ausführbarkeit, `set -euo pipefail`,
   kein `set +e`, kein `bilanz=$?`, und der Selbstschutz gegen einen leeren Skripttext.
   Ausdrücklich **kein** textuelles `||`-Verbot: `command -v ruff || true` und `grep -c '' || true`
   sind aus `format.sh` übernommene, legitime Bausteine. Eine Selbst-Ausnahme wie in
   `test_keine_automatische_formatierung.py` braucht es nicht — die Liste gilt nur für
   `scripts/check.sh`, nicht repoweit.
6. **`.claude/agents/developer.md`.** Schritt 2 bekommt den Prüflauf nach „Refactor" und vor dem
   Commit der Einheit; Schritt 3 ersetzt seine vier Beispielbefehle durch den Skriptnamen (der Satz
   „im Zweifel die tatsächlich konfigurierten Befehle aus …" entfällt — das Skript *ist* diese
   Befehle). Schritt 4 bleibt unverändert vollständig bestehen.
7. **Verankerung** im selben Testmodul (K13): Skriptpfad wörtlich und **genau zweimal**, Ort und
   Reihenfolge über Zeichenoffsets (Vorbild `MARKE_*` in `test_main_abgleich_verdrahtung.py`), mit
   Selbstschutz — werden Überschriften oder Ordnungsmarken nicht gefunden, scheitert der Test laut
   statt still. Keines der zehn Befehlsliterale steht danach noch in `developer.md`. Für den
   übrigen Suchraum `.claude/` wird die heutige Fundstellenmenge **gemessen**, bevor eine
   Abwesenheit dorthin ausgedehnt wird.
8. **`specs/architecture/0003-securitykonzept.md`**, Abschnitt 4, Zeilen 762–766 — Eigentümer ist
   der `security-engineer`, die Änderung ist von ihm vorgegeben und hier nur auszuführen: (i)
   Überschrift vom Einzelfall `format.sh` auf die **Musterform** heben, weil das Muster mit
   `check.sh` zum zweiten Mal auftritt; (ii) „wie in den **drei bestehenden** Skripten" → „in
   **jedem** Skript unter `scripts/`", weil eine mitgezählte Zahl still veraltet; (iii) vierter
   Punkt: *Der Ausgang eines prüfenden Skripts wird verdient, nicht durch Abwesenheit erreicht.*
   Hat bewusst kein eigenes Akzeptanzkriterium — es ist Doku-Pflege, keine Zusicherung.
9. **`docs/setup.md`** (K14): `scripts/check.sh` wörtlich, für die Vorbedingungen auf den
   `format.sh`-Abschnitt verweisen statt sie zu wiederholen, je Ausgang (0/1/2) ein Handgriff, der
   Satz dass nichts automatisch läuft und der Befehl folglich nichts abzuschalten hat — und der
   Hinweis, dass Ausgang `1` im verbundenen Arbeitsbaum der **Normalfall** ist.
10. **Nachweis der Randbedingung** (K5), als Messung im Abschlussbericht statt als neuer Testcode:
    die vier Familien aus `test_keine_automatische_formatierung.py` laufen auf dem fertigen Branch
    und melden null Befunde. Begründung, warum nicht erweitert wird: ADR 0083 Abschnitt 7.

### Entwurfsentscheidungen, die nicht neu zu treffen sind

- **Zwei Skripte, kein Modus.** Kein `format.sh --check`; `check.sh` ruft `format.sh` nie auf.
- **Fester Umfang**, kein Bereichs-Argument. `./scripts/check.sh` ohne Parameter.
- **Es wird nie geschrieben, nie repariert, nie unterbrochen** — gemeldet und beendet.
- **Bäume aus `BASH_SOURCE`**, nicht aus dem `cwd` (K12), wie `format.sh`.
- **Teilprüfung statt Komplettabbruch**; `0` nur bei Zähler `== 10`; Gleichstand geht an `2`.

## UI/UX

Nicht relevant — die Story berührt ausschließlich den Entwicklungsablauf (Prüfkommando,
Agenten-Ablaufdatei, Setup-Dokumentation). Es gibt keine Stelle, an der etwas angezeigt oder
eingegeben wird, und keine Datei unter `frontend/src/` im Umfang.

## Security

Sicherheitsrelevant, aber schmal: kein Endpunkt, keine Änderung an Auth, Berechtigungen oder
Datensichtbarkeit, kein Secret, keine neue Abhängigkeit, kein Datenmodellbezug, kein Laufzeitanteil.
Betroffen ist ausschließlich die Arbeitsweise der Entwicklung, deren Integrität das
Sicherheitskonzept als eigenes Asset führt — dieselbe Einstufung wie bei Spec 0395 und 0400. Der
einzige Schadensfall dieser Story ist ein **falsch-grüner Prüflauf**.

**S1 — Ausgang 0 wird verdient, nicht durch Abwesenheit erreicht (Muss).** `scripts/check.sh` zählt
die abgeschlossenen Prüfläufe mit; Ausgang `0` gilt nur bei Zähler `== 10` **und** null Befunden.
Ohne diesen Zähler entsteht die 0 aus dem Ausbleiben von Befunden, und jeder Pfad, auf dem eine
Prüfung gar nicht stattfindet — nicht erreichte Schleife, gescheitertes `cd`, unter `set -e`
unerreichbare Bilanzzeile —, meldet „geprüft und sauber". Das ist der einzige Fehlermodus, den
niemand bemerkt. Die Sammlung der Rückgabewerte steht als `if ! …; then`, nie als `bilanz=$?` hinter
einem Befehl; `set +e` kommt nicht vor. Ein textuelles `|| true`-Verbot ist ausdrücklich nicht Teil
der Auflage: `command -v ruff || true` und `grep -c '' || true` sind aus `scripts/format.sh`
übernommene, legitime Bausteine. Derselbe Zähler trägt die Teilprüfung aus K10: Er ist die Stelle,
an der ein übersprungener Baum sichtbar wird, statt in einer grünen Bilanz zu verschwinden.

**S2 — Die vier TypeScript-Prüfungen laufen ausschließlich als `npm run <skript>` (Muss).** Nie als
direkter `prettier`-/`tsc`-/`oxlint`-Aufruf. `--ignore-path ../.prettierignore` steckt im
npm-Skript, und `/.prettierignore` ist seit Spec 0400 die einzige Ausschlussquelle für Prettier.
Ein direkter Aufruf aus `e2e/` stiege in `e2e/.auth/` ab; bei einem Parse-Fehler auf einer halb geschriebenen
`state.json` steht der dort gespeicherte, 30 Tage gültige und nicht widerrufbare JWT im Code-Frame
und damit im Protokoll des Laufs.

**S3 — Das Skript installiert nichts, schreibt nichts und ruft `git` nicht auf (Muss).** Die
statische Verbotsliste in `scripts/tests/test_check_sh.py` greift an **zwei Textebenen**, und der
Unterschied ist nicht Bequemlichkeit, sondern die Auflösung eines echten Widerspruchs zwischen
dieser Auflage und K10:

- **Total am wirksamen Skripttext** (ganzzeilige Kommentare zu Leerzeilen normalisiert):
  `eval`, `uvx`, `pip install`, `uv pip`, `npx`, `prettier`, `--ignore-path`, `git `, `hooksPath`,
  `.git/hooks`, `settings.json`. Das `git `-Totalverbot ist bewusst total statt
  kontextanalysierend: `check.sh` hat keinen legitimen Grund, `git` aufzurufen, denn die Bäume
  leitet es wie `format.sh` aus `BASH_SOURCE` ab.
- **An der Ausführungsposition** (zusätzlich der Inhalt einfach gequoteter Zeichenketten je Zeile
  geleert): `npm ci` und `npm install`. `npm ci` wäre die naheliegende „Reparatur" der
  `node_modules`-Vorbedingung und ist genau das, was ein übersprungener Baum bewusst nicht tut —
  **zugleich verlangt K10 denselben String wörtlich in der Meldung**. Ein Totalverbot am
  Skripttext machte beide Zusicherungen zusammen unerfüllbar. Tragfähig ist die Ausführungsebene,
  weil `eval` selbst verboten ist: Ohne `eval` führt aus einem gequoteten Zeichenkettenliteral
  kein Weg zu einem ausgeführten Befehl.
- **Gegenprobe, ohne die das Verbot die falsche Hälfte belohnte:** Ein Test sichert, dass der
  Skripttext `npm ci` weiterhin **enthält**. Sonst wäre die bequemste Art, das Verbot zu
  erfüllen, den Handgriff aus der Meldung zu streichen — und der Aufrufer im verbundenen
  Arbeitsbaum wüsste nicht, was zu tun ist.

Die Regel gilt ab jetzt projektweit und steht in `specs/architecture/0002-testkonzept.md`
(„Zwei Textebenen für statische Verbote").

**S4-Konformität.** Die Pin-Extraktion folgt `scripts/format.sh` wörtlich: verankert,
zeichenklassenbegrenzt, Abbruch bei leerem oder mehrdeutigem Leseergebnis, der gelesene Wert wird
ausschließlich verglichen. `set -euo pipefail`. Der stille Fall („beide Seiten leer, der Vergleich
besteht") bekommt einen eigenen Spielplatz-Test; ein Leerstring-Fall, der die Gegenseite gefüllt
lässt, prüft ihn nicht.

**Restrisiko, bewusst getragen — der PATH-Rückfall für `ruff`.** Fehlt `<baum>/.venv/bin/ruff`, wird
`command -v ruff` genommen, identisch zu `scripts/format.sh`. Ein manipuliertes `ruff` auf dem PATH
könnte einen Lauf still grün machen. Getragen, weil wer dort schreiben kann auch in `.venv/bin/`
schreiben kann und ohnehin beliebigen Code auf diesem Rechner ausführt, und weil `check.sh` kein
Gate ist: Autorität bleibt die CI mit denselben Pins in fremder Umgebung. Eine abweichende,
strengere Auffindung nur hier brächte keinen Gewinn und zerbräche die Gleichheit mit `format.sh`, an
der die S4-Zusicherung hängt.

**`npm run` als Angriffsfläche: keine Änderung gegenüber heute.** `check.sh` ruft dieselben Skripte
auf, die heute von Hand und in CI laufen; `format.sh` ruft mit `npm run format` bereits eines davon.
Die Fläche ist `node_modules` plus `package.json` des ausgecheckten Standes und entsteht bei
`npm ci`, nicht beim Aufruf. Zu benennen ist eine Verschiebung der **Häufigkeit**, nicht der Fläche:
Ein gebündelter Reflexbefehl wird öfter und früher gefahren, auch unmittelbar nach einem Checkout.
Das Sicherheitskonzept setzt unter S4 bereits voraus, dass auf einem Rechner gearbeitet wird, auf
dem auch ein fremder PR-Branch ausgecheckt sein kann.

**Randbedingung „keine eingecheckte Datei steuert Sessions automatisch".** `scripts/check.sh` fällt
unter keine der vier Musterfamilien von `scripts/tests/test_keine_automatische_formatierung.py`:
kein Hook-Pfad, `stem`/`name` nicht in `GIT_HOOK_NAMEN`, keine Konfigurationsdatei und keine
Abhängigkeit, keine scharf schaltende `core.hooksPath`-Form. Eine fünfte Familie entsteht nicht —
die vier Familien prüfen repoweite **Form**, „dieses Skript installiert keinen Hook" ist eine
**Verhaltens**aussage über eine Datei und steht als Totalverbot in deren eigenem Test (S3).
Nachzuweisen ist auf dem fertigen Branch, dass alle vier Familien grün laufen; der Lauf gehört in
den Abschlussbericht. Bemerkenswert dabei: Der verworfene Weg (a) ist in seiner realistischsten Form
bereits maschinell gesperrt — ein „feuert nach einer Dateiänderung automatisch" hieße hier ein
`PostToolUse`-Eintrag, also ein Schlüssel `hooks` in einem eingecheckten `.claude/settings.json`,
genau der Köder in Familie 3.

Der Prüfpunkt in `.claude/agents/developer.md` ist von der Randbedingung nicht berührt, und die
Abgrenzung steht hier, weil sie sonst später bestritten wird: Die Datei **ist** eingecheckt und
steuert Sessionverhalten. Der Unterschied ist nicht die Wirkung, sondern der Ausführende — ein
Harness-Hook läuft ohne Zutun und ohne Kenntnis des Agenten und schreibt an einem Stand, den der
Aufrufer gerade geprüft hat; ein Ablaufschritt in einer Agentendatei wird von einer Rolle gelesen
und bewusst befolgt, wirkt nur in Sessions, die diese Rolle aufrufen, und schreibt nichts von
selbst. Spec 0395 hat dieselbe Abgrenzung bereits gezogen.

**Ausdrücklich nicht sicherheitsrelevant:** die Bündelung als solche, die Reihenfolge der zehn
Befehle, der Prüfpunkt je TDD-Einheit, und eine künftige Abweichung zwischen `check.sh` und der
CI-Schrittliste (Wartungs-, kein Sicherheitsthema). Ausgang 0 heißt „Format, Lint und Typen
sauber", nicht „CI wird grün"; die Ausgabe sagt das.

## Teststrategie

**Ebene und Bauart.** Keine Unit-Ebene — der Prüfgegenstand ist ein Bash-Skript mit echter
Verzweigung, seine Zusagen sind Exit-Codes, Meldungen und die Menge der abgesetzten Aufrufe.
Verhaltenstests als Unterprozess gegen synthetische Spielplätze (temporärer Repo-Abzug,
aufzeichnende `ruff`/`npm`/`mypy`-Attrappen auf isoliertem PATH, Zeitgrenze je Aufruf), dazu
statische Prüfungen über Skript- und `developer.md`-Text. `pytest` unter `scripts/tests/`, CI-Job
`demo-scripts`, **kein** neues Testframework (`bats-core`/`shunit2`/`shellcheck`), kein neuer Job,
kein numerisches Coverage-Gate.

**Der tragende Fall ist auch hier der stille, aber ein anderer als bei `format.sh`.** Dort war es
`"" == ""` in der Pin-Prüfung (gilt für `check.sh` unverändert und eigenständig, K11a). Hinzu kommt
der Fall, den nur ein Prüfskript hat: **„nichts aufgerufen" ist von „alles sauber" nicht zu
unterscheiden.** Beide enden mit Ausgang 0 und leerer Ausgabe. Die einzige wirksame Form ist die
positive Zusicherung der vollständigen Aufrufliste (K6). Daraus folgt eine Falle im bestehenden
Helfer: `Spielplatz.aufrufe()` liefert `[]`, wenn die Protokolldatei fehlt — jede „es wurde nichts
geschrieben"-Zusicherung wäre dann grün, weil die Aufzeichnung ausfiel. Wo Aufrufe erwartet werden,
gehört die Vollständigkeit der Liste mitgeprüft; wo keine erwartet werden, trägt die Zusicherung
den Exit-Code plus die Meldung.

**Edge Cases** decken die Kriterien K6–K13 je einzeln ab; drei davon sind an keinem Kriterium
ablesbar und deshalb hier benannt: (1) **beide** Python-Bäume ohne Pin **und** leere
Versionsausgabe — der einzige Fall, der `"" == ""` wirklich stellt; (2) abweichende Version in der
`.venv` eines Baums bei gleichzeitig aktuellem PATH, und umgekehrt die passende `.venv`-Version,
die Phase 2 dann auch aufrufen muss; (3) zwei rote Prüfungen in verschiedenen Bäumen — beide in der
Bilanz, alle zehn Aufrufe trotzdem erfolgt.

**Mutationsprobe ist hier die Evidenz, nicht die Zugabe** — die statischen Prüfungen starten auf
sauberem Bestand grün. Nach Grün je Familie ein echter Köder: `--check` aus einer Zeile entfernt;
`npm run format:check` zu `npm run format` verkürzt; ein Aufruf aus der Schleife genommen; die
zweite Nennung in `developer.md` gelöscht bzw. in Schritt 4 verschoben. Dazu die Wiederholung der
`format.sh`-Mutationsprobe nach dem Spielplatz-Umzug (K15).

**Was ausdrücklich nicht geprüft wird:** dass `ruff`/`mypy`/`oxlint`/`tsc`/Prettier korrekt prüfen
(Fremdverhalten, durch Pins fixiert); dass ein Agent den Befehl zur Laufzeit tatsächlich absetzt
(LLM-interpretiert); Laufzeit/Dauer des Skripts. Und eine Grenze, die benannt gehört statt
vorausgesetzt: `npm run lint` erbt oxlints heutiges Verhalten — Warnungen enden mit Exit 0. Ein neu
entstandener Lint-**Warnhinweis** wird von `check.sh` also nicht gemeldet; die Story verspricht
früheres Feedback in der Schärfe der CI, nicht darüber hinaus.

**`specs/architecture/0002-testkonzept.md` wird ergänzt** (kurze Erweiterungs-Sektion, nach der
Umsetzung geschrieben, wenn die Mutationsproben gelaufen sind), um vier über diesen Branch hinaus
gültige Regeln: (1) Ein Prüfskript, dessen einziger Ausgang ein Exit-Code ist, braucht die
vollständige Aufrufliste als Zusicherung — „nichts aufgerufen" und „alles sauber" sind sonst
identisch; eine leere Aufzeichnung darf nie als „es wurde nichts geschrieben" durchgehen. (2) Ein
geteiltes Fixture muss seine Zähne nach dem Umzug neu nachweisen; „läuft weiterhin grün" belegt
nur, dass nichts kaputtging. (3) Eine zweite Kopie einer Extraktions-/Prüflogik erbt keine
Testabdeckung. (4) „Nicht strenger als die CI" ist eine Zusicherung über Argumente, nicht über
Absichten.

## Entscheidungen

- **Kernfrage beantwortet mit „ja, aber (b) + (c)".** Weg (a) — Prüfungen, die nach einer
  Dateiänderung automatisch feuern — ist verworfen, in der eingecheckten wie in der lokalen
  Ausprägung. Gründe in ADR 0083.
- **Die Formatprüfung gehört in den Prüfbefehl**, obwohl ein Akzeptanzkriterium der Story
  „automatische Code-Formatierung" ausnimmt. Formatierung ist das Umschreiben von Dateien;
  `ruff format --check` und `prettier --check` schreiben nichts. Die Abgrenzung galt zudem gegen
  eine damals offene Story — #400 ist entschieden und in allen vier CI-Jobs blockierend. Die
  Gegengrenze ist scharf und eine Verbotsregel: `check.sh` ruft `format.sh` nicht auf, und keiner
  seiner Befehle trägt `--write`, `--fix` oder `--unsafe-fixes`.
- **Teilprüfung je Baum statt Komplettabbruch** (Daniel, 2026-09-11). Siehe K10.
- **Diese Spec trug einen echten Widerspruch, und er ist an der Textebene aufgelöst.** K10 verlangt
  `npm ci` **wörtlich in der Meldung** eines übersprungenen TypeScript-Baums; S3 führte `npm ci` in
  einer Verbotsliste, die **am Skripttext** greift. Beides zugleich ist an derselben Textebene
  unerfüllbar — die Meldung steht im Skript, und wer sie schreibt, verletzt das Verbot. Aufgelöst
  im Umsetzungslauf, nicht durch Aufgeben einer der beiden Seiten: Das Verbot meint ab jetzt die
  **Ausführungsposition** (einfach gequotete Zeichenketten zusätzlich geleert), die übrigen Verbote
  bleiben total, und eine Gegenprobe hält fest, dass der Handgriff in der Meldung stehen bleibt.
  Die Fassung von S3 oben beschreibt den gebauten Stand; die überholte stand bis zur Review-Runde
  hier und ist der Grund, warum der Fall festgehalten gehört statt weggekürzt zu werden.
- **Ungeprüfter Baum und Befund zugleich ergeben Ausgang 2.** Ein Befund löst Handlungsbedarf aus;
  die Bilanz nennt den ungeprüften Baum ohnehin.
- **`test_keine_automatische_formatierung.py` bekommt keine fünfte Musterfamilie.** Die vier
  Familien prüfen repoweite *Form*; „dieses Skript installiert keinen Hook" ist eine
  *Verhaltens*aussage über eine Datei und steht als Totalverbot in deren eigenem Test.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story hat keinen konkret benennbaren
  Bezug zu einer sichtbaren Oberfläche — kein Anzeige- oder Eingabeort, keine Frontend-Komponente,
  keine neuen darzustellenden Daten. Der gesamte Umfang liegt in `scripts/`, `.claude/`, `docs/`
  und `specs/`.
- `architect`, `test-engineer` und `security-engineer` wurden konsultiert.

## Offene Fragen

Keine. Die eine Produktentscheidung — Verhalten im verbundenen Arbeitsbaum — hat Daniel am
2026-09-11 getroffen (K10).

## Out of Scope

- **Automatische Code-Formatierung** (Dateien umschreiben) in jeder Form. Entschieden in Spec 0400.
- **Automatisch feuernde Prüfungen** jeder Art — eingecheckt wie lokal hinterlegt.
- **Tests, Build, Coverage-Gate, `docker compose`-Prüfungen und der e2e-Lauf** im Prüfbefehl. Tests
  laufen im TDD-Zyklus ohnehin fortlaufend und kosten ein Vielfaches. Ein grüner `check.sh`-Lauf
  ist deshalb keine Zusage über die CI, und Schritt 4 des `developer`-Ablaufs bleibt vollständig
  bestehen.
- **Ein eigener CI-Schritt für `check.sh`.** Die zehn Befehle stehen in der CI bereits einzeln und
  blockierend; ein Skriptaufruf dort ersetzte zehn benannte Schritte durch einen, dessen Fehlschlag
  nicht mehr sagt, welcher Baum rot war.
- **Eine exakte Fixierung von `mypy`.** `mypy>=1.13` kann lokal grün und in CI rot sein. Das
  besteht seit jeher, ist nicht Gegenstand dieser Story und wäre eine eigene Entscheidung; in
  ADR 0083 als bekannte Restschwäche benannt.
- **Ein Bereichs-Argument** (`check.sh backend`). Fester Umfang wie bei `format.sh`.
