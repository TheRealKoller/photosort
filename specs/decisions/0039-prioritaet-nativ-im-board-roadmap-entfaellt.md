# 0039 - Priorität wird nativ im GitHub-Project-Board gepflegt, `specs/roadmap.md` entfällt

**Status:** Accepted
**Datum:** 2026-08-28
**Bezug:** Story [#224](https://github.com/TheRealKoller/photosort/issues/224) ("Roadmap.md entfernen, Priorität direkt im GitHub-Project-Board pflegen", Status `Ready`), `architect`-Konsultation im `spec-writer`-Ablauf für die zugehörige künftige Feature-Spec. Löst Teile von ADR [`decisions/0017-github-projects-v2-spec-sync.md`](./0017-github-projects-v2-spec-sync.md) ab (siehe Abschnitt "Abgelöste Vorentscheidungen"), berührt ADR [`decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md`](./0036-github-issue-natives-story-refinement-inbox-entfaellt.md) (Abschnitt 5, issue-referenzierte Roadmap-Zeilen) und ADR [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5, Verschieben der Roadmap-Zeile nach PR-Merge).

## Kontext

Priorität und Status offener Arbeit werden heute an zwei Stellen parallel geführt:

1. `specs/roadmap.md` — eine eingecheckte, vom `requirements-engineer`-Agenten gepflegte Markdown-Datei mit Prioritätstabellen (`### Offen — Hoch/Mittel/Niedrig`), einem Freitext-Abschnitt "Priorisierung" (Begründungshistorie), einer "Bereits umgesetzt"-Tabelle und Abhängigkeitsnotizen.
2. Dem GitHub-Project-Board (V2, "PhotoSort Roadmap") — ein interaktives, auch mobil bedienbares Kanban-Board mit den Custom Fields `Status` und `Priorität` (ADR 0017 Abschnitt 3).

Die Verbindung zwischen beiden ist heute eine bewusste Einbahnstraße (ADR 0017 Abschnitt 4): `scripts/github-project-sync` parst die Prioritätstabellen aus `roadmap.md` (`roadmap_parser.py::parse_roadmap_priorities`) und schreibt den abgeleiteten Wert bei jedem Sync-Lauf ins Board-Feld `Priorität` — eine im Board-UI direkt gesetzte Priorität wird beim nächsten Lauf wieder überschrieben. Die aus `roadmap.md` abgeleitete Priorität geht außerdem in den `push_state_hash` ein, damit eine reine Prioritätsänderung in `roadmap.md` als `pushed` klassifiziert wird.

Seit Issues/Board die primäre, tagesaktuelle Sicht auf offene Arbeit sind (ADR 0030/0036: `capture` legt Issues an, Refinement schreibt in den Issue-Body, kein Inbox-Datei-Sync mehr), ist `roadmap.md` überwiegend eine zweite, manuell synchron zu haltende Kopie derselben Priorisierungsinformation. Der Pflegeaufwand (jede geschärfte Story/Spec zusätzlich eintragen, nach einem PR-Merge die Zeile physisch von "Offen" nach "Bereits umgesetzt" verschieben) steht in keinem Verhältnis zum Mehrwert — das Board zeigt Priorität und Status ohnehin, interaktiv und mobil.

Diese ADR ist wie 0017/0030/0036/0037 eine Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst, kein Eingriff in PhotoSorts Technologie-Stack, Datenmodell oder Laufzeitsystem. Sie wird als ADR festgehalten, weil sie eine als architekturrelevant markierte Grundsatzentscheidung (ADR 0017, Priorität als roadmap-getriebene Einbahnstraße) revidiert.

## Entscheidung

### 1. Das GitHub-Project-Board ist die alleinige, verbindliche Quelle für Priorität

Die Priorität (`Hoch`/`Mittel`/`Niedrig`) eines offenen Story-Issues bzw. einer offenen Feature-Spec lebt ausschließlich im Board-Feld `Priorität` und wird dort von Daniel direkt im Board-UI gepflegt. Es gibt keine zweite, dateibasierte Repräsentation mehr.

### 2. `scripts/github-project-sync` fasst das Board-Feld `Priorität` nicht mehr an — weder schreibend noch lesend

Das Sync-Tool:

- **liest** `roadmap.md` nicht mehr (die Datei existiert nicht mehr) und leitet keine Priorität mehr ab,
- **schreibt** das Board-Feld `Priorität` nie — kein `set_item_single_select` und kein `clear_item_field` auf dem Prioritäts-Feld, weder im Vollauf, im `--only NNNN`-Lauf, im `--only issue:NNN`-Story-Lauf noch beim `--adopt-issue`-Übergang,
- **liest** das Board-Feld `Priorität` nicht zurück — die Priorität geht in keine Hash-/Klassifikationslogik ein.

Damit entfällt der bisherige "Priority-Push"-Pfad vollständig. Eine im Board gesetzte Priorität ist ab jetzt stabil — sie wird von keinem Sync-Lauf mehr überschrieben oder geleert.

Bewusst **nicht** gewählt: eine Variante, bei der das Tool über ein neues, rein schreibendes CLI-Flag (`--priority Hoch|Mittel|Niedrig`) einen Startwert setzt. Das würde die mit dieser ADR entfernte Kopplung "das Tool verwaltet Priorität" über einen anderen Eingabekanal wieder einführen, eine neue, subtile "danach nie wieder anfassen"-Semantik erzeugen und zusätzliche Tool-/Test-Oberfläche kosten — ohne echten Gewinn gegenüber einem Board-Klick, der auf genau die mobile Bedienbarkeit einzahlt, für die das Board in ADR 0017 eingeführt wurde.

### 3. Das Board-Feld `Priorität` bleibt selbstprovisionierend

`gh_adapter.py::ensure_fields` legt das Single-Select-Feld `Priorität` mit den Optionen `Hoch`/`Mittel`/`Niedrig` weiterhin an, falls es fehlt (unveränderte Selbstprovisionierung aus ADR 0017 Abschnitt 3). Das Tool schreibt das Feld nur nicht mehr — die Spalte muss aber für Daniels manuelle Pflege auf einem frisch angelegten Board vorhanden sein.

### 4. `specs/roadmap.md` wird ersatzlos gelöscht

Die Datei wird vollständig entfernt. Die darin enthaltene Priorisierungs-Begründungshistorie (Freitext-Abschnitt "Priorisierung"), die "Bereits umgesetzt"-Tabelle und die Abhängigkeitsnotizen zwischen Specs werden **nicht** in ein Ersatzformat überführt — der Verlust dieser Historie ist eine im Refinement der Story bewusst bestätigte Entscheidung. Kein anderer Automatismus konsumiert `roadmap.md` (verifiziert: einziger maschineller Leser ist `roadmap_parser.py`, das mit entfernt wird).

Der Status offener Arbeit bleibt nachvollziehbar über den `**Status:**`-Header der jeweiligen Spec-Datei bzw. den nativen Status-/Zustand des GitHub-Issues plus das Board. Die "Bereits umgesetzt"-Sicht wird durch den Board-Status `Done` und den `**Status:** Implemented ([PR #NNN])`-Header der Spec-Datei abgedeckt (Letzteren schreibt `sync.py` bei der PR-Merge-Erkennung ohnehin selbst, ADR 0037 Abschnitt 5 — unverändert).

### 5. `requirements-engineer` pflegt keine Roadmap-Datei mehr, bleibt aber Priorisierungs-Beratung

Die Rolle "über das einzelne Feature hinausblicken, Priorität/Reihenfolge/Abhängigkeiten im Blick behalten" bleibt bei `requirements-engineer`. Was entfällt, ist ausschließlich das Führen der Datei: der Agent empfiehlt eine Priorität und benennt Abhängigkeiten/Konflikte im Refinement- und Review-Kontext, trägt sie aber nicht mehr irgendwo ein — die Priorität setzt Daniel im Board. Die tiefergehende Klärung der Agenten-/Skill-Grenzen bleibt der abhängigen Story [#177](https://github.com/TheRealKoller/photosort/issues/177) vorbehalten; diese ADR macht nur den durch den Wegfall der Datei zwingend nötigen Minimal-Schnitt.

## Abgelöste Vorentscheidungen

- **ADR 0017 Abschnitt 4** — der die Priorität betreffende Teil der Einbahnstraße "Status/Priorität nur Spec/`roadmap.md` → Board" ist hiermit abgelöst: Priorität wird gar nicht mehr synchronisiert, sondern nativ im Board gepflegt. Der **Status**-Teil derselben Einbahnstraße (Datei-Status → Board-Baseline, ggf. verfeinert durch Laufzeit-Override) bleibt unverändert gültig (ADR 0037).
- **ADR 0017 Abschnitt 5/6** — die Aufzählung der geparsten Quellen nennt `specs/roadmap.md` als Prioritätsquelle und bezieht die Priorität in den `push_state_hash` ein; beides entfällt. Der Hash-basierte Konflikt-/Klassifikationsmechanismus selbst (committete Baseline, `created`/`pushed`/`pulled`/`conflict`/`unchanged`) bleibt für Status und Inhalts-Zone unverändert.
- **ADR 0036 Abschnitt 5** — der Batch-Prioritäts-Push für issue-referenzierte `roadmap.md`-Zeilen im Vollauf entfällt.
- **ADR 0037 Abschnitt 5** — der Schritt "bei erkannter PR-Finalisierung ruft der Skill `requirements-engineer`, der die Roadmap-Zeile von 'Offen' nach 'Bereits umgesetzt' verschiebt" entfällt (es gibt keine Zeile mehr zu verschieben). Das Umschreiben des Spec-Datei-Status auf `Implemented ([PR #NNN])` durch `sync.py` selbst und der `finalized_from_pr`-Signalwert bleiben unverändert.

ADR 0017, 0036 und 0037 bleiben im Übrigen `Accepted` und gültig — diese ADR editiert sie nicht nachträglich, sondern löst die oben einzeln benannten Abschnitte ab (gleiches Muster wie der Nachtrag in ADR 0017 selbst).

## Begründung

- **Eine Quelle statt zwei:** Die parallele Pflege von `roadmap.md` und Board war reiner Synchronisationsaufwand, seit das Board die primäre Sicht ist. Priorität dort zu pflegen, wo sie ohnehin angezeigt wird (interaktiv, mobil), ist die naheliegende Vereinfachung.
- **Tool fasst Priorität gar nicht mehr an (statt Board-Feld lesen):** Die Akzeptanzkriterien der Story legen fest, dass Priorität "direkt am GitHub-Project-Item gesetzt" und dort gepflegt wird. Für eine reine Anzeige/Weiterverarbeitung im Tool gibt es keinen Bedarf — kein Sync-Schritt, keine Klassifikation und kein Bericht hängen von der Priorität ab. Das Tool nicht lesen zu lassen, hält die Kopplung minimal und macht eine im Board gesetzte Priorität dauerhaft stabil.
- **Priorität-Feld weiter provisionieren:** kostet nichts, verhindert aber, dass ein frisch (selbst-)angelegtes Board ohne Prioritätsspalte dasteht.
- **Bewusster Historienverlust:** im Refinement bestätigt. Die Begründungshistorie war ein Freitext-Artefakt ohne maschinellen Konsumenten; ihr Wert sinkt, sobald Priorisierung laufend im Board statt in nachgehaltenen Absätzen passiert.
- **Minimal-Schnitt bei `requirements-engineer`:** Die umfassende Neuordnung der Agenten-/Skill-Verantwortungen ist explizit Story #177 (abhängig von dieser hier). Diese ADR ändert an `requirements-engineer` nur, was der Wegfall der Datei erzwingt.

## Konsequenzen

- **Gelöscht:** `specs/roadmap.md`, `scripts/github-project-sync/src/github_project_sync/roadmap_parser.py`, `scripts/github-project-sync/tests/test_roadmap_parser.py`.
- **`scripts/github-project-sync/`:** `hashing.py::push_state_hash` verliert den `priority`-Parameter (Hash nur noch aus Status + Inhalts-Zone). `sync.py` verliert die gesamte Prioritäts-Verdrahtung (`_apply_priority_only`, den `priority`-Parameter in `_apply_fields`/`_sync_one`/`_adopt_story_and_push_first_content`/`set_feature_runtime_status`/`sync_story`, den Batch-Push-Block im Vollauf, `SpecSyncResult.priority_warning`, die `parse_roadmap_priorities`-Aufrufe). `cli.py` verliert das `priority_warning`-Feld im JSON-Output. `gh_adapter.py`/`ProjectFields` behalten die Prioritäts-Feld-Provisionierung. Integrationstests (`test_sync_integration.py`, `test_cli.py`, `test_hashing.py`) entsprechend angepasst.
- **Einmaliger, selbstheilender Effekt beim ersten Sync-Lauf nach der Umstellung:** Bestehende `specs/.github-sync-state.json`-Einträge haben einen `pushed_state_hash`, der mit Priorität berechnet wurde. Da `push_state_hash` die Priorität nicht mehr einbezieht, weicht der neu berechnete Hash ab → jede getrackte Spec wird einmalig als `pushed` klassifiziert (Inhalts-Zone unverändert → kein `conflict`). Folge: ein identischer Re-Push von Issue-Body und Feldern, danach ist die Baseline wieder stabil. Kein Datenverlust, kein manueller Eingriff nötig.
- **Skills:** `.claude/skills/github-project-sync/SKILL.md` (Beschreibung, `priority_warning`-Behandlung, Batch-Push-Erwähnung, `finalized_from_pr` → kein `requirements-engineer`-Aufruf mehr zum Zeilenverschieben), `.claude/skills/refinement/SKILL.md` (Schritt 2 + Schritt zum Eintragen der `roadmap.md`-Prioritätszeile → stattdessen: Prioritäts-**Empfehlung** an Daniel, der sie im Board setzt), `.claude/skills/spec-writer/SKILL.md` (Schritt 4: kein Umtragen des Roadmap-Eintrags mehr), `.claude/skills/capture/SKILL.md` (Nebensatz "kein Roadmap-Eintrag" bleibt sinngemäß korrekt, ggf. Formulierung glätten).
- **Agent:** `.claude/agents/requirements-engineer.md` — Aufgabe 1 ("Roadmap pflegen") wird zu "Priorisierung/Reihenfolge/Abhängigkeiten beraten" ohne Datei-Pflege; Aufgabe 2 Schritt 4 (Eintrag in `roadmap.md`) entfällt; Beschreibung/Frontmatter entsprechend.
- **Doku:** `README.md` (Projektstruktur-Tabelle: `roadmap.md`-Verweis entfernen), `specs/README.md` (Struktur-Aufzählung Zeile `roadmap.md`, "Roadmap" in der `docs/`-vs-`specs/`-Abgrenzung), `docs/ai-workflow.md` (Agenten-Tabelle: Konzept-Dokument-Zelle für `requirements-engineer`). `docs/architecture.md` braucht **keine** architektonische Aktualisierung (dev-Prozess-Tooling, kein System-/Datenmodell betroffen — analog ADR 0017); lediglich der historische Inline-Link `` `specs/roadmap.md` `` in der "Letzte Aktualisierung"-Prosa wird zu unverlinktem Text, damit kein toter Link zurückbleibt (die historische Aussage selbst bleibt unverändert).
- **Nicht Teil dieser ADR:** der volle bidirektionale Content-Sync für Feature-Specs (Inbox-Idee [`specs/inbox/0042`](../inbox/0042-adr-0017-content-sync-vereinfachen.md)) und die Überarbeitung `developer`/`ship-feature` bleiben unangetastet. Die tote `push_state_hash_inbox`-Hilfsfunktion (seit Spec 0059 ohne Aufrufer) wird hier nicht mit aufgeräumt, um den PR fokussiert zu halten.
- Ein späterer Wiedereinstieg in eine dateibasierte oder tool-verwaltete Priorität bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
