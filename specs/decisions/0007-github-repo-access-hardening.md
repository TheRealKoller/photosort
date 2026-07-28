# 0007 - GitHub-Repository-Zugriffshärtung

**Status:** Accepted
**Datum:** 2026-07-28

## Kontext

Repo `TheRealKoller/photosort` ist public. Ist-Zustand-Prüfung (`gh api`) ergab: genau ein Collaborator mit Schreibzugriff (Daniel, Rolle `admin`), keine Deploy Keys, keine Push-Restrictions, Branch Protection auf `main` mit `required_approving_review_count: 1`, aber `enforce_admins: false`. Da Daniel als PR-Autor sein eigenes Review laut GitHub-Regel nicht zur Erfüllung der Anforderung zählen lassen kann und weder er noch GitHub Copilot je mit Status "Approved" reviewen (beide nur "Commented"), war die Review-Anforderung faktisch nie erfüllbar und wurde bei allen bisherigen PRs (#1–#3) ausschließlich über den Admin-Bypass umgangen — eine Regel, die nie greift, ist keine echte Absicherung.

Auslöser für die Klärung *jetzt*: Daniel plant, PhotoSort künftig über ein separates, externes Tool ("Dockhand") automatisiert aus dem main-Branch auszuchecken, zu bauen und zu deployen. Dockhand selbst ist nicht Teil dieser Spec/ADR (eigenes künftiges Thema), aber sobald es angebunden ist, hat automatisiert deployter Code direkten Zugriff auf reale Zugangsdaten (OpenCloud App-Token, JWT `secret_key`, DB-Credentials, siehe `specs/architecture/0003-securitykonzept.md`). Diese ADR ist daher als Vorbedingung/Gate *vor* der Dockhand-Anbindung zu verstehen, nicht als Reaktion auf einen bereits laufenden Automatismus.

Ein zweiter, unabhängiger Punkt: Vorsorge für eine künftige, noch nicht gebaute Hintergrund-Automatisierung (siehe `CLAUDE.md`, Abschnitt "Hintergrund-Automatisierung"), die von Dritten erstellte Issues nur bearbeiten soll, wenn Daniel sie explizit freigegeben hat — bei von Daniel selbst erstellten Issues ist die Freigabe hingegen automatisch impliziert, ein Label ist dafür nicht nötig (siehe Spec 0007, Akzeptanzkriterium Teil 2b, und `CLAUDE.md`).

2FA/Account-Absicherung ist explizit nicht Teil dieser ADR — Daniels persönliche Verantwortung außerhalb des Projekt-Scopes.

## Entscheidung

### Branch Protection auf `main`

| Setting | Vorher | Nachher |
|---|---|---|
| `required_status_checks.contexts` | `backend`, `frontend`, `docker-compose-check` | unverändert |
| `required_status_checks.strict` | `true` | unverändert |
| `required_pull_request_reviews.required_approving_review_count` | `1` (faktisch nie erfüllbar) | **`0`** |
| `required_pull_request_reviews.require_code_owner_reviews` | `false` | unverändert (`false`, kein CODEOWNERS — bei einem Collaborator ohne Mehrwert) |
| `enforce_admins` | `false` | **`true`** |
| `required_conversation_resolution` | nicht gesetzt | **`true`** (neu) |
| `allow_force_pushes` | `false` | unverändert |
| `allow_deletions` | `false` | unverändert |
| `restrictions` (Push-Restrictions) | nicht gesetzt (`null`) | unverändert |

Die Copilot-Review-Praxis aus `CLAUDE.md` (`gh pr edit <PR> --add-reviewer "@copilot"`, Findings bewerten) bleibt **Pflicht-Praxis**, wird aber bewusst **kein** technisches Gate in der Branch Protection — es gibt niemanden, der ein solches Gate formal erfüllen könnte.

### Collaborators / Deploy Keys / Tokens

Keine Änderung am Ist-Zustand nötig (ein Collaborator, Daniel, `admin`; keine Deploy Keys; keine Push-Restrictions) — wird ab jetzt als Baseline dokumentiert (siehe Konsequenzen), damit künftige unbeabsichtigte Änderungen auffallen.

### Issue-Freigabe für künftige Automatisierung

Label `approved-for-agent` (manuell von Daniel vergeben), Policy in `CLAUDE.md` dokumentiert. Reine Vorbereitung — hat vorerst keine technische Wirkung, da die Hintergrund-Automatisierung selbst noch nicht existiert; die künftige Prüflogik ist explizit außerhalb des Scopes dieser ADR.

## Begründung

- **`required_approving_review_count: 0` statt weiterhin `1`:** Eine Anforderung, die ausschließlich über Admin-Bypass umgangen wird, täuscht eine Absicherung vor, die nicht existiert (Stakeholder-Entscheidung, siehe Kontext). Explizit auf 0 statt Entfernen des gesamten `required_pull_request_reviews`-Objekts, damit `require_code_owner_reviews: false` und künftige Optionen in diesem Objekt weiterhin explizit (nicht implizit über Objekt-Absenz) gesetzt bleiben.
- **`enforce_admins: true` (neu):** Solange die Review-Anforderung nur über den Admin-Bypass umgangen wurde, war `enforce_admins: false` die einzige Möglichkeit, überhaupt zu mergen — mit `required_approving_review_count: 0` entfällt dieser Zwang. Der einzige verbleibende Bypass-Effekt von `enforce_admins: false` wäre, dass Daniel als Admin auch mit rotem CI oder nicht aktuellem Branch mergen könnte. `CLAUDE.md` schreibt bereits als Prozessregel vor, dass CI grün sein muss, bevor ein PR gemerged wird — `enforce_admins: true` macht diese Regel technisch verbindlich statt nur Prozessregel, ohne neue Kosten (Daniel ist ohnehin an CI-grün gebunden).
- **`required_conversation_resolution: true` (neu):** Technische Detailentscheidung innerhalb der bereits akzeptierten Härtungsrichtung, kein eigenständiges Rückfrage-Thema (geringe, gut reversible Kosten). Ersetzt kein Approval, aber verhindert, dass ein offener Kommentar-Thread (von Daniel selbst oder von Copilot) beim Merge stillschweigend untergeht — ein leichtgewichtiges Substitut für das entfernte, nie funktionierende Approval-Gate.
- **`restrictions` weiterhin nicht gesetzt:** Bei genau einem Collaborator ohne Mehrwert; explizit zu revisitieren, sobald ein zweiter Actor (z.B. ein künftiger Automatisierungs-Agent-Token) Schreibzugriff erhält — das ist laut Kontext bewusst nicht Teil dieser ADR (der Token existiert noch nicht).

## Konsequenzen

- Jeder künftige PR kann von Daniel direkt gemerged werden, sobald CI grün, der Branch aktuell und alle Konversationen aufgelöst sind — kein blockierendes, nie erfüllbares Approval-Requirement mehr, aber auch kein Bypass eines roten CI-Laufs mehr, nicht einmal für dringende Fixes.
- Ist-Zustand von Collaborators/Deploy-Keys/Branch-Protection wird ab jetzt in [`architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md) (neue Sektion "GitHub-Repository-Zugriff", vom `security-engineer` zu ergänzen) als Baseline mit Datum dokumentiert. Künftige Audits vergleichen den tatsächlichen GitHub-Zustand (`gh api repos/TheRealKoller/photosort/branches/main/protection`, `.../collaborators`, `.../keys`) gegen diese Baseline — es gibt keine automatisierte Drift-Erkennung (Out of Scope, siehe Feature-Spec 0007).
- Diese ADR ist explizit Vorbedingung vor der Anbindung von Dockhand — sobald automatisiert deployter Code Zugriff auf reale Zugangsdaten erhält, ist ein sauberer, tatsächlich wirksamer main-Branch-Schutz und eine dokumentierte Zugriffs-Baseline Voraussetzung, kein optionales Nice-to-have.
- Label `approved-for-agent` und dessen Policy-Text in `CLAUDE.md` haben keine Code-Konsequenz in diesem Repo-Stand; die Prüflogik folgt erst mit der künftigen Hintergrund-Automatisierung (eigene, spätere Spec).
- 2FA/Account-Absicherung bleibt bewusst außerhalb dieser ADR (Daniels persönliche Verantwortung).
