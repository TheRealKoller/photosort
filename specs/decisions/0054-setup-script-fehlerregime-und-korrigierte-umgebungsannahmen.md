# 0054 - Fehlerregime des Setup-Scripts: die Session darf nicht am Werkzeug scheitern (korrigiert ADR 0053 in drei Punkten)

**Status:** Accepted
**Datum:** 2026-09-03
**Bezug:** GitHub-Issue [`#317`](https://github.com/TheRealKoller/photosort/issues/317), `specs/features/0317-setup-script-fehlerregime.md`, ADR [`0053`](./0053-gh-bereitstellung-per-umgebungs-setup-script.md) (Kontext-Punkt 6, Abschnitt 1 und Abschnitt 3 werden abgelöst), ADR [`0052`](./0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) (Abschnitt 1 — die dort offen gelassene Frage wird in Abschnitt 4 beantwortet), Spec [`0314`](../features/0314-gh-bereitstellung-remote-sessions.md) ([PR #315](https://github.com/TheRealKoller/photosort/pull/315), gemergt), Folge-Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318), `docs/setup.md`, `scripts/gh-board.py` (`MIN_GH_VERSION`)

Wie ADR 0052 gegenüber ADR 0017 Abschnitt 2 löst diese ADR benannte Abschnitte einer früheren Entscheidung ab und markiert **keine** ADR als `Superseded`. Die Richtungsentscheidung aus ADR 0053 — Bereitstellung außerhalb des Repositories, im Setup-Script der Cloud-Umgebung — bleibt unverändert gültig und wird hier ausdrücklich **nicht** angetastet. Korrigiert wird ihre Ausführung, nicht ihre Richtung.

## Kontext

ADR 0053 wurde auf Grundlage einer gemessenen Remote-Session und einer nur teilweise gelesenen Anbieter-Dokumentation entschieden. Nach dem Merge von PR #315 — und damit zu spät, um es dort noch zu berücksichtigen — hat eine gezielte Nachrecherche in der Anbieter-Dokumentation drei Aussagen zutage gefördert, die tragende Annahmen der ADR widerlegen. Alle drei sind wörtlich belegt.

1. **Ein Fehlschlag des Setup-Scripts blockiert den Start der Session — nicht nur den Aufbau der Umgebung.** Die Dokumentation formuliert es als harte Anforderung: „**Exit zero**: if the script exits non-zero, the session fails to start. Append `|| true` to non-critical commands so an intermittent install failure doesn't block the session."

   ADR 0053 Abschnitt 1 behauptet das Gegenteil, und zwar begründet und ausdrücklich: „**Das Skript darf laut scheitern.** `set -euo pipefail`, Abbruch bei jedem Fehlschlag. Ein gescheitertes Setup-Script ist ein sichtbar gescheiterter Umgebungs-Build mit einem Protokoll in der Oberfläche — und nicht, wie bei einem Hook, ein Vorgang, der eine laufende Session nicht beschädigen darf und deshalb jeden Fehlschlag in eine Meldung übersetzen muss. Es gibt hier keinen Grund, mit Exit-Code 0 zu enden." Genau dieser Grund existiert.

2. **Das Script läuft häufiger als angenommen.** ADR 0053 beschreibt es als „einmalig beim Einrichten der Umgebung". Tatsächlich läuft es, wenn kein zwischengespeicherter Zustand vorliegt: „The setup script runs again to rebuild the cache when you change the environment's setup script or allowed network hosts, and when the cache reaches its expiry after roughly seven days. Resuming an existing session never re-runs the setup script." Der Filesystem-Snapshot als Cache-Form (ADR 0053 Kontext-Punkt 6) stimmt; die Häufigkeit stimmt nicht.

   Zusammen mit Punkt 1 ist das der eigentliche Betriebsmangel: Nicht ein einmaliges Risiko beim Einrichten, sondern ein **wiederkehrendes** — etwa alle sieben Tage stellt sich die Frage neu, ob `github.com` in genau diesem Moment erreichbar ist und der Download innerhalb seines Zeitlimits durchläuft. Fällt die Antwort einmal negativ aus, startet keine neue Session mehr, bis jemand von Hand eingreift. Der Preis eines vorübergehenden Netzproblems wäre damit der vollständige Verlust des Zugangs zur Remote-Arbeit — für ein Werkzeug, das lediglich Komfort schafft.

3. **`gh` gilt laut Dokumentation als vorinstalliert.** Die Tabelle der mitgelieferten Werkzeuge führt unter „Utilities": `git, gh, jq, yq, ripgrep, tmux, vim, nano`, und ein eigener Abschnitt bekräftigt: „GitHub's `gh` CLI is pre-installed. […] `gh` reads `GH_TOKEN` automatically, so you don't need to run `gh auth login`."

   Das steht im Widerspruch zu Daniels zweifacher Messung (`command not found`, Exit-Code 127), auf der Spec 0309 und 0314 beruhen. Diese ADR löst den Widerspruch **nicht** auf — sie hält ihn fest. Eine Version nennt die Dokumentation ohnehin nicht, weshalb die Bindung an `MIN_GH_VERSION` unabhängig vom Ausgang nötig bleibt (Abschnitt 5).

Ein vierter Befund derselben Recherche betrifft nicht die Bereitstellung, sondern ihren Zweck, und ist deshalb bewusst **nicht** Gegenstand dieser ADR (siehe Abschnitt 4).

## Entscheidung

### 1. Das Setup-Script endet immer mit Exit-Code 0 — der Fehlschlag wird gemeldet, nicht durchgereicht

ADR 0053 Abschnitt 1, dritter Spiegelstrich („Das Skript darf laut scheitern") wird hiermit abgelöst. Er wird ersetzt durch:

> **Das Skript darf laut *melden*, aber nicht scheitern.** Ein Fehlschlag der Bereitstellung kostet die GitHub-CLI; er darf nicht zusätzlich die Session kosten.

Das ist keine Abschwächung der Sorgfalt, sondern eine Verschiebung ihres Angriffspunkts: Nicht mehr das Script als Ganzes bricht ab, sondern der Installationsteil in sich — und zwar unverändert hart.

### 2. Die Kapselung ist vorgeschrieben, nicht dem Geschmack überlassen — die naheliegende Schreibweise ist nachweislich falsch

Die zwei Eigenschaften „innen hart abbrechen" und „außen mit 0 enden" gleichzeitig zu erreichen, ist in `bash` **keine** Stilfrage. Die beiden naheliegenden Formen sind unbrauchbar, und das ist gemessen, nicht vermutet:

```
if ! ( set -e; ...; false; echo "wird trotzdem ausgefuehrt" ); then ...
( set -e; ...; false; echo "wird trotzdem ausgefuehrt" ) || warnen
```

In beiden Fällen unterdrückt `bash` das `set -e` im Rumpf der Subshell, weil sie Teil einer `if`-Bedingung bzw. einer `||`-Liste ist. Die Probe zeigte die Zeile nach dem Fehlschlag in **beiden** Varianten. Übertragen auf den Setup-Script-Block heißt das konkret: **Nach einer fehlgeschlagenen Prüfsummenprüfung wäre trotzdem entpackt und nach `/usr/local/bin` installiert worden.** Die vermeintliche Absicherung hätte die einzige Integritätsprüfung des Verfahrens ausgehebelt — sie wäre nicht bloß wirkungslos, sondern schädlich gewesen.

Verbindlich ist deshalb die Form, die die Probe als einzige besteht:

> Die Subshell steht **allein** als eigenständiges Kommando; ihr Ergebnis wird **danach** über `$?` ausgewertet. Sie steht nie in einer `if`-Bedingung und nie links einer `||`- oder `&&`-Liste.

Diese Begründung gehört als Kommentar in den Block selbst. Sie ist nicht offensichtlich, sie ist beim Bearbeiten leicht zu zerstören, und wer sie nicht kennt, „vereinfacht" die Form beim nächsten Anfassen genau in die kaputte Variante zurück.

### 3. Der abschließende Versionsaufruf darf selbst nicht zum Blocker werden

`gh --version` als letzte Zeile war unter dem alten Fehlerregime harmlos. Unter dem neuen ist es eine Falle: Fehlt `gh` — der Fall, den das neue Regime gerade überleben soll —, liefert die Zeile Exit-Code 127 und blockiert die Session, obwohl die Bereitstellung ihren Fehlschlag bereits sauber abgefangen hat. Der Aufruf wird deshalb gegen das Fehlen abgesichert, und das Script endet mit einem ausdrücklichen `exit 0`.

### 4. Die von ADR 0052 offen gelassene Board-Frage ist beantwortet — und gehört nicht hierher

Dieselbe Recherche beantwortet die Frage, die ADR 0052 Abschnitt 1 und Spec 0314 ausdrücklich offen ließen, weil sie ohne vorhandenes Binary nicht feststellbar war: „**GraphQL restrictions**: the proxy serves only a pinned set of GraphQL operations for pull-request workflows. […] The restriction applies to every request through the proxy regardless of the credentials you supply, so a `GH_TOKEN` you set gets the same 403. Claude can't reach GitHub APIs that exist only in GraphQL, such as Projects v2, through the proxy."

Projects v2 besitzt keine REST-Schnittstelle. Damit sind **sämtliche** Board-Operationen von `scripts/gh-board.py` (`project list`, `field-list`, `item-list`, `item-add`, `item-edit`) aus einer Cloud-Session heraus gesperrt — unabhängig davon, ob `gh` vorhanden ist und in welcher Version, und unabhängig von den hinterlegten Zugangsdaten. Die Schritte über Issues und Pull Requests bleiben nutzbar; der Lebenszyklus zerfällt, statt vollständig auszufallen.

**Das ist hier nur festgestellt, nicht entschieden.** Der Befund trifft den Zweck der Vorarbeit, nicht ihre Ausführung, und die möglichen Antworten — Remote-Arbeit auf die tragenden Schritte beschränken, das Board über einen anderen Weg erreichen, den Board-Zustand nicht mehr ausschließlich in GitHub führen, oder dem Board seine Rolle als verbindlicher Zustandsspeicher nehmen — unterscheiden sich in Tragweite und Preis erheblich. Eine solche Richtungsentscheidung nebenbei in einer Korrektur-ADR zu treffen, wäre genau die Art stiller Weichenstellung, die dieses Verzeichnis verhindern soll. Sie ist als Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318) erfasst und braucht eine eigene ADR.

Bis dahin gilt: Die Bereitstellung der CLI bleibt richtig und nützlich — sie trägt die Issue- und PR-Schritte, sie schließt die Dokumentationslücke, und sie ist Vorbedingung jeder Antwort auf #318, die das Board doch noch erreichbar macht.

### 5. Was ausdrücklich unverändert bleibt

- **Die Richtungsentscheidung** aus ADR 0053 Abschnitt 1 (Bereitstellung im Setup-Script der Cloud-Umgebung), Abschnitt 2 (kein ausführbares Artefakt im Repository, in sich abgeschlossen) und Abschnitt 3 (der Wortlaut wird dokumentiert). Der Auslöser für eine spätere Umkehr (ADR 0053 Abschnitt 6 — eine zweite dauerhaft betriebene Umgebung) bleibt gültig.
- **Alle Sicherheits-Muss-Eigenschaften** des Blocks: unauthentifiziert, `--proto '=https' --proto-redir '=https' --tlsv1.2` auf beiden `curl`-Aufrufen, Prüfsummenverifikation vor jeder Verwendung, genau ein benanntes Archivmitglied, `install -m 0755` nach `/usr/local/bin`, `mktemp -d` mit `trap`-Aufräumung, kein Paketmanager, kein neues Geheimnis, ausschließlich druckbares ASCII.
- **`MIN_GH_VERSION` als autoritativer Wert** und seine Bindung an den dokumentierten Block per CI-Test (ADR 0053 Abschnitt 4). Befund 3 ändert daran nichts: Selbst wenn `gh` vorinstalliert ist, nennt die Dokumentation keine Version, und die Idempotenz-Vorprüfung des Blocks entscheidet dann ohnehin von selbst richtig.
- **`scripts/gh-board.py` bleibt zeilenweise unverändert.** Die Festlegung „melden, nicht reparieren" (ADR 0052 Abschnitt 4/5) wird nicht berührt.

## Begründung

- **Warum das Fehlerregime umgedreht wird, statt den Fehlschlag unwahrscheinlicher zu machen:** Ein Zeitlimit hochsetzen oder Wiederholungsversuche einbauen verschiebt nur die Wahrscheinlichkeit; die Kopplung „Werkzeug nicht beschaffbar ⇒ kein Zugang zur Arbeitsumgebung" bliebe bestehen. Diese Kopplung ist das Problem, nicht ihre Eintrittshäufigkeit — und sie ist grob unverhältnismäßig, weil ein Komfortwerkzeug den Zugang als Ganzes verwettet.
- **Warum die Kapselungsform vorgeschrieben und begründet wird, statt sie nur zu zeigen:** Sie sieht umständlicher aus als die naheliegende Alternative und lädt zur „Vereinfachung" ein. Da der Block außerhalb des Repositories lebt und dort nie wieder reviewt wird, gäbe es keine zweite Gelegenheit, den Rückbau zu bemerken — und sein Ergebnis wäre eine Installation ohne wirksame Integritätsprüfung. Die Begründung im Kommentar ist deshalb kein Beiwerk, sondern die einzige verbliebene Schutzschicht.
- **Warum die Anbieter-Dokumentation diesmal wörtlich zitiert wird:** ADR 0053 stützte sich auf eine sinngemäße Wiedergabe („Die Dokumentation der Cloud-Umgebungen empfiehlt für diesen Fall ausdrücklich den ersten Weg"), und genau daneben stand die Aussage über den Exit-Code, die nicht mitgelesen wurde. Wörtliche Zitate machen bei der nächsten Prüfung nachvollziehbar, was tatsächlich dastand und was daraus geschlossen wurde.
- **Warum Befund 3 (`gh` vorinstalliert) den Widerspruch nicht auflöst:** Zwei zuverlässige Quellen widersprechen sich — eine Dokumentation und zwei eigene Messungen. Ohne eine Beobachtung in einer frisch **angelegten** Umgebung ist nicht entscheidbar, welche recht hat; Daniels Container war frisch, seine Umgebungs-Konfiguration nicht. Die Entscheidung ist gegen den Widerspruch robust: Ist `gh` da und neu genug, tut der Block nichts und sagt das; fehlt es, beschafft er es; scheitert das, startet die Session trotzdem.
- **Warum der Board-Befund ein eigenes Issue bekommt, obwohl er in derselben Recherche auffiel:** Er beantwortet eine Frage, die zwei ADRs ausdrücklich offen gelassen haben, und seine Konsequenzen reichen bis zur Frage, ob das GitHub-Board überhaupt der richtige Zustandsspeicher ist. Das ist keine Korrektur, sondern eine Neubewertung — und sie gehört nicht in einen Pull Request, der einen Fehler von gestern behebt.

## Konsequenzen

- **`docs/setup.md`:** Der Setup-Script-Block wird durch die abgesicherte Fassung ersetzt (Abschnitte 1–3). Der umgebende Text wird an drei Stellen korrigiert: wann das Script läuft (einschließlich des wiederkehrenden Neuaufbaus), was ein Fehlschlag bewirkt, und der Hinweis, dass `gh` laut Anbieter-Dokumentation eigentlich vorinstalliert sein sollte — samt der abweichenden Beobachtung und der Feststellung, dass der Block beide Fälle trägt.
- **`scripts/tests/test_setup_docs.py`:** Die bestehenden Zusicherungen (Bindung an `MIN_GH_VERSION`, Zeichenvorrat der Kopiervorlage) gelten unverändert für den neuen Block. Hinzu kommt eine Zusicherung, die den in Abschnitt 2 vorgeschriebenen Kapselungs-Fallstrick am dokumentierten Text festhält: Der Block enthält keine der beiden kaputten Formen. Das ist die einzige Eigenschaft dieser ADR, die am Repository-Stand prüfbar ist — der Rest ist Textprüfung im Review.
- **`specs/features/0314-*.md`:** Der Abschnitt „Offene Fragen"/„Out of Scope" wird um die inzwischen belegten Antworten ergänzt, mit Verweis hierher und auf #318. Die Spec bleibt `Implemented`; sie wird nicht rückwirkend umgeschrieben, sondern um den Kenntnisstand ergänzt.
- **`specs/architecture/0003-securitykonzept.md`:** Der Abschnitt zur Toolchain-Bereitstellung erhält den `bash`-Fallstrick als benannte Angriffsfläche — eine „Absicherung", die die Integritätsprüfung stillschweigend aushebelt, ist sicherheitsrelevant, nicht bloß ein Stilfehler.
- **`specs/architecture/0002-testkonzept.md`:** Die Sektion zu ADR 0053 wird um die dritte prüfbare Hinsicht des dokumentierten Blocks ergänzt (Kapselungsform), in derselben Logik wie die 2026-09-03 ergänzte Zeichenvorrats-Prüfung.
- **Außerhalb des Repositories, von Daniel auszuführen:** Der Block in der Weboberfläche wird durch die neue Fassung ersetzt. Wurde die alte bereits eingetragen, ist das dringlich — sie ist die Fassung mit dem Session-Blocker.
- **Es entstehen nicht:** eine Änderung an `scripts/gh-board.py`, `.claude/settings.json`, ein Hook, eine Workflow-Datei, ein Secret, eine neue Abhängigkeit, eine Änderung an `docs/architecture.md` oder `docs/ai-workflow.md`.
- **Offen und ausdrücklich nicht entschieden:** die Konsequenz aus dem Board-Befund (Issue #318), und ob eine frisch angelegte Cloud-Umgebung `gh` mitbringt und in welcher Version.
