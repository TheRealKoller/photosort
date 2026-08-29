---
name: capture
description: Hält eine neue Idee oder einen (vermeintlichen) Bug schnell und ungefiltert als GitHub-Issue fest — ohne Rückfragen, ohne Recherche, ohne Schärfen/Challengen (das passiert erst später, separat, über `refinement`). Nutze diesen Skill SOFORT, wenn der Nutzer erkennbar nur festhalten will, nicht besprechen — z.B. "notier das für später", "halt das mal fest", "das ist erstmal nur eine Idee", "ich glaube da ist ein Bug, schreib's auf", "leg das in die Inbox", "quick note:". NICHT nutzen, wenn der Nutzer eine Idee direkt besprechen/ausarbeiten will (dafür `refinement`) oder einen klaren, trivialen Bug sofort behoben haben will.
---

# Capture — Idee oder Bug schnell als GitHub-Issue festhalten

Der Sinn dieses Skills ist Geschwindigkeit: eine Idee oder ein (vermeintlicher) Bug wird roh festgehalten, ohne sie im selben Moment zu bewerten, zu hinterfragen oder auszuarbeiten — das übernimmt später `refinement`. Stell deshalb **keine** inhaltlichen Rückfragen zur Sache selbst (kein "warum", kein "für wen", keine Recherche im Code oder in `specs/`) — nur die technischen Minimal-Angaben unten, falls sie nicht eindeutig aus dem Gesagten hervorgehen.

Seit Spec [`0059`](../../../specs/features/0059-story-lebenszyklus-github-issues.md) entsteht dabei **keine** lokale Datei mehr unter `specs/inbox/` — der Rohtext lebt ausschließlich als neues GitHub-Issue (Status `Unrefined`), das `refinement` später direkt liest und verfeinert.

## Schritt 1: Typ bestimmen

Idee oder (vermeintlicher) Bug? Meist aus der Formulierung erkennbar ("wäre cool wenn", "könnten wir nicht auch" → Idee; "das verhält sich komisch", "ich glaube da ist ein Bug" → Bug). Nur nachfragen, wenn wirklich nicht erkennbar — sonst den naheliegenden Typ annehmen.

## Schritt 2: Titel und Rohtext vorbereiten

Leite aus dem Gesagten einen knappen Klartitel ab (keine Nummer davor — die GitHub-Issue-Nummer selbst ist ab jetzt die Identität, siehe ADR [`0036`](../../../specs/decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md), Abschnitt 1) sowie den Rohtext:

```markdown
## Rohtext

<Wortlaut/Inhalt des Nutzers — mitschreiben, nicht interpretieren, nicht ausschmücken, nicht recherchieren. Leichte sprachliche Glättung ist ok (ganze Sätze statt Stichpunkte), aber keine inhaltliche Ergänzung.>
```

Der Rohtext ist bewusst ungefiltert — das spätere Schärfen arbeitet mit dieser Rohfassung als Ausgangspunkt, nicht mit einer bereits interpretierten Version.

## Schritt 3: Issue anlegen

Rohtext in eine temporäre Datei schreiben (z.B. unter dem Scratchpad-Verzeichnis) und das Script `scripts/gh-board.py` im `create-issue`-Modus aufrufen (siehe Skill `github-board`):

```bash
python3 scripts/gh-board.py create-issue \
  --type idee|bug --title "<Klartitel>" --body-file <pfad-zur-rohtext-datei>
```

Das legt ein neues GitHub-Issue an (Status `Unrefined`, passendes `idee`/`bug`-Label, dem Project hinzugefügt) und gibt `{"issue_number": NNN}` auf stdout zurück. Enthält die Ausgabe stattdessen `{"error": "..."}`, die Meldung unverändert an Daniel weitergeben (kein eigener Lösungsversuch, analog zum `github-board`-Skill).

## Schritt 4: Kurz bestätigen

Eine knappe Bestätigung im Chat, kein längerer Kommentar: z.B. "Als GitHub-Issue #NNN festgehalten (Typ: Bug)." Keine Einschätzung, keine Rückfrage, keine Vorschläge zur Priorisierung — das ist explizit nicht Teil dieses Schritts.

## Was dieser Skill NICHT tut

- Keine Recherche im Code oder in `specs/`.
- Keine Bewertung, ob die Idee gut ist oder der Bug real ist.
- Keine Spec-Erstellung, keine Priorisierung.
- Kein Aufruf von `requirements-engineer`/`architect`/anderen Agenten.

Das alles passiert erst, wenn jemand das Issue später ausdrücklich verfeinern will — für Ideen über `refinement`, für Bugs in einem eigenen Gespräch (reproduzieren, Ursache prüfen, entscheiden ob und wie behoben wird).
