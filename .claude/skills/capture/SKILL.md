---
name: capture
description: Hält eine neue Idee oder einen (vermeintlichen) Bug schnell und ungefiltert als GitHub-Issue fest — ohne Rückfragen, ohne Recherche, ohne Schärfen/Challengen (das passiert erst später, separat, über `refinement`). Nutze diesen Skill SOFORT, wenn der Nutzer erkennbar nur festhalten will, nicht besprechen — z.B. "notier das für später", "halt das mal fest", "das ist erstmal nur eine Idee", "ich glaube da ist ein Bug, schreib's auf", "leg das in die Inbox", "quick note:". NICHT nutzen, wenn der Nutzer eine Idee direkt besprechen/ausarbeiten will (dafür `refinement`) oder einen klaren, trivialen Bug sofort behoben haben will.
---

# Capture — Idee oder Bug schnell als GitHub-Issue festhalten

**GitHub-Erlaubnisstufe:** lesend und schreibend

Jeder GitHub-Zugriff läuft über eine Operation des Skills `github-access`; lade ihn einmal über das Skill-Werkzeug, an deinem ersten GitHub-Berührungspunkt (Schritt 3). Dieser Skill nennt ausschließlich Operations-IDs und die Ablauf-Logik drumherum.

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

**Beides in je eine Datei schreiben** (z.B. unter dem Scratchpad-Verzeichnis), mit dem Schreib-Werkzeug, nicht per Shell-Umleitung: den Rohtext in eine Body-Datei, den Titel in eine genau einzeilige Titel-Datei. Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur (Skill `github-access`, Härtungsregel 4.1) — Titel wie Bodies tragen in diesem Projekt regelmäßig Backticks und Dollarzeichen. Die Titel-Datei wird außerdem auf Wohlgeformtheit geprüft (Regel 4.4), auf jedem Weg.

## Schritt 3: Issue anlegen

- `issue-anlegen`

Die Antwort trägt die Nummer des neuen Issues. Daraus wird `NNN` für Schritt 4 gewonnen — und das ist die **einzige** Stelle im gesamten Ablauf, an der eine Zahl aus einer Antwort stammt (die eng gefasste Ausnahme von Härtungsregel 4.2 im Skill `github-access`). Sie wird deshalb gegen `^[0-9]+$` **validiert**, bevor sie irgendwo weiterverwendet wird; weiterverwendet wird ausschließlich die geprüfte Zahl, nie die ausgegebene Zeichenkette, und die Issue-URL wird aus ihr gebildet. Passt sie nicht auf das Muster, wird abgebrochen und Daniel die Ausgabe unverändert gemeldet.

Scheitert die Operation **eindeutig** auf allen Wegen, ist **nichts** entstanden: Meldung des zuletzt versuchten Wegs unverändert an Daniel weitergeben, kein eigener Lösungsversuch, Schritt 4 entfällt. Bei einem **mehrdeutigen** Fehlschlag gilt die Regel aus der Wegleiter: erst lesend verifizieren, ob das Issue doch entstanden ist, nie blind ein zweites anlegen.

## Schritt 4: Issue ins Board aufnehmen

Bewusst eine **zweite** Operation statt eines kombinierten Anlegens: Das Issue soll überleben, auch wenn dieser Teil scheitert.

- `board-aufnahme`

Die URL wird aus der validierten Nummer **gebildet**, nicht aus einer Ausgabe übernommen. Der Statuswert `Unrefined` wird hier **nicht** gesetzt — er entsteht durch den nativen Workflow `Item added to project`, sobald das Item im Projekt liegt.

## Schritt 5: Kurz bestätigen

Eine knappe Bestätigung im Chat, kein längerer Kommentar: z.B. "Als GitHub-Issue #NNN festgehalten (Typ: Bug)." Keine Einschätzung, keine Rückfrage, keine Vorschläge zur Priorisierung — das ist explizit nicht Teil dieses Schritts.

**Ist Schritt 4 fehlgeschlagen** — der Normalfall in einer Cloud-Session, weil `board-aufnahme` dort auf keinem Weg erreichbar ist —, ist das **kein Abbruch**: Das Issue aus Schritt 3 existiert, seine Nummer ist bekannt. Die Bestätigung nennt sie und trägt zusätzlich diesen Abschnitt, mit der Nachhol-Zeile aus dem Katalogeintrag:

```markdown
## Lokal nachzuholen

Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- <Operations-ID>: <Nachhol-Zeile aus dem Katalogeintrag, mit den Nummern dieses Laufs>
```

Ein zweites `issue-anlegen` findet dafür **nicht** statt — das legte ein zweites Issue an. Ohne Item auf dem Board bleibt auch `Unrefined` aus; beides holt dieselbe Nachhol-Zeile nach. Der Abschnitt bleibt im Chat; dieser Skill schreibt ihn in kein GitHub-Artefakt.

## Was dieser Skill NICHT tut

- Keine Recherche im Code oder in `specs/`.
- Keine Bewertung, ob die Idee gut ist oder der Bug real ist.
- Keine Spec-Erstellung, keine Priorisierung.
- Kein Aufruf von `requirements-engineer`/`architect`/anderen Agenten.

Das alles passiert erst, wenn jemand das Issue später ausdrücklich verfeinern will — für Ideen über `refinement`, für Bugs in einem eigenen Gespräch (reproduzieren, Ursache prüfen, entscheiden ob und wie behoben wird).
