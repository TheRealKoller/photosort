---
name: capture
description: Hält eine neue Idee oder einen (vermeintlichen) Bug als Rohtext in `specs/inbox/` fest — schnell, ungefiltert, ohne Rückfragen, ohne Recherche, ohne Schärfen/Challengen (das passiert erst später, separat, meist über `idea-sharpener`). Nutze diesen Skill SOFORT, wenn der Nutzer erkennbar nur festhalten will, nicht besprechen — z.B. "notier das für später", "halt das mal fest", "das ist erstmal nur eine Idee", "ich glaube da ist ein Bug, schreib's auf", "leg das in die Inbox", "quick note:". NICHT nutzen, wenn der Nutzer eine Idee direkt besprechen/ausarbeiten will (dafür `idea-sharpener`) oder einen klaren, trivialen Bug sofort behoben haben will.
---

# Capture — Idee oder Bug schnell in der Inbox festhalten

Der Sinn dieses Skills ist Geschwindigkeit: eine Idee oder ein (vermeintlicher) Bug wird roh festgehalten, ohne sie im selben Moment zu bewerten, zu hinterfragen oder auszuarbeiten — das übernimmt später `idea-sharpener` (Ideen) bzw. ein bewusstes eigenes Gespräch (Bugs). Stell deshalb **keine** inhaltlichen Rückfragen zur Sache selbst (kein "warum", kein "für wen", keine Recherche im Code oder in `specs/`) — nur die technischen Minimal-Angaben unten, falls sie nicht eindeutig aus dem Gesagten hervorgehen.

## Schritt 1: Typ bestimmen

Idee oder (vermeintlicher) Bug? Meist aus der Formulierung erkennbar ("wäre cool wenn", "könnten wir nicht auch" → Idee; "das verhält sich komisch", "ich glaube da ist ein Bug" → Bug). Nur nachfragen, wenn wirklich nicht erkennbar — sonst den naheliegenden Typ annehmen.

## Schritt 2: Nächste freie Nummer ermitteln

`specs/inbox/` durchsehen (`ls`/Glob), höchste vorhandene vierstellige Nummer finden, +1. Existiert das Verzeichnis noch nicht, mit `0001` beginnen. Eigener Nummernkreis, unabhängig von `specs/features/`.

## Schritt 3: Eintrag anlegen

Datei `specs/inbox/NNNN-kurzer-slug.md` anlegen (Slug: 2-5 Wörter, kebab-case, aus dem Inhalt abgeleitet). Inhalt nach diesem Muster:

```markdown
# NNNN - <Kurztitel>

**Typ:** Idee | Bug (vermeintlich)
**Erfasst:** <heutiges Datum, YYYY-MM-DD>
**Status:** Unrefined

## Rohtext

<Wortlaut/Inhalt des Nutzers — mitschreiben, nicht interpretieren, nicht ausschmücken, nicht recherchieren. Leichte sprachliche Glättung ist ok (ganze Sätze statt Stichpunkte), aber keine inhaltliche Ergänzung.>
```

Der Rohtext ist bewusst ungefiltert — das spätere Schärfen arbeitet mit dieser Rohfassung als Ausgangspunkt, nicht mit einer bereits interpretierten Version.

## Schritt 4: Kurz bestätigen

Eine knappe Bestätigung im Chat, kein längerer Kommentar: z.B. "Als Inbox-Eintrag #NNNN festgehalten (Typ: Bug)." Keine Einschätzung, keine Rückfrage, keine Vorschläge zur Priorisierung — das ist explizit nicht Teil dieses Schritts.

## Was dieser Skill NICHT tut

- Keine Recherche im Code oder in `specs/`.
- Keine Bewertung, ob die Idee gut ist oder der Bug real ist.
- Keine Spec-Erstellung, kein Roadmap-Eintrag, kein GitHub-Issue.
- Kein Aufruf von `requirements-engineer`/`architect`/anderen Agenten.

Das alles passiert erst, wenn jemand den Eintrag später ausdrücklich verfeinern will — für Ideen i.d.R. über `idea-sharpener` unter Verweis auf die Inbox-Datei, für Bugs in einem eigenen Gespräch (reproduzieren, Ursache prüfen, entscheiden ob und wie behoben wird). Nach erfolgreicher Verfeinerung wird die Inbox-Datei gelöscht (der Inhalt lebt dann als Spec/Fix weiter) — das ist Teil des jeweiligen Folgeschritts, nicht dieses Skills.
