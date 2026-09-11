# 0397 - Dokumentationsumfang bleibt pflegbar

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** [Issue #397](https://github.com/TheRealKoller/photosort/issues/397)
**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Abschnitte „Security" und
„Teststrategie" Auflagen tragen, deren Wegfall an den betroffenen Stellen still bricht —
sie zu kürzen träfe genau das, was das dritte Akzeptanzkriterium schützt.

## Ziel

Die Dokumentation wächst schneller als ihre Pflegbarkeit — messbar nicht als Gesamtmasse, sondern
als Trend im Umfang **neu entstehender** Dokumente: Der Median einer Feature-Spec ist von 205
Zeilen (Specs 0251–0320) auf 556 gestiegen (0321–0399), der eines ADR von 55 über 99 auf 136. Im
Python-Code stehen 11.880 Zeilen Docstrings und Kommentare; einzelne Dateien bestehen zu über
55 % daraus.

Die Gesamtmasse ist dabei nicht das Problem: 98 der 106 Feature-Specs sind abgeschlossen und
werden nie wieder angefasst. Dieses Archiv kostet keine Pflege und ist nicht Gegenstand. Last
erzeugen rund 15.350 Zeilen lebender Dokumentation plus die Doku-Blöcke im Code. Darin lässt sich
der Ballast benennen, statt ihn zu schätzen: historische Begründung, Verweise, die nur begründen,
Wiederholung der Versionsgeschichte, Wiederholung dessen, was der Code selbst zeigt. Bleiben muss
alles, was nirgends sonst steht — Invarianten, Zusicherungen, bewusste Abweichungen. Für Skill-
und Agenten-Dateien verbietet `CLAUDE.md` genau diese Ballast-Klasse bereits; die Regel gilt
bislang nur dort.

## User Story

Als Entwickler und Stakeholder von PhotoSort möchte ich, dass Dokumentation nur das enthält, was
nirgends sonst steht, und dass ihr Umfang beim Entstehen begrenzt wird, damit sie gelesen,
aktuell gehalten und widerspruchsfrei gehalten werden kann, statt durch ihre Menge unbrauchbar zu
werden.

## Akzeptanzkriterien

- [ ] Eine verbindliche Regel an genau einer Stelle benennt, was nicht in ein Dokument oder einen
      Doku-Block gehört: historische Begründung, Verweise, die nur begründen, Wiederholung der
      Versionsgeschichte, Wiederholung dessen, was der Code selbst zeigt.
- [ ] Sie gilt ausdrücklich für alle fünf Orte: Feature-Specs, ADRs, Skill- und Agenten-Dateien,
      Setup-/Architektur-Dokumentation, Doku-Blöcke im Code.
- [ ] Sie benennt ebenso ausdrücklich das Geschützte: Invarianten, Zusicherungen und bewusste
      Abweichungen, die nicht aus dem Code ablesbar sind. Ein Kürzen darf diese nicht treffen.
      **Objektiv prüfbar** über ein geschlossenes Vokabular: Entfernt ein Diff-Hunk eine Zeile mit
      `muss`, `darf nicht`, `nie`, `immer`, `Invariante`, `Zusicherung`, `bewusst`, `absichtlich`,
      `sonst`, `Grund:` oder einer ADR-Nummer als Beleg, trägt der PR-Text für genau diese Stelle
      eine Begründung. Jede unbegründete Trefferzeile ist ein Finding.
- [ ] Je Doku-Art gibt es einen Umfangs-Richtwert, orientiert am Stand, als die Dokumentation noch
      pflegbar war (Feature-Specs rund 200, ADRs rund 100 Zeilen).
- [ ] Der Richtwert ist keine harte Grenze: Überschreitung zulässig, wenn im Dokument selbst
      begründet. Es entsteht kein Prüfschritt, der eine Änderung allein wegen ihrer Länge
      zurückweist — prüfbar als Abwesenheit: Der Diff fügt weder unter `.github/workflows/` noch
      in `.claude/skills/review-*/` eine Längenprüfung hinzu.
- [ ] Beim Entstehen einer neuen Spec oder eines neuen ADR wird gegen den Richtwert geprüft, bevor
      das Dokument abgeschlossen wird. Ergebnis ist ein kürzeres Dokument oder ein Satz Begründung
      **im Dokument**, nie eine Zurückweisung.
- [ ] Die lebende Dokumentation ist einmalig verdichtet: Skill- und Agenten-Dateien, ADRs,
      Setup-/Architektur-Dokumentation und die noch offenen Specs.
- [ ] Die Doku-Blöcke im Code sind dort verdichtet, wo sie nachweislich Ballast tragen, beginnend
      bei den Dateien mit dem höchsten Doku-Anteil.
- [ ] Abgeschlossene Feature-Specs werden nicht angefasst. Das Archiv bleibt, wie es ist.
- [ ] Nachvollziehbar ist, welche Art von Inhalt entfernt wurde: Der PR-Text nennt je geänderter
      Datei die entfernte Inhaltsart aus dem geschlossenen Vokabular der Regel und — bei einem
      nur-begründenden Verweis — wo der Inhalt weiterhin steht (ADR-Nummer, Commit, Codestelle).
- [ ] Die Regel erzeugt keine neue eigenständige Dokumentationsdatei.
- [ ] Beide PRs ändern **keine** Testdatei und keine Testkonfiguration; alle CI-Jobs bleiben grün.
      Eine Teständerung ist ein Finding, keine Anpassung.

## Datenmodell-Bezug

Nicht relevant. Es entstehen und ändern sich keine Entitäten; `docs/architecture.md` wird nur als
Gegenstand der Verdichtung angefasst, nicht wegen einer Modelländerung.

## Architektur / Umsetzung

Gewählter Ansatz und die Festlegungen dahinter: ADR
[`0077`](../decisions/0077-doku-ballast-eine-regel-an-einer-stelle-richtwerte-statt-gate.md).

### Die Regel

Der bestehende Konventions-Punkt **Skills/Agents** in `CLAUDE.md` wird durch einen allgemeinen
Punkt **ersetzt** und geht darin auf — er ist inhaltlich schon heute ein Spezialfall („Verweise,
die nur begründen"). Kein zweiter Punkt daneben, keine neue Datei. Der neue Punkt nennt die vier
verbotenen Klassen, die drei geschützten Klassen, die bestehende Ausnahme für funktional nötige
Verweise wortgetreu, die Geltung für alle fünf Orte, und dass abgeschlossene Feature-Specs
(`Implemented`/`Superseded`) nicht nachträglich gekürzt werden. Der Abschnitt „Doku-Pflege" bleibt
unberührt und bekommt keinen Querverweis — er regelt, *wann* aktualisiert wird, nicht, *was*
drinsteht.

### Richtwerte

| Doku-Art | Richtwert |
|---|---|
| Feature-Spec | ~200 Zeilen |
| ADR | ~100 Zeilen |
| Skill-/Agenten-Datei | ~120 Zeilen |
| Lebendes Konzept-/Übersichtsdokument (`docs/`, `specs/architecture/`) | ~300 Zeilen |
| Doku-Block einer Quellcode-Datei | ~25 % ihrer Zeilen |

Gezählt wird in **Zeilen zu höchstens 100 Zeichen**, also `Zeichenzahl ÷ 100`, wo eine Datei
diesem Umbruch nicht folgt. Ohne diesen Zusatz misst der Richtwert das Falsche:
`docs/architecture.md` trägt 54 Zeilen zu je 2.210 Zeichen, das Securitykonzept 931 Zeilen, von
denen eine einzige 92 KB groß ist — beide erfüllten einen reinen Zeilen-Richtwert mühelos.

### Verankerung beim Schreiben

Zwei Anker, beide verweisen auf den Konventions-Punkt, statt die Regel zu wiederholen:
`.claude/skills/spec-writer/SKILL.md` (Schritt 4, vor dem Spec-Commit) und
`.claude/agents/architect.md` (Aufgabe 1, bevor eine ADR abgeschlossen wird). `specs/TEMPLATE.md`
wird **nicht** angefasst: ein Hinweis dort würde als Textbaustein in jede neue Spec kopiert.
`specs/README.md` bekommt einen Satz zur Reichweite der ADR-Unveränderlichkeit (ADR 0077,
Abschnitt 4).

### Einmalige Verdichtung, lebende Doku — größter Hebel zuerst

1. `specs/architecture/`: `0003-securitykonzept.md` (931 Zeilen / 629 KB),
   `0002-testkonzept.md` (1642), `0004-design-system.md` (480), `0005-board-*.md` (224)
2. Die **27 Accepted-ADRs über 100 Zeilen** (zusammen 4.544 Zeilen). Nur „Kontext", „Begründung",
   „Konsequenzen"; „Entscheidung" und Statuszeile bleiben wortgetreu. `Superseded` ist Archiv.
3. `docs/setup.md` (482), `docs/ai-workflow.md` (239), `docs/architecture.md` (54 / 119 KB)
4. Skill-/Agenten-Dateien über 120 Zeilen: `design-system` (229), `ship-feature` (175),
   `agents/developer.md` (169), `penpot-design` (167), `refinement` (164),
   `penpot-entwurfsrunden` (142). `github-access` (774) wird **nicht gekürzt**, sondern trägt eine
   begründete Überschreitung — ein Operationskatalog ist Inhalt, der nirgends sonst steht.
5. Übrige Skills und Agenten sowie die 5 offenen Specs (`0049`, `0058`, `0065`, `0262`, `0302`,
   alle bereits unter 200 Zeilen): nur Ballast-Klassen entfernen, kein Kürzungsdruck.

### Einmalige Verdichtung, Doku-Blöcke im Code

Die Dateiliste wird nicht aufgezählt, sondern **gemessen** — sonst stünde hier, was ein Befehl
ohne Pflegeaufwand liefert. Aufnahmekriterium: **(a)** Quelldatei (keine Testdatei) mit ≥ 150
Zeilen und Doku-Anteil ≥ 40 %, **(b)** plus die drei Quelldateien mit der größten absoluten
Doku-Masse, die (a) verfehlen. Das ergibt heute 17 Dateien mit zusammen 4.733 Doku-Zeilen,
angeführt von `pricing.py` (64,5 %), `config.py` (61,8 %) und `models.py` (55,7 %); die drei
Masse-Dateien sind `worker.py`, `api/photos.py` und `api/projects.py`. Reihenfolge: absteigend
nach Anteil, die drei Masse-Dateien zuletzt.

**Testdateien bleiben außen vor** — dort trägt ein Kommentar meist das Szenario, das der Testname
nicht fasst. Erster, mechanischer Schnitt in jeder Datei: die 1.561 Spec-/ADR-/PR-/Issue-Verweise
in Kommentaren und Docstrings. Danach erst inhaltlich.

### Nachvollziehbarkeit und Zuschnitt

Keine neue Datei: Jeder Verdichtungs-Commit nennt im Body die entfernte Ballast-Klasse und was
erhalten blieb; der PR-Body trägt eine Tabelle (Doku-Art → entfernte Klassen → Zeilen
vorher/nachher). Es sind **zwei PRs** — PR 1 trägt Spec, ADR 0077, den Konventions-Punkt, die
beiden Anker und die lebende Doku (reines Markdown), PR 2 die Doku-Blöcke der Quellcode-Dateien.
Verhältnis zu ADR [`0045`](../decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md):
ADR 0077, Abschnitt 7.

## UI/UX

**Nicht relevant.** Es ändert sich kein gerendertes Pixel, keine JSX-Struktur, kein Klassenname,
keine Prop — in den Frontend-Dateien der Liste fallen ausschließlich Kommentarzeilen.

Eine Auflage bleibt: Die Kommentare in `ui/button.tsx`, `RatingButtons.tsx` und `ProjectNav.tsx`
tragen **gemessene Kontrastwerte, Trefferflächenregeln und eine Kollisionsregel** (gefülltes
`--danger` mit Radius 6 px ist formgleich mit dem „Aussortiert"-Kennzeichen, deshalb darf ein
`destructive`-Button nicht auf Seiten stehen, die Bewertungs-Kennzeichen zeigen). Das sind
Zusicherungen im Sinne der Regel und bleiben in ihrer Aussage stehen. Sie sind durch keinen Test
gedeckt: `designSystem.contract.test.ts` bindet die *Klassenzeile*, nicht ihre Begründung — das
zugesagte Verhalten überlebt eine Kürzung also, sein Warum nicht.

## Security

**Das Feature selbst ist nicht sicherheitsrelevant.** Keine Auth-Logik, keine Schnittstelle, kein
Datenmodell, keine Berechtigung, keine veränderte Sichtbarkeit zwischen den beiden Nutzern, keine
neue Eingabe von außen, kein Secret. Der Diff besteht aus Prosa.

**Sicherheitsrelevant ist die Tätigkeit.** Das Verdichten ist eine gezielte Löschaktion in genau
den zwei Artefaktklassen, in denen PhotoSort seine Sicherheitszusicherungen ablegt: dem
Securitykonzept und sicherheitsbegründenden Codekommentaren. Eine gelöschte Zeile kann dort die
einzige Stelle sein, an der eine Auflage steht — der Code führt sie aus, sagt aber nicht, dass er
sie einhalten *muss*. Vier Muss-Kriterien:

- **Überschriften, auf die von außen gezeigt wird, bleiben wortgleich.**
  `.claude/skills/review-security/SKILL.md` verlangt die Konsultation benannter Abschnitte;
  `opencloud/exif.py`, `worker.py`, `api/photos.py`, `backend/tests/test_exif.py` und
  `scripts/seed-opencloud-demo.py` zitieren „Standortdaten (GPS aus EXIF)" bzw.
  „Docker-Compose-Netzwerk" namentlich. Umbenennen oder Zusammenlegen bricht sie **still**.
  Nummerierte Listen werden nicht umnummeriert (mehrere Stellen zitieren „Punkt 4").
- **Im Wortlaut kürzbar, in der Aussage nicht:** Bedrohungsmodell samt Vertrauensgrenzen,
  Auth-Modell, Secrets-Handling, die beiden „Grundsatz, projektweit verbindlich"-Absätze der
  Robustheitsprinzipien, WebDAV-Pfad-/SSRF-Aussagen, die Cloud-Vision- und Standortdaten-Auflagen,
  jeder **offene** Eintrag unter „Restrisiken" und „Bekannte Lücken". Durchgestrichene Einträge
  dürfen fallen: ein zurückgenommenes Restrisiko ist keine bestehende Abweichung mehr.
- **Größter Hebel ohne Substanzrisiko zuerst:** der Änderungsjournal-Kopf des Securitykonzepts
  (~148 KB, 24 % der Datei, davon eine Zeile mit 92 KB) und die drei selbst als gegenstandslos
  markierten Abschnitte. Erst danach die inhaltliche Arbeit.
- **In den Code-Doku-Blöcken** bleiben die Kommentare stehen, die eine Allowlist vor einer
  Pfadoperation, eine bewusst doppelte Sanitisierung im Lesepfad, ein Pflichtprädikat gegen
  projektfremde Daten, eine bewusst unterlassene Protokollierung oder ein bewusst fehlendes Feld
  begründen. Wo eine Zusicherung nachweislich testgedeckt ist, darf der Block auf Aussage plus
  Testverweis schrumpfen; ohne nachgewiesenen Test bleibt er in voller Aussage.

## Teststrategie

**TDD läuft hier weitgehend leer.** PR 1 ändert ausschließlich Markdown und erzeugt kein
Verhalten — es gibt nichts, was rot werden könnte. Tragender Anker ist eine
Regressions-Invariante: Alle CI-Jobs bleiben grün, **ohne dass eine einzige Testdatei angefasst
wird**.

Das ist keine Formalie. **Neun bestehende Tests binden genau die Zeilen, die verdichtet werden
sollen** — darunter `e2e/tests/toolchain.spec.ts`, das drei Skill-Dateien wörtlich prüft
(Fettmarkierung inklusive), `scripts/tests/test_github_zugriff_an_einer_stelle.py`, das einen Satz
in 24 Dateien erwartet, und `backend/tests/test_config.py`, das Modell-IDs und Kostenangaben gegen
`docs/setup.md` prüft. **Ein reiner Markdown-PR kann deshalb den `backend`- und den `e2e`-Job rot
färben.** Vor dem Verdichten einer Datei wird geprüft, wer sie als *Text* liest:

```bash
grep -rn "getsource\|read_text\|readFileSync\|repoFile" backend/tests scripts/tests e2e frontend/src
```

**Ein neuer Test**, geschrieben als erster Schritt von PR 2, bevor ein Docstring fällt:
`test_dokumentierte_routen_behalten_ihre_openapi_beschreibung` — aus `app.openapi()` hat jede der
heute 11 beschriebenen Routen weiterhin eine **nicht-leere** `description`. Kein Textvergleich.
Die Docstrings dieser Routen sind die OpenAPI-Beschreibung (kein `summary=`/`description=`-
Argument existiert), ihr Wegfall wäre sonst still. Der Test startet grün; der Beleg ist eine
Mutationsprobe (einen Routen-Docstring probeweise entfernen, Rot sehen, zurücknehmen), im PR-Text
vermerkt. **Ausdrücklich kein** Snapshot von `/openapi.json`: Es gibt repoweit keinen Verbraucher,
und ein Schnappschuss pinnte genau den Text, den diese Story kürzen will — faktisch eine
Längen-Zurückweisung, gegen das fünfte Akzeptanzkriterium.

**Edge Cases für PR 2:** Ein Körper, der nur aus seinem Docstring besteht (`worker.py`,
`CriterionScoringGuardError`), behält ihn — Entfernen ergäbe `SyntaxError`. `# type: ignore`,
`# noqa`, `# pragma: no cover` und `@ts-expect-error` sind Code, kein Doku-Block. Die erste
Docstring-Zeile jeder Route bleibt. Im Frontend wird keine `className`-Zeile umbrochen:
`designSystem.contract.test.ts` blendet Kommentare vor dem Scan aus, bindet aber Code-Zeilen
wörtlich — und eine Freigabe, deren Ausschnitt nicht mehr gefunden wird, ist selbst ein
Fehlschlag.

**Coverage ist hier kein Netz, aber auch kein Risiko:** `coverage.py` zählt weder Kommentare noch
Docstrings als Statements — Zähler und Nenner bleiben unverändert. `ruff` hat keine `D`-Regeln
aktiviert; ein Docstring-Verlust bricht den Lint nicht. `specs/architecture/0002-testkonzept.md`
bekommt genau einen kurzen Abschnitt (Muster „Änderung, die nur Nicht-Code-Zeilen entfernt").

## Offene Fragen

Keine. Die beiden Punkte, die über eine technische Detailfrage hinausgingen — die Reichweite der
ADR-Unveränderlichkeit und der PR-Zuschnitt — sind entschieden und stehen als ADR 0077,
Abschnitt 4 und 7.

## Out of Scope

- Eine Reduktion um einen festen Prozentsatz. Eine solche Zielzahl lädt dazu ein, Zeilen
  umzuschichten statt Inhalt wegzulassen.
- Das Ausdünnen oder Auslagern abgeschlossener Feature-Specs.
- Die Anzahl der Rückfragen während einer Session.
- Das Rückgängigmachen der bewussten Aufteilung in fünf getrennte Review-Perspektiven.
