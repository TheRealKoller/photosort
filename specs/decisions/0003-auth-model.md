# 0003 - Auth-Modell

**Status:** Accepted
**Datum:** 2026-07-19

## Kontext

PhotoSort wird von genau zwei Personen genutzt (Daniel und seine Frau), die unabhängig voneinander Fotos kategorisieren sollen — es muss nachvollziehbar sein, wer welche Bewertung abgegeben hat.

## Entscheidung

- Getrennte Benutzerkonten (kein gemeinsamer Login).
- Einfache Passwort-Authentifizierung (Passwörter gehasht mit Argon2), Sessions via JWT.
- Kein Self-Signup: Accounts werden initial durch einen administrativen Schritt angelegt (z.B. CLI-Befehl oder Seed-Migration), da es sich um ein geschlossenes Zwei-Personen-System handelt.

## Begründung

Zwei bekannte Nutzer, kein Bedarf an Registrierung, OAuth-Providern oder Rollenmodell über "Nutzer" hinaus. Getrennte Accounts sind nötig, damit Bewertungen (`Rating`) eindeutig einer Person zugeordnet werden können.

## Konsequenzen

- Kein Passwort-Reset-Flow per E-Mail nötig für den Start (kann später ergänzt werden, wenn benötigt).
- Die konkrete Umsetzung der Account-Anlage (CLI vs. Migration vs. Admin-UI) ist in der jeweiligen Feature-Spec zu klären, sobald Auth implementiert wird.
