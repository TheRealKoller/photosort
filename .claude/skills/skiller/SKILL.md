---
name: skiller
description: Erstellt schnell einen neuen, schlanken Claude-Skill aus einer kurzen Beschreibung — kurzes Interview (Zweck, Trigger, Ausgabeformat), direkter Entwurf der SKILL.md, ein einzelner Testlauf, fertig. Kein Eval-/Benchmark-Overhead. Nutze diesen Skill IMMER, wenn der Nutzer einen neuen Skill erstellen, einen Workflow "in einen Skill packen", eine wiederholbare Aufgabe als Skill/Command speichern, oder "das nächste Mal automatisch so machen" möchte — auch wenn das Wort "Skill" nicht explizit fällt (z.B. "kannst du dir das merken als wiederverwendbaren Ablauf", "mach daraus ein Tool das ich immer wieder aufrufen kann").
---

# Skiller — schneller Skill-Ersteller

Baut einen neuen Claude-Skill in wenigen Schritten: kurz nachfragen, Entwurf schreiben, einmal testen, fertig. Kein Eval-Set, kein Benchmark, kein Viewer — das übernimmt bei Bedarf der ausführlichere eingebaute `skill-creator`. Skiller ist für den Fall gedacht, dass jemand schnell einen brauchbaren Skill will und lieber durch Benutzung nachbessert als durch aufwändige Vorab-Tests.

## Warum dieser Ablauf

Ein Skill lebt von seiner Trigger-Beschreibung und einer klaren, knappen Anleitung — nicht von Vollständigkeit im ersten Wurf. Die drei Schritte unten (Interview → Entwurf → ein Testlauf) liefern schnell etwas Benutzbares. Feinschliff passiert danach im echten Gebrauch: der Nutzer merkt beim Einsatz, was fehlt, und der Skill wird direkt angepasst.

## Schritt 1: Kurzes Interview

Stelle so knapp wie möglich diese drei Fragen (per AskUserQuestion, wenn sinnvolle Optionen erkennbar sind, sonst als normale Rückfrage im Chat). Wenn der Nutzer die Antworten schon in seiner ursprünglichen Beschreibung mitgeliefert hat, frage nicht erneut danach — nur Lücken füllen:

1. **Was soll der Skill können?** (die eigentliche Aufgabe/der Workflow)
2. **Wann soll er greifen?** (welche Formulierungen/Situationen sollen ihn auslösen)
3. **Wie soll die Ausgabe aussehen?** (Datei, Textantwort, bestimmtes Format/Struktur)

Frage außerdem, **wo der neue Skill abgelegt werden soll**:
- Projektspezifisch: `.claude/skills/<name>/` im aktuellen Projekt (nur hier nutzbar)
- Nutzerweit: `~/.claude/skills/<name>/` (in allen Projekten nutzbar)

## Schritt 2: SKILL.md entwerfen

Lege `<gewählter-ort>/skills/<skill-name>/SKILL.md` an. Halte dich an diese Punkte — sie kommen aus der Erfahrung, was Skills zuverlässig triggerbar und nützlich macht:

- **name**: kurz, kebab-case, eindeutig.
- **description**: Beschreibt WAS der Skill tut UND WANN er greifen soll — beides gehört hier rein, nicht in den Body. Formuliere sie bewusst "pushy": Claude tendiert dazu, Skills zu selten zu ziehen. Statt "Hilft beim Formatieren von Commit-Messages" lieber "Formatiert Commit-Messages nach Conventional-Commits-Schema. Nutze diesen Skill IMMER, wenn der Nutzer einen Commit erstellen will oder nach einer Commit-Message fragt, auch wenn er das Format nicht explizit nennt." Nenne konkrete Formulierungen/Situationen, die triggern sollen.
- **Body**: Anleitung in Imperativ, unter ~500 Zeilen. Erkläre kurz das *Warum* hinter wichtigen Schritten statt nur starre MUSS-Regeln aufzulisten — das gibt Claude beim späteren Ausführen Spielraum für sinnvolle Einzelfallentscheidungen.
- **Bundled resources** (`scripts/`, `references/`, `assets/`) nur anlegen, wenn der Skill sie wirklich braucht (z.B. ein Skript für einen deterministischen Verarbeitungsschritt, eine Vorlage für erzeugte Dateien). Für die meisten schlanken Skills reicht die SKILL.md allein.
- **Prinzip der Überraschungsfreiheit**: Keine Skills, die bei Betrachtung ihrer Beschreibung etwas anderes tun als erwartet, keine schädlichen/verschleiernden Inhalte. Rollenspiel-Skills ("agiere als X") sind in Ordnung.

Zeig dem Nutzer den Entwurf kurz und frag, ob er so passt, bevor du testest — das ist keine ausführliche Review-Runde, nur ein kurzer Sanity-Check ("passt das so, oder soll ich was ändern, bevor ich's teste?").

## Schritt 3: Ein Testlauf

Überlege dir (oder frag den Nutzer nach) einem realistischen Testprompt — genau der Art von Anfrage, die den Skill später wirklich triggern soll.

Führe **einen** Testlauf aus:
- Wenn ein Subagent-Tool verfügbar ist: starte einen Agenten mit dem Hinweis, den Skill unter dem angelegten Pfad zu nutzen, und dem Testprompt als Aufgabe. Kein Vergleichslauf ohne Skill, kein Benchmark — nur dieser eine Lauf.
- Wenn keine Subagenten verfügbar sind: führe den Skill selbst anhand seiner eigenen Anleitung für den Testprompt aus.

Zeig das Ergebnis direkt im Chat (keine eigene Viewer-Seite, kein separates Reporting). Frag den Nutzer, ob es passt oder was fehlt.

## Schritt 4: Nachschärfen (falls nötig)

Bei Feedback: SKILL.md gezielt anpassen (nicht neu schreiben) und bei Bedarf einen zweiten, letzten Testlauf machen. Erkläre Änderungen kurz, statt sie kommentarlos vorzunehmen — der Nutzer soll nachvollziehen können, was sich warum geändert hat.

Wenn der Nutzer zufrieden ist: fertig. Kein Packaging, keine Eval-Optimierung der Trigger-Beschreibung — falls das später gewünscht ist (z.B. weil ein Skill in der Praxis zu selten oder zu oft triggert), verweise auf den ausführlicheren `skill-creator`, der genau dafür eine Beschreibungs-Optimierungsschleife mitbringt.
