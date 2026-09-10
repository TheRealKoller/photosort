# 0074 - Cloud-Vision: Schrittmacher je Anbieter, Wiederholung nur bei 429, gedeckeltes Wartebudget

**Status:** Accepted
**Datum:** 2026-09-10
**Bezug:** [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) (Punkt 3, best-effort-Skip — bleibt für alle Fehler außer 429 unverändert), [`decisions/0031-mistral-provider-option-cloud-landmark.md`](./0031-mistral-provider-option-cloud-landmark.md), [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Punkt 3, providerneutrale HTTP-Bausteine, und Punkt 5, best-effort-Skip), [`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](./0034-strukturiertes-logging-cloud-vision-fehler.md) (Punkt 2/3, Log-Level), [`decisions/0035-cloud-vision-attempt-fehler-persistierung.md`](./0035-cloud-vision-attempt-fehler-persistierung.md), [`decisions/0019-job-lauf-heartbeat-watchdog.md`](./0019-job-lauf-heartbeat-watchdog.md) (die Zeitgrenze, die hier eingehalten werden muss), [`decisions/0051-ist-kostenerfassung-remote-laeufe.md`](./0051-ist-kostenerfassung-remote-laeufe.md), [`decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md`](./0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md) (Punkt 2, Importrichtung `config.py` → `cloud_vision.py`), [`decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md`](./0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md) (Punkt 2, Fortschritt am Blockende), [`features/0382-cloud-rate-limits-aussitzen.md`](../features/0382-cloud-rate-limits-aussitzen.md)

## Kontext

Ein Klassifizierungslauf ruft den Cloud-Anbieter in zwei Teilschritten an: die Kategorie-Klassifikation (`worker.py::run_remote_category_classification`) und die Sehenswürdigkeit-Erkennung (die Landmark-Teilphase in `worker.py::run_criterion_scoring`). Beide laufen nacheinander im selben `classify`-Job, beide in festen Blöcken von je `*_CONCURRENCY` gleichzeitigen Anfragen, beide gegen denselben Anbieter (`LANDMARK_PROVIDER`) mit demselben Modell (`LANDMARK_MODEL`).

Die Anfragen gehen dabei **so schnell heraus, wie der Anbieter antwortet** — es gibt keine Stelle im Code, die sie zeitlich verteilt. Erreicht ein Lauf die Anfragerate des Anbieters, antwortet dieser mit `429`. `cloud_vision.py::raise_for_vision_api_status` macht daraus einen gewöhnlichen `LandmarkApiError`/`RemoteCategoryClassificationApiError`, die Blockschleife fängt ihn über `return_exceptions=True` ab und **überspringt das Foto für diesen Lauf** (best-effort, ADR 0025 Punkt 3/ADR 0032 Punkt 5). Das Foto bleibt Kandidat des nächsten Laufs.

Für jeden anderen Fehler ist dieses Verhalten richtig und bleibt es. Für `429` ist es der falsche Schluss: Der Anbieter sagt nicht "diese Anfrage geht nicht", sondern "diese Anfrage geht **jetzt** nicht". Der Skip wirft eine Anfrage weg, die eine Sekunde später erfolgreich gewesen wäre — und er tut es genau dann gehäuft, wenn viel zu tun ist, also bei einem großen Import. Sichtbar ist das nur in der Statistik (`failed_calls`) und im Lauf-Protokoll; die einzige Abhilfe ist heute, den Lauf von Hand erneut anzustoßen, bei größeren Beständen wiederholt.

Zwei bestehende Gegebenheiten begrenzen den Lösungsraum:

- **Die Zeitgrenzen des Laufs (ADR 0019).** Schicht 2 des Fortschritts-Watchdogs setzt einen `RUNNING`-Lauf auf `FAILED`, dessen `last_progress_at` älter als `STALL_THRESHOLD` (15 Minuten) ist — **ohne die Coroutine abzubrechen**. `last_progress_at` wird in beiden Cloud-Teilschritten am **Blockende** fortgeschrieben (ADR 0068 Punkt 2). Ein Wartevorgang innerhalb eines Blocks ist für den Watchdog von einem Hänger nicht unterscheidbar. Wartet ein Block länger als 15 Minuten, sagt die Oberfläche "fehlgeschlagen", während der Lauf weiter kostenpflichtig anruft. Schicht 1 (`JOB_TIMEOUT_SECONDS`, 24 h) bleibt der äußere Not-Anker.
- **Die Importrichtung (ADR 0059 Punkt 2).** `config.py` importiert `cloud_vision.py` (der `LANDMARK_MODEL`-Validator braucht die Modell-Registry). `cloud_vision.py` darf `photosort.config` deshalb niemals importieren.

## Entscheidung

### 1. Genau ein Ort für Verteilung und Wiederholung: `cloud_vision.py::post_vision_request`

Die vier Aufrufstellen (`AnthropicLandmarkClient.detect`, `MistralLandmarkClient.detect`, `AnthropicCategoryClient.classify`, `MistralCategoryClient.classify`) enthalten heute denselben, viermal abgeschriebenen Block: `await self._client.post(URL, json=body)`, `except httpx.HTTPError` → feature-eigene Fehlerklasse, dann `raise_for_vision_api_status(...)`. Dieser Block wird durch **einen** Aufruf ersetzt:

```python
response = await post_vision_request(
    self._client, ANTHROPIC_ENDPOINT, body, error_class=LandmarkApiError, throttle=self._throttle
)
```

`post_vision_request` lebt in `cloud_vision.py` — dem Modul, das ADR 0032 Punkt 3 genau dafür angelegt hat ("providerneutrale HTTP-/Parsing-Bausteine, von beiden Feature-Modulen genutzt"). Es bleibt damit bei der bestehenden Arbeitsteilung: kein Prompt, kein Antwortschema, keine feature-spezifische Logik in `cloud_vision.py`; die Fehlerklasse kommt weiterhin als Parameter herein, damit dieses Modul weder `LandmarkApiError` noch `RemoteCategoryClassificationApiError` kennen muss.

Die vier Aufrufstellen unterscheiden sich danach nur noch in Endpunkt, Body und Fehlerklasse. Die anbieterspezifischen Endpunkt-Tatsachen (URL und die beiden bisher an den Aufrufstellen eingebetteten Meldungstexte) werden zu je einem `VisionEndpoint`-Wert; die beiden Meldungen bleiben **wortgleich** erhalten, damit die bestehenden Tests ohne geänderte Assertions grün bleiben und die in ADR 0035 Punkt 3 verifizierte Sanierung der Fehlermeldung (kein Key, keine Bilddaten, keine Query-Parameter) unverändert gilt.

**Damit ist das Akzeptanzkriterium "einheitlich für beide Cloud-Phasen und für beide Anbieter" strukturell erfüllt** und nicht durch vier gepflegte Kopien.

### 2. Verteilung = Mindestabstand zwischen Anfragen, kein Token-Bucket

Der Schrittmacher (`CloudRequestThrottle`) hält einen **Mindestabstand** zwischen zwei ausgehenden Anfragen an denselben Anbieter ein. Jeder Versuch — auch der erste, auch jede Wiederholung — reiht sich vor dem Absenden ein.

Die Reservierung ist bewusst **sperrenfrei**: Lesen des nächsten freien Zeitpunkts, Vorrücken um den Mindestabstand und Zurückschreiben passieren ohne dazwischenliegendes `await` und sind im Einzel-Loop von asyncio damit atomar. Erst danach wird geschlafen. Ein `asyncio.Lock` wäre eine zweite, an einen Event-Loop gebundene Zustandsquelle ohne Gewinn.

**Verworfen: ein Token-Bucket.** Ein Bucket erlaubt einen Stoß gesammelter Token — und genau ein Stoß ist der Auslöser eines `429`. Das ist keine Vermutung, sondern beim einen Anbieter erstparteilich ausgeschrieben (Anthropic, "Rate limits", abgerufen 2026-09-10): *"a rate of 60 requests per minute (RPM) might be enforced as 1 request per second. Short bursts of requests can exceed the limit and trigger rate limit errors."* Ein Lauf kann also weit unter der Minutenrate liegen und trotzdem abgewiesen werden — gegen genau das hilft nur ein Mindestabstand, nicht ein Minutenkontingent.

Für einen Hintergrundjob ohne wartenden Nutzer ist an einem Stoß ohnehin nichts gewonnen: Die Gesamtdauer eines Laufs hängt am Durchschnitt, nicht an der Spitze. Der Mindestabstand ist zudem die einzige der beiden Bauformen, deren schlimmster Fall sich ohne Simulation ausrechnen lässt — was Entscheidung 6 braucht.

**Die bestehenden `*_CONCURRENCY`-Einstellungen bleiben unverändert und behalten ihren Sinn** als Obergrenze *gleichzeitig offener* Anfragen (Speicher, offene Verbindungen). Der Schrittmacher begrenzt die *Rate*. Beide Grenzen gelten nebeneinander; die bindende ist ab jetzt in aller Regel die Rate.

### 3. Ein Schrittmacher je Anbieter und Prozess — nicht je Client

Das Rate-Limit hängt am Anbieterkonto, nicht am Client-Objekt. Beide Cloud-Teilschritte bauen sich je einen eigenen Client (`build_landmark_client`/`build_category_classification_client`); ein Schrittmacher je Client wäre bei zwei gleichzeitig laufenden `classify`-Jobs (zwei Projekte) die doppelte Rate — also genau in dem Fall wirkungslos, in dem er gebraucht wird.

Die Instanzen liegen deshalb in einem eigenen, kleinen Modul `cloud_vision_throttle.py`, das beim Import **je bekanntem Anbieter genau einen** Schrittmacher aus den Einstellungen baut (dieselbe Bauform wie `rate_limit.py::limiter`, das den Login-Limiter ebenfalls auf Modulebene aus `settings` baut — trotz des ähnlichen Namens hat dieses Modul nichts mit jenem zu tun: `rate_limit.py` begrenzt **eingehende** Anfragen an die eigene API).

Das eigene Modul ist keine Kosmetik, sondern die Auflage aus ADR 0059 Punkt 2: Die Registry der Instanzen liest `settings`, `cloud_vision.py` darf das nicht. Der Mechanismus (`CloudRequestThrottle`) bleibt deshalb in `cloud_vision.py` und ist frei von Konfigurationswissen; nur die *Instanzen* leben im neuen Modul, das `config.py` importieren darf.

Der Schrittmacher ist an den Clients ein **Konstruktor-Parameter**, nicht ein dort selbst beschaffter Wert (dasselbe Muster wie `transport` und, seit ADR 0059 Punkt 7, `model`) — sonst wäre er in Tests weder ersetzbar noch ohne echte Wartezeit ausführbar.

### 4. Wiederholt wird ausschließlich `429` — jeder andere Fehler bleibt ein sofortiger Skip

Wiederholt wird genau dann, wenn der Anbieter den Statuscode `429` liefert. Für alles andere bleibt das Verhalten aus ADR 0025 Punkt 3/ADR 0032 Punkt 5 **wortwörtlich unverändert**: ein Netzwerkfehler, eine Zeitüberschreitung, ein `5xx`, ein `401`/`403` und eine unerwartete Antwortstruktur führen weiterhin ohne jede Wiederholung zum Überspringen des Fotos.

Das ist keine Bequemlichkeit, sondern die Trennlinie: `429` ist die einzige Antwort, mit der der Anbieter selbst zusagt, dass dieselbe Anfrage später funktioniert. Ein `5xx` sagt das nicht, ein `401` sagt das Gegenteil, und eine Wiederholung nach ungültigen Zugangsdaten wäre eine Wiederholung, die nie gelingen kann.

**Insbesondere wird Anthropics `529 overloaded_error` nicht wiederholt.** Er ist ein eigener, von `429` getrennter Code und bedeutet laut Anthropic-Doku (abgerufen 2026-09-10) eine Überlastung **über alle Nutzer hinweg**, nicht das Ausschöpfen des eigenen Kontingents; ein `retry-after` ist für ihn nicht zugesagt. Die Story schließt Serverfehler ausdrücklich von der Wiederholung aus, und ein eigenes Verlangsamen hilft gegen eine fremde Überlast konzeptionell nicht — für diesen Fall bleibt der nächste Lauf der richtige Weg.

**Nach erschöpftem Wiederholungsbudget endet der Pfad genau dort, wo er heute schon endet:** `raise_for_vision_api_status` wirft die feature-eigene Fehlerklasse mit dem `429`-Status im Text, die Blockschleife zählt einen `failed_call`, schreibt die Zeile in `photo_cloud_vision_errors` (ADR 0035) und überspringt das Foto. Es braucht dafür **keine neue Fehlerklasse und keine Änderung an worker.py's Fehlerpfad**.

### 5. Die Wartezeit ist die Angabe des Anbieters, sonst eine verdoppelnde Staffel — und kein Jitter

Vor jeder Wiederholung wird gewartet:

1. **Anbieterangabe zuerst.** Der `Retry-After`-Antwortheader wird ausgewertet, in beiden vom HTTP-Standard erlaubten Formen (Ganzzahl in Sekunden und HTTP-Datum). Ein fehlender, leerer, unparsbarer, negativer oder in der Vergangenheit liegender Wert ist kein Fehler, sondern schlicht "keine Angabe".
2. **Sonst die Staffel.** `2 s`, `4 s`, `8 s`, … verdoppelnd.
3. **Gedeckelt.** Beide Wege werden auf `VISION_MAX_SINGLE_WAIT_SECONDS` (60 s) je Wartevorgang begrenzt. Ein Anbieter, der 20 Minuten fordert, bekommt sie nicht — siehe Entscheidung 6.

**Die Belegkette der Anbieterangabe ist ungleich, und die Lücke bleibt ausgeschrieben** (dieselbe Ehrlichkeitsauflage wie beim Vision-Fähigkeitsnachweis von `mistral-small-2603`):

- **Anthropic — belegt.** Die Rate-Limits-Doku (abgerufen 2026-09-10) sagt zu: *"you will get a 429 error … along with a `retry-after` header indicating how long to wait"*, und definiert den Wert als *"The number of seconds to wait"*. Also die Ganzzahl-Form, kein HTTP-Datum. Ausdrücklich **ohne** Zusage ist der Header beim Sonderfall "Ausgabenobergrenze der Kontostufe erreicht" — derselbe `429`, aber ohne `retry-after` und ohne Aussicht auf Erfolg (siehe Konsequenzen).
- **Mistral — nicht dokumentiert.** In der gesamten öffentlichen Mistral-Doku (Known limitations, Usage and limits, API-Referenz; abgerufen 2026-09-10) kommt `Retry-After` **nicht vor**; die API-Referenz zu `/v1/chat/completions` dokumentiert überhaupt nur `200`-Antworten. Das offizielle `mistralai`-SDK liest den Header, ist an dieser Stelle aber generierter Standardcode und damit kein Beleg dafür, dass die API ihn sendet.

Genau deshalb ist die Staffel **nicht** die Ausnahme, sondern der tragende Pfad: Der Header wird gelesen, wenn er da ist, und sein Fehlen ist der eingeplante Normalfall. Die HTTP-Datum-Form wird trotz fehlender Zusage beider Anbieter mit ausgewertet — sie ist die zweite vom Standard erlaubte Schreibweise, kostet einen Zweig, und die Alternative wäre, ein gültiges Datum still als "keine Angabe" zu behandeln.

**Nicht ausgewertet wird `retry-after-ms`.** Beide Anbieter-SDKs lesen diesen nicht standardisierten Header und bevorzugen ihn sogar; in **keiner** der beiden API-Dokumentationen kommt er vor. Sein einziger Gewinn wäre Genauigkeit unterhalb einer Sekunde — bedeutungslos, weil jede Wiederholung anschließend ohnehin durch den Schrittmacher mit seinem Mindestabstand läuft.

**Kein Jitter.** Er ist hier überflüssig, weil die Wiederholung **denselben Schrittmacher durchläuft wie ein Erstversuch**: Zwei gleichzeitig gedrosselte Anfragen können nicht im Gleichschritt erneut anklopfen, weil der Mindestabstand sie ohnehin hintereinander einreiht. Ein zusätzlicher Zufallsanteil brächte damit keine Streuung, die es nicht schon gibt, kostete aber eine Zufallsquelle, die in Tests wieder einzufangen wäre.

### 6. Die Lauf-Zeitgrenze wird nicht abgefragt, sondern durch ein gedeckeltes Wartebudget eingehalten

Der naheliegende Entwurf — der Wartevorgang prüft die Restzeit des Laufs — ist hier **nicht möglich und nicht nötig**.

*Nicht möglich*, weil der Wartevorgang tief im HTTP-Client sitzt. Die maßgebliche Zeitgrenze ist keine Restzeit, sondern der Fortschritts-Watchdog: Er vergleicht `last_progress_at` gegen `STALL_THRESHOLD`, und `last_progress_at` wird von der Blockschleife des Workers geschrieben. Um sie zu bedienen, bräuchte der Client Zugriff auf die Session — genau das, was `_detect_landmark_for_photo` ausdrücklich vermeidet ("bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher parallel per `asyncio.gather` laufen können"). Ein Heartbeat aus einer gleichzeitig laufenden Coroutine auf dieselbe Session wäre ein neuer, schwer zu testender Fehlermodus in der teuersten Schleife des Systems.

*Nicht nötig*, weil sich dieselbe Zusage billiger herstellen lässt: **Das Wartebudget wird so gedeckelt, dass ein Block die Watchdog-Schwelle strukturell nicht erreichen kann.** Je Anfrage gilt

- höchstens `VISION_MAX_RATE_LIMIT_ATTEMPTS` (5) Versuche insgesamt,
- höchstens `VISION_RETRY_BUDGET_SECONDS` (120 s) **summierte** Wartezeit über alle Wiederholungen einer Anfrage,
- höchstens `VISION_MAX_SINGLE_WAIT_SECONDS` (60 s) je einzelnem Wartevorgang.

Reicht die verbleibende Budgetzeit für die geforderte Wartezeit nicht mehr, wird **nicht gekürzt gewartet**, sondern sofort aufgegeben: Eine halbe Wartezeit führt mit hoher Wahrscheinlichkeit auf denselben `429` und verbrennt eine Anfrage, ohne etwas zu gewinnen.

Der schlimmste Fall einer Anfrage ist damit `120 s` Warten plus `5 × 60 s` Antwort-Zeitüberschreitung = **420 Sekunden**, also 7 Minuten gegen eine Schwelle von 15. Ein Block wartet auf seine gleichzeitigen Anfragen, nicht nacheinander — der schlimmste Fall eines Blocks ist deshalb derselbe Wert plus die Einreihung des Schrittmachers.

**Diese Rechnung wird als Invariantentest festgeschrieben** (Bauform wie die Vollständigkeits-Invariante zwischen Modell-Registry und Preistabelle in `test_pricing.py`), damit ein späteres Anheben einer der drei Konstanten nicht still an der Watchdog-Schwelle vorbeiläuft. Der Test ist die eigentliche Verbindung zwischen den beiden Zahlenwelten — im Produktivcode gibt es sie bewusst nicht, weil `cloud_vision.py` `worker.py` nicht importieren darf.

**Die 24-Stunden-Grenze bleibt der äußere Anker.** `asyncio.sleep` ist ein sauberer Abbruchpunkt: Ein `job_timeout` oder ein Worker-Shutdown bricht einen Wartevorgang mit `CancelledError` ab. Damit das trägt, fängt der Wiederholungspfad ausschließlich `Exception`, niemals `BaseException` — ein verschlucktes `CancelledError` machte den Job unabbrechbar und liefe zugleich in den in ADR 0068 Punkt 2 beschriebenen Zustand "Oberfläche sagt fehlgeschlagen, Lauf ruft weiter kostenpflichtig an".

### 7. Genau eine neue Betriebseinstellung: die Rate. Alles andere ist Modulkonstante

`CLOUD_VISION_REQUESTS_PER_MINUTE` (Voreinstellung `0` = "Voreinstellung des Anbieters benutzen", Muster von `LANDMARK_MODEL`) ist die einzige neue Umgebungsvariable. Sie muss eine sein: Die zulässige Rate hängt an der **Kontostufe** des Betreibers, ist also ein Betriebsparameter im Sinne von ADR 0025 Punkt 3 — anders als `VISION_REQUEST_TIMEOUT_SECONDS`, das dort ausdrücklich als "reiner technischer Wert" eingestuft wurde. Ohne diese Variable wäre eine Anpassung an die eigene Kontostufe eine Code-Änderung.

Versuchszahl, Wartebudget, Staffel und Deckel bleiben aus demselben Grund **Modulkonstanten**: Sie hängen an keiner Kontostufe, sondern an der Watchdog-Schwelle aus Entscheidung 6 — und sind damit gerade keine Werte, die ein Betreiber ohne Kenntnis dieser Rechnung verstellen können sollte.

**Der Name bricht bewusst mit der `LANDMARK_*`-Familie.** ADR 0059 Punkt 1 hat die Ungenauigkeit von `LANDMARK_PROVIDER`/`LANDMARK_MODEL` (beide gelten für beide Cloud-Anteile) nur deshalb fortgeschrieben, weil ein Umbenennen für den Betrieb eine breaking Änderung gewesen wäre. Für einen **neuen** Namen gibt es dieses Argument nicht, und der abweichende Präfix trägt hier sogar eine Aussage: Der Wert hängt am Anbieterkonto und gilt für beide Teilschritte gemeinsam — anders als die beiden `*_CONCURRENCY`-Werte, die je Teilschritt getrennt sind.

**Die Voreinstellungen je Anbieter stehen im Code** (`cloud_vision_throttle.py`), mit Quelle und Abrufdatum am Eintrag — dieselbe Belegpflicht, die ADR 0059 Punkt 5 für Modellpreise eingeführt hat. Sie sind bewusst vorsichtig: Eine zu vorsichtige Voreinstellung macht einen Lauf langsamer und ist über die Variable zu heben; eine zu großzügige führt genau den Zustand herbei, den diese Story abschafft.

| Anbieter | Voreinstellung | Herleitung (Recherchestand 2026-09-10) |
|---|---|---|
| `anthropic` | **60/min** (1 Anfrage/s) | Erstparteilich dokumentiert sind für die niedrigste **veröffentlichte** Stufe ("Start") 1.000 RPM und 2.000.000 Eingabe-Token/min — bei ~4.600 Eingabe-Token je Bild (`pricing.py::ASSUMED_USAGE_BY_PROVIDER`) bindet keine der beiden Grenzen. Die Voreinstellung liegt trotzdem weit darunter, weil dieselbe Doku zwei Vorbehalte macht: neue Organisationen starten in einer *Evaluation*-Stufe *"with limits below the standard limits shown on this page"* (Zahlen nicht veröffentlicht), und eine Minutenrate kann sekundengenau durchgesetzt werden. Bei zwei gleichzeitigen Anfragen und mehrsekündigen Antwortzeiten greift dieser Wert im Regelbetrieb ohnehin nicht — er ist eine Obergrenze, keine Bremse. |
| `mistral` | **40/min** (1 Anfrage alle 1,5 s) | **Nicht erstparteilich belegbar.** Mistral veröffentlicht keine Zahlen mehr je Tarif und verweist ausschließlich auf das Admin-Panel des eigenen Kontos; der frühere Hilfeartikel mit den Werten der kostenlosen Stufe liefert seit dem Recherchestand `404`. Der Wert liegt bewusst unterhalb der (nur noch sekundär kolportierten, hier ausdrücklich **nicht** als Beleg herangezogenen) Größenordnung von einer Anfrage je Sekunde. Er ist damit eine begründete Setzung, keine belegte Grenze — und genau der Fall, für den die Variable existiert. |

**Die Belegkette bleibt an dieser Stelle ausdrücklich unvollständig, statt geglättet zu werden.** Der verlässliche Wert für ein konkretes Konto steht nur im Admin-Panel des Anbieters. `docs/setup.md` sagt deshalb, wo er nachzusehen ist und in welche Richtung die Variable dann zu stellen ist.

### 8. Sichtbar wird das im Lauf-Protokoll — keine neue Spalte, kein neues Antwortfeld, keine Anzeige

Zwei Arten von Zeilen, beide auf `WARNING`:

- **Je Wiederholung eine Zeile** mit Anbieter, Versuchszähler, Wartezeit und deren Herkunft (Anbieterangabe oder Staffel). Eine Wiederholung ist nach Entscheidung 2 der Ausnahmefall; eine Zeile je Vorkommen ist deshalb verhältnismäßig und erklärt eine Laufzeit unmittelbar.
- **Je Cloud-Teilschritt höchstens eine Zusammenfassung** — Anzahl der eingereihten Anfragen, summierte Wartezeit, Anzahl der Wiederholungen —, und nur dann, wenn tatsächlich gewartet wurde. Sie entsteht aus der Differenz zweier Zählerstände des Schrittmachers, die der Worker zu Beginn und am Ende des Teilschritts abliest.

**`WARNING`, nicht `INFO`, ist hier keine Übertreibung, sondern die einzige sichtbare Wahl:** Das Root-Level des Projekts ist `WARNING` (ADR 0034 Punkt 2), eine `INFO`-Zeile erschiene in `docker compose logs` gar nicht erst, und die Zusage der Story wäre nicht eingelöst. Sie deckt sich zudem mit der Begründung, mit der ADR 0034 Punkt 3 für den ebenfalls **erwarteten** best-effort-Skip `WARNING` gewählt hat. Bei höchstens zwei Zusammenfassungszeilen je Lauf ist der Preis dafür klein.

**Ausdrücklich nicht Teil dieser Entscheidung:** eine Spalte an den Lauf-Tabellen, ein Feld in einer API-Antwort, eine Anzeige in der Oberfläche und ein Eintrag in `cloud_error_message`. Die Story verlangt Nachvollziehbarkeit im Lauf-Protokoll; eine gedrosselte Anfrage ist kein Fehler, und `cloud_error_message` ist der Fehlerkanal. Eine Migration wäre der teuerste Weg zur schwächsten Aussage.

## Begründung

Die Alternative "gar nichts verteilen, nur wiederholen" wäre kleiner gewesen und hätte die Kern-Zusage der Story ebenfalls eingelöst. Sie ist verworfen, weil sie den Lauf **langsamer** macht als die Verteilung: Ohne Schrittmacher rennt der Lauf in die Grenze, bezahlt jede abgewiesene Anfrage mit Latenz und Wartezeit und nähert sich der zulässigen Rate von oben. Der Schrittmacher hält ihn darunter und macht `429` zum Ausnahmefall — was zugleich die Voraussetzung dafür ist, dass ein enges Wiederholungsbudget (Entscheidung 6) reicht.

Die Alternative "die Wiederholung in die Blockschleife des Workers legen" hätte den `Retry-After`-Header nicht mehr zur Verfügung: Dort ist die Antwort längst zu einer Fehlermeldung eingedampft. Sie hätte den Header über eine angereicherte Fehlerklasse durch zwei Schichten schleusen müssen, um am Ende dieselbe Entscheidung zu treffen — an der Stelle, an der die Information ohnehin schon vorlag.

Der 60-Sekunden-Deckel je Wartevorgang ist keine willkürliche Zahl: Anthropics eigenes SDK befolgt einen `retry-after` ebenfalls nur, solange er *"> 0 und ≤ 60"* Sekunden ist, und fällt darüber auf seinen eigenen Backoff zurück (Quellcode `anthropic-sdk-python`, gelesen 2026-09-10 — ausdrücklich ein Sekundärbeleg, keine dokumentierte API-Zusage). Dass eine unabhängige Umsetzung an derselben Stelle dieselbe Grenze zieht, ist die beste Bestätigung, die für diesen Wert zu bekommen ist.

Die Alternative "ein Client-SDK übernimmt Retry und Backoff" scheidet an einer bestehenden Grundsatzentscheidung aus: Beide Cloud-Anbindungen sind bewusst direkte `httpx`-Aufrufe ohne Anbieter-SDK (ADR 0025 Punkt 1, ADR 0031 Punkt 2). Ein SDK für die Wiederholungslogik einzuführen, hieße eine Abhängigkeit für den kleineren Teil des Problems zu holen — die Verteilung über beide Teilschritte hinweg löst es ohnehin nicht, weil sie einen prozessweiten, anbietergebundenen Zustand braucht.

## Konsequenzen

- Ein Lauf gegen einen drosselnden Anbieter dauert **spürbar länger** und liefert dafür vollständige Ergebnisse. Das ist die ausdrücklich gewollte Richtung der Story ("Verlässlichkeit statt Tempo"), nicht ein hingenommener Nebeneffekt.
- Auch ein Lauf **ohne** jede Drosselung wird langsamer, sobald die Antwortzeiten des Anbieters unter dem Mindestabstand liegen: Der Schrittmacher wirkt immer, nicht erst nach dem ersten `429`. Die Kostenschätzung und die Ist-Kostenerfassung (ADR 0051/0059) sind davon unberührt — es ändert sich, wann eine Anfrage herausgeht, nicht wie viele.
- `CLOUD_VISION_REQUESTS_PER_MINUTE` ist der einzige Hebel, wenn die Voreinstellung nicht zur Kontostufe passt — nach oben bei einer höheren Stufe, nach unten, wenn trotz Verteilung noch `429` auftreten. Ein **sehr** niedriger Wert in Verbindung mit einer hohen `*_CONCURRENCY` kann die Einreihung eines Blocks über die Watchdog-Schwelle heben; die Rechnung aus Entscheidung 6 gilt für die Voreinstellungen, nicht für jede denkbare Konfiguration. `docs/setup.md` und `.env.example` sagen das ausdrücklich.
- Der schlimmste Fall bleibt, dass ein dauerhaft blockierender Anbieter Fotos ohne Ergebnis zurücklässt — wie heute, nur nach fünf Versuchen statt nach einem. Diese Fotos sind unverändert über `photo_cloud_vision_errors` je Foto und über `failed_calls` je Lauf sichtbar und bleiben Kandidaten des nächsten Laufs.
- **Ein Sonderfall wird bewusst nicht erkannt:** Anthropic verwendet denselben `429` auch, wenn die **monatliche Ausgabenobergrenze** der Kontostufe erreicht ist — dann ohne `retry-after` und ohne jede Aussicht, dass ein späterer Versuch gelingt (unterscheidbar nur an einem Feld im Antwortkörper, `error.details.error_code`). Der Wiederholungspfad behandelt ihn wie jede andere Drosselung und verbrennt dabei je Foto bis zu vier zusätzliche, aussichtslose Versuche. Das ist hingenommen, weil die Alternative anbieterspezifisches Auswerten des Antwortkörpers in einer ausdrücklich providerneutralen Funktion wäre und weil der Schaden klein und gedeckelt ist: abgewiesene Anfragen werden nicht abgerechnet, das Wartebudget begrenzt den Zeitverlust je Foto, und der Lauf endet regulär. Erkennbar ist die Lage am Ergebnis — *alle* Cloud-Aufrufe des Laufs schlagen mit `429` fehl —, aufzuklären ist sie in der Abrechnungsansicht des Anbieters, nicht in PhotoSort.
- Das Wiederholen einer Anfrage kostet **kein** zusätzliches Geld: Ein `429` wird nicht abgerechnet, und ein Aufruf zählt in der Lauf-Bilanz erst, wenn er ein Ergebnis geliefert hat (ADR 0051 Punkt 1).
