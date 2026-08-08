# 0026 - Roadmap-Kompaktübersicht und README-Verlinkung

**Status:** Accepted
**Erstellt:** 2026-08-08
**Bezug:** Inbox-Notiz `specs/inbox/0012-roadmap-kompaktuebersicht-und-readme-link.md` (Daniel selbst, interaktive Session; nach Aufnahme in diese Spec gelöscht), Idea-Sharpening-Gespräch mit Daniel am 2026-08-08

## Ziel

`specs/roadmap.md` beginnt direkt mit dem ausführlichen Abschnitt "Priorisierung" — langen Fließtext-Einträgen mit viel historischem Detail pro Spec. Die vorhandene kompakte Tabelle "Status auf einen Blick" (Spec-Nummer/Titel/Status) steht erst ganz am Dateiende, nach all diesen Fließtext-Absätzen. Wer sich nur schnell einen Überblick verschaffen will, muss daran vorbeiscrollen. Zusätzlich verlinkt das Root-`README.md` die Roadmap bisher nirgends — nur `specs/README.md` erwähnt sie. Diese Spec verschiebt die bestehende Tabelle an den Dateianfang, ergänzt eine neue, sehr knappe D2-Grafik direkt darüber, und verlinkt die Roadmap zusätzlich aus der README.

## User Story

Als Daniel möchte ich beim Öffnen von `specs/roadmap.md` sofort eine kompakte visuelle Übersicht über alle Roadmap-Einträge sehen, statt mich erst durch die ausführlichen Fließtext-Einträge scrollen zu müssen, damit ich mir schnell einen Überblick über Status und Priorität aller Features verschaffen kann — auch von der README aus.

## Akzeptanzkriterien

- [x] Am Anfang von `specs/roadmap.md` (vor dem Abschnitt "Priorisierung") steht eine neu eingebettete D2-Grafik (`specs/diagrams/roadmap-overview.d2`/`.svg`): eine Kanban-artige Kurzübersicht mit den vier Spalten Jetzt/Als Nächstes/Später/Ideenspeicher (Reihenfolge wie im Text). Bereits implementierte Specs werden pro Spalte zu einer einzigen Zähler-Karte zusammengefasst ("N umgesetzt"), nur nicht-implementierte Specs bekommen eine eigene Karte (Spec-Nummer + Kurztitel + Status).
- [x] Direkt unter der Grafik folgt die bestehende Tabelle "Status auf einen Blick", inhaltlich unverändert — nur von ihrer bisherigen Position am Dateiende an den Anfang verschoben.
- [x] Spec 0001 (Sonderstatus "Implemented (Backend) — Frontend-Oberfläche und API-Authentifizierung noch offen") ist in der neuen Grafik bewusst **nicht** enthalten, da sie in keiner der vier Prioritäts-Spalten im Text von `specs/roadmap.md` steht — die Grafik bildet nur ab, was tatsächlich einer Spalte zugeordnet ist (siehe Entscheidungen).
- [x] Die Specs 0022/0023 (beide Implemented, in der Tabelle aber ohne eigenen Fließtext-Bullet unter "Jetzt") werden für die Zähler-Karte der Spalte "Jetzt" mitgezählt (18 statt 16) — ohne begleitende Ergänzung fehlender Fließtext-Bullets, das bleibt außerhalb dieses Scopes (siehe Entscheidungen).
- [x] `README.md` verlinkt in der bestehenden "Projektstruktur"-Tabelle zusätzlich auf `specs/roadmap.md`.
- [x] `scripts/render-diagrams.sh` erzeugt `roadmap-overview.svg` mit, ohne Anpassung am Skript selbst nötig zu sein (iteriert bereits generisch über alle `specs/diagrams/*.d2`).
- [x] Die `.d2`-Quelldatei enthält einen kurzen Kopfkommentar, der festhält, dass die Grafik vom `requirements-engineer` mitgepflegt wird, sobald er ohnehin `roadmap.md` ändert (neue Spec, Status-/Prioritätswechsel) — Grafik und Tabelle im selben Schritt aktualisieren, damit beide nicht auseinanderlaufen.

## Datenmodell-Bezug

Nicht betroffen — reine Doku-/Diagramm-Änderung, kein Anwendungscode, kein Datenmodell.

## Architektur / Umsetzung

**Bezug:** [`decisions/0013-diagram-tooling-d2.md`](../decisions/0013-diagram-tooling-d2.md) (architect-Konsultation, 2026-08-08). Keine neue ADR nötig — reine Anwendung des bereits akzeptierten D2-Standards, keine neue Technologie/Abhängigkeit.

**Struktur der Grafik:** 4 Spalten (Jetzt/Als Nächstes/Später/Ideenspeicher), analog zu den Fließtext-Abschnitten in `specs/roadmap.md`. Pro Spalte eine Zähler-Karte für bereits implementierte Specs ("N umgesetzt") plus eine Einzelkarte (Spec-Nummer + Kurztitel + Status) für jede dort noch nicht implementierte Spec. Bewusst **keine** Karte pro Spec insgesamt (aktuell 26 Specs) — das würde das Diagramm unübersichtlich machen und leistet die Tabelle direkt darunter bereits. Aktueller Stand (2026-08-08): Jetzt = 18 umgesetzt, 0 offene Karten; Als Nächstes = 1 umgesetzt (0020) + 1 Karte (0024, Accepted); Später = 0 umgesetzt + 1 Karte (0004, Proposed); Ideenspeicher = 2 umgesetzt (0018, 0019) + 2 Karten (0025 Accepted, 0026 dieses Feature selbst).

**Umgesetzt (bereits fertig, lokal mit `d2 v0.7.1` gerendert):**
- `specs/diagrams/roadmap-overview.d2` — 4 Spalten über `grid-columns: 4` in einem umschließenden Container erzwungen (ohne `grid-columns` ordnet D2s Layout-Engine unverbundene Container vertikal an, nicht horizontal wie für ein Kanban-Board gewünscht).
- `specs/diagrams/roadmap-overview.svg` — gerendert über `scripts/render-diagrams.sh`, keine Anpassung am Skript nötig (iteriert bereits generisch über alle `*.d2`-Dateien im Verzeichnis).

**Betroffene Dateien:**
- `specs/roadmap.md` — Tabelle "Status auf einen Blick" vom Dateiende an den Anfang verschieben, neue Grafik per Markdown-Bild-Referenz direkt darüber einbinden.
- `README.md` — neue Zeile bzw. Ergänzung der bestehenden `specs/`-Zeile in der "Projektstruktur"-Tabelle mit Link auf `specs/roadmap.md`.

**Synchronhaltung:** kein Eintrag in `specs/README.md` nötig (dort steht Spec-Lifecycle, nicht Roadmap-Pflege). Stattdessen ein Kopfkommentar direkt in `roadmap-overview.d2` (näher am Bearbeitungsort): Hinweis, dass die Grafik vom `requirements-engineer` mitaktualisiert wird, wenn er ohnehin `roadmap.md` ändert.

## UI/UX

Nicht relevant. Reine Entwickler-/Projektdokumentation (`specs/roadmap.md`, `README.md`), keine App-Oberfläche für Daniel/seine Frau als Endnutzer betroffen (analog zu Spec 0018/0019).

## Security

Nicht relevant. Reine lokale Doku-/Diagrammpflege: kein Anwendungscode, kein Netzwerkzugriff zur Laufzeit, keine neue Abhängigkeit über das bereits akzeptierte D2-Tooling hinaus, keine Eingabe von außen. Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig (analog zu Spec 0018).

## Teststrategie

Reine Doku-Änderung, kein Anwendungscode — analog zu Spec 0018 kein automatisiertes Testframework, sondern benannte manuelle Smoke-Test-Szenarien vor Merge (test-engineer-Konsultation, 2026-08-08):

1. `scripts/render-diagrams.sh` erzeugt für `specs/diagrams/roadmap-overview.d2` ein valides SVG (Exit 0) und verarbeitet weiterhin alle übrigen bestehenden `.d2`-Dateien fehlerfrei (Regressionscheck, kein Bruch durch die zusätzliche Datei) — bereits lokal verifiziert.
2. Visuelle Prüfung des gerenderten SVG: 4 Spalten sichtbar, je Spalte eine Zähler-Karte sowie exakt die erwarteten Einzelkarten für nicht-implementierte Specs — Abgleich gegen die Tabelle "Status auf einen Blick" als Quelle der Wahrheit (keine Spec doppelt/fehlend, Zählwerte stimmen).
3. Tabelleninhalt nach dem Verschieben vom Dateiende an den Anfang inhaltlich unverändert (`git diff` zeigt nur Positionsverschiebung, keine Zell-/Zeilenänderung).
4. README-Link auf `specs/roadmap.md` in der Projektstruktur-Tabelle: manueller Klicktest in lokaler Vorschau bzw. GitHub-PR-Preview, Linkziel und -text korrekt.

`specs/architecture/0002-testkonzept.md` erfordert keine Ergänzung: die durch Spec 0018 etablierte Sektion "Reine Bash-Wrapper-Skripte ohne Testframework (`scripts/*.sh`)" deckt den unveränderten `render-diagrams.sh`-Wrapper bereits vollständig ab (verifiziert, test-engineer-Konsultation).

## Entscheidungen (2026-08-08, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Grafik zusätzlich zur verschobenen Tabelle, nicht statt ihr:** Daniel wollte explizit beides — die bestehende Tabelle nach oben verschieben *und* eine Grafik darüber, nicht nur eine der beiden Maßnahmen.
- **Pflegeaufwand der Grafik bewusst akzeptiert:** Devil's-Advocate-Einwand (die Grafik braucht bei praktisch jeder künftigen Roadmap-Änderung eine manuelle Aktualisierung des `.d2`-Quellcodes, sonst läuft sie von der Tabelle auseinander) wurde Daniel explizit vorgelegt — er hat sich bewusst für Grafik + Tabelle entschieden, da der `requirements-engineer` die Roadmap ohnehin bei jeder Änderung anfasst und die Pflege damit kein separater Zusatzschritt ist.
- **Zähler statt Karte pro Spec:** Empfehlung des `architect`-Agenten, von Daniel implizit durch Freigabe der Architektur-Vorlage bestätigt — bei 26 Specs wäre eine Karte pro Spec unübersichtlich, eine Zähler-Karte pro Spalte für bereits Implementiertes plus Einzelkarten nur für offene Arbeit hält den Fokus auf dem, was noch nicht erledigt ist.
- **Spec 0001 bewusst ausgelassen:** beim Aufbau der Grafik aufgefallen, dass Spec 0001 einen Sonderstatus (teilweise implementiert) hat und in keiner der vier Text-Prioritäts-Spalten von `specs/roadmap.md` steht. Daniel hat sich dagegen entschieden, sie nachträglich einer Spalte zuzuordnen (das wäre eine inhaltliche Priorisierungs-Entscheidung, nicht Teil dieser rein layoutbezogenen Spec) — sie bleibt nur in der Tabelle sichtbar, nicht in der Grafik.
- **0022/0023 nur für die Grafik mitgezählt, keine begleitende Textkorrektur:** ebenfalls beim Aufbau der Grafik aufgefallen — beide Specs sind laut Tabelle Implemented, tauchen aber in keinem Fließtext-Bullet unter "Jetzt" auf (Tabelle und Prosa sind an dieser Stelle bereits auseinandergelaufen). Daniel hat sich für die minimal-invasive Variante entschieden: für die neue Zähler-Karte mitzählen, aber keine zusätzlichen Fließtext-Bullets nachtragen — das bliebe ein eigener, größerer Aufräumschritt außerhalb des hier angefragten Scopes.

## Offene Fragen

Keine.

## Out of Scope

Nachträgliches Angleichen der Fließtext-Bullets unter "Jetzt" für die Specs 0022/0023 (Tabelle/Prosa-Drift bleibt bestehen, nur für die neue Grafik minimal-invasiv mitgezählt); nachträgliche Zuordnung von Spec 0001 zu einer der vier Prioritäts-Spalten; ein automatisiertes CI-Gate, das Diagramm-Quelle und Tabelleninhalt auf Drift prüft (analog zur bereits in Spec 0018 getroffenen Entscheidung, das nicht einzuführen).
