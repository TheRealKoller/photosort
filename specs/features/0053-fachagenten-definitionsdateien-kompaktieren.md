# 0053 - Skill-/Agenten-Dateien kompaktieren: Prosa straffen und historische ADR-/Spec-Zitate entfernen

**Status:** Accepted (Strang 1 umgesetzt, [PR #188](https://github.com/TheRealKoller/photosort/pull/188) — Gesamtstatus wechselt erst nach Merge von Strang 2/PR 2 auf `Implemented`)
**Erstellt:** 2026-08-22
**Bezug:** [`inbox/0026-idea-sharpener-tokenverbrauch-senken.md`](../inbox/0026-idea-sharpener-tokenverbrauch-senken.md) (Strang 1), [`inbox/0030-skills-agents-keine-adr-verweise.md`](../inbox/0030-skills-agents-keine-adr-verweise.md) (Strang 2), Spec [`0025`](./0025-test-engineer-review-kompaktierung.md) (Präzedenzfall für `test-engineer.md`, dort explizit als "eigene, separate Idee" für die übrigen Agenten vorgemerkt), Spec [`0032`](./0032-idea-sharpener-kalibrierung-und-skip-logik.md)/ADR [`0018`](../decisions/0018-idea-sharpener-kalibrierung-und-skip-logik.md) (bereits umgesetzte Modellzuweisung/Skip-Logik für den `idea-sharpener`-Ablauf selbst), Idea-Sharpening-Gespräche mit Daniel am 2026-08-22.

## Ziel

Diese Spec bündelt zwei unabhängige, aber thematisch verwandte Kompaktierungs-Stränge auf denselben Skill-/Agenten-Dateien — auf Daniels ausdrücklichen Wunsch in einer Spec zusammengeführt, statt zwei separate Specs zu pflegen, da beide Stränge größtenteils dieselben Dateien anfassen.

**Strang 1 (Ursprung: Inbox 0026):** Inbox-Eintrag 0026 wünschte sich allgemein weniger Tokenverbrauch im `idea-sharpener`-Ablauf. Die Recherche im Idea-Sharpening-Gespräch ergab: das ursprüngliche Anliegen war bereits durch Spec 0032/ADR 0018 (differenzierte Modellzuweisung, urteilsbasierte Skip-Logik) gelöst. Als echter, bisher unbetrachteter Resthebel bleibt: die vier Fachagenten-Definitionsdateien `.claude/agents/architect.md`, `.claude/agents/requirements-engineer.md`, `.claude/agents/ux-ui-designer.md` und `.claude/agents/security-engineer.md` werden bei **jedem** Aufruf vollständig als Systemprompt geladen — sowohl im `idea-sharpener`-Ablauf als auch im `developer`-Review-Workflow (ADR 0014) — und enthalten spürbar mehr ausschmückende Prosa pro Zeile als das bereits kompaktierte `test-engineer.md` (Spec 0025, 66 Zeilen/1091 Wörter als Referenzmaßstab; die vier hier betroffenen Dateien liegen bei 1209–1405 Wörtern trotz ähnlicher Zeilenzahl). Überträgt das in Spec 0025 bereits erprobte und akzeptierte Kompaktierungsmuster (Meta-Prosa straffen, Aufgaben-Substanz vollständig erhalten) auf die vier verbleibenden Fachagenten — genau die Fortsetzung, die Spec 0025 in ihrem Abschnitt "Out of Scope" explizit als eigene, spätere Idee vorgesehen hatte.

**Strang 2 (Ursprung: Inbox 0030):** Skills- und Agenten-Definitionsdateien sollen keine Verweise auf ADRs/Specs mehr enthalten, die nur der historischen Begründung einer Regel dienen ("warum/wie kam es dazu, dass diese Regel existiert") — die Regel selbst bleibt jeweils vollständig erhalten, nur das Herkunfts-Zitat entfällt. Betrifft praktisch alle Agenten- und Skill-Dateien des Projekts (11 Dateien, siehe Architektur/Umsetzung), am dichtesten `idea-sharpener/SKILL.md`. Etabliert zusätzlich eine **dauerhafte Konvention** (in `CLAUDE.md`) für künftige Skill-/Agenten-Änderungen, nicht nur eine einmalige Bereinigung.

Reines Entwickler-/Prozess-Tooling für den KI-gesteuerten Entwicklungsworkflow selbst (analog zu Spec 0025/0032), ohne jede Berührung mit der eigentlichen PhotoSort-Anwendung oder ihren Endnutzern. Keiner der beiden Stränge berührt `specs/features/*.md` oder `specs/decisions/*.md` selbst — historische Begründung gehört dort hin und bleibt davon unberührt; es geht ausschließlich um die operativen Instruktionsdateien unter `.claude/`.

## User Story

**Strang 1:** Als Daniel, der `idea-sharpener` und den `developer`-Review-Workflow regelmäßig nutzt, möchte ich, dass die vier verbleibenden Fachagenten-Definitionsdateien (`architect`, `requirements-engineer`, `ux-ui-designer`, `security-engineer`) ähnlich kompakt sind wie das bereits für `test-engineer.md` umgesetzte Muster, damit über viele Agenten-Aufrufe hinweg spürbar weniger Kontingent verbraucht wird, ohne dass Aufgaben-Substanz oder Prüftiefe darunter leidet.

**Strang 2:** Als Daniel, der Skills/Agents pflegt und weiterentwickelt, möchte ich, dass diese Dateien rein operativ funktionieren, ohne auf ADRs/Specs als Begründung ihrer eigenen Existenz zu verweisen, damit sie kürzer, fokussierter und unabhängig von der historischen Entstehungsgeschichte lesbar bleiben — und dass diese Eigenschaft bei künftigen Änderungen automatisch erhalten bleibt, nicht nur einmalig hergestellt wird.

## Akzeptanzkriterien

### Strang 1 — Prosa-Kompaktierung (vier Fachagenten)

- [x] **AK1 (Delegationsabsatz-Konsistenz):** In allen vier Dateien folgt der Absatz "Delegation an `research-engineer`" exakt demselben Satzskelett (Fehlt-dir-Bedingung → `Agent`-Tool-Aufruf mit `subagent_type: research-engineer`, `model: Standard` → "Die [X]-Entscheidung bleibt dabei bei dir" → "Bewerte den zurückgelieferten Bericht kritisch"), unterscheidet sich nur im domänenspezifischen Beispiel und Entscheidungs-Nomen ("architektonische"/"Priorisierungs-/Anforderungs-"/"Design-"/"Sicherheitsentscheidung"). Bleibt ein eigener, abgeschlossener Absatz — wird nicht in "Warum diese Rolle" einverleibt oder in eine gemeinsame externe Datei extrahiert (siehe Architektur/Umsetzung).
- [x] **AK2 ("Warum diese Rolle" gestrafft, kein Substanzverlust):** Der Absatz ist je Datei kürzer als im Ist-Stand, behält aber je Datei zwingend die Rollenbegründung sowie die technische-vs-AskUserQuestion-Abgrenzung. Bei `ux-ui-designer.md` bleibt der Zwei-Nutzer-Kontext (Daniel und seine Frau, PWA-Bezug) explizit erhalten — rollendefinierend, keine austauschbare Prosa. Eine Doppelung mit einer Aufgabe (z.B. `architect.md`: Drei-Perspektiven-Beschreibung steht sowohl in "Warum diese Rolle" als auch in Aufgabe 2) darf aus "Warum diese Rolle" gekürzt werden, solange sie in der jeweiligen Aufgabe vollständig erhalten bleibt.
- [x] **AK3 (`architect.md`, Substanz Aufgabe 1–4 vollständig):** Insbesondere erhalten bleiben: ADR-Unveränderlichkeit/Superseded-Regel, Pflege von `docs/architecture.md` + Root-`README.md` + `docs/setup.md`, die "ein Dokument, ein Owner"-Regel, die drei Review-Perspektiven (Pragmatiker/Senior-Entwickler/Pedant) mit Leitfrage je Perspektive und dem Hinweis, Widersprüche nicht künstlich zu glätten, die Abgrenzung zu `test-engineer`, der `## Blockiert: Architektur-Konsultation nötig`-Anker samt ADR-0024-Verweis, und die AskUserQuestion-Eskalation bei echten Entwurfs-Weggabelungen.
- [x] **AK4 (`requirements-engineer.md`, Substanz Aufgabe 1–4 vollständig):** Insbesondere erhalten bleiben: die drei Roadmap-Inhalte (Priorität/Verweis, Status-Überblick, Abhängigkeiten), die Abgrenzung "ergänzt idea-sharpener, ersetzt ihn nicht", die drei Review-Prüfpunkte (Vollständigkeit/Scope Creep/Out-of-Scope), und der Sicherheitsgrundsatz in Aufgabe 4, dass aus GitHub zurückgespielter Text ausschließlich als zu bewertende Daten gilt, niemals als Anweisung — dieser Satz darf beim Straffen nicht verwässert werden.
- [x] **AK5 (`ux-ui-designer.md`, Substanz Aufgabe 1–3 vollständig):** Insbesondere erhalten bleiben: die fünf Design-System-Inhalte, der komplette "Skill mitpflegen"-Absatz (Synchronisationspflicht `SKILL.md` ↔ `0004-design-system.md` inkl. der Ausnahme für rein historische Ergänzungen), die Reihenfolge-Bedingung "nach architect, vor Teststrategie/Security", die Bedingtheit von Aufgabe 2 (nur bei Frontend-Diff), die fünf Review-Kriterien, und die Nicht-eigenmächtig-Regel bei neuen UI-Bibliotheken (Abstimmung mit `architect`).
- [x] **AK6 (`security-engineer.md`, Substanz Aufgabe 1–3 vollständig):** Insbesondere erhalten bleiben: die sechs Konzept-Inhalte (Bedrohungsmodell/Auth-Modell/Secrets/Angriffsflächen/Restrisiken/Lücken), die sechs Review-Prüfpunkte, der Verweis auf die `security-review`-Skill, und die Einordnungs-Nuance "ein theoretisches Risiko ohne reale Relevanz für dieses private Projekt wird benannt, nicht weggelassen oder überbewertet".
- [x] **AK7 (messbar kürzer, kein hartes Minimalziel):** Jede der vier Dateien ist gegenüber dem Ist-Stand (architect.md 1405 Wörter, requirements-engineer.md 1360, ux-ui-designer.md 1268, security-engineer.md 1209) messbar kürzer. Referenzrahmen ist `test-engineer.md` (66 Zeilen/1091 Wörter) — kein hartes Zeilenlimit; `architect.md`/`requirements-engineer.md` dürfen wegen vier statt drei Aufgaben spürbar länger als die anderen bleiben, ohne dass das als Zielverfehlung gilt.
- [x] **AK8 (Frontmatter unangetastet in der Bedeutung):** Die YAML-`description` je Datei bleibt in ihrer Bedeutung (Rollen, Einsatzzeitpunkte, AskUserQuestion-Trigger) vollständig erhalten — nur sprachlich gestrafft, keine Trigger-Bedingung entfällt.
- [x] **AK9 (keine Seiteneffekte):** Modellzuweisungen/Trigger-Tabellen in `developer.md`, ADR 0014 und ADR 0018 bleiben unverändert — explizit kein Bestandteil dieser Spec. Abschließender `grep -rn "research-engineer" .claude/agents/ docs/ specs/` bestätigt, dass keine andere Stelle einen jetzt veralteten Wortlaut des Delegationsabsatzes zitiert.
- [x] **AK10 (Verifikationsmethode):** (a) Statischer Konsistenz-Check je Datei gegen AK1–AK6/AK8 (Bullet-für-Bullet-Abgleich alt/neu) plus (b) genau ein synthetischer Dry-Run auf einem Wegwerf-Branch, beschränkt auf `architect.md`s Aufgabe 2 (Drei-Perspektiven-Review) mit einem konstruierten Diff — als repräsentative Stichprobe statt vier Dry-Runs (Begründung siehe Teststrategie).

### Strang 2 — ADR-/Spec-Zitate entfernen, künftige Konvention (11 Dateien)

- [ ] **AK11 (Vier-Fragen-Klassifikation je Fundstelle, nicht pro Datei):** Für jede in den 11 Dateien gefundene ADR-/Spec-Nummer-Referenz (Auffindung via `grep -noE '(ADR|Spec)[[:space:]]*\[?`?[0-9]{4}' <Datei>`) wird explizit dokumentiert, welcher der vier Fälle zutrifft (funktional nötig → behalten / Bündelfall → nur Begründungsklausel streichen / Status-Fortschritts-Ausnahme → behalten / reine Herkunftsbegründung → entfernen). Kein pauschales "Datei X ist jetzt bereinigt" ohne Fundstellen-Liste.
- [ ] **AK12 (Regel-Substanz bleibt vollständig, Satz bleibt grammatisch intakt):** Nach Entfernen einer Herkunfts-/Begründungsklausel ist der verbleibende Satz weiterhin vollständig, eigenständig verständlich und frei von verwaisten Satzfragmenten (z.B. kein Komma/Bindestrich, der ins Leere zeigt).
- [ ] **AK13 (Bündelfall, konkret belegt):** Wo funktionale Anweisung und Begründungsklausel im selben Satz stehen, wird nur die Begründungsklausel gestrichen. Beispiel: `architect.md` ("...ruft dich daraufhin auf (nicht mehr `developer` selbst — siehe ADR 0024)") → "...ruft dich daraufhin auf (nicht mehr `developer` selbst)"; die funktionale Aussage bleibt unverändert. Gleiches Muster im neuen `CLAUDE.md`-Bullet zum PR-Workflow.
- [ ] **AK14 (funktionale ADR-Referenzen bleiben trotz Nummer):** Referenzen, bei denen die Datei selbst eine Pflegepflicht gegen die ADR formuliert (z.B. `ship-feature/SKILL.md` Schritt 3: "bei jeder künftigen Änderung zuerst in ADR 0014, dann hier synchron aktualisieren"), bleiben unverändert — funktional, keine Historie.
- [ ] **AK15 (Status-Ausnahme in `design-system/SKILL.md` explizit unangetastet):** Alle "(noch nicht implementiert, vorgesehen für Spec NNNN)"/"(implementiert mit Spec NNNN, Referenz ...)"-Vermerke bleiben wortgleich erhalten.
- [ ] **AK16 (Statusmarker vs. Herkunftszitat im selben Klammerausdruck sauber getrennt):** Wo ein Klammerausdruck sowohl Status als auch Herkunft mischt (Beispiel `CLAUDE.md`, Issue-Freigabe-Policy-Absatz: "vorbereitet mit Spec 0007/ADR 0007 ..., technisch noch nicht durchgesetzt, da die Automatisierung selbst noch nicht existiert"), wird nur der Herkunftsteil gestrichen, der Statusteil bleibt.
- [ ] **AK17 (keine neue Herkunfts-Referenz im neuen CLAUDE.md-Bullet selbst):** Der neue Konventions-Bullet in `CLAUDE.md` (Abschnitt "Konventionen") formuliert die Regel selbstständig, ohne auf Inbox 0030/Spec 0053 als Begründung zu verweisen.
- [ ] **AK18 (Verifikationsmethode als Pflicht-AK):** Abschließender `grep -noE '(ADR|Spec)[[:space:]]*\[?`?[0-9]{4}' .claude/agents/*.md .claude/skills/*/SKILL.md CLAUDE.md` (nach der Änderung) darf nur noch Treffer liefern, die laut AK14/AK15 explizit als "bleibt" klassifiziert wurden — jeder andere verbleibende Treffer ist ein Muss-Fix-Finding im Review.

## Datenmodell-Bezug

Keines — reine Prozess-/Prompt-Konfiguration (`.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `CLAUDE.md`), keine Berührung der PhotoSort-Datenbank oder Anwendungscode.

## Architektur / Umsetzung

Reine Instruktions-/Konventionsänderung an Agenten- und Skill-Definitionsdateien plus einem neuen Konventions-Bullet in `CLAUDE.md`. Kein neues System-/Datenmodell, keine neue Technologie, keine neue externe Abhängigkeit — daher keine neue ADR nötig (wie bereits bei Spec 0025/0018/0019 aus demselben Grund; anders als ADR 0018/0024 führt keiner der beiden Stränge eine neue Ausführungsmechanik ein, nur Inhalt/Stil bestehender Dateien).

### Strang 1 — Prosa-Kompaktierung (vier Fachagenten)

1. **Jede Datei einzeln behandeln, aber nach demselben Muster.** Kein gemeinsamer Mega-Refactor-Commit — die vier Fachinhalte (Architektur, Design, Security, Requirements) unterscheiden sich zu sehr, um sie in einem Schritt zu verschmelzen. Pro Datei greifen aber dieselben zwei Hebel:
   - **"Warum diese Rolle" straffen**: ausschmückende Wiederholungen raus, Kernaussage bleibt in einem knappen Absatz erhalten — Muster identisch zu `test-engineer.md` Zeilen 11–13.
   - **"Delegation an `research-engineer`"-Absatz vereinheitlichen**: kommt in allen fünf Fachagenten fast wortgleich vor und unterscheidet sich nur im domänenspezifischen Nomen. Auf einen einheitlichen, kürzeren Wortlaut bringen (Struktur: wann delegieren → wie → wer entscheidet trotzdem selbst → kritische Prüfung statt Blindübernahme), Platzhalter nur für das domänenspezifische Nomen.
   - **Bewusst keine Extraktion in eine gemeinsame externe Datei** (z.B. `.claude/agents/_shared/research-delegation.md`): jede Agenten-Datei ist als eigenständiger, vollständiger Systemprompt konzipiert und wird beim jeweiligen Subagenten-Aufruf komplett geladen — ein Verweis auf eine externe Datei würde entweder ungelesen bleiben (Nuance geht verloren) oder einen zusätzlichen `Read`-Aufruf pro Delegationsfall erzwingen. Die Ersparnis wäre marginal gegenüber der eingeführten Komplexität eines neuen, bisher unbenutzten Musters ("gemeinsam referenzierte Prompt-Fragmente").
   - **Aufgaben-Substanz (Aufgabe 1–4, je nach Datei 3 oder 4 Aufgaben) bleibt inhaltlich unverändert** — nur Prosa-Redundanz innerhalb der Aufgaben-Absätze kürzen, kein Bullet-Punkt/Prüfkriterium/Sonderfall darf inhaltlich verschwinden (siehe AK3–AK6 für die je Datei besonders zu erhaltenden Punkte).
   - **Frontmatter-`description` nur optional/sprachlich straffen, keine Trigger-Bedingungen oder -Beispiele verlieren** (analog Spec 0025) — niedrige Priorität; im Zweifel unangetastet lassen, da zuverlässiges Triggern wichtiger ist als die wenigen gesparten Tokens dort.
2. **Zielrahmen statt hartem Zeilenlimit.** `test-engineer.md` (66 Zeilen/1091 Wörter) ist der passende Vergleichsmaßstab, nicht `developer.md` — die vier Dateien gehören strukturell zur selben Peer-Gruppe (Drei-/Vier-Aufgaben-Rollenmuster), `developer.md` ist bewusst umfangreicher (TDD-Zyklus, feste Anker-Formate) und bleibt nur grobe Obergrenze, kein Zielwert. Realistisches Ziel pro Datei: Richtung 1100–1250 Wörter (architect/requirements-engineer dürfen wegen vier statt drei Aufgaben minimal darüberliegen).
3. **Abschließender Konsistenz-Check**: nach der Vereinheitlichung des Delegationsabsatzes per `grep -rn "research-engineer" .claude/agents/ docs/ specs/` prüfen, ob eine andere Stelle wortwörtlich auf die alte Formulierung verweist — falls ja, synchron anpassen, sonst unberührt lassen.

**Betroffene Dateien Strang 1:** `.claude/agents/architect.md`, `requirements-engineer.md`, `ux-ui-designer.md`, `security-engineer.md`.

**Umsetzungsreihenfolge Strang 1:** `architect.md` (größte Datei, 1405 Wörter, etabliert den vereinheitlichten Delegationsabsatz) → `requirements-engineer.md` (1360 Wörter) → `ux-ui-designer.md` (1268 Wörter) → `security-engineer.md` (1209 Wörter, zuletzt). Kein Lint-/Test-/Coverage-Lauf anwendbar — Verifikation je Datei per statischem Konsistenz-Check plus dem abschließenden Grep aus Punkt 3.

**Läuft als eigener PR (PR 1), muss vor Strang 2 gemergt sein** — Strang 2 setzt auf demselben Dateibestand auf und würde sonst gegen eine bald überholte Zwischenversion arbeiten.

### Strang 2 — ADR-/Spec-Zitate entfernen, künftige Konvention festhalten (11 Dateien)

**Ziel:** Skills und Agenten-Dateien enthalten keine Verweise auf ADRs/Specs mehr, die nur der historischen Begründung dienen ("warum/wie kam es dazu, dass diese Regel existiert"). Die Verhaltensregel selbst bleibt in jedem Fall vollständig erhalten — es entfällt ausschließlich das Zitat der Herkunft.

**Abgrenzungsregel (funktional vs. Begründung), anzuwenden je Referenz:**

> Frage: Muss der Agent/Skill die referenzierte Datei tatsächlich lesen, gegen sie prüfen, oder sie pflegen, um seine *aktuelle* Aufgabe zu erfüllen?
> - **Ja → behalten.** Beispiele: "lies zu Beginn frisch CLAUDE.md/specs/README.md"; "Verweis auf und Konsistenzprüfung gegen `decisions/0003-auth-model.md`" (`security-engineer.md`); "lies die bestehenden ADRs" vor Neuanlage eines Konzepts; "aktualisiere `specs/architecture/0004-design-system.md`, wenn ..." (Pflegepflicht).
> - **Nein → entfernen, Regel-Satz selbst unangetastet lassen.** Jedes "(siehe ADR NNNN)"/"(siehe Spec NNNN)", das nur erklärt, warum/wie eine bereits im selben Satz vollständig formulierte Regel entstanden ist — auch ohne "siehe"-Wortlaut, auch als reines Kontext-Zitat ohne Leseaufforderung. Beispiel: "kein `model`-Parameter ... (siehe ADR 0018, Teil 1)" → "kein `model`-Parameter ...".
> - **Sonderfall, bleibt bewusst erhalten:** Status-/Fortschritts-Referenzen in lebenden Dokumenten (v.a. `design-system/SKILL.md`), die nicht *begründen*, sondern den Umsetzungsstand markieren, den der Skill für seine Pflegepflicht kennen muss — z.B. "noch nicht implementiert, vorgesehen für Spec 0042" oder "implementiert mit Spec 0040, Referenz `CriterionDetailsPopover.tsx`".
> - **Bündelfall:** Enthält ein Satz sowohl eine funktionale Anweisung als auch eine Begründungs-Klausel, wird nur die Begründungs-Klausel gestrichen, die Anweisung bleibt wörtlich stehen.

**Künftige Konvention (dauerhaft, nicht nur Einmal-Bereinigung):** neuer Bullet in `CLAUDE.md`, Abschnitt "Konventionen" (direkt nach dem bestehenden Diagramm-Bullet), sinngemäß:

> **Skills/Agents:** enthalten keine Verweise auf ADRs/Specs, die nur der historischen Begründung einer Regel dienen — die Regel selbst steht vollständig im Text, das "warum/wie kam es dazu" nicht. Ein Verweis auf eine andere Datei bleibt erlaubt, wenn er funktional nötig ist (die Datei muss gelesen, gegen sie geprüft, oder sie muss gepflegt werden, um die Aufgabe zu erfüllen).

Verankert an dem Ort, den jeder Agent laut eigener Ansage "zu Beginn frisch" liest — nicht `specs/README.md` (regelt den Spec-Lifecycle, nicht Skill-/Agent-Autorenschaft), keine neue Datei (unverhältnismäßig für einen Absatz).

**Betroffene Dateien Strang 2 (11, vollständig):**
- `.claude/agents/architect.md`, `requirements-engineer.md`, `ux-ui-designer.md`, `security-engineer.md` (bereits Strang-1-Dateien — hier zweiter, unabhängiger Bearbeitungsgang nach Strang-1-Merge)
- `.claude/agents/test-engineer.md`, `developer.md` (neu für Strang 2, waren in Strang 1 explizit Out-of-Scope)
- `.claude/skills/idea-sharpener/SKILL.md`, `ship-feature/SKILL.md`, `github-project-sync/SKILL.md`, `design-system/SKILL.md`, `capture/SKILL.md`
- `CLAUDE.md` (neuer Konventions-Bullet)

**Umsetzungsreihenfolge Strang 2 (ein PR, ein Commit je Datei):**
1. `CLAUDE.md` zuerst — die Regel muss existieren, bevor sie angewendet wird.
2. `.claude/skills/idea-sharpener/SKILL.md` — mit Abstand am dichtesten betroffen, etabliert das Streich-Muster für die übrigen Dateien.
3. `.claude/skills/ship-feature/SKILL.md` — zweithöchste Dichte (ADR 0014/0018/0024).
4. `.claude/skills/github-project-sync/SKILL.md`.
5. `.claude/agents/developer.md` — u.a. die ADR-0024-Verweise (Verweis auf `ship-feature`/Blockiert-Anker bleibt als funktionale Anweisung stehen, nur "(siehe ADR 0024)" entfällt).
6. `.claude/agents/architect.md` → `requirements-engineer.md` → `ux-ui-designer.md` → `security-engineer.md` — dieselbe Reihenfolge wie Strang 1; Strang 1 ist zu diesem Zeitpunkt bereits gemergt, hier nur noch der Strang-2-Zitat-Pass.
7. `.claude/agents/test-engineer.md` (nur eine Fundstelle).
8. `.claude/skills/design-system/SKILL.md` — niedrigere Dichte, aber heikelste Datei wegen der Status-Referenzen-Ausnahme; zuletzt unter den inhaltlich bearbeiteten Dateien.
9. `.claude/skills/capture/SKILL.md` — nur Verifikation (`grep` liefert dort keinen Treffer zum Zeitpunkt dieser Spec; falls beim tatsächlichen Bearbeiten doch etwas gefunden wird, dieselbe Regel anwenden).
10. Abschließender Grep über alle 11 Dateien (AK18) als Konsistenz-Check.

**Läuft als eigener PR (PR 2), erst nach Merge von PR 1 begonnen** — beide ändern teilweise dieselben vier Dateien; sequenziell vermeidet Merge-Konflikte und lässt Strang 2 auf dem bereits gestrafften Text aufsetzen. Ein gemeinsamer PR über beide Konzepte hinweg würde `CLAUDE.md`s "klein und fokussiert" verletzen — Strang 2 ist zwar breit (11 Dateien), aber inhaltlich ein einziges, homogenes Konzept, das einen PR mit vielen, aber je Datei eigenen Commits rechtfertigt. Der Spec-Status wechselt erst nach Merge von PR 2 auf `Implemented`, mit Verweis auf beide PR-Nummern.

**ADR-Entscheidung (beide Stränge):** Keine neue ADR — reine Kompaktierung/Konventionsänderung bestehender Agenten-/Skill-Instruktionen, kein CLAUDE.md-Fall im Sinne von "neue Technologie/Datenmodell/externe Abhängigkeit" (analog Spec 0025/0018/0019).

## UI/UX

**Nicht relevant** (beide Stränge) — reine Änderung an Agenten-/Skill-Instruktionsdateien, keine App-Oberfläche betroffen, analog zu Spec 0018/0019/0020/0025 direkt eingeordnet, ohne gesonderte `ux-ui-designer`-Konsultation.

## Security

**Nicht relevant** (beide Stränge) — kein Anwendungscode, kein Datenmodell, keine Auth-/Secrets-Berührung, analog zu Spec 0018/0019/0025, ohne gesonderte `security-engineer`-Konsultation.

## Teststrategie

Reine Prozessänderung an Agenten-/Skill-Instruktionsdateien, kein Anwendungscode — `pytest`/`vitest` nicht einschlägig in beiden Strängen.

### Strang 1

`specs/architecture/0002-testkonzept.md` (Sektion "Agenten-Steuerungslogik selbst") nicht berührt, da dort die Skip-/Modell-Trigger-Logik behandelt wird, die hier laut AK9 unverändert bleibt — **keine Ergänzung des Testkonzepts nötig**, analog zu Spec 0025.

Unterschied zu Spec 0025: dort wurde ein Prüfpunkt ersatzlos entfernt (Verhaltensänderung, per Dry-Run beobachtbar). Hier wird **nichts entfernt**, nur Prosa gestrafft, während die Aufgaben-Substanz vollständig erhalten bleiben soll. Das Hauptrisiko ist stiller Inhaltsverlust beim Kürzen, nicht Verhaltensregression — und das erkennt ein statischer Vorher/Nachher-Abgleich zuverlässiger als ein Live-Dry-Run.

Verifikation zweistufig, mit bewusst asymmetrischem Aufwand:

1. **Statischer Konsistenz-Check** (primäres Verfahren, alle vier Dateien): Zeilen-/Wortzahlvergleich gegen den Ist-Stand, Bullet-für-Bullet-Abgleich jeder Aufgabe alt/neu gegen AK3–AK6, Delegationsabsatz-Skelettvergleich gegen AK1, Frontmatter-Bedeutungsabgleich gegen AK8.
2. **Ein repräsentativer synthetischer Dry-Run statt vier**: Von den vier Agenten hat `architect.md` mit dem Drei-Perspektiven-Review (Aufgabe 2) das höchste Risiko, dass gestraffte Rahmen-Prosa die Verhaltens-Nuance schwächt (die bewusste Nicht-Glättung der drei widersprüchlichen Sichtweisen). `requirements-engineer.md`, `security-engineer.md` und `ux-ui-designer.md` sind demgegenüber in ihren Review-Aufgaben checklistenartig/enumerativ aufgebaut — ihr Verhalten hängt direkt an den (laut AK4–AK6 vollständig erhaltenen) Bullet-Listen und ist damit durch den statischen Check ausreichend abgesichert. Ein Dry-Run auf einem Wegwerf-Branch für `architect.md`s Aufgabe 2 mit einem konstruierten Review-Diff genügt als Stichprobe. Vier separate Dry-Runs stünden in keinem Verhältnis zum Risiko einer reinen Prosa-Kompaktierung ohne Logikänderung.

### Strang 2

`specs/architecture/0002-testkonzept.md` **wurde ergänzt** — neue Sektion "Historische Herkunfts-Zitate aus Skills/Agenten-Dateien entfernen" (vor "Was bewusst nicht getestet wird"). Anders als Strang 1 (einmalige, abgeschlossene Prosa-Kompaktierung) etabliert Strang 2 eine **dauerhafte** Editierregel, die künftig bei jeder Änderung an `.claude/agents/*.md`/`.claude/skills/*/SKILL.md` gilt — strukturell ein neues, wiederkehrendes Testmuster, kein einmaliger Vorgang.

Rein statischer Konsistenz-Check, kein Dry-Run nötig: anders als Strang 1 (Risiko: stiller Bedeutungsverlust durch Prosa-Umformulierung) wird hier nur eine klar abgegrenzte Textklasse (Herkunftszitate) an grep-auffindbaren Stellen entfernt — das Fehlerrisiko liegt in falscher Klassifikation einer Fundstelle, was ein Bullet-für-Bullet-Abgleich zuverlässig aufdeckt. Ein synthetischer Dry-Run würde nicht zeigen, ob eine Begründung fälschlich mitgestrichen wurde, da das Verhalten der Regel selbst unverändert bleibt.

1. Vor Änderung: Grep-Fundstellenliste je Datei als Ausgangsbestand.
2. Je Fundstelle: Klassifikation nach AK11/AK14/AK15/AK16 dokumentieren (z.B. als Tabelle im PR).
3. Nach Änderung: Bullet-für-Bullet-Abgleich, dass die Regel-Substanz an jeder betroffenen Stelle (AK12) unverändert lesbar bleibt.
4. Abschließender Grep (AK18) — nur klassifizierte "bleibt"-Treffer dürfen übrig sein.
5. Ein Commit je Datei erleichtert den Abgleich, da jeder Commit-Diff einzeln gegen die Fundstellenliste dieser einen Datei geprüft werden kann.
6. **Laufende Beobachtung, dauerhaft statt einmaliges Gate:** ab Merge von Strang 2 ist jede künftige Skill-/Agenten-Änderung, die eine neue ADR-/Spec-Nummer als reines Herkunftszitat einführt statt sie wegzulassen, ein Muss-Fix-Finding im `test-engineer`-Review (Aufgabe 2) für jeden Skill-/Agenten-PR ab jetzt — kein optionaler Stilhinweis.

Kein neues CI-Gate, kein neues Testframework, kein Anwendungscode betroffen (beide Stränge). Kein automatisiertes Lint-/Klassifikations-Tooling für Strang 2 — die Fundstellenmenge ist für ein Solo-Projekt klein genug für einen manuellen, grep-gestützten Abgleich; ein automatisiertes Werkzeug könnte die Vier-Fragen-Klassifikation (braucht Satzkontext-Verständnis) ohnehin nicht zuverlässig ersetzen.

## Entscheidungen (2026-08-22, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Ausgangsbefund:** Inbox 0026 ("idea-sharpener soll weniger Tokens verbrauchen") war inhaltlich bereits durch Spec 0032/ADR 0018 gelöst und live im aktuellen `SKILL.md`. Daniel wollte den Eintrag explizit **nicht** als Duplikat schließen, sondern als Ausgangspunkt für die Suche nach weiterem Sparpotenzial nutzen — inklusive einer bewussten Neubewertung der in 0032 abgelehnten Hebel.
- **Neubewertung Modell-Downgrade für architect/test-engineer/security-engineer (Devil's Advocate):** weiterhin abgelehnt. Das spätere `developer`-Review (ADR 0014) ist diff-mechanisch und deckt genau die Art von Fehleinschätzung nicht ab, die in der Schärfungsphase selbst entsteht (z.B. ein subtil falscher Architekturansatz, der sich nie als auffälliges Diff-Muster zeigt). Kein neues Argument seit 0032, das das aufwiegt.
- **Neubewertung Skip-Logik für Schritt 3 (Konfliktrecherche) basierend auf Schritt-2-Einschätzung (Devil's Advocate):** weiterhin abgelehnt, mit geschärfter Begründung: zirkulär, da `requirements-engineer` seine Einschätzung *vor* jeder Code-/Spec-Recherche liefert (Haiku, minimaler Kontext) — genau diese ungeprüfte Früheinschätzung als Grundlage zu nehmen, um die Prüfung selbst zu überspringen, unterläuft den Zweck von Schritt 3.
- **Scope-Bestätigung durch Daniel:** nach Vorlage der beiden obigen Devil's-Advocate-Ergebnisse hat Daniel die Eingrenzung auf den einen verbleibenden, neuen Hebel (Agenten-Definitionsdateien kompaktieren) bestätigt.
- **Kein gemeinsamer Refactor, kein Extrahieren des Delegationsabsatzes in eine geteilte Datei** (architect-Konsultation): jede Agenten-Datei bleibt eigenständiger, vollständiger Systemprompt — eine Extraktion würde entweder Nuance verlieren (falls ungelesen) oder zusätzlichen `Read`-Aufwand pro Delegationsfall erzeugen, für zu geringen Gewinn bei einer reinen Prozess-Tooling-Kürzung.
- **Referenzmaßstab `test-engineer.md`, nicht `developer.md`** (architect-Konsultation): reine Zeilenzahl ist irreführend (die vier Dateien liegen zeilenmäßig nahe an `test-engineer.md`, aber wortreicher pro Zeile); `developer.md` ist strukturell keine Vergleichsgruppe (TDD-Zyklus, feste Anker-Formate).
- **Keine neue ADR** (architect-Konsultation): reine Kürzung/Vereinheitlichung bestehender Agenten-Instruktionen ohne neues System-/Datenmodell, neue Technologie oder externe Abhängigkeit — analog Spec 0025/0018/0019.
- **`ux-ui-designer` nicht konsultiert (Schritt 7):** reine Instruktionsdatei-Kürzung ohne jede App-Oberfläche — kein plausibles Gegenbeispiel, analog zur direkten Einordnung bei Spec 0018/0019/0020/0025.
- **`security-engineer` nicht konsultiert (Schritt 8):** kein Anwendungscode, kein Datenmodell, keine Auth-/Secrets-/Berechtigungs-Berührung — kein plausibles Gegenbeispiel, analog zu Spec 0018/0019/0025.
- **Asymmetrische Dry-Run-Tiefe (test-engineer-Konsultation):** ein einzelner Dry-Run für `architect.md` statt vier, da nur dort gestraffte Rahmenprosa eine echte Verhaltens-Nuance (Nicht-Glättung der drei Review-Perspektiven) gefährden könnte; die übrigen drei Agenten sind in ihren Review-Aufgaben checklistenartig aufgebaut und damit durch den statischen Konsistenz-Check ausreichend abgesichert.
- **Priorität — Niedrig (für beide Stränge):** analog zur Priorisierung von Spec 0025 ("Ideenspeicher"/niedrigste Kategorie zum Zeitpunkt von 0025, heute äquivalent "Niedrig" nach der Dreistufen-Umstellung durch Spec 0029): der Kontingent-Hebel, der frühere Kalibrierungs-Specs (0020/0032) höher stufte, war die Modell-/Skip-Logik-Änderung selbst — die hier explizit nicht Teil des Scopes ist. Übrig bleibt eine unabhängig sinnvolle, aber nicht dringende Aufräumarbeit. Strang 2 ist reine Konventions-/Lesbarkeitsarbeit ohne Endnutzer- oder Kontingent-Bezug, damit ebenfalls "Niedrig", keine eigene, höhere Priorisierung gerechtfertigt. `requirements-engineer`-Vorschlag nach Abschluss der Schärfung für den jetzt konkret feststehenden Scope (beide Stränge) bestätigt.

### Strang 2 — Inbox 0030, ergänzend geklärt

- **Auslöser:** allgemeine Grundsatz-Idee, kein konkreter Einzelvorfall — Skills/Agents sollen rein operativ funktionieren, unabhängig von der historischen Entstehungsgeschichte einer Regel.
- **Umfang: Konvention + einmalige Bereinigung, beides** (mit Daniel geklärt): nicht nur eine künftige Regel für neue Änderungen, sondern auch ein initialer Durchgang durch alle bestehenden Dateien, damit der Ist-Zustand sofort passt.
- **Koordination mit Strang 1:** auf Daniels Wunsch in derselben Spec integriert statt einer zweiten, separaten Spec — beide Stränge betreffen größtenteils dieselben Dateien; Reihenfolge/PR-Aufteilung siehe Architektur/Umsetzung (sequenziell, zwei PRs).
- **Restscope (test-engineer.md, developer.md, fünf SKILL.md-Dateien):** auf Daniels Wunsch ebenfalls vollständig in diese Spec aufgenommen, nicht in eine dritte, separate Spec ausgelagert — die zugrundeliegende Regel ist für alle Skill-/Agenten-Dateien identisch anwendbar, eine Aufteilung nach Datei-Typ hätte keinen fachlichen Mehrwert.
- **Scope "oder ähnliches" im Rohtext:** mit Daniel geklärt, dass auch reine Spec-Zitate als Kontext (nicht "lies diese Datei jetzt") demselben Entfernungs-Grundsatz unterliegen wie ADR-Zitate — nicht nur wörtliche "ADR"-Nennungen.
- **Abgrenzungsregel und Status-Ausnahme (architect-Konsultation):** funktionaler Test statt Bauchgefühl (siehe Architektur/Umsetzung) — mit einer wichtigen, vom Auftrag nicht vorgegebenen Ergänzung: `design-system/SKILL.md` enthält viele Status-/Fortschritts-Referenzen (~10 Fundstellen), die keine Regel-Begründung sind, sondern Umsetzungsstand markieren, den der Skill für seine Pflegepflicht aktiv braucht — bleiben explizit unangetastet.
- **Ort der künftigen Konvention (architect-Konsultation):** `CLAUDE.md`, Abschnitt "Konventionen", nicht `specs/README.md` (regelt Spec-Lifecycle, nicht Skill-/Agent-Autorenschaft) und keine neue Datei (unverhältnismäßig für einen Absatz).
- **Keine neue ADR (architect-Konsultation):** reine Instruktions-/Konventionsänderung ohne neue Ausführungsmechanik, System-/Datenmodell-Änderung oder externe Abhängigkeit — anders als ADR 0018/0024, die neue Ausführungsmechanik einführten.
- **Zwei sequenzielle PRs statt einem gemeinsamen (architect-Konsultation):** ein einzelner PR über beide Konzepte (Prosa-Kürzung + Zitat-Entfernung) auf denselben vier Dateien würde `CLAUDE.md`s "klein und fokussiert" verletzen; Strang 2 selbst ist trotz 11 Dateien ein einziges, homogenes Konzept und rechtfertigt einen PR mit vielen Einzeldatei-Commits.
- **Kein automatisiertes Lint-/Klassifikations-Tooling (test-engineer-Konsultation):** die Vier-Fragen-Klassifikation braucht Satzkontext-Verständnis, kein reines Pattern-Matching — für 11 Dateien in einem Solo-Projekt reicht ein manueller, grep-gestützter Abgleich; ein Werkzeug könnte die Klassifikation ohnehin nicht zuverlässig automatisieren.
- **Testkonzept-Ergänzung nötig (test-engineer-Konsultation), anders als Strang 1:** Strang 2 etabliert eine dauerhafte Editierregel (jede künftige Skill-/Agenten-Änderung), kein einmaliger Vorgang — neue Sektion in `specs/architecture/0002-testkonzept.md` bereits ergänzt.
- **Spec-Titel angepasst:** von "Fachagenten-Definitionsdateien kompaktieren" (nur Strang 1) auf einen Titel, der beide Stränge trägt — Dateiname/Spec-Nummer 0053 bleiben unverändert (bereits mit GitHub-Issue #186 verknüpft), nur der H1-Titel und die Roadmap-Kurzbeschreibung wurden aktualisiert.

### Strang 1 — Review-Ergebnis ([PR #188](https://github.com/TheRealKoller/photosort/pull/188))

- **Muss-Fix behoben:** In `architect.md` fehlte nach der Restrukturierung die `---`-Trennlinie zwischen Delegationsabsatz und `## Aufgabe 1`, die alle drei Schwesterdateien sowie `test-engineer.md` an derselben Stelle haben — unabhängig von `architect` und `test-engineer` gefunden, von `developer` ergänzt.
- **Gemeldeter Scope-Creep-Verdacht geprüft und verworfen:** `requirements-engineer` bewertete die strukturelle Umplatzierung in `architect.md` (Delegationsabsatz + AskUserQuestion-Passage von Aufgabe 1 nach "Warum diese Rolle" verschoben) zunächst als nicht von der Spec gedeckten Umbau. Der Orchestrator hat das gegen den main-Stand aller vier Dateien direkt gegengeprüft: `requirements-engineer.md`, `ux-ui-designer.md` und `security-engineer.md` hatten den Delegationsabsatz bereits vor diesem PR exakt an der Zielposition — nur `architect.md` war der Ausreißer. Die Einschätzung von `requirements-engineer` beruhte auf einer unzutreffenden Annahme zum Ist-Zustand der Schwesterdateien; kein Revert vorgenommen. Festgehalten als Beispiel dafür, dass ein Haiku-Review-Fund (siehe ADR 0014 Teil 2/ADR 0024 Teil 6) im Zweifel gegen den tatsächlichen Repo-Zustand verifiziert werden muss, bevor er als Muss-Fix an `developer` weitergereicht wird.
- **`security-engineer`/`ux-ui-designer` laut Trigger-Tabelle (ADR 0014/0024) nicht gestartet:** reiner `.claude/agents/*.md`-Diff ohne Frontend-/Auth-/Datenmodell-Bezug.
- **Kein Copilot-Review angefordert:** PR ändert ausschließlich Instruktionsdateien ohne jede Code-Datei (analog Spec 0025/PR #56, das aus demselben Grund ohne Copilot-Review auskam).

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Modell-Downgrade für `architect`/`test-engineer`/`security-engineer` in Reviews/Konsultationen — nach erneuter kritischer Prüfung weiterhin abgelehnt (siehe Entscheidungen, Strang 1).
- Skip-Logik für Schritt 3 (Code-/Spec-Konfliktrecherche) im `idea-sharpener`-Ablauf — nach erneuter kritischer Prüfung weiterhin abgelehnt (siehe Entscheidungen, Strang 1).
- Änderung der Trigger-Logik (welche Review-Agenten wann laufen) oder der Modellzuweisung — unverändert, betrifft nur ADR 0014/0018.
- Extraktion des Delegationsabsatzes in eine gemeinsam referenzierte externe Datei — bewusst abgelehnt (siehe Architektur/Umsetzung, Strang 1).
- **Änderung von `specs/features/*.md` oder `specs/decisions/*.md` selbst** — Strang 2 betrifft ausschließlich `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` und `CLAUDE.md`. Historische Begründung gehört in Specs/ADRs und bleibt dort unangetastet; nur die operativen Instruktionsdateien werden von Herkunftszitaten befreit.
- **Automatisiertes Lint-/CI-Tooling zur Zitat-Erkennung** — bewusst abgelehnt (siehe Entscheidungen, Strang 2); manueller, grep-gestützter Abgleich reicht für die Dateimenge eines Solo-Projekts.
- **Rückwirkende Neubewertung, ob eine Regel selbst noch sinnvoll ist** — Strang 2 entfernt ausschließlich Herkunftszitate, ändert aber keine einzige Verhaltensregel inhaltlich; das ist explizit nicht Teil dieser Spec.
