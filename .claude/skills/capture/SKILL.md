---
name: capture
description: Hält eine neue Idee oder einen (vermeintlichen) Bug schnell und ungefiltert als GitHub-Issue fest — ohne Rückfragen, ohne Recherche, ohne Schärfen/Challengen (das passiert erst später, separat, über `refinement`). Nutze diesen Skill SOFORT, wenn der Nutzer erkennbar nur festhalten will, nicht besprechen — z.B. "notier das für später", "halt das mal fest", "das ist erstmal nur eine Idee", "ich glaube da ist ein Bug, schreib's auf", "leg das in die Inbox", "quick note:". NICHT nutzen, wenn der Nutzer eine Idee direkt besprechen/ausarbeiten will (dafür `refinement`) oder einen klaren, trivialen Bug sofort behoben haben will.
---

# Capture — Idee oder Bug schnell als GitHub-Issue festhalten

Der Sinn dieses Skills ist Geschwindigkeit: eine Idee oder ein (vermeintlicher) Bug wird roh festgehalten, ohne sie im selben Moment zu bewerten, zu hinterfragen oder auszuarbeiten — das übernimmt später `refinement`. Stell deshalb **keine** inhaltlichen Rückfragen zur Sache selbst (kein "warum", kein "für wen", keine Recherche im Code oder in `specs/`) — nur die technischen Minimal-Angaben unten, falls sie nicht eindeutig aus dem Gesagten hervorgehen.

Seit Spec [`0059`](../../../specs/features/0059-story-lebenszyklus-github-issues.md) entsteht dabei **keine** lokale Datei mehr unter `specs/inbox/` — der Rohtext lebt ausschließlich als neues GitHub-Issue, das `refinement` später direkt liest und verfeinert.

## Schritt 1: Typ bestimmen

Idee oder (vermeintlicher) Bug? Meist aus der Formulierung erkennbar ("wäre cool wenn", "könnten wir nicht auch" → Idee; "das verhält sich komisch", "ich glaube da ist ein Bug" → Bug). Nur nachfragen, wenn wirklich nicht erkennbar — sonst den naheliegenden Typ annehmen.

## Schritt 2: Titel und Rohtext vorbereiten

Leite aus dem Gesagten einen knappen Klartitel ab (keine Nummer davor — die GitHub-Issue-Nummer selbst ist ab jetzt die Identität, siehe ADR [`0036`](../../../specs/decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md), Abschnitt 1) sowie den Rohtext:

```markdown
## Rohtext

<Wortlaut/Inhalt des Nutzers — mitschreiben, nicht interpretieren, nicht ausschmücken, nicht recherchieren. Leichte sprachliche Glättung ist ok (ganze Sätze statt Stichpunkte), aber keine inhaltliche Ergänzung.>
```

Der Rohtext ist bewusst ungefiltert — das spätere Schärfen arbeitet mit dieser Rohfassung als Ausgangspunkt, nicht mit einer bereits interpretierten Version.

**Beides in je eine Datei schreiben** (z.B. unter dem Scratchpad-Verzeichnis), mit dem Schreib-Werkzeug, nicht per Shell-Umleitung: den Rohtext in eine Body-Datei, den Titel in eine genau einzeilige Titel-Datei. Freitext gelangt nie in eine Kommandozeile (siehe `.claude/skills/github-access/SKILL.md`, „Verbindliche Regeln beim Einsetzen von Werten") — Titel wie Bodies tragen in diesem Projekt regelmäßig Backticks und Dollarzeichen.

## Schritt 3: Issue anlegen

```bash
gh issue create --repo TheRealKoller/photosort --title "$(cat <titel-datei>)" --body-file <body-datei> --label <idee|bug>
```

Der Aufruf gibt die URL des neuen Issues aus. Daraus wird die Issue-Nummer `NNN` für Schritt 4 gewonnen — und das ist die **einzige** Stelle im gesamten Ablauf, an der eine Zahl aus einer `gh`-Ausgabe stammt (siehe die Ausnahme in [`github-access`](../github-access/SKILL.md), Abschnitt „Verbindliche Regeln beim Einsetzen von Werten"). Sie wird deshalb **geparst und gegen `^[0-9]+$` validiert**, bevor sie irgendwo weiterverwendet wird; weiterverwendet wird ausschließlich die geprüfte Zahl, nie die ausgegebene Zeichenkette. Passt sie nicht auf das Muster, wird abgebrochen und Daniel die Ausgabe unverändert gemeldet.

Scheitert er (Exit-Code ≠ 0), ist **nichts** entstanden: Meldung unverändert an Daniel weitergeben, kein eigener Lösungsversuch, Schritt 4 entfällt.

## Schritt 4: Issue ins Board aufnehmen

Bewusst ein **zweiter** Befehl statt `gh issue create --project`: Das Issue soll überleben, auch wenn dieser Teil scheitert.

```bash
gh project item-add 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/<NNN> --format json --jq '.id'
```

Die URL wird aus der Nummer **gebildet**, nicht aus der `gh`-Ausgabe übernommen. Der Statuswert `Unrefined` wird hier **nicht** gesetzt — er entsteht durch den nativen Workflow `Item added to project`, sobald das Item im Projekt liegt.

## Schritt 5: Kurz bestätigen

Eine knappe Bestätigung im Chat, kein längerer Kommentar: z.B. "Als GitHub-Issue #NNN festgehalten (Typ: Bug)." Keine Einschätzung, keine Rückfrage, keine Vorschläge zur Priorisierung — das ist explizit nicht Teil dieses Schritts.

**Ist Schritt 4 fehlgeschlagen** (typischer Fall: eine Remote-Session, in der jeder Board-Zugriff mit `HTTP 403` endet), ist das **kein Abbruch**: Das Issue aus Schritt 3 existiert, seine Nummer steht in der Ausgabe. Die Bestätigung nennt sie und trägt zusätzlich diesen Abschnitt:

```markdown
## Lokal nachzuholen

Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- `board-aufnahme`: `gh project item-add 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/NNN --format json --jq '.id'`
```

`gh issue create` wird dafür **nicht** wiederholt — das legte ein zweites Issue an. Ohne Item auf dem Board bleibt auch `Unrefined` aus; beides holt derselbe Befehl nach. Der Abschnitt bleibt im Chat; dieser Skill schreibt ihn in kein GitHub-Artefakt.

## Was dieser Skill NICHT tut

- Keine Recherche im Code oder in `specs/`.
- Keine Bewertung, ob die Idee gut ist oder der Bug real ist.
- Keine Spec-Erstellung, keine Priorisierung.
- Kein Aufruf von `requirements-engineer`/`architect`/anderen Agenten.

Das alles passiert erst, wenn jemand das Issue später ausdrücklich verfeinern will — für Ideen über `refinement`, für Bugs in einem eigenen Gespräch (reproduzieren, Ursache prüfen, entscheiden ob und wie behoben wird).
