# 0532 - Sortierbare und durchsuchbare Ordnerauswahl beim Projektanlegen

**Status:** Implemented ([PR #544](https://github.com/TheRealKoller/photosort/pull/544))
**Erstellt:** 2026-09-27
**Bezug:** [Issue #532](https://github.com/TheRealKoller/photosort/issues/532)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Teststrategie ordnet fünfzehn
Kriterien je Testebene zu und nennt die bewusst geänderten Bestandstests, und die Festlegungen zu
Commit-Folge, Formular-Invariante und Leerzuständen stehen nirgends sonst.

## Ziel

Beim Anlegen eines Projekts wird der OpenCloud-Quellordner über eine Ordnerliste ausgewählt. Die
Reihenfolge dieser Liste ist heute unvorhersehbar; bei vielen gleichartig benannten Unterordnern
(z. B. Kamera-Exporte nach Datum) muss die ganze Ebene abgesucht werden, um einen bekannten Ordner
zu finden. Diese Story macht die Ordnerliste sortierbar — nach Name, Bildanzahl und
Änderungsdatum — und in der aktuell angezeigten Ebene durchsuchbar, damit der richtige Quellordner
schneller gefunden wird.

## User Story

Als Nutzer, der beim Anlegen eines Projekts den OpenCloud-Quellordner auswählt, möchte ich die
Unterordner der aktuellen Ebene sortieren und nach einem Namensteil durchsuchen können, damit ich
den richtigen Ordner auch bei vielen gleichartig benannten Ordnern ohne Absuchen der ganzen Liste
finde.

## Akzeptanzkriterien

**Sortierung**

- [ ] **AK1 – Sortierauswahl sichtbar.** Über der Ordnerliste steht eine Auswahl mit der sichtbaren Beschriftung „Sortierung“. Ihre Optionen stehen in dieser Reihenfolge: „Name A–Z“, „Name Z–A“, „Bildanzahl, meiste zuerst“, „Änderungsdatum, neueste zuerst“. Zugeklappt zeigt sie das wirksame Kriterium. Beim Öffnen der Seite ist „Name A–Z“ gewählt. Auswahl und Suchfeld (AK8) stehen in jedem Zustand der Ebene da (Laden, Fehler, leer, Liste) und sind nie deaktiviert.
- [ ] **AK2 – Name.** „Name A–Z“ ordnet nach dem Ordnernamen ohne Rücksicht auf Groß-/Kleinschreibung und in natürlicher Zahlenfolge (`IMG_9` vor `IMG_10`). Gleichwertige Namen wie `Foo`/`foo` stehen in einer festen Folge, die nicht von der Lieferreihenfolge abhängt. „Name Z–A“ ist die exakte Umkehrung derselben Ebene.
- [ ] **AK3 – Bildanzahl.** „Bildanzahl, meiste zuerst“ ordnet in drei Gruppen:
  1. alle Ordner mit „500+“, untereinander Name A–Z;
  2. die Ordner mit exakter Zahl, absteigend; bei gleicher Zahl gilt Name A–Z, und „0“ zählt als exakte Zahl;
  3. am Ende alle Ordner mit fehlgeschlagener Zählung („?“), Name A–Z.

  Scheitert die ganze Zählanfrage, stehen alle Ordner in Name A–Z.
- [ ] **AK4 – Vorläufige Reihenfolge.** Solange die Zähler der Ebene laden, zeigt „Bildanzahl“ die Liste sofort bedienbar in Name A–Z. Über der Liste steht „Vorläufig nach Name sortiert – die Bildanzahl wird noch gezählt.“ Hinweis und Lade-Spinner verschwinden im selben Schritt, in dem die Liste umsortiert wird. Wird die Liste vorläufig gezeigt, wird sie danach genau einmal umsortiert, ohne Zwischenstand. Kehrt man auf eine Ebene zurück, deren Zähler schon geladen sind, gibt es weder Hinweis noch Umsortieren. Bei den anderen Kriterien erscheint der Hinweis nie.
- [ ] **AK5 – Änderungsdatum.** „Änderungsdatum, neueste zuerst“ stellt den zuletzt geänderten Ordner zuoberst. Verglichen wird der Zeitpunkt, nicht die Zeichenkette. Ordner ohne Datumsangabe stehen am Ende. Bei gleichem Zeitpunkt und unter den Ordnern ohne Datum gilt Name A–Z. Das Datum selbst wird nicht angezeigt.
- [ ] **AK6 – Datum aus dem Backend.** `GET /opencloud/browse` liefert je Unterordner `modified_at`: einen ISO-8601-Zeitpunkt mit Zeitzone aus OpenCloud `getlastmodified`, oder `null`, wenn OpenCloud keinen liefert. Dafür stellt der Aufruf keine zusätzliche Anfrage an OpenCloud.
- [ ] **AK7 – Sortierung bleibt.** Die gewählte Sortierung bleibt bei jedem Ordnerwechsel (Zeile, Brotkrume) erhalten. Beim erneuten Öffnen der Seite gilt wieder „Name A–Z“.

**Suche**

- [ ] **AK8 – Filtern.** Das Feld „Unterordner durchsuchen“ filtert die Liste bei jeder Eingabe auf die Ordner, deren Name den getrimmten Begriff enthält.
  - Groß-/Kleinschreibung ist unerheblich, auch bei Umlauten.
  - Teiltreffer an beliebiger Stelle genügen.
  - Sonderzeichen gelten wörtlich.
  - Ein leerer oder nur aus Leerzeichen bestehender Begriff filtert nicht.
  - Esc leert einen nicht leeren Begriff, der Fokus bleibt im Feld.
- [ ] **AK9 – Nur diese Ebene.** Gefiltert werden nur die direkten Unterordner der angezeigten Ebene. Der Name eines Elternordners im Pfad ist kein Treffer. Ordner tieferer oder anderer Ebenen werden weder eingeblendet noch angefragt; Eingaben ins Suchfeld lösen keine Anfrage aus.
- [ ] **AK10 – Suche und Sortierung zusammen.** Die gefilterte Liste folgt dem gewählten Kriterium. Das gilt auch für die vorläufige Reihenfolge und das einmalige Umsortieren aus AK4.
- [ ] **AK11 – Gefilterte Zeilen voll benutzbar.** Ein gefiltert angezeigter Ordner zeigt denselben Zähler wie ohne Filter und führt beim Anklicken in diesen Ordner.

**Leerer Trefferfall**

- [ ] **AK12 – Kein Treffer.** Hat die Ebene Unterordner, aber keiner passt, erscheint `Kein Unterordner enthält „{Begriff}“ im Namen.` Dabei steht der getrimmte Begriff als reiner Text. Eine Ebene ohne Unterordner zeigt stattdessen „Dieser Ordner hat keine Unterordner.“, auch wenn ein Begriff eingegeben ist. Beide Meldungen erscheinen nie zugleich.
- [ ] **AK13 – Zurücksetzen.** Im Kein-Treffer-Fall bleibt der Begriff im Feld stehen. „Suche zurücksetzen“ leert ihn ohne Ordnerwechsel, setzt den Fokus ins Suchfeld und zeigt wieder die vollständige Liste der Ebene.

**Ordnerwechsel**

- [ ] **AK14 – Begriff wird beim Wechsel geleert.** Jeder Ordnerwechsel (Zeile, Brotkrume) leert den Suchbegriff. Auch nach der Rückkehr auf eine früher durchsuchte Ebene steht kein Begriff im Feld.
- [ ] **AK15 – Auswahl hängt nur an der Navigation.** Tippen, Esc, Enter, „Suche zurücksetzen“ und ein Wechsel der Sortierung ändern den Pfad des Quellordners nicht und senden das Formular nicht ab. „Projekt anlegen“ übernimmt weiterhin den zuletzt angesteuerten Ordner.

## Datenmodell-Bezug

Keine Entität und keine Migration. Einzige Vertragsänderung: `BrowseEntry` (Antwort von
`GET /opencloud/browse`) bekommt das optionale Feld `modified_at` (siehe Architektur).

## Architektur / Umsetzung

Keine neue ADR: Die Änderung ist ein optionales, additives Antwortfeld aus bereits geladenen Daten und dazu reine Frontend-Logik. Es gibt weder neue Technologie noch eine neue Abhängigkeit oder Datenhaltung.

### Backend: Änderungsdatum im Listing

- `GET /opencloud/browse` liefert je Unterordner zusätzlich `modified_at: datetime | None` (`BrowseEntry` in `api/opencloud.py`). Der Wert stammt aus `DavEntry.last_modified`. Diesen Wert fordert der PROPFIND in `opencloud/client.py` schon heute an (`getlastmodified`), und `webdav_xml.py` parst ihn bereits. `client.py` und `webdav_xml.py` bleiben deshalb unverändert.
- `null` bedeutet: OpenCloud hat für den Ordner kein Datum geliefert. Ein nicht lesbares Datum bricht das Listing wie bisher als `400` ab.
- JSON: ISO 8601 mit Zeitzone. Fehlt dem geparsten Datum die Zeitzone (RFC 1123 `-0000`), setzt die Abbildung in `api/opencloud.py` UTC (`replace(tzinfo=UTC)`). Ohne das serialisiert Pydantic keinen Offset, und `Date.parse` liest den Wert als Ortszeit. Backend-Test: Datum mit `-0000` → Antwort mit UTC-Offset. `webdav_xml.py` bleibt unverändert, weil der Worker `last_modified` ebenfalls nutzt.
- Frontend-Typ in `api/types.ts`: `modified_at: string | null`.
- Invariante: `browse` zählt nicht und stellt keine zusätzliche WebDAV-Anfrage. Bildzahlen kommen ausschließlich aus `GET /opencloud/folder-counts` (unverändert).

### Frontend: Sortieren und Filtern als reine Funktion

Neue Datei `frontend/src/utils/folderListing.ts` mit Test daneben. Die Funktion hat keinen React-/DOM-Bezug:

- `type FolderSort = 'name_asc' | 'name_desc' | 'count_desc' | 'modified_desc'`, Voreinstellung `'name_asc'`.
- `arrangeFolders(entries, { sort, searchTerm, counts, countsSettled })` liefert `{ entries, provisional }`. Dabei ist `counts` gleich `FolderCountOut[] | undefined`.
- **Filter vor Sortierung.** Der Suchbegriff wird getrimmt; ein leerer Begriff filtert nicht. Treffer: `name.toLocaleLowerCase('de').includes(begriff.toLocaleLowerCase('de'))`. Geprüft wird nur `name`, nie `path`.
- **Name:** `Intl.Collator('de', { numeric: true, sensitivity: 'base' })`, also natürliche Zahlenfolge (`IMG_9` vor `IMG_10`). Liefert der Collator Gleichstand (etwa `Foo`/`foo`), entscheidet der Codeeinheiten-Vergleich des Namens, damit die Reihenfolge deterministisch bleibt. `name_desc` ist die exakte Umkehrung von `name_asc`.
- **Bildanzahl:** Die Zuordnung läuft über `path`, genau wie `folderCountDisplayFor`. Es gibt drei Gruppen in fester Folge:
  1. `at_limit` — untereinander gleichwertig.
  2. exakte Zahl, absteigend.
  3. Fehler: `error`, kein Eintrag zum Pfad, oder die ganze Anfrage ist gescheitert.

  Innerhalb einer Gruppe und bei gleicher Zahl gilt `name_asc`.
- **Änderungsdatum:** `Date.parse(modified_at)` absteigend. `null` steht am Ende. Bei Gleichstand gilt `name_asc`.
- **Vorläufig:** Ist `sort === 'count_desc'` und `countsSettled === false`, gilt die Reihenfolge `name_asc` mit `provisional: true`. In allen anderen Fällen ist `provisional` gleich `false`.

### „Alle Zähler eingetroffen“

`folder-counts` liefert alle Zähler einer Ebene in **einer** Antwort; einzeln nachtröpfelnde Zeilen gibt es nicht. Eingetroffen heißt: Die Zähler-Query der Ebene lädt nicht mehr. `countsSettled` ist `!counts.isLoading`, also dieselbe Bedingung wie beim Lade-Spinner des Zählers. Hinweis „vorläufig“ und Spinner verschwinden damit gemeinsam.

- Erfolg: endgültige Sortierung nach den gelieferten Werten.
- Scheitert die Anfrage: ebenfalls endgültig. Alle Zeilen fallen in die Fehlergruppe, die Reihenfolge ist also `name_asc`.
- Während automatischer Wiederholungen von React Query bleibt die Liste vorläufig.
- Eine bereits geladene Ebene (`staleTime: Infinity`) ist sofort endgültig und wird nicht umsortiert.
- Die Zeilen tragen weiter `key={entry.path}`. Das einmalige Umsortieren verschiebt Zeilen, statt sie neu zu mounten; der Fokus bleibt erhalten.

### Zustand

- **Sortierung:** `useState<FolderSort>` in `FolderBrowser`. Die Komponente bleibt auf `ProjectCreatePage` über alle Wechsel von `value` hinweg gemountet, deshalb überdauert die Sortierung jeden Ordnerwechsel. Sie wird nicht gespeichert und beginnt beim erneuten Öffnen der Seite wieder mit `name_asc`.
- **Suchbegriff:** gehört zu einer internen Ebenen-Komponente in `FolderBrowser.tsx` mit Suchfeld, Liste und Leer-/Kein-Treffer-Zustand. Sie wird mit `key={value}` gerendert. Jede Änderung von `value` (Zeile, Brotkrume, Elternseite) mountet sie neu und leert den Begriff. Invariante: Ein Begriff taucht auch bei der Rückkehr auf eine früher durchsuchte Ebene nicht wieder auf.
- Weder Sortierung noch Suche rufen `onChange` auf. `value` ändert sich nur durch Navigation.
- `FolderCountIndicator` und der Spinner bleiben in `FolderBrowser.tsx`, weil `designSystem.contract.test.ts` den Spinner-Ausschnitt dort festschreibt. Zähler werden weiter per Pfad aus der ungefilterten Zählerantwort gelesen; der Filter berührt sie nicht.

### Formular-Invariante

`FolderBrowser` sitzt im `<form>` von `ProjectCreatePage`. Enter im Suchfeld darf das Formular **nicht** absenden, sonst würde implizites Absenden das Projekt anlegen. Deshalb setzt `onKeyDown` bei Enter `preventDefault`. Das Suchfeld trägt kein `name`. Auch die Sortierauswahl sendet nicht ab: nativer `<select>` oder Schaltflächen mit `type="button"`.

### Leerzustände

Zwei getrennte Zustände:

- Ebene ohne Unterordner: `browse` liefert eine leere Liste.
- Kein Treffer: `browse` ist nicht leer, der Begriff ist nach dem Trimmen nicht leer, und die gefilterte Liste ist leer.

Wortlaut, Form der Sortierauswahl, Hinweis „vorläufig“ und Zurücksetzen-Bedienelement kommen aus UX/Entwurf.

### Betroffene Dateien

- `backend/src/photosort/api/opencloud.py`: `BrowseEntry.modified_at`, Abbildung aus `entry.last_modified`.
- `backend/tests/test_api_opencloud_browse.py`: Der bestehende Test prüft die exakte JSON-Antwort und muss mitgezogen werden. Neu dazu kommen Datum vorhanden und Datum `null`.
- `frontend/src/api/types.ts`: `BrowseEntry.modified_at`.
- `frontend/src/utils/folderListing.ts` und `folderListing.test.ts`: neu.
- `frontend/src/components/FolderBrowser.tsx` und `FolderBrowser.test.tsx`.
- Alle `BrowseEntry`-Fixtures, z. B. `frontend/src/api/opencloud.test.ts` und `FolderBrowser.test.tsx`: Feld ergänzen (`tsc`).
- `frontend/src/pages/ProjectCreatePage.test.tsx`: Formular-Invariante (AK15).
- `frontend/src/designSystem.contract.test.ts`: `h-11`-Freigabe für das `<select>` (siehe UI/UX).
- `specs/architecture/0004-design-system.md` und Skill `design-system`: Muster „Suche und Sortierung über einer Liste“ (siehe UI/UX).
- `specs/architecture/0003-securitykonzept.md`: Ankerzeile für S1 mit Codestelle und Test (siehe Security).
- `docs/architecture.md`: Vertrag von `browse`, bereits nachgezogen.

Unverändert bleiben `opencloud/client.py`, `opencloud/webdav_xml.py`, `hooks/useOpenCloudFolderCounts.ts`, `hooks/useOpenCloudBrowse.ts` und `pages/ProjectCreatePage.tsx`.

### Reihenfolge

1. Backend-Feld und Test.
2. `types.ts` und Fixtures.
3. `folderListing.ts` und Test (Filter, drei Sortierarten, Gruppen, Gleichstände, vorläufig).
4. `FolderBrowser` mit Zustand, Ebenen-Komponente, Formular-Invariante und Leerzuständen.

## UI/UX

Die Änderung betrifft den Ordner-Browser auf „Neues Projekt anlegen“. Verwendet werden nur vorhandene Bausteine: `Input`, natives `<select>` im Stil des Felds „Referenzkamera“ und `Button`. Es kommt kein neues Token, kein neues Symbol und keine neue Abhängigkeit hinzu.

**Aufbau im Panel** (von oben nach unten): Brotkrumen, Bedienzeile, Hinweiszeile, dann die Liste oder ein Leerzustand. Die Listenzeilen selbst bleiben unverändert (Name und Zähler). Das Änderungsdatum wird nicht angezeigt.

**Bedienzeile:** Sie hat zwei Felder, jedes mit einer sichtbaren Beschriftung über dem Feld (`text-xs font-medium text-text-h`, wie „Name“ auf derselben Seite). Der Abstand zwischen den Feldern ist `gap-3`. Die Zeile steht in jedem Zustand der Ebene, auch beim Laden, bei einem Fehler und in einer leeren Ebene. Sie ist nie deaktiviert, damit sie beim Ordnerwechsel nicht erscheint und wieder verschwindet.

- **Suchfeld** (zuerst, wächst mit):
  - Beschriftung „Unterordner durchsuchen“, Platzhalter „Teil des Ordnernamens“.
  - `Input` mit `type="text"`, ohne `name`, mit `autoComplete="off"`, `autoCorrect="off"`, `autoCapitalize="off"` und `spellCheck={false}`.
  - Die Liste wird bei jedem Tastendruck sofort gefiltert.
  - Enter löst nichts aus.
  - Esc leert einen nicht leeren Begriff; der Fokus bleibt im Feld.
- **Sortierung** (danach):
  - Beschriftung „Sortierung“.
  - Natives `<select>` mit `h-11 w-full sm:w-auto rounded-sm border border-border-control bg-surface px-3 text-sm text-text-h`. Im zugeklappten Zustand zeigt es das wirksame Kriterium.
  - Optionen in dieser Reihenfolge: „Name A–Z“ (Voreinstellung), „Name Z–A“, „Bildanzahl, meiste zuerst“, „Änderungsdatum, neueste zuerst“.

**Hinweiszeile:**

- Solange die Liste vorläufig ist, steht dort: „Vorläufig nach Name sortiert – die Bildanzahl wird noch gezählt.“
- Darstellung `text-sm text-text`, ohne `Alert` und ohne Symbol.
- Der Hinweis verschwindet im selben Render wie die Zähler-Spinner, in dem auch umsortiert wird. Dadurch verschiebt sich die Liste nur einmal.
- Technisch ist die Zeile ein ständig vorhandenes `<p role="status">`. Es trägt nur im vorläufigen Zustand Text und hat ohne Text weder Höhe noch Abstand.
- Angesagt wird nur das Erscheinen des Hinweises. Das Ende der Vorläufigkeit, die Filterung und einzelne Tastendrücke werden nicht angesagt.

**Einmaliges Umsortieren:**

- Die Zeilen springen ohne Animation und ohne Scrollen an ihre neue Stelle.
- Der Fokus bleibt auf demselben Ordner, nicht auf derselben Position. Das stellt `key={entry.path}` sicher.
- Es gibt keinen Eingriff in Fokus oder Scroll-Position.
- Wer genau in diesem Moment daneben tippt, landet schlimmstenfalls in einem Ordner. Das lässt sich über die Brotkrume rückgängig machen.

**Leerzustände** (`text-sm text-text`, kein `Alert`, keine Fehlerfarbe):

- **Ebene ohne Unterordner:** „Dieser Ordner hat keine Unterordner.“ Der Text ersetzt „Keine Unterordner“ und gilt auch, wenn ein Suchbegriff eingegeben ist.
- **Kein Treffer:** `Kein Unterordner enthält „{Begriff}“ im Namen.`
  - `{Begriff}` ist der getrimmte Suchbegriff, gerendert als Textknoten. Lange Begriffe brechen um (`break-words`).
  - Darunter steht `Button variant="outline"` mit der Beschriftung „Suche zurücksetzen“, nach dem Vorbild von „Filter zurücksetzen“ in der Fotoübersicht.
  - Ein Klick leert den Begriff und setzt den Fokus ins Suchfeld. Bis dahin bleibt der Begriff im Feld stehen.

**Schmaler Viewport:**

- Unter `sm` stehen Suchfeld und Sortierung untereinander in voller Breite, das Suchfeld oben.
- Ab `sm` stehen sie nebeneinander: Suchfeld mit `flex-1`, Auswahl mit `w-auto`, unten bündig.
- Hinweis und Meldungen brechen um. Bei 360px scrollt nichts seitlich.

**Zugänglichkeit:**

- Beide Felder sind über `<label htmlFor>` beschriftet. Die Rollen ergeben sich aus den Elementen: `textbox`, `combobox`, `button`.
- Innerhalb des Formulars gibt es keine `search`-Landmarke.
- Die Hinweiszeile ist die einzige neue Live-Region.
- Beide Felder sind sichtbar 44px hoch (Kategorie „Eingabefelder“). „Suche zurücksetzen“ nutzt das Standardmaß des `Button` samt `tap-target`.

**Vertragstest:** Das `h-11` am `<select>` in `FolderBrowser.tsx` ist eine neue Fundstelle für die `h-11`-Freigabeliste in `designSystem.contract.test.ts`. Kategorie und Begründung sind dieselben wie beim Feld „Referenzkamera“.

**Design-System:** In `specs/architecture/0004-design-system.md` unter „Wiederkehrende Muster“ und gleichlautend im Skill `design-system` kommt ein Eintrag „Suche und Sortierung über einer Liste“ hinzu. Er fasst zusammen:

- Sortierung als natives `<select>` mit sichtbarer Beschriftung.
- Filterung im Client bei jedem Tastendruck, Esc leert.
- Der Kein-Treffer-Zustand nennt den Begriff und bietet „Suche zurücksetzen“ an; er ist vom Leerzustand der Ebene getrennt.
- Eine noch nicht endgültige Reihenfolge wird als Status-Zeile ausgewiesen und einmal umsortiert, ohne Eingriff in Fokus oder Scroll-Position.

## Security

Sicherheitsrelevant ist nur ein Punkt: Der Suchbegriff ist die erste freie Nutzereingabe, die die Oberfläche als Text wieder anzeigt. Es gibt keinen neuen Endpunkt, keine Änderung an Auth und keine Änderung daran, was die beiden Nutzer jeweils sehen. Gefiltert wird nur im Browser.

**S1 — Der Suchbegriff bleibt lokaler Text.**
- **Was gilt:** Der Begriff stammt nur aus dem Suchfeld und liegt nur im Zustand der Ebenen-Komponente. Er wird nie aus der URL oder einem Query-Parameter übernommen. In der Kein-Treffer-Meldung erscheint er nur als React-Textknoten: kein `dangerouslySetInnerHTML`, keine HTML-String-Prop. Falls Teiltreffer im Ordnernamen hervorgehoben werden, wird der Name in Textknoten zerlegt, statt einen Markup-String zu bauen.
- **Wofür:** `frontend/src/components/FolderBrowser.tsx` (Suchfeld, Kein-Treffer-Zustand). Projektweit gilt dasselbe im Sicherheitskonzept unter „Frontend“.
- **Bei Verletzung:** Ein präparierter Link bringt fremden Text in die Meldung. Wird er als Text gerendert, dient die Meldung zur Täuschung („Sitzung abgelaufen, bitte unter … anmelden“). Wird er als Markup gerendert, liest ein eingeschleustes Skript das JWT aus `localStorage`. Das Token ist 30 Tage gültig und lässt sich nicht widerrufen.
- **Nachweis:** Ein Test in `FolderBrowser.test.tsx` gibt einen Begriff mit Markup ein, etwa `<img src=x onerror=alert(1)>`. Erwartet: Die Meldung zeigt ihn wörtlich, und im DOM entsteht kein `img`. Mit der Umsetzung bekommt die Ankerliste in `specs/architecture/0003-securitykonzept.md` eine Zeile mit dieser Codestelle und diesem Test.

Daraus folgen keine Auflagen:
- `modified_at` bringt keinen neuen fremden Text. Das Feld ist ein typisiertes `datetime | None`, und ein unlesbares Datum endet über `client.py::list_folder` in der festen 400-Meldung, die den Rohwert nicht enthält. Angezeigt wird das Datum nicht.
- Dass Enter im Suchfeld das Formular nicht absendet, ist eine Frage der Korrektheit und durch die Formular-Regel im Architekturteil abgedeckt. `POST /projects` legt nach der bestehenden Existenzprüfung nur eine Projektzeile an; es startet keinen Lauf, und keine Daten verlassen das System.
- Der Begriff erreicht weder `path` noch das Backend. `/opencloud/browse?path=` bleibt die einzige Pfad-Eingabe und wird weiter durch `_join` geschützt.

## Teststrategie

Jede Zusage wird auf der niedrigsten Ebene geprüft, die sie widerlegen kann:

- Sortier- und Filterregeln an der reinen Funktion `arrangeFolders`,
- Verdrahtung, Zustände und Fokus an `FolderBrowser`,
- die Formular-Invariante an `ProjectCreatePage`,
- das neue Feld am Endpunkt.

Die Muster für den Commit-Aufzeichner, Enter im Formular und den Listenschlüssel stehen im Testkonzept (Sektion zu Spec 0532).

### Ebene je Akzeptanzkriterium

| AK | pytest `test_api_opencloud_browse.py` | Unit `utils/folderListing.test.ts` | Komponente `FolderBrowser.test.tsx` | Seite `ProjectCreatePage.test.tsx` |
|---|---|---|---|---|
| AK1 | – | – | Beschriftung und Optionen in Reihenfolge (einzige literale Zusicherung der Optionstexte), `toHaveDisplayValue('Name A–Z')`. Suchfeld und Auswahl vorhanden und aktiv beim Laden, im Fehlerfall, leer und mit Liste (parametrisiert) | – |
| AK2 | – | natürliche Zahlenfolge; Groß/klein; Gleichstand `Foo`/`foo` fest; umgestellte Eingabe ergibt dieselbe Ausgabe; `name_desc` ist die Umkehrung von `name_asc` | Verdrahtung: eine Fixture, in der die vier Kriterien paarweise verschiedene Reihenfolgen ergeben; je Option die erwartete Reihenfolge | – |
| AK3 | – | drei Gruppen; `0` vor Fehler; fehlender Eintrag zählt als Fehler; ganze Anfrage gescheitert (`counts` undefined, eingetroffen) ergibt `name_asc`; Gleichstände `name_asc` | über die Verdrahtungsfixture | – |
| AK4 | – | `provisional` über das Kreuzprodukt Kriterium × eingetroffen: nur bei `count_desc` und nicht eingetroffen, dann in Reihenfolge `name_asc` | Commit-Aufzeichner; Hinweis nur bei „Bildanzahl“; Rückkehr auf geladene Ebene; Fokus; gescheiterte Zählanfrage beendet die Vorläufigkeit | – |
| AK5 | – | neueste zuerst; `null` am Ende; Gleichstände `name_asc`; zwei Zeitpunkte mit verschiedenem Zonenversatz (Vergleich nach Zeit statt nach Zeichenkette) | über die Verdrahtungsfixture | – |
| AK6 | exaktes JSON mit Datum (`"2023-08-28T20:45:10Z"` aus einem UTC-`datetime`) und mit `null`; `list_folder` genau einmal aufgerufen | – | – | – |
| AK7 | – | – | „Bildanzahl“ wählen, Ordner wechseln: Die Auswahl zeigt weiter „Bildanzahl“, und die neue Ebene ist danach sortiert | – |
| AK8 | – | Teiltreffer in der Mitte; Groß/klein samt Umlaut; Trimmen; nur Leerzeichen filtert nicht; `.` und `(` gelten wörtlich | Eingabe filtert sofort; Esc leert, der Fokus bleibt | – |
| AK9 | – | Ein Begriff gleich dem Elternordner trifft keinen Unterordner (geprüft wird nur `name`, nie `path`) | Tippen löst keinen weiteren Aufruf von `browseFolder` oder `fetchFolderCounts` aus | – |
| AK10 | – | Filter mit jedem Kriterium; Filter während der vorläufigen Phase | – | – |
| AK11 | – | – | gefilterte Zeile zeigt ihren Zähler; Klick führt zu `onChange(path)` | – |
| AK12 | – | – | Unterscheidung in beide Richtungen: Liste mit Begriff ohne Treffer, leere Ebene mit Begriff. Wörtlicher Text mit getrimmtem Begriff; ein Begriff mit Markup bleibt Text | – |
| AK13 | – | – | Begriff bleibt stehen. „Suche zurücksetzen“: Feld leer, Fokus im Feld, alle Zeilen wieder da (Filter ein → aus) | – |
| AK14 | – | – | Testrahmen mit eigenem `value`-Zustand: Begriff eingeben, Zeile anklicken → Feld leer; über die Brotkrume zurück → Feld weiter leer | – |
| AK15 | – | – | Tippen, Esc, Zurücksetzen und Sortierwechsel rufen nie `onChange` | Name ausgefüllt, Vorbedingung „Projekt anlegen“ aktiv. In `Sub` navigieren, Begriff + Enter → kein Aufruf von `createProject`; danach Absenden → `opencloud_path: 'Sub'` |

### Pflichtfälle mit eigenem Gewicht

- **AK4, Commit-Folge:**
  - Ablauf: Ebene A laden und „Bildanzahl“ wählen. Dann auf Ebene B wechseln, deren Zählantwort über ein steuerbares Promise aussteht. Die Fixture ist so gewählt, dass die endgültige Reihenfolge von `name_asc` abweicht.
  - Aufgezeichnet wird ab dem Wechsel. Für jeden Commit mit Zeilen gilt: Hinweis sichtbar ⇔ Ladeanzeige sichtbar ⇔ Reihenfolge `name_asc`.
  - Die Folge der verschiedenen Reihenfolgen ist exakt `[name_asc, endgültig]`.
  - Bei der Rückkehr auf A ist schon der erste Commit mit Zeilen endgültig und ohne Hinweis.
  - Gegenprobe beim Einführen: Wird die Reihenfolge per Effekt nachgezogen, muss der Fall rot werden.
- **AK4, Fokus:** In der vorläufigen Phase eine Zeile fokussieren und dann die Zähler auflösen. Das fokussierte Element trägt danach denselben Namen wie vorher. Das fängt einen `key` über den Index.
- **AK15, Enter:** Ohne die Vorbedingung „Absende-Button aktiv“ besteht der Fall leer. Gegenprobe: Ohne `preventDefault` ruft `user-event` `createProject` auf.
- **Unit-Fixtures:** literale Tabellen, die Eingabe ist bewusst nicht vorsortiert. Jede Gleichstandsregel wird mit Namen geprüft, deren Eingabereihenfolge der erwarteten widerspricht.

### Bestandstests, die bewusst geändert werden

- `backend/tests/test_api_opencloud_browse.py::test_browse_returns_only_folders`: Das erwartete JSON bekommt `"modified_at": None`, der Vergleich bleibt exakt.
- `FolderBrowser.test.tsx`, Fall „shows a hint instead of an empty area when the folder has no subfolders“: geht im Unterscheidungsfall zu AK12 auf, mit neuem Wortlaut und exakter Prüfung statt Regex.
- `designSystem.contract.test.ts`: neuer Eintrag in `TALL_CONTROL_ALLOWLIST` für das `h-11` des `<select>` in `FolderBrowser.tsx`. Kategorie Eingabefeld, Begründung wie beim Auswahlfeld der Referenzkamera. Der `rounded-full`-Eintrag des Spinners bleibt unverändert und muss weiter treffen.
- `BrowseEntry`-Literale in `api/opencloud.test.ts`, `FolderBrowser.test.tsx`, `hooks/useOpenCloudBrowse.test.tsx` und `pages/ProjectCreatePage.test.tsx`: `modified_at: null` ergänzt, reiner Typnachzug.

Jede andere geänderte Erwartung ist ein Review-Befund, vor allem in den Zählertests von `FolderBrowser.test.tsx` und in `ProjectCreatePage.test.tsx`.

### E2E

Kein neuer Spec und keine Änderung an `e2e/`.

- Der Prüfstack läuft ohne OpenCloud, `/opencloud/browse` antwortet dort mit `400` (`e2e/tests/empty-and-error-states.spec.ts`). Eine Liste, die man sortieren oder durchsuchen könnte, entsteht dort nie.
- Alle Kriterien sind Logik-, DOM- und Fokusfragen, die jsdom widerlegen kann. Das Aufnahmekriterium für E2E ist nicht erfüllt.
- Die einzige Geometriezusage der UX-Festlegung ist: bei 360 px kein seitliches Scrollen. Diese misst `no-horizontal-scroll.spec.ts` über die Route „Neues Projekt“ bereits mit, weil die Bedienzeile laut AK1 auch im Fehlerzustand steht. Diese Voraussetzung sichert der AK1-Fall auf Komponentenebene.

### Manuell vor Merge

Über das Demo-Overlay `docker-compose.demo.yml` mit echter OpenCloud:

- OpenCloud liefert `getlastmodified` für Ordner tatsächlich. Sonst stünden alle Ordner ohne Datum da, und AK5 hätte keine Wirkung. Die Fakes können das nicht belegen.
- Die Kein-Treffer-Meldung mit langem Begriff und die Hinweiszeile brechen bei 360 px um.

Nicht automatisiert:

- die Ansage der Statuszeile durch einen Screenreader; geprüft werden nur `role="status"` und ihr Text;
- das Verhalten während der automatischen Wiederholungen von React Query. Das folgt aus der Semantik von `isLoading`, und die Tests laufen mit `retry: false`.

## Entscheidungen

- Alle vier Konsultationen sind gelaufen (`architect`, `ux-ui-designer`, `test-engineer`,
  `security-engineer`); keine wurde übersprungen.
- Keine neue ADR: `modified_at` ist ein optionales, additives Antwortfeld aus derselben
  PROPFIND-Antwort; keine neue Technologie, Abhängigkeit oder Datenhaltung.
- Name sortiert natürlich (`IMG_9` vor `IMG_10`) und ohne Rücksicht auf Groß-/Kleinschreibung;
  Gleichstände entscheidet der Codeeinheiten-Vergleich, damit die Folge nicht von der
  Lieferreihenfolge abhängt.
- Bei jedem Gleichstand (gleiche Zahl, Fehlergruppe, gleiches oder fehlendes Datum) gilt Name A–Z.
- Die vorläufige Reihenfolge bei „Bildanzahl“ ist Name A–Z; scheitert die ganze Zählanfrage, ist
  die Sortierung endgültig und alle Ordner stehen in der Fehlergruppe.
- Der Suchbegriff wird getrimmt; Umlaute werden nicht mit dem Grundbuchstaben gleichgesetzt.
- Die Sortierung überdauert Ordnerwechsel, wird aber nicht gespeichert.
- Das Änderungsdatum wird in den Zeilen nicht angezeigt; die Story verlangt es nicht.
- Kein E2E-Fall: Der E2E-Prüfstack hat kein OpenCloud, alle Kriterien sind in jsdom widerlegbar.

## Offene Fragen

- Ob OpenCloud für Ordner ein `getlastmodified` liefert und ob es Änderungen im Unterbaum nach oben
  weiterreicht, ist nicht am Bestand belegt. Der Ansatz transportiert, was OpenCloud meldet; die
  manuelle Prüfung vor dem Merge (Teststrategie) klärt, ob AK5 Wirkung hat.

## Out of Scope

- Anzeige des Änderungsdatums in der Ordnerliste.
- Suche über mehrere Ebenen oder rekursive Treffer.
- Gespeicherte Sortier-Voreinstellung über das Schließen der Seite hinaus.
- Änderungen an `GET /opencloud/folder-counts` oder an der Zählobergrenze.
