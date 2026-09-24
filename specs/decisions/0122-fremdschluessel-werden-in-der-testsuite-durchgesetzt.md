# 0122 - Fremdschlüssel werden in der Testsuite durchgesetzt

**Status:** Accepted
**Datum:** 2026-09-23
**Bezug:** [GitHub-Issue #350](https://github.com/TheRealKoller/photosort/issues/350), Spec 0350
**Berührt:** ADR [`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md) —
deren Feststellung „die Testsuite läuft ohne `PRAGMA foreign_keys=ON`, eine falsche
Löschreihenfolge fällt dort strukturell nicht auf" wird gegenstandslos. Die Entscheidung selbst
(metadatengeordnete Mengenlöschung, Reihenfolge und Vollständigkeit aus `Base.metadata` abgeleitet)
bleibt in Kraft und wird hier nicht abgelöst; ADR 0062 wird nicht nachträglich geändert.

## Kontext

Die Backend-Suite läuft gegen SQLite In-Memory. SQLite setzt Fremdschlüssel nur bei gesetztem
`PRAGMA foreign_keys` durch, und zwar **je Verbindung**; Postgres setzt sie immer durch. Bisher
setzte niemand dieses Pragma, und die Doku führte den Zustand an vier Stellen als bewusst offen
(Testkonzept, ADR 0062, `docs/architecture.md`, Securitykonzept), dazu in mehreren
Code-Kommentaren und Test-Docstrings. Damit war die Testdatenbank
nachsichtiger als die Zieldatenbank: eine fehlende ORM-Kaskade, eine falsche Löschreihenfolge und
eine verwaiste Kindzeile blieben in der gesamten Suite unsichtbar, und eine Assertion der Form
„kein `IntegrityError` geflogen" prüfte nichts. Die Zusagen der Projektlöschung wurden deshalb
ersatzweise über Zeilenzählungen und zwei Metadaten-Tests abgesichert.

Seitwärts davon liegt ein Verhaltensfehler derselben Ursache: `run_criterion_scoring` /
`run_classification` legen die Lauf-Zeile an, **bevor** sie die Herkunft ihres `scoring_run_id`
prüfen. Auf der Zieldatenbank läuft dieses INSERT bei einem verschwundenen Bewertungslauf in eine
Fremdschlüsselverletzung und reißt die Transaktion ab; der bisher geprüfte „saubere Fehlschlag"
(Lauf auf `FAILED`, `error_message` gesetzt) ist dort kein erreichbarer Zustand, weil es die Zeile
dafür gar nicht gibt.

## Entscheidung

1. **Das Pragma sitzt in `db.py::make_engine`, nicht global in `conftest.py`.** Damit gilt es für
   die Anwendung, für die `db_session`-Fixture und für jeden Test, der seine Engine über
   `make_engine` baut — und es lässt genau die Tests unberührt, die bewusst einen reduzierten
   Schemastand ohne Fremdschlüssel für eine Migrationsprüfung nachbauen: sie bauen ihre Engine
   weiterhin mit rohem `create_engine`. `tests/test_seed.py`, das seine synchrone Engine ebenfalls
   selbst baut, ist **kein** Ausnahmefall: es setzt dasselbe Pragma über denselben Handler, damit die
   Durchsetzung tatsächlich suiteweit gilt. *Verworfene Alternative:* ein globaler `Engine`-Listener.
   Er erwischt die reduzierten Schemata mit und erzeugt Fremdschlüsselverletzungen in Tests, deren
   ausdrückliches Ziel ein Zustand **vor** der jeweiligen Fremdschlüssel-Änderung ist.
2. **Die Durchsetzung wird belegt, nicht behauptet.** Ein Test legt eine Kindzeile ohne gültige
   Elternzeile an und erwartet die Ablehnung durch die Datenbank; ein zweiter prüft das Pragma
   unmittelbar an einer über `make_engine` gebauten Engine. Ein struktureller Wächter hält fest,
   dass `create_async_engine` ausschließlich in `db.py` vorkommt — jede weitere async-Engine
   entstünde an der Durchsetzung vorbei, ohne dass ein Verhaltenstest das bemerkte.
3. **Das ORM muss die Löschabhängigkeit kennen, nicht nur die Datenbank.** `Event` hängt als
   dritter Elternteil an `PhotoRanking` (`photo_rankings.event_id`). SQLAlchemy leitet die
   Löschreihenfolge von Tabellen aus **Relationships** ab, nicht aus Fremdschlüsseln: ohne
   `Event.rankings` löscht der Flush `events` vor `photo_rankings`. `Event.rankings` und
   `CriterionScoringRun.events` tragen deshalb `cascade="all, delete-orphan"` — dieselbe Form wie
   `Photo.rankings` und `CriterionScoringRun.rankings` daneben. **Kein Schemawechsel, keine
   Migration**: reine Relationship-Deklarationen.
4. **Der Herkunftsverweis wird geprüft, bevor die Lauf-Zeile entsteht.** Ein gemeinsamer Helfer
   legt die Lauf-Zeile für beide Aufrufer (`run_criterion_scoring` beim Direktaufruf,
   `run_classification` im verketteten Lauf) an; er prüft zuerst die **Existenz** des referenzierten
   `ScoringRun` und wirft sonst eine neue, typisierte Ausnahme. Die **Aktualitätsprüfung**
   („ist es der neueste *erfolgreiche* Lauf?") bleibt bewusst dahinter und endet unverändert als
   `FAILED`-Lauf — dafür gibt es eine Zeile, also auch eine sichtbare Historie. Der Unterschied der
   beiden Fälle ist die Unterscheidung „Elternteil fehlt" (nichts anzulegen, nichts zu markieren)
   und „Elternteil passt nicht" (Zeile anlegen, dann als fehlgeschlagen führen).
5. **Ein `IntegrityError` wird nicht übersetzt.** Am INSERT bleibt es beim Datenbankfehler; das
   Restfenster, in dem der referenzierte Bewertungslauf zwischen Prüfung und INSERT verschwindet,
   wird benannt statt zugedeckt. Es ist dieselbe Bauart wie die dort weiterhin offene Lücke der
   eingereihten, noch nicht gestarteten Jobs: ein Fenster zwischen Lesen und Schreiben, das nur
   eine Sperre oder eine echte Warteschlangen-Transaktion schlösse — beides steht außer Verhältnis
   zum Nutzen für ein Zwei-Nutzer-Werkzeug.

## Konsequenzen

- Testdatenbank und Zieldatenbank verhalten sich in Integritätsfragen gleich. Eine fehlende
  Kaskade, eine falsche Löschreihenfolge und eine verwaiste Kindzeile werden ab jetzt **im Test**
  rot, nicht erst unter Postgres.
- Die beiden Metadaten-Tests aus ADR 0062 bleiben in Kraft, ihre Begründung verschiebt sich: die
  Fremdschlüssel-Durchsetzung deckt die **Reihenfolge** ab, die abgeleitete Vollständigkeitsprüfung
  weiterhin die **Vergessenheit** einer Tabelle — ein Fremdschlüsselfehler nennt keine vergessene
  Anweisung.
- Die projektweite Regel „jede Lösch-Zusage wird über Zeilenzählungen geprüft, nie über die
  Abwesenheit einer Ausnahme" bleibt bestehen: Zeilenzählungen nennen auch die verwaiste Zeile, die
  ein **fehlender** Fremdschlüssel nicht meldet. Die Aussage „die Suite läuft ohne
  `PRAGMA foreign_keys=ON`" wird an allen Fundstellen als Tatsachenbehauptung nachgezogen.
- **Ein neuer Preis:** die Suite schlägt künftig auch dann fehl, wenn eine Test-Fixture selbst
  inkonsistent aufbaut (Kindzeile ohne Elternteil). Das ist gewollt. Ausgenommen bleiben die Tests,
  die ein reduziertes Schema ohne Fremdschlüssel nachbauen — jede weitere Ausnahme dieser Art ist
  eine bewusste Einzelentscheidung und keine Regel.
- **Benannte Restfenster:** der Herkunftsverweis kann zwischen Prüfung und INSERT verschwinden
  (Punkt 5), und der `409`-Wächter sieht eingereihte, noch nicht gestartete Jobs weiterhin nicht.
  Beide bleiben offen.
- **Der Migrationspfad bleibt außen vor:** `alembic/env.py` baut seine Engine weiterhin selbst. Er
  prüft Schemastände, in denen Fremdschlüssel absichtlich fehlen.
