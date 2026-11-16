# 0655 - Backend-Abhängigkeiten festgehalten, Dokumentnamen ohne Sonderzeichen

**Status:** Accepted
**Erstellt:** 2026-11-16
**Bezug:** Issue [#655](https://github.com/TheRealKoller/photosort/issues/655)

## Ziel

`backend/uv.lock` liegt heute nur auf dem Entwicklungsrechner: CI und jeder frische Klon lösen die
Backend-Abhängigkeiten neu auf. Zugleich trägt eine Feature-Spec einen Umlaut im Dateinamen und
wird dadurch in zwei Schreibweisen zitiert — zehn Verweise treffen, fünf zeigen ins Leere.

Nach dieser Story liegt die aufgelöste Backend-Abhängigkeitsmenge versioniert im Repository, und
jeder Dokumentname in den Nummernräumen ist ohne Sonderzeichen. Ein Stand zieht überall dieselben
Pakete, und ein Verweis trifft auf jedem System dieselbe Datei.

## User Story

Als wer am Projekt arbeitet — Mensch wie Agent, auf dem Entwicklungsrechner, auf dem CI-Runner
oder auf einem frischen Klon — möchte ich, dass die aufgelöste Backend-Abhängigkeitsmenge
versioniert im Repository liegt und jede Spec- und Entscheidungsdatei einen Namen ohne Umlaute
trägt, damit ein Stand überall dieselben Pakete zieht und ein Verweis auf ein Dokument auf jedem
System auf dieselbe Datei trifft.

## Akzeptanzkriterien

- [ ] **Die Auflösung ist festgehalten, ohne das Installationsverfahren zu ändern.** Ein frischer
      Stand bringt exakt die aufgelöste Backend-Abhängigkeitsmenge mit, statt sie neu zu ermitteln.
      Kein Prüfschritt wird dabei ersetzt, abgeschwächt, übersprungen oder nicht-blockierend
      gestellt, und kein Lauf scheitert durch die Aufnahme.
- [ ] **Die festgehaltene Auflösung gehört zum deklarierten Satz.** Sie ist aus den deklarierten
      Abhängigkeiten erzeugt, nicht von Hand bearbeitet; ein erneutes Erzeugen ohne Änderung am
      deklarierten Satz erzeugt keinen inhaltlichen Unterschied. Ändert jemand den deklarierten
      Satz, zieht die Auflösung im selben Zug nach.
- [ ] **Kein Dokument behauptet mehr das Gegenteil.** Keine Stelle im Bestand sagt noch, es gebe
      keine Lockdatei oder die Versionsangabe in den Manifesten sei die einzige Fixierung. Die
      Korrektur geschieht als datierter Nachtrag, ohne den Entscheidungstext umzuschreiben; was
      durch das Einchecken **nicht** behoben ist — die Installation prüft weiterhin keinen
      Integritäts-Hash —, bleibt als Lücke benannt.
- [ ] **Der Sonderzeichen-Name ist ersetzt, der Inhalt unberührt.** Die betroffene Spec liegt unter
      einem Namen ohne Umlaute und ohne sonstige Sonderzeichen; Nummer, Titel, Status und Inhalt
      bleiben unverändert, und die Versionshistorie führt über die Umbenennung hinweg weiter —
      keine Löschung mit anschließender Neuanlage.
- [ ] **Kein Verweis zeigt ins Leere, die Nummernprüfungen bleiben unverändert grün.** Nach der
      Umbenennung nennt jede Fundstelle den neuen Namen — auch die fünf, die heute schon ins Leere
      zeigen und dadurch wieder treffen. Die Nummernprüfungen laufen grün ohne gelockerte
      Zusicherung, ohne Ausnahmeliste, ohne gelöschten oder übersprungenen Test; wo eine Aussage im
      Bestand den alten Zustand behauptet (etwa die Testdokumentation, „genau ein solcher Name
      liegt im echten Bestand“), ist sie auf den neuen Zustand gebracht, nicht gestrichen.
- [ ] **Die Namenskonvention schließt die Lücke dauerhaft.** Die dokumentierte Konvention für Specs
      und Entscheidungen verlangt Dateinamen ohne Umlaute und Sonderzeichen; ein neuer Verstoß
      fällt auf, statt sich unbemerkt einzureihen.
- [ ] **Keine Lockdatei bleibt unbeabsichtigt liegen.** Nach der Umsetzung ist jede Lockdatei im
      Baum entweder versioniert oder bewusst ausgenommen; es bleibt keine still entstandene Datei
      dieser Art im Arbeitsbaum stehen.

**Umfang:** über dem Richtwert von ~200 Zeilen, weil zwei getrennte Gegenstände — der
Lockfile-Weg in CI und lokal samt drei Wächtern sowie die dauerhafte Namensprüfung samt
Umbenennung — zusammen mit den Doku- und Sicherheitspflichten in einer Spec stehen.

## Datenmodell-Bezug

Keiner: Die Story ändert weder Entitäten noch Migrationen noch die Systemarchitektur.

## Architektur / Umsetzung

**Bezug:** ADR [`0137`](../decisions/0137-backend-ci-beschleunigung-pytest-xdist-und-uv-cache.md),
ADR [`0080`](../decisions/0080-maschinelle-formatierung-ruff-format-und-prettier.md),
[`docs/setup.md`](../../docs/setup.md), [`specs/README.md`](../README.md). **Keine neue ADR.**

### Ausgangslage

`backend/uv.lock` existiert, ist heute untracked und hält 112 Pakete universell fest (eine
Auflösung, mehrere Marker-Äste für Python-Versionen). Die `uv pip`-Schnittstelle liest kein
Lockfile; Projektmodus gibt es nur bei `uv lock`, `uv sync` und `uv export`. Der bestehende
`.venv`-Stand stimmt mit dem Lock überein (`uv sync --locked --extra dev --dry-run`: „Would make no
changes“) — die Aufnahme ändert keinen Paketstand.

### Eine Quelle, zwei Umgebungsformen

**CI-Job `backend`** (`.github/workflows/ci.yml`, Schritt `Install dependencies` — Name und
Position bleiben, nur der `run:`-Rumpf wächst):

```yaml
      - name: Install dependencies
        run: |
          uv export --locked --extra dev --no-hashes --no-emit-project \
            -o "$RUNNER_TEMP/backend-requirements.txt"
          uv pip install --system --no-deps \
            -r "$RUNNER_TEMP/backend-requirements.txt" -e .
```

**Lokal** (`docs/setup.md`, derselbe Satz, andere Umgebungsform):

```bash
(cd backend && uv sync --locked --extra dev)
```

Nach jeder Änderung an `backend/pyproject.toml` gehört `(cd backend && uv lock)` dazu, und
`backend/uv.lock` in denselben Commit.

`uv export` erzeugt aus dem Lock eine Liste exakt gepinnter Anforderungen; `--no-deps` verhindert,
dass `uv pip` beim Installieren des Projekts erneut auflöst. `--locked` (nicht `--frozen`) bricht
ab, wenn Manifest und Lock auseinanderlaufen. `uv sync` scheidet für CI aus: Es arbeitet im
Projektmodus, legt `.venv` an, und alle vier Prüfschritte müssten auf `uv run` umgestellt werden —
genau das verbietet AK1.

**Verworfen:** unveränderter Installationsschritt (CI löst weiter neu auf; AK1 nur kosmetisch
erfüllt) und Export mit Hashes/`--require-hashes` (Hashprüfung ist außerhalb des Umfangs).

**Docker bleibt unverändert:** `backend/Dockerfile` (`pip install --no-cache-dir .`) löst weiterhin
frisch aus `pyproject.toml` auf — eine benannte Lücke. Die Exportdatei entsteht nur in
`$RUNNER_TEMP` bzw. gar nicht; es entsteht kein zweites Lockfile im Baum.

### Reproduzierbarkeit und Übereinstimmung

- Der CI-Runner (`ubuntu-latest`, x86_64, Python 3.12) fällt in den Lock-Ast
  `python_full_version < '3.13'`; der Trockenlauf gegen das bestehende `.venv` meldet „Would make
  no changes“. Plattformspezifische Pakete tragen Marker (`sys_platform == 'win32'`), der Export
  lässt sie stehen und Linux installiert sie nicht.
- **`--locked` an beiden Installationswegen** ist die erste Schicht gegen einen veralteten Lock:
  Ein `pyproject.toml`-Change ohne Lock-Refresh lässt den Installationsschritt mit Hinweis auf
  `uv lock` scheitern.
- **Ein netzfreier Wächtertest** liest `backend/pyproject.toml` und `backend/uv.lock` mit `tomllib`
  und vergleicht die deklarierten Abhängigkeiten samt dev-Extras mit
  `[package.metadata].requires-dist` des Lock-Eintrags `photosort`. Er bricht laut ab, wenn eine
  Deklaration eine Form trägt, die der Parser nicht kennt.
- **`uv` bleibt in CI unpinned:** Hebt eine künftige uv-Version die Lock-Revision an, scheitert
  `--locked` laut mit dem Hinweis auf `uv lock`; kein stiller Fehler.

### Namenskonvention und Umbenennung

`specs/README.md` verlangt für `features/`, `decisions/` und `architecture/` den Rumpf
`NNNN-[a-z0-9]+(-[a-z0-9]+)*`. Großbuchstaben, Leerzeichen, Punkte im Rumpf, Umlaute und andere
Nicht-ASCII-Zeichen sind damit ausgeschlossen. Grund: Git quotet solche Namen ohne `-z`, und sie
fallen aus jeder Aufzählung; Verweise treffen sie nur in genau einer Schreibweise.

Ein neuer Test prüft die tatsächlichen Dateinamen der drei Nummernräume. Die Aufzählung läuft über
`git ls-files -z --cached --others --exclude-standard` — **`-z` ist Pflicht**, sonst quotet Git den
Umlaut-Namen und die Prüfung fällt für genau den Fall aus, für den sie existiert. Der Befund nennt
Pfad, Position, Zeichen und Codepoint.

`git mv specs/features/0037-gateführte-bewertungs-pipeline-mit-backfill.md
specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md` ist eine reine Umbenennung:
Inhalt byte-gleich, Historie als Rename. Die zehn Umlaut-Verweise in acht Markdown-Dateien werden
auf den neuen Namen gebracht; die fünf ASCII-Verweise und die ASCII-Code-Kommentare treffen durch
die Umbenennung wieder. Die Aussage in `scripts/tests/test_dokumentnummern_eindeutig.py`, „genau
ein solcher Name liegt im echten Bestand“, wird auf den neuen Zustand gebracht; der synthetische
`-z`-Test bleibt unverändert.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `backend/uv.lock` | versioniert, Inhalt unverändert (generiert) |
| `.github/workflows/ci.yml` | `run:` von `Install dependencies` (Name/Position unverändert) |
| `docs/setup.md`, `docs/architecture.md`, `specs/README.md`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md` | Installationsweg, Namenskonvention, Lieferkette, benannte Lücken |
| `specs/decisions/0137-…md`, `specs/decisions/0080-…md` | datierter Nachtrag |
| `specs/features/0037-…` | `git mv` auf ASCII-Name |
| acht Markdown-Dateien | zehn Umlaut-Verweise auf neuen Namen |
| `scripts/tests/test_dokumentnummern_eindeutig.py` | Docstring-Aussage und Beispiel |
| drei neue Repo-Konsistenztests unter `scripts/tests/` | Lock aktuell, Lockdateien versioniert, Dateinamen ASCII |

### Reihenfolge für den `developer`

1. Tests zuerst, rot: die drei neuen Testdateien schreiben und ihren Fehlschlag belegen.
2. `backend/uv.lock` versionieren; `uv lock --check` und `uv sync --locked --extra dev --dry-run`.
3. `git mv` der Spec 0037 als eigener Commit; danach die zehn Umlaut-Verweise und den Docstring.
4. CI-`run:` umstellen; `scripts/tests/test_backend_ci_beschleunigung.py` bleibt grün.
5. Doku, ADR-Nachträge und die Lieferketten-/Lücken-Einträge in Test- und Sicherheitskonzept.
6. `(cd scripts && pytest)`, `./scripts/format.sh`, `./scripts/check.sh`, Backend-Tests.

## UI/UX

Nicht relevant: Die Story ändert ausschließlich Repository-Dateien, Build-/Installationswege und
Dokumentation. Es gibt keine sichtbare Oberfläche, keine neue Eingabe und keine Darstellung.

## Security

**Sicherheitsrelevant: ja, ausschließlich über die Lieferkette.** Kein Anwendungscode, kein
Endpunkt, keine neue Eingabe von außen, keine Änderung an Auth, Berechtigungen oder
Datensichtbarkeit zwischen den beiden Nutzern. Im Saldo eine Verengung — dieselbe Auflösung
überall, jede Versionsänderung als gelesener Diff — mit zwei unveränderten, benannten Lücken.

**Bedrohungsmodell.** Schützenswert ist die Integrität des Codes, der läuft: auf dem
Entwicklungsrechner (dort liegen `gh`-Token und Repo-Schreibrecht), im CI-Runner und im
Homeserver-Image (dort liegen Fotos und Zugangsdaten). Angreifer sind (a) ein kompromittiertes
oder untergeschobenes PyPI-Paket (Kontoübernahme, bösartiges Release, fremder Index, direkte URL);
(b) ein manipulierter Pull Request, der Manifest, Lock und Workflow ändert — das Repository ist
öffentlich, Fork-PRs laufen mit `contents: read` ohne Secrets, der Workflow bleibt auf
`on: pull_request`; (c) ein Netzangreifer, gegen den allein TLS trägt, solange kein Hash geprüft
wird. Nicht im Ziel ist ein Angreifer, der bereits Code auf Runner oder Homeserver ausführt. Das
Lock macht die **Version** sichtbar und reviewbar, nicht den **Inhalt** vertrauenswürdig.

**Auflagen für die Umsetzung.** Der Lock wird inhaltlich unverändert übernommen (112 Einträge:
111 Registry-Pakete + `photosort`), vor dem Commit mit `uv lock --check` und
`uv sync --locked --extra dev --dry-run` belegt; eine Manifest-Änderung zieht `uv lock` im selben
Commit nach. Der CI-Schritt bleibt fail-closed: `--locked`, nie `--frozen`; `--no-hashes`,
`--no-emit-project`, `--no-deps`; Ausgabedatei nur unter `"$RUNNER_TEMP"` und in Anführungszeichen;
kein `${{ }}`, kein `eval`, keine PR-kontrollierte Zeichenkette in der Kommandozeile; kein
`continue-on-error`, kein `if:`, kein `|| true`; Name, Position und die vier Prüfschritte bleiben
unverändert. Die Quellen bleiben geschlossen (111× `https://pypi.org/simple`, einmal
`editable = "."`); kein `[tool.uv]`-Index, kein `--index-url`/`UV_INDEX_URL`. Der Lock trägt keine
Geheimnisse und keine Familiendaten — das gilt für jeden künftigen Refresh, weil das Repository
öffentlich ist. Eine Fixierung, kein zweites Lock: die Exportdatei entsteht nur in
`$RUNNER_TEMP`. Doku sagt nicht mehr, als das Lock leistet: „fixiert Versionen, nicht Bytes“;
keine Formulierung „signaturgeprüft“ oder „integritätsgeprüft“. Der Lock-Diff wird gelesen; ein
pauschales `uv lock --upgrade` ist ein Review-Problem, paketweise Refreshes halten ihn lesbar.

**Bewusst getragene Restrisiken:**

- **Keine Integritäts-Hashprüfung.** `--no-hashes` verwirft die Lock-Hashes, `uv pip install` und
  `pip install` im Image prüfen keinen. Gemessen am 2026-11-16: ein auf `sha256:000…0` gesetzter
  Wheel-Hash besteht `uv lock --check` und `uv export --locked`; ein geänderter Manifest-Eintrag
  wird dagegen laut abgewiesen. Getragen, weil Hash-/Signaturprüfung außerhalb des Umfangs liegt —
  die Lücke bleibt benannt, bis eine eigene Story sie schließt.
- **Docker löst weiterhin frisch auf.** `backend/Dockerfile` liest den Lock nicht; das Image kann
  eine andere Menge tragen als der geprüfte CI-Stand. Getragen, weil eine Umstellung das
  Installationsverfahren änderte.
- **Patch-Latenz.** Eine Sicherheitsaktualisierung erreicht CI erst mit einem Lock-Commit, während
  das Image frisch auflöst; die Wege können auseinanderlaufen. Folgt aus dem Ziel „eine Auflösung
  überall“; eine `.github/dependabot.yml` existiert nicht und ist nicht Teil dieser Story.
- **`uv` ist ungepinnt**, vorbestehend. Eine neue Lock-Revision lässt `--locked` laut scheitern,
  statt still einen anderen Stand zu installieren.
- **Das Build-Backend** (`setuptools>=68` aus `[build-system].requires`) steht nicht unter der
  Fixierung; `--no-build-isolation` änderte das Installationsverfahren und ist außerhalb des
  Umfangs.
- **Der Cache-Schlüssel bleibt `hashFiles('backend/pyproject.toml')`.** Ein Lock-Refresh ohne
  Manifest-Änderung hält den Cache warm; uv's Cache ist inhaltsadressiert, eine andere Version ist
  ein Miss, keine falsche Installation. Die Schlüsseländerung ist ausdrücklich außerhalb des
  Umfangs.
- **Fork-PRs führen ihren gepinnten Satz im Runner aus.** Die Grenze ist unverändert:
  `contents: read`, keine Secrets, kein `pull_request_target`, kein Selbstmerge; der Merge bleibt
  das Gate.

**Prüfpunkte.** `test_backend_lock_aktuell.py` und `test_lockdateien_versioniert.py` sind
sicherheitsbezogen; `test_dateinamen_ohne_sonderzeichen.py` trägt AK4–AK6, ist aber kein
Sicherheitsgate. `test_backend_ci_beschleunigung.py` und
`test_signaturpruefung_je_paketsatz.py` bleiben unverändert. `specs/architecture/0003-securitykonzept.md`
bekommt einen datierten Abschnitt unter `## Angriffsflächen`, eine Zeile unter `## Bekannte
Lücken`, eine Ankerzeile und die Kopfzeile „Letzte Aktualisierung“ — mit derselben Aussage
„Versionen, nicht Bytes“ und beiden Lücken (Hash, Docker).

## Teststrategie

Keine Anwendungsebene betroffen: Die Story fasst keine Zeile unter `backend/src/photosort`,
`frontend/` oder `e2e/` an; Unit-, Integrations- und E2E-Ebene bleiben unberührt. Geprüft wird auf
der Ebene der Repo-Konsistenzwächter (`scripts/tests/`, CI-Job `demo-scripts`, netzfrei). **Kein
Wächter ruft `uv` auf:** `uv lock --check` rechnet gegen den Paketindex und machte aus einer
Bestandszusicherung einen Netztest.

| Datei | Prüfgegenstand | gefangener Verstoß |
|---|---|---|
| `test_backend_lock_aktuell.py` | Deklaration ↔ `requires-dist` des Lock-Eintrags `photosort`; Auflösungskanten ↔ Deklaration; der CI-Verbraucher liest den Lock | `pyproject.toml` geändert, `uv lock` vergessen; `requires-dist` von Hand nachgezogen; `--locked` zu `--frozen` abgeschwächt |
| `test_lockdateien_versioniert.py` | versionierte Lock-Menge exakt; unversioniert-nicht-ignoriert leer; alle vier Pfade existieren | `backend/uv.lock` fällt aus dem Index; ein zweiter Lock entsteht still |
| `test_dateinamen_ohne_sonderzeichen.py` | Dateinamen der drei Nummernräume gegen die dokumentierte Form | neue Spec/ADR mit Umlaut, Großbuchstabe, Leerzeichen oder Punkt im Rumpf |

**`test_backend_lock_aktuell.py`** vergleicht in drei Schritten: (1) `[project].dependencies` und
je Extra `[project].optional-dependencies` (Marker `extra == '<extra>'`) gegen `requires-dist`
über normalisierten Namen, Extras, Specifier und Marker, dazu `requires-python` und
`provides-extras`; (2) die `dependencies`/`optional-dependencies`-Kanten des `photosort`-Eintrags
gegen dieselbe Deklaration — das fängt einen nachgezogenen `requires-dist` bei veralteten Kanten;
(3) den `run:`-Rumpf von `Install dependencies` im Job `backend`: genau ein `uv export` mit
`--locked` und `--extra dev`, genau ein `uv pip install` mit `--system`, `--no-deps` und `-r` auf
genau die Datei, die `-o` erzeugt, kein `--frozen`. Kein Volldiff, damit eine zulässige
Umformulierung des Rumpfs keinen Testdiff erzwingt. Unbekannte Anforderungsformen (URL, Pfad, Git,
fremder Marker, doppelter Name) brechen laut ab; fehlende Datei, 0 oder 2 `photosort`-Einträge,
leeres `requires-dist` und weniger als 50 Pakete sind laute Fehler.

**`test_lockdateien_versioniert.py`** liest `git ls-files -z --cached --others
--exclude-standard` und vergleicht gegen einen festen Katalog (`uv.lock`, `poetry.lock`,
`Pipfile.lock`, `pdm.lock`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
`pnpm-lock.yaml`, `bun.lockb`). Versionierte Menge exakt `{backend/uv.lock,
frontend/package-lock.json, e2e/package-lock.json, eye/package-lock.json}`; unversioniert und
nicht ignoriert muss leer sein. Ein fünfter Paketsatz färbt rot, bis er eingetragen ist — die
Asymmetrie `scripts/` ohne Lock ist damit eine benannte Entscheidung, keine Ableitung.

**`test_dateinamen_ohne_sonderzeichen.py`** prüft jede `.md` unmittelbar in den drei
Nummernräumen gegen `^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$` und **jeden** Basename dort — auch
Nicht-`.md` und Verzeichnisse — auf ASCII ohne Großbuchstaben und Leerraum; ohne die zweite
Zusicherung entkäme ein Umlaut-Name der Prüfung durch Weglassen von `.md`. Der Befund nennt Pfad,
1-basierte Zeichenposition, Zeichen, `U+XXXX` und die zulässige Form, stabil sortiert. Die
Aufzählung nutzt `-z`; die Gegenproben-Tabelle (`ü`, `ß`, `Ö`, `é`, kyrillisches `а`,
ASCII-Großbuchstabe, Leerzeichen, Unterstrich, Punkt, Doppelbindestrich, fünfstellige Nummer,
`.MD`, NFD-zerlegter Name) lässt sich nicht lockern, ohne einen Fall zu löschen. Selbstschutz:
lauter Fehler bei leerem Suchraum gesamt und je Verzeichnis, Untergrenzen je Verzeichnis,
namentlicher Anker. Ein Wegwerf-Repo beweist, dass ein Umlaut-Pfad unverändert ankommt **und**
einen Befund mit `U+00FC` erzeugt.

**Wirksamkeitsbelege.** Der Dateinamen- und der Lock-Wächter beginnen rot; beide Läufe gehören
wörtlich in den Test-Docstring (Vorbild ADR 0081). Der erste Befund lautet:
`specs/features/0037-gateführte-bewertungs-pipeline-mit-backfill.md`, Zeichen `ü`, `U+00FC`,
Position 11. `test_backend_lock_aktuell.py` beginnt grün; sein Beleg ist eine Mutationsreihe am
Bestand mit Rücknahme: fehlende Dependency, geänderter Pin, entferntes dev-Extra, nachgezogene
`requires-dist` bei unveränderten Kanten, `--frozen` statt `--locked`, entferntes `--no-deps`,
abweichender `-r`-Pfad. Der Lock-Wächter wird über `git rm --cached backend/uv.lock` und ein
zusätzliches `scripts/uv.lock` rot.

**Bestehende Tests:** Einzige erlaubte Änderung ist der Docstring von
`test_dokumentnummern_eindeutig.py` an zwei Stellen — das Quoting-Beispiel wechselt auf den
Umlaut-Pfad der eigenen Fixture (`specs/decisions/0003-gateführte-pipeline.md`), und „Genau ein
solcher Name liegt im echten Bestand“ wird auf den neuen Zustand gebracht. Keine Assertion, kein
Testfall, keine Fixture ändert sich. `test_backend_ci_beschleunigung.py` pinnt die vier
Prüfschritte mit exaktem `run:`, die Job-Menge und den Cache-Schlüssel, nicht den Rumpf von
`Install dependencies`; es bleibt unverändert grün. `test_nummern.py`,
`test_nummernvergabe_verankert.py`, `test_verweisnummern_in_markdown.py` und
`test_signaturpruefung_je_paketsatz.py` bleiben unverändert.

**Nicht getestet:** dass die Datei das Ergebnis von `uv lock` ist (belegen `uv lock --check` lokal
und `--locked` in CI), Hash-/Signaturprüfung, der frische Auflösungslauf im Dockerfile, ein
ignorierter Fremd-Lock jenseits der vier Pfade und die Existenz von Markdown-Linkzielen
(bestehende, benannte Lücke). AK5 wird deshalb über die alte Schreibweise geprüft: `git grep` auf
`0037-gateführte` darf nur historische Zitate im Docstring des neuen Wächters liefern.

**`specs/architecture/0002-testkonzept.md`:** Datum und Kurzvermerk in Zeile 4; eine neue
Untersektion vor „Reine Bash-Wrapper-Skripte ohne Testframework“ mit den drei Wächtern, der
Aufteilung Daten/Bestand/Name, der Begründung gegen `uv` im Test und den drei Belegformen; die
Backend-Zelle der Lieferketten-Tabelle (Zeile 3155); ein datierter Block „Bekannte Lücken“ vor
„Werkzeuge im Überblick“ mit den drei Grenzen (Erzeugungsnachweis nur gegen uv, kein
Integritäts-Hash, Image löst frisch auf).

## Entscheidungen

- **architect konsultiert (Schritt 1):** Lockfile-Verbrauch, Reproduzierbarkeit, Erzwingung der
  Übereinstimmung, Namensprüfung und Doku-Pflichten sind benennbar an Code, CI und Datenmodell
  gebunden.
- **ux-ui-designer nicht konsultiert (Schritt 2):** Es gibt keinen konkret benennbaren Bezug zu
  einer sichtbaren Oberfläche; die Story ändert nur Repo-Dateien, CI und Doku.
- **test-engineer konsultiert (Schritt 3):** Es gibt konkret benennbares, nicht-triviales Verhalten
  (Aufzählung mit `-z`, Codepoint-Befund, Lock-/Manifest-Abgleich).
- **security-engineer konsultiert (Schritt 3):** Lieferkette und Lockfile sind ein konkret
  benennbarer Sicherheitsbezug.
- **Keine neue ADR:** Die Auslöser aus `CLAUDE.md` greifen nicht; die Entscheidungen von ADR 0137
  und 0080 bleiben gültig und bekommen datierte Nachträge.
- **Auslegung zu AK1 und „jede weitere CI-Änderung“:** Geändert wird ausschließlich der `run:`-Rumpf
  des bestehenden Installationsschritts. Installer (`uv pip`), Umgebung (`--system`), Ziel (`-e .`),
  Schrittname, Position, Job-Menge, Cache-Schlüssel und alle vier Prüfschritte bleiben unberührt.
  Ohne diese Änderung wäre AK1 („exakt die aufgelöste Menge“) nicht erfüllbar, weil `uv pip` kein
  Lockfile liest.

## Offene Fragen

Keine.

## Out of Scope

- Umstellung der Installation auf ein anderes Verfahren, Hash- oder Signaturprüfung der Pakete
- Der Cache-Schlüssel der Prüfungen und jede weitere CI-Änderung (eigenes Thema)
- Umbenennen weiterer Dateien ohne aktuellen Anlass
