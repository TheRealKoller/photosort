"""feste kategorien: photo_category_classifications + fine_labels-Umbenennung + zwei
datenverändernde Schritte

specs/features/0289-feste-kategorien.md, decisions/0049-festes-kategorien-set-mit-
vorrangreihenfolge-und-freien-feinlabels.md - vier Teile:

a) Neue Tabelle `photo_category_classifications` (1:1 zu `photos`): die remote ermittelte,
   bereits über `categories.py::resolve_category` aufgelöste Kategorie samt validierter
   Kandidatenliste.
b) Umbenennung `category_labels` -> `fine_labels`, `photo_category_detections` ->
   `photo_fine_labels`, Spalte `category_label_id` -> `fine_label_id`, Constraint ->
   `uq_fine_label_photo_label`; `photo_fine_labels.confidence` entfällt ersatzlos (ADR 0049
   Entwurfsentscheidung 7: die Zahl speiste nur die abgelöste Score-Auswahl).
c) `DELETE FROM photo_fine_labels` - die vorhandenen Zeilen stammen aus dem alten, offenen
   Prompt ("1-3 Schlagworte als Kategoriequelle") und sind unter der neuen Bedeutung
   ("Zusatzinformation neben einer Pflicht-Kategorie") nicht sinnvoll interpretierbar. Die
   Vokabular-Registry `fine_labels` BLEIBT erhalten.
d) `UPDATE photo_scores SET category_override = NULL` - PFLICHTSCHRITT, keine Aufräumaktion:
   der Override hat im Lesepfad Vorrang vor `resolve_category`; ein Altwert außerhalb des
   festen Sets würde die neue Whitelist-Validierung sonst dauerhaft umgehen (Security-Abschnitt
   der Spec 0289, Punkt 7).

`photo_rankings` bleibt bewusst UNBERÜHRT (Laufhistorie, Vorher-Stand für category_diff.py) -
dort stehen weiterhin Altwerte außerhalb des Sets.

EINBAHNSTRASSE: `downgrade()` stellt ausschließlich das SCHEMA wieder her. Die in (c) und (d)
gelöschten Daten sind nicht rekonstruierbar - beide destruktiven Schritte liegen in derselben
Revision und damit in derselben Transaktion, ein Rollback nach erfolgreichem Upgrade gibt sie
nicht zurück. Das ist von der Spec so akzeptiert ("keine erhaltenswerten Bestände") und durch
einen eigenen, benannten Test festgehalten, damit es später niemand für einen Bug hält.

Revision ID: d5e6f7a8b9c0
Revises: c2d3e4f5a6b7
Create Date: 2026-08-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # a) Neue 1:1-Tabelle (photo_id ist Primary Key, kein separates id+Unique-Paar).
    op.create_table(
        'photo_category_classifications',
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('category_key', sa.String(), nullable=False),
        sa.Column('detected_categories', sa.JSON(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id']),
        sa.PrimaryKeyConstraint('photo_id'),
    )

    # b) Naming-Migration (wertsicher, keine Neubefuellung) + Wegfall der Konfidenz.
    op.rename_table('category_labels', 'fine_labels')
    op.rename_table('photo_category_detections', 'photo_fine_labels')
    op.alter_column('photo_fine_labels', 'category_label_id', new_column_name='fine_label_id')
    with op.batch_alter_table('photo_fine_labels') as batch_op:
        batch_op.drop_constraint('uq_category_detection_photo_label', type_='unique')
        batch_op.create_unique_constraint(
            'uq_fine_label_photo_label', ['photo_id', 'fine_label_id']
        )
        batch_op.drop_column('confidence')

    # c) Bestandsdaten der alten Prompt-Generation verwerfen - die Registry selbst BLEIBT.
    op.execute(sa.text('DELETE FROM photo_fine_labels'))

    # d) Pflichtschritt (Security-Bedingung, siehe Modul-Docstring). Bewusst genau EINE Spalte:
    # alle uebrigen Werte der betroffenen photo_scores-Zeilen bleiben unveraendert.
    op.execute(sa.text('UPDATE photo_scores SET category_override = NULL'))


def downgrade() -> None:
    """Downgrade schema.

    Stellt NUR das Schema wieder her. Die in upgrade() (c)/(d) geloeschten Daten kehren NICHT
    zurueck - siehe Modul-Docstring ("Einbahnstrasse"). Kein Rollback-Versprechen."""
    with op.batch_alter_table('photo_fine_labels') as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))
        batch_op.drop_constraint('uq_fine_label_photo_label', type_='unique')
        batch_op.create_unique_constraint(
            'uq_category_detection_photo_label', ['photo_id', 'fine_label_id']
        )
    op.alter_column('photo_fine_labels', 'fine_label_id', new_column_name='category_label_id')
    op.rename_table('photo_fine_labels', 'photo_category_detections')
    op.rename_table('fine_labels', 'category_labels')
    op.drop_table('photo_category_classifications')
