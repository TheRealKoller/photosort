"""albumentscheidung: status wird nullable, favorite zieht als eigene spalte daneben

`ratings.status` traegt kuenftig ausschliesslich die ALBUMENTSCHEIDUNG (`album_worthy` |
`rejected`); `NULL` heisst "keine Albumentscheidung". Die Auszeichnung als Favorit verlaesst den
Wertevorrat und wird die eigene, unabhaengige Spalte `ratings.favorite`.

REIHENFOLGE des Vorwaertswegs, und sie ist nicht beliebig:

1. `favorite` anlegen (`nullable=False`, `server_default=sa.false()`) UND `status` nullable
   stellen - beides in EINEM `batch_alter_table`, weil SQLite kein `ALTER COLUMN` kennt und den
   Block zu einem einzigen Tabellenneuaufbau zusammenfasst.
2. ERST DANACH `UPDATE ratings SET favorite = true, status = NULL WHERE status = 'favorite'`.
   Umgekehrt (erst konvertieren, dann nullable stellen) bricht das `UPDATE` an der noch
   bestehenden `NOT NULL`-Bedingung ab.
3. `UPDATE photo_scores SET suggested_status = NULL WHERE suggested_status = 'favorite'` -
   dieselbe Enum-KLASSE, eine Kopplung ohne Fremdschluesselbeziehung (Auflage S11). Ohne diesen
   Schritt wirft eine Bestandszeile beim Lesen einen `LookupError`: eine 500 auf jeder
   Fotoliste, die das Foto enthaelt.

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


def upgrade() -> None:
    """Upgrade schema - siehe Modul-Docstring fuer die Reihenfolge."""
    with op.batch_alter_table("ratings") as batch_op:
        batch_op.add_column(
            sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.alter_column("status", existing_type=_STATUS_TYPE, nullable=True)

    op.execute(
        sa.text("UPDATE ratings SET favorite = true, status = NULL WHERE status = 'favorite'")
    )
    op.execute(
        sa.text(
            "UPDATE photo_scores SET suggested_status = NULL WHERE suggested_status = 'favorite'"
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN - und das ist hier ein echter, benannter
    VERLUST, kein Restrisiko:

    - Eine reine Favoritenzeile (`favorite = true AND status IS NULL`) wird wieder
      `status = 'favorite'`.
    - Eine Zeile, die Albumentscheidung UND Favorit traegt, behaelt die Albumentscheidung; die
      AUSZEICHNUNG GEHT VERLOREN, weil das alte Schema beide nicht zugleich abbilden kann.
    - Jede danach verbleibende Zeile ohne Albumentscheidung wird GELOESCHT - das alte Schema
      kann sie nicht darstellen. Ohne diese Loeschung scheiterte der `NOT NULL`-Aufbau mitten im
      Rueckwaertsweg und liesse die Tabelle halb umgebaut zurueck. Ein ersatzweise geschriebener
      Vorgabewert waere schlimmer: er erfaende eine Entscheidung, die niemand getroffen hat.

    `photo_scores.suggested_status` wird NICHT zurueckkonvertiert: Welche Zeile vorher
    `'favorite'` trug, steht nach dem Vorwaertsweg nirgends mehr."""
    op.execute(
        sa.text("UPDATE ratings SET status = 'favorite' WHERE favorite = true AND status IS NULL")
    )
    op.execute(sa.text("DELETE FROM ratings WHERE status IS NULL"))

    with op.batch_alter_table("ratings") as batch_op:
        batch_op.alter_column("status", existing_type=_STATUS_TYPE, nullable=False)
        batch_op.drop_column("favorite")
