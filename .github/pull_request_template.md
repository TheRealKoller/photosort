## Bezug

- Spec: `specs/features/....md` (Status vor diesem PR: Accepted)

<!--
Die folgende Zeile verknüpft PR und Issue strukturiert: GitHub zeigt sie beidseitig an
(PR: "Linked issues", Issue: "Linked pull requests") und schließt das Issue beim Merge
nach `main` selbst. Ohne sie entsteht nur ein Cross-Reference-Eintrag in der Timeline.
Einzutragende Nummer: bei neuen Specs die Spec-Nummer, bei Altspecs 0001-0065 die Nummer
aus der `**Bezug:**`-Zeile der Spec-Datei.
Ausnahme: PR ohne Issue-Bezug (reine Doku-/Chore-PRs) — Zeile löschen.
Das Keyword gehört ausschließlich hierher, nie in eine Commit-Nachricht oder den PR-Titel:
Beim Squash-Merge wandern beide Texte in Merge-Commit, Changelog und Release-PR.
-->
Closes #NNN

## Änderung

Kurz beschreiben, was und warum geändert wurde.

## Tests

- [ ] Neue/angepasste Tests decken die Änderung ab
- [ ] `pytest` (backend) grün
- [ ] `npm test` (frontend) grün
- [ ] Spec-Status ggf. auf `Implemented` aktualisiert
