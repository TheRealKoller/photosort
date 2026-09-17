# 0481 - Restdauer eines laufenden Klassifizierungslaufs

**Status:** Accepted
**Erstellt:** 2026-09-17
**Bezug:** [GitHub-Issue #481](https://github.com/TheRealKoller/photosort/issues/481)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Der Grund liegt in der Teststrategie: Drei
Zusagen dieser Spec — die Bindung zweier Spalten aneinander, die Ruhe der Anzeige über eine
Antwortfolge und die Unversehrtheit der Projektantwort — sind Aussagen über etwas, das *nicht*
passieren darf. Jede braucht ihren Prüfaufbau ausgeschrieben, weil sie sonst grün bestünde, ohne
zu prüfen.

## Ziel

Ein Klassifizierungslauf über eine größere Fotomenge läuft lange. Die Oberfläche sagt heute nur,
wie viele Fotos verarbeitet sind — an keiner Stelle, wie lange es noch dauert. Wer davorsitzt,
kann deshalb nicht entscheiden, ob sich Warten lohnt oder ob der Rechner in der Zeit anderweitig
gebraucht wird.

Diese Spec gibt dem laufenden Lauf eine zeitliche Dimension: am laufenden Teilschritt eine
geschätzte Restdauer, bewusst als grobe Spanne statt als scheingenaue Zahl, damit die Unsicherheit
sichtbar bleibt.

Der Zuschnitt ist eng: ausschließlich der gerade laufende Lauf eines Projekts. Keine
projektübergreifende Prognose, keine Warteschlangen-Gesamtsicht, keine Vorhersage für noch nicht
gestartete Läufe. Betrifft beide Nutzer.

## User Story

Als Nutzer, der einen Klassifizierungslauf angestoßen hat, möchte ich während des Laufs sehen, wie
lange er voraussichtlich noch dauert, damit ich entscheiden kann, ob ich warte oder den Rechner in
der Zeit anderweitig nutze.

## Akzeptanzkriterien

Die Kriterien sind gegenüber dem Issue auf Prüfbarkeit geschärft. Wo die ursprüngliche Fassung ein
Urteil verlangte ("wird nicht unruhig", "als Näherung erkennbar"), steht jetzt die mechanisch
prüfbare Aussage, die dieselbe Zusage trägt.

- [ ] **AK1:** Während eines laufenden Klassifizierungslaufs trägt genau der Teilschritt im Zustand
      `running` eine Zeitangabe. Kein Teilschritt im Zustand `pending`, `done` oder `skipped` trägt
      eine. Im DOM existiert zu jedem Zeitpunkt höchstens **eine** Zeitzeile, und sie liegt
      innerhalb des `<li>` mit `data-step-state="running"`.
- [ ] **AK2:** Jede angezeigte Zeitangabe ist ein Element eines geschlossenen Textvorrats (die
      sieben Stufentexte, "wird noch ermittelt", "erfahrungsgemäß kurz"). Über den gesamten
      Wertebereich der gelieferten Sekundenzahl entsteht kein Text außerhalb dieses Vorrats. Keine
      Einzelzahl.
- [ ] **AK3:** Zwei Teilzusagen. (a) Die Restdauer fährt in derselben Antwort mit wie der
      Fortschritt und ist damit nie seltener aktuell als er. (b) Der angezeigte Text ändert sich
      erst, wenn derselbe neue Text in zwei aufeinanderfolgenden Antworten steht; eine Antwortfolge,
      die zwischen zwei Stufentexten pendelt (A,B,A,B,A,B), erzeugt **null** sichtbare Wechsel.
- [ ] **AK4:** Solange keine belastbare Schätzung vorliegt, steht dort der eine feste Text "wird
      noch ermittelt" — für alle drei Ursachen ununterscheidbar: zu wenige verarbeitete Einheiten,
      zu kurze Zeit seit Phasenbeginn, kein gespeicherter Phasenbeginn (Altzeile nach der
      Migration). Weder ein leeres Feld noch eine Zahl.
- [ ] **AK5:** Der Teilschritt `ranking` trägt nie einen gemessenen Wert (serverseitig immer `null`)
      und zeigt einen Erfahrungstext, der keine Ziffer enthält und nicht mit "noch ca." beginnt. Die
      Unterscheidung ist zusätzlich maschinenlesbar (`data-eta-kind="experience"`).
- [ ] **AK6:** Eine Gesamtrestzeit für den gesamten Lauf **entfällt ersatzlos**. Sie wäre zu Beginn
      des Laufs nicht belastbar zu bilden, und nur dann sollte es sie geben (ADR 0116 Punkt 6).
- [ ] **AK7:** Gegenstandslos erfüllt, da AK6 entfällt.
- [ ] **AK8:** Nach Abschluss, Fehlschlag oder Abbruch steht keine Restdauer mehr da — auch dann
      nicht, wenn die Lauf-Zeile noch einen Teilschritt-Wert trägt. Der Zustand "beendet, aber
      `phase` nicht zurückgesetzt" existiert am Bestand und darf keine Zeitangabe erzeugen.
- [ ] **AK9:** Fortschrittswert (`x/y`), Balken und Zustandswort stehen gleichzeitig mit der
      Zeitangabe da. Die Zeitangabe ist ein zusätzlicher Knoten, kein Ersatz.
- [ ] **AK10:** Kein Eingabezustand der Restdauer-Rechnung nimmt die Projektantwort mit.
      `GET /projects` und `GET /projects/{id}` antworten mit 200 und vollständiger Liste, auch wenn
      Nenner null, Zähler null, Phasenbeginn abwesend oder Phasenbeginn in der Zukunft ist.

## Datenmodell-Bezug

`CriterionScoringRun` bekommt eine Spalte `phase_started_at: datetime | None` (naives UTC wie jede
andere Zeitspalte im Bestand). Additiv, nullbar, ohne `server_default`, ohne Datenwanderung.
Alembic-Revision `ab602909001e` auf `bcc517b1ab22`. Keine weitere Entität berührt;
`docs/architecture.md` zieht im selben Pull Request nach.

## Architektur / Umsetzung

**Entscheidung:** ADR
[`0116`](../decisions/0116-restdauer-als-servermessung-spanne-im-frontend-keine-gesamtrestzeit.md).

Die Restdauer ist eine **Servermessung**, die Spanne eine **Darstellung im Frontend**.

### Backend

`phase` und `phase_started_at` werden ausschließlich gemeinsam gesetzt, über eine einzige Funktion
`_set_phase` in `worker.py`. Bricht diese Bindung, rechnet die Messung den Beginn des vorigen
Teilschritts gegen den Fortschritt des aktuellen — die Restdauer ist zu groß, ohne Fehler und ohne
Testrot. Ein Quelltext-Wächter und ein Verhaltens-Nachsatz halten die Bindung fest (Teststrategie).

**Die erste Phase jedes Laufs ist der Sonderfall, an dem diese Bindung entkommt.** Sie wird heute
nicht per Zuweisung gesetzt, sondern als Konstruktor-Schlüsselwort
(`CriterionScoringRun(… phase=…)`, `worker.py` ~2942–2951). Entweder legt der Konstruktor die Zeile
mit `phase=None` an und `_set_phase` wird direkt nach dem `refresh` gerufen, **oder** der Wächter
zählt das Konstruktor-Schlüsselwort mit. Wird das Muster der bestehenden Schreibstellen-Wächter
(`taken_at`, `selection_position`) unbesehen übernommen, die diese Form ausdrücklich ausschließen,
entkommt genau die Stelle, die die erste Phase setzt — und die gesamte erste Phase jedes Laufs
zeigt dauerhaft "wird noch ermittelt", schweigend.

Betroffen sind fünf Zuweisungen plus eine Konstruktorstelle: `worker.py` 355 (`_fail_run`, auch vom
Watchdog), 2336, 2513, 2861, 2869 und 2948.

`CriterionScoringRunSummary` bekommt **ein** Feld `phase_remaining_seconds: float | None` — die
Restdauer des in `phase` genannten Teilschritts. Kein Feld je Teilschritt: Es läuft immer genau
einer, ein erledigter hat keine Restdauer, ein ausstehender keine Messgrundlage. Damit ist AK8 eine
Eigenschaft der Antwort, keine Regel der Oberfläche.

Gerechnet wird in einer reinen Funktion `classification_eta.py::remaining_seconds(*,
phase_started_at, now, processed, total)` aus dem Durchsatz seit Beginn des Teilschritts:
`(total − processed) · (now − phase_started_at) / processed`. Kein gleitendes Fenster — es bildete
jede kurze Schwankung ab (AK3).

Das Ergebnis ist `null`, solange nicht alle drei gelten: bekannter Nenner > 0, ≥ 3 verarbeitete
Einheiten, ≥ 15 s seit Phasenbeginn (benannte Konstanten). Für `ranking` ist es immer `null`.

**Die Schwellenprüfung steht vor der Division, nicht daneben.** Die Rechnung läuft in
`_criterion_scoring_run_summary` und damit im Lesepfad **jeder** Projektantwort (`GET /projects`,
`GET /projects/{id}`), im Zwei-Sekunden-Takt des Pollings. Ein unbehandelter `ZeroDivisionError`
dort nimmt nicht das Feld, sondern die gesamte Projektübersicht mit (HTTP 500). Ein pauschales
`except Exception: return None` ist ausdrücklich **kein** zulässiger Ersatz für die Reihenfolge: Es
deckt auch jeden anderen Rechenfehler zu.

Zwei Randfälle mit festgelegtem Ergebnis: `processed > total` ergibt `0.0`, nicht `null` — "wird
noch ermittelt", wenn die Arbeit faktisch fertig ist, wäre die falschere Aussage. `now <
phase_started_at` (Uhr-Rückschritt) ergibt `null`, nicht einen Betrag: Die Messgrundlage ist
ungültig, nicht die Restdauer kurz.

Die Zuordnung Teilschritt → Zähler steht serverseitig: `criteria` an der Lauf-Zeile,
`remote_categories` am verknüpften Remote-Lauf, `landmark` an den `landmark_*`-Spalten. Das Frontend
bildet sie nicht nach. **Kein zusätzlicher Datenbankzugriff je Projekt** — die Rechnung läuft über
bereits geladene Werte; eine Abfrage je Projekt fiele im Zwei-Sekunden-Takt an (ADR 0103 Punkt 1).

Der naive-UTC-Zeitpunkt wird jetzt an zwei Stellen gebraucht (Worker und Lesepfad) und bekommt
deshalb genau eine Definition in `clock.py::now_utc()`; `worker.py::_now_utc` liest sie. Zwei Uhren
mit verschiedener Zeitzonenbehandlung ergäben eine Restdauer, die um Stunden danebenliegt, ohne dass
etwas fehlschlägt.

### Frontend

`deriveClassificationSteps` hängt den gelieferten Wert an den Schritt im Zustand `running` und
vergibt eine Art: `measured` (Zahl vorhanden), `unknown` (`null`) oder `experience` (`ranking`). Aus
der Sekundenzahl entsteht über die Stufenleiter (siehe UI/UX) eine Spanne, nie eine Einzelzahl.

Die Ruhe der Anzeige (AK3) trägt sich auf vier Mittel: den kumulierten Durchsatz, die Schwellen, die
Stufenleiter und `useSteadyEtaText.ts` — ein geänderter Stufentext wird erst übernommen, wenn er in
zwei aufeinanderfolgenden Antworten steht. **Ein Wechsel des Teilschritts setzt das zurück**, damit
kein Text des vorigen Schritts in den nächsten hineinragt; der Rücksetzfall gewinnt gegen die
Verzögerung. Die allererste Angabe eines Teilschritts wird nicht verzögert.

**Die Zuordnung Phase → Zähler existiert nach dieser Änderung zweimal** — serverseitig für die
Restdauer, im Frontend in `classificationSteps.ts::progressOf` für `x/y`. Laufen sie auseinander,
zeigt dieselbe Zeile einen Fortschritt und eine dazu nicht passende Restdauer. Die Endpunkt-Testfälle
je Phase sind der Abgleich.

### Betroffene Dateien und Reihenfolge

1. **Zeit und Phasenwechsel** — `clock.py` (neu), `models.py` (Spalte), Migration
   `ab602909001e`, `worker.py::_set_phase` samt allen sechs Stellen oben, Quelltext-Wächter.
   Noch keine sichtbare Änderung.
2. **Reine Rechnung** — `classification_eta.py` (neu) plus die beiden Schwellwert-Konstanten. Ohne
   DB, ohne Uhr, `now` als Parameter.
3. **API** — `CriterionScoringRunSummary.phase_remaining_seconds`, befüllt in
   `_criterion_scoring_run_summary`.
4. **Frontend-Ableitung** — `api/types.ts`, `utils/classificationEta.ts` (neu),
   `utils/classificationSteps.ts`.
5. **Darstellung** — `hooks/useSteadyEtaText.ts` (neu), `components/ClassificationProgress.tsx`.
6. **Doku** — `docs/architecture.md` im selben Pull Request.

## UI/UX

Die Restdauer erscheint als eigene Textzeile unter den Meta-Angaben und vor dem Fortschrittsbalken,
an derselben Position wie `CloudDetail`, mit `text-xs text-text-muted` und
`data-eta-kind="measured|unknown|experience"`. Layout, Balken und `x/y`-Zeile bleiben unangetastet
(AK9).

**Stufenleiter.** Beide Ränder tragen bewusst **keine** Zahl: AK2 schließt jede Einzelzahl aus, und
"noch ca. 30 Sekunden" wäre genau eine.

| Gelieferte Restdauer | Angezeigter Text |
|---|---|
| < 60 s | nur noch wenige Sekunden |
| 60 s – < 2 min | noch ca. 1–2 Minuten |
| 2 – < 5 min | noch ca. 2–5 Minuten |
| 5 – < 10 min | noch ca. 5–10 Minuten |
| 10 – < 20 min | noch ca. 10–20 Minuten |
| 20 – < 40 min | noch ca. 20–40 Minuten |
| ≥ 40 min | noch über 40 Minuten |

**`unknown`** → "wird noch ermittelt". **`experience`** (nur `ranking`) → "erfahrungsgemäß kurz".

Der Unterschied zwischen gemessener und Erfahrungsangabe trägt sich über den **Wortlaut** und
`data-eta-kind`, nicht über eine Kursivierung: `italic` kommt im gesamten Frontend nicht vor, und
`ClassificationProgress` führt die Regel bereits, dass eine Aussage am ausgeschriebenen Wort hängt
und nicht allein an einer visuellen Auszeichnung.

**Barrierefreiheit.** Die Zeile läuft in der bestehenden `aria-live="polite"`-Liste mit. Stufenleiter
und Zwei-Antworten-Regel machen den Text selten wechselnd — seltener als die `x/y`-Zahlen, die dort
heute schon im Zwei-Sekunden-Takt mitlaufen. Eine visuell sichtbare, für Screenreader stumme
Restdauer wäre eine Barriere gegen genau den Zweck der Story.

Ausstehende und übersprungene Schritte bekommen keine Angabe; die Messung ist nur am laufenden
Schritt sinnvoll (AK1).

Kein neues Token, keine neue Komponente.

## Security

Nicht sicherheitsrelevant. Kein neuer Endpunkt, keine neue Eingabe von außen, kein Secret, keine
Änderung an Auth und keine Änderung an der Sichtbarkeit zwischen den beiden Nutzern.

`phase_remaining_seconds` ist kein Informationsleck. Das Feld geht über den router-weit
auth-pflichtigen Torwächter von `/projects` an genau die beiden Nutzer, denen dieselbe Antwort schon
heute alle zwei Sekunden `started_at`, `photos_total`, `photos_processed` und die Zähler je
Cloud-Teilschritt liefert. Die Rechnung ist eine Ableitung aus bereits gelieferten Werten; sie
wandert vom Klienten auf den Server und erschließt keine Angabe, die der Klient nicht schon bilden
könnte.

`phase_started_at` trägt keinen Nutzerbezug — `criterion_scoring_runs` führt keine `user_id` und
bekommt keine. Die Migration ist additiv und nullbar, ohne `server_default`, ohne Datenwanderung und
ohne Fremdschlüssel; der Löschgraph der Projektlöschung verläuft über Tabellen und Fremdschlüssel
und bleibt unberührt.

Das Sicherheitskonzept wird nicht fortgeschrieben: Die Angriffsfläche ist dort bereits beschrieben,
und ein Eintrag "Spec 0481 ändert daran nichts" wäre Doku-Ballast.

## Teststrategie

**Backend-Unit (`classification_eta.py`), tabellengetrieben.** Rechnung gegen einen nachgerechneten
Wert bei eingespeister `now`. `None` je Schwelle einzeln, Grenzen einschließend geprüft:
`total` = 0/`None`; `processed` = 0, 1, 2 **und 3** als erster erlaubter Wert; `elapsed` = 14,9 s
**und** 15,0 s. `phase_started_at is None` → `None` ohne Ausnahme. `now < phase_started_at` → `None`
als **eigenständiger** Fall, damit eine spätere Umstellung auf `abs()` rot wird. `processed > total`
→ `0.0`. Dazu ein Gegenfall: Eine unerwartete Eingabe muss **laut** scheitern statt als `None` zu
erscheinen — ohne ihn bliebe ein späteres `except Exception: return None` grün und hebelte die
Reihenfolge "Schwellenprüfung vor Division" aus.

**Backend-Wächter (`test_models.py`, neben den bestehenden Schreibstellen-Wächtern).** Drei
Zusicherungen statt einer, weil die erste allein auch gegen ein `_set_phase` bestünde, das den
Zeitstempel vergisst: die Menge der Funktionen in `worker.py`, die `phase` setzen, ist **gleich**
`{"_set_phase"}`; dasselbe für `phase_started_at`; und `_set_phase` setzt beide. Paketweit: Die
Menge der Module, die eines der Felder schreiben, ist gleich `{"worker.py"}` — sonst wandert die
Schreibstelle nach `api/projects.py` und der modulinterne Wächter bleibt grün.

Erkannte Schreibformen, jede einzeln an einem Schnipsel nachgewiesen: Attribut-Zuweisung,
**Konstruktor-Schlüsselwort** (Abweichung von den Vorgänger-Wächtern, Begründung oben),
Dict-Schlüssel eines gebündelten Updates, `.values(phase=…)`. Gegenproben ebenfalls einzeln: ein
gleichnamiger Funktionsparameter oder eine lokale Variable zählt nicht; `PhotoCloudVisionError(phase=…)`
— anderes Modell, gleichnamige Spalte — zählt nicht; Lesen zählt nie. Vergleich über
`ast.Attribute.attr`, nie über ein Textmuster: `"phase"` als Teilstring träfe `phase_started_at`,
`cloud_phases` und `CloudVisionPhase`. Suchraum gemessen (`rglob`), nicht gelistet. Bekannte Grenze,
benannt statt verschwiegen: `setattr` und ein gerechneter Spaltenname sind statisch unsichtbar —
dagegen steht der Verhaltens-Nachsatz, nicht dieser Wächter.

**Verhaltens-Nachsatz.** `assert_phase_binding(run)` am Ende jedes Worker-Falls, der einen Lauf
bewegt: `(phase is None) == (phase_started_at is None)`, und über eine vollständige Abfolge
(`remote_categories → criteria → landmark → ranking → None`) wächst der Zeitstempel bei jedem
Wechsel **streng monoton**. Ohne die Monotonie bestünde die Bindung auch gegen ein `_set_phase`, das
den alten Zeitstempel stehen lässt — genau der Fehler, den ADR 0116 beschreibt.

**Backend-Integration (Endpunkt).** Je Teilschritt ein Fall mit der Zuordnung Phase → Zähler.
Pflichtfall gegen den wahrscheinlichsten Fehler: Phase `landmark` bei `photos_processed ==
photos_total` (Kriterien fertig) und Landmark-Zählern bei 2/50 — der Wert muss aus den
Landmark-Zählern kommen; ein `photos_processed`-Rückgriff ergäbe hier dauerhaft "nur noch wenige
Sekunden", ohne dass etwas fehlschlägt. `ranking` → immer `null`. Lauf beendet → `null`, zusätzlich
der Fall "beendet, aber `phase` gesetzt" (AK8). Entartete Zustände → 200 **und vollständige Liste**;
die Listenlänge gehört in die Zusicherung, sonst bestünde der Test auch gegen eine Antwort, die nur
noch ein Projekt enthält (AK10).

**Ein Fall ohne Uhr-Attrappe:** `phase_started_at` wörtlich als
`datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=…)` gesetzt, Ergebnis gegen ein Band
geprüft. Ein Fixture-Zeitstempel, der aus derselben `now_utc()` stammt wie der Produktivcode, ist um
denselben Betrag falsch und bliebe grün. Monkeypatch-Falle: Bezieht `api/projects.py` die Uhr als
`from .clock import now_utc`, wirkt ein Patch auf `photosort.clock.now_utc` **nicht** — gepatcht wird
`photosort.api.projects.now_utc`.

**Migration (`test_migration_restdauer.py`, Vorlage `test_migration_seitenverhaeltnis.py`).**
Revision hängt am aktuellen Kopf; `upgrade` legt die Spalte nullable an; eine Bestandszeile mit
`status='running'` **und gesetzter `phase`** überlebt mit `phase_started_at IS NULL` (der von ADR
0116 benannte Zustand, nicht irgendeine Altzeile); `INSERT` ohne die Spalte funktioniert weiter;
`downgrade` entfernt die Spalte und lässt die Zeile stehen.

**Frontend-Unit.** `classificationEta.ts`: je Stufengrenze ein Fall **genau auf** ihr (einschließend
geprüft — `>` statt `>=` verschöbe jede Stufe); 0 s und ein sehr großer Wert für die Randtexte;
Bildmengen-Prüfung über einen Streifzug des Wertebereichs (erzeugte Textmenge = die sieben
Stufentexte, nichts darüber hinaus, AK2); Erfahrungstext ohne Ziffer und ohne "noch ca."; `EtaKind`
in `deriveClassificationSteps` inklusive: Wert hängt am `running`-Schritt und an keinem anderen.

**Frontend-Hook (`useSteadyEtaText`), Prüfgegenstand ist eine Antwortfolge (AK3).** `[A]` → A
sofort. `[A,B,A,B,A,B]` → durchgehend A, **null** Wechsel. `[A,B,B]` → B beim **dritten** Eintrag,
nicht beim zweiten und nicht später. Rücksetzfall: Teilschritt wechselt mitten im Fenster → der neue
Text gilt sofort, der alte ragt nie hinein — geprüft mit **verschiedenen** Texten, weil der Fehler
bei zufällig gleichem Stufentext unsichtbar bliebe. Obergrenze der Textwechsel über eine fest im
Test notierte, gestreute Folge, die einen ~30-Minuten-Lauf nachbildet; ohne sie ist die Zusage auf
zwei Antworten kalibriert.

**Frontend-Komponente.** Genau eine Zeitzeile, im `running`-`<li>`; kein anderer Zustand trägt eine;
`data-eta-kind` in allen drei Ausprägungen; die Zeile liegt innerhalb der `aria-live`-Liste;
Fortschrittswert, Balken und Zustandswort stehen unverändert daneben (AK9 als eigener Fall, nicht
als Seiteneffekt der Bestandstests); beendeter Lauf → keine Zeitzeile.

**E2E: nichts, und keine neue Datei unter `e2e/`.** Der Demo-Bestand hat heute keinen laufenden
Lauf, und seine Zeitstempel hängen an festen Ankern von 2024 — ein `phase_started_at` von dort
ergäbe dauerhaft "noch über 40 Minuten", also gerade nicht die Stufen, die ein Blick prüfen soll.
Ein `now`-relativer Zeitstempel bräche die Determinismus-Zusage des Seeders. Die Zeile bringt keine
neue Geometrie und kein neues Überlaufverhalten; das E2E-Aufnahmekriterium des Testkonzepts ("nur,
was jsdom prinzipiell nicht kann") ist nicht erfüllt.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) ist im selben Pull Request fortgeschrieben.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR 0116 angelegt.
- `ux-ui-designer` konsultiert (Schritt 2). Zwei seiner Festlegungen sind bewusst geändert: Die
  Stufenleiter trug an beiden Rändern eine Einzelzahl ("noch ca. 30 Sekunden", "10+ Minuten"), was
  AK2 widerspricht — beide Ränder sind jetzt Texte ohne Zahl. Und die Zeile bleibt in der
  `aria-live`-Region, weil die Begründung dagegen ("ändert sich bei jedem Poll") durch Stufenleiter
  und Zwei-Antworten-Regel nicht zutrifft.
- `test-engineer` konsultiert (Schritt 3): AK1–AK5, AK8 und AK9 auf Prüfbarkeit geschärft, AK10 neu.
  Testkonzept fortgeschrieben.
- `security-engineer` konsultiert (Schritt 3): nicht sicherheitsrelevant, am Bestand belegt.
  Sicherheitskonzept bewusst **nicht** fortgeschrieben.
- **AK6 entfällt ersatzlos**, nicht vertagt — an der Bedingung des Issues, nicht am Aufwand (ADR
  0116 Punkt 6). Wer eine Gesamtrestzeit später will, braucht zuerst gespeicherte Dauern je
  Teilschritt über mehrere Läufe; das ist eine eigene Entscheidung.
- `processed > total` ergibt `0.0` statt `null`, `now < phase_started_at` ergibt `null` statt eines
  Betrags.
- Der Unterschied gemessen/Erfahrung trägt sich über Wortlaut und Datenattribut statt über
  Kursivierung.

## Offene Fragen

- `demo_state.py` legt einen abgeschlossenen Lauf (`status=SUCCESS`) mit gesetzter
  `phase=CRITERIA` an. Das widerspricht der Invariante, auf die ADR 0116 seine AK8-Zusage stützt.
  Der Seeder wird im Zuge dieser Spec auf `phase=None` korrigiert (kein Test pinnt den Wert);
  AK8 ist zusätzlich so gefasst, dass der Lesepfad sich nicht allein auf `phase` verlässt. Die Frage
  an Daniel ist nur, ob die Seeder-Korrektur in diesen Pull Request gehört oder in einen eigenen —
  sie ist hier mit aufgenommen, weil die Zusage sonst gegen den eigenen Demo-Bestand falsch wäre.

## Out of Scope

- Eine Gesamtrestzeit für den gesamten Lauf (AK6, siehe oben).
- Restdauer für die übrigen Läufe (Scan, Ausschuss-Bewertung). Sie führen keinen Teilschritt-Zeiger.
- Gespeicherte Dauern vergangener Läufe und jede daraus abgeleitete Prognose.
- Projektübergreifende Prognose oder eine Warteschlangen-Gesamtsicht.
- Eine Aussage über die **Treffsicherheit** der Schätzung. Geprüft ist die Rechnung, nicht ihre
  Güte; es gibt keinen gespeicherten Durchsatz, gegen den sich messen ließe.
