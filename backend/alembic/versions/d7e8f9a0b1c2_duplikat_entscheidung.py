"""duplikat_entscheidung: die ausschuss-entscheidung bekommt ihre eigene tabelle

`photo_duplicate_decisions` traegt die ausdrueckliche Entscheidung des PROJEKTS darueber, ob eine
Aufnahme den Ausschuss-Schritt ueberlebt (ADR 0104). Die Duplikat-Gruppe selbst bekommt KEINE
eigene Entitaet; sie bleibt ein zur Lesezeit gebildeter Stern ueber `photo_scores.duplicate_of`.

DATENLOS in beide Richtungen: Es gibt vor dieser Story keine Entscheidungszeilen, und kein Schritt
berechnet rueckwirkend etwas. Ein bestehendes Projekt behaelt damit genau den Ausschuss, den sein
letzter Lauf vorgeschlagen hat.

`photo_id` ist Primaerschluessel UND Fremdschluessel - "hoechstens eine Entscheidung je Foto" ist
damit strukturell wahr, ohne eigenen Unique-Constraint, und ein wiederholtes `PUT` ueberschreibt
statt in eine 500 zu laufen. Der echte Fremdschluessel ist Pflicht: Die Loeschzusage in
`project_deletion.py` prueft Erreichbarkeit ueber die Kanten in `Base.metadata`, eine bloss
logische Spalte fiele still aus der Pruefung heraus. Sein Name ist ausgeschrieben, weil
`Base.metadata` keine `naming_convention` traegt und ein unbenannter Fremdschluessel unter SQLite
im Rueckwaertsweg nicht droppbar waere.

`decision` traegt KEINEN Default, weder Python- noch server-seitig: Die Abwesenheit der Zeile
heisst "noch nicht entschieden", und ein Vorgabewert erfaende eine Entscheidung, die niemand
getroffen hat - eine Entscheidung, die mitbestimmt, welche Bilddaten den Homeserver Richtung
Cloud-Anbieter verlassen.

Der Typ ist ein `VARCHAR(16)` ohne DB-seitige Pruefeinschraenkung (`native_enum=False` auf der
Modellseite). Ein echter Postgres-Enum-Typ verlangte fuer jeden kuenftigen Wert ein `ALTER TYPE`;
gerendert wird die Spalte hier bewusst als `sa.String`, damit Modell- und Migrationsseite dieselbe
DDL erzeugen. Gespeichert wird der Enum-NAME (`'KEEP'`/`'DISCARD'`), nicht der kleingeschriebene
Wert - siehe `tests/test_migration_duplikat_entscheidung.py`.

ACHTUNG - `downgrade()` VERLIERT DATEN, siehe seinen Docstring.

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-09-14 11:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "photo_duplicate_decisions"

# Deckt den laengsten gespeicherten Namen (`DISCARD`) mit Reserve. Ein Verweis auf das Enum aus
# `photosort.models` steht hier bewusst nicht: Eine Migration muss ohne den Code lauffaehig
# bleiben, gegen den sie geschrieben wurde.
_DECISION_TYPE = sa.String(length=16)


def upgrade() -> None:
    """Upgrade schema - legt die Tabelle an, ohne eine einzige Zeile zu schreiben."""
    op.create_table(
        _TABLE,
        sa.Column("photo_id", sa.Integer(), nullable=False),
        # Ohne `server_default`: siehe Modul-Docstring. Der Wert wird ausdruecklich geschrieben
        # oder die Zeile existiert nicht.
        sa.Column("decision", _DECISION_TYPE, nullable=False),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_photo_duplicate_decisions_photo_id"
        ),
        sa.PrimaryKeyConstraint("photo_id"),
    )


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN: Mit der Tabelle ist jede Entscheidung ueber den
    Ausschuss verloren, und das ist ein benannter VERLUST in beide Richtungen. Jedes ausdrueckliche
    "behalten" faellt fort - die Aufnahme ist danach wieder Duplikat-Verlierer und verlaesst den
    Bestand. Jedes ausdrueckliche "Ausschuss" faellt ebenfalls fort - die Aufnahme laeuft danach
    wieder in Kriterien-Bewertung und, bei erteilter Einwilligung, in die Cloud-Klassifizierung.
    Einen Rueckweg, der sie erhielte, gibt es nicht: es existiert keine zweite Stelle, an der sie
    stuenden."""
    op.drop_table(_TABLE)
