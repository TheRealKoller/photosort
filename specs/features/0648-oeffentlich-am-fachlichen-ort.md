# 0648 - Was andere Module brauchen, ist öffentlich und liegt fachlich richtig

**Status:** Accepted
**Erstellt:** 2026-11-18
**Bezug:** [Issue #648](https://github.com/TheRealKoller/photosort/issues/648)

## Ziel

Mehrere Funktionen, die andere Module brauchen, sind als privat markiert und werden trotzdem quer
durch das Projekt importiert. Wer eine davon umbenennt oder ihre Signatur ändert, muss fremde
Module mitpflegen, und der Importgraph zeigt die Schichtung nicht mehr.

Was ein anderes Modul braucht, ist öffentlich und liegt an seinem fachlichen Ort; was privat ist,
wird von außen nicht angefasst.

## User Story

Als Person, die PhotoSort ändert — Mensch wie KI — möchte ich, dass jede Funktion, die ein anderes
Modul braucht, unter einem öffentlichen Namen an ihrem fachlichen Ort liegt, damit ich ihre
Signatur und ihre Zusicherung als Vertrag lesen kann, statt beim Ändern eines fremden Moduls dessen
Innenseiten mitzupflegen — und damit der Importgraph zeigt, wie die Schichten liegen.

## Akzeptanzkriterien

<!-- AK-PLATZHALTER -->

**Maßstab „privat" (ADR [0150](../decisions/0150-privat-heisst-dateilokal-geteilt-heisst-oeffentlich.md)):**
Ein Name mit genau einem führenden Unterstrich gilt nur in der Datei, die ihn definiert; Dunder und
`_` sind ausgenommen, eine `__init__.py` ist eine Datei wie jede andere. Ein Unterstrich am
Modulsegment (`_runs`, `_criterion`, `_reads`, `_conversion`) heißt paketintern und fällt nicht
unter die Regel — über die Paketgrenze hält ihn der bestehende Paketgrenzen-Wächter fern.
Ausgangsstand auf `main` nach Spec 0647: 225 Bezüge auf 61 Symbole im Produktionscode, 71 Symbole
in 35 Testdateien (`local://0648-messung.md`); die 17 des Issue-Bodys stammen von vor der
Modulaufteilung. Zielstand ist in allen drei Fällen 0.

- [ ] **Kein privater Name überschreitet im Produktionscode eine Dateigrenze** — weder per
  Import noch per Attributzugriff auf ein importiertes Modul, noch als Zeichenkette an einer
  Patch-Stelle. Zielstand 0.
- [ ] **Die Funktionen liegen dort, wo ihr Fachgebiet liegt.** Ein Modul außerhalb der
  HTTP-Schicht importiert nicht aus der HTTP-Schicht; ein von mehreren Endpunkten genutzter
  **privater** Baustein liegt nicht in einem der beteiligten Endpunkt-Module (bereits öffentliche
  Bausteine sind nicht Gegenstand dieser Story, siehe Out of Scope); und ein Import innerhalb
  einer Funktion, der ausschließlich einen Zyklus vermeidet, bleibt nicht zurück — beide Seiten
  beziehen den Baustein auf Modulebene aus seinem neuen Ort. Eine Funktion, die HTTP-Verhalten
  trägt (Statuscode und Nutzertext), bleibt in der HTTP-Schicht.
- [ ] **Tests beziehen die geprüfte Funktion über ihre öffentliche Schnittstelle.** Keine
  Testdatei importiert einen privaten Namen aus dem Produktionscode, auch nicht als Zeichenkette
  an einer Stelle, die eine Funktion durch ein Test-Double ersetzt. Je Symbol ist bewusst einer
  von zwei Wegen gewählt: Es wird öffentlich, oder der Test prüft das von außen beobachtbare
  Verhalten und braucht den Namen nicht mehr.
- [ ] **Die öffentliche Fläche wächst nur so weit wie nötig.** Öffentlich wird ausschließlich, was
  tatsächlich von einer anderen Datei benutzt wird; jeder andere Name bleibt privat. Der alte Name
  verschwindet vollständig — kein Alias, kein Re-Export, kein öffentlicher Zwilling am bisherigen
  Ort. Es entstehen keine Sammel-Exporte über die betroffenen Module, und neu öffentliche Namen
  tragen eine Beschreibung ihres fachlichen Zwecks und ihrer geltenden Zusicherung (Docstring,
  bei Konstanten ein Kommentar).

- [ ] **Verhalten und Zusicherungen unverändert.** Die Testfälle bleiben in Anzahl und Aussage
  erhalten; geändert werden nur Namens- und Importzeilen, keine Erwartung. Alle Prüfungen
  inklusive Abdeckungs-Gate sind grün. Die Zusicherungen, die an den betroffenen Funktionen
  hängen, gelten wortgleich weiter und bleiben durch dieselben Tests belegt: genau eine Stelle
  bildet einen Remote-Pfad aus Basis und relativem Pfad und weist aufsteigende Segmente ab
  (`join_remote_path`); genau eine Zeichensanitisierung bedient beide Cloud-Pfade
  (`sanitize_label_text`); genau eine Stelle schreibt den Abbruch-Endzustand eines Laufs
  (`finish_cancelled`), und genau eine übernimmt einen wartenden Lauf (`take_over_queued_run`).
- [ ] **Ein Wächter hält die Regel fest.** Ein automatisierter Test scheitert, sobald im
  Produktionscode oder in einer Testdatei wieder ein privater Name aus einer anderen
  Produktionsdatei benutzt wird — per Import, Attributzugriff, `setattr`/`getattr`/`patch.object`
  oder Patch-Zeichenkette. Seine Meldung nennt Fundstelle und Namen.
- [ ] **Die lebenden Dokumente nennen die Namen, die es gibt.** Architektur-, Sicherheitskonzept-
  und Setup-Dokumentation führen die betroffenen Funktionen unter ihrem neuen Namen und ihrer
  neuen Heimat; abgeschlossene Feature-Specs und Entscheidungen bleiben unverändert.

## Architektur / Umsetzung

**Ansatz.** Reine Sichtbarkeits- und Ablageänderung ohne Verhaltensänderung, festgehalten in ADR
[`0150`](../decisions/0150-privat-heisst-dateilokal-geteilt-heisst-oeffentlich.md): Der führende
Unterstrich wird zur **Dateigrenze**, jeder gemessene Bezug wird zu einem Bezug auf einen
öffentlichen Namen an dessen Definitionsort, zwei Bausteine wechseln in ein Modul ohne Endpunkt,
und `classification_review.py` zieht als achte Lauf-Datei nach `worker/`. Damit verschwinden alle
sechs Importe innerhalb von Funktionen, die nur einen Zyklus vermeiden. Die vier Zusicherungen
aus AK5 bleiben an genau einer Stelle — es ändert sich nur der Name.

**Neue Heimat der verschobenen Bausteine**

| heute | neu | Grund |
|---|---|---|
| `api/projects.py::_count_landmark_candidates`, `::_count_remote_category_candidates` | `candidate_counts.py::count_landmark_candidates`, `::count_remote_category_candidates` (der dritte Zähler bleibt dort privat) | von `criterion_probe.py` (Nicht-HTTP) und `api/` gemeinsam benutzt; ein Endpunkt-Modul ist kein Ort dafür |
| `api/projects.py::_reject_while_a_criterion_run_is_active` | `api/run_guards.py::reject_while_a_criterion_run_is_active` | trägt `409` samt Nutzertext, bleibt also in der HTTP-Schicht, wird aber von `api/model_choice.py` gebraucht |
| `classification_review.py` | `worker/classification_review.py` (`run_classification_review`, `fail_review` statt `_fail`, `ReviewAbort`) | ist ein Lauf, bezieht `_runs` und `_criterion.local` auf Modulebene; keine Funktions-Importe mehr |

**Öffentlich am Definitionsort werden** (Unterstrich fällt, kein Alias, kein Re-Export):
`api/photos/_conversion.py` (`event_out`, `location_out`, `suggestion_reason`, `to_photo_out`),
`api/photos/_reads.py` (13 Lesehilfen, u.a. `get_project_or_404`,
`final_selection_decisions`, `photos_by_id`), `worker/_runs.py` (16 Laufhilfen, u.a.
`set_phase`, `fail_run`, `finish_cancelled`, `take_over_queued_run`, `now_utc`,
`CLOUD_VISION_IMAGE_MIME_TYPE`), `worker/_criterion/*` (Phasen und ihre Bausteine),
`worker/scan.py` und `worker/criterion_scoring.py` (je eine Funktion), `cloud_vision.py`
(`sanitize_label_text`), `opencloud/client.py` (`join_remote_path`) sowie die nur von Tests
benutzten Namen in `classification.py`, `demo_state.py`, den `person`-/`stats`-/`projects`-
Endpunkten, `events.py`, `horizon.py`, `landmark.py`, `remote_classification.py` und den
Probe-Skripten. `worker/__init__.py` verliert 31 `__all__`-Einträge,
`api/photos/__init__.py` zwei.

**Wächter.** `backend/tests/test_private_name_boundary.py` liest den Syntaxbaum von `backend/src`
und `backend/tests`: `from … import _name`, Attributzugriff `alias._name` auf ein
`photosort`-Modul, `setattr`/`getattr`/`monkeypatch.setattr`/`patch.object` mit privatem Namen und
Patch-Zeichenketten der Form `photosort.a.b._name`. Meldung `datei:zeile: _name aus modul`.
Der eigene private Name der Datei bleibt erlaubt, ein Unterstrich-Modulsegment wird übersprungen,
`TYPE_CHECKING`-Importe zählen mit. Bis zur Abarbeitung führt der Test eine Arbeitsliste
`_BEKANNTE_FUNDE` (Datei → Namen) mit **Gleichheitsprüfung in beide Richtungen**; der letzte
Schritt löscht sie und prüft gegen die leere Menge.

**Umsetzung in neun grünen Schritten:** G0 Wächter rot → G1 `sanitize_label_text` →
G2 `join_remote_path` → G3 `candidate_counts`/`run_guards` → G4 `api/photos/_reads`/
`_conversion` → G5 `worker/_runs` → G6 `_criterion`/`criterion_scoring`/`scan` → G7 Prüflauf ins
Worker-Paket → G8 Test-Symbole, Arbeitsliste leeren → G9 Doku. Die vollständige Zuordnung
alt→neu je Symbol, die mitziehenden Wächter-Konstanten und die Doku-Stellen stehen im
Architect-Bericht dieser Spec-Runde.

## UI/UX

Nicht relevant: reine Backend-Umbenennung und -Verlagerung ohne jede sichtbare Oberfläche, kein
Endpunkt und keine Antwort ändert sich.

## Security

<!-- SEC-PLATZHALTER -->

## Entscheidungen

- ux-ui-designer nicht konsultiert (Schritt 2): keine Frontend-Datei, kein Endpunkt, keine
  Antwortform berührt; die Story ändert ausschließlich Namen und Importorte im Backend.

## Offene Fragen

Keine.

## Out of Scope

- Private Helfer, die eine Testdatei aus einer anderen Testdatei importiert: die Testsuite ist
  kein Produkt; diese Helfer gehen mit dem Aufteilen der Testdateien in die gemeinsame Ablage.
- Das Aufteilen der Produktionsmodule selbst (Spec 0647).
- Neues Verhalten, neue Endpunkte, neue Fehlerfälle.
- Bereits öffentliche, aber in Endpunkt-Modulen liegende Bausteine (`api/persons.photo_person_outs`,
  `api/ratings.write_own_rating`, `api/motifs.StrengthBandsOut`,
  `api/photos/duplicate_groups.build_duplicate_group_out`) bleiben, wo sie sind: Die Regel aus
  AK2 gilt für die Symbole dieser Story, also die privaten Namen. Ihr Umzug ist ein eigenes Thema.
