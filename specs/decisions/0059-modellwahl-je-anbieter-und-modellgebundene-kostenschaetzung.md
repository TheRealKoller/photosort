# 0059 - Modellwahl je Anbieter als Betriebseinstellung, Vorab-Schätzung an das Modell gebunden

**Status:** Accepted
**Datum:** 2026-09-06
**Bezug:** [GitHub-Issue #304](https://github.com/TheRealKoller/photosort/issues/304), [`specs/features/0304-cloud-modell-je-anbieter-waehlbar.md`](../features/0304-cloud-modell-je-anbieter-waehlbar.md)

**Ändert eine Festlegung von (Teil-Ablösung):**
- [`decisions/0051-ist-kostenerfassung-remote-laeufe.md`](./0051-ist-kostenerfassung-remote-laeufe.md) **Punkt 2, Absatz „Zwei Preiskonstanten nebeneinander, bewusst"**: `remote_classification.py::COST_PER_IMAGE_USD` (Vorab-Schätzung je **Provider**, hand-nachgerechnet, nicht aus `MODEL_PRICING` abgeleitet) entfällt ersatzlos und wird durch eine Ableitung aus `MODEL_PRICING` plus einer offen gelegten Verbrauchsannahme je Provider ersetzt (Punkt 3 unten). Alle übrigen Festlegungen von ADR 0051 bleiben unverändert in Kraft — insbesondere Punkt 1 (Ist-Kosten aus gemessenem Verbrauch), Punkt 2 „Preisquelle ist eine Code-Konstante, kein Betriebsparameter", Punkt 3 (Persistenz an den Run-Tabellen, `NULL` = „nicht erfasst"), Punkt 4 (Betrag wird beim Laufende eingefroren) und Punkt 5 („nicht erfasst" ist ein struktureller Befund).

**Berührt außerdem (keine Ablösung):**
- [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) und [`decisions/0031-mistral-provider-option-cloud-landmark.md`](./0031-mistral-provider-option-cloud-landmark.md) Punkt 2 („jeweils günstigstes vision-fähiges Modell je Anbieter"): die **Voreinstellung** bleibt exakt dieses Modell. Diese ADR macht sie nur überschreibbar; ohne gesetzte Einstellung ändert sich nichts.
- [`decisions/0031`](./0031-mistral-provider-option-cloud-landmark.md) Punkt 3 / [`decisions/0032`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) Punkt 3 (**ein** Provider-Schalter für beide Cloud-Zwecke): die Modellwahl folgt demselben Muster — **ein** Schalter für beide Zwecke, kein Modell je Zweck.
- [`decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md`](./0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md) Punkt 5 (Vorab-Schätzung am Auslöser): der Ort und der Zweck der Schätzung bleiben unverändert; nur ihre Preisquelle wird ausgetauscht und ihr API-Vertrag um „kein Preis bekannt" erweitert.

## Kontext

Welches Cloud-Modell PhotoSort benutzt, steht je Anbieter fest im Code (`cloud_vision.py::ANTHROPIC_VISION_MODEL`/`MISTRAL_VISION_MODEL`). Ein Modellwechsel — zum Erproben eines stärkeren Modells, oder erzwungen durch eine Abkündigung beim Anbieter — verlangt Codeänderung und Release.

Der schwerere Teil ist ein Defekt, kein Komfortmangel. Es gibt zwei Kostenzahlen im Produkt, und sie sind unterschiedlich geschlüsselt:

- **Ist-Kosten nach dem Lauf** (`pricing.py::MODEL_PRICING`, ADR 0051): je **Modell-ID**. Korrekt — der Preis hängt am Modell.
- **Vorab-Schätzung vor dem Lauf** (`remote_classification.py::COST_PER_IMAGE_USD`, ADR 0032/0050): je **Provider**. Falsch — sie behauptet einen Betrag, der mit dem tatsächlich aufgerufenen Modell nichts zu tun haben muss.

Seit dem Wegfall des Bestätigungsdialogs ([`features/0296`](../features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md)) ist diese Schätzung die **einzige verbliebene Absicherung** gegen ungewollte Cloud-Kosten. Eine Modellwahl einzuführen, ohne die Schätzung vorher an das Modell zu binden, hieße: die Absicherung wird in dem Moment unwahr, in dem die neue Fähigkeit zum ersten Mal genutzt wird — und zwar still.

Der bisherige Schutz gegen genau das ist ein Invariantentest (`test_pricing.py::TestModelPricingRegistry`), der die `*_VISION_MODEL`-Konstanten gegen `MODEL_PRICING` prüft. Er greift für die Ist-Rechnung, aber **nicht** für die Schätzung: `COST_PER_IMAGE_USD` ist über Provider-Schlüssel geführt und bleibt bei jedem Modellwechsel formal vollständig. Der Test kann nicht anschlagen, weil ihm die Frage fehlt.

## Entscheidung

### 1. Modellwahl ist eine zweite Betriebseinstellung neben der Anbieterwahl, mit Prüfung beim Prozessstart

Neues `Settings`-Feld `landmark_model: str = ""` (Umgebungsvariable `LANDMARK_MODEL`), leer = „Voreinstellung des eingestellten Anbieters". Auflösung über eine Methode nach dem bereits etablierten Muster von `resolved_rate_limit_storage_uri()`:

```python
def resolved_landmark_model(self) -> str:
    return self.landmark_model or default_vision_model_for_provider(self.landmark_provider)
```

Ein `@model_validator(mode="after")` prüft einen gesetzten Wert gegen die Registry **des eingestellten Anbieters** (Punkt 2) und wirft sonst einen `ValidationError` mit der Liste der erlaubten Werte. Wegen `settings = Settings()` auf Modulebene schlägt das beim **Prozessstart** fehl, nicht mitten im Lauf — dasselbe Verhalten, das `landmark_provider` über sein `Literal` schon heute hat („kein stiller Fallback"). Ein für den Anbieter `anthropic` gültiges, aber unter `mistral` eingestelltes Modell ist damit ebenfalls ein Startfehler.

**Name `LANDMARK_MODEL`, bewusst:** er erbt die Ungenauigkeit von `LANDMARK_PROVIDER` (beide gelten für **beide** Cloud-Anteile, nicht nur für Sehenswürdigkeiten). Der genauere Name `CLOUD_VISION_MODEL` zerrisse das Paar, und ein Umbenennen von `LANDMARK_PROVIDER` wäre eine für diese Story sachfremde, für Daniel breaking Betriebsänderung (`.env`, `docker-compose.yml`, `docker-compose.e2e.yml`, CI, Doku). Die Zusammengehörigkeit der beiden Schalter wiegt hier schwerer als die Wortgenauigkeit; die Doppeltwirkung steht in `.env.example` und `docs/setup.md` bei beiden Feldern.

**Betriebseinstellung, kein Projekt-/Laufparameter** — identisch zu ADR 0031 Punkt 3: die Wahl betrifft Kosten und Vertragslage des Betreibers, nicht die Arbeit am einzelnen Projekt. Kein UI-Selektor, keine Spalte an `Project`.

**Kein Datenverlust, rücknehmbar:** die Einstellung wirkt ausschließlich auf künftige Aufrufe. Bereits geschriebene Ergebnisse und eingefrorene Beträge bleiben unberührt; Zurückstellen auf den alten Wert (oder Leeren) stellt den vorherigen Zustand vollständig her.

### 2. Eine Registry der wählbaren Modelle je Anbieter in `cloud_vision.py`, erstes Element ist die Voreinstellung

```python
VISION_MODELS_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "anthropic": (ANTHROPIC_VISION_MODEL, ...),
    "mistral":   (MISTRAL_VISION_MODEL, ...),
}
```

Geordnetes Tupel statt Menge: die Reihenfolge trägt eine Aussage (erstes Element = Voreinstellung des Anbieters), und ein Tupel ist unveränderlich — dieselbe Bauform wie die übrigen Registries im Projekt (`CATEGORY_REGISTRY`, `CRITERION_REGISTRY`). `VISION_MODEL_BY_PROVIDER`/`vision_model_for_provider()` gehen darin auf und werden zu `default_vision_model_for_provider()`, das die Voreinstellung aus der Registry liest; die dort dokumentierte defensive Rückfallregel („unbekannter Provider fällt auf seinen eigenen Namen zurück, damit ein Lauf als *nicht erfasst* auffällt statt an einem `KeyError` zu sterben") bleibt wörtlich erhalten. Sie ist durch das `Literal` auf `landmark_provider` und den Validator aus Punkt 1 heute unerreichbar — genau deshalb kostet sie nichts und wird nicht entfernt.

**Ort `cloud_vision.py`:** dort leben die Modell-IDs bereits, das Modul ist provider- und featureneutral und importiert bewusst nichts aus `photosort`. Mit dieser ADR wird es zusätzlich zur **Abhängigkeit von `config.py`** (der Validator braucht die Registry). Daraus folgt eine harte Regel, die im Modulkopf zu vermerken ist: **`cloud_vision.py` darf `photosort.config` niemals importieren** — sonst entsteht ein Importzyklus. Ein Bedarf danach ist der Anlass, die Registry in ein eigenes, abhängigkeitsfreies Modul zu ziehen, nicht den Zyklus zu bauen.

**Nur geprüfte Werte, keine freie Eingabe:** die Registry ist die einzige Quelle dafür, was wählbar ist. Es gibt keinen Pfad, über den eine beliebige Modellbezeichnung an einen Anbieter geschickt wird.

### 3. Die Vorab-Schätzung wird aus `MODEL_PRICING` abgeleitet — `COST_PER_IMAGE_USD` entfällt

Neu in `pricing.py`, direkt neben `MODEL_PRICING`:

```python
@dataclass(frozen=True)
class AssumedImageUsage:          # Verbrauchsannahme EINES Bildes, je Provider
    input_tokens: int
    output_tokens: int

ASSUMED_USAGE_BY_PROVIDER: dict[str, AssumedImageUsage] = {
    "anthropic": AssumedImageUsage(input_tokens=4_600, output_tokens=120),
    "mistral":   AssumedImageUsage(input_tokens=2_880, output_tokens=120),
}

def estimate_usd_per_image(model: str, provider: str) -> float | None:
    ...  # compute_cost_usd(model, TokenUsage(**assumed)) - kein neuer Rechenweg
```

Die Schätzung ist damit `compute_cost_usd` über einer angenommenen statt einer gemessenen Tokenzahl. Eine neue Modell-ID braucht genau **eine** gepflegte Tatsache — ihre verifizierten Token-Preise — und die Schätzung folgt automatisch.

**Warum das die Festlegung aus ADR 0051 Punkt 2 ablöst.** ADR 0051 hat die Ableitung geprüft und verworfen, mit zwei Gründen: sie „erzwänge eine dokumentierte Annahme über Bild- und Antwort-Tokens als Code-Struktur" und „würde den heute geltenden, gegen die reale Bildquelle nachgerechneten Schätzwert bei jeder Preispflege stillschweigend verschieben". Beide Gründe kippen mit dieser Story:

- Die Annahme **als Code-Struktur** ist jetzt der Gewinn, nicht der Preis. Heute steckt sie in einem 60-Zeilen-Kommentar, den jemand für jedes neue Modell von Hand nachrechnen müsste. Als benanntes, testbares Datum steht sie an einer Stelle, ist beim Review sichtbar und gilt für alle Modelle eines Anbieters gleichermaßen — sie hängt an unserer Bildquelle (`display`-Variante, 2048 px lange Kante) und unserem Prompt, nicht am Modell.
- Das „stillschweigende Verschieben bei Preispflege" ist genau das **geforderte** Verhalten. Die Story verlangt, dass die Schätzung dem eingestellten Modell folgt; ein von der Preisliste entkoppelter Handwert ist bei wählbaren Modellen keine Absicherung mehr, sondern der gemeldete Defekt.

ADR 0051s eigentlicher Kern — Preise sind eine belegpflichtige Tatsachenbehauptung im Code, kein `.env`-Parameter — bleibt vollständig erhalten und wird durch Punkt 5 sogar verschärft.

**Kalibrierungsauflage (macht „ohne gesetzte Einstellung exakt wie bisher" prüfbar):** die beiden Annahmewerte sind so gewählt, dass die abgeleitete Schätzung für das jeweilige **Voreinstellungs-Modell** die bisherigen Konstanten exakt reproduziert:

| Provider | Voreinstellungs-Modell | Rechnung | Ergebnis | bisher |
|---|---|---|---|---|
| anthropic | `claude-haiku-4-5` | 4 600 · $1,00/MTok + 120 · $5,00/MTok | **$0,0052** | $0,0052 |
| mistral | `ministral-3b-2512` | 2 880 · $0,10/MTok + 120 · $0,10/MTok | **$0,0003** | $0,0003 |

Die Zahlen sind nicht rückwärts erfunden, sondern die bereits dokumentierte Herleitung: 4 600 = ~3 900 Bild- + ~700 Prompt-Tokens (Anthropics offizielle Formel `px·px/750`, gerechnet auf die real versendete `display`-Variante), 120 Ausgabe-Tokens; 2 880 = ~2 030 Bild- + ~850 Prompt-Tokens, innerhalb der für die Pixtral-/Ministral-Familie dokumentierten Bandbreite von 1 000–4 000 Bild-Tokens (Mistral veröffentlicht keine offizielle Bild-Token-Formel — dieser Anteil bleibt ausdrücklich **dokumentiert-unkalibriert**, wie schon bisher). Die vorhandene Herleitungs-Dokumentation wandert mit nach `pricing.py`; ein Test pinnt beide Tabellenwerte.

Nicht geändert wird die bewusste Grobheit der Schätzung im Übrigen: ein Preis je Bild für **beide** Cloud-Anteile (der Landmark-Prompt ist kürzer als der Kategorie-Prompt), Überschätzung wird der Unterschätzung vorgezogen, `estimated_cost_usd = candidate_count · price_per_image_usd`.

### 4. Kein hinterlegter Preis heißt „kein Betrag", nicht „0"

`estimate_usd_per_image` liefert `None` für ein Modell ohne Preiseintrag — dieselbe Semantik wie `compute_cost_usd` (ADR 0051 Punkt 2). Der API-Vertrag von `ClassificationEstimateOut` wird entsprechend erweitert: `price_per_image_usd: float | None`, `estimated_cost_usd: float | None`, zusätzlich das neue Feld `model: str`. Die Oberfläche zeigt in diesem Fall an derselben Stelle statt eines Betrags einen Hinweis, dass für das eingestellte Modell kein Preis hinterlegt ist.

Das Feld `model` ist eine bewusste, kleine Ergänzung über den Buchstaben der Akzeptanzkriterien hinaus: die Antwort der Schätzung soll selbst aussagen, worauf sie sich bezieht — sonst bliebe genau die Verwechslung möglich, die diese Story behebt (Antwortfeld `provider`, gemeinter Bezug: Modell). Es kostet ein Feld und macht das Akzeptanzkriterium „die Schätzung passt zum eingestellten Modell" direkt prüfbar.

**Der Hinweis ist die zweite Verteidigungslinie, nicht der Normalfall.** Die erste ist der erweiterte Invariantentest: **jedes** Modell in `VISION_MODELS_BY_PROVIDER` muss einen Eintrag in `MODEL_PRICING` haben, und die Provider-Schlüssel der Registry müssen mit den `Literal`-Werten von `landmark_provider` und den Schlüsseln von `ASSUMED_USAGE_BY_PROVIDER` übereinstimmen (per `typing.get_args` ermittelt, nicht gegen eine zweite Liste). Bei grünem Test ist der `None`-Pfad unerreichbar. Er wird trotzdem gebaut, weil eine Absicherung, die ausschließlich aus einem Test besteht, mit diesem Test verschwindet — und weil der Ausfall genau die Zahl beträfe, die das Produkt gegen ungewollte Kosten schützt.

**Bewusst nicht:** der Start wird bei unbekanntem Preis nicht blockiert. Das wäre neues Verhalten, das kein Akzeptanzkriterium verlangt, und es bestrafte den Betreiber für einen Zustand, den er an der Oberfläche nicht auflösen kann.

### 5. Ein Preis ohne belegte Verifikation kommt nicht ins Produkt — strukturell, nicht per Kommentar

`ModelPricing` bekommt zwei Pflichtfelder: `source_url: str` und `verified_on: date`. Die Verifikationsangabe ist damit nicht mehr ein Kommentar, den man vergessen kann, sondern ein Feld, ohne das der Eintrag nicht konstruierbar ist. Ein Test prüft für jedes Registry-Modell, dass beide Felder gefüllt sind und `verified_on` nicht in der Zukunft liegt.

Daraus folgen zwei Regeln:

1. **Ein Modell, dessen Preis nicht gegen die offizielle Anbieterdokumentation verifiziert werden konnte, wird nicht in `VISION_MODELS_BY_PROVIDER` aufgenommen.** Ein wählbares Modell ohne Preis wäre ein wählbarer Zustand ohne Kostenabsicherung — genau die Lage, die diese Story beseitigen soll.
2. **Nichtverifizierbarkeit ist ein Blocker, kein Anlass zum Schätzen.** Ein aus Websuch-Aggregaten oder Analogieschluss („symmetrisch wie das kleinere Modell der Familie") gewonnener Preis darf nicht als verifizierter Wert eingetragen werden. Kann die umsetzende Sitzung die offizielle Preisseite nicht erreichen (im Umfeld dieser Story ist `docs.mistral.ai` durch den Egress-Proxy blockiert), meldet sie das als blockierende Rückfrage an Daniel zurück, statt einen Wert zu setzen. Das gilt für die Modell-**ID** genauso wie für den Preis: beide werden im selben Schritt gegen dieselbe offizielle Quelle bestätigt.

Bewusst **nicht** eingeführt: eine automatische Verfallsprüfung („Preis älter als N Monate"). Sie brächte ein zeitabhängig fehlschlagendes CI und ist eine eigene Frage.

### 6. Das benutzte Modell wird je **Lauf** persistiert, nicht je Foto

Zwei additive, nullable Spalten, eine Migration (auf `f4a5b6c7d8e9`):

| Tabelle | Spalte | Bedeutung |
|---|---|---|
| `criterion_scoring_runs` | `landmark_model: str \| None` | Modell-ID der Landmark-Phase dieses Laufs. Präfix wie bei `landmark_cost_usd`. |
| `remote_category_classification_runs` | `model: str \| None` | Modell-ID dieses Laufs. Kein Präfix — ein Lauf, ein Zweck. |

`NULL` heißt „nicht erfasst" (Zeile aus der Zeit vor dieser Migration), nicht „kein Modell" — exakt das `ScanRun.total_files`-Idiom von ADR 0051 Punkt 3. Geschrieben wird die Spalte an **derselben Stelle** wie der eingefrorene Betrag (im `finally` der jeweiligen Phase, mit demselben Commit) und aus **demselben** lokalen Wert (Punkt 7).

**Warum an der Lauf-Zeile und nicht an den bestehenden `provider`-Spalten der Foto-Zeilen** (`PhotoLandmarkDetection`, `PhotoCategoryClassification`, `PhotoFineLabel`), was die naheliegende Alternative wäre:

- Der eingefrorene Betrag steht an der Lauf-Zeile. Das Modell ist die **Preisgrundlage** dieses Betrags — ohne es ist ein historischer Betrag weder erklärbar noch nach einer erkannten Preiskorrektur nachrechenbar. Es gehört neben die Tokens und den Betrag, deren Aufbewahrung ADR 0051 Punkt 3 aus genau diesem Grund begründet.
- **Entscheidend:** eine Foto-Zeile entsteht nur bei einem *Treffer*. `_upsert_landmark_detection` läuft nur, wenn tatsächlich ein Name erkannt wurde. Ein Lauf, der 500 Aufrufe bezahlt und nichts erkennt, hinterließe an den Foto-Zeilen keine Spur des Modells — bei einer Angabe, deren Zweck die Erklärbarkeit ausgegebenen Geldes ist, ist das disqualifizierend.
- Das Modell ist über einen Lauf konstant. Es an N Foto-Zeilen zu wiederholen speicherte dieselbe Aussage tausendfach und ließe sie trotzdem lückenhaft.

Die bestehenden `provider`-Spalten je Foto bleiben unverändert; sie beantworten eine andere Frage (welchem Anbieter wurde dieses Bild übermittelt — eine Datenschutz-, keine Kostenfrage).

**Kein Lesepfad in der Oberfläche.** Das ist dieselbe eng begrenzte Ausnahme von „keine persistierte Zahl ohne Lesepfad" (ADR 0049 Entwurfsentscheidung 7), die ADR 0051 Punkt 3 für Tokens und Aufrufzahl bereits begründet hat, aus demselben Grund: die Angabe existiert nur im Moment des Laufs und ist danach unwiederbringlich, und der Adressat ist der Betreiber, nicht der Anwender. Die Statistikseite um eine Modellspalte zu erweitern ist eine eigene, spätere Story — die Story hier verlangt ausdrücklich keinen Modellvergleich im Produkt.

### 7. Genau eine Modellauflösung je Phase, durchgereicht statt mehrfach gelesen

Der Worker liest das Modell **einmal** je Cloud-Phase in eine lokale Variable (`model = settings.resolved_landmark_model()`, vor der Foto-Schleife) und benutzt denselben Wert für alle drei Zwecke: Bau des Clients, `compute_cost_usd` beim Einfrieren des Betrags, und die neue Modellspalte. Dafür bekommen die beiden Client-Factories einen Parameter — `build_landmark_client(model: str)` / `build_category_classification_client(model: str)`, die injizierten Signaturen im Worker entsprechend `Callable[[str], ...]`; `_try_build` wird mit `lambda: build_...(model)` aufgerufen. Die Clients nehmen das Modell im Konstruktor entgegen und setzen es in den Request-Body, statt eine Modulkonstante zu lesen.

Begründung: die Aussage „der angezeigte, der abgerechnete und der tatsächlich aufgerufene Wert sind derselbe" wird dadurch **strukturell** wahr statt durch drei zufällig übereinstimmende Lesevorgänge derselben globalen `settings`. Sie ist außerdem testbar — eine gefälschte Factory kann festhalten, welches Modell sie bekommen hat, und der Client mit `httpx.MockTransport` prüfen, was im `"model"`-Feld des Request-Bodys landet. `build_landmark_client`/`build_category_classification_client` selbst laufen weiterhin nie in einem automatisierten Test (echtes Secret); der auflösende Teil wandert mit `resolved_landmark_model()` in die `Settings` und ist damit erstmals direkt geprüft.

Die feature-eigenen Aliase `ANTHROPIC_LANDMARK_MODEL`/`MISTRAL_LANDMARK_MODEL` (`landmark.py`) und `ANTHROPIC_CATEGORY_MODEL`/`MISTRAL_CATEGORY_MODEL` (`remote_classification.py`) entfallen ersatzlos, ebenso der Test, der ihre Gleichheit mit den `*_VISION_MODEL`-Konstanten überwacht (`test_pricing.py::test_the_category_phase_models_are_still_aliases_of_the_vision_models`). Sie existierten als Platzhalter für eine mögliche spätere Entkopplung je Zweck; die Story entscheidet diese Frage ausdrücklich in die andere Richtung („wirkt auf beide Cloud-Anteile einheitlich; nicht zwei Modelle nebeneinander"). Ein Alias, der nur noch auf einen durchgereichten Parameter zeigt, wäre ein Platzhalter ohne Platz.

## Konsequenzen

- **Neu:** `Settings.landmark_model` + `resolved_landmark_model()` + Startvalidator; `VISION_MODELS_BY_PROVIDER`/`default_vision_model_for_provider` in `cloud_vision.py`; `AssumedImageUsage`/`ASSUMED_USAGE_BY_PROVIDER`/`estimate_usd_per_image` und die Felder `source_url`/`verified_on` an `ModelPricing` in `pricing.py`; zwei Modellspalten samt einer Alembic-Migration; Umgebungsvariable `LANDMARK_MODEL` in `.env.example` und beiden Backend-Diensten in `docker-compose.yml`.
- **Entfällt:** `remote_classification.py::COST_PER_IMAGE_USD`, `cloud_vision.py::VISION_MODEL_BY_PROVIDER`/`vision_model_for_provider`, die vier `*_LANDMARK_MODEL`/`*_CATEGORY_MODEL`-Aliase und der Alias-Wächtertest.
- **Geändert:** Signaturen beider Client-Factories und der zugehörigen injizierten Worker-Parameter; `ClassificationEstimateOut` wird in zwei Feldern nullable und bekommt `model` (Frontend-Typ und Anzeige ziehen nach).
- **API-Vertrag:** `price_per_image_usd`/`estimated_cost_usd` können jetzt `null` sein. Einziger Konsument ist das eigene Frontend; ein externer Client existiert nicht.
- **Doku (Owner `architect`, im selben PR):** `.env.example` und `docs/setup.md` bekommen `LANDMARK_MODEL` samt Voreinstellung und wählbaren Werten je Anbieter neben `LANDMARK_PROVIDER`; `docs/architecture.md` nimmt die beiden neuen Spalten ins Datenmodell und den geänderten Weg der Schätzung in die Worker-/Backend-Beschreibung auf.
- **Dauerhafte Pflegelast, ehrlich benannt:** die Registry ist eine kuratierte Liste, die veraltet. Ein vom Anbieter abgekündigtes Modell bleibt so lange wählbar, bis jemand es entfernt — und fällt dann erst beim Lauf auf (Aufruf schlägt fehl, best-effort, kein Laufabbruch), nicht beim Start. Das ist bewusst hingenommen: die Alternative wäre eine Modell-Abfrage beim Anbieter zur Startzeit, also eine Netzabhängigkeit im Hochfahren, für eine Liste mit zwei bis vier Einträgen.
- **Restrisiko:** die Genauigkeit der Schätzung hängt weiterhin an einer unkalibrierten Annahme über Bild-Tokens, für Mistral ohne offizielle Formel. Diese ADR ändert daran nichts — sie sorgt nur dafür, dass die Annahme an **einer** sichtbaren Stelle steht und der Preisfaktor immer zum eingestellten Modell gehört. Ersatzverfahren unverändert (ADR 0051): Abgleich der ersten realen Abrechnung mit den Ist-Kosten der Statistikseite.
