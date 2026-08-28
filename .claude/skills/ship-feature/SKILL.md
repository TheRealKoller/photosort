---
name: ship-feature
description: Koordiniert auf oberster Ebene (Orchestrator/Hauptsession) die Nachbereitung eines `developer`-Subagenten-Laufs — Review-Agenten aufrufen, Findings per SendMessage zurückspielen, Pull Request eröffnen, Copilot-Review anfordern/auswerten. Nutze diesen Skill IMMER, wenn eine `developer`-Subagenten-Antwort mit dem wörtlichen Anker `## Blockiert: Architektur-Konsultation nötig` oder `## Abschlussbericht` zurückkommt (auch `## Abschlussbericht (Folgeauftrag: Findings behoben)`) — das ist der verbindliche Übergabepunkt, an dem `developer` selbst keine weitere Verschachtelungsebene an Subagenten und keinen GitHub-Zugriff hat. Nicht nutzen für die Umsetzung selbst (dafür `developer`) oder das Schärfen einer Idee zur Spec (dafür `spec-writer`).

---

# Ship Feature — Review, PR und Copilot-Review vom Orchestrator

Übernimmt genau die Verantwortung, die ein per Agent-Tool gestarteter `developer`-Subagent strukturell nicht selbst wahrnehmen kann: eine weitere Verschachtelungsebene an Subagenten (die fünf Review-Agenten, ggf. `architect` bei einer Planungslücke) und GitHub-Schreibzugriff (Push, PR-Erstellung, Copilot-Review). `developer` bleibt für die Dauer dieses gesamten Ablaufs als offener Subagent ansprechbar (SendMessage), es wird für Folgeaufträge kein neuer Lauf gestartet, solange der Subagent noch erreichbar ist.

## Schritt 0: Trigger erkennen

Eine `developer`-Antwort löst diesen Skill aus, wenn sie einen der folgenden wörtlichen Anker enthält (Groß-/Kleinschreibung und Zeichensetzung exakt wie hier, keine sinngemäße Näherung):

- `## Blockiert: Architektur-Konsultation nötig` → Schritt 1.
- `## Abschlussbericht` (Erstbericht, vor jedem Review) → Schritt 2.
- `## Abschlussbericht (Folgeauftrag: Findings behoben)` (nach einem SendMessage-Fix-Auftrag) → Schritt 6.

**Kein exakter Match, aber erkennbar gemeinter Abschluss** (z.B. Tippfehler, abweichende Formatierung, fehlendes Feld): nicht stillschweigend als "fertig, bereit für Review" werten. Lies den Bericht inhaltlich vollständig — wirkt er wie ein vollständiger Abschluss, frag beim `developer`-Subagenten per SendMessage kurz nach, ob es sich um den finalen Bericht handelt und bitte um die Korrektur des Ankers (kostet eine Nachricht, verhindert aber ein falsch interpretiertes Signal); wirkt er unvollständig oder unklar, frag stattdessen inhaltlich nach, was fehlt. Nie raten.

## Schritt 1: "Blockiert" behandeln

Format:

```
## Blockiert: Architektur-Konsultation nötig

**Feature-Branch:** <Name>
**Grund:** <konkret, z.B. "Spec-Abschnitt fehlt" / "deckt Komplikation X nicht ab">
**Bisheriger Stand:** <was schon committet ist, falls etwas>
```

1. Ruf `architect` auf (Agent-Tool, `subagent_type: architect`, Standard-Modell — kein `model`-Parameter, wie bisher in `developer.md` Schritt 1 vorgesehen), im Vordergrund/`run_in_background: false`. Gib ihm den genannten Grund, den Spec-Bezug und den bisherigen Stand mit.
2. Gib das Ergebnis per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zurück, der bei Schritt 1 seines Ablaufs fortfährt.
3. Schlägt `SendMessage` fehl (Subagenten-Fenster bereits geschlossen/Timeout): siehe Abschnitt "Recovery" unten.

## Schritt 2: "Abschlussbericht" behandeln — Branch-/Diff-Verifikation

Format laut ADR 0024 Teil 3 (siehe dort für alle Feldnamen). Bevor überhaupt eine Review-Entscheidung getroffen wird, verifiziere den gemeldeten Stand selbst — der Bericht dient nur der Nachvollziehbarkeit/Plausibilisierung, nicht als alleinige Quelle:

1. `git branch --show-current` gegen den im Bericht genannten `**Feature-Branch:**` abgleichen. Bei Abweichung `git checkout <gemeldeter-branch>`.
2. `git status` muss sauber sein. Ist das nicht der Fall, obwohl der Bericht "sauber, alles committet" behauptet, das nicht stillschweigend ignorieren — im Bericht vermerken und den `developer`-Subagenten per SendMessage auf die Diskrepanz hinweisen, bevor es weitergeht.
3. `git diff --name-only main...HEAD` **selbst erneut ausführen** — das ist die verbindliche Quelle für die folgende Trigger-Auswertung, nicht die im Bericht unter "Betroffene Dateien" gelistete Liste. Weicht die selbst ermittelte Liste sichtbar von der gemeldeten ab, das im späteren Findings-Bericht vermerken statt kommentarlos zu verwerfen.

## Schritt 3: Review-Trigger-/Modelltabelle auswerten

Welche der fünf Review-Agenten tatsächlich laufen, entscheidet **nicht** eine freie Einzelfalleinschätzung, sondern die feste, mechanisch ausgewertete Trigger-Tabelle aus [ADR 0014](../../../specs/decisions/0014-review-agenten-selektion-und-modellzuweisung.md), Teil 1 — inhaltlich unverändert, hier nur zur unmittelbaren Ausführbarkeit erneut eingetragen (identische Kopie, bei jeder künftigen Änderung zuerst in ADR 0014, dann hier synchron aktualisieren):

| Agent | Verhalten | Trigger (läuft, wenn mindestens einer zutrifft) |
|---|---|---|
| `test-engineer` | **Fast immer aktiv.** Skip nur im Entartungsfall. | Läuft immer, **außer** der Diff enthält ausschließlich Nicht-Code-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) und **keine** Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` (oder Äquivalent). |
| `requirements-engineer` | **Immer aktiv, unverändert.** | Kein Skip-Pfad — siehe Begründung. |
| `security-engineer` | **Echt bedingt.** | Diff enthält mind. eine Datei unter `backend/src/photosort/api/`, `backend/src/photosort/opencloud/`; **oder** eine der explizit benannten Auth-/Secrets-tragenden Dateien `backend/src/photosort/main.py`, `security.py`, `rate_limit.py`, `config.py`, `seed.py`; **oder** eine neue Datei direkt unter `backend/src/photosort/` (nicht in einem bestehenden Unterordner — mechanischer Fallback für künftige neue Top-Level-Module, die die explizite Liste noch nicht kennt); **oder** eine Dependency-Datei (`backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`); **oder** `.env.example`; **oder** eine Datei unter `.github/workflows/**` (nicht nur Netzwerkkonfiguration — Workflows referenzieren Secrets und steuern Merge-/Push-Rechte); **oder** Docker-Compose-Netzwerkkonfiguration; **oder** eine Datei unter `frontend/src/auth/**` bzw. `frontend/src/api/client.ts` (Token-Handling/API-Client, unabhängig vom `ux-ui-designer`-Frontend-Trigger, der nur Design-System-Konformität prüft, keine Bedrohungsmodellierung). |
| `architect` | **Echt bedingt.** | Diff enthält neue Dateien/ein neues Modul; **oder** `specs/decisions/**`; **oder** Datenmodell-/Migrations-Dateien (`backend/alembic/**`); **oder** eine neue externe Abhängigkeit; **oder** der Abschnitt "Architektur / Umsetzung" der Spec ist nicht trivial (nicht "Wiederverwendung von X, 1–2 Dateien"). |
| `ux-ui-designer` | **Unverändert** (bestehendes Vorbild). | Diff enthält Dateien unter `frontend/`. |

Für den Orchestrator zusätzlich relevant (nicht rein mechanisch aus `git diff --name-only` ableitbar): der `architect`-Trigger "Abschnitt Architektur/Umsetzung nicht trivial" verlangt, diesen Spec-Abschnitt selbst zu lesen.

Sicherheitsnetz für diese Tabelle: **im Zweifel läuft der Agent, und zwar mit Standardmodell** — eine unklare Zuordnung ist niemals ein Grund, einen Agenten zu überspringen oder auf Haiku herabzustufen. Trifft für einen Agenten kein Trigger zu, aber die Zuordnung ist unklar (z.B. eine neue Datei an einer nicht eindeutig zuordenbaren Stelle): der Agent läuft trotzdem, im späteren Findings-Bericht explizit "Trigger unklar, deshalb ausgeführt" vermerken statt es stillschweigend als "läuft ohnehin" zu verbuchen.

**Modell je aufgerufenem Agenten** (Modell-Spalte unverändert, nur die Aufrufer-Spalte ist hier aktualisiert):

| Bisherige Zuständigkeit | Jetzige Zuständigkeit | Modell (unverändert) |
|---|---|---|
| `developer` Schritt 1 → `architect` (Umsetzungsplanung, bei Bedarf) | Orchestrator (nach "Blockiert"-Rückmeldung von `developer`) → `architect` | Standard |
| `developer` Schritt 4 → `test-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `test-engineer` | Standard |
| `developer` Schritt 4 → `security-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `security-engineer` | Standard |
| `developer` Schritt 4 → `architect` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `architect` | Standard |
| `developer` Schritt 4 → `requirements-engineer` (Review) | Orchestrator (nach `developer`-Abschlussbericht) → `requirements-engineer` | Günstig (Haiku) |
| `developer` Schritt 4 → `ux-ui-designer` (Review, bedingt) | Orchestrator (nach `developer`-Abschlussbericht) → `ux-ui-designer` | Günstig (Haiku) |

Für Schritt 4 dieses Skills (der eigentliche Agent-Tool-Aufruf) konkret: `test-engineer`, `security-engineer`, `architect` ohne `model`-Parameter (Standard); `requirements-engineer`, `ux-ui-designer` mit `model: "haiku"` (Günstig) — **`security-engineer` nie herabstufen**, auch nicht bei kleinem/trivial wirkendem Diff.

## Schritt 4: Review-Agenten parallel aufrufen, auf alle warten

Starte die laut Schritt 3 ermittelten Agenten **parallel**, jeweils mit dem festgelegten `model`-Wert, in einem einzigen Aufruf (alle Agent-Tool-Aufrufe in derselben Nachricht), alle im Vordergrund/`run_in_background: false`. Prüfumfang je Agent, wenn er läuft:

- **`test-engineer`** (`subagent_type: test-engineer`): Abdeckung der Akzeptanzkriterien, Testqualität, Abgleich mit dem Testkonzept (`specs/architecture/0002-testkonzept.md`), klassische Bugs/Logikfehler und Abweichungen von Code-Konventionen. Prüft dabei zusätzlich (dauerhafte Stichproben-Audit-Pflicht laut Testkonzept, Sektion "Agenten-Steuerungslogik selbst"), ob dein Skip-/Modell-Protokoll aus Schritt 3 tatsächlich zur Trigger-/Modelltabelle und zum real ermittelten Diff passt.
- **`security-engineer`** (`subagent_type: security-engineer`): Sicherheitsprobleme (OWASP-relevante Muster, Secrets, Eingabevalidierung, Auth-Durchsetzung), Abgleich mit dem Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`).
- **`architect`** (`subagent_type: architect`): ob die Architekturentscheidungen (ADRs, `docs/architecture.md`, Abschnitt "Architektur / Umsetzung" der Spec) eingehalten wurden, bewertet aus drei Blickwinkeln (Pragmatiker, Senior-Entwickler, Pedant).
- **`requirements-engineer`** (`subagent_type: requirements-engineer`): Anforderungstreue — sind alle Akzeptanzkriterien der Spec umgesetzt, wurde nichts (Scope Creep) oder etwas explizit als "Out of Scope" Ausgeschlossenes zusätzlich gebaut.
- **`ux-ui-designer`** (`subagent_type: ux-ui-designer`, nur wenn getriggert): Konsistenz mit dem Design-System (`specs/architecture/0004-design-system.md`), Usability, abgedeckte Zustände (leer/ladend/Fehler), Barrierefreiheit, Responsivität.

**Warte auf alle gestarteten Agenten**, bevor du weitermachst — kein Teil-Fix-Loop pro Einzelagent, kein SendMessage an `developer`, bevor nicht sämtliche Ergebnisse vorliegen.

**Qualitäts-Beobachtung der Haiku-Stufe (dauerhaft, kein einmaliges Gate):** Stellt sich im selben PR-Zyklus (Copilot-Review in Schritt 8, ein anderer Standard-Review-Agent, oder ein zeitnaher Folge-Bugfix) heraus, dass ein von `requirements-engineer`(Haiku) oder `ux-ui-designer`(Haiku) als erfüllt/konform bewertetes Kriterium tatsächlich nicht erfüllt/konform war, ist das kein normaler Fund: vermerke es explizit im Abschlussbericht an den Nutzer und benenne es als Auslöser für eine neue, ADR-0014/0024-ablösende ADR (Rückstufung der betroffenen Aufrufstelle auf Standard) — nicht nur als einzelnes Finding beheben und weitermachen.

## Schritt 5: Findings sammeln und per SendMessage zurückspielen

Führe alle Findings-Listen zusammen. Gib zuerst eine kurze Statusmeldung aus — für **jeden** der fünf Review-Agenten (nicht nur die gelaufenen): gelaufen ja/nein; bei "nein" der konkrete Trigger-Tabelleneintrag, der nicht zutraf; bei "ja" die Anzahl der Findings, ein Stichwort/Kurztitel je Finding (Must-Fix vs. nice-to-have kenntlich machen) sowie das verwendete Modell (Standard/Haiku), ggf. "Trigger unklar, deshalb ausgeführt".

Schick die gesammelte, konsolidierte Findings-Liste anschließend per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten (nicht an einen neuen Lauf) — er arbeitet sie über seinen Schritt 5 ("Findings beheben") ab, wiederholt seinen Qualitätscheck, committet, und antwortet mit dem Folgebericht `## Abschlussbericht (Folgeauftrag: Findings behoben)`.

Schlägt `SendMessage` fehl: siehe Abschnitt "Recovery" unten.

## Schritt 6: Folgebericht auswerten

Format:

```
## Abschlussbericht (Folgeauftrag: Findings behoben)

**Feature-Branch:** <Name, zur Bestätigung>
**Commit-Stand:** sauber, alles committet

### Behobene Findings
<Liste>

### Bewusst nicht behoben
<Liste mit Begründung, oder "keine">

### Tests & Codequalität
<erneut grün>
```

Verifiziere Branch/Status/Diff erneut mechanisch wie in Schritt 2 (dieselben drei Prüfungen). Findings, die laut Bericht "bewusst nicht behoben" wurden: kurz eigenständig plausibilisieren (nicht blind übernehmen) — wirkt die Begründung tragfähig, akzeptieren und im späteren PR-Bericht vermerken; wirkt sie nicht tragfähig, per SendMessage nachfragen/insistieren, bevor es weitergeht.

Kein eigener erneuter Testlauf durch den Orchestrator (bewusste Rollenteilung: TDD bleibt bei `developer`, Testqualität wird von den Review-Agenten geprüft) — "Tests & Codequalität: grün" im Bericht wird als Aussage übernommen, nicht selbst nachgestellt.

Nach Bestätigung geht es weiter zu Schritt 7 (PR-Erstellung) bzw., falls die Findings aus einer Copilot-Runde (Schritt 8) stammten, zurück in den Copilot-Ablauf (erneuter Push statt neuem PR).

## Schritt 7: Commit, Push, Pull Request

Inhaltlich unverändert gegenüber dem bisherigen `developer.md` Schritt 7, nur beim Orchestrator statt beim Subagenten ausgeführt (er hat den GitHub-Zugriff, dieselbe Arbeitskopie):

1. Falls seit dem letzten Zwischencommit noch uncommittete Änderungen bestehen: committen, mit der im Projekt üblichen Commit-Konvention (siehe `CLAUDE.md`, Conventional Commits).
2. Push den Feature-Branch (`git push -u origin <branch>`), nicht `main`.
3. Eröffne einen PR mit `gh pr create`. Halte dich an eine vorhandene `.github/pull_request_template.md`, sonst mindestens: Bezug zur Spec/zum Issue, kurze Zusammenfassung (Was und Warum), Testplan/was geprüft wurde.
4. Setz direkt danach das Board-Statusfeld der Spec auf `Review` (ADR [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](../../../specs/decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md), Abschnitt 4):

   ```bash
   PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "Review" --pr-number <PR-Nummer>
   ```

   Ein früherer, verfrühter `Implemented`-Bump des Spec-Status direkt nach der PR-Erstellung entfällt ersatzlos (ADR 0037, Abschnitt 4) — die eigentliche Finalisierung (Spec-Datei-Status auf `Implemented`) übernimmt seit ADR 0037 die automatische PR-Merge-Erkennung beim nächsten regulären `github-project-sync`-Lauf, siehe `.claude/skills/github-project-sync/SKILL.md` (Fall `finalized_from_pr`).

## Schritt 8: Copilot-Review anfordern und auswerten

Inhaltlich unverändert gegenüber dem bisherigen `developer.md` Schritt 8, nur beim Orchestrator statt beim Subagenten ausgeführt. Jeder PR mit mindestens einer Code-Datei im Diff (mind. eine Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` oder Äquivalent) bekommt zusätzlich zu Schritt 3–5 ein automatisiertes Copilot-Review — feste Projektkonvention (`CLAUDE.md`), kein optionaler Schritt. **Ausnahme:** Ändert der PR ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ohne jede Code-Datei, entfällt dieser gesamte Schritt (kein Anfordern, kein Warten, kein Auswerten) — im Abschlussbericht an den Nutzer kurz vermerken, dass Schritt 8 aus diesem Grund übersprungen wurde.

1. **Anfordern:** `gh pr edit <PR-Nummer> --add-reviewer "@copilot"` direkt nach dem Eröffnen des PR in Schritt 7 (nur falls die obige Bedingung zutrifft).
2. **Warten:** Copilot braucht üblicherweise ein bis wenige Minuten. Poll in angemessenen Abständen (z.B. alle 20-30s, mit vernünftigem Timeout statt endlos) `gh pr view <PR-Nummer> --json reviewRequests,reviews` — fertig ist es, sobald `reviewRequests` keinen Copilot-Eintrag mehr enthält bzw. `reviews` einen Eintrag mit `author.login == "copilot-pull-request-reviewer"` zeigt. Nicht selbst raten/simulieren, was das Review ergibt.
3. **Kommentare holen:** `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments --paginate` liefert die Inline-Findings (Autor `Copilot`).
4. **Bewerten wie jeden anderen Review-Fund:** Jeden Kommentar am tatsächlichen Code prüfen (lesen, nicht nur den Kommentartext glauben) — echtes Problem oder Fehlalarm/bereits abgedeckt? Bei echten Findings: per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zur Behebung geben (Test zuerst, falls eine Testlücke der Grund war, dann Fix, dann Commit — gleicher Maßstab wie Schritt 5/6), warten auf den Folgebericht. Bei Fehlalarmen: kurz im Abschlussbericht an den Nutzer begründen, warum kein Fix nötig war, statt kommentarlos zu ignorieren.
5. **Nach Fixes:** erneuter Push (kein neuer PR nötig, derselbe Branch).
6. **Antworten:** Auf jeden Copilot-Kommentar per `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments/<comment-id>/replies -f body="..."` kurz antworten — was gefixt wurde (mit Commit-Referenz) oder warum bewusst nicht.

## Recovery: `SendMessage` schlägt fehl

Ist das Subagenten-Fenster des `developer`-Laufs bereits geschlossen (z.B. Timeout, Sitzung beendet) und `SendMessage` liefert keine Antwort/schlägt sichtbar fehl — insbesondere relevant bei der ggf. längeren Wartezeit bis zum Copilot-Review in Schritt 8 —, nicht stillschweigend scheitern lassen und nicht die gesammelten Findings verwerfen:

1. Findings/offene Punkte (aus Review-Runde und/oder Copilot) vollständig schriftlich festhalten, bevor irgendetwas anderes passiert.
2. Aktuellen Branch-/Commit-Stand prüfen (`git status`, `git log -1`) — der bisherige Fortschritt bleibt im Feature-Branch erhalten, unabhängig vom Subagenten-Fenster.
3. Neuen `developer`-Lauf starten (Agent-Tool, `subagent_type: developer`, Standard-Modell), diesmal mit explizitem Kontext-Reload im Prompt: Spec-Nummer/-Pfad, exakter Feature-Branch-Name (Hinweis, dass er bereits existiert und weiterverwendet werden soll, nicht neu von `main` abgezweigt wird), sowie die vollständige Liste der in Schritt 1 dieses Recovery-Abschnitts festgehaltenen, noch offenen Findings. Der neue Lauf beginnt effektiv beim Folgeauftrag "Findings beheben" (siehe `developer.md`) mit bereits vorhandenem Branch, nicht bei dessen Schritt 0.
4. Danach normal mit Schritt 6 dieses Skills weitermachen (Folgebericht auswerten).

## Abschlussbericht an den Nutzer

Nach Abschluss (PR eröffnet, Copilot-Review ausgewertet oder aus genanntem Grund übersprungen) fasse für den Nutzer zusammen: PR-Link, Review-Protokoll (alle fünf Agenten, gelaufen ja/nein mit Begründung, Modell, Findings-Kurzfassung inkl. behobener/bewusst nicht behobener), Copilot-Ergebnis (falls gelaufen), sowie jede Stelle, an der du selbst eine technische Detailentscheidung getroffen hast (z.B. bei einem nicht-exakten Anker-Match oder einem SendMessage-Recovery-Fall).
