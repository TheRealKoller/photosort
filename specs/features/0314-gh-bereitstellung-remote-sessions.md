# 0314 - `gh`-Bereitstellung für Remote-Sessions: Setup-Script der Umgebung, im Repository nur die dokumentierte und CI-geprüfte Fassung

**Status:** Implemented ([PR #315](https://github.com/TheRealKoller/photosort/pull/315))
**Erstellt:** 2026-09-03
**Bezug:** GitHub-Issue [`#314`](https://github.com/TheRealKoller/photosort/issues/314), ADR [`0053`](../decisions/0053-gh-bereitstellung-per-umgebungs-setup-script.md), Vorgänger-Spec [`0309`](./0309-story-lebenszyklus-remote-sessions.md), ADR [`0052`](../decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md), ADR [`0046`](../decisions/0046-pr-issue-verknuepfung-closing-keyword.md), `scripts/gh-board.py` (`MIN_GH_VERSION`), `docs/setup.md`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Spec [`0309`](./0309-story-lebenszyklus-remote-sessions.md) hat den Blocker belegbar gemacht: In der Remote-Session fehlt `gh` schlicht (`command not found`, Exit-Code 127), und alle neun `doctor`-Prüfungen scheitern an dieser **einen** Ursache. Ein zweiter Lauf Daniels in einer echten Remote-Session hat den Befund reproduziert und mehr geklärt als gefordert: Der Bezug eines Release-Assets von `github.com` gelingt dort unauthentifiziert (HTTP 200, Prüfsumme exakt, Binary lauffähig) — gesperrt ist allein die **API** für Repositories, die der Session nicht zugeordnet sind (403).

Damit war nicht mehr die Frage, *ob* eine Vorkehrung technisch trägt, sondern **wo** sie liegt. Entschieden ist: im Setup-Script der Cloud-Umgebung, das einmalig beim Einrichten läuft und als Snapshot gecacht wird — nicht im Repository. Im Repository entsteht keine ausführbare Vorkehrung, wohl aber der **wörtliche Text** des Setup-Scripts plus ein CI-Test, der dessen Zielversion an `MIN_GH_VERSION` bindet.

Unabhängig davon behebt diese Spec einen zweiten, älteren Mangel: Die Voraussetzung `gh` steht im Projekt bisher **nirgends** — weder in `README.md` noch in `docs/setup.md` noch in `CLAUDE.md` —, obwohl der gesamte Entwicklungsablauf darauf steht. Eine frische Umgebung ist heute aus dem Repository heraus nicht korrekt einrichtbar, remote nicht und auf einem neuen Rechner ebenso wenig.

## User Story

Als Daniel möchte ich eine frisch gestartete Remote-Session sofort produktiv nutzen können, ohne vorher von Hand Werkzeuge nachzuinstallieren, damit Remote-Arbeit ein normaler Arbeitsmodus wird und nicht jedes Mal mit einem Einrichtungsumweg beginnt.

## Akzeptanzkriterien

Wortgleich zum Issue-Body von [`#314`](https://github.com/TheRealKoller/photosort/issues/314) in seiner korrigierten Fassung. Zwei Kriterien der ursprünglichen Fassung — „Vorkehrung versioniert im Repository" und „eine Stelle für die Mindestversion" — hat Daniel nach Vorliegen des Befunds bewusst umgekehrt bzw. aufgegeben; das ist in ADR 0053, Abschnitt 4 und 7, festgehalten und im Issue bereits nachgezogen.

### Bereitstellung

- [ ] In einer frisch gestarteten Remote-Session steht die GitHub-CLI in ausreichender Version zur Verfügung, ohne dass Daniel vor der Arbeit einen Handgriff tut.
- [ ] Die Bereitstellung liegt in der Konfiguration der Cloud-Umgebung, nicht im Repository. Sie läuft einmalig beim Einrichten der Umgebung, nicht bei jedem Sessionstart.
- [ ] Der Bezug erfolgt unauthentifiziert und erzeugt kein zusätzliches, dauerhaft abgelegtes Geheimnis.
- [ ] Das bezogene Artefakt wird vor der Verwendung gegen die vom Herausgeber mitgelieferte Prüfsumme verifiziert.
- [ ] An lokalen Arbeitsplätzen ändert sich nichts: keine zusätzliche Datei, die jede Session beeinflusst, keine Verzögerung beim Start, kein Eingriff in eine vorhandene Installation.
- [ ] Die Board-Werkzeuge installieren weiterhin **nichts** selbst nach, sondern melden nur — die Festlegung aus Spec 0309 bleibt unberührt.

### Dokumentation

- [ ] Die Voraussetzung ist in der Setup-Dokumentation festgehalten: dass die GitHub-CLI gebraucht wird, wofür, welche Mindestversion gilt und warum die übliche Distributions-Paketquelle dafür nicht genügt.
- [ ] Der Inhalt der Umgebungs-Vorkehrung ist im Repository dokumentiert, sodass eine neu angelegte Umgebung ohne Rekonstruktion wieder eingerichtet werden kann. Er liegt zwar nicht im Repository, aber er ist von dort ablesbar.
- [ ] Es ist benannt, dass die Zielversion dadurch an zwei Stellen existiert (im Code und in der Umgebungs-Konfiguration), welche davon maßgeblich ist, und woran ein Auseinanderlaufen auffällt.

### Nachweis

- [ ] In einer frisch gestarteten Remote-Session meldet die GitHub-CLI eine ausreichende Version. Ein vollständiger schreibender Lebenszyklus-Durchlauf ist ausdrücklich **nicht** als Nachweis gefordert.

## Datenmodell-Bezug

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug und Dokumentation und keine Anwendungsentität — weder Projekte, Fotos, Kategorien noch Klassifizierungsläufe. Keine Änderung an [`docs/architecture.md`](../../docs/architecture.md) nötig; die Einordnung entspricht ADR 0017/0033/0037/0043/0046/0052, die ebenfalls ohne Architektur-Update auskamen.

## Architektur / Umsetzung

Grundlage ist ADR [`0053`](../decisions/0053-gh-bereitstellung-per-umgebungs-setup-script.md). Die Umsetzung im Repository ist klein, weil die eigentliche Bereitstellung **außerhalb** liegt. Die Grenze ist mechanisch prüfbar formuliert (ADR 0053, Abschnitt 2):

> **Das Setup-Script ist in sich abgeschlossen. Es liest, klont und führt zur Provisionierungszeit nichts aus dem Repository aus.**

Daraus folgt: Der in `docs/setup.md` dokumentierte Block ist ein **Referenztext für Menschen**. Er wird von niemandem ausgeführt und von der Umgebung nicht gelesen — auch nicht von einem Agenten, der die Datei liest. Das Setup-Script in der Weboberfläche bleibt eine eigenständige Kopie.

**Betroffene Dateien:**

| Datei | Änderung |
|---|---|
| `docs/setup.md` | neuer Abschnitt „GitHub-CLI (`gh`)" inkl. wörtlichem Setup-Script-Block |
| `scripts/tests/test_setup_docs.py` | **neu**: bindet `GH_VERSION` aus dem Block an `MIN_GH_VERSION` |
| `scripts/tests/conftest.py` | `gh_board`-Loader aus `test_gh_board.py` hierher heben |
| `scripts/tests/test_gh_board.py` | nutzt den gehobenen Loader statt des modul-lokalen |
| `.claude/skills/github-board/SKILL.md` | wörtliche `2.72.0` → Verweis auf `MIN_GH_VERSION` |
| `.claude/skills/ship-feature/SKILL.md` | wörtliche `2.72.0` → Verweis auf `MIN_GH_VERSION` |

**`scripts/gh-board.py` bleibt zeilenweise unverändert.** Es entstehen nicht: `.claude/settings.json`, ein Hook, ein Installationsskript, eine Datei unter `.github/workflows/`, ein Secret, eine Änderung an `README.md`, `.gitignore`, `docs/architecture.md` oder `docs/ai-workflow.md`.

### Schritt 1 — `docs/setup.md`: neuer Abschnitt „GitHub-CLI (`gh`)"

Inhaltlich zu tragen hat der Abschnitt sechs Dinge, entsprechend den Dokumentations-Akzeptanzkriterien:

1. **Wozu**: der gesamte Story-Lebenszyklus läuft über `scripts/gh-board.py` und damit über `gh`.
2. **Mindestversion**: gepflegt als `MIN_GH_VERSION` in `scripts/gh-board.py` — das ist der **autoritative** Wert. Keine zweite Zahl im Prosatext.
3. **Warum die Distributions-Paketquelle nicht genügt**: Ubuntu liefert 2.45.x; `gh pr view --json closingIssuesReferences` — die Vorbedingung, an der `finalize` laut ADR 0046 die PR-Issue-Verknüpfung prüft — existiert erst ab 2.72.0. `apt install gh` verdeckt das Problem, statt es zu lösen (`gh` da, `finalize` trotzdem blockiert).
4. **Lokale Installation**: kurzer Hinweis auf die offizielle Bezugsquelle.
5. **Remote-Umgebungen**: der wörtliche Block aus ADR 0053, Abschnitt 3, samt Angabe, **wo** er einzutragen ist (Setup-Script in der Weboberfläche der Cloud-Umgebung) und dass die Umgebung danach neu aufzubauen ist, damit der Snapshot den Zustand aufnimmt.
6. **Der Pflichtschritt bei jeder Anhebung von `MIN_GH_VERSION`**: Block hier **und** Weboberfläche nachziehen. Dazu die benannte Lücke aus ADR 0053, Abschnitt 4: Die Zahl existiert zwangsläufig an zwei Orten, `MIN_GH_VERSION` ist maßgeblich, der CI-Test deckt den Übergang Code → Doku ab, ungesichert bleibt allein die Übertragung Doku → Weboberfläche. Woran ein Auseinanderlaufen auffällt: `doctor` meldet `gh_version` als fehlgeschlagen und nennt beide Zahlen, `abschluss-finalisieren` erscheint unter `blocked_lifecycle_steps`, und `finalize` bricht mit einer Meldung ab, die die Mindestversion nennt — **vor** jedem Schreibzugriff, es ist also nichts zurückzunehmen.

Am Block selbst ist zu verankern, dass er ein nicht auszuführender Referenztext ist.

### Schritt 2 — `scripts/tests/conftest.py`: `gh_board`-Loader hochziehen

Der Loader für `gh-board.py` liegt heute in `scripts/tests/test_gh_board.py`. Fixtures aus einem Testmodul sind **modul-lokal** — das neue Testmodul kommt nicht daran. Der Loader wandert deshalb nach `conftest.py`, neben den dort schon vorhandenen `seed_module`-Loader (`scripts/tests/conftest.py:26`), der als Vorbild dient: Laden per Pfad, weil `gh-board.py` mit Bindestrich kein gültiger Modulname ist, `scope="session"`.

`test_gh_board.py` nutzt danach den gehobenen Loader. Es ist eine reine Verschiebung: **kein bestehender Test ändert seine Zusicherung**, und der Bestand von 195 Tests in dieser Datei bleibt grün.

### Schritt 3 — `scripts/tests/test_setup_docs.py` (neu)

Der Test liest `GH_VERSION` aus dem Skript-Block in `docs/setup.md` und stellt ihn gegen `MIN_GH_VERSION` des per Pfad geladenen `gh-board`-Moduls. Er ist das **einzige testbare Verhalten** dieser Story und zugleich die in ADR 0053, Abschnitt 4, zugesagte Absicherung: Wird die Konstante angehoben, ohne den Block nachzuziehen, wird CI rot — sofort, nicht irgendwann.

Zwei Präzisierungen aus der `test-engineer`-Konsultation, die den Test tragfähig statt scheinbar-grün machen:

- **Der Extraktions-Regex braucht einen Zeilenanfangs-Anker** (`^GH_VERSION=`, `re.MULTILINE`). Ohne ihn färbt jede Erwähnung von `GH_VERSION` im Fließtext den „mehr als ein Treffer"-Test rot.
- **Genau ein Treffer ist zuzusichern.** Kein Treffer (Block umbenannt, Doku umgebaut) und mehrere Treffer (ein zweiter Block schleicht sich ein) sind beide Fehlerfälle mit eigener Meldung — ein Test, der still auf den ersten Treffer zeigt, hätte den Zweck verfehlt.

### Schritt 4 — die wörtliche `2.72.0` aus den beiden Skills entfernen

`.claude/skills/github-board/SKILL.md:60` und `.claude/skills/ship-feature/SKILL.md:111` nennen die Zahl heute im Prosatext. Sie weicht dem Verweis auf die gepflegte Konstante `MIN_GH_VERSION` in `scripts/gh-board.py`. Der Agent verliert dadurch nichts: Die Fehlermeldung des Werkzeugs führt die Zahl im Moment des Bedarfs selbst mit (`f"gh {MIN_GH_VERSION} …"`, `scripts/gh-board.py:1153`/`1162`). Sonst keine Änderung an den Skills.

**Fallstrick:** In der Befehlstabelle von `github-board/SKILL.md` **keine neue Zeile** einführen, die mit einem klein geschriebenen Backtick-Token beginnt — sonst bricht `test_die_cli_kennt_genau_die_in_der_skill_tabelle_dokumentierten_befehle`. Die Änderung ist ohnehin eine Textersetzung im Fließtext, keine Tabellenzeile.

### Manueller Schritt außerhalb des `developer`-Auftrags

Bleibt bei Daniel, wie die Rollout-Schritte in ADR 0037 Abschnitt 7, ADR 0046 und ADR 0052: den Block aus `docs/setup.md` in das Setup-Script der Cloud-Umgebung eintragen, die Umgebung neu aufbauen, dann `gh --version` in einer frisch gestarteten Remote-Session ausführen und das Ergebnis an #314 dokumentieren. Das ist der Nachweis der Story; er ist am Repository-Stand allein nicht erbringbar.

### Teststrategie

Der einzige neue Test ist der Doku-Bindungstest aus Schritt 3 — kein echtes `gh`, kein Netzwerk, kein Zugriff auf die Weboberfläche. Er läuft im bestehenden CI-Job `demo-scripts` (`ruff check .` + `pytest` über `scripts/`, **ohne** `--cov`; das 80%-Gate aus `CLAUDE.md` betrifft `backend/`).

**Was ausdrücklich nicht getestet wird und warum:** der Setup-Script-Block selbst. Er liegt außerhalb des Repositories, wird von CI nicht ausgeführt und ließe sich nur mit Netzwerkzugriff und Root-Rechten prüfen — beides hat `demo-scripts` nicht. Ein Test, der lediglich die Anwesenheit von Zeichenketten im Block behauptet, wäre eine Zusicherung über Text, nicht über Verhalten. Die Eigenschaften des Blocks (Idempotenz, `sort -V`, unauthentifiziert, Prüfsumme, ein benanntes Archivmitglied, kein Paketmanager) sind deshalb in ADR 0053, Abschnitt 3, als verbindlich festgehalten statt in Tests behauptet.

**Nicht-Regression:** Der Bestand von 241 Tests unter `scripts/tests/` — davon 195 in `test_gh_board.py` — bleibt vollständig grün. Die Loader-Verschiebung aus Schritt 2 ist die einzige Berührung und ändert keine Zusicherung.

## UI/UX

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug und Dokumentation und hat an keiner Stelle eine sichtbare Oberfläche — kein Pfad unter `frontend/`, keine dargestellten Daten, keine berührte Komponente.

## Security

Sicherheitsrelevant, aber kein Blocker (Einschätzung des `security-engineer` für diese Story). Die Lage ist ungewöhnlich: Das sicherheitskritische Artefakt — das Setup-Script — liegt außerhalb des Repositories und ist damit **nicht reviewbar**; im Repository liegt nur seine dokumentierte Fassung. Umso mehr hängt an den Eigenschaften des dokumentierten Blocks.

**Muss-Kriterien:**

1. **Unauthentifiziert.** Kein `GH_TOKEN`, kein `GITHUB_TOKEN`, kein `Authorization`-Header, kein neu abgelegtes Geheimnis. Deckt sich mit ADR 0052, Abschnitt 6, und ist Akzeptanzkriterium der Story.
2. **TLS erzwungen, auch über die Umleitung.** Beide `curl`-Aufrufe tragen `--proto '=https' --proto-redir '=https' --tlsv1.2`. Der zweite Schalter ist **nicht** redundant: `--proto` bindet nur den initialen Aufruf, der Weg läuft planmäßig über eine Umleitung auf `release-assets.githubusercontent.com`, und eine erzwungene `http`-Umleitung hätte Archiv **und** Prüfsummendatei konsistent ersetzen können — womit die einzige Integritätsprüfung ausgehebelt gewesen wäre. Dieser Fund des `security-engineer` ist behoben.
3. **Prüfsumme gegen `gh_<version>_checksums.txt` aus demselben Release**, vor Entpacken und vor `install`. Ehrlich benannt: Das schützt gegen abgebrochene und verfälschte Übertragung, nicht gegen einen kompromittierten Ursprung — die Prüfsumme stammt von dort. Vertrauensanker ist TLS zu `github.com` plus die versionsfest adressierte Release-URL; derselbe Anker, an dem das Projekt ohnehin hängt.
4. **Genau ein benanntes Archivmitglied wird entpackt**, nicht das Archiv. Kein Archivinhalt bestimmt einen Zielpfad (kein Path-Traversal über ein manipuliertes Archiv).
5. **Kein Paketmanager**, kein zusätzliches Repository, kein Fremdschlüssel im Keyring.
6. **Die Board-Werkzeuge installieren nichts nach.** `scripts/gh-board.py` bleibt unverändert; `doctor` meldet und repariert nicht (ADR 0052, Abschnitt 4/5). Eine Vorkehrung beim Einrichten der Umgebung ist ausdrücklich etwas anderes als ein Werkzeug, das sich zur Laufzeit selbst hilft.
7. **Der dokumentierte Block ist ein Referenztext, den kein Agent ausführt.** Am Block selbst zu verankern.

**Bewusst akzeptiertes Restrisiko** (Empfehlung des `security-engineer`, von Daniel zu bestätigen): **kein** zusätzlich fest verdrahteter SHA256-Pin je Architektur. Anders als in ADR 0033, wo die URL auf eine bewegliche Referenz (`resolve/main`) zeigt und der Hash die einzige Festlegung ist, *was* geladen wird, ist hier die Adresse selbst schon die Festlegung. Ein Pin wären zwei weitere versionsabhängige Zahlen, von Hand zu übertragen, ausgerechnet im nicht reviewbaren Artefakt; CI könnte sie nur auf Vorhandensein prüfen, nicht auf Richtigkeit.

Details in `specs/architecture/0003-securitykonzept.md`.

## Entscheidungen

1. **Bereitstellung im Setup-Script der Cloud-Umgebung, nicht im Repository** (Daniel, zweistufig: erst grundsätzlich dem Anbieter-Weg folgen, dann auf Rückfrage ausdrücklich die Vollvariante ohne aufgerufenes Repo-Skript). Der Repo-Weg ist **nicht technisch gescheitert** — der Remote-Lauf belegt das Gegenteil; er ist unterlegen bewertet worden. Der Auslöser für eine Umkehr steht in ADR 0053, Abschnitt 6: sobald eine zweite Umgebung dauerhaft dazukommt.
2. **Kein Mittelweg** (Logik als `scripts/…`-Datei, Weboberfläche ruft sie auf): verworfen, weil er an drei unbelegten Annahmen über den Provisionierungszeitpunkt hängt (Repository ausgecheckt, Pfad bekannt, Fassung passend).
3. **Der Wortlaut wird trotzdem dokumentiert.** „Nichts im Repository" bezieht sich auf **ausgeführte** Artefakte, nicht auf Wissen. Wissen ist billig und verlustfrei; Ausführungsabhängigkeit ist teuer.
4. **Die Zielversion an zwei Orten wird ausgewiesen statt beschwiegen** (ADR 0053, Abschnitt 4). Das Akzeptanzkriterium „eine Stelle" ist unter dieser Entscheidung strukturell nicht erfüllbar; erreicht wird stattdessen die Reduktion auf genau **einen** ungesicherten Übergang, und der ist eine Ausrollhandlung.
5. **Diese Spec bleibt nötig, nicht aus Formalismus:** `cmd_finalize` (`scripts/gh-board.py:907`) ruft `find_spec_path` **vor jedem** GitHub-Zugriff und verlangt eine Spec-Datei im Status `Accepted`/`Implemented`. Ohne diese Datei ist die Story über den Regelweg nicht abschließbar.

## Offene Fragen

Keine, die die Umsetzung blockiert. Zwei Punkte gehen an Daniel und sind ohne Antwort umsetzbar (die Umsetzung folgt jeweils der Empfehlung):

1. **Zusätzlicher SHA256-Pin je Architektur im dokumentierten Block?** Empfehlung: nein, Restrisiko akzeptieren (siehe Security).
2. **Gehört die Regel „dokumentierte Shell-Blöcke in `docs/` sind Referenztexte, die kein Agent ausführt" allgemein in `CLAUDE.md`?** Bisher nur am Block selbst verankert. Eine `CLAUDE.md`-Änderung ist Projektverfassung und war nicht Teil dieser Story.

## Nachtrag vom 2026-09-03 — was nach dem Merge über die Umgebung bekannt wurde

Diese Spec bleibt `Implemented` und wird bewusst **nicht** rückwirkend umgeschrieben; der Erkenntnisstand wird sichtbar fortgeschrieben statt nachträglich geglättet. Eine Nachrecherche in der Anbieter-Dokumentation — angestoßen durch Daniels Frage, wo das Setup-Script überhaupt einzutragen ist — hat nach dem Merge von PR #315 drei Aussagen zutage gefördert, die Annahmen dieser Spec und von ADR 0053 widerlegen. Alle drei sind in ADR [`0054`](../decisions/0054-setup-script-fehlerregime-und-korrigierte-umgebungsannahmen.md) wörtlich belegt.

1. **Der dokumentierte Block, so wie diese Spec ihn hinterlassen hat, konnte den Sessionstart blockieren.** Ein Setup-Script, das mit einem Fehler endet, verhindert den Start der Session — nicht nur den Aufbau der Umgebung, wie ADR 0053 Abschnitt 1 ausdrücklich annahm. Zusammen mit dem Neuaufbau alle rund sieben Tage war das ein wiederkehrendes Risiko. Behoben durch Spec [`0317`](./0317-setup-script-fehlerregime.md).
2. **Das Script läuft nicht einmalig beim Einrichten**, sondern immer, wenn kein zwischengespeicherter Zustand vorliegt — nach jeder Änderung am Script oder an den erlaubten Netzwerkzielen und nach etwa sieben Tagen Ablauf. Die Snapshot-Form des Zwischenspeichers stimmt, die Häufigkeit stimmte nicht.
3. **`gh` gilt laut Anbieter-Dokumentation als vorinstalliert**, im Widerspruch zu den zwei Messungen, auf denen diese Spec und Spec 0309 beruhen. Der Widerspruch ist ungelöst; er ändert nichts an der Notwendigkeit der Versionsbindung, weil die Dokumentation keine Version nennt.

**Die beiden hier offen gelassenen Fragen sind inzwischen beantwortet — eine davon negativ:**

- *„Keine Klärung, ob das Board über den Session-Proxy erreichbar ist"*: Es ist **nicht** erreichbar. Der Vermittler lässt auf der GraphQL-Schnittstelle nur einen festen Satz von Operationen rund um Pull Requests zu und nennt Projects v2 ausdrücklich als nicht erreichbar — unabhängig von den hinterlegten Zugangsdaten. Damit sind sämtliche Board-Operationen von `scripts/gh-board.py` aus einer Cloud-Session gesperrt, auch mit vorhandener und ausreichend neuer CLI. Die Issue- und PR-Schritte bleiben nutzbar. Was daraus folgt, ist als Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318) erfasst und braucht eine eigene ADR.
- *„Keine Klärung, ob eine neu angelegte Cloud-Umgebung die CLI von sich aus mitbringt"*: weiterhin offen, siehe Punkt 3 — Dokumentation und Messung widersprechen sich, und nur eine Beobachtung in einer frisch angelegten Umgebung kann das entscheiden.

Der Nutzen dieser Spec bleibt davon unberührt: Die Dokumentationslücke ist geschlossen, die Zielversion ist an `MIN_GH_VERSION` gebunden, und die CLI trägt die Issue- und PR-Schritte. Sie ist zudem Vorbedingung jeder Antwort auf #318, die das Board doch noch erreichbar macht.

## Out of Scope

- **Keine Vorkehrung im Repository.** Keine Datei, die bei jedem Sessionstart ausgeführt wird, keine Installationslogik im Projekt. Der Preis — nicht versioniert, nicht reviewbar, bei einer neu angelegten Umgebung erneut zu setzen — ist bekannt und in Kauf genommen. Der Rückweg bleibt offen.
- **Kein Nachladen durch die Board-Werkzeuge selbst.** Sie melden einen fehlenden oder zu alten Zustand klar und brechen ab.
- **Kein Absenken von `MIN_GH_VERSION`** und kein Rückbau der `closingIssuesReferences`-Prüfung, die sie nötig macht.
- **Keine Klärung, ob eine neu angelegte Cloud-Umgebung `gh` von sich aus mitbringt.** Bei der Prüfung war nur der Container frisch, nicht die zugrundeliegende Umgebungs-Konfiguration; die Anbieter-Dokumentation führt `gh` unter den vorinstallierten Werkzeugen, die Beobachtung widerspricht dem. Bleibt offen, Folge-Story.
- **Keine Klärung, ob das Board über den Session-Proxy erreichbar ist.** Solange die CLI fehlt, nicht feststellbar; die API-Beschränkung (403 auf `api.github.com` für fremde Repositories) macht die Frage dringlich. Sie ist die von ADR 0052, Abschnitt 1, ausdrücklich offen gelassene und gehört in eine eigene Story.
- **Kein Nachweis von Schreibrechten.**
- **Keine Ausweitung auf weitere Werkzeuge** (`jq`, `yq` …) und keine Ausweitung auf autonom laufende Agenten.
