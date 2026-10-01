# 0550 - Zurück nach dem Schließen der Großansicht verlässlich und stabil geprüft

**Status:** Accepted
**Erstellt:** 2026-10-01
**Bezug:** [Issue #550](https://github.com/TheRealKoller/photosort/issues/550)

## Ziel

Die automatische Prüfung vor jedem Merge soll nur dann rot werden, wenn etwas tatsächlich kaputt
ist. Zwei Prüfungen der Großansicht in der Kuratierung scheitern sporadisch, beide an derselben
Zusage: Nach dem Öffnen und Schließen der Großansicht führt ein einzelnes Zurück nicht auf die
Seite vor der Kuratierung.

- „verlässt die Kuratierung auch bei zweimal Escape nicht“
- „hält über jeden Schließweg Platz, URL und Fokus“

Eine Wiederholung als Ausweg schließt die geltende Verlässlichkeitsregel aus. Die Story klärt die
Ursache und behebt sie, auch wenn sie in der Anwendung liegt.

## User Story

Als Person, die über das Mergen entscheidet, möchte ich, dass die Prüfungen der Großansicht nur
dann scheitern, wenn sich die Großansicht tatsächlich falsch verhält, damit ein roter Lauf ein
verlässliches Signal ist und ich keinen Lauf auf Verdacht neu starten muss.

Als kuratierende Person möchte ich nach dem Schließen der Großansicht mit genau einem Zurück dort
landen, wo ich vor dem Öffnen gelandet wäre, damit ich die Kuratierung ohne Umweg verlassen kann.

## Akzeptanzkriterien

Begriffe: **Schließen-Test** = `hält über jeden Schließweg Platz, URL und Fokus`, **Escape-Test** =
`verlässt die Kuratierung auch bei zweimal Escape nicht` (beide in
`e2e/tests/kuratierung-grossansicht.spec.ts`). **Prüfbefehl** =
`npx playwright test tests/kuratierung-grossansicht.spec.ts -g "zweimal Escape|jeden Schließweg"`,
in beiden Viewport-Projekten. **Verzögerungs-Hunk** = temporäre Änderung in `oeffneEntwurf`:
`page.route` auf `**/api/projects/<id>` verzögert nur die **erste** Antwort und reicht alle weiteren
unverändert durch; feste Werte, wörtlich im PR zitiert, nie committet.

- [ ] **AK1 – Ursache benannt und belegt.** Ursache ist die Prüfung, nicht die Anwendung (siehe `## Architektur / Umsetzung`). *Nachweis:* (a) Alle fünf roten CI-Läufe zeigen `Expected …/projects/3/pipeline`, `Received …/projects/3/pipeline/kuratierung`, nie `/album` (erhoben beim Schreiben dieser Spec, Runs 36235752471, 36303200921, 36310322128, 36310649944, 36341574163). (b) **Zwischenlauf R1:** Spec mit Verlaufspositions-Prüfung (AK3) und neuen Meldungen (AK8), Einstieg noch an der alten Stelle, plus Hunk, Prüfbefehl `--repeat-each=10`: mindestens ein roter Lauf; **jeder** Fehlschlag steht in einer Abschlusszeile `…: genau ein Zurück führt zur Projektseite` mit Received `…/pipeline/kuratierung`; keine Prüfung der Verlaufsposition ist rot.
- [ ] **AK2 – vorher reproduziert, nachher ausgeblieben.** Der Verzögerungs-Hunk ist ein zulässiger Reproduktionsweg, sofern er vorher und nachher wortgleich ist, nicht committet wird und die Meldung darunter der aus CI entspricht. *Nachweis:* **R0** (unveränderter Spec + Hunk, Prüfbefehl `--repeat-each=10`, 40 Läufe) zeigt mindestens einen Fehlschlag mit `Expected …/pipeline`, `Received …/pipeline/kuratierung`. **R2** (korrigierter Spec + derselbe Hunk, derselbe Befehl) zeigt 40/40 grün in beiden Projekten. **R3** (ohne Hunk, `--repeat-each=30`) zeigt 120/120 grün. Der PR nennt je Lauf rot/gesamt pro Projekt und zitiert den Hunk. Im Merge-Stand enthält die Testdatei kein `page.route`.
- [ ] **AK3 – genau ein Zurück, in jeder Ansicht.** *E2E (Album-Entwurf):* `oeffneEntwurf` hält `einstieg` erst fest, wenn die URL auf `/projects/{id}/pipeline/[^/?#]+$` passt; danach wird `start = navigation.currentEntry.index` gemerkt. Die Position wird **sofort** nach `toBeHidden()` gelesen (kein `expect.poll`, vor der Fokusprüfung) und muss `start` sein – in allen 8 Fällen des Schließen-Tests (2 Öffnungsarten × Schließen/Escape/Klick neben das Bild/Browser-Zurück) und im Escape-Test nach (a) synthetisch und (b) nativ. „Zurück unmittelbar nach dem Schließen“ heißt: nachdem die Großansicht verschwunden ist. Beide Tests enden mit `goBack()` und `toHaveURL(einstieg)`. *jsdom, jede Ansicht:* Die Verlaufssonden in `AlbumDraftPage.test.tsx` und `AlbumSelectionPage.test.tsx` bleiben unverändert. **Neu** in `ProjectPersonsPage.test.tsx`, bestehender Fall `öffnet aus der zweiten Gruppe …` erweitert: Stub-Route vor der Seite (`initialEntries={['/stub', '/projects/3/persons']}`, `initialIndex={1}`, Probe mit `useLocation`/`useNavigate`); nach dem Schließen ist `location` = `{ pathname: '/projects/3/persons', state: null }`, ein `navigate(-1)` in `act` führt auf `/stub`. Zweimal Schließen vor `popstate` sichert einmalig der Hook-Test `goes back only once for two closes before the navigation settles`.
- [ ] **AK4 – übrige Zusagen bleiben.** Unverändert stehen und grün: scrollY offen/danach, `URL unverändert` und `Fokus auf dem Auslöser` je Fall; der Reload-Test; in jsdom die Aufrufzahl von `draftCalls()`/`getAlbumSelection` (kein Neuladen der Liste). *Nachweis:* Im Diff der Testdateien fehlt keine dieser Zeilen und keine ist abgeschwächt; R2/R3 und `vitest` grün.
- [ ] **AK5 – nicht abgeschwächt.** *Nachweis im Diff von `kuratierung-grossansicht.spec.ts`:* Kein `test(` entfernt; `oeffnungen` (2) und `wege` (4) vollständig; (a) und (b) bleiben, ebenso das abschließende `goBack()` mit exakt vergleichendem `toHaveURL(einstieg)`. Kein `test.skip`/`fixme`/`slow`; `MOBILE_ONLY`/`DESKTOP_ONLY` unberührt (`toolchain.spec.ts` grün). Das Einstiegsmuster wird strenger (Ende der Kette statt Präfix).
- [ ] **AK6 – keine Wiederholung, keine Zeitgrenzen, keine festen Wartezeiten.** *Nachweis im Diff unter `e2e/`:* kein neues `waitForTimeout`, `timeout:`, `retries`, `page.route` oder `setTimeout`; `playwright.config.ts` unverändert (`retries: 0`). Die Verlaufsposition wird sofort gelesen, nicht gepollt – das zeitversetzte `history.back()` bleibt sichtbar.
- [ ] **AK7 – echter Fehler wird erkannt (Gegenprobe R4).** In `frontend/src/hooks/useCurationLightbox.ts` wird in `close()` die Bedingung `ownEntryKeysRef.current.has(location.key)` temporär durch `false` ersetzt (immer `replace`-Zweig, der geöffnete Eintrag bleibt als überzähliger Schritt stehen). Danach `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d frontend` und der Prüfbefehl ohne Hunk. *Erwartet:* alle 4 Läufe (2 Tests × 2 Projekte) rot mit `Schließwege – Mausklick, Schließen: Verlaufsposition wie vor dem Öffnen` bzw. `Zweimal Escape – synthetisch: Verlaufsposition wie vor dem Öffnen` (erwartet `start`, erhalten `start+1`). Unter derselben Mutation sind auch die Großansicht-Fälle in `useCurationLightbox.test.tsx`, `AlbumDraftPage.test.tsx`, `AlbumSelectionPage.test.tsx` und der neue Fall in `ProjectPersonsPage.test.tsx` rot. Mutation zurücknehmen, neu bauen; Ausgabe im PR, nichts davon committet.
- [ ] **AK8 – Fehlermeldung nennt Prüfung und Schließweg.** Format: `Schließwege – ${art}, ${weg}: Verlaufsposition wie vor dem Öffnen` bzw. `Zweimal Escape – synthetisch|nativ: Verlaufsposition wie vor dem Öffnen`. Abschlusszeilen: `Schließwege: genau ein Zurück führt zur Projektseite` und `Zweimal Escape: genau ein Zurück führt zur Projektseite`. Keine Meldungszeichenkette kommt in beiden Tests vor. *Nachweis:* R4 zeigt die Meldung je Schließweg, R1 die Abschlussmeldung.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

**Ursache: die Prüfung, nicht die Anwendung.** `oeffneEntwurf`
(`e2e/tests/kuratierung-grossansicht.spec.ts:64-66`) hält `einstieg` fest, sobald die URL auf
`/projects/{id}/pipeline` passt. `/projects/{id}` wird aber zweimal per `replace` weitergeleitet:
erst auf `/pipeline` (`frontend/src/App.tsx:41-44`), dann nach dem Laden des Projekts auf
`/pipeline/{schritt}` (`frontend/src/pages/pipeline/ProjectPipelineLayout.tsx:72-74`; beim
Demo-Projekt `kuratierung`). Antwortet die Projektabfrage langsam, ist `einstieg` die Zwischenstufe
`/pipeline`, während der Verlaufseintrag vor dem Album auf `/pipeline/kuratierung` endet. Das exakte
`toHaveURL(einstieg)` scheitert dann mit genau der in CI beobachteten Meldung. Der Verlauf der
Großansicht selbst stimmt.

**Anwendung bleibt unverändert** (`useCurationLightbox.ts`, `CurationLightbox.tsx`,
`useModalDialog.ts`, die drei Seiten). In Chromium gemessen: Sobald der Dialog verschwindet, steht
der Verlauf bereits auf dem Eintrag vor dem Öffnen; ein zweites Escape geht nicht zweimal zurück
(Riegel in `close()`, `keydown.preventDefault()` unterdrückt die native Schließanfrage); alle drei
Ansichten nutzen dasselbe `lightbox.close`. Zwischen Schließaktion und `popstate` liegt ein Fenster
von wenigen Millisekunden, in dem die Großansicht noch sichtbar ist; es gehört zu `history.back()`
und bleibt.

**Änderungen in `e2e/tests/kuratierung-grossansicht.spec.ts`:**

1. **Einstieg am Ende der Weiterleitungskette.** `oeffneEntwurf` wartet mit
   `await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/pipeline/[^/?#]+$`))` und liest
   erst dann `einstieg = page.url()`. Kein fest eingetragener Schrittname. Der Doku-Block der
   Funktion nennt die Zusicherung in einem Satz: Das Ziel des Zurück ist die URL nach der letzten
   Weiterleitung; eine Zwischenstufe macht die Zusage zufällig rot.
2. **Verlaufsposition je Schließweg.** Nach `oeffneEntwurf`:
   `start = await page.evaluate(() => navigation.currentEntry?.index)` (Navigation API, in `lib.dom`
   typisiert). Nach jedem Schließweg sofort nach `toBeHidden()` lesen und mit
   `expect(index, '<Prüfung> – <Fall>: Verlaufsposition wie vor dem Öffnen').toBe(start)` prüfen –
   **kein `expect.poll`**: Die Großansicht verschwindet nur durch einen Eintragswechsel, und der
   Index wechselt vor `popstate`; verschwunden ⇒ Index endgültig.
3. **Eindeutige Meldungen** nach AK8. Das abschließende `goBack()` mit `toHaveURL(einstieg)` bleibt.

**Weitere Testdatei:** `frontend/src/pages/ProjectPersonsPage.test.tsx` – Verlaufssonde nach AK3.

**Reihenfolge der Nachweise:** R0 (rot vorher) → Korrekturen 2+3 → R1 → Korrektur 1 → R2, R3 →
R4 (Gegenprobe). Hunk und Mutation werden nie committet.

Keine ADR, keine Änderung an `docs/architecture.md`: Weder Muster noch Verhalten der Anwendung
ändern sich.

## Teststrategie

| Ebene | trägt | Gegenstand |
|---|---|---|
| E2E `kuratierung-grossansicht.spec.ts`, beide Projekte | AK3–AK6, AK8 | echtes asynchrones `popstate`, Weiterleitungskette beim Einstieg, Verlaufsposition je Schließweg |
| jsdom Hook `useCurationLightbox.test.tsx` (unverändert) | AK3 | Riegel: zweimal `close` vor `popstate` geht einmal zurück; nach Reload wird ersetzt |
| jsdom Seiten (Draft/Selection unverändert, Persons + Verlaufssonde) | AK3 „jede Ansicht“, AK4 | Verdrahtung je Ansicht: ein Zurück landet auf der Stub-Route |
| Nachweisläufe R0–R4, nicht committet | AK1, AK2, AK7, AK8 | siehe Akzeptanzkriterien |

**Edge Cases:** Einstieg auf der Zwischenstufe bei langsamer Projektabfrage (R0/R2); End-URL als
Form, nicht als Präfix – bekäme der Standardschritt Query oder Hash, scheitert `oeffneEntwurf` laut;
zweimal Escape synthetisch und nativ mit Position nach jedem; Browser-Zurück als Schließweg ruft
`close()` nicht auf, Position muss trotzdem `start` sein; `navigation.currentEntry.index` nur relativ
zu `start` vergleichen, nie absolut.

**Bewusst nicht:** kein E2E-Fall für Endauswahl und Personenübersicht – Hook und Lightbox sind
dieselben, den asynchronen Teil prüft E2E an einer Ansicht, die Verdrahtung jsdom je Ansicht.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) ist ergänzt: Verlaufssonde je Ansicht,
Regeln zum Einstieg nach der letzten Weiterleitung, zur Reproduktion per nicht committeter
Verzögerung und zu Meldungen mit Test und Fall; Zeile `kuratierung-grossansicht` erweitert.

## UI/UX

Nicht relevant: Die Anwendung bleibt unverändert; geändert werden ausschließlich Prüfungen. Keine
Anzeige, kein Zustand und keine Bedienung ändert sich.

## Security

Nicht relevant: keine Eingabe von außen, keine Auth-/Berechtigungs-/Secret-Stelle, kein
Datenmodell, keine veränderte Datensichtbarkeit.

## Entscheidungen

- Ursache liegt in der Prüfung; die Anwendung bleibt unverändert (architect, belegt durch Messung
  und die fünf CI-Meldungen).
- Reproduktion über einen nicht committeten Verzögerungs-Hunk, vorher und nachher wortgleich, nur
  gültig bei derselben Meldung wie in CI (test-engineer).
- Verlaufsposition sofort nach dem Verschwinden lesen statt per `expect.poll` (test-engineer,
  abweichend vom ersten Architekturvorschlag).
- Eigene Verlaufssonde für `ProjectPersonsPage` (test-engineer).
- ux-ui-designer nicht konsultiert (Schritt 2): Der in Schritt 1 festgelegte Ansatz ändert keine
  Komponente, keinen Zustand und keine Anzeige; geändert werden nur Testdateien.
- security-engineer nicht konsultiert (Schritt 3): kein Bezug zu Auth, externen Schnittstellen,
  Secrets, Eingaben von außen, Berechtigungen, Datenmodell oder Datensichtbarkeit.

## Out of Scope

Die übrigen sporadisch scheiternden Oberflächenprüfungen (Bilddetail-Bühne, Projektnavigation,
Rasterspalten); sie haben andere Ursachen.
