# 0053 - `gh`-Bereitstellung außerhalb des Repositories: Setup-Script der Cloud-Umgebung, im Repository nur die Dokumentation

**Status:** Accepted
**Datum:** 2026-09-02
**Bezug:** GitHub-Issue [`#314`](https://github.com/TheRealKoller/photosort/issues/314) ("Remote-Session ohne Handgriff produktiv"), `specs/features/0314-gh-bereitstellung-remote-sessions.md`, ADR [`0052`](./0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) (Abschnitt 4/5 — `gh-board.py` meldet, repariert nicht; Abschnitt 6 — kein zusätzliches Geheimnis), ADR [`0046`](./0046-pr-issue-verknuepfung-closing-keyword.md) (Abschnitt 5 — `closingIssuesReferences` als Vorbedingung von `finalize`), ADR [`0033`](./0033-modell-asset-download-statt-commit-label-embedder.md) (verifizierter Bezug statt Commit), ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md), `scripts/gh-board.py` (`MIN_GH_VERSION`), `docs/setup.md`, `specs/architecture/0003-securitykonzept.md`, Remote-Befund Daniels vom 2026-09-02 an Issue #314, `architect`-Konsultation für Story #314 am 2026-09-02.

## Kontext

Der Diagnoselauf aus Spec [`0309`](../features/0309-story-lebenszyklus-remote-sessions.md) hatte den Verdacht belegt; ein zweiter Lauf Daniels in einer echten Remote-Session hat ihn reproduziert und darüber hinaus mehr geklärt, als die Story verlangt hatte. Alle folgenden Punkte sind gemessen, nicht angenommen.

1. **`gh` fehlt in der Remote-Session erneut** (`command not found`, Exit-Code 127). Sämtliche neun `doctor`-Prüfungen scheitern an dieser **einen** Ursache; es gibt kein zweites, davon unabhängiges Problem. Der Befund aus 0309 war kein Einzelfall.

2. **Die Versionsgrenze ist nicht verhandelbar.** `MIN_GH_VERSION = "2.72.0"` (`scripts/gh-board.py:45`) steht dort, weil `gh pr view --json` erst ab dieser Version das Feld `closingIssuesReferences` kennt — die Vorbedingung, an der `finalize` laut ADR 0046 Abschnitt 5 die PR-Issue-Verknüpfung prüft. Ubuntus Paketquelle bietet 2.45.x an; `apt install gh` löst das Problem also nicht, sondern verdeckt es (`gh` da, `finalize` trotzdem blockiert).

3. **Der Bezug eines Release-Assets ist in der Cloud-Session möglich — der zuvor befürchtete Proxy-Riegel greift dort nicht.** Der Test trennt zwei Fälle sauber:
   - API-Metadaten eines **fremden** Repositories (`api.github.com/repos/cli/cli/releases/tags/v2.72.0`) → **403**, mit Hinweis auf `add_repo`.
   - Das **Release-Asset selbst** (`github.com/cli/cli/releases/download/v2.72.0/gh_2.72.0_linux_amd64.tar.gz`) → **HTTP 200**, 13.730.487 Bytes, unauthentifiziert, der Redirect auf `release-assets.githubusercontent.com` wird durchgelassen. Die Prüfsumme gegen `gh_2.72.0_checksums.txt` (ebenfalls 200) stimmt exakt, das entpackte Binary meldet `gh version 2.72.0`.

   Die Beschränkung des GitHub-Proxys wirkt also auf der **API**, nicht auf dem **Asset-Download**. Das ist für diese Entscheidung von zentraler Bedeutung, weil es eine Alternative *nicht* ausschließt: Eine Vorkehrung im Repository wäre technisch getragen worden. Sie scheidet aus anderen Gründen aus (Abschnitt 6), nicht daran.

4. **GitHub-Zugriff besteht in der Session sehr wohl.** Daniels Befund-Kommentar wurde über die GitHub-MCP-Werkzeuge an das Issue geschrieben. Das `authenticated: false` im Bericht war ausschließlich Folge des fehlenden Binaries — `gh auth status` konnte nicht laufen — und ist keine Aussage über die Rechtelage.

5. **Die Voraussetzung steht im Projekt nirgends geschrieben.** Weder `README.md` noch `docs/setup.md` noch `CLAUDE.md` erwähnen `gh` auch nur einmal, obwohl der gesamte Entwicklungsablauf darauf steht. Der Wert lebt heute als Konstante in `scripts/gh-board.py` und zusätzlich als Prosa-Zahl in `.claude/skills/github-board/SKILL.md` und `.claude/skills/ship-feature/SKILL.md`.

6. **Zwei Mechanismen stehen zur Verfügung, und die Anbieter-Dokumentation ordnet sie eindeutig zu.** Das **Setup-Script** wird in der Weboberfläche der Cloud-Umgebung gepflegt, läuft einmalig beim Einrichten der Umgebung — vor dem Start von Claude Code — und sein Ergebnis wird als Filesystem-Snapshot gecacht; es ist nicht versioniert und nicht reviewbar. Ein **`SessionStart`-Hook** in einer eingecheckten `.claude/settings.json` liegt dagegen im Repository, wird auch in Cloud-Sessions gelesen (anders als `~/.claude/settings.json` und `.claude/settings.local.json`) und läuft ohne Bestätigung — dafür bei **jedem** Sessionstart, ungecacht, und in **jeder** Session, auch in jeder lokalen. Die Dokumentation der Cloud-Umgebungen empfiehlt für diesen Fall ausdrücklich den ersten Weg: „Use a setup script to provision the VM itself: toolchains and CLI tools that aren't pre-installed. Use a SessionStart hook for project setup that should run everywhere, cloud and local."

7. **Daniels Entscheidung, in zwei Schritten getroffen.** Zuerst grundsätzlich: dem empfohlenen Weg folgen, also Setup-Script statt `SessionStart`-Hook. Dann auf Rückfrage ausdrücklich die Vollvariante — **die gesamte Installation liegt im Setup-Script der Weboberfläche** — und damit gegen den angebotenen Mittelweg, bei dem die Logik als Skript im Repository läge und die Weboberfläche sie nur aufriefe. Diese Festlegung ist Vorgabe dieser ADR, nicht ihr Ergebnis.

Diese ADR ist wie 0013/0016/0017/0033/0037/0042–0046/0052 eine Prozess-/Tooling-Entscheidung für die Entwicklungsumgebung selbst. Sie berührt PhotoSorts Laufzeitsystem, sein Datenmodell und seine Produktiv-Abhängigkeiten an keiner Stelle.

## Entscheidung

### 1. Die Bereitstellung liegt vollständig im Setup-Script der Cloud-Umgebung

`gh` wird beim **Einrichten der Umgebung** installiert, durch das in der Weboberfläche gepflegte Setup-Script, einmalig und danach gecacht. Im Repository entsteht **keine ausführbare Vorkehrung**: keine `.claude/settings.json`, kein Hook, kein Installationsskript, keine Änderung an `scripts/`. Die Fragen nach `PATH`-Sichtbarkeit, nach Latenz pro Sessionstart und nach der Rückwirkung auf lokale Sessions stellen sich damit gar nicht mehr — sie waren Eigenschaften des anderen Weges.

Das Setup-Script läuft mit Root-Rechten in einer Wegwerf-VM, vor Claude Code, ohne Zeitdruck einer wartenden Session. Daraus folgen drei Vereinfachungen, die die verworfene Hook-Variante sich nicht leisten konnte:

- **Ziel ist `/usr/local/bin`**, ein Verzeichnis, das ohnehin im `PATH` jeder Shell liegt. Keine Verzeichnissuche, keine Verdeckungsfälle, keine Nachprüfung des eigenen Erfolgs über den `PATH`.
- **Das Skript darf laut scheitern.** `set -euo pipefail`, Abbruch bei jedem Fehlschlag. Ein gescheitertes Setup-Script ist ein sichtbar gescheiterter Umgebungs-Build mit einem Protokoll in der Oberfläche — und nicht, wie bei einem Hook, ein Vorgang, der eine laufende Session nicht beschädigen darf und deshalb jeden Fehlschlag in eine Meldung übersetzen muss. Es gibt hier keinen Grund, mit Exit-Code 0 zu enden.
- **Es gibt keinen Agenten-Kontext, den eine Erfolgsmeldung verschmutzen könnte.** Das Skript darf reden.

### 2. Im Repository liegt nichts, was die Umgebung ausführt — auch kein aufgerufenes Skript

Der Mittelweg (Logik als `scripts/…`-Datei im Repository, die Weboberfläche ruft sie nur auf) ist ausdrücklich verworfen. Die Grenze wird nicht als Absichtserklärung formuliert, sondern an einem mechanisch prüfbaren Kriterium:

> **Das Setup-Script ist in sich abgeschlossen. Es liest, klont und führt zur Provisionierungszeit nichts aus dem Repository aus.**

Das ist keine Feinheit, sondern der Grund, warum die Variante überhaupt trennscharf ist: Ein Setup-Script, das ein Repo-Skript aufruft, hängt davon ab, dass das Repository zu diesem Zeitpunkt bereits ausgecheckt ist, an einem bekannten Pfad liegt und in der erwarteten Fassung vorliegt — drei Annahmen über einen Zeitpunkt, über den wir nichts Belegtes wissen, und drei zusätzliche Fehlerarten. Die abgeschlossene Variante hat keine davon.

### 3. Der Wortlaut des Setup-Scripts wird trotzdem im Repository dokumentiert

„Nichts im Repository" bezieht sich auf **ausgeführte** Artefakte, nicht auf Wissen. Der exakte Text, den Daniel in die Weboberfläche einträgt, steht wörtlich in `docs/setup.md`. Ohne das wäre der Inhalt einer Umgebung, die jederzeit neu angelegt werden kann, ausschließlich in einem Webformular vorhanden — nicht reviewbar, nicht rekonstruierbar, bei jeder neuen Umgebung aus dem Gedächtnis nachzubauen. Das wäre kein bewusster Verzicht, sondern ein vermeidbarer Verlust.

Dass dies **kein** wiedereingeführter Mittelweg ist, folgt aus demselben Kriterium wie Abschnitt 2: Der dokumentierte Block wird von niemandem ausgeführt und von der Umgebung nicht gelesen. Er ist ein Referenztext für Menschen; das Setup-Script bleibt eine eigenständige Kopie in der Oberfläche. Der Unterschied ist der zwischen „die Umgebung hängt am Repository" (verworfen) und „das Repository weiß, was in der Umgebung steht" (gewollt).

Der dokumentierte Wortlaut:

```bash
set -euo pipefail

# Muss zu MIN_GH_VERSION in scripts/gh-board.py passen (siehe docs/setup.md).
GH_VERSION="2.72.0"

SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"

need_install=1
if command -v gh >/dev/null 2>&1; then
  have="$(gh --version | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
  # sort -V vergleicht numerisch: 2.9.0 ist aelter als 2.72.0, ein String-Vergleich sagt das Gegenteil.
  if [ -n "$have" ] && [ "$(printf '%s\n%s\n' "$GH_VERSION" "$have" | sort -V | head -n1)" = "$GH_VERSION" ]; then
    need_install=0
    echo "gh $have liegt bereits vor (>= $GH_VERSION), keine Installation."
  fi
fi

if [ "$need_install" -eq 1 ]; then
  case "$(uname -m)" in
    x86_64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    *) echo "Nicht unterstuetzte Architektur: $(uname -m)" >&2; exit 1 ;;
  esac

  asset="gh_${GH_VERSION}_linux_${arch}.tar.gz"
  base="https://github.com/cli/cli/releases/download/v${GH_VERSION}"
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

  curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 180 -o "$tmp/$asset" "$base/$asset"
  curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 -o "$tmp/checksums.txt" \
    "$base/gh_${GH_VERSION}_checksums.txt"
  ( cd "$tmp" && awk -v a="$asset" '$2 == a' checksums.txt | sha256sum -c - )

  tar -xzf "$tmp/$asset" -C "$tmp" "gh_${GH_VERSION}_linux_${arch}/bin/gh"
  $SUDO install -m 0755 "$tmp/gh_${GH_VERSION}_linux_${arch}/bin/gh" /usr/local/bin/gh
fi

gh --version
```

Verbindliche Eigenschaften dieses Textes, die bei jeder Änderung erhalten bleiben müssen:

- **Idempotent.** Liegt `gh` bereits in ausreichender Version vor, wird nichts geladen und nichts geschrieben. Das trägt das Akzeptanzkriterium „liegt bereits eine ausreichende Version vor, wird nichts nachinstalliert" und macht die von Daniel übersprungene Vorprüfung folgenlos: Sollte eine frisch **angelegte** Umgebung `gh` doch mitbringen, meldet das Skript das und tut nichts.
- **Numerischer Vergleich** über `sort -V`. Ein lexikografischer Vergleich hielte `2.9.0` für neuer als `2.72.0` — derselbe Fehler, den `parse_gh_version` in `gh-board.py` bereits vermeidet.
- **Unauthentifiziert.** Kein `GH_TOKEN`, kein `GITHUB_TOKEN`, kein `Authorization`-Header, kein neu abgelegtes Geheimnis. Das ist ein Akzeptanzkriterium der Story und deckt sich mit ADR 0052 Abschnitt 6.
- **Prüfsumme gegen `gh_<version>_checksums.txt` aus demselben Release.** Ehrlich benannt: Das schützt gegen abgebrochene und verfälschte Übertragung, nicht gegen einen kompromittierten Ursprung — die Prüfsumme stammt von dort. Vertrauensanker ist TLS zu `github.com` plus das versionsfest adressierte Release; derselbe Anker, an dem das Projekt ohnehin hängt. Ein zusätzlich fest verdrahteter Hash wie in ADR 0033 entfällt bewusst: Dort zeigt die URL auf `resolve/main`, eine bewegliche Referenz, und der Hash ist die einzige Festlegung, *was* geladen wird; hier ist die Adresse selbst schon die Festlegung, und ein Hash wäre nur eine zweite versionsabhängige Zahl.
- **Aus dem Archiv wird genau ein benanntes Mitglied entpackt**, nicht das Archiv. Kein Archivinhalt bestimmt einen Zielpfad.
- **Kein Paketmanager.** `apt install gh` liefert 2.45.x und wäre nutzlos (Kontext, Punkt 2).

### 4. Die Mindestversion steht ab jetzt zwangsläufig an zwei Orten — benannte Lücke, abgesichert statt beschwiegen

Das Akzeptanzkriterium „es ist erkennbar, an welcher **einen** Stelle die Mindestversion gepflegt wird" ist unter dieser Entscheidung **nicht erfüllbar**, und das wird hier festgehalten statt umformuliert. Der Grund ist strukturell: Das Setup-Script muss die Zielversion nennen, es ist per Abschnitt 2 in sich abgeschlossen, und es liegt außerhalb des Repositories — es kann `MIN_GH_VERSION` nicht lesen. Zwei Orte sind die Kosten der gewählten Variante, nicht ein Versäumnis der Umsetzung.

Was stattdessen erreicht wird, ist eine **Reduktion auf genau einen ungesicherten Übergang**:

1. `MIN_GH_VERSION` in `scripts/gh-board.py` bleibt der **autoritative** Wert. Nichts daran ändert sich.
2. Der in `docs/setup.md` dokumentierte Skript-Block wird per **Test in CI** gegen diesen Wert gehalten: Ein Test liest `GH_VERSION` aus dem Block und stellt ihn gegen das `MIN_GH_VERSION` des geladenen `gh-board`-Moduls. Wird die Konstante angehoben, ohne den Block nachzuziehen, wird der Lauf rot — sofort, nicht irgendwann. Damit ist die Doku keine Kopie, die veralten darf, sondern eine erzwungen synchrone zweite Ansicht.
3. Ungesichert bleibt **allein** der letzte Schritt: dass der geprüfte Block auch tatsächlich in die Weboberfläche übertragen wird. Das ist eine Ausrollhandlung, kein Datenhaltungsproblem — dieselbe Klasse wie jede andere manuelle Übernahme, und sie wird in `docs/setup.md` als Pflichtschritt bei jeder Anhebung von `MIN_GH_VERSION` benannt.

**Woran ein Auseinanderlaufen auffällt**, wenn dieser letzte Schritt einmal vergessen wird: `python3 scripts/gh-board.py doctor` meldet die Prüfung `gh_version` als fehlgeschlagen und nennt beide Zahlen (gefundene Version und `MIN_GH_VERSION`), und `abschluss-finalisieren` erscheint unter `blocked_lifecycle_steps`. Unabhängig davon bricht `finalize` selbst mit einer Meldung ab, die die Mindestversion ausdrücklich nennt — und zwar **vor** jedem Schreibzugriff auf Spec-Datei und Board (ADR 0052/0046), sodass nichts zurückzunehmen ist. Der Fehlerfall ist damit laut, eindeutig und folgenlos; er ist nicht still. Das ist die Eigenschaft, die die Lücke tragbar macht — nicht die Hoffnung, dass sie nie eintritt.

Verworfen als vermeintlich bessere Absicherung: **das Setup-Script `MIN_GH_VERSION` aus dem ausgecheckten Repository lesen zu lassen.** Es würde die Lücke tatsächlich schließen, verletzt aber Abschnitt 2 und hängt an drei unbelegten Annahmen über den Provisionierungszeitpunkt (Repository vorhanden, Pfad bekannt, Fassung passend). Schlägt der Lesevorgang fehl, bräuchte es einen Rückfallwert — also wieder eine zweite Zahl, diesmal zusätzlich zu einem stillen Fehlerpfad. Der Preis übersteigt den Gewinn.

### 5. Abgrenzung zu ADR 0052: unverändert, und hier trivial erfüllt

ADR 0052 hält fest, dass `gh-board.py` — insbesondere `doctor` — Zustände **meldet** und nichts repariert. Diese ADR ändert daran nichts und markiert ADR 0052 ausdrücklich **nicht** als `Superseded`. Unter der gewählten Variante ist die Abgrenzung nicht einmal mehr begründungsbedürftig: Die Bereitstellung findet außerhalb des Repositories statt, zu einem Zeitpunkt, zu dem `gh-board.py` nicht läuft. An `scripts/gh-board.py` ändert sich **keine Zeile**, und kein Board-Befehl löst je eine Installation aus. `doctor` bleibt die einzige Instanz, die urteilt, und sein Urteil bleibt zutreffend, wenn die Umgebung nicht vorbereitet wurde: `gh_binary`/`gh_version` sind dann rot.

### 6. Was aufgegeben wird — damit eine spätere Umkehr informiert möglich ist

Die verworfene Variante ist nicht widerlegt worden; sie ist unterlegen bewertet worden. Der Unterschied gehört festgehalten, weil sich die Gewichte ändern können.

**Was der Repo-Weg geboten hätte und jetzt fehlt:**

- **Versionierung und Review.** Die Vorkehrung wäre Teil des Diffs gewesen, mit Historie und Vier-Augen-Prinzip. Der Setup-Script-Inhalt ist es nicht; ersatzweise ist sein Wortlaut dokumentiert (Abschnitt 3), aber die tatsächlich laufende Fassung bleibt unbeobachtet.
- **Automatische Ausbreitung.** Jede neue Umgebung — auch eine, die es heute noch nicht gibt — hätte die Vorkehrung mit dem Klon bekommen. Jetzt muss sie pro Umgebung eingetragen werden, von Hand.
- **Eine pflegbare Stelle für die Mindestversion.** Siehe Abschnitt 4; das ist der konkret bezifferbare Verlust.
- **Wirkung auch lokal.** Eine zu alte lokale `gh`-Installation bleibt unbemerkt, bis `doctor` oder `finalize` sie melden. (Praktisch derzeit ohne Belang: Daniels Rechner trägt `gh 2.98.0`.)

**Was der gewählte Weg dafür gewinnt:**

- **Keine Latenz pro Session.** Das Ergebnis wird als Snapshot gecacht; die Installation findet einmal statt, nicht bei jedem Sessionstart.
- **Kein Eingriff in jede lokale Session.** Eine eingecheckte `.claude/settings.json` wäre die erste im Repository gewesen und hätte ab dem Merge **jede** Session betroffen — mit einem Hook, der ohne Vertrauensdialog und ohne Bestätigung Code ausführt. Das entfällt vollständig; das Repository bleibt frei von einer Datei, die Sessionverhalten steuert.
- **Übereinstimmung mit der Anbieter-Empfehlung** (Kontext, Punkt 6) und damit die geringere Wahrscheinlichkeit, an einer künftigen Änderung der Hook- oder Settings-Semantik zu zerbrechen.

**Der Auslöser für eine Neubewertung** ist damit benannt und nicht dem Bauchgefühl überlassen: Sobald eine zweite Umgebung dauerhaft dazukommt (weitere Cloud-Umgebung, ein zweiter Rechner, ein autonom laufender Agent), kippt die Rechnung — Handpflegeaufwand und Drift-Risiko wachsen linear mit der Zahl der Umgebungen, während die Kosten des Repo-Weges konstant bleiben. Eine solche Umkehr ist architekturrelevant und braucht eine neue ADR, die diese hier als `Superseded` markiert. Der technische Weg dorthin ist offen: Kontext-Punkt 3 belegt, dass der Asset-Bezug aus einer Cloud-Session funktioniert.

### 7. Ein Akzeptanzkriterium der Story wird durch diese Entscheidung überstimmt

Die Story fordert wörtlich: „Die Vorkehrung liegt **versioniert im Repository** und wird mit ihm ausgeliefert — nicht ausschließlich in einer manuell über eine Weboberfläche gepflegten Umgebungs-Konfiguration." Genau das ist die nun gewählte Variante. Das Kriterium ist nicht erfüllt und wird nicht erfüllt werden.

Das ist kein Versehen und keine Auslegungsfrage: Daniel hat die Anforderung, nachdem der Befund vorlag, bewusst umgekehrt. Damit die spätere Anforderungsprüfung nicht einen Verstoß meldet, wo eine Entscheidung vorliegt, muss die Umkehr an der Quelle nachgezogen werden — im Issue-Body von #314 und in den Akzeptanzkriterien der Feature-Spec, **bevor** der PR in die Review-Phase geht. Zusammen mit diesem Kriterium fällt das Kriterium aus Abschnitt 4 („eine Stelle"); beide sind zu ersetzen durch das, was tatsächlich gilt: Die Vorkehrung liegt in der Umgebungs-Konfiguration, ihr Wortlaut liegt versioniert im Repository, und die Zielversion ist per CI-Test an `MIN_GH_VERSION` gebunden.

## Begründung

- **Warum diese ADR die frühere Fassung vom selben Tag vollständig ersetzt statt sie zu ergänzen:** Die vorherige Fassung entschied den `SessionStart`-Hook. Eine ADR ist nach Annahme unveränderlich — sie war zum Zeitpunkt der Umkehr aber noch nicht Teil des `main`-Standes, sondern lag als noch nicht gemergte Vorarbeit auf dem Feature-Branch. Eine `Superseded`-Kette über eine nie wirksam gewordene Entscheidung wäre Buchhaltung ohne Erkenntniswert; die aufgegebene Variante lebt stattdessen in Abschnitt 6 weiter, wo sie gebraucht wird.
- **Warum die Begründung ausdrücklich nicht lautet, der Repo-Weg sei gescheitert:** Er ist es nachweislich nicht (Kontext, Punkt 3 — Asset-Download HTTP 200, Prüfsumme exakt, Binary lauffähig). Eine Begründung, die eine technische Niederlage erfindet, wo eine Abwägung stattgefunden hat, macht eine spätere Umkehr unmöglich: Wer in einem Jahr liest „das ging nicht", prüft es nicht noch einmal. Deshalb steht das Messergebnis im Kontext und die Abwägung in Abschnitt 6.
- **Warum die zwei Orte für die Zahl benannt und nicht kaschiert werden:** Eine Zahl an zwei Orten ist keine Dokumentation, sondern ein Termin für einen Widerspruch. Man kann diesen Termin nicht wegformulieren, aber man kann ihn absichern (Test), verkleinern (nur ein ungesicherter Übergang) und laut machen (`doctor`/`finalize` melden beide Zahlen). Eine Spec, die stattdessen behauptete, das Kriterium sei erfüllt, wäre schlechter als eine, die die Lücke ausweist.
- **Warum der Wortlaut trotz „nichts im Repository" dokumentiert wird:** Die Anforderung war nie „das Repository soll nichts über die Umgebung wissen", sondern „das Repository soll die Umgebung nicht ausführen". Wissen ist billig und verlustfrei; Ausführungsabhängigkeit ist teuer. Die Grenze läuft zwischen beidem und ist in Abschnitt 2 mechanisch prüfbar formuliert.
- **Warum ein Fehlschlag hier laut sein darf, während er beim Hook leise sein musste:** Der Adressat ist ein anderer. Ein Setup-Script spricht zu einem Umgebungs-Build, der scheitern darf und dessen Protokoll gelesen wird; ein Hook spricht in eine laufende Session, die er nicht beschädigen darf. Dieselbe Handlung, zwei Zeitpunkte, zwei Fehlerregime — das ist der eigentliche inhaltliche Unterschied zwischen den beiden Varianten und der Grund, warum das Setup-Script mit deutlich weniger Sorgfaltsaufwand auskommt.
- **Warum der Dokumentationsteil unabhängig vom Ausgang fällig war und bleibt:** Der gesamte Entwicklungsablauf steht auf einem Werkzeug, das in keinem Dokument des Projekts vorkommt. Das war schon vor dem Befund ein Mangel und wäre es auch dann geblieben, wenn eine frische Umgebung `gh` mitgebracht hätte.

## Konsequenzen

- **Außerhalb des Repositories, von Daniel auszuführen:** Das Setup-Script der Cloud-Umgebung wird in der Weboberfläche um den Block aus Abschnitt 3 ergänzt; die Umgebung wird danach neu aufgebaut, damit der Snapshot den Zustand aufnimmt. Das ist ein manueller Schritt außerhalb des `developer`-Auftrags, wie die Rollout-Schritte in ADR 0037 Abschnitt 7, ADR 0046 und ADR 0052.
- **`docs/setup.md`:** neuer Abschnitt zur GitHub-CLI — wozu sie gebraucht wird (der gesamte Story-Lebenszyklus über `scripts/gh-board.py`), warum die Distributions-Paketquelle nicht genügt, wo die Mindestversion gepflegt wird (`MIN_GH_VERSION`), wie lokal installiert wird, der wörtliche Setup-Script-Block für Remote-Umgebungen samt Angabe, wo er einzutragen ist, und der Pflichtschritt „bei jeder Anhebung von `MIN_GH_VERSION` den Block hier **und** die Weboberfläche nachziehen".
- **Ein Test, der die Doku an die Konstante bindet** (`scripts/tests/`): liest `GH_VERSION` aus dem Skript-Block in `docs/setup.md` und vergleicht mit dem `MIN_GH_VERSION` des per Pfad geladenen `gh-board`-Moduls. Läuft im bestehenden CI-Job `demo-scripts` (`ruff` + `pytest` über `scripts/`, ohne Coverage-Gate — das 80%-Gate aus `CLAUDE.md` betrifft `backend/`). Das ist das einzige testbare Verhalten dieser Story und zugleich die in Abschnitt 4 zugesagte Absicherung.
- **Root-`README.md`:** unverändert. Es entsteht keine `.claude/settings.json`, also auch kein Anlass, `.claude/` in der Projektstruktur-Tabelle aufzunehmen.
- **`.gitignore`:** unverändert. Ohne eingecheckte `settings.json` gibt es keinen Anlass, `.claude/settings.local.json` zu ergänzen.
- **`.claude/skills/github-board/SKILL.md` und `.claude/skills/ship-feature/SKILL.md`:** die wörtliche Zahl `2.72.0` weicht dem Verweis auf die gepflegte Konstante `MIN_GH_VERSION` in `scripts/gh-board.py`. Der Agent verliert nichts — die Fehlermeldung des Werkzeugs führt die Zahl im Moment des Bedarfs selbst mit (`f"gh {MIN_GH_VERSION} ..."`). Sonst keine Änderung an den Skills.
- **`scripts/gh-board.py` bleibt unverändert** — keine Zeile.
- **Es entstehen nicht:** `.claude/settings.json`, `scripts/ensure-gh-cli.py`, ein Installations-Test, eine Datei unter `.github/workflows/`, ein Secret, eine neue Laufzeit-Abhängigkeit von Backend oder Frontend, eine Änderung an Board-Feldern.
- **Kein Effekt auf `docs/architecture.md`** — Entwickler-/Prozess-Tooling ohne Bezug zu Laufzeitarchitektur oder Datenmodell, gleiche Einordnung wie ADR 0017/0033/0037/0043/0046/0052. `docs/ai-workflow.md` bleibt unberührt: Ablauf und Rollenmodell ändern sich nicht.
- **Zwei Akzeptanzkriterien der Story sind vor der Review-Phase an der Quelle zu korrigieren** (Abschnitt 7): „Vorkehrung versioniert im Repository" und „eine Stelle für die Mindestversion". Ohne diese Korrektur meldet die Anforderungsprüfung zwei Verstöße, wo Entscheidungen vorliegen.
- **Der Nachweis** bleibt der aus der Story: In einer frisch gestarteten Remote-Session meldet `gh --version` eine ausreichende Version. Ein vollständiger schreibender Lebenszyklus-Durchlauf ist ausdrücklich nicht gefordert. Er kann erst nach dem Eintrag in die Weboberfläche und einem Neuaufbau der Umgebung erbracht werden — also nicht durch den `developer` und nicht am Repository-Stand allein.
- **Zwei Fragen bleiben offen und sind nicht Teil dieser Entscheidung:** ob eine neu **angelegte** Cloud-Umgebung `gh` von sich aus mitbringt (Daniels Lauf hatte einen frischen Container, aber keine frische Umgebungs-Konfiguration — die Anbieter-Dokumentation führt `gh` unter den vorinstallierten Werkzeugen, die Beobachtung widerspricht dem), und ob das GitHub-Project-Board über den Session-Proxy überhaupt erreichbar ist (nicht feststellbar, solange das Binary fehlt; die API-Beschränkung aus Kontext-Punkt 3 macht die Frage dringlich). Beide gehören in eine Folge-Story. Die zweite ist die von ADR 0052 Abschnitt 1 ausdrücklich offen gelassene.
- **Ebenfalls nicht Teil dieser Entscheidung:** weitere Werkzeuge (`jq`, `yq` …), ein Absenken von `MIN_GH_VERSION`, ein Rückbau der `closingIssuesReferences`-Prüfung, ein Nachweis von Schreibrechten, autonom laufende Agenten.
- Ein späterer Wechsel dieser Entscheidung — insbesondere die Rückkehr zu einer Vorkehrung im Repository (Abschnitt 6) — bleibt architekturrelevant und braucht eine neue, diese ADR als `Superseded` markierende ADR.
