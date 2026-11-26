# 0653 - Agenten laden nur den Kontext, den der Lauf braucht

**Status:** Implemented ([PR #671](https://github.com/TheRealKoller/photosort/pull/671))
**Erstellt:** 2026-11-26
**Bezug:** Issue [#653](https://github.com/TheRealKoller/photosort/issues/653)

## Ziel

Der GitHub-Operationskatalog wird bei jedem Lauf geladen, der GitHub berührt, obwohl der Lauf
meist nur eine oder zwei seiner 21 Operationen ausführt. Nach dem Umbau trägt eine Übersicht die
gemeinsamen Regeln und den Weg zu jeder Operation; die Einzelheiten einer Operation stehen in
einer eigenen Datei und werden erst gelesen, wenn der Lauf sie ausführt.

Der Zugriff selbst ändert sich nicht: dieselben Wege in derselben Reihenfolge, dieselbe
Fehlschlagbehandlung, dieselben Feldmengen, dieselben Nachholzeilen. Der Umbau ist ein Zuschnitt.

## User Story

Als ausführender Agent im Entwicklungsablauf möchte ich beim GitHub-Zugriff nur die Übersicht, die
gemeinsamen Regeln und die Einzelheiten der Operationen im Kontext haben, die ich in diesem Lauf
ausführe, damit jeder Lauf weniger Kontext verbraucht, ich eine Operation ohne Umweg über den
ganzen Katalog finde und eine Änderung an einer Operation nicht mehr die Prüfung des gesamten
Katalogs durchquert.

## Akzeptanzkriterien

- [ ] **Der Zugriff verhält sich unverändert.** Für jede der 21 Operationen führt der neue Aufbau
      zum selben Verhalten: dieselben Zugangswege in derselben Reihenfolge, dieselbe Behandlung
      eines eindeutigen und eines mehrdeutigen Fehlschlags, dieselben Feldmengen beim Lesen,
      dieselbe Nachholzeile.
- [ ] **Jede Operation ist aus der Übersicht heraus auffindbar.** Die Übersicht in `SKILL.md` nennt
      jede Operation mit unveränderter Kennung und verweist auf ihre Datei unter `operationen/`.
      Keine Kennung entfällt, keine kommt hinzu, keine ändert ihre Schreibweise.
- [ ] **Die Kontextkosten je Lauf sinken messbar.** Ein Lauf mit genau einer Operation liest
      `SKILL.md` plus eine Operationsdatei und damit weniger Zeichen als der heutige Gesamtkatalog
      (69.091). Ein Lauf lädt nie die Einzelheiten einer Operation, die er nicht ausführt.
- [ ] **Keine Zusicherung verschwindet beim Kürzen.** Jede Zusicherung des heutigen Katalogs hat
      im neuen Zuschnitt genau einen Ort: Leiterregeln samt Ausnahme bei mehrdeutigem Fehlschlag,
      Härtungsregeln 4.1–4.5 samt Nummern-Ausnahme, drei Erlaubnisstufen mit Rollenlisten,
      Remote-Grenze samt wörtlichem Nachhol-Abschnitt, Zielangaben je Operation, geschlossene
      Operationsmenge samt „keine Operation liest Issue-Kommentare", Lebenszyklus,
      CI-Ergebnisblock, Fehlerbehandlungsmuster und Zusammenfassung.
- [ ] **Genau ein Ort bleibt genau ein Ort.** Der Katalog ist der Skill `github-access` als Ganzes:
      Übersicht und gemeinsame Regeln in `SKILL.md`, je Operation genau eine Datei unter
      `operationen/`. Keine Zusicherung steht doppelt.
- [ ] **Die statische Absicherung greift weiter und wird nicht blind.** Ein `gh`-Befehl außerhalb
      des Skills fällt weiterhin auf; ein Aufruf in irgendeinem Teil des Katalogs bleibt erlaubt.
      Die Operationsmenge, die Ein-Definitions-Zusage, die Wege und die Auswertungsgrenzen werden
      über den verteilten Katalog geführt. Ein leeres oder unvollständiges Leseergebnis lässt die
      Prüfung laut scheitern.
- [ ] **Jeder Verweis auf den Katalog bleibt gültig.** Abschnittszitate aus Ablauf-Skills treffen
      weiterhin eine Überschrift in `SKILL.md`; die Angaben in `docs/setup.md` und
      `docs/ai-workflow.md` beschreiben den verteilten Katalog.

## Technischer Ansatz

- `SKILL.md` behält Frontmatter, Einordnung, Lebenszyklus, Wegleiter, Härtungsregeln,
  Erlaubnisstufen, Remote-Grenze, Fehlschlagmuster, CI-Block, Fehlerbehandlung und
  Zusammenfassung. Anstelle der 21 Operationsabschnitte tritt eine Übersichtstabelle mit Kennung,
  Zweck und Dateipfad sowie die Ladeanweisung.
- Jede Operation erhält `operationen/<id>.md`. Der Text wird unverändert übernommen; die
  Überschrift sinkt von `###` auf `##`, weil die Datei nur diese eine Operation trägt.
- Verweise auf `SKILL.md` werden dort ergänzt, wo eine Operationsdatei ohne den gemeinsamen Teil
  nicht lesbar wäre (Lebenszyklus-Tabelle, Wegleiter). Relative Dateiverweise werden auf die neue
  Tiefe gezogen.

## Teststrategie

- Der Katalogwächter (`scripts/tests/test_github_zugriff_an_einer_stelle.py`) liest den Katalog
  bereits über den Suchraum. Er wird um die Skill-Grenze ergänzt: zugriffsberechtigt ist jede
  Datei unter `.claude/skills/github-access/`, ein Abschnittszitat darf den Skillnamen nennen.
- Die Wächter, die bisher eine feste Datei lasen (`test_bereichsvorrat`,
  `test_entfallene_label_restlos`, `test_ci_warten_verankert`, `test_ship_entwurf_skill`,
  `test_story_entwurf_skill`), lesen die Operationsdatei der geprüften Operation.
- `mutationen.py` zeigt je Katalog-Invariante weiterhin einen herbeigeführten Verstoß, jetzt an
  der Datei, die die verletzte Stelle trägt.

## Auswirkungen

- Ein Lauf lädt 33.561 statt 69.091 Zeichen für die gemeinsamen Regeln; je ausgeführter Operation
  kommen ihre 0,5 bis 7,5 Tausend Zeichen hinzu.
- Eine Änderung an einer Operation berührt ihre Datei und nur die Prüfungen, die diese Operation
  tragen.
