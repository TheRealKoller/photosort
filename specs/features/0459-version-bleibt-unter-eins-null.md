# 0459 - Die Projektversion bleibt unter 1.0

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [GitHub-Issue #459](https://github.com/TheRealKoller/photosort/issues/459)

## Ziel

Die automatisch vergebene Projektversion bleibt unterhalb von 1.0.0, bis Daniel den ersten reifen
Stand ausruft. Der Sprung auf 1.0.0 ist eine Produktentscheidung und darf nicht als Nebenwirkung
eines einzelnen Commit-Suffixes entstehen.

Am 2026-09-12 ist genau das passiert: Der Merge von PR #450 (`feat!: …`) zog die Version von
0.43.0 auf 1.0.0 und erzeugte Tag und GitHub-Release `v1.0.0`. Ursache ist
`bump-minor-pre-major: false` in `release-please-config.json` — das Flag schont die
Major-Version vor 1.0 nur, wenn es auf `true` steht.

## User Story

Als Stakeholder möchte ich, dass die Versionsnummer weiter im 0.x-Bereich zählt, auch wenn eine
Änderung als Breaking Change gekennzeichnet ist, damit ich den Zeitpunkt von 1.0.0 selbst
bestimme und die Versionsnummer nach außen keine Reife behauptet, die noch nicht erreicht ist.

## Akzeptanzkriterien

1. Ein Breaking Change (`feat!:`, `fix!:`, `BREAKING CHANGE:`-Footer) erzeugt unterhalb von
   1.0.0 einen MINOR-Bump, keinen MAJOR-Bump.
2. `feat:` bumpt weiterhin MINOR, `fix:`/`perf:` weiterhin PATCH — unverändert.
3. Tag und GitHub-Release `v1.0.0` existieren nicht mehr.
4. Manifest, Frontend-Paketdateien und Changelog stehen wieder auf dem Stand 0.43.0.
5. Der nächste von release-please vorgeschlagene Release ist 0.44.0 und enthält die seit
   `v0.43.0` aufgelaufenen Änderungen vollständig.
6. Der Schritt auf 1.0.0 bleibt jederzeit möglich, ohne Code zu ändern: ein einzelner
   Konfigurationswert genügt.

## Architektur / Umsetzung

Die Entscheidung steht in ADR
[`0096`](../decisions/0096-erste-hauptversion-ist-eine-produktentscheidung.md).

**Betroffene Dateien, in dieser Reihenfolge:**

1. `release-please-config.json` — `bump-minor-pre-major` von `false` auf `true`.
   `bump-patch-for-minor-pre-major` bleibt unverändert auf `false`; es steuert das
   `feat:`-Verhalten und ist von dieser Änderung nicht betroffen (Kriterium 2).
2. `.release-please-manifest.json` — zurück auf `0.43.0`. Das Manifest ist laut ADR 0008 die
   Source of Truth; alles Weitere leitet sich davon ab.
3. `CHANGELOG.md` — der Abschnitt `## [1.0.0]` wird ersatzlos entfernt. Seine Einträge
   beschreiben Änderungen, die seit `v0.43.0` auf `main` liegen; release-please stellt sie beim
   nächsten Lauf unter der dann berechneten Nummer 0.44.0 wieder her.
4. `frontend/package.json` und `frontend/package-lock.json` (zwei Stellen: `$.version` und
   `$.packages[''].version`) — zurück auf `0.43.0`, entsprechend den `extra-files`-Einträgen der
   Konfiguration.
5. ADR `0008` — der falsche Kommentar am Flag wird richtiggestellt.

**Ausserhalb des Repositories, nach dem Eröffnen des Pull Requests und vor dessen Merge:**

- GitHub-Release `v1.0.0` löschen, Tag `v1.0.0` löschen (remote und lokal).
- Den offenen release-please-Pull-Request schliessen; der nächste Lauf legt ihn neu an.

Die Reihenfolge ist tragend: Existiert der Tag `v1.0.0` beim Merge dieses Pull Requests noch,
rechnet release-please ab diesem Tag weiter und der zurückgedrehte Manifest-Wert führt zu einem
Zustand, in dem Tag und Manifest sich widersprechen.

**Der Titel dieses Pull Requests trägt den Typ `chore:`.** Das Repository squasht mit
`COMMIT_OR_PR_TITLE`, der Titel wird damit zum Merge-Commit auf `main` und ist die einzige
Grundlage, auf der release-please die Änderung klassifiziert. `chore` ist nicht releasable und
löst deshalb selbst keinen Bump aus — jeder releasable Typ täte es und würde die gerade
zurückgedrehte Zählung sofort wieder verschieben.

## UI/UX

Kein Bezug — die Änderung berührt keine Oberfläche.

## Security

Keine neue Auflage. Das Löschen von Tag und Release erfolgt mit Daniels ausdrücklicher,
vorheriger Freigabe für genau diesen Tag; beides ist nach aussen sichtbar und das Löschen eines
Release ist nicht umkehrbar.

## Teststrategie

**Kein automatisierter Test**, und das ist eine bewusste Abweichung von der TDD-Vorgabe in
`CLAUDE.md`, nicht ein Versäumnis. Die Änderung besteht aus Konfigurationswerten ohne eigene
Logik; das Verhalten, das zu prüfen wäre, liegt vollständig in einer externen GitHub Action.

Ein Wächtertest auf `bump-minor-pre-major: true` wurde erwogen und von Daniel verworfen: Der Wert
wird beim geplanten Schritt auf 1.0.0 wieder umgestellt, und ein Test, der ihn festschreibt,
müsste dann mitgelöscht werden.

Verifiziert wird stattdessen am realen Lauf: Nach dem Merge muss der von release-please
vorgeschlagene Release die Nummer **0.44.0** tragen (Kriterium 5). Trägt er eine andere, ist die
Umsetzung nicht gelungen.

## Entscheidungen

- **Zurückdrehen statt Weiterzählen ab 1.0.1.** Ein Weiterzählen ließe die nach außen sichtbare
  Hauptversion stehen — genau das, was das Ziel ausschließt.
- **Der Changelog-Abschnitt wird entfernt, nicht umbenannt.** release-please erzeugt ihn beim
  nächsten Lauf aus den Commits neu; ein von Hand umgeschriebener Abschnitt würde dabei
  doppelt.

## Offene Fragen

Keine.

## Out of Scope

- Ein Wächtertest auf den Konfigurationswert (siehe Teststrategie).
- Die Versionsdrift in `backend/pyproject.toml`: Die Datei steht seit dem Bootstrap auf `0.1.0`,
  weil dem `generic`-Updater die Zeilen-Annotation `x-release-please-version` fehlt, die er zum
  Finden der Stelle braucht. Eigener Befund, eigenes Issue — diese Spec dreht die Version dort
  nicht zurück, weil sie dort nie mitgewandert ist.
