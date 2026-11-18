# 0648 - Was andere Module brauchen, ist öffentlich und liegt fachlich richtig

**Status:** Accepted
**Erstellt:** 2026-11-18
**Bezug:** [Issue #648](https://github.com/TheRealKoller/photosort/issues/648)

Über dem Richtwert von rund 200 Zeilen: Die Verschiebetabelle muss je Baustein alten und neuen
Ort nennen, weil AK4 „kein Zwilling" nur so prüfbar ist, und der Abschnitt Security trägt die
vier Zusicherungen aus AK5 mit ihren neuen Adressen.

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
| `api/projects.py::_count_landmark_candidates`, `::_count_remote_category_candidates`, `::_count_eye_candidates` | `candidate_counts.py::count_landmark_candidates`, `::count_remote_category_candidates`, `::count_eye_candidates` | von `criterion_probe.py` (Nicht-HTTP) und `api/` gemeinsam benutzt; ein Endpunkt-Modul ist kein Ort dafür |
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

**Einordnung: sicherheitsrelevant — als Sichtbarkeits- und Adressänderung, nicht als
Verhaltensänderung.** Kein Endpunkt, keine Antwort, keine Abfrage und kein Pfad ändert sich; es
entsteht keine neue Angriffsfläche und kein neues Restrisiko.

Betroffen ist die **Auffindbarkeit** der vier Zusicherungen aus AK5. Das Sicherheitskonzept
verankert sie über ihren Namen (Ankerliste, Abschnitt „Wer eine dieser Stellen verschiebt,
umbenennen oder ihren Schutz entfernt, zieht diese Liste im selben Pull Request nach"). Ein Name,
den es nach dem Umbau nicht mehr gibt, macht die Auflage unprüfbar: Wer eine sechste
Sanitisierungsstelle braucht, sucht die im Konzept genannte Adresse, findet keine Definition und
legt naheliegend eine zweite Fassung an — genau das, was die Auflage verbietet. Deshalb ziehen
`specs/architecture/0003-securitykonzept.md` (Adressen je Symbol: `join_remote_path`,
`sanitize_label_text`, `finish_cancelled`, `take_over_queued_run`, `fail_run`/`fail_export_run`/
`fail_review`, `reject_while_a_criterion_run_is_active`, `count_*_candidates`, `to_photo_out`,
`photos_by_id`, `partition_sizes`, `recognize_persons`, `place_infos`, `landmark_points_by_name`,
`apply_run_selection`, `build_grouping_and_rankings`, `log_cloud_vision_failure`,
`record_cloud_vision_error`, `start_criterion_scoring_run`, `album_level_source`,
`filtered_photo_ids`, `latest_successful_criterion_scoring_run_id`, `classify_scan_entries`) und
die Sicherheitskommentare im Code im selben Pull Request nach.

**Die eine fail-open-Stelle.** Wächter, die Namen als Zeichenketten führen, sind meist fail-closed:
Gleichheit gegen eine erwartete Menge wird bei veraltetem Namen rot. Eine Deny-Liste schneidet
dagegen nur — ein veralteter Eintrag trifft nichts, und der Test bleibt grün, ohne noch zu
schützen. `tests/test_classification_review_isolation.py::VERBOTENE_NAMEN` ist diese Form; ihre
vier betroffenen Einträge (`run_eye_phase`, `build_classification_estimate`,
`build_grouping_and_rankings`, `rebuild_run_selection` — der letzte ist heute schon tot) wandern im
selben Schritt wie die Namen.

**Schichtung und Duplikationsauflage.** `api/run_guards.py` bleibt in der HTTP-Schicht: die
Prüfung trägt Statuscode `409` und deutschen Nutzertext, beide Aufrufer sind HTTP-Handler, kein
Worker-Modul importiert sie. `candidate_counts.py` liegt oberhalb der HTTP-Schicht und enthält nur
Datenbank-Zählungen (kein `fastapi`, kein Worker-Import); `criterion_probe.py` bezieht sie auf
Modulebene statt aus `api/projects.py`, womit eine Kante Probe → HTTP-Schicht entfällt. Die
bewusste Duplikation derselben Ausschuss-/Schwellenbedingungen wie im Lauf bleibt Auflage
(S14/S15): `test_ausschuss_ueberlebende.py::_ERWARTETE_VERWENDUNGEN` führt den Schlüssel
`("candidate_counts.py", "survives_ausschuss"): 3` — umbenannt, nicht gestrichen; die Summe ist die
Zusicherung, nicht der Dateiname. Ebenso bleibt `"photosort.candidate_counts" in in_probe` in
`test_criterion_probe.py` die einzige Prüfung gegen eine stille Kopie der Zählung.

**Patch-Ziele.** Mit den gestrichenen Re-Exporten in `worker/__init__.py` verschwindet eine zweite
Adresse, an der ein Patch still nicht greifen konnte; jeder Patch zeigt danach auf den
Definitionsort oder scheitert laut.

**Restrisiko:** keines neu. Python erzwingt Sichtbarkeit nicht — die Regel bleibt eine Test- und
Konventionsregel, was ADR 0150 festhält und diese Story nicht ändert.

## Teststrategie

Reine Sichtbarkeits- und Ablageänderung: kein neuer Verhaltenstest. Neu ist genau **ein**
Struktur-Test über den Syntaxbaum (Klasse B nach ADR 0148); die Zusicherungen aus AK5 tragen
weiterhin die vorhandenen Tests, deren Knotenmenge gleich bleibt.

**AK1/AK3/AK6 — ein Wächter, drei Zusicherungen.**
`backend/tests/test_private_name_boundary.py` liest den Syntaxbaum von `backend/src` und
`backend/tests`; `finde_verstoesse(pfad)` liefert je Datei `(Zeile, Name, Modul)`, die Adresse ist
`src`- bzw. `tests`-relativ, die Meldung lautet `datei:zeile: name aus modul`.

- AK1 und AK3 sind **eine** Messung mit Pfadpräfix: die Fundmenge über `PRODUCTION_DIR` bzw.
  `TESTS_DIR` ist gleich der Arbeitsliste (G0–G8), ab G8 `== set()`. Die Gleichheit trägt die
  Aussage, weil sie den Bestand misst und die Erwartung der jeweilige Schritt ist — keine
  eingefrorene Namensliste, keine Prüfung von `__all__`-Längen. Eine bloße „keine Funde“-Assertion
  wäre auf jedem kaputten Walker grün; deshalb der Nicht-Leer-Nachweis über beide Wurzeln.
- AK6 belegt je Erfassungsform (`from`-Import, Attribut, `setattr`, `getattr`, `patch.object`,
  Patch-Zeichenkette) ein handgeschriebenes Snippet mit **genau einem** Fund und ausgeschriebenem
  Meldungstext. Die Snippets nennen einen Namen, der dauerhaft dateilokal bleibt (`_counted`),
  sonst prüften sie nach dem Umbau nichts mehr. Je eine Positivprobe deckt die Ausnahmen der Regel
  ab (Modulsegment im Import und als Attributkette, fremdes Objekt als `setattr`-Empfänger, `_`,
  unbekannter und öffentlicher Name).
- Der Rot-Lauf gegen den Ausgangsstand (leere Liste → volle Fundliste) ist der einmalige
  Mutationsbeleg für den Bestandspfad; die Snippets belegen die Zweige.

**AK5 — Anzahl und Aussage ohne Wortlaut-Test.** `pytest --collect-only -q` beider Stände
sortiert vergleichen: erwartete Differenz ist ausschließlich der neue Wächter und **genau ein**
zusätzlicher parametrisierter Fall `test_selection.py::…[worker/classification_review.py]`. Jede
übrige Knoten-ID bleibt identisch. Im `git diff --word-diff` über `backend/tests` ändert jede
Zeile nur einen Namen oder eine Importadresse aus der Zuordnungstabelle — keine
Assertion-Operanden, Literale, Zahlen, Fixtures oder Parametrisierungen.

**Mitziehende Wächter** (Namen als Zeichenketten): `test_worker_import_graph.py` (`_LAUF_DATEIEN`
+ `classification_review`, `_LAUF_EINSTIEGSPUNKTE` + `run_classification_review`,
`_ERLAUBTE_KANTEN`), `test_selection.py::_SELECTING_MODULES`, `test_models.py`
(`_ALLOWED_PHASE_WRITER_FUNCTIONS = {"set_phase"}`, `_ALLOWED_DECISION_MODEL_READERS` mit
`api/photos/_reads.py::final_selection_decisions`), `test_classification_review_isolation.py`,
`test_criterion_phases_standalone.py::_PHASEN` (sonst läuft `test_no_phase_names_another_phase`
gegen eine leere Schnittmenge still grün), `test_ausschuss_ueberlebende.py`,
`test_criterion_probe.py`, `tests/phase_binding.py`, `test_persons.py`.

**Abnahme:** vollständige Suite mit `--cov-fail-under=80`, `ruff check`, `ruff format --check`,
`mypy src`, Knotenmengen-Differenz, Wächter grün; dynamisch gerechnete Adressen (`getattr` mit
Variable, f-Strings) und relative Importe sind nicht messbar und bleiben Prüfkriterium im Review.

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
