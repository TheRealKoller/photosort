# 0151 - CI unter fünf Minuten: Shards mit einem Aggregator je Required-Kontext, Image-Build-Cache und eine Fremdpaket-Schicht ohne Quellcode-Abhängigkeit

**Status:** Accepted
**Datum:** 2026-11-23
**Bezug:** Issue [#650](https://github.com/TheRealKoller/photosort/issues/650), Spec [`../features/0650-ci-unter-fuenf-minuten.md`](../features/0650-ci-unter-fuenf-minuten.md)
**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Rechnung je Job, die Aggregator-Semantik und die verworfene apt-Alternative je in voller Aussage stehen.

## Kontext

Ein Pull Request wartet im Median 569 s auf die letzte Prüfung (Grenze: 300 s). Zwei Jobs bestimmen
die Dauer: `backend` (Median 569 s, davon 512 s `pytest` bei `-n auto` auf vier Kernen) und `e2e`
(Median 440 s, davon 206 s Image-Bau und Stackstart, 161 s Browserprüfung). Dazu
`docker-compose-check` (Median 315 s, davon 212 s Image-Bau) und `frontend` (Median 165 s). Der
Testbestand ist seit der letzten Beschleunigung mehr als viermal gewachsen; die Parallelisierung im
selben Job ist ausgereizt. Jede Beschleunigung muss die volle Testmenge, die Coverage-Schwelle von
80 % auf dem gesamten Backend-Code und die Blockierwirkung der Prüfungen unangetastet lassen.

## Entscheidung

### 1. Der Required-Kontext bleibt der Job-Schlüssel; die Arbeit wandert in Matrix-Jobs

`backend` und `e2e` werden Aggregatoren: `needs` auf alle Shards, `if: always()`, ausdrückliche
Prüfung `needs.<job>.result == 'success'` → rot. Die Arbeit liegt in den Matrix-Jobs `backend-test`
(5 Shards) und `e2e-shard` (2 Shards), die nicht erforderlich sind.

Grund: Der Check-Name eines Jobs ist sein Schlüssel. Ein Matrix-Job mit dem Schlüssel `backend`
hieße `backend (1)`; der Required-Kontext `backend` bliebe auf „Expected" stehen und jeder Merge
blockiert. Ohne `if: always()` würde ein Aggregator bei einem gescheiterten Shard übersprungen, und
ein übersprungener Job erfüllt keine Required-Prüfung — der Fehlschlag wäre unsichtbar. Mit
`always()` wird der Aggregator ausdrücklich rot.

### 2. Backend: acht Shards, Gate auf dem zusammengeführten Stand

Jeder Shard führt `pytest -n auto --cov=photosort --splits ${{ strategy.job-total }} --group
${{ matrix.shard }} --splitting-algorithm=least_duration` mit eigenem
`COVERAGE_FILE=.coverage.shard-<n>` und **ohne** Coverage-Schwelle. Die Zerlegung stammt aus der
committeten Dauerdatei `backend/.test_durations`; `least_duration` verteilt Tests einzeln nach
gemessener Dauer und hält zusätzlich die Testzahl je Shard gleich. Die Aggregator-Stufe führt
`coverage combine` und `coverage report --show-missing --fail-under=80` auf der Vereinigung aller
Shard-Daten aus.

Acht Shards statt vier oder fünf: Ein Shard kostet gemessene Fixkosten von rund 105 s
(Systempakete, Abhängigkeiten, Modell-Assets, mypy); die Testzeit je Shard fällt mit der Zahl. Bei
fünf Shards trug der langsamste lokal 26,5 % statt 20 % der Testzeit und landete damit dicht an der
Grenze, weil der CI-Runner rund 2,4-mal langsamer ist als der Entwicklungsrechner. Bei acht Shards
liegen die gemessenen Gruppen bei 25–32 s (Maximum/Mittel 1,14); das ergibt je Shard rund 75–80 s
Testzeit auf CI — und damit Reserve ohne einen weiteren Mechanismus.

### 3. e2e: zwei Shards mit je eigenem Prüfstack

`npm test -- --shard=${{ matrix.shard }}/${{ strategy.job-total }}`. Jeder Shard startet seinen
eigenen Compose-Prüfstack und seedet ihn selbst; `workers: 1`, `retries: 0`, `forbidOnly: true`
bleiben unverändert und bleiben per Assertion in `e2e/tests/toolchain.spec.ts` gebunden. Das
`setup`-Projekt läuft in jedem Shard, weil jeder Shard seinen eigenen Anmeldezustand braucht.

### 4. Images: Buildx-Cache nach `type=gha`, ein Schreiber

Neu entstehen `docker-compose.ci-cache.yml` (`cache_from`, Scope `photosort-images`) und
`docker-compose.ci-cache-write.yml` (`cache_to`, `mode=min`). Gelesen wird der Cache von beiden
e2e-Shards und von `docker-compose-check`; geschrieben **nur** von `docker-compose-check`, und nur
in Läufen, die kein Fork-Pull-Request sind. Ein Schreiber je Lauf verhindert konkurrierende
Exporte; die Fork-Bedingung hält fremde Pull-Request-Läufe aus dem Cache, den `main` und spätere
Pull Requests lesen. Beide bauenden Jobs richten den Buildx-Builder ein
(`docker/setup-buildx-action`), weil `type=gha` den `docker-container`-Treiber verlangt.

### 5. Das Backend-Image trennt Fremdpakete vom Quellcode und trägt ein Profil

Das Profil (`PHOTOSORT_PROFILE`) trennt das Produktionsimage (`full`) vom e2e-Prüfimage (`slim`):
`slim` lässt TensorFlow weg (~600 MB, NIMA-Ästhetik des Workers), weil die Oberflächenprüfung
keine Klassifizierung ausführt. MediaPipe, OpenCV und die Modell-Assets bleiben: die API bietet
die Gesichtserkennung für „Ohne Namen" an, und die e2e-Specs rufen sie auf. Das Produktionsimage baut und prüft weiterhin `docker-compose-check`. Der
Grund ist die Größe: 1,7 GB gegen 0,95 GB entscheiden über den Cache-Import je e2e-Shard.

`backend/Dockerfile` kopiert vor der Fremdpaket-Schicht nur `pyproject.toml` — und `uv.lock` als
Schichtschlüssel, nicht als Installationsquelle: `pip install -r /tmp/requirements.txt` (aus
`[project].dependencies` per `tomllib`) hängt damit nicht an `src/`. Ein Lock-Refresh verwirft die
Schicht; das Image löst weiterhin frisch aus `pyproject.toml` auf. Die Modell-Assets bekommen eine
eigene Schicht aus Manifest und Fetch-Skript; `src`, `alembic` und `scripts` folgen danach, dann
`pip install --no-deps .`.

Grund: Ohne diese Trennung invalidiert jede Quellcode-Änderung die teure Installationsschicht, und
der Image-Cache brächte im Regelfall nichts — `src/` steht heute vor `pip install .`.

### 6. Kein apt-Paket-Cache

Ein Cache der fünf Systempakete spart rund 30 s je Backend-Shard, verlangt aber einen weiteren
Mechanismus mit eigenem Fehlerpfad (Teiltreffer, veralteter Paketindex). Die achte Shard-Gruppe
schafft dieselbe Reserve ohne ihn; die Fixkosten je Shard laufen parallel und tragen nicht zur
Gesamtdauer bei.

## Begründung

- **Rechnung statt Hoffnung:** Backend je Shard rund 105 s Fixkosten + 512 × 0,15 ≈ 77 s Testzeit =
  ~182 s, Aggregator ~25 s → ~207 s. e2e je Shard ~60 s Fixkosten + ~60 s Stack (warmer
  Image-Cache) + ~90 s Browser = ~210 s, Aggregator ~5 s. `docker-compose-check` ~100 s Restarbeit
  + ~60 s Bau/Start = ~160 s. Der Median des Gesamtlaufs liegt damit bei rund 230 s, die übrigen
  Jobs bleiben darunter (frontend 165 s).
- **Keine Prüfung wird abgewählt:** Kein Shard trägt `-k`, `-m`, `--deselect`, `--ignore`,
  `--last-failed` oder einen Playwright-Selektor. Die Shard-Zahl kommt aus
  `strategy.job-total`, die Matrix ist lückenlos; die Summe der gesammelten Tests ist der Nachweis.
- **Das Gate wird strenger, nicht schwächer:** Die 80-%-Schwelle gilt jetzt auf der Vereinigung
  aller Shard-Daten statt auf einem Lauf und liegt in einem Job, der bei jedem Shard-Fehlschlag rot
  wird — zusätzlich zur Testmenge, die jeder Shard selbst ausführt.
- **Der Cache beschleunigt, er entscheidet nicht:** Kein Schritt überspringt eine Prüfung bei
  Cache-Treffer; die funktionalen Checks bauen, starten und prüfen weiterhin.

## Verworfene Alternativen

- **Nur schnellere Ausführung im bestehenden Job** (apt-Cache, `COVERAGE_CORE=sysmon`): 512 s
  `pytest` bleiben; die Grenze ist damit nicht erreichbar.
- **Größere oder bezahlte Runner:** Kosten ohne Notwendigkeit; die Shard-Rechnung erreicht das Ziel
  auf den freien Runnern, und Runner-Minuten sind bei öffentlichem Repository nicht der Engpass.
- **Registry-Cache (GHCR) statt GHA-Cache:** bräuchte `packages: write` (heute nur `contents: read`),
  einen Schreibpfad für Fork-Pull-Requests und einen neuen externen Zustand.
- **e2e ohne Zerlegung:** rund 280 s Median mit 144–197 s Streuung im Browserteil — keine Reserve
  gegen die 300-s-Grenze.
- **e2e mit mehr Playwright-Workern:** bricht das Verlässlichkeitsregime (`workers: 1`) und die
  geteilte Seed-Basis; Parallelität über Dateigrenzen wäre ein anderer Testaufbau, nicht eine
  Zerlegung.
- **Coverage-Gate je Shard:** würde 80 % auf einer Teilmenge messen — eine falsche Aussage.
- **Matrix-Job mit dem Schlüssel `backend`:** Check-Name `backend (1)`, Required-Kontext verfehlt,
  jeder Merge blockiert (siehe Entscheidung 1).
- **apt-Paket-Cache:** siehe Entscheidung 6.

## Konsequenzen

- Neu: dev-Dependency `pytest-split` (`backend/pyproject.toml`, `backend/uv.lock`), committete
  `backend/.test_durations`, `docker-compose.ci-cache.yml`, `docker-compose.ci-cache-write.yml`;
  umgebaut: `.github/workflows/ci.yml`, `backend/Dockerfile`; angepasst: die Wächter unter
  `scripts/tests/` und `specs/architecture/0002-testkonzept.md`.
- Mehr parallele Jobs je Lauf (6 → 16), mehr Runner-Minuten; bei öffentlichem Repository ohne
  Kosten und unter dem Nebenläufigkeitslimit von 20 gleichzeitigen Jobs.
- Ein kalter Image-Cache kostet im e2e-Job rund 90 s zusätzlich (erster Lauf nach einem
  Lock-Refresh); der Median gilt bei vorhandenen Caches und wird so gemessen.
- Lokal unverändert: `pytest -n auto --cov=photosort --cov-report=term-missing
  --cov-fail-under=80` prüft weiterhin die gesamte Menge und dieselbe Schwelle. Die Zerlegung ist
  ein CI-Verfahren; `--splits`/`--group` sind lokal nur zur Nachprobe nötig.
