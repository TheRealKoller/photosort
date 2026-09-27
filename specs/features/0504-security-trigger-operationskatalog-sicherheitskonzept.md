# 0504 - Security-Review greift bei Operationskatalog und Sicherheitskonzept

**Status:** Accepted
**Erstellt:** 2026-09-27
**Bezug:** [Issue #504](https://github.com/TheRealKoller/photosort/issues/504)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec den Wortlaut der Auslöser und der
Konzeptvermerke festlegt, den die drei Stellen gleichlautend tragen müssen.

## Ziel

Die Sicherheitsperspektive im Review eines Pull Requests läuft von selbst, wenn der Pull Request den
GitHub-Operationskatalog (`.claude/skills/github-access/`) oder das Sicherheitskonzept
(`specs/architecture/0003-securitykonzept.md`) ändert. Heute trifft ein solcher Pull Request keinen
Auslöser; sie läuft nur, wenn jemand die Rückfallregel „im Zweifel läuft die Perspektive" anwendet.

Der Zuschnitt ist eng: genau diese zwei Texte, nach dem Muster der bestehenden Einzelauslöser. Der
Preis ist angenommen: Die Sicherheitsperspektive läuft danach bei etwa jedem sechsten Pull Request
zusätzlich.

## User Story

Als Daniel, der als Einziger Änderungen am Entwicklungsablauf freigibt, möchte ich, dass die
Sicherheitsperspektive im Review von selbst läuft, sobald ein Pull Request den
GitHub-Operationskatalog oder das Sicherheitskonzept ändert, damit Änderungen an den Härtungsregeln
und an der Sicherheitsnorm nicht davon abhängen, dass im Einzelfall jemand an die Rückfallregel denkt.

## Akzeptanzkriterien

- [ ] **AK 1:** Ändert ein Pull Request ausschließlich `.claude/skills/github-access/SKILL.md`, lautet
  die Protokollzeile `review-security` „gelaufen (`.claude/skills/github-access/**`)" — nicht
  „Trigger unklar, deshalb ausgeführt".
- [ ] **AK 2:** Ändert ein Pull Request ausschließlich `specs/architecture/0003-securitykonzept.md`,
  lautet sie „gelaufen (`specs/architecture/0003-securitykonzept.md`)" — nicht „Trigger unklar,
  deshalb ausgeführt".
- [ ] **AK 3:** Ändert ein Pull Request ausschließlich `.claude/skills/refinement/SKILL.md`, lautet sie
  „geskippt", und die Perspektive wird nicht ausgeführt.
- [ ] **AK 4:** In `.claude/skills/review/SKILL.md` Schritt 3, ADR 0040 Teil 2 und ADR 0014 Teil 1
  ändert sich außerhalb der Security-Zeile nichts; in der Security-Zeile gibt es nur Einfügungen
  (einzige Löschung: der Satzendpunkt, der hinter den letzten Eintrag wandert). Die Änderung in
  Schritt 5 ändert die Perspektivenauswahl nicht.
- [ ] **AK 5:** Hinter jedem neuen Pfad steht eine Klammer, gebaut wie beim Eintrag
  `scripts/nummern.py`: ein Satz, Teilsätze mit `;` oder `—`; ihr erster Teil nennt, was der Text
  sicherheitsrelevant festlegt.
- [ ] **AK 6:** Der Abgleich nach Testkonzept „Agenten-Steuerungslogik selbst" Punkt 1 findet für die
  Security-Zeile an den drei Stellen `review/SKILL.md` Schritt 3, ADR 0040 Teil 2 und ADR 0014 Teil 1
  dieselbe Menge an Einzelauslöser-Pfaden in derselben Reihenfolge — einschließlich
  `scripts/nummern.py` in ADR 0014 —, je neuem Eintrag denselben Begründungswortlaut (nur die ADRs
  tragen zusätzlich den Vermerk „ergänzt …"), und die Spec-Verweise der ADRs zeigen auf diese Datei.
  Das Ergebnis steht im Abschlussbericht.
- [ ] **AK 7:** Im Sicherheitskonzept tragen die Einträge „Trigger-Blindfleck, dritter dokumentierter
  Fall" (Punkt 11), „Dritter Fall desselben Pfadlisten-blinden-Flecks" (ADR 0085/Spec 0259) und „Auch
  `.claude/**` löst den `review-security`-Trigger nicht aus" (Spec 0288) je den Vermerk, dass die
  Lücke für den Operationskatalog mit dieser Spec geschlossen ist; der zweite nennt zusätzlich das
  Sicherheitskonzept und führt die Grundsatzfrage (`.claude/**`, `scripts/**`) ausdrücklich als
  offen. Keine Stelle des Konzepts erklärt sie für entschieden.
- [ ] **AK 8:** Ein Probelauf auf lokalen Branches mit je genau einer geänderten Datei (Nachweis:
  `--name-only`), Diff-Basis der Feature-Branch, zeigt für `review-security`: (1) Operationskatalog →
  gelaufen mit Eintrag, (2) Sicherheitskonzept → gelaufen mit Eintrag, (3) `refinement` → geskippt.
  Das Ergebnis steht als Tabelle in dieser Spec.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

**Ansatz:** zwei neue `oder`-Einträge in der `review-security`-Zeile der Trigger-Tabelle, angehängt
nach `scripts/nummern.py`, zuerst der Katalog, dann das Konzept. Keine neue ADR: Die Tabelle wird bei
unverändertem Grundprinzip (feste Tabelle, „im Zweifel läuft die Perspektive") erweitert; ADR-relevant
wäre erst die ausgeklammerte Grundsatzfrage.

**Wortlaut der Begründungen** (an allen drei Stellen gleich):

1. `.claude/skills/github-access/**` (der einzige Text, der jeden GitHub-Zugriff des
   Entwicklungsablaufs samt Härtungsregeln und Erlaubnisstufen festlegt — welche Operation an das
   öffentliche Repository schreibt und welcher fremdbeschreibbare Text gelesen wird; ohne den Eintrag
   träfe ein PR, der nur diese Datei anfasst, keinen einzigen Trigger; bewusst eng: das breitere
   `.claude/skills/**` bleibt außen vor)
2. `specs/architecture/0003-securitykonzept.md` (der Maßstab, gegen den die Sicherheitsperspektive
   selbst prüft — eine Änderung verschiebt Muss-Kriterien, akzeptierte Restrisiken und bekannte
   Lücken für jedes künftige Review; ohne den Eintrag träfe ein PR, der nur diese Datei anfasst,
   keinen einzigen Trigger; bewusst eng: das breitere `specs/architecture/**` bleibt außen vor)

Pfadform: Verzeichnis-Glob für den Skill wie bei `penpot-design/**` und `ship-entwurf/**`, exakter
Dateipfad für das Konzept wie bei `scripts/nummern.py`.

**Die drei Stellen, Reihenfolge der Änderung:**

1. ADR 0040 Teil 2 (Sync-Quelle): kleines `oder`, Klammer beginnt mit
   `ergänzt 2026-09-27 mit Spec 0504 — ` und trägt danach die Begründung.
2. `.claude/skills/review/SKILL.md` Schritt 3: `**oder** eine Datei unter `.claude/skills/github-access/**` (…)`
   bzw. `**oder** `specs/architecture/0003-securitykonzept.md` (…)`, ohne Vermerk.
3. ADR 0014 Teil 1: erst den fehlenden Eintrag nachtragen, direkt nach `ship-entwurf`:
   `**oder** `scripts/nummern.py` (ergänzt 2026-09-14 mit ADR [`0108`](./0108-nummer-folgt-dem-rang-des-arbeitsstands.md), in dieser Tabelle nachgetragen 2026-09-27 mit Spec [`0504`](../features/0504-security-trigger-operationskatalog-sicherheitskonzept.md): <Begründung wörtlich aus `review/SKILL.md`>)`;
   danach die zwei neuen Einträge, Klammer beginnt mit
   `ergänzt 2026-09-27 mit Spec [`0504`](../features/0504-security-trigger-operationskatalog-sicherheitskonzept.md): `.

**Protokoll:** `review/SKILL.md` Schritt 5 — „gelaufen" wird zu „gelaufen (welcher
Trigger-Tabelleneintrag zutraf)", spiegelbildlich zu „geskippt (…)". „Trigger unklar, deshalb
ausgeführt" bleibt eine eigene Angabe.

**Testkonzept** (`specs/architecture/0002-testkonzept.md`, Sektion „Agenten-Steuerungslogik selbst"):

- Punkt 2, Pflicht-Grenzfall „nur Doku/Spec": `review-security` skippt, **außer** der Diff enthält
  `specs/architecture/0003-securitykonzept.md`.
- Punkt 2, neuer Pflicht-Grenzfall „Prozesstext mit und ohne eigenen Security-Eintrag": eine Datei
  unter einem Einzelauslöser außerhalb von `backend/`/`frontend/` (z. B.
  `.claude/skills/github-access/SKILL.md`) → `review-security` läuft und das Protokoll nennt den
  Eintrag; eine Datei unter `.claude/skills/**` ohne eigenen Eintrag (derzeit
  `.claude/skills/refinement/SKILL.md`) → `review-security` skippt. Wird ein weiterer Einzelauslöser
  aufgenommen, genügen Positivprobe für ihn plus diese Negativprobe. Wird die Grundsatzfrage zugunsten
  von `.claude/**` entschieden, entfällt der Negativfall.
- Punkt 3, Protokollform: „gelaufen (welcher Trigger-Tabelleneintrag zutraf) / geskippt (welcher
  Trigger-Tabelleneintrag nicht zutraf)"; eine fehlende Trigger-Begründung ist in beiden Richtungen
  eine Abweichung.

Keine Änderung an `docs/ai-workflow.md` (Trigger dort nur beispielhaft), Diagrammen,
`review-security`/`review-tests` oder `scripts/tests/`.

## UI/UX

nicht relevant — keine sichtbare Oberfläche; die Änderung betrifft ausschließlich Texte des
Entwicklungsablaufs.

## Security

**Sicherheitsrelevant, schmal.** Kein Anwendungscode, kein Endpunkt, kein Secret, keine
Abhängigkeit. Asset: Integrität des KI-gesteuerten Entwicklungsablaufs. Die Story bindet eine
bestehende Kontrolle an die zwei Texte, die die Härtung des GitHub-Zugriffs bzw. den Prüfmaßstab der
Sicherheitsperspektive festlegen; nichts wird schwächer.

**Grenzen, die bestehen bleiben:**

- Der Konzept-Auslöser greift nur, wo eine Perspektivenrunde stattfindet. `specs/**` liegt in der
  Zulassungsmenge von `ship-entwurf`; eine Konzeptänderung erreicht `main` dort weiterhin ohne sie.
  Der Katalog nicht, weil `ship-entwurf` `.claude/**` ausschließt.
- Eine reine Umbenennung trifft keinen Pfad-Trigger: `git diff --name-only` führt nur den neuen Pfad.
  Die Behebung (`--no-renames`) änderte die Perspektivenwahl bei Umbenennungs-PRs und liegt außerhalb
  dieser Spec.
- Eine Änderung an der Trigger-Tabelle selbst löst `review-security` weiterhin nicht aus; das gehört
  zur offenen Grundsatzfrage.

**Sicherheitskonzept — Wortlaut der Vermerke** (am Ende des jeweiligen Eintrags anhängen):

- Punkt 11 („Trigger-Blindfleck, dritter dokumentierter Fall"): „**Für den Operationskatalog
  geschlossen** (Spec [`0504`](../features/0504-security-trigger-operationskatalog-sicherheitskonzept.md)):
  `.claude/skills/github-access/**` ist Security-Trigger. Für die übrigen Prozess- und Werkzeugtexte
  gilt der Befund fort (Bekannte Lücken)."
- „Dritter Fall desselben Pfadlisten-blinden-Flecks" (ADR 0085/Spec 0259): „**Für den
  Operationskatalog und dieses Dokument geschlossen** (Spec [`0504`](../features/0504-security-trigger-operationskatalog-sicherheitskonzept.md)):
  `.claude/skills/github-access/**` und `specs/architecture/0003-securitykonzept.md` sind
  Security-Trigger. Beide greifen nur, wo eine Perspektivenrunde stattfindet; auf dem
  `ship-entwurf`-Pfad erreicht eine Änderung an diesem Dokument `main` weiterhin ohne sie. **Weiterhin
  offen** ist die Grundsatzfrage an Daniel, ob Prozess- und Werkzeugtexte insgesamt (`.claude/**`,
  `scripts/**`) einen Sicherheitsauslöser bekommen; bis dahin trifft ein Diff, der dort nur andere
  Texte ändert, keinen Trigger — auch nicht die Trigger-Tabelle `.claude/skills/review/SKILL.md`
  selbst."
- „Auch `.claude/**` löst den `review-security`-Trigger nicht aus" (Spec 0288): „**Für diesen Fall
  geschlossen** (Spec [`0504`](../features/0504-security-trigger-operationskatalog-sicherheitskonzept.md)): Der Diff enthielt den Operationskatalog, und
  `.claude/skills/github-access/**` ist Security-Trigger. Ein Diff, der nur
  `.claude/skills/refinement/SKILL.md` ändert, trifft weiterhin keinen Trigger; die offene Frage
  bleibt."
- Neuer Eintrag unter „Bekannte Lücken": „**Eine reine Umbenennung trifft keinen Pfad-Trigger der
  Review-Tabelle** (Spec 0504, gemessen): `git diff --name-only origin/main...HEAD` (Schritt 2 von
  `.claude/skills/review/SKILL.md`) führt eine umbenannte Datei nur unter ihrem neuen Pfad. Wer eine
  als Trigger eingetragene Datei verschiebt, bekommt dafür keine Sicherheitsperspektive, und der
  Eintrag zeigt danach ins Leere, ohne dass etwas rot wird. Behebung offen: `--no-renames` in
  Schritt 2 listete beide Pfade."
- Unverändert bleiben die Einträge zu `scripts/**`, `e2e/**`, Spec 0338, dem `ship-entwurf`-Pfad und
  das Restrisiko „getriggert statt unbedingt". Kopfzeile „Letzte Aktualisierung" nachziehen.

**Muss-Kriterien:**

- **S1:** Pfade exakt wie oben an allen drei Stellen — kein breiteres, kein engeres Muster.
- **S2:** Nur hinzufügen; kein bestehender Eintrag wird gekürzt oder umformuliert. Sicherheitsnetz
  „im Zweifel läuft die Perspektive" und die Muss-Fix-Regel bleiben wortgleich.
- **S3:** „gelaufen (…)", „geskippt (…)" und „Trigger unklar, deshalb ausgeführt" bleiben
  unterscheidbare Angaben.
- **S4:** Kein Schließungsvermerk im Konzept ohne die Einschränkung auf die Perspektivenrunde und die
  ausdrücklich offene Grundsatzfrage (beides steht im Vermerk zu ADR 0085/Spec 0259).
- **S5:** Probelauf-Branches nur lokal, nie gepusht, danach gelöscht; Änderung je Branch inhaltsleer;
  Diff-Basis steht im Protokoll.
- **S6:** Der Umsetzungs-PR selbst wird sicherheitlich reviewt (sein Diff enthält das Konzept).

## Teststrategie

Kein Anwendungscode — kein neuer Test unter `scripts/tests/`, kein CI-Gate. Die bestehende Suite läuft
einmal über den Stand (u. a. `test_verweisnummern_in_markdown.py` für die neuen Verweise).

| AK | Prüfform |
|---|---|
| 1, 2, 3, 8 | Trockenlauf (Testkonzept Punkt 2), Szenarien unten |
| 2 zusätzlich | Review dieses PRs: `review-security` muss mit dem Konzept-Eintrag laufen |
| 4 | `git diff --word-diff origin/main...HEAD` über die drei Stellen |
| 5, 6, 7 | statischer Abgleich (Testkonzept Punkt 1) bzw. Dokumentdurchsicht |

**Trockenlauf:** je Szenario ein lokaler Branch von der Spitze des Feature-Branches mit einem Commit
an genau einer Datei; Vorbedingung `git diff --name-only <feature-branch>...HEAD` liefert genau diese
Datei. Der `review`-Skill wird je Szenario frisch und ad hoc angewendet; der Aufruf nennt nur Branch
und Diff-Basis, kein erwartetes Ergebnis. Bewertet wird die Zeile `review-security`; „Trigger unklar,
deshalb ausgeführt" gilt als Fehlschlag.

| # | geänderte Datei | erwartet `review-security` |
|---|---|---|
| 1 | `.claude/skills/github-access/SKILL.md` | gelaufen, nennt `.claude/skills/github-access/**` |
| 2 | `specs/architecture/0003-securitykonzept.md` | gelaufen, nennt `specs/architecture/0003-securitykonzept.md` |
| 3 | `.claude/skills/refinement/SKILL.md` | geskippt |
| 4 | `specs/architecture/0002-testkonzept.md` | geskippt (Enge des Konzept-Eintrags) |

**Ergebnis des Probelaufs (2026-09-27):** vier lokale Branches `probe/0504-szenario-1` … `-4`, je von
der Spitze des Feature-Branches mit einem Commit, der an genau eine Datei eine Leerzeile anhängt; nie
gepusht, danach gelöscht. Je Szenario hat ein frischer Lauf ohne Kenntnis des erwarteten Ergebnisses
`review` Schritt 1–3 ad hoc angewendet (ohne Feature-Spec), Diff-Basis der Feature-Branch statt
`origin/main`. Schritt 4 (Aufruf der Perspektiven) entfiel; bewertet wird die Auswahl.

|#|Diff laut `--name-only`|erwartet|Protokollzeile `review-security`|Ergebnis|
|---|---|---|---|---|
|1|`.claude/skills/github-access/SKILL.md`|gelaufen|gelaufen (Eintrag „**oder** eine Datei unter `.claude/skills/github-access/**`")|✓|
|2|`specs/architecture/0003-securitykonzept.md`|gelaufen|gelaufen (Eintrag „`specs/architecture/0003-securitykonzept.md`")|✓|
|3|`.claude/skills/refinement/SKILL.md`|geskippt|geskippt (kein Eintrag trifft zu; „das breitere `.claude/skills/**` bleibt außen vor")|✓|
|4|`specs/architecture/0002-testkonzept.md`|geskippt|geskippt (kein Eintrag trifft zu; „das breitere `specs/architecture/**` bleibt außen vor")|✓|

In keinem Szenario stand „Trigger unklar, deshalb ausgeführt". Übrige Perspektiven in allen vier:
`review-requirements` gelaufen (rein diff-basiert), `review-tests`, `review-architecture`, `review-ux`
geskippt.

## Entscheidungen

- Alle drei fachlichen Konsultationen sind gelaufen (`architect`, `test-engineer`,
  `security-engineer`).
- `ux-ui-designer` nicht konsultiert (Schritt 2): keine sichtbare Oberfläche; der Diff betrifft
  ausschließlich Skill-, ADR- und Konzepttexte.
- Keine neue ADR; Vermerk „ergänzt … mit Spec 0504" in den ADRs wie bei den bisherigen Nachträgen.
- Szenario 4 prüft zusätzlich zur Story die Enge des Konzept-Eintrags.
- Die Negativprobe wird dauerhafter Pflicht-Grenzfall im Testkonzept.
- Die Umbenennungslücke wird im Konzept vermerkt, nicht behoben.

## Offene Fragen

- keine

## Out of Scope

- Die Grundsatzfrage, ob Prozess- und Werkzeugtexte insgesamt (`.claude/**`, `scripts/**`) einen
  Sicherheitsauslöser bekommen.
- Die Behebung der Umbenennungslücke (`--no-renames` in `review/SKILL.md` Schritt 2).
- Dass `review-tests` bei reinen Markdown-Diffs nicht läuft und den Tabellen-Abgleich deshalb dort
  nicht trägt.
