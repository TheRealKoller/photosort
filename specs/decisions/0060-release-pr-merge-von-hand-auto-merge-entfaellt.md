# 0060 - Release-PR wird von Hand gemergt, der Auto-Merge-Step entfällt

**Status:** Accepted
**Datum:** 2026-09-06

## Kontext

ADR [`0008`](./0008-automated-semver-releases.md) legte als zweiten Step von `.github/workflows/release-please.yml` einen Self-Merge des Release-PRs fest (`gh pr merge --auto --squash`, `if: steps.release.outputs.pr`, PR-Nummer über `env: PR_NUMBER: ${{ fromJson(steps.release.outputs.pr).number }}`). Ziel war ein Release ohne jeden Klick von Daniel.

Dieser Step hat seit seiner Einführung nie gegriffen. GitHub Actions wertet die `env:`-Ausdrücke eines Steps auch dann aus, wenn dessen `if:` zu `false` auswertet. Liefert `release-please` keinen PR-Output, bekommt `fromJson()` einen leeren String, und der Lauf endet mit

```
##[error]The template is not valid. .github/workflows/release-please.yml (Line: 38, Col: 22):
Error reading JToken from JsonReader. Path '', line 0, position 0.
```

Der Fehler trat in allen 40 zuletzt gelisteten Läufen auf, zuletzt in Run `34055552212` (2026-09-06). Die eigentliche Release-Arbeit (Step 1) ist zu diesem Zeitpunkt bereits abgeschlossen — der Schaden ist deshalb nicht ein ausgefallener Automatismus, sondern ein Signal, das dauerhaft auf Rot steht und damit nichts mehr aussagt: ein echter Release-Fehler wäre darin nicht zu erkennen.

Daniel prüft und mergt Release-PRs bewusst selbst und will das beibehalten (bindende Produktentscheidung, nicht Gegenstand dieser ADR).

## Entscheidung

1. **Der Auto-Merge-Step entfällt ersatzlos.** Keine reparierte Variante (weder ein zusätzlicher Guard im Ausdruck noch ein Ausweichen auf `outputs.prs`, ein zweiter Job oder ein separater Workflow). Der Release-PR wartet sichtbar auf Daniels eigenen Merge.
2. **`release-please.yml` besteht dauerhaft aus genau einem Step** — der auf Commit-SHA gepinnten `release-please-action` — und wertet in keinem `${{ }}`-Ausdruck mehr einen Step-Output aus. Als Regel für künftige Erweiterungen: Ein Step, der einen Output eines vorherigen Steps in `env:`/`with:`/`run:` interpoliert, muss den Leer-Output-Fall selbst tragen; `if:` schützt nicht davor, weil GitHub die Ausdrücke eines Steps unabhängig vom `if:`-Ergebnis auswertet. Diese Regel wird durch einen Guard-Test in `scripts/tests/` gehalten, nicht nur durch Prosa im Workflow-Kommentar.
3. **Kein Workflow im Repository mergt selbst nach `main`.** Mit dem Step verschwindet der einzige unbeaufsichtigte Merge-Pfad; die Bedingung aus ADR [`0007`](./0007-github-repo-access-hardening.md) (`required_approving_review_count: 0` ist tragbar, solange ausschließlich Daniel schreibt) gilt damit wieder ungeschmälert, statt nur "im Geiste berührt" zu sein.
4. **Das Repo-Setting `allow_auto_merge` bleibt unverändert `true`.** Es ist eine Fähigkeit, kein Pfad: GitHubs Auto-Merge muss pro PR von einem Menschen aktiviert werden. Abschalten brächte keinen Sicherheitsgewinn (der automatisierte Pfad verschwindet mit dem Step), nähme Daniel aber eine manuelle Option. **Lesart für künftige Audits:** `allow_auto_merge: true` belegt ab jetzt nicht mehr, dass ein automatisierter Merge-Pfad existiert.

8. **Der CI-Job `demo-scripts` wird Required Status Check der Branch Protection auf `main`** (Entscheidung Daniels, 2026-09-06, nachträglich zu dieser ADR ergänzt). Der Guard-Test aus Punkt 2 hält drei Invarianten, darunter das Verbot von `pull_request_target` in jedem Workflow — für ein public Repo das schärfste Muss-Kriterium aus Spec 0008, weil ein solcher Trigger Fork-PRs Zugriff auf `RELEASE_PLEASE_TOKEN` gäbe. `demo-scripts` war bis dahin kein Required Check (gemessen 2026-09-06: `backend`, `frontend`, `docker-compose-check`, `e2e`); ein Fehlschlag war sichtbar, blockierte den Merge aber nicht. Für Konsistenztests an Prozess-Metadaten wäre das vertretbar, für eine Sicherheitsinvariante ist es die Differenz zwischen Hinweis und Schranke. Preis der Entscheidung, bewusst getragen: Ab jetzt kann **jeder** Test unter `scripts/tests/` einen Merge blockieren, nicht nur die Sicherheitsinvarianten. Vertretbar, weil der Job netzwerkfrei und schnell ist. Geändert wird ausschließlich `required_status_checks.contexts`; die Branch-Protection-API ersetzt bei `PUT` das gesamte Objekt, der Aufruf muss den übrigen Zustand deshalb vollständig mitführen.
5. **Der Scope des `RELEASE_PLEASE_TOKEN` bleibt unverändert** (`Contents: Read & write`, `Pull requests: Read & write`, `Issues: Read & write`, `Metadata: Read`). Durch den Wegfall wird keine Permission frei: `gh pr merge --auto` brauchte `Pull requests: write`, das `release-please` für Anlage und Aktualisierung des Release-PRs ohnehin braucht. Es gibt deshalb auch keine Folge-Story "Scope reduzieren".
6. **Die Ausnahme "kein Copilot-Review auf Release-PRs" (ADR 0008) bleibt bestehen**, ruht ab jetzt aber nur noch auf dem inhaltlichen Argument (rein mechanischer Diff aus Versionsfeldern und Changelog, an dem ein Code-Review nichts findet). Das zweite Argument — `required_conversation_resolution: true` würde einen offenen Review-Thread zum Dauerblocker des Vollautomatismus machen — entfällt mit dem Automatismus.
7. **Der `permissions:`-Block des Workflows bleibt unverändert** (`contents: write`, `issues: write`, `pull-requests: write`). Er gilt dem `GITHUB_TOKEN`; der Workflow arbeitet durchgängig mit dem PAT. Eine Anpassung wäre eine eigene, von diesem Fehlerbild unabhängige Änderung.

## Begründung

- **Streichen statt Reparieren:** Ein Guard im Ausdruck (`${{ steps.release.outputs.pr && fromJson(...).number || '' }}`) würde den Lauf grün bekommen, aber genau den unbeaufsichtigten Merge-Pfad erhalten, den Daniel nicht will. Die einfachste Lösung ist hier zugleich die sicherere: ein Step weniger, eine Fehlerquelle weniger, ein automatisierter Schreibpfad nach `main` weniger.
- **Guard-Test statt Kommentar:** Die Fehlerklasse ist unauffällig (der Ausdruck sieht durch das `if:` abgesichert aus) und wurde über 40 Läufe hinweg nicht als Fehler erkannt, sondern als Rauschen ignoriert. Eine Prosa-Warnung im Workflow hätte dieselbe Halbwertszeit; ein Test in der bestehenden `scripts/tests/`-Reihe (CI-Job `demo-scripts`) wird rot, bevor das Muster erneut auf `main` landet.
- **Verworfen — `allow_auto_merge: false`:** siehe Entscheidung 4; Sicherheitsgewinn null, Komfortverlust real.
- **Verworfen — Anheben der Action-Version im selben Zug** (Node-20-Deprecation-Warnung im Lauf-Log): Der Runner erzwingt bereits Node 24 und die Action läuft damit durch ("are being forced to run on Node.js 24"). Es gibt kein Fehlerbild, nur eine Warnung, die mit dem nächsten regulären Versionssprung der Action verschwindet. Ein Sprung jetzt wäre eine Supply-Chain-Änderung (neuer SHA, neue Verifikation) und würde die Aussagekraft des einen echten Nachweis-Laufs verwässern, der der einzige verfügbare Beleg dieser Änderung ist.

## Konsequenzen

- Ein roter `release-please`-Lauf bedeutet ab sofort wieder, dass tatsächlich etwas kaputt ist.
- Ein Release entsteht erst, wenn Daniel den Release-PR mergt. Übersieht er ihn, bleibt der Release aus — dieselbe bewusst akzeptierte Lücke wie zuvor (kein Monitoring, kein Alarm; siehe Spec 0008, "Rollback-/Fehlerfall"), nur mit einem Menschen statt einer Automatisierung als Auslöser.
- ADR [`0008`](./0008-automated-semver-releases.md) ist an genau einer Stelle teilweise superseded: Abschnitt "Workflow-Ablauf", zweiter Step (Self-Merge). Alle übrigen Entscheidungen dieser ADR — Tooling, `release-type: simple`, Manifest als Source of Truth, `extra-files`, SHA-Pinning, PAT statt `GITHUB_TOKEN`, Trigger strikt `push: branches: [main]` — bleiben unverändert in Kraft.
- Prüfbarkeit: Der Workflow triggert weiterhin ausschließlich auf `push: branches: [main]` und ist vor dem Merge nicht real ausführbar. Es gilt das Ersatzmuster aus `specs/architecture/0002-testkonzept.md` (realer erster Lauf als Probe, verschärfte Vorab-Validierung).

## Beobachtung (nicht Gegenstand dieser Entscheidung)

Im selben Lauf-Log (`34055552212`) fällt ein davon unabhängiger, zweiter Defekt auf: Die letzten drei Merge-Commits auf `main` konnten von `release-please` nicht geparst werden (`commit could not be parsed`, danach `Considering: 0 commits` → `No commits for path: ., skipping`), weil ihre Squash-Titel keinen Conventional-Commit-Präfix tragen. Seit `v0.35.0` ist deshalb weder ein Release-PR noch ein Release entstanden. Das ist eine eigene Fehlerklasse (Commit-Titel-Konvention, nicht Workflow-Syntax) und wird hier ausdrücklich nicht mitentschieden — festgehalten, damit spätere Leser die Aussage "der Release-PR entsteht korrekt" nicht ungeprüft übernehmen.
