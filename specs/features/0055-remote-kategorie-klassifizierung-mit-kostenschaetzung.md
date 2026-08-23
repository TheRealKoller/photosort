# 0055 - Remote-Kategorie-Klassifizierung mit Kostenschätzung

**Status:** Accepted
**Erstellt:** 2026-08-23
**Bezug:** [`inbox/0035-remote-klassifizierung-mit-kostenschaetzung.md`](../inbox/0035-remote-klassifizierung-mit-kostenschaetzung.md) (Ursprung, Daniel selbst, interaktive Session), [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (neue ADR dieser Spec), [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md) (bestehende lokale Klassifizierung), [`decisions/0021-top-selection-ranking-kriterien-pipeline.md`](../decisions/0021-top-selection-ranking-kriterien-pipeline.md)/[`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](../decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) (aktuelles Kategorie-/Ranking-Modell), [`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md)/[`decisions/0031-mistral-provider-option-cloud-landmark.md`](../decisions/0031-mistral-provider-option-cloud-landmark.md) (bestehende Cloud-Vision-Anbindung, `landmark`-Kriterium, Vorbild dieser Spec), [`features/0035-klassifizierung-qualitaet-inhalt-recherche.md`](./0035-klassifizierung-qualitaet-inhalt-recherche.md) (Recherchegrundlage), [`features/0054-mistral-provider-option-cloud-landmark.md`](./0054-mistral-provider-option-cloud-landmark.md) (Out-of-Scope-Vormerkung: "Lokale mediapipe-Klassifizierung auf Mistral/Cloud umstellen — separate, spätere Idee", genau diese Spec).

## Ziel

Die bestehende lokale Bild-Kategorisierung (PEOPLE/LANDSCAPE/DETAIL, ADR 0015: mediapipe-Gesichtserkennung + Pillow-Unschärfe-Heuristik) ist Daniel qualitativ zu ungenau. Diese Spec macht eine Remote-Klassifizierung derselben drei Kategorien über die bereits produktiven Cloud-Vision-Provider (Anthropic/Mistral, analog zum `landmark`-Kriterium) verfügbar — als zusätzliches, vergleichbares Signal neben der lokalen Kategorie, nicht als Ersatz. Der Nutzer löst den Lauf manuell per Button aus, sieht vorab eine Kostenschätzung, und kann pro Foto die Remote-Kategorie gezielt als neue, sofort wirksame Kategorie übernehmen, wenn sie die lokale Fehleinschätzung korrigiert.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich Fotos optional durch ein Cloud-Vision-Modell in PEOPLE/LANDSCAPE/DETAIL klassifizieren lassen können, mit Kostenschätzung vor dem Lauf, damit ich bei Qualitätsmängeln der lokalen Klassifizierung eine bessere Alternative habe und einzelne Fehlklassifizierungen gezielt korrigieren kann.

## Akzeptanzkriterien

**Naming-Migration (Consent-Wiederverwendung):**
- [ ] `Project.cloud_landmark_detection_enabled`/`.cloud_landmark_consent_at` werden zu `.cloud_vision_detection_enabled`/`.cloud_vision_consent_at` umbenannt (wertsicheres `ALTER TABLE ... RENAME COLUMN`, keine Neubefüllung); Endpunkt `PUT /projects/{id}/cloud-landmark-consent` wird zu `PUT /projects/{id}/cloud-vision-consent`. Ein Projekt, das die Cloud-Erkennung für `landmark` bereits aktiviert hatte, bleibt danach technisch identisch aktiv — kein Re-Consent nötig, gated ab sofort automatisch auch die neue Remote-Kategorie-Klassifizierung.
- [ ] Migrations-Test verifiziert Werterhaltung über die Umbenennung hinweg (Zwei-Revisionen-Test: Zeile mit alten Spaltennamen vor der Migration einfügen, nach der Migration Wert unter neuem Namen lesen).
- [ ] Kein neuer, separater Consent-Schalter.

**Kostenschätzung:**
- [ ] `GET /projects/{id}/classify-categories-remote/estimate` liefert `candidate_count`, `provider`, `price_per_image_usd`, `estimated_cost_usd = candidate_count * price_per_image_usd` — ermittelt über dieselbe Kandidaten-Selektion wie der tatsächliche Lauf. Funktioniert unabhängig vom Consent-Schalter (auch bei deaktiviertem Consent `200`, kein `403`).
- [ ] `candidate_count=0` liefert weiterhin `200` mit `estimated_cost_usd=0.0`.
- [ ] `COST_PER_IMAGE_USD`-Konstante je Provider ist dokumentiert-unkalibriert (Kommentar mit Quellenverweis/Unsicherheit, analog anderer unkalibrierter Schwellenwerte im Projekt) — `developer` verifiziert Modell-Bild-Token-Kosten bei TDD-Einstieg gegen die aktuelle Preisliste, statt der Schätzung blind zu vertrauen.

**Remote-Klassifizierungs-Lauf:**
- [ ] `POST /projects/{id}/classify-categories-remote` startet einen eigenständigen, asynchronen Job (`run_remote_category_classification`) — `403` ohne Consent, `409` ohne aktuellen erfolgreichen `ScoringRun`, sonst `202`.
- [ ] Kandidatenmenge: alle Fotos mit `PhotoScore.suggested_status IS NULL` (kompletter Ausschuss-Überlebender-Bestand, kein Kandidatenpool-Vorfilter, konsistent mit ADR 0021).
- [ ] Bereits remote-klassifizierte Fotos werden bei Wiederholungsläufen übersprungen (Skip-Verhalten analog `_select_landmark_candidates`); neu hinzugekommene Kandidaten (z.B. durch einen neuen `score-criteria`-Lauf) werden bei einem Folgelauf trotzdem erfasst.
- [ ] Bei jedem erfolgreichen Cloud-Aufruf wird unbedingt genau eine `photo_category_detections`-Zeile geschrieben (`category`/`confidence`/`provider`/`computed_at`) — anders als bei `landmark` kein "nichts erkannt"-Fall.
- [ ] Best-effort ohne Retry: ein einzelner Fehlschlag bricht den Lauf nicht ab, das Foto bleibt beim nächsten Lauf erneut Kandidat.
- [ ] Neue Tabelle `remote_category_classification_runs` (Run-Tracking analog `CriterionScoringRun`, inkl. `last_progress_at`); `worker.py::reap_stalled_runs` bekommt einen vierten Tabellen-Block, ein hängender Lauf wird erkannt und auf `FAILED` gesetzt.
- [ ] Nebenläufigkeit über neues `Settings.remote_category_classification_concurrency` (Default `2`, analog `landmark_api_concurrency`).
- [ ] Bildquelle: ausschließlich die bereits auf 2048×2048 begrenzte `display`-Cache-Variante, nie das Original, kein GPS-/EXIF-Zugriff (identisch zu `landmark`).

**Manuelle Übernahme (Override) mit sofortiger Wirkung:**
- [ ] `PUT /photos/{id}/category-override` übernimmt die bereits gespeicherte Remote-Kategorie für ein Foto (kein Freitext-Body — nur Bestätigung einer serverseitig bereits validierten, vorhandenen Remote-Erkennung). `404` bei fehlendem Foto/Projekt, `409` ohne vorhandene `photo_category_detections`-Zeile oder ohne `PhotoRanking`-Zeile im aktuellen Lauf.
- [ ] Übernahme wirkt **sofort**: neue Funktion `worker.py::reassign_photo_category` verschiebt das Foto synchron im selben API-Request zwischen den zwei betroffenen `(cluster_key, category_key)`-Partitionen und ruft die bestehende `rank_photos`-Funktion nur für diese zwei Partitionen erneut auf — kein neuer Ranking-Algorithmus, kein voller Re-Scoring-Lauf, kein Hintergrund-Job.
- [ ] `DELETE /photos/{id}/category-override` nimmt die Übernahme zurück, rekonstruiert den automatisch abgeleiteten `category_key` über einen frischen `derive_active_categories`/`derive_category_key`-Aufruf auf dem vollständigen Kandidatenpool des Laufs, stellt exakt den Zustand vor dem Override wieder her (`category_key`/`rank_position`/`rank_score` identisch). Idempotent (`204` auch ohne aktiven Override).
- [ ] Additive Spalte `PhotoScore.category_override: str | None`; `run_criterion_scoring` verwendet `category_key = score.category_override or derive_category_key(...)` bei jeder künftigen Partitionsbildung — ein Override übersteht damit auch künftige volle Re-Scoring-Läufe automatisch, ohne Sonderfallcode.
- [ ] Ein Override betrifft ausschließlich den aktuellen (`_latest_scoring_run`) Lauf; kein `409`-Staleness-Guard gegen einen zwischenzeitlich neuen Scoring-Lauf (bewusst, gleiche Risikoklasse wie das bestehende `confirm-ausschuss-gate`-Verhalten).

**Module (Refactoring):**
- [ ] Neues, providerneutrales `cloud_vision.py`, extrahiert aus `landmark.py` (URLs/Modell-IDs/Timeout/Response-Parsing-Helfer: `raise_for_vision_api_status`, `anthropic_response_to_json`/`mistral_response_to_json`) — von beiden Feature-Modulen (`landmark.py`, `remote_classification.py`) genutzt. Bestehende `test_landmark.py`-Fälle bleiben nach dem Refactoring ohne Assertion-Änderung grün.
- [ ] Neues `remote_classification.py`, strukturell analog `landmark.py`: `CategoryDetection`, `CategoryDetectionClientLike`-Protocol, `AnthropicCategoryClient`/`MistralCategoryClient` (`httpx`-REST, kein SDK, `httpx.MockTransport`-testbar), `build_category_classification_client()`-Dispatch-Factory (nutzt `settings.landmark_provider`, kein neues Provider-Setting). `build_category_classification_client()` wird nie in einem automatisierten Test aufgerufen (bestehende Konvention).
- [ ] Kein neues Secret — `ANTHROPIC_API_KEY`/`MISTRAL_API_KEY` werden wiederverwendet.

**Keine Breaking Changes / Scope-Grenzen:**
- [ ] Nur die Kategorie-Zuordnung (PEOPLE/LANDSCAPE/DETAIL) — keine weiteren lokalen Kriterien werden remote-fähig gemacht.
- [ ] `PhotoCriterionScore`/`rank_photos`-Gewichtung selbst bleibt unverändert; die Remote-Kategorie fließt nicht als Kriterium in die Score-Berechnung ein, nur additiv in die Partitionierung (über `category_override`).

**Dokumentation:**
- [ ] `docs/architecture.md` um die neuen Tabellen/den neuen Job/die vier neuen Endpunkte ergänzt.
- [ ] `specs/architecture/0002-testkonzept.md` um die neue Sektion "Synchrone Partitions-Neusortierung + Spalten-Umbenennungs-Migration + geteilter Consent-Schalter für zwei Cloud-Kriterien" ergänzt (bereits im Rahmen dieser Konsultation geschehen).
- [ ] `specs/architecture/0003-securitykonzept.md` Abschnitt "Cloud-Vision-API" providerneutral erweitert (bereits im Rahmen dieser Konsultation geschehen).
- [ ] `specs/architecture/0004-design-system.md` um die zwei neuen UI-Muster ergänzt (bereits im Rahmen dieser Konsultation geschehen).

## Datenmodell-Bezug

Migration mit vier Teilen (siehe [`docs/architecture.md`](../docs/architecture.md)):
1. Umbenennung `Project.cloud_landmark_detection_enabled`/`.cloud_landmark_consent_at` → `.cloud_vision_detection_enabled`/`.cloud_vision_consent_at`.
2. Additiv `PhotoScore.category_override: str | None`.
3. Neue Tabelle `photo_category_detections` (1:1 zu `Photo`: `category`, `confidence`, `provider`, `computed_at`).
4. Neue Tabelle `remote_category_classification_runs` (Run-Tracking analog `CriterionScoringRun`).

Keine Änderung an `PhotoCriterionScore`, `PhotoRanking`-Schema oder dem bestehenden `landmark`-Kriterium selbst.

## Architektur / Umsetzung

Siehe [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Accepted) für die vollständige Begründung. Zusammenfassung:

**Wichtige Klarstellung:** `PhotoScore.category` (ADR 0015) existiert seit ADR 0021/Spec 0037 nicht mehr — die lokale Kategorie eines Fotos lebt heute als `PhotoRanking.category_key`, abgeleitet über `criteria.py::derive_category_key`/`derive_active_categories` (ADR 0023). Der gesamte Entwurf knüpft an diesen aktuellen Stand an.

- **Naming statt neuem Consent-Schalter:** `Project.cloud_landmark_detection_enabled`/`.cloud_landmark_consent_at` → `.cloud_vision_detection_enabled`/`.cloud_vision_consent_at` (Migration, Endpunkt `PUT /projects/{id}/cloud-vision-consent`) — technische Detailentscheidung, kein zweiter Consent-Schalter, wie von Daniel vorgegeben.
- **Neue additive Signalquelle statt achtem Kriterium:** Remote-Kategorie fließt nicht in `PhotoCriterionScore`/`rank_photos` ein, sondern in die neue Tabelle `photo_category_detections`, analog `photo_landmark_detections`.
- **Persistenter Override:** neue Spalte `PhotoScore.category_override: str | None` — `worker.py::run_criterion_scoring` respektiert sie bei jeder künftigen Partitionsbildung (`category_key = score.category_override or derive_category_key(...)`), macht den Override auch über künftige volle Re-Scoring-Läufe hinweg wirksam, ohne Sonderfallcode.
- **Modulstruktur:** neues, niedrigstufiges `cloud_vision.py` (extrahiert aus `landmark.py`: URLs, Modell-IDs, Timeout, `raise_for_vision_api_status`, `anthropic_response_to_json`/`mistral_response_to_json` — bisher schon providerneutral, jetzt public) + neues `remote_classification.py` (strukturell analog `landmark.py`: Protocol, zwei `httpx`-Clients, Dispatch-Factory, wiederverwendet dieselben Secrets/`settings.landmark_provider` — kein neues Secret).
- **Eigener Job, kein Teil von `score-criteria`:** `run_remote_category_classification`/`classify_categories_remote`, eigene Run-Tabelle `remote_category_classification_runs` (Watchdog-Konsequenz: `reap_stalled_runs` bekommt einen vierten Tabellen-Block), eigenes Concurrency-Setting `remote_category_classification_concurrency`, kein Kandidatenpool-Vorfilter (ADR 0021), Skip bereits klassifizierter Fotos.
- **Vier neue Endpunkte:** `GET .../classify-categories-remote/estimate` (Kostenschätzung, nutzt dieselbe Kandidatenermittlung wie der Lauf selbst), `POST .../classify-categories-remote` (Trigger, 403 ohne Consent), `PUT`/`DELETE /photos/{id}/category-override` (bestätigt nur eine bereits vorhandene Remote-Erkennung, kein Freitext).
- **Sofortige Override-Wirkung (architektonisch anspruchsvollster Teil):** neue Funktion `worker.py::reassign_photo_category` — reine Umverteilung zwischen zwei `(cluster_key, category_key)`-Partitionen desselben `CriterionScoringRun`, ruft die bestehende `ranking.py::rank_photos` nur in kleinerem Maßstab synchron im API-Request erneut auf (kein Job, keine neue Ranking-Logik). Die Rücknahme eines Overrides rekonstruiert die dafür nötige `active_categories`-Menge (die sonst nirgends persistiert ist) durch einen frischen Aufruf der bereits vorhandenen `derive_active_categories`/`derive_category_key` über den vollen Kandidatenpool des Laufs.
- **Kostenschätzung:** dokumentiert-unkalibrierte `COST_PER_IMAGE_USD`-Konstante in `remote_classification.py`. Recherchiert gegen offizielle Preisdoku: Anthropic `claude-haiku-4-5` ≈ $0,0019/Bild ($1/$5 pro MTok, offizielle Bild-Token-Formel `⌈B/28⌉×⌈H/28⌉`, Standard-Tier-Cap 1568px/1568 Tokens), Mistral `ministral-3b-2512` ≈ $0,0002–$0,0008/Bild (Preis gesichert, Bild-Token-Formel für dieses Modell nicht abschließend verifizierbar — `developer` soll bei TDD-Einstieg einen echten Testaufruf machen und `usage` auslesen statt der Schätzung zu vertrauen, analog zur bereits etablierten Modell-ID-Verifikationspflicht aus ADR 0025/0031).

## UI/UX

Vom `ux-ui-designer`-Agenten festgelegt (idea-sharpener-Ablauf).

**Trigger + Kostenschätzung:** Neue Section "Remote-Kategorisierung" auf `KuratierungStepPage.tsx` (Pipeline-Schritt "Kuratierung", vor dem bestehenden "Zur Kuratierungsansicht"-Link) — nicht auf `ProjectSettingsPage.tsx` (dort bleibt ausschließlich der Consent-Schalter). Eager-Schätzung (`GET .../estimate` beim Betreten der Seite geladen, nicht erst bei Klick, analog dem bestehenden "Eager-Zähler"-Muster: "~N Fotos · ~$Y" neben dem Button). Proaktive Deaktivierung bei fehlendem Consent (Erklärtext + Link zu den Projekteinstellungen), `candidate_count === 0` ("Alle Fotos bereits klassifiziert"), oder laufendem Run (Busy-Button). Klick öffnet einen Bestätigungsdialog (natives `<dialog>`, `showModal()` — bewusst ohne neues Radix-Paket) mit Fotoanzahl, Anbieter, geschätzten Gesamtkosten und einem expliziten Unsicherheitshinweis ("Schätzung, keine exakte Abrechnung"). Laufender Job: Busy-Button + `<progress>` + Fortschrittstext, identisch zum bestehenden Kriterien-Bewertungs-Muster.

**Anzeige lokal vs. remote + Override:** Erweiterung der bestehenden permanenten Kriterien-Aufschlüsselung (`CriterionDetailsList`/`CriterionDetailsPopover`, Spec 0040/0041) um eine neue Gruppe (nur sichtbar wenn eine Remote-Kategorie existiert): erkannte Kategorie, Konfidenz, Anbieter. Darunter genau eine von drei Zeilen — (1) keine Übersteuerung + Remote weicht ab → Button "Diese Kategorie übernehmen"; (2) aktive Übersteuerung → Hinweis "Manuell übernommen" + Button "Zurücksetzen"; (3) keine Übersteuerung, Remote stimmt bereits überein → reiner Hinweistext. Zusätzlich ein dezenter Kachel-Marker (Stift-Symbol) bei aktiver Übersteuerung, `aria-label="Kategorie manuell übersteuert"`. Erfolg löst eine Query-Invalidierung der Kuratierungsdaten aus — das Foto wechselt sichtbar in die neue Cluster×Kategorie-Sektion.

**Consent-Schalter-Umbenennung:** Label/Erklärtext des bestehenden Switches auf `ProjectSettingsPage.tsx` werden erweitert (z.B. "Cloud-Bilderkennung" statt "Cloud-Sehenswürdigkeit-Erkennung"), da er ab dieser Spec zwei Kriterien gated — reine Textpflege, kein neues UI-Element.

**Zustände:** Leer (`candidate_count === 0`), Ladend (Schätzung inline, laufender Job als Busy-Button, einzelne Override-Aktion als Busy-Button am jeweiligen Foto), Fehler (Alert+Retry-Muster durchgängig), Consent aus (proaktiv disabled + Link).

**Design-System:** zwei neue, bereits dokumentierte Muster in `specs/architecture/0004-design-system.md`: "Bestätigungsdialog vor kostenpflichtiger Aktion" und "Lokal-vs-Remote-Vergleich mit Override-Aktion". Keine neue externe Abhängigkeit.

## Security

**Sicherheitsrelevant: ja.** Zweiter produktiver Cloud-Vision-Datenfluss im Projekt (der erste ist `landmark`, ADR 0025/0031) — vier neue Endpunkte, Umbenennung des bestehenden Consent-Schalters, ein neuer nutzergesteuerter Override-Endpunkt. Vollständige projektweite Einordnung siehe `specs/architecture/0003-securitykonzept.md`, Abschnitt "Cloud-Vision-API" (im Rahmen dieser Konsultation aktualisiert).

**Bedrohungen und Gegenmaßnahmen:**

1. **Consent-Migration:** reines, wert-erhaltendes `ALTER TABLE ... RENAME COLUMN` — ein Bestandsprojekt mit bereits aktivierter `landmark`-Cloud-Erkennung bleibt danach technisch identisch aktiv, kein ungewolltes Zurücksetzen. Der Schalter deckt ab sofort automatisch auch die neue Remote-Kategorie-Klassifizierung ab, ohne erneute Bestätigung — bewusste, bereits in der Architektur-Konsultation abgestimmte Produktentscheidung, keine neue Sicherheitslücke. Der umbenannte Endpunkt muss nachweislich am selben router-weiten `get_current_user`-Torwächter hängen wie zuvor.
2. **Auth-Durchsetzung:** alle vier neuen Endpunkte müssen nachweislich am selben router-weiten `get_current_user`-Torwächter hängen wie alle übrigen `/projects/*`/`/photos/*`-Endpunkte — Muss-Kriterium, testseitig abzudecken.
3. **Override-Endpunkt ohne Injection-Fläche:** `PUT /photos/{id}/category-override` nimmt bewusst keinen Body/kein `category`-Feld entgegen — übernimmt ausschließlich die bereits serverseitig gespeicherte, gegen `REMOTE_CATEGORY_LABELS` validierte Kategorie. Kein beliebiger `category_key`-String einschleusbar. Muss-Kriterium: kein Freitext-Body, kein späterer "wäre praktisch"-Kompromiss.
4. **Datenexposition:** anders als `landmark` gibt es hier keinen inhaltlichen Vorfilter — Kandidatenmenge ist der komplette Ausschuss-Überlebender-Bestand, potenziell ein Vielfaches der bei `landmark` versendeten Foto-Zahl. Muss-Kriterium: ausschließlich die bereits auf 2048×2048 begrenzte `display`-Cache-Variante, nie das Original, kein GPS-/EXIF-Zugriff (bei Implementierung zu verifizieren).
5. **Kostenkontrolle:** ein gestohlenes JWT (bestehendes `localStorage`-Token-Risiko) kann den Lauf mit potenziell mehr Fotos als bei `landmark` auslösen, entsprechend größere Kostenwirkung. Für dieses Zwei-Personen-Familienprojekt als geringes, nicht-null finanzielles Restrisiko akzeptiert (kein Blocker) — Skip bereits klassifizierter Fotos bei Re-Läufen und `remote_category_classification_concurrency` (Default 2) begrenzen zusätzlich.
6. **Secrets:** kein neues Secret — `ANTHROPIC_API_KEY`/`MISTRAL_API_KEY` werden wiederverwendet. `RemoteCategoryClassificationApiError` darf wie `LandmarkApiError` nie API-Key oder Base64-Bilddaten in Meldung/Log einbetten.
7. **DPA/Rechtsraum:** identische Bewertung wie bei `landmark` (dieselben zwei Provider, dieselbe Anbindung) — keine erneute Recherche nötig.

## Teststrategie

Struktur analog Spec 0047/0054, ergänzt um zwei neue Muster (Zwei-Revisionen-Migrationstest, synchrone Teil-Neuberechnung außerhalb eines Jobs). `specs/architecture/0002-testkonzept.md` wurde bereits um die neue Sektion "Synchrone Partitions-Neusortierung + Spalten-Umbenennungs-Migration + geteilter Consent-Schalter für zwei Cloud-Kriterien" ergänzt.

**Testebenen:**
- **Unit:** `cloud_vision.py` direkt sowie als Regressionstest über die bestehenden `test_landmark.py`-Fälle (müssen unverändert grün bleiben). `remote_classification.py`-Clients via `httpx.MockTransport`, `_category_detection_from_json`, `REMOTE_CATEGORY_LABELS`-Validierung (ungültiges Label → Fehler, nicht klemmen — Unterschied zu `landmark`s offenem Confidence-Wertebereich). `build_category_classification_client()` nie automatisiert aufgerufen.
- **Integration:** `run_remote_category_classification` (neue `test_worker_remote_category_classification.py`): Vollkandidatenmenge ohne Vorfilter, Skip-bereits-klassifiziert, Nebenläufigkeit, best-effort-Fehlerisolation, leerer Kandidatenpool, unbedingtes Schreiben, geteiltes Consent-Gate (Aktivieren schaltet beide Cloud-Pfade frei). `reassign_photo_category`: No-op bei gleichem Ziel (Spy-Nachweis 0 Aufrufe von `rank_photos`), korrekte Neubefüllung beider Partitionen, Override-Rücknahme-Exaktheit (Setzen+Zurücknehmen ⇒ identischer Ausgangszustand). Endpunkte inkl. dokumentierter 403/404/409-Fälle.
- **Migration:** Zwei-Revisionen-Test für die Spalten-Umbenennung (bis Vorgänger-Revision migrieren, Zeile mit alten Spaltennamen einfügen, weiter migrieren, Werterhaltung unter neuen Namen per SQL verifizieren, alte Namen als entfernt bestätigen). Standard-Schema-/Cascade-Tests für die neuen Tabellen/Spalten.
- **Watchdog:** vierter Tabellen-Block für `remote_category_classification_runs` in den bestehenden `reap_stalled_runs`-Tests.

**Relevante Edge Cases:**
1. Override bei zwischenzeitlich neuem Scoring-Lauf: kein `409`-Staleness-Guard (bewusst), aber Override betrifft nachweislich nur den aktuellen Lauf.
2. Skip-Verhalten bei wiederholten Läufen: bereits klassifizierte Fotos nicht erneut angefragt, neu hinzugekommene Kandidaten schon.
3. Kostenschätzung bei 0 Kandidaten: `200`, `estimated_cost_usd=0.0`, unabhängig vom Consent-Schalter.
4. Override-Rücknahme reproduziert exakt den Zustand vor dem Override (da `PhotoCriterionScore` durch Overrides nie verändert wird).
5. Naming-Migration bricht bestehende Landmark-Consent-Tests nicht (Regressionspflicht) plus eigener Werterhaltungstest über die Migration selbst.
6. Neue Zielpartition unterhalb der 15%-Kategorie-Häufigkeitsschwelle (ADR 0023) ist beim Override erlaubt (Positivtest, kein Fehler).

## Entscheidungen (2026-08-23, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Scope bewusst auf die Kategorie-Zuordnung begrenzt:** nur PEOPLE/LANDSCAPE/DETAIL, keine weiteren lokalen Kriterien (z.B. Qualitäts-Score) remote-fähig gemacht — von Daniel im Klärungsgespräch explizit so eingegrenzt.
- **Ergänzend statt ersetzend:** Remote-Kategorie wird zusätzlich zur lokalen Kategorie/Ranking gespeichert (neue Tabelle `photo_category_detections`), überschreibt sie nicht automatisch — von Daniel bestätigt.
- **Foto-Umfang bewusst "alle", nicht nur die Kandidatenauswahl:** Daniel hat sich für den kompletten Ausschuss-Überlebenden-Bestand entschieden, nicht nur ein Cluster-Sample. Im Gespräch als konsistent mit dem bestehenden `landmark`-Kriterium eingeordnet, das laut ADR 0021 bereits ohne Kandidatenpool-Vorfilter läuft — keine neue Kostenklasse, nur potenziell mehr Fotos pro Lauf.
- **Consent-Wiederverwendung statt neuem Schalter:** Daniel hat sich explizit für die Mitnutzung des bestehenden `landmark`-Consent-Schalters entschieden (technisch umbenannt zu `cloud_vision_*`, gated künftig beide Kriterien) statt eines zweiten, granulareren Schalters.
- **Manuelle Übernahme mit sofortiger Wirkung (Devil's-Advocate-Ergebnis):** Im Devil's-Advocate-Schritt wurde hinterfragt, was mit der Remote-Kategorie geschehen soll — Daniel hat sich für "manuell übernehmbar" statt "nur Anzeige" entschieden, und im Folgeschritt explizit für sofortige Wirkung auf die Kuratierungs-Partitionierung statt Verzögerung auf den nächsten Scoring-Lauf oder rein kosmetischer Korrektur. Das war der architektonisch anspruchsvollste Teil dieser Spec (siehe `architect`-Konsultation, `worker.py::reassign_photo_category`).
- **Naming-Entscheidung `cloud_landmark_*` → `cloud_vision_*`:** eigenständige technische Detailentscheidung von `architect` (kein Rückfrage-Charakter) — vermeidet einen zweiten Consent-Schalter bei gleichzeitig klarerem, providerneutralem Feldnamen.
- **Neue ADR statt Editieren von ADR 0025/0021/0023:** `architect` hat sich für eine neue ADR-Datei (`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`) entschieden, da diese Spec sowohl eine neue Datenmodell-Grundstruktur (2 neue Tabellen, 1 additive Spalte, 1 Umbenennungs-Migration) als auch ein neues wiederverwendbares Modulmuster (`cloud_vision.py`) einführt.
- **Kostenschätzung als dokumentiert-unkalibrierte Konstante:** da Spec 0035 (Recherche) keine belastbaren fixen $/Bild-Zahlen liefert ("reale Cloud-Kosten nur mit echten Testbildern seriös bezifferbar"), hat `architect` einen pragmatischen, recherchierten Startwert je Provider mit Verifikationspflicht für `developer` festgelegt statt die Kostenschätzung ganz zurückzustellen.
- **Priorität MITTEL, von `requirements-engineer` vorläufig vergeben und nach vollständiger Architektur-/UX-/Test-/Security-Konsultation bestätigt:** strategisch wertvoll (adressiert einen von Daniel aktiv wahrgenommenen Qualitätsmangel, knüpft an die gerade abgeschlossene Cloud-Infrastruktur aus Spec 0047/0054 an), aber nicht blockierend für laufende Arbeit — verdrängt keinen der aktuellen Niedrig-Einträge, Mittel war unbesetzt.

## Offene Fragen

Keine — alle im Sharpening-Gespräch aufgetretenen Unklarheiten (Scope, Ersetzen/Ergänzen, Foto-Umfang, Consent-Mechanismus, Nutzung der Remote-Kategorie, Override-Wirkung) wurden mit Daniel geklärt (siehe Abschnitt "Entscheidungen").

## Out of Scope

- Weitere lokale Kriterien (z.B. Qualitäts-Score, Symmetrie, Komposition) remote-fähig machen — nur die Kategorie-Zuordnung ist Teil dieser Spec.
- Automatisches Ersetzen der lokalen Kategorie ohne manuelle Nutzerbestätigung — die Übernahme bleibt ein expliziter Klick pro Foto.
- Ein zweiter, granularerer Consent-Schalter getrennt für `landmark` und Kategorie-Klassifizierung — bewusst ein gemeinsamer Schalter.
- Batch-API- oder Prompt-Caching-Optimierungen — nur Baseline-REST-Implementierung, analog `landmark` (Spec 0047).
- Automatischer, staleness-sicherer Schutz gegen einen zwischenzeitlich neuen Scoring-Lauf beim Override — bewusst dieselbe Risikoklasse wie das bestehende `confirm-ausschuss-gate`-Verhalten.
- Exakte, kalibrierte Kostenabrechnung — die Kostenschätzung bleibt eine dokumentiert-unkalibrierte Näherung.
