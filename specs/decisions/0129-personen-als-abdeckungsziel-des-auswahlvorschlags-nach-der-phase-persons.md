# 0129 - Personen als Abdeckungsziel des Auswahlvorschlags, berechnet nach der Phase `persons`

**Status:** Accepted
**Datum:** 2026-10-01
**Bezug:** [GitHub-Issue #548](https://github.com/TheRealKoller/photosort/issues/548), Spec 0548.
Löst ADR [`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md)
in Punkt 4 (die Menge, aus der ein Platz vergeben wird) und Punkt 7 (Ort der Berechnung im
Kriterien-Lauf) teilweise ab.

## Kontext

Die Vergabe innerhalb eines Events kennt als Abdeckungsziel nur Motive. Die beiden festgelegten
Personen (ADR 0126) sollen gleichrangig mit Motiven abgedeckt werden, ohne dass sich Platzzahl,
Ähnlichkeitsmaß, Motive oder Cloud-Anfragen ändern. Der Vorschlag entsteht heute in der Phase
`ranking`; die Erkennung läuft danach als letzte Phase `persons`. Ein Vorschlag aus `ranking`
kennt die Namen des eigenen Laufs deshalb nicht, beim ersten Lauf eines Projekts gar keine.

## Entscheidung

### 1. Abdeckungsziele sind Motive und Personen, zwei getrennte Mengen

- `SelectionCandidate` bekommt das Pflichtfeld `person_ids: frozenset[int]`: die wirksam
  zugeordneten Personen des Bildes, nur als Id. Ein Name erreicht `selection.py` nie.
- In `_assign_event` gilt eine Person als vorkommend, wenn ein auswahlfähiger Kandidat des Events
  sie trägt. Motive und Personen bleiben zwei getrennte Mengen und werden nie zu einem
  gemeinsamen Schlüsselraum vermischt. Ein Motivschlüssel und eine Personen-Id können sonst
  kollidieren.
- Solange ein vorkommendes Motiv **oder** eine vorkommende Person unvertreten ist, kommen nur Bilder
  in Frage, die etwas davon tragen. Unter ihnen gewinnt der höchste Wert. Das gewählte Bild
  vertritt alles Unvertretene, das es trägt. Die Zahl der abgedeckten Ziele geht nie in den Wert
  ein.
- `_similarity` und `order_alternatives` lesen weiterhin nur Motive. Personen sind kein
  Ähnlichkeitsmerkmal.
- `_quotas` bleibt unberührt. Personen ändern nie, wie viele Plätze ein Event bekommt.

Daraus folgt ohne eigenen Code: Ohne Person in einem Event ist die eingeschränkte Menge dieselbe
wie bisher. Der Vorschlag ist dort deshalb identisch mit dem Vorschlag ohne Personen.

### 2. Woher die Personen kommen

`worker.py::_apply_run_selection` lädt für die auswahlfähigen Ids
`persons.py::load_effective_persons`. Dort gilt die Korrektur vor der Erkennung, und dieselbe
Menge nutzt auch der Personenfilter. Eine zweite Fassung der wirksamen Zuordnung entsteht nicht.
Gelesen wird der **aktuelle** Bestand, wie bei den Motivstärken. Einen Schnappschuss je Lauf gibt
es nicht.

### 3. Im Kriterien-Lauf entsteht der Vorschlag nach der Phase `persons`

- Der Aufruf von `_apply_run_selection` verlässt `_build_grouping_and_rankings`. Ihn rufen danach
  ausdrücklich zwei Stellen: `run_criterion_scoring` nach `_recognize_persons` und vor dem
  Erfolgsvermerk (im selben Commit), und `rebuild_run_grouping` nach
  `_build_grouping_and_rankings`. `rebuild_run_selection` bleibt der dritte Auslöser.
- Die Reihenfolge der Phasen bleibt gleich, und es entsteht kein neuer `ClassificationPhase`-Wert.
  Die Rechnung läuft unter der zuletzt gesetzten Phase (`persons`, oder `ranking`, wenn die
  Personenphase entfällt). Sie dauert so kurz, dass sie keinen eigenen Teilschritt braucht.
- Bis zum Erfolgsvermerk trägt der laufende Lauf keinen Vorschlag. Das ist unsichtbar, weil jeder
  Lesepfad den letzten **erfolgreichen** Lauf liest.

### 4. Kein Auslöser kommt hinzu

Personen anlegen, entfernen und korrigieren rechnet den Vorschlag nie neu. Die Änderung wirkt beim
nächsten der drei bestehenden Auslöser, also spätestens mit dem nächsten Klassifizierungslauf.

## Konsequenzen

- Die Zusage aus Spec 0292, der Auswahlvorschlag sei mit und ohne Personen derselbe, fällt. Der
  Zwillingstest `test_worker_persons.py::test_a_recognised_person_is_no_motif` vergleicht danach
  nur noch Motive, Stärken, Rangfolge und Statistik.
- Eine Richtwert- oder Versatzänderung übernimmt zwischenzeitliche Namenskorrekturen mit. Das
  deckt das „spätestens" der Spec ab.
- Die Import-Graph-Zusagen aus ADR 0126 Punkt 1 bleiben bestehen. `selection.py` importiert kein
  Personenmodul, und kein Cloud-Modul bekommt einen neuen Import.
- Es gibt keine Migration und keine Änderung an API oder Frontend.
