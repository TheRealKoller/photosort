"""albumentscheidung: status wird nullable, favorite zieht als eigene spalte daneben

`ratings.status` traegt kuenftig ausschliesslich die ALBUMENTSCHEIDUNG (`album_worthy` |
`rejected`); `NULL` heisst "keine Albumentscheidung". Die Auszeichnung als Favorit verlaesst den
Wertevorrat und wird die eigene, unabhaengige Spalte `ratings.favorite`.

DIE SPALTE TRAEGT DEN ENUM-NAMEN, NICHT SEINEN WERT: In `ratings.status` und
`photo_scores.suggested_status` steht `'FAVORITE'`, nicht `'favorite'`.
`SQLEnum(RatingStatus, native_enum=False)` speichert ohne `values_callable` den `.name`, auch bei
einem `enum.StrEnum`, dessen `.value` kleingeschrieben ist; die Ursprungsmigration
`f3aab5f3fa96_add_ratings_table.py` listet die Werte entsprechend gross. Ein `WHERE` auf den
kleingeschriebenen Wert trifft KEINE Zeile - die Migration liefe fehlerfrei durch, konvertierte
nichts, und der erste Lesepfad danach wuerfe einen `LookupError`. Genau dieser Fehler steht
unbemerkt auch in `c1d2e3f4a5b6_criterion_scoring_pipeline.py`. Gemessen und festgehalten in
`tests/test_migration_albumentscheidung.py::test_the_column_stores_the_enum_name_not_its_value`.

VERGLICHEN WIRD DESHALB UEBER `upper(...)`. Aus dem Anwendungscode kann keine andere Schreibweise
entstehen - jede Schreibstelle beider Spalten laeuft ueber das ORM -, und keine Migration hat je
einen nicht-leeren Wert hineingeschrieben. Die Unempfindlichkeit ist kein bekannter Fall, sondern
Versicherung: Die Konvertierung laeuft genau einmal, ist nach dem Deploy nicht nachholbar, und ihr
Fehlschlag ist eine 500 auf jeder Fotoliste statt einer Fehlermeldung.

REIHENFOLGE des Vorwaertswegs, und sie ist nicht beliebig:

1. `favorite` anlegen (`nullable=False`, `server_default=sa.false()`) UND `status` nullable
   stellen - beides in EINEM `batch_alter_table`, weil SQLite kein `ALTER COLUMN` kennt und den
   Block zu einem einzigen Tabellenneuaufbau zusammenfasst.
2. ERST DANACH die Konvertierung `favorite = true, status = NULL`. Umgekehrt (erst konvertieren,
   dann nullable stellen) bricht das `UPDATE` an der noch bestehenden `NOT NULL`-Bedingung ab.
3. `photo_scores.suggested_status` auf `NULL` - dieselbe Enum-KLASSE, eine Kopplung ohne
   Fremdschluesselbeziehung (Auflage S11). Ohne diesen Schritt wirft eine Bestandszeile beim
   Lesen einen `LookupError`: eine 500 auf jeder Fotoliste, die das Foto enthaelt.

`sa.false()` statt `sa.text("0")`: SQLite kennt keinen echten Boolean-Typ und akzeptiert
`DEFAULT 0` klaglos, Postgres bricht mit `DatatypeMismatch` ab.

ACHTUNG - `downgrade()` VERLIERT DATEN und stellt nur die Struktur wieder her: Zeilen ohne
Albumentscheidung werden GELOESCHT, und eine Zeile mit Albumentscheidung UND Favorit behaelt
allein die Albumentscheidung. Siehe den Docstring von `downgrade()`.

Revision ID: f6a7b8c9d0e1
Revises: e7f8a9b0c1d2
Create Date: 2026-09-13 15:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_TYPE = sa.String(length=20)

# Der GESPEICHERTE Wert des entfallenen Enum-Eintrags - der NAME, nicht `RatingStatus.FAVORITE`
# und nicht dessen kleingeschriebener `.value`. Als Konstante und nicht als Literal an drei
# Stellen, damit die Schreibweise nicht je Anweisung neu entschieden wird. Ein Verweis auf das
# Enum geht hier grundsaetzlich nicht: Der Eintrag ist mit dieser Migration fort, eine Migration
# muss aber ohne den Code lauffaehig bleiben, gegen den sie geschrieben wurde.
_STORED_FAVORITE = "FAVORITE"


def upgrade() -> None:
    """Upgrade schema - siehe Modul-Docstring fuer die Reihenfolge."""
    with op.batch_alter_table("ratings") as batch_op:
        batch_op.add_column(
            sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.alter_column("status", existing_type=_STATUS_TYPE, nullable=True)

    op.execute(
        sa.text(
            "UPDATE ratings SET favorite = true, status = NULL "
            f"WHERE upper(status) = '{_STORED_FAVORITE}'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE photo_scores SET suggested_status = NULL "
            f"WHERE upper(suggested_status) = '{_STORED_FAVORITE}'"
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN - und das ist hier ein echter, benannter
    VERLUST, kein Restrisiko:

    - Eine reine Favoritenzeile (`favorite = true AND status IS NULL`) wird wieder
      `status = 'FAVORITE'` - in der Schreibweise, die das WIEDERHERGESTELLTE alte Enum lesen
      kann.
    - Eine Zeile, die Albumentscheidung UND Favorit traegt, behaelt die Albumentscheidung; die
      AUSZEICHNUNG GEHT VERLOREN, weil das alte Schema beide nicht zugleich abbilden kann.
    - Jede danach verbleibende Zeile ohne Albumentscheidung wird GELOESCHT - das alte Schema
      kann sie nicht darstellen. Ohne diese Loeschung scheiterte der `NOT NULL`-Aufbau mitten im
      Rueckwaertsweg und liesse die Tabelle halb umgebaut zurueck. Ein ersatzweise geschriebener
      Vorgabewert waere schlimmer: er erfaende eine Entscheidung, die niemand getroffen hat.

    `photo_scores.suggested_status` wird NICHT zurueckkonvertiert: Welche Zeile vorher
    `'FAVORITE'` trug, steht nach dem Vorwaertsweg nirgends mehr."""
    op.execute(
        sa.text(
            f"UPDATE ratings SET status = '{_STORED_FAVORITE}' "
            "WHERE favorite = true AND status IS NULL"
        )
    )
    op.execute(sa.text("DELETE FROM ratings WHERE status IS NULL"))

    with op.batch_alter_table("ratings") as batch_op:
        batch_op.alter_column("status", existing_type=_STATUS_TYPE, nullable=False)
        batch_op.drop_column("favorite")
