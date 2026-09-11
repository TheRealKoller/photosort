# 0411 - Doku im Code bleibt knapp und wächst nicht nach

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** [Issue #411](https://github.com/TheRealKoller/photosort/issues/411)
**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec fünf Pull Requests trägt und
die Regeln, gegen die jeder einzelne Schnitt zu prüfen ist, vollständig führen muss — eine
verkürzte Fassung verlöre genau die Aussagen, deren Verlust sie verhindern soll.

## Ziel

Der Produktivcode trägt mehr Dokumentation, als er tragen soll. Die Doku-Ballast-Regel aus
`CLAUDE.md` gilt dort bereits, greift aber nicht: Die einmalige Verdichtung hat den Frontend-Code
nie erreicht, der mechanische Schnitt durch die Verweise ist nie gefallen, und für neu
geschriebenen Code gibt es keinen Punkt im Ablauf, an dem die Regel geprüft würde. Jede
Verdichtung bleibt damit eine Momentaufnahme, die sofort wieder zuwächst.

Dazu kommt ein zweiter Befund: Der heutige Schutz für Invarianten hängt an einem so weiten
Vokabular, dass sich nahezu jeder Kommentar darunter begründen lässt. Er schützt deshalb nicht die
Aussage, sondern auch ihre gesamte Herleitung.

## User Story

Als Entwickler an PhotoSort möchte ich im Quellcode nur die Aussagen vorfinden, die sich aus dem
Code selbst nicht ablesen lassen, damit ich beim Lesen einer Datei die Sache erfasse statt ihrer
Entstehungsgeschichte — und damit dieser Zustand nach dem Aufräumen erhalten bleibt.

## Akzeptanzkriterien

- [ ] Die Doku-Ballast-Regel ist auf den gesamten Produktivcode angewendet, im Umfang der beiden
      Aufnahmemengen A und B. Der Frontend-Bereich, den die erste Verdichtung ausgelassen hat,
      ist einbezogen.
- [ ] Verweise auf Specs, Entscheidungen, Pull Requests und Issues stehen nicht mehr als reine
      Begründung in Code-Kommentaren. Ein Verweis bleibt, wo er funktional nötig ist — wo also die
      verwiesene Stelle gelesen oder gepflegt werden muss, um die Aufgabe zu erfüllen.
- [ ] Eine dokumentierte Zusicherung, Invariante oder bewusste Abweichung nennt die geltende
      Regel, nicht ihre Herleitung (ADR 0086, Drei-Teile-Test): Abwägungstext,
      Alternativendiskussion und „wie kam es dazu" entfallen, die Aussage selbst bleibt
      vollständig.
- [ ] Erzwingt ein Test eine Zusicherung, nennt der Kommentar sie in einem Satz und benennt den
      Testknoten in der Adressform seines Läufers
      (`tests/test_x.py::TestY::test_z`). Der Verweis ist vor dem Streichen ausgeführt worden und
      hat genau diesen Knoten grün selektiert. Selektiert er nichts, bleibt die Zusicherung in
      voller Aussage stehen. Ein solcher Testverweis ist kein belegender Verweis und fällt nicht
      unter den Verweis-Schnitt.
- [ ] Die engere Fassung des Schutzes ist als ADR 0086 festgehalten und in `CLAUDE.md`
      übernommen, bevor auf ihrer Grundlage gekürzt wird.
- [ ] Punkt 2 des Prüfkatalogs in `.claude/skills/review-tests/SKILL.md` nennt Doku-Blöcke im Code
      als Prüfgegenstand, den Drei-Teile-Test als Schutzmaßstab und die fünf Inhaltsklassen als
      Befundvokabular. Ein Befund nennt Datei, Zeile und Inhaltsklasse; kein Befund nennt eine
      Länge oder einen Prozentwert.
- [ ] Kein PR-Body, kein Commit-Body und kein Spec-Abschnitt nennt einen Reduktions-Zielwert. Die
      Vorher/Nachher-Zahlen je Datei sind Messung, keine Zielgröße.
- [ ] Je PR gilt gegenüber `origin/main`: (a) der Diff enthält keine Zeile unter
      `backend/tests/`, `scripts/tests/`, `frontend/src/**/*.test.ts(x)`,
      `frontend/penpot/payload.test.ts`, `e2e/`; (b) die Menge der Testknoten und ihr jeweiliger
      Ausgang sind vorher und nachher identisch — Gleichheit, nicht Grün; (c) die `Stmts`-Spalte
      des Backend-Coverage-Berichts ist je Datei unverändert, und `Cover` sinkt an keiner Datei.
      Für `frontend/` entfällt (c) mangels Coverage-Konfiguration. `scripts/check.sh` läuft sauber
      durch.
- [ ] Der PR-Body trägt je geänderter Datei genau eine Zeile: Pfad → entfernte Inhaltsklasse(n) →
      Doku-Zeilen vorher/nachher. Jede genannte Klasse stammt aus der geschlossenen Menge
      {Abwägung, Vorfall, Messung, Wiederholung, belegender Verweis}. Bei einem entfernten Verweis
      nennt die Zeile, wo der Inhalt weiterhin steht. Als Doku-Zeile zählt eine nicht-leere Zeile,
      die vollständig innerhalb eines Kommentars oder Docstrings liegt; beide Messungen laufen
      über denselben Messweg.

## Datenmodell-Bezug

Nicht relevant. Es werden ausschließlich Kommentartexte und Docstrings geändert; keine Entität,
kein Feld, keine Migration.

## Architektur / Umsetzung

Gewählter Ansatz und die Festlegungen dahinter: ADR
[`0086`](../decisions/0086-schutz-gilt-der-aussage-nicht-der-herleitung.md). Sie löst ADR
[`0079`](../decisions/0079-doku-ballast-eine-regel-an-einer-stelle-richtwerte-statt-gate.md) in
zwei benannten Punkten teilweise ab; deren Abschnitte 3 bis 7 gelten unverändert weiter.

### Ist-Stand, gemessen am 11.09.2026

159 Nicht-Test-Quelldateien, 24.834 nicht-leere Zeilen, davon **8.671 Doku-Zeilen (34,9 %)** und
rund **500 Verweiszeilen** in Doku-Blöcken. **110 der 159 Dateien** liegen über dem Richtwert von
25 %.

| Bereich | Dateien | Doku-Zeilen | Anteil | über 25 % |
|---|---|---|---|---|
| `backend/src` | 38 | 4.874 | 39,2 % | 28 |
| `backend/alembic` | 23 | 485 | 36,8 % | 17 |
| `frontend/src` | 95 | 3.093 | 29,7 % | 62 |
| `frontend/penpot` | 2 | 141 | 38,5 % | 2 |
| `scripts` | 1 | 78 | 25,7 % | 1 |

Zwei Abweichungen von den Zahlen im Issue: Die dort genannten „76 von 176" Dateien zählen
Testdateien mit, die diese Story ausschließt — ohne sie sind es 62 von 95. Und das Backend liegt
bei 39,2 % **nach** der abgeschlossenen Verdichtung; der Befund gilt dort ebenso, nicht nur im nie
erreichten Frontend. Der Verweis-Bestand ist fast vollständig begründend, nicht funktional.

### Was geändert wird

| Datei | Änderung |
|---|---|
| `specs/decisions/0086-*.md` | liegt vor |
| `specs/decisions/0079-*.md` | Kopfzeile `**Teilweise abgelöst:**` — liegt vor |
| `specs/architecture/0003-securitykonzept.md` | Ankerliste Auflage → Codestelle → Test — liegt vor |
| `specs/architecture/0002-testkonzept.md` | ein Abschnitt „Nachweis ohne Rot-Grün", rund 15 Zeilen |
| `CLAUDE.md`, Punkt „Doku-Ballast" | Schutzsatz durch ADR 0086 Abschnitt 1 ersetzen; den Gate-Satz in Länge (unverändert absolut) und Inhalt (Kriterium in `review-tests`) trennen |
| `.claude/skills/review-tests/SKILL.md` | Prüfkatalog Punkt 2 bekommt das Inhalts-Kriterium |

Kein `docs/`-Update: Weder Systemarchitektur noch Datenmodell noch lokales Setup ändern sich.
Kein neuer Skill, kein CI-Job, kein Wächtertest, keine neue Datei im Repository.

### Die wiederkehrende Prüfung

Genau ein Ort: `.claude/skills/review-tests/SKILL.md`. Der Skill trägt das Kriterium heute schon —
aber nur für Skill-/Agenten-Dateien und nur im Abschnitt „Statischer Konsistenz-Check". Es wird auf
Doku-Blöcke im Code ausgeweitet und läuft damit bei jedem Diff mit einer Code-Datei. Ein Befund
nennt Inhaltsklasse und Zeile, nie eine Länge.

Der heutige Satz in `CLAUDE.md` („kein CI-Check und kein `review-*`-Kriterium") bezieht sich auf
die **Richtwerte**; die Inhaltsregel ist davon nicht berührt. Er wird trotzdem umformuliert, weil
seine heutige Fassung sonst gegen das neue Kriterium gelesen werden kann.

### Zuschnitt: fünf Pull Requests

Zwei geschlossene Aufnahmemengen begrenzen die Arbeit; alles darunter ist nicht Gegenstand, und
eine Datei ohne Ballast bleibt unverändert:

- **A — Verweis-Schnitt:** Datei mit ≥ 1 Verweiszeile im Doku-Block → rund 120 Dateien. Maßgeblich
  ist die Aufnahmeregel, nicht die Zahl.
- **B — Doku-Blöcke:** Doku-Anteil ≥ 35 % **und** ≥ 60 nicht-leere Zeilen → 44 Dateien,
  5.548 Doku-Zeilen (23 Backend / 4.163, 21 Frontend / 1.385).

1. **PR 1 — Die Regel.** Spec, ADR 0086, ADR-0079-Kopfzeile, Sicherheitskonzept, Testkonzept,
   `CLAUDE.md`, `review-tests/SKILL.md`. Keine Code-Datei, kein Verhalten.
2. **PR 2 — Der Verweis-Schnitt** (Menge A), Backend und Frontend zusammen. Mechanisch auffindbar,
   je Fundstelle eine Entscheidung: funktional nötig → bleibt; nur belegend → fällt.
3. **PR 3 — Doku-Blöcke Frontend** (Menge B, `frontend/`), 21 Dateien / 1.385 Zeilen. Absteigend
   nach Doku-Masse, angeführt von `api/types.ts` (215/486), `components/ProjectNav.tsx` (101/232),
   `components/ui/button.tsx` (82/176).
4. **PR 4 — Doku-Blöcke Backend ohne die beiden Ausreißer**, 17 Dateien. Absteigend nach
   Doku-Masse: `models.py` (338/626), `api/projects.py` (319/887), `cloud_vision.py` (311/563),
   dann der Rest.
5. **PR 5 — `worker.py` (921/2535) und `api/photos.py` (497/1301)**, zusammen 1.421 Doku-Zeilen.

Reihenfolge innerhalb eines PR: erst der mechanische Schnitt, dann der inhaltliche. Messung als
Wegwerf-Auswertung, nicht als eingechecktes Skript.

### Nachvollziehbarkeit je Datei

Der PR-Body trägt eine Zeile je geänderter Datei (Form siehe Akzeptanzkriterien). Commits werden
je Bereich und Inhaltsklasse geschnitten (z. B. „Verweise aus `backend/src/photosort/` entfernt"),
der Commit-Body nennt Klasse und was erhalten blieb. Keine Datei im Repository hält das fest — die
bestünde aus dem, was die Regel verbietet.

### Fallen, die still brechen

- **Funktionstragende Kommentare — fünf Fundstellen, vollständig gemessen.** Sie sehen aus wie
  Doku und sind Code: `backend/src/photosort/category_diff.py:310` und
  `backend/src/photosort/demo_state.py:1059` (`# pragma: no cover`),
  `backend/src/photosort/api/photos.py:428` (`# type: ignore[arg-type]`, der nachgestellte
  Erklärtext ist streichbar, das `# type: ignore` nicht),
  `frontend/src/components/StepMarker.tsx:45` und `:75` (`// prettier-ignore`).
- **`CLAUDE.md`:** Keine neue Zeile darf mit einem der sieben Marker aus
  `scripts/tests/test_werkzeugwahl_verankert.py` beginnen (`**Vorgabe:**`, `**Grund:**`,
  `**Shell ist die bessere Wahl bei:**`, `**Bündelung:**`, `**Vorrang:**`,
  `**Hintergrund-Läufe:**`, `**Unberührt:**`). Die Zeile `- **Commits:** …` bleibt unangetastet
  (`test_pr_titel_pruefung.py` leitet daraus die zehn Typen ab).
- **`frontend/src/designSystem.contract.test.ts`:** Die Freigabeliste trifft über
  `file` + `snippet`-Teilzeichenkette, nicht über Zeilennummern — eine Kommentarlöschung verwaist
  also keinen Eintrag. Die eine Ausnahme: `stripComments` entfernt `//`-Kommentare nur am
  Zeilenanfang. Vor dem Entfernen eines **nachgestellten** Kommentars in einer `.tsx` gegen die
  `*_ALLOWLIST`-Snippets abgleichen, sonst entsteht eine verwaiste Freigabe = Fehlschlag.
- **`e2e/tests/toolchain.spec.ts`** bindet `^CONFIRM_LITERAL = "…"$` und
  `^DEMO_PROJECT_PREFIX = "…"$` in `backend/src/photosort/demo_state.py` sowie
  `^const TOKEN_STORAGE_KEY = '…'$` in `frontend/src/auth/token.ts`, dazu ein unverankertes
  `toContain`. In PR 3/4 bleibt in diesen beiden Dateien jede Zeile unangetastet, die eine dieser
  drei Konstanten trägt.
- **`backend/tests/test_categories.py`** prüft die **Abwesenheit** von
  `SECONDARY_CATEGORY_MIN_CONFIDENCE` in `config.py`, `.env.example` und jedem Modul unter `api/`.
  Kein erklärender Kommentar darf diesen Namen dort neu einführen.
- Vor dem Verdichten einer Datei prüfen, wer sie als *Text* liest:
  `grep -rn "getsource\|read_text\|readFileSync\|repoFile" backend/tests scripts/tests e2e frontend/src`
- **Python:** Ein Körper, der nur aus seinem Docstring besteht, behält ihn (`SyntaxError`). Die
  Docstrings der 11 beschriebenen FastAPI-Routen sind deren OpenAPI-`description`; ihre erste
  Zeile bleibt.
- **Keine bestehende Testdatei anfassen, keine Testkonfiguration ändern.** Eine angepasste
  Erwartung ist ein Finding, keine Lösung — und ein Halt, der an den Aufrufer zurückgeht.

## UI/UX

Nicht relevant. Im Frontend ändern sich ausschließlich Kommentartexte; kein Renderpfad, kein
Zustand, keine Eingabe, keine dargestellten Daten. Die Story schließt jede Verhaltensänderung
ausdrücklich aus.

## Security

**Sicherheitsrelevant — ja, mit einem anderen Schadensmodell als sonst.** Die Story ändert kein
Verhalten, öffnet keine Angriffsfläche und fasst keinen Kontrollpfad an. Sie ändert, was ein
künftiger Entwickler an einer durchsetzenden Codestelle vorfindet. 91 Dateien unter `backend/src`
und `frontend/src` tragen sicherheitsbezogene Kommentare; an mehreren steht die Auflage samt dem
Angriff, gegen den sie gerichtet ist, in denselben Zeilen wie der zu schneidende Verweis. Der
Schaden tritt beim nächsten Refactoring ein: Wer nicht weiß, dass `algorithms=[ALGORITHM]` dem
`alg: none`-Angriff gilt, nimmt den Parameter wieder heraus. Das ist eine Regression bestehender
Kontrollen, prüfbar am Diff.

### Vier Regeln für den Schnitt an sicherheitsrelevanten Stellen

Zusätzlich zu ADR 0086, nur für Doku-Blöcke, die eine Sicherheitsauflage tragen.

**S1 — Das Angriffsmodell ist Teil von *wofür*, nicht Herleitung.** Der Angriff, gegen den eine
Auflage gerichtet ist, bleibt mit Namen stehen (Algorithm Confusion/`alg: none`, Broken
Object-Level Authorization, User-Enumeration, JWT-Fälschung bei bekanntem Secret,
Cross-Origin-Zugriff, Credential-Stuffing), nicht paraphrasiert zu „aus Sicherheitsgründen". Was
fällt: der Spec-/ADR-Pfad, der belegt, dass es die Regel gibt.

**S2 — Die untersagte Alternative bleibt, die Abwägung fällt.** `algorithms=[ALGORITHM]` ist ohne
„nie weglassen oder aus dem Token-Header übernehmen" nur eine Zeile Code; `allow_credentials=False`
ohne „Token geht über den Authorization-Header, nie über Cookies" nur ein Default, den man beim
nächsten Cookie-Bedarf umlegt. Erhalten bleibt genau die **eine** untersagte Variante als Halbsatz.
Mehrere Varianten, Aufwandsabwägung und Historie fallen.

**S3 — Ein Test ersetzt die Zusicherung nur, wenn sein Bruch die Verletzung ist.** Der Nachweis ist
nicht „es gibt einen Test mit passendem Namen", sondern der lokale Versuch: den Schutz entfernen,
die Suite laufen lassen, prüfen, ob genau dieser Test rot wird, Änderung verwerfen. Fällt kein
Test, bleibt die Aussage vollständig stehen — `frontend/src/auth/jwt.ts` ist der Fall dazu.

**S4 — Wo der Verweis fällt, tritt der erzwingende Test an seine Stelle.** An Stellen mit
Sicherheitsauflage wird `siehe specs/…` nicht ersatzlos gestrichen, sondern durch den Namen des
erzwingenden Tests ersetzt. Der Testname wird vor dem Eintragen am Bestand geprüft — ein Verweis
ins Leere löscht die Aussage ersatzlos.

Die Zuordnung Auflage → Codestelle → erzwingender Test steht in
`specs/architecture/0003-securitykonzept.md`, Abschnitt „Ankerliste". Sie deckt `security.py`,
`main.py`, `api/auth.py`, `api/ratings.py`, `api/deps.py`, `rate_limit.py`, `config.py` und
`frontend/src/auth/jwt.ts` ab. Wer eine dieser Stellen verschiebt, umbenennt oder ihren Schutz
entfernt, zieht die Liste im selben Pull Request nach.

`review-security` ist an dieser Story zu triggern, obwohl kein Verhalten geändert wird. Prüffrage
ist nicht „ist der Code noch sicher", sondern, ob je geschnittener Stelle S1 bis S4 eingehalten
sind.

## Teststrategie

Die Story schreibt keinen Produktivcode; der Rot-Grün-Zyklus läuft ins Leere. An seine Stelle tritt
ein **Vorher-Nachher-Gleichheitsnachweis** auf demselben Commit-Paar (`origin/main` →
Branch-Spitze), je PR einmal, mit den drei Größen (a), (b), (c) aus den Akzeptanzkriterien.

Suiten in dieser Reihenfolge: `scripts/` (`pytest -q --tb=no -rA`, nur PR 1 — PR 1 ändert genau
deren Prüfgegenstand), `backend/` (`pytest -q --tb=no -rA --cov=photosort --cov-report=term-missing`,
aus dem Worktree mit `PYTHONPATH=<worktree>/backend/src`), `frontend/`
(`npm run test -- --run --reporter=verbose`), `e2e/` nur im CI-Job.

Der Vergleich auf Ausgangs-**Gleichheit** statt auf Grün ist tragend: Im Worktree scheitern zwei
Fälle in `test_label_embedding.py` mangels `label_embedder.onnx`. Als Gleichheitsgröße sind sie
unschädlich, als Grün-Bedingung wären sie ein Dauerhindernis.

**Warum (c) trägt:** Docstrings und Kommentare sind keine Statements — unter reiner
Dokumentationsentfernung ist die `Stmts`-Spalte exakt invariant, nicht nur ungefähr. Sie fängt
genau drei Unfälle: versehentlich mitgelöschte Codezeile (`Stmts` sinkt), entferntes
`# pragma: no cover` (`Miss` steigt, `Cover` fällt), Körper aus nur einem Docstring
(`SyntaxError`, laut). Bezugswert: `TOTAL 4236`. Das Frontend hat keine Coverage-Konfiguration und
ist auf (a) und (b) angewiesen.

**(d) Die Prüfer sind Teil des Nachweises:** `scripts/check.sh` deckt sie ab. `ruff format --check`
reagiert auf Kommentarposition und Leerzeilen; `E501` (ab 111 Zeichen) ist der einzige Wächter
gegen einen beim Verdichten zu lang geratenen Satz; `mypy --strict` fängt ein verlorenes
`# type: ignore`; `npm run format:check` ein verlorenes `// prettier-ignore`. Ruff hat keine
`D`-Regeln aktiv — eine entfernte Docstring fällt dort **nicht** auf.

Kein neuer Test und kein Wächtertest. 148 von 152 Produktivdateien werden in mindestens einer
Testdatei namentlich geführt; die vier Ausnahmen liegen unter Aufnahmekriterium B und sind nicht
Gegenstand. `specs/architecture/0002-testkonzept.md` bekommt einen Abschnitt „Nachweis ohne
Rot-Grün" (rund 15 Zeilen), weil das Muster künftig für jede per Zusicherung verhaltensneutrale
Änderung gilt — ohne die Messzahlen dieser Story und ohne Verweis auf sie.

## Entscheidungen

- Neue ADR 0086 statt Änderung von 0079, und kein volles `Superseded`: Von 0079 fallen nur
  Abschnitt 1 (Spiegelstrich „das Geschützte") und die Inhaltshälfte von Abschnitt 2.
- Der engere Schutz ist ein Drei-Teile-Test, kein Vokabular: geschützt sind *was gilt*, *wofür*,
  *was bei Verletzung passiert*.
- Die wiederkehrende Prüfung sitzt an genau einem Ort (`review-tests`). Verworfen: ein Prüfpunkt in
  `developer.md` (die eigene Herleitung wirkt ihrem Autor stets nötig), ein neuer `review-*`-Skill,
  ein Wächtertest für Verweise (bräuchte eine wachsende Ausnahmeliste).
- Keine Ausnahme für Sicherheitskommentare, sondern vier Anwendungsregeln S1–S4 innerhalb von
  ADR 0086; die ADR hat dafür eine Präzisierung in Abschnitt 1 erhalten.
- Ein Testverweis ist kein belegender Verweis und wird von PR 2 nicht geschnitten — sonst löscht
  PR 2 mechanisch die Verweisform, die PR 3/4/5 setzen sollen.
- Fünf statt vier PRs: `worker.py` und `api/photos.py` (zusammen 1.421 Doku-Zeilen) bekommen einen
  eigenen PR, weil dort ein irrtümlich gelöschter Invariantensatz am teuersten wäre und das Review
  die einzige Stelle ist, die ihn fängt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Im Frontend ändern sich ausschließlich
  Kommentartexte — kein Renderpfad, kein Zustand, keine Eingabe, keine dargestellten Daten.

## Offene Fragen

Keine.

## Out of Scope

- Das nachträgliche Kürzen abgeschlossener Feature-Specs.
- Eine Verdichtung von Testdateien: dort trägt ein Kommentar meist das Szenario, das der Testname
  nicht fasst.
- Eine Zielgröße für eine prozentuale Reduktion.
- Der Umfang von `specs/architecture/0002-testkonzept.md` selbst (1.737 Zeilen, weit über dem
  Richtwert) — eigene Story.
