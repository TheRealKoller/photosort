# 0152 - Der Operationskatalog ist eine Übersicht plus eine Datei je Operation

**Status:** Accepted
**Datum:** 2026-11-26
**Bezug:** Issue [#653](https://github.com/TheRealKoller/photosort/issues/653), Feature-Spec
[`0653`](../features/0653-agenten-laden-nur-den-kontext-den-der-lauf-braucht.md)

## Kontext

Der Skill `github-access` ist der einzige Ort für jeden GitHub-Zugriff des Entwicklungsablaufs.
Sein Katalog war eine Datei mit 1.116 Zeilen; ein Lauf, der eine Operation ausführte, lud alle 21
mit. Übersicht, gemeinsame Regeln und Einzelheiten lagen im selben Text, also ließ sich der
Leseumfang nicht verkleinern, ohne eine der drei Ebenen zu verlieren.

## Entscheidung

### 1. Drei Ebenen, ein Ort

Der Katalog bleibt der Skill `github-access` — aber nicht mehr eine Datei:

- `SKILL.md` trägt die Übersicht, den Lebenszyklus, die Wegleiter, die Härtungsregeln, die
  Erlaubnisstufen, die Remote-Grenze, das Fehlschlagmuster, den CI-Ergebnisblock, die
  Fehlerbehandlung und die Zusammenfassung.
- `operationen/<id>.md` trägt genau eine Operation, mit Überschrift `## \`<id>\``.
- Die Übersichtstabelle in `SKILL.md` nennt jede Kennung mit der Datei, die ihre Einzelheiten
  trägt. Andere Dateien verweisen weiterhin ausschließlich über Kennungen und Abschnittstitel
  der `SKILL.md`.

### 2. Geladen wird nach Bedarf

Ein Ablauf lädt `SKILL.md` einmal an seinem ersten GitHub-Berührungspunkt. Vor jeder Operation
liest er deren Datei. Operationen, die der Lauf nicht ausführt, werden nicht geladen. Damit trägt
jeder Lauf die gemeinsamen Regeln und nur die Einzelheiten seines eigenen Vorhabens.

### 3. Eine Operation bleibt eine Definition

Die Zusicherungen gelten unverändert: geschlossene Operationsmenge, genau eine Definitionsstelle
je Operation, die Wege in fester Reihenfolge, das Ziel als Literal, die Auswertungsgrenzen, die
Nachholzeilen. Der Zuschnitt verschiebt Text, er ändert keinen Zugriff. Ein `gh`-Befehl bleibt
innerhalb des Skills erlaubt und außerhalb ein Befund; die Grenze verläuft um das Verzeichnis des
Skills, nicht um eine einzelne Datei.

## Konsequenzen

- Ein Lauf mit einer Operation liest rund die Hälfte der Zeichen des früheren Gesamtkatalogs.
- Eine Änderung an einer Operation liegt in ihrer Datei; die zugehörige Prüfung liest dieselbe
  Datei.
- Neue Operationen entstehen als weitere Datei plus eine Zeile in der Übersicht. Beides wird
  zusammen geprüft: Die Übersicht muss jede definierte Operation nennen, sonst ist sie nicht
  auffindbar.
