# 0007 - GitHub-Repo-Zugriffshärtung & Issue-Freigabe-Vorsorge

**Status:** Accepted
**Erstellt:** 2026-07-28
**Bezug:** `idea-sharpener`-Gespräch mit Daniel, 2026-07-28. ADR: [`decisions/0007-github-repo-access-hardening.md`](../decisions/0007-github-repo-access-hardening.md).

## Ziel

Das GitHub-Repo `TheRealKoller/photosort` ist public. Schreibzugriff soll ausschließlich bei Daniel und von ihm beauftragten KI-Agenten liegen — niemand sonst darf Code committen oder pushen können. Die bestehende Branch Protection auf `main` hat eine Lücke: die formale Review-Anforderung (`required_approving_review_count: 1`) war nie erfüllbar (Daniels eigene Reviews zählen laut GitHub-Regel nicht, Copilot reviewt nur kommentierend) und wurde bei allen bisherigen PRs ausschließlich über den Admin-Bypass (`enforce_admins: false`) umgangen — eine Regel, die nie greift, täuscht eine Absicherung vor, die nicht existiert.

Auslöser für die Klärung *jetzt*: Daniel plant, PhotoSort künftig über ein separates externes Tool ("Dockhand", nicht Teil dieser Spec) automatisiert aus dem Git-Repo zu bauen und per docker-compose zu deployen. Sobald das angebunden ist, hat automatisiert deployter Code direkten Zugriff auf reale Zugangsdaten (OpenCloud App-Token, JWT `secret_key`, DB-Credentials) und potenziell auf Familienfotos. Diese Spec ist als Vorbedingung/Gate zu verstehen, bevor Dockhand für PhotoSort angebunden wird — nicht als Reaktion auf ein konkretes Ereignis (allgemeine Vorsorge).

Zusätzlich, als Vorsorge für die in `CLAUDE.md` angekündigte, noch nicht existierende "Hintergrund-Automatisierung": von Dritten erstellte GitHub Issues sollen erst nach Daniels expliziter Freigabe automatisiert bearbeitet werden dürfen.

## User Story

Als Daniel (alleiniger Repo-Owner und Stakeholder) möchte ich, dass niemand außer mir oder einer von mir beauftragten KI Schreibzugriff auf das PhotoSort-Repository hat, und dass von Dritten erstellte Issues erst nach meiner expliziten Freigabe automatisiert bearbeitet werden, damit das öffentliche Repository auch bei künftiger Automatisierung (insbesondere dem geplanten automatisierten Deploy via Dockhand) sicher bleibt.

## Akzeptanzkriterien

**Teil 1 — Repo-Härtung**

- [ ] Branch Protection auf `main` wird in einem einzigen `PUT`-Request (nicht mehreren sequenziellen PATCHes, da die GitHub-API das gesamte Objekt ersetzt) auf den in ADR 0007 festgelegten Ziel-Zustand gebracht: `enforce_admins: true`, `required_pull_request_reviews.required_approving_review_count: 0`, `required_conversation_resolution: true`, `required_status_checks` (`backend`, `frontend`, `docker-compose-check`, `strict: true`) unverändert, `allow_force_pushes: false`, `allow_deletions: false`, `restrictions: null` unverändert.
  - **Vorab zu verifizieren:** GitHub-API-Doku nennt für `required_approving_review_count` einen Wertebereich 1–6. Empirisch prüfen, ob `0` akzeptiert wird; falls nicht, stattdessen das gesamte `required_pull_request_reviews`-Objekt entfernen (funktional gleichwertig) und das im Securitykonzept-Abschnitt so dokumentieren.
- [ ] Vor der Änderung wird der vollständige Ist-Zustand von `.../branches/main/protection` gesichert; nach der Änderung wird ein Diff über **alle** Felder gezogen (nicht nur die genannten), um unbeabsichtigte Nebenwirkungen des Objekt-Replace auszuschließen.
- [ ] Funktionaler Nachweis an einem Wegwerf-Branch/-PR: (a) ein Merge-Versuch mit absichtlich rotem CI-Check wird von `enforce_admins: true` blockiert, auch für Daniel als Admin; (b) ein Merge-Versuch mit bewusst offen gelassenem Kommentar-Thread wird von `required_conversation_resolution: true` blockiert und ist nach Auflösen möglich.
- [ ] `gh api repos/TheRealKoller/photosort/collaborators` liefert genau einen Eintrag (`TheRealKoller`, `permissions.admin: true`); `.../keys` liefert ein leeres Array (keine Deploy Keys). Zusätzlich geprüft: installierte GitHub Apps (z.B. Copilot-Reviewer) haben keinen Schreibzugriff auf Code, nur Kommentar-/Review-Rechte.
- [ ] Neue Sektion **"GitHub-Repository-Zugriff"** in `specs/architecture/0003-securitykonzept.md` (platziert nach "Secrets-Handling", vor "Angriffsflächen") dokumentiert den verifizierten Ist-Zustand konkret und datiert (Collaborators, Deploy Keys, finale Branch-Protection-Werte), verweist auf ADR 0007, und hält fest, dass die Baseline vor Anbindung von Dockhand erneut zu prüfen ist.
- [ ] ADR [`decisions/0007-github-repo-access-hardening.md`](../decisions/0007-github-repo-access-hardening.md) — bereits angelegt, Status `Accepted`.

**Teil 2 — Issue-Freigabe-Vorsorge**

- [ ] GitHub-Label `approved-for-agent` existiert im Repo (Farbe `0E8A16`, Beschreibung z.B. "Von Daniel freigegeben zur Bearbeitung durch eine künftige Hintergrund-Automatisierung").
- [ ] `CLAUDE.md`, Abschnitt "Hintergrund-Automatisierung", enthält unzweideutig: (a) Issues, deren Autor nicht Daniels GitHub-Account ist, dürfen erst nach Vergabe des Labels `approved-for-agent` automatisiert bearbeitet werden; (b) von Daniel selbst erstellte Issues benötigen das Label nicht; (c) entscheidend ist der Label-**Zustand zum Zeitpunkt der automatisierten Bearbeitung**, nicht ob es je vergeben wurde (ein wieder entferntes Label gilt nicht mehr als Freigabe).
- [ ] Explizit dokumentiert als Out of Scope: die technische Prüflogik (Label-Abfrage vor automatisierter Bearbeitung) — folgt erst mit der künftigen, noch nicht existierenden Hintergrund-Automatisierung.

## Datenmodell-Bezug

Keines — reine GitHub-Repo-Konfiguration und Dokumentation, keine Berührung mit der PhotoSort-Datenbank oder Anwendungscode.

## Architektur / Umsetzung

### Neue ADR

[`decisions/0007-github-repo-access-hardening.md`](../decisions/0007-github-repo-access-hardening.md) (Accepted) hält die dauerhafte Sicherheits-Policy-Entscheidung fest: finale Branch-Protection-Werte für `main` und die Begründung, warum `enforce_admins` und `required_conversation_resolution` gegenüber dem Ist-Zustand geändert werden. Diese Spec setzt die ADR um, trifft aber selbst keine neuen Grundsatzentscheidungen mehr.

### GitHub — Branch Protection auf `main`

Ziel-Zustand (siehe ADR 0007 für die vollständige Begründung je Zeile):

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["backend", "frontend", "docker-compose-check"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "require_code_owner_reviews": false
  },
  "required_conversation_resolution": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

Umsetzung per `gh api --method PUT repos/TheRealKoller/photosort/branches/main/protection --input <datei>` (kein Terraform/IaC — bewusst nicht eingeführt, einmalige Änderung an einem Einzelprojekt, kein wiederkehrender Multi-Repo-Bedarf). Änderungen gegenüber dem Ist-Zustand: `required_approving_review_count` 1→0, `enforce_admins` false→true, `required_conversation_resolution` neu (true). Alle übrigen Werte unverändert.

Verifikation: `gh api repos/TheRealKoller/photosort/branches/main/protection` muss exakt obige Werte zurückliefern — manueller Akzeptanzkriterien-Check, kein automatisierter Test (GitHub-Repo-Konfiguration außerhalb der Codebasis).

### GitHub — Collaborators / Deploy Keys / Tokens

Keine technische Änderung nötig (bereits minimal: ein Collaborator, keine Deploy Keys, keine Push-Restrictions). Wird dokumentiert (siehe Securitykonzept-Sektion unten).

### Dokumentation des Ist-Zustands — `specs/architecture/0003-securitykonzept.md`

Neue Sektion **"GitHub-Repository-Zugriff"**, platziert nach "Secrets-Handling" und vor "Angriffsflächen". Enthält: Snapshot mit Datum (Collaborators, Deploy Keys, Push-Restrictions, finale Branch-Protection-Werte), Verweis auf ADR 0007, Hinweis, dass dies eine manuell zu pflegende Baseline ohne automatisiertes Drift-Scanning ist, und dass sie vor Anbindung von Dockhand erneut zu prüfen ist, sobald dessen konkrete Zugriffsanforderungen feststehen.

### Dokumentation der Issue-Freigabe-Policy — `CLAUDE.md`

Ergänzung im bestehenden Abschnitt "Hintergrund-Automatisierung (Ausbaustufe)": Label `approved-for-agent`, manuell von Daniel vergeben für Issues, die nicht von ihm selbst erstellt wurden; Bedingung, die eine künftige Automatisierung vor Bearbeitung prüfen wird (Prüflogik selbst außerhalb des Scopes dieser Spec). Kurzer Verweis auf ADR 0007.

### README.md

Keine Änderung nötig — GitHub-Zugriffskonfiguration ist kein lokales Setup-Thema, gehört konzeptionell zu `architecture/0003-securitykonzept.md`.

### Umsetzungsreihenfolge

1. Branch-Protection-Settings via `gh api` anwenden und verifizieren.
2. `CLAUDE.md`-Ergänzung (Label-Policy).
3. `specs/architecture/0003-securitykonzept.md`-Ergänzung (Sektion "GitHub-Repository-Zugriff").
4. Label `approved-for-agent` im Repo anlegen (`gh label create`).

## UI/UX

Nicht relevant — reine Repo-Konfiguration/Dokumentation, keine Frontend-Änderung. Bestätigt durch `ux-ui-designer`: keine neuen/geänderten Backend-Endpunkte, keine Datenmodell-Änderung, kein Bezug zu `frontend/src/`, kein Aspekt, der das Design-System (`architecture/0004-design-system.md`) berührt.

## Security

**Sicherheitsrelevanz:** Hoch — das Feature ändert unmittelbar Zugriffskontroll-Primitive des Repos (Branch Protection, Collaborator-Modell, künftige Freigabe-Policy für Automatisierung). Es ist selbst eine Sicherheitsmaßnahme, aber wie jede Zugriffskontroll-Konfiguration auch selbst fehleranfällig.

**Bedrohungen und Gegenmaßnahmen:**

1. Ungewollter Direkt-Push/Force-Push/Branch-Löschung auf `main`, versehentlich (Daniel) oder durch kompromittiertes Schreibzugriffs-Credential → `allow_force_pushes: false`, `allow_deletions: false` (unverändert, jetzt durch `enforce_admins: true` auch für den Admin-Account selbst durchgesetzt statt umgehbar).
2. Merge von PRs mit rotem CI oder ungelöster Diskussion, weil das bisherige, faktisch nie erfüllbare Approval-Gate bislang nur über Admin-Bypass umgangen wurde → `required_approving_review_count: 0` (ehrliche statt vorgetäuschte Anforderung), kombiniert mit `enforce_admins: true` (CI-grün und `required_conversation_resolution: true` gelten jetzt technisch verbindlich, auch für den Admin).
3. Stiller Drift der Zugriffs-Baseline (neuer Collaborator, neuer Deploy Key, geänderte Branch Protection) bleibt unbemerkt, da GitHub-Repo-Einstellungen anders als Code nicht durch Reviews/CI laufen → Ist-Zustand wird als datierte Baseline in `specs/architecture/0003-securitykonzept.md` dokumentiert; künftige Audits vergleichen den tatsächlichen Zustand dagegen. Empfehlung: wiederkehrender manueller Prüfpunkt, mindestens unmittelbar vor Anbindung von Dockhand.
4. Ungeprüfte Bearbeitung von Issues durch eine künftige Hintergrund-Automatisierung → Label `approved-for-agent`, manuell vergeben, als Vorbedingung dokumentiert in `CLAUDE.md`. Hat aktuell keine technische Wirkung (Automatisierung existiert noch nicht) — reine Vorsorge.

**Einordnung: was diese Härtung tatsächlich schützt — und was nicht.** Aktuell hat ausschließlich Daniel Schreibzugriff (`admin`). Branch-Protection-Einstellungen sind selbst Repo-Konfiguration, die ein Admin-Account jederzeit ändern kann. Ein tatsächlich kompromittierter Daniel-Account (gestohlene Session/Token, Phishing) kann `enforce_admins` selbst wieder deaktivieren oder die Branch Protection entfernen — diese Spec verhindert das nicht und kann es prinzipiell nicht, solange es nur einen Admin-Account gibt. Was die Härtung real leistet:

- Schutz vor **Daniels eigenen versehentlichen Aktionen** (Force-Push, Merge bei rotem CI, übersehener offener Kommentar) — der Hauptnutzen im aktuellen Ein-Personen-Zustand.
- Schutz vor einem **künftigen, nicht-administrativen Automatisierungs-Token** (z.B. ein späterer Agent- oder Dockhand-Token mit eingeschränkten Rechten) — für einen solchen Actor greifen die Regeln verbindlich.
- **Keinen** Schutz vor einer vollständigen Kompromittierung des einzigen Admin-Accounts selbst — die einzige wirksame Gegenmaßnahme dagegen ist Kontosicherheit (2FA etc.), explizit außerhalb des Scopes dieser Spec.

`required_approving_review_count: 0` + `enforce_admins: true` sind in Summe konsistent, keine versteckte Lücke — sie adressieren unterschiedliche Bedrohungen (ehrlicher Verzicht auf ein nie erfüllbares Review-Gate vs. verbindliche Durchsetzung der übrigen, tatsächlich wirksamen Regeln). Einzige Prämisse: `required_approving_review_count: 0` ist nur so lange unproblematisch, wie ausschließlich Daniel Schreibzugriff hat — sobald ein zweiter Actor mit Schreibzugriff hinzukommt, ist das erneut zu bewerten (in ADR 0007 vermerkt).

**Dockhand-Zugriffsmodell:** zu Recht Out of Scope dieser Spec. Unverbindliche Leitplanke für eine künftige Dockhand-Spec: Ein reines Build-/Deploy-Tool, das `main` nur auscheckt und baut, braucht plausibel nur **Lesezugriff** auf das Repository, kein Schreibzugriff — sieht die künftige Spec einen Token mit Schreibrechten vor, sollte das ein bewusst begründeter Schritt sein, kein Default.

**Deploy Keys/Tokens/GitHub Apps:** einmalige Dokumentation der aktuellen Baseline (keine vorhanden) reicht als Ausgangspunkt, aber nicht als Dauerzustand — wiederkehrender manueller Prüfpunkt, mindestens vor Anbindung von Dockhand.

## Teststrategie

Dieses Feature enthält keinen Anwendungscode — `pytest`/`vitest` und das Backend-Coverage-Gate (`--cov-fail-under=80`) sind **nicht anwendbar**. Verifikation erfolgt dreistufig (siehe `architecture/0002-testkonzept.md`, neue Sektion "Repo-Konfiguration & Dokumentation (kein Anwendungscode)"):

1. **Config-Check:** `gh api`-Vorher/Nachher-Diff des vollständigen Branch-Protection-Objekts sowie von `/collaborators` und `/keys`, gegen den echten Repo-Zustand (keine Sandbox verfügbar).
2. **Funktionaler Repro-Test:** an einem Wegwerf-PR wird nachgewiesen, dass `enforce_admins` und `required_conversation_resolution` tatsächlich blockieren, nicht nur, dass die API sie als aktiviert meldet.
3. **Dokumentations-Review:** Checkliste, dass `CLAUDE.md`/`architecture/0003-securitykonzept.md` die konkreten, unzweideutigen Policy-/Baseline-Inhalte enthalten (nicht nur Verweise).

Wichtigster technischer Vorbehalt: unklar, ob `required_approving_review_count: 0` von der GitHub-API tatsächlich akzeptiert wird (Doku nennt 1–6) — vor Abhaken des entsprechenden Kriteriums empirisch per `gh api` zu prüfen; bei Ablehnung stattdessen das gesamte `required_pull_request_reviews`-Objekt entfernen (funktional gleichwertig).

## Offene Fragen

Keine — alle im Gespräch aufgeworfenen Punkte (Scope, enforce_admins-Konflikt, 2FA-Ausschluss, Label-Mechanismus, Dockhand-Abgrenzung) wurden mit Daniel geklärt bzw. sind in ADR 0007 entschieden.

## Out of Scope

- Implementierung der Dockhand-Anbindung selbst (separate, künftige Spec) — inklusive dessen konkretem Zugriffsmodell/Token-Scope.
- Implementierung der Hintergrund-Automatisierung selbst (separate, künftige Spec) — inklusive der technischen Prüflogik für das Label `approved-for-agent`.
- 2FA/Account-Absicherung von Daniels GitHub-Account (persönliche Verantwortung außerhalb des Projekt-Scopes).
- Automatisiertes Drift-Scanning der Branch-Protection-Baseline.
- Ein zweiter Repo-Actor/Automatisierungs-Token und damit verbundene Push-Restrictions (`restrictions`) — erst relevant, sobald ein solcher Token tatsächlich existiert.
