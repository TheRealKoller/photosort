# 0606 - Eye als lokaler Ersatz für die Cloud-Klassifizierung bewerten

**Status:** Implemented ([PR #607](https://github.com/TheRealKoller/photosort/pull/607))
**Erstellt:** 2026-11-02
**Bezug:** [GitHub-Issue #606](https://github.com/TheRealKoller/photosort/issues/606)
**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die beiden Abschnitte `## Security` und
`## Architektur / Umsetzung` Zusicherungen in der vollen Dreiteilung tragen (was gilt, wofür, was
bei Verletzung passiert) und nicht auf den Richtwert gekürzt werden dürfen.

## Ziel

PhotoSort braucht heute für mehrere Bewertungszwecke ein Cloud-Modell: für die Motivstärken (zwei
der acht Motive sind lokal gar nicht beurteilbar), den Ausschluss von Dokumenten und Screenshots,
die Albumtauglichkeit, die Feinlabels und die Namen von Sehenswürdigkeiten. Ohne Cloud-Freigabe
entsteht kein Album-Entwurf. Das kostet Geld, setzt eine Einwilligung voraus und hängt an der
Verfügbarkeit fremder Dienste.

Das auf dem eigenen Gerät lauffähige Bildmodell „Eye“ (Desert Ant Labs) verspricht Fototypen,
Szenen-Tags, Qualitäts- und Behaltenswert-Einschätzungen sowie die Erkennung geschlossener Augen,
ohne dass ein Foto den Heimserver verlässt. Diese Spec liefert eine belegte Entscheidung, ob und
für welche dieser Zwecke Eye die Cloud ersetzen kann — **sie baut Eye nicht ein**. Anlass ist
Neugier auf das Modell, kein akutes Problem mit den heutigen Ergebnissen.

## User Story

Als Betreiber von PhotoSort möchte ich Eye auf unseren eigenen Fotos zweckweise neben die heutige
Cloud-Klassifizierung stellen, damit ich belegt entscheiden kann, für welche Zwecke ein lokales
Modell die Cloud ersetzen darf.

## Akzeptanzkriterien

- [ ] Der Vergleich läuft auf echten Fotos aus mindestens zwei bestehenden Projekten
      unterschiedlicher Art (z. B. eine Reise mit Sehenswürdigkeiten und ein Familienalltag mit
      vielen Menschen), mit mindestens 100 Fotos je Projekt.
- [ ] Maßstab sind die Ergebnisse der heutigen Cloud-Klassifizierung für dieselben Fotos. Das
      Ergebnis nennt Anbieter und Modell, mit dem diese Ergebnisse entstanden sind.
- [ ] Fehlt für Vergleichsfotos ein Cloud-Ergebnis, dürfen in kleinem Umfang zusätzliche
      Cloud-Aufrufe erfolgen, aber erst nachdem die Kosten vorab angezeigt wurden.
- [ ] Der Vergleich ist getrennt je Zweck ausgewiesen: Motivstärken, Ausschluss als Dokument oder
      Screenshot, Albumtauglichkeit (einschließlich geschlossener Augen und verdeckter Gesichter),
      Feinlabels und Sehenswürdigkeitsnamen. Es gibt kein Gesamturteil über alle Zwecke.
- [ ] Jeder Zweck bekommt genau eines von drei Urteilen: „Eye ist besser“, „gleichwertig“ oder
      „schlechter / nicht geeignet“. Dazu kommen eine Begründung und beschriebene Beispielfotos;
      Bilddaten landen nicht im Repository.
- [ ] Für einen Ersatz der Cloud reicht „gleichwertig“, denn der Nutzen ist die geringere
      Cloud-Abhängigkeit.
- [ ] Daniel muss für den Vergleich kein Foto von Hand labeln. Er beurteilt höchstens
      Gegenüberstellungen, also welches von zwei Ergebnissen besser trifft.
- [ ] Für die Auswertung mit Eye verlässt kein Foto den Heimserver.
- [ ] Das Ergebnis sagt, ob Eye ein typisches Projekt auf dem Heimserver in vertretbarer Zeit
      auswertet, gemessen an der heutigen Laufzeit.
- [ ] Das Ergebnis beziffert, wie viele Cloud-Aufrufe je Projekt wegfielen, wenn Eye die als
      geeignet bewerteten Zwecke übernähme, und welche Zwecke weiter die Cloud brauchen.
- [ ] Die Lizenzbedingungen sind für unsere private Nutzung durch zwei Personen als „klar
      zulässig“, „unklar“ oder „unzulässig“ eingestuft. Dabei sind die nicht abschaltbare
      Lizenzmeldung an den Hersteller und die Pflicht zur Namensnennung ausdrücklich bewertet. Bei
      „unklar“ oder „unzulässig“ wird Eye nicht eingebaut.
- [ ] Der Beta-Status des Modells und die Frage nach seiner weiteren Pflege sind als Restrisiko
      benannt.
- [ ] Das Ergebnis nennt die bestehenden Festlegungen, die ein Einbau berühren würde, namentlich
      „ohne Cloud-Freigabe kein Album-Entwurf, kein stiller lokaler Rückfall“ bei der
      Albumtauglichkeit. Diese Festlegungen werden hier nicht geändert.
- [ ] Am Ende steht eine klare Empfehlung, ob Eye eingebaut werden soll und für welche Zwecke.
      Auch „nein, es bleibt bei der Cloud“ ist zulässig. Folgearbeit wird als eigene Story erfasst;
      diese Story ändert die Anwendung nicht.
- [ ] Was sich mit dieser Stichprobe nicht klären lässt, steht ausdrücklich als offener Punkt im
      Ergebnis.

## Datenmodell-Bezug

Keine Änderung. Das Werkzeug liest Bestandstabellen nur (`photos`, `photo_motif_strengths`,
`photo_motif_assessments`, `photo_album_suitability`, `photo_fine_labels`, `fine_labels`,
`photo_landmark_detections`, `remote_category_classification_runs`, `criterion_scoring_runs`).
Siehe [`docs/architecture.md`](../docs/architecture.md).

## Architektur / Umsetzung

**Ansatz:** einmaliges Auswertungswerkzeug neben der Anwendung. Anwendungscode, Datenmodell,
`docker-compose.yml` und die Docker-Images bleiben unverändert. Das Ergebnis wird als Abschnitt
`## Vergleichsergebnis` an diese Spec angehängt.

**Werkzeug und Laufweg**

- **Ort:** `tools/eye-eval/`, eigener Node-Baum mit `package.json` und eingecheckter
  `package-lock.json`. Bewusst mitcommittet: die Methode ist Teil des Belegs und muss im PR
  prüfbar sein. Der Baum geht in kein Image ein und hängt nicht in `scripts/check.sh` — er ist
  Messwerkzeug, kein Produktcode. In der CI läuft allein der Job `eye-eval`, den der
  Paketsatz-Wächter des Repositories für jedes `package-lock.json` verlangt: Installation mit
  Signaturprüfung und `npm test`, keine Auswertung. Eine spätere Einbau-Story ersetzt oder löscht
  ihn.
- **Eye über das offizielle Node-SDK** `@desert-ant-labs/eye/native` (linux-x64). Ein eigener
  LiteRT-Interpreter auf den rohen `.tflite`-Gewichten scheidet aus: die Lizenz erlaubt eine
  Nutzung ohne SDK nirgends ausdrücklich, und ein solcher Weg berührt die Lizenzgrauzone, die die
  Lizenzregel der Modellwahl-ADR 0022 meidet.
- **Laufumgebung:** Wegwerf-Container `node:22-bookworm` (bringt `libcurl.so.4` des nativen SDK
  mit) im Compose-Netz. Eingebunden: das Volume `photo_cache` **schreibgeschützt** und ein
  Arbeitsverzeichnis **außerhalb des Repositorys**, z. B. `~/photosort-eye-eval/`, zugleich `$HOME`
  des Containers.
- **Modell:** `eye.tflite` und `eye_meta.json` einmalig von Hugging Face in das Arbeitsverzeichnis,
  fest auf Revision `v1.0.0`; geladen über `Eye.load({ directory })`, damit im Lauf kein Download
  stattfindet.
- **Eingabe:** die `display`-Variante aus dem Cache (`thumbnails.py::display_path`, höchstens
  2048 px, nach EXIF gedreht) — dasselbe Bild, das die Cloud bekommen hat, damit beide Seiten
  identische Pixel sehen. Rohpixel dekodiert das Werkzeug selbst (`sharp`). Weichen
  `photos.etag` und Cache-Datei voneinander ab, fällt das Foto aus der Stichprobe und wird gezählt.

**Der heutige Maßstab**

- **Zugriff:** direkt aus Postgres über eine Verbindung mit `default_transaction_read_only=on`.
  Maßstab ist der aktuelle Stand je Foto, weil die Tabellen am Foto hängen, nicht am Lauf.
- **Stichprobe:** Fotos, die den Ausschuss überlebt haben und eine Cloud-Bewertung tragen — im
  selben zusammengesetzten Kriterium wie `select_remote_category_candidates`: eine
  `photo_motif_assessments`-Zeile mit `source='cloud'` **und** eine Zeile in
  `photo_album_suitability`. Mindestens 100 je Projekt, mindestens zwei Projekte unterschiedlicher
  Art.

| Zweck | Quelle |
|---|---|
| Motivstärken | `photo_motif_strengths` (8 × `strength`) |
| Ausschluss | `photo_motif_assessments.excluded_document` |
| Albumtauglichkeit | `photo_album_suitability.level` und `.reason` |
| Feinlabels | `photo_fine_labels.raw_label` plus `fine_labels.canonical_key` |
| Sehenswürdigkeit | `photo_landmark_detections` (`name`, `canonical_name`, `confidence`) |
| Landmark-Kandidat | `photo_criterion_scores.value` zu `landschaft` / `gebaeude` |
| Anbieter/Modell | `model` und `provider` der Laufzeilen |
| Laufzeit, Aufrufe | `started_at`/`finished_at`, Phasenzähler, `api_calls`, `landmark_api_calls` |

Grundgesamtheit der Sehenswürdigkeiten sind die Landmark-Kandidaten des Laufs; eine fehlende
Zeile heißt dort „kein Name“. Kandidat ist ein Foto, wenn in `photo_criterion_scores` der Wert zu
`landschaft` oder `gebaeude` die Schwelle 0,01 erreicht — dieselbe Regel und derselbe Wert wie im
Produktionslauf (`criteria.py::is_landmark_candidate`); beide Werte werden beim Anlegen der
Stichprobe aus der Datenbank gelesen, nicht im Werkzeug geraten. Fotos ohne Kandidatur kommen im
Zweck Sehenswürdigkeit nicht vor; sie sind weder Paar noch „beide gleich“.
Die Laufzeilen sind `remote_category_classification_runs.model` und
`criterion_scoring_runs.landmark_model`.

**Zusätzliche Cloud-Aufrufe für Fotos ohne Maßstab:** dafür entsteht kein neuer Code. Daniel
startet in der Oberfläche einen normalen Klassifizierungslauf mit Cloud
(`POST /projects/{id}/classify` mit `use_cloud=true`); vorher zeigt `GET …/classify/estimate` den
Betrag. Die Kandidatenauswahl überspringt bereits voll bewertete Fotos, es gehen also nur die Fotos
ohne Maßstab an den Anbieter. Das Werkzeug selbst ruft **nie** einen Cloud-Anbieter auf.
Nebenwirkung: wie jeder Lauf erzeugt dieser einen neuen Kriterienlauf und rechnet Gliederung und
Auswahlvorschlag neu.

**Abbildung Eye → fünf Zwecke.** Die Tabellen in `tools/eye-eval/` stehen wörtlich im Ergebnis und
werden **vor** dem ersten Vergleichslauf festgelegt und danach nicht mehr geändert, damit sie nicht
nachträglich an die Ergebnisse angepasst werden.

- **Motivstärken:** je Motiv aus `motifs.py` eine Funktion aus Eye-Signalen — Szenen (558) und
  `type`; `faces_detect` (Anzahl und Fläche) für `menschen`; `pets` und Szenen für `tiere`; Szenen
  für `landschaft`, `stadt_strasse`, `bauwerk_sehenswuerdigkeit`, `essen_trinken`; Szenen und
  `shot` für `aktivitaet` und `detail_stimmung` (die beiden heute lokal nicht beurteilbaren).
  Verglichen wird je Motiv über eine Schwelle „trifft zu / trifft nicht zu“ und eine
  Rangkorrelation.
- **Ausschluss Dokument/Screenshot:** Eye-`type` ∈ {`document`, `screenshot`, `receipt`, …} gegen
  `excluded_document`; falsch Ausgeschlossene und übersehene Dokumente getrennt ausgewiesen.
- **Albumtauglichkeit:** `aesthetic`, `keeper`, `reject`-Gründe, Schärfe sowie aus `faces_analyze`
  `eyes_open`/`blink` und `occlusion` gegen `level` 1–5 (Rangkorrelation), gesondert die benannten
  Mängel aus `album_suitability.py` (geschlossene Augen, verdeckte Gesichter) in beide Richtungen.
- **Feinlabels:** stärkste Eye-Szenen und -Tags gegen `raw_label`. Die Vokabulare sind
  verschieden, ein automatischer Treffervergleich entfällt — das Urteil kommt aus dem
  Paarvergleich.
- **Sehenswürdigkeitsnamen:** Eye liefert nur Szenenkategorien, keine Eigennamen. Auf den
  Landmark-Kandidaten wird gemessen, wie oft Eye eine Bauwerk- oder Wahrzeichen-Szene erkennt.
  Erwartetes Urteil: „schlechter / nicht geeignet“, mit dieser Begründung.

**Paarvergleich (Daniel labelt nichts):** eine statische HTML-Seite **im Arbeitsverzeichnis
außerhalb des Repositorys** zeigt je Foto das Cache-Bild und beide Ergebnisse, links/rechts je Foto
neu zufällig und ohne Hinweis auf die Herkunft. Daniel wählt „A trifft besser / beide gleich / B
trifft besser“; die Wahl landet in einer lokalen JSON-Datei. Ins Ergebnis gehen nur Zählungen und
beschriebene Beispiele. Vorgelegt werden Abweichungsfälle und eine kleine Zufallsauswahl
übereinstimmender Fälle.

**Laufzeit und eingesparte Aufrufe:** Der Eye-Durchsatz wird je Foto auf dem Heimserver gemessen
(alle Funktionen zusammen), auf die Fotozahl des Projekts hochgerechnet und der Dauer des letzten
Klassifizierungslaufs gegenübergestellt. Motivstärken, Ausschluss, Albumtauglichkeit und Feinlabels
kommen heute aus **einem** Aufruf je Foto (`run_remote_category_classification`), die
Sehenswürdigkeit aus einem eigenen. Ein Aufruf fällt nur weg, wenn **alle** seine Zwecke ersetzt
sind; ersetzt Eye einen Teil, spart das höchstens Ausgabe-Tokens, keinen Aufruf.

**Das Ergebnis bleibt textlich:** welche Auflagen für den Bericht im öffentlichen Repository gelten,
steht vollständig unter `## Security` (S6–S11) und wird hier nicht wiederholt.

**Festlegungen, die ein Einbau berühren würde** (werden hier nur benannt, nicht geändert): kein
Rückfall auf einen lokal gebildeten Qualitätswert und kein Album-Entwurf ohne Cloud-Freigabe (ADR
0095), Lizenzregel und kein drittes schweres Framework (ADR 0022), Modell-Assets als gepinnter
Download (ADR 0033), Motive und Ausschluss nur über einen neuen kostenpflichtigen Lauf (ADR 0091).
Dazu die Laufzeitfrage: das SDK gibt es nur für Node, Swift und Kotlin, das Backend ist Python.

**Ausführung** auf dem Heimserver mit den echten Projekten, nicht in der Entwicklungsumgebung.
Aufrufe, SDK-Version und Modell-SHA-256 stehen im `## Vergleichsergebnis`.

**Keine ADR jetzt:** in kein Produkt-Image kommt eine neue Abhängigkeit, System und Datenmodell
bleiben unverändert. Fällig wird eine ADR erst mit einer Einbau-Story; sie muss die Anbindung aus
dem Python-Backend, die Lizenzmeldung im Dauerbetrieb, das Verhältnis zu ADR 0022/0033 und die
Ablösung von ADR 0095 klären. `docs/architecture.md`, `docs/setup.md` und das README bleiben
unverändert — es ist eine einmalige Auswertung, kein Betrieb.

## UI/UX

**Keine Produktoberfläche, kein Design-System-Geltungsbereich.** Einzige sichtbare Fläche ist die
Wegwerf-Seite aus `tools/eye-eval/`, außerhalb von `frontend/`, nicht ausgeliefert und von keinem
Frontend-Test erfasst. Tokens, Tailwind und Kontrastvertrag aus
[`0004-design-system.md`](../architecture/0004-design-system.md) sind dort nicht bindend; es gelten
nur „Durchsatz vor Erklärung“ und „Die Fotos sind der Star“. Eine handgeschriebene Seite ohne
UI-Bibliothek genügt.

- **Ablauf:** ein Durchlauf je Zweck, Zweck im Kopf; Foto groß und unbeschnitten oben, darunter zwei
  gleich breite Ergebnisblöcke A und B, darunter „A trifft besser · beide gleich · B trifft
  besser“; Fortschritt als „Foto 37 von 120“, kein Zwischenstand der Urteile.
- **Blindheit:** A/B **je Foto** neu zufällig, nicht je Seite oder Sitzung; beide Seiten in
  derselben knappen Form (Urteil plus eine Begründungszeile, gleiche Feldreihenfolge), ohne
  Modell-/Anbieternamen, Konfidenzzahlen, Logo oder Kommentar im Quelltext; Auflösung erst am Ende.
- **Lesbarkeit:** Begründung bei 100 % ohne Zoom lesbar (mindestens 14 px), Umschalter „ganzes Bild
  / 100 %“ für die Details, an denen das Urteil hängt (Augen, Gesichter, Schärfe).
- **Bedienung:** Tastatur zuerst — `A`/`B`/`=` wählen, `Enter`/`→` weiter (erst nach einer Wahl),
  `←` zurück, `S` überspringen; sichtbarer Fokus, kein Hover-Zwang, Trefferflächen mindestens
  44 px; eine Wahl ist bis zum Weiterblättern änderbar und zählt nie durch einen Fehlgriff.
- **Zustände:** ladendes Bild als Platzhalter; fehlendes oder beschädigtes Bild sichtbar
  übersprungen statt still gezählt; sichtbare Speicherbestätigung nach jeder Wahl, Schreibfehler
  deutlich; Fortsetzung nach Neuladen an der letzten Wahl; Abschlussseite mit Zählungen je Zweck.

Kein Design-System-Nachtrag, keine Frontend-Tests, keine eigene Barrierefreiheits-Stufe.

## Security

**Sicherheitsrelevant, kein Blocker.** Neu sind ein ausgehender Kontakt zu einem Dritten
(Lizenzprüfung), ein Fremdpaket mit Lesezugriff auf alle Familienfotos und die Datenbank, und ein
Text, der in ein öffentliches Repository geht. Kein neuer Endpunkt, keine neue Eingabe von außen,
keine Änderung an Auth oder an der Sichtbarkeit zwischen den beiden Nutzern.

**Lizenzprüfung — „kein Foto verlässt den Heimserver“: Kriterium erfüllt.** Die Inferenz läuft im
Container auf dem Heimserver; die Lizenzprüfung überträgt laut Lizenz §7 nur Metadaten (Install-ID,
App-Kennung, Modell und Version, SDK-Name und -Version, Plattform), keine Bilddaten, Inputs,
Outputs oder Dateinamen.

- **S1 — Der Check bleibt unverändert.** §6/§7 verbieten Deaktivieren, Blockieren, Verschlechtern,
  Spoofen, Verfälschen und einen Build ohne ihn; er hat kein Opt-out. Schlägt er fehl, läuft das
  Modell weiter — für diese Auswertung entsteht keine Verfügbarkeitsabhängigkeit.
- **S2 — Drei Alternativen sind verboten, auch „nur für den Test“:** (a) Blockieren — hosts-/DNS-
  Senke, Firewall-Regel, Netz ohne Route zu `events.desertant.com`; (b) Umleiten —
  `DAL_LICENSE_ENDPOINT` auf localhost oder einen anderen Host, Proxy-Umschreibung; (c) Spoofen —
  gefälschte Lizenzantwort, gepatchtes SDK, gefälschte Install-ID. Jede verletzt die Lizenz und
  damit ADR 0022; bei „unklar/unzulässig“ wird Eye nicht eingebaut.
- **S3 — Nur `DAL_APP_ID=photosort-eye-eval` wird gesetzt.** Ein gesetztes
  `DAL_LICENSE_ENDPOINT` bricht den Lauf ab. Kein API-Key im SDK (nicht nötig, fügt nur eine
  Kontozuordnung hinzu). Die Install-ID bleibt im Arbeitsverzeichnis unter `$HOME`, nie im Repo,
  nie im Bericht; weil `$HOME` dauerhaft dort liegt, zählt ein Container-Neustart nicht als neue
  Installation.
- **S4 — Strengere Lesart:** „kein Paket verlässt den Heimserver“ wäre nur mit Offline-Lizenz
  erfüllt (signierte Lizenz, Kontakt `licensing@desertant.com`). Das ist nicht das formulierte
  Kriterium; würde es so gemeint, ist es eine Produktentscheidung — bis dahin gilt: Eye nicht
  einsetzen.
- **S5 — Ausgehender Verkehr im Lauf: nur `events.desertant.com`.** Kein eingehender Port, kein
  weiteres Ziel; die Datenbank liegt im Compose-Netz. Die Allowlist ist kein Blockieren des Checks,
  sie lässt genau das Ziel zu, das er braucht.

**Bericht im öffentlichen Repository** — einmal gepusht, nicht zurückholbar, deshalb Prüfung vor
dem ersten Push statt danach.

- **S6 — Keine Bilddaten:** keine Vorschau, kein Ausschnitt, kein Base64, keine `data:`-URL, keine
  Nachzeichnung; keine Dateinamen, Pfade, EXIF/GPS-Daten, kein Aufnahmedatum oder -ort.
- **S7 — Keine Eigennamen:** Personen nur als Rolle („Erwachsener“, „Kind“), Orte nur als Gattung
  („Wahrzeichen“, „Altstadt“, „Strand“), Projekte als „Projekt A/B“, wenn ihr Name einen Ort trägt;
  keine Kombination aus Ortstyp, Zeitraum und Projekt, die auf ein Reiseziel schließen lässt.
- **S8 — Nur Zählungen, Zwecke, Urteile und handgeschriebene Prosa:** keine A/B-Zuordnung, keine
  Zeile je Foto, keine Install-ID.
- **S9 — Arbeitsdaten außerhalb des Repos:** Vergleichsseite, A/B-JSON, Analyse-JSON, Bildkopien
  und Gewichte liegen unter `~/photosort-eye-eval/`; der Werkzeugbaum hat keinen Schreibpfad ins
  Repo. Bildkopien und Analysedaten werden nach der Auswertung mit dem Arbeitsverzeichnis gelöscht.
- **S10 — Der Lauf druckt keine Namen:** stdout trägt nur Zählungen, Detaildaten bleiben in Dateien
  im Arbeitsverzeichnis — sonst geraten Datei- oder Ortsnamen in das Sitzungstranskript.
- **S11 — Gate vor dem ersten Push:** (a) der Diff enthält nur Markdown — keine Binärdatei, kein
  `data:image`, keine Zeichenkette mit `.jpg/.jpeg/.png/.heic`, kein Pfad mit `/`; (b) Daniel liest
  `## Vergleichsergebnis` gegen, weil nur er die Namen der Familie und die Orte kennt. Ein Treffer
  wird vor dem Push umformuliert, nie in einem Folge-Commit nachgebessert.
- **S12 — Die Vergleichsseite ist statisch und lokal:** keine CDN-, Font-, Skript- oder
  Analyse-URL, geöffnet über `file://` oder `127.0.0.1`, nie an `0.0.0.0` gebunden, nie
  veröffentlicht.

**Datenbank, Zugangsdaten, Mounts**

- **S13 — Read-only wird geprüft, nicht angenommen:** Verbindung mit
  `options=-c default_transaction_read_only=on`, der Lauf liest `SHOW
  default_transaction_read_only` und bricht bei allem außer `on` ab; ausschließlich `SELECT`, kein
  `INSERT`/`UPDATE`/`DELETE`/DDL, kein `pg_dump`, kein `COPY TO`.
- **S14 — Kleinste Datenmenge:** nur die oben genannten Tabellen plus `photos` (Id, Projekt,
  `etag`) und `photo_criterion_scores` **nur** für die beiden Schlüssel `landschaft` und
  `gebaeude` — sie entscheiden, welche Fotos überhaupt Landmark-Kandidaten sind. `users`
  (Passwort-Hashes) und `person_references` (biometrische Referenzvektoren) werden nicht gelesen;
  kein Tabellenexport ins Arbeitsverzeichnis.
- **S15 — Nur die Datenbank-URL verlässt die `.env`:** zur Laufzeit aus `POSTGRES_*` gebildet und
  über eine gefilterte Env-Datei (Rechte 600) übergeben, die nur für den Lauf existiert.
  `--env-file .env` ist verboten — damit gingen OpenCloud-App-Token, `SECRET_KEY` und die
  Anbieter-Keys an Fremdcode. Kein Secret im Werkzeugbaum, in Paketdateien, Logs, Fehlermeldungen
  oder im Bericht; Verbindungsfehler werden ohne DSN ausgegeben.
- **S16 — Kein Repo im Container:** eingebunden sind nur eine Kopie von `tools/eye-eval/` im
  Arbeitsverzeichnis, `photo_cache` read-only und das Arbeitsverzeichnis read-write. Kein
  Docker-Socket, kein `--privileged`, kein veröffentlichter Port, `--rm`, nicht als root.
- **S17 — `npm ci` läuft im Container, nie auf dem Host:** sonst liefen Lifecycle-Skripte mit
  Daniels Rechten über das ganze Repo und `$HOME`. Funktioniert das Paket ohne sie, zusätzlich
  `--ignore-scripts`.
- **S18 — Restrisiko, benannt:** die DB-Rolle ist die Anwendungsrolle und darf schreiben;
  `default_transaction_read_only` ist Sitzungsschutz, keine Berechtigungsgrenze. Für den
  Einmal-Lauf mit einem Werkzeug ohne Schreibpfad technisch begrenzt — jede dauerhafte Verwendung
  setzt eine eigene Read-only-Rolle voraus. Im Compose-Netz erreicht der Container auch das Backend
  (ohne JWT nur `401`, Login rate-limitiert); OpenCloud ist über S5 nicht erreichbar, sein Token
  liegt nicht im Container.

**Gewichte und SDK (Supply Chain)**

- **S19 — Exakter Pin:** `@desert-ant-labs/eye@4.2.3` ohne `^`/`~`, eingecheckte `package-lock.json`
  mit Integritäts-Hashes, Installation über `npm ci`. Die transitiven Abhängigkeiten deklarieren im
  Paket Caret — der Pin entsteht allein durch das Lockfile.
- **S20 — Gewichte gepinnt und gehasht:** Bezug bei HF-Revision `v1.0.0`; Commit-SHA der Revision
  und SHA-256 jeder Datei werden festgehalten und vor jedem Lauf geprüft. Im Lauf findet kein
  HF-Download statt. Kein `HF_TOKEN`. Gewichte liegen im Arbeitsverzeichnis, nie im Repo.
- **S21 — Ehrliches Restrisiko:** der native Kern ist ein vorgefertigtes Binary eines
  source-available (nicht quelloffenen) Pakets und läuft mit Lesezugriff auf den gesamten
  Fotocache — wie jeder Bilddecoder. Der Pin schützt gegen einen später getauschten Stand, nicht
  gegen den veröffentlichten; das Binary ist nicht prüfbar. Getragen wird das von S5, S16 und
  davon, dass das Paket in kein Produktimage kommt.
- **S22 — Keine neue Abhängigkeit im Produkt:** nicht in `backend/pyproject.toml`,
  `frontend/package.json`, einem Dockerfile, `docker-compose.yml`, `scripts/check.sh` oder einem
  Image. Der CI-Job `eye-eval` prüft ausschließlich Installation mit Signaturprüfung und die
  Unit-Tests dieses Baums; er ist keine Produktabhängigkeit.

**Erst für einen Einbau relevant** (hier nicht entworfen): monatliche Lizenzabfrage aus dem Produkt
und der Hinweis in der Datenschutzerklärung; Namensnennung („Powered by Desert Ant Labs“);
Gewichte und natives Binary im Produktimage samt Third-Party-Notices; dauerhafter Fotozugriff mit
eigener Read-only-Rolle und CPU-Budget; eine Produktentscheidung mit eigener ADR, sobald Eye die
Albumtauglichkeit ohne Cloud übernähme; Ablage- und Löschregel für abgeleitete sensible Daten
(geschlossene Augen, Lächeln, Personenzahl).

**Zu prüfen und ohne Befund:** keine Auth-/Berechtigungsänderung, keine Eingabe von außen, kein
XSS-/CSRF-Bezug, keine geänderte Sichtbarkeit zwischen den beiden Nutzern, kein Schreibzugriff des
Werkzeugs, keine Bilddaten im Repository. Das Securitykonzept
([`0003`](../architecture/0003-securitykonzept.md)) wird im Umsetzungs-PR um eine Zeile unter
„Angriffsflächen“ fortgeschrieben.

## Teststrategie

Testlauf `node --test` über `npm test` im Werkzeugbaum, kein zusätzliches Framework und kein jsdom:
der Seiten-Generator wird als reine String-Funktion geprüft. `scripts/check.sh` führt ihn nicht,
der CI-Job `eye-eval` führt `npm test` aus — TDD gilt ohnehin, der Rot-Lauf wird im PR belegt.
Kein Test lädt das SDK, öffnet einen Socket oder braucht Bilddaten: die SDK-Aufrufe liegen hinter
einer dünnen Adaptergrenze, alles Prüfbare ist reine Funktion über bereits ermittelte Signale.

- **Unit** (`tools/eye-eval/test/*.test.js`): Auswahl, Basis-Extraktion je Zweck, eingefrorene
  Zuordnungstabelle, A/B-Zuweisung, Blinding im HTML, Entscheidungs-JSON, Ersparnis-Arithmetik,
  Report-Prüfer.
- **Integration, opt-in** (`npm run test:db` mit `EYE_EVAL_TEST_DATABASE_URL`, nur auf dem
  Heimserver, nicht Teil von `npm test`): Read-only-Verbindung und Etag/Cache-Abgleich. Ein stiller
  Skip gilt nicht als Nachweis; der Laufbericht hält fest, ob er lief.
- **Manuell, im Laufbericht belegt:** Modell-Pin und SHA-256, unveränderte Lizenzmeldung, Laufzeit
  je Foto, tatsächliche Verschiedenart der Projekte, Personen- und Ortsnamen im Fließtext,
  Urteilsqualität.
- **Nicht testbar:** SDK-Interna und Lizenzprüfung (Fremdcode), Bildinhalt.

Randfälle: Auswahl — genau 100 ist zulässig, 99 bricht ab statt still zu verkleinern; Ausschuss und
fehlende Cloud-Basis fallen raus und werden gezählt; zwei Projekte mit leerer oder gleicher
„Art“-Angabe brechen ab. Etag — fehlende oder abweichende Cache-Datei zählt als Ausfall, fällt ein
Projekt dadurch unter 100, bricht der Lauf ab. Basis je Zweck — fehlende Landmark- oder
Feinlabel-Zeile heißt „keine Basis für diesen Zweck“ (gezählte Teilmenge), kein Laufabbruch.
Zuordnungstabelle — `Object.freeze` plus Hash-Konstante, Abweichung vom gespeicherten Hash eines
Vorlaufs bricht vor dem ersten SDK-Aufruf ab. Blindheit — seed-deterministische Zuweisung, stabil
über Reload, beide Seiten besetzt, keine feste Alternation; das Markup enthält nur „A“/„B“, die
Zuordnung liegt in einer eigenen Mapping-Datei. Entscheidungen — JSON-Roundtrip und Fortsetzung
nach Reload, beschädigte oder fehlende Datei bricht mit Meldung ab statt still zurückzusetzen.
Ersparnis — ein Kategorie-Aufruf zählt nur bei 4/4 ersetzten Zwecken, der Landmark-Aufruf
unabhängig davon, Fotos ohne Cloud-Aufruf zählen 0. Report-Prüfer — Pfad, Dateiendung, Projekt- und
Landmarkname sind ein Befund; Personennamen im Fließtext bleiben manuelle Prüfung.

Das Testkonzept ([`0002`](../architecture/0002-testkonzept.md)) wird um einen Absatz „Werkzeuge
außerhalb des Coverage-Gates (`scripts/`, `tools/`)“ ergänzt: erster Node-Baum ohne
Coverage-Gate, eigener `node --test`-Lauf im Wegwerf-Container und im CI-Job `eye-eval`,
opt-in-DB-Test, Rot-Nachweis im PR.

## Entscheidungen

- **Umfang ist die Bewertung, nicht der Einbau** (Stakeholder): erst vergleichen, dann entscheiden;
  ein Einbau wird eine eigene Story.
- **„Gleichwertig“ genügt für einen Ersatz** (Stakeholder): der Nutzen ist die geringere
  Cloud-Abhängigkeit, nicht bessere Ergebnisse.
- **Zusätzliche Cloud-Aufrufe sind erlaubt, aber erst nach angezeigten Kosten** (Stakeholder):
  umgesetzt über den bestehenden Klassifizierungslauf mit Kostenvorschau statt eines zweiten
  Cloud-Pfads.
- **Die Lizenz ist Teil des Ergebnisses, kein Ausschlusskriterium im Voraus** (Stakeholder): bei
  „unklar“ oder „unzulässig“ wird Eye nicht eingebaut.
- **`architect` konsultiert (Schritt 1):** konkreter Bezug zu `remote_classification.py`,
  `landmark.py`, dem Cache-Pfad und den Ergebnistabellen.
- **`ux-ui-designer` konsultiert (Schritt 2):** die Seitenvergleichs-Seite ist eine benennbare
  sichtbare Fläche, auch wenn sie außerhalb von `frontend/` liegt; Blindleit und Lesbarkeit berühren
  die Beweiskraft der Story.
- **`test-engineer` konsultiert (Schritt 3):** Auswahl, Blinding, Ersparnis-Arithmetik und
  Report-Prüfung sind nicht-triviales Verhalten und unterliegen dem TDD-Zwang, obwohl sie außerhalb
  des Coverage-Gates liegen.
- **`security-engineer` konsultiert (Schritt 3):** Lizenzprüfung als ausgehender Kontakt,
  Lesezugriff eines Fremdpakets auf alle Familienfotos und die Datenbank, Bericht in einem
  öffentlichen Repo.
- **Node-SDK statt eigener LiteRT-Interpreter** (technisch): die Lizenz erlaubt die Nutzung ohne SDK
  nicht ausdrücklich; diesen Grauzonenweg schließt die Lizenzregel aus ADR 0022 aus.
- **Werkzeug wird committet, aber in kein Image eingehängt** (technisch): die Methode ist Teil des
  Belegs und muss auf den Heimserver. In der CI prüft ein eigener Job nur Installation und
  Unit-Tests; die Auswertung selbst bleibt beim Heimserver.
- **Keine ADR in dieser Story** (technisch): keine Produktabhängigkeit, keine System- oder
  Datenmodelländerung; die ADR-Pflicht entsteht mit einer Einbau-Story.
- **Kein Berichts-Substrat im Repo außer dem Text** (technisch): Bildkopien, A/B-Zuordnung und
  Analysedaten leben außerhalb und werden nach der Auswertung gelöscht.

## Offene Fragen

Keine. Was das Ergebnis selbst klären muss, steht dort als offener Punkt (letztes
Akzeptanzkriterium).

## Out of Scope

- Jeder Einbau von Eye in die Anwendung: Code, Abhängigkeit, Konfiguration, Datenmodell, Image.
- Die Entscheidung selbst, ob Eye eingebaut wird — diese Spec liefert die Grundlage.
- Duplikat- und Serienerkennung sowie Personenerkennung; sie laufen bereits lokal.
- Eine Änderung der Festlegungen aus ADR 0095, 0022, 0033 und 0091, auch wenn das Ergebnis sie
  berührt.
- Eine Änderung von Kostenvorschau, Modell-Registry oder Klassifizierungslauf.
- Die Wahl unterschiedlicher Modelle je Zweck und ihre Bedienung in der Oberfläche.

## Vergleichsergebnis

**Nachtrag (2026-11-02, PR #607):** Der Status steht auf `Implemented`, weil das Werkzeug unter
`tools/eye-eval/` umgesetzt und durch `node --test` abgesichert ist — die Akzeptanzkriterien
selbst beschreiben den Auswertungslauf und sind damit noch nicht erfüllt. Dieser Abschnitt bleibt
bis zu diesem Lauf ein Platzhalter und wird danach an dieser Stelle angehängt; eine Änderung am
Status geht damit einher.

*Wird nach dem Auswertungslauf angehängt — Anbieter und Modell des Maßstabs, Urteil und Begründung
je Zweck, Laufzeit, eingesparte Aufrufe, Lizenzeinstufung, Restrisiken, Empfehlung, offene Punkte.
Es gelten die Auflagen aus `## Security` (S6–S11) und `## Architektur / Umsetzung`.*
