# 0317 - Setup-Script der Cloud-Umgebung: Fehlschlag kostet das Werkzeug, nicht die Session

**Status:** Implemented ([PR #319](https://github.com/TheRealKoller/photosort/pull/319))
**Erstellt:** 2026-09-03
**Bezug:** GitHub-Issue [`#317`](https://github.com/TheRealKoller/photosort/issues/317), ADR [`0054`](../decisions/0054-setup-script-fehlerregime-und-korrigierte-umgebungsannahmen.md), Vorgänger-Spec [`0314`](./0314-gh-bereitstellung-remote-sessions.md) ([PR #315](https://github.com/TheRealKoller/photosort/pull/315), gemergt), ADR [`0053`](../decisions/0053-gh-bereitstellung-per-umgebungs-setup-script.md), Folge-Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318), `docs/setup.md`, `scripts/tests/test_setup_docs.py`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Spec 0314 hat den Setup-Script-Block für die Cloud-Umgebung dokumentiert und per CI-Test an `MIN_GH_VERSION` gebunden. Eine Nachrecherche in der Anbieter-Dokumentation — angestoßen durch Daniels Frage, wo das Script überhaupt einzutragen ist — hat danach drei Aussagen zutage gefördert, die tragende Annahmen von ADR 0053 widerlegen. Eine davon ist ein Betriebsrisiko, das genau in dem Moment scharf wird, in dem der Block tatsächlich in Betrieb geht:

**Ein Setup-Script, das mit einem Fehler endet, verhindert den Start der Session** — nicht nur den Aufbau der Umgebung, wie ADR 0053 Abschnitt 1 ausdrücklich annahm. Der dokumentierte Block trägt `set -euo pipefail` und bricht bei jedem Fehlschlag ab. Und er läuft häufiger als gedacht: nicht einmalig beim Einrichten, sondern immer dann, wenn kein Cache vorliegt — nach jeder Änderung am Script oder an den erlaubten Netzwerkzielen **und automatisch nach etwa sieben Tagen**.

Zusammen ergibt das eine grob unverhältnismäßige Kopplung: Ein vorübergehend nicht erreichbarer Herausgeber-Server oder ein überschrittenes Zeitlimit legt jede neu gestartete Session lahm, bis jemand von Hand eingreift — für ein Werkzeug, das Komfort schafft, nicht die Arbeit selbst ermöglicht.

Diese Spec dreht das Fehlerregime um, korrigiert die widerlegten Aussagen im Repository und hält den Kenntnisstand fest. Sie tastet die Richtungsentscheidung aus ADR 0053 nicht an.

## User Story

Als Daniel möchte ich, dass eine Vorkehrung, die meine Arbeitsumgebung einrichtet, im Fehlerfall höchstens sich selbst scheitern lässt und niemals meine Fähigkeit, überhaupt eine Session zu starten, damit ich mir mit einer Bequemlichkeit nicht meinen Zugang verbaue.

## Akzeptanzkriterien

Wortgleich zum Issue-Body von [`#317`](https://github.com/TheRealKoller/photosort/issues/317).

### Der Fehlerfall darf die Session nicht blockieren

- [ ] Scheitert die Bereitstellung der GitHub-CLI (Herausgeber nicht erreichbar, Zeitlimit, unerwartete Architektur), startet die Session trotzdem. Die CLI fehlt dann, aber die Arbeitsfähigkeit im Übrigen bleibt erhalten.
- [ ] Der Fehlschlag ist im Protokoll der Umgebung deutlich und als solcher erkennbar — er wird nicht verschwiegen, nur weil er nicht mehr blockiert.
- [ ] Innerhalb der Bereitstellung bricht ein Fehlschlag weiterhin **hart** ab: Schlägt die Prüfsummenverifikation fehl, wird nichts entpackt und nichts installiert. Die Nachsicht gilt ausschließlich der Session, nicht der Integritätsprüfung.
- [ ] Dass beide Eigenschaften zugleich gelten, ist belegt und nicht nur behauptet — die naheliegende Schreibweise erfüllt genau diese Kombination nachweislich **nicht**.

### Die Dokumentation gibt die Umgebung richtig wieder

- [ ] Wann die Vorkehrung läuft, ist zutreffend beschrieben, einschließlich des wiederkehrenden Neuaufbaus.
- [ ] Die Folge eines Fehlschlags ist zutreffend beschrieben.
- [ ] Die Angabe, dass die GitHub-CLI in solchen Umgebungen bereits vorhanden sein soll, ist festgehalten — samt der abweichenden Beobachtung und dem, was daraus folgt.
- [ ] Wo im Repository bisher eine widerlegte Annahme steht, ist sie korrigiert statt ergänzt.

### Abgrenzung

- [ ] Die getroffene Grundentscheidung — Bereitstellung außerhalb des Repositories — wird nicht umgeworfen.

## Datenmodell-Bezug

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug und Dokumentation, keine Anwendungsentität. Keine Änderung an [`docs/architecture.md`](../../docs/architecture.md) nötig — gleiche Einordnung wie ADR 0017/0033/0037/0043/0046/0052/0053.

## Architektur / Umsetzung

Grundlage ist ADR [`0054`](../decisions/0054-setup-script-fehlerregime-und-korrigierte-umgebungsannahmen.md). Der Kern ist eine Änderung von etwa zwölf Zeilen im dokumentierten Block; der Rest ist Korrektur widerlegter Aussagen.

**Betroffene Dateien:**

| Datei | Änderung |
|---|---|
| `specs/decisions/0054-*.md` | **neu**: die ADR |
| `specs/features/0317-*.md` | **neu**: diese Spec |
| `docs/setup.md` | Block ersetzt, drei Textstellen korrigiert |
| `scripts/tests/test_setup_docs.py` | Zusicherung auf die Kapselungsform |
| `specs/features/0314-*.md` | Kenntnisstand ergänzt (bleibt `Implemented`) |
| `specs/architecture/0003-securitykonzept.md` | `bash`-Fallstrick als Angriffsfläche |
| `specs/architecture/0002-testkonzept.md` | dritte prüfbare Hinsicht des Blocks |

`scripts/gh-board.py` bleibt zeilenweise unverändert. Es entstehen nicht: `.claude/settings.json`, ein Hook, eine Workflow-Datei, ein Secret, eine Änderung an `README.md`, `.gitignore`, `docs/architecture.md` oder `docs/ai-workflow.md`.

### Schritt 1 — Der Block in `docs/setup.md`

Drei Änderungen, alle in ADR 0054 Abschnitt 1–3 vorgegeben:

1. **Kein `set -e` auf oberster Ebene** (`set -uo pipefail`), dafür der Installationsteil in einer eigenen Subshell mit `set -eo pipefail`.
2. **Die Subshell steht allein**, ihr Ergebnis wird danach über `$?` ausgewertet, gefolgt von einer Warnung auf `stderr`, die benennt, was jetzt nicht geht (Board-Befehle) und dass die Session trotzdem startet.
3. **Der abschließende `gh --version`-Aufruf wird gegen das Fehlen abgesichert**, das Script endet mit ausdrücklichem `exit 0`.

**Der Fallstrick, der die Form erzwingt** — und der Grund, warum sie als Kommentar im Block steht: `if ! ( set -e; … )` und `( set -e; … ) || warnen` unterdrücken beide das `set -e` im Rumpf der Subshell, weil sie Teil einer `if`-Bedingung bzw. einer `||`-Liste ist. Gemessen, nicht vermutet: In beiden Formen lief die Zeile nach dem erzwungenen Fehlschlag weiter. Am Block hieße das, dass **nach fehlgeschlagener Prüfsummenprüfung entpackt und installiert würde** — die vermeintliche Absicherung wäre nicht wirkungslos, sondern schädlich.

Der übrige Wortlaut bleibt unverändert, insbesondere alle Sicherheitseigenschaften: unauthentifiziert, `--proto '=https' --proto-redir '=https' --tlsv1.2`, Prüfsummenverifikation, ein benanntes Archivmitglied, `install -m 0755`, `mktemp -d` mit `trap`, kein Paketmanager, ausschließlich druckbares ASCII.

### Schritt 2 — Die drei Textkorrekturen um den Block herum

In `docs/setup.md`, jeweils **korrigiert statt ergänzt** (eine widerlegte Aussage, die stehen bleibt und relativiert wird, ist schlechter als keine):

- **Wann das Script läuft:** nicht „einmalig beim Einrichten", sondern immer, wenn kein Cache vorliegt — nach Änderung am Script oder an den erlaubten Netzwerkzielen und nach etwa sieben Tagen Ablauf. Das Ergebnis bleibt ein Filesystem-Snapshot; das Wiederaufnehmen einer bestehenden Session löst nie einen Neulauf aus.
- **Was ein Fehlschlag bewirkt:** dass die Session nicht startet — und dass der Block genau deshalb so aufgebaut ist, wie er aufgebaut ist.
- **Vorinstallation:** dass die Anbieter-Dokumentation `gh` unter den mitgelieferten Werkzeugen führt, dass zwei eigene Messungen das Gegenteil zeigten, dass die Frage offen ist, und dass der Block beide Fälle trägt (liegt eine ausreichende Version vor, tut er nichts und sagt das).

### Schritt 3 — `scripts/tests/test_setup_docs.py`

Die bestehenden Zusicherungen gelten unverändert für den neuen Block und dürfen nicht aufgeweicht werden: Bindung von `GH_VERSION` an `MIN_GH_VERSION`, Zeichenvorrat der Kopiervorlage, die Extraktions-Fehlerfälle.

Neu hinzu kommt genau eine Zusicherung — dass der dokumentierte Block **keine** der drei kaputten Formen enthält: Subshell als `if`-Bedingung, Subshell links einer `||`/`&&`-Liste, und `set -e` auf oberster Ebene (die Rückkehr zum Sessionstart-Blocker, den diese Story behebt). Das ist die einzige Eigenschaft dieser Story, die am Repository-Stand mechanisch prüfbar ist; alles andere ist Textprüfung im Review. Der Test ist bewusst eng: Er prüft die Abwesenheit dieser drei konkret benannten Formen, nicht die Anwesenheit einer „richtigen" Form — letzteres wäre eine Formulierungspolizei, die bei jeder harmlosen Umformatierung rot wird.

Zwei bestehende Zusicherungen sind mitzuziehen, ohne sie aufzuweichen: `test_der_ausgeschnittene_block_ist_der_setup_script_block` verankert die Identität des Blocks bisher an `startswith("set -euo pipefail")` — genau der Zeile, die diese Story ändert. Sie wird auf inhaltliche Merkmale umgestellt (`install -m 0755`, `/usr/local/bin`, `releases/download`), weil eine Zusicherung, die bei jeder Umformatierung bricht, nichts über die Identität des Blocks aussagt. Die Zeichenvorrats- und Versionsbindungs-Prüfungen gelten unverändert für den neuen Block.

Zum Gegenbeweis gehört, dass der Test bei einer absichtlich eingebauten kaputten Form tatsächlich rot wird.

### Schritt 4 — Kenntnisstand nachziehen

- **`specs/features/0314-*.md`:** bleibt `Implemented` und wird **nicht** rückwirkend umgeschrieben. Ergänzt wird ein Abschnitt, der die inzwischen belegten Antworten auf die dort offen gelassenen Fragen festhält, mit Verweis auf ADR 0054 und Issue #318. Eine Spec, die nach dem Merge stillschweigend eine andere Geschichte erzählt, wäre schlechter als eine, die ihren Erkenntnisfortschritt zeigt.
- **`specs/architecture/0003-securitykonzept.md`:** Der `bash`-Fallstrick gehört unter die Angriffsflächen der Toolchain-Bereitstellung — eine „Absicherung", die die Integritätsprüfung stillschweigend aushebelt, ist sicherheitsrelevant, nicht bloß ein Stilfehler. Wichtig ist die Einordnung: Der Fehler wäre nicht von außen angreifbar, sondern selbst herbeigeführt; er senkt die Schutzwirkung, statt eine neue Tür zu öffnen.
- **`specs/architecture/0002-testkonzept.md`:** dritte prüfbare Hinsicht des Blocks, in derselben Logik, in der dort am 2026-09-03 die Zeichenvorrats-Prüfung ergänzt wurde.

### Manueller Schritt außerhalb des Repositories

Bleibt bei Daniel: den Block in der Weboberfläche durch die neue Fassung ersetzen. **Wurde die alte Fassung bereits eingetragen, ist das dringlich** — sie ist die Fassung mit dem Session-Blocker. Wurde sie noch nicht eingetragen, ist mit dieser Story schlicht die richtige Fassung verfügbar.

### Teststrategie

Ein neuer Test (Schritt 3), im bestehenden CI-Job `demo-scripts` (`ruff` + `pytest` über `scripts/`, ohne Coverage-Gate — das 80%-Gate betrifft `backend/`). Kein echtes `gh`, kein Netzwerk, keine Installation.

**Was ausdrücklich nicht getestet wird:** das Laufzeitverhalten des Blocks. Es wurde bei der Erarbeitung dieser Spec empirisch belegt — Idempotenz-Pfad, Fehlerpfad mit fehlgeschlagenem Download (Exit 0 trotz 404), harter Abbruch vor `tar`/`install` bei falscher und bei fehlender Prüfsumme, sowie der Gegenbeweis, dass die zwei naheliegenden Kapselungsformen genau das nicht leisten. In CI ist es nicht reproduzierbar: Es bräuchte Netzwerkzugriff, Root-Rechte und eine echte Installation nach `/usr/local/bin`. Der Beleg lebt deshalb in ADR 0054 und in dieser Spec, nicht in einem Test, der beides vortäuschen müsste.

## UI/UX

Nicht relevant — Entwickler-Werkzeug und Dokumentation, keine sichtbare Oberfläche, kein Pfad unter `frontend/`.

## Security

Sicherheitsrelevant, und zwar in beide Richtungen — das ist die Besonderheit dieser Story.

**Der zu behebende Zustand ist ein Verfügbarkeitsrisiko:** Ein Fehlschlag der Bereitstellung entzieht den Zugang zur gesamten Remote-Arbeitsumgebung, wiederkehrend etwa alle sieben Tage. Kein Angreifer nötig; ein Netzproblem genügt.

**Die naheliegende Behebung wäre ein Integritätsrisiko gewesen:** Beide üblichen Schreibweisen (`if ! (…)`, `(…) || warnen`) hätten das `set -e` der Subshell unterdrückt und damit nach fehlgeschlagener Prüfsummenprüfung weiter entpackt und installiert. Die einzige Integritätsprüfung des Verfahrens wäre stillschweigend ausgehebelt worden — bei unverändertem Aussehen des Blocks. Deshalb ist die Kapselungsform in ADR 0054 Abschnitt 2 vorgeschrieben, im Block kommentiert und per Test gegen Rückbau gesichert.

**Muss-Kriterien, unverändert aus Spec 0314 und ADR 0053 übernommen:** unauthentifiziert und kein neues Geheimnis; `--proto '=https' --proto-redir '=https' --tlsv1.2` auf beiden `curl`-Aufrufen; Prüfsumme vor Entpacken und Installation; genau ein benanntes Archivmitglied; `install -m 0755` nach `/usr/local/bin`; `mktemp -d` mit `trap`; kein Paketmanager; ausschließlich druckbares ASCII im Block; ausdrückliche Kennzeichnung als nichts-ausführender Referenztext; `scripts/gh-board.py` unverändert.

**Neu und ausdrücklich festzuhalten:** Die Warnung im Fehlerfall darf keine Ausgabe des fehlgeschlagenen Befehls verbatim weiterreichen. Sie nennt Version und Status-Code, nicht den Inhalt der Fehlermeldung — dieselbe Zurückhaltung, die `redact_for_report()` in `scripts/gh-board.py` für Berichte durchsetzt, und derselbe Grund: Das Provisionierungs-Protokoll ist einsehbar, und eine durchgereichte Fremdmeldung ist die Stelle, an der unbeabsichtigt etwas landet.

## Entscheidungen

1. **Das Fehlerregime wird umgedreht, statt den Fehlschlag unwahrscheinlicher zu machen.** Zeitlimit und Wiederholungen verschieben nur die Wahrscheinlichkeit; die Kopplung „Werkzeug nicht beschaffbar ⇒ kein Zugang" bleibt. Die Kopplung ist das Problem.
2. **Die Kapselungsform ist vorgeschrieben und begründet, nicht nur gezeigt.** Sie sieht umständlicher aus als die kaputte Alternative und lädt zur „Vereinfachung" ein; da der Block außerhalb des Repositories nie wieder reviewt wird, gäbe es keine zweite Gelegenheit, den Rückbau zu bemerken.
3. **ADR 0053 wird in drei Punkten abgelöst, aber nicht als `Superseded` markiert** — dieselbe Handhabung, mit der ADR 0052 gegenüber ADR 0017 Abschnitt 2 verfuhr. Die Richtungsentscheidung bleibt gültig; korrigiert wird ihre Ausführung.
4. **Der Board-Befund wird festgestellt, nicht entschieden** (ADR 0054 Abschnitt 4, Issue #318). Er trifft den Zweck der Vorarbeit, nicht ihre Ausführung, und seine möglichen Antworten reichen bis zur Frage, ob das GitHub-Board der richtige Zustandsspeicher ist. Eine Richtungsentscheidung nebenbei in einer Korrektur zu treffen, wäre genau die stille Weichenstellung, die `specs/` verhindern soll.
5. **Spec 0314 wird ergänzt, nicht umgeschrieben.** Sie bleibt `Implemented`; ihr Erkenntnisstand wird sichtbar fortgeschrieben statt nachträglich geglättet.

## Offene Fragen

Keine, die die Umsetzung blockiert. Zwei Punkte bleiben ausdrücklich offen und sind anderswo verortet:

1. **Ob eine frisch angelegte Cloud-Umgebung `gh` mitbringt und in welcher Version** — Dokumentation und Messung widersprechen sich. Nur durch Daniels Beobachtung zu klären; die Umsetzung ist gegen beide Ausgänge robust.
2. **Was aus der Board-Sperre folgt** — Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318), braucht eine eigene ADR.

## Out of Scope

- **Keine Umkehr der Richtungsentscheidung** aus ADR 0053. Der Auslöser für eine spätere Umkehr (zweite dauerhaft betriebene Umgebung) bleibt unverändert gültig.
- **Keine Lösung für den gesperrten Board-Zugriff** und keine Umgehung der Beschränkung.
- **Kein Nachladen durch die Board-Werkzeuge selbst**; `scripts/gh-board.py` bleibt unverändert.
- **Kein Absenken von `MIN_GH_VERSION`**, kein Rückbau der `closingIssuesReferences`-Prüfung.
- **Keine Wiederholungs-/Retry-Logik** im Block. Sie würde die Laufzeit gegen das Fünf-Minuten-Limit drücken und das eigentliche Problem — die Kopplung — nicht lösen.
- **Keine Ausweitung auf weitere Werkzeuge** und keine Ausweitung auf autonom laufende Agenten.
