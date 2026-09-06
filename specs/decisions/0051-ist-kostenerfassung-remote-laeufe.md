# 0051 - Ist-Kostenerfassung der Remote-Läufe aus dem tatsächlichen Token-Verbrauch

**Status:** Accepted
**Datum:** 2026-09-02
**Bezug:** [GitHub-Issue #207](https://github.com/TheRealKoller/photosort/issues/207), [`specs/features/0207-projekt-statistikseite.md`](../features/0207-projekt-statistikseite.md)

**Berührt außerdem (keine Ablösung):**
- [`decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md`](./0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md) Punkt 5 (Vorab-Schätzung über `COST_PER_IMAGE_USD`): die Schätzung **vor** dem Lauf bleibt unverändert bestehen und behält ihre eigene Konstante. Diese ADR ergänzt sie um eine zweite, unabhängige Größe — die Ist-Kosten **nach** dem Lauf.
- [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) Punkt 5 und [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) Punkt 6 (Run-Tracking über `criterion_scoring_runs`/`remote_category_classification_runs`): beide Tabellen bekommen je vier additive Spalten und werden damit zusätzlich zum Ort der Kosten-Buchführung eines Laufs.

## Kontext

Für die beiden Remote-Anteile des Klassifizierungslaufs (Sehenswürdigkeiten-Erkennung, Kategorie-Klassifizierung) fließt echtes Geld. Sichtbar ist davon heute ausschließlich eine **Schätzung vor dem Lauf** (`GET /projects/{id}/classify/estimate`, ADR 0050 Punkt 5): Kandidatenzahl × `COST_PER_IMAGE_USD[provider]`, eine dokumentiert-unkalibrierte Pauschale je Bild. Diese Zahl wird nirgends festgehalten — sie ist nach dem Klick verschwunden.

Damit existiert im Produkt **keine einzige Stelle, an der nachträglich erkennbar wäre, was ein Projekt tatsächlich gekostet hat**. Die Schätzung taugt dafür auch grundsätzlich nicht: sie basiert auf einer angenommenen Bildauflösung und einer angenommenen Antwortlänge, und ihre Kandidatenzahl ist für den Landmark-Anteil strukturell eine Vorhersage (ADR 0050 Punkt 5) — wie viele Aufrufe der Lauf am Ende wirklich abgesetzt hat und wie groß die Bilder darin waren, weiß nur der Lauf selbst.

Beide Provider liefern den tatsächlichen Verbrauch in **jeder** API-Antwort mit (Anthropic: `usage.input_tokens`/`usage.output_tokens`; Mistral: `usage.prompt_tokens`/`usage.completion_tokens`). Diese Information wird heute gelesen und verworfen — sie existiert genau einmal, im Moment der Antwort, und ist danach unwiederbringlich.

## Entscheidung

### 1. Ist-Kosten beruhen auf dem gemessenen Token-Verbrauch, nicht auf einer Pauschale

Jeder Cloud-Vision-Client gibt den `usage`-Block seiner Antwort als providerneutrales `TokenUsage(input_tokens, output_tokens)` mit dem Ergebnis zurück (`cloud_vision.py`, neben den bereits dort liegenden providerneutralen Envelope-Helfern). Der Worker summiert diese Werte über alle **erfolgreichen** Aufrufe einer Phase und berechnet daraus am Laufende genau einen Betrag.

Bewusst **nicht** gewählt: „Anzahl der tatsächlich abgesetzten Aufrufe × `COST_PER_IMAGE_USD`". Das wäre deutlich weniger Code (die Clients blieben unangetastet), aber die resultierende Zahl bliebe eine Schätzung — nur mit korrekterem Multiplikator. Das Akzeptanzkriterium der Story („beruhen auf dem tatsächlichen Verbrauch der durchgeführten Läufe, nicht auf einer Vorab-Schätzung") wäre damit dem Wortlaut nach verfehlt, und der Hauptzweck der Seite (Kostenkontrolle bei echtem Geld) hinge weiter an einer nie kalibrierten Annahme über Bildgrößen.

Ein fehlender oder strukturell unerwarteter `usage`-Block ist **kein Fehler**: die Extraktion liefert dann `None`, der Aufruf trägt nichts zur Summe bei und der Lauf protokolliert eine WARNING-Zeile (Muster ADR 0034). Eine erfolgreiche Klassifizierung darf niemals daran scheitern, dass die Abrechnungsangabe fehlt.

### 2. Preisquelle: eine Code-Konstante je Modell-ID, kein Betriebsparameter

Neues Modul `pricing.py`:

```python
@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_mtok: float
    output_usd_per_mtok: float

MODEL_PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_VISION_MODEL: ModelPricing(1.00, 5.00),   # claude-haiku-4-5
    MISTRAL_VISION_MODEL:   ModelPricing(0.10, 0.10),   # ministral-3b-2512
}

def compute_cost_usd(model: str, usage: TokenUsage) -> float | None
```

Der Schlüssel ist die **Modell-ID**, nicht der Provider: der Preis hängt am Modell, und die Modell-IDs werden bereits in `cloud_vision.py` zentral geführt. Ein hier nicht hinterlegtes Modell liefert `None` statt eines stillen `0.0` — ein Modellwechsel ohne Preispflege fällt damit als „nicht erfasst" auf, statt sich als kostenloser Lauf zu tarnen.

Code-Konstante statt `Settings`-Feld/Umgebungsvariable (gleiche Einordnung wie `VISION_REQUEST_TIMEOUT_SECONDS` in ADR 0025 Punkt 3, umgekehrte Richtung als bei `landmark_api_concurrency`): eine Preisänderung ist kein Deployment-Parameter, sondern eine belegpflichtige Tatsachenbehauptung. Sie gehört in einen Commit mit Datum, Quelle und Review — nicht in eine `.env`, in der sie unbemerkt jeden historischen Betrag umdeuten könnte.

**Zwei Preiskonstanten nebeneinander, bewusst:** `remote_classification.py::COST_PER_IMAGE_USD` (Vorab-Schätzung, Preis **pro Bild** inkl. angenommener Token-Zahlen) bleibt unverändert bestehen; `MODEL_PRICING` (Ist-Rechnung, Preis **pro Token**) tritt daneben. Eine Ableitung der einen aus der anderen wurde geprüft und verworfen: sie erzwänge eine dokumentierte Annahme über Bild- und Antwort-Tokens als Code-Struktur und würde den heute geltenden, gegen die reale Bildquelle nachgerechneten Schätzwert bei jeder Preispflege stillschweigend verschieben. Beide Konstanten verweisen stattdessen wechselseitig aufeinander mit dem Hinweis, dass ein Preiswechsel beide betrifft.

> **Nachtrag 2026-09-06 — dieser Absatz ist abgelöst.** Mit Spec [`0304`](../features/0304-cloud-modell-je-anbieter-waehlbar.md) und ADR [`0059`](./0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md) Punkt 3 entfällt `COST_PER_IMAGE_USD` ersatzlos; die Vorab-Schätzung wird über `pricing.py::estimate_usd_per_image()` aus `MODEL_PRICING` abgeleitet. Es gibt seitdem **eine** Preisquelle mit zwei Ableitungen, nicht zwei Konstanten nebeneinander. Grund: sobald das Modell je Anbieter einstellbar ist, war die providergeschlüsselte Schätzkonstante nach einem Modellwechsel unbemerkt falsch — beide oben genannten Gegengründe kippen damit (die dokumentierte Token-Annahme als Code-Struktur ist jetzt der Gewinn statt der Preis, und das „stillschweigende Verschieben bei Preispflege" ist genau das geforderte Verhalten). Abgelöst ist **nur** dieser Absatz — der Kern von Punkt 2 (Preise sind eine belegpflichtige Tatsachenbehauptung im Code, kein `.env`-Parameter) bleibt vollständig in Kraft und wird durch ADR 0059 Punkt 5 sogar verschärft. Alle übrigen Punkte dieser ADR sind unberührt; sie ist deshalb **nicht** `Superseded`.

> Nachtrag-Konvention analog Spec 0033/0045: abgelöste Einzelaussagen werden datiert benannt, statt eine im Übrigen gültige Entscheidung als Ganzes zu verwerfen.

### 3. Persistenz an den bestehenden Run-Tabellen, keine neue Kosten-Tabelle

Je vier additive Spalten, eine Migration:

| Tabelle | Spalten | Bedeutung |
|---|---|---|
| `criterion_scoring_runs` | `landmark_api_calls`, `landmark_input_tokens`, `landmark_output_tokens`, `landmark_cost_usd` | Der Landmark-Anteil dieses Klassifizierungslaufs. Präfix, weil die Tabelle seit ADR 0050 den Gesamtlauf trägt und die Kriterien-Phase selbst nichts kostet. |
| `remote_category_classification_runs` | `api_calls`, `input_tokens`, `output_tokens`, `cost_usd` | Der Kategorie-Anteil. Kein Präfix — dieser Lauf hat genau einen Zweck. |

Alle acht Spalten sind **nullable**, mit Python-seitigem Default `0`. Das ist exakt das bereits etablierte `ScanRun.total_files`-Idiom: `NULL` heißt „nicht erfasst" (Zeile aus der Zeit vor dieser Migration), `0` heißt „erfasst, es sind keine Kosten angefallen". Ein neuer Lauf bekommt durch den Modell-Default immer `0` und wird vom Worker mit den echten Summen überschrieben — es braucht keinen zusätzlichen „wurde erfasst"-Schalter und keinen Sonderfall für einen Lauf ohne Cloud-Nutzung.

Bewusst **nicht** gewählt:

- **Eine eigene Kosten-Tabelle** (`remote_api_costs` mit `project_id`, `purpose`, `run_id`). Sie bräuchte einen polymorphen oder doppelt-nullbaren Lauf-Bezug, weil die beiden Zwecke an zwei verschiedenen Run-Tabellen hängen — und beantwortete keine Frage, die vier Spalten an der jeweils zuständigen Run-Zeile nicht schon beantworten. Die Run-Tabellen führen bereits die übrige Lauf-Buchführung (`photos_total`, `photos_processed`, `suggestions_found`); Kosten sind derselbe Datentyp.
- **Eine Zeile je einzelnem API-Aufruf.** Gäbe Kosten pro Foto — eine Kennzahl, die die Story ausdrücklich nicht verlangt („keine Kennzahlen über den genannten Katalog hinaus") — und ließe die Tabelle mit jedem Lauf um die Kandidatenzahl wachsen.

**Warum Tokens und Aufrufzahl mitgespeichert werden, obwohl die Seite sie nicht anzeigt:** das ist eine bewusste, eng begrenzte Ausnahme von der sonst geltenden Linie „keine persistierte Zahl ohne Lesepfad" (ADR 0049 Entwurfsentscheidung 7). Der Betrag ist eine **Interpretation** des Verbrauchs durch eine Preiskonstante, die sich ändern wird und die heute selbst als „dokumentiert-unkalibriert" geführt wird. Ohne den zugrunde liegenden Verbrauch ist ein historischer Betrag weder erklärbar noch — nach einer erkannten Preiskorrektur — nachrechenbar; der Verbrauch existiert aber nur im Moment der API-Antwort und ist danach für immer verloren. Bei einer Kennzahl, deren einziger Zweck Kostenkontrolle über echtes Geld ist, wiegt diese Unumkehrbarkeit schwerer als die Sparsamkeitsregel. Für `float` statt `Numeric`: die Beträge liegen im Cent-Bereich, es findet keine Buchhaltung statt, und `float` ist der im gesamten Datenmodell durchgehend verwendete Fließkomma-Typ; gerundet wird erst bei der Ausgabe.

### 4. Der Betrag wird beim Laufende eingefroren, nicht beim Lesen berechnet

`landmark_cost_usd`/`cost_usd` werden einmal am Ende der jeweiligen Phase geschrieben. Eine spätere Preisänderung verändert damit **keinen** bereits ausgewiesenen historischen Betrag — sie gilt nur für künftige Läufe. Genau das ist bei einer Ausgaben-Rückschau die richtige Semantik: was bezahlt wurde, wurde zu den damaligen Preisen bezahlt. Die Alternative (Kosten beim Lesen aus gespeicherten Tokens berechnen) würde die Vergangenheit bei jeder Preispflege umschreiben.

### 5. „Nicht erfasst" ist ein struktureller Befund, keine Schätzung

Je Zweck wird zusätzlich zum Betrag ein Kennzeichen ausgeliefert, dass die ausgewiesene Summe für dieses Projekt unvollständig ist. Es ist wahr, wenn **mindestens einer** der beiden folgenden Befunde zutrifft:

**(a) Altlauf vor der Erfassung** — beide Teilbedingungen gemeinsam:

1. Es existiert mindestens ein Lauf des jeweiligen Typs mit `... cost_usd IS NULL` (also aus der Zeit vor dieser Migration), **und**
2. es existiert im Projekt mindestens ein Ergebnis dieser Art (`photo_landmark_detections`-Zeile bzw. `photo_category_classifications`-Zeile).

Die zweite Teilbedingung verhindert den häufigsten Fehlalarm: ein Projekt, das die Cloud-Nutzung nie aktiviert hatte, hat zwar Altläufe, aber nachweislich nichts ausgegeben — es soll „0,00 $" ohne Warnhinweis zeigen.

**(b) Erfassungslücke trotz Erfassung** — es existiert ein Lauf mit `... api_calls > 0` und dabei `... cost_usd IS NULL` **oder** `... cost_usd = 0`.

Bei Token-Preisen größer null ist ein Betrag von exakt `0` bei nachweislich abgesetzten Aufrufen strukturell unmöglich; er entsteht ausschließlich, wenn kein Verbrauch ermittelt werden konnte (fehlender `usage`-Block, Punkt 1) oder das Modell nicht bepreist ist (`compute_cost_usd` → `None`, Punkt 2). Diese Kombination ist damit ein zuverlässiger Indikator, kein heuristischer Verdacht. Ohne Befund (b) zeigte die Seite in genau diesen Fällen „0,00 $" ohne jeden Vorbehalt — auf einer Seite, deren Zweck Kostenkontrolle über echtes Geld ist, ist das die gefährlichste Falschaussage, weil sie wie eine belastbare Antwort aussieht. Der WARNING-Eintrag aus Punkt 1 erreicht den Nutzer nicht; das Kennzeichen tut es. Es kostet keine zusätzliche Spalte — die Aufrufzahl wird nach Punkt 3 ohnehin gespeichert. (Entscheidung Daniels im `spec-writer`-Ablauf zu Spec 0207.)

Für keinen der beiden Befunde wird **etwas geschätzt oder hochgerechnet** (Akzeptanzkriterium der Story); die Zahl bleibt die Summe des tatsächlich Erfassten, der Hinweis erklärt, dass sie nicht vollständig ist. Beide Befunde führen zum selben Kennzeichen und damit zur selben Aussage („die Summe ist unvollständig"), weil die Unterscheidung ihrer Ursachen für die Kostenkontrolle folgenlos ist — sie steht im Log.

**Bewusst getragene Grenze von Befund (a) beim Zweck `landmark`:** `photo_landmark_detections`-Zeilen entstehen nur, wenn tatsächlich eine Sehenswürdigkeit benannt wurde. Ein Altlauf, der viele kostenpflichtige Aufrufe abgesetzt und nichts gefunden hat, hinterlässt keine Ergebniszeile und löst Befund (a) deshalb nicht aus. Für Läufe **nach** dieser Migration schließt Befund (b) die Lücke (die Aufrufzahl steht dann an der Lauf-Zeile); für Altläufe bleibt sie bestehen und ist nicht nachträglich schließbar, weil die Aufrufzahl von damals nirgends existiert. Das Verhalten wird per Test festgeschrieben.

Bewusst nicht gewählt: eine projektweite `cost_tracking_since`-Spalte. Sie bräuchte eine neunte Spalte für eine Information, die die `NULL`-Läufe bereits tragen.

### 6. Fehlgeschlagene Aufrufe tragen nichts bei — dokumentierte Untererfassung

Ein Aufruf, der mit 4xx/5xx oder Timeout endet, liefert keinen auswertbaren `usage`-Block und geht deshalb nicht in die Summe ein. Bei einem abgelehnten Request fallen real auch keine Kosten an; bei einem Timeout nach begonnener Generierung kann eine kleine, nicht messbare Differenz entstehen. Das wird bewusst getragen statt geschätzt: eine erfundene Zahl an dieser Stelle widerspräche dem Kern dieser ADR. Die Fehlschläge selbst bleiben über `photo_cloud_vision_errors` sichtbar und werden auf derselben Statistikseite ausgewiesen — die Untererfassung ist damit für den Leser einordbar.

### 7. Währung: USD, wie abgerechnet, ohne Umrechnung

Beide Provider rechnen in USD ab. Der gespeicherte und angezeigte Betrag ist USD und wird als solcher beschriftet. Eine Umrechnung in EUR wurde verworfen: sie erforderte einen Wechselkurs — also entweder eine neue externe Abhängigkeit mit laufenden Kosten und Ausfallverhalten, oder eine gepflegte Kurs-Konstante, die den Betrag genau um den Fehler verfälschte, den diese ADR beseitigen soll.

## Begründung

Der Kern des Problems ist, dass die einzige Information, aus der sich echte Kosten ergeben, **flüchtig** ist: sie steht in jeder API-Antwort und wird bisher weggeworfen. Jede Lösung, die sie nicht im Moment des Aufrufs festhält, kann anschließend nur noch schätzen — unabhängig davon, wie sorgfältig sie das tut. Deshalb liegt der gesamte Eingriff dieser ADR an genau zwei Stellen: die Antwort trägt ihren Verbrauch bis zum Worker, und der Worker schreibt ihn samt daraus berechnetem Betrag an die ohnehin vorhandene Lauf-Zeile.

Alles Weitere (Aggregation, Aufschlüsselung nach Zweck, „nicht erfasst") folgt daraus als reine Lesequery über acht Spalten — ohne neue Tabelle, ohne neue externe Abhängigkeit, ohne Hintergrundprozess.

## Konsequenzen

- **Positiv:** Erstmals ist beantwortbar, was ein Projekt tatsächlich gekostet hat, aufgeschlüsselt nach Zweck. Die Zahl ist belegt (Tokens + Aufrufzahl liegen daneben) und bleibt auch nach einer Preisänderung korrekt, weil sie eingefroren ist. Ein nicht bepreistes Modell und eine fehlende `usage`-Angabe fallen auf, statt still zu 0 zu werden.
- **Negativ / bewusst getragen:** Zwei Preiskonstanten (Schätzung pro Bild, Ist-Preis pro Token) müssen bei einem Modell-/Preiswechsel gemeinsam gepflegt werden — beide tragen dazu einen gegenseitigen Verweis. Die Rückgabewerte beider Vision-Clients bekommen ein zusätzliches, optionales Feld (Test-Doubles bleiben durch den Default kompatibel). Tokens und Aufrufzahl sind persistierte Daten ohne Anzeigepfad. Läufe vor dieser Migration bleiben dauerhaft „nicht erfasst" — das ist beabsichtigt, nicht nachholbar und in der Story ausdrücklich so gewollt.
- **Folgearbeit:** Sollte je eine projektübergreifende Kostenübersicht gewünscht werden (in Story 0207 ausdrücklich out of scope), ist sie über dieselben acht Spalten ohne Datenmodell-Änderung erreichbar — die Kosten hängen bereits am Lauf, und der Lauf am Projekt.
