# 0079 - Doku-Ballast: eine Regel an einer Stelle, Richtwerte statt Gate

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** GitHub-Issue [`#397`](https://github.com/TheRealKoller/photosort/issues/397), Spec `specs/features/0397-*.md`
**Umfang:** über dem Richtwert von rund 100 Zeilen, weil diese ADR den Regeltext für fünf Orte,
die Richtwert-Tabelle und den Zuschnitt der einmaligen Verdichtung zugleich trägt.

## Kontext

`CLAUDE.md` verbietet eine benennbare Klasse von Doku-Ballast bereits — aber nur für Skill- und
Agenten-Dateien. Feature-Specs, ADRs, `docs/`, `specs/architecture/` und die Doku-Blöcke im Code
unterliegen ihr nicht. Gemessen: 10.669 Doku-Zeilen in 130 Python-Dateien (einzelne Quelldateien
über 55%), 1.561 Spec-/ADR-/PR-Verweise in Code-Kommentaren, 565 weitere in den drei
Konzeptdokumenten unter `specs/architecture/`.

Zwei Randbedingungen bestimmen die Lösung: eine zweite Regelstelle würde von der ersten
wegdriften, und ein Prüfschritt, der Änderungen wegen ihrer Länge zurückweist, erzeugt Umschichten
statt Weglassen.

## Entscheidung

### 1. Die Regel ist ein einziger Konventions-Punkt in `CLAUDE.md`

Der bestehende Punkt **Skills/Agents** unter „Konventionen" wird durch einen allgemeinen Punkt
ersetzt und geht darin auf — er ist inhaltlich ein Spezialfall („Verweise, die nur begründen").
Es entsteht keine neue Datei und kein zweiter Punkt daneben. Der Punkt benennt:

- die verbotenen Klassen: historische Begründung, Verweise auf Specs/ADRs/PRs, die nur begründen,
  Wiederholung der Versionsgeschichte, Wiederholung dessen, was der Code selbst zeigt;
- das Geschützte: Invarianten, Zusicherungen, bewusste Abweichungen, die aus dem Code nicht
  ablesbar sind — ein Kürzen darf diese nie treffen;
- die bestehende Ausnahme wortgetreu: ein Verweis bleibt erlaubt, wenn er funktional nötig ist;
- die Geltung für alle fünf Orte;
- dass abgeschlossene Feature-Specs (`Implemented`/`Superseded`) nicht nachträglich gekürzt werden.

Der Abschnitt „Doku-Pflege" bleibt unberührt — er regelt, *wann* aktualisiert wird, nicht, *was*
drinsteht. Kein Querverweis zwischen beiden, damit nichts zu synchronisieren ist.

### 2. Fünf Richtwerte, im selben Punkt, ohne jedes Gate

| Doku-Art | Richtwert |
|---|---|
| Feature-Spec | ~200 Zeilen |
| ADR | ~100 Zeilen |
| Skill-/Agenten-Datei | ~120 Zeilen |
| Lebendes Konzept-/Übersichtsdokument (`docs/`, `specs/architecture/`) | ~300 Zeilen |
| Doku-Block einer Quellcode-Datei | ~25% ihrer Zeilen |

Sie gelten für **neu entstehende** Dokumente. Überschreitung ist zulässig, wenn sie im Dokument
selbst in einem Satz begründet ist.

**Gezählt wird in Zeilen zu höchstens 100 Zeichen**, also `Zeichenzahl ÷ 100`, wo eine Datei
diesem Umbruch nicht folgt. Ohne diesen Satz misst der Richtwert das Falsche:
`docs/architecture.md` trägt 54 Zeilen zu je 2.210 Zeichen, `specs/architecture/0003-*.md` 931
Zeilen, von denen eine einzige 92 KB groß ist. Beide erfüllten einen Zeilen-Richtwert mühelos.
So ist er weder durch Umbrechen erfüllbar noch durch Zusammenziehen zu verfehlen. Es entsteht **kein** CI-Check, **kein** Test und **kein**
`review-*`-Kriterium, das eine Änderung allein wegen ihrer Länge zurückweist.

### 3. Geprüft wird an genau zwei Ankern, beim Schreiben

- `.claude/skills/spec-writer/SKILL.md`, Schritt 4, vor dem Spec-Commit.
- `.claude/agents/architect.md`, Aufgabe 1, bevor eine ADR abgeschlossen wird.

`specs/TEMPLATE.md` wird **nicht** angefasst: ein Hinweis dort würde als Textbaustein in jede neue
Spec kopiert. Beide Anker verweisen auf den Konventions-Punkt, statt die Regel zu wiederholen.

### 4. Unveränderlichkeit einer ADR schützt den Abschnitt „Entscheidung", nicht die Prosa drumherum

`specs/README.md` macht eine angenommene ADR unveränderlich. Das schützt den Entscheidungsgehalt.
Redaktionelles Verdichten von „Kontext", „Begründung" und „Konsequenzen" ändert die Entscheidung
nicht und ist deshalb keine Änderung im Sinne dieser Regel. Der Abschnitt „Entscheidung" bleibt
wortgetreu unangetastet, ebenso die Statuszeile und jeder Teil-Vermerk. ADRs mit Status
`Superseded` sind Archiv und werden nicht angefasst. `specs/README.md` bekommt dafür einen Satz —
Präzisierung der dort stehenden Lebenszyklus-Regel, keine zweite Doku-Regel.

### 5. Nachvollziehbarkeit über Commit-Bodies und eine PR-Tabelle, keine neue Datei

Jeder Verdichtungs-Commit nennt im Body die entfernte Ballast-Klasse und was erhalten blieb. Der
PR-Body trägt eine Tabelle (Doku-Art → entfernte Klassen → Zeilen vorher/nachher). Eine eigene
Datei bestünde genau aus dem, was die Regel verbietet.

### 6. Die einmalige Verdichtung ist eine abgeschlossene, gemessene Liste

Nicht „ein Prozentsatz weniger", sondern benannte Dateien mit gemessenem Ist-Stand (Liste und
Reihenfolge im Spec-Abschnitt „Architektur / Umsetzung"). Testdateien bleiben außen vor: dort trägt
ein Kommentar meist das Szenario, das der Testname nicht fasst — das ist geschützter Inhalt.

### 7. Der Zuschnitt sind zwei Pull Requests

PR 1 trägt Spec, diese ADR, den Konventions-Punkt, die beiden Anker und die lebende Doku — reines
Markdown. PR 2 trägt die Doku-Blöcke der Quellcode-Dateien. Die beiden Hälften haben
unterschiedliche Risikoklassen: in PR 2 muss jeder Testlauf unverändert grün bleiben, in PR 1
kann nichts brechen. ADR [`0045`](./0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md)
bleibt davon unberührt: Es entsteht kein reiner Spec-PR, den jene ADR verhindern will — PR 1
trägt die Regel selbst, PR 2 wendet sie an.

## Begründung

- **Ersetzen statt Danebenstellen:** zwei Punkte mit überlappendem Geltungsbereich driften; genau
  das ist der Fehlermodus, den die Story beschreibt.
- **Richtwert im selben Punkt wie das Verbot:** wer die Länge prüft, liest dabei zwangsläufig, was
  weggelassen werden soll.
- **Anker beim Schreiben statt beim Prüfen:** ein Gate würde Inhalt in Anhänge, Unterdateien und
  Commit-Bodies umschichten, ohne dass ein Satz weniger entsteht.
- **Route-Docstrings sind kein Ballast:** FastAPI macht sie zur OpenAPI-Beschreibung — sie sind
  Ausgabe, nicht Wiederholung. Kein Test hält sie fest, ihr Wegfall wäre still.

## Konsequenzen

- **`CLAUDE.md`:** der Punkt „Skills/Agents" wird ersetzt; sein Inhalt gilt weiter, nur breiter.
- **`specs/README.md`:** ein Satz zur Reichweite der ADR-Unveränderlichkeit (Abschnitt 4).
- **`.claude/skills/spec-writer/SKILL.md`, `.claude/agents/architect.md`:** je ein Prüfsatz.
- **Kein Effekt auf `.github/workflows/`, die `review-*`-Skills, `specs/TEMPLATE.md` und die
  Testsuiten** — die Verdichtung darf kein Verhalten ändern, alle bestehenden Tests bleiben
  unverändert grün.
- `.claude/skills/github-access/SKILL.md` (774 Zeilen, Operationskatalog) wird der erste Fall, der
  den Richtwert per begründeter Überschreitung trägt statt per Kürzung.
- Ein späterer Wechsel (etwa doch ein Längen-Gate, oder ein Zurücknehmen der Reichweite in
  Abschnitt 4) braucht eine neue, diese ADR als „Superseded" markierende ADR.
