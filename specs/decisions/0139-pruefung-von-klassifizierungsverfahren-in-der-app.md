# 0139 - Prüfung von Klassifizierungsverfahren in der App: eigener Prüflauf, eigene Tabellen, Modell je Seite

**Status:** Accepted
**Datum:** 2026-11-07
**Bezug:** Issue [#616](https://github.com/TheRealKoller/photosort/issues/616), ADR
[`0138`](./0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md) (Punkt 8 wird durch diese
Entscheidung abgelöst, alle übrigen Punkte gelten weiter), ADR
[`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md) (Löschumfang)
**Umfang:** über dem Richtwert von rund 100 Zeilen, weil Trennung vom geltenden Bestand,
Modellwahl je Seite, Eye-Fassungen und Exportgrenze gemeinsam eine Entscheidung bilden.

## Kontext

Welche Klassifizierung für PhotoSort taugt, soll am Foto beurteilt werden: zwei Verfahren
nebeneinander (Cloud gegen Eye, zwei Cloud-Modelle, zwei Fassungen der Eye-Übersetzung), ein
gemeinsames Urteil je Fall, eine Übersicht in der App und eine Exportdatei für die KI. ADR 0138
Punkt 8 legt den Vergleich als CLI ohne Endpunkt fest. Anbieter und Modell sind je Installation
fest eingestellt, und die rohe Eye-Antwort wird nicht gespeichert.

## Entscheidung

### 1. Die Prüfung ist ein Feature der App; das CLI `eye_comparison` entfällt

ADR 0138 Punkt 8 wird abgelöst. Prüfungen werden über Endpunkte angelegt, ausgeführt und
beurteilt. `python -m photosort.eye_comparison` wird entfernt. Die reine Vergleichslogik zieht in
das neue reine Modul `classification_comparison.py`. Dazu gehören die Präsenz über
`selection.motif_is_present`, die Zählung je Zweck und die Stichprobe mit Seed je Zweck. Das Modul
vergleicht Seite A mit Seite B statt Cloud mit Eye. Damit gibt es genau eine Zähl- und
Stichprobenlogik.

Ein Zweck wird für ein Foto nur verglichen, wenn beide Seiten dazu eine Aussage haben. Es gibt
**vier** Zwecke: `motifs`, `motif_feature`, `excluded_document`, `album_level`.
`motifs`, `excluded_document` und `album_level` zählen Fotos. `motif_feature` zählt Paare aus Foto
und Motiv - die einzelnen Motive, deren Präsenz zwischen den Seiten abweicht. Die vier Zwecke
haben je einen eigenen Deckel und je eine eigene Zählung (übereinstimmend, abweichend, vorgelegt):
eine gemeinsame Grenze ließe die Motiv-Merkmale den Platz von Ausschluss und Albumstufe fressen.
Folge, die die Anzeige tragen muss: ein Foto kann als Merkmal-Fall vorgelegt werden, ohne als
Motive-Fall vorgelegt zu sein, und umgekehrt; die Einheit steht je Zweck an der Zählung („Fotos“
gegen „Merkmale“).

### 2. Ein eigener Prüflauf, der ausschließlich in eigene Tabellen schreibt

Ein neuer arq-Job `run_classification_review` mit `max_tries=1` klassifiziert die Prüfmenge
**für beide Seiten neu**. Er ruft weder `run_classification`, `run_criterion_scoring`,
`run_remote_category_classification`, `_run_eye_phase` noch `upsert_assessment` auf, und er führt
keine Landmark-, Ranking- oder Auswahlberechnung aus. Er schreibt in keine bestehende Tabelle,
auch nicht in `photo_cloud_vision_errors`. Die Prüfmenge sind alle Fotos mit
`survives_ausschuss()`.

Eine lokale Seite rechnet den lokalen Vektor ohne Sehenswürdigkeits-Beitrag. Dieser Beitrag ist
ein Cloud-Teilschritt, und die Herkunft der Seite nennt die Auslassung. Ein Start setzt dieselben
Vorbedingungen voraus wie `POST …/classify`: einen erfolgreichen Ausschusslauf, ein bestätigtes
Gate und für jede Cloud-Seite die Projekteinwilligung.

**Invariante:** Nur diese Module lesen oder schreiben die Prüftabellen:
`classification_review.py` (Job), `api/classification_reviews.py`, `project_deletion.py` sowie die
Modell- und Migrationsdateien. Kein Prüfpfad schreibt eine andere Tabelle als diese. Das sichern
zwei Tests:

- ein Strukturwächter über Importe und Schreibziele;
- ein Verhaltenstest, der nach einer Prüfung einen normalen Lauf startet und Kandidatenmenge,
  Schätzung und geltende Ergebnisse mit einem Lauf ohne Prüfung vergleicht.

Wird die Invariante verletzt, ändert eine Prüfung Motive, Dokumentausschluss, Album-Entwurf oder
die Kandidatenauswahl des nächsten Cloud-Laufs. Bei Albumtauglichkeit und Cloud-Kopfzeile ist das
zugleich ein Kostenfehler.

### 3. Datenmodell

- `classification_reviews`: Projekt, anlegender Nutzer, Status (`ScanStatus`), Teilschritt,
  Prüfgröße, Seed, Fotozahlen, `last_progress_at` (Fortschritts-Watchdog), Zeitpunkte,
  Fehlermeldung.
- `classification_review_sides` (PK Prüfung + Seite `a`/`b`): Verfahrensart
  `cloud|eye|local`, `provider`, `model`, `eye_model_revision`, `eye_mapping_version`. Dazu die
  eingefrorene Schätzung `estimated_cost_usd` (Beleg, keine Eingabe) und die Ist-Kosten im Idiom
  der Remote-Läufe (`api_calls`, `failed_calls`, Tokens, `cost_usd`; `NULL` = nicht erfasst).
- `classification_review_results` (PK Prüfung + Seite + Foto) mit `excluded_document` und
  `album_level`, beide nullable. `NULL` heißt hier „dieses Verfahren trifft dazu keine Aussage“.
  Lokal hat weder Ausschuss noch Albumstufe, und ein erfundenes `false` würde jede
  Dokumentaufnahme zur Abweichung machen. Dazu kommt `classification_review_result_strengths`
  mit allen acht Motiven.
- `classification_review_cases`: die vorgelegten Fälle. Jeder Fall hat Prüfung, Foto, die
  **Fotoposition** (die laufende Nummer des Fotos in der eingefrorenen Prüfmenge, einmal
  geschrieben) und den Zweck (`motifs|motif_feature|excluded_document|album_level`); `motif_key`
  steht nur bei `motif_feature`. Ein Fall ist eindeutig je Prüfung, Foto, Zweck und Merkmal. Die
  Fotoposition ist der Anker jeder Anzeige und des Exports - ein Foto kann mehrere Fälle tragen,
  und ohne sie wäre „das dritte Foto der Prüfung“ in Oberfläche und Export nicht dieselbe Stelle.
- `classification_review_verdicts` (PK = Fall): `a_better|b_better|both_ok|both_wrong`,
  `updated_by_user_id`, `updated_at`. Es gibt **ein** Urteil je Fall, nicht eines je Nutzer.
  Setzen und Ändern ist ein Upsert, der letzte Schreiber gewinnt.

Der Teilschritt der Anzeige ist ein eigener Aufzählungswert (`side_a|side_b|cases`; `NULL`, sobald
der Lauf beendet ist) und kein Satz: die Oberfläche formuliert, der Server benennt einen Zustand.
Modellfreitext wird nicht gespeichert, also weder Feinlabels noch die Begründung der
Albumtauglichkeit. Zählungen entstehen beim Lesen aus den Ergebnissen, mit derselben Funktion, die
die Stichprobe zieht. Alle Tabellen fallen über `project_deletion.py` mit dem Projekt. Eine
laufende Prüfung sperrt die Projektlöschung (`409`) wie die übrigen Lauftypen.
`reap_stalled_runs` setzt eine hängende Prüfung auf `FAILED`.

Die **Fotoposition** entsteht aus der einmal eingefrorenen Prüfmenge in aufsteigender
`photo_id`-Reihenfolge und wird mit den Fällen geschrieben. Fallliste und Export lesen dieselbe
gespeicherte Nummer; keine der beiden Stellen leitet sie neu ab. Innerhalb eines Fotos sortiert
der Server nach Zweck in der Reihenfolge aus Punkt 1 und bei `motif_feature` nach der
Motiv-Registry - dieselbe Ordnung, in der die Fotoansicht die acht Motive zeigt.

### 4. Das Cloud-Modell ist eine Eigenschaft der Seite, nicht nur der Installation

Eine Cloud-Seite nennt ihr Modell aus `VISION_MODELS_BY_PROVIDER`. Der Anbieter folgt aus
`provider_for_vision_model(model)`. `build_category_classification_client(model)` und die
Drosselung leiten den Anbieter künftig aus dem Modell ab statt aus `settings.landmark_provider`.
Für den normalen Lauf ist das wirkungsgleich, weil `landmark_model` gegen diesen Anbieter
validiert ist. Wählbar ist nur ein Modell, dessen Anbieter einen API-Schlüssel hat. Die Einstellung
`landmark_provider`/`landmark_model` des normalen Laufs bleibt unberührt.

### 5. Eye-Übersetzungen sind benannte Fassungen, die nebeneinander aufrufbar sind

`eye_mapping.py` führt eine Fassungstabelle `MAPPING_VERSION → Abbildung`. `analyze(payload,
version)` rechnet jede eingetragene Fassung. Eine Fassung wird nie umgeschrieben; eine neue kommt
hinzu. Hat eine Prüfung zwei Eye-Seiten, wird der Dienst **einmal** je Foto gerufen, und beide
Fassungen werden auf dieselbe Antwort im Speicher angewendet. Die Antwort wird weiterhin nicht
gespeichert. Die Herkunft einer Eye-Seite ist `MODEL_REVISION` plus Fassung.

### 6. Kosten vor dem Start

Die Schätzung je Cloud-Seite ist die Fotozahl der Prüfmenge × `estimate_usd_per_image(model,
provider)`. Es gilt dieselbe Regel wie bei `_estimate_part`: `null` heißt „nicht schätzbar“, nie
„kostenlos“. Eye und lokal sind `0.0` und werden als kostenfrei angezeigt. Der Startaufruf
berechnet die Schätzung serverseitig neu und friert sie an der Seite ein.

Die Prüfgröße gilt **je Zweck** und ist auf 1 bis 200 begrenzt, Vorgabe 30. Die drei Zahlen liefert
der Options-Endpunkt; die Oberfläche trägt keine eigene Kopie. Die Untergrenze 1 schließt die
Prüfung ohne einen einzigen vorgelegten Fall aus („keine Abweichung“ ist eine Zählung, keine
Prüfung), die Obergrenze hält die Prüfung bei einem Sitzungsgegenstand und den Export bei einer
lesbaren Datei. Überschreitet eine Anfrage die Grenzen, ist das ein `422` und keine stille
Begrenzung - eine gekappte Prüfgröße wäre eine andere Prüfung als die angefragte. Die Größe gilt
für jeden der vier Zwecke einzeln; die Zahl der vorgelegten Fälle liegt damit zwischen 0 und
4 × Prüfgröße.

### 7. Export ohne Inhaltsangaben

`GET …/export` liefert JSON mit genau diesen Inhalten:

- Herkunft beider Seiten, Prüfgröße und Seed;
- Zählungen je Zweck und Merkmal sowie die Urteilszählungen;
- je Fall die Fotoposition, der Zweck, `motif_key`, beide Rohwerte und das Urteil. Dieselbe Nummer
  trägt die Anzeige, damit ein Urteil ohne Inhaltsangabe auf seinen Fall verweist.

Ausgeschlossen sind Bilddaten, Foto-Ids, Pfade, Dateinamen, Zeitstempel, Orte und GPS, Personen-
und Sehenswürdigkeitsnamen, Projektname, Nutzer und Modellfreitext. Der Dateiname der
Exportdatei enthält nur die Prüfungs-Id. Ein fester Schlüsselsatz im Serialisierer und ein
Strukturtest über dessen Eingaben sichern das.

## Konsequenzen

- ADR 0138 bekommt im Kopf den Vermerk `**Teilweise abgelöst:** Punkt 8 durch ADR 0139`.
- Spec 0610 bleibt `Implemented`. Ihr Werkzeug entfällt mit dieser Umsetzung.
- „Alt gegen neu“ ist erst prüfbar, wenn es eine zweite Eye-Fassung gibt. Dafür muss #615 seine
  Fassung **neben** `eye-4.2.3/v1` eintragen statt an ihrer Stelle.
- Cloud-Kosten einer Prüfung sind echtes Geld. Die Projektstatistik führt sie als eigenen Posten
  „Prüfungen“ neben Sehenswürdigkeiten und Kategorien, nach derselben Lückenregel.
