# 0081 - Früheres Qualitäts-Feedback: ein Prüfbefehl von Hand, ein Prüfpunkt je TDD-Einheit, kein Automatismus

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** [Issue #398](https://github.com/TheRealKoller/photosort/issues/398), Spec [`../features/0398-frueheres-qualitaets-feedback.md`](../features/0398-frueheres-qualitaets-feedback.md)

**Umfang:** rund 195 statt der Richtwert-100 Zeilen, weil diese ADR zwei Dinge trägt, die sonst auf
zwei Dokumente fielen: die von der Story verlangte *Abwägung* dreier benannter Wege mit Gründen
dafür und dagegen (Abschnitte 1–3) und die Semantik des entstehenden Werkzeugs, an der Tests
hängen werden (Abschnitte 4–7). Gekürzt wurde dafür die „Begründung" auf die Alternativen, die
oben keinen eigenen Abschnitt haben; die Liste der Totalverbote steht nur in der Spec.

## Kontext

Verstöße gegen Formatierung, Lint und Typprüfung fallen heute spät auf. `.claude/agents/developer.md` prüft in Schritt 3 **nach Abschluss aller TDD-Zyklen**, sonst bemerkt sie erst die CI. Beides kostet einen Nachbesserungszyklus zu einem Zeitpunkt, an dem der Arbeitskontext schon weitergezogen ist.

Am Bestand gemessen (11.09.2026):

- **Die Prüfungen liegen an vier Stellen in zwei Werkzeugketten.** `backend/`: `ruff format --check .`, `ruff check .`, `mypy src`. `scripts/`: `ruff format --check .`, `ruff check .`. `frontend/`: `npm run format:check`, `npm run lint`, `npm run typecheck`. `e2e/`: `npm run format:check`, `npm run typecheck`. **Zehn** Aufrufe, vier Arbeitsverzeichnisse.
- **`developer.md` nennt vier davon und kennt die Formatprüfung nicht.** Schritt 3 führt `ruff check .`, `mypy src`, `npm run lint`, `npm run typecheck` als Beispielbefehle und verweist im Übrigen auf „die tatsächlich konfigurierten Befehle aus `pyproject.toml`/`package.json`/CI-Workflow". Die mit ADR [`0080`](./0080-maschinelle-formatierung-ruff-format-und-prettier.md) eingeführte, in allen vier CI-Jobs blockierende Formatprüfung steht in **keiner** verwalteten Datei unter `.claude/`. Ein Lauf, der Schritt 3 wörtlich folgt, liefert heute einen Branch ab, dessen Formatprüfung lokal nie gelaufen ist.
- **Laufzeit des vollständigen Prüfsatzes: 6,1 s** (backend 0,13 s, scripts 0,02 s, frontend 4,61 s, e2e 1,30 s). Bei kaltem `mypy`-Cache 11,7 s; `mypy` allein kostet kalt 5,68 s und warm 0,11 s. Zum Vergleich der bewusst **nicht** erfassten Prüfungen: `pytest` unter `scripts/` allein 10,2 s.
- **Der Auslöser trägt in seiner Form nicht.** Der `/insights`-Vorschlag vom 10.09.2026 rechnet mit der Ersparnis wiederholter manueller Aufrufe. Die gibt es nicht: Geprüft wird etwa einmal je Feature-Lauf. Das Problem ist der **Zeitpunkt** der Rückmeldung, nicht die Anzahl der Aufrufe.

## Entscheidung

### 1. Weg (a) — Prüfungen, die nach einer Dateiänderung automatisch feuern — wird verworfen

Nicht in der eingecheckten und nicht in der lokalen Ausprägung. Vier Gründe, jeder für sich tragend:

1. **Der TDD-Zyklus durchläuft absichtlich Zustände, die nicht durchlaufen.** Die Rot-Phase schreibt einen Test gegen eine Funktion, die es noch nicht gibt — `mypy` ist dort per Konstruktion rot, und das ist der gewollte Zustand. Ein Prüflauf nach jeder Dateiänderung meldet an dieser Stelle einen Befund, der keiner ist. Meldet er nur, ist es Rauschen, das man sich abgewöhnt zu lesen; unterbricht er, bricht er TDD. Dieser Einwand hängt weder an der Laufzeit noch an der Arbeitsumgebung.
2. **Die eingecheckte Form ist bereits ausgeschlossen und mechanisch gehalten.** ADR [`0080`](./0080-maschinelle-formatierung-ruff-format-und-prettier.md) Abschnitt 12 und Akzeptanzkriterium K8 der Spec [`0400`](../features/0400-einheitliche-code-formatierung.md). Das trifft ausgerechnet die **realistischste** Bauform von (a): Ein `PostToolUse`-Eintrag, der nach jeder Dateiänderung feuert, ist ein `hooks`-Schlüssel in einer eingecheckten `.claude/settings.json` — und genau dieser Köder färbt Familie 3 von `scripts/tests/test_keine_automatische_formatierung.py` heute schon rot. Weg (a) ist in seiner naheliegendsten Form also nicht erst zu verbieten, sondern bereits verboten.
3. **Die lokale Form wirkt nur an einer einzigen Stelle der Welt.** Siehe Abschnitt 6.
4. **Die Kosten stehen nicht zum Nutzen.** 4,6 s je Frontend-Dateiänderung, bei Dutzenden Änderungen je Lauf — für eine Rückmeldung, die am Ende einer TDD-Einheit dieselbe ist.

### 2. Weg (b) wird gebaut: `scripts/check.sh`, ein Aufruf über alle vier Bäume

Das Gegenstück zu `scripts/format.sh`, im selben Muster: Ablageort unter `scripts/`, keine Stiloptionen, keine Dateilisten, keine Regelauswahl. Das Skript ruft dieselben **zehn** Befehle mit derselben Konfiguration auf wie die CI und ist damit reine Bequemlichkeit, keine zweite Quelle der Wahrheit. Es führt **keine Tests** und **keinen Build**: Tests laufen im TDD-Zyklus ohnehin fortlaufend, sind die einzige Prüfung, die der Ablauf nicht aufschiebt, und kosten ein Vielfaches (gemessen oben).

Die Zehn ist eine **Zahl, an der etwas hängt** (Abschnitt 5): backend 3, scripts 2, frontend 3, e2e 2. Die Aufrufliste steht als **literale Erwartung** im Test, nie als Ableitung aus einer „CI-Reihenfolge" — die stimmt nur innerhalb eines Baums. Über die Bäume hinweg läuft die CI `backend` → `frontend` → `demo-scripts` → `e2e`, `check.sh` dagegen `backend` → `scripts` → `frontend` → `e2e` (Python vor TypeScript, wie in `format.sh`). Eine Ableitung wäre schon heute falsch.

**Die vier TypeScript-Prüfungen laufen ausschließlich als `npm run <skript>`,** nie als direkter `prettier`-/`tsc`-/`oxlint`-Aufruf. `--ignore-path ../.prettierignore` steckt im npm-Skript, und diese Datei ist seit ADR 0080 Abschnitt 7 die **einzige** Ausschlussquelle für Prettier: Ein direktes `prettier --check .` aus `e2e/` stiege in `e2e/.auth/` ab und druckte bei einem Parse-Fehler auf einer halb geschriebenen `state.json` das dort liegende, 30 Tage gültige JWT in das Protokoll des Laufs.

**Vorbedingungen je Baum, für alle vier Werkzeuge:** `ruff`-Version gegen den aus der jeweiligen `pyproject.toml` **gelesenen** Pin; `node_modules` in `frontend/`/`e2e/`; **`mypy` aufrufbar**; die aufgerufenen **npm-Skriptnamen vorhanden**. Die letzten beiden sind keine Vollständigkeitskosmetik: Ohne sie endete ein fehlendes `mypy` oder ein umbenanntes npm-Skript als Aufruf mit Exit ≠ 0 und damit als **Befund** — ununterscheidbar von einem echten Typfehler, und die Trennung aus Abschnitt 5 wäre nur für zwei der vier Werkzeuge eingelöst. Der Pin-Vergleich ist hier aus dem Spiegelbild seines Grundes in `format.sh` nötig: Eine abweichende `ruff`-Version erzeugt dort einen Diff, den die CI nicht bestätigt, und hier ein **grünes Ergebnis, das die CI nicht bestätigt**. Phase 2 ruft deshalb dasselbe Binary auf, dessen Version Phase 1 geprüft hat — geprüft und aufgerufen dürfen nicht auseinanderfallen.

**Zwei Abweichungen vom Vorbild.** `format.sh` bricht bei der ersten verletzten Vorbedingung ab, weil das dort einen halb formatierten Baum verhindert; bei `check.sh` gibt es nichts zu schützen, und ein Abbruch kostet die Story ihren Nutzen.

1. **Kein Halt beim ersten Befund.** Alle prüfbaren Bäume laufen vollständig, die Sammelbilanz kommt am Ende. Ein Abbruch nach dem ersten Fund erzeugte genau die Schleife, die diese Entscheidung abschaffen soll: beheben, neu laufen, nächster Fund.
2. **Teilprüfung statt Komplettabbruch** (Entscheidung Daniels, 11.09.2026). Eine verletzte Vorbedingung nimmt **den betroffenen Baum** aus dem Lauf, nicht den Lauf. Die übrigen werden geprüft, der ausgenommene wird als „nicht geprüft" gemeldet, mit Baum und Handgriff. Sonst liefe der Nutzen der Story genau dort leer, wo er gebraucht wird (Abschnitt 6).

Phase 1 wertet trotzdem **alle vier Bäume vorab** aus und nennt die ausgenommenen, bevor der erste Befehl läuft: Wer erst am Ende erfährt, dass zwei Bäume fehlten, hat die Ausgabe dazwischen unter falscher Annahme gelesen.

### 3. Weg (c) wird gebaut: ein Prüfpunkt je TDD-Einheit statt einer am Ende

`developer.md` Schritt 2 bekommt den Prüflauf an die Stelle, an der der Agent ohnehin schon anhält — nach Grün + Refactor, vor dem Commit der Einheit. Schritt 3 und Schritt 4 bleiben unverändert bestehen; Schritt 3 verliert seine aufgezählten Beispielbefehle an den Skriptnamen.

Das ist der einzige der drei Wege, der den benannten Befund — den **Zeitpunkt** der Rückmeldung — tatsächlich verschiebt, und der einzige, der in jeder Arbeitsumgebung gleich wirkt. (b) allein verkürzte nur den Befehl, den ein Lauf einmal am Ende absetzt.

**Was das nicht ist: eine Durchsetzung.** Es ist Ablauftext, den zur Laufzeit ein LLM interpretiert. Zugesichert wird ausschließlich, dass der Befehl an der richtigen Stelle **dasteht** — nicht, dass er läuft. Das ist derselbe Vorbehalt, den `scripts/tests/test_main_abgleich_verdrahtung.py` für den `main`-Abgleich bereits ausspricht, und das ehrliche Maß für eine Änderung an einem Agenten-Ablauf.

### 4. Die Formatprüfung gehört dazu — die Abgrenzung gegen #400 steht dem nicht entgegen

Das Akzeptanzkriterium der Story nimmt „automatische Code-**Formatierung**" aus. Formatierung ist das Umschreiben von Dateien; `ruff format --check` und `prettier --check` schreiben nichts, sie melden. Die Abgrenzung galt zudem gegen eine damals offene Story — #400 ist entschieden, umgesetzt und in allen vier CI-Jobs blockierend. Sie in das frühe Feedback einzubeziehen schließt die im Kontext gemessene Lücke, statt ein Kriterium zu verletzen.

**Die Grenze wird trotzdem scharf gezogen, und sie ist eine Verbotsregel:** `check.sh` ruft `format.sh` nicht auf, nicht bedingt und nicht auf Wunsch, und keiner seiner zehn Befehle trägt `--write`, `--fix` oder `--unsafe-fixes`. Ein Prüfbefehl, der reparieren kann, ist kein Prüfbefehl mehr. Die Regel wird als Totalverbot am Skripttext gehalten, nicht als Absicht im Kopfkommentar (Abschnitt 7).

### 5. Ausgang `0` wird verdient, nicht durch Abwesenheit erreicht

`check.sh` verändert keine Datei und unterbricht nichts. Es meldet, setzt einen Exit-Code und überlässt die Entscheidung dem Aufrufer — derselbe Grund wie in ADR 0080 Abschnitt 12: Ein Werkzeug, das still schreibt, entzieht dem Aufrufer die Kontrolle über den Stand, den er gerade geprüft hat.

**Das Skript zählt die tatsächlich abgeschlossenen Prüfläufe mit.** Ein Lauf zählt, wenn der Befehl aufgerufen wurde und ein Urteil geliefert hat — auch ein negatives. Ausgang `0` verlangt Zähler `== 10`:

| Exit | Bedingung |
|---|---|
| `0` | Zähler `== 10` **und** kein Befund |
| `1` | kein Befund, aber Zähler `< 10` — mindestens ein Baum blieb ungeprüft |
| `2` | mindestens ein Befund |

**Warum der Zähler und nicht die schlichte Abwesenheit von Befunden:** Entstünde die `0` daraus, dass nichts gemeldet wurde, wäre jeder Pfad, auf dem eine Prüfung gar nicht stattfindet, ein Falsch-Grün — eine nicht erreichte Schleife, ein gescheitertes `cd` in `(cd … && cmd)`, oder der Bash-Fehlgriff, dass `bilanz=$?` unter `set -e` hinter einem fehlschlagenden Befehl nie erreicht wird. Der Zähler dreht die Beweislast um: Nicht Fehlerfreiheit wird behauptet, Vollständigkeit wird nachgewiesen. Die Befundsammlung steht deshalb als `if ! …; then`, nie als `bilanz=$?` hinter einem Befehl, und `set +e` kommt nicht vor.

**Derselbe Zähler trägt die Teilprüfung aus Abschnitt 2** — kein zweiter Mechanismus, sondern derselbe: Ein ausgenommener Baum erhöht den Zähler nicht, sein Fehlen kann also nicht als `0` durchgehen. Genau das erlaubt die Teilprüfung, ohne den Lauf zu kosten.

**Der Gleichstand — ungeprüfter Baum *und* Befund — geht an `2`.** Exit-Codes ordnen nach erforderlicher Handlung, und nur die `0` muss für einen Aufrufer, der bloß `$?` liest, unzweideutig sein. Zwischen `1` und `2` gewinnt der Befund: Er verlangt eine Änderung am Arbeitsstand, `1` nur eine an der Umgebung. Die Reihenfolge ist selbstkorrigierend — wer `2` bekommt, behebt und erneut läuft, sieht danach `1`. Umgekehrt ginge die Information verloren: Wer `1` bekäme, installierte `node_modules` und meldete „war nur die Umgebung", während der Befund die ganze Zeit dastand. Die Sammelbilanz nennt ohnehin **beides**; `$?` trägt nur das Dringendere.

Die tragende Zusicherung bleibt damit erhalten und wird sichtbarer: „konnte nicht prüfen" darf nie wie „geprüft und sauber" aussehen.

### 6. Wo die Lösung wirkt und wo nicht

| | Daniels Rechner | Worktree | Cloud-Session | CI |
|---|---|---|---|---|
| `scripts/check.sh` (b) | ja | nur mit Werkzeugkette, siehe unten | ja | nicht nötig, prüft selbst |
| Prüfpunkt in `developer.md` (c) | ja | ja | ja | — |
| lokaler Agenten-/Git-Hook (a) | ja | ja | **nein** | — |

**Die ausdrückliche Aussage zur lokalen Konfiguration:** Ein Hook in `.claude/settings.local.json` wirkte ausschließlich in dieser einen Installation auf diesem einen Rechner. Er ist nicht eingecheckt — das ist der Grund, aus dem er die verbindliche Randbedingung nicht verletzt, und zugleich der Grund, aus dem er in einer Cloud-Session nicht existiert und nicht dorthin gelangen kann: Das Setup-Script der Cloud-Umgebung (ADR [`0053`](./0053-gh-bereitstellung-per-umgebungs-setup-script.md)) installiert `gh` und sonst nichts. Er ist außerdem nicht prüfbar, weil nicht verwaltet, und nicht dokumentierbar, weil jede Dokumentation eine Datei beschriebe, die anderswo nicht liegt.

**Im verbundenen Arbeitsbaum fehlen `.venv` und `node_modules`** (gemessen) — und genau dort arbeitet der `developer`-Agent, für den der Prüfpunkt aus Abschnitt 3 gedacht ist. Ausgang `1` ist dort der **Normalfall**, kein Störfall. `check.sh` sucht `ruff` und `mypy` wie `format.sh` zuerst in `<baum>/.venv/bin/`, dann auf dem PATH; die npm-Skripte haben keinen solchen Rückfall. Der Rest greift wie in Abschnitt 2.

### 7. Die verbindliche Randbedingung bleibt unberührt, und das wird belegt statt behauptet

`scripts/check.sh` ist eine eingecheckte Datei, aber keine, die das Verhalten von Sessions **automatisch** steuert: Sie tut nichts, bis jemand sie aufruft — genau die Unterscheidung, auf der `format.sh` bereits steht. Kein Git-Hook, kein Editor-Hook, kein Agenten-Hook, kein npm-Lebenszyklus-Skript ruft sie.

**Eine Abgrenzung, die ausdrücklich dastehen muss, weil sie sonst später bestritten wird:** `.claude/agents/developer.md` **ist** eine eingecheckte Datei, die Sessionverhalten steuert — die Randbedingung meint sie nicht, und Abschnitt 3 verletzt sie nicht. Der Unterschied liegt im Ausführenden. Ein Hook der Arbeitsumgebung läuft **ohne Zutun** und schreibt an einem Stand, den der Aufrufer gerade geprüft hat; ein Ablaufschritt in einer Agentendatei wird von einer Rolle **gelesen und bewusst befolgt** und schreibt von selbst gar nichts. Spec [`0395`](../features/0395-dateiarbeit-dedizierte-werkzeuge.md) hat dieselbe Grenze bereits gezogen.

`scripts/tests/test_keine_automatische_formatierung.py` wird **nicht erweitert**, und der tragende Grund ist eine Zuständigkeitsgrenze, keine Risikoabschätzung: Die vier Musterfamilien prüfen repoweite **Form** — Pfade, Dateinamen, Konfigurationsschlüssel, eine scharf schaltende Schreibweise. „Dieses Skript installiert keinen Hook" ist dagegen eine **Verhaltens**aussage über **eine** Datei und gehört als Totalverbot am Skripttext in deren eigenen Test (`test_check_sh.py`, Liste in der Spec).

Zwei der Verbote zielen auf einen benennbaren Fehlgriff statt auf eine Gefahr im Allgemeinen: `npm ci` wäre die naheliegende „Reparatur" der `node_modules`-Vorbedingung — und genau das tut Ausgang `1` bewusst **nicht**. Und `git ` ist total verboten, weil `check.sh` seine Bäume wie `format.sh` aus `BASH_SOURCE` ableitet und keinen legitimen Grund hat, `git` aufzurufen.

Für die repoweite Form bleibt es beim **Nachweis**: Die vier Familien laufen auf dem fertigen Branch und melden null Befunde — eine Messung, kein neuer Testcode.

## Begründung

Die Abwägung der drei Wege steht vollständig in den Abschnitten 1 bis 3. Hier stehen nur die Alternativen, die dort keinen eigenen Abschnitt haben, weil sie verworfen wurden:

- **Zwei Skripte statt eines mit Modus:** `format.sh --check` machte ein schreibendes Werkzeug manchmal nicht-schreibend und zöge Lint und Typprüfung unter einen Namen, der Formatierung verspricht. Der Aufruf von `format.sh` aus `check.sh` heraus scheidet aus, weil `format.sh` schreibt.
- **Kein Bereichs-Argument (`check.sh backend`):** Es spart gemessene 4 s und kauft dafür eine Aufrufvariante, einen zweiten Ausgabefall und den Fehlermodus „den anderen Baum vergessen". Fester Umfang, wie bei `format.sh`.
- **Kein eigener CI-Schritt für `check.sh`:** Die zehn Befehle stehen in der CI bereits einzeln und blockierend. Ein Skriptaufruf dort ersetzte zehn benannte Schritte durch einen, dessen Fehlschlag nicht mehr sagt, welcher Baum rot war — und brächte die Teilprüfung aus Abschnitt 2 an eine Stelle, an der ein ungeprüfter Baum nie vorkommen darf.
- **Komplettabbruch bei verletzter Vorbedingung:** die strengere Regel und die schwächere Lösung. Er ist nur besser, wenn ein halb erledigter Lauf Schaden hinterlässt — beim Formatieren tut er das, beim Prüfen nicht.

## Konsequenzen

- **Ein neues Skript** (`scripts/check.sh`) und **eine neue Testdatei** (`scripts/tests/test_check_sh.py`, CI-Job `demo-scripts`) — Verhaltenszusicherungen und Verankerung in **einer** Datei, weil die Verankerung aus drei Tatsachen besteht und eine zweite Datei überwiegend aus ihrem Docstring bestünde.
- **Keine neue Abhängigkeit, kein neuer CI-Job, kein neuer Required Status Check.** Das Skript ruft ausschließlich, was in allen vier Bäumen bereits installiert ist.
- **`.claude/agents/developer.md` ändert sich an zwei Stellen** (Schritt 2, Schritt 3) und wird dabei nicht länger, sondern konkreter: Aufzählungen weichen einem Befehl.
- **`docs/setup.md` bekommt den Prüfbefehl** neben dem Formatierbefehl, mit seinen Vorbedingungen, dem Verhalten bei jedem der drei Ausgänge und dem ausdrücklichen Hinweis, dass ein Ausgang `1` im verbundenen Arbeitsbaum der Normalfall ist. `CLAUDE.md` und `docs/architecture.md` bleiben unberührt — weder Systemarchitektur noch Datenmodell ändern sich, und eine Regel, die die CI hart durchsetzt, braucht keine weitere Textstelle, die driften kann.
- **`specs/architecture/0003-securitykonzept.md` wird fortgeschrieben** (Abschnitt 4, Zeilen 762–766, gepflegt vom `security-engineer`): Die Überschrift steigt vom Einzelfall `format.sh` auf die Musterform, die mit `check.sh` zum zweiten Mal auftritt; „wie in den **drei bestehenden** Skripten" wird zu „in **jedem** Skript unter `scripts/`", weil eine mitgezählte Zahl still veraltet; und ein vierter Punkt kommt hinzu, der erst hier trägt — *der Ausgang eines prüfenden Skripts wird verdient, nicht durch Abwesenheit erreicht* (Abschnitt 5).
- **Ein grüner `check.sh`-Lauf ist keine Zusage über die CI.** Er deckt Format, Lint und Typprüfung ab, nicht Tests, nicht das Coverage-Gate, nicht den Frontend-Build, nicht die `docker-compose`-Prüfungen und nicht den `e2e`-Job. Schritt 4 des `developer`-Ablaufs bleibt vollständig bestehen und wird durch diese Entscheidung nicht ersetzt.
- **Bekannte Restschwäche, benannt statt verschwiegen:** `mypy` steht als `mypy>=1.13`, `oxlint` und `typescript` hängen am jeweiligen Lockfile. Phase 1 prüft für `mypy` nur die **Aufrufbarkeit**, nicht die Version — nur die beiden `ruff`-Pins werden verglichen. Eine lokale `mypy`-Version, die von der in CI installierten abweicht, kann lokal grün und in CI rot sein. Das besteht seit jeher und wird hier nicht mitgelöst; eine exakte Fixierung von `mypy` wäre eine eigene Entscheidung.
- **Was diese Entscheidung nicht zusichert:** dass ein Lauf den Befehl tatsächlich absetzt (Abschnitt 3).
