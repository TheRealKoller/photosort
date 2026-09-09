# 0299 - Kategorie-Konfidenz: Selbsteinschätzung des Modells anzeigen und auswerten

**Status:** Accepted
**Erstellt:** 2026-09-09
**Bezug:** [GitHub-Issue #299](https://github.com/TheRealKoller/photosort/issues/299) (Refinement vor dieser Spec-Erstellung abgeschlossen, Story-Inhalt unverändert übernommen und auf Testbarkeit geschärft)

## Ziel

Beim Kuratieren ist heute nicht erkennbar, wie belastbar eine automatisch vergebene Kategorie ist. Ein manueller Override ist zwar möglich, aber es fehlt jeder Hinweis darauf, *wo* er nötig wäre — man müsste jedes Foto einzeln nachprüfen. Eine Sicherheitsangabe je erkannter Kategorie schließt diese Lücke: sie macht wacklige Zuordnungen gezielt auffindbar, erklärt am einzelnen Foto, wie die Kategorie zustande kam, und erlaubt über alle Fotos hinweg eine Einschätzung, wie gut die Erkennung insgesamt arbeitet.

Die Angabe ist die **Selbsteinschätzung des Bilderkennungsmodells**, keine gemessene Trefferquote. Diese Quelle wurde bewusst gewählt; die Alternative, Unsicherheit aus bereits vorhandenen Signalen abzuleiten (Übereinstimmung lokaler und entfernter Erkennung, Anzahl der Kandidaten), wurde geprüft und verworfen. Die frühere Entscheidung, Konfidenzen ersatzlos zu streichen (ADR [`0049`](../decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md), Abschnitt 5), war damit begründet, dass eine persistierte Zahl *ohne Verwendung* irreführender Ballast wäre — diese Spec schafft genau die fehlende Verwendung, und zwar drei davon: Auffinden, Erklären, Auswerten.

## User Story

Als Nutzer von PhotoSort möchte ich neben jeder erkannten Kategorie sehen, wie sicher sich das Bilderkennungsmodell war, damit ich unsichere Zuordnungen gezielt finden und korrigieren kann, am einzelnen Foto nachvollziehe, wie die Kategorie zustande kam, und die Erkennungsqualität insgesamt beurteilen kann.

## Akzeptanzkriterien

Die Kriterien der Story sind bei der Spec-Erstellung auf Prüfbarkeit geschärft worden (`test-engineer`); Kriterium 12 ist dabei neu hinzugekommen, um die Abgrenzung selbst prüfbar zu machen.

**Erhebung und Persistenz**

- [ ] 1. Liefert die Modellantwort zu einem Kandidaten eine Angabe vom Typ `int`/`float` (nicht `bool`) im Band `0.0 <= v <= 1.0`, wird sie mit der Klassifizierungszeile des Fotos persistiert und ist nach erneutem Laden unverändert vorhanden. Ein Kandidat ohne oder mit ungültiger Angabe bleibt als Kategorie gültig und wird ohne Zahl gespeichert.
- [ ] 8. Ein ausschließlich lokal erkannter Kandidat liefert in der API `null`, nie `0.0`, und zeigt in der Oberfläche weder Zahl noch Platzhalter. Ein Schlüssel, der lokal **und** remote erkannt wurde, erscheint weiterhin als lokal gekennzeichneter Kandidat, behält aber die Modellzahl — die Zahl folgt dem Schlüssel, nicht der Herkunftskennzeichnung.
- [ ] 9. Es gibt keinen Backfill und keinen Spalten-Default: bestehende Klassifizierungszeilen behalten dauerhaft `NULL` und zeigen keine Angabe. Auch ein erneuter Klassifizierungslauf ändert das nicht, weil der Worker jedes Foto mit vorhandener Klassifizierungszeile überspringt (Kostenschutz). Eine erzwungene Neu-Klassifizierung ist ausdrücklich nicht Teil dieser Spec.
- [ ] 10. Fehlt die Angabe oder ist sie ungültig (`bool`, `NaN`, `±Infinity`, außerhalb `[0,1]`, falscher Typ), gilt: der Kandidat und die aufgelöste Kategorie bleiben unverändert gültig, das Foto wird nicht übersprungen, der Lauf scheitert nicht, und je verworfenem Wert entsteht **genau eine** WARNING-Zeile. Ungültige Werte werden **verworfen, nicht auf das Band geklemmt**.

**Anzeige**

- [ ] 2. Darstellung als kaufmännisch gerundete ganze Prozentzahl im Format `92%` (ohne Leerzeichen vor dem Prozentzeichen, konsistent mit den bestehenden Kriterienzeilen). `0.0` → `0%`, `1.0` → `100%`. Ein kleiner Wert ungleich null, der auf 0 rundet, wird als `0%` gezeigt — **keine** `< 1 %`-Sonderregel (anders als bei Geldbeträgen).
- [ ] 3. In der Foto-Detailansicht steht die Zahl in der Kandidatenliste an jedem Kandidaten, für den eine Modellangabe vorliegt — und ebenso in der einzeiligen Kategorie-Anzeige, wenn höchstens ein Kandidat existiert. Kandidaten ohne Angabe zeigen an dieser Stelle nichts.
- [ ] 4. In Grid und Kuratierung erscheint die Zahl über dieselbe geteilte Bewertungsdetails-Komponente wie in der Detailansicht. Der Kategorie-Chip in der **Gruppenüberschrift** der Kuratierung bekommt ausdrücklich **keine** Zahl: er benennt eine Partition, nicht ein Foto.
- [ ] 7. An beiden Anzeigeorten (Bewertungsdetails und Statistikblock) steht ein fester, im Code als benannte Konstante geführter Hinweis, der die Zahl als Selbsteinschätzung des Modells ausweist. Die Formulierungen „Trefferquote", „Genauigkeit" und „korrekt" kommen dort nicht vor.
- [ ] 11. Ein manueller Kategorie-Override lässt beide neuen Spalten der Klassifizierungszeile unverändert; die am Kandidaten angezeigte Zahl bleibt bei ihrem Schlüssel.

**Auffinden und Auswerten**

- [ ] 5. Ein standardmäßig ausgeschalteter Filterschalter in der Kuratierung zeigt nur noch Fotos mit einer Modellsicherheit **echt unter 60 %** (`0.6` selbst gilt nicht als niedrig). Fotos ohne Angabe fallen bei aktivem Filter heraus. Der Filter arbeitet auf den bereits geladenen Daten und löst keine neue Anfrage aus; die Gruppierung nach Tag/Cluster/Kategorie bleibt unverändert; eine durch den Filter leer gewordene Gruppe bleibt mit einem eigenen, vom Erschöpfungshinweis unterscheidbaren Text sichtbar; Ausschalten stellt exakt den vorherigen Sichtstand wieder her.
- [ ] 6. Die Statistikseite zeigt je **Modell**-Kategorie die Anzahl der Fotos mit Angabe und das arithmetische Mittel ihrer Sicherheiten, dazu die Bezugsbasis (Fotos mit / ohne Angabe). Eine Kategorie ohne ein einziges Foto mit Angabe zeigt **keine** Zahl, nicht `0 %`. Gruppiert wird über die vom Modell genannte Kategorie, ausdrücklich **nicht** über die wirksame Kategorie der Rangfolge — ein übersteuertes Foto zählt hier weiterhin zur Modell-Kategorie.

**Abgrenzung, prüfbar gemacht**

- [ ] 12. Die Zahl beeinflusst keine Auswahl: `resolve_category` behält ihre Signatur mit genau einem Parameter, und zwei Läufe mit identischen Kandidaten, aber unterschiedlichen Konfidenzen erzeugen identische Kategorie und identische Rangfolge.

## Datenmodell-Bezug

Zwei additive, nullable Spalten an der bestehenden Entität **PhotoCategoryClassification** (`photo_category_classifications`), siehe [`docs/architecture.md`](../../docs/architecture.md):

| Spalte | Typ | Bedeutung |
|---|---|---|
| `detected_category_confidences` | `SQLJSON`, nullable | Abbildung `category_key` → Konfidenz, ausschließlich Schlüssel aus `detected_categories`. Kann `{}` sein (Modell hat keine brauchbare Zahl geliefert). |
| `category_confidence` | `Float`, nullable | Die Konfidenz zur aufgelösten Kategorie **dieser Zeile**, also `detected_category_confidences.get(category_key)`. |

Eine **Abbildung**, kein positionsparalleles Array und keine Paarliste: der Wert hängt am Schlüssel und überlebt jede Umsortierung. Der Skalar ist bewusst redundant — er existiert, weil die Statistik-Aggregation in SQL laufen muss (`AVG` über einen aus JSON extrahierten Wert ist in SQLite und PostgreSQL unterschiedlich zu schreiben, und alle Klassifizierungszeilen eines Projekts nach Python zu laden verträgt sich nicht mit der Größenannahme „mehrere tausend Fotos"). Tragbar, weil es genau **eine** schreibende Stelle gibt; die Invariante `category_confidence == detected_category_confidences.get(category_key)` wird getestet.

`NULL` heißt „nicht erhoben", `0.0` hieße „das Modell war sich zu 0 % sicher" — deshalb **kein `server_default`, kein Backfill**, exakt das Muster von ADR [`0051`](../decisions/0051-ist-kostenerfassung-remote-laeufe.md). Damit erfüllt sich Akzeptanzkriterium 9 durch die Spaltenform selbst statt durch eine Sonderbehandlung im Lesepfad.

Nicht betroffen: `photo_fine_labels`. Die mit Spec 0289 entfernte Spalte `photo_fine_labels.confidence` war eine Konfidenz je **Feinlabel** und bleibt entfallen — hier ist nichts zu revertieren.

## Architektur / Umsetzung

Neue ADR [`0067`](../decisions/0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md) (Accepted). Sie löst ADR [`0049`](../decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) in genau zwei benannten Punkten ab (Abschnitt 5, Aufzählungspunkt „Konfidenzen entfallen ersatzlos"; Abschnitt 8, „`score` entfällt dort ersatzlos … irreführend halb gefüllt"); ADR 0049 trägt dafür den Kopfvermerk **Teilweise abgelöst** und bleibt im Übrigen unverändert `Accepted`.

**0. Die tragende Grenze: die Zahl entscheidet nichts.** `categories.py::resolve_category` bleibt buchstäblich unverändert — ein Parameter, allein `precedence`. Kein Codepfad, der eine Kategorie *bestimmt*, liest die neuen Felder; das gilt ausdrücklich auch für `worker.py::run_criterion_scoring`, das die Remote-Kandidaten heute über `select(PhotoCategoryClassification.photo_id, .detected_categories)` einliest und dabei die neue Spalte nicht anfassen darf. Der Grund steht in ADR [`0047`](../decisions/0047-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md): „höchster Wert gewinnt" ist in diesem Produkt bereits nachweislich gescheitert, weil Werte unterschiedlicher Skalen verglichen wurden und die unspezifischere Zahl regelmäßig gewann.

**1. Antwortschema und Parser (`remote_classification.py`) — erweitert, nicht ersetzt.** Der Kategorien-Eintrag wird vom nackten Schlüssel zum Objekt:

```json
{"categories": [{"key": "menschen", "confidence": 0.92}, {"key": "tier", "confidence": 0.41}],
 "fine_labels": ["Geburtstag"]}
```

`build_classification_prompt()` (`categories.py`) beschreibt die neue Form und fordert die Selbsteinschätzung ausdrücklich als Zahl zwischen 0 und 1 an; der Prompt entsteht weiterhin ausschließlich aus `CATEGORY_REGISTRY`, nie aus Datenbankinhalten.

`_categories_from_json` wird zu **einem** Durchlauf, der ein Paar liefert (`tuple[str, ...]`, `Mapping[str, float]`) — nicht zwei getrennte Funktionen, sonst könnten Dedup und Kappung auseinanderlaufen. Regeln, in dieser Reihenfolge:

- Ein Eintrag darf ein `dict` mit `key` **oder** weiterhin ein blanker `str` sein. Der String-Fall bleibt gültig und liefert eine Kategorie **ohne** Zahl — ein Modell, das die neue Anweisung ignoriert, verschlechtert die Anzeige, nicht die Klassifizierung. Alles andere ist ein verworfener Kategoriewert wie bisher (`_log_discarded_category`).
- Schlüsselvalidierung, Dedup („Erstnennung gewinnt", auch für die Konfidenz) und Kappung auf `MAX_REMOTE_CATEGORIES_PER_PHOTO` unverändert. **Die Konfidenz-Abbildung wird erst nach der Kappung auf die verbliebenen Schlüssel gefiltert** — sie darf keinen Schlüssel enthalten, der nicht in `categories` steht. Invariante: `set(detected_category_confidences) <= set(detected_categories)`.
- Konfidenz übernommen nur, wenn der Wert `int`/`float` ist **und** `0.0 <= wert <= 1.0`. `isinstance(raw, bool)` explizit ausschließen (`True` wäre sonst `1.0` = „100 % sicher"), und die Bereichsprüfung so schreiben, dass `NaN`/`Infinity` durchfallen (Pythons `json` parst beide standardmäßig; `0.0 <= nan <= 1.0` ist `False` → verworfen).
- **Verworfen wird, nicht geklemmt** — bewusst anders als `landmark.py::_landmark_detection_from_json`, das auf `[0, 1]` klemmt. `1.4 → 1.0` erzeugte aus einer kaputten Antwort die stärkste Aussage, die das Produkt kennt. Siehe dazu den Abschnitt Security: das ist hier eine Verfügbarkeitszusage, keine Kosmetik.
- Ein verworfener Konfidenzwert: eine `WARNING`-Zeile je Vorkommen (neue Schwesterfunktion `_log_discarded_confidence`) mit `photo_id` und einem **festen Grund-Token** (`nicht_numerisch` / `ausserhalb_intervall`) — **kein Rohwert**, nie die vollständige Antwort, nie der Kategorie-Key, nie Bilddaten. Begründung im Security-Abschnitt.

`RemoteClassification` bekommt ein drittes Feld: `category_confidences: Mapping[str, float] = MappingProxyType({})` — `MappingProxyType` statt `field(default_factory=dict)`, damit die Zusage von `frozen=True` auch für den Inhalt hält, wie bei den bestehenden Tupel-Feldern.

**2. Datenmodell und Migration.** Siehe Abschnitt „Datenmodell-Bezug". Die Migration ist rein additiv: `op.batch_alter_table("photo_category_classifications")` + zwei `add_column`, `down_revision` = der zum Umsetzungszeitpunkt aktuelle Head, Slug `kategorie_konfidenz`. `downgrade()` ist verlustbehaftet, aber schema-vollständig umkehrbar.

**3. Schreibpfad (`worker.py::run_remote_category_classification`).** Der bestehende `PhotoCategoryClassification(...)`-Konstruktor bekommt zwei Argumente; `category_key = resolve_category(classification.categories)` bleibt unverändert die Quelle des Skalar-Lookups. Der Skalar entsteht per **Lookup aus der bereits gebauten Abbildung**, nicht durch eine zweite Berechnung — eine zweite Berechnung driftet. Best-effort-Semantik unangetastet: eine fehlende oder unplausible Konfidenz ist **nie** ein Grund, ein Foto zu überspringen oder den Lauf scheitern zu lassen.

**4. API-Lesepfad (`api/photos.py`).**

- `CategoryCandidateOut.confidence: float | None = None`. **Die Zahl folgt dem Schlüssel, nicht der `origin`-Kennzeichnung** — `_category_candidates_out` fasst einen lokal *und* remote erkannten Schlüssel heute zu `origin="local"` zusammen; die Modellzahl gehört trotzdem an diese Zeile, denn es gibt eine Modellaussage zu diesem Schlüssel. Ein rein lokaler Kandidat bekommt `None`, nie `0.0`.
- `PhotoOut.category_confidence: float | None` — die Konfidenz zu `remote_category`. Eigenes Feld statt clientseitiger Ableitung aus der Kandidatenliste: `remote_category` kann `nicht_erkannt` sein und steht dann gar nicht in `detected_categories`. Dieses Feld trägt den Kuratierungsfilter.
- Nichts ändert sich an `set_category_override`/`delete_category_override`: ein Override lebt in `photo_scores.category_override` und berührt die Klassifizierungszeile nicht. Akzeptanzkriterium 11 ist damit eine Eigenschaft der bestehenden Trennung — es braucht keinen Code, nur einen Test, der sie festhält.

**5. Statistik (`api/stats.py`): eigener Block, andere Grundmenge als der vorhandene Kategorien-Block.** Neu `CategoryConfidenceEntryOut` (`category_key`, `display_name`, `photo_count`, `average_confidence: float | None`) und `CategoryConfidenceOut` (`entries` über alle Registry-Keys in Anzeigereihenfolge, `photos_with_confidence`, `photos_without_confidence`) an `ProjectStatsOut.category_confidence`. Aggregiert wird in **einer** GROUP-BY-Abfrage über `photo_category_classifications`, projektskopiert über `_photos_of_project(project_id)` (die Tabelle hat keine eigene `project_id`).

Gruppiert wird über die **Modell**-Kategorie, ausdrücklich nicht über `photo_rankings.category_key` wie `_categories_out`. Der vorhandene Block beantwortet „wie ist mein Bestand verteilt" und braucht dafür die wirksame Kategorie (lokal + remote + Override); dieser Block beantwortet „wie gut arbeitet die Erkennung" und braucht die Aussage des Modells über sich selbst. Beides in eine Zeile zu mischen ergäbe zwei richtige Zahlen mit einer falschen Aussage dazwischen. Deshalb weist der Block seine Basis mit aus, statt einen Mittelwert ohne Bezugsmenge zu zeigen. `average_confidence` ist `None` bei `photo_count == 0` — nie `0.0`; `func.avg` defensiv nach `float` casten.

**Kein Schwellwert im Backend.** Weder API noch Datenbank kennen einen Begriff von „unsicher" — die Statistik ist mit Mittelwert und Basisgrößen schwellenfrei aussagekräftig, und eine Schwelle, die Backend und Frontend beide bräuchten, müsste gespiegelt oder über ein neues API-Feld transportiert werden.

**6. Kuratierung: clientseitiger Filter, keine neuen Query-Parameter.** `CurateCategoriesPage` lädt über `top_n_per_category` bereits den vollständigen Pool ohne Paginierung und gruppiert clientseitig Tag → Cluster → Kategorie. Ein Filterschalter „Nur unsichere Zuordnungen" filtert `items`, **bevor** `groupByClusterAndCategory` läuft; Prädikat: `category_confidence !== null && category_confidence < LOW_CONFIDENCE_THRESHOLD` (`0.6`, exportierte Konstante im Seitenmodul, neben `toggleDayCollapse`/`countPhotosInDay` als reine, direkt testbare Hilfsfunktion). Fotos ohne Zahl fallen bei aktivem Filter heraus — sie sind keine „unsichere Zuordnung", sondern eine unbekannte (Entscheidung Daniels, siehe „Entscheidungen").

Zwei Fallen, die der Filter nicht auslösen darf:

- Die Merkliste gesehener Partitionen („erschöpfter Pool") wird weiterhin aus den **ungefilterten** `items` gespeist, sonst verschwänden Partitionen beim Einschalten des Filters dauerhaft.
- Bei aktivem Filter braucht eine leer gefilterte Partition einen eigenen Hinweistext, der sie von einer tatsächlich erschöpften unterscheidet.

Bewusst **keine** serverseitige Sortierung nach Konfidenz: die Kuratierung ordnet innerhalb einer Partition nach Rangposition („bestes Foto zuerst"), und eine Umsortierung nähme dieser Ansicht genau die Aussage, für die es sie gibt. Der Filterzustand lebt in `useState` (wie `collapsedDayKeys`), nicht in den Suchparametern — dort steht nur, was das Backend als Query-Parameter sieht.

**7. Anzeige: eine Stelle, drei Ansichten.** `CriterionDetailsList` wird von Detailseite, Grid **und** Kuratierung geteilt (über `CriterionDetailsPopover`) — die Zahl dort einzubauen erfüllt die Akzeptanzkriterien 3 und 4 in einem Zug, ohne dass irgendwo eine zweite Formatierungslogik entsteht. Beide Zweige sind zu bedienen: die Kandidatenliste (`showCandidateGroup`) und die einzeilige „Kategorie"-Anzeige (`candidateRows.length <= 1`). Fehlt die Zahl, wird **kein** Platzhalter gerendert — die Zeile sieht aus wie heute.

`formatCriterionPercent` (heute privat in `CriterionDetailsList.tsx`, `Math.round(value * 100)` + `%`, ohne Nachkommastelle) wandert nach `utils/formatStats.ts` und wird exportiert; Kandidatenliste und Statistikblock benutzen dieselbe Funktion. Bewusst **nicht** das dort vorhandene `formatPercent` (eine Nachkommastelle) — Akzeptanzkriterium 2 verlangt die Darstellung der Qualitätsmerkmale, und der Statistikblock folgt hier der Kategorie-Anzeige statt der Statistik-Hausformatierung.

**8. Demo-Daten (`demo_state.py`).** Der `PhotoCategoryClassification(...)`-Aufbau bekommt deterministische Konfidenzen über das vorhandene `_deterministic_unit_value`-Muster — mit mindestens einem Foto **ohne** Zahl und mindestens einem unterhalb der Filterschwelle, damit sowohl die Lückendarstellung als auch der Kuratierungsfilter im Browser sichtbar sind.

**Betroffene Dateien / Umsetzungsreihenfolge (TDD).** Backend zuerst — Datenpfad vor Anzeige, geparste Form vor persistierter Form:

1. `backend/src/photosort/categories.py` — `build_classification_prompt()`: neues Antwortschema + Anweisung zur Selbsteinschätzung. `resolve_category` bleibt unangetastet (Invariantentest).
2. `backend/src/photosort/remote_classification.py` — `RemoteClassification.category_confidences`, Ein-Durchlauf-Parser mit Paar-Rückgabe, `_log_discarded_confidence`.
3. `backend/src/photosort/models.py` + neue Alembic-Revision — die zwei nullable Spalten; Migrationstest.
4. `backend/src/photosort/worker.py` — Schreibstelle; Nachweis, dass der Kandidaten-Lesepfad unverändert bleibt.
5. `backend/src/photosort/api/photos.py` — `CategoryCandidateOut.confidence`, `PhotoOut.category_confidence`, `_category_candidates_out`.
6. `backend/src/photosort/api/stats.py` — Aggregatabfrage + `CategoryConfidenceOut`-Block.
7. `backend/src/photosort/demo_state.py` — deterministische Konfidenzen inkl. Lückenfall.
8. `backend/src/photosort/pricing.py` — `ASSUMED_USAGE_BY_PROVIDER` gegen die neue Antwortlänge nachrechnen und die Herleitung im Kommentar fortschreiben, auch wenn der Wert unverändert bleibt.

Frontend:

9. `frontend/src/api/types.ts` — `confidence`, `category_confidence`, Statistik-Typen.
10. `frontend/src/utils/formatStats.ts` — `formatCriterionPercent` hierher (+ Zeilen in `formatStats.test.ts`), Import in `CriterionDetailsList.tsx`.
11. `frontend/src/components/CriterionDetailsList.tsx` — Zahl in beiden Zweigen, kein Platzhalter bei `null`.
12. `frontend/src/pages/CurateCategoriesPage.tsx` — Filterschalter + reine Filterfunktion + Konstante; Merkliste weiter aus den ungefilterten `items`.
13. `frontend/src/pages/ProjectStatsPage.tsx` — neuer Block mit ausgewiesener Basis.

`docs/architecture.md` wird im selben PR ergänzt: die zwei Spalten beim Eintrag **PhotoCategoryClassification** unter „Datenmodell", das neue Statistikfeld unter „Komponenten", Verweis auf ADR 0067 und der Teil-Vermerk an ADR 0049. Nicht betroffen: `docs/setup.md` (keine neue Umgebungsvariable, kein neuer Setup-Schritt).

## UI/UX

Sichtbare Oberfläche: ja, an vier Stellen. Grundlage ist das Design-System [`0004`](../architecture/0004-design-system.md) (Dark Utility Register); keine neuen UI-Bibliotheken und keine neuen Abhängigkeiten.

**Bewertungsdetails (Detailseite, Grid, Kuratierung — geteilte `CriterionDetailsList`).** Die Prozentzahl steht **rechts neben dem Kategorienamen** in derselben Zeile, als sekundärer Text in `--text-muted`. In der Kandidatenliste trägt jeder Kandidat seine eigene Zahl in derselben Position, neben Name und Herkunfts-Badge; in der einzeiligen Kategorie-Anzeige steht sie zum angezeigten Schlüssel. Fehlt die Zahl, rendert die Zeile nur den Kategorienamen — **kein** Platzhalter, kein Strich, kein `0%`; die Lücke *ist* das korrekte Signal.

Die Schwelle 60 % wird **nicht** visuell kodiert (keine Farbe, kein Icon, keine Warnfarbe). Eine niedrige Selbsteinschätzung ist kein Fehler, und eine rote Markierung suggerierte eine Bewertung, die die Zahl nicht hergibt; die gezielte Suche leistet der Filter.

**Kennzeichnung als Selbsteinschätzung (Akzeptanzkriterium 7).** An beiden Anzeigeorten steht ein fester, im Code als benannte Konstante geführter Hinweis, erreichbar über einen kleinen Info-Trigger (`aria-label="Erklärung zur Konfidenz"`). Wortlaut:

> Modell-Selbsteinschätzung — die Angabe stammt vom Erkennungsmodell selbst und ist keine gemessene Trefferquote. Ein hoher Wert heißt, dass das Modell sich sicher war; er schließt einen Irrtum nicht aus.

Die Wörter „Trefferquote", „Genauigkeit" und „korrekt" kommen in der Anzeige sonst nicht vor — als Negativ-Assertion prüfbar.

**Kuratierung.** Ein Filterschalter „Nur unsichere Zuordnungen" in der bestehenden Filterleiste, standardmäßig aus, als natives `<input type="checkbox">` mit Label (Einmal-Entscheidung, kein Switch), im bestehenden `gap`-Raster. Eine durch den Filter leer gewordene Gruppe bleibt sichtbar und trägt einen eigenen Hinweistext, der sie vom Erschöpfungshinweis unterscheidet („Keine Fotos mit einer Sicherheit unter 60 % in dieser Gruppe."). Ausschalten stellt exakt den vorherigen Sichtstand wieder her. Der Kategorie-Chip der Gruppenüberschrift bekommt keine Zahl.

**Statistikseite.** Neuer Abschnitt „Konfidenz der Kategorie-Erkennung" nach dem bestehenden Kategorienverteilungs-Block, in der Anzeigereihenfolge der Registry (nicht alphabetisch — konsistent zum vorhandenen Kategorienblock). Je Zeile: Kategoriename, der Mittelwert als Hauptwert in `--text-h`, darunter kleingedruckt die Basis in `--text-muted` („42 Fotos mit Angabe, 8 ohne"). Eine Kategorie ohne eine einzige Angabe zeigt keinen Prozentwert; die Basiszeile erklärt es sachlich. Der Mittelwert ohne ausgewiesene Basis wäre eine Zahl ohne Aussage — die Basis ist deshalb Pflichtbestandteil, nicht Beiwerk.

**Zustände.** Laden über die bestehenden Skeleton-Platzhalter, keine neuen Ladezustände. Fehlende Zahl: leer, siehe oben. Leerer Filter: eigener Text je Gruppe. Leere Statistik: Kategoriename ohne Wert.

**Barrierefreiheit.** Die Prozentzahl ist eigener Textknoten neben dem Kategorienamen und wird als „Landschaft 78 Prozent" vorgelesen; begleitende Icons tragen `aria-hidden="true"`. `--text-muted` erreicht gegen alle vier Flächen mindestens 3:1 (nachgerechnet in `frontend/src/designSystem.contract.test.ts`) — die Zahl sitzt auf derselben Fläche wie der Kategoriename, es entsteht kein neuer Kontrastfall.

**Responsivität.** Der Kategoriename bleibt einzeilig, die Zahl sitzt rechts in derselben Zeile; die vier zusätzlichen Zeichen passen auch in der Grid-Kachel bei 360 px ohne Umbruch.

## Security

Sicherheitsrelevant, kein Blocker. Kein neuer externer Dienst, kein neues Secret, kein zusätzlicher Datenfluss Richtung Cloud, kein neuer Endpunkt und kein neuer Auth-Torwächter — es ist derselbe Aufruf mit einer längeren Antwort. Neu ist ausschließlich: erstmals wird ein **Zahlenwert** aus einer Modellantwort übernommen, persistiert und ausgeliefert. Alle bisherigen Übernahmen aus dieser Quelle waren Strings gegen ein geschlossenes Vokabular (`categories`) oder zeichensanierter Anzeigetext ohne Wirkung (`fine_labels`). Fünf Punkte.

1. **Die Konfidenz darf keinen Kontrollfluss steuern — Muss-Kriterium.** Die tragende Eindämmung gegen Prompt-Injection über Bildinhalte ist seit ADR 0049 „das Modell nennt Kandidaten, der Code entscheidet": `resolve_category` bildet das Ergebnis allein aus der Registry und der festen Vorrangreihenfolge, erzwingbar ist höchstens eine falsche, aber gültige Kategorie. Diese Eindämmung ist bemerkenswert exponiert, weil das Set mit `dokument_screenshot` Fotos von Texten, Bildschirmen und Schildern ausdrücklich als erwartete Eingabeklasse führt. Eine vom Modell gelieferte Zahl, die die Auswahl mitbestimmte, gäbe genau diese Entscheidung an die Antwort zurück — ein präpariertes Bild könnte dann über eine hohe Selbsteinschätzung eine Kategorie an der Vorrangreihenfolge vorbei erzwingen. Verbindlich deshalb: `resolve_category` behält seine Signatur über Schlüsseln allein; die Konfidenz geht in keine Auswahl, keine Sortierung, keine Filterung und keine Schwelle im Backend ein.

2. **Wertebereichsprüfung am Parser-Rand — Muss-Kriterium mit konkreter Ausfallfolge.** Pythons `json` parst `NaN`, `Infinity` und `-Infinity` ohne Fehler; das gilt für beide Provider-Pfade, da `cloud_vision.py` `json.loads` mit Standardeinstellungen verwendet. Die Ausgabeschicht akzeptiert diese Werte nicht: Starlette rendert Antworten mit `allow_nan=False`, ein `NaN` in einem `PhotoOut` lässt damit **die gesamte Listenantwort** mit `ValueError` scheitern, nicht nur den einen Eintrag; PostgreSQL lehnt dasselbe Literal bereits beim Schreiben der JSON-Spalte ab. Ein einziger entarteter Wert könnte also einen Job-Lauf abbrechen oder die Fotoliste eines Projekts dauerhaft auf 500 legen — verfügbarkeitswirksam, nicht nur unsauber. Die Prüfung (`int`/`float`, `bool` ausgeschlossen, `0.0 <= v <= 1.0`) schließt das vollständig und muss **vor** der Persistenz greifen, am selben Ort wie die Schlüsselvalidierung. Verworfen statt geklemmt ist hier doppelt begründet: ein geklemmtes `NaN` ist nicht definiert, und ein geklemmter Wert wäre eine Aussage, die das Modell nie getroffen hat. Eine spätere Umstellung auf Klemmen (`if v > 1.0: v = 1.0`) ließe `NaN` wieder durch, weil der Vergleich `False` ergibt.

   **Testform verbindlich vorgegeben:** als Unit-Test direkt am Parser, nicht als Integrationstest. Die Testsuite läuft auf SQLite in-memory, das die JSON-Spalte als Text hält und `NaN` verlustfrei zurückliest — der Produktionsdefekt auf PostgreSQL wäre über die Datenbankschicht nicht sichtbar.

3. **Die Schlüssel der Konfidenz-Abbildung sind ein zweiter Persistenzkanal — Muss-Kriterium.** `detected_categories` ist bewusst gegen genau eine Bedrohung gehärtet: dort landet nie die Rohliste des Modells, sonst wanderte unvalidierter Fremdtext über einen zweiten Kanal in API-Antwort und UI. Eine zweite JSON-Spalte, deren Schlüssel aus derselben Antwort stammen, eröffnet diesen Kanal erneut, wenn die Abbildung vor oder unabhängig von der Schlüsselvalidierung entsteht — der naheliegende Implementierungsfehler, weil Wert und Schlüssel in der Antwort im selben Objekt stehen. Verbindlich deshalb die Reihenfolge: validieren, deduplizieren, kappen — und **erst danach** die Abbildung auf die verbliebenen Schlüssel filtern. Die erweiterte Eingangsvalidierung bleibt fail-closed: Alles, was weder String noch Objekt mit brauchbarem `key` ist, geht durch denselben Verwerfen-Pfad wie bisher — kein neuer stiller Zweig.

4. **Logging: Grund statt Rohwert.** Für einen verworfenen *Kategorieschlüssel* trägt der Rohwert echten Diagnosewert — er zeigt ein Vokabular, das der Prompt nicht gesetzt hat. Für eine verworfene *Konfidenz* liegt der Diagnosewert dagegen fast vollständig in der Fehlerklasse: „kein Zahlentyp", „außerhalb [0,1]" sagen alles für eine Prompt-/Schemakorrektur Nötige; die konkrete `1.7` sagt nichts darüber hinaus. Die WARNING-Zeile enthält daher `photo_id` und ein festes Grund-Token (`nicht_numerisch` / `ausserhalb_intervall`), **keinen** Rohwert. Damit enthält die Zeile überhaupt keinen Fremdtext, und die Log-Injection-Frage stellt sich nicht. Zweiter, praktischer Grund: die wahrscheinlichste reale Fehlerform ist eine *systematische* Skalenverwechslung (`92` statt `0.92`) über einen ganzen Lauf — ein festes Grund-Token macht solche Läufe zählbar und greppbar, tausend verschiedene Rohwerte nicht.

5. **`_MAX_RESPONSE_TOKENS` ist eine Sicherheitsschranke, nicht nur eine Kostenschranke.** Die 256 begrenzen auch die Menge an Fremdtext, die je Foto geparst und potenziell geloggt werden kann. Die vollbesetzte neue Antwort liegt überschlägig bei 80–100 Ausgabe-Tokens gegenüber rund 50 bisher — 256 behält klare Reserve und ist **nicht anzuheben**. `pricing.py::ASSUMED_USAGE_BY_PROVIDER` mit `output_tokens=120` deckt die neue Länge weiterhin ab; die Marge schrumpft aber von rund dem Zweieinhalbfachen auf etwa das Anderthalbfache, und die Schätzung ist seit Spec 0296 die einzige verbliebene Absicherung vor der kostenpflichtigen Aktion. Die Neuherleitung ist deshalb im Kommentarblock über der Konstante nachzuziehen, auch wenn der Wert unverändert bleibt.

**Ausdrücklich geprüft und ohne Befund:** Datensichtbarkeit zwischen den beiden Nutzern unverändert (die Spalten tragen keinen `user_id`-Bezug, die Werte sind projektweit wie die übrigen Kategoriedaten; der Statistikblock ist kein personenbezogenes Aggregat). Projekt-Skopierung der Aggregation über `_photos_of_project` bleibt trotzdem Muss-Kriterium mit eigenem Test. Auth: kein neuer Endpunkt. Frontend/XSS: eine validierte Zahl ist kein Text und keine XSS-Fläche. Fehlende Konfidenz ist „keine Angabe", nie `0.0`. Secrets, Provider-Ziel, SSRF unverändert. Das dokumentierte Restrisiko „gestohlenes JWT löst einen kostenpflichtigen Lauf aus" steigt marginal in der Schadenshöhe, nicht in der Wahrscheinlichkeit — kein neuer Eintrag nötig.

Das Sicherheitskonzept [`0003`](../architecture/0003-securitykonzept.md) ist im selben Zug fortgeschrieben worden (Rückkehr der Konfidenz ohne die Eigenschaft, die sie sicherheitsrelevant machte; erste numerische Übernahme aus einer Modellantwort samt `NaN`-Fallstrick und SQLite-Blindstelle).

## Teststrategie

Das Testkonzept [`0002`](../architecture/0002-testkonzept.md) ist um zwei Sektionen fortgeschrieben worden, weil drei Punkte über diesen Branch hinausgehen: das Muster „Fremdwert mit Gültigkeitsband" gab es bisher nicht, `category_confidence` ist die **erste abgeleitete Spiegelspalte** des Datenmodells, und die SQLite-Blindstelle für `NaN` erweitert die Fehlerklasse aus `test_postgres_ddl_compatibility.py` um einen zweiten Vertreter.

**Ebenenaufteilung.** Die tragende Zusage („die Zahl entsteht korrekt, sie erfindet nichts, und sie entscheidet nichts") liegt fast vollständig auf **Unit-Ebene am Parser** und auf **Integrationsebene** an Schreibpfad und Endpunkten. **Kein neuer E2E-Spec**: es gibt keine Zusage, für die eine Layout-Engine nötig wäre.

- **Backend/Unit:** `test_remote_classification.py` (Schwerpunkt: Konfidenz-Zweig von `_categories_from_json`), `test_categories.py` (Signaturtest auf `resolve_category` per `inspect.signature`, repoweite Abwesenheits-Assertion der zwei Feldnamen in `categories.py`/`ranking.py`/Kriterien-Scoring), `test_models.py`, neu `test_migration_kategorie_konfidenz.py` (Auf- und Abwärtsrichtung, Altzeile bleibt `NULL`), `test_postgres_ddl_compatibility.py` (`FLOAT`, kein `server_default`).
- **Backend/Integration:** `test_worker_remote_category_classification.py` (Schreibpfad, Invariante über alle erzeugten Zeilen, Best-effort, Skip bei vorhandener Zeile), `test_api_photos.py`, `test_api_stats.py`, `test_api_category_override.py` (AK 11), `test_worker_criterion_scoring.py` (Paartest), `test_demo_state.py`.
- **Frontend:** `formatStats.test.ts` (inkl. Abgrenzung gegen den bestehenden Statistik-Formatierer), `CriterionDetailsList.test.tsx` (beide Zweige, `null` ohne Platzhalter, `0` als `0%`), `CurateCategoriesPage.test.tsx` (reine Filterfunktion, Konstante, Ein/Aus-Test der Merkliste, zwei unterscheidbare Leerzustände), `ProjectStatsPage.test.tsx`, sowie `null` als Basiswert in den `photo()`-Fabriken von Grid-, Detail- und Vergleichsseite.

**Edge Cases, die sonst durchrutschen:**

- `bool`: `isinstance(True, int)` ist `True` — `"confidence": true` käme ohne expliziten Ausschluss als `1.0` durch, läge **im** Gültigkeitsband und erschiene als „100 %". Je ein Fall für `true` und `false`.
- `NaN`/`Infinity`/`-Infinity` je ein Fall, und zwar mit **Roh-Textkörper** als Eingabe (`'{"categories":[{"key":"tier","confidence":NaN}]}'`), nicht mit einem per `json.dumps` erzeugten Dict.
- Bandfälle: `0.0` (gültig, **nicht** mit „fehlt" verwechseln), `1.0` (inklusiv), `-0.0`, `1.0000001`, `-0.5`, `2`, String `"0.92"` (verworfen, keine Konvertierung), `None`, Liste/Dict als Wert.
- Strukturmischung: blanker String + Objekt in einer Antwort; Objekt ohne `key`; Objekt mit `key` ohne `confidence`; Objekt mit unbekanntem `key` **und** gültiger Zahl.
- Dedup/Kappung × Konfidenz: derselbe Schlüssel zweimal mit verschiedenen Zahlen → Erstnennung gewinnt bei Schlüssel *und* Zahl. Zusicherung als **Mengengleichheit** formulieren (`set(mapping) == set(categories)`), nicht als Zählung.
- Invariante: aufgelöste Kategorie mit Zahl; ohne Zahl bei nicht leerer Abbildung; `nicht_erkannt` (beide Seiten `None`); leere Kandidatenliste. Der aufdeckende Fall: Vorrang wählt einen **anderen** Kandidaten als den mit der höchsten Konfidenz — der Skalar muss dem aufgelösten Schlüssel folgen, nicht dem Maximum.
- Filter: Schwelle **exklusiv** (`0.599` gefiltert, `0.6` nicht); Ein → Aus stellt alle Partitionsüberschriften wieder her; leer gefilterte vs. erschöpfte Partition über den jeweiligen Text unterschieden, nicht über eine Kachelzahl; keine neue Anfrage (Aufrufzähler).
- Anzeige: `null` erzeugt in **beiden** Zweigen keinen Platzhalter (Negativ-Assertion); `0.0` erscheint als `0%`; Rundung `0.995 → 100%`, `0.004 → 0%` (bewusst ohne `< 1 %`-Sonderregel); Gruppenüberschrift ohne Zahl.
- Statistik: `average_confidence is None` (Assertion auf `is None`, nicht auf Falsyness — `0.0` ist ebenfalls falsy); zweites Projekt bleibt außen vor; Abgrenzung gegen die Kategorienverteilung (übersteuertes Foto zählt hier zur Modell-Kategorie); Projekt ganz ohne Konfidenzen.

**Coverage-Gate (≥ 80 %)** unkritisch: der neue Anwendungscode ist klein und wird vollständig durchlaufen. `backend/alembic/versions/` liegt außerhalb von `--cov=photosort` (wird trotzdem getestet), `demo_state.py` liegt innerhalb und muss seine neuen Zeilen selbst tragen.

## Entscheidungen

- **`architect` konsultiert (Schritt 1):** Ansatz übernommen, neue ADR 0067 angelegt, ADR 0049 mit Teil-Vermerk versehen.
- **`ux-ui-designer` konsultiert (Schritt 2):** Ansatz übernommen. Zwei Punkte am `architect` ausgerichtet, wo dieser maßgeblich ist: Feldnamen und die Sortierreihenfolge des Statistikblocks (Registry-Anzeigereihenfolge statt alphabetisch).
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien geschärft, Kriterium 12 ergänzt, Testkonzept fortgeschrieben.
- **`security-engineer` konsultiert (Schritt 3):** Feature ist sicherheitsrelevant; Sicherheitskonzept fortgeschrieben. Seine Abweichung vom `architect` beim Logging (festes Grund-Token statt `%r`-Rohwert) ist übernommen — der Diagnosewert liegt in der Fehlerklasse, und Grund-Tokens machen eine systematische Skalenverwechslung zählbar.
- **Daniel (Produktentscheidung):** Auffinden über einen **Filterschalter mit fester Schwelle 60 %**, nicht über eine wählbare Schwelle und nicht über Sortieren. Sortieren nähme der Kuratierung die Ordnung „bestes Foto zuerst".
- **Daniel (Produktentscheidung):** Fotos **ohne** Angabe fallen bei aktivem Filter **heraus**, ohne zusätzlichen Sonderhinweis für Projekte, die noch gar keine Angaben haben. Der Hinweistext für eine leer gefilterte Partition bleibt davon unberührt.
- **Daniel (Produktentscheidung):** Akzeptanzkriterium 9 ist geschärft statt aufgeweicht — die Zahl erscheint an neu klassifizierten Fotos; der bereits klassifizierte Bestand bleibt auf unbestimmte Zeit ohne Angabe. „Neu-Klassifizierung erzwingen" wird eine eigene Folge-Story.
- **Technische Detailentscheidungen** (innerhalb dieser Spec getroffen): Rundung kleiner Werte auf `0%` ohne `< 1 %`-Sonderregel; Bildung der Spiegelspalte per Lookup statt zweiter Berechnung; kein E2E-Spec.

## Offene Fragen

Keine. Die drei Produktentscheidungen sind bei der Spec-Erstellung mit Daniel geklärt worden (siehe „Entscheidungen").

## Out of Scope

- **Die Sicherheitsangabe ist reine Anzeige- und Auswertungsinformation.** Welche Kategorie ein Foto erhält, entscheidet unverändert allein die feste Vorrangreihenfolge. Die Zahl fließt nicht in die Kategorieauswahl ein und verändert keine bestehende Zuordnung.
- **Kein automatisches Neu-Klassifizieren bestehender Fotos.** Dass die Angabe am Altbestand fehlt, ist bewusstes und dokumentiertes Verhalten.
- **„Neu-Klassifizierung erzwingen"** — eine eigene Folge-Story, hier ausdrücklich nicht enthalten.
- **Kein Ableiten der Sicherheit aus vorhandenen Signalen** (Übereinstimmung lokaler und entfernter Erkennung, Anzahl der Kandidaten) — geprüft und verworfen.
- **Keine Schwelle im Backend**, keine serverseitige Sortierung nach Konfidenz, keine Konfidenz je Feinlabel.
