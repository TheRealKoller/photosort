# 0357 - Voller Bildvorrat beim Kuratieren sichtbar

**Status:** Accepted
**Erstellt:** 2026-09-09
**Bezug:** [GitHub-Issue #357](https://github.com/TheRealKoller/photosort/issues/357), ADR [`0071`](../decisions/0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md), berührt ADR [`0021`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) (Backfill in Punkt 4) und ADR [`0069`](../decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) (Definition von `curation_position` in Punkt 8)

## Ziel

Die Kuratierung ist die Kernschleife von PhotoSort — Scan, Scoring und Kategorisierung dienen
ausschließlich ihr. Genau dort erschwert die heutige Ansicht die Entscheidung: Pro Kategorie sind
standardmäßig nur drei Fotos sichtbar, nirgends steht, wie groß der Kandidatenvorrat überhaupt
ist, und beim Verwerfen rückt sofort das nächstbeste Foto nach. Man verwirft damit blind gegen
eine unbekannte Restmenge und kann nicht beurteilen, ob überhaupt eine bessere Alternative
existiert oder ob sich weiteres Durchsehen lohnt.

Diese Story macht den vorhandenen Vorrat sichtbar und gibt die Kontrolle über das Durchsehen an
den Nutzer zurück. Sie betrifft beide Nutzer (Daniel und seine Frau) und gilt für den gesamten
Kuratierungs-Durchlauf, nicht für einen Sonderfall.

## User Story

Als kuratierender Nutzer möchte ich sehen, wie viele Fotos in einem Cluster und in jeder Kategorie
überhaupt zur Auswahl stehen, und die weiteren Kandidaten bei Bedarf selbst einsehen können, damit
ich beim Verwerfen eines Fotos einschätzen kann, ob es eine bessere Alternative gibt, statt blind
gegen eine unbekannte Restmenge zu entscheiden.

## Akzeptanzkriterien

Die Kriterien des Story-Issues, vom `test-engineer` auf Testbarkeit geschärft. Die sechs nicht
entscheidbaren Formulierungen des Issues ("ist eindeutig erkennbar", "genauso bewertbar") sind
dabei durch prüfbare Aussagen ersetzt; fachlich ist nichts hinzugekommen außer den ausdrücklich
als **neu** markierten Punkten, die Grenzfälle schließen.

### Standardwert für die Anzahl angezeigter Fotos

- [ ] 1. Ohne `topN`-Suchparameter fordert `/curate` `top_n_per_category=10` an; das Eingabefeld auf
      der Kuratierungs-Schrittseite startet bei 10 und der erzeugte Link lautet `…/curate?topN=10`.
- [ ] 2. Grenzen unverändert: `< 1` → 1, `> 10` → 10, leer/ungültig → 10. Serverseitig bleibt
      `Field(ge=1, le=10)`; `top_n_per_category=11` bleibt 422.
- [ ] 3. `MIN_TOP_N`/`MAX_TOP_N`/`DEFAULT_TOP_N`/`parseTopN()` existieren genau einmal; beide Seiten
      importieren sie. **Genau ein** Testfall bindet `DEFAULT_TOP_N` an den Zahlwert `10`
      (Produktzusage), alle anderen Tests importieren die Konstante statt `10` abzuschreiben
      (dieselbe Regel wie bei `LOW_CONFIDENCE_THRESHOLD`, Spec 0299).

### Sichtbare Mengenangaben

- [ ] 4. Die Cluster-Überschrift trägt die Kandidatenzahl **zusätzlich**: der von
      `formatClusterHeading()` erzeugte Text (Tageszeit + Zeitraum) steht danach unverändert im
      Baum, die Zahl in einem eigenen Element daneben. Negativ-Nachweis dafür, dass die Angabe
      weder die Tageszeit noch die für einen späteren Ausbau vorgesehene Ortsangabe verdrängt.
- [ ] 5. Cluster-Zahl = Summe der `partition_size` aller Kategorien dieses Clusters; ein Foto in
      zwei Kategorien desselben Clusters zählt **zweimal**. Kategorie-Zahl = `partition_size`
      dieser Kategorie.
- [ ] 6. Invariante statt abgeschriebener Zahlen: *Cluster-Zahl == Summe der angezeigten
      Kategorie-Zahlen desselben Clusters*.
- [ ] 7. Beide Zahlen ändern sich nicht durch: angezeigte Kachelzahl, verworfene Fotos, aktiven
      Konfidenzfilter, Ein-/Ausblenden weiterer Kandidaten.
- [ ] 8. Die Tages-Zahl ("N Fotos", eindeutige Fotos, Spec 0300 AK 26) bleibt auch dann unverändert,
      wenn weitere Kandidaten eingeblendet sind — nachgeladene Kandidaten fließen **nicht** in die
      Gruppierung ein, aus der `countPhotosInDay()` rechnet.
- [ ] 9. **Neu:** Bei genau einem Kandidaten lautet die Beschriftung "1 Kandidat", nicht
      "1 Kandidaten". Kein Randfall: im Demo-Bestand hat jede Partition genau ein Foto.
- [ ] 10. **Neu:** Eine nur noch erinnerte, leere Kategorie (Pool durch Kategorie-Override
      leergelaufen) rendert keine Zahl — insbesondere kein "0 Kandidaten", kein
      "undefined"/"NaN".

### Verwerfen ohne automatisches Nachrücken

- [ ] 11. Nach dem Verwerfen ist die **vollständige** Kachelliste der Kategorie (IDs in Reihenfolge)
      identisch mit der davor — geprüft als Listenvergleich, nicht als "das Foto ist noch da".
- [ ] 12. Die verworfene Kachel trägt `PhotoCard status='rejected'` (Badge-Text "Verworfen",
      `data-struck`); ihre Schaltfläche bleibt an derselben Stelle, ist deaktiviert und trägt den
      zugänglichen Namen **"Verworfen: ⟨Dateiname⟩"**.
- [ ] 13. Die Antwort von `GET /photos?top_n_per_category=N` hängt nicht mehr vom anfragenden Nutzer
      ab: dieselbe Anfrage liefert für beide Nutzer dieselben `items` **und** dieselben
      `curation_position`-Werte, auch wenn einer der beiden Fotos verworfen hat.
- [ ] 14. `curation_position` ist für jede ausgewählte Zugehörigkeit gleich `rank_position` und
      `null` für jede nicht ausgewählte.
- [ ] 15. Steht dasselbe Foto in zwei Kategorien, tragen nach dem Verwerfen **beide** Kacheln den
      Zustand.
- [ ] 16. Ein von Nutzer A verworfenes Foto erscheint bei Nutzer B unverworfen (der Zustand kommt
      aus `ownRatingStatus`, nicht aus `ratings` insgesamt).
- [ ] 17. **Neu:** Der Busy-Zustand einer Schaltfläche endet, obwohl das Foto in `items` bleibt.
- [ ] 18. **Neu:** Mehrere Fotos lassen sich gleichzeitig verwerfen — zwei schnelle Klicks auf
      verschiedene Kacheln verwerfen beide, kein Klick verpufft still.

### Weitere Kandidaten einsehen

- [ ] 19. Der Auslöser wird **genau dann** gerendert, wenn `partition_size` größer ist als die Zahl
      der ungefilterten Einträge dieser Kategorie — beide Richtungen geprüft.
- [ ] 20. Standardmäßig zugeklappt; `aria-expanded` wechselt `false`→`true`, `aria-controls` zeigt
      auf den eingeblendeten Bereich; der Text wechselt zwischen Ein- und Ausblenden.
- [ ] 21. Nachgeladene Kandidaten stehen **hinter** den Top-Fotos in aufsteigender Rangfolge und
      wiederholen keines der bereits gezeigten Fotos derselben Kategorie.
- [ ] 22. Nachgeladene Kandidaten sind bewertbar/verwerfbar mit demselben Verhalten wie AK 11/12 —
      auch nach Zuklappen und erneutem Aufklappen.
- [ ] 23. Ausblenden entfernt die Kacheln wieder; die Mengenangaben bleiben unverändert.
- [ ] 24. Bei aktivem Konfidenzfilter gilt er auch für nachgeladene Kandidaten. Bleibt danach nichts
      übrig, steht dort ein Text, der sich vom Zustand "noch nichts geladen" **unterscheidet**.
- [ ] 25. **Neu:** "Kein weiteres Foto verfügbar" und der Auslöser erscheinen nie gleichzeitig in
      derselben Kategorie.
- [ ] 26. Ladezustand (Skeleton) und Fehlerzustand (`Alert` + "Erneut versuchen") sind abgedeckt;
      nach erfolgreichem zweitem Versuch stehen die Kandidaten da.
- [ ] 27. Übersteigt die Restmenge eine Antwortseite, lassen sich die weiteren Seiten nachladen; die
      zweite Seite wird mit dem richtigen Offset angefordert. Der Vorrat ist damit auch bei großen
      Kategorien vollständig einsehbar.

### Neuer Endpunkt

- [ ] 28. Liefert die Zugehörigkeiten der Partition mit `rank_position > after_rank`, aufsteigend;
      `total = max(partition_size - after_rank, 0)` **unabhängig** von `limit`/`offset`.
- [ ] 29. Verworfene Fotos sind enthalten, mit ihren `ratings`.
- [ ] 30. `curation_position` ist nur an der angefragten Zugehörigkeit gesetzt; jede andere
      Zugehörigkeit desselben Fotos trägt `null`.
- [ ] 31. Kein erfolgreicher Lauf / unbekannter `cluster_key` / unbekannter `category_key` /
      `after_rank ≥ partition_size` → **200** mit leerem `PhotoListOut` (`total: 0`), kein Fehler.
- [ ] 32. Unbekanntes Projekt → 404, ohne Auth → 401; Keys eines **anderen** Projekts liefern leer
      (kein Foto aus dem Fremdprojekt).
- [ ] 33. Bezugslauf ist der letzte erfolgreiche `CriterionScoringRun`: ein älterer Lauf mit
      abweichenden Rängen wirkt sich nicht aus.

## Datenmodell-Bezug

**Keine Änderung.** Keine neue Tabelle, keine neue Spalte, keine Migration, kein neues
Antwortfeld. Die Story bewegt sich vollständig auf der Leseseite und nutzt aus, was ADR 0021
Punkt 4 bereits persistiert: den **vollen** sortierten Kandidatenpool je Partition
(`PhotoRanking`), nicht nur die Top-N. Genutzte vorhandene Felder: `PhotoRanking.rank_position`,
`PhotoRanking.is_primary`, `RankingOut.partition_size`, `RankingOut.curation_position`,
`PhotoOut.ratings[]`. Siehe [`docs/architecture.md`](../../docs/architecture.md), Eintrag
**PhotoRanking** — dort wird der Backfill-Satz im selben Pull Request ersetzt.

## Architektur / Umsetzung

**Grundlage:** ADR [`0071`](../decisions/0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md)
(mit dieser Story angelegt). Sie widerruft den Backfill aus ADR
[`0021`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) Punkt 4 und schärft die
Definition von `curation_position` aus ADR
[`0069`](../decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md)
Punkt 8; beide ADRs tragen dafür einen `**Teilweise abgelöst:**`-Vermerk. Die Story bewegt sich
vollständig auf der **Leseseite**: keine neue Tabelle, keine neue Spalte, keine Migration, kein
neues Antwortfeld, keine Änderung an `worker.py`, `ranking.py`, `criteria.py` oder `categories.py`.

### Entwurfsentscheidungen

**1. Kein Nachrücken = der Ablehnungsfilter fällt aus der Abfrage, kein neuer Merk-Mechanismus.**
`api/photos.py::_top_n_per_category_photo_ids` schließt heute per Outer-Join die vom anfragenden
Nutzer `REJECTED`-bewerteten Fotos aus und berechnet `row_number()` erst danach — das *ist* der
Backfill. Ohne diesen Filter ist die Fensterfunktion überflüssig: `PhotoRanking.rank_position` ist
je Partition lückenlos ab 1 vergeben (`ranking.py::rank_photos` liefert `index + 1` über die
vollständige Partition; `worker.py::run_criterion_scoring` ruft sie je
`(cluster_key, category_key)` auf, Haupt- und Nebenzugehörigkeiten in derselben Liste;
`worker.py::reassign_photo_category` vergibt bei einem Override die Positionen beider betroffenen
Partitionen vollständig neu). Die Auswahl wird damit `rank_position <= N`, sortiert nach
`cluster_key, category_key, rank_position`. Welche Fotos die Ansicht zeigt, hängt danach
ausschließlich vom Lauf ab, nicht mehr vom Bewertungsstand des Betrachters — Positionsstabilität
entsteht strukturell, nicht durch eine Frontend-Vorkehrung.

**2. `curation_position` bleibt, mit geschärfter Bedeutung — und die Sicherheitsauflage zieht um,
statt zu entfallen.**
Das Feld ist seit Spec 0300 die einzige Auskunft darüber, unter welchen seiner Kategorien ein Foto
zu zeigen ist (`utils/rankings.ts::curatedRankings`); das Frontend darf die Auswahlregel nicht
nachbilden. Es bleibt deshalb erhalten und trägt künftig schlicht die Position in der
**angezeigten** Auswahl — nach Entscheidung 1 identisch mit `rank_position`, sonst `null`. Ein
Umbenennen in ein `in_selection: bool` findet **nicht** statt (Schema-Änderung an einem gerade
eingeführten Feld ohne Nutzen für seinen einzigen Konsumenten).

Der Docstring von `RankingOut.curation_position` wird entsprechend umgeschrieben ("um die eigenen
Ablehnungen bereinigt" stimmt nicht mehr). Von seiner SICHERHEIT-Passage entfällt dabei **nur** die
Begründung — dass der Wert nie persistiert werden darf, weil er die Ablehnungen des Anfragenden
abbildet: ohne Ablehnungsfilter ist er nicht mehr nutzerabhängig.

**Die Auflage selbst gilt weiter und wird verlegt, nicht gelöscht.** Der naheliegende Schluss
"ohne Rating-Join ist die Antwort nutzerunabhängig" ist falsch: `_to_photo_out` blendet
`PhotoOut.suggestion` genau dann ein, wenn der **anfragende** Nutzer noch keine eigene
`Rating`-Zeile für dieses Foto hat (`has_own_rating`, `api/photos.py`). Die Regel gilt in beiden
Query-Modi, wird von dieser Story nicht angefasst, und zwei Nutzer bekommen für dasselbe Foto
weiterhin verschiedene Antwortkörper. (`PhotoOut.ratings[]` trägt die Auflage ausdrücklich nicht —
die Liste ist für beide Anfragenden identisch.)

Die umgeschriebene Passage steht deshalb künftig am **Antwortaufbau**
(`_to_photo_out`/`list_photos`) statt an einem einzelnen Feld und lautet sinngemäß: *Bekommt
`GET /projects/{id}/photos` oder `GET /projects/{id}/curation-candidates` je eine
Antwort-Zwischenspeicherung, ein `ETag` oder ein `Cache-Control` über `no-store` hinaus, muss der
Schlüssel den Nutzer enthalten — Grund ist `PhotoOut.suggestion`.* Das ist kein theoretischer
Vorbehalt: Das Frontend ist eine PWA mit Workbox (`registerType: 'autoUpdate'`), heute ohne
`runtimeCaching` für API-Antworten — dessen Ergänzung ist der naheliegende nächste Schritt, der
Service-Worker-Cache ist pro Browserprofil geteilt, und das JWT liegt in `localStorage`.

**3. Verworfen ist ein Anzeigezustand, kein neues Feld.**
Das verworfene Foto bleibt in der Antwort und trägt seinen Zustand wie überall sonst in
`PhotoOut.ratings[]`. Die Ansicht liest ihn mit der bestehenden
`utils/ownRating.ts::ownRatingStatus(photo.ratings, username)` (`username` aus dem JWT-Claim,
identisch zu Raster- und Detailansicht) und gibt ihn an die bestehende `PhotoCard`-Prop `status`
weiter, die "aussortiert" bereits vollständig darstellt (gedämpfte Bildfläche, `RatingBadge` mit
`x-circle` + Produktwort, durchgestrichener Dateiname). Übergeben wird
`status={ownStatus === 'rejected' ? 'rejected' : undefined}` — `undefined` heißt "die Karte trägt
keinen Zustand" und hält die bestehende Entscheidung aufrecht, dass in der Kuratierung nicht auf
jeder Kachel "Neu" steht. Kein neuer Marker, keine neue Farbe, kein neues Bauteil.

**4. Beide Mengenangaben werden im Frontend abgeleitet; die Cluster-Zahl ist die Summe der
Kategorie-Zahlen.**

- **Kategorie-Zahl = `RankingOut.partition_size`**, unverändert übernommen. Es zählt seit Spec 0300
  ausdrücklich *alle* Zeilen der Partition, Haupt- wie Nebenzugehörigkeiten ("wie viele Fotos
  stehen in dieser Kategorie dieses Clusters"), ist lauf-global und nicht nutzerspezifisch
  gefiltert — also exakt der geforderte vollständige Kandidatenbestand.
- **Cluster-Zahl = Summe der `partition_size`-Werte** der Kategorien dieses Clusters.

Das Antwortschema bleibt dadurch unverändert; es entsteht keine zweite, serverseitig gepflegte
Zahl neben `partition_size`.

**Ein Foto, das im selben Cluster in zwei Kategorien steht, zählt in der Cluster-Zahl doppelt.**
Das ist die bewusste Produktentscheidung Daniels (gegen die Empfehlung des `architect`, siehe ADR
0071 Entscheidung 4 samt der dort festgehaltenen verworfenen Alternative). Sie ist tragfähig, weil
die Zahl damit beschreibt, was tatsächlich zu sichten ist: Die Kachel erscheint zweimal, in beiden
Kategorien, und ist dort jeweils einzeln zu beurteilen.

**Daraus folgt die Beschriftung — und sie ist nicht optional.** Cluster- und Kategorie-Zahl werden
als **"Kandidaten"** beschriftet, nicht als "Fotos". Unter dem Wort "Fotos" wäre die Cluster-Zahl
schlicht falsch, und sie stünde zugleich im Widerspruch zur Tages-Überschrift, die seit Spec 0300
(Akzeptanzkriterium 26) ausdrücklich eindeutige *Fotos* zählt. Verschiedene Größen tragen
verschiedene Wörter; das ist die einzige Stelle, an der diese Entscheidung lesbar bleibt.

**5. Die Tages-Zahl wird nicht angefasst.**
`countPhotosInDay` zählt weiterhin eindeutige Fotos der geladenen Auswahl (Spec 0300,
Akzeptanzkriterium 26) — diese Story definiert sie weder um noch schreibt sie sie neu. Sie ändert
durch Entscheidung 1 nur ihr Verhalten, nicht ihre Bedeutung: Weil verworfene Fotos in der Antwort
bleiben, schrumpft sie beim Arbeiten nicht mehr.

**6. Alle Mengenangaben werden aus der UNGEFILTERTEN Gruppierung gebildet.**
Die Seite hält seit Spec 0299 zwei Gruppierungen (`unfiltered` und die um `filterLowConfidence`
reduzierte). Die Zahlen kommen ausschließlich aus `unfiltered.groups` — auch die Summe der
Cluster-Zahl. Andernfalls verschwänden sie genau dort, wo der Konfidenzfilter eine Gruppe leer
räumt, obwohl der Bestand unverändert ist, und die Cluster-Summe verlöre die weggefilterten
Kategorien. Das deckt sich mit dem Akzeptanzkriterium ("unabhängig davon, wie viele davon gerade
angezeigt werden") und ist der subtilste Fehler, den diese Story bereithält.

**7. "Weitere Kandidaten" ist ein eigener Lese-Endpunkt, auf Abruf.**
`GET /projects/{project_id}/curation-candidates?cluster_key=…&category_key=…&after_rank=N&limit=…&offset=…`
liefert die Zugehörigkeiten **einer** Partition mit `rank_position > after_rank`, aufsteigend nach
`rank_position`, als `PhotoListOut` (`total` = Restmenge der Partition, also
`max(partition_size - after_rank, 0)`). Bezugslauf ist derselbe wie in der Hauptabfrage (letzter
erfolgreicher `CriterionScoringRun`); verworfene Fotos sind auch hier enthalten und
gekennzeichnet. **`curation_position` wird nur für die angefragte Zugehörigkeit gesetzt** — sonst
erschiene ein nachgeladenes Foto zusätzlich unter seinen anderen Kategorien, in denen niemand
aufgeklappt hat. Verworfen wurden: den vollen Pool immer mitliefern (vervielfacht die Grundlast
für Daten, die zugeklappt nie angesehen werden), `list_photos` um `cluster_key`/`category_key`
erweitern (der Endpunkt trägt bereits einander ausschließende Modi und die Zusage, dass dort
`limit`/`offset` nicht gelten), und ein Endpunkt ohne Seitenweise mit stillem Server-Deckel
(verschwiege den Rest — genau das Verhalten, gegen das die Story antritt).

**8. Die Einblendemöglichkeit braucht keinen Probe-Request.**
Ob es weitere Kandidaten gibt, steht vor jedem Laden fest: `partition_size > Anzahl der
ungefilterten Einträge dieser Kategorie`. Ist das falsch, wird der Auslöser nicht gerendert. Der
Kandidaten-Request läuft ausschließlich im aufgeklappten Zustand (`enabled`). Bei aktivem
Konfidenzfilter wird `filterLowConfidence` auch auf die nachgeladenen Fotos angewendet (eine
Bedeutung des Filters in der ganzen Ansicht); die Beschriftung des Auslösers nennt weiterhin die
ungefilterte Restmenge, wie alle anderen Zahlen auch.

**9. Die Cluster-Überschrift wird ergänzt, nicht umgebaut.**
Die Zahl ist ein eigenes `<span>` neben der von `formatClusterHeading()` gelieferten Überschrift —
dieselbe Bauform wie die bestehende Kurzinfo der Tages-Überschrift. `formatClusterHeading()` selbst
wird **nicht** angefasst: Tageszeit und Zeitspanne bleiben, die für einen späteren Ausbau
vorgesehene Ortsangabe bleibt dort frei. Die Zeitspanne leitet sich weiterhin nur aus den
angezeigten Fotos ab; nachgeladene Kandidaten fließen nicht in die Gruppierung ein, sonst spränge
die Überschrift beim Aufklappen.

**10. Der Standardwert lebt künftig an einer Stelle.**
"3" steht heute dreimal (`CurateCategoriesPage.tsx::DEFAULT_TOP_N`, `KuratierungStepPage.tsx`
zweimal). Beim Anheben auf 10 wandern `MIN_TOP_N`/`MAX_TOP_N`/`DEFAULT_TOP_N` samt `parseTopN()`
in ein eigenes Modul `frontend/src/utils/curationTopN.ts`, das beide Seiten importieren. Grenzen
bleiben 1/10, deckungsgleich mit der serverseitigen Durchsetzung (`Query(None, ge=1, le=10)`).

**11. Mehrere Fotos lassen sich gleichzeitig verwerfen.**
`handleReject()` ignoriert heute jeden Klick, solange eine Ablehnung läuft
(`if (rejectingPhotoId !== null) return`) — sinnvoll, solange die Liste danach umsprang. Ohne
Nachrücken springt nichts mehr, und ein zweiter Klick verpuffte still. Der Zustand wird deshalb
von einer einzelnen Foto-Id auf eine **Menge laufender Foto-Ids** umgestellt; jedes Foto verwirft
unabhängig. Produktentscheidung Daniels.

**Aufgegeben wird dabei die seitenweite Sperre, nicht die Sperre je Foto.** Ein zweiter Vorgang für
*dasselbe* Foto bleibt ausgeschlossen: `Rating` trägt `UniqueConstraint(photo_id, user_id)`, zwei
nebenläufige Anfragen liefen in einen `IntegrityError` und damit in eine 500. Seit Spec 0300 hat
dasselbe Foto zudem bis zu vier Kacheln mit je eigener Schaltfläche — ein schneller Klick auf zwei
davon ist ein realistischer Bedienweg, kein konstruierter Doppelklick. Die Prüfung darf dabei
nicht gegen den Zustand im Render-Closure laufen, und `disabled` an der Schaltfläche ist kein
Ersatz: beides entsteht erst durch ein State-Update, zwei Klicks im selben Durchlauf sähen
denselben, leeren Schnappschuss.

### Betroffene Dateien

**Backend**

- `backend/src/photosort/api/photos.py`
  - `_top_n_per_category_photo_ids`: Outer-Join auf `Rating` und `row_number()` entfallen, Auswahl
    über `rank_position <= top_n`; `curation_position` wird die `rank_position`; der Parameter
    `current_user_id` wird überflüssig (Signatur und Aufrufstelle anpassen).
  - `RankingOut`: Docstring von `curation_position` neu geschrieben — die SICHERHEIT-Passage wird
    **umgeschrieben und verlegt**, nicht gelöscht (siehe Entscheidung 2): sie steht künftig am
    Antwortaufbau (`_to_photo_out`/`list_photos`) und nennt `PhotoOut.suggestion` als Grund.
    **Kein neues Feld.**
  - neuer Endpunkt `curation_candidates`: trägt `current_user: User = Depends(get_current_user)`
    als eigenen Parameter und reicht `current_user.id` an `_to_photo_out` durch. Jede seiner
    Abfragen — auch die Zählabfrage hinter `total` — filtert auf
    `criterion_scoring_run_id == _latest_successful_criterion_scoring_run_id(session, project_id)`.
    Wiederverwendet unverändert `_photos_by_id`, `_rankings_by_photo_id`, `_partition_sizes`,
    `_to_photo_out`, `_get_project_or_404`. Kein erfolgreicher Lauf oder unbekannte Keys → leeres
    `PhotoListOut`, kein Fehler.
- `backend/tests/test_api_photos.py` — die Bestandstests des alten Verhaltens werden zu
  Gegenteil-Tests umgeschrieben, nicht gelöscht (siehe Teststrategie); Tests für den neuen
  Endpunkt.

**Frontend**

- `frontend/src/utils/curationTopN.ts` *(neu)* — Grenzen, Standardwert 10, `parseTopN()`.
- `frontend/src/api/photos.ts` — `listCurationCandidates(projectId, { clusterKey, categoryKey,
  afterRank, limit, offset })`, Rückgabe `PhotoListOut` (kein neuer Typ in `types.ts` nötig).
- `frontend/src/hooks/usePhotos.ts` — `useCurationCandidatesQuery(...)` als `useInfiniteQuery` mit
  `PHOTOS_PAGE_SIZE`, Query-Key
  `['photos', projectId, 'curate', 'candidates', clusterKey, categoryKey, afterRank]` (unter dem
  `['photos', projectId]`-Präfix, damit die bestehende breite Invalidierung nach einer Bewertung
  auch hier greift), `enabled` nur im aufgeklappten Zustand.
- `frontend/src/components/CurationPhotoTile.tsx` *(neu, mit Test)* — die Kachel der Kuratierung
  (`PhotoCard` + `CriterionDetailsPopover` + `CategoryOverrideMarker`/`SecondaryCategoryMarker` +
  `QualityMeter` + Verwerfen-Aktion), heute rund 100 Zeilen JSX inline in der Seite. Sie wird für
  die Top-Auswahl **und** die eingeblendeten Kandidaten gebraucht; eine zweite Kopie wäre die
  zweite Stelle, an der eine künftige Änderung vergessen wird. Props tragen `photo` **und**
  `ranking` (die Zugehörigkeit dieses Vorkommens) — die Kachel ist seit Spec 0300 nicht mehr durch
  das Foto allein bestimmt.
- `frontend/src/components/CurationCandidates.tsx` *(neu, mit Abdeckung durch die
  Seiten-Integrationstests)* — der Aufklapp-Auslöser und der Bereich darunter: eigener
  Ladezustand (Skeleton), Fehlerzustand (`Alert` + "Erneut versuchen"), die beiden
  unterscheidbaren Leerzustände und der Nachlade-Auslöser weiterer Seiten. Er besitzt die
  Kandidaten-Query; die Kachel selbst baut die Seite über eine `renderTile`-Rückrufsfunktion,
  weil Verwerfen-Zustand und Override-Steuerung dort leben.
- `frontend/src/pages/CurateCategoriesPage.tsx` — Zahlen in Cluster- und Kategorie-Überschrift;
  verworfener Zustand an der Kachel; Aufklappbereich je Kategorie samt Nachladen weiterer Seiten;
  Umstellung von `rejectingPhotoId` auf eine Menge laufender Foto-Ids; Entfall des
  Skeleton-Tauschs und des `useEffect`, der auf das Verschwinden des Fotos wartet.
  `countPhotosInDay` bleibt unverändert. `knownGroupKeysRef` und `clusterMetaRef` bleiben: eine
  Partition kann weiterhin leerlaufen, nur nicht mehr durchs Verwerfen, sondern durch einen
  Kategorie-Override.
- `frontend/src/pages/pipeline/KuratierungStepPage.tsx` — Standardwert 10 aus dem neuen Modul; der
  Erklärsatz "sortierst du eines aus, rückt automatisch das nächstbeste derselben Kategorie nach"
  ist ab dieser Story unwahr und wird ersetzt.
- Zugehörige `*.test.tsx`/`*.test.ts` der berührten Dateien.

**Doku (im selben Pull Request, `CLAUDE.md`-Abschnitt "Doku-Pflege")**

- `docs/architecture.md` — Eintrag **PhotoRanking**: der Satz, der Backfill als `row_number()` nach
  dem `REJECTED`-Ausschlussfilter beschreibt, wird durch das neue Verhalten ersetzt;
  Backend-Absatz um `GET /projects/{id}/curation-candidates` ergänzt.
- `specs/architecture/0004-design-system.md` — das Muster "In-place Nachrücken (Backfill) statt
  Reflow" ist zurückgenommen (Wortlaut im Abschnitt UI/UX).
- `.claude/skills/design-system/SKILL.md` — führt dasselbe Muster in Kurzform und wird bei jeder
  Frontend-Arbeit gelesen; er wird im selben Schritt nachgezogen, damit die Regel nicht an zwei
  Stellen mit gegensätzlichem Inhalt steht.

### Reihenfolge der Umsetzung

1. **Backend, Ablehnungsfilter entfernen** — Test zuerst: ein verworfenes Foto bleibt im Ergebnis,
   an derselben `rank_position`, und kein bisher unsichtbares Foto erscheint. Kleinster Schnitt mit
   der größten Wirkung; alles Weitere setzt darauf auf.
2. **Backend, Kandidaten-Endpunkt** — inkl. Grenzfälle: kein erfolgreicher Lauf, unbekannte
   `cluster_key`/`category_key` (leere Liste), `after_rank` ≥ Partitionsgröße, Seitenweise/`total`,
   `curation_position` nur auf der angefragten Zugehörigkeit, 401 ohne Token, Fremdprojekt-Keys.
3. **Frontend-Zugriffsschicht** — API-Funktion und Hook gegen den fertigen Endpunkt.
4. **Standardwert 10** — eigenständig und unabhängig; erledigt ein Akzeptanzkriterium ganz.
5. **Kachel herauslösen** (`CurationPhotoTile`) — reines Refactoring bei unverändertem Verhalten,
   bevor die zweite Verwendungsstelle entsteht.
6. **Zahlen und verworfener Zustand** in der Kuratierungsansicht, inkl. Umstellung auf mehrere
   gleichzeitige Verwerfen-Vorgänge.
7. **Aufklappbereich "weitere Kandidaten"** samt Nachladen weiterer Seiten — der einzige Schritt
   mit neuem Ladeverhalten, deshalb zuletzt.
8. **Doku nachziehen** (`docs/architecture.md`, Erklärsatz auf der Pipeline-Seite).

### Hinweise für die Umsetzung

- **`api/photos.py` hat bewusst keine Router-weite Auth-Dependency** (Kopfkommentar der Datei:
  jeder Endpunkt braucht das echte `User`-Objekt, nicht nur den Torwächter). Ein neuer Endpunkt,
  der `current_user: User = Depends(get_current_user)` vergisst, ist deshalb **still öffentlich** —
  kein Fehler, keine 401, nur Daten. `current_user.id` wird an `_to_photo_out` durchgereicht;
  **nie ein Platzhalter wie `0`**, der ließe `suggestion` auch für längst bewertete Fotos wieder
  aufblitzen. Ein Test, der den Endpunkt ohne Token aufruft und 401 erwartet, gehört zur ersten
  Testrunde dieses Schritts.
- **`PhotoRanking` hat keine `project_id`.** `cluster_key` ist `cluster-<n>`, je Lauf neu vergeben
  und in jedem Projekt identisch; `category_key` kommt aus dem festen Set. Die einzige
  Projektbindung ist `criterion_scoring_run_id`, abgeleitet **ausschließlich aus dem
  Pfadparameter** (`_latest_successful_criterion_scoring_run_id(session, project_id)`) — nie aus
  einem Query-Parameter. Das Prädikat muss in der `WHERE`-Klausel jeder Abfrage des neuen
  Endpunkts stehen, die Zählabfrage hinter `total` eingeschlossen; `_photos_by_id` filtert nur nach
  Id und ist keine zweite Verteidigungslinie. Ohne dieses Prädikat liefert
  `?cluster_key=cluster-1&category_key=landschaft` Fotos fremder Projekte.
- Die Zählwerte werden als **exportierte, unit-getestete reine Funktionen** neben
  `countPhotosInDay` gebildet, nicht als Ausdruck im JSX — dieselbe Bauform wie
  `countPhotosInDay`/`toggleDayCollapse`/`sortCategoryKeys`:
  - `candidateCountOfCategory(entries: CurationEntry[]): number` →
    `entries[0]?.ranking.partition_size ?? 0` (alle Einträge einer Partition tragen denselben Wert).
  - `candidateCountOfCluster(photosByCategory): number` → Summe von `candidateCountOfCategory` über
    die Kategorien des Clusters.

  Eine Gruppe ohne Einträge (nur noch über `knownGroupKeysRef` bekannt, nach einem
  Kategorie-Override) liefert 0 und bekommt **keine** Zahl an die Überschrift — "0 Kandidaten" wäre
  eine Aussage über einen Bestand, den die Antwort gar nicht mehr beschreibt.
- **Der `useEffect`, der `rejectingPhotoId` zurücksetzt, sobald das Foto aus `items` verschwindet,
  muss weg.** Ohne Backfill verschwindet das Foto nie — die Schaltfläche bliebe dauerhaft im
  Busy-Zustand. Ersatz: den Eintrag im `onSettled`-Callback der Mutation aus der Menge entfernen.
- Der Aufklapp-Zustand folgt exakt dem bestehenden Tages-Aufklappen: `Button variant="ghost"` mit
  `aria-expanded`/`aria-controls`, Inhalt per bedingtem JSX (nicht CSS-versteckt), Zustand in einem
  `Set` mit `JSON.stringify([dayKey, clusterKey, categoryKey])` als kollisionssicherem Schlüssel —
  dieselbe Schlüsselbildung wie `knownGroupKeysRef`.
- Der Kandidatenbereich braucht seine eigenen Zustände: Skeleton beim Laden, `Alert` mit "Erneut
  versuchen" bei Fehler; die Rangfolge kommt vom Server und wird nicht nachsortiert. Der
  React-Schlüssel bleibt `${photo.id}-${ranking.category_key}` (ein Foto kann in zwei Kategorien
  stehen).
- Eine verworfene Kachel behält ihre Verwerfen-Schaltfläche an derselben Stelle, deaktiviert und
  mit "Verworfen" beschriftet. Ein Zurücknehmen ist in dieser Story **nicht** enthalten (weiterhin
  über die Rasteransicht, Filter "Aussortiert").
- Die beiden Platzhaltertexte für unvollständige Gruppen (erschöpfter Pool vs. leer gefiltert,
  Spec 0299) bleiben unverändert; sie werden nicht durch die neuen Zahlen ersetzt.

## UI/UX

### Ablauf und Layout

**Mengenangaben — zwei unterschiedliche Zählweisen:**

- **Tages-Ebene:** zählt **eindeutige Fotos**, Beschriftung "N Fotos" (unverändert seit Spec 0300
  AK 26). Ein Foto, das an einem Tag in zwei Kategorien steht, zählt einmal.
- **Cluster-Ebene (neu):** zeigt die **Summe der Kategorie-Kandidaten** darunter, Beschriftung
  "N Kandidaten". Ein Foto in zwei Kategorien desselben Clusters zählt zweimal (z.B. Cluster-Zahl
  "11" bei 9 verschiedenen Fotos).
- **Kategorie-Ebene (neu):** jede Kategorie-Überschrift zeigt ihre `partition_size`, Beschriftung
  "Kandidaten" (z.B. "Menschen — 5 Kandidaten").

Die verschiedenen Wörter sind der Träger der Entscheidung: oben eindeutige *Fotos*, darunter
*Kandidaten* im Sinne von Vorschlagsplätzen, die einzeln zu beurteilen sind. Bei genau einem
Kandidaten steht "1 Kandidat".

**Cluster-Überschrift:** Die bestehende `formatClusterHeading()`-Ausgabe (z.B. "14:30–15:15") wird
um eine Klammer-Kurzinfo `(N Kandidaten)` ergänzt. Das `<span>` sitzt in derselben Textzeile neben
der Cluster-Überschrift, gleiche Formsprache wie die bestehende `(N Fotos)`-Kurzinfo der
Tages-Kopfzeile, gleiche Textfarbe `text-text`.

**Kategorie-Überschrift:** Neben dem Kategorie-Label steht die Zahl aus `partition_size` mit dem
Label "Kandidaten", konsistent zur Cluster-Ebene.

**Verworfene Fotos bleiben sichtbar:** über die bestehende `PhotoCard`-Prop `status="rejected"`
(gedämpfte Bildfläche, Durchstreichung des Dateinamens, `RatingBadge` mit `x-circle`). Die Kachel
behält ihre Position und verschiebt kein anderes Foto.

**Verwerfen-Schaltfläche bei verworfenen Fotos:** Die Fußzeilen-Aktion wechselt zu einem
deaktivierten Button mit der Beschriftung "Verworfen" — sichtbar, aber `disabled`. Der zugängliche
Name trägt den Dateinamen ("Verworfen: ⟨Dateiname⟩"), sonst wären auf einer Seite mit vielen
Kacheln alle Schaltflächen namensgleich. Während einer laufenden Mutation wird nur die
Schaltfläche busy; Bild, Ecken-Marker und Info-Trigger bleiben stehen (ein Skeleton überbrückte
früher den Tausch auf ein *anderes* Foto und wäre jetzt ein Flackern ohne Zweck).

**Aufklapp-Auslöser für weitere Kandidaten:** nur, wenn `partition_size` größer ist als die Zahl
der ungefilterten Einträge dieser Kategorie. Unterhalb der Top-Foto-Reihe:

- Geschlossen: `Button variant="ghost"`, "Weitere Kandidaten laden", `aria-expanded="false"`.
- Offen: derselbe Button, `aria-expanded="true"`, "Weitere Kandidaten ausblenden".
- Muster wie die bestehende Tages-Aufklappung (`aria-expanded`/`aria-controls`).
- Die Beschriftung nennt die **ungefilterte** Restmenge, auch bei aktivem Konfidenzfilter.
- Beim Laden: Skeleton-Platzhalter in Kachelform. Bei Fehler: `Alert` mit "Erneut versuchen".
- Geladene Kandidaten stehen in derselben `<ul class="grid …">`-Struktur wie die Top-Fotos — kein
  neues Raster, gleiche Kachelgrößen, gleiche Bewertbar-/Verwerfbar-Zustände.
- Übersteigt die Restmenge eine Antwortseite, gibt es einen sichtbaren Nachlade-Auslöser für die
  weiteren Seiten (bestehendes `useInfiniteQuery`/`PHOTOS_PAGE_SIZE`-Muster der Rasteransicht).

**Nebenkategorien:** Dasselbe Foto kann in mehreren Kategorien desselben Clusters erscheinen.
React-Schlüssel `${photo.id}-${ranking.category_key}`. Im `topLeft`-Slot trägt ein übersteuertes
Foto den `CategoryOverrideMarker`, ein Foto in einer Nebenkategorie (`!ranking.is_primary`)
zusätzlich den `SecondaryCategoryMarker`; beide können gleichzeitig vorhanden sein und sitzen
nebeneinander in einem `flex gap-1`-Container.

**Responsivität:** kein Unterschied zur heutigen Kuratierung — die neuen Zahlen sind reiner Text.

### Zustände und Fehlerbehandlung

- **Leer:** bestehendes Textbanner "Keine Fotos in dieser Tageszeit" (ungefiltert) bzw. die
  Platzhalter aus Spec 0299 bei aktivem Konfidenzfilter (`LOW_CONFIDENCE_EMPTY_TEXT` /
  `LOW_CONFIDENCE_EMPTY_CLUSTER_TEXT`).
- **Gefiltert, aber teilweise leer:** `LOW_CONFIDENCE_NO_MORE_TEXT` statt "Kein weiteres Foto
  verfügbar" (Spec 0299 AK 5).
- **Ladend:** Skeleton-Platzhalter für die Top-Fotos wie heute. Der Aufklapp-Auslöser wird erst
  gerendert, wenn die Top-Fotos geladen sind.
- **Alle Top-Fotos verworfen:** Kategorie und Cluster bleiben sichtbar (die verworfenen Kacheln
  stehen weiter da). Der Auslöser erscheint nur, wenn es tatsächlich weitere ungefilterte
  Kandidaten gibt.
- **Fehler beim Laden von Kandidaten:** `Alert`-Banner mit Fehlertext, Button "Erneut versuchen"
  löst einen Refetch mit denselben Parametern aus.

### Barrierefreiheit

- `aria-expanded` am Aufklapp-Button wie bei der Tages-Aufklappung; `aria-controls={panelId}` zeigt
  auf den Bereich mit den Kandidaten.
- Beim Laden: `<ul role="status" aria-label="Weitere Kandidaten werden geladen…">` auf der
  Skeleton-Liste.
- Der durchgestrichene Dateiname (`data-struck` + `line-through` in `PhotoCard`) trägt den
  verworfenen Zustand; die Beschriftung "Verworfen" an der Schaltfläche ist zusätzliche,
  redundante Klarheit.
- Der `SecondaryCategoryMarker` trägt `aria-label="Nebenkategorie"`, nicht nur ein Symbol.
- Der Wegfall des Nachrückens hilft allen Nutzern und besonders bei Bewegungssensibilität: keine
  Positionswechsel als Folge einer eigenen Aktion.

### Änderung am Design-System

`specs/architecture/0004-design-system.md`, **Zeile 313**, Muster "In-place Nachrücken (Backfill)
statt Reflow": Der Eintrag wird durch die zurückgenommene Fassung ersetzt — verworfene Fotos
bleiben an ihrer Position sichtbar und gekennzeichnet, es rückt kein Kandidat nach, weitere
Kandidaten werden auf Anfrage separat geladen. Begründung im Eintrag: stabilere mentale Kartierung,
Designprinzip "Verlässlichkeit statt Onboarding".

**Zusätzlich Zeile 356:** Der dortige Punkt "Sofortige Wirkung ohne eigenes
Reflow-Vermeidungsmuster" verweist auf das Muster als "das **bestehende** In-place Nachrücken
(Backfill) statt Reflow"-Muster (Verwerfen in der Kuratierungsansicht)". Die Gegenprobe bleibt
inhaltlich richtig, aber die Kennzeichnung als bestehend wird falsch und ist mitzuziehen; das
Beispiel in Klammern trifft nach dieser Story nicht mehr zu.

## Security

Sicherheitsrelevant, kein Blocker. Kein neues Secret, keine neue Umgebungsvariable, kein neuer
externer Dienst oder Empfänger, keine neue Abhängigkeit, keine Prompt-Änderung, kein zusätzlicher
Datenfluss Richtung Cloud, keine Datenmodell-Änderung und keine Migration. Neu sind genau zwei
Dinge: ein **zweiter Lese-Endpunkt** und der **Wegfall eines nutzerabhängigen Filters** aus einem
bestehenden Lesepfad. Vollständige Herleitung in
[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt
"Voller Bildvorrat in der Kuratierung".

**1. Die Auflage "nutzerabhängiger Cache-/`ETag`-Schlüssel" entfällt nicht — sie wechselt ihre
Begründung. Muss-Kriterium.** Der naheliegende Schluss, die Antwort sei nach dem Wegfall des
Rating-Joins nutzerunabhängig, trifft für `curation_position` zu, für die **Antwort** aber nicht:
`_to_photo_out` berechnet `PhotoOut.suggestion` über
`has_own_rating = any(rating.user_id == current_user_id …)`. Zwei Nutzer bekommen für dasselbe Foto
weiterhin unterschiedliche Antwortkörper. `PhotoOut.ratings[]` trägt die Auflage ausdrücklich
**nicht** (für beide Anfragenden byte-identisch). Die SICHERHEIT-Passage wird deshalb umgeschrieben
und an den Antwortaufbau verlegt, nicht gelöscht. Nicht theoretisch: Das Frontend ist eine PWA mit
Workbox (`registerType: 'autoUpdate'`), heute ohne `runtimeCaching` für API-Antworten; der
Service-Worker-Cache ist pro Browserprofil geteilt, das JWT liegt in `localStorage`, und zwei
Personen an einem Gerät ist ein realistischer Familienfall.

**2. Auth und Projektbindung am neuen Endpunkt — beides Muss.** `api/photos.py` verzichtet bewusst
auf eine Router-weite Auth-Dependency; ein neuer Endpunkt, der den Parameter vergisst, ist **still
öffentlich**. `PhotoRanking` hat keine `project_id`, und `cluster_key` (`cluster-<n>`) ist in jedem
Projekt derselbe String — die einzige Projektbindung ist `criterion_scoring_run_id`, abgeleitet
ausschließlich aus dem Pfadparameter, und sie muss in jeder Abfrage stehen, auch der Zählabfrage
hinter `total`. Ein Projektübergriff wäre heute keine Rechteausweitung (beide Nutzer sehen alle
Projekte), sondern ein Korrektheitsfehler — Muss trotzdem, weil das Prädikat die *einzige* Grenze
ist.

**3. Freie Schlüsselstrings ohne Allowlist: tragfähig, mit vier Auflagen an die Verwendung.**
`cluster_key`/`category_key` bewusst nicht gegen `CATEGORY_REGISTRY` zu prüfen ist richtig (der
Lesepfad ist seit Spec 0289 tolerant gegenüber Altbestand). Sicherheitsrelevant ist allein, dass
der Wert seinen Kontext nie verlässt: ausschließlich als **gebundener** Query-Parameter in
SQLAlchemy-ORM-Ausdrücken (kein `text()`, keine f-String-Interpolation); kein Weg in Pfad-, Datei-,
Shell- oder Prompt-Operationen und keine Persistenz; **keine Rückspiegelung** in Antwort oder
Fehlermeldung (die Festlegung "unbekannte Keys → leere Liste" schließt das mit ab); kein
ungeprüftes Log dieser Werte. Soll: eine `max_length` auf beiden Parametern.

**4. Grenzen der Query-Parameter.** `limit: int = Query(60, ge=1, le=200)` und
`offset: int = Query(0, ge=0)` wie im Standard-Listing — Muss; `le=200` deckelt Antwortgröße und
die schwere Hydratation über `_photos_by_id`. `after_rank` mit `ge=0` — Muss, auch aus
Korrektheitsgründen (ein negativer Wert bläht `total` über die tatsächliche Menge auf).
Zusätzlich eine Obergrenze auf `after_rank` und `offset` — Soll: Ein Pydantic-`int` ist
unbeschränkt, und unter SQLite (Tests, lokale Entwicklung) wirft ein Wert jenseits von 2⁶³ einen
`OverflowError` und damit eine 500 statt einer leeren Liste (nachgestellt und bestätigt).
`list_photos` hat dieselbe unbeschränkte `offset`-Eigenschaft heute schon — eine kleine bestehende
Lücke, die diese Story nicht einführt und nicht schließen muss; die neuen Parameter sollten sie
nur nicht wiederholen.

**5. Ressourcenverbrauch: keine neue Klasse. Sichtbarkeit zwischen den Nutzern: keine neue
Information.** Antwortgröße und Hydratation sind durch `limit ≤ 200` gedeckelt; das übrige Profil
entspricht jedem `list_photos`-Aufruf. Der entfallende Filter war über
`own_rejection.user_id == current_user_id` **nur an den Anfragenden selbst** gebunden; über den
jeweils anderen hat er nie etwas verborgen. `PhotoOut.ratings[]` trug in beiden Zweigen schon immer
beide Bewertungen. Neu in der Antwort sind ausschließlich Fotos, die der Anfragende **selbst**
abgelehnt hat — dasselbe Foto mit demselben `ratings[]` ist über das Standard-Listing längst
erreichbar. Also eine Verschiebung der Ansicht, keine neue Datenklasse. Muss dazu: Die Kuratierung
liest den eigenen Zustand ausschließlich über `ownRatingStatus` und baut keine zweite Ableitung
(etwa "erster Eintrag in `ratings[]`"), die den Zustand des anderen als eigenen darstellte;
Testfall dafür in AK 16.

## Teststrategie

**Ebenen.** Backend-Integration (`backend/tests/test_api_photos.py`, In-Memory-SQLite,
`authenticated_api_client`): der neue Endpunkt vollständig (AK 28–33) und die Umkehrung der
Auswahl-Query (AK 13/14). Frontend-Unit (`frontend/src/utils/curationTopN.test.ts`):
tabellengetriebene Grenzfälle für `parseTopN()` (`null`, `''`, `'abc'`, `0`, `0.4`, `10.6`, `11`,
`-3`), plus **genau ein** Testfall, der `DEFAULT_TOP_N` an `10` bindet. Frontend-Integration
(`CurateCategoriesPage.test.tsx`, `KuratierungStepPage.test.tsx`, `usePhotos.test.tsx`, gemockte
`api/*`): Mengenangaben, Verworfen-Zustand, Auslöser/Nachladen, Filter-Zusammenspiel. **Kein neuer
E2E-Spec** — `/curate` steht bereits in `no-horizontal-scroll.spec.ts`, und die längere
Cluster-Überschrift ist genau der Fall, für den dieser Spec gebaut ist. Die deaktivierte
"Verworfen"-Schaltfläche wird **nicht** in `tap-targets.spec.ts` aufgenommen (der Spec verlangt
`toBeEnabled()`, ein deaktiviertes Element wäre falsch-rot).

**Bestandstests, die das alte Verhalten kodieren, werden ins Gegenteil umgeschrieben statt
gelöscht.** Namentlich:

- `test_backfill_shows_next_best_photo_after_rejecting_the_top_one` → *Verwerfen ändert die Auswahl
  nicht* (dieselben Ids vor und nach dem `PUT /rating`, das verworfene Foto weiterhin an
  Position 1).
- `test_rejection_filter_is_scoped_to_the_current_user` und
  `test_curation_position_is_scoped_to_the_rejections_of_the_asking_user` → **ein** Testfall
  *Antwort ist nutzerunabhängig*: zwei Nutzer, eine Ablehnung, identische `items` **und**
  identische `curation_position`-Werte. Der Zwei-Nutzer-Aufbau bleibt erhalten — die weggefallene
  Personalisierung wird zugesichert, nicht ersatzlos gestrichen.
- `test_curation_position_is_smaller_than_rank_position_behind_a_rejected_photo` →
  *`curation_position` ist entweder `null` oder gleich `rank_position`*, auch hinter einem
  verworfenen Foto.
- `rejects a photo and shows a skeleton in its tile until the backfilled photo arrives` → *die
  Kachel bleibt an ihrer Stelle und wird als verworfen markiert*, plus AK 17.
- Die drei Fälle `keeps the day section visible …`, `keeps a category section visible …`,
  `keeps a cluster heading available from the clusterMetaRef cache …` mocken eine **zweite Antwort
  ohne das Foto**. Diese Antwort ist nach der Änderung serverseitig unmöglich; die Tests würden
  eine Fiktion prüfen und `knownGroupKeysRef`/`clusterMetaRef` scheinbar abdecken. Sie werden auf
  den einzigen verbliebenen echten Auslöser umgehängt: den **Kategorie-Override**. Wird das nicht
  getan, ist der Erschöpfungs-Leerzustand ab hier ungetestet.
- `KuratierungStepPage.test.tsx`: vier Fälle mit hartem `topN=3`/Feldwert `'3'` → 10, über die
  importierte Konstante. Der Hilfetext zum Nachrücken ist danach falsch und wird ersetzt; der
  Testfall prüft den neuen Text und assertiert negativ auf die Nachrück-Aussage.
- `shows an empty-pool placeholder when a category has fewer than N photos` bleibt, ergänzt um
  AK 25 (Auslöser und Erschöpfungshinweis schließen sich aus).

**Fixture-Regel.** Die Fabriken in `CurateCategoriesPage.test.tsx` liefern heute
`partition_size: 1` als Basiswert, während viele Fälle zwei Kacheln rendern — mit sichtbaren Zahlen
wäre das ein in sich widersprüchlicher Bestand. `partition_size` ist ab hier in jeder Fixture
konsistent zur Zahl der Einträge zu setzen; mindestens ein Fall mit
`partition_size == angezeigte Einträge` (kein Auslöser) und einer mit
`partition_size > angezeigte Einträge` (Auslöser).

**Zwei Zählweisen in EINEM Testfall** (Regel aus Spec 0300, hier erstmals in der Oberfläche):
dieselbe Fixture — ein Foto in zwei Kategorien eines Clusters — trägt beide Assertions: Tages-Zahl
zählt es **einmal**, Cluster-Zahl **zweimal**. Zwei getrennte Positivtests blieben auch dann grün,
wenn beide Zahlen aus derselben Quelle kämen. Der bestehende Fall
`zaehlt ein doppelt gezeigtes Foto in der Tagesueberschrift nur einmal` wird dafür erweitert statt
dupliziert.

**Edge Cases mit eigenen Testfällen:**

- *Konfidenzfilter (Spec 0299):* Zahlen kommen aus der **ungefilterten** Gruppierung — Filter ein →
  Cluster-/Kategorie-Zahl unverändert; der Auslöser erscheint auch an einer leer gefilterten
  Kategorie; nachgeladene Kandidaten werden gefiltert, und "alles weggefiltert" ist vom "noch
  nichts geladen" unterscheidbar.
- *Mehrfachzugehörigkeit (Spec 0300):* Foto ist Top-1 in Kategorie A **und** Kandidat #12 in
  Kategorie B — nach dem Aufklappen von B erscheint es genau einmal je Kategorie, und der
  Nebenkategorie-Marker steht nur an der richtigen Kachel. Nachgeladene Fotos dürfen **nicht** in
  `items` der Hauptabfrage gemischt werden, sonst überschriebe die eine Antwort die
  Zugehörigkeiten der anderen.
- *Zustandskopplung zweier Listen auf einem Bildschirm:* Wird ein nachgeladener Kandidat verworfen,
  muss auch die Hauptliste den Zustand zeigen (und umgekehrt). Der neue Query-Key liegt deshalb
  unter dem Präfix `['photos', projectId]`; eigener Testfall in `usePhotos.test.tsx`.
- *Seitenweise:* zweite Seite wird mit dem richtigen Offset angefordert (AK 27).
- *Mehrfach-Verwerfen:* zwei schnelle Klicks auf verschiedene Kacheln verwerfen beide (AK 18).
- *Kategorie-Override:* Partition läuft leer → Abschnitt bleibt mit Leerzustand sichtbar,
  Cluster-Überschrift weiter aus dem Meta-Cache, keine Zahl an der leeren Kategorie (AK 10).
- *Endpunkt:* `after_rank` ≥ Partitionsgröße, `after_rank=0`, negatives `after_rank` (422),
  Seitenweise (`limit`/`offset`, `total` bleibt gleich), unbekannte Keys, Keys eines Fremdprojekts,
  kein erfolgreicher Lauf, älterer Lauf ohne Wirkung, 401 ohne Token.

**Coverage-Gate.** Nicht gefährdet — und genau deshalb kein Argument: gemessen liegt das Backend
bei **97 %** (3779 Statements, 128 ungedeckt). Selbst ein vollständig ungetesteter neuer Endpunkt
landete bei ~95 %. Das Gate sagt hier nichts; die Pflichtabdeckung sind die oben namentlich
genannten Fälle, nicht die Prozentzahl. Das Testkonzept
([`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md)) ist um eine
Backend- und eine Frontend-Sektion zu dieser Spec ergänzt.

## Offene Fragen

Keine. Die drei Produktentscheidungen dieser Spec hat Daniel im `spec-writer`-Ablauf getroffen:

1. **Cluster-Zahl = Summe der Kategorie-Zahlen** (gegen die Empfehlung des `architect`, in Kenntnis
   der Doppelzählung bei Nebenkategorien) — siehe ADR 0071 Entscheidung 4.
2. **Weitere Kandidaten sind seitenweise vollständig nachladbar**, statt nur die erste Seite zu
   zeigen.
3. **Mehrere Fotos lassen sich gleichzeitig verwerfen**, statt die bestehende Einfach-Sperre zu
   behalten.

## Out of Scope

- **Ein Verwerfen zurücknehmen.** In der Kuratierungsansicht nicht enthalten; weiterhin über die
  Rasteransicht, Filter "Aussortiert". Durch diese Story ist der Platz dafür allerdings entstanden
  (die Kachel bleibt stehen) — Kandidat für eine eigene Story.
- **Ortsangabe in der Cluster-Überschrift.** Bleibt für einen späteren Ausbau frei;
  `formatClusterHeading()` wird nicht angefasst.
- **Änderungen an Ausschuss-Phase, Ranking-Berechnung, Kategorisierung oder Datenmodell.** Die
  Story bewegt sich vollständig auf der Leseseite.
- **Ein Index auf `photo_rankings` für die Partitionssortierung.** Wäre eine Performance-, keine
  Sicherheits- oder Korrektheitsmaßnahme; nicht Teil dieser Story.
- **`runtimeCaching` für API-Antworten in der PWA.** Nicht Teil dieser Story; falls es später
  kommt, gilt die im Security-Abschnitt verlegte Auflage zum nutzerabhängigen Cache-Schlüssel.
