"""gewichtssaetze: die gewichte der qualitaetskriterien werden versioniert persistiert

Zwei Tabellen und eine Spalte (ADR 0100). `quality_weight_sets` haelt EINE Fassung des global
geltenden Gewichtssatzes, `quality_weight_entries` ihre Gewichte je Kriterium, und
`criterion_scoring_runs.quality_weight_set_id` haelt fest, mit welcher Fassung ein Lauf gerechnet
hat.

KEINE VORGABEFASSUNG WIRD EINGESCHRIEBEN, und das ist die eigentliche Aussage dieser Migration:
Ohne eine einzige Zeile gelten die Startwerte aus `quality.py`. Ein eingeschriebener Vorgabewert
waere von einer uebernommenen Anpassung nicht mehr zu unterscheiden - "zurueck auf die Startwerte"
hiesse danach "zurueck auf eine Fassung, die jemand uebernommen hat".

ES GILT DIE FASSUNG MIT DER HOECHSTEN `id`. Es gibt kein `active`-Kennzeichen, das danebentreten
und mit ihr auseinanderlaufen koennte; `id` IST die Version.

`criterion_key` traegt KEINEN Fremdschluessel, derselbe Grund wie bei
`photo_criterion_scores.criterion_key`: Ein neues Kriterium erzwingt nie eine Migration.
`based_on_event_id` traegt ebenfalls keinen - es ist das Zustimmungs-Token auf den zuletzt
gesehenen Ereignisstand (S6), wird nie zu einer Zeile aufgeloest und traegt bei leerem Log den
Wert `0`.

BEIDE TABELLEN HAENGEN AN KEINEM PROJEKT und bleiben von der Projektloeschung unberuehrt: Sie
tragen sieben Zahlen und einen Nutzerverweis, keinen Foto-Bezug, und sind auf kein Foto
zurueckzurechnen (S13).

ACHTUNG - `downgrade()` VERLIERT DATEN, siehe seinen Docstring.

Revision ID: c5d6e7f8a9b0
Revises: b1c2d3e4f5a6
Create Date: 2026-09-14 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETS = "quality_weight_sets"
_ENTRIES = "quality_weight_entries"
_RUNS = "criterion_scoring_runs"
_RUN_COLUMN = "quality_weight_set_id"
_ENTRY_UNIQUE = "uq_quality_weight_entries_set_criterion"
_RUN_FK = "fk_criterion_scoring_runs_quality_weight_set_id"


def upgrade() -> None:
    """Upgrade schema - legt beide Tabellen und die Spalte an, ohne eine einzige Zeile zu
    schreiben."""
    op.create_table(
        _SETS,
        # `id` IST die Version: Es gilt die Fassung mit der hoechsten `id`.
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # PFLICHTIG: Eine Fassung ohne Urheber liesse nicht mehr erkennen, wer die global
        # wirkende Anpassung ausgeloest hat. Die Fassung GILT trotzdem global - der Verweis ist
        # Urheberschaft, nie Geltungsbereich.
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        # `native_enum=False`: ein neuer Wert erzwingt sonst unter Postgres eine Typmigration,
        # waehrend SQLite sie nie verlangt - der Unterschied faellt erst produktiv auf.
        sa.Column(
            "origin",
            sa.Enum(
                "feedback",
                "revert",
                native_enum=False,
                length=16,
                name="qualityweightsetorigin",
            ),
            nullable=False,
        ),
        # OHNE `ForeignKeyConstraint`, siehe Modul-Docstring: Zustimmungs-Token, kein Verweis.
        sa.Column("based_on_event_id", sa.Integer(), nullable=True),
        sa.Column("reverts_set_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reverts_set_id"], [f"{_SETS}.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        _ENTRIES,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_id", sa.Integer(), nullable=False),
        # FREIER STRING OHNE FREMDSCHLUESSEL, siehe Modul-Docstring.
        sa.Column("criterion_key", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["set_id"], [f"{_SETS}.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Zwei Gewichte fuer dasselbe Kriterium in derselben Fassung waeren zwei Wahrheiten;
        # welche gilt, entschiede die Zeilenreihenfolge. BENANNT, damit `downgrade()` sie unter
        # SQLite ueberhaupt wieder loesen koennte.
        sa.UniqueConstraint("set_id", "criterion_key", name=_ENTRY_UNIQUE),
    )
    # `batch_alter_table` mit BENANNTEM Fremdschluessel: Ein unbenannt angelegter Constraint ist
    # im `downgrade()` unter SQLite nicht droppbar (`drop_constraint` braucht einen Namen).
    with op.batch_alter_table(_RUNS) as batch_op:
        # NULLBAR: `NULL` heisst "Startwerte oder Altzeile". Jeder bereits gelaufene Lauf hat mit
        # den Startwerten gerechnet und hat keine Fassung, auf die er zeigen koennte.
        batch_op.add_column(sa.Column(_RUN_COLUMN, sa.Integer(), nullable=True))
        batch_op.create_foreign_key(_RUN_FK, _SETS, [_RUN_COLUMN], ["id"])


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN: Mit den beiden Tabellen ist JEDE uebernommene
    Anpassung der Gewichte verloren, und es gibt keine zweite Stelle, an der sie stuende. Jeder
    Lauf danach rechnet wieder mit den Startwerten aus `quality.py` - die Rangfolgen aller
    Projekte verschieben sich beim naechsten Durchlauf, ohne dass irgendetwas das als Verlust
    ausweist. Verloren ist zusaetzlich die Angabe, mit welcher Fassung ein vergangener Lauf
    gerechnet hat; seine Zahlen sind danach nicht mehr nachrechenbar."""
    with op.batch_alter_table(_RUNS) as batch_op:
        batch_op.drop_constraint(_RUN_FK, type_="foreignkey")
        batch_op.drop_column(_RUN_COLUMN)
    op.drop_table(_ENTRIES)
    op.drop_table(_SETS)
