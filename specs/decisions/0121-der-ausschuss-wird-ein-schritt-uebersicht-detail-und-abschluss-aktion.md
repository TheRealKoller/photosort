# 0121 - Der Ausschuss wird ein Schritt: eine Übersicht, eine Detailansicht, eine Abschluss-Aktion

**Status:** Accepted
**Datum:** 2026-09-23
**Bezug:** [GitHub-Issue #525](https://github.com/TheRealKoller/photosort/issues/525), Spec 0525

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil sechs Entscheidungen samt der Grenze
zwischen ihnen (Punkt 5 gegenüber Punkt 6) nicht kürzer auseinanderzuhalten sind.
**Teilweise abgelöst:** ADR [`0104`](./0104-ausschuss-entscheidung-uebersteuert-den-automaten.md).
Abgelöst ist **allein** deren Folge-Notiz „Form und Bedienung des Gates — eine Liste, eine
Abschluss-Aktion, keine Einzelbestätigungspflicht — bleiben unberührt" und die Aufzählung der
Schreibwege in ihren Konsequenzen („einen Endpunkt je Aufnahme und einen je Gruppe"). **Unberührt
gelten** dort der Stern über `PhotoScore.duplicate_of` (Punkt 1), das projektweite Datum ohne
`user_id` (Punkt 2), das Überlebenden-Prädikat samt seiner Asymmetrie und seiner
Sicherheitsauflage (Punkt 3) sowie „keine Id-Liste im Body". Die abgelösten Zusagen der
bisherigen Umsetzung stehen im Spec-Abschnitt „Abgelöste Zusagen".

## Kontext

Erkennung und Sichtung sind heute zwei Pipeline-Schritte, und die Sichtung ist ein Umweg: Der
Schritt „Ausschuss-Gate" führt in die normale, nach Vorschlägen gefilterte Fotoliste
(`PhotoGridPage?gate=1`), aus der heraus je Kachel übernommen und bei Duplikaten auf eine separate
Vergleichsseite gewechselt wird. Übersicht und Detailansicht werden jetzt neu gestaltet.

## Entscheidung

### 1. `ausschuss` und `gate` sind ein Schritt

`StepId` umfasst nur noch `scan | ausschuss | kriterien | kuratierung`. Der zusammengelegte Schritt
heißt „Ausschuss" und ist **erledigt**, sobald `ScoringRun.gate_confirmed_at` gesetzt ist — dasselbe
Abschlusssignal, das heute den Gate-Schritt trägt. Er bleibt **ungated erreichbar**
(`ausschuss.isReachable = true`), und `kriterien.isReachable` hängt unverändert an
`category_selection_enabled && gate_confirmed_at !== null`.

**Grund:** Erkennung, Sichtung und Bestätigung sind eine Nutzerhandlung; ein zweiter Schritt
erzwänge genau die Zwei-Karten-Ansicht, die entfallen soll. Das Signal bleibt getrennt, weil
„gelaufen" und „gesichtet" weiterhin zwei verschiedene Aussagen sind.

**Anzeige der Schrittzahl:** Der Stepper leitet „Schritt n von m" aus `PIPELINE_STEPS.length` ab.
Die beiden wörtlichen „von 5"-Stellen in `Stepper.tsx` (Orientierungszeile und zugänglicher Name)
sind damit falsch und werden mitgezogen.

### 2. Die Übersicht ist ein eigener Lese-Endpunkt mit eigenem Antwortmodell

`GET /projects/{id}/ausschuss` liefert die Einträge der Übersicht, je Eintrag: `photo` (`PhotoOut`),
`reason` (`duplicate` | `low_quality`), `decision` (`keep` | `discard` | `null`) und
`group_anchor_photo_id` (`int | null`). Der Bestand ist **projektweit** und umfasst jede Aufnahme
mit `suggested_status IS NOT NULL` **oder** einer Zeile in `photo_duplicate_decisions` — also
offene, angenommene und aufgehobene zusammen. Paginiert wie die Fotoliste.

`reason` ist `duplicate`, wenn `PhotoScore.duplicate_of IS NOT NULL`; sonst `low_quality` — dieselbe
Ableitung wie `api/photos.py::_suggestion_reason`, ausdrücklich keine zweite. Die Werte werden
**nicht** aus `PhotoOut.suggestion` gelesen (ADR 0111 Punkt 1 untersagt das): Jenes Feld fällt nach
jeder Entscheidung und bei einer Albumbewertung des Anfragenden auf `null`, trägt also weder
`reason` noch `decision` verlässlich.

**Grund:** Der Filter `suggested` ist nutzerbezogen und enthält nur offene Vorschläge; er kann die
entschiedenen Bilder nicht tragen, die die Übersicht als Sichtungsfortschritt zeigen muss.

### 3. Die Detailansicht liegt im Schritt, nicht auf einer fremden Seite

Die Übersicht öffnet die Detailansicht über einen Query-Parameter derselben Schritt-Route
(`/projects/:id/pipeline/ausschuss?photo=<id>`); die Schritt-Route, ihr Erreichbarkeits-Guard und
`PROJECT_ROUTE_PATHS` bleiben unverändert. Die Duplikat-Gruppe eines Bildes kommt in der
Detailansicht aus dem bestehenden `GET /projects/{id}/duplicate-groups/{photo_id}` — **kein**
Wechsel auf die Ansicht „Duplikate vergleichen".

**Grund:** Die Story verlangt das große Bild und die Gruppe in **einer** Ansicht. Ein Verweis auf
`DuplicateComparePage` oder `PhotoDetailPage` wäre der benannte Umweg.

### 4. Die Abschluss-Aktion ist ein projektweiter Schreibweg im selben Aufruf wie der Gate-Vermerk

`POST /projects/{id}/confirm-ausschuss-gate` schreibt in **einer** Transaktion für jede Aufnahme mit
offenem Vorschlag (`duplicates.py::has_open_suggestion`, projektweit) die Zeile `discard` und setzt
danach `gate_confirmed_at`, falls es leer ist. Die Menge bestimmt der **Server**; der Body trägt
weiterhin keine Id-Liste (ADR 0104, Konsequenzen). Der Aufruf ist idempotent: Ein zweiter Aufruf
schreibt nur, was inzwischen wieder offen ist, und überschreibt den Zeitstempel nicht.

**„Manuell geänderte bleiben unangetastet" heißt: Wer eine Entscheidungszeile trägt, ist kein
offener Vorschlag und wird nicht angefasst.** Der Zusatz `discard` einer bereits manuell behaltenen
Aufnahme wäre deren stille Rücknahme.

**EINE Transaktion, ein `commit`.** Ein halb geschriebener Bestand wäre eine willkürliche Teilmenge
im abfließenden Bestand, und der Gate-Vermerk behauptete eine Sichtung, die nur zu einem Teil
stattfand.

**Sicherheit (S1):** Der Abschluss-Schreibweg verkleinert den abfließenden Bestand und kann ihn nie
vergrößern — die einzige geschriebene Entscheidung ist `discard`. Ein Body mit Id-Liste bleibt
untersagt: Er wäre ein Massen-Schreibweg auf beliebige Fotos des Projekts.

### 5. Das Aufheben bleibt auf Duplikat-Verlierer beschränkt

Die Detailansicht bietet „zustimmen" (`discard`) für jede Ausschuss-Aufnahme und „aufheben"
(`keep`) nur dort, wo `duplicates.py::keep_possible_for` wahr ist — also nicht bei einer Ablehnung
wegen geringer Qualität. Das ist die Asymmetrie aus ADR 0104 Punkt 3, gelesen und nicht geändert:
Ein unbedingtes `keep` höbe eine Schärfe-Ablehnung auf, zu der niemand befragt wurde.

### 6. Der Einzel-Schreibweg gilt für jede Ausschuss-Aufnahme

`PUT /projects/{id}/photos/{photo_id}/duplicate-decision` nimmt künftig jede Aufnahme an, die einen
offenen Vorschlag **oder** eine Duplikat-Gruppe hat — projektgebunden wie bisher. Die Antwort bleibt
die Gruppe; für eine Aufnahme ohne Gruppe ist sie der leere Stand.

**Grund:** Die Zustimmung in der Detailansicht muss auch eine Unschärfe-Ablehnung festhalten können.
Der naheliegende Ersatzweg — eine `Rating`-Zeile über `write_own_rating` — ist die nutzereigene
Albumentscheidung, die ADR 0104 Punkt 2 für den Ausschuss ausdrücklich ausschließt.

## Konsequenzen

- `GateStepPage.tsx` entfällt; `AusschussStepPage.tsx` trägt Trigger, Zustände und Übersicht. Der
  Gate-Modus `?gate=1` in `PhotoGridPage.tsx` und sein Bestätigungsaufruf entfallen ersatzlos.
- `RUN_FIELD_BY_STEP`, `getBlockedReason` und `PIPELINE_STEPS` verlieren `gate`; der Blockiert-Grund
  für `kriterien` bleibt Wort für Wort „Bestätige zuerst den Ausschuss oben."
- Der leere und der automatisch bestätigte Ausschuss (`suggestions_found == 0`, Gate setzt sich beim
  Jobabschluss selbst) bleiben dauerhaft sichtbar nachvollziehbar — das bestehende Muster, kein
  flüchtiger Hinweis.
- Der Demo-Bestand trägt beide Gründe bereits: die Duplikat-Gruppen des fünften Demo-Projekts
  (Verlierer ⇒ `duplicate`, der mit-abgelehnte Gewinner ⇒ `low_quality`) und die einzelnen offenen
  Vorschläge der übrigen Projekte. Für die Vorführung eines entschiedenen Bildes ohne Interaktion
  fehlt dort eine Entscheidungszeile — sie wird über die Übersicht selbst erzeugt.
- `docs/architecture.md` zieht den Endpunkt, die geänderte Semantik von `confirm-ausschuss-gate`,
  das Schrittmodell und den Abschnitt zur Vergleichsansicht im selben Pull Request nach.
