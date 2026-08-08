# 0008 - Automatisierte SemVer-Releases über ein Release-PR-Muster

**Status:** Accepted
**Datum:** 2026-07-29

## Kontext

Spec 0008 ("Automatisierte SemVer-Releases bei Merge nach main") verlangt: bei jedem PR-Merge nach `main` wird automatisch geprüft, ob ein Release fällig ist (SemVer-Bump nach Conventional Commits, Git-Tag + GitHub-Release mit generiertem Changelog, Versions-Bump als Commit in `backend/pyproject.toml` und `frontend/package.json`), ausdrücklich ohne Kopplung an das künftige Deploy-Tool "Dockhand" und ohne Docker-Image-Tagging.

Der Release-Mechanismus ist bereits mit Daniel per AskUserQuestion geklärt (nicht Teil dieser ADR-Entscheidung, sondern deren bindende Vorgabe): Release-PR-Muster (release-please-Stil) statt Direct-Push-Stil. Grund: ADR 0007 hat die Branch Protection auf `main` gehärtet (`enforce_admins: true`, `required_status_checks` strict mit Contexts `backend`/`frontend`/`docker-compose-check`, `required_pull_request_reviews`-Objekt mit `required_approving_review_count: 0`, `required_conversation_resolution: true`). Das Vorhandensein des `required_pull_request_reviews`-Objekts erzwingt auf GitHub einen PR-basierten Merge nach `main` — ein direkter `git push`/Commit (klassisches semantic-release-Muster) ist damit nicht mehr möglich, auch nicht für einen Bot mit `enforce_admins: true`.

ADR 0007 hält zudem fest, dass `required_approving_review_count: 0` nur sicher ist, solange Daniel der einzige Akteur mit Schreibzugriff ist, und bei einem zweiten Akteur re-evaluiert werden muss. Ein sich selbst mergender Release-Bot ist ein solcher zweiter *automatisierter* Akteur; Daniel hat dies für seine eigene Automatisierung explizit als akzeptabel bestätigt.

Diese ADR entscheidet die **technische Umsetzung** dieses bereits vorgegebenen Musters: Tooling, Datei-Struktur, Source of Truth für die Versionsnummer, Token/Berechtigungen für den Self-Merge.

## Entscheidung

### Tooling: `googleapis/release-please-action`

Neue externe Abhängigkeit: GitHub Action `googleapis/release-please-action`, Major-Version 4, referenziert über Commit-SHA statt beweglichem Tag (siehe "Token/Berechtigungen") — MIT-lizenziert, von Google betrieben, der De-facto-Standard für exakt das vorgegebene Release-PR-Muster. Kein selbstgebauter Workflow — die Logik "Conventional Commits seit letztem Release auswerten, Release-PR fortlaufend pflegen, bei dessen Merge Tag+Release erzeugen, releasable vs. nicht-releasable Commit-Typen unterscheiden" ist genau das, was das Tool tut, und ein Eigenbau würde denselben Umfang an Edge-Cases (Merge-Commit-Parsing, Changelog-Grouping, Pre-1.0-Bump-Regeln) neu und schlechter erfinden.

### Workflow-Datei: eine neue Datei, `ci.yml` bleibt unverändert

`.github/workflows/release-please.yml`, Trigger `push: branches: [main]`. Läuft **zusätzlich** zu, nicht anstatt, `ci.yml` (das unverändert bei `push`/`pull_request` weiterläuft). Ein einzelner Workflow genügt: `release-please-action` übernimmt bei jedem Lauf sowohl "Release-PR anlegen/aktualisieren" als auch — erkennt es, dass der letzte Merge selbst der Release-PR war — "Tag + GitHub-Release erzeugen".

Zwei neue Konfigurationsdateien im Repo-Root:
- `release-please-config.json`
- `.release-please-manifest.json`

### Versionierungsmechanik / Source of Truth

**Ein** Komponente im Manifest, Pfad `"."`, `release-type: "simple"` (dieser Release-Typ verwaltet selbst keine Paketdatei, sondern trackt die Version ausschließlich über `.release-please-manifest.json`). Das erzwingt strukturell genau **einen** Tag, **einen** Changelog, **eine** GitHub-Release pro Release-Lauf — passend zu "EINE gemeinsame Projekt-Version" (Punkt 6 der Vorgabe). Eine Zwei-Komponenten-Lösung (`python`-Typ für `backend/`, `node`-Typ für `frontend/`, verbunden über das `linked-versions`-Plugin) wäre technisch sauberer beim Parsen der Zieldateien, hätte aber standardmäßig zwei Tags/zwei Releases zur Folge — das widerspricht Punkt 1 der Vorgabe (**ein** Tag, **eine** Release) und wurde deshalb verworfen.

Die Manifest-Datei (`.release-please-manifest.json`, vom Tool selbst gepflegt) ist damit die Source of Truth für die aktuelle Version. `backend/pyproject.toml` und `frontend/package.json` (sowie `frontend/package-lock.json`, siehe Begründung) werden über `extra-files` in `release-please-config.json` synchron mitgeschrieben — sie sind abgeleitete Artefakte, keine eigene Quelle.

```jsonc
// release-please-config.json
{
  "release-type": "simple",
  "bump-minor-pre-major": false,       // feat bumpt MINOR auch < 1.0.0 (Punkt 2 der Vorgabe)
  "bump-patch-for-minor-pre-major": false, // fix bumpt PATCH auch < 1.0.0
  "include-component-in-tag": false,   // Tag wird "vX.Y.Z", kein Präfix
  "extra-files": [
    { "type": "generic", "path": "backend/pyproject.toml" },
    { "type": "json", "path": "frontend/package.json", "jsonpath": "$.version" },
    { "type": "json", "path": "frontend/package-lock.json", "jsonpath": "$.version" },
    { "type": "json", "path": "frontend/package-lock.json", "jsonpath": "$.packages[''].version" }
  ]
}
```

```jsonc
// .release-please-manifest.json (Bootstrap-Wert, siehe "Bootstrap" unten)
{ ".": "0.1.0" }
```

`bump-minor-pre-major`/`bump-patch-for-minor-pre-major` entsprechen zwar bereits den Tool-Defaults, werden aber explizit gesetzt statt implizit auf Default-Verhalten vertraut — falls sich Tool-Defaults künftig ändern, bleibt das hier geforderte Bump-Verhalten (Punkt 2) stabil dokumentiert.

Requirement 3 ("nur releasable Changes lösen ein Release aus") ist natives Default-Verhalten von `release-please`: Commit-Typen `docs`, `chore`, `test`, `ci`, `build`, `style`, `refactor` lösen weder einen Versions-Bump noch einen sichtbaren Changelog-Eintrag aus; nur `feat`/`fix`/`perf` sowie `!`/`BREAKING CHANGE`-Footer (unabhängig vom Typ) tun das. Keine zusätzliche Konfiguration nötig.

**Bekannte Einschränkung (`generic`-Extra-File für `pyproject.toml`):** Der `generic`-Updater ersetzt den *literalen* Versionsstring im Ziel-Text, ohne TOML zu parsen. Aktuell keine Kollisionsgefahr (keine Dependency-Range in `pyproject.toml` entspricht zufällig exakt der aktuellen Version). Da jeder Release-PR ohnehin vor dem (automatischen) Merge über den normalen PR-Prozess sichtbar ist (Diff einsehbar, CI läuft), ist das ein tragbares Restrisiko statt ein Blocker — sollte aber jedem, der einen Release-PR-Diff durchsieht, bewusst sein.

### Workflow-Ablauf

```yaml
# .github/workflows/release-please.yml (Kernlogik, Details bei Umsetzung verifizieren)
on:
  push:
    branches: [main]
permissions:
  contents: write
  pull-requests: write
jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - id: release
        uses: googleapis/release-please-action@<commit-sha> # v4.x.x, siehe "Token/Berechtigungen" — bewusst nicht der bewegliche Tag @v4
        with:
          token: ${{ secrets.RELEASE_PLEASE_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
      - name: Auto-Merge für den Release-PR aktivieren
        if: steps.release.outputs.pr
        env:
          GH_TOKEN: ${{ secrets.RELEASE_PLEASE_TOKEN }}
        run: gh pr merge --auto --squash <PR-Nummer aus steps.release.outputs>
```

Der zweite Step ist nötig, damit der Release-PR **ohne Klick von Daniel** gemergt wird, sobald dessen eigene CI (via `ci.yml`, ausgelöst durch den normalen `pull_request`-Trigger) grün ist und keine offenen Konversationen bestehen — das setzt Punkt 8 der Vorgabe (Self-Merge) technisch um, über GitHubs natives Auto-Merge-Feature statt über Polling/eigene Merge-Logik im Workflow. Voraussetzung: Repo-Setting "Allow auto-merge" muss aktiviert werden (aktuell `false`, geprüft via `gh api repos/TheRealKoller/photosort --jq .allow_auto_merge`) — einmaliger Setup-Schritt bei der Umsetzung (`gh api repos/TheRealKoller/photosort -X PATCH -f allow_auto_merge=true` oder über die Repo-Settings-UI).

Da `release-please` bei jedem Push nach `main` (also bei jedem regulären Feature-/Fix-Merge) den Release-PR-Branch neu aus dem aktuellen `main` + den bis dahin aufgelaufenen Commits berechnet und den bestehenden PR-Branch aktualisiert, bleibt der Release-PR automatisch "up to date" im Sinne von `required_status_checks.strict` — kein manuelles "Update branch" nötig.

**Bewusste Abweichung von der CLAUDE.md-Konvention "jeder PR bekommt ein angefordertes Copilot-Review":** Für den Release-PR wird **kein** Copilot-Review angefordert. Der Release-PR ist ein rein mechanischer, tool-generierter Diff (Versionsnummern + Changelog, kein handgeschriebener Code) — ein Review liefert dort keinen Erkenntnisgewinn. Wichtiger: `required_conversation_resolution: true` würde jede von Copilot hinterlassene, nicht aufgelöste Konversation zu einem dauerhaften Blocker für den vollautomatischen Self-Merge machen, den niemand routinemäßig auflöst — das würde die Automatisierung regelmäßig zum Stillstand bringen. Diese Ausnahme gilt **ausschließlich** für die von `release-please` erzeugten Release-PRs, nicht für reguläre Feature-/Fix-PRs.

### Token/Berechtigungen

Der Standard-`GITHUB_TOKEN` eines Workflow-Laufs löst laut GitHub keine Folge-Workflows aus, die auf von ihm selbst erzeugte Events reagieren (u.a. `pull_request`-Events für einen von ihm selbst erstellten PR) — das ist eine bewusste GitHub-Anti-Rekursions-Regel. Für den Release-PR bedeutet das konkret: würde `release-please-action` mit dem Standard-`GITHUB_TOKEN` laufen, würde `ci.yml` (Trigger `pull_request`) auf dem Release-PR **nicht** anlaufen — die für den Merge nötigen Status-Checks (`backend`/`frontend`/`docker-compose-check`) blieben dauerhaft aus, der Auto-Merge könnte nie greifen.

Lösung: ein **fine-grained Personal Access Token** (PAT), erstellt unter Daniels eigenem GitHub-Account, gescoped **ausschließlich auf `TheRealKoller/photosort`**, mit minimalen Repository-Permissions: `Contents: Read & write`, `Pull requests: Read & write`, `Issues: Read & write`, `Metadata: Read` (Pflicht-Minimum). Kein Admin, keine Organisations-weite Berechtigung, Ablaufdatum gesetzt (z.B. 1 Jahr, danach manuell zu erneuern). Gespeichert als Repo-Secret `RELEASE_PLEASE_TOKEN`.

**Korrektur (2026-08-08, `security-engineer`-Review der Umsetzung):** Der ursprünglich hier genannte Scope (`Contents`/`Pull requests`/`Metadata`) war unvollständig — `Issues: Read & write` fehlte. `release-please` setzt/entfernt die Zustands-Labels `autorelease: pending`/`autorelease: tagged` (interner Wiedererkennungsmechanismus für den eigenen Release-PR) über `octokit.issues.addLabels`/`removeLabel`; der zugrundeliegende REST-Endpunkt (`POST /repos/{owner}/{repo}/issues/{issue_number}/labels`) gehört laut GitHubs OpenAPI-Beschreibung zur Permission-Kategorie "Issues", nicht "Pull requests" — auch wenn die Nummer eine PR referenziert. Ohne diesen Scope schlägt der Label-Aufruf mit `403` fehl (ungefangene Exception, reißt den gesamten Action-Lauf mit), und ein bereits angelegter Release-PR bliebe für künftige Läufe unerkennbar. Der obige Scope-Text ist bereits korrigiert; siehe `specs/architecture/0003-securitykonzept.md` ("GitHub-Repository-Zugriff"/"Bekannte Lücken") für die vollständige Herleitung.

Eine GitHub-App-Installation (Token via `actions/create-github-app-token`) wäre die "sauberere" Lösung (kurzlebige Installations-Tokens statt eines langlebigen PATs) — für ein Solo-Projekt mit einem einzigen Collaborator ist der Betriebsaufwand einer eigenen GitHub-App-Registrierung/-Wartung gegenüber einem fine-grained, eng gescopten PAT jedoch nicht gerechtfertigt (Pragmatiker-Abwägung). Sollte das Projekt je einen zweiten menschlichen Collaborator bekommen, ist dieser Punkt zu revisitieren.

Da der PAT unter Daniels eigenem Account ausgestellt wird, ist ein damit ausgeführter Merge technisch kein neuer Collaborator im GitHub-Sinn (keine neue Identität mit eigenen Rechten) — die Automatisierung agiert weiterhin mit genau Daniels Rechten, nicht mit zusätzlich delegierten. Sie erweitert aber real den **automatisierten Blast-Radius**: ein Merge nach `main` kann jetzt ohne jeden menschlichen Klick zum Zeitpunkt des Merges passieren. Das verdient dieselbe Sorgfalt wie ein "echter" zweiter Akteur, auch wenn ADR 0007s Klausel ("re-evaluieren bei zweitem Akteur mit Schreibzugriff") formal nicht greift.

### Bootstrap (erster Release-Lauf)

Als Teil der Umsetzung dieser Spec (nicht Teil dieser ADR, sondern konkrete Implementierungsschritte):

1. `frontend/package.json` (aktuell `0.0.0`, nie synchron gepflegt) wird in derselben PR, die diese Spec umsetzt, manuell auf `0.1.0` gesetzt — synchron zu `backend/pyproject.toml` (bereits `0.1.0`). `frontend/package-lock.json` entsprechend mit `npm install --package-lock-only` regenerieren.
2. Diese PR fügt `release-please-config.json` und `.release-please-manifest.json` (Inhalt `{".": "0.1.0"}`) hinzu.
3. Direkt nach dem Merge dieser PR: Tag `v0.1.0` auf den Merge-Commit setzen und einen passenden GitHub-Release "v0.1.0" anlegen (z.B. `gh release create v0.1.0 --notes "Start der automatisierten Versionierung, siehe ADR 0008"`) — das ist der reale, sichtbare Anker "Startversion v0.1.0" (Punkt 7 der Vorgabe).
4. Ab da läuft die Automatisierung: der **erste automatisch erzeugte** Release ist die Version, die sich aus dem *nächsten* releasable Commit nach `v0.1.0` ergibt (z.B. `v0.1.1` bei einem `fix:`, `v0.2.0` bei einem `feat:`) — nicht nochmal `v0.1.0` selbst. Ohne einen echten Tag `v0.1.0` als Anker würde `release-please` sonst versuchen, die gesamte bisherige Commit-Historie seit Repo-Beginn (Specs 0001–0007, viele `feat:`-Commits) auszuwerten, was zu einer deutlich höheren, unbeabsichtigten ersten Versionsnummer führen würde.

*Anmerkung: "Startversion für den ersten automatischen Release-Lauf: v0.1.0" wurde hier so interpretiert, dass v0.1.0 der Bootstrap-Anker ist, ab dem automatisch weitergezählt wird — nicht, dass der erste automatisch von release-please erzeugte Tag zwingend selbst "v0.1.0" heißen muss (das widerspräche der ebenfalls vorgegebenen automatischen Bump-Logik). Diese Interpretation wurde in Schritt 9 der Spec-Verfeinerung mit Daniel bestätigt (siehe Spec 0008, Abschnitt "Offene Fragen").*

## Begründung

- **`release-please-action` statt Eigenbau:** Punkt 5 der Vorgabe beschreibt exakt das Verhaltensmuster, das dieses Tool bereits produktionsreif implementiert (u.a. bei Google selbst in hunderten Repos im Einsatz). Ein Eigenbau-Workflow müsste Conventional-Commit-Parsing, Pre-1.0-Bump-Regeln, Changelog-Grouping und Merge-Erkennung selbst nachbauen — deutlich mehr Wartungsaufwand für denselben Nutzen. Neue externe Abhängigkeit ist damit gerechtfertigt (siehe CLAUDE.md-Vorgabe zu externen Abhängigkeiten).
- **`release-type: simple` + `extra-files` statt Zwei-Komponenten-Manifest:** direkte Konsequenz aus Punkt 1+6 der Vorgabe (ein Tag, eine Release, eine gemeinsame Version) — eine technisch elegantere Zwei-Komponenten-Lösung wurde bewusst verworfen, weil sie diese explizite Vorgabe verletzt hätte.
- **Fine-grained PAT statt GitHub App:** Verhältnismäßigkeit für ein Solo-Projekt (Pragmatiker-Abwägung) bei gleichzeitig engem Scope (nur dieses Repo, minimale Permissions, Ablaufdatum) als Kompromiss zur Senior-Sichtweise (eine GitHub App wäre die langfristig sauberere Lösung, aber erst gerechtfertigt, wenn mehr als ein Repo/Bot-Use-Case sie teilen würde).
- **Kein Copilot-Review auf Release-PRs:** verhindert, dass eine allgemeine Prozessregel (die für inhaltliche Code-Reviews gedacht ist) die hier explizit gewünschte Vollautomatisierung (Punkt 8) lahmlegt. Eng gefasste, dokumentierte Ausnahme statt stillschweigender Abweichung.

## Konsequenzen

- Neue Repo-Secrets: `RELEASE_PLEASE_TOKEN` (fine-grained PAT, Rotation/Ablauf durch Daniel zu pflegen — nicht automatisierbar, da PAT-Erstellung ein manueller GitHub-UI-Schritt ist).
- Neues Repo-Setting: "Allow auto-merge" muss von `false` auf `true` gesetzt werden (einmaliger Schritt).
- Neue Dateien im Repo-Root: `release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`, sowie generiertes `CHANGELOG.md` (ab dem ersten automatischen Release).
- `backend/pyproject.toml`- und `frontend/package.json`/`package-lock.json`-Versionsfelder werden ab jetzt **nicht mehr manuell** gepflegt — jede manuelle Änderung dieser Felder außerhalb eines Release-PRs wird beim nächsten `release-please`-Lauf überschrieben/kann zu Inkonsistenzen mit dem Manifest führen. Das ist beabsichtigt (Single Source of Truth = Manifest), sollte aber allen, die an diesen Dateien arbeiten, bewusst sein.
- Bezug zu ADR 0007: diese ADR nutzt die durch ADR 0007 gehärtete Branch Protection als *Grund* für die Werkzeugwahl (Release-PR- statt Direct-Push-Muster) und erweitert gleichzeitig den in ADR 0007 beschriebenen Vertrauens-/Automatisierungs-Radius um einen sich selbst mergenden Bot-Workflow. `security-engineer` sollte dies explizit im Sicherheitskonzept (`architecture/0003-securitykonzept.md`) nachziehen (siehe unten, Konsultationspunkte).
- Explizit unverändert: keine Kopplung an Dockhand, kein Docker-Image-Tagging, kein Push-Restriction/Tag-Protection-Setup (aktuell keine Tag Protection Rules vorhanden — ein PAT-Inhaber könnte theoretisch einen bestehenden Release-Tag überschreiben; da nur Daniel selbst den PAT besitzt, aktuell kein zusätzliches Risiko, aber ein Punkt für eine spätere Härtungs-ADR, falls je ein zweiter Akteur hinzukommt).

## Offene Punkte für `security-engineer` (nächster Konsultationsschritt)

1. PAT-Scope/-Ablauf/-Storage als Repo-Secret; Rotationsprozess (kein technischer Reminder vorhanden — manuell zu tracken?).
2. Bestätigen, dass Auto-Merge tatsächlich `required_status_checks` und `required_conversation_resolution` korrekt respektiert (empirisch nach erstem echten Lauf zu verifizieren, nicht nur aus GitHub-Doku abgeleitet).
3. Re-Bewertung von ADR 0007s Aussage "`required_approving_review_count: 0` sicher, solange Daniel einziger Akteur mit Schreibzugriff" im Licht eines nun automatisiert selbst-mergenden Bot-Workflows (formal kein neuer Collaborator, faktisch aber ein neuer automatisierter Aktionspfad nach `main`).
4. Bewusste Ausnahme "kein Copilot-Review auf Release-PRs" — gegenprüfen, ob das akzeptabel ist oder ob z.B. ein nicht-blockierendes Review (angefordert, aber nicht auflösungspflichtig) ein besserer Mittelweg wäre.
5. Fehlende Tag-Protection auf `v*`-Tags — aktuell kein Problem (ein Akteur), aber als Nachtrag für `architecture/0003-securitykonzept.md` (GitHub-Repository-Zugriff-Sektion) zu dokumentieren, analog zur Baseline-Dokumentation aus ADR 0007.
6. Sicherstellen, dass `RELEASE_PLEASE_TOKEN` in Workflow-Logs nirgends im Klartext auftaucht (GitHub maskiert Secrets standardmäßig, aber explizit prüfen bei `gh pr merge`-Ausgabe/Debug-Logging).

## Nachtrag (2026-08-08): Korrektur des Konfigurationsbeispiels

Die getroffene **Entscheidung** ("Versionierungsmechanik / Source of Truth", oben) bleibt unverändert: ein Manifest-Eintrag `"."`, `release-type: "simple"`, ein Tag/eine Release/eine gemeinsame Version, dieselben Flags und `extra-files`. Nur das illustrative JSON-Beispiel darin war unvollständig: es zeigt `release-please-config.json` ohne einen Top-Level-`packages`-Key. Bei der Umsetzung stellte sich heraus, dass `packages` laut offiziellem JSON-Schema (`https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json`, `allOf[1].required == ["packages"]`) ein Pflichtfeld ist — das ursprüngliche Beispiel wäre gegen dieses Schema **nicht valide** gewesen (verifiziert: Entfernen von `packages` aus der tatsächlich umgesetzten Config lässt die Schema-Validierung fehlschlagen).

Umgesetzt (und gegen das Schema erfolgreich validiert) wurde stattdessen:

```jsonc
// release-please-config.json (tatsächlich umgesetzt)
{
  "release-type": "simple",
  "bump-minor-pre-major": false,
  "bump-patch-for-minor-pre-major": false,
  "include-component-in-tag": false,
  "extra-files": [ /* wie oben */ ],
  "packages": { ".": {} }
}
```

Die Top-Level-Felder (`release-type`, `bump-*`, `include-component-in-tag`, `extra-files`) bleiben als Defaults stehen und werden von der leeren Package-Override `packages["."] = {}` geerbt — verifiziert anhand des `release-please`-Quellcodes (`src/manifest.ts`, `extractPathConfig`: `pathConfig.releaseType ?? defaultConfig.releaseType ?? 'node'` u.ä. `??`-Ketten für jedes Feld) sowie empirisch gegen das reale Schema getestet. Funktional identisch zur ursprünglich skizzierten Absicht (ein Tag/eine Release über `release-type: simple` für den Root-Pfad `.`).

**Beobachtung, kein Fehler:** In der Praxis legen die meisten real existierenden `release-please`-Konfigurationen (u.a. `googleapis/release-please` selbst, `googlemaps/google-maps-ios-utils`, `osiegmar/FastCSV`) release-typische Felder wie `release-type`/`extra-files` direkt unter `packages["."]` statt top-level ab — beide Formen sind laut Schema und Quellcode gültig und für ein Repo mit genau einem Root-Package funktional gleichwertig. Die top-level-Variante folgt nicht der verbreitetsten Konvention, ist aber nicht falsch; falls dieses Repo je ein zweites Package bekäme (aktuell nicht geplant, siehe "Out of Scope" in Spec 0008), würden die Top-Level-Werte automatisch auch für das neue Package als Default gelten, sofern nicht explizit überschrieben — ein potenzieller, aber aktuell irrelevanter Stolperstein.

Da sich an der Entscheidung selbst nichts ändert (dieselbe Tool-Wahl, derselbe `release-type`, dieselbe Source of Truth, dieselben Flags — nur eine im ursprünglichen Beispiel fehlende Pflichteigenschaft des JSON-Schemas wird ergänzt), wird hierfür **keine neue, superseding ADR** angelegt; dieser Nachtrag korrigiert ausschließlich das fehlerhafte Beispiel in der bereits akzeptierten ADR, ohne deren Kernentscheidung anzutasten.
