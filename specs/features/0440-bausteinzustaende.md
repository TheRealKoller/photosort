# 0440 - Alle Bausteinzustände auf einen Blick

**Status:** Implemented
**Erstellt:** 2026-09-12
**Bezug:** [GitHub-Issue #440](https://github.com/TheRealKoller/photosort/issues/440),
[PR #443](https://github.com/TheRealKoller/photosort/pull/443)

**Umfang:** über dem Richtwert von rund 200 Zeilen, und zwar aus zwei Gründen, die beide in der
Bauart dieser Story liegen. Die Rastertabelle je Baustein **ist** die Umsetzungsvorlage — sie
ersetzt die Soll-Struktur-Datei, die ADR
[`0088`](../decisions/0088-bausteinregister-handarbeit-ohne-soll-struktur-seite-umbenannt.md)
Abschnitt 2 bewusst nicht anlegt; ohne sie wäre das Register nach einem Instanzverlust nicht
wieder aufbaubar. Und die Wächtertabelle samt Sichtprüfungsliste tritt an die Stelle
automatisierter Deckung, die es hier nicht geben kann: Kein Test dieses Repositoriums kann die
Design-Datei lesen. Dazu kommen die beim Bau gemessenen Eigenheiten der Plugin-API — sie stehen
hier, weil das Register nach einem Instanzverlust allein aus dieser Spec wieder entsteht.

## Ziel

Die Design-Datei „PhotoSort — Dark Utility Register" kennt zwölf Bausteine mit ihren Ausprägungen
und Zuständen, aber keine Fläche, auf der sie nebeneinander abzulesen wären. Was es gibt, ist die
Standardseite „Page 1": ein loser Fluss aus Variantenbrettern und Symbolen ohne Raster, ohne
Überschriften, ohne Achsenbeschriftung. Die Zustandsregeln des Design-Systems — gedrückt ist
Pflicht, deaktiviert sieht bei jeder Ausprägung gleich aus, ein Vorschlag ist umrandet statt
gefüllt — stehen ausschließlich als Prosa in
[`specs/architecture/0004-design-system.md`](../architecture/0004-design-system.md), an keiner
Stelle sichtbar nebeneinander.

Das kostet bereits: Ein Viertel der Schaltflächen-Varianten stand ohne Flächenbindung weiß in der
dunklen Datei und verfehlte den Kontrast. Es gab keine Fläche, auf der so etwas ins Auge springt.

Die Seite dient zwei Zwecken, nicht dreien:

- **Nachschlagen:** Wie sieht dieser Zustand aus? Welche Ausprägungen gibt es überhaupt?
- **Vollständigkeit belegen:** Jeder Zustand, den die Anwendung kennt, ist im Design-System
  definiert — und wo das nicht stimmt, fällt es beim Hinsehen auf.

## User Story

Als Gestalter und Prüfer des Design-Systems möchte ich alle Bausteine mit ihren Ausprägungen und
Zuständen auf einer benannten Seite in beschrifteten Rastern sehen, damit ich einen Zustand
nachschlagen kann, ohne die Dokumentation zu lesen, und eine Lücke oder einen Fehler im
Design-System beim Hinsehen bemerke statt erst, wenn jemand gezielt danach sucht.

## Akzeptanzkriterien

- [ ] Die Seite trägt den Namen „Bausteine — Zustände". Der Name „page 1" kommt in der
      Design-Datei nicht mehr vor.
- [ ] Je Baustein steht ein Raster: **Spalten = Ausprägungen, Zeilen = Zustände**, bei einer
      Größe. Jede Ausprägung und jeder Zustand, den das Design-System führt, kommt darin
      mindestens einmal vor — aber nicht jede denkbare Kombination. Der bauende Aufruf berichtet
      je Raster die geschalteten Werte gegen die Achsen aus `components.json`; das ist ein
      Selbstbericht, keine unabhängige Rücklesung.
- [ ] Wo ein Baustein zusätzlich eine Größenachse hat, steht sie als eigene beschriftete Reihe
      daneben, nicht als dritte Rasterdimension.
- [ ] Bausteine mit abweichenden Zuständen behalten ihre eigenen Zeilen — das Eingabefeld
      „fokussiert"/„fehlerhaft" statt „überfahren", das Auswahlkästchen „gesetzt"/„nicht gesetzt".
      Ein einheitliches Zeilenschema wird nicht erzwungen.
- [ ] Alle Felder eines Rasters sind gleich groß und gleich ausgerichtet, sodass der Vergleich
      zweier Felder nur den Unterschied zeigt, den er zeigen soll. Nachgewiesen wird das
      gemessen: Breite und Höhe aller Zellbretter eines Rasters sind paarweise gleich.
- [ ] Zeilen und Spalten sind beschriftet. Ohne Vorwissen ist ablesbar, welchen Zustand und
      welche Ausprägung ein Feld zeigt.
- [ ] Die Bausteine erscheinen so, wie sie in der Anwendung tatsächlich aussehen — mit Fläche,
      Rahmen, Schrift und Farbe des jeweiligen Zustands, nicht als leere Rahmen oder
      Beschriftungen auf Weiß, weil jede Zelle eine Bibliotheks-Instanz enthält, nie eine
      nachgezeichnete Form. **Nur so weit erfüllbar, wie die Bibliothek reicht** — siehe
      „Was die Bibliothek nicht hergibt": Ein Baustein ist dort eine Fläche mit einer
      Beschriftung, kein Abbild des Bedienelements. Das Register zeigt das unverfälscht und
      führt die Differenz als Lücke, statt sie nachzuzeichnen.
- [ ] Die zwölf Symbole stehen als eigener beschrifteter Block auf derselben Seite.
- [ ] **Der vorhandene Variantenbestand der Bibliothek bleibt vollständig erhalten.** Die Seite
      ordnet und beschriftet; sie entfernt nichts. Das kuratierte Raster steht neben dem Bestand
      auf derselben Seite, nicht an seiner Stelle — ein Ort, zwei Zonen.
- [ ] Benannte Lücken stehen sichtbar auf der Seite: Elemente, welche die Anwendung verwendet,
      die das Design-System aber noch nicht als Baustein führt — heute die aufklappenden
      Menü- und Infoflächen sowie die Schriftmuster. Diese Story schließt sie nicht; sie macht
      sie sichtbar.
- [ ] Die Seite muss einen Wiederaufbau der Design-Datei nicht überstehen. Sie entsteht und
      bleibt Handarbeit; es wird nichts gebaut, das sie erzeugt.

## Datenmodell-Bezug

Nicht relevant. Es entsteht keine Entität, keine Migration und keine Änderung an
[`docs/architecture.md`](../../docs/architecture.md) — die Arbeit liegt in der Penpot-Datei, das
Repository sieht davon nur Spec, ADR und zwei Doku-Stellen.

## Architektur / Umsetzung

Entscheidung und Begründung: ADR
[`0088`](../decisions/0088-bausteinregister-handarbeit-ohne-soll-struktur-seite-umbenannt.md).
Kurzfassung: Die Seite ist eine **dritte Seitenklasse** („Register") neben Ansichtsseite (ADR
0082) und Arbeitsseite (ADR 0073). Sie entsteht von Hand über `penpot-design` Schritt 3 in der
Hauptsession — kein `seed-register.js`, keine fünfte Zeile in der Schritttabelle, kein Eintrag in
der Laufregel-Zuordnung. Eine eigene Soll-Struktur-Datei entsteht nicht: *Was* zu zeigen ist,
steht abzählbar in `design/penpot/components.json` und `icons.json`; *wie* es angeordnet ist,
steht in der Rastertabelle unten.

### Repository-Änderungen (abschließend)

| Datei | Änderung |
|---|---|
| `specs/features/0440-bausteinzustaende.md` | diese Spec |
| `specs/decisions/0088-...md` | neue ADR |
| `.claude/skills/penpot-design/SKILL.md` | ein Block „Das Ablagemuster für das Register" neben dem für Ansichten |
| `design/penpot/README.md` | ein Absatz im `views.json`-Abschnitt (das Register steht bewusst nicht darin) und ein Unterabschnitt mit den drei beim Bau gemessenen API-Befunden |
| `specs/architecture/0004-design-system.md` | zwei Punkte unter „Bekannte Lücken": die Bausteine sind Token-Träger statt Abbilder, und das Register wird von Hand nachgezogen |
| `specs/architecture/0002-testkonzept.md` | zwei Punkte unter „Bekannte Lücken" und ein Satz zum Suchraum der Wächter |

**Unverändert, und das ist eine Zusicherung, kein Versäumnis:** `frontend/penpot/payload.test.ts`
(keine Kardinalität, keine zeilengebundene Freigabe), `design/penpot/verify.js`,
`components.json`, `views.json`, jedes `seed-*.js`, `fix-flaechen.js`, `docs/**`.

Damit liegt der Diff in `specs/**`, `design/penpot/**` und `.claude/**`. **Ausgeliefert wird auf
dem normalen Story-Weg, nicht über `ship-entwurf`:** Dessen Anker feuert nicht (kein Rundenlauf),
und `.claude/**` liegt außerhalb seiner Zulassungsmenge — er hielte an. Der Pull Request ändert
ausschließlich Doku-/Spec-Dateien, ein Copilot-Review entfällt deshalb.

### Rasterauswahl je Baustein

Eine Größe für alle Raster; die Größenachse steht nur bei der Schaltfläche zusätzlich als eigene
Reihe. „Mindestens einmal, nicht jede Kombination" heißt: Die dritte Achse wird nicht
einmultipliziert, und eine Kombination ohne Entsprechung im Produkt bleibt als **beschriftete
Leerzelle** stehen statt gefüllt zu werden — sie ist der sichtbare Beleg einer Regel.

| Baustein | Spalten | Zeilen | die eine Größe | Anmerkung |
|---|---|---|---|---|
| Schaltfläche | `auspraegung` (6) | `zustand` (5) | `groesse=default` | 30 Zellen; dazu **eine eigene beschriftete Reihe** `groesse` (default · sm · icon) bei `auspraegung=default`, `zustand=normal` |
| Eingabefeld | eine Spalte („Eingabefeld") | `zustand` (5: normal · fokussiert · fehlerhaft · fokussiert-fehlerhaft · disabled) | — | eigene Zustandsnamen, kein „überfahren" |
| Kennzeichen | Farbrolle (5: favorite · album-worthy · rejected · accent · neutral) | Füllung (2: solid · suggested) | — | `neutral × suggested` bleibt beschriftete Leerzelle (im Produkt ignoriert der neutrale Ton die Füllung) — macht „Füllung = entschieden, Umrandung = Vorschlag" ablesbar |
| Karte | `bewertung` (4) | `vorschlag` (2: ohne · mit) | — | in der Zeile `mit` ist nur `unbewertet` belegt; die drei anderen Zellen beschriftet leer („eine eigene Bewertung hat Vorrang", `RatingBadge.tsx`) |
| Hinweis | `auspraegung` (7) | eine Zeile | — | zwei Spaltengruppen-Überschriften: „Hinweisfläche" (3) und „Statuskennzeichen" (4) — der Achsenschnitt wird dadurch sichtbar |
| Auswahlkästchen | eine Spalte | `zustand` (3: nicht gesetzt · gesetzt · deaktiviert) | — | eigene Zustandsnamen |
| Schalter | eine Spalte | `zustand` (3) | — | neben dem Auswahlkästchen platziert, aber eigenes Raster |
| Fortschrittsanzeige | eine Spalte | `zustand` (2: determiniert · indeterminate) | — | `indeterminate` ruhend, als Bewegungslücke ausgewiesen |
| Dialog | `abbrechen` (2: aktiv · cancelDisabled) | `zustand` (2: offen · geschlossen) | — | Zeile `geschlossen` ist **eine** beschriftete Zelle („zeigt nichts") statt zwei gleicher |
| Platzhalter | `auspraegung` (2: zeile · kachel) | eine Zeile | — | ruhend, Puls als Bewegungslücke |
| Kategorie-Chip | `kategorie` (13) | eine Zeile | — | eine Reihe; reicht die Breite nicht, wird umgebrochen und die Fortsetzungszeile als solche beschriftet (nie als Zustand lesbar) |
| Schrittmarke | `auspraegung` (4) | `zustand` (3: normal · hover · active) | — | 12 Zellen |

Ein Baustein ohne Ausprägungsachse bekommt genau **eine** Spalte (mit dem Bausteinnamen
beschriftet), einer ohne Zustandsachse genau **eine** Zeile — die Leserichtung „Spalten =
Ausprägungen, Zeilen = Zustände" bleibt dadurch über alle zwölf Raster dieselbe.

### Maße und Lage — damit der Wiederaufbau maßhaltig ist

Diese Werte gehören in die Spec, weil das Register nach einem Instanzverlust allein aus ihr
entsteht: Ohne sie wäre der zugesagte Wiederaufbau zwar inhaltlich vollständig, aber nicht
maßgleich. Beschriftungsspalte 180, Kopfhöhe 56. Die Zelle ist 12 schmaler und 12 niedriger als das
Rasterfeld und besteht aus zwei Rechtecken je halber Zellbreite; die Instanz sitzt bei einem
Viertel der Zellbreite und 10 unter der Zellkante.

**Ein Zeilenlabel muss in die 180 breite Beschriftungsspalte passen** — in `text.sm` sind das
rund 23 Zeichen. Ein längeres Label ragt in die erste Zellspalte und steht dann im Baustein;
gekürzt wird die technische Klammer, nicht die deutsche Bezeichnung, denn die trägt die
Ablesbarkeit. Ein Leerzellen-Vermerk steht **in** seiner Zelle (feste Breite 170, umbrechend),
nicht darunter: Unter der letzten Zeile eines Rasters ragt er ins nächste.

| Raster | Rasterfeld (Breite × Höhe) | Spalte, Ursprung (x, y) |
|---|---|---|
| Schaltfläche | 200 × 64 | Bedienelemente, (0, −2400) |
| Schaltfläche — Größen | 200 × 64 | Bedienelemente, (0, −1990) |
| Eingabefeld | 260 × 64 | Bedienelemente, (0, −1830) |
| Auswahlkästchen | 260 × 60 | Bedienelemente, (0, −1420) |
| Schalter | 260 × 60 | Bedienelemente, (0, −1180) |
| Hinweis | 260 × 96 | Anzeigen, (2600, −2400) |
| Kennzeichen | 200 × 60 | Anzeigen, (2600, −2200) |
| Fortschrittsanzeige | 260 × 60 | Anzeigen, (2600, −2020) |
| Kategorie-Chip | 200 × 60 | Anzeigen, (2600, −1810) |
| Karte | 240 × 76 | Behälter und Verlauf, (5600, −2400) |
| Dialog | 300 × 96 | Behälter und Verlauf, (5600, −2180) |
| Schrittmarke | 200 × 64 | Behälter und Verlauf, (5600, −1900) |
| Platzhalter | 240 × 76 | Behälter und Verlauf, (5600, −1620) |

Die Befundzeilen stehen an x = 0 bei y = −2020 (Zustände) und y = −1866 (Größen). Symbolblock an
x = 0: Überschrift bei y = −900, darunter zwölf Zellen aus zwei 56 × 56-Feldern im Abstand 130,
der Symbolname unter der Zelle. Lücken-Block bei (0, −700), 2400 × 320. Seitentitel bei
(0, −2620), Zonenüberschrift bei (0, −2540), Gruppenüberschriften bei y = −2480. Die
Bestandsüberschrift steht bei (0, 420) und bleibt außerhalb des Rahmens.

**Alles Übrige liegt in einem Rahmen-Board `Bausteine — Zustände: Register`** bei (−60, −2680),
6760 × 2360, Fläche an `color.bg` gebunden. Es hält die Register-Zone im Ebenenbaum zusammen,
ist die Form, auf die ein Gesamtexport geht, und trägt **keine** Plugin-Daten. Die gebundene
Fläche ist kein Schmuck: Ohne sie exportiert der Rahmen auf transparentem Grund, der Export
zeigt weiß statt des tatsächlichen Seitengrunds, und die hellen Prüffelder verschmelzen mit dem
Nichts — die Sichtprüfung beurteilte dann einen Untergrund, den die Seite nicht hat.

**Symbolblock:** die zwölf Symbole aus `icons.json` als eigener beschrifteter Block, je Symbol
sein Name darunter; Strichfarbe kommt aus der Bibliotheksinstanz (`color.text-h`).

**Block „Benannte Lücken — was die Bibliothek nicht zeigt":** eine Textliste auf
`color.surface`, nicht als nachgezeichneter Baustein, mit sieben Einträgen. Die ersten drei sind
beim Bau gemessen (siehe „Was die Bibliothek nicht hergibt") und in `color.text` hervorgehoben:
kein Baustein ist ausmodelliert; die Zustände einer Schaltfläche sind nur teilweise
unterschieden; die Größenachse trägt keine eigenen Maße. Die vier weiteren in
`color.text-muted`: die aufklappenden Menü- und Infoflächen
(`frontend/src/components/ui/popover.tsx` samt Verwendungen), die Schriftmuster (sieben
`text.*`-Verbundtokens ohne Baustein), **Bewegung** (Puls, `indeterminate`, Spinner) und
**Behälter** (Karte und Dialog sind in der Bibliothek Blätter). Die Story schließt keine davon.

### Aufbau: Zellen, Beschriftung, Layout

- **Jede Zelle sind zwei Rechtecke fester, je Raster gleicher Größe** (`color.bg` und
  `color.text-h`), darüber **eine Bibliotheks-Instanz** (`komponente.instance()`), auf die
  Kombination geschaltet mit `switchVariant(position, wert)` — die **Position** der Achse, nicht
  ihr Name (`Object.keys(komponente.variantProps)`). Die festen Rechtecke tragen „alle Felder
  gleich groß und gleich ausgerichtet"; die Instanz selbst ist je Kombination unterschiedlich
  breit und könnte das nicht leisten.
- **Die Zelle ist kein Board und die Instanz nicht ihr Kind.** Zwei Gründe, beide gemessen:
  Penpot blendet über **jedem** Board im Canvas dessen Namen ein — bei über hundert Zellen
  überlagert das die Spaltenüberschriften und macht das Raster unlesbar. Und ein Board
  **beschneidet** seine Kinder, wodurch eine zu breite Instanz als Ausschnitt einer Farbfläche
  erscheint statt als Baustein. Gruppieren löst das nicht: `penpot.group()` friert im selben
  Aufruf die noch nicht nachgerechnete Instanzbreite ein.
- **Jedes Board bindet eine Fläche oder wird ausdrücklich geleert** (`fills = []`) — nie
  weggelassen: Ein neu erzeugtes Board ist deckend **weiß**. Das betrifft hier den Rahmen
  (geleert) und den Lücken-Block (`color.surface`).
- **Kein Flex-Layout für die Raster.** Positionen werden im Aufruf ausgerechnet und gesetzt: Flex
  rechnet nur bei wachsender Höhe, rechnet nicht nach, Kind-Sizing sitzt auf `layoutChild`, und
  ein Brett als Flex-Kind wächst nie in der Höhe. Alle vier scheitern still.
- **Bauen und Messen gehören in getrennte `execute_code`-Aufrufe** — im selben Aufruf gelesen ist
  eine Bretthöhe noch `1` und alle Kinder liegen auf `0,0`.
- **Beschriftung** über Tokens; die fünf Ebenen stehen in der Tabelle im Abschnitt „UI/UX". Ein
  leerer Text ist ungültig — eine unerwünschte Beschriftung wird ausgeblendet, nicht geleert.
  `fontFamily` ist Singular.
- **Kein Objekt des Registers trägt die Plugin-Daten `schluessel`, `ansicht` oder `breite`.**
  Andernfalls zählte `verify.js` es als Baustein bzw. Ansichtsbrett und der Abgleich würde rot,
  ohne dass etwas fehlt.

### Reihenfolge der Umsetzung

1. **Ungemessenes klären statt annehmen** (`penpot_api_info`): ob `page.name` schreibbar ist und
   ob `komponente.instance()` Plugin-Daten mitkopiert. Ergibt sich, dass die Umbenennung über die
   API nicht geht, wird das **gemeldet, nicht umgangen** — Daniel benennt die Seite im Browser um.
2. **Messen, bevor geschrieben wird:** welche Seite die Varianten-Behälter mit `schluessel` trägt
   (am Inhalt, nie am Namen), deren Ausdehnung, die Seitenliste, und `verify.js` als
   Ausgangsstand.
3. **Umbenennen statt neu anlegen** (`Bausteine — Zustände`), Prüfung in einem eigenen Aufruf.
   Danach die Seite aktiv schalten — Penpot lässt nur die **aktive** Seite beschreiben; `openPage`
   und Prüfung gehören in getrennte Aufrufe.
4. **Seitengrund** auf `color.bg` setzen, den Wert aus dem Token **gelesen**, nie getippt (eine
   Seite ist keine Form, `applyToken` greift dort nicht — als Lücke zu führen).
5. **Zwei Zonen anlegen:** Überschrift über dem Bestand („Bestand — Variantenbretter der
   Bibliothek") und über dem freien Bereich daneben („Register — kuratierte Raster"). Am Bestand
   wird nichts gelöscht, verschoben, umbenannt, in der Größe geändert oder in seinen Plugin-Daten
   verändert — auch nicht am von Hand entstandenen Brett `Entwurf: Sichtungsleiste`. Kollidiert
   die Fläche, weicht das Register aus.
6. **Ein Aufruf je Raster**, in der Reihenfolge der Tabelle oben, danach die Größenreihe der
   Schaltfläche, der Symbolblock, der Lücken-Block. Ein Fehlschlag bleibt dadurch lokal und der
   Wiederanlauf beginnt nicht von vorn.
7. **Abschluss:** `verify.js` unverändert ausführen. Es muss **dieselben Zahlen** melden wie in
   Schritt 2 (zwölf Bausteine, sieben Ansichten, dreißig Ansichtsbretter, sechs
   Ansichtsbehälter, `variantenMitFuellungOhneBindung` = 0). **Ausgenommen sind die mitgemeldeten
   Zählwerte über zusätzlich in Penpot vorhandene Objekte:** Sie steigen durch das Register
   legitim (Zellbretter, Beschriftungen, Striche) und sind an dieser Stelle Hinweis, keine
   Schwelle — ihr Anstieg ist keine Abweichung. Dazu `export_shape` je Raster auf die **Form**
   für die Sichtprüfung; kein Bild wird eingecheckt, das Anhängen an den Pull Request ist Daniels
   Handgriff.

## UI/UX

### Anordnung: drei Spalten nach Rolle, nicht nach Alphabet

Die zwölf Raster stehen in der Register-Zone in drei Spalten, gruppiert nach der Rolle des
Bausteins — wer nachschlägt, sucht nach „was ist das", nicht nach einem Anfangsbuchstaben:

| Spalte | Raster |
|---|---|
| **Bedienelemente** | Schaltfläche (samt Größenreihe), Eingabefeld, Auswahlkästchen, Schalter |
| **Anzeigen** | Hinweis, Kennzeichen, Fortschrittsanzeige, Kategorie-Chip |
| **Behälter und Verlauf** | Karte, Dialog, Schrittmarke, Platzhalter |

Die Schaltfläche steht oben links: Sie ist mit 30 Zellen plus Größenreihe das größte Raster und
der häufigste Nachschlagefall. Symbolblock und Lücken-Block stehen unter den drei Spalten, in
dieser Reihenfolge.

**Die Register-Zone liegt oberhalb des Bestands, nicht rechts davon.** Der Bestand reicht bis
x ≈ 18.830 — allein das Variantenbrett der Schaltfläche ist rund 17.960 px breit. Rechts daneben
wäre das Register nur nach einem sehr weiten Weg erreichbar und als „ein Ort, zwei Zonen" nicht
mehr wahrnehmbar. Beide Zonen bleiben getrennt und je mit Überschrift versehen; am Bestand ändert
sich dadurch nichts.

### Beschriftungshierarchie: fünf getrennte Größenstufen

Die Hierarchie trägt über die **Schriftgröße**, nicht über die Textfarbstufen — `color.text` und
`color.text-muted` sind laut Design-System nur schwach unterscheidbar, eine Hierarchie darf auf
ihnen nicht allein aufbauen.

| Ebene | Token | Farbe |
|---|---|---|
| Seitentitel „Bausteine — Zustände" | `text.2xl` | `color.text-h` |
| Zonenüberschrift („Bestand …" / „Register …") und Gruppenüberschrift („Bedienelemente", „Anzeigen", „Behälter und Verlauf") | `text.xl` | `color.text-h` |
| Rasterüberschrift (Bausteinname) | `text.lg` | `color.text-h` |
| Spalten- und Zeilenbeschriftung | `text.sm` | `color.text-muted` |
| Leerzellen-Vermerk, Bewegungsvermerk, Symbolname | `text.xs` | `color.text-muted` |

Zonen- und Gruppenüberschrift teilen bewusst **eine** Stufe: Fünf durch die Schriftgröße klar
getrennte Stufen (40 · 24 · 20 · 14 · 12 px) für sechs Rollen sind lesbarer als sechs Stufen, von
denen zwei sich nur in der Textfarbe unterschieden — und genau diese Unterscheidung trägt laut
Design-System nicht. Die Gruppenüberschrift ist durch ihre Stellung über ihrer Spalte eindeutig.

Die Verbundtokens tragen Schriftfamilie, Größe, Zeilenhöhe und Gewicht bereits — es wird kein
Gewicht, keine Kapitälchen- und keine Kursivstellung zusätzlich gesetzt.

### Zellgrund: jede Zelle ist halb dunkel, halb hell

Eine Zelle besteht aus **zwei gleich hohen Rechtecken** — links `color.bg`, rechts
`color.text-h` — und die Instanz liegt **über deren Grenze**. Damit ist jeder Baustein gegen
beide Gründe zu sehen, in einem Blick.

Das ist die Antwort auf den Kontrast-Vorfall, und sie geht weiter als ein Zellrahmen: Ein
dunkler oder transparenter Baustein auf dunklem Grund ist nicht erkennbar, und eine bloße
Zellgrenze macht ihn nicht sichtbar, sondern zeigt nur, *dass* dort etwas stehen sollte. Erst
der Wechsel hell/dunkel unter demselben Element zeigt, was es trägt und was ihm fehlt — bei
`button/ghost` und `button/link` wird auf der hellen Hälfte unmittelbar sichtbar, dass ihre
Textfarbe für hellen Grund nicht gedacht ist.

Ein Zellstrich entfällt damit: Die beiden Felder *sind* die Zelle, ihre Kanten sind die
Zellgrenze. Das erspart je Zelle eine Form und nimmt dem Raster die Verwechslungsgefahr
zwischen Zellrahmen und der Ausprägung `outline`.

**Die Instanz wird auf ihre Inhaltsbreite gebracht** (`flex.horizontalSizing = 'auto'` am
Instanz-Board) und sitzt bei einem Viertel der Zellbreite, sodass sie die Feldgrenze überlappt.
Ohne diesen Schritt behält sie die Breite ihrer Hauptinstanz — rund 350 px, gespannt von der
Debug-Beschriftung — und füllt die Zelle als abgeschnittene Farbfläche. **Bei einer Ausprägung
ohne Beschriftung** (`groesse=icon`) greift `auto` nicht, weil der ausgeblendete Text im Layout
verbleibt; dort wird die Instanz ausdrücklich auf `33 × 33` gesetzt.

### Leerzelle: eine Aussage, kein Versäumnis

Eine Leerzelle trägt denselben Strich und dieselbe Größe wie jede andere Zelle und darin einen
kurzen Vermerk in `text.xs`/`color.text-muted`, der sagt, **warum** die Kombination nicht
existiert — nicht bloß einen Gedankenstrich:

- Kennzeichen `neutral × suggested`: „neutraler Ton kennt keinen Vorschlag"
- Karte `favorite/album_worthy/rejected × vorschlag mit`: „eigene Bewertung hat Vorrang"
- Dialog, Zeile `geschlossen`: „zeigt nichts"

Eine Zelle ohne Strich und ohne Vermerk gibt es nicht: Sie wäre von einem abgebrochenen Aufbau
nicht zu unterscheiden.

### Die Beschriftung der Instanzen wird überschrieben

Die Hauptinstanzen tragen heute als sichtbaren Text **ihre eigene Variantenkombination**
(„bewertung=rejected, vorschlag=mit", „auspraegung=status-failed"). Eine so beschriftete Karte
erscheint **nicht** so, wie sie in der Anwendung aussieht — dort steht ein Dateiname. Im Register
gilt deshalb:

- **Die Kombination steht in der Zeilen- und Spaltenbeschriftung der Zelle, nie im Baustein.**
  Sie doppelt geführt zu haben, macht das Raster unlesbar und den Baustein unecht.
- **Die Instanz bekommt eine produktnahe Beschriftung**, damit Fläche, Umriss und Textfarbe des
  Zustands an einem echten Inhalt sichtbar sind (die Schaltfläche eine Aktionsbeschriftung, die
  Karte einen Dateinamen, der Hinweis einen Meldungssatz).
- **Herkunft dieser Beschriftungen ist abschließend geregelt** und folgt der geltenden
  Muss-Regel für Beispieldaten in Entwürfen, weil ein Formexport an einen öffentlichen Pull
  Request geht: ausschließlich aus dem versionierten Demo-Bestand (Projektnamen mit dem Präfix
  `Demo — `, Dateinamen der Form `foto-0001.jpg`, Pfade der Form `/Demo/<slug>`) oder erkennbar
  erfunden. Kein Name, kein Pfad, kein Datum und kein Dateiname aus Daniels Instanz, aus einer
  OpenCloud-Antwort oder aus der Erinnerung einer früheren Sitzung — auch nicht, damit es
  realistischer aussieht.
- **Vor der Übergabe an Daniel** werden die sichtbaren Zeichenketten des Registers einmal
  durchgesehen und es wird bestätigt, dass jede entweder UI-Beschriftung, Achsenbeschriftung oder
  Demo-Bestand ist.

### Was die Bibliothek nicht hergibt — am gebauten Register gemessen

Diese drei Befunde sind beim Bau entstanden, nicht vorher bekannt, und sie sind der eigentliche
Ertrag der Seite: Sie waren vorher nirgends sichtbar.

| Befund | Messung |
|---|---|
| **Kein Baustein ist ausmodelliert.** Jeder ist ein Rechteck mit genau **einer** Textbeschriftung — kein Kästchen, kein Häkchen, kein Schalterknauf, kein Fortschrittsbalken. | Auswahlkästchen, Schalter und Fortschrittsanzeige haben je ein Kind, Typ `text`. |
| **Die Zustände einer Schaltfläche sind nur teilweise unterschieden.** `normal`, `hover`, `active` und `busy` tragen dieselbe Füllung `color.accent` ohne Rahmen und ohne Deckkraftunterschied; allein `disabled` weicht ab (`color.surface` plus Rahmen). Die Regel „gedrückt ist Pflicht" ist in Penpot nicht abgebildet. | Füllung und Bindung aller fünf Zustände bei `auspraegung=default`, `groesse=default` verglichen. |
| **Die Größenachse trägt keine eigenen Maße.** `default`, `sm` und `icon` sind alle 33 hoch; die unterschiedlichen Breiten der Hauptinstanzen stammen allein aus ihrer Debug-Beschriftung. | Maße aller drei Größen bei `auspraegung=default`, `zustand=normal`. |

**Das Register zeichnet nichts davon nach.** Es zeigt, was die Bibliothek hat, und benennt die
Differenz — beim Schaltflächen-Raster und bei der Größenreihe als Befundzeile in `color.accent`
direkt unter dem Raster, alles Weitere im Lücken-Block. Ein nachgezeichnetes Kästchen wäre eine
freie Form und würde die Dauerregel brechen; er wäre außerdem eine zweite Wahrheit neben dem
Produkt.

### Zustände, die stillstehend nicht zu zeigen sind

`hover` und `active` bleiben **reguläre Zeilen des Rasters** — das Akzeptanzkriterium verlangt
jeden Zustand mindestens einmal, und beide wären statisch darstellbar.

**Ein Bewegungsvermerk an der einzelnen Zelle entfällt.** Die erste Fassung trug unter der
`busy`-Zelle „dreht sich — hier als Einzelbild", unter `indeterminate` „läuft durch" und am
Platzhalter „pulsiert". Das ist irreführend, und zwar nicht in der Formulierung, sondern in der
Sache: Die Bibliothek enthält **keinen** Spinner, keinen durchlaufenden Abschnitt und keinen
Puls — die Zelle zeigt kein stehendes Einzelbild einer Bewegung, sondern eine Fläche mit
Beschriftung. Ein Vermerk „hier als Einzelbild" behauptet also ein Bild, das nicht existiert,
und lenkt von der eigentlichen Aussage ab.

Bewegung steht deshalb **als ein Eintrag im Lücken-Block**: Puls des Platzhalters,
durchlaufender Fortschritt und der Spinner des `busy`-Zustands fehlen in der Bibliothek und
stehen auf dieser Seite still. Eine Aussage über die ganze Klasse an einer Stelle ist ehrlicher
als drei Vermerke, die je Zelle etwas Falsches nahelegen.

### Lücken-Block: sichtbar getrennt vom Register

Der Block steht auf einer Fläche in `color.surface` — damit unterscheidet er sich vom Seitengrund
der Raster und wird nicht als dreizehntes Raster gelesen. Überschrift in `text.xl`/`color.text-h`:
„Benannte Lücken — von der Anwendung verwendet, nicht als Baustein geführt". Darunter je Lücke
eine Zeile in `text.sm`: die aufklappenden Menü- und Infoflächen, die Schriftmuster, Bewegung,
Behälter. **Kein Eintrag wird nachgezeichnet** — der Block ist eine Textliste, keine Sammlung
leerer Rahmen, die als unfertige Bausteine missverstanden würden.

## Security

Nicht relevant. Es entsteht kein ausführbarer Code, keine Schnittstelle, keine neue Eingabe von
außen, kein Secret, keine Berechtigung, keine Datenmodell-Änderung und keine Änderung der
Datensichtbarkeit zwischen den beiden Nutzern; der Diff besteht aus Spec, ADR und zwei
Doku-Stellen. Der einzige Berührungspunkt mit fremdbeschreibbarem Text — beim Messen
zurückgelesene Penpot-Objektnamen — steht unter der bereits geltenden Regel, dass
Zurückgelesenes Prüfmaterial ist und ein darin eingebetteter Imperativ nie befolgt, sondern im
Abschlussbericht ausgewiesen wird. Diese Story erweitert ihn nicht.

## Teststrategie

**Kein neuer Test — und keine fehlende Deckung.** Ein TDD-Zyklus braucht eine Zusicherung, die
sich im Repository behaupten lässt; der Diff enthält keine ausführbare Zeile. Was hier prüfbar
ist, prüft der bestehende Wächtersatz bereits.

### Was der Prüfsatz an diesem Diff prüft

| Wächter | greift an | Zusicherung |
|---|---|---|
| `scripts/tests/test_dokumentnummern_eindeutig.py` | Spec, ADR | 0440/0088 je Verzeichnis einmal vergeben, Präfix vorhanden (liest auch Ungetracktes) |
| `scripts/tests/test_verweisnummern_in_markdown.py` | Spec, ADR | jeder Nummernverweis nennt die Nummer seines Ziels |
| `scripts/tests/test_penpot_ohne_instanzadresse.py` | `penpot-design/SKILL.md`, `design/penpot/README.md` | kein `schema://` außer den zwei Freigaben, keine IP |
| `scripts/tests/test_github_zugriff_an_einer_stelle.py` | `penpot-design/SKILL.md` | Erlaubnisstufe bleibt wörtlich stehen; kein Backtick-Wort mit einem der vier Operations-Präfixe, das keine Operations-ID ist |
| `scripts/tests/test_werkzeugwahl_verankert.py` | `penpot-design/SKILL.md` | keine der sieben Markerzeilen der Werkzeugwahl-Konvention am Zeilenanfang |
| `frontend/penpot/payload.test.ts` | unberührt | Kardinalitäten und fundstellengenaue Freigaben bleiben unverschoben, weil unter `design/penpot/` nur `README.md` angefasst wird |

**Zwei Fallen im neuen Block in `penpot-design/SKILL.md`, beide färben den Job `demo-scripts`
rot.** Eine Zeile, die mit einer der sieben Markerzeilen der Werkzeugwahl-Konvention **beginnt**,
gilt als zweite Fassung dieser Konvention (Codeblöcke ausgenommen, Nennung mitten in der Zeile
erlaubt). Und ein Backtick-Wort mit einem der vier Operations-Präfixe gilt als erfundene
Operations-ID. Beides ist sprachlich vermeidbar; beides scheitert laut, nicht still.

**Der Suchraum kommt aus `git ls-files`: Vor dem `git add` sieht der Verweis-Wächter Spec und ADR
nicht.** Nur der Dubletten-Wächter liest Ungetracktes. Der belastbare Lauf ist deshalb der nach
dem Hinzufügen.

**An der Stelle des Rot-Grün-Zyklus steht der Vorher-Nachher-Vergleich** aus dem Testkonzept,
Abschnitt „Nachweis ohne Rot-Grün", Punkte 1 und 2: kein Testdiff, identische Testknoten-Menge
mit identischem Ausgang zwischen `origin/main` und der Branch-Spitze. Punkt 3 (`Stmts`) entfällt,
es gibt keine Datei mit Statements. Punkt 2 ist hier keine Formsache — er ist der Detektor der
beiden Fallen oben. Coverage-Gate: kein Bezug, die Story fasst keine Zeile Anwendungscode an.

### Drei Zusicherungen ohne eigenen Wächter, je mit Begründung

- **Keine Plugin-Daten am Register.** Im Branch gibt es nichts, woran ein Test ansetzt. Geprüft
  wird sie trotzdem mechanisch, nur nicht in CI: `verify.js` bildet Bausteinliste, Brett- und
  Behälterzahl über genau diese Daten, ein Register-Objekt mit einem davon hebt eine der
  eingefrorenen Zahlen. Der Lauf in Schritt 7 belegt damit die Abwesenheit der Verletzung — nie
  die Vollständigkeit des Registers.
- **`payload.test.ts` bleibt unberührt.** Das ist eine Aussage über einen Diff, nicht über einen
  Dateizustand; ein Test darüber wäre nach dem Merge dauerhaft grün und prüfte nichts. Sie liegt
  im Nachweisverfahren (Punkt 1) und im Review.
- **Das Register steht nicht in `views.json`.** Der Fall ist schon gefangen: geschlossene,
  geordnete Namensmenge von sieben Schlüsseln und Anzeigenamen, `seite` als Ableitung
  `Ansicht — <Anzeigename>`, je Ansicht genau die zwei Prüfbreiten, Brettsumme gebunden gegen
  `ERWARTETE_ANSICHTEN`/`ERWARTETE_ANSICHTSBRETTER`. Ein späterer Eintrag färbt vier Zusicherungen
  rot und zwingt zusätzlich zu einer Änderung an `verify.js`. Ein eigener Wächter wäre eine
  zweite, schwächere Kopie.

### In der Sitzung gemessen, nicht mit dem Auge gezählt

Drei Kriterien sind billiger und härter als eine Sichtprüfung und gehören in einen eigenen
Messaufruf nach dem Bau (getrennt vom Bauaufruf — im selben Aufruf gelesen ist eine Bretthöhe
noch `1`):

1. **Zellgleichheit je Raster:** Breite und Höhe aller Zellbretter eines Rasters sind paarweise
   gleich, und ihre Zeilen- bzw. Spaltenachse liegt auf einer Koordinate.
2. **Vollständigkeit gegen `components.json`:** je Raster die Menge der geschalteten Ausprägungs-
   und Zustandswerte gegen die Achsen des Bausteins. Das ist ein **Selbstbericht des bauenden
   Aufrufs**, keine unabhängige Rücklesung — die Zellen tragen per Zusicherung keine
   Plugin-Daten, an denen ein Rückleser sie erkennen könnte. Als solcher zu berichten.
3. **Seitenliste:** „Bausteine — Zustände" vorhanden, „page 1" nicht mehr vorhanden.

### Sichtprüfung — sie tritt an die Stelle automatisierter Deckung

Daniel beurteilt das in der geöffneten Datei. **Ein Bildbeleg am Pull Request ist kein Teil der
Deckung** (die Kommandozeile hängt keine Bilder an); die Sichtprüfung selbst ist Pflicht und wird
in der PR-Beschreibung als offener Handgriff benannt, nicht als erledigt gemeldet.

**Ein Formexport einer Registerzelle taugt für die Kontrastbeurteilung nicht** und ist dafür auch
nicht zu verwenden: `export_shape` gibt ein Zellbrett **ohne den Seitengrund** aus, weil das Brett
selbst keine Fläche trägt. Eine transparente Zelle erscheint dort als leerer Rahmen, und ein
heller Text darin wird unsichtbar — beim ersten Lauf sah die Zelle `button/ghost` deshalb leer
aus, obwohl ihre Beschriftung vorhanden und an `color.text` gebunden war. Wer den Kontrast
beurteilen will, sieht in der geöffneten Datei hin oder exportiert einen Block **mit** Fläche
(etwa den Lücken-Block auf `color.surface`).

- [ ] Zwölf Raster mit Überschrift; Leserichtung überall Spalten = Ausprägungen, Zeilen = Zustände.
- [ ] Zeilen und Spalten sind beschriftet und ohne Vorwissen lesbar. **Keine Beschriftung
      überlagert eine andere** — insbesondere steht über keiner Zelle ein eingeblendeter
      Board-Name.
- [ ] Jede Zelle ist halb dunkel, halb hell, und der Baustein liegt über der Grenze. Kein
      Baustein verschwindet auf seinem Grund; bei `button/ghost` und `button/link` ist auf der
      hellen Hälfte ablesbar, dass ihre Textfarbe dort nicht trägt.
- [ ] Keine Instanz ragt aus ihrer Zelle, keine erscheint als abgeschnittene Farbfläche.
      `groesse=icon` ist ein kleines Quadrat, nicht ein breiter Balken.
- [ ] Jede Leerzelle trägt ihren Vermerk **innerhalb** der Zelle.
- [ ] Die Befundzeilen in `color.accent` stehen unter dem Schaltflächen-Raster und unter der
      Größenreihe und sind als Aussage über die Bibliothek lesbar, nicht als Beschriftung eines
      Bausteins.
- [ ] Die fünf Beschriftungsstufen sind als Hierarchie lesbar.
- [ ] Symbolblock: zwölf Symbole mit Namen; auf der hellen Hälfte ist erkennbar, dass die
      Strichfarbe für dunklen Grund gedacht ist.
- [ ] Lücken-Block als Textliste auf `color.surface`, kein Eintrag nachgezeichnet, nicht als
      dreizehntes Raster lesbar.
- [ ] Der Bestand ist unverändert: Variantenbretter, Symbole und das Brett
      `Entwurf: Sichtungsleiste` liegen an ihrer Stelle, in ihrer Größe, unter ihrem Namen.

## Entscheidungen

- **Dritte Seitenklasse „Register", von Hand, ohne Generator und ohne Soll-Struktur-Datei** — ADR
  [`0088`](../decisions/0088-bausteinregister-handarbeit-ohne-soll-struktur-seite-umbenannt.md).
- **Umbenennen statt neu anlegen.** Die Hauptinstanzen von 158 Varianten liegen nur einmal; ein
  Seitenname ist billig. Ist `page.name` über die API nicht schreibbar, wird das gemeldet und
  Daniel benennt die Seite im Browser um — es wird kein Ersatzweg über Neuanlegen gewählt.
- **Beschriftungshierarchie über fünf Größenstufen** (`text.2xl` bis `text.xs`) statt über die
  Textfarbstufen: `color.text` und `color.text-muted` sind nur schwach unterscheidbar.
- **Zelle aus zwei Feldern, halb `color.bg` und halb `color.text-h`, Instanz über der Grenze.**
  Erst der Wechsel unter demselben Element zeigt, was ein dunkler oder transparenter Baustein
  trägt. Ein bloßer Zellstrich (die erste Fassung) zeigte nur, *dass* dort etwas stehen sollte —
  und ließ sich mit der Ausprägung `outline` verwechseln.
- **Keine Boards und keine Gruppen als Zellen.** Penpot blendet über jedem Board dessen Namen
  ein und beschneidet dessen Kinder; `penpot.group()` friert die noch nicht nachgerechnete
  Instanzbreite ein. Deshalb freie Rechtecke plus freie Instanz, zusammengehalten von einem
  Rahmen-Board um die ganze Zone.
- **Instanzen auf Inhaltsbreite** (`flex.horizontalSizing = 'auto'`), `groesse=icon` fest auf
  33 × 33, weil `auto` bei ausgeblendeter Beschriftung nicht greift.
- **Kein Bewegungsvermerk je Zelle.** Er behauptete ein stehendes Einzelbild einer Bewegung, die
  in der Bibliothek gar nicht existiert; Bewegung steht als ein Eintrag im Lücken-Block.
- **`hover` und `active` bleiben reguläre Rasterzeilen.** Beide sind statisch darstellbar; sie aus
  dem Raster zu nehmen verfehlte das Kriterium „jeder Zustand mindestens einmal".
- **Instanz-Beschriftungen werden überschrieben**, Herkunft ausschließlich Demo-Bestand oder
  erkennbar erfunden.
- **Die Register-Zone liegt oberhalb des Bestands**, weil der Bestand rund 18.830 px breit ist.
- **Der Kategorie-Chip steht in einer ungebrochenen Reihe.** Der Umbruch aus der Rastertabelle
  ist nur für zu knappe Breite vorgesehen; die Fläche ist unbegrenzt, und dreizehn Chips in einer
  Reihe sind ablesbarer als eine Reihe plus Fortsetzungszeile.
- **Die Zusicherung „kein Objekt des Registers trägt Plugin-Daten" ist per Bauart erfüllt, nicht
  durch Aufräumen:** `komponente.instance()` kopiert die Plugin-Daten der Hauptinstanz **nicht**
  mit (am 2026-09-12 an der Schaltfläche gemessen: leere Schlüsselliste an Instanz und Kind). Es
  muss also nichts entfernt werden, damit die eingefrorenen Kardinalitäten unberührt bleiben.
- **`specs/architecture/0004-design-system.md` wird um einen Punkt ergänzt** — die stille Alterung
  des Registers ist eine geltende Pflegepflicht, die dort gesucht wird.
- **`specs/architecture/0002-testkonzept.md` wird um zwei Punkte ergänzt** (stille Alterung; die
  Zusicherung „keine Plugin-Daten" hat keinen Testgegenstand im Repository) **und um einen Satz
  zum Suchraum der Wächter**: Ein Wächter mit blankem `git ls-files` sieht eine neue Datei erst
  nach dem `git add`, ein grüner Lauf davor sagt über sie nichts. Damit umfasst der Diff sechs
  statt vier Dateien.
- **`test-engineer` konsultiert (Schritt 3), Ergebnis: kein neuer Test.** Jede Zusicherung dieser
  Story ist entweder eine Aussage über die Penpot-Datei, eine Aussage über einen Diff statt über
  einen Dateizustand, oder von einem bestehenden Wächter gedeckt, dessen Suchraum der Diff
  betritt.
- **`security-engineer` nicht konsultiert (Schritt 3):** Es entsteht kein ausführbarer Code, keine
  Schnittstelle, keine Eingabe von außen, kein Secret, keine Berechtigung, keine
  Datenmodell-Änderung und keine geänderte Datensichtbarkeit zwischen den beiden Nutzern; der
  Diff besteht aus Spec, ADR und Doku. Der einzige Fremdtext-Berührungspunkt steht unter einer
  bereits geltenden Regel, die diese Story nicht erweitert.

## Offene Fragen

Keine.

## Out of Scope

- **Die benannten Lücken zu schließen.** Die aufklappenden Menü- und Infoflächen und die
  Schriftmuster werden auf der Seite als Lücke ausgewiesen, nicht als Baustein ergänzt.
- **Ein Generator für die Seite.** Kein `seed-register.js`, keine Soll-Struktur-Datei, kein
  Eintrag in `views.json`.
- **Bausteine als Vorlage herausziehen.** Das Bibliotheks-Panel leistet das bereits; die Seite
  fügt dort nichts hinzu.
- **Änderungen am Bibliotheksbestand.** Kein Aufräumen, kein Entfernen der als verworfen
  benannten Schrittmarken-Fassung, keine Korrektur an einer Hauptinstanz.
