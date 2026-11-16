# 0635 - Bildflächen erst im gefüllten Zustand messen

**Status:** Implemented ([PR #646](https://github.com/TheRealKoller/photosort/pull/646))
**Erstellt:** 2026-11-16
**Bezug:** Issue [#635](https://github.com/TheRealKoller/photosort/issues/635)

## Ziel

Ein verpflichtender Prüflauf (E2E) ist an einem fremden Pull Request rot geworden, an demselben
Stand lokal aber grün: Die Messung der Duplikat-Stapel begann, bevor das Titelbild der vorderen
Karte geladen war. Der Lauf ist ein Pflicht-Check an `main`, und das Verlässlichkeitsregime des
Projekts erlaubt weder Wiederholen noch Quarantäne noch eine längere Zeitgrenze als Ersatz für die
Reparatur. Dasselbe Muster steht an weiteren Messstellen.

Nach dieser Änderung beginnen alle Messungen an Bildflächen erst im gefüllten Zustand, und die
Frage „sind die Bilder dieser Fläche geladen?" wird an genau einer gemeinsamen Stelle beantwortet.

## User Story

Als Entwickler an PhotoSort möchte ich, dass eine Messung an einer Bildfläche erst beginnt, wenn
deren Bilder geladen sind, und dass es dafür genau eine gemeinsame Wartehilfe gibt, damit ein rotes
Prüfergebnis immer einen echten Fehler der Anwendung bedeutet und nicht davon abhängt, wie schnell
ein Titelbild geladen ist.

## Akzeptanzkriterien

- [x] **Messung erst im gefüllten Zustand.** Jede Messung an einem Duplikat-Stapel — Überstand der
  hinteren Karten, Treffertest auf die nur von ihnen belegte Fläche, Enthaltensein von Kennzeichen
  und Dateiname — beginnt erst, wenn in jedem zu messenden Stapel das vordere Titelbild vollständig
  geladen ist (natürliche Breite größer als 0).
- [x] **Warten auf den Zielzustand, nicht auf Zeit.** Die Wartehilfe fragt den Zielzustand ab und
  enthält keine feste Wartezeit. Wiederholungsläufe bleiben ausgeschaltet.
- [x] **Ein Fehlschlag benennt den Fall.** Läuft das Warten in seine Zeitgrenze, beginnt die
  Meldung mit `<Fläche>: <Bild> nicht geladen` (am Stapel: `Duplikat-Stapel: Titelbild nicht
  geladen`). Belegt durch einen lokalen Lauf mit angehaltenen Bildanfragen (nicht committet), der
  mit genau dieser Meldung rot wird, ohne dass vorher eine Geometrie-Zusicherung fehlschlägt.
- [x] **Genau eine gemeinsame Stelle.** `e2e/lib/bilder.ts`; keine Prüfdatei führt ein eigenes
  Lade-Prädikat, eine eigene Wartegrenze oder eine eigene Wartemeldung.
- [x] **Abgedeckte Fälle unverändert:** (a) jede Fläche muss ein geladenes Bild haben, (b) eine
  Fläche ohne Bild ist zulässig und blockiert nicht, (c) ein einzelnes Bild. Für jede Fläche gilt
  dieselbe Wartegrenze der gemeinsamen Funktion (30 s), begrenzt durch das Testbudget.
- [x] **Keine Zusicherung wird abgeschwächt.** Keine Geometrie-Zusicherung entfällt, keine
  Toleranz ändert sich.
- [x] **Belegt grün, im selben Umfang.** `ausschuss-stapel` mit `--repeat-each=20` in `mobile` und
  `desktop` und der volle Prüfsatz ohne Fehlschlag; der verpflichtende E2E-Lauf ist grün.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

Neues Modul `e2e/lib/bilder.ts`, keine ADR (keine neue Technologie, keine Abhängigkeit).

- `bildstand(elements, bild)` läuft im Browser, als Referenz an `evaluateAll` übergeben, und greift
  auf keine Modulbindung zu. Je Element zählt es „ohne Bild", „ungeladen" oder „geladen"; das
  Prädikat `instanceof HTMLImageElement && complete && naturalWidth > 0` steht genau hier.
- `warteAufBilder(flaechen, { flaeche, was, bild, ohneBildZulaessig? })`: `toBeVisible` auf die
  erste Fläche (eine leere Liste ist kein „geladen"), dann `expect.poll` mit 30 s auf
  `ungeladen + (ohneBildZulaessig ? 0 : ohneBild) == 0`, Meldung `${flaeche}: ${was} nicht geladen`.
- `zaehleGeladeneBilder(flaechen, bild)`: Momentaufnahme ohne Warten, für die negative Vorbedingung
  in `grid-columns` („vor der Freigabe ist kein Bild geladen").
- Fälle: (a) `ohneBildZulaessig` weglassen; (b) `ohneBildZulaessig: true`; (c) Locator auf das
  `img`, `bild: null`.

Umgestellt: `ausschuss-stapel` (`openStacks` wartet auf das Titelbild jedes Stapels — die
Fehlerbehebung), `grid-columns` (Fotoraster, Duplikat-Raster, Fotoliste mit Fall b,
Negativzählung), `duplikat-vergleich` (Bühne, Streifen), `foto-karte-raster` (alle Kachelbilder
des Rasters, Locator auf `:scope > li img` wie bisher), `klassifizierung-pruefung`,
`kuratierung-grossansicht`, `bilddetail-buehne` (je Fall c).

## UI/UX

nicht relevant — die Änderung betrifft ausschließlich die Prüfebene `e2e/`.

## Security

nicht relevant — keine Eingabe von außen, keine Auth-, Secret- oder Datenmodell-Berührung.

## Teststrategie

- Nur E2E; Gegenstand ist die Wartebedingung der Prüfebene selbst.
- Reproduktion nach dem Verlässlichkeitsregime: lokale, nicht committete Verzögerung jeder
  Bildantwort um 3 s per `page.route`. Der alte Stand wird damit rot mit den Meldungen des
  CI-Fehlschlags (`vordere Karte mit Titelbild`, `Treffertest und Enthaltensein`), der neue grün.
- Meldungsnachweis: dieselbe Fassung mit nie freigegebenen Bildanfragen.
- „Keine eigene Fassung" im Review:
  `rg -n -U 'naturalWidth\s*>\s*0|\.complete\b|IMAGE_LOAD_TIMEOUT_MS|naturalWidth\)\)\s*\.toBeGreaterThan' e2e/tests`
  ist leer.

## Entscheidungen

- `ux-ui-designer` nicht konsultiert (Schritt 2): keine sichtbare Oberfläche berührt, nur `e2e/`.
- `security-engineer` nicht konsultiert (Schritt 3): keine Eingabe von außen, keine Auth-/Secret-/
  Berechtigungs- oder Datenmodell-Stelle, keine Datensichtbarkeit berührt.
- Die Negativzählung in `grid-columns` fällt unter „genau eine Stelle" und läuft über
  `zaehleGeladeneBilder`; sie bleibt eine Momentaufnahme ohne Poll.
- Die Einzelbild-Fälle warten jetzt 30 s statt der Playwright-Vorgabe von 5 s und prüfen zusätzlich
  `complete` — dieselbe Grenze wie die übrigen Fälle (AK 5).
- `foto-karte-raster` behält seinen Locator auf die Bilder des Rasters (`bild: null`), damit
  `toBeVisible` weiter das erste Bild prüft statt die erste Kachel.

## Out of Scope

- Ein committeter Wächter gegen eine zweite Fassung des Lade-Prädikats (ein Textmuster ließe sich
  umgehen; die Zusage trägt das Review).
- Ein Nachweis an einer absichtlich mutierten Anwendung.
