# 0017 - Zwei-Wege-Sync Feature-Specs ↔ GitHub Project (V2)

**Status:** Accepted
**Datum:** 2026-08-09
**Bezug:** `idea-sharpener`-Konsultation für die künftige Feature-Spec zu `specs/inbox/0011-zweiwege-sync-specs-github-projekt.md` (Spec-Nummer zum Zeitpunkt dieser ADR noch nicht vergeben).

## Kontext

Daniel möchte den Status (`Proposed`/`Accepted`/`Implemented`/`Superseded`) und die Priorität (`Hoch`/`Mittel`/`Niedrig`) aller Feature-Specs unter `specs/features/` zusätzlich zur bestehenden `specs/roadmap.md`-Tabellenansicht in einem interaktiven, auch mobil bedienbaren GitHub-Project-Board sichtbar haben (ein Issue/eine Card pro Spec-Datei, 1:1), und inhaltliche Änderungen, die er direkt in einem Issue vornimmt (typischer Fall: unterwegs am Handy), in die zugehörige Spec-Datei zurückspielen können. Eine frühere, statische D2-Kanban-Grafik in `roadmap.md` (Spec 0026) wurde in PR #53 wieder verworfen — dieses Feature ist bewusst etwas anderes (ein echtes, interaktives, extern editierbares Board), kein Wiederaufguss.

Randbedingungen, mit Daniel bereits geklärt (siehe zugehörige Spec):

- Ausschließlich session-getriggert (Daniel fragt in einer laufenden Claude-Code-Session danach) — kein Webhook, kein Scheduled Job, keine neue CI-Automatisierung. Ausdrücklich **keine** Vorstufe/kein Ersatz für die in `CLAUDE.md` beschriebene, noch nicht existierende "Hintergrund-Automatisierung (Ausbaustufe)".
- Kein bestehender Bestand — weder Project noch Issues existieren im Repo `TheRealKoller/photosort`, komplette Neuanlage.
- Es gibt keinen dedizierten `GH_TOKEN`/Bot-Account im Projekt; alle bisherige `gh`-Nutzung (z.B. Branch-Protection-Setup in Spec/ADR 0007) lief über die bereits authentifizierte lokale `gh`-CLI-Session des jeweiligen Agenten.
- Konfliktfall (Spec-Datei und Issue seit letztem Sync beide geändert) muss erkannt, nicht stillschweigend aufgelöst werden.
- Nur `specs/features/*.md` wird gesynct — Inbox-Einträge (`specs/inbox/`) haben keine Board-Repräsentation, da sie noch keinen Status/keine Priorität im Sinne des Feature-Lifecycles besitzen (siehe `specs/README.md`).

Umgebungscheck: `gh` (installiert, Version 2.97.0) bringt bereits native `gh project`/`gh issue`-Subcommands für GitHub Projects (V2) mit (`gh project create`, `field-list`, `field-create`, `item-add`, `item-edit`, u.a.) — keine rohe GraphQL-Query nötig. `gh project --help` weist selbst darauf hin, dass der lokale Token/die Session den Scope `project` benötigt (`gh auth refresh -s project`), der beim ursprünglichen `gh auth login` typischerweise nicht automatisch gesetzt ist.

Diese ADR ist wie 0007/0013/0016 eine Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst (Verwaltung der Specs), keine Änderung an PhotoSorts eigenem Technologie-Stack/Datenmodell/Laufzeitsystem — wird aber als ADR festgehalten, da eine neue externe Abhängigkeit (GitHub Projects V2 als Datenspeicher) sowie ein neues, dauerhaftes Sync-/Konfliktmodell eingeführt werden.

## Entscheidung

### 1. Komponente: neuer Skill `github-project-sync`, kein Ausbau von `requirements-engineer` zum Sync-Ausführer

Ein neuer Skill `.claude/skills/github-project-sync/SKILL.md` ist der Einstiegspunkt für "sync jetzt mit GitHub" u.ä. Er orchestriert den mechanischen Zwei-Wege-Abgleich (siehe Abschnitt 2–4) über ein dediziertes, getestetes Python-Skript (siehe Abschnitt 5), meldet Konflikte an Daniel zurück (kein Auto-Resolve) und delegiert **ausschließlich** die fachliche Bewertung zurückgespielter Inhaltsänderungen an `requirements-engineer` (neue, schmale "Aufgabe 4" in dessen Agentendatei, siehe Konsequenzen) — der Skill selbst trifft keine Anforderungsentscheidung.

Begründung gegen "der `requirements-engineer`-Agent führt den Sync direkt aus": der Sync ist mechanischer, deterministischer Datenabgleich (Markdown parsen, Hashes vergleichen, `gh`-Aufrufe orchestrieren) — kein Anforderungsurteil. Ein Skill lädt sich direkt in den aufrufenden Kontext (typischerweise den Hauptchat, wo Daniel den Sync explizit auslöst) statt einen zusätzlichen Subagenten-Hop zu erzeugen — passend zum bereits etablierten Skill-Muster für explizit, synchron ausgelöste Abläufe (`capture`, `idea-sharpener`) und ohne die in ADR 0014 dokumentierten Kontingent-Kosten eines weiteren Subagenten-Aufrufs für reine Mechanik. Die fachliche Bewertung ("braucht das erneutes Sharpening?") bleibt dagegen genau die Art von Urteilsarbeit, die laut Rollenmodell bei `requirements-engineer` liegt — dafür wird er weiterhin (wie in allen anderen Aufgaben) gezielt per `Agent`-Tool aufgerufen, nur eben punktuell pro betroffener Spec, nicht als Sync-Motor.

### 2. Credentials: bestehende `gh`-CLI-Session, kein neuer Bot-Token

Kein neuer `GH_TOKEN` in `.env.example`, keine neue Secrets-Infrastruktur. Der Sync läuft über die bereits authentifizierte lokale `gh`-Session des jeweiligen Agenten — identisches Muster wie in Spec/ADR 0007 etabliert. Einzige zusätzliche Voraussetzung: der Scope `project` muss auf dieser Session vorhanden sein (`gh auth refresh -s project`, einmalig pro Umgebung). Das Sync-Skript prüft das selbst zu Beginn (`gh auth status` parsen) und bricht mit einer klaren, auf `gh auth refresh -s project` verweisenden Fehlermeldung ab, falls der Scope fehlt — analog zur bereits etablierten Fehlerbehandlung in `scripts/render-diagrams.sh` bei fehlendem `d2`-Binary (ADR 0013). Kein Docs-Update in `docs/setup.md` nötig (siehe Begründung/Konsequenzen) — konsistent mit ADR 0013, die den lokalen `d2`-Bedarf ebenfalls nicht dort, sondern direkt im jeweiligen Tooling dokumentiert.

### 3. Datenmodell auf GitHub: ein Project, native `gh project`-Felder, Issue-Body als Inhalts-Spiegel

- Genau ein GitHub Project (V2), Owner `TheRealKoller` (persönlicher Account, kein Org), Titel "PhotoSort Roadmap". Wird beim ersten Sync-Lauf **selbstprovisionierend** angelegt, falls es noch nicht existiert (`gh project list --owner TheRealKoller` prüfen, sonst `gh project create`) — kein manueller GitHub-seitiger Einrichtungsschritt außer dem `gh auth refresh -s project` aus Abschnitt 2.
- Zwei Custom Fields (ebenfalls selbstprovisionierend über `gh project field-create`, falls fehlend):
  - `Status` (Single-Select): `Proposed`, `Accepted`, `Implemented`, `Superseded` — Werte 1:1 aus dem Feature-Lifecycle (`specs/README.md`).
  - `Priorität` (Single-Select): `Hoch`, `Mittel`, `Niedrig` — Werte 1:1 aus `specs/roadmap.md`.
- Zusätzlich wird der native GitHub-Issue-Zustand (`open`/`closed`) als grobe visuelle Kanban-Gruppierung mitgeführt: `Proposed`/`Accepted` → offen, `Implemented`/`Superseded` → geschlossen (`gh issue close`/`reopen` je nach Spec-Status).
- **Ein Issue pro Spec-Datei**, Titel `[NNNN] <Spec-Titel>` (Menschen-lesbar, **nicht** die technische Identitäts-Grundlage). Issue-Body: erste Zeile ein versteckter Marker `<!-- photosort-spec: NNNN -->` (technische, robuste 1:1-Identität — übersteht Titel-Umbenennungen und ist unabhängig von Custom-Field-Konfiguration abfragbar), danach der gespiegelte Spec-Inhalt (siehe Abschnitt 4).
- Kein rohes `gh api graphql` nötig — ausschließlich native `gh project`/`gh issue`-Subcommands (kleinere, stabilere Angriffsfläche als selbstgebaute GraphQL-Queries).

### 4. Richtung explizit getrennt und technisch erzwungen: Status/Priorität nur Spec/Roadmap → Board, Inhalt bidirektional

- **Status/Priorität sind bewusst Einbahnstraße** Spec-Datei/`roadmap.md` → Board-Felder — reine Anzeige. Auch wenn GitHub UI es erlaubt, das Single-Select-Feld direkt zu ändern oder eine Card zwischen Kanban-Spalten zu ziehen: der Sync liest diese Felder **nie zurück**, ein nachfolgender Lauf überschreibt sie wieder mit dem aus Spec-Datei/`roadmap.md` abgeleiteten Wert. Grund: Status-Übergänge (`Accepted` durch Daniels Freigabe im Chat, `Implemented` durch `developer`) laufen bereits über einen etablierten, bewussten Prozess (`CLAUDE.md`) — ein Drag-and-Drop auf dem Board soll diesen Prozess nicht stillschweigend umgehen können. Diese Einschränkung wird in der Card-/Feld-Beschreibung auf GitHub selbst dokumentiert (kurzer Hinweistext beim jeweiligen Feld), damit sie für Daniel nicht überraschend ist.
- **Nur der Inhalt unterhalb des Metadaten-Blocks ist bidirektional.** Jede Spec-Datei beginnt (siehe `specs/TEMPLATE.md`) mit `# NNNN - Titel` gefolgt vom Metadaten-Block (`**Status:**`/`**Erstellt:**`/`**Bezug:**`). Beim Zurückspielen einer Issue-Body-Änderung in die Spec-Datei bleiben H1-Titel und Metadaten-Block der lokalen Datei unangetastet — nur der Teil ab der ersten `##`-Überschrift (`## Ziel`) wird durch den entsprechenden Abschnitt des Issue-Bodys ersetzt. Ändert Daniel den Metadaten-Block versehentlich im Issue mit, wird das ignoriert (bewusst kein Fehler, kein Blocker — es wird beim nächsten Push ohnehin wieder mit dem korrekten, aus der Spec-Datei stammenden Block überschrieben).

### 5. Sync-Logik als dediziertes, getestetes Python-Tool statt Ad-hoc-Bash im Skill

Neues, eigenständiges Python-Package `scripts/github-project-sync/` (eigene `pyproject.toml`, getrennt von `photosort-demo-scripts`) — analog zur bereits in ADR 0013 etablierten Begründung, unabhängige Tooling-Anliegen nicht in ein gemeinsames Package zu zwingen. Enthält:

- Parsing von `specs/features/*.md` (Metadaten-Block, Inhalts-Zone) und `specs/roadmap.md` (Abschnitt "Status auf einen Blick", Tabellen je `### Offen — <Priorität>`-Unterüberschrift — **nicht** der freitextige Abschnitt "Priorisierung", der für menschliche Begründung gedacht, nicht maschinell robust parsbar ist).
- Hashing/Diff-Klassifikation je Spec (siehe Abschnitt 6) als reine, ohne Netzwerk testbare Funktionen.
- Ein dünner Adapter-Layer, der `gh issue`/`gh project`-Subcommands via `subprocess` aufruft (nicht live in Unit-Tests ausgeführt, gemockt/injiziert).
- Eigene `tests/` — deterministische Parsing-/Hashing-/Konflikt-Logik ist genau der Teil, der nicht bei jedem Lauf neu von einem Agenten ad-hoc nachgebildet werden soll (Fehler-/Drift-Risiko), sondern wie normale Anwendungslogik durch Tests abgesichert wird. Konkrete Testabdeckung/-strategie legt `test-engineer` im weiteren `idea-sharpener`-Ablauf fest (nicht Teil dieser ADR).

Der Skill (`.claude/skills/github-project-sync/SKILL.md`) ruft dieses Skript auf, interpretiert dessen strukturierte Ausgabe (pro Spec: `unchanged`/`pushed`/`pulled`/`conflict`/`created`) und übernimmt die Kommunikation mit Daniel (Konflikt-Rückfrage, Zusammenfassung, ggf. Aufruf von `requirements-engineer` bei `pulled`).

### 6. Zustands-/Konflikterkennung: committeter Hash-Snapshot statt Zeitstempel-Heuristik

Eine einzige, ins Git-Repository eingecheckte Zustandsdatei `specs/.github-sync-state.json` (JSON, ein Eintrag pro Spec-Nummer: `issue_number`, `item_id`, `pushed_state_hash`, `pulled_body_hash`, `last_synced_at`). Eingecheckt statt `.gitignore`-lokal, weil sie — wie alles unter `specs/` — Teil der Quelle der Wahrheit ist und über Sessions/Klone hinweg konsistent bleiben muss; kein separater Daemon/State-Server nötig, passend zum rein session-getriggerten Betrieb.

Bei jedem Sync-Lauf, pro Spec:

1. `push_hash_now` = Hash aus (Status-Zeile der Spec-Datei, aus `roadmap.md` abgeleitete Priorität, Inhalts-Zone der Spec-Datei ab `## Ziel`).
2. `pull_hash_now` = Hash der Inhalts-Zone des aktuellen Issue-Bodys (ab dem Marker-Kommentar, exklusive Metadaten-Zeilen).
3. Vergleich beider mit den gespeicherten Baseline-Hashes (`pushed_state_hash`/`pulled_body_hash`):
   - Kein Eintrag vorhanden → **`created`**: Issue neu anlegen, zum Project hinzufügen, Felder setzen.
   - Nur `push_hash_now` weicht ab → **`pushed`**: Issue-Body/Felder/Issue-Zustand (offen/geschlossen) aus der Spec-Datei aktualisieren.
   - Nur `pull_hash_now` weicht ab → **`pulled`**: Inhalts-Zone der Spec-Datei aus dem Issue-Body übernehmen (Metadaten-Block bleibt unangetastet, siehe Abschnitt 4); `requirements-engineer` wird vom Skill zur Bewertung aufgerufen.
   - Beide weichen ab → **`conflict`**: keine Seite wird automatisch überschrieben. Der Skill zeigt Daniel beide Diffs und lässt ihn entscheiden (Spec behalten / Issue-Inhalt übernehmen / manuell zusammenführen); die Baseline-Hashes werden erst nach expliziter Auflösung aktualisiert — ein erneuter Lauf ohne Auflösung meldet denselben Konflikt erneut (sicherer Default, kein stilles Verwerfen).
   - Keine Abweichung → **`unchanged`**.

Diese Grundstruktur (Hash-Vergleich gegen eine committete Baseline statt Zeitstempel) ist robuster als ein reiner `updated_at`-Vergleich, da Zeitstempel bei parallelen/asynchronen Edits (Daniel bearbeitet ein Issue, während gleichzeitig lokal am Spec-Text gearbeitet wird) keine zuverlässige Kausalitätsaussage treffen können — ein Hash-Diff gegen die zuletzt tatsächlich synchronisierte Fassung dagegen schon.

### 7. Neuanlage einer Spec erzeugt automatisch das Issue

Der letzte Schritt des `idea-sharpener`-Ablaufs (Anlage einer neuen `Accepted`-Spec) ruft künftig zusätzlich denselben Skill im Einzel-Spec-Modus auf (`github-project-sync --only NNNN`), statt einen eigenen Erzeugungspfad zu duplizieren — technisch identisch zum `created`-Fall aus Abschnitt 6, nur für eine einzelne, dem Skill explizit übergebene Spec-Nummer statt eines vollständigen Repo-Durchlaufs.

## Begründung

- **Skill statt Agent-Erweiterung als Sync-Motor:** siehe Abschnitt 1 — mechanischer Datenabgleich vs. fachliches Urteil sauber getrennt, kein zusätzlicher, für reine Mechanik unnötiger Subagenten-Hop (Kontingent-Kosten laut ADR 0014), passend zum bestehenden Skill-Trigger-Muster für explizit ausgelöste Abläufe.
- **Native `gh project`/`gh issue`-Subcommands statt roher GraphQL-Aufrufe:** `gh` (bereits in Version 2.97.0 vorhanden) deckt alle benötigten Operationen (Project/Field/Item anlegen und bearbeiten, Issue anlegen/bearbeiten/schließen) bereits ab — eine handgeschriebene GraphQL-Schicht wäre zusätzliche, fehleranfällige Komplexität ohne Mehrwert.
- **Bestehende `gh`-Session statt neuem Bot-Token:** konsistent mit dem in Spec/ADR 0007 bereits etablierten und bewusst gewählten Muster; ein dedizierter Automatisierungs-Token wäre zusätzliche Secrets-Infrastruktur für einen Anwendungsfall, der laut Randbedingung explizit nur innerhalb einer bereits von Daniel autorisierten, interaktiven Session läuft — kein eigenständiger Actor mit eigenem Schreibzugriff, der laut ADR 0007 ("`restrictions` weiterhin nicht gesetzt ... explizit zu revisitieren, sobald ein zweiter Actor mit Schreibzugriff hinzukommt") eine erneute Zugriffs-Bewertung auslösen würde.
- **Status/Priorität bewusst Einbahnstraße:** vermeidet eine strukturelle Verwechslungsgefahr (Kanban-Board suggeriert normalerweise, dass Ziehen einer Card den Status ändert) mit dem bereits etablierten, bewussten Status-Übergangs-Prozess in `CLAUDE.md`/`specs/README.md`. Eine Alternative (Board-Änderungen an Status/Priorität ebenfalls zurückspielen) hätte den in `CLAUDE.md` verankerten Freigabe-Prozess (Daniel gibt `Accepted` im Chat frei, `developer` setzt `Implemented`) am Board vorbei aushebeln können — nicht gewollt.
- **Committeter Hash-Snapshot statt Zeitstempel-Vergleich:** siehe Abschnitt 6 — robuster gegenüber echter Nebenläufigkeit zwischen lokaler Bearbeitung und Issue-Bearbeitung; Zustandsdatei im Repository hält den Sync-Zustand an derselben "Quelle der Wahrheit" wie alles andere unter `specs/`.
- **Kein Zurückspielen des Metadaten-Blocks:** macht Abschnitt 4 technisch verbindlich statt nur als Text-Konvention — ein versehentlich im Issue mitgeänderter Status-Text hat keine Wirkung, muss also nicht als eigener Fehlerfall behandelt werden.

## Konsequenzen

- Neue Datei `.claude/skills/github-project-sync/SKILL.md`.
- Neues Package `scripts/github-project-sync/` (`pyproject.toml`, Sync-Skript, `tests/`) — eigenständig, keine Abhängigkeit von `scripts/photosort-demo-scripts`.
- Neue, eingecheckte Datei `specs/.github-sync-state.json` (wird vom ersten Sync-Lauf angelegt).
- `.claude/agents/requirements-engineer.md`: neue, schmale "Aufgabe 4" (Bewertung, ob eine aus GitHub zurückgespielte Inhaltsänderung ein erneutes Sharpening/Refinement nötig macht) wird bei Umsetzung der zugehörigen Feature-Spec ergänzt.
- `.claude/skills/idea-sharpener/SKILL.md`: letzter Schritt ruft künftig zusätzlich `github-project-sync --only NNNN` für die neu angelegte Spec auf (siehe Abschnitt 7).
- **Kein** Effekt auf `docs/architecture.md`/`docs/setup.md`/`docs/ai-workflow.md`/`CLAUDE.md` — reine Prozess-/Tooling-Erweiterung für die Verwaltung von Specs, kein PhotoSort-System-/Datenmodell betroffen, analog zur Einordnung in ADR 0013 und ADR 0016. Insbesondere **keine** Berührung mit der in `CLAUDE.md` beschriebenen künftigen "Hintergrund-Automatisierung (Ausbaustufe)" oder der `approved-for-agent`-Label-Policy (Spec/ADR 0007) — dieser Sync bleibt strikt Daniel-session-getriggert, kein autonom laufender Agent, keine neue Trigger-Fläche für von Dritten erstellte Issues (im öffentlichen Repo können ohnehin nur von diesem Sync selbst erzeugte bzw. von Daniel bearbeitete Issues für Specs relevant werden).
- Voraussetzung für jede Umgebung, die den Sync ausführen soll: lokale `gh`-Session mit Scope `project` (`gh auth refresh -s project`, einmalig) — wird vom Sync-Skript selbst geprüft und bei Fehlen mit klarer Anleitung abgebrochen (kein stiller Fehlschlag).
- Ein späterer Wechsel des Grundprinzips (z.B. doch bidirektionale Status-Synchronisation, ein dedizierter Bot-Token statt der lokalen `gh`-Session, oder GraphQL statt `gh project`-Subcommands) bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
