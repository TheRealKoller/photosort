# 0052 - GitHub-Sync: natives Status-Feld statt Custom-Field, Inbox-Einbindung

**Status:** Implemented ([PR #173](https://github.com/TheRealKoller/photosort/pull/173))
**Erstellt:** 2026-08-21
**Bezug:** [`inbox/0028-github-sync-status-feld-und-inbox.md`](../inbox/0028-github-sync-status-feld-und-inbox.md), Feature [`0031`](./0031-zweiwege-sync-specs-github-projekt.md) (Implemented), ADR [`decisions/0017-github-projects-v2-spec-sync.md`](../decisions/0017-github-projects-v2-spec-sync.md) (Abschnitt 3 teilweise abgelöst, übrige Abschnitte weiter gültig), ADR [`decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md`](../decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md), `idea-sharpener`-Konsultation mit Daniel am 2026-08-21

## Ziel

Der bereits produktiv laufende Zwei-Wege-Sync (Spec 0031) zwischen `specs/features/*.md` und dem GitHub Project "PhotoSort Roadmap" soll zwei Dinge ändern: (1) statt eines eigenen Custom-Fields `Spec Status` wird das native, von GitHub automatisch angelegte Single-Select-Feld `Status` für den Spec-Lifecycle verwendet — damit ist "das richtige Feld mit den richtigen Werten" belegt und GitHub-Board-Views lassen sich einfacher darauf bauen; (2) auch `specs/inbox/*.md` (bisher explizit Out-of-Scope) wird 1:1 mit echtem Zwei-Wege-Sync erfasst, damit Daniel auch ungeschärfte Ideen/Bugs unterwegs im selben Board sieht und bearbeiten kann. `Superseded` verschwindet dabei als Feldwert und wird zusammen mit dem Inbox-`**Typ:**` (Idee/Bug) stattdessen über Repo-Labels abgebildet.

Reines Entwickler-/Prozess-Tooling für den KI-gesteuerten Entwicklungsworkflow selbst (analog zu Spec 0031), ohne jede Berührung mit der eigentlichen PhotoSort-Anwendung oder ihren Endnutzern.

## User Story

Als Daniel möchte ich den Spec-Lifecycle-Status direkt im nativen GitHub-`Status`-Feld sehen (statt in einem separaten Custom-Field) und auch Inbox-Einträge per echtem Zwei-Wege-Sync im selben GitHub Project verwalten können, damit ich einen einheitlichen, einfacher als Board-View baubaren Überblick über Specs *und* Rohideen habe — auch unterwegs am Handy.

## Akzeptanzkriterien

- [ ] **Natives Status-Feld statt Custom-Field:** Nach einem vollen Sync-Lauf mit dem neuen Code existiert im Project genau ein Single-Select-Feld namens exakt `Status` mit den Optionen `Proposed`/`Accepted`/`Implemented`/`Unrefined` (kein `Superseded` mehr als Feldwert). `ensure_fields()` erzeugt/erwartet kein Feld `Spec Status` mehr. Für Feature-Specs mit Status `Proposed`/`Accepted`/`Implemented` wird der Wert unverändert 1:1 ins (jetzt umbenannte) Feld geschrieben.
- [ ] **Superseded als Label, Feld geleert:** Für eine Spec mit `**Status:** Superseded` wird im selben Sync-Lauf sowohl das `Status`-Feld geleert (analog zum bestehenden Priorität-Leeren-Muster für Implemented/Superseded) als auch das Label `superseded` gesetzt; nativer Issue-Zustand bleibt geschlossen. Beide Effekte müssen gemeinsam nachgewiesen werden.
- [ ] **Inbox 1:1-Sync:** Für jede Datei unter `specs/inbox/*.md` existiert nach einem vollen Sync-Lauf genau ein Issue mit erster Body-Zeile `<!-- photosort-inbox: NNNN -->`, Status-Feld auf `Unrefined`. Das `Priorität`-Feld bleibt für Inbox-Items unberührt (nie gesetzt, nicht aktiv geleert).
- [ ] **Marker-Namespace-Trennung inkl. Cross-Namespace-Ablehnung:** `inbox/NNNN` und `features/NNNN` mit identischer Nummer (real vorkommend, z.B. `inbox/0004` und `features/0004`) erzeugen zwei getrennte Issues über zwei getrennte, jeweils hart auf den Entitäts-String geankerte Marker-Regexe (`photosort-spec` bzw. `photosort-inbox`) — keine gemeinsame, nur die Zahl extrahierende Parse-Funktion. Ein Issue mit `photosort-spec`-Marker wird vom Inbox-Sync-Pfad abgelehnt und umgekehrt, auch wenn die Nummer korrekt matcht.
- [ ] **Gelöschte Inbox-Datei → automatischer Issue-Close:** Symmetrisch zum bestehenden Feature-Verhalten (Spec 0031), mit eigenem, inbox-spezifischem Kommentartext ("Inbox-Eintrag wurde entfernt."), State-Eintrag im `inbox`-Namespace wird entfernt.
- [ ] **Zwei-Wege-Content-Sync für Inbox:** Inhaltsänderungen im Issue-Body fließen ab `## Rohtext` in die Inbox-Datei zurück (analog `## Ziel` bei Specs), Metadaten (`**Typ:**`/`**Erfasst:**`/`**Status:**`) bleiben unangetastet. Die bestehende Vier-Wege-Klassifikation (`created`/`pushed`/`pulled`/`conflict`/`unchanged`) gilt unverändert auch für Inbox-Einträge (Wiederverwendung, keine Duplikation der Klassifikationslogik). Ein `conflict`-Fall bei einem Inbox-Eintrag wird identisch zum bestehenden Feature-Konfliktverhalten behandelt (Daniel entscheidet, keine Seite wird automatisch überschrieben).
- [ ] **`idea-sharpener`-Übergang:** `github-project-sync --only NNNN --supersede-inbox MMMM` schließt gezielt das Inbox-Issue `MMMM` mit einem auf die neue Spec-Issue `NNNN` verlinkenden Kommentar und entfernt dessen State-Eintrag; alle anderen Einträge im selben Lauf bleiben unberührt. Fehlt für `MMMM` ein State-Eintrag (Tippfehler/bereits erledigt), bricht der Befehl mit einer klaren Fehlermeldung ab statt stillem No-op.
- [ ] **State-Datei-Migration:** Ein altes, flaches `specs/.github-sync-state.json` (`{"NNNN": {...}}`) wird beim ersten Lauf mit neuem Code transparent als `{"features": <alt>, "inbox": {}}` gelesen; anschließendes Schreiben erfolgt immer im neuen genesteten Format. Bereits bekannte Feature-Einträge werden dabei nicht fälschlich als `created` neu klassifiziert.
- [ ] **Label-Self-Provisioning:** `idee`/`superseded` werden bei Bedarf neu angelegt, das bereits im Repo existierende Label `bug` wird für Inbox-Bugs wiederverwendet (kein Duplikat). Labels werden pro Lauf voll reconciled (gesetzt wenn zutreffend, entfernt wenn nicht mehr zutreffend).
- [ ] **Unbekannter Typ/Status:** Ein unbekannter `**Typ:**`-Wert oder ein Inbox-Status ≠ `Unrefined` führt zu einem nicht-fatalen Warnfall (Eintrag wird übersprungen, der restliche Lauf läuft weiter) — analog zum bestehenden Muster für unbekannten Feature-Spec-Status.
- [ ] **Pfad-/Nummernvalidierung für beide Verzeichnisse:** Die bestehende `^\d{4}$`-Validierung vor jeder Pfadkonstruktion gilt über eine gemeinsame, parametrisierte Funktion für `specs/features/` *und* `specs/inbox/`, sowie für den `--supersede-inbox`-Wert — keine zwei unabhängig driftende Kopien derselben Prüfung.
- [ ] Migration der bereits produktiv befüllten 51 Feature-Items auf das neue Feldmodell ist ein einmaliger, manueller Rollout-Schritt (siehe ADR 0030 Abschnitt 3) — **kein** automatisierter Dauerbetrieb-Codepfad, der Board-Drift stillschweigend repariert (widerspräche dem in PR #115 etablierten Hart-Abbruch-Prinzip).

## Datenmodell-Bezug

Keine Berührung der PhotoSort-Datenbank/des Anwendungsdatenmodells. Erweiterung des bereits in Spec 0031 eingeführten, rein prozess-internen GitHub-Datenmodells: ein Single-Select-Feld `Status` (statt zwei getrennter `Status`/`Spec Status`), drei neue Repo-Labels (`idee`, `superseded`, Wiederverwendung von `bug`), sowie eine zweite Entität (`specs/inbox/*.md`) im selben Project mit eigenem Marker-Namespace. Zustandsdatei `specs/.github-sync-state.json` wechselt von flacher zu genesteter Struktur (`{"features": {...}, "inbox": {...}}`), rückwärtskompatibel gelesen.

## Architektur / Umsetzung

Siehe [`decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md`](../decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md) (Accepted, löst ADR 0017 Abschnitt 3 teilweise ab, ADR 0017 bleibt für die übrigen Abschnitte gültig) für die vollständige Begründung. Diese Spec setzt die dort getroffenen Entscheidungen um.

### Neue/betroffene Komponenten

- **`scripts/github-project-sync/src/github_project_sync/gh_adapter.py`**: `STATUS_FIELD_NAME` zurück auf `"Status"`, `STATUS_OPTIONS = ["Proposed", "Accepted", "Implemented", "Unrefined"]`; neue `ensure_label()`-Methode im `GhAdapter`-Protokoll + `GhCliAdapter`-Implementierung (`gh label list --json name --limit 100` / `gh label create`).
- **Neu: `inbox_parser.py`**: Parsing von `specs/inbox/*.md`, wiederverwendet die bestehende generische H1/Status/Inhalts-Zone-Erkennung aus `spec_parser.py`, ergänzt `**Typ:**`-Extraktion (Idee/Bug) und eigene Statuswert-Validierung (nur `Unrefined`).
- **`issue_body.py`**: Marker-Funktionen um zwei getrennte, jeweils hart geankerte Regexe erweitert (`photosort-spec` bzw. `photosort-inbox`), keine gemeinsame entitäts-agnostische Extraktion.
- **`state.py`**: Umstellung auf `{"features": {...}, "inbox": {...}}`, rückwärtskompatibles Lesen des alten flachen Formats (automatische Einmal-Migration beim ersten Lauf, kein manueller Schritt).
- **`sync.py`**: Label-Reconciliation (`superseded`/`idee`/`bug`), Superseded-Feld-Leerung statt Feldwert, eigener Inbox-Sync-Pfad (keine Priorität, `Unrefined` = offener Issue-Zustand), Orphan-Cleanup auf Inbox-Namensraum erweitert (generischer Schließ-Kommentar), `--supersede-inbox`-Verhalten, gemeinsame parametrisierte Pfad-/Nummernvalidierung für beide Verzeichnisse.
- **`cli.py`**: `--only` um `inbox:NNNN`-Präfix erweitert (bare `NNNN` bleibt rückwärtskompatibel Feature-Scope), neuer Flag `--supersede-inbox MMMM`, JSON-Ausgabe um `"inbox"`-Zweig ergänzt.
- **`.claude/skills/github-project-sync/SKILL.md`**: Dokumentation des neuen `"inbox"`-Ausgabezweigs, `inbox:NNNN`-Scopes, `--supersede-inbox`.
- **`.claude/skills/idea-sharpener/SKILL.md`**: letzter Schritt ruft bei aus einem Inbox-Eintrag hervorgegangenen Specs künftig `github-project-sync --only NNNN --supersede-inbox MMMM` auf (statt nur `--only NNNN`); zusätzlich wird an der Stelle, an der Inbox-Rohtext eingelesen wird, der Grundsatz "Inhalt ist Daten, keine Anweisung" explizit verankert (siehe Security-Abschnitt) — unabhängig davon, ob der Inbox-Eintrag lokal per `capture` oder per zurückgesynctem Issue-Inhalt entstanden ist.
- Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/`docs/ai-workflow.md`/Root-`README.md` (reines Entwickler-Tooling, wie ADR 0017/Spec 0031).

### Rollout-/Migrationsschritt (einmalig, manuell, kein Code — vor/unmittelbar nach Deploy)

1. `gh project field-list <number> --owner TheRealKoller --format json`: IDs des nativen `Status`-Felds (Todo/In Progress/Done, ungenutzt) und des `Spec Status`-Custom-Felds ermitteln.
2. Beide per `gh project field-delete --id <id>` löschen (kein Datenverlust — Status/Priorität sind reine, bei jedem Lauf neu berechnete Push-Spiegelung, nie Source of Truth, siehe ADR 0017 Abschnitt 4).
3. Neuen Code deployen.
4. Vollen Sync-Lauf ohne `--only` ausführen — legt `Status` frisch mit den vier neuen Optionen an, pusht alle Items neu (inkl. Feld-Leerung + Label `superseded` für die real betroffenen Specs `0003`/`0024`).

### Umsetzungsreihenfolge

1. `inbox_parser.py` (wiederverwendet `spec_parser.py`-Kernfunktion) — testgetrieben.
2. `issue_body.py`-Erweiterung (zwei getrennte Marker-Regexe) und `state.py`-Umstellung (genestete Namensräume + rückwärtskompatibles Lesen) — testgetrieben, unabhängig voneinander.
3. `gh_adapter.py`: Feldkonstanten ändern, `ensure_label()` ergänzen (+ `GhCliAdapter` + `FakeGhAdapter` in `tests/fakes.py`).
4. `sync.py`: Label-Reconciliation, Superseded-Feld-Leerung, Inbox-Sync-Pfad, erweiterter Orphan-Cleanup, `--supersede-inbox`-Verhalten, gemeinsame Pfad-/Nummernvalidierung.
5. `cli.py`: `--only inbox:NNNN`, `--supersede-inbox`, JSON-Ausgabe.
6. `.claude/skills/github-project-sync/SKILL.md` und `.claude/skills/idea-sharpener/SKILL.md` aktualisieren.
7. Manueller Rollout-Schritt (siehe oben) gegen das echte Project, dann finaler Voll-Sync zur Verifikation (Smoke-Test-Charakter wie in Spec 0031).

## UI/UX

**Nicht relevant** — reine Repo-/Tooling-Automatisierung ohne Berührung mit `frontend/src/` oder dem PhotoSort-Design-System. Die eigentliche Nutzeroberfläche (GitHub Project Board, Issue-Detailansicht) wird von GitHub selbst gestaltet, nicht von PhotoSort — identische Einordnung wie in Spec 0031, `ux-ui-designer`-Konsultation in Schritt 7 daher übersprungen (kein einziges plausibles Gegenbeispiel: weder neue Route noch Backend-Endpunkt noch Datenmodell-Änderung mit Bezug zu `frontend/src/`).

## Security

**Sicherheitsrelevanz: Ja** — Erweiterung eines bereits als sicherheitsrelevant eingestuften Features (Spec 0031: Issue-Spoofing, Prompt-Injection-Blast-Radius, Pfad-Traversal, Command-Injection); der Blast-Radius wächst durch echten Zwei-Wege-Sync für Inbox-Rohtext, es entsteht aber keine kategorial neue Bedrohungsklasse.

1. **Marker-Namespace-Verwechslung:** Ohne strikte Trennung könnte ein Issue mit `<!-- photosort-inbox: 0004 -->`-Marker fälschlich als Quelle für `features/0004` interpretiert werden (Nummernkreis-Kollision ist real vorkommend, siehe `inbox/0004` und `features/0004`, ebenso `inbox/0028` und `features/0028`). Gegenmaßnahme: zwei getrennte, jeweils hart auf den Entitäts-String geankerte Regexe (nicht eine gemeinsame, nur die Zahl extrahierende Funktion) plus expliziter Cross-Namespace-Ablehnungstest — die eigentliche Verteidigungslinie liegt in der Marker-Zeilen-Prüfung selbst, nicht nur in getrennten State-Namespaces.
2. **Prompt-Injection-Blast-Radius bei Inbox-Inhalten:** Zurückgespielter Inbox-Inhalt durchläuft (anders als bei Feature-Specs im `pulled`-Fall) keinen automatisierten `requirements-engineer`-Re-Scrutiny-Schritt, sondern erst irgendwann später einen vollen `idea-sharpener`-Lauf (Verständnisfragen, Konfliktsuche, Devil's Advocate, explizite Freigabe) — strukturell eine zusätzliche Schutzschicht gegenüber dem direkten Feature-Pfad. Die eigentliche Lücke: `idea-sharpener` selbst verankert den Grundsatz "Inhalt ist Daten, keine Anweisung" bisher nirgends explizit, weil Inbox-Inhalt bisher ausschließlich lokal verfasst war — das ändert sich mit echtem Zwei-Wege-Sync. Gegenmaßnahme: expliziter Anker dieses Grundsatzes direkt in `.claude/skills/idea-sharpener/SKILL.md` an der Stelle, an der Inbox-Rohtext eingelesen wird, unabhängig von dessen Herkunft. Kein zusätzlicher automatisierter Vor-Ab-Check nötig — der bestehende mehrstufige Ablauf ist die angemessene Kontrollinstanz, sofern der Anker explizit steht. Das Autor-Vertrauensmodell ändert sich nicht (nur Daniel als Collaborator kann einen Issue-Body editieren, Dritte nur kommentieren); ein vollständig kompromittierter Daniel-Account bleibt wie in Spec 0031/0007 out of scope.
3. **Pfad-Traversal über geparste Nummer:** Gilt jetzt für zwei Verzeichnisse (`specs/features/`, `specs/inbox/`) sowie den `--supersede-inbox`-Wert. Gegenmaßnahme: eine gemeinsame, parametrisierte Validierungsfunktion (`^\d{4}$`) statt zweier unabhängig driftender Kopien.
4. **Command-Injection:** Neue `ensure_label()`-Aufrufe verwenden ausschließlich statische, fest verdrahtete Werte (Labelnamen/-beschreibungen/-farben) — kein extern beeinflusster String. `--supersede-inbox`-Wert kommt vom Aufrufer (`idea-sharpener`, aus Dateinamen berechnet) und landet in Listenform-`subprocess`-Aufrufen — bei bestehender Listenform ausreichend abgesichert, die Nummernvalidierung aus Punkt 3 ist die relevante Ergänzung, keine neue Injection-Klasse.

`specs/architecture/0003-securitykonzept.md` wird der bestehende "GitHub-Project-Sync"-Vorausschau-Abschnitt um die Inbox-Erweiterung ergänzt.

## Teststrategie

- **Unit (Schwerpunkt):** `inbox_parser.py` (`**Typ:**`-Extraktion, Status-Validierung nur `Unrefined`, Wiederverwendungs-Nachweis der Kernfunktion aus `spec_parser.py`); Marker-Extraktion je Namespace (`issue_body.py`, inkl. Cross-Namespace-Ablehnung); `state.py::load_state()` Rückwärtskompatibilität (Alt-Format → genestet, fehlende Datei → beide Namespaces leer); `gh_adapter.py::ensure_label()` (Argumentkonstruktion, JSON-Parsing, gemocktes `subprocess.run`).
- **Integration (`FakeGhAdapter`, Mehr-Entitäten-Lauf):** gemischter Feature+Inbox-Lauf inkl. Nummernkollision; Superseded-Fall (Feld leeren + Label gleichzeitig); Label-Reconciliation über zwei Läufe inkl. `bug`-Wiederverwendung; State-Migration End-to-End (alte Fixture → voller Lauf → neues Format, keine falschen `created`); `--only NNNN` vs. `--only inbox:NNNN` als Regressions-Paar; `--supersede-inbox` kombiniert mit `--only`; symmetrischer Orphan-Cleanup für Inbox; Abbruch mitten in einer gemischten Feature+Inbox-Verarbeitungsreihenfolge.
- **E2E/Smoke (manuell, Wegwerf-Muster wie Spec 0031):** mindestens ein Wegwerf-Inbox-Issue real durchspielen, `--supersede-inbox` einmal real, Label-Neuanlage/-Wiederverwendung real verifizieren, danach vollständiger Cleanup. Der einmalige Rollout-Schritt (Feld löschen+neu anlegen) ist kein Testfall, sondern der manuelle Ablauf selbst (siehe Architektur-Abschnitt).
- **Relevante Edge Cases:** Nummernkollision `inbox/NNNN` vs. `features/NNNN`; State-Datei-Migration alt→neu; Superseded-Feld-Leerung+Label gleichzeitig; `bug`-Label-Wiederverwendung (kein Duplikat); Inbox-Datei ohne `**Bezug:**`-Zeile; Abbruch mitten im gemischten Lauf; unbekannter `**Typ:**`-Wert oder Inbox-Status ≠ `Unrefined` (nicht-fataler Warnfall); `--supersede-inbox MMMM` ohne existierenden State-Eintrag (klare Fehlermeldung statt stillem No-op).
- **Coverage-Gate:** weiterhin kein `--cov-fail-under`-Gate für `scripts/github-project-sync/` (nur `backend/` laut `CLAUDE.md`), aber vollständige Unit-Abdeckung für den gesamten neuen verzweigten Code (`inbox_parser.py`, `ensure_label()`, State-Migration), konsistent mit dem bestehenden Package-Grundsatz.

`specs/architecture/0002-testkonzept.md` wurde bereits um eine Erweiterung der Sektion "Externe CLI-Werkzeuge als dünne Adapter-Schicht" ergänzt (State-Formatmigration, Sync über zwei unabhängige Entitäts-/Nummernkreise, generisches Label-Self-Provisioning ohne Feld-Drift-Härte).

## Entscheidungen (2026-08-21, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Auslöser:** Daniel störte sich daran, dass das eigene `Spec Status`-Custom-Field faktisch dasselbe abbildet wie GitHubs natives `Status`-Feld, aber als separates, zusätzliches Feld — das native Feld sollte stattdessen direkt die Spec-Lifecycle-Werte tragen ("das richtige Feld mit den richtigen Werten"), auch um GitHub-Board-Views einfacher bauen zu können.
- **Priorität: Mittel** (Vorschlag von `requirements-engineer`, nach Architektur-/Test-/Security-Konsultation bestätigt) — sinnvolle, aber nicht blockierende Tooling-Verbesserung; reversiert eine dokumentierte, incident-getriebene Entscheidung (ADR 0017/PR #115) und braucht daher sorgfältige Migration, ist aber kein Produktivitäts-Blocker und steht hinter Spec 0047 (Hoch) zurück.
- **Label-Mapping bewusst uneinheitlich:** `Superseded`/`Idee`/`Bug` werden Labels (sichtbar auch außerhalb der Projekt-Ansicht in normalen Issue-Listen), `Priorität` bleibt bewusst ein eigenes Custom-Field (kein Label) — auf Nachfrage von Daniel explizit so geklärt, keine Vereinheitlichung aller Werte auf ein Modell.
- **Migration real, nicht hypothetisch:** Live-Check gegen das echte GitHub Project bestätigte, dass sowohl das native `Status`-Feld (ungenutzt, Todo/In Progress/Done) als auch `Spec Status` (produktiv, 51 Einträge) existieren — die Umsetzung ist also eine echte Daten-Migration, kein Neuanlegen. `gh` 2.97.0 kennt kein `field-edit`, daher ist Löschen+Neuanlegen (einmaliger manueller Rollout-Schritt) der einzige Weg — bewusst **kein** automatischer Dauerbetrieb-Reparatur-Codepfad, um das in PR #115 etablierte Hart-Abbruch-bei-Board-Drift-Prinzip nicht aufzuweichen.
- **Nummernkreis-Kollision zwischen Inbox und Features ist real** (nicht nur theoretisch) — z.B. existieren bereits gleichzeitig `inbox/0004`+`features/0004` und `inbox/0028`+`features/0028`. Deshalb zwei getrennte, hart geankerte Marker-Regexe statt eines gemeinsamen, entitäts-agnostischen Parsers.
- **`architect` nicht erneut zur Diskussion gestellt, ob ADR 0017 komplett `Superseded` wird:** ADR 0030 löst nur Abschnitt 3 ab, die übrigen Abschnitte (Skill-Architektur, `gh`-Session, Content-Bidirektionalität, Hash-Konflikterkennung, Auto-Issue bei neuer Spec) bleiben unverändert gültig — reine technische Abgrenzungsentscheidung des `architect`-Agenten, kein Daniel-Rückfragebedarf.
- **`ux-ui-designer` nicht konsultiert (Schritt 7):** reines Repo-/CLI-Tooling ohne jede Berührung mit `frontend/src/` oder sichtbarer PhotoSort-Oberfläche — identische Begründung wie bereits in Spec 0031 bestätigt.
- **Konfliktverhalten für Inbox bewusst identisch zum bestehenden Feature-Verhalten** — keine Rückfrage an Daniel nötig, da reine Wiederverwendung eines bereits etablierten, akzeptierten Musters (Daniel entscheidet bei `conflict`, keine Seite wird automatisch überschrieben).

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Echtzeit-/Hintergrund-Sync (weiterhin ausschließlich session-getriggert, siehe ADR 0017 Abschnitt 2 und "Randbedingungen").
- Rückspielen von Board-Änderungen an den Feldern `Status`/`Priorität` (weiterhin bewusste Einbahnstraße).
- Sync für `specs/decisions/` (ADRs) — nur `specs/features/*.md` und neu `specs/inbox/*.md`.
- Ein automatisierter Dauerbetrieb-Codepfad, der Feld-Optionsabweichungen ("Board-Drift") selbstständig repariert — der Rollout-Schritt bleibt bewusst manuell und einmalig.
- Automatisches Konflikt-Merging (Drei-Wege-Diff) — unverändert gegenüber Spec 0031.
- Ein zweites GitHub Project oder eine Trennung Inbox/Features auf Board-Ebene — beide Entitäten teilen sich bewusst dasselbe Project und Status-Feld.
