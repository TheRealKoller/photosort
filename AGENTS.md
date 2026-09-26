# AGENTS.md — Einstieg für OpenCode

Dieses Repository wird vollständig von KI entwickelt. Die verbindliche Verfassung steht in
[`CLAUDE.md`](./CLAUDE.md). Diese Datei existiert nur, weil OpenCode automatisch `AGENTS.md`
lädt und `CLAUDE.md` nicht — sie ersetzt `CLAUDE.md` nicht und wiederholt sie nicht.

**Lies `CLAUDE.md` zu Beginn jeder Session vollständig und halte dich unverändert daran** —
Rollenmodell, Spec-first, TDD, Konventionen, Werkzeugwahl, Doku-Pflege. Sie gilt hier genauso
wie in Claude Code.

## Was OpenCode automatisch übernimmt

- Die Skills unter [`.claude/skills/`](./.claude/skills/) sind unverändert gültig und werden
  geladen — der gesamte Ablauf (`refinement`, `spec-writer`, `review-*`, `ship-feature`,
  `browse-app`, `github-access`, …) steht zur Verfügung.

  **Bedingung: der YAML-Kopf bleibt strikt.** OpenCode parst ihn strenger als Claude Code und
  lässt eine `SKILL.md` **still** fallen, wenn ihr `description:` kein gültiger YAML-Skalar ist
  — ein `: ` im unquotierten Wert (z. B. ``Anker `## Blockiert: … nötig` ``) genügt. Ein
  `description:` mit Doppelpunkt gehört deshalb in Anführungszeichen (`description: '…'`); der
  Text selbst ändert sich dadurch nicht.

## Was eine OpenCode-Fassung braucht

- Die Rollen-Agenten unter [`.claude/agents/`](./.claude/agents/) sind für Claude Code
  geschrieben. Ihre OpenCode-Fassung (Subagenten mit denselben Rollen und Werkzeuggrenzen)
  liegt unter [`.opencode/agents/`](./.opencode/agents/) und verweist auf die jeweilige
  Rollendatei als einzige inhaltliche Quelle.

## omp

omp liest statt dieser Datei [`.omp/AGENTS.md`](./.omp/AGENTS.md): Sie bindet `CLAUDE.md`
vollständig ein und übersetzt die Claude-Code-Werkzeuge der Skills und Rollendateien auf die von
omp. Die Skills unter `.claude/skills/` lädt omp unverändert; die Rollen-Agenten liegen in
omp-Fassung unter [`.omp/agents/`](./.omp/agents/) und verweisen wie die OpenCode-Fassung auf die
jeweilige Rollendatei als einzige inhaltliche Quelle. Für ihren YAML-Kopf gilt dieselbe
Strenge-Bedingung wie oben.
