# 0061 - Skills umbenennen: idea-sharpener → spec-writer, story-refiner → refinement

**Status:** Implemented (direkte Umsetzung im selben Chat-Gespräch)
**Erstellt:** 2026-08-27
**Bezug:** Chat-Gespräch mit Daniel, 2026-08-27, direkt im Anschluss an Story #230 ("Kosteneffizientere Ideen-Pipeline").

## Ziel

`idea-sharpener` erzeugt aus einer bereits fachlich geschärften Story eine technische Feature-Spec — der Name legt aber "Schärfung/Refinement" nahe, was tatsächlich der andere Skill (`story-refiner`) macht. Diese Verwechslungsgefahr soll durch treffendere Namen behoben werden. Reine Umbenennung, keine Verhaltensänderung.

## User Story

Als Daniel, der beide Skills im Chat aufruft, möchte ich, dass ihre Namen die tatsächliche Funktion widerspiegeln (Spec-Erstellung vs. fachliche Schärfung), damit ich nicht mehr rätseln muss, welcher der beiden gemeint ist.

## Akzeptanzkriterien

- [x] `.claude/skills/idea-sharpener/` → `.claude/skills/spec-writer/` (inkl. `name:`-Frontmatter, Überschrift, Selbstverweise).
- [x] `.claude/skills/story-refiner/` → `.claude/skills/refinement/` (inkl. `name:`-Frontmatter, Überschrift, Selbstverweise).
- [x] Alle aktiven, nicht-historischen Referenzen aktualisiert: sechs Agenten-Definitionsdateien (`.claude/agents/*.md`), `capture`/`github-project-sync`/`ship-feature`-Skills, `docs/ai-workflow.md`, `specs/TEMPLATE.md`, `specs/roadmap.md` (aktuelle Einträge), `specs/diagrams/workflow-overview.d2` (inkl. SVG-Neurendern).
- [x] Historische Referenzen unverändert gelassen: `specs/decisions/*.md`, `specs/features/*.md` (bereits abgeschlossene Specs), `specs/architecture/0002`–`0004` (chronologische "Letzte Aktualisierung"-Historie), `CHANGELOG.md` — dokumentieren, was zum jeweiligen Zeitpunkt tatsächlich galt.
- [x] Verifikation: `grep -rl "idea-sharpener\|story-refiner"` außerhalb der historischen Dateien liefert nur noch die bewusst als Historie stehen gelassene Herkunfts-Erwähnung ("früherer... idea-sharpener-Ablauf") in den beiden umbenannten `SKILL.md`-Dateien selbst.

## Datenmodell-Bezug

Keines — reine Prozess-/Prompt-Konfiguration.

## Architektur / Umsetzung

Reine Datei-Umbenennung (`git mv`) plus mechanische Textersetzung, keine neue Technologie/Abhängigkeit/Datenmodell — keine ADR nötig, kein `architect`/`test-engineer`/`security-engineer`-Konsultationsaufwand angemessen (identisches Muster wie bei einer reinen Namensänderung ohne Verhaltensänderung; direkt von Claude umgesetzt statt über den vollen `refinement`/`spec-writer`-Ablauf, um nicht genau den in Story #230 gerade kritisierten Overhead für eine derart triviale, unzweideutige Änderung zu erzeugen).

## UI/UX

Nicht relevant — keine PhotoSort-App-Oberfläche betroffen.

## Security

Nicht relevant — keine Berührung von Auth, Secrets, externen Schnittstellen oder Datenmodell.

## Entscheidungen

- Exakte neue Namen von Daniel direkt vorgegeben (`spec-writer`, `refinement`), keine offene Frage.
- Historische Dateien (ADRs, abgeschlossene Feature-Specs, Roadmap-"Bereits umgesetzt"-Einträge, die drei Architektur-Konzeptdokumente) bewusst nicht angefasst — sie dokumentieren, welcher Name zum jeweiligen historischen Zeitpunkt korrekt war; rückwirkendes Umschreiben würde die Nachvollziehbarkeit vergangener Entscheidungen verfälschen (konsistentes Prinzip mit dem gesamten übrigen Projekt, z.B. Statusfeld-Umbenennungen in ADR 0030/0036/0037).
- Kein voller `spec-writer`/`refinement`-Konsultationsablauf für diese Spec selbst — bewusste, im Ziel-Abschnitt begründete Ausnahme angesichts der Trivialität und Eindeutigkeit der Anforderung.

## Offene Fragen

Keine.

## Out of Scope

- Inhaltliche Änderungen an den Skill-Abläufen selbst (das ist Story #230).
- Umbenennung/Anpassung der historischen Dateien.
