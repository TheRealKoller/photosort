# 0375 - Projektübersicht zeigt Umfang und nächsten Schritt

**Status:** Accepted
**Erstellt:** 2026-09-14
**Bezug:** [Issue #375](https://github.com/TheRealKoller/photosort/issues/375)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Stand-Zeile hat dreizehn Ausprägungen,
und ihre Tabelle ist die Zusicherung selbst — sie zu kürzen hieße, die Aussage zu entfernen. Die
Akzeptanzkriterien tragen zusätzlich je ihr Entscheidungsmerkmal, weil mehrere von ihnen nur durch
Hinsehen prüfbar sind und das dort stehen muss, statt eine Scheinprüfung zu erfinden.

## Ziel

Die Projektübersicht zeigt heute je Projekt nur Name, Ordner und Scan-Status. Wer wissen will, wie
viel in einem Projekt liegt und wo er stehengeblieben ist, muss jedes Projekt einzeln öffnen. Bei
mehreren Projekten nebeneinander ist das die eigentliche Reibung im Alltag beider Nutzer.

Diese Story bringt die drei fehlenden Angaben auf die Projektkarte: wie viele Fotos darin liegen, aus
welchem Zeitraum sie stammen, und welcher Schritt als nächster ansteht — in Worten, nicht als
Fortschrittsbalken. Sie setzt damit den Entwurf aus Spec
[`0358`](./0358-projektverwaltung-entwurf.md) im Code um; dort war die Umsetzung ausdrücklich
ausgeschlossen.

## User Story

Als Nutzer mit mehreren Projekten möchte ich auf der Projektübersicht sehen, wie viele Fotos in jedem
Projekt liegen, aus welchem Zeitraum sie stammen und welcher Schritt als nächster ansteht, damit ich
entscheiden kann, wo ich weitermache, ohne jedes Projekt einzeln zu öffnen.

## Akzeptanzkriterien

Je Kriterium steht, **woran** man feststellt, dass es erfüllt ist: `[M]` mechanisch in CI,
`[S]` Sichtprüfung. Mehrere Kriterien sind nur durch Hinsehen prüfbar — das steht ausdrücklich da.

### Die drei neuen Angaben

- [ ] **A1 — Drei zusätzliche Angaben je Karte.** Jede Projektkarte rendert neben Name und Ordnerpfad
  drei einzeln lokalisierbare Textbereiche: Fotoanzahl, Aufnahmezeitraum, Stand-Zeile. Jeder trägt
  seine Wortmarke bei sich („… Fotos", „Aufnahmen …", Stand-Zeile über
  `data-testid="project-stand-<id>"`) — es gibt keine Spaltenkopfzeile, aus der ein Wert seine
  Bedeutung bezieht, und damit keinen Text, den es nur in einer Breite gibt. `[M]`
- [ ] **A2 — Fotoanzahl.** Deutsches Zahlenformat mit Tausenderpunkt (`1284` → `1.284`), dahinter das
  Wort „Fotos". `photo_count === 0` rendert sichtbar `0 Fotos` — nicht den Strich `NOT_AVAILABLE`,
  nicht die leere Zeichenkette, nicht ein entferntes Element. `[M]`
- [ ] **A3 — Aufnahmezeitraum.** `formatTakenAtRange(earliest, latest)` mit vier entscheidbaren
  Fällen: (a) beide gesetzt, **verschiedene** Kalendertage → `formatDate(earliest) + ' – ' +
  formatDate(latest)` (Gedankenstrich U+2013, je ein Leerzeichen); (b) beide gesetzt, **derselbe**
  Kalendertag — entschieden am *formatierten* Datum, nicht am rohen Zeitstempel → das Datum
  **einmal**; (c) genau einer `null` → `NOT_AVAILABLE`; (d) beide `null` → `NOT_AVAILABLE`. Auf der
  Karte mit vorangestellter Wortmarke „Aufnahmen". `[M]`
- [ ] **A4 — Bearbeitungsstand, dreizehn Zeilen.** `deriveProjectStand(project)` erzeugt für jede
  erreichbare Feldkombination genau eines der vier Ergebnisse der Union, und die Menge der über den
  **vollständig aufgezählten** Eingaberaum beobachteten Ergebnisse entspricht **exakt** der Tabelle
  im Abschnitt UI/UX — keine unbeobachtete Zeile, kein vierzehntes Verhalten. `[M]`
- [ ] **A5 — Laufende und fehlgeschlagene Läufe behalten ihre Kennzeichen-Optik.** Die Stand-Zeile
  rendert für `kind:'lauf'` die bestehende `StatusTag`-Komponente mit `data-status="running"` bzw.
  `"failed"`; im Zustand `running` ist zusätzlich der bestehende Ring-Indikator vorhanden.
  Zugesichert wird der semantische Haken, **nicht** die CSS-Klasse. `[M]` Das tatsächliche Aussehen
  ist Hinsehen. `[S]`
- [ ] **A6 — Randfall B ist umgesetzt und wird nicht ausgelöst.** Die Bedingung lautet **positiv**
  „jeder Schritt ist erledigt", ausdrücklich **nicht** „die Frontier-Suche lief leer". Zwei
  Nachweise: (i) über den vollständig aufgezählten Eingaberaum liefert `deriveProjectStand` in keinem
  Fall `kind:'fertig'`; (ii) ein Projekt mit `category_selection_enabled: false` und vollem sonstigen
  Fortschritt liefert **nicht** „Alles erledigt". Die Darstellung von `{kind:'fertig'}` wird direkt an
  `ProjectStandLine` geprüft. Es wird **kein** Testeinstieg geschaffen, der den Zustand künstlich über
  die Projekt-Schnittstelle erzeugt. `[M]`

### Stimmigkeit der Angaben

- [ ] **S1 — Eine Ableitung, keine zweite.** `deriveProjectStand` ruft `computeStepStates` und die
  Frontier-Ableitung hinter `getDefaultStepId` auf und rechnet nichts nach. Zwei Nachweise: (i) über
  den gesamten aufgezählten Eingaberaum ist der von der Stand-Zeile benannte Schritt identisch mit
  `getDefaultStepId(computeStepStates(project))` — ermittelt durch **Rückabbildung des erzeugten
  Textes** auf `PIPELINE_STEPS`, nicht durch Vergleich mit einer abgetippten Zeichenkette; (ii)
  `func.min(Photo.taken_at)` kommt in `backend/src/photosort/` an **genau einer** Stelle vor. `[M]`
- [ ] **S2 — Der Klick löst ein, was die Zeile verspricht.** Ein Klick auf die Karte führt auf
  `/projects/:id`, das auf `getDefaultStepId` weiterleitet — also auf den Schritt, dessen Label die
  Stand-Zeile trägt. S1(i) ist dabei eine Bindungszusicherung, keine unabhängige zweite Messung; ihr
  Wert liegt darin, dass eine spätere eigenständige Nachrechnung daran rot wird. `[M]`
- [ ] **S3 — Gleichlauf mit der Statistikseite.** Für dasselbe Projekt liefern `GET /projects`,
  `GET /projects/{id}` und `GET /projects/{id}/stats` identische Werte für `photo_count`,
  `taken_at_earliest`, `taken_at_latest` — geprüft an mindestens zwei Projekten (eines mit Fotos,
  eines ohne) im selben Test, und das Testprojekt trägt `photo_scores`-Zeilen (siehe Security S3).
  `ProjectStatsPage` nutzt dieselbe `formatTakenAtRange`-Funktion wie die Projektkarte. `[M]`
- [ ] **S4 — Eine Abfrage, unabhängig von der Projektzahl.** `GET /projects` setzt sowohl bei **einem**
  als auch bei **vier** Projekten mit Fotos **genau eine** Anweisung ab, die `min(photos.taken_at)`
  enthält — exakte Kardinalität und Skaleninvarianz im selben Test. Ausdrücklich **keine** Assertion
  auf die Gesamtzahl aller Anweisungen. `[M]`
- [ ] **S5 — Die Bezugsmenge stimmt.** Fotos eines anderen Projekts fließen in keinen der drei Werte
  ein; ein Projekt ohne Fotos erhält `(0, None, None)`; ein frisch über `POST /projects` angelegtes
  antwortet mit `photo_count: 0` und beiden Zeitwerten `null`. `[M]`
- [ ] **S6 — `effective_selection_target` bleibt an derselben Zahl.** Mit dem Wegfall von
  `_project_photo_count` speist das Aggregat auch die Vorbelegung des Auswahl-Richtwerts. Es gilt
  unverändert `effective_selection_target == effective_target(selection_target, photo_count)` mit
  demselben `photo_count`, den die Antwort ausweist — inklusive `photo_count == 0`. `[M]`

### Darstellung

- [ ] **D1 — Vier Zustände.** `gefuellt`, `leer`, `ladend`, `fehler` schließen einander aus: im
  Ladezustand erscheint weder Leerzustandstext noch Karte, im Fehlerzustand weder Leerzustand noch
  Karte. Der Kopfbereich mit „Neues Projekt anlegen" ist in allen vier Zuständen bedienbar; die
  Zählzeile erscheint **nur** im Zustand `gefuellt`. `[M]`
- [ ] **D2 — Der Ladezustand ist für Screenreader erkennbar.** Der Platzhalter-Container trägt
  `role="status"` mit zugänglichem Namen; die Platzhalter selbst sind `aria-hidden`. Gilt heute
  bereits — das Kriterium ist ein Wächter gegen den Verlust beim Umbau auf das Raster. `[M]`
- [ ] **D3 — Aufteilung je Breite.** Ein DOM-Baum, kein zweiter Zweig: es gibt **keinen** Text, der
  nur in einer der beiden Breiten im DOM steht. `[M]` Die Geometrie ist in jsdom nicht prüfbar und
  wird im Browser gemessen: bei 1023px liegen die drei Angaben einer Karte auf verschiedenen
  y-Positionen, bei 1024px auf derselben (Toleranz ≤ 2px), und die x-Position der Fotoanzahl ist über
  **alle** Karten identisch — das ist die eigentliche Flucht-Zusage. Vorbedingung im selben Lauf:
  mindestens zwei Karten mit unterschiedlich langen Namen, und die beiden Breiten liefern ein
  verschiedenes Ergebnis. `[M]`
- [ ] **D4 — Name ungekürzt, Pfad kürzbar.** Der vollständige Projektname steht als Textknoten im DOM
  und trägt keine Kürzungs-Utility; der Ordnerpfad darf einzeilig gekürzt werden. `[M]` Dass der Name
  tatsächlich umbricht statt zu überlaufen, ist Hinsehen. `[S]`

### Angleichung der bestehenden Ansichten

- [ ] **G1 — „Projekt anlegen" begrenzt seine Breite.** Namensfeld und Ordner-Browser nehmen ab dem
  Umbruchpunkt nicht mehr die volle Inhaltsbreite ein (Spalten 1–6 bzw. 1–8). Im Browser messbar als
  Verhältnis zur mitgemessenen Breite des Inhaltsbereichs desselben Laufs, **nie** gegen eine
  hartkodierte Pixelzahl. `[M]` Ob das Ergebnis gut aussieht, ist Hinsehen. `[S]`
- [ ] **G2 — Löschdialog: vier Zusagen als Regressionsschutz.** Erstfokus auf „Abbrechen"; die
  Eingabetaste im Bestätigungsfeld löst das Löschen nicht aus; die Schaltflächenzeile darf umbrechen;
  der abzutippende Projektname wird nie gekürzt. **Alle vier gelten heute bereits** — das Kriterium
  ist ein Wächter, kein offener Bau. Neu zu ergänzen ist allein der fehlende Testfall „der Name wird
  nicht gekürzt". `[M]`
- [ ] **G3 — Die Bestätigungshürde bleibt unangetastet.** `isExactProjectNameMatch` bleibt exakt (kein
  Trimmen, keine Angleichung der Groß-/Kleinschreibung), und die serverseitige Prüfung bleibt
  unabhängig von der Bedingung im Dialog. Der Diff dieser Story enthält **keine** Zeile in
  `DeleteProjectDialog.tsx` unterhalb der Layout-Ebene und keine in der serverseitigen
  Namensprüfung. `[M]`

### Abgrenzung nach außen

- [ ] **X1 — Keine neuen Fehlertexte nach außen.** Die drei neuen Felder erzeugen keinen eigenen
  Fehlerpfad; der Fehlerzustand der Übersicht zeigt unverändert genau den `detail`-Text des Servers
  als Textknoten. `photo_count` und `taken_at_*` sind Zahlen und Zeitstempel, es gibt keine
  Freitextrückgabe. `[M]`

## Datenmodell-Bezug

Keine Migration, keine neue Tabelle, keine Feldänderung. `photos.taken_at` existiert und ist die
einzige gelesene Spalte. Betroffen ist allein das **Antwortschema** `ProjectOut`, das um drei
abgeleitete Felder wächst — siehe [`docs/architecture.md`](../../docs/architecture.md), dort im selben
Pull Request nachzuziehen.

## Architektur / Umsetzung

Getragen von ADR
[`0103`](../decisions/0103-bestandszahlen-an-projectout-stand-bleibt-frontend-ableitung.md):
Fotoanzahl und Aufnahmezeitraum werden Felder von `ProjectOut`, der Bearbeitungsstand bleibt eine
Frontend-Ableitung. Keine Migration, kein neuer Endpunkt, keine neue Abhängigkeit.

### Betroffene Dateien

**Backend**

| Datei | Änderung |
|---|---|
| `backend/src/photosort/photo_aggregates.py` | **neu.** Die eine Definition von „Fotoanzahl und Aufnahmezeitraum eines Projekts": die drei Spaltenausdrücke und der Stapel-Lookup über mehrere Projekte. |
| `backend/src/photosort/api/projects.py` | `ProjectOut` bekommt `photo_count`, `taken_at_earliest`, `taken_at_latest`; `_to_project_out` nimmt das Aggregat als Parameter; `list_projects` lädt es einmal für alle Projekte; `_project_photo_count` entfällt. |
| `backend/src/photosort/api/stats.py` | Die gebündelte Abfrage nimmt ihre drei Werte aus `photo_aggregates.py`, statt `func.count`/`func.min`/`func.max` selbst zu schreiben. Sonst unverändert. |
| `backend/tests/test_api_projects.py`, `backend/tests/test_api_stats.py` | Felder, Randfälle, Abfragezahl, Gleichlauf beider Endpunkte. |

**Frontend**

| Datei | Änderung |
|---|---|
| `frontend/src/api/types.ts` | Drei Pflichtfelder an `ProjectOut`. |
| `frontend/src/utils/pipelineSteps.ts` | `deriveProjectStand(project)` — die Stand-Ableitung, aufgesetzt auf `computeStepStates` und die bestehende Frontier-Suche. |
| `frontend/src/utils/formatStats.ts` | `formatTakenAtRange(earliest, latest)` — Datumsspanne, Ein-Tages-Fall, Platzhalter. |
| `frontend/src/components/ProjectStandLine.tsx` | **neu.** Rendert die vier Ausprägungen der Stand-Zeile. |
| `frontend/src/components/StatusTag.tsx` | Optionale Prop `label` überschreibt die Beschriftung; Optik, Tonwerte und Ring-Indikator unverändert. |
| `frontend/src/pages/ProjectListPage.tsx` | Karte → Rasterzeile, drei neue Angaben, Fehlertitel, Zählzeile. |
| `frontend/src/pages/ProjectCreatePage.tsx` | Namensfeld und Ordner-Browser auf Spaltenbreite begrenzt. |
| 15 lokale `project()`-Testfabriken | Drei Zeilen je Fabrik; `tsc` findet jede einzelne. |

### Datenfluss

Eine gruppierte Abfrage je Antwort, nicht eine je Projekt:

```sql
SELECT project_id, COUNT(*), MIN(taken_at), MAX(taken_at)
FROM photos WHERE project_id IN (…) GROUP BY project_id
```

`list_projects` lädt die Projekte, reicht ihre IDs einmal an
`photo_aggregates_by_project(session, ids)` und übergibt `_to_project_out` das fertige Aggregat.
`get_project`, `create_project` und `set_selection_target` rufen denselben Helfer mit einer
einelementigen Liste — es gibt keinen zweiten Rechenweg für dieselben Zahlen. Ein Projekt ohne Fotos
fehlt im Ergebnis der Gruppierung und bekommt die benannte Vorgabe `(0, None, None)`; `0` ist eine
Aussage, `null` ihre Abwesenheit, und die Unterscheidung trägt bis in die Anzeige.

`effective_selection_target` liest seine Fotoanzahl aus demselben Aggregat. Die bisherige
Einzelabfrage `_project_photo_count` entfällt ersatzlos: Die Übersicht setzt danach eine Abfrage
**weniger** je Projekt ab als vorher.

**Mechanischer Nachweis gegen N+1** (Muster aus `test_api_photos.py`/`test_project_deletion.py`): Ein
`before_cursor_execute`-Listener zählt die Anweisungen, die `min(photos.taken_at)` enthalten — es muss
genau **eine** sein, bei einem wie bei vier Projekten. Ein Test auf die Gesamtzahl wäre an die
bestehenden, hier nicht angefassten Lauf-Abfragen gebunden und beim nächsten fremden Zusatz rot.

### Die Stand-Ableitung lebt an genau einer Stelle

`frontend/src/utils/pipelineSteps.ts`, neben `computeStepStates` und der Frontier-Suche, die schon
heute das Ziel der Weiterleitung von `/projects/:id` bestimmt. `deriveProjectStand` **ruft** diese
beiden auf; es rechnet nichts nach. Damit ist die Zusage „der Klick landet auf dem Schritt, den die
Zeile benennt" strukturell erfüllt und nicht durch Nachhalten.

Rückgabe ist eine unterscheidbare Union, keine vorformatierte Zeichenkette — die Zeile braucht
Präfix, Schriftschnitt und Kennzeichen-Optik getrennt:

```ts
type ProjectStand =
  | { kind: 'weiter'; stepLabel: string }              // „Weiter:" + Schrittname
  | { kind: 'hinweis'; label: string }                 // Randfall A und C, reiner Text
  | { kind: 'lauf'; status: 'running' | 'failed'; label: string }
  | { kind: 'fertig' }                                 // Randfall B
```

Die Zuordnung ist zweistufig und deshalb vollzählig: erst der Frontier-Schritt, dann der Lauf, der zu
genau diesem Schritt gehört (`scan` → `last_scan`, `ausschuss` → `last_scoring_run`, `kriterien` →
`last_criterion_scoring_run`; `gate` und `kuratierung` tragen keinen Lauf). Die Schrittnamen kommen
wörtlich aus `PIPELINE_STEPS[].label`, die Zusätze „ läuft…" und „ fehlgeschlagen" werden angehängt
statt getippt. Ein `scan`, der Frontier ist, kann nur `null`, `running` oder `failed` sein — wäre er
`success`, wäre er erledigt und nicht Frontier.

**Randfall B gilt genau dann, wenn jeder Schritt `isDone` ist** — nicht, wenn die Frontier-Suche leer
läuft. Weil `kuratierung.isDone` ohne Abschlusssignal konstant `false` ist, bleibt der Zustand heute
unerreichbar und wird von selbst erreichbar, sobald es eines gibt.

**Randfall C, entschieden von Daniel:** Fällt die Frontier-Suche auf einen bereits **erledigten**
Schritt zurück, trägt die Zeile den eigenen Wortlaut „Kategorie-Bewertung ist abgeschaltet" als
reinen Text (`kind:'hinweis'`) statt eines irreführenden „Weiter: Ausschuss-Gate" auf etwas längst
Erledigtem. Das Klickziel bleibt unverändert. Die Zeile benennt in diesem Fall — wie in Randfall A
und B — keinen Schritt; die Zusage aus S2 bleibt damit unverletzt, weil sie nur greift, wo die Zeile
einen Schritt nennt.

**Bedingung ist der Rückfall, nicht der Flag-Zustand.** Zurückfallen kann die Suche nur bei
ausgeschaltetem `category_selection_enabled` — mit eingeschaltetem Flag gibt es immer einen
erreichbaren offenen Schritt. Umgekehrt gilt das nicht: Ein abgeschaltetes Flag bei noch offenem
Gate oder erreichbarer Kuratierung hat sehr wohl einen nächsten Schritt und nennt ihn. Am Flag
festgemacht verschwiege die Zeile dort einen tatsächlich erreichbaren Schritt.

**Eine benannte Abweichung vom Wortlaut des Entwurfs:** Die Tabelle in Spec 0358 schreibt „Weiter:
Kategorie-Kuratierung". `PIPELINE_STEPS` trägt seit dem Wegfall der Kategorien das Label
`Kuratierung`; angezeigt wird „Weiter: Kuratierung". Die Regel des Entwurfs („wörtlich
`PIPELINE_STEPS[].label`, es wird kein neues Vokabular erfunden") ist die tragende, der abgedruckte
Beispieltext die veraltete Seite derselben Aussage.

### Reihenfolge und Commit-Schnitte

Ein Pull Request, fünf Commits — jeder für sich lauffähig und grün:

1. `feat(api): Fotoanzahl und Aufnahmezeitraum an ProjectOut` — `photo_aggregates.py`, `projects.py`,
   Umstellung von `stats.py`, Backend-Tests einschließlich Abfragezählung und Gleichlauf. Dazu die
   Ergänzung in `docs/architecture.md` und die Ankerzeile im Sicherheitskonzept (Security S2).
2. `feat(ui): Bearbeitungsstand aus der bestehenden Schritt-Ableitung` — nur `pipelineSteps.ts` und
   Tests. Reine Logik, kein Rendering; die dreizehn Zeilen der Tabelle sind hier prüfbar, bevor
   irgendetwas gezeichnet wird.
3. `feat(ui): Projektkarte zeigt Anzahl, Zeitraum und Stand` — `types.ts`, die fünfzehn
   Testfabriken, `formatTakenAtRange`, `ProjectStandLine`, `StatusTag`-Prop, `ProjectListPage`.
4. `fix(ui): Anlegen-Formular auf Spaltenbreite` — `ProjectCreatePage`.
5. `test(ui): Zusagen des Löschdialogs festgehalten` — der fehlende Fall „Name wird nicht gekürzt".

Commit 2 vor Commit 3 ist kein Geschmack: Ohne ihn entstünde die Wortlaut-Tabelle in einer
Rendering-Komponente und wäre nur über das DOM prüfbar.

**Nebenbefund, vor Commit 3 zu entscheiden:** `ProjectListPage` ist heute der einzige Konsument von
`deriveScanStatus` und von `StatusTag` ohne `label`-Prop. Entfällt das eigenständige Scan-Kennzeichen,
ist die `LABELS`-Tabelle in `StatusTag.tsx` unerreichbar und `utils/scanStatus.ts` samt Testdatei
möglicherweise auch. Zwei saubere Wege: `label` **verpflichtend** machen (dann fällt `LABELS` weg und
`scanStatus.ts` mit ihm), oder `deriveProjectStand` nutzt `deriveScanStatus` für die Scan-Zeile weiter
(dann bleibt beides lebendig). Was **nicht** geht: eine Testdatei stehen lassen, die eine
Voreinstellung prüft, die kein Aufrufer mehr auslöst.

## UI/UX

### Aufteilung nach Breite

**Mobil:** Kartenliste in `flex flex-col gap-3`; Kopfbereich `h1` über Zählzeile, darunter die
Schaltfläche über die volle Breite. **Ab `lg:` (1024px):** Kopfbereich `flex flex-wrap items-center
justify-between` mit der Schaltfläche auf Eigenbreite rechts; die Karte wird zur einzeiligen
Rasterzeile.

Die Zeile ist **ein** DOM-Baum: `lg:grid lg:grid-cols-12 lg:gap-x-3` auf dem bestehenden `Link`. Kein
`hidden lg:block` neben `lg:hidden`, kein doppelter Inhalt, keine Spaltenkopfzeile — jeder Wert trägt
sein Wort bei sich. Das bestehende `min-h-11` bleibt die Zeilenhöhe.

### Die Projektkarte im Einzelnen

Mobil vier Zeilen untereinander (`gap-2`): Name → Ordnerpfad → Kennzahlenzeile → Stand-Zeile.
Ab `lg:` dieselben vier Angaben als Spaltengruppen:

| Spalten | Angabe | Typografie | Token |
|---|---|---|---|
| 1–4 | Identität: Name über Pfad | Name `text-lg` Semi-Bold, Pfad `font-mono text-xs` | Name `color.text-h`, Pfad `color.text` |
| 5–6 | Fotoanzahl | Zahl `font-mono`, Wort sans, beides `text-sm` | `color.text` |
| 7–9 | Aufnahmezeitraum | Wortmarke sans, Daten `font-mono`, `text-sm` | Wortmarke `color.text-muted`, Daten `color.text` |
| 10–12 | Stand-Zeile | `text-sm` | siehe unten |

Formatregeln: Fotoanzahl mit deutschem Tausenderpunkt und nachgestelltem Wort („1.284 Fotos"), **auch
bei 0** („0 Fotos"). Zeitraum als „Aufnahmen 02.04.2019 – 17.08.2019"; fällt frühestes und spätestes
Datum auf denselben Tag, steht das Datum einmal; fehlt eines von beiden, steht der etablierte Strich
`NOT_AVAILABLE` in `color.text-muted`. Der Strich heißt „keine Angabe" und ist ausdrücklich nicht
dasselbe wie eine Null. Der Name bleibt ungekürzt und umbricht bei Bedarf; der Ordnerpfad bleibt
`truncate`.

### Die Stand-Zeile

Aufbau: Präfix „Weiter:" in `color.text-muted`, dahinter der Schrittname in `color.text-h`,
Semi-Bold — Hierarchie über Farbe und Schnitt in einer Zeile, ohne zweite Textzeile. Das bisherige
eigenständige Scan-Kennzeichen entfällt und geht hier auf: zwei Statusaussagen nebeneinander
konkurrieren, und „wo mache ich weiter" schließt „läuft gerade etwas" mit ein.

| Frontier-Schritt | Zusätzliche Bedingung | Ausprägung | Wortlaut |
|---|---|---|---|
| `scan` | `last_scan === null` (**Randfall A**) | `hinweis` | „Noch nicht gescannt" |
| `scan` | `last_scan.status === 'running'` | `lauf` (running) | „Scan läuft…" |
| `scan` | `last_scan.status === 'failed'` | `lauf` (failed) | „Scan fehlgeschlagen" |
| `ausschuss` | Lauf `running` | `lauf` (running) | „Ausschuss-Erkennung läuft…" |
| `ausschuss` | Lauf `failed` | `lauf` (failed) | „Ausschuss-Erkennung fehlgeschlagen" |
| `ausschuss` | sonst | `weiter` | „Weiter: Ausschuss-Erkennung" |
| `gate` | — | `weiter` | „Weiter: Ausschuss-Gate" |
| `kriterien` | Lauf `running` | `lauf` (running) | „Kriterien-Bewertung läuft…" |
| `kriterien` | Lauf `failed` | `lauf` (failed) | „Kriterien-Bewertung fehlgeschlagen" |
| `kriterien` | sonst | `weiter` | „Weiter: Kriterien-Bewertung" |
| `kuratierung` | — | `weiter` | „Weiter: Kuratierung" |
| — | Frontier-Suche auf einen bereits **erledigten** Schritt zurückgefallen (**Randfall C**) | `hinweis` | „Kategorie-Bewertung ist abgeschaltet" |
| kein offener Schritt | **Randfall B** | `fertig` | „Alles erledigt" |

Randfall A bekommt bewusst **nicht** „Weiter: Scan": Ein Projekt, in dem noch nie etwas passiert ist,
hat keinen *nächsten* Schritt, sondern noch gar keinen. Randfall B trägt zusätzlich das Symbol `check`
(`aria-hidden` — das Wort trägt die Aussage), kein grünes Erfolgs-Kennzeichen: ein fertiges Projekt
ist ein Ruhezustand, keine Meldung. Laufende und fehlgeschlagene Läufe behalten die
Kennzeichen-Optik (Fläche `color.elevated`, farbiger 1px-Rand, farbige Beschriftung, beim laufenden
Lauf der Ring-Indikator); auf der Karte trägt das Kennzeichen seine Aussage über Rand und
Beschriftung, nicht über die Fläche.

### Die vier Zustände

Der Kopfbereich ist in **allen vier** Zuständen unverändert sichtbar und bedienbar — ein Projekt
anlegen zu können, hängt nicht daran, ob die Liste lädt oder scheitert. Nur die Zählzeile entfällt,
solange keine Zahl bekannt ist.

- **`gefuellt`:** die Kartenliste, Zählzeile „N Projekte" (heute steht dort „N Ordner" — das benennt
  die Liste falsch und wird korrigiert).
- **`leer`:** unverändert der bestehende, bereits gestaltete Leerzustand. Bewusst nicht angefasst.
- **`ladend`:** vier Platzhalter an der Stelle der Karten, Höhe `h-[136px]` mobil / `lg:h-[72px]`, im
  selben Abstand `gap-3`. Kein Text „Lädt…", kein Vollbild-Spinner. Der Container trägt `role="status"`
  mit zugänglichem Namen, die Platzhalter sind `aria-hidden`.
- **`fehler`:** ein `alert` anstelle der Liste, mit dem kuratierten Titel „Projekte konnten nicht
  geladen werden" statt des nichtssagenden Standardtitels „Fehler". Beitext ist der wörtliche
  `detail`-Text des Servers, ausschließlich als Textknoten. „Erneut versuchen" bleibt im Hinweis
  selbst. Der Fehler ersetzt nur die Liste, nie die ganze Ansicht.

### Barrierefreiheit

Der Ladezustand ist über `role="status"` angesagt, nicht nur optisch erkennbar. Kein Zustand hängt
allein an Farbe: „Alles erledigt" trägt das Wort, das Symbol ist `aria-hidden`; laufende und
fehlgeschlagene Läufe tragen ihre Aussage in der Beschriftung. Die Zeile **ist** die Trefferfläche
(mindestens 44px), sie wird nicht zusätzlich aufgespannt. Die Fokusreihenfolge folgt der visuellen.

### Angleichung der bestehenden Ansichten

**Projekt anlegen:** mobil laufen Feld, Browser und Aktionszeile über die volle Breite untereinander.
Ab `lg:` steht das Namensfeld auf Spalten 1–6 und der Ordner-Browser auf Spalten 1–8; Spalten 9–12
bleiben leer. Ein 950px breites Eingabefeld für einen Projektnamen ist unbrauchbar, und eine
Ordnerliste über die volle Inhaltsbreite ist eine Wüste aus Weißraum zwischen Name und Dateizahl.
Heute trägt die Seite keinerlei Breitenbegrenzung — das ist echt offen, kein bereits erfüllter Punkt.

**Löschdialog:** Erstfokus auf „Abbrechen", kein Absenden per Eingabetaste, umbrechende
Schaltflächenzeile auf schmalen Geräten, und der abzutippende Name nie gekürzt. Alle vier sind
bereits umgesetzt; die Story fügt nur den fehlenden Testfall zum ungekürzten Namen hinzu und ändert
sonst nichts unterhalb der Layout-Ebene.

### Ausgewiesene Lücken

Diese Story schließt keine davon; sie sind benannt, damit der fest gesetzte Wert nicht als Token
missverstanden wird: Umbruchbreite 1024px (nur in Tailwind und `e2e/lib/viewports.ts`),
Inhaltsbreite 1024px, 12 Rasterspalten, Platzhalterhöhen 136/72px (aus der Kartenhöhe gemessen),
Trefferflächenhöhe 44px, Semi-Bold ohne Schriftschnitt-Token, Textkürzung, Puls des Platzhalters.

## Security

Das Feature ist **sicherheitsrelevant**, in eng begrenztem Umfang: kein neuer Endpunkt, kein neues
Secret, keine neue Abhängigkeit, kein Datenfluss nach außen und keine neue Datenklasse. Das
Antwortschema eines bestehenden Endpunkts wächst um drei Felder, deren Werte dieselbe Zielgruppe heute
schon über `GET /projects/{id}/stats` bekommt, und eine bestehende Bestätigungshürde wird angefasst.

**S1 (Muss) — Die drei neuen Felder verändern die Datensichtbarkeit nicht, und die Auth-Durchsetzung
greift unverändert.** `photo_count`, `taken_at_earliest` und `taken_at_latest` stehen bereits in
`ProjectStatsOut`; neu ist allein der Ort. Alle vier tragenden Operationen hängen am router-weiten
`dependencies=[Depends(get_current_user)]` von `api/projects.py`, dessen Vollständigkeit
`tests/test_auth_guard.py::test_all_project_opencloud_and_stats_routes_require_token` erzwingt — ein
zusätzliches Antwortfeld an einer bestehenden Operation ändert daran nichts, und es entsteht kein
neuer Router. Ein Eigentümer- oder Rollenvergleich wird hier **nicht** erfunden: beide Nutzer sehen
dieselben Projekte (ADR 0003), ein an dieser Stelle neu eingezogener Ownership-Check wäre eine
stillschweigende Änderung des Auth-Modells. `taken_at` ist die korrigierte Aufnahmezeit und damit ein
schwaches personenbezogenes Datum; sein Empfängerkreis bleibt exakt derselbe wie bisher.

**S2 (Muss) — Die Aggregation ist projektgebunden, und zwar über die gesamte Stapelabfrage.**
`photo_aggregates_by_project(session, ids)` ist die erste Stelle des Projekts, die Zahlen für mehrere
Projekte in einem Zug liefert: `WHERE project_id IN (ids)` zusammen mit `GROUP BY project_id`, das
Ergebnis strikt über `project_id` geschlüsselt zurückgegeben, und ein Projekt ohne Treffer entsteht
als `(0, None, None)` — nie durch Übernahme einer Nachbarzeile, nie durch Auslassen des Eintrags.
Angriffsmodell: Die Ausfallrichtung ist keine Fehlermeldung, sondern eine plausible fremde Zahl — ohne
die Einschränkung trägt jede Karte den Bestand der gesamten Instanz, ohne dass irgendetwas rot wird.
Der Test läuft deshalb über **mindestens zwei** Projekte, davon eines ohne Fotos; ein Testbestand mit
einem einzigen Projekt bliebe auch bei fehlender Einschränkung grün. Die Durchsetzungsstelle wird als
Ankerzeile in `specs/architecture/0003-securitykonzept.md` eingetragen, im selben Pull Request, der
die Datei anlegt.

**S3 (Muss) — Die Übernahme in `api/stats.py` verschiebt die Bedeutung von `photo_count` nicht.**
`RatingsOut.unrated` wird dort als `photo_count − eigene Bewertungen` gerechnet, damit der
Bewertungsfortschritt der anderen Person nicht aus einer Differenz rekonstruierbar ist. Der geteilte
Spaltenausdruck muss unter dem dortigen LEFT JOIN auf `photo_scores` weiterhin genau eine Zeile je
Foto zählen — heute ist der Join 1:1, bei einer Änderung auf 1:N zählte er still zu hoch. Der
Gleichlauftest aus S3 der Akzeptanzkriterien fängt das nur, wenn sein Testprojekt tatsächlich
`photo_scores`-Zeilen trägt; das gehört in den Fall hinein. Die bestehenden Statistik-Tests zu
`photo_count`/`unrated` bleiben unverändert stehen.

**S4 (Muss) — Der wörtliche `detail`-Text im Fehlerzustand kann keinen Upstream-Text, keinen
Dateipfad und keine tokenbehaftete Adresse tragen; der Entwurf bleibt wie freigegeben.** Am Code
geprüft: Der Zustand speist sich ausschließlich aus `GET /projects`; `list_projects` wirft selbst
keine `HTTPException` und hat weder Pfad- noch Query-Parameter, also auch kein `422`. Die einzige auf
diesem Weg erzeugbare `detail`-Zeichenkette ist die feste 401-Meldung aus `api/deps.py`, die über
`UNAUTHORIZED_EVENT` im Login endet, nicht im Banner. Ein unerwarteter Serverfehler wird von Starlette
als Klartext ohne `detail`-Feld beantwortet; `api/client.ts::extractDetail` fällt dann auf
„Unerwarteter Fehler (500)" zurück, und es gibt keinen generischen Exception-Handler, der `str(exc)`
in ein `detail` schriebe. Der Upstream-Durchreicher existiert, liegt aber woanders: `create_project`
setzt `detail=str(exc)` aus `OpenCloudError` — dieser Weg erreicht die Erstellen-Seite, nie die
Übersicht.

Die Auflage ist deshalb eine **Erhaltungs**auflage: An `GET /projects` — die neue Aggregation
eingeschlossen — entsteht **kein** neuer `HTTPException(detail=…)`, der einen Ausnahmetext, einen
Dateisystempfad oder eine URL einbettet. Ein Datenbankfehler bleibt ein `500` ohne `detail` und wird
nicht zu einem sprechenden `503` mit `str(exc)` veredelt. Solange das gilt, ist der wörtliche `detail`
zu **behalten**; ihn vorsorglich durch einen Pauschaltext zu ersetzen ist ausdrücklich nicht verlangt.

**S5 (Muss) — Screenshot-Hygiene, verschärft durch die neue Kartendichte.** Der vollständige
`opencloud_path` steht bereits heute auf der Karte; die Story legt nichts Neues offen, und `truncate`
ist Darstellung, nie Schutzmaßnahme. Neu ist die **Kombination**: Ordnerpfad, Fotoanzahl und
Aufnahmezeitraum stehen ab dieser Story nebeneinander. Ordnerstruktur und Aufnahmedaten privater
Familienfotos gelten projektweit als sensibles Datum. Jedes Bild dieser Ansicht, das in einen
öffentlichen Pull Request, eine Spec oder einen Entwurf gelangt, zeigt ausschließlich synthetische
Demo-Daten, nie Daniels Instanz.

**S6 (Muss) — Drei Zusagen des Löschdialogs, jede an einem bestehenden Test verankert.**
`isExactProjectNameMatch` bleibt eine exportierte, einzeln geprüfte Funktion statt eines Ausdrucks im
JSX und vergleicht weiterhin ohne `trim()` und ohne `toLowerCase()`. Der Dialoginhalt bleibt **kein**
`<form>`; die Eingabeattribute `autoComplete`/`autoCapitalize`/`autoCorrect`/`spellCheck` bleiben
stehen — ihr Wegfall bricht den schreibungsgenauen Vergleich auf Mobilgeräten still, die Schaltfläche
schaltete sich nie frei, ohne dass irgendetwas einen Fehler zeigt. Die serverseitige Prüfung bleibt
von der Dialogbedingung unabhängig: `delete_project` vergleicht `payload.confirm_name.strip()` gegen
`project.name` und antwortet sonst `400`, gleichgültig wann ein Client seine Schaltfläche freischaltet.
Angriffsmodell: Eine per `curl` abgesetzte Löschung umgeht die Oberfläche vollständig — die
clientseitige Hürde ist eine Vorsatz-, keine Autorisierungshürde.

**Soll** — Die Fehlerzeile bleibt beim getrennten Bannertitel plus `detail` als Beitext, auch wenn der
Beitext einmal nur „Unerwarteter Fehler (500)" lautet: Titel und Beitext getrennt zu halten ist
billiger zu bewahren als später wiederherzustellen.

## Teststrategie

**Backend (`pytest`).** Der neue Stapel-Lookup wird auf **Integrationsebene** gegen die echte
In-Memory-SQLite geprüft, nicht als reine Funktion — sein Gegenstand *ist* die Gruppierung, und ein
Mock der DB-Schicht prüfte davon nichts. Neue Fälle in `test_api_projects.py`: die drei Werte für ein
Projekt mit Fotos und für ein frisch angelegtes ohne; die Trennung der Bezugsmengen; `MIN`/`MAX` bei
einer Einfügereihenfolge, die nicht der Zeitreihenfolge entspricht; die leere Projektliste (kein
Absturz, keine Abfrage mit leerer `IN`-Liste); die Kopplung an `effective_selection_target`. Der
N+1-Nachweis zählt über einen `before_cursor_execute`-Listener die Anweisungen mit
`min(photos.taken_at)` — einmal bei einem, einmal bei vier Projekten, beide Male genau eine. Den
Gleichlauf prüft ein Fall in `test_api_stats.py`, der beide Endpunkte im selben Test aufruft und die
drei Werte paarweise vergleicht, ergänzt um einen strukturellen Wächter im Stil von
`test_api_motif_corrections.py`: `func.min(Photo.taken_at)` kommt im Quellbaum an genau einer Stelle
vor. Das Coverage-Gate bleibt unverändert scharf.

**Frontend (`vitest`).** Vier Ebenen, ohne Überschneidung. (1) `utils/formatStats.test.ts` prüft
`formatTakenAtRange` über die vier Fälle aus A3 — Testdaten ohne Zonenkennzeichen und fern von
Mitternacht, weil der Lauf keine Zeitzone pinnt. (2) `utils/pipelineSteps.test.ts` prüft
`deriveProjectStand` über den **vollständig aufgezählten** Eingaberaum (`last_scan`,
`last_scoring_run` inkl. `gate_confirmed_at`, `last_criterion_scoring_run`,
`category_selection_enabled` — 256 Kombinationen) und hält die Menge der beobachteten Ergebnisse
gegen die dreizehn Zeilen der Tabelle, **in beiden Richtungen**; dazu A6 und S1(i). (3)
`components/ProjectStandLine.test.tsx` prüft die Darstellung je Ausprägung einmal — hier, und nur
hier, stehen die Anzeigetexte literal. (4) `pages/ProjectListPage.test.tsx` prüft das Zusammenspiel:
die drei Angaben je Karte, „0 Fotos" neben „Aufnahmen —" am ungescannten Projekt, die vier
einander ausschließenden Zustände, und die Zeile als eine Trefferfläche. Keine CSS-Assertion auf
irgendeiner Ebene. Die drei neuen Felder werden **nicht** optional und **nicht** mit Vorgabewert
versehen: dann erzwingt `tsc` die Ergänzung aller 15 `project()`-Fabriken, und es braucht keinen Test
über deren Vollzähligkeit.

**Die Tabelle steht auf der Ausgabeseite, nicht auf der Eingabeseite.** Das ist der Unterschied zu
der getippten Wertekopie, die Spec 0358 untersagt hat. Der Test rechnet den endlichen Eingaberaum
vollständig durch, sammelt die beobachteten Ergebnisse als Tripel `(kind, stepId, runStatus)` und
vergleicht die **Menge** gegen die Tabelle — nur das fängt ein vierzehntes Verhalten, eine unerreichbar
gewordene Zeile und eine zu zwei Zeilen kollabierte Unterscheidung. Den Anzeigetext bildet er auf
seine Definition **zurück** (Nachschlagen in `PIPELINE_STEPS`), statt ihn abzutippen; die drei
Sonderwortlaute stehen in einer ausdrücklichen Ausnahmeliste, sodass jede weitere Abweichung rot wird
statt zu einer stillen zweiten Textquelle. Dazu die paarweise Verschiedenheit aller erzeugten Texte.
Die unabhängige Sollgröße ist damit nicht der Wortlaut, sondern die Zuordnung Schritt → Lauffeld; ihr
Schlüsselvorrat wird gegen die Id-Menge aus `PIPELINE_STEPS` gehalten, damit ein sechster Schritt den
Test rot macht statt durchzurutschen.

**E2E (`e2e/`, Playwright).** Ein neuer Spec, weil die gemeinsame vertikale Flucht Geometrie ist und
`lg:grid-cols-12` in jsdom nur eine Zeichenkette in einem `class`-Attribut. Gemessen wird an der
exakten Grenze 1023/1024px, nicht an zwei bequemen Breiten. Der Rot-Nachweis bei Einführung ist
Pflicht. Nicht neu geprüft wird „kein waagerechtes Scrollen bei 360px" — `no-horizontal-scroll` deckt
die Route bereits ab. Die Breitenbegrenzung in „Projekt anlegen" wird im selben Spec als Verhältnis
zur mitgemessenen Inhaltsbreite geprüft, nie gegen eine Pixelzahl.

**Randfälle, die sonst durchrutschen:** ein laufender Lauf auf einem Schritt, der nicht Frontier ist,
wird nicht gezeigt; `gate` und `kuratierung` landen nie in `kind:'lauf'`; Randfall A greift an
`last_scan === null`, nicht an „Frontier ist Scan"; Randfall C nur bei **erledigtem** Gate; `0 Fotos`
nie als Strich und beide `null` nie als `0`; genau ein `null` (heute unmöglich, morgen erzeugt es eine
Änderung); derselbe Tag bei verschiedenen Uhrzeiten; `999` gegen `1000` an der Tausenderpunkt-Grenze;
leere Id-Menge im Stapel-Lookup; `effective_selection_target` bei `photo_count === 0`.

**Nicht automatisiert geprüft, ausdrücklich:** das gestalterische Urteil über Kartenhöhe,
Umbruchpunkt und Lesbarkeit des umbrechenden Namens (Hinsehen über `browse-app` vor dem PR); die
tatsächliche Farbwirkung der Kennzeichen; Sortieren/Filtern/Suchen nach dem Stand.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) ist um den Abschnitt zu Wortlaut-Tabellen
als Ausgabe-Sollgröße, vorweggenommenen unerreichbaren Zuständen und der Zeitzone der prüfenden
Maschine ergänzt.

## Entscheidungen

- **Randfall C, entschieden von Daniel:** Bei ausgeschaltetem `category_selection_enabled` zeigt die
  Karte „Kategorie-Bewertung ist abgeschaltet" statt eines irreführenden „Weiter: Ausschuss-Gate" auf
  einem erledigten Schritt. Klickziel unverändert.
- **ADR 0103 angelegt:** Aufnahmekriterium für `ProjectOut`, Bestandszahlen als Felder, Stand als
  Frontend-Ableitung, „Alles erledigt" an erledigten Schritten statt an leerer Frontier.
- Alle vier Konsultationen des Ablaufs sind gelaufen, keine wurde übersprungen.

## Offene Fragen

Keine. Die einzige Produktfrage (Randfall C) ist entschieden und oben festgehalten.

## Out of Scope

- Umbenennen eines Projekts und die Pflege-Ansicht insgesamt — eigene Folge-Story, eigene
  Backend-Erweiterung. Spec 0358 Abschnitt 6 setzt diesen Endpunkt voraus; er entsteht dort, nicht
  hier.
- Ein Abschlusssignal im Datenmodell, das Randfall B tatsächlich auslösen würde.
- Suchen, Filtern und Sortieren der Projektliste.
- Vorschaubilder der Fotos auf den Projektkarten.
- Ein vollständiges Fehlerregime für Anlegen und Löschen — nur die Übersicht trägt eine Zustandsachse.
