# 0650 - Prüfungen eines Pull Requests unter fünf Minuten

**Status:** Accepted
**Erstellt:** 2026-11-23
**Bezug:** Issue [#650](https://github.com/TheRealKoller/photosort/issues/650)

## Ziel

Jeder Pull Request wartet heute 8–11 Minuten, bis alle automatischen Prüfungen durch sind (Median
der letzten grünen Läufe: `backend` 569 s, `e2e` 440 s, `docker-compose-check` 315 s, `frontend`
165 s). KI-Agenten und Daniel warten blockierend auf dieses Ergebnis, bis zu dreimal je Pull
Request. Ziel: Alle Prüfungen eines Pull Requests sind in unter 5 Minuten abgeschlossen, ohne dass
sie an Aussagekraft verlieren.

## User Story

Als Daniel und als Entwicklungs-Agent, der nach einem Push auf das Prüfergebnis wartet, möchte ich,
dass alle Prüfungen eines Pull Requests in unter 5 Minuten abgeschlossen sind, damit jede Merge- und
Nachbesserungsrunde weniger Wartezeit kostet, ohne dass ein grünes Ergebnis weniger aussagt als
heute.

## Akzeptanzkriterien

- [ ] **Ziel erreicht:** Die Zeit vom Start bis zum Abschluss der letzten Prüfung eines Pull
      Requests liegt unter 5 Minuten. Grundlage ist der Median aus mindestens 3 aufeinanderfolgenden
      Läufen unter vergleichbaren Bedingungen (vorhandene Caches). Vorher- und Nachher-Werte je
      Prüfung stehen im Pull Request.
- [ ] **Volle Testmenge:** Jede Prüfung führt weiterhin ihre gesamte Testmenge aus. Kein Test wird
      übersprungen, abgewählt oder nur noch gelegentlich ausgeführt. Die Menge der ausgeführten
      Testfälle ist vorher und nachher gleich, abgesehen von nachgewiesen gleichwertig ersetzten
      Fällen.
- [ ] **Zusicherungen bleiben:** Tests dürfen zur Beschleunigung umgebaut werden, etwa indem sie
      vorbereitete Testdaten teilen statt sie neu aufzubauen. Ein umgebauter Test prüft danach
      dasselbe Verhalten mit mindestens denselben Zusicherungen. Keine Zusicherung wird entfernt
      oder abgeschwächt. Zu jedem umgebauten Test nennt der Pull Request das geprüfte Verhalten.
- [ ] **Gate unverändert:** Die Abdeckungsschwelle von 80 % gilt unverändert für den gesamten
      Backend-Code. Ein Testfehler oder eine Unterschreitung macht die Prüfung weiterhin
      zuverlässig rot.
- [ ] **Alle Prüfschritte vollständig:** Formatierung, Lint, Typprüfung, Tests und End-to-End-Prüfung
      laufen weiterhin vollständig. Kein Schritt wird übersprungen, abgeschwächt oder nicht mehr
      blockierend gemacht.
- [ ] **Merge-Schutz bleibt:** Ein Merge ist weiterhin erst nach grünen Prüfungen möglich. Braucht
      das gewählte Verfahren dafür einen manuellen Schritt von Daniel, nennt der Pull Request diesen
      Schritt ausdrücklich. Bis er erledigt ist, ist der Schutz nicht schwächer als heute.
- [ ] **Lokal genauso:** Die Tests lassen sich weiterhin lokal mit derselben Testmenge und
      derselben Schwelle ausführen wie in den Prüfungen.

## Datenmodell-Bezug

Keiner. Reine CI-/Build-Konfiguration ohne Produktcode, Datenmodell oder sichtbare Oberfläche.

## Architektur / Umsetzung

Gewählter Ansatz: **Parallelisieren über Runner-Grenzen mit einem Aggregator je Required-Kontext**,
dazu **Image-Build-Cache** und eine **Fremdpaket-Schicht im Image ohne Quellcode-Abhängigkeit** —
festgehalten in ADR [`0151`](../decisions/0151-ci-unter-fuenf-minuten-shards-mit-einem-aggregator.md).
Kein Test wird umgebaut: Die Prüfmenge bleibt quelltextgleich, sie wird nur aufgeteilt. Die
Akzeptanzklausel „Tests dürfen umgebaut werden" wird nicht in Anspruch genommen.

**Required-Kontexte unverändert.** `backend` und `e2e` bleiben die Job-Schlüssel und werden zu
Aggregatoren: `needs` auf alle Shards, `if: always()`, ausdrückliche Prüfung
`needs.<job>.result == 'success'` → rot. Ein Matrix-Job mit dem Schlüssel `backend` hieße
`backend (1)`; der erforderliche Kontext bliebe leer. Die neuen Matrix-Schlüssel `backend-test` und
`e2e-shard` werden **nicht** in die Branch Protection eingetragen. **Kein manueller Schritt.**

**Backend.** `backend-test` als Matrix über `shard: [1, 2, 3, 4, 5, 6, 7, 8]`, `fail-fast: false`,
je Shard alle bisherigen Schritte (Systempakete, Modell-Assets, `uv`-Cache, Installation, ruff,
mypy) und der Testschritt

    pytest -n auto --cov=photosort --splits ${{ strategy.job-total }} --group ${{ matrix.shard }}
        --splitting-algorithm=least_duration

mit `COVERAGE_FILE=.coverage.shard-${{ matrix.shard }}` und **ohne** `--cov-fail-under`; danach
Upload des Coverage-Datensatzes (`coverage-shard-<n>`). Der Aggregator `backend` prüft die
Shard-Ergebnisse, lädt die Datensätze über ihre Namen, führt `coverage combine` aus und bewertet
`coverage report --show-missing --fail-under=80`. `coverage` kommt in der Version aus
`backend/uv.lock` — eine Quelle, kein zweiter Pin. Die Zerlegung stützt sich auf die committete
`backend/.test_durations` (`pytest --store-durations`); `least_duration` verteilt Tests einzeln nach
gemessener Dauer und hält die Testzahl je Shard gleich.

**e2e.** `e2e-shard` als Matrix über `shard: [1, 2]`; jeder Shard startet seinen eigenen
Compose-Prüfstack, seedet ihn und führt `npm test -- --shard=${{ matrix.shard }}/${{
strategy.job-total }}` aus. `workers: 1`, `retries: 0`, `forbidOnly: true` bleiben unverändert. Der
Aggregator `e2e` prüft die Shard-Ergebnisse. Die stackgebundenen statischen Nachweise
(Projektname, Portbindungen, Köder-`.env`) laufen in jedem Shard vor dem Stackstart.

**Images.** Neu `docker-compose.ci-cache.yml` (`build.cache_from`, Scope `photosort-images`) und
`docker-compose.ci-cache-write.yml` (`build.cache_to`, `mode=min`). Beide e2e-Shards und
`docker-compose-check` lesen; geschrieben wird nur in `docker-compose-check` und nur in Läufen, die
kein Fork-Pull-Request sind. Beide Jobs richten den Buildx-Builder ein
(`docker/setup-buildx-action`), weil `type=gha` den `docker-container`-Treiber verlangt. In
`docker-compose-check` ersetzen die Cache-Overlays das `--build` nicht: Gebaut wird weiterhin, nur
aus dem Cache.

**Backend-Image.** `backend/Dockerfile` wird geschichtet: apt-Pakete → `pyproject.toml` (und
`uv.lock` als Schichtschlüssel) → Modell-Manifest, Fetch-Skript und Asset-Download → Fremdpakete
aus `[project].dependencies` (per `tomllib`, `pip install -r`) → `src`, `alembic`, `scripts` →
`pip install --no-deps .`. Das Image löst weiterhin frisch aus `pyproject.toml` auf; ein
Lock-Refresh verwirft die Fremdpaket-Schicht.

**Betroffene Dateien**

| Datei | Änderung |
|---|---|
| `.github/workflows/ci.yml` | Matrix-Jobs `backend-test`/`e2e-shard`, Aggregatoren `backend`/`e2e`, Buildx-Setup, Cache-Overlays, Coverage-Upload/-Combine |
| `backend/Dockerfile` | Schichtung nach Entscheidung 5 der ADR |
| `docker-compose.ci-cache.yml`, `docker-compose.ci-cache-write.yml` (neu) | `cache_from`/`cache_to` für `backend`, `worker`, `frontend` |
| `backend/pyproject.toml`, `backend/uv.lock` | dev-Dependency `pytest-split` |
| `backend/.test_durations` (neu) | einmalig erzeugte Dauerdatei |
| `scripts/tests/test_ci_wirkung.py`, `mutationen.py`, `waechter_aussagen.json` | Gate-, Vollständigkeits-, Required-Kontext- und Cache-Invarianten |
| `scripts/tests/test_backend_lock_aktuell.py`, `test_signaturpruefung_je_paketsatz.py` | Job-Schlüssel abgeleitet statt literal |
| `specs/architecture/0002-testkonzept.md`, `0003-securitykonzept.md`, `docs/architecture.md` | Trägerangaben und Gate-/Cache-Zusagen |

**Messung (AC 1).** Je Job und je geändertem Schritt: `jobs[].started_at`/`completed_at` aus
`gh api repos/TheRealKoller/photosort/actions/runs/<id>/jobs`; Lauf-Gesamtzeit von `created_at` bis
`completed_at` des zuletzt fertigen Jobs. Median, Minimum und Maximum aus **drei aufeinanderfolgenden
Läufen desselben Commits** (`gh run rerun`) mit vorhandenen Caches; ein Kaltlauf wird getrennt
ausgewiesen. Vorher-Werte: dieselbe Methode auf den letzten zehn erfolgreichen `main`-Läufen.

## Teststrategie

**Vollständigkeit der Testmenge.** Backend: Mengengleichheit über Knoten-IDs, nicht nur Summen —
`pytest --collect-only -q` gesamt (heute 6677) gegen die Vereinigung der Shard-Listen; Schnitt leer,
Vereinigung vollständig. Im CI-Lauf ergänzend `passed+skipped` je Shard; der eine erwartete Skip
(`test_eye_mapping.py::test_every_photo_type_exists_in_eye_meta`) bleibt derselbe. e2e: Vereinigung
der `--list --reporter=json`-Ausgaben beider Shards gleich der Gesamtliste (138 Tests); der
gemeinsame `setup`-Fall (Anmeldung) ist der einzige Schnitt und gewollt, weil jeder Shard seinen
eigenen Sitzungszustand braucht.

**Äquivalenz des Gates.** Der Einzellauf (`pytest -n auto --cov=photosort --cov-report=term-missing
--cov-fail-under=80`) und die Vereinigung (`coverage combine`, dann `coverage report
--show-missing --fail-under=80`) müssen in Prozentwert, `Stmts`/`Miss`/`Cover` und `Missing`-Spalte
je Datei übereinstimmen; zusätzlich muss die Dateimenge der des Pakets entsprechen (heute 112 —
fehlt eine Datei, sinkt der Nenner und der Prozentwert steigt). **Sensitivitätsprobe:** dieselbe
Vereinigung ohne einen Shard-Datensatz muss den Prozentwert senken oder unter 80 fallen; bleibt er
gleich, trägt der fehlende Shard nichts bei, und das ist ein Befund.

**Wächter.** `coverage-schwelle` wird neu gefasst, nicht gelockert: jeder Backend-`pytest`-Schritt
sammelt Coverage (`--cov=photosort`) und trägt **keine** Schwelle; genau ein Schritt führt
`coverage combine` **und** `coverage report … --fail-under≥80`; sein Job trägt `if: always()`, prüft
die Shard-Ergebnisse und seine `needs`-Menge ist gleich der Menge der Jobs mit `pytest` (beide
Richtungen); kein `continue-on-error`. Neu `testmenge-vollstaendig` (kein Auswahlschalter `-k`,
`-m`, `--deselect`, `--ignore`, `--last-failed`, `--collect-only`, `-x`; `--splits`/`--group` aus
`strategy.job-total`/`matrix.shard`; Matrix lückenlos; Playwright `--shard` aus der Matrix, kein
`--grep`/`--project`) und `required-kontext-stabil` (die fünf geforderten Schlüssel existieren ohne
`name:`-Override; jeder Job mit Qualitätsbefehl ist geforderter Kontext oder liegt in der
`needs`-Hülle eines solchen). `cache-und-artefakte` trägt die Security-Auflagen (unten). Jede
Invariante bekommt in `scripts/tests/mutationen.py` mindestens einen herbeigeführten Verstoß;
gleichwertige Umformulierungen (`if: ${{ always() }}`, `needs` als Blockliste, `--splits=` ohne
Leerzeichen) bleiben grün.

**Lokal prüfbar.** Zerlegung über `--collect-only` (seiteneffektfrei), Gate-Äquivalenz und
Sensitivitätsprobe über die Shard-Läufe in `backend/`, Playwright-Zerlegung über `--list
--reporter=json --shard=k/2`. Nicht lokal prüfbar bleibt die GitHub-Semantik von `needs`/`always()`;
dafür einmalig der Rot-Nachweis am Pull Request (einen Test in einem Shard brechen → nur dieser
Shard rot, Aggregator rot, Merge blockiert; danach zurückgenommen).

**Nachweise vor der Messung.** Alle Matrix-Jobs und alle geforderten Kontexte grün, keiner
übersprungen; je Shard-Log `--group`/`--shard`-Wert und Testzahl; Aggregator-Log `Combined <n>
files` mit `<n>` gleich der Shard-Zahl; Summe der Testzahlen wie oben.

## UI/UX

nicht relevant — reine CI-/Build-Konfiguration ohne sichtbare Oberfläche; kein Frontend-Bezug, keine
Anzeige, keine Eingabe (Skip, Schritt 2).

## Security

**Sicherheitsrelevant: ja, ausschließlich über Lieferkette und Prüf-Integrität.** Kein
Anwendungscode, kein Endpunkt, keine neue Eingabe von außen, keine Änderung an Auth, Berechtigungen
oder Datensichtbarkeit. Neu ist, dass ein gebautes Artefakt (Image-Schichten) geteilter Zustand
eines öffentlichen Repositories wird und ein Required-Check über mehrere Jobs urteilt.

**Angriffsmodell.** Schützenswert ist die Integrität dessen, was läuft: das Homeserver-Image, der
CI-Runner (mit `GITHUB_TOKEN`, `contents: read`) und die Aussage des Merge-Gates `backend`/`e2e`.
Angreifer sind ein Fork-Pull-Request-Autor (öffentliches Repository, keine Secrets, lesendes Token),
ein untergeschobenes PyPI-Paket und ein fremder Cache-Export.

**Auflagen.**

1. **Image-Cache.** Geschrieben wird `type=gha` nur in Läufen, die kein Fork-Pull-Request sind — über
   eine `$GITHUB_ENV`-Bedingung, nicht über ein `if:` am Build-Schritt. Der Scope ist ein Literal.
   *Bei Verletzung* wanderte Ausgabe eines Fremd-Pull-Requests in den Cache, den `main` und spätere
   Pull Requests lesen, ohne dass ein Check rot würde. Wächter: `cache_to` nur hinter dem
   Fork-Ausschluss, Scope ohne `${{ }}`.
2. **Keine weiteren Rechte.** `permissions: contents: read` bleibt auf oberster Ebene, kein Job
   bekommt einen eigenen `permissions:`-Block, kein Qualitätsjob liest `secrets.*`, kein
   cachegebautes Image wird gepusht oder deployt, kein Cache-Treffer ersetzt eine Prüfung.
3. **Coverage-Artefakte.** Upload und Download nur im selben Workflow-Lauf:
   `actions/download-artifact` ohne `run-id`/`github-token`, kein `gh run download`; Namen enthalten
   nur Workflow-Literale und `matrix.*`. Der Gate-Entscheid hängt an den `needs`-Ergebnissen, nicht
   an den Daten. *Bei Verletzung* könnte ein grünes `backend` aus fremden Daten entstehen.
4. **Gate-Version.** `coverage` im Aggregator stammt aus `backend/uv.lock`, nie unpinned aus dem
   Index. *Bei Verletzung* könnte genau der Code, der grün/rot entscheidet, ohne Repo-Diff wechseln.
5. **Compose-Overlays.** Beide neuen Dateien sind additiv und inhaltsgeschlossen: nur
   `services.*.build.cache_from`/`cache_to`, nie `ports`, `environment`, `env_file`, `volumes`,
   `secrets`; nicht als `docker-compose.override.yml` benannt. Die e2e-Nachweise (Köder-`.env`,
   Portbindungen) laufen über den vollständigen `-f`-Verbund inklusive Cache-Overlays. *Bei
   Verletzung* zöge ein Overlay einen echten Token in einen Stack, der fremden PR-Code ausführt.
6. **Dockerfile.** Keine Secrets als `ARG`/`ENV`/`build.args`; die Modell-Assets werden weiterhin
   per SHA256 geprüft und vor dem finalen Projekt-Install geschrieben (sonst fehlen sie im
   installierten Paket).

**Bewusst getragene Restrisiken.** Der Image-Cache bleibt ein Beschleuniger ohne
Integritätszusage: Wer einen Branch im Repository beschreiben darf, kann Schichten vorgeben.
Getragen, weil kein konsumierender Job Secrets oder Schreibrechte hat und kein so gebautes Image
veröffentlicht wird; neu zu stellen, sobald ein Job das Image pusht, deployt oder mit Secrets
verwendet. Die Coverage-Daten sind PR-gesteuerter Input — das ist die vorbestehende Natur eines
Qualitätsgates. `pip install uv` bleibt ungepinnt (vorbestehend, außerhalb des Umfangs).

## Entscheidungen

- `architect` konsultiert (Schritt 1): konkreter Bezug zu `.github/workflows/ci.yml`, `docker-compose*.yml`,
   `backend/Dockerfile`, `backend/pyproject.toml` und den Workflow-Wächtern. Ergebnis: ADR `0151`.
- `ux-ui-designer` nicht konsultiert (Schritt 2): keine sichtbare Oberfläche, kein Frontend-Bezug;
  die Story ändert ausschließlich CI- und Build-Konfiguration.
- `test-engineer` konsultiert (Schritt 3): Vollständigkeitsnachweis über Knoten-IDs, Gate-Äquivalenz
  mit Sensitivitätsprobe, Wächter-Mutationen, Aktualisierung von `0002-testkonzept.md`.
- `security-engineer` konsultiert (Schritt 3): lieferte das Angriffsmodell, die Auflagen 1–6 und die
  Ergänzungen zu `0003-securitykonzept.md`.
- **Acht Backend-Shards, kein apt-Paket-Cache.** Die Fixkosten je Shard (~105 s) dominieren die
  Testzeit, deshalb trägt die Zahl der Shards die Reserve: lokal gemessene Gruppen 25–32 s
  (Maximum/Mittel 1,14) gegenüber 54–72 s bei fünf Gruppen. Die Shard-Zahl bleibt eine Zeile, weil
  alle Ableitungen über `strategy.job-total` laufen; der apt-Cache ersetzt sie nicht und bringt
  einen zweiten Fehlerpfad.
- **`least_duration` statt `duration_based_chunks`.** Beide balancieren die gemessene Dauer, aber
  `least_duration` hält zusätzlich die Testzahl je Shard gleich; die Zerlegung in zusammenhängende
  Blöcke erzeugte Gruppen mit 153 und 3577 Tests bei gleicher Dauersumme.
- **Kein Test umgebaut.** Die Beschleunigung kommt aus Zerlegung und Cache; die Klausel zu
  umgebauten Tests bleibt ungenutzt.
- **Kein manueller Branch-Protection-Schritt.** `backend` und `e2e` bleiben die geforderten
  Kontexte; sie sind nach dem Umbau die Aggregatoren.

## Offene Fragen

- **Shard-Balance:** Bleibt der langsamste Shard unter dem 1,15-fachen des Mittels? Beleg im ersten
  Lauf; falls nicht, wird nur `backend/.test_durations` neu erzeugt.
- **Zustandsfreiheit der e2e-Specs über Dateigrenzen:** Keine Spec-Datei darf auf den Zustand einer
  anderen bauen. Der erste Shard-Lauf belegt es; andernfalls wird die e2e-Zerlegung zurückgenommen,
  und AC 1 ist mit diesem Verfahren nicht erfüllt — dann ist die Spec zu ändern, nicht die
  Zusicherung.
- **GHA-Cache-Quote (10 GB):** Reicht `mode=min` für beide Images dauerhaft neben dem uv- und dem
  Modell-Cache? Beobachtung im ersten Lauf; bei Verdrängung fällt der Median auf den Kaltfall.

## Out of Scope

- Behebung der Pillow-Deprecation-Warnungen.
- Aufteilung der Produktionsmodule (#647) und der Testdateien (#651); beide berühren dieselben
  Testdateien und laufen nicht parallel zu dieser Story.
- Ein automatisches Zeitbudget als eigene Prüfung.
- Das Agenten-Wartefenster in `github-access` (`pr-pruefstand-abwarten`) bleibt bei 15 Minuten; die
  Story ändert die Laufzeit, nicht die Warte-Obergrenze.
