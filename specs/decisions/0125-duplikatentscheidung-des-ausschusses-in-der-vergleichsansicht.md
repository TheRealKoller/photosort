# 0125 - Die Duplikatentscheidung des Ausschusses fällt in der Vergleichsansicht

**Status:** Accepted
**Datum:** 2026-09-26
**Bezug:** [GitHub-Issue #533](https://github.com/TheRealKoller/photosort/issues/533), Spec 0533
**Löst teilweise ab:** ADR
[`0121`](./0121-der-ausschuss-wird-ein-schritt-uebersicht-detail-und-abschluss-aktion.md) — aus
Punkt 2 die Form der Einträge (bisher je Eintrag eine Aufnahme) und die Paginierung nach
Aufnahmen; aus Punkt 3 der Teil ab „Die Duplikat-Gruppe eines Bildes kommt in der Detailansicht
aus …" samt Grund. Der Bestand (Vereinigung aus offenem Vorschlag und Entscheidungszeile), die
Ableitung von `reason`, die Form der Detailansicht als Query-Parameter der Schritt-Route und alle
übrigen Punkte von ADR 0121 gelten unverändert, ebenso ADR 0104 und ADR 0111.

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die neue Eintragsform der Übersicht ihre
Sicherheitsbindung (Punkt 2) und der neue Schreibweg die seine (Punkt 4) vollständig tragen müssen.

## Kontext

Die Duplikatentscheidung liegt an zwei Orten: eingebettet in der Ausschuss-Detailansicht und in der
Vergleichsansicht, die aus dem Ausschuss nicht mehr erreichbar ist. In der Übersicht steht jede
Aufnahme einer Gruppe als eigene Kachel. Die Gruppe wird dort zu einem Stapel, die Entscheidung in
der Vergleichsansicht zusammengeführt, und diese bekommt einen Abschluss je Gruppe.

## Entscheidung

### 1. Die Detailansicht verweist in die Vergleichsansicht, statt die Gruppe einzubetten

Bei gesetztem `group_anchor_photo_id` trägt die Detailansicht einen Link auf
`/projects/{id}/photos/{group_anchor_photo_id}/duplicates?from=ausschuss` und lädt die Gruppe nicht
mehr. Ihre Einzelentscheidung bleibt unverändert.

### 2. Die Übersicht fasst jede Duplikatgruppe zu einem Eintrag zusammen

`GET /projects/{id}/ausschuss` liefert in `items` zwei Eintragsarten, unterschieden über `kind`:

- **`photo`** — die bisherige Form (`photo`, `reason`, `decision`, `group_anchor_photo_id`,
  `keep_possible`) für jede Bestandsaufnahme, die in keiner Gruppe liegt.
- **`group`** — genau ein Eintrag je Duplikatgruppe mit mindestens einer Bestandsaufnahme:
  `group_anchor_photo_id`, `cover` (`PhotoOut` der ersten Bestandsaufnahme der Gruppe nach
  `taken_at`, `id`), `member_count` (Bestandsaufnahmen der Gruppe), `group_size` (alle Mitglieder)
  und `decision_counts {undecided, keep, discard}` über den **gespeicherten** Zeilen der
  Bestandsaufnahmen — dieselbe Größe wie `decision` am Einzeleintrag.

**Gruppiert wird nach Mitgliedschaft, nicht nach `reason`:** Schlüssel ist allein
`duplicates.py::representative_of` über `load_duplicate_links(session, project.id)`. Ein wegen
Unschärfe abgelehnter oder von einer Zeile getragener Gewinner liegt damit im Stapel seiner Gruppe.
Eine eigene SQL-Fassung des Sterns ist untersagt: `photo_scores.duplicate_of` zeigt ohne
Projektbedingung auf `photos.id`, der Stapel nähme sonst Aufnahmen eines fremden Projekts auf oder
nennte dessen Gewinner als Anker. Löst sich ein Zeiger nicht auf, bleibt die Aufnahme ein
`photo`-Eintrag und öffnet die Detailansicht — nie eine Vergleichsansicht ohne Gruppe.

**Reihenfolge und Paginierung:** Jeder Eintrag steht an der Stelle seiner ersten Bestandsaufnahme
(`taken_at`, `id`). `limit`, `offset` und `total` zählen **Einträge**; `open_count` zählt unverändert
Aufnahmen mit offenem Vorschlag, weil der Abschluss je Aufnahme schreibt. Der Bestand wird als
leichte Liste (Id, `taken_at`, gespeicherte Entscheidung) in **einer** Anweisung mit Projektbindung
und `has_ausschuss_entry()` geladen, erst danach gruppiert und geschnitten; hydratisiert wird nur die
Seite. Ein Schnitt in SQL vor dem Gruppieren zerlegte eine Gruppe über zwei Seiten in zwei Stapel.

**Der Detailfilter `?photo=<id>`** liefert weiterhin genau einen `photo`-Eintrag oder keinen, auch
für ein Gruppenmitglied — dann mit gesetztem `group_anchor_photo_id`. Die Detailansicht eines
Duplikats bleibt so über den Deep-Link erreichbar; aus der Übersicht öffnet der Stapel die
Vergleichsansicht an seinem Anker. Im Listenzweig trägt kein `photo`-Eintrag einen Gruppenanker.

### 3. Der Rückweg ist ein Query-Parameter der bestehenden Route

`?from=ausschuss` an `PROJECT_ROUTE_PATHS.photoDuplicates`; keine neue Route und kein
Router-Zustand, der beim Neuladen verloren ginge. Es zählt allein der wörtliche Wert `ausschuss`.
Das Ziel von „Zurück zum Ausschuss" ist fest `/projects/{projectId}/pipeline/ausschuss` und wird
nie aus dem Parameterwert gebildet — sonst wäre die Ansicht eine offene Weiterleitung auf eine vom
Link bestimmte Adresse. Gruppennavigation und Gruppenabschluss tragen den Parameter weiter; ohne
ihn fehlt der Rückweg nach dem ersten Blättern.

### 4. Der Gruppenabschluss übernimmt die offenen Vorschläge genau dieser Gruppe

`POST /projects/{project_id}/duplicate-groups/{photo_id}/confirm` im Router
`api/duplicate_decisions.py` (router-weite Auth-Dependency), ohne Body, Antwort `DuplicateGroupOut`.
Der Server löst den Stern **zuerst** auf (`404` vor jedem Schreiben), bildet die Menge in **einer**
Anweisung aus Projektbindung, Mitgliedschaft im Stern und `has_open_suggestion()` und schreibt für
sie `discard` — nur einfügen, nie überschreiben, eine Transaktion, `409` bei einem
Primärschlüsselkonflikt. `gate_confirmed_at` bleibt unberührt.

Das ist ADR 0121 Punkt 4, auf eine Gruppe begrenzt. Ein offener Vorschlag zeigt bereits `discard`;
der angezeigte Zustand ändert sich nicht, er wird festgeschrieben. Mitglieder mit Entscheidungszeile
oder ohne Vorschlag werden nicht geschrieben — ihr angezeigter Zustand gilt schon ohne Zeile.

**Untersagt ist das Festschreiben aus dem Client** mit dem angezeigten Wert über den Einzel- oder
Gruppenweg: Es schriebe `keep` auf den Gewinner ohne Vorschlag, der dadurch über
`has_ausschuss_entry` zum Ausschuss-Eintrag würde, und überschriebe eine gespeicherte Handlung am
unveränderlichen Mitglied — beides ohne Fehler und ohne Meldung.

**Sicherheit:** Die einzige geschriebene Entscheidung ist `discard`; der Weg verkleinert den
abfließenden Bestand und kann ihn nie vergrößern. Die Menge bestimmt der Server, eine Id-Liste im
Body bleibt untersagt. Die neue Aufrufstelle von `has_open_suggestion` erhöht ihren Eintrag in
`tests/test_ausschuss_ueberlebende.py::_ERWARTETE_VERWENDUNGEN`; kein Eintrag wird gesenkt.

### 5. Messwerte und Zeitspanne reisen in der Gruppenantwort

`DuplicateGroupPhotoOut` bekommt `sharpness` und `exposure` (`float | null`, aus `PhotoScore`,
`null` ohne Zeile), `DuplicateGroupOut` bekommt `span_seconds: int` — der Abstand zwischen
frühestem und spätestem `taken_at` der Mitglieder, gebildet in `duplicates.py` aus der bereits
geladenen Kantenliste. Die Messwerte werden **nie aus `PhotoOut.suggestion`** gelesen: Das Feld
fällt nach jeder Entscheidung und bei eigener Albumbewertung auf `null`, die Bewertungszeile
verlöre ihre Werte mitten im Durchgang.

Die Auszeichnung „beste je Messwert" bildet die Oberfläche über den **angezeigten, gerundeten**
Werten; die Antwort zeichnet kein Mitglied aus. Über Rohwerten gebildet, trüge von zwei gleich
angezeigten Werten nur einer die Auszeichnung.

## Konsequenzen

- `AusschussEntryOut` wird zur Vereinigung zweier Modelle mit dem Diskriminator `kind`; der
  TypeScript-Typ folgt. `AusschussStepPage.tsx::AusschussDetailGruppe` entfällt, die Detailansicht
  nutzt `DuplicatePhotoTile` nicht mehr.
- Ein Gewinner, der nur durch eine `keep`-Zeile in den Bestand kommt, erscheint in der Übersicht
  nicht mehr als Einzelkachel „Geringe Bildqualität", sondern in seinem Stapel.
- Beide Schreibwege und der neue Abschluss antworten mit derselben `DuplicateGroupOut` wie der
  Lesepfad; `empty_duplicate_group_out` trägt `span_seconds = 0`.
- Der zugängliche Name des Stapels beginnt weder mit `Duplikate vergleichen:` noch mit
  `Duplikate vergleichen —` — beide Präfixe sind vergeben.
- `cover` ist ein `PhotoOut` und damit eine Funktion des anfragenden Nutzers; die Cache-Auflage der
  Übersicht gilt für beide Eintragsarten.
- `docs/architecture.md` zieht Endpunktblock, Ausschuss- und Vergleichsansicht-Abschnitt im
  Umsetzungs-PR nach.
