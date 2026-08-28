# 0057 - Docker-Compose: LANDMARK_PROVIDER und MISTRAL_API_KEY durchreichen

**Status:** Implemented ([PR #243](https://github.com/TheRealKoller/photosort/pull/243))
**Erstellt:** 2026-08-24
**Bezug:** [`inbox/0038-landmark-provider-env-var-nicht-durchgereicht.md`](../inbox/0038-landmark-provider-env-var-nicht-durchgereicht.md) (Ursprung), [`features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](./0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) (Landmark, produktiv live seit PR #181), [`features/0054-mistral-provider-option-cloud-landmark.md`](./0054-mistral-provider-option-cloud-landmark.md) (Mistral-Provider-Wahl, produktiv live seit PR #195), [`features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Remote-Kategorie-Klassifizierung, nutzt denselben Schalter, ADR 0032 Punkt 3), [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md), [`decisions/0031-mistral-provider-option-cloud-landmark.md`](../decisions/0031-mistral-provider-option-cloud-landmark.md)

## Zusammenfassung des Fehlers

**Symptom:** Ein Nutzer setzt `LANDMARK_PROVIDER=mistral` in `.env` (um Mistral statt Anthropic für die Landmark-Erkennung/Remote-Kategorie-Klassifizierung zu nutzen), oder `MISTRAL_API_KEY=...`, und erwartet, dass dies im Container wirkt. Tatsächlich sieht der Container diese Werte nie — die Container-Umgebung erhält nur `ANTHROPIC_API_KEY`, und Pydantic-Settings in `backend/src/photosort/config.py` fällt still auf den Default `landmark_provider="anthropic"` zurück. Ergebnis: Fotos werden trotzdem an Anthropic gesendet, nicht an Mistral wie konfiguriert.

**Ursache:** Die `environment:`-Blöcke der Services `backend` (Zeilen 34-52 in `docker-compose.yml`) und `worker` (ab Zeile 80) reichen nur `ANTHROPIC_API_KEY` durch, nicht `LANDMARK_PROVIDER` und `MISTRAL_API_KEY`. Alle drei Variablen sind bereits in `.env.example` dokumentiert und im Pydantic-Modell `Settings` vorhanden, die Durchleitung wurde nur übersehen.

**Auswirkung:**
- Landmark-Erkennung (Spec 0047) nutzt immer Anthropic, unabhängig von `LANDMARK_PROVIDER=mistral`.
- Remote-Kategorie-Klassifizierung (Spec 0055) nutzt immer Anthropic, obwohl ADR 0032 Punkt 3 den Schalter bewusst gemeinsam nutzt.
- Eine bereits getroffene, dokumentierte Betreiberentscheidung (Provider-Wahl inkl. akzeptiertem Mistral-DPA-Restrisiko, ADR 0031/Spec 0054) war unbemerkt wirkungslos.
- Lokales Testen/Entwickeln mit `LANDMARK_PROVIDER=mistral` war nicht reproduzierbar.

## Ziel

Config-Regression beheben: `LANDMARK_PROVIDER` und `MISTRAL_API_KEY` in die `environment:`-Blöcke von `backend` und `worker` in `docker-compose.yml` aufnehmen, ohne Rebuild nötig (nur `docker compose up -d`), plus CI-Regressionstest gegen ein erneutes, unbemerktes Wiederauftreten.

## User Story

Als Betreiber einer PhotoSort-Installation möchte ich Umgebungsvariablen für die Cloud-Provider-Konfiguration (`LANDMARK_PROVIDER`, `MISTRAL_API_KEY`) in `.env` setzen und erwarten, dass diese innerhalb der Docker-Container korrekt ankommen und wirken, damit die Landmark-Erkennung und Remote-Kategorie-Klassifizierung tatsächlich mit dem von mir konfigurierten Cloud-Provider laufen.

## Akzeptanzkriterien

**Config & Durchleitung:**
- [ ] In `docker-compose.yml`, Services `backend` und `worker` (beide `environment:`-Blöcke), wird direkt nach der bestehenden Zeile `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}` ergänzt: `LANDMARK_PROVIDER: ${LANDMARK_PROVIDER:-anthropic}` und `MISTRAL_API_KEY: ${MISTRAL_API_KEY:-}`.
- [ ] **Kein Leerdefault für `LANDMARK_PROVIDER`:** `landmark_provider` ist `Literal["anthropic", "mistral"]` ohne `env_ignore_empty`; ein Leerdefault (`${LANDMARK_PROVIDER:-}`) würde bei fehlender `.env`-Variable eine explizite leere Zeichenkette in den Container setzen → `ValidationError` beim Prozessstart, Container kommt gar nicht mehr hoch. Der Compose-Default muss den Pydantic-Default `"anthropic"` explizit duplizieren (analog `SECRET_KEY: ${SECRET_KEY:-change-me}` im selben Block). `MISTRAL_API_KEY` bleibt beim Leerdefault-Muster (`str`-Feld, Pydantic-Default `""`).
- [ ] `docker-compose.demo.yml` bleibt unverändert (eigene, unabhängige Services `opencloud-demo`/`seed` ohne Landmark-/Mistral-Bezug, überschreibt `backend`/`worker` nicht — die Korrektur wirkt dort automatisch mit).

**Ursache behoben, Downstream-Logik bereits/bewusst nicht getestet:**
- [ ] Nach diesem Fix erreicht ein in `.env` gesetztes `LANDMARK_PROVIDER=mistral`/`MISTRAL_API_KEY` den Container und damit `Settings()` (verifiziert durch den CI-Regressionstest unten). Dass `Settings.landmark_provider` daraufhin tatsächlich die Mistral-Variante von `build_landmark_client()`/`build_category_classification_client()` liefert, ist bereits durch bestehende Tests (`test_config.py`, `test_landmark.py`) abgedeckt bzw. bewusst nicht automatisiert getestet (die Dispatch-`if`-Verzweigung selbst, laut ausdrücklicher Konvention in `specs/architecture/0002-testkonzept.md:166`/`:237`) — kein neuer Testauftrag für diesen Bugfix.

**Regressions-Test in CI:**
- [ ] Ein neuer Static-Check-Schritt im `docker-compose-check`-Job (`.github/workflows/ci.yml`, analog "Static check - worker command runs no migration", Zeile 157-168) prüft per `docker compose config --format json | jq` für **beide** Services (`backend`, `worker`):
  1. Ohne gesetzte `LANDMARK_PROVIDER`/`MISTRAL_API_KEY`: `environment.LANDMARK_PROVIDER == "anthropic"` (nicht leer — der eigentliche Regressionsschutz) und `environment.MISTRAL_API_KEY == ""`.
  2. Mit exportierten `LANDMARK_PROVIDER=mistral`/`MISTRAL_API_KEY=<Testwert>`: beide Services lösen exakt diese Werte auf.
- [ ] Der Check schlägt fehl (Exit-Code ≠ 0), wenn eine Variable fehlt, falsch benannt ist, oder einen falschen/leeren Wert auflöst.
- [ ] Der Check läuft ohne real gesetzten `ANTHROPIC_API_KEY`/`MISTRAL_API_KEY`-Wert in der CI-Umgebung (kein Secret-Leck in CI-Logs durch `docker compose config`s interpolierte Ausgabe) — bestehende Konvention im `docker-compose-check`-Job bereits eingehalten, hier nur beibehalten.

**Keine Migrationen / kein erweiterter Scope:**
- [ ] Keine Datenbankmigrationen nötig (reine Config-Korrektur, kein Datenmodell).
- [ ] `.env.example` bleibt unverändert (Variablen waren bereits dokumentiert, nur Container-Durchleitung war fehlerhaft).
- [ ] Kein rückwirkender Abgleich/keine Korrektur bereits mit dem falschen Provider verarbeiteter Fotos (siehe Abschnitt "Entscheidungen").

## Datenmodell-Bezug

Nicht betroffen — kein neues Feld, keine neue Tabelle, keine Migration. Reine Infrastruktur-Config-Korrektur.

## Architektur / Umsetzung

**Ansatz:** Reine Config-Korrektur in `docker-compose.yml` — kein neues Muster, keine neue Abhängigkeit, keine ADR nötig (Bugfix eines bereits in ADR 0025/0031/0032 beabsichtigten Verhaltens). `docker-compose.demo.yml` ist nicht betroffen.

**Betroffene Dateien:**
- `docker-compose.yml` (einzige Code-Änderung)
- `.github/workflows/ci.yml` (neuer Static-Check-Schritt im `docker-compose-check`-Job)
- `.env.example` bleibt unverändert (Variablen bereits dokumentiert)

**Änderung in `docker-compose.yml`:** In beiden `environment:`-Blöcken (`backend`, Zeilen 34-52; `worker`, ab Zeile 80) werden direkt nach `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}` zwei neue Zeilen ergänzt (Reihenfolge folgt `Settings`-Modell: `landmark_provider`/`mistral_api_key` stehen dort direkt nach `anthropic_api_key`):

```
LANDMARK_PROVIDER: ${LANDMARK_PROVIDER:-anthropic}
MISTRAL_API_KEY: ${MISTRAL_API_KEY:-}
```

Wichtig — kein Leerdefault für `LANDMARK_PROVIDER`: Anders als bei reinen `str`-Feldern (`ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `OPENCLOUD_*`, Default `""`) ist `landmark_provider` ein `Literal["anthropic", "mistral"] = "anthropic"`. Da `Settings` kein `env_ignore_empty` setzt, würde eine leer gesetzte Env-Var im Container als explizite leere Zeichenkette ankommen — ein ungültiger `Literal`-Wert, der pydantic-settings beim Prozessstart mit `ValidationError` abbrechen lässt (Container startet gar nicht mehr). Der Compose-Default dupliziert deshalb den Pydantic-Default `"anthropic"` explizit, analog zu `SECRET_KEY: ${SECRET_KEY:-change-me}` und `CATEGORY_SELECTION_ENABLED: ${CATEGORY_SELECTION_ENABLED:-true}` in denselben Blöcken (Compose-Default spiegelt immer den tatsächlichen Settings-Default, nicht grundsätzlich einen Leerstring).

**Reihenfolge der Umsetzung:**
1. `docker-compose.yml`: beide Zeilenpaare in `backend` und `worker` ergänzen.
2. Manueller Smoke-Test lokal: `docker compose config` prüfen, dass beide Variablen in den aufgelösten `environment:`-Abschnitten beider Services erscheinen; `LANDMARK_PROVIDER=mistral` in `.env` setzen, `docker compose up -d`, verifizieren dass `settings.landmark_provider == "mistral"` im Container.
3. CI-Regressionstest in `.github/workflows/ci.yml` ergänzen (siehe Akzeptanzkriterien/Teststrategie).
4. Kein Rebuild nötig, kein Datenmodell/keine Migration betroffen.

## UI/UX

Nicht relevant (idea-sharpener, Schritt 7, strukturell begründet — kein AskUserQuestion nötig): reine Infrastruktur-Config-Änderung ohne jede sichtbare Oberfläche, auch nicht mittelbar.

## Security

Sicherheitsrelevant, ja (`security-engineer`-Konsultation, 2026-08-24) — reiner Config-Bugfix, keine neue Angriffsflächen-Klasse. Vollständige Herleitung siehe `specs/architecture/0003-securitykonzept.md` (Kopf-Changelog, Eintrag 2026-08-24, bereits im Rahmen dieser Konsultation ergänzt).

**Kein Versagen der Fail-Fast-Validierung, sondern eine Ebene davor verloren:** ADR 0031/Spec 0054 legen bewusst fest, dass `Settings.landmark_provider` bei einem ungültigen Wert mit `ValidationError` abbricht — "kein stiller Fallback". Diese Validierung funktioniert weiterhin korrekt; sie wurde nur nie erreicht, weil die Variablen den Python-Prozess über den fehlenden Docker-Compose-Passthrough bislang gar nicht erreichten. Das Ergebnis war strukturell dasselbe wie ein stiller Fallback: eine explizite, im Devil's-Advocate-Gespräch von Spec 0054 bewusst mit akzeptiertem DPA-/ZDR-Restrisiko getroffene Betreiberentscheidung (Mistral/EU statt Anthropic/USA) war unbemerkt wirkungslos.

**Muss-Kriterium für den CI-Regressionstest:** Der `docker compose config --format json | jq`-Check darf nie mit real gesetztem `ANTHROPIC_API_KEY`/`MISTRAL_API_KEY` in der CI-Umgebung laufen (Secret-Leck in CI-Logs, da `docker compose config` interpolierte Werte ausgibt). Verifiziert: Der bestehende `docker-compose-check`-Job setzt an keiner Stelle einen echten Wert für diese beiden Variablen — beizubehalten.

**`MISTRAL_API_KEY: ${MISTRAL_API_KEY:-}`-Passthrough:** kein neues Muster, exakte Kopie des bereits etablierten `ANTHROPIC_API_KEY`-Passthroughs — kein Secret in der Compose-Datei selbst, nur Interpolation aus `.env`/Shell-Umgebung.

**Rückwirkung bewusst nicht Teil dieser Spec** (siehe Abschnitt "Entscheidungen") — Daniel hat sich für den reinen Forward-Fix entschieden, keine rückwirkende Identifikation bereits mit dem falschen Provider verarbeiteter Fotos.

## Teststrategie

`specs/architecture/0002-testkonzept.md` bleibt unverändert — der neue CI-Schritt wendet ausschließlich das bei Spec 0013 etablierte Muster "Static Check im `docker-compose-check`-Job" (Presence-/Wert-Verifikation per `docker compose config --format json | jq`) auf einen neuen, analogen Fall an, kein neues Testmuster.

**Testebenen:**
- **CI Static Check (neu, einzige nötige Testebene):** siehe Akzeptanzkriterien oben — Presence UND aufgelöster Default-/Override-Wert für beide Variablen, beide Services.
- **Kein Functional Check nötig:** `docker compose config` löst die `${VAR:-default}`-Interpolation vollständig und deterministisch auf — exakt das, was der Container zur Laufzeit als Environment bekommt. Ob `pydantic-settings` eine korrekt gesetzte Env-Var einliest, ist Bibliotheksverhalten, kein bugfix-spezifisches Risiko, und bereits durch die bestehende Testsuite implizit belegt.
- **Kein neuer Backend-Unit-Test nötig:** die Dispatch-Logik (`build_landmark_client()`/`build_category_classification_client()`) ist laut bestehender, expliziter Konvention nie automatisiert getestet (`specs/architecture/0002-testkonzept.md:166`/`:237`); `Settings.landmark_provider` selbst ist bereits über `test_config.py` abgedeckt.

**Relevante Edge Cases:**
| Fall | Ebene | Erwartung |
|---|---|---|
| `LANDMARK_PROVIDER` nicht gesetzt | CI Static Check (neu) | beide Services: `"anthropic"`, nicht leer — kritischster Fall, sonst Crash beim echten Containerstart |
| `LANDMARK_PROVIDER=mistral` gesetzt | CI Static Check (neu) | beide Services: `"mistral"` |
| `MISTRAL_API_KEY` nicht gesetzt | CI Static Check (neu) | beide Services: `""` |
| `MISTRAL_API_KEY=<Wert>` gesetzt | CI Static Check (neu) | beide Services: exakt dieser Wert |
| `LANDMARK_PROVIDER=openai` (ungültiger Wert) | bereits unit-getestet (`test_config.py::test_landmark_provider_rejects_an_unknown_value`) | kein Compose-Layer-Fall — Compose reicht Strings ungeprüft durch, Validierung passiert erst in `Settings()`; nicht Teil dieses Bugfixes |
| `MISTRAL_API_KEY` fehlt bei `LANDMARK_PROVIDER=mistral` | vorbestehendes, bewusst nicht automatisiert getestetes Verhalten aus Spec 0054 | außerhalb des Scopes dieses Bugfixes, kein neuer Gap |

## Entscheidungen (2026-08-24, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Kein Leerdefault für `LANDMARK_PROVIDER`:** eigenständige, kritische technische Korrektur von `architect` gegenüber dem ursprünglichen Draft (der `${LANDMARK_PROVIDER:-}` vorschlug) — ein Leerdefault hätte den Container beim Start mit `ValidationError` abstürzen lassen (`Literal`-Feld ohne `env_ignore_empty`), eine schwerere Regression als der ursprüngliche, immerhin funktionsfähige stille Fallback auf Anthropic.
- **AK3/AK4 ("Funktionalität Landmark"/"Funktionalität Remote-Kategorie") von `test-engineer` durch eine ehrliche "Ursache behoben, Downstream bereits/bewusst nicht getestet"-Formulierung ersetzt** — die ursprünglich im Draft formulierten Kriterien hätten fälschlich suggeriert, dieser Bugfix bräuchte einen neuen End-to-End-Nachweis über den Dispatch hinweg; tatsächlich ist die Dispatch-Verzweigung selbst laut bestehender Konvention bewusst nie automatisiert getestet.
- **Kein Functional-CI-Check, nur Static Check:** eigenständige technische Entscheidung von `test-engineer` — ein echter Containerstart-Test wäre für diese Regressionsklasse unverhältnismäßig, da `docker compose config` die Interpolation bereits vollständig und deterministisch auflöst.
- **Bewusst kein rückwirkender Abgleich bereits fälschlich mit Anthropic verarbeiteter Fotos:** `security-engineer` hat identifiziert, dass sich betroffene Zeilen technisch über `provider="anthropic"` in `photo_landmark_detections`/`photo_category_detections` erkennen ließen, und dies Daniel als offene Frage vorgelegt. Daniel hat sich für den reinen Forward-Fix ohne zusätzliches Rückwirkungs-Akzeptanzkriterium entschieden.
- **Keine neue ADR:** von `architect` bestätigt — reine Bugfix-Korrektur eines bereits in ADR 0025/0031/0032 beabsichtigten Verhaltens, keine neue Architekturentscheidung.
- **`docker-compose.demo.yml` unverändert:** von `architect` verifiziert — eigene, unabhängige Services ohne Landmark-/Mistral-Bezug, überschreibt `backend`/`worker` nicht.

## Offene Fragen

Keine — die einzige im Sharpening-Gespräch aufgetretene Unklarheit (rückwirkender Abgleich betroffener Fotos) wurde mit Daniel geklärt (siehe Abschnitt "Entscheidungen").

## Out of Scope

- Änderungen an der `backend/src/photosort/config.py::Settings`-Struktur (nicht nötig — Variablen sind bereits vorhanden).
- Rückwirkende Identifikation/Korrektur bereits mit dem falschen Provider verarbeiteter Fotos (bewusste Stakeholder-Entscheidung, siehe "Entscheidungen").
- Neue Features für Provider-Auswahl oder Kostenmanagement (separate Specs, nicht Teil dieses Bugfixes).
- Behebung anderer denkbarer Config-Übersehungen in `docker-compose.yml` (nur die beiden genannten Variablen).
