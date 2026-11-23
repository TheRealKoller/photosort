# 0651 - Testdaten an einer Stelle pflegen, Tests je Thema ausführen

**Status:** Accepted
**Erstellt:** 2026-11-22
**Bezug:** Issue [#651](https://github.com/TheRealKoller/photosort/issues/651)

## Ziel

Testdaten und Attrappen sind an genau einer Stelle pflegbar; große Testdateien sind je Thema
getrennt und allein lauffähig, ohne dass ein Testfall oder eine Zusicherung verloren geht.

## User Story

Als Entwickler von PhotoSort möchte ich Testdaten, Attrappen und die Testumgebung an genau einer
Stelle ändern können und die Tests eines Themas in einer überschaubaren, allein lauffähigen Datei
vorfinden, damit ich Änderungen ohne Nachziehen an dutzenden Stellen umsetzen kann, ein gezielter
Lauf nicht das ganze Fachgebiet einsammelt und sich zwei Änderungen an verschiedenen Themen nicht in
derselben Riesendatei in die Quere kommen.

## Akzeptanzkriterien

- [ ] **Eine Definition je Baustein, keine divergierenden Kopien.** Von jedem heute mehrfach
  ausgeschriebenen Testbaustein gibt es genau eine Definition. Ausgangsstand: Projektaufbau 18
  Definitionen in 18 Dateien, Fotoaufbau 16 in 15, Auftrags-Auslöser-Doppelgänger 6 in drei
  unterschiedlich ausgestatteten Fassungen, OpenCloud-Doppelgänger 5; im Frontend Foto-Testobjekt
  26-mal, Projekt-Testobjekt 14-mal, Testumgebung 72-mal in 54 Dateien. Jede Abweichung zwischen
  bisherigen Aufrufern wird ein Parameter der einen Definition; unterschiedlich ausgestattete
  Fassungen desselben Doppelgängers werden zu einer zusammengeführt, die alle bisherigen Zusagen trägt.
- [ ] **Auffindbarkeit ohne Suche.** Die verbindliche Testkonvention nennt für Backend und Frontend je
  genau eine Fundstelle gemeinsamer Testbausteine; jeder der genannten Bausteine liegt dort, ein neuer
  gehört dorthin. Die Konvention enthält danach keine Regel mehr, die eine Kopie je Testdatei verlangt
  (Projektgraph-Aufbau „in einer Hilfsfunktion der Testdatei"; im Frontend „kleine, literale
  Testobjekte pro Testdatei"). Was dateilokal bleibt — inhaltliche Zusicherungen, tabellenweise
  ausgeschriebene Erwartungen —, ist dort ausdrücklich benannt.
- [ ] **Große Testdateien sind je Thema aufgeteilt und allein lauffähig.** Geteilt sind die vier
  größten Backend-Dateien (Bewertungs-Pipeline 7.243, Foto-API 7.153, Ereignisse 3.884, Demo-Zustand
  3.210) und die drei größten Frontend-Dateien (Design-Vertrag 2.490, Foto-Detail 2.109, Album-Entwurf
  1.761). Zielwert: keine Backend-Datei über 1.500, keine Frontend-Datei über 1.000 Zeilen; Ausnahmen
  (etwa eine einzige tabellenweise Erwartung) sind im Pull Request begründet. Jede entstandene Datei
  trägt ihr Thema im Namen, läuft für sich allein grün und braucht keine Vorbereitung, Attrappe oder
  Basisklasse aus einer Schwesterdatei. Ein gezielter Lauf sammelt nur die Testfälle seines Themas ein.
- [ ] **Testbestand und Testaussage unverändert.** Die Zahl eingesammelter Testfälle ist vor und nach
  dem Umbau identisch (Backend heute 6.443), alle laufen grün, die Abdeckung bleibt ≥ 80 %, kein
  Testfall wird gelöscht, übersprungen oder als erwarteter Fehlschlag markiert — die eine bestehende
  Auslassung bleibt die einzige. Keine Zusicherung wird abgeschwächt.
- [ ] **Die Design-Vertragsprüfung prüft danach dasselbe.** Dieselben Regeln gegen dieselbe Dateimenge,
  dieselben Fundstellen. Die Positiv-Gegenprobe bleibt nicht leer; jede entstandene Datei, die die
  Suchmuster als Literale trägt, ist als eigene Fundstelle ausgenommen — eine Ausnahme über ein Muster,
  das alle Teile still freistellt, gilt als nicht abgeschlossen.
- [ ] **Verweise außerhalb des Testbaums bleiben gültig.** Keine der rund 415 Stellen in
  Produktivcode-Docstrings, Migrationen, `docs/` und `specs/`, die auf eine aufzuteilende Testdatei
  verweist, zeigt danach ins Leere; wo sie einen Testknoten nennt, nennt sie einen existierenden.
- [ ] **Grenzen respektiert.** Produktionsverhalten unverändert — Produktivcode nur in
  Verweiskommentaren. Kein Testfall gelöscht, `scripts/tests` und der GitHub-Katalog unberührt, und
  die neuen Bausteine greifen nicht öfter auf produktionsinterne Symbole zu als heute.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

Messung am Bestand (2026-11-22): 183 Backend-Testdateien / 111.811 Zeilen, 171 Frontend-Testdateien /
47.621 Zeilen. `scripts/tests` verweist auf keine der sieben aufzuteilenden Dateien — der
Konfliktfall „Umbau macht das Regelwerk ungültig" besteht nicht. Die Einsammelzahl (`pytest
--collect-only -q`, vitest) wird vor dem ersten Commit festgehalten und nach jedem Teil verglichen.

**Backend — eine Fundstelle: `backend/tests/support/`** (Paket, nicht `conftest.py`: reine
Fabrikfunktionen werden importiert, Fixtures bleiben in `conftest.py`). Duplikate am Bestand:

| Baustein | heutige Namen (Dateien) | Ziel in `support/` |
|---|---|---|
| Projekt | `_make_project` (18), `_project` (21), `_create_project` (4) | `make_project(session, *, name=…, …)` |
| Foto | `_add_photo` (13), `_photo` (17), `_make_photo` (7) | `add_photo(session, project, …)` |
| Nutzer | `_user` (10), `_make_user` (4) | `make_user` |
| Lauf | `_successful_run` (7), `_add_run` (3), `_add_successful_scoring_run` (3) | `add_run`, `add_successful_run` |
| Anzeigebild | `_write_display_variant` (3) | `write_display_variant` |
| OpenCloud-Eintrag/-URL | `_entry` (7), `_url` (8) | `opencloud_entry`, `opencloud_url` |
| Migrationen | `_create_pre_migration_schema` (38), `_load_migration_module` (36), `_apply` (32), `_apply_upgrade`/`_apply_downgrade` (6) | `migration_harness` |

Form: Fabrikfunktion mit Schlüsselwort-Parametern. Jede Abweichung zwischen den Aufrufern (Pfad,
Kennung, Schalter) wird ein Parameter mit dem Wert des häufigsten Aufrufers als Vorgabe. Vor dem
Zusammenführen wird je Gruppe der Vergleich der Fassungen festgehalten; ein Aufrufer, dessen Fassung
mehr tut (z. B. Auslöser-Doppelgänger mit zusätzlichem Verhalten), bekommt dieses Verhalten als
Parameter, nie als stillen Unterschied. Aufrufer wechseln mechanisch (`ast-grep`/Import-Umstellung);
der Testkörper bleibt unverändert, damit keine Zusicherung berührt wird.

**Frontend — eine Fundstelle: `frontend/src/test/`** (besteht bereits mit `motifSetFixture.ts`,
`projectStateSpace.ts`). Neu: `fixtures.ts` (`makePhoto`, `makeProject` mit Überschreibung per
Teilobjekt) und `render.tsx` (Testumgebung: `QueryClientProvider` + Router, 54 Dateien tragen
`QueryClientProvider`, 21 definieren `renderPage`/`renderWith…`).

**Testkonvention (`specs/architecture/0002-testkonzept.md`)** im selben PR: Zeile 1176 („kleine,
literale Testobjekte pro Testdatei", `fixtures.ts`-Vorbehalt) und Zeile 165 („Hilfsfunktion der
Testdatei") werden ersetzt durch: Bausteine in `backend/tests/support/` bzw. `frontend/src/test/`;
dateilokal bleiben inhaltliche Zusicherungen und tabellenweise ausgeschriebene Erwartungen.
Historisch gewachsene Erwähnungen von `_make_project`-Kopien in anderen Konzeptabschnitten werden
bei Berührung angepasst, nicht flächig umgeschrieben. `docs/architecture.md` ändert sich nur, wenn
dort ein Testverzeichnis beschrieben ist.

**Aufteilung (Schritt 2)** entlang der Themen der Produktionsmodule; Dateiname = Thema. Beispiele:
`test_api_photos_*.py` → `test_api_photos_list.py`, `…_detail.py`, `…_curation.py`, `…_display.py`;
`test_worker_criterion_scoring_*.py` → je Kriterium/Phase. Der genaue Schnitt ergibt sich aus den
`class Test…`-Gruppen und `# ---`-Abschnitten der Dateien; Testklassen wandern vollständig. Alles
Gemeinsame, das nach dem Schnitt in zwei Teilen gebraucht wird, geht nach `support/`, nie in eine
Schwesterdatei. Frontend: `designSystem.*.contract.test.ts` je Regelgruppe; Suchmuster-Literale tragende
Teile stehen einzeln in der Ausnahmeliste (Selbstausnahme je Datei, kein Glob über alle Teile);
`PhotoDetailPage.*.test.tsx` und `AlbumDraftPage.*.test.tsx` je Bereich der Seite.

**Verweise:** Fundstellen über `rg` auf die sieben Dateinamen (und `Klasse::test`-Knoten) in
`backend/src`, `backend/alembic`, `docs`, `specs`, `.claude`, `.omp`, `frontend/src`; 115 Dateien
treffen. Jeder Verweis wird auf die neue Datei umgeschrieben. Abgeschlossene Specs
(`Implemented`) werden nur an der Verweisstelle korrigiert — das ist keine Kürzung nach `CLAUDE.md`,
sondern Wahrung der Gültigkeit.

**Reihenfolge:** (1) Einsammelzahl messen, (2) `support/` + `frontend/src/test/` + Konvention,
Aufrufer umstellen (Test grün), (3) Aufteilung Datei für Datei, je Datei Einsammelzahl- und
Knotenvergleich (Knotenmenge vorher/nachher gleich bis auf den Dateinamen), (4) Verweise, (5)
Gesamtlauf mit Coverage. Keine ADR: keine neue Technologie, kein neues Datenmodell.

## UI/UX

Nicht relevant: ausschließlich Testcode, keine sichtbare Oberfläche.

## Security

Nicht relevant: keine Eingabe von außen, keine Auth-/Secret-/Berechtigungsstelle, kein Datenmodell,
keine Datensichtbarkeit; Produktivcode nur in Kommentaren.

## Teststrategie

Der Umbau ist selbst das Testobjekt; die Gegenprobe ist mechanisch:

- Knotenmenge `pytest --collect-only -q` / `vitest list` vor und nach: gleiche Zahl, gleiche Namen
  (bis auf den Dateinamen), keine neuen `skip`/`xfail`.
- Jede entstandene Datei läuft einzeln grün (`pytest <datei>`, `vitest run <datei>`).
- Je zusammengeführtem Baustein: ein Aufrufer mit der Abweichung läuft gegen den Parameter statt
  gegen die Kopie; kein Test des Bausteins selbst, solange er reine Datenerzeugung ist.
- Design-Vertrag: Positiv-Gegenprobe bleibt nicht leer; Ausnahmeliste nennt jede Teildatei einzeln.

## Entscheidungen

- `architect` nicht erfragt: der Subagenten-Aufruf scheiterte infrastrukturell (`401 API key
  required`), kein inhaltlicher Grund; der Abschnitt „Architektur / Umsetzung" stammt aus der
  Messung der Hauptsession und ist beim Review gegen den Bestand zu prüfen.
- `ux-ui-designer` nicht konsultiert (Schritt 2): ausschließlich Testcode ohne Oberfläche.
- `test-engineer` nicht konsultiert (Schritt 3): derselbe Subagenten-Ausfall; die Teststrategie
  folgt dem Issue (Einsammelzahl, Einzellauf) und ist mechanisch prüfbar.
- `security-engineer` nicht konsultiert (Schritt 3): kein Sicherheitsbezug (siehe Abschnitt).
- Fundstellen `backend/tests/support/` und `frontend/src/test/` sind technische Detailentscheidung
  innerhalb der Spec.

## Offene Fragen

Keine.

## Out of Scope

- Löschen oder Lockern der Prüfungen unter `scripts/tests`.
- Laufzeit-Optimierung der Testvorbereitung.
- Aufteilen von Produktionsmodulen.
