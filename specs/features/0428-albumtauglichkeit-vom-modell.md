# 0428 - Albumtauglichkeit vom Modell bewerten lassen und Qualität vom Inhalt im Score trennen

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [Issue #428](https://github.com/TheRealKoller/photosort/issues/428), Story 4 des Zielbilds [#424](https://github.com/TheRealKoller/photosort/issues/424)

**Umfang:** deutlich über dem Richtwert von rund 200 Zeilen. Die Story trägt drei voneinander
unabhängige Umbauten in einem Zug — Modellbewertung, Score-Trennung und Cloud-Gate —, berührt
Backend, Datenmodell und Frontend zugleich, und der Großteil der Länge entfällt auf die vierzehn
nummerierten Sicherheitsauflagen und die namentliche Testfallliste. Beide sind Zusicherungen mit
Bereich und Verletzungsfolge und werden nicht gekürzt; das Coverage-Gate trägt diese Spec
nachweislich nicht, die Fallliste ist die einzige Absicherung.

## Ziel

Innerhalb eines Motivs soll der Album-Entwurf das qualitativ beste Bild wählen. Der heutige
Rang-Score kann das nicht: Er mischt Qualitätsmessungen mit Inhaltssignalen bei gleichem Gewicht,
und zwei Kompositionskriterien melden ohne erkennbares Subjekt bzw. ohne erkanntes Gesicht aktiv
einen schlechten Wert statt gar keinen. Ein Foto ohne Personen wird dadurch doppelt abgewertet —
für das, was ihm fehlt, und für das, was es nicht ist. Die angezeigte Qualitätsstufe ist
entsprechend verfälscht.

Unabhängig davon sehen die lokalen Messungen nicht, was ein Bild für ein Album unbrauchbar macht:
geschlossene Augen, verdeckte Gesichter, angeschnittene Personen, langweilige Komposition. Diese
Story holt dieses Urteil beim Cloud-Modell ein und trennt Qualität vom Inhalt. Sie ist Grundlage
für Story 5 (Auswahl mit Richtwert und Mischung), die andernfalls „das beste Bild je Motiv" auf
einer nachweislich verfälschten Grundlage wählt.

## User Story

Als kuratierender Nutzer möchte ich, dass die Qualität eines Fotos danach beurteilt wird, wie
brauchbar es für ein Album ist — und nicht danach, was darauf zu sehen ist —, damit der
Album-Entwurf je Motiv tatsächlich das beste Bild vorschlägt und ich nicht jeden Vorschlag von Hand
korrigieren muss.

## Akzeptanzkriterien

**Albumtauglichkeit vom Modell**

- [ ] Das Cloud-Modell bewertet je Foto die Albumtauglichkeit auf einer festen Skala und nennt dazu eine kurze Begründung.
- [ ] Die Bewertung erfasst ausdrücklich, was lokale Messungen nicht sehen: geschlossene Augen, verdeckte Gesichter, angeschnittene Personen, langweilige Komposition.
- [ ] Die Frage geht an denjenigen Modellaufruf, der jedes Ausschuss-überlebende Foto ohnehin erreicht. Es entsteht kein zusätzlicher Aufruf je Foto.
- [ ] Fotos, die in einem früheren Lauf ohne Albumtauglichkeit bewertet wurden, lassen sich nachbewerten, ohne das Projekt neu einzulesen.

**Qualität und Inhalt getrennt**

- [ ] Der Qualitätswert speist sich aus der Modellbewertung und den lokalen Qualitäts- und Kompositionsmessungen. Inhaltssignale (Menschen, Tier, Gebäude, Landschaft, Fahrzeug, Essen, Sehenswürdigkeit erkannt) gehen nicht mehr in ihn ein.
- [ ] Die Modellbewertung führt, die lokalen Messungen korrigieren sie: ein deutlicher Modellbefund gegen ein Bild kann nicht durch gute lokale Messwerte überstimmt werden.
- [ ] Ein Kriterium, das für ein Foto nicht messbar ist, wird weggelassen statt als schlechter Wert gewertet. Das gilt auch für Kompositionskriterien ohne erkennbares Subjekt bzw. ohne erkanntes Gesicht.
- [ ] Zwei Fotos, die sich ausschließlich im Inhalt unterscheiden, erhalten denselben Qualitätswert.
- [ ] Die angezeigte Qualitätsstufe eines Fotos ohne Personen und ohne erkanntes Objekt ist nicht mehr systematisch niedriger als die eines gleich guten Fotos mit Personen.

**Begründung sichtbar**

- [ ] Die Begründung des Modells ist dort am Bild sichtbar, wo der Album-Entwurf nachgearbeitet wird.

**Ohne Cloud**

- [ ] Ist die Cloud-Nutzung für ein Projekt nicht freigegeben, entsteht kein Album-Entwurf. Die Oberfläche sagt, dass dafür die Cloud-Freigabe nötig ist, und bietet sie an.
- [ ] Es gibt keinen stillen Rückfall auf einen rein lokal gebildeten Qualitätswert.
- [ ] Scan, Ausschuss-Gate und die lokale Bewertung laufen unverändert und vollständig ohne Cloud weiter.

**Gewichte**

- [ ] Die Gewichte des Qualitätswerts sind benannt und an einer Stelle änderbar. Motivabhängige Gewichte (Horizont bei Landschaft, Freiraum bei Porträt) bleiben möglich, werden in dieser Story aber noch nicht festgelegt.

## Datenmodell-Bezug

Neu: `photo_album_suitability` (`photo_id` als Primärschlüssel und Fremdschlüssel auf `photos`,
`level`, `reason`, `provider`, `computed_at`). Die Tabelle hängt an `photos`, nicht an
`photo_motif_assessments` — Begründung in ADR 0095, Abschnitt 6.

Geändert: `photo_rankings.rank_score` und `rank_position` werden nullable; `event_id` bleibt
`NOT NULL`. `PhotoCriterionScore.value` bleibt `NOT NULL` — ein nicht messbares Kriterium wird
gelöscht, nicht auf `NULL` gesetzt.

Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Grundlage: ADR [`0095`](../decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md).
Sie grenzt zugleich ADR [`0002`](../decisions/0002-hybrid-ai-scoring.md) ein: Scan, Ausschuss-Gate
und lokale Bewertung bleiben cloudfrei, allein der Album-Entwurf setzt die Freigabe voraus. ADR 0091
(Motivstärken nur innerhalb eines Motivs vergleichen) bleibt unberührt — die Albumtauglichkeit ist
keine Motivstärke.

### Gewählter Ansatz

**Die Albumtauglichkeit ist eine fünfstufige Modellaussage im bestehenden Aufruf.** Das
Antwortschema von `remote_classification.py` wächst um ein Feld `album_suitability` mit einer ganzen
Zahl `1..5` und einer kurzen Begründung. Der Prompt beschreibt jede Stufe mit einem Anker und nennt
darin ausdrücklich geschlossene Augen, verdeckte Gesichter, angeschnittene Personen und langweilige
Komposition. Kein zweiter Aufruf je Foto: `select_remote_category_candidates` erreicht ohne Vorfilter
den kompletten Ausschuss-überlebenden Bestand, `landmark.py` dagegen nur eine Kandidatenteilmenge und
kommt dafür nicht in Frage.

**Der Qualitätswert ersetzt den bisherigen Rang-Score.** `photo_rankings.rank_score` trägt ab hier

    Q = clamp(M + LOCAL_CORRECTION_SPAN · (2·L − 1), 0, 1)

mit `M` = normierte Modellstufe (`(Stufe − 1)/4`), `L` = gewichtetes Mittel der **vorhandenen**
lokalen Qualitäts-/Kompositionskriterien, `LOCAL_CORRECTION_SPAN = 0,1`. Ohne jedes lokale Kriterium
gilt `Q = M`. Weil `2 · span = 0,2` kleiner ist als der Stufenabstand `0,25`, kann ein Foto der
niedrigeren Modellstufe eines der höheren nie überholen — die lokalen Messungen ordnen ausschließlich
innerhalb einer Stufe (Invariantentest über `L = 0` / `L = 1`).

**Inhalt raus, Nicht-Messbares weg.** In den Qualitätswert gehen genau `sharpness`, `exposure`,
`aesthetics`, `goldener_schnitt`, `symmetrie`, `horizont`, `freiraum`. Die sieben Kriterien mit
`presence_threshold` fallen heraus (Invariantentest: kein Eintrag der Gewichtstabelle trägt eine
`presence_threshold`), ebenso `content_landscape` — es misst Texturarmut, „mehr gleichförmige Fläche"
ist keine Güteaussage; als Kriterium bleibt es unverändert bestehen. `goldener_schnitt` ohne Subjekt
und `freiraum` ohne Gesicht liefern **keinen Wert** statt `0.0`; das Mittel renormiert auf die
vorhandenen Kriterien.

**Ohne Modellurteil kein Entwurf.** `rank_score`/`rank_position` werden nullable. `NULL` heißt „kein
Qualitätswert, weil keine Modellbewertung" — projektweit ohne Cloud-Freigabe, je Foto bei einem
fehlgeschlagenen Aufruf. Ein solches Foto behält seine `event_id` (`NOT NULL`, die Gliederung ist
keine Cloud-Leistung), bleibt im einsehbaren Vorrat und erscheint nicht im Entwurf. Kein Rückfall auf
einen lokal gebildeten Wert.

### Betroffene und neue Dateien

**Neu (Backend):**
- `backend/src/photosort/album_suitability.py` — rein: Stufenzahl, Ankertexte, Prompt-Block,
  `normalize_level`, Parsing der Stufe, Sanitisierung/Kappung der Begründung.
- `backend/src/photosort/classification_prompt.py` — `build_classification_prompt(*,
  max_fine_labels)`: Umzug von `motifs.py::build_motif_prompt` samt seiner Wächtertests, ergänzt um
  den Albumtauglichkeits-Block und die erweiterte JSON-Formzeile. `motifs.py` bleibt reines
  Registermodul und behält seine Grenze („weiß nichts über die Antwortform").
- `backend/src/photosort/quality.py` — rein: `QUALITY_CRITERION_WEIGHTS`, `LOCAL_CORRECTION_SPAN`,
  `local_correction(values, weights) -> float | None` (renormierendes Mittel, aus `rank_photos`
  hierher gezogen), `compute_quality_score(...)`. **Die eine benannte Stelle für die Gewichte.**
- `backend/alembic/versions/<neu>_albumtauglichkeit.py` — Tabelle `photo_album_suitability`;
  `photo_rankings.rank_score`/`rank_position` auf nullable. **Reine Strukturänderung: kein Backfill
  und keine Datenmanipulation**, auch keine Rücksetzung der Bestandswerte auf `NULL`. Die
  vorhandenen Werte stammen zwar aus der alten Formel und wären unter den neuen Anzeigeschwellen
  falsch zu lesen — sie werden aber nicht behandelt, weil der Bestand nach der Umsetzung verworfen
  wird (Daniel löscht die Projekte und legt sie neu an, siehe „Entscheidungen"). `downgrade()`
  stellt die Struktur her, nie die Daten.

**Geändert (Backend):**
- `remote_classification.py` — `RemoteClassification` um die Albumtauglichkeit erweitert; Parsing
  **inhaltlich tolerant** (fehlendes/entartetes Feld → keine Bewertung, kein Fehler, eine
  `WARNING`-Zeile nach bestehendem Muster mit festem Grund-Token statt Rohwert);
  `_MAX_RESPONSE_TOKENS` anheben — zusammen mit seinem Kommentar, dem Wächtertest in
  `tests/test_remote_classification.py` und `pricing.py::ASSUMED_USAGE_BY_PROVIDER.output_tokens`
  (aus der vollbesetzten Antwort **neu herzuleiten**, Invariante `Schranke ≥ 2 × Annahme` einhalten,
  nicht der Annahme anpassen). Richtwert nach Überschlag: Annahme ~250, Schranke 512.
- `criteria.py` — `compute_golden_ratio_score`/`compute_freiraum_score` auf `float | None`; die
  beiden ausführlichen Kommentare, die den `0.0`-Fallback begründen, werden mit der Setzung
  revidiert. Die beiden übrigen `freiraum`-Fallbacks (`0.5`) bleiben: sie sind messbar und neutral.
- `worker.py` — `ContentCriteria` bekommt `not_measurable: frozenset[str]`;
  `_compute_content_criteria` füllt es. `run_criterion_scoring` bekommt neben `_upsert_criterion` ein
  `_delete_criterion` und wendet es **nur** auf `not_measurable` an — ein Kriterium, das mangels
  Detektor gar nicht berechnet wurde, behält seine Altzeile. `_build_grouping_and_rankings` lädt die
  Albumtauglichkeit der Kandidaten, bildet `Q` und schreibt `PhotoRanking` mit `NULL` für Fotos ohne
  Bewertung; `rank_photos` läuft nur über die bewertete Teilmenge (`rank_position` bleibt dort
  lückenlos ab 1). `run_remote_category_classification` persistiert die Albumtauglichkeit im selben
  Schleifendurchlauf wie die Motiv-Kopfzeile (derselbe `now`, dieselbe Best-effort-Regel).
  `select_remote_category_candidates`: Skip-Kriterium wird **Cloud-Kopfzeile UND
  Albumtauglichkeitszeile** — das ist die Nachbewertung. `DEFAULT_CRITERION_WEIGHTS` entfällt.

**Das Skip-Kriterium steht an drei Stellen, und keine davon zieht automatisch nach.** Die Annahme,
`GET .../classify/estimate` benutze dieselbe Funktion und folge deshalb von selbst, ist falsch —
`api/projects.py::_count_remote_category_candidates` ist eine **eigene, duplizierte Query**
(`COUNT` mit `NOT EXISTS`), die ihr Docstring unter Sicherheitsauflage S15 ausdrücklich als Duplikat
führt. Alle drei ändern sich in derselben PR (Auflagen S6/S7):

- `worker.py::select_remote_category_candidates` — was gesendet wird.
- `api/projects.py::_count_remote_category_candidates` — was die Schätzung zählt. Bleibt sie
  unverändert, zählt sie `0`, während der Lauf den gesamten Bestand sendet: eine kostenpflichtige
  Aktion würde auf falscher Grundlage freigegeben. Die Negation eines `exists()` wird per De Morgan
  zur Disjunktion — eine falsch geklammerte Negation zählt still eine andere Menge, deshalb prüft
  der Test **Mengengleichheit** gegen den Worker-Pfad statt zweier getrennter Erwartungswerte.
- `api/photos.py::_cloud_vision_status_out` (die `is_candidate`-Ableitung der
  `REMOTE_CATEGORY`-Phase) — was die Oberfläche als Ergebnis meldet. Bleibt sie beim reinen
  Kopfzeilentest, meldet sie für jedes Bestandsfoto `RESULT`, während dasselbe Foto in Auswahl und
  Schätzung wieder Kandidat ist.
- `ranking.py` — `rank_photos(scores: Mapping[int, float])`: reine Sortierung. Renormierung und
  Gewichte ziehen nach `quality.py` um.
- `models.py` — `PhotoAlbumSuitability`; `PhotoRanking.rank_score`/`rank_position` nullable.
- `project_deletion.py` — `photo_album_suitability` in die Löschfolge (vor `photos`).
- `api/photos.py` — `RankingOut.rank_score`/`rank_position` nullable; neues
  `AlbumSuitabilityOut { level, reason }` an `PhotoOut`; `_top_n_per_event_photo_ids` und
  `_partition_sizes` schließen `rank_position IS NULL` aus.

**Geändert (Frontend):** siehe Abschnitt UI/UX.

### Umsetzungsreihenfolge

1. `album_suitability.py` (rein, keine Abhängigkeiten).
2. `classification_prompt.py` — Umzug + neuer Block, Wächtertests mit umziehen.
3. `remote_classification.py` — Schema, Parsing, Token-Schranke; `pricing.py`-Annahme neu herleiten.
4. Datenmodell + Migration + `project_deletion.py`.
5. Schreibpfad `run_remote_category_classification` + geweitete Kandidatenauswahl (Nachbewertung).
6. `criteria.py` + `ContentCriteria.not_measurable` + `_compute_content_criteria`.
7. `quality.py` (rein) samt Invariantentests.
8. `ranking.py` auf reine Sortierung umbauen, `DEFAULT_CRITERION_WEIGHTS` entfernen.
9. Ranking-Phase im Worker: Qualitätswert bilden, `NULL` schreiben, `_delete_criterion` anwenden.
10. API-Schicht.
11. Frontend.
12. Abschließend: `docs/architecture.md` gegen das tatsächlich Gebaute prüfen.

Schritte 1–3 und 7–8 sind reine Module und laufen ohne Datenbank — sie tragen den Großteil der
Invariantentests.

## UI/UX

Drei Anzeigeorte, nach Genauigkeit gestaffelt, plus ein neuer Zustand der Kuratierung. Keine neue
Farbe, kein neues Symbol, kein neuer Baustein, keine neue Abhängigkeit.

### Eine Stufenskala, nicht zwei

Die grobe Dreistufigkeit (`utils/qualityLevel.ts` → `QualityMeter`) bleibt die einzige Stufenanzeige
auf der Kachel. Mit den Schwellen auf den Stufenmitten (0,375 / 0,625) ist sie eine deterministische
Vergröberung der Modellstufe: **Stufe 1–2 → niedrig, 3 → mittel, 4–5 → hoch**, für jeden zulässigen
lokalen Korrekturbetrag. Das gilt, solange `span ≤ 0,125` ist; ein größerer Wert lässt dieselbe
Modellstufe in zwei Anzeigestufen erscheinen, und die Zuordnung oben wird falsch. Ein Test prüft sie
über die Extremwerte `L = 0` und `L = 1` je Stufe.

Die genaue Stufe („Stufe 4 von 5") erscheint deshalb **nicht** neben der Dreistufigkeit, sondern nur
in den Bewertungsdetails. Zwei Skalen nebeneinander wären zwei Zahlen für eine Aussage.

Die drei Beschriftungen heißen ab hier **„Wenig albumtauglich" / „Bedingt albumtauglich" / „Gut
albumtauglich"** statt „Einfache/Gute/Hohe Bildqualität" — der Wert misst keine Bildgüte mehr, und
ein gestochen scharfes, langweiliges Foto trüge sonst die Beschriftung „Einfache Bildqualität".
Dieselbe Vokabel („Albumtauglichkeit") gilt in Datenmodell, API und Oberfläche.

**Abgrenzung zur Bewertung „Album-würdig".** Die Modellaussage darf nie die Form des
Bewertungs-Kennzeichens annehmen: keine `Badge`, keine Bewertungsfarbe (`--rating-album-worthy`,
`--accent`), kein `book`-Symbol, keine gefüllte Fläche. Sie bleibt schmuckloser Text in der
Kartenfußzeile mit dem neutralen Drei-Punkte-Meter (`aria-hidden`); das Kennzeichen der menschlichen
Bewertung bleibt gefüllt, farbig und im Kartenkörper. Verletzt eine Umsetzung das, liegen die
Entscheidung eines Menschen und die Schätzung eines Modells in derselben Form und Farbe auf einer
Kachel.

### Die Begründung

- **Kuratierungskachel** (`CurationPhotoTile`, Fußzeile, unmittelbar unter der Stufenzeile und über
  dem Verwerfen-Knopf): auf zwei Zeilen begrenzt (`line-clamp-2`, `text-xs text-text`). Der
  vollständige Text bleibt im DOM und damit für Screenreader ungekürzt. Kein Ausklapp-Bedienelement
  je Kachel. Ohne Begründung (`reason === null`) entfällt die Zeile ersatzlos — kein Platzhalter,
  kein „—".
- **Info-Popover der Kachel und Einzelbildansicht** (`CriterionDetailsList`, Block „Qualität"):
  Zeile „Albumtauglichkeit" mit dem Wert „Stufe 4 von 5" in der bestehenden zweispaltigen Form,
  darunter die **vollständige** Begründung über die volle Breite (`text-xs text-text`, ungekürzt;
  das Popover ist 288px breit und scrollt bereits).
- **Sonst nirgends.** Die Rasterkachel (`PhotoGridPage`) bekommt keine Fußzeile; ihr Info-Popover
  zeigt dieselbe Zeile wie das der Kuratierung, weil beide dieselbe Komponente einbinden.

### Zustand „Cloud-Freigabe nötig"

Nur die Kuratierung (`CuratePage`). Scan, Ausschuss-Gate, lokale Bewertung, Raster-, Einzelbild- und
Vergleichsansicht bleiben unangetastet und werden nicht blockiert; die Schrittleiste markiert die
Kuratierung **nicht** als blockierten Schritt und leitet nicht um — die Vorbedingung des Schritts
ist unverändert, fehlend ist eine Projekteinstellung.

Form: der **Leerzustand der ganzen Ansicht**, an der Stelle von `CURATION_EMPTY_TEXT` und mit
Vorrang vor ihm — ohne Freigabe wäre „führe eine Kriterien-Bewertung aus" ein Rat, der nicht hilft.

- Ein Satz in `--text`: benennt, dass ohne Cloud-Freigabe kein Album-Entwurf entsteht, und dass die
  Freigabe in den Projekteinstellungen erteilt wird.
- Darunter `Button asChild variant="secondary"` → `/projects/:id/settings`, beschriftet „Zu den
  Projekteinstellungen". Bewusst **nicht** die primäre, gefüllte Ausprägung: die Schaltfläche
  navigiert, sie erteilt nichts.
- **Kein `Alert`, kein `role="alert"`, keine Fehlerfarbe, kein Symbol.** Eine fehlende Einwilligung
  ist kein Fehler.
- **Der Zustimmungstext wird nicht wiederholt.** Die Erklärung, was an die Cloud geht, steht
  weiterhin an genau einer Stelle — im Info-Popover neben dem Schalter der Projekteinstellungen. Ein
  zweiter Zustimmungstext in der Kuratierung ist untersagt; zwei Fassungen desselben Textes driften,
  und eine Einwilligung, die an zwei Orten verschieden beschrieben ist, ist keine.
- Der Rückweg ist die bestehende Projektnavigation der Kopfzeile; kein `?from=`-Parameter, kein
  eigener „Zurück zur Kuratierung"-Knopf.
- Der Hinweis erscheint erst, wenn Projekt **und** Kuratierungsantwort geladen sind — sonst blitzt
  er beim Laden eines freigegebenen Projekts kurz auf.

### Foto ohne Bewertung (`rank_score === null` bei aktiver Cloud)

- Kachel: an der Stelle der Stufenzeile der Satz **„Noch nicht bewertet"**, gleiche Schriftgröße,
  gleicher Ton. **Kein Meter-Glyph** — `●○○` oder `○○○` hieße „schlechteste Stufe" statt „nicht
  beurteilt". Kein Kennzeichen, keine Farbe, kein Symbol, keine gedämpfte Bildfläche: das Foto ist
  weder aussortiert noch fehlerhaft.
- Bewertungsdetails: die Zeile „Albumtauglichkeit" trägt denselben Satz statt einer Stufe, und es
  erscheint **keine** Begründungszeile.
- Die Zeile „Rang M von N" entfällt vollständig, wenn `rank_position === null` — geprüft auf
  `!== null`, nie auf Falsyness. „Rang – von 12" wäre eine Rangaussage über ein Foto ohne Rang.
- „Noch nie klassifiziert" und „Modellaufruf für dieses Foto fehlgeschlagen" tragen denselben Satz:
  beide Male hilft derselbe nächste Klassifizierungslauf.
- Anzahlangaben bleiben wahrheitsfähig: die Zahl an der Event-Überschrift („N Kandidaten") und der
  Leerplatz „Kein weiteres Foto verfügbar" müssen dieselbe Menge beschreiben wie der tatsächlich
  einsehbare Vorrat.

### Abgedeckte Zustände der Kuratierung

| Zustand | Darstellung |
|---|---|
| ladend | bestehendes Skelett-Raster (6 Kacheln, `role="status"`), jetzt auch über die Projektabfrage |
| Fehler beim Laden | bestehender `Alert` mit „Erneut versuchen" |
| ohne Cloud-Freigabe | Leerzustand oben, mit Vorrang vor dem Leertext |
| leer trotz Freigabe | bestehender `CURATION_EMPTY_TEXT` |
| einzelnes Foto ohne Wert | „Noch nicht bewertet" auf der Kachel, kein Fehlerbild |
| Fehlschlag des Cloud-Anteils eines ganzen Laufs | unverändert im Klassifizierungsschritt gemeldet |

### Betroffene Frontend-Dateien

`api/types.ts` (`AlbumSuitabilityOut`, `PhotoOut.album_suitability`, `RankingOut`-Felder nullable) ·
`utils/qualityLevel.ts` (Schwellen, Beschriftungen, Vergröberung) · `utils/albumSuitability.ts`
(neu: „Stufe N von 5" und „Noch nicht bewertet" an einer Stelle) · `components/QualityMeter.tsx`
(`level: QualityLevel | null`) · `components/CurationPhotoTile.tsx` (Fußzeile) ·
`components/CriterionDetailsList.tsx` (Block „Qualität", `rank_position`-Absicherung) ·
`components/CriterionDetailsPopover.tsx` · `pages/CuratePage.tsx` (`useProjectQuery`, Leerzustand) ·
`pages/PhotoDetailPage.tsx` · `pages/PhotoGridPage.tsx`.

### Bezug zum Design-System

Alles steht auf vorhandenen Mustern: Stufenanzeige („Grobe Qualitäts-Einordnung statt Rohwert"),
Leerzustand mit Weg zur Vorbedingung, fehlender Wert als Satz statt als Nullwert, ruhiger Hinweis
ohne Fehleroptik. Nachzutragen in `specs/architecture/0004-design-system.md` und im Skill
`design-system`: die geänderten Stufenbeschriftungen, die Abgrenzungsregel Modellstufe ↔
Bewertungskennzeichen und das Muster „fehlende Einwilligung als Leerzustand mit Weg zur einen
Stelle, an der sie erteilt wird". Penpot braucht keinen neuen Baustein.

### Barrierefreiheit und Handy-Breite

- Die Begründung ist freier Modelltext und wird **ausschließlich als React-Textknoten** gerendert —
  nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in `href`/`src`/`style`.
- Die visuelle Kürzung auf der Kachel geschieht per `line-clamp`, nicht durch Abschneiden der
  Zeichenkette: der vorgelesene Text bleibt vollständig.
- Die Stufe wird nie allein über Farbe oder Form getragen — das Punkte-Meter ist `aria-hidden`, der
  ausgeschriebene Stufenname ist der eigentliche Text, und das gilt auch für „Noch nicht bewertet".
- Kein neues Bedienelement auf der Kachel: die Fußzeile behält genau eine Trefferfläche (Verwerfen).
- Bei 360px (Kachel rund 158px): Stufenzeile einzeilig, Begründung zwei Zeilen, Kachel wächst um
  rund 40px. Ein DOM-Baum, kein breitenabhängiger Zweig, kein waagerechtes Scrollen.

## Teststrategie

**Unit (rein, ohne I/O) — der Schwerpunkt dieser Spec.** Die drei neuen Module sind absichtlich rein
und tragen deshalb die Hauptlast:

- `album_suitability.py`: `normalize_level` an allen fünf Stufen (1→0,0 / 5→1,0), Parsing einer
  wohlgeformten Antwort, und jede Verwerfungsform einzeln — fehlende Stufe, 0, 6, `"3"`, 3.5,
  `null`. Jede ergibt „keine Zeile", nie eine geklemmte Stufe. Sanitisierung der Begründung:
  Steuerzeichen/Zeilenumbrüche, Länge `MAX-1`/`MAX`/`MAX+1` (bei `MAX+1` wird **gekürzt**, nicht
  verworfen — Gegenstück zur Feinlabel-Regel, die verwirft, und deshalb als Paar zu prüfen), leere
  und nur-Weißraum-Begründung → `NULL`, nie `""`.
- `classification_prompt.py`: der Umzug von `build_motif_prompt` ist verhaltenserhaltend und läuft
  nach dem Muster „Nachweis ohne Rot-Grün" (kein Testdiff an den mitziehenden Wächtertests,
  identische Testknoten-Menge). Neu geprüft wird nur der Albumtauglichkeits-Block: alle fünf
  Ankertexte vorhanden, die vier benannten Mängel wörtlich genannt, die Skalengrenzen genannt.
- `quality.py`: `local_correction()` und `compute_quality_score()` über der vollen Matrix. Drei
  tragende Fälle: `L`-Renormierung auf die vorhandene Teilmenge (ein fehlendes Kriterium senkt den
  Wert **nicht** — Gegenprobe gegen eine Implementierung, die es als 0 wertet); `Q = M` exakt bei
  leerer Kriterienmenge; Clamping an beiden Rändern (Stufe 1 mit `L=0` bleibt 0, Stufe 5 mit `L=1`
  bleibt 1).

**Invarianten (Unit, tabellengetrieben).** Die vier tragenden Zusagen bekommen je einen eigenen,
benannten Test, der die Aussage über der **Tabelle** formuliert statt sie abzuschreiben:

(a) Kein Eintrag von `QUALITY_CRITERION_WEIGHTS` trägt eine `presence_threshold`, und
    `content_landscape` steht nicht darin. Gelesen aus `CRITERIA_REGISTRY`, nicht aus einer zweiten
    Aufzählung im Test — sonst besteht der Test ein neu aufgenommenes Inhaltskriterium. Dazu eine
    Positiv-Gegenprobe: die Tabelle ist nicht leer und enthält alle sieben Schlüssel.
(b) Zwei synthetische Fotos, die sich ausschließlich in Inhaltskriterien und Motivstärken
    unterscheiden, liefern denselben `Q`.
(c) Für jedes der vier benachbarten Stufenpaare: `Q(n, L=1) <= Q(n+1, L=0)`. Dazu, als eigener Fall,
    `LOCAL_CORRECTION_SPAN < 0,125` **strikt** — mit dem Kommentar, dass die strikte Grenze von der
    Anzeigezusage kommt und nicht von der Ordnungszusage (die trüge noch 0,125). Ohne diesen einen
    Schritt bricht die Frontend-Zusage, während alle Backend-Tests grün bleiben.
(d) `_MAX_RESPONSE_TOKENS >= 2 * assumed.output_tokens` je Anbieter — der Wächter existiert bereits
    (`tests/test_remote_classification.py`, Klasse zu Sicherheitsauflage S12) und wird mitgezogen,
    zusammen mit dem festgenagelten Literal (`== 384` → `== 512`), dem
    `>= longest_plausible_response_tokens`-Fall und dem Herleitungskommentar an der Konstante. Die
    neue Herleitung rechnet die Zahl und den Begründungssatz **mit**; die Schranke wird an die
    Invariante angepasst, nie die Annahme an die Schranke.

**Integration (echtes SQLite, echter Job) — hier liegt das eigentliche Risiko.**

- **„Nicht messbar" vs. „nicht berechenbar" wird PAARWEISE in einem Fall geprüft**, mit einer
  Assertion darauf, dass die beiden Datenbankzustände sich **unterscheiden müssen**. Getrennt
  geschrieben bestehen beide Hälften auch ein `_delete_criterion`, das immer oder nie löscht — und
  genau das ist der naheliegende Fehler. Je Kriterium (`goldener_schnitt`, `freiraum`) vier Fälle:
  Detektion lief + kein Merkmal → Altzeile **fort**, keine neue Zeile, Schlüssel nicht in `L`;
  Detektor-Builder lieferte `None` → Altzeile **unverändert** in Wert, Quelle und Zeitstempel;
  Detektor warf eine Ausnahme → dito; Merkmal vorhanden → Wert geschrieben, Schlüssel **nicht** in
  `not_measurable`.
- **Der gefährlichste Fall hat kein Kriterium im Namen:** fehlt die `display`-Cache-Datei oder ist
  sie unlesbar, verlässt `_compute_content_criteria` die Funktion früh mit zwei leeren Mengen.
  `not_measurable` muss dort **leer** sein. Eine Voreinstellung „alles, was nicht in `values` steht,
  ist nicht messbar" löscht in diesem Fall den gesamten Kriteriensatz des Fotos — lautlos, und mit
  grüner Suite, wenn der Fall fehlt.
- `_delete_criterion` räumt die Zeile **und** den In-Memory-Cache `existing_criterion_scores` ab;
  ein späteres `_upsert_criterion` im selben Lauf darf kein verwaistes ORM-Objekt wiederbeleben.
  Nachweis: zwei aufeinanderfolgende Läufe über demselben Foto, nach dem zweiten existiert die Zeile
  nicht.
- **Nachbewertungs-Auswahl über einer Fixture mit allen vier Kombinationen** aus Cloud-Kopfzeile ×
  Albumtauglichkeitszeile, plus einem am Gate aussortierten Foto. Zwei Assertions über **derselben**
  Fixture: die Kandidatenliste des Worker-Pfads und die Zahl aus
  `api/projects.py::_count_remote_category_candidates` stimmen überein. Das Kriterium bleibt
  konjunktiv — der Fall „Albumtauglichkeit vorhanden, Cloud-Kopfzeile fehlt" gehört dazu und ergibt
  **Kandidat**; er ist die einzige Stelle, an der eine Lockerung auf nur eines der beiden Merkmale
  auffällt.
- `rebuild_run_grouping` (zweiter Aufrufer desselben Rangfolgepfads, Versatz-Endpunkt):
  Zustandsgleichheit als Tupel-Schnappschuss ohne Ids vor/nach, mit Anti-Leerlauf-Marker —
  bestehendes Muster aus Spec 0426. Ohne diesen Fall rechnet der Neuaufbau still weiter nach der
  alten Formel.
- **Ohne Freigabe:** ein vollständiger Lauf mit `cloud_vision_detection_enabled = False` erzeugt
  null Albumtauglichkeitszeilen, jede Rangzeile trägt `rank_score IS NULL` und
  `rank_position IS NULL` bei gesetztem `event_id`, und die lokalen Kriterienwerte sind **identisch**
  zu denen desselben Bestands mit Freigabe. Die Gleichheit der lokalen Werte ist der eigentliche
  Nachweis für „kein stiller Rückfall": eine Assertion nur auf `NULL` bestünde auch, wenn der lokale
  Pfad nebenbei etwas anderes gerechnet hätte.
- **Ein Foto ohne Albumtauglichkeit fällt nicht aus der Gliederung:** es behält seine
  Event-Zugehörigkeit, bleibt im einsehbaren Vorrat und erscheint nicht im Entwurf.

**Migration.** `upgrade()`: Tabelle `photo_album_suitability` mit `photo_id` als PK/FK, `level`
NOT NULL, `reason` nullable; `rank_score`/`rank_position` nullable, `event_id` bleibt NOT NULL.
Geprüft über die gerenderte Postgres-DDL (Nullability, FK, PK) **und** eine SQLite-Verhaltensprobe.
Die Migration ist eine **reine Strukturänderung**; es gibt keinen Testfall über Bestandswerte, weil
sie keine anfasst. `downgrade()` stellt Struktur wieder her und nie Daten: ein Fall pinnt fest, was
mit den `NULL`-Zeilen geschieht (Zeilen entfallen). `PhotoCriterionScore.value` bleibt NOT NULL — ein
Fall hält das fest, damit das Löschen nicht später durch eine `NULL`-Zeile ersetzt wird.

**Frontend (`vitest`).**

- `qualityLevel.ts` tabellengetrieben über **zehn** Fälle: die fünf Modellstufen je bei `L = 0` und
  `L = 1`, also die Werte 0 / 0,1 / 0,15 / 0,35 / 0,4 / 0,6 / 0,65 / 0,85 / 0,9 / 1,0. Jede Stufe
  muss in **genau einer** Anzeigestufe landen; die Fälle 0,35 und 0,4 bzw. 0,6 und 0,65 sind die
  eigentliche Zusage, alles andere trägt sie nur. Dazu die Schwellen als Literale festgenagelt und
  die Inklusivität am Grenzwert (`0,375` → mittel, nächstkleinerer darstellbarer Wert → niedrig).
- `rank_score === null` und `rank_position === null` werden **paarweise gegen eine Zeile mit den
  Werten 0 / 1** geprüft, mit einer Assertion darauf, dass sich die beiden Darstellungen
  unterscheiden, und mit einer **Kardinalität von Null** auf dem Meter-Element und der Rang-Zeile —
  nicht per Textsuche. Muster aus Spec 0427; `0.0` ist ein gültiger Qualitätswert und ein
  Falsyness-Filter verliert ihn lautlos.
- Begründung: voller Text im DOM bei gekürzter Darstellung (Assertion auf den Textinhalt, nicht auf
  die sichtbare Zeilenzahl — die kann jsdom nicht); `reason = null` erzeugt **keinen** Träger
  (Kardinalität Null über ein `data-`-Attribut, nicht über Textsuche); ein Text mit HTML-artigem
  Inhalt kommt als Text an, und ein `javascript:`-Payload erzeugt weder Anker noch `img` (S12).
- Leerzustand ohne Freigabe: benannter Hinweis plus Link in die Projekteinstellungen, und die
  Foto-Liste hat **null** Einträge — beides in einem Fall.

**E2E — kein neuer Spec.** Alles hier Zugesagte ist auf `vitest`-/`pytest`-Ebene prüfbar. Die
einzige echte Layout-Frage (eine sehr lange Begründung sprengt die Kachel) wird **ohne** neuen Spec
abgedeckt: der Demo-Seeder (`demo_state.py`) bekommt ein Foto mit einer Begründung in maximaler
Länge und eines mit `reason = NULL`, womit die bestehenden Specs `no-horizontal-scroll` und
`popover-position` die Kuratierungsroute bereits mit dem Extremfall besuchen. Die visuelle Wirkung
der zweizeiligen Kürzung selbst bleibt Sichtprüfung.

**Bewusst nicht geprüft.** Ob die Modellstufe für ein konkretes Foto die richtige ist, ob die
Ankertexte das Modell tatsächlich zu der gemeinten Unterscheidung bringen, und ob `span = 0,1` die
richtige Korrekturbreite ist. Alles drei ist Kalibrierung gegen einen Fotokorpus, den das Repository
nach der Bilddaten-Regel nicht haben kann — dieselbe Klasse wie die Motivstärken (Spec 0427) und die
Schwellwerte in `scoring.py`. Die Startwerte sind dokumentiert-unkalibriert.

**Coverage.** Backend-Gate `--cov-fail-under=80`, Ausgangslage 97 %. Das Gate trägt diese Spec
**nicht**: bei rund 200 neuen Statements bliebe die Zahl auch dann bei etwa 93 %, wenn der gesamte
Albumtauglichkeitspfad ungetestet bliebe. Tragend ist allein die Fallliste oben. Die drei neuen
reinen Module erreichen 100 %; in `worker.py` ist nicht die Zahl der Maßstab, sondern ob die vier
Zweige des Lösch-/Behalten-Entscheids je einen Fall haben.

## Security

Einstufung: **sicherheitsrelevant.** Kein neues Secret, kein neuer Anbieter, kein zweiter Aufruf je
Foto, unveränderter Bilddatenumfang. Neu sind drei Dinge: ein Fremdtextkanal, der bis in die
Oberfläche durchschlägt; eine Modellzahl, die die Bildauswahl steuert; und eine geweitete
Kandidatenauswahl, die den bereits bewerteten Bestand einmalig erneut an den Anbieter schickt. Die
Auflagen sind nummeriert, damit Umsetzung und Review sie einzeln abhaken können.

### Die Cloud-Antwort als Vertrauensgrenze

- **S1** Die Stufe wird ausschließlich als echter `int` im Band `1 <= level <= 5` übernommen,
  `bool` vorher ausgeschlossen (`isinstance(True, int)` ist `True`; `"level": true` erschiene sonst
  als Stufe 1, die schlechteste Aussage, die das Produkt kennt, erfunden aus einem Nicht-Wert).
  `float` wird abgewiesen, auch `4.0`: die Stufe ist ein Anker, kein Messwert, und die
  Zurückweisung aller Gleitkommawerte schließt `NaN`/`±Infinity` mit aus, die `json.loads` klaglos
  parst. Keine Umdeutung von `"4"`. Die Bereichsprüfung bleibt ein **Vergleich** und ein
  unbrauchbarer Wert wird **verworfen**, nie geklemmt — `rank_score` ist eine
  `double precision`-Spalte und Starlette rendert mit `allow_nan=False`: ein durchgelassener
  entarteter Wert legt die gesamte Fotoliste des Projekts auf `500`, nicht nur den einen Eintrag.
  Die Prüfung gehört an den Parser in `album_suitability.py`, nicht an die Datenbankschicht — die
  Testsuite läuft auf SQLite, dessen Typaffinität einen Gleitkommawert in einer INTEGER-Spalte
  still annimmt, während PostgreSQL ihn abweist. Ohne brauchbare Stufe entsteht **keine** Zeile,
  und das Foto bleibt Kandidat des nächsten Laufs.
- **S2** `reason` wird mit `cloud_vision.py::_sanitize_label_text` saniert — dieselbe Funktion, nie
  eine zweite Fassung davon —, **danach** gemessen und auf `MAX_ALBUM_SUITABILITY_REASON_LENGTH`
  (160 Zeichen) gekürzt. Die Reihenfolge ist die Auflage: vor der Sanitisierung zu kürzen ließe
  einen halbierten Bidi-/Zero-Width-Kontext stehen, den die Sanitisierung danach nicht mehr sieht.
  Kein String, oder leer nach der Sanitisierung, heißt `NULL` — nie `""`.
  **Gekürzt statt verworfen**, bewusst anders als der Feinlabel- und der Sehenswürdigkeit-Pfad:
  dort erzwingt eine Vergleichsoperation stromabwärts das Verwerfen (`_slugify` auf einen
  `canonical_key`, exakter Vergleich in `events.py::LandmarkChangeSignal`), und ein gekürzter Wert
  führte zwei verschiedene Dinge zusammen. `reason` wird nirgends verglichen, geschlüsselt,
  dedupliziert oder slugifiziert; die Kappung ist eine Storage- und Degenerationsgrenze, wie bei
  `PhotoCloudVisionError.error_message`. Wird der Text später Gegenstand eines Vergleichs, gilt ab
  dann die Verwerfensregel — diese Auflage ist an die Abwesenheit jeder Identitätsfunktion
  gebunden, nicht an den Text.
- **S3** Eine verworfene Stufe erzeugt genau eine WARNING-Zeile mit `photo_id` und einem **festen
  Grund-Token**, nie dem Rohwert. `reason` wird **nie** geloggt, in keiner Länge und in keiner
  Form: es ist genau der Fremdtext, der aus dem Log herauszuhalten ist, und eine mehrzeilige
  Antwort erzeugte gefälschte Logzeilen. Nie die vollständige Antwort, nie der Request-Body, nie
  Base64-Bilddaten, nie der API-Key.
- **S4** Der Prompt entsteht in `classification_prompt.py` ausschließlich aus dem Code —
  `MOTIF_REGISTRY` und die fünf festen Stufenanker. Nie aus Datenbankinhalten und nie aus einer
  früheren Modellantwort; jeder Rückkopplungspfad bleibt untersagt.
- **S5** `_MAX_RESPONSE_TOKENS` und `pricing.py::ASSUMED_USAGE_BY_PROVIDER.output_tokens` werden
  **beide** aus einer vollbesetzten Antwort neu hergeleitet — vollbesetzter Achter-Motivvektor,
  `excluded`, zwei Feinlabels, Stufe und eine Begründung an der 160-Zeichen-Grenze. Die
  Reserve-Invariante `Schranke >= 2 × Annahme` reißt bei den heutigen Werten (384 gegen 2 × 180)
  **rechnerisch**, nicht hypothetisch: die Reserve beträgt heute 24 Token. Sie wird hier durch neue
  Zahlen eingehalten, nicht durch Anpassen der Erwartung — Richtwert nach Überschlag: Annahme 250,
  Schranke 512. `_MAX_RESPONSE_TOKENS` bleibt eine **Sicherheits**schranke: eine abgeschnittene
  Antwort ist kein JSON und landet auf dem strukturell harten Pfad, nie bei einem teilweise
  geparsten Datensatz. Die Zeichengrenze aus S2 und diese Schranke hängen aneinander — wer die eine
  hebt, leitet die andere neu her.

### Die geweitete Kandidatenauswahl

- **S6** Das Übersprungen-Kriterium ist **zusammengesetzt**: Cloud-Kopfzeile **und**
  Albumtauglichkeitszeile. Jede Lockerung auf nur eines der beiden schickt fertig bewertete Fotos
  erneut an den Anbieter — Kosten und wiederholte Datenexposition. Es steht an den drei im
  Architekturteil benannten Stellen und ändert sich an allen dreien in derselben PR. Der Status in
  `api/photos.py` macht zugleich sichtbar, wenn ein Foto seine Stufe wiederholt unbrauchbar liefert
  (S1) und deshalb bei jedem Lauf erneut gesendet wird: es meldet dann nicht `RESULT`, sondern
  bleibt als offener Kandidat erkennbar.
- **S7** Die Schätzung zählt dieselbe Menge, die der Lauf sendet — geprüft als **Mengengleichheit**
  zwischen beiden Funktionen über denselben Datenbestand, nicht als zwei getrennt hingeschriebene
  Erwartungswerte. Die Zählung negiert ein `exists()`; aus zwei Bedingungen wird per De Morgan eine
  Disjunktion, und eine falsch geklammerte Negation zählt still eine andere Menge. Eine Schätzung,
  die eine andere Menge zählt als der Lauf sendet, ist eine falsche Grundlage für die Freigabe
  einer kostenpflichtigen Aktion.
- **S8** Das lokale Ausschuss-Gate bleibt unberührt und begrenzt weiterhin, welche Fotos den
  Homeserver überhaupt erreichen dürfen: `join(PhotoScore)` plus
  `PhotoScore.suggested_status.is_(None)` bleiben in **derselben** Anweisung wie der Skip-Term
  ausgeschrieben, die Weitung fasst ausschließlich den zweiten Konjunktionsteil an. Untersagte
  Alternative: die Auswahl auf einen Outer Join oder eine vorgeschaltete Auflösung umzubauen, in
  der das Gate zu einem nachgelagerten Filter über einer bereits gebildeten Menge wird.
- **S9** Die Weitung schickt den gesamten bereits klassifizierten Bestand einmalig erneut an den
  Anbieter. Getragen wird das von den bestehenden Schranken und keiner weiteren: die Freigabe steht
  auf `False`, solange sie niemand setzt, und die Vorab-Kostenschätzung benutzt dieselbe
  Auswahlfunktion und zeigt den Sprung deshalb zwangsläufig an, bevor der Lauf startet. Es entsteht
  **keine** zusätzliche Deckelung und keine zweite Bestätigung.

### Die Einwilligung

- **S10** Es gibt keinen Weg zu einer Cloud-Bewertung ohne erteilte Freigabe. Das Gate bleibt
  `use_cloud and project.cloud_vision_detection_enabled` an beiden bestehenden Stellen — der
  Auslöse-Endpunkt antwortet `400`, und der Lauf baut bei fehlender Freigabe **gar keinen Client**.
  Die laufbezogene Checkbox kann eine fehlende Freigabe nie ersetzen. Die Albumtauglichkeit hängt
  am bestehenden Aufruf und bekommt keinen eigenen Auslöser, keinen eigenen Teilschritt und keinen
  Weg über die Sehenswürdigkeits-Erkennung.
- **S11** Die Album-Ansicht **führt zur** Freigabe hin und legt den Schalter nicht selbst um:
  eingewilligt wird ausschließlich dort, wo Anbieter und geschätzte Kosten daneben stehen. Sonst
  gäbe es zwei Orte, an denen die Konsequenz der Freigabe vollständig stehen muss, und einer davon
  läuft mit der Zeit vom anderen weg.

### Oberfläche und Löschpfad

- **S12** `reason` wird ausschließlich als regulärer React-Textknoten gerendert — nie über
  `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie als Markdown oder Rich Text, und er
  fließt in kein `href`, `src` oder `style`. Die Zusage allein reicht nicht; es gibt dafür ein
  durchgesetztes Muster im Bestand (`CloudVisionStatusList.test.tsx`, `MotifStrengthList.test.tsx`)
  und **zwei** Testfälle sind Pflicht: ein Markup-Payload erscheint als Text und materialisiert
  kein Element, und ein `javascript:`-Payload erzeugt weder Anker noch `img` mit diesem Wert. Die
  Begründung ist erkennbar als Aussage des Modells auszuweisen, nicht als Aussage von PhotoSort:
  sie stammt aus einem Bild, das Text enthalten kann. Sie geht in keinen Dateinamen, keinen Pfad,
  keinen Header und in keine Schreiboperation nach OpenCloud.
- **S13** `photo_album_suitability` wird in `project_deletion.py` aufgenommen, in derselben PR, die
  die Tabelle anlegt. Die Position folgt der per Test erzwungenen Ordnung
  `reversed(Base.metadata.sorted_tables)` — „vor `photos`" beschreibt das Ergebnis, ist aber keine
  hinreichende Vorgabe. Sonst überleben Aussagen über die Bildgüte gelöschter Familienfotos die
  Projektlöschung. Die Vollständigkeit fängt
  `test_project_deletion.py::test_delete_projects_covers_every_table_reachable_from_projects` von
  selbst; dieser Wächtertest wird nicht angefasst, um ihn grün zu bekommen.
- **S14** Entsteht für die Albumtauglichkeit ein neuer `APIRouter`, trägt er den Torwächter als
  Router-Dependency **und** wird in die handgepflegte Liste in
  `tests/test_auth_guard.py::_protected_router_operations` eingetragen. Ein dort fehlender Eintrag
  lässt einen später ergänzten zweiten Endpunkt desselben Routers von keinem
  Vollständigkeitstest erfasst.

## Entscheidungen

- **Skala:** fünf Stufen mit Ankertexten im Prompt statt einer stufenlosen Zahl. Nur ein fester
  Stufenabstand trägt die Ordnungszusage („nicht überstimmbar") beweisbar. Von Daniel bestätigt.
- **Rechenvorschrift:** Korrekturband `Q = clamp(M + 0,1·(2L−1), 0, 1)` statt „Modellwert als Deckel,
  lokal nur abwertend". Beide erfüllen „Modell führt"; das Korrekturband nutzt die volle Skala, statt
  jedes Foto unter seiner Modellstufe zu halten. Von Daniel bestätigt.
- **Foto ohne Modellurteil** (Cloud freigegeben, Einzelaufruf fehlgeschlagen): kein Qualitätswert
  (`NULL`), nicht im Entwurf, bleibt im Vorrat, nächster Lauf holt es nach.
- **Ort der Begründung:** auf der Kuratierungskachel, auf zwei Zeilen gekürzt, voller Text im DOM und
  im Popover. Das Akzeptanzkriterium sagt „sichtbar", nicht „abrufbar". Von Daniel bestätigt.
- **Stufenbeschriftungen:** „Wenig / Bedingt / Gut albumtauglich" statt „Einfache / Gute / Hohe
  Bildqualität". Eine Vokabel über Datenmodell, API und Oberfläche. Von Daniel bestätigt.
- **Der Altbestand wird nicht behandelt.** Die Migration ist eine reine Strukturänderung ohne
  Backfill und ohne Rücksetzung: Daniel löscht die Projekte nach der Umsetzung und legt sie neu an,
  womit alles neu berechnet und neu an den Anbieter geschickt wird. Eine Datenmanipulation in der
  Migration wäre Arbeit an einem Bestand, den es danach nicht mehr gibt.
- **Nachbewertung ohne zusätzliche Bremse:** Die geweitete Kandidatenauswahl schickt den bereits
  klassifizierten Bestand einmalig erneut an den Anbieter. Getragen wird das von der Cloud-Freigabe
  (steht auf `False`, solange niemand sie setzt) und der Vorab-Kostenschätzung, die dieselbe Menge
  zählt und den Sprung vor dem Lauf anzeigt. Keine Obergrenze je Lauf, keine zweite Bestätigung.
  Von Daniel bestätigt.
- **`content_landscape` gehört weder zu Qualität noch zu den Inhaltssignalen** und geht nicht in den
  Qualitätswert ein; als Kriterium bleibt es unverändert bestehen.
- **Das Skip-Kriterium steht an drei Codestellen, nicht an einer.** Die Annahme, die Kostenschätzung
  benutze dieselbe Funktion und folge automatisch, ist am Bestand widerlegt worden:
  `_count_remote_category_candidates` ist eine bewusst duplizierte Query. Alle drei Stellen ändern
  sich in derselben PR.
- **Die Feinlabel-Zeilen eines Fotos werden vor dem Neuschreiben gelöscht** (`worker.py`,
  `run_remote_category_classification`). Das ist die zwingende Folge der Nachbewertung und bei der
  Umsetzung aufgefallen: Die geweitete Auswahl schickt bereits klassifizierte Fotos erneut, der
  zweite Einfügeversuch desselben Labels verletzte `UniqueConstraint(photo_id, fine_label_id)`, und
  die `IntegrityError` rollte den **gesamten** Lauf zurück. Die Zeilen der vorherigen Antwort fallen
  damit vollständig — dieselbe Regel wie beim Stärkevektor.
- **`provider` in `photo_album_suitability` ist `NOT NULL` und ohne Default:** die Zeile entsteht
  ausschließlich aus einer Cloud-Antwort, ihr Anbieter ist damit immer bekannt.
- **ADR 0067 muss nicht geändert werden:** sie ist bereits durch ADR 0091 abgelöst, und dort ist die
  Zusage „Modellzahl steuert die Auswahl nicht" für Motivstärken bewusst aufgegeben. ADR 0091s
  tragende Grenze (Stärken nur innerhalb eines Motivs vergleichen) bleibt unberührt, weil die
  Albumtauglichkeit keine Motivstärke ist.
- Alle vier Konsultationen des `spec-writer`-Ablaufs sind gelaufen; keine wurde übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Motive selbst (Story 3), Auswahl mit Richtwert und Mischung (Story 5), Album-Entwurf je Nutzer
  (Story 6), aus Feedback justierte Gewichte (Story 8).
- Der Vergleich mit spezialisierten Qualitäts- und Ästhetikmodellen — eine eigene Recherche-Story
  nach dem Muster von #420: erst messen, dann über eine Anbindung entscheiden.
- Kalibrierung der Schwellen und Gewichte gegen einen Fotokorpus.
- Motivabhängige Gewichte: strukturell möglich (beide Funktionen nehmen die Gewichtstabelle als
  Parameter), werden hier aber nicht festgelegt.
