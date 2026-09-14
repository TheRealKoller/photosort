# 0105 - Ortsnamen aus dem lokalen Datensatz, betrieben als Auszug auf einem Volume

**Frühere Nummer:** 0103 (bis 2026-09-14), aufgelöste Dublette mit
`0103-bestandszahlen-an-projectout-stand-bleibt-frontend-ableitung.md`.

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** ADR [`0102`](./0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md)
Punkt 6 (die dort offen gelassene Wegwahl wird hier getroffen), Spec
`specs/features/0434-ortsnamen-fuer-events.md`

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Wegwahl selbst nur ein Satz ist und
das Tragende daneben liegt: die Grenzen der Messung, die sie stützt, und der Betriebsweg, ohne den
die Wahl im Betrieb nicht ankommt.

## Kontext

ADR 0102 Punkt 6 hat die Wahl zwischen lokalem Ortsdatensatz und externem Dienst hinter ein
Protokoll gestellt und an eine Messung an einem echten Projekt gebunden. Die Messung ist gelaufen
(2026-09-14, 408 Fotos, 50 Events, 10 verschiedene Ortszellen).

## Die Messung

**Lokal (GeoNames `allCountries`):** 10 von 10 gefragten Zellen mit Ortsnamen, davon 8 zusätzlich
mit Viertel. Kein Fehltreffer, kein Treffer, der nur eine Region nennt. Block D: von 17 Events ohne
Sehenswürdigkeit bekämen 16 einen Ortsnamen, eines bliebe bei Nummer und Zeitspanne; 12 der
benannten wären gleichnamig, 8 davon per Viertel unterscheidbar. Block E: 100 % der 282 Fotos mit
Koordinate liegen in einer Zelle mit auflösbarem Ortsnamen.

**Extern (Photon): ausgefallen, nicht gemessen.** 10 von 10 Zellen endeten im Ausfallgrund
`http-status` — die Verbindung stand, es kam ein Fehlerstatus statt Daten. Systematisch, nicht
schleichend; der Verdacht (ungeprüft) ist ein fehlender aussagekräftiger User-Agent. Die Trennung
von Ausfall und Fehltreffer, die ADR 0102 Punkt 5 und Spec 0434 für genau diesen Fall verlangen,
hat gehalten: Photon steht in der Messung als **ungemessen**, nicht als schlecht.

## Entscheidung

### 1. Die Ortsauskunft kommt aus dem lokalen Datensatz (GeoNames)

Der lokale Weg erreicht in der Messung das Maximum — besser als 10 von 10 und 100 % kann kein
Kandidat sein. Ein aufgeklärter Photon-Lauf könnte diese Zahlen bestenfalls einholen, nie
schlagen. Dazu ist der lokale Weg strukturell vorzuziehen: kein Datenabfluss, kein zweiter
Empfänger von Ortsdaten der Familie, keine Abhängigkeit von einer erklärten Demo-Instanz, keine
unbezifferte Ratenbegrenzung. Der Photon-Ausfall wurde deshalb **nicht** aufgeklärt.

**Wer diese ADR später liest, darf nicht glauben, hier hätten zwei Zahlenreihen nebeneinander
gestanden.** Es gab keinen Vergleich. Es gab eine Zahlenreihe, die nichts offenließ, und einen
Kandidaten ohne Zahlen. Die Wahl trägt, weil der Gemessene das Erreichbare ausschöpft — nicht,
weil der Ungemessene schlechter abgeschnitten hätte.

**Was die Stichprobe nicht hergibt.** Gemessen wurde ein Projekt mit 10 verschiedenen Zellen. Dass
100 % über andere Reisen, andere Länder und dünner besiedelte Gegenden hinweg halten, ist plausibel
übertragbar, aber **nicht belegt**. Tragfähig ist die Wahl trotzdem, weil der Rückfall spezifiziert
und harmlos ist: Eine Zelle ohne Treffer lässt ihr Event bei Nummer und Zeitspanne, der Lauf läuft
weiter (ADR 0102 Punkt 5). Eine schlechtere Trefferquote anderswo kostet Namen, nicht Läufe.

### 2. Der Schalter `EXTERNAL_PLACE_LOOKUP_ENABLED` entfällt

Mit der Wahl auf den lokalen Weg schaltet er nichts mehr. ADR 0102 und das Sicherheitskonzept
untersagen seine Umwidmung, weil sein Name genau eine Sache benennt; ein Schalter, der nichts
schaltet, ist Ballast. Er entfällt zusammen mit dem Photon-Kandidaten im Messkommando. Eine
`.env`, die ihn noch trägt, bricht davon nicht (`Settings` läuft mit `extra="ignore"`).

**Der externe Empfänger entfällt damit ganz** — nicht nur vorerst. Ortsdaten der Familie verlassen
das System auf diesem Weg nie; kein Betriebszustand kann das wieder aufmachen.

### 3. Betrieben wird ein vorbereiteter Auszug auf einem eigenen Volume

Die Rohdatei ist für den Betrieb untauglich: `allCountries.txt` misst 1,74 GB bei 13,46 Mio.
Zeilen. Gebraucht wird davon wenig — der Auflöser liest fünf Felder (Name, Breite, Länge,
`featureClass`, `featureCode`) und verwirft jede Zeile außerhalb der Klassen `P` und `A`.

**Der Auszug ist eine GeoNames-Datei mit geleerten Spalten, kein eigenes Format.** Er behält die
Spaltenpositionen des Originals und lässt die ungebrauchten Felder leer. Damit liest ihn
`parse_geonames_line` unverändert, und die Gleichheit zum gemessenen Verhalten ist strukturell,
nicht argumentiert: dieselben Zeilen, dieselben Felder, derselbe Parser. Gemessen (2026-09-14):

| | Zeilen | Größe |
|---|---|---|
| `allCountries.txt` | 13.464.135 | 1,74 GB |
| Auszug (`P`+`A`) | 5.770.883 | 223 MB |
| Auszug, gzip-gepackt | 5.770.883 | **69 MB** |

Abgelegt wird die gepackte Form: 96 % kleiner als die Rohdatei, und ein vollständiger
Lese-Durchgang darüber dauert 3,3 s (gemessen) — der Auflöser geht je Lauf einmal durch.

- **Wo:** eigenes Docker-Volume `place_dataset`, im Backend-Dienst schreibbar, im Worker
  **nur lesend** eingehängt. Genau ein Schreiber, und der operative Pfad ist keiner.
- **Wer erzeugt ihn:** ein Kommando im Produktivpaket, `python -m photosort.place_dataset`, das
  bezieht, den Auszug bildet, das Archiv wieder löscht und den Hash des Auszugs daneben legt.
  Aufgerufen über die Container-Konsole, einmal je Volume. **Kein Shellskript auf dem Host:** Auf
  dem Server gibt es keine Shell, nur eine Oberfläche für Docker Compose und eine
  Container-Konsole. `scripts/fetch-ortsdatensatz.sh` entfällt ersatzlos — eine zweite Fassung
  desselben Ablaufs driftet, und die auf dem Server unbrauchbare wäre die schlechtere.
- **Was der Hash schützt:** den Auszug selbst, also genau die Datei, die gelesen wird. Vor jedem
  Gebrauch geprüft (69 MB, unter einer Sekunde). Das schließt die Lücke, die der Bezug in Teil 1
  offen ließ und benannte: dort war das Archiv geprüft und die daneben liegende entpackte Datei
  nicht. Ungeschützt bleibt weiterhin der **Erstbezug** — dort tragen allein HTTPS und das
  Vertrauen in GeoNames (ADR 0102, Restrisiko der Spec 0434).
- **Was passiert, wenn er fehlt oder der Hash nicht stimmt:** Es wird kein Auflöser gebaut (Muster
  `build_landmark_client` ohne Einwilligung), es entsteht **kein stiller Ersatzweg**, und jeder
  Lauf schreibt eine laute Zeile mit festem Grund-Token. Die Events behalten Nummer und
  Zeitspanne, der Lauf läuft durch. Das ist der Zustand von heute, nicht ein Fehlerzustand.

**Warum nicht ins Docker-Image** (Muster `label_embedder.onnx`): Dort kostete jeder kalte Bau 400
MB von GeoNames und einen Durchgang durch 1,74 GB — auch zweimal je CI-Lauf, weil die Jobs
`docker-compose-check` und `e2e` das Backend-Image bauen. Zudem wechselte der Datensatz bei jedem
Rebuild still auf den Stand der jeweiligen Nacht. Das Volume kostet dafür einen einmaligen
Handgriff je Volume; bis er getan ist, heißen Events wie heute nach Nummer und Zeitspanne.

### 4. Kein Neubezugsrhythmus

Der Auszug wird erneuert, wenn es einen Anlass gibt (ein falscher oder fehlender Name fällt auf),
nicht nach Kalender. Ein automatischer Neubezug wäre ein wiederkehrender ungeprüfter Abruf für
einen Nutzen, den nichts beziffert: Bereits abgelegte `place_lookups` werden von einem neueren
Datensatz ohnehin nicht rückwirkend berührt.

### 5. Namensnennung: eine Zeile am Fuß der Projektliste

GeoNames steht unter CC BY 4.0, die Namensnennung ist Pflicht und wird sichtbar erfüllt: eine
statische Zeile am Fuß der Projektliste — der Einstiegsseite nach der Anmeldung, app-weit statt
projektgebunden, und außerhalb der Arbeitsansichten. Keine neue Komponente, kein neues Token.
Genannt werden Quelle und Lizenz, verlinkt auf `geonames.org` und den Lizenztext.

## Konsequenzen

- `EXTERNAL_PLACE_LOOKUP_ENABLED`, `Settings.external_place_lookup_enabled`, der Eintrag in
  `.env.example` und der Photon-Kandidat in `place_probe.py` entfallen. Sicherheitsauflage S1 der
  Spec 0434 entfällt mit ihm; S2, S4 und S9 verlieren ihren externen Teil.
- Neu: `backend/src/photosort/place_dataset.py` (Bezug und Auszug), Volume `place_dataset` in
  `docker-compose.yml`, Einstellung für den Pfad des Auszugs mit Vorgabe auf dem Volume.
  `scripts/fetch-ortsdatensatz.sh` entfällt.
- Das Kommando bleibt wie `place_probe` von jedem Endpunkt, jedem Compose-`command` und jedem
  automatischen Pfad fern — ein 400-MB-Abruf tritt nur ein, wenn er getippt wird.
- `docs/setup.md` (Bezug des Auszugs, Messkommando ohne den externen Kandidaten) und
  `docs/architecture.md` ziehen im selben Pull Request nach.
- Die Ländervarianz der Trefferquote bleibt offen und wird durch keinen Test gedeckt; sie fällt im
  Betrieb als fehlender Name auf, nicht als Fehler.
