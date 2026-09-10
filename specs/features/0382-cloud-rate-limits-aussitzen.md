# 0382 - Vollständige Cloud-Läufe trotz Anbieter-Rate-Limits

**Status:** Accepted
**Erstellt:** 2026-09-10
**Bezug:** [Issue #382](https://github.com/TheRealKoller/photosort/issues/382)

## Ziel

Ein Klassifizierungslauf soll auch dann vollständige Ergebnisse liefern, wenn der Cloud-Anbieter
die Anfragerate begrenzt. Heute meldet der Anbieter nach einer Weile einen Rate-Limit-Fehler
(429), und das betroffene Foto bleibt in diesem Lauf ohne Ergebnis. Der Ausfall ist still: Er
fällt nur auf, wenn man gezielt in die Statistik oder ins Lauf-Protokoll sieht, und er lässt sich
nur beheben, indem der Lauf von Hand erneut angestoßen wird — bei größeren Importen wiederholt.
Betroffen ist damit jeder, der einen größeren Bestand einliest; besonders spürbar auf dem derzeit
gewählten Modellpfad, auf dem das Limit regelmäßig erreicht wird.

Der Nutzen ist Verlässlichkeit statt Tempo: Ein Lauf, der länger dauert, aber fertig wird, ist
einem schnellen Lauf mit unsichtbaren Lücken vorzuziehen.

## User Story

Als Nutzer, der einen größeren Fotobestand einliest, möchte ich, dass PhotoSort die Anfragen an
den Cloud-Anbieter selbst so verteilt und bei einer Drosselung so lange wartet, wie es nötig ist,
damit am Ende eines Laufs kein Foto allein deshalb ohne Ergebnis bleibt, weil der Anbieter zu
viele Anfragen auf einmal bekommen hat.

## Akzeptanzkriterien

Gegenüber dem Issue-Body durch `test-engineer` auf Testbarkeit geschärft; die fachliche Aussage
ist unverändert, ergänzt sind die konkreten Werte und Orte, an denen sie prüfbar wird.

- [ ] **K1** Antwortet der Anbieter mit HTTP `429`, wird **dieselbe** Anfrage nach einer Wartezeit
      erneut gestellt statt das Foto zu überspringen — bis zu
      `VISION_MAX_RATE_LIMIT_ATTEMPTS = 5` Versuchen insgesamt (also höchstens vier
      Wiederholungen). Folgt auf ein `429` ein `200`, ist dessen Ergebnis das Ergebnis des
      Aufrufs, und der Lauf zählt dafür **keinen** `failed_call`.
- [ ] **K2** Liegt ein auswertbarer `Retry-After`-Antwortheader vor, bestimmt er die Wartezeit — in
      beiden vom HTTP-Standard erlaubten Formen (Ganzzahl-Sekunden und HTTP-Datum, ein naives
      Datum ohne Zeitzone als UTC gelesen). „Nicht auswertbar" ist ausdrücklich **kein Fehler**,
      sondern „keine Angabe": fehlender, leerer, unparsbarer, nicht endlicher (`nan`/`inf`),
      `<= 0` oder in der Vergangenheit liegender Wert. `retry-after-ms` wird nicht ausgewertet.
- [ ] **K3** Ohne Anbieterangabe greift die verdoppelnde Staffel `2 s, 4 s, 8 s, 16 s`
      (`VISION_INITIAL_RETRY_WAIT_SECONDS = 2.0`, Verdopplung je Versuch). Der Staffelwert hängt am
      **Versuchszähler**, nicht daran, wie oft die Staffel bisher gegriffen hat — eine einzelne
      Anbieterangabe dazwischen setzt sie nicht zurück. Jede Wartezeit, aus welcher Quelle auch
      immer, ist auf `VISION_MAX_SINGLE_WAIT_SECONDS = 60.0` gedeckelt.
- [ ] **K4** Vor **jedem** Absenden — erster Versuch wie jede Wiederholung — reiht sich die Anfrage
      in einen Schrittmacher ein, der einen Mindestabstand von `60 / Anfragen-pro-Minute` Sekunden
      zwischen zwei Anfragen an denselben Anbieter hält (kein Token-Bucket, kein Stoß). Es gibt
      **genau eine** Schrittmacher-Instanz je Anbieter und Prozess; beide Cloud-Teilschritte und
      mehrere gleichzeitig laufende Läufe teilen sie sich. Die Rate ist über
      `CLOUD_VISION_REQUESTS_PER_MINUTE` einstellbar (`ge=0`, Voreinstellung `0` = „Voreinstellung
      des Anbieters"); die Anbieter-Voreinstellungen sind `anthropic: 60`, `mistral: 40`.
- [ ] **K5** Jeder andere Fehlschlag führt **ohne jede Wiederholung** und mit **genau einem**
      HTTP-Versuch sofort zum Überspringen des Fotos: Netzwerkfehler/Zeitüberschreitung, `5xx`
      **einschließlich Anthropics `529`**, `401`, `403`, jeder andere `4xx`, unerwartete
      Antwortstruktur. Fehlerklasse, Meldungstext, `failed_calls`, die
      `photo_cloud_vision_errors`-Zeile und `cloud_error_message` sind dabei wortgleich die von
      heute.
- [ ] **K6** Verteilung und Wiederholung liegen in **einer** Funktion
      (`cloud_vision.py::post_vision_request`), durch die alle vier Aufrufstellen gehen
      (`AnthropicLandmarkClient.detect`, `MistralLandmarkClient.detect`,
      `AnthropicCategoryClient.classify`, `MistralCategoryClient.classify`). Die Einheitlichkeit
      über beide Cloud-Phasen und beide Anbieter ist damit strukturell erfüllt, nicht durch vier
      gepflegte Kopien. Der Schrittmacher ist an allen vier Klassen ein Schlüsselwortparameter
      **ohne Default**.
- [ ] **K7** Ein Lauf darf spürbar länger dauern; die bestehenden Zeitgrenzen bleiben wirksam. Je
      Anfrage gilt hart: höchstens 5 Versuche, höchstens `VISION_RETRY_BUDGET_SECONDS = 120.0`
      summierte Wartezeit, höchstens 60.0 s je Wartevorgang. Reicht das Restbudget für die
      geforderte Wartezeit nicht, wird **sofort aufgegeben statt gekürzt gewartet**. Der schlimmste
      Fall je Anfrage ist damit `120 + 5 × 60 = 420 s` gegen `STALL_THRESHOLD = 15 min` — als
      Invariantentest festgeschrieben. Ein Abbruch (`asyncio.CancelledError` aus
      `JOB_TIMEOUT_SECONDS` oder einem Worker-Shutdown) läuft durch den Wartevorgang hindurch und
      wird **nicht** in die feature-eigene Fehlerklasse umgewandelt.
- [ ] **K8** Im Lauf-Protokoll steht je Wiederholung **eine** `WARNING`-Zeile mit Anbieter,
      Versuchszähler, gewarteter Zeit und deren Herkunft (Anbieterangabe oder Staffel), und je
      Cloud-Teilschritt **höchstens eine** `WARNING`-Zusammenfassung (eingereihte Anfragen,
      summierte Wartezeit, Wiederholungen) — letztere nur, wenn in **diesem** Teilschritt
      tatsächlich gewartet wurde, und ausschließlich aus der **Differenz** der Zählerstände dieses
      Teilschritts. Keine dieser Zeilen enthält den rohen Headerwert, `response.text`, `.headers`
      oder `.json()`.
- [ ] **K9** Ein Lauf, dessen Fotos heute wegen der Drosselung ohne Ergebnis bleiben, liefert
      danach für dieselben Fotos ein Ergebnis: Bei einem Anbieter, der auf `429` ein `200` folgen
      lässt, entsteht die Ergebniszeile (`photo_landmark_detections` bzw.
      `photo_category_classifications`), `failed_calls` bleibt `0` und es entsteht **keine**
      `photo_cloud_vision_errors`-Zeile. Bei einem dauerhaft mit `429` antwortenden Anbieter bleibt
      es beim heutigen Verhalten: Foto übersprungen, `failed_calls == 1`, Fehlerzeile geschrieben,
      Lauf endet regulär mit `SUCCESS`.
- [ ] **K10** `.env.example`, `docs/setup.md` und `docs/architecture.md` nennen
      `CLOUD_VISION_REQUESTS_PER_MINUTE` mit derselben Voreinstellung (`0`, ausdrücklich **nicht**
      leer), denselben Anbieter-Voreinstellungen (60/40) und denselben Budget-Zahlen wie der Code.
      Weicht die Umsetzung ab, ziehen die drei Dateien im selben Pull Request mit.

### Anmerkungen zu K2, K3 und K7

Drei Stellen, an denen die geschärfte Fassung eine Grenze sichtbar macht, die der Issue-Wortlaut
(„so lange wartet, wie es nötig ist") so nicht erwarten lässt. Die fachliche Aussage bleibt; die
Grenzen sind in ADR [`0074`](../decisions/0074-cloud-vision-schrittmacher-je-anbieter-und-wiederholung-nur-bei-429.md)
bereits entschieden und werden hier nur prüfbar benannt:

- **Ein Anbieter, der mehr als 60 s verlangt, bekommt sie nicht** (Deckel aus K3). Es wird nach
  60 s erneut angeklopft; hilft das über das Budget hinweg nicht, endet die Anfrage im gewohnten
  Überspringen. „Aussitzen" ist damit auf gut zwei Minuten je Foto begrenzt, nicht unbegrenzt.
- **Ein `429` ohne jede Aussicht auf Erfolg kostet trotzdem vier zusätzliche Versuche** —
  Anthropic verwendet denselben Statuscode bei erreichter Ausgabenobergrenze. Bewusst hingenommen
  und ausdrücklich Out of Scope; der Schaden ist durch das Budget gedeckelt und abgewiesene
  Anfragen werden nicht abgerechnet.
- **Die Staffel wird von einer Anbieterangabe nicht zurückgesetzt** (K3). Diese Festlegung
  schreiben weder Issue noch ADR aus; sie ist so gewählt, weil ein Rücksetzen einem Anbieter
  erlaubte, mit einer einzigen kleinen Angabe die gesamte Staffel flachzuhalten. Der Testfall
  nagelt sie fest: „ohne Header / mit Header `5` / ohne Header" ergibt `2 s`, `5 s`, `8 s` — nicht
  `2 s`, `5 s`, `4 s`.

## Datenmodell-Bezug

Keiner. Die Story bewegt sich vollständig in der Cloud-Client-Schicht: keine Tabelle, keine
Spalte, keine Migration, kein neues Antwortfeld. Siehe
[`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Grundlage:** ADR [`0074`](../decisions/0074-cloud-vision-schrittmacher-je-anbieter-und-wiederholung-nur-bei-429.md)
(mit dieser Story angelegt). Die Story bewegt sich vollständig in der **Cloud-Client-Schicht**:
keine Tabelle, keine Spalte, keine Migration, kein Antwortfeld, keine Oberfläche. Der
Fehlerpfad des Workers (`_log_cloud_vision_failure`, `_record_cloud_vision_error`,
`failed_calls`, `cloud_error_message`) bleibt **unverändert** — er wird nach erschöpftem
Wiederholungsbudget genauso erreicht wie heute nach dem ersten `429`.

`docs/architecture.md`, `docs/setup.md` und `.env.example` sind bereits mit der Entscheidung
aktualisiert (`architect`, im selben Branch). Wer beim Umsetzen von den dort dokumentierten
Namen oder Voreinstellungen abweicht, muss die drei Dateien mitziehen — sie sind die
Betriebsdoku dieser Variable, nicht eine Nacherzählung.

### Entwurfsentscheidungen

> **Drei Nachträge gehen diesem Abschnitt vor**, dort wo sie ihm widersprechen — sie stammen aus
> den nachgelagerten Konsultationen und stehen begründet unter `## Entscheidungen`:
> (1) `post_vision_request` wartet ausschließlich über den `sleep` des Schrittmachers, nie über
> ein eigenes `asyncio.sleep` (`test-engineer`, sonst warten die Client-Tests real);
> (2) `retry_after_seconds` bekommt `*, now: datetime | None = None`, und die Instanzbildung in
> `cloud_vision_throttle.py` liegt in einer reinen Funktion über einem `Settings`-Objekt
> (`test-engineer`); (3) `math.isfinite` ist Pflicht — `min(float("nan"), 60.0)` liefert `nan`,
> die Deckelung allein reicht nicht (`security-engineer`, siehe `## Security` Punkt 1/2).

**1. Ein einziger neuer Aufrufpfad: `cloud_vision.py::post_vision_request`.**
Die vier Cloud-Aufrufstellen (`AnthropicLandmarkClient.detect`, `MistralLandmarkClient.detect`,
`AnthropicCategoryClient.classify`, `MistralCategoryClient.classify`) enthalten heute denselben,
viermal abgeschriebenen Block: `await self._client.post(URL, json=body)` →
`except httpx.HTTPError` → feature-eigene Fehlerklasse → `raise_for_vision_api_status(...)`.
Dieser Block wird an allen vier Stellen durch **einen** Aufruf ersetzt:

    response = await post_vision_request(
        self._client, ANTHROPIC_ENDPOINT, body,
        error_class=LandmarkApiError, throttle=self._throttle,
    )

Danach bleibt an den Aufrufstellen unverändert `response.json()` → providerspezifischer
Envelope-Parser → feature-eigene Extraktion stehen. `post_vision_request` gehört nach
`cloud_vision.py`, weil ADR 0032 Punkt 3 dieses Modul genau dafür angelegt hat; die Fehlerklasse
kommt weiterhin als Parameter herein, damit das Modul weder `LandmarkApiError` noch
`RemoteCategoryClassificationApiError` kennen muss.

Die anbieterspezifischen Endpunkt-Tatsachen werden zu je einem `VisionEndpoint`-Wert
(`frozen dataclass`: `url`, `provider`, `status_label`, `unreachable_label`), Konstanten
`ANTHROPIC_ENDPOINT`/`MISTRAL_ENDPOINT` in `cloud_vision.py`. Die beiden bisher an den
Aufrufstellen eingebetteten Meldungstexte bleiben **wortgleich**:
`"Anthropic Vision API nicht erreichbar: {exc}"` und
`"Mistral Chat Completions API nicht erreichbar: {exc}"`, ebenso die Statuslabels
`"Anthropic"`/`"Mistral"`. Bestehende Assertions in `test_landmark.py`/
`test_remote_classification.py` bleiben dadurch ohne Änderung grün, und die in ADR 0035 Punkt 3
verifizierte Sanierung der Fehlermeldung (kein Key, keine Bilddaten, keine Query-Parameter) gilt
unverändert.

**2. Der Schrittmacher hält einen Mindestabstand — er ist kein Token-Bucket.**
`CloudRequestThrottle` (ebenfalls `cloud_vision.py`, konfigurationsfrei) reiht **jeden** Versuch
vor dem Absenden ein, auch den ersten und jede Wiederholung. Die Reservierung ist bewusst
**sperrenfrei** und muss es bleiben — zwischen Lesen und Zurückschreiben des nächsten freien
Zeitpunkts darf kein `await` stehen, dann ist der Abschnitt im Einzel-Loop von asyncio atomar:

    async def acquire(self) -> None:
        now = self._clock()
        start = max(now, self._next_free)
        self._next_free = start + self._min_interval_seconds   # kein await dazwischen
        wait = start - now
        if wait > 0:
            self._delayed_requests += 1
            self._total_delay_seconds += wait
            await self._sleep(wait)

`clock` (Default `time.monotonic`) und `sleep` (Default `asyncio.sleep`) sind
Konstruktor-Parameter — ohne sie wäre kein Test dieser Klasse ohne echte Wartezeit möglich.
`min_interval_seconds=0.0` ist ein gültiger Wert und bedeutet „kein Schrittmacher"; das ist die
Bauform, die die Client-Tests benutzen.

Ein Token-Bucket ist verworfen (ADR 0074 Entscheidung 2): Er erlaubt genau den Stoß, der den
`429` auslöst — Anthropic schreibt selbst, eine Minutenrate könne sekundengenau durchgesetzt
werden.

**3. Die Schrittmacher-Instanzen liegen prozessweit je Anbieter, in einem eigenen Modul.**
Neues Modul `backend/src/photosort/cloud_vision_throttle.py`, das beim Import je bekanntem
Anbieter genau eine Instanz aus `settings` baut — dieselbe Bauform wie `rate_limit.py::limiter`
(das trotz des ähnlichen Namens etwas völlig anderes tut: es begrenzt **eingehende** Anfragen an
`POST /auth/login`).

Das eigene Modul ist **Pflicht, keine Geschmacksfrage**: Die Registry liest `settings`, und
`cloud_vision.py` darf `photosort.config` niemals importieren (ADR 0059 Punkt 2 — `config.py`
importiert `cloud_vision.py` für den `LANDMARK_MODEL`-Validator, die Gegenrichtung wäre ein
Importzyklus). Der *Mechanismus* bleibt deshalb in `cloud_vision.py`, nur die *Instanzen* leben
im neuen Modul. Inhalt:

- `build_throttles(settings) -> dict[str, CloudRequestThrottle]` — reine Funktion über einem
  übergebenen `Settings`-Objekt (Auflage 2 der Teststrategie), die das Modul beim Import genau
  einmal aufruft.
- `_THROTTLES: dict[str, CloudRequestThrottle]`, beim Import gefüllt.
- `throttle_for_provider(provider: str) -> CloudRequestThrottle` — direkter Dict-Zugriff, ein
  unbekannter Anbieter ist ein `KeyError` (durch das `Literal` auf `Settings.landmark_provider`
  unerreichbar).

Die **Voreinstellungstabelle** `DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER = {"anthropic": 60,
"mistral": 40}` gehört dagegen **nicht** hierher, sondern nach `cloud_vision.py` — aus derselben
Importrichtung heraus, die das eigene Modul überhaupt nötig macht: `config.py` löst die `0` gegen
sie auf (`resolved_cloud_vision_requests_per_minute`) und müsste sie sonst aus
`cloud_vision_throttle.py` importieren, also aus genau dem Modul, das seinerseits `config.py`
importiert. `cloud_vision.py` ist konfigurationsfrei und führt mit `VISION_MODELS_BY_PROVIDER`
schon die Schwester-Registry, die für `LANDMARK_MODEL` dieselbe Rolle spielt. Unverändert gilt:
je Eintrag Quelle und Abrufdatum im Kommentar (Belegpflicht analog ADR 0059 Punkt 5); die
Herleitung beider Zahlen und die **offen bleibende Beleglücke bei Mistral** stehen in ADR 0074
Entscheidung 7 (samt datiertem Umsetzungs-Nachtrag zu diesem Ort) und sind von dort zu übernehmen,
nicht neu zu erfinden.

Der Schrittmacher ist an den vier Client-Klassen ein **Pflicht-Schlüsselwortparameter ohne
Default** — dieselbe Begründung, die ADR 0059 Punkt 7 für `model` ausgeschrieben hat: Ein
Aufrufer, der ihn vergisst, fiele nicht beim Typecheck auf, sondern erst an der Anfragerate des
Anbieters. Die beiden Factories `build_landmark_client`/`build_category_classification_client`
reichen `throttle_for_provider(settings.landmark_provider)` durch; beide Cloud-Teilschritte
teilen sich dadurch **denselben** Schrittmacher, ebenso zwei gleichzeitig laufende
`classify`-Jobs.

**4. Wiederholt wird ausschließlich `429`.**
Netzwerkfehler, Zeitüberschreitung, `5xx` (inklusive Anthropics `529 overloaded_error`), `401`,
`403` und unerwartete Antwortstrukturen führen weiterhin **ohne jede Wiederholung** zum
Überspringen des Fotos. `429` ist die einzige Antwort, mit der der Anbieter selbst zusagt, dass
dieselbe Anfrage später funktioniert.

Nach erschöpftem Budget endet der Pfad dort, wo er heute schon endet:
`raise_for_vision_api_status` wirft die feature-eigene Fehlerklasse mit dem `429` im Text, die
Blockschleife zählt einen `failed_call`, schreibt `photo_cloud_vision_errors` und überspringt das
Foto. **Es braucht keine neue Fehlerklasse und keine Änderung an `worker.py`s Fehlerpfad.**

**5. Wartezeit: Anbieterangabe vor Staffel, beides gedeckelt, kein Jitter.**
`retry_after_seconds(response) -> float | None` liest `Retry-After` in beiden vom HTTP-Standard
erlaubten Formen (Ganzzahl-Sekunden und HTTP-Datum über `email.utils.parsedate_to_datetime`).
Drei Fallstricke, die der Test abdecken muss: `float("nan")`/`float("inf")` **parsen erfolgreich**
und müssen über `math.isfinite` abgewiesen werden; ein naives Datum ohne Zeitzone ist als UTC zu
lesen; ein Wert `<= 0` oder in der Vergangenheit ist „keine Angabe", kein Fehler. Fehlt der
Header, greift die verdoppelnde Staffel `2 s`, `4 s`, `8 s`, … — bei Mistral ist das der
**eingeplante Normalfall**, weil dort kein `Retry-After` dokumentiert ist (ADR 0074
Entscheidung 5). `retry-after-ms` wird bewusst **nicht** ausgewertet.

Kein Jitter: Die Wiederholung läuft ohnehin durch denselben Schrittmacher, der zwei gleichzeitig
gedrosselte Anfragen hintereinander einreiht.

**6. Die Lauf-Zeitgrenze wird nicht abgefragt, sondern durch ein gedeckeltes Budget eingehalten.**
Der Wartevorgang sitzt im HTTP-Client und hat **keinen** Session-Zugriff — `last_progress_at` von
dort zu schreiben, verbietet sich (siehe Docstring von `_detect_landmark_for_photo`: „bewusst OHNE
Session-Zugriff, damit mehrere Aufrufe sicher parallel per `asyncio.gather` laufen können").
Stattdessen wird das Budget so eng gedeckelt, dass ein Block die Watchdog-Schwelle strukturell
nicht erreicht. Vier Modulkonstanten in `cloud_vision.py`:

    VISION_MAX_RATE_LIMIT_ATTEMPTS = 5        # Versuche insgesamt, nicht Wiederholungen
    VISION_RETRY_BUDGET_SECONDS = 120.0       # summierte Wartezeit EINER Anfrage
    VISION_MAX_SINGLE_WAIT_SECONDS = 60.0     # je einzelnem Wartevorgang
    VISION_INITIAL_RETRY_WAIT_SECONDS = 2.0   # Startwert der Staffel

Reicht das Restbudget für die geforderte Wartezeit nicht, wird **nicht gekürzt gewartet**,
sondern sofort aufgegeben — eine halbe Wartezeit führt auf denselben `429` und verbrennt eine
Anfrage. Schlimmster Fall je Anfrage: `120 s` Warten + `5 × 60 s`
(`VISION_REQUEST_TIMEOUT_SECONDS`) = **420 s** gegen `STALL_THRESHOLD` von 15 Minuten.

`asyncio.sleep` ist ein sauberer Abbruchpunkt für den 24-Stunden-`JOB_TIMEOUT_SECONDS`. Damit das
trägt, fängt der Wiederholungspfad **ausschließlich `Exception`, niemals `BaseException`** — ein
verschlucktes `CancelledError` machte den Job unabbrechbar und liefe in genau den Zustand, den
ADR 0068 Punkt 2 beschreibt (Oberfläche sagt „fehlgeschlagen", der Lauf ruft weiter
kostenpflichtig an).

**Diese Rechnung wird als Invariantentest festgeschrieben** (Bauform wie die
Registry↔Preistabelle-Invariante in `test_pricing.py`): Der Test importiert `STALL_THRESHOLD` aus
`worker.py` und die vier Konstanten aus `cloud_vision.py` und prüft, dass der schlimmste Fall mit
Sicherheitsabstand darunter bleibt. Im Produktivcode gibt es diese Verbindung bewusst nicht —
`cloud_vision.py` darf `worker.py` nicht importieren.

**7. Genau eine neue Betriebsvariable — `CLOUD_VISION_REQUESTS_PER_MINUTE`.**
In `config.py`:

    cloud_vision_requests_per_minute: int = Field(default=0, ge=0)

`0` heißt „Voreinstellung des eingestellten Anbieters" (Muster von `LANDMARK_MODEL`), aufgelöst
über eine Methode `resolved_cloud_vision_requests_per_minute(provider)` neben
`resolved_landmark_model()`. **Achtung, Unterschied zu `LANDMARK_MODEL=`:** Ein *leerer* Wert ist
für ein Zahlenfeld ein Startfehler; `.env.example` trägt deshalb `=0` und sagt das ausdrücklich.

Versuchszahl, Budget, Staffel und Deckel bleiben **Modulkonstanten** (sie hängen an der
Watchdog-Rechnung aus Entscheidung 6, nicht an einer Kontostufe). Der abweichende Namenspräfix
gegenüber `LANDMARK_*` ist Absicht und in ADR 0074 Entscheidung 7 begründet.

**8. Sichtbar wird das im Lauf-Protokoll — zwei Arten von `WARNING`-Zeilen.**
`WARNING` und nicht `INFO`, weil das Root-Level des Projekts `WARNING` ist (ADR 0034 Punkt 2) und
eine `INFO`-Zeile in `docker compose logs` gar nicht erst erschiene; ADR 0034 Punkt 3 hat aus
demselben Grund bereits für den **erwarteten** best-effort-Skip `WARNING` gewählt.

- **Je Wiederholung eine Zeile**, aus `post_vision_request`: Anbieter, Versuchszähler, Wartezeit
  und deren Herkunft (Anbieterangabe oder Staffel). Nie der rohe Headerwert, nie
  `response.text`/`.headers`/`.json()` — nur die geparste Zahl (Sicherheits-Muss-Kriterium der
  ADRs 0025/0034/0035, hier unverändert gültig).
- **Je Cloud-Teilschritt höchstens eine Zusammenfassung**, aus `worker.py`, und nur wenn
  tatsächlich gewartet wurde. Sie entsteht aus der Differenz zweier Zählerstände: `ThrottleStats`
  (`frozen dataclass`: `delayed_requests`, `total_delay_seconds`, `retries`,
  `total_retry_wait_seconds`) mit einer Methode `since(previous) -> ThrottleStats`.

Neuer Helfer `_log_cloud_vision_throttling(phase, provider, stats)` direkt neben dem bestehenden
`_log_cloud_vision_failure` — dem Ort, an dem sich beide Cloud-Teilschritte ihre Logzeilen schon
heute teilen. Er kehrt wirkungslos zurück, wenn `delayed_requests == 0 and retries == 0`; dadurch
bleiben alle bestehenden Worker-Tests (die mit Test-Doubles arbeiten und den Schrittmacher nie
berühren) unverändert still.

**9. Was ausdrücklich NICHT gebaut wird.**
Keine Spalte an `CriterionScoringRun`/`RemoteCategoryClassificationRun`, kein Feld in einer
API-Antwort, keine Anzeige in der Oberfläche, kein Eintrag in `cloud_error_message`, keine
Migration. Die Story verlangt Nachvollziehbarkeit im **Lauf-Protokoll**; eine gedrosselte Anfrage
ist kein Fehler, und `cloud_error_message` ist der Fehlerkanal.

### Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `backend/src/photosort/cloud_vision.py` | **Kern.** `VisionEndpoint` + zwei Endpunkt-Konstanten, `CloudRequestThrottle`, `ThrottleStats`, `retry_after_seconds`, `post_vision_request`, vier neue Modulkonstanten, `DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER` (siehe Zeile darunter). `raise_for_vision_api_status` bleibt unverändert und wird von `post_vision_request` am Ende aufgerufen. |
| `backend/src/photosort/cloud_vision_throttle.py` | **neu**, klein: prozessweite Instanzen + `throttle_for_provider`. (Umsetzung: die Voreinstellungstabelle liegt in `cloud_vision.py` neben `VISION_MODELS_BY_PROVIDER` — `config.py` löst gegen sie auf und dürfte dieses Modul sonst nicht importieren, siehe Nachtrag in ADR 0074 Entscheidung 7.) |
| `backend/src/photosort/config.py` | neues Feld `cloud_vision_requests_per_minute` + `resolved_cloud_vision_requests_per_minute()`. |
| `backend/src/photosort/landmark.py` | `throttle`-Pflichtparameter an beiden Client-Klassen, beide `detect`-Blöcke auf `post_vision_request` umgestellt, `build_landmark_client` reicht den Schrittmacher durch. |
| `backend/src/photosort/remote_classification.py` | dasselbe für beide `classify`-Methoden und `build_category_classification_client`. |
| `backend/src/photosort/worker.py` | `_log_cloud_vision_throttling` neben `_log_cloud_vision_failure`; je ein Zählerstand-Schnappschuss und eine Zusammenfassung in beiden Cloud-Teilschritten (Stellen unten). |
| `backend/tests/test_cloud_vision.py` | Schrittmacher, `retry_after_seconds`, `post_vision_request`, Invariantentest gegen `STALL_THRESHOLD`. |
| `backend/tests/test_landmark.py`, `backend/tests/test_remote_classification.py` | Client-Konstruktionen bekommen einen `throttle`; neue Fälle „429 dann 200" und „429 bis zum Budgetende". |
| `backend/tests/test_config.py` | Voreinstellung, Auflösung je Anbieter, `ge=0`. |
| `specs/decisions/0074-…md`, `docs/architecture.md`, `docs/setup.md`, `.env.example` | **bereits erledigt** (`architect`). |

**Die beiden Einbaustellen in `worker.py` genau:**

- *Landmark-Teilschritt* (`run_criterion_scoring`): Schnappschuss unmittelbar nach
  `run.landmark_model = landmark_model` (dort ist bereits sichergestellt, dass
  `landmark_client is not None`); Zusammenfassung **nach** dem `finally` des Teilschritts, direkt
  beim bestehenden `if landmark_failures > 0:`-Block.
- *Remote-Kategorie-Teilschritt* (`run_remote_category_classification`): Schnappschuss nach
  `run.failed_calls = failed_calls; await session.commit()` und **vor** dem `try:`;
  Zusammenfassung nach dem `finally`, vor `run.status = ScanStatus.SUCCESS`.

### Reihenfolge der Umsetzung

1. **`CloudRequestThrottle` + `ThrottleStats`** in `cloud_vision.py` — reine, synchron
   testbare Mechanik mit injizierter Uhr und injiziertem `sleep`. Zuerst, weil alles andere
   darauf steht und weil sich hier ohne HTTP prüfen lässt, dass der Abstand eingehalten und
   korrekt gezählt wird.
2. **`retry_after_seconds`** — isolierte Funktion, deckt die vier Fallstricke aus
   Entwurfsentscheidung 5 ab.
3. **`VisionEndpoint` + `post_vision_request`** gegen `httpx.MockTransport`: Erfolg beim ersten
   Versuch, `429`→`200`, `429` bis zum Budgetende (endet in der bekannten Fehlerklasse),
   `Retry-After` schlägt Staffel, Netzwerkfehler und `5xx`/`401` **ohne** Wiederholung,
   `CancelledError` läuft durch.
4. **Invariantentest** gegen `STALL_THRESHOLD` — steht bewusst *vor* der Client-Umstellung, damit
   die Zahlen aus Schritt 3 festgenagelt sind, bevor sie sich verbreiten.
5. **`config.py` + `cloud_vision_throttle.py`** — Variable, Auflösung, Voreinstellungen je
   Anbieter, prozessweite Instanzen.
6. **`landmark.py`**, dann **`remote_classification.py`** — je Modul beide Client-Klassen
   umstellen und die Factory den Schrittmacher durchreichen lassen. Prüfpunkt nach jedem der
   beiden Module: die bestehenden Tests der Datei bleiben inhaltlich unverändert grün, nur die
   Konstruktoraufrufe wachsen um ein Argument.
7. **`worker.py`** — Helfer plus die zwei Einbaustellen. Prüfpunkt: kein bestehender Worker-Test
   ändert sich.
8. **Abgleich der Doku:** prüfen, dass Variablenname, Voreinstellungen (60/40) und die
   Budget-Zahlen im Code mit `.env.example`, `docs/setup.md` und `docs/architecture.md`
   übereinstimmen. Weichen sie ab, ziehen die Doku-Dateien im selben PR mit.

## UI/UX

Nicht relevant. Die Story berührt keine einzige Datei unter `frontend/`, erzeugt kein neues Feld
in einer API-Antwort und keine neue Spalte; die geforderte Nachvollziehbarkeit liegt ausdrücklich
im Server-Lauf-Protokoll (`docker compose logs`), das keine sichtbare Oberfläche ist. Damit fehlt
jeder konkret benennbare Anhaltspunkt für einen UI/UX-Anteil, und `ux-ui-designer` wurde nicht
konsultiert.

Die einzige für einen Nutzer wahrnehmbare Änderung ist, dass ein Lauf länger dauern kann. Das
zeigt die bestehende Fortschrittsanzeige unverändert an — es entsteht kein neuer Zustand, der
gestaltet werden müsste.

## Security

Sicherheitsrelevant, kein Blocker. Kein neues Secret, kein neuer Empfänger, keine neue
Abhängigkeit, kein neuer Endpunkt, keine Datenmodell-Änderung, keine Migration, keine Oberfläche.
**Neu ist eine Angriffsflächen-Klasse, die es im Projekt bislang nicht gab:** Mit der Auswertung
des `Retry-After`-Headers wird ein externer Antwortpartner erstmals zu einer **Steuergröße der
eigenen Laufzeit** statt nur zu einer Datenquelle — ein Wert aus seiner Antwort entscheidet, wie
lange eine Job-Coroutine des eigenen Prozesses nicht weiterarbeitet. Die Wartezeit ist damit eine
Eingabe von außen und unterliegt derselben Validierungspflicht wie jeder Request-Body.
Vollständige Herleitung in
[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt
"Anbieter-gesteuerte Wartezeit im Cloud-Vision-Pfad".

**1. Die Deckel begrenzen die Fremdeinwirkung vollständig — aber nur einer trägt bedingungslos.**
`VISION_MAX_RATE_LIMIT_ATTEMPTS = 5` ist eine Ganzzahl-Zählung und hält unabhängig davon, was aus
dem Header kommt. `VISION_RETRY_BUDGET_SECONDS` und `VISION_MAX_SINGLE_WAIT_SECONDS` sind
Fließkomma-Vergleiche und damit nur so gut wie die Endlichkeitsprüfung davor. Nachgestellt und
bestätigt (Python 3.12): `min(float("nan"), 60.0)` liefert **`nan`**, nicht `60.0` — die
Argumentreihenfolge entscheidet (`min(60.0, float("nan"))` liefert `60.0`) —, und `nan > budget`
ist immer `False`, das Budget also nie erschöpft. `float("inf")` wird von `min(inf, 60.0)` korrekt
gekappt, `budget_used + inf` wäre danach aber ebenfalls unbrauchbar. Ohne `math.isfinite` fällt
die Zeitdeckelung lautlos aus und es bleibt allein die Versuchszählung; mit ihr greifen alle drei.
Der schlimmste Fall je Anfrage bleibt `120 s` + `5 × 60 s` = `420 s` zuzüglich der Einreihung des
Schrittmachers (bei den Voreinstellungen ≤ 15 s je Block) gegen `STALL_THRESHOLD` von 900 s.

**2. Muss-Kriterien an `retry_after_seconds`, jedes testseitig abzudecken.**
(a) `math.isfinite` **vor** jeder Verwendung — `nan`/`inf` parsen erfolgreich und sind „keine
Angabe", nicht ein großer Wert; die Deckelung per `min(...)` ist gegen `nan` wirkungslos und
ersetzt die Prüfung nicht. (b) Die Funktion trägt **keine Exception** aus dem Header nach außen —
nachgestellt: `email.utils.parsedate_to_datetime("garbage")` und `("")` werfen `ValueError`, und
`int("9"*5000)` ebenfalls (`sys.set_int_max_str_digits`-Grenze); jeder dieser Fälle ist „keine
Angabe", kein Fehlerpfad. (c) Ein Wert `<= 0` bzw. ein Datum in der Vergangenheit ergibt `None`
und **niemals** eine negative Zahl — `asyncio.sleep(-5)` kehrt zwar sofort zurück (nachgestellt),
die eigentliche Gefahr ist ein negativer Summand, der das *Restbudget vergrößert*. (d) Ein naives
Datum ohne Zeitzone wird als UTC gelesen. (e) Rückgabewert `float | None`, nie ein durchgereichter
String. Zusätzlich: das Restbudget darf ausschließlich schrumpfen.

**3. Die Wiederholungsbedingung ist exakt `response.status_code == 429`. Muss.** Kein `>= 429`,
kein „4xx", kein `in range(...)`. Ein weiter gefasstes Prädikat zöge Anthropics `529` und jedes
`5xx` mit hinein (von ADR 0074 Entscheidung 4 ausgeschlossen) und — sicherheitlich relevanter —
auch `401`/`403`. Eine Wiederholung nach ungültigen oder gesperrten Zugangsdaten sendet denselben
API-Key **fünfmal** gegen einen Endpunkt, der ihn gerade abgelehnt hat: das Muster, das
anbieterseitige Missbrauchserkennung auslöst, und es kann per Definition nicht gelingen. Der
`401`/`403`-ohne-Wiederholung-Fall gehört als eigener Test in `test_cloud_vision.py`. Ein
Kostenrisiko entsteht aus der Wiederholung **nicht**: ein `429` wird nicht abgerechnet, und ein
Aufruf zählt in der Lauf-Bilanz erst mit Ergebnis (ADR 0051 Punkt 1).

**4. Der neue Logpfad sieht erstmals den Request-Body. Muss.** In `post_vision_request` liegen
`body` (die **base64-kodierten Bilddaten** des Familienfotos) und der Key-tragende
`httpx.AsyncClient` (`x-api-key` bzw. `Authorization: Bearer` in den Default-Headern) im selben
Sichtbereich wie die neue `WARNING`-Zeile — bisher wurde an dieser Stelle nicht geloggt. Die Zeile
je Wiederholung darf ausschließlich enthalten: das `provider`/`status_label`-Feld des **eigenen**
`VisionEndpoint`-Konstantenwerts, den Versuchszähler (`int`), die bereits geparste und gedeckelte
Wartezeit (`float`) und ein **festes Literal** für deren Herkunft („Anbieterangabe"/„Staffel").
Verboten: `body`, `json=…`, das `httpx.Request`-Objekt, `client.headers`, `response.headers`,
`response.text`, `response.json()` und der **rohe** `Retry-After`-Wert. Letzterer ist zugleich die
einzige Log-Injection-Fläche des Features (geforgte Logzeile über Steuerzeichen im Headerwert);
indem nur die geparste Zahl in die Zeile geht, ist sie strukturell geschlossen statt gefiltert.
Unveränderte Fortschreibung der Muss-Kriterien aus ADR 0025/0031/0032/0034 Punkt 5/0035 Punkt 3
an einer neuen Stelle. Für `_log_cloud_vision_throttling` gilt dasselbe — es bekommt
ausschließlich `ThrottleStats` (reine Zahlen), nie eine Antwort.

**5. Der Abbruchvertrag trägt — nachgeprüft — solange nur `Exception` gefangen wird. Muss.** Am
Branch verifiziert: Beide Cloud-Block-Schleifen in `worker.py` (Landmark- und
Remote-Kategorie-Teilschritt) prüfen ihre `asyncio.gather(..., return_exceptions=True)`-
Ergebnisliste bereits explizit auf `asyncio.CancelledError`-Instanzen und werfen sie erneut; der
in `_process_scan_block` verankerte projektweite Vertrag ist an beiden Stellen vorhanden.
`asyncio.sleep` ist damit ein echter Abbruchpunkt für `JOB_TIMEOUT_SECONDS` und den
Worker-Shutdown — aber nur, solange `post_vision_request` das `CancelledError` nach oben lässt.
Ein `except BaseException`, ein nacktes `except:`, ein `contextlib.suppress` um die Schleife oder
ein `asyncio.shield` um den Sleep machte den Job unabbrechbar und liefe in den von ADR 0068
Punkt 2 beschriebenen Zustand. Dasselbe gilt für den **zweiten** neuen Sleep, den in
`CloudRequestThrottle.acquire()`.

**6. `cloud_vision_throttle.py` darf beim Import nicht werfen. Muss.** Die Instanzen entstehen zur
Modul-Importzeit, der Mindestabstand aus `60 / rate`. `Field(default=0, ge=0)` lässt `0`
ausdrücklich zu, und `0` heißt „Voreinstellung des Anbieters". Löst
`resolved_cloud_vision_requests_per_minute(provider)` die `0` nicht auf — oder liefert eine
Anbieter-Voreinstellung von `0` —, ist das ein `ZeroDivisionError` **zur Importzeit** und damit
ein gleichzeitiger Startfehler von Backend *und* Worker, nicht ein fehlgeschlagener Lauf. Zu
prüfen ist die Auflösung, nicht die Division: die Methode darf nie `0` zurückgeben.
`CLOUD_VISION_REQUESTS_PER_MINUTE` selbst ist kein Secret, wird beim Start pydantic-typgeprüft und
fließt in keine Pfad-, Datei-, Shell- oder SQL-Operation.

**7. Geprüft und ohne Befund.** *Kein SSRF, keine Erweiterung der Zielmenge:* die Ziel-URL wird zu
einem `VisionEndpoint`-Konstantenwert, stammt nicht aus Daten und niemals aus einer Antwort;
nachgeprüft, dass `httpx` per Voreinstellung keinen Weiterleitungen folgt und keiner der vier
Clients `follow_redirects` setzt. **Muss daraus:** `post_vision_request` setzt `follow_redirects`
nicht und behandelt kein `3xx` als wiederholbar — sonst gingen Key und Bilddaten an ein vom
Anbieter benanntes fremdes Ziel. *Keine Consent-Frage:* Empfänger, Zweck, Datenumfang je Foto und
die Kandidatenmenge bleiben identisch; die Bilddaten einer mit `429` abgewiesenen Anfrage haben
die Leitung ohnehin bereits passiert, und das Foto wäre im nächsten Lauf erneut Kandidat gewesen.
Anders als bei ADR 0047 verschiebt sich hier **nicht einmal** die Kandidatenmenge — das bestehende
projektweite Opt-in gilt unverändert, kein Zurücksetzen des Consent-Zeitstempels. *Kein
Innentäter-Modell:* der prozessweite Schrittmacher wird von zwei gleichzeitigen `classify`-Läufen
geteilt, ein Lauf verlangsamt den anderen — laut ADR 0074 Entscheidung 3 genau so gewollt und im
Bedrohungsmodell dieses Projekts keine Bedrohung. *Fehlermeldungspfad unverändert:*
`raise_for_vision_api_status` bleibt wie es ist, die in ADR 0035 Punkt 3 verifizierte Sanierung
gilt weiter.

**8. Restrisiken, bewusst akzeptiert.** (a) *Logvolumen* — eine `WARNING`-Zeile je Wiederholung,
`docker-compose.yml` konfiguriert keine Rotation. Selbstbegrenzend: die Zeilen können nicht
schneller entstehen, als der Schrittmacher Anfragen zulässt, und jede Wiederholung kostet
mindestens 2 s Wanduhr. Kein Blocker — aber der Grund, warum die Zusammenfassung je Teilschritt
nur bei tatsächlichem Warten geschrieben werden darf. (b) *Missverständliche
Zusammenfassungszeile* — `ThrottleStats.since()` liest prozessweite Zähler; bei zwei gleichzeitigen
`classify`-Jobs enthält die Zusammenfassung des einen Laufs die Wartezeiten des anderen. Das
Sicherheitskonzept schreibt der Lauf-/Kostentransparenz ausdrücklich die Rolle eines
Erkennungsmechanismus zu; eine Zahl, die etwas anderes misst als ihr Label verspricht, schwächt
genau das. **Soll:** die Zeile benennt den Schrittmacher als anbieterweit, nicht als lauf-eigen.
(c) *Sehr kleine Rate bei erhöhter `*_CONCURRENCY`* kann die Einreihung eines Blocks über
`STALL_THRESHOLD` heben (in `.env.example` und `docs/setup.md` ausgeschrieben). **Soll:** der
Invariantentest rechnet die Einreihung des Schrittmachers für die *Voreinstellungen* mit ein — er
darf `config.py`/`cloud_vision_throttle.py` importieren, der Produktivcode darf das nicht —, damit
ein späteres Absenken einer Voreinstellung nicht still an der Schwelle vorbeiläuft. (d) *Der
Sonderfall „429 wegen Ausgabenobergrenze"* wird nicht erkannt und verbrennt je Foto bis zu vier
aussichtslose Versuche — gedeckelt, nicht abgerechnet, in ADR 0074 hergeleitet.

## Teststrategie

Festgelegt durch `test-engineer`. Projektweite Konventionen und die daraus neu abgeleiteten Regeln
stehen im Testkonzept
([`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md), Sektion „Der
erste Testgegenstand, der WARTET"); hier steht, was für **diese** Story konkret zu prüfen ist.

### Zwei Auflagen an die Umsetzung, ohne die nichts davon testbar ist

**1. Der Schrittmacher ist der einzige Zeitgeber — `post_vision_request` wartet über ihn.** Die
Entwurfsentscheidungen nennen `clock`/`sleep` nur an `CloudRequestThrottle`. Damit wäre die
Wiederholungsstaffel in `post_vision_request` an einem *zweiten*, nicht injizierten
`asyncio.sleep` festgemacht — jeder Client-Test „429 bis zum Budgetende" schliefe real
`2+4+8+16 = 30 s`, mal vier Aufrufstellen. Verbindlich deshalb: `CloudRequestThrottle` hält
`clock`/`sleep` (Voreinstellungen `time.monotonic`/`asyncio.sleep`) und gibt sie lesbar heraus;
`post_vision_request` wartet ausschließlich darüber. Das ist keine neue Kopplung —
`post_vision_request` schreibt ohnehin schon `retries`/`total_retry_wait_seconds` in den
Schrittmacher zurück, sonst könnte `ThrottleStats` diese beiden Felder gar nicht führen.

**2. Zwei kleine Signaturzugeständnisse zugunsten exakter Assertions.**
`retry_after_seconds(response, *, now: datetime | None = None)` — ohne injizierbaren
Bezugszeitpunkt sind die HTTP-Datum-Fälle nur mit Toleranzfenster prüfbar. Und die Instanzbildung
in `cloud_vision_throttle.py` gehört in eine **reine Funktion über einem `Settings`-Objekt**, die
das Modul beim Import einmal aufruft — sonst ist die Registry nur über `importlib.reload` prüfbar.

### Ebenenverteilung

| Ebene | Gegenstand | Ort |
|---|---|---|
| Unit, netzwerkfrei | `CloudRequestThrottle`, `ThrottleStats`, `retry_after_seconds`, die vier Budget-Konstanten | `tests/test_cloud_vision.py` |
| Unit, Konfiguration | `cloud_vision_requests_per_minute`, `resolved_…()`, Registry und abgeleitetes Intervall | `tests/test_config.py`, `tests/test_cloud_vision_throttle.py` (neu) |
| Integration, HTTP | `post_vision_request` gegen `httpx.MockTransport` | `tests/test_cloud_vision.py` |
| Integration, Client | die vier Aufrufstellen, „429→200" und „429 bis Budgetende" | `tests/test_landmark.py`, `tests/test_remote_classification.py` |
| Integration, Lauf | K9-Nachweis und die Protokoll-Zusammenfassung je Teilschritt | `tests/test_worker_criterion_scoring.py`, `tests/test_worker_remote_category_classification.py` |
| Invariante | Wartebudget gegen `STALL_THRESHOLD` | `tests/test_cloud_vision.py` |
| E2E/Frontend | **nichts.** Keine Oberfläche, kein Antwortfeld, keine Route. | — |

### 1. Schrittmacher (Unit, K4)

Zwei Doubles, beide ohne echte Wartezeit: **(a)** eingefrorene Uhr (`clock` liefert konstant
`0.0`) plus aufzeichnender `sleep`, der die Dauer anhängt und `await asyncio.sleep(0)` macht —
damit sind Wartezeiten eine *Liste erwarteter Zahlen*; **(b)** fortschreitende Uhr, deren `sleep`
das `now` addiert und die der Test selbst weiterstellen darf.

- Erster Aufruf wartet nie; zweiter Aufruf unmittelbar danach wartet genau `min_interval`.
- Ist zwischen zwei Aufrufen mehr als `min_interval` vergangen (Uhr (b) vorgestellt), wartet der
  zweite **nicht** — der Schrittmacher bremst nicht rückwirkend.
- `min_interval_seconds=0.0` ist gültig und bedeutet „kein Schrittmacher": kein `sleep`-Aufruf,
  `delayed_requests == 0`. Das ist die Bauform, mit der die bestehenden Client-Tests konstruieren.
- **Sperrenfreiheit/Atomarität:** fünf `acquire()` gleichzeitig per `asyncio.gather` bei
  eingefrorener Uhr → aufgezeichnete Wartezeiten exakt `[0, 1, 2, 3, 4] × min_interval`, streng
  monoton und ohne Dublette. Genau dieser Fall wird rot, wenn zwischen Lesen und Zurückschreiben
  von `_next_free` ein `await` steht — der Fehler, den Entwurfsentscheidung 2 ausschließt.
- Zähler: `delayed_requests`/`total_delay_seconds` wachsen nur bei tatsächlichem Warten;
  `ThrottleStats.since(previous)` liefert die Differenz und **nie** negative Werte.
- `sleep`-Double wirft `asyncio.CancelledError` → propagiert unverändert (K7).

### 2. `retry_after_seconds` (Unit, K2) — die vier Fallstricke, jeder als eigener Fall

- `"nan"`, `"inf"`, `"-inf"`, `"NaN"` → `None`. Diese Werte **parsen erfolgreich** durch
  `float()`; ohne `math.isfinite` liefe daraus eine unendliche oder undefinierte Wartezeit.
- Naives HTTP-Datum ohne Zeitzone → als **UTC** gelesen. Der Fall braucht einen Testlauf mit
  verstellter Prozess-Zeitzone (`monkeypatch.setenv("TZ", "Asia/Tokyo")` + `time.tzset()`,
  `tzset()` auch im Teardown) — auf einer UTC-Maschine wäre eine Implementierung, die naiv als
  *Ortszeit* liest, sonst zufällig grün.
- `"0"`, `"-5"`, Datum in der Vergangenheit → `None` („keine Angabe", kein Fehler).
- Fehlender, leerer, unparsbarer Header (`"bald"`, `"1,5"`) → `None`.
- Gegenprobe: `"30"` → `30.0`; Datum `now + 45 s` bei injiziertem `now` → exakt `45.0`;
  `retry-after-ms: 500` allein → `None` (wird bewusst nicht ausgewertet).

### 3. `post_vision_request` (Integration über `httpx.MockTransport`, K1/K3/K5/K7/K8)

Handler mit Antwortliste und Aufrufzähler; Schrittmacher mit `min_interval_seconds=0.0` und
aufzeichnendem `sleep`.

- Erfolg beim ersten Versuch → genau eine Anfrage, kein `sleep`, keine Logzeile.
- `429` → `200` → zwei Anfragen, Ergebnis des `200`, **eine** aufgezeichnete Wartezeit `2.0`.
- Dauerhaft `429` → genau **5** Anfragen, Wartezeiten exakt `[2.0, 4.0, 8.0, 16.0]`, am Ende die
  übergebene Fehlerklasse mit `429` im Text (dieselbe Meldung wie heute, aus
  `raise_for_vision_api_status`).
- `Retry-After` schlägt Staffel: Header `"5"` → gewartet `5.0`, nicht `2.0`.
- Staffel hängt am Versuchszähler: „ohne / `5` / ohne" → `[2.0, 5.0, 8.0]` (siehe Anmerkung zu K3).
- Einzeldeckel: Header `"1200"` → gewartet `60.0`.
- Budget: Header dauerhaft `"60"` → Wartezeiten `[60.0, 60.0]`, danach **sofort aufgegeben** (drei
  Anfragen, nicht fünf), Summe exakt `120.0` — der Nachweis für „nicht gekürzt warten".
- **Ohne Wiederholung** (je ein Fall): `500`, `529`, `401`, `403`, `httpx.ConnectError`,
  `httpx.ReadTimeout` → genau **eine** Anfrage, kein `sleep`, bekannte Fehlerklasse.
- Der Schrittmacher wird auch beim **ersten** Versuch und bei **jeder** Wiederholung durchlaufen
  (Zählernachweis über einen Schrittmacher mit `min_interval > 0`, eingefrorene Uhr: 5 Versuche →
  4 Einreihungen).
- `sleep` wirft `asyncio.CancelledError` → propagiert, wird **nicht** zur Fehlerklasse (K7).
- **Log (K8):** je Wiederholung genau eine `WARNING`-Zeile mit Anbieter, Versuchszähler, Wartezeit
  und Herkunft. Sicherheitsnachweis mit einem Rohwert, der sich von der geparsten Zahl
  unterscheidet — Header `"Retry-After: voellig-kaputt-4711"` plus Antwortkörper mit Markerstring:
  `caplog.text` enthält `2.0`, aber weder `4711` noch den Marker noch einen Headernamen.

### 4. Invariantentest gegen `STALL_THRESHOLD` (K7)

Importiert `STALL_THRESHOLD` aus `worker.py` und die vier Konstanten aus `cloud_vision.py`
(Bauform wie die Registry↔Preistabelle-Invariante in `test_pricing.py`; im Produktivcode gibt es
diese Verbindung bewusst nicht):

- schlimmster Fall `= VISION_RETRY_BUDGET_SECONDS + VISION_MAX_RATE_LIMIT_ATTEMPTS ×
  VISION_REQUEST_TIMEOUT_SECONDS` **plus** ein benannter `SAFETY_MARGIN_SECONDS = 300` bleibt
  unter `STALL_THRESHOLD.total_seconds()`;
- derselbe schlimmste Fall ist **auf `420.0` festgenagelt** — sonst verschiebt ein Anheben einer
  Konstante die Rechnung still, während Spec, ADR und `docs/architecture.md` weiter `420 s`
  behaupten;
- Summe der zugelassenen Staffelschritte (`2+4+8+16 = 30`) passt ins Budget — sonst ist die
  zugesagte Versuchszahl auf dem staffelgetriebenen Pfad (Mistrals Normalfall) unerreichbar;
- `VISION_MAX_SINGLE_WAIT_SECONDS <= VISION_RETRY_BUDGET_SECONDS` und
  `VISION_MAX_RATE_LIMIT_ATTEMPTS >= 1`;
- zusätzlich für die **Voreinstellungen**: Einreihung eines vollen Blocks
  (`(concurrency − 1) × min_interval`) plus schlimmster Fall plus Abstand bleibt unter der
  Schwelle. Für beliebige Betriebswerte gilt das ausdrücklich nicht — siehe „Bekannte Lücken".

### 5. Client-Ebene (K1/K5/K6) — `test_landmark.py`, `test_remote_classification.py`

Je Client (alle **vier**) ein Paar: „429 → 200 liefert das erwartete Ergebnis, zwei Anfragen" und
„dauerhaft 429 endet in `LandmarkApiError`/`RemoteCategoryClassificationApiError`, fünf Anfragen".
Je Testdatei ein Hilfskonstruktor `_no_throttle()` (`min_interval_seconds=0.0`) für die
Bestandsfälle und ein `_recording_throttle()` für die neuen. Dazu der Signaturtest analog
`TestTheModelIsAlwaysPassedIn` in `test_pricing.py`: `throttle` hat an allen vier Klassen
`default is inspect.Parameter.empty` **und** `kind is KEYWORD_ONLY`.

**Zur Zusage „die bestehenden Fälle bleiben inhaltlich unverändert": geprüft und realistisch.**
Am echten Code nachgesehen — es sind ~22 Konstruktionsstellen (11 in `test_landmark.py`, 11 in
`test_remote_classification.py`), die genau ein Schlüsselwortargument bekommen. Kein bestehender
Fall benutzt `429` (die Fehlerpfade sind `401`, `500`, `ConnectError`), es wird also kein
Bestandstest still zu einem wartenden Test. Keine Assertion prüft einen Meldungstext des
Wiederholungspfads; die beiden Sicherheitstests konstruieren die Fehlerklasse selbst. Bedingungen:
die Meldungstexte `"Anthropic Vision API nicht erreichbar: {exc}"` /
`"Mistral Chat Completions API nicht erreichbar: {exc}"` und die Statuslabels `"Anthropic"`/
`"Mistral"` bleiben wortgleich, und `throttle` bekommt **keinen** Default, um die Anpassung zu
sparen.

### 6. Lauf-Ebene (K8/K9) — die eigentliche Zusage der Story

**K9 nur als Paar, und nur auf Worker-Ebene.** Ein Client-Test zeigt nicht, dass der Lauf das Foto
verbucht. Über die vorhandene Factory-Injektion (`build_landmark_client=` /
`build_category_client=`) wird ausnahmsweise ein **echter** Client mit `httpx.MockTransport`
hereingereicht — ein Fake-Double abstrahiert genau die Schicht weg, um die es geht:

- „dauerhaft 429": keine Ergebniszeile, `failed_calls == 1`, `photo_cloud_vision_errors`-Zeile da,
  Lauf `SUCCESS` — der heutige Zustand, der nach erschöpftem Budget erhalten bleibt;
- „429, dann 200": Ergebniszeile da, `failed_calls == 0`, keine Fehlerzeile.
  Erst der Kontrast belegt die Zusage.

**K8-Zusammenfassung** über `monkeypatch.setattr(worker, "throttle_for_provider", …)` (etablierte
Konvention, vgl. `test_worker_reap_stalled_runs.py`), damit Worker und injizierter Client denselben
Schrittmacher sehen. Drei Fälle je Teilschritt:

- kein Warten → **keine** Zeile (das ist zugleich der Grund, warum alle bestehenden Worker-Tests
  mit `assert len(caplog.records) == 0` still bleiben — sie berühren den Schrittmacher nie);
- gewartet → genau eine Zeile mit eingereihten Anfragen, summierter Wartezeit, Wiederholungen;
- **Differenz statt Absolutwert:** Zählerstand vor dem Teilschritt künstlich ungleich null, während
  des Teilschritts genau zwei weitere Vorgänge → die Zeile meldet „zwei", nicht „alle". Ohne
  diesen Fall schriebe der zweite Cloud-Teilschritt sich die Wartezeit des ersten zu und wäre bei
  einem einzelnen Teilschritt trotzdem grün.

Zusätzlich als reine Unit-Fälle: `_log_cloud_vision_throttling` mit handgebauten `ThrottleStats`
(still bei `0/0`, Zeile sonst).

### 7. Konfiguration und Registry (K4)

`test_config.py`: Voreinstellung `0`, `ge=0` weist `-1` ab, Env-Override greift,
`resolved_cloud_vision_requests_per_minute("anthropic"/"mistral")` liefert bei `0` die
Voreinstellungen `60`/`40` und bei gesetztem Wert diesen für **beide** Anbieter — plus der
ausdrückliche Fall, dass ein *leerer* Wert ein Startfehler ist (Unterschied zu `LANDMARK_MODEL=`).

`test_cloud_vision_throttle.py` (neu): genau eine Instanz je bekanntem Anbieter, Identität bei
wiederholtem `throttle_for_provider(...)`-Abruf (beide Cloud-Teilschritte teilen sich denselben),
unbekannter Anbieter → `KeyError`, abgeleitetes Intervall `1.0`/`1.5 s`, kein Intervall `0` und
keine Division durch null; die Voreinstellungstabelle deckt genau die Anbieter von
`Settings.landmark_provider` ab. **Kein Test ruft `acquire()` auf einer Registry-Instanz auf** —
sie ist prozessweit und trägt Zustand über die gesamte pytest-Sitzung. Geprüft wird über die reine
Bau-Funktion mit einer handgebauten `Settings`.

### Was bewusst nicht getestet wird

- Ob `60`/`40` zur tatsächlichen Kontostufe passen und ob die Anbieter `Retry-After` real senden —
  eine Aussage über fremde Systeme, nicht über Code. Ersatzverfahren: Blick ins Lauf-Protokoll
  nach dem ersten größeren Import.
- Dass die beiden Factories den prozessweiten Schrittmacher durchreichen: sie laufen in keinem
  automatisierten Test (echtes Secret, echter Netzwerkversuch). Abgesichert nur als
  Quelltext-Verankerung (`inspect.getsource(...)` enthält den Registry-Aufruf) plus
  `mypy --strict`.
- Der Sonderfall „429 wegen erreichter Ausgabenobergrenze" — ausdrücklich Out of Scope und im Test
  von jeder anderen Drosselung nicht unterscheidbar.
- Frontend und E2E: unberührt, kein sichtbarer Anteil.

### Coverage-Gate

`--cov-fail-under=80` ist hier kein Maßstab: Das Backend liegt bei ~97 %, die rund 150 neuen Zeilen
könnten vollständig ungetestet bleiben, ohne das Gate zu röten. Pflichtabdeckung sind die oben
namentlich benannten Fälle.

## Entscheidungen

- **Der Schrittmacher hält einen Mindestabstand, kein Token-Bucket** — ein Bucket erlaubt genau
  den Stoß, der den `429` auslöst (ADR 0074 Entscheidung 2).
- **Wiederholt wird ausschließlich `429`**, exakt als `== 429` geprüft. Jeder andere Fehler behält
  den heutigen best-effort-Skip (ADR 0025 Punkt 3 / ADR 0032 Punkt 5 bleiben dort unverändert).
- **Die Lauf-Zeitgrenze wird nicht abgefragt, sondern durch ein gedeckeltes Budget eingehalten** —
  der Wartevorgang sitzt im HTTP-Client ohne Session-Zugriff und darf `last_progress_at` nicht
  schreiben. Die Einhaltung wird als Invariantentest gegen `STALL_THRESHOLD` festgeschrieben statt
  als Kommentar.
- **Genau eine neue Betriebsvariable** (`CLOUD_VISION_REQUESTS_PER_MINUTE`); Versuchszahl, Budget,
  Staffel und Deckel bleiben Modulkonstanten, weil sie an der Watchdog-Rechnung hängen und nicht
  an einer Kontostufe.
- **Nachtrag `test-engineer` (Auflage 1): `post_vision_request` wartet ausschließlich über den
  `sleep` des Schrittmachers**, nicht über ein eigenes `asyncio.sleep`. Ohne das hinge die
  Wiederholungsstaffel an einem zweiten, nicht injizierten Zeitgeber, und die Client-Tests würden
  real warten (`2+4+8+16 = 30 s` je Aufrufstelle). Diese Festlegung geht der Formulierung in
  „Architektur / Umsetzung", Entwurfsentscheidung 1, vor.
- **Nachtrag `test-engineer` (Auflage 2):** `retry_after_seconds` bekommt einen injizierbaren
  Bezugszeitpunkt (`*, now: datetime | None = None`), und die Instanzbildung in
  `cloud_vision_throttle.py` liegt in einer reinen Funktion über einem `Settings`-Objekt, die das
  Modul beim Import einmal aufruft — sonst wäre die Registry nur über `importlib.reload` prüfbar.
- **Nachtrag `security-engineer`: `math.isfinite` ist Pflicht, nicht Kür.** Nachgestellt:
  `min(float("nan"), 60.0)` liefert `nan`, und `nan > budget` ist immer `False` — ohne die
  Endlichkeitsprüfung fallen beide Zeit-Deckel lautlos aus, und es bliebe allein die
  Versuchszählung.
- **`architect` konsultiert (Schritt 1):** ADR 0074 angelegt, `docs/architecture.md`,
  `docs/setup.md` und `.env.example` im selben Branch mitgezogen.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** kein konkret benennbarer Bezug zu einer
  sichtbaren Oberfläche — keine Datei unter `frontend/`, kein neues API-Feld, keine neue Spalte;
  die geforderte Nachvollziehbarkeit liegt im Server-Lauf-Protokoll.
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien auf K1–K10 geschärft, Testkonzept
  um die Sektion „Der erste Testgegenstand, der WARTET" ergänzt.
- **`security-engineer` konsultiert (Schritt 3):** sicherheitsrelevant, kein Blocker;
  Sicherheitskonzept an vier Stellen fortgeschrieben, darunter eine neue projektweit verbindliche
  Regel für wartende Job-Coroutinen.

## Offene Fragen

Keine.

## Out of Scope

- Keine Anzeige in der Oberfläche, kein neues Feld in einer API-Antwort, keine neue Spalte und
  keine Migration — die geforderte Nachvollziehbarkeit liegt ausschließlich im Lauf-Protokoll.
- Keine Wiederholung bei anderen Fehlern als `429` (Zeitüberschreitung, `5xx`, `401`, `403`,
  unerwartete Antwortstruktur) — dort bleibt das Überspringen des Fotos unverändert.
- Kein Erkennen des Sonderfalls „`429` wegen erreichter Ausgabenobergrenze" (Anthropic verwendet
  denselben Statuscode); der Schaden ist durch das Wartebudget gedeckelt.
